"""order_router.py — GỬI lệnh tới broker. Điểm DUY NHẤT chạm `mt5.order_send()`.

VÌ SAO KHÔNG DÙNG `core/infra/mt5_bridge.py`
============================================
`mt5_bridge` là đường THỦ CÔNG: nút đóng tay, đóng nửa, flatten all, halt. Nó xử lý
MỘT lệnh một lần theo yêu cầu của người vận hành.

Module này là đường TỰ ĐỘNG: nó nhận một KẾ HOẠCH cho cả sổ và gửi phần chênh lệch.
Hai đường tách biệt CÓ CHỦ Ý — gộp chúng nghĩa là một lần bấm tay có thể đi qua logic
tái cân bằng, và một lượt tái cân bằng có thể đi qua logic bấm tay.

BỐN BẤT BIẾN — mỗi cái đều có test khoá lại
============================================
  1. **Cổng chặn → chặn lệnh LÀM TĂNG phơi nhiễm. KHÔNG chặn đường THOÁT.**
     Kiểm ở đây chứ không tin bên gọi: một điểm chạm broker thì một chỗ kiểm.

     SỬA 15/08/2026 — trước đó `plan.allowed is False` chặn TẤT CẢ, kể cả lệnh
     ĐÓNG. Nghe thì an toàn, thực tế là lỗ hổng chết người: khi
     `ftmo_leverage_policy` trả 0 vì đệm tới sàn đã cạn (đo được: equity 95.000 với
     số dư đầu ngày 100.000 → đòn bẩy 0,00x), mục tiêu của mọi công cụ về 0 và kế
     hoạch sinh ra một loạt lệnh ĐÓNG — đúng thứ cần làm. Nhưng cổng lúc ấy cũng
     đang chặn, nên router trả về mà không gửi gì. Hệ ĐÓNG BĂNG ở đúng thời điểm
     phải thoát, và ngồi nguyên đó cho tới khi chạm sàn nội bộ 9% rồi luật 10%.

     Cổng an toàn sinh ra để ngăn hệ MỞ THÊM rủi ro khi trạng thái không rõ ràng.
     Nó chưa bao giờ có nghĩa "cấm giảm rủi ro". Nay phân loại tường minh:

         CLOSE · REDUCE · REVERSE_CLOSE   → LUÔN gửi, kể cả khi cổng chặn
         OPEN · INCREASE · REVERSE_OPEN   → chỉ gửi khi cổng cho phép

     `REVERSE` tách làm đôi theo đúng bất biến 2: nửa đóng đi qua, nửa mở bị giữ
     lại — vị thế cũ được đóng, không có vị thế mới, tức phơi nhiễm GIẢM.
  2. **ĐẢO CHIỀU là HAI lệnh.** Đóng vị thế cũ, rồi mở vị thế mới ngược chiều. Gộp
     thành một lệnh khối lượng gấp đôi là hành vi của broker netting; MT5 hedging
     sẽ mở thêm một vị thế thứ hai thay vì đảo, và sổ lệch ngay từ lệnh đầu.
  3. **DỪNG LỖ VÀ CHỐT LỜI ĐI KÈM lệnh mở.** `sl` và `tp` nằm trong chính
     `order_send`, không đặt sau
     bằng một lệnh `modify` thứ hai. Giữa hai lệnh đó là một khoảng thời gian vị thế
     nằm TRẦN, và nếu tiến trình chết đúng lúc ấy thì nó nằm trần mãi mãi — đúng lỗ
     hổng mà `disaster_stop` sinh ra để bịt.

     LƯỚI AN TOÀN thêm 24/08/2026 — `sl` ĐI KÈM vẫn là đường CHÍNH, không đổi. Nhưng
     đo được trên tài khoản thật: broker trả `retcode=10009` (DONE) mà vẫn lặng lẽ
     BỎ QUA trường `sl` — vị thế mở ra trần thật, không lỗi nào báo. `_send_one()`
     đọc lại vị thế NGAY trong cùng lệnh gọi (`_verify_stop_attached`) và gắn lại
     bằng một `TRADE_ACTION_SLTP` CHỈ KHI phát hiện thiếu — khoảng hở còn lại dưới
     một giây, so với treo tới chu kỳ `ftmo_guard` sau (đo được 90 giây, hậu quả là
     đóng sạch CẢ SỔ thay vì một vị thế). Đây là lưới CHO trường hợp đường chính
     thất bại, không phải một đường mở-rồi-modify thay thế nó.
  4. **Ghi nhật ký MỌI lệnh**, kể cả lệnh bị broker từ chối và lệnh bị bỏ qua vì
     trùng khoá. Lệnh không ghi là lệnh không truy được.
  5. **NGẮT MẠCH khi broker liên tiếp từ chối.** Sau `max_failures` lỗi, breaker
     chuyển OPEN và mọi lệnh sau đó bị chặn tại chỗ, không gửi ra sàn.

VÌ SAO PHẢI CÓ NGẮT MẠCH — nối 15/08/2026 khi `LIVE_ORDERS` chuyển mặc định sang 1
====================================================================================
Không có nó, một sự cố phía broker biến thành một vòng lặp gửi lệnh:

    kế hoạch có 23 việc → 23 lệnh bị từ chối (vd 10019 không đủ ký quỹ)
    → chu kỳ sau vẫn 23 việc đó, vì vị thế chưa mở nên "chênh lệch" không đổi
    → 23 lệnh nữa … lặp mãi

Mỗi lượt là 23 yêu cầu tới máy chủ FTMO. Broker có hạn mức số lệnh/giây, và vượt
hạn mức lặp lại là lý do bị khoá tài khoản — mất tài khoản vì lỗi kỹ thuật chứ
không phải vì thua lỗ.

Breaker phân biệt hai loại mã lỗi, và phân biệt đó mới là phần có giá trị:

    FATAL (10014 khối lượng sai · 10016 SL sai · 10019 thiếu ký quỹ · 10018 thị
           trường đóng…)  → lỗi CẤU TRÚC, thử lại bao nhiêu lần cũng hỏng. OPEN ngay.
    RETRIABLE (10004 báo giá lại · lỗi kết nối…) → sự cố tạm thời, đếm tới ngưỡng
           rồi mới OPEN, và sau `cooldown` thử lại một lệnh (HALF_OPEN).

Thử lại một lỗi FATAL là cách tự khoá tài khoản trong khi vấn đề nằm ở chỗ khác.

DRY-RUN MẶC ĐỊNH BẬT
=====================
`dry_run=True` là mặc định vì danh mục đang ở `FORWARD_TEST`. Ở chế độ này router đi
qua ĐÚNG mọi nhánh logic — dựng request, kiểm bất biến, ghi nhật ký — chỉ không gọi
`order_send`. Nhờ vậy thứ được kiểm là chính đường code sẽ chạy khi bật thật, không
phải một nhánh song song.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.python.utils.logger import log, log_error

# Độ trượt giá cho phép, tính bằng ĐIỂM broker. 20 điểm ≈ 2 pip trên cặp 5 chữ số —
# đủ rộng để lệnh khớp lúc thanh khoản bình thường, đủ hẹp để không khớp ở một mức
# giá vô lý khi sổ lệnh mỏng.
DEVIATION_POINTS = 20

# Magic number của hệ. Cố ý nằm trong một dải RIÊNG để hai bot chạy
# chung một tài khoản vẫn phân biệt được vị thế của ai — và để `position_book` không
# nhận nhầm vị thế của hệ kia là MỒ CÔI.
MAGIC_BASE = 5100000


@dataclass(frozen=True)
class SendResult:
    """Kết quả gửi MỘT lệnh."""
    symbol: str
    action: str                  # OPEN | CLOSE | INCREASE | REDUCE | REVERSE_CLOSE …
    side: str
    lots: float
    ok: bool
    dry_run: bool
    retcode: Optional[int] = None
    order_id: Optional[int] = None
    price: Optional[float] = None
    stop_price: Optional[float] = None
    idempotency_key: str = ""
    reason: str = ""

    # ── BỐI CẢNH KHỚP LỆNH, thêm 15/08/2026
    #
    # SPREAD LÚC VÀO LỆNH là trường quan trọng nhất trong nhóm này, và trước đó
    # KHÔNG sổ nào ghi. Lý do nó quan trọng với đúng hệ này: mọi số Sharpe trong
    # repo đều là SAU chi phí, và spread là lớp lớn nhất — bỏ sót một lớp đã từng
    # đảo dấu kết luận (Sharpe +0,216 sau spread+commission nhưng −0,456 sau swap).
    # Backtest có thể dùng spread ƯỚC LƯỢNG; chỉ khi ghi spread
    # THẬT ở từng lệnh mới biết ước lượng ấy sai bao nhiêu, và sai theo hướng nào.
    #
    # Không đo được thì để `None`, KHÔNG điền 0.0: 0.0 nghĩa là "spread bằng
    # không", một điều không tồn tại, và nó sẽ lặng lẽ kéo trung bình xuống.
    bid: Optional[float] = None
    ask: Optional[float] = None
    spread_price: Optional[float] = None     # ask − bid, ĐƠN VỊ GIÁ
    spread_bps: Optional[float] = None       # quy về bps để so với bảng chi phí
    slippage_price: Optional[float] = None   # giá khớp − giá dự kiến
    equity_usd: float = 0.0
    leverage: float = 0.0
    target_weight: Optional[float] = None
    notional_usd: float = 0.0
    magic: int = 0
    bar_utc: str = ""
    timeframe: str = ""
    legs: str = ""                           # chân nào nhắm vào công cụ này

    def explain(self) -> str:
        """Một dòng cho sổ log và bảng giao diện.

        Thêm SPREAD và NOTIONAL vào dòng này (15/08/2026): người vận hành đọc log
        lúc lệnh vừa đi, và hai con số đó là thứ quyết định có phải can thiệp ngay
        hay không — spread giãn bất thường là dấu hiệu vào lệnh sai thời điểm.
        """
        tag = "DRY" if self.dry_run else ("OK " if self.ok else "LỖI")
        s = (f"[{tag}] {self.symbol:8} {self.action:13} {self.side:4} "
             f"{self.lots:6.2f} lot")
        if self.price:
            s += f" @ {self.price:.5f}"
        if self.spread_bps is not None:
            s += f" · spread {self.spread_bps:.2f} bps"
        if self.notional_usd:
            s += f" · notional ${self.notional_usd:,.0f}"
        if self.stop_price:
            s += f" · SL {self.stop_price:.5f}"
        if self.retcode is not None:
            s += f" · retcode {self.retcode}"
        if self.reason:
            s += f" · {self.reason}"
        return s


@dataclass
class RouteResult:
    sent: List[SendResult] = field(default_factory=list)
    skipped: List[SendResult] = field(default_factory=list)
    dry_run: bool = True
    blocked_reason: str = ""

    @property
    def ok(self) -> bool:
        return not self.blocked_reason and all(r.ok for r in self.sent)

    def explain(self) -> str:
        if self.blocked_reason:
            return f"KHÔNG GỬI LỆNH NÀO — {self.blocked_reason}"
        head = (f"{'DRY-RUN — ' if self.dry_run else ''}{len(self.sent)} lệnh gửi · "
                f"{len(self.skipped)} bỏ qua")
        return "\n".join([head] + [f"  {r.explain()}" for r in self.sent + self.skipped])


def magic_for(leg: str) -> int:
    """Magic number tất định cho một chân. Cùng chân luôn cho cùng số.

    Suy từ tên chứ không gán tay: mỗi lần gán tay là một cơ hội gán trùng, và magic
    trùng nghĩa là hai chân nhận nhầm vị thế của nhau.
    """
    h = int(hashlib.sha1(leg.encode("utf-8")).hexdigest()[:6], 16)
    return MAGIC_BASE + (h % 90000)


def idempotency_key(symbol: str, action: str, bar_utc: str) -> str:
    """Khoá chống gửi trùng: MỘT công cụ, MỘT việc, MỘT nến — gửi đúng một lần.

    Gồm cả `bar_utc` vì cùng một việc trên cùng công cụ ở nến SAU là một lệnh khác
    hoàn toàn hợp lệ. Thiếu nó thì hệ chỉ vào lệnh được đúng một lần rồi câm.
    """
    raw = f"{symbol}|{action}|{bar_utc}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


_claims_restored = False


def _osm():
    """`OrderStateMachine`, hoặc `None` nếu không nạp được.

    Cùng lý do fail-soft như `_make_breaker`: module này import `core.config` →
    `MetaTrader5`, nên trên máy không cài thư viện thì không nạp được. Không có
    MT5 thì cũng không có `order_send` nào để mà chống trùng.
    """
    try:
        from src.python.core.broker.order_state_machine import OrderStateMachine

        return OrderStateMachine
    except Exception as exc:
        log_error(f"router: KHÔNG nạp được order_state_machine ({type(exc).__name__}) "
                  f"— chống gửi trùng chỉ còn trong BỘ NHỚ của tiến trình này")
        return None


def _restore_claims_once() -> None:
    """Nạp lại khoá chống trùng TỪ ĐĨA. Chạy ĐÚNG MỘT LẦN mỗi tiến trình.

    ⚠️ LỖI ĐÃ SỬA 15/08/2026 — CHỐNG GỬI TRÙNG TRƯỚC ĐÓ CHỈ SỐNG ĐƯỢC MỘT CHU KỲ
    ===========================================================================
    Bản cũ giữ khoá trong `self._seen`, một `set` của INSTANCE. Nhưng
    `engine._build_plan()` dựng một `OrderRouter` MỚI mỗi chu kỳ, nên `_seen`
    luôn rỗng khi vào `route()` — nó chỉ chống được lệnh trùng TRONG CÙNG một
    lượt gọi, đúng thứ không bao giờ xảy ra vì `order_plan` đã gộp theo công cụ.

    Hệ quả thật: một tiến trình khởi động lại (watchdog, người vận hành mở lại
    giao diện, `live_server` thay bản mới) giữa lúc lệnh đã gửi nhưng sổ vị thế
    chưa kịp ghi là hệ gửi LẠI đúng lệnh đó cho cùng một nến. Cửa sổ ấy nhỏ
    nhưng có thật, và hậu quả là hai vị thế cho một tín hiệu.

    Nay khoá đi qua `OrderStateMachine`: `create_order()` claim và ghi
    `ORDER_CREATED` vào outbox JSONL, `rebuild_from_outbox()` nạp lại lúc khởi
    động. Đó chính là bộ máy 963 dòng đã có sẵn trong repo mà chưa ai nối vào.

    Chỉ nạp MỘT lần: `rebuild_from_outbox()` đọc và phát lại toàn bộ nhật ký, và
    router được dựng mới mỗi chu kỳ — gọi mỗi lần là đọc lại cả tệp mỗi giờ, và
    tệ hơn, nó XOÁ SẠCH trạng thái trong RAM trước khi phát lại, nên mọi khoá
    vừa claim trong chu kỳ này mà chưa kịp ghi đĩa sẽ biến mất.
    """
    global _claims_restored
    if _claims_restored:
        return
    _claims_restored = True
    osm = _osm()
    if osm is None:
        return
    try:
        n = osm.rebuild_from_outbox()
        if n:
            log(f"router: đã nạp lại {n} khoá chống gửi trùng từ sổ bền vững")
    except Exception as exc:
        log_error(f"router: KHÔNG nạp lại được khoá chống trùng ({type(exc).__name__}: "
                  f"{exc}) — có thể gửi lại lệnh của nến trước sau khi khởi động lại")


def _make_breaker():
    """Ngắt mạch MT5, hoặc `None` nếu không nạp được.

    `circuit_breaker` import `MetaTrader5` ở đầu module, nên trên máy không cài thư
    viện (CI, máy phát triển) nó không nạp được. Trả `None` và chạy tiếp KHÔNG phải
    fail-soft ở tầng rủi ro: không có thư viện MT5 thì cũng không có `order_send`
    nào để mà chặn.
    """
    try:
        from src.python.core.broker.circuit_breaker import MT5CircuitBreaker

        return MT5CircuitBreaker()
    except Exception:
        return None



# Hành động LÀM GIẢM phơi nhiễm — luôn được gửi, kể cả khi cổng an toàn đang chặn.
# Xem bất biến 1: cổng sinh ra để ngăn MỞ THÊM rủi ro, không phải để cấm thoát.
_RISK_REDUCING = frozenset({"CLOSE", "REDUCE", "REVERSE_CLOSE"})



# Đệm ký quỹ giữ lại. Gửi tới sát 100% ký quỹ tự do là tự đặt mình một tick nữa
# là Margin Call.
_MARGIN_BUFFER = 1.20


def _margin_shortfall(mt5, req: Dict[str, Any], action: str) -> str:
    """Lý do KHÔNG đủ ký quỹ cho lệnh này. Rỗng = đủ, cứ gửi.

    LỖI ĐÃ SỬA 21/08/2026 — MỘT LỆNH KHÔNG VỪA KÝ QUỸ HẠ CẢ LƯỢT GỬI
    =================================================================
        17:30:24  BROKER_REJECTED (broker từ chối retcode 10019)   ×6
        17:37:26  [CIRCUIT BREAKER OPEN] retcode=10019

    `10019` là NO_MONEY, và nó nằm trong `FATAL_RETCODES`, nên một lệnh không vừa
    ký quỹ MỞ CẦU CHÌ và chặn nốt những lệnh còn lại trong cùng lượt — đúng hình
    dạng sự cố `10014` đã sửa sáng nay.

    Đo lúc 17:45 trên chính tài khoản: notional gộp ~$571.000 = 5,7× equity ở đòn
    bẩy 1:15, tức cần ~38% equity làm ký quỹ. Kế hoạch lệnh tính lot từ chính
    sách đòn bẩy mà KHÔNG hỏi broker còn bao nhiêu ký quỹ tự do, nên khi danh mục
    đã đầy thì phần còn lại của kế hoạch âm thầm rụng — và danh mục THẬT khác
    danh mục ĐỊNH, với việc chân nào lọt được quyết định bởi THỨ TỰ GỬI chứ không
    bởi chiến lược.

    Hỏi trước bằng `order_calc_margin()` thì lệnh không vừa bị bỏ qua có LÝ DO ĐỌC
    ĐƯỢC, cầu chì không mở, và các chân sau vẫn được xét.

    KHÔNG chặn lệnh GIẢM phơi nhiễm: đóng bớt luôn TRẢ LẠI ký quỹ, và chặn đường
    thoát vì thiếu ký quỹ là đúng cái vòng xoáy cần tránh nhất.

    Fail-soft: không tính được thì cho gửi. Đoán sai theo hướng chặn sẽ làm hệ
    đứng im vì một phép tính phụ.
    """
    if action in _RISK_REDUCING:
        return ""
    try:
        need = mt5.order_calc_margin(req["type"], req["symbol"],
                                     req["volume"], req["price"])
        if need is None:
            return ""
        acc = mt5.account_info()
        if acc is None:
            return ""
        free = float(acc.margin_free)
    except Exception:
        return ""
    if float(need) * _MARGIN_BUFFER <= free:
        return ""
    return (f"BỎ QUA — ký quỹ không đủ: cần ${float(need):,.0f} "
            f"(×{_MARGIN_BUFFER:.2f} đệm = ${float(need) * _MARGIN_BUFFER:,.0f}) "
            f"nhưng chỉ còn ${free:,.0f} tự do")


def _is_fatal(retcode) -> bool:
    """Retcode có thuộc nhóm KHÔNG tự khỏi không.

    Đọc từ `circuit_breaker.FATAL_RETCODES` — bảng phân loại retcode có ĐÚNG MỘT
    chủ sở hữu, và một bản sao thứ hai ở đây là chỗ hai bên trôi khỏi nhau. Không
    đọc được thì coi là FATAL: cảnh báo thừa rẻ hơn cảnh báo thiếu.
    """
    try:
        from src.python.core.broker.circuit_breaker import CircuitBreaker

        return int(retcode or 0) in CircuitBreaker.FATAL_RETCODES
    except Exception:
        return True


def _build_now() -> str:
    """Bản build đang chạy — để sổ quyết định trả lời được "lệnh do bản nào sinh"."""
    try:
        from src.python.core.runtime_meta import version

        return version()
    except Exception:
        return ""


def _timeframe_of(symbol: str) -> str:
    """Khung tín hiệu của các chân đang nhắm vào `symbol`, ghép bằng dấu gạch chéo.

    Một công cụ có thể do nhiều chân ở nhiều khung cùng giữ
    và H4 — nên trường này không quy về một khung được. Ghi đủ đúng hơn chọn bừa.
    """
    try:
        from src.python.strategies import registry as REG

        # So khớp qua REGISTRY chứ không qua chuỗi khoá chân: khoá chân viết
        # thường còn symbol viết hoa, nên phép
        # `symbol in k` của bản trước KHÔNG BAO GIỜ đúng và hai ô "khung tín
        # hiệu"/"chân" luôn trống. Registry giữ `symbols` chuẩn hoá sẵn.
        tfs = sorted({s.signal_tf for s in REG.STRATEGIES
                      if symbol in (s.symbols or ())})
        return " / ".join(tfs)
    except Exception:
        return ""


def _legs_of(symbol: str) -> str:
    """Tên các CHÂN đang nhắm vào `symbol`, ghép bằng dấu cộng.

    Một công cụ có thể do nhiều chân cùng giữ, nên trường "chiến
    lược" của thư không quy về một tên được. Ghi đủ cả ba đúng hơn là chọn bừa một.
    """
    try:
        from src.python.strategies import registry as REG

        # Cùng lý do như `_timeframe_of`: khớp qua `registry.symbols`, không qua
        # chuỗi khoá chân viết thường.
        names = sorted({s.name for s in REG.STRATEGIES
                        if symbol in (s.symbols or ())})
        return " + ".join(names) if names else symbol
    except Exception:
        return symbol


class OrderRouter:
    """Gửi kế hoạch ra broker. Giữ khoá chống trùng trong bộ nhớ phiên chạy."""

    def __init__(self, mt5=None, *, dry_run: bool = True,
                 deviation: int = DEVIATION_POINTS, breaker=None,
                 simulation: bool = False):
        """`simulation=True` → KHÔNG chạm bất kỳ trạng thái VẬN HÀNH nào.

        ⚠️ LỖI ĐÃ SỬA 15/08/2026 — BACKTEST LÀM BẨN TRẠNG THÁI LIVE
        ============================================================
        `parity.replay_leg` dựng router với `dry_run=False` (đúng, vì nó phải đi
        qua nhánh gửi thật để đo được đường code thật) trên một `SimBroker`. Nhưng
        hai tác dụng phụ đi theo nhánh đó lại chạm vào thế giới thật:

          · GỬI EMAIL — mỗi lệnh mô phỏng bắn một thư "VÀO LỆNH". Một lượt parity
            bảy chân là hàng trăm thư báo những lệnh KHÔNG HỀ TỒN TẠI.
          · GHI SỔ KHOÁ BỀN VỮNG — `create_order()` ghi `ORDER_CREATED` vào
            `logs/live/durable_event_log.jsonl`, đúng tệp mà bản LIVE dùng để
            chống gửi trùng. Chạy backtest xong là khoá của những nến mô phỏng nằm
            trong sổ live, và lệnh THẬT ở đúng nến đó sẽ bị chặn như lệnh trùng.

        Thấy được trong đầu ra lượt parity 19:43 hôm nay: `[STATE_MACHINE] Created
        Order …` và `email … VÀO LỆNH` xen giữa các dòng mô phỏng.

        `dry_run` KHÔNG thay được cờ này: `dry_run=True` cắt luôn `order_send`, tức
        cắt đúng thứ parity cần đo. Hai câu hỏi khác nhau thì hai cờ:

            dry_run     "có gọi order_send không?"
            simulation  "broker này có phải broker THẬT không?"
        """
        self.mt5 = mt5
        self.dry_run = bool(dry_run)
        self.simulation = bool(simulation)
        self.deviation = int(deviation)
        if not self.simulation:
            _restore_claims_once()
        # Ngắt mạch dùng CHUNG cho cả phiên chạy: bộ đếm lỗi phải cộng dồn qua nhiều
        # chu kỳ tái cân bằng. Tạo mới mỗi lần gọi `route()` thì bộ đếm reset về 0
        # sau mỗi chu kỳ và ngưỡng `max_failures` không bao giờ chạm tới.
        self.breaker = breaker if breaker is not None else _make_breaker()

    # ─────────────────────────────────────────────── gửi một lệnh
    def _send_one(self, *, symbol: str, action: str, side: str, lots: float,
                  stop_price: Optional[float], bar_utc: str,
                  take_profit: Optional[float] = None,
                  leg: str = "", reason: str = "") -> SendResult:
        """`reason` là LÝ DO nghiệp vụ của lệnh, đi vào `comment` gửi broker.

        Thêm 15/08/2026. Trước đó `comment` chỉ mang tên HÀNH ĐỘNG (`OPEN`,
        `CLOSE`), nên nhìn lịch sử lệnh trên MT5 không biết được vì sao đóng —
        mốc đóng phiên, dừng lỗ, hay chốt lời đều hiện một chữ "CLOSE".
        Cùng lỗ hổng ấy làm bảng lý-do-đóng của vòng backtest 2026 chỉ có một
        dòng, che mất 113 lệnh (16,8%) thật ra chạm time-stop.
        """
        key = idempotency_key(symbol, action, bar_utc)
        if lots <= 0:
            return SendResult(symbol=symbol, action=action, side=side, lots=lots,
                              ok=False, dry_run=self.dry_run, idempotency_key=key,
                              reason="lot <= 0")

        # NGẮT MẠCH — hỏi trước khi chạm sàn, kể cả trong dry-run để đường code
        # giống nhau ở hai chế độ.
        if self.breaker is not None:
            allowed, why = self.breaker.can_execute()
            if not allowed:
                return SendResult(symbol=symbol, action=action, side=side,
                                  lots=lots, ok=False, dry_run=self.dry_run,
                                  idempotency_key=key,
                                  reason=f"NGẮT MẠCH: {why}")

        # CLAIM khoá TRƯỚC khi chạm broker, và claim BỀN VỮNG — xem
        # `_restore_claims_once`. `create_order` trả `None` nghĩa là khoá đã có
        # người giữ, tức lệnh này đã gửi rồi (có thể ở một tiến trình trước).
        osm = None if self.simulation else _osm()
        claim = None
        if osm is not None:
            claim = osm.create_order(
                strategy=leg or symbol, symbol=symbol, bar_timestamp=bar_utc,
                direction=side, lot=float(lots), setup_id=action,
                timeframe=str(bar_utc)[:16])
            if claim is None:
                return SendResult(symbol=symbol, action=action, side=side, lots=lots,
                                  ok=True, dry_run=self.dry_run, idempotency_key=key,
                                  reason="BỎ QUA — trùng khoá chống gửi lặp")

        if self.dry_run or self.mt5 is None:
            # DRY-RUN đi qua ĐÚNG nhánh claim ở trên để đường code giống hệt chế
            # độ thật, rồi NHẢ NGAY: không có lệnh thật nào tồn tại, nên giữ khoá
            # lại sẽ chặn đúng lệnh đó khi bật `LIVE_ORDERS=1` trong cùng nến.
            self._release(osm, claim, "dry-run")
            return SendResult(symbol=symbol, action=action, side=side, lots=lots,
                              ok=True, dry_run=True, stop_price=stop_price,
                              idempotency_key=key,
                              reason="dry-run — không gọi order_send")

        # Lệnh làm GIẢM phơi nhiễm phải đóng ĐÍCH DANH vị thế, xem `_close_symbol`.
        if action in _RISK_REDUCING:
            res = self._close_symbol(symbol=symbol, action=action, side=side,
                                     lots=lots, key=key, reason=reason)
            if not res.ok:
                self._release(osm, claim, res.reason or "đóng lệnh thất bại")
            return res

        try:
            mt5 = self.mt5
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                self._release(osm, claim, "không đọc được tick")
                return SendResult(symbol=symbol, action=action, side=side, lots=lots,
                                  ok=False, dry_run=False, idempotency_key=key,
                                  reason="không đọc được tick")
            is_buy = side == "BUY"
            bid = float(getattr(tick, "bid", 0.0) or 0.0)
            ask = float(getattr(tick, "ask", 0.0) or 0.0)
            price = ask if is_buy else bid
            # SPREAD ĐO TẠI CHỖ, không lấy từ cấu hình: bảng ước lượng trong
            # Spread backtest có thể là ƯỚC LƯỢNG, và mục đích ghi
            # số này là để biết ước lượng ấy lệch bao nhiêu so với broker thật.
            spread_price = (ask - bid) if (ask > 0 and bid > 0) else None
            spread_bps = (spread_price / price * 1e4
                          if spread_price is not None and price > 0 else None)
            req: Dict[str, Any] = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(lots),
                "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
                "price": price,
                "deviation": self.deviation,
                "magic": magic_for(leg or symbol),
                "comment": (f"CHEO-FX {reason or action}")[:31],
                "type_time": mt5.ORDER_TIME_GTC,
            }
            # Dừng lỗ đi CÙNG lệnh mở — xem bất biến 3 ở đầu file.
            if stop_price:
                req["sl"] = float(stop_price)
            # CHỐT LỜI cũng đi CÙNG lệnh mở, và vì đúng một lý do: backtest thoát ở
            # mức TP đó. Gửi lệnh mà không gửi `tp` nghĩa là live KHÔNG có lối thoát
            # thắng nào — vị thế chỉ đóng khi bị dừng lỗ quét hoặc khi tới mốc đóng
            # phiên. Trên chuỗi 462 lệnh đo được, chốt lời là lối thoát của 47,8% số
            # lệnh; bỏ nó là bỏ toàn bộ phần lãi và giữ nguyên phần lỗ.
            if take_profit:
                req["tp"] = float(take_profit)
            short = _margin_shortfall(mt5, req, action)
            if short:
                return SendResult(symbol=symbol, action=action, side=side,
                                  lots=lots, ok=False, price=price,
                                  spread_bps=spread_bps, stop_price=stop_price,
                                  reason=short)
            res = mt5.order_send(req)
            retcode = int(getattr(res, "retcode", -1))
            ok = retcode == int(getattr(mt5, "TRADE_RETCODE_DONE", 10009))
            if self.breaker is not None:
                if ok:
                    self.breaker.record_success("trade")
                else:
                    self.breaker.record_failure(
                        retcode, str(getattr(res, "comment", "")))
            if not ok:
                self._release(osm, claim, f"broker từ chối retcode {retcode}")
            order_id = int(getattr(res, "order", 0) or 0)
            if ok and stop_price and order_id:
                # LƯỚI AN TOÀN cho bất biến 3, KHÔNG thay thế nó — xem sự cố
                # 24/08/2026 ở `_verify_stop_attached`. Đường chính vẫn là `sl`
                # trong CHÍNH request này (ở trên); đây chỉ bắt đúng trường hợp
                # broker lặng lẽ bỏ qua nó dù trả DONE.
                self._verify_stop_attached(mt5, order_id, symbol, float(stop_price))
            # Giá KHỚP THẬT nếu broker trả về, nếu không thì giá đã gửi. Chênh
            # lệch giữa hai cái là TRƯỢT GIÁ — thứ backtest không có và là một
            # trong bốn nguồn lệch đã biết của cổng parity.
            filled = float(getattr(res, "price", 0.0) or 0.0) or price
            return SendResult(
                symbol=symbol, action=action, side=side, lots=lots, ok=ok,
                dry_run=False, retcode=retcode,
                order_id=int(getattr(res, "order", 0) or 0),
                price=filled, stop_price=stop_price, idempotency_key=key,
                bid=bid or None, ask=ask or None,
                spread_price=spread_price, spread_bps=spread_bps,
                slippage_price=(filled - price) if filled and price else None,
                magic=int(req.get("magic", 0) or 0), bar_utc=str(bar_utc),
                reason="" if ok else f"broker từ chối: {getattr(res, 'comment', '')}")
        except Exception as exc:                           # pragma: no cover
            log_error(f"order_send {symbol} {action}: {type(exc).__name__}: {exc}")
            self._release(osm, claim, f"{type(exc).__name__}: {exc}")
            return SendResult(symbol=symbol, action=action, side=side, lots=lots,
                              ok=False, dry_run=False, idempotency_key=key,
                              reason=f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _verify_stop_attached(mt5, ticket: int, symbol: str, stop_price: float) -> None:
        """Đọc lại vị thế VỪA MỞ, gắn lại cầu chì nếu broker đã lặng lẽ bỏ qua nó.

        SỰ CỐ 24/08/2026 — `req["sl"]` gửi kèm chính lệnh mở (đúng bất biến 3),
        broker trả `retcode=10009` (DONE), nhưng `positions_get()` đọc lại cho thấy
        `sl=0` trên vị thế vừa tạo — không lỗi, không cảnh báo, cầu chì biến mất
        trong im lặng. `ftmo_guard.open_risk_usd()` sau đó thấy hàng loạt vị thế
        "thiếu cầu chì" cùng lúc, đúng thiết kế fail-closed nên giả định rủi ro ở
        mức TRẦN cho phép và đóng sạch toàn bộ 40/40 vị thế — tốn hai lượt spread
        cho một lỗi lẽ ra sửa được ngay khi phát hiện.

        ĐÂY KHÔNG PHẢI VI PHẠM BẤT BIẾN 3. Đường CHÍNH vẫn là `sl` trong CHÍNH
        request mở lệnh (xem `_send_one` ở trên) — hàm này chỉ chạy SAU khi lệnh
        đó đã "DONE", như một LƯỚI AN TOÀN cho đúng trường hợp broker không tôn
        trọng trường đó. Khoảng hở còn lại (giữa lúc vị thế mở và lúc hàm này gắn
        lại SL) chỉ còn dưới một giây trong CÙNG lệnh gọi — thay vì treo tới khi
        `ftmo_guard` phát hiện ở chu kỳ sau (đo được: 90 giây, và hậu quả là đóng
        sạch cả sổ thay vì một vị thế).
        """
        try:
            positions = mt5.positions_get(ticket=ticket)
        except Exception as exc:
            log_error(f"router: không đọc lại được vị thế #{ticket} ({symbol}) để "
                      f"xác minh cầu chì: {type(exc).__name__}: {exc}")
            return
        if not positions:
            log_error(f"router: vị thế #{ticket} ({symbol}) không thấy khi xác minh "
                      f"cầu chì — có thể đã đóng ngay sau khi mở.")
            return
        pos = positions[0]
        if float(getattr(pos, "sl", 0.0) or 0.0) > 0.0:
            return          # cầu chì đã có trên broker, không cần làm gì thêm
        log_error(f"router: vị thế #{ticket} ({symbol}) mở THÀNH CÔNG nhưng broker "
                  f"KHÔNG gắn cầu chì (sl=0) dù request đã kèm sl={stop_price:.6f} — "
                  f"gắn lại ngay qua TRADE_ACTION_SLTP.")
        try:
            res2 = mt5.order_send({
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "symbol": symbol,
                "sl": float(stop_price),
                "tp": float(getattr(pos, "tp", 0.0) or 0.0),
                "magic": int(getattr(pos, "magic", 0) or 0),
            })
            retcode2 = int(getattr(res2, "retcode", -1))
            if retcode2 == int(getattr(mt5, "TRADE_RETCODE_DONE", 10009)):
                log(f"router: đã gắn lại cầu chì cho #{ticket} ({symbol}) — "
                    f"sl={stop_price:.6f}")
            else:
                log_error(f"router: gắn lại cầu chì cho #{ticket} ({symbol}) THẤT "
                          f"BẠI — retcode {retcode2} ({getattr(res2, 'comment', '')})")
        except Exception as exc:
            log_error(f"router: lỗi khi gắn lại cầu chì cho #{ticket} ({symbol}): "
                      f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _release(osm, claim: Optional[str], why: str) -> None:
        """NHẢ khoá chống trùng khi lệnh KHÔNG hề tới được broker.

        Giữ khoá của một lệnh chưa từng tồn tại là tự chặn chính mình: mọi lần
        thử lại cho CÙNG nến sẽ bị coi là trùng, dù không có vị thế nào. Với chân
        H4 đó là mất 4 giờ; với hai chân D1 là mất trọn chu kỳ tái cân bằng 21
        ngày. Đây đúng lỗi mà `release_rejected_order` bên một hệ một-tài-sản sinh ra để
        sửa (ghi trong docstring của nó, 21/07).

        Hợp đồng của `release_rejected_order`: phải chuyển sang một trạng thái
        terminal-rejected TRƯỚC. Chỉ nhả ở nhánh REJECTED để không phá vỡ dedup
        thật của những lệnh ĐÃ khớp.
        """
        if osm is None or not claim:
            return
        try:
            from src.python.core.broker.order_state_machine import OrderState

            osm.transition(claim, OrderState.VALIDATED, reason=why)
            osm.transition(claim, OrderState.SUBMITTING, reason=why)
            osm.transition(claim, OrderState.BROKER_REJECTED, reason=why)
            osm.release_rejected_order(claim)
        except Exception as exc:                           # pragma: no cover
            log_error(f"router: KHÔNG nhả được khoá {claim[:16]}: "
                      f"{type(exc).__name__}: {exc} — nến này sẽ không thử lại được")

    def _close_symbol(self, *, symbol: str, action: str, side: str,
                      lots: float, key: str, reason: str = "") -> SendResult:
        """ĐÓNG đích danh từng vị thế của `symbol`, tối đa `lots`.

        ⚠️ LỖI ĐÃ SỬA 15/08/2026 — LỆNH ĐÓNG TRƯỚC ĐÓ LÀM TĂNG PHƠI NHIỄM
        =================================================================
        Bản cũ gửi lệnh đóng y hệt lệnh mở: `TRADE_ACTION_DEAL` + `ORDER_TYPE_SELL`,
        KHÔNG có trường `position`. Trên tài khoản NETTING thì đúng — broker tự trừ
        vào vị thế đang có. Nhưng tài khoản FTMO là **HEDGING**, và ở đó lệnh không
        chỉ định `position` là một lệnh MỞ MỚI: muốn đóng 0,42 lot mua thì nhận
        thêm 0,42 lot bán, thành hai vị thế ngược chiều cùng tồn tại.

        Hậu quả cộng dồn, và cộng dồn theo hướng tệ nhất:
          · phơi nhiễm GẤP ĐÔI thay vì về 0 — đúng lúc hệ đang cố giảm rủi ro
          · ký quỹ chiếm gấp đôi, mà FTMO Swing chỉ có đòn bẩy 1:30
          · chu kỳ sau `positions_get()` thấy hai vị thế, chênh lệch vẫn khác 0,
            hệ lại gửi thêm một lệnh "đóng" nữa — vòng lặp nhân đôi vị thế
          · phí swap trả cho CẢ HAI chân, mỗi đêm

        Chính docstring ở đầu file đã nêu đúng cơ chế này ở bất biến 2 (đảo chiều
        phải là hai lệnh) nhưng chưa áp cho nhánh ĐÓNG.

        Nay: đọc `positions_get(symbol=…)`, lọc theo magic của hệ, rồi đóng từng vị
        thế bằng `"position": ticket` — đúng cách `mt5_bridge.close_position_api`
        vẫn làm cho nút FLATTEN ALL.
        """
        mt5 = self.mt5
        try:
            positions = mt5.positions_get(symbol=symbol)
        except Exception as exc:
            return SendResult(symbol=symbol, action=action, side=side, lots=lots,
                              ok=False, dry_run=False, idempotency_key=key,
                              reason=f"đọc vị thế lỗi: {type(exc).__name__}: {exc}")
        if positions is None:
            # LỖI ĐỌC, không phải "không có vị thế" — cùng cái bẫy fail-open mà
            # `mt5_bridge.close_all_positions` đã ghi. Báo hỏng để chu kỳ sau thử lại.
            return SendResult(symbol=symbol, action=action, side=side, lots=lots,
                              ok=False, dry_run=False, idempotency_key=key,
                              reason="positions_get trả None (lỗi đọc) — chưa đóng gì")

        # Chỉ đụng vị thế CỦA HỆ NÀY. Dải magic riêng để hai bot chạy chung một tài
        # khoản không đóng nhầm lệnh của nhau — xem `MAGIC_BASE`.
        mine = [p for p in positions
                if MAGIC_BASE <= int(getattr(p, "magic", 0) or 0) < MAGIC_BASE + 90000]
        if not mine:
            return SendResult(symbol=symbol, action=action, side=side, lots=lots,
                              ok=True, dry_run=False, idempotency_key=key,
                              reason="không còn vị thế của hệ — coi như đã đóng")

        remaining = float(lots)
        closed = 0.0
        last_price = None
        errors = []
        for p in mine:
            if remaining <= 1e-9:
                break
            vol = min(float(getattr(p, "volume", 0.0) or 0.0), remaining)
            if vol <= 0:
                continue
            try:
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    errors.append("không đọc được tick")
                    break
                is_long = int(getattr(p, "type", 0)) == int(mt5.ORDER_TYPE_BUY)
                req: Dict[str, Any] = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": float(vol),
                    # NGƯỢC chiều vị thế đang giữ, và `position` khoá đúng vị thế đó.
                    "type": (mt5.ORDER_TYPE_SELL if is_long else mt5.ORDER_TYPE_BUY),
                    "position": int(getattr(p, "ticket", 0)),
                    "price": float(tick.bid if is_long else tick.ask),
                    "deviation": self.deviation,
                    "magic": int(getattr(p, "magic", 0) or 0),
                    # LÝ DO đi kèm lệnh, không chỉ tên hành động: nó hiện trong
                    # lịch sử MT5 và là chỗ duy nhất truy được "vì sao đóng" khi
                    # nhìn lại từ phía broker.
                    "comment": (f"CHEO-FX {reason or action}")[:31],
                    "type_time": mt5.ORDER_TIME_GTC,
                }
                res = mt5.order_send(req)
                retcode = int(getattr(res, "retcode", -1))
                ok = retcode == int(getattr(mt5, "TRADE_RETCODE_DONE", 10009))
                if self.breaker is not None:
                    if ok:
                        self.breaker.record_success("trade")
                    else:
                        self.breaker.record_failure(
                            retcode, str(getattr(res, "comment", "")))
                if ok:
                    closed += vol
                    remaining -= vol
                    last_price = req["price"]
                else:
                    errors.append(f"#{req['position']} retcode {retcode} "
                                  f"{getattr(res, 'comment', '')}")
            except Exception as exc:                       # pragma: no cover
                errors.append(f"{type(exc).__name__}: {exc}")

        return SendResult(
            symbol=symbol, action=action, side=side, lots=round(closed, 2),
            ok=(closed > 0 and not errors), dry_run=False, price=last_price,
            idempotency_key=key,
            reason=("" if not errors else "; ".join(errors)[:200]))

    # ─────────────────────────────────────────────── gửi cả kế hoạch
    @staticmethod
    def _pick_take_profit(action) -> Optional[float]:
        """Mức chốt lời gửi broker. Chiến lược khai MỘT mức, server giữ MỘT mức.

        Bỏ trống (`None`) thì lệnh đi mà KHÔNG có chốt lời — chấp nhận được cho chiến
        lược không khai TP, nhưng với chiến lược CÓ khai thì đó là mất lối thoát
        thắng, nên `order_plan` phải luôn điền trường này.
        """
        tp = getattr(action, "take_profit", None)
        return float(tp) if tp and float(tp) > 0 else None

    def route(self, plan, *, bar_utc: Optional[str] = None,
              log_decisions: bool = True) -> RouteResult:
        """Gửi mọi việc trong `plan`. Trả kết quả từng lệnh, không ném lỗi."""
        out = RouteResult(dry_run=self.dry_run)
        gate_open = bool(getattr(plan, "allowed", False))
        if not gate_open:
            out.blocked_reason = getattr(plan, "gate", None) and plan.gate.explain() \
                or "cổng an toàn chặn"
            log(f"router: cổng chặn lệnh TĂNG phơi nhiễm — {out.blocked_reason}. "
                f"Lệnh GIẢM phơi nhiễm vẫn được gửi.")

        stamp = bar_utc or datetime.now(timezone.utc).isoformat(timespec="hours")

        for a in plan.to_trade:
            if a.action == "REVERSE":
                # BẤT BIẾN 2 — hai lệnh, không phải một.
                out.sent.append(self._send_one(
                    symbol=a.symbol, action="REVERSE_CLOSE",
                    side=("SELL" if a.current_lots > 0 else "BUY"),
                    lots=abs(a.current_lots), stop_price=None, bar_utc=stamp,
                    reason=a.reason))
                if gate_open:
                    out.sent.append(self._send_one(
                        symbol=a.symbol, action="REVERSE_OPEN", side=a.side,
                        lots=abs(a.target_lots), stop_price=a.stop_price,
                        take_profit=self._pick_take_profit(a),
                        bar_utc=stamp, reason=a.reason))
                else:
                    # Nửa ĐÓNG đã đi qua, nửa MỞ bị giữ lại → phơi nhiễm GIẢM.
                    out.skipped.append(SendResult(
                        symbol=a.symbol, action="REVERSE_OPEN", side=a.side,
                        lots=abs(a.target_lots), ok=True, dry_run=self.dry_run,
                        reason=f"CHẶN nửa MỞ của lệnh đảo — {out.blocked_reason}"))
                continue

            if not gate_open and a.action not in _RISK_REDUCING:
                out.skipped.append(SendResult(
                    symbol=a.symbol, action=a.action, side=a.side, lots=a.lots,
                    ok=True, dry_run=self.dry_run,
                    reason=f"CHẶN — {out.blocked_reason}"))
                continue

            # Lệnh ĐÓNG hoặc GIẢM không mang dừng lỗ/chốt lời: hai mức đó thuộc về
            # vị thế CÒN LẠI, và gửi kèm `sl`/`tp` vào một lệnh đóng là cách broker
            # từ chối cả lệnh.
            opening = a.action in ("OPEN", "INCREASE")
            out.sent.append(self._send_one(
                symbol=a.symbol, action=a.action, side=a.side, lots=a.lots,
                stop_price=(a.stop_price if opening else None),
                take_profit=(self._pick_take_profit(a) if opening else None),
                bar_utc=stamp, reason=a.reason))

        for a in plan.actions:
            if a.action == "HOLD" and a.reason:
                out.skipped.append(SendResult(
                    symbol=a.symbol, action="HOLD", side="FLAT", lots=0.0,
                    ok=True, dry_run=self.dry_run, reason=a.reason))

        # Gắn bối cảnh CẤP KẾ HOẠCH vào từng kết quả TRƯỚC khi ghi sổ và gửi thư.
        # Làm ở một chỗ để sổ, thư và bảng giao diện không bao giờ nói ba số khác
        # nhau cho cùng một lệnh.
        self._enrich(out, plan)
        if log_decisions and not self.simulation:
            self._log(out, plan)
        self._email(out, plan)
        return out

    # ─────────────────────────────────────────────── email sự kiện lệnh
    def _email(self, out: RouteResult, plan) -> None:
        """Một thư cho mỗi lệnh ĐÃ CHẠM broker. Không bao giờ ném lỗi.

        Chỉ gửi ở chế độ thật: `dry_run` nghĩa là chưa có gì xảy ra trên tài khoản,
        và thư báo "đã vào lệnh" cho một lệnh không tồn tại là thứ làm người vận
        hành mất niềm tin vào cả kênh email.

        Lệnh BỊ TỪ CHỐI cũng gửi — đó là lúc danh mục lệch khỏi mục tiêu mà không ai
        biết, và nhóm retcode FATAL thì hệ sẽ không tự khỏi.

        NGOẠI LỆ: lệnh bị chính NGẮT MẠCH chặn (chưa từng chạm broker, `r.retcode`
        luôn `None`) KHÔNG đi qua `order_rejected` — xem `EM.circuit_breaker_open`
        cho lý do (sự cố 24/08/2026: một cầu dao mở cascade thành N thư "retcode 0"
        sai sự thật cho N công cụ đứng chờ cùng một chu kỳ).
        """
        if self.dry_run or self.simulation:
            return
        from functools import partial

        try:
            from src.python.shared.notifications import emails as EM
            from src.python.utils import alerts

            lev = float(getattr(plan, "leverage", 0.0) or 0.0)
            equity = float(getattr(plan, "equity_usd", 0.0) or 0.0)
            by_symbol = {a.symbol: a for a in getattr(plan, "actions", [])}
            breaker_blocked: list = []
            for r in out.sent:
                act = by_symbol.get(r.symbol)
                if not r.ok:
                    if (r.reason or "").startswith("NGẮT MẠCH:"):
                        breaker_blocked.append(r)
                        continue
                    alerts.once(
                        f"order_rejected_{r.symbol}_{r.retcode}",
                        partial(EM.order_rejected, symbol=r.symbol, action=r.action,
                                lots=r.lots, retcode=int(r.retcode or 0),
                                comment=r.reason or "", side=r.side,
                                bar_utc=str(getattr(plan, "asof", "") or ""),
                                fatal=_is_fatal(r.retcode)),
                        ttl_sec=3600.0)
                    continue
                if r.action in ("OPEN", "INCREASE", "REVERSE_OPEN"):
                    EM.entry(strategy=_legs_of(r.symbol), symbol=r.symbol,
                             direction=r.side, lots=r.lots, price=float(r.price or 0.0),
                             stop_price=r.stop_price,
                             weight=(act.target_weight if act else None),
                             leverage=lev, equity=float(equity or 0.0),
                             spread=float(r.spread_price or 0.0),
                             trade_id=f"#{r.order_id}" if r.order_id else "",
                             magic=magic_for(r.symbol),
                             timeframe=_timeframe_of(r.symbol),
                             notional_usd=r.notional_usd,
                             broker_time=str(getattr(plan, "asof", "") or ""),
                             reason=(act.reason if act else ""))
            if breaker_blocked:
                why = breaker_blocked[0].reason or ""
                alerts.once(
                    "circuit_breaker_open",
                    partial(EM.circuit_breaker_open,
                            blocked_symbols=[r.symbol for r in breaker_blocked],
                            why=why),
                    ttl_sec=3600.0)
        except Exception as exc:                           # pragma: no cover
            log(f"router: KHÔNG gửi được email sự kiện lệnh: "
                f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _enrich(out: RouteResult, plan) -> None:
        """Bơm bối cảnh kế hoạch (equity, đòn bẩy, tỷ trọng, nến) vào từng lệnh.

        `SendResult` là `frozen=True` nên phải thay bằng bản sao — cố ý giữ nó
        bất biến: một bản ghi lệnh đã gửi mà sửa được là một bản ghi không tin được.
        """
        import dataclasses

        lev = float(getattr(plan, "leverage", 0.0) or 0.0)
        eq = float(getattr(plan, "equity_usd", 0.0) or 0.0)
        asof = str(getattr(plan, "asof", "") or "")
        by_sym = {a.symbol: a for a in getattr(plan, "actions", [])}
        for bucket in (out.sent, out.skipped):
            for i, r in enumerate(bucket):
                act = by_sym.get(r.symbol)
                bucket[i] = dataclasses.replace(
                    r, equity_usd=eq, leverage=lev,
                    target_weight=getattr(act, "target_weight", None),
                    notional_usd=float(getattr(act, "notional_usd", 0.0) or 0.0),
                    bar_utc=r.bar_utc or asof,
                    timeframe=r.timeframe or _timeframe_of(r.symbol),
                    legs=r.legs or _legs_of(r.symbol))

    # ─────────────────────────────────────────────── nhật ký
    @staticmethod
    def _log(out: RouteResult, plan) -> None:
        """Ghi MỌI lệnh vào sổ quyết định — kể cả lệnh bị chặn và bị từ chối."""
        try:
            from src.python.execution import decision_log as DLOG

            # GHI ĐỦ MỌI TRƯỜNG của `SendResult`.
            #
            # Bản trước chọn tay 11 trường, và danh sách chọn tay là danh sách sẽ
            # thiếu đúng trường mới thêm — spread, trượt giá, notional, magic đều
            # rơi ra ngoài dù chúng đã được đo. `asdict` lấy hết, nên thêm một
            # trường vào `SendResult` là nó vào sổ ngay, không phải sửa hai chỗ.
            from dataclasses import asdict

            rows = [dict(asdict(r), leg=_legs_of(r.symbol),
                         timeframe=_timeframe_of(r.symbol))
                    for r in out.sent + out.skipped]
            if out.blocked_reason:
                rows.append({"symbol": "-", "action": "BLOCKED", "side": "-",
                             "lots": 0.0, "ok": False, "dry_run": out.dry_run,
                             "reason": out.blocked_reason})
            if rows:
                DLOG.record_many(
                    rows, strategy="OrderRouter",
                    extra={"leverage": getattr(plan, "leverage", None),
                           "equity_usd": getattr(plan, "equity_usd", None),
                           "asof": getattr(plan, "asof", None),
                           "gate": plan.gate.explain() if getattr(plan, "gate", None) else None,
                           "build": _build_now()})
        except Exception as exc:                           # pragma: no cover
            log_error(f"router: không ghi được sổ quyết định — {exc}")
