"""Vòng 51 — TỐI ƯU công thức `xs_z` (xếp hạng cắt ngang theo z trên 20 cross).

VÒNG 50 ĐÃ CHO GÌ
=================
`xs_z` ở H1 cho ALL 0,280 · FORM 0,293 · OOS 0,259 — **ổn định gần như hoàn hảo qua
hai cửa sổ**, và tương quan với chân H1 đang LIVE chỉ 0,252. Đó là hai tính chất khó
có cùng lúc, nên hướng này đáng đào sâu thay vì bỏ.

Vấn đề duy nhất đo được: chi phí ăn **58% gross** (0,0504 / 0,0870 bps mỗi nến), do
tái cân bằng 25 lượt/năm. Nếu edge là thật thì giảm tần suất phải LÀM TĂNG Sharpe —
vì gross giảm chậm hơn chi phí. Nếu Sharpe giảm khi giãn tần suất, edge chỉ là nhiễu
tần số cao và phải loại. Đó là một kiểm định, không phải một vòng tinh chỉnh.

BỐN TRỤC ĐO
===========
    window     cửa sổ tính z (ngày giao dịch, quy đổi sang nến từng khung)
    n_leg      số cross mỗi chân
    rebalance  giãn cách tái cân bằng (ngày giao dịch)
    vol gate   chỉ giao dịch khi biến động rổ DƯỚI phân vị q trượt 252 ngày

CỔNG CHẤP NHẬN — đặt TRƯỚC khi xem kết quả
==========================================
    1. FORM > 0 VÀ OOS > 0            (không chấp nhận ô chỉ đẹp một nửa)
    2. ALL > 0,45
    3. VÙNG THAM SỐ: ô lân cận phải cùng dấu — đỉnh cô lập là nhiễu
    4. |corr| với chân H1 đang LIVE < 0,7
"""
import sys
import io
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":          # chỉ bọc khi chạy trực tiếp — nếu bọc lúc import
    # thì wrapper bị thu hồi và đóng luôn stdout của script gọi nó
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import numpy as np
import pandas as pd

from src.python.research import fx_cross_lab as LAB

pd.set_option("display.width", 260, "display.max_columns", 40, "display.max_rows", 400)
t0 = time.time()
DEV = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"
BARS_DAY = {"M30": 48, "H1": 24, "H4": 6, "D1": 1}


