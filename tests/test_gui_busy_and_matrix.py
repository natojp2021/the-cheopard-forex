# -*- coding: utf-8 -*-
"""Hiệu ứng "ĐANG CHẠY…" và MA TRẬN CHIẾN LƯỢC — hai thứ nói cho người vận hành
biết hệ đang làm gì.

MA TRẬN TỪNG CHẾT LẶNG LẼ
==========================
`get_decision_matrix_rows` đọc `state["portfolio"]` như một DANH SÁCH các hàng có
khoá `name`, trong khi `engine._read_portfolio` ghi vào đó một TỪ ĐIỂN chỉ số danh
mục. Lặp một từ điển cho ra các KHOÁ, nên `r["name"]` ném `TypeError`.

Lỗi không lộ ra vì hai lý do cộng lại: lúc khởi động `portfolio` là `{}` và `{} or []`
cho `[]` (không lặp gì, bảng vẽ đúng), còn khối gọi thì bọc trong `try/except
Exception` nuốt trọn. Hậu quả: sau lượt backtest đầu tiên (~2 phút sau khi mở bảng),
ma trận ĐỨNG IM VĨNH VIỄN ở giá trị lúc khởi động, không một dòng lỗi.

Ba test đầu ghim đúng ba trạng thái mà bảng phải đi qua.
"""
from __future__ import annotations

import pytest

from src.python.core import gui_command_center as G


def _state(**kw):
    base = {"portfolio": {}, "positions_list": [], "market_closed": False,
            "equity": 100_000.0}
    base.update(kw)
    return base


def test_matrix_survives_portfolio_metrics_dict():
    """Sau backtest, `state["portfolio"]` là TỪ ĐIỂN chỉ số — bảng vẫn phải vẽ.

    Đây là hình dạng THẬT mà `engine._read_portfolio` ghi ra. Bản cũ ném TypeError
    ở đúng hình dạng này.
    """
    metrics = {"name": "FX", "stage": "FORWARD_TEST", "n_strategies": 27,
               "sharpe_all": 2.874, "max_dd_sd": 4.0, "worst_day_sd": -1.27}
    rows = G.get_decision_matrix_rows(_state(portfolio=metrics))
    assert len(rows) == len(G._magic_map), "thiếu chân trong bảng"
    assert all(r["decision"] for r in rows)


def test_matrix_marks_active_from_real_broker_positions():
    """"Có lệnh" phải đọc từ VỊ THẾ THẬT qua `magic`, không từ `state["portfolio"]`."""
    name, magic = next(iter(G._magic_map.items()))
    rows = G.get_decision_matrix_rows(_state(
        positions_list=[{"magic": magic, "profit": -250.0}]))
    row = next(r for r in rows if r["name"] == name)
    assert row["active"] is True
    assert row["decision"] == "ACTIVE"
    # −$250 trên equity $100.000 = −0,25%.
    assert row["r"] == "-0.25%", row["r"]

    other = next(r for r in rows if r["name"] != name)
    assert other["active"] is False and other["r"] == "—"


def test_matrix_empty_at_startup_does_not_claim_positions():
    """Lúc khởi động chưa đọc được vị thế — KHÔNG chân nào được hiện ACTIVE."""
    rows = G.get_decision_matrix_rows(_state())
    assert not any(r["active"] for r in rows)
    assert all(r["r"] == "—" for r in rows)


def test_busy_text_cycles_and_returns_to_start():
    """Chuỗi chấm phải CHẠY và phải LẶP — đứng im trông y hệt hệ đã treo."""
    seen = [G.busy_text("ĐANG CHẠY", t)
            for t in range(0, G.BUSY_TICK_EVERY * len(G._BUSY_DOTS),
                           G.BUSY_TICK_EVERY)]
    assert seen == ["ĐANG CHẠY", "ĐANG CHẠY.", "ĐANG CHẠY..",
                    "ĐANG CHẠY...", "ĐANG CHẠY...."], seen
    # Quay vòng: khung kế tiếp phải trở lại khung đầu.
    assert G.busy_text("ĐANG CHẠY", G.BUSY_TICK_EVERY * len(G._BUSY_DOTS)) == seen[0]


def test_busy_text_holds_each_frame_for_full_period():
    """Đổi khung mỗi `BUSY_TICK_EVERY` lượt, không phải mỗi lượt.

    `process_queues` chạy 100 ms một lần; đổi mỗi lượt cho ra 10 khung/giây — nhanh
    tới mức thành nhiễu chứ không đọc được.
    """
    for t in range(G.BUSY_TICK_EVERY):
        assert G.busy_text("X", t) == "X"
    assert G.busy_text("X", G.BUSY_TICK_EVERY) == "X."


def test_busy_text_empty_when_idle():
    """Không có việc nặng thì không có chữ — nhãn rỗng, không phải 'ĐANG CHẠY' câm."""
    assert G.busy_text("", 7) == ""


@pytest.mark.parametrize("key", ["busy"])
def test_engine_state_exposes_busy_key(key):
    """Giao diện đọc `state["busy"]`; đổi tên khoá ở engine là tắt hiệu ứng.

    Cùng lớp lỗi với `"mt"` vs `"mt5_connected"` — thẻ MT5 hiện DISCONNECTED suốt
    dù kết nối vẫn tốt, và không có lỗi nào để lần ra.
    """
    import inspect

    from src.python.core import engine as E

    src = inspect.getsource(E.TradingEngine.__init__)
    assert f'"{key}"' in src, f"engine không còn đặt khoá state[{key!r}]"
