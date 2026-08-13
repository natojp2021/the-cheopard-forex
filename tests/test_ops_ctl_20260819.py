# -*- coding: utf-8 -*-
"""`ops_ctl` — công cụ điều khiển thay các nút của bảng điều khiển cũ.

VÌ SAO TỆP NÀY QUAN TRỌNG HƠN VẺ NGOÀI
=======================================
Xoá giao diện là xoá cả ba hành động vận hành của nó. `ops_ctl` thay chúng, nên nó là
đường DUY NHẤT còn lại để một người can thiệp vào bot đang chạy — kể cả trong tình huống
xấu nhất, khi thao tác cần là kill switch.

Ba nhóm bất biến:
  1. `stop` KHÔNG được chạm vòng lặp. Chặn lệnh mới và dừng vòng lặp là hai việc khác
     nhau, và nhầm chúng là để vị thế đang mở chạy không người quản lý.
  2. Thao tác không hoàn tác được phải đòi `--confirm`.
  3. Không đọc được vị thế thì KHÔNG BAO GIỜ báo là rỗng.
"""
from __future__ import annotations

import pytest

from src.python import ops_ctl


@pytest.fixture(autouse=True)
def _isolate_switch(tmp_path, monkeypatch):
    """Công tắc ghi vào tmp — test KHÔNG được đụng công tắc THẬT của người vận hành.

    Không cô lập thì một lượt `pytest` sẽ TẮT giao dịch trên máy đang chạy live, và
    không ai biết vì sao bot ngừng vào lệnh.
    """
    from src.python.execution import trading_control as tc

    monkeypatch.setattr(tc, "CONTROL_PATH", tmp_path / "trading_control.json")
    return tc


# ─────────────────────────────────────── 1. stop không chạm vòng lặp
def test_stop_only_closes_the_switch():
    """`stop` chỉ đóng công tắc — không `stop_loop`, không chạm engine.

    Ứng dụng phải chạy bình thường để còn đọc tài khoản, đếm time-stop, đối soát sổ vị
    thế và canh cầu chì. Một vị thế đang mở mà mất người quản lý là tình trạng nguy hiểm
    HƠN việc vào thêm lệnh.
    """
    import inspect

    source = inspect.getsource(ops_ctl.cmd_stop)
    assert "set_enabled(False" in source
    for forbidden in ("stop_loop", "is_running"):
        assert forbidden not in source, f"`stop` chạm tới `{forbidden}`"


def test_module_cannot_reach_the_engine_at_all():
    """META: cả module KHÔNG được import engine.

    Mạnh hơn test trên: kiểm từng hàm thì một hàm mới có thể lách qua; kiểm cả module thì
    không. Ranh giới này là thứ làm `ops_ctl` an toàn hơn nút bấm cũ — nút cũ nằm cùng
    tiến trình với engine và chỉ cách `engine.stop_loop()` một dòng code.
    """
    import inspect

    source = inspect.getsource(ops_ctl)
    assert "stop_loop" not in source
    assert "TradingEngine" not in source


def test_run_and_stop_actually_flip_the_switch(_isolate_switch):
    """Hai lệnh phải đổi được trạng thái THẬT, không chỉ in ra chữ."""
    tc = _isolate_switch

    class _A:
        pass

    assert ops_ctl.cmd_run(_A()) == 0
    assert tc.read().enabled is True
    assert ops_ctl.cmd_stop(_A()) == 0
    assert tc.read().enabled is False
    # Ghi lại AI đã đổi và VÌ SAO — dấu vết kiểm toán của một thao tác tiền thật.
    assert "ops_ctl" in tc.read().reason


# ─────────────────────────────────────── 2. thao tác không hoàn tác đòi xác nhận
def test_flatten_refuses_without_confirm():
    """Kill switch KHÔNG được chạy chỉ vì gõ đúng tên lệnh.

    Nó đóng mọi vị thế theo giá thị trường hiện tại — không hoàn tác được. Mã thoát 2
    (chứ không phải 0) để một script gọi nhầm cũng biết là nó chưa làm gì.
    """
    closed = []
    from src.python.core.infra import mt5_bridge

    original = getattr(mt5_bridge, "close_all_positions", None)
    try:
        mt5_bridge.close_all_positions = lambda **k: closed.append(1) or (1, 1)

        class _A:
            confirm = False

        assert ops_ctl.cmd_flatten(_A()) == 2
        assert closed == [], "đã đóng lệnh dù chưa xác nhận"
    finally:
        if original is not None:
            mt5_bridge.close_all_positions = original


