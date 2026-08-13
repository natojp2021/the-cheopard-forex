# -*- coding: utf-8 -*-
"""ftmo_request_budget.py — NGÂN SÁCH REQUEST MỖI NGÀY (Hyperactivity Guard).

TÀI LIỆU MỎ NEO: `docs/ftmo/ftmo-risk-and-reward.md` §II.2 mục 1
=================================================================
    "Chống Spam Request (Hyperactivity Limit)
     Quy định FTMO: Giới hạn 2,000 requests/ngày (mở, sửa, xóa lệnh, modify
     SL/TP)."

Và §II.1 xếp "Hyperactive Order Modification" vào nhóm **CẤM**, cùng hạng với
Martingale và Latency Arbitrage.

TRẠNG THÁI TRƯỚC 07/08: KHÔNG CÓ GÌ
=====================================
Rà toàn bộ `src/` ngày 07/08: không module nào đếm số request gửi tới broker.
`order_send_api()` gửi bao nhiêu lệnh cũng được, và mỗi lần thử lại (tối đa 3
lần/lệnh) cũng là một request tính vào hạn mức mà không ai biết.

VÌ SAO NGUY HIỂM DÙ HỆ THỐNG "CHỈ RA VÀI LỆNH/THÁNG"
======================================================
Tần suất VÀO LỆNH thấp không có nghĩa số REQUEST thấp. Ba nguồn phình:

  1. **Dời SL.** 12 chiến lược LIVE, mỗi chu kỳ 5 phút = 288 chu kỳ/ngày. Chỉ
     cần một lỗi khiến trailing dời SL mỗi chu kỳ (vd ngưỡng dời nhỏ hơn nhiễu
     giá) là 288 × số vị thế request/ngày từ MỘT chiến lược.
  2. **Thử lại.** Mỗi `order_send` hỏng thử lại tới 3 lần. Log 03/08 ghi 90 lần
     IPC hỏng trong một ngày.
  3. **Đối chiếu khởi động.** Mỗi lần bot restart, `reconciliation` khôi phục
     SL/TP cho mọi vị thế. Một vòng lặp khởi động lại (watchdog) nhân số đó lên.

Không cái nào trong ba nguồn ấy làm tăng số LỆNH, nên chúng vô hình với mọi
thước đo hiện có của hệ thống.

THIẾT KẾ: ĐẾM THEO NGÀY GIAO DỊCH FTMO, BỀN QUA RESTART
=========================================================
  * Ngày reset theo `ftmo.trading_day()` (giờ Praha), KHÔNG theo UTC — cùng một
    lỗi múi giờ đã ghi ở "điểm dễ sai #1" trong `ftmo.py`.
  * Bộ đếm ghi xuống đĩa: bot restart giữa ngày mà đếm lại từ 0 thì hạn mức
    không còn ý nghĩa, và restart lặp chính là một trong ba nguồn phình.
  * Lệnh BẢO VỆ (đóng vị thế, dời SL để giảm rủi ro) KHÔNG BAO GIỜ bị chặn.
    Chặn một lệnh đóng vì "hết ngân sách request" là biến một quy tắc vệ sinh
    thành một cách mất tài khoản — đúng thứ tự ưu tiên đã chốt trong `ftmo.py`:
    Account Survival đứng trên FTMO Compliance.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from src.python.utils.logger import log, log_error

# Hạn mức chính thức của FTMO.
DAILY_REQUEST_LIMIT = 2000

# Ngưỡng nội bộ, tính theo TỶ LỆ hạn mức. Luôn cách xa giới hạn thật — cùng
# triết lý với các ngưỡng drawdown: hạn mức không phải chỉ tiêu để tiêu hết.
WARN_RATIO = 0.50      # 1.000 request: ghi log cảnh báo
THROTTLE_RATIO = 0.70  # 1.400 request: chặn lệnh VÀO mới, vẫn cho quản lý lệnh
BLOCK_RATIO = 0.85     # 1.700 request: chỉ còn lệnh BẢO VỆ được đi qua

# Phân loại request. `PROTECTIVE` là nhóm DUY NHẤT không bao giờ bị chặn.
KIND_ENTRY = "ENTRY"            # mở vị thế mới
KIND_MANAGE = "MANAGE"          # dời SL/TP không giảm rủi ro (vd nới TP)
KIND_PROTECTIVE = "PROTECTIVE"  # đóng vị thế, dời SL về phía giảm lỗ
_ALL_KINDS = (KIND_ENTRY, KIND_MANAGE, KIND_PROTECTIVE)

# Khóa bảo vệ đồng bộ hóa (thread-safe) cho bộ đếm.
_lock = threading.RLock()
# Đường dẫn lưu trữ trạng thái bộ đếm.
_STATE_FILE: Optional[Path] = None
# Cờ đánh dấu trạng thái ghi file thất bại để tránh log lỗi liên tục.
_write_failed = False


def _state_file() -> Path:
    """Khởi tạo và trả về đường dẫn file lưu trạng thái bộ đếm request."""
    global _STATE_FILE
    if _STATE_FILE is None:
        from src.python.core.config import LIVE_DIR
        _STATE_FILE = Path(LIVE_DIR) / "ftmo_request_budget.json"
    return _STATE_FILE


def _today() -> str:
    """Ngày giao dịch theo giờ Praha — SSOT là `ftmo.trading_day()`."""
    from src.python.core.infra import ftmo
    return ftmo.trading_day().isoformat()


def _default_state() -> Dict[str, Any]:
    """Trả về trạng thái mặc định của bộ đếm (chưa ghi nhận request nào)."""
    return {"day": None, "total": 0,
            "by_kind": {k: 0 for k in _ALL_KINDS},
            # Số lần đã TỪ CHỐI vì hết ngân sách — nếu con số này khác 0 thì có
            # một nguồn phình request cần tìm, không phải chuyện "hôm nay bận".
            "denied": 0}


def _read() -> Dict[str, Any]:
    """Đọc trạng thái bộ đếm từ file. Nếu file hỏng, sẽ đếm lại từ 0 có chủ đích."""
    base = _default_state()
    try:
        from src.python.core.infra.state_store import load_json
        st = load_json(str(_state_file()))
        if isinstance(st, dict):
            base.update(st)
            # `by_kind` có thể thiếu khoá khi nâng cấp từ bản cũ.
            merged = {k: 0 for k in _ALL_KINDS}
            merged.update(base.get("by_kind") or {})
            base["by_kind"] = merged
    except Exception as e:
        # ĐỌC HỎNG -> ĐẾM LẠI TỪ 0, CÓ CHỦ Ý.
        # ------------------------------------------------------------------
        # Ngược với `ftmo._read_state()` (fail-CLOSED khi đọc hỏng). Lý do khác
        # nhau về BẢN CHẤT: ở đó, không đọc được nghĩa là không biết còn cách
        # giới hạn mất-tài-khoản bao xa. Ở đây, không đọc được chỉ khiến bộ đếm
        # vệ sinh bị reset — mà chặn sạch giao dịch vì một file đếm hỏng là cái
        # giá lớn hơn nhiều so với rủi ro nó phòng.
        #
        # Vẫn phải LOG: nếu dòng này lặp lại thì bộ đếm đang vô hiệu.
        log_error(f"⚠️ [REQUEST BUDGET] không đọc được bộ đếm ({e}) — đếm lại từ "
                  f"0 cho hôm nay. Hạn mức {DAILY_REQUEST_LIMIT}/ngày tạm thời "
                  f"không còn chính xác.")
    return base


def _write(st: Dict[str, Any]) -> None:
    """Ghi trạng thái bộ đếm xuống file (nguyên tử hóa)."""
    global _write_failed
    try:
        from src.python.core.infra.state_store import save_json_atomic
        ok = bool(save_json_atomic(str(_state_file()), st))
    except Exception as e:
        ok = False
        log_error(f"❌ [REQUEST BUDGET] ngoại lệ khi ghi bộ đếm: {e}")
    if not ok and not _write_failed:
        log_error("❌ [REQUEST BUDGET] KHÔNG ghi được bộ đếm — sau khi khởi động "
                  "lại, số request hôm nay sẽ bị đếm lại từ 0.")
    _write_failed = not ok


def _roll_day(st: Dict[str, Any]) -> Dict[str, Any]:
    """Sang ngày giao dịch mới -> reset bộ đếm. Idempotent."""
    today = _today()
    if st.get("day") != today:
        if st.get("total"):
            log(f"📊 [REQUEST BUDGET] Ngày mới {today} — hôm qua dùng "
                f"{st.get('total')}/{DAILY_REQUEST_LIMIT} request "
                f"({st.get('by_kind')}). Bộ đếm reset.")
        st.update(_default_state())
        st["day"] = today
    return st


@dataclass(frozen=True)
class BudgetDecision:
    """Kết quả hỏi "có được gửi request này không"."""

    allowed: bool
    used: int
    limit: int
    reason: str = ""

    @property
    def remaining(self) -> int:
        """Số lượng request còn lại có thể sử dụng."""
        return max(0, self.limit - self.used)

    @property
    def used_ratio(self) -> float:
        """Tỷ lệ số request đã dùng trên tổng hạn mức."""
        return (self.used / self.limit) if self.limit > 0 else 0.0


def can_send(kind: str = KIND_ENTRY) -> BudgetDecision:
    """Có được gửi một request loại `kind` không? KHÔNG tăng bộ đếm.

    Tách khỏi `record()` có chủ đích: giữa lúc hỏi và lúc gửi thật còn nhiều
    cổng khác có thể chặn, và đếm một request chưa từng được gửi sẽ làm bộ đếm
    trôi khỏi số thật của FTMO theo hướng bi quan — rồi tự chặn mình sớm.
    """
    with _lock:
        st = _roll_day(_read())
        used = int(st.get("total") or 0)

    if kind == KIND_PROTECTIVE:
        # KHÔNG BAO GIỜ CHẶN. Xem docstring đầu file.
        return BudgetDecision(True, used, DAILY_REQUEST_LIMIT)

    ratio = used / DAILY_REQUEST_LIMIT if DAILY_REQUEST_LIMIT else 0.0
    if ratio >= BLOCK_RATIO:
        return BudgetDecision(
            False, used, DAILY_REQUEST_LIMIT,
            f"đã dùng {used}/{DAILY_REQUEST_LIMIT} request hôm nay "
            f"({ratio:.0%} >= {BLOCK_RATIO:.0%}) — chỉ còn lệnh BẢO VỆ được gửi. "
            f"FTMO xếp 'Hyperactive Order Modification' vào nhóm CẤM.")
    if kind == KIND_ENTRY and ratio >= THROTTLE_RATIO:
        return BudgetDecision(
            False, used, DAILY_REQUEST_LIMIT,
            f"đã dùng {used}/{DAILY_REQUEST_LIMIT} request hôm nay "
            f"({ratio:.0%} >= {THROTTLE_RATIO:.0%}) — ngừng MỞ lệnh mới, vẫn "
            f"quản lý bình thường các vị thế đang có.")
    return BudgetDecision(True, used, DAILY_REQUEST_LIMIT)


def record(kind: str = KIND_ENTRY, count: int = 1) -> int:
    """Ghi nhận `count` request ĐÃ GỬI. Trả tổng sau khi cộng.

    Gọi SAU khi request thật sự rời khỏi tiến trình — kể cả khi broker từ chối,
    vì FTMO đếm request gửi lên, không đếm request thành công.
    """
    if count <= 0:
        return 0
    with _lock:
        st = _roll_day(_read())
        before = int(st.get("total") or 0)
        st["total"] = before + int(count)
        by_kind = st.get("by_kind") or {}
        by_kind[kind] = int(by_kind.get(kind, 0)) + int(count)
        st["by_kind"] = by_kind
        _write(st)
        after = st["total"]

    # Cảnh báo khi VỪA VƯỢT ngưỡng, không phải mỗi lần gọi — nếu không, mỗi
    # request sau ngưỡng lại sinh một dòng log và ta có một nguồn spam mới.
    for ratio, label in ((BLOCK_RATIO, "CHẶN"), (THROTTLE_RATIO, "SIẾT"),
                        (WARN_RATIO, "CẢNH BÁO")):
        threshold_count = int(DAILY_REQUEST_LIMIT * ratio)
        if before < threshold_count <= after:
            log_error(f"⚠️ [REQUEST BUDGET] {label}: đã dùng {after}/"
                      f"{DAILY_REQUEST_LIMIT} request hôm nay ({after / DAILY_REQUEST_LIMIT:.0%}). "
                      f"Phân rã: {st['by_kind']}. Tần suất vào lệnh của hệ thống "
                      f"rất thấp, nên con số này cao nghĩa là có nguồn phình "
                      f"(dời SL lặp / thử lại / restart vòng lặp) cần tìm.")
            break
    return after


def record_denied() -> None:
    """Đánh dấu một request bị từ chối vì hết ngân sách — để còn truy được."""
    with _lock:
        st = _roll_day(_read())
        st["denied"] = int(st.get("denied") or 0) + 1
        _write(st)


def snapshot() -> Dict[str, Any]:
    """Ảnh chụp bộ đếm hôm nay — cho GUI, email và báo cáo ngày."""
    with _lock:
        st = _roll_day(_read())
        used = int(st.get("total") or 0)
        return {
            "day": st.get("day"),
            "used": used,
            "limit": DAILY_REQUEST_LIMIT,
            "remaining": max(0, DAILY_REQUEST_LIMIT - used),
            "used_ratio": used / DAILY_REQUEST_LIMIT if DAILY_REQUEST_LIMIT else 0.0,
            "by_kind": dict(st.get("by_kind") or {}),
            "denied": int(st.get("denied") or 0),
        }


def reset_for_test(state_file: Optional[Path] = None) -> None:
    """Dùng trong test: trỏ bộ đếm sang file tạm và xoá trạng thái tiến trình."""
    global _STATE_FILE, _write_failed
    with _lock:
        _STATE_FILE = state_file
        _write_failed = False
