# -*- coding: utf-8 -*-
"""HAI NGUỒN SPAM VÀ MỘT LỖI VĨNH VIỄN — sửa từ gốc, có test ghim.

Nhật ký VPS ngày 18/08/2026 chứa đúng ba bệnh, và chúng khác nhau về bản chất:

  1. CỔNG SPREAD — ~590 dòng trong 49 phút. Dấu vân tay khử lặp chứa chính các con số
     đổi mỗi tick, nên hai lớp khử lặp đã có đều vô hiệu.
  2. BẢNG SPREAD — 28 dòng mỗi 30 phút = 1.344 dòng/ngày. Không phải lỗi: đó là một
     phép đo cần thiết bị đặt sai chỗ (console thay vì sổ).
  3. `[FX-M1]` EURUSD — ba dòng lỗi mỗi giờ, suốt cả ngày, KHÔNG BAO GIỜ tự khỏi.
     Đây là lỗi thật, và hai bệnh trên che nó: một dòng lỗi lặp mãi giữa 590 dòng ồn
     thì không ai đọc.

Điểm chung đáng ghi lại: cả ba đều là lỗi của TẦNG QUAN SÁT, không phải của logic
giao dịch — và chính vì thế chúng sống lâu. Không có test nào từng đo "log có đọc
được không".
"""
from __future__ import annotations

import pytest


# ═════════════════════════════════════════ 1. cổng spread: dedup theo trạng thái
class _FakeEngine:
    """Chỉ đủ phần engine mà `_log_spread_gate` chạm tới.

    Dựng lớp giả thay vì `TradingEngine` thật vì engine thật nối MT5 lúc khởi tạo.
    Hàm được kiểm là hàm THẬT — nó được gắn vào lớp giả qua `__get__`, nên test đo
    đúng code sẽ chạy trên VPS, không đo một bản chép lại.
    """

    _SPREAD_STEP = None
    _SPREAD_REMIND = None

    def __init__(self, total: int = 27):
        from src.python.core.engine import TradingEngine

        self.lines: list = []
        self._spread_over_n = 0
        self._spread_logged_at = 0.0
        self.state = {"spread": {f"SYM{i}": 1.0 for i in range(total)}}
        self._SPREAD_STEP = TradingEngine._SPREAD_STEP
        self._SPREAD_REMIND = TradingEngine._SPREAD_REMIND
        self._fn = TradingEngine._log_spread_gate.__get__(self, _FakeEngine)

    def log(self, msg):
        self.lines.append(msg)

    def gate(self, over: dict):
        self._fn({"cap_bps": 3.0, "over": over})


def _over(n: int, base: float = 7.0) -> dict:
    return {f"SYM{i}": base + i * 0.11 for i in range(n)}


def test_spread_gate_logs_once_when_the_episode_starts(monkeypatch):
    """Vào trạng thái giãn -> ĐÚNG một dòng, kèm số đếm và ba cái tệ nhất."""
    e = _FakeEngine()
    e.gate(_over(20))
    assert len(e.lines) == 1, e.lines
    line = e.lines[0]
    assert "20/27 công cụ" in line
    assert "tệ nhất" in line
    # Danh sách đầy đủ 20 tên KHÔNG được lên console — nó nằm ở thẻ GUARD và sổ JSONL.
    assert line.count("SYM") <= 3, f"vẫn liệt kê cả rổ: {line}"


