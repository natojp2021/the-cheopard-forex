"""
Risk Guard — Trạng thái rủi ro tập trung, PERSISTENT qua restart (spec 02 §1.7, §2.5).

VẤN ĐỀ:
Kiến trúc cũ đặt module này ở `live_strategies/risk_guard.py`, gây import ngược từ các module
tầng thấp hơn (ví dụ: `mt5_bridge.py`, `target_mode.py`), tạo ra rủi ro circular dependency tiềm ẩn khi refactor. 
Trạng thái rủi ro từng nằm trong RAM, khiến việc restart làm mất dữ liệu giới hạn rủi ro.

GIẢI PHÁP & VÌ SAO CẦN:
- Đưa module về `core/infra/` cùng cấp với các module cơ sở khác, triệt tiêu import ngược.
- Guard sở hữu và lưu trữ trạng thái (trades_today, consec_loss, v.v.) vào file JSON, bảo vệ dữ liệu khi khởi động lại.
- Lưu ý: consec_loss chỉ phục vụ day-halt tại đây, không áp dụng penalty cho Kelly scaler (chỉ cần risk guard).
- Nguyên tắc: Một guard không nằm trên live path thì không tồn tại.
"""
import copy
import os
import threading

# Sử dụng get_clock() thay vì gọi trực tiếp time.time() / datetime.now().
# VÌ SAO CẦN: Đảm bảo tính nhất quán thời gian giữa Live (RealClock) và Backtest (mô phỏng).
# Nếu gọi hàm thời gian trực tiếp, backtest sẽ hoàn tất trong vài phút thực và 
# bị xem là cùng một ngày giao dịch, dẫn đến việc reset hằng ngày và cooldown bị hỏng.
from src.python.core.infra.clock import get_clock as _get_clock


def _now_utc():
    """Lấy thời gian UTC hiện tại thông qua clock mô phỏng hoặc thực."""
    return _get_clock().now()


def _now_ts() -> float:
    """Lấy timestamp hiện hành thông qua clock mô phỏng hoặc thực."""
    return _get_clock().now().timestamp()


def _day_key() -> int:
    """Số thứ tự NGÀY GIAO DỊCH FTMO (giờ Praha), KHÔNG phải ngày UTC.

    VẤN ĐỀ VÀ GIẢI PHÁP:
    Nếu dùng ngày UTC sẽ bị lệch 2 giờ so với ngày chốt của FTMO (00:00 Praha = 22:00 UTC).
    Sự sai lệch này có thể làm hỏng logic của day_start_equity (làm trần daily-loss bị đếm lại), 
    trades_today, consec_loss và hiệu lực của day-halt.
    Do đó, hệ thống ưu tiên sử dụng ngày giao dịch từ module ftmo (theo múi giờ Praha).
    """
    try:
        from src.python.core.infra import ftmo
        return ftmo.trading_day().toordinal()
    except Exception:
        # Nhánh này chỉ chạy khi module ftmo hỏng — lúc đó `evaluate()` cũng đã
        # fail-closed chặn hết entry, nên rơi về ngày UTC là chấp nhận được.
        return int(_now_ts() / 86400)
from typing import Any, Dict, Optional, Tuple

import MetaTrader5 as mt5

# Các thư viện datetime/timezone không còn dùng ở đây do logic ghi CSV đã được gỡ bỏ.
from src.python.core.config import (
    LIVE_DIR, INP_MAX_TRADES_DAY, INP_MAX_CONSEC_LOSS_DAY, INP_DAILY_LOSS_CAP_PCT,
    INP_COOLDOWN_MIN, INP_DD_WARN_PCT, INP_KILL_SWITCH_DD_PCT,
)
from src.python.core.infra.state_store import save_json_atomic, load_json
from src.python.utils.logger import log, log_error
from src.python.utils import decision_journal


