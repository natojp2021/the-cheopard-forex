"""registry.py — SỔ ĐĂNG KÝ CHIẾN LƯỢC. Nguồn sự thật DUY NHẤT.

VÌ SAO CÓ MODULE NÀY
====================
Kế thừa đúng một bài học tốt của The Cheopard: khi danh mục có nhiều hơn một chiến
lược, câu hỏi "cái nào đang chạy tiền thật" phải có MỘT chỗ trả lời, không phải suy
ra từ việc đọc code hay từ trí nhớ. Hệ XAUUSD cũ có `core/strategy_registry.py` làm
việc đó, và tài liệu của nó nhiều lần phải ghi "nguồn chân lý duy nhất là registry;
bảng dưới đây là ảnh chụp" — vì bảng trong tài liệu đã trôi khỏi code.

Ở đây registry giữ đúng vai trò đó, không hơn: **khai báo**, không chứa logic.

HAI KHUNG THỜI GIAN, ĐỪNG NHẦM
==============================
Mỗi chiến lược có HAI khung và chúng khác nhau:

    signal_tf     khung mà LOGIC TÍN HIỆU chạy trên đó
    execution_tf  khung mà LỆNH được khớp

`currency_reversal` và `currency_carry` tính tín hiệu từ nến **D1** (lookback 21
nến ngày, tái cân bằng mỗi 21 ngày) nhưng khớp lệnh trong nến **H1** lúc 15:00 UTC
— giờ có spread rẻ nhất, đo được 1,6567 bps/khứ hồi so với 2,3043 lúc 22:00.

Thư mục đặt theo `signal_tf` (quy ước The Cheopard: `d1/`, `h1/`, `h4/`, `m30/`),
vì đó là thứ quyết định bản chất chiến lược. `execution_tf` khai trong registry để
không ai đọc đường dẫn rồi kết luận sai rằng hệ này không dùng H1.

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
    # Bằng chứng đo được. `None` = chưa đo. Mọi con số đều là SAU ĐỦ CHI PHÍ
    # (spread + commission + swap + biên broker 1,0%/năm) ở đòn bẩy 1,0.
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
_TIER1_FX: Tuple[str, ...] = (
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
)

# 20 cross tổng hợp — dựng từ 7 cặp vs USD, thành phần USD triệt tiêu.
# Xem `research/fx_cross_pairs.CROSS_DEFS` cho định nghĩa và spread ước lượng.
_CROSS_20: Tuple[str, ...] = (
    "EURGBP", "EURJPY", "GBPJPY", "AUDCAD", "NZDJPY", "GBPCAD", "GBPAUD",
    "EURNZD", "CADJPY", "CHFJPY", "CADCHF", "EURCAD", "EURCHF", "GBPCHF",
    "AUDCHF", "NZDCAD", "GBPNZD", "EURAUD", "AUDNZD", "AUDJPY",
)

STRATEGIES: Tuple[StrategySpec, ...] = (
    StrategySpec(
        name="CurrencyReversal",
        module="currency_reversal",
        signal_tf="D1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=_TIER1_FX,
        hypothesis="Đồng tiền vừa yếu tương đối so với rổ thì hồi lại trong ~1 tháng; "
                   "đồng vừa mạnh thì hạ nhiệt. Cược TƯƠNG ĐỐI, không cược hướng USD.",
        source="Li, B., Zhao, P., Hoi, S.C.H. & Gopalkrishnan, V. (2012) “PAMR: "
               "Passive-Aggressive Mean Reversion Strategy for Portfolio Selection”, "
               "Machine Learning 87(2) — "
               "D:/project-learning/documents/forex-strategies/PAMR_ Passive-Aggressive "
               "Mean Reversion Strategy for Portfolio Se.pdf · Menkhoff, L., Sarno, L., "
               "Schmeling, M. & Schrimpf, A. (2012) “Currency Momentum Strategies”, J. "
               "Financial Economics 106(3) — "
               "D:/project-learning/documents/forex-strategies/Currency Momentum "
               "Strategies.pdf · cổng chế độ theo Brière, M. & Drut, B. (2009, sửa 2010) "
               "“The Revenge of Fundamentals on Carry Trades during Crises”, Amundi "
               "Working Paper WP-005-2009 — "
               "D:/project-learning/documents/forex-strategies/Working Paper July 2009 - "
               "the revenge of fundamentals on carry trades during crises.pdf",
        sharpe_all=0.576, sharpe_oos=0.395, max_dd_pct=8.27,
        notes="Chạy ĐƠN LẺ thì bị phí swap ăn 25% lợi nhuận gộp. Chỉ nên chạy trong "
              "danh mục hai chân — xem `currency_carry.combined()`.",
    ),
    StrategySpec(
        name="CrossMeanReversion",
        module="cross_mean_reversion",
        signal_tf="H1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=_CROSS_20,
        hypothesis="Tỷ giá chéo là spread giữa hai đồng tiền, đã triệt tiêu thành "
                   "phần USD chung; lệch khỏi trung bình động của chính nó thì hồi "
                   "lại trong ~4-6 ngày.",
        source="Zheng Nan (2025) “Profitability of Pairs Trading Based on Cointegration in "
               "the Foreign Exchange Market”, MSc Finance thesis, Waseda — "
               "D:/project-learning/documents/forex-strategies/57231515_202509.pdf. Đo "
               "được time-stop hơn stop giá +85% — cửa sổ HL×4,32 · vào 2σ có quay lại · "
               "time-stop thay stop 3σ. Rổ của họ cũng là cross (JPY crosses)",
        sharpe_all=1.059, sharpe_oos=1.121, max_dd_pct=None,
        notes="CHIẾN LƯỢC H1 DUY NHẤT qua được cổng sau 13 hướng nội ngày bị bác bỏ. "
              "**PBO = 0,2571** — đầu tiên của dự án dưới ngưỡng 0,50; control "
              "p = 0,0000; 15/15 ô tham số dương; 6/7 năm dương. "
              "⚠️ Chi phí cross là ƯỚC LƯỢNG (dữ liệu không có chuỗi cross) và "
              "chiến lược chết ở chi phí ×2 — phải đo spread thật trước khi cấp vốn.",
    ),
    StrategySpec(
        name="CrossMomentum",
        module="cross_momentum",
        signal_tf="D1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=_CROSS_20,
        hypothesis="Cross vừa mạnh tương đối so với 19 cross khác thì tiếp tục mạnh "
                   "trong ~1 tháng; cross vừa yếu thì tiếp tục yếu.",
        source="Moskowitz, T.J., Ooi, Y.H. & Pedersen, L.H. (2012) “Time Series Momentum”, "
               "J. Financial Economics 104(2) — "
               "D:/project-learning/documents/forex-strategies/Time_series_momentum.pdf — "
               "momentum 1–12 tháng · Menkhoff, L., Sarno, L., Schmeling, M. & Schrimpf, "
               "A. (2011) “Currency Momentum Strategies”, BIS Working Paper 366 — "
               "D:/project-learning/documents/forex-strategies/work366.pdf",
        sharpe_all=0.897, sharpe_oos=0.920, max_dd_pct=None,
        notes="CHÂN THỨ TƯ. |tương quan| lớn nhất với ba chân cũ chỉ 0,188. "
              "Ghép vào: danh mục 1,003 → 1,287 (OOS 1,260 → 1,524), MaxDD "
              "12,6 → 9,2 σ, đuôi 10,9 → 8,9 σ.",
    ),
    StrategySpec(
        name="CurrencyCarry",
        module="currency_carry",
        signal_tf="D1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=_TIER1_FX,
        hypothesis="Đồng lãi suất cao được bù đắp cho rủi ro sụp; phần bù đó hiện "
                   "thành lợi nhuận trong giai đoạn bình lặng.",
        source="Olszweski, F. & Zhou, G. (2014) “Strategy diversification: Combining "
               "momentum and carry strategies within a foreign exchange portfolio”, J. "
               "Derivatives & Hedge Funds 19(4) — "
               "D:/project-learning/documents/forex-strategies/jdhf.2013.16.pdf — luật "
               "NGUYÊN VĂN 3 cao / 3 thấp · cổng chế độ theo Brière, M. & Drut, B. (2009, "
               "sửa 2010) “The Revenge of Fundamentals on Carry Trades during Crises”, "
               "Amundi Working Paper WP-005-2009 — "
               "D:/project-learning/documents/forex-strategies/Working Paper July 2009 - "
               "the revenge of fundamentals on carry trades during crises.pdf · gộp tỷ "
               "trọng trước khi tính phí theo Burnside, C., Eichenbaum, M. & Rebelo, S. "
               "(2011) “Carry Trade and Momentum in Currency Markets”, NBER WP 16942 — "
               "D:/project-learning/documents/forex-strategies/w16942.pdf",
        sharpe_all=0.151, sharpe_oos=0.745, max_dd_pct=10.37,
        notes="ĐƠN LẺ thì YẾU và bất ổn (DEV −0,114 / OOS +0,745) — KHÔNG chạy một "
              "mình. Giá trị của nó là làm CHÂN ĐỐI TRỌNG: tương quan −0,059 với "
              "reversal, và nó NHẬN swap (−1,716%/năm) trong khi reversal TRẢ.",
    ),
    StrategySpec(
        name="ZBandAUDCADH1",
        module="zband_audcad",
        signal_tf="H1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=("AUDCAD",),
        hypothesis="AUDCAD lệch khỏi trung bình động của chính nó thì hồi về — tự "
                   "tương quan bậc một ÂM và có ý nghĩa thống kê.",
        source="Sepp, A. & Lucic, V. (2026) “The Science and Practice of Trend-Following "
               "Systems”, arXiv:2607.19497v1 — "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.pdf. §chẩn "
               "đoán ngưỡng hoà vốn c* = √(π/2a)·|φ|/(1−φ) dùng để CHỌN công cụ trước khi "
               "backtest · Zheng Nan (2025) “Profitability of Pairs Trading Based on "
               "Cointegration in the Foreign Exchange Market”, MSc Finance thesis, Waseda "
               "— D:/project-learning/documents/forex-strategies/57231515_202509.pdf. Đo "
               "được time-stop hơn stop giá +85%",
        sharpe_all=0.775, sharpe_oos=0.649, max_dd_pct=6.72,
        notes="CHỌN BẰNG CHẨN ĐOÁN, không bằng Sharpe: φ = −0,0234 (t = −3,97) · c* 3,86 bps vs chi phí 0,99 → biên +2,87. "
              "698 lệnh · thắng 68.6% · net 4.6 bps/lệnh (t = 2.38). "
              "KHÔNG có cắt lỗ theo giá — đo được time-stop hơn SL theo ATR ở cả "
              "vòng 57 và 59. Qua 6/6 kiểm định gồm HAI control (thời điểm và chiều).",
    ),
    StrategySpec(
        name="ZBandNZDCADH1",
        module="zband_nzdcad",
        signal_tf="H1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=("NZDCAD",),
        hypothesis="NZDCAD lệch khỏi trung bình động của chính nó thì hồi về — tự "
                   "tương quan bậc một ÂM và có ý nghĩa thống kê.",
        source="Sepp, A. & Lucic, V. (2026) “The Science and Practice of Trend-Following "
               "Systems”, arXiv:2607.19497v1 — "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.pdf. §chẩn "
               "đoán ngưỡng hoà vốn c* = √(π/2a)·|φ|/(1−φ) dùng để CHỌN công cụ trước khi "
               "backtest · Zheng Nan (2025) “Profitability of Pairs Trading Based on "
               "Cointegration in the Foreign Exchange Market”, MSc Finance thesis, Waseda "
               "— D:/project-learning/documents/forex-strategies/57231515_202509.pdf. Đo "
               "được time-stop hơn stop giá +85%",
        sharpe_all=0.796, sharpe_oos=0.749, max_dd_pct=7.2,
        notes="CHỌN BẰNG CHẨN ĐOÁN, không bằng Sharpe: φ = −0,0206 (t = −3,50) · c* 3,38 bps vs chi phí 0,72 → biên +2,66. "
              "712 lệnh · thắng 69.9% · net 5.01 bps/lệnh (t = 2.48). "
              "KHÔNG có cắt lỗ theo giá — đo được time-stop hơn SL theo ATR ở cả "
              "vòng 57 và 59. Qua 6/6 kiểm định gồm HAI control (thời điểm và chiều).",
    ),
    StrategySpec(
        name="ZBandGBPAUDH1",
        module="zband_gbpaud",
        signal_tf="H1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=("GBPAUD",),
        hypothesis="GBPAUD lệch khỏi trung bình động của chính nó thì hồi về — tự "
                   "tương quan bậc một ÂM và có ý nghĩa thống kê.",
        source="Sepp, A. & Lucic, V. (2026) “The Science and Practice of Trend-Following "
               "Systems”, arXiv:2607.19497v1 — "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.pdf. §chẩn "
               "đoán ngưỡng hoà vốn c* = √(π/2a)·|φ|/(1−φ) dùng để CHỌN công cụ trước khi "
               "backtest · Zheng Nan (2025) “Profitability of Pairs Trading Based on "
               "Cointegration in the Foreign Exchange Market”, MSc Finance thesis, Waseda "
               "— D:/project-learning/documents/forex-strategies/57231515_202509.pdf. Đo "
               "được time-stop hơn stop giá +85%",
        sharpe_all=0.742, sharpe_oos=0.439, max_dd_pct=6.29,
        notes="CHỌN BẰNG CHẨN ĐOÁN, không bằng Sharpe: φ âm cùng dấu FORM/OOS · biên dương ở cả M30 (t = −6,35) và H1. "
              "283 lệnh · thắng 69.6% · net 10.84 bps/lệnh (t = 2.38). "
              "KHÔNG có cắt lỗ theo giá — đo được time-stop hơn SL theo ATR ở cả "
              "vòng 57 và 59. Qua 6/6 kiểm định gồm HAI control (thời điểm và chiều).",
    ),
    StrategySpec(
        name="ZBandGBPAUDM30",
        module="zband_gbpaud",
        signal_tf="M30", execution_tf="M30",
        stage=FORWARD_TEST,
        symbols=("GBPAUD",),
        hypothesis="GBPAUD lệch khỏi trung bình động của chính nó thì hồi về — tự "
                   "tương quan bậc một ÂM và có ý nghĩa thống kê.",
        source="Sepp, A. & Lucic, V. (2026) “The Science and Practice of Trend-Following "
               "Systems”, arXiv:2607.19497v1 — "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.pdf. §chẩn "
               "đoán ngưỡng hoà vốn c* = √(π/2a)·|φ|/(1−φ) dùng để CHỌN công cụ trước khi "
               "backtest · Zheng Nan (2025) “Profitability of Pairs Trading Based on "
               "Cointegration in the Foreign Exchange Market”, MSc Finance thesis, Waseda "
               "— D:/project-learning/documents/forex-strategies/57231515_202509.pdf. Đo "
               "được time-stop hơn stop giá +85%",
        sharpe_all=0.919, sharpe_oos=1.007, max_dd_pct=4.55,
        notes="CHỌN BẰNG CHẨN ĐOÁN, không bằng Sharpe: φ = −0,0255 (t = −6,35) · c* 2,98 bps vs chi phí 0,71 → biên +2,27. "
              "374 lệnh · thắng 68.7% · net 8.12 bps/lệnh (t = 2.86). "
              "KHÔNG có cắt lỗ theo giá — đo được time-stop hơn SL theo ATR ở cả "
              "vòng 57 và 59. Qua 6/6 kiểm định gồm HAI control (thời điểm và chiều).",
    ),
    StrategySpec(
        name="ZBandAUDCADM30",
        module="zband_audcad",
        signal_tf="M30", execution_tf="M30",
        stage=FORWARD_TEST,
        symbols=("AUDCAD",),
        hypothesis="AUDCAD lệch khỏi trung bình động của chính nó thì hồi về — tự "
                   "tương quan bậc một ÂM và có ý nghĩa thống kê.",
        source="Sepp, A. & Lucic, V. (2026) “The Science and Practice of Trend-Following "
               "Systems”, arXiv:2607.19497v1 — "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.pdf. §chẩn "
               "đoán ngưỡng hoà vốn c* = √(π/2a)·|φ|/(1−φ) dùng để CHỌN công cụ trước khi "
               "backtest · Zheng Nan (2025) “Profitability of Pairs Trading Based on "
               "Cointegration in the Foreign Exchange Market”, MSc Finance thesis, Waseda "
               "— D:/project-learning/documents/forex-strategies/57231515_202509.pdf. Đo "
               "được time-stop hơn stop giá +85%",
        sharpe_all=0.811, sharpe_oos=0.856, max_dd_pct=7.59,
        notes="CHỌN BẰNG CHẨN ĐOÁN, không bằng Sharpe: φ = −0,0255 (t = −6,36) · c* 2,98 bps vs chi phí 0,99 → biên +1,99. "
              "866 lệnh · thắng 69.5% · net 4.14 bps/lệnh (t = 2.5). "
              "KHÔNG có cắt lỗ theo giá — đo được time-stop hơn SL theo ATR ở cả "
              "vòng 57 và 59. Qua 6/6 kiểm định gồm HAI control (thời điểm và chiều).",
    ),
    StrategySpec(
        name="ZBandNZDCADM30",
        module="zband_nzdcad",
        signal_tf="M30", execution_tf="M30",
        stage=FORWARD_TEST,
        symbols=("NZDCAD",),
        hypothesis="NZDCAD lệch khỏi trung bình động của chính nó thì hồi về — tự "
                   "tương quan bậc một ÂM và có ý nghĩa thống kê.",
        source="Sepp, A. & Lucic, V. (2026) “The Science and Practice of Trend-Following "
               "Systems”, arXiv:2607.19497v1 — "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.pdf. §chẩn "
               "đoán ngưỡng hoà vốn c* = √(π/2a)·|φ|/(1−φ) dùng để CHỌN công cụ trước khi "
               "backtest · Zheng Nan (2025) “Profitability of Pairs Trading Based on "
               "Cointegration in the Foreign Exchange Market”, MSc Finance thesis, Waseda "
               "— D:/project-learning/documents/forex-strategies/57231515_202509.pdf. Đo "
               "được time-stop hơn stop giá +85%",
        sharpe_all=0.675, sharpe_oos=0.503, max_dd_pct=8.05,
        notes="CHỌN BẰNG CHẨN ĐOÁN, không bằng Sharpe: φ = −0,0303 (t = −7,56) · c* 3,56 bps vs chi phí 0,72 → biên +2,84. "
              "850 lệnh · thắng 70.7% · net 3.72 bps/lệnh (t = 2.12). "
              "KHÔNG có cắt lỗ theo giá — đo được time-stop hơn SL theo ATR ở cả "
              "vòng 57 và 59. Qua 6/6 kiểm định gồm HAI control (thời điểm và chiều).",
    ),
    StrategySpec(
        name="RsiDivGBPNZDM30",
        module="rsi_div_gbpnzd",
        signal_tf="M30", execution_tf="M30",
        stage=FORWARD_TEST,
        symbols=("GBPNZD",),
        hypothesis="QUAN HỆ giữa hai chuỗi — đại lượng KHÁC họ Z-Band, nên nó nhìn thị "
                   "trường theo cách khác chứ không lặp lại.",
        source="Wilder, J.W. (1978) “New Concepts in Technical Trading Systems”, Trend "
               "Research — KHÔNG có bản gốc trong kho tham chiếu. Công thức RSI cài lại từ "
               "định nghĩa gốc trong `shared/indicators.py`; phân kỳ ở đây được ĐO trên "
               "lưới chứ không lấy theo mô tả sách",
        sharpe_all=1.35, sharpe_oos=0.765, max_dd_pct=None,
        notes="|tương quan| với TOÀN BỘ chân đang chạy tối đa **0.096**. "
              "316 lệnh · thắng 62.0% · net 22.62 bps/lệnh (t = 4.25) · "
              "7/7 năm dương. Qua 7/7 kiểm định. MẠNH NHẤT toàn hệ: Sharpe 1,350 · t = 4,25 · vùng tham số 12/12 ô dương.",
    ),
    StrategySpec(
        name="StreakAUDCADM30",
        module="streak_audcad",
        signal_tf="M30", execution_tf="M30",
        stage=FORWARD_TEST,
        symbols=("AUDCAD",),
        hypothesis="ĐẾM nến liên tiếp, miễn nhiễm với độ lớn — đại lượng KHÁC họ Z-Band, nên nó nhìn thị "
                   "trường theo cách khác chứ không lặp lại.",
        source="Lo, A.W. & MacKinlay, A.C. (1990) “When Are Contrarian Profits Due to "
               "Stock Market Overreaction?”, Review of Financial Studies 3(2) — KHÔNG có "
               "bản gốc trong kho; trích GIÁN TIẾP qua "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.md. Biến thể "
               "ĐẾM thay cho đo độ lệch — về cấu tạo không thể trùng z-score",
        sharpe_all=0.969, sharpe_oos=0.803, max_dd_pct=None,
        notes="|tương quan| với TOÀN BỘ chân đang chạy tối đa **0.238**. "
              "902 lệnh · thắng 62.7% · net 6.72 bps/lệnh (t = 3.27) · "
              "7/7 năm dương. Qua 7/7 kiểm định. 902 lệnh — NHIỀU NHẤT toàn hệ, khoảng tin cậy hẹp nhất. Bỏ 5 tháng tốt nhất vẫn còn +29,97%.",
    ),
    StrategySpec(
        name="VolRegimeGBPCHFM30",
        module="vol_regime_gbpchf",
        signal_tf="M30", execution_tf="M30",
        stage=FORWARD_TEST,
        symbols=("GBPCHF",),
        hypothesis="TỶ SỐ σ ngắn/σ dài — đại lượng KHÁC họ Z-Band, nên nó nhìn thị "
                   "trường theo cách khác chứ không lặp lại.",
        source="Cont, R. (2001) “Empirical properties of asset returns: stylized facts and "
               "statistical issues”, Quantitative Finance 1(2) — KHÔNG có bản gốc trong "
               "kho; tính chất cụm biến động được dẫn lại trong "
               "D:/project-learning/documents/forex-strategies/1404.3274v1.md (Lempérière "
               "et al., “Two centuries of trend following”). Cược BIẾN ĐỘNG hồi quy, không "
               "phải giá hồi quy",
        sharpe_all=0.951, sharpe_oos=1.122, max_dd_pct=None,
        notes="|tương quan| với TOÀN BỘ chân đang chạy tối đa **0.105**. "
              "79 lệnh · thắng 67.1% · net 20.11 bps/lệnh (t = 2.92) · "
              "6/7 năm dương. Qua 7/7 kiểm định. OOS 1,122 CAO HƠN FORM 0,860 — dấu hiệu tốt nhất có thể có về việc không khớp quá vào giai đoạn hiệu chỉnh. ⚠️ Chỉ 79 lệnh, khoảng tin cậy rộng.",
    ),
    StrategySpec(
        name="VolRegimeAUDCHFM30",
        module="vol_regime_audchf",
        signal_tf="M30", execution_tf="M30",
        stage=FORWARD_TEST,
        symbols=("AUDCHF",),
        hypothesis="TỶ SỐ σ ngắn/σ dài — đại lượng KHÁC họ Z-Band, nên nó nhìn thị "
                   "trường theo cách khác chứ không lặp lại.",
        source="Cont, R. (2001) “Empirical properties of asset returns: stylized facts and "
               "statistical issues”, Quantitative Finance 1(2) — KHÔNG có bản gốc trong "
               "kho; tính chất cụm biến động được dẫn lại trong "
               "D:/project-learning/documents/forex-strategies/1404.3274v1.md (Lempérière "
               "et al., “Two centuries of trend following”). Cược BIẾN ĐỘNG hồi quy, không "
               "phải giá hồi quy",
        sharpe_all=0.752, sharpe_oos=1.254, max_dd_pct=None,
        notes="|tương quan| với TOÀN BỘ chân đang chạy tối đa **0.238**. "
              "252 lệnh · thắng 61.9% · net 9.58 bps/lệnh (t = 2.35) · "
              "7/7 năm dương. Qua 7/7 kiểm định. OOS 1,254 gấp 2,7 lần FORM 0,471. Cùng họ với GBPCHF, tương quan chỉ 0,105.",
    ),
    StrategySpec(
        name="RsiDivNZDCADM30",
        module="rsi_div_nzdcad",
        signal_tf="M30", execution_tf="M30",
        stage=FORWARD_TEST,
        symbols=("NZDCAD",),
        hypothesis="QUAN HỆ giữa hai chuỗi — đại lượng KHÁC họ Z-Band, nên nó nhìn thị "
                   "trường theo cách khác chứ không lặp lại.",
        source="Wilder, J.W. (1978) “New Concepts in Technical Trading Systems”, Trend "
               "Research — KHÔNG có bản gốc trong kho tham chiếu. Công thức RSI cài lại từ "
               "định nghĩa gốc trong `shared/indicators.py`; phân kỳ ở đây được ĐO trên "
               "lưới chứ không lấy theo mô tả sách",
        sharpe_all=0.782, sharpe_oos=1.147, max_dd_pct=None,
        notes="|tương quan| với TOÀN BỘ chân đang chạy tối đa **0.303**. "
              "725 lệnh · thắng 52.8% · net 4.72 bps/lệnh (t = 2.41) · "
              "6/7 năm dương. Qua 7/7 kiểm định. Cùng họ VÀ cùng công cụ với `RsiDivNZDCADH1` nhưng khác khung — tương quan 0,303, nên hai chân vào CHUNG một nhóm rủi ro.",
    ),
    StrategySpec(
        name="AccelGBPNZDH1",
        module="accel_gbpnzd",
        signal_tf="H1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=("GBPNZD",),
        hypothesis="ĐẠO HÀM BẬC HAI — đà đang mạnh lên hay chậm lại — đại lượng KHÁC họ Z-Band, nên nó nhìn thị "
                   "trường theo cách khác chứ không lặp lại.",
        source="Carver, R. (2015) “Systematic Trading”, Harriman House — quy tắc “accel” = "
               "đạo hàm của EWMAC, bản cài đặt ở "
               "`project-refer/carver-systematic-trading/core/forecast.py`. Ở đây dùng "
               "NGƯỢC chiều Carver: vòng 53 đo đúng khung dự báo liên tục của ông trên FX "
               "và mọi họ thuận chiều cho gross ÂM · Sepp, A. & Lucic, V. (2026) “The "
               "Science and Practice of Trend-Following Systems”, arXiv:2607.19497v1 — "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.pdf. §chẩn "
               "đoán ngưỡng hoà vốn c* = √(π/2a)·|φ|/(1−φ) dùng để CHỌN công cụ trước khi "
               "backtest §6.2 phân rã đóng góp của đà thành phần drift (∝√span) và phần tự "
               "tương quan (∝1/√span)",
        sharpe_all=1.098, sharpe_oos=0.581, max_dd_pct=None,
        notes="|tương quan| với TOÀN BỘ chân đang chạy tối đa **0.144**. "
              "112 lệnh · thắng 63.4% · net 24.15 bps/lệnh (t = 3.49) · "
              "6/7 năm dương. Qua 7/7 kiểm định. HỌ ACCEL: mọi họ khác đo bậc không (mức) hoặc bậc một (đà); đây là lần đầu dự án khai thác bậc hai. net 24,15 bps/lệnh, cao thứ nhì toàn hệ.",
    ),
    StrategySpec(
        name="RsiDivNZDCADH1",
        module="rsi_div_nzdcad",
        signal_tf="H1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=("NZDCAD",),
        hypothesis="QUAN HỆ giữa hai chuỗi — giá lập cực trị mới mà RSI thì không — đại lượng KHÁC HẲN họ Z-Band, nên nó "
                   "nhìn thị trường theo một cách khác chứ không lặp lại.",
        source="Wilder, J.W. (1978) “New Concepts in Technical Trading Systems”, Trend "
               "Research — KHÔNG có bản gốc trong kho tham chiếu. Công thức RSI cài lại từ "
               "định nghĩa gốc trong `shared/indicators.py`; phân kỳ ở đây được ĐO trên "
               "lưới chứ không lấy theo mô tả sách",
        sharpe_all=0.828, sharpe_oos=0.905, max_dd_pct=None,
        notes="HỌ MỚI, không phải Z-Band. |tương quan| với TOÀN BỘ chân đang "
              "chạy tối đa **0.178** — đây là lý do nhận, không phải Sharpe. "
              "350 lệnh · thắng 53.7% · net 7.35 bps/lệnh (t = 2.56) · "
              "7/7 năm dương. Qua 7/7 kiểm định. Ô CÂN BẰNG NHẤT của ba họ mới (FORM 0,795 vs OOS 0,905) và là chân duy nhất trong nhóm đạt 7/7 năm dương.",
    ),
    StrategySpec(
        name="StreakGBPCADH1",
        module="streak_gbpcad",
        signal_tf="H1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=("GBPCAD",),
        hypothesis="ĐẾM nến liên tiếp — miễn nhiễm với độ lớn — đại lượng KHÁC HẲN họ Z-Band, nên nó "
                   "nhìn thị trường theo một cách khác chứ không lặp lại.",
        source="Lo, A.W. & MacKinlay, A.C. (1990) “When Are Contrarian Profits Due to "
               "Stock Market Overreaction?”, Review of Financial Studies 3(2) — KHÔNG có "
               "bản gốc trong kho; trích GIÁN TIẾP qua "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.md. Biến thể "
               "ĐẾM thay cho đo độ lệch — về cấu tạo không thể trùng z-score",
        sharpe_all=0.967, sharpe_oos=0.521, max_dd_pct=None,
        notes="HỌ MỚI, không phải Z-Band. |tương quan| với TOÀN BỘ chân đang "
              "chạy tối đa **0.084** — đây là lý do nhận, không phải Sharpe. "
              "472 lệnh · thắng 56.6% · net 7.38 bps/lệnh (t = 3.02) · "
              "6/7 năm dương. Qua 7/7 kiểm định. Sharpe cao nhất ba họ mới (0,967), t = 3,02. FORM/OOS chênh 2,3 lần — chấp nhận được nhưng phải theo dõi ở live.",
    ),
    StrategySpec(
        name="StreakGBPAUDH1",
        module="streak_gbpaud",
        signal_tf="H1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=("GBPAUD",),
        hypothesis="ĐẾM nến liên tiếp — miễn nhiễm với độ lớn — đại lượng KHÁC HẲN họ Z-Band, nên nó "
                   "nhìn thị trường theo một cách khác chứ không lặp lại.",
        source="Lo, A.W. & MacKinlay, A.C. (1990) “When Are Contrarian Profits Due to "
               "Stock Market Overreaction?”, Review of Financial Studies 3(2) — KHÔNG có "
               "bản gốc trong kho; trích GIÁN TIẾP qua "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.md. Biến thể "
               "ĐẾM thay cho đo độ lệch — về cấu tạo không thể trùng z-score",
        sharpe_all=0.809, sharpe_oos=0.741, max_dd_pct=None,
        notes="HỌ MỚI, không phải Z-Band. |tương quan| với TOÀN BỘ chân đang "
              "chạy tối đa **0.07** — đây là lý do nhận, không phải Sharpe. "
              "257 lệnh · thắng 57.6% · net 9.71 bps/lệnh (t = 2.53) · "
              "6/7 năm dương. Qua 7/7 kiểm định. Cùng họ với GBPCAD nhưng tương quan giữa hai chân chỉ 0,091 — cùng cách nhìn, khác công cụ, và đó là đa dạng hoá thật.",
    ),
    StrategySpec(
        name="VolRegimeGBPAUDH1",
        module="vol_regime_gbpaud",
        signal_tf="H1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=("GBPAUD",),
        hypothesis="TỶ SỐ σ ngắn/σ dài — cược BIẾN ĐỘNG hồi quy, không phải giá — đại lượng KHÁC HẲN họ Z-Band, nên nó "
                   "nhìn thị trường theo một cách khác chứ không lặp lại.",
        source="Cont, R. (2001) “Empirical properties of asset returns: stylized facts and "
               "statistical issues”, Quantitative Finance 1(2) — KHÔNG có bản gốc trong "
               "kho; tính chất cụm biến động được dẫn lại trong "
               "D:/project-learning/documents/forex-strategies/1404.3274v1.md (Lempérière "
               "et al., “Two centuries of trend following”). Cược BIẾN ĐỘNG hồi quy, không "
               "phải giá hồi quy",
        sharpe_all=0.818, sharpe_oos=0.628, max_dd_pct=None,
        notes="HỌ MỚI, không phải Z-Band. |tương quan| với TOÀN BỘ chân đang "
              "chạy tối đa **0.121** — đây là lý do nhận, không phải Sharpe. "
              "282 lệnh · thắng 63.1% · net 8.17 bps/lệnh (t = 2.46) · "
              "6/7 năm dương. Qua 7/7 kiểm định. Tỷ lệ thắng 63,1%, cao nhất ba họ mới. Cùng công cụ GBPAUD với chân streak nhưng đọc đại lượng khác hẳn.",
    ),
    StrategySpec(
        name="ZBandEURCHFH1",
        module="zband_eurchf",
        signal_tf="H1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=("EURCHF",),
        hypothesis="EURCHF lệch khỏi trung bình động của chính nó thì hồi về "
                   "— tự tương quan bậc một ÂM và có ý nghĩa thống kê.",
        source="Sepp, A. & Lucic, V. (2026) “The Science and Practice of Trend-Following "
               "Systems”, arXiv:2607.19497v1 — "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.pdf. §chẩn "
               "đoán ngưỡng hoà vốn c* = √(π/2a)·|φ|/(1−φ) dùng để CHỌN công cụ trước khi "
               "backtest · Zheng Nan (2025) “Profitability of Pairs Trading Based on "
               "Cointegration in the Foreign Exchange Market”, MSc Finance thesis, Waseda "
               "— D:/project-learning/documents/forex-strategies/57231515_202509.pdf. Đo "
               "được time-stop hơn stop giá +85%",
        sharpe_all=0.795, sharpe_oos=0.708, max_dd_pct=5.16,
        notes="CHỌN BẰNG CHẨN ĐOÁN: φ = −0,0285 (t = −4,84) · c* 4,73 vs chi phí 0,46 → biên +4,27. 630 lệnh · thắng 67.9% · "
              "net 3.14 bps/lệnh (t = 2.45). Qua 7/7 kiểm định gồm hai "
              "control và vùng tham số 8-9/9 ô dương. 630 lệnh — NHIỀU NHẤT trong các chân H1, nên khoảng tin cậy của kỳ vọng hẹp hơn hẳn những chân chỉ có trăm lệnh.",
    ),
    StrategySpec(
        name="ZBandGBPUSDH1",
        module="zband_gbpusd",
        signal_tf="H1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=("GBPUSD",),
        hypothesis="GBPUSD lệch khỏi trung bình động của chính nó thì hồi về "
                   "— tự tương quan bậc một ÂM và có ý nghĩa thống kê.",
        source="Sepp, A. & Lucic, V. (2026) “The Science and Practice of Trend-Following "
               "Systems”, arXiv:2607.19497v1 — "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.pdf. §chẩn "
               "đoán ngưỡng hoà vốn c* = √(π/2a)·|φ|/(1−φ) dùng để CHỌN công cụ trước khi "
               "backtest · Zheng Nan (2025) “Profitability of Pairs Trading Based on "
               "Cointegration in the Foreign Exchange Market”, MSc Finance thesis, Waseda "
               "— D:/project-learning/documents/forex-strategies/57231515_202509.pdf. Đo "
               "được time-stop hơn stop giá +85%",
        sharpe_all=0.679, sharpe_oos=0.738, max_dd_pct=7.25,
        notes="CHỌN BẰNG CHẨN ĐOÁN: φ = −0,0181 (t = −3,47) · c* 2,97 vs chi phí 1,20 → biên +1,77. 113 lệnh · thắng 69.0% · "
              "net 14.94 bps/lệnh (t = 2.12). Qua 7/7 kiểm định gồm hai "
              "control và vùng tham số 8-9/9 ô dương. CHÂN ĐẦU TIÊN trên MAJOR. 16 chân còn lại đều giao dịch cross tổng hợp, nên rủi ro dựng cross (spread ước lượng, hai chân khớp lệch nhau) là rủi ro CHUNG của cả danh mục. GBPUSD là công cụ thật: spread đo trực tiếp, khớp một lệnh.",
    ),
    StrategySpec(
        name="ZBandEURGBPH1",
        module="zband_eurgbp",
        signal_tf="H1", execution_tf="H1",
        stage=FORWARD_TEST,
        symbols=("EURGBP",),
        hypothesis="EURGBP lệch khỏi trung bình động của chính nó thì hồi về "
                   "— tự tương quan bậc một ÂM và có ý nghĩa thống kê.",
        source="Sepp, A. & Lucic, V. (2026) “The Science and Practice of Trend-Following "
               "Systems”, arXiv:2607.19497v1 — "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.pdf. §chẩn "
               "đoán ngưỡng hoà vốn c* = √(π/2a)·|φ|/(1−φ) dùng để CHỌN công cụ trước khi "
               "backtest · Zheng Nan (2025) “Profitability of Pairs Trading Based on "
               "Cointegration in the Foreign Exchange Market”, MSc Finance thesis, Waseda "
               "— D:/project-learning/documents/forex-strategies/57231515_202509.pdf. Đo "
               "được time-stop hơn stop giá +85%",
        sharpe_all=0.713, sharpe_oos=0.307, max_dd_pct=6.31,
        notes="CHỌN BẰNG CHẨN ĐOÁN: φ = −0,0247 (t = −4,20) · c* 4,09 vs chi phí 0,52 → biên +3,56. 121 lệnh · thắng 80.2% · "
              "net 19.68 bps/lệnh (t = 2.21). Qua 7/7 kiểm định gồm hai "
              "control và vùng tham số 8-9/9 ô dương. Cửa sổ 384 nến H1 = 16 ngày giao dịch, chậm nhất nhóm H1 — bắt nhịp hồi quy khác hẳn ba chân N24-N96. Thắng 80,2%, cao nhất toàn hệ.",
    ),
    StrategySpec(
        name="ZBandGBPNZDH4",
        module="zband_gbpnzd",
        signal_tf="H4", execution_tf="H4",
        stage=FORWARD_TEST,
        symbols=("GBPNZD",),
        hypothesis="GBPNZD lệch khỏi trung bình động của chính nó thì hồi về "
                   "— tự tương quan bậc một ÂM và có ý nghĩa thống kê.",
        source="Sepp, A. & Lucic, V. (2026) “The Science and Practice of Trend-Following "
               "Systems”, arXiv:2607.19497v1 — "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.pdf. §chẩn "
               "đoán ngưỡng hoà vốn c* = √(π/2a)·|φ|/(1−φ) dùng để CHỌN công cụ trước khi "
               "backtest · Zheng Nan (2025) “Profitability of Pairs Trading Based on "
               "Cointegration in the Foreign Exchange Market”, MSc Finance thesis, Waseda "
               "— D:/project-learning/documents/forex-strategies/57231515_202509.pdf. Đo "
               "được time-stop hơn stop giá +85%",
        sharpe_all=1.214, sharpe_oos=0.879, max_dd_pct=5.04,
        notes="CHỌN BẰNG CHẨN ĐOÁN: φ = −0,0090 · c* 2,92 vs chi phí 0,74 → biên +2,18. 562 lệnh · thắng 68.7% · "
              "net 8.11 bps/lệnh (t = 3.84) · **7/7 năm dương**. Qua 7/7 "
              "kiểm định gồm hai control và VÙNG THAM SỐ 8-9/9 ô lân cận "
              "dương. GBPNZD bị LOẠI ở M30 (FORM 1,551 / OOS 0,238) nhưng ĐẠT ở H4 (1,398 / 0,879, 7/7 năm) — mỗi ô phải kiểm định riêng, không suy từ ô khác.",
    ),
    StrategySpec(
        name="ZBandAUDCADH4",
        module="zband_audcad",
        signal_tf="H4", execution_tf="H4",
        stage=FORWARD_TEST,
        symbols=("AUDCAD",),
        hypothesis="AUDCAD lệch khỏi trung bình động của chính nó thì hồi về "
                   "— tự tương quan bậc một ÂM và có ý nghĩa thống kê.",
        source="Sepp, A. & Lucic, V. (2026) “The Science and Practice of Trend-Following "
               "Systems”, arXiv:2607.19497v1 — "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.pdf. §chẩn "
               "đoán ngưỡng hoà vốn c* = √(π/2a)·|φ|/(1−φ) dùng để CHỌN công cụ trước khi "
               "backtest · Zheng Nan (2025) “Profitability of Pairs Trading Based on "
               "Cointegration in the Foreign Exchange Market”, MSc Finance thesis, Waseda "
               "— D:/project-learning/documents/forex-strategies/57231515_202509.pdf. Đo "
               "được time-stop hơn stop giá +85%",
        sharpe_all=1.062, sharpe_oos=1.059, max_dd_pct=3.13,
        notes="CHỌN BẰNG CHẨN ĐOÁN: φ = −0,0179 · c* 5,88 vs chi phí 0,99 → biên +4,89. 217 lệnh · thắng 68.7% · "
              "net 13.73 bps/lệnh (t = 3.34) · **7/7 năm dương**. Qua 7/7 "
              "kiểm định gồm hai control và VÙNG THAM SỐ 8-9/9 ô lân cận "
              "dương. Ô CÂN BẰNG NHẤT dự án: FORM 1,067 vs OOS 1,059, chênh 0,8%. Vào chung nhóm rủi ro ZBand_AUDCAD với hai chân H1/M30.",
    ),
    StrategySpec(
        name="ZBandGBPAUDH4",
        module="zband_gbpaud",
        signal_tf="H4", execution_tf="H4",
        stage=FORWARD_TEST,
        symbols=("GBPAUD",),
        hypothesis="GBPAUD lệch khỏi trung bình động của chính nó thì hồi về "
                   "— tự tương quan bậc một ÂM và có ý nghĩa thống kê.",
        source="Sepp, A. & Lucic, V. (2026) “The Science and Practice of Trend-Following "
               "Systems”, arXiv:2607.19497v1 — "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.pdf. §chẩn "
               "đoán ngưỡng hoà vốn c* = √(π/2a)·|φ|/(1−φ) dùng để CHỌN công cụ trước khi "
               "backtest · Zheng Nan (2025) “Profitability of Pairs Trading Based on "
               "Cointegration in the Foreign Exchange Market”, MSc Finance thesis, Waseda "
               "— D:/project-learning/documents/forex-strategies/57231515_202509.pdf. Đo "
               "được time-stop hơn stop giá +85%",
        sharpe_all=0.904, sharpe_oos=0.563, max_dd_pct=5.02,
        notes="CHỌN BẰNG CHẨN ĐOÁN: φ = −0,0135 · c* 4,42 vs chi phí 0,71 → biên +3,70. 365 lệnh · thắng 69.6% · "
              "net 10.67 bps/lệnh (t = 2.89) · **7/7 năm dương**. Qua 7/7 "
              "kiểm định gồm hai control và VÙNG THAM SỐ 8-9/9 ô lân cận "
              "dương. Vào chung nhóm rủi ro ZBand_GBPAUD với hai chân H1/M30.",
    ),
    StrategySpec(
        name="CrossXsReversion",
        module="cross_xs_reversion",
        signal_tf="H4", execution_tf="H4",
        stage=FORWARD_TEST,
        symbols=_CROSS_20,
        hypothesis="Cross vừa lệch xa trung bình 5 ngày HƠN 19 cross khác thì hồi về "
                   "trong ~2 ngày. Cược tương đối, không cược mức tuyệt đối.",
        source="Lo, A.W. & MacKinlay, A.C. (1990) “When Are Contrarian Profits Due to "
               "Stock Market Overreaction?”, Review of Financial Studies 3(2) — KHÔNG có "
               "bản gốc trong kho; trích GIÁN TIẾP qua "
               "D:/project-learning/documents/forex-strategies/2607.19497v1.md — tự tương "
               "quan CHÉO là nguồn lợi nhuận contrarian · Avellaneda, M. & Lee, J.-H. "
               "(2010) “Statistical Arbitrage in the U.S. Equities Market”, Quantitative "
               "Finance 10(7) — KHÔNG có bản gốc trong kho; trích GIÁN TIẾP qua "
               "D:/project-learning/documents/forex-strategies/57231515_202509.md (bản "
               "giản lược: xếp hạng z thô thay phần dư PCA) · Olszweski, F. & Zhou, G. "
               "(2014) “Strategy diversification: Combining momentum and carry strategies "
               "within a foreign exchange portfolio”, J. Derivatives & Hedge Funds 19(4) — "
               "D:/project-learning/documents/forex-strategies/jdhf.2013.16.pdf (chia đều "
               "1/N cứng)",
        sharpe_all=0.460, sharpe_oos=0.381, max_dd_pct=7.75,
        notes="CHÂN THỨ NĂM — chân H4 ĐẦU TIÊN. Điểm giá trị KHÔNG phải Sharpe (0,460 "
              "là chân yếu thứ nhì) mà là TÍNH TRỰC GIAO: |tương quan| với cả bốn "
              "chân cũ tối đa **0,074**. Cùng đại lượng z với chân H1 nhưng cược khác "
              "hẳn — H1 cược 'cross lệch khỏi CHÍNH NÓ', chân này cược 'cross lệch hơn "
              "19 cross KHÁC', nên nó KHÔNG chịu cú sốc chung toàn rổ mà chân H1 chịu. "
              "Control p = 0,0000 · bootstrap P(<0) = 7,9% · 6/7 năm dương · bỏ 5 "
              "tháng tốt nhất vẫn giữ dấu. ⚠️ Chết ở chi phí ×5; vùng tham số "
              "(n_leg 7, tái cân bằng 2 ngày) tái lập được trên cả M30 và H4.",
    ),
)

# ═══════════════════════════════════════════════════════════ danh mục vận hành
# BA CHÂN, CHIA ĐỀU, chuẩn hoá cùng biến động trước khi ghép.
#
# Ba nguồn ĐỘC LẬP cùng kết luận rằng chia đều nhiều chân không tương quan là cách
# ghép tốt nhất, và lợi ích chính là CẮT DRAWDOWN chứ không phải tăng lợi nhuận:
#   Olszweski & Zhou (2014)  momentum 0,79 + carry 0,63  ->  0,98 · MaxDD −29% -> −8,95%
#   Burnside/Eichenbaum/Rebelo (NBER w16942)  carry 0,41 + mom 0,62  ->  **0,98**
#   đo được ở đây            0,544 / 0,364 / 1,145        ->  **1,199** · MaxDD −65%
#
# Burnside mô tả đúng cơ chế `currency_carry.combined()` đang dùng:
#   "Khi hai chiến lược ĐỒNG THUẬN về dấu, vị thế ròng là ±1/n. Khi BẤT ĐỒNG, vị thế
#    ròng là ZERO." — tức gộp tỷ trọng TRƯỚC khi tính chi phí, không cộng hai chuỗi
#   lợi nhuận đã tính phí riêng.
#
# Ma trận tương quan đo được — gần trực giao hoàn hảo, đây là lý do nó hoạt động:
#              reversal   carry   cross_H1
#   reversal      1,000  −0,097     +0,054
#   carry        −0,097   1,000     +0,008
#   cross_H1     +0,054  +0,008      1,000
PORTFOLIO = {
    "name": "TwentySevenLegFX",
    # 14 chiến lược, CHÍN nhóm rủi ro — xem `portfolio.RISK_GROUPS`. Tỷ trọng KHÔNG
    # chia đều theo chiến lược mà chia đều theo NHÓM: ba chân cùng công cụ ở ba khung
    # chỉ được MỘT suất, nếu không thì danh mục âm thầm gấp ba phơi nhiễm vào AUDCAD.
    "legs": {
        "CurrencyReversal": 1 / 21, "CurrencyCarry": 1 / 21,
        "CrossMeanReversion": 1 / 21, "CrossMomentum": 1 / 21,
        "CrossXsReversion": 1 / 21,
        "ZBandAUDCADH1": 1 / 63, "ZBandAUDCADM30": 1 / 63, "ZBandAUDCADH4": 1 / 63,
        "ZBandGBPAUDH1": 1 / 63, "ZBandGBPAUDM30": 1 / 63, "ZBandGBPAUDH4": 1 / 63,
        "ZBandNZDCADH1": 1 / 42, "ZBandNZDCADM30": 1 / 42,
        "ZBandGBPNZDH4": 1 / 21,
        "ZBandEURCHFH1": 1 / 21, "ZBandGBPUSDH1": 1 / 21, "ZBandEURGBPH1": 1 / 21,
        "RsiDivNZDCADH1": 1 / 42, "RsiDivNZDCADM30": 1 / 42,
        "StreakGBPCADH1": 1 / 21, "StreakGBPAUDH1": 1 / 21,
        "VolRegimeGBPAUDH1": 1 / 21,
        "RsiDivGBPNZDM30": 1 / 21, "StreakAUDCADM30": 1 / 21,
        "VolRegimeGBPCHFM30": 1 / 21, "VolRegimeAUDCHFM30": 1 / 21,
        "AccelGBPNZDH1": 1 / 21},
    "vol_normalise": True,      # chuẩn hoá cùng biến động TRƯỚC khi chia đều —
                                # không làm thì chân biến động lớn nhất áp đảo
    "entry_points": {
        "CurrencyReversal": "src.python.strategies.d1.currency_carry:combined",
        "CurrencyCarry": "src.python.strategies.d1.currency_carry:combined",
        "CrossMeanReversion": "src.python.strategies.h1.cross_mean_reversion:live_decisions",
        "CrossMomentum": "src.python.strategies.d1.cross_momentum:live_targets",
        "CrossXsReversion": "src.python.strategies.h4.cross_xs_reversion:live_targets",
        "ZBandAUDCADH1": "src.python.strategies.h1.zband_audcad:live_decision",
        "ZBandNZDCADH1": "src.python.strategies.h1.zband_nzdcad:live_decision",
        "ZBandGBPAUDH1": "src.python.strategies.h1.zband_gbpaud:live_decision",
        "ZBandGBPAUDM30": "src.python.strategies.m30.zband_gbpaud:live_decision",
        "ZBandAUDCADM30": "src.python.strategies.m30.zband_audcad:live_decision",
        "ZBandNZDCADM30": "src.python.strategies.m30.zband_nzdcad:live_decision",
        "ZBandGBPNZDH4": "src.python.strategies.h4.zband_gbpnzd:live_decision",
        "ZBandAUDCADH4": "src.python.strategies.h4.zband_audcad:live_decision",
        "ZBandGBPAUDH4": "src.python.strategies.h4.zband_gbpaud:live_decision",
        "ZBandEURCHFH1": "src.python.strategies.h1.zband_eurchf:live_decision",
        "ZBandGBPUSDH1": "src.python.strategies.h1.zband_gbpusd:live_decision",
        "ZBandEURGBPH1": "src.python.strategies.h1.zband_eurgbp:live_decision",
        "RsiDivNZDCADH1": "src.python.strategies.h1.rsi_div_nzdcad:live_decision",
        "StreakGBPCADH1": "src.python.strategies.h1.streak_gbpcad:live_decision",
        "StreakGBPAUDH1": "src.python.strategies.h1.streak_gbpaud:live_decision",
        "VolRegimeGBPAUDH1": "src.python.strategies.h1.vol_regime_gbpaud:live_decision",
        "AccelGBPNZDH1": "src.python.strategies.h1.accel_gbpnzd:live_decision",
        "RsiDivGBPNZDM30": "src.python.strategies.m30.rsi_div_gbpnzd:live_decision",
        "RsiDivNZDCADM30": "src.python.strategies.m30.rsi_div_nzdcad:live_decision",
        "StreakAUDCADM30": "src.python.strategies.m30.streak_audcad:live_decision",
        "VolRegimeGBPCHFM30": "src.python.strategies.m30.vol_regime_gbpchf:live_decision",
        "VolRegimeAUDCHFM30": "src.python.strategies.m30.vol_regime_audchf:live_decision",
    },
    "sizing": "src.python.execution.portfolio_sizing:size_portfolio",
    "leverage_policy": "src.python.execution.ftmo_leverage_policy:decide",
    "decision_log": "src.python.execution.decision_log:record_many",
    # Bốn điểm nối THÊM 14/08/2026 — trước đó đường live thiếu hẳn bốn lớp này.
    # `target_weights` là chỗ 27 chân gộp thành MỘT vector tỷ trọng và triệt tiêu
    # nhau; thiếu nó thì live chỉ chạy 3/27 chân trong khi backtest chạy đủ 27.
    "target_weights": "src.python.strategies.portfolio:target_weights",
    "netting_report": "src.python.strategies.portfolio:netting_report",
    "disaster_stop": "src.python.execution.disaster_stop:compute_book",
    "live_risk": "src.python.execution.portfolio_risk:snapshot",
    # Bốn điểm nối THÊM sau đợt kiểm toán 14/08 (docs/forex/09_kiem_toan_thuc_thi.md).
    # `position_book` là chỗ bịt lỗ hổng NẶNG NHẤT: 27 chân thoát bằng time-stop,
    # time-stop cần `bars_held`, và trước đó KHÔNG module nào tính giá trị đó.
    "order_plan": "src.python.execution.order_plan:build",
    "order_router": "src.python.execution.order_router:OrderRouter",
    "position_book": "src.python.execution.position_book:PositionBook",
    "trading_control": "src.python.execution.trading_control:entry_allowed",
    # Trần đòn bẩy — ĐO LẠI 15/08 sau khi sửa look-ahead `i = j` → `i = j + 1` trong
    # engine backtest. Số cũ 3,7x dựa trên chuỗi đã bị thổi phồng; với chuỗi đúng nó
    # cho MaxDD 9,35%, vượt sàn nội bộ 9%. Trần đo được nay là 3,51x → lấy 3,5.
    # Con số này phải đo lại mỗi khi danh mục đổi số chân.
    # NÂNG 3,5 → 5,0 ngày 15/08/2026 (đòn bẩy THỰC bão hoà ở 5,25x). SSOT là
    # `execution/ftmo_leverage_policy.LEVERAGE_MAX`; con số ở đây chỉ để hiển thị
    # và phải khớp — `tests/test_rulebook.py` cưỡng chế điều đó.
    "leverage_cap": 6.0,
    "max_dd_self_cap_pct": 9.0,  # sàn nội bộ, chặt hơn mốc 10% của FTMO
    "stage": FORWARD_TEST,
    # Sau đủ chi phí (spread + commission + swap + biên broker 1,0%/năm)
    # Đo lại 13/08/2026 sau khi thêm chân thứ năm `CrossXsReversion` (H4):
    #   bốn chân  1,287 ALL · 1,170 FORM · 1,524 OOS · ngày tệ nhất −8,9σ
    #   năm chân  1,310 ALL · 1,219 FORM · 1,506 OOS · ngày tệ nhất −4,49σ
    #   MƯỜI MỘT  1,833 ALL · 1,785 FORM · 1,966 OOS · ngày tệ nhất −2,91σ
    #   MƯỜI BỐN  2,178 ALL · 2,207 FORM · 2,154 OOS · ngày tệ nhất −2,21σ
    #   MƯỜI BẢY  2,501 ALL · 2,612 FORM · 2,317 OOS · ngày tệ nhất −1,88σ
    #   HAI MỐT   2,879 ALL · 3,037 FORM · 2,616 OOS · ngày tệ nhất −1,50σ
    #   HAI BẢY   3,313 ALL · 3,451 FORM · 3,106 OOS · ngày tệ nhất −1,23σ
    #   ⚠️ BA DÒNG TRÊN LÀ SỐ CŨ, ĐÃ BỊ THỔI PHỒNG. Sửa look-ahead 15/08/2026
    #   (`i = j` → `i = j + 1`): 18,8% số lệnh vào lại ở giá MỞ CỬA của chính nến
    #   vừa thoát ở giá ĐÓNG CỬA — không thực hiện được, và mang 27,0% tổng lãi.
    #   SỐ ĐÚNG:  3,134 ALL · 3,330 FORM · 2,805 OOS · ngày tệ nhất −1,25σ
    #             MaxDD 5,60σ · 7/7 năm dương · |corr| nhóm 0,303
    # M30 từ chỗ CHỈ CÓ Z-Band nay có bốn họ (rsi_div · streak · vol_regime + z-band).
    # Đó là nguồn của phần lớn mức tăng: khung này trước đây không có đa dạng hoá
    # cách nhìn nào, nên mọi chân đều lỗ cùng lúc trong cùng một loại chế độ.
    # Bốn chân cuối (14/08) thuộc BA HỌ MỚI — phân kỳ giá/RSI, đếm chuỗi nến, tỷ số
    # hai độ lệch chuẩn. Chúng KHÔNG đọc "giá cách trung bình bao xa" như 17 chân
    # trước, nên |tương quan| với toàn bộ danh mục tối đa 0,206. Sharpe tăng 15% nhờ
    # đa dạng hoá CÁCH NHÌN, không phải nhờ chân nào mạnh hơn.
    # Ba chân H1 thêm 14/08 (EURCHF · GBPUSD · EURGBP) — GBPUSD là chân ĐẦU TIÊN trên
    # MAJOR, nên nó cũng là chân đầu tiên không mang rủi ro dựng cross tổng hợp.
    # FORM và OOS chênh 2,4% — đây là dấu hiệu mạnh nhất rằng danh mục KHÔNG bị khớp
    # quá vào giai đoạn hiệu chỉnh, vì OOS chưa từng được dùng để chọn bất cứ thứ gì.
    # Sáu chân Z-Band (13/08/2026) gộp thành BA nhóm rủi ro theo công cụ, nên danh mục
    # có 11 chiến lược nhưng TÁM suất bằng nhau — xem `portfolio.RISK_GROUPS`.
    # Sharpe nhích nhẹ, nhưng giá trị thật nằm ở ĐUÔI: ngày tệ nhất giảm gần một nửa.
    # Đó đúng là thứ ràng buộc TAIL của FTMO quan tâm, không phải Sharpe.
    # ĐO LẠI 15/08/2026 sau khi sửa look-ahead `i = j` → `i = j + 1`.
    # Số cũ (3,313 / 3,451 / 3,106) bị thổi phồng bởi 18,8% lệnh vào lại ở
    # giá MỞ CỬA của chính nến vừa thoát ở giá ĐÓNG CỬA.
    # ⚠️ ĐO LẠI 15/08/2026 SAU KHI SỬA MÔ HÌNH CHI PHÍ CROSS.
    #
    # `fx_cross_pairs.spread_pips()` đổi từ `đo_được × 1,5` sang
    # `max(đo_được × 3,0, sàn tham chiếu FTMO)` — chi phí 20 cross tăng 2–3 lần.
    # Bộ số CŨ (Sharpe 3,134 / FORM 3,330 / OOS 2,805) tính trên mô hình rẻ hơn
    # thực tế, nên nó là số của một hệ không còn tồn tại.
    #
    #     Sharpe ALL   3,134 → 2,874   (−8,3%)
    #     Sharpe OOS   2,805 → 2,505   (−10,7%)
    #
    # Chi phí tăng 2–3 lần mà Sharpe chỉ giảm ~8–11% là bằng chứng biên lợi nhuận
    # KHÔNG mỏng tới mức phụ thuộc giả định chi phí — đúng thứ bài stress chi phí
    # (kiểm định 5 của quy trình thăng cấp) sinh ra để trả lời.
    #
    # Đo bằng `research/fx/recost_portfolio.py`, chạy lại được bất cứ lúc nào.
    "sharpe_all": 2.874, "sharpe_form": 3.087, "sharpe_oos": 2.505,
    "sortino_all": 3.869, "calmar_all": 1.849,
    "years_positive": "7/7",
    "max_dd_reduction_vs_best_leg": "-77%",
    "worst_day_sigma": 1.27,
    "max_inter_group_corr": 0.300,
    "risk_groups": 21,
}

# ═══════════════════════════════════════════════════════════ đã bác bỏ
# Giữ lại CÓ CHỦ Ý: mỗi dòng là một hướng đã tốn công đo và đã có kết luận. Xoá đi
# thì lần sau sẽ có người thử lại chính nó. Đây là tài sản, không phải rác.
REJECTED_DIRECTIONS: Tuple[Dict[str, str], ...] = (
    {"name": "GapFade_va_HLRange", "tf": "M30/H1",
     "reason": "Hai họ mới của vòng 67 KHÔNG có ô nào lọt top: `gap_fade` (khoảng "
               "hở mở cửa so với đóng cửa trước, vào ngược) và `hl_range` (biên độ "
               "high-low quá rộng, vào ngược). `hl_range` là bản ĐẢO CHIỀU của "
               "`range_break` đã bị loại ở vòng 65 — cả hai chiều đều thua, nên "
               "kết luận là ĐẠI LƯỢNG biên độ nến vô dụng trên FX, không phải do "
               "chọn sai chiều. `gap_fade` thua vì trên FX khoảng hở trong phiên "
               "quá hiếm và quá nhỏ để bù chi phí.",
     "doc": "research/fx/m30_h1_hunt2.py"},
    {"name": "Accel_CADCHF_M30_va_GBPCAD_H1", "tf": "M30/H1",
     "reason": "Hai ô họ ACCEL qua 6/7 kiểm định nhưng TRƯỢT vùng tham số: 6/12 và "
               "7/12 ô lân cận dương, dưới ngưỡng 60%. Cùng họ, ô GBPNZD H1 đạt "
               "9/12 và được nhận. Vùng tham số là cổng phân biệt 'họ có tín "
               "hiệu' với 'ô may mắn trong họ có tín hiệu'.",
     "doc": "research/fx/hunt2_validate.py"},
    {"name": "RangeBreak_H1", "tf": "H1",
     "reason": "Họ MỞ RỘNG BIÊN ĐỘ (nến có biên độ > k lần trung bình, vào THUẬN "
               "chiều nến): chỉ **12,5%** ô trong lưới 384 ô cho Sharpe dương, "
               "net trung vị −1,82 bps/lệnh. Ba họ còn lại cùng vòng đều đạt "
               "45-53% ô dương. Kết luận khớp với 63 vòng trước: trên FX, hướng "
               "THUẬN chiều thua ở mọi khung — chỉ hồi quy sống được.",
     "doc": "research/fx/h1_families.py"},
    {"name": "ZBandGBPNZD_H1", "tf": "H1",
     "reason": "Vùng tham số ĐẸP NHẤT toàn bộ vòng 64 — 18/18 ô lân cận dương, "
               "Sharpe ALL 0,978, t = 3,34, qua cả hai control với p = 0,0000. "
               "Vẫn LOẠI vì FORM 1,493 so với OOS **−0,119**: toàn bộ lợi nhuận "
               "nằm ở giai đoạn hiệu chỉnh và biến mất ở giai đoạn kiểm chứng. "
               "Vùng tham số vững KHÔNG cứu được một ô có OOS âm — nó chỉ nói "
               "rằng cái sai được lặp lại nhất quán. Cùng công cụ ở H4 thì ĐẠT "
               "(ZBandGBPNZDH4, FORM 1,398 / OOS 0,879).",
     "doc": "research/fx/h1_validate.py"},
    {"name": "ZBandGBPCAD_H4_exit_at_mean_False", "tf": "H4",
     "reason": "GBPCAD H4 ra Sharpe 0,815 ở lab nhưng 0,557 ở động cơ sản xuất "
               "— lab không có nhánh thoát khi z về 0. Suýt cứu bằng tham số mới "
               "`exit_at_mean=False` (Sharpe lên 0,865), nhưng đo trên CẢ BẢY "
               "chân cho thấy nó chỉ tốt hơn ở **1/7**. Một tham số chỉ đúng đúng "
               "ô mình cần nó đúng là bậc tự do, không phải phát hiện. Tham số vẫn "
               "giữ trong `zband_core` KÈM bảng đo 7 chân, mặc định True, không "
               "chân nào dùng False. BÀI HỌC THÀNH QUY TẮC: kiểm định phải chạy "
               "trên cùng đường code với sản xuất; lab chỉ để quét rộng.",
     "doc": "research/fx/h4_validate.py"},
    {"name": "XsZscoreReversion_M30", "tf": "M30",
     "reason": "CÙNG luật với chân H4 đã nhận (`CrossXsReversion`) nhưng ở M30: "
               "Sharpe 0,410 · FORM 0,410 · OOS 0,417 — ổn định hơn cả bản H4 nhìn "
               "từ hai cửa sổ. Vẫn LOẠI vì hai kiểm định khác: bootstrap khối cho "
               "P(<0) = 11,5% (ngưỡng 10%), và bỏ 5 tháng tốt nhất thì ĐỔI DẤU "
               "(−0,49%) — 5 tháng đó chiếm 103,4% lợi nhuận. Bản H4 cùng luật chỉ "
               "89,8% và giữ dấu. Bài học: FORM/OOS đẹp KHÔNG thay được kiểm định đuôi.",
     "doc": "research/fx/xs_z_validate.py"},
    {"name": "CointegrationPairs_Majors", "tf": "M30/H1/H4",
     "reason": "Spread β-hedge (Engle-Granger) giữa 21 tổ hợp hai major, 3 khung = "
               "63 ô: **0/63 ô** có ADF trung vị < 0,05. Không có hai major nào "
               "cointegrate thật — chúng chung nhân tố USD nhưng chân còn lại là "
               "bước đi ngẫu nhiên độc lập. Ô 'tốt nhất' (NZDUSD~USDCAD H4, Sharpe "
               "0,604) có ADF 0,118 và chỉ 30 lệnh — nhiễu. Kết luận cấu trúc: chân "
               "H1 thắng vì cross là CÔNG CỤ GIAO DỊCH ĐƯỢC (một spread), không vì "
               "cointegration; β khớp phải trả HAI spread nên không bù nổi.",
     "doc": "research/fx/coint_lab.py"},
    {"name": "LeadLag_CrossPredictability", "tf": "H1",
     "reason": "Tự tương quan CHÉO giữa 20 cross: 124/380 ô ngoài đường chéo vượt "
               "ngưỡng t>2 (32,6%) — tín hiệu THẬT về mặt thống kê. Nhưng giao dịch "
               "được thì âm sâu: gross 0,16 bps/nến vs chi phí 1,57. Hồi quy đa biến "
               "trượt, 6 cấu hình, ALL từ −9,06 đến −9,95. Vòng quay 2.600-4.960/năm. "
               "Bài học: t-stat lớn trên IC 0,03 vẫn không đủ biên độ để bù một lượt "
               "khứ hồi.",
     "doc": "research/fx/leadlag_h1.py"},
    {"name": "FreqtradeConfluence_4Rules", "tf": "H1/M30",
     "reason": "Bốn luật hợp lưu lấy nguyên văn từ `project-refer/freqtrade-strategies` "
               "(HLHB của babypips — viết RIÊNG cho forex, Triple Supertrend, "
               "Bandtastic, TrendRider pullback) × 2 khung × 7 cặp = 56 ô: **0/56 ô** "
               "qua cổng FORM>0 & OOS>0 & ALL>0,4. Trung vị theo luật: hlhb H1 −0,122, "
               "triple_st H1 −0,834, trendrider H1 −0,527, bandtastic H1 +0,014. "
               "Giả thiết 'giao của N điều kiện yếu lọc ra tập con đủ mạnh' bị bác bỏ: "
               "số lệnh giảm đúng như dự đoán nhưng net/lệnh KHÔNG tăng. "
               "Ngoại lệ duy nhất đáng ghi: `bandtastic` (hồi quy trung bình CÓ cổng "
               "xu hướng) dương 4/7 cặp và net +5,06 bps/lệnh trên GBPUSD H1 — không "
               "đủ phổ quát để nhận, nhưng xác nhận hướng sống sót trên FX là MEAN "
               "REVERSION, không phải trend.",
     "doc": "research/fx/confluence_h1.py"},
    {"name": "PriceActionFamilies_XAU", "tf": "M30/H1/H4",
     "reason": "8 family của hệ XAUUSD trên FX: 28/33 NO_INFORMATION, "
               "MFE/|MAE| ≈ 1,00 (chữ ký bước đi ngẫu nhiên); 363 phép thử sinh 5 "
               "'phát hiện' — ÍT HƠN mức ngẫu nhiên",
     "doc": "docs/forex/00_ket_qua_vong_1.md"},
    {"name": "FixReversal", "tf": "H1",
     "reason": "Tín hiệu THẬT và đặc tả trước (Krohn JoF 2024; EURUSD h13 Frankfurt "
               "t = −3,83, vượt Bonferroni) nhưng độ lớn ≈ đúng 1 lượt khứ hồi. "
               "1/1104 luật qua DEV → OOS Sharpe −1,34; control p = 0,56; DSR = 0,0000",
     "doc": "docs/forex/02_kien_thuc_nen_internet.md"},
    {"name": "TrendMA_20_120", "tf": "D1",
     "reason": "Luật Olszweski & Zhou nguyên văn: chi phí chỉ ăn 0,5-7,4% lợi nhuận "
               "gộp (chi phí KHÔNG phải ràng buộc) nhưng tín hiệu âm — danh mục "
               "Sharpe −0,07, 2/7 năm dương; EURUSD qua 11 năm −0,13",
     "doc": "docs/forex/03_ket_qua_vong_2_champion.md"},
    {"name": "CrossSectionalMomentum", "tf": "D1",
     "reason": "Chiều NGƯỢC với reversal: OOS Sharpe −0,95. Menkhoff et al. tìm "
               "momentum ở 1-12 tháng; ở 21 ngày dấu đảo lại",
     "doc": "docs/forex/03_ket_qua_vong_2_champion.md"},
    {"name": "MonthEndFlow", "tf": "D1",
     "reason": "Ứng viên chân thứ hai: |t| lớn nhất chỉ 1,27; DEV Sharpe 0,07 vs "
               "OOS 0,53 — bất ổn. Tương quan thấp không cứu được một chân không có edge",
     "doc": "docs/forex/03_ket_qua_vong_2_champion.md"},
    {"name": "IntradayVolumeConditioned", "tf": "H1",
     "reason": "Giả thuyết Campbell-Grossman-Wang (khối lượng tách thanh khoản khỏi "
               "thông tin) BỊ BÁC BỎ trên FX H1: fade trên khối lượng THẤP cho ratio "
               "−0,079 còn khối lượng CAO +0,264 — NGƯỢC dự đoán; 0/7 cặp vượt chi phí",
     "doc": "research/fx/volume_scan.py"},
    {"name": "H1GridCrossSectional", "tf": "H1",
     "reason": "Cắt ngang trên lưới H1 (lb/hold 24-120 nến): reversal ô tốt nhất có "
               "DEV −0,238 / OOS +1,426 — bất ổn, MaxDD 15,2%. Momentum: MỌI ô âm "
               "(−0,54 đến −1,38) sau khi sửa lỗi look-ahead",
     "doc": "research/fx/h1_momentum_test.py"},
    {"name": "NewsOverreaction", "tf": "M30",
     "reason": "Edge THẬT (control p = 0,0000, phân vị 100%; nến tin dịch chuyển "
               "4-6x bình thường) NHƯNG không với tới được: vào muộn 1 nến làm t tụt "
               "1,64 → 0,47, tức edge nằm đúng ở nến spread rộng nhất. OOS t = 0,10-0,74, "
               "chết ở chi phí ×5, phụ thuộc nặng 2022",
     "doc": "src/python/strategies/m30/news_overreaction.py"},
    {"name": "SignalDispersionGate", "tf": "D1",
     "reason": "Thử cắt thời gian trong thị trường để giảm phí swap: mọi biến thể "
               "Sharpe 0,41-0,58, PBO giữ nguyên 0,686 — không cải thiện",
     "doc": "docs/forex/04_ket_qua_cuoi_cung.md"},
    {"name": "RegimeSwitch_RevToMom", "tf": "D1",
     "reason": "Đổi sang momentum khi khủng hoảng: DEV đẹp hơn (1,133) nhưng OOS sụt "
               "0,710, chênh lệch t = +0,98 — chữ ký overfit. Bản 'đứng ngoài' ổn định hơn",
     "doc": "docs/forex/03_ket_qua_vong_2_champion.md"},
    {"name": "InverseVolLegWeights", "tf": "danh mục",
     "reason": "Trọng số NGHỊCH ĐẢO BIẾN ĐỘNG thay `LEG_WEIGHTS` đều — chuẩn dùng "
               "chung của Moskowitz-Ooi-Pedersen (JFE 2012, σ đích 40%), AQR "
               "(Century of Evidence 2014, vol ex-ante 10%), Olszweski-Zhou (JDHF "
               "2014, MinVar hạ MaxDD 17,42% → 8,41%) và Levy-Lopes (DML, EWMA "
               "δ=0,97). Bốn nguồn độc lập, nên đo chứ không bàn. Kết quả trên đúng "
               "danh mục này: σ cuộn 20 ngày làm đuôi mỏng đi thật (ngày tệ nhất "
               "76,0 → 48,0 bps, skew −0,52 → −0,02) và nhờ đó được cấp thêm đòn "
               "bẩy, nhưng SHARPE THUA Ở CẢ 7/7 NĂM (toàn mẫu 2,430 → 1,644; 2020 "
               "2,00→1,29 · 2022 2,06→0,49 · 2024 1,01→0,10). Lợi thế 2026 (+16,95% "
               "ở trần 8,0x) chỉ là hệ quả của việc được nới trần, không phải lợi "
               "nhuận tốt hơn. Cửa sổ 60 ngày còn tệ hơn: đuôi DÀY LÊN 98,0 bps và "
               "4,9% cửa sổ 252 ngày CHẾT. Nguyên nhân: chân ZBand đã tự chuẩn hoá "
               "theo σ ngay trong z-score, và `LEG_WEIGHTS` đã gộp theo tương quan "
               "(ngưỡng 0,70) — chuẩn hoá lần nữa là dồn vốn sang chân σ thấp mà lợi "
               "nhuận cũng thấp. Đo tại `research/fx/invvol_weights.py` và "
               "`invvol_relever.py`; bài đầu có test chống nhìn trước và test đó ĐÃ "
               "BẮT một lỗi thật (sàn σ dùng phân vị TOÀN MẪU, lệch trọng số 5,48e-01) "
               "— phải sửa thành phân vị mở rộng rồi mới đọc được số.",
     "doc": "research/fx/invvol_weights.py"},
    {"name": "TimeStopAtHalfLife_Zheng432", "tf": "M30/H1/H4",
     "reason": "Neo time-stop vào NỬA ĐỜI hồi quy theo Zheng Nan (MSc 2025, §4.3.1): "
               "cửa sổ = thời hạn = 4,32 × HL, với 4,32 = ln(1/0,05)/ln2 = số lần nửa "
               "đời để OU phân rã 95% độ lệch. Zheng đo được +400% P&L và winrate "
               "73,3% → 78,2% khi thay cửa sổ cố định bằng cửa sổ neo HL. PHÁT HIỆN "
               "PHỤ ĐÁNG GIỮ LẠI: đo nửa đời 12 chân ZBand cho thấy CẢ 12 CỬA SỔ đã "
               "nằm ở 4,37–4,98 × HL — tức tham số tìm bằng quét lưới TRÙNG với con "
               "số suy từ lý thuyết OU, một xác nhận độc lập rằng `window_bars` đang "
               "đúng. Nhưng 5 chân có `timestop_mult` 2,0–3,0 nên giữ tới 8,8–14,9 lần "
               "nửa đời; ép mult về 1,0 cho cả 12 để khớp luật thì đo trên đường live "
               "2026 (parity.replay_leg, 22 chân, 673 lệnh) cho: lãi −0,18 điểm %, "
               "MaxDD không đổi, và nhánh TIME_STOP TỆ ĐI (−$9.992 → −$11.924, winrate "
               "35,4% → 31,7%). Từng chân: 2 tốt hơn (EURCHF +$71, EURGBP +$12) · 3 tệ "
               "hơn (AUDCAD-H4 −$136, GBPUSD −$126, GBPAUD-H4 −$72). 2/5 không đủ — "
               "cùng ngưỡng đã loại `exit_at_mean=False` ở 1/7 chân. Hai bài phản chứng "
               "cùng hướng: nới ×1,5 và ×2,0 cũng làm lãi GIẢM. Kết luận: 113 lệnh "
               "TIME_STOP thua KHÔNG phải vì thời hạn sai, mà vì chúng là những lần hồi "
               "quy thật sự không xảy ra — thời hạn nào cũng không cứu được.",
     "doc": "research/fx/timestop_halflife_rule.py"},
    {"name": "ZBandEntryOnReentry_Zheng", "tf": "M30/H1/H4",
     "reason": "Vào lệnh khi z QUAY LẠI vào dải thay vì khi còn NGOÀI dải — luật của "
               "Zheng Nan (MSc 2025, §4.3.1): không vào lúc giá vừa xuyên RA, chỉ vào "
               "khi giá trở lại trong dải, vì xuyên ra mới chứng minh CÓ lệch chứ chưa "
               "chứng minh lệch sắp đóng. Giả thuyết trước khi đo: winrate TĂNG (đã có "
               "bằng chứng hồi quy khởi động), R:R giảm, số lệnh giảm. ĐO TRÊN ĐƯỜNG "
               "LIVE 2026 (parity.replay_leg): winrate **GIẢM 66,1% → 47,7%** — ngược "
               "hẳn giả thuyết — lãi −$5.752, số lệnh TĂNG 673 → 1.157. Từng chân: 2 "
               "tốt hơn, 10 tệ hơn. NGUYÊN NHÂN: vào khi z đã về trong dải là vào GẦN "
               "TRUNG BÌNH, chỗ phần hồi quy còn lại rất ngắn; mục tiêu thoát (z qua 0) "
               "nằm sát điểm vào nên chi phí ăn hết biên, và điều kiện 'quay lại' xảy "
               "ra thường xuyên hơn nhiều so với 'hai nến liên tiếp ngoài dải' nên sinh "
               "gấp rưỡi số lệnh mỏng. Bài học: BIÊN NẰM Ở CHỖ LỆCH SÂU, không ở chỗ "
               "lệch đã đóng một phần. Hai số ĐI ĐÚNG hướng dự đoán mà vẫn không cứu "
               "được: R:R 0,72 → 1,28 và nhánh TIME_STOP −$9.992 → −$2.253 (winrate "
               "35,4% → 49,4%) — tức luật này THẬT SỰ loại được nhóm lệnh xấu, nhưng "
               "cái nó loại kèm theo là toàn bộ phần lãi. Tham số `entry_mode` GIỮ LẠI "
               "trong `zband_core.ZBandConfig` kèm bảng đo, mặc định 'outside', không "
               "chân nào dùng 'reenter' — cùng cách xử lý `exit_at_mean`.",
     "doc": "research/fx/entry_mode_reenter.py"},
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
              f"  chân: {', '.join(p['legs'])} — chia đều, chuẩn hoá cùng biến động",
              f"  trần đòn bẩy {p['leverage_cap']}x",
              f"  Sharpe ALL {p['sharpe_all']:.3f} · FORM {p['sharpe_form']:.3f} "
              f"· OOS {p['sharpe_oos']:.3f} · {p['years_positive']} năm dương",
              "", f"ĐÃ BÁC BỎ: {len(REJECTED_DIRECTIONS)} hướng "
              f"({', '.join(r['name'] for r in REJECTED_DIRECTIONS)})"]
    return "\n".join(lines)
