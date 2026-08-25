"""`order_plan` với chiến lược có SL CỨNG. Kiểm HỢP ĐỒNG giữa chiến lược và thực thi.

Bốn điều bắt buộc, và mỗi điều là một cách hệ có thể mở một vị thế mà không ai biết
nó rủi ro bao nhiêu:

  1. không có SL   -> KHÔNG mở vị thế mới (fail-closed), nhưng đường THOÁT vẫn mở
  2. SL chiến lược -> đi vào `stop_price`; cầu chì `disaster_stop` xuống `fuse_price`
  3. cỡ lệnh       -> đến từ khoảng cách SL, KHÔNG từ tỷ trọng × đòn bẩy
  4. trần rủi ro   -> tổng rủi ro mở vượt trần thì BỎ HẾT mục tiêu mở
"""
from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
import pytest

from src.python.execution import order_plan as OP

EQUITY = 100_000.0
PRICES = {"EURUSD": 1.0850, "GBPUSD": 1.2700, "USDJPY": 150.20}


# ═══════════════════════════════════════════════════════════════ khung giả
class _Decision:
    """Bản tối giản của `SweepDecision` — chỉ những trường tầng thực thi đọc."""

    def __init__(self, instrument: str, side: int, entry: float, stop: float,
                 tp: float, enter: bool = True) -> None:
        self.instrument = instrument
        self.side = side
        self.entry_px = entry
        self.stop_px = stop
        self.tp_px = tp
        self.sl_pips = abs(entry - stop) * (100.0 if "JPY" in instrument else 10_000.0)
        self.rr = 3.0
        self.state = "ENTRY" if enter else "WINDOW_CLOSED"
        self._enter = enter

    @property
    def enter(self) -> bool:
        return self._enter


class _Targets:
    asof = "2026-08-25"
    regime = "NORMAL"

    def __init__(self, decisions: Dict[str, _Decision]) -> None:
        self.single_decisions = {f"asia_sweep:{k}": v for k, v in decisions.items()}
        self.pair_weights = pd.Series(dtype=float)
        self.cross_decisions: List[object] = []
        self.rank_weights: Dict[str, pd.Series] = {}
        self.leg_scale = {"asia_sweep": 1.0}
        self.notes: List[str] = []

    @property
    def entries(self) -> Dict[str, object]:
        return {d.instrument: d for d in self.single_decisions.values()
                if getattr(d, "enter", False)}


def _plan(targets, **kw) -> OP.OrderPlan:
    """Kế hoạch với mọi cổng MỞ — test này đo phần SIZING, không đo cổng an toàn."""
    base = dict(equity_usd=EQUITY, prices=PRICES, mt5=None,
                reconciliation_done=True, trading_enabled=True,
                ftmo_entries_allowed=True, day_start_balance=EQUITY)
    base.update(kw)
    return OP.build(targets, **base)


def _sell_eur() -> _Decision:
    return _Decision("EURUSD", -1, 1.08500, 1.08800, 1.07900)


# ═══════════════════════════════════════════════════════════════ 1. FAIL-CLOSED
def test_no_stop_targets_means_no_new_positions(monkeypatch):
    """Chiến lược không khai được SL = không biết rủi ro = KHÔNG mở vị thế."""
    from src.python.strategies import portfolio as PF

    monkeypatch.setattr(PF, "stop_targets", lambda _t: {})
    plan = _plan(_Targets({"EURUSD": _sell_eur()}))
    assert all(a.action in ("HOLD", "CLOSE", "REDUCE") for a in plan.actions), \
        [a.explain() for a in plan.actions]


def test_stop_targets_raising_does_not_crash_the_plan(monkeypatch):
    """Đọc SL lỗi thì ghi chú và bỏ lượt — không được ném ra ngoài."""
    from src.python.strategies import portfolio as PF

    def boom(_t):
        raise RuntimeError("giả lập lỗi đọc SL")

    monkeypatch.setattr(PF, "stop_targets", boom)
    plan = _plan(_Targets({"EURUSD": _sell_eur()}))
    assert any("stop_targets" in n for n in plan.notes), plan.notes
    assert not [a for a in plan.actions if a.action == "OPEN"]


def test_invalid_stop_price_blocks_the_open(monkeypatch):
    from src.python.strategies import portfolio as PF

    monkeypatch.setattr(PF, "stop_targets", lambda _t: {
        "EURUSD": {"side": -1.0, "entry": 1.0850, "stop": float("nan"),
                   "tp": 1.0790}})
    plan = _plan(_Targets({"EURUSD": _sell_eur()}))
    opens = [a for a in plan.actions if a.action == "OPEN"]
    assert not opens, [a.explain() for a in opens]


