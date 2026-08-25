"""Nhật ký EVENT TIMELINE theo NGÀY — bản ghi đúng như những gì GUI đang hiện.

VẤN ĐỀ:
`logs/YYYY-MM-DD.log` là log THÔ của tiến trình: mỗi dòng mang tiền tố
"YYYY-MM-DD HH:MM:SS: ", còn nguyên các dòng mà GUI cố tình lọc bỏ, còn nguyên
badge "[LEVEL] CATEGORY |" và phần đuôi "| — | —". Nó KHÔNG dựng lại được
Event Timeline, cũng không dán thẳng cho người khác đọc được. Hệ quả: mỗi lần
khởi động lại GUI trong cùng một ngày, bảng timeline trắng trơn — toàn bộ ngữ
cảnh phiên trước (đã vào bao nhiêu lệnh, guard đã chặn gì) biến mất khỏi màn
hình dù engine vẫn đang giữ nguyên state đó.

VÌ SAO CẦN:
Ghi song song MỘT file/ngày ở ĐÚNG định dạng timeline ("HH:MM:SS | nội dung",
y hệt đầu ra của nút COPY) để:
  1. Copy/dán/gửi được nguyên trạng, không phải hậu xử lý.
  2. Đọc lại lịch sử của MỘT NGÀY BẤT KỲ qua `load_day` (nút LOGS DIR).
  3. Nạp ngược lên timeline lúc khởi động — nhưng CHỈ phần do ĐÚNG BẢN BUILD
     đang chạy ghi, qua `load_build`. Xem `mark_build`.

AI GHI (đúng MỘT nguồn cho mỗi chế độ chạy, không bao giờ cả hai):
  - Chế độ GUI: `TradingGUIV2._append_log` — nó thấy MỌI dòng qua stdout
    redirector, kể cả log phát ra từ `utils.logger` của các module khác.
  - Chế độ CLI: `engine.log` và `utils.logger.log` — hai nơi này tự kiểm tra
    "không phải GUI" trước khi gọi vào đây.

ĐỊNH DẠNG FILE: dòng đầu của mỗi bản ghi là "HH:MM:SS | nội dung"; các dòng
tiếp theo của cùng bản ghi (thông điệp nhiều dòng, ví dụ "\\nLý do: ...") được
ghi trần. Khi đọc lại, dòng KHÔNG khớp "HH:MM:SS | " được nối vào bản ghi ngay
trước nó.
"""
from __future__ import annotations

import os
import re
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Chỉ phụ thuộc SSOT đường dẫn (thuần stdlib, không side-effect) — module này
# được `utils/logger.py` import ở cấp module nên tuyệt đối không được kéo theo
# `core.config` hay bất cứ thứ gì khởi tạo MT5.
from src.python.shared.paths import LOG_DIR

# Thư mục đích — để ở cấp module (không phải hằng đóng băng trong hàm) nhằm cho
# test chuyển hướng sang tmp mà không phải chạm vào biến toàn cục của dự án.
TIMELINE_DIR: Path = LOG_DIR
FILE_PREFIX = "timeline_"
TIME_FMT = "%H:%M:%S"

# "HH:MM:SS | nội dung" — mốc nhận diện đầu một bản ghi khi đọc file.
_ENTRY_RE = re.compile(r"^(\d{2}:\d{2}:\d{2}) \| (.*)$")
# Tiền tố thời gian của log thô: "2026-08-11 17:00:34: ".
_STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2} (\d{2}:\d{2}:\d{2}):?\s")
# Định dạng ỐNG của `utils/logger.py`:
#     "2026-08-15 17:27:30 | INFO    | cheopard | nội dung"
#
# Bản trước KHÔNG nhận dạng này, và `_STAMP_RE` cũng không khớp vì sau giây là
# " | " chứ không phải ": ". Hệ quả: cả dòng thô rơi vào phần NỘI DUNG, rồi
# timeline lại đóng thêm giờ của chính nó ở đầu — sinh ra dòng hai dấu ống liên
# tiếp mà người đọc thấy là "17:27:30 | | INFO | cheopard | ...". Mọi dòng do
# module khác phát qua `utils.logger` (mailer, risk_guard, mt5_bridge) đều dính.
_PIPE_STAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2} (\d{2}:\d{2}:\d{2}) \| [A-Z]+\s*\| [^|]*\| ")
# Badge "[LEVEL] CATEGORY | " ở đầu và đuôi "| — | —" mà GUI vẫn cắt bỏ.
_BADGE_RE = re.compile(r"^\s*\[[A-Z0-9_]+\]\s+[A-Z0-9_]+\s*\|\s*")
_TRAIL_RE = re.compile(r"\s*\|\s*(?:[A-Za-z0-9_\-]+|—)\s*\|\s*(?:[A-Za-z0-9_\-]+|—)\s*$")

