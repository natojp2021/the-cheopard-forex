"""gui_v2.py — "Quant Trading Command Center" dashboard (nhân bản độc lập của
core/gui.py, KHÔNG sửa/đụng file cũ). Layout/màu sắc dựa theo ảnh tham chiếu
"Trung tâm giao dịch định lượng tối giản". Engine backend TÁI SỬ DỤNG y hệt
core/engine.py (TradingEngine) — chỉ lớp trình bày khác.

Nguyên tắc dữ liệu: MỌI ô hiển thị số/nhãn phải trace được về 1 nguồn thật
trong engine.state hoặc 1 module core/* đang chạy live. Những gì spec ảnh gốc
đòi hỏi (probability ML hiệu chỉnh, OOD score, "model engine" telemetry, VPS
uptime...) nhưng KHÔNG có nguồn thật nào trong repo (đường ống ML A-F cũ đã
mồ côi — xem src/python/ai/predictor.py) thì hiển thị "N/A", không bịa số.
"""
import sys
import os
import threading
import queue
import webbrowser
from datetime import datetime, timedelta, timezone
from tkinter import messagebox
import tkinter as tk
import customtkinter as ctk

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# KHÔNG XOÁ dù trông như "import không dùng" (ruff F401): `ui_patches` vá
# `ctk.CTkButton.__init__/configure/cget` NGAY LÚC IMPORT để nút bấm có màu
# disabled đúng. Xoá dòng này không gây lỗi cú pháp nào — GUI chỉ lặng lẽ mất
# hành vi. Đây là lý do đợt dọn 74 import không dùng (28/07) chừa nó ra.
import src.python.core.ui_patches  # noqa: F401  (import lấy side-effect)
from src.python.core.engine import TradingEngine
from src.python.core.config import STRAT_MAGICS, SPREAD_CAP
from src.python.core import strategy_registry as _strategy_registry
from src.python.utils import timeline_log
from src.python.shared import asset_profile as _asset_profile
from src.python.research import fx_cross_pairs as _cross_pairs

ctk.set_appearance_mode("Dark")

# ============================================================
# COLOR SYSTEM — DARK NAVY, đổi 14/08/2026.
#
# Hệ XAUUSD dùng tông LỤC trên nền #050805 (đen ngả lục). Hệ Forex dùng tông XANH
# DƯƠNG trên nền #0A101A (đen ngả lam). Cả hai đều tối — bảng số nhìn nhiều giờ
# liền thì nền sáng chói mắt — nhưng SẮC nền khác hẳn nên liếc một cái là biết
# đang mở hệ nào.
#
# Vì sao phải phân biệt được: hai bảng điều khiển trông giống nhau là cách để một
# hôm nào đó có người đọc số của hệ Forex rồi hành động trên hệ XAU, hoặc ngược lại.
# Khác biệt phải nằm ở thứ nhìn thấy TRƯỚC KHI đọc chữ, tức là màu nền.
#
#     XAUUSD   nền #050805 lục-đen   ·  nhấn LỤC   #35D875
#     Forex    nền #0A101A lam-đen   ·  nhấn LAM   #4FA8FF
#
# CHỈ TÊN BIẾN GIỮ NGUYÊN, giá trị đổi hết. Giữ tên để toàn bộ 1.875 dòng dựng giao
# diện bên dưới không phải sửa một chữ nào: `C_GREEN` vẫn là "màu của tăng", `C_RED`
# vẫn là "màu của giảm". Riêng vai trò NHẤN CHÍNH chuyển từ `C_GREEN` sang `C_BLUE`
# — đó là khác biệt nhận dạng giữa hai hệ.
#
# Mọi cặp chữ/nền đạt tương phản WCAG AA (>= 4,5:1) trên nền tối tương ứng.
# ============================================================
C_BG_ROOT     = "#0A101A"   # nền cửa sổ — đen ngả lam
C_BG_SIDEBAR  = "#0D1420"   # thanh bên, sáng hơn nền một bậc
C_BG_CARD     = "#121B2A"   # thẻ nổi trên nền
C_BG_INPUT    = "#0E1622"

C_BORDER      = "#1E2C40"
C_BORDER_ACT  = "#31527D"

TAG = {
    "orange": {"bg": "#2E2519", "fg": "#E0913F", "bd": "#5E4526"},
    "red":    {"bg": "#311D22", "fg": "#FF6B7A", "bd": "#6B333C"},
    "amber":  {"bg": "#2E2818", "fg": "#E8B84B", "bd": "#5E4F25"},
    "blue":   {"bg": "#16273D", "fg": "#5AB0FF", "bd": "#2E5480"},
    "green":  {"bg": "#152B24", "fg": "#3DD68C", "bd": "#2A5B45"},
    "purple": {"bg": "#241F3A", "fg": "#A98BF5", "bd": "#463C70"},
}

C_TEXT        = "#E8EEF6"   # chữ chính
C_TEXT_MUT    = "#96A9C2"
C_TEXT_DIM    = "#5F7390"

C_GREEN       = "#2FD48A"   # tăng / đạt — hơi ngả lam so với lục của hệ XAU
C_GREEN_HI    = "#4BEFA3"
C_GREEN_BTN   = "#0F3A2A"
C_GREEN_BTN_H = "#164E39"

C_RED         = "#FF5C6E"   # giảm / cảnh báo
C_RED_BG      = "#1E0C10"
C_RED_BTN     = "#4A161E"
C_RED_BTN_H   = "#631E28"

C_BLUE        = "#4FA8FF"   # NHẤN CHÍNH của hệ Forex
C_BLUE_BTN    = "#0E2C4C"
C_BLUE_BTN_H  = "#143E68"

C_AMBER       = "#F0BE4A"
C_AMBER_BTN   = "#42340D"
C_AMBER_BTN_H = "#564513"

# THÊM 30/07 (yêu cầu người dùng: card SESSION và REGIME mỗi trạng thái một màu
# riêng). Ba màu bổ sung để đủ sắc phân biệt — bảng màu cũ chỉ có lục/lam/hổ
# phách/đỏ, không đủ cho 5 phiên + 8 regime mà vẫn nhìn ra khác nhau.
C_TEAL        = "#2DD4BF"
C_VIOLET      = "#A78BFA"
C_ORANGE      = "#FF9A4D"

# --------------------------------------------------- màu theo PHIÊN / REGIME
# Hai bảng dưới đây tô màu 2 card telemetry theo TRẠNG THÁI, thay vì để cả hai
# cùng một màu xám như trước (người vận hành phải ĐỌC chữ mới biết đang ở phiên
# nào). Màu xếp theo MỨC ĐỘ, không random: phiên càng sôi động màu càng "nóng"/
# sáng, regime càng nguy hiểm màu càng đỏ — nhìn một cái là biết.
#
# Key là chuỗi THÔ (chưa `.title()`), lấy từ SSOT `shared/regime_taxonomy`:
# `TIME_REGIME_LABELS` (5 nhãn phiên) và `REGIME_LABELS` (6 nhãn Market Regime)
# + "NEUTRAL"/"DATA_WHIPSAW" mà tầng LLM/veto có thể phát ra ngoài 6 nhãn đó.
# Nhãn lạ -> rơi về C_TEXT (trắng) chứ không tô sai màu.
_SESSION_COLOR = {
    "ASIAN":         C_BLUE,      # phiên Á — lặng, biên hẹp
    "LONDON":        C_AMBER,     # London — thanh khoản tăng
    "NEW_YORK":      C_GREEN_HI,  # chồng lấn London-NY — đỉnh điểm
    "NEW_YORK_ONLY": C_TEAL,      # chỉ còn NY — còn chạy nhưng mỏng dần
    "NO_SESSION":    C_TEXT_DIM,  # vùng chết — cố ý mờ
}

_REGIME_COLOR = {
    "CRISIS_SHOCK":      C_RED,       # nguy hiểm nhất
    "TIER1_WHIPSAW":     C_ORANGE,
    "DATA_WHIPSAW":      C_AMBER,
    "CONFLICTING_NOISE": C_VIOLET,
    "LOW_LIQUIDITY":     C_BLUE,
    "ROUTINE_NORMAL":    C_GREEN,
    "STRUCTURAL_TREND":  C_GREEN_HI,  # điều kiện tốt nhất cho chiến lược trend
    "NEUTRAL":           C_TEXT_MUT,
    # --- trạng thái CỨNG (`regime_engine`, đo từ GIÁ) — thêm 04/08 ---
    # Bảng trên là 6 nhãn LLM chấm từ TIN TỨC; 5 nhãn dưới là trục KHÁC hẳn,
    # dùng cho card HARD REGIME. Không gộp hai trục vào một bảng tên chung vì
    # chúng không so sánh được với nhau — "NOISE" của giá không phải
    # "CONFLICTING_NOISE" của tin.
    "UPTREND":           C_GREEN_HI,
    "DOWNTREND":         C_RED,
    "SIDEWAYS":          C_BLUE,
    "NOISE":             C_VIOLET,
    "UNKNOWN":           C_TEXT_DIM,
    # --- nhãn V2 (`regime_envelope`, mặc định từ 11/08) ---
    # NÉN màu hổ phách vì đó là trạng thái DUY NHẤT chặn vào lệnh: người vận hành
    # thấy màu này thì biết ngay tại sao không có lệnh nào, không phải đi đọc log.
    "TREND_UP":          C_GREEN_HI,
    "TREND_DOWN":        C_RED,
    "RANGE":             C_BLUE,
    "NEN":               C_AMBER,
}

_STATE_TAG = {"SẴN SÀNG": "green", "CÓ LỆNH": "blue", "TẠM DỪNG": "amber"}

# Tên hiển thị (Portfolio Board) -> tên chính tắc dùng bởi regime_detector /
# allocation_policy / portfolio_allocation.EVIDENCE_SCORE (SSOT khác nhau,
# STRATEGY_REGIME_AFFINITY nằm trong regime_detector.py — module của hệ XAUUSD và
# KHÔNG tồn tại trong repo này; hệ Forex thay bằng
# `core/intelligence/fx_market_state.py`).
# DẪN XUẤT 29/07 từ `core/strategy_registry.py` (bản literal thứ 7 của cùng
# danh sách trước đó). `_DISPLAY_ORDER` thì KHÔNG dẫn xuất được: nó là thứ tự
# TRÌNH BÀY do người dùng chọn (nhóm theo khung M5 -> H1 -> H4 -> D1), khác thứ
# tự dispatch của registry — dẫn xuất sẽ âm thầm đổi bố cục GUI.
_CANON = {s.gui_tag: s.name for s in _strategy_registry.live() if s.gui_tag}
_FRAME_DESC = {s.gui_tag: s.gui_desc
               for s in _strategy_registry.live() if s.gui_tag and s.gui_desc}
# Thứ tự nhóm theo KHUNG THỜI GIAN (M30 -> H1 -> H4 -> D1), không theo thứ tự
# dispatch. Trong mỗi khung, chiến lược Sharpe cao đứng trước.
#
# ĐỔI 14/08/2026 khi chuyển sang Forex: bản XAU khai danh sách này BẰNG TAY và đó
# chính là chỗ nó từng để sót 5 chiến lược đang chạy tiền thật — vòng lặp render bỏ
# qua tên không có trong `_magic_map` nên chiến lược THIẾU biến mất khỏi bảng vận
# hành mà không có cảnh báo nào (xem chú thích lịch sử trong git).
#
# Nay danh sách SINH RA từ registry: thêm chiến lược vào `strategies/registry.py` là
# nó tự hiện, không phải nhớ sửa hai chỗ. Lỗi "sót chiến lược" hết đường xảy ra.
_DISPLAY_ORDER = _strategy_registry.display_order()
_magic_map = {name: magic for name, magic in STRAT_MAGICS}
def _build_timeframe_info():
    """"M5 · Scalping" kiểu — ghép timeframe + hạng mục (Scalping/Day/Swing)
    từ _FRAME_DESC ("Category · Timeframe · Mô tả"), giống Portfolio Board
    của core/gui.py (V1) vốn hiện cả 2 thông tin này cùng lúc."""
    info = {}
    for name, desc in _FRAME_DESC.items():
        category, tf, _detail = desc.split(" · ")
        info[name] = f"{tf} · {category}"
    return info


_TIMEFRAME = _build_timeframe_info()


# XOÁ 01/08: ở đây từng có bản `_card()` và `_section_title()` THỨ HAI, khác
# hẳn bản thật ở khối CUSTOM WIDGETS bên dưới (font 13 màu xanh thay vì font 16
# màu xám, và `_card` không cho lời gọi ghi đè `fg_color`). Vì Python lấy định
# nghĩa CUỐI CÙNG, bản này chưa từng chạy một lần nào — nhưng người đọc file lại
# gặp nó TRƯỚC và tưởng đó là hành vi thật. Đọc sai kiểu đó là cách người ta
# "sửa" một widget mà giao diện không đổi gì rồi đi tìm nguyên nhân ở chỗ khác.


def _kv_row(parent, key, value_text="--", value_color=None):
    row = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(row, text=key, font=ctk.CTkFont(family="Consolas", size=12), text_color=C_TEXT_DIM,
                 width=110, anchor="w").pack(side="left")
    val = ctk.CTkLabel(row, text=value_text, font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                        text_color=value_color or C_TEXT, anchor="w")
    val.pack(side="left", fill="x", expand=True)
    return row, val


