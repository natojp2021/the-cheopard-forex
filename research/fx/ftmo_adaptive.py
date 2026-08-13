"""Vòng 12 — đòn bẩy THÍCH ỨNG vs CỐ ĐỊNH, trên cùng 86 cửa sổ."""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.d1 import currency_carry as CY
from src.python.execution import ftmo_leverage_policy as LP
from src.python.core.infra import ftmo
pd.set_option("display.width",250,"display.max_columns",30)

net,_,_ = CY.combined(start="2020-01-01", weight_reversal=0.5)
vol = float(net.std(ddof=1)); arr = net.to_numpy()
starts = list(range(0, max(1,len(arr)-252), 21))
print(f"σ_ngày = {vol:.3f} bps = {vol/100:.4f}%  ·  {len(starts)} cửa sổ trượt\n")

def fixed(lev, target, max_days=252):
    res=[]
    for s in starts:
        eq=100_000.0
        r=arr[s:]; out=("expire",max_days,eq)
        for i,x in enumerate(r):
            if i>=max_days: break
            ds=eq; eq*= (1.0+x*lev/1e4)
            if eq<=90_000: out=("MAX_LOSS",i,eq); break
            if eq<ds*(1-ftmo.DAILY_LOSS_HARD): out=("DAILY",i,eq); break
            if target and eq>=100_000*(1+target): out=("PASS",i,eq); break
        else: out=("expire",min(len(r),max_days),eq)
        res.append(out)
    return res

def adaptive(target, lev_max=6.0, max_days=252):
    return [LP.simulate_path(arr[s:], vol, target_pct=target,
                             max_days=max_days, leverage_max=lev_max) for s in starts]

def summarize(res, tag):
    n=len(res); p=sum(1 for o in res if o[0]=="PASS")
    b=sum(1 for o in res if o[0] in ("MAX_LOSS","DAILY"))
    e=n-p-b
    md=np.median([o[1] for o in res if o[0]=="PASS"]) if p else float('nan')
    finals=[(o[2]/100_000-1)*100 for o in res]
    return {"cấu hình":tag,"PASS":f"{p/n:.1%}","VI PHẠM":f"{b/n:.1%}","hết hạn":f"{e/n:.1%}",
            "ngày TV":f"{md:.0f}" if p else "—",
            "equity TV":f"{np.median(finals):+.2f}%","equity p10":f"{np.percentile(finals,10):+.2f}%"}

print("="*118); print("A. PHASE 1 (+10%, 252 ngày)"); print("="*118)
rows=[summarize(fixed(l,0.10), f"cố định {l}x") for l in (2,3,4,5,6)]
rows+= [summarize(adaptive(0.10,lm), f"THÍCH ỨNG (trần {lm:.0f}x)") for lm in (4.0,6.0,8.0)]
print(pd.DataFrame(rows).to_string(index=False))

print(); print("="*118); print("B. PHASE 2 (+5%, 252 ngày)"); print("="*118)
rows=[summarize(fixed(l,0.05), f"cố định {l}x") for l in (2,3,4)]
rows+= [summarize(adaptive(0.05,lm), f"THÍCH ỨNG (trần {lm:.0f}x)") for lm in (4.0,6.0)]
print(pd.DataFrame(rows).to_string(index=False))

print(); print("="*118); print("C. FUNDED — 1 năm, không mục tiêu, chỉ cần sống"); print("="*118)
rows=[summarize(fixed(l,None), f"cố định {l}x") for l in (2,3,4)]
rows+= [summarize(adaptive(None,lm), f"THÍCH ỨNG (trần {lm:.0f}x)") for lm in (4.0,6.0)]
print(pd.DataFrame(rows).to_string(index=False))

print(); print("="*118); print("D. VÍ DỤ CHÍNH SÁCH ĐANG QUYẾT GÌ"); print("="*118)
for eq,ds,lbl in [(100_000,100_000,"ngày đầu"),(103_000,103_000,"đã lãi 3%"),
                  (108_000,108_000,"đã lãi 8%"),(96_000,96_000,"đang lỗ 4%"),
                  (92_000,92_000,"đang lỗ 8% — sát sàn"),(101_000,104_000,"lỗ 2,9% trong ngày")]:
    d=LP.decide(eq,ds,vol)
    print(f"  {lbl:<24} equity ${eq:>7,} → lev {d.leverage:>4.2f}x  [{d.state:<12}] {d.reason}")
