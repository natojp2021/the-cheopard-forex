"""Vòng 11b — BIÊN HIỆU QUẢ ĐÒN BẨY cho FTMO. Tối đa P(pass) với P(vi phạm) chấp nhận được."""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.d1 import currency_carry as CY, currency_reversal as CR
from src.python.core.infra import ftmo
pd.set_option("display.width",250,"display.max_columns",30)

net,parts,W = CY.combined(start="2020-01-01", weight_reversal=0.5)
rev = CR.backtest(start="2020-01-01").net

def simulate(r, lev, target_pct, max_days=252):
    eq=100_000.0
    for i,x in enumerate(r):
        if i>=max_days: return "expire", i
        ds=eq
        eq *= (1.0 + x*lev/1e4)
        if eq < 90_000.0: return "MAX_LOSS", i
        if eq < ds*(1-ftmo.DAILY_LOSS_HARD): return "DAILY", i
        if eq >= 100_000*(1+target_pct): return "PASS", i
    return "expire", max_days

def frontier(series, label, target=0.10, max_days=252):
    print(f"\n  --- {label} · mục tiêu +{target*100:.0f}% trong {max_days} ngày ---")
    print(f"  {'lev':>5} | {'PASS':>6} {'VI PHẠM':>8} {'hết hạn':>8} | {'ngày TV':>8} | {'DD kỳ vọng':>10}")
    arr = series.to_numpy()
    starts = range(0, max(1,len(arr)-max_days), 21)
    for lev in (1,2,3,4,5,6,8,10):
        out=[simulate(arr[s:], lev, target, max_days) for s in starts]
        n=len(out); p=sum(1 for o in out if o[0]=="PASS")
        b=sum(1 for o in out if o[0] in ("MAX_LOSS","DAILY"))
        e=sum(1 for o in out if o[0]=="expire")
        md=np.median([o[1] for o in out if o[0]=="PASS"]) if p else float('nan')
        # DD kỳ vọng trong cửa sổ 1 năm ở đòn bẩy đó
        dds=[]
        for s in starts:
            w=arr[s:s+max_days]*lev/1e4
            eq=np.cumprod(1+w); dd=float((np.maximum.accumulate(eq)-eq).max()/np.maximum.accumulate(eq).max())
            dds.append(dd*100)
        print(f"  {lev:>5} | {p/n:>6.1%} {b/n:>8.1%} {e/n:>8.1%} | {md if p else float('nan'):>8.0f} | {np.median(dds):>9.2f}%")

print("="*104); print("BIÊN HIỆU QUẢ ĐÒN BẨY — FTMO $100k"); print("="*104)
frontier(net, "DANH MỤC HAI CHÂN (rev+carry 50/50)")
frontier(rev, "REVERSAL ĐƠN")

print()
print("="*104); print("PHASE 2 (+5%) — dễ hơn nhiều"); print("="*104)
frontier(net, "DANH MỤC HAI CHÂN", target=0.05)

print()
print("="*104); print("TÀI KHOẢN FUNDED (không có mục tiêu lợi nhuận, chỉ cần không vi phạm)"); print("="*104)
arr=net.to_numpy(); starts=range(0,max(1,len(arr)-252),21)
for lev in (2,3,4,5,6,8):
    rets=[];bre=0
    for s in starts:
        w=arr[s:s+252]*lev/1e4
        eq=100_000*np.cumprod(1+w)
        breach = (eq<90_000).any()
        if breach: bre+=1
        rets.append((eq[-1]/100_000-1)*100)
    print(f"  lev {lev:>2}x: lợi nhuận năm trung vị {np.median(rets):+6.2f}% · "
          f"p10 {np.percentile(rets,10):+6.2f}% · P(vi phạm 10%) {bre/len(starts):.1%}")