def test_spread_gate_stays_silent_while_only_the_numbers_move(monkeypatch):
    """ĐÂY LÀ BẤT BIẾN TRUNG TÂM: 590 nhịp mà số công cụ không đổi -> vẫn một dòng.

    Bản cũ dedup theo `str(sorted(over.items()))`, tức dấu vân tay chứa cả giá trị
    bps. Giá trị đó đổi mỗi tick, nên vân tay đổi mỗi tick, nên lớp khử lặp không bao
    giờ khớp — 590 dòng trong 49 phút.
    """
    import time as _time

    e = _FakeEngine()
    now = [1000.0]
    monkeypatch.setattr(_time, "time", lambda: now[0])
    e.gate(_over(20))
    for i in range(590):
        now[0] += 5.0
        # Cùng 20 công cụ, giá trị bps nhảy loạn — đúng hình dạng dữ liệu thật.
        e.gate(_over(20, base=7.0 + (i % 17) * 0.3))
    # Chỉ được thêm các dòng NHẮC LẠI theo `_SPREAD_REMIND` (15 phút), không hơn.
    expected = 1 + (590 * 5.0) / e._SPREAD_REMIND
    assert len(e.lines) <= expected + 1, f"{len(e.lines)} dòng: {e.lines[:3]}"
    assert 590 / len(e.lines) > 50, f"chỉ giảm {590 / len(e.lines):.0f} lần"


def test_spread_gate_speaks_up_when_the_count_changes_materially(monkeypatch):
    """3 công cụ giãn và 24 công cụ giãn là hai tình huống KHÁC NHAU — phải nói.

    Nén theo trạng thái mà không có ngưỡng này thì một đợt xấu dần từ 3 lên 24 công
    cụ đi qua hoàn toàn im lặng.
    """
    import time as _time

    e = _FakeEngine()
    monkeypatch.setattr(_time, "time", lambda: 1000.0)
    e.gate(_over(3))
    e.gate(_over(3))
    assert len(e.lines) == 1
    e.gate(_over(3 + e._SPREAD_STEP))
    assert len(e.lines) == 2, "số công cụ nhảy một bậc mà không báo"


def test_spread_gate_does_not_drift_through_the_threshold(monkeypatch):
    """Mốc so sánh là LẦN GHI gần nhất, không phải nhịp gần nhất.

    Cập nhật số đếm mỗi nhịp sẽ để một chuỗi +1 liên tiếp trôi từ 3 lên 24 công cụ mà
    không nhịp nào vượt ngưỡng "đổi đáng kể" — tức im lặng đúng lúc tình hình xấu dần.
    Đây là chỗ một bản vá chống spam làm mất đúng thông tin nó phải giữ.
    """
    import time as _time

    e = _FakeEngine()
    monkeypatch.setattr(_time, "time", lambda: 1000.0)
    e.gate(_over(3))
    for n in range(4, 25):
        e.gate(_over(n))
    assert len(e.lines) >= 2, "trôi qua ngưỡng mà không có dòng nào"


def test_spread_gate_reports_recovery_with_the_previous_count(monkeypatch):
    """Ra khỏi trạng thái giãn phải có dòng, và nó phải nói vừa rồi bao nhiêu công cụ."""
    import time as _time

    e = _FakeEngine()
    monkeypatch.setattr(_time, "time", lambda: 1000.0)
    e.gate(_over(20))
    e.gate({})
    assert "đã về dưới trần" in e.lines[-1]
    assert "20" in e.lines[-1], e.lines[-1]


def test_spread_gate_silent_when_it_was_never_wide(monkeypatch):
    """Chưa từng giãn thì KHÔNG được báo "đã về dưới trần".

    Bản trước truyền `{}` vào cổng lúc thị trường đóng và sinh ra dòng vô nghĩa
    "spread mọi công cụ đã về dưới trần None bps" ngay khi thị trường vừa đóng — một
    chuyển-trạng-thái GIẢ do chính cách bỏ qua tạo ra.
    """
    import time as _time

    e = _FakeEngine()
    monkeypatch.setattr(_time, "time", lambda: 1000.0)
    e.gate({})
    assert e.lines == []


