"""cross_momentum.py — CrossMomentum

20 cặp: EURGBP, EURAUD, EURNZD… · D1 · BOTH · Cross-Sectional Momentum trên cross tổng
hợp

┌─ QUY TẮC VÀO LỆNH ────────────────────────────────────────────────────────────┐
│  VÀO   (xếp hạng cắt ngang)                                                   │
│     a. hôm nay là nến tái cân bằng (mỗi 21 nến D1)                            │
│     b. MUA 5 cross có momentum CAO nhất trong 20 cross                        │
│     c. BÁN 5 cross có momentum THẤP nhất                                      │
│     d. tỷ trọng trong mỗi chân ∝ 1/σ, chuẩn hoá tổng = 5                      │
│     → khớp thị trường trên từng chân của cross tổng hợp                       │
│     giờ CẤM (UTC): 20, 21, 22, 23                                             │
│                                                                               │
│  THOÁT                                                                        │
│     · tái cân bằng kế tiếp sau 21 nến D1                                      │
│                                                                               │
│  CẮT LỖ  KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop       │
│  VỊ THẾ  tối đa 10                                                            │
└───────────────────────────────────────────────────────────────────────────────┘

KẾT QUẢ   Sharpe 0,897 ALL · 0,920 OOS
TẦN SUẤT  tái cân bằng mỗi 21 nến D1 ≈ 12 lần/năm · giữ 21 ngày giao dịch
CHỈ BÁO   tín hiệu = lợi nhuận log tích luỹ 63 nến D1 của từng cross · σ(189 nến) để
          chia tỷ trọng inverse-vol
PHÂN LOẠI CỔ ĐIỂN HỌC THUẬT — luật lấy NGUYÊN VĂN từ Moskowitz, Ooi & Pedersen 2012

NGUỒN
  · Moskowitz, Ooi & Pedersen (2012) "Time Series Momentum", J. Financial Economics
    104(2)
    D:/project-learning/documents/forex-strategies/Time_series_momentum.pdf
  · Menkhoff, Sarno, Schmeling & Schrimpf (2011) "Currency Momentum Strategies", BIS
    Working Paper 366
    D:/project-learning/documents/forex-strategies/work366.pdf

Số liệu SAU ĐỦ CHI PHÍ (spread đo thật trên MT5 14/08/2026 ×1,5 + commission + swap +
biên broker 1,0%/năm). OOS từ 2024-01-01 chưa từng dùng để chọn gì. Spread là của tài
khoản DEMO — đo lại bằng `scripts/measure_broker_costs.py` trước khi cấp vốn.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.python.research import fx_cross_lab as LAB
from src.python.strategies import rulebook as RB
from src.python.research import fx_cross_pairs as _CP

# Tham số — nằm trong dải mà TSMOM/Menkhoff đo là có edge. Không tinh chỉnh.
LOOKBACK_BARS = 63          # 3 tháng
REBALANCE_BARS = 21         # 1 tháng
N_LEG = 5                   # 5 long / 5 short trên 20 cross
TIMEFRAME = "D1"


@dataclass(frozen=True)
class Config:
    lookback_bars: int = LOOKBACK_BARS
    rebalance_bars: int = REBALANCE_BARS
    n_leg: int = N_LEG
    broker_markup_pct: float = 1.0


def backtest(cfg: Config = Config(), start: str = "2020-01-01") -> LAB.SimResult:
    panel = LAB.build_panel(TIMEFRAME, start=start,
                            broker_markup_pct=cfg.broker_markup_pct)
    pos = LAB.sig_xs_reversal(panel, sign=+1, n_leg=cfg.n_leg,
                              lookback=cfg.lookback_bars,
                              rebalance_bars=cfg.rebalance_bars)
    return LAB.simulate_positions(panel, pos, name="cross_momentum")


def daily_pnl(cfg: Config = Config(), start: str = "2020-01-01") -> pd.Series:
    return backtest(cfg, start).pnl_daily


def live_targets(cfg: Config = Config(), start: str = "2020-01-01") -> pd.Series:
    """Tỷ trọng mục tiêu trên từng cross cho phiên hiện tại (hàng cuối)."""
    return backtest(cfg, start).positions.iloc[-1].round(4)


def explain_decisions(cfg: Config = Config(), start: str = "2020-01-01") -> list:
    """Bản ghi quy tắc cho chân momentum cắt ngang trên cross.

    Tín hiệu = lợi nhuận log tích luỹ `lookback_bars` nến trước. Ghi cả 20 cross kể
    cả cross KHÔNG được chọn, vì câu hỏi "vì sao EURGBP hôm nay không có vị thế" chỉ
    trả lời được nếu có dòng của EURGBP kèm thứ hạng của nó.
    """
    from src.python.execution import rule_trace as RT
    from src.python.research import fx_cross_lab as LAB

    panel = LAB.build_panel(TIMEFRAME, start=start,
                            broker_markup_pct=cfg.broker_markup_pct)
    cum = panel.logp.cumsum()
    signal = cum - cum.shift(cfg.lookback_bars)
    vol = panel.logp.diff().rolling(max(cfg.lookback_bars * 3, 60),
                                    min_periods=30).std()
    W = backtest(cfg, start).positions

    # TÍN HIỆU LẤY TẠI NẾN TÁI CÂN BẰNG GẦN NHẤT, không phải nến hiện tại. Vị thế
    # được GIỮ giữa hai lần tái cân bằng nên tín hiệu hôm nay đã trôi khỏi tín hiệu
    # lúc ra quyết định; ghép hai cái đó tạo bản ghi TỰ MÂU THUẪN ("hạng 12 — top 5").
    # Lệch thêm một nến (`j - 1`) vì `sig_xs_reversal` đọc `mom.iloc[i-1]`.
    n = len(panel.logp)
    since = int((n - 1) % cfg.rebalance_bars)
    j = max((n - 1) - since - 1, 0)
    return RT.traces_from_ranking(
        timestamp=panel.logp.index[-1], strategy="CrossMomentum",
        signal_name=f"momentum_{cfg.lookback_bars}d",
        signal=signal.iloc[j], weights=W.iloc[-1], n_leg=cfg.n_leg,
        vol=vol.iloc[j], cost_bps=panel.cost_1rt_bps,
        bars_since=since, bars_next=cfg.rebalance_bars - since)


# Rổ 20 cross tổng hợp — lấy từ SSOT `research/fx_cross_pairs.CROSS_DEFS` thay vì
# viết lại, để không có hai danh sách trôi khỏi nhau.
_CROSS_UNIVERSE = tuple(d[0] for d in _CP.CROSS_DEFS)

# ══ NGUỒN GỐC — mỗi dòng một bài, kèm đường dẫn mở được
SOURCES = (
    "Moskowitz, Ooi & Pedersen (2012) \"Time Series Momentum\", J. Financial Economics "
    "104(2) — D:/project-learning/documents/forex-strategies/Time_series_momentum.pdf",
    "Menkhoff, Sarno, Schmeling & Schrimpf (2011) \"Currency Momentum Strategies\", BIS "
    "Working Paper 366 — D:/project-learning/documents/forex-strategies/work366.pdf",
)

# ══ THẺ LUẬT — dữ liệu cho GUI và tests/test_rulebook.py.
# ══ Bản người đọc là khối QUY TẮC VÀO LỆNH ở ĐẦU FILE, sinh ra từ đây.
RULEBOOK = RB.RuleBook(
    name="CrossMomentum",
    signal_tf="D1", execution_tf="H1", direction="BOTH",
    universe=_CROSS_UNIVERSE,
    max_positions=2 * N_LEG,
    family="Cross-Sectional Momentum trên cross tổng hợp",
    source=" · ".join(SOURCES),
    hours_utc="mọi giờ",
    forbidden_hours_utc=(20, 21, 22, 23),
    indicators=(
        f"tín hiệu = lợi nhuận log tích luỹ {LOOKBACK_BARS} nến D1 của từng cross",
        f"σ({max(LOOKBACK_BARS * 3, 60)} nến) để chia tỷ trọng inverse-vol",
    ),
    entry_logic="RANK",
    entry_rules=(
        RB.Rule("a", f"hôm nay là nến tái cân bằng (mỗi {REBALANCE_BARS} nến D1)"),
        RB.Rule("b", f"MUA {N_LEG} cross có momentum CAO nhất trong 20 cross",
                "momentum bền ở thang 1-12 tháng (TSMOM), đảo chiều ở thang dài hơn"),
        RB.Rule("c", f"BÁN {N_LEG} cross có momentum THẤP nhất"),
        RB.Rule("d", f"tỷ trọng trong mỗi chân ∝ 1/σ, chuẩn hoá tổng = {N_LEG}"),
    ),
    entry_price="khớp thị trường trên từng chân của cross tổng hợp",
    exit_rules=(
        RB.Rule("x1", f"tái cân bằng kế tiếp sau {REBALANCE_BARS} nến D1"),
    ),
    stop_loss="KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop",
    take_profit="không có — thoát theo tín hiệu hoặc time-stop",
    blocks=(
        "giờ CẤM UTC 20-23 — spread rộng nhất",
        "chi phí cross đã ĐO THẬT trên MT5 ngày 14/08/2026, nhân hệ số an toàn 1,5",
    ),
    frequency=f"tái cân bằng mỗi {REBALANCE_BARS} nến D1 ≈ 12 lần/năm",
    avg_holding=f"{REBALANCE_BARS} ngày giao dịch",
    expectancy="Sharpe 0,897 ALL · 0,920 OOS",
    trace_signal_name=f"momentum_{LOOKBACK_BARS}d",
)
