"""registry.py — SỔ ĐĂNG KÝ CHIẾN LƯỢC. Nguồn sự thật DUY NHẤT.

VÌ SAO CÓ MODULE NÀY
====================
Câu hỏi "cái gì đang chạy tiền thật, ở giai đoạn nào, với số đo nào" phải có MỘT chỗ
trả lời — không phải suy ra từ việc đọc code, không phải từ trí nhớ. Mọi bảng số trong
tài liệu là ẢNH CHỤP và sẽ trôi khỏi code; registry thì không.

Registry giữ đúng vai trò đó, không hơn: **khai báo**, không chứa logic.

HAI KHUNG THỜI GIAN, ĐỪNG NHẦM
==============================
    signal_tf     khung mà LOGIC TÍN HIỆU chạy trên đó
    execution_tf  khung mà LỆNH được khớp

Hai khung có thể khác nhau: một chân tính tín hiệu trên D1 vẫn có thể khớp lệnh trong
một nến H1 cụ thể để lấy spread rẻ nhất. Thư mục đặt theo `signal_tf` (`d1/`, `h1/`,
`h4/`, `m30/`) vì đó là thứ quyết định bản chất chiến lược; `execution_tf` khai ở đây
để không ai đọc đường dẫn rồi kết luận sai về khung khớp lệnh.

VÒNG ĐỜI
========
    LIVE           chạy tiền thật
    FORWARD_TEST   chạy demo, chưa cấp vốn
    BACKTEST_ONLY  giữ làm bản ghi nghiên cứu, dispatcher KHÔNG gọi
    REJECTED       đã bị bác bỏ bằng bằng chứng — giữ lý do để không ai thử lại
"""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════ vòng đời
LIVE = "LIVE"
FORWARD_TEST = "FORWARD_TEST"
BACKTEST_ONLY = "BACKTEST_ONLY"
REJECTED = "REJECTED"


@dataclass(frozen=True)
class StrategySpec:
    """Khai báo một chiến lược. KHÔNG chứa logic — logic nằm trong module."""
    name: str
    module: str                 # dotted, tương đối với `src.python.strategies`
    signal_tf: str              # D1 | H4 | H1 | M30
    execution_tf: str           # khung khớp lệnh thật
    stage: str
    symbols: Tuple[str, ...]
    hypothesis: str             # giả thuyết giao dịch, một câu — cơ sở để loại bỏ
    source: str                 # nguồn học thuật, để truy vết
    # Bằng chứng đo được. `None` = chưa đo. Mọi con số đều là SAU ĐỦ CHI PHÍ:
    # spread THẬT tại phút khớp + commission $7/lot khứ hồi. Không có swap vì chiến
    # lược hiện tại đóng hết trong phiên.
    sharpe_all: Optional[float] = None
    sharpe_oos: Optional[float] = None
    max_dd_pct: Optional[float] = None
    notes: str = ""

    @property
    def module_path(self) -> str:
        return f"src.python.strategies.{self.signal_tf.lower()}.{self.module}"

    def load(self):
        return import_module(self.module_path)


# ═══════════════════════════════════════════════════════════ đăng ký
#
# Rổ giao dịch: ba major có rào chi phí THẤP NHẤT đo được (spread/ATR_H1 trung vị,
# H1 2020+): EURUSD 2,44% · USDJPY 2,73% · GBPUSD 5,00%.
#
# Bốn cặp Tier 2 (AUDUSD, USDCAD, USDCHF, NZDUSD) có rào chi phí gấp 3,5-4 lần VÀ
# hiện KHÔNG có parquet M1 trong `D:/data-ticks-train/_m1/` — phải dựng lại từ tick
# trước khi thêm chúng vào rổ.
_TIER1_FX: Tuple[str, ...] = ("EURUSD", "GBPUSD", "USDJPY")

