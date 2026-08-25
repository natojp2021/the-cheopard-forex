"""logger.py — logging cho The Cheopard Forex.

VIẾT LẠI 13/08/2026. Bản cũ (182 dòng) là tầng log của một hệ một-tài-sản: nó bơm mọi dòng
sang `timeline_log` để dựng dòng thời gian sự kiện cho GUI command center, và bám
vào một cây thư mục state runtime theo tài khoản. Cả hai thứ đó đã bị xoá cùng
engine cũ, nên module chỉ còn lại một import gãy.

Hệ hiện tại cần đúng ba thứ ở tầng log, không hơn:
  * ghi ra console để chạy nghiên cứu
  * ghi ra file xoay theo NGÀY để truy vết quyết định giao dịch thật
  * KHÔNG có tác dụng phụ lúc import (bản cũ tạo thư mục ngay khi nạp module,
    khiến một script nghiên cứu thuần tuý cũng dựng thư mục vận hành)

Thư mục log chỉ được tạo ở lần ghi ĐẦU TIÊN, không phải lúc import.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Dict, Optional

from src.python.shared.paths import LOG_DIR

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_loggers: Dict[str, logging.Logger] = {}
_file_handler: Optional[logging.Handler] = None

# BỘ NHẬN DÒNG LOG CHO CONSOLE VẬN HÀNH — xem `attach_console_sink()`.
_console_sink = None


def attach_console_sink(sink) -> None:
    """Chuyển hướng phần CONSOLE của mọi logger sang `sink(message, levelno)`.

    VÌ SAO CẦN — HAI ĐỊNH DẠNG TRÊN CÙNG MỘT MÀN HÌNH
    ==================================================
    Hệ có HAI đường ghi log song song, và chúng đến từ hai lớp khác nhau:

        engine.log(...)            -> `log_callback` do điểm vào truyền vào
        utils.logger.log(...)      -> handler console của chính logger này
                                      (mt5_bars, fx_data, ftmo, news_guard…)

    Với giao diện đồ hoạ thì cả hai gặp nhau ở bảng log, vì `gui_command_center`
    thay `sys.stderr` bằng `_Redirector` — tức nó bắt được cả nhánh thứ hai. Console
    không có mẹo đó, nên nếu không bắc cầu ở đây thì màn hình có hai định dạng lẫn
    nhau: dòng của engine đã tô màu và gắn nhóm, còn dòng của `mt5_bars` ra nguyên
    dạng `2026-08-19 22:33:55 | INFO | cheopard | …`.

    Tệ hơn cái xấu: nhánh thứ hai sẽ KHÔNG đi qua bộ nén spam và KHÔNG vào sổ JSONL.
    Đúng những dòng ồn nhất đã đo được (`[FX-M1]`, `DỮ LIỆU CŨ`) lại thuộc nhánh này.

    Chỉ nhận MỘT `sink`: hai bộ hiển thị cùng lúc là hai lần in cùng một dòng.
    """
    global _console_sink
    _console_sink = sink


def _usable_stream(stream) -> bool:
    """Luồng này ghi được không.

    VÌ SAO PHẢI HỎI — LỖI ĐÃ XẢY RA TRÊN MÁY VẬN HÀNH 16/08/2026
    =============================================================
    `start_live_server.vbs` chạy bảng điều khiển bằng `pythonw.exe` để không hiện
    cửa sổ đen. `pythonw` KHÔNG có console, nên `sys.stdout` và `sys.stderr` đều là
    `None` — không phải một luồng đã đóng, mà đúng nghĩa `None`.

    `logging.StreamHandler(stream)` neo luồng ngay lúc KHỞI TẠO (và khi truyền None
    thì nó tự thay bằng `sys.stderr`, tức vẫn là None ở đây). Từ đó mọi lần ghi log
    chạy vào `None.write(...)` và ném `AttributeError`. `logging` bắt lại rồi in
    "--- Logging error ---" kèm nguyên vẹn call stack, nên MỖI dòng log sinh ra
    khoảng 15 dòng rác — đúng thứ đã ngập nhật ký khởi động:

        AttributeError: 'NoneType' object has no attribute 'write'
        Message: '🏦 [FTMO] Chốt vốn ban đầu $100,000.00 — hạn mức lỗ ngày $5,000…'

    Nguy hiểm hơn cả rác: thông điệp GỐC bị chôn dưới call stack. Đúng ba dòng FTMO
    quan trọng nhất lúc khởi động — chốt vốn ban đầu, ngày giao dịch mới, tháng mới
    — đều rơi vào đây. Người vận hành nhìn nhật ký mà không đọc được mốc rủi ro của
    chính ngày hôm đó.

    Không ghi được console thì BỎ handler console; file handler và handler của giao
    diện vẫn chạy, nên không mất dòng log nào. Chạy từ terminal thì `sys.stderr` là
    luồng thật và console vẫn có như cũ.
    """
    if stream is None:
        return False
    write = getattr(stream, "write", None)
    if not callable(write):
        return False
    # Luồng đã đóng vẫn còn `.write` nhưng ném `ValueError` khi gọi. Kiểm bằng cờ
    # `closed` thay vì gọi thử — gọi thử là ghi một dòng rác vào nhật ký thật.
    return not bool(getattr(stream, "closed", False))


class _ConsoleHandler(logging.Handler):
    """Ghi ra `sys.stderr` TẠI THỜI ĐIỂM GHI, không neo luồng lúc khởi tạo.

    VÌ SAO KHÔNG DÙNG THẲNG `logging.StreamHandler`
    ================================================
    `StreamHandler` lưu luồng vào `self.stream` ngay trong `__init__`. Ở hệ này thứ
    tự khởi động làm điều đó sai theo HAI hướng ngược nhau, và chỉ một handler giải
    quyết muộn mới đúng được cả hai:

        1. `pythonw.exe` (bảng điều khiển chạy ẩn) không có console → `sys.stderr`
           là `None` lúc logger khởi tạo. `StreamHandler` neo `None`, và mỗi dòng
           log sau đó ném `AttributeError` rồi nở thành ~15 dòng traceback.

        2. `gui_command_center.__init__` THAY `sys.stdout`/`sys.stderr` bằng
           `_Redirector` để đẩy từng dòng vào bảng log của giao diện — nhưng nó làm
           việc đó SAU khi logger đã khởi tạo. Một handler neo sớm sẽ giữ mãi luồng
           cũ, nên dòng `log()` không bao giờ tới được giao diện.

    Hướng 1 là sự cố ngày 16/08/2026; hướng 2 là hệ quả nếu vá hướng 1 bằng cách chỉ
    bỏ handler khi không có luồng. Giải quyết muộn xử lý cả hai: lúc chưa có console
    thì bỏ qua im lặng, lúc giao diện đã gắn `_Redirector` thì dòng log hiện lên.

    Không có luồng ghi được thì BỎ QUA dòng đó — không ném, không rác. Dòng vẫn nằm
    đủ trong file log, nên không mất bản ghi nào.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Console vận hành đã gắn -> giao dòng cho nó và DỪNG. Nó tự lo dấu thời
        # gian, màu, nhóm, nén spam và sổ JSONL; ghi thêm ra stderr ở đây là in đôi.
        if _console_sink is not None:
            try:
                _console_sink(record.getMessage(), record.levelno)
                return
            except Exception:
                # Bộ hiển thị hỏng thì rơi về stderr chứ không mất dòng log.
                pass
        stream = sys.stderr
        if not _usable_stream(stream):
            return
        try:
            stream.write(self.format(record) + "\n")
            flush = getattr(stream, "flush", None)
            if callable(flush):
                flush()
        except Exception:                       # pragma: no cover
            self.handleError(record)


