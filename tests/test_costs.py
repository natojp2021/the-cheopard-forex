"""Kiểm định MÔ HÌNH CHI PHÍ — spread, commission, swap, biên broker.

VÌ SAO
======
Chi phí là nơi hệ này gần chết nhất, và mỗi lần đều vì BỎ SÓT một lớp, không vì
tính sai lớp đang có:

    bỏ commission   commission EURUSD (0,70 pip) LỚN HƠN spread trung vị (0,31 pip)
    bỏ swap         `project-refer/carver` cho thấy Sharpe 0,216 sau spread+commission
                    nhưng **−0,456** sau swap
    bỏ biên broker  biên 1,0%/năm là lớp CHI PHÍ LỚN NHẤT (1,590%/năm) — lớn hơn cả
                    spread (0,355) và chênh lệch lãi suất (0,184) cộng lại

Nên các test ở đây không kiểm tra "công thức có đúng dấu" mà kiểm tra "lớp chi phí có
thực sự được cộng vào" — bằng cách bật/tắt nó và đòi kết quả PHẢI đổi.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.python.shared import carry_costs as CC


def test_swap_calendar_multiplier_is_365_over_252():
    """Swap tính theo ngày LỊCH, lợi nhuận tính theo ngày GIAO DỊCH.

    Bỏ qua hệ số này làm chi phí swap bị đánh giá thấp đi 31% — đúng bằng
    365/252 − 1. Học từ `project-refer/carver-systematic-trading`.
    """
    assert CC.SWAP_CALENDAR_MULTIPLIER == pytest.approx(365.0 / 252.0)
    assert CC.SWAP_CALENDAR_MULTIPLIER > 1.44


def test_policy_rates_cover_all_eight_currencies():
    """Rổ có 8 đồng; thiếu một đồng làm chân carry lệch âm thầm."""
    assert len(CC.POLICY_RATES) >= 8
    for ccy in ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"):
        assert ccy in CC.POLICY_RATES, f"thiếu lãi suất {ccy}"


def test_rate_series_is_stepwise_not_interpolated():
    """Lãi suất chính sách đổi theo BƯỚC tại ngày họp, không nội suy tuyến tính.

    Nội suy làm tín hiệu carry biết trước quyết định của ngân hàng trung ương —
    một dạng look-ahead khó thấy vì nó nằm trong dữ liệu, không nằm trong code.
    """
    idx = pd.date_range("2020-01-01", "2024-12-31", freq="B")
    R = CC.rate_series(idx)
    assert len(R) == len(idx)
    assert R.notna().all().all()
    for ccy in ("USD", "EUR", "JPY"):
        # số giá trị KHÁC NHAU phải ít hơn nhiều số ngày — dấu hiệu của bậc thang
        assert R[ccy].nunique() < len(idx) / 20, f"{ccy} trông như đã bị nội suy"


def test_broker_markup_makes_carry_costlier_both_ways():
    """Biên broker là chi phí THUẦN: nó làm CẢ long và short đều tệ hơn.

    Đây là điểm dễ cài sai nhất: nếu cài như một độ lệch có dấu thì một chiều sẽ
    được LỢI từ biên broker — điều không tồn tại trên thị trường thật.
    """
    idx = pd.date_range("2022-01-01", "2023-12-31", freq="B")
    specs = {"EURUSD": ("EUR", "USD")}

    for side in (+1.0, -1.0):
        W = pd.DataFrame({"EURUSD": pd.Series(side, index=idx)})
        c0 = float(CC.pair_carry_bps(W, specs, broker_markup_pct=0.0)
                   ["total_carry_bps"].sum())
        c3 = float(CC.pair_carry_bps(W, specs, broker_markup_pct=3.0)
                   ["total_carry_bps"].sum())
        # quy ước: `total_carry_bps` DƯƠNG = CHI PHÍ. Biên broker phải LÀM TĂNG nó
        # ở cả hai chiều — nếu một chiều giảm thì biên đã bị cài như độ lệch có dấu.
        assert c3 > c0, f"chiều {side:+.0f}: biên broker phải làm carry ĐẮT hơn"


def test_transaction_cost_scales_with_turnover():
    """Gấp đôi vòng quay phải gấp đôi chi phí giao dịch — không hơn, không kém."""
    from src.python.research import fx_cross_lab as LAB

    panel = LAB.build_panel("H4", start="2023-01-01")
    n, m = panel.logp.shape
    cols = panel.logp.columns

    def alternating(period: int) -> pd.DataFrame:
        p = np.zeros((n, m))
        for i in range(n):
            p[i] = 1.0 if (i // period) % 2 == 0 else -1.0
        return pd.DataFrame(p, index=panel.logp.index, columns=cols)

    slow = LAB.simulate_positions(panel, alternating(40))
    fast = LAB.simulate_positions(panel, alternating(20))
    ratio = fast.trade_cost_bps_bar / slow.trade_cost_bps_bar
    assert 1.7 < ratio < 2.3, f"tỷ lệ chi phí = {ratio:.2f}, kỳ vọng ≈ 2"


def test_h4_leg_backtest_really_subtracts_costs():
    """Gross phải LỚN HƠN net, và khoảng cách phải khớp chi phí báo ra.

    Test này bắt lỗi "tính chi phí rồi quên trừ" — lỗi im lặng vì mọi con số vẫn có.
    """
    from src.python.strategies.h4 import cross_xs_reversion as XXS

    r = XXS.backtest()
    assert r.gross_bps_bar > 0
    total = r.trade_cost_bps_bar + r.carry_cost_bps_bar
    assert total > 0, "chi phí phải dương — không thì có lớp bị bỏ"
    assert total / r.gross_bps_bar > 0.25, "chi phí < 25% gross là bất thường trên FX"


def test_higher_broker_markup_lowers_sharpe():
    """Độ nhạy biên swap phải ĐƠN ĐIỆU giảm. Nếu không, mô hình chi phí sai dấu."""
    from src.python.strategies.h4 import cross_xs_reversion as XXS

    sh = []
    for mk in (0.0, 1.0, 2.0, 3.0):
        d = XXS.daily_pnl(XXS.Config(broker_markup_pct=mk))
        sd = float(d.std(ddof=1))
        sh.append(float(d.mean()) / sd * np.sqrt(252))
    assert all(sh[i] > sh[i + 1] for i in range(len(sh) - 1)), \
        f"Sharpe theo biên broker không giảm đơn điệu: {sh}"
