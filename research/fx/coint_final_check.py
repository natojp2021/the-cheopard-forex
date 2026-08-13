"""Vòng 29 — kiểm định ứng viên H1 cuối: 3 cặp rẻ, max_hl=120, ts=3.0, giữ ~4 ngày."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from itertools import combinations
from src.python.research import fx_cointegration as CO
from src.python.shared import carry_costs as CC, asset_profile as AP
from src.python.research.validation import stress_testing as ST
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); FORM=pd.Timestamp("2024-01-01")
CHEAP=["EURUSD","USDJPY","GBPUSD"]; CFG=CO.Config(max_hl_bars=120,hl_multiplier=3.0)
logp, costs = CO.load_logprices(timeframe="H1", start="2020-01-01")
RATES = CC.rate_series(pd.DatetimeIndex(sorted(set(logp.index.normalize()))))

def swap_bps(a,b,side,t_in,t_out,markup=1.0):
    pa,pb=AP.get(a),AP.get(b)
    d0,d1=pd.Timestamp(t_in).normalize(),pd.Timestamp(t_out).normalize()
    nights=max((d1-d0).days,0)
    if nights==0: return 0.0
    try: r=RATES.loc[d0]
    except KeyError: r=RATES.iloc[RATES.index.searchsorted(d0)]
    def leg(p,w):
        diff=float(r.get(p.base,0.0)-r.get(p.quote,0.0))
        return (-w*diff+abs(w)*markup)/365.0*100.0*CC.SWAP_CALENDAR_MULTIPLIER
    return (leg(pa,side*1.0)+leg(pb,-side*1.0))*nights

tr=[]
for a,b in combinations(CHEAP,2):
    for t in CO.simulate_pair(np.exp(logp[a]),np.exp(logp[b]),costs[a],costs[b],cfg=CFG):
        sw=swap_bps(a,b,t.side,t.entry_time,t.exit_time)
        tr.append({"time":pd.Timestamp(t.entry_time),"exit":pd.Timestamp(t.exit_time),
                   "net":t.gross_bps-t.cost_bps-sw,"gross":t.gross_bps,"cost":t.cost_bps,
                   "swap":sw,"bars":t.bars_held,"pair":f"{a}/{b}","side":t.side})
A=pd.DataFrame(tr).sort_values("time")
net=A.set_index("time")["net"]

print("="*118); print("A. CONTROL — vào NGẪU NHIÊN, cùng số lệnh, cùng thời gian giữ, cùng chi phí"); print("="*118)
rng=np.random.default_rng(23); ctl=[]
for k in range(300):
    best=[]
    for a,b in combinations(CHEAP,2):
        sub=A[A["pair"]==f"{a}/{b}"]
        lx,ly=logp[a].to_numpy(),logp[b].to_numpy(); n=len(lx)
        for _,row in sub.iterrows():
            h=int(row["bars"]); i=int(rng.integers(600,n-h-1)); s=int(rng.choice([-1,1]))
            g=s*((lx[i+h]-lx[i])-(ly[i+h]-ly[i]))*1e4
            best.append(g-row["cost"]-row["swap"])
    ctl.append(float(np.mean(best)))
ctl=np.array(ctl); real=float(net.mean())
pct=float((ctl<real).mean())
print(f"  control: p05={np.percentile(ctl,5):+.2f} p50={np.percentile(ctl,50):+.2f} p95={np.percentile(ctl,95):+.2f}")
print(f"  THẬT   : {real:+.2f} bps -> phân vị {pct:.1%}  p={1-pct:.4f}")

print(); print("="*118); print("B. ĐƯỜNG EQUITY THEO NGÀY"); print("="*118)
daily=net.resample("1D").sum().fillna(0.0); daily=daily[daily.index>=pd.Timestamp("2020-04-01")]
def st(s,l):
    cum=s.cumsum(); dd=cum.cummax()-cum; sd=float(s.std(ddof=1))
    return {"win":l,"tong_bps":round(float(cum.iloc[-1]),0),"bps_ngay":round(float(s.mean()),2),
            "sharpe":round(float(s.mean())/sd*np.sqrt(252),3) if sd>0 else np.nan,
            "maxDD_bps":round(float(dd.max()),0)}
print(pd.DataFrame([st(daily[daily.index<FORM],"FORM"),st(daily[daily.index>=FORM],"OOS"),st(daily,"ALL")]).to_string(index=False))

print(); print("="*118); print("C. STRESS + OUTLIER"); print("="*118)
for k in (1,1.5,2,3):
    x=A["gross"]-k*(A["cost"]+A["swap"])
    print(f"  chi phí ×{k}: net={float(x.mean()):+6.2f} t={float(x.mean())/(float(x.std(ddof=1))/np.sqrt(len(x))):+5.2f}")
o=ST.outlier_removal_test(list(net.to_numpy()),n_remove=10)
print(f"  bỏ 10 lệnh tốt nhất: {o['pct_of_profit_from_outliers']*100:.1f}% lợi nhuận · đổi dấu {o['sign_flipped_to_loss']}")

print(); print("="*118); print("D. THEO NĂM + THEO CẶP"); print("="*118)
print(pd.DataFrame({"tong_bps":net.groupby(net.index.year).sum().round(0),
                    "n":net.groupby(net.index.year).size()}).to_string())
print(); print(A.groupby("pair")["net"].agg(["count","mean","sum"]).round(2).to_string())
print(f"\nelapsed {time.time()-t0:.0f}s")
