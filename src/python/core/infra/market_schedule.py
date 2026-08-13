"""market_schedule.py — SSOT giờ mở/đóng cửa và chế độ NGỦ ĐÔNG cuối tuần.

QUY ƯỚC GIỜ — VÀ VÌ SAO MỐC MỞ LẠI LÀ 21:00 UTC CHỦ NHẬT
=========================================================
    MỞ CỬA     21:00 UTC Chủ Nhật  →  00:00 UTC Thứ Bảy
    NGỦ ĐÔNG   00:00 UTC Thứ Bảy   →  21:00 UTC Chủ Nhật

21:00 UTC Chủ Nhật chính là **00:00 Thứ Hai theo giờ máy chủ broker** (FTMO chạy
GMT+3 mùa hè, GMT+2 mùa đông). Nghĩa là hệ tỉnh dậy đúng lúc nến ngày đầu tuần của
broker mở — không sớm hơn, vì trước đó thanh khoản gần như bằng không và spread giãn
gấp nhiều lần; không muộn hơn, vì bỏ mất phần đầu phiên.

Đây cũng là lý do KHÔNG dùng 00:00 UTC làm mốc: 00:00 UTC Thứ Hai đã là 03:00 giờ
broker, tức trễ ba tiếng so với lúc thị trường thật sự mở.

KHI NGỦ ĐÔNG (`is_market_closed() -> True`)
============================================
    1. Engine   ngừng quét tín hiệu, KHÔNG dựng kế hoạch, KHÔNG đặt lệnh mới
    2. Cổng tin ngừng gọi LLM và ngừng cào tin — không có tin cuối tuần
    3. Dữ liệu  ngừng fetch nến mới
    4. GUI      hiện trạng thái STAND-BY
    5. Nhịp tim VẪN chạy — để watchdog không tưởng hệ đã chết mà khởi động lại

⚠️ NGỦ ĐÔNG KHÔNG ĐÓNG VỊ THẾ. Danh mục này CỐ Ý giữ lệnh qua cuối tuần: time-stop
ngắn nhất là 12 nến H4 (2 ngày), dài nhất là chu kỳ tái cân bằng 21 ngày của hai
chân D1. Đóng hết vào tối Thứ Sáu rồi mở lại tối Chủ Nhật là trả thêm một lượt
spread đầy đủ cho mỗi vị thế mỗi tuần — với 24 công cụ thì đó là khoản phí lớn hơn
nhiều so với rủi ro gap (đo được: gap cuối tuần tệ nhất của rổ FX 2,138%, và Thứ Hai
là ngày AN TOÀN NHẤT tuần của danh mục — xem `core/infra/target_mode.py`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from src.python.shared.paths import RUNTIME_STATE_DIR

# Giờ UTC thị trường mở lại vào Chủ Nhật = 00:00 giờ máy chủ broker Thứ Hai.
SUNDAY_OPEN_HOUR_UTC = 21


def _as_utc(now_utc: Optional[datetime] = None) -> datetime:
    if now_utc is None:
        return datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        return now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(timezone.utc)


def is_market_closed(now_utc: Optional[datetime] = None) -> bool:
    """Thị trường có đang đóng (NGỦ ĐÔNG) không.

        Thứ Bảy      đóng CẢ NGÀY
        Chủ Nhật     đóng TRƯỚC 21:00 UTC
    """
    t = _as_utc(now_utc)
    wd = t.weekday()                       # Thứ Hai = 0 … Chủ Nhật = 6
    if wd == 5:
        return True
    return wd == 6 and t.hour < SUNDAY_OPEN_HOUR_UTC


def next_open_utc(now_utc: Optional[datetime] = None) -> datetime:
    """Thời điểm UTC thị trường mở lại. Đang mở thì trả về chính `now`."""
    t = _as_utc(now_utc)
    if not is_market_closed(t):
        return t
    # Chủ Nhật trước giờ mở → mở ngay hôm nay; Thứ Bảy → mở vào Chủ Nhật.
    days = 0 if t.weekday() == 6 else (6 - t.weekday())
    return (t + timedelta(days=days)).replace(
        hour=SUNDAY_OPEN_HOUR_UTC, minute=0, second=0, microsecond=0)


def seconds_to_open(now_utc: Optional[datetime] = None) -> float:
    """Còn bao nhiêu giây tới lúc mở lại. Đang mở thì 0."""
    t = _as_utc(now_utc)
    if not is_market_closed(t):
        return 0.0
    return max(0.0, (next_open_utc(t) - t).total_seconds())


def describe(now_utc: Optional[datetime] = None, *, countdown: bool = True) -> str:
    """Một câu đọc được cho email và cho thẻ trạng thái trên GUI.

    `countdown=False` bỏ phần "(còn xx giờ)". Thẻ trên giao diện vẽ lại mỗi 5 giây,
    nên một con số giờ lẻ đếm lùi ở đó chỉ nhấp nháy chứ không nói thêm điều gì —
    MỐC MỞ LẠI đã có sẵn ngay bên cạnh. Trong EMAIL thì ngược lại: người đọc nhận
    thư một lần, không có gì để so, nên khoảng cách thời gian là thông tin thật.
    """
    t = _as_utc(now_utc)
    if not is_market_closed(t):
        return "thị trường ĐANG MỞ"
    s = f"NGỦ ĐÔNG cuối tuần — mở lại {next_open_utc(t):%Y-%m-%d %H:%M} UTC"
    if countdown:
        s += f" (còn {seconds_to_open(t) / 3600.0:.1f} giờ)"
    return s


# Không có `is_market_open()`: dùng `not is_market_closed()`. Hai hàm phủ định nhau
# là hai chỗ để sửa khi đổi lịch, và một trong hai sẽ bị quên.


# ═══════════════════════════════════════════════════════ PHA THỊ TRƯỜNG BỀN VỮNG
# VẤN ĐỀ (hệ XAUUSD báo 14/08, hệ này mắc y hệt — sửa 15/08/2026):
# email "NGỦ ĐÔNG" sáng thứ Bảy tới đều đặn, nhưng email "THỨC DẬY" sáng thứ Hai
# CHƯA BAO GIỜ tới.
#
# VÌ SAO: cờ "pha trước đó" chỉ là thuộc tính trong BỘ NHỚ. Nó phải sống từ lúc thị
# trường đóng (00:00 UTC thứ Bảy) tới lúc mở lại (21:00 UTC Chủ Nhật), tức **~45 giờ
# liên tục**. Bất kỳ lần khởi động lại nào trong quãng đó — VPS reboot, watchdog kill
# vì heartbeat cũ, hay người vận hành tắt bot cuối tuần — đều đưa cờ về `None`, và
# nhánh gửi email bị chặn bởi điều kiện `prev is not None`.
#
# Chiều ngược lại KHÔNG BAO GIỜ hỏng, và đó là lý do lỗi này sống lâu: lúc thị trường
# ĐÓNG, bot đã chạy liên tục suốt phiên thứ Sáu nên cờ luôn còn nguyên. Một lỗi chỉ
# hỏng ở MỘT chiều thì nhìn vào log vẫn thấy "email vẫn chạy".
#
# Đây là họ lỗi "trạng thái vòng đời chỉ nằm trong RAM" đã cắn dự án nhiều lần —
# cùng họ với `bars_held` không có ai tính (xem `execution/position_book.py`). Cách
# chữa giống nhau: GHI XUỐNG ĐĨA, đọc lại lúc khởi động.

PHASE_PATH = Path(RUNTIME_STATE_DIR) / "market_phase.json"


def load_phase(path: Optional[Path] = None) -> Optional[bool]:
    """Pha thị trường lần cuối đã ghi. `None` = chưa từng ghi (lần chạy đầu tiên).

    Phân biệt `None` với `False` là điểm mấu chốt: `False` nghĩa là "lần trước thị
    trường ĐANG MỞ" — một thông tin thật; `None` nghĩa là "chưa biết gì". Gộp hai
    thứ đó lại chính là cách email thức dậy biến mất.
    """
    from src.python.core.infra import state_store

    d = state_store.load_json(Path(path) if path is not None else PHASE_PATH)
    if not d or "closed" not in d:
        return None
    return bool(d["closed"])


def save_phase(closed: bool, path: Optional[Path] = None) -> bool:
    """Ghi pha hiện tại. Gọi mỗi lần kiểm, không chỉ khi đổi.

    Ghi cả khi không đổi vì chi phí gần bằng 0 và nó làm file luôn phản ánh lần kiểm
    gần nhất — nếu chỉ ghi lúc đổi thì một lần đổi bị mất là mất vĩnh viễn.
    """
    from src.python.core.infra import state_store

    return state_store.save_json_atomic(
        Path(path) if path is not None else PHASE_PATH,
        {"closed": bool(closed),
         "updated_utc": datetime.now(timezone.utc).isoformat()})
