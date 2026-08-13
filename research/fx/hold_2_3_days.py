"""Vòng 23 — RÀNG BUỘC NGƯỜI DÙNG: giữ lệnh 2-3 ngày.
Test trên chiến lược cắt ngang đã chứng minh có edge, nhưng rút ngắn thời gian giữ.
Hai biến thể: (a) LUÔN có vị thế, (b) CHỌN LỌC — chỉ vào khi tín hiệu mạnh, còn lại đứng ngoài."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.d1 import currency_reversal as CR
from src.python.shared import carry_costs as CC, asset_profile as AP
pd.set_option("display.width",250,"display.max_columns",30)
DEV=pd.Timestamp("2024-01-01"); t0=time.time()
SPECS={s:(AP.get(s).base,AP.get(s).quote) for s in CR.PAIRS}
F, costs = CR.currency_returns(start="2020-01-01")

def run(lb, rb, sign=-1, n_leg=3, markup=1.0, sel_q=None, regime=True):
    """sel_q: nếu đặt, CHỈ vào lệnh khi độ phân tán tín hiệu >= phân vị đó (trượt),
    còn lại đứng ngoài -> cắt cả phí giao dịch lẫn swap."""
    cum=F.cumsum(); sig=sign*(cum-cum.shift(lb))
    vol=F.rolling(63,min_periods=31).std()
    crisis = CR.regime_is_crisis(F, CR.Config()) if regime else pd.Series(False,index=F.index)
    disp = sig.std(axis=1)/vol.mean(axis=1)
    thr = disp.shift(1).rolling(252,min_periods=126).quantile(sel_q) if sel_q else None
    cols=list(F.columns); W=pd.DataFrame(0.0,index=F.index,columns=cols)
    held=pd.Series(0.0,index=cols); need=2*n_leg
    for i,t in enumerate(F.index):
        if i%rb==0 and i>0:
            s,v=sig.iloc[i-1],vol.iloc[i-1]
            weak = bool(thr is not None and (pd.isna(thr.iloc[i]) or disp.iloc[i-1]<thr.iloc[i]))
            if weak:
                held=pd.Series(0.0,index=cols)
            elif s.notna().sum()>=need and v.notna().sum()>=need:
                o=s.dropna().sort_values(ascending=False); w=pd.Series(0.0,index=cols)
                for grp,sg in ((list(o.index[:n_leg]),1.0),(list(o.index[-n_leg:]),-1.0)):
                    iv=(1.0/v[grp].replace(0,np.nan)).fillna(0.0)
                    if iv.sum()>0: w[grp]=sg*iv/iv.sum()
                held=w
        W.loc[t]=0.0 if crisis.iloc[i] else held
    P=CR.pair_weights(W); gross=(W*F).sum(axis=1)
    turn=P.diff().abs().fillna(P.abs()); tc=(turn*costs.reindex(P.columns)).sum(axis=1)/2.0
    cy=CC.pair_carry_bps(P,SPECS,broker_markup_pct=markup)
    net=(gross-tc-cy["total_carry_bps"]).dropna()
    search_grid=1.0-float((P.abs().sum(axis=1)<1e-9).mean())
    return net, {"tc":float(tc.mean())*252/100,"carry":float(cy["total_carry_bps"].mean())*252/100,"tim":search_grid}

def st(s,l):
    d=CR.stats(s,l); return d
print("="*118); print("A. LUÔN CÓ VỊ THẾ — rút ngắn thời gian giữ (rb = số ngày giữ)"); print("="*118)
rows=[]
for lb in (5,10,15,21,42):
    for rb in (2,3,5,10,21):
        net,info = run(lb,rb)
        d=st(net,"ALL"); d.update({"lb":lb,"rb":rb,"DEV":st(net[net.index<DEV],"")["sharpe"],
            "OOS":st(net[net.index>=DEV],"")["sharpe"],"tc%":round(info["tc"],2),"carry%":round(info["carry"],2)})
        rows.append(d)
G=pd.DataFrame(rows)
print("ALL sharpe:"); print(G.pivot(index="lb",columns="rb",values="sharpe").round(3).to_string())
print("\nOOS:"); print(G.pivot(index="lb",columns="rb",values="OOS").round(3).to_string())
print("\nchi phí giao dịch %/năm:"); print(G.pivot(index="lb",columns="rb",values="tc%").round(2).to_string())
print("\nann%:"); print(G.pivot(index="lb",columns="rb",values="ann_ret_pct").round(2).to_string())

print()
print("="*118); print("B. CHỌN LỌC — chỉ vào khi tín hiệu mạnh, giữ 2-3 ngày, còn lại ĐỨNG NGOÀI")
print("="*118)
rows=[]
for lb in (5,10,21):
    for rb in (2,3,5):
        for q in (0.5,0.7,0.8):
            net,info = run(lb,rb,sel_q=q)
            if len(net)<200: continue
            d=st(net,"ALL"); d.update({"lb":lb,"rb":rb,"q":q,"DEV":st(net[net.index<DEV],"")["sharpe"],
                "OOS":st(net[net.index>=DEV],"")["sharpe"],"tim":round(info["tim"],3),
                "tc%":round(info["tc"],2),"carry%":round(info["carry"],2)})
            rows.append(d)
S=pd.DataFrame(rows)
good=S[(S["DEV"]>0)&(S["OOS"]>0)]
cols=["lb","rb","q","tim","tc%","carry%","ann_ret_pct","sharpe","DEV","OOS","max_dd_pct","calmar"]
print("Ô có CẢ DEV lẫn OOS dương:")
print(good[cols].sort_values("sharpe",ascending=False).head(12).to_string(index=False) if len(good) else "  không có")
print(f"\nelapsed {time.time()-t0:.0f}s")
