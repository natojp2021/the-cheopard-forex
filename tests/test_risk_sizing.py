"""Cỡ lệnh từ khoảng cách SL. Ba nhóm bất biến, và cả ba đều là chỗ mất tài khoản.

  1. ĐƠN VỊ       một chạm SL phải mất ĐÚNG `risk_pct`% equity, trên CẢ HAI họ cặp.
                  Giá trị 1 pip của 1 lot KHÁC NHAU giữa EURUSD ($10 cố định) và
                  USDJPY (1.000 JPY, tức ~$6,7 ở giá 150) — dùng $10 cho mọi cặp là
                  sai cỡ lệnh tới 33%.
  2. FAIL-CLOSED  không tính được rủi ro thì lot = 0, KÈM LÝ DO. Trả một con số
                  "trông hợp lý" là cách hệ mở vị thế với rủi ro không ai chọn.
  3. TRẦN         rủi ro mở ĐỒNG THỜI phải cộng được và phải chặn được TRƯỚC khi gửi.
"""
from __future__ import annotations

import pytest

from src.python.execution import risk_sizing as RS
from src.python.shared import asset_profile as AP

EQUITY = 100_000.0
PRICES = {"EURUSD": 1.0850, "GBPUSD": 1.2700, "USDJPY": 150.20}


# ═══════════════════════════════════════════════════════════════ 1. ĐƠN VỊ
@pytest.mark.parametrize("symbol,entry,stop", [
    ("EURUSD", 1.08500, 1.08200),          # 30 pip
    ("GBPUSD", 1.27000, 1.27400),          # 40 pip, chiều BÁN
    ("USDJPY", 150.200, 150.500),          # 30 pip, quote JPY
])
def test_one_stop_hit_loses_exactly_the_requested_percent(symbol, entry, stop):
    r = RS.lots_for_risk(symbol, entry_price=entry, stop_price=stop,
                         equity_usd=EQUITY, risk_pct=0.45, prices=PRICES)
    assert r.ok, r.reason
    want = EQUITY * 0.45 / 100.0
    # Sai số duy nhất được phép là LÀM TRÒN LOT (bước 0,01) — không phải sai đơn vị.
    tol = 0.01 * r.sl_pips * r.value_per_pip_per_lot
    assert abs(r.risk_usd - want) <= tol, (
        f"{symbol}: rủi ro {r.risk_usd:.2f} lệch khỏi {want:.2f} quá mức làm tròn "
        f"({tol:.2f}) — {r.explain()}")


def test_pip_value_differs_between_pair_families():
    """EURUSD 1 pip/lot = $10 cố định; USDJPY phụ thuộc TỶ GIÁ. Dùng chung là sai 33%."""
    eur = RS.lots_for_risk("EURUSD", entry_price=1.0850, stop_price=1.0820,
                           equity_usd=EQUITY, risk_pct=0.45, prices=PRICES)
    jpy = RS.lots_for_risk("USDJPY", entry_price=150.20, stop_price=150.50,
                           equity_usd=EQUITY, risk_pct=0.45, prices=PRICES)
    assert eur.value_per_pip_per_lot == pytest.approx(10.0, rel=1e-6)
    assert jpy.value_per_pip_per_lot == pytest.approx(1000.0 / 150.20, rel=1e-3)
    assert abs(jpy.value_per_pip_per_lot - eur.value_per_pip_per_lot) > 1.0


def test_notional_does_not_multiply_price_for_usd_base_pairs():
    """USDJPY: 1 lot = 100.000 USD, KHÔNG nhân giá. Nhân giá là sai 150 lần."""
    r = RS.lots_for_risk("USDJPY", entry_price=150.20, stop_price=150.50,
                         equity_usd=EQUITY, risk_pct=0.45, prices=PRICES)
    assert r.notional_usd == pytest.approx(100_000.0 * r.lots, rel=1e-9)


def test_lot_notional_usd_refuses_to_guess_for_cross_pairs():
    """Cặp chéo thiếu tỷ giá quote->USD phải NỔ, không mặc định 1,0."""
    with pytest.raises(ValueError, match="usd_per_quote"):
        RS.lot_notional_usd("EURJPY", 160.0)
    got = RS.lot_notional_usd("EURJPY", 160.0, 1.0 / 150.0)
    assert got == pytest.approx(100_000.0 * 160.0 / 150.0, rel=1e-9)


