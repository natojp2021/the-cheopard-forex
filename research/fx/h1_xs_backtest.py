"""Vòng 17 — BACKTEST THẬT chiến lược cắt ngang lưới H1, giữ 2-5 ngày.
Đây là ứng viên H1 cuối cùng: quyết định trên nến H1, giữ 48-120 nến H1.
Chi phí đầy đủ + DEV/OOS + control."""
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
print(f"H1: {len(F):,} nến  ·  chi phí rổ 1 khứ hồi = {IX.BASKET_COST_BPS} bps\n")

def backtest_xs(lb, hold, sign=-1, n_leg=3, markup=1.0):
    """Danh mục cắt ngang trên lưới H1. Chi phí: giao dịch mỗi lần tái cân bằng +
    swap mỗi ĐÊM (không phải mỗi nến — swap tính theo ngày lịch)."""
    cum=F.cumsum(); sig=sign*(cum-cum.shift(lb))
    vol=F.rolling(max(lb*4,200),min_periods=100).std()
    cols=list(F.columns); Fv,Sv,Vv=F.to_numpy(),sig.to_numpy(),vol.to_numpy()
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
    Wdf=pd.DataFrame(W,index=F.index,columns=cols)
    P=CR.pair_weights(Wdf)
    gross=(Wdf*F).sum(axis=1)
    turn=P.diff().abs().fillna(P.abs())
    tcost=(turn*costs.reindex(P.columns)).sum(axis=1)/2.0
    # swap: quy về NGÀY rồi phân bổ lại lên nến H1
    Pd = P.resample("1D").last().dropna(how="all")
    carry_d = CC.pair_carry_bps(Pd, SPECS, broker_markup_pct=markup)["total_carry_bps"]
    carry_h = carry_d.reindex(P.index.normalize()).to_numpy()/24.0
    net = (gross - tcost - pd.Series(np.nan_to_num(carry_h),index=P.index)).dropna()
    return net

def sh(s, bars_per_year=6000):
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(bars_per_year) if sd>0 else np.nan
def stats(s,lbl,bpy=6000):
    cum=s.cumsum(); dd=(cum.cummax()-cum)
    yrs=(s.index.max()-s.index.min()).days/365.25
    return {"win":lbl,"n":len(s),"ann%":round(float(cum.iloc[-1])/100/yrs,2),
            "vol%":round(float(s.std(ddof=1))*np.sqrt(bpy)/100,2),
            "sharpe":round(sh(s,bpy),3),"maxDD%":round(float(dd.max())/100,2)}

print("="*112); print("A. QUÉT lb × hold (chi phí ĐẦY ĐỦ gồm swap)"); print("="*112)
rows=[]
for lb in (24,48,96,120):
    for hold in (24,48,96,120):
        net = backtest_xs(lb,hold)
        d,o = net[net.index<DEV], net[net.index>=DEV]
        rows.append({"lb":lb,"hold":hold,"ALL_sharpe":round(sh(net),3),
                     "DEV":round(sh(d),3),"OOS":round(sh(o),3),
                     "ann%":round(float(net.cumsum().iloc[-1])/100/((net.index.max()-net.index.min()).days/365.25),2)})
G=pd.DataFrame(rows)
print(G.pivot(index="lb",columns="hold",values="ALL_sharpe").round(3).to_string())
print("\nOOS:"); print(G.pivot(index="lb",columns="hold",values="OOS").round(3).to_string())
print("\nann%:"); print(G.pivot(index="lb",columns="hold",values="ann%").round(2).to_string())

print()
print("="*112); print("B. Ô TỐT NHẤT — chi tiết"); print("="*112)
best=G.sort_values("ALL_sharpe",ascending=False).iloc[0]
lb,hold=int(best["lb"]),int(best["hold"])
net=backtest_xs(lb,hold)
print(f"  lb={lb} hold={hold}")
print(pd.DataFrame([stats(net[net.index<DEV],"DEV"),stats(net[net.index>=DEV],"OOS"),stats(net,"ALL")]).to_string(index=False))

print()
print("="*112); print("C. CONTROL — tín hiệu xếp hạng NGẪU NHIÊN, cùng tần suất"); print("="*112)
def ctl(seed,lb,hold,n_leg=3):
    rng=np.random.default_rng(seed)
    cols=list(F.columns); Fv=F.to_numpy()
    vol=F.rolling(max(lb*4,200),min_periods=100).std().to_numpy()
    W=np.zeros((len(F),len(cols))); held=np.zeros(len(cols))
    for i in range(len(F)):
        if i>lb and i%hold==0:
            s=rng.standard_normal(len(cols)); v=vol[i-1]
            if np.isnan(v).sum()<=len(cols)-2*n_leg:
                o=np.argsort(-s); w=np.zeros(len(cols))
                for grp,sg in ((o[:n_leg],1.0),(o[-n_leg:],-1.0)):
                    iv=np.nan_to_num(1.0/np.where(np.isfinite(v[grp])&(v[grp]>0),v[grp],np.nan))
                    if iv.sum()>0: w[grp]=sg*iv/iv.sum()
                held=w
        W[i]=held
    Wdf=pd.DataFrame(W,index=F.index,columns=cols); P=CR.pair_weights(Wdf)
    gross=(Wdf*F).sum(axis=1)
    turn=P.diff().abs().fillna(P.abs()); tcost=(turn*costs.reindex(P.columns)).sum(axis=1)/2.0
    Pd=P.resample("1D").last().dropna(how="all")
    cd=CC.pair_carry_bps(Pd,SPECS,broker_markup_pct=1.0)["total_carry_bps"]
    ch=cd.reindex(P.index.normalize()).to_numpy()/24.0
    return (gross-tcost-pd.Series(np.nan_to_num(ch),index=P.index)).dropna()
cs=[sh(ctl(s,lb,hold)) for s in range(60)]
cs=np.array([x for x in cs if np.isfinite(x)])
real=sh(net)
print(f"  control: p05={np.percentile(cs,5):+.3f} p50={np.percentile(cs,50):+.3f} p95={np.percentile(cs,95):+.3f}")
print(f"  THẬT   : {real:+.3f}  ->  phân vị {float((cs<real).mean()):.1%}  p={1-float((cs<real).mean()):.4f}")
print(f"\nelapsed {time.time()-t0:.0f}s")