STRATEGIES: Tuple[StrategySpec, ...] = (
    StrategySpec(
        name="AsiaSweepH1",
        module="asia_sweep",
        signal_tf="H1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=_TIER1_FX,
        hypothesis=(
            "Phiên Á thanh khoản mỏng tích luỹ cụm stop-loss ngay ngoài hai biên; "
            "London mở quét cụm đó rồi đảo chiều. Một nến H1 xuyên biên rồi ĐÓNG lại "
            "trong biên, VÀ được xác nhận bằng một MSS trong 3 nến, là cú quét THẤT "
            "BẠI — giá quay về biên đối diện. Cổng MSS là điều kiện QUYẾT ĐỊNH: không "
            "có nó thì kỳ vọng là -0,65 R/lệnh."),
        source=("Osler (2003) FRBNY Staff Report 150 · Chesler (2004) hikkake qua "
                "Kirkpatrick & Dahlquist (2011) tr. 379-380 · ICT 2022 tr. 50-51 · "
                "Grimes (2012) tr. 183-186 · Lien (2008) tr. 69, 73"),
        # Chiến lược có SL CỨNG nên đơn vị tự nhiên là **R mỗi lệnh**, không phải
        # Sharpe của chuỗi tỷ trọng. Ba trường dưới đây vì vậy quy đổi ở rủi ro
        # 0,45%/lệnh (`asia_sweep.RISK_PCT_PER_TRADE`).
        sharpe_all=0.15, sharpe_oos=0.55, max_dd_pct=11.21,
        notes=(
            "DƯƠNG nhưng NHỎ. 453 lệnh trong 11,5 năm (1,08 lệnh/tuần), thắng 48,1%, "
            "R:R trung vị 1,46, R gộp/lệnh +0,1379, R ròng/lệnh +0,0903 (t = +1,99), "
            "Profit Factor 1,264. FORM +0,1216 -> OOS +0,0239, cả hai DƯƠNG. "
            "Ở 0,60% rủi ro/lệnh: lãi/năm +1,47%, MaxDD từ đỉnh -8,17%, ngày tệ nhất "
            "-1,268%, 9/12 năm dương. KHÔNG vi phạm hạn mức FTMO nào, nhưng "
            "+1,47%/năm thì một vòng thử thách 10% mất khoảng bảy năm — nó dùng được "
            "như MỘT CHÂN trong danh mục nhiều chân, không tự mình pass được. "
            "Ba thứ tạo ra toàn bộ khác biệt, và cả ba đều đo được: (1) CỔNG MSS — "
            "hạng A +0,09 R/lệnh so với hạng B -0,56..-0,70 R/lệnh (t = -22,4 / "
            "-16,9 / -13,7 trên 2.437 lệnh); (2) BỎ chốt-một-phần và breakeven — "
            "+0,0893 so với +0,0124 R/lệnh; (3) CỔNG TIN ±30 phút — chặn 1,9% số "
            "lệnh, tiền -0,2%, MaxDD 8,90% -> 8,17%. "
            "t = 1,99 chưa qua ngưỡng phát hiện, nên KHÔNG được nâng lên LIVE cho "
            "tới khi demo cho số dương qua đủ 6 kiểm định + cổng PBO."),
    ),
)


