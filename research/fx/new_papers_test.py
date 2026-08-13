"""Vòng 34 — hai ý tưởng từ tài liệu MỚI, áp cho chiến lược H1 cross.

A) TSMOM (Moskowitz/Ooi/Pedersen, JFE 2012) §4.1 — INVERSE-VOL SIZING:
   "We size each position so that it has an ex ante annualized volatility of 40%...
    position size = 40%/σ_{t−1}"
   Chiến lược cross hiện dùng tỷ trọng ĐỀU. Đây là nâng cấp có nguồn.

B) AdTurtle (Vezeris et al., JRFM 2019) — EXCLUSION ZONE theo ATR:
   "we added an exclusion zone based on the ATR indicator, in order to have
    controlled conditions for opening a new position"
   Áp cho ta: KHÔNG vào lệnh khi biến động cross đang bất thường cao — vì lúc đó
   dải Bollinger giãn ra và z-score mất ý nghĩa (đúng cơ chế Zheng Nan truy ra cho
   thất bại AUD/NZD: "cú tăng vọt biến động làm β đã hiệu chỉnh vô hiệu").
"""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_cross_pairs as CX
from src.python.strategies.h1 import cross_mean_reversion as XMR
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); DEV=pd.Timestamp("2024-01-01")

tr = XMR.backtest()
P, SPECS = CX.build_crosses("H1", start="2020-01-01")

def sh(s):
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(252) if sd>0 else np.nan
def report(tr_df, w, label):
    """w: Series trọng số theo index của tr_df (mỗi lệnh một trọng số)."""
    x = tr_df["net_bps"].to_numpy()*w.to_numpy()
    s = pd.Series(x, index=tr_df["entry_time"]).resample("1D").sum().fillna(0.0)
    s = s[s.index>=pd.Timestamp("2020-04-01")]
    return {"cfg":label,"n":len(tr_df),"ALL":round(sh(s),3),
            "FORM":round(sh(s[s.index<DEV]),3),"OOS":round(sh(s[s.index>=DEV]),3),
            "bps_ngay":round(float(s.mean()),2)}

print("="*112); print("A. INVERSE-VOL SIZING (TSMOM §4.1) vs TỶ TRỌNG ĐỀU"); print("="*112)
# vol ex-ante cua tung cross tai thoi diem vao lenh (252 nen H1 truoc, nhan qua)
vol_map={}
for n in P.columns:
    r=np.log(P[n]).diff()
    vol_map[n]=r.rolling(252,min_periods=100).std().shift(1)
w_eq=pd.Series(1.0,index=tr.index)
w_iv=[]
for _,row in tr.iterrows():
    v=vol_map[row["cross"]].get(row["entry_time"], np.nan)
    w_iv.append(1.0/v if (pd.notna(v) and v>0) else np.nan)
w_iv=pd.Series(w_iv,index=tr.index)
w_iv=(w_iv/w_iv.mean()).fillna(1.0)                # chuan hoa ve trung binh 1
rows=[report(tr,w_eq,"tỷ trọng ĐỀU (hiện tại)"), report(tr,w_iv,"INVERSE-VOL (TSMOM)")]
# gioi han don bay: chan 1 cross chiem qua nhieu
w_cap=w_iv.clip(upper=float(w_iv.quantile(0.90)))
rows.append(report(tr,w_cap,"inverse-vol + cap p90"))
print(pd.DataFrame(rows).to_string(index=False))

print(); print("="*112); print("B. EXCLUSION ZONE theo ATR (AdTurtle) — bỏ lệnh khi biến động bất thường"); print("="*112)
atr_map={}
for n in P.columns:
    s=P[n]
    tr_range=(s.rolling(2).max()-s.rolling(2).min())/s
    atr_map[n]=(tr_range.ewm(alpha=1/14,adjust=False).mean()/
                tr_range.ewm(alpha=1/14,adjust=False).mean().rolling(500,min_periods=200).median()).shift(1)
atr_rel=[]
for _,row in tr.iterrows():
    atr_rel.append(atr_map[row["cross"]].get(row["entry_time"], np.nan))
tr2=tr.copy(); tr2["atr_rel"]=atr_rel
print(f"  ATR tương đối tại lúc vào lệnh: p50={tr2['atr_rel'].median():.2f} p90={tr2['atr_rel'].quantile(0.9):.2f}")
rows=[report(tr,w_eq,"không lọc")]
for thr in (2.5,2.0,1.5,1.2):
    m=tr2["atr_rel"].fillna(1.0)<=thr
    sub=tr2[m]
    if len(sub)<200: continue
    d=report(sub,pd.Series(1.0,index=sub.index),f"loại ATR_rel > {thr}")
    d["%giữ"]=round(float(m.mean())*100,1); rows.append(d)
print(pd.DataFrame(rows).to_string(index=False))

print(); print("="*112); print("C. GHÉP CẢ HAI (nếu cả hai đều giúp)"); print("="*112)
best_thr=None
R=pd.DataFrame(rows)
cand=R[(R["cfg"]!="không lọc")&(R["OOS"]>R.iloc[0]["OOS"])&(R["ALL"]>R.iloc[0]["ALL"])]
if len(cand):
    best_thr=float(cand.iloc[0]["cfg"].split(">")[1])
    m=tr2["atr_rel"].fillna(1.0)<=best_thr; sub=tr2[m]
    wi=w_iv.reindex(sub.index); wi=(wi/wi.mean()).fillna(1.0)
    print(pd.DataFrame([report(sub,pd.Series(1.0,index=sub.index),f"ATR≤{best_thr} + đều"),
                        report(sub,wi,f"ATR≤{best_thr} + inverse-vol")]).to_string(index=False))
else:
    print("  bộ lọc ATR không cải thiện cả ALL lẫn OOS -> KHÔNG ghép")
print(f"\nelapsed {time.time()-t0:.0f}s")