# ---------------------------------------------------------------- Nguồn tài khoản (Account Source)
# VẤN ĐỀ & VÌ SAO CẦN:
# `risk_guard` là module duy nhất đọc tài khoản qua biến `mt5` cấp module thay vì nhận broker từ caller.
# Trong môi trường backtest qua SimBroker, `mt5.account_info()` sẽ trả về None do không có terminal thật.
# Điều này dẫn đến `day_start_equity = 0`, làm kích hoạt fail-closed chặn toàn bộ entry.
# Giải pháp là tách NGUỒN khỏi NGƯỜI DÙNG thông qua Dependency Injection (`_account_source`), 
# cho phép backtest tiêm mock data mà không ảnh hưởng live.
_account_source = None


def set_account_source(fn) -> None:
    """Đặt nguồn đọc tài khoản (`fn() -> account_info | None`). `None` = về mặc định.

    Chỉ backtest/test gọi. Live KHÔNG gọi -> dùng thẳng `mt5.account_info()`.
    """
    global _account_source
    _account_source = fn


def _account_info():
    """Đọc tài khoản qua nguồn hiện hành. Không bao giờ raise -> None."""
    try:
        return _account_source() if _account_source is not None else mt5.account_info()
    except Exception:
        return None

# Load env variables and read BOT_NAME
try:
    from src.python.utils.env_loader import load_env_file
    load_env_file()
except Exception:
    pass

BOT_NAME = os.environ.get("BOT_NAME", "THE CHEOPARD")

STATE_FILE = os.path.join(LIVE_DIR, "risk_state.json")
SCHEMA_VERSION = 2

_DONE_KEYS = [
    f"done_{k}_{side}"
    for k in ("A", "B", "C", "D", "Dp", "E", "F")
    for side in ("buy", "sell")
]


def _default_state() -> Dict[str, Any]:
    """Khởi tạo trạng thái rủi ro mặc định ban đầu."""
    st = {
        "schema_version": SCHEMA_VERSION,
        "day_key": -1,
        "day_start_equity": 0.0,
        "trades_today": 0,
        "counted_groups_today": [],
        "consec_loss": 0,
        "cooldown_until": 0.0,
        "halted_until_day_key": -1,   # Ngày (broker epoch-day) mà halt còn hiệu lực
        "halt_reason": "",
        # Global Kill Switch: độc lập với day-halt, không tự phục hồi, cần clear thủ công.
        "kill_switch_triggered": False,
        "kill_switch_reason": "",
        # Cờ xác nhận việc đóng vị thế từ kill switch, cho phép retry đóng nếu trước đó chưa đóng hết.
        "kill_switch_close_confirmed": False,
        # Tránh thực thi kép một tín hiệu (deduplication). Định dạng: "<bar_iso>|<strat>|<side>".
        "executed_signals": [],
    }
    for k in _DONE_KEYS:
        st[k] = False
    return st


state: Dict[str, Any] = _default_state()

# state được cập nhật từ nhiều luồng (engine loop, event monitor).
# RLock cho phép các hàm public gọi lẫn nhau an toàn (vd: register_group_result -> _halt_day -> _persist).
_STATE_LOCK = threading.RLock()


def _persist() -> None:
    """Chụp nhanh và lưu trạng thái rủi ro xuống đĩa với cơ chế ghi atomic an toàn."""
    with _STATE_LOCK:
        snapshot = copy.deepcopy(state)  # chụp trong lock, dump ngoài nguy cơ mutate
    if not save_json_atomic(STATE_FILE, snapshot):
        log_error("❌ [RISK GUARD] Không ghi được risk_state.json!")


