"""
Máy Trạng Thái Đơn Hàng Idempotent & Hộp Thư Ra Giao Dịch (Cấp Độ Sản Xuất Tier 4.2)
==================================================================================
Quản lý 23 trạng thái vòng đời của đơn hàng với các tính năng:
- Băm khóa Idempotency SHA256 vĩnh viễn (độ hỗn loạn hex 64 ký tự đầy đủ).
- Ngữ nghĩa yêu cầu Idempotency nguyên tử (`claim_idempotency_key`, được sử dụng bởi `create_order`).
- Ghi nhật ký hộp thư ra giao dịch (`_append_durable_event` vào durable_event_log.jsonl với sequence_number và trace_id).
- Khôi phục từ hộp thư ra (`rebuild_from_outbox`) để phát lại nhật ký và khôi phục trạng thái sau khi khởi động lại.
- Các bản chụp không thay đổi về Quyết định, Thực thi và Khớp lệnh (Decision, Execution, Fill Snapshots).
- Hợp đồng xác minh bảo vệ (`ProtectionVerificationResult`) để từ chối các chuyển đổi trạng thái không an toàn.
- Giao thức xử lý khẩn cấp với khả năng theo dõi thử lại và tạm dừng toàn hệ thống khi đạt giới hạn.
- Bảo vệ khớp lệnh một phần (`handle_partially_filled`) để đảm bảo số lượng khớp lệnh được xác minh.
- Đồ thị chuyển đổi hợp lệ (`_VALID_TRANSITIONS`) để ngăn chặn các chuyển đổi trạng thái không cho phép.
"""
from __future__ import annotations
import enum
import hashlib
import json
import threading
from collections import deque
from pathlib import Path
import pandas as pd
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, Any, Set

from src.python.core.config import LIVE_DIR
from src.python.utils.logger import log, log_error
from src.python.core.infra.clock import now_utc_ts

EXECUTION_VERSION = "order_sm_v3.5"
RISK_POLICY_VERSION = "portfolio_risk_v3.5"
# Hằng số phiên bản lược đồ chính sách để đảm bảo tính nhất quán giữa DecisionSnapshot và policy_snapshot của đơn hàng.
POLICY_SCHEMA_VERSION = "policy_v4.2"


@dataclass
class ProtectionVerificationResult:
    position_verified: bool
    stop_verified: bool
    broker_stop_price: float
    expected_stop_price: float
    tolerance: float


@dataclass
class DecisionSnapshot:
    signal_id: str
    decision_timestamp: str
    symbol: str
    timeframe: str
    strategy_version: str
    feature_schema_version: str
    feature_values: Dict[str, Any]
    market_snapshot: Dict[str, Any]
    broker_spec_snapshot: Dict[str, Any]
    policy_snapshot: Dict[str, Any] = field(default_factory=lambda: {"policy_schema_version": POLICY_SCHEMA_VERSION})


@dataclass
class ExecutionSnapshot:
    order_id: str
    execution_timestamp: str
    slippage: float


@dataclass
class FillSnapshot:
    order_id: str
    fill_timestamp: str
    fill_price: float
    fill_quantity: float


class OrderState(enum.Enum):
    # Quá trình thuận lợi (9 trạng thái)
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    SUBMITTING = "SUBMITTING"
    BROKER_ACCEPTED = "BROKER_ACCEPTED"
    FILLED = "FILLED"
    POSITION_VERIFIED = "POSITION_VERIFIED"
    PROTECTED = "PROTECTED"
    MANAGED = "MANAGED"
    CLOSED = "CLOSED"

    # Quá trình thất bại & Các trạng thái phục hồi (14 trạng thái)
    REJECTED = "REJECTED"
    VALIDATION_REJECTED = "VALIDATION_REJECTED"
    BROKER_REJECTED = "BROKER_REJECTED"
    SUBMIT_TIMEOUT = "SUBMIT_TIMEOUT"
    UNKNOWN_BROKER_STATE = "UNKNOWN_BROKER_STATE"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    POSITION_VERIFY_FAILED = "POSITION_VERIFY_FAILED"
    PROTECTION_FAILED = "PROTECTION_FAILED"
    EMERGENCY_CLOSING = "EMERGENCY_CLOSING"
    EMERGENCY_CLOSE_RETRY = "EMERGENCY_CLOSE_RETRY"
    EMERGENCY_CLOSE_FAILED = "EMERGENCY_CLOSE_FAILED"
    EMERGENCY_CLOSED = "EMERGENCY_CLOSED"
    CANCELLED = "CANCELLED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


# Bảng xác định các chuyển đổi trạng thái hợp lệ. Các trạng thái kết thúc (không có trong từ điển)
# sẽ không cho phép bất kỳ chuyển đổi nào tiếp theo.
_VALID_TRANSITIONS: Dict[OrderState, Set[OrderState]] = {
    OrderState.CREATED: {OrderState.VALIDATED, OrderState.VALIDATION_REJECTED},
    OrderState.VALIDATED: {OrderState.SUBMITTING, OrderState.CANCELLED},
    OrderState.SUBMITTING: {OrderState.BROKER_ACCEPTED, OrderState.BROKER_REJECTED, OrderState.SUBMIT_TIMEOUT},
    OrderState.SUBMIT_TIMEOUT: {OrderState.UNKNOWN_BROKER_STATE},
    OrderState.UNKNOWN_BROKER_STATE: {OrderState.FILLED, OrderState.CANCELLED, OrderState.RECONCILIATION_REQUIRED},
    OrderState.BROKER_ACCEPTED: {OrderState.FILLED, OrderState.PARTIALLY_FILLED, OrderState.CANCELLED},
    OrderState.FILLED: {OrderState.POSITION_VERIFIED, OrderState.POSITION_VERIFY_FAILED},
    # Cho phép trạng thái PARTIALLY_FILLED chuyển sang CLOSED vì các lệnh khớp một phần 
    # vẫn tiếp tục được theo dõi và có thể đóng bình thường bởi chiến lược quản lý lệnh.
    OrderState.PARTIALLY_FILLED: {OrderState.PROTECTED, OrderState.EMERGENCY_CLOSING,
                                  OrderState.CLOSED},
    OrderState.POSITION_VERIFIED: {OrderState.PROTECTED, OrderState.PROTECTION_FAILED},
    # Cho phép PROTECTION_FAILED khôi phục về PROTECTED khi gắn SL lại thành công hoặc
    # chuyển sang CLOSED khi vị thế được đóng bình thường trên broker.
    OrderState.PROTECTION_FAILED: {OrderState.EMERGENCY_CLOSING, OrderState.PROTECTED, OrderState.CLOSED},
    OrderState.POSITION_VERIFY_FAILED: {OrderState.EMERGENCY_CLOSING, OrderState.RECONCILIATION_REQUIRED},
    OrderState.PROTECTED: {OrderState.MANAGED},
    OrderState.MANAGED: {OrderState.CLOSED, OrderState.EMERGENCY_CLOSING},
    OrderState.EMERGENCY_CLOSING: {OrderState.EMERGENCY_CLOSED, OrderState.EMERGENCY_CLOSE_RETRY, OrderState.EMERGENCY_CLOSE_FAILED},
    OrderState.EMERGENCY_CLOSE_RETRY: {OrderState.EMERGENCY_CLOSING},
    OrderState.EMERGENCY_CLOSE_FAILED: {OrderState.EMERGENCY_CLOSE_RETRY, OrderState.RECONCILIATION_REQUIRED},
}

