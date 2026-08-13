"""fx_cointegration.py — pairs trading cointegration ở khung H1, theo phương pháp Zheng Nan.

NGUỒN — LẤY NGUYÊN QUY TRÌNH, KHÔNG TỰ CHẾ
==========================================
Zheng Nan (2025), *Profitability of Pairs Trading Based on Cointegration in the
Foreign Exchange Market*, MSc thesis — một trong 10 tài liệu người dùng cung cấp.
Quy trình 12 bước của họ (§3 `docs/forex/01_kien_thuc_nen_forex.md`) được áp
NGUYÊN VĂN ở đây, chỉ đổi khung thời gian từ NGÀY sang H1.

Vì sao đáng thử ở H1 dù chín hướng nội ngày đã đổ: mọi hướng đó đo tín hiệu trên
MỘT chuỗi giá. Pairs trading đo trên SPREAD của hai chuỗi tương quan cao, và spread
có biến động thấp hơn nhiều so với từng chân:

    EURUSD H1 vol ≈ 11,8 bps
    spread EURUSD−β·GBPUSD (corr ≈ 0,9) ≈ √(2(1−0,9)) × 11,8 ≈ 5,3 bps

Cùng một mức lệch giá tuyệt đối vì thế là một TỶ LỆ lớn hơn nhiều trên spread. Một
cú lệch 2σ của spread ≈ 10,6 bps so với chi phí hai chân ≈ 2,1 bps — tỷ lệ 5:1,
trong khi mọi tín hiệu một-chuỗi ở H1 chỉ đạt 0,06-0,30.

Đó là lý do CẤU TRÚC để hướng này khác, không phải hy vọng.

⚠️ ĐỐI CHỨNG PHẢI NHỚ: Jirapongpan & Phumchusri (IEEE) đã thử pairs trading FX ở
đúng khung H1 và THẤT BẠI. Nhưng họ dùng **chênh lệch RSI** làm tín hiệu — không
có cointegration, không hedge ratio, không half-life. Bản này khác ở đúng ba thứ đó.

QUY TRÌNH (Zheng Nan §4)
========================
 1. log giá mọi chuỗi
 2. ADF trên từng chuỗi — phải KHÔNG bác bỏ unit root (chuỗi là I(1))
 3. Johansen trên cặp → quan hệ cointegration + hệ số hedge β
 4. Lọc: |β| trong [2/3, 2]  (chặn một chân áp đảo chân kia)
 5. spread S_t = ln(P_x) − β·ln(P_y) − c
 6. half-life từ AR(1):  ΔS_t = α·S_{t−1} + ε  →  HL = ln2 / |ln(1+α)|
 7. cửa sổ Bollinger = HL × 4,32   (thời gian phân rã 95%, không phải 50%)
 8. ngưỡng ±2σ
 9. VÀO: spread ra NGOÀI dải RỒI QUAY VÀO LẠI — không vào ngay lúc xuyên dải
10. RA: spread cắt đường trung bình
11. DỪNG: time-stop = ceil(4,32 × HL) bar, KHÔNG dùng 3σ
12. sizing: hai chân cân bằng theo β

Điểm 9 và 11 là hai chỗ Zheng Nan đo được cải thiện lớn nhất (+85% P&L khi đổi từ
stop 3σ sang time-stop; P&L ×5 khi đổi từ cửa sổ cố định sang HL×4,32).

TÁCH MẪU
========
    FORM  2020-2024  chọn cặp, ước lượng β và HL      (không đo hiệu suất)
    OOS   2024-2026  CHỈ đọc để kết luận
β và HL được ước lượng lại theo cửa sổ TRƯỢT trong OOS (Zheng Nan §4.2.4 cảnh báo
quan hệ cointegration có thể biến mất; Clegg 2014).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.python.shared import asset_profile as AP
from src.python.shared import fx_data as D

FORM_END = pd.Timestamp("2024-01-01")

# Ngưỡng lấy từ Zheng Nan §4.2.2 — không tinh chỉnh.
BETA_MIN, BETA_MAX = 2.0 / 3.0, 2.0
HL_MULTIPLIER = 4.32        # ln(1/0,05)/ln(2) — thời gian phân rã 95%
ENTRY_SIGMA = 2.0
ADF_PVALUE_MAX = 0.05


@dataclass(frozen=True)
class Config:
    hl_multiplier: float = HL_MULTIPLIER
    entry_sigma: float = ENTRY_SIGMA
    min_hl_bars: int = 4          # HL quá ngắn = nhiễu vi cấu trúc, không phải quan hệ
    max_hl_bars: int = 240        # HL > 10 ngày ở H1 -> quá chậm cho khung này
    reestimate_bars: int = 500    # tần suất ước lượng lại β và HL
    require_reentry: bool = True  # Zheng Nan §4.3.1 — chờ quay vào dải


# ═══════════════════════════════════════════════════════ ước lượng
def hedge_ratio(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """β và hằng số từ OLS trên log giá. Trả (beta, const).

    Dùng OLS thay Johansen ở tầng ước lượng TRƯỢT vì Johansen đắt hơn nhiều lần và
    trên cặp hai chuỗi hai phương pháp cho β rất gần nhau. Johansen vẫn được dùng ở
    tầng CHỌN CẶP (`screen_pairs`), nơi độ chính xác của kiểm định quan trọng hơn tốc độ.
    """
    A = np.column_stack([y, np.ones(len(y))])
    coef, *_ = np.linalg.lstsq(A, x, rcond=None)
    return float(coef[0]), float(coef[1])


def half_life(spread: np.ndarray) -> float:
    """HL từ AR(1) trên spread: ΔS = α·S_{t−1} + ε → HL = ln2/|ln(1+α)|.

    Trả `inf` nếu α >= 0 (không hồi quy về trung bình) — caller phải loại cặp đó.
    """
    s = spread[~np.isnan(spread)]
    if len(s) < 30:
        return float("inf")
    ds, lag = np.diff(s), s[:-1]
    A = np.column_stack([lag, np.ones(len(lag))])
    coef, *_ = np.linalg.lstsq(A, ds, rcond=None)
    alpha = float(coef[0])
    if alpha >= 0 or (1.0 + alpha) <= 0:
        return float("inf")
    return float(np.log(2.0) / abs(np.log(1.0 + alpha)))


def screen_pairs(logp: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    """Bước 2-6: lọc cặp qua ADF + Johansen + ràng buộc β + half-life.

    Chạy trên CỬA SỔ FORM. Trả bảng các cặp đủ điều kiện kèm β, HL, p-value.
    """
    from statsmodels.tsa.stattools import adfuller
    from statsmodels.tsa.vector_ar.vecm import coint_johansen

    # bước 2: mỗi chuỗi phải là I(1) — KHÔNG được tự nó đã dừng
    integrated = {}
    for c in logp.columns:
        try:
            p = adfuller(logp[c].dropna(), maxlag=12, autolag=None)[1]
        except Exception:
            p = 0.0
        integrated[c] = p > ADF_PVALUE_MAX      # không bác bỏ unit root -> I(1)

    rows = []
    for a, b in combinations(logp.columns, 2):
        if not (integrated.get(a) and integrated.get(b)):
            continue
        sub = logp[[a, b]].dropna()
        if len(sub) < 500:
            continue
        x, y = sub[a].to_numpy(), sub[b].to_numpy()
        try:
            jres = coint_johansen(sub.to_numpy(), det_order=0, k_ar_diff=1)
            trace_stat = float(jres.lr1[0])
            crit_95 = float(jres.cvt[0, 1])
            cointegrated = trace_stat > crit_95
            v = jres.evec[:, 0]
            beta_j = float(-v[1] / v[0]) if v[0] != 0 else np.nan
        except Exception:
            continue
        if not cointegrated:
            continue
        beta, const = hedge_ratio(x, y)
        if not (BETA_MIN <= abs(beta) <= BETA_MAX):
            continue
        spread = x - beta * y - const
        try:
            adf_p = adfuller(spread, maxlag=12, autolag=None)[1]
        except Exception:
            adf_p = 1.0
        if adf_p > ADF_PVALUE_MAX:
            continue
        hl = half_life(spread)
        if not (cfg.min_hl_bars <= hl <= cfg.max_hl_bars):
            continue
        rows.append({"x": a, "y": b, "beta": round(beta, 4),
                     "beta_johansen": round(beta_j, 4) if np.isfinite(beta_j) else None,
                     "half_life_bars": round(hl, 1),
                     "window_bars": int(np.ceil(hl * cfg.hl_multiplier)),
                     "adf_p_spread": round(adf_p, 5),
                     "johansen_trace": round(trace_stat, 2),
                     "corr": round(float(np.corrcoef(np.diff(x), np.diff(y))[0, 1]), 3)})
    return pd.DataFrame(rows).sort_values("adf_p_spread") if rows else pd.DataFrame()


# ═══════════════════════════════════════════════════════ mô phỏng
@dataclass
class PairTrade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    side: int               # +1 long spread (mua x, bán y), −1 ngược lại
    entry_z: float
    exit_reason: str        # MEAN | TIMESTOP
    gross_bps: float
    cost_bps: float
    net_bps: float
    bars_held: int


def simulate_pair(px: pd.Series, py: pd.Series, cost_x: float, cost_y: float,
                  cfg: Config = Config(),
                  start: Optional[pd.Timestamp] = None) -> List[PairTrade]:
    """Mô phỏng một cặp theo đúng luật 5-11. β và HL ước lượng lại TRƯỢT.

    Chi phí: mỗi lệnh mở+đóng = 2 chân × khứ hồi. Đây là nhược điểm cấu trúc của
    pairs trading và phải tính đủ, không được coi là "một lệnh".
    """
    idx = px.index.intersection(py.index)
    lx, ly = np.log(px.reindex(idx)).to_numpy(), np.log(py.reindex(idx)).to_numpy()
    n = len(idx)
    cost_rt = cost_x + cost_y            # bps, hai chân, khứ hồi

    trades: List[PairTrade] = []
    pos = 0
    entry_i = -1
    entry_spread = 0.0
    entry_z = 0.0
    was_outside = 0                      # −1 dưới dải, +1 trên dải, 0 trong dải
    beta = const = hl = window = None
    last_fit = -10 ** 9
    start_i = idx.searchsorted(start) if start is not None else 0

    for i in range(600, n):
        # ── ước lượng lại β/HL theo chu kỳ, CHỈ dùng dữ liệu quá khứ
        if i - last_fit >= cfg.reestimate_bars:
            w = slice(max(0, i - 2000), i)
            b, c0 = hedge_ratio(lx[w], ly[w])
            if BETA_MIN <= abs(b) <= BETA_MAX:
                sp = lx[w] - b * ly[w] - c0
                h = half_life(sp)
                if cfg.min_hl_bars <= h <= cfg.max_hl_bars:
                    beta, const, hl = b, c0, h
                    window = int(np.ceil(h * cfg.hl_multiplier))
            last_fit = i
        if beta is None or window is None:
            continue

        w0 = max(0, i - window)
        hist = lx[w0:i] - beta * ly[w0:i] - const
        if len(hist) < max(20, window // 2):
            continue
        mu, sd = float(np.mean(hist)), float(np.std(hist, ddof=1))
        if sd <= 0:
            continue
        s_now = lx[i] - beta * ly[i] - const
        z = (s_now - mu) / sd

        # ── quản lý vị thế đang mở
        if pos != 0:
            crossed_mean = (pos == 1 and s_now >= mu) or (pos == -1 and s_now <= mu)
            timeout = (i - entry_i) >= int(np.ceil(hl * cfg.hl_multiplier))
            if crossed_mean or timeout:
                gross = pos * (s_now - entry_spread) * 1e4
                trades.append(PairTrade(
                    entry_time=idx[entry_i], exit_time=idx[i], side=pos,
                    entry_z=round(entry_z, 2),
                    exit_reason="MEAN" if crossed_mean else "TIMESTOP",
                    gross_bps=round(gross, 3), cost_bps=round(cost_rt, 3),
                    net_bps=round(gross - cost_rt, 3), bars_held=i - entry_i))
                pos = 0
            continue

        # ── tín hiệu vào: ra NGOÀI dải rồi QUAY VÀO (bước 9)
        if cfg.require_reentry:
            if z > cfg.entry_sigma:
                was_outside = 1
            elif z < -cfg.entry_sigma:
                was_outside = -1
            elif was_outside == 1 and z <= cfg.entry_sigma and i >= start_i:
                pos, entry_i, entry_spread, entry_z = -1, i, s_now, z
                was_outside = 0
            elif was_outside == -1 and z >= -cfg.entry_sigma and i >= start_i:
                pos, entry_i, entry_spread, entry_z = +1, i, s_now, z
                was_outside = 0
        else:
            if z > cfg.entry_sigma and i >= start_i:
                pos, entry_i, entry_spread, entry_z = -1, i, s_now, z
            elif z < -cfg.entry_sigma and i >= start_i:
                pos, entry_i, entry_spread, entry_z = +1, i, s_now, z
    return trades


def load_logprices(symbols: Sequence[str] = AP.FX_ALL, timeframe: str = "H1",
                   start: str = "2020-01-01") -> Tuple[pd.DataFrame, pd.Series]:
    """log giá đóng của mọi cặp trên lưới chung + chi phí khứ hồi mỗi cặp (bps)."""
    closes, costs = {}, {}
    for sym in symbols:
        b = D.build_bars(D.load_m1(sym), timeframe)
        b = b[b.index >= start]
        closes[sym] = b["close"]
        prof = AP.get(sym)
        px = float(b["close"].median()); sp = float(b["spread_usd"].median())
        costs[sym] = (sp + prof.commission_price_units(px)) / px * 1e4
    df = pd.DataFrame(closes).dropna()
    return np.log(df), pd.Series(costs, name="cost_1rt_bps")
