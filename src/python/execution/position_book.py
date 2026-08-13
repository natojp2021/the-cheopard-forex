"""position_book.py — SỔ VỊ THẾ BỀN VỮNG: chân nào đang giữ gì, và giữ được bao lâu.

LỖ HỔNG MÀ MODULE NÀY BỊT — NGHIÊM TRỌNG NHẤT TÌM ĐƯỢC TRONG ĐỢT KIỂM TOÁN
===========================================================================
Cả 27 chân thoát lệnh bằng ĐÚNG HAI cách: tín hiệu ngược chiều, và **time-stop**.
Không chân nào có dừng lỗ theo giá (đo được là làm tệ đi — `research/fx/sl_test.py`).
Nghĩa là time-stop không phải một lớp phụ; với phần lớn lệnh nó là lối thoát DUY NHẤT.

Time-stop cần `bars_held`. Trước 14/08/2026, `bars_held` **không có ai tính**:

    live_decision(start, bars_held=0)     ← mọi nơi gọi đều truyền 0
    portfolio.single_leg_decisions()      ← nhận `bars_held` nhưng không ai đưa vào
    (không module nào sinh ra giá trị này)

Hậu quả nếu chạy thật: mỗi chu kỳ, chân đang giữ lệnh nhận `bars_held = 0`, nên
điều kiện `bars_held >= timestop` KHÔNG BAO GIỜ đúng, và **vị thế được giữ vô hạn**.
Với chân H4 time-stop 12 nến (2 ngày) thì đó là một vị thế lẽ ra đóng sau hai ngày
nhưng nằm lại nhiều tuần. Không có exception, không có test đỏ — đúng lớp lỗi im
lặng đã tìm thấy ba lần trong đợt này.

Bot khởi động lại còn tệ hơn: kể cả có tính `bars_held` trong RAM thì restart cũng
xoá sạch. Vì vậy sổ này phải BỀN VỮNG trên đĩa, ghi bằng
`state_store.save_json_atomic` (temp → flush → fsync → replace), pattern học từ
`xaubot-ai` qua hệ XAUUSD.

ĐẾM NẾN, KHÔNG ĐẾM GIỜ ĐỒNG HỒ
===============================
`bars_held` phải là SỐ NẾN ĐÃ ĐÓNG kể từ nến vào lệnh, không phải số giờ trôi qua.
Hai thứ khác nhau ở mọi cuối tuần và mọi ngày lễ: từ 17:00 thứ Sáu tới 09:00 thứ Hai
là 64 giờ đồng hồ nhưng **0 nến**. Quy đổi bằng giờ sẽ đóng lệnh sớm hai ngày mỗi
tuần, và đóng sai thời điểm là lệch hẳn khỏi hành vi mà backtest đã đo.

Nên `bars_held()` nhận chính chỉ mục nến của công cụ đó — cùng nguồn dữ liệu mà
backtest dùng. Đó là điều kiện để live và backtest cùng đếm một kiểu.

ĐỐI SOÁT — BA NHÓM, KHÔNG PHẢI HAI
===================================
So sổ với vị thế thật trên broker cho ba nhóm, và cả ba đều phải xử lý khác nhau:

    KHỚP     sổ có, broker có       → bình thường
    MỒ CÔI   broker có, sổ KHÔNG    → vị thế lạ: người mở tay, hoặc sổ đã mất.
                                      KHÔNG được tự đóng (có thể là lệnh của hệ
                                      khác trên cùng tài khoản), KHÔNG được coi là
                                      của mình. Chặn vào lệnh mới cho tới khi người
                                      vận hành quyết định.
    ĐÃ ĐÓNG  sổ có, broker KHÔNG    → lệnh đã đóng lúc bot không chạy (SL thảm hoạ
                                      nổ, hoặc đóng tay). Ghi nhận và xoá khỏi sổ.

Nhóm MỒ CÔI là lý do `reconciliation_done` tồn tại trong `entry_gate`: chừng nào còn
vị thế không rõ chủ, mọi phép tính phơi nhiễm đều thiếu, và cấp thêm rủi ro lên trên
một con số đã sai là cách mất tài khoản. Hệ XAUUSD học đúng bài này trong
`core/execution/reconciliation.py` (533 dòng, giao thức 5 bước); bản ở đây rút gọn
cho mô hình danh mục nhưng giữ nguyên bất biến: **không đối soát xong thì không vào
lệnh mới**.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

from src.python.core.infra import state_store
from src.python.shared.paths import RUNTIME_STATE_DIR

BOOK_PATH = Path(RUNTIME_STATE_DIR) / "position_book.json"


def _build_now() -> str:
    """Bản build ĐANG chạy. Chụp lúc mở lệnh, không đọc lại lúc gửi thư."""
    try:
        from src.python.core.runtime_meta import version

        return version()
    except Exception:
        return ""


def _login_now() -> str:
    """Tài khoản MT5 THẬT đang đăng nhập, không phải giá trị trong `.env`.

    Hai thứ có thể lệch nhau — đó chính là sự cố `account_mismatch`. Ghi cái THẬT
    để sau này truy được lệnh đã đi vào tài khoản nào.
    """
    try:
        import MetaTrader5 as mt5

        ai = mt5.account_info()
        if ai is not None:
            return str(ai.login)
    except Exception:
        pass
    import os

    return os.environ.get("MT5_LOGIN", "")


@dataclass
class LegPosition:
    """Một vị thế do MỘT chân sở hữu."""
    leg: str                      # khoá chân, vd "zb_audcad_h1"
    symbol: str
    side: str                     # BUY | SELL
    lots: float
    entry_bar_utc: str            # thời điểm NẾN vào lệnh, ISO UTC
    entry_price: float
    timeframe: str                # M30 | H1 | H4 | D1
    stop_price: Optional[float] = None
    opened_at_utc: str = ""       # thời điểm gửi lệnh thật, để đối chiếu với broker
    note: str = ""

    # ── TRƯỜNG KIỂM TOÁN, thêm 15/08/2026
    #
    # VÌ SAO PHẢI CHỤP LÚC VÀO LỆNH, KHÔNG ĐỌC LẠI LÚC GỬI THƯ:
    # Thư đóng lệnh gửi hàng giờ — có khi hàng ngày — sau khi lệnh mở. Đọc lại
    # `runtime_meta.version()` hay `MT5_LOGIN` ở thời điểm ấy cho ra trạng thái
    # HIỆN TẠI, không phải trạng thái lúc lệnh được sinh ra. Sau một lần nạp bản
    # mới giữa chừng, thư sẽ nói lệnh do bản build mới sinh ra — sai, và sai đúng
    # ở ô mà người ta dùng để truy "lệnh này do bản nào".
    #
    # `equity_at_entry` là mẫu số của mọi phép kiểm cỡ lệnh: cỡ lệnh ở đây là
    # `lot = equity × leverage × w / notional`, nên không có equity lúc vào thì
    # KHÔNG tái kiểm được sizing, tức không phát hiện được sizing sai.
    equity_at_entry: float = 0.0      # mẫu số để tái kiểm cỡ lệnh
    leverage_at_entry: float = 0.0    # đòn bẩy chính sách cấp lúc đó
    weight_at_entry: float = 0.0      # tỷ trọng mục tiêu của chân
    notional_usd: float = 0.0         # phơi nhiễm USD lúc mở
    ticket: int = 0                   # ticket broker, để đối chiếu lịch sử MT5
    magic: int = 0
    build: str = ""                   # bản build SINH RA lệnh này
    account_login: str = ""           # tài khoản THẬT lúc mở, không phải .env lúc gửi thư

    @property
    def signed_lots(self) -> float:
        return self.lots if self.side == "BUY" else -self.lots


@dataclass
class ReconcileResult:
    """Kết quả đối soát sổ với broker."""
    matched: List[str] = field(default_factory=list)      # khoá chân
    orphan: List[str] = field(default_factory=list)       # symbol trên broker, không có chủ
    closed_elsewhere: List[str] = field(default_factory=list)  # khoá chân
    lot_mismatch: Dict[str, Dict[str, float]] = field(default_factory=dict)
    problems: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Đối soát SẠCH. `entry_gate.reconciliation_done` lấy đúng giá trị này."""
        return not self.orphan and not self.lot_mismatch and not self.problems

    def explain(self) -> str:
        head = (f"đối soát: {len(self.matched)} khớp · {len(self.orphan)} mồ côi · "
                f"{len(self.closed_elsewhere)} đã đóng ngoài hệ")
        if self.ok:
            return head + " · SẠCH"
        return head + "\n  " + "\n  ".join(
            self.problems
            + [f"MỒ CÔI {s} — vị thế không rõ chủ trên broker" for s in self.orphan]
            + [f"LỆCH LOT {k}: sổ {v['sổ']} vs broker {v['broker']}"
               for k, v in self.lot_mismatch.items()])