def load_persisted_state() -> None:
    """Gọi 1 lần khi khởi động: khôi phục risk state để restart không reset cap."""
    data = load_json(STATE_FILE)
    if not data:
        _persist()
        return
    if data.get("schema_version") == 1:
        data["schema_version"] = SCHEMA_VERSION
        data["counted_groups_today"] = []
        log("🔧 [RISK GUARD] Migrated risk_state schema v1 -> v2.")
    elif data.get("schema_version") != SCHEMA_VERSION:
        log("🔧 [RISK GUARD] risk_state.json schema không hợp lệ — dùng state mặc định.")
        _persist()
        return
    for k in state:
        if k in data:
            state[k] = data[k]
   
    # Ý nghĩa các tham số Risk Guard khôi phục từ đĩa (risk_state.json):
    # - day_key: Mã định danh ngày theo Epoch (int(time/86400)), tự động reset khi sang ngày UTC mới.
    # - trades_today: Số lượng lệnh/chuỗi lệnh đã giao dịch trong ngày (để chặn quá INP_MAX_TRADES_DAY).
    # - consec_loss: Số trận thua liên tiếp trong ngày (kích hoạt day-halt nếu vượt INP_MAX_CONSEC_LOSS_DAY).
    # - halted: Trạng thái dừng giao dịch tạm thời (YES + lý do nếu vi phạm rủi ro, ngược lại là 'no').
    is_halted = bool(state["halt_reason"]) and state["halted_until_day_key"] >= state["day_key"]
    if state['trades_today'] > 0 or state['consec_loss'] > 0 or is_halted:
        log(
            f"🛡️ [RISK GUARD] Khôi phục state: day_key={state['day_key']}, trades_today={state['trades_today']}, "
            f"consec_loss={state['consec_loss']}, halted={'YES (' + state['halt_reason'] + ')' if is_halted else 'no'}"
        )


def reset_daily_state() -> None:
    """
    Reset trạng thái đầu ngày (sử dụng ngày UTC/FTMO thống nhất) và chụp equity làm mốc (baseline).
    VÌ SAO CẦN:
    Đồng bộ mốc thời gian với `target_mode.daily_entries_allowed()` thay vì dùng broker-tick-epoch
    để tránh tình trạng có hai khái niệm "ngày" khác nhau, dẫn đến cảnh báo và xử lý sai.
    """
    day_key = _day_key()
    with _STATE_LOCK:
        if state["day_key"] == day_key:
            # Baseline retry: nếu đầu ngày không lấy được equity (=0), thử lại
            # các cycle sau thay vì tắt daily-loss cap suốt cả ngày.
            if state.get("day_start_equity", 0.0) <= 0.0:
                try:
                    acc = _account_info()
                    if acc is not None and float(acc.equity) > 0:
                        state["day_start_equity"] = float(acc.equity)
                        log(f"🛡️ [RISK GUARD] day_start_equity chụp lại được: {state['day_start_equity']:.2f}")
                        _persist()
                except Exception as _e:
                    # Nếu lỗi, log lại rõ ràng để người vận hành biết cảnh báo DD có thể đang không hoạt động.
                    log_error(f"❌ [RISK GUARD] không chụp lại được "
                              f"day_start_equity ({_e}) — mọi cảnh báo drawdown "
                              f"trong ngày sẽ IM LẶNG cho tới khi chụp được.")
            return
        state["day_key"] = day_key
        state["trades_today"] = 0
        state["counted_groups_today"] = []
        state["consec_loss"] = 0
        state["cooldown_until"] = 0.0
        state["halt_reason"] = ""
        for k in _DONE_KEYS:
            state[k] = False
        # Chụp equity đầu ngày (bao gồm floating) làm mốc daily-loss cap
        try:
            acc = _account_info()
            state["day_start_equity"] = float(acc.equity) if acc else 0.0
        except Exception:
            state["day_start_equity"] = 0.0
        log(f"🛡️ Daily state reset for day key: {day_key} | day_start_equity={state['day_start_equity']:.2f}")
        _persist()


def _roll_day_if_needed() -> None:
    """
    Tự cuộn sang ngày mới nếu `day_key` đã đổi — KHÔNG chờ ai gọi hộ.

    VẤN ĐỀ VÀ GIẢI PHÁP:
    Lịch sử cho thấy `reset_daily_state()` chỉ được gọi từ vòng lặp engine, 
    nhưng khi chạy backtest bằng code path không qua engine loop, giới hạn ngày bị vượt trần.
    Tự kiểm tra và tự cuộn ngày trực tiếp tại các hot path xử lý vào/ra lệnh 
    sẽ đảm bảo tính nhất quán (parity) giữa môi trường live và backtest.
    """
    with _STATE_LOCK:
        if state["day_key"] == _day_key():
            return
    reset_daily_state()


