"""
Module kết nối trực tiếp với MetaTrader 5 thông qua Pure API.
Cung cấp các hàm gửi lệnh, quản lý vị thế và xử lý sự cố kết nối,
được bảo vệ bởi Circuit Breaker và cơ chế khóa đa luồng (thread-safety).
"""
import sys
import time
import threading
import MetaTrader5 as mt5
import os
from typing import Optional, List, Dict, Any, Tuple

try:
    from src.python.utils.env_loader import load_env_file
    load_env_file()
except Exception as e:
    print(f"Warning: load_env_file failed: {e}", flush=True)

BOT_NAME = os.environ.get("BOT_NAME", "THE CHEOPARD")
from src.python.core.config import LOGIN, PASSWORD, SERVER, SYMBOL, MT5_PATH, MT5_API_LOCK
from src.python.core.infra.symbol_spec import get_symbol_spec
from src.python.utils.logger import log, log_error
from src.python.utils.exception_handler import safe_guard
from src.python.core.broker.circuit_breaker import circuit_breaker
from src.python.core.infra import ftmo_request_budget as _request_budget

# Biến lưu thời gian gửi lệnh cuối cùng.
# VÌ SAO CẦN: Khoá (magic, symbol, comment) giúp phân tách rate-limit:
# - Tránh block nhầm khi nhiều chiến lược có tín hiệu cùng lúc (khác magic).
# - Tránh block nhầm khi một chiến lược có nhiều setup kích hoạt sát nhau (cùng magic, khác comment).
# Từ đó chỉ chặn đúng trường hợp một setup bị kẹt vòng lặp gửi liên tục (spam).
_last_order_send_time: Dict[Tuple[Any, str, str], float] = {}


# LƯU Ý THREAD-SAFETY: thư viện MetaTrader5 dùng chung 1 kênh IPC cho toàn process
# và KHÔNG thread-safe. Toàn bộ hàm mt5.* đã được bọc MT5_API_LOCK (RLock) tại
# config.py (import sớm nhất). Bridge giữ lock này qua các CẶP call cần atomic
# (vd: order_send + last_error) để tránh thread khác chen giữa.

# Mã lỗi MT5 KHÔNG phải sự cố thoáng qua — thử lại bao nhiêu lần cũng vô ích vì
# nguyên nhân nằm ở cấu hình/trạng thái terminal, không ở đường truyền.
#   -6  AUTHORIZATION_FAILED  sai tài khoản/mật khẩu/server, hoặc terminal đang
#                             đăng nhập tài khoản khác
#   -2  INVALID_PARAMS        tham số initialize() sai (path/login)
#   -3  NO_MEMORY
_FATAL_ERROR_CODES = {-2, -3, -6}

_RECONNECT_MAX_ATTEMPTS = 8        # 8 lần với backoff -> tổng ~63s chờ
_RECONNECT_INITIAL_DELAY = 0.5         # giây; nhân đôi mỗi lần, trần 16s


# Các vòng HÂM NÓNG lịch sử, tính bằng giây chờ trước mỗi lần thử lại.
#
# Vì sao cần chờ LÂU hơn `copy_rates_retry` (0,3s · 1,0s): hai việc khác nhau. Bên
# kia xử lý terminal CHỚP TẮT khi đã có sẵn lịch sử — vài trăm mili giây là đủ. Ở
# đây terminal phải TẢI lịch sử từ server lần đầu, và đó là việc mất vài giây.
_HISTORY_WARMUP_WAITS = (1.0, 3.0, 5.0)


def _prime_symbols() -> tuple:
    """Đưa mọi công cụ vào Market Watch VÀ ép terminal tải lịch sử về.

    Trả `(số công cụ có nến, danh sách công cụ chưa có nến)`.

    HAI KHÁC BIỆT SO VỚI BẢN XAUUSD
    ================================
    1. NHIỀU CÔNG CỤ. Bản gốc gọi `mt5.symbol_select(SYMBOL, True)` — đúng với hệ
       MỘT tài sản. Ở đây `SYMBOL = SYMBOLS[0]` chỉ là công cụ đầu bảng chữ cái,
       còn danh mục chạy trên 27 công cụ. Chọn một rồi coi là xong nghĩa là 26 công
       cụ còn lại không ở trong Market Watch.

    2. PHẢI ÉP TẢI LỊCH SỬ, KHÔNG CHỈ CHỌN. `symbol_select` đưa công cụ vào Market
       Watch nhưng KHÔNG kích hoạt tải nến. Chỉ `copy_rates_from_pos` mới làm, và
       lần gọi đầu tiên khởi động một tiến trình tải BẤT ĐỒNG BỘ rồi trả về RỖNG.

       Đây là nguyên nhân thật của sự cố VPS ngày 16/08/2026. Nhật ký:

           ⚠️ [FX-M1] fetch EURUSD (copy_rates_from_pos trả về 0/1 bar,
              thử lại 2 lần đều hỏng)

       `mt5_bars.load_m1` ĐÃ gọi `symbol_select` trước khi fetch, và `copy_rates_retry`
       ĐÃ thử lại hai lần trong 1,3 giây — vẫn 0 nến. Không phải chớp tắt: terminal
       mới cài trên VPS chưa có lịch sử, và 1,3 giây không đủ để tải xong.

    HÂM NÓNG MỘT LẦN LÚC KHỞI ĐỘNG, KHÔNG PHẢI MỖI CHU KỲ
    ======================================================
    Chờ tới 9 giây là chấp nhận được ở `init_mt5()` (chạy đúng một lần, và người vận
    hành đang nhìn màn hình chờ). Đưa nó vào vòng lặp 5 giây thì mỗi chu kỳ đều ngủ,
    và các cổng rủi ro chạy trễ theo.

    KHÔNG fail-closed: một công cụ thiếu lịch sử KHÔNG được làm hỏng cả kết nối — 26
    chân còn lại vẫn chạy đúng. Nhưng phải NÓI TO đúng những công cụ nào, vì mỗi công
    cụ thiếu là một nhóm chân âm thầm tính tín hiệu trên parquet lịch sử.
    """
    import time as _time

    from src.python.core.config import SYMBOLS

    symbols = list(SYMBOLS or ((SYMBOL,) if SYMBOL else ()))
    if not symbols:
        return 0, []

    tf = getattr(mt5, "TIMEFRAME_M1", 1)

    def _has_bars(sym: str) -> bool:
        """Một lượt thăm dò. CHÍNH lượt này ép terminal bắt đầu tải lịch sử."""
        try:
            r = mt5.copy_rates_from_pos(sym, tf, 0, 1)
            return r is not None and len(r) > 0
        except Exception:
            return False

    for sym in symbols:
        try:
            mt5.symbol_select(sym, True)
        except Exception as e:
            log_error(f"Lỗi symbol_select({sym}): {e}")

    pending = [s for s in symbols if not _has_bars(s)]
    for waited in _HISTORY_WARMUP_WAITS:
        if not pending:
            break
        _time.sleep(waited)
        pending = [s for s in pending if not _has_bars(s)]

    ready = len(symbols) - len(pending)
    if pending:
        log_error(
            f"⚠️ {len(pending)}/{len(symbols)} công cụ CHƯA CÓ LỊCH SỬ M1 sau "
            f"{sum(_HISTORY_WARMUP_WAITS):.0f}s hâm nóng: "
            f"{', '.join(pending[:10])}" + (" …" if len(pending) > 10 else "")
            + " — các chân trên chúng sẽ tính tín hiệu bằng PARQUET LỊCH SỬ, không "
              "phải giá hiện tại. Mở biểu đồ M1 của chúng trong terminal để ép tải.")
    else:
        log(f"🔌 {ready}/{len(symbols)} công cụ đã sẵn lịch sử M1")
    return ready, pending


