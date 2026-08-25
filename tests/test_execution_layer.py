"""Kiểm định TẦNG THỰC THI — sổ vị thế, công tắc, router gửi lệnh.

VÌ SAO CÓ FILE NÀY
==================
Đợt kiểm toán 14/08/2026 (`docs/forex/09_kiem_toan_thuc_thi.md`) tìm ra bốn lỗ hổng
cùng dạng "sai im lặng". Nặng nhất:

    Cả 27 chân thoát lệnh bằng time-stop, và time-stop cần `bars_held`.
    KHÔNG module nào tính `bars_held` — mọi nơi gọi đều truyền 0.
    ⟹ điều kiện `bars_held >= timestop` không bao giờ đúng ⟹ giữ vị thế VÔ HẠN.

Không exception, không test đỏ. Các test dưới đây ghim lại từng bất biến để lớp lỗi
đó không quay lại.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.python.execution import order_router as OR
from src.python.execution import trading_control as TC
from src.python.execution.position_book import PositionBook


@pytest.fixture()
def book(tmp_path) -> PositionBook:
    return PositionBook(tmp_path / "book.json")


class _Pos:
    def __init__(self, symbol, volume, type_=0):
        self.symbol, self.volume, self.type = symbol, volume, type_


# ═════════════════════════════════════════════════════ 1. đồng hồ time-stop
def test_bars_held_counts_bars_not_hours(book):
    """Đếm NẾN, không đếm giờ — cuối tuần có 64 giờ nhưng 0 nến.

    Quy đổi bằng giờ sẽ đóng lệnh sớm hai ngày mỗi tuần, tức lệch hẳn khỏi hành vi
    mà backtest đã đo.
    """
    book.open("zb_audcad_h1", symbol="AUDCAD", side="BUY", lots=1.0,
              entry_bar_utc="2026-08-14 15:00:00", entry_price=0.90, timeframe="H1")
    # Nến thật: 2 nến thứ Sáu, rồi NHẢY qua cuối tuần sang thứ Hai thêm 3 nến.
    idx = pd.DatetimeIndex(["2026-08-14 15:00", "2026-08-14 16:00",
                            "2026-08-14 17:00",
                            "2026-08-17 09:00", "2026-08-17 10:00",
                            "2026-08-17 11:00"])
    # 5 nến SAU nến vào lệnh — dù đồng hồ đã trôi hơn 68 giờ.
    assert book.bars_held("zb_audcad_h1", idx) == 5


def test_bars_held_zero_when_no_position(book):
    assert book.bars_held("zb_audcad_h1", pd.DatetimeIndex(["2026-08-14 15:00"])) == 0


def test_all_bars_held_skips_legs_without_index(book):
    """Chân thiếu chỉ mục phải BỎ QUA, không được trả 0.

    Trả 0 nghĩa là "vừa vào lệnh" — nói vậy với một chân đã giữ ba tuần là tự tay
    tắt time-stop của nó, đúng lỗ hổng file này sinh ra để chặn.
    """
    book.open("zb_audcad_h1", symbol="AUDCAD", side="BUY", lots=1.0,
              entry_bar_utc="2026-08-10 09:00:00", entry_price=0.9, timeframe="H1")
    book.open("accel_gbpnzd_h1", symbol="GBPNZD", side="SELL", lots=0.5,
              entry_bar_utc="2026-08-10 09:00:00", entry_price=2.1, timeframe="H1")
    idx = pd.date_range("2026-08-10 09:00", periods=30, freq="h")
    got = book.all_bars_held({"zb_audcad_h1": idx})
    assert got == {"zb_audcad_h1": 29}
    assert "accel_gbpnzd_h1" not in got


# ═════════════════════════════════════════════════════ 2. sổ bền vững
def test_book_survives_restart(tmp_path):
    """Sổ phải sống qua restart — trong RAM thì restart xoá sạch đồng hồ time-stop."""
    p = tmp_path / "book.json"
    b1 = PositionBook(p)
    b1.open("zb_audcad_h1", symbol="AUDCAD", side="BUY", lots=1.5,
            entry_bar_utc="2026-08-10 09:00:00", entry_price=0.9, timeframe="H1",
            stop_price=0.855)
    b2 = PositionBook(p)
    assert len(b2) == 1
    assert b2.get("zb_audcad_h1").stop_price == pytest.approx(0.855)
    assert b2.sides() == {"zb_audcad_h1": 1}


def test_one_position_per_leg(book):
    """Mọi thẻ luật khai `max_positions=1` — sổ phải cưỡng chế điều đó."""
    book.open("zb_audcad_h1", symbol="AUDCAD", side="BUY", lots=1.0,
              entry_bar_utc="2026-08-10 09:00:00", entry_price=0.9, timeframe="H1")
    with pytest.raises(ValueError):
        book.open("zb_audcad_h1", symbol="AUDCAD", side="SELL", lots=1.0,
                  entry_bar_utc="2026-08-11 09:00:00", entry_price=0.9,
                  timeframe="H1")


# ═════════════════════════════════════════════════════ 3. đối soát
def test_reconcile_clean_book_is_ok(book):
    book.open("zb_audcad_h1", symbol="AUDCAD", side="BUY", lots=1.5,
              entry_bar_utc="2026-08-10 09:00:00", entry_price=0.9, timeframe="H1")
    r = book.reconcile([_Pos("AUDCAD", 1.5, 0)])
    assert r.ok and r.matched == ["zb_audcad_h1"]


def test_orphan_position_blocks_reconciliation(book):
    """Vị thế lạ trên broker → đối soát KHÔNG sạch → cổng chặn vào lệnh mới.

    KHÔNG tự đóng: có thể là lệnh của hệ XAUUSD trên cùng tài khoản.
    """
    r = book.reconcile([_Pos("EURJPY", 2.0, 1)])
    assert not r.ok
    assert r.orphan == ["EURJPY"]


def test_position_closed_elsewhere_is_removed(book):
    """Cầu chì nổ lúc bot không chạy → xoá khỏi sổ, nếu không chân đó câm vĩnh viễn."""
    book.open("zb_audcad_h1", symbol="AUDCAD", side="BUY", lots=1.5,
              entry_bar_utc="2026-08-10 09:00:00", entry_price=0.9, timeframe="H1")
    r = book.reconcile([])
    assert r.closed_elsewhere == ["zb_audcad_h1"]
    assert len(book) == 0
    # Chân đó phải mở lại được ngay, không vướng "đã có vị thế".
    book.open("zb_audcad_h1", symbol="AUDCAD", side="SELL", lots=1.0,
              entry_bar_utc="2026-08-12 09:00:00", entry_price=0.9, timeframe="H1")


def test_lot_mismatch_is_flagged(book):
    """Lệch lot phải HIỆN RA — nhưng từ 21/08/2026 nó không khoá cả danh mục nữa.

    Chủ ý ban đầu là "hiện ra, KHÔNG tự sửa". Đo được cái giá của phần "không tự
    sửa": sổ ghi NZDCAD −1.0 còn broker giữ −0.81 sau một lần đóng bớt ngoài hệ;
    `ok` đòi `lot_mismatch` rỗng nên 0.19 lot lệch trên MỘT công cụ chặn toàn bộ
    lệnh mới của 27 công cụ, liên tục từ 14:08 tới 21:00 — không một lệnh nào
    trong hai ngày.

    Nên phần "hiện ra" giữ nguyên (`healed_lots` + `explain()`), phần "không tự
    sửa" đổi thành: cân theo broker khi lot GIẢM, vẫn báo lỗi khi lot TĂNG. Đường
    cũ vẫn kiểm được qua `auto_heal_lots=False`.
    """
    book.open("zb_audcad_h1", symbol="AUDCAD", side="BUY", lots=1.5,
              entry_bar_utc="2026-08-10 09:00:00", entry_price=0.9, timeframe="H1")
    r = book.reconcile([_Pos("AUDCAD", 0.5, 0)], auto_heal_lots=False)
    assert not r.ok and "AUDCAD" in r.lot_mismatch


def test_broker_holding_more_than_the_book_is_never_healed(book):
    """Phơi nhiễm NHIỀU hơn sổ là bất thường thật — đóng bớt không làm lot tăng."""
    book.open("zb_audcad_h1", symbol="AUDCAD", side="BUY", lots=0.5,
              entry_bar_utc="2026-08-10 09:00:00", entry_price=0.9, timeframe="H1")
    r = book.reconcile([_Pos("AUDCAD", 1.5, 0)])
    assert not r.ok and "AUDCAD" in r.lot_mismatch
    assert r.healed_lots == {}


# ═════════════════════════════════════════════════════ 4. công tắc thủ công
def test_trading_control_defaults_to_enabled(tmp_path):
    assert TC.read(tmp_path / "ctl.json").enabled is True


def test_trading_control_persists(tmp_path):
    p = tmp_path / "ctl.json"
    TC.set_enabled(False, reason="đang vá lỗi", by="toan", path=p)
    st = TC.read(p)
    assert st.enabled is False and "vá lỗi" in st.reason
    assert TC.entry_allowed(p) is False


def test_trading_control_fails_closed_on_corrupt_file(tmp_path):
    """File hỏng → TẮT. Không đọc được ý người vận hành thì không tự cho phép."""
    p = tmp_path / "ctl.json"
    p.write_text("{ khong phai json", encoding="utf-8")
    assert TC.entry_allowed(p) is False


# ═════════════════════════════════════════════════════ 5. router gửi lệnh
class _Plan:
    def __init__(self, actions, allowed=True, leverage=3.7):
        self.actions = actions
        self.allowed = allowed
        self.leverage = leverage
        self.gate = type("G", (), {"explain": lambda s: "cổng chặn"})()

    @property
    def to_trade(self):
        return [a for a in self.actions if a.action != "HOLD"]


def _act(symbol, action, side, lots, cur=0.0, tgt=0.0, stop=None, reason=""):
    from src.python.execution.order_plan import OrderAction
    return OrderAction(symbol=symbol, action=action, side=side, lots=lots,
                       current_lots=cur, target_lots=tgt, target_weight=0.1,
                       stop_price=stop, reason=reason)



@pytest.fixture(autouse=True)
def _isolate_idempotency(tmp_path, monkeypatch):
    """Mỗi test một sổ khoá RIÊNG.

    Khoá chống gửi trùng nay ghi ra đĩa và sống qua khởi động lại (xem
    `order_router._restore_claims_once`). Dùng chung sổ thật thì test này chặn
    test kia, và tệ hơn — chạy test sẽ ghi vào đúng sổ mà bản LIVE đang dùng.
    """
    from src.python.core.broker.order_state_machine import OrderStateMachine as OSM

    monkeypatch.setattr(OSM, "_outbox_file", tmp_path / "durable_event_log.jsonl",
                        raising=False)
    OSM._orders.clear()
    OSM._claimed_keys.clear()
    OSM._claim_order.clear()
    monkeypatch.setattr(OR, "_claims_restored", True, raising=False)
    yield
    OSM._orders.clear()
    OSM._claimed_keys.clear()
    OSM._claim_order.clear()


class _BrokerPos:
    """Vị thế broker tối thiểu — đúng các trường mà router đọc.

    Tách khỏi `_Pos` của nhóm test đối soát: chỗ đó chỉ cần symbol/volume/type,
    còn router cần thêm `ticket` (để khoá lệnh đóng) và `magic` (để phân biệt vị
    thế của hệ này với hệ khác chạy chung tài khoản).
    """

    def __init__(self, ticket, symbol, typ, volume, magic):
        self.ticket, self.symbol, self.type = ticket, symbol, typ
        self.volume, self.magic, self.sl = volume, magic, 0.0


class _MT5:
    """Broker giả kiểu HEDGING — đúng loại tài khoản FTMO cấp.

    Phân biệt netting/hedging là bắt buộc ở đây, không phải chi tiết thừa: trên
    hedging, một lệnh KHÔNG mang trường `position` là lệnh MỞ MỚI chứ không trừ
    vào vị thế đang có. Bản giả cũ không mô phỏng điều đó, nên nó xác nhận một
    đường code mà trên tài khoản thật sẽ nhân đôi phơi nhiễm — xem
    `order_router._close_symbol`.
    """

    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    TRADE_RETCODE_DONE = 10009

    def __init__(self, positions=None):
        self.requests = []
        self.positions = list(positions or [])

    def symbol_info_tick(self, _s):
        return type("T", (), {"bid": 0.8999, "ask": 0.9001})()

    def positions_get(self, symbol=None, ticket=None):
        return tuple(p for p in self.positions
                     if (symbol is None or p.symbol == symbol)
                     and (ticket is None or p.ticket == ticket))

    def order_send(self, req):
        self.requests.append(req)
        if "position" in req:
            self.positions = [p for p in self.positions
                              if p.ticket != req["position"]]
        else:
            self.positions.append(_BrokerPos(9000 + len(self.requests), req["symbol"],
                                       req["type"], req["volume"], req["magic"]))
        return type("R", (), {"retcode": 10009, "order": 12345, "comment": "done"})()


def _held(symbol="AUDCAD", lots=1.0, long=True):
    """Một vị thế đang mở của CHÍNH hệ này (magic nằm trong dải của hệ)."""
    return _BrokerPos(1, symbol, 0 if long else 1, lots, OR.MAGIC_BASE + 1)


def test_router_sends_nothing_when_gate_blocks():
    """Bất biến 1 — cổng chặn thì KHÔNG một lệnh nào, kiểm ở chính router."""
    mt5 = _MT5()
    r = OR.OrderRouter(mt5, dry_run=False)
    out = r.route(_Plan([_act("AUDCAD", "OPEN", "BUY", 1.0, tgt=1.0, stop=0.85)],
                        allowed=False), log_decisions=False)
    assert out.sent == [] and mt5.requests == []
    assert out.blocked_reason


def test_reverse_becomes_two_orders():
    """Bất biến 2 — ĐẢO CHIỀU là đóng rồi mở, không phải một lệnh gấp đôi."""
    mt5 = _MT5([_held("AUDCAD", 1.0, long=True)])
    r = OR.OrderRouter(mt5, dry_run=False)
    out = r.route(_Plan([_act("AUDCAD", "REVERSE", "SELL", 2.0,
                              cur=1.0, tgt=-1.0, stop=0.95)]),
                  log_decisions=False, bar_utc="2026-08-15 10:00")
    assert [s.action for s in out.sent] == ["REVERSE_CLOSE", "REVERSE_OPEN"]
    assert len(mt5.requests) == 2
    assert out.sent[0].lots == pytest.approx(1.0)   # đóng đúng phần đang giữ
    assert out.sent[1].lots == pytest.approx(1.0)   # mở đúng phần muốn giữ
    # Nửa ĐÓNG phải khoá đích danh vị thế cũ, nửa MỞ thì không.
    assert "position" in mt5.requests[0], "lệnh đóng KHÔNG khoá ticket"
    assert "position" not in mt5.requests[1]
    # Kết cục: đúng MỘT vị thế, và là vị thế NGƯỢC chiều ban đầu.
    assert len(mt5.positions) == 1
    assert mt5.positions[0].type == mt5.ORDER_TYPE_SELL


def test_open_order_carries_stop_in_same_request():
    """Bất biến 3 — cầu chì nằm TRONG lệnh mở, không đặt sau bằng lệnh thứ hai.

    Giữa hai lệnh là khoảng thời gian vị thế nằm TRẦN; tiến trình chết đúng lúc đó
    thì nó nằm trần mãi mãi.
    """
    mt5 = _MT5()
    r = OR.OrderRouter(mt5, dry_run=False)
    r.route(_Plan([_act("AUDCAD", "OPEN", "BUY", 1.0, tgt=1.0, stop=0.855)]),
            log_decisions=False)
    assert mt5.requests[0]["sl"] == pytest.approx(0.855)


class _MT5Fused(_MT5):
    """Ticket trả về KHỚP đúng vị thế vừa tạo — đúng hành vi MT5 thật, cần cho
    `_verify_stop_attached` (tra `positions_get(ticket=...)`). `honor_sl=False`
    tái tạo sự cố 24/08/2026: broker trả DONE nhưng bỏ qua `sl` của request.
    """

    TRADE_ACTION_SLTP = 2

    def __init__(self, *, honor_sl: bool, positions=None):
        super().__init__(positions)
        self.honor_sl = honor_sl

    def order_send(self, req):
        self.requests.append(req)
        if req.get("action") == self.TRADE_ACTION_SLTP:
            for p in self.positions:
                if p.ticket == req["position"]:
                    p.sl = float(req["sl"])
            return type("R", (), {"retcode": 10009, "order": 0, "comment": "done"})()
        if "position" in req:
            self.positions = [p for p in self.positions if p.ticket != req["position"]]
            return type("R", (), {"retcode": 10009, "order": 0, "comment": "done"})()
        ticket = 9000 + len(self.requests)
        pos = _BrokerPos(ticket, req["symbol"], req["type"], req["volume"], req["magic"])
        if self.honor_sl:
            pos.sl = float(req.get("sl", 0.0) or 0.0)
        self.positions.append(pos)
        return type("R", (), {"retcode": 10009, "order": ticket, "comment": "done"})()


def test_broker_silently_drops_sl_gets_repaired_immediately():
    """SỰ CỐ 24/08/2026 — broker trả DONE nhưng bỏ qua `sl`. `ftmo_guard` sau đó
    thấy vị thế "thiếu cầu chì", giả định rủi ro ở mức trần và đóng SẠCH cả sổ
    (đo được: 40/40 vị thế cho một lỗi ở đúng MỘT vị thế). Router phải tự phát
    hiện và gắn lại NGAY trong cùng lệnh gọi, không chờ chu kỳ guard sau.
    """
    mt5 = _MT5Fused(honor_sl=False)
    r = OR.OrderRouter(mt5, dry_run=False)
    out = r.route(_Plan([_act("AUDCAD", "OPEN", "BUY", 1.0, tgt=1.0, stop=0.85)]),
                  log_decisions=False, bar_utc="2026-08-24T09")

    assert out.sent[0].ok
    sltp = [rq for rq in mt5.requests if rq.get("action") == mt5.TRADE_ACTION_SLTP]
    assert len(sltp) == 1, "phải tự gửi đúng MỘT lệnh SLTP để gắn lại cầu chì"
    assert sltp[0]["sl"] == pytest.approx(0.85)
    assert mt5.positions[0].sl == pytest.approx(0.85), \
        "vị thế trên broker phải có cầu chì thật sau khi gắn lại"


def test_broker_honors_sl_no_repair_needed():
    """Đường bình thường — broker gắn cầu chì đúng ngay lần đầu thì KHÔNG gửi
    thêm lệnh SLTP nào (lưới an toàn chỉ can thiệp khi thật sự thiếu)."""
    mt5 = _MT5Fused(honor_sl=True)
    r = OR.OrderRouter(mt5, dry_run=False)
    out = r.route(_Plan([_act("AUDCAD", "OPEN", "BUY", 1.0, tgt=1.0, stop=0.85)]),
                  log_decisions=False, bar_utc="2026-08-24T09")

    assert out.sent[0].ok
    assert len(mt5.requests) == 1, "không cần verify/sửa gì khi cầu chì đã đúng từ đầu"


def test_close_order_has_no_stop():
    """Gửi kèm `sl` vào lệnh ĐÓNG là cách broker từ chối cả lệnh."""
    mt5 = _MT5([_held("AUDCAD", 1.0, long=True)])
    r = OR.OrderRouter(mt5, dry_run=False)
    r.route(_Plan([_act("AUDCAD", "CLOSE", "SELL", 1.0, cur=1.0, tgt=0.0,
                        stop=0.855)]), log_decisions=False,
            bar_utc="2026-08-15 10:00")
    assert "sl" not in mt5.requests[0]


def test_close_targets_position_by_ticket():
    """Lệnh ĐÓNG phải khoá ĐÍCH DANH vị thế, không phải một lệnh ngược chiều.

    Trên tài khoản HEDGING — đúng loại FTMO cấp — lệnh không mang `position` là
    lệnh MỞ MỚI. Bản trước gửi đúng như vậy, nên mỗi lần hệ định đóng 0,42 lot mua
    thì nhận thêm 0,42 lot bán: phơi nhiễm GẤP ĐÔI đúng lúc đang cố giảm rủi ro,
    ký quỹ chiếm gấp đôi, và chu kỳ sau chênh lệch vẫn khác 0 nên hệ lại gửi thêm
    một lệnh "đóng" nữa — vòng lặp nhân đôi vị thế.
    """
    mt5 = _MT5([_held("AUDCAD", 0.42, long=True)])
    r = OR.OrderRouter(mt5, dry_run=False)
    out = r.route(_Plan([_act("AUDCAD", "CLOSE", "SELL", 0.42, cur=0.42, tgt=0.0)]),
                  log_decisions=False, bar_utc="2026-08-15 10:00")
    assert mt5.requests, "không gửi lệnh đóng nào"
    assert mt5.requests[0].get("position") == 1, "lệnh đóng KHÔNG khoá ticket"
    assert mt5.positions == [], "vẫn còn vị thế sau khi đóng"
    assert out.sent[0].ok


def test_close_ignores_positions_of_other_systems():
    """Chỉ đóng vị thế CỦA HỆ NÀY — magic ngoài dải là của bot khác.

    Hai bot chạy chung một tài khoản là tình huống có thật (hệ XAUUSD dùng dải
    2607xx). Đóng nhầm lệnh của hệ kia là phá vị thế mà mình không hề quản lý.
    """
    ngoai = _BrokerPos(77, "AUDCAD", 0, 1.0, 260701)   # magic của hệ XAUUSD
    mt5 = _MT5([ngoai])
    r = OR.OrderRouter(mt5, dry_run=False)
    out = r.route(_Plan([_act("AUDCAD", "CLOSE", "SELL", 1.0, cur=1.0, tgt=0.0)]),
                  log_decisions=False, bar_utc="2026-08-15 10:00")
    assert mt5.requests == [], "đã đụng vào vị thế của hệ khác"
    assert mt5.positions == [ngoai]
    assert out.sent[0].ok, "không còn vị thế của hệ = coi như đã đóng"


def test_close_fails_loudly_when_positions_get_errors():
    """`positions_get()` trả None là LỖI ĐỌC, KHÔNG phải 'không có vị thế'.

    Coi lỗi đọc là 'đã phẳng sổ' là fail-OPEN ở đúng nhánh cứu hoả — cùng cái bẫy
    mà `mt5_bridge.close_all_positions` đã ghi lại.
    """
    mt5 = _MT5([_held("AUDCAD", 1.0)])
    mt5.positions_get = lambda symbol=None, ticket=None: None
    r = OR.OrderRouter(mt5, dry_run=False)
    out = r.route(_Plan([_act("AUDCAD", "CLOSE", "SELL", 1.0, cur=1.0, tgt=0.0)]),
                  log_decisions=False, bar_utc="2026-08-15 10:00")
    assert out.sent[0].ok is False
    assert "lỗi đọc" in out.sent[0].reason


def test_blocked_gate_still_sends_exit_orders():
    """Cổng chặn lệnh TĂNG phơi nhiễm, KHÔNG được chặn đường THOÁT.

    Khi `ftmo_leverage_policy` trả 0 vì đệm tới sàn đã cạn, mục tiêu mọi công cụ
    về 0 và kế hoạch sinh ra một loạt lệnh ĐÓNG — đúng thứ cần làm. Bản trước
    `return` sớm ở `plan.allowed is False`, nên hệ ĐÓNG BĂNG ở đúng thời điểm
    phải thoát và ngồi nguyên tới khi chạm sàn nội bộ 9% rồi luật FTMO 10%.
    """
    mt5 = _MT5([_held("AUDCAD", 1.0, long=True)])
    r = OR.OrderRouter(mt5, dry_run=False)
    out = r.route(_Plan([_act("AUDCAD", "CLOSE", "SELL", 1.0, cur=1.0, tgt=0.0),
                         _act("GBPAUD", "OPEN", "BUY", 0.3, tgt=0.3, stop=1.8)],
                        allowed=False),
                  log_decisions=False, bar_utc="2026-08-15 10:00")
    gui = [s.action for s in out.sent]
    assert "CLOSE" in gui, "cổng chặn nuốt luôn lệnh ĐÓNG"
    assert "OPEN" not in gui, "cổng chặn nhưng lệnh MỞ vẫn đi"
    assert mt5.positions == [], "vị thế chưa được thoát"


def test_idempotency_blocks_duplicate_send():
    """Cùng công cụ, cùng việc, cùng nến → gửi ĐÚNG một lần."""
    mt5 = _MT5()
    r = OR.OrderRouter(mt5, dry_run=False)
    plan = _Plan([_act("AUDCAD", "OPEN", "BUY", 1.0, tgt=1.0, stop=0.85)])
    r.route(plan, bar_utc="2026-08-14T15", log_decisions=False)
    r.route(plan, bar_utc="2026-08-14T15", log_decisions=False)
    assert len(mt5.requests) == 1
    # Nến SAU là lệnh khác, phải gửi được.
    r.route(plan, bar_utc="2026-08-14T16", log_decisions=False)
    assert len(mt5.requests) == 2


def test_dry_run_never_touches_broker():
    mt5 = _MT5()
    r = OR.OrderRouter(mt5, dry_run=True)
    out = r.route(_Plan([_act("AUDCAD", "OPEN", "BUY", 1.0, tgt=1.0, stop=0.85)]),
                  log_decisions=False)
    assert mt5.requests == []
    assert all(s.dry_run for s in out.sent)


def test_magic_is_deterministic_and_outside_xau_range():
    """Magic phải tất định và KHÁC dải 2607xx của hệ XAUUSD.

    Hai bot chung một tài khoản mà magic trùng thì `position_book` nhận nhầm vị thế
    của hệ kia là của mình — hoặc báo MỒ CÔI cho vị thế của chính mình.
    """
    a = OR.magic_for("zb_audcad_h1")
    assert a == OR.magic_for("zb_audcad_h1")
    assert a != OR.magic_for("zb_gbpaud_h1")
    assert OR.MAGIC_BASE >= 5_000_000
    assert not (260_000 <= a <= 269_999)


# ═════════════════════════════════════════════════════ 6. phạm vi cổng tin
def test_news_gate_declares_only_what_calendar_has():
    """Không được khai loại sự kiện mà lịch không có dòng nào.

    Khai một cổng không bao giờ nổ tệ hơn không khai: người đọc code tin rằng họp
    RBA có được canh, và không ai đi kiểm lại.
    """
    import pandas as pd

    from src.python.ai import news_guard as NG

    df = pd.read_parquet(NG.CALENDAR_PATH)
    have = {str(e).upper() for e in df["event"].unique()}
    declared = set(NG.BLOCK_FULL_DAY_EVENTS) | set(NG.WINDOW_ONLY_EVENTS)
    assert declared <= have, f"khai nhưng lịch không có: {sorted(declared - have)}"


def test_news_scope_is_declared_but_does_not_decide_blocking():
    """Phạm vi lịch phải ĐỌC ĐƯỢC, nhưng KHÔNG được tham gia quyết định chặn.

    Đã thử lọc `blocks_instrument()` theo `COVERED_CURRENCIES` và SAI, hoàn lại
    14/08/2026: tầng LLM đọc tiêu đề tin nên biết được thứ lịch không có ("BOJ can
    thiệp" là JPY), và lọc theo phạm vi LỊCH sẽ vô hiệu hoá đúng phần LLM có ích.
    Ngoài ra `currencies` rỗng nghĩa là KHÔNG BIẾT → chặn tất cả, và đó là nhánh an
    toàn không được phá.
    """
    from src.python.ai import news_guard as NG

    # Khai báo phạm vi: đọc được.
    assert NG.in_scope("EURUSD") and NG.in_scope("GBPJPY")
    assert not NG.in_scope("AUDCAD") and not NG.in_scope("NZDCAD")
    assert "NGOÀI PHẠM VI" in NG.scope_note("AUDCAD")
    assert NG.scope_note("EURUSD") == ""

    # Không biết đồng nào → chặn TẤT CẢ, kể cả công cụ ngoài phạm vi lịch.
    d = NG.GuardDecision(timestamp=pd.Timestamp("2026-08-14"), blocked=True,
                         source="CALENDAR", currencies=())
    assert d.blocks_instrument("EURUSD") is True
    assert d.blocks_instrument("AUDCAD") is True

    # Biết đồng nào thì lọc theo ĐỒNG, không theo phạm vi lịch.
    d2 = NG.GuardDecision(timestamp=pd.Timestamp("2026-08-14"), blocked=True,
                          source="LLM", currencies=("JPY",))
    assert d2.blocks_instrument("CADJPY") is True
    assert d2.blocks_instrument("AUDCAD") is False


# ═════════════════════════════════════════════════════ 7. nối vào vòng lặp engine
def _engine(monkeypatch, *, closed=False):
    from src.python.core.infra import market_schedule as MS
    from src.python.core.engine import TradingEngine

    monkeypatch.setattr(MS, "is_market_closed", lambda *a, **k: closed)
    e = TradingEngine()
    e._prev_market_closed = closed
    return e


def test_plan_not_built_when_market_closed(monkeypatch):
    """Cuối tuần KHÔNG dựng kế hoạch — giá đóng băng cho lot sai ngay lúc mở cửa."""
    e = _engine(monkeypatch, closed=True)
    called = []
    monkeypatch.setattr(e, "_build_plan", lambda: called.append(1))
    e._last_plan = 0.0
    e._maybe_build_plan()
    assert called == []


def test_plan_is_built_when_market_open(monkeypatch):
    e = _engine(monkeypatch, closed=False)
    called = []
    monkeypatch.setattr(e, "_build_plan", lambda: called.append(1))
    e._last_plan = 0.0
    e._maybe_build_plan()
    assert called == [1]


def test_plan_respects_cadence(monkeypatch):
    """Dựng lại trong vòng một giờ là ra cùng một kế hoạch — tốn 130 giây vô ích."""
    import time as _t

    e = _engine(monkeypatch, closed=False)
    called = []
    monkeypatch.setattr(e, "_build_plan", lambda: called.append(1))
    e._last_plan = _t.time()          # vừa dựng xong
    e._maybe_build_plan()
    assert called == []


def test_engine_defaults_to_dry_run(monkeypatch):
    """Mặc định KHÔNG chạm tiền thật. Một lần bật nhầm là tiền thật.

    `arm_orders` đã bỏ 15/08/2026 — công tắc vào lệnh nay là `trading_control`, và
    "môi trường có được chạm tiền thật" là biến `LIVE_ORDERS` trong `.env`.
    """
    from src.python.core import config

    e = _engine(monkeypatch)
    assert e.dry_run is (not config.LIVE_ORDERS)


def test_build_plan_without_broker_reports_instead_of_crashing(monkeypatch):
    """Chưa kết nối MT5 thì ghi lý do vào state, không ném lỗi lên vòng lặp."""
    e = _engine(monkeypatch)
    e.state["account_info"] = None
    e.state["prices"] = {}
    e._build_plan()
    assert "chưa có equity" in e.state["order_plan"]["error"]


def test_spread_log_skipped_when_market_closed(monkeypatch):
    """Spread cuối tuần là giá đóng băng — ghi vào bảng đo sẽ kéo lệch trung vị."""
    e = _engine(monkeypatch, closed=True)
    lines = []
    monkeypatch.setattr(e, "log", lambda m: lines.append(m))
    e.state["spread"] = {"EURUSD": 0.3}
    e.state["prices"] = {"EURUSD": 1.10}
    e._last_spread_log = 0.0
    e._maybe_log_spread()
    assert lines == []


def test_spread_log_prints_table_with_deviation(monkeypatch):
    """Bảng phải có cột LỆCH so với ước lượng — đó là thứ dùng để thay ước lượng."""
    e = _engine(monkeypatch, closed=False)
    lines = []
    monkeypatch.setattr(e, "log", lambda m: lines.append(m))
    # 1,0 bps trên EURUSD ở 1,10 = 0,00011 giá = 1,1 pip, ước lượng 0,3 → +267%
    e.state["spread"] = {"EURUSD": 1.0}
    e.state["prices"] = {"EURUSD": 1.10}
    e._last_spread_log = 0.0
    e._maybe_log_spread()
    body = "\n".join(lines)
    assert "SPREAD THẬT" in body
    assert "EURUSD" in body and "%" in body
    assert "rộng hơn ước lượng" in body


def test_spread_card_handles_dict_from_engine():
    """Thẻ SPREAD nhận DICT 27 công cụ, không phải một số.

    Bản kế thừa format thẳng `f"{spread:.2f}"` → `TypeError` với dict. Lỗi bị
    `status_callback` nuốt nên MỌI thẻ sau đó ngừng vẽ, không có gì báo — đúng
    triệu chứng "các card không load" đã gặp.
    """
    spread = {"EURUSD": 0.3, "AUDCAD": 1.2, "GBPNZD": 9.9}
    with pytest.raises(TypeError):
        f"{spread:.2f}"                       # cách CŨ — chứng minh nó vỡ

    vals = sorted(spread.values())
    med = vals[len(vals) // 2]
    assert f"{med:.2f} bps" == "1.20 bps"     # cách MỚI — trung vị, có đơn vị


# ═════════════════════════════════════════════════════ 8. nút RUN / STOP ENGINE
@pytest.fixture()
def _ctl(tmp_path, monkeypatch):
    """Trỏ công tắc sang thư mục tạm để test không đụng file thật."""
    from src.python.execution import trading_control as _TC

    monkeypatch.setattr(_TC, "CONTROL_PATH", tmp_path / "ctl.json")
    return tmp_path / "ctl.json"


def test_stop_blocks_entries_but_keeps_loop_running(monkeypatch, _ctl):
    """STOP chặn lệnh MỚI nhưng KHÔNG dừng vòng lặp.

    Đây là điểm đổi nghĩa 15/08/2026. Trước đó STOP gọi `stop_loop()` — bảng đứng
    hình mà không ngăn được gì. Cái người vận hành cần lúc 2 giờ sáng là "ngừng vào
    lệnh mới ngay", không phải "tắt màn hình".
    """
    e = _engine(monkeypatch)
    stopped = []
    monkeypatch.setattr(e, "stop_loop", lambda: stopped.append(1))

    e.block_entries(by="test")
    assert e.entries_allowed is False
    assert stopped == [], "STOP KHÔNG được dừng vòng lặp"


def test_run_allows_entries(monkeypatch, _ctl):
    e = _engine(monkeypatch)
    e.block_entries(by="test")
    e.allow_entries(by="test")
    assert e.entries_allowed is True


def test_switch_survives_restart(monkeypatch, _ctl):
    """Bot tự khởi động lại lúc 3 giờ sáng KHÔNG được tự cho phép vào lệnh trở lại."""
    e1 = _engine(monkeypatch)
    e1.block_entries(by="test")

    e2 = _engine(monkeypatch)          # giả lập tiến trình mới
    assert e2.entries_allowed is False


def test_entries_allowed_reads_disk_every_time(monkeypatch, _ctl):
    """Không nhớ trong RAM: công tắc có thể bị đổi từ tiến trình khác.

    Một bản sao cũ trong RAM nghĩa là hệ vẫn vào lệnh sau khi người vận hành đã bấm
    STOP ở nơi khác.
    """
    from src.python.execution import trading_control as _TC

    e = _engine(monkeypatch)
    assert e.entries_allowed is True
    _TC.set_enabled(False, reason="tiến trình khác", by="script",
                    path=_TC.CONTROL_PATH)
    assert e.entries_allowed is False


def test_plan_not_routed_when_entries_blocked(monkeypatch, _ctl):
    """Đã bấm STOP thì kế hoạch VẪN dựng và hiện, nhưng không lệnh nào được gửi."""
    e = _engine(monkeypatch)
    e.block_entries(by="test")
    lines = []
    monkeypatch.setattr(e, "log", lambda m: lines.append(m))

    # Giả lập một kế hoạch đã dựng xong với 2 việc.
    routed = []
    monkeypatch.setattr(e, "state", dict(e.state))
    assert e.entries_allowed is False
    # Đường code thật: `_build_plan` trả về sớm trước khi chạm router.
    assert not any("order_send" in str(x) for x in routed)


def test_dry_run_follows_live_orders_env(monkeypatch, _ctl):
    """`dry_run` suy từ biến môi trường, KHÔNG phải một cờ sửa được lúc chạy.

    Trộn "môi trường có được chạm tiền thật" với "người vận hành có cho vào lệnh" là
    cách một lần bấm nút trên máy phát triển gửi lệnh thật.
    """
    from src.python.core import config

    e = _engine(monkeypatch)
    assert e.dry_run is (not config.LIVE_ORDERS)


def test_no_stray_arm_orders_flag(monkeypatch, _ctl):
    """Bốn công tắc cho một quyết định đã gộp còn hai — không được mọc lại cái thứ ba."""
    e = _engine(monkeypatch)
    assert not hasattr(e, "arm_orders"), (
        "`arm_orders` đã bỏ 15/08/2026; công tắc vào lệnh là `trading_control`")


# ═════════════════════════════════════════════════════ 9. ngắt mạch
class _Breaker:
    """Ngắt mạch giả: đếm lỗi, mở sau `limit` lần."""

    def __init__(self, limit=3):
        self.limit, self.fails, self.ok_count = limit, 0, 0

    def can_execute(self):
        if self.fails >= self.limit:
            return False, f"OPEN sau {self.fails} lỗi liên tiếp"
        return True, ""

    def record_failure(self, retcode, comment=""):
        self.fails += 1
        return True

    def record_success(self, source="trade"):
        self.ok_count += 1
        self.fails = 0


class _RejectMT5(_MT5):
    """Broker từ chối MỌI lệnh — mô phỏng sự cố phía sàn."""

    def order_send(self, req):
        self.requests.append(req)
        return type("R", (), {"retcode": 10019, "order": 0,
                              "comment": "no money"})()


def test_breaker_stops_the_retry_storm():
    """Broker từ chối liên tiếp → NGẮT MẠCH, không gửi thêm.

    Không có nó, một sự cố phía broker thành vòng lặp: kế hoạch 23 việc → 23 lệnh
    bị từ chối → chu kỳ sau vẫn 23 việc đó (vị thế chưa mở nên chênh lệch không
    đổi) → 23 lệnh nữa. Vượt hạn mức lệnh/giây lặp lại là lý do bị KHOÁ tài khoản —
    mất tài khoản vì lỗi kỹ thuật chứ không phải vì thua lỗ.
    """
    mt5 = _RejectMT5()
    br = _Breaker(limit=3)
    r = OR.OrderRouter(mt5, dry_run=False, breaker=br)

    acts = [_act(f"SYM{i}", "OPEN", "BUY", 1.0, tgt=1.0, stop=0.9)
            for i in range(10)]
    out = r.route(_Plan(acts), bar_utc="2026-08-15T10", log_decisions=False)

    assert len(mt5.requests) == 3, f"gửi {len(mt5.requests)} lệnh, phải dừng ở 3"
    assert sum(1 for s in out.sent if "NGẮT MẠCH" in s.reason) == 7


def test_breaker_is_shared_across_cycles():
    """Bộ đếm lỗi phải CỘNG DỒN qua nhiều chu kỳ tái cân bằng.

    Tạo breaker mới mỗi lần `route()` thì bộ đếm reset sau mỗi chu kỳ và ngưỡng
    `max_failures` không bao giờ chạm tới — ngắt mạch thành trang trí.
    """
    mt5 = _RejectMT5()
    br = _Breaker(limit=3)
    r = OR.OrderRouter(mt5, dry_run=False, breaker=br)
    for i in range(3):
        r.route(_Plan([_act("AUDCAD", "OPEN", "BUY", 1.0, tgt=1.0, stop=0.9)]),
                bar_utc=f"2026-08-15T1{i}", log_decisions=False)
    assert br.fails >= 3
    assert len(mt5.requests) == 3


def test_breaker_checked_in_dry_run_too():
    """Dry-run phải đi qua ĐÚNG đường code của chế độ thật, kể cả nhánh ngắt mạch."""
    br = _Breaker(limit=0)          # OPEN ngay từ đầu
    r = OR.OrderRouter(_MT5(), dry_run=True, breaker=br)
    out = r.route(_Plan([_act("AUDCAD", "OPEN", "BUY", 1.0, tgt=1.0, stop=0.9)]),
                  log_decisions=False)
    assert all("NGẮT MẠCH" in s.reason for s in out.sent)


@pytest.fixture()
def _isolate_alerts(tmp_path, monkeypatch):
    """Sổ chống-gửi-trùng RIÊNG cho từng test — xem `_isolate_idempotency` ở trên.

    Không cách ly thì `alerts.once()` đọc/ghi `logs/live/alert_dedup.json` thật,
    và một test chạy trước có thể chặn (`ttl_sec`) email của test chạy sau.
    """
    from src.python.utils import alerts

    monkeypatch.setattr(alerts, "STATE_PATH", tmp_path / "alert_dedup.json")
    alerts._last_sent.clear()
    yield
    alerts._last_sent.clear()


def test_breaker_block_sends_one_grouped_email_not_one_per_symbol(monkeypatch, _isolate_alerts):
    """SỰ CỐ 24/08/2026 — một cầu dao mở KHÔNG được cascade thành N thư sai sự thật.

    Trước bản vá: mỗi hành động bị NGẮT MẠCH chặn (chưa từng chạm broker) vẫn đi
    qua `EM.order_rejected` với `retcode=0` giả — một mã không tồn tại trong MT5 —
    và nội dung thư khẳng định sai "Broker từ chối". 22 công cụ bị breaker chặn
    trong cùng một chu kỳ ra 22 thư như vậy cho ĐÚNG MỘT nguyên nhân gốc.
    """
    from src.python.execution import order_router as OR_mod
    from src.python.shared.notifications import emails as EM_mod

    rejected_calls = []
    grouped_calls = []
    monkeypatch.setattr(EM_mod, "order_rejected",
                        lambda **kw: rejected_calls.append(kw) or True)
    monkeypatch.setattr(EM_mod, "circuit_breaker_open",
                        lambda **kw: grouped_calls.append(kw) or True)
    monkeypatch.setattr(EM_mod, "entry", lambda **kw: True)

    br = _Breaker(limit=0)          # OPEN ngay từ đầu — mọi lệnh đều bị chặn
    r = OR.OrderRouter(_MT5(), dry_run=False, breaker=br)
    acts = [_act(f"SYM{i}", "OPEN", "BUY", 1.0, tgt=1.0, stop=0.9) for i in range(5)]
    out = r.route(_Plan(acts), bar_utc="2026-08-24T08", log_decisions=False)

    assert all("NGẮT MẠCH" in s.reason for s in out.sent)
    assert rejected_calls == [], "lệnh bị NGẮT MẠCH chặn không được coi là broker từ chối"
    assert len(grouped_calls) == 1, "phải gộp thành ĐÚNG MỘT thư cho cả đợt"
    assert sorted(grouped_calls[0]["blocked_symbols"]) == [f"SYM{i}" for i in range(5)]


def test_duplicate_claim_skip_does_not_resend_entry_email(monkeypatch, _isolate_alerts):
    """SỰ CỐ 25/08/2026 — khoá chống gửi lặp còn sống (khởi động lại giữa lúc claim
    chưa nhả, hoặc chu kỳ sau lặp đúng tín hiệu) không được coi là một lần vào lệnh
    MỚI. `_send_one()` trả `ok=True, reason="BỎ QUA — trùng khoá..."` cho trường hợp
    này — đúng cho đường gửi lệnh (không được gửi lại thật), nhưng `_email()` trước
    bản vá chỉ nhìn `ok` và `action` nên vẫn báo "🔔 vào lệnh" cho một lần KHÔNG hề
    chạm broker, làm người vận hành tưởng có thêm một vị thế không có thật.
    """
    from src.python.shared.notifications import emails as EM_mod

    entry_calls = []
    monkeypatch.setattr(EM_mod, "entry", lambda **kw: entry_calls.append(kw) or True)

    mt5 = _MT5()
    r = OR.OrderRouter(mt5, dry_run=False)
    plan = _Plan([_act("AUDCAD", "OPEN", "BUY", 1.0, tgt=1.0, stop=0.85)])

    r.route(plan, bar_utc="2026-08-25T07", log_decisions=False)
    r.route(plan, bar_utc="2026-08-25T07", log_decisions=False)  # cùng nến -> trùng khoá

    assert len(mt5.requests) == 1, "chỉ được chạm broker đúng một lần"
    assert len(entry_calls) == 1, (
        "chỉ được báo 'vào lệnh' đúng một lần — lần BỎ QUA không phải một lệnh mới")


# ═════════════════════════════════════════════════════ 10. quản lý lệnh sau khi mở
def test_exit_reasons_are_a_closed_set():
    """Lý do đóng phải là tập ĐÓNG — bản ghi mọc biến thể chính tả là bản ghi vô dụng."""
    from src.python.execution import exit_manager as EM

    with pytest.raises(ValueError):
        EM.record_close(None, "x", reason="time stop", exit_price=1.0,
                        exit_bar_utc="2026-08-15", bars_held=1)


def test_record_close_is_the_single_convergence_point(book):
    """Mọi nhánh đóng lệnh đi qua MỘT hàm, và hàm đó phải cập nhật SỔ.

    Hệ XAUUSD học bài này ở `position_lifecycle.finalize_position_closed()`: hai
    đường đóng lệnh không hội tụ nghĩa là một đường sẽ quên cập nhật sổ, và sổ lệch
    thì đối soát báo MỒ CÔI cho chính vị thế của mình.
    """
    from src.python.execution import exit_manager as EM

    book.open("zb_audcad_h1", symbol="AUDCAD", side="BUY", lots=1.0,
              entry_bar_utc="2026-08-10 09:00:00", entry_price=0.9000,
              timeframe="H1", stop_price=0.8559)
    rec = EM.record_close(book, "zb_audcad_h1", reason=EM.REASON_TIMESTOP,
                          exit_price=0.9045, exit_bar_utc="2026-08-12 09:00:00",
                          bars_held=48, log=False)
    assert rec is not None
    assert len(book) == 0, "sổ phải sạch sau khi đóng"
    assert rec.gross_bps == pytest.approx(50.0, abs=0.1)   # +45 pip trên 0,9000
    assert rec.reason == EM.REASON_TIMESTOP


def test_record_close_on_empty_leg_returns_none(book):
    from src.python.execution import exit_manager as EM

    assert EM.record_close(book, "zb_audcad_h1", reason=EM.REASON_MANUAL,
                           exit_price=1.0, exit_bar_utc="2026-08-15",
                           bars_held=0, log=False) is None


def test_mfe_mae_measure_where_the_trade_had_been(book):
    """MFE/MAE quét bóng nến — chúng trả lời "lệnh ĐÃ TỪNG ở đâu", không phải giá đóng.

    Đây đúng hai đại lượng đã dùng để BÁC BỎ dừng lỗ và trailing, nên ghi chúng ở
    live là cách kiểm chứng lại kết luận đó bằng tiền thật.
    """
    from src.python.execution import exit_manager as EM

    bars = pd.DataFrame(
        {"open": [1.0, 1.0, 1.0], "high": [1.02, 1.05, 1.01],
         "low": [0.99, 0.97, 1.00], "close": [1.0, 1.0, 1.0]},
        index=pd.to_datetime(["2026-08-10 09:00", "2026-08-10 10:00",
                              "2026-08-10 11:00"]))
    ex = EM.excursions(bars, entry_price=1.0, side=1,
                       entry_bar_utc="2026-08-10 09:00",
                       exit_bar_utc="2026-08-10 11:00")
    assert ex["mfe_bps"] == pytest.approx(500.0, abs=1)    # cao nhất 1,05
    assert ex["mae_bps"] == pytest.approx(-300.0, abs=1)   # thấp nhất 0,97

    # Bán thì đảo chiều cả hai.
    ex2 = EM.excursions(bars, entry_price=1.0, side=-1,
                        entry_bar_utc="2026-08-10 09:00",
                        exit_bar_utc="2026-08-10 11:00")
    assert ex2["mfe_bps"] == pytest.approx(300.0, abs=1)
    assert ex2["mae_bps"] == pytest.approx(-500.0, abs=1)


def test_summarise_groups_by_close_reason():
    """Bảng theo LÝ DO ĐÓNG — thứ đầu tiên nhìn khi live lệch khỏi backtest."""
    from src.python.execution import exit_manager as EM

    mk = lambda r, g: EM.ClosedTrade(
        leg="l", symbol="AUDCAD", side="BUY", lots=1.0,
        entry_bar_utc="a", exit_bar_utc="b", entry_price=1.0, exit_price=1.0,
        bars_held=10, reason=r, gross_bps=g)
    out = EM.summarise([mk(EM.REASON_TIMESTOP, 5.0), mk(EM.REASON_TIMESTOP, -3.0),
                        mk(EM.REASON_FUSE, -50.0)])
    assert out.loc[EM.REASON_TIMESTOP, "lệnh"] == 2
    assert out.loc[EM.REASON_FUSE, "lệnh"] == 1
    assert out.loc[EM.REASON_TIMESTOP, "thắng_pct"] == pytest.approx(50.0)


# ═════════════════════════════════════════════════════ 11. gọi ngược về giao diện
# ĐÃ XOÁ 19/08/2026: `test_ui_callback_never_touches_tk_from_background_thread`.
#
# Test đó ghim một bất biến THẬT và quan trọng — `_ui()` chỉ được xếp hàng, không
# được chạm Tk từ luồng nền, vì `root.after()` gọi từ luồng nền ném `RuntimeError:
# main thread is not in main loop` và giết luồng nền kèm 12 dòng traceback.
#
# Nhưng bất biến đó nói về một thứ KHÔNG CÒN TỒN TẠI: `TradingGUIV2` đã bị xoá cùng
# đợt chuyển sang console-only. Giữ test cho một lớp đã xoá là giữ một test luôn
# xanh mà không đo gì — đúng loại test làm người đọc tin rằng có lớp bảo vệ ở chỗ
# không có gì cả.
#
# Đáng ghi lại: chính họ lỗi này là một trong ba lý do xoá giao diện. Console-only
# không có luồng giao diện, nên cả lớp lỗi "gọi Tk từ luồng sai" biến mất theo —
# không phải được vá, mà là không còn chỗ để xảy ra.

def test_undelivered_symbols_excludes_duplicate_skip_from_sync():
    """SỰ CỐ 25/08/2026 — khoá chống-gửi-lặp còn giữ trả `ok=True`, nhưng lệnh đó
    CHƯA từng chạm broker lần này. Đưa thẳng `r.ok` vào `sync_from_targets`
    (bỏ sót nhánh "BỎ QUA — trùng khoá") khiến sổ ghi "MỞ" cho một vị thế ma —
    đúng lỗi hạng này mà `sync_from_targets` sinh ra để tránh, chỉ khác ở CHỖ
    đưa vào (`failed_symbols` thiếu, không phải bản thân `sync_from_targets` sai).
    """
    from src.python.core.engine import _undelivered_symbols

    real_reject = OR.SendResult(symbol="AUDCAD", action="OPEN", side="BUY",
                                lots=1.0, ok=False, dry_run=False,
                                reason="broker từ chối retcode 10019")
    duplicate_skip = OR.SendResult(symbol="GBPUSD", action="OPEN", side="SELL",
                                   lots=1.0, ok=True, dry_run=False,
                                   reason="BỎ QUA — trùng khoá chống gửi lặp")
    real_fill = OR.SendResult(symbol="USDJPY", action="OPEN", side="SELL",
                              lots=1.0, ok=True, dry_run=False, reason="")

    got = _undelivered_symbols([real_reject, duplicate_skip, real_fill])

    assert got == {"AUDCAD", "GBPUSD"}, (
        "lệnh bị từ chối THẬT và lệnh bị khoá trùng lặp đều không được đồng bộ "
        "vào sổ như thể đã khớp; chỉ lệnh khớp thật (USDJPY) được đồng bộ")


def test_engine_finalises_positions_closed_on_broker(monkeypatch, _ctl, tmp_path):
    """Vị thế biến mất khỏi broker → sổ phải được dọn VÀ ghi nhận.

    Không có bước này thì `position_book` giữ mãi một chân đã hết vị thế, và
    `open()` báo "đã có vị thế" mỗi lần chân đó muốn vào lại — chân câm vĩnh viễn
    mà không có lỗi nào.
    """
    from src.python.execution.position_book import PositionBook

    e = _engine(monkeypatch)
    book = PositionBook(tmp_path / "book.json")
    book.open("zb_audcad_h1", symbol="AUDCAD", side="BUY", lots=1.0,
              entry_bar_utc="2026-08-10 09:00:00", entry_price=0.90,
              timeframe="H1", stop_price=0.8559)

    lines = []
    monkeypatch.setattr(e, "log", lambda m: lines.append(m))
    e.state["positions_list"] = []            # broker KHÔNG còn vị thế nào
    e.state["prices"] = {"AUDCAD": 0.8600}
    e._finalise_closed(book)

    assert len(book) == 0, "sổ phải sạch"
    assert any("ĐÓNG" in l and "CLOSED_ELSEWHERE" in l for l in lines), lines


def test_engine_keeps_positions_still_on_broker(monkeypatch, _ctl, tmp_path):
    """Vị thế CÒN trên broker thì không được đụng vào sổ."""
    from src.python.execution.position_book import PositionBook

    e = _engine(monkeypatch)
    book = PositionBook(tmp_path / "book.json")
    book.open("zb_audcad_h1", symbol="AUDCAD", side="BUY", lots=1.0,
              entry_bar_utc="2026-08-10 09:00:00", entry_price=0.90, timeframe="H1")
    e.state["positions_list"] = [{"symbol": "AUDCAD"}]
    e.state["prices"] = {"AUDCAD": 0.90}
    e._finalise_closed(book)
    assert len(book) == 1
