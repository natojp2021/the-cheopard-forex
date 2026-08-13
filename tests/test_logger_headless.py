# -*- coding: utf-8 -*-
"""Tầng log phải đúng ở CẢ HAI đầu của thứ tự khởi động bảng điều khiển.

SỰ CỐ ĐÃ XẢY RA (máy vận hành, 16/08/2026)
===========================================
`start_live_server.vbs` chạy bảng điều khiển bằng `pythonw.exe` để không hiện cửa sổ
đen. `pythonw` không có console: `sys.stdout` và `sys.stderr` là `None`.

`logging.StreamHandler` neo luồng lúc KHỞI TẠO, nên nó giữ `None` và mọi lần ghi log
ném `AttributeError: 'NoneType' object has no attribute 'write'`. `logging` bắt lại
rồi in "--- Logging error ---" kèm nguyên call stack — mỗi dòng log nở thành ~15
dòng rác, và thông điệp GỐC bị chôn bên dưới. Ba dòng FTMO quan trọng nhất lúc khởi
động (chốt vốn ban đầu · ngày giao dịch mới · tháng mới) đều rơi vào đây.

CÁI BẪY THỨ HAI, NGƯỢC HƯỚNG
=============================
`gui_command_center.__init__` THAY `sys.stdout`/`sys.stderr` bằng `_Redirector` để
đẩy từng dòng vào bảng log của giao diện — nhưng nó làm việc đó SAU khi logger đã
khởi tạo. Nên bản vá kiểu "không có luồng thì đừng gắn handler" chữa được rác nhưng
lại làm MỌI dòng `log()` biến mất khỏi giao diện.

Đó là lý do trong nhật ký sự cố, `🏦 [FTMO] Pha tài khoản` hiện sạch (đi bằng
`print` → stdout → `_Redirector`) còn `🏦 [FTMO] Chốt vốn ban đầu` thì vỡ (đi bằng
`log()` → handler neo vào None).

Hai test dưới đây ghim hai đầu đó. Chúng kiểm HÀNH VI — ghim luồng rồi đòi kết quả —
chứ không kiểm sự hiện diện của một dòng code.
"""
from __future__ import annotations

import logging
import sys


def _fresh(monkeypatch):
    """Nạp lại `logger` với bộ nhớ đệm sạch — module cache logger theo tên."""
    from src.python.utils import logger as L

    monkeypatch.setattr(L, "_loggers", {}, raising=False)
    monkeypatch.setattr(L, "_root", None, raising=False)
    return L


class _Sink:
    """Thế thân của `_Redirector` trong giao diện: gom từng dòng ghi vào."""

    closed = False

    def __init__(self):
        self.lines = []

    def write(self, s):
        if s.strip():
            self.lines.append(s.strip())

    def flush(self):
        pass


def test_logging_survives_without_console(monkeypatch):
    """Không có `sys.stderr` thì ghi log KHÔNG được ném và KHÔNG được sinh rác."""
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(sys, "stdout", None)
    L = _fresh(monkeypatch)

    errors = []
    monkeypatch.setattr(logging.Handler, "handleError",
                        lambda self, record: errors.append(record))

    lg = L.get_logger("test_headless")
    assert lg.handlers, "logger không có handler nào"

    # Đường hàm tự do mà tầng FTMO dùng (`ftmo.py` gọi `log()` trực tiếp).
    L.log("🏦 [FTMO] Chốt vốn ban đầu $100,000.00")
    L.log_error("MT5 không trả được nến M1 cho EURUSD")

    assert not errors, (
        f"{len(errors)} lỗi logging khi không có console — mỗi lỗi in ~15 dòng "
        f"traceback và chôn mất thông điệp gốc")


def test_log_reaches_stderr_installed_after_logger_was_built(monkeypatch):
    """Giao diện gắn `_Redirector` MUỘN — dòng log vẫn phải tới được nó.

    Đây là bất biến giữ cho bảng log của giao diện không rỗng. Handler neo luồng lúc
    khởi tạo sẽ trượt test này.
    """
    monkeypatch.setattr(sys, "stderr", None)        # trạng thái `pythonw` lúc đầu
    L = _fresh(monkeypatch)
    lg = L.get_logger("test_late_stream")
    L.log("dòng phát ra khi CHƯA có giao diện")     # phải im lặng, không ném

    sink = _Sink()                                   # giao diện khởi động ở đây
    monkeypatch.setattr(sys, "stderr", sink)
    L.log("🏦 [FTMO] Chốt vốn ban đầu $100,000.00")

    assert any("Chốt vốn ban đầu" in x for x in sink.lines), (
        "dòng log KHÔNG tới được luồng gắn sau — bảng log giao diện sẽ rỗng "
        f"(đã nhận: {sink.lines})")
    assert not any("CHƯA có giao diện" in x for x in sink.lines), (
        "dòng phát trước khi có luồng lại xuất hiện — handler đang đệm lại quá khứ")
    assert lg.handlers


def test_console_output_still_works_from_terminal(monkeypatch):
    """Chạy nghiên cứu từ terminal thì console vẫn phải có — bản vá không cắt mất."""
    sink = _Sink()
    monkeypatch.setattr(sys, "stderr", sink)
    L = _fresh(monkeypatch)
    L.get_logger("test_terminal")
    L.log("dòng nghiên cứu")
    assert any("dòng nghiên cứu" in x for x in sink.lines), \
        "mất đầu ra console khi stderr là luồng thật"


def test_closed_stream_is_not_written_to(monkeypatch):
    """Luồng ĐÃ ĐÓNG còn `.write` nhưng ném khi gọi — phải bị từ chối như None."""
    L = _fresh(monkeypatch)

    class _Closed:
        closed = True

        def write(self, _):                     # pragma: no cover - không được gọi
            raise AssertionError("đã ghi vào luồng ĐÃ ĐÓNG")

        def flush(self):                        # pragma: no cover
            pass

    monkeypatch.setattr(sys, "stderr", _Closed())
    L.get_logger("test_closed_stream")
    L.log("dòng này không được ghi và không được ném")
