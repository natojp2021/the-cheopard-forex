"""Thời điểm theo ĐỒNG HỒ MÁY CHỦ BROKER (MT5 server clock) — dùng cho email.

VÌ SAO CẦN: Các email tín hiệu bị chặn/từ chối trước đây chỉ có
một dòng thời gian lấy từ đồng hồ máy chạy bot quy về GMT+7.
Khi đối chiếu với chart/history trong terminal MT5 (luôn hiển thị theo 
giờ máy chủ broker) người vận hành phải tự cộng/trừ offset trong đầu. 
Hàm này cung cấp dòng thứ hai: giờ đúng như broker thấy, đọc từ `tick.time` 
của tick mới nhất.

Quy ước chuyển đổi giữ nguyên văn cách toàn hệ thống đang làm (xem
`live_strategies/market_guards.get_server_offset_hours()` và `core/engine.py`
chỗ tính `sod_epoch`): `tick.time` là epoch nhưng đã mang giờ máy chủ, nên
sử dụng `fromtimestamp(..., tz=utc)` rồi bỏ tzinfo mới ra đúng "giờ trên chart MT5" —
không chuyển timezone thêm lần nữa.

CHỈ ĐỂ HIỂN THỊ: Không hàm nào ở đây tham gia quyết định entry/exit/sizing, và
mọi lỗi đều trả `None` (bên gọi bỏ dòng đó khỏi email) thay vì raise ngoại lệ — 
thiếu một dòng thời gian không được phép làm mất cả email cảnh báo.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

# Định dạng thời gian chuẩn để hiển thị giờ broker trong email
BROKER_TIME_FMT = "%Y-%m-%d %H:%M:%S"


def broker_time_str(tick: Any, fmt: str = BROKER_TIME_FMT) -> Optional[str]:
    """Giờ máy chủ broker tại thời điểm `tick` (duck-type: chỉ cần có thuộc tính `.time` 
    là epoch giây, khớp cả `mt5.symbol_info_tick()` thật và `sim_broker` trong backtest).

    Trả về `None` nếu không có tick hoặc `tick.time` rỗng/không hợp lệ (ví dụ: cuối tuần,
    terminal mất kết nối, hoặc symbol chưa được chọn trong Market Watch).
    """
    try:
        epoch = int(getattr(tick, "time", 0) or 0)
        if epoch <= 0:
            return None
        return datetime.fromtimestamp(epoch, tz=timezone.utc).replace(tzinfo=None).strftime(fmt)
    except Exception:
        return None


def broker_time_str_from_mt5(mt5: Any, symbol: str,
                             fmt: str = BROKER_TIME_FMT) -> Optional[str]:
    """Giống như `broker_time_str()` nhưng tự động đọc tick mới nhất của `symbol`.

    Dùng ở những chỗ có sẵn handle `mt5` (thật hoặc SimBroker) mà không có sẵn
    tick (ví dụ: `PortfolioAllocationEngine.compute()`). Việc này thêm 1 lần đọc tick, 
    nhưng chỉ xảy ra trên nhánh gửi email (hiếm khi gọi), không nằm trên đường dẫn 
    nóng (hot path) của mỗi chu kỳ.
    """
    try:
        return broker_time_str(mt5.symbol_info_tick(symbol), fmt=fmt)
    except Exception:
        return None