def entry_allowed() -> Tuple[bool, str]:
    """
    Tập hợp các cap cấp hệ thống trước khi xét tín hiệu. Trả về (allowed, reason).
    Mọi lần chặn đều được ghi decision journal ở phía gọi.
    """
    _roll_day_if_needed()      # bộ đếm ngày tự cuộn
    with _STATE_LOCK:
        # Kiểm tra halt_reason có giá trị để tránh kích hoạt halt nhầm do trạng thái mặc định (-1 >= -1).
        if state["halt_reason"] and state["halted_until_day_key"] >= state["day_key"]:
            return False, f"day_halted:{state['halt_reason']}"
        if _now_ts() < state["cooldown_until"]:
            return False, "cooldown"
        if state["trades_today"] >= INP_MAX_TRADES_DAY:
            return False, "max_trades_day"
        # Daily loss cap theo EQUITY (tính cả floating) — 100 nghĩa là tắt.
        # FAIL-CLOSED: Khi bật cap nhưng không lấy được equity (mất kết nối, baseline hỏng), 
        # hệ thống sẽ CHẶN entry thay vì ngó lơ âm thầm.
        if 0 < INP_DAILY_LOSS_CAP_PCT < 100:
            if state["day_start_equity"] <= 0:
                return False, "daily_loss_cap_baseline_unavailable"
            try:
                acc = _account_info()
                if acc is None:
                    return False, "daily_loss_cap_equity_unavailable"
                loss_pct = (state["day_start_equity"] - float(acc.equity)) / state["day_start_equity"] * 100.0
                if loss_pct >= INP_DAILY_LOSS_CAP_PCT:
                    _halt_day(f"daily_loss_cap {loss_pct:.1f}% >= {INP_DAILY_LOSS_CAP_PCT}%")
                    return False, "daily_loss_cap"
            except Exception:
                return False, "daily_loss_cap_equity_unavailable"
        return True, ""


def _halt_day(reason: str) -> None:
    """Thực hiện khóa giao dịch (day-halt) cho đến hết ngày."""
    with _STATE_LOCK:
        # Cần kiểm tra halt_reason tồn tại, đảm bảo không áp dụng khóa nhầm ngay khi vừa khởi tạo bot.
        if state["halt_reason"] and state["halted_until_day_key"] >= state["day_key"]:
            return
        state["halted_until_day_key"] = state["day_key"]
        state["halt_reason"] = reason
    log_error(f"🛑 [RISK GUARD] HALT hết ngày: {reason}")
    decision_journal.record("RISK", "day_halt", detail=reason)
    try:
        from src.python.utils.alerts import send_alert
        send_alert("day_halt", f"🛑 [{BOT_NAME}] RISK GUARD: DỪNG GIAO DỊCH HẾT NGÀY",
                   f"Lý do: {reason}\nBot sẽ tự mở lại vào ngày giao dịch kế tiếp.",
                   body_html=(f"<b>Trạng thái:</b> <span style='color: #dc3545;'>Đã dừng giao dịch hết ngày (Day Halt)</span><br><br>"
                              f"<table style='width: 100%; border-collapse: collapse; margin: 12px 0;'>"
                              f"<tr><td style='padding: 8px; border: 1px solid #dee2e6;'><b>Lý do</b></td><td style='padding: 8px; border: 1px solid #dee2e6;'><code>{reason}</code></td></tr>"
                              f"</table>"
                              f"<i>Bot sẽ tự động mở lại trạng thái giao dịch vào đầu ngày làm việc tiếp theo.</i>"))
    except Exception as _e:
        # Vẫn tiếp tục thực hiện khoá, không để lỗi gửi email làm hỏng tiến trình dừng.
        # Tuy nhiên cần log ra lỗi rõ ràng để người vận hành kiểm tra tình trạng kết nối.
        log_error(f"❌ [RISK GUARD] KHÔNG gửi được email báo dừng ngày ({_e}) — "
                  f"bot ĐÃ dừng, chỉ là thông báo không tới nơi.")
    _persist()


