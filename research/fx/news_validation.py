"""Vòng 19 — KIỂM ĐỊNH ứng viên M30 news-overreaction. Gộp về mức SỰ KIỆN."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.m30 import news_overreaction as NW
from src.python.research.validation import stress_testing as ST
pd.set_option("display.width",250,"display.max_columns",30)
DEV=pd.Timestamp("2024-01-01")

print("="*112); print("A. BASELINE — hold=4 M30 (2 giờ), 4 sự kiện lớn"); print("="*112)
ser, tr = NW.backtest()
print(f"  lệnh: {len(tr)} · sự kiện: {len(ser)}")
print(pd.DataFrame([NW.stats(ser[ser.index<DEV],"DEV"),NW.stats(ser[ser.index>=DEV],"OOS"),
                    NW.stats(ser,"ALL")]).to_string(index=False))

print(); print("="*112); print("B. QUÉT hold × ngưỡng cú sốc — báo cáo TOÀN BỘ"); print("="*112)
rows=[]
for hold in (1,2,4,6,8):
    for mz in (0.0,5.0,10.0,15.0):
        s,_ = NW.backtest(NW.Config(hold_bars=hold, min_shock_bps=mz))
        if len(s)<40: continue
        d=NW.stats(s,"ALL"); d.update({"hold":hold,"min_shock":mz,
            "DEV_t":NW.stats(s[s.index<DEV],"d").get("t"),"OOS_t":NW.stats(s[s.index>=DEV],"o").get("t")})
        rows.append(d)
G=pd.DataFrame(rows)
print(G[["hold","min_shock","n","per_year","net_bps","t","ann_pct","sharpe","hit","DEV_t","OOS_t"]].to_string(index=False))

print(); print("="*112); print("C. THEO LOẠI SỰ KIỆN (hold=4)"); print("="*112)
for e in ["NFP","FOMC","CPI","ECB_RATE"]:
    s,_=NW.backtest(NW.Config(events=(e,)))
    if len(s)>=20:
        st=NW.stats(s,e); print(f"  {e:<10} n={st['n']:>3} net={st['net_bps']:+7.3f} t={st['t']:+5.2f} "
                                f"ann={st['ann_pct']:+6.3f}% sharpe={st['sharpe']:+.3f} hit={st['hit']:.3f}")

print(); print("="*112); print("D. STRESS CHI PHÍ — spread sau tin giãn mạnh, phải chịu được"); print("="*112)
for k in (1,2,3,5,8):
    s,_=NW.backtest(NW.Config(cost_multiplier=k))
    st=NW.stats(s,"")
    print(f"  chi phí ×{k}: net={st['net_bps']:+7.3f} bps  t={st['t']:+5.2f}  ann={st['ann_pct']:+6.3f}%  sharpe={st['sharpe']:+.3f}")

print(); print("="*112); print("E. CONTROL — cùng số lệnh, cùng cặp, nhưng thời điểm NGẪU NHIÊN"); print("="*112)
bars,costs = NW.load_panel()
real,_ = NW.backtest()
n_ev = len(real)
allidx = bars["EURUSD"].index
rng=np.random.default_rng(3); ctl=[]
for k in range(200):
    fake = pd.DatetimeIndex(sorted(rng.choice(allidx[10:-10], size=n_ev, replace=False)))
    t2 = NW.generate_trades(bars,costs,fake,NW.Config())
    s2 = NW.event_portfolio(t2)
    if len(s2)>=30: ctl.append(float(s2.mean()))
ctl=np.array(ctl); rm=float(real.mean())
print(f"  control net_bps: p05={np.percentile(ctl,5):+.3f} p50={np.percentile(ctl,50):+.3f} p95={np.percentile(ctl,95):+.3f}")
print(f"  THẬT           : {rm:+.3f}  ->  phân vị {float((ctl<rm).mean()):.1%}  p={1-float((ctl<rm).mean()):.4f}")

print(); print("="*112); print("F. OUTLIER — vài sự kiện có gánh toàn bộ không?"); print("="*112)
o=ST.outlier_removal_test(list(real.to_numpy()), n_remove=5)
print(f"  5 sự kiện tốt nhất = {o['pct_of_profit_from_outliers']*100:.1f}% lợi nhuận · đổi dấu: {o['sign_flipped_to_loss']}")
print(f"  bỏ đi -> tổng {o['total_return_after']:.1f} bps (trước {o['total_return_before']:.1f})")

print(); print("="*112); print("G. THEO NĂM"); print("="*112)
by=real.groupby(real.index.year)
print(pd.DataFrame({"n":by.size(),"net_bps":by.mean().round(3),
                    "tong_bps":by.sum().round(1)}).to_string())
