"""order_plan.py — ĐƯỜNG DUY NHẤT từ mục tiêu danh mục tới lệnh gửi broker.

VÌ SAO PHẢI CÓ MODULE NÀY
==========================
Các mảnh dưới đây đều tự chạy được, nhưng mỗi mảnh có một khái niệm "vị thế" riêng:

    portfolio.live_targets()        quyết định của chân
    risk_sizing.lots_for_risk       SL + %equity → lot       (không biết vị thế thật)
    ftmo_leverage_policy.decide()   đòn bẩy                  (không ai gọi)
    disaster_stop                   cầu chì                  (không ai gọi)
    portfolio_risk.snapshot()       vị thế thật              (không ai gọi)

Nối tay ở nơi gọi là cách để mỗi lần gọi lại nối hơi khác nhau, và để một lần sửa
chỉ áp vào một phần các chỗ gọi. Module này là điểm nối DUY NHẤT.

BẢY BƯỚC, THỨ TỰ CỐ ĐỊNH
=========================
    1. đọc vị thế THẬT từ broker          `portfolio_risk.snapshot()`
    2. cổng an toàn hợp nhất              `entry_gate.EntryGate.evaluate()`
    3. đòn bẩy theo đệm equity            `ftmo_leverage_policy.decide()`
    4. tỷ trọng RÒNG (chỉ để báo cáo)     `portfolio.target_weights()`
    5. SL + % equity → LOT                `risk_sizing.size_book()`
    6. trần rủi ro NGÀY và ĐỒNG TIỀN      ở đây
    7. so với vị thế thật → LỆNH CHÊNH    ở đây
    8. cầu chì dự phòng cho vị thế mới    `disaster_stop.compute_book()`

Thứ tự không đảo được. Cụ thể: bước 1 phải trước bước 2 vì cổng cần biết có bao
nhiêu vị thế đang thiếu dừng lỗ; bước 3 phải trước bước 6 vì cổng chặn khi chính sách
đòn bẩy trả 0; bước 6 phải sau bước 5 vì "chênh lệch" chỉ có nghĩa khi hai bên cùng
đơn vị lot.

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
from src.python.execution import risk_sizing as RS
from src.python.execution.entry_gate import EntryGate, GateResult
from src.python.execution.position_book import PositionBook
from src.python.core.infra import symbol_spec as SS
from src.python.shared import asset_profile as AP

# Chênh lệch lot nhỏ hơn ngần này thì KHÔNG gửi lệnh. Mỗi lệnh trả một lượt spread
# đầy đủ, nên đuổi theo sai số làm tròn là trả phí để không đổi được gì.
MIN_TRADE_LOTS = 0.01

# Chênh lệch tỷ trọng nhỏ hơn ngần này cũng bỏ qua — cùng lý do, nhưng chặn sớm hơn
# một bước để khỏi phải quy đổi lot cho những thứ chắc chắn sẽ bị bỏ.
MIN_WEIGHT_DELTA = 0.005

# Trần rủi ro MỞ ĐỒNG THỜI, % equity. FTMO chốt mốc ngày ở 5,00% và tính CẢ lãi/lỗ
# chưa đóng, nên trần nội bộ phải nằm DƯỚI mốc đó với biên: 4,00% để một ngày xấu
# nhất (mọi SL cùng chạm) vẫn còn 1,00 điểm % đệm cho trượt giá, spread giãn và gap
# cuối tuần. Con số nội bộ tự đặt, không phải luật FTMO.
#
# Rổ hiện tại: 3 công cụ x 0,60%/lệnh = 1,80% rủi ro mở tối đa — còn cách trần rất
# xa. Trần này chỉ kích hoạt nếu rổ được mở rộng hoặc `risk_pct_per_trade` bị nâng.
_DAILY_RISK_CAP_PCT = 4.0

# Trần rủi ro dồn vào MỘT ĐỒNG TIỀN, % equity.
#
# VÌ SAO CẦN RIÊNG MỘT TRẦN CHO ĐỒNG TIỀN: rổ hiện tại là ba cặp và CẢ BA đều có chân
# USD. Ba lệnh cùng chiều USD không phải ba cược độc lập — đó là MỘT cược vào USD với
# cỡ gấp ba, và `_DAILY_RISK_CAP_PCT` không nhìn thấy điều đó vì nó chỉ cộng rủi ro
# theo CÔNG CỤ.
#
# 1,50% cho phép hai lệnh cùng chiều USD ở mức 0,60%/lệnh, chặn lệnh thứ ba. Đây là
# con số nội bộ tự đặt: nó nói "được phép tập trung, không được phép dồn hết".
_CURRENCY_RISK_CAP_PCT = 1.5


def _registry_risk_pct() -> float:
    """% equity rủi ro mỗi lệnh, đọc từ SSOT. Thiếu khai báo thì NỔ, không đoán.

    Đoán một giá trị mặc định ở đây là cách để một hôm nào đó danh mục chạy với mức
    rủi ro mà không ai chọn — đúng họ lỗi "trả một con số trông hợp lý".
    """
    from src.python.strategies import registry as REG

    try:
        return float(REG.PORTFOLIO["risk_pct_per_trade"])
    except (KeyError, TypeError, ValueError) as exc:
        raise KeyError(
            "registry.PORTFOLIO thiếu `risk_pct_per_trade` — chiến lược có SL cứng "
            "BẮT BUỘC khai mức rủi ro mỗi lệnh ở SSOT, không nhận mặc định."
        ) from exc


def _touches(symbol: str, currency: str) -> bool:
    prof = AP.get(symbol)
    return currency in (prof.base, prof.quote)


def _currency_overflow(want: Dict[str, float], risk_book: Dict[str, object],
                       equity_usd: float) -> Optional[tuple]:
    """Đồng tiền nào đang gánh rủi ro vượt trần. Trả (đồng tiền, % equity) hoặc None.

    Một vị thế EURUSD mua mang EUR long + USD short, nên rủi ro của nó tính vào CẢ
    HAI đồng. Chỉ cộng theo công cụ thì ba cặp cùng chân USD trông như ba cược độc
    lập, trong khi thực tế là một cược gấp ba.
    """
    if not (equity_usd > 0) or not want:
        return None
    load: Dict[str, float] = {}
    for sym in want:
        rl = risk_book.get(sym)
        r = float(getattr(rl, "risk_usd", 0.0) or 0.0)
        if r <= 0:
            continue
        prof = AP.get(sym)
        for ccy in (prof.base, prof.quote):
            load[ccy] = load.get(ccy, 0.0) + r
    if not load:
        return None
    ccy, usd = max(load.items(), key=lambda kv: kv[1])
    pct = 100.0 * usd / float(equity_usd)
    return (ccy, pct) if pct > _CURRENCY_RISK_CAP_PCT else None


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
    # Hợp đồng giữa chiến lược và tầng gửi lệnh.
    #
    # `stop_price` mang DỪNG LỖ CHIẾN LƯỢC khi chiến lược khai nó, còn `fuse_price`
    # giữ CẦU CHÌ của `disaster_stop` ở một trường riêng. Lẫn hai thứ là chuyện
    # nghiêm trọng: cầu chì 8xATR trên EURUSD là ~80 pip, tức gần BA LẦN rủi ro dự
    # kiến của một lệnh.
    #
    # `take_profit` là mức mà `order_router` gửi làm `tp`. MỘT mức, vì server broker
    # giữ được đúng một `tp` cho một vị thế. Bỏ trống nó nghĩa là lệnh đi mà không có
    # lối thoát THẮNG nào.
    take_profit: Optional[float] = None
    fuse_price: Optional[float] = None
    risk_usd: float = 0.0
    # Notional USD của phần MỤC TIÊU. Tính Ở ĐÂY vì đây là chỗ DUY NHẤT có bảng
    # giá đầy đủ: `usd_per_quote` của một cross cần tỷ giá của đồng định giá, mà
    # tầng gửi lệnh chỉ thấy giá của chính công cụ đang gửi. Bản trước để tầng đó
    # tự tính và nó luôn ra 0 — một ô trống im lặng trong mọi bản ghi lệnh.
    notional_usd: float = 0.0

    def explain(self) -> str:
        return (f"{self.symbol:8} {self.action:9} {self.side:4} {self.lots:6.2f} lot "
                f"(đang {self.current_lots:+.2f} → muốn {self.target_lots:+.2f})"
                + (f" · SL {self.stop_price:.5f}" if self.stop_price else "")
                + (f" · TP {self.take_profit:.5f}" if self.take_profit else "")
                + (f" · rủi ro ${self.risk_usd:,.0f}" if self.risk_usd else "")
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


def min_trade_lots(symbol: str, mt5_module=None) -> float:
    """Lot NHỎ NHẤT broker chịu nhận cho `symbol`. KHÔNG phải hằng số toàn cục.

    LỖI 04:28 NGÀY 21/08/2026 — MỘT CÔNG CỤ CÁ BIỆT LÀM HỎNG CẢ LƯỢT GỬI
    ====================================================================
        [LỖI] <công cụ>  INCREASE  SELL  0.02 lot ... retcode 10014 Invalid volume
        [CIRCUIT BREAKER OPEN] FATAL NON-RETRIABLE ERROR: retcode=10014

    Đo trên chính tài khoản: một công cụ có `volume_min = 0.1`, trong khi phần còn
    lại là 0,01. `MIN_TRADE_LOTS = 0.01` là hằng số TOÀN CỤC, nên chênh lệch 0,02
    lot của nó qua được cổng nội bộ rồi bị broker từ chối.

    Hậu quả không dừng ở một lệnh hỏng: `10014` bị xếp vào nhóm lỗi CHẾT NGƯỜI
    không được thử lại, nên nó mở CẦU CHÌ và chặn nốt những lệnh còn lại trong
    cùng lượt. Một công cụ có bậc lot khác thường làm đứng cả danh mục, lặp lại
    mỗi chu kỳ.

    Ngưỡng đúng là `max(volume_min, volume_step)`: dưới `volume_min` broker từ
    chối, và dưới `volume_step` thì làm tròn về 0.
    """
    try:
        spec = SS.resolve(symbol, mt5_module=mt5_module)
        return max(float(spec.volume_min), float(spec.volume_step))
    except Exception:
        # Không đọc được đặc tả thì dùng ngưỡng CŨ. Đoán cao hơn sẽ bỏ lỡ lệnh
        # thật; đoán thấp hơn chỉ lặp lại đúng lỗi này.
        return MIN_TRADE_LOTS


def _classify(current: float, target: float, min_lots: float = MIN_TRADE_LOTS) -> str:
    """Đặt tên cho việc phải làm. Tên phải phân biệt được ĐẢO CHIỀU với TĂNG THÊM.

    Đảo chiều là hai lệnh (đóng rồi mở ngược) chứ không phải một, và nếu gọi nhầm nó
    là "tăng thêm" thì tầng bridge sẽ gửi một lệnh sai chiều với khối lượng sai.
    """
    if abs(target) < 1e-9:
        return "CLOSE" if abs(current) >= min_lots else "HOLD"
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
          leverage_override: Optional[float] = None,
          risk_pct_per_trade: Optional[float] = None,
          extra_blocks: Optional[List[str]] = None) -> OrderPlan:
    """Dựng kế hoạch cho chu kỳ hiện tại. KHÔNG gửi lệnh.

    `targets` là `PortfolioTargets` từ `portfolio.live_targets()`, và nó PHẢI
    mang được `stop_targets()` — xem bước 5.
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

    `extra_blocks` là danh sách lý do chặn mà BÊN GỌI đã phát hiện, gộp thẳng vào
    cổng an toàn. Mặc định rỗng để mọi script gọi hàm này không đổi hành vi; đường
    LIVE (`engine._build_plan`) truyền vào lý do "dữ liệu ôi".
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
            from src.python.execution.order_router import MAGIC_BASE

            # Xem ghi chú cùng nội dung ở `engine._reconcile_on_start()`: `or []`
            # ở đây MỞ cổng lệnh đúng lúc không đọc được tài khoản, và thiếu
            # `own_magic_base` làm mọi vị thế của chân xếp hạng thành mồ côi.
            raw = mt5.positions_get()
            if raw is None:
                notes.append("KHÔNG đọc được vị thế broker (positions_get trả "
                             "None) — đối soát bỏ qua, cổng giữ fail-closed")
                reconciliation_done = False
                rec = None
            else:
                rec = book.reconcile(raw, own_magic_base=MAGIC_BASE)
                notes.append(rec.explain().splitlines()[0])
            if rec is not None:
                if reconciliation_done is None:
                    reconciliation_done = rec.ok
                if not rec.ok:
                    notes.extend(rec.explain().splitlines()[1:])
            # Chiều đang giữ của từng CHÂN lấy từ sổ, không suy từ vị thế broker:
            # một công cụ có thể do nhiều chân cùng giữ, nên
            # vị thế theo công cụ KHÔNG quy ngược ra được chiều của từng chân.
            #
            # Chạy KỂ CẢ khi đối soát bỏ qua: `positions` để None sẽ làm các phép
            # tính phía dưới mất đầu vào. Cổng đã fail-closed nên không có lệnh
            # nào ra, nhưng bản kế hoạch vẫn phải mô tả đúng trạng thái đang giữ.
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
        ftmo_reason=ftmo_reason,
        # Lý do chặn do BÊN GỌI phát hiện — hiện dùng cho cổng dữ liệu ôi mà
        # `engine._build_plan` đo được (xem `mt5_bars.stale_symbols`). Đi qua
        # `extra_blocks` thay vì một `return` sớm ở engine là CÓ CHỦ ĐÍCH: cổng
        # chặn làm `allowed=False`, và `order_router.route()` vẫn cho lệnh GIẢM
        # phơi nhiễm đi qua — tức đường THOÁT không bị khoá. Một `return` sớm sẽ
        # lặp lại đúng lỗi đã sửa ngày 15/08/2026.
        extra_blocks=list(extra_blocks or []))

    # ── 4. gộp các chân → tỷ trọng RÒNG
    weights = PF.target_weights(targets, positions=positions)
    weights = weights[weights.abs() >= MIN_WEIGHT_DELTA]

    # ── 5. SL + % equity → LOT. ĐƯỜNG SIZING DUY NHẤT kể từ 25/08/2026.
    #
    # Chiến lược khai SL theo giá, nên rủi ro mỗi lệnh là số ĐÃ BIẾT TRƯỚC thay vì
    # một hàm của biến động và đòn bẩy. Xem docstring `risk_sizing`.
    #
    # Chiến lược KHÔNG khai được SL = KHÔNG biết rủi ro = KHÔNG mở vị thế. Fail-closed;
    # đường THOÁT vẫn mở vì `want` rỗng làm mọi vị thế đang giữ thành CLOSE.
    stop_targets: Dict[str, Dict[str, float]] = {}
    fn = getattr(PF, "stop_targets", None)
    if not callable(fn):
        raise AttributeError(
            "`strategies.portfolio` thiếu `stop_targets()`. Từ 25/08/2026 mọi chiến "
            "lược PHẢI khai SL theo giá — đường sizing theo tỷ trọng đã bị xoá, nên "
            "không có nhánh dự phòng nào để chạy.")
    try:
        stop_targets = fn(targets) or {}
    except Exception as exc:                          # noqa: BLE001
        stop_targets = {}
        notes.append(f"KHÔNG đọc được stop_targets ({type(exc).__name__}: {exc}) — "
                     f"không mở vị thế mới lượt này")

    risk_pct = float(risk_pct_per_trade if risk_pct_per_trade is not None
                     else _registry_risk_pct())
    mins = {s: min_trade_lots(s, mt5) for s in stop_targets}
    risk_book = RS.size_book(stop_targets, equity_usd=equity_usd,
                             risk_pct=risk_pct, prices=prices,
                             min_lots_by_symbol=mins)
    want: Dict[str, float] = {}
    for sym, t in stop_targets.items():
        rl = risk_book[sym]
        if not rl.ok:
            notes.append(rl.explain())
            continue
        want[sym] = rl.lots * (1.0 if float(t.get("side", 0)) > 0 else -1.0)
    w_by_symbol = {s: float(weights.get(s, 0.0)) for s in want}

    total_risk = RS.total_risk_pct(risk_book, equity_usd)
    if stop_targets:
        notes.append(f"rủi ro MỞ nếu mọi SL cùng chạm: {total_risk:.2f}% equity "
                     f"({len(want)} lệnh x {risk_pct:.2f}%) — mốc ngày FTMO 5,00%")

    # ── TẦNG PHỐI HỢP DANH MỤC: rủi ro dồn vào MỘT đồng tiền.
    #
    # Bước này KHÔNG thay `_DAILY_RISK_CAP_PCT`: cái đó cộng theo công cụ, cái này
    # cộng theo ĐỒNG TIỀN. Một rổ ba cặp cùng chân USD có thể qua cổng thứ nhất mà
    # vẫn là một cược duy nhất gấp ba lần vào USD.
    #
    # Bỏ lệnh có rủi ro NHỎ NHẤT trước, cho tới khi mọi đồng tiền dưới trần. Bỏ hết
    # (như cổng ngày) sẽ chặn cả những lệnh không góp phần vào chỗ tập trung.
    ccy_over = _currency_overflow(want, risk_book, equity_usd)
    while ccy_over and want:
        ccy, load = ccy_over
        drop = min((s for s in want if _touches(s, ccy)),
                   key=lambda s: getattr(risk_book.get(s), "risk_usd", 0.0),
                   default=None)
        if drop is None:
            break
        notes.append(f"BỎ {drop} — rủi ro dồn vào {ccy} là {load:.2f}% equity, "
                     f"vượt trần {_CURRENCY_RISK_CAP_PCT:.2f}%")
        want.pop(drop, None)
        ccy_over = _currency_overflow(want, risk_book, equity_usd)
    # Con số mà danh mục cũ KHÔNG BIẾT TRƯỚC. Có SL cứng thì rủi ro ngày là phép
    # CỘNG, nên chặn được TRƯỚC khi gửi thay vì ước lượng từ biến động lịch sử.
    if total_risk > _DAILY_RISK_CAP_PCT:
        want = {}
        notes.append(f"CHẶN — tổng rủi ro mở {total_risk:.2f}% vượt trần nội bộ "
                     f"{_DAILY_RISK_CAP_PCT:.2f}%/ngày")

    # ── 7. cầu chì cho mọi công cụ có mục tiêu (tính trước để gắn vào lệnh mở)
    stops = DS.compute_book(weights, prices, leverage=leverage,
                            equity_usd=equity_usd, atr_daily_pct=atr_daily_pct)

    # ── 6. chênh lệch giữa THẬT và MUỐN
    actions: List[OrderAction] = []
    gross = 0.0
    for symbol in sorted(set(real) | set(want)):
        cur = float(real.get(symbol, 0.0))
        tgt = float(want.get(symbol, 0.0))
        min_lots = min_trade_lots(symbol, mt5)
        kind = _classify(cur, tgt, min_lots)
        delta = abs(tgt - cur)
        too_small = delta < min_lots
        if kind == "HOLD" or too_small:
            kind, delta = "HOLD", 0.0
        side = ("FLAT" if kind == "HOLD"
                else "BUY" if tgt > cur else "SELL")
        st = stops.get(symbol)
        tgt_stop = stop_targets.get(symbol) if stop_targets else None
        reason = ""
        if too_small and min_lots > MIN_TRADE_LOTS:
            # NÓI RA, đừng im lặng bỏ qua. Một công cụ có bậc lot thô hơn phần
            # còn lại sẽ vắng mặt khỏi danh mục một cách có hệ thống, và nếu
            # không có dòng này thì nó vắng mặt mà không ai biết vì sao.
            reason = (f"BỎ QUA — chênh lệch {delta:.2f} lot dưới mức tối thiểu "
                      f"{min_lots:.2f} của {symbol}")
        # DỪNG LỖ ĐI KÈM LỆNH MỞ — hai nguồn, và nguồn nào cai trị là do chiến lược.
        #
        #   có `tgt_stop`     SL CHIẾN LƯỢC cai trị. Cầu chì `disaster_stop` xuống
        #                     vai dự phòng (`fuse_price`) vì nó xa hơn SL 4-6 lần;
        #                     cầu chì không tính được KHÔNG chặn lệnh, vì lệnh vẫn
        #                     có SL thật đi kèm.
        #   không `tgt_stop`  CẦU CHÌ là dừng lỗ DUY NHẤT, nên nó không tính được
        #                     thì KHÔNG mở vị thế mới.
        sl_price = None
        tp_price = None
        if tgt_stop is not None:
            sl_price = float(tgt_stop.get("stop", float("nan")))
            tp_price = float(tgt_stop.get("tp", float("nan")))
            if not (tp_price > 0):
                tp_price = None
            if not (sl_price > 0):
                if kind in ("OPEN", "INCREASE", "REVERSE"):
                    kind, side, delta = "HOLD", "FLAT", 0.0
                    reason = "CHẶN — chiến lược khai SL nhưng giá SL không hợp lệ"
                sl_price = None
            elif st is not None and not st.ok:
                reason = f"cầu chì dự phòng không tính được: {st.reason}"
        elif st is not None and not st.ok:
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
            notional = abs(tgt) * float(RS.lot_notional_usd(
                symbol, px, AP.usd_per_quote(symbol, prices)))
            gross += notional
        fuse = st.stop_price if st is not None and st.ok else None
        rl = risk_book.get(symbol) if risk_book else None
        actions.append(OrderAction(
            symbol=symbol, action=kind, side=side, lots=round(delta, 2),
            current_lots=round(cur, 2), target_lots=round(tgt, 2),
            target_weight=round(float(w_by_symbol.get(symbol, 0.0)), 5),
            stop_price=(sl_price if sl_price is not None else fuse),
            take_profit=tp_price,
            fuse_price=fuse,
            risk_usd=round(float(getattr(rl, "risk_usd", 0.0)), 2),
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
