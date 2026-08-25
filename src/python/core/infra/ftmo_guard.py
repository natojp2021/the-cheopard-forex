"""ftmo_guard.py — LỚP PHÒNG THỦ CHỦ ĐỘNG: đóng sạch vị thế TRƯỚC ngưỡng FTMO.

VÌ SAO MODULE NÀY PHẢI TỒN TẠI
===============================
Trước 15/08/2026 hệ Forex KHÔNG có lớp nào ĐÓNG lệnh vì rủi ro. Ba lớp đang có —
`entry_gate`, `ftmo_leverage_policy`, `trading_control` — đều chỉ chặn lệnh MỚI.
Đối chiếu với một hệ một-tài-sản cho thấy chỗ hổng: bên đó `engine._loop` gọi
`risk_guard.monitor_equity_drawdown()`, `risk_guard.check_kill_switch()` và
`ftmo_guard.check(mt5)` mỗi chu kỳ; bên này `check_kill_switch()` được port sang
nhưng KHÔNG AI GỌI, và `ftmo_guard` thì không có.

Hệ quả với đúng danh mục này: nhiều chân giữ lệnh qua đêm và qua cuối tuần, không
chân nào có SL theo giá. Giá chạy ngược cả rổ thì không có gì đóng — cầu chì
`disaster_stop` đặt ở ≥8×ATR với ngân sách 2%/vị thế, nên nhiều vị thế cùng nổ
đã vượt xa mốc ngày 5%, mà chúng chỉ nổ SAU khi tổn thất đã xảy ra.

VỊ TRÍ TRONG CHUỖI PHÒNG THỦ
=============================
Bốn lớp, xếp theo thứ tự CHẠM tới, không phải theo mức độ nghiêm trọng:

    1. `ftmo.evaluate().block_reason`      chặn LỆNH MỚI     lỗ ngày dự báo ≥4%
    2. `ftmo_guard.check()`  ← module này  ĐÓNG SẠCH         dự báo ≥4,5% / thực ≥4%
    3. `ftmo_leverage_policy.decide()`     đòn bẩy → 0       đệm tới sàn cạn
    4. `risk_guard.check_kill_switch()`    ĐÓNG SẠCH + halt  lỗ ngày thực ≥ ngưỡng .env

Lớp 2 và lớp 4 làm cùng một việc nhưng KHÔNG thừa: lớp 4 chỉ nhìn lỗ ĐÃ thực hiện,
còn lớp 2 nhìn lỗ đã thực hiện CỘNG rủi ro đang mở. Kịch bản giết tài khoản mà chỉ
lớp 2 bắt được:

    lỗ ngày 3,5% + phơi nhiễm đang mở với rủi ro 1,6% = 5,1% nếu mọi cầu chì cùng nổ

Ở thời điểm đó lớp 4 im lặng (3,5% < ngưỡng), lớp 1 và lớp 3 đã chặn lệnh mới nhưng
KHÔNG đụng tới vị thế đang mở. Chỉ lớp 2 hành động — và đó chính là lần cần hành
động, vì sau khi các cầu chì kích hoạt thì đã quá muộn.

VÌ SAO TÁCH KHỎI `ftmo.py`
===========================
`ftmo.py` là tầng LUẬT: chỉ đo và phán quyết, không chạm broker, nên gọi được từ
backtest và test mà không cần giả lập gì. Module NÀY là tầng HÀNH ĐỘNG: nó gọi
`close_all_positions()`, gửi email, ghi cờ bền vững. Trộn hai thứ lại thì tầng luật
không còn kiểm chứng được độc lập.

ĐÁNH ĐỔI CÓ CHỦ Ý
==================
Đóng lệnh là chốt lỗ ở mức hiện tại và bỏ mất khả năng hồi giá. Đó là đánh đổi theo
đúng thứ tự ưu tiên của hệ (Account Survival > mọi thứ khác): một ngày lỗ 4% vẫn
còn tài khoản để giao dịch tiếp, một lần chạm 5% thì không.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Optional, Tuple

from src.python.core.infra import ftmo
from src.python.shared.paths import LOG_DIR
from src.python.utils.logger import log, log_error

_LOCK = threading.Lock()

# Cờ ĐÃ ĐÓNG SẠCH của ngày, ghi ra đĩa.
#
# Phải bền vững: sau khi đóng sạch, tiến trình có thể bị khởi động lại (watchdog,
# người vận hành mở lại giao diện). Cờ trong RAM sẽ mất, hệ tưởng chưa làm gì và
# cho phép vào lệnh lại ngay trong ngày đã chạm ngưỡng — tức mở lại đúng rủi ro
# vừa cắt. Đây là cùng cái bẫy đã làm mất email "thức dậy" cuối tuần.
STATE_PATH = LOG_DIR / "live" / "ftmo_guard.json"


@dataclass(frozen=True)
class GuardResult:
    """Kết quả một lượt kiểm. `acted=True` nghĩa là ĐÃ gửi lệnh đóng."""
    acted: bool
    reason: str = ""
    closed: int = 0
    total: Optional[int] = None

    def explain(self) -> str:
        if not self.acted:
            return self.reason or "trong hạn mức"
        return (f"ĐÓNG SẠCH — {self.reason} · đã đóng {self.closed}/"
                f"{self.total if self.total is not None else '?'} vị thế")


def _read_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_state(data: dict) -> None:
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(STATE_PATH) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        import os

        os.replace(tmp, STATE_PATH)
    except Exception as exc:
        log_error(f"[FTMO GUARD] KHÔNG ghi được cờ trạng thái: {exc}")


def already_flattened_today() -> bool:
    """Hôm nay ĐÃ đóng sạch vì chạm ngưỡng chưa.

    Ngày tính theo CE(S)T như mọi mốc FTMO khác — dùng UTC ở đây là để lỗ của ngày
    này rơi sang ngày khác và mốc 5% reset sai thời điểm.
    """
    return _read_state().get("flattened_day") == str(ftmo.trading_day())


def open_risk_usd(mt5) -> Tuple[float, bool]:
    """Tổng rủi ro USD nếu MỌI cầu chì đang đặt cùng kích hoạt, và ĐỦ DỮ LIỆU chưa.

    Trả `(rủi_ro, đầy_đủ)`. `đầy_đủ=False` nghĩa là có vị thế KHÔNG đọc được cầu chì
    — bên gọi phải giả định trường hợp xấu nhất chứ không được coi phần đọc được là
    toàn bộ. Đây là chỗ fail-closed quan trọng nhất của module: rủi ro đo thiếu
    trông y hệt rủi ro thấp.
    """
    try:
        positions = mt5.positions_get()
    except Exception:
        return 0.0, False
    if positions is None:
        return 0.0, False           # LỖI ĐỌC, không phải "không có vị thế"

    from src.python.execution import risk_sizing as PS
    from src.python.shared import asset_profile as AP

    total = 0.0
    complete = True
    for p in positions:
        sl = float(getattr(p, "sl", 0.0) or 0.0)
        px = float(getattr(p, "price_current", 0.0) or 0.0)
        lots = abs(float(getattr(p, "volume", 0.0) or 0.0))
        symbol = str(getattr(p, "symbol", ""))
        if sl <= 0.0 or px <= 0.0 or lots <= 0.0:
            # Vị thế KHÔNG có cầu chì: tổn thất tối đa của nó không có chặn trên.
            complete = False
            continue
        try:
            notional = float(PS.lot_notional_usd(
                symbol, px, AP.usd_per_quote(symbol, {symbol: px})))
            total += lots * notional * abs(px - sl) / px
        except Exception:
            complete = False
    return total, complete


def check(mt5, *, equity: Optional[float] = None,
          balance: Optional[float] = None) -> GuardResult:
    """Một lượt kiểm. Đóng sạch nếu đã chạm ngưỡng. KHÔNG BAO GIỜ ném lỗi.

    Gọi mỗi chu kỳ từ `engine._loop`. Chi phí một lượt là một `positions_get()` và
    một phép cộng — rẻ hơn nhiều so với hậu quả của việc gọi thưa.
    """
    try:
        return _check(mt5, equity=equity, balance=balance)
    except Exception as exc:                               # pragma: no cover
        # Hỏng ở chính lớp phòng thủ là tình trạng phải NÓI TO, nhưng không được
        # làm gãy vòng lặp — vòng lặp chết là mất luôn mọi lớp còn lại.
        log_error(f"[FTMO GUARD] lượt kiểm HỎNG: {type(exc).__name__}: {exc}")
        return GuardResult(acted=False, reason=f"lỗi kiểm tra: {exc}")


def _check(mt5, *, equity: Optional[float], balance: Optional[float]) -> GuardResult:
    if equity is None or balance is None:
        try:
            ai = mt5.account_info()
        except Exception:
            ai = None
        if ai is None:
            # Không đọc được tài khoản thì không đo được gì. KHÔNG đóng bừa: đóng
            # sạch là hành động một chiều, và một lần mất kết nối thoáng qua không
            # phải lý do để chốt lỗ cả danh mục.
            return GuardResult(acted=False, reason="chưa đọc được tài khoản")
        equity = float(ai.equity) if equity is None else equity
        balance = float(ai.balance) if balance is None else balance

    if equity <= 0.0:
        return GuardResult(acted=False, reason="equity <= 0, chưa đo được")

    with _LOCK:
        if already_flattened_today():
            return GuardResult(acted=False,
                               reason="hôm nay đã đóng sạch vì chạm ngưỡng")

    # Mốc số dư ĐẦU NGÀY là mẫu số của mọi phép đo dưới đây. Thiếu nó thì không đo
    # được gì — và "không đo được" KHÔNG phải "không sao". Nhưng cũng không đóng
    # bừa: đóng sạch là hành động một chiều, còn thiếu mốc là lỗi cấu hình chứ
    # không phải bằng chứng đang lỗ. Chặn lệnh mới đã do `ftmo.evaluate()` lo.
    day_start = float((ftmo._read_state() or {}).get("day_start_balance") or 0.0)
    if day_start <= 0.0:
        return GuardResult(acted=False, reason="chưa có mốc số dư đầu ngày")

    realized = max(0.0, (day_start - equity) / day_start)
    risk_usd, risk_complete = open_risk_usd(mt5)
    if not risk_complete:
        # Rủi ro đo THIẾU trông y hệt rủi ro THẤP. Giả định mức trần cho phép.
        risk_usd = max(risk_usd, ftmo.MAX_OPEN_RISK * equity)
    projected = realized + (risk_usd / day_start if day_start > 0 else 0.0)

    reason = ""
    if realized >= ftmo.DAILY_FLATTEN_REALIZED:
        reason = (f"lỗ ngày THỰC {realized:.2%} ≥ ngưỡng "
                  f"{ftmo.DAILY_FLATTEN_REALIZED:.1%}")
    elif projected >= ftmo.DAILY_FLATTEN_PROJECTED:
        reason = (f"lỗ ngày DỰ BÁO {projected:.2%} ≥ ngưỡng "
                  f"{ftmo.DAILY_FLATTEN_PROJECTED:.1%} "
                  f"(thực {realized:.2%} + rủi ro đang mở {risk_usd / day_start:.2%}"
                  + ("" if risk_complete else ", ƯỚC LƯỢNG vì thiếu cầu chì") + ")")
    if not reason:
        return GuardResult(acted=False,
                           reason=(f"trong hạn mức · thực {realized:.2%} · "
                                   f"dự báo {projected:.2%}"))

    return _flatten(reason=reason, equity=equity, realized=realized)


def _flatten(*, reason: str, equity: float, realized: float) -> GuardResult:
    """Đóng sạch và ghi cờ. Chỉ ghi cờ khi THẬT SỰ không còn vị thế nào."""
    log_error(f"🚨 [FTMO GUARD] {reason} — ĐÓNG SẠCH VỊ THẾ.")
    closed, total = 0, None
    try:
        from src.python.core.infra.mt5_bridge import close_all_positions

        closed, total = close_all_positions(reason=f"FTMO GUARD: {reason}")
    except Exception as exc:
        log_error(f"[FTMO GUARD] KHÔNG đóng được vị thế: {type(exc).__name__}: {exc}")
        return GuardResult(acted=True, reason=f"{reason} — LỖI ĐÓNG: {exc}")

    if total is not None and closed >= total:
        # Chỉ đánh dấu khi tài khoản THẬT SỰ phẳng. `total=None` nghĩa là
        # `positions_get()` lỗi đọc — lúc đó không khẳng định được gì, và ghi cờ
        # sẽ làm chu kỳ sau bỏ qua bước kiểm này.
        with _LOCK:
            st = _read_state()
            st["flattened_day"] = str(ftmo.trading_day())
            st["reason"] = reason
            _write_state(st)
    else:
        log_error(f"[FTMO GUARD] mới đóng {closed}/{total} — CHƯA đánh dấu, "
                  f"chu kỳ sau sẽ thử tiếp.")

    try:
        from functools import partial

        from src.python.shared.notifications import emails as EM
        from src.python.utils import alerts

        alerts.once("ftmo_guard_flatten",
                    # `total` BẮT BUỘC: thư có hai nhánh, và nhánh "chưa đóng
                    # hết" là nhánh phải gọi người vận hành dậy giữa đêm.
                    partial(EM.kill_switch, reason=reason, equity=equity,
                            dd_pct=realized * 100.0, closed_positions=closed,
                            total=total),
                    ttl_sec=12 * 3600.0)
    except Exception as exc:                               # pragma: no cover
        log(f"[FTMO GUARD] không gửi được email: {exc}")

    return GuardResult(acted=True, reason=reason, closed=closed, total=total)
