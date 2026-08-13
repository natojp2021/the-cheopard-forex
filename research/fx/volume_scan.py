"""Vòng 15 — KHỐI LƯỢNG có tách được thanh khoản khỏi thông tin không?
Dự đoán ghi TRƯỚC (Campbell-Grossman-Wang): VOL_THAP fade có lãi, VOL_CAO fade lỗ."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_volume_conditioned as VC
from src.python.shared import asset_profile as AP
pd.set_option("display.width",250,"display.max_columns",30)
out=ROOT/"reports"/"fx_research"; t0=time.time()

print("="*120)
print("A. FADE DỊCH CHUYỂN LỚN, TÁCH THEO KHỐI LƯỢNG — H1, |ret_z|>=1.5, hold=1")
print("   Dự đoán: VOL_THAP có ratio DƯƠNG, VOL_CAO ratio ÂM/thấp hơn")
print("="*120)
allr=[]
for sym in AP.FX_ALL:
    b = VC.load_bars(sym, "H1", start="2020-01-01")
    r = VC.conditional_reversal(b, hold=1, move_z=1.5)
    if not r.empty:
        r["symbol"]=sym; allr.append(r)
A = pd.concat(allr, ignore_index=True)
piv = A.pivot(index="symbol", columns="bucket", values="ratio")
pivt = A.pivot(index="symbol", columns="bucket", values="t_stat")
print("cost_ratio (fade, >1 = vượt chi phí):"); print(piv.round(3).to_string())
print("\nt-stat:"); print(pivt.round(2).to_string())
print("\ntrung bình 7 cặp:"); print(piv.mean().round(3).to_string())

print()
print("="*120); print("B. QUÉT hold × move_z trên EURUSD (chi phí thấp nhất)"); print("="*120)
b = VC.load_bars("EURUSD","H1",start="2020-01-01")
rows=[]
for mz in (1.0,1.5,2.0,2.5,3.0):
    for h in (1,2,4,8):
        r = VC.conditional_reversal(b, hold=h, move_z=mz)
        if r.empty: continue
        lo = r[r["bucket"]=="VOL_THAP"]
        hi = r[r["bucket"]=="VOL_CAO"]
        if len(lo) and len(hi):
            rows.append({"move_z":mz,"hold":h,"n_thap":int(lo["n"].iloc[0]),
                "thap_bps":float(lo["fwd_bps"].iloc[0]),"thap_t":float(lo["t_stat"].iloc[0]),
                "thap_ratio":float(lo["ratio"].iloc[0]),
                "cao_bps":float(hi["fwd_bps"].iloc[0]),"cao_t":float(hi["t_stat"].iloc[0]),
                "chenh_lech":round(float(lo["fwd_bps"].iloc[0])-float(hi["fwd_bps"].iloc[0]),3)})
G=pd.DataFrame(rows); print(G.to_string(index=False))

print()
print("="*120); print("C. GỘP 7 CẶP — hold × move_z, chỉ nhóm VOL_THAP"); print("="*120)
rows=[]
for mz in (1.0,1.5,2.0,2.5):
    for h in (1,2,4,8):
        best=[]
        for sym in AP.FX_ALL:
            bb = VC.load_bars(sym,"H1",start="2020-01-01")
            r = VC.conditional_reversal(bb, hold=h, move_z=mz)
            if r.empty: continue
            lo=r[r["bucket"]=="VOL_THAP"]
            if len(lo): best.append({"sym":sym,"bps":float(lo["fwd_bps"].iloc[0]),
                                    "t":float(lo["t_stat"].iloc[0]),"ratio":float(lo["ratio"].iloc[0]),
                                    "n":int(lo["n"].iloc[0])})
        if best:
            d=pd.DataFrame(best)
            rows.append({"move_z":mz,"hold":h,"n_tb":int(d["n"].mean()),
                         "bps_tb":round(float(d["bps"].mean()),3),
                         "ratio_tb":round(float(d["ratio"].mean()),3),
                         "so_cap_duong":int((d["ratio"]>0).sum()),
                         "so_cap_vuot_1":int((d["ratio"]>1).sum()),
                         "t_min":round(float(d["t"].min()),2),"t_max":round(float(d["t"].max()),2)})
print(pd.DataFrame(rows).to_string(index=False))
print(f"\nelapsed {time.time()-t0:.0f}s")
