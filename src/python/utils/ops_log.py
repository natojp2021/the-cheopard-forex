# -*- coding: utf-8 -*-
"""ops_log.py — SỔ CÓ CẤU TRÚC (JSONL) cho mọi thứ console không in.

VÌ SAO MODULE NÀY TỒN TẠI
==========================
Chuyển từ giao diện đồ hoạ sang console đặt ra một câu hỏi mà bản GUI không phải trả
lời: **dữ liệu chi tiết đi đâu?**

Giao diện có chỗ cho trạng thái — 27 hàng ma trận, thẻ tài khoản, bảng vị thế — vì
nó VẼ LẠI cùng một vùng màn hình. Console thì không: mọi thứ in ra là một dòng cộng
thêm vĩnh viễn. Nên nếu bê nguyên nội dung giao diện sang console, sản phẩm thu được
không phải một console nhẹ hơn mà là một giao diện tệ hơn — vẫn nhiều dữ liệu như
cũ, nhưng mất khả năng ghi đè, cộng thêm việc nuốt luôn các dòng có ích.

Nhật ký VPS 18/08/2026 là bằng chứng sống của hướng sai đó: 590 dòng cổng spread
trong 49 phút, cộng 28 dòng bảng spread mỗi 30 phút (1.344 dòng/ngày). Không ai đọc
được gì, mà số liệu thì vẫn không truy vấn được vì nó nằm trong văn bản tự do.

PHÂN CÔNG DỨT KHOÁT
====================
    console   SỰ KIỆN + ĐỔI TRẠNG THÁI + CẢNH BÁO   ← người đọc, vài giây
    JSONL     TOÀN BỘ SỐ ĐO, mọi trường, mọi lần    ← máy đọc, về sau

Một dòng JSONL không bao giờ cạnh tranh chỗ với dòng khác, nên ở đây KHÔNG khử lặp
và KHÔNG tiết chế: bảng spread 27 công cụ mỗi 30 phút là thứ dựng nên phân phối chi
phí thật của 21 cặp chéo — giả định lớn nhất còn lại của cả hệ. Cắt nó ở console là
đúng; cắt nó ở đây là phá mất phép đo.

VÌ SAO JSONL CHỨ KHÔNG PHẢI CSV HAY MỘT BẢNG
=============================================
Mỗi dòng độc lập, nên tiến trình bị kill giữa lúc ghi chỉ làm hỏng dòng cuối chứ
không hỏng cả tệp — quan trọng với một hệ chạy trên VPS bị watchdog kill. Và các
nhóm sự kiện có tập trường KHÁC NHAU (một lệnh khớp không cùng trường với một lượt
đo spread); JSONL cho phép điều đó mà không cần lược đồ chung giả tạo.

BẤT BIẾN AN TOÀN: hàm `emit()` KHÔNG BAO GIỜ được ném lỗi ra ngoài. Nó là tầng quan
sát; một lỗi ghi đĩa (đầy ổ, khoá tệp, quyền) không được phép làm chết vòng lặp giao
dịch. Lưu ý đây là ngoại lệ CÓ CHỦ Ý với quy tắc fail-closed của dự án: quy tắc đó áp
cho các lớp AN TOÀN (đọc vị thế, guard, đóng lệnh), nơi "không đo được" phải thành
"không vào lệnh". Tầng quan sát thì ngược lại — chặn giao dịch vì không ghi được log
là biến một sự cố ổ đĩa thành một sự cố giao dịch.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.python.shared.paths import LOG_DIR

# Các nhóm sổ. Chia theo CÂU HỎI người ta sẽ đặt về sau, không theo module sinh ra
# dòng log — vì khi truy vết một lệnh lỗ, người ta hỏi "hôm đó rủi ro thế nào", chứ
# không hỏi "dòng này do module nào ghi".
CATEGORIES = ("system", "market", "strategy", "trading", "ai", "risk", "daily")

_lock = threading.Lock()
_root: Optional[Path] = None      # ghi đè được trong test, xem `set_root()`


def set_root(path) -> None:
    """Đổi thư mục gốc của sổ. CHỈ dành cho test.

    Có hàm này thay vì để test tự ghi vào `logs/` thật là vì một lượt test đầy đủ
    sinh ra hàng nghìn dòng, và chúng sẽ trộn vào sổ vận hành THẬT — tức làm bẩn
    đúng nguồn dữ liệu mà sổ này sinh ra để giữ sạch.
    """
    global _root
    _root = Path(path) if path is not None else None


def log_root() -> Path:
    """Thư mục gốc của sổ. Báo cáo khởi động in đường dẫn này để người vận hành biết
    tìm chi tiết ở đâu khi console chỉ cho họ một dòng tóm tắt."""
    return Path(_root) if _root is not None else Path(LOG_DIR)


def _dir_for(category: str) -> Path:
    base = _root if _root is not None else LOG_DIR
    return Path(base) / category


def emit(category: str, event: str, **fields: Any) -> None:
    """Ghi MỘT dòng JSON vào `logs/<category>/<YYYY-MM-DD>.jsonl`.

    `category` ngoài `CATEGORIES` vẫn được ghi (vào đúng tên đó) chứ không bị từ
    chối: chặn ở đây nghĩa là một nhóm sự kiện mới sẽ MẤT dữ liệu cho tới khi ai đó
    sửa danh sách, và mất dữ liệu quan sát là cái giá cao hơn một thư mục lạ.
    `CATEGORIES` là tài liệu về ý định, không phải cổng kiểm duyệt.
    """
    try:
        row: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "event": event,
        }
        row.update(fields)
        folder = _dir_for(category)
        path = folder / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        line = json.dumps(row, ensure_ascii=False, default=str)
        with _lock:
            folder.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception:
        # Xem BẤT BIẾN AN TOÀN ở docstring đầu file. Cố ý im lặng.
        pass


def read_today(category: str) -> list:
    """Đọc lại sổ hôm nay của một nhóm. Dùng cho báo cáo tắt máy và cho test.

    Dòng hỏng (tiến trình bị kill giữa lúc ghi) bị BỎ QUA thay vì làm hỏng cả lượt
    đọc — đúng lý do chọn JSONL ngay từ đầu.
    """
    path = _dir_for(category) / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    out = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except FileNotFoundError:
        return []
    except Exception:
        return out
    return out
