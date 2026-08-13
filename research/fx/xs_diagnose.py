"""Vòng 3 — CHẨN ĐOÁN: 62,7% lợi nhuận từ 5 tháng là rủi ro hay là cơ chế?"""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_cross_section as XS
pd.set_option("display.width",250,"display.max_columns",30)
out = ROOT/"reports"/"fx_research"

R, costs = XS.pair_daily(start="2020-01-01"); F = XS.ccy_returns(R)
cfg = XS.XsConfig(21,21,3,3,sign=-1)
df = XS.run_xs(F,costs,cfg); net=df["net_bps"]
def sh(s): 
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(252) if sd>0 else np.nan

# 1. 5 tháng tốt nhất là tháng nào? Có phải sự kiện vĩ mô?
mo = net.groupby([net.index.year, net.index.month]).sum()
print("="*100); print("1. 10 THÁNG TỐT NHẤT / 5 THÁNG TỆ NHẤT (bps)"); print("="*100)
print("TỐT:"); print(mo.nlargest(10).round(0).to_string())
print("\nTỆ:"); print(mo.nsmallest(5).round(0).to_string())
print(f"\nphân phối tháng: n={len(mo)}  dương={int((mo>0).sum())} ({(mo>0).mean():.1%})  "
      f"trung vị={float(mo.median()):.0f} bps  trung bình={float(mo.mean()):.0f} bps")

# 2. Lợi nhuận có tương quan với BIẾN ĐỘNG rổ không? (giả thuyết cơ chế)
print(); print("="*100); print("2. CƠ CHẾ: lợi nhuận theo phân vị BIẾN ĐỘNG rổ tiền tệ (đo ngày TRƯỚC)")
print("="*100)
basket_vol = F.std(axis=1).rolling(21).mean().shift(1)
q = pd.qcut(basket_vol.reindex(net.index).dropna(), 5, labels=[1,2,3,4,5])
g = net.reindex(q.index).groupby(q, observed=True)
print(pd.DataFrame({"n":g.size(),"mean_bps":g.mean().round(3),"ann_pct":(g.mean()*252/100).round(2),
                    "sharpe":g.apply(lambda s: round(sh(s),2))}).to_string())

# 3. Đóng góp từng ĐỒNG TIỀN (chân nào tạo tiền?)
print(); print("="*100); print("3. ĐÓNG GÓP THEO ĐỒNG TIỀN"); print("="*100)
cum=F.cumsum(); mom=cum-cum.shift(21); vol=F.rolling(63,min_periods=31).std()
W=pd.DataFrame(0.0,index=F.index,columns=F.columns); lw=pd.Series(0.0,index=F.columns)
for i,t in enumerate(F.index):
    if i%21==0 and i>0:
        s=(-1*mom.iloc[i-1]).dropna(); v=vol.iloc[i-1]
        if len(s)>=6 and v.notna().sum()>=6:
            o=s.sort_values(ascending=False); L=list(o.index[:3]); S=list(o.index[-3:])
            w=pd.Series(0.0,index=F.columns)
            for grp,sg in ((L,1.0),(S,-1.0)):
                iv=(1.0/v[grp].replace(0,np.nan)).fillna(0.0)
                if iv.sum()>0: w[grp]=sg*iv/iv.sum()
            lw=w
    W.loc[t]=lw
contrib=(W*F).sum()
print(pd.DataFrame({"tong_bps":contrib.round(0),"ty_le":(contrib/contrib.sum()).round(3),
                    "ty_trong_tb":W.mean().round(3),"ty_trong_abs":W.abs().mean().round(3)}).sort_values("tong_bps",ascending=False).to_string())

# 4. Chân LONG (đồng yếu) vs chân SHORT (đồng mạnh) — chân nào có edge?
print(); print("="*100); print("4. CHÂN LONG (mua đồng YẾU) vs CHÂN SHORT (bán đồng MẠNH)"); print("="*100)
longs=(W.clip(lower=0)*F).sum(axis=1); shorts=(W.clip(upper=0)*F).sum(axis=1)
for tag,s in (("LONG (đồng yếu)",longs),("SHORT (đồng mạnh)",shorts),("TỔNG gross",longs+shorts)):
    print(f"  {tag:<20} ann={float(s.mean())*252/100:+6.2f}%  sharpe={sh(s):+.2f}  hit={(s>0).mean():.3f}")

# 5. Bao nhiêu ngày sau tái cân bằng thì edge xuất hiện? (thông tin cho tần suất)
print(); print("="*100); print("5. LỢI NHUẬN THEO NGÀY-TRONG-CHU-KỲ (0 = ngày tái cân bằng)"); print("="*100)
dic = pd.Series(np.arange(len(net))%21, index=net.index)
g2 = net.groupby(dic)
prof = pd.DataFrame({"mean_bps":g2.mean().round(3),"cum":g2.mean().cumsum().round(2)})
print(prof.T.to_string())
