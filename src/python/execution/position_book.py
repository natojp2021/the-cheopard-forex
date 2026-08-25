"""position_book.py — SỔ VỊ THẾ BỀN VỮNG. Ai đang giữ cái gì, và có khớp broker không.

VÌ SAO SỔ GHI THEO CHÂN, CÒN BROKER GHI THEO CÔNG CỤ
=====================================================
Một chiến lược chạy nhiều công cụ thì mỗi công cụ là một CHÂN riêng, và mỗi chân có
`magic` riêng. Broker thì chỉ biết vị thế theo CÔNG CỤ. Hai cách ghi khác nhau, nên
phải có một chỗ giữ ánh xạ và một chỗ đối soát.

Thiếu sổ thì không trả lời được: vị thế EURUSD kia là của hệ hay do người vận hành mở
tay? Nó thuộc chân nào? Mở từ nến nào? Không có câu trả lời thì mọi phép tính phơi
nhiễm và mọi quyết định đóng đều đặt trên một con số không kiểm chứng được.

BỀN VỮNG TRÊN ĐĨA, KHÔNG TRONG RAM
===================================
Khởi động lại tiến trình KHÔNG được làm sổ trống. Sổ trống nghĩa là mọi vị thế thật
thành "mồ côi", và hệ sẽ hoặc bỏ mặc chúng, hoặc mở trùng lên chúng.

ĐỐI SOÁT PHẢI XONG TRƯỚC KHI VÀO LỆNH
======================================
`reconcile()` so sổ với `positions_get()` của broker và trả kết quả cho `entry_gate`.
Chưa đối soát xong thì cổng CHẶN — chưa biết vị thế nào là của hệ thì mọi phép tính
phơi nhiễm còn vô nghĩa.

SỔ GHI Ý ĐỊNH THÌ SỔ SẼ NÓI DỐI — LỖI ĐÃ TỪNG XẢY RA
=====================================================
Khi broker TỪ CHỐI một lệnh mà sổ vẫn ghi vị thế (vì sổ ghi theo Ý ĐỊNH chứ theo KẾT
QUẢ), hậu quả không dừng ở một dòng sai:

  * `open()` từ chối mở lại chân đã có trong sổ, nên chân đó KHÔNG THỂ thử lại chừng
    nào bóng ma còn nằm đó.
  * `sides()` báo chân đang giữ lệnh, nên các phép cộng phơi nhiễm sai theo.

`reconcile()` chu kỳ sau dọn được, nhưng giữa hai thời điểm đó hệ ra quyết định trên
một thế giới không có thật — và với sổ vị thế thì "sai rồi tự sửa" không phải thiết kế
chấp nhận được. Nên `sync_from_targets()` nhận `failed_symbols` và KHÔNG ghi gì cho
những công cụ broker đã từ chối.

⚠️ ĐỒNG HỒ `bars_held` KHÔNG CÒN ĐIỀU KHIỂN GÌ
==============================================
Nó được giữ vì nó là dữ liệu chẩn đoán tốt (giữ bao lâu trước khi thoát), nhưng chiến
lược hiện tại KHÔNG thoát theo số nến — nó thoát bằng dừng lỗ/chốt lời trên server và
bằng mốc đóng phiên. Đừng nối lại một lối thoát theo `bars_held` mà không đo trước.
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
    healed_lots: Dict[str, Dict[str, float]] = field(default_factory=dict)
    problems: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Đối soát SẠCH. `entry_gate.reconciliation_done` lấy đúng giá trị này."""
        return not self.orphan and not self.lot_mismatch and not self.problems

    def explain(self) -> str:
        head = (f"đối soát: {len(self.matched)} khớp · {len(self.orphan)} mồ côi · "
                f"{len(self.closed_elsewhere)} đã đóng ngoài hệ")
        if self.healed_lots:
            head += f" · {len(self.healed_lots)} công cụ đã cân lot theo broker"
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

    def _heal_symbol_lots(self, symbol: str, broker_signed_lots: float) -> bool:
        """Cân lot của các chân giữ `symbol` cho khớp broker. True nếu đã cân.

        BROKER LÀ SỰ THẬT, VÀ MỘT CÔNG CỤ LỆCH KHÔNG ĐƯỢC KHOÁ CẢ DANH MỤC
        ================================================================
        Lệch lot đã từng xảy ra: sổ ghi −1.0 còn broker giữ −0.81 (đóng một phần
        ngoài hệ). `ReconcileResult.ok` đòi `lot_mismatch` rỗng, nên 0.19 lot lệch
        trên MỘT công cụ làm `reconciliation_done` False và cổng chặn TOÀN BỘ lệnh
        mới của 27 công cụ — liên tục từ 14:08 tới 21:00, không một lệnh nào.

        `auto_close_missing` đã áp đúng nguyên tắc này cho trường hợp chân biến
        mất: broker là sự thật, giữ lại chỉ làm chân đó vĩnh viễn không vào lệnh
        được. Lệch lot cùng một họ, chỉ khác mức độ.

        Cân theo TỶ LỆ khi nhiều chân cùng giữ một công cụ:
        không có cách nào biết chân nào bị đóng bớt, nên chia đều theo tỷ trọng
        đang giữ. Sai số phân bổ giữa các chân nhỏ hơn hẳn cái giá của việc khoá
        cả danh mục.

        Trả False khi không cân được (tổng sổ bằng 0, hoặc dấu ngược nhau) — lúc
        đó lệch lot là bất thường thật, để nguyên cho cổng fail-closed xử lý.
        """
        legs = [(k, v) for k, v in self._pos.items() if v.symbol == symbol]
        if not legs:
            return False
        current = sum(v.signed_lots for _, v in legs)
        if abs(current) < 1e-9:
            return False
        # Dấu ngược nhau nghĩa là sổ và broker không nói về cùng một chiều —
        # đó là bất thường thật, không phải đóng bớt.
        if current * broker_signed_lots <= 0:
            return False
        # CHỈ cân khi lot GIẢM. Broker giữ NHIỀU hơn sổ là phơi nhiễm không giải
        # thích được — đúng thứ mà cổng fail-closed tồn tại để chặn. Đóng bớt chỉ
        # có thể làm lot nhỏ đi, nên chiều tăng không bao giờ là đóng bớt.
        if abs(broker_signed_lots) > abs(current):
            return False
        scale = broker_signed_lots / current
        for _, v in legs:
            v.lots = round(abs(v.lots * scale), 2)
        self.save()
        return True

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
                  auto_close_missing: bool = True,
                  auto_heal_lots: bool = True,
                  own_magic_base: Optional[int] = None,
                  own_magic_span: int = 90_000) -> ReconcileResult:
        """So sổ với vị thế THẬT trên broker. Trả kết quả, KHÔNG tự đặt lệnh.

        `broker_positions` là các đối tượng có `symbol`, `volume`, `type`
        (0 = mua, 1 = bán) — đúng thứ `mt5.positions_get()` trả về.

        `auto_close_missing=True` xoá khỏi sổ những chân mà broker không còn vị thế:
        đó là chuyện BÌNH THƯỜNG (cầu chì nổ, hoặc người vận hành đóng tay), và giữ
        lại thì chân đó vĩnh viễn không vào lệnh mới được vì `open()` sẽ báo trùng.

        MỒ CÔI thì TUYỆT ĐỐI không tự xử lý — xem docstring đầu file.

        MAGIC LÀ THỨ PHÂN BIỆT "CỦA HỆ" VỚI "MỒ CÔI", KHÔNG PHẢI SỔ CHÂN
        ================================================================
        Sự cố 22:08 ngày 20/08/2026: hệ mở 22 vị thế thành công (`retcode 10009`,
        có SL đủ), rồi TỰ KHOÁ MÌNH ở chu kỳ sau:

            [ĐỐI SOÁT] 0 khớp, 22 lạ, 0 đã đóng nơi khác
            KHÔNG GỬI LỆNH NÀO — CHẶN: đối soát khởi động CHƯA xong

        Nguyên nhân là một giả định sai nằm ngay trong phép so: sổ chỉ ghi
        `PF.SINGLE_LEGS`, còn 22 lệnh kia do các chân XẾP HẠNG (`X-MR-H1`,
        `CCY-REV`, `CCY-CARRY`, `X-XS-H4`, `X-MOM-D1`) sinh ra. Chân xếp hạng
        giao dịch theo RỔ, một chân chạm nhiều công cụ, nên không có khoá chân
        nào để ghi vào sổ. So sổ-chân với vị thế-công cụ thì mọi vị thế của chân
        xếp hạng VĨNH VIỄN là mồ côi, và cổng fail-closed khoá vĩnh viễn theo.

        Câu hỏi mà `orphan` cần trả lời là "vị thế này có phải do HỆ mở không",
        và câu đó có lời đáp chính xác hơn nhiều: MAGIC. `order_router.magic_for`
        sinh magic tất định trong khoảng `[MAGIC_BASE, MAGIC_BASE + 90000)`, và
        mọi lệnh của hệ đều mang nó. Đo lúc 22:14 trên chính tài khoản: 22/22 vị
        thế có magic trong khoảng đó.

        Fail-closed vẫn nguyên vẹn, và đó là điểm quan trọng nhất của bản vá này:
        magic NGOÀI khoảng — lệnh tay, EA khác, bot khác dùng chung tài khoản —
        vẫn là MỒ CÔI và vẫn chặn lệnh mới. Cái bỏ đi chỉ là báo động giả về
        chính vị thế của mình.

        Truyền `own_magic_base=None` để dùng `order_router.MAGIC_BASE`; truyền
        một số âm để tắt hẳn lớp nhận diện này (chỉ dùng trong test).
        """
        res = ReconcileResult()
        if own_magic_base is None:
            try:
                from src.python.execution.order_router import MAGIC_BASE

                own_magic_base = int(MAGIC_BASE)
            except Exception:
                # Không đọc được dải magic thì KHÔNG nhận vơ vị thế nào là của
                # mình: fail-closed đúng hướng, thà báo mồ côi thừa còn hơn bỏ
                # sót một vị thế lạ.
                own_magic_base = -1

        broker: Dict[str, float] = {}
        ours: set = set()
        for p in broker_positions:
            sym = str(getattr(p, "symbol", ""))
            vol = float(getattr(p, "volume", 0.0) or 0.0)
            side = 1.0 if int(getattr(p, "type", 0)) == 0 else -1.0
            broker[sym] = broker.get(sym, 0.0) + side * vol
            magic = int(getattr(p, "magic", 0) or 0)
            if own_magic_base >= 0 and (
                    own_magic_base <= magic < own_magic_base + own_magic_span):
                ours.add(sym)

        book = self.symbol_lots()

        for sym, blots in broker.items():
            if abs(blots) < 1e-9:
                continue
            if sym in ours and (sym not in book or abs(book[sym]) < 1e-9):
                # Vị thế của HỆ nhưng chân xếp hạng không ghi sổ được — bình
                # thường, không phải mồ côi và cũng không phải lệch lot.
                continue
            if sym not in book or abs(book[sym]) < 1e-9:
                res.orphan.append(sym)
            elif abs(book[sym] - blots) > tolerance_lots:
                if auto_heal_lots and self._heal_symbol_lots(sym, blots):
                    res.healed_lots[sym] = {"sổ cũ": round(book[sym], 3),
                                            "broker": round(blots, 3)}
                else:
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
                      *, lots_by_symbol: Optional[Dict[str, float]] = None,
                      failed_symbols: Optional[Iterable[str]] = None
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
    Sổ ghi theo CHÂN, còn broker giữ vị thế theo CÔNG CỤ. Nhiều chân có thể cùng
    nhắm vào một công cụ, và `order_plan` gộp chúng thành MỘT lệnh ròng — nên một vị
    thế broker không quy ngược ra được chân nào. Chiều đúng của từng chân chỉ có ở
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
        # CÔNG CỤ lấy từ `LEG_INSTRUMENT`, KHÔNG từ `spec.symbols[0]`: một chiến lược
        # chạy nhiều công cụ thì `symbols[0]` luôn là công cụ đầu tiên, nên cả ba chân
        # sẽ cùng ghi vị thế lên một cặp. Chỉ lùi về `spec.symbols[0]` cho chân
        # một-công-cụ không khai bảng tra.
        symbol = (getattr(PF, "LEG_INSTRUMENT", {}).get(leg) or spec.symbols[0])
        meta[leg] = (symbol, spec.signal_tf)
        if side != 0:
            per_symbol[symbol] = per_symbol.get(symbol, 0) + 1

    asof = str(getattr(targets, "asof", "") or "")
    failed = {str(s) for s in (failed_symbols or ())}
    for leg, side in wanted.items():
        if leg not in meta:
            continue
        symbol, tf = meta[leg]
        cur = current.get(leg, 0)
        if side == cur:
            continue
        if symbol in failed:
            # BROKER TỪ CHỐI THÌ SỔ KHÔNG ĐƯỢC ĐỔI.
            #
            # Đo 19:14 ngày 20/08/2026: 27 lệnh bị từ chối `retcode=10027`
            # (AutoTrading tắt ở terminal), vậy mà sổ vẫn ghi các chân BUY
            # 0,16 lot với `ticket=0` trong khi broker có ĐÚNG 0 vị thế. Sổ ghi
            # theo Ý ĐỊNH, không theo kết quả.
            #
            # Hậu quả không dừng ở một dòng sai: `open()` từ chối mở lại chân đã
            # có trong sổ, nên chân đó KHÔNG THỂ thử lại chừng nào bóng ma còn
            # nằm đó; `sides()` báo chân đang giữ lệnh nên hai chân ngược chiều
            # tưởng đã triệt tiêu nhau; và đồng hồ time-stop bắt đầu chạy cho một
            # vị thế không tồn tại.
            #
            # `reconcile()` chu kỳ sau có dọn được, nhưng "sai rồi tự sửa" không
            # phải thiết kế đúng cho sổ vị thế — giữa hai thời điểm đó hệ ra
            # quyết định trên một thế giới không có thật.
            changes[leg] = f"BỎ QUA — broker TỪ CHỐI lệnh {symbol}, sổ giữ nguyên"
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
        sym = getattr(PF, "LEG_INSTRUMENT", {}).get(leg)
        try:
            loaded = mod._load(sym) if sym else mod._load(start)
            # `_load` trả DataFrame (nến) hoặc một object có `.df` — chấp cả hai để
            # không buộc mọi chiến lược phải cùng một kiểu trả về.
            out[leg] = getattr(loaded, "df", loaded).index
        except Exception:                                  # pragma: no cover
            continue
    return out