def halt_day(reason: str) -> None:
    """Public helper to halt trading for the rest of the day (e.g., from pre-trade risk check)."""
    _halt_day(reason)


_last_dd_check_ts = 0.0

def monitor_equity_drawdown() -> None:
    """
    Cảnh báo drawdown intraday theo equity (spec §1.8). Tự throttle 60s/lần; email dedup 6h. 
    Chỉ mang tính chất CẢNH BÁO — không chặn lệnh trực tiếp ở đây.

    VẤN ĐỀ VÀ VÌ SAO CẦN:
    Chức năng này cần được gọi định kỳ để theo dõi liên tục mức sụt giảm trong ngày.
    Hiện tại nó được gọi từ `ftmo_guard.check()` (vòng lặp mỗi chu kỳ) để đảm bảo 
    người vận hành luôn được cảnh báo sớm nhất khi có dấu hiệu rủi ro.
    """
    global _last_dd_check_ts
    now = _now_ts()
    if now - _last_dd_check_ts < 60:
        return
    _last_dd_check_ts = now
    base = state.get("day_start_equity", 0.0)
    if base <= 0:
        return
    try:
        acc = _account_info()
        if acc is None:
            return
        dd_pct = (base - float(acc.equity)) / base * 100.0
        if dd_pct >= INP_DD_WARN_PCT:
            from src.python.utils.alerts import send_alert
            subject = f"[{BOT_NAME}] CẢNH BÁO MỨC SỤT GIẢM (DRAWDOWN) {dd_pct:.1f}%"
            text_body = (
                f"Vốn hiện tại (Equity): {acc.equity:,.2f} / Đầu ngày: {base:,.2f} -> Drawdown {dd_pct:.1f}% "
                f">= Ngưỡng cảnh báo {INP_DD_WARN_PCT}%.\n"
                f"Chuỗi thua liên tiếp (consec_loss) = {state.get('consec_loss', 0)}, "
                f"Số lệnh hôm nay (trades_today) = {state.get('trades_today', 0)}."
            )
            html_body = (
                f"<b>Mức sụt giảm vốn (Drawdown) đã chạm ngưỡng cảnh báo!</b><br><br>"
                f"<table style='width: 100%; border-collapse: collapse; margin: 12px 0;'>"
                f"<tr style='background-color: #fff3cd;'><td style='padding: 8px; border: 1px solid #ffe69c;'><b>Vốn hiện tại (Equity)</b></td><td style='padding: 8px; border: 1px solid #ffe69c;'>{acc.equity:,.2f}</td></tr>"
                f"<tr><td style='padding: 8px; border: 1px solid #ffe69c;'><b>Vốn đầu ngày</b></td><td style='padding: 8px; border: 1px solid #ffe69c;'>{base:,.2f}</td></tr>"
                f"<tr style='background-color: #fff3cd;'><td style='padding: 8px; border: 1px solid #ffe69c;'><b>Mức sụt giảm (Drawdown)</b></td><td style='padding: 8px; border: 1px solid #ffe69c;'><b style='color: #dc3545;'>{dd_pct:.1f}%</b> (Ngưỡng cảnh báo: {INP_DD_WARN_PCT}%)</td></tr>"
                f"<tr><td style='padding: 8px; border: 1px solid #ffe69c;'><b>Chuỗi thua liên tiếp</b></td><td style='padding: 8px; border: 1px solid #ffe69c;'>{state.get('consec_loss', 0)}</td></tr>"
                f"<tr style='background-color: #fff3cd;'><td style='padding: 8px; border: 1px solid #ffe69c;'><b>Số lệnh hôm nay</b></td><td style='padding: 8px; border: 1px solid #ffe69c;'>{state.get('trades_today', 0)}</td></tr>"
                f"</table>"
            )
            send_alert("drawdown_warning", subject, text_body, ttl_sec=6 * 3600, body_html=html_body)
            decision_journal.record("RISK", "drawdown_warning", dd_pct=round(dd_pct, 2))
    except Exception as _e:
        log_error(f"❌ [RISK GUARD] KHÔNG gửi được cảnh báo drawdown ({_e}).")


