"""fx_statarb_pca.py — statistical arbitrage bằng mô hình nhân tố PCA (Avellaneda & Lee).

NGUỒN — CÓ TRONG CHÍNH CORPUS NGƯỜI DÙNG CUNG CẤP
==================================================
Avellaneda, M. & Lee, J. (2010). "Statistical arbitrage in the US equities market."
*Quantitative Finance* 10(7), 761-782.

Đây là nguồn Zheng Nan (2025) trích dẫn ĐẦU TIÊN trong danh mục tham khảo, và là
người đầu tiên áp Ornstein-Uhlenbeck vào pairs trading thực hành. Nhưng phần tôi
CHƯA dùng là phần cốt lõi của họ: thay vì ghép từng cặp, họ **dựng mô hình nhân tố
bằng PCA rồi giao dịch PHẦN DƯ** của từng công cụ so với mô hình đó.

VÌ SAO KHÁC VỀ CẤU TRÚC, KHÔNG CHỈ KHÁC VỀ MỨC ĐỘ
==================================================
Ba cách tiếp cận đã thử và cách này:

    pairs cointegration   spread của HAI công cụ, hedge ratio từ hồi quy
    cắt ngang (xs)        XẾP HẠNG công cụ với nhau, long top / short bottom
    **PCA stat-arb**      PHẦN DƯ của MỘT công cụ so với k nhân tố chung của CẢ RỔ

Khác biệt quan trọng: pairs chỉ trừ được một chiều nhiễu (chân kia); cắt ngang chỉ
trừ được trung bình rổ. PCA trừ **k chiều nhiễu cùng lúc** — với FX, nhân tố 1
thường là "đô-la", nhân tố 2 là "risk-on/risk-off", nhân tố 3 là khối tiền tệ.
Sau khi trừ cả ba, phần còn lại là thứ riêng của công cụ đó.

Nên đây không phải biến thể của những gì đã thử. Nó là một cách khử nhiễu khác hẳn.

LUẬT — LẤY NGUYÊN THAM SỐ CỦA HỌ
=================================
Avellaneda & Lee §4 định nghĩa **s-score** và bốn ngưỡng. Tôi dùng đúng số của họ,
không tinh chỉnh:

    s = (X_t − m) / σ_eq        X = phần dư tích luỹ, khớp vào OU
    mở LONG    khi s < −1,25        đóng LONG    khi s > −0,50
    mở SHORT   khi s > +1,25        đóng SHORT   khi s < +0,75

Bốn ngưỡng KHÔNG đối xứng, và đó là có chủ ý trong bài gốc: ngưỡng đóng short (0,75)
xa 0 hơn ngưỡng đóng long (0,50). Tôi giữ nguyên bất đối xứng đó thay vì "làm cho
gọn" — nó là một phần của kết quả họ báo.

Quy trình mỗi ngày (họ dùng cửa sổ 60 ngày, tôi giữ):
    1. lấy ma trận lợi nhuận chuẩn hoá của N công cụ trên cửa sổ 60 kỳ TRƯỚC
    2. PCA -> giữ k nhân tố đầu
    3. với từng công cụ: hồi quy lợi nhuận lên k nhân tố -> phần dư
    4. phần dư tích luỹ -> khớp AR(1)/OU -> tính s-score
    5. áp bốn ngưỡng trên

TÍNH NHÂN QUẢ: PCA, hồi quy và OU đều khớp trên cửa sổ KẾT THÚC ở kỳ t−1. Vị thế
tính từ s-score tại t−1, áp cho lợi nhuận kỳ t. Không có bước nào chạm dữ liệu tương lai.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

FORM_END = pd.Timestamp("2024-01-01")

# Ngưỡng s-score — Avellaneda & Lee §4. Không tinh chỉnh.
S_OPEN_LONG = -1.25
S_CLOSE_LONG = -0.50
S_OPEN_SHORT = +1.25
S_CLOSE_SHORT = +0.75

WINDOW = 60          # cửa sổ khớp, bằng số kỳ (họ dùng 60 ngày)
N_FACTORS = 3        # nhân tố: đô-la · risk-on/off · khối tiền tệ
MIN_OU_KAPPA = 0.0   # loại công cụ không hồi quy về trung bình


@dataclass(frozen=True)
class Config:
    window: int = WINDOW
    n_factors: int = N_FACTORS
    s_open_long: float = S_OPEN_LONG
    s_close_long: float = S_CLOSE_LONG
    s_open_short: float = S_OPEN_SHORT
    s_close_short: float = S_CLOSE_SHORT
    # Avellaneda & Lee loại công cụ có tốc độ hồi quy quá chậm so với cửa sổ:
    # κ·window phải đủ lớn, nếu không thì "phần dư" chỉ là xu hướng chưa khớp.
    min_kappa_window: float = 2.0


def _pca_residual_scores(R: np.ndarray, cfg: Config) -> np.ndarray:
    """s-score của từng công cụ tại kỳ CUỐI của cửa sổ `R` (shape = window × N).

    Trả mảng N phần tử; NaN nghĩa là công cụ đó không đủ điều kiện (không hồi quy
    về trung bình đủ nhanh, hoặc phần dư suy biến).
    """
    n_obs, n_ins = R.shape
    if n_obs < 20 or n_ins < cfg.n_factors + 2:
        return np.full(n_ins, np.nan)

    # chuẩn hoá theo công cụ trước khi PCA — nếu không, công cụ biến động lớn sẽ
    # chiếm hết nhân tố đầu và "nhân tố chung" chỉ là chính công cụ đó
    mu, sd = R.mean(axis=0), R.std(axis=0, ddof=1)
    sd = np.where(sd > 0, sd, np.nan)
    Z = (R - mu) / sd
    if not np.isfinite(Z).all():
        return np.full(n_ins, np.nan)

    # PCA qua SVD trên ma trận đã chuẩn hoá
    try:
        U, S, Vt = np.linalg.svd(Z, full_matrices=False)
    except np.linalg.LinAlgError:
        return np.full(n_ins, np.nan)
    k = min(cfg.n_factors, len(S))
    F = U[:, :k] * S[:k]                     # điểm nhân tố, window × k

    out = np.full(n_ins, np.nan)
    A = np.column_stack([F, np.ones(n_obs)])
    for j in range(n_ins):
        y = Z[:, j]
        try:
            beta, *_ = np.linalg.lstsq(A, y, rcond=None)
        except np.linalg.LinAlgError:
            continue
        resid = y - A @ beta
        X = np.cumsum(resid)                 # phần dư TÍCH LUỸ — biến của OU

        # khớp AR(1) trên X: X_{t+1} = a + b·X_t + ε
        x0, x1 = X[:-1], X[1:]
        if len(x0) < 10:
            continue
        B = np.column_stack([x0, np.ones(len(x0))])
        try:
            coef, *_ = np.linalg.lstsq(B, x1, rcond=None)
        except np.linalg.LinAlgError:
            continue
        b_ar, a_ar = float(coef[0]), float(coef[1])
        if not (0.0 < b_ar < 1.0):
            continue                          # không hồi quy về trung bình
        kappa = -np.log(b_ar)
        if kappa * cfg.window < cfg.min_kappa_window:
            continue                          # hồi quy quá chậm so với cửa sổ
        m_eq = a_ar / (1.0 - b_ar)
        var_eps = float(np.var(x1 - B @ coef, ddof=2))
        var_eq = var_eps / (1.0 - b_ar ** 2)
        if var_eq <= 0:
            continue
        out[j] = (X[-1] - m_eq) / np.sqrt(var_eq)
    return out


def build_positions(returns: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    """Vị thế (+1/−1/0) cho từng công cụ theo luật s-score.

    `returns` = lợi nhuận log theo kỳ (bps hoặc tỷ lệ đều được — s-score bất biến
    theo đơn vị vì đã chuẩn hoá).
    """
    R = returns.to_numpy(dtype=float)
    n, m = R.shape
    pos = np.zeros((n, m))
    state = np.zeros(m)

    for i in range(cfg.window, n):
        win = R[i - cfg.window:i]            # KẾT THÚC ở i−1, không gồm kỳ i
        if not np.isfinite(win).all():
            pos[i] = state
            continue
        s = _pca_residual_scores(win, cfg)
        for j in range(m):
            sj = s[j]
            if not np.isfinite(sj):
                state[j] = 0.0               # mất điều kiện -> THOÁT, không giữ
                continue
            if state[j] == 0.0:
                if sj < cfg.s_open_long:
                    state[j] = 1.0
                elif sj > cfg.s_open_short:
                    state[j] = -1.0
            elif state[j] > 0 and sj > cfg.s_close_long:
                state[j] = 0.0
            elif state[j] < 0 and sj < cfg.s_close_short:
                state[j] = 0.0
        pos[i] = state
    return pd.DataFrame(pos, index=returns.index, columns=returns.columns)


# ═══════════════════════════════════════════════════════ mô phỏng
@dataclass
class Result:
    pnl: pd.Series                  # bps mỗi kỳ, danh mục chia đều
    positions: pd.DataFrame
    gross_bps: float
    cost_bps: float
    swap_bps: float
    n_trades: int
    time_in_market: float
    avg_positions: float


def simulate(returns: pd.DataFrame, pos: pd.DataFrame,
             cost_1rt_bps: pd.Series, swap_bps_per_bar: pd.Series) -> Result:
    """Vị thế tại kỳ t ăn lợi nhuận kỳ t+1. Chia đều giữa các công cụ đang mở."""
    ret = returns.reindex_like(pos)
    gross = (pos.shift(1) * ret).sum(axis=1)
    turn = pos.diff().abs().fillna(pos.abs())
    tcost = (turn * cost_1rt_bps.reindex(pos.columns) / 2.0).sum(axis=1)
    scost = (pos.abs().shift(1) * swap_bps_per_bar.reindex(pos.columns)).sum(axis=1)

    n_act = pos.abs().sum(axis=1).replace(0, np.nan)
    scale = (1.0 / n_act).fillna(0.0)
    pnl = ((gross - tcost - scost) * scale).fillna(0.0)
    return Result(
        pnl=pnl, positions=pos,
        gross_bps=float((gross * scale).mean()),
        cost_bps=float((tcost * scale).mean()),
        swap_bps=float((scost * scale).mean()),
        n_trades=int((turn > 0).sum().sum() // 2),
        time_in_market=float((pos.abs().sum(axis=1) > 0).mean()),
        avg_positions=float(pos.abs().sum(axis=1).mean()))


def stats(pnl: pd.Series, label: str = "", periods_per_year: float = 252.0
          ) -> Dict[str, object]:
    s = pnl[pnl.index >= pd.Timestamp("2020-04-01")]
    if len(s) < 60 or float(s.std(ddof=1)) <= 0:
        return {"label": label, "sharpe": np.nan}
    cum = s.cumsum()
    dd = cum.cummax() - cum
    yrs = max((s.index.max() - s.index.min()).days / 365.25, 1e-9)
    return {
        "label": label,
        "sharpe": round(float(s.mean()) / float(s.std(ddof=1))
                        * np.sqrt(periods_per_year), 3),
        "ann_pct": round(float(cum.iloc[-1]) / 100.0 / yrs, 2),
        "max_dd_pct": round(float(dd.max()) / 100.0, 2),
        "hit": round(float((s[s != 0] > 0).mean()), 3) if (s != 0).any() else np.nan,
    }
