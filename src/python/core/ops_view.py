# -*- coding: utf-8 -*-
"""ops_view.py — CÁC HÀM ĐỌC TRẠNG THÁI, cứu ra từ bảng điều khiển Tk trước khi xoá.

VÌ SAO MODULE NÀY TỒN TẠI
==========================
`gui_command_center.py` (1.926 dòng) bị xoá ngày 19/08/2026 khi hệ chuyển sang chạy
console-only. Nhưng khoảng 280 dòng đầu của tệp đó KHÔNG phải code vẽ giao diện — nó
là logic NGHIỆP VỤ đọc trạng thái:

    get_decision_matrix_rows()   quyết định của từng chân: ACTIVE / SCANNING /
                                 REGIME OFF / STAND BY / STOPPED
    get_system_health()          gom sức khoẻ các hệ con thành nhãn đọc được
    get_ai_trend()            thiên hướng RÒNG của danh mục, đo từ vị thế thật
    _open_magics() / _current_r() đọc vị thế đang mở và R hiện tại

Xoá chúng cùng với phần vẽ sẽ mất đúng thứ mà console cần nhất để trả lời câu hỏi
"BOT đang làm gì?". Nên chúng chuyển sang đây NGUYÊN VĂN — cùng logic, cùng chú
thích, chỉ đổi nguồn import màu sang `ops_theme`.

BẤT BIẾN GIỮ NGUYÊN TỪ BẢN CŨ: mọi hàm ở đây fail-soft, không bao giờ ném ra ngoài;
trả "N/A" khi nguồn dữ liệu thật không tồn tại hoặc lỗi. Đây là tầng TRÌNH BÀY —
một nguồn dữ liệu hỏng phải hiện thành "N/A", không được làm chết vòng lặp.

KHÔNG mang theo: `busy_text` (hiệu ứng chấm chạy — console không có animation),
`_kv_row`/`_card`/`_section_title` (dựng widget), `categorize_log` (đã thay bằng
`ops_console.classify`, cùng cách tiếp cận keyword nhưng gắn với nhóm sổ JSONL).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.python.core import strategy_registry as _strategy_registry
from src.python.core.config import SPREAD_CAP, STRAT_MAGICS
from src.python.core.ops_theme import C_GREEN, C_RED, C_TEXT_DIM, C_TEXT_MUT
from src.python.shared import asset_profile as _asset_profile  # noqa: F401


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
