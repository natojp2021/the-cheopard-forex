"""portfolio_sizing.py — quy tỷ trọng danh mục thành LOT thật, dưới ràng buộc FTMO.

VÌ SAO MODULE NÀY KHÁC HẲN TẦNG SIZING CŨ
=========================================
Hệ XAUUSD cũ tính lot theo công thức per-trade:

    lot = (rủi ro USD) / (khoảng cách SL × giá trị điểm)

Công thức đó giả định mỗi lệnh có một SL riêng và rủi ro được đo bằng khoảng cách
tới SL đó. **Danh mục tiền tệ cắt ngang không có SL từng lệnh** — nó có tỷ trọng
mục tiêu trên 7 cặp, giữ 21 ngày, và rủi ro được đo bằng BIẾN ĐỘNG của cả danh mục.
Áp công thức cũ vào đây sẽ cho ra một con số vô nghĩa.

Mô hình đúng là **volatility targeting**:

    lot_i = (equity × leverage × w_i) / (contract_size_i × price_i × usd_per_quote_i)

trong đó `leverage` được chọn để biến động danh mục khớp mục tiêu, và mục tiêu ấy
lại bị chặn trên bởi giới hạn drawdown của FTMO chứ không phải bởi mong muốn lợi nhuận.

BA ĐIỂM QUY ĐỔI DỄ SAI VỚI FOREX
================================
1. **Giá trị 1 lot phụ thuộc họ cặp.** XXXUSD: 1 lot = 100.000 XXX, giá trị USD =
   100.000 × price. USDXXX: 1 lot = 100.000 USD, giá trị USD = 100.000 (không nhân
   giá). Dùng chung một công thức là sai notional tới vài lần.
2. **Lot phải làm tròn theo `volume_step` của broker** — và làm tròn XUỐNG, vì vượt
   trần rủi ro do làm tròn lên là lỗi im lặng.
3. **Tổng phơi nhiễm gộp ≠ tổng |tỷ trọng|.** Hai chân của danh mục triệt tiêu nhau
   trên cùng một cặp trước khi ra lệnh (xem `currency_carry.combined`), nên notional
   thật nhỏ hơn tổng hai chân cộng lại.

RÀNG BUỘC FTMO ÁP Ở ĐÂU
=======================
Hằng số lấy từ `core/infra/ftmo.py` (neo vào `docs/ftmo/ftmo.md`), KHÔNG khai lại:
    MAX_LOSS_HARD    10%   equity không bao giờ dưới $90.000
    DAILY_LOSS_HARD   5%   mốc tính lại mỗi 00:00 CE(S)T
    MAX_OPEN_RISK     2%   trần rủi ro danh mục mở cùng lúc
Với danh mục vol-target, "rủi ro mở" được diễn giải là **tổn thất kỳ vọng ở phân vị
xấu** chứ không phải tổng khoảng cách SL — xem `open_risk_estimate()`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.python.core.infra import ftmo
from src.python.core.infra import symbol_spec as SS
from src.python.shared import asset_profile as AP

# Số ngày giao dịch/năm dùng để quy đổi biến động.
TRADING_DAYS = 252

# Phân vị dùng khi ước lượng "rủi ro mở" của danh mục vol-target.
# 2,33σ ≈ phân vị 99% một phía của phân phối chuẩn — cùng tinh thần bảo thủ với
# cách FTMO đo (equity tức thời, gồm lãi/lỗ chưa đóng).
OPEN_RISK_SIGMA = 2.33


@dataclass(frozen=True)
class LotOrder:
    """Một lệnh mục tiêu đã quy về lot thật."""
    symbol: str
    weight: float
    direction: str          # "BUY" | "SELL" | "FLAT"
    lots: float
    notional_usd: float


@dataclass
class SizingResult:
    orders: List[LotOrder]
    leverage: float
    target_vol_pct: float
    est_portfolio_vol_pct: float
    gross_notional_usd: float
    open_risk_pct: float
    ftmo_ok: bool
    notes: List[str] = field(default_factory=list)


# ═════════════════════════════════════════════════════════ quy đổi notional
def lot_notional_usd(symbol: str, price: float,
                     usd_per_quote: Optional[float] = None) -> float:
    """Giá trị USD của 1,0 lot tại `price`.

        XXXUSD   1 lot = contract_size đơn vị XXX  →  contract_size × price
        USDXXX   1 lot = contract_size đơn vị USD  →  contract_size
        cặp chéo 1 lot = contract_size đơn vị BASE →  contract_size × price
                                                      × tỷ giá QUOTE→USD

    ⚠️ NHÁNH CẶP CHÉO SỬA 14/08/2026. Bản cũ đặt `usd_per_quote = 1.0` mặc định kèm
    chú thích "chưa dùng — vũ trụ hiện tại toàn cặp USD". Chú thích đó đã sai từ lâu:
    22 trong 27 chân giao dịch cặp chéo. Mặc định 1,0 làm notional của GBPNZD sai
    đúng bằng tỷ giá NZDUSD (~40%) và của EURJPY sai **150 lần** — sai IM LẶNG, vì
    kết quả vẫn là một con số dương trông hợp lý.

    Nay `usd_per_quote=None` với cặp chéo là LỖI, không phải mặc định. Lấy giá trị
    đúng bằng `asset_profile.usd_per_quote(symbol, prices)`.
    """
    prof = AP.get(symbol)
    if prof.quote_is_usd:
        return prof.contract_size * price
    if prof.base == "USD":
        return prof.contract_size
    if usd_per_quote is None:
        raise ValueError(
            f"{symbol} là cặp chéo: phải truyền `usd_per_quote` (tỷ giá "
            f"{prof.quote}→USD). Bỏ trống làm notional sai im lặng theo đúng tỷ giá "
            f"đó. Dùng `asset_profile.usd_per_quote({symbol!r}, prices)`.")
    return prof.contract_size * price * float(usd_per_quote)


def _require_pair_weights(weights: pd.Series) -> pd.Series:
    """Chặn lỗi truyền nhầm tỷ trọng ĐỒNG TIỀN vào chỗ cần tỷ trọng CẶP.

    `currency_reversal.target_weights()` trả tỷ trọng theo ĐỒNG TIỀN (USD, EUR,
    GBP…), còn sizing cần tỷ trọng theo CẶP (EURUSD, USDJPY…). Hai thứ có cùng kiểu
    `pd.Series` nên trình biên dịch không bắt được, và triệu chứng khi nhầm là
    **notional = 0 một cách im lặng** — mọi lệnh biến mất mà không có lỗi nào.
    Đó là loại lỗi tệ nhất ở tầng đặt lệnh, nên nó phải nổ ngay tại đây.
    """
    unknown = [k for k in weights.index if k not in AP.PROFILES]
    if unknown:
        raise ValueError(
            f"weights phải theo CẶP giao dịch, nhận được {list(weights.index)}. "
            f"Nếu đang có tỷ trọng đồng tiền, chuyển qua "
            f"`currency_reversal.pair_weights(W)` trước. Khoá lạ: {unknown}")
    return weights


def weights_to_lots(weights: pd.Series, prices: Dict[str, float], *,
                    equity_usd: float, leverage: float,
                    mt5_module=None) -> List[LotOrder]:
    """Quy tỷ trọng CẶP -> lot, đã làm tròn theo `volume_step` của broker."""
    _require_pair_weights(weights)
    orders: List[LotOrder] = []
    for symbol, w in weights.items():
        w = float(w)
        px = float(prices.get(symbol, 0.0))
        if px <= 0:
            continue
        target_usd = equity_usd * leverage * abs(w)
        # Cặp chéo cần tỷ giá QUOTE→USD suy từ 7 major trong chính `prices`.
        # Thiếu major thì KeyError nổ ở đây, không âm thầm dùng 1,0 — xem
        # `lot_notional_usd()` cho hậu quả đo được của mặc định đó.
        per_lot = lot_notional_usd(symbol, px, AP.usd_per_quote(symbol, prices))
        raw_lots = target_usd / per_lot if per_lot > 0 else 0.0
        spec = SS.resolve(symbol, mt5_module=mt5_module)
        lots = spec.normalize_volume(raw_lots)
        direction = "FLAT" if lots <= 0 or abs(w) < 1e-9 else ("BUY" if w > 0 else "SELL")
        orders.append(LotOrder(symbol=symbol, weight=round(w, 5),
                               direction=direction, lots=lots,
                               notional_usd=round(lots * per_lot, 2)))
    return orders


# ═════════════════════════════════════════════════════════ đòn bẩy & ràng buộc
def leverage_for_vol_target(strategy_daily_vol_bps: float,
                            target_vol_pct_annual: float) -> float:
    """Hệ số đòn bẩy để đưa biến động chiến lược về mục tiêu năm.

    `strategy_daily_vol_bps` = std lợi nhuận NGÀY của danh mục ở đòn bẩy 1,0,
    đơn vị bps (đúng đơn vị mà `currency_carry.combined()` trả về).
    """
    ann_vol_pct = strategy_daily_vol_bps * np.sqrt(TRADING_DAYS) / 100.0
    if ann_vol_pct <= 0:
        return 0.0
    return float(target_vol_pct_annual / ann_vol_pct)


def max_leverage_for_drawdown(strategy_max_dd_pct: float,
                              dd_budget_pct: float) -> float:
    """Đòn bẩy tối đa để drawdown lịch sử không vượt ngân sách cho phép.

    ĐÂY LÀ CẬN TRÊN THẬN TRỌNG, KHÔNG PHẢI ĐẲNG THỨC (sửa 14/08/2026)
    -----------------------------------------------------------------
    Bản trước ghi "drawdown scale TUYẾN TÍNH theo đòn bẩy … nên phép chia này là
    đúng chứ không phải xấp xỉ". Câu đó SAI với cách hệ này tính equity, và sai
    theo hướng an toàn — đo được:

        đòn bẩy   DD tuyến tính dự đoán   DD thật đo được
          1,0x            3,15%                3,15%
          3,0x            9,45%                7,74%
          3,7x           11,66%                8,98%
          4,85x          15,28%               10,74%

    Lý do: lãi/lỗ ở đây CỘNG DỒN trên số dư ban đầu tĩnh (khớp cách FTMO tính hạn
    mức), không nhân lãi kép. Tổn thất tính bằng ĐÔ-LA thì đúng là tuyến tính theo
    đòn bẩy, nhưng drawdown tính bằng PHẦN TRĂM lấy đỉnh equity làm mẫu số — mà
    đỉnh cũng lớn lên theo đòn bẩy. Tử số tăng tuyến tính, mẫu số cũng tăng, nên
    thương số tăng CHẬM HƠN tuyến tính.

    Giữ nguyên phép chia vì nó lệch về phía an toàn (đòn bẩy cấp ra nhỏ hơn mức
    thật sự cần), đúng thứ tự ưu tiên Account Survival > Profit Maximization. Ai
    cần con số chính xác thì quét trực tiếp trên chuỗi lợi nhuận như
    `ftmo_leverage_policy` đã làm để ra trần 3,7x — đừng nới hằng số ở đây.
    """
    if strategy_max_dd_pct <= 0:
        return float("inf")
    return float(dd_budget_pct / strategy_max_dd_pct)


def open_risk_estimate(daily_vol_bps: float, leverage: float) -> float:
    """Ước lượng "rủi ro danh mục mở" theo % equity, để so với `ftmo.MAX_OPEN_RISK`.

    Danh mục vol-target không có SL nên không có khái niệm "tổng khoảng cách tới SL".
    Đại lượng tương đương về mặt ý nghĩa là **tổn thất một ngày ở phân vị xấu**:

        open_risk = OPEN_RISK_SIGMA × σ_ngày × đòn bẩy

    Đây là diễn giải, không phải một con số FTMO công bố — ghi rõ để không ai nhầm
    nó với một luật của quỹ.
    """
    return float(OPEN_RISK_SIGMA * daily_vol_bps / 100.0 * leverage)


def size_portfolio(weights: pd.Series, prices: Dict[str, float], *,
                   daily_vol_bps: float, max_dd_pct: float,
                   equity_usd: float = 100_000.0,
                   target_vol_pct_annual: float = 6.0,
                   dd_budget_pct: float = 6.0,
                   mt5_module=None) -> SizingResult:
    """Sizing đầy đủ: chọn đòn bẩy nhỏ nhất giữa mục tiêu vol và trần drawdown.

    `dd_budget_pct = 6.0` mặc định KHÔNG phải giới hạn 10% của FTMO mà là mốc
    `TOTAL_WARNING` trong `docs/ftmo/`: chạm 10% là mất tài khoản, nên ngân sách
    vận hành phải nằm hẳn dưới đó. Nguyên tắc thứ tự của dự án — Account Survival
    trước Profit Maximization — buộc chọn giá trị NHỎ HƠN trong hai đòn bẩy.
    """
    notes: List[str] = []
    lev_vol = leverage_for_vol_target(daily_vol_bps, target_vol_pct_annual)
    lev_dd = max_leverage_for_drawdown(max_dd_pct, dd_budget_pct)
    leverage = min(lev_vol, lev_dd)
    if lev_dd < lev_vol:
        notes.append(f"đòn bẩy bị TRẦN DRAWDOWN chặn: {lev_dd:.2f} < {lev_vol:.2f} "
                     f"(mục tiêu vol {target_vol_pct_annual:.1f}% không đạt được "
                     f"trong ngân sách DD {dd_budget_pct:.1f}%)")

    orders = weights_to_lots(weights, prices, equity_usd=equity_usd,
                             leverage=leverage, mt5_module=mt5_module)
    gross = sum(o.notional_usd for o in orders)
    open_risk = open_risk_estimate(daily_vol_bps, leverage)

    ftmo_ok = True
    if open_risk > ftmo.MAX_OPEN_RISK * 100.0:
        ftmo_ok = False
        notes.append(f"VI PHẠM MAX_OPEN_RISK: {open_risk:.2f}% > "
                     f"{ftmo.MAX_OPEN_RISK * 100:.2f}%")
    for o in orders:
        if o.direction != "FLAT" and o.lots <= 0:
            notes.append(f"{o.symbol}: tỷ trọng {o.weight:+.4f} làm tròn về 0 lot — "
                         f"equity quá nhỏ so với bước lot của broker")

    return SizingResult(
        orders=orders, leverage=round(leverage, 4),
        target_vol_pct=target_vol_pct_annual,
        est_portfolio_vol_pct=round(daily_vol_bps * np.sqrt(TRADING_DAYS) / 100.0
                                    * leverage, 3),
        gross_notional_usd=round(gross, 2),
        open_risk_pct=round(open_risk, 3),
        ftmo_ok=ftmo_ok, notes=notes)
