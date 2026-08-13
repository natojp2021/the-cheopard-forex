"""Vòng 21 — cứu chiến lược M30 news: điểm yếu là CHI PHÍ (chết ở ×3).
Ba đòn: (a) vào muộn 1 nến để spread co, (b) chỉ cặp rẻ, (c) chỉ cú sốc lớn."""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.m30 import news_overreaction as NW
from src.python.shared import asset_profile as AP
pd.set_option("display.width",250,"display.max_columns",30)
DEV=pd.Timestamp("2024-01-01")

bars, costs = NW.load_panel()
print("chi phí khứ hồi (bps):", {s:round(costs[s],2) for s in costs.index})
CHEAP = ["EURUSD","USDJPY","GBPUSD"]
print(f"nhóm rẻ: {CHEAP}\n")

def run(entry_delay=0, hold=4, min_shock=5.0, syms=None, cost_mult=1.0, events=NW.EVENTS_DEFAULT):
    """entry_delay: vào lệnh ở nến p+delay thay vì p (chờ spread co lại)."""
    ev = NW.load_events(NW.Config(events=events))
    rows=[]
    use = syms or list(bars)
    for sym in use:
        b=bars[sym]; logc=np.log(b["close"])*1e4; idx=b.index; cost=float(costs[sym])*cost_mult
        for t in ev:
            p=idx.searchsorted(pd.Timestamp(t))
            e=p+entry_delay
            if p<1 or e+hold>=len(idx): continue
            shock=float(logc.iloc[p]-logc.iloc[p-1])
            if abs(shock)<min_shock: continue
            side=-int(np.sign(shock))
            gross=side*float(logc.iloc[e+hold]-logc.iloc[e])
            rows.append({"time":idx[p],"net":gross-cost})
    if not rows: return pd.Series(dtype=float)
    return pd.DataFrame(rows).groupby("time")["net"].mean().sort_index()

print("="*112); print("A. VÀO MUỘN — chờ spread co lại sau tin"); print("="*112)
for d in (0,1,2):
    for h in (4,6,8):
        s=run(entry_delay=d,hold=h)
        if len(s)<40: continue
        st=NW.stats(s,"")
        d3=NW.stats(s[s.index<DEV],""); o3=NW.stats(s[s.index>=DEV],"")
        print(f"  delay={d} hold={h}: n={st['n']:>3} net={st['net_bps']:+6.2f} t={st['t']:+5.2f} "
              f"sharpe={st['sharpe']:+.3f} | DEV t={d3.get('t',0):+5.2f} OOS t={o3.get('t',0):+5.2f}")

print(); print("="*112); print("B. CHỈ 3 CẶP RẺ NHẤT"); print("="*112)
for d in (0,1):
    for h in (4,6,8):
        s=run(entry_delay=d,hold=h,syms=CHEAP)
        if len(s)<40: continue
        st=NW.stats(s,"")
        d3=NW.stats(s[s.index<DEV],""); o3=NW.stats(s[s.index>=DEV],"")
        print(f"  delay={d} hold={h}: n={st['n']:>3} net={st['net_bps']:+6.2f} t={st['t']:+5.2f} "
              f"sharpe={st['sharpe']:+.3f} ann={st['ann_pct']:+.3f}% | DEV t={d3.get('t',0):+5.2f} OOS t={o3.get('t',0):+5.2f}")

print(); print("="*112); print("C. STRESS CHI PHÍ trên cấu hình tốt nhất của B"); print("="*112)
best=None; bs=-9
for d in (0,1):
    for h in (4,6,8):
        s=run(entry_delay=d,hold=h,syms=CHEAP)
        if len(s)>=40:
            st=NW.stats(s,"")
            if st["sharpe"]>bs and NW.stats(s[s.index>=DEV],"").get("t",0)>0:
                bs=st["sharpe"]; best=(d,h)
if best:
    d,h=best; print(f"  cấu hình: delay={d} hold={h}, 3 cặp rẻ")
    for k in (1,2,3,5):
        s=run(entry_delay=d,hold=h,syms=CHEAP,cost_mult=k)
        st=NW.stats(s,"")
        print(f"    chi phí ×{k}: net={st['net_bps']:+6.2f} t={st['t']:+5.2f} sharpe={st['sharpe']:+.3f} ann={st['ann_pct']:+.3f}%")
    print()
    s=run(entry_delay=d,hold=h,syms=CHEAP)
    by=s.groupby(s.index.year)
    print("  theo năm (net bps trung bình):"); print(by.mean().round(2).to_string())
else:
    print("  KHÔNG có cấu hình nào có OOS t > 0")
