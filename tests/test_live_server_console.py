# -*- coding: utf-8 -*-
"""ĐIỂM VÀO console-only — các bất biến của đường khởi động và dừng.

TỆP NÀY THAY `test_live_server_splash.py` (19/08/2026)
======================================================
Tệp cũ kiểm màn hình chờ của bảng điều khiển Tk: năm bước nạp, tỷ lệ thanh tăng dần,
mỗi bước phải THẬT SỰ chạy được (vì `perform_load` nuốt lỗi, nên một module đổi tên
sẽ để splash chạy đủ năm bước và hiện "Hoàn tất!" trong khi không nạp được gì).

Cả màn hình chờ và bảng điều khiển đã bị xoá, nên những test đó không còn đo gì. Điều
KHÔNG mất đi là ý định phía sau chúng: **đường khởi động nuốt lỗi thì phải có test
gọi thẳng từng bước**. Ở bản console-only, các bước đó là dựng console, bắc cầu
logger, và dựng báo cáo khởi động — và ba test đầu dưới đây gọi thẳng vào chúng.

Hai nhóm test cuối (`alerts.recently_sent`) giữ nguyên từ tệp cũ: chúng không liên
quan gì tới giao diện, và bất biến của chúng vẫn đúng.
"""
from __future__ import annotations

import pytest

from src.python import live_server as LS


# ─────────────────────────────────────────── console dựng được và không nuốt lỗi
def test_console_can_be_built_and_renders_without_state(capsys, tmp_path):
    """Dựng console rồi in báo cáo khởi động với trạng thái RỖNG — không được ném.

    Đây là ca thật, không phải ca giả: `boot_report` chạy ngay sau `start_loop()`, và
    lúc đó vòng lặp mới chỉ điền được một phần trạng thái. Bản đầu của `_boot_rows`
    đọc `state["account_info"]["server"]` trực tiếp và ném `TypeError` khi khoá còn
    trống — tức chặn cả lần khởi động vì một dòng trang trí.
    """
    from src.python.core.ops_console import OpsConsole
    from src.python.utils import ops_log

    ops_log.set_root(tmp_path)
    try:
        console = OpsConsole(heartbeat_seconds=9999.0)
        console.boot_report({})
        console.heartbeat()
        console.shutdown_report("test")
    finally:
        ops_log.set_root(None)
    out = capsys.readouterr().out
    assert "KHỞI ĐỘNG" in out
    assert "TỔNG KẾT PHIÊN" in out


def test_logger_bridge_routes_module_logs_into_console(capsys, tmp_path):
    """`utils.logger.log()` phải đi qua console vận hành, không ra định dạng cũ.

    Không có cầu này thì màn hình có HAI định dạng lẫn nhau — dòng của engine đã tô
    màu và gắn nhóm, dòng của `mt5_bars`/`fx_data` ra nguyên dạng
    `2026-08-19 22:33:55 | INFO | cheopard | …`. Tệ hơn cái xấu: nhánh thứ hai sẽ
    KHÔNG qua bộ nén spam và KHÔNG vào sổ JSONL, mà đúng những dòng ồn nhất đã đo
    được (`[FX-M1]`, `DỮ LIỆU CŨ`) lại thuộc nhánh đó.
    """
    from src.python.core.ops_console import OpsConsole
    from src.python.utils import logger as L
    from src.python.utils import ops_log

    ops_log.set_root(tmp_path)
    console = OpsConsole(heartbeat_seconds=9999.0)
    L.attach_console_sink(lambda msg, level: console.event(str(msg)))
    try:
        L.log("[FX-M1] dòng thử qua cầu logger")
    finally:
        L.attach_console_sink(None)
        ops_log.set_root(None)
    out = capsys.readouterr().out
    assert "dòng thử qua cầu logger" in out
    # Định dạng CŨ không được xuất hiện: có nó nghĩa là cầu không chặn được nhánh
    # stderr, và hai bộ hiển thị đang cùng in một dòng.
    assert "| INFO    | cheopard |" not in out


def test_no_gui_module_remains_importable():
    """Bảng điều khiển Tk phải KHÔNG còn import được.

    Đây là test chống HỒI SINH, không phải test hình thức. Đợt xoá này bỏ cả tệp giao
    diện lẫn `customtkinter`/`matplotlib` khỏi `requirements.txt`. Nếu ai đó khôi
    phục tệp giao diện mà quên phần phụ thuộc, nó sẽ chạy được trên máy này (venv còn
    thư viện cũ) và chết trên máy sạch — đúng loại lệch môi trường khó tìm nhất.
    """
    import importlib

    for name in ("src.python.core.gui_command_center", "src.python.core.ui_patches"):
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(name)


def test_entry_point_has_no_gui_mode():
    """Không còn `run_gui`/`_splash`, và `--cli` vẫn nhận được.

    `--cli` giữ lại làm cờ KHÔNG TÁC DỤNG: `start_live_server.bat`, tài liệu và thói
    quen của người vận hành đều còn dùng nó. Xoá thì lệnh cũ chết với "unrecognized
    arguments" — một cái chết vô nghĩa cho thứ giờ đã là mặc định.
    """
    assert not hasattr(LS, "run_gui")
    assert not hasattr(LS, "_splash")
    assert not hasattr(LS, "SPLASH_STEPS")
    assert hasattr(LS, "run_console")


def test_lifecycle_log_writes_full_timestamp(tmp_path, monkeypatch):
    """Sổ vòng đời phải ghi ĐỦ ngày giờ, không chỉ năm.

    Bản cũ dựng dòng bằng `strftime(chr(37)+chr(89))`, tức `%Y` — mọi mốc trong sổ
    đều là "2026". Sổ đó sinh ra để dựng lại THỨ TỰ sự kiện khi tiến trình tự thoát
    không dấu vết; chỉ có năm thì nó không trả lời được đúng câu hỏi ấy.

    ĐỔI TÊN TỆP 19/08/2026: `gui_lifecycle.log` -> `live_server.log`. Không còn giao
    diện nào để mà đặt tên theo.
    """
    import re

    monkeypatch.setattr(LS, "LIVE_DIR", str(tmp_path))
    LS._log("mốc thử")
    body = (tmp_path / "live_server.log").read_text(encoding="utf-8")
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", body), body
    assert "mốc thử" in body


def test_pid_check_fails_closed_when_it_cannot_ask(monkeypatch):
    """Không kiểm được PID -> coi như CÒN SỐNG, không cho bản thứ hai chạy.

    Đoán sai theo hướng "đã chết" cho phép hai tiến trình cùng gửi lệnh lên MỘT tài
    khoản MT5 — hai bộ quản lý vị thế đánh nhau trên cùng số lệnh. Với console-only
    nguy cơ này cao hơn bản GUI: không còn cửa sổ nào để người vận hành nhìn thấy
    rằng bản cũ vẫn đang mở.
    """
    import subprocess

    def boom(*_a, **_k):
        raise OSError("tasklist không chạy được")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(LS.os, "name", "nt")
    assert LS._pid_is_alive(4242) is True


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
