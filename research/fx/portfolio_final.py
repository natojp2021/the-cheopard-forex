"""Vòng 36 — xac minh module danh muc BA CHAN + FTMO."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies import portfolio as PF
from src.python.execution import ftmo_leverage_policy as LP
from src.python.core.infra import ftmo
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); DEV=pd.Timestamp("2024-01-01")

print("="*112); print("A. DANH MUC BA CHAN — chuan hoa bien dong tren FORM (khong dung OOS)"); print("="*112)
res = PF.backtest(start="2020-01-01")
net = res.net
print("  he so chuan hoa (1/sigma_FORM):", res.leg_scale if hasattr(res,'leg_scale') else {k:round(1/v,3) for k,v in res.leg_vol.items()})
print()
print(pd.DataFrame([PF.stats(net[net.index<DEV],"FORM"),PF.stats(net[net.index>=DEV],"OOS"),
                    PF.stats(net,"ALL")]).to_string(index=False))
print()
print("  tuong quan giua cac chan:"); print(PF.correlation_matrix(res).to_string())
print()
by=net.groupby(net.index.year)
print("  theo nam (Sharpe):")
print(by.apply(lambda s: round(float(s.mean())/float(s.std(ddof=1))*np.sqrt(252),2) if s.std(ddof=1)>0 else np.nan).to_string())
print(f"  nam duong: {int((by.sum()>0).sum())}/{len(by)}")

print(); print("="*112); print("B. STRESS BIEN SWAP BROKER — bien so quyet dinh"); print("="*112)
print(f"{'markup':>8} | {'ALL':>7} {'FORM':>7} {'OOS':>7}")
print("-"*40)
for mk in (0.0,0.5,1.0,1.5,2.0,3.0):
    r=PF.backtest(start="2020-01-01",broker_markup_pct=mk); s=r.net
    def sh(x):
        sd=float(x.std(ddof=1)); return float(x.mean())/sd*np.sqrt(252) if sd>0 else np.nan
    print(f"{mk:>8.1f} | {sh(s):>7.3f} {sh(s[s.index<DEV]):>7.3f} {sh(s[s.index>=DEV]):>7.3f}")

print(); print("="*112); print("C. FTMO $100k — don bay thich ung tren danh muc BA CHAN"); print("="*112)
vol=float(net.std(ddof=1))*100   # chuan hoa -> 1 sd/ngay; quy ve % de dung LP
arr=(net*100).to_numpy()          # 1 don vi = 1% equity o don bay 1
starts=list(range(0,max(1,len(arr)-252),21))
def summarize(res_list,tag):
    n=len(res_list); p=sum(1 for o in res_list if o[0]=="PASS")
    b=sum(1 for o in res_list if o[0] in ("MAX_LOSS","DAILY"))
    md=np.median([o[1] for o in res_list if o[0]=="PASS"]) if p else float('nan')
    fin=[(o[2]/100_000-1)*100 for o in res_list]
    return {"cfg":tag,"PASS":f"{p/n:.1%}","VI PHAM":f"{b/n:.1%}",
            "ngay TV":f"{md:.0f}" if p else "—","equity TV":f"{np.median(fin):+.2f}%"}
rows=[]
for lm in (2.0,3.0,4.0,6.0):
    out=[LP.simulate_path(arr[s:], vol, target_pct=0.10, max_days=252, leverage_max=lm) for s in starts]
    rows.append(summarize(out,f"thich ung tran {lm:.0f}x"))
print("  Phase 1 (+10%, 252 ngay):")
print(pd.DataFrame(rows).to_string(index=False))
rows=[]
for lm in (2.0,3.0,4.0):
    out=[LP.simulate_path(arr[s:], vol, target_pct=None, max_days=252, leverage_max=lm) for s in starts]
    rows.append(summarize(out,f"thich ung tran {lm:.0f}x"))
print("\n  FUNDED (1 nam, chi can song):")
print(pd.DataFrame(rows).to_string(index=False))
print(f"\nelapsed {time.time()-t0:.0f}s")
