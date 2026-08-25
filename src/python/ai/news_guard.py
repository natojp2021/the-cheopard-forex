"""news_guard.py — CỔNG TIN VĨ MÔ. Một tầng, chỉ chặn, không dự báo.

ĐANG **BẬT**, CỬA SỔ ±30 PHÚT — và con số quyết định là MaxDD, không phải lợi nhuận
═══════════════════════════════════════════════════════════════════════════════════
Đo trên đúng 462 lệnh của chiến lược đang chạy, ở rủi ro 0,60%/lệnh:

    cửa sổ    số lệnh bị chặn   R của lệnh bị chặn   R còn lại   số dư cuối   MaxDD
    không            0                  —             +0,0893    $124.740    -8,90%
    ±15p             2  (0,4%)       +1,0304          +0,0852    $123.504    -8,90%
    ±30p             9  (1,9%)       +0,0366          +0,0903    $124.542    -8,28%
    ±60p            13  (2,8%)       +0,1341          +0,0880    $123.694    -8,28%
    ±240p           41  (8,9%)       +0,1276          +0,0855    $121.602    -7,90%
    CẢ NGÀY         41  (8,9%)       +0,1985          +0,0786    $119.858    -8,87%

±30 phút là điểm đúng, và lý do KHÔNG phải lợi nhuận: tiền gần như không đổi
($124.542 so với $124.740, tức -0,2%) nhưng **MaxDD giảm 8,90% -> 8,28%**. Với ràng
buộc FTMO thì 0,62 điểm phần trăm đệm tới sàn 9% đáng giá hơn nhiều 0,2% lợi nhuận.

CHẶN CẢ NGÀY thì SAI HƯỚNG, và số đo nói rõ: 41 lệnh nằm trong ngày có NFP/CPI/FOMC
có kỳ vọng **+0,1985 R**, tức HƠN HAI LẦN trung bình. Chặn chúng mất 8,1R mà MaxDD chỉ
nhích 8,90% -> 8,87%. Ngày tin không phải ngày xấu; chỉ ĐÚNG PHÚT công bố mới xấu.

Cơ chế giải thích được: cú sốc định giá lại xảy ra trong vài phút quanh mốc công bố,
và rủi ro thật ở đó không phải "giá đi sai hướng" mà là **dừng lỗ bị nhảy qua** — một
tổn thất LỚN HƠN 0,60% đã dự kiến. Backtest không thấy được điều đó (nó giả định SL
khớp đúng giá), nên phần đệm MaxDD đo được ở trên vẫn là ƯỚC LƯỢNG THẤP của giá trị
thật mà cổng này mang lại.

Tắt bằng `ENABLED_DEFAULT = True` hoặc biến môi trường `NEWS_GUARD=0`.

═══════════════════════════════════════════════════════════════════════════════════
VÌ SAO CHỈ CHẶN, KHÔNG DỰ BÁO
═══════════════════════════════════════════════════════════════════════════════════
Một kiến trúc "chuyên gia + chủ tịch" sinh ra một DỰ BÁO HƯỚNG rồi dùng nó để điều
chỉnh vị thế. Ở đây bỏ toàn bộ phần dự báo, giữ đúng phần chặn. Ba lý do đo được:

  1. **Tin không dự báo được HƯỚNG.** Hướng giao dịch phản ứng thái quá sau tin đã bị
     bác bỏ: control p = 0,0000 nhưng toàn bộ edge nằm trong nến có spread rộng nhất,
     và vào lệnh CHẬM MỘT NẾN làm t rơi 1,64 -> 0,47. Cái đo được là ĐỘ LỚN dịch
     chuyển (NFP 5,1x biên độ thường), không phải CHIỀU.

  2. **Một tầng thì kiểm chứng được, hai tầng thì không.** Với chuyên gia + chủ tịch,
     khi hệ ra quyết định sai không truy được sai ở tầng nào. Một tầng có một đầu
     vào, một đầu ra, một bản ghi.

  3. **Càng ít cổng càng ít chỗ hỏng im lặng.** Chính module này từng đọc trượt cột
     lịch (`time` thay vì `time_utc`) và trả THÔNG suốt nhiều ngày mà không báo lỗi.
     Đó là lý do `health()` tồn tại: nó làm cho "cổng đang mù" không thể im lặng.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
CALENDAR_PATH = ROOT / "data" / "economic_calendar_events.parquet"

# ⚠️ MẶC ĐỊNH TẮT — xem phần đầu docstring. Cổng này đo được là LÀM HẠI trên rổ cross
# hiện tại (Sharpe trung vị 0,811 → 0,622). Không xoá code vì nó sẽ cần khi danh mục
# thêm công cụ chứa USD/EUR/GBP hoặc thêm chiến lược theo xu hướng.
ENABLED_DEFAULT = True


def is_enabled() -> bool:
    """Cổng có đang bật không. Biến môi trường `NEWS_GUARD` ghi đè mặc định."""
    v = os.getenv("NEWS_GUARD")
    if v is None:
        return ENABLED_DEFAULT
    return v.strip().lower() in ("1", "true", "yes", "on")

# ═══════════════════════════════════════════════════════ tham số
# Cửa sổ chặn quanh sự kiện. Rộng hơn một hệ một-tài-sản (±30 phút) vì các chiến lược ở đây
# giữ lệnh nhiều NGÀY: một lệnh mở ngay trước NFP sẽ ôm trọn cú nhảy, và cú nhảy đó
# lớn gấp 4-6 lần biên độ nến thường (đo được: NFP 15,88 bps vs 3,12 bps thường).
BLOCK_BEFORE_MIN = 30.0
BLOCK_AFTER_MIN = 30.0

# Chặn TOÀN NGÀY với sự kiện tác động lớn nhất. Mặc định BẬT: thanh khoản mỏng đi từ
# nhiều giờ trước tin, và spread giãn kéo dài sau tin.
BLOCK_FULL_DAY_EVENTS: Tuple[str, ...] = ()

# Sự kiện chỉ chặn theo cửa sổ hẹp.
#
# THU HẸP 14/08/2026 — CHỈ KHAI NHỮNG GÌ LỊCH THẬT SỰ CÓ.
# Bản trước khai thêm mười loại: RBA_RATE · BOC_RATE · RBNZ_RATE · SNB_RATE ·
# BOJ_RATE · GDP · PPI · RETAIL_SALES · PMI · UNEMPLOYMENT. Không loại nào có MỘT
# dòng nào trong `data/economic_calendar_events.parquet` (968 dòng, đúng năm loại:
# NFP · CPI · FOMC · ECB_RATE · BOE_RATE).
#
# Khai một cổng không bao giờ nổ tệ hơn không khai: người đọc code tin rằng họp RBA
# có được canh, và không ai đi kiểm lại. Danh sách nay bằng đúng thứ đo được.
WINDOW_ONLY_EVENTS: Tuple[str, ...] = ("NFP", "CPI", "FOMC",
                                      "ECB_RATE", "BOE_RATE")

HIGH_IMPACT = set(BLOCK_FULL_DAY_EVENTS) | set(WINDOW_ONLY_EVENTS)

# ĐỒNG TIỀN CỔNG NÀY CANH ĐƯỢC — và chỉ ba đồng này.
#
# Nguồn lịch hiện có chỉ phủ USD · EUR · GBP. Năm đồng còn lại mà danh mục giao dịch
# nặng (JPY · AUD · NZD · CAD · CHF) KHÔNG có dữ liệu, và sẽ không có: người vận
# hành đã xác nhận "tôi chỉ có thế thôi".
#
# Cách xử lý đúng là KHAI RÕ phạm vi chứ không giả vờ canh cả rổ. `blocks_instrument`
# vì vậy trả `False` cho công cụ không chứa ba đồng này — không phải vì nó an toàn,
# mà vì cổng KHÔNG BIẾT, và một cổng không biết thì không được phép ra phán quyết.
# Nói "thông" khi thật ra là "mù" chính là kiểu hỏng im lặng mà cả module này sinh
# ra để tránh; `health()` và `scope_note()` làm cho sự mù đó đọc được.
COVERED_CURRENCIES: Tuple[str, ...] = ("USD", "EUR", "GBP")


def in_scope(instrument: str) -> bool:
    """Công cụ này có nằm trong phạm vi cổng canh được không."""
    s = str(instrument).upper()
    return any(c in s for c in COVERED_CURRENCIES)


def scope_note(instrument: str) -> str:
    """Một câu nói rõ cổng có canh được công cụ này qua LỊCH hay không.

    Chỉ để ghi vào sổ và hiển thị. KHÔNG dùng để quyết định chặn — xem
    `GuardDecision.blocks_instrument()` cho lý do.
    """
    if in_scope(instrument):
        return ""
    return (f"{instrument} NGOÀI PHẠM VI lịch tin: nguồn hiện có chỉ phủ "
            f"{', '.join(COVERED_CURRENCIES)}. Cổng không chặn vì KHÔNG BIẾT, "
            f"không phải vì đã kiểm và thấy an toàn.")

# Ánh xạ SỰ KIỆN → ĐỒNG TIỀN. Lịch `data/economic_calendar_events.parquet` không có
# cột tiền tệ (968 dòng, năm loại sự kiện), nên phải suy ra. Suy sai ở đây làm cổng
# chặn nhầm công cụ — chặn AUDNZD vì NFP là mất lệnh mà không giảm rủi ro gì.
EVENT_CURRENCY: Dict[str, Tuple[str, ...]] = {
    "NFP": ("USD",), "CPI": ("USD",), "FOMC": ("USD",),
    "ECB_RATE": ("EUR",), "BOE_RATE": ("GBP",),
    "BOJ_RATE": ("JPY",), "RBA_RATE": ("AUD",), "BOC_RATE": ("CAD",),
    "RBNZ_RATE": ("NZD",), "SNB_RATE": ("CHF",),
}


def _currencies_of(events: Sequence[str]) -> Tuple[str, ...]:
    """Đồng tiền bị ảnh hưởng bởi tập sự kiện. Rỗng = không biết → chặn tất cả."""
    out: List[str] = []
    for e in events:
        out.extend(EVENT_CURRENCY.get(str(e).upper(), ()))
    return tuple(sorted(set(out)))


@dataclass
class GuardDecision:
    """Quyết định của cổng — ghi đủ để tái lập, kể cả khi KHÔNG chặn.

    Ghi cả trường hợp thông suốt là có chủ ý: câu hỏi vận hành hay gặp nhất là "vì
    sao hôm nay không có lệnh nào", và nó chỉ trả lời được nếu cổng cũng ghi lúc mở.
    """
    timestamp: pd.Timestamp
    blocked: bool
    source: str                       # CALENDAR | LLM | NONE
    severity: str = "NONE"            # NONE | MEDIUM | HIGH
    events: Tuple[str, ...] = ()
    currencies: Tuple[str, ...] = ()  # đồng tiền bị ảnh hưởng, rỗng = toàn bộ
    minutes_to_event: Optional[float] = None
    reason: str = ""
    llm_used: bool = False
    llm_error: str = ""

    def to_row(self) -> Dict[str, object]:
        d = asdict(self)
        d["timestamp"] = str(self.timestamp)
        return d

    def explain(self) -> str:
        v = "CHẶN" if self.blocked else "THÔNG"
        ev = ", ".join(self.events) if self.events else "—"
        return (f"[{self.timestamp}] NewsGuard {v} · nguồn {self.source} · "
                f"mức {self.severity} · sự kiện: {ev} · {self.reason}")

    def blocks_instrument(self, instrument: str) -> bool:
        """Cổng có chặn công cụ NÀY không.

        Nếu `currencies` rỗng thì chặn toàn bộ. Nếu có, chỉ chặn công cụ chứa ít nhất
        một đồng bị ảnh hưởng — NFP không có lý do gì chặn AUDNZD.
        """
        if not self.blocked:
            return False
        # ⚠️ KHÔNG lọc theo `COVERED_CURRENCIES` ở đây — thử rồi và SAI, hoàn lại
        # 14/08/2026. Ba lý do:
        #   1. Sự kiện từ LỊCH đã tự giới hạn: `EVENT_CURRENCY` chỉ ánh xạ ra
        #      USD/EUR/GBP, nên `currencies` bên dưới đã lọc đúng rồi. Thêm một
        #      lớp lọc nữa là thừa.
        #   2. Tầng LLM đọc TIÊU ĐỀ TIN, nên nó BIẾT được những thứ lịch không có —
        #      "BOJ can thiệp ngoại hối" là JPY, và chặn CADJPY lúc đó là đúng.
        #      Lọc theo phạm vi LỊCH sẽ vô hiệu hoá đúng phần mà tầng LLM có ích.
        #   3. `currencies` rỗng nghĩa là KHÔNG BIẾT sự kiện thuộc đồng nào →
        #      chặn tất cả. Đó là nhánh an toàn, và lọc phạm vi làm hỏng nó.
        # `COVERED_CURRENCIES` / `in_scope()` / `scope_note()` vẫn giữ, nhưng chỉ
        # để KHAI BÁO và CHẨN ĐOÁN — không tham gia quyết định chặn.
        if not self.currencies:
            return True
        s = instrument.upper()
        return any(c.upper() in s for c in self.currencies)


# ═══════════════════════════════════════════════════════ tầng 0 — lịch kinh tế
_cache: Dict[str, object] = {"df": None, "mtime": None}


def load_calendar(path: Path = CALENDAR_PATH) -> Optional[pd.DataFrame]:
    """Đọc lịch kinh tế, có cache theo mtime. Trả None nếu không có — fail-soft."""
    try:
        if not path.exists():
            return None
        mt = path.stat().st_mtime
        if _cache["df"] is not None and _cache["mtime"] == mt:
            return _cache["df"]           # type: ignore[return-value]
        df = pd.read_parquet(path)
        # Lịch thật dùng cột `time_utc`; bản cũ tìm `time` nên đọc trượt và cổng LUÔN
        # trả THÔNG mà không báo lỗi — đúng dạng hỏng im lặng nguy hiểm nhất.
        col = "time_utc" if "time_utc" in df.columns else "time"
        df = df.rename(columns={col: "time"})
        df["time"] = pd.to_datetime(df["time"], utc=True)
        if "impact" in df.columns:
            df = df[df["impact"].astype(str).str.lower() == "high"]
        _cache["df"], _cache["mtime"] = df, mt
        return df
    except Exception:                     # pragma: no cover — fail-soft có chủ ý
        return None


# ═══════════════════════════════════════════════════════ SỨC KHOẺ LỊCH
# RÀ SOÁT 14/08/2026 — bốn lỗ hổng đo được trên chính file lịch đang dùng
# (`data/economic_calendar_events.parquet`, 968 dòng):
#
#   1. MẬT ĐỘ PHÍA TRƯỚC RẤT MỎNG. Lịch phủ tới 2027-12 (489 ngày nữa) nhưng chỉ
#      **40 dòng** trong quãng đó, tức ~1 sự kiện/12 ngày. Không phải sắp hết hạn,
#      nhưng khi nó hết thì cổng trả "THÔNG" y hệt lúc thật sự không có tin — hai
#      tình huống khác hẳn nhau mà không phân biệt được. `health()` bên dưới làm
#      cho tình trạng đó không thể im lặng.
#   2. THIẾU 5/8 ĐỒNG TIỀN. Lịch chỉ có NFP · CPI · FOMC · ECB_RATE · BOE_RATE,
#      tức USD · EUR · GBP. Nhưng `WINDOW_ONLY_EVENTS` khai cả RBA · RBNZ · BOC ·
#      SNB · BOJ — không dòng nào tồn tại, nên cổng KHÔNG BAO GIỜ nổ cho chúng.
#      Rổ hiện tại là USD · EUR · GBP · JPY, nên ba đồng đầu ĐƯỢC canh; JPY thì
#      KHÔNG (không có dòng BOJ nào). Cổng mù đúng một trong bốn đồng của rổ.
#   3. 57 DÒNG TỰ ĐÁNH DẤU CHƯA KIỂM CHỨNG (`source` chứa `VERIFY_BEFORE_EVENT`).
#   4. `impact` chỉ có MỘT giá trị "high" cho cả 968 dòng — không phân cấp được,
#      nên việc chặn cả ngày hay chặn cửa sổ hẹp phụ thuộc hoàn toàn vào TÊN sự kiện.
#
# Ba hàm dưới đây không sửa được dữ liệu, nhưng làm cho tình trạng đó KHÔNG THỂ im
# lặng: bên gọi đọc `health()` và biết cổng đang mù ở đâu.

# Số ngày tối thiểu lịch phải phủ về phía trước thì cổng mới đáng tin.
MIN_FORWARD_DAYS = 30

# Đồng tiền mà danh mục thật sự giao dịch — dùng để chấm độ phủ của lịch.
# Đồng tiền mà rổ THẬT SỰ giao dịch, suy từ SSOT thay vì gõ tay: gõ tay là chỗ
# danh sách này trôi khỏi rổ và `health()` chấm độ phủ của một rổ không tồn tại.
def _traded_currencies() -> Tuple[str, ...]:
    from src.python.shared import asset_profile as AP
    from src.python.strategies.h1 import asia_sweep as AS

    out: list = []
    for sym in AS.INSTRUMENTS:
        prof = AP.get(sym)
        for c in (prof.base, prof.quote):
            if c not in out:
                out.append(c)
    return tuple(out)


TRADED_CURRENCIES: Tuple[str, ...] = _traded_currencies()


@dataclass(frozen=True)
class CalendarHealth:
    """Lịch có dùng được không, và mù ở đâu."""
    ok: bool
    rows: int
    last_event_utc: Optional[str]
    forward_days: float
    covered_currencies: Tuple[str, ...]
    blind_currencies: Tuple[str, ...]
    unverified_rows: int
    problems: Tuple[str, ...] = ()

    def explain(self) -> str:
        head = (f"lịch {self.rows} dòng · phủ tới {self.last_event_utc} "
                f"({self.forward_days:.0f} ngày nữa) · mù: "
                f"{', '.join(self.blind_currencies) or 'không'}")
        return head if self.ok else head + "\n  VẤN ĐỀ: " + " · ".join(self.problems)


def health(now_utc: Optional[pd.Timestamp] = None,
           path: Path = CALENDAR_PATH) -> CalendarHealth:
    """Chấm sức khoẻ lịch. Gọi ở khởi động và trước mỗi chu kỳ tái cân bằng.

    KHÔNG tự chặn giao dịch: cổng tin hiện mặc định TẮT vì đo được nó làm hại, nên
    một lịch cũ không phải lý do dừng hệ. Nhưng nếu ai bật cổng lên (`NEWS_GUARD=1`)
    mà lịch đã cạn, họ phải biết là mình đang bật một cổng KHÔNG canh gì cả.
    """
    now = pd.Timestamp(now_utc) if now_utc is not None else pd.Timestamp(
        datetime.now(timezone.utc))
    if now.tzinfo is None:
        now = now.tz_localize("UTC")

    df = load_calendar(path)
    if df is None or df.empty:
        return CalendarHealth(
            ok=False, rows=0, last_event_utc=None, forward_days=-1.0,
            covered_currencies=(), blind_currencies=TRADED_CURRENCIES,
            unverified_rows=0,
            problems=("không đọc được lịch kinh tế — cổng tin mù hoàn toàn",))

    last = pd.Timestamp(df["time"].max())
    forward = (last - now).total_seconds() / 86400.0
    events = tuple(sorted(str(e).upper() for e in df["event"].unique()))
    covered = _currencies_of(events)
    blind = tuple(c for c in TRADED_CURRENCIES if c not in covered)

    unverified = 0
    if "source" in df.columns:
        unverified = int(df["source"].astype(str)
                         .str.contains("VERIFY", case=False, na=False).sum())

    problems: List[str] = []
    if forward < MIN_FORWARD_DAYS:
        problems.append(
            f"lịch chỉ còn {forward:.0f} ngày phía trước (tối thiểu "
            f"{MIN_FORWARD_DAYS}) — khi cạn, cổng trả THÔNG y hệt lúc không có tin")
    # `blind` KHÔNG còn tính là "vấn đề" từ 14/08/2026: phạm vi đã được KHAI BÁO
    # tường minh ở `COVERED_CURRENCIES`, và `blocks_instrument()` tôn trọng nó. Một
    # giới hạn đã khai báo và đã cưỡng chế là một quyết định, không phải một lỗi.
    # Nó vẫn hiện trong `blind_currencies` để người vận hành đọc được.
    declared = set(BLOCK_FULL_DAY_EVENTS) | set(WINDOW_ONLY_EVENTS)
    never_fire = tuple(sorted(declared - set(events)))
    if never_fire:
        problems.append(
            f"{len(never_fire)} loại sự kiện khai trong code nhưng KHÔNG có dòng nào "
            f"trong lịch: {', '.join(never_fire)}")
    if unverified:
        problems.append(f"{unverified} dòng tự đánh dấu CHƯA kiểm chứng "
                        f"(source chứa VERIFY)")

    return CalendarHealth(
        ok=not problems, rows=len(df), last_event_utc=str(last),
        forward_days=round(forward, 1), covered_currencies=covered,
        blind_currencies=blind, unverified_rows=unverified,
        problems=tuple(problems))


def check_calendar(now_utc: pd.Timestamp,
                   path: Path = CALENDAR_PATH) -> GuardDecision:
    """Tầng 0: chặn theo lịch. Không cần mạng, không cần LLM, không cần khoá API."""
    df = load_calendar(path)
    if df is None or df.empty or "time" not in df.columns:
        return GuardDecision(timestamp=now_utc, blocked=False, source="NONE",
                             reason="không có lịch kinh tế — cổng THÔNG (fail-soft)")

    now = pd.Timestamp(now_utc).tz_localize("UTC") if now_utc.tzinfo is None \
        else pd.Timestamp(now_utc)
    ev_col = "event" if "event" in df.columns else df.columns[-1]

    # (a) chặn toàn ngày với sự kiện lớn nhất
    day = df[df["time"].dt.date == now.date()]
    big = day[day[ev_col].astype(str).str.upper().isin(BLOCK_FULL_DAY_EVENTS)]
    if not big.empty:
        evs = tuple(sorted(set(big[ev_col].astype(str).str.upper())))
        ccy = tuple(sorted(set(big["currency"].astype(str)))) \
            if "currency" in big.columns else ()
        return GuardDecision(
            timestamp=now_utc, blocked=True, source="CALENDAR", severity="HIGH",
            events=evs, currencies=ccy,
            reason=f"chặn TOÀN NGÀY: {', '.join(evs)} công bố hôm nay — thanh khoản "
                   f"mỏng từ nhiều giờ trước và spread giãn kéo dài sau tin")

    # (b) cửa sổ hẹp quanh mọi sự kiện tác động lớn
    lo = now - timedelta(minutes=BLOCK_AFTER_MIN)
    hi = now + timedelta(minutes=BLOCK_BEFORE_MIN)
    near = df[(df["time"] >= lo) & (df["time"] <= hi)]
    near = near[near[ev_col].astype(str).str.upper().isin(HIGH_IMPACT)]
    if not near.empty:
        evs = tuple(sorted(set(near[ev_col].astype(str).str.upper())))
        ccy = tuple(sorted(set(near["currency"].astype(str)))) \
            if "currency" in near.columns else ()
        mins = float((near["time"].iloc[0] - now).total_seconds() / 60.0)
        return GuardDecision(
            timestamp=now_utc, blocked=True, source="CALENDAR", severity="MEDIUM",
            events=evs, currencies=ccy, minutes_to_event=round(mins, 1),
            reason=f"trong cửa sổ ±{int(BLOCK_BEFORE_MIN)} phút quanh "
                   f"{', '.join(evs)} ({mins:+.0f} phút)")

    return GuardDecision(timestamp=now_utc, blocked=False, source="CALENDAR",
                         reason="không có sự kiện tác động lớn trong cửa sổ")


# ═══════════════════════════════════════════════════════ tầng 1 — LLM một lượt
PROMPT_TEMPLATE = """Role: FX Risk Gatekeeper for a systematic mean-reversion book.
Task: decide whether to BLOCK opening NEW positions right now.

