"""engine.py — ĐỘNG CƠ VẬN HÀNH của The Cheopard Forex.

VÌ SAO VIẾT LẠI CHỨ KHÔNG CHÉP TỪ HỆ XAUUSD
============================================
`gui_command_center.py` được KẾ THỪA nguyên vẹn — nó chỉ dùng bảy thứ từ động cơ:

    TradingEngine(log_callback, status_callback)
    .state              từ điển trạng thái mà giao diện đọc
    .start_loop()       TRẢ BOOL — giao diện đọc để biết có bật được nút không
    .stop_loop()
    .is_running         THUỘC TÍNH, không phải phương thức
    .log()  .log_error()
    .update_mt5_status()  làm mới một lượt, chạy trên luồng riêng của giao diện

Bốn chữ ký trên PHẢI khớp đúng những gì `gui_command_center` gọi. Sai một chỗ là
cửa sổ dựng tới nửa chừng rồi văng — và vì `pythonw` không có console nên nó văng
lặng lẽ, đúng dạng "nhấn vào mà không thấy gì".

Engine XAU cài bảy thứ đó cùng vài nghìn dòng logic của hệ vàng: `SYMBOL="XAUUSD"`,
đường ống ML A-F, bộ máy AI hai tầng, hàng chục cổng riêng của vàng. Chép nó sang
đây là kéo cả một hệ khác vào — và mọi con số nó sinh ra sẽ là con số của vàng.

Bản này cài đúng bảy thứ đó, đọc từ nguồn thật của hệ Forex:
    tài khoản, vị thế, spread   ← MetaTrader5 (nếu có)
    danh mục, chiến lược         ← `strategies/registry` + `strategies/portfolio`
    cổng chặn                    ← `ai/news_guard`

⚠️ ĐỘNG CƠ NÀY CHỈ ĐỌC. Nó KHÔNG đặt lệnh, không sửa lệnh, không đóng lệnh. Vòng lặp
chỉ làm mới trạng thái để giao diện hiển thị. Việc đặt lệnh đi qua `execution/`, và
cố ý không có đường nối từ đây sang đó — một bảng điều khiển có nút "vào lệnh" là
cách để một lần trượt tay thành một lệnh thật.
"""
from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.python.core.config import LIVE_ORDERS as _LIVE_ORDERS

REFRESH_SECONDS = 5.0          # nhịp làm mới tài khoản/vị thế/spread — rẻ, đọc MT5

# Nhịp chạy lại backtest danh mục. Đặt 1 giờ chứ không phải 10 phút: đầu vào của nó
# là nến ĐÃ ĐÓNG trên khung M30 trở lên, nên trong 10 phút gần như không có gì đổi —
# chạy lại chỉ tốn 40 giây CPU và thêm một dòng log không mang thông tin mới.
PORTFOLIO_EVERY = 3600.0

# Nhịp dựng KẾ HOẠCH LỆNH. Cùng 1 giờ với backtest danh mục vì cùng phụ thuộc nến
# ĐÃ ĐÓNG khung M30 trở lên — dựng dày hơn chỉ ra cùng một kế hoạch.
PLAN_EVERY = 3600.0

# Nhịp in bảng SPREAD THẬT lên Event Timeline. 30 phút vì spread FX đổi mạnh theo
# giờ — giãn nhiều lần lúc giao ca Á-Âu và quanh tin — nên một mẫu mỗi 30 phút suốt
# tuần mới cho phân phối thật. Đây là số đo dùng để THAY ước lượng chi phí của 21
# cặp chéo, giả định lớn nhất còn lại của cả hệ.
SPREAD_LOG_EVERY = 1800.0

# Cùng một dòng log lặp lại trong khoảng này thì chỉ ghi MỘT lần. Vòng lặp chạy mỗi
# 5 giây, nên một lỗi dai dẳng (mất kết nối, spread giãn) sẽ sinh 720 dòng giống hệt
# mỗi giờ nếu không khử — và chúng nuốt mất mọi dòng có ích trên timeline.
LOG_DEDUP_SECONDS = 300.0

# Số lần MT5 thất bại LIÊN TIẾP trước khi báo ⛔. Nhịp vòng lặp 5 giây → ~15 giây
# ân hạn, đủ cho terminal nối xong tới server sau khi mở.
#
# Vì sao cần: terminal vừa mở trả -6 AUTHORIZATION_FAILED dù thông tin đăng nhập
# ĐÚNG. Đo trên VPS 16/08/2026 — lỗi lúc 09:28:38, kết nối được lúc 09:28:43, cùng
# một cấu hình. Không có ân hạn thì mỗi lần khởi động đều sinh một dòng ⛔ tự khỏi,
# và một cảnh báo thường xuyên sai là cảnh báo sẽ bị bỏ qua lúc nó đúng.
#
# Bản XAUUSD giải quyết cùng chuyện này bằng `mt5_bridge.init_mt5()`: 8 lần thử với
# backoff luỹ thừa (~63 giây). Ở đây không ngủ trong vòng lặp — nhịp 5 giây phải
# giữ cho các cổng rủi ro chạy đúng — nên ân hạn đếm bằng SỐ LẦN.
MT5_FAIL_GRACE = 3


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _log_incident(what: str, exc: BaseException) -> None:
    """Ghi sự cố của callback ra TỆP RIÊNG.

    VÌ SAO PHẢI CÓ: bản đầu bọc mọi lời gọi callback bằng `except Exception: pass`.
    Ý định là "giao diện hỏng thì động cơ vẫn chạy" — nhưng hệ quả là MỌI lỗi biến
    mất không dấu vết, và hai triệu chứng nặng nhất đều sinh ra từ đó:

      · `log_callback` là `print`, gặp chữ tiếng Việt trên console cp1252 thì ném
        UnicodeEncodeError → nuốt → chế độ CLI im hoàn toàn, không một dòng nào.
      · `status_callback` hỏng → nuốt → giao diện KHÔNG BAO GIỜ nhận được state,
        và mọi thẻ hiện N/A trong khi động cơ vẫn đọc dữ liệu bình thường.

    Cả hai đều không có exception, không có log, không có gì để lần ra. Nay lỗi đi
    vào `logs/live/engine_errors.log` — vẫn không làm chết động cơ, nhưng có dấu vết.
    """
    try:
        from src.python.core.config import LIVE_DIR
        f = Path(LIVE_DIR) / "engine_errors.log"
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now(timezone.utc).isoformat()} · {what} · "
                     f"{type(exc).__name__}: {exc}\n")
    except Exception:
        pass                          # đến đây mà còn hỏng thì thôi, đừng làm chết engine