# Ghi từ nhiều luồng (engine loop, worker email, callback GUI) vào cùng một file.
_write_lock = threading.Lock()

# Các dòng KHÔNG đưa lên timeline (và vì thế cũng không vào file này) — vẫn còn
# đủ trong log thô `logs/YYYY-MM-DD.log`. Mỗi phần tử là bộ từ khoá phải khớp
# ĐỦ thì mới coi là nhiễu.
# Mỗi phần tử là một BỘ từ khoá; dòng chứa ĐỦ cả bộ thì bị ẩn khỏi timeline.
# Dùng bộ nhiều từ chứ không một từ đơn là có chủ ý: "backtest" một mình sẽ nuốt
# luôn những dòng quan trọng như "backtest 14 chân LỖI".
NOISE_PATTERNS: Tuple[Tuple[str, ...], ...] = (
    ("KHÔNG gửi AI", "chỉ số đã ngừng cập nhật"),
    ("[SYMBOL SPEC]", "ĐÃ ĐỐI CHIẾU"),
    ("phiếu", "hỏng"),
    # ── Forex, thêm 14/08/2026
    ("đang làm mới chỉ số danh mục",),     # tiến độ; dòng KẾT QUẢ mới đáng giữ
    ("động cơ CHỈ ĐỌC đã khởi động",),     # lặp mỗi lần bấm RUN
    # ── kênh email, thêm 15/08/2026
    #
    # `utils/mailer.py` ghi một dòng cho MỖI lá thư, kể cả thư bị bỏ qua vì
    # `APP_ENV != PROD`. Với mười lăm loại thư và một thư cho mỗi lệnh vào/ra, đó
    # là nguồn spam lớn nhất còn lại. Bên gọi đã in một dòng TÓM TẮT về kênh email
    # (xem `engine._send_startup_email`), nên các dòng dưới đây chỉ nhân đôi.
    # Chúng vẫn còn NGUYÊN trong log thô `logs/cheopard_forex.log`.
    ("email KHÔNG gửi", "APP_ENV"),
    ("email BỎ QUA", "SMTP"),
    ("đã gửi email:",),
    ("[ALERT]",),
    # ── máy trạng thái lệnh, thêm 15/08/2026
    #
    # `order_state_machine` ghi một dòng cho MỖI lệnh được tạo và MỖI lần chuyển
    # trạng thái. Với nhiều chân tái cân bằng theo giờ, đó là hàng chục dòng mỗi chu
    # kỳ nói lại đúng thứ mà dòng `[OK] AUDCAD OPEN ...` của router đã nói. Vết
    # đầy đủ nằm ở `logs/live/durable_event_log.jsonl` — bền hơn sổ log nhiều.
    ("[STATE_MACHINE]",),
    # Dòng xác nhận cài bẫy lỗi toàn cục — in đúng một lần lúc import `config`,
    # nói một việc hạ tầng mà người vận hành không hành động gì được. Bản thân
    # các LỖI mà nó bắt thì VẪN lên timeline, và đó mới là thứ đáng đọc.
    ("Đã cài đặt Global Exception Hook",),
)


def is_noise(msg: str) -> bool:
    """True nếu dòng log thuộc nhóm bị GUI ẩn khỏi Event Timeline."""
    return any(all(k in msg for k in pattern) for pattern in NOISE_PATTERNS)


def file_log_disabled() -> bool:
    """Tôn trọng đúng công tắc mà `utils.logger` đang dùng cho log thô.

    Backtest/research bật cờ này để không làm bẩn sổ ghi của bản chạy LIVE —
    timeline cũng phải im theo, nếu không cờ đó chỉ chặn được một nửa.

    Tên cờ đổi từ `QUANT_XAU_DISABLE_FILE_LOG` sang `CHEOPARD_FX_DISABLE_FILE_LOG`
    khi chuyển sang Forex: giữ tên cũ thì đặt cờ cho hệ này sẽ làm câm luôn một hệ một-tài-sản
    nếu hai hệ cùng chạy trên một máy.
    """
    return os.environ.get("CHEOPARD_FX_DISABLE_FILE_LOG", "").strip().lower() in {"1", "true", "yes"}


