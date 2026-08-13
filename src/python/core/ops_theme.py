# -*- coding: utf-8 -*-
"""ops_theme.py — BẢNG MÀU NGỮ NGHĨA, tách khỏi giao diện đồ hoạ.

VÌ SAO TÁCH RA THÀNH MODULE RIÊNG
==================================
Bảng màu này sinh ra cho `gui_command_center.py`, và ngày 19/08/2026 tệp đó bị xoá
(chuyển sang console-only để bỏ chi phí RAM/CPU của Tk trên VPS). Nhưng bản thân
bảng màu KHÔNG phải thứ thuộc về giao diện: nó là quy ước "màu nào nghĩa gì" của cả
hệ — lục là tăng/đạt, đỏ là giảm/cảnh báo, hổ phách là trạng thái duy nhất chặn vào
lệnh. Console cần đúng những quy ước đó.

GIÁ TRỊ CHÉP NGUYÊN VĂN, KHÔNG THÊM MÀU MỚI
============================================
Mọi mã hex dưới đây lấy y nguyên từ `gui_command_center.py` trước khi xoá. Không
thêm sắc mới, không thêm biến thể: người vận hành đã đọc bảng điều khiển này nhiều
tuần, và đổi nghĩa của một màu tốn nhiều hơn là tiết kiệm. Cặp chữ/nền của bản gốc
đạt tương phản WCAG AA (>= 4,5:1) trên nền tối; console giữ nguyên phần chữ.

`TAG` là hệ thẻ dùng chung (6 sắc). Terminal chỉ dùng khoá `fg` — nó không vẽ nền
thẻ được như widget, nên `bg`/`bd` giữ lại để không mất thông tin thiết kế nếu về
sau cần dựng lại bảng bằng `rich.panel`.
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────── nền & viền
C_BG_ROOT     = "#0A101A"   # nền cửa sổ — đen ngả lam
C_BG_SIDEBAR  = "#0D1420"
C_BG_CARD     = "#121B2A"
C_BG_INPUT    = "#0E1622"

C_BORDER      = "#1E2C40"
C_BORDER_ACT  = "#31527D"

# ─────────────────────────────────────────────────────────── hệ thẻ dùng chung
TAG = {
    "orange": {"bg": "#2E2519", "fg": "#E0913F", "bd": "#5E4526"},
    "red":    {"bg": "#311D22", "fg": "#FF6B7A", "bd": "#6B333C"},
    "amber":  {"bg": "#2E2818", "fg": "#E8B84B", "bd": "#5E4F25"},
    "blue":   {"bg": "#16273D", "fg": "#5AB0FF", "bd": "#2E5480"},
    "green":  {"bg": "#152B24", "fg": "#3DD68C", "bd": "#2A5B45"},
    "purple": {"bg": "#241F3A", "fg": "#A98BF5", "bd": "#463C70"},
}

# ─────────────────────────────────────────────────────────── chữ
C_TEXT        = "#E8EEF6"
C_TEXT_MUT    = "#96A9C2"
C_TEXT_DIM    = "#5F7390"

# ─────────────────────────────────────────────────────────── sắc ngữ nghĩa
C_GREEN       = "#2FD48A"   # tăng / đạt
C_GREEN_HI    = "#4BEFA3"
C_RED         = "#FF5C6E"   # giảm / cảnh báo
C_BLUE        = "#4FA8FF"   # NHẤN CHÍNH của hệ Forex
C_AMBER       = "#F0BE4A"
C_TEAL        = "#2DD4BF"
C_VIOLET      = "#A78BFA"
C_ORANGE      = "#FF9A4D"

# ĐÃ BỎ khi xoá giao diện: `C_*_BTN` / `C_*_BTN_H` / `C_RED_BG`. Chúng là màu nền và
# màu hover của NÚT BẤM — console không có nút, và giữ lại hằng số không ai đọc chỉ
# mời người sau dùng sai chỗ.

# ─────────────────────────────────────────────────────────── màu theo PHIÊN
# Xếp theo MỨC ĐỘ, không random: phiên càng sôi động màu càng "nóng"/sáng.
# Khoá là chuỗi THÔ, lấy từ SSOT `shared/regime_taxonomy.TIME_REGIME_LABELS`.
SESSION_COLOR = {
    "ASIAN":         C_BLUE,      # phiên Á — lặng, biên hẹp
    "LONDON":        C_AMBER,     # London — thanh khoản tăng
    "NEW_YORK":      C_GREEN_HI,  # chồng lấn London-NY — đỉnh điểm
    "NEW_YORK_ONLY": C_TEAL,      # chỉ còn NY — còn chạy nhưng mỏng dần
    "NO_SESSION":    C_TEXT_DIM,  # vùng chết — cố ý mờ
}

# ─────────────────────────────────────────────────────────── màu theo TRẠNG THÁI
# BA TRỤC KHÁC NHAU trong cùng một bảng tra, và đó là chủ ý của bản gốc: chúng
# không so sánh được với nhau ("NOISE" của giá không phải "CONFLICTING_NOISE" của
# tin), nhưng chúng không bao giờ xuất hiện cùng một chỗ nên một bảng tra là đủ.
# Nhãn lạ rơi về `C_TEXT` chứ không tô sai màu — xem `color_for_regime()`.
REGIME_COLOR = {
    # trục MỀM (LLM chấm từ TIN TỨC)
    "CRISIS_SHOCK":      C_RED,       # nguy hiểm nhất
    "TIER1_WHIPSAW":     C_ORANGE,
    "DATA_WHIPSAW":      C_AMBER,
    "CONFLICTING_NOISE": C_VIOLET,
    "LOW_LIQUIDITY":     C_BLUE,
    "ROUTINE_NORMAL":    C_GREEN,
    "STRUCTURAL_TREND":  C_GREEN_HI,  # điều kiện tốt nhất cho chiến lược trend
    "NEUTRAL":           C_TEXT_MUT,
    # trục CỨNG (đo từ GIÁ)
    "UPTREND":           C_GREEN_HI,
    "DOWNTREND":         C_RED,
    "SIDEWAYS":          C_BLUE,
    "NOISE":             C_VIOLET,
    "UNKNOWN":           C_TEXT_DIM,
    # nhãn V2 (`regime_envelope`)
    # NÉN màu hổ phách vì đó là trạng thái DUY NHẤT chặn vào lệnh: thấy màu này là
    # biết ngay tại sao không có lệnh nào, không phải đi đọc log.
    "TREND_UP":          C_GREEN_HI,
    "TREND_DOWN":        C_RED,
    "RANGE":             C_BLUE,
    "NEN":               C_AMBER,
}

# ─────────────────────────────────────────────────────────── mức nghiêm trọng
# Bốn mức của dòng sự kiện, ánh xạ sang ĐÚNG các sắc đã có ở trên. Không sắc mới.
LEVEL_COLOR = {
    "info":  C_TEXT_MUT,
    "good":  C_GREEN,
    "warn":  C_AMBER,
    "error": C_RED,
}

# Màu của từng NHÓM sự kiện, dùng cho nhãn `[TRADING]` / `[RISK]` đứng đầu dòng.
# Lấy từ `TAG` để nhóm nào cũng nằm trong 6 sắc của hệ thẻ, không phát sinh sắc thứ 7.
CATEGORY_COLOR = {
    "system":   TAG["blue"]["fg"],
    "market":   TAG["purple"]["fg"],
    "strategy": TAG["blue"]["fg"],
    "trading":  TAG["green"]["fg"],
    "ai":       TAG["purple"]["fg"],
    "risk":     TAG["amber"]["fg"],
    "daily":    TAG["orange"]["fg"],
}


def color_for_regime(label) -> str:
    """Màu của một nhãn trạng thái. Nhãn lạ -> chữ trắng, KHÔNG đoán màu.

    Đoán màu cho nhãn chưa biết là cách tệ nhất: người vận hành đọc màu nhanh hơn
    đọc chữ, nên một nhãn mới bị tô lục sẽ được hiểu là "an toàn" trước khi có ai
    kịp đọc tên nó.
    """
    return REGIME_COLOR.get(str(label or "").strip().upper(), C_TEXT)


def color_for_session(label) -> str:
    return SESSION_COLOR.get(str(label or "").strip().upper(), C_TEXT)


def color_for_pnl(value) -> str:
    """Lục nếu dương, đỏ nếu âm, mờ nếu bằng 0 hoặc không đọc được."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return C_TEXT_DIM
    if v > 0:
        return C_GREEN
    if v < 0:
        return C_RED
    return C_TEXT_DIM
