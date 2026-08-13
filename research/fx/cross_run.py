"""Vòng 30 — mean reversion trên 20 CẶP CHÉO tổng hợp, H1. Một chân thay vì hai."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_cross_pairs as CX
from src.python.shared import carry_costs as CC
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); FORM=pd.Timestamp("2024-01-01")

P, SPECS = CX.build_crosses("H1", start="2020-01-01")
print(f"dựng {len(P.columns)} cross tổng hợp · {len(P):,} nến H1")
RATES = CC.rate_series(pd.DatetimeIndex(sorted(set(P.index.normalize()))))

def swap_bps(spec, side, t_in, t_out, markup=1.0):
    """MỘT chân: chênh lệch lãi suất base-quote + biên broker."""
    d0,d1=pd.Timestamp(t_in).normalize(),pd.Timestamp(t_out).normalize()
    nights=max((d1-d0).days,0)
    if nights==0: return 0.0
    try: r=RATES.loc[d0]
    except KeyError: r=RATES.iloc[RATES.index.searchsorted(d0)]
    diff=float(r.get(spec.base,0.0)-r.get(spec.quote,0.0))
    return (-side*diff+markup)/365.0*100.0*CC.SWAP_CALENDAR_MULTIPLIER*nights

def run(cfg=CX.Config(), names=None):
    rows=[]
    for name in (names or P.columns):
        spec=SPECS[name]
        for t in CX.simulate(name, P[name], spec, cfg):
            sw=swap_bps(spec,t.side,t.entry_time,t.exit_time,cfg.markup_pct)
            rows.append({"time":pd.Timestamp(t.entry_time),"cross":name,"side":t.side,
                "gross":t.gross_bps,"cost":t.cost_bps,"swap":sw,
                "net":t.gross_bps-t.cost_bps-sw,"bars":t.bars_held,"reason":t.exit_reason})
    return pd.DataFrame(rows)

print()
print("="*126); print("A. TỪNG CROSS — mặc định (HL≤120, cửa sổ 3×HL, vào 2σ có quay lại)"); print("="*126)
A=run()
g=A.groupby("cross")
S=pd.DataFrame({"n":g.size(),"ngay_giu":(g["bars"].mean()/24).round(2),
    "gross":g["gross"].mean().round(2),"phi":g["cost"].mean().round(2),
    "swap":g["swap"].mean().round(2),"net":g["net"].mean().round(2),
    "t":(g["net"].mean()/(g["net"].std(ddof=1)/np.sqrt(g.size()))).round(2),
    "hit":g["net"].apply(lambda x:(x>0).mean()).round(3)})
S["FORM"]=A[A["time"]<FORM].groupby("cross")["net"].mean().round(2)
S["OOS"]=A[A["time"]>=FORM].groupby("cross")["net"].mean().round(2)
print(S.sort_values("net",ascending=False).to_string())

print()
print("="*126); print("B. DANH MỤC TẤT CẢ CROSS (không lọc — số trung thực)"); print("="*126)
for lbl,m in (("FORM",A["time"]<FORM),("OOS",A["time"]>=FORM),("ALL",A["time"].notna())):
    x=A[m]["net"]
    print(f"  {lbl:>4}: n={len(x):>4}  net={float(x.mean()):+6.2f} bps  "
          f"t={float(x.mean())/(float(x.std(ddof=1))/np.sqrt(len(x))):+5.2f}  hit={float((x>0).mean()):.3f}")
daily=A.sort_values("time").set_index("time")["net"].resample("1D").sum().fillna(0.0)
daily=daily[daily.index>=pd.Timestamp("2020-04-01")]
def st(s,l):
    cum=s.cumsum(); dd=cum.cummax()-cum; sd=float(s.std(ddof=1))
    return {"win":l,"tong_bps":round(float(cum.iloc[-1]),0),"bps_ngay":round(float(s.mean()),2),
            "sharpe":round(float(s.mean())/sd*np.sqrt(252),3) if sd>0 else np.nan,
            "maxDD_bps":round(float(dd.max()),0)}
print()
print(pd.DataFrame([st(daily[daily.index<FORM],"FORM"),st(daily[daily.index>=FORM],"OOS"),st(daily,"ALL")]).to_string(index=False))
print()
print("  theo năm (tổng bps):"); print(daily.groupby(daily.index.year).sum().round(0).to_string())

print()
print("="*126); print("C. STRESS CHI PHÍ"); print("="*126)
for k in (1,1.5,2,3):
    x=A["gross"]-k*(A["cost"]+A["swap"])
    print(f"  ×{k}: net={float(x.mean()):+6.2f} bps  t={float(x.mean())/(float(x.std(ddof=1))/np.sqrt(len(x))):+5.2f}")
print(f"\nelapsed {time.time()-t0:.0f}s")
