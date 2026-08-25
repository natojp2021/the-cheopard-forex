"""risk_sizing.py — cỡ lệnh từ KHOẢNG CÁCH SL và % equity. ĐƯỜNG SIZING DUY NHẤT.

VÌ SAO MODULE NÀY THAY HẲN `portfolio_sizing.py` (đã XOÁ 25/08/2026)
====================================================================
Hệ này từng có hai công thức sizing cho hai loại chiến lược:

    ĐÃ XOÁ — danh mục nhiều chân KHÔNG có SL theo giá
        lot_i = equity x leverage x w_i / notional_i
        rủi ro là hàm của BIẾN ĐỘNG và ĐÒN BẨY; mất bao nhiêu thì KHÔNG biết trước,
        chỉ ước lượng được từ biến động lịch sử

    CÒN LẠI — chiến lược CÓ SL cứng (`AsiaSweepH1`)
        lot   = equity x risk_pct / (SL_pip x giá trị 1 pip / lot)
        rủi ro là số ĐÃ BIẾT TRƯỚC; đòn bẩy là HỆ QUẢ, không phải đầu vào

Danh mục không-SL đã bị xoá cùng nhiều chân, nên công thức thứ nhất KHÔNG CÒN AI GỌI.
Giữ nó lại là để dành một cách gọi sai công thức mà không ai thấy — nên `weights_to_lots`,
`size_portfolio`, `leverage_for_vol_target`, `max_leverage_for_drawdown` và
`open_risk_estimate` đã bị xoá theo, đúng quy tắc "không code chết" của `CLAUDE.md`.
`lot_notional_usd` được CỨU sang đây vì nó là phép quy đổi ĐƠN VỊ, không phải sizing.

Công thức còn lại học từ một hệ một-tài-sản
(`lot = risk_usd / (SL_distance x point_value)`), nhưng KHÔNG port thẳng: vàng có
một cặp duy nhất và `point_value` là hằng số, còn FX có ba họ cặp với ba phép quy
đổi khác nhau. Mọi thứ phụ thuộc tài sản ở đây đi qua `shared/asset_profile.py` —
xem mục "CHUẨN HOÁ ĐƠN VỊ" trong docstring của module đó.

BA CÁI BẪY ĐƠN VỊ, VÀ CẢ BA ĐỀU TỪNG LÀM HỎNG HỆ NÀY
====================================================
1. `usd_per_quote` mặc định 1,0 làm notional của cặp quote JPY sai **150 lần**. Ở
   đây nó là THAM SỐ BẮT BUỘC suy từ bảng giá thật, và thiếu giá thì `raise`.
2. Giá trị 1 pip của 1 lot KHÁC NHAU theo họ cặp. EURUSD: 1 pip = $10 cố định.
   USDJPY: 1 pip = 1.000 JPY = 1.000/giá USD, tức ~$6,7 ở giá 150 và ~$9,1 ở giá
   110. Dùng $10 cho mọi cặp là sai cỡ lệnh tới 33%.
3. `min_stop_pips` của broker. Backtest không mô phỏng `stops_level`, nên một SL
   2 pip chạy đẹp trong lab sẽ bị broker TỪ CHỐI ở live. Hàm này chặn tại đây thay
   vì để lệnh bị từ chối lúc gửi.

FAIL-CLOSED
===========
Không tính được rủi ro thì lot = 0, KHÔNG phải "một mức sàn dương". Đây là quy tắc
của tầng rủi ro trong `CLAUDE.md`, và `target_mode.risk_fraction` là tiền lệ. Mọi
nhánh trả 0 đều kèm LÝ DO đọc được — một số 0 không có lý do là một số 0 không truy
vết được.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from src.python.shared import asset_profile as AP

# Lot nhỏ nhất và bước lot mặc định. `symbol_spec` đọc số THẬT từ broker ở live;
# hai hằng số này chỉ dùng khi chạy không có MT5 (backtest, xem trước kế hoạch).
DEFAULT_MIN_LOTS = 0.01
DEFAULT_LOT_STEP = 0.01

# Trần cứng cho MỘT vị thế, tính bằng % equity. Không phải tham số chiến lược — đây
# là chốt an toàn: một lỗi đơn vị (bẫy số 1 và 2 ở trên) biểu hiện thành lot lớn bất
# thường, và trần này biến một sự cố mất tài khoản thành một cảnh báo.
MAX_RISK_PCT_PER_POSITION = 1.0


@dataclass(frozen=True)
class RiskLot:
    """Kết quả sizing của MỘT vị thế. Luôn đọc được vì sao ra con số đó."""
    symbol: str
    lots: float
    risk_usd: float
    sl_pips: float
    value_per_pip_per_lot: float
    notional_usd: float
    leverage_implied: float
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.lots > 0.0

    def explain(self) -> str:
        if not self.ok:
            return f"{self.symbol:8} lot 0.00 — {self.reason}"
        return (f"{self.symbol:8} {self.lots:6.2f} lot · rủi ro ${self.risk_usd:,.0f} "
                f"trên SL {self.sl_pips:.1f} pip · ${self.value_per_pip_per_lot:.2f}/pip"
                f"/lot · notional ${self.notional_usd:,.0f} "
                f"({self.leverage_implied:.2f}x)"
                + (f" · {self.reason}" if self.reason else ""))


def lot_notional_usd(symbol: str, price: float,
                     usd_per_quote: Optional[float] = None) -> float:
    """Giá trị USD của 1,0 lot tại `price`.

        XXXUSD   1 lot = contract_size đơn vị XXX  ->  contract_size x price
        USDXXX   1 lot = contract_size đơn vị USD  ->  contract_size
        cặp chéo 1 lot = contract_size đơn vị BASE ->  contract_size x price
                                                       x tỷ giá QUOTE->USD

    ⚠️ CẶP CHÉO KHÔNG ĐƯỢC MẶC ĐỊNH `usd_per_quote = 1.0`. Mặc định đó làm notional
    của một cặp chéo sai đúng bằng tỷ giá đồng định giá — với cặp quote JPY là sai
    **150 lần** — và sai IM LẶNG, vì kết quả vẫn là một con số dương trông hợp lý.

    Nay `usd_per_quote=None` với cặp chéo là LỖI, không phải mặc định. Lấy giá trị
    đúng bằng `asset_profile.usd_per_quote(symbol, prices)`.

    Rổ hiện tại (`AsiaSweepH1`) chỉ có ba major nên nhánh cặp chéo chưa chạy — nhưng
    nó ở lại vì `ftmo_guard` gọi hàm này cho MỌI vị thế broker trả về, kể cả vị thế
    người vận hành mở tay trên một cặp ngoài rổ.
    """
    prof = AP.get(symbol)
    if prof.quote_is_usd:
        return prof.contract_size * price
    if prof.base == "USD":
        return prof.contract_size
    if usd_per_quote is None:
        raise ValueError(
            f"{symbol} là cặp chéo: phải truyền `usd_per_quote` (tỷ giá "
            f"{prof.quote}->USD). Bỏ trống làm notional sai im lặng theo đúng tỷ giá "
            f"đó. Dùng `asset_profile.usd_per_quote({symbol!r}, prices)`.")
    return prof.contract_size * price * float(usd_per_quote)


def _round_step(lots: float, step: float) -> float:
    if step <= 0:
        return lots
    return float(int(lots / step + 1e-9) * step)


def lots_for_risk(symbol: str, *, entry_price: float, stop_price: float,
                  equity_usd: float, risk_pct: float,
                  prices: Optional[Dict[str, float]] = None,
                  usd_per_quote: Optional[float] = None,
                  min_lots: float = DEFAULT_MIN_LOTS,
                  lot_step: float = DEFAULT_LOT_STEP,
                  max_lots: Optional[float] = None) -> RiskLot:
    """Số lot để một lần chạm SL mất đúng `risk_pct`% equity. FAIL-CLOSED.

    `usd_per_quote` là tỷ giá QUOTE->USD. Truyền trực tiếp (live: lấy từ broker) hoặc
    để hàm suy từ `prices` (bảng giá major). Thiếu cả hai với cặp quote != USD thì
    trả lot 0 kèm lý do — KHÔNG mặc định 1,0. Mặc định 1,0 là chính cái đã làm
    notional EURJPY sai 150 lần.

    Trả `RiskLot` với `lots = 0` ở mọi nhánh không tính được. Bên gọi chỉ cần kiểm
    `.ok`, và `.reason` là thứ đi vào `decision_log`.
    """
    bad = lambda why: RiskLot(symbol=symbol, lots=0.0, risk_usd=0.0,
                              sl_pips=float("nan"), value_per_pip_per_lot=float("nan"),
                              notional_usd=0.0, leverage_implied=0.0, reason=why)

    if not (equity_usd > 0):
        return bad(f"equity không dương ({equity_usd})")
    if not (risk_pct > 0):
        return bad(f"risk_pct không dương ({risk_pct})")
    if risk_pct > MAX_RISK_PCT_PER_POSITION:
        return bad(f"risk_pct {risk_pct:.2f}% vượt trần cứng "
                   f"{MAX_RISK_PCT_PER_POSITION:.2f}%/vị thế — nghi lỗi đơn vị")
    for nm, v in (("entry_price", entry_price), ("stop_price", stop_price)):
        if v is None or not (float(v) > 0):
            return bad(f"{nm} không dương ({v})")

    prof = AP.get(symbol)
    dist = abs(float(entry_price) - float(stop_price))
    if dist <= 0:
        return bad("SL trùng giá vào — khoảng cách 0")
    sl_pips = dist / prof.pip
    if sl_pips < prof.min_stop_pips:
        return bad(f"SL {sl_pips:.1f} pip nhỏ hơn khoảng dừng tối thiểu broker "
                   f"{prof.min_stop_pips:.1f} pip — live sẽ TỪ CHỐI lệnh")

    if usd_per_quote is None:
        if prof.quote == "USD":
            usd_per_quote = 1.0
        elif prices:
            try:
                usd_per_quote = AP.usd_per_quote(symbol, prices)
            except KeyError as exc:
                return bad(f"không suy được tỷ giá {prof.quote}->USD ({exc})")
        else:
            return bad(f"cặp quote {prof.quote} cần `usd_per_quote` hoặc bảng "
                       f"`prices`; không mặc định 1,0")
    if not (float(usd_per_quote) > 0):
        return bad(f"usd_per_quote không dương ({usd_per_quote})")

    vpp = prof.value_per_pip_per_lot(float(entry_price), float(usd_per_quote))
    if not (vpp > 0):
        return bad(f"giá trị 1 pip/lot không dương ({vpp})")

    risk_usd = float(equity_usd) * float(risk_pct) / 100.0
    raw = risk_usd / (sl_pips * vpp)
    lots = _round_step(raw, lot_step)
    if max_lots is not None:
        lots = min(lots, float(max_lots))
    if lots < min_lots:
        return bad(f"lot cần {raw:.4f} nhỏ hơn lot tối thiểu {min_lots:.2f} — "
                   f"rủi ro ${risk_usd:,.0f} quá nhỏ cho SL {sl_pips:.1f} pip")

    # Notional quy USD. 1 lot = `contract_size` đơn vị BASE, nên:
    #   base = USD (USDJPY…)  ->  notional = contract_size x lots, KHÔNG nhân giá
    #   base != USD (EURUSD…) ->  giá trị USD của base = giá x tỷ giá quote->USD
    # Nhân giá cho cả hai họ là chỗ sai 150 lần đã ghi ở đầu module.
    if prof.base == "USD":
        notional = prof.contract_size * lots
    else:
        notional = prof.contract_size * lots * float(entry_price) * float(usd_per_quote)

    return RiskLot(symbol=symbol, lots=lots,
                   risk_usd=lots * sl_pips * vpp, sl_pips=sl_pips,
                   value_per_pip_per_lot=vpp, notional_usd=notional,
                   leverage_implied=notional / float(equity_usd))


def size_book(stop_targets: Dict[str, Dict[str, float]], *, equity_usd: float,
              risk_pct: float, prices: Optional[Dict[str, float]] = None,
              min_lots_by_symbol: Optional[Dict[str, float]] = None,
              lot_step_by_symbol: Optional[Dict[str, float]] = None
              ) -> Dict[str, RiskLot]:
    """Sizing cho CẢ RỔ. `stop_targets` là đầu ra `portfolio.stop_targets()`.

    Một công cụ không tính được KHÔNG làm rơi cả rổ — nó nhận `RiskLot` với lot 0
    kèm lý do. Đây là fail-closed ở mức CÔNG CỤ: mất một cơ hội, không mất cả phiên.
    """
    mins = min_lots_by_symbol or {}
    steps = lot_step_by_symbol or {}
    out: Dict[str, RiskLot] = {}
    for sym, t in stop_targets.items():
        out[sym] = lots_for_risk(
            sym, entry_price=float(t.get("entry", float("nan"))),
            stop_price=float(t.get("stop", float("nan"))),
            equity_usd=equity_usd, risk_pct=risk_pct, prices=prices,
            min_lots=float(mins.get(sym, DEFAULT_MIN_LOTS)),
            lot_step=float(steps.get(sym, DEFAULT_LOT_STEP)))
    return out


def total_risk_pct(book: Dict[str, RiskLot], equity_usd: float) -> float:
    """Tổng rủi ro MỞ nếu mọi SL cùng bị chạm, tính bằng % equity.

    Đây là con số phải so với mốc ngày 5% của FTMO — và nó là số ĐÃ BIẾT TRƯỚC, khác
    hẳn danh mục cũ nơi rủi ro ngày chỉ ước lượng được từ biến động lịch sử.
    """
    if not (equity_usd > 0):
        return 0.0
    return 100.0 * sum(r.risk_usd for r in book.values()) / float(equity_usd)