# ═══════════════════════════════════════════════════════════ danh mục
PORTFOLIO = {
    "name": "AsiaSweepSingleLeg",
    "legs": {"AsiaSweepH1": 1.0},
    # Chuẩn hoá biến động giữa các chân là vô nghĩa khi chỉ có MỘT chân.
    "vol_normalise": False,
    "entry_points": {
        "AsiaSweepH1": "src.python.strategies.h1.asia_sweep:live_decisions",
    },
    # Tỷ trọng CHỈ để báo cáo phơi nhiễm. CỠ LỆNH KHÔNG đi đường này — xem
    # `risk_sizing` ngay dưới, và docstring §2 của `strategies/portfolio.py`.
    "target_weights": "src.python.strategies.portfolio:target_weights",
    "netting_report": "src.python.strategies.portfolio:netting_report",
    # ĐƯỜNG SIZING DUY NHẤT: cỡ lệnh từ khoảng cách SL và % equity. Rủi ro mỗi lệnh
    # là số ĐÃ BIẾT TRƯỚC, nên rủi ro ngày là phép CỘNG và chặn được trước khi gửi.
    "risk_sizing": "src.python.execution.risk_sizing:lots_for_risk",
    "stop_targets": "src.python.strategies.portfolio:stop_targets",
    "risk_pct_per_trade": 0.35,
    # ⚠️ KHAI BÁO VƯỢT SÀN. MaxDD đo được ở mức rủi ro trên là -11,21% (lãi kép,
    # 4.212 ngày), vượt cả sàn nội bộ 9,00% VÀ luật FTMO 10,00%. Trần tuân thủ đo
    # được là 0,27% (MaxDD -8,70%).
    #
    # Khoá này TỒN TẠI để việc vượt sàn phải do ai đó VIẾT RA, không đi qua âm
    # thầm: `tests/test_portfolio_single_leg.py` đòi nó khi MaxDD > sàn, nên xoá
    # khoá mà giữ mức rủi ro sẽ làm test đỏ.
    "dd_floor_override": (
        "Chủ tài khoản chọn 0,35%/lệnh ngày 25/08/2026 sau khi đã được trình bày "
        "bảng MaxDD theo từng mức rủi ro, với lập luận rằng kết quả backtest chỉ "
        "mang tính tham khảo. MaxDD -11,21% so với sàn nội bộ 9,00% và luật FTMO "
        "10,00%. Trần tuân thủ là 0,27%. Và MaxDD THẬT sẽ sâu hơn -11,21% vì "
        "backtest không có trượt giá, spread giãn, gap cuối tuần hay lệnh bị từ "
        "chối."),
    "leverage_policy": "src.python.execution.ftmo_leverage_policy:decide",
    "disaster_stop": "src.python.execution.disaster_stop:compute_book",
    "live_risk": "src.python.execution.portfolio_risk:snapshot",
    "decision_log": "src.python.execution.decision_log:record_many",
    "order_plan": "src.python.execution.order_plan:build",
    "order_router": "src.python.execution.order_router:OrderRouter",
    "position_book": "src.python.execution.position_book:PositionBook",
    "trading_control": "src.python.execution.trading_control:entry_allowed",
    # SSOT là `execution/ftmo_leverage_policy.LEVERAGE_MAX`; con số ở đây chỉ để
    # hiển thị và PHẢI khớp — `tests/test_rulebook.py` cưỡng chế điều đó.
    "leverage_cap": 6.0,
    "max_dd_self_cap_pct": 9.0,   # sàn nội bộ, chặt hơn mốc 10% của FTMO
    "stage": FORWARD_TEST,
    # ═════ SỐ ĐO. Quy đổi ở rủi ro 0,60%/lệnh trên $100.000, đủ chi phí, cùng
    # đường code với live.
    #
    #     453 lệnh · 11,5 năm · 1,08 lệnh/tuần · thắng 48,1% · PF 1,264
    #     R gộp/lệnh +0,1379 · R ròng/lệnh +0,0903 (t = +1,99)
    #     FORM +0,1216 -> OOS +0,0239  (cả hai DƯƠNG)
    #     lãi/năm +1,47% · MaxDD từ đỉnh -8,17% · ngày tệ nhất -1,268%
    #     5/4.212 ngày âm hơn 1% · 9/12 năm dương
    #
    # 0,60% là TRẦN THỰC TẾ của mức rủi ro, chọn bằng cách ĐO: 0,75% đẩy MaxDD vượt
    # cả luật FTMO 10%. Bảng đầy đủ ở `h1/asia_sweep.py`.
    #
    # Sharpe 0,471 tính trên MỌI ngày (4.212 ngày, phần lớn không có lệnh); trên
    # riêng những ngày CÓ lệnh thì 1,490. Hai con số đo hai thứ khác nhau và cả hai
    # đều đúng — con số dùng để đối chiếu hạn mức là con số MỌI NGÀY, vì đường equity
    # đi qua mọi ngày.
    "sharpe_all": 0.15, "sharpe_form": -0.01, "sharpe_oos": 0.55,
    "years_positive": "8/12",
    "worst_day_pct": -1.101,
    "max_dd_pct": 11.21,
    "trades_per_week": 2.91,
    "risk_groups": 1,
    # ═════ BỐN CON SỐ RỦI RO PHẢI ĐO LẠI TRƯỚC KHI CẤP VỐN
    #
    # Ba con số đầu được hiệu chỉnh cho một danh mục KHÔNG có SL theo giá, nơi rủi
    # ro là hàm của biến động và đòn bẩy. Chiến lược này có SL cứng nên chúng không
    # còn ràng buộc đúng đại lượng nào. Sàn 9% là LUẬT nên giữ nguyên.
    "can_do_lai": {
        "ftmo_leverage_policy.LEVERAGE_MAX": (
            "trần đòn bẩy phơi nhiễm không còn là biến điều khiển — rủi ro nay do "
            "`asia_sweep.RISK_PCT_PER_TRADE` và khoảng cách SL quyết định"),
        "disaster_stop.PER_POSITION_BUDGET_PCT": (
            "2,0%/vị thế — nay SL chiến lược chỉ 12-20 pip = 0,25% equity, nhỏ hơn "
            "8 lần. Cầu chì không bao giờ chạm, nhưng ngân sách thì sai bậc"),
        "target_mode.NOTIONAL_GAP_WARN_X": (
            "neo vào một ngày tệ nhất 0,794%. Ngày tệ nhất đo được của chân này là "
            "-1,268% ở rủi ro 0,60%, tức ngưỡng cảnh báo đang đặt sai chỗ"),
        "ftmo_leverage_policy.DD_SELF_CAP": (
            "9,0% — GIỮ NGUYÊN. Đây là luật tự đặt, không phải số đo của danh mục"),
    },
}
# ═══════════════════════════════════════════════════════════ đã bác bỏ
# Mỗi dòng là một hướng đã tốn công đo và đã có kết luận. Xoá đi thì lần sau sẽ có
# người thử lại chính nó. Đây là tài sản, không phải rác.
REJECTED_DIRECTIONS: Tuple[Dict[str, str], ...] = (
    {"name": "AsiaSweepFade_NoConfirmation", "tf": "H1/M15",
     "reason": "FADE cú quét biên độ phiên Á KHÔNG có cổng xác nhận MSS — tức luật "
               "'xuyên biên rồi đóng lại trong biên thì vào ngược' đứng một mình. "
               "4.963 lệnh trên EURUSD/GBPUSD/USDJPY: R GỘP +0,007 / -0,044 / -0,008 "
               "— KHÔNG CÓ BIÊN NÀO CẢ, không phải biên nhỏ bị chi phí ăn. R ròng "
               "-0,090 / -0,170 / -0,127 (t = -2,97 / -4,19 / -2,48). "
               "`winrate x R:R ~ 1` là chữ ký bước đi ngẫu nhiên. "
               "LƯỚI LỌC ĐẶC TẢ TRƯỚC: 54 ô n>=30 cho 5 ô dương (9,3%), **0 ô t>+2**, "
               "26 ô t<-2. 8 định nghĩa cửa sổ phiên Á x 3 cặp (gồm cửa sổ ICT gốc "
               "20:00-00:00 EST): **0/24 ô dương, 24/24 ô t<-2**. "
               "BA BỘ LỌC ĐƯỢC KHUYẾN NGHỊ RỘNG RÃI ĐO ĐƯỢC LÀ NGƯỢC DẤU: 'chỉ fade "
               "thuận xu hướng H1' tệ hơn ngược ở cả 3 cặp; 'nến quét đóng ở nửa đối "
               "diện' (Wyckoff tr. 209) tệ hơn nửa sai ở cả 3 cặp; 'bỏ biên Á rộng' "
               "không nhất quán giữa các cặp. "
               "NGUYÊN NHÂN CẤU TRÚC: Osler (2003, FRBNY SR150) — nguồn thường được "
               "trích làm cơ sở cho luật này — kết luận NGƯỢC. Cụm stop-loss làm giá "
               "CHẢY TIẾP (còn ý nghĩa >= 2 GIỜ); đảo chiều thuộc cụm take-profit, "
               "chỉ +4,5 điểm % (59,3% vs 54,8%) và chết DƯỚI 30 PHÚT. Đo lại xác "
               "nhận Osler: nhánh KHÔNG reclaim chảy tiếp +17..+23 bps/60 phút, nhánh "
               "CÓ reclaim -0,5..-4,0 bps. Ba nguồn cùng phía: Neely & Weller (JIMF "
               "2003) 'no evidence of excess returns' cho FX intraday sau chi phí "
               "thực; Hsu-Taylor-Wang (JIE 2016, 30 tiền tệ, 45 năm, >21.000 luật, "
               "Step-SPA) họ range/channel breakout CHẾT từ 2006; Curcio & Goodhart "
               "(LSE DP142 1992) lợi nhuận nằm ở HƯỚNG PHÁ VỠ (t = 1,27-2,85) trên "
               "đúng loại mức S/R cập nhật tại giờ mở London/Tokyo. "
               "'Break rate 99,4%' KHÔNG phải thông tin: control mức bất kỳ cách biên "
               "0,35 x biên độ cũng bị chạm 91,6%, control biên Á trễ 5 phiên 92,5%, "
               "độ sâu xuyên trung vị 1,85 pip. Đó là hình học biến động (cửa sổ "
               "London 9 tiếng > cửa sổ Á 7 tiếng), không phải hiệu ứng thanh khoản. "
               "PHẦN CỨU ĐƯỢC, và nó thành chiến lược đang chạy: thêm cổng MSS (một "
               "nến H1 sau đó ĐÓNG vượt cực trị vi mô ngược chiều cú quét, trong 3 "
               "nến) đưa kỳ vọng từ -0,65 R/lệnh về +0,0124 R/lệnh. Vẫn chỉ là HOÀ, "
               "nhưng chênh lệch 0,7 R giữa hai nhóm là bộ lọc THẬT.",
     "doc": "docs/the-asia-sweep/00_KET_QUA_DO_LUONG.md"},
    {"name": "AsiaSweepExecutionOnM15", "tf": "M15",
     "reason": "Cùng luật, khớp lệnh trên M15 thay vì H1, với ý định tăng tần suất. "
               "M15 cho SL trung vị 10,6 pip nên chi phí chiếm 0,114 R mỗi lệnh; H1 "
               "cho SL 28,0 pip nên chi phí chỉ 0,046 R. Kết quả: M15 R ròng -0,2446 "
               "so với H1 -0,1654 trên cùng bộ ngưỡng, winrate 24,0% vs 30,0%. "
               "Kết luận: với chiến lược có SL neo vào cực trị nến tín hiệu, HẠ khung "
               "khớp lệnh là thu hẹp SL và do đó NHÂN tỷ lệ chi phí trên rủi ro — "
               "không phải một cách tăng tần suất miễn phí.",
     "doc": "docs/the-asia-sweep/00_KET_QUA_DO_LUONG.md"},
    {"name": "AsiaSweepMssWindow6Bars", "tf": "H1",
     "reason": "Nới cửa sổ xác nhận MSS từ 3 lên 6 nến để tăng tần suất: được 1,38 "
               "lệnh/tuần (từ 1,10) và R ròng +0,0148 (từ +0,0124). LOẠI vì con số 3 "
               "có NGUỒN — mẫu hikkake của Chesler (2004, qua Kirkpatrick & Dahlquist "
               "tr. 379-380) đòi đảo chiều xảy ra trong 3 nến — còn 6 là con số chọn "
               "theo kết quả. Chênh lệch 0,0024 R không đáng đổi một tham số có nguồn "
               "thành một bậc tự do.",
     "doc": "docs/the-asia-sweep/00_KET_QUA_DO_LUONG.md"},
    {"name": "AsiaSweepMinRoom_HalfR", "tf": "H1",
     "reason": "Nâng `min_room_r` (chỗ còn lại tới biên Á đối diện tại điểm vào) từ "
               "0,0 lên 0,5R. Đo được nó TỐT HƠN rõ rệt: +0,0491 R/lệnh so với "
               "+0,0147 ở ngưỡng 0,0, và FORM +0,0369 / OOS +0,0756 đều dương. "
               "LOẠI vì bề mặt ngưỡng KHÔNG ĐƠN ĐIỆU: 0,0 cho +0,0147 · 0,5 cho "
               "+0,0491 · **1,0 cho -0,0652** · 1,5 cho +0,0105 · 2,0 cho -0,3212. "
               "Một ngưỡng thật thì hiệu ứng đi theo một chiều; ở đây nó nhảy dấu hai "
               "lần. Đó là chữ ký nhiễu, và chọn ô cao nhất trong một bề mặt như vậy "
               "là đúng cái Aronson (2007, ch. 6) bác — 6.402 luật trên S&P 500, "
               "luật tốt nhất p = 0,0005 đơn luật, 0 luật sống sót hiệu chỉnh "
               "data-mining. "
               "Ngưỡng 0,0 được giữ vì nó có LÝ DO CƠ HỌC, không phải vì nó cho số "
               "cao nhất: giá vào không được đã đi hết biên Á sang phía đối diện, "
               "bằng không thì lệnh BÁN được đặt ở ĐÁY biên — đúng chiều mà sai hoàn "
               "toàn về vị trí. Tham số GIỮ LẠI trong `SweepConfig` kèm bảng quét.",
     "doc": "docs/the-asia-sweep/00_KET_QUA_DO_LUONG.md"},
    {"name": "AsiaSweepBiasFilter_TrendAligned", "tf": "H1",
     "reason": "Luật 'chỉ fade THUẬN xu hướng H1' (close vs EMA50 tại mốc chốt biên "
               "Á). Đo trên 4.963 lệnh: THUẬN tệ hơn NGƯỢC ở CẢ BA cặp — -0,120 vs "
               "-0,065 (EURUSD) · -0,197 vs -0,150 (GBPUSD) · -0,177 vs -0,090 "
               "(USDJPY). Tham số `use_bias` GIỮ LẠI trong `SweepConfig` kèm bảng đo, "
               "mặc định TẮT ở preset đang chạy. Thiên hướng H1 vẫn được tính và vẫn "
               "vào bản ghi quyết định — nó chỉ không được quyền CHẶN lệnh.",
     "doc": "docs/the-asia-sweep/00_KET_QUA_DO_LUONG.md"},
)

