"""Phiên KHÔNG có lệnh nào đóng không được gắn nhãn "✅ PHIÊN LÃI".

SỰ CỐ 27/08/2026: người vận hành nhận thư "Session Report" ghi tiêu đề
"✅ PHIÊN LÃI — 2026-08-26" ngay phía trên dòng "Không có lệnh nào đóng
trong phiên" ở khối ④ — tự mâu thuẫn trong cùng một thư. Root cause:
`send()` chỉ có hai nhánh (`is_win = net_bps >= 0`), và 0 lệnh đóng luôn
cho `net_bps = 0.0` (`build_metrics()` khởi tạo `gp = gl = 0.0` khi
`closed == []`), rơi thẳng vào nhánh "lãi". "0 lệnh" là trạng thái thứ ba
— KHÔNG GIAO DỊCH — không thuộc thang lãi/lỗ.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.python.shared.notifications import session_report as SR  # noqa: E402


def _capture(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        SR, "_emit",
        lambda subject, html, text, images=None: captured.update(
            subject=subject, html=html, text=text) or True)
    return captured


def _metrics(total_trades, net_bps=0.0):
    return {
        "date": "2026-08-26", "closed": [], "total_trades": total_trades,
        "wins": 0, "losses": 0, "win_rate": 0.0,
        "gross_profit_bps": 0.0, "gross_loss_bps": 0.0, "net_bps": net_bps,
        "profit_factor": None, "avg_win_bps": 0.0, "avg_loss_bps": 0.0,
        "largest_win_bps": 0.0, "largest_loss_bps": 0.0, "by_reason": {},
    }


def test_zero_trades_is_neutral_not_win(monkeypatch):
    captured = _capture(monkeypatch)
    monkeypatch.setattr(SR, "build_metrics", lambda day: _metrics(0))

    SR.send("2026-08-26", equity=99997.16, balance=100025.21)

    assert "PHIÊN LÃI" not in captured["html"]
    assert "PHIÊN KHÔNG GIAO DỊCH" in captured["html"]
    assert "Phiên lãi" not in captured["subject"]
    assert "không giao dịch" in captured["subject"].lower()


def test_zero_trades_neutral_in_text_body_too(monkeypatch):
    captured = _capture(monkeypatch)
    monkeypatch.setattr(SR, "build_metrics", lambda day: _metrics(0))

    SR.send("2026-08-26")

    assert "PHIÊN LÃI" not in captured["text"]
    assert "PHIÊN KHÔNG GIAO DỊCH" in captured["text"]


def test_real_win_session_still_labeled_win(monkeypatch):
    """Đối chứng: có lệnh đóng và net_bps dương vẫn phải ra đúng nhãn LÃI cũ."""
    captured = _capture(monkeypatch)
    monkeypatch.setattr(SR, "build_metrics", lambda day: _metrics(3, net_bps=12.5))

    SR.send("2026-08-26")

    assert "PHIÊN LÃI" in captured["html"]
    assert "PHIÊN KHÔNG GIAO DỊCH" not in captured["html"]


def test_real_loss_session_still_labeled_loss(monkeypatch):
    captured = _capture(monkeypatch)
    monkeypatch.setattr(SR, "build_metrics", lambda day: _metrics(2, net_bps=-4.0))

    SR.send("2026-08-26")

    assert "PHIÊN LỖ" in captured["html"]
    assert "PHIÊN KHÔNG GIAO DỊCH" not in captured["html"]
