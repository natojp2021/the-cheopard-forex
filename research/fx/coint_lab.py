"""Vòng 49 — COINTEGRATION β≠1 giữa hai MAJOR, khung M30/H1/H4.

VÌ SAO ĐÂY LÀ CHUYỆN KHÁC VỚI CHÂN H1 ĐANG CHẠY
================================================
`cross_mean_reversion` (H1, đang LIVE) giao dịch **cross tổng hợp**: EURUSD/GBPUSD.
Trong không gian log đó chính là spread với **β = 1 CỐ ĐỊNH**:

    log(EURGBP) = log(EURUSD) − 1,00 × log(GBPUSD)

Nhưng β = 1 là một ÁP ĐẶT, không phải kết quả đo. Nếu quan hệ thật là 1:0,7 thì
spread β=1 còn dư một phần xu hướng chưa khử — đúng phần làm nó không hồi quy.
Vòng này **khớp β từ dữ liệu** (Engle-Granger) rồi khớp lại định kỳ.

Đánh đổi phải trả: β khớp thì có sai số ước lượng, và spread β≠1 **không phải một
công cụ giao dịch được** — phải mở HAI lệnh, trả HAI spread. Cross tổng hợp chỉ trả
MỘT. Nên β≠1 phải thắng đủ nhiều để bù chi phí gấp đôi. Đó là câu hỏi của vòng này.

LUẬT — Engle-Granger + Ornstein-Uhlenbeck, tham số lấy nguyên của Zheng Nan (2025)
==================================================================================
    1. trên cửa sổ khớp kết thúc ở nến t−1: hồi quy log(y) lên log(x) → β, α
    2. spread = log(y) − β·log(x) − α
    3. ADF trên spread; loại nếu p > 0,05  (kiểm định NGAY trong cửa sổ khớp)
    4. half-life từ AR(1); loại nếu ngoài [MIN_HL, MAX_HL] nến
    5. cửa sổ z = half_life × 4,32   (= ln(1/0,05)/ln(2), thời gian phân rã 95%)
    6. vào khi |z| > 2,0 và nến trước còn NGOÀI dải → tránh vào lại liên tục
    7. ra khi z về 0, hoặc time-stop = cửa sổ z nến, hoặc |z| > 3,0 (cắt lỗ)
    8. khớp lại β mỗi REESTIMATE nến

TÍNH NHÂN QUẢ: mọi khớp (β, ADF, HL) chỉ dùng nến đã đóng trước t. Vị thế tại t−1
ăn lợi nhuận tại t.

CHỐNG OVERFIT — GIAO THỨC CHỌN CÓ TRƯỚC KHI XEM KẾT QUẢ
========================================================
21 tổ hợp × 3 khung = 63 ô. Với 63 ô thì ô tốt nhất gần như chắc chắn là nhiễu.
Nên giao thức là:
    · SÀNG trên FORM (đến 2024-01-01): giữ tổ hợp có ADF trung vị < 0,05
    · Sharpe FORM chỉ dùng để XẾP HẠNG, không dùng để chấp nhận
    · chấp nhận CHỈ KHI OOS (từ 2024-01-01) cũng dương
    · và phổ quát: cùng luật phải dương trên ≥ nửa số tổ hợp đã sàng
"""
import sys
import io
import time
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd

from src.python.shared import asset_profile as AP
from src.python.shared import fx_data as D
from src.python.shared import carry_costs as CC

pd.set_option("display.width", 260, "display.max_columns", 40, "display.max_rows", 300)
t0 = time.time()
DEV = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"

HL_MULT = 4.32
ENTRY_SIGMA = 2.0
STOP_SIGMA = 3.0
MIN_HL = 4
MAX_HL = 120
ADF_MAX = 0.05
FIT_BARS = 1500
REESTIMATE = 500
BAR_HOURS = {"M30": 0.5, "H1": 1.0, "H4": 4.0, "D1": 24.0}
BARS_YEAR = {"M30": 252 * 48, "H1": 252 * 24, "H4": 252 * 6, "D1": 252}


# ═══════════════════════════════════════════════════════ thống kê
def _adf_p(s: np.ndarray) -> float:
    """ADF không có trend, 1 độ trễ. Nội suy trên bảng giá trị tới hạn MacKinnon.

    Tự cài thay vì gọi statsmodels để lab chạy được không cần thêm phụ thuộc, và để
    thấy rõ đang kiểm định đúng cái gì.
    """
    n = len(s)
    if n < 30:
        return 1.0
    dy = np.diff(s)
    y1 = s[:-1]
    dy1 = np.concatenate([[0.0], dy[:-1]])
    X = np.column_stack([y1, np.ones(n - 1), dy1])[1:]
    Y = dy[1:]
    try:
        beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    except np.linalg.LinAlgError:
        return 1.0
    resid = Y - X @ beta
    dof = len(Y) - X.shape[1]
    if dof <= 0:
        return 1.0
    s2 = float(resid @ resid) / dof
    try:
        XtXi = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return 1.0
    se = np.sqrt(s2 * XtXi[0, 0])
    if se <= 0:
        return 1.0
    tau = float(beta[0]) / se
    # giá trị tới hạn MacKinnon (1994), mô hình có hằng số, n lớn
    crit = np.array([-3.43, -2.86, -2.57, -2.24, -1.94, -1.62])
    pval = np.array([0.01, 0.05, 0.10, 0.25, 0.50, 0.75])
    if tau <= crit[0]:
        return 0.005
    if tau >= crit[-1]:
        return 0.90
    return float(np.interp(tau, crit, pval))


