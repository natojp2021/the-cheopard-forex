"""Vòng 31 — kiểm định nghiêm ứng viên H1 CROSS: control + PBO + stress + lọc có nguyên tắc."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_cross_pairs as CX
from src.python.shared import carry_costs as CC
from src.python.research.validation import stress_testing as ST, overfitting_stats as OS
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); FORM=pd.Timestamp("2024-01-01")
P,SPECS = CX.build_crosses("H1",start="2020-01-01")
RATES = CC.rate_series(pd.DatetimeIndex(sorted(set(P.index.normalize()))))

def swap_bps(spec,side,t_in,t_out,markup=1.0):
    d0,d1=pd.Timestamp(t_in).normalize(),pd.Timestamp(t_out).normalize()
    nights=max((d1-d0).days,0)
    if nights==0: return 0.0
    try: r=RATES.loc[d0]
    except KeyError: r=RATES.iloc[RATES.index.searchsorted(d0)]
    diff=float(r.get(spec.base,0.0)-r.get(spec.quote,0.0))
    return (-side*diff+markup)/365.0*100.0*CC.SWAP_CALENDAR_MULTIPLIER*nights

def run(cfg=CX.Config(), names=None, markup=1.0):
    rows=[]
    for name in (names or P.columns):
        sp=SPECS[name]
        for t in CX.simulate(name,P[name],sp,cfg):
            sw=swap_bps(sp,t.side,t.entry_time,t.exit_time,markup)
            rows.append({"time":pd.Timestamp(t.entry_time),"cross":name,"bars":t.bars_held,
                "gross":t.gross_bps,"cost":t.cost_bps,"swap":sw,"net":t.gross_bps-t.cost_bps-sw})
    return pd.DataFrame(rows).sort_values("time")

A=run()
def daily(df):
    d=df.set_index("time")["net"].resample("1D").sum().fillna(0.0)
    return d[d.index>=pd.Timestamp("2020-04-01")]
def sh(s):
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(252) if sd>0 else np.nan

print("="*118); print("A. CONTROL — vào NGẪU NHIÊN, cùng cross, cùng số lệnh, cùng thời gian giữ"); print("="*118)
rng=np.random.default_rng(31); ctl=[]
for k in range(250):
    best=[]
    for name in P.columns:
        sub=A[A["cross"]==name]
        if len(sub)<3: continue
        lp=np.log(P[name].dropna()).to_numpy(); n=len(lp)
        for _,r in sub.iterrows():
            h=int(r["bars"]); i=int(rng.integers(600,n-h-1)); s=int(rng.choice([-1,1]))
            best.append(s*(lp[i+h]-lp[i])*1e4 - r["cost"] - r["swap"])
    ctl.append(float(np.mean(best)))
ctl=np.array(ctl); real=float(A["net"].mean()); pct=float((ctl<real).mean())
print(f"  control: p05={np.percentile(ctl,5):+.2f} p50={np.percentile(ctl,50):+.2f} p95={np.percentile(ctl,95):+.2f}")
print(f"  THẬT   : {real:+.2f} bps -> phân vị {pct:.1%}  p={1-pct:.4f}")

print(); print("="*118); print("B. VÙNG THAM SỐ + PBO (lưới cửa sổ × ngưỡng vào)"); print("="*118)
grid={}
for m in (2.0,2.5,3.0,4.0,4.32):
    for sig in (1.5,2.0,2.5):
        B=run(CX.Config(lookback_hl_mult=m,entry_sigma=sig))
        if len(B)<200: continue
        grid[f"m{m}_s{sig}"]=daily(B)
M=pd.DataFrame(grid).fillna(0.0)
print("  Sharpe theo ô:")
sh_grid=pd.Series({k:sh(v) for k,v in grid.items()})
print(sh_grid.round(3).to_string())
pbo=OS.probability_of_backtest_overfitting(M,n_splits=8)
print(f"\n  PBO = {pbo['pbo']:.4f}  (ngưỡng < 0,50)   n_cau_hinh={int(pbo['n_strategies'])}")
print(f"  Sharpe: min {sh_grid.min():.3f} · trung vị {sh_grid.median():.3f} · max {sh_grid.max():.3f}")

print(); print("="*118); print("C. LỌC CÓ NGUYÊN TẮC — bỏ cross có half-life ngoài dải, KHÔNG bỏ theo lợi nhuận"); print("="*118)
d0=daily(A)
print(f"  tất cả 20 cross      : Sharpe ALL {sh(d0):+.3f} · OOS {sh(d0[d0.index>=FORM]):+.3f}")
for mh in (60,90,120):
    B=run(CX.Config(max_hl_bars=mh)); db=daily(B)
    print(f"  max_hl={mh:>3} nến H1     : Sharpe ALL {sh(db):+.3f} · OOS {sh(db[db.index>=FORM]):+.3f} · n={len(B)}")

print(); print("="*118); print("D. STRESS CHI PHÍ + BIÊN SWAP"); print("="*118)
for k in (1,1.5,2,3):
    x=A["gross"]-k*(A["cost"]+A["swap"]); dd=A.assign(net=x)
    print(f"  chi phí ×{k}: net={float(x.mean()):+6.2f} bps · Sharpe {sh(daily(dd)):+.3f}")
print()
for mk in (0.0,0.5,1.0,2.0):
    B=run(markup=mk); db=daily(B)
    print(f"  biên swap {mk:.1f}%/năm: net={float(B['net'].mean()):+6.2f} · Sharpe ALL {sh(db):+.3f} · OOS {sh(db[db.index>=FORM]):+.3f}")

print(); print("="*118); print("E. OUTLIER + THEO NĂM"); print("="*118)
o=ST.outlier_removal_test(list(A["net"].to_numpy()),n_remove=20)
print(f"  bỏ 20 lệnh tốt nhất /{len(A)}: {o['pct_of_profit_from_outliers']*100:.1f}% lợi nhuận · đổi dấu {o['sign_flipped_to_loss']}")
by=d0.groupby(d0.index.year)
print(f"\n  {int((by.sum()>0).sum())}/{len(by)} năm dương")
print(f"\nelapsed {time.time()-t0:.0f}s")
