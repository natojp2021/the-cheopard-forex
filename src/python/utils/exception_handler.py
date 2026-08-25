"""
exception_handler.py — Module quản lý ngoại lệ (Exception Handling) tập trung và chống Crash toàn diện.
Cung cấp decorator @safe_guard, context manager safe_execute, và Global Exception Hook
để bắt mọi lỗi phát sinh từ hàm/luồng phụ, ghi log stacktrace chi tiết, gửi email cảnh báo
và trả về giá trị an toàn (fallback) để đảm bảo BOT hoạt động 24/5 không bao giờ sập.
"""

import sys
import time
import threading
import traceback
from functools import wraps
from typing import Any, Callable
from datetime import datetime
import os
from src.python.utils.logger import log, log_error

try:
    from src.python.utils.env_loader import load_env_file
    load_env_file()
except Exception:
    pass

BOT_NAME = os.environ.get("BOT_NAME", "THE CHEOPARD")

# Bộ đệm điều tiết gửi email cảnh báo lỗi (chống spam email khi lỗi lặp lại trong vòng lặp)
_EMAIL_THROTTLE_LOCK = threading.Lock()
_LAST_EMAIL_TIMES = {}
EMAIL_THROTTLE_INTERVAL = 300.0  # 5 phút (300s) cho mỗi chữ ký lỗi (Error Signature)
_MAX_THROTTLE_ENTRIES = 500      # chặn dict phình vô hạn khi chạy dài (nhiều chữ ký lỗi khác nhau)

# Lỗi Fatal luôn bị reraise (không fail-soft) vì môi trường chạy không còn tin cậy.
FATAL_EXCEPTION_TYPES = (MemoryError, RecursionError, SystemError, ImportError)


def is_fatal_exception(exc: BaseException) -> bool:
    """True nếu exception thuộc nhóm FATAL_EXCEPTION_TYPES — môi trường/tiến trình không
    còn đáng tin cậy, không nên fail-soft dù caller có truyền reraise=False hay không."""
    return isinstance(exc, FATAL_EXCEPTION_TYPES)


