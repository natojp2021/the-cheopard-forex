"""Vòng 3 / Bước 2 — MULTI-REGIME. Giả thuyết đặc tả trước từ Brière & Drut (Amundi WP-005-2009):
chiến lược ĐẢO VAI theo chế độ rủi ro. Họ đo carry(calm)/PPP(crisis) Sharpe 0,85/-0,48 -> 0,20/+1,09.
Ở đây kiểm: REVERSAL(vol thấp) / MOMENTUM(vol cao) trên cùng bộ máy cắt ngang.
Thước đo regime: biến động rổ tiền tệ (proxy VIX nội-FX; ta không có VIX)."""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_cross_section as XS
pd.set_option("display.width",250,"display.max_columns",30)
out = ROOT/"reports"/"fx_research"

R, costs = XS.pair_daily(start="2020-01-01"); F = XS.ccy_returns(R)
def sh(s):
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(252) if sd>0 else np.nan
def st(s,l): return XS.stats(s,l)

rev = XS.run_xs(F,costs,XS.XsConfig(21,21,3,3,sign=-1))["net_bps"]
mom = XS.run_xs(F,costs,XS.XsConfig(21,21,3,3,sign=+1))["net_bps"]

# regime: biến động rổ, ngưỡng PHÂN VỊ TRƯỢT nhân quả (dùng được ở live)
bvol = F.std(axis=1).rolling(21).mean()
thr  = bvol.shift(1).rolling(252, min_periods=126).quantile(0.80)
hi   = (bvol.shift(1) >= thr).reindex(rev.index).fillna(False)

print("="*118); print("A. TỪNG CHIẾN LƯỢC THEO CHẾ ĐỘ (vol rổ: top 20% trượt = 'CRISIS')"); print("="*118)
rows=[]
for tag,s in (("REVERSAL",rev),("MOMENTUM",mom)):
    for rt,m in (("CALM",~hi),("CRISIS",hi)):
        x=s[m]
        rows.append({"strategy":tag,"regime":rt,"n":len(x),"ann_pct":round(float(x.mean())*252/100,2),
                     "sharpe":round(sh(x),3),"hit":round(float((x>0).mean()),3)})
print(pd.DataFrame(rows).to_string(index=False))
print("\n  so sánh Brière & Drut: carry 0,85(calm)/0,20(crisis) · PPP -0,48(calm)/+1,09(crisis)")

# chiến lược CHUYỂN: reversal khi calm, momentum khi crisis
switch = rev.where(~hi, mom)
print(); print("="*118); print("B. SO SÁNH BỐN CẤU HÌNH — DEV / OOS tách riêng"); print("="*118)
rows=[]
for tag,s in (("REV thuần",rev),("MOM thuần",mom),
              ("SWITCH rev/mom",switch),("REV + nghỉ khi crisis",rev.where(~hi,0.0))):
    for lbl,x in (("DEV",s[s.index<XS.DEV_END]),("OOS",s[s.index>=XS.DEV_END]),("ALL",s)):
        d=st(x,f"{tag} {lbl}"); d["cfg"]=tag; d["win"]=lbl; rows.append(d)
T=pd.DataFrame(rows)
cols=["cfg","win","n_days","ann_ret_pct","ann_vol_pct","sharpe","sortino","max_dd_pct","calmar","hit_rate"]
print(T[cols].to_string(index=False))
T.to_csv(out/"xs_regime_switch.csv",index=False)

print(); print("="*118); print("C. TƯƠNG QUAN — điều kiện để đa dạng hoá có tác dụng (Olszweski & Zhou)"); print("="*118)
print(f"  corr(REV, MOM) = {rev.corr(mom):+.3f}   [theo xây dựng phải ≈ -1 vì cùng tín hiệu đảo dấu]")
print(f"  REV vs SWITCH  = {rev.corr(switch):+.3f}")

# kiểm định chuỗi: switch có thật sự khác REV về mặt thống kê không?
diff = (switch - rev).dropna()
tstat = float(diff.mean())/(float(diff.std(ddof=1))/np.sqrt(len(diff)))
print(f"  chênh lệch SWITCH-REV: {float(diff.mean())*252/100:+.2f}%/năm, t={tstat:+.2f}")
