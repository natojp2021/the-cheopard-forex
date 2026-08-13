"""order_plan.py — ĐƯỜNG DUY NHẤT từ mục tiêu danh mục tới lệnh gửi broker.

VÌ SAO PHẢI CÓ MODULE NÀY
==========================
Trước 14/08/2026 các mảnh đã có đủ nhưng KHÔNG ai nối chúng, và mỗi mảnh có một
khái niệm "vị thế" riêng:

    portfolio.live_targets()        quyết định của chân      (3/27 chân)
    portfolio_sizing.size_portfolio tỷ trọng → lot           (không biết vị thế thật)
    ftmo_leverage_policy.decide()   đòn bẩy                  (không ai gọi)
    disaster_stop                   cầu chì                  (không ai gọi)
    portfolio_risk.snapshot()       vị thế thật              (không ai gọi)

Nối tay ở nơi gọi là cách mỗi lần gọi lại nối hơi khác nhau. Hệ XAUUSD học đúng bài
này: `position_sizing.py` của nó tồn tại vì cùng một khối 8 dòng tính lot từng bị
nhân bản trong cả 8 file chiến lược, và một lần sửa chỉ áp vào 7/8 file đã gây lỗi
Hard-TP. Module này là bản tương đương cho tầng DANH MỤC.

BẢY BƯỚC, THỨ TỰ CỐ ĐỊNH
=========================
    1. đọc vị thế THẬT từ broker          `portfolio_risk.snapshot()`
    2. cổng an toàn hợp nhất              `entry_gate.EntryGate.evaluate()`
    3. đòn bẩy theo đệm equity            `ftmo_leverage_policy.decide()`
    4. gộp 27 chân → tỷ trọng RÒNG        `portfolio.target_weights()`
    5. tỷ trọng → LOT                     `portfolio_sizing.weights_to_lots()`
    6. so với vị thế thật → LỆNH CHÊNH    ở đây
    7. gắn cầu chì cho mọi vị thế mới     `disaster_stop.compute_book()`

Thứ tự không đảo được. Cụ thể: bước 1 phải trước bước 2 vì cổng cần biết có bao
nhiêu vị thế thiếu cầu chì; bước 3 phải trước bước 5 vì lot tỷ lệ thẳng với đòn bẩy;
bước 6 phải sau bước 5 vì "chênh lệch" chỉ có nghĩa khi hai bên cùng đơn vị lot.

MODULE NÀY KHÔNG GỬI LỆNH
==========================
Nó trả về một KẾ HOẠCH đọc được và kiểm được. Việc gửi thuộc về tầng bridge. Tách
như vậy để kế hoạch test được mà không cần broker, và để người vận hành đọc được
"hệ định làm gì" trước khi cho phép — đúng giai đoạn FORWARD_TEST hiện tại.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.python.execution import disaster_stop as DS
from src.python.execution import ftmo_leverage_policy as POL
from src.python.execution import portfolio_risk as PR
from src.python.execution import portfolio_sizing as PS
from src.python.execution.entry_gate import EntryGate, GateResult
from src.python.execution.position_book import PositionBook
from src.python.shared import asset_profile as AP

# Chênh lệch lot nhỏ hơn ngần này thì KHÔNG gửi lệnh. Mỗi lệnh trả một lượt spread
# đầy đủ, nên đuổi theo sai số làm tròn là trả phí để không đổi được gì.
MIN_TRADE_LOTS = 0.01

# Chênh lệch tỷ trọng nhỏ hơn ngần này cũng bỏ qua — cùng lý do, nhưng chặn sớm hơn
# một bước để khỏi phải quy đổi lot cho những thứ chắc chắn sẽ bị bỏ.
MIN_WEIGHT_DELTA = 0.005


@dataclass(frozen=True)
class OrderAction:
    """Một việc cần làm trên MỘT công cụ."""
    symbol: str
    action: str                 # OPEN | CLOSE | INCREASE | REDUCE | REVERSE | HOLD
    side: str                   # BUY | SELL | FLAT
    lots: float                 # SỐ LOT PHẢI GIAO DỊCH, luôn dương
    current_lots: float         # đang giữ (dương = mua, âm = bán)
    target_lots: float          # muốn giữ
    target_weight: float
    stop_price: Optional[float] = None
    reason: str = ""
    # Notional USD của phần MỤC TIÊU. Tính Ở ĐÂY vì đây là chỗ DUY NHẤT có bảng
    # giá đầy đủ: `usd_per_quote` của một cross cần tỷ giá của đồng định giá, mà
    # tầng gửi lệnh chỉ thấy giá của chính công cụ đang gửi. Bản trước để tầng đó
    # tự tính và nó luôn ra 0 — một ô trống im lặng trong mọi bản ghi lệnh.
    notional_usd: float = 0.0

    def explain(self) -> str:
        return (f"{self.symbol:8} {self.action:9} {self.side:4} {self.lots:6.2f} lot "
                f"(đang {self.current_lots:+.2f} → muốn {self.target_lots:+.2f})"
                + (f" · cầu chì {self.stop_price:.5f}" if self.stop_price else "")
                + (f" · {self.reason}" if self.reason else ""))


@dataclass
class OrderPlan:
    """Kế hoạch đầy đủ cho một chu kỳ tái cân bằng."""
    allowed: bool
    gate: GateResult
    leverage: float
    leverage_reason: str = ""
    actions: List[OrderAction] = field(default_factory=list)
    risk: Optional[PR.RiskSnapshot] = None
    gross_notional_usd: float = 0.0
    # Mang theo để tầng gửi lệnh không phải hỏi lại engine — thư vào lệnh cần cả
    # hai, và một tham số đi kèm kế hoạch thì không bao giờ lệch với kế hoạch.
    equity_usd: float = 0.0
    asof: str = ""
    notes: List[str] = field(default_factory=list)

    @property
    def to_trade(self) -> List[OrderAction]:
        return [a for a in self.actions if a.action != "HOLD"]

    def explain(self) -> str:
        head = (f"đòn bẩy {self.leverage:.2f}x · {len(self.to_trade)}/"
                f"{len(self.actions)} công cụ cần giao dịch · notional "
                f"${self.gross_notional_usd:,.0f}")
        if not self.allowed:
            return f"KHÔNG THỰC THI — {self.gate.explain()}\n  ({head})"
        lines = [head] + [f"  {a.explain()}" for a in self.to_trade]
        return "\n".join(lines + [f"  ghi chú: {n}" for n in self.notes])


def _classify(current: float, target: float) -> str:
    """Đặt tên cho việc phải làm. Tên phải phân biệt được ĐẢO CHIỀU với TĂNG THÊM.

    Đảo chiều là hai lệnh (đóng rồi mở ngược) chứ không phải một, và nếu gọi nhầm nó
    là "tăng thêm" thì tầng bridge sẽ gửi một lệnh sai chiều với khối lượng sai.
    """
    if abs(target) < 1e-9:
        return "CLOSE" if abs(current) >= MIN_TRADE_LOTS else "HOLD"
    if abs(current) < 1e-9:
        return "OPEN"
    if current * target < 0:
        return "REVERSE"
    return "INCREASE" if abs(target) > abs(current) else "REDUCE"


def build(targets, *, equity_usd: float, prices: Dict[str, float],
          mt5=None, positions: Optional[Dict[str, int]] = None,
          daily_vol_bps: float = 9.33,
          worst_day_bps: float = 79.4,
          day_start_balance: Optional[float] = None,
          book: Optional["PositionBook"] = None,
          reconciliation_done: Optional[bool] = None,
          trading_enabled: Optional[bool] = None,
          ftmo_entries_allowed: Optional[bool] = None,
          ftmo_reason: str = "",
          atr_daily_pct: Optional[Dict[str, float]] = None,
          leverage_override: Optional[float] = None) -> OrderPlan:
    """Dựng kế hoạch cho chu kỳ hiện tại. KHÔNG gửi lệnh.

    `targets` là `PortfolioTargets` từ `portfolio.live_targets()`.
    `positions` là chiều đang giữ của TỪNG CHÂN (+1/−1/0) — cần cho chân trả `HOLD`;
    khác với vị thế theo CÔNG CỤ mà `mt5` trả về.

    `book` là `PositionBook` — SỔ VỊ THẾ bền vững. Truyền vào thì hàm tự đối soát sổ
    với broker và tự suy ra `reconciliation_done`; bỏ trống thì phải truyền tay, và
    `None` nghĩa là CHƯA BIẾT → cổng chặn (fail-closed).

    `trading_enabled=None` thì đọc từ `trading_control` (công tắc bền vững trên đĩa).
    Trước 14/08/2026 hai tham số này không có ai sinh ra giá trị — cổng chờ một thứ
    không tồn tại và bên gọi phải tự bịa `True`.

    `mt5=None` thì bỏ qua bước đọc vị thế thật và coi sổ đang trống — chỉ dùng để
    xem trước kế hoạch.
    """
    from src.python.strategies import portfolio as PF

    notes: List[str] = []

    # ── 0. công tắc thủ công — đọc từ đĩa, không nhận mặc định True
    if trading_enabled is None:
        from src.python.execution import trading_control
        ctl = trading_control.read()
        trading_enabled = ctl.enabled
        if not ctl.enabled:
            notes.append(ctl.explain())

    # ── 1. vị thế THẬT + ĐỐI SOÁT sổ với broker
    risk: Optional[PR.RiskSnapshot] = None
    real: Dict[str, float] = {}
    unprotected: Optional[int] = 0
    if mt5 is not None:
        risk = PR.snapshot(mt5, equity_usd)
        for p in risk.positions:
            real[p.symbol] = real.get(p.symbol, 0.0) + (
                p.lots if p.side == "BUY" else -p.lots)
        unprotected = len(risk.unprotected)
        notes.append(risk.explain().splitlines()[0])

        if book is not None:
            rec = book.reconcile(mt5.positions_get() or [])
            notes.append(rec.explain().splitlines()[0])
            if reconciliation_done is None:
                reconciliation_done = rec.ok
            if not rec.ok:
                notes.extend(rec.explain().splitlines()[1:])
            # Chiều đang giữ của từng CHÂN lấy từ sổ, không suy từ vị thế broker:
            # một công cụ có thể do nhiều chân cùng giữ (AUDCAD có ba chân), nên
            # vị thế theo công cụ KHÔNG quy ngược ra được chiều của từng chân.
            if positions is None:
                positions = book.sides()

    # ── 2b. phán quyết của TẦNG LUẬT FTMO
    #
    # `ftmo_entries_allowed` mặc định `True` cho tới 15/08/2026, và không bên gọi nào
    # truyền giá trị — nghĩa là `ftmo.evaluate().block_reason` CHƯA BAO GIỜ được hỏi
    # trên đường live, dù `entry_gate` có sẵn nhánh đọc nó. Một cổng mặc định MỞ là
    # một cổng không tồn tại.
    #
    # Nay mặc định là `None` = CHƯA BIẾT, và hàm tự đi hỏi `ftmo.evaluate()`. Hỏi
    # không được thì fail-CLOSED: không đánh giá được luật thì coi như luật cấm.
    if ftmo_entries_allowed is None:
        try:
            from src.python.core.infra import ftmo as _ftmo

            ftmo_reason = ftmo_reason or _ftmo.evaluate(
                float(equity_usd),
                balance=float(day_start_balance or equity_usd) or None).block_reason
            ftmo_entries_allowed = not ftmo_reason
        except Exception as exc:
            ftmo_entries_allowed = False
            ftmo_reason = (f"không đánh giá được trạng thái FTMO "
                           f"({type(exc).__name__}: {exc}) — fail-closed")
        notes.append(f"tầng FTMO: {'THÔNG' if ftmo_entries_allowed else ftmo_reason}")

    # ── 3. đòn bẩy (tính trước cổng vì cổng cần biết chính sách có HALT không)
    dec = POL.decide(equity_usd, float(day_start_balance or equity_usd),
                     daily_vol_bps, worst_day_bps=worst_day_bps)
    leverage = float(leverage_override if leverage_override is not None
                     else dec.leverage)

    # ── 2. cổng an toàn hợp nhất
    gate = EntryGate.evaluate(
        reconciliation_done=reconciliation_done,
        trading_enabled=trading_enabled,
        ftmo_entries_allowed=ftmo_entries_allowed,
        leverage=leverage,
        unprotected_positions=unprotected,
        regime_crisis="CRISIS" in str(getattr(targets, "regime", "")),
        ftmo_reason=ftmo_reason)

    # ── 4. gộp 27 chân → tỷ trọng RÒNG
    weights = PF.target_weights(targets, positions=positions)
    weights = weights[weights.abs() >= MIN_WEIGHT_DELTA]

    # ── 5. tỷ trọng → LOT
    orders = PS.weights_to_lots(weights, prices, equity_usd=equity_usd,
                                leverage=leverage, mt5_module=mt5)
    want: Dict[str, float] = {
        o.symbol: (o.lots if o.direction == "BUY"
                   else -o.lots if o.direction == "SELL" else 0.0)
        for o in orders}
    w_by_symbol = {o.symbol: o.weight for o in orders}

    # ── 7. cầu chì cho mọi công cụ có mục tiêu (tính trước để gắn vào lệnh mở)
    stops = DS.compute_book(weights, prices, leverage=leverage,
                            equity_usd=equity_usd, atr_daily_pct=atr_daily_pct)

    # ── 6. chênh lệch giữa THẬT và MUỐN
    actions: List[OrderAction] = []
    gross = 0.0
    for symbol in sorted(set(real) | set(want)):
        cur = float(real.get(symbol, 0.0))
        tgt = float(want.get(symbol, 0.0))
        kind = _classify(cur, tgt)
        delta = abs(tgt - cur)
        if kind == "HOLD" or delta < MIN_TRADE_LOTS:
            kind, delta = "HOLD", 0.0
        side = ("FLAT" if kind == "HOLD"
                else "BUY" if tgt > cur else "SELL")
        st = stops.get(symbol)
        reason = ""
        if st is not None and not st.ok:
            # Cầu chì không đặt được thì KHÔNG mở vị thế mới — mở mà không có cầu
            # chì là tái lập đúng lỗ hổng module `disaster_stop` sinh ra để bịt.
            if kind in ("OPEN", "INCREASE", "REVERSE"):
                kind, side, delta = "HOLD", "FLAT", 0.0
                reason = f"CHẶN — cầu chì không hợp lệ: {st.reason}"
            else:
                reason = f"cầu chì: {st.reason}"
        px = float(prices.get(symbol, 0.0) or 0.0)
        notional = 0.0
        if px > 0:
            notional = abs(tgt) * float(PS.lot_notional_usd(
                symbol, px, AP.usd_per_quote(symbol, prices)))
            gross += notional
        actions.append(OrderAction(
            symbol=symbol, action=kind, side=side, lots=round(delta, 2),
            current_lots=round(cur, 2), target_lots=round(tgt, 2),
            target_weight=round(float(w_by_symbol.get(symbol, 0.0)), 5),
            stop_price=(st.stop_price if st is not None and st.ok else None),
            reason=reason, notional_usd=round(notional, 2)))

    if not gate.allowed:
        # Kế hoạch vẫn được dựng đầy đủ để người vận hành ĐỌC ĐƯỢC hệ định làm gì,
        # nhưng `allowed=False` và không lệnh nào được phép gửi.
        notes.append("kế hoạch dựng để XEM, cổng an toàn đang chặn thực thi")

    return OrderPlan(allowed=gate.allowed, gate=gate, leverage=round(leverage, 4),
                     leverage_reason=dec.reason, actions=actions, risk=risk,
                     gross_notional_usd=round(gross, 2), notes=notes,
                     equity_usd=float(equity_usd),
                     asof=str(getattr(targets, "asof", "") or ""))
