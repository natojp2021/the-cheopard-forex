"""Vòng 27 — ÉP THỜI GIAN GIỮ XUỐNG 2-3 NGÀY để cắt swap.
Swap = 12,71 bps ở 8,2 ngày. Giảm còn 2,5 ngày -> swap ~3,9 bps.
Câu hỏi: gross giảm bao nhiêu? Nếu giảm ít hơn swap tiết kiệm được thì THẮNG."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from itertools import combinations
from src.python.research import fx_cointegration as CO
from src.python.shared import carry_costs as CC, asset_profile as AP
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); FORM=pd.Timestamp("2024-01-01")
logp, costs = CO.load_logprices(timeframe="H1", start="2020-01-01")
RATES = CC.rate_series(pd.DatetimeIndex(sorted(set(logp.index.normalize()))))

def swap_bps(a,b,side,t_in,t_out,markup=1.0):
    pa,pb=AP.get(a),AP.get(b)
    d0,d1=pd.Timestamp(t_in).normalize(),pd.Timestamp(t_out).normalize()
    nights=max((d1-d0).days,0)
    if nights==0: return 0.0
    try: r=RATES.loc[d0]
    except KeyError: r=RATES.iloc[RATES.index.searchsorted(d0)]
    def leg(p,w):
        diff=float(r.get(p.base,0.0)-r.get(p.quote,0.0))
        return (-w*diff+abs(w)*markup)/365.0*100.0*CC.SWAP_CALENDAR_MULTIPLIER
    return (leg(pa,side*1.0)+leg(pb,-side*1.0))*nights

def run(max_hl, ts_mult, min_hl=4):
    cfg=CO.Config(max_hl_bars=max_hl, hl_multiplier=ts_mult, min_hl_bars=min_hl)
    rows=[]
    for a,b in combinations(logp.columns,2):
        for t in CO.simulate_pair(np.exp(logp[a]),np.exp(logp[b]),costs[a],costs[b],cfg=cfg):
            sw=swap_bps(a,b,t.side,t.entry_time,t.exit_time)
            rows.append({"time":pd.Timestamp(t.entry_time),"gross":t.gross_bps,
                         "cost":t.cost_bps,"swap":sw,"net":t.gross_bps-t.cost_bps-sw,
                         "bars":t.bars_held,"pair":f"{a}/{b}","reason":t.exit_reason})
    return pd.DataFrame(rows)

print("="*126); print("QUÉT: trần half-life × hệ số time-stop  ->  tìm cấu hình giữ 2-3 ngày")
print("      (baseline cũ: max_hl=240, ts=4.32 -> giữ 8,2 ngày, swap 12,71, net +1,31, OOS −1,11)")
print("="*126)
rows=[]
for max_hl in (24,48,72,120):
    for ts in (1.0,1.5,2.0,3.0,4.32):
        A=run(max_hl,ts)
        if len(A)<100: continue
        o=A[A["time"]>=FORM]["net"]; f=A[A["time"]<FORM]["net"]
        rows.append({"max_hl":max_hl,"ts_mult":ts,"n":len(A),
            "ngay_giu":round(float(A["bars"].mean())/24,2),
            "gross":round(float(A["gross"].mean()),2),
            "phi_gd":round(float(A["cost"].mean()),2),
            "swap":round(float(A["swap"].mean()),2),
            "net":round(float(A["net"].mean()),2),
            "t":round(float(A["net"].mean())/(float(A["net"].std(ddof=1))/np.sqrt(len(A))),2),
            "FORM":round(float(f.mean()),2) if len(f)>10 else None,
            "OOS":round(float(o.mean()),2) if len(o)>10 else None,
            "OOS_t":round(float(o.mean())/(float(o.std(ddof=1))/np.sqrt(len(o))),2) if len(o)>10 else None,
            "hit":round(float((A["net"]>0).mean()),3)})
G=pd.DataFrame(rows)
print(G.to_string(index=False))

print()
print("="*126); print("Ô có CẢ FORM lẫn OOS dương"); print("="*126)
good=G[(G["FORM"].fillna(-9)>0)&(G["OOS"].fillna(-9)>0)]
print(good.sort_values("t",ascending=False).to_string(index=False) if len(good) else "  KHÔNG có")
print(f"\nelapsed {time.time()-t0:.0f}s")
