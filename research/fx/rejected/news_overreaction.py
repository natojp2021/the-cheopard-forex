"""news_overreaction.py — CHIẾN LƯỢC M30: fade phản ứng thái quá sau tin đã lên lịch.

═══════════════════════════════════════════════════════════════════════════════
1. VÌ SAO ĐÂY LÀ HƯỚNG NỘI NGÀY DUY NHẤT CÒN SỐNG
═══════════════════════════════════════════════════════════════════════════════
Bảy hướng nội ngày đã bị bác bỏ bằng đo lường (xem `strategies/registry.py`):
price-action families · hiệu ứng fix theo giờ · RSI-diff pairs · ML lọc lệnh ·
cắt ngang cuộn H1 · cắt ngang neo phiên · đảo chiều có điều kiện khối lượng.

Và một phép đo quyết định giải thích VÌ SAO tất cả đều đổ: quét hệ số thông tin
(IC) trên 7 cặp × 15 đặc trưng × 5 horizon cho **|IC| lớn nhất = 0,0180**. Với chi
phí khứ hồi ~0,9-2,9 bps ở H1, một IC cỡ đó không đủ. Mọi mẫu hình GIÁ ở nội ngày
cho tín hiệu 0,2-0,5 bps — nằm dưới chi phí.

Tin tức khác về ĐỘ LỚN, không phải về mức độ. Đo được trên M30, 2020+:

    biên độ nến bình thường   EURUSD 3,12 bps · USDJPY 3,46 · GBPUSD 3,53
    biên độ nến chứa tin      NFP  15,88 (5,1x) · FOMC 13,97 (4,5x) · CPI 13,15 (4,2x)

Dịch chuyển gấp 4-6 lần nghĩa là ngay cả khi chỉ bắt được một phần nhỏ của nó,
phần đó vẫn lớn hơn chi phí nhiều lần. Đây là điều kiện mà không mẫu hình giá nào
ở nội ngày đạt được.

═══════════════════════════════════════════════════════════════════════════════
2. CƠ CHẾ — VÌ SAO FADE, KHÔNG PHẢI ĐI THEO
═══════════════════════════════════════════════════════════════════════════════
Phản ứng tức thời với tin bị chi phối bởi lệnh thị trường của thuật toán và người
giao dịch phản xạ, trong lúc sổ lệnh MỎNG NHẤT (người tạo lập rút báo giá quanh
mốc tin để tránh rủi ro chọn lọc bất lợi). Kết quả là giá đi quá xa so với mức mà
thông tin thật sự biện minh, rồi hồi lại khi thanh khoản quay về.

Đây là hiện tượng đã có tên trong tài liệu vi cấu trúc: **liquidity-driven
overshoot around announcements**. Nó cùng họ với cơ chế tồn kho của Krohn et al.
(2024) — thù lao cho việc cung cấp thanh khoản đúng lúc nó khan hiếm nhất.

Điểm quan trọng cho thiết kế: ta KHÔNG dự báo nội dung tin. Ta không cần biết NFP
ra bao nhiêu. Ta chỉ cần biết **thời điểm** (đã lên lịch, công khai) và **hướng cú
sốc đầu tiên** (quan sát được sau khi nến tin đóng). Đó là lý do chiến lược này
không đòi hỏi dữ liệu dự báo/đồng thuận mà ta không có.

═══════════════════════════════════════════════════════════════════════════════
3. LUẬT
═══════════════════════════════════════════════════════════════════════════════
    Với mỗi sự kiện đã lên lịch t (giờ UTC, từ `data/economic_calendar_events.parquet`):
      1. Chờ nến M30 CHỨA mốc t đóng lại
      2. move = log(close[t]) − log(close[t−1])        cú sốc đầu tiên
      3. Nếu |move| < MIN_SHOCK_BPS: BỎ QUA (không có cú sốc thì không có gì để fade)
      4. Vào lệnh NGƯỢC chiều `move` trên MỌI cặp đủ điều kiện, tỷ trọng đều
      5. Giữ HOLD_BARS nến M30 rồi đóng
      6. Không giữ qua đêm: nếu chạm 20:00 UTC thì đóng sớm

TÍNH NHÂN QUẢ: mọi đại lượng chỉ dùng nến ĐÃ ĐÓNG. Mốc sự kiện biết trước từ lịch,
`move` biết được đúng lúc nến tin đóng, lệnh vào ở nến kế tiếp.

⚠️ ĐIỂM YẾU THỰC THI PHẢI BIẾT — và vì sao vẫn chấp nhận được:
Ngay sau tin, spread giãn mạnh và slippage cao hơn hẳn ngày thường. Backtest ở đây
dùng spread TRUNG VỊ của cặp, tức **đánh giá thấp chi phí thật**. Bù lại: ta vào
lệnh ở nến SAU nến tin (đã cách mốc 30-60 phút), là lúc spread đã co lại đáng kể.
Stress test nhân chi phí ×3 và ×5 nằm trong `scratch/news_validation.py` — chiến
lược phải sống sót ở đó mới được dùng.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.python.shared import asset_profile as AP
from src.python.shared import fx_data as D

# ═════════════════════════════════════════════════════════ tham số (SSOT)
TIMEFRAME = "M30"
HOLD_BARS = 4               # 4 nến M30 = 2 giờ
MIN_SHOCK_BPS = 5.0         # dưới ngưỡng này coi như không có cú sốc
MAX_HOUR_UTC = 20           # không giữ vị thế qua 20:00 UTC
EVENTS_DEFAULT: Tuple[str, ...] = ("NFP", "FOMC", "CPI", "ECB_RATE")

CALENDAR_PATH = Path("data/economic_calendar_events.parquet")
DEV_END = pd.Timestamp("2024-01-01")


@dataclass(frozen=True)
class Config:
    hold_bars: int = HOLD_BARS
    min_shock_bps: float = MIN_SHOCK_BPS
    events: Tuple[str, ...] = EVENTS_DEFAULT
    max_hour_utc: int = MAX_HOUR_UTC
    cost_multiplier: float = 1.0     # >1 để stress chi phí


# ═════════════════════════════════════════════════════════ dữ liệu
def load_events(cfg: Config = Config(), start: str = "2020-01-01") -> pd.DatetimeIndex:
    """Mốc sự kiện đã lên lịch. Đây là thông tin BIẾT TRƯỚC — không phải dự báo."""
    ev = pd.read_parquet(CALENDAR_PATH)
    ev["time_utc"] = pd.to_datetime(ev["time_utc"])
    ev = ev[(ev["time_utc"] >= start) & (ev["event"].isin(cfg.events))]
    return pd.DatetimeIndex(sorted(ev["time_utc"].unique()))


def load_panel(symbols: Sequence[str] = AP.FX_ALL,
               start: str = "2020-01-01") -> Tuple[Dict[str, pd.DataFrame], pd.Series]:
    """Nến M30 của từng cặp + chi phí khứ hồi (bps) của cặp đó."""
    bars, costs = {}, {}
    for sym in symbols:
        b = D.build_bars(D.load_m1(sym), TIMEFRAME)
        b = b[b.index >= start]
        prof = AP.get(sym)
        px = float(b["close"].median())
        sp = float(b["spread_usd"].median())
        costs[sym] = (sp + prof.commission_price_units(px)) / px * 1e4
        bars[sym] = b
    return bars, pd.Series(costs, name="cost_1rt_bps")


# ═════════════════════════════════════════════════════════ tín hiệu
@dataclass
class Trade:
    time: pd.Timestamp
    symbol: str
    side: int               # +1 mua, −1 bán  (ngược chiều cú sốc)
    shock_bps: float
    gross_bps: float
    cost_bps: float
    net_bps: float


def generate_trades(bars: Dict[str, pd.DataFrame], costs: pd.Series,
                    events: pd.DatetimeIndex,
                    cfg: Config = Config()) -> pd.DataFrame:
    """Sinh toàn bộ lệnh. Dùng CHUNG bởi backtest và live (live lấy sự kiện cuối)."""
    rows: List[Trade] = []
    for sym, b in bars.items():
        logc = np.log(b["close"]) * 1e4
        idx = b.index
        cost = float(costs[sym]) * cfg.cost_multiplier
        for t in events:
            p = idx.searchsorted(pd.Timestamp(t))
            # cần nến trước (tính cú sốc) và đủ nến sau (để giữ)
            if p < 1 or p + cfg.hold_bars >= len(idx):
                continue
            shock = float(logc.iloc[p] - logc.iloc[p - 1])
            if abs(shock) < cfg.min_shock_bps:
                continue
            # thoát sớm nếu chạm giờ cấm giữ qua đêm
            exit_p = p + cfg.hold_bars
            for k in range(p + 1, exit_p + 1):
                if idx[k].hour >= cfg.max_hour_utc:
                    exit_p = k
                    break
            side = -int(np.sign(shock))
            gross = side * float(logc.iloc[exit_p] - logc.iloc[p])
            rows.append(Trade(time=idx[p], symbol=sym, side=side,
                              shock_bps=round(shock, 3), gross_bps=round(gross, 3),
                              cost_bps=round(cost, 3),
                              net_bps=round(gross - cost, 3)))
    return pd.DataFrame([t.__dict__ for t in rows])


def event_portfolio(trades: pd.DataFrame) -> pd.Series:
    """Gộp các cặp thành MỘT quan sát mỗi sự kiện, tỷ trọng đều.

    Đây là điểm thống kê quan trọng: 7 cặp trong cùng một sự kiện KHÔNG độc lập
    (chúng chia sẻ chân USD và cùng phản ứng với cùng một tin). Tính t-stat trên
    từng dòng lệnh sẽ phồng lên vì coi 7 quan sát tương quan là 7 quan sát độc
    lập. Gộp về mức SỰ KIỆN cho ra số quan sát đúng.
    """
    if trades.empty:
        return pd.Series(dtype=float)
    return trades.groupby("time")["net_bps"].mean().sort_index()


# ═════════════════════════════════════════════════════════ chỉ số
def stats(series: pd.Series, label: str = "") -> Dict[str, object]:
    if len(series) < 20:
        return {"label": label, "n": len(series)}
    cum = series.cumsum()
    dd = cum.cummax() - cum
    yrs = max((series.index.max() - series.index.min()).days / 365.25, 1e-9)
    per_year = len(series) / yrs
    sd = float(series.std(ddof=1))
    return {
        "label": label, "n": len(series),
        "per_year": round(per_year, 1),
        "net_bps": round(float(series.mean()), 3),
        "t": round(float(series.mean()) / (sd / np.sqrt(len(series))), 2) if sd > 0 else np.nan,
        "ann_pct": round(float(cum.iloc[-1]) / 100.0 / yrs, 3),
        "sharpe": round(float(series.mean()) / sd * np.sqrt(per_year), 3) if sd > 0 else np.nan,
        "hit": round(float((series > 0).mean()), 3),
        "max_dd_bps": round(float(dd.max()), 1),
    }


def backtest(cfg: Config = Config(), start: str = "2020-01-01"
             ) -> Tuple[pd.Series, pd.DataFrame]:
    bars, costs = load_panel(start=start)
    events = load_events(cfg, start=start)
    trades = generate_trades(bars, costs, events, cfg)
    return event_portfolio(trades), trades


# ═════════════════════════════════════════════════════════ giao diện LIVE
def next_events(cfg: Config = Config(), lookahead_days: int = 14) -> pd.DatetimeIndex:
    """Sự kiện sắp tới — dùng để lên lịch chờ, biết trước hàng tuần."""
    ev = pd.read_parquet(CALENDAR_PATH)
    ev["time_utc"] = pd.to_datetime(ev["time_utc"])
    now = pd.Timestamp.utcnow().tz_localize(None)
    m = (ev["time_utc"] >= now) & (ev["time_utc"] <= now + pd.Timedelta(days=lookahead_days))
    return pd.DatetimeIndex(sorted(ev[m & ev["event"].isin(cfg.events)]["time_utc"]))
