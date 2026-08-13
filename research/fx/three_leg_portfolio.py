"""Vòng 35 — DANH MỤC BA CHÂN. Cơ sở: Burnside/Eichenbaum/Rebelo (NBER w16942, tài
liệu người dùng vừa bổ sung) — xác nhận ĐỘC LẬP THỨ BA cho danh mục 50-50:

  "An equally-weighted combination of the two currency strategies, which we call the
   '50-50 strategy', has an average payoff of 4.5 percent, a standard deviation of
   4.6 percent and a Sharpe ratio of 0.98. The high Sharpe ratio of the combined
   strategy reflects the low correlation between the payoffs to the two strategies."

Và họ mô tả đúng cơ chế `combined()` của ta:
  "When the two underlying strategies agree on the sign... the net position is ±1/n.
   When they disagree... the net position for that currency is ZERO."

Ba nguồn độc lập cùng kết luận (Olszweski&Zhou 0,79→0,98 · Burnside 0,41/0,62→0,98
· ta 0,576/0,151→0,721). Câu hỏi: thêm chân H1 cross vào thì sao?
"""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.d1 import currency_reversal as CR, currency_carry as CY
from src.python.strategies.h1 import cross_mean_reversion as XMR
pd.set_option("display.width",250,"display.max_columns",30)
t0=time.time(); DEV=pd.Timestamp("2024-01-01")

# hai chan D1 (bps/ngay, don vi rui ro 1)
d1_net,_,_ = CY.combined(start="2020-01-01", weight_reversal=0.5)
# chan H1 cross (bps/ngay)
h1_tr = XMR.backtest()
h1_net = XMR.daily_pnl(h1_tr)

idx = d1_net.index.intersection(h1_net.index)
A = d1_net.reindex(idx).fillna(0.0)
B = h1_net.reindex(idx).fillna(0.0)
# chuan hoa VE CUNG BIEN DONG truoc khi ghep — neu khong, chan bien dong lon se ap dao
A_n = A/float(A.std(ddof=1)); B_n = B/float(B.std(ddof=1))

def sh(s):
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(252) if sd>0 else np.nan
def st(s,l):
    cum=s.cumsum(); dd=cum.cummax()-cum
    return {"cfg":l,"ALL":round(sh(s),3),"FORM":round(sh(s[s.index<DEV]),3),
            "OOS":round(sh(s[s.index>=DEV]),3),"maxDD_sd":round(float(dd.max()),1)}

print("="*112); print("A. TƯƠNG QUAN — điều kiện để đa dạng hoá có tác dụng"); print("="*112)
print(f"  corr(danh mục D1 hai chân, H1 cross) = {A.corr(B):+.3f}")
print(f"  Sharpe riêng: D1 {sh(A):+.3f} · H1 {sh(B):+.3f}")

print(); print("="*112); print("B. GHÉP — chuẩn hoá cùng biến động, chia đều (Burnside/Olszweski)"); print("="*112)
rows=[st(A_n,"chỉ D1 (2 chân)"), st(B_n,"chỉ H1 cross")]
for w in (0.25,0.4,0.5,0.6,0.75):
    rows.append(st(w*A_n+(1-w)*B_n, f"{w:.0%} D1 / {1-w:.0%} H1"))
print(pd.DataFrame(rows).to_string(index=False))

print(); print("="*112); print("C. BA CHÂN RIÊNG (reversal · carry · cross) — chia đều đúng nghĩa"); print("="*112)
F,_ = CR.currency_returns(start="2020-01-01")
rev = CR.backtest(start="2020-01-01").net.reindex(idx).fillna(0.0)
car = CY.backtest(start="2020-01-01").net.reindex(idx).fillna(0.0)
legs = {"reversal":rev, "carry":car, "cross_H1":B}
N = {k: v/float(v.std(ddof=1)) for k,v in legs.items()}
print("  ma trận tương quan:")
print(pd.DataFrame(legs).corr().round(3).to_string())
eq = sum(N.values())/len(N)
print()
print(pd.DataFrame([st(N["reversal"],"reversal"),st(N["carry"],"carry"),
                    st(N["cross_H1"],"cross_H1"),st(eq,"BA CHÂN chia đều")]).to_string(index=False))
print()
by=eq.groupby(eq.index.year)
print("  ba chân theo năm (Sharpe):")
print(by.apply(lambda s: round(sh(s),2)).to_string())
print(f"  năm dương: {int((by.sum()>0).sum())}/{len(by)}")
print(f"\nelapsed {time.time()-t0:.0f}s")
