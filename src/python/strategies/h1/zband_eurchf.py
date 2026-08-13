"""zband_eurchf.py — ZBandEURCHFH1

EURCHF · H1 · BOTH · Z-Band Mean Reversion (Ornstein-Uhlenbeck, không cắt lỗ theo giá)

┌─ QUY TẮC VÀO LỆNH ────────────────────────────────────────────────────────────┐
│  VÀO   (đủ CẢ)                                                                │
│     a. |z| > 2.0                                                              │
│     b. nến TRƯỚC cũng ngoài dải: |z(t−1)| > 2.0                               │
│     c. z < −2.0 → MUA · z > +2.0 → BÁN                                        │
│     → khớp tại giá MỞ CỬA nến kế tiếp sau nến tín hiệu                        │
│                                                                               │
│  THOÁT                                                                        │
│     · z về 0                                                                  │
│     · time-stop 72 nến H1                                                     │
│     · xuất hiện tín hiệu NGƯỢC chiều                                          │
│                                                                               │
│  CẮT LỖ  KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop       │
│  VỊ THẾ  tối đa 1                                                             │
└───────────────────────────────────────────────────────────────────────────────┘

KẾT QUẢ   Sharpe 0.767 ALL · 0.827 FORM · 0.665 OOS · net 3.01 bps/lệnh (t = 2.35) ·
          thắng 67.8% · 6/7 năm dương
TẦN SUẤT  628 lệnh trong 6.5 năm ≈ 96 lệnh/năm · giữ 72 nến H1
CHỈ BÁO   z = (log giá − trung bình 24 nến) / độ lệch chuẩn 24 nến · time-stop = 72 nến
          H1
PHÂN LOẠI CỔ ĐIỂN (dải lệch chuẩn / Ornstein-Uhlenbeck), TINH CHỈNH HIỆN ĐẠI — công cụ
          chọn bằng chẩn đoán Sepp & Lucic 2026, thoát bằng time-stop Zheng Nan 2025

NGUỒN
  · Sepp & Lucic (2026) "The Science and Practice of Trend-Following Systems",
    arXiv:2607.19497v1
    D:/project-learning/documents/forex-strategies/2607.19497v1.pdf
  · Zheng Nan (2025) "Profitability of Pairs Trading Based on Cointegration in the
    Foreign Exchange Market", MSc thesis Waseda
    D:/project-learning/documents/forex-strategies/57231515_202509.pdf

Số liệu SAU ĐỦ CHI PHÍ (spread đo thật trên MT5 14/08/2026 ×1,5 + commission + swap +
biên broker 1,0%/năm). OOS từ 2024-01-01 chưa từng dùng để chọn gì. Spread là của tài
khoản DEMO — đo lại bằng `scripts/measure_broker_costs.py` trước khi cấp vốn.
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from src.python.strategies import zband_core as ZB

NAME = "ZBandEURCHFH1"
INSTRUMENT = "EURCHF"
TIMEFRAME = "H1"

# Tham số — chọn theo VÙNG, không theo đỉnh. Xem `reports/fx_research/focused_mr.csv`
# cho toàn bộ lưới N × k; các ô lân cận cùng dấu, không phải đỉnh cô lập.
WINDOW_BARS = 24
ENTRY_SIGMA = 2.0
TIMESTOP_MULT = 3.0

CONFIG = ZB.ZBandConfig(
    name=NAME, instrument=INSTRUMENT, timeframe=TIMEFRAME,
    window_bars=WINDOW_BARS, entry_sigma=ENTRY_SIGMA,
    timestop_mult=TIMESTOP_MULT)

# Bằng chứng đo được — sau ĐỦ chi phí, ở đòn bẩy 1,0. Hai hằng số này đi
# thẳng vào thẻ luật và vào docstring đầu file, nên chúng là MỘT nguồn.
EXPECTANCY = (
    "Sharpe 0.767 ALL · 0.827 FORM · 0.665 OOS · net 3.01 bps/lệnh (t = 2.35) · thắng "
    "67.8% · 6/7 năm dương"
)
FREQUENCY = "628 lệnh trong 6.5 năm ≈ 96 lệnh/năm"

RULEBOOK = ZB.rulebook(
    CONFIG, expectancy=EXPECTANCY, frequency=FREQUENCY)


def _load(start: str = "2020-01-01", broker_markup_pct: float = 1.0):
    """Nến cross tổng hợp + chi phí thật của nó."""
    from research.fx.trade_lab import load_crosses
    for ins in load_crosses(TIMEFRAME, start=start,
                            broker_markup_pct=broker_markup_pct):
        if ins.name == INSTRUMENT:
            return ins
    raise KeyError(f"không dựng được cross {INSTRUMENT} ở khung {TIMEFRAME}")


def backtest(start: str = "2020-01-01", *, broker_markup_pct: float = 1.0
             ) -> ZB.BacktestResult:
    ins = _load(start, broker_markup_pct)
    return ZB.run(ins.df, ins.cost_1rt_bps, ins.swap_bps_per_bar, CONFIG)


def daily_pnl(start: str = "2020-01-01", *, broker_markup_pct: float = 1.0
              ) -> pd.Series:
    return backtest(start, broker_markup_pct=broker_markup_pct).pnl_daily


def stats(start: str = "2020-01-01") -> Dict[str, object]:
    return ZB.stats(backtest(start), CONFIG)


def live_decision(start: str = "2020-01-01", bars_held: int = 0,
                  side: int = 0) -> ZB.EntryDecision:
    """Quyết định cho nến ĐÃ ĐÓNG gần nhất — cùng đường code với backtest."""
    ins = _load(start)
    return ZB.live_decision(ins.df, ins.cost_1rt_bps, ins.swap_bps_per_bar,
                            CONFIG, bars_held=bars_held, side=side)


def explain_decisions(start: str = "2020-01-01", bars_held: int = 0) -> List:
    """Bản ghi quy tắc vào lệnh. Chiến lược MỘT công cụ nên chỉ có một bản ghi."""
    return [live_decision(start, bars_held)]


if __name__ == "__main__":
    import json
    print(json.dumps(stats(), indent=2, ensure_ascii=False, default=str))
    print()
    print(live_decision().explain())
