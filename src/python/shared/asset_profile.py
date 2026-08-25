"""asset_profile.py — SSOT đặc tả từng tài sản (The Cheopard Forex).

VÌ SAO MODULE NÀY PHẢI TỒN TẠI
==============================
Hệ thống XAUUSD tiền nhiệm nhúng thẳng đặc tính của vàng vào hằng số toàn cục:

    research/backtest.py      SPREAD_CAP = 1.00 USD · ATR_MIN/MAX = 1.50/10.00 USD
                              COMMISSION_PRICE = 0.07 $/oz
    exit_lab/exit_engine.py   SPREAD_HALF_DEFAULT = 0.15 · COMMISSION_USD = 0.07
    live_strategies/…         ngưỡng ATR/SL tính bằng USD

Không con số nào trong đó có nghĩa với EURUSD. Đo được (scratch/fx_data_recon.py,
H1 2020+): ATR_H1 trung vị của EURUSD = 0,0013 giá — nhỏ hơn `ATR_MIN` của vàng
1.000 lần. Nếu port thẳng, MỌI tín hiệu bị lọc sạch và hệ thống trông như "không
có cơ hội" trong khi thực ra bộ lọc đang tính sai đơn vị.

Nguyên tắc: CORE ENGINE không được biết mình đang chạy tài sản nào. Mọi thứ phụ
thuộc tài sản đi qua đúng module này.

CHUẨN HOÁ ĐƠN VỊ — ĐIỂM DỄ SAI NHẤT
====================================
`exit_lab.exit_engine` tính R thuần bằng ĐƠN VỊ GIÁ (r = Δprice / sl_dist), nên
hệ số quy đổi lot/tiền tệ triệt tiêu — TRỪ chi phí. Chi phí phải được đưa về
cùng đơn vị giá, và phép quy đổi đó KHÁC NHAU giữa hai họ cặp:

    XXXUSD (EURUSD, GBPUSD, AUDUSD, NZDUSD)
        1 lot = 100.000 XXX, lãi/lỗ tính bằng USD = Δprice × 100.000
        commission $7/lot khứ hồi  ->  7 / 100.000 = 0,00007 giá = 0,70 pip

    USDXXX (USDJPY, USDCAD, USDCHF)
        1 lot = 100.000 USD, lãi/lỗ tính bằng XXX = Δprice × 100.000
        commission $7 = 7 × price (XXX/USD)  ->  price × 7e-5 đơn vị giá
        USDJPY @150 -> 1,05 pip · USDCAD @1,35 -> 0,95 pip · USDCHF @0,90 -> 0,63 pip

Tức CÙNG một mức commission USD cho ra chi phí theo pip KHÁC NHAU tuỳ cặp và tuỳ
tỷ giá hiện hành. Đây chính là loại giả định mà "port thẳng từ XAUUSD" bỏ sót.

CHI PHÍ MẶC ĐỊNH — VÌ SAO KHÔNG PHẢI 0
=======================================
Dữ liệu Dukascopy là spread ECN THÔ, chưa gồm commission. Broker raw-spread thu
~$3,5/lot/chiều = **$7/lot khứ hồi**. Với EURUSD, commission (0,70 pip) LỚN HƠN
chính spread trung vị (0,31 pip) — bỏ qua nó là nhân đôi-ba edge một cách hệ
thống. Mặc định ở đây vì vậy là $7, không phải 0.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

# Commission khứ hồi mặc định cho tài khoản FX raw-spread (USD / 1.0 lot).
DEFAULT_FX_COMMISSION_USD_PER_LOT_RT = 7.0


@dataclass(frozen=True)
class AssetProfile:
    """Đặc tả bất biến của một tài sản giao dịch.

    Chỉ chứa sự thật về HỢP ĐỒNG và ĐƠN VỊ — không chứa tham số chiến lược, không
    chứa ngưỡng đã hiệu chỉnh. Ngưỡng hiệu chỉnh theo cặp thuộc về lớp calibration
    riêng (`configs/assets/<SYMBOL>.yaml`), vì chúng thay đổi theo kết quả nghiên
    cứu còn những trường dưới đây thì không.
    """
    symbol: str
    kind: str                      # "fx" | "metal"
    base: str                      # đồng tiền cơ sở (EUR trong EURUSD)
    quote: str                     # đồng tiền định giá (USD trong EURUSD)
    pip: float                     # số đơn vị giá cho 1 pip
    contract_size: float           # số đơn vị `base` trong 1.0 lot
    digits: int
    # Khoảng dừng tối thiểu broker chấp nhận (pip). Backtest KHÔNG mô phỏng
    # `stops_level`, nên đây là chốt để research không sinh ra SL mà live từ chối.
    min_stop_pips: float = 3.0
    commission_usd_per_lot_rt: float = DEFAULT_FX_COMMISSION_USD_PER_LOT_RT

    # ---------------------------------------------------------------- đơn vị
    @property
    def quote_is_usd(self) -> bool:
        return self.quote == "USD"

    def pips(self, price_distance: float) -> float:
        """Đổi khoảng cách giá -> pip."""
        return price_distance / self.pip

    def price(self, pips: float) -> float:
        """Đổi pip -> khoảng cách giá."""
        return pips * self.pip

    # ------------------------------------------------------------- chi phí
    def commission_price_units(self, price: float) -> float:
        """Commission khứ hồi quy về ĐƠN VỊ GIÁ — tham số `commission_per_oz`
        của `exit_lab.exit_engine.simulate_trade()`.

        Xem phần "CHUẨN HOÁ ĐƠN VỊ" ở đầu module để biết vì sao hai họ cặp có
        hai công thức khác nhau. `price` bị bỏ qua với cặp quote = USD (hệ số 1),
        nhưng vẫn nhận vào để caller không phải phân nhánh theo loại cặp.
        """
        per_unit_usd = self.commission_usd_per_lot_rt / self.contract_size
        if self.quote_is_usd:
            return per_unit_usd
        # quote != USD: chi phí USD phải quy sang đồng quote. Với USDXXX thì
        # chính `price` là tỷ giá XXX/USD nên nhân thẳng.
        if self.base == "USD":
            return per_unit_usd * price
        # Cặp chéo (EURJPY, GBPJPY…): cần tỷ giá quote/USD từ ngoài. Chưa hỗ trợ
        # — fail rõ ràng thay vì trả một con số sai âm thầm.
        raise NotImplementedError(
            f"{self.symbol}: cặp chéo cần tỷ giá {self.quote}/USD để quy đổi "
            f"commission; truyền qua lớp calibration khi mở rộng sang cross pairs.")

    def commission_pips(self, price: float) -> float:
        return self.commission_price_units(price) / self.pip

    # ------------------------------------------------------- giá trị vị thế
    def value_per_pip_per_lot(self, price: float, usd_per_quote: float = 1.0) -> float:
        """Giá trị 1 pip của 1.0 lot, tính bằng USD.

        `usd_per_quote` = tỷ giá QUOTE->USD. Với quote = USD thì bằng 1. Với
        USDJPY thì bằng 1/price (JPY->USD). Tách tham số thay vì tự suy để lớp
        gọi (live) truyền tỷ giá THẬT từ broker thay vì một xấp xỉ.
        """
        pip_value_quote = self.pip * self.contract_size
        if self.quote_is_usd:
            return pip_value_quote
        if self.base == "USD":
            return pip_value_quote / price
        return pip_value_quote * usd_per_quote


# ═══════════════════════════════════════════════════════════════ REGISTRY
_FX = dict(kind="fx", contract_size=100_000.0)

PROFILES: Dict[str, AssetProfile] = {
    # ---- Tier 1: rào chi phí thấp nhất (đo được — xem reports/fx_recon/)
    "EURUSD": AssetProfile(symbol="EURUSD", base="EUR", quote="USD",
                           pip=0.0001, digits=5, min_stop_pips=2.0, **_FX),
    "GBPUSD": AssetProfile(symbol="GBPUSD", base="GBP", quote="USD",
                           pip=0.0001, digits=5, min_stop_pips=2.0, **_FX),
    "USDJPY": AssetProfile(symbol="USDJPY", base="USD", quote="JPY",
                           pip=0.01, digits=3, min_stop_pips=2.0, **_FX),
    # ---- Tier 2: chỉ mở khi Tier 1 đã chứng minh edge
    "AUDUSD": AssetProfile(symbol="AUDUSD", base="AUD", quote="USD",
                           pip=0.0001, digits=5, min_stop_pips=2.0, **_FX),
    "USDCAD": AssetProfile(symbol="USDCAD", base="USD", quote="CAD",
                           pip=0.0001, digits=5, min_stop_pips=2.0, **_FX),
    "USDCHF": AssetProfile(symbol="USDCHF", base="USD", quote="CHF",
                           pip=0.0001, digits=5, min_stop_pips=2.0, **_FX),
    "NZDUSD": AssetProfile(symbol="NZDUSD", base="NZD", quote="USD",
                           pip=0.0001, digits=5, min_stop_pips=2.0, **_FX),
    # ---- Kim loại: giữ để ĐỐI CHIẾU, không phải mục tiêu giao dịch của hệ này.
    # `pip=0.10` là quy ước dự án; commission $0,07/oz × 100 oz/lot = $7/lot khứ
    # hồi — cùng bậc với FX, tiện so sánh trực tiếp.
    # XAUUSD ĐÃ XOÁ 13/08/2026: hệ này là Forex-only. Giữ nó trong
    # PROFILES nghĩa là `get("XAUUSD")` trả về đơn vị của vàng KHÔNG BÁO LỖI —
    # đúng cơ chế đã làm `ATR_MIN = 1,50 USD` lọc sạch 100% tín hiệu FX mà
    # backtest vẫn "chạy xong". Nay nó raise KeyError, và test chốt điều đó.
}

# Nhóm ưu tiên nghiên cứu — thứ tự này là quyết định dự án, và nó KHỚP với thứ
# hạng rào chi phí đo được (spread/ATR_H1 trung vị, H1 2020+):
#     EURUSD 2,44%  ·  USDJPY 2,73%  ·  GBPUSD 5,00%
#     [XAUUSD 7,26% để tham chiếu]
#     AUDUSD 8,65%  ·  USDCHF 8,69%  ·  USDCAD 8,84%  ·  NZDUSD 10,11%
# Bốn cặp Tier 2 có rào chi phí GẤP 3,5-4 LẦN EURUSD. Đó là lý do định lượng để
# không mở rộng danh mục trước khi Tier 1 có edge — không phải một sở thích.
TIER1: Tuple[str, ...] = ("EURUSD", "GBPUSD", "USDJPY")
TIER2: Tuple[str, ...] = ("AUDUSD", "USDCAD", "USDCHF", "NZDUSD")
FX_ALL: Tuple[str, ...] = TIER1 + TIER2

# ═══════════════════════════════════════════════════════════════ CẶP CHÉO
# THÊM 14/08/2026 SAU KHI PHÁT HIỆN MỘT LỖ HỔNG NGHIÊM TRỌNG Ở TẦNG SIZING.
#
# `PROFILES` trước hôm nay chỉ có 7 cặp USD, và `portfolio_sizing._require_pair_weights()`
# ném `ValueError` cho mọi khoá lạ. Nhưng phần lớn các chân giao dịch CẶP CHÉO — tức
# đường quy đổi tỷ trọng sang lot KHÔNG CHẠY ĐƯỢC cho phần lớn danh mục, và điều đó
# chỉ lộ ra khi có người thật sự nối `target_weights()` vào `weights_to_lots()`.
#
# Cross dựng bằng arbitrage tam giác nên GIÁ chính xác tới từng pip. Thứ phải cẩn
# thận là ĐƠN VỊ:
#   · pip = 0,01 nếu quote là JPY, còn lại 0,0001 — nhầm chỗ này sai 100 lần
#   · notional USD cần tỷ giá QUOTE→USD lấy từ ngoài (`usd_per_quote`), vì không
#     chân nào của cross chứa USD để tự suy ra
#
# ⚠️ `spread_typical_pips` ở đây là ƯỚC LƯỢNG từ bảng broker raw-spread, không phải
# số đo. Chi phí thật của cross PHẢI đo lại trên tài khoản sẽ giao dịch — đó là lý do
# mọi báo cáo trong repo đều có cột stress chi phí ×2.
_CROSS_DEFS = (
    ("EURGBP", "EUR", "GBP"), ("EURAUD", "EUR", "AUD"), ("EURNZD", "EUR", "NZD"),
    ("EURCAD", "EUR", "CAD"), ("EURCHF", "EUR", "CHF"), ("EURJPY", "EUR", "JPY"),
    ("GBPAUD", "GBP", "AUD"), ("GBPNZD", "GBP", "NZD"), ("GBPCAD", "GBP", "CAD"),
    ("GBPCHF", "GBP", "CHF"), ("GBPJPY", "GBP", "JPY"),
    ("AUDNZD", "AUD", "NZD"), ("AUDCAD", "AUD", "CAD"), ("AUDCHF", "AUD", "CHF"),
    ("AUDJPY", "AUD", "JPY"),
    ("NZDCAD", "NZD", "CAD"), ("NZDCHF", "NZD", "CHF"), ("NZDJPY", "NZD", "JPY"),
    ("CADCHF", "CAD", "CHF"), ("CADJPY", "CAD", "JPY"), ("CHFJPY", "CHF", "JPY"),
)

for _name, _base, _quote in _CROSS_DEFS:
    PROFILES[_name] = AssetProfile(
        symbol=_name, base=_base, quote=_quote,
        pip=(0.01 if _quote == "JPY" else 0.0001),
        digits=(3 if _quote == "JPY" else 5),
        min_stop_pips=3.0, **_FX)

CROSSES: Tuple[str, ...] = tuple(n for n, _, _ in _CROSS_DEFS)

# Rổ GIAO DỊCH đầy đủ của danh mục nhiều chân: 7 major + 21 cross.
TRADED_ALL: Tuple[str, ...] = tuple(TIER1 + TIER2) + CROSSES


def usd_per_quote(symbol: str, prices: Dict[str, float]) -> float:
    """Tỷ giá QUOTE→USD của một cặp, suy từ giá 7 major.

    Cần cho MỌI phép quy notional và giá trị pip của cặp chéo: 1 lot GBPNZD là
    100.000 GBP, nhưng lãi/lỗ tính bằng NZD, và trần rủi ro thì tính bằng USD.
    Thiếu bước quy đổi này thì notional của cross sai theo đúng tỷ giá NZDUSD —
    khoảng 40% — và sai im lặng.

    Ném `KeyError` khi thiếu giá major cần thiết. Fail-closed: trả 1,0 làm mặc định
    là cách nhân notional lên gần gấp đôi cho các cặp quote JPY mà không ai biết.
    """
    prof = get(symbol)
    q = prof.quote
    if q == "USD":
        return 1.0
    direct = f"{q}USD"          # vd NZDUSD -> NZD sang USD là giá luôn
    if direct in prices and float(prices[direct]) > 0:
        return float(prices[direct])
    inverse = f"USD{q}"         # vd USDJPY -> JPY sang USD là 1/giá
    if inverse in prices and float(prices[inverse]) > 0:
        return 1.0 / float(prices[inverse])
    raise KeyError(
        f"{symbol}: cần tỷ giá {q}->USD để quy notional sang USD, nhưng thiếu cả "
        f"{direct} lẫn {inverse} trong bảng giá. Truyền đủ 7 major vào `prices`.")


def get(symbol: str) -> AssetProfile:
    try:
        return PROFILES[symbol.upper()]
    except KeyError:
        raise KeyError(f"Chưa có AssetProfile cho {symbol!r}. "
                       f"Đã khai: {sorted(PROFILES)}") from None


def is_fx(symbol: str) -> bool:
    return get(symbol).kind == "fx"
