"""Danh mục MỘT CHÂN — hợp đồng giữa chiến lược và tầng thực thi.

Ba nhóm bất biến:

  1. KHOÁ CHÂN   ba công cụ = ba chân riêng, và hai bảng tra không được gộp. Gộp
                 chúng là chỗ đã sinh lỗi: `spec.symbols[0]` luôn trả EURUSD nên cả
                 ba chân cùng ghi vị thế lên một cặp.
  2. MỤC TIÊU    `stop_targets()` phải phát SL/TP đúng phía; `target_weights()` chỉ
                 mô tả phơi nhiễm và KHÔNG được dùng làm cỡ lệnh.
  3. GHI SỔ      phiên KHÔNG vào lệnh vẫn phải vào `decision_log` kèm lý do.
"""
from __future__ import annotations

from typing import Dict

import pandas as pd
import pytest

from src.python.strategies import portfolio as PF
from src.python.strategies import registry as REG
from src.python.strategies.h1 import asia_sweep as AS


# ═══════════════════════════════════════════════════════════════ khung giả
class _Dec:
    def __init__(self, instrument: str, side: int, enter: bool = True) -> None:
        self.instrument = instrument
        self.side = side
        self.state = "ENTRY" if enter else "WINDOW_CLOSED"
        self.asof = "2026-08-25"
        self.entry_px = 1.0850 if side else float("nan")
        self.stop_px = (1.0880 if side < 0 else 1.0820) if side else float("nan")
        self.tp_px = (1.0790 if side < 0 else 1.0910) if side else float("nan")
        self.sl_pips = 30.0
        self.rr = 3.0
        self.steps = (("asia_range", True, "biên Á 30,0 pip trong dải"),)
        self._enter = enter

    @property
    def enter(self) -> bool:
        return self._enter


def _targets(decisions: Dict[str, _Dec]) -> PF.PortfolioTargets:
    return PF.PortfolioTargets(
        asof="2026-08-25",
        single_decisions={f"asia_sweep:{k}": v for k, v in decisions.items()},
        leg_scale={"asia_sweep": 1.0})


# ═══════════════════════════════════════════════════════════════ 1. KHOÁ CHÂN
def test_one_leg_per_instrument():
    assert set(PF.LEG_INSTRUMENT.values()) == set(AS.INSTRUMENTS)
    assert len(PF.LEG_INSTRUMENT) == len(AS.INSTRUMENTS)


def test_single_legs_map_to_strategy_names_not_instruments():
    """`SINGLE_LEGS` phải tra được qua `registry.by_name` — nó là TÊN CHIẾN LƯỢC."""
    for leg, name in PF.SINGLE_LEGS.items():
        assert REG.by_name(name) is not None, f"{leg}: {name!r} không có trong registry"


def test_the_two_lookup_tables_have_the_same_keys():
    """Lệch khoá nghĩa là một chân có tên chiến lược mà không có công cụ, hoặc ngược lại."""
    assert set(PF.SINGLE_LEGS) == set(PF.LEG_INSTRUMENT)


def test_every_leg_resolves_to_an_entry_point():
    for name in set(PF.SINGLE_LEGS.values()):
        assert name in REG.PORTFOLIO["entry_points"], f"{name} thiếu điểm vào live"
        path = REG.PORTFOLIO["entry_points"][name]
        mod_path, _, attr = path.partition(":")
        from importlib import import_module
        mod = import_module(mod_path)
        assert callable(getattr(mod, attr, None)), f"{path} không gọi được"


def test_gui_rows_use_the_same_magic_as_the_order_router():
    """Bảng vận hành và bộ gửi lệnh phải dùng CÙNG một nguồn magic.

    Hai lược đồ băm khác nhau nghĩa là mọi hàng đều báo "không có lệnh" dù broker
    đang giữ vị thế — bảng nói dối mà không có cảnh báo nào.
    """
    from src.python.core import strategy_registry as SR
    from src.python.execution.order_router import magic_for

    specs = SR.all_specs()
    assert len(specs) == len(PF.LEG_INSTRUMENT)
    for g in specs:
        assert g.magic == magic_for(g.name), g.name
        assert g.symbol == PF.LEG_INSTRUMENT[g.name]


# ═══════════════════════════════════════════════════════════════ 2. MỤC TIÊU
def test_stop_targets_carry_sl_tp_on_the_right_side():
    t = _targets({"EURUSD": _Dec("EURUSD", -1), "GBPUSD": _Dec("GBPUSD", +1)})
    st = PF.stop_targets(t)
    assert set(st) == {"EURUSD", "GBPUSD"}
    assert st["EURUSD"]["stop"] > st["EURUSD"]["entry"] > st["EURUSD"]["tp"]
    assert st["GBPUSD"]["stop"] < st["GBPUSD"]["entry"] < st["GBPUSD"]["tp"]


