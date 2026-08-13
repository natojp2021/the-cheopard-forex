"""Kiểm định NGỦ ĐÔNG CUỐI TUẦN — lịch mở/đóng và email chuyển trạng thái.

VÌ SAO CÓ FILE NÀY
==================
Hai lỗi có thể xảy ra ở đây và cả hai đều im lặng:

  1. Sai MỐC GIỜ. Mở lại lúc 00:00 UTC thay vì 21:00 UTC Chủ Nhật là dậy muộn ba
     tiếng so với lúc thị trường thật sự mở (00:00 giờ máy chủ broker GMT+3).
  2. Gửi email SAI SỐ LẦN. Gửi mỗi vòng lặp thì cuối tuần có hàng nghìn thư; không
     gửi lần nào thì người vận hành không biết hệ đã ngủ hay đã chết.

Hệ XAUUSD từng có đúng lớp lỗi thứ hai ở dạng ngược lại: `if not is_market_closed()`
bọc một dòng log ĐÃ BỊ COMMENT — cổng trông như có nhưng không làm gì cả.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.python.core.infra import market_schedule as MS


def _utc(day: int, hour: int, month: int = 8, year: int = 2026) -> datetime:
    return datetime(year, month, day, hour, 0, tzinfo=timezone.utc)


# 2026-08-14 là Thứ Sáu, 15 Thứ Bảy, 16 Chủ Nhật, 17 Thứ Hai.
@pytest.mark.parametrize("day,hour,closed", [
    (14, 12, False),   # Thứ Sáu giữa phiên
    (14, 23, False),   # Thứ Sáu khuya — VẪN mở, chỉ đóng từ 00:00 Thứ Bảy
    (15, 0, True),     # Thứ Bảy 00:00 — mốc đóng
    (15, 12, True),    # Thứ Bảy giữa ngày
    (15, 23, True),    # Thứ Bảy khuya
    (16, 12, True),    # Chủ Nhật trưa — vẫn đóng
    (16, 20, True),    # Chủ Nhật 20:00 — còn một giờ nữa mới mở
    (16, 21, False),   # Chủ Nhật 21:00 UTC = 00:00 Thứ Hai giờ broker → MỞ
    (17, 3, False),    # Thứ Hai
])
def test_market_closed_boundaries(day, hour, closed):
    assert MS.is_market_closed(_utc(day, hour)) is closed


def test_reopens_at_broker_midnight_not_utc_midnight():
    """Mốc mở là 21:00 UTC Chủ Nhật, KHÔNG phải 00:00 UTC Thứ Hai.

    00:00 UTC Thứ Hai đã là 03:00 giờ máy chủ broker (GMT+3) — dậy muộn ba tiếng và
    bỏ mất phần đầu phiên Á.
    """
    assert MS.SUNDAY_OPEN_HOUR_UTC == 21
    assert MS.is_market_closed(_utc(16, 20, )) is True
    assert MS.is_market_closed(_utc(16, 21)) is False


def test_next_open_and_countdown():
    sat = _utc(15, 12)
    assert MS.next_open_utc(sat) == _utc(16, 21)
    assert MS.seconds_to_open(sat) == pytest.approx(33 * 3600)
    sun = _utc(16, 12)
    assert MS.next_open_utc(sun) == _utc(16, 21)
    assert MS.seconds_to_open(sun) == pytest.approx(9 * 3600)
    # Đang mở thì không đếm ngược.
    assert MS.seconds_to_open(_utc(17, 3)) == 0.0


def test_naive_datetime_is_treated_as_utc():
    """Truyền datetime không có múi giờ không được ngầm hiểu thành giờ máy."""
    assert MS.is_market_closed(datetime(2026, 8, 15, 12)) is True
    assert MS.is_market_closed(datetime(2026, 8, 17, 3)) is False


def test_no_is_market_open_helper():
    """Cố ý KHÔNG có hàm phủ định thứ hai — hai chỗ sửa thì một chỗ sẽ bị quên."""
    assert not hasattr(MS, "is_market_open")


# ═════════════════════════════════════════════════════ engine gửi email đúng lần
class _Engine:
    """Bọc engine thật nhưng chặn mọi thứ chạm ra ngoài.

    Trạng thái đóng/mở giữ trong `self.closed` thay vì một hàng đợi bị "pop": chính
    `describe()` cũng gọi `is_market_closed()`, nên hàng đợi sẽ cạn sai nhịp và test
    hỏng vì lý do không liên quan gì tới thứ đang kiểm.
    """

    def __init__(self, monkeypatch, closed: bool = False, sent=None, phase=None):
        from src.python.core.engine import TradingEngine

        self.sent = sent if sent is not None else []
        self.closed = closed
        if phase is not None:
            monkeypatch.setattr(MS, "PHASE_PATH", phase)
        self.eng = TradingEngine()
        monkeypatch.setattr(MS, "is_market_closed", lambda *a, **k: self.closed)
        monkeypatch.setattr(self.eng, "_send_market_state_email",
                            lambda c: self.sent.append(c))

    def tick(self, n: int = 1, closed: "bool | None" = None):
        if closed is not None:
            self.closed = closed
        for _ in range(n):
            self.eng._check_market_hours()


def test_first_run_ever_sends_no_email(monkeypatch, tmp_path):
    """Lần chạy đầu TRONG ĐỜI (chưa có file pha) không gửi email."""
    e = _Engine(monkeypatch, closed=True, phase=tmp_path / "phase.json")
    e.tick()
    assert e.sent == []
    assert e.eng.state["market_closed"] is True


def test_wake_email_survives_restart_mid_weekend(monkeypatch, tmp_path):
    """LỖI ĐÃ SỬA 15/08/2026 — email THỨC DẬY sau khi VPS reboot giữa cuối tuần.

    Cờ "pha trước đó" phải sống ~45 giờ liên tục từ 00:00 thứ Bảy tới 21:00 Chủ
    Nhật. Khi nó chỉ nằm trong RAM, một lần reboot / watchdog kill / tắt bot cuối
    tuần đưa nó về `None`, và nhánh gửi email bị `prev is not None` chặn — email
    ngủ đông vẫn tới đều đặn nhưng email thức dậy KHÔNG BAO GIỜ tới.

    Chiều ngược lại không bao giờ hỏng (lúc đóng, bot đã chạy liên tục suốt phiên
    thứ Sáu), nên nhìn log vẫn thấy "email vẫn chạy" — đó là lý do lỗi sống lâu.
    """
    phase = tmp_path / "phase.json"
    sent = []

    e1 = _Engine(monkeypatch, closed=False, sent=sent, phase=phase)
    e1.tick()                                  # thứ Sáu, đang mở
    e1.tick(closed=True)                       # 00:00 thứ Bảy → NGỦ ĐÔNG
    assert sent == [True]

    # ── VPS reboot trưa Chủ Nhật: tiến trình MỚI, RAM sạch
    e2 = _Engine(monkeypatch, closed=True, sent=sent, phase=phase)
    e2.tick()                                  # vẫn đóng — không có gì đổi
    assert sent == [True], "không được gửi lại email ngủ đông sau reboot"

    e2.tick(closed=False)                      # 21:00 Chủ Nhật → THỨC DẬY
    assert sent == [True, False], "email THỨC DẬY phải tới sau reboot"


def test_phase_is_written_every_check(monkeypatch, tmp_path):
    """Ghi mỗi lần kiểm, không chỉ khi đổi — một lần đổi bị mất là mất vĩnh viễn."""
    phase = tmp_path / "phase.json"
    e = _Engine(monkeypatch, closed=False, phase=phase)
    e.tick()
    assert MS.load_phase(phase) is False
    e.tick(closed=True)
    assert MS.load_phase(phase) is True


def test_load_phase_distinguishes_unknown_from_open(tmp_path):
    """`None` (chưa biết) KHÁC `False` (lần trước đang mở) — gộp là mất email."""
    p = tmp_path / "phase.json"
    assert MS.load_phase(p) is None
    MS.save_phase(False, p)
    assert MS.load_phase(p) is False
    MS.save_phase(True, p)
    assert MS.load_phase(p) is True


def test_email_sent_once_per_transition(monkeypatch, tmp_path):
    """Mở → đóng → mở phải cho ĐÚNG hai email, không phải một email mỗi vòng lặp."""
    e = _Engine(monkeypatch, closed=False, phase=tmp_path / "phase.json")
    e.tick(3)                       # đang mở
    e.tick(3, closed=True)          # chuyển sang ngủ đông
    e.tick(2, closed=False)         # thức dậy
    assert e.sent == [True, False], e.sent


def test_weekend_is_completely_silent_in_the_log(monkeypatch, tmp_path):
    """Cả cuối tuần KHÔNG một dòng log nào — kể cả lúc chuyển pha.

    Hệ XAUUSD in dòng standby mỗi 5 phút → ~540 dòng gần giống hệt nhau mỗi cuối
    tuần. Bản trước ở đây rút xuống hai dòng (lúc ngủ đông, lúc thức dậy); từ
    15/08/2026 bỏ nốt cả hai.

    Lý do: pha thị trường hiện THƯỜNG TRỰC trên thẻ SESSION qua
    `state["market_status"]`, nên một dòng log chỉ lặp lại thứ đang nhìn thấy. Còn
    người vận hành KHÔNG ngồi trước màn hình thì dòng log cũng vô ích với họ —
    thứ tới được tay họ là EMAIL, và đó là kênh vẫn giữ nguyên (xem
    `test_weekend_sends_exactly_two_emails`).
    """
    lines = []
    e = _Engine(monkeypatch, closed=False, phase=tmp_path / "phase.json")
    monkeypatch.setattr(e.eng, "log", lambda m: lines.append(m))
    monkeypatch.setattr(MS, "describe", lambda *a, **k: "…")

    e.tick(5)                              # thứ Sáu, đang mở
    e.tick(32_400, closed=True)            # cả cuối tuần, 45 giờ × 5 giây
    e.tick(5, closed=False)                # thứ Hai, mở lại

    assert lines == [], f"sổ log phải im, nhưng có {len(lines)} dòng: {lines[:6]}"


def test_weekend_sends_exactly_two_emails(monkeypatch, tmp_path):
    """Đúng HAI email mỗi cuối tuần: NGỦ ĐÔNG và THỨC DẬY — không hơn, không kém.

    Đây là bất biến thay thế cho hai dòng log đã bỏ. Email là kênh DUY NHẤT chạm
    tới người vận hành khi màn hình tắt, nên nó phải bắn ĐÚNG ở hai lần chuyển pha
    và im suốt 45 giờ ở giữa.
    """
    sent = []
    e = _Engine(monkeypatch, closed=False, phase=tmp_path / "phase.json")
    monkeypatch.setattr(e.eng, "log", lambda m: None)
    monkeypatch.setattr(MS, "describe", lambda *a, **k: "…")
    monkeypatch.setattr(e.eng, "_send_market_state_email",
                        lambda closed: sent.append("NGỦ ĐÔNG" if closed else "THỨC DẬY"))

    e.tick(5)
    e.tick(32_400, closed=True)
    e.tick(5, closed=False)

    assert sent == ["NGỦ ĐÔNG", "THỨC DẬY"], sent


def test_startup_mid_weekend_is_silent(monkeypatch, tmp_path):
    """Khởi động giữa cuối tuần KHÔNG được ghi log — trạng thái đã có trên thẻ GUI.

    Đổi 15/08/2026 theo phản hồi vận hành. Log giữ cho SỰ KIỆN (lúc CHUYỂN pha),
    không phải cho TRẠNG THÁI: pha thị trường hiện thường trực ở
    `state["market_status"]`, nên một dòng mỗi lần mở ứng dụng chỉ lặp lại thứ đang
    nhìn thấy, và nhiễu tích lại làm chìm dòng thật sự quan trọng.
    """
    lines = []
    phase = tmp_path / "phase.json"
    MS.save_phase(True, phase)          # lần trước cũng đang đóng → không chuyển pha
    e = _Engine(monkeypatch, closed=True, phase=phase)
    monkeypatch.setattr(e.eng, "log", lambda m: lines.append(m))
    e.tick()
    assert lines == [], lines
    # Nhưng TRẠNG THÁI vẫn phải có, để thẻ giao diện đọc được.
    assert e.eng.state["market_closed"] is True
    assert e.eng.state["market_status"]
