"""Mức log phải khớp Ý NGHĨA của thông điệp.

SỬA 21/08/2026 — DÒNG "ĐÃ XỬ LÝ ĐÚNG" GHI Ở MỨC ERROR
======================================================
`_say_once()` ghi MỌI nhánh ở mức ERROR, kể cả nhánh nói rằng mọi thứ đã được xử
lý đúng ("dùng spread SỐNG", "dùng số ĐO GẦN NHẤT"). Bộ soát log theo giờ đếm nó
là LỖI MỚI mỗi lần câu chữ đổi:

    🔴 1 LỖI MỚI:
       [1×] ERROR | [SPREAD] EURUSD: spread sống trả 0 — dùng số ĐO GẦN NHẤT ...

Hệ quả nặng hơn không phải báo động giả: người vận hành học được rằng dòng ERROR
ở đây thường vô hại, và đó chính là cách một dòng ERROR THẬT bị lướt qua.

Chỉ nhánh cuối — không đo được gì, công cụ rụng khỏi rổ — mới là ERROR.
"""
from __future__ import annotations

import pytest

from src.python.shared import mt5_bars


class _FakeInfo:
    def __init__(self, spread):
        self.spread = spread


@pytest.fixture(autouse=True)
def _reset():
    mt5_bars._LAST_GOOD_SPREAD.clear()
    mt5_bars._SPREAD_LOG_AT.clear()
    mt5_bars._SPREAD_LOG_KIND.clear()
    yield


def _capture(monkeypatch):
    seen = {"info": [], "error": []}
    import src.python.utils.logger as L

    monkeypatch.setattr(L, "log", lambda m, *a, **k: seen["info"].append(m))
    monkeypatch.setattr(L, "log_error", lambda m, *a, **k: seen["error"].append(m))
    return seen


def test_measured_fallback_is_info_not_error(monkeypatch) -> None:
    """Đo được spread sống -> ĐÃ XỬ LÝ ĐÚNG -> mức thông tin."""
    import MetaTrader5 as mt5

    seen = _capture(monkeypatch)
    monkeypatch.setattr(mt5, "symbol_info", lambda s: _FakeInfo(3), raising=False)
    mt5_bars._live_spread_fallback("EURUSD", 1e-5, 100)
    assert seen["info"] and not seen["error"], seen


def test_cached_fallback_is_info_not_error(monkeypatch) -> None:
    """Dùng số đo gần nhất cũng là xử lý đúng — không phải lỗi."""
    import MetaTrader5 as mt5

    monkeypatch.setattr(mt5, "symbol_info", lambda s: _FakeInfo(2), raising=False)
    mt5_bars._live_spread_fallback("EURUSD", 1e-5, 100)      # nạp bộ nhớ
    mt5_bars._SPREAD_LOG_AT.clear()
    mt5_bars._SPREAD_LOG_KIND.clear()
    seen = _capture(monkeypatch)
    monkeypatch.setattr(mt5, "symbol_info", lambda s: _FakeInfo(0), raising=False)
    mt5_bars._live_spread_fallback("EURUSD", 1e-5, 100)
    assert seen["info"] and not seen["error"], seen


def test_no_measurement_at_all_stays_error(monkeypatch) -> None:
    """Phần KHÔNG được hạ mức: mất hẳn nguồn đo thì công cụ rụng khỏi rổ.

    Đó là lúc hệ thật sự mất một công cụ, và nó phải nổi lên như một lỗi.
    """
    import MetaTrader5 as mt5

    seen = _capture(monkeypatch)
    monkeypatch.setattr(mt5, "symbol_info", lambda s: _FakeInfo(0), raising=False)
    mt5_bars._live_spread_fallback("EURUSD", 1e-5, 100)
    assert seen["error"] and not seen["info"], seen
