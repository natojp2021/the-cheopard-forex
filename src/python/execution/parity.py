"""parity.py — CHẠY ĐƯỜNG LIVE trên dữ liệu lịch sử rồi SO với backtest.

CÂU HỎI DUY NHẤT MODULE NÀY TRẢ LỜI
====================================
    Backtest nói chân này vào lệnh ở nến 100 và ra ở nến 148.
    Đường code thật — live_decision → position_book → order_plan → order_router →
    broker — có làm ĐÚNG như vậy không?

Trước 15/08/2026 không có gì trả lời được câu đó. Backtest tính lãi lỗ thẳng từ mảng
giá, còn tiền thật đi qua bảy lớp khác. Hai hệ, không ai đối chiếu.

CÁCH ĐO — REPLAY TỪNG NẾN, KHÔNG PHẢI CHẠY LẠI BACKTEST
========================================================
Với mỗi nến `i`:
    1. `SimBroker.step(i)`            quét dừng lỗ trên server TRƯỚC (SL không đợi ai)
    2. `live_decision(df[:i+1], …)`   ĐÚNG hàm mà live gọi, trên dữ liệu tới nến i
    3. `bars_held` lấy từ `PositionBook`, không phải từ biến đếm nội bộ
    4. `order_plan.build()` → `order_router.route()` → `SimBroker.order_send()`
    5. sổ vị thế cập nhật theo kết quả khớp THẬT của broker ảo

Cắt dữ liệu tới `i+1` là điều kiện chống nhìn tương lai: hàm quyết định không thể
thấy nến nào sau `i` vì chúng không có trong mảng nó nhận.

Bước 1 phải đứng TRƯỚC bước 2. Trên broker thật, dừng lỗ nằm trên server và bị bóng
nến quét, không đợi chiến lược gọi hàm. Đảo thứ tự là mô phỏng một thứ không tồn tại.

ĐỌC KẾT QUẢ
===========
`compare()` trả `ParityReport`. Khớp hoàn toàn là lý tưởng nhưng KHÔNG bắt buộc —
điều bắt buộc là mọi chênh lệch phải GIẢI THÍCH ĐƯỢC. Bốn nguồn lệch đã biết:

    làm tròn lot   backtest coi cỡ vị thế liên tục; broker làm tròn theo volume_step
    cầu chì        backtest không có SL; live có, và nó nổ (đo được: −1,5% Sharpe)
    cổng chặn      entry_gate có thể chặn một nến mà backtest vẫn vào
    triệt tiêu     hai chân ngược chiều trên cùng công cụ gộp trước khi gửi

Lệch KHÔNG thuộc bốn nhóm đó là một lỗi chưa biết, và phải tìm ra trước khi cấp vốn.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.python.execution.position_book import PositionBook
from src.python.execution.sim_broker import SimBroker


@dataclass
class ParityReport:
    """So sánh chuỗi lệnh của backtest với chuỗi lệnh của đường live."""
    leg: str
    symbol: str
    n_backtest: int
    n_live: int
    matched: int
    only_backtest: List[str] = field(default_factory=list)
    only_live: List[str] = field(default_factory=list)
    gross_backtest_bps: float = 0.0
    gross_live_bps: float = 0.0
    notes: List[str] = field(default_factory=list)

    @property
    def entry_match_pct(self) -> float:
        base = max(self.n_backtest, 1)
        return round(self.matched / base * 100.0, 1)

    @property
    def ok(self) -> bool:
        """Đạt khi MỌI lệnh của backtest đều có lệnh live cùng nến vào."""
        return self.matched == self.n_backtest and not self.only_live

    def explain(self) -> str:
        head = (f"{self.leg} ({self.symbol}): backtest {self.n_backtest} lệnh · "
                f"live {self.n_live} lệnh · khớp điểm vào {self.matched}"
                f"/{self.n_backtest} = {self.entry_match_pct}%")
        gross = (f"  gross backtest {self.gross_backtest_bps:+.1f} bps · "
                 f"live {self.gross_live_bps:+.1f} bps · "
                 f"lệch {self.gross_live_bps - self.gross_backtest_bps:+.1f}")
        lines = [head, gross]
        if self.only_backtest:
            lines.append(f"  CHỈ backtest có ({len(self.only_backtest)}): "
                         + ", ".join(self.only_backtest[:5]))
        if self.only_live:
            lines.append(f"  CHỈ live có ({len(self.only_live)}): "
                         + ", ".join(self.only_live[:5]))
        lines += [f"  {n}" for n in self.notes]
        return "\n".join(lines)


def replay_leg(mod, *, start: int = 0, end: Optional[int] = None,
               equity_usd: float = 100_000.0,
               spread_bps: float = 0.0,
               with_disaster_stop: bool = False) -> Dict[str, object]:
    """Chạy ĐƯỜNG LIVE của MỘT chân trên dữ liệu lịch sử.

    `mod` là module chiến lược (có `_load`, `live_decision`, `CONFIG`, `NAME`…).
    `spread_bps=0` để so RIÊNG phần logic vị thế với backtest — chi phí đã được
    backtest cộng riêng, nên bật spread ở đây sẽ trừ hai lần.

    `with_disaster_stop=False` mặc định vì cầu chì là lớp CHỈ CÓ ở live; bật lên để
    đo riêng nó tốn bao nhiêu (đã đo ở `research/fx/sl_test.py`: −1,5% Sharpe).
    """
    from src.python.execution.order_router import OrderRouter

    ins = mod._load()
    df = ins.df
    end = len(df) if end is None else int(end)
    symbol = mod.INSTRUMENT
    tf = mod.TIMEFRAME

    broker = SimBroker({symbol: df}, spread_bps=spread_bps, balance=equity_usd)
    # `dry_run=False` để đi qua ĐÚNG nhánh gửi thật — đó là thứ cần đo.
    # `simulation=True` để nhánh ấy KHÔNG chạm trạng thái vận hành: không email,
    # không sổ khoá bền vững, không nhật ký quyết định. Xem `OrderRouter.__init__`.
    router = OrderRouter(broker, dry_run=False, breaker=None, simulation=True)
    book = PositionBook(_tmp_book_path())
    leg = f"{mod.NAME}"

    decisions: List[str] = []
    pending: Optional[int] = None      # chiều mong muốn, chờ khớp ở nến KẾ TIẾP

    for i in range(max(start, 2), end):
        broker.step(i)

        # ── KHỚP Ý ĐỊNH CỦA NẾN TRƯỚC, tại giá MỞ CỬA nến này.
        # Thẻ luật của mọi chân ghi "khớp tại giá MỞ CỬA nến kế tiếp sau nến tín
        # hiệu", và `entry_signals()` đã `.shift(1)` đúng vì lý do đó. Khớp ngay
        # tại nến tín hiệu là dùng giá đóng cửa mà lúc ra quyết định chưa có —
        # bản đầu của driver này làm vậy và cho lệch MỘT NẾN có hệ thống, khớp
        # điểm vào rơi xuống 2,4%.
        if pending is not None:
            broker.price_at = "open"          # VÀO lệnh: mở cửa nến kế tiếp
            _execute(pending, leg, symbol, tf, book, broker, router, df, i,
                     with_disaster_stop=with_disaster_stop)
            pending = None

        # Vị thế bị cầu chì đóng lúc bước nến → sổ phải biết, nếu không chân đó
        # vĩnh viễn không mở lại được (`open()` báo trùng).
        if book.get(leg) is not None and not broker.positions_get(symbol):
            book.close(leg, reason="cầu chì nổ trên broker ảo")

        held = book.bars_held(leg, df.index[:i + 1])
        # CHIỀU vị thế lấy từ SỔ, và nó BẮT BUỘC: lối thoát "z qua 0" của chân
        # Z-Band cần biết chiều. Bỏ nó thì lối thoát đó im và 88% số lệnh chạy tới
        # time-stop — đúng bug mà kiểm định này tìm ra ngày 15/08/2026.
        _held_pos = book.get(leg)
        cur_side = 0 if _held_pos is None else (
            1 if _held_pos.side == "BUY" else -1)
        d = _decide(mod, df.iloc[:i + 1], ins, held, cur_side)
        action = str(getattr(d, "action", "FLAT"))
        decisions.append(action)

        pos = book.get(leg)
        want = 0
        if action == "BUY":
            want = 1
        elif action == "SELL":
            want = -1
        elif action == "HOLD" and pos is not None:
            want = 1 if pos.side == "BUY" else -1

        cur = 0 if pos is None else (1 if pos.side == "BUY" else -1)
        if want == cur:
            continue

        # ⚠️ HAI QUY ƯỚC KHỚP LỆNH KHÁC NHAU TRONG CÙNG MỘT ENGINE — phát hiện
        # 15/08/2026 khi dựng kiểm định parity, và phải mô phỏng đúng cả hai thì
        # hai hệ mới so được với nhau:
        #
        #     VÀO lệnh   `entry_signals()` đã `.shift(1)`, và `entry = o[i]`
        #                → tín hiệu ở nến t, khớp ở MỞ CỬA nến t+1.  THẬN TRỌNG.
        #     THOÁT lệnh `exit_px = c[j]` ngay tại nến phát hiện điều kiện thoát
        #                → khớp ở ĐÓNG CỬA nến t, KHÔNG trễ một nến.  LẠC QUAN HƠN.
        #
        # Cả hai đều tự nó hợp lý (bot chạy ngay sau khi nến đóng), nhưng chúng
        # KHÔNG giống nhau, và trước hôm nay không có chỗ nào ghi điều đó. Bản đầu
        # của driver này áp quy ước "trễ một nến" cho CẢ HAI chiều và mọi lệnh
        # thoát ra chậm đúng một nến — khớp điểm vào chỉ đạt 56%.
        if want == 0 or (cur != 0 and want != cur):
            broker.price_at = "close"         # THOÁT: đóng cửa nến hiện tại
            _execute(want, leg, symbol, tf, book, broker, router, df, i,
                     with_disaster_stop=with_disaster_stop,
                     exit_reason=_exit_reason(d, want, cur))
            if want != 0:
                continue                      # đảo chiều đã xử lý trọn ở đây

            # ĐÁNH GIÁ LẠI NGAY TRÊN CÙNG NẾN sau khi thoát.
            #
            # Backtest thoát ở nến j rồi quét tiếp từ j+1 với tín hiệu `B[j+1]` —
            # mà tín hiệu đó đã `.shift(1)` nên nó dựng từ dữ liệu tới hết nến j.
            # Tức backtest DÙNG ĐƯỢC tín hiệu của chính nến vừa thoát.
            #
            # `live_decision()` không làm được vậy trong MỘT lần gọi: khi đang giữ
            # vị thế và time-stop kích hoạt, nó trả `FLAT` và dừng ở đó — nhánh
            # BUY/SELL nằm sau `else` của `bars_held > 0`. Gọi một lần thì lệnh
            # mới phải đợi thêm một nến, và đo được nó làm khớp điểm vào dừng ở
            # 58,7%.
            #
            # Nên: gọi LẦN HAI với `bars_held = 0` (đã hết vị thế) để hỏi "giờ
            # không còn gì trong tay, có tín hiệu vào không?". Đây cũng là hành vi
            # mà engine live PHẢI có — nếu không, mỗi lần thoát là mất một nến.
            d2 = _decide(mod, df.iloc[:i + 1], ins, 0, 0)
            a2 = str(getattr(d2, "action", "FLAT"))
            if a2 in ("BUY", "SELL"):
                pending = 1 if a2 == "BUY" else -1
        else:
            pending = want                    # VÀO: chờ mở cửa nến kế tiếp

    return {"broker": broker, "book": book, "decisions": decisions,
            "bars": df.iloc[start:end]}


def _exit_reason(decision, want: int, cur: int) -> str:
    """Phân loại LÝ DO THOÁT từ chính quyết định của chiến lược.

    ⚠️ THÊM 15/08/2026 — TRƯỚC ĐÓ MỌI LỆNH ĐỀU MANG MỘT NHÃN.
    `SimBroker.round_trips()` lấy `f.reason or f.action`, mà driver này không
    truyền `reason` nào, nên 673/673 lệnh của vòng 2026 hiện đúng một dòng "đóng
    theo lệnh ngược chiều". Đo lại bằng tay: **113 lệnh (16,8%) thật ra chạm
    time-stop** — mất hẳn trong báo cáo.

    Vì sao điều đó nghiêm trọng: bảng lý-do-đóng là thứ ĐẦU TIÊN phải nhìn khi
    live lệch khỏi backtest (xem `exit_manager.summarise`). Tỷ lệ TIMESTOP ở live
    khác backtest nghĩa là đồng hồ time-stop sai; DISASTER_STOP xuất hiện nhiều
    nghĩa là cầu chì quá gần. Một bảng chỉ có một dòng thì không phát hiện được gì.

    Nguồn phân loại là chuỗi `reason` mà `live_decision` trả về — cùng chuỗi mà
    đường live ghi vào `rule_trace`, nên hai bên đọc được cùng một thứ.
    """
    txt = str(getattr(decision, "reason", "") or "").lower()
    if cur != 0 and want != 0:
        return "REVERSE"
    if "time-stop" in txt or "time stop" in txt or "hết hạn" in txt:
        return "TIME_STOP"
    if "qua 0" in txt or "hồi quy" in txt or "trung bình" in txt:
        return "MEAN"
    if "ngược chiều" in txt or "đảo" in txt:
        return "SIGNAL"
    return "SIGNAL"


def _execute(want: int, leg: str, symbol: str, tf: str, book, broker, router,
             df: pd.DataFrame, i: int, *, with_disaster_stop: bool,
             exit_reason: str = "") -> None:
    """Khớp ý định của nến trước tại giá MỞ CỬA nến `i`."""
    pos = book.get(leg)
    cur = 0 if pos is None else (1 if pos.side == "BUY" else -1)
    if want == cur:
        return

    plan = _mini_plan(symbol, cur, want, broker, i,
                      with_disaster_stop=with_disaster_stop,
                      exit_reason=exit_reason)
    if plan is None:
        return
    router.route(plan, bar_utc=str(df.index[i]), log_decisions=False)

    if want == 0:
        book.close(leg, reason="tín hiệu thoát")
        return
    if pos is not None:
        book.close(leg, reason="đảo chiều")
    px = float(broker.symbol_info(symbol).ask if want > 0
               else broker.symbol_info(symbol).bid)
    book.open(leg, symbol=symbol, side="BUY" if want > 0 else "SELL",
              lots=1.0, entry_bar_utc=str(df.index[i]),
              entry_price=px, timeframe=tf)


def _decide(mod, sub: pd.DataFrame, ins, held: int, side: int = 0):
    """Gọi ĐÚNG hàm quyết định của họ chiến lược trên dữ liệu đã cắt.

    `side` BẮT BUỘC cho chân Z-Band: lối thoát "z qua 0" cần biết chiều, và bỏ nó
    thì lối thoát đó im — 88% số lệnh sẽ chạy tới time-stop thay vì thoát ở trung
    bình. Đây chính là bug mà kiểm định parity tìm ra ngày 15/08/2026.
    """
    raise NotImplementedError(
        f"{mod.__name__}: cổng parity này được dựng cho hai họ `asia_sweep_core` và "
        f"`asia_sweep_core`, cả hai đã XOÁ ngày 25/08/2026 cùng danh mục nhiều chân.\n"
        f"\n"
        f"VÌ SAO KHÔNG PORT THẲNG ĐƯỢC sang `AsiaSweepH1` — ba giả định của vòng "
        f"replay ở `replay_leg()` không còn đúng:\n"
        f"  · `bars_held`/`side` — chân cũ thoát bằng time-stop theo SỐ NẾN và bằng "
        f"'z qua 0'. Chân mới thoát bằng SL/TP trên SERVER và bằng GIỜ trong phiên, "
        f"nên hai tham số đó không mô tả trạng thái của nó.\n"
        f"  · `ins.cost_1rt_bps` / `swap_bps_per_bar` — chi phí ước lượng theo nến. "
        f"Chân mới đọc spread THẬT tại phút khớp, và không giữ qua đêm nên không có "
        f"swap.\n"
        f"  · một khung duy nhất — chân mới cần M1 để đua SL/TP trong nến, còn tín "
        f"hiệu ở H1.\n"
        f"\n"
        f"THỨ THAY THẾ, và nó đã chạy: `asia_sweep_core.simulate_path()` chạy vị thế "
        f"trên nến M1 với đúng ngữ nghĩa SL/TP nằm trên server (SL được tính TRƯỚC "
        f"trong cùng một phút — giả định bảo thủ, xem docstring của hàm đó).\n"
        f"\n"
        f"CÒN THIẾU, và phải dựng lại: đoạn SAU quyết định — `order_plan.build()` -> "
        f"`order_router.route()` -> `SimBroker.order_send()` -> `PositionBook`, tức "
        f"đúng phần mà module này sinh ra để kiểm. `tests/test_live_path.py` và "
        f"`tests/test_execution_layer.py` phủ một phần, nhưng không phủ vòng replay "
        f"nhiều nghìn nến.")


def _mini_plan(symbol: str, cur: int, want: int, broker: SimBroker, i: int,
               *, with_disaster_stop: bool, exit_reason: str = ""):
    """Kế hoạch một-công-cụ, đúng dạng `order_router.route()` nhận.

    KHÔNG gọi `order_plan.build()` ở đây: hàm đó cần `PortfolioTargets` của toàn bộ
    chân và mỗi lần gọi chạy lại toàn bộ backtest (~130 giây). Kiểm định parity cần
    hàng nghìn lượt, nên phần được kiểm ở đây là ĐOẠN SAU của đường live — phân loại
    việc phải làm, đảo chiều thành hai lệnh, gắn cầu chì, khớp qua broker, cập nhật
    sổ. Phần cổng an toàn và quy tỷ trọng có test riêng ở `tests/test_live_path.py`.
    """
    from src.python.execution.order_plan import OrderAction

    if want == 0:
        action, side, lots = "CLOSE", ("SELL" if cur > 0 else "BUY"), 1.0
    elif cur == 0:
        action, side, lots = "OPEN", ("BUY" if want > 0 else "SELL"), 1.0
    else:
        action, side, lots = "REVERSE", ("BUY" if want > 0 else "SELL"), 2.0

    stop = None
    if with_disaster_stop and want != 0:
        px = float(broker._bar(symbol)["close"])
        stop = px * (1 - 0.049) if want > 0 else px * (1 + 0.049)

    act = OrderAction(symbol=symbol, action=action, side=side, lots=lots,
                      current_lots=float(cur), target_lots=float(want),
                      target_weight=0.1, stop_price=stop,
                      reason=exit_reason)

    class _P:
        allowed = True
        leverage = 1.0
        actions = [act]
        gate = type("G", (), {"explain": lambda s: "ok"})()

        @property
        def to_trade(self):
            return [act]

    return _P()


def compare(mod, report_leg: Optional[str] = None, **kw) -> ParityReport:
    """Chạy replay rồi so chuỗi lệnh với `mod.backtest()`."""
    out = replay_leg(mod, **kw)
    broker: SimBroker = out["broker"]
    bars: pd.DataFrame = out["bars"]

    bt = mod.backtest().trades
    if not bt.empty:
        lo, hi = bars.index[0], bars.index[-1]
        bt = bt[(bt["entry_time"] >= lo) & (bt["entry_time"] <= hi)]

    live = broker.round_trips()
    bt_entries = {str(t) for t in bt["entry_time"]} if not bt.empty else set()
    lv_entries = {str(t) for t in live["entry_time"]} if not live.empty else set()

    rep = ParityReport(
        leg=report_leg or mod.NAME, symbol=mod.INSTRUMENT,
        n_backtest=len(bt), n_live=len(live),
        matched=len(bt_entries & lv_entries),
        only_backtest=sorted(bt_entries - lv_entries),
        only_live=sorted(lv_entries - bt_entries),
        gross_backtest_bps=float(bt["gross_bps"].sum()) if not bt.empty else 0.0,
        gross_live_bps=float(live["gross_bps"].sum()) if not live.empty else 0.0)

    if broker.rejected:
        rep.notes.append(f"{len(broker.rejected)} lệnh bị broker ảo từ chối")
    n_sl = sum(1 for f in broker.fills if f.action == "SL_HIT")
    if n_sl:
        rep.notes.append(f"{n_sl} lần cầu chì nổ — lớp CHỈ CÓ ở live")
    return rep


def _tmp_book_path():
    import tempfile
    from pathlib import Path

    return Path(tempfile.mkdtemp()) / "parity_book.json"
