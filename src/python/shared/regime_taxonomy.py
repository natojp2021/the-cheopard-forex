"""Từ vựng Regime duy nhất của hệ thống (Regime Taxonomy).

Cung cấp source of truth (SSOT) cho các định nghĩa regime, bao gồm:
1. Regime Định Lượng (Quantitative Regime): Dựa trên bar lịch sử (Volatility x Trend).
2. LLM Macro Regime: Ánh xạ trạng thái vĩ mô hiện tại từ AI sang trục Trend chung.
3. Time Regime (Phiên giao dịch): Định nghĩa các phiên giao dịch dựa trên múi giờ London.

Quy định tầng: Đặt tại `shared/` vì đây là các hàm thuần (pure functions) dựa trên ngưỡng hằng số,
không side-effect, phục vụ chung cho cả Live, Core Intelligence và Research.
Lưu ý: Các ngưỡng định lượng ở đây chỉ dùng để chấm điểm/báo cáo, KHÔNG quyết định Sizing Live.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd

# ---------------------------------------------------------------- từ vựng nhãn
# Trục trend — DÙNG CHUNG cho cả hai bộ phân loại (định lượng + LLM macro).
TREND_RANGING = "ranging"
TREND_NORMAL = "normal"
TREND_TRENDING = "trending"
TREND_LABELS = (TREND_RANGING, TREND_NORMAL, TREND_TRENDING)

# Trục volatility — chỉ bộ định lượng dùng (LLM không phát nhãn volatility riêng).
VOL_LOW = "low"
VOL_NORMAL = "normal"
VOL_HIGH = "high"
VOL_LABELS = (VOL_LOW, VOL_NORMAL, VOL_HIGH)

# Nhãn "không xác định được" khi macro state thiếu/hỏng/stale (fail-soft).
TREND_NEUTRAL_SENTINEL = "NEUTRAL"

# Cặp trend đối lập — dùng để phân biệt "mismatch" với "chỉ là không khớp".
OPPOSITE_TREND = {TREND_TRENDING: TREND_RANGING, TREND_RANGING: TREND_TRENDING}

# Bảng ánh xạ chuỗi regime của LLM (ghi trong data/live/macro_state.json bởi
# `core/ai_macro/macro_sentiment_worker.py`) về trục trend chung ở trên. Đây là SSOT của
# phép ánh xạ đó — `core/ai_macro/regime_detector.py` đọc từ đây, KHÔNG tự lặp.
# Mọi chuỗi LLM không có trong bảng -> TREND_NORMAL (gồm ROUTINE_NORMAL,
# CRISIS_SHOCK, DATA_WHIPSAW, TIER1_WHIPSAW).
_LLM_REGIME_TO_TREND = {
    "STRUCTURAL_TREND": TREND_TRENDING,
    "DIRECTIONAL_SURGE": TREND_TRENDING,
    "CONFLICTING_NOISE": TREND_RANGING,
    "CHOPPY_CONFLICT": TREND_RANGING,
    "LOW_LIQUIDITY": TREND_RANGING,
    "PRE_EVENT_LULL": TREND_RANGING,
    "HOLIDAY_THIN": TREND_RANGING,
}


# Nghĩa tiếng Việt của từng nhãn regime LLM — SSOT cho MỌI bề mặt hiển thị
# (email vào/đóng lệnh, log MRC, GUI, báo cáo labs).
LLM_REGIME_MEANING_VI = {
    "STRUCTURAL_TREND":  "Xu hướng cấu trúc — dòng tiền một chiều",
    "DIRECTIONAL_SURGE": "Bứt phá có hướng — động lượng mạnh",
    "CONFLICTING_NOISE": "Nhiễu mâu thuẫn — tin trái chiều, dễ bị quét hai đầu",
    "CHOPPY_CONFLICT":   "Giằng co — biên độ hẹp, đảo chiều liên tục",
    "LOW_LIQUIDITY":     "Thanh khoản mỏng — spread giãn, trượt giá cao",
    "PRE_EVENT_LULL":    "Lặng trước tin — thị trường chờ sự kiện",
    "HOLIDAY_THIN":      "Nghỉ lễ — thanh khoản mỏng",
    "CRISIS_SHOCK":      "Sốc khủng hoảng — biến động cực đoan",
    "TIER1_WHIPSAW":     "Whipsaw tin Tier-1 — quét hai chiều quanh tin lớn",
    "DATA_WHIPSAW":      "Whipsaw dữ liệu kinh tế",
    "ROUTINE_NORMAL":    "Bình thường — không có yếu tố vĩ mô nổi bật",
    TREND_NEUTRAL_SENTINEL: "Trung lập — chưa có dữ liệu macro tươi",
}


def llm_regime_meaning_vi(llm_regime: str) -> str:
    """Diễn giải tiếng Việt của nhãn regime, "" nếu chưa biết nhãn đó."""
    return LLM_REGIME_MEANING_VI.get((llm_regime or "").upper().strip(), "")


def map_llm_regime_to_trend(llm_regime: str) -> str:
    """Ánh xạ chuỗi regime LLM về 1 trong 3 nhãn trend chung.

    Mọi chuỗi không nằm trong bảng (ROUTINE_NORMAL, CRISIS_SHOCK, DATA_WHIPSAW,
    TIER1_WHIPSAW, hoặc chuỗi lạ) -> `TREND_NORMAL`. Đây là fail-soft có chủ
    đích: một nhãn regime lạ KHÔNG được biến thành mismatch (giảm risk 0.70×)
    chỉ vì hệ thống chưa biết nó là gì.
    """
    return _LLM_REGIME_TO_TREND.get((llm_regime or "").upper().strip(), TREND_NORMAL)


# --------------------------------------------------- Ngưỡng phân loại định lượng
# ⚠️ NGƯỠNG ĐO TRÊN XAUUSD (2015-2026, M5) — CHƯA hiệu chỉnh lại cho FX.
# Bốn con số dưới đây là phân vị thực đo của VÀNG, không phải của rổ FX. Chúng
# còn ở đây vì chúng CHỈ gắn nhãn cho báo cáo attribution/backtest và KHÔNG
# tham gia bất kỳ quyết định rủi ro hay vào lệnh nào — không chân nào trong 27
# chân đọc chúng (kiểm bằng grep, 0 caller ngoài module này).
# Nếu sau này có ai nối chúng vào một cổng thật thì PHẢI đo lại trên FX trước:
# ATR và ADX của EURUSD sống ở thang hoàn toàn khác thang của vàng.
VOL_LOW_MAX = 0.80
VOL_HIGH_MIN = 1.30
TREND_RANGING_MAX = 17.0
TREND_TRENDING_MIN = 31.0


@dataclass(frozen=True)
class Regime:
    vol: str     # VOL_LOW | VOL_NORMAL | VOL_HIGH
    trend: str   # TREND_RANGING | TREND_NORMAL | TREND_TRENDING

    @property
    def label(self) -> str:
        return f"{self.trend}_{self.vol}vol"


def classify_row(atr_regime_ratio: float, adx_m5: float) -> Optional[Regime]:
    """Phân loại từ 2 giá trị feature đã có tại thời điểm entry (nhân quả —
    caller phải đảm bảo lấy từ bar ĐÃ ĐÓNG trước/tại thời điểm quyết định,
    không phải bar tương lai). Trả None nếu thiếu dữ liệu (NaN)."""
    if not (pd.notna(atr_regime_ratio) and pd.notna(adx_m5)):
        return None
    if atr_regime_ratio <= VOL_LOW_MAX:
        vol = VOL_LOW
    elif atr_regime_ratio >= VOL_HIGH_MIN:
        vol = VOL_HIGH
    else:
        vol = VOL_NORMAL
    if adx_m5 <= TREND_RANGING_MAX:
        trend = TREND_RANGING
    elif adx_m5 >= TREND_TRENDING_MIN:
        trend = TREND_TRENDING
    else:
        trend = TREND_NORMAL
    return Regime(vol=vol, trend=trend)


def classify_at(m5: pd.DataFrame, t: pd.Timestamp) -> Optional[Regime]:
    """Tra cứu regime tại/trước thời điểm `t` trong DataFrame M5 đã có
    `atr_regime_ratio`/`adx_m5` (từ `add_core_features`) — dùng `asof` (bar
    đã đóng gần nhất <= t), không look-ahead."""
    pos = m5.index.searchsorted(t, side="right") - 1
    if pos < 0:
        return None
    row = m5.iloc[pos]
    return classify_row(row.get("atr_regime_ratio"), row.get("adx_m5"))

# =============================================================================
# TRỤC THỨ 3: EFFICIENCY RATIO + BỘ PHÂN LOẠI 6 TRẠNG THÁI (thêm 27/07/2026)
# =============================================================================
# Thêm trục Efficiency Ratio (ER) để phân tách rõ TIER1_WHIPSAW (đi lòng vòng)
# và STRUCTURAL_TREND (đi thẳng) khi cả 2 đều thuộc nhóm volatility cao.

# Ngưỡng phân vị thực đo (cùng tập dữ liệu với 2 trục trên).
ER_LOW_MAX = 0.058       # p25 — đường đi lòng vòng
ER_HIGH_MIN = 0.208      # p75 — đi thẳng
VOL_EXTREME_MIN = 2.90   # p99 atr_regime_ratio
TICK_Z_THIN = -1.20      # p05 z-điểm số tick (đã tự chuẩn hoá -> ổn định qua era)

ER_WINDOW = 48           # 48 bar M5 = 4 giờ

# Spread luôn so tương đối với trung vị trượt (rolling median) thay vì ngưỡng bp tuyệt đối
# để tránh era-bias (broker siết spread dần theo năm).
SPREAD_RATIO_WINDOW = 288    # 288 bar M5 = 1 ngày
SPREAD_RATIO_WIDE = 1.25     # p95 của spread_bp / median trượt 1 ngày

# 6 nhãn — CỐ Ý trùng tên với 6 nhãn LLM trong
# docs/research/specs/market_regime_classification.md để một ngày có thể đối
# chiếu trực tiếp "LLM nói gì" vs "giá nói gì" trên cùng bộ từ vựng.
REGIME_LABELS = (
    "CRISIS_SHOCK",
    "TIER1_WHIPSAW",
    "STRUCTURAL_TREND",
    "CONFLICTING_NOISE",
    "ROUTINE_NORMAL",
    "LOW_LIQUIDITY",
)


def efficiency_ratio(close: pd.Series, window: int = ER_WINDOW) -> pd.Series:
    """Kaufman Efficiency Ratio = |dịch chuyển ròng| / |tổng đường đi|.

    Nhân quả: chỉ dùng `close` tới bar hiện tại. Giá trị ~1 = đi thẳng tuyệt
    đối, ~0 = đi lòng vòng về chỗ cũ. Trả NaN cho `window` bar đầu.
    """
    net = (close - close.shift(window)).abs()
    path = close.diff().abs().rolling(window).sum()
    return net / path.replace(0, pd.NA)


def classify_quant_row(
    atr_regime_ratio: float,
    adx_m5: float,
    er: float,
    spread_ratio: Optional[float] = None,
    tick_z: Optional[float] = None,
) -> str:
    """Phân loại 1 bar thành 1 trong 6 nhãn (hoặc "UNKNOWN" nếu thiếu dữ liệu).

    Thứ tự xét từ NGUY HIỂM NHẤT xuống THƯỜNG NHẬT — nhãn xét sau ghi đè nhãn
    xét trước, nên `CRISIS_SHOCK` luôn thắng. Caller phải truyền giá trị từ bar
    ĐÃ ĐÓNG (xem `classify_quant_at`).

    `spread_ratio` = spread_bp / trung vị trượt 1 ngày của spread_bp (TƯƠNG ĐỐI,
    không phải bp tuyệt đối — xem khối comment ở SPREAD_RATIO_WIDE để biết vì sao
    ngưỡng tuyệt đối gây lệch era nghiêm trọng).
    """
    if not (pd.notna(atr_regime_ratio) and pd.notna(adx_m5) and pd.notna(er)):
        return "UNKNOWN"

    label = "ROUTINE_NORMAL"
    # Cạn thanh khoản: vol thấp KÈM dấu hiệu sổ lệnh mỏng (spread giãn/ít tick).
    thin = (spread_ratio is not None and pd.notna(spread_ratio)
            and spread_ratio >= SPREAD_RATIO_WIDE)
    thin = thin or (tick_z is not None and pd.notna(tick_z)
                    and tick_z <= TICK_Z_THIN)
    if atr_regime_ratio <= VOL_LOW_MAX and thin:
        label = "LOW_LIQUIDITY"
    # Nhiễu loạn: có biến động nhưng không có hướng.
    if atr_regime_ratio > VOL_LOW_MAX and adx_m5 <= TREND_RANGING_MAX \
            and er <= ER_HIGH_MIN:
        label = "CONFLICTING_NOISE"
    # Xu hướng cấu trúc: đi thẳng VÀ có lực.
    if er >= ER_HIGH_MIN and adx_m5 >= TREND_TRENDING_MIN:
        label = "STRUCTURAL_TREND"
    # Bão dữ liệu: vol cao nhưng đường đi lòng vòng (quét stop cả 2 đầu).
    if atr_regime_ratio >= VOL_HIGH_MIN and er <= ER_LOW_MAX:
        label = "TIER1_WHIPSAW"
    # Cú sốc: vol cực đoan, TA vô nghĩa.
    if atr_regime_ratio >= VOL_EXTREME_MIN:
        label = "CRISIS_SHOCK"
    return label


def add_quant_regime(m5: pd.DataFrame, close_col: str = "close") -> pd.DataFrame:
    """Thêm cột `er` và `quant_regime` vào bản sao của `m5`.

    Yêu cầu `m5` đã có `atr_regime_ratio` và `adx_m5` (từ
    `shared.indicators.add_core_features`). Cột thanh khoản là TUỲ CHỌN — thiếu
    cả spread lẫn `n_tick` thì nhãn LOW_LIQUIDITY sẽ không bao giờ được gán
    (fail-soft, không raise) vì nó chỉ dựa vào 2 tín hiệu đó.

    Sinh thêm: `er`, `spread_bp`, `spread_ratio`, `tick_z`, `quant_regime`.
    `spread_ratio` và `tick_z` đều dùng cửa sổ trượt NHÂN QUẢ (chỉ bar quá khứ),
    nên an toàn để gán nhãn tại thời điểm ra quyết định.

    LƯU Ý về tính nhất quán giữa các đường dữ liệu: frame M5 dựng từ M1 qua
    `data_loader.build_m5_features()` KHÔNG có `n_tick`, nên ở đường đó
    LOW_LIQUIDITY chỉ dựa vào spread; parquet M5 thô trên `D:\\data-ticks-train`
    thì CÓ `n_tick` nên dùng đủ 2 tín hiệu và bắt được nhiều bar hơn. Đây là
    khác biệt THẬT giữa 2 nguồn, không phải bug — nhưng đừng so trực tiếp tỉ lệ
    LOW_LIQUIDITY giữa 2 đường.
    """
    out = m5.copy()
    if "er" not in out.columns:
        out["er"] = efficiency_ratio(out[close_col])

    if "spread_ratio" not in out.columns:
        if "spread_bp" not in out.columns:
            spread = out.get("spread_usd", out.get("spread"))
            out["spread_bp"] = (spread / out[close_col] * 1e4) if spread is not None else pd.NA
        if out["spread_bp"].isna().all():
            out["spread_ratio"] = pd.NA
        else:
            med = out["spread_bp"].rolling(
                SPREAD_RATIO_WINDOW, min_periods=SPREAD_RATIO_WINDOW // 4).median()
            out["spread_ratio"] = out["spread_bp"] / med.replace(0, pd.NA)

    if "tick_z" not in out.columns:
        if "n_tick" in out.columns:
            w = 2016
            roll = out["n_tick"].rolling(w, min_periods=SPREAD_RATIO_WINDOW)
            out["tick_z"] = (out["n_tick"] - roll.mean()) / roll.std()
        else:
            out["tick_z"] = pd.NA

    out["quant_regime"] = [
        classify_quant_row(a, x, e, s, t)
        for a, x, e, s, t in zip(
            out["atr_regime_ratio"], out["adx_m5"], out["er"],
            out["spread_ratio"], out["tick_z"],
            strict=True,
        )
    ]
    return out


def classify_quant_at(m5: pd.DataFrame, t: pd.Timestamp) -> str:
    """Tra cứu nhãn 6-trạng-thái tại/trước `t` (asof, không look-ahead).

    `m5` phải đã đi qua `add_quant_regime()`. Trả "UNKNOWN" nếu `t` nằm trước
    bar đầu tiên hoặc dữ liệu thiếu.
    """
    if "quant_regime" not in m5.columns:
        raise KeyError("m5 chưa có cột 'quant_regime' — gọi add_quant_regime() trước")
    pos = m5.index.searchsorted(t, side="right") - 1
    if pos < 0:
        return "UNKNOWN"
    return str(m5["quant_regime"].iloc[pos])


# =============================================================================
# TRỤC THỜI GIAN — "TIME REGIME" 
# =============================================================================
# Phân loại Time Regime neo theo giờ địa phương London (ZoneInfo)
# Đảm bảo bám đúng phiên giao dịch bất kể lịch đổi giờ DST mùa hè.
# =============================================================================
from datetime import datetime, timezone   

try:                                       
    from zoneinfo import ZoneInfo
    _LONDON = ZoneInfo("Europe/London")
except Exception:                          
    _LONDON = None

# 5 Nhãn Phiên Giao Dịch chính.
TIME_ASIAN_QUIET = "ASIAN"
TIME_LONDON = "LONDON"
TIME_NY_OVERLAP = "NEW_YORK"
TIME_NY_ONLY = "NEW_YORK_ONLY"
TIME_DEAD_ZONE = "NO_SESSION"

TIME_REGIME_LABELS = (
    TIME_ASIAN_QUIET, TIME_LONDON,
    TIME_NY_OVERLAP, TIME_NY_ONLY, TIME_DEAD_ZONE,
)

# (giờ London bắt đầu, giờ London kết thúc) — nửa mở [start, end).
# Bảng phủ KÍN 24 giờ, không hở không chồng (có test kiểm bất biến này).
_TIME_REGIME_WINDOWS = (
    (23, 24, TIME_ASIAN_QUIET),    # GMT+7 06:00-07:00
    (0,  6,  TIME_ASIAN_QUIET),    # GMT+7 07:00-13:00
    (6,  7,  TIME_DEAD_ZONE),      # GMT+7 13:00-14:00 — Á đã tan, London chưa mở
    (7,  12, TIME_LONDON),         # GMT+7 14:00-19:00 (gộp 30/07 từ 2 khung)
    (12, 16, TIME_NY_OVERLAP),     # GMT+7 19:00-23:00  <- thanh khoản cao nhất
    (16, 18, TIME_NY_ONLY),        # GMT+7 23:00-01:00
    (18, 23, TIME_DEAD_ZONE),      # GMT+7 01:00-06:00 — cuối phiên Mỹ, mỏng
)


TIME_REGIME_ACTIVITY = {
    TIME_DEAD_ZONE:    0.10,
    TIME_ASIAN_QUIET:  0.25,
    TIME_LONDON:       0.70,
    TIME_NY_OVERLAP:   1.00,
    TIME_NY_ONLY:      0.65,
}

TIME_REGIME_VI = {
    TIME_ASIAN_QUIET:  "Phiên Á yên ắng — biên hẹp, hợp range hơn trend",
    TIME_LONDON:       "Phiên London — thanh khoản tăng, xu hướng trong ngày hình thành",
    TIME_NY_OVERLAP:   "Chồng lấn London–New York — thanh khoản và biến động cao nhất",
    TIME_NY_ONLY:      "New York — vẫn nhiều cơ hội, thanh khoản giảm dần",
    TIME_DEAD_ZONE:    "No session — thanh khoản mỏng, biến động thất thường",
}


def london_hour(now_utc: Optional[datetime] = None) -> int:
    """Giờ (0-23) theo múi giờ London, đã tính DST. Fallback về UTC nếu môi
    trường thiếu tzdata — kém chính xác 1 giờ vào mùa hè nhưng KHÔNG bao giờ
    ném lỗi, vì trục thời gian được dùng trong đường chạy live."""
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if _LONDON is None:
        return now.astimezone(timezone.utc).hour
    return now.astimezone(_LONDON).hour


def classify_time_regime(now_utc: Optional[datetime] = None) -> str:
    """Time Regime hiện tại — một trong `TIME_REGIME_LABELS`."""
    h = london_hour(now_utc)
    for start, end, label in _TIME_REGIME_WINDOWS:
        if start <= h < end:
            return label
    return TIME_DEAD_ZONE 


def time_regime_activity(now_utc: Optional[datetime] = None) -> float:
    """Điểm hoạt động 0.0-1.0 của Time Regime hiện tại."""
    return TIME_REGIME_ACTIVITY.get(classify_time_regime(now_utc), 0.5)


def session_label(dt_utc: Optional[datetime] = None) -> str:
    """Nhãn phiên (tương thích ngược, giờ UTC thô — xem ghi chú ngay trên)."""
    h = (dt_utc or datetime.now(timezone.utc)).hour
    if 0 <= h < 7:
        return "Asia"
    if 7 <= h < 12:
        return "London"
    if 12 <= h < 13:
        return "London/NY Overlap"
    if 13 <= h < 21:
        return "New York"
    return "Overnight"


# ─────────────────────────────────────────────────────────────────────────────
# TRẠNG THÁI THỊ TRƯỜNG "HARD" GẦN NHẤT — chỉ để HIỂN THỊ (07/08)
#
import time as _time                      

_LAST_HARD_REGIME: Dict[str, tuple] = {}

# Từ vựng nhãn của bộ đo ĐƯỜNG BAO (`core/intelligence/regime_envelope.py`).
#
# SSOT nằm Ở ĐÂY chứ không ở `core/` vì phân tầng: `shared/` không được import lên
# `core/` (test `test_shared_layer_does_not_import_upward` khoá điều này), mà chính
# `shared/` là nơi email/GUI đọc để hiển thị. Chiều đúng là `core` import xuống
# `shared` — `regime_envelope` lấy tên nhãn từ đây, không tự khai lại.
ENVELOPE_TREND_UP = "TREND_UP"
ENVELOPE_TREND_DOWN = "TREND_DOWN"
ENVELOPE_RANGE = "RANGE"
ENVELOPE_COMPRESSION = "NEN"
ENVELOPE_LABELS = (ENVELOPE_TREND_UP, ENVELOPE_TREND_DOWN,
                   ENVELOPE_RANGE, ENVELOPE_COMPRESSION)

# Tên HIỂN THỊ cho người vận hành. Tách khỏi tên nhãn nội bộ vì hai lý do:
#
# 1. Nhãn nội bộ không dấu (`NEN`) để an toàn khi ghi log/JSON; nhưng đưa thẳng ra
#    màn hình thì `"NEN".title()` cho "Nen" — mất dấu, đọc như lỗi gõ.
# 2. "NÉN" gây hiểu nhầm là giá đang bị siết trong hộp nhỏ. Kiểm chứng bằng mắt trên
#    TradingView (11/08, cửa sổ 05-18/05/2026) cho thấy KHÔNG phải vậy: giá đi từ
#    4480 lên 4773 rồi về 4543 — 293 điểm, không hề hẹp theo nghĩa thông thường.
#    Nó "hẹp" so với CHÍNH độ biến động lúc đó: ATR ~39 điểm/nến, nên 60 nến đi ngẫu
#    nhiên cũng phủ ~302 điểm. Tức thị trường tiêu hao 13 ngày mà không dựng nổi biên
#    nào rộng hơn nhiễu của chính nó. Tên hiển thị nói đúng điều đó.
ENVELOPE_DISPLAY_VI = {
    ENVELOPE_TREND_UP:    "XU HƯỚNG TĂNG",
    ENVELOPE_TREND_DOWN:  "XU HƯỚNG GIẢM",
    ENVELOPE_RANGE:       "RANGE (biên rộng)",
    ENVELOPE_COMPRESSION: "VÔ ĐỊNH (không cấu trúc)",
}


def envelope_display_vi(label: str) -> str:
    """Tên hiển thị của nhãn đường bao; trả chính `label` nếu không phải nhãn V2."""
    return ENVELOPE_DISPLAY_VI.get(str(label), str(label))

# Diễn giải từng trạng thái bằng lời trader — dùng chung cho email và GUI.
HARD_REGIME_MEANING = {
    # ── Nhãn V2 (`regime_envelope`, mặc định từ 11/08/2026) ────────────────────
    "TREND_UP": "Xu hướng TĂNG — giá đã đi hết phần lớn biên độ 10 ngày về phía trên",
    "TREND_DOWN": "Xu hướng GIẢM — giá đã đi hết phần lớn biên độ 10 ngày về phía dưới",
    "RANGE": "RANGE đã hình thành, biên RỘNG — giá dập trong biên và có xu hướng "
             "tôn trọng biên đó (đo được 59% số lần)",
    # KHÔNG viết "biên hẹp" — bản đầu viết vậy và nó MÂU THUẪN với chính chart.
    # Kiểm bằng mắt trên TradingView (cửa sổ 05-18/05/2026): giá chạy 293 điểm
    # (4480 -> 4773 -> 4543). Hẹp ở đây là hẹp SO VỚI biến động của chính nó, không
    # phải hẹp trên màn hình. Người vận hành mở chart thấy giá chạy 300 điểm mà đọc
    # "biên hẹp" sẽ tưởng hệ thống hỏng.
    "NEN": "Giá đi lòng vòng rồi về gần chỗ cũ, KHÔNG dựng được biên nào rộng hơn "
           "mức dao động thường ngày của chính nó — chưa có cấu trúc để bám, và hay "
           "bung ra bất ngờ. Đây là trạng thái DUY NHẤT bị chặn vào lệnh",

    # ── Nhãn V1 (`regime_engine`) — CHỈ CÒN DÙNG KHI REGIME_GATE_MODE=v1 ───────
    # Diễn giải dưới đây đã được SỬA LẠI cho khớp thực tế đo được 11/08/2026
    # (18.397 nến H4, 2015-2026). Bản cũ mô tả theo TÊN nhãn và mô tả sai:
    #   "SIDEWAYS" từng ghi là "đi ngang biên hẹp" — thực tế dịch chuyển ròng
    #   trung vị 3,87 ATR, tức một xu hướng; còn "NOISE" mới là chỗ chứa dịch
    #   chuyển ≈0. Hai nhãn này ĐẢO NGHĨA cho nhau.
    "UPTREND": "Xu hướng TĂNG rõ — giá đi lên đều, thuận cho chiến lược bám xu hướng",
    "DOWNTREND": "Nhãn V1 gọi là GIẢM, nhưng đo thực tế thì sau nhãn này giá "
                 "thường ĐI LÊN (+0,7 ATR/4 ngày) — đừng đọc theo nghĩa mặt chữ",
    "SIDEWAYS": "Nhãn V1 gọi là đi ngang, nhưng đo thực tế đây là trạng thái CÓ "
                "xu hướng (dịch chuyển trung vị 3,9 ATR)",
    "NOISE": "Nhãn V1 gọi là nhiễu, nhưng đo thực tế đây mới là RANGE thật "
             "(dịch chuyển ròng gần 0)",
    "UNKNOWN": "Chưa đủ nến để kết luận",
}


def remember_hard_regime(symbol: str, label: str, confidence: float,
                         describe_text: str) -> None:
    """Ghi lại nhãn mà cổng vào lệnh vừa tính. Không ảnh hưởng quyết định nào."""
    _LAST_HARD_REGIME[str(symbol).upper()] = (
        str(label), float(confidence), str(describe_text), _time.time())


def latest_hard_regime(symbol: str,
                       max_age_seconds: float = 6 * 3600) -> Optional[dict]:
    """Trạng thái HARD gần nhất mà cổng vào lệnh đã dùng.

    `None` khi chưa đo lần nào hoặc số đã quá cũ — nơi hiển thị phải nói "chưa
    đo được" thay vì in một nhãn có thể đã hết hiệu lực. Nến H4 nên mặc định 6
    giờ là khoảng một nến rưỡi.
    """
    record = _LAST_HARD_REGIME.get(str(symbol).upper())
    if not record:
        return None
    label, confidence, describe_text, ts = record
    age = _time.time() - ts
    if age > max_age_seconds:
        return None
    return {"label": label, "confidence": confidence,
            "describe": describe_text, "age_minutes": age / 60.0}
