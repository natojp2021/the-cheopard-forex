# -*- coding: utf-8 -*-
"""`fx_data.parquet_only()` — backtest KHÔNG được chạy trên nến live.

LỖI ĐÃ TÌM RA 16/08/2026
=========================
`USE_MT5_BARS` là cờ TOÀN CỤC đọc từ biến môi trường, nhưng cùng một `load_m1`
phục vụ hai mục đích trái ngược:

    · TÍN HIỆU LIVE  cần nến MỚI NHẤT              → MT5
    · BACKTEST       cần 6,5 năm CỐ ĐỊNH           → parquet

Trên VPS (`FX_BARS_FROM_MT5=1`), `engine._read_portfolio` → `PF.backtest()` →
`daily_bars()` → `load_m1()` nhận về 200.000 nến M1 = **6,6 tháng** thay vì 6,5
năm. Mẫu ngắn hơn 11 lần, mà `sharpe_all` / `max_dd_sd` / `worst_day_sd` /
`years_positive` vẫn được báo như số toàn mẫu. Không lỗi, không cảnh báo.
"""
from __future__ import annotations

import threading

import pandas as pd
import pytest

from src.python.shared import fx_data as D


@pytest.fixture
def _fake(monkeypatch):
    """Bật cờ live và đếm xem nhánh MT5 có bị gọi không."""
    hits = {"mt5": 0, "parquet": 0}
    fake = pd.DataFrame({"close": [1.0]}, index=pd.to_datetime(["2026-08-16"]))

    def _mt5(sym, *a, **k):
        hits["mt5"] += 1
        return fake

    def _pq(sym):
        hits["parquet"] += 1
        return fake

    monkeypatch.setattr(D, "USE_MT5_BARS", True, raising=False)
    monkeypatch.setattr("src.python.shared.mt5_bars.load_m1", _mt5)
    monkeypatch.setattr(D, "_load_m1_parquet", _pq)
    return hits


def test_live_path_uses_mt5_by_default(_fake):
    """Ngoài khối `parquet_only`, cờ live phải giữ nguyên tác dụng."""
    D.load_m1("EURUSD")
    assert _fake["mt5"] == 1 and _fake["parquet"] == 0


def test_backtest_path_forced_to_parquet(_fake):
    """Trong khối, KHÔNG được chạm MT5 — đây là bất biến chính."""
    with D.parquet_only():
        D.load_m1("EURUSD")
    assert _fake["mt5"] == 0, "backtest vẫn đọc nến MT5 → mẫu ngắn hơn 11 lần"
    assert _fake["parquet"] == 1


def test_flag_restored_after_block(_fake):
    """Ra khỏi khối thì trả lại nguyên trạng — không rò rỉ sang lượt sau."""
    with D.parquet_only():
        pass
    D.load_m1("EURUSD")
    assert _fake["mt5"] == 1


def test_nested_blocks_restore_correctly(_fake):
    """Lồng nhau phải trả về đúng trạng thái CỦA TẦNG NGOÀI, không phải False cứng."""
    with D.parquet_only():
        with D.parquet_only():
            D.load_m1("EURUSD")
        D.load_m1("EURUSD")          # vẫn trong tầng ngoài → vẫn parquet
    assert _fake["mt5"] == 0
    assert _fake["parquet"] == 2


def test_flag_is_thread_local(_fake):
    """Luồng backtest KHÔNG được ép luồng live đọc parquet.

    Một cờ chung sẽ biến bản vá thành đúng cái bệnh nó chữa, chỉ đổi chiều: thay vì
    backtest chạy trên nến live, thì live chạy trên parquet cũ.
    """
    seen = {}
    started = threading.Event()
    release = threading.Event()

    def _worker():
        started.set()
        release.wait(timeout=5)
        seen["forced_in_other_thread"] = D._parquet_forced()

    t = threading.Thread(target=_worker)
    t.start()
    started.wait(timeout=5)
    with D.parquet_only():
        release.set()
        t.join(timeout=5)
    assert seen.get("forced_in_other_thread") is False, (
        "cờ rò rỉ sang luồng khác — live sẽ đọc parquet cũ")


def test_engine_wraps_portfolio_backtest():
    """`_read_portfolio` phải thật sự dùng khối này, không chỉ có hàm nằm đó."""
    import inspect

    from src.python.core import engine as E

    src = inspect.getsource(E.TradingEngine._read_portfolio)
    assert "parquet_only()" in src, "backtest danh mục chưa được ép parquet"
