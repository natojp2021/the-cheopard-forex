"""live_server.py — ĐIỂM VÀO của The Cheopard Forex (CLI và GUI).

KẾ THỪA BỐ CỤC TỪ THE CHEOPARD
===============================
Giữ nguyên vai trò và tên của bản XAUUSD: một điểm vào duy nhất, hai chế độ (`--cli`
và GUI), STOP_FILE cho phép dừng êm từ bên ngoài, và màn hình chờ vì khởi động mất
vài chục giây.

BA THỨ THÊM VÀO — mỗi thứ vá một lỗi ĐÃ XẢY RA
===============================================
1. **CHỐNG CHẠY NHIỀU BẢN.** Ngày 14/08 có bốn tiến trình cùng chạy (hai từ 9:31,
   hai từ 9:36) vì mỗi lần nhấn launcher lại mở thêm một bản. Người dùng nhìn cửa sổ
   của bản CŨ và tưởng code mới không được nạp. Nay bản thứ hai phát hiện bản đang
   chạy, ĐƯA CỬA SỔ CŨ LÊN TRƯỚC rồi tự thoát.

2. **ĐẶT TÊN CỬA SỔ.** Bản trước để customtkinter tự đặt, và tiêu đề ra là "CTk" —
   trên thanh tác vụ không phân biệt được với bất kỳ app Python nào khác, kể cả hệ
   XAUUSD nếu chạy song song.

3. **BÁO LỖI THẤY ĐƯỢC.** `pythonw` không có console nên mọi traceback biến mất.
   Lỗi khởi động nay hiện thành hộp thoại.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.python.core.config import LIVE_DIR, LOCK_FILE, BOT_NAME  # noqa: E402

STOP_FILE = Path(LIVE_DIR) / "STOP_REQUESTED"
WINDOW_TITLE = f"{BOT_NAME} — Quant Trading Command Center"

# Nhịp giữa hai bước của màn hình chờ, mili giây. 180 lấy nguyên từ bản XAUUSD.
#
# Là hằng số MODULE chứ không phải số viết thẳng: nó là thứ duy nhất cần đổi để
# giữ splash mở lâu hơn khi kiểm tra hiển thị bằng ảnh chụp màn hình, và một hằng
# số có tên thì không ai phải sửa vào giữa thân hàm để làm việc đó.
SPLASH_STEP_MS = 180


def _preload_config() -> None:
    from src.python.core import config              # noqa: F401
    from src.python.utils import env_loader         # noqa: F401


def _preload_build() -> None:
    from src.python.core.runtime_meta import version
    version()


def _preload_mt5() -> None:
    import MetaTrader5                              # noqa: F401


def _preload_guards() -> None:
    from src.python.core.infra import ftmo, ftmo_guard          # noqa: F401
    from src.python.execution import entry_gate                 # noqa: F401
    from src.python.execution import ftmo_leverage_policy       # noqa: F401
    from src.python.strategies import registry                  # noqa: F401


# CÁC BƯỚC của màn hình chờ: (dòng chữ, tỷ lệ thanh, việc làm THẬT).
#
# Ở CẤP MODULE chứ không nằm trong `_splash` vì `perform_load` NUỐT lỗi của từng
# bước — không nuốt thì một module đổi tên sẽ chặn cả đường khởi động vì một cửa sổ
# trang trí. Nhưng nuốt lỗi nghĩa là hỏng mà im lặng, nên phải có test gọi thẳng
# từng hàm nạp: `tests/test_live_server_splash.py`.
#
# Bản XAUUSD chỉ đếm 180 ms mỗi bước rồi đổi chữ — thanh tiến trình nói "Đang kiểm
# tra kết nối MT5" trong khi không kiểm gì. Ở đây mỗi bước nạp thật nhóm module
# tương ứng: dòng chữ không nói dối, và phần import nặng chạy xong TRƯỚC khi dựng
# cửa sổ chính, tức lấp đúng quãng người vận hành phải chờ.
SPLASH_STEPS = (
    ("Đang nạp cấu hình hệ thống...", 0.2, _preload_config),
    ("Đang kiểm tra Git metadata...", 0.4, _preload_build),
    ("Đang kiểm tra kết nối MT5...", 0.6, _preload_mt5),
    ("Đang nạp các chỉ số bảo vệ Guard...", 0.8, _preload_guards),
    ("Hoàn tất! Đang hiển thị bảng điều khiển...", 1.0, None),
)


# ═══════════════════════════════════════════════════════ chạy lệnh hệ thống ẨN
def _run_hidden(cmd: list, timeout: float = 5.0):
    """Chạy `cmd` mà KHÔNG chớp cửa sổ console. Trả `stdout` (chữ thường), hoặc "".

    VÌ SAO CẦN CỜ NÀY
    ==================
    `pythonw.exe` không có console, nên mỗi `subprocess.run` gọi một lệnh console
    (`tasklist`, `taskkill`, `git`) làm Windows CẤP một cửa sổ mới — nó hiện lên rồi
    tắt trong tích tắc. `capture_output=True` chỉ chuyển hướng luồng ra, KHÔNG ngăn
    cửa sổ được cấp.

    Số lần chớp không nhỏ: `_terminate` gọi `_pid_is_alive` mỗi 0,3 giây trong tối đa
    8 giây, tức tới ~27 cửa sổ nhấp nháy liên tiếp mỗi lần nhấn VBS để nạp bản mới.
    Đúng thứ người vận hành báo ngày 15/08/2026.

    `CREATE_NO_WINDOW` (0x08000000) là cách hệ XAUUSD xử lý — xem
    `core/runtime_meta._git` ở cả hai repo.
    """
    import subprocess

    flags = 0x08000000 if os.name == "nt" else 0
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=timeout, creationflags=flags)
        return (out.stdout or "").lower()
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════ chống chạy nhiều bản
def _pid_is_alive(pid: int) -> bool:
    """Tiến trình `pid` còn sống VÀ đúng là bản chạy của hệ này?

    Chỉ kiểm tra pid tồn tại là chưa đủ: Windows tái dùng pid, nên một pid cũ có thể
    đang thuộc về chương trình khác và ta sẽ từ chối khởi động vì một lý do sai.
    """
    return "python" in _run_hidden(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"])


def _acquire_lock() -> bool:
    """Ghi khoá. Trả False nếu đã có bản khác đang chạy."""
    try:
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        if LOCK_FILE.exists():
            try:
                pid = int(LOCK_FILE.read_text(encoding="utf-8").strip() or 0)
            except (ValueError, OSError):
                pid = 0
            if pid and pid != os.getpid() and _pid_is_alive(pid):
                return False
        LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except Exception:
        return True             # không khoá được thì cho chạy — fail-soft


def _running_pid() -> int:
    """PID ghi trong tệp khoá, hoặc 0."""
    try:
        return int(LOCK_FILE.read_text(encoding="utf-8").strip() or 0)
    except (ValueError, OSError):
        return 0


def _other_instance_pids() -> list:
    """PID của MỌI tiến trình đang chạy `-m src.python.live_server`, trừ chính mình.

    VÌ SAO KHÔNG DÙNG PID TRONG TỆP KHOÁ
    =====================================
    Tệp khoá chỉ nhớ ĐÚNG MỘT pid — bản chạy gần nhất. Bản nào chết mà không nhả
    khoá, hoặc hai bản khởi động cùng lúc, là có một tiến trình sống sót mà không ai
    còn tham chiếu tới. Đo được lúc 13:33 ngày 15/08/2026: hai bản cùng chạy, một
    bản từ 12:34 chạy mã CŨ. Cả hai cùng ghi vào `logs/timeline_*.log`, nên sổ log
    trộn dòng của hai bản — và người vận hành thấy đúng những dòng vừa được xoá
    khỏi mã nguồn, kết luận rằng bản sửa không có tác dụng. Sáu vòng sửa log trước
    đó không sai; chúng chỉ bị một tiến trình ma nói đè lên.

    Thêm nữa, `pythonw.exe` trong `.venv311\Scripts` là một shim: nó nạp trình
    thông dịch nền rồi giữ vai trò TIẾN TRÌNH CHA. `taskkill /T` giết cây con của
    pid được chỉ định, KHÔNG giết cha nó — nên diệt theo pid khoá luôn để sót shim.

    Nay quét theo DÒNG LỆNH: mọi tiến trình python có `src.python.live_server` đều
    là một bản của ứng dụng này, dù được khởi động bằng đường nào.
    """
    if os.name != "nt":
        return []
    out = _run_hidden([
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | "
        "Where-Object { $_.CommandLine -like '*src.python.live_server*' } | "
        "Select-Object -ExpandProperty ProcessId"], timeout=20)
    mine = os.getpid()
    pids = []
    for line in out.splitlines():
        line = line.strip()
        if not line.isdigit():
            continue
        pid = int(line)
        if pid != mine and pid not in pids:
            pids.append(pid)
    return pids


def _terminate(pid: int, timeout_s: float = 8.0) -> bool:
    """Dừng tiến trình cũ và ĐỢI nó chết hẳn.

    Phải đợi: `taskkill` trả về ngay, nhưng tiến trình còn giữ tệp khoá và cổng MT5
    thêm một lúc. Chạy bản mới trước khi bản cũ nhả tay là hai bản cùng nói chuyện
    với một terminal MT5.
    """
    import time as _t

    _run_hidden(["taskkill", "/PID", str(pid), "/T", "/F"], timeout=10)
    deadline = _t.monotonic() + timeout_s
    while _t.monotonic() < deadline:
        if not _pid_is_alive(pid):
            try:
                if LOCK_FILE.exists():
                    LOCK_FILE.unlink()
            except OSError:
                pass
            return True
        _t.sleep(0.3)
    return False


def _release_lock() -> None:
    try:
        if LOCK_FILE.exists() and LOCK_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
            LOCK_FILE.unlink()
    except Exception:
        pass


def _bring_window_to_front() -> bool:
    """Tìm cửa sổ của bản đang chạy và đưa nó lên trước. True nếu tìm thấy."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def _on_window(hwnd, _l):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if WINDOW_TITLE in buf.value and user32.IsWindowVisible(hwnd):
                    found.append(hwnd)
            return True

        user32.EnumWindows(_on_window, 0)
        if found:
            user32.ShowWindow(found[0], 9)          # SW_RESTORE
            user32.SetForegroundWindow(found[0])
            return True
    except Exception:
        pass
    return False


