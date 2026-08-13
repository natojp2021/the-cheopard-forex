"""Vòng 20 — chiều MOMENTUM trên lưới H1 (gợi ý từ GEMINI, project-refer/tradingsystem).
GEMINI: tách EUR khỏi USD bằng 2 cặp rồi đi THEO đà. Phân rã 8 đồng của ta làm việc
đó triệt để hơn — nhưng ta mới chỉ backtest chiều reversal."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_intraday_xs as IX
from src.python.shared import carry_costs as CC, asset_profile as AP
from src.python.strategies.d1 import currency_reversal as CR
pd.set_option("display.width",250,"display.max_columns",30)
DEV=pd.Timestamp("2024-01-01"); t0=time.time()
SPECS={s:(AP.get(s).base,AP.get(s).quote) for s in IX.PAIRS}
F, costs = IX.currency_bars("H1", start="2020-01-01")

def bt(lb,hold,sign,n_leg=3,markup=1.0):
    cum=F.cumsum(); sig=sign*(cum-cum.shift(lb))
    vol=F.rolling(max(lb*8,200),min_periods=100).std()
    cols=list(F.columns); Sv,Vv=sig.to_numpy(),vol.to_numpy()
    W=np.zeros((len(F),len(cols))); held=np.zeros(len(cols))
    for i in range(len(F)):
        if i>lb and i%hold==0:
            s,v=Sv[i-1],Vv[i-1]   # NHÂN QUẢ: tín hiệu của bar TRƯỚC
            if np.isnan(s).sum()<=len(cols)-2*n_leg and np.isnan(v).sum()<=len(cols)-2*n_leg:
                o=np.argsort(-np.nan_to_num(s,nan=-1e18)); w=np.zeros(len(cols))
                for grp,sg in ((o[:n_leg],1.0),(o[-n_leg:],-1.0)):
                    iv=np.nan_to_num(1.0/np.where(np.isfinite(v[grp])&(v[grp]>0),v[grp],np.nan))
                    if iv.sum()>0: w[grp]=sg*iv/iv.sum()
                held=w
        W[i]=held
    Wdf=pd.DataFrame(W,index=F.index,columns=cols); P=CR.pair_weights(Wdf)
    gross=(Wdf*F).sum(axis=1)
    turn=P.diff().abs().fillna(P.abs()); tcost=(turn*costs.reindex(P.columns)).sum(axis=1)/2.0
    Pd=P.resample("1D").last().dropna(how="all")
    cd=CC.pair_carry_bps(Pd,SPECS,broker_markup_pct=markup)["total_carry_bps"]
    ch=cd.reindex(P.index.normalize()).to_numpy()/24.0
    return (gross-tcost-pd.Series(np.nan_to_num(ch),index=P.index)).dropna()

def sh(s,bpy=6000):
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(bpy) if sd>0 else np.nan
def ann(s):
    return float(s.cumsum().iloc[-1])/100/((s.index.max()-s.index.min()).days/365.25)

print("="*112); print("A. MOMENTUM (sign=+1) — chi phí ĐẦY ĐỦ gồm swap"); print("="*112)
rows=[]
for lb in (4,8,12,24):
    for hold in (24,48,96,120):
        n=bt(lb,hold,+1)
        rows.append({"lb":lb,"hold":hold,"ALL":round(sh(n),3),
                     "DEV":round(sh(n[n.index<DEV]),3),"OOS":round(sh(n[n.index>=DEV]),3),
                     "ann%":round(ann(n),2)})
G=pd.DataFrame(rows)
print("ALL sharpe:"); print(G.pivot(index="lb",columns="hold",values="ALL").round(3).to_string())
print("\nDEV:"); print(G.pivot(index="lb",columns="hold",values="DEV").round(3).to_string())
print("\nOOS:"); print(G.pivot(index="lb",columns="hold",values="OOS").round(3).to_string())
print("\nann%:"); print(G.pivot(index="lb",columns="hold",values="ann%").round(2).to_string())

good=G[(G["DEV"]>0)&(G["OOS"]>0)&(G["ALL"]>0.2)]
print()
print("="*112); print("B. Ô có CẢ DEV lẫn OOS dương (điều kiện tối thiểu)"); print("="*112)
print(good.sort_values("ALL",ascending=False).to_string(index=False) if len(good) else "  KHÔNG có ô nào")

if len(good):
    b=good.sort_values("ALL",ascending=False).iloc[0]
    lb,hold=int(b["lb"]),int(b["hold"])
    n=bt(lb,hold,+1)
    print(); print("="*112); print(f"C. CONTROL cho lb={lb} hold={hold}"); print("="*112)
    def ctl(seed):
        rng=np.random.default_rng(seed); cols=list(F.columns)
        vol=F.rolling(max(lb*8,200),min_periods=100).std().to_numpy()
        W=np.zeros((len(F),len(cols))); held=np.zeros(len(cols))
        for i in range(len(F)):
            if i>lb and i%hold==0:
                s=rng.standard_normal(len(cols)); v=vol[i-1]
                if np.isnan(v).sum()<=len(cols)-6:
                    o=np.argsort(-s); w=np.zeros(len(cols))
                    for grp,sg in ((o[:3],1.0),(o[-3:],-1.0)):
                        iv=np.nan_to_num(1.0/np.where(np.isfinite(v[grp])&(v[grp]>0),v[grp],np.nan))
                        if iv.sum()>0: w[grp]=sg*iv/iv.sum()
                    held=w
            W[i]=held
        Wdf=pd.DataFrame(W,index=F.index,columns=cols); P=CR.pair_weights(Wdf)
        g=(Wdf*F).sum(axis=1); turn=P.diff().abs().fillna(P.abs())
        tc=(turn*costs.reindex(P.columns)).sum(axis=1)/2.0
        Pd=P.resample("1D").last().dropna(how="all")
        cd=CC.pair_carry_bps(Pd,SPECS,broker_markup_pct=1.0)["total_carry_bps"]
        ch=cd.reindex(P.index.normalize()).to_numpy()/24.0
        return (g-tc-pd.Series(np.nan_to_num(ch),index=P.index)).dropna()
    cs=np.array([sh(ctl(s)) for s in range(60)]); cs=cs[np.isfinite(cs)]
    r=sh(n)
    print(f"  control p05={np.percentile(cs,5):+.3f} p50={np.percentile(cs,50):+.3f} p95={np.percentile(cs,95):+.3f}")
    print(f"  THẬT {r:+.3f} -> phân vị {float((cs<r).mean()):.1%}  p={1-float((cs<r).mean()):.4f}")
    cum=n.cumsum(); dd=(cum.cummax()-cum)
    print(f"  maxDD {float(dd.max())/100:.2f}%  ·  ann {ann(n):+.2f}%  ·  vol {float(n.std(ddof=1))*np.sqrt(6000)/100:.2f}%")
    by=n.groupby(n.index.year)
    print("\n  theo năm (ann%):")
    print((by.mean()*6000/100).round(2).to_string())
print(f"\nelapsed {time.time()-t0:.0f}s")
