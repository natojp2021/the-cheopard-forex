"""trading_control.py — CÔNG TẮC THỦ CÔNG của người vận hành. SSOT, bền vững trên đĩa.

CHUẨN LẤY TỪ `quant-xau/core/execution/trading_control.py`
==========================================================
Hệ XAUUSD có công tắc này và `entry_gate` của hệ Forex đã đòi tham số
`trading_enabled` từ đầu — nhưng KHÔNG module nào sinh ra giá trị đó. Cổng đang chờ
một thứ không tồn tại, và bên gọi phải tự bịa ra `True`. Đợt kiểm toán 14/08/2026
tìm ra chỗ này.

RANH GIỚI QUAN TRỌNG NHẤT — CHỈ CHẶN VÀO LỆNH MỚI
==================================================
Tắt công tắc KHÔNG:
    · đóng vị thế đang mở
    · gỡ cầu chì thảm hoạ trên broker
    · dừng đối soát, dừng ghi nhật ký, dừng đếm time-stop

Lý do giữ nguyên như hệ cũ: một vị thế đang mở mà mất người quản lý là tình trạng
NGUY HIỂM HƠN việc vào thêm lệnh. Muốn đóng sạch thì đó là kill switch — chức năng
riêng, có xác nhận riêng.

BỀN VỮNG TRÊN ĐĨA, KHÔNG PHẢI BIẾN TOÀN CỤC
============================================
Công tắc phải sống qua restart. Một người vận hành tắt giao dịch lúc 22:00 rồi bot
tự khởi động lại lúc 23:00 và bật lại giao dịch là đúng cái tình huống công tắc sinh
ra để chặn.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.python.core.infra import state_store
from src.python.shared.paths import RUNTIME_STATE_DIR

CONTROL_PATH = Path(RUNTIME_STATE_DIR) / "trading_control.json"


@dataclass(frozen=True)
class ControlState:
    enabled: bool = True
    reason: str = ""
    changed_at_utc: str = ""
    changed_by: str = ""

    def explain(self) -> str:
        v = "BẬT" if self.enabled else "TẮT"
        who = f" bởi {self.changed_by}" if self.changed_by else ""
        when = f" lúc {self.changed_at_utc}" if self.changed_at_utc else ""
        return f"công tắc giao dịch {v}{who}{when}" + (f" — {self.reason}"
                                                       if self.reason else "")


def read(path: Optional[Path] = None) -> ControlState:
    """Trạng thái công tắc.

    Phân biệt HAI tình huống mà `state_store.load_json` gộp làm một (nó nuốt lỗi và
    trả `None` cho cả hai):

        file KHÔNG TỒN TẠI  → BẬT. Chưa ai đụng công tắc, giữ hành vi mặc định.
        file CÓ mà đọc hỏng → TẮT. Người vận hành ĐÃ ghi một ý muốn xuống đó và ta
                              không đọc được nó; tự cho phép giao dịch trong tình
                              huống ấy là bỏ qua đúng thứ công tắc sinh ra để nghe.
    """
    # Giải `CONTROL_PATH` lúc GỌI, không phải lúc định nghĩa hàm. Mặc định tham số
    # được chốt một lần khi module nạp, nên `path = CONTROL_PATH` làm mọi lần đổi
    # `CONTROL_PATH` sau đó bị bỏ qua — test tưởng đang ghi vào thư mục tạm nhưng
    # thật ra ghi đè công tắc THẬT của người vận hành.
    path = Path(path) if path is not None else CONTROL_PATH
    exists = Path(path).exists()
    d = state_store.load_json(path)
    if not d:
        if exists:
            return ControlState(
                enabled=False,
                reason="file công tắc TỒN TẠI nhưng đọc không được — fail-closed")
        return ControlState()
    try:
        return ControlState(
            enabled=bool(d.get("enabled", True)),
            reason=str(d.get("reason", "")),
            changed_at_utc=str(d.get("changed_at_utc", "")),
            changed_by=str(d.get("changed_by", "")))
    except Exception:                                      # pragma: no cover
        # File hỏng → coi như TẮT. Đây là chỗ fail-CLOSED có chủ ý: không đọc được ý
        # muốn của người vận hành thì không được tự cho phép giao dịch.
        return ControlState(enabled=False,
                            reason="file công tắc hỏng — fail-closed, mặc định TẮT")


def entry_allowed(path: Optional[Path] = None) -> bool:
    return read(path).enabled


def set_enabled(enabled: bool, *, reason: str = "", by: str = "operator",
                path: Optional[Path] = None) -> ControlState:
    """Bật/tắt công tắc và ghi xuống đĩa ngay."""
    path = Path(path) if path is not None else CONTROL_PATH
    st = ControlState(enabled=bool(enabled), reason=reason,
                      changed_at_utc=datetime.now(timezone.utc).isoformat(),
                      changed_by=by)
    state_store.save_json_atomic(path, asdict(st))
    return st
