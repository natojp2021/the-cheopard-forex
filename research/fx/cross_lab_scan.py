"""Vòng 39 — QUÉT 5 HỌ × 4 KHUNG trên 20 cross. Mục tiêu: M30≥3 H1≥4 H4≥2 D1≥2."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_cross_lab as LAB
pd.set_option("display.width",260,"display.max_columns",30)
t0=time.time()
out=ROOT/"reports"/"fx_research"; out.mkdir(parents=True,exist_ok=True)

TFS=["M30","H1","H4","D1"]
HL_RANGE={"M30":(8,240),"H1":(4,120),"H4":(3,40),"D1":(2,20)}
LEVERAGE={"M30":(110,40),"H1":(55,20),"H4":(20,10),"D1":(20,10)}

results=[]; rows=[]
for tf in TFS:
    print(f"── {tf} ...", flush=True)
    panel=LAB.build_panel(tf, start="2020-01-01")
    lo,hi=HL_RANGE[tf]; dl,de=LEVERAGE[tf]
    jobs = {
      "zscore_band": dict(min_hl=lo,max_hl=hi),
      "donchian":    dict(lookback=dl, exit_lookback=de),
      "cross_carry": dict(n_leg=5),
      "xs_reversal": dict(sign=-1, n_leg=5),
      "xs_momentum": dict(sign=+1, n_leg=5),
      "tsmom":       dict(),
    }
    for fam,kw in jobs.items():
        fn = LAB.SIGNAL_FAMILIES.get("xs_reversal" if fam=="xs_momentum" else fam)
        try:
            pos = fn(panel, **kw)
            r = LAB.simulate_positions(panel, pos, name=fam)
            results.append(r); rows.append(LAB.split_report(r))
        except Exception as e:
            print(f"   {fam}: LOI {type(e).__name__}: {e}")
T=pd.DataFrame(rows)
T.to_csv(out/"cross_lab_scan.csv", index=False)
print()
print("="*140); print("TOÀN BỘ KẾT QUẢ (đủ chi phí: spread + commission + swap, markup 1,0%/năm)"); print("="*140)
print(T.to_string(index=False))

print()
print("="*140); print("ỨNG VIÊN — cả FORM lẫn OOS dương, và ALL > 0,3"); print("="*140)
g=T[(T["FORM"].fillna(-9)>0)&(T["OOS"].fillna(-9)>0)&(T["ALL"].fillna(-9)>0.3)]
print(g.sort_values(["tf","ALL"],ascending=[True,False]).to_string(index=False) if len(g) else "  không có")
print()
if len(g):
    print("  đếm theo khung:")
    for tf in TFS:
        n=len(g[g["tf"]==tf]); need={"M30":3,"H1":4,"H4":2,"D1":2}[tf]
        print(f"    {tf}: {n}  (mục tiêu ≥{need})  {'✓' if n>=need else '✗ thiếu '+str(need-n)}")
print(f"\nelapsed {time.time()-t0:.0f}s")
