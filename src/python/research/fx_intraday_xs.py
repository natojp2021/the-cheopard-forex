"""fx_intraday_xs.py — tìm chiến lược cắt ngang ở khung NỘI NGÀY (H1/M30).

VÌ SAO HƯỚNG NÀY, SAU KHI BỐN HƯỚNG NỘI NGÀY ĐÃ ĐỔ
===================================================
Đã bác bỏ ở khung nội ngày:
  * 8 price-action family (M30/H1/H4) — 28/33 NO_INFORMATION
  * hiệu ứng fix theo giờ — drift ≈ đúng 1 lượt khứ hồi
  * RSI-difference pairs trading H1 (Jirapongpan IEEE) — không đạt
  * lọc ML trên feature giá/vol/corr — < 60% CV

Nhưng ở khung NGÀY, đúng một thứ hoạt động: **cắt ngang tiền tệ**. Và lý do nó
hoạt động là CẤU TRÚC, không phải thang thời gian:

    long đồng yếu + short đồng mạnh  →  triệt tiêu thành phần USD chung
    →  cái còn lại là tín hiệu TƯƠNG ĐỐI, không bị drift USD nhấn chìm

Vòng 1 đã chứng minh mặt còn lại: mọi cược CÓ HƯỚNG ở nội ngày đều thất bại vì
chúng đo chu kỳ USD chứ không đo tín hiệu. Cấu trúc cắt ngang không có lý do gì
chỉ tồn tại ở thang ngày — nó chưa từng được thử ở nội ngày. Đó là khoảng trống
duy nhất còn lại có cơ sở.

Cộng thêm một thứ chỉ có ở nội ngày: **cấu trúc phiên**, đo được rất mạnh và ổn
định (`reports/fx_recon/session_profile.csv`) — biên độ H1 giờ 13-14 GMT gấp 3-4
lần giờ 21-23 GMT trên mọi cặp.

RÀNG BUỘC CHI PHÍ — PHẢI ĐỐI DIỆN TỪ ĐẦU
=========================================
Chi phí khứ hồi rổ 7 cặp: **1,657 bps** ở giờ rẻ nhất (15:00 UTC).
Chiến lược D1 giải bài toán này bằng cách giữ 21 ngày (12 lượt/năm). Ở nội ngày,
tần suất cao gấp bội, nên tín hiệu phải mạnh hơn nhiều **trên mỗi lượt**:

    tái cân bằng mỗi 24 giờ  →  252 lượt/năm  →  418 bps/năm chi phí
    tái cân bằng mỗi 120 giờ →   50 lượt/năm  →   83 bps/năm

Vì vậy quy trình ở đây tách đôi có chủ ý:
  BƯỚC 1  đo SỨC MẠNH TÍN HIỆU thô (bps/lượt), chưa nói gì tới chi phí
  BƯỚC 2  chỉ những ô có drift/chi phí > 1 mới được đi tiếp

Làm ngược lại — backtest đủ chi phí ngay — sẽ trộn "tín hiệu yếu" với "tần suất
sai" và không tách được hai nguyên nhân, đúng lỗi đã mắc ở vòng hiệu ứng fix.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.python.shared import asset_profile as AP
from src.python.shared import fx_data as D

PAIRS: Tuple[str, ...] = AP.FX_ALL
DEV_END = pd.Timestamp("2024-01-01")

# Chi phí khứ hồi rổ 7 cặp, tỷ trọng đều, ở giờ rẻ (đo được, xem docstring).
BASKET_COST_BPS = 1.657


# ═══════════════════════════════════════════════════════ ma trận đồng tiền nội ngày
def currency_bars(timeframe: str = "H1", start: str = "2020-01-01"
                  ) -> Tuple[pd.DataFrame, pd.Series]:
    """(lợi nhuận log của 8 đồng tiền theo nến `timeframe`, bps; chi phí mỗi cặp).

    Chuẩn hoá tổng = 0 mỗi nến — dollar-neutral theo xây dựng, giống bản D1.
    Chỉ giữ nhãn thời gian mà **mọi cặp đều có nến**: thiếu một cặp thì phép xếp
    hạng cắt ngang lệch, và điều đó tệ hơn là bỏ qua nhãn đó.
    """
    rets: Dict[str, pd.Series] = {}
    costs: Dict[str, float] = {}
    for sym in PAIRS:
        m1 = D.load_m1(sym)
        bars = D.build_bars(m1, timeframe)
        bars = bars[bars.index >= start]
        prof = AP.get(sym)
        r = np.log(bars["close"]).diff() * 1e4
        foreign = prof.base if prof.quote_is_usd else prof.quote
        rets[foreign] = r if prof.quote_is_usd else -r
        px = float(bars["close"].median())
        sp = float(bars["spread_usd"].median())
        costs[sym] = (sp + prof.commission_price_units(px)) / px * 1e4
    F = pd.DataFrame(rets).dropna(how="any")     # chỉ nhãn có đủ 7 cặp
    F["USD"] = -F.mean(axis=1)
    F = F.sub(F.mean(axis=1), axis=0)
    return F, pd.Series(costs, name="cost_1rt_bps")


# ═══════════════════════════════════════════════════════ BƯỚC 1: sức mạnh tín hiệu
@dataclass
class SignalPower:
    timeframe: str
    lookback: int
    hold: int
    sign: int                 # −1 reversal, +1 momentum
    n_obs: int
    gross_bps: float          # lợi nhuận/lượt, chưa chi phí
    t_stat: float
    bps_per_bar: float
    cost_ratio: float         # gross / chi phí một lượt
    hit_rate: float


def measure_signal(F: pd.DataFrame, lookback: int, hold: int, *,
                   sign: int = -1, n_leg: int = 3,
                   timeframe: str = "H1") -> SignalPower:
    """Sức mạnh tín hiệu cắt ngang, KHÔNG chi phí, KHÔNG chồng lấn vị thế.

    Lấy mẫu mỗi `hold` nến để các quan sát không chồng nhau — chồng lấn làm t-stat
    phồng lên giả tạo, và đó là cách dễ nhất để tự lừa mình ở khung nội ngày nơi
    số quan sát rất lớn.
    """
    cum = F.cumsum()
    signal = sign * (cum - cum.shift(lookback))
    vol = F.rolling(max(lookback * 4, 100), min_periods=50).std()

    idx = np.arange(lookback, len(F) - hold, hold)
    out = []
    cols = list(F.columns)
    Fv, Sv, Vv = F.to_numpy(), signal.to_numpy(), vol.to_numpy()
    for i in idx:
        s, v = Sv[i], Vv[i]
        if np.isnan(s).sum() > len(cols) - 2 * n_leg or np.isnan(v).sum() > len(cols) - 2 * n_leg:
            continue
        order = np.argsort(-np.nan_to_num(s, nan=-1e18))
        longs, shorts = order[:n_leg], order[-n_leg:]
        w = np.zeros(len(cols))
        for grp, sg in ((longs, 1.0), (shorts, -1.0)):
            iv = 1.0 / np.where(np.isfinite(v[grp]) & (v[grp] > 0), v[grp], np.nan)
            iv = np.nan_to_num(iv)
            if iv.sum() > 0:
                w[grp] = sg * iv / iv.sum()
        fwd = Fv[i + 1:i + 1 + hold].sum(axis=0)
        out.append(float(np.dot(w, fwd)))

    a = np.array(out, dtype=float)
    a = a[np.isfinite(a)]
    if len(a) < 30:
        return SignalPower(timeframe, lookback, hold, sign, len(a),
                           *([float("nan")] * 5))
    mean = float(a.mean())
    t = mean / (float(a.std(ddof=1)) / np.sqrt(len(a)))
    return SignalPower(
        timeframe=timeframe, lookback=lookback, hold=hold, sign=sign,
        n_obs=len(a), gross_bps=round(mean, 4), t_stat=round(t, 2),
        bps_per_bar=round(mean / hold, 4),
        cost_ratio=round(mean / BASKET_COST_BPS, 3),
        hit_rate=round(float((a > 0).mean()), 4))


def scan(F: pd.DataFrame, lookbacks: Sequence[int], holds: Sequence[int], *,
         timeframe: str = "H1", signs: Sequence[int] = (-1, +1)) -> pd.DataFrame:
    """Quét lưới (lookback × hold × chiều). Báo cáo TOÀN BỘ, không lọc trước."""
    rows = []
    for sg in signs:
        for lb in lookbacks:
            for h in holds:
                rows.append(measure_signal(F, lb, h, sign=sg,
                                           timeframe=timeframe).__dict__)
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════ điều kiện phiên
def session_of(index: pd.DatetimeIndex) -> pd.Series:
    """Nhãn phiên theo giờ UTC. Ranh giới lấy từ cấu trúc thanh khoản đo được,
    không phải quy ước sách vở: `reports/fx_recon/session_profile.csv`."""
    h = index.hour
    lab = np.where(h < 7, "ASIA",
          np.where(h < 12, "LONDON",
          np.where(h < 16, "OVERLAP",         # London+NY, biên độ lớn nhất
          np.where(h < 20, "NY", "ROLLOVER"))))
    return pd.Series(lab, index=index)


def measure_by_session(F: pd.DataFrame, lookback: int, hold: int, *,
                       sign: int = -1, n_leg: int = 3) -> pd.DataFrame:
    """Tách sức mạnh tín hiệu theo PHIÊN mà vị thế được MỞ.

    Giả thuyết: đảo chiều cắt ngang mạnh nhất khi vị thế mở vào lúc thanh khoản
    mỏng (phiên Á) — đó là lúc lệch giá tạm thời dễ hình thành nhất — rồi hồi lại
    khi thanh khoản châu Âu vào. Đây là cơ chế của Breedon & Ranaldo (dòng lệnh
    doanh nghiệp theo giờ địa phương) áp cho cược tương đối thay vì cược hướng.
    """
    cum = F.cumsum()
    signal = sign * (cum - cum.shift(lookback))
    vol = F.rolling(max(lookback * 4, 100), min_periods=50).std()
    sess = session_of(F.index)

    idx = np.arange(lookback, len(F) - hold, hold)
    recs = []
    cols = list(F.columns)
    Fv, Sv, Vv = F.to_numpy(), signal.to_numpy(), vol.to_numpy()
    for i in idx:
        s, v = Sv[i], Vv[i]
        if np.isnan(s).sum() > len(cols) - 2 * n_leg:
            continue
        order = np.argsort(-np.nan_to_num(s, nan=-1e18))
        w = np.zeros(len(cols))
        for grp, sg in ((order[:n_leg], 1.0), (order[-n_leg:], -1.0)):
            iv = np.nan_to_num(1.0 / np.where(np.isfinite(v[grp]) & (v[grp] > 0),
                                              v[grp], np.nan))
            if iv.sum() > 0:
                w[grp] = sg * iv / iv.sum()
        recs.append({"session": sess.iloc[i], "time": F.index[i],
                     "pnl_bps": float(np.dot(w, Fv[i + 1:i + 1 + hold].sum(axis=0)))})

    df = pd.DataFrame(recs)
    if df.empty:
        return df
    g = df.groupby("session")["pnl_bps"]
    out = pd.DataFrame({"n": g.size(), "mean_bps": g.mean().round(4),
                        "std": g.std(ddof=1).round(3)})
    out["t"] = (out["mean_bps"] / (out["std"] / np.sqrt(out["n"]))).round(2)
    out["cost_ratio"] = (out["mean_bps"] / BASKET_COST_BPS).round(3)
    out["hit"] = g.apply(lambda x: float((x > 0).mean())).round(4)
    return out.sort_values("mean_bps", ascending=False)
