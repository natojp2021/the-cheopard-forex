"""Kiểm định ĐƯỜNG VÀO LỆNH THẬT — bốn lớp thêm ngày 14/08/2026.

VÌ SAO FILE TEST NÀY TỒN TẠI
=============================
Lỗ hổng mà nó ghim lại là loại tệ nhất: KHÔNG có exception, KHÔNG có test đỏ, chỉ
có một hệ chạy khác hẳn hệ đã kiểm định.

    `backtest()`      dùng đủ 27 chân  →  Sharpe 3,313 · +22,3%/năm ở 3,7x
    `live_targets()`  phát ra  3 chân  →  hai chân D1 + một chân cross H1

22 chân một-công-cụ đều đã có `live_decision()` và `registry.PORTFOLIO["entry_points"]`
khai đủ 27 đường, nhưng không có gì gọi chúng. Hai chân xếp hạng thì chỉ được ghi
log chứ không phát tỷ trọng. Mọi con số công bố vì vậy mô tả một danh mục mà đường
live không dựng được — và không một test nào trước đây phát hiện điều đó.

Bốn nhóm test dưới đây ghim bốn lớp đã thêm để bịt lỗ hổng:
    1. đủ 27 chân tới được đường live
    2. tỷ trọng RÒNG có triệt tiêu chân ngược chiều
    3. cầu chì thảm hoạ không thoái hoá thành dừng lỗ chiến lược
    4. lớp đọc rủi ro thật FAIL-CLOSED khi không đọc được vị thế
"""
from __future__ import annotations

import pytest

from src.python.execution import disaster_stop as DS
from src.python.execution import portfolio_risk as PR
from src.python.strategies import portfolio as PF
from src.python.strategies import registry as REG


# ═════════════════════════════════════════════════════ 1. đủ 27 chân tới live
def test_single_legs_cover_every_non_aggregate_leg():
    """22 chân một-công-cụ phải là ĐÚNG phần bù của 5 chân gộp trong LEG_WEIGHTS."""
    aggregate = {"reversal", "carry", "cross_h1", "cross_mom", "cross_xs_h4"}
    assert set(PF.SINGLE_LEGS) | aggregate == set(PF.LEG_WEIGHTS)
    assert set(PF.SINGLE_LEGS) & aggregate == set()
    assert len(PF.SINGLE_LEGS) == 22


def test_every_single_leg_resolves_through_registry():
    """Đường import phải lấy từ registry, và phải gọi được thật.

    Ánh xạ chết (tên chiến lược sai chính tả) sẽ làm chân đó im lặng biến mất khỏi
    danh mục live — đúng dạng lỗi mà file test này sinh ra để chặn.
    """
    from importlib import import_module

    for leg, name in PF.SINGLE_LEGS.items():
        assert name in REG.PORTFOLIO["entry_points"], f"{leg}: {name} thiếu điểm vào"
        path = REG.PORTFOLIO["entry_points"][name]
        mod_path, _, fn = path.partition(":")
        assert callable(getattr(import_module(mod_path), fn)), f"{name}: {path}"


def test_new_live_entry_points_registered():
    """Bốn lớp mới phải nằm trong registry — nếu không thì không ai biết chúng có."""
    from importlib import import_module

    for key in ("target_weights", "netting_report", "disaster_stop", "live_risk"):
        path = REG.PORTFOLIO[key]
        mod_path, _, fn = path.partition(":")
        assert callable(getattr(import_module(mod_path), fn)), f"{key}: {path}"


# ═════════════════════════════════════════════════════ 2. triệt tiêu tỷ trọng
class _FakeDecision:
    def __init__(self, instrument: str, action: str):
        self.instrument = instrument
        self.cross = instrument
        self.action = action


def _targets(single: dict, *, cross=()):
    import pandas as pd

    return PF.PortfolioTargets(
        asof="2026-08-14",
        pair_weights=pd.Series(dtype=float),
        cross_decisions=list(cross),
        leg_scale={k: 1.0 for k in PF.LEG_WEIGHTS},
        regime="CALM",
        single_decisions=single,
        rank_weights={})


