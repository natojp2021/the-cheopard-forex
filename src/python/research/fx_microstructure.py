"""fx_microstructure.py — đặc trưng VI CẤU TRÚC dựng từ M1, đánh giá ở H1.

VÌ SAO ĐÂY LÀ THÔNG TIN MỚI, KHÔNG PHẢI HƯỚNG THỨ 10 CỦA CÙNG MỘT THỨ
======================================================================
Chín hướng nội ngày đã đổ đều dùng **OHLCV của chính khung đó**. Quét IC trên 15
đặc trưng loại đó cho |IC| lớn nhất = 0,0180 — trần của thông tin nằm trong giá
nến H1.

Nhưng dữ liệu gốc là **M1**, và mỗi nến H1 chứa 60 nến M1. Đường đi BÊN TRONG giờ
đó mang thông tin mà OHLC của H1 đã vứt bỏ:

    H1 chỉ giữ:  open, high, low, close, tổng tick
    M1 còn cho:  giá đi tới high trước hay low trước? đi thẳng hay zigzag?
                 bao nhiêu phút đóng tăng vs giảm? khối lượng dồn vào đâu?

Đây chính là loại thông tin mà tài liệu vi cấu trúc FX (Evans & Lyons; Lyons 2001)
chỉ ra là giải thích phần lớn biến động tỷ giá ngắn hạn: **dòng lệnh (order flow)**.
Ta không có dòng lệnh thật của liên ngân hàng, nhưng **quy tắc tick của Lee & Ready
(1991)** cho một proxy chuẩn: phân loại mỗi giao dịch là mua hay bán theo hướng
thay đổi giá. Áp lên M1 closes trong mỗi giờ cho ra mất cân bằng dòng lệnh ước lượng.

BỐN NHÓM ĐẶC TRƯNG
==================
1. **Mất cân bằng dòng lệnh (tick rule)** — tỷ lệ phút tăng trừ phút giảm, có và
   không có trọng số khối lượng. Proxy trực tiếp cho áp lực mua/bán ròng.
2. **Hiệu suất đường đi** — |close−open| / tổng biến động M1. Gần 1 = giá đi thẳng
   (thông tin); gần 0 = zigzag hết biên độ mà không đi đâu (thanh khoản/nhiễu).
   Đây là cách phân biệt thông tin/thanh khoản KHÁC với khối lượng — và khối lượng
   đã được chứng minh là KHÔNG phân biệt được trên FX (xem `fx_volume_conditioned`).
3. **Variance ratio** — var(lợi nhuận 5 phút) / (5 × var(lợi nhuận 1 phút)). > 1 =
   xu hướng bền trong giờ; < 1 = đảo chiều trong giờ. Lo & MacKinlay (1988).
4. **Thứ tự cực trị** — high đến trước hay low đến trước. Cho biết chiều áp lực
   ban đầu và chiều đảo ngược, thứ mà OHLC không nói.

TẤT CẢ đều tính từ nến M1 ĐÃ ĐÓNG trong giờ đã kết thúc → dùng được ở live ngay
khi nến H1 đóng, và không có look-ahead theo xây dựng.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.python.shared import asset_profile as AP
from src.python.shared import fx_data as D

DEV_END = pd.Timestamp("2024-01-01")


def build_features(symbol: str, timeframe: str = "H1",
                   start: str = "2020-01-01") -> pd.DataFrame:
    """Đặc trưng vi cấu trúc cho từng nến `timeframe`, tính từ M1 bên trong nó.

    Trả frame chỉ số theo nhãn nến `timeframe`, kèm `ret_bps` của chính nến đó
    (để đo IC) — mọi đặc trưng đều biết được lúc nến ĐÓNG.
    """
    m1 = D.load_m1(symbol)
    m1 = m1[m1.index >= start]
    rule = D.TF_RULE[timeframe]

    c = m1["close"]
    r1 = np.log(c).diff()
    up = np.sign(r1)                       # quy tắc tick: +1 mua, −1 bán, 0 không đổi
    vol = m1["volume"] if "volume" in m1 else pd.Series(1.0, index=m1.index)

    g = m1.resample(rule, origin="start_day", closed="left", label="left")
    n = g.size()

    f = pd.DataFrame(index=n.index)
    f["n_m1"] = n

    # ── 1. mất cân bằng dòng lệnh (tick rule)
    f["ofi_tick"] = up.resample(rule, origin="start_day", closed="left",
                                label="left").sum() / n.replace(0, np.nan)
    ofi_v = (up * vol).resample(rule, origin="start_day", closed="left", label="left").sum()
    vsum = vol.resample(rule, origin="start_day", closed="left", label="left").sum()
    f["ofi_vol"] = ofi_v / vsum.replace(0, np.nan)

    # ── 2. hiệu suất đường đi
    o = g["open"].first(); cl = g["close"].last()
    hi = g["high"].max(); lo = g["low"].min()
    path = r1.abs().resample(rule, origin="start_day", closed="left", label="left").sum()
    net = (np.log(cl) - np.log(o)).abs()
    f["path_eff"] = net / path.replace(0, np.nan)
    f["range_eff"] = net / (np.log(hi) - np.log(lo)).replace(0, np.nan)

    # ── 3. variance ratio 5 phút / 1 phút
    r5 = np.log(c).diff(5)
    v1 = (r1 ** 2).resample(rule, origin="start_day", closed="left", label="left").sum()
    v5 = (r5 ** 2).resample(rule, origin="start_day", closed="left", label="left").sum() / 5.0
    f["var_ratio"] = v5 / v1.replace(0, np.nan)

    # ── 4. thứ tự cực trị: high trước hay low trước (chuẩn hoá về [−1, 1])
    def _argpos(s: pd.Series, how: str) -> pd.Series:
        idxpos = s.groupby(pd.Grouper(freq=rule, origin="start_day", closed="left",
                                      label="left"))
        return idxpos.apply(lambda x: (np.argmax(x.to_numpy()) if how == "max"
                                       else np.argmin(x.to_numpy())) / max(len(x) - 1, 1)
                            if len(x) else np.nan)
    f["hi_pos"] = _argpos(m1["high"], "max")
    f["lo_pos"] = _argpos(m1["low"], "min")
    f["hi_before_lo"] = np.sign(f["lo_pos"] - f["hi_pos"])

    # ── lợi nhuận của chính nến (để đo IC), và giá đóng
    f["ret_bps"] = (np.log(cl) - np.log(o)) * 1e4
    f["close"] = cl
    f["spread_usd"] = g["spread_usd"].mean()

    # chỉ giữ nến đủ dữ liệu M1 (giờ giao dịch thật)
    expected = int(pd.Timedelta(rule) / pd.Timedelta(minutes=1))
    f = f[f["n_m1"] >= 0.8 * expected]

    prof = AP.get(symbol)
    px = float(f["close"].median()); sp = float(f["spread_usd"].median())
    f.attrs["cost_1rt_bps"] = (sp + prof.commission_price_units(px)) / px * 1e4
    f.attrs["symbol"] = symbol
    return f.dropna(subset=["ret_bps"])


FEATURE_COLS: Tuple[str, ...] = (
    "ofi_tick", "ofi_vol", "path_eff", "range_eff", "var_ratio",
    "hi_pos", "lo_pos", "hi_before_lo",
)


def normalize(f: pd.DataFrame, window: int = 500) -> pd.DataFrame:
    """Chuẩn hoá z-score TRƯỢT, nhân quả (`.shift(1)` trên cả trung bình lẫn độ lệch).

    Bắt buộc vì các đặc trưng này có chu kỳ ngày mạnh (đường đi trong giờ Á khác hẳn
    giờ London). Không chuẩn hoá thì IC đo được chỉ là cấu trúc phiên đã biết.
    """
    out = f.copy()
    for col in FEATURE_COLS:
        if col not in out:
            continue
        s = out[col]
        mu = s.shift(1).rolling(window, min_periods=window // 4).mean()
        sd = s.shift(1).rolling(window, min_periods=window // 4).std()
        out[col + "_z"] = (s - mu) / sd.replace(0, np.nan)
    return out


def information_scan(symbols: Sequence[str] = AP.FX_ALL,
                     timeframe: str = "H1",
                     horizons: Sequence[int] = (1, 2, 4, 8, 24),
                     start: str = "2020-01-01") -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    """IC của từng đặc trưng vi cấu trúc với lợi nhuận TƯƠNG LAI.

    Trả (IC trung bình qua các cặp, IC theo từng cặp). Đặc trưng tính trên nến `t`;
    lợi nhuận đo từ nến `t+1` trở đi — không chồng lấn, không look-ahead.
    """
    per_pair: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        f = normalize(build_features(sym, timeframe, start))
        r = f["ret_bps"]
        cols = [c + "_z" for c in FEATURE_COLS if c + "_z" in f]
        rows: Dict[str, Dict[str, float]] = {}
        for h in horizons:
            fwd = r.shift(-1).rolling(h).sum().shift(-(h - 1))
            for col in cols:
                x = f[col]
                m = x.notna() & fwd.notna() & np.isfinite(x)
                if m.sum() < 500:
                    continue
                rows.setdefault(col, {})[f"h{h}"] = round(
                    float(np.corrcoef(x[m], fwd[m])[0, 1]), 4)
        per_pair[sym] = pd.DataFrame(rows).T
    common = None
    for df in per_pair.values():
        common = df if common is None else common.add(df, fill_value=np.nan)
    avg = common / len(per_pair)
    return avg, per_pair