# ── HIỆU ỨNG "ĐANG CHẠY…" ────────────────────────────────────────────────────
#
# VÌ SAO CẦN: lúc mở bảng điều khiển, engine làm ba việc nặng trước khi có gì để
# hiện — nối MT5, đối soát vị thế, và chạy `PF.backtest()` (27 chân, ~2 phút). Suốt
# quãng đó màn hình đứng yên với "N/A" và "—", không phân biệt được "đang làm việc"
# với "đã treo". Đó là hai sự cố khác hẳn nhau mà triệu chứng giống hệt — cùng loại
# nhầm lẫn mà `engine.log` phải mở sổ riêng để cắt đôi.
#
# CHU KỲ: `process_queues` chạy mỗi 100 ms. Đổi khung mỗi 4 lượt cho ra 400 ms một
# bước — đủ chậm để mắt bắt kịp, đủ nhanh để thấy là đang chuyển động.
BUSY_TICK_EVERY = 4
_BUSY_DOTS = ("", ".", "..", "...", "....")


def busy_text(label: str, tick: int) -> str:
    """Nhãn kèm chuỗi chấm chạy — hàm THUẦN nên test được mà không cần dựng Tk.

    Tách khỏi widget có chủ ý: phần dễ sai của một animation là công thức chọn
    khung, không phải lệnh vẽ. Giữ nó thuần thì `tests/` ghim được hành vi.
    """
    if not label:
        return ""
    return f"{label}{_BUSY_DOTS[(tick // BUSY_TICK_EVERY) % len(_BUSY_DOTS)]}"


# ============================================================
# READ-ONLY DATA ACCESSORS — mọi hàm ở đây fail-soft, không bao giờ raise ra
# ngoài; trả "N/A" khi nguồn dữ liệu thật không tồn tại/lỗi.
# ============================================================
def is_forex_weekend(now_utc=None) -> bool:
    """Xấp xỉ giờ đóng cửa forex/kim loại (đóng Thứ 7 00:00 UTC, mở lại Chủ
    Nhật 21:00 UTC) — SSOT uỷ quyền cho core.infra.market_schedule."""
    from src.python.core.infra.market_schedule import is_market_closed
    return is_market_closed(now_utc)


def get_ai_trend():
    """THIÊN HƯỚNG RÒNG của danh mục — thay cho sentiment LLM của hệ XAUUSD.

    Hệ XAU lấy con số này từ phán quyết của MoE Chairman (LLM hai tầng). Hệ Forex bỏ
    kiến trúc đó, và thay bằng thứ ĐO ĐƯỢC: tổng vị thế thật của 14 chiến lược, quy
    về phơi nhiễm từng đồng tiền.

    Khác biệt không chỉ là nguồn. Sentiment LLM là một DỰ ĐOÁN có thể sai; thiên
    hướng danh mục là một SỰ KIỆN — hệ đang nghiêng về đâu thì đúng là đang nghiêng
    về đó. Với một bảng vận hành, cái thứ hai hữu ích hơn hẳn.

    Quy ước dấu: dương = nghiêng đồng RỦI RO (AUD/NZD/CAD/GBP), âm = nghiêng đồng
    TRÚ ẨN (JPY/CHF/USD). Trả (nhãn, màu, mô tả chế độ).
    """
    try:
        from src.python.core.intelligence import fx_market_state as _fms
        st = _fms.get_state()
        if st.error or st.net_bias is None:
            return "N/A", C_TEXT_MUT, "N/A"
        b = float(st.net_bias)
        regime = f"{st.soft_regime} / {st.hard_regime}"
        # Vùng chết ±0,05: dưới mức đó thì danh mục coi như trung tính, và hiện
        # "BULLISH +0,01" chỉ là nhiễu làm người đọc tưởng có tín hiệu.
        if b >= 0.05:
            return f"RISK-ON ▲ ({b:+.2f})", C_GREEN, regime
        if b <= -0.05:
            return f"RISK-OFF ▼ ({b:+.2f})", C_RED, regime
        return f"TRUNG TÍNH ▶ ({b:+.2f})", C_TEXT_MUT, regime
    except Exception:
        return "N/A", C_TEXT_MUT, "N/A"


def get_system_health(state):
    rows = {}
    # Phụ đề nói RÕ đang nối vào đâu. Bản XAU để "N/A" ở đây, và hệ quả là khi
    # terminal đăng nhập nhầm tài khoản thì bảng vẫn báo CONNECTED một cách vui vẻ.
    _acc0 = state.get("account_info", {}) or {}
    _mt_ok = bool(state.get("mt5_connected"))
    if _mt_ok:
        _sub = (f"{_acc0.get('company', '')} · "
                f"{'DEMO' if _acc0.get('is_demo') else 'THẬT'} · "
                f"đòn bẩy 1:{_acc0.get('leverage', '?')}").strip(" ·")
    else:
        _sub = str(state.get("positions_read_error") or "chưa kết nối")[:70]
    rows["MT5 TERMINAL"] = ("CONNECTED" if _mt_ok else "DISCONNECTED", _sub)

    acc = state.get("account_info", {}) or {}
    # Phụ đề: equity + môi trường chạy, hai thứ đọc từ `.env` và từ broker. Bản XAU
    # để trống, nên nhìn thẻ không biết đang chạy DEV hay PROD.
    _eq = acc.get("equity")
    rows["ACCOUNT"] = (
        str(acc.get("login")) if acc.get("login") else "N/A",
        (f"{_eq:,.0f} {acc.get('currency', '')} · {acc.get('app_env', '')} · "
         f"FTMO {acc.get('ftmo_phase', '')}").strip(" ·") if _eq is not None else "")
    rows["SERVER"] = (str(acc.get("server")) if acc.get("server") else "N/A", "")

    gmt7 = timezone(timedelta(hours=7))

    # ĐÃ GỠ 15/08/2026: MODEL ENGINE · SOFT REGIME · NEWS FEED · HARD REGIME H4 ·
    # AI TREND. Cả năm tính đầu ra của bộ máy AI vĩ mô hệ XAUUSD, thứ hệ Forex không
    # có — xem ghi chú ở chỗ dựng thẻ trong `_build_health_card`. Giữ phần TÍNH mà
    # không thẻ nào đọc là giữ code chết trên đường chạy mỗi 5 giây.
    #
    # SESSION thì GIỮ: nó chỉ đọc đồng hồ, không phụ thuộc bộ máy AI nào, và phiên
    # giao dịch là thứ ảnh hưởng thật tới spread và thanh khoản.
    # THỊ TRƯỜNG ĐÓNG → thẻ hiện STAND BY, không hiện tên phiên.
    #
    # `classify_time_regime` chỉ đọc GIỜ trong ngày, nên trưa thứ Bảy nó vẫn trả về
    # "LONDON" — đúng theo đồng hồ mà sai theo thực tế: lúc ấy không có phiên nào mở,
    # không có thanh khoản, và spread là giá đóng băng. Để nguyên thì thẻ nói hệ đang
    # ở phiên London trong khi hệ đang ngủ đông.
    if state.get("market_closed"):
        rows["SESSION"] = ("STAND BY",
                           str(state.get("market_status") or "thị trường đóng cửa")[:60],
                           C_TEXT_DIM)
        return rows

    try:
        # `time_regime_cadence_minutes` KHÔNG TỒN TẠI trong module này — thẻ
        # SESSION đã hiện "N/A" từ lúc port sang và không ai phát hiện, vì
        # `except Exception` nuốt `ImportError` rồi ghi đúng chữ "N/A" mà người đọc
        # tưởng là "chưa có dữ liệu". Sửa 15/08/2026: dùng `time_regime_activity`,
        # hàm thật sự có.
        from src.python.shared.regime_taxonomy import (
            classify_time_regime,
            time_regime_activity,
        )
        now_utc = datetime.now(timezone.utc)
        session = classify_time_regime(now_utc)
        act = time_regime_activity(now_utc)
        now_local = now_utc.astimezone(gmt7)
        rows["SESSION"] = (session,
                           f"hoạt động {act:.0%} · "
                           f"{now_local.strftime('%H:%M')} (GMT+7)",
                           _SESSION_COLOR.get(session))
    except Exception as exc:
        # Ghi RÕ lỗi thay vì "N/A" — chính chữ N/A đã che lỗi này suốt.
        rows["SESSION"] = ("LỖI", f"{type(exc).__name__}: {exc}"[:60])

    return rows


# ĐÃ XOÁ 15/08/2026 — `_hard_regime_cache`, `HARD_REGIME_CACHE_S`,
# `HARD_REGIME_MAX_AGE_S`, `_hard_regime_row()`, `_regime_blocks_strategy()`.
#
# Cả khối là CẦU DAO TRẠNG THÁI THỊ TRƯỜNG port từ hệ XAUUSD. Nó dựa vào
# `core.intelligence.regime_engine` và `regime_envelope` — hai module KHÔNG TỒN TẠI
# ở hệ Forex. Mọi lượt gọi ném `ImportError`, rơi vào `except` và trả `False`.
#
# Tức 55 dòng đó luôn trả về một hằng số. Chúng vẫn chạy mỗi 5 giây, vẫn nạp cache,
# vẫn làm người đọc mã tin rằng có một cầu dao đang canh trạng thái thị trường —
# trong khi không có. Một cổng không tồn tại mà trông như đang tồn tại nguy hiểm hơn
# một cổng thiếu, vì nó chặn cả việc đi tìm cổng thật.
#
# Chúng cũng là hai chỗ DUY NHẤT còn import `core/execution/entry_pipeline.py`
# (1.476 dòng, đường vào lệnh của XAU mà hệ này không dùng) — xoá ở đây là gỡ nốt
# tham chiếu cuối cùng để xoá được cả file đó.
#
# Hệ Forex đo trạng thái thị trường bằng `core/intelligence/fx_market_state.py`
# (biến động rổ 20 cross theo phân vị trượt). Muốn dựng lại cầu dao thì dựng trên
# nguồn ấy, và phải đo trước khi bật — xem `registry.REJECTED_DIRECTIONS`.


def _regime_blocks_strategy(gui_tag: str) -> bool:
    """Chiến lược có đang bị cầu dao trạng thái tắt không.

    Hệ Forex CHƯA có cầu dao trạng thái nào có quyền chặn lệnh, nên luôn `False`.
    Giữ hàm (thay vì xoá lời gọi) để chỗ nối sẵn sàng khi cầu dao được dựng trên
    `fx_market_state`, và để bảng quyết định không phải đổi hình dạng lúc đó.
    """
    return False


def _open_magics(state) -> set:
    """Tập `magic` của các vị thế ĐANG MỞ, đọc từ vị thế THẬT của broker.

    VÌ SAO KHÔNG ĐỌC `state["portfolio"]` NHƯ BẢN CŨ
    =================================================
    Bản cũ viết `{r["name"]: r for r in (state.get("portfolio") or [])}`, tức coi
    `state["portfolio"]` là DANH SÁCH các hàng có khoá `name`. Nhưng
    `engine._read_portfolio` ghi vào đó một TỪ ĐIỂN chỉ số danh mục
    (`sharpe_all`, `max_dd_sd`, `n_strategies`…). Lặp một từ điển cho ra các KHOÁ,
    nên `r` là chuỗi `"sharpe_all"` và `r["name"]` ném
    `TypeError: string indices must be integers`.

    Lỗi đó không lộ ra vì hai lý do cộng lại:
      · lúc khởi động `portfolio` là `{}`, mà `{} or []` cho `[]` → không lặp gì,
        bảng vẫn vẽ đúng;
      · khối gọi hàm này bọc trong `try/except Exception` nuốt trọn.

    Hậu quả đo được: sau khi lượt backtest danh mục đầu tiên kết thúc (~2 phút sau
    khi mở bảng điều khiển), MA TRẬN ĐỨNG IM VĨNH VIỄN ở giá trị lúc khởi động —
    không có dòng lỗi nào, không có gì để lần ra.

    Nguồn đúng là vị thế THẬT: một chân "có lệnh" khi broker đang giữ vị thế mang
    `magic` của nó. `state["portfolio"]` chưa bao giờ chứa thông tin đó.
    """
    out = set()
    for p in (state.get("positions_list") or []):
        magic = p.get("magic") if isinstance(p, dict) else getattr(p, "magic", None)
        if magic is not None:
            try:
                out.add(int(magic))
            except (TypeError, ValueError):
                continue
    return out


