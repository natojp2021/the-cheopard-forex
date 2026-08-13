"""fx_volume_conditioned.py — đảo chiều CÓ ĐIỀU KIỆN KHỐI LƯỢNG, khung H1/M30.

VÌ SAO HƯỚNG NÀY, SAU KHI SÁU HƯỚNG NỘI NGÀY ĐÃ ĐỔ
====================================================
Đã bác bỏ ở khung nội ngày, có số liệu:
    price-action families (8)      28/33 NO_INFORMATION
    hiệu ứng fix theo giờ          drift ≈ 1 lượt khứ hồi, DSR = 0,0000
    RSI-diff pairs (IEEE)          không đạt, chính tác giả báo
    ML lọc lệnh                    < 60% CV, OOS bất định
    cắt ngang cuộn H1              |t| max 1,75 trên 72 phép thử
    cắt ngang neo phiên            gross 0,1-0,36 bps vs chi phí 1,657 bps

Tất cả sáu hướng trên chỉ dùng **GIÁ**. Nhưng dữ liệu có một cột chưa ai đụng tới:
`n_tick` — số tick trong mỗi nến, tức TICK VOLUME. Đây đúng là đại lượng MT5 cấp ở
live (`tick_volume`), nên dùng nó không phải xấp xỉ mà là parity.

CƠ CHẾ — Campbell, Grossman & Wang (1993)
==========================================
"Trading Volume and Serial Correlation in Stock Returns", *QJE* 108(4).

Luận điểm cốt lõi: **khối lượng phân biệt được hai loại dịch chuyển giá**.
  * Dịch chuyển do THÔNG TIN → giá đi tới giá trị mới và Ở LẠI đó
  * Dịch chuyển do THANH KHOẢN (ai đó cần thoát vị thế gấp) → người tạo lập yêu
    cầu nhượng bộ giá để hấp thụ, rồi giá HỒI khi áp lực qua đi

Hai loại này trông giống hệt nhau nếu chỉ nhìn giá. Khối lượng tách chúng ra: giao
dịch thanh khoản đòi nhượng bộ giá và đi kèm khối lượng **thấp bất thường** so với
độ lớn dịch chuyển — không ai muốn nhận phía bên kia.

    dịch chuyển lớn + khối lượng THẤP   -> thanh khoản  -> ĐẢO CHIỀU
    dịch chuyển lớn + khối lượng CAO    -> thông tin    -> KHÔNG fade

Đây là lý do có nội dung để kỳ vọng một tín hiệu MẠNH HƠN đảo chiều thuần tuý:
đảo chiều thuần trộn lẫn hai nhóm và bị nhóm "thông tin" kéo về 0. Điều đó khớp
chính xác với thứ đo được ở `fx_intraday_xs`: đảo chiều nội ngày có dấu ĐÚNG nhưng
độ lớn quá nhỏ.

Bằng chứng ngoại suy sang FX: Chordia/Roll/Subrahmanyam và các nghiên cứu vi cấu
trúc FX cho thấy dòng lệnh giải thích phần lớn biến động tỷ giá ngắn hạn — đó là
cùng một cơ chế nhìn từ góc khác.

⚠️ GIỚI HẠN CỦA TICK VOLUME
============================
Tick volume KHÔNG phải khối lượng thật (FX giao ngay không có sổ lệnh tập trung).
Nó đếm số lần báo giá thay đổi. Tương quan với khối lượng thật thường cao (nhiều
nghiên cứu báo 0,8-0,9 trên FX majors) nhưng nó cũng phản ánh **hoạt động báo giá**
— tăng khi thị trường căng thẳng kể cả khi không ai giao dịch. Phải chuẩn hoá theo
chính giờ trong ngày, nếu không sẽ chỉ đo lại cấu trúc phiên đã biết.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.python.shared import asset_profile as AP
from src.python.shared import fx_data as D

DEV_END = pd.Timestamp("2024-01-01")


# ═══════════════════════════════════════════════════════ dữ liệu + chuẩn hoá
def load_bars(symbol: str, timeframe: str = "H1",
              start: str = "2020-01-01") -> pd.DataFrame:
    """Nến kèm hai đại lượng đã CHUẨN HOÁ THEO GIỜ TRONG NGÀY.

    Chuẩn hoá theo giờ là bắt buộc, không phải tinh chỉnh: cả khối lượng lẫn biên
    độ đều có chu kỳ ngày rất mạnh (biên độ giờ 13-14 UTC gấp 3-4 lần giờ 21-23).
    Không chuẩn hoá thì "khối lượng cao" chỉ có nghĩa là "đang trong phiên London",
    và ta sẽ đo lại cấu trúc phiên đã biết thay vì đo thông tin mới.

    Cửa sổ chuẩn hoá 60 ngày TRƯỢT và `.shift(1)` — nhân quả, dùng được ở live.
    """
    m1 = D.load_m1(symbol)
    b = D.build_bars(m1, timeframe)
    b = b[b.index >= start].copy()
    prof = AP.get(symbol)

    b["ret_bps"] = np.log(b["close"]).diff() * 1e4
    b["range_bps"] = (b["high"] - b["low"]) / b["close"] * 1e4
    b["hour"] = b.index.hour

    n_per_day = {"H1": 24, "M30": 48, "M15": 96}.get(timeframe, 24)
    win = 60 * n_per_day

    def _norm(col: str) -> pd.Series:
        g = b.groupby("hour")[col]
        med = g.transform(lambda s: s.shift(1).rolling(60, min_periods=20).median())
        return b[col] / med.replace(0, np.nan)

    b["vol_rel"] = _norm("volume") if "volume" in b else np.nan
    b["range_rel"] = _norm("range_bps")
    # Độ lớn dịch chuyển chuẩn hoá theo biến động gần đây của chính nó.
    sd = b["ret_bps"].shift(1).rolling(win // 4, min_periods=100).std()
    b["ret_z"] = b["ret_bps"] / sd

    px = float(b["close"].median())
    sp = float(b["spread_usd"].median())
    b.attrs["cost_1rt_bps"] = (sp + prof.commission_price_units(px)) / px * 1e4
    b.attrs["symbol"] = symbol
    return b.dropna(subset=["ret_bps"])


# ═══════════════════════════════════════════════════════ đo sức mạnh tín hiệu
@dataclass
class VolResult:
    symbol: str
    timeframe: str
    bucket: str
    n: int
    fwd_bps: float          # lợi nhuận theo chiều FADE (ngược dịch chuyển)
    t_stat: float
    cost_bps: float
    ratio: float
    hit: float


def conditional_reversal(b: pd.DataFrame, *, hold: int = 1,
                         move_z: float = 1.5,
                         vol_q: Tuple[float, float] = (0.33, 0.67)
                         ) -> pd.DataFrame:
    """Đo lợi nhuận của việc FADE một dịch chuyển lớn, tách theo NHÓM KHỐI LƯỢNG.

    Điều kiện kích hoạt: |ret_z| >= `move_z` (dịch chuyển lớn so với biến động gần
    đây của chính nến đó). Với mỗi nến thoả, đo lợi nhuận `hold` nến kế tiếp theo
    chiều NGƯỢC dịch chuyển.

    Dự đoán của Campbell-Grossman-Wang, ghi TRƯỚC khi nhìn số:
        khối lượng THẤP  -> fade CÓ LÃI  (dịch chuyển do thanh khoản)
        khối lượng CAO   -> fade LỖ      (dịch chuyển do thông tin)
    Nếu cả hai nhóm giống nhau thì khối lượng không mang thông tin và giả thuyết
    bị bác bỏ — đó là kết quả có giá trị ngang một kết quả dương.
    """
    if "vol_rel" not in b or b["vol_rel"].isna().all():
        return pd.DataFrame()
    fwd = b["ret_bps"].shift(-1).rolling(hold).sum().shift(-(hold - 1))
    trig = b["ret_z"].abs() >= move_z
    side = -np.sign(b["ret_z"])                  # fade
    pnl = side * fwd

    lo, hi = b["vol_rel"].quantile(vol_q[0]), b["vol_rel"].quantile(vol_q[1])
    bucket = pd.Series(np.where(b["vol_rel"] <= lo, "VOL_THAP",
                       np.where(b["vol_rel"] >= hi, "VOL_CAO", "VOL_TB")),
                       index=b.index)

    df = pd.DataFrame({"pnl": pnl, "bucket": bucket})[trig].dropna()
    if len(df) < 50:
        return pd.DataFrame()

    cost = float(b.attrs.get("cost_1rt_bps", 1.0))
    rows = []
    for name, grp in df.groupby("bucket"):
        x = grp["pnl"]
        if len(x) < 30:
            continue
        m = float(x.mean())
        rows.append(VolResult(
            symbol=b.attrs.get("symbol", "?"), timeframe="", bucket=name,
            n=len(x), fwd_bps=round(m, 4),
            t_stat=round(m / (float(x.std(ddof=1)) / np.sqrt(len(x))), 2),
            cost_bps=round(cost, 4), ratio=round(m / cost, 3),
            hit=round(float((x > 0).mean()), 4)).__dict__)
    # cả rổ, không tách nhóm — để thấy tách nhóm có thêm gì không
    x = df["pnl"]
    m = float(x.mean())
    rows.append(VolResult(b.attrs.get("symbol", "?"), "", "TAT_CA", len(x),
                          round(m, 4),
                          round(m / (float(x.std(ddof=1)) / np.sqrt(len(x))), 2),
                          round(cost, 4), round(m / cost, 3),
                          round(float((x > 0).mean()), 4)).__dict__)
    return pd.DataFrame(rows)


def build_signal(b: pd.DataFrame, *, move_z: float, vol_max_q: float,
                 hold: int) -> pd.Series:
    """Chuỗi vị thế (+1/−1/0) của luật: fade dịch chuyển lớn trên khối lượng thấp.

    Ngưỡng khối lượng là phân vị TRƯỢT nhân quả, không phải phân vị toàn mẫu —
    bản toàn mẫu dùng thông tin tương lai và không chạy được ở live.
    """
    thr = b["vol_rel"].shift(1).rolling(2000, min_periods=500).quantile(vol_max_q)
    trig = (b["ret_z"].abs() >= move_z) & (b["vol_rel"] <= thr)
    side = (-np.sign(b["ret_z"])).where(trig, 0.0).fillna(0.0)
    # giữ `hold` nến: lan truyền vị thế, không chồng lệnh mới lên lệnh cũ
    pos = side.copy()
    if hold > 1:
        pos = side.replace(0.0, np.nan).ffill(limit=hold - 1).fillna(0.0)
    return pos
