"""Vòng 22 — vi cấu trúc từ M1: có phá được trần IC 0,018 không?"""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_microstructure as MS
pd.set_option("display.width",250,"display.max_columns",40)
t0=time.time()
avg, per = MS.information_scan(horizons=(1,2,4,8,24,48))
print("="*110); print("IC TRUNG BÌNH 7 CẶP — đặc trưng VI CẤU TRÚC (dựng từ M1)"); print("="*110)
print(avg.round(4).to_string())
print(f"\n  |IC| lớn nhất = {avg.abs().max().max():.4f}   (trần cũ từ đặc trưng giá H1: 0,0180)")
best=avg.abs().stack().sort_values(ascending=False).head(10)
print("\n  Top 10:")
for (f,h),v in best.items():
    s=avg.loc[f,h]; vals=[per[p].loc[f,h] for p in per if f in per[p].index and h in per[p].columns]
    vals=[x for x in vals if pd.notna(x)]
    pos=sum(1 for x in vals if x>0)
    print(f"    {f:<18} {h:<4} IC={s:+.4f}  t≈{s*np.sqrt(35000):+5.1f}  cùng dấu {max(pos,len(vals)-pos)}/{len(vals)}")
print(f"\nelapsed {time.time()-t0:.0f}s")