def _last_error_code() -> int:
    try:
        return int(mt5.last_error()[0])
    except Exception:
        return 0


@safe_guard(fallback=False, alert_email=True, context_name="mt5_bridge.init_mt5")
def init_mt5() -> bool:
    """Khởi tạo kết nối MetaTrader 5. Backoff luỹ thừa, dừng sớm khi lỗi cố định.

    Xem `reconnect_mt5()` cho lý do đầy đủ — cùng một lớp lỗi, xử lý cùng một cách.
    """
    if sys.version_info >= (3, 12):
        log(f"⚠️ CẢNH BÁO – MetaTrader5 chỉ có bản cho Python <= 3.11; bạn đang chạy {sys.version.split()[0]}")
        
    time.sleep(0.5)
    delay = _RECONNECT_INITIAL_DELAY
    for attempt in range(1, _RECONNECT_MAX_ATTEMPTS + 1):
        initialized = False
        init_kwargs = {}
        if MT5_PATH:
            init_kwargs["path"] = MT5_PATH
            
        # Prioritize login using credentials if configured in .env
        if LOGIN and PASSWORD and SERVER:
            init_kwargs.update({"server": SERVER, "login": int(LOGIN), "password": PASSWORD})
            try:
                if mt5.initialize(**init_kwargs):
                    # Check if the terminal is logged in to the correct account
                    acc = mt5.account_info()
                    if acc is not None and acc.login == int(LOGIN):
                        initialized = True
                        if attempt == 1:
                            pass # log("🔌 Kết nối thành công bằng thông tin đăng nhập")
                        else:
                            pass # log(f"🔌 Kết nối thành công bằng thông tin đăng nhập (lần thử {attempt}/{_RECONNECT_MAX_ATTEMPTS})")
                    else:
                        # Force login explicitly using mt5.login()
                        if mt5.login(login=int(LOGIN), password=PASSWORD, server=SERVER):
                            initialized = True
                            if attempt == 1:
                                log(f"🔌 Đã đăng nhập tài khoản MT5 {LOGIN} qua mt5.login()")
                            else:
                                log(f"🔌 Đã đăng nhập tài khoản MT5 {LOGIN} qua mt5.login() (lần thử {attempt}/{_RECONNECT_MAX_ATTEMPTS})")
                        else:
                            log(f"❌ Đăng nhập tài khoản MT5 {LOGIN} qua mt5.login() thất bại (lần thử {attempt}/{_RECONNECT_MAX_ATTEMPTS}, lỗi: {mt5.last_error()})")
            except Exception as e:
                log(f"❌ Ngoại lệ khi khởi tạo phiên bằng thông tin đăng nhập: {e}")
        else:
            # Fallback to default active session
            try:
                if mt5.initialize(**init_kwargs):
                    initialized = True
                    if attempt == 1:
                        pass # log("🔌 Kết nối thành công bằng phiên đang hoạt động sẵn")
                    else:
                        pass # log(f"🔌 Kết nối thành công bằng phiên đang hoạt động sẵn (lần thử {attempt}/{_RECONNECT_MAX_ATTEMPTS})")
            except Exception as e:
                log(f"❌ Ngoại lệ khi khởi tạo phiên đang hoạt động: {e}")
                    
        if initialized:
            _prime_symbols()
            circuit_breaker.record_success(source="connection")
            return True

        code = _last_error_code()
        if code in _FATAL_ERROR_CODES:
            log_error(f"❌ Kết nối MT5 DỪNG ở lần {attempt}: {mt5.last_error()} — lỗi cố định "
                      f"(cấu hình/đăng nhập), thử lại không giải quyết được.")
            return False
        if attempt < _RECONNECT_MAX_ATTEMPTS:
            log(f"🔄 Lần thử kết nối MT5 {attempt}/{_RECONNECT_MAX_ATTEMPTS} thất bại "
                f"({mt5.last_error()}). Thử lại sau {delay:.1f}s...")
            time.sleep(delay)
            delay = min(delay * 2, 16.0)

    log_error(f"❌ Lỗi: Không thể kết nối MT5 sau {_RECONNECT_MAX_ATTEMPTS} lần thử.")
    return False