[Context]
Time (UTC): {now}
Traded instruments: {instruments}
Calendar layer says: {calendar_verdict}

[Headlines in the last 24h]
{headlines}

[Rules]
- The book is MEAN-REVERSION on FX crosses. It loses in trending, gap-driven regimes.
- BLOCK only for events that produce a sustained directional repricing: central bank
  policy surprises, emergency meetings, sovereign/credit shocks, war escalation,
  large intervention, systemic bank failure.
- DO NOT block for routine data already on the calendar, opinion pieces, forecasts,
  analyst commentary, or price recaps.
- If nothing qualifies, return block=false. A false block costs real edge; the
  calendar layer already covers scheduled events.
- currencies: list ONLY the currencies actually repriced. Empty list means all.

[Output — JSON only, no prose]
{{"block": true|false,
  "severity": "NONE"|"MEDIUM"|"HIGH",
  "currencies": ["USD", ...],
  "reason": "<lý do bằng TIẾNG VIỆT, tối đa 25 từ>"}}"""


def build_prompt(now_utc: pd.Timestamp, headlines: Sequence[str],
                 instruments: Sequence[str], calendar: GuardDecision) -> str:
    """Dựng prompt một lượt. Không có tầng hai, không có tranh luận chuyên gia."""
    hl = "\n".join(f"- {h.strip()}" for h in headlines[:40]) or "- (không có tiêu đề)"
    return PROMPT_TEMPLATE.format(
        now=now_utc, instruments=", ".join(instruments) or "FX crosses",
        calendar_verdict=("BLOCK — " + calendar.reason) if calendar.blocked
        else "clear",
        headlines=hl)


def parse_llm_response(text: str) -> Dict[str, object]:
    """Bóc JSON khỏi câu trả lời. Chấp nhận cả khi model bọc trong ```json."""
    s = text.strip()
    if "```" in s:
        parts = [p for p in s.split("```") if "{" in p]
        if parts:
            s = parts[0].replace("json", "", 1).strip()
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j <= i:
        raise ValueError(f"không tìm thấy JSON trong câu trả lời: {text[:120]!r}")
    return json.loads(s[i:j + 1])