class PositionBook:
    """Sổ vị thế bền vững. Mọi thay đổi ghi xuống đĩa ngay, không đợi tắt máy."""

    def __init__(self, path: Path = BOOK_PATH):
        self.path = Path(path)
        self._pos: Dict[str, LegPosition] = {}
        self.load()

    # ─────────────────────────────────────────────── bền vững
    def load(self) -> None:
        data = state_store.load_json(self.path) or {}
        self._pos = {}
        for leg, d in (data.get("positions") or {}).items():
            try:
                self._pos[leg] = LegPosition(**d)
            except TypeError:
                # Sổ cũ thiếu trường mới: bỏ dòng hỏng chứ không nuốt cả sổ. Mất một
                # dòng thì đối soát báo MỒ CÔI và người vận hành thấy; nuốt cả sổ thì
                # hệ tưởng mình không giữ gì.
                continue

    def save(self) -> bool:
        return state_store.save_json_atomic(self.path, {
            "updated_utc": datetime.now(timezone.utc).isoformat(),
            "positions": {k: asdict(v) for k, v in self._pos.items()},
        })

    # ─────────────────────────────────────────────── truy vấn
    def __len__(self) -> int:
        return len(self._pos)

    def get(self, leg: str) -> Optional[LegPosition]:
        return self._pos.get(leg)

    def all(self) -> Dict[str, LegPosition]:
        return dict(self._pos)

    def sides(self) -> Dict[str, int]:
        """Chiều đang giữ của từng chân — đầu vào `positions=` của `target_weights()`."""
        return {k: (1 if v.side == "BUY" else -1) for k, v in self._pos.items()}

    def symbol_lots(self) -> Dict[str, float]:
        """Lot RÒNG theo công cụ theo sổ. Dùng để so với broker."""
        out: Dict[str, float] = {}
        for p in self._pos.values():
            out[p.symbol] = out.get(p.symbol, 0.0) + p.signed_lots
        return out

    # ─────────────────────────────────────────────── đồng hồ time-stop
    def bars_held(self, leg: str, bar_index: pd.DatetimeIndex) -> int:
        """Số nến ĐÃ ĐÓNG kể từ nến vào lệnh. `0` khi chân không giữ vị thế.

        `bar_index` là chỉ mục nến của đúng công cụ và đúng khung của chân đó, lấy
        từ cùng nguồn dữ liệu mà backtest dùng — đó là điều kiện để live và backtest
        đếm giống nhau.

        Đếm NẾN chứ không đếm giờ: từ 17:00 thứ Sáu tới 09:00 thứ Hai là 64 giờ nhưng
        0 nến, và quy đổi bằng giờ sẽ đóng lệnh sớm hai ngày mỗi tuần.
        """
        p = self._pos.get(leg)
        if p is None:
            return 0
        entry = pd.Timestamp(p.entry_bar_utc)
        if entry.tzinfo is not None:
            entry = entry.tz_convert(None)
        idx = pd.DatetimeIndex(bar_index)
        if idx.tz is not None:
            idx = idx.tz_convert(None)
        return int((idx > entry).sum())

    def all_bars_held(self, bar_indexes: Dict[str, pd.DatetimeIndex]) -> Dict[str, int]:
        """`bars_held` cho mọi chân đang giữ vị thế. Chân thiếu chỉ mục → bỏ qua.

        Bỏ qua chứ KHÔNG trả 0: 0 nghĩa là "vừa vào lệnh", và nói vậy với một chân đã
        giữ ba tuần là tự tay tắt time-stop của nó.
        """
        out: Dict[str, int] = {}
        for leg in self._pos:
            idx = bar_indexes.get(leg)
            if idx is not None:
                out[leg] = self.bars_held(leg, idx)
        return out

    # ─────────────────────────────────────────────── thay đổi sổ
    def open(self, leg: str, *, symbol: str, side: str, lots: float,
             entry_bar_utc: str, entry_price: float, timeframe: str,
             stop_price: Optional[float] = None, note: str = "",
             equity_at_entry: float = 0.0, leverage_at_entry: float = 0.0,
             weight_at_entry: float = 0.0, notional_usd: float = 0.0,
             ticket: int = 0, magic: int = 0) -> LegPosition:
        """Ghi nhận một vị thế MỚI. Ghi đĩa ngay."""
        if leg in self._pos:
            raise ValueError(
                f"{leg} đã có vị thế trong sổ ({self._pos[leg].symbol} "
                f"{self._pos[leg].side}). Mỗi chân giữ TỐI ĐA một vị thế — "
                f"`max_positions=1` trong mọi thẻ luật. Đóng trước khi mở lại.")
        p = LegPosition(
            leg=leg, symbol=symbol, side=side.upper(), lots=float(lots),
            entry_bar_utc=str(entry_bar_utc), entry_price=float(entry_price),
            timeframe=timeframe, stop_price=stop_price,
            opened_at_utc=datetime.now(timezone.utc).isoformat(), note=note,
            equity_at_entry=float(equity_at_entry),
            leverage_at_entry=float(leverage_at_entry),
            weight_at_entry=float(weight_at_entry),
            notional_usd=float(notional_usd),
            ticket=int(ticket), magic=int(magic),
            # Chụp NGAY, không đọc lại lúc gửi thư — xem chú thích ở `LegPosition`.
            build=_build_now(), account_login=_login_now())
        self._pos[leg] = p
        self.save()
        return p

    def close(self, leg: str, reason: str = "") -> Optional[LegPosition]:
        """Xoá khỏi sổ. Trả về bản ghi vừa xoá để bên gọi ghi nhật ký."""
        p = self._pos.pop(leg, None)
        if p is not None:
            self.save()
        return p

    def update_lots(self, leg: str, lots: float) -> None:
        p = self._pos.get(leg)
        if p is not None:
            p.lots = float(lots)
            self.save()

    # ─────────────────────────────────────────────── đối soát
    def reconcile(self, broker_positions: Iterable, *,
                  tolerance_lots: float = 0.01,
                  auto_close_missing: bool = True) -> ReconcileResult:
        """So sổ với vị thế THẬT trên broker. Trả kết quả, KHÔNG tự đặt lệnh.

        `broker_positions` là các đối tượng có `symbol`, `volume`, `type`
        (0 = mua, 1 = bán) — đúng thứ `mt5.positions_get()` trả về.

        `auto_close_missing=True` xoá khỏi sổ những chân mà broker không còn vị thế:
        đó là chuyện BÌNH THƯỜNG (cầu chì nổ, hoặc người vận hành đóng tay), và giữ
        lại thì chân đó vĩnh viễn không vào lệnh mới được vì `open()` sẽ báo trùng.

        MỒ CÔI thì TUYỆT ĐỐI không tự xử lý — xem docstring đầu file.
        """
        res = ReconcileResult()
        broker: Dict[str, float] = {}
        for p in broker_positions:
            sym = str(getattr(p, "symbol", ""))
            vol = float(getattr(p, "volume", 0.0) or 0.0)
            side = 1.0 if int(getattr(p, "type", 0)) == 0 else -1.0
            broker[sym] = broker.get(sym, 0.0) + side * vol

        book = self.symbol_lots()

        for sym, blots in broker.items():
            if abs(blots) < 1e-9:
                continue
            if sym not in book or abs(book[sym]) < 1e-9:
                res.orphan.append(sym)
            elif abs(book[sym] - blots) > tolerance_lots:
                res.lot_mismatch[sym] = {"sổ": round(book[sym], 3),
                                         "broker": round(blots, 3)}

        for leg, p in list(self._pos.items()):
            if abs(broker.get(p.symbol, 0.0)) < 1e-9:
                res.closed_elsewhere.append(leg)
                if auto_close_missing:
                    self.close(leg, reason="broker không còn vị thế")
            else:
                res.matched.append(leg)

        if res.closed_elsewhere:
            res.problems.append(
                f"{len(res.closed_elsewhere)} chân có trong sổ nhưng broker không còn "
                f"vị thế ({', '.join(res.closed_elsewhere[:5])}) — đã xoá khỏi sổ. "
                f"Nguyên nhân thường gặp: cầu chì thảm hoạ đã nổ, hoặc đóng tay.")
        return res