def _show_error(msg: str) -> None:
    """Hiện lỗi ra hộp thoại VÀ stderr — tuỳ chế độ chạy mà cái nào đến được."""
    print(msg, file=sys.stderr)
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror(f"{BOT_NAME} — không khởi động được", msg[:2000])
        r.destroy()
    except Exception:
        pass


def _log(msg: str) -> None:
    """Một dòng vào SỔ VÒNG ĐỜI `logs/live/gui_lifecycle.log`. Không bao giờ ném.

    VÌ SAO CÓ SỔ RIÊNG: `pythonw` không có console, nên mọi thứ in ra màn hình đều
    rơi vào hư không. Ngày 14/08 giao diện tự thoát sau vài phút mà KHÔNG để lại dấu
    vết nào — khoá được nhả sạch nên nhìn từ ngoài giống hệt người dùng tự đóng cửa
    sổ. Sổ này là đường duy nhất phân biệt hai chuyện đó.

    Dùng chung cho splash và cho các mốc trong `run_gui` — hai đường ghi riêng là
    hai đường sẽ trôi khỏi nhau, và lúc cần đọc thì thứ tự sự kiện không còn tin được.
    """
    try:
        from datetime import datetime as _dt

        f = Path(LIVE_DIR) / "gui_lifecycle.log"
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(f"{_dt.now().strftime('%Y-%m-%d %H:%M:%S')} "
                     f"pid {os.getpid()} {msg}\n")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════ chế độ CLI
