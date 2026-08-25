"""trading_control.py — CÔNG TẮC GIAO DỊCH THỦ CÔNG, BỀN VỮNG trên đĩa.

BA TÍNH CHẤT, VÀ CẢ BA ĐỀU BẮT BUỘC
====================================
    BỀN VỮNG    trạng thái nằm trên đĩa, không trong RAM. Khởi động lại tiến trình
                KHÔNG được bật lại giao dịch — người vận hành tắt là tắt.
    FAIL-CLOSED file hỏng, thiếu, không đọc được  ->  TẮT. Không đọc được ý định của
                người vận hành thì không được đoán rằng họ muốn giao dịch.
    CHỈ CHẶN MỞ tắt công tắc KHÔNG khoá đường thoát. Vị thế đang mở vẫn được đóng,
                dừng lỗ vẫn chạy. Một vị thế đang mở mà mất người quản lý là tình
                trạng nguy hiểm hơn việc vào thêm lệnh.
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
