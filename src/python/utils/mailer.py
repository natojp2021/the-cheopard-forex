"""mailer.py — gửi email vận hành. MỘT đường duy nhất, và nó KHÔNG BAO GIỜ ném lỗi.

VÌ SAO KHÔNG NÉM LỖI
=====================
Email là đường QUAN SÁT, không phải đường quyết định. Một lỗi SMTP — hết hạn mật
khẩu ứng dụng, mạng chập, Gmail chặn — không được phép làm dừng vòng lặp giao dịch
hay làm hỏng một chu kỳ tái cân bằng. Hàm ở đây trả `False` và ghi log, không raise.

Đây là ngoại lệ có chủ ý với nguyên tắc fail-closed của dự án: fail-closed áp cho
tầng RỦI RO (không tính được rủi ro thì không vào lệnh), không áp cho tầng thông báo.

CÔNG TẮC MÔI TRƯỜNG
====================
Chỉ `APP_ENV=PROD` mới thật sự gửi. Mọi giá trị khác chỉ GHI LOG nội dung thư — nhờ
vậy chạy thử ở máy phát triển không spam hộp thư, mà vẫn kiểm được nội dung đúng.
Quy ước này kế thừa nguyên từ một hệ một-tài-sản.
"""
from __future__ import annotations

import smtplib
import ssl
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, Optional

from src.python.utils.logger import log, log_error


# ─────────────────────────────────────────── thư bị nuốt ở môi trường DEV
_DEV_MAIL: Dict[str, Any] = {"n": 0, "last_print": 0.0, "sample": ""}
_DEV_MAIL_EVERY = 300.0


def _dev_mail_swallowed(subject: str) -> None:
    """Đếm thư bị nuốt ở DEV, in GỘP thay vì một dòng mỗi thư.

    Đo 07:32:43 ngày 21/08/2026: mười dòng liên tiếp, mỗi dòng một tiêu đề thư,
    chiếm trọn màn hình ngay sau khi lượt gửi lệnh kết thúc:

        email KHÔNG gửi (APP_ENV != PROD) — nội dung: 🔔 [...] BUY ... — AUDJPY (Lot 0.02)
        email KHÔNG gửi (APP_ENV != PROD) — nội dung: 🔔 [...] SELL ... — CADCHF (Lot 0.02)
        ... (8 dòng nữa)

    Mỗi dòng nói đúng một điều đã biết từ trước khi bot khởi động: `APP_ENV`
    không phải PROD nên KHÔNG thư nào được gửi. Đó là CẤU HÌNH, không phải sự
    kiện — mà nội dung thư thì đã nằm nguyên trong bảng kết quả lệnh ngay phía
    trên, đầy đủ hơn (giá, spread, SL, retcode).

    Nên: đếm và nói MỘT lần mỗi 5 phút, kèm một tiêu đề mẫu để biết loại thư nào
    đang bị nuốt.
    """
    import time

    _DEV_MAIL["n"] += 1
    _DEV_MAIL["sample"] = subject
    now = time.time()
    if now - float(_DEV_MAIL["last_print"]) >= _DEV_MAIL_EVERY:
        n = int(_DEV_MAIL["n"])
        _DEV_MAIL["n"] = 0
        _DEV_MAIL["last_print"] = now
        log(f"email DEV: {n} thư KHÔNG gửi (APP_ENV != PROD) — ví dụ: {subject}")


def _config() -> dict:
    from src.python.core.config import EMAIL
    return dict(EMAIL)


def is_configured() -> bool:
    """Có đủ thông tin để gửi không. Thiếu là im lặng bỏ qua, không phải lỗi."""
    c = _config()
    return bool(c.get("host") and c.get("user") and c.get("password")
                and c.get("recipient"))



def _load_images(images: Optional[Dict[str, str]]):
    """`{cid: đường_dẫn}` → danh sách `MIMEImage` đã gắn Content-ID.

    Dấu ngoặc nhọn quanh Content-ID là BẮT BUỘC theo RFC 2392; thiếu nó thì Gmail
    hiện đúng, còn Outlook hiện ô vỡ — một khác biệt chỉ lộ ra trên máy người dùng.
    """
    out = []
    for cid, path in (images or {}).items():
        try:
            f = Path(path)
            if not f.is_file():
                continue
            part = MIMEImage(f.read_bytes())
            part.add_header("Content-ID", f"<{cid}>")
            part.add_header("Content-Disposition", "inline", filename=f.name)
            out.append(part)
        except Exception:
            continue          # thiếu một hình không được làm mất cả lá thư
    return out


def send(subject: str, body_text: str, body_html: Optional[str] = None,
         images: Optional[Dict[str, str]] = None) -> bool:
    """Gửi một email. Trả `True` nếu đã gửi thật, `False` nếu bỏ qua hoặc lỗi.

    `images` là `{cid: đường_dẫn}` — ảnh NHÚNG trong thân thư, tham chiếu từ HTML
    bằng `<img src="cid:tên">`. Nhúng chứ không dẫn link ngoài là bắt buộc: gần như
    mọi client email chặn ảnh tải từ internet cho tới khi người đọc bấm "hiện ảnh",
    nên ảnh dẫn link sẽ hiện thành ô vỡ ở đúng lần đọc đầu tiên.

    Ảnh không tồn tại thì BỎ QUA lặng lẽ, không ném lỗi — thiếu một hình trang trí
    không được phép làm mất cả lá thư cảnh báo.
    """
    from src.python.core.config import IS_PROD

    c = _config()
    if not is_configured():
        log(f"email BỎ QUA (chưa cấu hình SMTP trong .env): {subject}")
        return False
    if not IS_PROD:
        _dev_mail_swallowed(subject)
        return False

    try:
        # Cấu trúc `related` bọc ngoài `alternative` là cấu trúc DUY NHẤT mà cả
        # Gmail, Outlook và client điện thoại cùng hiểu khi thư vừa có bản text,
        # vừa có bản HTML, vừa có ảnh nhúng. Đảo hai lớp lại thì Outlook hiện ảnh
        # thành tệp đính kèm rời thay vì nhúng trong thân thư.
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            alt.attach(MIMEText(body_html, "html", "utf-8"))

        embedded = _load_images(images)
        if embedded:
            msg = MIMEMultipart("related")
            msg.attach(alt)
            for part in embedded:
                msg.attach(part)
        else:
            msg = alt
        msg["Subject"] = subject
        msg["From"] = f"{c.get('sender_name') or 'bot'} <{c['user']}>"
        msg["To"] = c["recipient"]

        port = int(c.get("port") or 587)
        if c.get("use_tls"):
            with smtplib.SMTP(c["host"], port, timeout=20) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(c["user"], c["password"])
                s.send_message(msg)
        else:
            with smtplib.SMTP_SSL(c["host"], port, timeout=20,
                                  context=ssl.create_default_context()) as s:
                s.login(c["user"], c["password"])
                s.send_message(msg)
        log(f"đã gửi email: {subject}")
        return True
    except Exception as exc:                              # pragma: no cover
        log_error(f"KHÔNG gửi được email {subject!r}: {type(exc).__name__}: {exc}")
        return False
