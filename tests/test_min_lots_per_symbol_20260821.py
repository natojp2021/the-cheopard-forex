"""Lot tối thiểu là của TỪNG công cụ, không phải một hằng số toàn cục.

SỰ CỐ 04:28 NGÀY 21/08/2026 — MỘT CÔNG CỤ CÁ BIỆT HẠ CẢ LƯỢT GỬI
=================================================================
    [LỖI] NZDCAD  INCREASE  SELL  0.02 lot ... retcode 10014 Invalid volume
    [CIRCUIT BREAKER OPEN] FATAL NON-RETRIABLE ERROR: retcode=10014

Đo trên chính tài khoản: `NZDCAD.volume_min = 0.1`, còn 26 công cụ kia là 0,01.
`MIN_TRADE_LOTS = 0.01` là hằng số TOÀN CỤC, nên chênh lệch 0,02 lot của NZDCAD
qua được cổng nội bộ rồi bị broker từ chối — mỗi chu kỳ, đều đặn.

Hậu quả không dừng ở một lệnh: `10014` bị xếp cùng nhóm với 10019 (hết ký quỹ) và
10027 (tắt giao dịch tự động), tức nhóm "hỏng cả tài khoản", nên nó MỞ CẦU CHÌ và
chặn nốt những lệnh còn lại trong cùng lượt.

Hai tầng, hai lỗi, và cả hai đều phải sửa:
  * `order_plan.min_trade_lots` — hỏi broker thay vì dùng hằng số;
  * `circuit_breaker.ORDER_SCOPED_RETCODES` — `10014` nói "khối lượng của LỆNH
    NÀY sai", không nói "tài khoản hỏng".
"""
from __future__ import annotations

from src.python.core.broker.circuit_breaker import MT5CircuitBreaker
from src.python.execution import order_plan as OP


class _FakeInfo:
    def __init__(self, vmin: float, vstep: float):
        self.volume_min, self.volume_step, self.volume_max = vmin, vstep, 100.0
        self.digits, self.point, self.trade_stops_level = 5, 1e-5, 0
        self.trade_contract_size, self.trade_tick_size = 100000.0, 1e-5
        self.trade_tick_value, self.spread = 1.0, 1
        self.name = "X"


class _FakeMT5:
    def __init__(self, table):
        self._t = table

    def symbol_info(self, s):
        return self._t.get(s)


def test_min_trade_lots_follows_the_broker(monkeypatch) -> None:
    """NZDCAD 0,1 và AUDCAD 0,01 phải cho hai ngưỡng KHÁC nhau."""
    mt5 = _FakeMT5({"NZDCAD": _FakeInfo(0.1, 0.01),
                    "AUDCAD": _FakeInfo(0.01, 0.01)})
    assert OP.min_trade_lots("NZDCAD", mt5) == 0.1
    assert OP.min_trade_lots("AUDCAD", mt5) == 0.01


def test_step_larger_than_min_wins(monkeypatch) -> None:
    """Ngưỡng là `max(volume_min, volume_step)` — dưới bậc thì làm tròn về 0."""
    mt5 = _FakeMT5({"X": _FakeInfo(0.01, 0.5)})
    assert OP.min_trade_lots("X", mt5) == 0.5


def test_unreadable_spec_falls_back_to_old_constant() -> None:
    """Không đọc được đặc tả thì giữ hằng số cũ, không đoán cao lên.

    Đoán cao hơn sẽ âm thầm bỏ lỡ lệnh thật; đoán bằng cũ thì tệ nhất là lặp lại
    đúng lỗi đã biết, và lỗi đã biết thì nhìn thấy được.
    """
    assert OP.min_trade_lots("KHONG-CO", None) == OP.MIN_TRADE_LOTS


def test_invalid_volume_does_not_open_the_breaker() -> None:
    """`10014` từ chối MỘT lệnh, cầu chì phải giữ nguyên CLOSED."""
    cb = MT5CircuitBreaker()
    assert cb.state.value == "CLOSED"
    cb.record_failure(retcode=10014, comment="Invalid volume")
    assert cb.state.value == "CLOSED", "10014 không được hạ cả lượt gửi"


def test_account_wide_faults_still_open_the_breaker() -> None:
    """Phần KHÔNG được nới: lỗi cấp TÀI KHOẢN vẫn phải mở cầu chì.

    Đây là ranh giới của bản vá. Hết ký quỹ và tắt giao dịch tự động là hỏng ở
    cấp tài khoản — gửi tiếp chỉ sinh thêm lệnh hỏng.
    """
    for code in (10019, 10027, 10018):
        cb = MT5CircuitBreaker()
        cb.record_failure(retcode=code, comment="loi cap tai khoan")
        assert cb.state.value == "OPEN", f"retcode {code} phải mở cầu chì"


def test_invalid_volume_is_still_not_retried() -> None:
    """Vẫn KHÔNG thử lại: gửi lại đúng khối lượng sai thì vẫn sai.

    `order_router._is_fatal()` đọc `FATAL_RETCODES`, nên 10014 CỐ Ý nằm ở cả hai
    tập. Test này khoá điều đó lại để không ai "dọn" một bên đi.
    """
    from src.python.execution.order_router import _is_fatal

    assert _is_fatal(10014) is True
    assert 10014 in MT5CircuitBreaker.FATAL_RETCODES
    assert 10014 in MT5CircuitBreaker.ORDER_SCOPED_RETCODES