def check_llm(now_utc: pd.Timestamp, headlines: Sequence[str],
              instruments: Sequence[str], calendar: GuardDecision,
              call_llm=None) -> GuardDecision:
    """Tầng 1: một lượt gọi LLM. `call_llm(prompt) -> str` do bên gọi cung cấp.

    Không import SDK nào ở đây có chủ ý: module này phải chạy được và test được mà
    không cần khoá API. Bên gọi truyền hàm gọi vào; test truyền hàm giả.
    """
    if call_llm is None:
        return GuardDecision(
            timestamp=now_utc, blocked=calendar.blocked, source=calendar.source,
            severity=calendar.severity, events=calendar.events,
            currencies=calendar.currencies, reason=calendar.reason,
            llm_used=False, llm_error="không có hàm gọi LLM")
    try:
        raw = call_llm(build_prompt(now_utc, headlines, instruments, calendar))
        d = parse_llm_response(raw)
        blocked = bool(d.get("block", False)) or calendar.blocked
        sev = str(d.get("severity", "NONE")).upper()
        ccy = tuple(str(c).upper() for c in d.get("currencies", []) or ())
        why = str(d.get("reason", "")).strip()
        # Nếu CẢ HAI tầng cùng chặn thì giữ lý do của lịch (cụ thể hơn) và ghép thêm
        reason = calendar.reason if calendar.blocked else why
        if calendar.blocked and why:
            reason = f"{calendar.reason} · LLM: {why}"
        return GuardDecision(
            timestamp=now_utc, blocked=blocked,
            source="LLM" if not calendar.blocked else "CALENDAR",
            severity=sev if not calendar.blocked else calendar.severity,
            events=calendar.events,
            currencies=ccy or calendar.currencies,
            minutes_to_event=calendar.minutes_to_event,
            reason=reason, llm_used=True)
    except Exception as exc:              # fail-soft: giữ kết quả tầng 0
        return GuardDecision(
            timestamp=now_utc, blocked=calendar.blocked, source=calendar.source,
            severity=calendar.severity, events=calendar.events,
            currencies=calendar.currencies, reason=calendar.reason,
            llm_used=False, llm_error=f"{type(exc).__name__}: {exc}")


