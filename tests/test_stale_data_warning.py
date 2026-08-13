# -*- coding: utf-8 -*-
"""Cảnh báo DỮ LIỆU CŨ — phải kêu, và phải kêu vừa đủ.

Khi `FX_BARS_FROM_MT5=1` mà MT5 không trả được nến, hệ lùi về parquet lịch sử. Hai
nguồn CÙNG HÌNH DẠNG nên chiến lược không phân biệt được — nếu cổng tươi mới ở
`engine._build_plan` có lúc nào đó hỏng, hệ sẽ vào lệnh thật trên giá của tuần
trước mà không có gì báo. Dòng cảnh báo này là lớp duy nhất đứng trước tình huống đó.

Nhưng `load_m1` được gọi cho 7 công cụ ở mỗi lượt dựng kế hoạch, nên cảnh báo không
giới hạn sẽ lấp kín nhật ký và bị lọc bỏ — mất đúng tác dụng nó sinh ra để có.
"""
from __future__ import annotations

import pytest

from src.python.shared import fx_data


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(fx_data, "_MT5_BARS_MISSING", {}, raising=False)


def _messages(monkeypatch) -> list:
    out = []
    import src.python.utils.logger as L

    monkeypatch.setattr(L, "log_error", lambda m, *a: out.append(m))
    return out


def test_warns_with_consequence_and_fix(monkeypatch):
    """Cảnh báo phải nói HẬU QUẢ, không chỉ thuật lại thao tác."""
    msgs = _messages(monkeypatch)
    fx_data._warn_stale_source("EURUSD")
    assert len(msgs) == 1
    m = msgs[0]
    assert "EURUSD" in m
    assert "PARQUET" in m, "không nói đang dùng nguồn nào"
    assert "KHÔNG phải giá hiện tại" in m, "không nói HẬU QUẢ"
    assert "Market Watch" in m, "không nói cách kiểm"


def test_repeat_is_throttled_per_symbol(monkeypatch):
    """Gọi lại ngay thì KHÔNG kêu nữa — 7 công cụ mỗi chu kỳ sẽ lấp kín nhật ký."""
    msgs = _messages(monkeypatch)
    for _ in range(20):
        fx_data._warn_stale_source("EURUSD")
    assert len(msgs) == 1, f"kêu {len(msgs)} lần cho cùng một công cụ"


def test_each_symbol_warns_separately(monkeypatch):
    """Chặn lặp theo TỪNG công cụ — GBPUSD hỏng không được bị EURUSD che mất."""
    msgs = _messages(monkeypatch)
    for s in ("EURUSD", "GBPUSD", "AUDUSD"):
        fx_data._warn_stale_source(s)
    assert len(msgs) == 3
    assert {"EURUSD", "GBPUSD", "AUDUSD"} == {
        s for s in ("EURUSD", "GBPUSD", "AUDUSD") if any(s in m for m in msgs)}


def test_warns_again_after_window(monkeypatch):
    """Quá cửa sổ thì kêu lại — hệ vẫn đang chạy trên dữ liệu cũ, đừng để quên."""
    msgs = _messages(monkeypatch)
    fx_data._warn_stale_source("EURUSD")
    fx_data._MT5_BARS_MISSING["EURUSD"] -= fx_data._STALE_WARN_EVERY + 1.0
    fx_data._warn_stale_source("EURUSD")
    assert len(msgs) == 2


def test_recovery_clears_the_throttle(monkeypatch):
    """MT5 có nến trở lại → xoá mốc, để lần hỏng KẾ TIẾP báo NGAY chứ không bị nuốt.

    Cùng lý do `alerts.reset()` tồn tại cho cặp sự kiện mất/khôi phục kết nối.
    """
    msgs = _messages(monkeypatch)
    fx_data._warn_stale_source("EURUSD")
    assert len(msgs) == 1

    import pandas as pd

    fake = pd.DataFrame({"close": [1.0]}, index=pd.to_datetime(["2026-08-16"]))
    monkeypatch.setattr(fx_data, "USE_MT5_BARS", True, raising=False)
    monkeypatch.setattr("src.python.shared.mt5_bars.load_m1",
                        lambda s, *a, **k: fake)
    assert not fx_data.load_m1("EURUSD").empty
    assert "EURUSD" not in fx_data._MT5_BARS_MISSING, "không xoá mốc khi hồi phục"

    monkeypatch.setattr("src.python.shared.mt5_bars.load_m1",
                        lambda s, *a, **k: None)
    monkeypatch.setattr(fx_data, "_load_m1_parquet", lambda s: fake)
    fx_data.load_m1("EURUSD")
    assert len(msgs) == 2, "hỏng lại mà bị mốc cũ nuốt mất"