def sig_xs_zscore(panel, *, window: int, n_leg: int, rebalance: int,
                  vol_q: float | None = None) -> pd.DataFrame:
    """Xếp hạng cắt ngang theo z. `vol_q` = cổng biến động rổ (None = tắt cổng).

    Cổng biến động dùng phân vị TRƯỢT của 252 ngày TRƯỚC (`.shift(1)`) — bản toàn mẫu
    sẽ dùng thông tin tương lai và không chạy được live.
    """
    lp = panel.logp
    mu = lp.rolling(window, min_periods=window // 2).mean()
    sd = lp.rolling(window, min_periods=window // 2).std(ddof=1)
    z = ((lp - mu) / sd.replace(0, np.nan)).shift(1)

    gate = None
    if vol_q is not None:
        bvol = lp.diff().std(axis=1).rolling(window * 4, min_periods=window).mean()
        thr = bvol.rolling(window * 40, min_periods=window * 8).quantile(vol_q).shift(1)
        gate = (bvol.shift(1) <= thr).fillna(False).to_numpy()

    Zv = z.to_numpy()
    n, m = Zv.shape
    pos = np.zeros((n, m))
    cur = np.zeros(m)
    for i in range(window, n):
        if i % rebalance == 0:
            row = Zv[i]
            ok = np.isfinite(row)
            cur = np.zeros(m)
            if ok.sum() >= 2 * n_leg and (gate is None or gate[i]):
                idx = np.where(ok)[0]
                order = idx[np.argsort(row[idx])]
                cur[order[:n_leg]] = +1.0 / n_leg      # z thấp nhất → mua
                cur[order[-n_leg:]] = -1.0 / n_leg
        pos[i] = cur
    return pd.DataFrame(pos, index=lp.index, columns=lp.columns)


def sh(s, lo=None, hi=None):
    if lo is not None:
        s = s[s.index >= lo]
    if hi is not None:
        s = s[s.index < hi]
    sd = float(s.std(ddof=1))
    return float(s.mean()) / sd * np.sqrt(252) if sd > 0 and len(s) > 60 else np.nan


def main():
    from src.python.strategies.h1 import cross_mean_reversion as CMR
    live_h1 = CMR.daily_pnl(CMR.backtest())

    rows, series = [], {}
    for tf in ("M30", "H1", "H4"):
        panel = LAB.build_panel(tf, start="2020-01-01")
        bd = BARS_DAY[tf]
        print(f"── {tf}: {len(panel.logp):,} nến", flush=True)
        for wd in (3, 5, 10, 20):
            for nl in (3, 5, 7):
                for rd in (1, 2, 5, 10):
                    if rd > wd:
                        continue
                    w = max(int(round(wd * bd)), 10)
                    rb = max(int(round(rd * bd)), 1)
                    p = sig_xs_zscore(panel, window=w, n_leg=nl, rebalance=rb)
                    r = LAB.simulate_positions(panel, p)
                    d = r.pnl_daily
                    key = f"{tf}|w{wd}|n{nl}|r{rd}"
                    series[key] = d
                    rows.append({
                        "tf": tf, "win_d": wd, "n_leg": nl, "reb_d": rd,
                        "ALL": round(sh(d), 3), "FORM": round(sh(d, hi=DEV), 3),
                        "OOS": round(sh(d, lo=DEV), 3),
                        "gross": round(r.gross_bps_bar, 4),
                        "phi": round(r.trade_cost_bps_bar + r.carry_cost_bps_bar, 4),
                        "phi%": round((r.trade_cost_bps_bar + r.carry_cost_bps_bar)
                                      / max(r.gross_bps_bar, 1e-9) * 100, 1),
                        "turn/nam": round(r.turnover_per_year, 1)})
        print(f"   xong ({time.time() - t0:.0f}s)", flush=True)

    T = pd.DataFrame(rows)
    T.to_csv(OUT / "xs_z_grid.csv", index=False)

    print()
    print("=" * 150)
    print("KIỂM ĐỊNH TẦN SUẤT — nếu edge thật, giãn tái cân bằng phải TĂNG Sharpe")
    print("=" * 150)
    piv = T.pivot_table(index=["tf", "win_d", "n_leg"], columns="reb_d",
                        values="ALL")
    print(piv.round(3).to_string())

    print()
    print("=" * 150)
    print("30 Ô TỐT NHẤT")
    print("=" * 150)
    print(T.sort_values("ALL", ascending=False).head(30).to_string(index=False))

    print()
    print("=" * 150)
    print("CỔNG 1-2: FORM>0 & OOS>0 & ALL>0,45")
    print("=" * 150)
    k = T[(T["FORM"] > 0) & (T["OOS"] > 0) & (T["ALL"] > 0.45)].sort_values(
        "ALL", ascending=False)
    print(k.to_string(index=False) if len(k) else "  KHÔNG CÓ")

    if len(k):
        print()
        print("=" * 150)
        print("CỔNG 4: tương quan với chân H1 ĐANG LIVE (CrossMeanReversion)")
        print("=" * 150)
        for _, r in k.head(12).iterrows():
            key = f"{r.tf}|w{int(r.win_d)}|n{int(r.n_leg)}|r{int(r.reb_d)}"
            both = pd.DataFrame({"new": series[key], "live": live_h1}).fillna(0.0)
            c = float(both.corr().iloc[0, 1])
            flag = "ĐỘC LẬP" if abs(c) < 0.7 else "TRÙNG — loại"
            print(f"    {key:22s} ALL {r.ALL:+.3f}  corr {c:+.3f}  {flag}")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