# ═══════════════════════════════════════════════════════════ 2. FAIL-CLOSED
@pytest.mark.parametrize("kwargs,needle", [
    (dict(entry_price=1.0850, stop_price=1.0850), "khoảng cách 0"),
    (dict(entry_price=1.0850, stop_price=0.0), "không dương"),
    (dict(entry_price=1.0850, stop_price=1.08495), "khoảng dừng tối thiểu"),
])
def test_bad_stop_gives_zero_lots_with_a_reason(kwargs, needle):
    r = RS.lots_for_risk("EURUSD", equity_usd=EQUITY, risk_pct=0.45,
                         prices=PRICES, **kwargs)
    assert not r.ok and r.lots == 0.0
    assert needle in r.reason, r.reason


def test_missing_quote_rate_gives_zero_lots_not_a_default_of_one():
    """Không có bảng giá cho cặp quote != USD: lot 0, KHÔNG mặc định 1,0."""
    r = RS.lots_for_risk("USDJPY", entry_price=150.20, stop_price=150.50,
                         equity_usd=EQUITY, risk_pct=0.45)
    assert not r.ok and "usd_per_quote" in r.reason


def test_risk_pct_above_hard_cap_is_refused():
    """Vượt trần cứng/vị thế là dấu hiệu LỖI ĐƠN VỊ, không phải một lựa chọn."""
    r = RS.lots_for_risk("EURUSD", entry_price=1.0850, stop_price=1.0820,
                         equity_usd=EQUITY,
                         risk_pct=RS.MAX_RISK_PCT_PER_POSITION + 0.01, prices=PRICES)
    assert not r.ok and "trần cứng" in r.reason


def test_non_positive_equity_gives_zero_lots():
    for eq in (0.0, -1.0):
        r = RS.lots_for_risk("EURUSD", entry_price=1.0850, stop_price=1.0820,
                             equity_usd=eq, risk_pct=0.45, prices=PRICES)
        assert not r.ok and "equity" in r.reason


def test_risk_too_small_for_min_lot_gives_zero_not_a_rounded_up_lot():
    """Rủi ro nhỏ hơn một lot tối thiểu: KHÔNG được làm tròn LÊN.

    Làm tròn lên là vào lệnh với rủi ro LỚN HƠN mức đã chọn — im lặng.
    """
    r = RS.lots_for_risk("EURUSD", entry_price=1.0850, stop_price=1.0450,
                         equity_usd=500.0, risk_pct=0.05, prices=PRICES)
    assert not r.ok and "lot tối thiểu" in r.reason


# ═══════════════════════════════════════════════════════════════ 3. TRẦN
def test_total_risk_is_the_sum_over_the_book():
    targets = {
        "EURUSD": {"side": -1.0, "entry": 1.0850, "stop": 1.0880},
        "GBPUSD": {"side": +1.0, "entry": 1.2700, "stop": 1.2660},
        "USDJPY": {"side": -1.0, "entry": 150.20, "stop": 150.50},
    }
    book = RS.size_book(targets, equity_usd=EQUITY, risk_pct=0.45, prices=PRICES)
    assert all(r.ok for r in book.values()), {k: v.reason for k, v in book.items()}
    total = RS.total_risk_pct(book, EQUITY)
    assert total == pytest.approx(3 * 0.45, abs=0.05), total


def test_one_bad_symbol_does_not_drop_the_whole_book():
    """Fail-closed ở mức CÔNG CỤ: mất một cơ hội, không mất cả phiên."""
    targets = {
        "EURUSD": {"side": -1.0, "entry": 1.0850, "stop": 1.0880},
        "GBPUSD": {"side": +1.0, "entry": 1.2700, "stop": 1.2700},   # SL trùng giá vào
    }
    book = RS.size_book(targets, equity_usd=EQUITY, risk_pct=0.45, prices=PRICES)
    assert book["EURUSD"].ok
    assert not book["GBPUSD"].ok and book["GBPUSD"].reason


def test_zero_equity_gives_zero_total_risk_not_a_division_error():
    assert RS.total_risk_pct({}, 0.0) == 0.0
