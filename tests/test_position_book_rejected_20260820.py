"""Lệnh bị broker TỪ CHỐI không được để lại vị thế MA trong sổ.

SỰ CỐ 20/08/2026 — SỔ GHI Ý ĐỊNH, KHÔNG GHI KẾT QUẢ
====================================================
19:14:52, `AutoTrading` bị tắt ở terminal. Cả 27 lệnh bị từ chối:

    Order 61878f1b828e5419 ... AUDCAD BUY 0.48 lots
    [CIRCUIT BREAKER OPEN] retcode=10027 (AutoTrading disabled by client)

Broker có ĐÚNG 0 vị thế. Nhưng `data/live/position_book.json` ngay sau đó:

    zb_audcad_h1       AUDCAD BUY lots=0.16 ticket=0
    zb_audcad_m30      AUDCAD BUY lots=0.16 ticket=0
    streak_audcad_m30  AUDCAD BUY lots=0.16 ticket=0

Ba chân "đang giữ lệnh" cho một vị thế chưa từng tồn tại. Hậu quả:

  * `open()` từ chối mở lại chân đã có trong sổ → chân đó KHÔNG THỂ thử lại
    chừng nào bóng ma còn nằm đó.
  * `sides()` báo chân đang giữ lệnh → hai chân ngược chiều tưởng đã triệt tiêu.
  * Đồng hồ time-stop chạy cho một vị thế không tồn tại.

`reconcile()` chu kỳ sau dọn được, nhưng giữa hai thời điểm đó hệ ra quyết định
trên một thế giới không có thật — và với sổ vị thế thì "sai rồi tự sửa" không
phải thiết kế chấp nhận được.
"""
from __future__ import annotations

import pytest

from src.python.execution import position_book as PB


class _Decision:
    """Bản tối giản của `EntryDecision` — `_side_of` chỉ đọc `.action`."""

    def __init__(self, action: str) -> None:
        self.action = action


class _Targets:
    """Bản tối giản của `targets` — chỉ những trường `sync_from_targets` đọc."""

    asof = "2026-08-20T19:14:00"

    def __init__(self, decisions):
        self.single_decisions = decisions


def _buy(legs):
    return {leg: _Decision("BUY") for leg in legs}


def _legs_for_symbol(symbol: str):
    """Các chân đơn trỏ vào `symbol`, lấy từ SSOT thay vì viết tay."""
    from src.python.strategies import portfolio as PF
    from src.python.strategies import registry as REG

    out = []
    for leg, name in PF.SINGLE_LEGS.items():
        spec = REG.by_name(name)
        if spec is not None and spec.symbols and spec.symbols[0] == symbol:
            out.append(leg)
    return out


def _book(tmp_path):
    book = PB.PositionBook(path=tmp_path / "position_book.json") \
        if "path" in PB.PositionBook.__init__.__code__.co_varnames \
        else PB.PositionBook()
    return book


def test_rejected_symbol_leaves_book_untouched(tmp_path, monkeypatch):
    """Công cụ nằm trong `failed_symbols` thì KHÔNG chân nào của nó được mở sổ."""
    monkeypatch.setattr(PB, "_login_now", lambda: "test", raising=False)
    book = _book(tmp_path)
    legs = _legs_for_symbol("AUDCAD")
    assert legs, "phải có ít nhất một chân AUDCAD trong registry"

    targets = _Targets(_buy(legs))
    changed = PB.sync_from_targets(
        book, targets, {"AUDCAD": 0.9012},
        lots_by_symbol={"AUDCAD": 0.48},
        failed_symbols={"AUDCAD"})

    assert book.symbol_lots().get("AUDCAD", 0.0) == 0.0
    for leg in legs:
        assert "TỪ CHỐI" in changed.get(leg, ""), changed


def test_successful_symbol_still_recorded(tmp_path, monkeypatch):
    """Không bị từ chối thì sổ vẫn phải ghi — nếu không, time-stop chết trở lại.

    Bản vá này chỉ được phép chặn ĐÚNG nhánh lệnh hỏng. Chặn quá tay thì sổ rỗng
    vĩnh viễn, và đó chính là lỗi đã sửa ngày 15/08/2026.
    """
    monkeypatch.setattr(PB, "_login_now", lambda: "test", raising=False)
    book = _book(tmp_path)
    legs = _legs_for_symbol("AUDCAD")
    targets = _Targets(_buy(legs))

    PB.sync_from_targets(book, targets, {"AUDCAD": 0.9012},
                         lots_by_symbol={"AUDCAD": 0.48},
                         failed_symbols=set())

    assert book.symbol_lots().get("AUDCAD", 0.0) == pytest.approx(0.48, abs=0.02)


def test_failed_symbols_defaults_to_none(tmp_path, monkeypatch):
    """Bên gọi cũ (không truyền `failed_symbols`) phải giữ nguyên hành vi."""
    monkeypatch.setattr(PB, "_login_now", lambda: "test", raising=False)
    book = _book(tmp_path)
    legs = _legs_for_symbol("AUDCAD")
    PB.sync_from_targets(book, _Targets(_buy(legs)),
                         {"AUDCAD": 0.9012}, lots_by_symbol={"AUDCAD": 0.48})
    assert book.symbol_lots().get("AUDCAD", 0.0) > 0
