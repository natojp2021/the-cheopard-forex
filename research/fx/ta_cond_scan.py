"""Vong 44 — TA CO DIEU KIEN + PHA VO BIEN PHIEN tren EU/GU."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_ta_lab as TA, fx_ta_conditional as TC
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); out=ROOT/"reports"/"fx_research"
rows=[]
def add(bars,pos,label):
    try:
        r=TA.simulate(bars,pos,name=label); d=TA.row(r); d["họ"]=label; rows.append(d)
    except Exception as e: print(f"   {label}: {type(e).__name__}: {e}")

for tf in ("M30","H1","H4"):
    print(f"-- {tf}", flush=True)
    for sym in TA.TIER1:
        b=TA.load(sym,tf,start="2020-01-01")
        bh=TA.load(sym,"H4" if tf!="H4" else "D1",start="2020-01-01")
        base_rsi=TA.sig_rsi_mr(b); base_bb=TA.sig_bb_mr(b)
        # A. dieu kien hoa
        add(b,base_rsi,"rsi_goc"); add(b,base_bb,"bb_goc")
        for ses in (("LONDON",),("OVERLAP",),("ASIA",),("LONDON","OVERLAP")):
            tag="+".join(s[:3] for s in ses)
            add(b,TC.gate_session(b,base_bb,ses),f"bb_phien_{tag}")
        add(b,TC.gate_vol_regime(b,base_bb,low=True),"bb_vol_THAP")
        add(b,TC.gate_vol_regime(b,base_bb,low=False),"bb_vol_CAO")
        add(b,TC.gate_htf_range(b,base_bb),"bb_adx<25")
        add(b,TC.gate_htf_range(b,TC.gate_vol_regime(b,base_bb,low=True)),"bb_volTHAP+adx")
        add(b,TC.sig_mtf_mr(b,bh),"bb_mtf")
        # confluence
        for need in (2,3):
            add(b,TC.sig_confluence_mr(b,need=need),f"hop_luu_{need}/3")
        # B. pha vo bien phien
        for rs,ts in (("ASIA","LONDON"),("ASIA","OVERLAP"),("LONDON","OVERLAP")):
            for buf in (0.0,0.25):
                add(b,TC.sig_session_breakout(b,range_session=rs,trade_session=ts,buffer_atr=buf),
                    f"pha_{rs[:3]}->{ts[:3]}_b{buf}")
        add(b,TC.sig_prev_day_breakout(b),"pha_ngay_truoc")

T=pd.DataFrame(rows); T.to_csv(out/"ta_conditional_scan.csv",index=False)
print(); print("="*140); print("TOAN BO"); print("="*140)
print(T.sort_values("ALL",ascending=False).to_string(index=False))
print(); print("="*140); print("CONG: FORM>0 va OOS>0 va ALL>0,5  (chat hon vong 43 vi so phep thu da tang)"); print("="*140)
g=T[(T["FORM"].fillna(-9)>0)&(T["OOS"].fillna(-9)>0)&(T["ALL"].fillna(-9)>0.5)]
print(g.sort_values("ALL",ascending=False).to_string(index=False) if len(g) else "  KHONG CO")
print(); print(f"tong phep thu vong nay: {len(T)}")
print("theo ho (Sharpe ALL trung binh):")
print(T.groupby("họ")["ALL"].agg(["mean","max"]).round(3).sort_values("mean",ascending=False).head(14).to_string())
print(f"\nelapsed {time.time()-t0:.0f}s")
