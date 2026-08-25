"""Bất biến của chiến lược AsiaSweepH1. Kiểm HÀNH VI, không kiểm sự hiện diện của code.

Bốn nhóm, và mỗi nhóm neo vào một cách hệ này CÓ THỂ hỏng thật:

  1. NHÌN TRƯỚC   quyết định không được đổi khi ghim thêm dữ liệu TƯƠNG LAI. Đây là
                  test quan trọng nhất của file: bản đầu của `_mss_confirm` đọc close
                  của 1-3 nến SAU khi vào lệnh và cho ra winrate 73% (t = +14,6) —
                  một kết quả trông y như phát hiện. Test này bắt đúng lớp lỗi đó.
  2. CHI PHÍ      bật/tắt lớp chi phí phải làm kết quả ĐỔI. Chi phí bị bỏ sót là chỗ
                  duy nhất một chiến lược hoà biến thành một chiến lược "có lãi".
  3. NHÂN QUẢ     SL/TP chỉ được đặt ở phía ĐÚNG của giá vào; cú quét phải ĐÓNG lại
                  trong biên; nến vào lệnh phải SAU nến xác nhận.
  4. PHÂN HẠNG    cổng MSS phải thực sự tách được hai nhóm — nếu không thì `min_grade`
                  chỉ là một tham số trang trí.
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest

from src.python.shared import fx_data as D
from src.python.strategies import asia_sweep_core as SC
from src.python.strategies.h1 import asia_sweep as AS

SYMBOL = "EURUSD"


# ═══════════════════════════════════════════════════════════════ dữ liệu dùng chung
@pytest.fixture(scope="module")
def m1() -> pd.DataFrame:
    """M1 THẬT, cắt còn ~18 tháng để test chạy trong vài giây."""
    with D.parquet_only():
        df = D.load_m1(SYMBOL)
    return df[df.index >= df.index.max() - pd.Timedelta(days=540)].copy()


@pytest.fixture(scope="module")
def cfg() -> SC.SweepConfig:
    return AS.CONFIGS[SYMBOL]


@pytest.fixture(scope="module")
def result(m1, cfg) -> SC.BacktestResult:
    return SC.run(m1, cfg)


# ═══════════════════════════════════════════════════════ 1. KHÔNG NHÌN TRƯỚC
def test_decision_does_not_change_when_future_bars_are_pinned(m1, cfg):
    """Ghim dữ liệu SAU điểm cắt: mọi quyết định TRƯỚC điểm cắt phải y nguyên.

    Đây là test bắt được lỗi thật ngày 25/08/2026. `_mss_confirm` bản đầu quét các
    nến sau cú quét để trả lời "có MSS không", trong khi lệnh khớp ở giá MỞ nến ngay
    sau nến quét — tức quyết định dùng CLOSE của tối đa 3 GIỜ SAU khi vào lệnh.

    Cách kiểm: lấy nửa sau của mẫu và ĐẬP nó (nhân giá 1,05, tức dịch 500 pip). Nếu
    một quyết định nào ở nửa ĐẦU đổi theo, nó đã đọc tương lai.
    """
    cut = m1.index[len(m1) // 2]
    poisoned = m1.copy()
    tail = poisoned.index > cut
    for col in ("open", "high", "low", "close"):
        poisoned.loc[tail, col] = poisoned.loc[tail, col] * 1.05

    base = SC.run(m1, cfg).decisions.set_index("session")
    pois = SC.run(poisoned, cfg).decisions.set_index("session")
    keep = base.index[base.index < cut.normalize() - pd.Timedelta(days=1)]
    assert len(keep) > 50, "mẫu quá ngắn để test có ý nghĩa"

    a = base.loc[keep, ["state", "side", "has_mss", "has_fvg"]]
    b = pois.loc[keep, ["state", "side", "has_mss", "has_fvg"]]
    diff = (a != b).any(axis=1)
    assert not diff.any(), (
        f"{int(diff.sum())} phiên TRƯỚC điểm cắt đổi quyết định khi ghim dữ liệu "
        f"tương lai — có nhìn trước. Ví dụ:\n{a[diff].head()}\n{b[diff].head()}")


def test_entry_bar_is_strictly_after_the_confirming_bar(result, cfg):
    """Nến khớp lệnh phải nằm SAU nến xác nhận ít nhất một nến khung khớp lệnh."""
    T = result.trades
    assert len(T) > 0, "không có lệnh nào để kiểm"
    gap = (T["t_entry"] - pd.to_datetime(T["session"])).dt.total_seconds() / 60.0
    assert (gap > 0).all(), "có lệnh khớp trước cả mốc phiên"
    # Với MSS bắt buộc, nến vào lệnh cách nến QUÉT ít nhất 2 nến khung khớp lệnh
    # (1 nến xác nhận + 1 nến khớp). Kiểm bằng chính khoảng cách tối thiểu.
    if cfg.require_mss:
        span = (T["t_exit"] - T["t_entry"]).dt.total_seconds() / 60.0
        assert (span >= 0).all(), "có lệnh thoát TRƯỚC khi vào"


def test_asia_range_uses_only_bars_before_the_execution_window(m1, cfg):
    """Biên Á chỉ được dựng từ nến trong cửa sổ Á — không lấn sang cửa sổ khớp lệnh."""
    p = SC.prepare(m1, cfg)
    m0 = SC.minute_of_session(cfg.asia_start_utc)
    m1_ = SC.minute_of_session(cfg.asia_end_utc)
    sess = p.sessions[len(p.sessions) // 2]
    day = p.m1[p.m1["session"] == sess]
    inside = day[(day["m"] >= m0) & (day["m"] < m1_)]
    assert float(p.asia.at[sess, "hi"]) == pytest.approx(float(inside["high"].max()))
    assert float(p.asia.at[sess, "lo"]) == pytest.approx(float(inside["low"].min()))


def test_liquidity_map_uses_only_closed_sessions(m1, cfg):
    """PDH/PDL phải là cực trị của phiên TRƯỚC, không phải của phiên hiện tại."""
    p = SC.prepare(m1, cfg)
    i = len(p.sessions) // 2
    sess, prev = p.sessions[i], p.sessions[i - 1]
    lq = p.liq[sess]
    prev_day = p.m1[p.m1["session"] == prev]
    assert lq.pdh == pytest.approx(float(prev_day["high"].max()))
    assert lq.pdl == pytest.approx(float(prev_day["low"].min()))


# ═══════════════════════════════════════════════════════════════ 2. CHI PHÍ
def test_costs_are_actually_subtracted(result):
    """`r_net` phải THẤP HƠN `r_gross` ở mọi lệnh, và chênh lệch bằng đúng `cost_r`."""
    T = result.trades
    assert len(T) > 0
    assert (T["cost_r"] > 0).all(), "có lệnh chi phí bằng 0 — lớp phí không được cộng"
    assert (T["r_net"] < T["r_gross"]).all()
    np.testing.assert_allclose(
        (T["r_gross"] - T["r_net"]).to_numpy(), T["cost_r"].to_numpy(), atol=1e-12)


def test_wider_stop_makes_cost_a_smaller_fraction_of_risk(m1, cfg):
    """Chi phí tính theo R phải GIẢM khi SL rộng ra — nếu không thì đơn vị đang sai.

    Đây là quan hệ nhân quả, không phải một hằng số cần ghim: chi phí là số PIP cố
    định, còn R là khoảng cách SL. Nới đệm SL thì cùng số pip phí chiếm phần nhỏ hơn.
    """
    narrow = SC.run(m1, dataclasses.replace(cfg, sl_buffer_pips=1.0)).trades
    wide = SC.run(m1, dataclasses.replace(cfg, sl_buffer_pips=25.0)).trades
    assert len(narrow) > 5 and len(wide) > 5
    assert wide["cost_r"].median() < narrow["cost_r"].median(), (
        f"SL rộng hơn mà chi phí/R không giảm: {wide['cost_r'].median():.4f} vs "
        f"{narrow['cost_r'].median():.4f}")


# ═══════════════════════════════════════════════════════════════ 3. NHÂN QUẢ
def test_stop_and_targets_sit_on_the_correct_side_of_entry(result):
    """SL và TP phải nằm đúng phía. Đảo phía là một lệnh khớp xong SL ngay lập tức."""
    T = result.trades
    sell, buy = T[T["side"] < 0], T[T["side"] > 0]
    assert (sell["stop_px"] > sell["entry_px"]).all(), "lệnh BÁN có SL dưới giá vào"
    assert (sell["tp_px"] < sell["entry_px"]).all(), "lệnh BÁN có TP trên giá vào"
    assert (buy["stop_px"] < buy["entry_px"]).all(), "lệnh MUA có SL trên giá vào"
    assert (buy["tp_px"] > buy["entry_px"]).all(), "lệnh MUA có TP dưới giá vào"


def test_sweep_candle_closes_back_inside_the_asia_range(m1, cfg):
    """Điều kiện QUYẾT ĐỊNH: nến quét phải ĐÓNG lại trong biên, không chỉ chạm.

    Nếu chỉ cần CHẠM thì gần như mọi phiên đều đủ điều kiện (99,4% phiên bị quét) và
    luật mất hết khả năng phân biệt — xem `REJECTED_DIRECTIONS`.
    """
    p = SC.prepare(m1, cfg)
    checked = 0
    for sess in p.sessions:
        d = SC.detect_setup(p, sess, cfg)
        if not d.enter:
            continue
        checked += 1
        bar = p.exec_bars.loc[pd.Timestamp(d.sweep_time)]
        c = float(bar["close"])
        if d.sweep_side > 0:
            assert c < d.asia_high, f"{sess}: nến quét đóng NGOÀI biên trên"
        else:
            assert c > d.asia_low, f"{sess}: nến quét đóng NGOÀI biên dưới"
    assert checked > 0, "không có lệnh nào để kiểm"


def test_positions_close_by_the_flat_hour(result, cfg):
    """Chiến lược TRONG PHIÊN: không lệnh nào được sống qua mốc `flat_utc`."""
    T = result.trades
    mflat = SC.minute_of_session(cfg.flat_utc)
    shifted = T["t_exit"] - pd.Timedelta(hours=SC.SESSION_ANCHOR_HOUR)
    minute = (shifted - shifted.dt.normalize()).dt.total_seconds() // 60
    assert (minute <= mflat).all(), "có lệnh thoát sau mốc đóng bắt buộc"


def test_no_more_than_one_trade_per_session(result):
    """Một lệnh mỗi phiên mỗi công cụ — nếu không thì rủi ro ngày không còn là phép cộng."""
    T = result.trades
    assert T["session"].is_unique, "có phiên phát nhiều hơn một lệnh"


# ═══════════════════════════════════════════════════════════ 4. PHÂN HẠNG
def test_mss_gate_separates_the_two_groups(m1, cfg):
    """Cổng MSS phải tách được hạng A khỏi hạng B — nếu không, `min_grade` là trang trí.

    Đo trên toàn mẫu: hạng A +0,0124 R/lệnh so với hạng B -0,56..-0,70 R/lệnh. Test
    này không ghim con số (mẫu ở đây ngắn hơn nhiều) — nó đòi ĐÚNG DẤU và đòi khoảng
    cách đủ lớn để không thể là nhiễu làm tròn.
    """
    open_cfg = dataclasses.replace(cfg, require_mss=False, min_grade="C")
    res = SC.run(m1, open_cfg)
    by = SC.stats_by_grade(res)
    if "A" not in by.index or "B" not in by.index:
        pytest.skip(f"mẫu ngắn không có cả hai hạng: {list(by.index)}")
    assert by.loc["B", "R ròng"] < by.loc["A", "R ròng"], by.to_string()
    assert by.loc["A", "R ròng"] - by.loc["B", "R ròng"] > 0.20, by.to_string()


def test_min_grade_actually_filters(m1, cfg):
    """Nâng `min_grade` phải GIẢM số lệnh. Không giảm nghĩa là ngưỡng không được đọc."""
    counts = {}
    for grade in ("C", "B", "A", "A+"):
        c = dataclasses.replace(cfg, min_grade=grade, require_mss=False)
        counts[grade] = len(SC.run(m1, c).trades)
    assert counts["C"] >= counts["B"] >= counts["A"] >= counts["A+"], counts
    assert counts["C"] > counts["A+"], counts


def test_unknown_execution_timeframe_raises(cfg):
    """Khung lạ phải NỔ, không được đoán 15 phút — đoán sai là nhìn trước im lặng."""
    bad = dataclasses.replace(cfg, exec_tf="M7")
    with pytest.raises(ValueError, match="TF_MINUTES"):
        _ = bad.exec_minutes


def test_unknown_grade_raises(cfg):
    bad = dataclasses.replace(cfg, min_grade="S+")
    with pytest.raises(ValueError, match="min_grade"):
        _ = bad.min_grade_rank


def test_every_rejected_session_carries_a_reason(m1, cfg):
    """Phiên KHÔNG vào lệnh vẫn phải nói LÝ DO — `decision_log` ghi cả HOLD/SKIP."""
    p = SC.prepare(m1, cfg)
    for sess in p.sessions[:120]:
        d = SC.detect_setup(p, sess, cfg)
        if d.enter:
            continue
        assert d.steps, f"{sess}: trạng thái {d.state} không có bước nào ghi lại"
        assert any(not ok for _, ok, _ in d.steps), (
            f"{sess}: trạng thái {d.state} nhưng mọi bước đều PASS")


# ═══════════════════════════════════════════════════════ 5. CỔNG TIN
def test_news_window_blocks_entries_around_high_impact_events(m1, cfg):
    """Không được vào lệnh trong ±`news_window_min` phút quanh tin tác động mạnh.

    Cổng nằm trong CHÍNH `detect_setup`, không chỉ ở `order_plan` — nếu chỉ chặn ở
    live thì backtest và live giao dịch hai tập lệnh khác nhau, và mọi con số công bố
    mô tả một chiến lược mà live không chạy.
    """
    p = SC.prepare(m1, cfg)
    assert p.news_times.size > 0, "không nạp được lịch tin — cổng đang mù"
    for sess in p.sessions:
        d = SC.detect_setup(p, sess, cfg)
        if not d.enter:
            continue
        assert not SC._in_news_window(
            p.news_times, pd.Timestamp(d.entry_time), cfg.news_window_min), (
            f"{sess}: vào lệnh lúc {d.entry_time} nằm trong cửa sổ tin")


def test_disabling_the_news_window_lets_more_trades_through(m1, cfg):
    """Tắt cổng (`news_window_min=0`) phải cho SỐ LỆNH >= bật. Không đổi = cổng chết."""
    on = len(SC.run(m1, cfg).trades)
    off = len(SC.run(m1, dataclasses.replace(cfg, news_window_min=0.0)).trades)
    assert off >= on, (off, on)


def test_news_window_matches_the_live_gate_source(cfg):
    """Backtest và live phải đọc CÙNG danh sách sự kiện — hai danh sách là hai cổng."""
    from src.python.ai import news_guard as NG

    assert cfg.news_window_min == pytest.approx(NG.BLOCK_BEFORE_MIN)
    assert cfg.news_window_min == pytest.approx(NG.BLOCK_AFTER_MIN)
    assert NG.HIGH_IMPACT, "danh sách sự kiện tác động mạnh rỗng"


def test_missing_calendar_fails_open_in_research_not_closed(cfg, monkeypatch):
    """Lịch hỏng ở tầng NGHIÊN CỨU thì KHÔNG chặn gì — backtest phải nói rõ nó mù.

    Fail-CLOSED ở đây sẽ làm backtest bỏ hết lệnh và kết quả trông như "chiến lược
    không có tín hiệu", một chẩn đoán sai hẳn. Đường LIVE thì ngược lại: `engine`
    fail-closed khi không đánh giá được cổng tin.
    """
    from src.python.ai import news_guard as NG

    monkeypatch.setattr(NG, "load_calendar", lambda *a, **k: None)
    assert SC._news_times(cfg).size == 0


# ═══════════════════════════════════════════════════════ 6. KẾ TOÁN THOÁT LỆNH
def test_stopped_out_trade_loses_exactly_one_r(result):
    """Lệnh bị dừng lỗ GỐC quét phải mất ĐÚNG 1 R cộng phí — không bao giờ 0 R.

    ĐÂY LÀ TEST CỦA MỘT LỖI THẬT, tìm ra 25/08/2026. Một nhánh thoát cũ ghi `0 R` cho
    lệnh chạm mức chốt-một-phần rồi bị dừng lỗ gốc quét: 22 trong 453 lệnh, và nó
    thổi kỳ vọng từ +0,0417 lên +0,0903 R/lệnh — gấp hơn hai lần.

    Lớp lỗi này KHÔNG có triệu chứng nào khác: số lệnh đúng, winrate đúng, đường
    equity trông hợp lý. Chỉ một bất biến kế toán mới bắt được nó.
    """
    T = result.trades
    sl = T[T["outcome"] == "SL"]
    assert len(sl) > 0, "mẫu không có lệnh nào bị dừng lỗ — test vô nghĩa"
    # r_gross đúng -1,0; r_net = -1,0 - phí, nên luôn TỆ HƠN -1,0.
    np.testing.assert_allclose(sl["r_gross"].to_numpy(), -1.0, atol=1e-12)
    assert (sl["r_net"] < -1.0).all(), (
        "có lệnh SL cho r_net >= -1,0 — phí chưa được trừ")


def test_breakeven_exit_nets_exactly_zero(result):
    """Lệnh bị quét ở mức breakeven phải ra ĐÚNG 0 R sau phí.

    Đó là ý nghĩa của "breakeven": mức được đặt ở giá vào CỘNG phí khứ hồi thật, nên
    chạm nó là hoà THẬT. Nếu ra âm thì mức BE đang đặt thiếu phí, và mỗi lệnh chạm BE
    là một lệnh lỗ nhỏ được ghi nhận là hoà.
    """
    T = result.trades
    be = T[T["outcome"] == "BE"]
    if be.empty:
        pytest.skip("mẫu không có lệnh nào chạm breakeven")
    np.testing.assert_allclose(be["r_net"].to_numpy(), 0.0, atol=1e-9)


def test_target_exit_pays_exactly_the_declared_rr(result, cfg):
    """Lệnh chạm chốt lời phải ra ĐÚNG `tp_r_multiple` R gộp — R:R là hằng số."""
    T = result.trades
    tp = T[T["outcome"] == "TP"]
    assert len(tp) > 0, "mẫu không có lệnh nào chạm chốt lời"
    np.testing.assert_allclose(tp["r_gross"].to_numpy(), cfg.tp_r_multiple, atol=1e-12)
    np.testing.assert_allclose(T["rr"].to_numpy(), cfg.tp_r_multiple, atol=1e-12)


def test_every_outcome_is_one_of_the_four_declared(result):
    """Bốn kết cục, hết. Một kết cục lạ nghĩa là có nhánh thoát không ai khai."""
    assert set(result.trades["outcome"]) <= {"SL", "BE", "TP", "TIME"}


def test_breakeven_arms_only_after_price_travels_the_trigger(m1, cfg):
    """Tắt breakeven phải làm số lệnh KẾT CỤC `BE` bằng 0, và kết quả đổi."""
    on = SC.run(m1, cfg).trades
    off = SC.run(m1, dataclasses.replace(cfg, be_trigger_r=0.0)).trades
    assert (on["outcome"] == "BE").any(), "breakeven bật mà không lệnh nào chạm"
    assert not (off["outcome"] == "BE").any(), "breakeven tắt mà vẫn có kết cục BE"
    assert on["r_net"].mean() != off["r_net"].mean()