def _current_r(state, magic: int) -> str:
    """Lãi/lỗ ĐANG CHẠY của chân này, tính bằng % equity. "—" khi không có lệnh.

    Cột này tên là CUR. R nhưng hệ Forex KHÔNG có R (bội số rủi ro) vì không chân
    nào đặt SL theo giá — không có mẫu số. Bản XAUUSD có SL từng lệnh nên R có
    nghĩa; port thẳng tên cột sang đây thì cột hoặc rỗng, hoặc hiện một con số
    không định nghĩa được.

    Nên đại lượng hiện ở đây là **% equity**: lãi/lỗ chưa đóng của mọi vị thế mang
    `magic` này, chia cho equity. Đó là con số dùng được thật — nó đúng đơn vị với
    hạn mức ngày 4% và sàn tổng 9% mà người vận hành phải theo dõi.
    """
    eq = state.get("equity")
    try:
        eq = float(eq)
    except (TypeError, ValueError):
        return "—"
    if eq <= 0:
        return "—"
    total = 0.0
    found = False
    for p in (state.get("positions_list") or []):
        m = p.get("magic") if isinstance(p, dict) else getattr(p, "magic", None)
        try:
            if m is None or int(m) != magic:
                continue
        except (TypeError, ValueError):
            continue
        v = p.get("profit") if isinstance(p, dict) else getattr(p, "profit", None)
        try:
            total += float(v)
            found = True
        except (TypeError, ValueError):
            continue
    if not found:
        return "—"
    return f"{total / eq * 100:+.2f}%"


def get_decision_matrix_rows(state):
    open_magics = _open_magics(state)
    try:
        from src.python.core.intelligence import strategy_scoring
    except Exception:
        # Fail-SOFT có chủ ý: đây là công tắc VẬN HÀNH, không phải cổng AN TOÀN.
        # Cổng an toàn thật nằm ở `entry_gate` và `ftmo_guard`. Fail-closed ở đây
        # nghĩa là một file JSON hỏng làm câm toàn bộ bảng mà không giảm rủi ro nào.
        strategy_scoring = None
    rows = []
    for name in _DISPLAY_ORDER:
        if name not in _magic_map:
            continue
        has_position = _magic_map[name] in open_magics
        canon = _CANON.get(name, name)
        # VÒNG ĐỜI đọc từ `strategy_scoring` — công tắc VẬN HÀNH đặt tay, bền vững
        # trên đĩa. Trước 15/08/2026 khối này import `allocation_policy` và
        # `strategy_scoring`, cả hai KHÔNG TỒN TẠI, nên `lifecycle` luôn `None` và
        # `enabled` luôn `True` cho cả 27 chân — đo được 27/27. Không có đường nào
        # tạm dừng một chân lúc đang chạy, mà cột LIVE vẫn xanh như thể có.
        lifecycle = strategy_scoring.get_manual_state(canon) if strategy_scoring else None
        enabled = lifecycle not in strategy_scoring.BLOCKING if lifecycle else True
        is_weekend = is_forex_weekend() or state.get("market_closed", False)
        if not enabled:
            decision = "STOPPED"
        elif has_position:
            decision = "ACTIVE"
        elif is_weekend:
            decision = "STAND BY"
        elif _regime_blocks_strategy(name):
            # SAU `CÓ LỆNH` có chủ đích: cầu dao chỉ chặn ENTRY MỚI, vị thế đang
            # mở vẫn được quản lý bình thường. Một chiến lược có lệnh mà trạng
            # thái đã đổi sang ô bị cấm thì đúng nhất là hiện ACTIVE — nó vẫn
            # đang làm việc, chỉ không mở thêm.
            decision = "REGIME OFF"
        else:
            decision = "SCANNING"
        regime_ok = not _regime_blocks_strategy(name)
        rows.append({
            "name": name, "enabled": enabled, "active": has_position,
            "r": _current_r(state, _magic_map[name]), "decision": decision,
            "regime_ok": regime_ok, "live": bool(enabled and regime_ok),
        })
    #
    # Ba khoá, theo đúng thứ tự cần chú ý:
    #   1. đang CÓ LỆNH        — thứ phải theo dõi ngay
    #   2. đang được phép vào  — thứ có thể phát tín hiệu bất cứ lúc nào
    #   3. `_DISPLAY_ORDER`    — giữ nhóm khung thời gian M5 -> H1 -> H4 -> D1
    #
    # Khoá 1 đứng trước khoá 2 có chủ đích: một chiến lược ĐANG giữ lệnh mà vừa
    # bị cầu dao tắt vẫn phải nằm trên đầu — vị thế của nó vẫn đang được quản lý
    # (cầu dao chỉ chặn lệnh MỚI), nên nó vẫn là thứ cần nhìn.
    order = {n: i for i, n in enumerate(_DISPLAY_ORDER)}
    rows.sort(key=lambda r: (0 if r["active"] else 1,
                             0 if r.get("live", True) else 1,
                             order.get(r["name"], 99)))
    return rows


_STRAT_KEYWORDS = list(_DISPLAY_ORDER) + list(_CANON.values())
# Rổ nhận diện symbol trong dòng log. ĐỔI 14/08/2026: bản kế thừa để XAUUSD và
# XAGUSD ở đầu danh sách — hệ này là Forex-only nên hai mục đó chỉ có thể gán
# nhãn SAI cho một dòng log. Sinh từ `asset_profile.FX_ALL` để không lệch khi rổ đổi.
_SYMBOL_KEYWORDS = tuple(_asset_profile.FX_ALL) + tuple(
    n for n, *_ in _cross_pairs.CROSS_DEFS)


def categorize_log(msg):
    """Suy luận (level, category, symbol, strategy) TỪ text log — cùng cách
    tiếp cận keyword-matching mà core/gui.py._append_log() đã dùng, chỉ đổi
    nhãn hiển thị cho khớp cột Event Timeline. Không có cách nào lấy các
    trường này có cấu trúc 100% từ engine.log() (chuỗi phẳng) — xem
    domain_events.jsonl/decision_journal cho nguồn có cấu trúc hơn nếu cần
    nâng cấp sau này."""
    lower = msg.lower()
    if any(k in lower for k in ("email", "smtp", "gửi mail")):
        level, cat = "EMAIL", "EMAIL"
    elif any(k in msg for k in ("[CIRCUIT BREAKER]", "MARGIN GUARD", "LECH PARITY", "stops_level", "[GUARD]")):
        level, cat = "GUARD", "GUARD"
    elif "bị chặn" in lower or "blocked" in lower or "chặn entry" in lower:
        level, cat = "BLOCKED", "BLOCKED"
    elif "[wd-advisor]" in lower:
        level, cat = "ADVISOR", "ADVISOR"
    elif "[manual]" in lower:
        level, cat = "MANUAL", "MANUAL"
    elif any(k in lower for k in ("error", "failed", "lỗi", "loi:")):
        level, cat = "ERROR", "SYSTEM"
    elif any(k in lower for k in ("cảnh báo", "canh bao", "warning", "safe-mode")):
        level, cat = "WARNING", "SYSTEM"
    elif any(k in lower for k in ("chairman", "moe", "gemini", "groq", "openrouter",
                                  "prob", "prediction", "model", "gbm")):
        level, cat = "AI", "AI"
    elif any(k in lower for k in ("candidate", "signal", "setup")):
        level, cat = "SIGNAL", "DECISION"
    elif any(k in lower for k in ("open", "close", "buy", "sell", "trade", "lệnh", "lenh", "đóng", "dong")):
        level, cat = "TRADE", "TRADE"
    elif any(k in lower for k in ("đã kết nối", "connected", "thành công", "thanh cong")):
        level, cat = "SUCCESS", "SYSTEM"
    else:
        level, cat = "INFO", "SYSTEM"

    symbol = "—"
    for s in _SYMBOL_KEYWORDS:
        if s in msg:
            symbol = s
            break
    strategy = "—"
    matched = [s for s in _STRAT_KEYWORDS if s in msg]
    if len(matched) == 1:
        strategy = matched[0]
    return level, cat, symbol, strategy


_LEVEL_VARIANT = {
    "INFO": "blue", "SUCCESS": "green", "WARNING": "amber", "ERROR": "red",
    "TRADE": "green", "SIGNAL": "purple", "AI": "purple", "GUARD": "orange",
    "BLOCKED": "red", "ADVISOR": "purple", "MANUAL": "blue", "EMAIL": "blue",
}


# ============================================================
# CUSTOM WIDGETS
# ============================================================
def _card(parent, **kwargs):
    defaults = dict(fg_color=C_BG_CARD, border_width=1, border_color=C_BORDER, corner_radius=6)
    defaults.update(kwargs)
    return ctk.CTkFrame(parent, **defaults)


def _section_title(parent, text):
    return ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
                         text_color=C_TEXT_DIM)