@safe_guard(fallback=False, alert_email=True, context_name="mt5_bridge.reconnect_mt5")
def reconnect_mt5(symbol: str = None) -> bool:
    """Khôi phục kết nối IPC tới MT5. Backoff luỹ thừa, dừng sớm khi lỗi cố định.

    VẤN ĐỀ VÀ KIẾN TRÚC:
    1. Độ trễ (delay) cần đủ dài cho các sự cố thực tế (ví dụ: MT5 khởi động lại, 
       VPS đổi mạng, sàn bảo trì) vì chúng có thể kéo dài từ vài chục giây đến vài phút. 
       Do đó, sử dụng backoff luỹ thừa tổng cộng khoảng 63s.
    2. Với các lỗi cố định (ví dụ sai tài khoản/mật khẩu), việc thử lại nhiều lần là vô ích 
       và chỉ tạo ra log thừa, làm chậm quá trình vận hành. 
    Nguyên tắc: Kiên nhẫn với lỗi thoáng qua, dứt khoát với lỗi cố định.
    """
    sym = symbol if symbol is not None else SYMBOL
    time.sleep(0.5)
    delay = _RECONNECT_INITIAL_DELAY
    for attempt in range(1, _RECONNECT_MAX_ATTEMPTS + 1):
        ok = False
        init_kwargs = {}
        if MT5_PATH:
            init_kwargs["path"] = MT5_PATH
            
        # Prioritize login using credentials if configured in .env
        if LOGIN and PASSWORD and SERVER:
            init_kwargs.update({"server": SERVER, "login": int(LOGIN), "password": PASSWORD})
            try:
                if mt5.initialize(**init_kwargs):
                    # Check if the terminal is logged in to the correct account
                    acc = mt5.account_info()
                    if acc is not None and acc.login == int(LOGIN):
                        ok = True
                        if attempt == 1:
                            log("🔌 Kết nối lại thành công bằng thông tin đăng nhập")
                        else:
                            log(f"🔌 Kết nối lại thành công bằng thông tin đăng nhập (lần thử {attempt}/{_RECONNECT_MAX_ATTEMPTS})")
                    else:
                        # Force login explicitly using mt5.login()
                        if mt5.login(login=int(LOGIN), password=PASSWORD, server=SERVER):
                            ok = True
                            if attempt == 1:
                                log(f"🔌 Reconnect: Đã đăng nhập tài khoản MT5 {LOGIN} qua mt5.login()")
                            else:
                                log(f"🔌 Reconnect: Đã đăng nhập tài khoản MT5 {LOGIN} qua mt5.login() (lần thử {attempt}/{_RECONNECT_MAX_ATTEMPTS})")
                        else:
                            log(f"❌ Reconnect: Đăng nhập tài khoản MT5 {LOGIN} thất bại (lần thử {attempt}/{_RECONNECT_MAX_ATTEMPTS}, lỗi: {mt5.last_error()})")
            except Exception as e:
                log(f"❌ Reconnect: ngoại lệ thông tin đăng nhập – {e}")
        else:
            # Fallback to default active session
            try:
                ok = mt5.initialize(**init_kwargs)
                if ok:
                    if attempt == 1:
                        log("🔌 Kết nối lại thành công bằng phiên đang hoạt động sẵn")
                    else:
                        log(f"🔌 Kết nối lại thành công bằng phiên đang hoạt động sẵn (lần thử {attempt}/{_RECONNECT_MAX_ATTEMPTS})")
            except Exception as e:
                log(f"❌ Reconnect: ngoại lệ initialize() – {e}")
                
        if ok:
            try:
                mt5.symbol_select(sym, True)
            except Exception as e:
                log_error(f"Lỗi symbol_select({sym}): {e}")
            try:
                # Spec broker có thể đổi giữa 2 phiên kết nối; xoá cache để
                # get_symbol_spec build lại từ terminal mới (sửa ngày 16/07/2026).
                from src.python.core.infra import symbol_spec
                symbol_spec.invalidate()
            except Exception:
                pass
            circuit_breaker.record_success(source="connection")
            return True
            
        code = _last_error_code()
        if code in _FATAL_ERROR_CODES:
            log_error(f"❌ Kết nối lại MT5 DỪNG ở lần {attempt}: {mt5.last_error()} — "
                      f"lỗi cố định (cấu hình/đăng nhập), thử lại không giải quyết được. "
                      f"Cần người vận hành kiểm tra terminal/thông tin đăng nhập.")
            return False
        if attempt < _RECONNECT_MAX_ATTEMPTS:
            log(f"🔄 Lần thử kết nối lại MT5 {attempt}/{_RECONNECT_MAX_ATTEMPTS} thất bại "
                f"({mt5.last_error()}). Thử lại sau {delay:.1f}s...")
            time.sleep(delay)
            delay = min(delay * 2, 16.0)

    log(f"❌ Kết nối lại thất bại sau {_RECONNECT_MAX_ATTEMPTS} lần thử – {mt5.last_error()}")
    return False

_mismatch_times: list = []
_mismatch_surrender: bool = False
# Khóa bảo vệ thread-safety cho check_mt5_health().
# VÌ SAO CẦN: Hàm này được gọi đồng thời từ nhiều thread (engine chính và các
# worker thread của giao diện). Các thao tác đọc-sửa-ghi trên cấu trúc dữ liệu
# _mismatch_times và _mismatch_surrender cần được bảo vệ để tránh mất cập nhật
# (lost update) khi nhiều thread cùng phát hiện mismatch một lúc.
_mismatch_lock = threading.Lock()