def _make_file_handler() -> Optional[logging.Handler]:
    """Handler ghi file, xoay theo ngày, giữ 30 ngày.

    Trả None nếu không tạo được thư mục — nghiên cứu vẫn phải chạy được trên máy
    chỉ có quyền đọc, và mất log không phải lý do để dừng một backtest.
    """
    global _file_handler
    if _file_handler is not None:
        return _file_handler
    # TEST KHÔNG ĐƯỢC GHI VÀO SỔ LOG CỦA TIẾN TRÌNH ĐANG CHẠY THẬT.
    #
    # Đo 17:37:26 ngày 21/08/2026 — những dòng này nằm trong
    # `logs/cheopard_forex.log` của bot đang chạy live:
    #
    #     [CIRCUIT BREAKER OPEN] FATAL NON-RETRIABLE ERROR: retcode=10019
    #                            (loi cap tai khoan)
    #
    # `loi cap tai khoan` là chuỗi `comment=` của một FIXTURE trong
    # `test_min_lots_per_symbol_20260821`. Bộ soát log theo giờ đọc chúng như sự
    # cố THẬT của tài khoản, và người đọc log sau này cũng vậy.
    #
    # Cùng họ với ba lỗ rò đã bịt ở một hệ một-tài-sản (`trade_journal`,
    # `allocation_policy`, `durable_event_log`) và với `position_book` ở chính
    # repo này: trạng thái/hiện vật runtime không có ranh giới giữa test và live.
    import os

    if os.environ.get("CHEOPARD_DISABLE_FILE_LOG", "").strip().lower() in {
            "1", "true", "yes"}:
        _file_handler = None
        return None
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        h = TimedRotatingFileHandler(
            LOG_DIR / "cheopard_forex.log", when="midnight",
            backupCount=30, encoding="utf-8")
        h.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
        _file_handler = h
    except OSError:
        _file_handler = None
    return _file_handler


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Logger đã gắn handler console + file. Gọi nhiều lần trả cùng một đối tượng."""
    if name in _loggers:
        return _loggers[name]

    log = logging.getLogger(name)
    log.setLevel(level)
    log.propagate = False              # tránh nhân đôi dòng qua root logger

    if not log.handlers:
        # LUÔN gắn — `_ConsoleHandler` tự quyết ở thời điểm ghi, nên nó đúng cả khi
        # chưa có console (bỏ qua) lẫn khi giao diện gắn `_Redirector` muộn (hiện lên).
        console = _ConsoleHandler()
        console.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))
        log.addHandler(console)
        fh = _make_file_handler()
        if fh is not None:
            log.addHandler(fh)

    _loggers[name] = log
    return log


# ── API tương thích ngược cho tầng FTMO.
# `core/infra/ftmo.py` gọi `log()` / `log_error()` dạng hàm tự do. Giữ đúng chữ ký
# đó thay vì sửa 1.500 dòng luật quỹ — tầng luật FTMO là phần ÍT được phép đụng
# vào nhất trong repo (mỗi hằng số ở đó neo vào một điều khoản trong docs/ftmo/).
_root = None


def _default() -> logging.Logger:
    global _root
    if _root is None:
        _root = get_logger("cheopard")
    return _root


def log(message: str, *args) -> None:
    _default().info(message, *args)


def log_error(message: str, *args) -> None:
    _default().error(message, *args)