def test_stop_targets_skip_decisions_that_do_not_enter():
    t = _targets({"EURUSD": _Dec("EURUSD", -1, enter=False)})
    assert PF.stop_targets(t) == {}


def test_stop_targets_skip_failed_instruments():
    t = PF.PortfolioTargets(
        asof="2026-08-25",
        single_decisions={"asia_sweep:EURUSD": RuntimeError("nạp nến hỏng"),
                          "asia_sweep:GBPUSD": _Dec("GBPUSD", +1)})
    st = PF.stop_targets(t)
    assert set(st) == {"GBPUSD"}


def test_target_weights_are_normalised_to_gross_one():
    t = _targets({"EURUSD": _Dec("EURUSD", -1), "GBPUSD": _Dec("GBPUSD", +1)})
    w = PF.target_weights(t)
    assert float(w.abs().sum()) == pytest.approx(1.0)
    assert w["EURUSD"] < 0 < w["GBPUSD"]


def test_no_signal_keeps_the_side_already_held():
    """Phiên không có setup KHÔNG phải chỉ thị đóng — nếu không, lệnh bị đóng ngay."""
    t = _targets({"EURUSD": _Dec("EURUSD", 0, enter=False)})
    held = PF.target_weights(t, positions={"asia_sweep:EURUSD": -1})
    assert held.get("EURUSD", 0.0) < 0, held.to_dict()
    flat = PF.target_weights(t, positions={})
    assert flat.empty or float(flat.abs().sum()) == 0.0


def test_side_of_holds_previous_on_non_entry_states():
    assert PF._side_of(_Dec("EURUSD", -1, enter=False), previous=+1) == +1
    assert PF._side_of(_Dec("EURUSD", -1, enter=True), previous=+1) == -1
    assert PF._side_of(RuntimeError("x"), previous=-1) == -1
    assert PF._side_of(None, previous=0) == 0


def test_exposure_report_nets_the_usd_leg():
    """Ba cặp đều có chân USD — ba lệnh cùng chiều USD là MỘT cược gấp ba."""
    t = _targets({"EURUSD": _Dec("EURUSD", -1), "GBPUSD": _Dec("GBPUSD", -1)})
    rep = PF.exposure_report(t)
    assert float(rep.loc["USD", "exposure"]) == pytest.approx(2.0)
    assert float(rep.loc["EUR", "exposure"]) == pytest.approx(-1.0)


def test_netting_report_has_no_savings_with_one_leg():
    t = _targets({"EURUSD": _Dec("EURUSD", -1)})
    rep = PF.netting_report(t)
    assert float(rep["saved"].abs().sum()) == 0.0


# ═══════════════════════════════════════════════════════════════ 3. GHI SỔ
def test_rejected_sessions_are_logged_too(monkeypatch):
    """`decision_log` phải nhận CẢ phiên không vào lệnh, kèm trạng thái và lý do."""
    seen = []
    from src.python.execution import decision_log as DLOG

    monkeypatch.setattr(DLOG, "record_many", lambda rows: seen.extend(rows))
    t = _targets({"EURUSD": _Dec("EURUSD", 0, enter=False)})
    PF._log_decisions(t)
    assert len(seen) == 1
    assert seen[0]["state"] == "WINDOW_CLOSED"
    assert seen[0]["steps"], "không ghi lại bước nào — không truy vết được"


def test_logging_failure_does_not_block_trading(monkeypatch):
    """Ghi sổ hỏng KHÔNG được chặn giao dịch — nhưng cũng không được lan ngoại lệ."""
    from src.python.execution import decision_log as DLOG

    def boom(_rows):
        raise OSError("đĩa đầy")

    monkeypatch.setattr(DLOG, "record_many", boom)
    PF._log_decisions(_targets({"EURUSD": _Dec("EURUSD", -1)}))


# ═══════════════════════════════════════════════════════ registry <-> code
def test_registry_risk_pct_matches_the_strategy_constant():
    """Hai chỗ khai mức rủi ro thì hai chỗ sẽ trôi khỏi nhau. Test này chốt chúng."""
    assert float(REG.PORTFOLIO["risk_pct_per_trade"]) == pytest.approx(
        AS.RISK_PCT_PER_TRADE)


def test_registry_universe_matches_the_strategy_basket():
    spec = REG.by_name(AS.NAME)
    assert tuple(spec.symbols) == tuple(AS.INSTRUMENTS)


def test_portfolio_declares_the_sl_sizing_path():
    """Danh mục PHẢI khai cả `risk_sizing` và `stop_targets` — thiếu một là fail-closed."""
    for key in ("risk_sizing", "stop_targets", "risk_pct_per_trade"):
        assert key in REG.PORTFOLIO, f"registry.PORTFOLIO thiếu {key!r}"
    assert "sizing" not in REG.PORTFOLIO, (
        "đường sizing theo tỷ trọng đã bị xoá — khoá `sizing` không được sống lại")