def run_cli() -> int:
    from src.python.core.engine import TradingEngine

    engine = TradingEngine(log_callback=print)
    if not engine.start_loop():
        return 1
    try:
        while engine.is_running:
            if STOP_FILE.exists():
                engine.log("nhận STOP_REQUESTED — dừng êm")
                try:
                    STOP_FILE.unlink()
                except OSError:
                    pass
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        engine.log("dừng bởi người dùng (Ctrl+C)")
    finally:
        engine.stop_loop()
    return 0


# ═══════════════════════════════════════════════════════ chế độ GUI
def _splash() -> None:
    """MÀN HÌNH CHỜ — clone từ `live_server.run_gui()` của hệ XAUUSD.

    Giữ nguyên bố cục và luồng của bản gốc: cửa sổ `overrideredirect` căn giữa
    480×260, khung viền một pixel, tên thương hiệu cỡ 26 đậm, phụ đề, dòng trạng
    thái nghiêng, thanh tiến trình 320×4 vẽ bằng `Canvas`, và `perform_load(step)`
    tự lên lịch qua `after(180, …)`.

    ĐỔI SO VỚI BẢN GỐC — ba chỗ, đều có lý do
    ==========================================
    1. BẢNG MÀU. Bản XAUUSD dùng xanh lá trên nền đen (`#35D875` / `#050805`); hệ
       này là DARK NAVY. Màu lấy thẳng từ `gui_command_center` chứ không chép số:
       splash lệch tông với cửa sổ chính thì lúc chuyển tiếp thành một cú nháy.

    2. CÁC BƯỚC LÀM VIỆC THẬT. Bản gốc chỉ đếm 180 ms mỗi bước rồi đổi chữ — thanh
       tiến trình nói "Đang kiểm tra kết nối MT5" trong khi không kiểm gì. Ở đây
       mỗi bước NẠP THẬT nhóm module tương ứng. Hai cái lợi cộng lại: dòng chữ
       không nói dối, và phần nạp nặng (pandas, chiến lược) chạy XONG trước khi
       dựng cửa sổ chính — đúng phần làm người vận hành chờ lâu nhất.

    3. LỖI KHÔNG LÀM CHẾT KHỞI ĐỘNG. Một bước nạp hỏng chỉ ghi log rồi đi tiếp:
       splash là lớp hiển thị, và module hỏng thật sẽ nổ đúng chỗ của nó ở
       `TradingGUIV2()` với traceback đầy đủ. Chết ở đây là chôn mất traceback ấy.
    """
    import tkinter as tk

    from src.python.core.gui_command_center import (
        C_BG_ROOT, C_BLUE, C_BORDER, C_TEXT_DIM, C_TEXT_MUT)

    splash = tk.Tk()
    splash.title(f"{BOT_NAME} - Loading")
    splash.overrideredirect(True)

    w, h = 480, 260
    sw, sh = splash.winfo_screenwidth(), splash.winfo_screenheight()
    splash.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
    splash.configure(bg=C_BG_ROOT)
    splash.attributes("-topmost", True)
    splash.focus_force()

    border = tk.Frame(splash, bg=C_BORDER, bd=1)
    border.place(relx=0, rely=0, relwidth=1, relheight=1)
    container = tk.Frame(border, bg=C_BG_ROOT)
    container.place(relx=0.01, rely=0.02, relwidth=0.98, relheight=0.96)

    tk.Label(container, text="THE CHEOPARD", font=("Consolas", 26, "bold"),
             fg=C_BLUE, bg=C_BG_ROOT).pack(pady=(45, 8))
    tk.Label(container, text="FX PORTFOLIO QUANTITATIVE SYSTEM",
             font=("Consolas", 10, "bold"),
             fg=C_TEXT_DIM, bg=C_BG_ROOT).pack(pady=(0, 25))

    status_lbl = tk.Label(container, text="Đang khởi động hệ thống...",
                          font=("Consolas", 10, "italic"),
                          fg=C_TEXT_MUT, bg=C_BG_ROOT)
    status_lbl.pack(pady=(0, 8))

    canvas_w = 320
    canvas = tk.Canvas(container, width=canvas_w, height=4, bg=C_BG_ROOT,
                       highlightthickness=0)
    canvas.pack()
    bar = canvas.create_rectangle(0, 0, 0, 4, fill=C_BLUE, width=0)

    def perform_load(step: int = 0) -> None:
        try:
            if step < len(SPLASH_STEPS):
                text, ratio, work = SPLASH_STEPS[step]
                status_lbl.configure(text=text)
                canvas.coords(bar, 0, 0, int(canvas_w * ratio), 4)
                # VẼ TRƯỚC, LÀM SAU: `update()` đẩy khung hình ra màn hình trước khi
                # bước nạp chặn vòng lặp Tk. Đảo thứ tự thì người vận hành thấy chữ
                # của bước TRƯỚC trong suốt lúc bước NÀY chạy.
                splash.update()
                if work is not None:
                    try:
                        work()
                    except Exception as exc:
                        _log(f"[SPLASH] bước {step} ({text}) lỗi: "
                             f"{type(exc).__name__}: {exc}")
                splash.after(SPLASH_STEP_MS, lambda: perform_load(step + 1))
            else:
                splash.destroy()
        except Exception:
            _log("[SPLASH] vỡ: " + traceback.format_exc())
            try:
                splash.destroy()
            except Exception:
                pass

    splash.after(50, lambda: perform_load(0))
    splash.mainloop()


