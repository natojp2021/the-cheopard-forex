"""Spread không đo được KHÔNG được phép xoá sạch nến của một công cụ.

SỰ CỐ 20/08/2026 — MỘT CÔNG CỤ HẠ CẢ DANH MỤC 27 CHÂN
======================================================
Bot chạy LIVE với `FX_BARS_FROM_MT5=1`. Nhịp tim báo "MT5 OK · 27/27 chân sẵn
sàng" đều đặn mỗi 45 giây, không có cảnh báo nào. Nhưng không lệnh nào vào được,
mỗi chu kỳ, vì:

    1. `mt5_bars.load_m1_from_mt5("EURUSD")` thấy cột `spread` của nến lịch sử
       toàn 0  ->  đặt `spread_usd = NaN` (có chủ ý: chi phí 0 là dối trá).
    2. `fx_data.build_bars` có `dropna(subset=[..., "spread_usd"])`
       ->  EURUSD: 200.000 nến M1 biến thành **0 nến H1**.
    3. `fx_cross_pairs.build_crosses` gộp 7 cặp USD bằng `DataFrame(px).dropna()`
       ->  một cột rỗng làm GIAO của mọi cột rỗng theo: rổ 20 cross = (0, 20).
    4. `cross_mean_reversion.evaluate_cross` gọi `idx[-1]` trên chỉ mục rỗng
       ->  `IndexError: index -1 is out of bounds for axis 0 with size 0`.
    5. `portfolio.live_targets` ném  ->  `engine._build_plan` ném  ->  **cả 27
       chân đứng im**, và console chỉ in đúng một dòng không có tên tệp.

Ba tầng đều sửa, và ba tầng đều cần: tầng 1 để công cụ không rụng, tầng 4 để một
chân thiếu dữ liệu không kéo theo 26 chân còn lại, tầng 3 để lần sau lỗi tự khai
tên công cụ thay vì bắt người đọc lần ngược năm hàm.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.python.shared import mt5_bars
from src.python.strategies.h1 import cross_mean_reversion as XMR


class _FakeInfo:
    def __init__(self, spread: int) -> None:
        self.spread = spread


def _clear_cache() -> None:
    mt5_bars._LAST_GOOD_SPREAD.clear()


def test_live_spread_used_when_history_spread_is_zero(monkeypatch) -> None:
    """Spread lịch sử = 0 thì lấy spread SỐNG, không trả NaN và cũng không trả 0."""
    _clear_cache()
    import MetaTrader5 as mt5

    monkeypatch.setattr(mt5, "symbol_info", lambda s: _FakeInfo(3), raising=False)
    got = mt5_bars._live_spread_fallback("EURUSD", 1e-5, 200_000)
    assert got == pytest.approx(3e-5)
    # Không bao giờ được là 0: chi phí bằng 0 làm mọi chân "có lãi".
    assert got > 0


def test_zero_live_spread_falls_back_to_last_measured(monkeypatch) -> None:
    """Spread sống chớp về 0 thì giữ số ĐO GẦN NHẤT — vũ trụ giao dịch phải ổn định.

    Đo trên chính tài khoản demo 20/08/2026: `symbol_info("EURUSD").spread` trả
    0 rồi 1 rồi 0 trong vài giây. Không nhớ số cũ thì EURUSD rụng khỏi rổ ở chu
    kỳ này và quay lại ở chu kỳ sau — rổ 20 cross đổi thành phần theo nhịp ngẫu
    nhiên, tức chiến lược chạy trên một vũ trụ không xác định.
    """
    _clear_cache()
    import MetaTrader5 as mt5

    monkeypatch.setattr(mt5, "symbol_info", lambda s: _FakeInfo(2), raising=False)
    first = mt5_bars._live_spread_fallback("EURUSD", 1e-5, 100)
    monkeypatch.setattr(mt5, "symbol_info", lambda s: _FakeInfo(0), raising=False)
    second = mt5_bars._live_spread_fallback("EURUSD", 1e-5, 100)
    assert second == first == pytest.approx(2e-5)


def test_no_measurement_anywhere_returns_nan(monkeypatch) -> None:
    """Hết đường đo thì NaN — mất công cụ còn hơn giao dịch với chi phí bịa ra."""
    _clear_cache()
    import MetaTrader5 as mt5

    monkeypatch.setattr(mt5, "symbol_info", lambda s: _FakeInfo(0), raising=False)
    assert np.isnan(mt5_bars._live_spread_fallback("EURUSD", 1e-5, 100))


def test_empty_price_series_skips_instead_of_raising() -> None:
    """Chân cross không có nến phải trả SKIP, không được ném `IndexError`.

    Đây là lớp chặn quan trọng nhất: nguyên nhân gốc có thể quay lại ở hình dạng
    khác (terminal chưa tải xong lịch sử, công cụ bị gỡ khỏi Market Watch), và
    khi đó MỘT chân thiếu dữ liệu không được phép hạ cả `_build_plan`.
    """
    empty = pd.Series(dtype=float, index=pd.DatetimeIndex([]))
    spec = XMR.CX._spec("EURGBP")
    d = XMR.evaluate_cross("EURGBP", empty, spec, XMR.Config())
    assert d.action == "SKIP"
    assert d.cross == "EURGBP"
    assert "KHÔNG CÓ NẾN" in d.reason


def test_all_nan_price_series_also_skips() -> None:
    """Chuỗi toàn NaN cũng phải SKIP — `dropna()` biến nó thành rỗng."""
    idx = pd.date_range("2026-08-01", periods=50, freq="h")
    d = XMR.evaluate_cross("EURGBP", pd.Series(np.nan, index=idx),
                           XMR.CX._spec("EURGBP"), XMR.Config())
    assert d.action == "SKIP"


def test_fallback_log_is_throttled_not_per_call(monkeypatch) -> None:
    """Trạng thái ổn định chỉ được NÓI một lần, không phải mỗi lần nạp nến.

    Đo 19:14 ngày 20/08/2026: hàm này chạy nhiều lần mỗi giây khi 27 chân cùng
    dựng kế hoạch, và dòng `[SPREAD] EURUSD ...` chiếm 14 trong 15 dòng cuối của
    nhật ký — đẩy sạch dòng có ích ra ngoài màn hình. Nén ở tầng hiển thị không
    cứu được: phải sửa ngay tại ĐIỂM GHI.
    """
    _clear_cache()
    mt5_bars._SPREAD_LOG_AT.clear()
    mt5_bars._SPREAD_LOG_KIND.clear()
    import MetaTrader5 as mt5

    said: list[str] = []
    monkeypatch.setattr(mt5, "symbol_info", lambda s: _FakeInfo(3), raising=False)
    # Bat CA HAI muc: tu 21/08/2026 nhanh "da xu ly dung" ghi bang `log()` chu
    # khong phai `log_error()` (xem test_spread_fallback_20260821_level). Chi dem
    # mot muc thi phep kiem NEN o day am tham do 0 dong va luon xanh.
    monkeypatch.setattr("src.python.utils.logger.log_error",
                        lambda m, *a, **k: said.append(m))
    monkeypatch.setattr("src.python.utils.logger.log",
                        lambda m, *a, **k: said.append(m))
    for _ in range(50):
        mt5_bars._live_spread_fallback("EURUSD", 1e-5, 100)
    assert len(said) == 1, f"50 lần gọi phải cho ĐÚNG 1 dòng, nhận {len(said)}"


def test_state_change_speaks_immediately(monkeypatch) -> None:
    """Chỉ ĐỔI TRẠNG THÁI THẬT mới được phá throttle.

    Hai yêu cầu ngược nhau trong cùng một hàm, và test này giữ cả hai:

      * Mất hẳn nguồn đo phải nói NGAY — bóp nghẹt theo thời gian mà không xét
        trạng thái sẽ giấu đúng lúc cần biết.
      * Spread sống chớp 1/0 KHÔNG phải đổi trạng thái. Bản đầu coi `live` và
        `cached` là hai trạng thái, nên EURUSD (chớp liên tục) phá throttle mỗi
        lần gọi và nhật ký vẫn 2 dòng/giây sau khi đã "sửa".
    """
    _clear_cache()
    mt5_bars._SPREAD_LOG_AT.clear()
    mt5_bars._SPREAD_LOG_KIND.clear()
    import MetaTrader5 as mt5

    said: list[str] = []
    # Bat CA HAI muc: tu 21/08/2026 nhanh "da xu ly dung" ghi bang `log()` chu
    # khong phai `log_error()` (xem test_spread_fallback_20260821_level). Chi dem
    # mot muc thi phep kiem NEN o day am tham do 0 dong va luon xanh.
    monkeypatch.setattr("src.python.utils.logger.log_error",
                        lambda m, *a, **k: said.append(m))
    monkeypatch.setattr("src.python.utils.logger.log",
                        lambda m, *a, **k: said.append(m))
    monkeypatch.setattr(mt5, "symbol_info", lambda s: _FakeInfo(3), raising=False)
    mt5_bars._live_spread_fallback("EURUSD", 1e-5, 100)
    assert len(said) == 1

    # Spread sống chớp về 0 nhưng VẪN còn số đo -> CÙNG trạng thái `measured`,
    # nên KHÔNG được nói thêm dòng nào. Đây chính là chỗ bản đầu nén hụt.
    monkeypatch.setattr(mt5, "symbol_info", lambda s: _FakeInfo(0), raising=False)
    for _ in range(20):
        mt5_bars._live_spread_fallback("EURUSD", 1e-5, 100)
    assert len(said) == 1, f"chớp 1/0 không phải đổi trạng thái, nhận {len(said)} dòng"

    # Mất hẳn nguồn đo THÌ phải nói ngay — đó là đổi trạng thái thật.
    _clear_cache()
    mt5_bars._live_spread_fallback("EURUSD", 1e-5, 100)
    assert len(said) == 2
    assert "KHÔNG đo được" in said[1]
