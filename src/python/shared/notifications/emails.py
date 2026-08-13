"""Bộ email SỰ KIỆN của hệ — CLONE nguyên văn từ `core/engine.py` của hệ XAUUSD.

VÌ SAO CLONE CHỨ KHÔNG VIẾT LẠI
================================
Nội dung, tiêu đề, bảng màu và bố cục của bộ thư này đã được người vận hành chỉnh
và xác thực qua nhiều vòng trên hệ XAUUSD — trên máy thật, với client thật. Viết
lại "cho gọn" là vứt bỏ toàn bộ vòng kiểm chứng đó và bắt đầu lại từ đầu, ở đúng
kênh mà lỗi chỉ lộ ra trên hộp thư người đọc chứ không lộ ra ở test.

Nên: giữ NGUYÊN chuỗi, nguyên emoji, nguyên mã màu, nguyên thứ tự hàng trong bảng.
Chỉ đổi những gì bắt buộc phải đổi khi chuyển sang danh mục Forex — và mỗi chỗ đổi
đều ghi rõ lý do ngay tại chỗ.

VÌ SAO NẰM Ở ĐÂY CHỨ KHÔNG NẰM TRONG `engine.py`
=================================================
Bên XAU năm hàm này nằm thẳng trong `engine.py`. Ở đây tách ra vì hệ Forex có thêm
nhóm thư VÒNG ĐỜI LỆNH phát từ `order_router`, và nhóm RỦI RO phát từ `ftmo_guard` —
ba nơi gọi mà nội dung nằm ở một nơi thì khung viền và cách trình bày không trôi
khỏi nhau được.

BỐN ĐIỀU KIỆN, giữ nguyên của bản cũ:
  1. Không bao giờ ném lỗi ra ngoài — hỏng SMTP KHÔNG được làm gãy luồng giao dịch.
  2. Chỉ gửi ở chuyển TRẠNG THÁI, không gửi theo lịch.
  3. Có bản `text` bên cạnh `html` — client trên điện thoại thường hiện bản text.
  4. Khung viền khai báo TỪNG CẠNH, xem `_alert_card_style()`.

Tầng gửi thật là `utils/mailer.py` (SSOT của SMTP, tôn trọng `APP_ENV=PROD`).
Chống gửi trùng nằm ở `utils/alerts.py`.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.python.utils.mailer import send as _send

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _alert_card_style(border_color: str) -> str:
    """Khung ngoài của 5 email trạng thái hệ thống (mất kết nối / khôi phục /
    khởi động / chờ / đóng cửa) — dùng chung để sửa một chỗ là đồng bộ cả năm.

    Viền khai báo TỪNG CẠNH thay vì viết tắt `border:`: nhiều client email tự
    viết lại CSS inline và khi gặp viết tắt đi kèm `border-radius` thì bung ra
    không đều, làm cạnh trái-phải hiện khác màu cạnh trên-dưới. Bốn dòng tường
    minh không còn chỗ cho việc bung ra ấy.

    `background` đặt tường minh vì thiếu nó thì nền chế độ tối của client ăn
    lem vào trong khung.
    """
    return ("font-family: Arial, sans-serif; background: #ffffff; color: #212529; "
            f"border-top: 1px solid {border_color}; border-right: 1px solid {border_color}; "
            f"border-bottom: 1px solid {border_color}; border-left: 1px solid {border_color}; "
            "border-radius: 8px; padding: 16px; max-width: 600px; margin: 0 auto;")


_CELL = ("padding: 8px; border: 1px solid #dee2e6; height: 40px; "
         "vertical-align: middle;")


def _table(pairs) -> str:
    """Bảng hai cột, tô nền xen kẽ bắt đầu từ hàng đầu — đúng như bản cũ."""
    rows = []
    for i, (label, value) in enumerate(pairs):
        bg = " style='background-color: #f8f9fa;'" if i % 2 == 0 else ""
        rows.append(f"<tr{bg}><td style='{_CELL}'><b>{label}</b></td>"
                    f"<td style='{_CELL}'>{value}</td></tr>")
    return (f"<table style='width: 100%; border-collapse: collapse; "
            f"margin: 12px 0;'>{''.join(rows)}</table>")


def _rocket() -> tuple:
    """`(thẻ_img, {cid: đường_dẫn})` — ảnh nhúng của bản cũ, nguyên kích thước.

    Nhúng qua `cid:` chứ không dẫn link ngoài: gần như mọi client email chặn ảnh
    tải từ internet cho tới khi người đọc bấm "hiện ảnh", nên ảnh dẫn link sẽ hiện
    thành ô vỡ ở đúng lần đọc đầu tiên.
    """
    rocket_path = os.path.join(str(PROJECT_ROOT), "assets", "rocket.png")
    if os.path.isfile(rocket_path):
        return ("<div style='text-align: center; margin: 16px 0;'>"
                "<img src='cid:rocket' alt='Rocket' "
                "style='max-width: 120px; height: auto;' /></div>",
                {"rocket": rocket_path})
    return "", {}


def _limits() -> dict:
    """Bốn ràng buộc SỐ, đọc từ SSOT — KHÔNG viết cứng trong chuỗi email.

    ⚠️ LỖI ĐÃ SỬA 15/08/2026. Bản trước ghi thẳng "trần 3,50x", "sàn nội bộ 9,00%",
    "giới hạn ngày FTMO 5,00%" vào chuỗi. Nếu ai đó nới `LEVERAGE_MAX` hay
    `DD_SELF_CAP` thì hệ chạy theo số mới còn email vẫn nói số cũ — và email là
    kênh DUY NHẤT người vận hành đọc khi không ngồi trước màn hình. Một cảnh báo
    nói sai chính ngưỡng đang áp dụng còn tệ hơn không có cảnh báo.

    Chủ sở hữu: `core/infra/ftmo.py` (luật gốc) và
    `execution/ftmo_leverage_policy.py` (biên tự đặt) — xem bảng SSOT trong
    CLAUDE.md. Đọc lỗi thì trả "?" chứ không đoán.
    """
    out = {"daily": "?", "max": "?", "floor": "?", "lev": "?"}
    try:
        from src.python.core.infra import ftmo

        out["daily"] = f"{ftmo.DAILY_LOSS_HARD:.2%}".replace(".", ",")
        out["max"] = f"{ftmo.MAX_LOSS_HARD:.2%}".replace(".", ",")
    except Exception:
        pass
    try:
        from src.python.execution import ftmo_leverage_policy as POL

        out["floor"] = f"{POL.DD_SELF_CAP:.2%}".replace(".", ",")
        out["lev"] = f"{POL.LEVERAGE_MAX:.2f}x".replace(".", ",")
    except Exception:
        pass
    return out


def _bot() -> str:
    try:
        from src.python.core.config import BOT_NAME
        return str(BOT_NAME)
    except Exception:
        return "The Cheopard Forex"


def _version() -> str:
    try:
        from src.python.core.runtime_meta import version
        return version()
    except Exception:
        return "?"


def _now_local() -> str:
    """Giờ máy, định dạng của bản cũ. Thư ghi kèm "(GMT +7)" như bản cũ."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _acc(account: Optional[Dict[str, Any]]) -> tuple:
    """`(login, server, balance, equity, currency)` với fallback về `.env`.

    Fallback là của bản cũ và cần thật: thư KHỞI ĐỘNG gửi ngay lúc mở máy, khi
    `account_info` có thể chưa kịp về từ MT5. Không có fallback thì đúng lá thư
    quan trọng nhất lại là lá thư trống thông tin tài khoản.
    """
    acc = account or {}
    env_login = os.environ.get("MT5_LOGIN", "N/A")
    env_server = os.environ.get("MT5_SERVER", "N/A")
    login_id = acc.get("login", env_login) or env_login
    server_name = acc.get("server", env_server) or env_server
    return (login_id, server_name,
            float(acc.get("balance", 0.0) or 0.0),
            float(acc.get("equity", 0.0) or 0.0),
            acc.get("currency", "USD"))


def _emit(subject: str, html: str, text: str, images: Optional[dict] = None) -> bool:
    try:
        return _send(subject, text, html, images=images or {})
    except Exception:
        # Điều kiện 1: hỏng email KHÔNG được làm gãy luồng gọi.
        return False


# ══════════════════════════════════════════════ 1. trạng thái hệ thống & kết nối
def startup(*, account: Optional[Dict[str, Any]] = None,
            strategies: int = 0, positions: int = 0,
            market_status: str = "") -> bool:
    """CLONE `send_startup_alert_email` — hệ vừa khởi động và kết nối được MT5."""
    login_id, server_name, balance, equity, currency = _acc(account)
    rocket_img_tag, images = _rocket()

    html = (
        f"<div style='{_alert_card_style('#28a745')}'>"
        f"<h2 style='color: #28a745; margin-top: 0;'>HỆ THỐNG KHỞI ĐỘNG THÀNH CÔNG</h2>"
        f"{rocket_img_tag}"
        f"<p>BOT <b>{_bot()} </b> đã được bật và kết nối máy chủ <b>{server_name}</b>.</p>"
        + _table([("Tài khoản MT5", login_id),
                  ("Máy chủ (Server)", server_name),
                  ("Số dư (Balance)", f"{balance:,.2f} {currency}"),
                  ("Vốn thực tế (Equity)", f"{equity:,.2f} {currency}"),
                  ("Build", _version()),
                  # HAI HÀNG THÊM cho hệ Forex: bên XAU một tài khoản chạy 12 chiến
                  # lược trên MỘT tài sản, nên số chân không phải thông tin. Ở đây
                  # 27 chân trải trên 27 công cụ, và "bao nhiêu chân đang chạy, đang
                  # giữ bao nhiêu vị thế" là câu đầu tiên người vận hành hỏi.
                  ("Chiến lược đang chạy", strategies),
                  ("Vị thế đang mở", positions),
                  ("Thị trường", market_status or "—")])
        + f"<p style='font-size: 13px;'><b>Thời điểm khởi động:</b> {_now_local()} (GMT +7)</p>"
        f"</div>"
    )
    subject = f"🟢 [STARTED] BOT {_bot()} khởi động  thành công"
    text = (
        f"Thông báo khởi động hệ thống {_bot()} :\n\n"
        f"✅ Trạng thái: Đã khởi động và kết nối MT5 Bridge thành công (100% Pure API).\n"
        f"💼 Tài khoản: {login_id}\n"
        f"🖥️ Máy chủ (Server): {server_name}\n"
        f"💰 Balance: {balance:,.2f} {currency} | Equity: {equity:,.2f} {currency}\n"
        f"📦 Build: {_version()}\n"
        f"📊 Chiến lược: {strategies} chân | Vị thế đang mở: {positions}\n"
        f"Thời điểm khởi động: {_now_local()} (GMT +7)\n"
    )
    return _emit(subject, html, text, images)


