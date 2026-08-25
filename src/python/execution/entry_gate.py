"""entry_gate.py — CỔNG AN TOÀN HỢP NHẤT, điểm hội tụ DUY NHẤT trước khi gửi lệnh.

VÌ SAO MỘT CỔNG, KHÔNG PHẢI NHIỀU `if` RẢI RÁC
===============================================
Mọi điều kiện an toàn gom vào MỘT hàm `evaluate()` với ngữ nghĩa **fail-closed**:
điều kiện nào KHÔNG XÁC ĐỊNH (`None`) thì coi như CHẶN.

Lý do nó phải như vậy: khi các cổng nằm rải rác trong pipeline, thêm một cổng mới
nghĩa là phải nhớ chèn đúng chỗ, và quên một chỗ thì không ai biết — không có test
nào bắt được "thiếu một lệnh `if`". Thêm cổng mới thì thêm THAM SỐ vào hàm này, và
chữ ký hàm là thứ trình biên dịch nhắc.

MỘT ĐIỀU CỐ Ý GIỮ: CỔNG NÀY CHỈ CHẶN MỞ LỆNH MỚI
=================================================
Nó không đóng vị thế đang mở, không gỡ dừng lỗ, không dừng đối soát. Vị thế đang mở
mà mất người quản lý là tình trạng NGUY HIỂM HƠN việc vào thêm lệnh — muốn đóng hết
thì dùng kill switch, đó là chức năng riêng và có xác nhận riêng.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class GateResult:
    """Kết quả cổng. `allowed=False` thì KHÔNG được gửi bất kỳ lệnh MỞ nào."""
    allowed: bool
    reasons: List[str] = field(default_factory=list)

    def explain(self) -> str:
        return "cho phép vào lệnh" if self.allowed else "CHẶN: " + " · ".join(self.reasons)


class EntryGate:
    """Cổng an toàn. Chỉ trả `allowed=True` khi MỌI điều kiện đều thoả."""

    @staticmethod
    def evaluate(*,
                 reconciliation_done: Optional[bool],
                 trading_enabled: Optional[bool],
                 ftmo_entries_allowed: Optional[bool],
                 leverage: Optional[float],
                 unprotected_positions: Optional[int],
                 regime_crisis: Optional[bool] = False,
                 news_blocked: bool = False,
                 news_reason: str = "",
                 ftmo_reason: str = "",
                 extra_blocks: Optional[List[str]] = None) -> GateResult:
        """Chấm mọi điều kiện. Ba tham số đầu `None` = CHẶN, không phải "bỏ qua".

        `leverage` là mức mà `ftmo_leverage_policy.decide()` vừa cấp: bằng 0 nghĩa là
        chính sách đã quyết định DỪNG (đệm cạn hoặc chạm sàn nội bộ 9%), và khi đó
        không được có lệnh mở nào — kể cả lệnh "nhỏ thôi".

        `unprotected_positions` là số vị thế đang mở KHÔNG có dừng lỗ trên server
        broker. Còn dù chỉ một vị thế như vậy thì mở thêm là chồng rủi ro không đo
        được lên rủi ro đã không đo được.
        """
        reasons: List[str] = []

        if reconciliation_done is not True:
            reasons.append(
                "đối soát khởi động CHƯA xong — chưa biết vị thế nào là của hệ, "
                "vị thế nào là lạ, nên mọi phép tính phơi nhiễm còn vô nghĩa")
        if trading_enabled is not True:
            reasons.append("công tắc giao dịch đang TẮT (người vận hành)")
        if ftmo_entries_allowed is not True:
            reasons.append("tầng FTMO không cho vào lệnh"
                           + (f" — {ftmo_reason}" if ftmo_reason else ""))
        if leverage is None:
            reasons.append("chưa có quyết định đòn bẩy — fail-closed")
        elif leverage <= 0.0:
            reasons.append("chính sách đòn bẩy trả 0 (HALT) — đệm equity đã cạn")
        if unprotected_positions is None:
            reasons.append("không đọc được trạng thái dừng lỗ của vị thế — fail-closed")
        elif unprotected_positions > 0:
            reasons.append(f"{unprotected_positions} vị thế đang mở KHÔNG có dừng lỗ "
                           f"trên broker — đặt dừng lỗ trước khi mở thêm")
        if regime_crisis:
            reasons.append("cổng chế độ CRISIS — biến động rổ ở phân vị cực đoan")
        if news_blocked:
            reasons.append("cổng tin CHẶN" + (f" — {news_reason}" if news_reason else ""))
        for b in (extra_blocks or []):
            reasons.append(b)

        return GateResult(allowed=not reasons, reasons=reasons)
