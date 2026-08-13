"""Vòng 18 — TIN TỨC: nguồn nội ngày duy nhất có biên độ >> chi phí.
Đo hành vi giá quanh sự kiện đã LÊN LỊCH (biết trước thời điểm, không phải dự báo)."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.shared import fx_data as D, asset_profile as AP
pd.set_option("display.width",250,"display.max_columns",40)
DEV=pd.Timestamp("2024-01-01")

ev = pd.read_parquet("data/economic_calendar_events.parquet")
ev["time_utc"]=pd.to_datetime(ev["time_utc"])
ev = ev[ev["time_utc"]>=pd.Timestamp("2020-01-01")]
print("sự kiện 2020+:"); print(ev.groupby(["event","impact"]).size().to_string())
print(f"\ntổng {len(ev)} sự kiện\n")

# M30 để nhìn rõ quanh mốc tin
bars={}
for s in AP.FX_ALL:
    b=D.build_bars(D.load_m1(s),"M30"); b=b[b.index>="2020-01-01"]
    prof=AP.get(s); px=float(b["close"].median()); sp=float(b["spread_usd"].median())
    b.attrs["cost"]=(sp+prof.commission_price_units(px))/px*1e4
    bars[s]=b
print("chi phí khứ hồi (bps):", {s:round(bars[s].attrs['cost'],3) for s in bars})

def around(sym, times, pre=6, post=12):
    """Lợi nhuận log (bps) theo từng bước M30 quanh mốc tin. 0 = nến chứa mốc."""
    b=bars[sym]; c=np.log(b["close"])*1e4
    idx=b.index; out=[]
    for t in times:
        t=pd.Timestamp(t)
        pos=idx.searchsorted(t)
        if pos<pre+1 or pos+post>=len(idx): continue
        seg=c.iloc[pos-pre:pos+post+1].to_numpy()
        out.append(seg-seg[pre])          # neo về 0 tại nến chứa tin
    return np.array(out) if out else None

print()
print("="*118); print("A. ĐƯỜNG GIÁ TRUNG BÌNH QUANH TIN (bps, neo 0 tại nến tin) — EURUSD")
print("   cột = số nến M30 kể từ tin.  |t|>2 in đậm ý nghĩa")
print("="*118)
for evname in ["NFP","FOMC","CPI","ECB_RATE"]:
    tt=ev[ev["event"]==evname]["time_utc"]
    if len(tt)<10: continue
    A=around("EURUSD",tt)
    if A is None: continue
    m=A.mean(axis=0); t=m/(A.std(axis=0,ddof=1)/np.sqrt(len(A)))
    lbls=[f"{i-6:+d}" for i in range(len(m))]
    print(f"\n  {evname} (n={len(A)}):")
    print("    bước:", " ".join(f"{l:>6}" for l in lbls))
    print("    mean:", " ".join(f"{v:>6.1f}" for v in m))
    print("    t   :", " ".join(f"{v:>6.1f}" for v in t))

print()
print("="*118); print("B. BIÊN ĐỘ TUYỆT ĐỐI — tin có tạo dịch chuyển lớn hơn bình thường không?")
print("="*118)
for sym in ["EURUSD","USDJPY","GBPUSD"]:
    b=bars[sym]; r=(np.log(b["close"]).diff()*1e4).abs()
    base=float(r.median())
    row=[f"{sym} nền={base:.2f}"]
    for evname in ["NFP","FOMC","CPI"]:
        tt=ev[ev["event"]==evname]["time_utc"]
        if len(tt)<10: continue
        idx=b.index; vals=[]
        for t in tt:
            p=idx.searchsorted(pd.Timestamp(t))
            if 0<p<len(idx): vals.append(float(r.iloc[p]))
        if vals: row.append(f"{evname}={np.median(vals):.2f} ({np.median(vals)/base:.1f}x)")
    print("  "+"  ".join(row))

print()
print("="*118); print("C. CHIẾN LƯỢC: FADE dịch chuyển ngay sau tin (nến tin -> giữ N nến)")
print("="*118)
rows=[]
for evname in ["NFP","FOMC","CPI","ECB_RATE","ALL"]:
    tt = ev["time_utc"] if evname=="ALL" else ev[ev["event"]==evname]["time_utc"]
    if len(tt)<10: continue
    for hold in (1,2,4,8):
        allp=[]
        for sym in AP.FX_ALL:
            b=bars[sym]; c=np.log(b["close"])*1e4; idx=b.index; cost=b.attrs["cost"]
            for t in tt:
                p=idx.searchsorted(pd.Timestamp(t))
                if p<2 or p+hold>=len(idx): continue
                move=c.iloc[p]-c.iloc[p-1]          # dịch chuyển của nến tin
                fwd =c.iloc[p+hold]-c.iloc[p]
                allp.append(-np.sign(move)*fwd - cost)   # FADE, trừ chi phí
        if len(allp)>=60:
            a=np.array(allp); m=float(a.mean())
            rows.append({"event":evname,"hold_m30":hold,"n":len(a),"net_bps":round(m,3),
                         "t":round(m/(a.std(ddof=1)/np.sqrt(len(a))),2),
                         "hit":round(float((a>0).mean()),3)})
R=pd.DataFrame(rows); print(R.to_string(index=False))
print()
print("  --- chiều NGƯỢC LẠI (đi THEO dịch chuyển) ---")
print(R.assign(net_bps=-R["net_bps"], t=-R["t"]).to_string(index=False))