def disconnected(*, account: Optional[Dict[str, Any]] = None,
                 minutes: float = 5.0) -> bool:
    """CLONE `send_disconnection_alert_email` — MT5 mất kết nối quá ngưỡng."""
    login_id, server_name = _acc(account)[:2]
    now_str = _now_local()

    subject = f"⚠️ CẢNH BÁO: Mất kết nối MT5 Bridge quá {minutes:.0f} phút — {_bot()}"
    text = (
        f"Cảnh báo hệ thống:\n\n"
        f"BOT {_bot()} đã mất kết nối với MT5 terminal/EA quá {minutes:.0f} phút.\n"
        f"Vui lòng đăng nhập VPS/Server giám sát để kiểm tra logs và thực hiện reconnect thủ công trên Dashboard GUI.\n\n"
        f"💼 Tài khoản: {login_id}\n"
        f"🖥️ Máy chủ (Server): {server_name}\n"
        f"📦 Build: {_version()}\n"
        f"Thời điểm ghi nhận mất kết nối: {now_str} (GMT +7)\n"
    )
    html = (
        f"<div style='{_alert_card_style('#dc3545')}'>"
        f"<h2 style='color: #dc3545; margin-top: 0;'>⚠️ MẤT KẾT NỐI MT5 QUÁ {minutes:.0f} PHÚT</h2>"
        f"<p>BOT <b>{_bot()}</b> đã mất kết nối với <b>MT5 terminal/EA</b> quá {minutes:.0f} phút. "
        f"Trong thời gian này hệ thống KHÔNG vào lệnh mới và KHÔNG quản lý được vị thế đang mở.</p>"
        f"<div style='background-color: #fff5f5; border-left: 5px solid #dc3545; border-radius: 6px; padding: 12px; margin: 12px 0;'>"
        f"<b style='color: #b02a37;'>Cần làm ngay:</b> đăng nhập VPS/Server giám sát, kiểm tra logs và "
        f"bấm <b>Reconnect</b> thủ công trên Dashboard GUI nếu hệ thống chưa tự kết nối lại."
        f"</div>"
        + _table([("Tài khoản MT5", login_id),
                  ("Máy chủ (Server)", server_name),
                  ("Build", _version()),
                  ("Thời điểm mất kết nối", f"{now_str} (GMT +7)")])
        + f"<p style='font-size: 12px; color: #6c757d; border-top: 1px solid #dee2e6; padding-top: 8px; margin-bottom: 0;'>"
        f"Email tự động từ {_bot()}. Bạn sẽ nhận được email 🟢 KHÔI PHỤC KẾT NỐI khi kết nối trở lại.</p>"
        f"</div>"
    )
    return _emit(subject, html, text)


def reconnected(*, account: Optional[Dict[str, Any]] = None,
                downtime_min: float = 0.0, positions: int = 0) -> bool:
    """CLONE `send_reconnection_alert_email` — MT5 đã nối lại sau một lần rớt."""
    login_id, server_name = _acc(account)[:2]

    subject = f"🟢 [RECONNECTED] BOT {_bot()} đã khôi phục kết nối MT5 Bridge ({login_id})"
    text = (
        f"Thông báo khôi phục kết nối:\n\n"
        f"✅ BOT {_bot()}  đã kết nối lại thành công với máy chủ **MetaTrader 5** ({login_id} - {server_name}).\n"
        f"Hệ thống tự động tiếp tục giám sát vị thế và vào lệnh theo kế hoạch AI.\n\n"
        f"⏱️ Thời gian mất kết nối: {downtime_min:.1f} phút | Vị thế đang mở: {positions}\n"
        f"Thời điểm khôi phục: {_now_local()} (GMT +7)\n"
    )
    html = (
        f"<div style='{_alert_card_style('#17a2b8')}'>"
        f"<h2 style='color: #17a2b8; margin-top: 0;'>🟢 KHÔI PHỤC KẾT NỐI MT5 THÀNH CÔNG</h2>"
        f"<p>BOT <b>{_bot()}</b> đã kết nối lại thành công với máy chủ <b>MetaTrader 5</b> (<b>{login_id}</b> - {server_name}).</p>"
        f"<p>Hệ thống tự động tiếp tục vòng lặp giám sát vị thế thời gian thực và khớp lệnh Pure API.</p>"
        # HAI SỐ THÊM cho hệ Forex: danh mục 27 chân giữ lệnh qua đêm, nên "mất kết
        # nối bao lâu" và "đang giữ bao nhiêu vị thế" quyết định người vận hành có
        # phải vào đối chiếu tay hay không.
        + _table([("Thời gian mất kết nối", f"{downtime_min:.1f} phút"),
                  ("Vị thế đang mở", positions)])
        + f"<p style='font-size: 13px;'><b>Thời điểm khôi phục:</b> {_now_local()} (GMT +7)</p>"
        f"</div>"
    )
    return _emit(subject, html, text)


def standby(*, account: Optional[Dict[str, Any]] = None,
            positions: int = 0, market_status: str = "") -> bool:
    """CLONE `send_standby_email` — thị trường đóng cửa cuối tuần."""
    login_id, server_name, balance, equity, currency = _acc(account)
    rocket_img_tag, images = _rocket()

    html = (
        f"<div style='{_alert_card_style('#ffc107')}'>"
        f"<h2 style='color: #d39e00; margin-top: 0;'>CHẾ ĐỘ STAND BY (THỊ TRƯỜNG ĐÓNG CỬA)</h2>"
        f"{rocket_img_tag}"
        f"<p>BOT <b>{_bot()}</b> đã chuyển sang chế độ <b>STAND BY</b> do thị trường đóng cửa (cuối tuần).</p>"
        # ĐOẠN THÊM cho hệ Forex, và nó không phải trang trí: hệ XAU đóng hết lệnh
        # trước cuối tuần, còn danh mục này CỐ Ý giữ qua cuối tuần (time-stop ngắn
        # nhất 12 nến H4 = 2 ngày). Người vận hành mở thư sáng thứ Bảy thấy vị thế
        # còn nguyên mà không có dòng này sẽ tưởng hệ quên đóng.
        f"<div style='background-color: #fffbea; border-left: 5px solid #ffc107; border-radius: 6px; padding: 12px; margin: 12px 0;'>"
        f"<b>Vị thế đang mở được GIỮ NGUYÊN.</b> Danh mục này cố ý giữ lệnh qua cuối tuần — "
        f"đóng rồi mở lại là trả thêm một lượt spread cho mỗi vị thế mỗi tuần. "
        f"Cầu chì trên server broker vẫn nguyên trong suốt thời gian đóng cửa."
        f"</div>"
        + _table([("Tài khoản MT5", login_id),
                  ("Máy chủ (Server)", server_name),
                  ("Số dư (Balance)", f"{balance:,.2f} {currency}"),
                  ("Vốn thực tế (Equity)", f"{equity:,.2f} {currency}"),
                  ("Build", _version()),
                  ("Vị thế giữ qua cuối tuần", positions),
                  ("Mở lại", market_status or "—")])
        + f"<p style='font-size: 13px;'><b>Thời điểm chuyển STAND BY:</b> {_now_local()} (GMT +7)</p>"
        f"</div>"
    )
    subject = f"🟡 [STAND BY] BOT {_bot()} đã chuyển sang chế độ STAND BY"
    text = (
        f"Thông báo chuyển chế độ STAND BY {_bot()}:\n\n"
        f"💤 Trạng thái: Thị trường đóng cửa (cuối tuần) — Chuyển sang STAND BY.\n"
        f"💼 Tài khoản: {login_id}\n"
        f"🖥️ Máy chủ: {server_name}\n"
        f"💰 Balance: {balance:,.2f} {currency} | Equity: {equity:,.2f} {currency}\n"
        f"📦 Build: {_version()}\n"
        f"📌 Vị thế giữ qua cuối tuần: {positions} (GIỮ NGUYÊN theo thiết kế)\n"
        f"⏰ Mở lại: {market_status or '—'}\n"
        f"Thời điểm chuyển STAND BY: {_now_local()} (GMT +7)\n"
    )
    return _emit(subject, html, text, images)