def test_current_direction_is_recorded_as_measured():
    """Hướng này đã đo và đã ghi vào `REJECTED_DIRECTIONS` — không được xoá bằng chứng."""
    assert REG.is_rejected("AsiaSweepFade_NoConfirmation") is not None
    assert REG.by_name(AS.NAME).stage == REG.FORWARD_TEST, (
        "chưa có số dương qua 6 kiểm định + cổng PBO thì không được lên LIVE")


# ═══════════════════════════════════════════════════════════ ĐƠN VỊ
def test_daily_pnl_is_in_percent_not_fraction():
    """Một R = `RISK_PCT_PER_TRADE` PHẦN TRĂM equity. Chia thêm 100 là sai 100 lần.

    Lỗi đã xảy ra và nó nguy hiểm đúng vì kết quả vẫn "hợp lý": MaxDD báo -0,09%
    trong khi số thật là -8,74%. Một con số rủi ro nhỏ hơn thực tế 100 lần thì không
    ai nhìn lại nó.
    """
    r_series = AS.daily_pnl("EURUSD")
    pct_series = AS.portfolio_daily_pnl()
    assert not r_series.empty and not pct_series.empty
    # Tổng % equity phải bằng tổng R của cả rổ nhân đúng mức rủi ro mỗi lệnh.
    total_r = sum(AS.daily_pnl(s).sum() for s in AS.INSTRUMENTS)
    assert pct_series.sum() == pytest.approx(total_r * AS.RISK_PCT_PER_TRADE, rel=1e-9)


def test_breaching_the_internal_floor_must_be_declared():
    """MaxDD vượt sàn nội bộ thì SSOT phải khai báo tường minh. Không được im lặng.

    Đây là bất biến FTMO quan trọng nhất của danh mục, và nó là hàm của
    `RISK_PCT_PER_TRADE`. Test này KHÔNG cấm vượt sàn — quyết định rủi ro thuộc về
    chủ tài khoản. Nó cấm vượt sàn mà KHÔNG AI BIẾT: nâng mức rủi ro qua ngưỡng mà
    không viết lý do vào `registry.PORTFOLIO["dd_floor_override"]` sẽ làm test đỏ.

    Ngược lại cũng đúng: khai báo vượt sàn trong khi MaxDD thật ra đạt là một cảnh
    báo giả nằm mãi trong SSOT, nên nó cũng bị chặn.
    """
    res = PF.backtest()
    st = PF.stats(res.pnl)
    dd = abs(st["MaxDD từ đỉnh %"])
    floor = float(REG.PORTFOLIO["max_dd_self_cap_pct"])
    override = str(REG.PORTFOLIO.get("dd_floor_override") or "").strip()
    if dd >= floor:
        assert override, (
            f"MaxDD {dd:.2f}% vượt sàn nội bộ {floor:.2f}% ở rủi ro "
            f"{AS.RISK_PCT_PER_TRADE:.2f}%/lệnh mà `registry.PORTFOLIO` KHÔNG khai "
            f"`dd_floor_override` — hạ `RISK_PCT_PER_TRADE` hoặc viết lý do ra")
        assert str(AS.RISK_PCT_PER_TRADE).replace(".", ",") in override, (
            "khai báo vượt sàn không nêu đúng mức rủi ro đang dùng — nó đã trôi khỏi "
            "code")
    else:
        assert not override, (
            f"MaxDD {dd:.2f}% ĐẠT sàn {floor:.2f}% nhưng SSOT vẫn khai "
            f"`dd_floor_override` — xoá nó, cảnh báo giả làm người đọc ngừng đọc")


def test_maxdd_matches_the_number_documented_in_the_registry():
    """Số MaxDD trong SSOT phải khớp số đo. Lệch nghĩa là SSOT đã trôi khỏi code."""
    res = PF.backtest()
    st = PF.stats(res.pnl)
    assert abs(st["MaxDD từ đỉnh %"]) == pytest.approx(
        float(REG.PORTFOLIO["max_dd_pct"]), abs=0.30), (
        f"đo được {st['MaxDD từ đỉnh %']:.2f}% · registry ghi "
        f"{REG.PORTFOLIO['max_dd_pct']:.2f}%")


def test_worst_day_stays_under_the_daily_cap():
    """Ngày tệ nhất phải dưới trần rủi ro ngày nội bộ, và do đó dưới mốc FTMO 5%."""
    from src.python.execution import order_plan as OP

    res = PF.backtest()
    st = PF.stats(res.pnl)
    assert abs(st["ngày tệ nhất %"]) < OP._DAILY_RISK_CAP_PCT