# Các trạng thái thuận lợi của vòng đời lệnh. Được gộp chung lại để giảm thiểu log,
# cho đến khi lệnh đạt trạng thái MANAGED.
_HAPPY_PATH_STEPS = frozenset({
    OrderState.VALIDATED,
    OrderState.SUBMITTING,
    OrderState.BROKER_ACCEPTED,
    OrderState.FILLED,
    OrderState.POSITION_VERIFIED,
    OrderState.PROTECTED,
})

MAX_EMERGENCY_CLOSE_ATTEMPTS = 5
# Giới hạn bộ nhớ số lượng khóa idempotency được lưu để ngăn lệnh bị xử lý trùng lặp.
MAX_REMEMBERED_CLAIMS = 20_000
# Số lần thử nghiệm tối đa gán lại mức dừng lỗ sau khi bảo vệ thất bại trước khi kích hoạt tạm dừng.
PROTECTION_RETRY_LIMIT = 3


@dataclass
class EmergencyCloseTracking:
    """Theo dõi siêu dữ liệu cho các hoạt động đóng khẩn cấp và giới hạn thử lại."""
    attempt_count: int = 0
    first_failure_at: Optional[pd.Timestamp] = None
    last_attempt_at: Optional[pd.Timestamp] = None
    last_broker_error: str = ""
    next_retry_at: Optional[pd.Timestamp] = None


