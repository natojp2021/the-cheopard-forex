"""Vòng 28 — chỉ 3 cặp RẺ NHẤT: phí 2 chân 1,98-2,27 bps thay vì 3,4-3,9."""
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
CHEAP=["EURUSD","USDJPY","GBPUSD"]
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

print("="*126); print("3 CẶP RẺ — quét trần HL × time-stop, ĐỦ CHI PHÍ (giao dịch + swap)"); print("="*126)
rows=[]
for max_hl in (48,120,240):
    for ts in (1.5,2.0,3.0,4.32):
        cfg=CO.Config(max_hl_bars=max_hl,hl_multiplier=ts)
        tr=[]
        for a,b in combinations(CHEAP,2):
            for t in CO.simulate_pair(np.exp(logp[a]),np.exp(logp[b]),costs[a],costs[b],cfg=cfg):
                sw=swap_bps(a,b,t.side,t.entry_time,t.exit_time)
                tr.append({"time":pd.Timestamp(t.entry_time),"gross":t.gross_bps,"cost":t.cost_bps,
                           "swap":sw,"net":t.gross_bps-t.cost_bps-sw,"bars":t.bars_held,"pair":f"{a}/{b}"})
        if len(tr)<50: continue
        A=pd.DataFrame(tr); f=A[A["time"]<FORM]["net"]; o=A[A["time"]>=FORM]["net"]
        rows.append({"max_hl":max_hl,"ts":ts,"n":len(A),"ngay_giu":round(float(A["bars"].mean())/24,2),
            "gross":round(float(A["gross"].mean()),2),"phi":round(float(A["cost"].mean()),2),
            "swap":round(float(A["swap"].mean()),2),"net":round(float(A["net"].mean()),2),
            "t":round(float(A["net"].mean())/(float(A["net"].std(ddof=1))/np.sqrt(len(A))),2),
            "FORM":round(float(f.mean()),2) if len(f)>10 else None,
            "OOS":round(float(o.mean()),2) if len(o)>10 else None,
            "OOS_t":round(float(o.mean())/(float(o.std(ddof=1))/np.sqrt(len(o))),2) if len(o)>10 else None,
            "hit":round(float((A["net"]>0).mean()),3),"lenh_nam":round(len(A)/6.5,1)})
G=pd.DataFrame(rows); print(G.to_string(index=False))
good=G[(G["FORM"].fillna(-9)>0)&(G["OOS"].fillna(-9)>0)]
print()
print("Ô có CẢ FORM lẫn OOS dương:")
print(good.sort_values("t",ascending=False).to_string(index=False) if len(good) else "  KHÔNG có")

if len(good):
    b=good.sort_values("t",ascending=False).iloc[0]
    print()
    print("="*126); print(f"CHI TIẾT ô tốt nhất: max_hl={int(b['max_hl'])} ts={b['ts']}"); print("="*126)
    cfg=CO.Config(max_hl_bars=int(b["max_hl"]),hl_multiplier=float(b["ts"]))
    tr=[]
    for a,bb in combinations(CHEAP,2):
        for t in CO.simulate_pair(np.exp(logp[a]),np.exp(logp[bb]),costs[a],costs[bb],cfg=cfg):
            sw=swap_bps(a,bb,t.side,t.entry_time,t.exit_time)
            tr.append({"time":pd.Timestamp(t.entry_time),"net":t.gross_bps-t.cost_bps-sw,"pair":f"{a}/{bb}"})
    A=pd.DataFrame(tr)
    print("  theo cặp:")
    print(A.groupby("pair")["net"].agg(["count","mean"]).round(2).to_string())
    print("\n  theo năm (tổng bps):")
    print(A.set_index("time")["net"].groupby(lambda x: x.year).sum().round(0).to_string())
print(f"\nelapsed {time.time()-t0:.0f}s")
