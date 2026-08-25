"""sim_broker.py — BROKER ẢO hình dạng MT5, để chạy ĐÚNG code live trên dữ liệu lịch sử.

VÌ SAO PHẢI CÓ
==============
Backtest của chiến lược tính lãi lỗ thẳng từ
mảng giá. Nó KHÔNG đi qua bất kỳ lớp nào của đường vào lệnh thật:

    entry_gate · order_plan · position_book · disaster_stop · order_router
    làm tròn lot theo volume_step · triệt tiêu chân · cầu chì nổ

Nghĩa là mọi con số công bố đến từ một hệ, còn tiền thật sẽ đi qua một hệ khác, và
**không có gì kiểm hai hệ đó cho ra cùng kết quả**. Hệ XAUUSD tiền nhiệm giải đúng
bài này bằng `core/infra/sim_broker.py`: một broker ảo cho phép chạy THẲNG hàm
`evaluate_and_trade()` của live trên dữ liệu lịch sử. Module này là bản tương đương
cho mô hình danh mục.

PHẠM VI — MÔ PHỎNG CÁI GÌ, KHÔNG MÔ PHỎNG CÁI GÌ
=================================================
CÓ:
    · mở/đóng vị thế qua `order_send`, đúng dạng request mà `order_router` dựng
    · giá khớp = giá nến CỘNG nửa spread đúng chiều (mua ở ask, bán ở bid)
    · dừng lỗ trên SERVER: mỗi lần bước nến, kiểm bóng nến có chạm `sl` không
    · làm tròn lot theo `volume_step`
    · equity/balance cập nhật theo giá hiện tại

KHÔNG:
    · trượt giá ngoài spread, khớp một phần, lệnh bị từ chối ngẫu nhiên, requote
    · độ trễ mạng
Ba thứ đó chỉ đo được trên tài khoản thật. Bỏ chúng nghĩa là parity đo ở đây là
**cận trên** — hai hệ khớp nhau ở đây là điều kiện CẦN, không phải điều kiện đủ.

ĐỒNG HỒ ẢO
==========
Broker không tự biết thời gian. Bên gọi `step(i)` để đẩy nó tới nến thứ `i`, và mọi
truy vấn giá trả về giá TẠI nến đó. Nhờ vậy không có đường nào nhìn thấy dữ liệu
tương lai.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# Hằng số MT5, khai lại để module chạy được trên máy KHÔNG cài MetaTrader5 (CI).
# Giá trị lấy đúng theo tài liệu MT5 — sai một con số ở đây là `order_router` đọc
# nhầm mã trả về và tưởng lệnh hỏng thành công.
TRADE_ACTION_DEAL = 1
ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
ORDER_TIME_GTC = 0
TRADE_RETCODE_DONE = 10009
TRADE_RETCODE_INVALID_VOLUME = 10014
TRADE_RETCODE_NO_MONEY = 10019


@dataclass
class SimPosition:
    """Một vị thế trên broker ảo. Trường trùng tên với `mt5.positions_get()`."""
    ticket: int
    symbol: str
    volume: float
    type: int                    # 0 = mua, 1 = bán
    price_open: float
    sl: float = 0.0
    tp: float = 0.0
    magic: int = 0
    comment: str = ""
    profit: float = 0.0
    open_bar: int = 0

    @property
    def side_sign(self) -> int:
        return 1 if self.type == ORDER_TYPE_BUY else -1


@dataclass
class SimFill:
    """Bản ghi một lần khớp — dùng để so với danh sách lệnh của backtest."""
    bar: int
    time: pd.Timestamp
    symbol: str
    action: str                  # OPEN | CLOSE | SL_HIT
    side: str
    volume: float
    price: float
    reason: str = ""


@dataclass
class SimAccount:
    balance: float = 100_000.0
    equity: float = 100_000.0
    margin_free: float = 100_000.0
    login: int = 0
    server: str = "SIM"


class SimBroker:
    """Broker ảo. Truyền thẳng vào `order_router.OrderRouter(mt5=...)`.

    Một broker cho MỘT công cụ là đủ cho kiểm định parity từng chân; truyền `bars`
    là dict {symbol: DataFrame} để mô phỏng nhiều công cụ cùng lúc.
    """

    # Hằng số MT5 lộ ra như thuộc tính lớp — `order_router` đọc `mt5.ORDER_TYPE_BUY`.
    TRADE_ACTION_DEAL = TRADE_ACTION_DEAL
    ORDER_TYPE_BUY = ORDER_TYPE_BUY
    ORDER_TYPE_SELL = ORDER_TYPE_SELL
    ORDER_TIME_GTC = ORDER_TIME_GTC
    TRADE_RETCODE_DONE = TRADE_RETCODE_DONE

    def __init__(self, bars: Dict[str, pd.DataFrame], *,
                 spread_bps: float = 0.0, balance: float = 100_000.0,
                 volume_step: float = 0.01, volume_min: float = 0.01,
                 price_at: str = "open"):
        self.bars = {k: v for k, v in bars.items()}
        self.spread_bps = float(spread_bps)
        self.volume_step = float(volume_step)
        self.volume_min = float(volume_min)
        # Giá khớp lấy từ cột nào. MẶC ĐỊNH "open", không phải "close":
        # thẻ luật của mọi chân ghi "khớp tại giá MỞ CỬA nến kế tiếp sau nến tín
        # hiệu", và backtest cũng vào ở `o[i]`. Khớp ở giá đóng cửa của chính nến
        # tín hiệu là nhìn thấy thông tin mình chưa được phép có.
        self.price_at = str(price_at)
        self.account = SimAccount(balance=balance, equity=balance,
                                  margin_free=balance)
        self.positions: List[SimPosition] = []
        self.fills: List[SimFill] = []
        self.rejected: List[Dict] = []
        self._i = 0
        self._ticket = 1

    # ─────────────────────────────────────────────── đồng hồ ảo
    def step(self, i: int) -> List[SimFill]:
        """Đẩy broker tới nến thứ `i`. Trả các lần khớp do DỪNG LỖ gây ra.

        Kiểm dừng lỗ TRƯỚC khi trả điều khiển cho chiến lược: trên broker thật, SL
        nằm trên server và bị quét bởi bóng nến, không đợi ai gọi hàm. Kiểm sau khi
        chiến lược quyết định là mô phỏng một thứ không tồn tại.
        """
        self._i = int(i)
        hit = self._sweep_stops()
        self._mark_to_market()
        return hit

    def _bar(self, symbol: str, i: Optional[int] = None) -> pd.Series:
        return self.bars[symbol].iloc[self._i if i is None else i]

    def now(self, symbol: str) -> pd.Timestamp:
        return self.bars[symbol].index[self._i]

    # ─────────────────────────────────────────────── API hình dạng MT5
    def symbol_select(self, _symbol: str, _enable: bool = True) -> bool:
        return True

    def symbol_info(self, symbol: str):
        if symbol not in self.bars:
            return None
        mid = float(self._bar(symbol)[self.price_at])
        return type("Info", (), {
            "bid": mid * (1 - self.spread_bps / 2e4),
            "ask": mid * (1 + self.spread_bps / 2e4),
            "volume_step": self.volume_step, "volume_min": self.volume_min,
            "volume_max": 100.0, "digits": 5, "point": 1e-5,
            "trade_stops_level": 0, "trade_freeze_level": 0, "filling_mode": 1,
        })()

    def symbol_info_tick(self, symbol: str):
        info = self.symbol_info(symbol)
        if info is None:
            return None
        return type("Tick", (), {"bid": info.bid, "ask": info.ask,
                                 "last": (info.bid + info.ask) / 2})()

    def positions_get(self, symbol: Optional[str] = None, **_):
        if symbol is None:
            return list(self.positions)
        return [p for p in self.positions if p.symbol == symbol]

    def account_info(self):
        return self.account

    def order_send(self, req: Dict):
        """Khớp lệnh. Trả đối tượng có `retcode`, `order`, `comment` như MT5."""
        symbol = str(req.get("symbol", ""))
        if symbol not in self.bars:
            return self._reject(req, TRADE_RETCODE_INVALID_VOLUME, "symbol lạ")

        vol = self._round_volume(float(req.get("volume", 0.0)))
        if vol < self.volume_min:
            return self._reject(req, TRADE_RETCODE_INVALID_VOLUME,
                                f"lot {vol} dưới tối thiểu {self.volume_min}")

        is_buy = int(req.get("type", ORDER_TYPE_BUY)) == ORDER_TYPE_BUY
        info = self.symbol_info(symbol)
        price = float(info.ask if is_buy else info.bid)

        # Lệnh NGƯỢC chiều vị thế đang mở = ĐÓNG bớt, không phải mở thêm. Broker
        # netting làm vậy; mô phỏng sai chỗ này thì sổ vị thế ảo phình gấp đôi và
        # mọi so sánh parity phía sau vô nghĩa.
        opp = [p for p in self.positions
               if p.symbol == symbol and (p.type == ORDER_TYPE_BUY) != is_buy]
        remaining = vol
        for p in list(opp):
            if remaining <= 1e-9:
                break
            take = min(p.volume, remaining)
            # LÝ DO ĐÓNG lấy từ `comment` của lệnh — bên gọi biết vì sao nó
            # đóng, broker thì không. Bản trước gán cứng một chuỗi cho MỌI lệnh,
            # nên bảng lý-do-đóng của vòng 2026 chỉ có ĐÚNG MỘT dòng và 113 lệnh
            # chạm time-stop (16,8%) biến mất khỏi báo cáo. Bảng ấy là thứ đầu
            # tiên phải nhìn khi live lệch khỏi backtest — xem `exit_manager`.
            self._close(p, take, price,
                        str(req.get("comment", "")).strip()
                        or "ĐÓNG theo lệnh ngược chiều")
            remaining -= take
        if remaining > 1e-9:
            self._open(symbol, remaining, is_buy, price,
                       float(req.get("sl", 0.0) or 0.0),
                       int(req.get("magic", 0) or 0),
                       str(req.get("comment", "")))

        self._mark_to_market()
        return type("Res", (), {"retcode": TRADE_RETCODE_DONE,
                                "order": self._ticket - 1,
                                "comment": "done", "volume": vol,
                                "price": price})()

    # ─────────────────────────────────────────────── nội bộ
    def _reject(self, req: Dict, retcode: int, why: str):
        self.rejected.append({"req": dict(req), "retcode": retcode, "why": why})
        return type("Res", (), {"retcode": retcode, "order": 0, "comment": why})()

    def _round_volume(self, v: float) -> float:
        """Làm tròn XUỐNG theo `volume_step` — vượt trần rủi ro do làm tròn lên là
        lỗi im lặng, và backtest thì không làm tròn gì cả."""
        if self.volume_step <= 0:
            return v
        return float(np.floor(v / self.volume_step + 1e-9) * self.volume_step)

    def _open(self, symbol: str, vol: float, is_buy: bool, price: float,
              sl: float, magic: int, comment: str) -> None:
        p = SimPosition(ticket=self._ticket, symbol=symbol, volume=vol,
                        type=ORDER_TYPE_BUY if is_buy else ORDER_TYPE_SELL,
                        price_open=price, sl=sl, magic=magic, comment=comment,
                        open_bar=self._i)
        self._ticket += 1
        self.positions.append(p)
        self.fills.append(SimFill(self._i, self.now(symbol), symbol, "OPEN",
                                  "BUY" if is_buy else "SELL", vol, price))

    def _close(self, p: SimPosition, vol: float, price: float,
               reason: str, action: str = "CLOSE") -> None:
        pnl = p.side_sign * (price - p.price_open) / p.price_open
        self.account.balance += pnl * vol * 100_000.0 * p.price_open / p.price_open
        p.volume -= vol
        self.fills.append(SimFill(self._i, self.now(p.symbol), p.symbol, action,
                                  "SELL" if p.type == ORDER_TYPE_BUY else "BUY",
                                  vol, price, reason))
        if p.volume <= 1e-9:
            self.positions.remove(p)

    def _sweep_stops(self) -> List[SimFill]:
        """Quét bóng nến xem có vị thế nào chạm SL không. Đây là SL TRÊN SERVER."""
        out: List[SimFill] = []
        for p in list(self.positions):
            if p.sl <= 0:
                continue
            b = self._bar(p.symbol)
            lo, hi = float(b["low"]), float(b["high"])
            hit = (p.type == ORDER_TYPE_BUY and lo <= p.sl) or \
                  (p.type == ORDER_TYPE_SELL and hi >= p.sl)
            if hit:
                n = len(self.fills)
                self._close(p, p.volume, p.sl, "cầu chì thảm hoạ nổ", "SL_HIT")
                out.extend(self.fills[n:])
        return out

    def _mark_to_market(self) -> None:
        eq = self.account.balance
        for p in self.positions:
            px = float(self._bar(p.symbol)["close"])
            eq += p.side_sign * (px - p.price_open) / p.price_open * \
                p.volume * 100_000.0 * p.price_open / p.price_open
            p.profit = p.side_sign * (px - p.price_open) * p.volume * 100_000.0
        self.account.equity = eq
        self.account.margin_free = eq

    # ─────────────────────────────────────────────── báo cáo
    def fills_frame(self) -> pd.DataFrame:
        return pd.DataFrame([f.__dict__ for f in self.fills])

    def round_trips(self) -> pd.DataFrame:
        """Ghép OPEN với CLOSE thành LỆNH KHỨ HỒI, để so với `res.trades`."""
        rows: List[Dict] = []
        open_stack: Dict[str, List[SimFill]] = {}
        for f in self.fills:
            if f.action == "OPEN":
                open_stack.setdefault(f.symbol, []).append(f)
                continue
            st = open_stack.get(f.symbol) or []
            if not st:
                continue
            o = st.pop(0)
            side = 1 if o.side == "BUY" else -1
            gross = side * (f.price - o.price) / o.price * 1e4
            rows.append({"entry_time": o.time, "exit_time": f.time,
                         "symbol": f.symbol, "side": side,
                         "bars": f.bar - o.bar, "reason": f.reason or f.action,
                         "entry_px": o.price, "exit_px": f.price,
                         "gross_bps": gross})
        return pd.DataFrame(rows)
