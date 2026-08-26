"""`emails.entry()` phải in TP THẬT khi có, và không được khẳng định sai về
cách tính cỡ lệnh.

SỰ CỐ 27/08/2026: người vận hành nhận thư "Vào lệnh mới — SELL EURUSD" ghi
"Chốt lời (TP): Không đặt TP cố định" và "Cỡ lệnh theo vol-targeting ...
KHÔNG suy từ khoảng cách tới cắt lỗ" — cả hai đều sai cho `AsiaSweepH1`:
chiến lược này CÓ TP=3R thật gửi cùng lệnh (bất biến 3, `order_router.
_send_one`), và cỡ lệnh đi qua `risk_sizing.size_book()` (SL + % equity →
lot), không phải công thức weight/leverage/notional thuần vol-targeting.
Root cause: `SendResult` tính rồi BỎ `take_profit` trước khi tới email —
xem `order_router.SendResult.take_profit` và `tests/test_execution_layer.py
::test_send_result_carries_take_profit_sent_to_broker`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.python.shared.notifications import emails as EM  # noqa: E402


def _capture(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        EM, "_emit",
        lambda subject, html, text, images=None: captured.update(
            subject=subject, html=html, text=text) or True)
    return captured


def test_entry_email_shows_real_tp_when_provided(monkeypatch):
    captured = _capture(monkeypatch)
    EM.entry(strategy="AsiaSweepH1", symbol="EURUSD", direction="SELL",
             lots=2.55, price=1.16506, stop_price=1.16799, tp_price=1.15200,
             weight=-1.0, leverage=5.25, equity=100025.21)

    assert "1.15200" in captured["html"]
    assert "Không đặt TP cố định" not in captured["html"]
    assert "1.15200" in captured["text"]
    assert "Không đặt TP cố định" not in captured["text"]


def test_entry_email_falls_back_when_tp_missing(monkeypatch):
    """Đối chứng: không có TP thật thì phải nói RÕ "không có", không được bịa
    số — nhưng cũng không được lặp lại câu khẳng định sai cũ."""
    captured = _capture(monkeypatch)
    EM.entry(strategy="AsiaSweepH1", symbol="EURUSD", direction="SELL",
             lots=2.55, price=1.16506, stop_price=1.16799, tp_price=None)

    assert "Không có" in captured["html"]


def test_entry_email_does_not_claim_pure_vol_targeting_sizing(monkeypatch):
    captured = _capture(monkeypatch)
    EM.entry(strategy="AsiaSweepH1", symbol="EURUSD", direction="SELL",
             lots=2.55, price=1.16506, stop_price=1.16799, tp_price=1.15200)

    assert "KHÔNG suy từ khoảng cách tới cắt lỗ" not in captured["html"]
    assert "KHÔNG suy từ khoảng cách tới cắt lỗ" not in captured["text"]
    assert "risk_sizing.size_book" in captured["html"] + captured["text"]
