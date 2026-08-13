"""vol_regime_audchf.py — VolRegimeAUDCHFM30

AUDCHF · M30 · BOTH · Chế độ biến động (tỷ số σ ngắn / σ dài)

┌─ QUY TẮC VÀO LỆNH ────────────────────────────────────────────────────────────┐
│  VÀO   (đủ CẢ)                                                                │
│     a. σ(48 nến) / σ(192 nến) > 1.3                                           │
│     b. tổng lợi nhuận 48 nến gần nhất < 0 → MUA · > 0 → BÁN                   │
│     → khớp tại giá MỞ CỬA nến kế tiếp sau nến tín hiệu                        │
│                                                                               │
│  THOÁT                                                                        │
│     · xuất hiện tín hiệu NGƯỢC chiều                                          │
│     · time-stop 48 nến M30                                                    │
│                                                                               │
│  CẮT LỖ  KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop       │
│  VỊ THẾ  tối đa 1                                                             │
└───────────────────────────────────────────────────────────────────────────────┘

KẾT QUẢ   Sharpe 0.639 ALL · 0.498 FORM · 0.906 OOS · net 9.00 bps/lệnh (t = 2.00) ·
          thắng 61.0% · 7/7 năm dương
TẦN SUẤT  223 lệnh trong 6.5 năm ≈ 34 lệnh/năm · giữ tối đa 48 nến M30
CHỈ BÁO   σ ngắn hạn: độ lệch chuẩn lợi nhuận log 48 nến · σ dài hạn: độ lệch chuẩn 192
          nến
PHÂN LOẠI HIỆN ĐẠI — dựng từ tính chất cụm biến động (Cont 2001), không có tiền lệ trong
          tài liệu bán lẻ

NGUỒN
  · Cont (2001) "Empirical properties of asset returns: stylized facts and statistical
    issues", Quantitative Finance 1(2)
    KHÔNG có bản gốc trong kho, dẫn lại trong
    D:/project-learning/documents/forex-strategies/1404.3274v1.md

Số liệu SAU ĐỦ CHI PHÍ (spread đo thật trên MT5 14/08/2026 ×1,5 + commission + swap +
biên broker 1,0%/năm). OOS từ 2024-01-01 chưa từng dùng để chọn gì. Spread là của tài
khoản DEMO — đo lại bằng `scripts/measure_broker_costs.py` trước khi cấp vốn.
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from src.python.strategies import signal_families as SF

NAME = "VolRegimeAUDCHFM30"
FAMILY = "vol_regime"
INSTRUMENT = "AUDCHF"
TIMEFRAME = "M30"

# Tham số — chọn theo VÙNG, không theo đỉnh. Xem `reports/fx_research/h1_families.csv`
# cho toàn bộ lưới; đa số ô lân cận cùng dấu.
WINDOW = 192
THRESHOLD = 1.3
TIMESTOP_BARS = 48

CONFIG = SF.FamilyConfig(
    name=NAME, family=FAMILY, instrument=INSTRUMENT, timeframe=TIMEFRAME,
    window=WINDOW, threshold=THRESHOLD, timestop_bars=TIMESTOP_BARS)

# Bằng chứng đo được — sau ĐỦ chi phí, ở đòn bẩy 1,0. Hai hằng số này đi
# thẳng vào thẻ luật và vào docstring đầu file, nên chúng là MỘT nguồn.
EXPECTANCY = (
    "Sharpe 0.639 ALL · 0.498 FORM · 0.906 OOS · net 9.00 bps/lệnh (t = 2.00) · thắng "
    "61.0% · 7/7 năm dương"
)
FREQUENCY = "223 lệnh trong 6.5 năm ≈ 34 lệnh/năm"

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
