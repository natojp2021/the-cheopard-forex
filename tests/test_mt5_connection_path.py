# -*- coding: utf-8 -*-
"""ĐƯỜNG KẾT NỐI MT5 — đối chiếu 1-1 với hệ XAUUSD.

LỖ HỔNG ĐÃ TÌM RA 16/08/2026
=============================
`core/infra/mt5_bridge.py` của hai repo GIỐNG HỆT NHAU — cùng số dòng, cùng tên hàm,
cùng `init_mt5` / `reconnect_mt5` / `check_mt5_health`. Nhưng bên XAUUSD
`engine.start()` gọi `init_mt5()` ở bước 2, còn bên Forex **KHÔNG AI GỌI**: quét cả
`src/` chỉ ra ba dòng CHÚ THÍCH nhắc tên nó.

Lớp kết nối tốt nhất của dự án nằm đó dưới dạng CODE CHẾT, trong khi `_read_broker`
tự viết lại một bản yếu hơn ngay trong vòng lặp 5 giây. Cùng họ lỗi với `ftmo_guard`
và `risk_guard.check_kill_switch` — thứ trông như lớp bảo vệ nhưng không chạy.

Bốn test dưới đây khoá lại bốn mắt xích, để không mắt nào lặng lẽ đứt lần nữa.
"""
from __future__ import annotations

import inspect

from src.python.core import engine as E
from src.python.core.infra import mt5_bridge as B


def test_startup_actually_calls_init_mt5():
    """`start_loop` phải đi qua `_connect_once` → `init_mt5`. Đây là mắt xích ĐÃ ĐỨT."""
    assert "_connect_once" in inspect.getsource(E.TradingEngine.start_loop)
    assert "init_mt5" in inspect.getsource(E.TradingEngine._connect_once)


def test_init_mt5_primes_every_symbol():
    """`init_mt5` phải hâm nóng CẢ danh mục, không chỉ `SYMBOL` đầu bảng chữ cái.

    Bản XAUUSD gọi `symbol_select(SYMBOL, True)` — đúng cho hệ MỘT tài sản. Ở đây
    `SYMBOL = SYMBOLS[0]` chỉ là công cụ đầu bảng chữ cái trong 27 công cụ.
    """
    assert "_prime_symbols" in inspect.getsource(B.init_mt5)
    assert not hasattr(B, "_select_all_symbols"), "còn sót tên hàm cũ"


def test_prime_symbols_forces_history_download():
    """Hâm nóng phải GỌI `copy_rates_from_pos`, không chỉ `symbol_select`.

    `symbol_select` đưa công cụ vào Market Watch nhưng KHÔNG kích hoạt tải nến. Chỉ
    `copy_rates_from_pos` mới làm, và lần đầu nó khởi động tải bất đồng bộ rồi trả
    RỖNG — đó là nguyên nhân thật của "0/1 bar" trên VPS.
    """
    src = inspect.getsource(B._prime_symbols)
    assert "symbol_select" in src
    assert "copy_rates_from_pos" in src, (
        "chỉ select mà không fetch thì lịch sử không bao giờ được tải")


def test_prime_symbols_reports_pending_and_never_raises(monkeypatch):
    """Công cụ thiếu lịch sử phải được NÊU TÊN, và không được làm hỏng kết nối."""
    calls = {"select": [], "rates": []}

    class _MT5:
        TIMEFRAME_M1 = 1

        def symbol_select(self, sym, enable=True):
            calls["select"].append(sym)
            return True

        def copy_rates_from_pos(self, sym, tf, start, count):
            calls["rates"].append(sym)
            return [] if sym == "EURUSD" else [1]

    monkeypatch.setattr(B, "mt5", _MT5())
    monkeypatch.setattr("time.sleep", lambda *_: None)
    msgs = []
    monkeypatch.setattr(B, "log_error", lambda m, *a: msgs.append(m))
    monkeypatch.setattr(B, "log", lambda m, *a: None)

    ready, pending = B._prime_symbols()

    # Rổ lấy từ SSOT, không gõ lại một con số: thêm/bớt công cụ là test tự theo.
    from src.python.strategies import portfolio as PF
    want = set(PF.LEG_INSTRUMENT.values())
    got = set(calls["select"])
    assert got >= want, (
        f"thiếu công cụ trong `symbol_select`: {sorted(want - got)}")
    assert pending == ["EURUSD"], pending
    # Số công cụ SẴN SÀNG = rổ trừ đúng cái không có lịch sử. Neo vào rổ thật thay
    # vì một con số cứng — con số cứng là chỗ test nói dối khi rổ đổi.
    assert ready == len(got) - 1, (ready, sorted(got))
    assert any("EURUSD" in m for m in msgs), "không nêu tên công cụ thiếu lịch sử"
    assert any("PARQUET" in m for m in msgs), "không nói HẬU QUẢ"


def test_connect_failure_does_not_block_startup(monkeypatch):
    """Nối hỏng thì bảng VẪN lên — khác XAUUSD có chủ ý.

    Bên đó một tài sản, không nối được thì không có gì để làm. Bên này bảng phải lên
    để người vận hành đọc được LÝ DO, và `entry_gate` đã fail-closed nên không kết
    nối thì cũng không có lệnh nào ra.
    """
    eng = E.TradingEngine.__new__(E.TradingEngine)
    errs = []
    monkeypatch.setattr(eng, "log_error", lambda m: errs.append(m), raising=False)
    monkeypatch.setattr("src.python.core.infra.mt5_bridge.init_mt5", lambda: False)

    assert eng._connect_once() is False
    assert errs and "check_mt5_connection.py" in errs[0], (
        "không chỉ ra công cụ chẩn đoán")
