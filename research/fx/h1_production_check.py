"""Vòng 32 — xac minh module H1 production + log quyet dinh vao lenh."""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.h1 import cross_mean_reversion as XMR
from src.python.execution import decision_log as DL
pd.set_option("display.width",250,"display.max_columns",30)
DEV=pd.Timestamp("2024-01-01")

print("="*110); print("A. BACKTEST cau hinh Zheng Nan (window=HL×4,32 · vao 2σ)"); print("="*110)
tr = XMR.backtest()
d = XMR.daily_pnl(tr)
print(f"  {len(tr)} lenh · giu TB {tr['bars_held'].mean()/24:.2f} ngay · {len(tr)/6.5:.0f} lenh/nam")
print(f"  gross {tr['gross_bps'].mean():+.2f} · phi {tr['cost_bps'].mean():.2f} · swap {tr['swap_bps'].mean():.2f} · net {tr['net_bps'].mean():+.2f} bps")
print()
print(pd.DataFrame([XMR.stats(d[d.index<DEV],"FORM"),XMR.stats(d[d.index>=DEV],"OOS"),
                    XMR.stats(d,"ALL")]).to_string(index=False))
print()
by=d.groupby(d.index.year)
print("  theo nam (tong bps):"); print(by.sum().round(0).to_string())
print(f"  nam duong: {int((by.sum()>0).sum())}/{len(by)}")
print()
print("  ty le ly do thoat:"); print(tr["exit_reason"].value_counts().to_string())

print(); print("="*110); print("B. LOG QUYET DINH VAO LENH — quyet dinh live hien tai"); print("="*110)
decs = XMR.live_decisions()
n = DL.record_many(decs, strategy="CrossMeanReversion_H1")
print(f"  da ghi {n} quyet dinh vao logs/decisions/")
print()
for x in decs[:6]:
    print("   ", x.explain())
acts = pd.Series([x.action for x in decs]).value_counts()
print(f"\n  phan bo hanh dong: {acts.to_dict()}")

print(); print("="*110); print("C. DOC LAI SO + TRUY NGUOC"); print("="*110)
df = DL.load()
print(f"  so co {len(df)} dong")
s = DL.daily_summary()
print(f"\n  tom tat hom nay ({len(s)} cross):")
print(s.head(8).to_string(index=False) if len(s) else "  (trong)")