@safe_guard(fallback=False, alert_email=True, context_name="mt5_bridge.check_mt5_health")
def check_mt5_health(symbol: str = None) -> bool:
    """Check if IPC terminal info and symbol info are healthy. Reconnect automatically if disconnected."""
    sym = symbol if symbol is not None else SYMBOL
    info = mt5.terminal_info()
    
    # 1. If IPC connection is dead, trigger reconnect
    if info is None:
        log("🔌 Mất kết nối IPC MT5! Đang tự động kết nối lại...")
        return reconnect_mt5(sym)
        
    # 2. If logged into the wrong account (or not logged in), trigger reconnect to force switch.
    # VẤN ĐỀ: Log vận hành 18/07 (22:00-22:12) ghi nhận terminal bị user đăng nhập tài khoản KHÁC 
    # (vd demo mới) -> bot cướp lại login vô hạn -> IPC gãy liên hồi.
    # XỬ LÝ: Sau số lần vượt ngưỡng trong 10 phút, NGỪNG tranh chấp và cảnh báo rõ ràng.
    if LOGIN:
        acc = mt5.account_info()
        if acc is None or acc.login != int(LOGIN):
            current_login = acc.login if acc is not None else "None"
            import time as _t
            global _mismatch_times, _mismatch_surrender
            now = _t.monotonic()
            with _mismatch_lock:
                _mismatch_times = [x for x in _mismatch_times if now - x < 600] + [now]
                surrendered = _mismatch_surrender
                if not surrendered and len(_mismatch_times) >= 4:
                    _mismatch_surrender = True
                    just_surrendered = True
                else:
                    just_surrendered = False
            if surrendered:
                return False                      # da nhuong quyen — khong danh nhau nua
            if just_surrendered:
                msg = (f"Terminal MT5 liên tục bị đổi sang tài khoản {current_login} "
                       f"(config .env = {LOGIN}). NGỪNG tự động giành lại để tránh vòng lặp. "
                       f"Nếu {current_login} là tài khoản MỚI của bạn: cập nhật MT5_LOGIN/"
                       f"MT5_PASSWORD/MT5_SERVER trong .env rồi restart engine.")
                log(f"⛔ {msg}")
                try:
                    from src.python.utils.alerts import send_alert
                    html = (f"<b>Phát hiện xung đột tài khoản MT5!</b><br><br>"
                            f"Terminal MT5 liên tục bị đổi sang tài khoản <b>{current_login}</b> (cấu hình hiện tại là {LOGIN}).<br>"
                            f"Hệ thống đã ngừng tự động kết nối lại để tránh vòng lặp lỗi.<br><br>"
                            f"<i>Cách xử lý:</i> Nếu {current_login} là tài khoản mới, hãy cập nhật thông tin trong file <code>.env</code> và khởi động lại bot.")
                    send_alert("account_mismatch", f"⛔ [{BOT_NAME}] Xung đột tài khoản MT5", msg, body_html=html)
                except Exception:
                    pass
                return False
            log(f"🔌 Terminal MT5 đăng nhập sai tài khoản ({current_login} vs {LOGIN}). Đang tự động kết nối lại...")
            return reconnect_mt5(sym)
        else:
            with _mismatch_lock:
                _mismatch_times = []
                _mismatch_surrender = False
        
    # 3. If IPC is alive but terminal has no connection to broker server,
    # return False but DO NOT trigger reconnect immediately.
    # This gives MT5 terminal time to establish connection without being interrupted by login loops.
    if not info.connected:
        return False
        
    # 4. Check if symbol is selected
    sym_info = mt5.symbol_info(sym)
    if sym_info is None:
        log(f"🔌 Không tìm thấy hoặc chưa chọn symbol {sym}! Đang tự động kết nối lại...")
        return reconnect_mt5(sym)
        
    return True

# ==============================================================================
# PURE API EXECUTION FUNCTIONS (100% API TRADING - REPLACING EA/CSV)
# ==============================================================================



def _order_send_compat(request: Dict[str, Any]):
    """
    Gửi order tương thích đa build terminal:
    - Terminal build >= 6001 (07/2026) yêu cầu truyền field dạng keyword arguments
      (mt5.order_send(**request)); dạng dict positional cũ trả về None với
      last_error (-2, 'Unnamed arguments not allowed').
    - Build cũ hơn vẫn nhận dạng dict positional -> fallback khi kwargs bị từ chối parse.
    Trả về (result, last_error_khi_None). Phải gọi bên trong MT5_API_LOCK.
    """
    result = mt5.order_send(**request)
    if result is not None:
        return result, None
    err = mt5.last_error()
    if err and err[0] == -2:
        # Package/terminal cũ không nhận kwargs -> thử lại dạng dict positional
        result = mt5.order_send(request)
        if result is not None:
            return result, None
        err = mt5.last_error()
    return None, err

def _position_already_exists(request: Dict[str, Any], wall_t0: float) -> bool:
    """Có vị thế nào của đúng (magic, symbol) vừa sinh SAU `wall_t0` không?

    Dùng để phân biệt hai nghĩa của `order_send() -> None`:
      * lệnh chưa bao giờ tới server  -> retry là đúng
      * lệnh ĐÃ khớp, chỉ mất phản hồi -> retry sẽ NHÂN ĐÔI vị thế

    Fail-CLOSED có chủ đích: nếu không đọc được `positions_get()` thì trả `True`
    (= "coi như đã có") để KHÔNG retry. Giữa hai cách hỏng, "bỏ lỡ một lệnh" rẻ
    hơn nhiều so với "mở gấp đôi rủi ro một tín hiệu mà không lớp exposure nào
    đếm được" — ticket thứ hai còn không nằm trong state chiến lược nên không
    được BE/trailing/journal.
    """
    if request.get("position"):        # lệnh đóng/sửa, không phải mở mới
        return False
    try:
        with MT5_API_LOCK:
            positions = mt5.positions_get(symbol=request.get("symbol", SYMBOL))
    except Exception as exc:
        log_error(f"❌ [API EXEC] không dò được vị thế sau order_send None: {exc}")
        return True
    if positions is None:
        return True
    magic = request.get("magic")
    for p in positions:
        # `time_msc` (epoch ms) chính xác hơn `time` (epoch giây) cho cửa sổ vài
        # trăm mili-giây của một lần gửi lệnh.
        t = getattr(p, "time_msc", None)
        t_sec = (float(t) / 1000.0) if t else float(getattr(p, "time", 0) or 0)
        if p.magic == magic and t_sec >= wall_t0 - 1.0:
            return True
    return False