def test_opposing_legs_on_same_instrument_cancel():
    """Hai chân cùng công cụ ngược chiều, cùng suất → tỷ trọng ròng bằng 0.

    Đây là luật Burnside et al. (NBER w16942): "khi hai chiến lược BẤT ĐỒNG, vị thế
    ròng cho đồng tiền đó là ZERO". Gửi cả hai lệnh là trả HAI lần spread cho một
    phơi nhiễm ròng bằng không.
    """
    # rsidiv_nzdcad_h1 và rsidiv_nzdcad_m30 cùng suất _HALF, cùng công cụ NZDCAD.
    t = _targets({"rsidiv_nzdcad_h1": _FakeDecision("NZDCAD", "BUY"),
                  "rsidiv_nzdcad_m30": _FakeDecision("NZDCAD", "SELL")})
    w = PF.target_weights(t)
    assert w.get("NZDCAD", 0.0) == pytest.approx(0.0, abs=1e-9)


def test_agreeing_legs_on_same_instrument_add_up():
    """Cùng chiều thì CỘNG — nếu không thì triệt tiêu đã ăn cả tín hiệu đồng thuận."""
    t = _targets({"rsidiv_nzdcad_h1": _FakeDecision("NZDCAD", "BUY"),
                  "rsidiv_nzdcad_m30": _FakeDecision("NZDCAD", "BUY")})
    w = PF.target_weights(t)
    assert w.get("NZDCAD", 0.0) == pytest.approx(1.0, abs=1e-9)


def test_hold_keeps_existing_side_and_flat_closes():
    """`HOLD` KHÔNG mang chiều — phải lấy từ vị thế đang giữ, `FLAT` thì về 0.

    Suy đoán chiều cho HOLD là cách sinh ra lệnh đảo chiều không ai yêu cầu.
    """
    t = _targets({"accel_gbpnzd_h1": _FakeDecision("GBPNZD", "HOLD")})
    assert PF.target_weights(t, positions={"accel_gbpnzd_h1": -1}).get(
        "GBPNZD", 0.0) == pytest.approx(-1.0)
    # Không biết vị thế cũ → không có mục tiêu, chứ không phải đoán MUA.
    assert PF.target_weights(t).empty or abs(
        PF.target_weights(t).get("GBPNZD", 0.0)) < 1e-9

    t2 = _targets({"accel_gbpnzd_h1": _FakeDecision("GBPNZD", "FLAT")})
    assert abs(PF.target_weights(t2, positions={"accel_gbpnzd_h1": 1}).get(
        "GBPNZD", 0.0)) < 1e-9


def test_target_weights_are_normalised_to_gross_one():
    """Tổng TRỊ TUYỆT ĐỐI = 1,0 để `size_portfolio` nhân đòn bẩy lên là ra notional."""
    t = _targets({"zb_audcad_h1": _FakeDecision("AUDCAD", "BUY"),
                  "zb_gbpaud_h1": _FakeDecision("GBPAUD", "SELL"),
                  "accel_gbpnzd_h1": _FakeDecision("GBPNZD", "BUY")})
    w = PF.target_weights(t)
    assert float(w.abs().sum()) == pytest.approx(1.0, abs=1e-6)


def test_netting_report_shows_what_was_saved():
    t = _targets({"rsidiv_nzdcad_h1": _FakeDecision("NZDCAD", "BUY"),
                  "rsidiv_nzdcad_m30": _FakeDecision("NZDCAD", "SELL")})
    r = PF.netting_report(t)
    assert r.loc["NZDCAD", "n_legs"] == 2
    assert r.loc["NZDCAD", "saved"] > 0, "hai chân triệt tiêu mà báo không tiết kiệm gì"


