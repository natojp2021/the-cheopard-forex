# -*- coding: utf-8 -*-
"""ftmo_risk_state.py — MÁY TRẠNG THÁI RỦI RO TÀI KHOẢN (Account Risk State Machine).

TÀI LIỆU MỎ NEO: `docs/ftmo/ftmo-risk-and-reward.md` §I.2 mục 2
================================================================
Tài liệu đặc tả một thang trạng thái CÓ TÊN:

    [+5% / +2%]  --> HEALTHY       (Sizing 100% chuẩn)
       [ 0% ]    --> NEUTRAL       (Trạng thái cân bằng)
    [-1% / -2%]  --> NORMAL DD     (Khởi động quản trị drawdown nhẹ)
      [ -3% ]    --> CAUTION       (Giảm 25% risk per trade)
      [ -4% ]    --> HIGH RISK     (Giảm 50% risk per trade, siết chặt filter)
      [-4.5%]    --> DEFENSIVE     (Chỉ cho phép chiến lược Win-rate cao)
      [ -5% ]    --> HARD STOP     (Cầu dao tự động đóng sạch vị thế)

VÌ SAO TÁCH THÀNH MODULE RIÊNG
===============================
Trước 07/08, `ftmo.evaluate()` có một chuỗi `if/elif` tính hệ số rủi ro rải rác
giữa các nhánh chặn. Nó ĐÚNG về mặt số học nhưng có ba vấn đề:

  1. **Không có tên trạng thái.** Log/email/GUI chỉ nói được "risk ×0.25", không
     nói được hệ thống đang ở đâu trên thang. Người vận hành không đọc được
     "còn bao xa tới cầu dao".
  2. **Không kiểm được từng bậc.** Muốn viết test cho bậc CAUTION phải dựng cả
     một `ComplianceState` với state file, mốc ngày, mốc tháng. Nên thực tế
     không ai test từng bậc, và các bậc trôi khỏi tài liệu mà không ai biết.
  3. **Thứ tự nhánh quyết định kết quả.** Ghi chú ngay trong `ftmo.py` đã ghi
     nhận một nhánh (`DAILY_EMERGENCY`) "gần như không bao giờ chạy" vì nhánh
     trước bắt mất. Đó là dấu hiệu kinh điển của logic phân loại bị nhét vào
     luồng điều khiển.

Module này là HÀM THUẦN: vào là ba con số, ra là một trạng thái có tên. Không
đọc file, không gọi broker, không phụ thuộc đồng hồ. Nhờ đó test được từng bậc
bằng đúng con số của tài liệu.

CƠ SỞ ĐO: LỖ NGÀY (daily drawdown), KHÔNG PHẢI TỔNG
=====================================================
Thang trong tài liệu kết thúc ở "-5% -> HARD STOP", và 5% là **giới hạn lỗ
NGÀY** của FTMO (giới hạn tổng là 10%). Bậc -4,5% cũng trùng đúng ngưỡng đóng
sạch theo lỗ ngày dự báo đã có sẵn trong `ftmo.DAILY_FLATTEN_PROJECTED`.

Trục TỔNG được xét SONG SONG chứ không trộn vào cùng thang: một tài khoản lỗ
7% tổng nhưng hôm nay chưa lỗ gì vẫn nguy hiểm, và thang lỗ-ngày không thấy
điều đó. Lấy trạng thái NGHIÊM TRỌNG HƠN trong hai trục.
"""
from __future__ import annotations

import enum
import math
from dataclasses import dataclass
from typing import Optional


class AccountRiskState(enum.Enum):
    """Bậc trạng thái rủi ro tài khoản, xếp theo mức độ nghiêm trọng TĂNG DẦN.

    Giá trị số dùng để so sánh "bậc nào nghiêm trọng hơn" — KHÔNG dùng thứ tự
    khai báo của `enum` vì thứ tự đó dễ bị đổi khi ai đó chèn bậc mới vào giữa.
    """

    HEALTHY = 0        # đang lãi — cỡ lệnh chuẩn
    NEUTRAL = 1        # quanh hoà vốn
    NORMAL_DD = 2      # sụt nhẹ, chưa cần can thiệp
    CAUTION = 3        # giảm 25% cỡ lệnh
    HIGH_RISK = 4      # giảm 50% cỡ lệnh, siết bộ lọc
    DEFENSIVE = 5      # ngừng mở lệnh mới
    HARD_STOP = 6      # đóng sạch vị thế

    @property
    def severity(self) -> int:
        return int(self.value)


