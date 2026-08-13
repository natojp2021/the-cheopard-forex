"""fx_clock.py — đo cấu trúc lợi nhuận FX quanh đồng hồ 24 giờ.

GIẢ THUYẾT ĐƯỢC ĐẶC TẢ TRƯỚC (không suy ra từ kết quả nào của dự án)
====================================================================
Krohn, Mueller & Whelan (2024), *Journal of Finance* 79(1) 541-578:
USD tăng giá hệ thống TRƯỚC ba phiên fix lớn và giảm giá SAU đó → danh mục ngoại
tệ có hình V quanh mỗi fix, hình W trên 24 giờ. 21 năm, G9, t = 5,5–9,2.
Cơ chế: rủi ro tồn kho của dealer khi trung gian cầu USD vô điều kiện tại các fix.

Xác nhận độc lập — Breedon & Ranaldo (SNB WP 2011-4): đồng tiền giảm giá trong
chính giờ giao dịch địa phương; với EURUSD tạo thành chiến lược có lợi nhuận.

⚠️ MÚI GIỜ LÀ VẤN ĐỀ ĐÚNG/SAI, KHÔNG PHẢI CHI TIẾT
==================================================
Ba fix được định nghĩa theo GIỜ ĐỊA PHƯƠNG:
    Tokyo   09:55 JST          — Nhật KHÔNG có DST  -> 00:55 UTC quanh năm
    ECB     14:15 Frankfurt    — CET/CEST           -> 13:15 UTC đông / 12:15 hè
    London  16:00 London       — GMT/BST            -> 16:00 UTC đông / 15:00 hè
Chỉ số dữ liệu của ta là UTC. Nếu gom theo GIỜ UTC CỐ ĐỊNH thì hai fix châu Âu bị
trải ra hai giờ khác nhau tuỳ mùa, và biên độ đo được bị chia gần một nửa. Mọi phép
gom ở đây vì vậy chạy trên GIỜ ĐỊA PHƯƠNG của chính trung tâm liên quan.

QUY ƯỚC DẤU — "DOL" (dollar factor)
===================================
Để cộng gộp các cặp, mọi lợi nhuận được biểu diễn theo **vị thế LONG NGOẠI TỆ so
với USD**:
    XXXUSD (EURUSD, GBPUSD, AUDUSD, NZDUSD) ->  r = +Δlog(price)
    USDXXX (USDJPY, USDCAD, USDCHF)         ->  r = −Δlog(price)
Khi đó "USD tăng giá" = r ÂM trên MỌI cặp. Không có quy ước này thì cộng gộp cho ra
nhiễu, và đây là lỗi rất dễ mắc.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.python.shared import fx_data as D
from src.python.shared import asset_profile as AP

# ───────────────────────────────────────────────────────── múi giờ & fix
TZ_TOKYO = ZoneInfo("Asia/Tokyo")
TZ_FRANKFURT = ZoneInfo("Europe/Berlin")
TZ_LONDON = ZoneInfo("Europe/London")
TZ_NY = ZoneInfo("America/New_York")

# fix -> (múi giờ, giờ thập phân địa phương)
FIXES: Dict[str, Tuple[ZoneInfo, float]] = {
    "TOKYO": (TZ_TOKYO, 9 + 55 / 60),
    "ECB": (TZ_FRANKFURT, 14 + 15 / 60),
    "LONDON": (TZ_LONDON, 16.0),
}

# Cửa sổ giao dịch ĐƯỢC ĐẶC TẢ TRƯỚC, giờ New York — Krohn et al. §V.
# (tên, tz, giờ bắt đầu, giờ kết thúc, hướng USD: +1 = long USD)
PRESPEC_WINDOWS: Tuple[Tuple[str, ZoneInfo, float, float, int], ...] = (
    ("TOKYO_pre",   TZ_NY, 17.0, 20 + 55 / 60, +1),
    ("TOKYO_post",  TZ_NY, 20 + 55 / 60, 26.0, -1),      # 26.0 = 02:00 hôm sau
    ("ECB_pre",     TZ_NY, 2.0, 8 + 15 / 60, +1),
    ("ECB_post",    TZ_NY, 8 + 15 / 60, 17.0, -1),
    ("LONDON_pre",  TZ_NY, 2.0, 11.0, +1),
    ("LONDON_post", TZ_NY, 11.0, 17.0, -1),
)

# Breedon & Ranaldo (SNB), giờ New York — luật gốc trên EURUSD.
BR_WINDOWS: Tuple[Tuple[str, ZoneInfo, float, float, int], ...] = (
    ("BR_europe", TZ_NY, 3.0, 9.0, +1),    # short EURUSD = long USD
    ("BR_us",     TZ_NY, 11.0, 15.0, -1),  # long EURUSD  = short USD
)

DEV_END = pd.Timestamp("2024-01-01")


# ───────────────────────────────────────────────────────── tiện ích
def local_hour(index: pd.DatetimeIndex, tz: ZoneInfo) -> np.ndarray:
    """Giờ thập phân địa phương. Index là UTC naive -> gán UTC rồi đổi múi giờ."""
    idx = index.tz_localize("UTC") if index.tz is None else index
    loc = idx.tz_convert(tz)
    return loc.hour.to_numpy() + loc.minute.to_numpy() / 60.0


def local_date(index: pd.DatetimeIndex, tz: ZoneInfo) -> np.ndarray:
    idx = index.tz_localize("UTC") if index.tz is None else index
    return idx.tz_convert(tz).normalize().tz_localize(None).to_numpy()


def dol_sign(symbol: str) -> int:
    """+1 nếu long cặp = long ngoại tệ; −1 nếu long cặp = long USD."""
    return 1 if AP.get(symbol).quote_is_usd else -1


def bars_with_returns(symbol: str, rule: str = "15min",
                      start: str = "2020-01-01") -> pd.DataFrame:
    """Nến `rule` kèm lợi nhuận log theo quy ước DOL, đơn vị **bps**."""
    m1 = D.load_m1(symbol)
    bars = D.build_bars(m1, {"15min": "M15", "1h": "H1", "30min": "M30"}[rule])
    bars = bars[bars.index >= start].copy()
    s = dol_sign(symbol)
    bars["ret_bps"] = s * np.log(bars["close"]).diff() * 1e4
    bars["spread_bps"] = bars["spread_usd"] / bars["close"] * 1e4
    return bars.dropna(subset=["ret_bps"])


# ───────────────────────────────────────────────────────── hồ sơ theo giờ
def hour_profile(symbol: str, tz: ZoneInfo, *, rule: str = "1h",
                 start: str = "2020-01-01",
                 end: Optional[str] = None) -> pd.DataFrame:
    """Lợi nhuận DOL trung bình theo GIỜ ĐỊA PHƯƠNG, kèm t-stat.

    Trả bảng: giờ | n | mean_bps | t | cum_bps (tích luỹ trong ngày).
    """
    bars = bars_with_returns(symbol, rule=rule, start=start)
    if end:
        bars = bars[bars.index < end]
    h = local_hour(bars.index, tz)
    bars = bars.assign(h=np.floor(h).astype(int))
    g = bars.groupby("h")["ret_bps"]
    out = pd.DataFrame({
        "n": g.size(),
        "mean_bps": g.mean(),
        "std_bps": g.std(ddof=1),
    })
    out["t"] = out["mean_bps"] / (out["std_bps"] / np.sqrt(out["n"]))
    out["cum_bps"] = out["mean_bps"].cumsum()
    return out.round(4)


# ───────────────────────────────────────────────────────── cửa sổ đặc tả trước
@dataclass
class WindowResult:
    symbol: str
    window: str
    usd_side: int
    n_days: int
    mean_bps: float          # lợi nhuận của CHIẾN LƯỢC (đã áp hướng USD)
    t: float
    hit_rate: float
    cost_bps: float          # chi phí khứ hồi thực tế của cặp
    net_bps: float
    ann_gross_pct: float
    ann_net_pct: float
    drift_cost_ratio: float


def _window_daily(bars: pd.DataFrame, tz: ZoneInfo, h0: float, h1: float) -> pd.Series:
    """Tổng lợi nhuận DOL (bps) trong cửa sổ [h0,h1) mỗi NGÀY địa phương.

    `h1 > 24` = cửa sổ vắt qua nửa đêm; phần sau nửa đêm được gán về ngày TRƯỚC
    để một "phiên giao dịch" nằm trọn trong một quan sát (cửa sổ TOKYO_post của
    Krohn chạy 20:55 → 02:00 hôm sau).
    """
    h = local_hour(bars.index, tz)
    d = local_date(bars.index, tz)
    if h1 <= 24.0:
        mask = (h >= h0) & (h < h1)
        day = d
    else:
        in_late = h >= h0                       # tối ngày D
        in_early = h < (h1 - 24.0)              # sáng sớm ngày D+1
        mask = in_late | in_early
        day = np.where(in_early, d - np.timedelta64(1, "D"), d)
    if not mask.any():
        return pd.Series(dtype=float)
    return pd.Series(bars["ret_bps"].to_numpy()[mask]).groupby(day[mask]).sum()


def eval_window(symbol: str, name: str, tz: ZoneInfo, h0: float, h1: float,
                usd_side: int, *, rule: str = "1h", start: str = "2020-01-01",
                end: Optional[str] = None, n_round_trips: float = 1.0) -> WindowResult:
    """Đánh giá MỘT cửa sổ đã đặc tả trước, kèm chi phí thật của cặp.

    `usd_side = +1` nghĩa là chiến lược LONG USD trong cửa sổ, tức lợi nhuận
    chiến lược = −(lợi nhuận DOL). `usd_side = −1` thì ngược lại.
    """
    bars = bars_with_returns(symbol, rule=rule, start=start)
    if end:
        bars = bars[bars.index < end]
    daily_dol = _window_daily(bars, tz, h0, h1)
    if len(daily_dol) < 30:
        return WindowResult(symbol, name, usd_side, len(daily_dol),
                            *([float("nan")] * 8))
    r = -usd_side * daily_dol           # lợi nhuận chiến lược, bps/ngày
    mean = float(r.mean())
    t = mean / (float(r.std(ddof=1)) / np.sqrt(len(r)))

    prof = AP.get(symbol)
    px = float(bars["close"].median())
    sp_px = float(bars["spread_usd"].median())
    comm_px = prof.commission_price_units(px)
    cost_bps = (sp_px + comm_px) / px * 1e4 * n_round_trips

    net = mean - cost_bps
    return WindowResult(
        symbol=symbol, window=name, usd_side=usd_side, n_days=len(r),
        mean_bps=round(mean, 4), t=round(t, 2),
        hit_rate=round(float((r > 0).mean()), 4),
        cost_bps=round(cost_bps, 4), net_bps=round(net, 4),
        ann_gross_pct=round(mean * 252 / 100, 2),
        ann_net_pct=round(net * 252 / 100, 2),
        drift_cost_ratio=round(mean / cost_bps, 2) if cost_bps > 0 else float("nan"),
    )


def eval_prespec(symbols: Tuple[str, ...] = AP.FX_ALL, *, rule: str = "1h",
                 start: str = "2020-01-01",
                 end: Optional[str] = None) -> pd.DataFrame:
    """Toàn bộ cửa sổ đặc tả trước của Krohn + Breedon-Ranaldo, mọi cặp."""
    rows = []
    for sym in symbols:
        for name, tz, h0, h1, side in PRESPEC_WINDOWS + BR_WINDOWS:
            rows.append(eval_window(sym, name, tz, h0, h1, side,
                                    rule=rule, start=start, end=end).__dict__)
    return pd.DataFrame(rows)
