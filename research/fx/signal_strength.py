"""Vòng 8 — ĐÒN CUỐI trên chi phí swap: chỉ vào lệnh khi TÍN HIỆU ĐỦ MẠNH.
Cơ sở: swap tính theo ĐÊM nên không giảm được bằng tần suất; đòn bẩy duy nhất là
THỜI GIAN TRONG THỊ TRƯỜNG. Lọc theo độ phân tán cắt ngang = chỉ đứng trong thị
trường khi phép xếp hạng thực sự có nội dung, thay vì khi 8 đồng gần như bằng nhau."""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.d1 import currency_reversal as CR
from src.python.shared import carry_costs as CC, asset_profile as AP
from src.python.research.validation import overfitting_stats as OS
pd.set_option("display.width",250,"display.max_columns",30)
DEV=pd.Timestamp("2024-01-01"); SPECS={s:(AP.get(s).base,AP.get(s).quote) for s in CR.PAIRS}
def sh(s):
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(252) if sd>0 else np.nan

F,costs = CR.currency_returns(start="2020-01-01")
cum=F.cumsum(); LB=21
signal=-(cum-cum.shift(LB))
# ĐỘ PHÂN TÁN cắt ngang: std của tín hiệu qua 8 đồng, chuẩn hoá theo biến động rổ
disp = signal.std(axis=1) / F.rolling(63,min_periods=31).std().mean(axis=1)
disp_thr = disp.shift(1).rolling(252,min_periods=126).quantile(0.50)   # trên trung vị lịch sử

def run(gate_disp=False, disp_q=0.50, regime_q=0.80):
    cfg=CR.Config(regime_quantile=regime_q)
    vol=F.rolling(63,min_periods=31).std()
    crisis=CR.regime_is_crisis(F,cfg)
    thr = disp.shift(1).rolling(252,min_periods=126).quantile(disp_q)
    weak = (disp.shift(1) < thr).fillna(False) if gate_disp else pd.Series(False,index=F.index)
    W=pd.DataFrame(0.0,index=F.index,columns=F.columns); held=pd.Series(0.0,index=F.columns)
    for i,t in enumerate(F.index):
        if i%21==0 and i>0:
            s,v=signal.iloc[i-1],vol.iloc[i-1]
            if s.notna().sum()>=6 and v.notna().sum()>=6:
                o=s.dropna().sort_values(ascending=False); w=pd.Series(0.0,index=F.columns)
                for grp,sg in ((list(o.index[:3]),1.0),(list(o.index[-3:]),-1.0)):
                    iv=(1.0/v[grp].replace(0,np.nan)).fillna(0.0)
                    if iv.sum()>0: w[grp]=sg*iv/iv.sum()
                held=w
        W.loc[t]= 0.0 if (crisis.iloc[i] or weak.iloc[i]) else held
    P=CR.pair_weights(W)
    gross=(W*F).sum(axis=1)
    turn=P.diff().abs().fillna(P.abs())
    cost=(turn*costs.reindex(P.columns)).sum(axis=1)/2.0
    pc=CC.pair_carry_bps(P,SPECS,broker_markup_pct=1.0)
    return (gross-cost-pc["total_carry_bps"]).dropna(), P

print("="*118); print("LỌC ĐỘ PHÂN TÁN TÍN HIỆU (kèm cổng chế độ 0,80) — đủ chi phí, markup 1,0%"); print("="*118)
rows=[]; series={}
for gd,dq,label in [(False,0.0,"không lọc phân tán"),(True,0.30,"lọc dưới p30"),
                    (True,0.50,"lọc dưới p50"),(True,0.70,"lọc dưới p70")]:
    s,P = run(gate_disp=gd, disp_q=dq)
    series[label]=s
    search_grid = 1.0-float((P.abs().sum(axis=1)<1e-9).mean())
    for lbl,x in (("DEV",s[s.index<DEV]),("OOS",s[s.index>=DEV]),("ALL",s)):
        d=CR.stats(x,lbl); d["cfg"]=label; d["time_in_mkt"]=round(search_grid,3); rows.append(d)
T=pd.DataFrame(rows)
print(T[["cfg","label","time_in_mkt","ann_ret_pct","ann_vol_pct","sharpe","max_dd_pct","calmar"]].to_string(index=False))

print(); print("="*118); print("PBO trên nhóm biến thể này"); print("="*118)
M=pd.DataFrame(series).dropna()
pbo=OS.probability_of_backtest_overfitting(M,n_splits=8)
print(f"  PBO = {pbo['pbo']:.4f}   (ngưỡng López de Prado: < 0,50)")
print(f"  tương quan giữa các biến thể: {M.corr().min().min():.3f} .. {M.corr().replace(1,np.nan).max().max():.3f}")
