"""
Atomic JSON state persistence — trạng thái rủi ro và vị thế phải SỐNG SÓT qua restart
(spec 02 §2.5: phục hồi trạng thái sau restart, không mở lệnh mới trước khi reconciliation).

Pattern học từ xaubot-ai (smart_risk_manager): temp -> flush -> fsync -> backup -> os.replace.
Mọi file state đều có "schema_version" để nâng cấp cấu trúc không phá file cũ.
"""
import os
import json
import threading
from typing import Any, Dict, Optional

# `log_error` được import ở cấp module, không import lười trong hàm.
# Điều này giúp dễ dàng mock trong các bài test và `utils.logger` 
# chỉ phụ thuộc `shared.paths` nên không gây vòng lặp import.
from src.python.utils.logger import log_error

# Khoá toàn cục đảm bảo an toàn I/O khi đọc/ghi file từ nhiều luồng.
_IO_LOCK = threading.Lock()


def save_json_atomic(path, data: Dict[str, Any]) -> bool:
    """Ghi JSON atomic: không bao giờ để lại file hỏng giữa chừng khi crash.

    Đảm bảo `path` được ép kiểu thành `str` để chấp nhận cả đối tượng `Path`
    (ví dụ từ pytest fixture) tránh lỗi TypeError khi nối chuỗi.
    """
    path = str(path)
    tmp_path = path + ".tmp"
    bak_path = path + ".bak"
    with _IO_LOCK:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1, default=str)
                f.flush()
                os.fsync(f.fileno())
            if os.path.isfile(path):
                try:
                    os.replace(path, bak_path)
                except OSError:
                    pass
            os.replace(tmp_path, path)
            return True
        except Exception:
            return False


def load_json(path) -> Optional[Dict[str, Any]]:
    """Đọc JSON; nếu file chính hỏng thì fallback sang bản .bak."""
    path = str(path)
    with _IO_LOCK:
        for p in (path, path + ".bak"):
            try:
                if os.path.isfile(p):
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
            except Exception:
                continue
    return None


# ═══════════════════════════════════════════════════════════════════════════
# STATE VỊ THẾ CỦA CHIẾN LƯỢC
# ═══════════════════════════════════════════════════════════════════════════
# Module này đóng vai trò SSOT cho việc đọc/ghi JSON an toàn.
# Định dạng trạng thái mặc định: `{"done": [], "pos": {}}`.
#
# VÌ SAO THÔNG ĐIỆP LỖI PHẢI NÓI RÕ HẬU QUẢ:
# ----------------------------------------------------------
# State rỗng KHÔNG phải "mất một file cấu hình". Nó là **mất dấu mọi vị thế đang
# mở**: `_manage()` không còn ticket nào để dời BE, trail, hay chốt sổ. Vị thế
# vẫn chạy trên broker với mỗi SL/TP của broker bảo vệ. `_adopt_orphans()` nhận
# nuôi lại được, nhưng mất `entry_time`/`bars_held`/`peak` — tức mất luôn điều
# kiện thoát theo thời gian.
#
# Tham số `tag` giữ TÊN CHIẾN LƯỢC trong log để dễ dàng định vị lỗi thuộc 
# chiến lược nào khi trạng thái bị hỏng.

# Trạng thái mặc định nếu không đọc được từ file.
_DEFAULT_STATE = {"done": [], "pos": {}}


def load_strategy_state(state_file, tag: str) -> dict:
    """Đọc state vị thế. Luôn trả dict có `done` và `pos`.

    Rơi về mặc định khi không đọc được — nhưng KHÔNG im lặng: nếu file tồn tại
    mà đọc hỏng (kể cả bản `.bak`) thì ghi log mức lỗi kèm hậu quả.
    """
    from pathlib import Path

    p = Path(state_file)
    data = load_json(str(p))
    if isinstance(data, dict) and data:
        data.setdefault("done", [])
        data.setdefault("pos", {})
        return data
    if p.exists():
        log_error(f"❌ [{tag}] state {p.name} TỒN TẠI nhưng đọc không được (cả "
                  f"bản .bak) — khởi tạo rỗng. Vị thế đang mở sẽ phải nhận nuôi "
                  f"lại và MẤT bars_held/entry_time.")
    return {k: (list(v) if isinstance(v, list) else dict(v))
            for k, v in _DEFAULT_STATE.items()}


def save_strategy_state(state_file, state: dict, tag: str) -> bool:
    """Ghi state vị thế nguyên tử (fsync + bản `.bak` + khoá I/O).

    Trả `False` khi ghi hỏng, và luôn log — mất đường ghi này nghĩa là lần khởi
    động sau sẽ không biết gì về vị thế vừa mở.
    """
    from pathlib import Path

    p = Path(state_file)
    if save_json_atomic(str(p), state):
        return True
    log_error(f"❌ [{tag}] KHÔNG ghi được state {p.name} — vị thế đang mở có thể "
              f"mất dấu sau khi khởi động lại.")
    return False
