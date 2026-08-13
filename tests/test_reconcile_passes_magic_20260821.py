"""Nơi GỌI `reconcile()` phải truyền `own_magic_base`, và không được fail-open.

FOREX 0 LỆNH TRONG 2 NGÀY — NGUYÊN NHÂN
=======================================
Mọi chu kỳ từ 14:08 tới 20:32 ngày 21/08/2026 đều in:

    KHÔNG GỬI LỆNH NÀO — CHẶN: đối soát khởi động CHƯA xong

trong khi cùng ngày lúc 18:29:05 đối soát báo "Hoàn tất ... entries_allowed=True".
Hai câu đó không mâu thuẫn: `entries_allowed` là cờ khác, còn cổng đọc
`reconciliation_done = rec.ok`, và `rec.ok` False vì 44 vị thế broker đối chiếu
với sổ 2 chân cho ra 42 mồ côi.

`reconcile()` đã có `own_magic_base` từ bản vá sự cố 22:08 ngày 20/08 — nhưng CẢ
HAI nơi gọi (`engine.py`, `order_plan.py`) chưa bao giờ truyền nó, nên nhận diện
theo magic bị vô hiệu và vị thế của chân xếp hạng vĩnh viễn là mồ côi.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITES = [
    ROOT / "src" / "python" / "core" / "engine.py",
    ROOT / "src" / "python" / "execution" / "order_plan.py",
]


def _reconcile_calls(text: str) -> list[str]:
    return [text[m.start(): m.start() + 200]
            for m in re.finditer(r"\.reconcile\(", text)]


def test_every_call_site_passes_own_magic_base():
    for path in SITES:
        for call in _reconcile_calls(path.read_text(encoding="utf-8")):
            assert "own_magic_base" in call, (
                f"{path.name}: reconcile() thiếu own_magic_base — mọi vị thế của "
                f"chân xếp hạng thành mồ côi và cổng khoá vĩnh viễn"
            )


def test_no_call_site_fails_open_on_positions_get():
    """`positions_get() or []` ở đây MỞ cổng đúng lúc không đọc được tài khoản.

    None thành [] nghĩa là sổ tự xoá mọi chân (`auto_close_missing`) và mọi mồ côi
    biến mất, nên `rec.ok` thành True.
    """
    for path in SITES:
        text = path.read_text(encoding="utf-8")
        assert "positions_get() or []" not in text, (
            f"{path.name}: fail-open trên positions_get()"
        )


def test_none_positions_keeps_the_gate_closed():
    text = (ROOT / "src" / "python" / "execution" / "order_plan.py").read_text(
        encoding="utf-8")
    i = text.index("raw = mt5.positions_get()")
    block = text[i: i + 600]
    assert "if raw is None" in block
    assert "reconciliation_done = False" in block, (
        "không đọc được vị thế thì cổng phải ĐÓNG, không phải để None rồi suy tiếp"
    )


def test_plan_still_knows_held_sides_when_reconcile_is_skipped():
    """Bỏ qua đối soát không được làm `positions` mất đầu vào."""
    text = (ROOT / "src" / "python" / "execution" / "order_plan.py").read_text(
        encoding="utf-8")
    i = text.index("raw = mt5.positions_get()")
    block = text[i: i + 1400]
    j = block.index("positions = book.sides()")
    guard = block[:j]
    assert "if rec is not None:" in guard, (
        "phần dùng rec phải được canh riêng, không bọc cả khối"
    )


# ─────────────────────────────────────────── cân lot theo broker
import pytest

from src.python.execution.position_book import PositionBook


def _book(tmp_path):
    b = PositionBook(path=tmp_path / "book.json")
    return b


def test_partial_close_outside_the_system_does_not_lock_the_portfolio(tmp_path):
    """0.19 lot lệch trên MỘT công cụ đã khoá toàn bộ 27 công cụ.

    Sổ ghi NZDCAD −1.0, broker giữ −0.81 (đóng một phần ngoài hệ).
    `ReconcileResult.ok` đòi `lot_mismatch` rỗng, nên cổng chặn mọi lệnh mới liên
    tục từ 14:08 tới 21:00 ngày 21/08/2026.
    """
    book = _book(tmp_path)
    book.open(leg="zb_nzdcad_h1", symbol="NZDCAD", side="SELL", lots=1.0,
              entry_bar_utc="2026-08-20T00:00:00+00:00", entry_price=0.8,
              timeframe="H1")

    class P:
        symbol, volume, type, magic = "NZDCAD", 0.81, 1, 5100001

    rec = book.reconcile([P()], own_magic_base=5100000)

    assert rec.lot_mismatch == {}, "lệch lot không được khoá cả danh mục"
    assert "NZDCAD" in rec.healed_lots
    assert rec.ok is True
    assert abs(book.symbol_lots()["NZDCAD"] - (-0.81)) < 0.011


def test_healed_lots_are_persisted(tmp_path):
    """Cân lot chỉ trong RAM thì restart là quay lại lệch — họ lỗi cũ của dự án."""
    path = tmp_path / "book.json"
    book = PositionBook(path=path)
    book.open(leg="zb_nzdcad_h1", symbol="NZDCAD", side="SELL", lots=1.0,
              entry_bar_utc="2026-08-20T00:00:00+00:00", entry_price=0.8,
              timeframe="H1")

    class P:
        symbol, volume, type, magic = "NZDCAD", 0.81, 1, 5100001

    book.reconcile([P()], own_magic_base=5100000)

    again = PositionBook(path=path)
    assert abs(again.symbol_lots()["NZDCAD"] - (-0.81)) < 0.011


def test_opposite_direction_is_not_healed_away(tmp_path):
    """Sổ và broker ngược chiều là bất thường THẬT — phải để cổng fail-closed."""
    book = _book(tmp_path)
    book.open(leg="zb_nzdcad_h1", symbol="NZDCAD", side="SELL", lots=1.0,
              entry_bar_utc="2026-08-20T00:00:00+00:00", entry_price=0.8,
              timeframe="H1")

    class P:
        symbol, volume, type, magic = "NZDCAD", 0.81, 0, 5100001  # type 0 = MUA

    rec = book.reconcile([P()], own_magic_base=5100000)
    assert rec.healed_lots == {}
    assert rec.ok is False, "ngược chiều thì KHÔNG được tự cân rồi mở cổng"
