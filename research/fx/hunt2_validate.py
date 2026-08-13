"""Vòng 68 — KIỂM ĐỊNH tám ứng viên M30/H1 từ vòng 67.

TÁM ỨNG VIÊN — sáu M30, hai H1
==============================
M30 hiện chỉ có ba chân và CẢ BA đều là Z-Band, nên khung này chưa có đa dạng hoá
cách nhìn nào. Sáu ứng viên M30 dưới đây thuộc ba họ khác hẳn.

    M30 streak      AUDCAD N4  k0,5 ts192  FORM 1,062 · OOS 0,803 · 7/7 · 902 lệnh
    M30 rsi_div     GBPNZD N192 k3,0 ts192 FORM 1,674 · OOS 0,765 · 7/7 · 316 lệnh
    M30 vol_regime  GBPCHF N96 k1,6 ts48   FORM 0,860 · OOS 1,122 · 6/7 ·  79 lệnh
    M30 accel       CADCHF N96 k2,5 ts192  FORM 0,628 · OOS 1,051 · 7/7 · 134 lệnh
    M30 vol_regime  AUDCHF N192 k1,3 ts48  FORM 0,471 · OOS 1,254 · 7/7 · 252 lệnh
    M30 rsi_div     NZDCAD N96 k3,0 ts48   FORM 0,582 · OOS 1,147 · 6/7 · 725 lệnh
    H1  accel       GBPCAD N12 k2,0 ts24   FORM 0,718 · OOS 0,887 · 6/7 · 627 lệnh
    H1  accel       GBPNZD N48 k2,5 ts24   FORM 1,367 · OOS 0,581 · 6/7 · 112 lệnh

HỌ `accel` LÀ THỨ MỚI NHẤT Ở ĐÂY
=================================
Nó đo ĐẠO HÀM BẬC HAI của giá — đà đang mạnh lên hay chậm lại. Mọi họ trước đo bậc
không (giá cách trung bình bao xa) hoặc bậc một (đà). Đây là lần đầu dự án khai thác
bậc hai, và nó chạy được ở CẢ HAI khung, trên hai công cụ khác nhau.

BẢY KIỂM ĐỊNH — không nới cho họ mới
=====================================
    1. control THỜI ĐIỂM · 2. control CHIỀU · 3. bootstrap khối
    4. ổn định năm · 5. loại ngoại lai · 6. stress chi phí · 7. vùng tham số
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

from research.fx.h1_families import run, sharpe
from research.fx.h1_fam_validate import control_side, control_timing
from research.fx.m30_h1_hunt2 import NEW_FAM, OLD_FAM, _bs
from research.fx.mr_validate import block_bootstrap
from research.fx.trade_lab import load_crosses, load_majors

pd.set_option("display.width", 245, "display.max_columns", 30)
FORM_END = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"
FAMS = {**NEW_FAM, **OLD_FAM}

# (khung, họ, công cụ, N, k, time-stop)
CANDIDATES: Tuple[Tuple[str, str, str, int, float, int], ...] = (
    ("M30", "streak", "AUDCAD", 4, 0.5, 192),
    ("M30", "rsi_div", "GBPNZD", 192, 3.0, 192),
    ("M30", "vol_regime", "GBPCHF", 96, 1.6, 48),
    ("M30", "accel", "CADCHF", 96, 2.5, 192),
    ("M30", "vol_regime", "AUDCHF", 192, 1.3, 48),
    ("M30", "rsi_div", "NZDCAD", 96, 3.0, 48),
    ("H1", "accel", "GBPCAD", 12, 2.0, 24),
    ("H1", "accel", "GBPNZD", 48, 2.5, 24),
)


def main() -> None:
    t0 = time.time()
    univ = {tf: {i.name: i for i in (load_crosses(tf) + load_majors(tf))}
            for tf in ("M30", "H1")}
    series: Dict[str, pd.Series] = {}
    verdicts: List[Dict] = []

    for tf, fam, nm, N, k, ts in CANDIDATES:
        fn, Ns, Ks = FAMS[fam]
        ins = univ[tf][nm]
        b, s = _bs(fn, ins.df, N, k)
        T, d = run(ins.df, ins.cost_1rt_bps, ins.swap_bps_per_bar, b, s, ts)
        label = f"{tf}·{fam}·{nm}·N{N}·k{k}·ts{ts}"
        series[label] = d
        v = T["net_bps"]
        tm = float(v.mean()) / float(v.std(ddof=1)) * np.sqrt(len(v))
        cum = d.cumsum()
        yrs = max((d.index.max() - d.index.min()).days / 365.25, 1e-9)

        print()
        print("█" * 118)
        print(f"█ {label}")
        print("█" * 118)
        print(f"  Sharpe ALL {sharpe(d):+.3f} · FORM {sharpe(d, hi=FORM_END):+.3f} "
              f"· OOS {sharpe(d, lo=FORM_END):+.3f}")
        print(f"  {len(T)} lệnh · thắng {float((v > 0).mean()) * 100:.1f}% · "
              f"net {float(v.mean()):+.2f} bps/lệnh (t = {tm:+.2f}) · "
              f"giữ {float(T['bars'].mean()):.0f} nến · "
              f"{float(cum.iloc[-1]) / 100 / yrs:+.2f}%/năm · MaxDD "
              f"{float((cum.cummax() - cum).max()) / 100:.2f}%")

        ct = np.array([control_timing(T, ins, x) for x in range(300)])
        ct = ct[np.isfinite(ct)]
        p_t = float((ct < tm).mean())
        d1 = p_t >= 0.95
        cs = np.array([control_side(T, x) for x in range(300)])
        cs = cs[np.isfinite(cs)]
        p_s = float((cs < tm).mean())
        d2 = p_s >= 0.95
        print(f"  1-2. CONTROL  thời điểm p = {1 - p_t:.4f} "
              f"{'ĐẠT' if d1 else 'KHÔNG'} · chiều p = {1 - p_s:.4f} "
              f"{'ĐẠT' if d2 else 'KHÔNG'}")

        bs = block_bootstrap(d)
        d3 = bs["p_neg"] < 0.10
        yr = d.groupby(d.index.year).sum() / 100.0
        d4 = int((yr > 0).sum()) >= len(yr) - 1
        mo = d.resample("MS").sum()
        rest = float((mo.sum() - mo.nlargest(5).sum()) / 100.0)
        d5 = rest > 0
        print(f"  3-5. bootstrap P(<0) {bs['p_neg']:.1%} {'ĐẠT' if d3 else 'KHÔNG'} · "
              f"năm {int((yr > 0).sum())}/{len(yr)} {'ĐẠT' if d4 else 'KHÔNG'} · "
              f"bỏ top5 {rest:+.2f}% {'ĐẠT' if d5 else 'KHÔNG'}")

        base = ins.cost_1rt_bps
        line = []
        for m in (2, 3, 5):
            _, dd = run(ins.df, base * m, ins.swap_bps_per_bar, b, s, ts)
            line.append(f"×{m} {sharpe(dd):+.3f}")
        print(f"  6. STRESS CHI PHÍ  " + " · ".join(line))

        neigh = []
        for dn in Ns:
            for dk in Ks:
                bb, ss = _bs(fn, ins.df, dn, dk)
                _, d2n = run(ins.df, base, ins.swap_bps_per_bar, bb, ss, ts)
                x = sharpe(d2n)
                if np.isfinite(x):
                    neigh.append(x)
        n_pos = sum(1 for x in neigh if x > 0)
        d7 = n_pos >= len(neigh) * 0.6
        print(f"  7. VÙNG THAM SỐ  {n_pos}/{len(neigh)} ô dương  "
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
    print("█" * 118)
    print("█ ĐỘC LẬP — tương quan chéo giữa các ứng viên và với 21 chân đang chạy")
    print("█" * 118)
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
        print(f"  {a:38s} " + " · ".join(f"{b} {v:.3f}" for v, b in top))

    V = pd.DataFrame(verdicts)
    print()
    print("=" * 118)
    print("TỔNG KẾT")
    print("=" * 118)
    print(V.to_string(index=False))
    pd.DataFrame(allser).to_csv(OUT / "hunt2_validate_pnl.csv")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
