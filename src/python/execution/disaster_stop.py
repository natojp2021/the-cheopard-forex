"""disaster_stop.py — CẦU CHÌ HẠ TẦNG. Lớp cuối, KHÔNG phải dừng lỗ giao dịch.

HAI LOẠI DỪNG LỖ, VÀ ĐỪNG LẪN
==============================
    dừng lỗ CHIẾN LƯỢC   do chiến lược khai, 24-32 pip, đi kèm lệnh mở. Đây là luật
                         GIAO DỊCH — nó quyết định rủi ro mỗi lệnh.
    cầu chì (module này)  >= 8xATR. Đây là luật HẠ TẦNG — nó chỉ trả lời một câu:
                         nếu TIẾN TRÌNH CHẾT thì vị thế mất bao nhiêu trước khi
                         broker tự đóng?

Cầu chì LUÔN xa hơn dừng lỗ chiến lược, nên trong vận hành bình thường nó không bao
giờ chạm. Điều KHÔNG được làm là để cầu chì THAY dừng lỗ chiến lược: 8xATR trên
EURUSD là ~80 pip, tức gần BA LẦN rủi ro dự kiến của một lệnh.

VÌ SAO >= 8xATR, KHÔNG PHẢI 2-3xATR
====================================
Vì cầu chì phải nằm ĐỦ XA để không cắt ngang một lệnh còn hợp lệ. Một cầu chì đặt gần
sẽ biến thành một dừng lỗ mà không ai chọn — và nó cắt đúng những lệnh đang tạm âm
nhưng vẫn trong kịch bản. Đặt xa thì nó chỉ kích hoạt ở đúng tình huống nó sinh ra để
xử lý: phần mềm không còn chạy.

NGÂN SÁCH THEO VỊ THẾ
=====================
`PER_POSITION_BUDGET_PCT` giới hạn tổn thất TỐI ĐA của một vị thế nếu cầu chì nổ, tính
bằng % equity. Nó là ràng buộc NGƯỢC lên cỡ vị thế: cỡ càng lớn thì cầu chì phải càng
gần, và gần quá thì vi phạm nguyên tắc ở trên.

⚠️ Con số hiện tại được hiệu chỉnh cho một danh mục sizing theo TỶ TRỌNG. Chiến lược
hiện tại sizing theo KHOẢNG CÁCH SL nên rủi ro mỗi lệnh nhỏ hơn nhiều lần — ngân sách
này vì vậy chưa ràng buộc đúng đại lượng. Xem `registry.PORTFOLIO["can_do_lai"]`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

# Số tiền tối đa chấp nhận mất trên MỘT vị thế khi hệ thống không còn ai trông.
# 2,0% chọn theo hai ràng buộc: nhỏ hơn nhiều mốc lỗ ngày 5% của FTMO để một vị thế
# chạm cầu chì không tự nó gây vi phạm, và đủ lớn để khoảng cách rơi vào vùng ~10σ.
PER_POSITION_BUDGET_PCT = 2.0

# Cầu chì phải cách giá ít nhất ngần này lần ATR ngày. Dưới mức đó thì nó không còn
# là cầu chì. 8,0 vì SL 3×ATR đã đo được là làm hỏng kỳ vọng — biên gấp hơn hai lần.
MIN_ATR_MULT = 8.0

# Trần khoảng cách: xa hơn mức này thì cầu chì vô dụng vì tài khoản đã cháy trước.
# 12% ≈ vượt cả mốc lỗ tổng 10% của FTMO ở đòn bẩy 1,0.
MAX_DISTANCE_PCT = 12.0


@dataclass(frozen=True)
class DisasterStop:
    """Cầu chì cho MỘT vị thế. `ok=False` thì KHÔNG được gửi lệnh."""
    symbol: str
    side: str                    # BUY | SELL
    entry_price: float
    stop_price: float
    distance_pct: float          # khoảng cách theo % giá
    distance_atr: Optional[float]   # quy ra bội số ATR ngày, None nếu chưa đo
    loss_at_stop_usd: float
    ok: bool
    reason: str


def distance_pct(weight: float, leverage: float, *,
                 budget_pct: float = PER_POSITION_BUDGET_PCT) -> float:
    """Khoảng cách cầu chì theo % giá, suy từ ngân sách tổn thất một vị thế.

    Tỷ trọng càng nhỏ thì cầu chì càng xa — đúng: vị thế nhỏ cần cú sốc lớn hơn mới
    làm mất ngần ấy tiền. Tỷ trọng 0 trả về vô cực (không có gì để bảo vệ).
    """
    exposure = abs(float(weight)) * float(leverage)
    if exposure <= 0:
        return float("inf")
    return float(budget_pct) / exposure


def max_weight_for_fuse(atr_daily_pct: float, leverage: float, *,
                        budget_pct: float = PER_POSITION_BUDGET_PCT,
                        min_atr_mult: float = MIN_ATR_MULT) -> float:
    """Tỷ trọng LỚN NHẤT của một công cụ mà cầu chì vẫn đặt đủ xa.

    HỆ QUẢ KHÔNG ĐỊNH TRƯỚC NHƯNG ĐÚNG: lớp cầu chì áp một TRẦN TẬP TRUNG lên danh
    mục. Muốn cầu chì cách ít nhất `min_atr_mult × ATR` mà tổn thất tại đó không
    quá `budget_pct`, thì:

        budget / (w × lev) >= min_atr_mult × ATR
        ⟹  w <= budget / (lev × min_atr_mult × ATR)

    Với ATR ngày 0,5%, đòn bẩy 3,7x, ngân sách 2,0%: w <= **13,5%** một công cụ.
    Tỷ trọng lớn nhất của danh mục hiện tại nằm dưới trần — nhưng
    một danh mục chỉ vài chân hoạt động sẽ vượt, và khi đó `compute()` từ chối đúng
    như thiết kế: không phải "cầu chì hỏng" mà là "vị thế quá tập trung để bảo vệ".
    """
    denom = float(leverage) * float(min_atr_mult) * float(atr_daily_pct)
    return float(budget_pct) / denom if denom > 0 else float("inf")


def compute(symbol: str, side: str, entry_price: float, weight: float,
            leverage: float, equity_usd: float, *,
            atr_daily_pct: Optional[float] = None,
            min_stop_dist_price: float = 0.0,
            budget_pct: float = PER_POSITION_BUDGET_PCT) -> DisasterStop:
    """Cầu chì cho một vị thế. Kiểm cả ba ràng buộc trước khi trả `ok=True`.

    `atr_daily_pct` = ATR ngày quy theo % giá. Truyền `None` thì bỏ qua kiểm tra
    "cầu chì có quá gần không" — chỉ nên làm khi thật sự không đo được, vì đó chính
    là kiểm tra ngăn cầu chì thoái hoá thành SL chiến lược.
    """
    side = side.upper()
    if side not in ("BUY", "SELL"):
        return DisasterStop(symbol, side, entry_price, 0.0, 0.0, None, 0.0, False,
                            f"chiều không hợp lệ: {side!r}")
    if entry_price <= 0:
        return DisasterStop(symbol, side, entry_price, 0.0, 0.0, None, 0.0, False,
                            "giá vào lệnh <= 0")

    raw_pct = distance_pct(weight, leverage, budget_pct=budget_pct)
    if raw_pct == float("inf"):
        return DisasterStop(symbol, side, entry_price, 0.0, raw_pct, None, 0.0, False,
                            "tỷ trọng bằng 0 — không có vị thế để bảo vệ")

    notes: List[str] = []
    # Vị thế nhỏ cho ra khoảng cách rất xa (ngân sách chia cho phơi nhiễm bé). KẸP
    # về trần thay vì từ chối: cầu chì xa hơn 12% là cầu chì không bao giờ nổ, mà
    # từ chối đặt lại khiến vị thế nằm TRẦN — tệ hơn hẳn một cầu chì đặt gần hơn mức
    # ngân sách đòi. Kẹp luôn lệch về phía an toàn: tổn thất tối đa chỉ NHỎ đi.
    dpct = raw_pct
    if raw_pct > MAX_DISTANCE_PCT:
        dpct = MAX_DISTANCE_PCT
        notes.append(f"kẹp về trần {MAX_DISTANCE_PCT:.1f}% (ngân sách đòi "
                     f"{raw_pct:.1f}%) — vị thế nhỏ nên tổn thất tại cầu chì chỉ "
                     f"{abs(weight) * leverage * dpct:.2f}% equity")

    dprice = entry_price * dpct / 100.0
    stop = entry_price - dprice if side == "BUY" else entry_price + dprice
    d_atr = (dpct / atr_daily_pct) if (atr_daily_pct and atr_daily_pct > 0) else None
    loss = equity_usd * abs(weight) * leverage * dpct / 100.0

    reasons: List[str] = []
    if d_atr is not None and d_atr < MIN_ATR_MULT:
        reasons.append(f"cầu chì chỉ cách {d_atr:.1f}×ATR (tối thiểu {MIN_ATR_MULT}) "
                       f"— ở khoảng này nó cắt vào nhiễu bình thường và thành SL "
                       f"chiến lược, thứ đã đo được làm đổi dấu kỳ vọng")
    if min_stop_dist_price > 0 and dprice < min_stop_dist_price:
        reasons.append(f"gần hơn khoảng SL tối thiểu broker cho phép "
                       f"({min_stop_dist_price:.5f}) — broker sẽ từ chối lệnh")

    return DisasterStop(symbol=symbol, side=side, entry_price=float(entry_price),
                        stop_price=round(stop, 8), distance_pct=round(dpct, 4),
                        distance_atr=(round(d_atr, 2) if d_atr is not None else None),
                        loss_at_stop_usd=round(loss, 2),
                        ok=not reasons,
                        reason=" · ".join(reasons + notes) or "đạt")


def compute_book(weights, prices: Dict[str, float], *, leverage: float,
                 equity_usd: float,
                 atr_daily_pct: Optional[Dict[str, float]] = None,
                 min_stop_dist: Optional[Dict[str, float]] = None,
                 budget_pct: float = PER_POSITION_BUDGET_PCT
                 ) -> Dict[str, DisasterStop]:
    """Cầu chì cho CẢ SỔ, từ vector tỷ trọng của `portfolio.target_weights()`."""
    atr = atr_daily_pct or {}
    msd = min_stop_dist or {}
    out: Dict[str, DisasterStop] = {}
    for symbol, w in weights.items():
        w = float(w)
        if abs(w) < 1e-9:
            continue
        px = float(prices.get(str(symbol), 0.0))
        if px <= 0:
            continue
        out[str(symbol)] = compute(
            str(symbol), "BUY" if w > 0 else "SELL", px, w, leverage, equity_usd,
            atr_daily_pct=atr.get(str(symbol)),
            min_stop_dist_price=float(msd.get(str(symbol), 0.0)),
            budget_pct=budget_pct)
    return out


def worst_case_loss_pct(stops: Dict[str, DisasterStop], equity_usd: float) -> float:
    """Tổn thất % equity nếu MỌI cầu chì cùng nổ trong một ngày.

    ⚠️ ĐO ĐƯỢC 14/08/2026 TRÊN SỔ THẬT: **27,68%** — VƯỢT XA mốc lỗ ngày 5% của FTMO.
    Phải nói thẳng điều này thay vì để người đọc tưởng lớp cầu chì bảo đảm tuân thủ:

        LỚP CẦU CHÌ KHÔNG BẢO ĐẢM TUÂN THỦ FTMO. Nó chỉ biến một tổn thất KHÔNG có
        cận trên (vị thế trần khi phần mềm chết) thành một tổn thất CÓ cận trên.

    Và không thể có cả hai. Muốn tổng mọi cầu chì dưới 5% thì mỗi vị thế chỉ được
    0,2% ngân sách, tức khoảng cách 0,49% ≈ **1×ATR** — đúng vùng đã đo được là làm
    đổi dấu kỳ vọng (SL 3ATR cho −0,272 vs time-stop +0,070). Cầu chì đặt ở đó không
    còn là cầu chì, nó là SL chiến lược, và nó phá chiến lược.

    Ràng buộc 5% do lớp khác giữ, không phải lớp này:
        · trần đòn bẩy 3,7x  → ngày tệ nhất đã quan sát thành −2,94%
        · `ftmo_leverage_policy.decide()` co đòn bẩy khi đệm mỏng
        · người vận hành

    Con số 27,68% cũng là cận trên KHÔNG VẬT LÝ: nó giả định 24 vị thế hai chiều
    trên 8 đồng tiền cùng đi ngược tối đa một lúc. Sổ này long EUR ở cặp này và
    short EUR ở cặp khác — một cú sốc EUR không thể làm cả hai cùng lỗ.
    """
    if equity_usd <= 0:
        return 0.0
    total = sum(s.loss_at_stop_usd for s in stops.values() if s.ok)
    return round(total / equity_usd * 100.0, 3)