def log_path(day: Optional[Union[datetime, date]] = None) -> Path:
    """Đường dẫn file timeline của một ngày (mặc định: hôm nay)."""
    d = day or datetime.now()
    if isinstance(d, datetime):
        d = d.date()
    return Path(TIMELINE_DIR) / f"{FILE_PREFIX}{d.strftime('%Y-%m-%d')}.log"


def normalize(raw_msg: str) -> Optional[Tuple[str, str]]:
    """Log THÔ -> (giờ "HH:MM:SS", nội dung như trên timeline). None nếu bỏ qua.

    Đây là SSOT của phép biến đổi "log thô -> dòng timeline": GUI dùng nó để vẽ
    hàng, hai nơi ghi CLI dùng nó để ghi file. Tách ra một chỗ để bản trên màn
    hình và bản trong file không bao giờ trôi khỏi nhau.
    """
    if raw_msg is None:
        return None
    msg = str(raw_msg).rstrip("\r\n")
    if not msg.strip() or is_noise(msg):
        return None

    piped = _PIPE_STAMP_RE.match(msg)
    stamp = None if piped else _STAMP_RE.match(msg)
    if piped:
        time_str, text = piped.group(1), msg[piped.end():]
    elif stamp:
        time_str, text = stamp.group(1), msg[stamp.end():]
    else:
        # Dòng không mang tiền tố thời gian (print() thô, traceback…) — đóng dấu
        # theo giờ nhận. KHÔNG cắt 21 ký tự đầu như bản cũ trong GUI: điều kiện
        # cũ (`msg[10] == " "`) khớp nhầm mọi câu tiếng Việt có dấu cách ở vị
        # trí thứ 11 và ăn mất đầu câu.
        time_str, text = datetime.now().strftime(TIME_FMT), msg

    if "[CYCLE]" in text and " | " in text:
        text = text.split(" | ", 1)[0]
    text = _BADGE_RE.sub("", text)
    text = _TRAIL_RE.sub("", text)
    if " | Lý do: " in text:
        text = text.replace(" | Lý do: ", "\nLý do: ")
    elif " | Reason: " in text:
        text = text.replace(" | Reason: ", "\nReason: ")

    if not text.strip():
        return None
    return time_str, text


def append(time_str: str, message: str,
           when: Optional[Union[datetime, date]] = None) -> bool:
    """Ghi thêm một bản ghi vào file của ngày. Fail-soft, trả True nếu đã ghi.

    Không bao giờ ném ngoại lệ: mất một dòng nhật ký hiển thị KHÔNG được phép
    làm gãy luồng giao dịch đang gọi nó.
    """
    if file_log_disabled():
        return False
    try:
        path = log_path(when)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = str(message).split("\n")
        block = f"{time_str} | {lines[0]}\n" + "".join(f"{ln}\n" for ln in lines[1:])
        with _write_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(block)
        return True
    except Exception:
        return False


def record_raw(raw_msg: str,
               when: Optional[Union[datetime, date]] = None) -> Optional[Tuple[str, str]]:
    """`normalize()` + `append()` — lối vào cho chế độ CLI (engine/logger)."""
    parsed = normalize(raw_msg)
    if parsed is None:
        return None
    append(parsed[0], parsed[1], when=when)
    return parsed


# ═════════════════════════════════════════════════════════ mốc phân đoạn BUILD
# Dòng mốc ghi vào file mỗi lần một tiến trình khởi động. Nó KHÔNG phải bản ghi
# timeline: `load_day`/`load_build` nhận ra và không trả nó cho người gọi.
_BUILD_TOKEN = "###BUILD###"