# ═════════════════════════════════════════════════════ 3. cầu chì thảm hoạ
def test_disaster_stop_is_far_from_price():
    """Cầu chì phải cách giá nhiều lần ATR — nếu gần, nó là SL chiến lược trá hình.

    Đo được hai lần độc lập (vòng 57, 59): SL 3×ATR làm kỳ vọng đổi dấu. Ngưỡng
    tối thiểu ở đây là 8×ATR, biên gấp hơn hai lần mức đã biết là gây hại.
    """
    s = DS.compute("AUDCAD", "BUY", 0.90, weight=0.11, leverage=3.7,
                   equity_usd=100_000.0, atr_daily_pct=0.5)
    assert s.ok, s.reason
    assert s.distance_atr >= DS.MIN_ATR_MULT
    assert s.stop_price < 0.90, "cầu chì lệnh MUA phải nằm DƯỚI giá vào"


def test_disaster_stop_refuses_when_it_would_become_a_strategy_stop():
    """Vị thế quá lớn → cầu chì rơi vào vùng nhiễu → PHẢI từ chối, không đặt lặng lẽ."""
    s = DS.compute("AUDCAD", "BUY", 0.90, weight=0.40, leverage=3.7,
                   equity_usd=100_000.0, atr_daily_pct=0.5)
    assert not s.ok
    assert "ATR" in s.reason


def test_disaster_stop_clamps_instead_of_leaving_position_naked():
    """Vị thế nhỏ đòi khoảng cách rất xa → KẸP về trần, KHÔNG bỏ trần vị thế.

    Từ chối đặt vì "xa quá" là để vị thế không có gì bảo vệ — tệ hơn hẳn một cầu chì
    gần hơn mức ngân sách đòi, vì kẹp chỉ làm tổn thất tối đa NHỎ đi.
    """
    s = DS.compute("EURUSD", "SELL", 1.10, weight=0.005, leverage=3.7,
                   equity_usd=100_000.0, atr_daily_pct=0.45)
    assert s.ok, s.reason
    assert s.distance_pct == pytest.approx(DS.MAX_DISTANCE_PCT)
    assert s.stop_price > 1.10, "cầu chì lệnh BÁN phải nằm TRÊN giá vào"


def test_disaster_stop_loss_never_exceeds_budget():
    """Tổn thất tại cầu chì không được vượt ngân sách một vị thế."""
    for w in (0.01, 0.05, 0.11, 0.2):
        s = DS.compute("AUDCAD", "BUY", 0.90, weight=w, leverage=3.7,
                       equity_usd=100_000.0)
        budget = 100_000.0 * DS.PER_POSITION_BUDGET_PCT / 100.0
        assert s.loss_at_stop_usd <= budget * 1.001, (w, s.loss_at_stop_usd)


# ═════════════════════════════════════════════════════ 4. đọc rủi ro thật
class _Pos:
    def __init__(self, symbol, volume, price_open, sl=0.0, type_=0, profit=0.0):
        self.symbol, self.volume, self.price_open = symbol, volume, price_open
        self.sl, self.type, self.profit = sl, type_, profit


class _FakeMT5:
    def __init__(self, positions):
        self._p = positions

    def positions_get(self, **_):
        return self._p


def test_risk_snapshot_fails_closed_when_positions_unreadable():
    """Không đọc được vị thế phải NÉM LỖI, không được trả về 'sổ rỗng'.

    Coi lỗi đọc là 'không có vị thế nào' là cách một tài khoản đầy lệnh bị nhìn thành
    tài khoản trống, rồi tầng trên cấp thêm phơi nhiễm lên phơi nhiễm nó không thấy.
    """
    with pytest.raises(RuntimeError):
        PR.snapshot(_FakeMT5(None), equity_usd=100_000.0)


def test_risk_snapshot_flags_positions_without_broker_stop():
    """Vị thế không có SL trên server broker phải bị nêu tên — đây là lỗ hổng chính."""
    snap = PR.snapshot(_FakeMT5([_Pos("EURUSD", 0.5, 1.10, sl=0.0)]),
                       equity_usd=100_000.0)
    assert "EURUSD" in snap.unprotected
    assert not snap.ok
    assert any("có lệnh dừng" in b for b in snap.breaches)


