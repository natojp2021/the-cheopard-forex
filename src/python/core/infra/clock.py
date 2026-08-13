"""Clock abstraction (Giai đoạn 1 của sáng kiến Virtual Clock + IBroker adapter).

Mục tiêu: Các hàm quyết định-nghiệp-vụ hiện đang gọi thẳng
`datetime.now(timezone.utc)`/`time.time()` (ví dụ: `market_guards.get_server_offset_hours()`)
có thể được "tiêm" một đồng hồ ẢO khi chạy backtest, tick đúng theo timestamp
của từng bar lịch sử, thay vì luôn đọc giờ thật của máy — điều kiện cần để
backtest gọi thẳng `evaluate_and_trade()` (chưa sửa) mà vẫn ra kết quả nhất
quán, tái lập được (không phụ thuộc lúc nào bạn bấm chạy backtest).

Thiết kế tối giản có chủ đích: 1 hàm `now() -> datetime` (UTC, tz-aware).
Không thêm `sleep()`/`schedule()` — vòng lặp live vẫn tự quản lý nhịp riêng
(`engine.py: loop_runner`), Clock chỉ trả lời "bây giờ là mấy giờ".

Mặc định toàn hệ thống là `RealClock` (hành vi live giữ nguyên 100%) — chỉ
backtest driver mới gọi `set_clock(VirtualClock(...))`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


class Clock:
    """Interface cơ sở cho các loại đồng hồ trong hệ thống."""

    def now(self) -> datetime:
        """Trả về thời gian hiện tại (tz-aware UTC)."""
        raise NotImplementedError


class RealClock(Clock):
    """Đồng hồ thời gian thực, sử dụng giờ hệ thống."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class VirtualClock(Clock):
    """Đồng hồ ảo cho backtest.
    
    Driver loop gọi `.set(t)` mỗi khi tiến sang bar/tick lịch sử tiếp theo,
    TRƯỚC khi gọi `evaluate_and_trade()`.
    """

    def __init__(self, t: Optional[datetime] = None):
        """Khởi tạo đồng hồ ảo với thời gian ban đầu."""
        self._t = t or datetime(1970, 1, 1, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._t

    def set(self, t) -> None:
        """Cập nhật thời gian cho đồng hồ ảo.
        
        Args:
            t: `datetime` hoặc `pd.Timestamp` (nếu naive thì mặc định coi như UTC).
        """
        if getattr(t, "tzinfo", None) is None:
            import pandas as pd
            t = pd.Timestamp(t, tz="UTC").to_pydatetime()
        self._t = t


# Đồng hồ mặc định của hệ thống
_default_clock: Clock = RealClock()


def get_clock() -> Clock:
    """Lấy thể hiện đồng hồ hiện tại đang được sử dụng."""
    return _default_clock


def set_clock(clock: Clock) -> None:
    """Thiết lập đồng hồ cho toàn hệ thống."""
    global _default_clock
    _default_clock = clock


def reset_clock() -> None:
    """Đặt lại hệ thống về đồng hồ thời gian thực (RealClock).
    
    Được gọi ở cuối 1 lượt backtest để không rò rỉ VirtualClock
    sang tiến trình/lệnh gọi khác (an toàn khi các test chạy chung process).
    """
    global _default_clock
    _default_clock = RealClock()


def now_utc_ts():
    """Lấy `pd.Timestamp` UTC theo đồng hồ ĐANG hoạt động.

    VÌ SAO CẦN: 51 chỗ trong `live_strategies/` và `core/execution/` gọi thẳng
    `pd.Timestamp.now("UTC")` để đóng dấu `entry_time`. Ở live thì đúng, nhưng
    dưới `VirtualClock` (backtest gọi `evaluate_and_trade()` thật qua SimBroker
    driver) chúng trả GIỜ MÁY LÚC CHẠY BACKTEST, không phải giờ mô phỏng. Hệ
    quả: mọi lệnh trong một lượt backtest có `entry_time` gần như trùng nhau,
    `holding_hours` trong sổ lệnh ~0, và `market_memory` — vốn đọc `entry_time`
    để cắt cửa sổ as-of — không dùng được sổ lệnh backtest.

    VẤN ĐỀ ĐƯỢC GIẢI QUYẾT: Đây là gap "entry_time rogue-wall-clock" ghi lại
    ở Giai đoạn 3 SimBroker mà chưa đóng.

    Trả về tz-aware UTC. Dùng thay cho `pd.Timestamp.now("UTC")` ở MỌI chỗ
    đóng dấu thời gian nghiệp vụ; `time.time()` cho throttle/đo hiệu năng thì
    giữ nguyên vì đó là thời gian tường thật sự.
    """
    import pandas as pd

    return pd.Timestamp(get_clock().now())