def _alert_fatal_rejection(result, request) -> None:
    """Email báo broker TỪ CHỐI VĨNH VIỄN một lệnh. Fail-soft tuyệt đối.

    Tách khỏi `order_send_api()` 07/08 vì bánh cóc độ phức tạp chặn — đây
    thuần là dựng HTML thông báo, không thuộc logic gửi lệnh.
    """
    try:
        from src.python.utils.alerts import send_alert
        msg_text = f"Lệnh bị từ chối.\nretcode={result.retcode}: {result.comment}\nrequest={request}"
        html = (f"<b>Broker TỪ CHỐI lệnh (FATAL ERROR)</b><br><br>"
                f"<table style='width: 100%; border-collapse: collapse; margin: 12px 0;'>"
                f"<tr><td style='padding: 8px; border: 1px solid #dee2e6;'><b>Mã lỗi (retcode)</b></td><td style='padding: 8px; border: 1px solid #dee2e6;'><b style='color: #dc3545;'>{result.retcode}</b></td></tr>"
                f"<tr style='background-color: #f8f9fa;'><td style='padding: 8px; border: 1px solid #dee2e6;'><b>Lý do</b></td><td style='padding: 8px; border: 1px solid #dee2e6;'>{result.comment}</td></tr>"
                f"<tr><td style='padding: 8px; border: 1px solid #dee2e6;'><b>Request</b></td><td style='padding: 8px; border: 1px solid #dee2e6;'><code>{request}</code></td></tr>"
                f"</table>")
        send_alert(f"order_rejected_{result.retcode}",
                   f"[{BOT_NAME}] Broker TỪ CHỐI lệnh (retcode={result.retcode})",
                   msg_text, body_html=html)
    except Exception:
        pass

def _check_request_budget(kind: str) -> bool:
    """Còn ngân sách request hôm nay không? `False` = KHÔNG được gửi.

    NGÂN SÁCH REQUEST FTMO (nối 07/08). Tài liệu §II.2: FTMO giới hạn 2.000
    request/ngày và xếp "Hyperactive Order Modification" vào nhóm CẤM. Trước
    hôm nay hệ thống KHÔNG có bộ đếm nào.

    PHÂN LOẠI được quyết định ở nơi gọi, vì chỉ ở đó mới có `is_entry` để phân
    biệt mở lệnh mới với thao tác trên vị thế đã có. Mọi thao tác KHÔNG phải
    entry được xếp là BẢO VỆ — nhóm không bao giờ bị chặn. Xếp rộng như vậy có
    chủ đích: nhầm một lệnh nới TP thành "bảo vệ" chỉ tốn vài request, còn nhầm
    một lệnh ĐÓNG thành "quản lý" rồi chặn nó là một cách mất tài khoản.

    Tách khỏi `order_send_api()` vì bánh cóc độ phức tạp chặn — nâng trần là
    cách sai. Khối này vốn là một cổng độc lập nên tách ra đọc rõ hơn.
    """
    budget = _request_budget.can_send(kind)
    if budget.allowed:
        return True
    log_error(f"🛑 [REQUEST BUDGET] chặn lệnh: {budget.reason}")
    _request_budget.record_denied()
    return False


@safe_guard(fallback=None, alert_email=True, context_name="mt5_bridge.order_send_api")
def _halt_and_reject(msg: str) -> None:
    """Chặn ngày giao dịch vì một hạn mức tiền-giao-dịch bị vượt, rồi từ chối lệnh.

    Hai chốt chặn (tần suất gửi lệnh, trần lot mỗi lệnh) đều báo hiệu LỖI LOGIC
    của chiến lược chứ không phải điều kiện thị trường, nên phản ứng đúng là
    dừng ngày chứ không chỉ bỏ một lệnh. Gộp về đây để hai chốt không bao giờ
    phản ứng khác nhau.
    """
    log_error(f"🛑 {msg}")
    try:
        from src.python.core.infra import risk_guard
        risk_guard.halt_day(msg)
    except Exception as e:
        log_error(f"❌ Lỗi gọi risk_guard.halt_day: {e}")
    return None


def _check_simulation_flag_cleared() -> None:
    """Cờ mô phỏng phải TẮT trước mỗi lệnh gửi ra broker thật.

    Vị thế ảo đi qua `SimBridge.order_send_api()`, nên tới được cầu nối này
    nghĩa là một lệnh TIỀN THẬT sắp gửi đi. Cờ còn bật tức nó đã rò khỏi một
    khối `with simulating(...)` (thường do exception thoát ra), và mọi thứ đo
    từ lệnh này — log, email, journal — sẽ mang nhãn mô phỏng: một vị thế tiền
    thật trông như lệnh giấy.

    Guard tự xoá cờ và kêu to nhưng KHÔNG chặn lệnh: lỗi ở lớp quan sát không
    được phép làm hỏng luồng giao dịch.
    """
    try:
        from src.python.core.virtual import simulation_context as _simctx
        _simctx.assert_not_simulating("mt5_bridge.order_send_api")
    except Exception:
        pass