def test_flatten_reports_unknown_total_as_failure(monkeypatch):
    """KHÔNG xác định được tổng số vị thế -> báo LỖI, không báo thành công.

    Đây là hình dạng lỗi nặng nhất từng gặp trong họ dự án này: kill switch báo "đã đóng
    hết" khi chưa đóng gì, vì `positions_get()` trả `None` và mã gọi hiểu thành rỗng.
    Người vận hành đọc "đã đóng hết" rồi đi ngủ.
    """
    from src.python.core.infra import mt5_bridge

    monkeypatch.setattr(mt5_bridge, "close_all_positions",
                        lambda **k: (0, None), raising=False)

    class _A:
        confirm = True

    assert ops_ctl.cmd_flatten(_A()) == 1


def test_flatten_partial_close_is_a_failure(monkeypatch):
    """Đóng 2/3 vị thế KHÔNG phải thành công — còn một vị thế không ai quản lý."""
    from src.python.core.infra import mt5_bridge

    monkeypatch.setattr(mt5_bridge, "close_all_positions",
                        lambda **k: (2, 3), raising=False)

    class _A:
        confirm = True

    assert ops_ctl.cmd_flatten(_A()) == 1


# ─────────────────────────────────────── 3. không đọc được != rỗng
def test_status_does_not_touch_mt5_by_default(monkeypatch):
    """`status` mặc định đọc ĐĨA — không `initialize()`, không khởi chạy terminal.

    `mt5.initialize()` chờ tới 60 giây VÀ tự khởi chạy terminal nếu chưa mở. Để nó chạy
    mặc định là biến lệnh hay dùng nhất thành lệnh chậm nhất, kèm một tác dụng phụ không
    ai xin.
    """
    called = []
    monkeypatch.setattr(ops_ctl, "_init_mt5",
                        lambda con: called.append(1) or None)

    class _A:
        mt5 = False

    assert ops_ctl.cmd_status(_A()) == 0
    assert called == [], "`status` đã nối MT5 dù không được yêu cầu"


def test_positions_never_reports_empty_when_the_read_failed(monkeypatch, capsys):
    """`positions_get()` trả `None` -> nói KHÔNG ĐỌC ĐƯỢC, không nói "không có".

    Họ lỗi tái phát nhiều nhất của dự án. Ở một công cụ vận hành, hiểu sai theo hướng này
    khiến người vận hành tin rằng mình đang không có phơi nhiễm.
    """
    class _FakeMt5:
        @staticmethod
        def positions_get():
            return None

    monkeypatch.setattr(ops_ctl, "_init_mt5", lambda con: _FakeMt5)

    class _A:
        pass

    assert ops_ctl.cmd_positions(_A()) == 1
    out = capsys.readouterr().out
    assert "KHÔNG đọc được" in out
    assert "Không có vị thế nào" not in out


def test_positions_reports_a_genuine_empty_book_as_empty(monkeypatch, capsys):
    """Đọc được và rỗng thì phải nói rõ là rỗng — nếu không, cảnh báo mất giá trị.

    Nhánh này quan trọng ngang nhánh trên: nếu mọi lần rỗng đều báo "không đọc được" thì
    người vận hành học cách bỏ qua dòng đó, và lần thật sự không đọc được sẽ trôi qua.
    """
    class _FakeMt5:
        @staticmethod
        def positions_get():
            return []

    monkeypatch.setattr(ops_ctl, "_init_mt5", lambda con: _FakeMt5)

    class _A:
        pass

    assert ops_ctl.cmd_positions(_A()) == 0
    assert "Không có vị thế nào" in capsys.readouterr().out


def test_help_renders_on_a_cp1252_console():
    """`--help` phải in được chữ Việt có dấu.

    `argparse` in phần trợ giúp TRƯỚC khi bất cứ `OpsConsole` nào được dựng, nên
    `use_utf8_stdout()` phải được gọi ở đầu `main()`. Bản đầu để `_make_console()` lo
    việc đó và `ops_ctl --help` nổ `UnicodeEncodeError` trên console Windows mặc định.
    """
    import inspect

    source = inspect.getsource(ops_ctl.main)
    assert "use_utf8_stdout()" in source
    assert source.index("use_utf8_stdout()") < source.index("build_parser()")