# ============================================================
# MAIN DASHBOARD
# ============================================================
class TradingGUIV2:
    def __init__(self):
        self.log_queue = queue.Queue()
        self.status_queue = queue.Queue()
        self.all_logs = []

        class _Redirector:
            def __init__(self, q):
                self.queue, self.buffer = q, ""

            def write(self, string):
                self.buffer += string
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    line = line.strip()
                    if line:
                        self.queue.put(line)

            def flush(self):
                pass

        sys.stdout = _Redirector(self.log_queue)
        sys.stderr = _Redirector(self.log_queue)

        self.root = ctk.CTk()
        # BUILD ngay trên THANH TIÊU ĐỀ, không chỉ ở góc thanh bên.
        #
        # Ngày 15/08 người vận hành sửa code rồi nhấn VBS mà vẫn thấy "bản build lúc
        # 12:30". Nguyên nhân thật nằm ở khoá một-tiến-trình (nó FOCUS bản cũ thay
        # vì nạp bản mới — đã sửa ở `live_server.py`), nhưng chuyện đó chỉ mất hai
        # phút để chẩn đoán KHI NHÌN THẤY build id. Tiêu đề cửa sổ là chỗ đầu tiên
        # mắt nhìn tới, và `version()` đã mang sẵn dấu thời gian của mã nguồn.
        try:
            from src.python.core.runtime_meta import version as _v
            self.root.title(f"The Cheopard Forex — BUILD {_v()}")
        except Exception:
            self.root.title("The Cheopard Forex")
        self.root.geometry("1680x1000")
        self.root.minsize(1360, 820)
        self.root.configure(fg_color=C_BG_ROOT)

        # Hàng đợi thứ BA, cùng cơ chế với `log_queue`/`status_queue`: mọi thao tác
        # giao diện phát sinh từ luồng nền đi qua đây. Xem `_ui()`.
        self.ui_queue: "queue.Queue" = queue.Queue()

        self.engine = TradingEngine(log_callback=self.enqueue_log, status_callback=self.enqueue_status)

        self._timeline_rows = []
        self._timeline_filter = "ALL"

        self.create_widgets()

        # Trước khi bơm log MỚI: dựng lại phần do CHÍNH bản build này ghi, để nó
        # nằm đúng phía dưới (timeline xếp mới-nhất-trên-cùng).
        self._restore_build_timeline()

        self.root.after(100, self.process_queues)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        threading.Thread(target=self.engine.update_mt5_status, daemon=True).start()

    # ------------------------------------------------------------------
    def enqueue_log(self, msg):
        self.log_queue.put(msg)

    def enqueue_status(self, state):
        self.status_queue.put(state)

    def process_queues(self):
        while not self.log_queue.empty():
            try:
                self._append_log(self.log_queue.get_nowait())
            except queue.Empty:
                break
        while not self.status_queue.empty():
            try:
                self.update_ui_state(self.status_queue.get_nowait())
            except queue.Empty:
                break
        while not self.ui_queue.empty():
            try:
                fn, args = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args)
            except Exception as exc:
                # Một callback hỏng không được làm chết vòng rút hàng đợi — mất
                # `process_queues` là mất luôn timeline và mọi cập nhật thẻ.
                self._append_log(f"[GUI] callback {getattr(fn, '__name__', fn)}: {exc}")
        self._tick_busy()
        # Tự đặt lịch lại. Bọc lỗi vì lượt cuối cùng có thể chạy đúng lúc cửa sổ
        # đang đóng — lúc đó Tk đã tắt và `after()` ném TclError. Đó là kết thúc
        # bình thường, không phải sự cố cần đổ traceback vào timeline.
        try:
            self.root.after(100, self.process_queues)
        except (RuntimeError, tk.TclError):
            pass

    def _tick_busy(self) -> None:
        """Một khung của hiệu ứng "ĐANG CHẠY…". Đọc `state["busy"]` do engine đặt.

        Nằm TRONG `process_queues` chứ không tự đặt `after()` riêng: một vòng lặp
        `after` thứ hai là một chỗ nữa có thể chết lặng lẽ, và khi nó chết thì hiệu
        ứng đứng yên — trông y hệt "hệ đã treo", tức chỉ báo lại nói dối đúng cái
        điều nó sinh ra để trả lời.
        """
        lbl = getattr(self, "busy_lbl", None)
        if lbl is None:
            return
        try:
            reason = str((self.engine.state or {}).get("busy") or "")
        except Exception:
            reason = ""
        try:
            if reason:
                self._busy_tick += 1
                lbl.configure(text=busy_text(reason, self._busy_tick),
                              text_color=C_AMBER)
            elif self._busy_tick:
                # Chỉ vẽ lại MỘT lần khi vừa xong, không mỗi 100 ms: `configure`
                # trên Tk là lệnh vẽ thật, gọi 10 lần/giây cho một chuỗi không đổi
                # là đốt CPU để không thay đổi gì.
                self._busy_tick = 0
                lbl.configure(text="SẴN SÀNG", text_color=C_TEXT_MUT)
        except (RuntimeError, tk.TclError):
            pass



    # ------------------------------------------------------------------
    # WIDGET CONSTRUCTION
    # ------------------------------------------------------------------
    def create_widgets(self):
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()

    # ── SIDEBAR ──────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self.root, width=272, corner_radius=0, fg_color=C_BG_SIDEBAR, border_width=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)

        brand = ctk.CTkFrame(sb, fg_color="transparent")
        brand.pack(padx=16, pady=(12, 4), fill="x")
        mark = tk.Canvas(brand, width=32, height=32, bg=C_BG_SIDEBAR, highlightthickness=0)
        mark.pack(side="left", padx=(0, 8))
        mark.create_oval(3, 3, 29, 29, outline=C_GREEN_HI, width=2)
        mark.create_oval(11, 11, 21, 21, fill=C_GREEN_HI, outline="")
        title_box = ctk.CTkFrame(brand, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(title_box, text="THE CHEOPARD", font=ctk.CTkFont(family="Consolas", size=20, weight="bold"),
                     text_color=C_GREEN_HI).pack(anchor="w")
        ctk.CTkLabel(title_box, text="QUANT TRADING COMMAND CENTER",
                     font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
                     text_color=C_TEXT_DIM).pack(anchor="w")

        ctk.CTkFrame(sb, height=1, fg_color=C_BORDER_ACT, corner_radius=0).pack(fill="x", pady=(6, 8))



        # ── GUARD STATUS CARD ─────────────────────────────────────────────
        guard_card = _card(sb)
        guard_card.pack(padx=14, pady=(0, 8), fill="x")
        _section_title(guard_card, ">_ GUARD SYSTEM").pack(padx=10, pady=(6, 4), anchor="w")

        _, self.guard_main_lbl = _kv_row(guard_card, "STATUS", "MONITORING", C_GREEN)
        self.guard_main_lbl.master.pack(padx=10, pady=(1, 2), fill="x")

        # HÀNG RIÊNG, không đè lên STATUS ở trên: STATUS là thông tin AN TOÀN
        # (MONITORING / HALT), và mượn nó để hiện tiến trình là che mất đúng dòng
        # người vận hành cần đọc nhất khi có sự cố.
        _, self.busy_lbl = _kv_row(guard_card, "TIẾN TRÌNH", "SẴN SÀNG", C_TEXT_MUT)
        self.busy_lbl.master.pack(padx=10, pady=(1, 2), fill="x")
        self._busy_tick = 0

        self.guard_tags = {}
        pairs = [
            ("mt5_terminal", "MT5 TERMINAL", "DISCONNECTED", C_TEXT_MUT),
            ("server",       "SERVER",       "N/A", C_TEXT_MUT),
            ("account",      "ACCOUNT",      "N/A", C_TEXT_MUT),
            ("ftmo_mode",    "FTMO MODE",    "N/A", C_TEXT_MUT),
            ("trades_today", "TRADES TODAY", "0", C_TEXT),
            ("consec_loss",  "CONSEC LOSS",  "0", C_TEXT),
            ("halt",         "SYSTEM HALT",  "NO", C_GREEN),
        ]
        for key, label_txt, default_val, color in pairs:
            row_frame, val_lbl = _kv_row(guard_card, label_txt, default_val, color)
            row_frame.pack(padx=10, pady=1, fill="x")
            self.guard_tags[key] = val_lbl

        ctk.CTkFrame(guard_card, height=4, fg_color="transparent").pack()

        ctk.CTkLabel(sb, text="PRIMARY CONTROLS", font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                     text_color=C_TEXT_DIM).pack(padx=16, pady=(2, 4), anchor="w")

        ctrl = ctk.CTkFrame(sb, fg_color="transparent")
        ctrl.pack(padx=14, fill="x")

        self.arm_btn = ctk.CTkButton(ctrl, text="[ RUN ENGINE ]", height=36,
                                      font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                                      fg_color=C_GREEN_BTN, hover_color=C_GREEN_BTN_H, text_color=C_GREEN,
                                      border_width=1, border_color=C_BORDER_ACT, command=self.on_arm)
        self.arm_btn.pack(fill="x", pady=(0, 6))

        self.disarm_btn = ctk.CTkButton(ctrl, text="[ STOP ENGINE ]", height=36,
                                         font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                                         fg_color="transparent", hover_color=C_BORDER_ACT, text_color=C_TEXT_MUT,
                                         border_width=1, border_color=C_BORDER, state="disabled",
                                         command=self.on_disarm)
        self.disarm_btn.pack(fill="x", pady=(0, 6))


        ctk.CTkLabel(sb, text="THE CHEOPARD © 2026",
                     font=ctk.CTkFont(family="Consolas", size=10), text_color=C_TEXT_DIM).pack(side="bottom", pady=4)
        try:
            from src.python.core.runtime_meta import version as _rt_ver
            _ver = _rt_ver() or "N/A"
        except Exception:
            _ver = "N/A"
        ver_box = ctk.CTkFrame(sb, fg_color="transparent")
        ver_box.pack(side="bottom", pady=(0, 2))
        ctk.CTkLabel(ver_box, text="BUILD ", font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
                     text_color=C_AMBER).pack(side="left")
        ctk.CTkLabel(ver_box, text=_ver, font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
                     text_color=C_GREEN).pack(side="left")

    # ── MAIN ─────────────────────────────────────────────────────────
    def _build_main(self):
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(10, 10), pady=10)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=0)
        main.grid_rowconfigure(1, weight=1)
        main.grid_rowconfigure(2, weight=0)
        self.main_scroll = main

        self._build_middle_row(main, row=0)
        self._build_timeline(main, row=1)
        self._build_positions_panel(main, row=2)

    def _build_middle_row(self, parent, row):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        wrap.grid_columnconfigure(0, weight=3, uniform="mid_cols")
        wrap.grid_columnconfigure(1, weight=3, uniform="mid_cols")
        wrap.grid_columnconfigure(2, weight=4, uniform="mid_cols")

        self.account_cards = []
        self._build_health_card(wrap, col=0, padx=(0, 6))
        self._build_account_card(wrap, col=1, padx=6)
        self._build_matrix_card(wrap, col=2)

    def _build_account_card(self, parent, col, padx):
        """Panel ACCOUNT OVERVIEW — clone được (yêu cầu người dùng: 1 bản bên
        trái + 1 bản bên phải của STRATEGY DECISION MATRIX). Mỗi lần gọi tạo 1
        bộ widget ĐỘC LẬP (không dùng self.acc_* cố định vì gọi 2 lần sẽ ghi
        đè) — lưu vào self.account_cards, update_ui_state() cập nhật ĐỒNG THỜI
        mọi bản clone trong list này với CÙNG 1 dữ liệu tài khoản thật."""
        card = _card(parent)
        card.grid(row=0, column=col, sticky="nsew", padx=padx)
        _section_title(card, "> ACCOUNT OVERVIEW").pack(padx=12, pady=(4, 2), anchor="w")
        ctk.CTkFrame(card, height=1, fg_color=C_BORDER).pack(fill="x", padx=12, pady=(0, 4))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(padx=12, pady=(0, 6), fill="both", expand=True)
        grid.grid_columnconfigure((0, 1), weight=1, uniform="acc_cols")
        pairs = [
            ("balance", "💰 BALANCE"), ("equity", "⚖️ EQUITY"),
            ("openpnl", "📈 OPEN PNL"), ("daily_pnl", "🗓️ DAILY PNL"),
            ("dd_daily", "📉 DAILY DD"), ("dd_max", "🛑 MAX DD"),
            ("freemargin", "🧮 FREE MARGIN"), ("spread", "📶 SPREAD"),
        ]
        for r in range((len(pairs) + 1) // 2):
            grid.grid_rowconfigure(r, weight=1, uniform="acc_rows")
        widgets = {}
        for i, (key, label) in enumerate(pairs):
            block = ctk.CTkFrame(grid, fg_color=C_BG_INPUT, border_width=1, border_color=C_BORDER, corner_radius=4)
            block.grid(row=i // 2, column=i % 2, sticky="nsew", padx=2, pady=2)
            ctk.CTkLabel(block, text=label, font=ctk.CTkFont(family="Consolas", size=14),
                         text_color=C_TEXT, anchor="w").pack(anchor="w", padx=8, pady=(4, 0))
            lbl = ctk.CTkLabel(block, text="N/A", font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                                text_color=C_TEXT, anchor="w")
            lbl.pack(anchor="w", padx=8, pady=(0, 4))
            widgets[key] = lbl
        self.account_cards.append(widgets)

    # Số hàng chiến lược hiện cùng lúc trước khi phải cuộn. 7 = vừa hết chiều
    # cao hàng giữa ở bố cục hiện tại mà không đẩy các card cạnh bên giãn ra.
    _MATRIX_VISIBLE_ROWS = 7

    def _build_matrix_card(self, parent, col):
        card = _card(parent)
        card.grid(row=0, column=col, sticky="nsew", padx=(6, 0))
        header_row = ctk.CTkFrame(card, fg_color="transparent")
        header_row.pack(padx=12, pady=(4, 2), fill="x")
        _section_title(header_row, "> STRATEGY DECISION MATRIX").pack(side="left", anchor="w")

        hdr = ctk.CTkFrame(card, fg_color=C_BG_INPUT, corner_radius=4)
        hdr.pack(padx=12, pady=(0, 1), fill="x")
        # Trọng số cột, nhân 4 so với bản gốc (1·2·1·1·1) để biểu diễn được bước
        # 0,25. STRATEGY 4 → 8 (rộng gấp đôi), TIMEFRAME 8 → 4 nhả lại đúng phần
        # đó nên tổng KHÔNG ĐỔI và ba cột còn lại giữ nguyên bề ngang.
        #
        # Cần rộng vì nhãn chiến lược nay là `<HỌ>-<CẶP>-<KHUNG>`, dài tới 15 ký tự
        # (`VOLR-GBPCHF-M30`) — xem `strategy_registry._tag_of`. TIMEFRAME thì chỉ
        # chứa hai tới ba ký tự nên phần rộng cũ của nó là chỗ trống thuần tuý.
        cols = [("STRATEGY", 8), ("TIMEFRAME", 4), ("LIVE", 4), ("CUR. R", 4), ("MODE", 4)]
        for i, (_, w) in enumerate(cols):
            hdr.grid_columnconfigure(i, weight=w, uniform="mx_cols")
        for i, (txt, _) in enumerate(cols):
            ctk.CTkLabel(hdr, text=txt, font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                         text_color=C_TEXT_DIM, anchor="w" if i in (0, 1) else "center").grid(
                row=0, column=i, sticky="ew", padx=4, pady=2)

        body = ctk.CTkScrollableFrame(card, fg_color="transparent",
                                      height=self._MATRIX_VISIBLE_ROWS * 26)
        body.pack(padx=(12, 4), pady=(0, 6), fill="both", expand=True)
        self.matrix_body = body

        self.matrix_rows = {}
        self._matrix_order = []
        for name in _DISPLAY_ORDER:
            if name not in _magic_map:
                continue
            rf = ctk.CTkFrame(body, fg_color="transparent")
            rf.pack(padx=0, pady=0, fill="x")
            for i, (_, w) in enumerate(cols):
                rf.grid_columnconfigure(i, weight=w, uniform="mx_cols")
            ctk.CTkLabel(rf, text=name, font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                         text_color=C_TEXT, anchor="w").grid(row=0, column=0, sticky="ew", padx=4, pady=2)
            ctk.CTkLabel(rf, text=_TIMEFRAME.get(name, "—"), font=ctk.CTkFont(family="Consolas", size=14),
                         text_color=C_TEXT_MUT, anchor="w").grid(row=0, column=1, sticky="ew", padx=4)
            enabled_lbl = ctk.CTkLabel(rf, text="●", font=ctk.CTkFont(size=14), text_color=C_TEXT_DIM, anchor="center")
            enabled_lbl.grid(row=0, column=2, sticky="ew", padx=4)
            r_lbl = ctk.CTkLabel(rf, text="—", font=ctk.CTkFont(family="Consolas", size=14), text_color=C_TEXT_MUT,
                                  anchor="center")
            r_lbl.grid(row=0, column=3, sticky="ew", padx=4)
            dec_lbl = ctk.CTkLabel(rf, text="—", width=95, corner_radius=5,
                                    font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                                    fg_color=TAG["blue"]["bg"], text_color=TAG["blue"]["fg"])
            dec_lbl.grid(row=0, column=4, padx=4)

            self.matrix_rows[name] = {"enabled": enabled_lbl, "r": r_lbl,
                                      "dec": dec_lbl, "frame": rf}
            self._matrix_order.append(name)



    _POS_COLS = [
        ("SYMBOL", 90), ("STRATEGY", 130), ("TF", 55),
        ("DIRECTION", 90), ("SIZE (LOTS)", 100), ("ENTRY", 90),
        ("CURRENT", 90), ("P/L ($)", 100), ("SL", 90), ("TP", 90), ("MANAGE", 140),
    ]

    def _build_positions_panel(self, parent, row):
        panel = _card(parent)
        panel.grid(row=row, column=0, sticky="nsew", pady=(0, 10))
        title_row = ctk.CTkFrame(panel, fg_color="transparent")
        title_row.pack(padx=12, pady=(10, 4), fill="x")
        self.pos_title_lbl = _section_title(title_row, "> OPEN POSITIONS (0)")
        self.pos_title_lbl.pack(side="left", anchor="w")
        self.flatten_btn = ctk.CTkButton(
            title_row, text="[ CLOSE ALL ]", height=26, width=120,
            font=ctk.CTkFont(family="Consolas", size=15, weight="bold"),
            fg_color=TAG["red"]["bg"], hover_color=TAG["red"]["bd"],
            text_color=TAG["red"]["fg"], border_width=1, border_color=TAG["red"]["bd"],
            command=self.on_flatten_all)
        self.flatten_btn.pack(side="right")

        hdr = ctk.CTkFrame(panel, fg_color=C_BG_INPUT, corner_radius=4)
        hdr.pack(padx=12, pady=(0, 4), fill="x")
        for txt, w in self._POS_COLS:
            ctk.CTkLabel(hdr, text=txt, width=w, font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                         text_color=C_TEXT_DIM, anchor="w").pack(side="left", padx=4, pady=3)

        self.pos_scroll = ctk.CTkScrollableFrame(panel, fg_color="transparent", height=120)
        self.pos_scroll.pack(padx=12, pady=(0, 10), fill="x")
        try:
            if hasattr(self.pos_scroll, "_scrollbar"):
                self.pos_scroll._scrollbar.grid_remove()
        except Exception:
            pass
        self.pos_widgets = {}
        self.pos_empty_lbl = ctk.CTkLabel(self.pos_scroll, text="NO ACTIVE POSITIONS",
                                           font=ctk.CTkFont(family="Consolas", size=16, slant="italic"),
                                           text_color=C_TEXT_DIM)
        self.pos_empty_lbl.pack(pady=10)

    def _build_health_card(self, parent, col, padx):
        """SYSTEM HEALTH — trước đây là 1 strip ngang riêng chiếm cả hàng
        (6 card cạnh nhau), nay dồn thành 1 card dọc đặt trong hàng giữa
        (thay chỗ bản clone thứ 2 của ACCOUNT OVERVIEW, theo yêu cầu người
        dùng). self.health_widgets giữ nguyên contract {name: (dot,
        status_lbl, lat_lbl)} — update_ui_state() không cần đổi gì."""
        card = _card(parent)
        card.grid(row=0, column=col, sticky="nsew", padx=padx)
        _section_title(card, "> SYSTEM TELEMETRY").pack(padx=12, pady=(4, 2), anchor="w")
        ctk.CTkFrame(card, height=1, fg_color=C_BORDER).pack(fill="x", padx=12, pady=(0, 4))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(padx=12, pady=(0, 6), fill="x")
        grid.grid_columnconfigure((0, 1), weight=1, uniform="health_cols")

        # BỎ NĂM THẺ 15/08/2026: MODEL ENGINE · SOFT REGIME · HARD REGIME H4 ·
        # AI TREND · NEWS FEED.
        #
        # Cả năm kế thừa từ hệ XAUUSD, nơi chúng hiển thị đầu ra của bộ máy AI vĩ mô
        # hai tầng (`ai_moe_engine`, 3.296 dòng). Hệ Forex KHÔNG có bộ máy đó — nó
        # thay bằng `ai/news_guard.py` một tầng, và cổng đó MẶC ĐỊNH TẮT vì đo được
        # là làm hại (Sharpe trung vị 0,811 → 0,622, vòng 63).
        #
        # Nên năm thẻ này hoặc hiện "N/A" vĩnh viễn, hoặc tệ hơn: hiện một nhãn
        # trông có nghĩa nhưng không lớp nào đọc tới. Một thẻ trạng thái mà không
        # quyết định nào phụ thuộc vào nó là chỗ để người vận hành tin nhầm rằng hệ
        # đang canh một thứ nó không canh.
        labels = ["SESSION"]
        icons = {"SESSION": "🕒"}
        self.health_widgets = {}
        # Lưới hai cột. Còn ĐÚNG MỘT thẻ nên nó chiếm cả hai cột — bỏ năm thẻ kia
        # mà giữ nguyên `column=i % 2` sẽ để SESSION nằm co ở nửa trái và nửa phải
        # trống hoác.
        for i, name in enumerate(labels):
            block = ctk.CTkFrame(grid, fg_color=C_BG_INPUT, border_width=1, border_color=C_BORDER, corner_radius=4)
            span = 2 if len(labels) == 1 else 1
            block.grid(row=i // 2, column=0 if span == 2 else i % 2,
                       columnspan=span, sticky="nsew", padx=2, pady=2)
            ctk.CTkLabel(block, text=f"{icons.get(name, '')} {name}", font=ctk.CTkFont(family="Consolas", size=14),
                         text_color=C_TEXT, anchor="w").pack(anchor="w", padx=8, pady=(4, 0))
            val_row = ctk.CTkFrame(block, fg_color="transparent")
            val_row.pack(fill="x", padx=8, pady=(0, 4))
            dot = ctk.CTkLabel(val_row, text="●", font=ctk.CTkFont(size=12), text_color=C_TEXT_DIM)
            dot.pack(side="left", padx=(0, 4))
            status_lbl = ctk.CTkLabel(val_row, text="N/A", font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                                       text_color=C_TEXT_MUT, anchor="w")
            status_lbl.pack(side="left")
            # C_TEXT (trắng) là mặc định của text phụ từ 30/07 — xem ghi chú tại
            # chỗ cập nhật trong `update_ui_state()`. Đặt luôn ở đây để lần vẽ
            # đầu tiên (trước tick cập nhật đầu) không nhấp nháy xám->trắng.
            lat_lbl = ctk.CTkLabel(block, text="N/A", font=ctk.CTkFont(family="Consolas", size=10),
                                    text_color=C_TEXT, anchor="w")
            lat_lbl.pack(anchor="w", padx=8, pady=(0, 4))
            self.health_widgets[name] = (dot, status_lbl, lat_lbl)

    def _build_timeline(self, parent, row):
        panel = _card(parent)
        panel.grid(row=row, column=0, sticky="nsew", pady=(0, 10))

        _section_title(panel, "> EVENT TIMELINE").pack(padx=12, pady=(10, 4), anchor="w")

        toolbar = ctk.CTkFrame(panel, fg_color=C_BG_INPUT, corner_radius=4)
        toolbar.pack(padx=12, pady=(0, 4), fill="x")

        self.timeline_filter_buttons = {}

        for label in ("ALL", "INFO", "WARNING", "ERROR", "TRADE", "GUARD", "AI"):
            btn = ctk.CTkButton(
                toolbar, text=label, width=65, height=25,
                font=ctk.CTkFont(family="Consolas", size=15, weight="bold"),
                fg_color="transparent", hover_color=C_BORDER_ACT, border_width=0,
                text_color=C_TEXT_MUT, command=lambda t=label: self._set_timeline_filter(t),
            )
            btn.pack(side="left", padx=4, pady=2)
            self.timeline_filter_buttons[label] = btn

        ctk.CTkFrame(toolbar, width=1, height=25, fg_color=C_BORDER, corner_radius=0).pack(
            side="right", padx=8, pady=2)
        ctk.CTkButton(toolbar, text="LOGS DIR", width=90, height=25,
                      font=ctk.CTkFont(family="Consolas", size=15, weight="bold"),
                      fg_color=C_BLUE_BTN, hover_color=C_BLUE_BTN_H, text_color=C_BLUE,
                      border_width=1, border_color=C_BLUE_BTN,
                      command=self.open_logs_directory).pack(side="right", padx=4, pady=2)
        ctk.CTkButton(toolbar, text="CLEAR", width=70, height=25,
                      font=ctk.CTkFont(family="Consolas", size=15, weight="bold"),
                      fg_color=C_RED_BTN, hover_color=C_RED_BTN_H, text_color=C_RED,
                      border_width=1, border_color=C_RED_BG,
                      command=self.clear_timeline).pack(side="right", padx=4, pady=2)
        ctk.CTkButton(toolbar, text="COPY", width=70, height=25,
                      font=ctk.CTkFont(family="Consolas", size=15, weight="bold"),
                      fg_color=C_GREEN_BTN, hover_color=C_GREEN_BTN_H, text_color=C_GREEN,
                      border_width=1, border_color=C_GREEN_BTN,
                      command=self.copy_logs).pack(side="right", padx=4, pady=2)

        hdr = ctk.CTkFrame(panel, fg_color=C_BG_INPUT, corner_radius=4)
        hdr.pack(padx=12, pady=(0, 4), fill="x")
        cols = [("TIME", 90), ("CATEGORY", 110), ("MESSAGE", 820)]
        for txt, w in cols:
            ctk.CTkLabel(hdr, text=txt, width=w, font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                         text_color=C_TEXT_DIM, anchor="w").pack(side="left", padx=4, pady=3)

        self.timeline_scroll = ctk.CTkScrollableFrame(panel, fg_color="transparent", height=150)
        self.timeline_scroll.pack(padx=12, pady=(0, 10), fill="both", expand=True)
        self._set_timeline_filter("ALL")

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------
    # ══════════════════════════════════════════════════════════════════════════
    # RUN / STOP ENGINE — CÔNG TẮC VÀO LỆNH, KHÔNG PHẢI CÔNG TẮC ỨNG DỤNG
    # ══════════════════════════════════════════════════════════════════════════
    # ĐỔI NGHĨA 15/08/2026. Trước đó hai nút này chỉ bật/tắt VÒNG LẶP làm mới, tức
    # STOP làm bảng đứng hình mà không thật sự ngăn được gì — trong khi cái người
    # vận hành cần lúc 2 giờ sáng là "ngừng vào lệnh MỚI ngay", không phải "tắt màn
    # hình".
    #
    #     RUN   mọi chiến lược ĐƯỢC PHÉP vào lệnh mới
    #     STOP  lệnh mới BỊ TỪ CHỐI — ứng dụng vẫn chạy bình thường
    #
    # STOP KHÔNG đóng vị thế đang mở, KHÔNG gỡ cầu chì, KHÔNG dừng đếm time-stop.
    # Vị thế đang mở mà mất người quản lý là tình trạng nguy hiểm HƠN việc vào thêm
    # lệnh. Muốn đóng sạch thì dùng FLATTEN ALL — chức năng riêng, có xác nhận riêng.
    #
    # Trạng thái ghi vào `execution/trading_control.py` nên nó SỐNG QUA RESTART: bot
    # tự khởi động lại lúc 3 giờ sáng KHÔNG được tự cho phép vào lệnh trở lại.
    # ══════════════════════════════════════════════════════════════════════════
    # GỌI NGƯỢC VỀ LUỒNG GIAO DIỆN — phải AN TOÀN khi cửa sổ đã đóng
    # ══════════════════════════════════════════════════════════════════════════
    # LỖI ĐÃ SỬA 15/08/2026:
    #
    #     RuntimeError: main thread is not in main loop
    #       gui_command_center.py:1028 in worker → self.root.after(0, ...)
    #
    # Nút RUN chạy công việc trên LUỒNG NỀN rồi gọi `root.after()` để quay về luồng
    # giao diện. Nhưng công việc đó mất vài giây (khởi động vòng lặp, đọc MT5), và
    # nếu trong lúc ấy người dùng đóng cửa sổ — hoặc mở bản thứ hai đè lên bản cũ —
    # thì Tk đã tắt vòng lặp chính, `after()` ném RuntimeError, và luồng nền chết
    # kèm nguyên một traceback đổ vào timeline.
    #
    # Đây là lỗi VÔ HẠI về mặt tiền bạc nhưng độc hại với sổ log: một traceback 12
    # dòng mỗi lần khởi động lại làm chìm mọi dòng có ích.
    def _ui(self, fn, *a) -> None:
        """Xếp `fn` vào hàng đợi để LUỒNG GIAO DIỆN chạy. Gọi được từ luồng nền.

        VÌ SAO KHÔNG GỌI `root.after()` TRỰC TIẾP
        ==========================================
        `after()` KHÔNG an toàn giữa các luồng: nó đăng ký một lệnh Tcl, mà việc đó
        đòi vòng lặp chính đang chạy. Luồng nền của nút RUN mất vài giây (khởi động
        vòng lặp, đọc MT5); nếu trong quãng ấy cửa sổ đóng — hoặc `live_server` dừng
        bản cũ để nạp bản mới — thì vòng lặp chính đã tắt và `after()` ném
        `RuntimeError: main thread is not in main loop`, kéo theo một traceback 12
        dòng đổ vào timeline. Đã xảy ra lúc 12:36:13 ngày 15/08/2026.

        Bọc `try/except` quanh `after()` KHÔNG đủ: cửa sổ có thể đóng ở giữa lúc
        `after()` đang chạy, và kiểm `winfo_exists()` trước đó chỉ thu hẹp cửa sổ
        đua chứ không đóng nó.

        Nay đi qua hàng đợi — ĐÚNG cơ chế mà `log_queue`/`status_queue` đã dùng từ
        đầu. `queue.Queue` an toàn giữa các luồng theo thiết kế, và `process_queues`
        (chạy trên luồng chính, mỗi 100 ms) là bên DUY NHẤT chạm vào Tk. Cửa sổ đóng
        thì `process_queues` ngừng được đặt lịch, phần tồn trong hàng đợi bị bỏ đi
        cùng tiến trình — không có gì để ném lỗi.
        """
        self.ui_queue.put((fn, a))

    def on_arm(self):
        self.arm_btn.configure(state="disabled")

        def worker():
            # Vòng lặp phải chạy thì mới có ai dựng kế hoạch — bật nếu chưa chạy.
            ok = True
            if not getattr(self.engine, "is_running", False):
                ok = self.engine.start_loop()
            if not ok:
                self._ui(self._reset_arm_button)
                return
            self.engine.allow_entries(by="GUI")
            self._ui(self.set_bot_running_ui)
        threading.Thread(target=worker, daemon=True).start()

    def _reset_arm_button(self):
        self.arm_btn.configure(state="normal")
        messagebox.showerror("Lỗi khởi động", "Không thể khởi động hệ thống. Hãy kiểm tra log hoặc kết nối MT5.")

    def set_bot_running_ui(self):
        self.arm_btn.configure(state="disabled")
        self.disarm_btn.configure(state="normal", text_color=C_RED, border_color=C_RED_BG)

    def on_disarm(self):
        self.disarm_btn.configure(state="disabled")

        def worker():
            # KHÔNG gọi `stop_loop()`: ứng dụng phải chạy bình thường để còn đọc tài
            # khoản, đếm time-stop, đối soát sổ vị thế và canh cầu chì. Chỉ chặn
            # đúng một thứ — lệnh MỚI.
            self.engine.block_entries(by="GUI")
            self._ui(self.set_bot_stopped_ui)
        threading.Thread(target=worker, daemon=True).start()

    def set_bot_stopped_ui(self):
        self.arm_btn.configure(state="normal")
        self.disarm_btn.configure(state="disabled", text_color=C_TEXT_MUT, border_color=C_BORDER)

    def on_flatten_all(self):
        try:
            import MetaTrader5 as mt5
            _raw = mt5.positions_get()
            n = -1 if _raw is None else len(_raw)
        except Exception:
            n = -1
        if n == 0:
            messagebox.showinfo("Flatten", "Không có vị thế nào đang mở.")
            return
        if not messagebox.askyesno("FLATTEN ALL", f"Đóng TOÀN BỘ {n if n >= 0 else ''} vị thế?"):
            return
        self._do_flatten_all()

    def _do_flatten_all(self):
        def worker():
            try:
                from src.python.core.infra import mt5_bridge
                closed, total = mt5_bridge.close_all_positions(reason="MANUAL FLATTEN ALL (GUI v2)")
                if total is None:
                    self.engine.log_error(
                        "[MANUAL] FLATTEN ALL: KHÔNG xác định được số vị thế trên broker "
                        "— KHÔNG thể khẳng định đã đóng hết. Kiểm tra terminal MT5 và "
                        "bấm lại, hoặc đóng tay.")
                else:
                    self.engine.log(f"[MANUAL] FLATTEN ALL: đóng {closed}/{total} vị thế (MANUAL OVERRIDE).")
            except Exception as e:
                self.engine.log(f"[MANUAL] FLATTEN lỗi: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def refresh_breaker_state(self):
        """Đồng bộ trạng thái cầu dao ngày vào `engine.state["guards"]` cho thẻ GUI.

        ĐỔI 31/07: hàm này từng vừa đọc trạng thái vừa vẽ lại nút [PAUSE TRADING].
        Nút đó và cặp `manual_pause_today()`/`resume_entries()` đứng sau nó đã bị
        xoá cùng toàn bộ nhóm vận hành thủ công — cầu dao nay CHỈ do drawdown
        thật kích hoạt, nên không còn gì để người dùng bấm. Chỉ giữ phần đọc.
        """
        try:
            from src.python.core.infra.target_mode import breaker_status, DAILY_STOP_DD
            st = breaker_status()
            if "guards" not in self.engine.state:
                self.engine.state["guards"] = {}
            g = self.engine.state["guards"]
            g["breaker_tripped"] = st["tripped"]
            g.setdefault("dd_pct", 0.0)
            g.setdefault("dd_limit", DAILY_STOP_DD * 100.0)
            g.setdefault("margin_pct", 0.0)
            g.setdefault("spread", 0.0)
        except Exception as e:
            self.engine.log(f"[GUI v2 ERROR] refresh_breaker_state: {e}")

    def _set_timeline_filter(self, value):
        self._timeline_filter = value
        if hasattr(self, "timeline_filter_buttons"):
            for tag, btn in self.timeline_filter_buttons.items():
                if tag == value:
                    btn.configure(fg_color=C_BLUE_BTN, border_width=1, border_color=C_BLUE, text_color=C_BLUE)
                else:
                    btn.configure(fg_color="transparent", border_width=0, text_color=C_TEXT_MUT)
        self._rebuild_timeline()

    def clear_timeline(self):
        self.all_logs.clear()
        for f in self._timeline_rows:
            f.destroy()
        self._timeline_rows = []
        if hasattr(self.timeline_scroll, "_scrollbar"):
            self.timeline_scroll._scrollbar.grid_remove()

    def open_logs_directory(self):
        log_dir = os.path.join(PROJECT_ROOT, "logs")
        os.makedirs(log_dir, exist_ok=True)
        webbrowser.open(log_dir)

    def copy_logs(self):
        """Giống nút COPY của gui.py (V1) — copy toàn bộ Event Timeline hiện
        có (all_logs, không phụ thuộc filter đang chọn) vào clipboard dưới dạng rút gọn,
        loại bỏ category/badge và dấu trailing | — | —, tách dòng cho Phán quyết."""
        try:
            lines = []
            for e in self.all_logs:
                msg = e['message']
                if timeline_log.is_noise(msg):
                    continue
                msg_lines = msg.split("\n")
                lines.append(f"{e['time']} | {msg_lines[0]}")
                for extra in msg_lines[1:]:
                    lines.append(extra)

            text = "\n".join(lines)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("Đã sao chép", "Đã sao chép log vào clipboard.")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể sao chép log: {e}")

    # ------------------------------------------------------------------
    # LOG / TIMELINE
    # ------------------------------------------------------------------
    def _append_log(self, msg):
        # Lọc nhiễu + cắt tiền tố/badge nằm ở `utils.timeline_log.normalize()`:
        # dùng CHUNG với nơi ghi file để bản trên màn hình và bản trong
        # `logs/timeline_YYYY-MM-DD.log` không bao giờ khác nhau.
        parsed = timeline_log.normalize(msg)
        if parsed is None:
            return
        time_str, text = parsed
        level, cat, symbol, strategy = categorize_log(msg)
        entry = {"time": time_str, "level": level, "category": cat, "message": text,
                 "symbol": symbol, "strategy": strategy}
        # Ghi ngay khi nhận: đây là nơi ghi DUY NHẤT ở chế độ GUI (engine.log và
        # utils.logger.log tự nhường khi phát hiện stdout đã bị GUI chiếm).
        timeline_log.append(time_str, text)
        self._append_entry(entry)

    def _append_entry(self, entry):
        """Đưa một bản ghi ĐÃ chuẩn hoá vào bộ nhớ + timeline (KHÔNG ghi file).

        Dùng chung cho luồng log mới và luồng nạp lại log cũ trong ngày — bản
        nạp lại vốn đã nằm sẵn trong file, ghi lần nữa sẽ nhân đôi mỗi lần khởi
        động lại.
        """
        self.all_logs.append(entry)
        if len(self.all_logs) > 1500:
            self.all_logs.pop(0)
        self._push_timeline_row(entry)

    # Số dòng nạp lại tối đa. Dựng cả nghìn hàng CTkFrame sẽ treo Tk vài giây;
    # phần cũ hơn vẫn còn nguyên trong file (nút LOGS DIR).
    RESTORE_MAX_ROWS = 300

    def _restore_build_timeline(self):
        """Nạp lại log trong ngày do ĐÚNG BẢN BUILD ĐANG CHẠY ghi.

        VÌ SAO KHÔNG NẠP CẢ NGÀY
        =========================
        File timeline gom theo NGÀY. Một ngày sửa code nhiều lần là một file chứa
        dòng của nhiều bản build, và bản trước (`_restore_today_timeline`) nạp hết
        lên màn hình. Hậu quả đo được ngày 15/08/2026: người vận hành thấy nguyên
        đám dòng vừa bị XOÁ khỏi mã nguồn — do bản build lúc 12:34 ghi — và kết
        luận rằng sáu vòng sửa log không có tác dụng, trong khi tệp log không dài
        thêm một dòng nào kể từ lúc nạp bản mới.

        Một màn hình nói dối về trạng thái HIỆN TẠI nguy hiểm hơn một màn hình
        thiếu ngữ cảnh. Nay `timeline_log.mark_build` đóng mốc mỗi lần khởi động,
        và chỗ này chỉ lấy phân đoạn của build đang chạy: khởi động lại CÙNG một
        bản thì ngữ cảnh còn đủ, còn dòng của bản khác không lọt vào.
        """
        try:
            from src.python.core.runtime_meta import version as _build_version

            build = _build_version()
            timeline_log.mark_build(build)
            entries = timeline_log.load_build(build, limit=self.RESTORE_MAX_ROWS)
        except Exception as exc:                                # pragma: no cover
            print(f"[GUI] Không nạp lại được timeline: {exc}", flush=True)
            return

        for item in entries:
            message = item["message"]
            level, cat, symbol, strategy = categorize_log(message)
            self._append_entry({"time": item["time"], "level": level, "category": cat,
                                "message": message, "symbol": symbol, "strategy": strategy})

    def _row_matches_filter(self, entry):
        return self._timeline_filter == "ALL" or entry["level"] == self._timeline_filter

    def _push_timeline_row(self, entry):
        if not self._row_matches_filter(entry):
            return
        rf = ctk.CTkFrame(self.timeline_scroll, fg_color="transparent")
        variant = _LEVEL_VARIANT.get(entry["level"], "blue")
        level_color = TAG[variant]["fg"]
        cols = [
            (entry["time"], 90, C_TEXT_DIM, "normal"),
            (entry["category"], 110, level_color, "bold"),
            (entry["message"], 820, level_color, "normal"),
        ]
        for txt, w, color, weight in cols:
            ctk.CTkLabel(rf, text=txt, width=w, font=ctk.CTkFont(family="Consolas", size=14, weight=weight),
                         text_color=color, anchor="w", justify="left").pack(side="left", padx=4, pady=2)
        if self._timeline_rows:
            rf.pack(fill="x", before=self._timeline_rows[0])
            gm = getattr(rf, "_last_geometry_manager_call", None)
            if gm:
                gm["kwargs"].pop("before", None)
        else:
            rf.pack(fill="x")
        self._timeline_rows.insert(0, rf)
        while len(self._timeline_rows) > 200:
            old = self._timeline_rows.pop()
            old.destroy()
        
        # Chỉ hiện scrollbar khi số lượng log vượt quá khung nhìn (> 4 dòng)
        if hasattr(self.timeline_scroll, "_scrollbar"):
            if len(self._timeline_rows) > 4:
                self.timeline_scroll._scrollbar.grid()
            else:
                self.timeline_scroll._scrollbar.grid_remove()

    def _rebuild_timeline(self):
        for f in self._timeline_rows:
            f.destroy()
        self._timeline_rows = []
        for entry in self.all_logs[-500:]:
            self._push_timeline_row(entry)

    # ------------------------------------------------------------------
    # STATE UPDATE
    # ------------------------------------------------------------------
    def _update_guard_card(self, state):
        if not hasattr(self, "guard_tags"):
            return
        
        connected = bool(state.get("mt5_connected"))
        if "mt5_terminal" in self.guard_tags:
            self.guard_tags["mt5_terminal"].configure(
                text="CONNECTED" if connected else "DISCONNECTED",
                text_color=C_GREEN if connected else C_RED
            )
        # SERVER — chuyển từ lưới SYSTEM TELEMETRY về card này (04/08).
        # Đọc cùng nguồn `state["account"]` như trước để không đổi ngữ nghĩa.
        if "server" in self.guard_tags:
            acc = state.get("account") or state.get("account_info") or {}
            server_name = str(acc.get("server") or "")
            if not server_name and connected:
                try:
                    import MetaTrader5 as mt5
                    info = mt5.account_info()
                    if info and hasattr(info, "server"):
                        server_name = str(info.server or "")
                except Exception:
                    pass
            name = server_name if server_name else "N/A"
            self.guard_tags["server"].configure(
                text=name, text_color=C_TEXT if name != "N/A" else C_TEXT_MUT)

            self._refresh_account_and_mode(connected)

        try:
            from src.python.core.infra import risk_guard
            rg_st = risk_guard.state
            from src.python.core.config import INP_MAX_TRADES_DAY, INP_MAX_CONSEC_LOSS_DAY
            
            trades = rg_st.get("trades_today", 0)
            max_trades = INP_MAX_TRADES_DAY
            t_color = C_RED if trades >= max_trades else (C_AMBER if trades >= max_trades - 2 else C_TEXT)
            self.guard_tags["trades_today"].configure(text=f"{trades}", text_color=t_color)

            consec = rg_st.get("consec_loss", 0)
            max_consec = INP_MAX_CONSEC_LOSS_DAY
            c_color = C_RED if consec >= max_consec else (C_AMBER if consec >= max_consec - 1 else C_TEXT)
            self.guard_tags["consec_loss"].configure(text=f"{consec}", text_color=c_color)

            from src.python.core.broker.order_state_machine import OrderStateMachine
            is_halted = OrderStateMachine.is_trading_halted() or bool(rg_st.get("halt_reason"))
            h_color = C_RED if is_halted else C_GREEN
            self.guard_tags["halt"].configure(text=f"{'YES' if is_halted else 'NO'}", text_color=h_color)
        except Exception:
            pass

        is_standby = is_forex_weekend() or state.get("market_closed", False)
        g = state.get("guards") or {}
        if g.get("breaker_tripped"):
            dd = g.get("dd_pct", 0.0)
            txt, color = f"⛔ BLOCK: DAILY DD −{dd:.1f}%", C_RED
        elif is_standby or not self.engine.is_running:
            txt, color = "STAND BY", C_AMBER
        else:
            txt, color = "MONITORING", C_GREEN
        self.guard_main_lbl.configure(text=txt, text_color=color)

    def _refresh_account_and_mode(self, connected: bool) -> None:
        """Số hiệu tài khoản và pha FTMO đang áp dụng.

        Hai dòng này trả lời "đang nối tới tài khoản NÀO và nó chịu luật gì" —
        câu hỏi đầu tiên khi một máy chạy nhiều tài khoản, và là thứ phân biệt
        một lệnh sai tài khoản với một lệnh đúng.

        Fail-soft: đọc hỏng thì hiện "N/A" chứ không làm gãy vòng vẽ GUI.
        """
        account_text = "N/A"
        if connected:
            try:
                import MetaTrader5 as mt5
                info = mt5.account_info()
                login = int(getattr(info, "login", 0) or 0)
                if login > 0:
                    account_text = str(login)
            except Exception:
                pass
        if "account" in self.guard_tags:
            self.guard_tags["account"].configure(
                text=account_text,
                text_color=C_TEXT if account_text != "N/A" else C_TEXT_MUT)

        mode_text, mode_color = "N/A", C_TEXT_MUT
        try:
            from src.python.core.infra import ftmo

            phase = str(ftmo._read_state().get("phase") or "").upper()
            if phase:
                mode_text = phase
                mode_color = C_GREEN if phase != "CHALLENGE" else C_TEXT
        except Exception:
            pass
        if "ftmo_mode" in self.guard_tags:
            self.guard_tags["ftmo_mode"].configure(text=mode_text, text_color=mode_color)

    def update_ui_state(self, state):
        self.refresh_breaker_state()
        self._update_guard_card(state)

        connected = bool(state.get("mt5_connected"))
        acc = state.get("account_info", {}) or {}
        g = state.get("guards") or {}
        eq = float(acc.get("equity", 0.0) or 0.0)
        is_standby = is_forex_weekend() or state.get("market_closed", False)

        # ACCOUNT OVERVIEW — cập nhật ĐỒNG THỜI mọi bản clone (trái + phải)
        if connected:
            bal = float(acc.get("balance", 0.0) or 0.0)
            open_positions = state.get("positions_list") or []
            open_pnl = sum(float(p.get("profit", 0.0)) for p in open_positions)
            has_open = bool(open_positions)
            free_margin = None
            try:
                import MetaTrader5 as mt5
                mt5_acc = mt5.account_info()
                free_margin = float(mt5_acc.margin_free) if mt5_acc else None
            except Exception:
                free_margin = None
            for w in self.account_cards:
                w["balance"].configure(text=f"${bal:,.2f}", text_color=C_TEXT_MUT if is_standby else C_TEXT)
                w["equity"].configure(text=f"${eq:,.2f}", text_color=C_TEXT_MUT if is_standby else (C_GREEN if eq >= bal else C_RED))
                w["openpnl"].configure(
                    text=(f"{'+' if open_pnl >= 0 else ''}${open_pnl:,.2f}" if has_open else ""),
                    text_color=C_TEXT_MUT if (is_standby or not has_open)
                    else (C_GREEN if open_pnl >= 0 else C_RED))
                w["freemargin"].configure(text=f"${free_margin:,.2f}" if free_margin is not None else "N/A", text_color=C_TEXT_MUT if is_standby else C_TEXT)
        else:
            for w in self.account_cards:
                for key in ("balance", "equity", "openpnl", "freemargin"):
                    w[key].configure(text="N/A", text_color=C_TEXT_MUT)

        # DAILY PNL + DRAWDOWN (DAILY): ĐỂ TRỐNG khi hôm nay CHƯA vào lệnh nào
        # (yêu cầu người dùng 29/07). Trước đây hiển thị `+0.0` và `0.00%` — hai giá
        # trị đó KHÔNG phân biệt được "chưa giao dịch" với "đã giao dịch và hoà",
        # tức người đọc không biết bot đang im vì chưa có tín hiệu hay vì kết quả
        # đang bằng 0. Chuỗi rỗng là câu trả lời trung thực cho "chưa có gì để báo".
        #
        # `trades_today is None` = KHÔNG ĐỌC ĐƯỢC bộ đếm (lỗi risk_guard) — khác hẳn
        # `0`. Trường hợp đó vẫn hiển thị số như cũ: thà hiện một số có thể vô nghĩa
        # còn hơn để trống và làm người dùng tin rằng chưa có lệnh nào.
        traded_today = None if not g else g.get("trades_today")
        closed_today = state.get("closed_trades_today")
        no_trade_yet = (traded_today == 0) and not (closed_today or 0)

        if g and not no_trade_yet:
            for w in self.account_cards:
                w["dd_daily"].configure(text=f"{float(g.get('dd_pct', 0.0)):.2f}%",
                                        text_color=C_TEXT_MUT if is_standby else C_TEXT)
        elif no_trade_yet:
            for w in self.account_cards:
                w["dd_daily"].configure(text="", text_color=C_TEXT_MUT)
        else:
            for w in self.account_cards:
                w["dd_daily"].configure(text="N/A", text_color=C_TEXT_MUT)

        # MAX DD — phần ngân sách 10% TĨNH đã tiêu, đo từ VỐN BAN ĐẦU.
        #
        # Khác hẳn DAILY DD: mẫu số là vốn ban đầu và KHÔNG đổi khi tài khoản
        # tăng trưởng (luật FTMO 2-Step). Lãi lên $120k thì sàn vẫn $90k, nên
        # con số này càng nhỏ dần khi tài khoản lớn lên — đó là thông tin, không
        # phải lỗi làm tròn.
        max_dd_text, max_dd_color = "N/A", C_TEXT_MUT
        try:
            from src.python.core.infra import ftmo as _ftmo

            _st = _ftmo._read_state()
            initial = float(_st.get("initial_balance") or 0.0)
            equity = float(state.get("equity") or 0.0)
            if initial > 0 and equity > 0:
                used_pct = max(0.0, (initial - equity) / initial) * 100.0
                limit_pct = _ftmo.MAX_LOSS_HARD * 100.0
                max_dd_text = f"{used_pct:.2f}% / {limit_pct:.0f}%"
                # Đổi màu theo mức tiêu ngân sách: quá nửa là đáng nhìn, quá
                # 80% là sát mức mất tài khoản.
                ratio = used_pct / limit_pct if limit_pct else 0.0
                max_dd_color = (C_RED if ratio >= 0.8
                                else (C_AMBER if ratio >= 0.5 else C_TEXT))
        except Exception:
            pass
        if is_standby:
            max_dd_color = C_TEXT_MUT
        for w in self.account_cards:
            if "dd_max" in w:
                w["dd_max"].configure(text=max_dd_text, text_color=max_dd_color)


        if no_trade_yet:
            for w in self.account_cards:
                w["daily_pnl"].configure(text="", text_color=C_TEXT_MUT)
        else:
            daily_pnl = float(state.get("daily_profit", 0.0) or 0.0)
            sign2 = "+" if daily_pnl >= 0 else "-"
            for w in self.account_cards:
                w["daily_pnl"].configure(
                    text=f"{sign2}${abs(daily_pnl):,.2f}",
                    text_color=C_TEXT_MUT if is_standby else (C_GREEN if daily_pnl >= 0 else C_RED))

        # SPREAD — engine trả DICT {symbol: bps} cho 27 công cụ, không phải một số.
        # Bản kế thừa từ hệ XAUUSD một tài sản format thẳng `f"{spread:.2f}"`, và
        # với dict thì đó là `TypeError`. Lỗi bị `status_callback` nuốt, nên MỌI thẻ
        # sau dòng này ngừng vẽ mà không có gì báo — đúng triệu chứng "các card không
        # load" đã gặp. Sửa 15/08/2026.
        spread = state.get("spread")
        if isinstance(spread, dict) and spread:
            vals = sorted(spread.values())
            med = vals[len(vals) // 2]
            over = [s for s, v in spread.items() if v > SPREAD_CAP]
            txt = f"{med:.2f} bps" + (f" · {len(over)} vượt trần" if over else "")
            col = C_RED if over else C_TEXT
        elif isinstance(spread, (int, float)) and spread:
            txt, col = f"{spread:.2f}", (C_RED if spread > SPREAD_CAP else C_TEXT)
        else:
            txt, col = "N/A", C_TEXT
        for w in self.account_cards:
            w["spread"].configure(text=txt,
                                  text_color=C_TEXT_MUT if is_standby else col)

        # AI TREND nay nằm trong SYSTEM TELEMETRY (xem `get_system_health`).

        # STRATEGY DECISION MATRIX
        try:
            matrix = get_decision_matrix_rows(state)
            for row in matrix:
                w = self.matrix_rows.get(row["name"])
                if not w:
                    continue
                # Chấm XANH chỉ khi chiến lược VỪA còn trong danh mục VỪA được
                # trạng thái thị trường cho phép — xem `get_decision_matrix_rows`.
                # `row.get("live", row["enabled"])` để bản ghi cũ (chưa có khoá
                # mới) vẫn render đúng như trước thay vì tắt hết thành xám.
                _live = row.get("live", row["enabled"])
                w["enabled"].configure(
                    text_color=C_TEXT_MUT if is_standby
                    else (TAG["green"]["fg"] if _live else C_TEXT_DIM))
                w["r"].configure(text=row["r"], text_color=C_TEXT_MUT if is_standby else C_TEXT)
                variant = {"ACTIVE": "blue", "SCANNING": "green", "STOPPED": "amber",
                           "BLOCKED": "red", "STAND BY": "amber",
                           "REGIME OFF": "amber"}.get(row["decision"], "blue")
                w["dec"].configure(text=row["decision"], fg_color=TAG[variant]["bg"], text_color=TAG[variant]["fg"])
            # Sắp xếp lại vị trí hàng CHỈ KHI thứ tự đổi (chiến lược vào/ra
            # lệnh). Gọi pack_forget + pack mỗi chu kỳ refresh sẽ làm bảng
            # nhấp nháy dù không có gì thay đổi.
            order = [r["name"] for r in matrix if r["name"] in self.matrix_rows]
            if order != self._matrix_order:
                for name in order:
                    frame = self.matrix_rows[name].get("frame")
                    if frame is not None:
                        frame.pack_forget()
                        frame.pack(padx=0, pady=0, fill="x")
                self._matrix_order = order
        except Exception:
            pass

        # SYSTEM HEALTH
        try:
            health = get_system_health(state)
            for name, (dot, status_lbl, lat_lbl) in self.health_widgets.items():
                row = health.get(name, ("N/A", "N/A"))
                # 3-tuple = hàng tự khai báo màu riêng (SESSION/REGIME, 30/07);
                # 2-tuple = hàng theo quy tắc ok/bad chung như trước.
                status, lat = row[0], row[1]
                own_color = row[2] if len(row) > 2 else None
                ok_words = ("CONNECTED", "HEALTHY", "SYNCED")
                bad_words = ("DISCONNECTED", "STALE", "NO DATA")
                color = C_TEXT_MUT if is_standby else (
                    own_color or (C_GREEN if status in ok_words
                                  else (C_RED if status in bad_words else C_TEXT_DIM)))
                dot.configure(text_color=color)
                status_lbl.configure(text=status, text_color=color if status not in ("N/A",) else C_TEXT_MUT)
                # Text phụ = TRẮNG mặc định (yêu cầu người dùng 30/07). Trước đây
                # là C_TEXT_DIM (#5D665F) — trên nền card tối thì gần như không
                # đọc được, mà đây toàn là thông tin cần đọc thật: giờ cập nhật
                # macro, % hoạt động phiên, tên model engine.
                lat_lbl.configure(text=lat, text_color=C_TEXT_MUT if is_standby else C_TEXT)
        except Exception:
            pass

        # OPEN POSITIONS
        self._update_positions(state)

    def _update_positions(self, state):
        pos_list = state.get("positions_list", [])
        # GIỮ NGUYÊN CHUỖI LỖI, không ép về bool.
        #
        # Bản cũ làm `bool(...)` rồi hiện một câu cố định "MT5 lỗi hoặc mất kết nối".
        # Nhưng `engine._read_broker` đã đặt vào đây chính `mt5.last_error()` — mã lỗi
        # nói rõ là sai đường dẫn terminal, sai tên server, hay sai mật khẩu. Ép về
        # bool là vứt đúng thứ người vận hành cần rồi bắt họ đoán.
        #
        # Đo được trên VPS 16/08/2026: hai terminal MT5 đang chạy mà bảng vẫn
        # DISCONNECTED, và không đâu trên màn hình nói được vì sao.
        read_error_msg = str(state.get("positions_read_error") or "")
        read_error = bool(read_error_msg)
        self.pos_title_lbl.configure(
            text=("> OPEN POSITIONS (?)" if read_error
                  else f"> OPEN POSITIONS ({len(pos_list)})"))

        if hasattr(self.pos_scroll, "_scrollbar"):
            if len(pos_list) > 2:
                self.pos_scroll._scrollbar.grid()
            else:
                self.pos_scroll._scrollbar.grid_remove()

        if not pos_list:
            if self.pos_empty_lbl is None:
                self.pos_empty_lbl = ctk.CTkLabel(
                    self.pos_scroll,
                    text=(f"!! KHÔNG ĐỌC ĐƯỢC VỊ THẾ — {read_error_msg}"
                          if read_error else "NO ACTIVE POSITIONS"),
                    font=ctk.CTkFont(family="Consolas", size=16, slant="italic"),
                    wraplength=900, justify="center",
                    text_color=(C_RED if read_error else C_TEXT_DIM))
                self.pos_empty_lbl.pack(pady=10)
            else:
                # Nhãn đã tồn tại từ chu kỳ trước: phải cập nhật, nếu không nó
                # kẹt ở trạng thái cũ khi kết nối hỏng rồi phục hồi.
                self.pos_empty_lbl.configure(
                    text=(f"!! KHÔNG ĐỌC ĐƯỢC VỊ THẾ — {read_error_msg}"
                          if read_error else "NO ACTIVE POSITIONS"),
                    text_color=(C_RED if read_error else C_TEXT_DIM))
            for tk_, w in list(self.pos_widgets.items()):
                w["frame"].destroy()
            self.pos_widgets = {}
            return
        elif self.pos_empty_lbl is not None:
            self.pos_empty_lbl.destroy()
            self.pos_empty_lbl = None

        active_tickets = set()
        for p in pos_list:
            ticket = p["ticket"]
            active_tickets.add(ticket)
            if ticket in self.pos_widgets:
                self._refresh_position_row(self.pos_widgets[ticket], p)
            else:
                w = self._create_position_row(p)
                self.pos_widgets[ticket] = w
                self._refresh_position_row(w, p)

        for ticket in list(self.pos_widgets.keys()):
            if ticket not in active_tickets:
                self.pos_widgets[ticket]["frame"].destroy()
                del self.pos_widgets[ticket]

    def _create_position_row(self, p):
        """Style clone từ _push_timeline_row() (Event Timeline) — frame trong
        suốt (không phải card bo góc riêng từng dòng), label cùng width/anchor/
        padx/pady với header, để 2 bảng trông đồng bộ 1 hệ thống."""
        frame = ctk.CTkFrame(self.pos_scroll, fg_color="transparent")
        frame.pack(fill="x")

        c_type = C_GREEN if p["type"] == "BUY" else C_RED
        ctk.CTkLabel(frame, text=p["symbol"], width=90, font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                     text_color=C_TEXT, anchor="w", justify="left").pack(side="left", padx=4, pady=4)
        # STRATEGY + TF — "?" khi vị thế không thuộc chiến lược nào đã đăng ký
        # (mở tay, hoặc còn sót từ phiên bản cũ). Nói "?" đúng hơn để trống.
        ctk.CTkLabel(frame, text=str(p.get("strategy") or "?"), width=130,
                     font=ctk.CTkFont(family="Consolas", size=14),
                     text_color=C_TEXT, anchor="w", justify="left").pack(side="left", padx=4, pady=4)
        ctk.CTkLabel(frame, text=str(p.get("timeframe") or "?"), width=55,
                     font=ctk.CTkFont(family="Consolas", size=14),
                     text_color=C_TEXT_MUT, anchor="w", justify="left").pack(side="left", padx=4, pady=4)
        ctk.CTkLabel(frame, text=p["type"], width=90, font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                     text_color=c_type, anchor="w", justify="left").pack(side="left", padx=4, pady=4)
        ctk.CTkLabel(frame, text=f"{p['volume']:.2f}", width=100, font=ctk.CTkFont(family="Consolas", size=14),
                     text_color=C_TEXT_MUT, anchor="w", justify="left").pack(side="left", padx=4, pady=4)
        ctk.CTkLabel(frame, text=f"{p['price_open']:.2f}", width=90, font=ctk.CTkFont(family="Consolas", size=14),
                     text_color=C_TEXT_MUT, anchor="w", justify="left").pack(side="left", padx=4, pady=4)
        current_lbl = ctk.CTkLabel(frame, text="", width=90, font=ctk.CTkFont(family="Consolas", size=14),
                                    anchor="w", justify="left")
        current_lbl.pack(side="left", padx=4, pady=4)
        pl_lbl = ctk.CTkLabel(frame, text="", width=100, font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
                               anchor="w", justify="left")
        pl_lbl.pack(side="left", padx=4, pady=4)
        sl_lbl = ctk.CTkLabel(frame, text="", width=90, font=ctk.CTkFont(family="Consolas", size=14),
                               text_color=C_RED, anchor="w", justify="left")
        sl_lbl.pack(side="left", padx=4, pady=4)
        tp_lbl = ctk.CTkLabel(frame, text="", width=90, font=ctk.CTkFont(family="Consolas", size=14),
                               text_color=C_GREEN, anchor="w", justify="left")
        tp_lbl.pack(side="left", padx=4, pady=4)

        btn_row = ctk.CTkFrame(frame, fg_color="transparent", width=140)
        btn_row.pack(side="left", padx=4, pady=4)
        for _txt, _cmd, _variant in [
                ("BE", lambda t=p["ticket"], e=p["price_open"], s=p["symbol"], sd=p["type"]:
                 self._manual_be(t, e, s, sd), "green"),
                ("1/2", lambda t=p["ticket"], v=p["volume"], s=p["symbol"]: self._manual_half(t, v, s), "amber"),
                ("X", lambda t=p["ticket"], s=p["symbol"]: self._manual_close(t, s), "red")]:
            ctk.CTkButton(btn_row, text=_txt, width=40, height=20, font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
                          fg_color=TAG[_variant]["bg"], hover_color=TAG[_variant]["bd"], text_color=TAG[_variant]["fg"],
                          border_width=1, border_color=TAG[_variant]["bd"], command=_cmd).pack(side="left", padx=2)

        return {"frame": frame, "current": current_lbl, "pl": pl_lbl, "sl": sl_lbl, "tp": tp_lbl}

    def _refresh_position_row(self, w, p):
        profit = float(p["profit"])
        cur, entry = float(p["price_current"]), float(p["price_open"])
        w["current"].configure(text=f"{cur:.2f}", text_color=C_GREEN if cur >= entry else C_RED)
        w["pl"].configure(text=f"{'+' if profit >= 0 else ''}${profit:.2f}",
                           text_color=C_GREEN if profit >= 0 else (C_RED if profit < 0 else C_TEXT_MUT))
        w["sl"].configure(text=f"{p['sl']:.2f}" if p.get("sl") else "—")
        w["tp"].configure(text=f"{p['tp']:.2f}" if p.get("tp") else "—")

    def _manual_be(self, ticket, entry, symbol, side="BUY"):
        """Dời cầu chì của MỘT vị thế về ngay trên/dưới giá vào (break-even).

        VIẾT LẠI 15/08/2026 — nút này TRƯỚC ĐÓ KHÔNG CHẠY.
        ===================================================
        Bản cũ gọi `core.execution.position_execution_service.move_stop`, module port
        từ hệ XAUUSD. Module đó import `position_lifecycle`, `core.management_command_log`
        và `shared.execution_rules.exit_rules` — cả ba KHÔNG TỒN TẠI ở hệ Forex, nên
        dòng `import` ném `ImportError`, `except` bên dưới nuốt, và người vận hành chỉ
        thấy một dòng "[MANUAL] BE #x lỗi: …" rồi tưởng là trục trặc nhất thời. Bấm
        bao nhiêu lần cũng vậy.

        Nay gọi thẳng `mt5_bridge.modify_position_sl_api` — đường THỦ CÔNG vốn đã có
        sẵn và đã làm nền cho FLATTEN ALL, đóng tay, đóng nửa. Nó tự làm tròn SL theo
        `SymbolSpec` và tự tôn trọng stops/freeze level của broker.

        BIÊN TÍNH THEO ĐIỂM GIÁ CỦA TỪNG CẶP, không phải hằng số.
        Bản cũ dùng `0.10 if entry > 100 else 0.002` — con số của vàng và của cặp
        chấm-năm-chữ-số. Với USDJPY (giá ~150, hai chữ số thập phân) nhánh `> 100`
        cho 0,10 tức 10 pip; với EURUSD thì 0,002 là 20 pip. Hai cặp cùng một nút mà
        biên lệch nhau cả chục lần. Nay biên = 20 lần điểm giá của chính công cụ đó.
        """
        def worker():
            try:
                from src.python.core.infra import mt5_bridge
                from src.python.core.infra.symbol_spec import get_symbol_spec

                point = float(get_symbol_spec(symbol).point)
                if point <= 0:
                    raise ValueError(f"{symbol}: point <= 0, không tính được biên")
                offset = 20.0 * point
                new_sl = float(entry) + (offset if side == "BUY" else -offset)
                ok = mt5_bridge.modify_position_sl_api(
                    int(ticket), new_sl, symbol=symbol)
                self.engine.log(
                    f"[MANUAL] BE #{ticket} {symbol} -> {new_sl:.5f}: "
                    f"{'OK' if ok else 'BỎ QUA/FAIL'} (MANUAL OVERRIDE)")
            except Exception as e:
                self.engine.log(f"[MANUAL] BE #{ticket} lỗi: "
                                f"{type(e).__name__}: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _manual_half(self, ticket, volume, symbol):
        if not messagebox.askyesno("Đóng 50%", f"Đóng 50% vị thế #{ticket}?"):
            return

        def worker():
            try:
                from src.python.core.infra import mt5_bridge
                half = max(0.01, round(volume / 2, 2))
                ok = mt5_bridge.close_position_api(int(ticket), volume=half, symbol=symbol)
                self.engine.log(f"[MANUAL] CLOSE 1/2 #{ticket} ({half} lot): {'OK' if ok else 'FAIL'}")
            except Exception as e:
                self.engine.log(f"[MANUAL] 1/2 #{ticket} lỗi: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _manual_close(self, ticket, symbol):
        if not messagebox.askyesno("Đóng vị thế", f"Đóng TOÀN BỘ vị thế #{ticket}?"):
            return

        def worker():
            try:
                from src.python.core.infra import mt5_bridge
                ok = mt5_bridge.close_position_api(int(ticket), symbol=symbol)
                self.engine.log(f"[MANUAL] CLOSE #{ticket}: {'OK' if ok else 'FAIL'}")
            except Exception as e:
                self.engine.log(f"[MANUAL] CLOSE #{ticket} lỗi: {e}")
        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    def on_close(self):
        if self.engine.is_running:
            if not messagebox.askokcancel("XÁC NHẬN THOÁT", "Engine đang chạy, xác nhận thoát?"):
                return
        self.engine.stop_loop()
        self.root.destroy()

    AUTO_ARM_DELAY_MS = 800

    def _auto_started(self) -> None:
        def _write(msg: str) -> None:
            try:
                self.engine.log(msg)
            except Exception:
                print(msg)

        if os.environ.get("CHEOPARD_NO_AUTO_ARM", "").strip().lower() in ("1", "true", "yes"):
            _write("[GUI] Bỏ qua tự khởi động engine (CHEOPARD_NO_AUTO_ARM).")
            return
        try:
            if getattr(self.engine, "is_running", lambda: False)():
                return                      # đã chạy sẵn -> không bấm chồng
        except Exception:
            pass
        # _ghi("[GUI] Tự khởi động engine (không cần bấm [RUN ENGINE]). "
        #      "Đặt CHEOPARD_NO_AUTO_ARM=1 để tắt.")
        self.on_arm()

    def _sync_buttons(self) -> None:
        """Đồng bộ nút RUN/STOP với công tắc THẬT trên đĩa.

        Công tắc `trading_control` sống qua restart, nên trạng thái nút lúc mở ứng
        dụng phải ĐỌC TỪ NÓ, không phải mặc định cứng. Bản trước luôn khởi tạo
        RUN=bật / STOP=tắt, nên mở ứng dụng lên là KHÔNG BẤM ĐƯỢC STOP dù hệ đang
        cho vào lệnh — người vận hành mất đúng cái nút cần nhất.
        """
        try:
            on = bool(self.engine.entries_allowed)
        except Exception:
            on = True
        if on:
            self.arm_btn.configure(state="disabled")
            self.disarm_btn.configure(state="normal", text_color=C_RED,
                                      border_color=C_RED_BG)
        else:
            self.arm_btn.configure(state="normal")
            self.disarm_btn.configure(state="disabled", text_color=C_TEXT_MUT,
                                      border_color=C_BORDER)

    def run(self):
        self._sync_buttons()
        self.root.after(self.AUTO_ARM_DELAY_MS, self._auto_started)
        self.root.mainloop()