def load_day(day: Optional[Union[datetime, date]] = None,
             limit: Optional[int] = None,
             keep_markers: bool = False) -> List[Dict[str, str]]:
    """Đọc lại timeline của một ngày -> [{"time", "message"}] theo thứ tự CŨ->MỚI.

    `limit`: chỉ lấy `limit` bản ghi GẦN NHẤT (dựng lại 5.000 hàng widget lúc
    khởi động sẽ treo Tk vài giây — người vận hành chỉ cần phần đuôi).
    Không có file (chưa chạy hôm nay) là trạng thái BÌNH THƯỜNG -> trả [].
    """
    path = log_path(day)
    try:
        if not path.exists():
            return []
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    entries: List[Dict[str, str]] = []
    for line in raw.splitlines():
        m = _ENTRY_RE.match(line)
        if m:
            entries.append({"time": m.group(1), "message": m.group(2)})
        elif entries and line.strip():
            # Dòng nối tiếp của bản ghi nhiều dòng ("Lý do: ...").
            entries[-1]["message"] += "\n" + line
    # LỌC NHIỄU KHI NẠP LẠI, không chỉ khi ghi.
    #
    # `is_noise` trước đây chỉ chặn ở đường GHI. Nhưng file log của những phiên TRƯỚC
    # còn nguyên các dòng đã ghi lúc bộ lọc chưa tồn tại, và mỗi lần mở lại giao diện
    # chúng được nạp lên hết — người vận hành thấy đúng cái spam mà bộ lọc lẽ ra đã
    # dọn. Lọc ở CẢ HAI đường thì màn hình sạch bất kể file cũ chứa gì.
    #
    # Lọc TRƯỚC khi cắt theo `limit`: cắt trước rồi lọc sẽ trả về ít hơn số dòng người
    # gọi yêu cầu, và những dòng có ích bị đẩy ra ngoài cửa sổ bởi chính đám nhiễu.
    entries = [e for e in entries if not is_noise(e["message"])]
    if not keep_markers:
        # Mốc phân đoạn build là dữ liệu HẠ TẦNG, không phải sự kiện giao dịch —
        # người đọc file hay bấm LOGS DIR không cần thấy. Chỉ `load_build` giữ.
        entries = [e for e in entries
                   if not e["message"].startswith(_BUILD_TOKEN)]
    if limit is not None and limit >= 0:
        entries = entries[-limit:] if limit else []
    return entries


def mark_build(build: str, when: Optional[Union[datetime, date]] = None) -> bool:
    """Đóng mốc "từ đây trở đi là bản build này ghi". Gọi MỘT lần lúc khởi động.

    VÌ SAO CẦN
    ===========
    File timeline gom theo NGÀY, nên một ngày sửa code nhiều lần là một file chứa
    dòng của nhiều bản build khác nhau. Nạp ngược cả file lên giao diện làm màn
    hình trộn dòng của bản đang chạy với dòng của những bản đã bị sửa — ngày
    15/08/2026 người vận hành thấy nguyên đám log đã bị xoá khỏi mã nguồn và kết
    luận rằng sáu vòng sửa đều vô hiệu, trong khi tệp log không dài thêm dòng nào
    kể từ lúc nạp bản mới.

    Mốc này chia file thành các PHÂN ĐOẠN theo build. `load_build` chỉ trả về
    phân đoạn của build đang chạy, nên ngữ cảnh phiên trước vẫn còn (khởi động
    lại cùng một bản thì thấy đủ) mà dòng của bản khác không lọt vào.
    """
    return append(datetime.now().strftime(TIME_FMT),
                  f"{_BUILD_TOKEN} {build}", when=when)


def load_build(build: str, day: Optional[Union[datetime, date]] = None,
               limit: Optional[int] = None) -> List[Dict[str, str]]:
    """Bản ghi trong ngày do ĐÚNG `build` này ghi, theo thứ tự CŨ->MỚI.

    Dòng nằm TRƯỚC mốc build đầu tiên bị bỏ: chúng do một tiến trình chạy trước
    khi có cơ chế mốc, tức chắc chắn thuộc một bản khác.
    """
    out: List[Dict[str, str]] = []
    current: Optional[str] = None
    for e in load_day(day, limit=None, keep_markers=True):
        msg = e["message"]
        if msg.startswith(_BUILD_TOKEN):
            current = msg[len(_BUILD_TOKEN):].strip()
            continue
        if current == build:
            out.append(e)
    if limit is not None and limit >= 0:
        out = out[-limit:] if limit else []
    return out


def available_days() -> List[str]:
    """Danh sách ngày (YYYY-MM-DD) đang có file timeline, mới nhất trước."""
    try:
        names = [p.name for p in Path(TIMELINE_DIR).glob(f"{FILE_PREFIX}*.log")]
    except Exception:
        return []
    days = [n[len(FILE_PREFIX):-len(".log")] for n in names]
    return sorted((d for d in days if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d)), reverse=True)
