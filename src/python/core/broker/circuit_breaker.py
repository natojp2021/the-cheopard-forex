import time
import threading
from enum import Enum
from typing import Set, Tuple
import MetaTrader5 as mt5
from src.python.utils.logger import log, log_error

class BreakerState(Enum):
    CLOSED = "CLOSED"         # Bình thường, cho phép thực thi lệnh
    OPEN = "OPEN"             # Ngắt mạch, chặn mọi lệnh gửi ra sàn
    HALF_OPEN = "HALF_OPEN"   # Thử nghiệm kết nối lại sau thời gian cooldown

class MT5CircuitBreaker:
    """
    Bộ ngắt mạch tổ chức (Institutional Circuit Breaker) cho kết nối và khớp lệnh MT5 Pure API.
    Phân loại lỗi có thể thử lại và lỗi nghiêm trọng, bảo vệ tài khoản khỏi việc gửi quá nhiều lệnh 
    khi máy chủ môi giới gặp sự cố hoặc tài khoản không đủ tiền ký quỹ.
    """
    # Các mã lỗi trả về được phân loại dựa trên tài liệu MetaTrader5.
    # Lỗi nghiêm trọng (Fatal) đại diện cho các lỗi cấu trúc cần can thiệp thủ công.
    # Lỗi có thể thử lại (Retriable) đại diện cho các sự cố tạm thời có thể tự phục hồi.

    # Các mã lỗi MT5 KHÔNG được phép thử lại (Lỗi nghiêm trọng)
    FATAL_RETCODES: Set[int] = {
        10013,  # Yêu cầu không hợp lệ
        # 10014 CỐ Ý nằm ở CẢ HAI tập, đừng "dọn" đi:
        #   ở đây  -> `order_router._is_fatal()` trả True = KHÔNG thử lại
        #             (gửi lại đúng khối lượng sai thì vẫn sai);
        #   ở dưới -> `ORDER_SCOPED_RETCODES` chặn nó MỞ CẦU CHÌ.
        # Hai câu hỏi khác nhau: "có thử lại không" và "có dừng cả lượt không".
        10014,  # Khối lượng không hợp lệ
        10015,  # Giá không hợp lệ
        10016,  # Mức Dừng lỗ/Chốt lời không hợp lệ
        10017,  # Giao dịch bị vô hiệu hóa cho mã này
        10018,  # Thị trường đóng cửa
        10019,  # Không đủ tiền ký quỹ
        10022,  # Thời gian hết hạn không hợp lệ
        10026,  # Giao dịch tự động bị máy chủ vô hiệu hóa
        10027,  # Giao dịch tự động bị máy khách vô hiệu hóa
        10030,  # Chế độ khớp lệnh không được hỗ trợ
    }

    # LỖI CỦA RIÊNG MỘT LỆNH — KHÔNG được hạ cả lượt gửi.
    #
    # SỰ CỐ 04:28 NGÀY 21/08/2026
    # ============================
    #     [LỖI] <công cụ>  INCREASE  SELL  0.02 lot ... retcode 10014 Invalid volume
    #     [CIRCUIT BREAKER OPEN] FATAL NON-RETRIABLE ERROR: retcode=10014
    #
    # một công cụ có `volume_min = 0.1` trong khi phần còn lại là 0,01 — xem
    # `order_plan.min_trade_lots` cho nguyên nhân gốc, đã sửa. Nhưng bản thân
    # cách phân loại ở đây cũng sai một bậc: `10014` nói "KHỐI LƯỢNG CỦA LỆNH
    # NÀY sai", không nói "tài khoản hỏng". Xếp nó cạnh 10019 (hết ký quỹ) và
    # 10027 (tắt giao dịch tự động) là đánh đồng một lỗi tham số với một sự cố
    # toàn tài khoản, nên một công cụ có bậc lot khác thường chặn nốt 26 công cụ
    # còn lại, lặp lại mỗi chu kỳ.
    #
    # Vẫn KHÔNG thử lại — gửi lại đúng khối lượng sai thì vẫn sai. Chỉ khác ở
    # chỗ: từ chối MỘT lệnh, không mở cầu chì.
    #
    # Cố ý chỉ có 10014 ở đây. 10013/10015/10016/10022 cũng mang tính "một
    # lệnh", nhưng chưa quan sát được trên đường live nên chưa đụng — nới một
    # lớp an toàn theo suy luận là cách nó âm thầm mục ra.
    ORDER_SCOPED_RETCODES: Set[int] = {
        10014,  # Khối lượng không hợp lệ — sai tham số của CHÍNH lệnh này
    }

    # Các mã lỗi MT5 có thể thử lại (Sự cố kết nối hoặc báo giá lại tạm thời)
    RETRIABLE_RETCODES: Set[int] = {
        10004,  # Báo giá lại
        10006,  # Yêu cầu bị từ chối
        10012,  # Hết thời gian chờ
        10021,  # Không có báo giá
        10024,  # Quá nhiều yêu cầu
        10031,  # Không có kết nối tới máy chủ môi giới
        10032,  # Chỉ cho phép tài khoản thực
        10036,  # Vị thế đã đóng
    }

    def __init__(self, max_failures: int = 5, cooldown_seconds: float = 60.0,
                 half_open_trial_timeout: float = 30.0):
        self.max_failures = max_failures
        self.cooldown_seconds = cooldown_seconds
        # Thời gian chờ tối đa cho một lệnh thử nghiệm.
        self.half_open_trial_timeout = half_open_trial_timeout
        self._half_open_trial_started_at = 0.0
        self.state = BreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.last_fatal_error: str = ""
        self._lock = threading.Lock()
        # Cờ trạng thái đảm bảo chỉ có duy nhất một lệnh thử nghiệm được gửi đi
        # trong trạng thái HALF_OPEN, ngăn chặn việc gửi quá nhiều lệnh khi 
        # hệ thống chưa hoàn toàn phục hồi. Cờ này sẽ được giải phóng khi lệnh thử
        # được ghi nhận thành công hoặc thất bại.
        self._half_open_trial_in_flight = False

    def can_execute(self) -> Tuple[bool, str]:
        """Kiểm tra trạng thái bộ ngắt mạch trước khi thực thi lệnh."""
        with self._lock:
            now = time.time()
            if self.state == BreakerState.OPEN:
                if now - self.last_failure_time >= self.cooldown_seconds:
                    log(f"⚡ [CIRCUIT BREAKER] Cooldown {self.cooldown_seconds}s hết hạn. Chuyển sang HALF_OPEN để thử nghiệm.")
                    self.state = BreakerState.HALF_OPEN
                    self._half_open_trial_in_flight = True
                    self._half_open_trial_started_at = now
                    return True, "HALF_OPEN test execution"
                else:
                    remaining = int(self.cooldown_seconds - (now - self.last_failure_time))
                    return False, f"CIRCUIT BREAKER OPEN! Blocked due to fatal error or too many retries. Cooldown: {remaining}s left. Last error: {self.last_fatal_error}"
            if self.state == BreakerState.HALF_OPEN:
                if self._half_open_trial_in_flight:
                    # Nếu lệnh thử nghiệm không trả về kết quả trong thời gian chờ,
                    # xem như thất bại. Điều này ngăn chặn tình trạng cờ thử nghiệm
                    # bị kẹt vô thời hạn do ngoại lệ hoặc thoái lui sớm từ tiến trình gọi.
                    # Khi hệ thống vượt quá thời gian thử, trạng thái sẽ quay về OPEN
                    # và tiếp tục chu kỳ làm nguội (cooldown).
                    if now - self._half_open_trial_started_at >= self.half_open_trial_timeout:
                        log_error(
                            f"⏱️ [CIRCUIT BREAKER] Lệnh thử nghiệm HALF_OPEN quá "
                            f"{self.half_open_trial_timeout:.0f}s không có kết quả "
                            f"(caller thoát sớm hoặc ném lỗi) — coi như THẤT BẠI, "
                            f"quay lại OPEN và đếm lại cooldown.")
                        self.state = BreakerState.OPEN
                        self._half_open_trial_in_flight = False
                        self._half_open_trial_started_at = 0.0
                        self.last_failure_time = now
                        return False, ("CIRCUIT BREAKER OPEN! Lệnh thử nghiệm trước đó "
                                       "quá hạn không có kết quả.")
                    return False, ("CIRCUIT BREAKER HALF_OPEN: đang chờ kết quả lệnh thử nghiệm trước đó "
                                    "trước khi cho phép thêm lệnh mới.")
                self._half_open_trial_in_flight = True
                self._half_open_trial_started_at = now
                return True, "HALF_OPEN test execution (retry probe)"
            return True, "CLOSED (Normal)"

    def record_success(self, source: str = "trade"):
        """
        Ghi nhận quá trình thực thi thành công và đặt lại trạng thái ngắt mạch.

        Việc kết nối lại thành công (source="connection") sẽ không đặt lại trạng thái 
        ngắt mạch nếu lỗi trước đó là lỗi nghiêm trọng từ giao dịch (ví dụ: thiếu tiền).
        Chỉ kết quả giao dịch thành công (source="trade") mới xóa trạng thái lỗi nghiêm trọng.
        """
        with self._lock:
            self._half_open_trial_in_flight = False
            self._half_open_trial_started_at = 0.0
            if source == "connection" and self.last_fatal_error.startswith("FATAL"):
                log("🔄 [CIRCUIT BREAKER] Reconnect OK nhưng breaker đang OPEN vì lỗi FATAL trade "
                    f"({self.last_fatal_error}) — giữ nguyên OPEN, chờ cooldown + probe.")
                return
            if self.state != BreakerState.CLOSED or self.failure_count > 0:
                log("✅ [CIRCUIT BREAKER] Thực thi thành công -> Reset trạng thái về CLOSED.")
                self.state = BreakerState.CLOSED
                self.failure_count = 0
                self.last_fatal_error = ""

    def record_failure(self, retcode: int, comment: str = "") -> bool:
        """
        Ghi nhận kết quả giao dịch thất bại.
        
        Trả về True nếu lỗi thuộc nhóm có thể thử lại, False nếu thuộc nhóm lỗi nghiêm trọng.
        """
        # Trích xuất lỗi từ MetaTrader5 trước khi khóa luồng để tránh treo hệ thống
        # nếu cuộc gọi giao tiếp tiến trình (IPC) gặp sự cố.
        detail = comment
        if not detail:
            try:
                detail = mt5.last_error()
            except Exception as e:
                detail = f"(không đọc được last_error: {e})"
        with self._lock:
            self._half_open_trial_in_flight = False
            self._half_open_trial_started_at = 0.0
            self.last_failure_time = time.time()
            error_msg = f"retcode={retcode} ({detail})"

            if retcode in self.ORDER_SCOPED_RETCODES:
                # Từ chối ĐÚNG lệnh này, giữ nguyên trạng thái cầu chì.
                log_error(f"⛔ [LỆNH BỊ TỪ CHỐI] {error_msg} — sai tham số của "
                          f"riêng lệnh này, KHÔNG mở cầu chì, các lệnh còn lại "
                          f"trong lượt vẫn được gửi.")
                return False

            if retcode in self.FATAL_RETCODES:
                self.failure_count = self.max_failures
                self.state = BreakerState.OPEN
                self.last_fatal_error = f"FATAL NON-RETRIABLE ERROR: {error_msg}"
                log_error(f"🛑 [CIRCUIT BREAKER OPEN] Phát hiện lỗi nghiêm trọng cấm retry: {self.last_fatal_error}")
                return False

            if retcode in self.RETRIABLE_RETCODES:
                self.failure_count += 1
                log(f"⚠️ [CIRCUIT BREAKER] Lỗi có thể retry ({self.failure_count}/{self.max_failures}): {error_msg}")
                if self.failure_count >= self.max_failures:
                    self.state = BreakerState.OPEN
                    self.last_fatal_error = f"MAX RETRIES EXCEEDED: {error_msg}"
                    log_error(f"🛑 [CIRCUIT BREAKER OPEN] Đạt giới hạn {self.max_failures} lần lỗi liên tiếp: {self.last_fatal_error}")
                    return False
                return True

            # Mã lỗi không xác định -> xem như lỗi thông thường tăng bộ đếm
            self.failure_count += 1
            log(f"⚠️ [CIRCUIT BREAKER] Lỗi không phân loại ({self.failure_count}/{self.max_failures}): {error_msg}")
            if self.failure_count >= self.max_failures:
                self.state = BreakerState.OPEN
                self.last_fatal_error = f"MAX UNKNOWN ERRORS EXCEEDED: {error_msg}"
                log_error(f"🛑 [CIRCUIT BREAKER OPEN] Đạt giới hạn lỗi: {self.last_fatal_error}")
                return False
            return True

# Thực thể duy nhất (Singleton) của bộ ngắt mạch cho toàn hệ thống
circuit_breaker = MT5CircuitBreaker()
