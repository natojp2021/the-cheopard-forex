"""live_server.py — ĐIỂM VÀO của The Cheopard Forex. CONSOLE-ONLY từ 19/08/2026.

VÌ SAO XOÁ HẲN BẢNG ĐIỀU KHIỂN ĐỒ HOẠ
======================================
Bản trước có hai chế độ: `--cli` và một bảng điều khiển customtkinter 1.926 dòng.
Bảng đó bị xoá, không phải "tắt mặc định":

  · CHI PHÍ THẬT. Tk + customtkinter + matplotlib + Pillow nạp vào cùng tiến trình
    với vòng lặp giao dịch. Trên VPS đó là RAM và CPU tiêu cho một cửa sổ mà không
    ai ngồi trước — máy này đã có tiền lệ bị kill vì hết RAM khi chạy song song.
  · RỦI RO THẬT. Ba trong số các sự cố vận hành đã ghi lại đều xuất phát từ tầng
    giao diện chứ không từ logic giao dịch: `pythonw` không có console nên mọi
    traceback biến mất; `_Redirector` thay `sys.stdout` làm logger ghi vào chỗ khác;
    `root.after()` gọi từ luồng nền ném `RuntimeError` và giết luồng nền. Không có
    sự cố nào trong đó tồn tại nếu không có cửa sổ.
  · GIỮ LẠI "CHO TƯƠNG THÍCH" LÀ GIỮ CẢ BA VẤN ĐỀ. Một chế độ không ai dùng vẫn phải
    được nạp, kiểm và bảo trì.

Phần LOGIC trong tệp giao diện cũ không mất: nó chuyển sang `core/ops_view.py` (các
hàm đọc trạng thái) và `core/ops_theme.py` (bảng màu ngữ nghĩa). Phần bị xoá đúng là
phần dựng widget.

BA THỨ GIỮ LẠI TỪ BẢN CŨ — mỗi thứ vá một lỗi ĐÃ XẢY RA
========================================================
1. CHỐNG CHẠY NHIỀU BẢN. Ngày 14/08 có bốn tiến trình cùng chạy vì mỗi lần nhấn
   launcher lại mở thêm một bản; người dùng nhìn bản CŨ và tưởng code mới không được
   nạp. Với console-only nguy cơ còn cao hơn: hai tiến trình cùng gửi lệnh lên MỘT
   tài khoản MT5 là hai bộ quản lý vị thế đánh nhau.
2. STOP_FILE cho phép dừng ÊM từ bên ngoài (watchdog, tác vụ theo lịch) — không dùng
   `taskkill`, vì kill giữa lúc gửi lệnh là chỗ sinh ra vị thế không có SL.
3. BÁO LỖI THẤY ĐƯỢC lúc khởi động. Nay in ra stderr thay vì hộp thoại.

CÁC NÚT BẤM CHUYỂN SANG `ops_ctl`
=================================
Bảng cũ có ba hành động thật, và console-only phải thay được cả ba — nếu không thì đây
là một bước lùi, không phải một bước gọn:

    RUN ENGINE   -> python -m src.python.ops_ctl run
    STOP ENGINE  -> python -m src.python.ops_ctl stop
    FLATTEN ALL  -> python -m src.python.ops_ctl flatten --confirm

Chúng chạy ở TIẾN TRÌNH KHÁC và nói chuyện qua công tắc trên đĩa, nên đổi được từ một
phiên SSH thứ hai mà không chạm vào tiến trình bot. Đó là hơn nút bấm, không phải kém.

ĐÃ XOÁ: `_splash`, `run_gui`, `_show_error` dạng hộp thoại messagebox, `_run_hidden`
với cờ `CREATE_NO_WINDOW`, `_bring_window_to_front`. Cả năm thứ tồn tại chỉ vì có
một cửa sổ và vì `pythonw` không có console — console-only thì không còn cái nào có
nghĩa.
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import time
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.python.core.config import BOT_NAME, LIVE_DIR, LOCK_FILE  # noqa: E402

STOP_FILE = Path(LIVE_DIR) / "STOP_REQUESTED"

# Nhịp kiểm STOP_FILE và kiểm động cơ còn sống, giây.
POLL_SECONDS = 1.0


def _log(msg: str) -> None:
    """SỔ VÒNG ĐỜI — ghi mọi mốc khởi động/thoát ra tệp riêng.

    VÌ SAO CẦN: ngày 14/08 tiến trình tự thoát sau vài phút và KHÔNG để lại dấu vết
    nào. Không có sổ này thì không phân biệt được "người vận hành tự đóng" với "vòng
    lặp chính vỡ" — hai sự cố khác hẳn nhau mà nhìn từ ngoài giống hệt.

    Ghi bằng `strftime` đầy đủ ngày-giờ. Bản đầu dựng dòng bằng mã định dạng `%Y` nên
    mọi mốc trong sổ đều mang dấu thời gian "2026", tức không dựng lại được thứ tự sự
    kiện — đúng thứ mà sổ này sinh ra để làm.
    """
    from datetime import datetime

    try:
        path = Path(LIVE_DIR) / "live_server.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")
    except Exception:
        pass


def _fail(msg: str) -> None:
    """Lỗi khởi động: ra stderr VÀ vào sổ vòng đời.

    Không dùng `messagebox` nữa — một hộp thoại trên VPS là một tiến trình treo vô
    thời hạn chờ người bấm OK, và không ai ở đó để bấm.
    """
    _log("LỖI KHỞI ĐỘNG: " + msg.replace("\n", " | "))
    try:
        sys.stderr.write("\n" + msg + "\n")
        sys.stderr.flush()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════ chống chạy nhiều bản
def _pid_is_alive(pid: int) -> bool:
    """PID này còn sống không.

    Dùng `os.kill(pid, 0)` trên POSIX; trên Windows dùng `tasklist`. Không có
    `CREATE_NO_WINDOW` nữa: console-only thì một cửa sổ con chớp lên không còn là
    vấn đề (bản cũ cần cờ đó vì `pythonw` làm Windows CẤP cửa sổ mới cho mỗi lệnh,
    tới ~27 lần nhấp nháy mỗi lần khởi động).
    """
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import subprocess

    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                             capture_output=True, text=True, timeout=5.0)
        return str(pid) in (out.stdout or "")
    except Exception:
        # KHÔNG kết luận "đã chết" khi không kiểm được: đoán sai theo hướng đó cho
        # phép bản thứ hai khởi động và hai tiến trình cùng gửi lệnh lên một tài
        # khoản. Fail-closed ở đây nghĩa là coi như CÒN SỐNG.
        return True


def _running_pid():
    try:
        return int(Path(LOCK_FILE).read_text(encoding="utf-8").strip() or 0)
    except Exception:
        return None


def _acquire_lock() -> bool:
    """Chiếm khoá. `False` nếu đã có bản khác đang chạy thật."""
    pid = _running_pid()
    if pid and pid != os.getpid() and _pid_is_alive(pid):
        return False
    try:
        path = Path(LOCK_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except Exception:
        # Không ghi được khoá thì VẪN cho chạy: mất lớp chống nhân bản còn nhẹ hơn
        # không chạy được bot vì một tệp khoá.
        return True


def _release_lock() -> None:
    try:
        path = Path(LOCK_FILE)
        if path.is_file() and path.read_text(encoding="utf-8").strip() == str(os.getpid()):
            path.unlink()
    except Exception:
        pass


def _terminate(pid: int, timeout: float = 8.0) -> bool:
    """Dừng ÊM bản cũ: đặt STOP_FILE trước, chỉ kill khi nó không chịu chết.

    Thứ tự này quan trọng. `taskkill` ngay lập tức có thể cắt giữa lúc `order_router`
    đã gửi lệnh mà chưa xác minh xong SL/TP — tức để lại một vị thế không có điểm
    dừng trên tài khoản thật. STOP_FILE đi qua đường dừng có kiểm soát của engine.
    """
    try:
        STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
        STOP_FILE.write_text("stop", encoding="utf-8")
    except Exception:
        pass
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _pid_is_alive(pid):
            return True
        time.sleep(0.3)
    if os.name == "nt":
        import subprocess

        try:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True, timeout=5.0)
        except Exception:
            return False
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            return False
    time.sleep(0.5)
    return not _pid_is_alive(pid)


# ═══════════════════════════════════════════════════════ vòng chạy console
def run_console(*, heartbeat: float, structured: bool, quiet: bool) -> int:
    """Chạy động cơ và trình bày qua `OpsConsole`. Đây là chế độ DUY NHẤT.

    THỨ TỰ CÁC BƯỚC CÓ Ý NGHĨA
    ===========================
    1. Dựng console TRƯỚC engine, và bắc cầu `utils.logger` vào nó ngay. Nếu làm
       ngược, các dòng log phát ra trong lúc engine khởi tạo (nối MT5, đọc pha FTMO,
       đối soát vị thế) sẽ ra theo định dạng cũ và KHÔNG đi qua bộ nén spam.
    2. `start_loop()` trước `boot_report()`: báo cáo khởi động phải đọc trạng thái
       ĐÃ điền, nếu không nó in một bảng toàn "n/a" và chẳng nói được gì.
    3. `shutdown_report()` nằm trong `finally` — nó phải ra CẢ KHI vòng lặp vỡ, vì
       đúng lúc đó người vận hành cần biết còn vị thế nào đang mở.
    """
    from src.python.core.engine import TradingEngine
    from src.python.core.ops_console import OpsConsole
    from src.python.utils import logger as _logger

    console = OpsConsole(heartbeat_seconds=heartbeat, structured=structured,
                         quiet=quiet)
    _logger.attach_console_sink(lambda msg, level: console.event(str(msg)))

    engine = TradingEngine(log_callback=console.log, status_callback=console.status)
    _log("động cơ: bắt đầu khởi động")
    if not engine.start_loop():
        _fail("KHÔNG khởi động được vòng lặp động cơ — xem logs/ để biết nguyên nhân.")
        return 1
    _log("động cơ: vòng lặp đang chạy")

    console.boot_report(engine.state)
    console.strategy_table(engine.state)

    reason = ""
    try:
        while engine.is_running:
            if STOP_FILE.exists():
                reason = "nhận STOP_REQUESTED"
                engine.log("nhận STOP_REQUESTED — dừng êm")
                try:
                    STOP_FILE.unlink()
                except OSError:
                    pass
                break
            time.sleep(POLL_SECONDS)
        else:
            # Ra khỏi `while` mà không `break` nghĩa là `is_running` thành False —
            # tức động cơ tự dừng. Phân biệt với "người vận hành yêu cầu dừng" vì
            # một động cơ tự tắt là một sự cố cần điều tra.
            reason = reason or "động cơ TỰ DỪNG (không do yêu cầu bên ngoài)"
    except KeyboardInterrupt:
        reason = "Ctrl+C"
        engine.log("dừng bởi người dùng (Ctrl+C)")
    except Exception:
        reason = "vòng lặp chính VỠ"
        _log("vòng lặp chính VỠ: " + traceback.format_exc())
        console.event("LỖI · vòng lặp chính vỡ: " + traceback.format_exc(limit=3),
                      category="system", level="error")
    finally:
        try:
            engine.stop_loop()
        except Exception:
            _log("stop_loop lỗi: " + traceback.format_exc())
        # Gỡ cầu log TRƯỚC báo cáo tắt máy: `stop_loop` có thể còn phát log, và một
        # console đã bắt đầu in báo cáo tổng kết thì không nên bị chen dòng vào giữa.
        try:
            _logger.attach_console_sink(None)
        except Exception:
            pass
        console.shutdown_report(reason)
        _log(f"đã thoát ({reason or 'bình thường'})")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=f"{BOT_NAME} — điểm vào (console-only)")
    ap.add_argument("--force", action="store_true",
                    help="bỏ qua khoá chống chạy nhiều bản")
    ap.add_argument("--keep", action="store_true",
                    help="thoát nếu đã có bản đang chạy, thay vì thay thế nó")
    ap.add_argument("--heartbeat", type=float, default=None,
                    help="giây giữa hai nhịp tim (mặc định 45)")
    ap.add_argument("--no-json", action="store_true",
                    help="không ghi sổ JSONL có cấu trúc (chỉ để chẩn đoán)")
    ap.add_argument("--quiet", action="store_true",
                    help="chỉ hiện cảnh báo/lỗi và nhịp tim")
    # `--cli` giữ lại làm cờ KHÔNG TÁC DỤNG, không xoá: `start_live_server.bat`, tài
    # liệu và thói quen của người vận hành đều còn dùng nó. Xoá thì lệnh cũ chết với
    # "unrecognized arguments" — một cái chết vô nghĩa cho thứ giờ đã là mặc định.
    ap.add_argument("--cli", action="store_true", help=argparse.SUPPRESS)
    a, _ = ap.parse_known_args(argv)

    if not a.force and not _acquire_lock():
        old = _running_pid()
        if a.keep:
            _fail(f"{BOT_NAME} ĐANG CHẠY (PID {old}). Bỏ --keep để tự thay thế.")
            return 0
        # MẶC ĐỊNH LÀ THAY THẾ, không phải nhường. Bản trước nhường cho tiến trình
        # cũ, và hệ quả tệ hơn vấn đề nó chữa: sau mỗi lần sửa code, chạy lại chỉ
        # focus vào tiến trình đang chạy MÃ CŨ, và người vận hành thấy build cũ dù
        # đã sửa xong từ lâu. Một cơ chế chống nhân bản biến thành khoá cứng vào
        # bản cũ.
        if old and _terminate(old):
            _log(f"đã dừng bản cũ PID {old}, khởi động bản mới")
            _acquire_lock()
        else:
            _fail(f"{BOT_NAME} ĐANG CHẠY (PID {old}) và KHÔNG dừng được.\n"
                  f"Dừng nó bằng tay rồi chạy lại, hoặc thêm --force.\n"
                  f"Khoá: {LOCK_FILE}")
            return 1

    from src.python.core.ops_console import HEARTBEAT_SECONDS

    try:
        return run_console(
            heartbeat=HEARTBEAT_SECONDS if a.heartbeat is None else a.heartbeat,
            structured=not a.no_json, quiet=a.quiet)
    except Exception:
        _fail("khởi động thất bại:\n" + traceback.format_exc())
        return 1
    finally:
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