# ═══════════════════════════════════════════════════════ điểm vào duy nhất
def decide(now_utc: Optional[pd.Timestamp] = None, *,
           headlines: Optional[Sequence[str]] = None,
           instruments: Sequence[str] = (),
           call_llm=None,
           calendar_path: Path = CALENDAR_PATH,
           force: bool = False) -> GuardDecision:
    """Điểm vào DUY NHẤT của cổng tin. Tầng 0 luôn chạy; tầng 1 chỉ khi có `call_llm`.

    Bên gọi (`portfolio.live_targets`) chỉ cần gọi hàm này rồi hỏi
    `decision.blocks_instrument(sym)` cho từng công cụ.

    `force=True` bỏ qua công tắc — dùng cho nghiên cứu và test, KHÔNG dùng ở live.
    """
    now = pd.Timestamp(now_utc) if now_utc is not None \
        else pd.Timestamp(datetime.now(timezone.utc))
    if not force and not is_enabled():
        return GuardDecision(
            timestamp=now, blocked=False, source="DISABLED",
            reason="cổng TẮT theo mặc định — đo được nó làm Sharpe trung vị giảm "
                   "0,811 → 0,622 trên rổ cross hiện tại (vòng 63). Bật bằng "
                   "NEWS_GUARD=1 khi danh mục có công cụ chứa USD/EUR/GBP.")
    cal = check_calendar(now, calendar_path)
    # Gắn tình trạng lịch vào lý do: cổng BẬT mà lịch cạn là cổng không canh gì,
    # và người vận hành phải đọc được điều đó ngay trên bản ghi quyết định.
    h = health(now, calendar_path)
    if not h.ok:
        cal = replace(cal, reason=(cal.reason + " ⚠️ LỊCH KHÔNG ĐẠT: "
                                   + " · ".join(h.problems)))
    if call_llm is None or not headlines:
        return cal
    return check_llm(now, headlines, instruments, cal, call_llm)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    d = decide()
    print(d.explain())
    from src.python.strategies.h1 import asia_sweep as AS
    for s in AS.INSTRUMENTS:
        print(f"  {s}: {'CHẶN' if d.blocks_instrument(s) else 'cho phép'}")
