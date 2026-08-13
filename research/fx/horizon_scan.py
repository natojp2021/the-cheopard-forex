"""Vòng 41 — QUÉT HORIZON KHÁC NHAU THẬT. Bài học vòng 40: cùng lookback-1-tháng ở
4 khung cho 28/28 cặp tương quan > 0,7 — đó là 1 chiến lược, không phải 8.
Lần này mỗi khung dùng horizon khác nhau về THỜI GIAN LỊCH, và tương quan là cổng."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_cross_lab as LAB
pd.set_option("display.width",270,"display.max_columns",30)
t0=time.time(); out=ROOT/"reports"/"fx_research"

# HORIZON theo KHUNG — cố ý khác nhau về thời gian lịch, không phải cùng 1 tháng
# (bars, gio_giu_uoc_tinh)
JOBS = {
 "M30": [  # khung ngan -> horizon NGAY/GIO
   ("zscore_fast",  "zscore_band", dict(min_hl=6,  max_hl=48,  hl_mult=3.0)),   # ~1-3 ngay
   ("xs_mom_1w",    "xs_reversal", dict(sign=+1, n_leg=5, lookback=240, rebalance_bars=48)),   # 5 ngay/1 ngay
   ("tsmom_2w",     "tsmom",       dict(lookback=480, rebalance_bars=48)),      # 10 ngay/1 ngay
   ("donchian_2d",  "donchian",    dict(lookback=96, exit_lookback=24)),        # 2 ngay/12h
 ],
 "H1": [
   ("zscore_zn",    "zscore_band", dict(min_hl=4,  max_hl=120, hl_mult=4.32)),  # ban Zheng Nan
   ("zscore_fast",  "zscore_band", dict(min_hl=4,  max_hl=36,  hl_mult=3.0)),   # nhanh hon
   ("xs_mom_1m",    "xs_reversal", dict(sign=+1, n_leg=5, lookback=504, rebalance_bars=120)),  # 21ng/5ng
   ("tsmom_3m",     "tsmom",       dict(lookback=1512, rebalance_bars=120)),    # 63ng/5ng
   ("donchian_1w",  "donchian",    dict(lookback=120, exit_lookback=48)),       # 5ng/2ng
 ],
 "H4": [
   ("zscore_slow",  "zscore_band", dict(min_hl=3,  max_hl=40,  hl_mult=4.32)),  # ~5-30 ngay
   ("xs_mom_2m",    "xs_reversal", dict(sign=+1, n_leg=5, lookback=252, rebalance_bars=30)),   # 42ng/5ng
   ("tsmom_6m",     "tsmom",       dict(lookback=756, rebalance_bars=30)),      # 126ng/5ng
   ("donchian_1m",  "donchian",    dict(lookback=126, exit_lookback=42)),       # 21ng/7ng
   ("cross_carry",  "cross_carry", dict(n_leg=5, rebalance_bars=30)),
 ],
 "D1": [
   ("zscore_slow",  "zscore_band", dict(min_hl=3,  max_hl=25,  hl_mult=4.32)),
   ("xs_mom_3m",    "xs_reversal", dict(sign=+1, n_leg=5, lookback=63, rebalance_bars=21)),
   ("tsmom_12m",    "tsmom",       dict(lookback=252, rebalance_bars=21)),      # TSMOM goc 12-1
   ("donchian_55",  "donchian",    dict(lookback=55, exit_lookback=20)),        # Turtle goc
   ("cross_carry",  "cross_carry", dict(n_leg=5, rebalance_bars=21)),
 ],
}
FN={"zscore_band":LAB.sig_zscore_band,"donchian":LAB.sig_donchian,
    "cross_carry":LAB.sig_cross_carry,"xs_reversal":LAB.sig_xs_reversal,
    "tsmom":LAB.sig_tsmom}

results=[]; rows=[]
for tf,jobs in JOBS.items():
    print(f"── {tf} ...", flush=True)
    p=LAB.build_panel(tf,start="2020-01-01")
    for label,fam,kw in jobs:
        try:
            r=LAB.simulate_positions(p, FN[fam](p,**kw), name=label)
            results.append(r); d=LAB.split_report(r); d["family"]=label; rows.append(d)
        except Exception as e:
            print(f"   {label}: LOI {type(e).__name__}: {e}")
T=pd.DataFrame(rows); T.to_csv(out/"horizon_scan.csv",index=False)
print()
print("="*150); print("KẾT QUẢ (đủ chi phí)"); print("="*150)
print(T.to_string(index=False))

print()
print("="*150); print("ỨNG VIÊN — FORM>0 và OOS>0 và ALL>0,3"); print("="*150)
g=T[(T["FORM"].fillna(-9)>0)&(T["OOS"].fillna(-9)>0)&(T["ALL"].fillna(-9)>0.3)]
print(g.sort_values(["tf","ALL"],ascending=[True,False]).to_string(index=False) if len(g) else "  khong co")

if len(g):
    keys=[f"{r['family']}.{r['tf']}" for _,r in g.iterrows()]
    sel=[r for r in results if f"{r.name}.{r.timeframe}" in keys]
    C=LAB.correlation_report(sel)
    print()
    print("="*150); print("CỔNG TƯƠNG QUAN — >0,7 nghĩa là TRÙNG chiến lược, không tính là 2"); print("="*150)
    print(C.to_string())
    # greedy chon nhom doc lap
    order=list(g.sort_values("ALL",ascending=False).apply(lambda r: f"{r['family']}.{r['tf']}",axis=1))
    keep=[]
    for k in order:
        if all(abs(C.loc[k,j])<=0.7 for j in keep): keep.append(k)
    print()
    print(f"  NHÓM ĐỘC LẬP (|corr| ≤ 0,7): {len(keep)} chiến lược")
    for k in keep: print(f"    {k}")
    print()
    cnt={}
    for k in keep: cnt[k.split('.')[1]]=cnt.get(k.split('.')[1],0)+1
    for tf,need in (("M30",3),("H1",4),("H4",2),("D1",2)):
        n=cnt.get(tf,0)
        print(f"    {tf}: {n}  (mục tiêu ≥{need})  {'✓' if n>=need else '✗ thiếu '+str(need-n)}")
print(f"\nelapsed {time.time()-t0:.0f}s")