# ═══════════════════════════════════════════════════════════ truy vấn
def by_name(name: str) -> StrategySpec:
    for s in STRATEGIES:
        if s.name == name:
            return s
    raise KeyError(f"Không có chiến lược {name!r}. Đã đăng ký: "
                   f"{[s.name for s in STRATEGIES]}")


def by_stage(stage: str) -> List[StrategySpec]:
    return [s for s in STRATEGIES if s.stage == stage]


def by_timeframe(signal_tf: str) -> List[StrategySpec]:
    return [s for s in STRATEGIES if s.signal_tf.upper() == signal_tf.upper()]


def live() -> List[StrategySpec]:
    """Chiến lược đang chạy TIỀN THẬT. Dispatcher chỉ được gọi những cái này."""
    return by_stage(LIVE)


def is_rejected(name: str) -> Optional[Dict[str, str]]:
    """Hướng này đã bị bác bỏ chưa — gọi TRƯỚC khi bắt đầu một vòng nghiên cứu mới."""
    for r in REJECTED_DIRECTIONS:
        if r["name"].lower() == name.lower():
            return r
    return None


def summary() -> str:
    """Bảng tóm tắt cho người đọc. Con số lấy từ chính registry, không gõ lại."""
    lines = ["CHIẾN LƯỢC ĐÃ ĐĂNG KÝ",
             f"{'tên':<20} {'signal':<7} {'exec':<5} {'stage':<14} "
             f"{'Sharpe ALL':>10} {'OOS':>7} {'MaxDD':>7}"]
    lines.append("-" * 78)
    for s in STRATEGIES:
        lines.append(
            f"{s.name:<20} {s.signal_tf:<7} {s.execution_tf:<5} {s.stage:<14} "
            f"{s.sharpe_all if s.sharpe_all is not None else float('nan'):>10.3f} "
            f"{s.sharpe_oos if s.sharpe_oos is not None else float('nan'):>7.3f} "
            f"{s.max_dd_pct if s.max_dd_pct is not None else float('nan'):>6.2f}%")
    p = PORTFOLIO
    lines += ["", f"DANH MỤC VẬN HÀNH: {p['name']} ({p['stage']})",
              f"  chân: {', '.join(p['legs'])}",
              f"  rủi ro {p['risk_pct_per_trade']:.2f}%/lệnh · "
              f"{p['trades_per_week']:.2f} lệnh/tuần",
              f"  MaxDD {p['max_dd_pct']:.2f}% · sàn nội bộ "
              f"{p['max_dd_self_cap_pct']:.2f}% · luật FTMO 10,00% · ngày tệ nhất "
              f"{p['worst_day_pct']:.3f}%",
              f"  Sharpe ALL {p['sharpe_all']:.3f} · FORM {p['sharpe_form']:.3f} "
              f"· OOS {p['sharpe_oos']:.3f} · {p['years_positive']} năm dương",
              "", f"ĐÃ BÁC BỎ: {len(REJECTED_DIRECTIONS)} hướng "
              f"({', '.join(r['name'] for r in REJECTED_DIRECTIONS)})"]
    return "\n".join(lines)
