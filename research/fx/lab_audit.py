"""Vòng 40 — KIỂM TOÁN lab: (a) 8 ứng viên có phải 8 chiến lược thật?
(b) vì sao zscore_band H1 ở lab = −0,241 mà production = +1,059?"""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_cross_lab as LAB
pd.set_option("display.width",260,"display.max_columns",30)
t0=time.time()

print("="*118); print("A. TƯƠNG QUAN — 8 'ứng viên' có phải 8 chiến lược ĐỘC LẬP?"); print("="*118)
res=[]
for tf in ["M30","H1","H4","D1"]:
    p=LAB.build_panel(tf,start="2020-01-01")
    for fam,kw in (("xs_momentum",dict(sign=+1,n_leg=5)),("tsmom",dict())):
        fn=LAB.sig_xs_reversal if fam=="xs_momentum" else LAB.sig_tsmom
        r=LAB.simulate_positions(p, fn(p,**kw), name=fam); res.append(r)
C=LAB.correlation_report(res)
print(C.to_string())
print()
hi=[(a,b,C.loc[a,b]) for i,a in enumerate(C.index) for b in C.columns[i+1:] if abs(C.loc[a,b])>0.7]
print(f"  cặp có |tương quan| > 0,7: {len(hi)}/{len(C)*(len(C)-1)//2}")
for a,b,v in hi[:12]: print(f"    {a:<18} {b:<18} {v:+.3f}")

print()
print("="*118); print("B. VÌ SAO zscore_band H1 lệch? So từng thành phần"); print("="*118)
from src.python.strategies.h1 import cross_mean_reversion as XMR
tr=XMR.backtest()
print(f"  PRODUCTION: {len(tr)} lệnh · net {tr['net_bps'].mean():+.2f} bps/lệnh · "
      f"Sharpe {XMR.stats(XMR.daily_pnl(tr),'')['sharpe']}")
p=LAB.build_panel("H1",start="2020-01-01")
pos=LAB.sig_zscore_band(p,min_hl=4,max_hl=120)
r=LAB.simulate_positions(p,pos,name="zscore_band")
print(f"  LAB       : %trong thị trường {r.time_in_market:.3f} · turnover {r.turnover_per_year:.1f}/năm · "
      f"Sharpe {LAB.stats(r.pnl_daily,'')['sharpe']}")
print()
# so thoi gian giu
dur=[]
for c in pos.columns:
    s=pos[c]; ch=s.diff().abs()>0
    idx=np.flatnonzero(ch.to_numpy())
    if len(idx)>1: dur += list(np.diff(idx))
print(f"  LAB giữ vị thế trung bình {np.mean(dur) if dur else 0:.0f} nến H1 = {np.mean(dur)/24 if dur else 0:.1f} ngày")
print(f"  PRODUCTION giữ {tr['bars_held'].mean():.0f} nến = {tr['bars_held'].mean()/24:.1f} ngày")
print()
print("  -> NGUYÊN NHÂN: `sig_zscore_band` KHÔNG có time-stop, chỉ thoát khi cắt trung bình.")
print("     Vị thế thua bị giữ vô hạn. Production có time-stop ceil(4,32×HL) và 11% lệnh")
print("     thoát bằng nó — chính 11% đó là thứ chặn lỗ kéo dài.")
print(f"\nelapsed {time.time()-t0:.0f}s")