# ═════════════════════════════════════════ 2. bảng spread: số liệu vào sổ, không lên console
def test_spread_survey_keeps_every_instrument_in_the_ledger():
    """Console nhận 1 dòng; sổ JSONL phải giữ ĐỦ 27 công cụ.

    Cắt bớt số liệu ở đây là phá phép đo dựng nên phân phối chi phí thật của 21 cặp
    chéo — giả định lớn nhất còn lại của cả hệ. Việc cần làm là đổi CHỖ ĐẶT, không
    phải giảm dữ liệu.
    """
    from src.python.utils import ops_log

    assert "spread_survey" in _engine_source(), (
        "engine không còn ghi bảng spread vào sổ — phép đo chi phí chéo đã mất")
    assert "logs/market" in _engine_source() or "market" in ops_log.CATEGORIES


def _engine_source() -> str:
    import inspect

    from src.python.core.engine import TradingEngine
    return inspect.getsource(TradingEngine._maybe_log_spread)


def test_spread_survey_prints_a_single_summary_line():
    """Thân hàm chỉ được gọi `self.log` cho DÒNG TÓM TẮT, không lặp qua từng hàng.

    Test đọc mã nguồn chứ không chạy hàm, vì hàm thật cần trạng thái MT5. Điều cần
    ghim là bất biến CẤU TRÚC: không có vòng `for` nào bọc quanh `self.log`.
    """
    body = _engine_source()
    assert "for sym, pips, est, diff in rows:\n            self.log" not in body, (
        "vẫn in từng hàng ra console — 28 dòng mỗi 30 phút quay lại")
    assert body.count("self.log(") <= 2, body.count("self.log(")


# ═════════════════════════════════════════ 3. FX-M1: giảm dần số nến
class _FakeMT5:
    """Terminal chỉ có `available` nến — xin nhiều hơn thì trả rỗng.

    Đây là hành vi đã suy ra từ nhật ký: `copy_rates_from_pos(..., 0, 200000)` trả
    0/1 bar cho EURUSD suốt cả ngày trong khi `symbol_info_tick` vẫn chạy (spread đọc
    được bình thường), tức symbol tồn tại và terminal có nối — nó chỉ không có đủ
    lịch sử ở mức đang xin.
    """

    TIMEFRAME_M1 = 1

    def __init__(self, available: int):
        self.available = available
        self.asked: list = []

    def symbol_select(self, *_a, **_k):
        return True

    def symbol_info(self, _s):
        class _I:
            point = 1e-5
        return _I()

    def copy_rates_from_pos(self, _sym, _tf, _start, count):
        self.asked.append(count)
        if count > self.available:
            return []
        import numpy as np

        return np.zeros(count, dtype=[("time", "i8"), ("open", "f8"),
                                      ("high", "f8"), ("low", "f8"),
                                      ("close", "f8"), ("tick_volume", "i8"),
                                      ("spread", "i8")])


def test_degrading_fetch_succeeds_when_terminal_has_partial_history():
    """LỖI GỐC của ba dòng lỗi mỗi giờ: vòng thử lại KHÔNG BAO GIỜ xin ít hơn.

    Bản cũ lặp lại đúng một yêu cầu 200.000 nến sau 0,3s rồi 1,0s. Nó chữa được sự cố
    THOÁNG QUA (đúng thứ nó sinh ra để chữa) nhưng ở đây nguyên nhân không thoáng qua:
    terminal chỉ đơn giản không có 200.000 nến. Xin lại cùng con số thì lần nào cũng
    hỏng, mãi mãi.

    Trái khoáy nhất: hàm khai `min_bars=1` — nó nói rõ "chỉ cần biết CÓ nến hay
    không" — mà không bao giờ thử xin ít hơn. Yêu cầu và điều kiện chấp nhận lệch
    nhau 200.000 lần.
    """
    from src.python.shared import mt5_bars

    mt5 = _FakeMT5(available=10_000)
    df = mt5_bars.load_m1("EURUSD", mt5=mt5)
    assert df is not None and not df.empty, "vẫn hỏng dù terminal có 10.000 nến"
    assert mt5.asked[0] == mt5_bars.DEFAULT_BARS, "không thử mức đầy đủ trước"
    assert mt5.asked[-1] <= 10_000, mt5.asked


