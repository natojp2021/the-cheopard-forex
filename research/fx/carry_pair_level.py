"""Vòng 6b — phí swap tính ĐÚNG trên vị thế cặp + thử siết cổng chế độ.
Giả thuyết siết cổng đến TỪ CHẨN ĐOÁN CƠ CHẾ (Q5 vol rổ Sharpe 0,13 vs Q2 1,85),
không phải từ việc dò kết quả; và nó cắt THỜI GIAN TRONG THỊ TRƯỜNG = cắt thẳng phí swap."""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.d1 import currency_reversal as CR
from src.python.shared import carry_costs as CC, asset_profile as AP
pd.set_option("display.width",250,"display.max_columns",30)
DEV=pd.Timestamp("2024-01-01")
SPECS = {s:(AP.get(s).base, AP.get(s).quote) for s in CR.PAIRS}

def full_net(cfg, markup=1.0):
    r = CR.backtest(start="2020-01-01", cfg=cfg)
    pc = CC.pair_carry_bps(r.weights_pair, SPECS, broker_markup_pct=markup)
    return (r.gross - r.cost - pc["total_carry_bps"]).dropna(), r, pc

print("="*118); print("A. SO SÁNH: phí tính trên ĐỒNG TIỀN (sai) vs trên CẶP (đúng)"); print("="*118)
net_c, r, pc = full_net(CR.Config())
bd_ccy = CC.carry_breakdown(r.weights_ccy)
print(f"  mức đồng tiền: markup {float(bd_ccy['broker_markup_bps'].mean())*252/100:.3f}%/năm  "
      f"(Σ|w_ccy| tb = {r.weights_ccy.abs().sum(axis=1).mean():.3f})")
print(f"  mức CẶP      : markup {float(pc['broker_markup_bps'].mean())*252/100:.3f}%/năm  "
      f"(Σ|w_pair| tb = {float(pc['gross_exposure'].mean()):.3f})")
print(f"  chênh lệch lãi suất mức cặp: {float(pc['rate_diff_bps'].mean())*252/100:+.3f}%/năm")

print(); print("="*118); print("B. CHIẾN LƯỢC ĐỦ CHI PHÍ (mức cặp) — bản hiện tại vs siết cổng chế độ"); print("="*118)
variants = {
    "hiện tại  (loại top 20% vol)": CR.Config(regime_quantile=0.80),
    "siết      (loại top 40% vol)": CR.Config(regime_quantile=0.60),
    "siết mạnh (loại top 50% vol)": CR.Config(regime_quantile=0.50),
    "không cổng               ": CR.Config(regime_gate=False),
}
rows=[]
for name,cfg in variants.items():
    s, rr, p = full_net(cfg)
    act = 1.0 - float((rr.weights_pair.abs().sum(axis=1)<1e-9).mean())
    for lbl,x in (("DEV",s[s.index<DEV]),("OOS",s[s.index>=DEV]),("ALL",s)):
        d = CR.stats(x,lbl); d["variant"]=name; d["time_in_mkt"]=round(act,3)
        d["carry_pct"]=round(float(p["total_carry_bps"].mean())*252/100,3); rows.append(d)
T=pd.DataFrame(rows)
print(T[["variant","label","time_in_mkt","carry_pct","ann_ret_pct","ann_vol_pct","sharpe","max_dd_pct","calmar"]].to_string(index=False))

print(); print("="*118); print("C. STRESS BIÊN BROKER trên bản tốt nhất (mức cặp)"); print("="*118)
best_name = T[T["label"]=="OOS"].sort_values("sharpe",ascending=False).iloc[0]["variant"]
print(f"  bản có OOS Sharpe cao nhất: {best_name}")
cfg = variants[best_name]
for mk in (0.0,0.5,1.0,1.5,2.0,3.0):
    s,_,_ = full_net(cfg, markup=mk); o=s[s.index>=DEV]
    print(f"    biên {mk:>4.1f}%/năm: ALL sharpe={float(s.mean())/float(s.std(ddof=1))*np.sqrt(252):+.3f} ann={float(s.mean())*252/100:+6.2f}%"
          f"  |  OOS sharpe={float(o.mean())/float(o.std(ddof=1))*np.sqrt(252):+.3f} ann={float(o.mean())*252/100:+6.2f}%")
