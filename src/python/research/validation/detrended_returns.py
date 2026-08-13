"""detrended_returns.py — khử xu hướng thị trường trước khi tính lợi suất luật.

REFERENCES
==========
Primary Reference
-----------------
Aronson, D. (2007). *Evidence-Based Technical Analysis: Applying the Scientific
Method and Statistical Inference to Trading Signals*. Wiley.
  * Ch. 1 "Objective Rules and Their Evaluation", tr. 27-29 — đặc tả đầy đủ phép
    khử xu hướng và lý do nó tương đương với việc dựng mốc chuẩn riêng cho từng
    mức thiên lệch vị thế.
  * Ch. 9 "Case Study Results and the Future of TA", tr. 448 — xác nhận case
    study 6.402 luật dùng dữ liệu đã khử xu hướng để tính lợi suất luật.

Supporting References
---------------------
* López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley.
  Ch. 11 tr. 152 — "bảy tội", trong đó tội thứ ba là kể chuyện sau sự việc; khử
  xu hướng loại bỏ một nguồn chính của những câu chuyện ấy.
* Chan, E.P. (2013). *Algorithmic Trading*. Wiley. Ch. 1 ví dụ 1.1 — chuỗi ngẫu
  nhiên cùng độ nhọn tái tạo được lợi nhuận chiến lược momentum trong 12% số
  lần; cùng tinh thần "phải có mốc chuẩn đúng".

Confirmed by: Aronson (2007) ch.1 và ch.9; tinh thần nhất quán với López de
Prado (2018) ch.11 và Chan (2013) ch.1.

VÌ SAO MODULE NÀY TỒN TẠI
==========================
Dự án đã vấp "long-bias artifact" ba lần — DON-H4 (19/07), H4-Metals (20/07),
MOMBURST (27/07). Mỗi lần một chiến lược CHỈ MUA trông có lãi, và mỗi lần phải
dựng lại một phép đối chứng vào-lệnh-ngẫu-nhiên từ đầu để phát hiện rằng lợi
nhuận ấy đến từ việc vàng tăng 11 lần trong mẫu, không từ kỹ năng định thời.

Aronson tr. 27 gọi cách làm ấy là "quite burdensome when many rules are being
tested. It would require that a separate benchmark be computed for each rule
based on its particular position bias." Và ông đưa ra cách rẻ hơn:

    "The easier method merely requires that the historical data for the market
     being traded be detrended prior to rule testing."

Sau khi khử xu hướng, luật KHÔNG có khả năng dự báo có lợi suất kỳ vọng đúng
bằng **không**, bất kể nó thiên về mua hay bán bao nhiêu:

    ER = [p(long) × lợi suất ngày TB] − [p(short) × lợi suất ngày TB]

Với lợi suất ngày trung bình bằng 0 thì `p(long)` và `p(short)` không còn quan
trọng — ER luôn bằng 0 (Aronson tr. 28).

RÀNG BUỘC QUAN TRỌNG NHẤT, DỄ CÀI SAI
======================================
Trích nguyên văn Aronson tr. 27:

    "It is important to point out that the detrended data is used **only for the
     purpose of calculating daily rule returns. It is not used for signal
     generation** if the time series of the market being traded is also being
     used as a rule input series. Signals would be generated from actual market
     data (not detrended)."

Nghĩa là quy trình có HAI chuỗi giá chạy song song:

    tín hiệu   ← chuỗi giá THẬT
    lợi suất   ← chuỗi giá ĐÃ KHỬ XU HƯỚNG

Dùng chuỗi đã khử để sinh tín hiệu là sai — nó tạo ra một thị trường không tồn
tại, và mọi ngưỡng (Donchian, ATR, đường trung bình) sẽ khác đi.

API của module này ép đúng ràng buộc ấy: `evaluate_positions()` nhận chuỗi vị
thế đã sinh từ dữ liệu thật, và chỉ nhận thêm chuỗi giá để tự khử xu hướng bên
trong. Nó không bao giờ trả về chuỗi giá đã khử cho caller dùng sinh tín hiệu.

DÙNG LOG THAY VÌ PHẦN TRĂM
===========================
Aronson tr. 28-29 khuyến nghị dùng log của tỉ số giá thay vì phần trăm, và khử
xu hướng theo đúng cách ấy: tính log tỉ số từng ngày, lấy trung bình, trừ trung
bình khỏi từng ngày.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
import pandas as pd


@dataclass
class DetrendedResult:
    """Kết quả đo một luật trên dữ liệu đã khử xu hướng."""

    n_bars: int
    n_bars_in_market: int
    total_log_return: float
    mean_per_bar: float
    std_per_bar: float
    sharpe_per_bar: float
    # Cùng phép đo nhưng trên dữ liệu GỐC — để thấy phần nào đến từ drift.
    total_log_return_raw: float
    drift_per_bar: float

    @property
    def drift_contribution(self) -> float:
        """Phần lợi suất gốc đến từ drift thị trường, KHÔNG từ định thời.

        Bằng hiệu giữa lợi suất trên dữ liệu gốc và trên dữ liệu đã khử. Con số
        này chính là "long-bias artifact" đo được thành số.
        """
        return self.total_log_return_raw - self.total_log_return

    def summary(self) -> str:
        return (
            f"n={self.n_bars} ({self.n_bars_in_market} nến có vị thế)\n"
            f"  lợi suất log TRÊN DỮ LIỆU GỐC     {self.total_log_return_raw:+.4f}\n"
            f"  lợi suất log ĐÃ KHỬ XU HƯỚNG      {self.total_log_return:+.4f}\n"
            f"  phần đến từ drift thị trường      {self.drift_contribution:+.4f}"
            f"  ({self.drift_contribution / self.total_log_return_raw:.0%} của tổng)"
            if abs(self.total_log_return_raw) > 1e-12 else
            f"n={self.n_bars}: lợi suất gốc xấp xỉ 0, không tách được phần drift"
        )


def _log_returns(close: Sequence[float]) -> np.ndarray:
    """Log của tỉ số giá từng nến — Aronson tr. 28-29 khuyến nghị thay cho %."""
    c = np.asarray(close, dtype=np.float64)
    if c.ndim != 1:
        raise ValueError("close phải là chuỗi một chiều.")
    if len(c) < 2:
        raise ValueError("cần ít nhất 2 giá để tính lợi suất.")
    if not np.isfinite(c).all() or (c <= 0).any():
        raise ValueError("close chứa giá trị không hợp lệ (NaN, inf, hoặc <= 0).")
    r = np.full(len(c), np.nan)
    r[1:] = np.log(c[1:] / c[:-1])
    return r


def detrend_log_returns(close: Sequence[float]) -> np.ndarray:
    """Lợi suất log đã trừ đi trung bình — chuỗi kết quả có drift bằng 0.

    Aronson tr. 28: *"one first determines the average daily price change of the
    market being traded over the historical test period. This average value is
    then subtracted from each day's price change."*

    Trả về mảng cùng độ dài `close`, phần tử đầu là NaN (không có nến trước).

    CẢNH BÁO: kết quả chỉ dùng để TÍNH LỢI SUẤT. Không dùng để sinh tín hiệu —
    xem phần ràng buộc ở đầu module.
    """
    r = _log_returns(close)
    drift = np.nanmean(r)
    return r - drift


def market_drift_per_bar(close: Sequence[float]) -> float:
    """Drift trung bình mỗi nến, tính bằng log tỉ số giá."""
    return float(np.nanmean(_log_returns(close)))


def evaluate_positions(
    positions: Sequence[float],
    close: Sequence[float],
    already_lagged: bool = False,
) -> DetrendedResult:
    """Đo một luật trên dữ liệu đã khử xu hướng.

    Args:
        positions: chuỗi vị thế cùng độ dài `close`. `+1` mua, `−1` bán, `0`
            đứng ngoài; giá trị phân số được chấp nhận cho định cỡ liên tục.
            **Phải được sinh từ dữ liệu giá THẬT**, không phải dữ liệu đã khử.
        close: chuỗi giá đóng nến gốc, chưa khử xu hướng.
        already_lagged: `False` (mặc định) nghĩa là `positions[t]` là quyết định
            đưa ra TẠI nến `t`, nên lợi suất nó hưởng là của nến `t+1`; hàm sẽ
            tự dịch. Đặt `True` nếu caller đã dịch sẵn.

            Mặc định `False` là lựa chọn fail-safe có chủ đích: quên dịch sẽ tạo
            thiên lệch nhìn trước, đúng thứ Aronson tr. 29-30 cảnh báo, và một
            mặc định "tự dịch" thì sai lệch về phía thận trọng chứ không về phía
            thổi phồng.

    Returns:
        `DetrendedResult` kèm cả con số trên dữ liệu gốc, để thấy phần nào của
        lợi nhuận đến từ drift thị trường.
    """
    pos = np.asarray(positions, dtype=np.float64)
    if pos.shape[0] != len(close):
        raise ValueError(
            f"positions dài {pos.shape[0]} nhưng close dài {len(close)} — "
            f"hai chuỗi phải cùng trục thời gian.")
    if not np.isfinite(pos).all():
        raise ValueError("positions chứa NaN/inf — thay bằng 0 nếu đứng ngoài.")

    r_raw = _log_returns(close)
    drift = float(np.nanmean(r_raw))
    r_det = r_raw - drift

    if already_lagged:
        p = pos
    else:
        # Quyết định tại nến t hưởng lợi suất của nến t+1.
        p = np.full_like(pos, np.nan)
        p[1:] = pos[:-1]

    ok = np.isfinite(p) & np.isfinite(r_det)
    pnl_det = p[ok] * r_det[ok]
    pnl_raw = p[ok] * r_raw[ok]
    in_market = int(np.count_nonzero(p[ok]))

    sd = float(pnl_det.std(ddof=1)) if len(pnl_det) > 1 else 0.0
    mean = float(pnl_det.mean()) if len(pnl_det) else 0.0
    return DetrendedResult(
        n_bars=int(ok.sum()),
        n_bars_in_market=in_market,
        total_log_return=float(pnl_det.sum()),
        mean_per_bar=mean,
        std_per_bar=sd,
        sharpe_per_bar=(mean / sd) if sd > 0 else 0.0,
        total_log_return_raw=float(pnl_raw.sum()),
        drift_per_bar=drift,
    )


def evaluate_trades(
    entry_idx: Sequence[int],
    exit_idx: Sequence[int],
    direction: Sequence[int],
    close: Sequence[float],
) -> DetrendedResult:
    """Đo một sổ LỆNH (vào/ra rời rạc) trên dữ liệu đã khử xu hướng.

    Tiện cho các chiến lược của dự án vốn sinh lệnh rời rạc chứ không sinh chuỗi
    vị thế liên tục. Hàm dựng chuỗi vị thế từ sổ lệnh rồi gọi `evaluate_positions`.

    Args:
        entry_idx, exit_idx: chỉ số nến vào và ra, cùng độ dài.
        direction: `+1` mua, `−1` bán, cùng độ dài với hai chuỗi trên.
        close: chuỗi giá gốc.

    Lưu ý: vị thế được coi là nắm giữ từ nến `entry_idx` tới hết nến
    `exit_idx − 1`, tức lợi suất của nến ra KHÔNG được tính hai lần.
    """
    e = np.asarray(entry_idx, dtype=int)
    x = np.asarray(exit_idx, dtype=int)
    d = np.asarray(direction, dtype=np.float64)
    if not (len(e) == len(x) == len(d)):
        raise ValueError("entry_idx, exit_idx và direction phải cùng độ dài.")
    if len(e) and (x <= e).any():
        raise ValueError("mọi exit_idx phải lớn hơn entry_idx tương ứng.")

    pos = np.zeros(len(close), dtype=np.float64)
    for a, b, s in zip(e, x, d):
        if a < 0 or b > len(close):
            raise ValueError(f"chỉ số lệnh ({a}, {b}) nằm ngoài chuỗi giá.")
        pos[a:b] += s
    # Chuỗi `pos` ở đây đã là vị thế ĐANG NẮM tại mỗi nến, nên không dịch nữa.
    return evaluate_positions(pos, close, already_lagged=True)
