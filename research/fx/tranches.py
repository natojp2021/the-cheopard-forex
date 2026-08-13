"""Vòng 24 — CHIA LÔ SO LE (staggered tranches).
Ý tưởng: thay vì tái cân bằng TOÀN BỘ danh mục mỗi 21 ngày, chạy N lô song song,
mỗi lô vẫn giữ 21 ngày nhưng vào lệch nhau. Kết quả:
  * có lệnh MỖI NGÀY (hoặc mỗi 2-3 ngày) -> giao dịch thường xuyên
  * mỗi vị thế vẫn được giữ đủ 21 ngày -> giữ nguyên edge
  * turnover được LÀM MƯỢT -> chi phí không tăng, rủi ro thời điểm giảm
Đây là kỹ thuật chuẩn trong quản lý danh mục hệ thống (Carver)."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.d1 import currency_reversal as CR, currency_carry as CY
from src.python.shared import carry_costs as CC, asset_profile as AP
pd.set_option("display.width",250,"display.max_columns",30)
DEV=pd.Timestamp("2024-01-01"); t0=time.time()
SPECS={s:(AP.get(s).base,AP.get(s).quote) for s in CR.PAIRS}
F, costs = CR.currency_returns(start="2020-01-01")

def leg_weights(sign, lb, hold, offset, n_leg=3):
    """Một LÔ: tái cân bằng mỗi `hold` ngày, lệch `offset` ngày so với gốc."""
    cum=F.cumsum(); sig=sign*(cum-cum.shift(lb))
    vol=F.rolling(63,min_periods=31).std()
    cols=list(F.columns); W=pd.DataFrame(0.0,index=F.index,columns=cols)
    held=pd.Series(0.0,index=cols); need=2*n_leg
    for i,t in enumerate(F.index):
        if i>lb and (i-offset)%hold==0:
            s,v=sig.iloc[i-1],vol.iloc[i-1]
            if s.notna().sum()>=need and v.notna().sum()>=need:
                o=s.dropna().sort_values(ascending=False); w=pd.Series(0.0,index=cols)
                for grp,sg in ((list(o.index[:n_leg]),1.0),(list(o.index[-n_leg:]),-1.0)):
                    iv=(1.0/v[grp].replace(0,np.nan)).fillna(0.0)
                    if iv.sum()>0: w[grp]=sg*iv/iv.sum()
                held=w
        W.loc[t]=held
    return W

def carry_w(lb_unused, hold, offset, n_leg=3):
    sig=CY.carry_signal(F); vol=F.rolling(63,min_periods=31).std()
    cols=list(F.columns); W=pd.DataFrame(0.0,index=F.index,columns=cols)
    held=pd.Series(0.0,index=cols); need=2*n_leg
    for i,t in enumerate(F.index):
        if i>63 and (i-offset)%hold==0:
            s,v=sig.iloc[i-1],vol.iloc[i-1]
            if s.notna().sum()>=need and v.notna().sum()>=need:
                o=s.dropna().sort_values(ascending=False); w=pd.Series(0.0,index=cols)
                for grp,sg in ((list(o.index[:n_leg]),1.0),(list(o.index[-n_leg:]),-1.0)):
                    iv=(1.0/v[grp].replace(0,np.nan)).fillna(0.0)
                    if iv.sum()>0: w[grp]=sg*iv/iv.sum()
                held=w
        W.loc[t]=held
    return W

def build(n_tranche, hold=21, lb=21, markup=1.0):
    """N lô so le, mỗi lô 50% reversal + 50% carry, gộp tỷ trọng TRƯỚC khi tính phí."""
    offs=[round(k*hold/n_tranche) for k in range(n_tranche)]
    Wr=sum(leg_weights(-1,lb,hold,o) for o in offs)/n_tranche
    Wc=sum(carry_w(lb,hold,o) for o in offs)/n_tranche
    W=0.5*Wr+0.5*Wc
    crisis=CR.regime_is_crisis(F,CR.Config())
    W=W.mask(crisis,0.0)
    P=CR.pair_weights(W); gross=(W*F).sum(axis=1)
    turn=P.diff().abs().fillna(P.abs()); tc=(turn*costs.reindex(P.columns)).sum(axis=1)/2.0
    cy=CC.pair_carry_bps(P,SPECS,broker_markup_pct=markup)
    net=(gross-tc-cy["total_carry_bps"]).dropna()
    # tần suất giao dịch: số ngày có thay đổi vị thế đáng kể
    days_trading=float((turn.sum(axis=1)>1e-6).mean())
    return net, {"tc":float(tc.mean())*252/100,"carry":float(cy["total_carry_bps"].mean())*252/100,
                 "days_trading":days_trading,"turn":float(turn.sum(axis=1).mean())}

print("="*118); print("CHIA LÔ SO LE — cùng edge 21 ngày, nhưng giao dịch thường xuyên hơn"); print("="*118)
rows=[]
for n in (1,3,5,7,11,21):
    net,info=build(n)
    d=CR.stats(net,"ALL")
    d.update({"n_lo":n,"vao_lenh_moi":f"{21/n:.1f} ngày","%ngày_giao_dịch":round(info["days_trading"]*100,1),
              "tc%":round(info["tc"],3),"carry%":round(info["carry"],3),
              "DEV":CR.stats(net[net.index<DEV],"")["sharpe"],"OOS":CR.stats(net[net.index>=DEV],"")["sharpe"]})
    rows.append(d)
T=pd.DataFrame(rows)
cols=["n_lo","vao_lenh_moi","%ngày_giao_dịch","tc%","carry%","ann_ret_pct","ann_vol_pct","sharpe","DEV","OOS","max_dd_pct","calmar"]
print(T[cols].to_string(index=False))
print(f"\nelapsed {time.time()-t0:.0f}s")