def check_kill_switch() -> None:
    """
    Kiểm tra và kích hoạt Global Kill Switch — khiên bảo vệ cuối cùng.

    VÌ SAO CẦN:
    Độc lập với day-halt thông thường, module này luôn bật. Khi sụt giảm equity chạm 
    ngưỡng INP_KILL_SWITCH_DD_PCT, nó sẽ đóng SẠCH mọi vị thế và khóa toàn bộ hệ thống.
    
    CƠ CHẾ:
    - Yêu cầu can thiệp thủ công qua clear_kill_switch() để mở lại.
    - Được gọi mỗi chu kỳ từ engine loop. Tối ưu bằng cờ sticky để tránh lặp luồng cảnh báo.
    - Nếu lần kích hoạt trước đóng vị thế chưa triệt để, hệ thống sẽ tự thử đóng nốt (retry) ở chu kỳ sau.
    """
    with _STATE_LOCK:
        already_triggered = bool(state.get("kill_switch_triggered"))
        close_confirmed = bool(state.get("kill_switch_close_confirmed"))
    if already_triggered and close_confirmed:
        return

    if already_triggered:
        # Retry đóng lại vị thế nếu lần kích hoạt trước chưa đóng sạch.
        # Tránh tính toán lại DD hay spam luồng cảnh báo.
        reason = state.get("kill_switch_reason") or "GLOBAL KILL SWITCH (retry đóng vị thế còn sót)"
        log_error(f"🚨 [RISK GUARD] Kill switch đã trigger trước đó nhưng CHƯA xác nhận đóng hết "
                  f"vị thế — thử đóng lại: {reason}")
    else:
        base = state.get("day_start_equity", 0.0)
        if base <= 0:
            return
        try:
            acc = _account_info()
            if acc is None:
                return
            dd_pct = (base - float(acc.equity)) / base * 100.0
        except Exception:
            return
        if dd_pct < INP_KILL_SWITCH_DD_PCT:
            return

        reason = f"GLOBAL KILL SWITCH: floating DD {dd_pct:.1f}% >= {INP_KILL_SWITCH_DD_PCT}% (day_start_equity={base:.2f})"
        with _STATE_LOCK:
            if state.get("kill_switch_triggered"):
                return
            state["kill_switch_triggered"] = True
            state["kill_switch_reason"] = reason
        log_error(f"🚨🚨 [RISK GUARD] {reason} — DONG SACH toan bo vi the + HALT toan he thong.")
        decision_journal.record("RISK", "kill_switch_triggered", dd_pct=round(dd_pct, 2), detail=reason)

    closed, total = 0, None
    try:
        from src.python.core.infra import mt5_bridge
        closed, total = mt5_bridge.close_all_positions(reason=reason)
        log_error(f"🚨 [RISK GUARD] Kill switch: da dong {closed}/{total} vi the.")
    except Exception as _ce:
        log_error(f"❌ [RISK GUARD] Kill switch: loi khi dong vi the (bo qua, van halt): {_ce}")
    # Chỉ xác nhận là đóng hoàn tất khi biết được tổng số (total) và số lệnh đóng (closed) thoả mãn.
    # Ngược lại, cần retry ở chu kỳ kế.
    closed_ok = (total is not None and closed >= total)

    try:
        from src.python.core.broker.order_state_machine import OrderStateMachine
        OrderStateMachine.halt_trading(reason)
    except Exception as _he:
        log_error(f"❌ [RISK GUARD] Kill switch: loi khi halt_trading (bo qua): {_he}")

    with _STATE_LOCK:
        state["kill_switch_close_confirmed"] = closed_ok
    _persist()

    try:
        from src.python.utils.alerts import send_alert
        if closed_ok:
            subject = f"🚨 [{BOT_NAME}] KÍCH HOẠT GLOBAL KILL SWITCH - ĐÃ ĐÓNG SẠCH VỊ THẾ"
            text_body = (
                f"Lý do: {reason}\n\n"
                f"Toàn bộ vị thế đã được đóng tự động, entry mới bị chặn trên toàn hệ thống.\n"
                f"Yêu cầu can thiệp thủ công (sử dụng hàm clear_kill_switch()) để mở lại sau khi xác minh tình hình."
            )
            html_body = (
                f"<div style='border: 1px solid #dc3545; border-radius: 8px; padding: 16px; background-color: #f8d7da;'>"
                f"<h2 style='color: #dc3545; margin-top: 0;'>🚨 KÍCH HOẠT GLOBAL KILL SWITCH</h2>"
                f"<p><b>Trạng thái:</b> Đã đóng toàn bộ vị thế và dừng hệ thống.</p>"
                f"<p><b>Lý do:</b> <code>{reason}</code></p>"
                f"<hr style='border: 1px solid #f5c2c7; margin: 12px 0;'>"
                f"<p style='margin-bottom: 0;'><b>Hành động yêu cầu:</b> Cần can thiệp thủ công (<code>clear_kill_switch()</code>) để mở lại hệ thống sau khi đã kiểm tra.</p>"
                f"</div>"
            )
        else:
            # Gửi cảnh báo nhấn mạnh việc đóng chưa hoàn tất và yêu cầu kiểm tra/đóng bằng tay ngay lập tức.
            subject = (f"🚨🚨 [{BOT_NAME}] KILL SWITCH: CHƯA ĐÓNG HẾT VỊ THẾ "
                       f"({closed}/{total if total is not None else '?'}) — CẦN CAN THIỆP THỦ CÔNG NGAY")
            text_body = (
                f"Lý do: {reason}\n\n"
                f"CẢNH BÁO: hệ thống đã HALT entry mới, nhưng KHÔNG xác nhận đóng hết vị thế "
                f"(đã đóng {closed}/{total if total is not None else 'không xác định'}). "
                f"CÓ THỂ vẫn còn vị thế đang mở KHÔNG được kiểm soát bởi kill switch.\n"
                f"Yêu cầu kiểm tra + đóng thủ công NGAY LẬP TỨC qua terminal MT5, sau đó dùng "
                f"clear_kill_switch() khi đã xác minh an toàn."
            )
            html_body = (
                f"<div style='border: 1px solid #dc3545; border-radius: 8px; padding: 16px; background-color: #f8d7da;'>"
                f"<h2 style='color: #dc3545; margin-top: 0;'>🚨🚨 KILL SWITCH: CHƯA ĐÓNG HẾT VỊ THẾ</h2>"
                f"<p><b>Trạng thái:</b> Đã HALT entry mới, nhưng đóng vị thế "
                f"{closed}/{total if total is not None else '?'} — CÓ THỂ CÒN VỊ THẾ MỞ.</p>"
                f"<p><b>Lý do:</b> <code>{reason}</code></p>"
                f"<hr style='border: 1px solid #f5c2c7; margin: 12px 0;'>"
                f"<p style='margin-bottom: 0;'><b>Hành động yêu cầu:</b> KIỂM TRA + ĐÓNG THỦ CÔNG NGAY qua "
                f"terminal MT5, sau đó dùng <code>clear_kill_switch()</code> khi đã xác minh an toàn.</p>"
                f"</div>"
            )
        send_alert("kill_switch", subject, text_body, body_html=html_body)
    except Exception as _e:
        # Trường hợp xấu nhất khi email bị lỗi, log ra console là cơ hội cuối cùng 
        # để báo động người điều hành.
        log_error(f"🛑 [RISK GUARD] KHÔNG gửi được email KILL SWITCH ({_e}) — "
                  f"KILL SWITCH ĐÃ KÍCH HOẠT nhưng thông báo không tới nơi. "
                  f"KIỂM TRA TERMINAL MT5 NGAY.")


