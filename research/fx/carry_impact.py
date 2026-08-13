"""Vòng 6 — PHÉP THỬ SỐNG CÒN: chiến lược có sống sót phí swap không?
Theo trình tự của Carver: gross -> +spread/comm -> +swap. Cột thứ ba mới là sự thật."""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.d1 import currency_reversal as CR
from src.python.shared import carry_costs as CC
pd.set_option("display.width",250,"display.max_columns",30)
DEV=pd.Timestamp("2024-01-01")

r = CR.backtest(start="2020-01-01")
W = r.weights_ccy

print("="*118); print("A. CHIẾN LƯỢC CÓ SHORT CARRY HỆ THỐNG KHÔNG?"); print("="*118)
expo = CC.carry_exposure(W)
active = expo[W.abs().sum(axis=1) > 1e-9]
print(f"  phơi nhiễm carry trung bình: {float(active.mean()):+.3f} %/năm  (DƯƠNG = nhận tiền)")
print(f"  trung vị: {float(active.median()):+.3f}   p10: {float(active.quantile(.1)):+.3f}   p90: {float(active.quantile(.9)):+.3f}")
print(f"  tỷ lệ ngày short carry: {float((active<0).mean()):.1%}")
t = float(active.mean())/(float(active.std(ddof=1))/np.sqrt(len(active)))
print(f"  t-stat khác 0: {t:+.2f}")
print()
print("  phơi nhiễm carry theo năm (%/năm):")
print(active.groupby(active.index.year).mean().round(3).to_string())

print(); print("="*118); print("B. TRÌNH TỰ CARVER — chi phí cộng dồn từng lớp"); print("="*118)
bd = CC.carry_breakdown(W)
layers = {
    "1. GROSS (không chi phí)":              r.gross,
    "2. + spread & commission":              r.gross - r.cost,
    "3. + swap (chênh lệch lãi suất)":       r.gross - r.cost - bd["rate_diff_bps"],
    "4. + biên broker 1,0%/năm  = ĐỦ":       r.gross - r.cost - bd["total_carry_bps"],
}
rows=[]
for name, s in layers.items():
    s = s.dropna()
    for lbl, x in (("DEV", s[s.index<DEV]), ("OOS", s[s.index>=DEV]), ("ALL", s)):
        d = CR.stats(x, lbl); d["lop"] = name; rows.append(d)
T = pd.DataFrame(rows)
print(T[["lop","label","ann_ret_pct","ann_vol_pct","sharpe","max_dd_pct","calmar"]].to_string(index=False))

print(); print("  chi phí trung bình mỗi lớp (%/năm):")
print(f"    spread+commission : {float(r.cost.mean())*252/100:+.3f}")
print(f"    chênh lệch lãi suất: {float(bd['rate_diff_bps'].mean())*252/100:+.3f}")
print(f"    biên broker        : {float(bd['broker_markup_bps'].mean())*252/100:+.3f}")
print(f"    TỔNG               : {(float(r.cost.mean())+float(bd['total_carry_bps'].mean()))*252/100:+.3f}")

print(); print("="*118); print("C. STRESS BIÊN BROKER — mức nào thì chiến lược chết?"); print("="*118)
for mk in (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0):
    b = CC.carry_breakdown(W, broker_markup_pct=mk)
    s = (r.gross - r.cost - b["total_carry_bps"]).dropna()
    o = s[s.index>=DEV]
    print(f"  biên {mk:>4.1f}%/năm: ALL ann={float(s.mean())*252/100:+6.2f}% sharpe={float(s.mean())/float(s.std(ddof=1))*np.sqrt(252):+.3f}"
          f"   |  OOS ann={float(o.mean())*252/100:+6.2f}% sharpe={float(o.mean())/float(o.std(ddof=1))*np.sqrt(252):+.3f}")
