"""Trạng thái VÒNG ĐỜI của từng chân, đặt tay và bền vững trên đĩa.

VÌ SAO CẦN — LỖ HỔNG ĐO ĐƯỢC NGÀY 15/08/2026
=============================================
`gui_command_center.get_decision_matrix_rows()` import `allocation_policy` và
`strategy_scoring` trong `try/except`. Cả hai KHÔNG TỒN TẠI, nên `lifecycle` luôn
là `None`, và dòng ngay sau đó:

    enabled = (lifecycle not in ("PAUSED", "RETIRED", "RESEARCH")) if lifecycle else True

cho `enabled = True` cho MỌI chân. Đo được: **27/nhiều chân luôn bật**. Không có đường
nào tạm dừng một chân lúc đang chạy — muốn tắt phải sửa `registry.py` rồi khởi động
lại, tức phải đụng vào SSOT của chiến lược để làm một việc VẬN HÀNH.

Đó là hai loại quyết định khác nhau và không được trộn:

    registry.STRATEGIES   "chân này có tồn tại không, số liệu backtest ra sao"
    module này            "hôm nay chân này CÓ ĐƯỢC vào lệnh không"

Chân bị nghi ngờ (trượt giá bất thường, tương quan đổi, broker đổi spread) phải tắt
được trong vài giây mà không sửa mã nguồn, không khởi động lại, và không mất số liệu
lịch sử của nó.

VÌ SAO KHÔNG CHẤM ĐIỂM TỰ ĐỘNG
===============================
Hệ XAUUSD có `strategy_scoring` chấm điểm và `allocation_policy` tự đổi vòng đời
theo điểm. Hệ này CỐ Ý không port phần đó: nhiều chân đang ở `FORWARD_TEST`, mẫu live
chưa đủ dài để một luật tự động có ý nghĩa thống kê, và một luật tự tắt chân dựa
trên vài chục lệnh chính là cách chọn đỉnh nhiễu. Khi nào có mẫu đủ dài thì thêm
tầng chấm điểm ĐỌC module này, đừng viết đè lên nó.

TRẠNG THÁI KHÔNG PHẢI FAIL-CLOSED
==================================
File hỏng hoặc thiếu → mọi chân coi như `LIVE`. Ngược với `trading_control` (file
hỏng thì TẮT giao dịch) là có chủ ý: `trading_control` là công tắc AN TOÀN, còn đây
là công tắc VẬN HÀNH. Fail-closed ở đây nghĩa là một file JSON hỏng làm câm toàn bộ
danh mục — mất cơ hội mà không giảm được rủi ro nào, vì cổng an toàn thật nằm ở
`entry_gate` và `ftmo_guard`.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Dict, Optional

from src.python.shared.paths import LOG_DIR
from src.python.utils.logger import log

# Tập trạng thái ĐÓNG. Chuỗi lạ bị từ chối ngay ở `set_manual_state` chứ không im
# lặng lưu: một trạng thái gõ sai sẽ không khớp bộ lọc nào và chân đó lại chạy tiếp
# trong khi người vận hành tin rằng đã tắt.
LIVE = "LIVE"              # được vào lệnh bình thường
PAUSED = "PAUSED"          # tạm dừng, giữ vị thế đang mở
RETIRED = "RETIRED"        # loại hẳn khỏi danh mục
RESEARCH = "RESEARCH"      # chỉ theo dõi, không vào lệnh
STATES = (LIVE, PAUSED, RETIRED, RESEARCH)

# Trạng thái CHẶN vào lệnh mới. `gui_command_center` và `portfolio` cùng đọc bộ này
# — hai bản sao là hai chỗ trôi khỏi nhau.
BLOCKING = frozenset({PAUSED, RETIRED, RESEARCH})

STATE_PATH = LOG_DIR / "live" / "strategy_lifecycle.json"

_LOCK = threading.Lock()


def _read() -> Dict[str, dict]:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write(data: Dict[str, dict]) -> None:
    import os

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(STATE_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


def get_manual_state(name: str) -> Optional[str]:
    """Trạng thái đặt tay của chân `name`, hoặc `None` nếu chưa ai đặt.

    `None` khác `LIVE`: `None` nghĩa là "chưa có ai can thiệp" và bên gọi giữ hành
    vi mặc định của mình, còn `LIVE` là một quyết định đã ghi. Phân biệt được hai
    thứ đó là điều kiện để sau này biết chân nào đã được rà soát.
    """
    row = _read().get(str(name))
    if not isinstance(row, dict):
        return None
    state = row.get("state")
    return state if state in STATES else None


def is_blocked(name: str) -> bool:
    """Chân này có đang bị chặn vào lệnh mới không."""
    return get_manual_state(name) in BLOCKING


def set_manual_state(name: str, state: str, *, reason: str = "",
                     by: str = "operator") -> str:
    """Đặt trạng thái cho một chân. NỔ nếu `state` không nằm trong tập đóng.

    Ghi kèm `reason`, `by`, dấu thời gian — ba tháng sau nhìn lại, "vì sao chân này
    bị tắt" là câu hỏi duy nhất còn quan trọng, và nó không nằm ở đâu khác.
    """
    state = str(state).upper().strip()
    if state not in STATES:
        raise ValueError(f"trạng thái {state!r} không hợp lệ "
                         f"(chọn: {', '.join(STATES)})")
    with _LOCK:
        data = _read()
        data[str(name)] = {
            "state": state,
            "reason": reason,
            "by": by,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        _write(data)
    log(f"[VÒNG ĐỜI] {name} → {state}"
        + (f" · {reason}" if reason else "") + f" (bởi {by})")
    return state


def clear(name: str) -> bool:
    """Bỏ can thiệp tay, trả chân về hành vi mặc định. True nếu có gì để xoá."""
    with _LOCK:
        data = _read()
        if str(name) not in data:
            return False
        data.pop(str(name))
        _write(data)
    log(f"[VÒNG ĐỜI] {name} → bỏ can thiệp tay")
    return True


def all_states() -> Dict[str, dict]:
    """Toàn bộ bản ghi, cho giao diện và báo cáo."""
    return _read()


def blocked_names() -> frozenset:
    """Tên các chân đang bị chặn — dùng cho `portfolio.live_targets`."""
    return frozenset(n for n, row in _read().items()
                     if isinstance(row, dict) and row.get("state") in BLOCKING)
