"""Bất biến: bộ test KHÔNG BAO GIỜ được gửi email thật.

SỰ CỐ 25/08/2026 — một đợt chạy pytest gửi THẬT một email "🔔 Vào lệnh mới —
SELL AUDCAD" tới hộp thư vận hành, dù danh mục đang chạy live chỉ còn 3 cặp
EU/GU/UJ (AUDCAD không thuộc registry hiện tại) và `trade_id=#12345` là dữ
liệu giả của một FIXTURE test. `.env` của repo đặt `APP_ENV=PROD` (bắt buộc
cho bot LIVE), và `tests/conftest.py` trước bản vá này KHÔNG có dòng nào chặn
`mailer.send()` đọc lại biến đó — nên MỌI test chạm vào đường gửi email đều
gửi THẬT ra SMTP thật, không cần mock riêng ở từng test.

Hai lớp chặn đã thêm vào `conftest.py`:
    1. `os.environ["APP_ENV"] = "test"` — đặt TRƯỚC mọi import, để `core.config`
       tính `IS_PROD = False` ngay từ lần import đầu tiên.
    2. Fixture `_block_real_smtp` — ép thẳng `core.config.IS_PROD = False`,
       phòng khi module đó đã bị import trước dòng env ở trên (vd một plugin
       pytest khác import sớm hơn).

File này chỉ ghim lại bất biến — không lặp lại chi tiết TẠI SAO `mailer.send()`
tôn trọng `IS_PROD` (xem docstring của chính hàm đó).
"""
from __future__ import annotations


def test_is_prod_forced_false_during_tests():
    """`core.config.IS_PROD` phải là `False` trong MỌI phiên test, bất kể `.env`
    thật của repo ghi gì — đây là điều kiện TIÊN QUYẾT để `mailer.send()` không
    chạm SMTP thật."""
    from src.python.core import config as cfg

    assert cfg.IS_PROD is False, (
        "IS_PROD=True trong lúc test — mọi lời gọi mailer.send() sau đây sẽ "
        "gửi email THẬT ra hộp thư vận hành")


def test_mailer_send_never_touches_real_smtp():
    """`mailer.send()` phải tự nhận ra không phải PROD và trả `False` — không
    ném lỗi, không mở kết nối SMTP nào, kể cả khi `.env` có cấu hình SMTP hợp
    lệ (repo này CÓ, vì bot LIVE dùng chung `.env`)."""
    from src.python.utils import mailer

    ok = mailer.send("[TEST] không được gửi thật", "nội dung kiểm thử")
    assert ok is False, (
        "send() trả True nghĩa là đã (hoặc tưởng đã) gửi thật — sai trong test")


def test_email_entry_call_does_not_reach_real_smtp():
    """Đường đi ĐẦY ĐỦ, KHÔNG mock riêng: gọi thẳng `emails.entry()` (hàm dựng
    nội dung ở lớp NGHIỆP VỤ — đúng hàm sự cố 25/08/2026 đã gọi tới) và đòi nó
    tự nhận ra không phải PROD rồi bỏ qua, thay vì phải tin một mock ở giữa.

    `emails.py` bind `_send = mailer.send` bằng `from ... import send as
    _send` — patch `mailer.send` sau đó KHÔNG chạm được tham chiếu này (Python
    copy giá trị lúc import, không giữ liên kết ngược). Test này vì vậy đi qua
    ĐÚNG con đường thật — không mock — và chỉ dựa vào `IS_PROD=False` (đã ép ở
    `conftest.py`) để chặn, đúng cơ chế mà `mailer.send()` thật sự dùng.
    """
    from src.python.shared.notifications import emails as EM

    ok = EM.entry(strategy="TEST", symbol="EURUSD", direction="BUY", lots=0.01,
                  price=1.10000, stop_price=1.09000, weight=None, leverage=1.0,
                  equity=1000.0, spread=0.0001, trade_id="#test", magic=0,
                  timeframe="H1", notional_usd=100.0, broker_time="", reason="")

    assert ok is False, (
        "entry() trả True nghĩa là mailer.send tưởng đã gửi thật trong test")