class TradingEngine:
    """Động cơ CHỈ ĐỌC: làm mới trạng thái cho bảng điều khiển.

    `log_callback(msg)` và `status_callback(state)` do giao diện truyền vào. Động cơ
    KHÔNG bao giờ tự đụng vào widget — Tkinter không an toàn đa luồng, nên vòng lặp
    nền chỉ gọi callback và giao diện tự xếp hàng cập nhật.
    """

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None,
                 status_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

        # Chống backtest CHỒNG NHAU. Giao diện gọi `update_mt5_status` trên một luồng
        # riêng ngay lúc dựng cửa sổ (gui_command_center dòng 700), rồi `start_loop`
        # khởi động thêm một vòng lặp nữa — hai luồng cùng vào `_read_portfolio`, mỗi
        # luồng chạy backtest 14 chân mất ~40 giây, và log ra hai dòng "đang làm mới"
        # cùng một giây. Khoá này cho phép ĐÚNG MỘT lượt tại một thời điểm.
        self._portfolio_lock = threading.Lock()
        self._last_portfolio = 0.0        # mốc tính từ lúc XONG, không phải lúc bắt đầu
        self._selected: set = set()       # symbol đã đưa vào Market Watch
        self._last_state: Dict[str, str] = {}   # bộ nhớ cho `_log_change`

        # Bộ nhớ dòng log gần nhất — dùng để KHỬ LẶP, xem `log()`.
        self._last_msg = ""
        self._last_msg_at = 0.0

        # NGỦ ĐÔNG cuối tuần. Pha trước đó đọc TỪ ĐĨA, không phải từ RAM.
        #
        # Lỗi đã sửa 15/08/2026 (hệ XAUUSD báo trước, hệ này mắc y hệt): email "ngủ
        # đông" sáng thứ Bảy luôn tới, email "thức dậy" sáng thứ Hai KHÔNG BAO GIỜ
        # tới. Cờ này phải sống ~45 giờ liên tục từ lúc đóng tới lúc mở lại, mà một
        # lần VPS reboot hay watchdog kill trong quãng đó đưa nó về `None` và nhánh
        # gửi email bị `prev is not None` chặn. Chi tiết ở `market_schedule`.
        self._prev_market_closed: Optional[bool] = None
        self._last_standby_log = 0.0

        # Mốc bắt đầu MẤT kết nối MT5. `None` = đang kết nối bình thường.
        # Email cảnh báo chỉ gửi khi đã mất quá `DISCONNECT_ALERT_MIN` phút: MT5
        # rớt vài giây khi broker đổi máy chủ là chuyện thường, và gửi thư cho mỗi
        # lần chớp như vậy làm người vận hành lọc cả chủ đề vào thùng rác.
        self._disconnected_since: Optional[float] = None

        # ── KẾ HOẠCH LỆNH
        # KHÔNG có cờ `arm_orders` riêng ở đây. Trước 15/08/2026 có bốn công tắc cho
        # cùng một quyết định "có gửi lệnh không" — `arm_orders`, `dry_run`, file
        # `trading_control`, và nút trên giao diện — tức 8 tổ hợp mà chỉ 3 có nghĩa.
        # Năm tổ hợp còn lại là chỗ để bật nhầm. Nay còn HAI, mỗi cái một câu hỏi:
        #
        #     trading_control  "người vận hành CÓ CHO vào lệnh không?"  ← nút RUN/STOP
        #     LIVE_ORDERS      "môi trường này được chạm tiền thật?"    ← .env
        #
        # `dry_run` suy từ `LIVE_ORDERS`, không phải một biến sửa được lúc chạy.
        self.dry_run = not _LIVE_ORDERS
        self._plan_lock = threading.Lock()
        self._last_plan = 0.0
        self._book = None                 # PositionBook, nạp lười
        self._bar_index_cache: Dict[str, Any] = {}
        self._bar_index_at = 0.0
        self._last_spread_log = 0.0

        # ── CỔNG SPREAD: bộ nhớ cho `_log_spread_gate`. Xem docstring ở đó cho lý do
        # vì sao hai lớp khử lặp cũ không chặn được 590 dòng/49 phút.
        self._spread_over_n = 0          # số công cụ vượt trần ở LẦN GHI gần nhất
        self._spread_logged_at = 0.0

        # Tên khoá phải khớp ĐÚNG những gì `gui_command_center` đọc. Bản đầu ghi
        # `"mt"` trong khi GUI đọc `state["mt5_connected"]` — thẻ MT5 TERMINAL hiện
        # DISCONNECTED suốt dù kết nối vẫn tốt, và không có lỗi nào để lần ra.
        # `test_engine_state_keys` khoá lại danh sách này.
        self.state: Dict[str, Any] = {
            "mt5_connected": False,          # ← GUI đọc đúng tên này
            "mt": False,                     # tên cũ, giữ cho hạ tầng kế thừa
            "account": None, "account_info": None, "equity": None,
            "daily_profit": None, "positions_list": [], "positions_read_error": "",
            "closed_trades_today": [], "spread": {}, "guards": {},
            "market_closed": False, "portfolio": {},
            "sentiment": {}, "updated": "",
            # VIỆC NẶNG ĐANG CHẠY — chuỗi mô tả, rỗng khi rảnh.
            #
            # Giao diện đọc khoá này để chạy hiệu ứng "ĐANG CHẠY…" (xem
            # `gui_command_center.busy_text`). Lúc mở bảng điều khiển, engine mất
            # ~2 phút cho `PF.backtest()` 27 chân mà màn hình không có gì đổi —
            # không phân biệt được "đang làm việc" với "đã treo".
            "busy": "",
        }

    # ─────────────────────────────────────────────── log
    def log(self, msg: str) -> None:
        """Gửi một dòng cho giao diện.

        KHÔNG tự thêm dấu thời gian: `gui_command_center` đã dán "HH:MM:SS |" vào đầu
        mỗi dòng khi hiện. Engine thêm nữa thì mỗi dòng có HAI mốc giờ, và chúng còn
        LỆCH NHAU vì engine dùng UTC còn giao diện dùng giờ máy — đọc log thành ra
        phải đoán mốc nào là mốc thật.
        """
        # KHỬ LẶP: cùng một nội dung trong vòng `LOG_DEDUP_SECONDS` chỉ ghi một lần.
        # Không có bước này thì mỗi lỗi lặp lại theo nhịp vòng lặp (5 giây) sẽ đẩy
        # hàng trăm dòng giống hệt nhau vào timeline và nuốt mất những dòng có ích.
        now = time.time()
        if msg == self._last_msg and now - self._last_msg_at < LOG_DEDUP_SECONDS:
            return
        self._last_msg, self._last_msg_at = msg, now

        # SỔ RIÊNG CỦA ĐỘNG CƠ — ghi song song, không phụ thuộc giao diện.
        #
        # VÌ SAO: timeline chỉ được ghi khi giao diện lấy được dòng log ra khỏi hàng
        # đợi rồi tự ghi. Nếu đường đó đứt thì không phân biệt được "động cơ không
        # chạy" với "động cơ chạy nhưng giao diện không nhận" — hai lỗi khác hẳn nhau
        # mà triệu chứng giống hệt: màn hình trống. Sổ này cắt đôi khả năng đó.
        try:
            from src.python.core.config import LIVE_DIR
            f = Path(LIVE_DIR) / "engine.log"
            with f.open("a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now().strftime('%H:%M:%S')} {msg}" + chr(10))
        except Exception:
            pass

        if self.log_callback:
            try:
                self.log_callback(msg)
            except UnicodeEncodeError:
                # Console Windows mặc định cp1252 không in được chữ có dấu. Thay vì
                # mất luôn dòng log, gửi bản đã lược dấu — nội dung còn đọc được.
                try:
                    self.log_callback(msg.encode("ascii", "replace").decode("ascii"))
                except Exception as exc2:
                    _log_incident("log_callback(ascii)", exc2)
            except Exception as exc:
                _log_incident("log_callback", exc)

    def log_error(self, msg: str) -> None:
        self.log(f"LỖI · {msg}")

    # ─────────────────────────────────────────────── vòng lặp
    def _connect_once(self) -> bool:
        """Nối MT5 MỘT LẦN qua `mt5_bridge.init_mt5()`, trước khi vòng lặp chạy.

        ĐỐI CHIẾU 1-1 VỚI HỆ XAUUSD — LỖ HỔNG ĐÃ TÌM RA 16/08/2026
        ===========================================================
        `core/infra/mt5_bridge.py` của hai repo GIỐNG HỆT NHAU: cùng số dòng, cùng
        tên hàm, cùng `init_mt5` / `reconnect_mt5` / `check_mt5_health`. Nhưng bên
        XAUUSD `engine.start()` gọi `init_mt5()` ở bước 2, còn bên này **KHÔNG AI
        GỌI** — quét cả `src/` chỉ ra ba dòng CHÚ THÍCH nhắc tên nó.

        Tức lớp kết nối tốt nhất của dự án nằm đó dưới dạng CODE CHẾT, trong khi
        `_read_broker` tự viết lại một bản yếu hơn ngay trong vòng lặp 5 giây. Đây
        đúng họ lỗi "code chết trông như lớp bảo vệ" mà `ftmo_guard` và
        `risk_guard.check_kill_switch` từng mắc.

        BỐN THỨ `init_mt5()` LÀM MÀ VÒNG LẶP KHÔNG LÀM
        ==============================================
            · 8 lần thử với backoff luỹ thừa 0,5 → 16 giây (~63 giây tổng)
            · DỪNG SỚM ở mã lỗi cố định {-2, -3, -6} — cấu hình sai thì thử lại vô ích
            · dự phòng `mt5.login()` khi `initialize(login=…)` không vào đúng tài khoản
            · `_prime_symbols()` — đưa cả 27 công cụ vào Market Watch VÀ ép tải lịch sử

        Việc cuối là thứ chữa dòng "DỮ LIỆU CŨ · EURUSD" trên VPS: `symbol_select`
        không kích hoạt tải nến, chỉ `copy_rates_from_pos` mới làm, và lần gọi đầu
        chỉ khởi động tải bất đồng bộ rồi trả rỗng.

        VÌ SAO Ở ĐÂY CHỨ KHÔNG PHẢI TRONG VÒNG LẶP
        ===========================================
        `init_mt5()` NGỦ tới ~63 giây. Chấp nhận được khi chạy đúng một lần lúc khởi
        động (người vận hành đang nhìn màn hình chờ), nhưng đưa vào nhịp 5 giây thì
        mọi cổng rủi ro chạy trễ theo — và cổng rủi ro trễ là cổng rủi ro hỏng.

        KHÔNG chặn khởi động khi nối hỏng, KHÁC bản XAUUSD có chủ ý: bên đó một tài
        sản, không nối được thì không có gì để làm. Bên này bảng điều khiển vẫn phải
        lên để người vận hành đọc được lý do — và `entry_gate` đã fail-closed, nên
        không kết nối thì cũng không có lệnh nào ra.
        """
        try:
            from src.python.core.infra.mt5_bridge import init_mt5

            ok = bool(init_mt5())
        except Exception as exc:
            self.log_error(f"init_mt5 ném lỗi: {type(exc).__name__}: {exc}")
            return False
        if not ok:
            self.log_error("⛔ Không nối được MT5 lúc khởi động — bảng vẫn lên để "
                           "đọc lý do, nhưng cổng lệnh fail-closed cho tới khi nối "
                           "được. Chạy scripts/check_mt5_connection.py để chẩn đoán.")
        return ok

    def start_loop(self) -> bool:
        """Bật vòng lặp làm mới. TRẢ BOOL: giao diện dùng nó để hoàn tác nút khi lỗi."""
        if self.is_running:
            return True
        try:
            # Khởi động là quãng NẶNG NHẤT và cũng là quãng màn hình trống nhất:
            # nối MT5, đối soát vị thế, gửi thư khởi động. Bật cờ bận ngay để giao
            # diện có gì để hiện thay vì đứng im ở "N/A".
            self.state["busy"] = "ĐANG KHỞI ĐỘNG"
            self._connect_once()
            self._stop.clear()
            self.is_running = True
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            self._log_startup_banner()
            return True
        except Exception as exc:                           # pragma: no cover
            self.is_running = False
            self.log_error(f"không khởi động được vòng lặp: {exc}")
            return False
        finally:
            # Xoá trong `finally`: nhánh lỗi ở trên `return False` mà không đi qua
            # dòng nào xoá cờ, nên thiếu chỗ này thì khởi động HỎNG lại hiện "đang
            # chạy" mãi mãi — đúng lúc cần nói rõ nhất là đã dừng.
            self.state["busy"] = ""

    def _log_startup_banner(self) -> None:
        """Bộ dòng log KHỞI ĐỘNG, đúng bộ và đúng thứ tự của hệ XAUUSD.

        Bốn dòng, mỗi dòng trả lời một câu mà người vận hành hỏi ngay khi mở ứng
        dụng, và không dòng nào lặp lại ở chu kỳ sau:

            🔌  đang chạy BẢN NÀO, với những chiến lược nào
            🏦  tài khoản đang ở PHA nào của FTMO
            🔍  sổ vị thế có khớp broker không, lệnh mới có được phép không
            💤  thị trường đang mở hay đóng

        Đây là những dòng TRẠNG THÁI KHỞI ĐỘNG — khác hẳn dòng lặp mỗi chu kỳ đã bị
        gỡ ngày 15/08/2026. Chúng in ĐÚNG MỘT LẦN cho mỗi lần chạy, và không có
        chúng thì sổ log không cho biết bản đang chạy là bản nào.
        """
        # ── 🔌 bản build + danh sách chiến lược
        try:
            from src.python.core.runtime_meta import version
            self.state["version"] = version()
        except Exception as exc:
            self.log_error(f"không đọc được định danh build: {exc}")

        # ── 🏦 pha tài khoản FTMO
        try:
            from src.python.core.infra import ftmo as _ftmo
            phase = _ftmo.sync_phase_from_env() or _ftmo._read_state().get("phase")
            self.log(f"🏦 [FTMO] Pha tài khoản: {phase} "
                     f"(mục tiêu {_ftmo.PHASE_TARGETS.get(phase)}, "
                     f"hệ số đệm {_ftmo.buffer_k():.2f})")
        except ValueError:
            raise      # FTMO_PHASE sai -> dừng khởi động, KHÔNG đoán
        except Exception as exc:
            self.log_error(f"không đọc được pha FTMO: {exc}")

        # ── 🔍 đối soát sổ vị thế với broker
        self._log_startup_reconcile()

        # ── 📨 email xác nhận hệ đã sống. Gửi ĐỒNG BỘ, không đẩy sang luồng nền:
        # trên luồng nền nó rơi vào giữa hai dòng bất kỳ và bộ log khởi động mất
        # thứ tự cố định — thứ tự ấy là thứ làm người vận hành đọc lướt một cái là
        # biết đủ. Gửi mất chưa tới một giây.
        self._send_startup_email()

        # ── 🔌 bản build + danh sách chiến lược, dòng CHỐT của bộ khởi động
        try:
            from src.python.core.runtime_meta import banner
            self.log(f"🔌 Kết nối thành công | {banner()}")
        except Exception as exc:
            self.log_error(f"không đọc được banner build: {exc}")

        # ── 💤 pha thị trường
        try:
            from src.python.core.infra import market_schedule as MS
            self.log("💤 Thị trường ĐÓNG CỬA" if MS.is_market_closed()
                     else "📈 Thị trường ĐANG MỞ")
        except Exception as exc:
            self.log_error(f"không đọc được lịch thị trường: {exc}")

    def _send_startup_email(self) -> None:
        """Email "bot đã khởi động". TTL 10 phút chống bấm RUN nhiều lần liên tiếp."""
        from functools import partial

        try:
            from src.python.core import strategy_registry as SR
            from src.python.core.infra import market_schedule as MS
            from src.python.shared.notifications import emails as EM
            from src.python.utils import alerts

            from src.python.utils import mailer

            sent = alerts.once(
                "startup",
                partial(EM.startup,
                        account=self.state.get("account_info") or {},
                        strategies=len(SR.live()),
                        positions=len(self.state.get("positions_list") or []),
                        market_status=MS.describe()),
                ttl_sec=600.0)
            # MỘT dòng cho cả kênh email, đúng kiểu "[Email Watcher]" của bản cũ:
            # nó nói kênh có sẵn sàng không, không thuật lại từng lá thư. Chi tiết
            # nội dung nằm ở log thô `logs/cheopard_forex.log`.
            # BA trường hợp, và phải phân biệt được cả ba. `alerts.once()` trả
            # `False` cho hai lý do trái ngược nhau — đã gửi rồi (tốt) và không gửi
            # được (xấu) — nên hỏi thêm `recently_sent` trước khi kết luận.
            #
            # Bản cũ gộp cả hai vào một câu đổ lỗi cho `APP_ENV`, và nhật ký VPS
            # ngày 16/08/2026 in ra dòng tự mâu thuẫn "chỉ GHI LOG (APP_ENV=PROD,
            # cần PROD để gửi thật)" trong khi thư vừa gửi thành công 4 phút trước.
            from src.python.core.config import APP_ENV, IS_PROD

            if sent:
                self.log("📨 [Email] đã gửi thư khởi động tới người vận hành")
            elif alerts.recently_sent("startup", 600.0):
                self.log("📨 [Email] BỎ QUA thư khởi động — đã gửi trong 10 phút qua")
            elif not mailer.is_configured():
                self.log("📨 [Email] TẮT — chưa khai SMTP trong .env")
            elif not IS_PROD:
                self.log(f"📨 [Email] chỉ GHI LOG (APP_ENV={APP_ENV}, "
                         f"cần PROD để gửi thật)")
            else:
                self.log("📨 [Email] KHÔNG gửi được dù APP_ENV=PROD và SMTP đã khai "
                         "— xem lỗi SMTP trong logs/cheopard_forex.log")
        except Exception as exc:                           # pragma: no cover
            _log_incident("email khởi động", exc)

    def _log_startup_reconcile(self) -> None:
        """Đối soát sổ vị thế với broker MỘT LẦN lúc khởi động, và NÓI kết quả.

        `order_plan.build()` vẫn tự đối soát mỗi chu kỳ và đưa `reconciliation_done`
        vào cổng fail-closed — chỗ này KHÔNG thay việc đó. Nó trả lời câu hỏi mà
        người vận hành hỏi ngay lúc mở ứng dụng: sổ có khớp broker không, và có
        vị thế lạ nào không.

        Fail-CLOSED: lỗi ở chính quá trình đối soát nghĩa là KHÔNG biết trạng thái
        thật, nên chặn lệnh mới thay vì cho qua im lặng.
        """
        try:
            import MetaTrader5 as mt5

            if mt5.terminal_info() is None:
                self.log("🔍 [ĐỐI SOÁT] BỎ QUA — chưa kết nối MT5. "
                         "Cổng lệnh vẫn fail-closed cho tới khi đối soát được.")
                return
            book = self._book_ref()
            rec = book.reconcile(mt5.positions_get() or [])
            self.log(f"🔍 [ĐỐI SOÁT] Hoàn tất đối chiếu khởi động: "
                     f"{len(rec.matched)} khớp, {len(rec.orphan)} lạ, "
                     f"{len(rec.closed_elsewhere)} đã đóng nơi khác, "
                     f"entries_allowed={self.entries_allowed}")
            if not rec.ok:
                for line in rec.explain().splitlines()[1:]:
                    self.log(f"⚠️ [ĐỐI SOÁT] {line}")
        except Exception as exc:
            self.log_error(f"[ĐỐI SOÁT] KHÔNG đối soát được ({exc}) — "
                           f"fail-closed, lệnh mới bị chặn")

    def stop_loop(self) -> None:
        self._stop.set()
        self.is_running = False
        self.log("động cơ đã dừng")

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._check_market_hours()
                self.update_mt5_status()
                self._run_active_defence()
                self._maybe_log_spread()
                self._maybe_build_plan()
                self._maybe_session_report()
            except Exception as exc:                       # pragma: no cover
                self.log_error(f"vòng lặp: {exc}")
            self._stop.wait(REFRESH_SECONDS)

    def _maybe_session_report(self) -> None:
        """Báo cáo TỔNG KẾT PHIÊN, gửi ĐÚNG MỘT LẦN cho mỗi ngày giao dịch.

        Chống gửi trùng nằm ở `alerts.once` với chủ đề mang NGÀY: mỗi ngày là một
        chủ đề khác nên hôm sau vẫn gửi được, còn trong cùng ngày thì mọi chu kỳ
        sau đều bị chặn. TTL 20 giờ đủ phủ hết phần còn lại của ngày mà không
        tràn sang ngày kế.
        """
        from functools import partial

        try:
            from src.python.shared.notifications import session_report as SR
            from src.python.utils import alerts

            day = SR.should_send()
            if not day:
                return
            acc = self.state.get("account_info") or {}
            sent = alerts.once(
                f"session_report_{day}",
                partial(SR.send, day,
                        equity=float(acc.get("equity") or 0.0),
                        balance=float(acc.get("balance") or 0.0)),
                ttl_sec=20 * 3600.0)
            if sent:
                self.log(f"📊 [Báo cáo phiên] đã gửi tổng kết ngày {day}")
        except Exception as exc:                           # pragma: no cover
            _log_incident("báo cáo tổng kết phiên", exc)

    def _run_active_defence(self) -> None:
        """Ba hàm PHÒNG THỦ CHỦ ĐỘNG, chạy mỗi chu kỳ. Đây là lớp duy nhất ĐÓNG lệnh.

        BỔ SUNG 15/08/2026 SAU KHI SO KHỚP VỚI HỆ XAUUSD
        =================================================
        Bên đó `engine._loop` gọi cả ba hàm này mỗi chu kỳ. Bên này KHÔNG gọi hàm
        nào: `risk_guard.check_kill_switch()` được port sang nhưng chưa ai gọi, và
        `ftmo_guard` thì chưa tồn tại. Nghĩa là toàn bộ phòng thủ của hệ Forex chỉ
        là CHẶN LỆNH MỚI — `entry_gate`, `ftmo_leverage_policy`, `trading_control`
        đều không đụng tới vị thế đang mở.

        Với đúng danh mục này thì đó là lỗ hổng chí mạng: 27 chân giữ lệnh qua đêm
        và qua cuối tuần, không chân nào có SL theo giá. Giá chạy ngược cả rổ thì
        trước đây không có gì đóng cho tới khi cầu chì `disaster_stop` nổ ở ≥8×ATR
        — mà lúc đó tổn thất đã xảy ra rồi, và nhiều vị thế cùng nổ thì tổng đã
        vượt xa mốc ngày 5%.

        THỨ TỰ GỌI CÓ Ý NGHĨA:
          1. `monitor_equity_drawdown` cập nhật mốc và phát cảnh báo sớm
          2. `ftmo_guard.check`        đóng theo lỗ ngày THỰC + rủi ro ĐANG MỞ
          3. `check_kill_switch`       lưới cuối theo ngưỡng `.env`

        Mỗi lớp bọc riêng: một lớp hỏng KHÔNG được làm hai lớp còn lại không chạy.
        """
        import MetaTrader5 as mt5

        if not self.state.get("mt5_connected"):
            return          # chưa đọc được gì thì chưa phán được gì

        for name, fn in (("monitor_equity_drawdown", self._defence_monitor),
                         ("ftmo_guard.check", self._defence_ftmo_guard),
                         ("check_kill_switch", self._defence_kill_switch)):
            try:
                fn(mt5)     # chỉ `ftmo_guard` cần tay cầm; hai hàm kia tự đọc
            except Exception as exc:                       # pragma: no cover
                # Hỏng ở tầng phòng thủ phải NÓI TO — đây là lớp mà im lặng nghĩa
                # là không ai biết nó đã ngừng bảo vệ.
                self.log_error(f"LỚP PHÒNG THỦ {name} HỎNG: "
                               f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _defence_monitor(_mt5) -> None:
        """`risk_guard` tự lấy tài khoản qua `set_account_source` — không cần tay cầm."""
        from src.python.core.infra import risk_guard

        risk_guard.monitor_equity_drawdown()

    def _defence_ftmo_guard(self, mt5) -> None:
        from src.python.core.infra import ftmo_guard

        acc = self.state.get("account_info") or {}
        res = ftmo_guard.check(mt5,
                               equity=float(acc.get("equity") or 0.0) or None,
                               balance=float(acc.get("balance") or 0.0) or None)
        self.state["ftmo_guard"] = res.explain()
        if res.acted:
            self.log(f"🚨 [FTMO GUARD] {res.explain()}")

    @staticmethod
    def _defence_kill_switch(_mt5) -> None:
        from src.python.core.infra import risk_guard

        risk_guard.check_kill_switch()

    # ─────────────────────────────────────────────── ngủ đông cuối tuần
    def _check_market_hours(self) -> None:
        """Phát hiện CHUYỂN TRẠNG THÁI mở/đóng và gửi email đúng MỘT lần mỗi lần đổi.

        VÌ SAO SO SÁNH VỚI TRẠNG THÁI TRƯỚC, KHÔNG GỬI THEO LỊCH
        =========================================================
        Gửi theo lịch ("cứ 00:00 Thứ Bảy thì gửi") sai ở hai đầu: bot khởi động lại
        lúc 03:00 Thứ Bảy sẽ không gửi gì cả, còn bot chạy liên tục mà lịch trôi qua
        lúc đang bận sẽ gửi trễ hoặc gửi trùng. So sánh với trạng thái CHU KỲ TRƯỚC
        thì đúng trong cả hai trường hợp, và đó cũng là cách hệ XAUUSD làm.

        PHA TRƯỚC ĐÓ ĐỌC TỪ ĐĨA, KHÔNG PHẢI TỪ RAM
        ===========================================
        Chỉ lần chạy đầu tiên TRONG ĐỜI (chưa có file pha) mới không gửi email. Mọi
        lần khởi động lại sau đó đều so với pha đã ghi trên đĩa, nên một lần VPS
        reboot vào trưa Chủ Nhật vẫn gửi được email "thức dậy" lúc 21:00.

        Đây là lỗi đã cắn hệ XAUUSD: cờ trong RAM phải sống ~45 giờ liên tục từ
        00:00 thứ Bảy tới 21:00 Chủ Nhật, và bất kỳ lần restart nào trong quãng đó
        đều làm mất email thức dậy. Chiều ngược lại không bao giờ hỏng vì lúc thị
        trường đóng, bot đã chạy liên tục suốt phiên thứ Sáu — nên nhìn log vẫn
        thấy "email vẫn chạy".
        """
        from src.python.core.infra import market_schedule as MS

        closed = MS.is_market_closed()
        prev = self._prev_market_closed
        # Phân biệt "lần kiểm đầu TRONG TIẾN TRÌNH này" với "chưa từng ghi pha ra
        # đĩa". Hai thứ khác nhau: cái đầu xảy ra mỗi lần khởi động, cái sau chỉ một
        # lần trong đời. Dòng trạng thái lúc khởi động phải bám vào cái ĐẦU.
        if prev is None:
            # Lần kiểm đầu sau khởi động: lấy pha lần trước TỪ ĐĨA. Đây là dòng làm
            # email "thức dậy" tới được sau một lần restart giữa cuối tuần.
            prev = MS.load_phase()
        self._prev_market_closed = closed
        MS.save_phase(closed)
        self.state["market_closed"] = closed
        # Thẻ giao diện: KHÔNG đếm ngược — xem `MS.describe`. Email vẫn giữ.
        self.state["market_status"] = MS.describe(countdown=False)

        # KHÔNG in dòng trạng thái lúc khởi động (bỏ 15/08/2026). Pha thị trường
        # đã hiện thường trực trên thẻ giao diện qua `state["market_status"]`, nên
        # một dòng log mỗi lần mở ứng dụng chỉ lặp lại thứ đang nhìn thấy. Log giữ
        # cho SỰ KIỆN — lúc CHUYỂN pha — chứ không phải cho trạng thái.

        if prev is not None and prev != closed:
            # KHÔNG ghi dòng log cho lần chuyển pha (bỏ 15/08/2026). Pha thị trường
            # đã hiện thường trực trên thẻ giao diện qua `state["market_status"]`,
            # và EMAIL mới là thứ báo cho người vận hành khi họ không nhìn màn hình.
            # Một dòng nữa trong sổ log chỉ lặp lại thứ đang nhìn thấy.
            threading.Thread(target=self._send_market_state_email,
                             args=(closed,), daemon=True).start()
        # KHÔNG lặp lại dòng ngủ đông trong lúc thị trường đóng.
        #
        # Hệ XAUUSD in nó mỗi 5 phút; ở đây bỏ hẳn, chỉ giữ đúng HAI dòng cho mỗi
        # cuối tuần — lúc NGỦ ĐÔNG và lúc THỨC DẬY. Lý do: pha thị trường hiện
        # thường trực trên thẻ giao diện qua `state["market_status"]`, nên nhắc lại
        # trong sổ log chỉ lặp thứ đang nhìn thấy. Log giữ cho SỰ KIỆN, không phải
        # cho TRẠNG THÁI.

    def _send_market_state_email(self, closed: bool) -> None:
        """Email NGỦ ĐÔNG / THỨC DẬY. Nội dung ở `shared/notifications/emails.py`.

        Nội dung thư dựng ở module dùng chung chứ không viết tại đây: mười bảy loại
        thư của hệ phải cùng một khung viền và cùng một cách trình bày, và bản viết
        tay tại chỗ chính là chỗ chúng trôi khỏi nhau.
        """
        try:
            from src.python.core.infra import market_schedule as MS
            from src.python.shared.notifications import emails as EM

            EM.market_phase(closed=closed,
                            account=self.state.get("account_info") or {},
                            positions=len(self.state.get("positions_list") or []),
                            market_status=MS.describe())
        except Exception as exc:                           # pragma: no cover
            _log_incident("email chuyển trạng thái thị trường", exc)

    # ─────────────────────────────────────────────── công tắc vào lệnh
    @property
    def entries_allowed(self) -> bool:
        """Người vận hành CÓ đang cho vào lệnh mới không. Đọc từ đĩa mỗi lần hỏi.

        Đọc lại mỗi lần thay vì nhớ trong RAM là có chủ ý: công tắc có thể bị đổi từ
        một tiến trình khác (script, phiên GUI thứ hai), và một bản sao cũ trong RAM
        nghĩa là hệ vẫn vào lệnh sau khi người vận hành đã bấm STOP ở nơi khác.
        """
        from src.python.execution import trading_control

        return trading_control.entry_allowed()

    def allow_entries(self, by: str = "operator") -> bool:
        """[ RUN ENGINE ] — cho phép MỌI chiến lược vào lệnh mới."""
        from src.python.execution import trading_control

        was = trading_control.entry_allowed()
        st = trading_control.set_enabled(True, reason="RUN ENGINE", by=by)
        self.state["entries_allowed"] = True
        # Chỉ log khi trạng thái THẬT SỰ ĐỔI. Bấm RUN lúc đang RUN, hoặc mở lại
        # ứng dụng, không phải một sự kiện — và mỗi lần khởi động lại in thêm một
        # dòng giống hệt thì sổ log mất khả năng cho biết CHUYỆN GÌ đã xảy ra.
        # KHÔNG ghi log (bỏ 15/08/2026). Hai nút RUN/STOP tự đổi trạng thái bật/tắt
        # ngay trên giao diện, nên trạng thái luôn nhìn thấy được. Vết KIỂM TOÁN của
        # thao tác này nằm ở `trading_control` — file trên đĩa có `reason`, `by` và
        # dấu thời gian, tồn tại lâu hơn sổ log của một phiên.
        _ = was
        return st.enabled

    def block_entries(self, by: str = "operator") -> bool:
        """[ STOP ENGINE ] — từ chối lệnh MỚI. Ứng dụng vẫn chạy bình thường.

        KHÔNG dừng vòng lặp, KHÔNG đóng vị thế đang mở, KHÔNG gỡ cầu chì, KHÔNG dừng
        đếm time-stop. Một vị thế đang mở mà mất người quản lý là tình trạng nguy
        hiểm HƠN việc vào thêm lệnh — muốn đóng sạch thì đó là kill switch, chức năng
        riêng có xác nhận riêng.
        """
        from src.python.execution import trading_control

        st = trading_control.set_enabled(False, reason="STOP ENGINE", by=by)
        self.state["entries_allowed"] = False
        # KHÔNG ghi log — xem lý do ở `allow_entries`.
        return not st.enabled

    # ─────────────────────────────────────────────── bảng spread định kỳ
    # Ước lượng spread đang dùng trong backtest (pip). Nguồn: bảng công bố của các
    # broker raw-spread, ghi trong docstring `research/fx_cross_pairs.py`. Đây là
    # ƯỚC LƯỢNG, và thay nó bằng SỐ ĐO là mục đích của bảng log này.
    SPREAD_ESTIMATE_PIPS = {
        "EURUSD": 0.3, "GBPUSD": 0.5, "USDJPY": 0.4, "AUDUSD": 0.5,
        "USDCAD": 0.6, "USDCHF": 0.6, "NZDUSD": 0.8,
        "EURGBP": 0.9, "EURJPY": 1.0, "GBPJPY": 1.8, "AUDJPY": 1.3,
        "EURAUD": 1.6, "EURCHF": 1.3, "EURNZD": 2.0, "EURCAD": 1.5,
        "GBPAUD": 2.0, "GBPNZD": 2.5, "GBPCAD": 1.8, "GBPCHF": 1.6,
        "AUDNZD": 1.5, "AUDCAD": 1.3, "AUDCHF": 1.4, "NZDCAD": 1.6,
        "NZDCHF": 1.8, "NZDJPY": 1.5, "CADCHF": 1.5, "CADJPY": 1.4, "CHFJPY": 1.6,
    }

    def _maybe_log_spread(self) -> None:
        """In bảng spread THẬT lên timeline mỗi 30 phút, kèm cột lệch so với ước lượng.

        Không chạy khi thị trường đóng: giá cuối tuần là giá đóng băng, và ghi nó vào
        bảng đo sẽ kéo trung vị xuống bằng những con số không giao dịch được.
        """
        from src.python.core.infra import market_schedule as MS

        if MS.is_market_closed():
            return
        if time.time() - self._last_spread_log <= SPREAD_LOG_EVERY:
            return
        self._last_spread_log = time.time()

        sp = self.state.get("spread") or {}
        px = self.state.get("prices") or {}
        if not sp:
            return

        from src.python.shared import asset_profile as AP

        rows = []
        for sym, bps in sp.items():
            mid = float(px.get(sym) or 0.0)
            if mid <= 0:
                continue
            try:
                pip = AP.get(sym).pip
            except Exception:
                pip = 0.01 if sym.endswith("JPY") else 0.0001
            pips = (bps / 1e4 * mid) / pip
            est = self.SPREAD_ESTIMATE_PIPS.get(sym)
            rows.append((sym, pips, est,
                         (pips / est - 1.0) * 100.0 if est else None))
        if not rows:
            return

        rows.sort(key=lambda r: (r[3] is None, -(r[3] or 0)))

        # TOÀN BỘ 27 công cụ vào SỔ CÓ CẤU TRÚC, không lên console.
        #
        # Đây là phép đo dựng nên phân phối chi phí thật của 21 cặp chéo — giả định
        # lớn nhất còn lại của cả hệ — nên KHÔNG được cắt bớt số liệu. Nhưng nó là
        # TRẠNG THÁI, không phải sự kiện: in 28 dòng mỗi 30 phút cho ra 1.344 dòng
        # mỗi ngày (đo trên nhật ký VPS 18/08/2026) và chúng nuốt mọi dòng có ích.
        #
        # Nên chia đôi: số liệu đầy đủ đi vào JSONL (truy vấn được, không cạnh tranh
        # chỗ với dòng khác), console nhận đúng một dòng tóm tắt.
        from src.python.utils import ops_log

        from src.python.core.config import SPREAD_CAP_BPS

        ops_log.emit("market", "spread_survey", cap_bps=SPREAD_CAP_BPS,
                     rows=[{"symbol": sym, "pips": round(pips, 3),
                            "estimate_pips": est,
                            "diff_pct": None if diff is None else round(diff, 1)}
                           for sym, pips, est, diff in rows])

        got = [r[3] for r in rows if r[3] is not None]
        if not got:
            self.log(f"SPREAD THẬT {len(rows)} công cụ — chưa có mốc ước lượng để so")
            return
        wider = sum(1 for d in got if d > 0)
        med = sorted(got)[len(got) // 2]
        worst = rows[0]
        self.log(f"SPREAD THẬT {len(rows)} công cụ · {wider}/{len(got)} rộng hơn ước "
                 f"lượng · trung vị lệch {med:+.0f}% · rộng nhất {worst[0]} "
                 f"{worst[1]:.2f} pip ({worst[3]:+.0f}%) — chi tiết trong "
                 f"logs/market/*.jsonl")

    # ─────────────────────────────────────────────── kế hoạch lệnh
    def _maybe_build_plan(self) -> None:
        """Dựng kế hoạch lệnh nếu tới hạn. KHÔNG gửi trừ khi đã vũ trang.

        BA LỚP CHẶN TRƯỚC KHI CHẠM BROKER, và cần cả ba:
          1. `is_market_closed()` — cuối tuần không dựng kế hoạch. Giá cuối tuần là
             giá đóng băng, và một kế hoạch dựng trên giá đóng băng sẽ sai lot ngay
             lúc mở cửa.
          2. `arm_orders` — công tắc trong tiến trình, mặc định TẮT.
          3. `trading_control` — công tắc BỀN VỮNG trên đĩa của người vận hành, đọc
             bên trong `order_plan.build()`.
        Lớp 2 và 3 khác nhau có chủ đích: lớp 2 mất khi restart (đúng, vì vũ trang là
        hành động có ý thức cho MỘT phiên), lớp 3 sống qua restart (đúng, vì tắt
        giao dịch là một quyết định vận hành).
        """
        from src.python.core.infra import market_schedule as MS

        if MS.is_market_closed():
            return
        if time.time() - self._last_plan <= PLAN_EVERY:
            return
        if not self._plan_lock.acquire(blocking=False):
            return
        try:
            self._build_plan()
        except Exception as exc:                           # pragma: no cover
            self.state["order_plan"] = {"error": f"{type(exc).__name__}: {exc}"}
            self.log_error(f"dựng kế hoạch lệnh: {exc}")
        finally:
            self._last_plan = time.time()
            self._plan_lock.release()

    def _book_ref(self):
        """Sổ vị thế, nạp một lần. Nạp lười vì nó đọc đĩa."""
        if self._book is None:
            from src.python.execution.position_book import PositionBook
            self._book = PositionBook()
        return self._book

    def _bar_indexes(self) -> Dict[str, Any]:
        """Chỉ mục nến của 22 chân, có cache.

        NẶNG: mỗi chân nạp một chuỗi nến. Cache theo cùng nhịp dựng kế hoạch — chỉ
        mục nến chỉ đổi khi có nến mới đóng, và trong một giờ thì cùng lắm vài nến.
        """
        if time.time() - self._bar_index_at > PLAN_EVERY:
            from src.python.execution import position_book as PB
            book = self._book_ref()
            if len(book):
                self._bar_index_cache = PB.bar_indexes_for(book.all().keys())
                self._bar_index_at = time.time()
        return self._bar_index_cache

    def _finalise_closed(self, book) -> None:
        """Ghi nhận mọi vị thế đã BIẾN MẤT khỏi broker kể từ chu kỳ trước.

        Điểm hội tụ của nhánh đóng lệnh BỊ ĐỘNG: cầu chì nổ, người vận hành đóng tay
        trên MT5, hoặc broker đóng vì lý do của họ. Nhánh CHỦ ĐỘNG (hệ tự gửi lệnh
        đóng) đi qua `order_router` rồi cũng về đây ở chu kỳ kế tiếp.

        Không có bước này thì `position_book` giữ mãi một chân đã hết vị thế, và
        `open()` sẽ báo "đã có vị thế" mỗi lần chân đó muốn vào lệnh lại — chân câm
        vĩnh viễn mà không có lỗi nào.
        """
        from src.python.execution import exit_manager as EM

        # `positions_list` là danh sách DICT (xem `_read_broker`), không phải đối
        # tượng vị thế của MT5. Đọc nhầm kiểu ở đây làm hàm ném AttributeError giữa
        # chu kỳ và mọi bước sau `_finalise_closed` không chạy.
        real = {str(p.get("symbol", "")) for p in
                (self.state.get("positions_list") or []) if isinstance(p, dict)}
        if not book.all():
            return
        prices = self.state.get("prices") or {}
        for leg, pos in list(book.all().items()):
            if pos.symbol in real:
                continue
            px = float(prices.get(pos.symbol) or pos.entry_price)
            rec = EM.record_close(
                book, leg, reason=EM.REASON_RECONCILE, exit_price=px,
                exit_bar_utc=_now(), bars_held=0,
                note="broker không còn vị thế — cầu chì nổ hoặc đóng tay")
            if rec is not None:
                self.log(rec.explain())
                self._send_close_email(rec, pos)

    def _send_close_email(self, rec, pos) -> None:
        """Email cho MỘT vị thế vừa đóng. Gọi từ điểm hội tụ `_finalise_closed`.

        Đặt ở đây chứ không ở `order_router` là có chủ ý: `order_router` chỉ thấy
        nhánh hệ CHỦ ĐỘNG đóng. Cầu chì nổ trên server broker và người vận hành đóng
        tay trên MT5 không đi qua nó — mà đó lại đúng là hai ca người vận hành cần
        biết nhất, vì cả hai đều xảy ra lúc không ai nhìn màn hình.
        """
        try:
            from src.python.shared.notifications import emails as EM

            EM.close(strategy=getattr(rec, "leg", "?"),
                     symbol=pos.symbol, direction=pos.side, lots=float(pos.lots),
                     entry_price=float(pos.entry_price),
                     exit_price=float(getattr(rec, "exit_price", 0.0) or 0.0),
                     pnl_usd=getattr(rec, "pnl_usd", None),
                     bars_held=getattr(rec, "bars_held", None),
                     reason=str(getattr(rec, "reason", "") or ""))
        except Exception as exc:                           # pragma: no cover
            _log_incident("email đóng lệnh", exc)

    def _build_plan(self) -> None:
        """Một chu kỳ đầy đủ: mục tiêu 27 chân → kế hoạch → (tuỳ chọn) gửi lệnh."""
        import MetaTrader5 as mt5

        from src.python.execution import order_plan as OP
        from src.python.strategies import portfolio as PF

        t0 = time.time()
        acc = self.state.get("account_info") or {}
        equity = float(acc.get("equity") or 0.0)
        prices = dict(self.state.get("prices") or {})
        if equity <= 0 or not prices:
            self.state["order_plan"] = {
                "error": "chưa có equity hoặc bảng giá — chưa kết nối MT5"}
            return

        book = self._book_ref()
        self._finalise_closed(book)

        # `bars_held` là ĐỒNG HỒ TIME-STOP. Với phần lớn lệnh, time-stop là lối thoát
        # DUY NHẤT (không chân nào có SL theo giá), nên truyền thiếu nó nghĩa là mọi
        # chân đang giữ lệnh nhận `bars_held = 0` và vị thế được giữ VÔ HẠN.
        held = book.all_bars_held(self._bar_indexes())

        targets = PF.live_targets(bars_held=held, log=True)
        plan = OP.build(
            targets, equity_usd=equity, prices=prices, mt5=mt5, book=book,
            daily_vol_bps=float(self.state.get("portfolio", {}).get(
                "daily_vol_bps") or 9.33),
            day_start_balance=float(acc.get("balance") or equity))

        self.state["order_plan"] = {
            "asof": targets.asof,
            "allowed": plan.allowed,
            "leverage": plan.leverage,
            "n_actions": len(plan.to_trade),
            "gross_notional_usd": plan.gross_notional_usd,
            "gate": plan.gate.explain(),
            "actions": [a.explain() for a in plan.to_trade],
            "entries_allowed": self.entries_allowed,
            "dry_run": self.dry_run,
            "bars_held": held,
        }
        # Chỉ log khi CỔNG ĐỔI trạng thái. Bản trước còn in một dòng tóm tắt kế
        # hoạch MỖI GIỜ — số liệu đó đã nằm trong `state["order_plan"]` cho thẻ
        # giao diện đọc, nên in thêm vào sổ log là nhân đôi cùng một thông tin.
        self._log_change("plan_gate", plan.gate.explain(),
                         f"cổng lệnh: {plan.gate.explain()}")

        # LUÔN gọi router, KỂ CẢ khi người vận hành đã bấm STOP.
        #
        # SỬA 15/08/2026 — trước đó chỗ này `return` sớm khi `entries_allowed` là
        # False. Nghe thì đúng ("đã bấm STOP thì đừng gửi gì"), nhưng nó khoá luôn
        # ĐƯỜNG THOÁT: sau khi bấm STOP, không lệnh ĐÓNG nào tới được broker nữa.
        # Time-stop hết hạn — không đóng. Cầu chì cần dời — không dời. Chính sách
        # đòn bẩy trả 0 và kế hoạch muốn đóng sạch — cũng không đóng. Vị thế đang
        # mở bị bỏ mặc, mà CLAUDE.md nói rõ đó là tình trạng nguy hiểm HƠN việc vào
        # thêm lệnh.
        #
        # Phân loại nằm ở MỘT chỗ duy nhất — `order_router.route()`: lệnh làm TĂNG
        # phơi nhiễm bị chặn, lệnh làm GIẢM luôn đi qua. `order_plan` cũng đã tự
        # đọc `trading_control`, nên cổng trong kế hoạch đã đóng sẵn; ở đây chỉ cần
        # ngừng chặn thêm một lần nữa ở tầng trên.
        from src.python.execution.order_router import OrderRouter

        router = OrderRouter(mt5, dry_run=self.dry_run)
        out = router.route(plan, bar_utc=str(targets.asof))
        self.state["order_plan"]["routed"] = out.explain()
        for line in out.explain().splitlines():
            self.log(line)

        # GHI SỔ ngay sau khi gửi. Không có bước này thì `position_book` rỗng vĩnh
        # viễn và TIME-STOP không bao giờ kích hoạt — xem `position_book.sync_from_targets`.
        #
        # Chỉ đồng bộ khi cổng CHO PHÉP: cổng đang chặn thì router chỉ gửi lệnh
        # GIẢM phơi nhiễm, và nhánh đóng đã được `_finalise_closed` dọn ở chu kỳ
        # sau theo vị thế THẬT của broker. Ghi ý định "mở" vào sổ trong lúc lệnh mở
        # bị chặn là tự tạo ra một vị thế ma.
        if plan.allowed:
            try:
                from src.python.execution import position_book as PB

                changed = PB.sync_from_targets(
                    book, targets, prices,
                    lots_by_symbol={a.symbol: a.target_lots for a in plan.actions})
                for leg, what in changed.items():
                    self.log(f"[SỔ] {leg}: {what}")
            except Exception as exc:
                # Sổ lệch là tình trạng phải NÓI TO: chu kỳ sau `reconcile()` sẽ
                # thấy mồ côi và cổng fail-closed sẽ chặn lệnh mới.
                self.log_error(f"KHÔNG ghi được sổ vị thế: "
                               f"{type(exc).__name__}: {exc}")

    # ─────────────────────────────────────────────── làm mới trạng thái
    def update_mt5_status(self) -> None:
        """Làm mới toàn bộ trạng thái. Giao diện gọi trên luồng riêng lúc khởi động.

        Tên giữ nguyên như hệ XAUUSD vì `gui_command_center` được kế thừa nguyên vẹn
        và gọi đúng tên này — đổi tên ở đây là phải sửa GUI, mà GUI thì không sửa.
        """
        self._read_broker()
        self._read_guards()
        self._maybe_read_portfolio()
        self.state["updated"] = _now()
        if self.status_callback:
            try:
                self.status_callback(self.state)
            except Exception as exc:
                # Đây là đường DUY NHẤT đưa dữ liệu lên giao diện. Nuốt lỗi ở đây
                # nghĩa là mọi thẻ hiện N/A mà không ai biết vì sao.
                _log_incident("status_callback", exc)
                self.log(f"KHÔNG cập nhật được giao diện: {type(exc).__name__}")


    # Ngưỡng phút mất kết nối trước khi gửi email. Bằng hệ XAUUSD.
    DISCONNECT_ALERT_MIN = 5.0

    def _on_mt5_lost(self) -> None:
        """MT5 vừa rớt. Gửi email nếu đã rớt quá ngưỡng, ĐÚNG MỘT lần mỗi lần rớt."""
        now = time.time()
        if self._disconnected_since is None:
            self._disconnected_since = now
            return
        down_min = (now - self._disconnected_since) / 60.0
        if down_min < self.DISCONNECT_ALERT_MIN:
            return
        from functools import partial

        from src.python.shared.notifications import emails as EM
        from src.python.utils import alerts

        alerts.once("mt5_disconnected",
                    partial(EM.disconnected,
                            account=self.state.get("account_info") or {},
                            minutes=self.DISCONNECT_ALERT_MIN),
                    ttl_sec=6 * 3600.0)

    def _on_mt5_back(self) -> None:
        """MT5 nối lại. Chỉ gửi email nếu TRƯỚC ĐÓ thật sự có một lần rớt."""
        if self._disconnected_since is None:
            return
        down_min = (time.time() - self._disconnected_since) / 60.0
        self._disconnected_since = None
        if down_min < self.DISCONNECT_ALERT_MIN:
            return          # chớp một cái rồi lại — không ai được báo, không cần báo lại
        from functools import partial

        from src.python.shared.notifications import emails as EM
        from src.python.utils import alerts

        # Xoá mốc của chủ đề "mất kết nối" để lần rớt kế tiếp báo NGAY, không bị
        # TTL sáu tiếng của lần này nuốt mất.
        alerts.reset("mt5_disconnected")
        alerts.once("mt5_reconnected",
                    partial(EM.reconnected,
                            account=self.state.get("account_info") or {},
                            downtime_min=down_min,
                            positions=len(self.state.get("positions_list") or [])),
                    ttl_sec=300.0)

    def _check_account_identity(self, actual_login, server, expected_login) -> None:
        """Tài khoản đang đăng nhập có ĐÚNG tài khoản trong `.env` không.

        FAIL-CLOSED: lệch thì tắt công tắc giao dịch ngay, không chỉ gửi thư.

        Đây là sự cố nguy hiểm nhất trong nhóm hạ tầng, và nó không hiếm: MT5 nhớ
        phiên đăng nhập cuối, nên chỉ cần ai đó đăng nhập tài khoản cá nhân để xem
        biểu đồ rồi quên đăng xuất là hệ sẽ đặt lệnh của danh mục FTMO lên tài khoản
        đó — với cỡ lệnh tính theo equity của tài khoản kia. `mt5.initialize()` trần
        KHÔNG bắt được: nó chỉ gắn vào terminal đang mở, ai đang đăng nhập cũng được.

        `expected_login` rỗng nghĩa là `.env` chưa khai `MT5_LOGIN` — không so được
        thì không phán, nhưng đó là một lỗ hổng cấu hình cần khai cho đủ.
        """
        if not expected_login:
            return
        try:
            if int(actual_login) == int(expected_login):
                return
        except (TypeError, ValueError):
            return

        from functools import partial

        from src.python.execution import trading_control
        from src.python.shared.notifications import emails as EM
        from src.python.utils import alerts

        trading_control.set_enabled(
            False, reason=f"XUNG ĐỘT TÀI KHOẢN: MT5 đang đăng nhập {actual_login}, "
                          f"cấu hình là {expected_login}", by="account_guard")
        self.log_error(f"⛔ XUNG ĐỘT TÀI KHOẢN — MT5 đang đăng nhập {actual_login} "
                       f"nhưng .env khai {expected_login}. ĐÃ TẮT công tắc giao dịch.")
        alerts.once("account_mismatch",
                    partial(EM.account_mismatch, expected=str(expected_login),
                            actual=str(actual_login), server=str(server or "")),
                    ttl_sec=3600.0)

    def _read_broker(self) -> None:
        """Tài khoản, vị thế, spread từ MT5. Thiếu MT5 thì bảng vẫn chạy, chỉ trống."""
        try:
            import MetaTrader5 as mt5
        except ImportError:
            self.state["mt"] = self.state["mt5_connected"] = False
            self.state["positions_read_error"] = (
                "chưa cài MetaTrader5 — bảng chạy ở chế độ chỉ xem backtest")
            return

        try:
            from src.python.core.config import (LOGIN, PASSWORD, SERVER, MT5_PATH,
                                                MT5_API_LOCK)
            with MT5_API_LOCK:
                # Đăng nhập bằng thông tin trong `.env` nếu có. Gọi `initialize()`
                # trần chỉ gắn vào terminal đang mở — nếu terminal đang đăng nhập tài
                # khoản KHÁC thì bảng hiện số của tài khoản đó mà không ai biết.
                kw = {"path": MT5_PATH} if MT5_PATH else {}
                if LOGIN and PASSWORD and SERVER:
                    ok = mt5.initialize(login=LOGIN, password=PASSWORD,
                                        server=SERVER, **kw)
                    # DỰ PHÒNG `mt5.login()` — mượn từ `mt5_bridge.init_mt5()` của
                    # hệ XAUUSD. `initialize(login=…)` thất bại khi terminal vừa mở
                    # và chưa nối xong tới server: nó trả -6 AUTHORIZATION_FAILED
                    # dù thông tin đăng nhập ĐÚNG. Gọi `login()` trên phiên đã gắn
                    # được thì qua, vì lúc đó terminal đã sẵn sàng.
                    #
                    # Đo trên VPS 16/08/2026: -6 lúc 09:28:38, kết nối được lúc
                    # 09:28:43 — cùng thông tin đăng nhập, cách nhau đúng một chu kỳ.
                    if not ok and mt5.initialize(**kw):
                        try:
                            ok = bool(mt5.login(login=int(LOGIN), password=PASSWORD,
                                                server=SERVER))
                        except Exception:
                            ok = False
                else:
                    ok = mt5.initialize(**kw)
                if not ok:
                    self.state["mt"] = self.state["mt5_connected"] = False
                    err = mt5.last_error()
                    self._mt5_fail_streak = getattr(self, "_mt5_fail_streak", 0) + 1
                    detail = (
                        f"{err}"
                        + (f" · path={MT5_PATH}" if MT5_PATH else
                           " · .env CHƯA khai MT5_PATH (bắt buộc khi có nhiều "
                           "terminal đang chạy)")
                        + (f" · login={LOGIN} server={SERVER}" if LOGIN
                           else " · .env chưa khai MT5_LOGIN"))
                    # ÂN HẠN KHỞI ĐỘNG — cách xử lý của `mt5_bridge.init_mt5()` bên
                    # XAUUSD: nó thử tới 8 lần với backoff (~63 giây) trước khi kêu,
                    # vì terminal cần vài giây để nối tới server sau khi mở.
                    #
                    # Ở đây không ngủ trong vòng lặp (nhịp 5 giây phải giữ cho các
                    # cổng rủi ro chạy đúng), nên ân hạn tính bằng SỐ LẦN thất bại
                    # LIÊN TIẾP. Dưới ngưỡng thì báo nhẹ, quá ngưỡng mới ⛔.
                    #
                    # Không bỏ hẳn dòng dưới ngưỡng: im lặng hoàn toàn thì lúc hệ
                    # thật sự hỏng, mười giây đầu không có gì để lần ra.
                    if self._mt5_fail_streak < MT5_FAIL_GRACE:
                        self.log(f"⏳ Đang chờ MT5 sẵn sàng "
                                 f"({self._mt5_fail_streak}/{MT5_FAIL_GRACE}) — {err}")
                    else:
                        # `log_first=True`: nếu MT5 chưa bao giờ kết nối được thì đây
                        # là dòng DUY NHẤT nói được vì sao. Xem `_log_change`.
                        self._log_change("mt5", "0",
                                         f"⛔ MT5 KHÔNG kết nối được: {detail}",
                                         log_first=True)
                    self._on_mt5_lost()
                    self.state["positions_read_error"] = f"MT5 không kết nối: {detail}"
                    return
            self.state["mt"] = self.state["mt5_connected"] = True
            self.state["positions_read_error"] = ""
            # Phân biệt LẦN ĐẦU với KẾT NỐI LẠI: "đã kết nối lại" khi chưa từng kết
            # nối là một câu sai, và nó làm người đọc tưởng vừa có một lần rớt.
            first = self._last_state.get("mt5") is None
            self._log_change("mt5", "1",
                             "🔌 MT5 đã kết nối" if first else "MT5 đã kết nối lại",
                             log_first=True)
            self._mt5_fail_streak = 0
            self._on_mt5_back()

            with MT5_API_LOCK:
                ai = mt5.account_info()
            if ai is not None:
                # `state["account"]` phải là DICT, không phải số login.
                # `gui_command_center` làm `state.get("account") or state.get(
                # "account_info")` rồi gọi `.get("server")` — đặt int vào đây thì
                # `int.get` ném AttributeError, khối try nuốt, và ba thẻ SERVER ·
                # ACCOUNT · FTMO MODE về N/A trong khi dữ liệu vẫn đầy đủ ở
                # `account_info`. Lỗi im lặng, không có gì để lần ra.
                self.state["equity"] = float(ai.equity)
                from src.python.core.config import APP_ENV, BOT_NAME, FTMO_PHASE
                self.state["account_info"] = {
                    "login": ai.login, "server": ai.server, "currency": ai.currency,
                    "balance": float(ai.balance), "equity": float(ai.equity),
                    "margin": float(ai.margin), "margin_free": float(ai.margin_free),
                    "margin_level": float(ai.margin_level or 0.0),
                    "profit": float(ai.profit), "leverage": int(ai.leverage),
                    "name": ai.name, "company": ai.company,
                    "is_demo": "demo" in str(ai.server).lower(),
                    # ba mục dưới đây đến từ `.env`, không phải từ broker — thẻ trên
                    # bảng hiện chúng để biết đang chạy môi trường nào
                    "app_env": APP_ENV, "bot_name": BOT_NAME, "ftmo_phase": FTMO_PHASE,
                }
                self.state["account"] = self.state["account_info"]
                self._check_account_identity(ai.login, ai.server, LOGIN)
                self.state["daily_profit"] = float(ai.equity) - float(ai.balance)

            with MT5_API_LOCK:
                pos = mt5.positions_get()
            self.state["positions_list"] = [
                {"symbol": p.symbol, "type": "BUY" if p.type == 0 else "SELL",
                 "volume": float(p.volume), "price_open": float(p.price_open),
                 "price_current": float(p.price_current),
                 "profit": float(p.profit), "magic": int(p.magic),
                 "comment": p.comment}
                for p in (pos or ())]

            # spread hiện tại của các công cụ đang giao dịch, quy sang BPS
            from src.python.core import strategy_registry as _sr
            syms = sorted({s for g in _sr.live() for s in g.symbols})
            sp: Dict[str, float] = {}
            # `symbol_select` là BẮT BUỘC trước lần đọc đầu: symbol không nằm trong
            # Market Watch thì `symbol_info` trả bid/ask = 0. Và phải CHỌN HẾT trước
            # rồi mới ĐỌC — chọn xong đọc ngay thì terminal chưa kịp nạp tick đầu tiên
            # và 20 cross biến mất khỏi bảng spread mà không có lỗi nào. Tách hai vòng
            # cho terminal thời gian nạp trong lúc ta còn đang chọn các symbol sau.
            if not self._selected.issuperset(syms):
                with MT5_API_LOCK:
                    for s in syms:
                        mt5.symbol_select(s, True)
                self._selected.update(syms)
            px: Dict[str, float] = {}
            for s in syms:
                with MT5_API_LOCK:
                    info = mt5.symbol_info(s)
                if info is None or info.ask <= 0:
                    continue
                mid = (info.ask + info.bid) / 2.0
                if mid > 0:
                    sp[s] = round((info.ask - info.bid) / mid * 1e4, 2)
                    # GIÁ GIỮA giữ luôn ở đây: `order_plan` cần nó để quy tỷ trọng
                    # sang lot, và cặp chéo còn cần giá của 7 major để đổi notional
                    # sang USD. Đọc riêng một lượt nữa là hai ảnh chụp lệch thời
                    # điểm — lot tính trên giá này còn cầu chì đặt trên giá kia.
                    px[s] = mid
            self.state["spread"] = sp
            self.state["prices"] = px
        except Exception as exc:                           # pragma: no cover
            self.state["positions_read_error"] = f"{type(exc).__name__}: {exc}"

    def _log_change(self, key: str, value: str, msg: str,
                    log_first: bool = False) -> None:
        """Chỉ ghi log khi giá trị ĐỔI so với lần trước.

        Trạng thái ổn định không cần nhắc lại mỗi 5 giây; cái người vận hành cần
        thấy là THỜI ĐIỂM nó đổi.

        `log_first=True` ghi CẢ lần đầu. Cần cho các trạng thái HỎNG: quy tắc "lần
        đầu thì im" sinh ra để chặn spam lúc khởi động, nhưng với một thứ chưa bao
        giờ hoạt động thì lần đầu CŨNG LÀ lần duy nhất — và nó bị nuốt.

        Đo được trên VPS ngày 16/08/2026: MT5 không kết nối được ngay từ lượt đầu,
        nên `_last_state["mt5"]` chưa có giá trị nào, nên `mt5.last_error()` KHÔNG
        BAO GIỜ được ghi. Người vận hành chỉ thấy "DISCONNECTED" và "KHÔNG ĐỌC ĐƯỢC
        VỊ THẾ" — hai câu không nói được nguyên nhân, mà nguyên nhân thì đã nằm sẵn
        trong tay hệ thống.
        """
        prev = self._last_state.get(key)
        if prev != value:
            self._last_state[key] = value
            if prev is not None or log_first:
                self.log(msg)

    def _read_guards(self) -> None:
        """Trạng thái các cổng chặn.

        BA KHOÁ `trades_today` · `consec_loss` · `dd_pct` · `breaker_tripped` là thứ
        `gui_command_center` đọc để tô thẻ GUARD SYSTEM. Thiếu chúng thì thẻ hiện N/A
        và cầu dao trên bảng đứng im ở MONITORING kể cả khi đã chạm ngưỡng — tức bảng
        nói "an toàn" đúng lúc không an toàn.
        """
        g: Dict[str, Any] = {}

        # ── FTMO: cập nhật mốc ngày/tuần/tháng từ equity THẬT.
        # Không gọi thì `initial_balance` và `day_start_balance` đứng ở 0, và mọi
        # phép tính sụt vốn chia cho 0 hoặc so với mốc sai — thẻ FTMO trên bảng hiện
        # số vô nghĩa mà trông vẫn như số thật.
        try:
            from src.python.core.infra import ftmo
            eq = self.state.get("equity")
            acc = self.state.get("account_info") or {}
            if eq:
                st = ftmo.update_baselines(float(eq), balance=acc.get("balance"))
                g["ftmo"] = {
                    "phase": st.get("phase"),
                    "initial_balance": st.get("initial_balance"),
                    "day_start_balance": st.get("day_start_balance"),
                    "trading_days": len(st.get("trading_days") or []),
                }
        except Exception as exc:                       # pragma: no cover
            g["ftmo"] = {"error": str(exc)}

        # ── cổng rủi ro tài khoản, đọc từ `risk_guard` (kế thừa nguyên vẹn)
        try:
            from src.python.core.infra import risk_guard
            from src.python.core.config import (INP_DAILY_LOSS_CAP_PCT,
                                                INP_KILL_SWITCH_DD_PCT)
            rg = risk_guard.state
            eq = self.state.get("equity")
            eq0 = rg.get("day_start_equity")
            dd = 0.0
            if eq and eq0 and float(eq0) > 0:
                dd = max(0.0, (float(eq0) - float(eq)) / float(eq0) * 100.0)
            tripped = bool(rg.get("halt_reason")) or dd >= INP_KILL_SWITCH_DD_PCT
            g.update({
                "trades_today": int(rg.get("trades_today", 0) or 0),
                "consec_loss": int(rg.get("consec_loss", 0) or 0),
                "dd_pct": round(dd, 2),
                "breaker_tripped": tripped,
                "halt_reason": rg.get("halt_reason") or "",
                "day_start_equity": eq0,
                "daily_cap_pct": INP_DAILY_LOSS_CAP_PCT,
                "kill_switch_pct": INP_KILL_SWITCH_DD_PCT,
            })
            self._log_change("breaker", str(tripped),
                             (f"CẦU DAO BẬT · sụt vốn ngày {dd:.2f}% "
                              f"(ngưỡng {INP_KILL_SWITCH_DD_PCT}%) · "
                              f"{rg.get('halt_reason') or 'chạm ngưỡng'}")
                             if tripped else "cầu dao đã nhả — mở lệnh trở lại")
            self._risk_emails(dd=dd, tripped=tripped,
                              equity=float(eq or 0.0), day_start=float(eq0 or 0.0),
                              halt_reason=str(rg.get("halt_reason") or ""),
                              warn_pct=float(INP_DAILY_LOSS_CAP_PCT),
                              halt_pct=float(INP_KILL_SWITCH_DD_PCT))
        except Exception as exc:                       # pragma: no cover
            g.update({"trades_today": 0, "consec_loss": 0, "dd_pct": 0.0,
                      "breaker_tripped": False, "guard_error": str(exc)})
        try:
            from src.python.ai import news_guard as NG
            d = NG.decide()
            g["news"] = {
                "blocked": d.blocked, "source": d.source, "severity": d.severity,
                "events": list(d.events), "reason": d.reason,
                "enabled": NG.is_enabled()}
        except Exception as exc:
            g["news"] = {"blocked": False, "source": "ERROR", "reason": str(exc)}
        try:
            from src.python.core.config import SPREAD_CAP_BPS
            sp = self.state.get("spread") or {}
            over_cap = {k: v for k, v in sp.items() if v > SPREAD_CAP_BPS}
            g["spread"] = {"cap_bps": SPREAD_CAP_BPS, "over": over_cap,
                           "blocked": bool(over_cap)}
        except Exception:
            pass
        self.state["guards"] = g
        n = g.get("news", {})
        self._log_change("news", str(n.get("blocked")),
                         f"cổng tin {'CHẶN' if n.get('blocked') else 'THÔNG'} · "
                         f"{n.get('reason', '')[:90]}")
        # Spread cuối tuần là giá đóng băng và luôn giãn gấp nhiều lần (đo được:
        # AUDNZD 12,22 bps so với trần 3,0). Cảnh báo lúc đó là báo động giả đều đặn
        # mỗi cuối tuần, và báo động giả lặp lại làm người vận hành ngừng đọc log.
        # Cuối tuần: BỎ HẲN cổng này, không truyền dict rỗng vào.
        # Truyền `{}` làm `cap_bps` thành `None` và sinh ra dòng vô nghĩa
        # "spread mọi công cụ đã về dưới trần None bps" ngay khi thị trường đóng —
        # một chuyển-trạng-thái GIẢ do chính cách bỏ qua tạo ra.
        if not self.state.get("market_closed"):
            self._log_spread_gate(g.get("spread", {}))

    # Số công cụ phải đổi ít nhất bằng đây mới coi là "đổi đáng kể" và ghi lại.
    _SPREAD_STEP = 5
    # Đang giãn liên tục thì nhắc lại mỗi ngần này giây, để không ai tưởng hệ treo.
    # 15 phút: quãng giãn quanh giao ca ngày dài ~50 phút, tức ~3 dòng cho cả đợt.
    _SPREAD_REMIND = 900.0

    def _log_spread_gate(self, spread_state: Dict[str, Any]) -> None:
        """Cổng spread: ghi lúc ĐỔI TRẠNG THÁI, không ghi lại mỗi nhịp.

        NGUỒN SPAM SỐ MỘT CỦA CẢ HỆ — đo trên nhật ký VPS 18/08/2026
        ============================================================
        Từ 04:11 tới 05:00 (49 phút) nhật ký có **~590 dòng** như nhau, mỗi 5 giây một
        dòng, mỗi dòng liệt kê đủ 20 công cụ:

            04:11:34 | spread VƯỢT trần 3.0 bps: AUDCAD 7.0, AUDCHF 8.85, AUDJPY 6.27, …
            04:11:38 | spread VƯỢT trần 3.0 bps: AUDCAD 7.0, AUDCHF 8.85, AUDJPY 6.35, …

        Hai lớp khử lặp ĐÃ CÓ mà cả hai đều không chặn được, vì cùng một lý do:

          · `log()` so sánh NGUYÊN VĂN dòng log. Con số bps đổi mỗi tick, nên hai dòng
            liền nhau không bao giờ giống hệt.
          · `_log_change` so sánh `str(sorted(over.items()))` — tức dấu vân tay CÓ
            CHỨA chính những con số đổi liên tục ấy.

        Bài học: dấu vân tay của một trạng-thái phải chỉ chứa phần ĐỊNH TÍNH. Nhồi số
        đo vào khoá dedup là tự vô hiệu hoá lớp dedup mà vẫn tưởng đang có nó.

        Thời điểm 04:11–05:00 giờ máy = 23:11–00:00 giờ Praha, tức đúng quãng giao ca
        ngày của broker: spread giãn gấp 3–5 lần là chuyện BÌNH THƯỜNG, xảy ra MỖI
        NGÀY. Nên đây không phải sự cố cần báo 590 lần; nó là một trạng thái cần báo
        hai lần — lúc vào và lúc ra.

        BA MỨC, KHÔNG PHẢI MỘT
        =======================
          1. VÀO/RA trạng thái giãn — luôn ghi. Đây là thứ người vận hành cần.
          2. Đang giãn mà số công cụ đổi ĐÁNG KỂ (≥ `_SPREAD_STEP`) — ghi lại, vì
             "3 công cụ giãn" và "24 công cụ giãn" là hai tình huống khác nhau.
          3. Đang giãn, số lượng gần như không đổi — IM, tối đa một dòng nhắc mỗi
             `_SPREAD_REMIND` để không ai tưởng hệ đã treo.

        Danh sách đầy đủ 20 công cụ KHÔNG vào console: nó nằm trong
        `state["guards"]["spread"]["over"]` (bảng trạng thái đọc được bất cứ lúc nào)
        và trong sổ JSONL. Console chỉ cần đếm và ba cái tệ nhất.
        """
        over = spread_state.get("over") or {}
        cap = spread_state.get("cap_bps")
        total = len(self.state.get("spread") or {}) or len(over)
        prev_n = self._spread_over_n
        now = time.time()

        if not over:
            self._spread_over_n = 0
            self._spread_logged_at = 0.0
            if prev_n:
                self.log(f"spread mọi công cụ đã về dưới trần {cap} bps "
                         f"(vừa rồi {prev_n} công cụ vượt)")
            return

        worst = sorted(over.items(), key=lambda kv: -kv[1])[:3]
        detail = " · ".join(f"{k} {v:.1f}" for k, v in worst)
        big_change = abs(len(over) - prev_n) >= self._SPREAD_STEP
        stale = now - self._spread_logged_at >= self._SPREAD_REMIND
        if prev_n == 0 or big_change or stale:
            self._spread_over_n = len(over)
            self._spread_logged_at = now
            self.log(f"spread VƯỢT trần {cap} bps: {len(over)}/{total} công cụ "
                     f"(tệ nhất {detail}) — chi tiết trong thẻ GUARD/sổ JSONL")
        # KHÔNG có nhánh `else`, và đó là chủ ý: `_spread_over_n` giữ số đếm của LẦN
        # GHI gần nhất, không phải của nhịp gần nhất. Cập nhật nó mỗi nhịp thì một
        # chuỗi thay đổi +1 liên tiếp sẽ trôi từ 3 lên 24 công cụ mà không nhịp nào
        # vượt ngưỡng "đổi đáng kể" — tức im lặng đúng lúc tình hình xấu dần.

    def _risk_emails(self, *, dd: float, tripped: bool, equity: float,
                     day_start: float, halt_reason: str,
                     warn_pct: float, halt_pct: float) -> None:
        """Ba mức cảnh báo rủi ro, mỗi mức một thư, mỗi thư một chủ đề dedup riêng.

        Chia ba chủ đề chứ không một là có chủ ý: sụt vốn đi lên thì người vận hành
        phải nhận đủ CẢ BA mốc. Gộp một chủ đề thì thư "cảnh báo" ở mốc thấp sẽ nuốt
        mất thư "đã dừng" ở mốc cao trong cùng một TTL — đúng lúc cần biết nhất.

        Ngưỡng lấy từ `.env` (`KILL_SWITCH_DD_PCT`), KHÔNG viết cứng ở đây.
        """
        from functools import partial

        try:
            from src.python.shared.notifications import emails as EM
            from src.python.utils import alerts

            if dd <= 0.0 or day_start <= 0.0:
                return
            if tripped:
                alerts.once("day_halt",
                            partial(EM.day_halt,
                                    reason=halt_reason or f"sụt vốn ngày {dd:.2f}%",
                                    equity=equity, day_start=day_start, dd_pct=dd),
                            ttl_sec=12 * 3600.0)
            elif dd >= warn_pct:
                alerts.once("drawdown_warning",
                            partial(EM.drawdown_warning,
                                    equity=equity, day_start=day_start,
                                    dd_pct=dd, threshold_pct=warn_pct),
                            ttl_sec=6 * 3600.0)
        except Exception as exc:                           # pragma: no cover
            _log_incident("email cảnh báo rủi ro", exc)

    def _maybe_read_portfolio(self) -> None:
        """Chạy backtest danh mục nếu tới hạn VÀ chưa có lượt nào đang chạy.

        Hai lớp chặn, và cần cả hai:
          · `_portfolio_lock` chặn hai luồng cùng vào — `acquire(blocking=False)` để
            luồng đến sau đi tiếp làm việc khác thay vì đứng chờ 40 giây.
          · mốc thời gian tính từ lúc lượt trước KẾT THÚC. Tính từ lúc bắt đầu thì
            một lượt chạy 40 giây chỉ còn cách lượt sau đúng `PORTFOLIO_EVERY − 40`,
            và khi máy chậm thì hai lượt dính vào nhau.
        """
        if time.time() - self._last_portfolio <= PORTFOLIO_EVERY:
            return
        if not self._portfolio_lock.acquire(blocking=False):
            return                      # đã có lượt đang chạy — bỏ qua, không xếp hàng
        try:
            # KHÔNG bật cờ `busy` ở đây (quyết định 16/08/2026, người vận hành):
            # backtest danh mục là việc NỀN chạy lại mỗi `PORTFOLIO_EVERY`, không
            # phải việc người vận hành đang chờ. Hiện nó lên giao diện làm hàng
            # TIẾN TRÌNH nhấp nháy suốt phiên và biến chỉ báo thành nhiễu — chỉ báo
            # lúc nào cũng sáng thì không còn nói được điều gì.
            #
            # Cờ `busy` chỉ dành cho quãng KHỞI ĐỘNG, lúc màn hình chưa có gì để
            # hiện và người vận hành thật sự đang chờ.
            self._read_portfolio()
        finally:
            self._last_portfolio = time.time()
            self._portfolio_lock.release()

    def _read_portfolio(self) -> None:
        """Chỉ số danh mục. NẶNG — backtest 14 chân mất ~40 giây."""
        try:
            import numpy as np
            import pandas as pd
            from src.python.strategies import portfolio as PF
            from src.python.strategies import registry as REG

            from src.python.shared import fx_data as FXD

            t0 = time.time()
            # ÉP PARQUET: backtest cần 6,5 năm cố định. Trên VPS có
            # `FX_BARS_FROM_MT5=1`, `load_m1` trả nến MT5 = 200.000 nến M1 ≈ 6,6
            # THÁNG — mẫu ngắn hơn 11 lần, mà mọi chỉ số vẫn được báo như số toàn
            # mẫu. Xem `fx_data.parquet_only()`.
            with FXD.parquet_only():
                res = PF.backtest()
            n = res.net
            cum = n.cumsum()
            yr = n.groupby(n.index.year).sum()
            form = pd.Timestamp("2024-01-01")

            def sh(s):
                sd = float(s.std(ddof=1))
                return (round(float(s.mean()) / sd * float(np.sqrt(252)), 3)
                        if sd > 0 else float("nan"))

            G = PF.group_correlation(res)
            cols = list(G.columns)
            mx = max((abs(float(G.loc[a, b])) for a in cols for b in cols if a != b),
                     default=0.0)
            self.state["portfolio"] = {
                "name": REG.PORTFOLIO["name"], "stage": REG.PORTFOLIO["stage"],
                "n_strategies": len(REG.STRATEGIES),
                "n_groups": len(PF.RISK_GROUPS),
                "sharpe_all": sh(n), "sharpe_form": sh(n[n.index < form]),
                "sharpe_oos": sh(n[n.index >= form]),
                "max_dd_sd": round(float((cum.cummax() - cum).max()), 2),
                "worst_day_sd": round(float(n.min()), 2),
                "years_positive": f"{int((yr > 0).sum())}/{len(yr)}",
                "max_group_corr": round(mx, 3),
                "leverage_cap": REG.PORTFOLIO.get("leverage_cap"),
            }
            # KHÔNG log chỉ số danh mục. Chúng là TRẠNG THÁI, đã nằm trong
            # `state["portfolio"]` và hiện trên thẻ giao diện; in mỗi giờ chỉ làm
            # sổ log đầy những dòng giống hệt nhau.
        except FileNotFoundError as exc:
            # Trên VPS không có 620 MB parquet lịch sử. Đó là chuyện BÌNH THƯỜNG —
            # backtest cần nó, giao dịch live thì không. Ghi MỘT LẦN kèm cách sửa
            # thay vì lặp lại mỗi giờ: một lỗi đã biết mà lặp mãi thì người vận hành
            # ngừng đọc log, và dòng thật sự quan trọng chìm theo.
            self.state["portfolio"] = {"error": "thiếu dữ liệu lịch sử (parquet)"}
            self._log_change(
                "portfolio_data", "missing",
                f"BỎ QUA backtest danh mục — thiếu dữ liệu lịch sử. "
                f"Đây là bình thường trên VPS: backtest cần parquet 620 MB, giao "
                f"dịch live thì KHÔNG. Đặt FX_BARS_FROM_MT5=1 trong .env để chân "
                f"lấy nến thẳng từ MT5. ({exc.__class__.__name__})")
        except Exception as exc:                           # pragma: no cover
            self.state["portfolio"] = {"error": f"{type(exc).__name__}: {exc}"}
            self.log_error(f"làm mới danh mục: {exc}")
