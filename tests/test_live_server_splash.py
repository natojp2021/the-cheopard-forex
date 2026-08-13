# -*- coding: utf-8 -*-
"""MÀN HÌNH CHỜ của `live_server` — các bước nạp phải THẬT SỰ chạy được.

VÌ SAO TEST NÀY TỒN TẠI
========================
`_splash.perform_load` bọc mỗi bước trong `try/except` và chỉ ghi log khi hỏng. Đó
là lựa chọn đúng cho đường khởi động — một module đổi tên KHÔNG được phép chặn cả
bảng điều khiển vì một cửa sổ trang trí. Nhưng nuốt lỗi nghĩa là hỏng mà im lặng:
thanh tiến trình vẫn chạy đủ năm bước, vẫn hiện "Hoàn tất!", trong khi không bước
nào nạp được gì.

Đây đúng lớp lỗi đã để `position_execution_service` hỏng âm thầm nhiều ngày (biên
dịch sạch, import ném `ImportError`, `except` nuốt mất). Test gọi THẲNG từng hàm nạp
nên không có chỗ nào nuốt.
"""
from __future__ import annotations

import pytest

from src.python import live_server as LS


def test_splash_steps_are_ordered_and_complete():
    """Năm bước, tỷ lệ TĂNG DẦN và kết thúc đúng 1,0 — thanh không được lùi hay hụt."""
    ratios = [r for _, r, _ in LS.SPLASH_STEPS]
    assert len(LS.SPLASH_STEPS) == 5
    assert ratios == sorted(ratios), f"tỷ lệ thanh không tăng dần: {ratios}"
    assert ratios[-1] == 1.0, f"bước cuối không lấp đầy thanh: {ratios[-1]}"
    assert all(0.0 < r <= 1.0 for r in ratios)


def test_splash_step_labels_are_non_empty_vietnamese():
    """Mỗi bước phải có dòng chữ — thanh chạy mà không nói đang làm gì là vô dụng."""
    for text, _, _ in LS.SPLASH_STEPS:
        assert text.strip(), "bước không có dòng chữ"
        assert text.endswith("..."), f"thiếu dấu ba chấm: {text!r}"


@pytest.mark.parametrize("idx", range(4))
def test_each_preload_step_actually_runs(idx):
    """Từng hàm nạp phải chạy được THẬT.

    `perform_load` nuốt lỗi của các hàm này, nên nếu một module bị đổi tên thì splash
    vẫn chạy đủ năm bước và vẫn hiện "Hoàn tất!" trong khi không nạp được gì. Chỉ
    phép gọi thẳng như ở đây mới phát hiện.
    """
    text, _, work = LS.SPLASH_STEPS[idx]
    assert work is not None, f"bước {idx} ({text}) mất hàm nạp"
    work()          # ném thì test đỏ — đó chính là điều ta muốn


def test_last_step_has_no_work():
    """Bước cuối chỉ là dòng chữ đóng màn — gắn việc nặng vào đó là làm chậm lúc mở."""
    assert LS.SPLASH_STEPS[-1][2] is None


def test_splash_step_interval_is_sane():
    """Nhịp phải dương và không quá chậm — 5 bước × nhịp là thời gian người vận hành chờ."""
    assert isinstance(LS.SPLASH_STEP_MS, int)
    assert 50 <= LS.SPLASH_STEP_MS <= 500, LS.SPLASH_STEP_MS


def test_lifecycle_log_writes_full_timestamp(tmp_path, monkeypatch):
    """Sổ vòng đời phải ghi ĐỦ ngày giờ, không chỉ năm.

    Bản cũ dựng dòng bằng `strftime(chr(37)+chr(89))`, tức `%Y` — mọi mốc trong sổ
    đều là "2026". Sổ đó sinh ra để dựng lại THỨ TỰ sự kiện khi giao diện tự thoát
    không dấu vết; chỉ có năm thì nó không trả lời được đúng câu hỏi ấy.
    """
    import re

    monkeypatch.setattr(LS, "LIVE_DIR", str(tmp_path))
    LS._log("mốc thử")
    body = (tmp_path / "gui_lifecycle.log").read_text(encoding="utf-8")
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", body), body
    assert "mốc thử" in body


# ── alerts.recently_sent — phân biệt "đã gửi rồi" với "không gửi được" ────────
def test_recently_sent_distinguishes_dedup_from_failure(tmp_path, monkeypatch):
    """`once()` trả False vì hai lý do TRÁI NGƯỢC; `recently_sent` phải tách được.

    Nhật ký VPS 16/08/2026 in dòng tự mâu thuẫn:

        📨 [Email] chỉ GHI LOG (APP_ENV=PROD, cần PROD để gửi thật)

    Nó vừa nói APP_ENV=PROD vừa đòi phải là PROD. Sự thật: thư khởi động đã gửi
    thành công 4 phút trước và lần này bị chặn vì TRÙNG (`ttl_sec=600`). Người vận
    hành đọc dòng đó thì kết luận kênh email đang tắt trong khi nó vẫn chạy.
    """
    from src.python.utils import alerts

    monkeypatch.setattr(alerts, "_last_sent", {}, raising=False)
    monkeypatch.setattr(alerts, "_load_from_disk", lambda: None)
    monkeypatch.setattr(alerts, "_save_to_disk", lambda: None)

    topic = "test_topic"
    assert alerts.recently_sent(topic, 600.0) is False, "chưa gửi mà báo đã gửi"

    # Gửi THÀNH CÔNG → lần hai bị chặn vì trùng, và `recently_sent` phải nói CÓ.
    assert alerts.once(topic, lambda: True, ttl_sec=600.0) is True
    assert alerts.once(topic, lambda: True, ttl_sec=600.0) is False
    assert alerts.recently_sent(topic, 600.0) is True, (
        "bị chặn vì trùng nhưng `recently_sent` nói chưa gửi — bên gọi sẽ đổ lỗi "
        "nhầm cho APP_ENV")


def test_recently_sent_false_when_sender_failed(monkeypatch):
    """Gửi HỎNG thì `recently_sent` phải trả False — nếu không, lỗi thật bị che."""
    from src.python.utils import alerts

    monkeypatch.setattr(alerts, "_last_sent", {}, raising=False)
    monkeypatch.setattr(alerts, "_load_from_disk", lambda: None)
    monkeypatch.setattr(alerts, "_save_to_disk", lambda: None)

    topic = "test_fail"
    assert alerts.once(topic, lambda: False, ttl_sec=600.0) is False
    assert alerts.recently_sent(topic, 600.0) is False, (
        "gửi hỏng mà báo 'đã gửi gần đây' — người vận hành sẽ tưởng thư đã tới")
