"""Vòng 7 — VALIDATION ĐẦY ĐỦ bằng bộ công cụ SẴN CÓ của dự án.
parameter_stability_scan + find_stable_plateau  (Parameter Cliff)
probability_of_backtest_overfitting             (PBO / CSCV)
whites_reality_check                            (data-snooping đa chiến lược)
tenths_consistency                              (Kirkpatrick & Dahlquist)
robust_metrics                                  (R-cubed, drawdown profile)
outlier_removal_test / monte_carlo_permutation  (stress_testing)"""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.d1 import currency_reversal as CR
from src.python.shared import carry_costs as CC, asset_profile as AP
from src.python.research.validation import stress_testing as ST
from src.python.research.validation import overfitting_stats as OS
from src.python.research.validation import reality_check as RC
from src.python.research.validation import robust_metrics as RM
pd.set_option("display.width",250,"display.max_columns",30)
DEV=pd.Timestamp("2024-01-01")
SPECS={s:(AP.get(s).base,AP.get(s).quote) for s in CR.PAIRS}
out=ROOT/"reports"/"fx_research"; out.mkdir(parents=True,exist_ok=True)

def net_of(cfg, markup=1.0):
    r=CR.backtest(start="2020-01-01",cfg=cfg)
    pc=CC.pair_carry_bps(r.weights_pair,SPECS,broker_markup_pct=markup)
    return (r.gross-r.cost-pc["total_carry_bps"]).dropna()
def sh(s):
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(252) if sd>0 else np.nan

# ---- 1. PARAMETER CLIFF trên ngưỡng cổng chế độ
print("="*118); print("1. PARAMETER CLIFF — ngưỡng cổng chế độ (công cụ: parameter_stability_scan)"); print("="*118)
qs=[0.40,0.45,0.50,0.55,0.60,0.65,0.70,0.75,0.80,0.85,0.90]
series={}; met=[]
for q in qs:
    s=net_of(CR.Config(regime_quantile=q)); series[f"q{q:.2f}"]=s; met.append(sh(s))
rep=ST.parameter_stability_scan(qs,met)
print(rep.round(4).to_string(index=False))
pl=ST.find_stable_plateau(rep,min_plateau_width=3)
print(f"\n  bình nguyên: {pl}")

# ---- 2. PBO qua CSCV trên toàn bộ lưới đã thử
print(); print("="*118); print("2. PBO / CSCV — xác suất overfit trên lưới tham số đã thử"); print("="*118)
M=pd.DataFrame(series).dropna()
pbo=OS.probability_of_backtest_overfitting(M, n_splits=8)
for k,v in pbo.items():
    if isinstance(v,(int,float,np.floating)): print(f"  {k}: {v:.4f}")
    else: print(f"  {k}: {v}")

# ---- 3. WHITE'S REALITY CHECK
print(); print("="*118); print("3. WHITE'S REALITY CHECK — chiến lược tốt nhất có thắng được data-snooping?"); print("="*118)
try:
    res=RC.whites_reality_check({k:v.to_numpy() for k,v in series.items()}, n_bootstrap=2000)
    print(f"  {res}")
except Exception as e:
    print(f"  (lỗi: {e})")

# ---- chọn cấu hình theo BÌNH NGUYÊN, không theo đỉnh
q_star = 0.50 if pl is None else float(np.clip((pl["start_param"]+pl["end_param"])/2, 0.40, 0.90))
q_star = min(qs, key=lambda q: abs(q-q_star))
print(f"\n  -> chọn regime_quantile = {q_star:.2f} (giữa bình nguyên, KHÔNG phải đỉnh)")
best=series[f"q{q_star:.2f}"]

# ---- 4. TENTHS CONSISTENCY
print(); print("="*118); print("4. TENTHS CONSISTENCY — 10 khúc thời gian (Kirkpatrick & Dahlquist)"); print("="*118)
from src.python.research.validation import robustness_diagnostics as RD
try:
    cr=RD.tenths_consistency(list(best.index), list(best.to_numpy()/100.0), n_segments=10)
    for seg in getattr(cr,"segments",[]): print(f"  {seg}")
    print(f"  tóm tắt: {cr}")
except Exception as e:
    print(f"  (lỗi: {e})")

# ---- 5. ROBUST METRICS
print(); print("="*118); print("5. ROBUST METRICS — R-cubed, drawdown profile"); print("="*118)
eq=(1.0+best/1e4).cumprod()
try:
    rm=RM.compute(eq, periods_per_year=252)
    print(f"  {rm}")
except Exception as e:
    print(f"  (lỗi: {e})")

# ---- 6. OUTLIER + PERMUTATION
print(); print("="*118); print("6. OUTLIER REMOVAL + MONTE CARLO PERMUTATION"); print("="*118)
mo=best.groupby([best.index.year,best.index.month]).sum()
o=ST.outlier_removal_test(list(mo.to_numpy()), n_remove=5)
print(f"  outlier (theo THÁNG): {o}")
try:
    mc=ST.monte_carlo_permutation(list(best.to_numpy()/1e4), n_simulations=2000)
    print(f"  permutation: {mc}")
except Exception as e:
    print(f"  (permutation lỗi: {e})")

# ---- 7. KẾT QUẢ CUỐI
print(); print("="*118); print("7. CHAMPION SAU KHI ĐỦ CHI PHÍ (markup 1,0%/năm)"); print("="*118)
print(pd.DataFrame([CR.stats(best[best.index<DEV],"DEV"),CR.stats(best[best.index>=DEV],"OOS"),
                    CR.stats(best,"ALL")]).to_string(index=False))
by=best.groupby(best.index.year)
print("\n  theo năm:"); print(pd.DataFrame({"ann_pct":(by.mean()*252/100).round(2),
      "sharpe":by.apply(lambda s: round(sh(s),2))}).to_string())
best.to_csv(out/"champion_net_full_costs.csv")
