"""Vòng 66 — KIỂM ĐỊNH năm ứng viên H1 thuộc BA HỌ MỚI (không phải z-band).

NĂM ỨNG VIÊN — chọn đại diện cho ba họ, ưu tiên CÂN BẰNG FORM/OOS
=================================================================
    rsi_div     NZDCAD N96 k6,0 ts24   FORM 0,795 · OOS 0,905 · 7/7 năm · 350 lệnh
    rsi_div     NZDCAD N96 k3,0 ts24   FORM 0,690 · OOS 1,143 · 6/7 năm · 467 lệnh
    streak      GBPAUD N6  k0,5 ts24   FORM 0,850 · OOS 0,741 · 6/7 năm · 257 lệnh
    streak      GBPCAD N5  k0,5 ts24   FORM 1,182 · OOS 0,521 · 6/7 năm · 472 lệnh
    vol_regime  GBPAUD N96 k1,3 ts24   FORM 0,920 · OOS 0,628 · 6/7 năm · 282 lệnh

VÌ SAO VÒNG NÀY QUAN TRỌNG HƠN SỐ SHARPE CỦA NÓ
================================================
Bảy chân H1 hiện có đều đọc cùng một đại lượng (khoảng cách chuẩn hoá tới trung bình
động). Ba họ ở đây đọc ba thứ khác hẳn — QUAN HỆ giá/RSI, ĐẾM chuỗi nến, TỶ SỐ hai
độ lệch chuẩn — và |tương quan| với mọi chân H1 đo được tối đa **0,206**.

Một chân Sharpe 0,80 độc lập đóng góp cho danh mục nhiều hơn một chân Sharpe 1,00
tương quan 0,7 với chân đã có. Đó là lý do vòng này không tìm số cao nhất.

BẢY KIỂM ĐỊNH — như mọi ứng viên khác, không nới cho họ mới
===========================================================
    1. control THỜI ĐIỂM   giữ số lệnh và thời gian giữ, vào lệnh ngẫu nhiên
    2. control CHIỀU       giữ thời điểm, đảo chiều ngẫu nhiên
    3. bootstrap khối      21 ngày, 2000 lần, P(<0) < 10%
    4. ổn định năm         >= 6/7 năm dương
    5. loại ngoại lai      bỏ 5 tháng tốt nhất vẫn giữ dấu
    6. stress chi phí      ×2 ×3 ×5
    7. vùng tham số        đa số ô lân cận cùng dấu
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import numpy as np
import pandas as pd

from research.fx.h1_families import FAMILIES, run, sharpe
from research.fx.mr_validate import block_bootstrap
from research.fx.trade_lab import load_crosses, load_majors

pd.set_option("display.width", 240, "display.max_columns", 30)
FORM_END = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"

# (họ, công cụ, N, k, time-stop)
CANDIDATES: Tuple[Tuple[str, str, int, float, int], ...] = (
    ("rsi_div", "NZDCAD", 96, 6.0, 24),
    ("rsi_div", "NZDCAD", 96, 3.0, 24),
    ("streak", "GBPAUD", 6, 0.5, 24),
    ("streak", "GBPCAD", 5, 0.5, 24),
    ("vol_regime", "GBPAUD", 96, 1.3, 24),
)


def control_timing(T: pd.DataFrame, ins, seed: int) -> float:
    """Giữ số lệnh và thời gian giữ, vào lệnh tại thời điểm NGẪU NHIÊN."""
    rng = np.random.default_rng(seed)
    c = ins.df["close"].to_numpy()
    n = len(c)
    out = []
    for _, t in T.iterrows():
        bars = int(t["bars"])
        if bars < 1 or bars >= n - 2:
            continue
        i = int(rng.integers(0, n - bars - 1))
        side = 1 if t["gross_bps"] >= 0 else -1     # giữ phân phối chiều
        g = side * (c[i + bars] - c[i]) / c[i] * 1e4
        out.append(g - (t["gross_bps"] - t["net_bps"]))
    if not out:
        return np.nan
    s = pd.Series(out)
    sd = float(s.std(ddof=1))
    return float(s.mean()) / sd * np.sqrt(len(s)) if sd > 0 else np.nan


def control_side(T: pd.DataFrame, seed: int) -> float:
    """Giữ thời điểm và thời gian giữ, ĐẢO chiều ngẫu nhiên."""
    rng = np.random.default_rng(seed)
    flip = rng.choice([-1.0, 1.0], size=len(T))
    cost_bps = (T["gross_bps"] - T["net_bps"]).to_numpy()
    v = T["gross_bps"].to_numpy() * flip - cost_bps
    s = pd.Series(v)
    sd = float(s.std(ddof=1))
    return float(s.mean()) / sd * np.sqrt(len(s)) if sd > 0 else np.nan


def main() -> None:
    t0 = time.time()
    univ = {i.name: i for i in (load_crosses("H1") + load_majors("H1"))}
    series: Dict[str, pd.Series] = {}
    verdicts: List[Dict] = []

    for fam, nm, N, k, ts in CANDIDATES:
        fn = FAMILIES[fam][0]
        ins = univ[nm]
        b, s = fn(ins.df, N, k)
        T, d = run(ins.df, ins.cost_1rt_bps, ins.swap_bps_per_bar, b, s, ts)
        label = f"{fam}·{nm}·N{N}·k{k}·ts{ts}"
        series[label] = d
        v = T["net_bps"]
        tm = float(v.mean()) / float(v.std(ddof=1)) * np.sqrt(len(v))
        cum = d.cumsum()
        yrs = max((d.index.max() - d.index.min()).days / 365.25, 1e-9)

        print()
        print("█" * 112)
        print(f"█ {label}")
        print("█" * 112)
        print(f"  Sharpe ALL {sharpe(d):+.3f} · FORM {sharpe(d, hi=FORM_END):+.3f} "
              f"· OOS {sharpe(d, lo=FORM_END):+.3f}")
        print(f"  {len(T)} lệnh · thắng {float((v > 0).mean()) * 100:.1f}% · "
              f"net {float(v.mean()):+.2f} bps/lệnh (t = {tm:+.2f}) · "
              f"giữ {float(T['bars'].mean()):.0f} nến")
        print(f"  {float(cum.iloc[-1]) / 100 / yrs:+.2f}%/năm · MaxDD "
              f"{float((cum.cummax() - cum).max()) / 100:.2f}%")

        ct = np.array([control_timing(T, ins, x) for x in range(300)])
        ct = ct[np.isfinite(ct)]
        p_t = float((ct < tm).mean())
        d1 = p_t >= 0.95
        print(f"\n  1. CONTROL THỜI ĐIỂM  t {tm:+.2f} vs p50 {np.median(ct):+.2f} "
              f"· p = {1 - p_t:.4f}  {'ĐẠT' if d1 else 'KHÔNG ĐẠT'}")

        cs = np.array([control_side(T, x) for x in range(300)])
        cs = cs[np.isfinite(cs)]
        p_s = float((cs < tm).mean())
        d2 = p_s >= 0.95
        print(f"  2. CONTROL CHIỀU      t {tm:+.2f} vs p50 {np.median(cs):+.2f} "
              f"· p = {1 - p_s:.4f}  {'ĐẠT' if d2 else 'KHÔNG ĐẠT'}")

        bs = block_bootstrap(d)
        d3 = bs["p_neg"] < 0.10
        print(f"  3. BOOTSTRAP KHỐI     {bs['mean']:+.3f} CI95 [{bs['ci_lo']:+.3f} · "
              f"{bs['ci_hi']:+.3f}] P(<0) {bs['p_neg']:.1%}  "
              f"{'ĐẠT' if d3 else 'KHÔNG ĐẠT'}")

        yr = d.groupby(d.index.year).sum() / 100.0
        d4 = int((yr > 0).sum()) >= len(yr) - 1
        print(f"  4. ỔN ĐỊNH NĂM        {int((yr > 0).sum())}/{len(yr)}  "
              f"{'ĐẠT' if d4 else 'KHÔNG ĐẠT'}")

        mo = d.resample("MS").sum()
        rest = float((mo.sum() - mo.nlargest(5).sum()) / 100.0)
        d5 = rest > 0
        print(f"  5. LOẠI NGOẠI LAI     bỏ 5 tháng tốt nhất còn {rest:+.2f}%  "
              f"{'ĐẠT' if d5 else 'KHÔNG ĐẠT'}")

        base = ins.cost_1rt_bps
        line = []
        for m in (2, 3, 5):
            _, dd = run(ins.df, base * m, ins.swap_bps_per_bar, b, s, ts)
            line.append(f"×{m} {sharpe(dd):+.3f}")
        print(f"  6. STRESS CHI PHÍ     " + "  ·  ".join(line))

        neigh = []
        Ns, Ks = FAMILIES[fam][1], FAMILIES[fam][2]
        for dn in Ns:
            for dk in Ks:
                bb, ss = fn(ins.df, dn, dk)
                _, d2n = run(ins.df, base, ins.swap_bps_per_bar, bb, ss, ts)
                x = sharpe(d2n)
                if np.isfinite(x):
                    neigh.append(x)
        n_pos = sum(1 for x in neigh if x > 0)
        d7 = n_pos >= len(neigh) * 0.6
        print(f"  7. VÙNG THAM SỐ       {n_pos}/{len(neigh)} ô lân cận dương  "
              f"{'ĐẠT' if d7 else 'KHÔNG ĐẠT'}")

        verdicts.append({"ứng viên": label, "ALL": round(sharpe(d), 3),
                         "FORM": round(sharpe(d, hi=FORM_END), 3),
                         "OOS": round(sharpe(d, lo=FORM_END), 3),
                         "n": len(T), "t": round(tm, 2),
                         "p_tđ": round(1 - p_t, 4), "p_chiều": round(1 - p_s, 4),
                         "boot": bs["p_neg"], "năm": f"{int((yr > 0).sum())}/{len(yr)}",
                         "bỏ_top5": round(rest, 2), "vùng": f"{n_pos}/{len(neigh)}",
                         "ĐẠT": d1 and d2 and d3 and d4 and d5 and d7})

    print()
    print("█" * 112)
    print("█ ĐỘC LẬP — tương quan với 17 chân đang chạy")
    print("█" * 112)
    from src.python.strategies import portfolio as PF

    def day(s):
        s = s.copy()
        s.index = pd.DatetimeIndex(s.index).as_unit("ns").normalize()
        return s.groupby(s.index).sum()

    res = PF.backtest()
    allser = {**{k: day(v) for k, v in series.items()},
              **{k: day(v) for k, v in res.legs.items()}}
    C = pd.DataFrame(allser).fillna(0.0).corr()
    for a in series:
        top = sorted(((abs(float(C.loc[a, b])), b) for b in allser if b != a),
                     reverse=True)[:2]
        print(f"  {a:34s} " + " · ".join(f"{b} {v:.3f}" for v, b in top))

    V = pd.DataFrame(verdicts)
    print()
    print("=" * 112)
    print("TỔNG KẾT")
    print("=" * 112)
    print(V.to_string(index=False))
    pd.DataFrame(allser).to_csv(OUT / "h1_fam_validate_pnl.csv")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
