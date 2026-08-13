# -*- coding: utf-8 -*-
"""ftmo_reward.py — GỢI Ý RÚT LỢI NHUẬN (Reward / Payout Suggestion).

TÀI LIỆU MỎ NEO: `docs/ftmo/ftmo-risk-and-reward.md` §III.1
============================================================
    "KHÔNG cần chờ cuối tháng calendar! FTMO áp dụng cơ chế rút tiền linh hoạt
     theo chu kỳ tối thiểu 14 ngày."

    [01/08] Giao dịch ngày đầu tiên ────> [14/08] Đủ điều kiện 14 ngày
                                                  ▼  (Vị thế phải đóng hết)
                                          [Từ 15/08] Đủ điều kiện CLAIM
                                                  ▼
                                          [Review 1-2 ngày] FTMO Approve
                                                  ▼
                                          [Nhận tiền 80%] ~18/08-19/08

MODULE PHỤ — VÀ ĐƯỢC THIẾT KẾ ĐỂ LUÔN LÀ PHỤ
==============================================
Nó chỉ ĐỌC và GỬI EMAIL. Không một đường nào từ module này chạm tới cỡ lệnh,
cổng vào lệnh, hay bất kỳ quyết định giao dịch nào. Đó là ràng buộc có chủ đích:
một gợi ý rút tiền mà lỡ khoá được đường vào lệnh sẽ biến một tiện ích thành
một rủi ro vận hành.

Cụ thể: hàm `check()` **không bao giờ raise** và **không trả về bất cứ thứ gì
mà caller có thể dùng để chặn**. Test khoá đúng hai điều này.

BA ĐIỀU KIỆN CLAIM (theo tài liệu)
====================================
  1. Đủ `MIN_CLAIM_CYCLE_DAYS` = 14 ngày kể từ ngày giao dịch ĐẦU TIÊN của chu kỳ.
  2. Đang có LÃI so với vốn ban đầu (không có lãi thì không có gì để rút).
  3. **Đã đóng hết vị thế.** Đây là điều kiện dễ quên nhất và cũng là điều kiện
     duy nhất phụ thuộc trạng thái tức thời — nên module gợi ý CỬA SỔ thích hợp
     chứ không ra lệnh đóng vị thế. Việc đóng lệnh là quyết định của người vận
     hành, không phải của một module thông báo.

CHỈ PHA FUNDED
===============
Pha CHALLENGE/VERIFICATION không có payout — lãi ở đó chỉ để đạt mục tiêu. Gửi
email "bạn có thể rút $4.000" khi đang thi là sai thông tin ở mức có thể khiến
người vận hành thao tác nhầm.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from src.python.utils.logger import log, log_error

# Chu kỳ rút tối thiểu của FTMO, tính bằng NGÀY LỊCH kể từ ngày giao dịch đầu
# tiên của chu kỳ (không phải ngày giao dịch — tài liệu ghi rõ mốc 01/08 -> 14/08).
MIN_CLAIM_CYCLE_DAYS = 14

# Tỷ lệ chia lợi nhuận chuẩn của FTMO 2-Step.
PROFIT_SPLIT = 0.80

# Ngưỡng lãi TỐI THIỂU mới gợi ý, tính theo tỷ lệ vốn ban đầu. Rút $200 trên tài
# khoản $100.000 là reset chu kỳ 14 ngày để lấy một khoản không đáng — và chu kỳ
# mới bắt đầu lại từ đầu, nên mỗi lần rút có CHI PHÍ CƠ HỘI thật.
MIN_PROFIT_RATIO = 0.01

# Không gửi lại gợi ý sớm hơn ngần này ngày, kể cả khi vẫn đủ điều kiện. Một
# email nhắc mỗi chu kỳ 5 phút thì người nhận sẽ lọc bỏ nó, và lần thật sự quan
# trọng cũng bị lọc theo.
RESUGGEST_COOLDOWN_DAYS = 3

# Khóa đồng bộ cho các thao tác đọc/ghi trạng thái
_lock = threading.RLock()
# Đường dẫn lưu trạng thái của module
_STATE_FILE: Optional[Path] = None


def _state_file() -> Path:
    """Lấy hoặc khởi tạo đường dẫn tới file lưu trạng thái."""
    global _STATE_FILE
    if _STATE_FILE is None:
        from src.python.core.config import LIVE_DIR
        _STATE_FILE = Path(LIVE_DIR) / "ftmo_reward.json"
    return _STATE_FILE


def _default_state() -> Dict[str, Any]:
    """Trả về cấu trúc trạng thái mặc định ban đầu."""
    return {
        # Ngày giao dịch đầu tiên của CHU KỲ hiện tại (ISO, giờ Praha).
        "cycle_start_day": None,
        # Ngày gửi gợi ý gần nhất — dùng cho cooldown.
        "last_suggested_day": None,
        # Đỉnh lãi đã gợi ý, để không nhắc lại cùng một mức.
        "last_suggested_profit": 0.0,
        # Số lần đã gợi ý trong chu kỳ này.
        "suggest_count": 0,
    }


def _read() -> Dict[str, Any]:
    """Đọc trạng thái từ file JSON, trả về giá trị mặc định nếu có lỗi."""
    base = _default_state()
    try:
        from src.python.core.infra.state_store import load_json
        st = load_json(str(_state_file()))
        if isinstance(st, dict):
            base.update(st)
    except Exception as e:
        # Fail-soft: mất trạng thái gợi ý chỉ khiến gửi lại một email thừa.
        # Đây là module PHỤ — không có gì đáng để fail-closed.
        log_error(f"⚠️ [REWARD] không đọc được state gợi ý rút tiền ({e}) — "
                  f"dùng mặc định, có thể gửi lại một email đã gửi.")
    return base


def _write(st: Dict[str, Any]) -> None:
    """Ghi trạng thái hiện tại xuống file JSON một cách an toàn."""
    try:
        from src.python.core.infra.state_store import save_json_atomic
        save_json_atomic(str(_state_file()), st)
    except Exception as e:
        log_error(f"⚠️ [REWARD] không ghi được state gợi ý rút tiền: {e}")


@dataclass(frozen=True)
class RewardSuggestion:
    """Kết quả đánh giá cơ hội rút tiền. Thuần dữ liệu, không hành động."""

    eligible: bool                 # đủ CẢ ba điều kiện chưa
    days_in_cycle: int             # đã qua bao nhiêu ngày lịch của chu kỳ
    days_remaining: int            # còn bao nhiêu ngày nữa đủ 14
    profit_usd: float              # lãi gộp so với vốn ban đầu
    profit_ratio: float            # lãi gộp theo tỷ lệ vốn ban đầu
    trader_payout_usd: float       # phần trader nhận sau khi chia 80%
    open_positions: int            # số vị thế đang mở (phải bằng 0 mới claim được)
    reason: str = ""               # vì sao CHƯA đủ điều kiện
    should_notify: bool = False    # có nên gửi email lúc này không

    @property
    def summary(self) -> str:
        """Một dòng cho log — nói đủ để không phải mở email ra xem."""
        if self.eligible:
            return (f"ĐỦ ĐIỀU KIỆN rút: lãi ${self.profit_usd:,.0f} "
                    f"({self.profit_ratio:+.2%}) -> nhận ${self.trader_payout_usd:,.0f} "
                    f"({PROFIT_SPLIT:.0%}), chu kỳ {self.days_in_cycle} ngày")
        return f"chưa đủ điều kiện rút: {self.reason}"


def _days_between(start_iso: Optional[str], end_iso: str) -> int:
    """Số ngày LỊCH giữa hai mốc ISO. `0` khi thiếu mốc hoặc mốc hỏng."""
    if not start_iso:
        return 0
    try:
        from datetime import date
        a = date.fromisoformat(str(start_iso))
        b = date.fromisoformat(str(end_iso))
        return max(0, (b - a).days)
    except (ValueError, TypeError):
        return 0


def evaluate(equity: float, *, initial_capital: float, phase: str,
             open_positions: int, first_trading_day: Optional[str],
             today: str) -> RewardSuggestion:
    """Đánh giá cơ hội rút tiền. HÀM THUẦN — không đọc file, không gửi email.

    Tách phần tính khỏi phần gửi để test được từng điều kiện bằng đúng con số
    của tài liệu, không phải dựng cả state file lẫn hộp thư.

    `first_trading_day` là ngày giao dịch ĐẦU TIÊN của chu kỳ hiện tại (ISO).
    `None` nghĩa là chưa giao dịch ngày nào — chu kỳ chưa bắt đầu.
    """
    days_in_cycle = _days_between(first_trading_day, today)
    days_remaining = max(0, MIN_CLAIM_CYCLE_DAYS - days_in_cycle)

    profit_usd = float(equity) - float(initial_capital)
    profit_ratio = (profit_usd / initial_capital) if initial_capital > 0 else 0.0
    payout = max(0.0, profit_usd) * PROFIT_SPLIT

    def _no(reason: str) -> RewardSuggestion:
        return RewardSuggestion(
            eligible=False, days_in_cycle=days_in_cycle,
            days_remaining=days_remaining, profit_usd=profit_usd,
            profit_ratio=profit_ratio, trader_payout_usd=payout,
            open_positions=int(open_positions), reason=reason)

    # Thứ tự kiểm: từ điều kiện KHÔNG THỂ đổi trong ngày tới điều kiện có thể.
    # Nhờ đó lý do trả về luôn là thứ người vận hành hành động được hoặc rõ ràng
    # là phải chờ, chứ không phải một lý do tình cờ bắt trước.
    from src.python.core.infra.ftmo import PHASE_FUNDED
    if str(phase).upper() != PHASE_FUNDED:
        return _no(f"pha {phase} chưa có payout — chỉ tài khoản FUNDED mới rút được")
    if not first_trading_day:
        return _no("chu kỳ chưa bắt đầu (chưa có ngày giao dịch nào)")
    if days_remaining > 0:
        return _no(f"còn {days_remaining} ngày nữa mới đủ chu kỳ "
                   f"{MIN_CLAIM_CYCLE_DAYS} ngày (đã qua {days_in_cycle} ngày)")
    if profit_ratio < MIN_PROFIT_RATIO:
        return _no(f"lãi {profit_ratio:+.2%} chưa đạt mức tối thiểu "
                   f"{MIN_PROFIT_RATIO:.0%} — rút bây giờ sẽ reset chu kỳ "
                   f"{MIN_CLAIM_CYCLE_DAYS} ngày để lấy một khoản nhỏ")
    if int(open_positions) > 0:
        return _no(f"còn {open_positions} vị thế đang mở — FTMO yêu cầu đóng hết "
                   f"trước khi claim. Đợi vị thế đóng tự nhiên theo luật thoát "
                   f"của chiến lược, KHÔNG đóng ép chỉ để rút tiền")

    return RewardSuggestion(
        eligible=True, days_in_cycle=days_in_cycle, days_remaining=0,
        profit_usd=profit_usd, profit_ratio=profit_ratio,
        trader_payout_usd=payout, open_positions=0, reason="", should_notify=True)


def mark_first_trading_day(day: str) -> None:
    """Đánh dấu ngày giao dịch đầu tiên của chu kỳ. Idempotent.

    Chỉ ghi khi CHƯA có mốc: chu kỳ chạy từ lệnh đầu tiên, và mọi lệnh sau đó
    không dời mốc. Ghi đè bằng ngày mới nhất sẽ đẩy mốc lùi mãi và chu kỳ 14
    ngày không bao giờ hoàn thành.
    """
    if not day:
        return
    with _lock:
        st = _read()
        if st.get("cycle_start_day"):
            return
        st["cycle_start_day"] = str(day)
        _write(st)
        log(f"💰 [REWARD] Chu kỳ rút tiền bắt đầu {day} — đủ điều kiện claim sau "
            f"{MIN_CLAIM_CYCLE_DAYS} ngày.")


def start_new_cycle(day: Optional[str] = None) -> None:
    """Bắt đầu chu kỳ mới sau khi ĐÃ RÚT. Gọi thủ công khi payout hoàn tất."""
    with _lock:
        st = _default_state()
        st["cycle_start_day"] = str(day) if day else None
        _write(st)
        log(f"💰 [REWARD] Bắt đầu chu kỳ rút tiền mới (mốc {day or 'chờ lệnh đầu'}).")


def _should_notify(st: Dict[str, Any], suggestion: RewardSuggestion,
                   today: str) -> bool:
    """Có gửi email lúc này không — lọc trùng lặp, KHÔNG đổi kết luận đủ/chưa đủ.

    Hai lớp lọc:
      1. Cooldown ngày: không nhắc lại trong `RESUGGEST_COOLDOWN_DAYS` ngày.
      2. Mức lãi: chỉ nhắc lại khi lãi đã tăng thêm ít nhất 1 điểm phần trăm so
         với lần nhắc trước — nếu không thì email thứ hai không mang tin gì mới.
    """
    if not suggestion.eligible:
        return False
    last_day = st.get("last_suggested_day")
    if last_day:
        if _days_between(last_day, today) < RESUGGEST_COOLDOWN_DAYS:
            return False
        previous_ratio = float(st.get("last_suggested_profit") or 0.0)
        if suggestion.profit_ratio <= previous_ratio + 0.01:
            return False
    return True


def check(equity: float, *, open_positions: int,
          send_email: bool = True) -> RewardSuggestion:
    """Điểm vào DUY NHẤT cho hệ thống live. KHÔNG BAO GIỜ raise.

    Trả về `RewardSuggestion` để log/GUI dùng. Caller KHÔNG được dùng kết quả
    này để chặn bất cứ thứ gì — xem ràng buộc ở đầu file.
    """
    try:
        from src.python.core.infra import ftmo

        st_ftmo = ftmo._read_state()
        today = ftmo.trading_day().isoformat()
        with _lock:
            st = _read()

        suggestion = evaluate(
            equity,
            initial_capital=ftmo.initial_balance(st_ftmo),
            phase=str(st_ftmo.get("phase") or ftmo.PHASE_CHALLENGE),
            open_positions=int(open_positions or 0),
            first_trading_day=st.get("cycle_start_day"),
            today=today)

        if not (send_email and _should_notify(st, suggestion, today)):
            return suggestion

        _send_suggestion_email(suggestion, equity)
        with _lock:
            st = _read()
            st["last_suggested_day"] = today
            st["last_suggested_profit"] = suggestion.profit_ratio
            st["suggest_count"] = int(st.get("suggest_count") or 0) + 1
            _write(st)
        log(f"💰 [REWARD] {suggestion.summary}")
        return suggestion
    except Exception as e:
        # Nuốt MỌI lỗi. Module phụ không được phép làm gãy chu kỳ giao dịch.
        log_error(f"⚠️ [REWARD] lỗi khi đánh giá cơ hội rút tiền (bỏ qua): {e}")
        return RewardSuggestion(False, 0, MIN_CLAIM_CYCLE_DAYS, 0.0, 0.0, 0.0,
                                int(open_positions or 0), reason=f"lỗi: {e}")


def _send_suggestion_email(s: RewardSuggestion, equity: float) -> None:
    """Email gợi ý rút tiền. Fail-soft — mất email không ảnh hưởng gì."""
    try:
        from src.python.utils.alerts import send_alert

        text = (
            f"ĐỦ ĐIỀU KIỆN RÚT LỢI NHUẬN (FTMO Claim)\n\n"
            f"  Equity hiện tại   : ${equity:,.2f}\n"
            f"  Lãi gộp           : ${s.profit_usd:,.2f} ({s.profit_ratio:+.2%})\n"
            f"  Bạn nhận ({PROFIT_SPLIT:.0%})     : ${s.trader_payout_usd:,.2f}\n"
            f"  Chu kỳ            : {s.days_in_cycle} ngày "
            f"(tối thiểu {MIN_CLAIM_CYCLE_DAYS})\n"
            f"  Vị thế đang mở    : {s.open_positions}\n\n"
            f"Các bước tiếp theo:\n"
            f"  1. Vào FTMO Client Area -> Payout.\n"
            f"  2. FTMO xét duyệt 1-2 ngày làm việc.\n"
            f"  3. Sau khi nhận tiền, chạy `ftmo_reward.start_new_cycle()` để "
            f"đếm lại chu kỳ 14 ngày.\n\n"
            f"Đây là GỢI Ý, không phải lệnh. Bot không tự rút và không đổi hành "
            f"vi giao dịch vì email này.")

        html = (
            f"<b>💰 Đủ điều kiện rút lợi nhuận (FTMO Claim)</b><br><br>"
            f"<table style='border-collapse:collapse'>"
            f"<tr><td style='padding:6px 12px'>Equity hiện tại</td>"
            f"<td style='padding:6px 12px'><b>${equity:,.2f}</b></td></tr>"
            f"<tr style='background:#f8f9fa'><td style='padding:6px 12px'>Lãi gộp</td>"
            f"<td style='padding:6px 12px'><b style='color:#16a34a'>"
            f"${s.profit_usd:,.2f} ({s.profit_ratio:+.2%})</b></td></tr>"
            f"<tr><td style='padding:6px 12px'>Bạn nhận ({PROFIT_SPLIT:.0%})</td>"
            f"<td style='padding:6px 12px'><b style='color:#16a34a'>"
            f"${s.trader_payout_usd:,.2f}</b></td></tr>"
            f"<tr style='background:#f8f9fa'><td style='padding:6px 12px'>Chu kỳ</td>"
            f"<td style='padding:6px 12px'>{s.days_in_cycle} ngày "
            f"(tối thiểu {MIN_CLAIM_CYCLE_DAYS})</td></tr>"
            f"<tr><td style='padding:6px 12px'>Vị thế đang mở</td>"
            f"<td style='padding:6px 12px'>{s.open_positions}</td></tr></table>"
            f"<br><i>Đây là GỢI Ý. Bot không tự rút tiền và không đổi hành vi "
            f"giao dịch vì email này.</i>")

        send_alert("ftmo_reward_claim",
                   f"💰 Đủ điều kiện rút ${s.trader_payout_usd:,.0f} từ FTMO",
                   text, body_html=html)
    except Exception as e:
        log_error(f"⚠️ [REWARD] gửi email gợi ý rút tiền lỗi (bỏ qua): {e}")


def reset_for_test(state_file: Optional[Path] = None) -> None:
    """Dùng trong test: trỏ state sang file tạm."""
    global _STATE_FILE
    with _lock:
        _STATE_FILE = state_file
