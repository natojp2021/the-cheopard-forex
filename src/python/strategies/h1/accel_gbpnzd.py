"""accel_gbpnzd.py — AccelGBPNZDH1

GBPNZD · H1 · BOTH · Gia tốc giá (đạo hàm bậc hai)

┌─ QUY TẮC VÀO LỆNH ────────────────────────────────────────────────────────────┐
│  VÀO   (đủ CẢ)                                                                │
│     a. gia tốc = lợi nhuận(48 nến) − lợi nhuận(48 nến trước đó), chuẩn hoá theo σ của│
│        chính nó                                                               │
│     b. |z(gia tốc)| > 2.5                                                     │
│     c. z < −2.5 → MUA · z > +2.5 → BÁN                                        │
│     → khớp tại giá MỞ CỬA nến kế tiếp sau nến tín hiệu                        │
│                                                                               │
│  THOÁT                                                                        │
│     · xuất hiện tín hiệu NGƯỢC chiều                                          │
│     · time-stop 24 nến H1                                                     │
│                                                                               │
│  CẮT LỖ  KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop       │
│  VỊ THẾ  tối đa 1                                                             │
└───────────────────────────────────────────────────────────────────────────────┘

KẾT QUẢ   Sharpe 1.023 ALL · 1.282 FORM · 0.530 OOS · net 22.80 bps/lệnh (t = 3.24) ·
          thắng 62.4% · 6/7 năm dương
TẦN SUẤT  109 lệnh trong 6.4 năm ≈ 17 lệnh/năm · giữ tối đa 24 nến H1
CHỈ BÁO   lợi nhuận log 48 nến, và hiệu của hai lợi nhuận liên tiếp · σ(192 nến) của gia
          tốc, để chuẩn hoá
PHÂN LOẠI HIỆN ĐẠI — ĐẢO CHIỀU quy tắc accel của Carver 2015; họ duy nhất trong danh mục
          đọc đạo hàm bậc hai

NGUỒN
  · Carver (2015) "Systematic Trading", Harriman House
    quy tắc "accel" = đạo hàm của EWMAC; bản cài đặt ở
    `project-refer/carver-systematic-trading/core/forecast.py`. Ở đây dùng NGƯỢC chiều
    Carver
  · Sepp & Lucic (2026) "The Science and Practice of Trend-Following Systems",
    arXiv:2607.19497v1
    D:/project-learning/documents/forex-strategies/2607.19497v1.pdf

Số liệu SAU ĐỦ CHI PHÍ (spread đo thật trên MT5 14/08/2026 ×1,5 + commission + swap +
biên broker 1,0%/năm). OOS từ 2024-01-01 chưa từng dùng để chọn gì. Spread là của tài
khoản DEMO — đo lại bằng `scripts/measure_broker_costs.py` trước khi cấp vốn.
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from src.python.strategies import signal_families as SF

NAME = "AccelGBPNZDH1"
FAMILY = "accel"
INSTRUMENT = "GBPNZD"
TIMEFRAME = "H1"

# Tham số — chọn theo VÙNG, không theo đỉnh. Xem `reports/fx_research/h1_families.csv`
# cho toàn bộ lưới; đa số ô lân cận cùng dấu.
WINDOW = 48
THRESHOLD = 2.5
TIMESTOP_BARS = 24

CONFIG = SF.FamilyConfig(
    name=NAME, family=FAMILY, instrument=INSTRUMENT, timeframe=TIMEFRAME,
    window=WINDOW, threshold=THRESHOLD, timestop_bars=TIMESTOP_BARS)

# Bằng chứng đo được — sau ĐỦ chi phí, ở đòn bẩy 1,0. Hai hằng số này đi
# thẳng vào thẻ luật và vào docstring đầu file, nên chúng là MỘT nguồn.
EXPECTANCY = (
    "Sharpe 1.023 ALL · 1.282 FORM · 0.530 OOS · net 22.80 bps/lệnh (t = 3.24) · thắng "
    "62.4% · 6/7 năm dương"
)
FREQUENCY = "109 lệnh trong 6.4 năm ≈ 17 lệnh/năm"

RULEBOOK = SF.rulebook(
    CONFIG, expectancy=EXPECTANCY, frequency=FREQUENCY)


def _load(start: str = "2020-01-01", broker_markup_pct: float = 1.0):
    """Nến + chi phí thật của công cụ."""
    from research.fx.trade_lab import load_crosses, load_majors
    for ins in (load_crosses(TIMEFRAME, start=start,
                             broker_markup_pct=broker_markup_pct)
                + load_majors(TIMEFRAME, start=start,
                              broker_markup_pct=broker_markup_pct)):
        if ins.name == INSTRUMENT:
            return ins
    raise KeyError(f"không dựng được {INSTRUMENT} ở khung {TIMEFRAME}")


def backtest(start: str = "2020-01-01", *, broker_markup_pct: float = 1.0
             ) -> SF.BacktestResult:
    ins = _load(start, broker_markup_pct)
    return SF.run(ins.df, ins.cost_1rt_bps, ins.swap_bps_per_bar, CONFIG)


def daily_pnl(start: str = "2020-01-01", *, broker_markup_pct: float = 1.0
              ) -> pd.Series:
    return backtest(start, broker_markup_pct=broker_markup_pct).pnl_daily


def stats(start: str = "2020-01-01") -> Dict[str, object]:
    return SF.stats(backtest(start), CONFIG)


def live_decision(start: str = "2020-01-01", bars_held: int = 0,
                  side: int = 0) -> SF.EntryDecision:
    """Quyết định cho nến ĐÃ ĐÓNG gần nhất — cùng đường code với backtest."""
    ins = _load(start)
    return SF.live_decision(ins.df, ins.cost_1rt_bps, ins.swap_bps_per_bar,
                            CONFIG, bars_held=bars_held, side=side)


def explain_decisions(start: str = "2020-01-01", bars_held: int = 0) -> List:
    """Bản ghi quy tắc vào lệnh. Chiến lược MỘT công cụ nên chỉ có một bản ghi."""
    return [live_decision(start, bars_held)]


if __name__ == "__main__":
    import json
    print(json.dumps(stats(), indent=2, ensure_ascii=False, default=str))
    print()
    print(live_decision().explain())
