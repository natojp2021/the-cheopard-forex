"""fx_fix_lab.py — cô đặc và điều kiện hoá hiệu ứng fix cho đến khi nó vượt chi phí.

VÌ SAO CẦN BƯỚC NÀY (kết quả đo được, `reports/fx_research/clock_prespec_windows.csv`)
=====================================================================================
Toàn bộ 14 cửa sổ đặc tả trước của Krohn et al. §V và Breedon-Ranaldo, trên cả 7 cặp,
cho **net ÂM**. Tỷ lệ drift/chi phí tốt nhất = 0,90 (USDJPY LONDON_pre) — vẫn < 1.

Đó KHÔNG phải bằng chứng hiệu ứng không tồn tại. Hồ sơ theo giờ cho thấy điều ngược
lại: trên EURUSD, giờ 07:00-08:00 New York (= 13:00-14:00 Frankfurt, tức giờ NGAY
TRƯỚC fix ECB 14:15) có DOL = −1,019 bps với **t = −4,30**, mạnh nhất trong 24 giờ;
giờ kế tiếp (bao trùm chính thời điểm fix) đảo dấu +0,883 bps, t = +2,06.

Tức chữ V là THẬT nhưng **dồn vào ~2 giờ**, trong khi cửa sổ của Krohn dài 6,25 giờ.
Cửa sổ dài pha loãng drift xuống dưới ngưỡng chi phí. Chi phí không phụ thuộc độ dài
cửa sổ — nó chỉ phụ thuộc SỐ LƯỢT khứ hồi. Vậy nên:

    tỷ lệ drift/chi phí  =  (drift thu được)  /  (chi phí mỗi lượt × số lượt)

có thể được cải thiện bằng HAI đòn, và cả hai đều đã được đặc tả trước bởi nguồn:

  ĐÒN 1 — CÔ ĐẶC THEO GIỜ. Giữ nguyên số lượt, tăng drift/lượt bằng cách chỉ ở trong
  thị trường ở những giờ mà drift thật sự xảy ra. Đây không phải tối ưu hoá tham số:
  giờ trước fix là vị trí mà cơ chế tồn kho của Krohn DỰ ĐOÁN drift phải nằm.

  ĐÒN 2 — ĐIỀU KIỆN HOÁ THEO RỦI RO TỒN KHO. Krohn et al. §IV đo được: **độ lớn đảo
  chiều LỚN HƠN sau những ngày biến động cao / spread cao**. Đó là hệ quả trực tiếp
  của cơ chế — tồn kho rủi ro hơn thì dealer đòi thù lao cao hơn. Giao dịch chỉ ở
  nhóm phân vị trên cắt số lượt xuống 1/5 trong khi giữ phần lớn drift.

  ĐÒN 3 — DÒNG CUỐI THÁNG (Ứng viên 2). Tái cân bằng hedge tổ chức tập trung quanh
  London fix của những ngày giao dịch cuối tháng, hàng chục tỷ USD notional. Tần suất
  ~36 ngày/năm thay vì 252 → chi phí gần như không còn là ràng buộc.

KỶ LUẬT CHỐNG OVERFIT
=====================
Mọi giả thuyết ở đây phải đến TỪ NGUỒN, không từ việc nhìn kết quả. Ba đòn trên đều
có xuất xứ nguồn ghi rõ. Ngoài ra:
  * DEV 2020-2024 / OOS 2024+ tách sẵn, verdict chỉ đọc OOS.
  * Mọi giờ được báo cáo cùng lúc (không chọn giờ tốt nhất rồi báo cáo riêng).
  * Số phép thử được đếm tường minh để hiệu chỉnh Bonferroni.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.python.research import fx_clock as C
from src.python.shared import asset_profile as AP

DEV_END = pd.Timestamp("2024-01-01")


# ═════════════════════════════════════════════════════ nền: bảng ngày × giờ
def hour_panel(symbol: str, tz: ZoneInfo, *, start: str = "2020-01-01") -> pd.DataFrame:
    """Bảng (ngày địa phương × giờ địa phương) -> lợi nhuận DOL bps của nến H1 đó.

    Kèm các cột điều kiện tính TỪ NGÀY TRƯỚC (nhân quả, không nhìn tương lai):
        prev_range_bps   biên độ ngày trước, bps
        prev_spread_bps  spread trung vị ngày trước, bps
        is_month_end_3   thuộc 3 ngày giao dịch cuối tháng
        is_month_end_1   là ngày giao dịch cuối tháng
    """
    bars = C.bars_with_returns(symbol, rule="1h", start=start)
    h = np.floor(C.local_hour(bars.index, tz)).astype(int)
    d = C.local_date(bars.index, tz)
    df = pd.DataFrame({
        "day": d, "h": h,
        "ret_bps": bars["ret_bps"].to_numpy(),
        "spread_bps": bars["spread_bps"].to_numpy(),
        "high": bars["high"].to_numpy(), "low": bars["low"].to_numpy(),
        "close": bars["close"].to_numpy(),
    })
    panel = df.pivot_table(index="day", columns="h", values="ret_bps", aggfunc="sum")

    # đặc trưng theo ngày -> dịch 1 ngày để chỉ dùng thông tin đã biết
    daily = df.groupby("day").agg(
        hi=("high", "max"), lo=("low", "min"), cl=("close", "last"),
        sp=("spread_bps", "median"))
    daily["range_bps"] = (daily["hi"] - daily["lo"]) / daily["cl"] * 1e4
    cond = pd.DataFrame(index=daily.index)
    cond["prev_range_bps"] = daily["range_bps"].shift(1)
    cond["prev_spread_bps"] = daily["sp"].shift(1)

    idx = pd.DatetimeIndex(daily.index)
    ym = idx.to_period("M")
    rank_from_end = pd.Series(0, index=daily.index)
    for _, grp in pd.Series(idx, index=daily.index).groupby(ym):
        order = np.arange(len(grp), 0, -1)          # 1 = ngày cuối tháng
        rank_from_end.loc[grp.index] = order
    cond["me_rank"] = rank_from_end
    cond["is_month_end_3"] = rank_from_end <= 3
    cond["is_month_end_1"] = rank_from_end == 1

    return panel.join(cond)


# ═════════════════════════════════════════════════════ đánh giá một luật giờ
@dataclass
class HourRule:
    """Một luật: ở trong thị trường đúng giờ `hours` (giờ địa phương `tz`),
    hướng `usd_side` (+1 long USD). Mỗi giờ liền kề nhau = MỘT lượt khứ hồi."""
    name: str
    tz: ZoneInfo
    hours: Tuple[int, ...]
    usd_side: int

    @property
    def n_round_trips(self) -> float:
        """Số lượt khứ hồi. Các giờ LIÊN TIẾP gộp thành một vị thế duy nhất."""
        hs = sorted(self.hours)
        blocks = 1
        for a, b in zip(hs, hs[1:]):
            if b != a + 1:
                blocks += 1
        return float(blocks)


@dataclass
class RuleResult:
    symbol: str
    rule: str
    n_trades: int
    gross_bps: float
    t: float
    hit_rate: float
    cost_bps: float
    net_bps: float
    ratio: float
    ann_net_pct: float
    sharpe: float


def cost_round_trip_bps(symbol: str, panel_ref: pd.DataFrame | None = None,
                        px: float | None = None, sp_px: float | None = None) -> float:
    """Chi phí MỘT lượt khứ hồi, bps — spread thật + commission theo AssetProfile."""
    prof = AP.get(symbol)
    if px is None or sp_px is None:
        bars = C.bars_with_returns(symbol, rule="1h", start="2020-01-01")
        px = float(bars["close"].median())
        sp_px = float(bars["spread_usd"].median())
    return (sp_px + prof.commission_price_units(px)) / px * 1e4


def eval_rule(symbol: str, rule: HourRule, panel: pd.DataFrame, *,
              mask: Optional[pd.Series] = None,
              cost_1rt: Optional[float] = None) -> RuleResult:
    """`mask` = bộ lọc ngày (điều kiện hoá). Chi phí nhân theo số lượt khứ hồi."""
    cols = [h for h in rule.hours if h in panel.columns]
    if not cols:
        return RuleResult(symbol, rule.name, 0, *([float("nan")] * 8))
    sub = panel if mask is None else panel[mask.reindex(panel.index, fill_value=False)]
    daily_dol = sub[cols].sum(axis=1, min_count=len(cols)).dropna()
    if len(daily_dol) < 25:
        return RuleResult(symbol, rule.name, len(daily_dol), *([float("nan")] * 8))
    r = -rule.usd_side * daily_dol                  # lợi nhuận chiến lược, bps/ngày
    c1 = cost_1rt if cost_1rt is not None else cost_round_trip_bps(symbol)
    cost = c1 * rule.n_round_trips
    net = r - cost
    sd = float(r.std(ddof=1))
    net_sd = float(net.std(ddof=1))
    # annualise theo TẦN SUẤT THẬT của luật (số ngày giao dịch/năm), không phải 252
    per_year = len(r) / ((panel.index.max() - panel.index.min()).days / 365.25)
    return RuleResult(
        symbol=symbol, rule=rule.name, n_trades=len(r),
        gross_bps=round(float(r.mean()), 4),
        t=round(float(r.mean()) / (sd / np.sqrt(len(r))), 2) if sd > 0 else float("nan"),
        hit_rate=round(float((net > 0).mean()), 4),
        cost_bps=round(cost, 4),
        net_bps=round(float(net.mean()), 4),
        ratio=round(float(r.mean()) / cost, 2) if cost > 0 else float("nan"),
        ann_net_pct=round(float(net.mean()) * per_year / 100, 2),
        sharpe=round(float(net.mean()) / net_sd * np.sqrt(per_year), 2) if net_sd > 0 else float("nan"),
    )


# ═════════════════════════════════════════════════════ điều kiện hoá
def quintile_mask(panel: pd.DataFrame, col: str, q: int, n_q: int = 5) -> pd.Series:
    """Mặt nạ ngày thuộc phân vị thứ `q` (1 = thấp nhất) của cột điều kiện.

    Phân vị tính TRÊN TOÀN MẪU — đây là một điểm cần biết khi đọc số: nó dùng
    thông tin của cả kỳ để định nghĩa ranh giới phân vị. Với một bộ lọc dựa trên
    biến động (rất dai và ổn định) thì sai lệch này nhỏ, nhưng nó KHÔNG bằng 0.
    Phiên bản triển khai live phải dùng phân vị RỖNG TRƯỢT — xem `rolling_quintile_mask`.
    """
    v = panel[col]
    edges = v.quantile(np.linspace(0, 1, n_q + 1)).to_numpy()
    lo, hi = edges[q - 1], edges[q]
    return (v >= lo) & (v <= hi if q == n_q else v < hi)


def rolling_quintile_mask(panel: pd.DataFrame, col: str, q_lo: float,
                          window: int = 252) -> pd.Series:
    """Mặt nạ "hôm nay thuộc top (1−q_lo) của `window` ngày TRƯỚC ĐÓ" — nhân quả.

    Đây là phiên bản dùng được ở live. `q_lo=0.8` = top 20%.
    """
    v = panel[col]
    thr = v.shift(1).rolling(window, min_periods=window // 2).quantile(q_lo)
    return (v >= thr).fillna(False)
