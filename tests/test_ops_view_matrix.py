# -*- coding: utf-8 -*-
"""MA TRẬN CHIẾN LƯỢC — thứ nói cho người vận hành biết từng chân đang làm gì.

MA TRẬN TỪNG CHẾT LẶNG LẼ
==========================
`get_decision_matrix_rows` đọc `state["portfolio"]` như một DANH SÁCH các hàng có
khoá `name`, trong khi `engine._read_portfolio` ghi vào đó một TỪ ĐIỂN chỉ số danh
mục. Lặp một từ điển cho ra các KHOÁ, nên `r["name"]` ném `TypeError`.

Lỗi không lộ ra vì hai lý do cộng lại: lúc khởi động `portfolio` là `{}` và `{} or []`
cho `[]` (không lặp gì, bảng vẽ đúng), còn khối gọi thì bọc trong `try/except
Exception` nuốt trọn. Hậu quả: sau lượt backtest đầu tiên (~2 phút sau khi mở bảng),
ma trận ĐỨNG IM VĨNH VIỄN ở giá trị lúc khởi động, không một dòng lỗi.

CHUYỂN NGUỒN 19/08/2026: hàm này rời `gui_command_center` (đã xoá) sang
`core/ops_view.py`. Nội dung test giữ nguyên — nó kiểm LOGIC quyết định, và logic đó
không đổi khi đổi tầng trình bày. Đúng vì vậy mà nó là test có giá trị nhất trong đợt
xoá giao diện: nó chứng minh phần nghiệp vụ được cứu ra nguyên vẹn.

ĐÃ BỎ cùng đợt: bốn test của `busy_text` (hiệu ứng "ĐANG CHẠY…" với chuỗi chấm chạy).
Console không có animation, và hàm đó đã bị xoá chứ không chuyển sang — nên giữ test
lại sẽ là test cho một tính năng không tồn tại.
"""
from __future__ import annotations

import pytest

from src.python.core import ops_view as G


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
