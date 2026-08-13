"""Vòng 37 — FTMO tren danh muc BA CHAN, DON VI DUNG (risk-parity, % equity)."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies import portfolio as PF
from src.python.execution import ftmo_leverage_policy as LP
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); DEV=pd.Timestamp("2024-01-01")
res=PF.backtest(start="2020-01-01")

print("="*112); print("A. BA CACH GOP — cung mot chien luoc, ba don vi khac nhau"); print("="*112)
def prof(s,l,unit):
    cum=s.cumsum(); dd=cum.cummax()-cum; sd=float(s.std(ddof=1))
    return {"cach":l,"don vi":unit,"sharpe":round(float(s.mean())/sd*np.sqrt(252),3),
            "ann":round(float(s.mean())*252/100,2),"vol":round(sd*np.sqrt(252)/100,2),
            "maxDD":round(float(dd.max())/100,2)}
rp = res.risk_parity_bps(target_vol_pct_annual=8.0)
print(pd.DataFrame([
    prof(res.net_bps,"chia đều VỐN (không chuẩn hoá)","bps"),
    prof(rp,"chia đều RỦI RO, vol mục tiêu 8%","bps"),
]).to_string(index=False))
print()
print("  -> chia đều RỦI RO tốt hơn vì cross_h1 (vol 22,5%/năm) không áp đảo hai chân D1 (4,3-4,5%)")

print(); print("="*112); print("B. FTMO $100k — mo phong tren rp (don vi % equity dung)"); print("="*112)
for tvol in (6.0,8.0,10.0):
    s=res.risk_parity_bps(target_vol_pct_annual=tvol)
    arr=(s/100.0).to_numpy()   # bps -> %
    vol=float(np.std(arr,ddof=1))
    starts=list(range(0,max(1,len(arr)-252),21))
    def summ(out,tag):
        n=len(out); p=sum(1 for o in out if o[0]=="PASS")
        b=sum(1 for o in out if o[0] in ("MAX_LOSS","DAILY"))
        md=np.median([o[1] for o in out if o[0]=="PASS"]) if p else float('nan')
        fin=[(o[2]/100_000-1)*100 for o in out]
        return {"vol mục tiêu":f"{tvol:.0f}%","tran":tag,"PASS":f"{p/n:.1%}",
                "VI PHAM":f"{b/n:.1%}","ngay TV":f"{md:.0f}" if p else "—",
                "equity TV":f"{np.median(fin):+.2f}%","equity p10":f"{np.percentile(fin,10):+.2f}%"}
    rows=[]
    for lm in (2.0,3.0,4.0):
        out=[LP.simulate_path(arr[st:]*1e4, vol*1e4, target_pct=0.10, max_days=252, leverage_max=lm) for st in starts]
        rows.append(summ(out,f"{lm:.0f}x"))
    print(f"\n  Phase 1 (+10%), vol mục tiêu {tvol:.0f}%/năm:")
    print(pd.DataFrame(rows).to_string(index=False))

print(); print("="*112); print("C. FUNDED — 1 nam, chi can song"); print("="*112)
s=res.risk_parity_bps(target_vol_pct_annual=8.0); arr=(s/100.0).to_numpy(); vol=float(np.std(arr,ddof=1))
starts=list(range(0,max(1,len(arr)-252),21))
rows=[]
for lm in (2.0,3.0,4.0):
    out=[LP.simulate_path(arr[st:]*1e4, vol*1e4, target_pct=None, max_days=252, leverage_max=lm) for st in starts]
    n=len(out); b=sum(1 for o in out if o[0] in ("MAX_LOSS","DAILY"))
    fin=[(o[2]/100_000-1)*100 for o in out]
    rows.append({"tran":f"{lm:.0f}x","VI PHAM":f"{b/n:.1%}",
                 "loi nhuan TV":f"{np.median(fin):+.2f}%","p10":f"{np.percentile(fin,10):+.2f}%",
                 "p90":f"{np.percentile(fin,90):+.2f}%"})
print(pd.DataFrame(rows).to_string(index=False))
print(f"\nelapsed {time.time()-t0:.0f}s")