def _json_safe(obj: Any) -> Any:
    """Chuyển đổi đệ quy các đối tượng không thể dùng json.dumps trực tiếp (OrderState, pd.Timestamp, dataclass)
    thành dạng từ điển an toàn cho JSON để có thể phục hồi lại qua _json_restore()."""
    if isinstance(obj, OrderState):
        return {"__order_state__": obj.value}
    if isinstance(obj, pd.Timestamp):
        return {"__timestamp__": obj.isoformat()}
    if isinstance(obj, EmergencyCloseTracking):
        return {"__emergency_tracking__": {
            "attempt_count": obj.attempt_count,
            "first_failure_at": obj.first_failure_at.isoformat() if obj.first_failure_at is not None else None,
            "last_attempt_at": obj.last_attempt_at.isoformat() if obj.last_attempt_at is not None else None,
            "last_broker_error": obj.last_broker_error,
            "next_retry_at": obj.next_retry_at.isoformat() if obj.next_retry_at is not None else None,
        }}
    if isinstance(obj, ProtectionVerificationResult):
        return {"__protection_verification__": asdict(obj)}
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def _json_restore(obj: Any) -> Any:
    """Phục hồi các đối tượng từ dạng JSON an toàn được tạo bởi _json_safe, dùng khi phát lại hộp thư ra."""
    if isinstance(obj, dict):
        if set(obj.keys()) == {"__order_state__"}:
            return OrderState(obj["__order_state__"])
        if set(obj.keys()) == {"__timestamp__"}:
            return pd.Timestamp(obj["__timestamp__"])
        if set(obj.keys()) == {"__emergency_tracking__"}:
            d = obj["__emergency_tracking__"]
            return EmergencyCloseTracking(
                attempt_count=d.get("attempt_count", 0),
                first_failure_at=pd.Timestamp(d["first_failure_at"]) if d.get("first_failure_at") else None,
                last_attempt_at=pd.Timestamp(d["last_attempt_at"]) if d.get("last_attempt_at") else None,
                last_broker_error=d.get("last_broker_error", ""),
                next_retry_at=pd.Timestamp(d["next_retry_at"]) if d.get("next_retry_at") else None,
            )
        if set(obj.keys()) == {"__protection_verification__"}:
            return ProtectionVerificationResult(**obj["__protection_verification__"])
        return {k: _json_restore(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_restore(v) for v in obj]
    return obj


class OrderStateMachine:
    _lock = threading.Lock()
    # Khóa độc lập cho ghi chép sự kiện hộp thư ra nhằm tránh deadlock với `_lock` chính.
    _outbox_lock = threading.Lock()
    _orders: Dict[str, Dict[str, Any]] = {}
    _decision_snapshots: Dict[str, Any] = {}
    _execution_snapshots: Dict[str, Any] = {}
    _fill_snapshots: Dict[str, Any] = {}
    _claimed_keys: Set[str] = set()
    # Hàng đợi ghi nhớ khóa theo FIFO để kiểm soát kích thước tập khóa idempotency.
    _claim_order: "deque[str]" = deque()
    _sequence_counter: int = 0
    _outbox_file: Optional[Path] = None
    _trading_halted: bool = False
    _halt_file: Optional[Path] = None

    @classmethod
    def _get_outbox_file(cls) -> Path:
        if cls._outbox_file is None:
            from src.python.core.infra.account_controller import AccountController
            cls._outbox_file = AccountController.get_file_path("durable_event_log.jsonl")
            cls._outbox_file.parent.mkdir(parents=True, exist_ok=True)
        return cls._outbox_file

    @classmethod
    def _get_halt_file(cls) -> Path:
        if cls._halt_file is None:
            from src.python.core.infra.account_controller import AccountController
            cls._halt_file = AccountController.get_file_path("trading_halt_state.json")
        return cls._halt_file

    @classmethod
    def _persist_halt_state(cls, halted: bool, reason: str = "") -> None:
        """Lưu trữ trạng thái tạm dừng giao dịch xuống đĩa để đảm bảo lệnh tạm dừng không bị mất 
        khi hệ thống khởi động lại do lỗi."""
        try:
            from src.python.core.infra.state_store import save_json_atomic
            # Xác minh trạng thái lưu để bảo vệ dữ liệu tạm dừng và ghi log nếu lỗi xảy ra.
            if not save_json_atomic(str(cls._get_halt_file()), {
                "halted": bool(halted), "reason": reason,
                "updated_at": now_utc_ts().isoformat(),
            }):
                log_error(
                    f"❌ [STATE_MACHINE] KHÔNG ghi được trading_halt_state.json "
                    f"(halted={halted}) — halt này CHỈ CÒN TRONG RAM và sẽ mất "
                    f"khi process khởi động lại. Kiểm quyền ghi/dung lượng "
                    f"{cls._get_halt_file()} NGAY.")
        except Exception as e:
            log_error(f"❌ [STATE_MACHINE] Không ghi được trading_halt_state.json: {e}")

    @classmethod
    def load_persisted_halt_state(cls) -> bool:
        """Khôi phục trạng thái tạm dừng từ lần chạy trước khi khởi động.
        Áp dụng nguyên tắc đóng an toàn (fail-closed) khi tệp trạng thái bị hỏng hoặc lỗi khi đọc."""
        try:
            from src.python.core.infra.state_store import load_json
            halt_file = cls._get_halt_file()
            data = load_json(str(halt_file))
            if not isinstance(data, dict) and halt_file.exists():
                with cls._lock:
                    cls._trading_halted = True
                log_error(f"🛑 [STATE_MACHINE] {halt_file.name} TỒN TẠI nhưng đọc không được "
                          f"(cả bản .bak) — FAIL-CLOSED: coi như ĐANG HALT, entry mới bị CHẶN. "
                          f"Kiểm tra vị thế trên MT5 rồi `clear_trading_halt(lý do)` để mở lại.")
                return True
            if data and data.get("halted"):
                with cls._lock:
                    cls._trading_halted = True
                log_error(f"🛑 [STATE_MACHINE] Khôi phục TRADING_HALTED từ lượt chạy trước: "
                          f"{data.get('reason', '')} (lúc {data.get('updated_at', '?')}) — "
                          f"entry mới vẫn bị CHẶN cho tới khi `clear_trading_halt()` được gọi thủ công.")
                return True
        except Exception as e:
            # Xử lý đóng an toàn nếu đọc lỗi cờ an toàn.
            with cls._lock:
                cls._trading_halted = True
            log_error(f"❌ [STATE_MACHINE] Không đọc được trading_halt_state.json: {e} "
                      f"— FAIL-CLOSED: chặn entry mới cho tới khi xử lý thủ công.")
            return True
        return False

    @classmethod
    def clear_trading_halt(cls, reason: str) -> bool:
        """Khôi phục giao dịch thủ công sau khi xử lý thành công nguyên nhân gây tạm dừng.
        Bắt buộc cung cấp lý do để lưu vết an toàn."""
        if not (reason or "").strip():
            log_error("❌ [STATE_MACHINE] clear_trading_halt() từ chối — cần lý do (audit trail).")
            return False
        with cls._lock:
            cls._trading_halted = False
        cls._persist_halt_state(False, reason=f"cleared: {reason}")
        log_error(f"✅ [STATE_MACHINE] TRADING_HALTED đã được RESUME thủ công: {reason}")
        return True

    @classmethod
    def _capture_api_context(cls) -> Dict[str, Any]:
        """Thu thập nhanh dữ liệu bối cảnh hệ thống ngoài để lưu trữ quá trình ra quyết định.
        Bỏ qua an toàn khi dữ liệu không khả dụng để không cản trở việc vào lệnh."""
        ctx: Dict[str, Any] = {}
        try:
            from src.python.core.infra.state_store import load_json
            macro_state_file = Path(LIVE_DIR) / "macro_state.json"
            macro_state = load_json(str(macro_state_file))
            if macro_state:
                ctx["macro_sentiment"] = macro_state
        except Exception:
            pass
        try:
            from src.python.core.ai_macro import macro_event_guard
            ctx["macro_event_guard"] = macro_event_guard.check_now()
        except Exception:
            pass
        return ctx

    @classmethod
    def _append_durable_event(cls, event_type: str, aggregate_id: str, payload: Dict[str, Any], trace_id: Optional[str] = None):
        """Hộp thư ra giao dịch: Lưu trữ các sự kiện giao dịch không thay đổi cùng số trình tự xuống đĩa, 
        đảm bảo tính toàn vẹn và nguyên tử của bản ghi."""
        try:
            with cls._outbox_lock:
                cls._sequence_counter += 1
                seq = cls._sequence_counter
                record = {
                    # Sử dụng đồng hồ chuẩn để đảm bảo tính nhất quán về thời gian của sự kiện.
                    "event_id": f"evt_{seq}_{now_utc_ts().strftime('%Y%m%d%H%M%S%f')}",
                    "aggregate_id": aggregate_id,
                    "sequence_number": seq,
                    "created_at": now_utc_ts().isoformat(),
                    "event_type": event_type,
                    "trace_id": trace_id,
                    "payload": _json_safe(payload),
                }
                with open(cls._get_outbox_file(), "a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
        except Exception as e:
            log_error(f"❌ [STATE_MACHINE] Durable Event Outbox write failed: {e}")

    @classmethod
    def rebuild_from_outbox(cls) -> int:
        """Phục hồi hệ thống bằng cách phát lại nhật ký hộp thư ra để nạp lại trạng thái nội bộ 
        (`_orders`, `_claimed_keys`, `_sequence_counter`) khi hệ thống khởi động."""
        outbox = cls._get_outbox_file()
        replayed = 0
        corrupted = 0
        with cls._lock:
            cls._orders.clear()
            cls._claimed_keys.clear()
            cls._claim_order.clear()
            cls._decision_snapshots.clear()
            cls._sequence_counter = 0
            if not outbox.exists():
                return 0
            try:
                with open(outbox, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except Exception:
                            # Báo cáo các sự kiện bị lỗi để người vận hành kiểm tra sự thiếu toàn vẹn.
                            corrupted += 1
                            continue
                        cls._sequence_counter = max(cls._sequence_counter, int(record.get("sequence_number", 0)))
                        event_type = record.get("event_type")
                        aggregate_id = record.get("aggregate_id")
                        payload = _json_restore(record.get("payload", {}))
                        if event_type == "ORDER_CREATED" and aggregate_id:
                            cls._orders[aggregate_id] = payload
                            cls._remember_claim(aggregate_id)
                            # Khôi phục bản chụp quyết định (decision_snapshot) từ dữ liệu trực tiếp trong payload.
                            _ds = payload.get("decision_snapshot")
                            if _ds:
                                cls._decision_snapshots[aggregate_id] = _ds
                            replayed += 1
                        elif event_type == "OrderStateTransitioned" and aggregate_id in cls._orders:
                            try:
                                cls._orders[aggregate_id]["state"] = OrderState(payload.get("new_state"))
                            except Exception:
                                pass
                            # Đảm bảo siêu dữ liệu (metadata) được khôi phục và hợp nhất vào thông tin đơn hàng hiện tại.
                            _meta = payload.get("metadata")
                            if _meta:
                                cls._orders[aggregate_id].setdefault("close_metadata", {}).update(_meta)
                        elif event_type == "OrderCloseMetadataAnnotated" and aggregate_id in cls._orders:
                            # Hợp nhất thêm siêu dữ liệu cho đơn hàng khi đã hoàn thành mà không thay đổi trạng thái.
                            _ameta = payload.get("metadata")
                            if _ameta:
                                cls._orders[aggregate_id].setdefault("close_metadata", {}).update(_ameta)
                        elif event_type == "PartiallyFilledProtected" and aggregate_id in cls._orders:
                            order = cls._orders[aggregate_id]
                            order["state"] = OrderState.PARTIALLY_FILLED
                            order["filled_quantity"] = payload.get("filled_quantity")
                            order["sl_price"] = payload.get("sl_price")
                        elif event_type == "OrderClaimReleased" and aggregate_id:
                            # Đồng bộ hóa việc phát hành khóa khỏi bộ nhớ đối với các lệnh bị loại bỏ.
                            cls._orders.pop(aggregate_id, None)
                            cls._decision_snapshots.pop(aggregate_id, None)
                            cls._claimed_keys.discard(aggregate_id)
                            if replayed > 0:
                                replayed -= 1
            except Exception as e:
                log_error(f"❌ [STATE_MACHINE] Rebuild từ outbox lỗi (bắt đầu từ trạng thái rỗng): {e}")
        if corrupted:
            log_error(f"❌ [STATE_MACHINE] {corrupted} dòng trong durable_event_log.jsonl HỎNG, "
                      f"không đọc được — sổ vòng đời lệnh vừa phục hồi KHÔNG ĐẦY ĐỦ. Nếu dòng "
                      f"hỏng là ORDER_CREATED thì khoá chống trùng của tín hiệu đó đã mất và hệ "
                      f"thống có thể mở lệnh thứ hai cho cùng một tín hiệu. Kiểm tra file NGAY.")
        # Quá trình chi tiết về khôi phục đơn hàng được xử lý tập trung tại `engine.py`.
        return replayed

    @classmethod
    def generate_idempotency_key(cls, strategy_id: str, strategy_version: str, symbol: str,
                                 timeframe: str, signal_bar_timestamp: Any, direction: str,
                                 setup_id: str = "main", entry_sequence: int = 1) -> str:
        """Tạo hàm băm khóa idempotency ổn định và xác định duy nhất cho các tín hiệu giao dịch."""
        raw_key = f"{strategy_id}|{strategy_version}|{symbol}|{timeframe}|{signal_bar_timestamp}|{direction}|{setup_id}|{entry_sequence}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @classmethod
    def _remember_claim(cls, idempotency_key: str) -> None:
        """Ghi nhớ khóa an toàn và quản lý giới hạn để không gây tràn bộ nhớ, gọi nội bộ khi có `_lock`."""
        if idempotency_key in cls._claimed_keys:
            return
        cls._claimed_keys.add(idempotency_key)
        cls._claim_order.append(idempotency_key)
        while len(cls._claim_order) > MAX_REMEMBERED_CLAIMS:
            _old = cls._claim_order.popleft()
            # Bỏ khóa khi không còn tồn tại bản ghi trong dữ liệu `_orders` hiện tại.
            if _old not in cls._orders:
                cls._claimed_keys.discard(_old)
            else:
                cls._claim_order.append(_old)
                break

    @classmethod
    def claim_idempotency_key(cls, idempotency_key: str) -> bool:
        """Xử lý nguyên tử và chống trùng lặp khóa idempotency trong `create_order`."""
        with cls._lock:
            if idempotency_key in cls._orders or idempotency_key in cls._claimed_keys:
                return False
            cls._orders[idempotency_key] = {"state": "CLAIMED"}
            cls._remember_claim(idempotency_key)
            return True

    @classmethod
    def create_order(cls, strategy: str, symbol: str, bar_timestamp: Any, direction: str, lot: float,
                     decision_snapshot: Optional[Dict[str, Any]] = None, trace_id: Optional[str] = None,
                     setup_id: str = "main", timeframe: str = "M5") -> Optional[str]:
        """Tạo đơn hàng mới sau khi kiểm tra chống trùng lặp và lưu trữ chi tiết."""
        key = cls.generate_idempotency_key(strategy, "1.0", symbol, timeframe or "M5",
                                           bar_timestamp, direction, setup_id=setup_id or "main")
        if not cls.claim_idempotency_key(key):
            log(f"🔑 [STATE_MACHINE] Signal with key {key[:16]} already exists (Duplicate blocked).")
            return None

        # Bản chụp quyết định sẽ được lưu vào khối nội dung sự kiện `ORDER_CREATED` để bảo toàn lịch sử.
        full_snapshot: Dict[str, Any] = dict(decision_snapshot) if decision_snapshot else {}
        full_snapshot["api_context"] = cls._capture_api_context()
        resolved_trace_id = trace_id or f"trace_{key[:16]}"

        with cls._lock:
            policy_snap = {
                "policy_schema_version": POLICY_SCHEMA_VERSION,
                "break_even_r": 1.0,
                "trail_start_r": 1.5,
                "trail_atr_mult": 2.0,
                "time_stop_bars": 12,
            }

            cls._orders[key] = {
                "idempotency_key": key,
                "trace_id": resolved_trace_id,
                "strategy": strategy,
                "symbol": symbol,
                "direction": direction,
                "lot": lot,
                "state": OrderState.CREATED,
                "created_at": now_utc_ts(),
                "policy_snapshot": policy_snap,
                "execution_version": EXECUTION_VERSION,
                "risk_policy_version": RISK_POLICY_VERSION,
                "emergency_tracking": EmergencyCloseTracking(),
                "decision_snapshot": full_snapshot,
                # Lộ trình trạng thái nhằm tổng kết chuỗi chuyển đổi để tránh gây quá tải trên nhật ký (log).
                "_transition_path": [OrderState.CREATED.value],
            }
            cls._decision_snapshots[key] = full_snapshot

        cls._append_durable_event("ORDER_CREATED", key, cls._orders[key], trace_id=resolved_trace_id)
        log(f"🔀 [STATE_MACHINE] Created Order {key[:16]} for {strategy} on {symbol} {direction} {lot} lots.")
        try:
            from src.python.utils import decision_journal
            decision_journal.record("TRADE", f"{strategy} {symbol} {direction} lot={lot}",
                                     trace_id=resolved_trace_id, strategy=strategy, symbol=symbol)
        except Exception as _dje:
            log_error(f"❌ [STATE_MACHINE] decision_journal TRADE ghi lỗi (bỏ qua, không chặn tạo lệnh): {_dje}")
        return key

    @classmethod
    def transition(cls, idempotency_key: str, new_state: OrderState, reason: str = "",
                   broker_verification: Optional[ProtectionVerificationResult] = None, ticket: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Chuyển đổi trạng thái đơn hàng dựa trên biểu đồ hợp lệ, từ chối khi xác minh thất bại."""
        with cls._lock:
            order = cls._orders.get(idempotency_key)
            if not order:
                return False

            old_state = order["state"]
            if not isinstance(old_state, OrderState):
                try:
                    old_state = OrderState(old_state)
                except Exception:
                    log_error(f"❌ [STATE_MACHINE] Trạng thái hiện tại không hợp lệ cho {idempotency_key[:16]}: {old_state!r}")
                    return False

            allowed = _VALID_TRANSITIONS.get(old_state, set())
            if new_state not in allowed:
                log_error(f"❌ [STATE_MACHINE] Transition bị từ chối: {old_state.value} -> {new_state.value} "
                          f"không hợp lệ cho key {idempotency_key[:16]} (reason={reason}).")
                return False

            if new_state == OrderState.PROTECTED:
                if broker_verification is None or not broker_verification.stop_verified:
                    log_error(f"🛡️ [STATE_MACHINE] TỪ CHỐI chuyển PROTECTED cho {idempotency_key[:16]}: "
                              f"chưa có ProtectionVerificationResult.stop_verified=True — không thể tin "
                              f"là đã có SL xác nhận trên broker. Caller nên chuyển sang PROTECTION_FAILED.")
                    return False

            order["state"] = new_state
            order["updated_at"] = now_utc_ts()
            if broker_verification:
                order["broker_verification"] = broker_verification
            if metadata:
                order.setdefault("close_metadata", {}).update(metadata)
            trace_id = order.get("trace_id")
            created_at = order.get("created_at")

            cls._append_durable_event("OrderStateTransitioned", aggregate_id=idempotency_key, payload={
                "key": idempotency_key,
                "old_state": old_state.value,
                "new_state": new_state.value,
                "ticket": ticket,
                "reason": reason,
                "metadata": metadata or {},
            }, trace_id=trace_id)
            # GỘP LOG VÒNG ĐỜI LỆNH (30/07 — yêu cầu người dùng "quá nhiều log
            # khi vào lệnh")
            # -----------------------------------------------------------------
            # Một lệnh vào bình thường đi qua 7 bước và trước đây in ĐỦ 7 dòng:
            #     CREATED -> VALIDATED -> SUBMITTING -> BROKER_ACCEPTED ->
            #     FILLED -> POSITION_VERIFIED -> PROTECTED -> MANAGED
            # Bảy dòng cho một sự kiện, lặp lại mỗi lệnh, đẩy những dòng ĐÁNG ĐỌC
            # (lý do vào lệnh, cảnh báo, sự cố) trôi khỏi màn hình.
            #
            # Nay: các bước THUẬN LỢI im lặng, và khi tới `MANAGED` in ĐÚNG MỘT
            # dòng tổng kết cả chặng đường. Mọi bước BẤT THƯỜNG (rejected,
            # protection failed, emergency, closed...) vẫn in ngay như cũ —
            # chúng mới là thứ cần thấy tức thì.
            #
            # KHÔNG MẤT AUDIT TRAIL: từng bước vẫn được ghi đầy đủ vào
            # `durable_event_log.jsonl` ngay phía trên (`_append_durable_event`),
            # nguồn sự thật để `rebuild_from_outbox()` dựng lại trạng thái. Đây
            # thuần tuý là giảm ồn ở tầng HIỂN THỊ.
            order.setdefault("_transition_path", []).append(new_state.value)
            if new_state in _HAPPY_PATH_STEPS:
                pass                      # im lặng — sẽ gộp vào dòng MANAGED
            elif new_state == OrderState.MANAGED:
                _transition_path = " -> ".join(order.get("_transition_path") or [new_state.value])
                log(f"🔀 [STATE_MACHINE] Order {idempotency_key[:16]} sẵn sàng: {_transition_path}"
                    + (f" ({reason})" if reason else ""))
            else:
                log(f"🔀 [STATE_MACHINE] Order {idempotency_key[:16]} transitioned: {old_state.value} -> {new_state.value}"
                    + (f" ({reason})" if reason else ""))

            if new_state == OrderState.CLOSED:
                duration_sec = None
                if isinstance(created_at, pd.Timestamp):
                    duration_sec = (now_utc_ts() - created_at).total_seconds()
                cls._append_durable_event("PositionClosed", aggregate_id=idempotency_key, payload={
                    "key": idempotency_key,
                    "management_duration_seconds": duration_sec,
                    **(metadata or {}),
                }, trace_id=trace_id)

            # BUG-11: Cleanup unbounded memory growth
            # Terminal states per _VALID_TRANSITIONS comment (line ~118): REJECTED,
            # VALIDATION_REJECTED, BROKER_REJECTED, CANCELLED, CLOSED, EMERGENCY_CLOSED.
            # OrderState.ABANDONED does not exist in the enum — referencing it raised
            # AttributeError on every transition() call once _orders exceeded 100.
            if len(cls._orders) > 100:
                _TERMINAL_STATES = (
                    OrderState.CLOSED, OrderState.REJECTED, OrderState.VALIDATION_REJECTED,
                    OrderState.BROKER_REJECTED, OrderState.CANCELLED, OrderState.EMERGENCY_CLOSED,
                )
                # `k != idempotency_key` (FIX 08/08): danh sách này theo THỨ TỰ
                # TẠO chứ không theo thời điểm đóng, và nó chạy ở CUỐI chính lời
                # gọi vừa đóng lệnh. Một lệnh giữ lâu (swing_don giữ nhiều ngày,
                # nằm ở đầu `_orders`) có thể bị dọn NGAY trong lời gọi đóng của
                # chính nó, trong khi 50 lệnh đóng từ trước vẫn được giữ. Khi đó
                # `position_lifecycle.finalize_position_closed()` nhận `True` từ
                # `transition()` nhưng ngay sau đó `get_order()` trả `None` — mất
                # `trace_id` (khoá join sổ lệnh <-> sổ sự kiện) và
                # `annotate_close_metadata(..., journal_published=True)` trả
                # `False` trong im lặng (caller không kiểm giá trị trả về), tức
                # mất dấu "đã ghi sổ" giữa hai con đường đóng lệnh.
                keys_to_remove = [k for k, v in cls._orders.items()
                                  if v.get("state") in _TERMINAL_STATES and k != idempotency_key]
                for k in keys_to_remove[:-50]:  # Keep last 50 terminal orders
                    cls._orders.pop(k, None)
                    cls._decision_snapshots.pop(k, None)
                    cls._execution_snapshots.pop(k, None)
                    cls._fill_snapshots.pop(k, None)
                    # FIX 01/08: TUYỆT ĐỐI KHÔNG `_claimed_keys.discard(k)` ở đây.
                    # Dọn bộ nhớ là việc của bản ghi CHI TIẾT lệnh; quyền chống trùng
                    # của tín hiệu phải sống lâu hơn thế, nếu không hệ thống tự nhả
                    # dedup đúng lúc bận nhất (>100 lệnh) và có thể mở lệnh thứ hai cho
                    # cùng một tín hiệu. Xem `_remember_claim()` cho kịch bản đầy đủ và
                    # cho trần bộ nhớ thay thế.

            return True

    @classmethod
    def resolve_unknown_broker_state(cls, idempotency_key: str, broker_ticket_found: Optional[Any]) -> Optional[OrderState]:
        """FIX 21/07: đọc mô tả "khi timeout, chuyển UNKNOWN_BROKER_STATE, Engine PHẢI truy vấn
        lại số lệnh sang trước khi quyết định retry" nhưng trước đây không có code nào thực sự
        làm điều này — SUBMIT_TIMEOUT chỉ tồn tại ở khai báo enum, 0 caller. Hàm này là contract
        point thật: caller tự truy vấn broker (vd mt5.positions_get/history_orders_get theo
        magic/comment) RỒI gọi hàm này với kết quả tìm được."""
        if not cls.transition(idempotency_key, OrderState.UNKNOWN_BROKER_STATE, reason="submit timeout - truy vấn lại broker"):
            return None
        next_state = OrderState.FILLED if broker_ticket_found else OrderState.CANCELLED
        ok = cls.transition(idempotency_key, next_state,
                             ticket=str(broker_ticket_found) if broker_ticket_found else None,
                             reason="kết quả truy vấn broker sau submit timeout")
        return next_state if ok else None

    @classmethod
    def handle_partially_filled(cls, idempotency_key: str, filled_quantity: float,
                                 verification: ProtectionVerificationResult,
                                 escalate_on_unverified: bool = True) -> bool:
        """FIX 21/07: trước đây chỉ ghi state=PARTIALLY_FILLED và 2 giá trị do caller truyền vào
        rồi dừng lại — không verify gì, không có nhánh EMERGENCY_CLOSING như đọc mô tả ("phần đã
        fill phải được bảo vệ NGAY"). Giờ bắt buộc ProtectionVerificationResult THẬT cho phần đã
        khớp, rồi tự động chuyển tiếp: PROTECTED nếu SL xác nhận, EMERGENCY_CLOSING nếu không.

        `escalate_on_unverified` (THÊM 01/08, khi hàm này lần đầu được nối vào đường
        thực thi thật — trước đó nó có 0 caller production): `False` để DỪNG ở
        PARTIALLY_FILLED thay vì nhảy thẳng EMERGENCY_CLOSING, nhường quyền xử lý cho
        `PositionExecutionService.ensure_protected_or_escalate()`.

        VÌ SAO CẦN: `EMERGENCY_CLOSING` ở đây chỉ là một NHÃN TRẠNG THÁI — không có dòng
        code nào gửi lệnh đóng theo sau nó. Vé sẽ nằm im ở trạng thái đó, không ai thử
        gắn lại SL, và mọi lần đóng bình thường sau này đều bị `transition()` từ chối
        (EMERGENCY_CLOSING không có cạnh sang CLOSED). Đường `ensure_protected_or_
        escalate()` thì làm đúng chính sách thận trọng người dùng đã chọn: thử gắn lại SL
        tối đa `PROTECTION_RETRY_LIMIT` lần, và chỉ khi hết lượt mới CHẶN entry mới toàn
        hệ thống + cảnh báo CRITICAL, KHÔNG tự ý đóng vị thế.
        """
        with cls._lock:
            order = cls._orders.get(idempotency_key)
            if order is None:
                return False
            old_state = order["state"]
            if not isinstance(old_state, OrderState):
                try:
                    old_state = OrderState(old_state)
                except Exception:
                    return False
            if OrderState.PARTIALLY_FILLED not in _VALID_TRANSITIONS.get(old_state, set()):
                log_error(f"❌ [STATE_MACHINE] PARTIALLY_FILLED không hợp lệ từ {old_state.value} cho {idempotency_key[:16]}.")
                return False
            order["state"] = OrderState.PARTIALLY_FILLED
            order["filled_quantity"] = filled_quantity
            order["sl_price"] = verification.expected_stop_price
            order["updated_at"] = now_utc_ts()
            trace_id = order.get("trace_id")
            cls._append_durable_event("PartiallyFilledProtected", aggregate_id=idempotency_key, payload={
                "filled_quantity": filled_quantity,
                "sl_price": verification.expected_stop_price,
                "stop_verified": verification.stop_verified,
            }, trace_id=trace_id)

        # Chuyển tiếp NGOẠI khỏi 'with cls._lock' ở trên (transition() tự khoá riêng) —
        # bảo vệ phần đã fill NGAY, không chờ toàn bộ order fill xong.
        if verification.stop_verified:
            return cls.transition(idempotency_key, OrderState.PROTECTED, broker_verification=verification)
        if not escalate_on_unverified:
            log_error(f"⚠️ [STATE_MACHINE] {idempotency_key[:16]} khớp MỘT PHẦN ({filled_quantity}) và "
                      f"CHƯA xác minh được SL — giữ ở PARTIALLY_FILLED, nhường cho "
                      f"ensure_protected_or_escalate() thử gắn lại SL.")
            return True
        return cls.transition(idempotency_key, OrderState.EMERGENCY_CLOSING,
                               reason="Partial fill không xác minh được SL cho phần đã khớp")

    @classmethod
    def record_emergency_close_attempt(cls, idempotency_key: str, success: bool, broker_error: str = "") -> Optional[OrderState]:
        """FIX 21/07: EMERGENCY_CLOSE_FAILED từng là "terminal state im lặng" — enum tồn tại
        nhưng 0 logic nào update EmergencyCloseTracking hay dẫn đến hành động gì. Giờ: mỗi lần
        đóng khẩn cấp thất bại cập nhật thật attempt_count/first_failure_at/last_attempt_at/
        last_broker_error/next_retry_at (bounded exponential backoff, trần 300s), và sau
        MAX_EMERGENCY_CLOSE_ATTEMPTS lần thì báo CRITICAL metric + chặn entry mới toàn hệ thống
        qua is_trading_halted().

        FIX 08/08 — VÒNG THỬ LẠI TỰ GÃY VÀ CỜ HALT IM LẶNG (hai lỗi thật, có test)
        --------------------------------------------------------------------------
        (1) Sau lượt thử đầu, lệnh nằm ở `EMERGENCY_CLOSE_RETRY`, mà đồ thị chỉ có
            cạnh RETRY -> EMERGENCY_CLOSING. Lượt thứ hai gọi `transition(RETRY ->
            RETRY)` và lượt cuối gọi `transition(RETRY -> EMERGENCY_CLOSE_FAILED)` —
            không cạnh nào tồn tại, nên MỌI lượt từ lượt 2 trở đi bị từ chối và hàm
            trả `None`. Sổ vòng đời đóng băng vĩnh viễn ở RETRY (từ đó cũng không
            còn đường sang CLOSED, nên lần đóng thật về sau cũng bị từ chối). Hai
            test cũ không bắt được vì CHÍNH TEST tự chèn `transition(...,
            EMERGENCY_CLOSING)` sau mỗi lượt — một hợp đồng không được viết ở đâu
            cả, và hàm này hiện có 0 caller production để làm việc chèn đó. Nay hàm
            tự đưa lệnh về EMERGENCY_CLOSING (đúng nghĩa "bắt đầu một lượt đóng
            khẩn cấp nữa") trước khi ghi nhận lượt mới.
        (2) Cờ halt trước đây được bật bằng cách ghi thẳng `cls._trading_halted =
            True`, KHÔNG qua `halt_trading()` — nên không có email nào tới người
            vận hành; và dòng log CRITICAL + metric lại bị gác sau `and ok`, mà
            `ok` chính là kết quả transition vừa bị từ chối ở (1). Kết quả: toàn hệ
            thống ngừng vào lệnh, cờ ghi xuống đĩa nên sống qua restart, mà TUYỆT
            ĐỐI im lặng. Nay đi qua `halt_trading()` (log CRITICAL + metric + email
            dedup) và không gác cảnh báo sau `ok`."""
        _newly_halted_reason: Optional[str] = None
        with cls._lock:
            order = cls._orders.get(idempotency_key)
            if order is None:
                return None
            _state_now = order.get("state")
            tracking = order.get("emergency_tracking")
            if not isinstance(tracking, EmergencyCloseTracking):
                tracking = EmergencyCloseTracking()
            now = now_utc_ts()
            if success:
                order["emergency_tracking"] = tracking
                target = OrderState.EMERGENCY_CLOSED
            else:
                tracking.attempt_count += 1
                if tracking.first_failure_at is None:
                    tracking.first_failure_at = now
                tracking.last_attempt_at = now
                tracking.last_broker_error = broker_error
                backoff_sec = min(300, 5 * (2 ** (tracking.attempt_count - 1)))
                tracking.next_retry_at = now + pd.Timedelta(seconds=backoff_sec)
                order["emergency_tracking"] = tracking
                if tracking.attempt_count >= MAX_EMERGENCY_CLOSE_ATTEMPTS:
                    # KHÔNG tự bật cờ ở đây: `halt_trading()` gọi ngay dưới sẽ
                    # bật + persist + báo động. Bật trước làm nó thấy
                    # `already_halted=True` và im lặng bỏ qua email cảnh báo.
                    _newly_halted_reason = f"emergency_close_failed x{tracking.attempt_count}: {broker_error}"
                    target = OrderState.EMERGENCY_CLOSE_FAILED
                else:
                    target = OrderState.EMERGENCY_CLOSE_RETRY
            attempt_count_snapshot = tracking.attempt_count

        # FIX 23/07 (review nhất quán trước release): persist I/O nằm NGOẠI
        # 'with cls._lock' — khớp pattern halt_trading(), tránh giữ global OSM
        # lock trong lúc ghi đĩa (contention nếu nhiều thread gọi OSM cùng lúc).
        if _newly_halted_reason is not None:
            cls.halt_trading(_newly_halted_reason)

        # Xem (1) trong docstring: một lượt đóng khẩn cấp mới bắt đầu bằng việc
        # quay lại EMERGENCY_CLOSING; thiếu bước này thì mọi lượt từ lượt 2 đều
        # bị chính đồ thị trạng thái từ chối.
        if _state_now == OrderState.EMERGENCY_CLOSE_RETRY:
            cls.transition(idempotency_key, OrderState.EMERGENCY_CLOSING,
                           reason="bắt đầu lượt đóng khẩn cấp tiếp theo")

        ok = cls.transition(idempotency_key, target, reason=broker_error or "emergency close thành công")
        if target == OrderState.EMERGENCY_CLOSE_FAILED:
            try:
                from src.python.core.observability import MetricsEngine
                MetricsEngine.record_metric("RECOVERY", "emergency_close_failed_terminal", 1.0,
                                             warn_thresh=0.0, crit_thresh=0.0, metric_type="counter",
                                             labels={"idempotency_key": idempotency_key[:16]})
            except Exception as _me:
                log_error(f"❌ [STATE_MACHINE] không ghi được metric emergency_close_failed: {_me}")
            log_error(f"🔴 [STATE_MACHINE] CRITICAL: {idempotency_key[:16]} EMERGENCY_CLOSE_FAILED sau "
                      f"{attempt_count_snapshot} lần thử -> CHẶN ENTRY MỚI TOÀN HỆ THỐNG.")
        return target if ok else None

    @classmethod
    def release_rejected_order(cls, idempotency_key: str) -> bool:
        """FIX 21/07 (code review): `create_order()` claims the idempotency key
        (strategy|symbol|bar_timestamp|direction) BEFORE the broker call is ever
        made. Every one of the 8 strategies' order-send failure branch
        (`else: log_error("order fail ...")`) previously did NOTHING to the OSM
        record — it stayed orphaned at SUBMITTING forever, and because
        `claim_idempotency_key()` only checks "does this key exist in `_orders`"
        (not its state), ANY transient broker error (requote/timeout/temporary
        reject) permanently poisoned that bar+direction: every subsequent retry
        for the SAME bar (the strategy's normal, intended behavior — e.g.
        magic_hours' `pending_side` retry loop is explicitly designed to retry
        temporary failures) was rejected as "duplicate" by `create_order()`,
        even though NO real order exists on the broker. Net effect: one
        transient broker hiccup could silently cost an entire trading
        opportunity (up to a full rebalance period) with no operator-visible
        symptom beyond a log line. Cadence in this repo: 30m/1h/4h bar close for
        the 25 intraday legs, 21 days for the two D1 legs.

        This releases the claim ONLY if the order's current state is a
        terminal REJECTED-type state that provably never resulted in a real
        broker position (VALIDATION_REJECTED/BROKER_REJECTED/CANCELLED) — never
        for FILLED/PROTECTED/MANAGED/etc., which would break real dedup
        guarantees. Caller contract: transition to `BROKER_REJECTED` (or
        equivalent) FIRST, then call this."""
        _RELEASABLE = {OrderState.VALIDATION_REJECTED, OrderState.BROKER_REJECTED, OrderState.CANCELLED}
        with cls._lock:
            order = cls._orders.get(idempotency_key)
            if not order:
                return False
            state = order.get("state")
            if not isinstance(state, OrderState):
                try:
                    state = OrderState(state)
                except Exception:
                    return False
            if state not in _RELEASABLE:
                log_error(f"❌ [STATE_MACHINE] release_rejected_order({idempotency_key[:16]}) TỪ CHỐI: "
                          f"trạng thái hiện tại {state.value} không phải terminal-rejected — "
                          f"KHÔNG giải phóng (tránh phá vỡ dedup thật).")
                return False
            _trace_id = order.get("trace_id")
            del cls._orders[idempotency_key]
            cls._claimed_keys.discard(idempotency_key)
            # FIX 08/08: việc giải phóng phải BỀN như việc claim. Trước đây nó
            # chỉ xoá trong RAM, nên `rebuild_from_outbox()` phát lại
            # `ORDER_CREATED` và claim lại đúng khoá này — tức chính bug mà hàm
            # này sinh ra để sửa quay lại qua ngả restart: một lần broker từ chối
            # tạm thời + một lần restart (watchdog/redeploy) là chặn vĩnh viễn
            # cơ hội của bar đó — với hai chân D1 thì mất cả chu kỳ tái cân bằng 21 ngày.
            cls._append_durable_event("OrderClaimReleased", aggregate_id=idempotency_key,
                                       payload={"key": idempotency_key, "state": state.value},
                                       trace_id=_trace_id)
        log(f"🔄 [STATE_MACHINE] Giải phóng idempotency key {idempotency_key[:16]} (state={state.value}) "
            f"— cho phép retry cùng bar/direction chu kỳ sau.")
        return True

    @classmethod
    def is_trading_halted(cls) -> bool:
        """True nếu bất kỳ order nào đã EMERGENCY_CLOSE_FAILED quá hết MAX_EMERGENCY_CLOSE_ATTEMPTS,
        hoặc PROTECTION_RETRY_LIMIT bị vượt quá halt_trading() — các chiến lược PHẢI kiểm tra cờ
        này qua EntrySafetyGate.evaluate() trước khi vào lệnh mới."""
        return cls._trading_halted

    @classmethod
    def halt_trading(cls, reason: str) -> None:
        """Stage D (21/07): điểm dừng chung để bật cờ is_trading_halted() từ bên ngoài
        record_emergency_close_attempt() (vd PositionExecutionService.ensure_protected_or_escalate
        sau khi hết PROTECTION_RETRY_LIMIT lần thử gán lại SL mà vẫn không xác minh được — chính
        sách THẬN TRỌNG người dùng chọn: KHÔNG tự động emergency-close, chỉ CHẶN entry mới +
        CRITICAL alert + đợi reconciliation/người vận hành can thiệp thủ công)."""
        with cls._lock:
            already_halted = cls._trading_halted
            cls._trading_halted = True
        if already_halted:
            return
        cls._persist_halt_state(True, reason=reason)
        log_error(f"🛑 [STATE_MACHINE] CRITICAL: hệ thống bị TRADING_HALTED — {reason}")
        try:
            from src.python.core.observability import MetricsEngine
            MetricsEngine.record_metric("RECOVERY", "trading_halted", 1.0,
                                         warn_thresh=0.0, crit_thresh=0.0, metric_type="counter",
                                         labels={"reason": reason[:80]})
        except Exception as _me:
            log_error(f"❌ [STATE_MACHINE] không ghi được metric trading_halted: {_me}")
        # FIX 25/07 (code review — CRITICAL): trước đây halt_trading() chỉ ghi
        # log + metric (đọc bằng cách chủ động vào GUI/log) — KHÔNG có kênh cảnh
        # báo chủ động nào (email) tới người vận hành. Đây là kịch bản NGHIÊM
        # TRỌNG NHẤT của hệ thống (1 lệnh có thể đang KHÔNG được bảo vệ SL/TP,
        # xem `PositionExecutionService.ensure_protected_or_escalate`) nhưng lại
        # là kênh im lặng nhất — gửi alert thật, tái dùng hạ tầng dedup sẵn có
        # (`utils/alerts.send_alert`, cùng cơ chế risk_guard kill-switch dùng).
        try:
            from src.python.utils.alerts import send_alert
            send_alert(
                "trading_halted",
                "🛑🛑 [THE CHEOPARD] TRADING HALTED — CẦN CAN THIỆP THỦ CÔNG NGAY",
                f"Lý do: {reason}\n\n"
                "Hệ thống đã CHẶN toàn bộ entry mới trên MỌI chiến lược. Nguyên nhân thường gặp: "
                "không xác minh được SL/TP đã đặt thành công sau nhiều lần thử (có thể đang có vị "
                "thế KHÔNG được bảo vệ).\n"
                "Yêu cầu: kiểm tra vị thế đang mở qua terminal MT5 NGAY, xác nhận SL/TP thủ công "
                "nếu cần, sau đó gọi OrderStateMachine.clear_trading_halt(reason) để mở lại.",
                body_html=(
                    "<div style='border:1px solid #dc3545;border-radius:8px;padding:16px;"
                    "background-color:#f8d7da'>"
                    "<h3 style='color:#dc3545;margin-top:0'>🛑🛑 TRADING HALTED</h3>"
                    f"<p><b>Lý do:</b> <code>{reason}</code></p>"
                    "<p>Hệ thống đã CHẶN entry mới trên MỌI chiến lược — CÓ THỂ đang có vị thế "
                    "KHÔNG được bảo vệ SL/TP.</p>"
                    "<p style='margin-bottom:0'><b>Hành động yêu cầu:</b> kiểm tra vị thế qua "
                    "terminal MT5 NGAY, sau đó dùng <code>clear_trading_halt()</code> khi đã xác "
                    "minh an toàn.</p></div>"
                ),
            )
        except Exception as _ae:
            log_error(f"❌ [STATE_MACHINE] không gửi được alert trading_halted (bỏ qua): {_ae}")

    @classmethod
    def annotate_close_metadata(cls, idempotency_key: str, metadata: Dict[str, Any]) -> bool:
        """Ghi thêm metadata vào một order ĐÃ ở trạng thái terminal, KHÔNG đổi state.

        VÌ SAO CẦN (30/07): `transition()` không thể dùng cho việc này — CLOSED là
        terminal, không có cạnh CLOSED -> CLOSED, nên mọi lời gọi đều bị từ chối.
        Nhưng có những sự thật chỉ biết được SAU khi đã CLOSED, và phải bền vững
        qua restart. Trường hợp đầu tiên: cờ `journal_published` của
        `position_lifecycle` — dấu vết "đã phát PositionClosed vào sổ lệnh" dùng
        để đảm bảo phát ĐÚNG MỘT LẦN giữa hai con đường đóng lệnh. Nếu cờ này chỉ
        sống trong RAM thì một lần restart giữa hai con đường sẽ sinh bản ghi
        trùng — làm sai rolling expectancy mà StrategyHealthEngine dùng để tự
        động giảm rủi ro thật.

        Ghi kèm một durable event riêng (`OrderCloseMetadataAnnotated`) thay vì
        mượn `OrderStateTransitioned`: mượn sẽ khiến `rebuild_from_outbox()` ghi
        đè `state` bằng một giá trị không thuộc lần chuyển trạng thái nào, tức
        làm bẩn chính nguồn sự thật mà nó đang cố bảo vệ.
        """
        if not idempotency_key or not metadata:
            return False
        with cls._lock:
            order = cls._orders.get(idempotency_key)
            if not order:
                return False
            order.setdefault("close_metadata", {}).update(metadata)
            cls._append_durable_event("OrderCloseMetadataAnnotated", aggregate_id=idempotency_key,
                                       payload={"key": idempotency_key, "metadata": metadata},
                                       trace_id=order.get("trace_id"))
            return True

    @classmethod
    def get_order(cls, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Trả BẢN SAO của bản ghi, không phải hàng trong sổ cái (sửa 08/08).

        Bản cũ trả thẳng dict nội bộ: khoá chỉ bảo vệ lúc tra cứu chứ không bảo
        vệ thứ trả ra. Một caller vô tình gán vào đó (`order["state"] = ...`) là
        ghi thẳng vào sổ cái, vòng qua toàn bộ kiểm tra của `transition()` (đồ
        thị trạng thái + bắt buộc `stop_verified=True` khi vào PROTECTED) và
        không để lại sự kiện nào trong outbox — RAM và sổ sự kiện lệch nhau vĩnh
        viễn, không truy được ai đã đổi. Mọi caller hiện tại (`exit_pipeline`,
        `position_lifecycle`) chỉ ĐỌC nên bản sao không đổi hành vi."""
        with cls._lock:
            order = cls._orders.get(idempotency_key)
            if order is None:
                return None
            snapshot = dict(order)
            _cm = order.get("close_metadata")
            if isinstance(_cm, dict):
                # Dict lồng DUY NHẤT mà caller thật sự đọc/ghi — sao riêng.
                snapshot["close_metadata"] = dict(_cm)
            return snapshot

    @classmethod
    def get_snapshot(cls, idempotency_key: str) -> Optional[Dict[str, Any]]:
        with cls._lock:
            return cls._decision_snapshots.get(idempotency_key)
