"""config.py — CẤU HÌNH VẬN HÀNH của The Cheopard Forex.

KẾ THỪA BỐ CỤC TỪ THE CHEOPARD, ĐỔI GIÁ TRỊ SANG FOREX
=======================================================
Giữ nguyên tên và vai trò từng hằng số của `core/config.py` bản XAUUSD, để toàn bộ
hạ tầng kế thừa (`entry_pipeline`, `order_state_machine`, `position_execution_service`,
`gui_command_center`…) chạy được mà không phải sửa một dòng nào.

Cái ĐỔI là giá trị và đơn vị — và đó là chỗ nguy hiểm nhất khi port một hệ giao dịch:

    SYMBOL      "XAUUSD" (một tài sản)  →  danh sách công cụ sinh từ registry
    SPREAD_CAP  1,00 USD trên vàng      →  3,0 BPS. Con số 1,00 trên EURUSD ở 1,10
                                            là 9.090 bps — trần đó không bao giờ chặn.
    ATR_MIN     1,50 USD                →  BỎ HẲN. Ngưỡng ATR tuyệt đối của vàng lớn
                                            gấp ~1000 lần ATR H1 của EURUSD, nên nó
                                            lọc sạch 100% tín hiệu FX mà KHÔNG báo lỗi.
                                            Đây là lỗi đã xảy ra thật ở vòng đầu dự án.
    STRAT_MAGICS  khai tay từng chiến lược → sinh từ registry, không có danh sách thứ hai

MỌI HẰNG SỐ TIỀN TỆ Ở ĐÂY ĐỀU LÀ **BPS**, không phải đơn vị giá. Trên một hệ đa cặp
thì đơn vị giá không so sánh được giữa các công cụ (0,0001 của EURUSD và 0,01 của
USDJPY là cùng một pip), nên mọi ngưỡng phải chuẩn hoá.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Dict, List, Tuple

from src.python.core import strategy_registry as _sr
from src.python.utils.env_loader import load_env_file

# NẠP .env NGAY, TRƯỚC MỌI `os.getenv` BÊN DƯỚI.
#
# Thiếu dòng này là lỗi im lặng kinh điển: `os.getenv("MT5_LOGIN", "0")` trả "0",
# `MT5_PASSWORD` trả rỗng, MT5 không đăng nhập được — nhưng KHÔNG có exception nào.
# Bảng điều khiển hiện lên đầy đủ với mọi thẻ trống trơn, và người dùng phải đoán
# xem là chưa có dữ liệu hay là hỏng.
#
# `load_env_file()` KHÔNG ghi đè biến môi trường đã có sẵn của tiến trình, nên đặt
# biến ở dòng lệnh vẫn thắng nội dung .env — đúng thứ tự ưu tiên thường dùng.
load_env_file()

# BẪY LỖI TOÀN CỤC — cài NGAY SAU khi nạp `.env`, TRƯỚC mọi thứ khác.
#
# ⚠️ THIẾU TỪ ĐẦU, BỔ SUNG 15/08/2026.
# `utils/exception_handler.py` được port sang từ hệ XAUUSD nhưng KHÔNG AI GỌI —
# 245 dòng bảo vệ nằm im, và mỗi lần đọc mã nguồn lại tưởng là đã có. Bên đó gọi
# ở đúng vị trí này (`core/config.py`, ngay sau `load_env_file()`).
#
# Nó bẫy hai thứ mà `try/except` rải rác KHÔNG bắt được:
#   · `sys.excepthook`       — ngoại lệ chưa bắt ở LUỒNG CHÍNH
#   · `threading.excepthook` — ngoại lệ ở LUỒNG PHỤ
#
# Luồng phụ mới là chỗ nguy hiểm: engine chạy vòng lặp trên luồng riêng, email và
# backtest cũng vậy. Một luồng chết vì ngoại lệ chưa bắt thì Python in traceback
# ra stderr rồi im — tiến trình VẪN SỐNG, giao diện VẪN VẼ, nhưng vòng lặp giao
# dịch đã dừng. Người vận hành nhìn màn hình thấy mọi thứ bình thường trong khi
# không còn ai quản lý vị thế đang mở.
#
# Đặt ở `config.py` vì đây là module mà MỌI đường vào đều import: giao diện,
# `live_server`, script nghiên cứu, và cả pytest.
from src.python.utils.exception_handler import install_global_exception_handler

install_global_exception_handler()

# ═══════════════════════════════════════════════════════ đường dẫn
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LIVE_DIR = PROJECT_ROOT / "logs" / "live"
LOG_DIR = PROJECT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data"
REPORT_DIR = PROJECT_ROOT / "reports"
LOCK_FILE = LIVE_DIR / "cheopard_forex.lock"

for _d in (LIVE_DIR, LOG_DIR, REPORT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# MQL5 chỉ dùng khi có EA đi kèm; hệ này chạy thuần Python qua MetaTrader5 API.
MQL5_FILES_DIR = os.getenv("MQL5_FILES_DIR", "")

# ═══════════════════════════════════════════════════════ kết nối MT5
# Khoá dùng chung cho MỌI lời gọi MetaTrader5. Thư viện MT5 KHÔNG an toàn đa luồng:
# hai luồng cùng gọi `copy_rates_*` có thể trả dữ liệu của nhau. Hệ này có vòng lặp
# nền của GUI và vòng lặp vận hành cùng đọc, nên khoá là bắt buộc, không phải tuỳ chọn.
MT5_API_LOCK = threading.RLock()

LOGIN = int(os.getenv("MT5_LOGIN", "0") or 0)
PASSWORD = os.getenv("MT5_PASSWORD", "")
SERVER = os.getenv("MT5_SERVER", "")
MT5_PATH = os.getenv("MT5_PATH", "")

# APP_ENV=PROD mới gửi email thật; giá trị khác chỉ ghi log. Giữ nguyên quy ước của
# The Cheopard để cùng một tệp .env dùng được cho cả hai hệ.
APP_ENV = os.getenv("APP_ENV", "DEV").strip().upper()
IS_PROD = APP_ENV == "PROD"

# Cờ MÔI TRƯỜNG cho phép chạm tiền thật. Khác hẳn công tắc RUN/STOP trên giao diện:
#
#     LIVE_ORDERS      thuộc về MÁY/MÔI TRƯỜNG — đặt một lần trong `.env`, hiếm khi đổi
#     nút RUN/STOP     thuộc về NGƯỜI VẬN HÀNH — đổi trong ngày, ghi vào trading_control
#
# Tách hai câu hỏi đó ra vì trộn chúng là cách một lần bấm nút trên máy phát triển
# gửi lệnh thật.
#
# MẶC ĐỊNH `1` — ĐẶT THEO YÊU CẦU NGƯỜI VẬN HÀNH 15/08/2026.
# Nghĩa là: chạy ứng dụng + bấm [ RUN ENGINE ] là lệnh THẬT đi ra broker.
# Đặt `LIVE_ORDERS=0` trong `.env` để quay lại chế độ dry-run.
#
# ⚠️ Điều này KHÔNG bỏ các lớp chặn khác, và chúng vẫn là thứ giữ tài khoản:
#     trading_control       nút STOP → từ chối lệnh mới, bền vững qua restart
#     entry_gate            fail-closed; đối soát chưa sạch → không lệnh nào
#     ftmo_leverage_policy  đệm cạn → đòn bẩy 0 → dừng hẳn
#     disaster_stop         cầu chì đi kèm mọi lệnh mở
LIVE_ORDERS = os.getenv("LIVE_ORDERS", "1").strip().lower() in ("1", "true", "yes", "on")
BOT_NAME = os.getenv("BOT_NAME", "The Cheopard Forex")

# Giai đoạn FTMO — quyết định ngưỡng mục tiêu và trần rủi ro trong `core/infra/ftmo`.
FTMO_PHASE = os.getenv("FTMO_PHASE", "PHASE1").strip().upper()

# ═══════════════════════════════════════════════════════ email báo cáo
EMAIL = {
    "host": os.getenv("EMAIL_SMTP_HOST", ""),
    "port": int(os.getenv("EMAIL_SMTP_PORT", "587") or 587),
    "use_tls": os.getenv("EMAIL_USE_TLS", "true").strip().lower() in ("1", "true", "yes"),
    "user": os.getenv("EMAIL_SMTP_USER", ""),
    "password": os.getenv("EMAIL_SMTP_PASS", ""),
    "recipient": os.getenv("EMAIL_RECIPIENT", ""),
    "sender_name": os.getenv("EMAIL_SENDER_NAME", BOT_NAME),
    "session_end_gmt": os.getenv("EMAIL_SESSION_END_GMT", ""),
    "poll_seconds": float(os.getenv("EMAIL_WATCH_POLL_SECONDS", "60") or 60),
    "only_when_trades": os.getenv("EMAIL_ONLY_WHEN_TRADES", "1").strip().lower()
                        in ("1", "true", "yes"),
}


def _keys(name: str) -> tuple:
    """Đọc danh sách khoá API phân tách bằng dấu phẩy.

    Nhiều khoá cho một dịch vụ là để XOAY VÒNG khi chạm hạn mức — `.env` của The
    Cheopard khai kiểu đó và giữ nguyên quy ước để một tệp dùng được cho cả hai hệ.
    """
    raw = os.getenv(name, "") or ""
    return tuple(k.strip() for k in raw.split(",") if k.strip())


API_KEYS = {
    "finnhub": _keys("FINHUB_API_KEYS"), "newsapi": _keys("NEWS_API_KEYS"),
    "alpha_vantage": _keys("ALPHA_VANTAGE_API_KEYS"), "gemini": _keys("GEMINI_API_KEYS"),
    "openrouter": _keys("OPEN_ROUTER_API_KEYS"), "groq": _keys("GROQ_API_KEYS"),
    "github": _keys("GITHUB_API_KEYS"), "bls": _keys("BLS_API_KEYS"),
    "bea": _keys("BEA_API_KEYS"), "fred": _keys("FRED_API_KEYS"),
    "eia": _keys("EIA_API_KEYS"),
}

LOOP_SECONDS = float(os.getenv("LOOP_SECONDS", "5"))

# ═══════════════════════════════════════════════════════ công cụ giao dịch
# KHÔNG có `SYMBOL` số ít như bản XAU. Hệ này đa công cụ, và danh sách sinh từ
# registry — thêm chiến lược là công cụ của nó tự vào đây.
SYMBOLS: Tuple[str, ...] = tuple(sorted({s for g in _sr.live() for s in g.symbols}))

# Tương thích ngược cho hạ tầng kế thừa còn hỏi `SYMBOL`. Trả công cụ ĐẦU TIÊN chỉ để
# không vỡ import; mọi chỗ dùng nó trên hệ đa cặp đều là chỗ CẦN SỬA.
SYMBOL = SYMBOLS[0] if SYMBOLS else ""

# ═══════════════════════════════════════════════════════ magic + trạng thái
STRAT_MAGICS: List[Tuple[str, int]] = [(g.gui_tag, g.magic) for g in _sr.all_specs()]
MAGIC_BY_NAME: Dict[str, int] = {g.name: g.magic for g in _sr.all_specs()}
STRAT_STATE_FILES: Dict[str, Path] = {
    g.name: LIVE_DIR / f"{g.name.lower()}_{g.magic}.json" for g in _sr.all_specs()}

# ═══════════════════════════════════════════════════════ cổng rủi ro
# Trần spread — BPS, không phải USD. Neo vào chi phí ĐO THẬT trên MT5 ngày 14/08/2026
# (`reports/broker_costs.csv`): spread cross trung vị 0,3-1,0 bps, p95 gấp khoảng rưỡi.
# Trần 3,0 cho phép vào lệnh ở mọi điều kiện bình thường và chặn đúng lúc sổ lệnh giãn
# bất thường — đó là lúc chi phí thật vượt xa mọi giả định của backtest.
SPREAD_CAP_BPS: float = 3.0
SPREAD_CAP: float = SPREAD_CAP_BPS          # tên cũ cho hạ tầng kế thừa

# ⚠️ `ATR_MIN` / `ATR_MAX` của bản XAU (1,50 và 12,0 USD) CỐ Ý KHÔNG CÓ ở đây.
# Ngưỡng biến động tuyệt đối không port được sang FX: ATR H1 của EURUSD cỡ 0,0015 —
# nhỏ hơn 1,50 khoảng một nghìn lần, nên cổng đó lọc sạch 100% tín hiệu mà không báo
# lỗi nào. Nếu cần cổng biến động trên FX thì phải dùng ATR/GIÁ theo phân vị trượt,
# và hiện chưa chiến lược nào cần nên không khai bừa một hằng số để đó.

INP_MAX_TRADES_DAY = int(os.getenv("MAX_TRADES_DAY", "12"))
INP_MAX_CONSEC_LOSS_DAY = int(os.getenv("MAX_CONSEC_LOSS_DAY", "4"))
INP_DAILY_LOSS_CAP_PCT = float(os.getenv("DAILY_LOSS_CAP_PCT", "3.0"))
INP_COOLDOWN_MIN = float(os.getenv("COOLDOWN_MIN", "30"))
INP_DD_WARN_PCT = float(os.getenv("DD_WARN_PCT", "6.0"))

# CẦU DAO CỨNG: chạm mức sụt vốn này thì NGỪNG mở lệnh mới cho tới hết ngày.
# Đặt 8,0% chứ không phải 10,0% (giới hạn tổng của FTMO) là có chủ ý — chạm đúng
# ngưỡng quỹ là đã trượt, cầu dao phải bật TRƯỚC đó để còn đường lùi.
INP_KILL_SWITCH_DD_PCT = float(os.getenv("KILL_SWITCH_DD_PCT", "8.0"))

# Trần khối lượng mỗi lệnh. Hệ này chạy 14 chiến lược trên 6 công cụ, nên trần phải
# tính cho TỔNG chứ không cho từng lệnh — `execution/portfolio_sizing` lo phần đó.
# Con số ở đây là chốt chặn cuối cùng chống lỗi tính lot.
INP_MAX_LOT_PER_ORDER = float(os.getenv("MAX_LOT_PER_ORDER", "2.0"))

INP_CALIBRATOR_ENABLED = os.getenv("CALIBRATOR_ENABLED", "0").strip().lower() in (
    "1", "true", "yes")

# Bản XAU có `GBM_MODEL_FILE` cho đường ống ML. Hệ Forex không có mô hình ML nào —
# 63 vòng nghiên cứu cho thấy tín hiệu khai thác được là thống kê tuyến tính (tự
# tương quan bậc một), không cần mô hình học máy. Giữ hằng số rỗng để hạ tầng kế thừa
# hỏi tới thì không vỡ.
GBM_MODEL_FILE = ""
