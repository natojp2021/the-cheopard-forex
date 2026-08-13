"""symbol_spec.py — thông số hợp đồng của symbol, đọc từ MT5 với đường lùi an toàn.

VIẾT LẠI HOÀN TOÀN 13/08/2026. Bản cũ ghim XAUUSD làm symbol mặc định và dùng bảng
thông số của vàng cho MỌI symbol lạ — với hệ Forex thì đó không phải "hơi bảo thủ",
đó là sai số sizing ~1.000 lần (vàng 100 oz/lot, point 0,01; EURUSD 100.000 đơn vị,
point 0,00001).

NGUYÊN TẮC
==========
Nguồn chân lý là **MT5 của chính broker đang dùng** — số lot tối thiểu, bước lot,
contract size, digits đều là thứ broker quyết định và có thể khác nhau giữa các nhà
cung cấp. Bảng fallback ở đây CHỈ phục vụ nghiên cứu offline và test; nếu một symbol
sắp giao dịch tiền thật mà phải rơi vào fallback thì đó là lỗi cấu hình, không phải
một mặc định chấp nhận được — nên hàm `resolve()` ghi log CẢNH BÁO ở trường hợp đó.

Thông số dùng cho nghiên cứu (pip, contract size, commission) nằm ở
`shared/asset_profile.py`; module này lo phần **thực thi** (lot step, stops level,
digits) mà chỉ MT5 mới biết.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from src.python.utils.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class SymbolSpec:
    """Thông số thực thi của một symbol."""
    symbol: str
    digits: int
    point: float
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    stops_level_points: int = 0     # khoảng SL/TP tối thiểu broker chấp nhận
    freeze_level_points: int = 0    # vùng broker CẤM sửa lệnh quanh giá hiện tại
    filling_mode: int = 0           # ORDER_FILLING_* mà broker chấp nhận
    from_broker: bool = False       # True = đọc thật từ MT5, False = fallback

    # ── ba thuộc tính dưới đây là API mà `mt5_bridge` (kế thừa từ The Cheopard)
    # gọi tới. Giữ đúng tên và ngữ nghĩa để không phải sửa module đặt lệnh.
    @property
    def min_stop_dist(self) -> float:
        """Khoảng cách TỐI THIỂU từ giá tới SL/TP, tính bằng ĐƠN VỊ GIÁ.

        Broker từ chối lệnh có SL gần hơn mức này. Trả về đơn vị giá chứ không phải
        điểm, vì mọi phép so sánh ở tầng đặt lệnh đều làm trên giá — quy đổi ở đây
        một lần thay vì rải phép nhân `point` khắp nơi.
        """
        return self.stops_level_points * self.point

    @property
    def freeze_dist(self) -> float:
        """Vùng ĐÓNG BĂNG quanh giá: broker cấm sửa/huỷ lệnh khi giá lọt vào đây.

        Khác `min_stop_dist` ở chỗ nó chặn việc SỬA lệnh đã có, không phải việc ĐẶT
        lệnh mới. Nhiều broker để 0; khi đó mọi lệnh sửa đều được chấp nhận.
        """
        return self.freeze_level_points * self.point

    def round_price(self, price: float) -> float:
        """Làm tròn giá về đúng số chữ số của symbol.

        Gửi giá thừa chữ số làm broker trả `Invalid price` — lỗi này không hiện ra
        lúc backtest vì backtest không có broker nào từ chối.
        """
        return round(float(price), self.digits)

    def normalize_volume(self, volume: float) -> float:
        """Làm tròn khối lượng về bội của `volume_step`, kẹp trong [min, max].

        Làm tròn XUỐNG có chủ ý: vượt trần rủi ro vì làm tròn lên là lỗi im lặng,
        còn thiếu một bước lot thì chỉ là rủi ro nhỏ hơn dự kiến.
        """
        if volume <= 0:
            return 0.0
        steps = int(volume / self.volume_step)
        v = steps * self.volume_step
        v = max(self.volume_min, min(v, self.volume_max))
        return round(v, 8)


# Fallback CHỈ cho nghiên cứu offline: chuẩn FX 100.000 đơn vị/lot.
# Cặp JPY có digits 3 (point 0,001), các cặp còn lại digits 5 (point 0,00001).
def _fx_fallback(symbol: str) -> SymbolSpec:
    is_jpy = symbol.upper().endswith("JPY")
    return SymbolSpec(
        symbol=symbol,
        digits=3 if is_jpy else 5,
        point=0.001 if is_jpy else 0.00001,
        contract_size=100_000.0,
        volume_min=0.01, volume_max=100.0, volume_step=0.01,
        stops_level_points=0, from_broker=False,
    )


def resolve(symbol: str, mt5_module=None) -> SymbolSpec:
    """Thông số của `symbol`: ưu tiên MT5, rơi về chuẩn FX nếu không có.

    `mt5_module` truyền vào để test được mà không cần MT5 thật; ở live thì để None
    và hàm tự import.
    """
    mt5 = mt5_module
    if mt5 is None:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except ImportError:
            mt5 = None

    if mt5 is not None:
        info = mt5.symbol_info(symbol)
        if info is None and hasattr(mt5, "symbol_select"):
            mt5.symbol_select(symbol, True)
            info = mt5.symbol_info(symbol)
        if info is not None:
            return SymbolSpec(
                symbol=symbol,
                digits=int(info.digits),
                point=float(info.point),
                contract_size=float(info.trade_contract_size),
                volume_min=float(info.volume_min),
                volume_max=float(info.volume_max),
                volume_step=float(info.volume_step),
                stops_level_points=int(getattr(info, "trade_stops_level", 0)),
                from_broker=True,
            )

    log.warning("symbol_spec: KHÔNG đọc được %s từ MT5 — dùng chuẩn FX 100.000/lot. "
                "Nếu symbol này giao dịch tiền thật, PHẢI xác minh lại thông số.",
                symbol)
    return _fx_fallback(symbol)


# ═══════════════════════════════════════════════════════ API cho tầng đặt lệnh
# `mt5_bridge` gọi `get_symbol_spec(symbol)` và `symbol_spec.invalidate()`. Hai tên
# này đến từ hệ XAUUSD; giữ nguyên để module đặt lệnh kế thừa chạy không phải sửa.
_cache: Dict[str, SymbolSpec] = {}


def get_symbol_spec(symbol: str, mt5_module=None) -> SymbolSpec:
    """Thông số symbol, có cache trong tiến trình.

    Cache là cần thiết chứ không phải tối ưu: `mt5.symbol_info()` là lời gọi IPC tới
    terminal, và tầng đặt lệnh hỏi thông số cho MỖI lệnh. Không cache thì mỗi lệnh
    tốn thêm một vòng IPC đúng lúc cần nhanh nhất.

    ⚠️ Cache phải được XOÁ khi đổi terminal hoặc đổi tài khoản — dùng `invalidate()`.
    Broker khác nhau có `digits`, `volume_step`, `stops_level` khác nhau, và dùng
    thông số của broker cũ để đặt lệnh trên broker mới là lỗi im lặng: lệnh bị từ
    chối, hoặc tệ hơn, khớp với khối lượng sai.
    """
    key = symbol.upper()
    hit = _cache.get(key)
    if hit is not None:
        return hit
    spec = resolve(symbol, mt5_module=mt5_module)
    _cache[key] = spec
    return spec


def invalidate(symbol: Optional[str] = None) -> None:
    """Xoá cache. Không truyền `symbol` thì xoá tất cả.

    Gọi sau mỗi lần kết nối lại terminal: thông số phải dựng lại từ terminal MỚI.
    """
    if symbol is None:
        _cache.clear()
    else:
        _cache.pop(symbol.upper(), None)
