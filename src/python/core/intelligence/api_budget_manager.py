# -*- coding: utf-8 -*-
"""`api_budget_manager.py` — Quản lý ngân sách API thích ứng.

Tầng thứ BA của Regime Intelligence, theo đề xuất của người dùng:

    Market Regime  (thị trường đang ở pha nào — LLM macro)
        ↓
    Time Regime    (đang là khung giờ nào — shared/regime_taxonomy)
        ↓
    API Regime     (có đáng tiêu một lời gọi API lúc này không — module này)

Câu hỏi module này trả lời KHÔNG phải "bây giờ là mấy giờ?" mà là
**"hiện tại có đáng để tiêu tốn một API call không?"**


VÌ SAO CẦN — SỐ LIỆU THỰC ĐO
-----------------------------------
Mỗi chu kỳ `macro_sentiment_worker.run_once()` tiêu khoảng 8 lời gọi API:
3 nguồn tin (Finnhub / NewsAPI / Alpha Vantage) + 4 chuyên gia L1 chạy song song
(Gemini / Groq / OpenRouter / GitHub) + 1 Chairman L2. Chu kỳ cố định 5 phút
(`macro_sentiment_scheduler.DEFAULT_REFRESH_MINUTES`) -> 288 lượt/ngày ->
**~2.300 lời gọi API mỗi ngày**, phân bổ ĐỀU trong khi thanh khoản thì không hề
đều: 13/24 giờ rơi vào ASIAN_QUIET + DEAD_ZONE.

⚠️ MODULE NÀY KẾ THỪA TỪ HỆ XAUUSD VÀ HIỆN KHÔNG CÓ CALLER PRODUCTION ở hệ
Forex: bộ máy LLM hai tầng mà nó cấp ngân sách đã bị thay bằng `ai/news_guard.py`
một tầng, và cổng tin đó mặc định TẮT. Giữ lại để không phá import kế thừa;
đừng dựng luật mới trên nó mà chưa nối lại nguồn tiêu API.

Chi phí đó có thật: OpenRouter free tier 50 request/ngày (đã phải dựng
`OPENROUTER_DAILY_LIMIT` + `OPENROUTER_L1_DAILY_CAP` để chặn tay), và
`api_key_pool` đã phải học cách đánh dấu key hết quota theo NGÀY.


TẤT ĐỊNH, KHÔNG DÙNG AI ĐỂ QUYẾT ĐỊNH
--------------------------------------
Đây là quyết định thiết kế có chủ đích. Dùng một lời gọi LLM để quyết định
"có nên gọi LLM không" thì tự triệt tiêu mục đích tiết kiệm, thêm một điểm lỗi
vào đường chạy live, và làm chính sách không backtest được (kết quả không tái lập).
Toàn bộ chính sách ở đây là hàm thuần trên các con số quan sát được — vẫn
"adaptive" đúng nghĩa (tự điều chỉnh theo trạng thái), nhưng kiểm chứng được
từng nhánh và tái lập 100%.


FAIL-OPEN TUYỆT ĐỐI
-------------------
Mọi lỗi trong module này -> `should_call=True` (cho gọi như cũ). KHÔNG BAO GIỜ
fail-closed. Lý do cụ thể chứ không phải nguyên tắc suông: nếu tầng macro bị bỏ
đói, `macro_state.json` sẽ cũ đi, `get_macro_state()` trả SAFE_DEFAULT_STATE, và
`regime_multiplier_for_strategy()` bị ghim 1.0 cho CẢ 8 chiến lược. Một module
tiết kiệm chi phí tuyệt đối không được phép tạo ra rủi ro cho logic giao dịch.


BẤT BIẾN AN TOÀN (có test bám từng cái)
----------------------------------------
1. Cửa sổ tin tác động mạnh (NFP/FOMC/CPI/ECB/BOE, ±30' quanh giờ công bố) LUÔN
   nâng lên CRITICAL — không bao giờ bị tiết kiệm bỏ qua.
2. Có vị thế mở đang ở gần SL/TP -> CRITICAL.
3. Có bất kỳ vị thế mở nào -> tối thiểu BALANCED.
4. Regime bị Smart Veto siết (CRISIS_SHOCK / TIER1_WHIPSAW / DATA_WHIPSAW) ->
   GHIM ở BALANCED. Bản đầu ép "tối thiểu ACTIVE" là bẫy tự khuếch đại — xem
   lập luận tại `classify_api_regime()`.
5. Hết ngân sách ngày CHỈ hạ được xuống ECONOMY, KHÔNG bao giờ chặn CRITICAL.


ĐO TỪ LOG LIVE — VÌ SAO PHẢI SỬA TIẾP
--------------------------------------------
Bản đầu chạy thật cho khoảng cách 5m26s liên tục (= 300s + ~26s gọi API), tức
~265 lượt/ngày, gần đúng nhịp cố định CŨ. Ba nguyên nhân, đã sửa cả ba:

1. `TIER1_WHIPSAW` giữ 5 chu kỳ liên tiếp -> luôn ép ACTIVE (bất biến 4 ở trên).
2. Backoff "dữ liệu không đổi" gần như không bao giờ chạy: fingerprint so KHỚP
   TUYỆT ĐỐI, nhưng LLM nhiễu ±0.05 giữa hai lần chấm cùng bộ tin
   (-0.25 -> -0.20 -> -0.30) nên chuỗi trùng bị reset liên tục.
   -> `UNCHANGED_BACKOFF_AFTER` 2 -> 1, và fingerprint lượng tử hoá về bước 0.1.
3. Lãng phí lớn nhất KHÔNG phải số chu kỳ mà là gửi lại đúng bộ tin cũ cho 4 L1
   + 1 Chairman. -> `sentiment_worker` giờ bỏ HẲN lời gọi LLM khi bộ headline
   không đổi (xem `headlines_fingerprint` ở module đó).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.python.shared.regime_taxonomy import (
    TIME_REGIME_VI,
    classify_time_regime,
    time_regime_activity,
)
from src.python.utils.logger import log

# --------------------------------------------------------------- API Regime
API_ECONOMY = "ECONOMY"
API_BALANCED = "BALANCED"
API_ACTIVE = "ACTIVE"
API_CRITICAL = "CRITICAL"

API_REGIME_LABELS = (API_ECONOMY, API_BALANCED, API_ACTIVE, API_CRITICAL)
_API_REGIME_RANK = {name: i for i, name in enumerate(API_REGIME_LABELS)}

# Khoảng cách TỐI THIỂU giữa 2 lời gọi thật, theo API Regime (giây).
#
# Giãn toàn bộ bảng theo yêu cầu user ("tối ưu việc call api, tránh
# dùng quá nhiều TRƯỚC khi vào các phiên cao điểm"). 
# Bảng quy về giờ GMT+7: 
# - 00-13h = 30-60'
# - London 15-19h = 30'
# - overlap 19-23h = 10'
# - 23h = 30'
# - "10 phút là mức nhỏ nhất" khi đang có lệnh mở.
#
#   bậc        khung giờ GMT+7
#   ECONOMY    01:00-14:00 (vùng chết + phiên Á)
#   BALANCED   14:00-19:00 London, 23:00-01:00 NY-only
#   ACTIVE     19:00-23:00 chồng lấn London–NY
#   CRITICAL   cửa sổ tin lớn (xem lập luận riêng bên dưới)
#
# ACTIVE: Bậc này không chỉ dùng cho khung giờ, ACTIVE cũng là SÀN của hai
# đường leo thang — biến động thực tế bất thường (`volatility_spike`, bất biến
# 4b) và vị thế mở với consumer nhạy exit (bất biến 3). 
#
# VÌ SAO GIÃN ĐƯỢC MÀ KHÔNG MẤT GÌ — lập luận theo NGƯỜI TIÊU THỤ, không theo cảm
# giác "giờ này quan trọng": consumer duy nhất đang nối vào đây là
# `macro_sentiment_worker` -> `macro_state.json`, và dữ liệu đó CHỈ nuôi sizing
# LỆNH MỚI (`portfolio_allocation.regime_multiplier`) + Smart Veto. Mọi chiến
# lược live đang chạy đều quyết định trên bar H1/H4 — tức có tối đa 1 quyết định
# mỗi 60 phút, và với 2 chiến lược PA mới thì mỗi 4 giờ. Làm mới macro mỗi 5 phút
# để phục vụ một quyết định mỗi 4 giờ là chi tiêu thuần: 47/48 lần làm mới bị ghi
# đè trước khi có ai đọc tới. Nhịp 10' ở giờ cao điểm vẫn NHANH HƠN nhịp ra quyết
# định của mọi chiến lược đang chạy.
#
# Không có chiến lược M5 nào đang live nên nhánh "Smart Veto tắt M5" cũng không
# cần dữ liệu tươi theo phút.
#
# CRITICAL: Bậc này là KHOẢN CHI LỚN NHẤT của cả thiết kế. Cửa sổ
# `macro_event_guard` là ±30' quanh mỗi tin -> 1 giờ/tin. Ngày có 3 tin lớn
# (CPI + 2 phát biểu Fed) = 3 giờ ở CRITICAL: 90 chu kỳ, NHIỀU HƠN toàn bộ
# 21 giờ còn lại cộng lại (~39). Trong đúng cửa sổ đó `macro_event_guard`
# đang CHẶN vào lệnh mới — mà macro_state chỉ nuôi lệnh mới — nên dữ liệu
# siêu tươi lúc đó gần như không có người dùng; giá trị thật là có một bản
# đọc mới NGAY KHI cửa sổ chặn mở ra. CRITICAL vẫn là bậc DUY NHẤT nhanh hơn
# mức sàn của user.
MIN_INTERVAL_SECONDS = {
    API_ECONOMY:  3600.0,   # 60'
    API_BALANCED: 1800.0,   # 30'
    API_ACTIVE:    900.0,   # 15'
    API_CRITICAL:  300.0,   # 5'
}

# Ngưỡng điểm hoạt động (Time Regime) -> API Regime nền.
_ACTIVITY_TO_REGIME = (
    (0.75, API_ACTIVE),      # NY_OVERLAP 1.00
    (0.50, API_BALANCED),    # LONDON 0.70, NY_ONLY 0.65
    (0.00, API_ECONOMY),     # ASIAN_QUIET 0.25, DEAD_ZONE 0.10
)

# Regime mà `sentiment_worker` Smart Veto ĐÃ siết giao dịch (tắt M5 / giảm 50% H1
# / tắt hẳn trend dài). Khi ở các trạng thái này, nhịp gọi API được GHIM ở
# BALANCED — xem lập luận đầy đủ tại chỗ dùng trong `classify_api_regime()`.
_VETO_THROTTLED_REGIMES = {"CRISIS_SHOCK", "TIER1_WHIPSAW", "DATA_WHIPSAW"}

# Vị thế coi là "gần điểm thoát" khi còn <= 25% quãng đường tới SL hoặc TP.
NEAR_EXIT_FRACTION = 0.25

# Dùng hết >= tỉ lệ này ngân sách ngày -> ép ECONOMY (trừ CRITICAL).
BUDGET_PRESSURE_RATIO = 0.80

# Dữ liệu không đổi liên tiếp N lần -> nới khoảng cách gọi (hệ số nhân).
# Người dùng nêu rõ "mức độ thay đổi của dữ liệu kể từ lần gọi trước" là một yếu
# tố quyết định. Gọi lại API để nhận về đúng bộ headline cũ là chi phí thuần.
#
# Với ngưỡng cao hơn, backoff gần như không bao giờ kích hoạt vì LLM nhiễu
# ±0.05 giữa hai lần chấm CÙNG bộ tin làm chuỗi trùng bị reset. Ngưỡng 1
# nghĩa là "trùng một lần là đã đủ tín hiệu để nới" — an toàn, vì nới chỉ làm
# giãn cách dài hơn chứ không bao giờ bỏ qua cửa sổ tin lớn (CRITICAL không bị nới).
UNCHANGED_BACKOFF_AFTER = 1
UNCHANGED_BACKOFF_MAX = 3.0

# Nhịp TICK của vòng lặp gọi tới đây. Tách khỏi khoảng-cách-gọi CÓ CHỦ ĐÍCH:
# tick rẻ (không tốn API) nên giữ dày để không bỏ lỡ thời điểm một cửa sổ tin
# mở ra; chỉ LỜI GỌI mới bị siết. Nếu tick cũng thưa theo ECONOMY thì bất biến
# số 1 (không bỏ lỡ tin lớn) sẽ không giữ được.
TICK_SECONDS = 60.0


@dataclass(frozen=True)
class BudgetDecision:
    """Kết quả một lần hỏi "có nên gọi API lúc này không"."""
    should_call: bool
    api_regime: str
    reason: str
    min_interval_seconds: float
    time_regime: str = ""
    seconds_since_last: Optional[float] = None
    escalations: tuple = field(default_factory=tuple)

    def as_log(self) -> str:
        esc = f" [{'+'.join(self.escalations)}]" if self.escalations else ""
        return (f"{self.api_regime}{esc} / {self.time_regime} — {self.reason} "
                f"(giãn cách tối thiểu {self.min_interval_seconds / 60:.0f}')")


def _max_regime(a: str, b: str) -> str:
    return a if _API_REGIME_RANK.get(a, 0) >= _API_REGIME_RANK.get(b, 0) else b


def _base_regime_from_time(now_utc: Optional[datetime]) -> str:
    activity = time_regime_activity(now_utc)
    for threshold, regime in _ACTIVITY_TO_REGIME:
        if activity >= threshold:
            return regime
    return API_ECONOMY


def _prime_on_session_open(last_call_ts: Optional[float],
                           now_utc: Optional[datetime]) -> tuple:
    """(có_nên_mồi, mô_tả) — cho gọi NGAY một lần khi vừa bước sang một Time
    Regime SÔI ĐỘNG HƠN khung của lần gọi trước.

    Đây là mảnh ghép làm cho việc giãn nhịp ở giờ thấp điểm trở nên
    an toàn, và nó trả lời trực tiếp yêu cầu user — "tránh dùng quá nhiều TRƯỚC
    khi vào các phiên cao điểm": nếu 13:00-14:00 GMT+7 (vùng chết) chạy nhịp 60'
    thì đúng lúc London mở 14:00, `macro_state.json` có thể đã cũ 59 phút, và
    lệnh đầu phiên sẽ được size bằng bức tranh macro của phiên Á. Nghịch lý: càng
    tiết kiệm ở giờ rẻ thì càng dễ vào giờ đắt với dữ liệu cũ.

    Mồi ở ĐÚNG ranh giới phiên giải quyết việc đó với chi phí gần bằng không:
    trong bảng khung giờ hiện tại chỉ có 3 lần chuyển LÊN mỗi ngày (vùng chết ->
    Á 06:00, vùng chết -> London 14:00, London -> chồng lấn 19:00), tức tối đa
    +3 chu kỳ/ngày. Chuyển XUỐNG (London -> NY-only -> vùng chết) KHÔNG mồi: dữ
    liệu cũ đi vào lúc thanh khoản cạn dần không gây hại.

    KHÔNG GIỮ STATE: suy khung của lần gọi trước từ chính `last_call_ts`, nên
    hàm thuần, tái lập 100% và không thêm file/biến toàn cục nào. Tự nhiên chỉ
    bắn ĐÚNG MỘT LẦN cho mỗi lần chuyển — ngay sau khi mồi, `last_call_ts` đã
    nằm trong khung mới nên điều kiện không còn đúng.
    """
    if last_call_ts is None:
        return False, ""                    # đã có nhánh "lần gọi đầu tiên" riêng
    try:
        prev_regime = classify_time_regime(
            datetime.fromtimestamp(last_call_ts, tz=timezone.utc))
        cur_regime = classify_time_regime(now_utc)
        if prev_regime == cur_regime:
            return False, ""
        if time_regime_activity_of(cur_regime) <= time_regime_activity_of(prev_regime):
            return False, ""
        return True, (f"vừa sang {cur_regime} (trước đó {prev_regime}) — "
                      f"mồi lại dữ liệu ở ranh giới phiên")
    except Exception:
        return False, ""                    # fail-soft: không mồi khi không chắc


def time_regime_activity_of(time_regime: str) -> float:
    """Điểm hoạt động của MỘT nhãn cho trước (khác `time_regime_activity()` của
    `regime_taxonomy` — hàm đó chấm theo thời điểm hiện tại). Mặc định 0.5 cho
    nhãn lạ, khớp quy ước fail-mềm ở nơi kia."""
    from src.python.shared.regime_taxonomy import TIME_REGIME_ACTIVITY
    return TIME_REGIME_ACTIVITY.get(time_regime, 0.5)


def time_regime_cadence_minutes(now_utc: Optional[datetime] = None) -> float:
    """Nhịp gọi API (PHÚT) ứng với khung giờ hiện tại — nền, CHƯA tính leo thang.

    Module này là owner của `MIN_INTERVAL_SECONDS`, nên số phút phải lấy từ đây —
    GUI KHÔNG được tự dựng bảng activity->phút (đó sẽ là nguồn sự thật thứ hai
    cho cùng một luật).

    Cố ý CHỈ dùng `_base_regime_from_time()` (thuần, rẻ) chứ không gọi
    `classify_api_regime()`: hàm kia đọc `data/economic_calendar_events.parquet`
    qua `macro_event_guard` và áp escalation theo vị thế/ngân sách — quá đắt cho
    một card GUI refresh liên tục, và card SESSION mô tả KHUNG GIỜ chứ không phải
    trạng thái leo thang tức thời. Nhịp THẬT có thể dày hơn con số này khi có
    escalation (cửa sổ tin, vị thế mở, volatility spike).
    """
    return MIN_INTERVAL_SECONDS[_base_regime_from_time(now_utc)] / 60.0


def _high_impact_window(now_utc: Optional[datetime]) -> tuple:
    """(có_trong_cửa_sổ, mô_tả). Tái dùng `macro_event_guard` — module đã đọc
    `data/economic_calendar_events.parquet` với NFP/FOMC/CPI/ECB_RATE/BOE_RATE và
    cửa sổ ±30 phút. KHÔNG dựng lịch riêng ở đây (đó sẽ là nguồn sự thật thứ hai
    cho cùng một câu hỏi)."""
    try:
        from src.python.core.ai_macro import macro_event_guard
        res = macro_event_guard.check_now(now_utc)
        if res.get("blocked"):
            return True, str(res.get("reason") or "cửa sổ tin tác động mạnh")
    except Exception:
        pass                      # fail-soft: không có lịch -> không leo thang
    return False, ""


def classify_api_regime(
    *,
    now_utc: Optional[datetime] = None,
    has_open_position: bool = False,
    nearest_exit_fraction: Optional[float] = None,
    market_regime: Optional[str] = None,
    budget_used: Optional[int] = None,
    budget_limit: Optional[int] = None,
    exit_sensitive: bool = False,
    volatility_spike: bool = False,
) -> tuple:
    """Phân loại API Regime dựa trên trạng thái hiện tại.
    Trả về (api_regime, time_regime, lý_do, tuple các lần leo thang).

    `volatility_spike`: True khi biến động giá THỰC TẾ (vd tỉ lệ
    ATR ngắn hạn / nền) đang cao bất thường ngay lúc gọi — escalate tối thiểu
    lên ACTIVE, ĐỘC LẬP với giờ trong ngày và ghim Smart-Veto (bất biến 4),
    vì đây là tín hiệu THỊ TRƯỜNG THẬT không phụ thuộc lịch/LLM đã biết trước
    — dữ liệu tươi hơn giúp phát hiện SỚM nếu sentiment/regime đang đổi theo
    biến động đó. KHÔNG tự nâng lên CRITICAL (dành riêng cho lịch tin XÁC
    ĐỊNH ở bất biến 1) — vẫn bị bất biến 5 (sức ép ngân sách) ghi đè xuống
    ECONOMY như mọi tier khác trừ CRITICAL.

    `nearest_exit_fraction`: phần quãng đường CÒN LẠI tới SL/TP gần nhất,
    0.0 = đã chạm, 1.0 = còn nguyên. `None` = không biết/không có vị thế.

    `exit_sensitive`: API này có dữ liệu THẬT SỰ ảnh hưởng tới việc thoát một
    vị thế ĐANG MỞ hay không. Mặc định False, và đây là mặc định ĐÚNG:

      - `macro_sentiment_worker` (consumer lớn nhất): `macro_state.json` chỉ được
        đọc bởi `portfolio_allocation.py:246` (`regime_multiplier` -> sizing lệnh
        MỚI), snapshot lúc tạo lệnh trong `order_state_machine`, và GUI.
        KHÔNG đường thoát lệnh nào đọc nó — SL/TP nằm trên
        broker, còn BE/trailing/timeout là logic thuần trong `_manage()` của từng
        chiến lược. Vậy "vị thế sắp chạm SL/TP" KHÔNG làm dữ liệu macro có giá
        trị hơn.
      - `ai_position_controller.evaluate_position_management()`: phát trực tiếp
        HOLD/CLOSE/PARTIAL_CLOSE/TRAIL_SL cho vị thế đang mở. Consumer NÀY mới
        đúng là exit-sensitive -> truyền True.

    VÌ SAO PHẢI TÁCH (đo được, không phải lý thuyết): mô phỏng 1 ngày cho thấy
    nếu áp escalation exit cho MỌI consumer, kịch bản "vị thế nằm gần SL/TP suốt
    ngày" (rất thường gặp với H4/D1) đẩy lên 288 chu kỳ/ngày ở bảng nhịp
    (720 ở bảng cũ) — vẫn ĐẮT HƠN chế độ cố định cũ. Một module sinh ra
    để tiết kiệm mà tốn hơn là hỏng.

    CẢNH BÁO KHI WIRE CONSUMER exit_sensitive: con số trên vẫn đúng với
    `exit_sensitive=True`. Hiện `ai_position_controller` KHÔNG chạy theo lịch cố
    định (nó chạy theo chu kỳ engine, chỉ khi có vị thế mở) nên chưa nối vào đây.
    Trước khi nối bất kỳ consumer exit-sensitive nào, phải đối chiếu
    `MIN_INTERVAL_SECONDS[CRITICAL]` với nhịp nền THẬT của consumer đó — nếu nhịp
    nền đã thưa hơn 5 phút thì module này sẽ làm nó DÀY LÊN chứ không tiết kiệm.
    """
    time_regime = classify_time_regime(now_utc)
    regime = _base_regime_from_time(now_utc)
    reason = TIME_REGIME_VI.get(time_regime, time_regime)
    escalations = []

    # --- bất biến 4: regime bị Smart Veto siết -> GHIM ở BALANCED --------
    # Log live cho thấy bản đầu tiên ép "tối thiểu ACTIVE" là một
    # BẪY TỰ KHUẾCH ĐẠI:
    #
    #   TIER1_WHIPSAW giữ 5 chu kỳ liên tiếp (13:00 -> 13:22) -> luôn ép ACTIVE
    #   -> khoảng cách thật 5m26s (= 300s + ~26s gọi API), tức ~265 lượt/ngày,
    #      gần đúng nhịp cố định CŨ, mất gần hết phần tiết kiệm.
    #
    # Nhưng chính những regime đó là lúc `sentiment_worker` Smart Veto đã TẮT M5
    # và GIẢM 50% H1 — hệ thống đã tự quyết định giao dịch ÍT NHẤT. Việc
    # đốt token NHIỀU NHẤT đúng lúc đó: hai cơ chế chỉ ngược chiều nhau.
    #
    # Lập luận cho việc ghim BALANCED (10') thay vì hạ hẳn xuống ECONOMY (60'):
    # macro_state chỉ nuôi sizing lệnh MỚI, mà lệnh mới đang bị veto — nên dữ
    # liệu tươi hơn gần như không thêm giá trị. Điều VẪN cần là phát hiện lúc
    # regime THOÁT khỏi trạng thái bị veto để giao dịch được nối lại; 10 phút là
    # đủ nhanh cho việc đó. Ghim hai đầu (không nhanh hơn, không chậm hơn) nên
    # nó vẫn được theo dõi cả trong DEAD_ZONE.
    #
    # Cửa sổ tin tác động mạnh vẫn nâng lên CRITICAL ở dưới — đó mới là thứ thật
    # sự cần phản ứng nhanh, và nó dựa trên LỊCH có thật (`macro_event_guard`)
    # chứ không phải nhãn do chính vòng lặp này sinh ra.
    if market_regime and str(market_regime).upper() in _VETO_THROTTLED_REGIMES:
        if regime != API_BALANCED:
            escalations.append(f"regime {market_regime} bị Smart Veto siết "
                               f"-> ghim {API_BALANCED}")
        regime = API_BALANCED

    # --- bất biến 4b: biến động thực tế bất thường -> tối thiểu ACTIVE --
    # Đặt SAU bất biến 4 (ghim BALANCED) có chủ đích: cho phép thoát khỏi
    # ghim đó khi giá đang giật mạnh THẬT (vd DXY) dù regime Smart-Veto
    # chưa đổi nhãn — LLM regime cập nhật theo tin, có thể trễ hơn giá.
    if volatility_spike:
        if _API_REGIME_RANK[regime] < _API_REGIME_RANK[API_ACTIVE]:
            escalations.append("biến động thực tế bất thường (ATR spike)")
        regime = _max_regime(regime, API_ACTIVE)

    # --- bất biến 3: có vị thế mở ---------------------------------------
    # SÀN HAI MỨC:
    #   - Consumer nhạy exit (vd `ai_position_controller` phát HOLD/CLOSE/TRAIL
    #     cho vị thế đang mở) -> sàn ACTIVE = 10', đúng con số user yêu cầu.
    #   - Consumer KHÔNG nhạy exit (macro worker) -> sàn BALANCED = 30'.
    #     Không đường thoát lệnh nào đọc `macro_state.json` — SL/TP
    #     nằm trên broker, BE/trailing/timeout là logic thuần trong `_manage()` của
    #     từng chiến lược và chạy mỗi tick, KHÔNG tốn API. Nên với vị thế đang mở,
    #     làm mới macro 10' thay vì 30' không giúp gì cho chính vị thế đó; nó chỉ
    #     làm sizing của lệnh TIẾP THEO tươi hơn.
    #
    # Ép 10' phẳng sẽ đắt thật chứ không chỉ trên lý thuyết: chiến lược H4 giữ
    # lệnh nhiều ngày nên "đang có vị thế mở" gần như luôn đúng, tức 10' sẽ áp cả
    # 13 giờ vùng chết + phiên Á -> 144 chu kỳ/ngày.
    # Sàn 30' cho nhánh này chỉ thêm ~13 chu kỳ/ngày so với 51 khi rảnh tay.
    if has_open_position:
        floor = API_ACTIVE if exit_sensitive else API_BALANCED
        if _API_REGIME_RANK[regime] < _API_REGIME_RANK[floor]:
            escalations.append(f"đang có vị thế mở -> tối thiểu {floor}")
        regime = _max_regime(regime, floor)

    # --- bất biến 2: vị thế sắp chạm SL/TP (CHỈ với consumer nhạy exit) -
    if (exit_sensitive and has_open_position
            and nearest_exit_fraction is not None
            and nearest_exit_fraction <= NEAR_EXIT_FRACTION):
        escalations.append(f"vị thế cách điểm thoát {nearest_exit_fraction:.0%}")
        regime = API_CRITICAL

    # --- bất biến 1: cửa sổ tin lớn (ưu tiên cao nhất) ------------------
    in_news, news_reason = _high_impact_window(now_utc)
    if in_news:
        escalations.append("tin tác động mạnh")
        regime = API_CRITICAL
        reason = news_reason or reason

    # --- bất biến 5: sức ép ngân sách, KHÔNG hạ được CRITICAL -----------
    if (budget_limit and budget_used is not None
            and budget_used >= budget_limit * BUDGET_PRESSURE_RATIO
            and regime != API_CRITICAL):
        escalations.append(f"ngân sách {budget_used}/{budget_limit}")
        regime = API_ECONOMY

    return regime, time_regime, reason, tuple(escalations)


def decide(
    *,
    last_call_ts: Optional[float],
    now_ts: Optional[float] = None,
    now_utc: Optional[datetime] = None,
    has_open_position: bool = False,
    nearest_exit_fraction: Optional[float] = None,
    market_regime: Optional[str] = None,
    budget_used: Optional[int] = None,
    budget_limit: Optional[int] = None,
    unchanged_streak: int = 0,
    exit_sensitive: bool = False,
    volatility_spike: bool = False,
) -> BudgetDecision:
    """Có nên gọi API ngay bây giờ không.

    `last_call_ts`/`now_ts` là epoch giây (`time.time()`). Truyền
    `last_call_ts=None` nghĩa là chưa gọi lần nào -> LUÔN cho gọi (mồi dữ liệu).

    `volatility_spike`: xem docstring `classify_api_regime()`.

    KHÔNG raise. Bất kỳ lỗi nào -> cho gọi (xem "FAIL-OPEN" ở đầu module).
    """
    try:
        if now_ts is None:
            now_ts = (now_utc or datetime.now(timezone.utc)).timestamp()

        regime, time_regime, reason, escalations = classify_api_regime(
            now_utc=now_utc, has_open_position=has_open_position,
            nearest_exit_fraction=nearest_exit_fraction,
            market_regime=market_regime,
            budget_used=budget_used, budget_limit=budget_limit,
            exit_sensitive=exit_sensitive, volatility_spike=volatility_spike)

        min_gap = MIN_INTERVAL_SECONDS[regime]

        # Dữ liệu lặp lại nhiều lần -> nới dần, nhưng KHÔNG áp cho CRITICAL:
        # lúc có tin lớn thì "headline chưa đổi" chính là thông tin cần theo dõi.
        if regime != API_CRITICAL and unchanged_streak >= UNCHANGED_BACKOFF_AFTER:
            factor = min(UNCHANGED_BACKOFF_MAX,
                         1.0 + (unchanged_streak - UNCHANGED_BACKOFF_AFTER + 1) * 0.5)
            min_gap *= factor
            escalations = escalations + (f"dữ liệu không đổi ×{unchanged_streak}",)

        if last_call_ts is None:
            return BudgetDecision(True, regime, "lần gọi đầu tiên — mồi dữ liệu",
                                  min_gap, time_regime, None, escalations)

        elapsed = max(0.0, now_ts - last_call_ts)

        # Mồi ở ranh giới phiên — xem `_prime_on_session_open()`. Đặt SAU backoff
        # "dữ liệu không đổi" và TRƯỚC phép so giãn cách, vì mục đích của nó đúng
        # là bỏ qua giãn cách đó đúng một lần. KHÔNG mồi khi đang bị sức ép ngân
        # sách (bất biến 5): lúc quota gần cạn thì giữ lại phần còn cho cửa sổ tin
        # (CRITICAL) đáng hơn là làm tươi dữ liệu ở ranh giới phiên.
        budget_pressed = any(e.startswith("ngân sách") for e in escalations)
        if not budget_pressed:
            prime, prime_reason = _prime_on_session_open(last_call_ts, now_utc)
            if prime and elapsed < min_gap:
                return BudgetDecision(True, regime, prime_reason, min_gap,
                                      time_regime, elapsed,
                                      escalations + ("mồi đầu phiên",))

        if elapsed >= min_gap:
            return BudgetDecision(True, regime, reason, min_gap,
                                  time_regime, elapsed, escalations)
        return BudgetDecision(
            False, regime,
            f"mới gọi {elapsed / 60:.1f}' trước, chờ đủ {min_gap / 60:.0f}'",
            min_gap, time_regime, elapsed, escalations)
    except Exception as e:                                  # pragma: no cover
        log(f"[API_BUDGET] Lỗi khi quyết định (fail-open -> vẫn gọi): {e}")
        return BudgetDecision(True, API_ACTIVE, f"fail-open sau lỗi: {e}",
                              MIN_INTERVAL_SECONDS[API_ACTIVE])


# --------------------------------------------------------------- quan sát
# Đếm trong bộ nhớ tiến trình. CỐ Ý không ghi file: đây là số liệu vận hành để
# đọc trên GUI/log, không phải sổ sách giao dịch — thêm một file state nữa vào
# `LIVE_DIR` là thêm một thứ phải đồng bộ giữa các tài khoản (xem bài học đường
# dẫn macro_state 28/07). Muốn lưu lâu dài thì đẩy qua observability sẵn có.
_stats = {"calls_made": 0, "calls_skipped": 0, "by_regime": {}}


def record(decision: BudgetDecision) -> None:
    """Ghi nhận một quyết định để đo hiệu quả thật thay vì ước lượng."""
    try:
        key = "calls_made" if decision.should_call else "calls_skipped"
        _stats[key] += 1
        slot = _stats["by_regime"].setdefault(
            decision.api_regime, {"made": 0, "skipped": 0})
        slot["made" if decision.should_call else "skipped"] += 1
    except Exception:
        pass


def stats() -> dict:
    """Bản sao số liệu tích luỹ (made/skipped tổng và theo API Regime)."""
    total = _stats["calls_made"] + _stats["calls_skipped"]
    saved_pct = (_stats["calls_skipped"] / total * 100.0) if total else 0.0
    return {
        "calls_made": _stats["calls_made"],
        "calls_skipped": _stats["calls_skipped"],
        "saved_pct": round(saved_pct, 1),
        "by_regime": {k: dict(v) for k, v in _stats["by_regime"].items()},
    }


def reset_stats_for_test() -> None:
    _stats["calls_made"] = 0
    _stats["calls_skipped"] = 0
    _stats["by_regime"] = {}