def order_send_api(request: Dict[str, Any], max_retries: int = 3) -> Optional[Any]:
    """
    Gửi lệnh trực tiếp ra máy chủ sàn qua Pure API mt5.order_send() được bảo vệ bởi Circuit Breaker.
    Tự động retry với Exponential Backoff khi gặp Requote hoặc Price Changed.
    """
    _check_simulation_flag_cleared()

    # Pre-trade Risk Limit checks (phê duyệt 18/07)
    action = request.get("action")
    is_deal_or_pending = action in (mt5.TRADE_ACTION_DEAL, mt5.TRADE_ACTION_PENDING)
    is_entry = is_deal_or_pending and (not request.get("position"))
    
    # 1. Tần suất gửi lệnh tối đa 1 lệnh mỗi 5 giây MỖI (magic, symbol) — chặn
    # spam thật (1 chiến lược bị lỗi vòng lặp gửi liên tục), không chặn nhầm 2 chiến
    # lược khác nhau cùng có tín hiệu trong cùng chu kỳ.
    if is_entry:
        # VÌ SAO CẦN KHÓA THEO (magic, symbol, comment):
        # MỘT chiến lược có NHIỀU SETUP dùng CHUNG magic có thể gửi lệnh sát nhau.
        # Ví dụ chiến lược swing_don: setup D55 và D20 nổ cùng bar, gửi 2 lệnh hợp lệ
        # cách nhau vài mili-giây với chung magic và symbol, chỉ khác comment.
        # Nếu khóa thiếu comment, lệnh thứ 2 sẽ bị tính là spam và gọi halt_day() toàn tài khoản.
        # Comment phân biệt được các setup nên việc đưa comment vào khóa giúp giữ lại
        # tính năng phát hiện spam (gửi lặp cùng một lệnh).
        key = (request.get("magic"), request.get("symbol", SYMBOL),
               request.get("comment", ""))
        now = time.time()
        last_ts = _last_order_send_time.get(key, 0.0)
        if now - last_ts < 5.0:
            msg = (f"Pre-Trade Risk Limit: Tần suất gửi lệnh quá nhanh cho magic="
                   f"{key[0]} symbol={key[1]} ({now - last_ts:.2f}s < 5s)!")
            return _halt_and_reject(msg)

    # 2. Quy mô lệnh đơn tối đa (chặn lỗi logic sizing quá to)
    #
    # Quy định chỉ kiểm tra trần khối lượng (Lot size) đối với lệnh ENTRY.
    # VẤN ĐỀ: Nếu áp dụng trần Lot size cho cả lệnh ĐÓNG vị thế (ví dụ cắt lỗ khẩn cấp), 
    # các vị thế lớn sẽ không thể đóng được, khiến kill switch rơi vào vòng lặp vô hạn 
    # và vị thế trôi tự do. Trần Lot size chỉ được thiết kế để chặn lỗi logic SIZING đầu vào.
    volume = request.get("volume")
    if volume is not None and is_entry:
        try:
            from src.python.core.config import INP_MAX_LOT_PER_ORDER
        except ImportError:
            INP_MAX_LOT_PER_ORDER = 1.0
        if float(volume) > INP_MAX_LOT_PER_ORDER:
            msg = f"Pre-Trade Risk Limit: Lot size {volume} vuot muc cho phep {INP_MAX_LOT_PER_ORDER}!"
            return _halt_and_reject(msg)

    # VÌ SAO CẦN PHÂN BIỆT LỆNH BẢO VỆ VỚI CIRCUIT BREAKER:
    # Circuit breaker dùng chung cho mọi lệnh. Nếu một lỗi trên lệnh ENTRY mở breaker,
    # việc chặn luôn các lệnh BẢO VỆ (đóng vị thế, dời SL) sẽ rất nguy hiểm.
    # Vì thế lệnh KHÔNG phải entry được phép BỎ QUA trạng thái OPEN của breaker 
    # nhưng vẫn cập nhật trạng thái lỗi thành công/thất bại để theo dõi sức khỏe broker.
    # Phân loại: xem `_check_request_budget()` cho lý do chọn nhóm.
    _budget_kind = (_request_budget.KIND_ENTRY if is_entry
                    else _request_budget.KIND_PROTECTIVE)
    if not _check_request_budget(_budget_kind):
        return None

    can_exec, reason = circuit_breaker.can_execute()
    if not can_exec:
        if is_entry:
            log_error(f"🛑 [API EXEC blocked] {reason}")
            return None
        log_error(f"⚠️ [API EXEC] Circuit breaker đang chặn nhưng đây là lệnh BẢO VỆ vị thế "
                  f"(đóng/sửa SL-TP) — vẫn cho phép gửi, KHÔNG chặn protective exit. Lý do breaker: {reason}")

    if not check_mt5_health(request.get("symbol", SYMBOL)):
        return None

    if is_entry:
        _last_order_send_time[key] = time.time()

    # Mốc WALL-CLOCK riêng: `time_msc` của vị thế broker là epoch ms thật,
    # không so được với `monotonic()`. Dùng cho phép dò chống nhân đôi lệnh.
    _order_send_wall_t0 = time.time()
    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            # Breaker có thể đã OPEN giữa các attempt -> không retry vô ích
            can_exec, reason = circuit_breaker.can_execute()
            if not can_exec:
                log_error(f"🛑 [API EXEC blocked] {reason}")
                return None
        # Giữ lock qua cả cặp order_send + last_error để last_error không bị
        # thread khác ghi đè giữa 2 call (IPC dùng chung toàn process).
        with MT5_API_LOCK:
            result, err = _order_send_compat(request)
        # Đếm NGAY sau khi request rời tiến trình, KHÔNG chờ kết quả: FTMO đếm
        # request GỬI LÊN, không đếm request thành công. Mỗi vòng thử lại vì thế
        # cũng tính — và đó chính là một trong ba nguồn phình mà bộ đếm sinh ra
        # để phát hiện.
        _request_budget.record(_budget_kind)
        if result is None:
            log_error(f"❌ [API EXEC] order_send() trả về None (attempt {attempt}/{max_retries}): {err}")
            circuit_breaker.record_failure(10031, str(err))
            # VẤN ĐỀ VÀ KIẾN TRÚC: `None` KHÔNG có nghĩa "lệnh không được gửi".
            # MT5 trả None khi IPC/terminal timeout. Điều này có thể xảy ra khi lệnh ĐÃ tới 
            # server và ĐÃ khớp nhưng bị mất phản hồi. Nếu retry mù quáng sẽ dẫn đến rủi ro 
            # nhân đôi vị thế, và vị thế thừa sẽ bị mồ côi (không được trailing stop/BE).
            # GIẢI PHÁP: Dò trước khi retry. Nếu đã có vị thế mới của đúng (magic, symbol)
            # sinh ra sau thời điểm bắt đầu gửi thì coi như ĐÃ THÀNH CÔNG, dừng ngay lập tức.
            if _position_already_exists(request, _order_send_wall_t0):
                log_error("🛑 [API EXEC] order_send trả None NHƯNG vị thế đã tồn tại "
                          "trên broker — KHÔNG retry (chống nhân đôi lệnh).")
                return None
            time.sleep(0.2 * attempt)
            continue

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            log(f"🎯 [API EXEC DONE] Lệnh #{result.order} | Symbol={request.get('symbol')} | Lot={request.get('volume')} | Giá={result.price} | SL={request.get('sl')} | TP={request.get('tp')}")
            circuit_breaker.record_success()
            return result

        # Lỗi từ broker -> kiểm tra xem có được phép retry không
        retriable = circuit_breaker.record_failure(result.retcode, result.comment)
        if not retriable:
            log_error(f"🛑 [API EXEC FATAL] Lệnh bị từ chối vĩnh viễn (ticket #{result.order}, retcode={result.retcode}): {result.comment}")
            _alert_fatal_rejection(result, request)
            return result

        if attempt < max_retries:
            delay = 0.25 * (2 ** (attempt - 1))  # Exponential backoff: 0.25s, 0.5s...
            log(f"🔄 [API EXEC REQUOTE] Gửi lại lệnh sau {delay:.2f}s (retcode={result.retcode}: {result.comment})...")
            time.sleep(delay)
            # Cập nhật lại giá ask/bid mới nhất trước khi gửi lại
            tick = mt5.symbol_info_tick(request.get("symbol", SYMBOL))
            if tick and request.get("action") == mt5.TRADE_ACTION_DEAL:
                if request.get("type") == mt5.ORDER_TYPE_BUY:
                    request["price"] = float(tick.ask)
                elif request.get("type") == mt5.ORDER_TYPE_SELL:
                    request["price"] = float(tick.bid)
        else:
            log_error(f"❌ [API EXEC FAILED] Hết số lần thử lại ({max_retries} lần) cho lệnh retcode={result.retcode}: {result.comment}")
            return result
    return None

