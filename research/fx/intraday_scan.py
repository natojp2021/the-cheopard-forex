"""Vòng 13 — SĂN CHIẾN LƯỢC H1. Bước 1: sức mạnh tín hiệu, chưa nói chi phí."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_intraday_xs as IX
pd.set_option("display.width",250,"display.max_columns",30)
out = ROOT/"reports"/"fx_research"; out.mkdir(parents=True,exist_ok=True)

t0=time.time()
F, costs = IX.currency_bars("H1", start="2020-01-01")
print(f"H1: {len(F):,} nến × 8 đồng · {F.index.min()} → {F.index.max()}  ({time.time()-t0:.0f}s)")
print(f"chi phí khứ hồi rổ = {IX.BASKET_COST_BPS} bps\n")

print("="*118)
print("A. LƯỚI lookback × hold — REVERSAL (sign=-1). gross_bps = lợi nhuận/lượt CHƯA chi phí")
print("="*118)
LB=[4,8,12,24,48,96]; HD=[4,8,12,24,48,96]
S = IX.scan(F, LB, HD, timeframe="H1", signs=(-1,))
S.to_csv(out/"intraday_h1_reversal.csv", index=False)
piv_g = S.pivot(index="lookback",columns="hold",values="gross_bps")
piv_t = S.pivot(index="lookback",columns="hold",values="t_stat")
piv_c = S.pivot(index="lookback",columns="hold",values="cost_ratio")
print("gross bps/lượt:"); print(piv_g.round(3).to_string())
print("\nt-stat:"); print(piv_t.round(2).to_string())
print("\ncost_ratio (>1 mới đáng giao dịch):"); print(piv_c.round(2).to_string())

print()
print("="*118); print("B. MOMENTUM (sign=+1) — đối chứng"); print("="*118)
S2 = IX.scan(F, LB, HD, timeframe="H1", signs=(+1,))
print("t-stat:"); print(S2.pivot(index="lookback",columns="hold",values="t_stat").round(2).to_string())

print()
print("="*118); print("C. Ô TỐT NHẤT (cost_ratio > 1, xếp theo t)"); print("="*118)
both = pd.concat([S,S2])
good = both[(both["cost_ratio"]>1.0) & (both["n_obs"]>=100)].copy()
print(good.sort_values("t_stat",key=abs,ascending=False).head(15).to_string(index=False) if len(good) else "  KHÔNG có ô nào vượt chi phí")

print()
print("="*118); print("D. THEO PHIÊN — vị thế mở ở phiên nào thì tốt?"); print("="*118)
for lb,h in [(12,12),(24,24),(24,48),(48,48)]:
    r = IX.measure_by_session(F, lb, h, sign=-1)
    if not r.empty:
        print(f"\n  lookback={lb}h hold={h}h (reversal):")
        print(r.to_string())
print(f"\nelapsed {time.time()-t0:.0f}s")
