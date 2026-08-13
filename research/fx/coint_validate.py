"""Vòng 26 — kiểm định nghiêm pairs cointegration H1: THÊM SWAP + không lọc trong mẫu + control."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from itertools import combinations
from src.python.research import fx_cointegration as CO
from src.python.shared import carry_costs as CC, asset_profile as AP
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); FORM=pd.Timestamp("2024-01-01")
logp, costs = CO.load_logprices(timeframe="H1", start="2020-01-01")
RATES = CC.rate_series(pd.DatetimeIndex(sorted(set(logp.index.normalize()))))
MARKUP=1.0

def swap_bps(a,b,beta,side,t_in,t_out):
    """Phí swap cho MỘT lệnh pairs: 2 chân, mỗi chân theo chênh lệch lãi suất + biên broker.
    side=+1: long x, short y (theo tỷ trọng beta)."""
    pa,pb = AP.get(a), AP.get(b)
    d0,d1 = pd.Timestamp(t_in).normalize(), pd.Timestamp(t_out).normalize()
    nights = max((d1-d0).days,0)
    if nights==0: return 0.0
    try:
        r = RATES.loc[d0]
    except KeyError:
        r = RATES.iloc[RATES.index.searchsorted(d0)]
    def leg(p, w):
        diff = float(r.get(p.base,0.0)-r.get(p.quote,0.0))
        return (-w*diff + abs(w)*MARKUP)/365.0*100.0*CC.SWAP_CALENDAR_MULTIPLIER
    return (leg(pa, side*1.0) + leg(pb, -side*abs(beta))) * nights

def sim_with_swap(a,b):
    tr = CO.simulate_pair(np.exp(logp[a]), np.exp(logp[b]), costs[a], costs[b])
    out=[]
    for t in tr:
        # beta xap xi tu ty le chi phi -> dung 1.0 lam bao thu (tinh du swap chan y)
        sw = swap_bps(a,b,1.0,t.side,t.entry_time,t.exit_time)
        out.append({"time":pd.Timestamp(t.entry_time),"exit":pd.Timestamp(t.exit_time),
                    "gross":t.gross_bps,"cost":t.cost_bps,"swap":sw,
                    "net":t.gross_bps-t.cost_bps-sw,"bars":t.bars_held,"pair":f"{a}/{b}"})
    return out

print("="*118); print("A. TẤT CẢ 21 CẶP, ĐỦ CHI PHÍ (giao dịch 2 chân + SWAP 2 chân)"); print("="*118)
alltr=[]
for a,b in combinations(logp.columns,2):
    alltr += sim_with_swap(a,b)
A=pd.DataFrame(alltr)
print(f"  tổng {len(A)} lệnh · giữ trung bình {A['bars'].mean():.0f} nến H1 = {A['bars'].mean()/24:.1f} ngày")
print(f"  gross {A['gross'].mean():+.2f} · phí giao dịch {A['cost'].mean():.2f} · SWAP {A['swap'].mean():.2f} · net {A['net'].mean():+.2f} bps")
for lbl,m in (("FORM",A["time"]<FORM),("OOS",A["time"]>=FORM),("ALL",A["time"].notna())):
    x=A[m]["net"]
    print(f"  {lbl:>4}: n={len(x):>4} net={float(x.mean()):+7.2f} bps  "
          f"t={float(x.mean())/(float(x.std(ddof=1))/np.sqrt(len(x))):+5.2f}  hit={float((x>0).mean()):.3f}")

print()
print("="*118); print("B. ĐƯỜNG EQUITY DANH MỤC — tỷ trọng đều 21 cặp, 1 đơn vị rủi ro/lệnh"); print("="*118)
A=A.sort_values("time")
daily = A.set_index("time")["net"].resample("1D").sum().fillna(0.0)
daily = daily[daily.index>=pd.Timestamp("2020-04-01")]
def stats(s,l):
    cum=s.cumsum(); dd=cum.cummax()-cum
    yrs=(s.index.max()-s.index.min()).days/365.25
    sd=float(s.std(ddof=1))
    return {"win":l,"n_ngay":len(s),"tong_bps":round(float(cum.iloc[-1]),0),
            "bps_ngay":round(float(s.mean()),2),
            "sharpe":round(float(s.mean())/sd*np.sqrt(252),3) if sd>0 else np.nan,
            "maxDD_bps":round(float(dd.max()),0)}
print(pd.DataFrame([stats(daily[daily.index<FORM],"FORM"),stats(daily[daily.index>=FORM],"OOS"),
                    stats(daily,"ALL")]).to_string(index=False))
print()
by=daily.groupby(daily.index.year)
print("  theo năm (tổng bps):"); print(by.sum().round(0).to_string())

print()
print("="*118); print("C. CONTROL — vào lệnh NGẪU NHIÊN, cùng số lệnh, cùng thời gian giữ"); print("="*118)
rng=np.random.default_rng(11); ctl=[]
pairs=list(combinations(logp.columns,2))
for k in range(150):
    best=[]
    for a,b in pairs:
        sub=A[A["pair"]==f"{a}/{b}"]
        if len(sub)<5: continue
        lx,ly=logp[a].to_numpy(),logp[b].to_numpy(); n=len(lx)
        for _,row in sub.iterrows():
            h=int(row["bars"]); i=int(rng.integers(600,n-h-1)); s=int(rng.choice([-1,1]))
            g=s*((lx[i+h]-lx[i])-(ly[i+h]-ly[i]))*1e4
            best.append(g-row["cost"]-row["swap"])
    if best: ctl.append(float(np.mean(best)))
ctl=np.array(ctl); real=float(A["net"].mean())
print(f"  control net_bps: p05={np.percentile(ctl,5):+.2f} p50={np.percentile(ctl,50):+.2f} p95={np.percentile(ctl,95):+.2f}")
print(f"  THẬT           : {real:+.2f}  ->  phân vị {float((ctl<real).mean()):.1%}  p={1-float((ctl<real).mean()):.4f}")

print()
print("="*118); print("D. STRESS: chi phí ×N (spread + swap)"); print("="*118)
for k in (1,2,3,5):
    x=A["gross"]-k*(A["cost"]+A["swap"])
    print(f"  ×{k}: net={float(x.mean()):+7.2f} bps  t={float(x.mean())/(float(x.std(ddof=1))/np.sqrt(len(x))):+5.2f}")
print(f"\nelapsed {time.time()-t0:.0f}s")
