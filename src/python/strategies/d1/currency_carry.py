"""currency_carry.py — CurrencyCarry

7 cặp: EURUSD, GBPUSD, USDJPY… · D1 · BOTH · Cross-Sectional Currency Carry

┌─ QUY TẮC VÀO LỆNH ────────────────────────────────────────────────────────────┐
│  VÀO   (xếp hạng cắt ngang)                                                   │
│     a. hôm nay là ngày tái cân bằng (mỗi 21 ngày)                             │
│     b. MUA 3 đồng có lãi suất CAO nhất so với rổ                              │
│     c. BÁN 3 đồng có lãi suất THẤP nhất so với rổ                             │
│     d. tỷ trọng ∝ 1/σ(63), tổng mỗi chân = 1                                  │
│     e. cổng chế độ CALM: biến động rổ < phân vị 80% trượt 252 ngày            │
│     → gộp với chân reversal qua combined() rồi mới quy sang tỷ trọng cặp — gộp│
│       TRƯỚC khi tính phí tiết kiệm đo được +0,595%/năm                        │
│     giờ CẤM (UTC): 20, 21, 22, 23                                             │
│                                                                               │
│  THOÁT                                                                        │
│     · tái cân bằng kế tiếp sau 21 ngày                                       │
│     · cổng chế độ chuyển CRISIS → về 0                                        │
│                                                                               │
│  CẮT LỖ  KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop       │
│  VỊ THẾ  tối đa 6                                                             │
└───────────────────────────────────────────────────────────────────────────────┘

KẾT QUẢ   Sharpe 0,151 ALL · 0,745 OOS · MaxDD 10,37%. Giá trị thật là làm CHÂN ĐỐI
          TRỌNG: tương quan −0,059 với reversal, và nó NHẬN swap (−1,716%/năm) trong khi
          reversal TRẢ
TẦN SUẤT  tái cân bằng mỗi 21 ngày ≈ 12 lần/năm · giữ 21 ngày giao dịch
CHỈ BÁO   lãi suất chính sách của 8 đồng, dạng BẬC THANG theo ngày họp (không nội suy) ·
          tín hiệu = lãi suất đồng − trung bình rổ, đơn vị %/năm · σ(63 ngày) — chỉ để
          chia tỷ trọng
PHÂN LOẠI CỔ ĐIỂN HỌC THUẬT — luật 3 cao / 3 thấp lấy NGUYÊN VĂN từ Olszweski & Zhou
          2014

NGUỒN
  · Olszweski & Zhou (2014) "Strategy diversification: Combining momentum and carry
    strategies within a foreign exchange portfolio", J. Deriv. & Hedge Funds 19(4)
    D:/project-learning/documents/forex-strategies/jdhf.2013.16.pdf
  · Brière & Drut (2009, sửa 2010) "The Revenge of Fundamentals on Carry Trades during
    Crises", Amundi WP-005-2009
    D:/project-learning/documents/forex-strategies/Working Paper July 2009 - the revenge
    of fundamentals on carry trades during crises.pdf
  · Burnside, Eichenbaum & Rebelo (2011) "Carry Trade and Momentum in Currency Markets",
    NBER WP 16942
    D:/project-learning/documents/forex-strategies/w16942.pdf

Số liệu SAU ĐỦ CHI PHÍ (spread đo thật trên MT5 14/08/2026 ×1,5 + commission + swap +
biên broker 1,0%/năm). OOS từ 2024-01-01 chưa từng dùng để chọn gì. Spread là của tài
khoản DEMO — đo lại bằng `scripts/measure_broker_costs.py` trước khi cấp vốn.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.python.shared import asset_profile as AP
from src.python.shared import carry_costs as CC
from src.python.strategies.d1 import currency_reversal as CR
from src.python.strategies import rulebook as RB

# ═════════════════════════════════════════════════════════ tham số (SSOT)
REBALANCE_DAYS = 21
N_LEG = 3                   # Olszweski & Zhou: 3 cao / 3 thấp
VOL_WINDOW = 63


@dataclass(frozen=True)
class Config:
    rebalance_days: int = REBALANCE_DAYS
    n_leg: int = N_LEG
    vol_window: int = VOL_WINDOW
    regime_gate: bool = True


# ═════════════════════════════════════════════════════════ tín hiệu
def carry_signal(F: pd.DataFrame) -> pd.DataFrame:
    """Tín hiệu carry = lãi suất chính sách, chuẩn hoá trừ trung bình cắt ngang.

    Trừ trung bình để tín hiệu là TƯƠNG ĐỐI: khi cả thế giới cùng tăng lãi (2022-2023)
    thì không đồng nào "lãi cao" hơn theo nghĩa carry — chỉ chênh lệch mới sinh carry.
    """
    R = CC.rate_series(F.index, list(F.columns))
    return R.sub(R.mean(axis=1), axis=0)


def target_weights(F: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    """Tỷ trọng mục tiêu theo đồng tiền. Cùng cấu trúc `currency_reversal` để hai
    chân ghép được ở tầng danh mục mà không cần lớp chuyển đổi nào."""
    signal = carry_signal(F)
    vol = F.rolling(cfg.vol_window, min_periods=cfg.vol_window // 2).std()
    crisis = (CR.regime_is_crisis(F, CR.Config()) if cfg.regime_gate
              else pd.Series(False, index=F.index))

    W = pd.DataFrame(0.0, index=F.index, columns=F.columns)
    held = pd.Series(0.0, index=F.columns)
    need = 2 * cfg.n_leg
    for i, t in enumerate(F.index):
        if i % cfg.rebalance_days == 0 and i > 0:
            s, v = signal.iloc[i - 1], vol.iloc[i - 1]
            if s.notna().sum() >= need and v.notna().sum() >= need:
                order = s.dropna().sort_values(ascending=False)
                w = pd.Series(0.0, index=F.columns)
                for grp, sgn in ((list(order.index[:cfg.n_leg]), +1.0),
                                 (list(order.index[-cfg.n_leg:]), -1.0)):
                    iv = (1.0 / v[grp].replace(0, np.nan)).fillna(0.0)
                    if iv.sum() > 0:
                        w[grp] = sgn * iv / iv.sum()
                held = w
        W.loc[t] = 0.0 if crisis.iloc[i] else held
    return W


# ═════════════════════════════════════════════════════════ backtest
def backtest(start: str = "2020-01-01", cfg: Config = Config(), *,
             broker_markup_pct: float = CC.DEFAULT_BROKER_MARKUP_PCT
             ) -> CR.BacktestResult:
    """Backtest đủ chi phí. Với carry, thành phần `rate_diff_bps` thường ÂM
    (= thu nhập) — đó là toàn bộ lý do chân này tồn tại."""
    F, costs = CR.currency_returns(start=start)
    W = target_weights(F, cfg)
    P = CR.pair_weights(W)
    gross = (W * F).sum(axis=1)
    turnover = P.diff().abs().fillna(P.abs())
    trade_cost = (turnover * costs.reindex(P.columns)).sum(axis=1) / 2.0
    specs = {s: (AP.get(s).base, AP.get(s).quote) for s in P.columns}
    carry = CC.pair_carry_bps(P, specs, broker_markup_pct=broker_markup_pct)
    total_cost = trade_cost + carry["total_carry_bps"]
    return CR.BacktestResult(net=(gross - total_cost).dropna(), gross=gross,
                             cost=total_cost, trade_cost=trade_cost,
                             carry_cost=carry["total_carry_bps"],
                             weights_ccy=W, weights_pair=P)


# ═════════════════════════════════════════════════════════ danh mục hai chân
def explain_decisions(start: str = "2020-01-01", cfg: Config = Config()) -> List:
    """Ban ghi quy tac cho chan carry — tin hieu la chenh lech lai suat da chuan hoa."""
    from src.python.execution import rule_trace as RT

    F, _ = CR.currency_returns(start=start)
    signal = carry_signal(F)
    vol = F.rolling(cfg.vol_window, min_periods=cfg.vol_window // 2).std()
    crisis = (CR.regime_is_crisis(F, CR.Config()) if cfg.regime_gate
              else pd.Series(False, index=F.index))
    W = target_weights(F, cfg)

    n = len(F)
    since = int((n - 1) % cfg.rebalance_days)
    # TÍN HIỆU LẤY TẠI NẾN TÁI CÂN BẰNG GẦN NHẤT, không phải nến hiện tại. Vị thế
    # được GIỮ giữa hai lần tái cân bằng nên tín hiệu hôm nay đã trôi khỏi tín hiệu
    # lúc ra quyết định; ghép hai cái đó sinh bản ghi TỰ MÂU THUẪN ("hạng 5/8 —
    # thuộc top 3"). Lệch thêm một ngày vì `target_weights` đọc `signal.iloc[i-1]`.
    j = max((n - 1) - since - 1, 0)
    return RT.traces_from_ranking(
        timestamp=F.index[-1], strategy="CurrencyCarry",
        signal_name="rate_diff_vs_basket_pct",
        signal=signal.iloc[j], weights=W.iloc[-1], n_leg=cfg.n_leg,
        regime="CRISIS" if bool(crisis.iloc[-1]) else "CALM",
        regime_blocking=bool(crisis.iloc[-1]),
        vol=vol.iloc[j], bars_since=since,
        bars_next=cfg.rebalance_days - since)


def combined(start: str = "2020-01-01", *,
             weight_reversal: float = 0.5,
             broker_markup_pct: float = CC.DEFAULT_BROKER_MARKUP_PCT
             ) -> Tuple[pd.Series, Dict[str, pd.Series], pd.DataFrame]:
    """Danh mục CHIA ĐỀU hai chân, gộp vị thế TRƯỚC khi tính chi phí.

    Điểm mấu chốt — và là lý do hàm này không chỉ là phép cộng hai chuỗi lợi nhuận:
    hai chân thường yêu cầu vị thế NGƯỢC nhau trên cùng một cặp (reversal short đồng
    mạnh, carry long đồng lãi cao, mà đồng mạnh thường là đồng lãi cao). Gộp tỷ trọng
    trước rồi mới tính chi phí sẽ tự động **triệt tiêu phần chồng lấn**, cắt cả phí
    giao dịch lẫn phí swap. Cộng hai chuỗi lợi nhuận ròng đã tính chi phí riêng sẽ
    tính DƯ chi phí và đánh giá thấp danh mục.

    Đây chính là Currency Exposure Engine hoạt động ở tầng liên-chiến-lược.
    """
    F, costs = CR.currency_returns(start=start)
    w_rev = CR.target_weights(F, CR.Config())
    w_car = target_weights(F, Config())

    a = float(np.clip(weight_reversal, 0.0, 1.0))
    W = a * w_rev + (1.0 - a) * w_car
    P = CR.pair_weights(W)

    gross = (W * F).sum(axis=1)
    turnover = P.diff().abs().fillna(P.abs())
    trade_cost = (turnover * costs.reindex(P.columns)).sum(axis=1) / 2.0
    specs = {s: (AP.get(s).base, AP.get(s).quote) for s in P.columns}
    carry = CC.pair_carry_bps(P, specs, broker_markup_pct=broker_markup_pct)
    net = (gross - trade_cost - carry["total_carry_bps"]).dropna()

    parts = {
        "gross_bps": gross,
        "trade_cost_bps": trade_cost,
        "carry_cost_bps": carry["total_carry_bps"],
        "rate_diff_bps": carry["rate_diff_bps"],
        "gross_exposure": carry["gross_exposure"],
    }
    return net, parts, W


def live_targets(start: str = "2020-01-01", *, weight_reversal: float = 0.5):
    """Vị thế mục tiêu của DANH MỤC hai chân cho phiên hiện tại."""
    _, _, W = combined(start=start, weight_reversal=weight_reversal)
    P = CR.pair_weights(W)
    last = P.iloc[-1]
    F, _ = CR.currency_returns(start=start)
    crisis = bool(CR.regime_is_crisis(F, CR.Config()).iloc[-1])
    ctx = {
        "asof": str(W.index[-1].date()),
        "regime": "CRISIS (đứng ngoài)" if crisis else "CALM (giao dịch)",
        "weight_reversal": weight_reversal,
        "ccy_weights": W.iloc[-1].round(4).to_dict(),
        "execution_hour_utc": CR.EXECUTION_HOUR_UTC,
    }
    out = [CR.TargetPosition(sym, round(float(w), 4),
                             "FLAT" if abs(w) < 1e-6 else ("BUY" if w > 0 else "SELL"))
           for sym, w in last.items()]
    return out, ctx


# ══ NGUỒN GỐC — mỗi dòng một bài, kèm đường dẫn mở được
SOURCES = (
    "Olszweski & Zhou (2014) \"Strategy diversification: Combining momentum and carry "
    "strategies within a foreign exchange portfolio\", J. Deriv. & Hedge Funds 19(4) — "
    "D:/project-learning/documents/forex-strategies/jdhf.2013.16.pdf",
    "Brière & Drut (2009, sửa 2010) \"The Revenge of Fundamentals on Carry Trades "
    "during Crises\", Amundi WP-005-2009 — "
    "D:/project-learning/documents/forex-strategies/Working Paper July 2009 - the "
    "revenge of fundamentals on carry trades during crises.pdf",
    "Burnside, Eichenbaum & Rebelo (2011) \"Carry Trade and Momentum in Currency "
    "Markets\", NBER WP 16942 — "
    "D:/project-learning/documents/forex-strategies/w16942.pdf",
)

# ══ THẺ LUẬT — dữ liệu cho GUI và tests/test_rulebook.py.
# ══ Bản người đọc là khối QUY TẮC VÀO LỆNH ở ĐẦU FILE, sinh ra từ đây.
RULEBOOK = RB.RuleBook(
    name="CurrencyCarry",
    signal_tf="D1", execution_tf="H1", direction="BOTH",
    universe=("EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "USD"),
    traded=("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"),
    max_positions=2 * N_LEG,
    family="Cross-Sectional Currency Carry",
    source=" · ".join(SOURCES),
    hours_utc="mọi giờ",
    forbidden_hours_utc=CR.FORBIDDEN_HOURS_UTC,
    indicators=(
        "lãi suất chính sách của 8 đồng, dạng BẬC THANG theo ngày họp (không nội suy)",
        "tín hiệu = lãi suất đồng − trung bình rổ, đơn vị %/năm",
        f"σ({VOL_WINDOW} ngày) — chỉ để chia tỷ trọng",
    ),
    entry_logic="RANK",
    entry_rules=(
        RB.Rule("a", f"hôm nay là ngày tái cân bằng (mỗi {REBALANCE_DAYS} ngày)"),
        RB.Rule("b", f"MUA {N_LEG} đồng có lãi suất CAO nhất so với rổ",
                "đồng lãi cao được bù đắp cho rủi ro sụp; phần bù hiện ra khi bình lặng"),
        RB.Rule("c", f"BÁN {N_LEG} đồng có lãi suất THẤP nhất so với rổ"),
        RB.Rule("d", f"tỷ trọng ∝ 1/σ({VOL_WINDOW}), tổng mỗi chân = 1"),
        RB.Rule("e", f"cổng chế độ CALM: biến động rổ < phân vị "
                     f"{CR.REGIME_QUANTILE:.0%} trượt {CR.REGIME_WINDOW} ngày",
                "dùng CHUNG ngưỡng với chân reversal — hai chân phải cùng đứng ngoài "
                "trong crisis, nếu không thì combined() gộp một chân đang tắt với "
                "một chân đang chạy và tỷ trọng ròng mất ý nghĩa"),
    ),
    entry_price="gộp với chân reversal qua combined() rồi mới quy sang tỷ trọng cặp — "
                "gộp TRƯỚC khi tính phí tiết kiệm đo được +0,595%/năm",
    exit_rules=(
        RB.Rule("x1", f"tái cân bằng kế tiếp sau {REBALANCE_DAYS} ngày"),
        RB.Rule("x2", "cổng chế độ chuyển CRISIS → về 0"),
    ),
    stop_loss="KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop",
    take_profit="không có — thoát theo tín hiệu hoặc time-stop",
    blocks=(
        "cổng chế độ CRISIS → đứng ngoài",
        "KHÔNG chạy chân này một mình: đơn lẻ DEV −0,114 / OOS +0,745, quá bất ổn",
    ),
    frequency=f"tái cân bằng mỗi {REBALANCE_DAYS} ngày ≈ 12 lần/năm",
    avg_holding=f"{REBALANCE_DAYS} ngày giao dịch",
    expectancy="Sharpe 0,151 ALL · 0,745 OOS · MaxDD 10,37%. Giá trị thật là làm CHÂN "
               "ĐỐI TRỌNG: tương quan −0,059 với reversal, và nó NHẬN swap "
               "(−1,716%/năm) trong khi reversal TRẢ",
    trace_signal_name="rate_diff_vs_basket_pct",
)