# ───────────────────────────────────────────────────────── ngưỡng theo tài liệu
# Ngưỡng LỖ NGÀY (tỷ lệ vốn ban đầu). Đọc là "lỗ ngày >= ngưỡng thì vào bậc này".
DAILY_CAUTION = 0.03
DAILY_HIGH_RISK = 0.04
DAILY_DEFENSIVE = 0.045
DAILY_HARD_STOP = 0.05

# Ngưỡng TỔNG (tỷ lệ vốn ban đầu). Trục song song — xem docstring đầu file.
# Giới hạn cứng là 10%; các bậc đặt sao cho HARD_STOP còn đệm 2 điểm phần trăm
# để lệnh đóng kịp khớp (cùng lập luận với `ftmo.TOTAL_FLATTEN_PROJECTED`).
TOTAL_CAUTION = 0.04
TOTAL_HIGH_RISK = 0.06
TOTAL_DEFENSIVE = 0.07
TOTAL_HARD_STOP = 0.08

# Ngưỡng LÃI để gọi là HEALTHY (tài liệu: "[+5% / +2%] --> HEALTHY").
PROFIT_HEALTHY = 0.02

# Hệ số cỡ lệnh của từng bậc — đúng con số tài liệu ghi trong ngoặc.
#   CAUTION   "Giảm 25% risk per trade"  -> còn 0,75
#   HIGH_RISK "Giảm 50% risk per trade"  -> còn 0,50
#   DEFENSIVE "Chỉ cho phép chiến lược Win-rate cao" -> hệ thống này không có
#             trục win-rate ở tầng sizing, nên diễn giải bảo thủ hơn: NGỪNG mở
#             lệnh mới. Chọn cách nghiêm hơn là đúng thứ tự ưu tiên đã chốt
#             (Account Survival đứng trên Profit Maximization) và tránh việc
#             một khái niệm chưa triển khai được biến thành "cứ giao dịch tiếp".
_STATE_RISK_MULTIPLIER = {
    AccountRiskState.HEALTHY: 1.00,
    AccountRiskState.NEUTRAL: 1.00,
    AccountRiskState.NORMAL_DD: 1.00,
    AccountRiskState.CAUTION: 0.75,
    AccountRiskState.HIGH_RISK: 0.50,
    AccountRiskState.DEFENSIVE: 0.00,
    AccountRiskState.HARD_STOP: 0.00,
}

# Diễn giải bằng lời trader — dùng cho log, email và GUI.
STATE_MEANING = {
    AccountRiskState.HEALTHY: "Đang lãi — giao dịch cỡ lệnh chuẩn",
    AccountRiskState.NEUTRAL: "Quanh hoà vốn — bình thường",
    AccountRiskState.NORMAL_DD: "Sụt nhẹ — bình thường, chưa cần can thiệp",
    AccountRiskState.CAUTION: "Cảnh báo — giảm 25% cỡ lệnh",
    AccountRiskState.HIGH_RISK: "Rủi ro cao — giảm 50% cỡ lệnh, siết bộ lọc",
    AccountRiskState.DEFENSIVE: "Phòng thủ — NGỪNG mở lệnh mới, chỉ quản lý lệnh đang có",
    AccountRiskState.HARD_STOP: "Cầu dao — ĐÓNG SẠCH vị thế ngay",
}