def send_exception_alert_email(error_sig: str, exc_info: str, context: str = ""):
    """
    Gửi email khẩn cấp đến người giám sát khi xảy ra ngoại lệ/crash.
    Có cơ chế chống spam (Throttling 5 phút cho cùng 1 vị trí lỗi).
    """
    now = time.time()
    with _EMAIL_THROTTLE_LOCK:
        last_time = _LAST_EMAIL_TIMES.get(error_sig, 0.0)
        if now - last_time < EMAIL_THROTTLE_INTERVAL:
            # Đã gửi cảnh báo cho lỗi này trong vòng 5 phút qua -> Bỏ qua để chống spam
            return
        # Dọn các chữ ký lỗi đã quá hạn throttle nếu dict phình quá lớn (tránh rò rỉ bộ nhớ)
        if len(_LAST_EMAIL_TIMES) >= _MAX_THROTTLE_ENTRIES:
            expired = [k for k, t in _LAST_EMAIL_TIMES.items() if now - t >= EMAIL_THROTTLE_INTERVAL]
            for k in expired:
                del _LAST_EMAIL_TIMES[k]
        _LAST_EMAIL_TIMES[error_sig] = now

    try:
        # ⚠️ SỬA 15/08/2026 — EMAIL CẢNH BÁO LỖI CHƯA TỪNG GỬI ĐƯỢC.
        # Bản port từ một hệ một-tài-sản gọi `shared.notifications.email_reporter`, module
        # KHÔNG TỒN TẠI ở hệ này. Mỗi lần có ngoại lệ, khối này ném `ModuleNotFound`
        # ngay dòng đầu, rơi vào `except` bên dưới và chỉ ghi một dòng log —
        # tức đúng kênh sinh ra để báo lỗi khi không ai nhìn màn hình thì im lặng
        # hỏng. Nay dùng `utils/mailer.py`, SSOT của SMTP ở repo này.
        cfg = None

        subject = f"🚨 [CRITICAL ERROR] Ngoại lệ hệ thống {BOT_NAME} — {error_sig[:40]}"
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        text = (
            f"Cảnh báo lỗi nghiêm trọng từ hệ thống {BOT_NAME} (the-cheopard-forex):\n\n"
            f"📍 Vị trí/Bối cảnh: {context or error_sig}\n"
            f"⏰ Thời gian: {ts}\n\n"
            f"📝 Stacktrace chi tiết:\n{exc_info}\n\n"
            f"Hệ thống đã kích hoạt chế độ Fallback an toàn để giữ cho BOT tiếp tục hoạt động."
        )
        html = (
            f"<div style='font-family: Arial, sans-serif; border: 1px solid #dc3545; border-radius: 8px; padding: 16px; max-width: 650px;'>"
            f"<h2 style='color: #dc3545; margin-top: 0;'>🚨 NGOẠI LỆ / CRITICAL ERROR</h2>"
            f"<p>BOT <b>{BOT_NAME} (the-cheopard-forex)</b> vừa phát hiện lỗi thực thi tại module/hàm quan trọng.</p>"
            f"<table style='width: 100%; border-collapse: collapse; margin: 12px 0;'>"
            f"<tr style='background-color: #f8f9fa;'><td style='padding: 8px; border: 1px solid #dee2e6; width: 30%;'><b>Vị trí/Bối cảnh</b></td><td style='padding: 8px; border: 1px solid #dee2e6;'><b>{context or error_sig}</b></td></tr>"
            f"<tr><td style='padding: 8px; border: 1px solid #dee2e6;'><b>Thời gian ghi nhận</b></td><td style='padding: 8px; border: 1px solid #dee2e6;'>{ts}</td></tr>"
            f"<tr style='background-color: #f8f9fa;'><td style='padding: 8px; border: 1px solid #dee2e6;'><b>Cơ chế phục hồi</b></td><td style='padding: 8px; border: 1px solid #dee2e6;'><span style='color: #28a745; font-weight: bold;'>Safe Fallback Triggered (Bot vẫn tiếp tục chạy)</span></td></tr>"
            f"</table>"
            f"<h3>🔍 Stacktrace & Chi tiết lỗi:</h3>"
            f"<pre style='background-color: #212529; color: #f8f9fa; padding: 12px; border-radius: 6px; font-size: 12px; overflow-x: auto;'>{exc_info}</pre>"
            f"</div>"
        )
        # Chạy gửi email trong luồng riêng để không block luồng xử lý chính
        threading.Thread(target=lambda: _async_send(cfg, subject, html, text), daemon=True).start()
    except Exception as e:
        log(f"❌ Không thể gửi email cảnh báo lỗi (lỗi cấu hình/SMTP): {e}")


def _async_send(cfg, subject, html, text):
    """Gửi qua `utils/mailer.py` — SSOT của SMTP, tôn trọng `APP_ENV=PROD`.

    `cfg` giữ lại trong chữ ký cho khớp bên gọi, nhưng không dùng: `mailer` tự đọc
    cấu hình từ `core.config.EMAIL`. Một nơi đọc cấu hình SMTP thì không có chuyện
    hai nơi đọc ra hai thứ khác nhau.
    """
    try:
        from src.python.utils.mailer import send

        if send(subject, text, html):
            log("📨 Đã gửi email cảnh báo ngoại lệ đến người giám sát.")
    except Exception as e:
        log(f"❌ Lỗi khi gửi email cảnh báo ngoại lệ: {e}")


def _report_exception(header: str, stacktrace: str, error_sig: str,
                      context: str, alert_email: bool, fatal: bool = False) -> None:
    """
    Xử lý ngoại lệ DÙNG CHUNG cho mọi bẫy lỗi (decorator, context manager, global hooks):
    ghi log tiêu đề lỗi + stacktrace chi tiết, và gửi email cảnh báo nếu được bật.
    `fatal=True` (xem FATAL_EXCEPTION_TYPES) đổi mức log/tiêu đề email để phân biệt rõ với
    lỗi recoverable thông thường — báo hiệu tiến trình sắp/đang bị ném lại, không fail-soft.
    """
    prefix = "💀 [FATAL — KHÔNG fail-soft, sẽ ném lại]" if fatal else "🔴"
    log_error(f"{prefix} {header}")
    log(f"{prefix} Stacktrace:\n{stacktrace}")
    if alert_email:
        send_exception_alert_email(
            error_sig=error_sig, exc_info=stacktrace,
            context=(f"[FATAL] {context}" if fatal else context))


