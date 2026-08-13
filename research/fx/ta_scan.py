"""Vong 43 — QUET 10 HO TA THUAN x 4 KHUNG tren EURUSD + GBPUSD."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_ta_lab as TA
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); out=ROOT/"reports"/"fx_research"

PAR = {
 "M30": dict(ma_cross=dict(fast=20,slow=100), donchian=dict(lookback=96,exit_lb=24),
             adx_trend=dict(fast=20,slow=100)),
 "H1":  dict(ma_cross=dict(fast=20,slow=100), donchian=dict(lookback=55,exit_lb=20),
             adx_trend=dict(fast=20,slow=100)),
 "H4":  dict(ma_cross=dict(fast=10,slow=50),  donchian=dict(lookback=30,exit_lb=10),
             adx_trend=dict(fast=10,slow=50)),
 "D1":  dict(ma_cross=dict(fast=20,slow=100), donchian=dict(lookback=55,exit_lb=20),
             adx_trend=dict(fast=20,slow=100)),
}
rows=[]; store={}
for tf in ("M30","H1","H4","D1"):
    print(f"-- {tf} ...", flush=True)
    for sym in TA.TIER1:
        bars=TA.load(sym,tf,start="2020-01-01")
        for fam,fn in TA.FAMILIES.items():
            kw=PAR[tf].get(fam,{})
            try:
                pos=fn(bars,**kw)
                r=TA.simulate(bars,pos,name=fam)
                rows.append(TA.row(r)); store[(fam,sym,tf)]=r
            except Exception as e:
                print(f"   {fam}/{sym}: {type(e).__name__}: {e}")
T=pd.DataFrame(rows); T.to_csv(out/"ta_scan_tier1.csv",index=False)

print(); print("="*150); print("TOAN BO — 10 ho x 2 cap x 4 khung, du chi phi"); print("="*150)
print(T.sort_values(["nhóm","họ","tf","cặp"]).to_string(index=False))

print(); print("="*150); print("UNG VIEN — FORM>0 va OOS>0 va ALL>0,3"); print("="*150)
g=T[(T["FORM"].fillna(-9)>0)&(T["OOS"].fillna(-9)>0)&(T["ALL"].fillna(-9)>0.3)]
print(g.sort_values("ALL",ascending=False).to_string(index=False) if len(g) else "  KHONG CO")

print(); print("="*150); print("TOM TAT THEO NHOM (Sharpe ALL trung binh)"); print("="*150)
print(T.groupby("nhóm")["ALL"].agg(["count","mean","max"]).round(3).to_string())
print(); print("theo ho:")
print(T.groupby("họ")["ALL"].agg(["mean","max"]).round(3).sort_values("mean",ascending=False).to_string())
print(f"\nelapsed {time.time()-t0:.0f}s")
