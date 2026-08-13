"""Vong 46 — PCA STAT-ARB (Avellaneda & Lee) tren 3 vu tru x 3 khung."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_statarb_pca as SA, fx_cross_pairs as CX
from src.python.shared import asset_profile as AP, fx_data as D, carry_costs as CC
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); DEV=pd.Timestamp("2024-01-01"); out=ROOT/"reports"/"fx_research"
BH={"H1":1.0,"H4":4.0,"D1":24.0}; PPY={"H1":252*24,"H4":252*6,"D1":252}

def universe_usd(tf):
    r,c,s={},{},{}
    for sym in AP.FX_ALL:
        b=D.build_bars(D.load_m1(sym),tf); b=b[b.index>="2020-01-01"]
        r[sym]=np.log(b["close"]).diff()*1e4
        p=AP.get(sym); px=float(b["close"].median()); sp=float(b["spread_usd"].median())
        c[sym]=(sp+p.commission_price_units(px))/px*1e4
        s[sym]=CC.SWAP_CALENDAR_MULTIPLIER*1.0/365.0*100.0*BH[tf]/24.0
    return pd.DataFrame(r).dropna(), pd.Series(c), pd.Series(s)

def universe_cross(tf):
    P,SP=CX.build_crosses(tf,start="2020-01-01")
    r=(np.log(P).diff()*1e4).dropna()
    c={n:SP[n].cost_1rt_bps_at(float(P[n].median())) for n in P.columns}
    s={n:CC.SWAP_CALENDAR_MULTIPLIER*1.0/365.0*100.0*BH[tf]/24.0 for n in P.columns}
    return r, pd.Series(c), pd.Series(s)

def universe_all(tf):
    a,ca,sa=universe_usd(tf); b,cb,sb=universe_cross(tf)
    idx=a.index.intersection(b.index)
    return pd.concat([a.loc[idx],b.loc[idx]],axis=1), pd.concat([ca,cb]), pd.concat([sa,sb])

rows=[]; store={}
for tf in ("H1","H4","D1"):
    for uname,fn in (("7 cap USD",universe_usd),("20 cross",universe_cross),("27 ca hai",universe_all)):
        try:
            R,C,S=fn(tf)
            for k in (2,3,5):
                cfg=SA.Config(n_factors=k)
                pos=SA.build_positions(R,cfg)
                res=SA.simulate(R,pos,C,S)
                d=res.pnl.resample("1D").sum().fillna(0.0)
                a=SA.stats(d,"ALL"); f=SA.stats(d[d.index<DEV],"F"); o=SA.stats(d[d.index>=DEV],"O")
                rows.append({"vu tru":uname,"tf":tf,"k":k,"ALL":a["sharpe"],
                    "FORM":f["sharpe"],"OOS":o["sharpe"],"ann%":a.get("ann_pct"),
                    "maxDD%":a.get("max_dd_pct"),"n_lenh":res.n_trades,
                    "gross":round(res.gross_bps,3),"phi":round(res.cost_bps,3),
                    "swap":round(res.swap_bps,3),"%tt":round(res.time_in_market,2),
                    "vithe_tb":round(res.avg_positions,1)})
                store[(uname,tf,k)]=d
            print(f"  {uname:<12} {tf:<3} xong", flush=True)
        except Exception as e:
            print(f"  {uname} {tf}: {type(e).__name__}: {e}")
T=pd.DataFrame(rows); T.to_csv(out/"statarb_pca_scan.csv",index=False)
print(); print("="*140); print("PCA STAT-ARB (Avellaneda & Lee) — nguong s-score nguyen ban, du chi phi"); print("="*140)
print(T.to_string(index=False))
print(); print("="*140); print("CONG: FORM>0 va OOS>0 va ALL>0,5"); print("="*140)
g=T[(T["FORM"].fillna(-9)>0)&(T["OOS"].fillna(-9)>0)&(T["ALL"].fillna(-9)>0.5)]
print(g.sort_values("ALL",ascending=False).to_string(index=False) if len(g) else "  KHONG CO")
print(f"\nelapsed {time.time()-t0:.0f}s")
