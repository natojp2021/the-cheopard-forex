"""cross_xs_reversion.py — CrossXsReversion

20 cặp: EURGBP, EURAUD, EURNZD… · H4 · BOTH · Cross-Sectional Z-Score Reversion trên
cross tổng hợp

┌─ QUY TẮC VÀO LỆNH ────────────────────────────────────────────────────────────┐
│  VÀO   (xếp hạng cắt ngang)                                                   │
│     a. nến này là nến tái cân bằng (mỗi 12 nến H4 = 2 ngày giao dịch)          │
│     b. MUA 7 cross có z THẤP nhất trong 20 cross                              │
│     c. BÁN 7 cross có z CAO nhất                                              │
│     d. tỷ trọng chia đều 1/7 mỗi chân — KHÔNG tối ưu hoá                      │
│     → khớp thị trường trên hai chân của cross tổng hợp                        │
│                                                                               │
│  THOÁT                                                                        │
│     · tái cân bằng kế tiếp sau 12 nến H4                                      │
│                                                                               │
│  CẮT LỖ  KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop       │
│  VỊ THẾ  tối đa 14                                                            │
└───────────────────────────────────────────────────────────────────────────────┘

KẾT QUẢ   Sharpe 0,460 ALL · 0,505 FORM · 0,381 OOS · MaxDD 7,75% · +2,40%/năm. Control
          p = 0,0000 · bootstrap P(<0) = 7,9%
TẦN SUẤT  tái cân bằng mỗi 2 ngày ≈ 126 lần/năm · vòng quay 13,3/năm · giữ 2 ngày giao
          dịch
CHỈ BÁO   z(cross) = (logp − trung bình 30 nến) / σ(30 nến), cửa sổ KẾT THÚC ở nến trước
          (.shift(1))
PHÂN LOẠI CỔ ĐIỂN (Lo & MacKinlay 1990) — bản GIẢN LƯỢC của mô hình Avellaneda & Lee
          2010: xếp hạng z thô thay phần dư PCA

NGUỒN
  · Lo & MacKinlay (1990) "When Are Contrarian Profits Due to Stock Market
    Overreaction?", Review of Financial Studies 3(2)
    KHÔNG có bản gốc trong kho, trích gián tiếp qua
    D:/project-learning/documents/forex-strategies/2607.19497v1.md
  · Avellaneda & Lee (2010) "Statistical Arbitrage in the U.S. Equities Market",
    Quantitative Finance 10(7)
    KHÔNG có bản gốc trong kho, trích gián tiếp qua
    D:/project-learning/documents/forex-strategies/57231515_202509.md
  · Olszweski & Zhou (2014) "Strategy diversification: Combining momentum and carry
    strategies within a foreign exchange portfolio", J. Deriv. & Hedge Funds 19(4)
    D:/project-learning/documents/forex-strategies/jdhf.2013.16.pdf

Số liệu SAU ĐỦ CHI PHÍ (spread đo thật trên MT5 14/08/2026 ×1,5 + commission + swap +
biên broker 1,0%/năm). OOS từ 2024-01-01 chưa từng dùng để chọn gì. Spread là của tài
khoản DEMO — đo lại bằng `scripts/measure_broker_costs.py` trước khi cấp vốn.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.python.research import fx_cross_lab as LAB
from src.python.strategies import rulebook as RB
from src.python.research import fx_cross_pairs as _CP

TIMEFRAME = "H4"
FORM_END = pd.Timestamp("2024-01-01")

# ═══════════════════════════════════════════════════════ tham số — đo, không đoán
BARS_PER_DAY = 6                 # H4: 24h / 4h = 6 nến mỗi ngày giao dịch
WINDOW_DAYS = 5                  # cửa sổ tính z
N_LEG = 7                        # số cross mỗi chân (mua 7 / bán 7 trên rổ 20)
REBALANCE_DAYS = 2               # giãn cách tái cân bằng

WINDOW_BARS = WINDOW_DAYS * BARS_PER_DAY          # 30
REBALANCE_BARS = REBALANCE_DAYS * BARS_PER_DAY    # 12


@dataclass(frozen=True)
class Config:
    window_bars: int = WINDOW_BARS
    n_leg: int = N_LEG
    rebalance_bars: int = REBALANCE_BARS
    broker_markup_pct: float = 1.0


# ═══════════════════════════════════════════════════════ tín hiệu
def zscore(logp: pd.DataFrame, window: int) -> pd.DataFrame:
    """z-score của log giá trên cửa sổ trượt, ĐÃ dịch một nến.

    `.shift(1)` ở cuối là điều làm chuỗi này chạy được live: giá trị tại nến t chỉ
    chứa thông tin đến hết nến t−1.
    """
    mu = logp.rolling(window, min_periods=window // 2).mean()
    sd = logp.rolling(window, min_periods=window // 2).std(ddof=1)
    return ((logp - mu) / sd.replace(0, np.nan)).shift(1)


def target_weights(logp: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    """Tỷ trọng mục tiêu từng cross theo thời gian.

    Giữ nguyên vị thế giữa hai lần tái cân bằng — đây là thứ giữ chi phí ở 42% gross
    thay vì 60%.
    """
    z = zscore(logp, cfg.window_bars)
    Zv = z.to_numpy()
    n, m = Zv.shape
    pos = np.zeros((n, m))
    cur = np.zeros(m)
    for i in range(cfg.window_bars, n):
        if i % cfg.rebalance_bars == 0:
            row = Zv[i]
            ok = np.isfinite(row)
            cur = np.zeros(m)
            if ok.sum() >= 2 * cfg.n_leg:
                idx = np.where(ok)[0]
                order = idx[np.argsort(row[idx])]
                cur[order[:cfg.n_leg]] = +1.0 / cfg.n_leg   # z thấp nhất → MUA
                cur[order[-cfg.n_leg:]] = -1.0 / cfg.n_leg  # z cao nhất  → BÁN
        pos[i] = cur
    return pd.DataFrame(pos, index=logp.index, columns=logp.columns)


# ═══════════════════════════════════════════════════════ backtest
def backtest(cfg: Config = Config(), start: str = "2020-01-01") -> LAB.SimResult:
    """Backtest ĐỦ CHI PHÍ: spread + commission mỗi cross + swap mỗi đêm giữ."""
    panel = LAB.build_panel(TIMEFRAME, start=start,
                            broker_markup_pct=cfg.broker_markup_pct)
    pos = target_weights(panel.logp, cfg)
    return LAB.simulate_positions(panel, pos, name="cross_xs_reversion")


def daily_pnl(cfg: Config = Config(), start: str = "2020-01-01") -> pd.Series:
    return backtest(cfg, start).pnl_daily


def stats(cfg: Config = Config(), start: str = "2020-01-01") -> Dict[str, object]:
    r = backtest(cfg, start)
    d = r.pnl_daily

    def sh(s):
        sd = float(s.std(ddof=1))
        return round(float(s.mean()) / sd * np.sqrt(252), 3) if sd > 0 else np.nan

    cum = d.cumsum()
    yrs = max((d.index.max() - d.index.min()).days / 365.25, 1e-9)
    return {
        "strategy": "CrossXsReversion", "timeframe": TIMEFRAME,
        "sharpe_all": sh(d),
        "sharpe_form": sh(d[d.index < FORM_END]),
        "sharpe_oos": sh(d[d.index >= FORM_END]),
        "ann_pct": round(float(cum.iloc[-1]) / 100.0 / yrs, 2),
        "max_dd_pct": round(float((cum.cummax() - cum).max()) / 100.0, 2),
        "turnover_per_year": round(r.turnover_per_year, 1),
        "cost_share_of_gross": round(
            (r.trade_cost_bps_bar + r.carry_cost_bps_bar)
            / max(r.gross_bps_bar, 1e-9), 3),
    }


# ═══════════════════════════════════════════════════════ live
def live_targets(cfg: Config = Config(), start: str = "2020-01-01") -> pd.Series:
    """Tỷ trọng mục tiêu từng cross cho nến H4 hiện tại (hàng cuối)."""
    return backtest(cfg, start).positions.iloc[-1].round(4)


def explain_decisions(cfg: Config = Config(), start: str = "2020-01-01") -> List:
    """BẢN GHI QUY TẮC VÀO LỆNH cho cả 20 cross — kể cả cross không được chọn.

    Câu hỏi "vì sao EURGBP hôm nay không có vị thế" chỉ trả lời được nếu có dòng của
    EURGBP kèm z-score và thứ hạng của nó. Nên ghi cả rổ, không chỉ 14 cross đã chọn.

    ⚠️ TÍN HIỆU LẤY TẠI NẾN TÁI CÂN BẰNG GẦN NHẤT, KHÔNG PHẢI NẾN HIỆN TẠI.
    Vị thế được GIỮ giữa hai lần tái cân bằng, nên z hiện tại đã trôi khỏi z lúc ra
    quyết định. Ghép tỷ trọng hôm nay với z hôm nay tạo ra bản ghi TỰ MÂU THUẪN kiểu
    "hạng 12/20 — thuộc top 7", và bản ghi tự mâu thuẫn thì vô dụng khi truy vết lệnh.
    """
    from src.python.execution import rule_trace as RT

    panel = LAB.build_panel(TIMEFRAME, start=start,
                            broker_markup_pct=cfg.broker_markup_pct)
    z = zscore(panel.logp, cfg.window_bars)
    W = target_weights(panel.logp, cfg)

    n = len(panel.logp)
    since = int((n - 1) % cfg.rebalance_bars)
    j = (n - 1) - since                       # chỉ số nến tái cân bằng gần nhất
    # tín hiệu là −z: z thấp nhất được MUA, nên đảo dấu để "hạng 1 = mua" như các chân
    # xếp hạng khác. Không đảo thì hạng 1 lại là chân bán, đọc log sẽ ngược.
    return RT.traces_from_ranking(
        timestamp=panel.logp.index[-1], strategy="CrossXsReversion",
        signal_name=f"neg_zscore_{cfg.window_bars}bar",
        signal=-z.iloc[j], weights=W.iloc[-1], n_leg=cfg.n_leg,
        cost_bps=panel.cost_1rt_bps,
        bars_since=since, bars_next=cfg.rebalance_bars - since)


if __name__ == "__main__":
    import json
    print(json.dumps(stats(), indent=2, ensure_ascii=False))
    print()
    for t in sorted(explain_decisions(), key=lambda x: -abs(x.target_weight))[:6]:
        print(t.explain())


# Rổ 20 cross tổng hợp — lấy từ SSOT `research/fx_cross_pairs.CROSS_DEFS` thay vì
# viết lại, để không có hai danh sách trôi khỏi nhau.
_CROSS_UNIVERSE = tuple(d[0] for d in _CP.CROSS_DEFS)

# ══ NGUỒN GỐC — mỗi dòng một bài, kèm đường dẫn mở được
SOURCES = (
    "Lo & MacKinlay (1990) \"When Are Contrarian Profits Due to Stock Market "
    "Overreaction?\", Review of Financial Studies 3(2) — KHÔNG có bản gốc trong kho, "
    "trích gián tiếp qua "
    "D:/project-learning/documents/forex-strategies/2607.19497v1.md",
    "Avellaneda & Lee (2010) \"Statistical Arbitrage in the U.S. Equities Market\", "
    "Quantitative Finance 10(7) — KHÔNG có bản gốc trong kho, trích gián tiếp qua "
    "D:/project-learning/documents/forex-strategies/57231515_202509.md",
    "Olszweski & Zhou (2014) \"Strategy diversification: Combining momentum and carry "
    "strategies within a foreign exchange portfolio\", J. Deriv. & Hedge Funds 19(4) — "
    "D:/project-learning/documents/forex-strategies/jdhf.2013.16.pdf",
)

# ══ THẺ LUẬT — dữ liệu cho GUI và tests/test_rulebook.py.
# ══ Bản người đọc là khối QUY TẮC VÀO LỆNH ở ĐẦU FILE, sinh ra từ đây.
RULEBOOK = RB.RuleBook(
    name="CrossXsReversion",
    signal_tf="H4", execution_tf="H4", direction="BOTH",
    universe=_CROSS_UNIVERSE,
    max_positions=2 * N_LEG,
    family="Cross-Sectional Z-Score Reversion trên cross tổng hợp",
    source=" · ".join(SOURCES),
    hours_utc="mọi giờ",
    forbidden_hours_utc=(),
    indicators=(
        f"z(cross) = (logp − trung bình {WINDOW_BARS} nến) / σ({WINDOW_BARS} nến), "
        f"cửa sổ KẾT THÚC ở nến trước (.shift(1))",
    ),
    entry_logic="RANK",
    entry_rules=(
        RB.Rule("a", f"nến này là nến tái cân bằng (mỗi {REBALANCE_BARS} nến H4 "
                     f"= {REBALANCE_DAYS} ngày giao dịch)",
                "mỗi nến thì chi phí ăn 60% gross → Sharpe rơi về 0,305; "
                "5 ngày thì tín hiệu hết hạn → 0,072"),
        RB.Rule("b", f"MUA {N_LEG} cross có z THẤP nhất trong 20 cross",
                "bị bán quá mức so với 19 cross khác → kỳ vọng hồi lên"),
        RB.Rule("c", f"BÁN {N_LEG} cross có z CAO nhất"),
        RB.Rule("d", f"tỷ trọng chia đều 1/{N_LEG} mỗi chân — KHÔNG tối ưu hoá",
                "tín hiệu z ở đây YẾU nhưng RỘNG: chọn 3 cross tốt nhất là đặt cược vào "
                "độ chính xác của thứ hạng, mà độ chính xác đó không có (n_leg 3 → 0,131)"),
    ),
    entry_price="khớp thị trường trên hai chân của cross tổng hợp",
    exit_rules=(
        RB.Rule("x1", f"tái cân bằng kế tiếp sau {REBALANCE_BARS} nến H4"),
    ),
    stop_loss="KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop",
    take_profit="không có — thoát theo tín hiệu hoặc time-stop",
    blocks=(
        "chết ở chi phí ×5 (Sharpe −0,619) — phải đo spread cross thật trên MT5",
        "biên swap broker 3,0%/năm → Sharpe 0,083, gần như hết edge",
    ),
    frequency=f"tái cân bằng mỗi {REBALANCE_DAYS} ngày ≈ 126 lần/năm · "
              f"vòng quay 13,3/năm",
    avg_holding=f"{REBALANCE_DAYS} ngày giao dịch",
    expectancy="Sharpe 0,460 ALL · 0,505 FORM · 0,381 OOS · MaxDD 7,75% · "
               "+2,40%/năm. Control p = 0,0000 · bootstrap P(<0) = 7,9%",
    trace_signal_name=f"neg_zscore_{WINDOW_BARS}bar",
)
