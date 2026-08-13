"""Vòng 33 — hai kiểm định từ tài liệu MỚI người dùng bổ sung.

1) LEVICH & THOMAS (NBER 1991, SSRN-id226734) — bootstrap bằng XÁO TRỘN CHUỖI GIÁ:
   "each new series constructed from random reordering [of the original series]...
    apply mechanical trading rules for each new series"
   Mạnh hơn control ngẫu-nhiên-hoá-thời-điểm: nó phá CẤU TRÚC CHUỖI (mean reversion)
   mà GIỮ NGUYÊN phân phối lợi nhuận, biến động, đuôi. Nếu chiến lược vẫn lãi trên
   chuỗi xáo trộn thì lợi nhuận đến từ chính LUẬT (vd luật quay-vào-dải tạo thiên
   lệch tổng hợp), không từ mean reversion thật.

2) MENKHOFF et al. (BIS WP366) — cảnh báo: "danh mục momentum FX lệch mạnh về đồng
   tiền PHỤ có chi phí cao, chiếm ~50% lợi nhuận". Kiểm cùng thứ trên cross của ta:
   lợi nhuận có tập trung vào cross ĐẮT không?
"""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_cross_pairs as CX
from src.python.strategies.h1 import cross_mean_reversion as XMR
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time()

P, SPECS = CX.build_crosses("H1", start="2020-01-01")
cfg = XMR.Config().to_cx()

print("="*112)
print("1. LEVICH-THOMAS BOOTSTRAP — xáo trộn chuỗi giá, chạy lại luật")
print("   Chuỗi xáo trộn giữ nguyên phân phối/biến động, MẤT cấu trúc chuỗi.")
print("="*112)
def run_on(series_map):
    best=[]
    for name, s in series_map.items():
        for t in CX.simulate(name, s, SPECS[name], cfg):
            best.append(t.gross_bps - t.cost_bps)
    return np.array(best)

real = run_on({n: P[n] for n in P.columns})
print(f"  THẬT: {len(real)} lệnh · gross-net-phí trung bình {real.mean():+.3f} bps")

rng = np.random.default_rng(1991)
boot=[]
for k in range(60):
    shuffled={}
    for n in P.columns:
        s=P[n].dropna()
        r=np.diff(np.log(s.to_numpy()))
        rng.shuffle(r)                       # phá cấu trúc chuỗi, giữ phân phối
        px=np.exp(np.concatenate([[np.log(s.iloc[0])], np.log(s.iloc[0])+np.cumsum(r)]))
        shuffled[n]=pd.Series(px, index=s.index)
    b=run_on(shuffled)
    if len(b)>50: boot.append(float(b.mean()))
boot=np.array(boot)
pct=float((boot<real.mean()).mean())
print(f"  xáo trộn ({len(boot)} lần): p05={np.percentile(boot,5):+.3f} "
      f"p50={np.percentile(boot,50):+.3f} p95={np.percentile(boot,95):+.3f}")
print(f"  -> phân vị của THẬT: {pct:.1%}   p = {1-pct:.4f}")
print(f"  {'PASS — lợi nhuận đến từ cấu trúc chuỗi, không từ luật' if pct>0.95 else 'CẢNH BÁO — luật tự tạo lợi nhuận trên chuỗi ngẫu nhiên'}")

print()
print("="*112)
print("2. MENKHOFF — lợi nhuận có tập trung vào cross ĐẮT không?")
print("="*112)
tr = XMR.backtest()
g = tr.groupby("cross").agg(n=("net_bps","size"), net=("net_bps","mean"),
                            total_move=("net_bps","sum"), cost_bps=("cost_bps","mean"))
g["phi_pip"]=[SPECS[c].spread_pips for c in g.index]
g=g.sort_values("phi_pip")
print(g.round(2).to_string())
corr=float(np.corrcoef(g["phi_pip"], g["net"])[0,1])
print(f"\n  tương quan(spread cross, net/lệnh) = {corr:+.3f}")
total_move=g["tong"].sum()
re=g[g["phi_pip"]<=1.6]; passed=g[g["phi_pip"]>1.6]
print(f"  cross RẺ  (spread ≤1,6 pip, n={len(re)}): {float(re['tong'].sum()):+.0f} bps "
      f"= {float(re['tong'].sum())/tong*100:.0f}% tổng lợi nhuận")
print(f"  cross ĐẮT (spread >1,6 pip, n={len(dat)}): {float(dat['tong'].sum()):+.0f} bps "
      f"= {float(dat['tong'].sum())/tong*100:.0f}%")
print(f"\n  {'AN TOÀN — lợi nhuận không phụ thuộc cross đắt' if corr<0.2 else 'CẢNH BÁO — đúng bẫy Menkhoff mô tả'}")
print(f"\nelapsed {time.time()-t0:.0f}s")