@safe_guard(fallback=[], alert_email=True, context_name="mt5_bridge.get_positions_api")
def get_positions_api(magic: Optional[int] = None, symbol: str = SYMBOL) -> List[Any]:
    """Lấy danh sách các vị thế đang mở (open positions) qua Pure API."""
    if not check_mt5_health(symbol):
        return []
    try:
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            return []
        if magic is not None:
            return [p for p in positions if p.magic == magic]
        return list(positions)
    except Exception as e:
        log_error(f"❌ Ngoại lệ get_positions_api: {e}")
        return []


def get_positions_api_strict(magic: Optional[int] = None, symbol: str = SYMBOL) -> List[Any]:
    """Return broker positions or raise khi broker state cannot be verified.

    An empty list is a valid account state, so reconciliation must distinguish
    it from an MT5/API failure.  The normal polling helper above intentionally
    keeps its resilient fallback; startup reconciliation uses this strict path.
    """
    if not check_mt5_health(symbol):
        raise RuntimeError("MT5 health check failed while reading positions")
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        raise RuntimeError(f"positions_get returned None: {mt5.last_error()}")
    if magic is not None:
        return [p for p in positions if p.magic == magic]
    return list(positions)

@safe_guard(fallback=False, alert_email=True, context_name="mt5_bridge.modify_position_sl_api")
def modify_position_sl_api(ticket: int, new_sl: float, symbol: str = SYMBOL) -> bool:
    """
    Sửa mức Stop Loss của một vị thế đang mở trực tiếp qua Pure API.
    Sử dụng cho cơ chế TP2 Trailing Lock và Breakeven Shield.
    """
    if not check_mt5_health(symbol):
        return False

    # Lấy thông tin vị thế hiện tại để giữ nguyên TP cũ
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        log(f"⚠️ [MODIFY SL] Vị thế #{ticket} không tồn tại hoặc đã đóng.")
        return False
    pos = positions[0]

    # Làm tròn SL + stops/freeze-level qua SymbolSpec (nguồn chân lý duy nhất)
    spec = get_symbol_spec(symbol)
    digits = spec.digits
    point = spec.point
    rounded_sl = spec.round_price(new_sl)

    if abs(pos.sl - rounded_sl) < point:
        return True  # SL đã ở đúng mức yêu cầu, không cần sửa đổi

    # Stops-level / freeze-level compliance: SL mới phải cách giá hiện tại tối thiểu
    # required; vi phạm -> BỎ QUA chu kỳ này (thử lại sau) thay vì ăn retcode 10016
    # làm circuit breaker mở khóa toàn hệ thống.
    tick = mt5.symbol_info_tick(symbol)
    if tick:
        market_price = float(tick.bid) if pos.type == mt5.ORDER_TYPE_BUY else float(tick.ask)
        required = max(spec.min_stop_dist, spec.freeze_dist)
        if required > 0 and abs(market_price - rounded_sl) < required:
            log(f"⚠️ [MODIFY SL SKIP] Ticket #{ticket}: SL {rounded_sl} cách giá {market_price} < stops/freeze level {required:.{digits}f} — thử lại chu kỳ sau.")
            return False

    # VẤN ĐỀ: Gửi kèm `pos.tp` khi đặt lại SLTP là cần thiết để không xóa TP. 
    # Tuy nhiên, nếu giá hiện tại đã ĐI QUA mức TP đó (ví dụ do trượt giá hoặc 
    # TP chưa kịp cập nhật lên broker), việc gửi yêu cầu sẽ bị từ chối (retcode 10013).
    # Hậu quả là lệnh không được dời SL, lợi nhuận không được khóa và circuit breaker mở.
    # XỬ LÝ: Nếu TP không còn hợp lệ, bỏ qua TP trong request để đảm bảo dời được SL. 
    # Việc dời SL khóa lợi nhuận được ưu tiên hơn so với một mức TP quá hạn.
    tp_gui = pos.tp
    if tick and pos.tp:
        _price = float(tick.bid) if pos.type == mt5.ORDER_TYPE_BUY else float(tick.ask)
        _expired = (pos.type == mt5.ORDER_TYPE_BUY and pos.tp <= _price) or                    (pos.type != mt5.ORDER_TYPE_BUY and pos.tp >= _price)
        if _expired:
            tp_gui = 0.0
            log(f"⚠️ [MODIFY SL] #{ticket}: TP {pos.tp} đã bị giá {_price} vượt qua — "
                f"BỎ TP khỏi yêu cầu để dời được SL (gửi kèm sẽ ăn retcode 10013 "
                f"và circuit breaker mở, SL không bao giờ dời được).")

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "symbol": symbol,
        "sl": rounded_sl,
        "tp": tp_gui,
        "magic": pos.magic
    }
    result = order_send_api(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        # Verify: đọc lại vị thế để xác nhận SL thật trên server (không tin request)
        try:
            chk = mt5.positions_get(ticket=ticket)
            if chk and abs(chk[0].sl - rounded_sl) > point:
                log(f"⚠️ [MODIFY SL WARNING] Ticket #{ticket}: server báo DONE nhưng SL đọc lại = {chk[0].sl} != {rounded_sl}")
                return False
        except Exception as _ve:
            # VẤN ĐỀ VÀ KIẾN TRÚC: Nếu lỗi khi đọc lại vị thế để xác minh SL 
            # (ví dụ do IPC hiccup), ta vẫn ưu tiên retcode từ broker và trả về True. 
            # Tuy nhiên, cần ghi log cảnh báo rõ ràng thay vì bỏ qua âm thầm, 
            # để người vận hành biết bước xác minh cục bộ đã thất bại.
            log(f"🔍 [MODIFY SL] Ticket #{ticket}: không đọc lại được vị thế để xác minh SL ({_ve}) "
                f"— coi như DONE dựa trên retcode broker (chưa xác minh lại được).")
        log(f"🎯 [MODIFY SL DONE] Lệnh #{ticket} | SL cũ={pos.sl} → SL mới={rounded_sl}")
        return True
    return False

# VÌ SAO DÙNG fallback=(0, None):
# Nếu dùng `(0, 0)`, khi gặp lỗi broker giữa lúc đóng khẩn cấp, caller (kill switch)
# sẽ tính toán 0 >= 0 là True và lầm tưởng đã đóng sạch vị thế. Từ đó chặn các 
# VẤN ĐỀ VÀ KIẾN TRÚC: Tránh "Deadlock" logic khi Kill Switch.
# Nếu dùng `fallback=(0, 0)`, hệ thống lầm tưởng 0 vị thế là đã đóng thành công và 
# ngừng retry ở các chu kỳ sau. Sử dụng `(0, None)` buộc hệ thống hiểu là 
# "trạng thái không xác định" và cho phép các vòng lặp tiếp theo tiếp tục dọn dẹp.
@safe_guard(fallback=(0, None), alert_email=True, context_name="mt5_bridge.close_all_positions")
def close_all_positions(reason: str = "") -> Tuple[int, Optional[int]]:
    """Đóng SẠCH mọi vị thế (mọi symbol, mọi magic/chiến lược).
    Dùng cho tính năng GUI 'FLATTEN ALL' và Global Kill Switch tự động.
    Trả về (số_đã_đóng, tổng_số)."""
    # VẤN ĐỀ VÀ KIẾN TRÚC: FAIL-OPEN trong công tắc khẩn cấp.
    # `positions_get()` trả None khi có lỗi đọc dữ liệu. Nếu bị gán thành danh sách rỗng, 
    # hệ thống sẽ trả về (0, 0) và ngộ nhận là tài khoản đã phẳng (không còn vị thế).
    # Các luồng cứu hỏa như Kill Switch hoặc FLATTEN ALL sẽ hiểu sai và ngừng cắt lỗ.
    # XỬ LÝ: Khi lỗi đọc, phải báo lỗi rõ ràng và trả total=None để caller thực hiện RETRY.
    _raw = mt5.positions_get()
    if _raw is None:
        log_error("🚨 [CLOSE_ALL] positions_get() trả None (LỖI ĐỌC, không phải "
                  "'không có vị thế') — KHÔNG thể khẳng định đã đóng hết. "
                  "Trả total=None để caller RETRY, không coi là 'đã sạch'.")
        return 0, None
    positions = list(_raw)
    total = len(positions)
    closed = 0
    for p in positions:
        try:
            if close_position_api(int(p.ticket), symbol=p.symbol):
                closed += 1
        except Exception as _e:
            log_error(f"❌ [CLOSE_ALL] ticket #{p.ticket} loi khi dong (bo qua, tiep tuc cac ve khac): {_e}")
    log(f"🚨 [CLOSE_ALL] Da dong {closed}/{total} vi the" + (f" — ly do: {reason}" if reason else ""))
    return closed, total


@safe_guard(fallback=False, alert_email=True, context_name="mt5_bridge.close_position_api")
def close_position_api(ticket: int, volume: Optional[float] = None, symbol: str = SYMBOL) -> bool:
    """
    Đóng một phần (partial close) hoặc toàn bộ vị thế qua Pure API.
    Sử dụng cho cơ chế Fuzzy Exits hoặc chốt lời chủ động khi gia tốc Kalman PnL suy kiệt.
    """
    if not check_mt5_health(symbol):
        return False
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        log(f"⚠️ [CLOSE POS] Vị thế #{ticket} không còn tồn tại.")
        return False
    pos = positions[0]
    close_vol = float(volume) if (volume is not None and volume > 0 and volume < pos.volume) else float(pos.volume)
    
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return False
    # Đóng vị thế BUY -> bán ra ở BID; Đóng vị thế SELL -> mua lại ở ASK
    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    close_price = float(tick.bid) if pos.type == mt5.ORDER_TYPE_BUY else float(tick.ask)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": ticket,
        "symbol": symbol,
        "volume": close_vol,
        "type": close_type,
        "magic": pos.magic,
        "comment": "THE_CHEOPARD_CLOSE",
        "type_filling": get_symbol_spec(symbol).filling_mode,
    }
    result = order_send_api(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        log(f"🎯 [CLOSE POS DONE] Ticket #{ticket} | Vol={close_vol}/{pos.volume} @ {close_price}")
        return True
    return False