def resume(*, account: Optional[Dict[str, Any]] = None,
           positions: int = 0, market_status: str = "") -> bool:
    """CLONE `send_resume_email` — thị trường mở cửa trở lại."""
    login_id, server_name, balance, equity, currency = _acc(account)
    rocket_img_tag, images = _rocket()

    html = (
        f"<div style='{_alert_card_style('#28a745')}'>"
        f"<h2 style='color: #28a745; margin-top: 0;'>KHÔI PHỤC CHẾ ĐỘ GIAO DỊCH ACTIVE</h2>"
        f"{rocket_img_tag}"
        f"<p>BOT <b>{_bot()}</b> đã kết thúc STAND BY và khôi phục chế độ <b>GIAO DỊCH</b> thời gian thực.</p>"
        + _table([("Tài khoản MT5", login_id),
                  ("Máy chủ (Server)", server_name),
                  ("Số dư (Balance)", f"{balance:,.2f} {currency}"),
                  ("Vốn thực tế (Equity)", f"{equity:,.2f} {currency}"),
                  ("Build", _version()),
                  ("Vị thế đang mở", positions),
                  ("Trạng thái", market_status or "—")])
        + f"<p style='font-size: 13px;'><b>Thời điểm kích hoạt lại:</b> {_now_local()} (GMT +7)</p>"
        f"</div>"
    )
    subject = f"🟢 [ACTIVE] BOT {_bot()} đã khôi phục chế độ GIAO DỊCH"
    text = (
        f"Thông báo khôi phục chế độ giao dịch {_bot()}:\n\n"
        f"🚀 Trạng thái: Thị trường đã mở cửa — Khôi phục chế độ GIAO DỊCH active.\n"
        f"💼 Tài khoản: {login_id}\n"
        f"🖥️ Máy chủ: {server_name}\n"
        f"💰 Balance: {balance:,.2f} {currency} | Equity: {equity:,.2f} {currency}\n"
        f"📦 Build: {_version()}\n"
        f"📌 Vị thế đang mở: {positions}\n"
        f"Thời điểm kích hoạt lại: {_now_local()} (GMT +7)\n"
    )
    return _emit(subject, html, text, images)


def market_phase(*, closed: bool, account: Optional[Dict[str, Any]] = None,
                 positions: int = 0, market_status: str = "") -> bool:
    """Bộ chuyển: pha thị trường đổi → `standby()` hoặc `resume()`.

    Một lối vào cho bên gọi, vì `engine._check_market_hours` chỉ biết cờ `closed`.
    """
    fn = standby if closed else resume
    return fn(account=account, positions=positions, market_status=market_status)


def account_mismatch(*, expected: str, actual: str, server: str = "") -> bool:
    """CLONE `send_alert("account_mismatch", …)` của `mt5_bridge`.

    Sự cố nguy hiểm nhất trong nhóm hạ tầng: hệ sẽ đặt lệnh của danh mục FTMO lên
    một tài khoản khác, với cỡ lệnh tính theo equity của tài khoản kia.
    """
    subject = f"⛔ [{_bot()}] XUNG ĐỘT TÀI KHOẢN MT5"
    text = (
        f"Cảnh báo hệ thống:\n\n"
        f"⛔ Tài khoản đang đăng nhập trên MT5 KHÔNG khớp cấu hình. Mọi lệnh đã bị chặn.\n\n"
        f"💼 Cấu hình mong đợi: {expected}\n"
        f"💼 Đang đăng nhập   : {actual}\n"
        f"🖥️ Máy chủ          : {server or '—'}\n"
        f"📦 Build            : {_version()}\n"
        f"Thời điểm phát hiện: {_now_local()} (GMT +7)\n"
    )
    html = (
        f"<div style='{_alert_card_style('#dc3545')}'>"
        f"<h2 style='color: #dc3545; margin-top: 0;'>⛔ XUNG ĐỘT TÀI KHOẢN MT5</h2>"
        f"<p>Tài khoản đang đăng nhập trên MT5 <b>KHÔNG khớp</b> với cấu hình của hệ. "
        f"Công tắc giao dịch đã được TẮT tự động.</p>"
        f"<div style='background-color: #fff5f5; border-left: 5px solid #dc3545; border-radius: 6px; padding: 12px; margin: 12px 0;'>"
        f"<b style='color: #b02a37;'>Cần làm ngay:</b> đăng nhập đúng tài khoản trên MT5 terminal, "
        f"hoặc sửa <code>MT5_LOGIN</code> trong <code>.env</code> nếu đây là thay đổi có chủ ý."
        f"</div>"
        + _table([("Cấu hình mong đợi", expected),
                  ("Đang đăng nhập", actual),
                  ("Máy chủ (Server)", server or "—"),
                  ("Build", _version()),
                  ("Thời điểm phát hiện", f"{_now_local()} (GMT +7)")])
        + "</div>"
    )
    return _emit(subject, html, text)


# ═══════════════════════════════════════════════════ 2. vòng đời lệnh
#
# CLONE ĐẦY ĐỦ layout CARD của `shared/notifications/email_reporter.py` hệ XAUUSD
# (`render_open_html` / `render_close_html`, thiết kế lại 21/07 và bổ sung 28-29/07).
#
# GIỮ NGUYÊN TOÀN BỘ CẤU TRÚC, không cắt khối nào:
#   header gradient navy + hai mốc giờ (GMT+7 và giờ Broker/MT5) + huy hiệu chiều
#   → tên chiến lược
#   → bảng định danh (Account ID · Trade ID · Symbol · Magic · Build version)
#   → ba thẻ giá Entry · Close · PnL
#   → ① KẾT QUẢ  ② VÒNG ĐỜI LỆNH  ③ MỨC GIÁ & BẢO VỆ  ④ PHÂN RÃ PnL
#   → 🛡️ Trạng thái hệ thống
#   → 📊 Ghi chú về cách tính số liệu (card `_notice_card`)
BORDER_ENTRY = "#142a57"      # vào lệnh — navy, khớp gradient header
BORDER_WIN = "#1e874b"        # đóng lệnh THẮNG
BORDER_LOSS = "#c0392b"       # đóng lệnh LỖ
BORDER_REJECT = "#b45309"     # lệnh bị từ chối — hổ phách sậm

_NOTICE_PALETTE = {
    #                 nền        viền mảnh   thanh trái  tiêu đề    kẻ ngang
    "entry":    ("#eff6ff", "#93c5fd", "#2563eb", "#1d4ed8", "#bfdbfe"),
    "win":      ("#f0fdf4", "#86efac", "#16a34a", "#15803d", "#bbf7d0"),
    "loss":     ("#fef2f2", "#fca5a5", "#dc2626", "#b91c1c", "#fecaca"),
    "reject":   ("#fffbeb", "#fcd34d", "#d97706", "#b45309", "#fde68a"),
}

# Nhãn tiếng Việt + màu cho từng lý do đóng. Khoá là tập ĐÓNG của
# `execution/exit_manager.REASONS` — chuỗi lạ rơi về xám, không bịa nhãn.
_CLOSE_REASON_VI = {
    "SIGNAL":          ("Tín hiệu ngược chiều", "#234c91"),
    "TIME_STOP":       ("Hết hạn nắm giữ (time-stop)", "#b45309"),
    "DISASTER_STOP":   ("Cầu chì nổ (disaster stop)", "#c0392b"),
    "MANUAL":          ("Đóng tay", "#64748b"),
    "RECONCILE":       ("Phát hiện khi đối soát", "#94a3b8"),
    "REVERSE":         ("Đảo chiều", "#7c3aed"),
    "FLATTEN":         ("Đóng sạch theo lệnh rủi ro", "#c0392b"),
    "UNKNOWN":         ("Không xác định", "#94a3b8"),
}


def _close_reason_badge(code: str) -> str:
    label, color = _CLOSE_REASON_VI.get(str(code).upper(), (str(code), "#64748b"))
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
            f'background:{color};color:#ffffff;font-weight:700;font-size:11px">'
            f'{label}</span>')


