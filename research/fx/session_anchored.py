"""Vòng 14 — CẮT NGANG NEO PHIÊN. Giả thuyết cơ chế, không phải dò lưới.

Cơ chế (Breedon & Ranaldo SNB 2011, áp cho cược TƯƠNG ĐỐI thay vì cược hướng):
phiên Á thanh khoản mỏng -> dịch chuyển ở đó phần lớn là dòng lệnh, không phải
thông tin. Khi thanh khoản châu Âu vào, giá hồi. Cắt ngang: đồng tăng mạnh nhất
trong phiên Á sẽ kém hơn trong phiên London.

CHỈ 10 phép thử (5 cửa sổ × 2 chiều), MỘT lượt khứ hồi/ngày."""
import sys, io, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.research import fx_intraday_xs as IX
pd.set_option("display.width",250,"display.max_columns",30)
out = ROOT/"reports"/"fx_research"
DEV=pd.Timestamp("2024-01-01")

F, costs = IX.currency_bars("H1", start="2020-01-01")
F = F.copy(); F["__h"]=F.index.hour; F["__d"]=F.index.normalize()
cols=[c for c in F.columns if not c.startswith("__")]

def session_sum(h0,h1):
    """Tổng lợi nhuận đồng tiền trong [h0,h1) UTC theo từng NGÀY."""
    m=(F["__h"]>=h0)&(F["__h"]<h1)
    return F[m].groupby("__d")[cols].sum()

# cửa sổ: (ten, gio_tin_hieu, gio_giao_dich)
WINDOWS = [
    ("ASIA→LONDON",        (0,7),  (7,12)),
    ("ASIA→LDN+OVERLAP",   (0,7),  (7,16)),
    ("LONDON→OVERLAP",     (7,12), (12,16)),
    ("LONDON→OVL+NY",      (7,12), (12,20)),
    ("OVERLAP→NY",         (12,16),(16,20)),
]
def evaluate(sig_win, trade_win, sign, n_leg=3):
    S = session_sum(*sig_win); R = session_sum(*trade_win)
    idx = S.index.intersection(R.index)
    S,R = S.loc[idx], R.loc[idx]
    vol = R.rolling(60,min_periods=30).std().shift(1)
    pnl=[]
    Sv,Rv,Vv = (sign*S).to_numpy(), R.to_numpy(), vol.to_numpy()
    for i in range(len(idx)):
        s,v = Sv[i], Vv[i]
        if np.isnan(s).any() or np.isnan(v).sum()>2: continue
        o=np.argsort(-s); w=np.zeros(len(cols))
        for grp,sg in ((o[:n_leg],1.0),(o[-n_leg:],-1.0)):
            iv=np.nan_to_num(1.0/np.where(np.isfinite(v[grp])&(v[grp]>0),v[grp],np.nan))
            if iv.sum()>0: w[grp]=sg*iv/iv.sum()
        pnl.append((idx[i], float(np.dot(w,Rv[i]))))
    if len(pnl)<100: return None
    ser = pd.Series([p for _,p in pnl], index=[t for t,_ in pnl])
    return ser

print("="*126); print("A. CẮT NGANG NEO PHIÊN — 10 phép thử, 1 lượt khứ hồi/ngày (chi phí 1,657 bps)")
print("="*126)
rows={}
for name,sw,tw in WINDOWS:
    for sign,tag in ((-1,"REV"),(+1,"MOM")):
        ser = evaluate(sw,tw,sign)
        if ser is None: continue
        net = ser - IX.BASKET_COST_BPS
        t = float(ser.mean())/(float(ser.std(ddof=1))/np.sqrt(len(ser)))
        rows[f"{name} {tag}"]=net
        print(f"  {name:<20} {tag}: n={len(ser):>4}  gross={float(ser.mean()):+7.3f} bps  t={t:+5.2f}  "
              f"ratio={float(ser.mean())/IX.BASKET_COST_BPS:+6.2f}  net={float(net.mean()):+7.3f}  "
              f"ann={float(net.mean())*252/100:+6.2f}%  hit={float((net>0).mean()):.3f}")

print()
print("="*126); print("B. ỨNG VIÊN TỐT NHẤT — tách DEV/OOS"); print("="*126)
def sh(s):
    sd=float(s.std(ddof=1)); return float(s.mean())/sd*np.sqrt(252) if sd>0 else np.nan
best = sorted(rows.items(), key=lambda kv: -sh(kv[1]))[:4]
for name,net in best:
    d,o = net[net.index<DEV], net[net.index>=DEV]
    print(f"  {name:<26} ALL sharpe={sh(net):+6.3f} ann={float(net.mean())*252/100:+6.2f}%  |  "
          f"DEV {sh(d):+6.3f}  OOS {sh(o):+6.3f}")

print()
print("="*126); print("C. GỘP các cửa sổ KHÔNG chồng lấn (danh mục nội ngày)"); print("="*126)
# ASIA→LONDON và OVERLAP→NY không chồng thời gian -> có thể chạy song song
for combo in [("ASIA→LONDON REV","OVERLAP→NY REV"),("ASIA→LONDON REV","LONDON→OVERLAP REV"),
              ("ASIA→LDN+OVERLAP REV","OVERLAP→NY REV")]:
    if all(c in rows for c in combo):
        a,b = rows[combo[0]], rows[combo[1]]
        idx=a.index.intersection(b.index)
        comb=(0.5*a.reindex(idx)+0.5*b.reindex(idx)).dropna()
        d,o=comb[comb.index<DEV],comb[comb.index>=DEV]
        print(f"  {combo[0]} + {combo[1]}")
        print(f"     corr={a.reindex(idx).corr(b.reindex(idx)):+.3f}  ALL sharpe={sh(comb):+.3f} "
              f"ann={float(comb.mean())*252/100:+.2f}%  DEV {sh(d):+.3f}  OOS {sh(o):+.3f}")
