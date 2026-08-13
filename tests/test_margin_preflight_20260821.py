"""Lệnh không vừa ký quỹ phải bị BỎ QUA trước khi gửi, không để broker từ chối.

SỰ CỐ 17:30 NGÀY 21/08/2026
===========================
    17:30:24  BROKER_REJECTED (broker từ chối retcode 10019)   ×6
    17:37:26  [CIRCUIT BREAKER OPEN] retcode=10019

`10019` là NO_MONEY, và nó nằm trong `FATAL_RETCODES`, nên một lệnh không vừa ký
quỹ MỞ CẦU CHÌ và chặn nốt những lệnh còn lại trong cùng lượt — đúng hình dạng
sự cố `10014` đã sửa cùng ngày.

Đo lúc 17:45 trên chính tài khoản: notional gộp ~$571.000 = 5,7× equity ở đòn bẩy
1:15, tức cần ~38% equity làm ký quỹ. Kế hoạch lệnh tính lot từ chính sách đòn
bẩy mà KHÔNG hỏi broker còn bao nhiêu ký quỹ tự do. Khi danh mục đã đầy thì phần
còn lại của kế hoạch âm thầm rụng — và danh mục THẬT khác danh mục ĐỊNH, với việc
chân nào lọt được quyết định bởi THỨ TỰ GỬI chứ không bởi chiến lược.
"""
from __future__ import annotations

from types import SimpleNamespace

from src.python.execution import order_router as OR


class _MT5:
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1

    def __init__(self, need, free):
        self._need, self._free = need, free

    def order_calc_margin(self, type_, symbol, volume, price):
        return self._need

    def account_info(self):
        return SimpleNamespace(margin_free=self._free)


def _req():
    return {"type": 0, "symbol": "AUDCAD", "volume": 0.5, "price": 0.9}


def test_enough_margin_sends() -> None:
    assert OR._margin_shortfall(_MT5(1000.0, 50_000.0), _req(), "OPEN") == ""


def test_not_enough_margin_is_skipped_with_a_readable_reason() -> None:
    reason = OR._margin_shortfall(_MT5(40_000.0, 10_000.0), _req(), "OPEN")
    assert "ký quỹ không đủ" in reason
    assert "40,000" in reason and "10,000" in reason


def test_buffer_is_applied_not_just_raw_need() -> None:
    """Vừa khít 100% ký quỹ tự do vẫn phải từ chối.

    Gửi tới sát 100% là tự đặt mình một tick nữa là Margin Call — và ở tài khoản
    này thì Margin Call nghĩa là broker tự đóng lệnh, tức mất quyền kiểm soát
    điểm thoát.
    """
    assert OR._margin_shortfall(_MT5(10_000.0, 10_500.0), _req(), "OPEN") != ""
    assert OR._margin_shortfall(_MT5(10_000.0, 13_000.0), _req(), "OPEN") == ""


def test_risk_reducing_orders_are_never_blocked() -> None:
    """Lệnh GIẢM phơi nhiễm KHÔNG bao giờ bị chặn vì thiếu ký quỹ.

    Đóng bớt luôn TRẢ LẠI ký quỹ. Chặn đường thoát vì thiếu ký quỹ chính là cái
    vòng xoáy cần tránh nhất: hết ký quỹ -> không đóng được -> càng hết ký quỹ.
    """
    broke = _MT5(99_999.0, 1.0)
    for action in OR._RISK_REDUCING:
        assert OR._margin_shortfall(broke, _req(), action) == "", action


def test_fails_soft_towards_sending() -> None:
    """Không tính được thì CHO GỬI — đoán sai theo hướng chặn làm hệ đứng im."""
    class _Broken:
        def order_calc_margin(self, *a):
            raise RuntimeError("khong tinh duoc")

        def account_info(self):
            return None

    assert OR._margin_shortfall(_Broken(), _req(), "OPEN") == ""

    class _NoneMargin:
        def order_calc_margin(self, *a):
            return None

        def account_info(self):
            return SimpleNamespace(margin_free=0.0)

    assert OR._margin_shortfall(_NoneMargin(), _req(), "OPEN") == ""