def _fmt_duration(hours: float) -> str:
    """Thời gian nắm giữ dạng người đọc được ("2 ngày 3 giờ", "45 phút")."""
    if hours < 0:
        return "—"
    if hours < 1:
        return f"{hours * 60:.0f} phút"
    if hours < 24:
        h = int(hours)
        m = int(round((hours - h) * 60))
        return f"{h} giờ" + (f" {m} phút" if m else "")
    d = int(hours // 24)
    h = int(round(hours - d * 24))
    return f"{d} ngày" + (f" {h} giờ" if h else "")


def _card_style(border_color: str) -> str:
    """Style container ngoài cùng của email card — DÙNG CHUNG cho cả 5 template
    để đường bao/bo góc/đổ bóng không bị lệch nhau khi sửa một chỗ."""
    return ("max-width:650px;margin:20px auto;background:#ffffff;border-radius:18px;"
            f"overflow:hidden;border:1px solid {border_color};"
            "box-shadow:0 8px 30px rgba(20,35,60,0.10)")


def _kv_row(label, value, color="#0f172a", bold=True) -> str:
    """Một hàng nhãn — giá trị. Cỡ chữ 15px/16px theo bản cũ (đã chỉnh 28/07)."""
    weight = "600" if bold else "500"
    return (f'<tr style="border-bottom:1px solid #f1f5f9">'
            f'<td style="padding:8px 0;color:#64748b;font-size:15px">{label}</td>'
            f'<td style="padding:8px 0;text-align:right;font-weight:{weight};'
            f'color:{color};font-size:16px">{value}</td></tr>')


def _block(number_title: str, rows_html: str) -> str:
    return (f'<div style="margin:0 28px 18px 28px">'
            f'<div style="font-size:12px;font-weight:700;color:#94a3b8;text-transform:uppercase;'
            f'letter-spacing:0.6px;margin-bottom:6px">{number_title}</div>'
            f'<table style="width:100%;border-collapse:collapse">{rows_html}</table></div>')


def _notice_card(kind: str, title: str, body_html: str, foot_html: str = "") -> str:
    """Card ghi chú cuối email theo mẫu Macro Veto của bản cũ."""
    bg, border, accent, title_c, divider = _NOTICE_PALETTE.get(
        kind, _NOTICE_PALETTE["entry"])
    foot = ""
    if foot_html:
        foot = (f'<p style="margin:12px 0 0 0;font-size:12px;color:#94a3b8;'
                f'border-top:1px solid {divider};padding-top:8px">{foot_html}</p>')
    return (f'<div style="font-family:Segoe UI,Arial,sans-serif;background-color:{bg};'
            f'border:1px solid {border};border-left:5px solid {accent};'
            f'border-radius:6px;padding:16px;margin:18px 28px 20px 28px">'
            f'<h4 style="margin:0 0 12px 0;color:{title_c};font-size:16px;'
            f'border-bottom:1px solid {divider};padding-bottom:8px">{title}</h4>'
            f'<div style="font-size:14px;line-height:1.55;color:#0f172a">{body_html}</div>'
            f'{foot}</div>')


def _footer_line() -> str:
    """Dòng chân email đứng một mình, không nằm trong card ghi chú."""
    return (f'<p style="font-family:Segoe UI,Arial,sans-serif;font-size:12px;'
            f'color:#94a3b8;margin:0 28px 20px 28px;border-top:1px solid #e2e8f0;'
            f'padding-top:10px">Email tự động từ {_bot()}.</p>')


def _system_status_block(rows_html: str) -> str:
    """Khối 🛡️ Trạng thái hệ thống — nền xanh nhạt, viền bo, đúng bản cũ."""
    return ('<div style="margin:0 28px 18px 28px">'
            '<table style="width:100%;border-collapse:collapse;background:#f5f8fc;'
            'border:1px solid #e3eaf4;border-radius:12px">'
            '<tr><td style="padding:14px 16px">'
            '<div style="font-size:13px;font-weight:700;color:#234c91;margin-bottom:8px">'
            '🛡️ Trạng thái hệ thống</div>'
            '<table style="width:100%;border-collapse:collapse">'
            + rows_html + '</table></td></tr></table></div>')


def _guard_status() -> tuple:
    """(nhãn, màu) của lớp phòng thủ chủ động — thay `_black_swan_guard_status`.

    Hệ XAUUSD hiển thị Black Swan Guard. Hệ này không có module đó; thứ tương
    đương là `ftmo_guard` — lớp DUY NHẤT có quyền đóng sạch vị thế. Đọc trạng
    thái thật của nó chứ không in một chữ "OK" cố định: một ô luôn cùng giá trị
    không mang thông tin nào, và tệ hơn, nó làm người đọc tin rằng có thứ đang
    canh trong khi không ai kiểm.
    """
    try:
        from src.python.core.infra import ftmo_guard as FG

        if FG.already_flattened_today():
            return "ĐÃ ĐÓNG SẠCH hôm nay (chạm ngưỡng)", "#c0392b"
        return "OK", "#1e874b"
    except Exception as exc:
        return f"KHÔNG ĐỌC ĐƯỢC ({type(exc).__name__})", "#b45309"


def _market_state_rows() -> str:
    """Hai hàng trạng thái thị trường: chế độ CỨNG và phiên giao dịch.

    Nguồn là `core/intelligence/fx_market_state` (biến động rổ 20 cross theo phân
    vị trượt) và `shared/regime_taxonomy` — KHÔNG phải bộ máy AI vĩ mô của hệ
    XAUUSD, thứ hệ này cố ý không có.
    """
    rows = ""
    try:
        from src.python.core.intelligence import fx_market_state as FMS

        st = FMS.get_state()
        if st.error or st.hard_regime == "UNKNOWN":
            rows += _kv_row("Trạng thái thị trường (Hard Regime)",
                            "chưa đo được ở chu kỳ gần đây", "#94a3b8", bold=False)
        else:
            pct = ("" if st.hard_percentile is None
                   else f" (phân vị {st.hard_percentile:.0%} của 6 năm)")
            color = {"CRISIS": "#c0392b", "ELEVATED": "#b45309",
                     "CALM": "#1e874b"}.get(st.hard_regime, "#0f172a")
            rows += _kv_row("Trạng thái thị trường (Hard Regime)",
                            f"{st.hard_regime}{pct}", color)
    except Exception as exc:
        rows += _kv_row("Trạng thái thị trường (Hard Regime)",
                        f"lỗi đọc: {type(exc).__name__}", "#b45309", bold=False)
    try:
        from datetime import timezone as _tz

        from src.python.shared.regime_taxonomy import (
            classify_time_regime, time_regime_activity)

        now = datetime.now(_tz.utc)
        ses = classify_time_regime(now)
        act = time_regime_activity(now)
        rows += _kv_row("Thanh khoản", f"{ses} — hoạt động {act:.0%}")
    except Exception as exc:
        rows += _kv_row("Thanh khoản", f"lỗi đọc: {type(exc).__name__}",
                        "#b45309", bold=False)
    return rows


def _ids_table(*, trade_id: str, symbol: str, magic=None) -> str:
    """Bảng định danh dưới tên chiến lược — Account ID · Trade ID · Symbol · Build."""
    rows = _kv_row("Tài khoản (Account ID)", os.environ.get("MT5_LOGIN", "Unknown"))
    rows += _kv_row("Trade ID", trade_id or "—")
    if symbol:
        rows += _kv_row("Symbol", symbol)
    if magic is not None:
        rows += _kv_row("Magic", str(magic))
    rows += _kv_row("Build version", _version())
    return ('<div style="margin:0 28px 18px 28px">'
            f'<table style="width:100%;border-collapse:collapse">{rows}</table></div>')


def _price_card(label, value, bg, fg_label, fg_value) -> str:
    return (f'<td width="32%" style="padding:14px 8px;text-align:center;'
            f'background:{bg};border-radius:12px">'
            f'<div style="font-size:11px;color:{fg_label};text-transform:uppercase;'
            f'letter-spacing:0.6px">{label}</div>'
            f'<div style="margin-top:6px;font-size:18px;font-weight:700;'
            f'color:{fg_value}">{value}</div></td>')


def _header(border: str, eyebrow: str, title: str, badge: str, badge_bg: str,
            stamps: str, subtitle_label: str, subtitle: str, body: str,
            tail: str) -> str:
    """Khung card đầy đủ. `stamps` là các mốc giờ dưới tiêu đề (có thể rỗng)."""
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;font-family:Segoe UI,Arial,sans-serif;color:#172033">
  <div style="{_card_style(border)}">
    <!-- Header -->
    <div style="background:linear-gradient(135deg,#0b1736,#142a57);padding:24px 28px;color:#ffffff">
      <table style="width:100%;border-collapse:collapse">
        <tr>
          <td>
            <div style="font-size:12px;text-transform:uppercase;letter-spacing:1.2px;color:#9fb4dd">{eyebrow}</div>
            <div style="margin-top:6px;font-size:24px;font-weight:700">{title}</div>
            {stamps}
          </td>
          <td align="right" valign="top">
            <span style="display:inline-block;padding:8px 14px;border-radius:999px;background:{badge_bg};color:#ffffff;font-size:14px;font-weight:700">{badge}</span>
          </td>
        </tr>
      </table>
    </div>

    <!-- Strategy -->
    <div style="padding:24px 28px 18px 28px">
      <div style="font-size:12px;color:#748096;text-transform:uppercase;letter-spacing:0.8px">{subtitle_label}</div>
      <div style="margin-top:4px;font-size:22px;font-weight:800;color:#102044">{subtitle}</div>
    </div>

{body}
{tail}
  </div>
</body></html>
"""


def _stamps(gmt7: str, broker: str) -> str:
    """Hai mốc giờ dưới tiêu đề: giờ máy (GMT+7) và giờ máy chủ broker.

    Bản cũ hiện CẢ HAI có chủ ý, và lý do vẫn đúng ở đây: giờ broker là thứ đối
    chiếu được với lịch sử lệnh trên MT5, còn giờ máy là thứ khớp với sổ log. Chỉ
    hiện một cái là mỗi lần điều tra phải tự quy đổi, và quy đổi tay là chỗ sai.
    """
    out = (f'<div style="margin-top:5px;font-size:13px;color:#c8d5ed">'
           f'{gmt7} (GMT +7)</div>')
    if broker and broker != "—":
        out += (f'<div style="margin-top:2px;font-size:13px;color:#c8d5ed">'
                f'{broker} (giờ Broker/MT5)</div>')
    return out


def entry(*, strategy: str, symbol: str, direction: str, lots: float,
          price: float, stop_price: Optional[float] = None,
          weight: Optional[float] = None, leverage: Optional[float] = None,
          equity: float = 0.0, spread: float = 0.0, timeframe: str = "",
          trade_id: str = "", magic=None, atr: Optional[float] = None,
          broker_time: str = "", notional_usd: float = 0.0,
          reason: str = "") -> bool:
    """CLONE `send_strategy_entry_email` + `render_open_html` — đã MỞ vị thế thật.

    BỐN KHỐI giữ nguyên đánh số, thứ tự và mọi hàng của bản cũ. Ba chỗ đổi, mỗi
    chỗ là hệ quả của một khác biệt ĐÃ ĐO:

      · "Chốt lời (TP)" ghi "Không đặt TP cố định" — giữ HÀNG, đổi giá trị. Danh
        mục không có TP theo giá; bỏ hẳn hàng thì người quen đọc email bản cũ sẽ
        tưởng thiếu dữ liệu chứ không hiểu là hệ cố ý không có.
      · "Tỷ lệ R:R" BỎ — R:R cần một TP, và bịa ra nó là bịa một con số.
      · "Rủi ro ($)/(%)" thay bằng "Tỷ trọng mục tiêu" · "Đòn bẩy danh mục" ·
        "Notional". Cỡ lệnh ở đây là vol-targeting
        (`lot = equity × leverage × w / notional`), không suy từ khoảng cách tới
        SL, nên "risk USD" của bản cũ không có định nghĩa tương ứng.
    """
    is_buy = str(direction).upper().startswith("B")
    dir_txt = "BUY" if is_buy else "SELL"
    dir_bg = "#1e874b" if is_buy else "#c0392b"
    now = _now_local()
    sl_txt = f"{stop_price:.5f}" if stop_price else "⚠️ KHÔNG CÓ"

    ids = _ids_table(trade_id=trade_id, symbol=symbol, magic=magic)

    # ① Thông tin lệnh
    summary = _block("① THÔNG TIN LỆNH",
                     _kv_row("Chiến lược", strategy)
                     + _kv_row("Hướng lệnh", dir_txt, dir_bg)
                     + _kv_row("Khung tín hiệu", timeframe or "—")
                     + _kv_row("Phiên bản build", _version()))

    # ② Khớp lệnh
    exec_rows = (_kv_row("Thời gian mở lệnh", f"{now} (GMT+7)")
                 + _kv_row("Thời gian mở lệnh",
                           f"{broker_time or '—'} (giờ Broker/MT5)", bold=False)
                 + _kv_row("Giá vào lệnh", f"{price:.5f}")
                 + _kv_row("Khối lượng (Lot)", f"{lots:.2f} lot"))
    if notional_usd:
        exec_rows += _kv_row("Notional", f"{notional_usd:,.0f} $")
    if weight is not None:
        exec_rows += _kv_row("Tỷ trọng mục tiêu", f"{weight:+.2%}")
    if leverage is not None:
        exec_rows += _kv_row("Đòn bẩy danh mục",
                             f"{leverage:.2f}x <span style='color:#94a3b8;"
                             f"font-weight:500'>(trần {_limits()['lev']})</span>")
    if equity:
        exec_rows += _kv_row("Equity", f"{equity:,.2f} $")
    execution = _block("② KHỚP LỆNH", exec_rows)

    # ③ Mức giá & bảo vệ
    price_rows = _kv_row("Giá vào lệnh", f"{price:.5f}")
    if stop_price and price:
        dist = abs(price - float(stop_price))
        price_rows += _kv_row(
            "Cầu chì (SL server)",
            f"{stop_price:.5f} <span style='color:#94a3b8;font-weight:500'>"
            f"(cách {dist:.5f})</span>", color="#c0392b")
    else:
        price_rows += _kv_row("Cầu chì (SL server)", sl_txt, color="#c0392b")
    price_rows += _kv_row("Chốt lời (TP)", "Không đặt TP cố định")
    if atr is not None:
        price_rows += _kv_row("ATR lúc vào lệnh", f"{float(atr):.5f}")
    price_rows += _kv_row("Spread", f"{spread:.5f}" if spread else "—")
    prices_block = _block("③ MỨC GIÁ & BẢO VỆ", price_rows)

    # ④ Thiết lập
    note = (reason or "Tín hiệu vào lệnh theo thẻ luật của chân.")
    setup = _block("④ THIẾT LẬP",
                   _kv_row("Lối thoát", "time-stop hoặc tín hiệu ngược chiều")
                   + f'<tr><td colspan="2" style="padding:10px 0;font-size:13px;'
                     f'line-height:1.45;color:#334155;font-style:italic">'
                     f'"{note}"</td></tr>')

    guard_label, guard_color = _guard_status()
    status = _system_status_block(
        _kv_row("Lớp phòng thủ (FTMO Guard)", guard_label, guard_color)
        + _market_state_rows())

    notice = _notice_card(
        "entry", "📊 Ghi chú về cách tính số liệu",
        "Cỡ lệnh theo <b>vol-targeting</b>: "
        "<code>lot = equity × đòn bẩy × tỷ trọng ÷ notional</code>, KHÔNG suy từ "
        "khoảng cách tới cắt lỗ. Danh mục <b>không có SL theo giá</b> — đo lại "
        "14/08 trên 22 chân: mọi mức SL đều tệ hơn, 1×ATR mất 23% Sharpe và làm "
        "MaxDD TỆ ĐI. Cầu chì ≥8×ATR chỉ là lớp phòng khi tiến trình chết.",
        f"Email tự động từ {_bot()}.")

    html = _header(BORDER_ENTRY, "Real-time Trade Alert",
                   f"🔔 Vào lệnh mới — {dir_txt}", dir_txt, dir_bg,
                   _stamps(now, broker_time), "Chiến lược", strategy,
                   ids + summary + execution + prices_block + setup + status,
                   notice)

    text = (
        f"🔔 REAL-TIME TRADE ALERT — {dir_txt}\n"
        f"{now} (GMT +7)"
        + (f" | {broker_time} (giờ Broker/MT5)" if broker_time else "") + "\n\n"
        f"ĐỊNH DANH\n"
        f"  - Chiến lược: {strategy}\n"
        f"  - Tài khoản (Account ID): {os.environ.get('MT5_LOGIN', 'Unknown')}\n"
        f"  - Trade ID: {trade_id or '—'}\n"
        f"  - Symbol: {symbol}\n"
        + (f"  - Magic: {magic}\n" if magic is not None else "")
        + f"  - Build version: {_version()}\n\n"
        f"① THÔNG TIN LỆNH\n"
        f"  - Hướng lệnh: {dir_txt}\n"
        f"  - Khung tín hiệu: {timeframe or '—'}\n\n"
        f"② KHỚP LỆNH\n"
        f"  - Giá vào lệnh: {price:.5f}\n"
        f"  - Khối lượng: {lots:.2f} lot\n"
        + (f"  - Notional: {notional_usd:,.0f} $\n" if notional_usd else "")
        + (f"  - Tỷ trọng mục tiêu: {weight:+.2%}\n" if weight is not None else "")
        + (f"  - Đòn bẩy danh mục: {leverage:.2f}x (trần {_limits()['lev']})\n"
           if leverage is not None else "")
        + (f"  - Equity: {equity:,.2f} $\n" if equity else "")
        + f"\n③ MỨC GIÁ & BẢO VỆ\n"
        f"  - Cầu chì (SL server): {sl_txt}\n"
        f"  - Chốt lời (TP): Không đặt TP cố định\n"
        + (f"  - ATR lúc vào lệnh: {float(atr):.5f}\n" if atr is not None else "")
        + f"  - Spread: {spread:.5f}\n\n"
        f"④ THIẾT LẬP\n"
        f"  - Lối thoát: time-stop hoặc tín hiệu ngược chiều\n"
        f"  - Lý do: {note}\n\n"
        f"📊 Cỡ lệnh theo vol-targeting, KHÔNG suy từ khoảng cách tới cắt lỗ.\n"
    )
    subject = f"🔔 [{_bot()}] {dir_txt} {strategy} — {symbol} (Lot {lots:.2f})"
    return _emit(subject, html, text)


def close(*, strategy: str, symbol: str, direction: str, lots: float,
          entry_price: float, exit_price: float, pnl_usd: Optional[float] = None,
          bars_held: Optional[int] = None, reason: str = "",
          mfe: Optional[float] = None, mae: Optional[float] = None,
          equity: float = 0.0, trade_id: str = "", magic=None,
          gross_bps: Optional[float] = None, stop_price: Optional[float] = None,
          entry_time: str = "", broker_open: str = "", broker_close: str = "",
          holding_hours: Optional[float] = None, timeframe: str = "",
          swap_usd: Optional[float] = None,
          commission_usd: Optional[float] = None,
          entry_reason: str = "", exit_detail: str = "") -> bool:
    """CLONE `send_strategy_close_email` + `render_close_html` — đã ĐÓNG vị thế.

    GIỮ ĐỦ MỌI KHỐI của bản cũ, kể cả những khối chỉ hiện khi có dữ liệu:
    định danh · ba thẻ giá · ① KẾT QUẢ · ② VÒNG ĐỜI LỆNH (bốn mốc giờ, thời gian
    nắm giữ, huy hiệu lý do đóng, lý do vào lệnh ban đầu) · ③ MỨC GIÁ & BẢO VỆ ·
    ④ PHÂN RÃ PnL · 🛡️ Trạng thái hệ thống · 📊 Ghi chú.

    ĐỔI so với bản cũ, mỗi chỗ có lý do:
      · "PnL (R)" → "Lãi/lỗ (bps)". R là bội số của rủi ro ban đầu, mà rủi ro ban
        đầu = khoảng SL × lot. Danh mục không có SL chiến lược nên mẫu số đó không
        tồn tại; `gross_bps` là thứ chiến lược thật sự sinh ra và là thứ so được
        với backtest.
      · MFE/MAE tính bằng **bps** thay vì R, cùng lý do.
      · "Rủi ro gốc (mẫu số của R)" BỎ — không có mẫu số thì không có hàng.
    """
    pnl = float(pnl_usd or 0.0)
    is_win = pnl > 0 if pnl_usd is not None else (float(gross_bps or 0.0) > 0)
    border = BORDER_WIN if is_win else BORDER_LOSS
    dir_txt = "BUY" if str(direction).upper().startswith("B") else "SELL"
    dir_bg = "#1e874b" if dir_txt == "BUY" else "#c0392b"
    res_text = "✅ WIN" if is_win else "❌ LOSS"
    header_title = "✅ Đóng lệnh — WIN" if is_win else "❌ Đóng lệnh — LOSS"
    pnl_bg = "#edf9f2" if is_win else "#fff2f2"
    pnl_fg_label = "#3f8760" if is_win else "#a84a4a"
    pnl_fg_value = "#238451" if is_win else "#c43f3f"
    close_fg = ("#238451" if exit_price > entry_price
                else "#c43f3f" if exit_price < entry_price else "#15264e")
    now = _now_local()

    ids = _ids_table(trade_id=trade_id, symbol=symbol, magic=magic)

    pnl_cell = (f"{pnl:+.2f}" if pnl_usd is not None
                else f"{float(gross_bps or 0.0):+.1f} bps")
    prices = (
        '<div style="padding:0 28px 18px 28px"><table style="width:100%;'
        'border-collapse:separate;border-spacing:0"><tr>'
        + _price_card("Entry", f"{entry_price:.5f}", "#f5f8fc", "#748096", "#15264e")
        + '<td width="2%"></td>'
        + _price_card("Close", f"{exit_price:.5f}", "#f5f8fc", "#748096", close_fg)
        + '<td width="2%"></td>'
        + _price_card("PnL", pnl_cell, pnl_bg, pnl_fg_label, pnl_fg_value)
        + "</tr></table></div>"
    )

    # ① KẾT QUẢ
    result_rows = _kv_row("Kết quả", res_text, pnl_fg_value)
    if gross_bps is not None:
        result_rows += _kv_row("Lãi/lỗ (bps)", f"{float(gross_bps):+.1f} bps",
                               pnl_fg_value)
    if mfe is not None:
        give_back = (float(mfe) - float(gross_bps)) if gross_bps is not None else None
        mfe_txt = f"{float(mfe):+.1f} bps"
        if give_back is not None and give_back > 0.1:
            mfe_txt += (f' <span style="color:#94a3b8;font-weight:500">'
                        f'(trả lại {give_back:.1f} bps)</span>')
        result_rows += _kv_row("Đỉnh lãi đã chạm (MFE)", mfe_txt)
    if mae is not None:
        result_rows += _kv_row("Lỗ sâu nhất đã chịu (MAE)", f"{float(mae):+.1f} bps",
                               color="#c0392b")
    result_rows += _kv_row("Khối lượng (Lot)", f"{lots:.2f} lot")
    if pnl_usd is not None:
        result_rows += _kv_row("Lãi/lỗ ($)", f"{pnl:+.2f} $", pnl_fg_value)
    if equity:
        result_rows += _kv_row("Equity sau đóng", f"{equity:,.2f} $")
    result_block = _block("① KẾT QUẢ", result_rows)

    # ② VÒNG ĐỜI LỆNH
    life_rows = (
        _kv_row("Thời gian mở lệnh", f"{entry_time or '—'} (GMT+7)")
        + _kv_row("Thời gian mở lệnh",
                  f"{broker_open or '—'} (giờ Broker/MT5)", bold=False)
        + _kv_row("Thời gian đóng lệnh", f"{now} (GMT+7)")
        + _kv_row("Thời gian đóng lệnh",
                  f"{broker_close or '—'} (giờ Broker/MT5)", bold=False)
    )
    if holding_hours is not None:
        life_rows += _kv_row("Thời gian nắm giữ", _fmt_duration(float(holding_hours)))
    if bars_held is not None:
        life_rows += _kv_row("Số nến đã giữ",
                             f"{bars_held} nến" + (f" ({timeframe})" if timeframe else ""))
    life_rows += _kv_row("Lý do đóng", _close_reason_badge(reason or "UNKNOWN"))
    if exit_detail:
        life_rows += (f'<tr><td colspan="2" style="padding:6px 0;font-size:13px;'
                      f'line-height:1.5;color:#334155">{exit_detail}</td></tr>')
    if entry_reason:
        life_rows += (f'<tr><td colspan="2" style="padding:6px 0;font-size:12px;'
                      f'color:#64748b;line-height:1.45"><b>Lý do vào lệnh ban đầu:</b> '
                      f'{entry_reason[:400]}</td></tr>')
    life_block = _block("② VÒNG ĐỜI LỆNH", life_rows)

    # ③ MỨC GIÁ & BẢO VỆ
    price_rows = _kv_row("Giá vào lệnh", f"{entry_price:.5f}")
    if stop_price:
        dist = abs(entry_price - float(stop_price))
        price_rows += _kv_row(
            "Cầu chì ban đầu (SL server)",
            f"{stop_price:.5f} <span style='color:#94a3b8;font-weight:500'>"
            f"(cách {dist:.5f})</span>")
    else:
        price_rows += _kv_row("Cầu chì ban đầu (SL server)", "Không có")
    price_rows += _kv_row("Chốt lời (TP)", "Không đặt TP cố định")
    price_rows += _kv_row("Giá đóng", f"{exit_price:.5f}", close_fg)
    price_block = _block("③ MỨC GIÁ & BẢO VỆ", price_rows)

    # ④ PHÂN RÃ PnL — chỉ hiện khi có số thật.
    #
    # Với danh mục giữ lệnh qua đêm và qua cuối tuần, SWAP là lớp chi phí đã từng
    # đảo dấu kết luận của cả một hướng nghiên cứu: Sharpe +0,216 sau
    # spread+commission nhưng **−0,456** sau swap. Gộp nó vào một con số PnL là
    # che đúng lớp chi phí nguy hiểm nhất của hệ này.
    pnl_block = ""
    if any(v is not None for v in (gross_bps, swap_usd, commission_usd, pnl_usd)):
        pr = ""
        if gross_bps is not None:
            pr += _kv_row("Lãi/lỗ thô (Gross)", f"{float(gross_bps):+.1f} bps")
        if commission_usd is not None:
            pr += _kv_row("Phí hoa hồng (Commission)", f"{float(commission_usd):+.2f} $",
                          color="#c0392b" if float(commission_usd) < 0 else "#0f172a")
        if swap_usd is not None:
            pr += _kv_row("Phí qua đêm (Swap)", f"{float(swap_usd):+.2f} $",
                          color="#c0392b" if float(swap_usd) < 0 else "#0f172a")
        if pnl_usd is not None:
            pr += _kv_row("PnL ròng (Net)", f"{pnl:+.2f} $", pnl_fg_value)
        pnl_block = _block("④ PHÂN RÃ PnL", pr)

    guard_label, guard_color = _guard_status()
    status_block = _system_status_block(
        _kv_row("Lớp phòng thủ (FTMO Guard)", guard_label, guard_color)
        + _market_state_rows())

    notice = _notice_card(
        "win" if is_win else "loss", "📊 Ghi chú về cách tính số liệu",
        "Lãi/lỗ tính bằng <b>bps trên giá</b> — đơn vị mà chiến lược sinh ra và là "
        "đơn vị so được với backtest. Quy sang USD cần lot, notional và tỷ giá quy "
        "đổi tại thời điểm đóng; khi thiếu một trong ba, ô USD để trống thay vì in "
        "một con số sai. Lý do đóng lấy từ tập ĐÓNG của "
        "<code>execution/exit_manager.REASONS</code> — không nhánh nào đóng mà "
        "không khai báo lý do.",
        f"Email tự động từ {_bot()}.")

    html = _header(border, "Real-time Trade Alert", header_title, dir_txt, dir_bg,
                   _stamps(now, broker_close), "Chiến lược", strategy,
                   ids + prices + result_block + life_block + price_block
                   + pnl_block + status_block,
                   notice)

    text = (
        f"{res_text} — ĐÓNG LỆNH\n"
        f"{now} (GMT +7)"
        + (f" | {broker_close} (giờ Broker/MT5)" if broker_close else "") + "\n\n"
        f"ĐỊNH DANH\n"
        f"  - Chiến lược: {strategy}\n"
        f"  - Tài khoản (Account ID): {os.environ.get('MT5_LOGIN', 'Unknown')}\n"
        f"  - Trade ID: {trade_id or '—'}\n"
        f"  - Symbol: {symbol}\n"
        + (f"  - Magic: {magic}\n" if magic is not None else "")
        + f"  - Build version: {_version()}\n\n"
        f"① KẾT QUẢ\n"
        f"  - Kết quả: {res_text}\n"
        + (f"  - Lãi/lỗ (bps): {float(gross_bps):+.1f} bps\n"
           if gross_bps is not None else "")
        + (f"  - MFE: {float(mfe):+.1f} bps\n" if mfe is not None else "")
        + (f"  - MAE: {float(mae):+.1f} bps\n" if mae is not None else "")
        + f"  - Khối lượng (Lot): {lots:.2f} lot\n"
        + (f"  - Lãi/lỗ ($): {pnl:+.2f} $\n" if pnl_usd is not None else "")
        + (f"  - Equity sau đóng: {equity:,.2f} $\n" if equity else "")
        + f"\n② VÒNG ĐỜI LỆNH\n"
        f"  - Thời gian mở lệnh: {entry_time or '—'} (GMT+7)"
        + (f" | {broker_open} (giờ Broker/MT5)" if broker_open else "") + "\n"
        f"  - Thời gian đóng lệnh: {now} (GMT+7)"
        + (f" | {broker_close} (giờ Broker/MT5)" if broker_close else "") + "\n"
        + (f"  - Thời gian nắm giữ: {_fmt_duration(float(holding_hours))}\n"
           if holding_hours is not None else "")
        + (f"  - Số nến đã giữ: {bars_held} nến "
           f"{('(' + timeframe + ')') if timeframe else ''}\n"
           if bars_held is not None else "")
        + f"  - Lý do đóng: "
          f"{_CLOSE_REASON_VI.get(str(reason).upper(), (reason or '—', ''))[0]}\n"
        + (f"    {exit_detail}\n" if exit_detail else "")
        + (f"  - Lý do vào lệnh ban đầu: {entry_reason[:400]}\n" if entry_reason else "")
        + f"\n③ MỨC GIÁ & BẢO VỆ\n"
        f"  - Giá vào lệnh: {entry_price:.5f}\n"
        + (f"  - Cầu chì ban đầu: {float(stop_price):.5f}\n" if stop_price
           else "  - Cầu chì ban đầu: Không có\n")
        + f"  - Chốt lời (TP): Không đặt TP cố định\n"
        f"  - Giá đóng: {exit_price:.5f}\n"
        + (("\n④ PHÂN RÃ PnL\n"
            + (f"  - Lãi/lỗ thô (Gross): {float(gross_bps):+.1f} bps\n"
               if gross_bps is not None else "")
            + (f"  - Phí hoa hồng: {float(commission_usd):+.2f} $\n"
               if commission_usd is not None else "")
            + (f"  - Phí qua đêm (Swap): {float(swap_usd):+.2f} $\n"
               if swap_usd is not None else "")
            + (f"  - PnL ròng (Net): {pnl:+.2f} $\n" if pnl_usd is not None else ""))
           if pnl_block else "")
        + f"\n🛡️ Trạng thái hệ thống\n"
        f"  - Lớp phòng thủ (FTMO Guard): {guard_label}\n"
        f"\n📊 Lãi/lỗ tính bằng bps trên giá — đơn vị so được với backtest.\n"
    )
    subject = (f"{'✅' if is_win else '❌'} [{_bot()}] ĐÓNG LỆNH "
               f"{'WIN' if is_win else 'LOSS'}: {strategy} — {symbol} "
               f"({(f'{pnl:+.2f} $') if pnl_usd is not None else f'{float(gross_bps or 0):+.1f} bps'})")
    return _emit(subject, html, text)


def order_rejected(*, symbol: str, action: str, lots: float, retcode: int,
                   comment: str = "", fatal: bool = False,
                   side: str = "", bar_utc: str = "") -> bool:
    """CLONE `send_alert(f"order_rejected_{retcode}", …)` của `mt5_bridge`.

    Bản cũ dùng khung CẢNH BÁO đơn giản của `send_alert` (nền trắng, viền hổ
    phách, tiêu đề "⚠️ CẢNH BÁO HỆ THỐNG") chứ KHÔNG phải card 4 khối — giữ đúng
    như vậy: đây là sự cố hạ tầng, không phải báo cáo giao dịch, và trộn hai loại
    vào một hình dạng làm mất khả năng phân biệt khi quét nhanh hộp thư.
    """
    color = "#dc3545" if fatal else BORDER_REJECT
    head = "#b02a37" if fatal else "#b45309"
    lead = ("Mã lỗi này thuộc nhóm KHÔNG tự khỏi — cầu dao đã ngắt và hệ sẽ không "
            "thử lại cho tới khi người vận hành xử lý."
            if fatal else
            "Mã lỗi này thuộc nhóm tạm thời — hệ sẽ thử lại ở chu kỳ sau.")
    subject = (f"{'⛔' if fatal else '⚠️'} [{_bot()}] LỆNH BỊ TỪ CHỐI "
               f"{action} {symbol} — retcode {retcode}")
    html = (
        f"<div style='font-family:Segoe UI,Arial,sans-serif;border:1px solid {color};"
        f"border-radius:8px;padding:16px;max-width:600px;background:#ffffff'>"
        f"<h3 style='color:{head};margin:0 0 10px 0'>"
        f"{'⛔ LỆNH BỊ TỪ CHỐI (FATAL)' if fatal else '⚠️ LỆNH BỊ TỪ CHỐI'}</h3>"
        f"<div style='font-size:14px;color:#334155;line-height:1.6'>"
        f"Broker từ chối lệnh <b>{action} {symbol}</b>. {lead}</div>"
        + _table([("Tài khoản (Account ID)", os.environ.get("MT5_LOGIN", "Unknown")),
                  ("Công cụ (Symbol)", symbol),
                  ("Hành động", action),
                  ("Chiều", side or "—"),
                  ("Khối lượng", f"{lots:.2f} lot"),
                  ("Nến tín hiệu", bar_utc or "—"),
                  ("Retcode", retcode),
                  ("Broker trả lời", comment or "—"),
                  ("Build version", _version()),
                  ("Thời điểm", f"{_now_local()} (GMT +7)")])
        + f"<p style='font-size:12px;color:#6c757d;border-top:1px solid #dee2e6;"
          f"padding-top:8px;margin-bottom:0'>Khoá chống gửi trùng của lệnh này đã "
          f"được NHẢ, nên chu kỳ sau hệ được phép thử lại cùng nến. "
          f"Email tự động từ {_bot()}.</p>"
        + "</div>"
    )
    text = (
        f"Cảnh báo hệ thống {_bot()}:\n\n"
        f"{'⛔ FATAL' if fatal else '⚠️'} Lệnh {action} {symbol} {lots:.2f} lot bị từ chối.\n"
        f"💼 Tài khoản: {os.environ.get('MT5_LOGIN', 'Unknown')}\n"
        f"🧭 Chiều: {side or '—'} | Nến tín hiệu: {bar_utc or '—'}\n"
        f"🔢 Retcode: {retcode}\n"
        f"💬 Broker: {comment or '—'}\n"
        f"📦 Build: {_version()}\n"
        f"{lead}\n"
        f"Thời điểm: {_now_local()} (GMT +7)\n"
    )
    return _emit(subject, html, text)


# ═════════════════════════════════════════ 3. rủi ro và tuân thủ FTMO
#
# CLONE nguyên văn các `send_alert(...)` của `core/infra/risk_guard.py` và
# `core/infra/ftmo_guard.py` hệ XAUUSD.
#
# Nhóm này KHÔNG dùng card 4 khối như nhóm vào/đóng lệnh — và đó là chủ ý của bản
# cũ, không phải thiếu sót: cảnh báo rủi ro phải trông KHÁC HẲN báo cáo giao dịch
# để người vận hành phân biệt được trong một cái liếc. Bản cũ dùng hai khung:
#
#   · khung ĐỎ nền `#f8d7da` — kill switch, sự kiện một chiều cần can thiệp tay
#   · khung CẢNH BÁO của `send_alert` (viền hổ phách, tiêu đề "⚠️ CẢNH BÁO HỆ
#     THỐNG") — mọi cảnh báo còn lại
def _alert_wrap(body_html: str) -> str:
    """Khung bao mặc định của `utils/alerts.send_alert` bản cũ, giữ nguyên."""
    return ("<div style='font-family:Segoe UI,Arial,sans-serif;border:1px solid #f59e0b;"
            "border-radius:8px;padding:16px;max-width:600px;background:#ffffff'>"
            "<h3 style='color:#b45309;margin:0 0 10px 0'>⚠️ CẢNH BÁO HỆ THỐNG</h3>"
            f"<div style='font-size:14px;color:#334155;line-height:1.6'>{body_html}</div>"
            "</div>")


def _critical_wrap(title: str, body_html: str) -> str:
    """Khung ĐỎ của `risk_guard` cho sự kiện một chiều (kill switch)."""
    return ("<div style='font-family:Segoe UI,Arial,sans-serif;border: 1px solid #dc3545; "
            "border-radius: 8px; padding: 16px; background-color: #f8d7da;'>"
            f"<h2 style='color: #dc3545; margin-top: 0;'>{title}</h2>"
            f"{body_html}</div>")


# Bảng nền vàng của cảnh báo drawdown bản cũ — giữ nguyên mã màu.
_WARN_CELL = "padding: 8px; border: 1px solid #ffe69c;"


def _warn_table(pairs) -> str:
    rows = []
    for i, (label, value) in enumerate(pairs):
        bg = " style='background-color: #fff3cd;'" if i % 2 == 0 else ""
        rows.append(f"<tr{bg}><td style='{_WARN_CELL}'><b>{label}</b></td>"
                    f"<td style='{_WARN_CELL}'>{value}</td></tr>")
    return ("<table style='width: 100%; border-collapse: collapse; margin: 12px 0;'>"
            + "".join(rows) + "</table>")


def drawdown_warning(*, equity: float, day_start: float, dd_pct: float,
                     threshold_pct: float, consec_loss: int = 0,
                     trades_today: int = 0) -> bool:
    """CLONE `send_alert("drawdown_warning", …)` — `risk_guard.py:350`."""
    subject = f"[{_bot()}] CẢNH BÁO MỨC SỤT GIẢM (DRAWDOWN) {dd_pct:.1f}%"
    text = (
        f"Vốn hiện tại (Equity): {equity:,.2f} / Đầu ngày: {day_start:,.2f} "
        f"-> Drawdown {dd_pct:.1f}% >= Ngưỡng cảnh báo {threshold_pct}%.\n"
        f"Chuỗi thua liên tiếp (consec_loss) = {consec_loss}, "
        f"Số lệnh hôm nay (trades_today) = {trades_today}.\n"
        f"Giới hạn lỗ ngày FTMO: {_limits()['daily']} | Sàn nội bộ: {_limits()['floor']} (luật FTMO {_limits()['max']}).\n"
    )
    body = (
        f"<b>Mức sụt giảm vốn (Drawdown) đã chạm ngưỡng cảnh báo!</b><br><br>"
        + _warn_table([
            ("Vốn hiện tại (Equity)", f"{equity:,.2f}"),
            ("Vốn đầu ngày", f"{day_start:,.2f}"),
            ("Mức sụt giảm (Drawdown)",
             f"<b style='color: #dc3545;'>{dd_pct:.1f}%</b> "
             f"(Ngưỡng cảnh báo: {threshold_pct}%)"),
            ("Chuỗi thua liên tiếp", consec_loss),
            ("Số lệnh hôm nay", trades_today),
            # HAI HÀNG THÊM cho hệ Forex: bên XAU không neo vào luật quỹ trong thư
            # này. Ở đây phải neo, vì mỗi mốc chỉ có ý nghĩa khi đọc cùng khoảng
            # cách còn lại tới giới hạn cứng — đó là thứ quyết định hành động.
            ("Giới hạn lỗ ngày FTMO", _limits()["daily"]),
            ("Sàn nội bộ", f"{_limits()['floor']} (luật FTMO {_limits()['max']})"),
        ])
    )
    return _emit(subject, _alert_wrap(body), text)


def day_halt(*, reason: str, equity: float = 0.0, day_start: float = 0.0,
             dd_pct: float = 0.0) -> bool:
    """CLONE `send_alert("day_halt", …)` — `risk_guard.py:286`."""
    subject = f"🛑 [{_bot()}] RISK GUARD: DỪNG GIAO DỊCH HẾT NGÀY"
    text = (f"Lý do: {reason}\n"
            f"Bot sẽ tự mở lại vào ngày giao dịch kế tiếp.\n"
            f"Equity: {equity:,.2f} | Đầu ngày: {day_start:,.2f} | "
            f"Sụt vốn ngày: {dd_pct:.2f}%\n")
    body = (
        f"<b>Trạng thái:</b> <span style='color: #dc3545;'>Đã dừng giao dịch hết "
        f"ngày (Day Halt)</span><br><br>"
        f"<table style='width: 100%; border-collapse: collapse; margin: 12px 0;'>"
        f"<tr><td style='padding: 8px; border: 1px solid #dee2e6;'><b>Lý do</b></td>"
        f"<td style='padding: 8px; border: 1px solid #dee2e6;'><code>{reason}</code></td></tr>"
        f"<tr><td style='padding: 8px; border: 1px solid #dee2e6;'><b>Equity</b></td>"
        f"<td style='padding: 8px; border: 1px solid #dee2e6;'>{equity:,.2f}</td></tr>"
        f"<tr><td style='padding: 8px; border: 1px solid #dee2e6;'><b>Vốn đầu ngày</b></td>"
        f"<td style='padding: 8px; border: 1px solid #dee2e6;'>{day_start:,.2f}</td></tr>"
        f"<tr><td style='padding: 8px; border: 1px solid #dee2e6;'><b>Sụt vốn ngày</b></td>"
        f"<td style='padding: 8px; border: 1px solid #dee2e6;'>{dd_pct:.2f}%</td></tr>"
        f"</table>"
        # CÂU THÊM cho hệ Forex: bên XAU đóng hết lệnh trước khi dừng, ở đây vị thế
        # được GIỮ. Không nói rõ thì người đọc tưởng "dừng giao dịch" là đã phẳng sổ.
        f"<i>Vị thế đang mở được GIỮ và vẫn được quản lý — time-stop vẫn đếm, cầu "
        f"chì vẫn nguyên. Bot sẽ tự động mở lại trạng thái giao dịch vào đầu ngày "
        f"làm việc tiếp theo (chốt theo CE(S)T, không phải UTC).</i>"
    )
    return _emit(subject, _alert_wrap(body), text)


def kill_switch(*, reason: str, equity: float = 0.0, dd_pct: float = 0.0,
                closed_positions: int = 0, total: Optional[int] = None) -> bool:
    """CLONE `send_alert("kill_switch", …)` — `risk_guard.py:466`.

    Giữ nguyên HAI NHÁNH của bản cũ, và đây là chi tiết quan trọng nhất trong cả
    nhóm: đóng ĐỦ và đóng THIẾU là hai tình huống khác hẳn nhau. Đóng thiếu nghĩa
    là vẫn còn vị thế KHÔNG được kill switch kiểm soát, và người vận hành phải vào
    terminal đóng tay NGAY — gộp hai nhánh vào một thư là cách để tình huống thứ
    hai trôi qua mà không ai xử lý.
    """
    closed_ok = total is not None and closed_positions >= total
    tot_txt = total if total is not None else "?"
    if closed_ok:
        subject = f"🚨 [{_bot()}] KÍCH HOẠT GLOBAL KILL SWITCH - ĐÃ ĐÓNG SẠCH VỊ THẾ"
        text = (
            f"Lý do: {reason}\n\n"
            f"Toàn bộ vị thế đã được đóng tự động, entry mới bị chặn trên toàn hệ thống.\n"
            f"Yêu cầu can thiệp thủ công (sử dụng hàm clear_kill_switch()) để mở lại "
            f"sau khi xác minh tình hình.\n"
            f"Equity: {equity:,.2f} | Sụt vốn: {dd_pct:.2f}% | Đã đóng: {closed_positions}\n"
        )
        html = _critical_wrap(
            "🚨 KÍCH HOẠT GLOBAL KILL SWITCH",
            f"<p><b>Trạng thái:</b> Đã đóng toàn bộ vị thế và dừng hệ thống.</p>"
            f"<p><b>Lý do:</b> <code>{reason}</code></p>"
            f"<p><b>Equity:</b> {equity:,.2f} · <b>Sụt vốn:</b> {dd_pct:.2f}% · "
            f"<b>Đã đóng:</b> {closed_positions}/{tot_txt} vị thế</p>"
            f"<hr style='border: 1px solid #f5c2c7; margin: 12px 0;'>"
            f"<p style='margin-bottom: 0;'><b>Hành động yêu cầu:</b> Cần can thiệp thủ "
            f"công (<code>clear_kill_switch()</code>) để mở lại hệ thống sau khi đã "
            f"kiểm tra. Sàn nội bộ 9% — luật FTMO 10% — khoảng cách đó là toàn bộ biên "
            f"an toàn còn lại.</p>")
    else:
        subject = (f"🚨🚨 [{_bot()}] KILL SWITCH: CHƯA ĐÓNG HẾT VỊ THẾ "
                   f"({closed_positions}/{tot_txt}) — CẦN CAN THIỆP THỦ CÔNG NGAY")
        text = (
            f"Lý do: {reason}\n\n"
            f"CẢNH BÁO: hệ thống đã HALT entry mới, nhưng KHÔNG xác nhận đóng hết vị thế "
            f"(đã đóng {closed_positions}/{total if total is not None else 'không xác định'}). "
            f"CÓ THỂ vẫn còn vị thế đang mở KHÔNG được kiểm soát bởi kill switch.\n"
            f"Yêu cầu kiểm tra + đóng thủ công NGAY LẬP TỨC qua terminal MT5, sau đó dùng "
            f"clear_kill_switch() khi đã xác minh an toàn.\n"
        )
        html = _critical_wrap(
            "🚨🚨 KILL SWITCH: CHƯA ĐÓNG HẾT VỊ THẾ",
            f"<p><b>Trạng thái:</b> Đã HALT entry mới, nhưng đóng vị thế "
            f"{closed_positions}/{tot_txt} — CÓ THỂ CÒN VỊ THẾ MỞ.</p>"
            f"<p><b>Lý do:</b> <code>{reason}</code></p>"
            f"<hr style='border: 1px solid #f5c2c7; margin: 12px 0;'>"
            f"<p style='margin-bottom: 0;'><b>Hành động yêu cầu:</b> KIỂM TRA + ĐÓNG THỦ "
            f"CÔNG NGAY qua terminal MT5, sau đó dùng <code>clear_kill_switch()</code> "
            f"khi đã xác minh an toàn.</p>")
    return _emit(subject, html, text)


def ftmo_guard(*, reason: str, equity: float, exposure_x: float = 0.0,
               leverage: float = 0.0, n_positions: int = 0) -> bool:
    """CLONE `send_alert(...)` — `core/infra/ftmo_guard.py:251` hệ XAUUSD.

    Bên XAU thư này cảnh báo "vào quá số lệnh hoặc quá tổng lot cho phép". Hệ Forex
    không giới hạn theo SỐ LỆNH — 27 chân mở cùng lúc là trạng thái bình thường —
    mà theo PHƠI NHIỄM (notional ÷ equity) với trần 3,50x, đo được cho MaxDD đúng
    9,00%. Nên hai ô "số lệnh / tổng lot" đổi thành "phơi nhiễm / đòn bẩy".
    """
    subject = f"🏦 [{_bot()}] CẢNH BÁO TUÂN THỦ FTMO"
    text = (
        f"Lý do: {reason}\n\n"
        f"Equity: {equity:,.2f} | Phơi nhiễm: {exposure_x:.2f}x | "
        f"Đòn bẩy: {leverage:.2f}x (trần 3,50x)\n"
        f"Vị thế đang mở: {n_positions}\n"
        f"Sàn nội bộ {_limits()['floor']} — luật FTMO {_limits()['max']}.\n"
    )
    body = (
        f"<b>Tầng tuân thủ FTMO phát cảnh báo:</b> <code>{reason}</code><br><br>"
        + _warn_table([
            ("Equity", f"{equity:,.2f} USD"),
            ("Phơi nhiễm", f"<b style='color: #dc3545;'>{exposure_x:.2f}x</b> equity"),
            ("Đòn bẩy đang cấp", f"{leverage:.2f}x"),
            ("Trần đòn bẩy", f"{_limits()['lev']} (đo cho MaxDD đúng sàn nội bộ)"),
            ("Vị thế đang mở", n_positions),
            ("Sàn nội bộ", f"{_limits()['floor']} (luật FTMO {_limits()['max']})"),
        ])
    )
    return _emit(subject, _alert_wrap(body), text)


def reward_claim(*, profit_usd: float, profit_pct: float,
                 suggestion: str = "") -> bool:
    """CLONE `send_alert("ftmo_reward_claim", …)` — `ftmo_reward.py:341`."""
    subject = f"💰 [{_bot()}] ĐỦ ĐIỀU KIỆN RÚT LỢI NHUẬN"
    text = (
        f"Tài khoản đã đạt điều kiện yêu cầu chia sẻ lợi nhuận từ quỹ.\n\n"
        f"Lợi nhuận: {profit_usd:,.2f} USD ({profit_pct:+.2f}%)\n"
        f"Đề xuất: {suggestion or '—'}\n"
        f"Chi tiết chu kỳ rút tiền: docs/ftmo/ftmo-risk-and-reward.md\n"
    )
    body = (
        f"<b>Tài khoản đã đạt điều kiện yêu cầu chia sẻ lợi nhuận từ quỹ.</b><br><br>"
        + _warn_table([
            ("Lợi nhuận", f"{profit_usd:,.2f} USD"),
            ("Tỷ lệ", f"<b style='color: #198754;'>{profit_pct:+.2f}%</b>"),
            ("Đề xuất", suggestion or "—"),
        ])
        + f"<i>Chi tiết chu kỳ rút tiền ở <code>docs/ftmo/ftmo-risk-and-reward.md</code>.</i>"
    )
    return _emit(subject, _alert_wrap(body), text)