def safe_guard(fallback: Any = None, alert_email: bool = True, reraise: bool = False, context_name: str = ""):
    """
    Decorator bảo vệ hàm khỏi sập (Crash Guard).
    Nếu hàm phát sinh Exception, bắt lại, ghi log chi tiết, gửi email (nếu bật) và trả về `fallback`.

    Args:
        fallback: Giá trị trả về an toàn khi xảy ra lỗi (ví dụ: False, None, pd.DataFrame(), ...).
        alert_email: Có gửi email cảnh báo lỗi hay không.
        reraise: Có ném tiếp ngoại lệ lên tầng trên hay không (mặc định False = nuốt lỗi và trả về fallback).
        context_name: Tên bối cảnh tùy chỉnh để ghi vào log/email.
    """
    def decorator(func: Callable):
        func_sig = f"{func.__module__}.{func.__qualname__}"
        ctx = context_name or func_sig

        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                fatal = is_fatal_exception(e)
                _report_exception(
                    header=f"Lỗi tại [{ctx}]: {type(e).__name__} - {e}",
                    stacktrace=traceback.format_exc(),
                    error_sig=func_sig, context=ctx, alert_email=alert_email, fatal=fatal,
                )
                if reraise or fatal:
                    raise  # giữ nguyên traceback gốc — fatal luôn ném lại dù reraise=False
                return fallback
        return wrapper
    return decorator


class safe_execute:
    """
    Context manager bảo vệ khối mã lệnh (trong vòng lặp hoặc luồng ngầm).
    Sử dụng:
        with safe_execute(context="tên_bối_cảnh", alert_email=True):
            # đoạn code có nguy cơ lỗi
    """
    def __init__(self, context: str = "Anonymous Context", alert_email: bool = True, reraise: bool = False):
        self.context = context
        self.alert_email = alert_email
        self.reraise = reraise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            return False
        fatal = exc_val is not None and is_fatal_exception(exc_val)
        _report_exception(
            header=f"Lỗi khối lệnh tại [{self.context}]: {exc_type.__name__} - {exc_val}",
            stacktrace="".join(traceback.format_exception(exc_type, exc_val, exc_tb)),
            error_sig=self.context, context=self.context, alert_email=self.alert_email, fatal=fatal,
        )
        # Trả về True để nuốt ngoại lệ (không lan ra ngoài khối with); False để ném tiếp.
        # Fatal luôn ném tiếp (return False) bất kể self.reraise — giống safe_guard.
        return not (self.reraise or fatal)


def _global_exception_hook(exc_type, exc_value, exc_traceback):
    """Hook bắt mọi lỗi chưa được xử lý ở luồng chính (Main Thread Uncaught Exception)."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    _report_exception(
        header=f"UNCAUGHT MAIN THREAD EXCEPTION: {exc_type.__name__} - {exc_value}",
        stacktrace="".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
        error_sig="UNCAUGHT_MAIN_THREAD", context="Main Thread Uncaught Exception", alert_email=True,
        fatal=is_fatal_exception(exc_value) if exc_value is not None else False,
    )


def _threading_exception_hook(args):
    """Hook bắt mọi lỗi chưa được xử lý ở các luồng phụ (Background Threads Uncaught Exception)."""
    thread = args.thread
    _report_exception(
        header=f"UNCAUGHT BACKGROUND THREAD EXCEPTION in [{thread.name}]: {args.exc_type.__name__} - {args.exc_value}",
        stacktrace="".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
        error_sig=f"THREAD_{thread.name}", context=f"Background Thread [{thread.name}]", alert_email=True,
        fatal=is_fatal_exception(args.exc_value) if args.exc_value is not None else False,
    )


def install_global_exception_handler():
    """
    Cài đặt bẫy lỗi toàn cục (Global Exception Hooks) cho cả luồng chính và mọi luồng phụ.
    Đảm bảo không một lỗi nào có thể sập chương trình một cách thầm lặng mà không ghi log & gửi email.
    """
    sys.excepthook = _global_exception_hook
    if hasattr(threading, "excepthook"):
        threading.excepthook = _threading_exception_hook
    log("🏗️ Đã cài đặt Global Exception Hook và Threading Exception Guard.")
