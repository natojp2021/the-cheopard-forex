"""Vòng 10 — validation danh mục hai chân bằng bộ công cụ dự án.
Điểm kỷ luật: w=0,5 là CHIA ĐỀU do Olszweski & Zhou ĐẶC TẢ TRƯỚC (họ chứng minh
chia đều thắng tối ưu hoá, Sharpe 0,98 vs 0,70), KHÔNG phải giá trị chọn từ lưới."""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.d1 import currency_reversal as CR, currency_carry as CY
from src.python.research.validation import overfitting_stats as OS
from src.python.research.validation import stress_testing as ST
from src.python.research.validation import robustness_diagnostics as RD
from src.python.research.validation import robust_metrics as RM
pd.set_option("display.width",250,"display.max_columns",30)
DEV=pd.Timestamp("2024-01-01")
def sh(s):
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(252) if sd>0 else np.nan
out=ROOT/"reports"/"fx_research"

net,parts,W = CY.combined(start="2020-01-01", weight_reversal=0.5)

print("="*112); print("1. PBO — tỷ trọng hai chân có chọn được đáng tin không?"); print("="*112)
grid={}
for w in (0.0,0.2,0.3,0.4,0.5,0.6,0.7,0.8,1.0):
    n,_,_ = CY.combined(start="2020-01-01", weight_reversal=w); grid[f"w{w:.1f}"]=n
M=pd.DataFrame(grid).dropna()
pbo=OS.probability_of_backtest_overfitting(M,n_splits=8)
print(f"  PBO = {pbo['pbo']:.4f}  (ngưỡng < 0,50)   n_strategies={int(pbo['n_strategies'])}")
rep=ST.parameter_stability_scan([0.0,0.2,0.3,0.4,0.5,0.6,0.7,0.8,1.0],[sh(grid[k]) for k in grid])
print(f"  vách đá: {int(rep['is_cliff_neighbor'].sum())}/{len(rep)} điểm")
pl=ST.find_stable_plateau(rep,min_plateau_width=3)
print(f"  bình nguyên: {pl}")

print(); print("="*112); print("2. TENTHS CONSISTENCY (Kirkpatrick & Dahlquist)"); print("="*112)
cr=RD.tenths_consistency(list(net.index), list(net.to_numpy()/100.0), n_segments=10)
for s in cr.segments:
    print(f"  khúc {s.idx:>2}: {str(s.start.date())} → {str(s.end.date())}  total_r={s.total_r:+.3f}  maxDD={s.max_drawdown_r:+.3f}")
print(f"  -> {cr.n_segments_positive}/{cr.n_segments} khúc dương")

print(); print("="*112); print("3. ROBUST METRICS"); print("="*112)
eq=(1.0+net/1e4).cumprod()
rm=RM.compute(eq,periods_per_year=252)
print(f"  RAR {rm.rar_pct:.2f}%  r_cubed {rm.r_cubed:.3f}  robust_sharpe {rm.robust_sharpe:.3f}  MAR {rm.mar:.3f}")
print(f"  maxDD {rm.max_drawdown*100:.2f}%  dài nhất {rm.drawdown.max_length_days:.0f} ngày  TB {rm.drawdown.avg_max_length_days:.0f} ngày")
print(f"  (REV đơn trước đây: r_cubed 0,559 · maxDD dài nhất 610 ngày)")

print(); print("="*112); print("4. OUTLIER REMOVAL — theo tháng"); print("="*112)
mo=net.groupby([net.index.year,net.index.month]).sum()
o=ST.outlier_removal_test(list(mo.to_numpy()),n_remove=5)
print(f"  5 tháng tốt nhất = {o['pct_of_profit_from_outliers']*100:.1f}% lợi nhuận  (REV đơn: 62-79%)")
print(f"  bỏ đi -> tổng {o['total_return_after']:.0f} bps, đổi dấu: {o['sign_flipped_to_loss']}")

print(); print("="*112); print("5. THEO NĂM"); print("="*112)
by=net.groupby(net.index.year)
print(pd.DataFrame({"ann_pct":(by.mean()*252/100).round(2),
                    "sharpe":by.apply(lambda s: round(sh(s),2))}).to_string())

print(); print("="*112); print("6. CHỐT — danh mục 50/50, đủ chi phí"); print("="*112)
print(pd.DataFrame([CR.stats(net[net.index<DEV],"DEV"),CR.stats(net[net.index>=DEV],"OOS"),
                    CR.stats(net,"ALL")]).to_string(index=False))
net.to_csv(out/"portfolio_2leg_net.csv")
