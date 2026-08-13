"""Vong 45 — kiem dinh ung vien bb_vol_THAP GBPUSD H4: control + tuong quan + PHO QUAT."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_ta_lab as TA, fx_ta_conditional as TC
from src.python.research import fx_cross_pairs as CX
from src.python.shared import asset_profile as AP
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); DEV=pd.Timestamp("2024-01-01")

def sh(s):
    s=s[s.index>=pd.Timestamp("2020-04-01")]
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(252) if sd>0 else np.nan

b=TA.load("GBPUSD","H4",start="2020-01-01")
pos=TC.gate_vol_regime(b, TA.sig_bb_mr(b), low=True)
real=TA.simulate(b,pos,name="bb_volTHAP")
print("="*112); print("1. CONTROL — vao NGAU NHIEN, cung tan suat va thoi gian giu"); print("="*112)
n_tr=real.n_trades; hold=int(round(real.bars_held_avg))
print(f"  that: {n_tr} lenh · giu {hold} nen · Sharpe {sh(real.pnl_daily):+.3f}")
rng=np.random.default_rng(45); ctl=[]
N=len(b.df)
for k in range(400):
    p=np.zeros(N)
    for _ in range(n_tr):
        i=int(rng.integers(20,N-hold-1)); s=int(rng.choice([-1,1]))
        p[i:i+hold]=s
    r=TA.simulate(b,pd.Series(p,index=b.df.index),name="ctl")
    v=sh(r.pnl_daily)
    if np.isfinite(v): ctl.append(v)
ctl=np.array(ctl); rv=sh(real.pnl_daily); pct=float((ctl<rv).mean())
print(f"  control: p05={np.percentile(ctl,5):+.3f} p50={np.percentile(ctl,50):+.3f} p95={np.percentile(ctl,95):+.3f}")
print(f"  -> phan vi {pct:.1%}   p={1-pct:.4f}   {'QUA' if pct>0.95 else 'TRUOT'}")

print(); print("="*112); print("2. TUONG QUAN voi 4 chan dang chay"); print("="*112)
from src.python.strategies import portfolio as PF
from src.python.strategies.d1 import cross_momentum as CM
res=PF.backtest(start="2020-01-01")
legs=dict(res.legs); legs["cross_mom"]=CM.daily_pnl(); legs["bb_volTHAP"]=real.pnl_daily
idx=None
for s in legs.values(): idx=s.index if idx is None else idx.union(s.index)
L={k:v.reindex(idx).fillna(0.0) for k,v in legs.items()}
C=pd.DataFrame(L).corr().round(3)
print(C.to_string())
mx=max(abs(C.loc["bb_volTHAP",k]) for k in C.columns if k!="bb_volTHAP")
print(f"\n  |tuong quan| lon nhat: {mx:.3f}  {'-> DOC LAP' if mx<=0.7 else '-> TRUNG'}")

print(); print("="*112); print("3. PHO QUAT — cung cong thuc tren 7 cap USD + 20 cross, H4"); print("="*112)
print("   Neu chi GBPUSD song thi day la NHIEU. Edge that phai xuat hien o nhieu cong cu.")
rows=[]
for sym in AP.FX_ALL:
    try:
        bb=TA.load(sym,"H4",start="2020-01-01")
        p=TC.gate_vol_regime(bb, TA.sig_bb_mr(bb), low=True)
        r=TA.simulate(bb,p,name="x"); d=r.pnl_daily
        rows.append({"cong cu":sym,"loai":"USD","ALL":round(sh(d),3),
                     "FORM":round(sh(d[d.index<DEV]),3),"OOS":round(sh(d[d.index>=DEV]),3),
                     "n":r.n_trades,"net":round(r.net_bps_trade,2)})
    except Exception as e: pass
# cross: dung chinh bo may TA nhung tren chuoi cross tong hop
P,SPECS=CX.build_crosses("H4",start="2020-01-01")
import src.python.shared.carry_costs as CC
for name in P.columns:
    try:
        sp=SPECS[name]
        df=pd.DataFrame({"close":P[name]})
        df["high"]=P[name].rolling(2).max(); df["low"]=P[name].rolling(2).min()
        df["open"]=P[name].shift(1); df["spread_usd"]=sp.spread_pips*sp.pip
        c=df["close"]
        ma20,sd20=c.rolling(20).mean(),c.rolling(20).std(ddof=1)
        df["bb_up"],df["bb_dn"],df["bb_mid"]=ma20+2*sd20,ma20-2*sd20,ma20
        pc=c.shift(1)
        tr=pd.concat([df["high"]-df["low"],(df["high"]-pc).abs(),(df["low"]-pc).abs()],axis=1).max(axis=1)
        df["atr14"]=tr.ewm(alpha=1/14,adjust=False).mean()
        px=float(c.median())
        bars=TA.Bars(symbol=name,timeframe="H4",df=df.dropna(subset=["close"]),
                     cost_1rt_bps=sp.cost_1rt_bps_at(px),
                     swap_bps_per_bar=CC.SWAP_CALENDAR_MULTIPLIER*1.0/365.0*100.0*4.0/24.0)
        p=TC.gate_vol_regime(bars, TA.sig_bb_mr(bars), low=True)
        r=TA.simulate(bars,p,name="x"); d=r.pnl_daily
        rows.append({"cong cu":name,"loai":"CROSS","ALL":round(sh(d),3),
                     "FORM":round(sh(d[d.index<DEV]),3),"OOS":round(sh(d[d.index>=DEV]),3),
                     "n":r.n_trades,"net":round(r.net_bps_trade,2)})
    except Exception as e: pass
U=pd.DataFrame(rows).sort_values("ALL",ascending=False)
print(U.to_string(index=False))
print()
pos_n=int((U["ALL"]>0).sum()); both=int(((U["FORM"]>0)&(U["OOS"]>0)).sum())
print(f"  {pos_n}/{len(U)} cong cu co ALL duong ({pos_n/len(U):.0%})")
print(f"  {both}/{len(U)} cong cu co CA FORM lan OOS duong ({both/len(U):.0%})")
print(f"  trung vi ALL = {U['ALL'].median():+.3f}")
print(f"\nelapsed {time.time()-t0:.0f}s")