def _half_life(s: np.ndarray) -> float:
    """Half-life từ AR(1): s_{t+1} = a + b·s_t. HL = −ln2/ln(b)."""
    if len(s) < 20:
        return np.nan
    x0, x1 = s[:-1], s[1:]
    X = np.column_stack([x0, np.ones(len(x0))])
    try:
        coef, *_ = np.linalg.lstsq(X, x1, rcond=None)
    except np.linalg.LinAlgError:
        return np.nan
    b = float(coef[0])
    if not (0.0 < b < 1.0):
        return np.nan
    return -np.log(2.0) / np.log(b)


# ═══════════════════════════════════════════════════════ mô phỏng một tổ hợp
def run_pair(lx: pd.Series, ly: pd.Series, cost_x: float, cost_y: float,
             swap_bar: float, timeframe: str) -> dict:
    """Spread β-hedge của hai major. Trả thống kê + chuỗi P&L ngày.

    Chi phí: mỗi lần đổi vị thế trả nửa chi phí khứ hồi trên CẢ HAI chân, chân x nhân
    thêm |β| vì khối lượng chân đối ứng tỷ lệ với β.
    """
    idx = lx.index
    x, y = lx.to_numpy(), ly.to_numpy()
    n = len(x)
    pos = np.zeros(n)                 # +1 = mua spread (mua y, bán β·x)
    betas = np.zeros(n)
    zs = np.full(n, np.nan)
    adf_hist = []

    beta = alpha = np.nan
    win = 0
    last_fit = -10 ** 9
    state = 0
    held = 0
    was_out = False

    for i in range(FIT_BARS, n):
        if i - last_fit >= REESTIMATE:
            last_fit = i
            xf, yf = x[i - FIT_BARS:i], y[i - FIT_BARS:i]
            A = np.column_stack([xf, np.ones(FIT_BARS)])
            try:
                c, *_ = np.linalg.lstsq(A, yf, rcond=None)
            except np.linalg.LinAlgError:
                beta = np.nan
            else:
                beta, alpha = float(c[0]), float(c[1])
                sp = yf - beta * xf - alpha
                p = _adf_p(sp)
                adf_hist.append(p)
                hl = _half_life(sp)
                if (p > ADF_MAX or not np.isfinite(hl)
                        or not (MIN_HL <= hl <= MAX_HL)):
                    beta = np.nan
                else:
                    win = int(round(hl * HL_MULT))

        if not np.isfinite(beta) or win < MIN_HL:
            state, held, was_out = 0, 0, False        # mất điều kiện → THOÁT
            pos[i] = 0.0
            continue

        w = min(win, i)
        sp_w = y[i - w:i] - beta * x[i - w:i] - alpha
        mu, sd = float(sp_w.mean()), float(sp_w.std(ddof=1))
        if sd <= 0:
            pos[i] = state
            continue
        z = (y[i - 1] - beta * x[i - 1] - alpha - mu) / sd
        zs[i] = z
        betas[i] = beta

        if state == 0:
            if z < -ENTRY_SIGMA and was_out:
                state, held = 1, 0
            elif z > ENTRY_SIGMA and was_out:
                state, held = -1, 0
        else:
            held += 1
            if (state == 1 and z >= 0.0) or (state == -1 and z <= 0.0):
                state, held = 0, 0                     # về trung bình
            elif abs(z) > STOP_SIGMA:
                state, held = 0, 0                     # cắt lỗ
            elif held >= win:
                state, held = 0, 0                     # time-stop
        was_out = abs(z) > ENTRY_SIGMA
        pos[i] = state

    P = pd.Series(pos, index=idx)
    B = pd.Series(betas, index=idx).replace(0.0, np.nan).ffill().fillna(1.0)

    # lợi nhuận spread: mua y, bán β·x. Chuẩn hoá theo (1+|β|) để 1 đơn vị vị thế
    # tương ứng notional gộp = 1 — nếu không, tổ hợp có β lớn sẽ giả-thắng nhờ đòn bẩy.
    ry = pd.Series(np.concatenate([[0.0], np.diff(y)]), index=idx) * 1e4
    rx = pd.Series(np.concatenate([[0.0], np.diff(x)]), index=idx) * 1e4
    scale = 1.0 / (1.0 + B.abs())
    gross = P.shift(1) * (ry - B.shift(1) * rx) * scale

    turn = P.diff().abs().fillna(P.abs())
    tcost = turn * scale * (cost_y + B.abs() * cost_x) / 2.0
    scost = P.abs().shift(1).fillna(0.0) * swap_bar * (1.0 + B.abs()) * scale
    pnl = (gross - tcost - scost).fillna(0.0)

    flips = int((turn > 0).sum())
    n_tr = max(flips // 2, 1)
    daily = pnl.resample("1D").sum().fillna(0.0)

    def sh(s, lo=None, hi=None):
        if lo is not None:
            s = s[s.index >= lo]
        if hi is not None:
            s = s[s.index < hi]
        sd_ = float(s.std(ddof=1))
        return float(s.mean()) / sd_ * np.sqrt(252) if sd_ > 0 and len(s) > 60 else np.nan

    return {"ALL": round(sh(daily), 3), "FORM": round(sh(daily, hi=DEV), 3),
            "OOS": round(sh(daily, lo=DEV), 3),
            "adf_med": round(float(np.median(adf_hist)), 4) if adf_hist else np.nan,
            "n": n_tr, "beta_med": round(float(B.median()), 3),
            "gross/l": round(float(gross.sum()) / n_tr, 2),
            "phi/l": round(float(tcost.sum() + scost.sum()) / n_tr, 2),
            "net/l": round(float(pnl.sum()) / n_tr, 2),
            "%tt": round(float((P.abs() > 0).mean()), 3),
            "hold": round(float(P.abs().sum() / max(flips / 2.0, 1.0)), 1),
            "daily": daily}


def main():
    syms = list(AP.FX_ALL)
    combos = list(combinations(syms, 2))
    print(f"{len(combos)} tổ hợp × 3 khung = {len(combos) * 3} ô\n")
    rows = []
    for tf in ("M30", "H1", "H4"):
        lp, cost = {}, {}
        for s in syms:
            b = D.build_bars(D.load_m1(s), tf)
            b = b[b.index >= "2020-01-01"]
            lp[s] = np.log(b["close"])
            px = float(b["close"].median())
            sp = float(b["spread_usd"].median())
            cost[s] = (sp + AP.get(s).commission_price_units(px)) / px * 1e4
        L = pd.DataFrame(lp).dropna()
        swap = (CC.SWAP_CALENDAR_MULTIPLIER * 1.0 / 365.0 * 100.0
                * BAR_HOURS[tf] / 24.0)
        print(f"── {tf}: {len(L):,} nến  ·  swap {swap:.4f} bps/nến")
        for a, b_ in combos:
            r = run_pair(L[a], L[b_], cost[a], cost[b_], swap, tf)
            r.pop("daily")
            rows.append({"tf": tf, "pair": f"{b_}~{a}", **r})
        print(f"   xong ({time.time() - t0:.0f}s)", flush=True)

    T = pd.DataFrame(rows)
    T.to_csv(OUT / "coint_lab.csv", index=False)

    print()
    print("=" * 160)
    print("SÀNG BƯỚC 1 — chỉ giữ tổ hợp cointegrate thật (ADF trung vị < 0,05)")
    print("=" * 160)
    S = T[T["adf_med"] < ADF_MAX].copy()
    print(f"{len(S)}/{len(T)} ô qua sàng ADF")
    print(S.sort_values("ALL", ascending=False).head(30).to_string(index=False))

    print()
    print("=" * 160)
    print("PHỔ QUÁT theo khung — trên các ô ĐÃ QUA SÀNG ADF")
    print("=" * 160)
    if len(S):
        g = S.groupby("tf").agg(
            n_cell=("ALL", "size"), ALL_med=("ALL", "median"),
            OOS_med=("OOS", "median"), n_all_pos=("ALL", lambda x: int((x > 0).sum())),
            n_oos_pos=("OOS", lambda x: int((x > 0).sum())),
            net_med=("net/l", "median"), gross_med=("gross/l", "median"),
            phi_med=("phi/l", "median"), trades=("n", "median")).round(3)
        print(g.to_string())

    print()
    print("=" * 160)
    print("CỔNG: qua ADF & FORM>0 & OOS>0 & ALL>0,4")
    print("=" * 160)
    k = S[(S["FORM"] > 0) & (S["OOS"] > 0) & (S["ALL"] > 0.4)]
    print(k.to_string(index=False) if len(k) else "  KHÔNG CÓ Ô NÀO QUA CỔNG")

    print()
    print("── TOÀN BỘ, không sàng, 15 ô tốt nhất (để thấy sàng ADF có tác dụng gì)")
    print(T.sort_values("ALL", ascending=False).head(15).to_string(index=False))
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
