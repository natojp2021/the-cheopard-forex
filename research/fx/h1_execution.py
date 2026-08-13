"""Vòng 5 — TẦNG THỰC THI H1. Câu hỏi: tái cân bằng vào GIỜ H1 nào?
Đây là tối ưu CHI PHÍ (spread đo được), không phải fitting tín hiệu — spread theo giờ
là đặc tính vi cấu trúc ổn định, không phải một mẫu hình lợi nhuận."""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.shared import fx_data as D, asset_profile as AP
pd.set_option("display.width",250,"display.max_columns",30)

print("="*120); print("SPREAD THEO GIỜ UTC (pip trung vị, H1, 2020+) — cột cuối = chi phí rổ 7 cặp")
print("="*120)
tab={}
for sym in AP.FX_ALL:
    m1=D.load_m1(sym); b=D.build_bars(m1,"H1"); b=b[b.index>="2020-01-01"]
    pip=AP.get(sym).pip
    tab[sym]=(b["spread_usd"]/pip).groupby(b.index.hour).median()
S=pd.DataFrame(tab)
# chi phí rổ: tỷ trọng đều, quy về bps
basket_bps=[]
for h in S.index:
    best=0.0
    for sym in AP.FX_ALL:
        p=AP.get(sym); m1=D.load_m1(sym); b=D.build_bars(m1,"H1"); b=b[b.index>="2020-01-01"]
        px=float(b["close"].median()); sp=float(S.loc[h,sym])*p.pip
        best+=(sp+p.commission_price_units(px))/px*1e4/7
    basket_bps.append(best)
S["ROTHOP_bps"]=basket_bps
print(S.round(3).to_string())
best=S["ROTHOP_bps"].idxmin(); worst=S["ROTHOP_bps"].idxmax()
print()
print(f"  GIỜ RẺ NHẤT : {best:02d}:00 UTC  -> {S.loc[best,'ROTHOP_bps']:.4f} bps/khứ hồi rổ")
print(f"  GIỜ ĐẮT NHẤT: {worst:02d}:00 UTC  -> {S.loc[worst,'ROTHOP_bps']:.4f} bps  "
      f"(đắt hơn {S.loc[worst,'ROTHOP_bps']/S.loc[best,'ROTHOP_bps']:.2f} lần)")
print()
print("  TIẾT KIỆM mỗi năm nếu thực thi ở giờ rẻ thay vì giờ đắt:")
n_rb=252/21
print(f"    {n_rb:.0f} lần tái cân bằng/năm × ({S.loc[worst,'ROTHOP_bps']-S.loc[best,'ROTHOP_bps']:.4f} bps) "
      f"= {n_rb*(S.loc[worst,'ROTHOP_bps']-S.loc[best,'ROTHOP_bps'])/100:.3f}%/năm")
print()
print("  Xếp hạng 6 giờ rẻ nhất (dùng làm cửa sổ thực thi hợp lệ):")
print(S["ROTHOP_bps"].nsmallest(6).round(4).to_string())
