# -*- coding: utf-8 -*-
"""Thước đo hiệu suất BỀN — thay CAGR%/MAR/Sharpe trong báo cáo so sánh.

References
----------
Primary Reference:
    Faith, C. (2007). *Way of the Turtle: The Secret Methods that Turned Ordinary
    People into Legendary Traders*. McGraw-Hill. Ch. 12 "On Solid Ground",
    tr. 182-190.

    Faith chứng minh bằng thực nghiệm rằng MAR, CAGR% và Sharpe **không bền**:
    dịch mốc bắt đầu lùi 1 tháng và mốc kết thúc lùi 2 tháng trên một phép kiểm
    hơn mười năm làm Sharpe đổi 0,08-0,12 và MAR đổi 0,18-0,22 — trong khi RAR%
    chỉ đổi 0,11 điểm phần trăm. CAGR% nhạy hơn RAR% khoảng **30 lần**.

    Nguyên nhân (tr.185): tử số của MAR và Sharpe đều chứa lợi nhuận, mà lợi
    nhuận nhạy với mốc đầu-cuối; sụt vốn tối đa cũng nhạy khi nó rơi gần hai đầu.
    MAR nhạy gấp đôi vì cả tử lẫn mẫu đều nhạy.

Supporting References:
    - Kirkpatrick, C.D. & Dahlquist, J.R. (2011). *Technical Analysis*, ch.22
      tr.548 — báo cáo **lợi nhuận ròng trên sụt vốn tối đa**; với FTMO đặc biệt
      hợp lý vì sụt vốn là ràng buộc cứng chứ không chỉ là thước đo khó chịu.
    - Halls-Moore, M. (2015). *Successful Algorithmic Trading*, ch.3 tr.16 —
      mặt phẳng hiệu suất gồ ghề là dấu hiệu tham số không phản ánh hiện tượng
      thật; thước bền làm mặt phẳng đọc được.

Champion Knowledge synthesized from:
    - Faith (2007) ch.12 — RAR%, R-cubed, robust Sharpe
    - Kirkpatrick & Dahlquist (2011) ch.22 — net profit / max drawdown
    - Aronson (2007) ch.6 — vì sao con số của người thắng cuộc là tiêu chí chọn,
      không phải ước lượng (lý do phải có thước ít nhạy với chọn lọc)

Vì sao module này tồn tại
--------------------------
Mọi con số dự án báo cáo trong phiên 03/08 đều thuộc nhóm không bền: tổng R,
R/lệnh, Sharpe, sụt vốn tối đa một điểm. Khi so hai cấu hình chỉ khác nhau chút
ít, các thước này có thể đảo thứ hạng chỉ vì mốc dữ liệu — nghĩa là quyết định
"cấu hình A tốt hơn B" có thể là nhiễu.

Ba thước ở đây không làm chiến lược tốt hơn. Chúng làm **phép so sánh đáng tin
hơn**, và đó là điều kiện cần cho mọi quyết định phía sau.

Ghi chú về phạm vi
------------------
Module thuần tính toán trên đường vốn — không biết gì về chiến lược, không đọc
dữ liệu, không có tác dụng phụ. Cố ý như vậy để dùng được cho cả backtest lẫn
báo cáo live.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Số phiên giao dịch một năm. Dùng 252 cho nhất quán với phần còn lại của dự án.
TRADING_DAYS_YEAR = 252

# Faith tr.188 lấy trung bình **5** lần sụt vốn lớn nhất và 5 lần dài nhất.
# Con số 5 là của ông, không phải lựa chọn của dự án.
TOP_DRAWDOWNS = 5

# Dưới ngưỡng này thì hồi quy trên đường vốn không có ý nghĩa.
MIN_POINTS = 30


@dataclass(frozen=True)
class DrawdownProfile:
    """Hồ sơ sụt vốn nhiều chiều thay cho một con số tối đa.

    Faith tr.187: "The maximum drawdown is **a single point** on an equity curve,
    and so you are missing out on some valuable additional data… A system that
    had five large drawdowns of 32, 34, 35, 35, and 36 percent would be harder
    to trade than would a system that had drawdowns of 20, 25, 26, 29, and 36."
    """

    max_depth: float                 # sụt vốn sâu nhất (tỉ lệ, 0-1)
    avg_max_depth: float             # trung bình TOP_DRAWDOWNS lần sâu nhất
    max_length_days: float           # đợt sụt vốn dài nhất
    avg_max_length_days: float       # trung bình TOP_DRAWDOWNS lần dài nhất
    n_drawdowns: int

    def summary(self) -> str:
        return (f"sụt vốn sâu nhất {self.max_depth:.2%} "
                f"(TB{TOP_DRAWDOWNS} sâu nhất {self.avg_max_depth:.2%}), "
                f"dài nhất {self.max_length_days:.0f} ngày "
                f"(TB{TOP_DRAWDOWNS} dài nhất {self.avg_max_length_days:.0f} ngày), "
                f"tổng {self.n_drawdowns} đợt")


@dataclass(frozen=True)
class RobustMetrics:
    """Bộ thước bền đầy đủ, kèm các thước cũ để đối chiếu."""

    # --- thước BỀN (Faith ch.12) ---
    rar_pct: float                   # lợi nhuận năm theo hồi quy
    r_cubed: float                   # RAR% / (sụt vốn TB × thời lượng TB / 365)
    robust_sharpe: float             # RAR% / độ lệch chuẩn năm hoá
    drawdown: DrawdownProfile

    # --- thước KHÔNG BỀN, giữ để đối chiếu và để không phá tương thích ---
    cagr_pct: float
    max_drawdown: float
    sharpe: float
    mar: float

    # --- K&D ch.22 tr.548 ---
    net_profit_over_max_dd: float

    n_points: int

    def summary(self) -> str:
        lines = [
            "THƯỚC BỀN (Faith ch.12 tr.186-188):",
            f"  RAR%      {self.rar_pct:8.2f}   (lợi nhuận năm theo hồi quy)",
            f"  R³        {self.r_cubed:8.3f}   (RAR% / sụt vốn TB điều chỉnh thời lượng)",
            f"  R-Sharpe  {self.robust_sharpe:8.3f}",
            f"  {self.drawdown.summary()}",
            "THƯỚC CŨ (không bền — chỉ để đối chiếu):",
            f"  CAGR%     {self.cagr_pct:8.2f}",
            f"  Sharpe    {self.sharpe:8.3f}",
            f"  MAR       {self.mar:8.3f}",
            f"  sụt vốn tối đa {self.max_drawdown:.2%}",
            f"K&D ch.22 tr.548: lãi ròng / sụt vốn tối đa = "
            f"{self.net_profit_over_max_dd:.2f}",
        ]
        return "\n".join(lines)


def _as_equity(equity: pd.Series | np.ndarray | list) -> np.ndarray:
    arr = np.asarray(getattr(equity, "to_numpy", lambda: equity)(), dtype=float) \
        if hasattr(equity, "to_numpy") else np.asarray(equity, dtype=float)
    if arr.size < MIN_POINTS:
        raise ValueError(f"cần ít nhất {MIN_POINTS} điểm đường vốn, có {arr.size}")
    if np.any(arr <= 0):
        raise ValueError("đường vốn phải dương ở mọi điểm (dùng giá trị tài khoản, "
                         "không dùng lãi lỗ tích luỹ có thể âm)")
    return arr


def regressed_annual_return(equity, periods_per_year: int = TRADING_DAYS_YEAR) -> float:
    """RAR% — độ dốc hồi quy tuyến tính qua TOÀN BỘ điểm của đường vốn log.

    Faith tr.186: "A better measure of the slope is a simple **linear regression
    of all the points**… much less sensitive to changes in the data at the end of
    the test."

    Khác CAGR% ở chỗ CAGR% chỉ là độ dốc đường thẳng nối điểm đầu với điểm cuối,
    nên một đợt sụt vốn nằm ở hai đầu làm nó đổi mạnh.
    """
    v = _as_equity(equity)
    y = np.log(v)
    x = np.arange(y.size, dtype=float)
    slope = float(np.polyfit(x, y, 1)[0])
    return float(np.expm1(slope * periods_per_year) * 100.0)


def drawdown_profile(equity, periods_per_year: int = TRADING_DAYS_YEAR,
                     top: int = TOP_DRAWDOWNS) -> DrawdownProfile:
    """Hồ sơ sụt vốn: độ sâu và THỜI LƯỢNG, mỗi thứ lấy trung bình `top` lần tệ nhất.

    Faith tr.187-188: "the extent of the drawdown is only one dimension: **All 30
    percent drawdowns are not the same.** I would not mind a drawdown that lasted
    only two months before recovering to new highs nearly as much as I would mind
    one that took two years."

    Một "đợt sụt vốn" = quãng từ lúc rời đỉnh cũ tới lúc lập đỉnh mới. Đợt đang
    dở ở cuối chuỗi VẪN được tính — bỏ nó đi sẽ làm đẹp số một cách giả tạo đúng
    lúc nguy hiểm nhất.
    """
    v = _as_equity(equity)
    peak = np.maximum.accumulate(v)
    under = v < peak

    depths: list[float] = []
    lengths: list[int] = []
    i = 0
    n = v.size
    while i < n:
        if not under[i]:
            i += 1
            continue
        j = i
        while j < n and under[j]:
            j += 1
        start_val = v[i - 1] if i > 0 else v[i]
        depths.append(float(1.0 - v[i:j].min() / start_val))
        lengths.append(j - i)
        i = j

    if not depths:
        return DrawdownProfile(0.0, 0.0, 0.0, 0.0, 0)

    days_per_period = 365.0 / periods_per_year
    top_d = sorted(depths, reverse=True)[:top]
    top_l = sorted(lengths, reverse=True)[:top]
    return DrawdownProfile(
        max_depth=float(max(depths)),
        avg_max_depth=float(np.mean(top_d)),
        max_length_days=float(max(lengths) * days_per_period),
        avg_max_length_days=float(np.mean(top_l) * days_per_period),
        n_drawdowns=len(depths),
    )


def r_cubed(equity, periods_per_year: int = TRADING_DAYS_YEAR) -> float:
    """R-cubed (RRRR) — tỉ số lợi nhuận/rủi ro tính cả ĐỘ SÂU lẫn THỜI LƯỢNG.

    Faith tr.188:

        R³ = RAR% / (sụt vốn tối đa trung bình × thời lượng trung bình / 365)

    Ví dụ của ông: RAR% 50%, sụt vốn trung bình 25%, thời lượng trung bình 365
    ngày → R³ = 50 / (25 × 365/365) = 2,0.

    Trả `inf` khi không có sụt vốn nào — đúng về mặt toán, và người đọc cần thấy
    trường hợp đó thay vì một con số bịa.
    """
    rar = regressed_annual_return(equity, periods_per_year)
    dd = drawdown_profile(equity, periods_per_year)
    denom = dd.avg_max_depth * 100.0 * (dd.avg_max_length_days / 365.0)
    if denom <= 1e-12:
        return float("inf") if rar > 0 else float("-inf") if rar < 0 else 0.0
    return float(rar / denom)


def compute(equity, periods_per_year: int = TRADING_DAYS_YEAR) -> RobustMetrics:
    """Tính đủ bộ thước bền cộng các thước cũ để đối chiếu.

    Parameters
    ----------
    equity
        Chuỗi **giá trị tài khoản** theo thời gian (phải dương). Không nhận lãi
        lỗ tích luỹ dạng R vì nó có thể âm và log không xác định.
    """
    v = _as_equity(equity)
    n = v.size

    log_ret = np.diff(np.log(v))
    ann_vol = float(log_ret.std(ddof=1) * np.sqrt(periods_per_year)) if n > 2 else 0.0
    ann_mean = float(log_ret.mean() * periods_per_year) if n > 1 else 0.0

    years = n / periods_per_year
    cagr = float(((v[-1] / v[0]) ** (1.0 / years) - 1.0) * 100.0) if years > 0 else 0.0

    dd = drawdown_profile(v, periods_per_year)
    rar = regressed_annual_return(v, periods_per_year)
    net_profit = float(v[-1] / v[0] - 1.0)

    return RobustMetrics(
        rar_pct=rar,
        r_cubed=r_cubed(v, periods_per_year),
        robust_sharpe=float(rar / 100.0 / ann_vol) if ann_vol > 1e-12 else 0.0,
        drawdown=dd,
        cagr_pct=cagr,
        max_drawdown=dd.max_depth,
        sharpe=float(ann_mean / ann_vol) if ann_vol > 1e-12 else 0.0,
        mar=float(cagr / 100.0 / dd.max_depth) if dd.max_depth > 1e-12 else float("inf"),
        net_profit_over_max_dd=(float(net_profit / dd.max_depth)
                                if dd.max_depth > 1e-12 else float("inf")),
        n_points=n,
    )


def equity_from_r_multiples(r_multiples, risk_per_trade: float = 0.0025,
                            initial: float = 100_000.0) -> np.ndarray:
    """Dựng đường vốn từ chuỗi R để dùng được các thước ở trên.

    Phần lớn kết quả nghiên cứu của dự án ở dạng chuỗi R, còn thước bền cần
    đường vốn dương. Hàm này nối hai thứ.

    Dùng **cộng dồn** (`initial × (1 + risk × ΣR)`) chứ không nhân dồn, để khớp
    với cách dự án định cỡ theo phần trăm vốn cố định mỗi lệnh. Nếu về sau chuyển
    sang định cỡ nhân dồn thì phải đổi hàm này cho khớp — ghi rõ để không lệch
    âm thầm giữa hai tầng.
    """
    r = np.asarray(r_multiples, dtype=float)
    if r.size == 0:
        raise ValueError("chuỗi R rỗng")
    eq = initial * (1.0 + risk_per_trade * np.cumsum(r))
    eq = np.r_[initial, eq]
    if np.any(eq <= 0):
        raise ValueError("đường vốn chạm 0 — chuỗi R này làm cháy tài khoản ở mức "
                         f"rủi ro {risk_per_trade:.2%}/lệnh")
    return eq
