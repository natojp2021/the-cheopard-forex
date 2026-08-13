"""Vòng 16 — PHÉP ĐO QUYẾT ĐỊNH: có BẤT KỲ đặc trưng H1 nào dự báo được không?
Information Coefficient = corr(đặc trưng_t, lợi nhuận_{t+1..t+h}). Nếu IC ~ 0 khắp nơi
thì alpha H1 không tồn tại trong dữ liệu này và mọi chiến lược H1 đều vô vọng."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.shared import fx_data as D, asset_profile as AP
pd.set_option("display.width",250,"display.max_columns",40)

def features(sym, tf="H1", start="2020-01-01"):
    m1=D.load_m1(sym); b=D.build_bars(m1,tf); b=b[b.index>=start].copy()
    c=b["close"]; r=np.log(c).diff()*1e4
    f=pd.DataFrame(index=b.index)
    sd = r.rolling(500,min_periods=200).std()
    for k in (1,2,4,8,24,48,120):
        f[f"ret_{k}"] = r.rolling(k).sum()/ (sd*np.sqrt(k))
    f["range_rel"] = ((b["high"]-b["low"])/c*1e4) / ((b["high"]-b["low"])/c*1e4).rolling(500,min_periods=200).median()
    if "volume" in b: 
        f["vol_rel"] = b["volume"]/b["volume"].rolling(500,min_periods=200).median()
        f["vol_x_ret"] = f["vol_rel"]*f["ret_1"]
    f["spread_rel"] = b["spread_usd"]/b["spread_usd"].rolling(500,min_periods=200).median()
    for n in (24,120):
        f[f"ema_dist_{n}"] = (c - c.ewm(span=n,adjust=False).mean())/(c*sd/1e4)
    f["ibs"] = (b["close"]-b["low"])/(b["high"]-b["low"]).replace(0,np.nan)
    f["hour"] = b.index.hour
    f["dow"] = b.index.dayofweek
    # RSI 14
    d=c.diff(); up=d.clip(lower=0).ewm(alpha=1/14,adjust=False).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
    f["rsi"] = 100-100/(1+up/dn.replace(0,np.nan))
    return f, r

HOR=[1,2,4,8,24]
print("="*126); print("IC = corr(đặc trưng_t, lợi nhuận tương lai). |IC|>0,03 mới đáng chú ý ở n~50k")
print("="*126)
t0=time.time(); big={}
for sym in AP.FX_ALL:
    f,r = features(sym)
    rows={}
    for h in HOR:
        fwd = r.shift(-1).rolling(h).sum().shift(-(h-1))
        for col in f.columns:
            x=f[col]; m=x.notna()&fwd.notna()
            if m.sum()<1000: continue
            rows.setdefault(col,{})[f"h{h}"]=round(float(np.corrcoef(x[m],fwd[m])[0,1]),4)
    big[sym]=pd.DataFrame(rows).T
    
# gộp: IC trung bình qua 7 cặp
allic = sum(big[s] for s in big)/len(big)
print("\nIC TRUNG BÌNH 7 CẶP:")
print(allic.round(4).to_string())
print(f"\n  |IC| lớn nhất = {allic.abs().max().max():.4f}")
best = allic.abs().stack().sort_values(ascending=False).head(8)
print("\n  Top 8 |IC|:")
for (feat,h),v in best.items():
    sgn = allic.loc[feat,h]
    # tính t-stat gộp: IC * sqrt(N)
    n_eff = 40000
    print(f"    {feat:<14} {h:<4} IC={sgn:+.4f}  t≈{sgn*np.sqrt(n_eff):+.1f}")

print()
print("="*126); print("NHẤT QUÁN GIỮA CÁC CẶP — đặc trưng nào cùng dấu trên >=6/7 cặp?")
print("="*126)
for feat in allic.index:
    for h in allic.columns:
        vals=[big[s].loc[feat,h] for s in big if feat in big[s].index and h in big[s].columns]
        vals=[v for v in vals if pd.notna(v)]
        if len(vals)<7: continue
        pos=sum(1 for v in vals if v>0)
        if pos>=6 or pos<=1:
            print(f"  {feat:<14} {h:<4} IC_tb={np.mean(vals):+.4f}  cùng dấu {max(pos,7-pos)}/7  "
                  f"[{min(vals):+.4f} .. {max(vals):+.4f}]")
print(f"\nelapsed {time.time()-t0:.0f}s")