def run_gui() -> int:
    try:
        from src.python.core.gui_command_center import TradingGUIV2
    except ImportError as exc:
        _show_error(f"Thiếu thư viện hoặc module:\n\n{exc}\n\n"
                 f"Cài lại bằng:\n"
                 f"    .venv311\\Scripts\\python.exe -m pip install -r requirements.txt")
        return 1
    except Exception:
        _show_error(traceback.format_exc())
        return 1

    # SỔ VÒNG ĐỜI — ghi mọi mốc khởi động/thoát ra tệp riêng.
    #
    # VÌ SAO CẦN: ngày 14/08 giao diện tự thoát sau vài phút và KHÔNG để lại dấu vết
    # nào — `pythonw` không có console, khoá được nhả sạch nên nhìn từ ngoài giống
    # như người dùng tự đóng. Không có sổ này thì không cách nào biết nó thoát vì
    # cửa sổ bị đóng hay vì mainloop vỡ.
    # Uỷ quyền cho `_log` ở cấp module — cùng một tệp, cùng một định dạng.
    #
    # Bản cũ tự dựng dòng bằng `_dt.now().strftime(chr(37)+chr(89))`, tức mã định
    # dạng `%Y` → chỉ ghi được NĂM. Mọi mốc trong sổ đều mang dấu thời gian "2026",
    # nên không dựng lại được thứ tự sự kiện — đúng thứ mà sổ này sinh ra để làm.
    _milestone = _log

    # MÀN HÌNH CHỜ chạy TRƯỚC khi dựng cửa sổ chính: `TradingGUIV2()` mất vài giây
    # (nạp pandas, chiến lược, dựng 27 hàng ma trận) và trong quãng đó màn hình
    # hoàn toàn trống. Splash lấp đúng quãng đó, và các bước nạp của nó cũng làm
    # ấm sẵn phần import nặng nhất.
    _milestone("splash BẮT ĐẦU")
    try:
        _splash()
    except Exception:
        # Splash chỉ là lớp hiển thị — hỏng thì đi thẳng vào giao diện chính, đừng
        # chặn khởi động vì một cửa sổ trang trí.
        _milestone("splash VỠ (bỏ qua): " + traceback.format_exc())
    _milestone("splash XONG")

    _milestone("BẮT ĐẦU dựng giao diện")
    try:
        gui = TradingGUIV2()
        # Đặt tên cửa sổ TẠI ĐÂY chứ không sửa `gui_command_center`: tệp đó kế thừa
        # nguyên vẹn, và tên bot đến từ `.env` nên nó là việc của điểm vào.
        try:
            gui.root.title(WINDOW_TITLE)
        except Exception:
            pass
        _milestone("đã dựng xong, vào mainloop")
        gui.run()
        _milestone("mainloop KẾT THÚC bình thường (cửa sổ đã đóng)")
    except Exception:
        _milestone("mainloop VỠ: " + traceback.format_exc())
        _show_error(traceback.format_exc())
        return 1
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=f"{BOT_NAME} — điểm vào")
    ap.add_argument("--cli", action="store_true",
                    help="chạy chế độ dòng lệnh, không mở giao diện")
    ap.add_argument("--force", action="store_true",
                    help="bỏ qua khoá chống chạy nhiều bản")
    ap.add_argument("--keep", action="store_true",
                    help="giữ bản đang chạy, chỉ đưa cửa sổ của nó lên trước")
    a, _ = ap.parse_known_args(argv)

    if not a.force and not _acquire_lock():
        # ĐÃ CÓ BẢN ĐANG CHẠY — và từ 15/08/2026 xử lý mặc định là THAY THẾ NÓ.
        #
        # Bản trước đưa cửa sổ CŨ lên trước rồi tự thoát. Ý định đúng (chống mở bốn
        # tiến trình cùng lúc như hôm 14/08) nhưng hệ quả tệ hơn: sau mỗi lần sửa
        # code, nhấn VBS chỉ FOCUS lại tiến trình cũ đang chạy mã cũ, và người vận
        # hành thấy "bản build lúc 12:30" dù đã sửa xong từ lâu. Một cơ chế chống
        # nhân bản biến thành cơ chế khoá cứng vào bản cũ.
        #
        # Nay: dừng bản cũ, rồi chạy bản mới. `--keep` giữ hành vi cũ nếu ai cần.
        old = _running_pid()
        if a.keep:
            if not _bring_window_to_front():
                _show_error(f"{BOT_NAME} ĐANG CHẠY (PID {old}).\n\n"
                            f"Bỏ --keep để tự thay thế, hoặc đóng bản cũ rồi mở lại.")
            return 0
        victims = _other_instance_pids() or ([old] if old else [])
        if victims and all(_terminate(v) for v in victims):
            _milestone("da dung ban cu PID " + ",".join(str(v) for v in victims)
                       + ", khoi dong ban moi")
            _acquire_lock()
        else:
            _show_error(f"{BOT_NAME} ĐANG CHẠY (PID {old}) và KHÔNG dừng được.\n\n"
                        f"Đóng nó bằng tay rồi mở lại, hoặc chạy với --force.\n"
                        f"Khoá: {LOCK_FILE}")
            return 1

    try:
        return run_cli() if a.cli else run_gui()
    finally:
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