def test_risk_snapshot_flags_leverage_breach():
    """Phơi nhiễm vượt trần 3,7x phải thành vi phạm, không phải cảnh báo suông."""
    # 40 lot EURUSD ở 1,10 ≈ $4,4 triệu notional trên $100k equity = 44x.
    snap = PR.snapshot(_FakeMT5([_Pos("EURUSD", 40.0, 1.10, sl=1.0)]),
                       equity_usd=100_000.0)
    assert snap.actual_leverage > 3.7
    assert any("vượt trần" in b for b in snap.breaches)


def test_risk_snapshot_computes_net_currency_exposure():
    """Một vị thế EURGBP ngầm mang EUR long + GBP short — phải hiện ra ở phơi nhiễm."""
    snap = PR.snapshot(_FakeMT5([_Pos("EURGBP", 1.0, 0.85, sl=0.80)]),
                       equity_usd=100_000.0)
    assert snap.net_exposure["EUR"] > 0
    assert snap.net_exposure["GBP"] < 0


def test_reconcile_reports_drift_between_real_and_target():
    """Lệch giữa vị thế thật và lot mục tiêu phải hiện ra, không tự sửa."""
    from src.python.execution.portfolio_sizing import LotOrder

    snap = PR.snapshot(_FakeMT5([_Pos("EURUSD", 1.0, 1.10, sl=1.0)]),
                       equity_usd=100_000.0)
    out = PR.reconcile(snap, [LotOrder(symbol="EURUSD", weight=0.1,
                                       direction="BUY", lots=0.5,
                                       notional_usd=55_000.0)])
    assert out["EURUSD"]["lệch"] == pytest.approx(0.5)


# ═════════════════════════════════════════════════════ 5. kế hoạch lệnh hợp nhất
class _MT5:
    """MT5 giả: đủ cho `positions_get` và `symbol_info` (trả None → dùng fallback)."""

    def __init__(self, positions=()):
        self._p = list(positions)

    def positions_get(self, **_):
        return self._p

    def symbol_info(self, _symbol):
        return None

    def symbol_select(self, _symbol, _enable=True):
        return True


_PRICES = {"EURUSD": 1.10, "GBPUSD": 1.27, "USDJPY": 150.0, "AUDUSD": 0.66,
           "USDCAD": 1.36, "USDCHF": 0.88, "NZDUSD": 0.60,
           "AUDCAD": 0.90, "GBPAUD": 1.95, "GBPNZD": 2.10, "NZDCAD": 0.82}
_ATR = {k: 0.5 for k in _PRICES}


def test_order_plan_blocks_when_reconciliation_not_done():
    """Chưa đối soát xong thì KHÔNG lệnh nào được phép — fail-closed."""
    from src.python.execution import order_plan as OP

    t = _targets({"zb_audcad_h1": _FakeDecision("AUDCAD", "BUY")})
    plan = OP.build(t, equity_usd=100_000.0, prices=_PRICES, mt5=_MT5(),
                    reconciliation_done=False, atr_daily_pct=_ATR)
    assert not plan.allowed
    assert any("đối soát" in r for r in plan.gate.reasons)


def test_order_plan_blocks_when_a_position_has_no_fuse():
    """Còn vị thế không có cầu chì thì không được mở thêm."""
    from src.python.execution import order_plan as OP

    t = _targets({"zb_audcad_h1": _FakeDecision("AUDCAD", "BUY")})
    naked = _Pos("EURUSD", 0.5, 1.10, sl=0.0)
    plan = OP.build(t, equity_usd=100_000.0, prices=_PRICES, mt5=_MT5([naked]),
                    reconciliation_done=True, atr_daily_pct=_ATR)
    assert not plan.allowed
    assert any("cầu chì" in r for r in plan.gate.reasons)


def test_order_plan_classifies_reverse_separately_from_increase():
    """Đảo chiều phải mang nhãn REVERSE — gọi nhầm là INCREASE sẽ gửi lệnh sai chiều."""
    from src.python.execution import order_plan as OP

    assert OP._classify(0.5, -0.5) == "REVERSE"
    assert OP._classify(0.5, 1.0) == "INCREASE"
    assert OP._classify(1.0, 0.5) == "REDUCE"
    assert OP._classify(0.0, 0.5) == "OPEN"
    assert OP._classify(0.5, 0.0) == "CLOSE"