def test_portfolio_without_stop_targets_raises(monkeypatch):
    """Không có `stop_targets()` thì NỔ — không có nhánh sizing dự phòng nào."""
    from src.python.strategies import portfolio as PF

    monkeypatch.delattr(PF, "stop_targets")
    with pytest.raises(AttributeError, match="stop_targets"):
        _plan(_Targets({"EURUSD": _sell_eur()}))


# ═══════════════════════════════════════════════════════ 2. SL vs CẦU CHÌ
def test_strategy_stop_goes_to_stop_price_and_fuse_stays_separate():
    """SL chiến lược cai trị `stop_price`; cầu chì giữ chỗ riêng ở `fuse_price`.

    Lẫn hai thứ là chuyện nghiêm trọng: cầu chì 8xATR trên EURUSD là ~80 pip, tức
    gần BA LẦN rủi ro dự kiến của một lệnh.
    """
    d = _sell_eur()
    plan = _plan(_Targets({"EURUSD": d}))
    act = next(a for a in plan.actions if a.symbol == "EURUSD")
    assert act.stop_price == pytest.approx(d.stop_px), act.explain()
    assert act.take_profit == pytest.approx(d.tp_px)
    if act.fuse_price is not None:
        assert abs(act.fuse_price - d.entry_px) > abs(act.stop_price - d.entry_px), \
            "cầu chì phải XA hơn SL chiến lược"


# ═══════════════════════════════════════════════════════════════ 3. CỠ LỆNH
def test_lots_come_from_stop_distance_not_from_leverage():
    """SL rộng gấp đôi thì lot phải NHỎ đi khoảng một nửa — dấu hiệu sizing theo R."""
    tight = _plan(_Targets({"EURUSD": _Decision(
        "EURUSD", -1, 1.08500, 1.08700, 1.07900)}))
    wide = _plan(_Targets({"EURUSD": _Decision(
        "EURUSD", -1, 1.08500, 1.08900, 1.07900)}))
    a = next(x for x in tight.actions if x.symbol == "EURUSD")
    b = next(x for x in wide.actions if x.symbol == "EURUSD")
    assert a.target_lots != 0 and b.target_lots != 0
    assert abs(b.target_lots) < abs(a.target_lots)
    assert abs(b.target_lots) == pytest.approx(abs(a.target_lots) / 2.0, rel=0.06)


def test_risk_usd_is_reported_on_every_open_action():
    """Mỗi lệnh mở phải mang theo số tiền RỦI RO — nếu không thì bản ghi thiếu."""
    plan = _plan(_Targets({"EURUSD": _sell_eur()}))
    act = next(a for a in plan.actions if a.symbol == "EURUSD")
    assert act.risk_usd > 0, act.explain()
    from src.python.strategies import registry as REG
    want = EQUITY * float(REG.PORTFOLIO["risk_pct_per_trade"]) / 100.0
    assert act.risk_usd == pytest.approx(want, rel=0.05)


def test_leverage_is_a_consequence_not_an_input():
    """Đổi đòn bẩy KHÔNG được đổi lot — đòn bẩy nay là hệ quả của cỡ lệnh."""
    t = _Targets({"EURUSD": _sell_eur()})
    lo = _plan(t, leverage_override=1.0)
    hi = _plan(t, leverage_override=5.0)
    a = next(x for x in lo.actions if x.symbol == "EURUSD")
    b = next(x for x in hi.actions if x.symbol == "EURUSD")
    assert a.target_lots == pytest.approx(b.target_lots)


# ═══════════════════════════════════════════════════════════════ 4. TRẦN
def test_total_open_risk_is_reported():
    plan = _plan(_Targets({
        "EURUSD": _sell_eur(),
        "GBPUSD": _Decision("GBPUSD", +1, 1.27000, 1.26600, 1.27700),
        "USDJPY": _Decision("USDJPY", -1, 150.200, 150.500, 149.600)}))
    assert any("rủi ro MỞ" in n for n in plan.notes), plan.notes


def test_exceeding_the_daily_risk_cap_drops_every_open(monkeypatch):
    """Tổng rủi ro mở vượt trần: BỎ HẾT mục tiêu mở, không phải cắt bớt một cái."""
    monkeypatch.setattr(OP, "_DAILY_RISK_CAP_PCT", 0.10)
    plan = _plan(_Targets({
        "EURUSD": _sell_eur(),
        "GBPUSD": _Decision("GBPUSD", +1, 1.27000, 1.26600, 1.27700)}))
    assert any("vượt trần nội bộ" in n for n in plan.notes), plan.notes
    assert not [a for a in plan.actions if a.action == "OPEN"]


