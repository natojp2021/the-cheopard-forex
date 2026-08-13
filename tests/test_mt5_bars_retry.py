# -*- coding: utf-8 -*-
"""`copy_rates_retry` — clone từ `market_guards` của hệ XAUUSD.

VÌ SAO PORT
============
Nhật ký XAUUSD ngày 03/08/2026: `copy_rates_from_pos` hỏng **90 lần trong một
ngày**, riêng một chiến lược 40 lần trên ~288 chu kỳ — tức **14% số lần kiểm tín
hiệu không bao giờ chạy**, âm thầm. Gom theo cửa sổ 60 giây được 51 cụm, và các cụm
lớn có nhiều chiến lược KHÁC NHAU cùng hỏng trên CÙNG symbol cùng lúc → nguyên nhân
ở TERMINAL, và là thoáng qua.

Bản Forex trước đây gọi đúng MỘT lần rồi lùi về parquet lịch sử — tức mỗi lần
terminal chớp tắt là một chu kỳ chạy trên dữ liệu cũ.

Bốn bất biến dưới đây là bốn thứ khiến bản gốc dùng được, và mỗi thứ đều từng là
một lỗi thật ở đâu đó.
"""
from __future__ import annotations

import pytest

from src.python.shared import mt5_bars as MB


class _FakeMT5:
    """Trả `seq[i]` cho lần gọi thứ i. `Exception` trong seq nghĩa là NÉM."""

    TIMEFRAME_M1 = 1        # hằng số mà `_timeframe_const` tra cứu

    def __init__(self, seq):
        self.seq = list(seq)
        self.calls = 0

    def symbol_select(self, symbol, enable=True):
        return True

    def copy_rates_from_pos(self, symbol, tf, start, count):
        v = self.seq[min(self.calls, len(self.seq) - 1)]
        self.calls += 1
        if isinstance(v, Exception):
            raise v
        return v


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    """Không ngủ thật — test này kiểm LUẬT thử lại, không kiểm đồng hồ."""
    monkeypatch.setattr("time.sleep", lambda *_: None)
    monkeypatch.setattr(MB, "_fetch_retry_stats",
                        {"lan_hong": 0, "cuu_duoc": 0, "ngoai_le": 0},
                        raising=False)
    monkeypatch.setattr(MB, "_fetch_failure_last_logged", {}, raising=False)


def _real_clock(monkeypatch):
    from src.python.core.infra import clock

    monkeypatch.setattr(clock, "get_clock", lambda: clock.RealClock())


def test_retry_rescues_a_transient_failure(monkeypatch):
    """Lần đầu rỗng, lần hai có nến → phải TRẢ NẾN, không bỏ chu kỳ."""
    _real_clock(monkeypatch)
    fake = _FakeMT5([None, [1, 2, 3]])
    out = MB.copy_rates_retry(fake, "EURUSD", 1, 100, tag="T", min_bars=1)
    assert out == [1, 2, 3]
    assert fake.calls == 2
    assert MB._fetch_retry_stats["cuu_duoc"] == 1


def test_exception_is_caught_not_propagated(monkeypatch):
    """`copy_rates_from_pos` NÉM cũng phải vào được vòng thử lại.

    Bản đầu bên XAUUSD không bọc `try`, nên ngoại lệ bay thẳng ra và làm gãy CẢ CHU
    KỲ — vòng thử lại nằm ngay bên dưới nhưng không bao giờ chạy tới.
    """
    _real_clock(monkeypatch)
    fake = _FakeMT5([RuntimeError("IPC vỡ"), [9]])
    out = MB.copy_rates_retry(fake, "EURUSD", 1, 100, tag="T", min_bars=1)
    assert out == [9], "ngoại lệ làm gãy vòng thử lại"
    assert MB._fetch_retry_stats["ngoai_le"] == 1


def test_no_retry_and_no_sleep_in_backtest(monkeypatch):
    """Đồng hồ ẢO → trả None NGAY. Giữ parity và không treo backtest.

    Dữ liệu backtest tất định nên gọi lại chắc chắn ra cùng kết quả; `sleep` trong
    hàng chục nghìn chu kỳ sẽ treo cả lượt chạy.
    """
    from src.python.core.infra import clock

    monkeypatch.setattr(clock, "get_clock", lambda: clock.VirtualClock())
    slept = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))

    fake = _FakeMT5([None, [1]])
    assert MB.copy_rates_retry(fake, "EURUSD", 1, 100, tag="T", min_bars=1) is None
    assert fake.calls == 1, "đã thử lại trong backtest — phá parity"
    assert not slept, "đã ngủ trong backtest — sẽ treo vòng lặp"


def test_gives_up_after_all_waits(monkeypatch):
    """Hỏng suốt thì trả None sau đúng số lần đã khai — không thử vô hạn."""
    _real_clock(monkeypatch)
    fake = _FakeMT5([None])
    assert MB.copy_rates_retry(fake, "EURUSD", 1, 100, tag="T", min_bars=1,
                               wait_seconds=(0.1, 0.2)) is None
    assert fake.calls == 3, f"gọi {fake.calls} lần, phải là 1 + 2"


def test_failure_log_is_throttled_per_symbol(monkeypatch):
    """Lỗi kéo dài không được lấp nhật ký, nhưng KHÔNG BAO GIỜ im hoàn toàn."""
    msgs = []
    import src.python.utils.logger as L

    monkeypatch.setattr(L, "log_error", lambda m, *a: msgs.append(m))

    for _ in range(10):
        MB.log_fetch_failure_throttled("T", "EURUSD", "rỗng")
    assert len(msgs) == 1, f"kêu {len(msgs)} lần cho cùng (tag, symbol)"

    MB.log_fetch_failure_throttled("T", "GBPUSD", "rỗng")
    assert len(msgs) == 2, "chặn lặp phải theo TỪNG symbol"


def test_load_m1_uses_retry(monkeypatch):
    """`load_m1` phải đi qua `copy_rates_retry`, không gọi thẳng một lần."""
    seen = {}

    def _spy(mt5, symbol, tf, count, *, tag, min_bars=None, **kw):
        seen.update(symbol=symbol, tag=tag, min_bars=min_bars)
        return None

    monkeypatch.setattr(MB, "copy_rates_retry", _spy)
    assert MB.load_m1("EURUSD", _FakeMT5([None])) is None
    assert seen["symbol"] == "EURUSD"
    assert seen["min_bars"] == 1, (
        "đòi đủ n_bars sẽ coi terminal mới tải được vài nghìn nến là HỎNG và ném "
        "đi toàn bộ số nến đó")
