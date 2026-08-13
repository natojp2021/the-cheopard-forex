"""Cổng dữ liệu ôi + lưới D1 — nối/sửa 22/08/2026.

Hai việc, cùng một họ "lớp bảo vệ chỉ có trên giấy":

1. `mt5_bars.freshness()` tồn tại từ 15/08 và hai docstring trong `fx_data.py` khai
   rằng cổng chặn dữ liệu ôi nằm ở `engine._build_plan`. Rà 22/08: hàm chưa từng
   được gọi ở đâu. Nay đã nối — và test dưới đây khoá cả ba vế: sổ tuổi dữ liệu
   được ghi cho CẢ HAI nhánh nguồn, ngưỡng chặn hoạt động, và cổng chặn đi qua
   `extra_blocks` chứ không khoá đường thoát.
2. `resample(..., origin="start_day")` với freq `"1D"` là MÌN CHỜ NÂNG PHIÊN BẢN:
   `"start_day"` vốn là mặc định nên nó không điều khiển gì, mà hành vi của
   `origin` lại khác nhau giữa hai bản pandas — 2.3.3 (venv này) HONOUR nó, 3.0.3
   (hệ `quant-xau`) BỎ QUA kèm `RuntimeWarning`. Code dựa vào `origin` để đổi lưới
   D1 vì thế chạy đúng hôm nay và âm thầm đổi hành vi ngay khi nâng pandas. Test
   khoá lại "lưới D1 là nửa đêm UTC" như một sự thật ĐƯỢC KIỂM, thay vì một tham
   số mà ý nghĩa phụ thuộc phiên bản.
"""
from __future__ import annotations

import datetime as dt
import warnings

import pandas as pd
import pytest

from src.python.execution.entry_gate import EntryGate
from src.python.shared import fx_data as FD
from src.python.shared import mt5_bars as MB


@pytest.fixture(autouse=True)
def _clean():
    MB.reset_staleness()
    MB.reset_offset_cache()
    yield
    MB.reset_staleness()
    MB.reset_offset_cache()


def _m1(start: str, minutes: int) -> pd.DataFrame:
    idx = pd.date_range(start, periods=minutes, freq="1min")
    return pd.DataFrame({"open": 1.1, "high": 1.1, "low": 1.1, "close": 1.1,
                         "spread_usd": 3e-5, "volume": 10.0}, index=idx)


# ───────────────────────────── 1. sổ tuổi dữ liệu ─────────────────────────────
def test_note_bars_records_newest_bar():
    MB.note_bars("EURUSD", _m1("2026-08-22 08:00", 60))
    now = pd.Timestamp("2026-08-22 09:30")
    # 60 nến từ 08:00 -> nến cuối nhãn 08:59; now 09:30 => 31 phút = 0,5167h
    assert MB.staleness(now)["EURUSD"] == pytest.approx(31 / 60, abs=1e-3)


def test_note_bars_ignores_empty_and_none():
    MB.note_bars("EURUSD", None)
    MB.note_bars("GBPUSD", _m1("2026-08-22 08:00", 0))
    assert MB.staleness(pd.Timestamp("2026-08-22 09:00")) == {}


def test_stale_symbols_only_reports_what_exceeds_threshold():
    MB.note_bars("EURUSD", _m1("2026-08-22 08:00", 60))      # cũ 0,6h
    MB.note_bars("AUDCAD", _m1("2026-07-25 08:00", 60))      # cũ ~28 ngày
    stale = MB.stale_symbols(now=pd.Timestamp("2026-08-22 09:30"))
    assert set(stale) == {"AUDCAD"}, "chỉ công cụ vượt ngưỡng mới bị báo"
    assert stale["AUDCAD"] > 600


def test_threshold_catches_the_28_day_incident_with_margin():
    """Sự cố 15/08/2026 (parquet cũ 28 ngày) phải bị bắt với biên lớn."""
    assert MB.STALE_MAX_AGE_H <= 24.0
    assert 28 * 24 / MB.STALE_MAX_AGE_H >= 100


def test_load_m1_records_staleness_on_parquet_branch(monkeypatch):
    """Nhánh parquet là nhánh NGUY HIỂM NHẤT — nó trả DataFrame hợp lệ của tháng trước."""
    cu = _m1("2026-07-25 08:00", 60)
    monkeypatch.setattr(FD, "USE_MT5_BARS", False)
    monkeypatch.setattr(FD, "_load_m1_parquet", lambda sym: cu)
    FD.load_m1("AUDCAD")
    assert "AUDCAD" in MB.staleness(pd.Timestamp("2026-08-22 09:00"))


def test_load_m1_records_staleness_on_mt5_branch(monkeypatch):
    tuoi = _m1("2026-08-22 08:00", 60)
    monkeypatch.setattr(FD, "USE_MT5_BARS", True)
    monkeypatch.setattr(FD, "_parquet_forced", lambda: False)
    monkeypatch.setattr(MB, "load_m1", lambda sym, *a, **k: tuoi)
    FD.load_m1("EURUSD")
    assert "EURUSD" in MB.staleness(pd.Timestamp("2026-08-22 09:00"))


