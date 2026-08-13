"""Nến MT5 phải trả về chỉ mục UTC — kiểm toán chéo 22/08/2026 từ hệ `quant-xau`.

`mt5_bars.load_m1()` trước đây làm `pd.to_datetime(rates["time"], unit="s")` rồi trả
luôn, nhưng `rates["time"]` mang GIỜ MÁY CHỦ (Đông Âu: UTC+3 hè / UTC+2 đông) trong
khi `fx_data._load_m1_parquet` trả UTC. Cả `mt5_bars` tồn tại để hai nguồn thay thế
được cho nhau, nên lệch 2-3 giờ ở đây phá đúng cái nó bảo vệ:

  1. `cross_mean_reversion` chặn theo `ts.hour` với cửa sổ 10-16 UTC — ở live cửa sổ
     THẬT chạy 07-13 UTC, tức giao dịch đúng những giờ nghiên cứu đã loại.
  2. `build_bars("4h")`/`daily_bars()` gộp theo `origin="start_day"` -> biên nến H4/D1
     lệch 2-3 giờ so với backtest (bốn chân H4, ba chân D1).
  3. `freshness()` cho tuổi dữ liệu ÂM -> cổng chặn dữ liệu ôi không bao giờ kích hoạt.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.python.shared import mt5_bars as MB


class _Tick:
    def __init__(self, epoch: int):
        self.time = epoch


class _FakeMT5:
    """Chỉ đủ để `load_m1` chạy: nến M1 + tick + point."""
    TIMEFRAME_M1 = 1

    def __init__(self, first_bar_server: dt.datetime, n: int, tick_epoch: int | None):
        # `rates["time"]` của MT5 là epoch mà `utcfromtimestamp()` cho ra ĐÚNG giờ
        # trên chart (giờ máy chủ) — nên phải gắn tzinfo=utc khi dựng, không để
        # naive (naive sẽ bị `.timestamp()` hiểu là giờ máy chạy test).
        base = first_bar_server.replace(tzinfo=dt.timezone.utc)
        self._bars = [
            {"time": int((base + dt.timedelta(minutes=i)).timestamp()),
             "open": 1.1, "high": 1.1, "low": 1.1, "close": 1.1,
             "spread": 3, "tick_volume": 10}
            for i in range(n)
        ]
        self._tick_epoch = tick_epoch

    def symbol_select(self, symbol, enable=True):
        return True

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        return self._bars[-int(count):]

    def symbol_info_tick(self, symbol):
        return _Tick(self._tick_epoch) if self._tick_epoch else None

    def symbol_info(self, symbol):
        return type("I", (), {"point": 1e-5})()


@pytest.fixture(autouse=True)
def _clear_cache():
    MB.reset_offset_cache()
    yield
    MB.reset_offset_cache()


@pytest.mark.parametrize("ngay,offset_mong_doi", [
    ("2026-01-15", 2),   # mùa đông — EET
    ("2026-06-15", 3),   # mùa hè — EEST
    ("2026-03-28", 2),   # thứ Bảy TRƯỚC chủ nhật cuối tháng 3
    ("2026-03-29", 3),   # chủ nhật cuối tháng 3, sau 01:00 UTC
    ("2026-10-24", 3),   # thứ Bảy TRƯỚC chủ nhật cuối tháng 10
    ("2026-10-25", 2),   # chủ nhật cuối tháng 10, sau 01:00 UTC
])
def test_dst_calendar_follows_european_schedule(ngay, offset_mong_doi):
    t = dt.datetime.fromisoformat(f"{ngay}T12:00:00+00:00")
    assert MB.dst_calendar_offset_hours(t) == offset_mong_doi


def test_offset_measured_from_tick_wins_over_calendar():
    """Đo bằng tick là đường CHÍNH — đúng cho cả broker không chạy giờ Đông Âu."""
    now = dt.datetime(2026, 8, 22, 10, 0, tzinfo=dt.timezone.utc)
    srv = int(dt.datetime(2026, 8, 22, 15, 0, tzinfo=dt.timezone.utc).timestamp())
    mt5 = _FakeMT5(dt.datetime(2026, 8, 22, 9, 0), 10, srv)
    assert MB.server_offset_hours(mt5, "EURUSD", now) == 5, (
        "offset phải ĐO từ tick, không suy từ lịch — lịch chỉ là lưới an toàn")


def test_offset_falls_back_to_calendar_when_tick_is_stale():
    """Cuối tuần/mất kết nối: tick cũ nhiều ngày, phép trừ không còn đo múi giờ."""
    now = dt.datetime(2026, 8, 22, 10, 0, tzinfo=dt.timezone.utc)
    stale = int(dt.datetime(2026, 8, 20, 13, 0, tzinfo=dt.timezone.utc).timestamp())
    mt5 = _FakeMT5(dt.datetime(2026, 8, 22, 9, 0), 10, stale)
    assert MB.server_offset_hours(mt5, "EURUSD", now) == 3      # EEST theo lịch


def test_offset_falls_back_to_calendar_without_tick():
    now = dt.datetime(2026, 1, 15, 10, 0, tzinfo=dt.timezone.utc)
    mt5 = _FakeMT5(dt.datetime(2026, 1, 15, 9, 0), 10, None)
    assert MB.server_offset_hours(mt5, "EURUSD", now) == 2      # EET theo lịch


def test_load_m1_index_is_utc_not_server_time(monkeypatch):
    """Bất biến chính: nhãn nến trả về đã LÙI đúng offset máy chủ."""
    # Nến máy chủ 13:00-13:09; máy chủ = UTC+3 -> UTC phải là 10:00-10:09.
    now = dt.datetime(2026, 8, 22, 10, 9, tzinfo=dt.timezone.utc)
    srv_tick = int(dt.datetime(2026, 8, 22, 13, 9, tzinfo=dt.timezone.utc).timestamp())
    mt5 = _FakeMT5(dt.datetime(2026, 8, 22, 13, 0), 10, srv_tick)
    monkeypatch.setattr(MB, "server_offset_hours", lambda *a, **k: 3)
    df = MB.load_m1("EURUSD", mt5, n_bars=10)
    assert df is not None and len(df) == 10
    assert str(df.index[0]) == "2026-08-22 10:00:00"
    assert str(df.index[-1]) == "2026-08-22 10:09:00"


def test_freshness_is_not_negative_once_index_is_utc(monkeypatch):
    """Hệ quả của bất biến trên: cổng dữ liệu ôi mới đo được tuổi THẬT.

    Với chỉ mục còn ở giờ máy chủ, `freshness()` trả số ÂM (nến "ở tương lai") nên
    mọi ngưỡng chặn đều vô hiệu. Sau khi quy về UTC, tuổi dữ liệu tươi ≈ 0.
    """
    now = dt.datetime(2026, 8, 22, 10, 10, tzinfo=dt.timezone.utc)
    srv_tick = int(dt.datetime(2026, 8, 22, 13, 9, tzinfo=dt.timezone.utc).timestamp())
    mt5 = _FakeMT5(dt.datetime(2026, 8, 22, 13, 0), 10, srv_tick)
    monkeypatch.setattr(MB, "server_offset_hours", lambda *a, **k: 3)
    df = MB.load_m1("EURUSD", mt5, n_bars=10)
    tuoi = MB.freshness(df, now=pd.Timestamp(now).tz_localize(None))
    assert 0.0 <= tuoi < 0.5, f"tuổi dữ liệu phải dương và nhỏ, nhận {tuoi:.3f} giờ"


def test_h4_boundary_from_mt5_bars_matches_utc_grid(monkeypatch):
    """Biên nến H4 dựng từ nến MT5 phải trùng lưới UTC — cùng lưới với parquet."""
    from src.python.shared import fx_data as FD
    now = dt.datetime(2026, 8, 22, 9, 0, tzinfo=dt.timezone.utc)
    srv_tick = int(dt.datetime(2026, 8, 22, 12, 0, tzinfo=dt.timezone.utc).timestamp())
    # 12 giờ nến M1 liên tục, bắt đầu 00:00 giờ máy chủ = 21:00 UTC hôm trước.
    mt5 = _FakeMT5(dt.datetime(2026, 8, 22, 0, 0), 12 * 60, srv_tick)
    monkeypatch.setattr(MB, "server_offset_hours", lambda *a, **k: 3)
    m1 = MB.load_m1("EURUSD", mt5, n_bars=12 * 60)
    h4 = FD.build_bars(m1, "H4")
    assert len(h4) > 0
    assert {t.hour for t in h4.index} <= {0, 4, 8, 12, 16, 20}, (
        "biên H4 phải nằm trên lưới UTC 00/04/08/12/16/20 — nếu lệch thì bốn chân H4 "
        "đang chạy trên chuỗi nến khác chuỗi backtest đã kiểm định")
