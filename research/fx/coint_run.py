"""Vòng 25 — pairs trading cointegration H1, quy trình Zheng Nan nguyên văn."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_cointegration as CO
from src.python.shared import asset_profile as AP
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); FORM=pd.Timestamp("2024-01-01")

logp, costs = CO.load_logprices(timeframe="H1", start="2020-01-01")
print(f"H1: {len(logp):,} nến × {len(logp.columns)} cặp")
print("chi phí khứ hồi (bps):", {k:round(v,2) for k,v in costs.items()})
print()

print("="*118); print("A. SÀNG LỌC CẶP trên cửa sổ FORM 2020-2024 (ADF + Johansen + β + HL)"); print("="*118)
form = logp[logp.index < FORM]
scr = CO.screen_pairs(form)
if scr.empty:
    print("  KHÔNG cặp nào qua sàng lọc")
else:
    print(scr.to_string(index=False))
    print(f"\n  {len(scr)}/21 tổ hợp qua sàng lọc")

print()
print("="*118); print("B. MÔ PHỎNG — β/HL ước lượng lại TRƯỢT, chi phí HAI CHÂN đầy đủ"); print("="*118)
rows=[]
pairs = [(r["x"],r["y"]) for _,r in scr.iterrows()] if not scr.empty else []
if not pairs:
    from itertools import combinations
    pairs = list(combinations(logp.columns,2))
    print("  (không có cặp qua sàng lọc -> mô phỏng TẤT CẢ 21 tổ hợp để xem có gì không)")
for a,b in pairs:
    tr = CO.simulate_pair(np.exp(logp[a]), np.exp(logp[b]), costs[a], costs[b])
    if len(tr)<20: continue
    df=pd.DataFrame([t.__dict__ for t in tr]); df["entry_time"]=pd.to_datetime(df["entry_time"])
    net=df.set_index("entry_time")["net_bps"].sort_index()
    d,o = net[net.index<FORM], net[net.index>=FORM]
    yrs=(net.index.max()-net.index.min()).days/365.25
    rows.append({"pair":f"{a}/{b}","n":len(net),"lenh_nam":round(len(net)/yrs,1),
        "gross":round(float(df["gross_bps"].mean()),2),"cost":round(float(df["cost_bps"].mean()),2),
        "net":round(float(net.mean()),2),
        "t":round(float(net.mean())/(float(net.std(ddof=1))/np.sqrt(len(net))),2),
        "FORM_net":round(float(d.mean()),2) if len(d)>5 else None,
        "OOS_net":round(float(o.mean()),2) if len(o)>5 else None,
        "OOS_n":len(o),"hit":round(float((net>0).mean()),3),
        "bars_tb":round(float(df["bars_held"].mean()),0),
        "%timestop":round(float((df["exit_reason"]=="TIMESTOP").mean()),2)})
R=pd.DataFrame(rows)
if len(R):
    print(R.sort_values("net",ascending=False).to_string(index=False))
    print()
    print("="*118); print("C. DANH MỤC — gộp mọi cặp có net>0 trên FORM, đo trên OOS"); print("="*118)
    sel = R[(R["FORM_net"].fillna(-9)>0)]
    print(f"  chọn trên FORM: {len(sel)} cặp -> {list(sel['pair'])}")
    if len(sel):
        allt=[]
        for p in sel["pair"]:
            a,b=p.split("/")
            tr=CO.simulate_pair(np.exp(logp[a]),np.exp(logp[b]),costs[a],costs[b])
            for t in tr: allt.append({"time":t.entry_time,"net":t.net_bps,"pair":p})
        A=pd.DataFrame(allt); A["time"]=pd.to_datetime(A["time"])
        oos=A[A["time"]>=FORM]
        print(f"\n  OOS: {len(oos)} lệnh · net trung bình {float(oos['net'].mean()):+.2f} bps · "
              f"t={float(oos['net'].mean())/(float(oos['net'].std(ddof=1))/np.sqrt(len(oos))):+.2f} · "
              f"hit={float((oos['net']>0).mean()):.3f}")
        print(f"  tổng OOS: {float(oos['net'].sum()):+.0f} bps trên {len(sel)} cặp")
else:
    print("  không cặp nào đủ 20 lệnh")
print(f"\nelapsed {time.time()-t0:.0f}s")
