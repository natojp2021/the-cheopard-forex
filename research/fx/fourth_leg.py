"""Vòng 42 — xs_momentum trên cross có phải CHÂN THỨ TƯ thật của danh mục?"""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_cross_lab as LAB
from src.python.strategies import portfolio as PF
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); DEV=pd.Timestamp("2024-01-01")

# chan moi: cross momentum cat ngang, D1, lookback 3 thang
p=LAB.build_panel("D1",start="2020-01-01")
xm=LAB.simulate_positions(p, LAB.sig_xs_reversal(p,sign=+1,n_leg=5,lookback=63,rebalance_bars=21), name="xs_mom")
new=xm.pnl_daily

res=PF.backtest(start="2020-01-01")
legs=dict(res.legs); legs["cross_mom"]=new
idx=None
for s in legs.values(): idx=s.index if idx is None else idx.union(s.index)
legs={k:v.reindex(idx).fillna(0.0) for k,v in legs.items()}

print("="*112); print("A. TƯƠNG QUAN với ba chân hiện có — cổng quyết định"); print("="*112)
C=pd.DataFrame(legs).corr().round(3)
print(C.to_string())
mx=max(abs(C.loc["cross_mom",k]) for k in C.columns if k!="cross_mom")
print(f"\n  |tương quan| lớn nhất của chân mới với chân cũ: {mx:.3f}  "
      f"{'-> ĐỘC LẬP, tính là chân thật' if mx<=0.7 else '-> TRÙNG, không tính'}")

def sh(s):
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(252) if sd>0 else np.nan
def st(s,l):
    cum=s.cumsum(); dd=cum.cummax()-cum
    return {"cfg":l,"ALL":round(sh(s),3),"FORM":round(sh(s[s.index<DEV]),3),
            "OOS":round(sh(s[s.index>=DEV]),3),"maxDD_sd":round(float(dd.max()),1)}

print(); print("="*112); print("B. GHÉP BỐN CHÂN — chuẩn hoá biến động FORM, chia đều"); print("="*112)
N={}
for k,v in legs.items():
    f=v[v.index<DEV]; sd=float(f.std(ddof=1))
    N[k]=v/sd if sd>0 else v*0.0
three=sum(N[k] for k in ("reversal","carry","cross_h1"))/3
four=sum(N.values())/4
rows=[st(N[k],k) for k in N] + [st(three,"BA CHÂN"), st(four,"BỐN CHÂN")]
print(pd.DataFrame(rows).to_string(index=False))
print()
by=four.groupby(four.index.year)
print("  bốn chân theo năm (Sharpe):")
print(by.apply(lambda s: round(sh(s),2)).to_string())
print(f"  năm dương: {int((by.sum()>0).sum())}/{len(by)}")

print(); print("="*112); print("C. ĐUÔI — ngày tệ nhất (quyết định đòn bẩy FTMO)"); print("="*112)
for lbl,s in (("BA CHÂN",three),("BỐN CHÂN",four)):
    print(f"  {lbl}: sigma {float(s.std(ddof=1)):.3f} · ngày tệ nhất {float(s.min()):.2f} = "
          f"{abs(float(s.min()))/float(s.std(ddof=1)):.1f}σ")
print(f"\nelapsed {time.time()-t0:.0f}s")