def test_degrading_fetch_gives_up_cleanly_when_there_is_nothing():
    """Không có nến nào thì trả `None` — không ném, và đã thử hết các bậc.

    Số lần gọi cũng bị ghim. Bản đầu để MỌI bậc tự thử lại ba lượt, cho ra 12 lần gọi
    và ~5,2 giây `sleep` cho một lượt hỏng hoàn toàn — nhân bảy công cụ là 36 giây
    chặn một vòng lặp có nhịp 5 giây. Chờ rồi xin LẠI đúng con số vừa hỏng vì thiếu
    lịch sử không mang thêm thông tin nào, nên các bậc GIỮA không chờ.
    """
    from src.python.shared import mt5_bars

    mt5 = _FakeMT5(available=0)
    assert mt5_bars.load_m1("EURUSD", mt5=mt5) is None
    # bậc đầu 3 lượt · hai bậc giữa 1 lượt · bậc cuối 3 lượt
    assert len(mt5.asked) == 3 + (len(mt5_bars.DEGRADE_BARS) - 2) + 3, mt5.asked
    assert sorted(set(mt5.asked), reverse=True) == list(mt5_bars.DEGRADE_BARS)


def test_degrade_steps_go_down_and_reach_a_usable_floor():
    """Các bậc phải GIẢM dần, và bậc cuối vẫn đủ dùng cho chân ngắn.

    Bậc cuối quá cao thì cơ chế vô dụng với terminal mới cài; quá thấp thì hệ chạy
    trên mẫu không đủ cho bất kỳ chân nào mà vẫn tưởng đã có dữ liệu.
    """
    from src.python.shared import mt5_bars

    steps = list(mt5_bars.DEGRADE_BARS)
    assert steps == sorted(steps, reverse=True), steps
    assert steps[0] == mt5_bars.DEFAULT_BARS
    assert 1_000 <= steps[-1] <= 6_000, steps[-1]


def test_intermediate_degrade_steps_do_not_each_log_a_failure(monkeypatch):
    """Một sự cố -> một dòng, không phải bốn.

    Không có cờ `quiet` thì lượt giảm-dần bốn bậc sinh bốn dòng lỗi cho cùng một sự
    cố — tức một bản vá chống spam lại làm spam nặng thêm.
    """
    from src.python.shared import mt5_bars

    said: list = []
    monkeypatch.setattr(mt5_bars, "log_fetch_failure_throttled",
                        lambda *a, **k: said.append(a))
    mt5_bars.load_m1("EURUSD", mt5=_FakeMT5(available=0))
    assert len(said) <= 1, f"{len(said)} dòng lỗi cho một sự cố: {said}"


def test_lower_step_success_is_announced_with_the_bar_count(monkeypatch):
    """Chạy được ở bậc thấp thì PHẢI nói rõ đang chạy trên bao nhiêu nến.

    Đây là dòng phân biệt "terminal chưa tải xong lịch sử" với "terminal hỏng". Không
    có nó thì hệ âm thầm quyết định trên mẫu ngắn — cùng họ lỗi với `parquet_only`,
    nơi backtest lặng lẽ chạy trên mẫu ngắn hơn 11 lần mà mọi chỉ số vẫn được báo như
    số toàn mẫu.
    """
    from src.python.utils import logger as L

    said: list = []
    monkeypatch.setattr(L, "log", lambda msg, *a: said.append(str(msg)))
    from src.python.shared import mt5_bars

    mt5_bars.load_m1("EURUSD", mt5=_FakeMT5(available=10_000))
    joined = " ".join(said)
    assert "hạ xuống" in joined, said
    assert "10,000" in joined or "10000" in joined, said
    assert "5.760" in joined, "không nói cửa sổ dài nhất cần bao nhiêu"