def clear_kill_switch(reason: str) -> bool:
    """
    Xóa trạng thái khóa của Kill Switch (mở lại bot), yêu cầu lý do hợp lệ để lưu audit log.
    Hàm này phải do người vận hành kích hoạt sau khi đã kiểm tra thủ công sự cố.
    """
    if not reason:
        log_error("❌ [RISK GUARD] clear_kill_switch() từ chối — cần lý do (audit trail).")
        return False
    with _STATE_LOCK:
        state["kill_switch_triggered"] = False
        state["kill_switch_reason"] = ""
        state["kill_switch_close_confirmed"] = False
    _persist()
    try:
        from src.python.core.broker.order_state_machine import OrderStateMachine
        OrderStateMachine.clear_trading_halt(reason)
    except Exception as _e:
        log_error(f"❌ [RISK GUARD] clear_kill_switch: lỗi clear_trading_halt (bỏ qua): {_e}")
    log_error(f"✅ [RISK GUARD] KILL SWITCH đã được RESUME thủ công: {reason}")
    decision_journal.record("RISK", "kill_switch_cleared", detail=reason)
    return True


def signal_already_executed(bar_time: str, strat: str, side: int) -> bool:
    """Kiểm tra tín hiệu (bar, strat, side) đã được thực thi chưa nhằm tránh bị lặp lệnh."""
    key = f"{bar_time}|{strat}|{side}"
    with _STATE_LOCK:
        return key in state.get("executed_signals", [])


