"""Rổ cross rỗng phải trả khung ĐÚNG HÌNH DẠNG, không được ném.

SỰ CỐ 21:52:42 NGÀY 20/08/2026 — CÙNG HỘT, KHÁC VỎ
===================================================
Sau khi vá `evaluate_cross` cho chuỗi rỗng, đúng nguyên nhân gốc quay lại ở tầng
kế bên:

    KeyError: 'entry_time'
      cross_mean_reversion.backtest, dòng 286
      return pd.DataFrame(rows).sort_values("entry_time")

`rows` rỗng → `DataFrame([])` không có cột nào → `sort_values("entry_time")` nổ →
`portfolio.live_targets` nổ → `_build_plan` nổ → **cả 27 chân đứng im**. Đúng
chuỗi hậu quả của sự cố 19:14, chỉ khác chỗ vấp.

Bài học ghi lại ở đây vì nó sẽ còn lặp: rổ RỖNG là trạng thái BÌNH THƯỜNG của thị
trường (một công cụ mất nến, cuối tuần, terminal chưa tải xong lịch sử), không
phải lỗi lập trình. Mọi hàm trên đường `live_targets` phải đi qua được nó.

Và sửa nửa vời thì chỉ đổi ngoại lệ này lấy ngoại lệ khác: bản vá đầu trả
`DataFrame(columns=[...])`, khiến `entry_time` mang dtype `object`, và `daily_pnl`
nổ tiếp `TypeError: Only valid with DatetimeIndex`. Kiểu dữ liệu cũng là một phần
của "đúng hình dạng".
"""
from __future__ import annotations

import pandas as pd

from src.python.strategies.h1 import cross_mean_reversion as XMR

COLUMNS = ["entry_time", "exit_time", "cross", "side", "entry_z", "exit_reason",
           "bars_held", "gross_bps", "cost_bps", "swap_bps", "net_bps"]


def _empty_like_backtest(monkeypatch) -> pd.DataFrame:
    """Chạy `backtest()` với rổ cross RỖNG — đúng tình huống đã gây sự cố."""
    monkeypatch.setattr(
        XMR.CX, "build_crosses",
        lambda timeframe="H1", start="2020-01-01": (
            pd.DataFrame(index=pd.DatetimeIndex([])), {}))
    monkeypatch.setattr(
        XMR.CC, "rate_series",
        lambda idx: pd.DataFrame(index=pd.DatetimeIndex([])))
    return XMR.backtest()


def test_empty_basket_returns_frame_not_exception(monkeypatch) -> None:
    df = _empty_like_backtest(monkeypatch)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0
    assert list(df.columns) == COLUMNS


def test_empty_frame_has_datetime_dtypes(monkeypatch) -> None:
    """`entry_time` phải là datetime64 — `daily_pnl` resample trên chính cột này."""
    df = _empty_like_backtest(monkeypatch)
    assert str(df["entry_time"].dtype).startswith("datetime64")
    assert str(df["exit_time"].dtype).startswith("datetime64")


def test_downstream_survives_empty_frame(monkeypatch) -> None:
    """`daily_pnl` và `stats` phải chạy qua khung rỗng — đó là cả điểm của bản vá.

    Test này mới là test THẬT: kiểm khung rỗng có đúng cột thì chưa đủ, vì bản vá
    đầu tiên qua được phép kiểm đó mà vẫn làm `daily_pnl` nổ.
    """
    df = _empty_like_backtest(monkeypatch)
    s = XMR.daily_pnl(df)
    assert len(s) == 0
    assert XMR.stats(s, "rỗng")["n"] == 0