@dataclass(frozen=True)
class RiskStateDecision:
    """Kết quả phân loại. Bất biến — đây là một phép ĐO, không phải trạng thái."""

    state: AccountRiskState            # Bậc trạng thái rủi ro phân loại được
    risk_multiplier: float             # Hệ số rủi ro áp dụng (ví dụ: 1.0, 0.75, 0.5, 0.0)
    allow_new_entries: bool            # Cờ cho phép mở vị thế mới hay không
    flatten_positions: bool            # Cờ yêu cầu đóng sạch vị thế lập tức (cầu dao)
    reason: str                        # Chuỗi giải thích lý do để ghi log/email
    # Trục nào quyết định bậc này ("daily" | "total" | "profit"). Cần cho log:
    # "HIGH_RISK vì lỗ ngày 4,1%" khác hẳn "HIGH_RISK vì tổng đã lỗ 6,2%", và
    # hai tình huống đó đòi hai hành động khác nhau từ người vận hành.
    driver: str = ""

    @property
    def meaning(self) -> str:
        return STATE_MEANING.get(self.state, "")


def _classify_daily(daily_dd: float) -> AccountRiskState:
    """Bậc theo trục LỖ NGÀY. Xếp từ nặng xuống nhẹ để bậc nặng luôn thắng."""
    if daily_dd >= DAILY_HARD_STOP:
        return AccountRiskState.HARD_STOP
    if daily_dd >= DAILY_DEFENSIVE:
        return AccountRiskState.DEFENSIVE
    if daily_dd >= DAILY_HIGH_RISK:
        return AccountRiskState.HIGH_RISK
    if daily_dd >= DAILY_CAUTION:
        return AccountRiskState.CAUTION
    if daily_dd > 0:
        return AccountRiskState.NORMAL_DD
    return AccountRiskState.NEUTRAL


def _classify_total(total_dd: float) -> AccountRiskState:
    """Bậc theo trục TỔNG (so với vốn ban đầu, mốc TĨNH của FTMO 2-Step)."""
    if total_dd >= TOTAL_HARD_STOP:
        return AccountRiskState.HARD_STOP
    if total_dd >= TOTAL_DEFENSIVE:
        return AccountRiskState.DEFENSIVE
    if total_dd >= TOTAL_HIGH_RISK:
        return AccountRiskState.HIGH_RISK
    if total_dd >= TOTAL_CAUTION:
        return AccountRiskState.CAUTION
    if total_dd > 0:
        return AccountRiskState.NORMAL_DD
    return AccountRiskState.NEUTRAL


