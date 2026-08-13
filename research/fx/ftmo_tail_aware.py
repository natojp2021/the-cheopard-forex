"""Vòng 38 — FTMO voi rang buoc DUOI. So sanh truoc/sau."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies import portfolio as PF
from src.python.execution import ftmo_leverage_policy as LP
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time()
res=PF.backtest(start="2020-01-01")

def summ(out,tag):
    n=len(out); p=sum(1 for o in out if o[0]=="PASS")
    b=sum(1 for o in out if o[0] in ("MAX_LOSS","DAILY"))
    md=np.median([o[1] for o in out if o[0]=="PASS"]) if p else float('nan')
    fin=[(o[2]/100_000-1)*100 for o in out]
    return {"cfg":tag,"PASS":f"{p/n:.1%}","VI PHAM":f"{b/n:.1%}",
            "ngay TV":f"{md:.0f}" if p else "—",
            "equity TV":f"{np.median(fin):+.2f}%","p10":f"{np.percentile(fin,10):+.2f}%"}

for tvol in (6.0,8.0):
    s=res.risk_parity_bps(tvol); arr=s.to_numpy()
    vol=float(s.std(ddof=1)); wd=float(s.min())
    starts=list(range(0,max(1,len(arr)-252),21))
    print("="*112)
    print(f"VOL MUC TIEU {tvol:.0f}%/nam  ·  sigma {vol:.1f} bps  ·  ngay te nhat {wd:.0f} bps ({abs(wd)/vol:.1f}σ)")
    print("="*112)
    rows=[]
    for tag,w in (("KHONG duoi",None),("CO duoi",wd)):
        for lm in (2.0,4.0):
            out=[LP.simulate_path(arr[st:],vol,target_pct=0.10,max_days=252,
                                  leverage_max=lm,worst_day_bps=w) for st in starts]
            rows.append(summ(out,f"{tag}, tran {lm:.0f}x"))
    print("  Phase 1 (+10%, 252 ngay):")
    print(pd.DataFrame(rows).to_string(index=False))
    rows=[]
    for tag,w in (("KHONG duoi",None),("CO duoi",wd)):
        for lm in (2.0,4.0):
            out=[LP.simulate_path(arr[st:],vol,target_pct=None,max_days=252,
                                  leverage_max=lm,worst_day_bps=w) for st in starts]
            rows.append(summ(out,f"{tag}, tran {lm:.0f}x"))
    print("\n  FUNDED (1 nam):")
    print(pd.DataFrame(rows).to_string(index=False))
    print()

print("="*112); print("PHASE 2 (+5%) voi rang buoc duoi"); print("="*112)
s=res.risk_parity_bps(8.0); arr=s.to_numpy(); vol=float(s.std(ddof=1)); wd=float(s.min())
starts=list(range(0,max(1,len(arr)-252),21))
rows=[]
for lm in (2.0,4.0,6.0):
    out=[LP.simulate_path(arr[st:],vol,target_pct=0.05,max_days=252,
                          leverage_max=lm,worst_day_bps=wd) for st in starts]
    rows.append(summ(out,f"tran {lm:.0f}x"))
print(pd.DataFrame(rows).to_string(index=False))
print(f"\nelapsed {time.time()-t0:.0f}s")