def mark_signal_executed(bar_time: str, strat: str, side: int) -> None:
    """Lưu lại tín hiệu đã thực thi, duy trì lịch sử ngắn đủ tránh trùng lặp."""
    key = f"{bar_time}|{strat}|{side}"
    with _STATE_LOCK:
        lst = state.setdefault("executed_signals", [])
        if key not in lst:
            lst.append(key)
            del lst[:-200]  # giữ 200 entry gần nhất, đủ phủ nhiều ngày
    _persist()


def register_trade_opened(group_id: Optional[str] = None) -> None:
    """Ghi nhận một lượt mở lệnh để cập nhật đếm số lượng lệnh trong ngày."""
    _roll_day_if_needed()      # đếm vào ĐÚNG ngày
    with _STATE_LOCK:
        if group_id and group_id in state["counted_groups_today"]:
            return
        state["trades_today"] += 1
        if group_id:
            state["counted_groups_today"].append(group_id)
    _persist()


def register_group_result(group_id: str, total_pnl: float, details: Optional[Dict] = None) -> None:
    """
    Nhận kết quả 1 nhóm lệnh vừa đóng hết (từ position_manager):
    - Cập nhật chuỗi thua theo PnL NET của group (quy tắc từ shared.execution_rules.day_risk,
      SSOT chung với backtest). consec_loss chỉ phục vụ day-halt — không có Kelly
      drawdown penalty (quyết định 2026-07-16).
    - Dừng hết ngày nếu chuỗi thua chạm INP_MAX_CONSEC_LOSS_DAY.
    """
    from src.python.shared.execution_rules import day_risk
    with _STATE_LOCK:
        state["consec_loss"] = day_risk.next_consec(state["consec_loss"], total_pnl < 0)
        consec_now = state["consec_loss"]
        if total_pnl < 0:
            # Cooldown SAU LỆNH THUA (INP_COOLDOWN_MIN hiện 0 = tắt, parity backtest)
            state["cooldown_until"] = _now_ts() + INP_COOLDOWN_MIN * 60
    if total_pnl < 0 and day_risk.should_halt_day(consec_now, INP_MAX_CONSEC_LOSS_DAY):
        _halt_day(f"consec_loss {consec_now} >= {INP_MAX_CONSEC_LOSS_DAY}")
    decision_journal.record(
        "EXIT", "group_closed", group_id=group_id, pnl=round(total_pnl, 2),
        consec_loss=consec_now, **(details or {})
    )
    _persist()


# ------------------------------------------------------------------ Ghi log CSV (Lưu trữ)
# VẤN ĐỀ VÀ KIẾN TRÚC HIỆN TẠI (trade CSV):
# Toàn bộ logic ghi `xau_trades_context.csv` phục vụ email reporter đã được loại bỏ.
# Hệ thống hiện tại sử dụng `trade_journal.jsonl` làm SSOT (Single Source of Truth) cho các thống kê.
