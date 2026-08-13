"""disaster_stop.py — lệnh dừng lỗ THẢM HOẠ đặt trên broker, cho danh mục không có SL.

VÌ SAO MODULE NÀY TỒN TẠI, KHI CẢ 27 CHÂN ĐỀU CỐ Ý KHÔNG CÓ DỪNG LỖ
====================================================================
Hai loại dừng lỗ khác nhau, và lẫn chúng là cách phá hỏng chiến lược:

    dừng lỗ CHIẾN LƯỢC   "luận điểm giao dịch đã sai"      → hệ này KHÔNG dùng
    dừng lỗ THẢM HOẠ     "phần mềm đã chết"                → hệ này BẮT BUỘC có

Loại thứ nhất bị loại có bằng chứng. Đo LẠI ngày 14/08/2026 trên chính danh mục 22
chân một-công-cụ đang chạy (`research/fx/sl_test.py`, mô phỏng MAE trên 100% lệnh
thật, quét bóng nến chứ không đợi nến đóng):

    SL         Sharpe   FORM    OOS    MaxDD(σ)   chân TỆ ĐI   % lệnh bị dừng
    không có   3,634    3,836   3,298    4,00       0/22            0,0%
    1×ATR      2,786    2,918   2,567    5,03      20/22            6,4%
    2×ATR      3,272    3,411   3,055    3,66      16/22            1,1%
    3×ATR      3,521    3,703   3,222    3,87       5/22            0,3%
    4×ATR      3,563    3,733   3,290    3,97       3/22            0,1%
    8×ATR      3,579    3,755   3,295    4,01       1/22            0,0%
    12×ATR     3,634    3,836   3,298    4,00       0/22            0,0%

Ba điều đọc được, và điều thứ ba mới là điều quan trọng:

  1. MỌI mức SL đều tệ hơn không SL, và càng đặt gần càng tệ. Đơn điệu, không có
     điểm ngọt nào ở giữa.
  2. Ở 1×ATR mất 23% Sharpe — vì chiến lược hồi quy VÀO LỆNH KHI GIÁ ĐANG ĐI NGƯỢC,
     nên SL gần luôn bị quét đúng trước lúc hồi.
  3. **SL KHÔNG làm giảm drawdown.** Ở 1×ATR, MaxDD TỆ ĐI: 4,00σ → 5,03σ. Đây là
     phản trực giác nhưng đúng cơ chế: dừng lỗ biến một khoản lỗ CÒN HỒI ĐƯỢC thành
     một khoản lỗ ĐÃ THỰC HIỆN, rồi chiến lược vào lại và trả thêm một lượt phí.
     Nói cách khác, ở hệ này SL không mua được sự an toàn nào — nó chỉ tính tiền.

Vì vậy "không có SL chiến lược" không phải liều lĩnh; nó là mức tối ưu ĐO ĐƯỢC.

GIÁ CỦA CẦU CHÌ — CŨNG ĐO ĐƯỢC
===============================
Cùng bảng trên trả lời luôn câu "vậy đặt cầu chì tốn bao nhiêu": ở 8×ATR, Sharpe
3,634 → **3,579**, tức mất **1,5%**, và chỉ 1/22 chân bị ảnh hưởng, 0,0% số lệnh bị
dừng trong toàn bộ 6,5 năm. Đó là phí bảo hiểm cho việc không bao giờ để vị thế nằm
trần khi phần mềm chết — và đó chính là lý do `MIN_ATR_MULT = 8,0` chứ không phải 3.

Loại thứ hai KHÔNG liên quan gì tới chiến lược. Nó trả lời một câu khác hẳn:

    "Nếu tiến trình Python chết lúc 02:00 sáng thứ Tư, ai đóng vị thế?"

Câu trả lời hiện tại của hệ này là KHÔNG AI. Time-stop chỉ chạy khi bot còn sống;
`ftmo_leverage_policy` chỉ can thiệp ở lần quyết định kế tiếp. Mất điện, mất mạng,
Windows update, MT5 treo — vị thế đứng trần cho tới khi có người phát hiện. Hệ
XAUUSD tiền nhiệm có trạng thái `PROTECTED` nghĩa là SL đã nằm trên server broker;
hệ này port sang mà bỏ mất lớp đó.

CÁCH ĐẶT KHOẢNG CÁCH — TỪ NGÂN SÁCH, KHÔNG TỪ BIẾN ĐỘNG
========================================================
SL theo ATR là SL chiến lược trá hình: nó phản ứng với nhiễu thị trường, tức đúng
thứ vừa bị bác bỏ. Khoảng cách ở đây suy ngược từ **số tiền tối đa chấp nhận mất
trên MỘT vị thế nếu không ai còn ở đó**:

    tổn thất = notional × biến_động_giá
    notional = |tỷ trọng| × equity × đòn bẩy
    ⟹  biến_động_giá = ngân_sách_% / (|tỷ trọng| × đòn bẩy)

Với ngân sách 2,0% equity, đòn bẩy 3,7x và chân nặng nhất |w| = 0,11:

    khoảng cách = 2,0 / (0,11 × 3,7) = **4,9%** giá

So với σ ngày điển hình của FX (~0,5%) thì đó là **~10σ** — xa tới mức nhiễu thường
không bao giờ chạm, và chỉ một cú sập thật mới kích hoạt. Đúng ý đồ: nó là cầu chì,
không phải công tắc.

RÀNG BUỘC PHẢI KIỂM: CẦU CHÌ KHÔNG ĐƯỢC THÀNH CÔNG TẮC
=======================================================
Nếu khoảng cách tính ra NHỎ hơn `MIN_ATR_MULT × ATR ngày` thì vị thế đang quá lớn
so với ngân sách thảm hoạ, và SL sẽ bắt đầu cắt vào nhiễu bình thường — tức tái lập
đúng cái đã đo là làm tệ đi. `check()` báo lỗi thay vì âm thầm đặt SL gần.
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
    Danh mục 27 chân hiện tại có tỷ trọng lớn nhất 11,2% nên nằm dưới trần — nhưng
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
