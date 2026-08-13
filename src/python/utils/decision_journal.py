"""
Decision Journal — nhật ký quyết định machine-readable (JSONL) theo spec 02 §1.8:
"Mỗi quyết định Trade, Skip, Block hoặc Modify cần có lý do rõ ràng".

- Mỗi dòng 1 JSON: ts_utc, ts_local, kind (TRADE/SKIP/BLOCK/MODIFY/EXIT/RISK), reason, chi tiết.
- Đồng thời đếm rejection theo reason (pattern "rejection-reason accounting" học từ
  tradingbot/risk_supervisor) để báo cáo "hôm nay không vào lệnh vì X ×N" trong email daily.
"""
import os
import re
import json
import time
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Đọc SSOT đường dẫn (thuần stdlib, không side-effect) thay vì lấy từ core.config
from src.python.shared.paths import LOG_DIR as _LOG_DIR

JOURNAL_DIR = str(_LOG_DIR)
_LOCK = threading.Lock()

# Bộ đếm lý do bị chặn trong ngày (reset khi đổi ngày UTC)
_rejection_counters: Dict[str, int] = {}
_counter_day: str = ""

# ---------------------------------------------------------- GOM + GIÃN NHỊP
# Giãn nhịp (Throttle) log file để chống phình to ổ đĩa, 
# nhưng vẫn đảm bảo tổng bộ đếm không bị mất.
_NUMBER_IN_REASON = re.compile(r"[-+]?\d[\d.,]*%?")
_THROTTLE_S = 300.0        # mỗi nhóm ghi tối đa 1 dòng / 5 phút
# Ghi khi chạm ngưỡng đếm, tránh rủi ro sập tiến trình làm mất sự kiện.
_COUNT_THRESHOLD = 500
_last_flush_ts: Dict[str, float] = {}
_pending: Dict[str, int] = {}


def normalise_reason(reason) -> str:
    """Khoá nhóm của một lý do — thay mọi số biến thiên bằng `N`.

    Dùng chung với `email_reporter` (nó đọc lại file này). Đặt ở đây vì `utils/`
    là tầng thấp nhất: tầng thông báo import xuống được, chiều ngược lại thì
    không — nếu để bên kia, hai bên sẽ có hai định nghĩa "cùng một lý do".
    """
    return _NUMBER_IN_REASON.sub("N", str(reason or "khac").strip())[:90]


def _journal_path() -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(JOURNAL_DIR, f"decisions_{day}.jsonl")


def record(kind: str, reason: str, **fields: Any) -> None:
    """Ghi 1 quyết định. kind: TRADE | SKIP | BLOCK | MODIFY | EXIT | RISK."""
    global _counter_day
    now_utc = datetime.now(timezone.utc)
    entry = {
        "ts_utc": now_utc.isoformat(timespec="seconds"),
        "ts_local": datetime.now().isoformat(timespec="seconds"),
        "kind": kind,
        "reason": reason,
    }
    entry.update({k: v for k, v in fields.items() if v is not None})
    line = json.dumps(entry, ensure_ascii=False, default=str)

    with _LOCK:
        day = now_utc.strftime("%Y-%m-%d")
        if day != _counter_day:
            _rejection_counters.clear()
            _last_flush_ts.clear()
            _pending.clear()
            _counter_day = day

        if kind in ("SKIP", "BLOCK"):
            _rejection_counters[reason] = _rejection_counters.get(reason, 0) + 1
            # Giãn nhịp theo nhóm lý do (lần đầu luôn ghi).
            key = normalise_reason(reason)
            now_ts = time.monotonic()
            prev = _last_flush_ts.get(key)
            _pending[key] = waited = _pending.get(key, 0) + 1
            if (prev is not None and (now_ts - prev) < _THROTTLE_S
                    and waited < _COUNT_THRESHOLD):
                return                       # gộp vào lần ghi kế tiếp
            entry["count"] = _pending.pop(key, 1)
            _last_flush_ts[key] = now_ts
            line = json.dumps(entry, ensure_ascii=False, default=str)

        try:
            os.makedirs(JOURNAL_DIR, exist_ok=True)
            with open(_journal_path(), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass  # journal không được phép làm sập luồng giao dịch


def rejection_summary() -> Dict[str, int]:
    """Snapshot bộ đếm lý do chặn hôm nay (cho email daily / GUI)."""
    with _LOCK:
        return dict(sorted(_rejection_counters.items(), key=lambda kv: -kv[1]))


# ============================================================================
# TIER 1.5 v3.0: EXIT REASON AGGREGATION
# ============================================================================
# Chuẩn hoá tên exit_layer (khóa cho analytics / QA reports):
KNOWN_EXIT_LAYERS = {
    "BE_TP1",           # BE khi TP1 sub-order đóng (handle_suborder_closed)
    "BE_R",             # BE tại +Xr (manage_open_positions)
    "TRAIL_ATR",        # Trailing SL theo ATR
    "SCALED_TP_T1",     # Scaled TP tier 1 (Tier 1.4)
    "SCALED_TP_T2",
    "SCALED_TP_T3",
    "SCALED_TP_T4",
    "RUNNER_LOCK_TP1",  # Runner được khóa tại TP1 (khi TP2 đóng)
    "KALMAN_ACCEL",     # Kalman PnL acceleration collapse
    "PEAK_GIVEBACK",    # Peak-profit protection (%-giveback)
    "WEEKEND_TP",       # Weekend guard chốt lãi
    "WEEKEND_CUT",      # Weekend guard cắt lỗ
}


def read_today_events(kinds: Optional[list] = None) -> list:
    """
    Đọc journal file hôm nay và trả về list events (dict).
    kinds: filter theo kind ('EXIT', 'MODIFY', ...). None = tất cả.
    Fail-closed: file không tồn tại/hỏng -> trả list rỗng, log error nếu strict cần.
    """
    events = []
    path = _journal_path()
    if not os.path.exists(path):
        return events
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                    if kinds is None or ev.get("kind") in kinds:
                        events.append(ev)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return events


def exit_layer_summary() -> Dict[str, int]:
    """
    Đếm số lần mỗi exit_layer được kích hoạt trong hôm nay.
    Dùng cho email daily, GUI diagnostics, và QA report.
    """
    counts: Dict[str, int] = {}
    for ev in read_today_events(kinds=["EXIT", "MODIFY"]):
        layer = ev.get("exit_layer")
        if layer:
            counts[layer] = counts.get(layer, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
