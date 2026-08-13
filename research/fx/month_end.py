"""Vòng 4 — CHÂN THỨ HAI: dòng tái cân bằng cuối tháng.
Giả thuyết đặc tả trước: tái cân bằng hedge tiền tệ của tổ chức (hàng chục tỷ USD notional)
tập trung quanh London fix những ngày giao dịch cuối tháng. Cơ chế BẮT BUỘC, không thể tự dừng.
THIẾT KẾ GỌN: chỉ 8 phép thử trên RỔ (không quét 672 ô cặp×giờ như lần trước)."""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.d1 import currency_reversal as CR
pd.set_option("display.width",240,"display.max_columns",30)
DEV=pd.Timestamp("2024-01-01")

F, costs = CR.currency_returns(start="2020-01-01")
usd = F["USD"]                      # lợi nhuận USD (bps), đã chuẩn hoá tổng rổ = 0
idx = pd.DatetimeIndex(F.index)

# xếp hạng ngày trong tháng: rank_end=1 là ngày giao dịch CUỐI tháng
ym = idx.to_period("M")
rank_end = pd.Series(0, index=F.index); rank_start = pd.Series(0, index=F.index)
for _, g in pd.Series(idx, index=F.index).groupby(ym):
    rank_end.loc[g.index] = np.arange(len(g),0,-1)
    rank_start.loc[g.index] = np.arange(1,len(g)+1)

def sh(s):
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(252) if sd>0 else np.nan

print("="*112); print("A. LỢI NHUẬN USD THEO VỊ TRÍ NGÀY TRONG THÁNG (bps/ngày)"); print("="*112)
rows=[]
for k in range(1,6):
    m = rank_end==k
    x = usd[m]
    rows.append({"vi_tri":f"cuoi-{k}", "n":len(x), "mean_bps":round(float(x.mean()),3),
                 "t":round(float(x.mean())/(float(x.std(ddof=1))/np.sqrt(len(x))),2), "hit":round(float((x>0).mean()),3)})
for k in range(1,6):
    m = rank_start==k
    x = usd[m]
    rows.append({"vi_tri":f"dau-{k}", "n":len(x), "mean_bps":round(float(x.mean()),3),
                 "t":round(float(x.mean())/(float(x.std(ddof=1))/np.sqrt(len(x))),2), "hit":round(float((x>0).mean()),3)})
base = usd[(rank_end>5)&(rank_start>5)]
rows.append({"vi_tri":"giua-thang","n":len(base),"mean_bps":round(float(base.mean()),3),
             "t":round(float(base.mean())/(float(base.std(ddof=1))/np.sqrt(len(base))),2),"hit":round(float((base>0).mean()),3)})
print(pd.DataFrame(rows).to_string(index=False))

print(); print("="*112); print("B. CHIẾN LƯỢC: giữ USD trong N ngày cuối tháng (chi phí thật rổ 7 cặp)"); print("="*112)
# chi phí: 1 khứ hồi trên rổ, tỷ trọng đều 1/7 mỗi cặp
cost_basket = float((costs/7).sum())
res={}
for N in (1,2,3,5):
    for side,tag in ((+1,"LONG USD"),(-1,"SHORT USD")):
        m = rank_end<=N
        r = (side*usd).where(m, 0.0)
        # chi phí: vào 1 lần đầu cửa sổ, ra 1 lần cuối -> 1 khứ hồi/tháng
        entry = m & (~m.shift(1).fillna(False))
        r = r - cost_basket*entry.astype(float)
        res[f"{tag} N={N}"]=r
        for lbl,x in (("ALL",r),("DEV",r[r.index<DEV]),("OOS",r[r.index>=DEV])):
            a=x[x!=0]
            print(f"  {tag} N={N} {lbl:>3}: ann={float(x.mean())*252/100:+6.2f}%  sharpe={sh(x):+6.2f}  "
                  f"n_active={len(a):>4}  hit={float((a>0).mean()):.3f}" if len(a) else "")
        print()

print("="*112); print("C. ỨNG VIÊN TỐT NHẤT ghép với CHIẾN LƯỢC LÕI"); print("="*112)
core = CR.backtest(start="2020-01-01").net
best_key = max(res, key=lambda k: sh(res[k]))
leg2 = res[best_key].reindex(core.index).fillna(0.0)
print(f"  chân 2 tốt nhất: {best_key}  sharpe={sh(leg2):+.2f}")
print(f"  corr(lõi, chân2) = {core.corr(leg2):+.3f}   <- càng gần 0 càng tốt")
for w in (0.5,):
    comb = (1-w)*core + w*leg2
    for lbl,x in (("DEV",comb[comb.index<DEV]),("OOS",comb[comb.index>=DEV]),("ALL",comb)):
        print(f"  ghép 50/50 {lbl:>3}: ", CR.stats(x,lbl))
