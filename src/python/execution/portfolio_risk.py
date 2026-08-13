"""portfolio_risk.py — đọc rủi ro THẬT từ vị thế broker, không từ ý định của chiến lược.

VÌ SAO PHẢI ĐỌC TỪ BROKER
==========================
`portfolio_sizing` tính rủi ro từ tỷ trọng MONG MUỐN. Đó là ý định, không phải sự
thật. Giữa ý định và sự thật có: lệnh khớp một phần, lệnh bị từ chối, lệnh trượt
giá, vị thế còn sót từ phiên trước, và vị thế do người vận hành mở tay. Mỗi thứ
trong đó làm rủi ro thật khác rủi ro tính toán, và không cái nào phát ra exception.

Hệ XAUUSD có `core/execution/portfolio_risk.py` làm việc này cho một tài sản với
dừng lỗ từng lệnh: rủi ro mở = tổng (khoảng cách tới SL × giá trị điểm). Công thức
đó VÔ NGHĨA ở đây vì 27 chân không đặt SL chiến lược — không có "khoảng cách tới SL"
để cộng. Bản này vì vậy viết lại quanh ba đại lượng đo được trên sổ FX:

    PHƠI NHIỄM   tổng notional / equity, so với trần đòn bẩy 3,7x
    ĐUÔI         notional × ngày tệ nhất đã quan sát, so với mốc lỗ ngày 5%
    BẢO VỆ       có bao nhiêu vị thế KHÔNG có lệnh dừng nào trên server broker

Đại lượng thứ ba là thứ hệ này thiếu hẳn cho tới 14/08/2026 — xem `disaster_stop`.

FAIL-CLOSED
===========
Không đọc được vị thế thì hàm BÁO LỖI, không trả về "sổ rỗng". Coi lỗi đọc là
"không có vị thế nào" là cách một tài khoản đầy lệnh bị nhìn thành tài khoản trống,
rồi tầng trên cấp thêm phơi nhiễm lên trên phơi nhiễm nó không thấy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.python.core.infra import ftmo
from src.python.core.infra import target_mode
from src.python.execution import ftmo_leverage_policy as POL
from src.python.shared import asset_profile as AP

# Ngày tệ nhất ĐÃ QUAN SÁT của danh mục 27 chân ở đòn bẩy 1,0, đơn vị % equity.
# Đo trên 2.389 ngày 2020-01 → 2026-07. Dùng để quy phơi nhiễm hiện tại thành tổn
# thất đuôi ước lượng — cùng nguồn số với `ftmo_leverage_policy.TAIL_BUFFER`.
PORTFOLIO_WORST_DAY_PCT = 0.794


@dataclass(frozen=True)
class PositionRisk:
    """Rủi ro của MỘT vị thế đang mở trên broker."""
    symbol: str
    side: str                    # BUY | SELL
    lots: float
    notional_usd: float
    profit_usd: float
    has_stop: bool               # có SL nằm trên SERVER broker hay không
    stop_distance_pct: Optional[float]


@dataclass
class RiskSnapshot:
    """Ảnh chụp rủi ro cả sổ tại một thời điểm."""
    equity_usd: float
    positions: List[PositionRisk] = field(default_factory=list)
    gross_notional_usd: float = 0.0
    net_exposure: Dict[str, float] = field(default_factory=dict)
    actual_leverage: float = 0.0
    tail_loss_pct: float = 0.0
    unprotected: List[str] = field(default_factory=list)
    breaches: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.breaches

    def explain(self) -> str:
        head = (f"{len(self.positions)} vị thế · notional ${self.gross_notional_usd:,.0f} "
                f"= {self.actual_leverage:.2f}x equity · tổn thất đuôi ước lượng "
                f"{self.tail_loss_pct:.2f}%")
        if self.unprotected:
            head += f" · {len(self.unprotected)} vị thế KHÔNG có lệnh dừng"
        if self.breaches:
            return head + "\n  VI PHẠM: " + "\n  VI PHẠM: ".join(self.breaches)
        return head + " · đạt"


def _notional_usd(symbol: str, lots: float, price: float) -> float:
    """Notional quy USD. Cặp XXXUSD thì giá đã là tỷ giá sang USD; USDXXX thì chia."""
    try:
        prof = AP.get(symbol)
        size = float(prof.contract_size)
    except Exception:
        size = 100_000.0
    base = abs(float(lots)) * size
    if symbol.endswith("USD"):
        return base * float(price)
    if symbol.startswith("USD"):
        return base
    # Cross không chứa USD: quy đổi cần tỷ giá thứ ba. Lấy notional theo đồng CƠ SỞ
    # là ước lượng THẤP HƠN thực tế cho cặp mạnh hơn USD — ghi rõ để không ai coi
    # con số này là chính xác tuyệt đối.
    return base


def snapshot(mt5, equity_usd: float, *,
             leverage_cap: float = POL.LEVERAGE_MAX,
             worst_day_pct: float = PORTFOLIO_WORST_DAY_PCT) -> RiskSnapshot:
    """Đọc toàn bộ vị thế từ broker và chấm ba ràng buộc.

    `mt5` là module MetaTrader5 đã `initialize()`. Truyền module giả trong test.
    Ném `RuntimeError` khi không đọc được — fail-closed, xem docstring đầu file.
    """
    raw = mt5.positions_get()
    if raw is None:
        raise RuntimeError(
            "positions_get() trả None — KHÔNG đọc được vị thế từ broker. Không được "
            "coi đây là 'sổ rỗng': mọi ràng buộc phơi nhiễm phía sau sẽ tính trên một "
            "sổ trống trong khi tài khoản có thể đang đầy lệnh.")

    snap = RiskSnapshot(equity_usd=float(equity_usd))
    expo: Dict[str, float] = {}

    for p in raw:
        symbol = str(getattr(p, "symbol", ""))
        lots = float(getattr(p, "volume", 0.0) or 0.0)
        price = float(getattr(p, "price_open", 0.0) or 0.0)
        sl = float(getattr(p, "sl", 0.0) or 0.0)
        side = "BUY" if int(getattr(p, "type", 0)) == 0 else "SELL"
        notional = _notional_usd(symbol, lots, price)
        dist = (abs(price - sl) / price * 100.0) if (sl > 0 and price > 0) else None

        snap.positions.append(PositionRisk(
            symbol=symbol, side=side, lots=lots,
            notional_usd=round(notional, 2),
            profit_usd=float(getattr(p, "profit", 0.0) or 0.0),
            has_stop=sl > 0,
            stop_distance_pct=(round(dist, 4) if dist is not None else None)))

        snap.gross_notional_usd += notional
        if sl <= 0:
            snap.unprotected.append(symbol)

        sgn = 1.0 if side == "BUY" else -1.0
        if len(symbol) >= 6:
            base, quote = symbol[:3], symbol[3:6]
            expo[base] = expo.get(base, 0.0) + sgn * notional
            expo[quote] = expo.get(quote, 0.0) - sgn * notional

    snap.net_exposure = {k: round(v, 2) for k, v in sorted(expo.items())}
    snap.actual_leverage = round(
        snap.gross_notional_usd / snap.equity_usd, 4) if snap.equity_usd > 0 else 0.0
    snap.tail_loss_pct = round(snap.actual_leverage * worst_day_pct, 3)

    # ── ba ràng buộc
    if snap.actual_leverage > leverage_cap:
        snap.breaches.append(
            f"phơi nhiễm {snap.actual_leverage:.2f}x vượt trần {leverage_cap:.2f}x — "
            f"trần này neo vào MaxDD 9% nội bộ, vượt nó là vượt cả ngân sách drawdown")
    if snap.tail_loss_pct > ftmo.DAILY_LOSS_HARD * 100.0:
        snap.breaches.append(
            f"ngày tệ nhất đã quan sát ({worst_day_pct:.3f}%) ở phơi nhiễm hiện tại "
            f"thành {snap.tail_loss_pct:.2f}% — vượt mốc lỗ ngày "
            f"{ftmo.DAILY_LOSS_HARD * 100:.0f}% của FTMO")
    if snap.unprotected:
        snap.breaches.append(
            f"{len(snap.unprotected)} vị thế KHÔNG có lệnh dừng trên server broker "
            f"({', '.join(sorted(set(snap.unprotected))[:6])}"
            f"{'…' if len(set(snap.unprotected)) > 6 else ''}) — nếu tiến trình chết "
            f"thì không có gì đóng chúng. Xem `execution/disaster_stop.py`.")

    warn = target_mode.notional_gap_warning(snap.gross_notional_usd, snap.equity_usd)
    if warn:
        snap.breaches.append(warn)
    return snap


def reconcile(snap: RiskSnapshot, targets, *, tolerance_lots: float = 0.01
              ) -> Dict[str, Dict[str, float]]:
    """So vị thế THẬT với lot MỤC TIÊU. Trả các symbol lệch quá `tolerance_lots`.

    Lệch nghĩa là một trong hai: lệnh chưa khớp hết, hoặc có vị thế không ai đặt.
    Cả hai đều phải người vận hành nhìn — không tự sửa ở đây, vì tự đặt lệnh bù dựa
    trên một bản đọc có thể sai là cách nhân đôi vị thế.
    """
    real: Dict[str, float] = {}
    for p in snap.positions:
        real[p.symbol] = real.get(p.symbol, 0.0) + (
            p.lots if p.side == "BUY" else -p.lots)

    want = {str(o.symbol): (o.lots if o.direction == "BUY"
                            else -o.lots if o.direction == "SELL" else 0.0)
            for o in targets}

    out: Dict[str, Dict[str, float]] = {}
    for sym in sorted(set(real) | set(want)):
        r, w = real.get(sym, 0.0), want.get(sym, 0.0)
        if abs(r - w) > tolerance_lots:
            out[sym] = {"thật": round(r, 3), "mục tiêu": round(w, 3),
                        "lệch": round(r - w, 3)}
    return out
