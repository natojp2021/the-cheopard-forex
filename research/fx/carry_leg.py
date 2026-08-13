"""Vòng 9 — chân CARRY độc lập + danh mục hai chân. Chi phí đầy đủ."""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.d1 import currency_reversal as CR, currency_carry as CY
pd.set_option("display.width",250,"display.max_columns",30)
DEV=pd.Timestamp("2024-01-01")
def sh(s):
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(252) if sd>0 else np.nan

rev = CR.backtest(start="2020-01-01")
car = CY.backtest(start="2020-01-01")

print("="*118); print("A. CHÂN CARRY ĐỘC LẬP — đủ chi phí (markup 1,0%)"); print("="*118)
print(pd.DataFrame([CR.stats(car.net[car.net.index<DEV],"DEV"),
                    CR.stats(car.net[car.net.index>=DEV],"OOS"),
                    CR.stats(car.net,"ALL")]).to_string(index=False))
print(f"\n  phí carry của chân này: {float(car.carry_cost.mean())*252/100:+.3f}%/năm")
print(f"  trong đó chênh lệch lãi suất: (âm = NHẬN tiền)")
from src.python.shared import carry_costs as CC, asset_profile as AP
SPECS={s:(AP.get(s).base,AP.get(s).quote) for s in CR.PAIRS}
bd_car = CC.pair_carry_bps(car.weights_pair, SPECS, broker_markup_pct=1.0)
bd_rev = CC.pair_carry_bps(rev.weights_pair, SPECS, broker_markup_pct=1.0)
print(f"    CARRY   : {float(bd_car['rate_diff_bps'].mean())*252/100:+.3f}%/năm")
print(f"    REVERSAL: {float(bd_rev['rate_diff_bps'].mean())*252/100:+.3f}%/năm")

print(); print("="*118); print("B. TƯƠNG QUAN — điều kiện để đa dạng hoá có tác dụng"); print("="*118)
c = rev.net.corr(car.net)
print(f"  corr(reversal, carry) = {c:+.3f}")
cg = rev.gross.corr(car.gross)
print(f"  corr trên GROSS       = {cg:+.3f}")

print(); print("="*118); print("C. DANH MỤC HAI CHÂN — gộp vị thế TRƯỚC khi tính chi phí"); print("="*118)
rows=[]
for w in (0.0,0.25,0.4,0.5,0.6,0.75,1.0):
    net, parts, W = CY.combined(start="2020-01-01", weight_reversal=w)
    for lbl,x in (("DEV",net[net.index<DEV]),("OOS",net[net.index>=DEV]),("ALL",net)):
        d=CR.stats(x,lbl); d["w_rev"]=w
        d["carry_pct"]=round(float(parts["carry_cost_bps"].reindex(x.index).mean())*252/100,3)
        d["gross_expo"]=round(float(parts["gross_exposure"].reindex(x.index).mean()),3)
        rows.append(d)
T=pd.DataFrame(rows)
cols=["w_rev","label","gross_expo","carry_pct","ann_ret_pct","ann_vol_pct","sharpe","sortino","max_dd_pct","calmar"]
print(T[cols].to_string(index=False))

print(); print("="*118); print("D. SO SÁNH: cộng chuỗi RỜI vs gộp vị thế (chứng minh việc gộp là cần)"); print("="*118)
naive = (0.5*rev.net + 0.5*car.net).dropna()
merged, parts50, _ = CY.combined(start="2020-01-01", weight_reversal=0.5)
print(f"  cộng rời  : ann={float(naive.mean())*252/100:+.2f}%  sharpe={sh(naive):+.3f}")
print(f"  gộp vị thế: ann={float(merged.mean())*252/100:+.2f}%  sharpe={sh(merged):+.3f}")
print(f"  -> gộp tiết kiệm được {(float(merged.mean())-float(naive.mean()))*252/100:+.3f}%/năm chi phí trùng lặp")

print(); print("="*118); print("E. ĐỘ NHẠY BIÊN SWAP — danh mục 50/50 vs reversal đơn"); print("="*118)
print(f"{'markup':>8} | {'REV đơn ALL':>12} {'OOS':>7} | {'50/50 ALL':>10} {'OOS':>7}")
print("-"*60)
for mk in (0.0,0.5,1.0,1.5,2.0,3.0):
    r1 = CR.backtest(start="2020-01-01", broker_markup_pct=mk).net
    n2,_,_ = CY.combined(start="2020-01-01", weight_reversal=0.5, broker_markup_pct=mk)
    print(f"{mk:>8.2f} | {sh(r1):>12.3f} {sh(r1[r1.index>=DEV]):>7.3f} | {sh(n2):>10.3f} {sh(n2[n2.index>=DEV]):>7.3f}")
