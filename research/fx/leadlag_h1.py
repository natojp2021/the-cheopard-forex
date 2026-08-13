"""Vong 47 — LEAD-LAG giua cac cong cu, khung H1. Huong chua tung thu.

Y tuong: mot cong cu co the DAN mot cong cu khac vi thanh khoan/thong tin khong lan
truyen tuc thoi. Neu EURGBP dan EURCHF thi loi nhuan EURGBP hom nay du bao EURCHF
mai — day la thong tin CHEO GIUA cong cu, khac han moi thu da thu (deu la thong tin
TRONG mot chuoi).

Nguon: Lo & MacKinlay (1990) ve tu tuong quan cheo; Menkhoff et al. ve lan truyen
thong tin trong FX. Day la chieu duy nhat cua ma tran tu tuong quan chua khai thac:
     duong cheo  = momentum/reversal cua chinh no      -> DA THU
     ngoai cheo  = lead-lag giua cac cong cu           -> CHUA THU
"""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_cross_lab as LAB
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); DEV=pd.Timestamp("2024-01-01"); out=ROOT/"reports"/"fx_research"

panel=LAB.build_panel("H1",start="2020-01-01")
R=(panel.logp.diff()*1e4).dropna()
N=len(R.columns)
print(f"H1: {len(R):,} nen x {N} cross")

print(); print("="*110); print("A. MA TRAN TU TUONG QUAN CHEO — loi nhuan(i,t-1) vs loi nhuan(j,t)"); print("="*110)
X=R.shift(1).to_numpy()[1:]; Y=R.to_numpy()[1:]
m=np.isfinite(X).all(axis=1)&np.isfinite(Y).all(axis=1)
X,Y=X[m],Y[m]
Xz=(X-X.mean(0))/X.std(0,ddof=1); Yz=(Y-Y.mean(0))/Y.std(0,ddof=1)
CC=(Xz.T@Yz)/len(Xz)
C=pd.DataFrame(CC,index=R.columns,columns=R.columns)
diag=np.diag(CC); off=CC[~np.eye(N,dtype=bool)]
print(f"  duong cheo (chinh no):  trung binh {diag.mean():+.4f}  |max| {np.abs(diag).max():.4f}")
print(f"  ngoai cheo (lead-lag):  trung binh {off.mean():+.4f}  |max| {np.abs(off).max():.4f}")
t_thr=2.0/np.sqrt(len(Xz))
print(f"  nguong |IC| de t>2 voi n={len(Xz):,}: {t_thr:.4f}")
sig=int((np.abs(off)>t_thr).sum())
print(f"  so o ngoai cheo vuot nguong: {sig}/{N*N-N} ({sig/(N*N-N):.1%})")
top=[]
for i,a in enumerate(R.columns):
    for j,b in enumerate(R.columns):
        if i!=j: top.append((a,b,CC[i,j]))
top.sort(key=lambda x:-abs(x[2]))
print("\n  10 cap lead-lag manh nhat (dan -> theo):")
for a,b,v in top[:10]: print(f"    {a} -> {b}: {v:+.4f}  (t={v*np.sqrt(len(Xz)):+.1f})")

print(); print("="*110); print("B. CHIEN LUOC: du bao tung cross bang loi nhuan TRE cua CA RO"); print("="*110)
print("   Hoi quy da bien tren cua so truot, nhan qua. Vao lenh theo dau du bao.")
def build(lookback_fit=2000, refit=250, min_ic=0.0, top_k=5):
    Rv=R.to_numpy(); n,mm=Rv.shape
    pos=np.zeros((n,mm)); B=None; last=-10**9
    for i in range(lookback_fit+1,n):
        if i-last>=refit:
            W=Rv[i-lookback_fit:i]
            if np.isfinite(W).all():
                Xf=W[:-1]; Yf=W[1:]
                A=np.column_stack([Xf,np.ones(len(Xf))])
                try: B=np.linalg.lstsq(A,Yf,rcond=None)[0]
                except np.linalg.LinAlgError: B=None
            last=i
        if B is None: continue
        pred=np.append(Rv[i-1],1.0)@B          # du bao loi nhuan nen i
        if not np.isfinite(pred).all(): continue
        # chi vao top_k du bao manh nhat moi chieu
        o=np.argsort(-pred)
        w=np.zeros(mm)
        w[o[:top_k]]=1.0; w[o[-top_k:]]=-1.0
        pos[i]=w
    return pd.DataFrame(pos,index=R.index,columns=R.columns)

def sh(s):
    s=s[s.index>=pd.Timestamp("2020-04-01")]
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(252) if sd>0 else np.nan
rows=[]
for refit in (250,500):
    for tk in (3,5,8):
        p=build(refit=refit,top_k=tk)
        r=LAB.simulate_positions(panel,p,name=f"leadlag_r{refit}_k{tk}")
        d=r.pnl_daily
        rows.append({"refit":refit,"top_k":tk,"ALL":round(sh(d),3),
                     "FORM":round(sh(d[d.index<DEV]),3),"OOS":round(sh(d[d.index>=DEV]),3),
                     "gross":round(r.gross_bps_bar,4),"phi":round(r.trade_cost_bps_bar,4),
                     "swap":round(r.carry_cost_bps_bar,4),
                     "turn/nam":round(r.turnover_per_year,1),"%tt":round(r.time_in_market,2)})
        print(f"  refit={refit} top_k={tk} xong", flush=True)
T=pd.DataFrame(rows); T.to_csv(out/"leadlag_h1.csv",index=False)
print(); print(T.to_string(index=False))
print(); g=T[(T["FORM"]>0)&(T["OOS"]>0)&(T["ALL"]>0.5)]
print("CONG FORM>0 & OOS>0 & ALL>0,5:")
print(g.to_string(index=False) if len(g) else "  KHONG CO")
print(f"\nelapsed {time.time()-t0:.0f}s")