def classify(daily_dd: float, total_dd: float,
             period_profit: float = 0.0,
             projected_daily_dd: Optional[float] = None,
             projected_total_dd: Optional[float] = None) -> RiskStateDecision:
    """Phân loại trạng thái rủi ro tài khoản. Hàm THUẦN, không tác dụng phụ.

    Tham số — TẤT CẢ là tỷ lệ của VỐN BAN ĐẦU, không phải của equity hiện tại.
    Dùng chung mẫu số là điều kiện để cộng/so sánh chúng có nghĩa; sai mẫu số là
    lỗi đã từng xảy ra trong `ftmo.evaluate()` (xem ghi chú "MẪU SỐ PHẢI GIỐNG").

      daily_dd            : lỗ ngày ĐÃ thực hiện (>= 0; 0 nghĩa là chưa lỗ).
      total_dd            : tổng sụt so với vốn ban đầu (>= 0).
      period_profit       : lãi của kỳ hiện tại; > 0 mới có thể là HEALTHY.
      projected_daily_dd  : lỗ ngày DỰ BÁO = đã lỗ + rủi ro các vị thế đang mở.
                            Bỏ trống -> dùng `daily_dd` (mất lớp bảo vệ dự báo).
      projected_total_dd  : tương tự cho trục tổng.

    VÌ SAO DỰ BÁO LÀ THAM SỐ RIÊNG chứ không để caller tự cộng vào `daily_dd`:
    hai con số phải được phân biệt trong LÝ DO trả về. Người vận hành cần biết
    "đã lỗ 4,5%" khác với "mới lỗ 2% nhưng đang ôm 2,5% rủi ro" — cùng bậc, hai
    hành động khác nhau hoàn toàn.

    ĐẦU VÀO KHÔNG HỢP LỆ -> HARD_STOP. `NaN` lọt qua mọi phép so sánh (kể cả
    `>=`), nên nếu không chặn thì một `NaN` sẽ được phân loại là NEUTRAL và mở
    khoá toàn bộ hệ thống đúng lúc phép đo drawdown đã hỏng. Đây là biến thể của
    họ lỗi fail-open đã lặp nhiều lần trong dự án.
    """
    for field_name, value in (("daily_dd", daily_dd), ("total_dd", total_dd),
                         ("period_profit", period_profit)):
        if value is None or not isinstance(value, (int, float)) \
                or not math.isfinite(float(value)):
            return RiskStateDecision(
                state=AccountRiskState.HARD_STOP, risk_multiplier=0.0,
                allow_new_entries=False, flatten_positions=False,
                reason=(f"{field_name}={value!r} không phải số hữu hạn — không đo được "
                        f"khoảng cách tới giới hạn FTMO, fail-closed"),
                driver="invalid")

    daily_dd = max(0.0, float(daily_dd))
    total_dd = max(0.0, float(total_dd))
    proj_daily = max(daily_dd, float(projected_daily_dd)
                     if projected_daily_dd is not None
                     and math.isfinite(float(projected_daily_dd)) else daily_dd)
    proj_total = max(total_dd, float(projected_total_dd)
                     if projected_total_dd is not None
                     and math.isfinite(float(projected_total_dd)) else total_dd)

    daily_state = _classify_daily(proj_daily)
    total_state = _classify_total(proj_total)
    state = daily_state if daily_state.severity >= total_state.severity else total_state
    driver = "daily" if daily_state.severity >= total_state.severity else "total"

    # HEALTHY chỉ khi ĐANG LÃI và KHÔNG có sụt nào đáng kể trên cả hai trục.
    # Đặt sau cùng vì nó là bậc NHẸ NHẤT — không được phép ghi đè một bậc nặng.
    if (state.severity <= AccountRiskState.NEUTRAL.severity
            and period_profit >= PROFIT_HEALTHY):
        state, driver = AccountRiskState.HEALTHY, "profit"

    reason_text = _build_reason(state, driver, daily_dd, total_dd, proj_daily,
                          proj_total, period_profit)
    return RiskStateDecision(
        state=state,
        risk_multiplier=_STATE_RISK_MULTIPLIER[state],
        allow_new_entries=state.severity < AccountRiskState.DEFENSIVE.severity,
        flatten_positions=state is AccountRiskState.HARD_STOP,
        reason=reason_text, driver=driver)


def _build_reason(state: AccountRiskState, driver: str, daily_dd: float,
                  total_dd: float, proj_daily: float, proj_total: float,
                  period_profit: float) -> str:
    """Câu giải thích cho log/email. Nói RÕ con số nào đẩy vào bậc này.

    Phân biệt "đã lỗ" với "dự báo" một cách tường minh: hai tình huống cùng bậc
    nhưng đòi hai hành động khác nhau từ người vận hành.
    """
    label = state.name
    if driver == "profit":
        return f"{label}: đang lãi {period_profit:+.2%} — cỡ lệnh chuẩn"
    if driver == "daily":
        if proj_daily > daily_dd + 1e-9:
            return (f"{label}: lỗ ngày DỰ BÁO {proj_daily:.2%} "
                    f"(đã lỗ {daily_dd:.2%} + rủi ro đang mở "
                    f"{proj_daily - daily_dd:.2%})")
        return f"{label}: lỗ ngày {daily_dd:.2%}"
    if driver == "total":
        if proj_total > total_dd + 1e-9:
            return (f"{label}: tổng sụt DỰ BÁO {proj_total:.2%} "
                    f"(đã mất {total_dd:.2%} + rủi ro đang mở "
                    f"{proj_total - total_dd:.2%})")
        return f"{label}: tổng sụt {total_dd:.2%} so với vốn ban đầu"
    return label


def distance_to_hard_stop(daily_dd: float, total_dd: float) -> dict:
    """Còn bao xa tới cầu dao, tính bằng điểm phần trăm — cho log và email.

    Trả cả hai trục vì trục nào cạn trước là thông tin quyết định: cạn trục ngày
    thì mai reset, cạn trục tổng thì hết thật.
    """
    return {
        "daily_room": max(0.0, DAILY_HARD_STOP - max(0.0, float(daily_dd or 0.0))),
        "total_room": max(0.0, TOTAL_HARD_STOP - max(0.0, float(total_dd or 0.0))),
    }