# ───────────────────── 2. cổng chặn, nhưng KHÔNG khoá đường thoát ─────────────
def test_gate_blocks_on_extra_blocks():
    g = EntryGate.evaluate(
        reconciliation_done=True, trading_enabled=True, ftmo_entries_allowed=True,
        leverage=3.5, unprotected_positions=0,
        extra_blocks=["DỮ LIỆU ÔI: 1 công cụ có nến mới nhất cũ hơn 2h"])
    assert g.allowed is False
    assert any("DỮ LIỆU ÔI" in r for r in g.reasons)


def test_gate_allows_when_nothing_is_stale():
    g = EntryGate.evaluate(
        reconciliation_done=True, trading_enabled=True, ftmo_entries_allowed=True,
        leverage=3.5, unprotected_positions=0, extra_blocks=[])
    assert g.allowed is True


def test_order_plan_build_accepts_extra_blocks():
    """`build()` phải chuyển tiếp `extra_blocks` xuống cổng, mặc định rỗng."""
    import inspect

    from src.python.execution import order_plan as OP
    sig = inspect.signature(OP.build)
    assert "extra_blocks" in sig.parameters
    assert sig.parameters["extra_blocks"].default is None, (
        "mặc định phải là None/rỗng để mọi script gọi `build()` không đổi hành vi")


def test_engine_wires_the_gate_instead_of_returning_early():
    """Cổng phải đi qua `extra_blocks`, KHÔNG phải `return` sớm.

    `return` sớm sẽ khoá luôn `order_router.route()` — tức time-stop và lệnh đóng
    không tới được broker, đúng lỗi đã sửa ngày 15/08/2026.
    """
    import inspect

    from src.python.core import engine as EG
    # Bỏ COMMENT trước khi phân tích. Khối chú thích trong `_build_plan` kể lại
    # chính lỗi 15/08 nên nó có cả chữ "return" lẫn "order_router.route()" —
    # so chuỗi trên nguyên văn nguồn sẽ khớp vào chú thích và báo oan.
    code = [l for l in inspect.getsource(EG.TradingEngine._build_plan).splitlines()
            if not l.strip().startswith("#")]
    src = "\n".join(code)
    assert "stale_symbols" in src, "cổng dữ liệu ôi phải được gọi trong `_build_plan`"
    assert "extra_blocks=extra_blocks" in src, "phải truyền xuống `OP.build`"
    i_stale = src.index("stale_symbols")
    i_route = src.index("router.route(")
    assert i_stale < i_route, "phải đo TRƯỚC khi gửi lệnh"
    giua = src[i_stale:i_route].splitlines()
    assert not any(l.strip() == "return" or l.strip().startswith("return ")
                   for l in giua), (
        "không được `return` sớm giữa cổng dữ liệu ôi và router — đó là khoá "
        "đường thoát của vị thế đang mở")


def test_unmeasurable_staleness_fails_closed(monkeypatch):
    """Không đo được tuổi dữ liệu KHÔNG được hiểu là 'dữ liệu tươi'."""
    import inspect

    from src.python.core import engine as EG
    src = inspect.getsource(EG.TradingEngine._build_plan)
    assert "fail-closed" in src and "không đo được tuổi dữ liệu" in src


# ─────────────────────────── 3. lưới D1 là nửa đêm UTC ───────────────────────
def test_origin_for_daily_freq_is_version_dependent():
    """`origin` với freq "1D" ĐỔI HÀNH VI THEO PHIÊN BẢN pandas — mìn chờ nâng cấp.

        pandas 2.3.3 (venv này)        `origin` CÓ tác dụng
        pandas 3.0.3 (hệ `quant-xau`)  `origin` bị BỎ QUA + `RuntimeWarning`

    Nên không code nào được dựa vào `origin` để đổi lưới nến D1: nó chạy đúng hôm
    nay và âm thầm đổi hành vi ngay khi nâng pandas. Test này ghi lại phiên bản
    hiện tại đang ở nhánh nào, để lần nâng cấp tới có một chỗ báo.
    """
    df = _m1("2026-08-17 00:00", 60 * 30)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        a = df.resample("1D", origin=pd.Timestamp("1970-01-01 21:00")).close.last()
    bi_bo_qua = any("origin" in str(x.message) for x in w)
    b = df.resample("1D").close.last()
    co_tac_dung = list(a.index) != list(b.index)
    assert co_tac_dung != bi_bo_qua, (
        "pandas phải RÕ RÀNG ở một trong hai nhánh: honour `origin` (lưới dịch) "
        "hoặc bỏ qua kèm cảnh báo. Không được im lặng mà cũng không đổi gì.")
    if bi_bo_qua:
        assert list(a.index) == list(b.index)


def test_daily_grid_is_utc_midnight():
    df = _m1("2026-08-17 00:00", 60 * 72)
    d1 = FD.build_bars(df, "D1")
    assert len(d1) > 0
    assert {t.hour for t in d1.index} == {0}


def test_build_bars_daily_emits_no_origin_warning():
    """Bỏ `origin=` khỏi nhánh '1D' nên không còn `RuntimeWarning` nào."""
    df = _m1("2026-08-17 00:00", 60 * 72)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        FD.build_bars(df, "D1")
    assert not [x for x in w if "origin" in str(x.message)], (
        f"vẫn còn cảnh báo về `origin`: {[str(x.message) for x in w]}")
