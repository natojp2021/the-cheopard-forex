"""asia_sweep_core.py — ĐỘNG CƠ ASIA RANGE SWEEP. Bảy lớp, một máy trạng thái.

VÌ SAO LÀ MỘT ĐỘNG CƠ BẢY LỚP, KHÔNG PHẢI MỘT HÀM `if`
=======================================================
Bản đặc tả nghiệp vụ nói rõ điều này, và nó đúng: không được code

    if AsiaLow bị quét:  MUA

vì như vậy khi không vào lệnh, không ai biết nó dừng ở bước nào — và đó đúng là thứ
không truy vết được lúc 3 giờ sáng. Nên bảy lớp là bảy tầng DỮ LIỆU, và trạng thái
cũng là dữ liệu:

    Lớp 1  SESSION      mốc phiên, cửa sổ Á / London / NY         `minute_of_session`
    Lớp 2  ASIA RANGE   biên, độ rộng                             `prepare` -> `asia`
    Lớp 3  LIQUIDITY    PDH/PDL, cực trị tuần, equal high/low     `LiquidityMap`
    Lớp 4  SWEEP        độ sâu, râu/thân, vị trí đóng, thời điểm   trong `detect_setup`
    Lớp 5  REVERSAL     reclaim, MSS/CHoCH, FVG                   `_mss_after`, `_fvg`
    Lớp 6  CONTEXT      thiên hướng H1, thứ trong tuần, tin       `prepare` -> `bias`
    Lớp 7  CLASSIFIER   A+ / A / B / C / NO_TRADE                 `_grade`

    NO_DATA -> ASIA_INCOMPLETE
            -> RANGE_REJECTED            (setup xấu #1: biên Á ngoài dải)
            -> ARMED -> WINDOW_CLOSED    (setup xấu #5: không quét trong cửa sổ)
                     -> SWEPT_NO_RECLAIM (setup xấu #3: đóng ngoài biên = breakout)
                     -> BIAS_MISMATCH
                     -> GRADE_TOO_LOW    (setup xấu #4 / #6)
                     -> RR_TOO_LOW
                     -> NO_ROOM          (setup xấu #8: giá đã đi hết biên Á)
                     -> NEWS_WINDOW      (setup xấu #7: ±30 phút quanh tin lớn)
                     -> ENTRY

Mỗi lần chuyển trạng thái ghi lý do KÈM SỐ ĐO, và `SweepDecision.explain()` in ra
đúng chuỗi đó. Đây là nguyên liệu cho `rule_trace.RuleTrace` ở tầng trên.

VÀ VÌ SAO CHỈ CÓ MỘT ĐƯỜNG CODE
================================
Quy tắc cứng của repo: **kiểm định phải chạy trên cùng đường code với sản xuất**. Một
"lab" riêng để quét nhanh luôn thiếu một nhánh nào đó của động cơ thật, và con số nó
in ra là con số của một chiến lược không tồn tại. Nên `backtest()`, `live_decision()`
và mọi script ở `research/fx/` đều đi qua đúng `detect_setup()` và `simulate_path()`
dưới đây — không có đường thứ hai.

BỐN SETUP ĐƯỢC PHÂN HẠNG ĐỂ ĐO RIÊNG
=====================================
Bản đặc tả nghiệp vụ yêu cầu backtest TỪNG setup độc lập, để trả lời "yếu tố nào
thực sự tạo ra lợi nhuận" thay vì trộn một đống khái niệm rồi không biết cái nào
work. `setup_grade` là trường làm việc đó, và `stats_by_grade()` là bảng đọc nó:

    A+   reclaim + MSS + FVG + thuận thiên hướng + biên Á TRÙNG một mức thanh khoản
         thật (PDH/PDL/cực trị tuần) + phiên Á CHƯA tự ăn PDH/PDL
    A    reclaim + MSS + thuận thiên hướng
    B    reclaim + thuận thiên hướng
    C    reclaim, không thuận thiên hướng
    NO_TRADE  một trong bảy setup xấu kích hoạt

`min_grade` là ngưỡng nhận. Đặt "A+" thì chỉ giao dịch hạng cao nhất.

BẢY SETUP XẤU, TỪNG CÁI CÓ NGƯỠNG SỐ
=====================================
    #1 biên Á ngoài dải               `range_min_pips` / `range_max_pips`
    #2 xuyên quá sâu (hoặc quá nông)  `depth_min_pips` / `depth_max_pips`
    #3 không reclaim                  nến quét ĐÓNG ngoài biên -> breakout thật
    #4 không displacement / MSS       hạ hạng xuống B/C; `min_grade` quyết định bỏ
    #5 quá muộn                       ngoài `exec_start_utc`..`exec_end_utc`
    #6 phiên Á ĐÃ ăn thanh khoản HTF  `asia_took_pdh` / `asia_took_pdl` -> hạ hạng
    #8 giá đã đi hết biên Á           `min_room_r` — chỗ còn lại tới biên đối diện
    #7 tin tác động mạnh              `news_window_min` = 30 phút mỗi bên quanh
                                      NFP · CPI · FOMC · ECB · BOE. Đo được: chặn
                                      1,9% số lệnh, tiền -0,2%, MaxDD 8,90% -> 8,28%

⚠️ CẢNH BÁO BẮT BUỘC ĐỌC TRƯỚC KHI CẤP VỐN
==========================================
Hướng này ĐÃ ĐƯỢC ĐO và nằm trong `registry.REJECTED_DIRECTIONS` dưới tên
`AsiaRangeSweepFade`. 4.963 lệnh trên đúng ba cặp này, đủ chi phí:

    R/lệnh GỘP   +0,007 (EURUSD) · -0,044 (GBPUSD) · -0,008 (USDJPY)
    lưới lọc     54 ô n>=30 -> 0 ô t>+2, 26 ô t<-2
    cửa sổ Á     8 định nghĩa x 3 cặp -> 0/24 ô dương, 24/24 ô t<-2

Số đo đầy đủ: `docs/the-asia-sweep/00_KET_QUA_DO_LUONG.md`. Module này được viết theo
YÊU CẦU RÕ RÀNG của chủ tài khoản sau khi đã được trình bày kết quả trên, để chạy DEMO
và tự kiểm chứng. `stage` giữ ở `FORWARD_TEST`.

NGUỒN — thứ tự ưu tiên theo `CLAUDE.md`
=======================================
Học thuật (ưu tiên 1):
  · Osler (2003) "Stop-Loss Orders and Price Cascades in Currency Markets", FRBNY
    Staff Report 150. USD/JPY · USD/DEM · GBP/USD, quote phút-theo-phút, giờ New
    York, 01/1996-04/1998. Stop-loss = 43% khối lượng lệnh, 45% giá trị. Cụm
    stop-loss nằm NGAY NGOÀI mốc tròn (14,3% lệnh stop-buy có giá khớp đuôi [01,10]
    so với 6,9% đuôi [91,00]; lệnh >= $50M: 62% giá trị trong đuôi [90,100]/[01,09])
    -> cơ sở của dải độ sâu xuyên và đệm SL 3-4 pip. Hiệu ứng dòng lệnh điều kiện
    MẠNH HƠN khi thanh khoản THẤP -> cơ sở của việc phiên Á đáng quan tâm.
    ⚠️ Kết luận CHÍNH của Osler NGƯỢC với hướng fade: cụm stop làm giá CHẢY TIẾP (còn
    ý nghĩa >= 2 GIỜ), còn đảo chiều thuộc cụm take-profit, chỉ +4,5 điểm % (59,3%
    vs 54,8%) và chết DƯỚI 30 PHÚT.
    `docs/the-asia-sweep/references/Carol_Osler_FED_NY_sr150_StopLoss_Orders.md`
  · Curcio & Goodhart (1992) LSE FMG DP 142 — phá vỡ S/R (mức cập nhật ĐÚNG tại giờ
    mở London và Tokyo) sinh lợi nhuận theo HƯỚNG PHÁ VỠ, t = 1,27-2,85, sống sót
    chi phí rộng hơn 99% spread quan sát. NGƯỢC hướng này.
  · Neely & Weller (2003) JIMF 22(2):223-237 — FX intraday: "no evidence of excess
    returns" sau chi phí thực tế và giờ giao dịch thực tế. NGƯỢC.
  · Hsu, Taylor & Wang (2016) J. Int. Economics 102:188-208 — 30 tiền tệ DM+EM,
    45 năm, > 21.000 luật, Step-SPA: họ range/channel breakout CHẾT từ 2006. NGƯỢC.
  · Aronson (2007) "Evidence-Based Technical Analysis" ch. 6 — 6.402 luật trên
    S&P 500, luật tốt nhất p = 0,0005 đơn luật -> 0 luật sống sót hiệu chỉnh
    data-mining. Cổng bắt buộc cho mọi lưới giờ.

Sách / tài liệu nghiệp vụ (ưu tiên 3 — lấy NGUYÊN TẮC, không lấy số làm bằng chứng):
  · Lien (2008) "Day Trading and Swing Trading the Currency Market" 2nd ed. Wiley
    tr. 69: "large investment banks and hedge funds are known to try to use the Asian
    session to run important stop and option barrier levels" — cơ chế, KHÔNG có số.
    tr. 73: biên độ 08:00-12:00 EST chiếm 70% biên phiên Âu và 80% biên phiên Mỹ ->
    cơ sở của cửa sổ khớp lệnh.
  · Villahermosa (2019) "The Wyckoff Methodology in Depth" tr. 209 — nến
    "significant" phải ĐÓNG ở NỬA đối diện biên nến; đây là ngưỡng đo được DUY NHẤT
    mà cả sách cho. tr. 142-152: spring/upthrust/UTAD chỉ được gọi tên khi nó KHỞI
    PHÁT cú phá vỡ; sách tự thừa nhận tr. 172 là "impossible to create a strategy
    with 100% objective rules".
  · ICT 2022 Mentorship tr. 50-51 (MSS phải có displacement VÀ candle CLOSE, không
    phải wick), tr. 85-91 (FVG = mô thức 3 nến), tr. 86-87 ("phá rồi quay ngay vào
    range" KHÔNG phải displacement — đúng điều kiện cần cho chiều fade), tr. 99
    (Asian range = high/low 20:00-00:00 NY), tr. 158 (Judas quét 10-20 pip ngoài
    biên), tr. 224-226 (OTE 0,62-0,79, sweet spot 0,705). Toàn sách KHÔNG có
    winrate, không R:R, không mẫu thống kê nào.
  · Chesler (2004) "hikkake" qua Kirkpatrick & Dahlquist (2011) tr. 379-380 — mẫu
    fade-breakout-giả DUY NHẤT trong kho có ngưỡng số: đảo chiều phải xảy ra TRONG
    3 NẾN. Đây là nguồn của `mss_max_bars = 3`.
  · Crabel qua Kirkpatrick & Dahlquist (2011) tr. 386-389 — HV6 < 50% HV100 mới đủ
    điều kiện nhận tín hiệu NR4; và (NGƯỢC hướng này) breakout xuyên SỚM thành công
    cao hơn, setup wide-range thua xa setup NR.
  · Grimes (2012) tr. 183-186 — gọi kế hoạch "đảo chiều khi mức phá vỡ không giữ" là
    "a futile plan"; tiêu chí đúng là THẤT BẠI CỦA NHỊP ĐẦU TIÊN, không phải việc giá
    xuyên lại mức. Đây là lý do điều kiện reclaim ở đây đòi ĐÓNG NẾN, không chỉ chạm.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.python.shared import asset_profile as AP
from src.python.strategies.rulebook import Rule, RuleBook

# ═══════════════════════════════════════════════════════════ Lớp 1 — SESSION
# Mốc neo PHIÊN: 21:00 UTC — trước Tokyo mở (00:00 UTC) và sau khi New York đóng, nên
# biên Á, cửa sổ London và cửa sổ NY nằm trong CÙNG một phiên và không cửa sổ nào bị
# cắt qua nửa đêm. Quyết định KỸ THUẬT, không phải tham số chiến lược.
SESSION_ANCHOR_HOUR = 21

# Số phút của một nến, theo tên khung. SSOT cho phép cộng "giá mở nến kế tiếp": rải
# số 15 hay 60 dọc file là cách để đổi khung mà quên một chỗ, và chỗ quên đó chính là
# một lỗi NHÌN TRƯỚC im lặng — mô phỏng bắt đầu ngay TRONG nến tín hiệu.
TF_MINUTES: Dict[str, int] = {"M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240}

# Thứ hạng setup. Số lớn = tốt hơn, để so sánh bằng `>=`.
GRADES: Dict[str, int] = {"NO_TRADE": 0, "C": 1, "B": 2, "A": 3, "A+": 4}


def minute_of_session(hour_utc: float) -> int:
    """Phút-trong-phiên của một giờ UTC. 00:00 UTC = phút 180."""
    return int(round((hour_utc - SESSION_ANCHOR_HOUR) % 24 * 60))


# ═══════════════════════════════════════════════════════════════════ cấu hình
@dataclass(frozen=True)
class SweepConfig:
    """Tham số của MỘT công cụ. Mọi ngưỡng tính bằng PIP của chính cặp đó."""
    name: str
    instrument: str

    # ── Lớp 1: khung giờ (UTC). Biên Á neo UTC vì Nhật KHÔNG có DST.
    asia_start_utc: float = 0.0
    asia_end_utc: float = 7.0
    exec_start_utc: float = 7.0
    exec_end_utc: float = 15.0
    flat_utc: float = 20.0

    # ── Lớp 2: bộ lọc biên Á (pip) — setup xấu #1
    range_min_pips: float = 15.0
    range_max_pips: float = 45.0

    # ── Lớp 4: chữ ký cú quét (pip) — setup xấu #2
    depth_min_pips: float = 2.0
    depth_max_pips: float = 25.0
    wick_body_min: float = 0.5          # râu ngoài biên / thân nến

    # ── Lớp 5: xác nhận đảo chiều
    require_mss: bool = False           # đòi MSS/CHoCH mới vào
    require_fvg: bool = False           # đòi có FVG mới vào
    mss_max_bars: int = 3               # Chesler/hikkake: đảo chiều TRONG 3 nến
    fvg_min_pips: float = 1.0           # khoảng hở nhỏ hơn ngần này = nhiễu làm tròn

    # ── Lớp 3: bản đồ thanh khoản
    equal_tol_pips: float = 2.0         # hai mức cách nhau dưới ngần này = "equal"
    liq_lookback_days: int = 5          # cực trị tuần lấy từ bao nhiêu phiên đã đóng

    # ── LUẬT THOÁT. Một dừng lỗ, một chốt lời, một lần dời breakeven. Hết.
    #
    # KHÔNG có chốt một phần, KHÔNG có TP theo cấu trúc giá. Cả hai đã bị xoá, và
    # xoá là quyết định chứ không phải thiếu sót: một luật thoát mà server broker giữ
    # được toàn bộ (một `sl`, một `tp`, một lần `modify`) thì backtest và live thoát
    # ở ĐÚNG cùng một giá. Mỗi nhánh thêm vào là một chỗ live có thể lệch mà không ai
    # biết — và một nhánh như vậy đã từng ghi 0 R cho một lệnh thật ra mất 1 R.
    sl_buffer_pips: float = 3.0

    # Chốt lời cách giá vào đúng `tp_r_multiple` lần khoảng cách dừng lỗ. R:R vì vậy
    # là HẰNG SỐ và mọi lệnh so được với nhau — kỳ vọng chỉ còn phụ thuộc tỷ lệ thắng.
    tp_r_multiple: float = 3.0

    # Khi giá đi được `be_trigger_r` lần R theo chiều mình thì dời dừng lỗ về giá vào
    # CỘNG đúng phí khứ hồi. Chạm mức đó là HOÀ THẬT, không phải hoà gộp rồi âm sau
    # phí. `be_extra_pips` là đệm thêm nếu muốn dương một chút. 0 = tắt breakeven.
    be_trigger_r: float = 1.0
    be_extra_pips: float = 0.0

    # Trailing liên tục SAU khi breakeven đã kích hoạt: giữ dừng lỗ cách giá tốt nhất
    # `trail_r` lần R. 0 = KHÔNG trailing, dừng lỗ nằm im ở mức breakeven.
    trail_r: float = 0.0

    # CHỖ CÒN LẠI TRONG BIÊN Á tại điểm vào, tính bằng R. Setup xấu #8.
    #
    # MSS có thể xác nhận muộn tới `mss_max_bars` nến sau cú quét, và trong khoảng đó
    # giá có thể đã chạy xuyên cả biên Á sang phía đối diện. Vào lệnh lúc đó là BÁN ở
    # đáy biên (hoặc MUA ở đỉnh biên) — đúng chiều luật, sai hoàn toàn về vị trí.
    #
    # Đo được: bỏ điều kiện này thêm 600 lệnh và kéo kỳ vọng từ +0,0147 xuống
    # -0,0177 R/lệnh. Nó là một bộ lọc THẬT, không phải một chi tiết hiện thực.
    min_room_r: float = 0.0

    # ── Lớp 6: bối cảnh
    use_bias: bool = True
    bias_ema_h1: int = 50

    # ── Lớp 7: ngưỡng nhận
    min_grade: str = "C"

    # ── setup xấu #7: cửa sổ quanh tin tác động mạnh, tính bằng PHÚT mỗi bên.
    # 0 = tắt. Xem `ai/news_guard.py` cho bảng đo chọn con số 30.
    news_window_min: float = 30.0

    # ── khung
    signal_tf: str = "H1"               # khung BỐI CẢNH (biên Á, thiên hướng)
    exec_tf: str = "H1"                 # khung PHÁT HIỆN cú quét và KHỚP LỆNH

    @property
    def pip(self) -> float:
        return AP.get(self.instrument).pip

    @property
    def exec_minutes(self) -> int:
        """Số phút một nến khung khớp lệnh. Khung lạ thì NỔ, không đoán 15."""
        try:
            return TF_MINUTES[self.exec_tf]
        except KeyError:
            raise ValueError(
                f"{self.name}: khung khớp lệnh {self.exec_tf!r} không có trong "
                f"TF_MINUTES {sorted(TF_MINUTES)}. Thêm vào bảng thay vì để hàm mô "
                f"phỏng đoán độ dài nến.") from None

    @property
    def family(self) -> str:
        """Tên HỌ tín hiệu. `name` là `<HỌ>:<CÔNG CỤ>`, họ là phần trước dấu hai chấm."""
        return self.name.split(":")[0]

    @property
    def min_grade_rank(self) -> int:
        try:
            return GRADES[self.min_grade]
        except KeyError:
            raise ValueError(f"{self.name}: min_grade {self.min_grade!r} lạ; "
                             f"chỉ có {sorted(GRADES)}") from None


# ═══════════════════════════════════════════════════════ Lớp 3 — LIQUIDITY MAP
@dataclass(frozen=True)
class LiquidityMap:
    """Các mức thanh khoản HTF có sẵn LÚC chốt biên Á. Không mức nào nhìn trước.

    VÌ SAO LỚP NÀY TỒN TẠI: "biên Á bị quét" đo được là gần như VÔ NGHĨA — 99,4%
    phiên bị quét, mà một mức BẤT KỲ cách đó 0,35 biên cũng bị quét 91,6% (xem
    `docs/the-asia-sweep/00_KET_QUA_DO_LUONG.md` §5). Cái CÓ THỂ mang thông tin là
    biên Á TRÙNG một mức thanh khoản thật — PDH/PDL, cực trị tuần, hay hai mức bằng
    nhau (equal highs/lows, nơi stop dồn thành cụm theo Osler).
    """
    pdh: float = float("nan")           # previous day high
    pdl: float = float("nan")
    pwh: float = float("nan")           # cực trị `liq_lookback_days` phiên đã đóng
    pwl: float = float("nan")
    asia_took_pdh: bool = False         # setup xấu #6
    asia_took_pdl: bool = False
    equal_high: bool = False            # biên Á TRÊN trùng một mức HTF
    equal_low: bool = False

    def confluent(self, sweep_side: int) -> bool:
        """Biên bị quét có TRÙNG một mức thanh khoản thật không?"""
        return bool(self.equal_high if sweep_side > 0 else self.equal_low)

    @property
    def took_htf(self) -> bool:
        return bool(self.asia_took_pdh or self.asia_took_pdl)


# ═══════════════════════════════════════════════════════════════════ quyết định
@dataclass(frozen=True)
class SweepDecision:
    """Quyết định cho MỘT phiên của MỘT công cụ. Đọc được, ghi sổ được."""
    instrument: str
    asof: str
    state: str
    # Tên HỌ tín hiệu, phải khớp `RuleBook.trace_signal_name`. Đây là mối nối giữa
    # thẻ luật KHAI BÁO và bản ghi RUNTIME: lệch nhau thì khi một lệnh thua bất
    # thường, không đối chiếu được "luật cho phép gì" với "hôm nay đã làm gì". Công
    # cụ nằm ở trường `instrument` riêng, nên một họ chạy nhiều cặp vẫn truy vết
    # được từng cặp.
    signal_name: str = ""
    setup_grade: str = "NO_TRADE"
    side: int = 0                       # +1 MUA · -1 BÁN · 0 không vào
    entry_px: float = float("nan")
    stop_px: float = float("nan")
    tp_px: float = float("nan")
    sl_pips: float = float("nan")
    rr: float = float("nan")
    asia_high: float = float("nan")
    asia_low: float = float("nan")
    asia_range_pips: float = float("nan")
    depth_pips: float = float("nan")
    wick_body: float = float("nan")
    close_pos: float = float("nan")
    h1_bias: int = 0
    sweep_side: int = 0
    sweep_time: str = ""
    entry_time: str = ""                # nến KHỚP LỆNH; xem `simulate_path`
    has_mss: bool = False
    has_fvg: bool = False
    fvg_mid: float = float("nan")
    liq_confluence: bool = False
    asia_took_htf: bool = False
    steps: Tuple[Tuple[str, bool, str], ...] = ()

    @property
    def enter(self) -> bool:
        return self.state == "ENTRY" and self.side != 0

    def explain(self) -> str:
        L = [f"{self.instrument} · {self.asof} · {self.state} · hạng "
             f"{self.setup_grade}"]
        for code, ok, detail in self.steps:
            L.append(f"   {'PASS' if ok else 'STOP'} {code:12} {detail}")
        if self.enter:
            L.append(f"   -> {'MUA' if self.side > 0 else 'BÁN'} @ {self.entry_px:.5f}"
                     f" · SL {self.stop_px:.5f} ({self.sl_pips:.1f} pip)"
                     f" · TP {self.tp_px:.5f} (R:R {self.rr:.2f})")
        return "\n".join(L)


# ═══════════════════════════════════════════════════════════════════ chuẩn bị
def _session_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    shifted = out.index - pd.Timedelta(hours=SESSION_ANCHOR_HOUR)
    out["session"] = shifted.normalize()
    out["m"] = ((shifted - shifted.normalize()).total_seconds() // 60).astype(np.int32)
    return out


def resample(m1: pd.DataFrame, rule: str) -> pd.DataFrame:
    """M1 -> khung lớn hơn. `spread_usd` lấy TRUNG BÌNH: phí phải trả là phí lúc khớp."""
    cols = dict(open=("open", "first"), high=("high", "max"),
                low=("low", "min"), close=("close", "last"),
                n=("close", "size"))
    if "spread_usd" in m1.columns:
        cols["spread_usd"] = ("spread_usd", "mean")
    o = m1.resample(rule).agg(**cols)
    return o[o["n"] > 0].drop(columns="n")


@dataclass
class Prepared:
    """Dữ liệu đã dựng sẵn cho cả mẫu. Dựng MỘT lần, dùng cho mọi phiên."""
    m1: pd.DataFrame
    exec_bars: pd.DataFrame             # khung KHỚP LỆNH (`cfg.exec_tf`)
    h1: pd.DataFrame
    asia: pd.DataFrame                  # index = session · hi · lo · rng · nbar
    bias: pd.Series                     # index = session · +1/-1
    liq: Dict[pd.Timestamp, LiquidityMap]
    sessions: List[pd.Timestamp]
    # Mốc công bố tin tác động mạnh, UTC naive. Rỗng = không lọc tin.
    news_times: np.ndarray = field(default_factory=lambda: np.array([], dtype="M8[ns]"))


def prepare(m1: pd.DataFrame, cfg: SweepConfig) -> Prepared:
    """Dựng đủ sáu lớp bối cảnh — KHÔNG dùng dữ liệu tương lai.

    Biên Á chốt tại `asia_end_utc`; thiên hướng đọc từ nến H1 ĐÃ ĐÓNG cuối cùng trước
    mốc đó; bản đồ thanh khoản chỉ dùng các PHIÊN ĐÃ ĐÓNG. Cả ba đều là thông tin có
    sẵn lúc cửa sổ khớp lệnh mở.
    """
    pip = cfg.pip
    s1 = _session_frame(m1)
    ex = _session_frame(resample(m1, f"{cfg.exec_minutes}min"))
    h1 = resample(m1, "1h")
    h1["ema"] = h1["close"].ewm(span=cfg.bias_ema_h1, adjust=False).mean()
    h1 = _session_frame(h1)

    ma0 = minute_of_session(cfg.asia_start_utc)
    ma1 = minute_of_session(cfg.asia_end_utc)

    # ── Lớp 2: biên Á
    a = s1[(s1["m"] >= ma0) & (s1["m"] < ma1)]
    g = a.groupby("session")
    asia = pd.DataFrame({"hi": g["high"].max(), "lo": g["low"].min(),
                         "nbar": g.size()})
    # Phiên thiếu > 30% nến (lễ, nửa phiên) không có biên Á đáng tin -> bỏ hẳn.
    asia = asia[asia["nbar"] >= int(0.70 * (ma1 - ma0))]
    asia = asia[(asia["hi"] - asia["lo"]) > 0]
    asia["rng"] = asia["hi"] - asia["lo"]

    # ── Lớp 6: thiên hướng H1 tại nến đóng lúc `asia_end_utc`
    bb = h1[h1["m"] == ma1 - 60]
    bias = pd.Series(np.where(bb["close"] > bb["ema"], 1, -1),
                     index=pd.Index(bb["session"].to_numpy(), name="session"))
    bias = bias[~bias.index.duplicated(keep="last")]

    # ── Lớp 3: bản đồ thanh khoản, từ cực trị TOÀN PHIÊN của các phiên ĐÃ ĐÓNG
    day = s1.groupby("session").agg(hi=("high", "max"), lo=("low", "min"),
                                    n=("close", "size"))
    day = day[day["n"] > 600]
    keys = list(day.index)
    pos = {k: i for i, k in enumerate(keys)}
    tol = cfg.equal_tol_pips * pip
    liq: Dict[pd.Timestamp, LiquidityMap] = {}
    for sess in asia.index:
        i = pos.get(sess)
        if i is None or i < 1:
            liq[sess] = LiquidityMap()
            continue
        prev = day.iloc[i - 1]
        pdh, pdl = float(prev["hi"]), float(prev["lo"])
        wk = day.iloc[max(0, i - cfg.liq_lookback_days):i]
        pwh = float(wk["hi"].max()) if len(wk) else float("nan")
        pwl = float(wk["lo"].min()) if len(wk) else float("nan")
        ah, al = float(asia.at[sess, "hi"]), float(asia.at[sess, "lo"])
        near = lambda x, y: bool(np.isfinite(y)) and abs(x - y) <= tol
        liq[sess] = LiquidityMap(
            pdh=pdh, pdl=pdl, pwh=pwh, pwl=pwl,
            # setup xấu #6: phiên Á TỰ ăn thanh khoản lớn trước khi London vào
            asia_took_pdh=bool(ah > pdh), asia_took_pdl=bool(al < pdl),
            equal_high=near(ah, pdh) or near(ah, pwh),
            equal_low=near(al, pdl) or near(al, pwl))

    return Prepared(m1=s1, exec_bars=ex, h1=h1, asia=asia, bias=bias, liq=liq,
                    sessions=list(asia.index),
                    news_times=_news_times(cfg))


def _news_times(cfg: SweepConfig) -> np.ndarray:
    """Mốc công bố tin tác động mạnh, lấy từ `ai/news_guard.py` — CÙNG nguồn với live.

    VÌ SAO LỌC TIN NẰM Ở ĐÂY, KHÔNG CHỈ Ở `order_plan`
    ==================================================
    `order_plan` có cổng tin cho đường LIVE. Nếu backtest KHÔNG có cùng bộ lọc thì hai
    bên giao dịch hai tập lệnh khác nhau, và mọi con số công bố mô tả một chiến lược
    mà live không chạy. Đặt bộ lọc vào CHÍNH `detect_setup` là cách duy nhất để hai
    đường không thể lệch.

    Không nạp được lịch thì trả rỗng — KHÔNG chặn gì. Đây là fail-OPEN có chủ ý và chỉ
    ở tầng NGHIÊN CỨU: một lịch thiếu không được làm backtest im lặng bỏ hết lệnh (kết
    quả sẽ là "chiến lược không vào lệnh nào" và trông như một lỗi khác hẳn). Ở tầng
    LIVE thì ngược lại — `engine` fail-CLOSED khi không đánh giá được cổng tin.
    """
    if cfg.news_window_min <= 0:
        return np.array([], dtype="M8[ns]")
    try:
        from src.python.ai import news_guard as NG

        df = NG.load_calendar()
        if df is None or df.empty:
            return np.array([], dtype="M8[ns]")
        big = df[df["event"].astype(str).str.upper().isin(NG.HIGH_IMPACT)]
        t = pd.to_datetime(big["time"])
        if getattr(t.dt, "tz", None) is not None:
            t = t.dt.tz_convert("UTC").dt.tz_localize(None)
        return np.sort(t.to_numpy())
    except Exception:                                          # pragma: no cover
        return np.array([], dtype="M8[ns]")


def _in_news_window(times: np.ndarray, when: pd.Timestamp,
                    window_min: float) -> bool:
    """`when` có nằm trong ±`window_min` phút quanh một mốc tin nào không."""
    if times.size == 0 or window_min <= 0:
        return False
    i = int(np.searchsorted(times, np.datetime64(when)))
    for j in (i - 1, i):
        if 0 <= j < times.size:
            gap = abs((times[j] - np.datetime64(when)) / np.timedelta64(1, "m"))
            if gap <= window_min:
                return True
    return False


# ═══════════════════════════════════════════════════════════ Lớp 5 — REVERSAL
def _mss_confirm(bars: pd.DataFrame, i_sweep: int, sweep_side: int,
                 cfg: SweepConfig) -> int:
    """Chỉ số nến mà CLOSE của nó xác nhận MSS/CHoCH. -1 nếu không có.

    ⚠️ TRẢ VỀ CHỈ SỐ, KHÔNG TRẢ VỀ BOOL — và đây là chỗ đã có một lỗi NHÌN TRƯỚC
    thật, bắt được ngày 25/08/2026 ngay trong lượt đo đầu tiên.
    ==========================================================================
    Bản đầu của hàm này trả `bool`: "có MSS trong 3 nến sau cú quét không". Nhưng
    lệnh lại khớp ở giá MỞ của nến `i_sweep + 1`, tức quyết định dùng CLOSE của nến
    đó và hai nến sau nó — thông tin của 1 đến 3 GIỜ SAU khi vào lệnh.

    Hậu quả đo được, và nó trông rất giống một phát hiện:

        hạng A (có MSS)      winrate 73,0% / 77,0% / 67,8%
                             R ròng +0,74 / +0,76 / +0,71 · t = +14,6 / +12,6 / +8,1
        hạng B (không MSS)   winrate 17,5% / 15,4% / 19,0%
                             R ròng -0,65 / -0,70 / -0,57 · t = -22,4 / -16,9 / -13,7

    Tách hạng hoàn hảo trên cả ba cặp với t hai chữ số là chữ ký của vòng lặp kín,
    không phải của biên giao dịch: "MSS đã xảy ra" nghĩa là giá ĐÃ đi đúng chiều ta
    muốn sau khi vào lệnh, nên hạng A thắng 73% là chuyện tất yếu về mặt số học.

    Bản này trả CHỈ SỐ nến xác nhận, và `detect_setup` khớp lệnh ở giá MỞ nến KẾ
    TIẾP nến đó.

    Định nghĩa MSS theo ICT 2022 tr. 50-51, hai điều kiện và cả hai kiểm được:
      (1) giá phá qua cực trị vi mô gần nhất NGƯỢC chiều cú quét
      (2) bằng một **candle CLOSE**, không phải wick — "phá rồi quay ngay vào range"
          KHÔNG phải displacement (tr. 86-87)

    Cửa sổ `mss_max_bars` = 3 nến lấy từ mẫu hikkake của Chesler (2004, qua
    Kirkpatrick & Dahlquist tr. 379-380): mẫu fade-breakout-giả DUY NHẤT trong kho có
    ngưỡng số, và ngưỡng của nó là "đảo chiều trong 3 nến". ICT KHÔNG cho ngưỡng nào
    cho "quick shift" hay "energetic", nên phần định lượng duy nhất ở đây là cực trị
    vi mô + close.
    """
    n = len(bars)
    if i_sweep + 1 >= n:
        return -1
    lo0 = float(bars["low"].iloc[max(0, i_sweep - 1):i_sweep + 1].min())
    hi0 = float(bars["high"].iloc[max(0, i_sweep - 1):i_sweep + 1].max())
    end = min(n, i_sweep + 1 + cfg.mss_max_bars)
    for j in range(i_sweep + 1, end):
        c = float(bars["close"].iloc[j])
        if (c < lo0) if sweep_side > 0 else (c > hi0):
            return j
    return -1


def _fvg(bars: pd.DataFrame, i_sweep: int, sweep_side: int,
         cfg: SweepConfig, i_last: int) -> Tuple[bool, float]:
    """Fair Value Gap 3 nến sau cú quét. Trả (có, giá GIỮA khoảng hở).

    ICT 2022 tr. 85-91: mô thức BA nến, nến giữa tạo khoảng hở. Với lệnh BÁN (quét
    biên trên) cần bearish FVG — `low[k-1] > high[k+1]`, khoảng hở
    [high[k+1]; low[k-1]]. Đặc tả vào ở 50% khoảng hở; con số đó tương đương vùng
    sweet spot OTE 0,705 (tr. 224-226) nhưng 50% là mức đặc tả nói rõ.

    ICT KHÔNG cho độ lớn tối thiểu của FVG, nên `fvg_min_pips` là ngưỡng của HỆ NÀY:
    một khoảng hở 0,3 pip là nhiễu làm tròn, không phải mất cân bằng.

    `i_last` là nến CUỐI CÙNG đã đóng lúc ra quyết định. Mô thức 3 nến hoàn thành ở
    nến `k+1`, nên chỉ nhận FVG có `k + 1 <= i_last` — cùng lý do với `_mss_confirm`:
    một FVG chưa đóng đủ 3 nến là thông tin của tương lai.
    """
    pip = cfg.pip
    n = len(bars)
    hi_k = min(n - 1, i_sweep + cfg.mss_max_bars, i_last)
    for k in range(i_sweep, max(i_sweep, hi_k)):
        if k - 1 < 0 or k + 1 > i_last or k + 1 >= n:
            continue
        lo_prev = float(bars["low"].iloc[k - 1])
        hi_prev = float(bars["high"].iloc[k - 1])
        hi_next = float(bars["high"].iloc[k + 1])
        lo_next = float(bars["low"].iloc[k + 1])
        if sweep_side > 0:                            # lệnh BÁN
            if (lo_prev - hi_next) >= cfg.fvg_min_pips * pip:
                return True, (lo_prev + hi_next) / 2.0
        else:                                         # lệnh MUA
            if (lo_next - hi_prev) >= cfg.fvg_min_pips * pip:
                return True, (lo_next + hi_prev) / 2.0
    return False, float("nan")


# ═══════════════════════════════════════════════════════════ Lớp 7 — CLASSIFIER
def _grade(*, aligned: bool, has_mss: bool, has_fvg: bool, confluent: bool,
           took_htf: bool) -> str:
    """Hạng setup. Thứ tự điều kiện là thứ tự QUAN TRỌNG, không phải tuỳ ý.

    `took_htf` (setup xấu #6 — phiên Á đã tự ăn PDH/PDL) HẠ hạng: nếu thanh khoản
    HTF đã bị lấy trong phiên Á thì cú quét ở London không còn là cú quét một cụm
    stop chưa ai chạm.
    """
    if not aligned:
        return "C"
    if has_mss and has_fvg and confluent and not took_htf:
        return "A+"
    if has_mss:
        return "A"
    return "B"


# ═══════════════════════════════════════════════════════════════════ phát hiện
def detect_setup(p: Prepared, session: pd.Timestamp, cfg: SweepConfig,
                 *, upto_minute: Optional[int] = None) -> SweepDecision:
    """Quyết định cho MỘT phiên. `upto_minute` giới hạn thông tin (dùng cho live).

    Trả `SweepDecision` ở trạng thái XA NHẤT mà phiên đó đạt được. Trạng thái KHÔNG
    vào lệnh vẫn được trả kèm lý do — `decision_log` ghi cả HOLD/SKIP, vì khi live
    lệch khỏi backtest thì thứ cần biết trước tiên là nó lệch ở BƯỚC nào.
    """
    pip = cfg.pip
    steps: List[Tuple[str, bool, str]] = []
    asof = str(session.date())

    def mk(state: str, **kw) -> SweepDecision:
        return SweepDecision(instrument=cfg.instrument, asof=asof, state=state,
                             signal_name=cfg.family, steps=tuple(steps), **kw)

    if session not in p.asia.index:
        steps.append(("asia_range", False, "phiên thiếu > 30% nến phiên Á"))
        return mk("ASIA_INCOMPLETE")
    row = p.asia.loc[session]
    hi, lo, rng = float(row["hi"]), float(row["lo"]), float(row["rng"])
    rng_pips = rng / pip
    lq = p.liq.get(session, LiquidityMap())
    base = dict(asia_high=hi, asia_low=lo, asia_range_pips=rng_pips)

    # ── setup xấu #1
    if not (cfg.range_min_pips <= rng_pips <= cfg.range_max_pips):
        steps.append(("asia_range", False,
                      f"biên Á {rng_pips:.1f} pip ngoài [{cfg.range_min_pips:.0f}; "
                      f"{cfg.range_max_pips:.0f}] — setup xấu #1"))
        return mk("RANGE_REJECTED", **base)
    steps.append(("asia_range", True, f"biên Á {rng_pips:.1f} pip trong dải"))

    b = int(p.bias.get(session, 0))
    if cfg.use_bias and b == 0:
        steps.append(("h1_bias", False, "không có nến H1 đóng lúc chốt biên Á"))
        return mk("ASIA_INCOMPLETE", **base)
    steps.append(("h1_bias", True,
                  f"H1 {'TĂNG' if b > 0 else 'GIẢM'} (close vs EMA{cfg.bias_ema_h1})"))
    steps.append(("liquidity", True,
                  f"PDH {lq.pdh:.5f} · PDL {lq.pdl:.5f} · trùng mức HTF trên/dưới "
                  f"{int(lq.equal_high)}/{int(lq.equal_low)} · phiên Á đã ăn PDH/PDL "
                  f"{int(lq.took_htf)}"))
    base["h1_bias"] = b

    m0 = minute_of_session(cfg.exec_start_utc)
    m_end = minute_of_session(cfg.exec_end_utc)
    if upto_minute is not None:
        m_end = min(m_end, upto_minute)
    sess_bars = p.exec_bars[p.exec_bars["session"] == session]
    # `detect` = phần được phép ĐỌC để ra quyết định: chỉ nến trong cửa sổ khớp lệnh,
    # và ở live chỉ nến đã đóng (`upto_minute`). Mọi phép quét cú quét, MSS và FVG
    # chạy trên `detect`; `sess_bars` chỉ dùng để lấy giá MỞ nến vào lệnh. Tách hai
    # khung là cách để một lỗi nhìn trước không thể lặng lẽ quay lại.
    detect = sess_bars[sess_bars["m"] < m_end]
    w = detect[detect["m"] >= m0]
    if w.empty:
        steps.append(("window", False, f"chưa có nến {cfg.exec_tf} nào trong cửa sổ"))
        return mk("ARMED", **base)

    idx_all = list(detect.index)
    seen_touch = False
    for t, bar in w.iterrows():
        o, h, l, c = (float(bar["open"]), float(bar["high"]),
                      float(bar["low"]), float(bar["close"]))
        up_touch, dn_touch = h > hi, l < lo
        if not (up_touch or dn_touch):
            continue
        seen_touch = True
        sw = 1 if (up_touch and (not dn_touch or (h - hi) >= (lo - l))) else -1
        depth = (h - hi) if sw > 0 else (lo - l)
        depth_pips = depth / pip
        body = abs(c - o)
        wb = depth / body if body > 0 else float("inf")
        cpos = (c - l) / max(h - l, 1e-12)
        info = dict(base, sweep_side=sw, depth_pips=depth_pips, wick_body=wb,
                    close_pos=cpos, sweep_time=str(t),
                    liq_confluence=lq.confluent(sw), asia_took_htf=lq.took_htf)

        # ── setup xấu #2
        if not (cfg.depth_min_pips <= depth_pips <= cfg.depth_max_pips):
            steps.append(("depth", False,
                          f"xuyên {depth_pips:.1f} pip ngoài [{cfg.depth_min_pips:.1f}"
                          f"; {cfg.depth_max_pips:.1f}] — setup xấu #2"))
            continue
        # ── setup xấu #3 — đây là breakout THẬT, không phải cú quét
        if (sw > 0 and c >= hi) or (sw < 0 and c <= lo):
            steps.append(("reclaim", False,
                          f"nến quét ĐÓNG ngoài biên ({c:.5f}) — breakout, "
                          f"setup xấu #3"))
            continue
        if wb < cfg.wick_body_min:
            steps.append(("wick_body", False,
                          f"râu/thân {wb:.2f} < {cfg.wick_body_min:.2f}"))
            continue
        if cfg.wick_body_min > 0 and (
                (sw > 0 and cpos >= 0.5) or (sw < 0 and cpos <= 0.5)):
            steps.append(("close_half", False,
                          f"đóng ở nửa cùng phía cú quét ({cpos:.2f}) — "
                          f"Wyckoff tr. 209"))
            continue

        steps.append(("depth", True, f"xuyên {depth_pips:.1f} pip"))
        steps.append(("reclaim", True, f"ĐÓNG lại trong biên tại {c:.5f}"))

        side = -sw
        i_sweep = idx_all.index(t)
        # Nến CUỐI CÙNG đã đóng lúc ra quyết định. Nếu MSS xác nhận ở nến `j` thì đó
        # là `j`; không có MSS thì chính nến quét. Lệnh khớp ở giá MỞ nến KẾ TIẾP nến
        # này — xem cảnh báo nhìn trước ở docstring `_mss_confirm`.
        j_mss = _mss_confirm(detect, i_sweep, sw, cfg)
        has_mss = j_mss >= 0
        i_decide = j_mss if has_mss else i_sweep
        has_fvg, fvg_mid = _fvg(detect, i_sweep, sw, cfg, i_decide)
        info.update(has_mss=has_mss, has_fvg=has_fvg, fvg_mid=fvg_mid)
        steps.append(("reversal", True,
                      f"MSS {int(has_mss)}"
                      + (f" xác nhận ở nến {idx_all[i_decide]}" if has_mss else "")
                      + f" · FVG {int(has_fvg)} (cửa sổ {cfg.mss_max_bars} nến)"))

        aligned = (not cfg.use_bias) or (side == b)
        if cfg.use_bias and not aligned:
            steps.append(("bias_match", False,
                          f"lệnh {'MUA' if side > 0 else 'BÁN'} ngược thiên hướng H1"))
            return mk("BIAS_MISMATCH", side=side, **info)
        if cfg.require_mss and not has_mss:
            steps.append(("mss", False, "đòi MSS mà không có — setup xấu #4"))
            return mk("GRADE_TOO_LOW", side=side, setup_grade="B", **info)
        if cfg.require_fvg and not has_fvg:
            steps.append(("fvg", False, "đòi FVG mà không có"))
            return mk("GRADE_TOO_LOW", side=side, setup_grade="B", **info)

        grade = _grade(aligned=aligned, has_mss=has_mss, has_fvg=has_fvg,
                       confluent=lq.confluent(sw), took_htf=lq.took_htf)
        if GRADES[grade] < cfg.min_grade_rank:
            steps.append(("grade", False,
                          f"hạng {grade} dưới ngưỡng {cfg.min_grade}"))
            return mk("GRADE_TOO_LOW", side=side, setup_grade=grade, **info)
        steps.append(("grade", True, f"hạng {grade} >= {cfg.min_grade}"))

        m_decide = int(detect["m"].iloc[i_decide])
        nxt = sess_bars[sess_bars["m"] > m_decide]
        if nxt.empty:
            steps.append(("entry", False,
                          f"chưa có nến {cfg.exec_tf} kế tiếp nến xác nhận để khớp"))
            return mk("RECLAIMED", side=side, setup_grade=grade, **info)
        entry_bar = nxt.iloc[0]
        e = float(entry_bar["open"])
        t_entry_bar = nxt.index[0]
        buf = cfg.sl_buffer_pips * pip
        stop = (h + buf) if side < 0 else (l - buf)
        risk = abs(e - stop)
        if risk <= 0:
            steps.append(("entry", False,
                          "giá mở nến kế tiếp đã vượt dừng lỗ — bỏ"))
            return mk("RECLAIMED", side=side, setup_grade=grade, **info)

        tp = e + side * cfg.tp_r_multiple * risk
        px = dict(entry_px=e, stop_px=stop, tp_px=tp, sl_pips=risk / pip,
                  rr=cfg.tp_r_multiple)

        # ── setup xấu #8: giá vào đã đi hết biên Á sang phía đối diện.
        # `room` = chỗ còn lại tới biên đối diện, tính bằng R. Âm nghĩa là giá đã
        # xuyên qua nó rồi — vào lệnh lúc đó là bán ở đáy biên, đúng chiều mà sai chỗ.
        room = ((e - lo) if side < 0 else (hi - e)) / risk
        if room <= cfg.min_room_r:
            steps.append(("room", False,
                          f"chỉ còn {room:.2f}R tới biên Á đối diện "
                          f"(<= {cfg.min_room_r:.2f}) — setup xấu #8"))
            return mk("NO_ROOM", side=side, setup_grade=grade, **px, **info)
        steps.append(("room", True, f"còn {room:.2f}R tới biên Á đối diện"))
        steps.append(("target", True,
                      f"TP cố định {cfg.tp_r_multiple:.1f}R tại {tp:.5f} · "
                      f"breakeven khi đạt {cfg.be_trigger_r:.1f}R"))

        # ── setup xấu #7: ĐÚNG PHÚT công bố tin, không phải cả ngày.
        #
        # Đo được: ngày có NFP/CPI/FOMC cho kỳ vọng +0,1985 R, tức HƠN HAI LẦN trung
        # bình — ngày tin KHÔNG phải ngày xấu. Chỉ cửa sổ hẹp quanh mốc công bố mới
        # xấu, và rủi ro ở đó không phải "giá đi sai hướng" mà là DỪNG LỖ BỊ NHẢY QUA,
        # tức một tổn thất lớn hơn mức đã dự kiến. Xem bảng đo ở `ai/news_guard.py`.
        if _in_news_window(p.news_times, t_entry_bar, cfg.news_window_min):
            steps.append(("news", False,
                          f"trong ±{cfg.news_window_min:.0f} phút quanh tin tác động "
                          f"mạnh — setup xấu #7"))
            return mk("NEWS_WINDOW", side=side, setup_grade=grade,
                      entry_time=str(t_entry_bar), **px, **info)
        steps.append(("news", True,
                      f"ngoài ±{cfg.news_window_min:.0f} phút quanh tin lớn"))
        steps.append(("entry", True, f"khớp giá mở {t_entry_bar}"))
        return mk("ENTRY", side=side, setup_grade=grade,
                  entry_time=str(t_entry_bar), **px, **info)

    if not seen_touch:
        steps.append(("sweep", False,
                      "giá không ra khỏi biên Á trong cửa sổ — setup xấu #5"))
        return mk("WINDOW_CLOSED", **base)
    steps.append(("sweep", False, "có ra khỏi biên nhưng không cú nào đủ chữ ký"))
    return mk("SWEPT_NO_RECLAIM", **base)


# ═══════════════════════════════════════════════════════════════════ mô phỏng
@dataclass
class TradeResult:
    session: pd.Timestamp
    t_entry: pd.Timestamp
    t_exit: pd.Timestamp
    instrument: str
    side: int
    setup_grade: str
    entry_px: float
    stop_px: float
    tp_px: float
    sl_pips: float
    rr: float
    asia_range_pips: float
    depth_pips: float
    h1_bias: int
    has_mss: bool
    has_fvg: bool
    liq_confluence: bool
    outcome: str            # SL | BE | TP | TIME
    r_gross: float
    cost_r: float
    r_net: float
    minutes: float


def simulate_path(p: Prepared, d: SweepDecision, session: pd.Timestamp,
                  cfg: SweepConfig) -> Optional[TradeResult]:
    """Chạy vị thế trên nến M1 tới khi đóng. Trả kết quả theo đơn vị R.

    THỨ TỰ TRONG MỘT PHÚT: nếu một nến M1 chạm CẢ dừng lỗ và mục tiêu thì tính DỪNG
    LỖ TRƯỚC. Giả định BẢO THỦ có chủ ý — dữ liệu M1 không nói thứ tự trong phút, và
    giả định ngược lại là cách backtest tự tặng cho mình những lệnh không có thật.

    VÒNG ĐỜI
    ========
        1. mở với dừng lỗ tại `stop_px` và chốt lời tại `tp_px` (= 3R nếu
           `tp_r_multiple = 3`)
        2. khi giá đi được `be_trigger_r` lần R theo chiều mình -> dời dừng lỗ về
           **giá vào cộng đúng phí khứ hồi**. Chạm mức đó là HOÀ THẬT: cộng phí vào
           mức breakeven là điểm khác biệt giữa "hoà" và "hoà gộp rồi âm sau phí".
        3. nếu `trail_r > 0` thì sau bước 2 dừng lỗ đi theo giá tốt nhất, giữ khoảng
           cách `trail_r` lần R, và CHỈ đi theo chiều có lợi
        4. còn sống tới `flat_utc` thì đóng ở giá đóng nến đó

    Mức breakeven được tính TỪ PHÍ THẬT của chính lệnh đó (spread lúc khớp +
    commission), không phải một hằng số pip. Spread lúc khớp của GBPUSD gấp đôi
    EURUSD, nên một hằng số dùng chung sẽ hoặc thiếu ở cặp này hoặc thừa ở cặp kia.

    ⚠️ KẾ TOÁN THOÁT LỆNH — MỘT LỖI ĐÃ XẢY RA Ở ĐÂY
    ==============================================
    Một bản trước của hàm này có thêm nhánh chốt-một-phần, và nhánh đó ghi **0 R cho
    một lệnh thật ra mất 1 R**: lệnh chạm mức chốt-một-phần rồi bị dừng lỗ GỐC quét
    thoát qua nhánh `TP1_BE`, nhánh này cộng biến tích luỹ (đang bằng 0) rồi break,
    không trừ 1 R. 22 trong 453 lệnh, và nó thổi kỳ vọng từ +0,0417 lên +0,0903 R —
    gấp hơn hai lần.

    Lớp lỗi này KHÔNG có triệu chứng nào khác: số lệnh đúng, winrate đúng, đường
    equity trông hợp lý. Đó là lý do bốn bất biến kế toán dưới đây được ghim bằng
    test, và tại sao vòng lặp này chỉ có BỐN đường ra:

        SL    r_gross = -1,0 CHÍNH XÁC          `test_stopped_out_trade_loses_exactly_one_r`
        BE    r_net   =  0,0 CHÍNH XÁC          `test_breakeven_exit_nets_exactly_zero`
        TP    r_gross = `tp_r_multiple` CHÍNH XÁC  `test_target_exit_pays_exactly_the_declared_rr`
        TIME  tính từ giá đóng nến cuối         `test_every_outcome_is_one_of_the_four_declared`

    Thêm một nhánh thoát thứ năm thì phải thêm một bất biến kế toán cho nó TRƯỚC.
    """
    if not d.enter:
        return None
    seg = p.m1[p.m1["session"] == session]
    # `entry_time` là NHÃN của nến khớp lệnh, do `detect_setup` xác định. Mô phỏng bắt
    # đầu từ đúng phút đó. KHÔNG suy lại bằng `sweep_time + exec_minutes`: khi có xác
    # nhận MSS thì nến vào lệnh cách nến quét tới 4 nến, và phép cộng đó sẽ mở vị thế
    # SỚM tới 3 giờ — đúng họ lỗi nhìn trước mà `_mss_confirm` sinh ra để chặn.
    if not d.entry_time:
        raise ValueError(
            f"{cfg.instrument} {d.asof}: quyết định ENTRY thiếu `entry_time`. Không "
            f"được suy thời điểm khớp từ `sweep_time` — xem ghi chú ở đây.")
    t_entry = pd.Timestamp(d.entry_time)
    mflat = minute_of_session(cfg.flat_utc)
    fwd = seg[(seg.index >= t_entry) & (seg["m"] <= mflat)]
    if fwd.empty:
        return None

    side, e = d.side, d.entry_px
    stop, tp = d.stop_px, d.tp_px
    risk = abs(e - stop)

    # PHÍ THẬT của chính lệnh này — dùng cho CẢ hai việc: trừ khỏi kết quả, và đặt
    # mức breakeven. Hai chỗ phải cùng một con số, nếu không thì "hoà" ở một chỗ là
    # "âm" ở chỗ kia.
    sp = float(fwd.iloc[0].get("spread_usd", 0.0) or 0.0)
    prof = AP.get(cfg.instrument)
    cost_price = sp + prof.commission_price_units(e)
    cost_r = cost_price / risk

    be_level = e + side * (cost_price + cfg.be_extra_pips * cfg.pip)
    be_armed = False
    best = e                                          # giá tốt nhất đã đạt
    outcome = "TIME"
    r_out = 0.0
    k_exit = len(fwd) - 1
    hi = fwd["high"].to_numpy()
    lo = fwd["low"].to_numpy()

    for k in range(len(fwd)):
        if side < 0:
            hit_stop, hit_tp = hi[k] >= stop, lo[k] <= tp
            reach = lo[k]
        else:
            hit_stop, hit_tp = lo[k] <= stop, hi[k] >= tp
            reach = hi[k]

        if hit_stop:                                  # bảo thủ: dừng lỗ TRƯỚC
            r_out = (side * (stop - e) / risk) if be_armed else -1.0
            outcome = "BE" if be_armed else "SL"
            k_exit = k
            break
        if hit_tp:
            r_out, outcome, k_exit = d.rr, "TP", k
            break

        # ── cập nhật giá tốt nhất rồi mới xét dời dừng lỗ. Thứ tự này quan trọng:
        # dời trước khi cập nhật là dùng giá của phút TRƯỚC để đặt stop cho phút NÀY.
        if (reach - best) * side > 0:
            best = reach
        r_now = side * (best - e) / risk
        if cfg.be_trigger_r > 0 and not be_armed and r_now >= cfg.be_trigger_r:
            be_armed = True
            stop = be_level
        if be_armed and cfg.trail_r > 0:
            trail = best - side * cfg.trail_r * risk
            if (trail - stop) * side > 0:             # CHỈ đi theo chiều có lợi
                stop = trail

    if outcome == "TIME":
        r_out = side * (float(fwd.iloc[k_exit]["close"]) - e) / risk

    r_locked = r_out

    return TradeResult(
        session=session, t_entry=fwd.index[0], t_exit=fwd.index[k_exit],
        instrument=cfg.instrument, side=side, setup_grade=d.setup_grade,
        entry_px=e, stop_px=d.stop_px, tp_px=tp, sl_pips=d.sl_pips,
        rr=d.rr, asia_range_pips=d.asia_range_pips,
        depth_pips=d.depth_pips, h1_bias=d.h1_bias, has_mss=d.has_mss,
        has_fvg=d.has_fvg, liq_confluence=d.liq_confluence,
        outcome=outcome, r_gross=r_locked, cost_r=cost_r, r_net=r_locked - cost_r,
        minutes=float((fwd.index[k_exit] - fwd.index[0]).total_seconds() / 60))


# ═══════════════════════════════════════════════════════════════════ backtest
@dataclass
class BacktestResult:
    trades: pd.DataFrame
    decisions: pd.DataFrame
    config: SweepConfig

    @property
    def r_net(self) -> pd.Series:
        return self.trades["r_net"] if len(self.trades) else pd.Series(dtype=float)


def run(m1: pd.DataFrame, cfg: SweepConfig) -> BacktestResult:
    """Backtest đầy đủ, trên cùng đường code với live."""
    p = prepare(m1, cfg)
    trades: List[TradeResult] = []
    decs: List[Dict[str, object]] = []
    for s in p.sessions:
        d = detect_setup(p, s, cfg)
        decs.append({"session": s, "state": d.state, "grade": d.setup_grade,
                     "side": d.side, "asia_range_pips": d.asia_range_pips,
                     "depth_pips": d.depth_pips, "rr": d.rr,
                     "has_mss": d.has_mss, "has_fvg": d.has_fvg})
        tr = simulate_path(p, d, s, cfg)
        if tr is not None:
            trades.append(tr)
    T = pd.DataFrame([t.__dict__ for t in trades])
    return BacktestResult(trades=T, decisions=pd.DataFrame(decs), config=cfg)


def live_decision(m1: pd.DataFrame, cfg: SweepConfig) -> SweepDecision:
    """Quyết định cho phiên GẦN NHẤT, dùng thông tin tới nến khớp lệnh đã đóng cuối."""
    p = prepare(m1, cfg)
    if not p.sessions:
        return SweepDecision(instrument=cfg.instrument, asof="", state="NO_DATA",
                             steps=(("data", False, "không dựng được biên Á nào"),))
    s = p.sessions[-1]
    last = p.exec_bars[p.exec_bars["session"] == s]
    upto = int(last["m"].max()) + 1 if len(last) else None
    return detect_setup(p, s, cfg, upto_minute=upto)


# ═══════════════════════════════════════════════════════════════════ thống kê
def stats(res: BacktestResult) -> Dict[str, object]:
    T = res.trades
    if T.empty:
        return {"instrument": res.config.instrument, "n": 0}
    r = T["r_net"]
    years = max((T["session"].max() - T["session"].min()).days / 365.25, 1e-9)
    return {
        "instrument": res.config.instrument,
        "n": int(len(T)),
        "lệnh/tuần": round(len(T) / (years * 52.0), 2),
        "thắng%": round(100.0 * float((r > 0).mean()), 2),
        "R:R": round(float(T["rr"].median()), 2),
        "SL pip TV": round(float(T["sl_pips"].median()), 1),
        "phí R TV": round(float(T["cost_r"].median()), 3),
        "R gộp/lệnh": round(float(T["r_gross"].mean()), 4),
        "R ròng/lệnh": round(float(r.mean()), 4),
        "t ròng": (round(float(r.mean() / r.std(ddof=1) * np.sqrt(len(r))), 2)
                   if len(r) > 2 and r.std(ddof=1) > 0 else float("nan")),
        "R ròng tổng": round(float(r.sum()), 1),
        "giữ (phút) TV": round(float(T["minutes"].median()), 0),
        "hạng": T["setup_grade"].value_counts().to_dict(),
        "kết cục": T["outcome"].value_counts().to_dict(),
        "phiên bị loại": res.decisions["state"].value_counts().to_dict(),
    }


def stats_by_grade(res: BacktestResult) -> pd.DataFrame:
    """Kỳ vọng theo HẠNG setup — bảng trả lời "yếu tố nào tạo ra lợi nhuận".

    Bản đặc tả nghiệp vụ yêu cầu đúng bảng này: đo TỪNG setup độc lập thay vì trộn
    một đống khái niệm rồi không biết cái nào work.
    """
    T = res.trades
    if T.empty:
        return pd.DataFrame()
    g = T.groupby("setup_grade")
    return pd.DataFrame({
        "n": g.size(),
        "thắng%": g["r_net"].apply(lambda s: 100.0 * (s > 0).mean()).round(2),
        "R gộp": g["r_gross"].mean().round(4),
        "R ròng": g["r_net"].mean().round(4),
        "t": g["r_net"].apply(
            lambda s: (s.mean() / s.std(ddof=1) * np.sqrt(len(s))
                       if len(s) > 2 and s.std(ddof=1) > 0 else np.nan)).round(2),
    }).sort_index()


# ═══════════════════════════════════════════════════════════════════ thẻ luật
def rulebook(cfg: SweepConfig, *, expectancy: str, frequency: str,
             source: str) -> RuleBook:
    """Thẻ luật bảy mục. Mọi điều kiện vào lệnh PHẢI có ngưỡng số —
    `tests/test_rulebook.py` cưỡng chế điều đó."""
    return RuleBook(
        name=cfg.name,
        signal_tf=cfg.signal_tf,
        execution_tf=cfg.exec_tf,
        direction="BOTH",
        universe=(cfg.instrument,),
        traded=(cfg.instrument,),
        max_positions=1,
        family="Asia Range Sweep (quét thanh khoản biên phiên Á, vào NGƯỢC cú quét)",
        source=source,
        hours_utc=(f"biên Á {cfg.asia_start_utc:02.0f}:00-{cfg.asia_end_utc:02.0f}:00 "
                   f"(không vào lệnh) · khớp {cfg.exec_start_utc:02.0f}:00-"
                   f"{cfg.exec_end_utc:02.0f}:00 · đóng hết {cfg.flat_utc:02.0f}:00"),
        forbidden_hours_utc=tuple(
            h for h in range(24)
            if not (cfg.exec_start_utc <= h < cfg.exec_end_utc)),
        indicators=(
            f"L2 biên Á = high/low của M1 trong {cfg.asia_start_utc:02.0f}:00-"
            f"{cfg.asia_end_utc:02.0f}:00 UTC",
            f"L3 bản đồ thanh khoản = PDH/PDL + cực trị {cfg.liq_lookback_days} phiên "
            f"đã đóng, dung sai trùng mức {cfg.equal_tol_pips:.1f} pip",
            f"L5 MSS = close nến {cfg.exec_tf} vượt cực trị vi mô 2 nến, trong "
            f"{cfg.mss_max_bars} nến",
            f"L5 FVG = mô thức 3 nến, khoảng hở >= {cfg.fvg_min_pips:.1f} pip",
            f"TP = giá vào + {cfg.tp_r_multiple:.1f} x khoảng cách dừng lỗ",
            f"breakeven = giá vào + phí khứ hồi THẬT, kích hoạt ở "
            f"+{cfg.be_trigger_r:.1f}R",
            f"L6 thiên hướng H1 = close vs EMA{cfg.bias_ema_h1} tại nến H1 đóng lúc "
            f"{cfg.asia_end_utc:02.0f}:00 UTC",
        ),
        entry_logic="ALL",
        entry_rules=(
            Rule("a", f"biên Á trong [{cfg.range_min_pips:.0f}; "
                      f"{cfg.range_max_pips:.0f}] pip",
                 "setup xấu #1 — biên quá hẹp thì mục tiêu không bù phí; quá rộng thì "
                 "thị trường đã phân phối, không còn là vùng tích luỹ"),
            Rule("b", f"nến {cfg.exec_tf} xuyên biên {cfg.depth_min_pips:.1f}-"
                      f"{cfg.depth_max_pips:.1f} pip",
                 "setup xấu #2 — Osler sr150: 62% giá trị lệnh stop >= $50M nằm trong "
                 "đuôi [90,100]/[01,09] quanh mốc tròn, tức túi stop trong ~10 pip"),
            Rule("c", "nến quét ĐÓNG trở lại TRONG biên Á (điều kiện quyết định, "
                      "1 nến)",
                 "setup xấu #3 — phân biệt cú quét THẤT BẠI với breakout thật. "
                 "Grimes 2012 tr. 183: fade theo việc giá xuyên LẠI mức là 'a futile "
                 "plan'; phải fade theo THẤT BẠI của nhịp đầu tiên"),
            Rule("d", (f"râu ngoài biên / thân nến >= {cfg.wick_body_min:.2f}"
                       if cfg.wick_body_min > 0 else
                       "lọc râu/thân TẮT (wick_body_min = 0,00)"),
                 "nến quét phải là nến từ chối, không phải nến thân đặc"),
            Rule("e", "nến quét đóng ở NỬA đối diện chiều quét (close_pos < 0,50 khi "
                      "quét biên trên)",
                 "Villahermosa 2019 tr. 209 — ngưỡng đo được duy nhất mà Wyckoff cho "
                 "cho nến significant"),
            Rule("f", ("chiều lệnh KHỚP thiên hướng H1 (+1 mua / -1 bán)"
                       if cfg.use_bias else
                       "thiên hướng H1 chỉ dùng để PHÂN HẠNG, không chặn "
                       "(use_bias = 0)"),
                 "đo được: thuận H1 TỆ HƠN ngược ở cả 3 cặp — xem "
                 "00_KET_QUA_DO_LUONG §3. Giữ tham số kèm bảng đo, cùng cách xử lý "
                 "`exit_at_mean` của họ Z-Band cũ"),
            Rule("g", f"hạng setup >= {cfg.min_grade} (thứ hạng "
                      f"{cfg.min_grade_rank}/{max(GRADES.values())}) — A+ đòi MSS + "
                      f"FVG + trùng mức thanh khoản HTF + phiên Á CHƯA ăn PDH/PDL",
                 "setup xấu #4 và #6 — Lớp 7 phân hạng để đo TỪNG setup độc lập"),
            Rule("h", f"còn > {cfg.min_room_r:.2f}R tới biên Á đối diện tại điểm vào",
                 "setup xấu #8 — MSS xác nhận muộn tới 3 nến, và trong khoảng đó giá "
                 "có thể đã chạy xuyên cả biên. Bỏ điều kiện này thêm 600 lệnh và kéo "
                 "kỳ vọng từ +0,0147 xuống -0,0177 R/lệnh"),
        ),
        entry_price=(f"khớp tại giá MỞ nến {cfg.exec_tf} kế tiếp sau nến quét — nến "
                     f"tín hiệu đã ĐÓNG, không nhìn trước"),
        exit_rules=(
            Rule("x1", f"TP = giá vào + {cfg.tp_r_multiple:.1f}R, chốt TOÀN BỘ vị thế",
                 "R:R là HẰNG SỐ nên mọi lệnh so được với nhau, và kỳ vọng chỉ còn "
                 "phụ thuộc tỷ lệ thắng"),
            Rule("x2", f"khi đạt +{cfg.be_trigger_r:.1f}R -> dời dừng lỗ về giá vào "
                       f"CỘNG đúng phí khứ hồi",
                 "chạm mức đó là HOÀ THẬT sau phí, không phải hoà gộp rồi âm. Mức "
                 "tính từ phí THẬT của chính lệnh đó, không phải một hằng số pip"),
            Rule("x3", (f"trailing giữ dừng lỗ cách giá tốt nhất "
                        f"{cfg.trail_r:.1f}R" if cfg.trail_r > 0
                        else "KHÔNG trailing — dừng lỗ nằm im ở mức breakeven"),
                 "mỗi nhánh quản lý lệnh thêm vào là một chỗ live có thể lệch khỏi "
                 "backtest"),
            Rule("x4", f"đóng hết lúc {cfg.flat_utc:02.0f}:00 UTC",
                 "chiến lược TRONG phiên; giữ qua đêm là trả swap cho một cú quét đã "
                 "hết hiệu lực. Osler: cửa sổ đảo chiều còn ý nghĩa DƯỚI 30 phút"),
        ),
        stop_loss=(f"cực trị nến quét +/- {cfg.sl_buffer_pips:.1f} pip. SL CỨNG, đặt "
                   f"trên server broker CÙNG lệnh mở. Cầu chì `disaster_stop` "
                   f">= 8xATR là lớp DỰ PHÒNG, không phải dừng lỗ giao dịch"),
        take_profit=(f"giá vào + {cfg.tp_r_multiple:.1f}R, chốt toàn bộ. Breakeven ở "
                     f"+{cfg.be_trigger_r:.1f}R"),
        blocks=(
            "tối đa 1 vị thế / công cụ · tối đa 1 lần vào lệnh / công cụ / phiên",
            f"setup xấu #5 — tín hiệu ngoài {cfg.exec_start_utc:02.0f}:00-"
            f"{cfg.exec_end_utc:02.0f}:00 UTC bị BỎ",
            f"setup xấu #7 — KHÔNG vào lệnh trong ±{cfg.news_window_min:.0f} phút "
            f"quanh NFP · CPI · FOMC · ECB · BOE (`ai/news_guard.py`). Chặn cả NGÀY "
            f"thì sai hướng: ngày có tin cho kỳ vọng HƠN HAI LẦN trung bình, chỉ đúng "
            f"phút công bố mới xấu",
            "phiên thiếu > 30% nến phiên Á bị bỏ hẳn (lễ, nửa phiên)",
            "rủi ro MỞ đồng thời <= 4,00% equity theo NGÀY "
            "(`order_plan._DAILY_RISK_CAP_PCT`) và <= 1,50% theo ĐỒNG TIỀN "
            "(`_CURRENCY_RISK_CAP_PCT`) — cả hai dưới mốc ngày FTMO 5,00%",
            "mọi cổng của `execution/entry_gate.py` (fail-closed)",
        ),
        frequency=frequency,
        avg_holding=f"trong phiên, đóng chậm nhất {cfg.flat_utc:02.0f}:00 UTC",
        expectancy=expectancy,
        trace_signal_name=cfg.family,
    )
