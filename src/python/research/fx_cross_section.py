"""fx_cross_section.py — sức mạnh tiền tệ cắt ngang (cross-sectional currency strategies).

VÌ SAO HƯỚNG NÀY, VÀ VÌ SAO BÂY GIỜ
===================================
Ba hướng ĐỊNH HƯỚNG (directional) đã bị bác bỏ bằng đo lường:

  1. Mẫu hình giá đơn công cụ (8 family × 3 cặp × 3 khung) — 28/33 NO_INFORMATION,
     MFE/|MAE| ≈ 1,00 (`docs/forex/00_ket_qua_vong_1.md`)
  2. Hiệu ứng fix ở cấp giờ — tín hiệu thật (t = −3,83, đặc tả trước) nhưng độ lớn
     ≈ 1 lượt khứ hồi; thất bại cả 3 cổng, control p = 0,56, DSR = 0,0000
  3. Momentum 20/120 ngày — chi phí chỉ ăn 0,5-7,4% lợi nhuận gộp (tức chi phí KHÔNG
     còn là ràng buộc), nhưng chính tín hiệu âm: danh mục Sharpe −0,07, 2/7 năm dương,
     EURUSD 11 năm Sharpe −0,13

Cả ba đều là cược vào HƯỚNG của một cặp so với USD. Và cả ba đều bị nhiễu bởi cùng
một thứ: **drift của chính USD trong cửa sổ 2020-2026** (chu kỳ siêu tăng 2022 rồi
đảo chiều). Một cửa sổ 6 năm chứa một chế độ vĩ mô áp đảo thì mọi cược có hướng đều
đang đo chế độ đó, không đo tín hiệu.

Cắt ngang khác về BẢN CHẤT, không chỉ về mức độ:

    long đồng MẠNH NHẤT  +  short đồng YẾU NHẤT   →   phơi nhiễm USD ròng ≈ 0

Thành phần chung (USD lên/xuống toàn cục) bị TRIỆT TIÊU về mặt cấu trúc. Đó chính là
điều mà `docs/forex/00_ket_qua_vong_1.md` §6 nêu như yêu cầu kiến trúc: `EURUSD BUY +
GBPUSD BUY + AUDUSD BUY` thực chất là MỘT cược "USD yếu"; xếp hạng cắt ngang biến nó
thành cược tương đối thật.

GIẢ THUYẾT — ĐẶC TẢ TRƯỚC
=========================
Menkhoff, L., Sarno, L., Schmeling, M. & Schrimpf, A. (2012). "Currency Momentum
Strategies." *Journal of Financial Economics* 106(3). Cũng BIS Working Paper 366.

  * Chênh lệch lợi nhuận cắt ngang **tới 10%/năm** giữa đồng thắng và đồng thua quá khứ
  * KHÔNG giải thích được bằng nhân tố rủi ro truyền thống
  * **Không tương quan cao** với carry, cũng không với các quy tắc kỹ thuật chuẩn
  * Lookback có edge trong khoảng **1–12 tháng**, tái cân bằng tháng

⚠️ Cảnh báo của chính tác giả, phải ghi vào verdict: *"giải thích MỘT PHẦN bằng chi
phí giao dịch"* và *"dường như có những **giới hạn arbitrage rất hiệu quả** ngăn lợi
nhuận momentum khỏi bị khai thác dễ dàng trên thị trường tiền tệ."*

Và một cấu hình đối chứng bắt buộc: Menkhoff et al. (2014) *Currency Value* đo được
tỷ giá thực dự báo excess return **theo chiều NGƯỢC** với trực giác value. Nghĩa là
trên FX, chiều của tín hiệu cắt ngang KHÔNG hiển nhiên. Vì vậy ở đây **cả hai chiều
đều được báo cáo** (momentum và reversal), và cái nào được chọn phải do OOS quyết,
không do tôi chọn sau khi xem DEV.

DỰNG SỨC MẠNH TỪNG ĐỒNG TIỀN
============================
Ta có 7 cặp vs USD → 8 đồng tiền. Lợi nhuận log của một đồng so với USD:
    XXXUSD  ->  r(XXX) = +Δlog(price)
    USDXXX  ->  r(XXX) = −Δlog(price)
    r(USD)  =  −(trung bình r của 7 đồng kia)      [chuẩn hoá tổng bằng 0]
Cách chuẩn hoá này làm rổ 8 đồng có tổng lợi nhuận 0 mỗi kỳ, tức mọi chiến lược
long-short trên đó **dollar-neutral về mặt xây dựng**.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.python.shared import fx_data as D
from src.python.shared import asset_profile as AP

PAIRS: Tuple[str, ...] = AP.FX_ALL          # 7 cặp vs USD
CCYS: Tuple[str, ...] = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD")

DEV_END = pd.Timestamp("2024-01-01")


# ═══════════════════════════════════════════════════ dựng ma trận lợi nhuận đồng tiền
def pair_daily(symbols: Sequence[str] = PAIRS,
               start: str = "2020-01-01") -> Tuple[pd.DataFrame, pd.DataFrame]:
    """(lợi nhuận log D1 của từng CẶP, chi phí khứ hồi bps của từng cặp)."""
    rets, costs = {}, {}
    for sym in symbols:
        m1 = D.load_m1(sym)
        # KHÔNG truyền `origin=`: nó bằng mặc định và đổi hành vi theo phiên bản pandas — xem
        # `shared/fx_data.build_bars`. Lưới D1 là nửa đêm UTC.
        g = m1.resample("1D")
        d = g.agg({"close": "last", "spread_usd": "median"}).dropna(subset=["close"])
        d = d[d.index >= start]
        rets[sym] = np.log(d["close"]).diff()
        prof = AP.get(sym)
        px = float(d["close"].median()); sp = float(d["spread_usd"].median())
        costs[sym] = (sp + prof.commission_price_units(px)) / px * 1e4
    R = pd.DataFrame(rets).dropna(how="all")
    return R, pd.Series(costs, name="cost_1rt_bps")


def ccy_returns(R: pd.DataFrame) -> pd.DataFrame:
    """Lợi nhuận log của 8 đồng tiền, chuẩn hoá tổng = 0 mỗi ngày (bps)."""
    out = {}
    for sym in R.columns:
        prof = AP.get(sym)
        foreign = prof.base if prof.quote_is_usd else prof.quote
        out[foreign] = (R[sym] if prof.quote_is_usd else -R[sym]) * 1e4
    F = pd.DataFrame(out)
    F["USD"] = -F.mean(axis=1)
    return F.sub(F.mean(axis=1), axis=0)        # tổng = 0


# ═══════════════════════════════════════════════════ chiến lược xếp hạng
@dataclass
class XsConfig:
    lookback_days: int = 21           # ~1 tháng — đầu dưới dải 1-12 tháng của nguồn
    rebalance_days: int = 21          # tái cân bằng tháng
    n_long: int = 3                   # nguồn dùng 3 cao / 3 thấp (như carry của [C])
    n_short: int = 3
    sign: int = +1                    # +1 = momentum (long đồng mạnh); −1 = reversal
    vol_window: int = 63              # chuẩn hoá rủi ro theo biến động đồng tiền


def _pair_for(ccy: str) -> Tuple[str, int]:
    """Cặp dùng để giao dịch một đồng tiền, và dấu: +1 nếu long đồng = long cặp."""
    for sym in PAIRS:
        prof = AP.get(sym)
        if prof.quote_is_usd and prof.base == ccy:
            return sym, +1
        if prof.base == "USD" and prof.quote == ccy:
            return sym, -1
    raise KeyError(ccy)


def run_xs(F: pd.DataFrame, costs: pd.Series, cfg: XsConfig,
           start: Optional[str] = None) -> pd.DataFrame:
    """Mô phỏng chiến lược cắt ngang. Trả bảng theo ngày: gross/cost/net (bps).

    Nhân quả: xếp hạng dùng lợi nhuận tích luỹ đến hết ngày `t−1`; vị thế áp cho
    ngày `t`. Tái cân bằng mỗi `rebalance_days`; giữa hai lần tái cân bằng vị thế
    KHÔNG đổi (đó là điều giữ chi phí thấp).
    """
    if start:
        F = F[F.index >= start]
    cum = F.cumsum()
    mom = (cum - cum.shift(cfg.lookback_days))          # lợi nhuận lookback
    vol = F.rolling(cfg.vol_window, min_periods=cfg.vol_window // 2).std()

    dates = F.index
    weights = pd.DataFrame(0.0, index=dates, columns=F.columns)
    last_w = pd.Series(0.0, index=F.columns)
    for i, t in enumerate(dates):
        if i % cfg.rebalance_days == 0:
            sig = mom.iloc[i - 1] if i > 0 else None
            v = vol.iloc[i - 1] if i > 0 else None
            if sig is not None and sig.notna().sum() >= cfg.n_long + cfg.n_short \
                    and v is not None and v.notna().sum() >= cfg.n_long + cfg.n_short:
                s = (cfg.sign * sig).dropna()
                order = s.sort_values(ascending=False)
                longs = list(order.index[:cfg.n_long])
                shorts = list(order.index[-cfg.n_short:])
                w = pd.Series(0.0, index=F.columns)
                # inverse-vol trong mỗi chân, rồi chuẩn hoá gộp về 1 đơn vị rủi ro
                for grp, sgn in ((longs, +1.0), (shorts, -1.0)):
                    iv = (1.0 / v[grp].replace(0, np.nan)).fillna(0.0)
                    if iv.sum() > 0:
                        w[grp] = sgn * iv / iv.sum()
                last_w = w
        weights.loc[t] = last_w

    gross = (weights * F).sum(axis=1)

    # ── chi phí: quy tỷ trọng ĐỒNG TIỀN về tỷ trọng CẶP rồi đo thay đổi
    pw = pd.DataFrame(0.0, index=dates, columns=list(PAIRS))
    for ccy in F.columns:
        if ccy == "USD":
            continue
        sym, sgn = _pair_for(ccy)
        pw[sym] = pw[sym] + sgn * weights[ccy]
    turn = pw.diff().abs().fillna(pw.abs())
    cost = (turn * costs.reindex(pw.columns)).sum(axis=1) / 2.0

    return pd.DataFrame({"gross_bps": gross, "cost_bps": cost,
                         "net_bps": gross - cost}).dropna()


# ═══════════════════════════════════════════════════ chỉ số
def stats(s: pd.Series, label: str) -> Dict[str, object]:
    if len(s) < 30:
        return {"label": label, "n_days": len(s)}
    cum = s.cumsum()
    dd = (cum.cummax() - cum)
    ann = 252.0
    sd = float(s.std(ddof=1))
    years = max((s.index.max() - s.index.min()).days / 365.25, 1e-9)
    down = float(s[s < 0].std(ddof=1)) if (s < 0).any() else np.nan
    ann_ret = float(cum.iloc[-1]) / 100.0 / years
    mdd = float(dd.max()) / 100.0
    return {
        "label": label, "n_days": len(s),
        "ann_ret_pct": round(ann_ret, 2),
        "ann_vol_pct": round(sd * np.sqrt(ann) / 100.0, 2),
        "sharpe": round(float(s.mean()) / sd * np.sqrt(ann), 3) if sd > 0 else np.nan,
        "sortino": round(float(s.mean()) / down * np.sqrt(ann), 3) if down and down > 0 else np.nan,
        "max_dd_pct": round(mdd, 2),
        "calmar": round(ann_ret / mdd, 3) if mdd > 0 else np.nan,
        "hit_rate": round(float((s > 0).mean()), 3),
    }