def test_daily_cap_stays_below_the_ftmo_daily_limit():
    """Trần nội bộ PHẢI nằm dưới mốc ngày 5,00% của FTMO — có biên, không sát."""
    assert 0.0 < OP._DAILY_RISK_CAP_PCT <= 4.0
    from src.python.core.infra import ftmo
    limit = getattr(ftmo, "MAX_DAILY_LOSS_PCT", 5.0)
    assert OP._DAILY_RISK_CAP_PCT < limit


def test_registry_risk_pct_is_read_not_guessed(monkeypatch):
    """Thiếu khai báo rủi ro ở SSOT thì NỔ, không nhận mặc định."""
    from src.python.strategies import registry as REG

    monkeypatch.setitem(REG.PORTFOLIO, "risk_pct_per_trade", None)
    with pytest.raises(KeyError, match="risk_pct_per_trade"):
        OP._registry_risk_pct()


# ═══════════════════════════════════ 5. TẦNG PHỐI HỢP DANH MỤC
def test_currency_concentration_cap_drops_the_smallest_trade(monkeypatch):
    """Ba cặp cùng chân USD là MỘT cược gấp ba — trần theo ĐỒNG TIỀN phải thấy điều đó.

    Trần theo CÔNG CỤ (`_DAILY_RISK_CAP_PCT`) cộng theo công cụ nên nó KHÔNG thấy chỗ
    tập trung này. Hai cổng đo hai đại lượng khác nhau, và cần cả hai.
    """
    monkeypatch.setattr(OP, "_CURRENCY_RISK_CAP_PCT", 0.80)
    plan = _plan(_Targets({
        "EURUSD": _sell_eur(),                                       # rủi ro ~0,6%
        "GBPUSD": _Decision("GBPUSD", +1, 1.27000, 1.26600, 1.27700),
        "USDJPY": _Decision("USDJPY", -1, 150.200, 150.500, 149.600)}))
    assert any("dồn vào" in n for n in plan.notes), plan.notes
    opened = [a.symbol for a in plan.actions if a.action == "OPEN"]
    assert len(opened) < 3, opened


def test_currency_cap_leaves_a_single_trade_alone():
    """Một lệnh duy nhất KHÔNG được coi là tập trung — nếu không thì cổng chặn tất cả."""
    plan = _plan(_Targets({"EURUSD": _sell_eur()}))
    assert not any("dồn vào" in n for n in plan.notes), plan.notes
    assert [a for a in plan.actions if a.action == "OPEN"]


def test_currency_cap_stays_below_the_daily_cap():
    """Trần đồng tiền phải CHẶT HƠN trần ngày — nếu ngược thì nó không bao giờ kích hoạt."""
    assert 0.0 < OP._CURRENCY_RISK_CAP_PCT <= OP._DAILY_RISK_CAP_PCT


# ═══════════════════════════════════ 6. TP TỚI ĐƯỢC BROKER
def test_router_sends_the_declared_take_profit():
    """`tp` gửi broker phải bằng đúng mức chiến lược khai."""
    from src.python.execution.order_router import OrderRouter

    act = OP.OrderAction(
        symbol="EURUSD", action="OPEN", side="SELL", lots=1.0, current_lots=0.0,
        target_lots=-1.0, target_weight=-1.0, stop_price=1.0880,
        take_profit=1.0790)
    assert OrderRouter._pick_take_profit(act) == pytest.approx(1.0790)


def test_router_sends_no_take_profit_when_strategy_declares_none():
    from src.python.execution.order_router import OrderRouter

    act = OP.OrderAction(
        symbol="EURUSD", action="OPEN", side="SELL", lots=1.0, current_lots=0.0,
        target_lots=-1.0, target_weight=-1.0, stop_price=1.0880)
    assert OrderRouter._pick_take_profit(act) is None


def test_stop_and_target_ride_along_with_the_opening_order():
    """`sl` và `tp` phải nằm TRONG chính request mở lệnh, không đặt sau.

    Đặt sau là để lại một khoảng thời gian vị thế sống mà KHÔNG có dừng lỗ — và nếu
    lệnh đặt-sau thất bại thì khoảng đó là vĩnh viễn.
    """
    import inspect

    from src.python.execution.order_router import OrderRouter

    src = inspect.getsource(OrderRouter._send_one)
    i_req = src.index('req["sl"]')
    i_tp = src.index('req["tp"]')
    i_send = src.index("order_send(req)")
    assert i_req < i_send and i_tp < i_send, (
        "sl/tp được gán SAU khi gửi lệnh — vị thế sẽ có lúc không được bảo vệ")