# ═══════════════════════════════════════════════════════ tiện ích cho engine
def sync_from_targets(book: "PositionBook", targets, prices: Dict[str, float],
                      *, lots_by_symbol: Optional[Dict[str, float]] = None
                      ) -> Dict[str, str]:
    """Cập nhật sổ theo Ý ĐỊNH của từng chân sau khi kế hoạch đã được gửi.

    ⚠️ LỖI ĐÃ SỬA 15/08/2026 — TRƯỚC ĐÓ KHÔNG AI GHI VÀO SỔ TRÊN ĐƯỜNG LIVE
    ======================================================================
    `book.open()` chỉ được gọi từ `execution/parity.py`, tức chỉ trong bộ mô phỏng
    chạy tay. Đường live gửi lệnh xong rồi thôi. Sổ vĩnh viễn RỖNG, và bốn thứ chết
    theo, tất cả đều IM LẶNG:

      1. `all_bars_held()` trả `{}` → mọi chân nhận `bars_held = 0` → **TIME-STOP
         KHÔNG BAO GIỜ KÍCH HOẠT**. Với phần lớn chân, time-stop là lối thoát DUY
         NHẤT (không chân nào có SL theo giá), nên vị thế được giữ vô hạn.
      2. `sides()` trả `{}` → `target_weights(positions=None)` → chân trả `HOLD`
         bị coi như đứng ngoài, và hai chân ngược chiều không triệt tiêu nhau.
      3. `reconcile()` thấy MỌI vị thế thật là MỒ CÔI → `rec.ok` False → cổng
         fail-closed chặn → sau lệnh ĐẦU TIÊN, hệ tự khoá mình vĩnh viễn.
      4. `_finalise_closed()` không bao giờ chạy → không có bản ghi thoát, không
         có email đóng lệnh, không có MFE/MAE.

    Đây đúng loại lỗi mà CLAUDE.md đã ghi ở mục "Hỏng thì NỔ": `bars_held` không ai
    tính nên time-stop không bao giờ kích hoạt — nó quay lại ở tầng khác.

    VÌ SAO ĐỒNG BỘ TỪ Ý ĐỊNH CHỨ KHÔNG TỪ FILL CỦA BROKER
    ======================================================
    Sổ ghi theo CHÂN, còn broker giữ vị thế theo CÔNG CỤ. AUDCAD có ba chân cùng
    nhắm vào nó, và `order_plan` gộp chúng thành MỘT lệnh ròng — nên một vị thế
    broker không quy ngược ra được chân nào. Chiều đúng của từng chân chỉ có ở
    `targets.single_decisions`, và `reconcile()` so hai bên ở mức CÔNG CỤ
    (`symbol_lots()` tự cộng các chân lại) nên hai cách ghi vẫn khớp nhau.

    `lots_by_symbol` là lot RÒNG mục tiêu theo công cụ; chia đều cho các chân cùng
    công cụ và cùng chiều. Không truyền thì ghi 0 lot — sổ vẫn đúng về CHIỀU và về
    `bars_held`, chỉ phần đối chiếu lot là không dùng được.
    """
    from src.python.strategies import portfolio as PF
    from src.python.strategies import registry as REG

    changes: Dict[str, str] = {}
    decisions = dict(getattr(targets, "single_decisions", {}) or {})
    if not decisions:
        return changes

    # Chiều mục tiêu của từng chân, có tính `HOLD` = giữ nguyên chiều đang có.
    current = book.sides()
    wanted: Dict[str, int] = {}
    for leg, dec in decisions.items():
        wanted[leg] = PF._side_of(dec, previous=current.get(leg, 0))

    # Đếm số chân CÙNG công cụ VÀ cùng chiều để chia lot.
    per_symbol: Dict[str, int] = {}
    meta: Dict[str, tuple] = {}
    for leg, side in wanted.items():
        name = PF.SINGLE_LEGS.get(leg)
        spec = REG.by_name(name) if name else None
        if spec is None or not spec.symbols:
            continue
        meta[leg] = (spec.symbols[0], spec.signal_tf)
        if side != 0:
            per_symbol[spec.symbols[0]] = per_symbol.get(spec.symbols[0], 0) + 1

    asof = str(getattr(targets, "asof", "") or "")
    for leg, side in wanted.items():
        if leg not in meta:
            continue
        symbol, tf = meta[leg]
        cur = current.get(leg, 0)
        if side == cur:
            continue
        if cur != 0:
            book.close(leg, reason="đảo chiều" if side else "tín hiệu thoát")
            changes[leg] = "ĐÓNG" if side == 0 else "ĐẢO"
        if side == 0:
            continue
        px = float(prices.get(symbol) or 0.0)
        if px <= 0:
            # KHÔNG ghi vị thế với giá 0: `entry_price` sai làm mọi phép đo lãi/lỗ
            # và MFE/MAE sau này sai theo, mà không có gì báo.
            changes[leg] = "BỎ QUA — không có giá"
            continue
        n = max(1, per_symbol.get(symbol, 1))
        lots = abs(float((lots_by_symbol or {}).get(symbol, 0.0))) / n
        book.open(leg, symbol=symbol, side="BUY" if side > 0 else "SELL",
                  lots=round(lots, 2), entry_bar_utc=asof, entry_price=px,
                  timeframe=tf, note="đồng bộ từ kế hoạch")
        changes[leg] = f"MỞ {'BUY' if side > 0 else 'SELL'} {symbol}"
    return changes


def bar_indexes_for(legs: Iterable[str], start: str = "2020-01-01"
                    ) -> Dict[str, pd.DatetimeIndex]:
    """Chỉ mục nến của từng chân, lấy đúng đường dữ liệu mà backtest dùng.

    Nặng (mỗi chân nạp một chuỗi nến), nên bên gọi phải cache theo chu kỳ tái cân
    bằng chứ đừng gọi mỗi vòng lặp giao diện.
    """
    from importlib import import_module

    from src.python.strategies import portfolio as PF
    from src.python.strategies import registry as REG

    out: Dict[str, pd.DatetimeIndex] = {}
    for leg in legs:
        name = PF.SINGLE_LEGS.get(leg)
        if name is None:
            continue
        target = REG.PORTFOLIO["entry_points"][name]
        mod = import_module(target.partition(":")[0])
        try:
            out[leg] = mod._load(start).df.index
        except Exception:                                  # pragma: no cover
            continue
    return out