def test_order_plan_does_not_send_anything():
    """Module chỉ DỰNG kế hoạch. Nếu nó gọi order_send thì test này phải đỏ."""
    from src.python.execution import order_plan as OP

    class _Trap(_MT5):
        def order_send(self, *_a, **_k):     # pragma: no cover
            raise AssertionError("order_plan KHÔNG được gửi lệnh")

    t = _targets({"zb_audcad_h1": _FakeDecision("AUDCAD", "BUY")})
    OP.build(t, equity_usd=100_000.0, prices=_PRICES, mt5=_Trap(),
             reconciliation_done=True, atr_daily_pct=_ATR)


# ═════════════════════════════════════════════════════ 6. sizing cho CẶP CHÉO
def test_cross_pairs_have_profiles():
    """22/27 chân giao dịch cặp chéo — thiếu profile là sizing ném lỗi cho phần lớn sổ."""
    from src.python.shared import asset_profile as AP

    for sym in ("AUDCAD", "GBPNZD", "EURJPY", "NZDCAD", "CHFJPY"):
        assert sym in AP.PROFILES, f"{sym} thiếu AssetProfile"
    assert AP.get("EURJPY").pip == pytest.approx(0.01), "cặp JPY phải có pip 0,01"
    assert AP.get("AUDCAD").pip == pytest.approx(0.0001)


def test_cross_notional_requires_quote_conversion():
    """Bỏ trống `usd_per_quote` với cặp chéo phải NÉM LỖI, không dùng mặc định 1,0.

    Mặc định 1,0 làm notional EURJPY sai 150 lần — sai im lặng vì kết quả vẫn dương.
    """
    from src.python.execution import portfolio_sizing as PS

    with pytest.raises(ValueError):
        PS.lot_notional_usd("EURJPY", 160.0)
    # Có tỷ giá thì ra con số đúng bậc: 100.000 EUR × 160 JPY/EUR × (1/150) USD/JPY
    got = PS.lot_notional_usd("EURJPY", 160.0, 1.0 / 150.0)
    assert 100_000.0 < got < 120_000.0, got


def test_usd_per_quote_uses_direct_or_inverse_major():
    from src.python.shared import asset_profile as AP

    assert AP.usd_per_quote("GBPNZD", _PRICES) == pytest.approx(0.60)   # NZDUSD
    assert AP.usd_per_quote("EURJPY", _PRICES) == pytest.approx(1 / 150.0)  # 1/USDJPY
    assert AP.usd_per_quote("EURUSD", _PRICES) == pytest.approx(1.0)
    with pytest.raises(KeyError):
        AP.usd_per_quote("GBPNZD", {"EURUSD": 1.1})


# ═════════════════════════════════════════════════════ 7. sức khoẻ lịch tin
def test_news_calendar_health_reports_blind_currencies():
    """Lịch chỉ có USD/EUR/GBP — phải NÊU TÊN 5 đồng còn lại thay vì im lặng.

    Từ 14/08/2026 việc thiếu 5 đồng KHÔNG còn tính là "vấn đề": phạm vi đã được khai
    tường minh ở `COVERED_CURRENCIES` và người vận hành đã xác nhận không có thêm
    nguồn dữ liệu. Một giới hạn ĐÃ KHAI BÁO là một quyết định, không phải một lỗi.
    Nhưng nó vẫn phải ĐỌC ĐƯỢC — đó là thứ test này khoá lại.
    """
    from src.python.ai import news_guard as NG

    h = NG.health()
    assert set(h.blind_currencies) >= {"AUD", "NZD", "CAD", "CHF", "JPY"}
    assert set(h.covered_currencies) == set(NG.COVERED_CURRENCIES)
    assert "mù" in h.explain()


def test_news_decision_carries_calendar_problems():
    """Bản ghi quyết định phải mang theo vấn đề của lịch — không chỉ nằm ở hàm riêng."""
    from src.python.ai import news_guard as NG

    d = NG.decide(force=True)
    assert "LỊCH KHÔNG ĐẠT" in d.reason
