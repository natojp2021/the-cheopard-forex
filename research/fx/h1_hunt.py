"""Vòng 64 — SĂN CHIẾN LƯỢC H1 trên 12 công cụ CHƯA khai thác.

VÌ SAO CÒN CHỖ ĐỂ TÌM
=====================
Chẩn đoán Sepp & Lucic (vòng 58) cho 15 công cụ H1 có biên hoà vốn DƯƠNG. Ba trong
số đó đã thành chiến lược (AUDCAD · NZDCAD · GBPAUD). Mười hai công cụ còn lại chưa
ai chạm tới, và trong đó có công cụ biên LỚN NHẤT toàn bộ khung H1:

    AUDNZD  φ = −0,0484 (t = −8,23)  c* 8,20 bps  chi phí 0,55  biên **+7,65**
    EURCHF  φ = −0,0285 (t = −4,84)  c* 4,73      chi phí 0,46  biên  +4,27
    EURGBP  φ = −0,0247 (t = −4,20)  c* 4,09      chi phí 0,52  biên  +3,56

AUDNZD từng bị thử ở vòng 60 với hai bộ tham số (N48/k2,0 và N96/k1,5) và cả hai
đều trượt. Nhưng đó là hai điểm trong một lưới rộng, và biên +7,65 nói rằng chỗ này
có dư địa gấp 14 lần chi phí — trượt hai điểm không kết luận được gì về cả vùng.

QUÉT BẰNG ĐỘNG CƠ SẢN XUẤT, KHÔNG PHẢI LAB
===========================================
Vòng 61 cho một bài học tốn công: `trade_lab` thiếu nhánh thoát khi z về 0, nên cùng
tham số cho hai kết quả khác hẳn (0,815 ở lab vs 0,557 ở động cơ thật), và tôi suýt
cứu con số đó bằng một tham số chỉ đúng ở 1/7 chân.

Vòng này quét THẲNG bằng `zband_core` — cùng đường code sẽ chạy live. Không có khoảng
cách giữa thứ đo được và thứ sẽ chạy.

LƯỚI: 12 công cụ × 5 cửa sổ × 4 ngưỡng × 3 time-stop = 720 ô
CỔNG ĐẶT TRƯỚC (không đổi sau khi thấy kết quả):
    FORM > 0 · OOS > 0 · ALL > 0,55 · t(net) > 2,0 · số lệnh >= 60
    và VÙNG THAM SỐ: ô lân cận phải cùng dấu
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import numpy as np
import pandas as pd

from research.fx.trade_lab import load_crosses, load_majors
from src.python.strategies import zband_core as ZB

pd.set_option("display.width", 230, "display.max_columns", 30, "display.max_rows", 300)
FORM_END = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"

USED = {"AUDCAD", "NZDCAD", "GBPAUD"}      # đã có chiến lược H1


def sharpe(s: pd.Series, lo=None, hi=None) -> float:
    if lo is not None:
        s = s[s.index >= lo]
    if hi is not None:
        s = s[s.index < hi]
    sd = float(s.std(ddof=1))
    return float(s.mean()) / sd * np.sqrt(252) if sd > 0 and len(s) > 60 else np.nan


def main() -> None:
    t0 = time.time()
    diag = pd.read_csv(OUT / "breakeven_diag.csv")
    sel = diag[(diag["tf"] == "H1") & (diag["biên"] > 0.8)
               & (diag["khai thác"] == "HỒI QUY")].sort_values("biên", ascending=False)
    names = [n for n in sel["công cụ"] if n not in USED]
    print(f"{len(names)} công cụ chưa khai thác: {', '.join(names)}\n")

    univ = {i.name: i for i in (load_crosses("H1") + load_majors("H1"))}
    rows: List[Dict] = []
    for nm in names:
        ins = univ.get(nm)
        if ins is None:
            continue
        margin = float(sel[sel["công cụ"] == nm]["biên"].iloc[0])
        for N in (24, 48, 96, 192, 384):
            for k in (1.5, 2.0, 2.5, 3.0):
                for ts in (1.0, 2.0, 3.0):
                    cfg = ZB.ZBandConfig(f"{nm}H1", nm, "H1", N, k, ts)
                    res = ZB.run(ins.df, ins.cost_1rt_bps, ins.swap_bps_per_bar, cfg)
                    T = res.trades
                    if T.empty or len(T) < 40:
                        continue
                    d, v = res.pnl_daily, T["net_bps"]
                    yr = d.groupby(d.index.year).sum()
                    rows.append({
                        "công cụ": nm, "biên": margin, "N": N, "k": k, "ts": ts,
                        "ALL": round(sharpe(d), 3),
                        "FORM": round(sharpe(d, hi=FORM_END), 3),
                        "OOS": round(sharpe(d, lo=FORM_END), 3),
                        "n": len(T),
                        "thắng%": round(float((v > 0).mean()) * 100, 1),
                        "net": round(float(v.mean()), 2),
                        "t": round(float(v.mean()) / float(v.std(ddof=1))
                                   * np.sqrt(len(v)), 2),
                        "năm+": f"{int((yr > 0).sum())}/{len(yr)}",
                        "nến/lệnh": round(float(T["bars"].mean()), 0)})
        print(f"  {nm} xong ({time.time() - t0:.0f}s)", flush=True)

    R = pd.DataFrame(rows)
    R.to_csv(OUT / "h1_hunt.csv", index=False)

    print()
    print("=" * 140)
    print("CỔNG: FORM>0 & OOS>0 & ALL>0,55 & t>2,0 & n>=60")
    print("=" * 140)
    k = R[(R["FORM"] > 0) & (R["OOS"] > 0) & (R["ALL"] > 0.55)
          & (R["t"] > 2.0) & (R["n"] >= 60)].sort_values("ALL", ascending=False)
    print(f"{len(k)}/{len(R)} ô qua cổng")
    print(k.head(28).to_string(index=False) if len(k) else "  KHÔNG CÓ")

    if len(k):
        print()
        print("── theo CÔNG CỤ (ô qua cổng · Sharpe cao nhất · OOS trung vị)")
        g = k.groupby("công cụ").agg(
            n_ô=("ALL", "size"), ALL_max=("ALL", "max"),
            FORM_tv=("FORM", "median"), OOS_tv=("OOS", "median"),
            biên=("biên", "first")).round(3).sort_values("ALL_max", ascending=False)
        print(g.to_string())

        print()
        print("── VÙNG THAM SỐ của ô tốt nhất mỗi công cụ")
        for nm in g.index[:4]:
            best = k[k["công cụ"] == nm].iloc[0]
            sub = R[(R["công cụ"] == nm) & (R["ts"] == best["ts"])]
            piv = sub.pivot_table(index="N", columns="k", values="ALL")
            n_pos = int((piv > 0).sum().sum())
            n_best = int(piv.notna().sum().sum())
            print(f"\n   {nm} · ts={best['ts']} · {n_pos}/{n_tot} ô dương")
            print("   " + piv.round(2).to_string().replace("\n", "\n   "))
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
