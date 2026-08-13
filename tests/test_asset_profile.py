"""Kiểm định `asset_profile` — SSOT về pip / contract size / commission.

VÌ SAO ĐÂY LÀ TEST QUAN TRỌNG NHẤT CỦA DỰ ÁN
============================================
Đây là nơi lỗi đơn vị của hệ XAUUSD đã gây thiệt hại thật: `ATR_MIN = 1,50 USD`
lấy từ vàng lớn hơn ~1000 lần ATR H1 của EURUSD, nên nó lọc sạch 100% tín hiệu FX
mà KHÔNG báo lỗi — backtest chạy xong, ra 0 lệnh, và trông như "chiến lược không có
cơ hội" chứ không như một lỗi.

Loại lỗi đó không bị bắt bởi test kiểu "hàm có chạy không". Nó chỉ bị bắt bởi test
kiểm tra ĐỘ LỚN có nằm trong khoảng đúng của thị trường hay không.
"""
from __future__ import annotations

import math

import pytest

from src.python.shared import asset_profile as AP


def test_every_pair_in_fx_all_has_profile():
    for sym in AP.FX_ALL:
        p = AP.get(sym)
        assert p is not None, f"{sym} thiếu profile"
        assert p.pip > 0
        assert p.contract_size > 0


def test_tier1_is_subset_of_fx_all():
    assert set(AP.TIER1) <= set(AP.FX_ALL)
    assert AP.TIER1 == ("EURUSD", "GBPUSD", "USDJPY")


@pytest.mark.parametrize("sym,pip", [
    ("EURUSD", 0.0001), ("GBPUSD", 0.0001), ("AUDUSD", 0.0001),
    ("NZDUSD", 0.0001), ("USDCAD", 0.0001), ("USDCHF", 0.0001),
    ("USDJPY", 0.01),
])
def test_pip_size_matches_pair_family(sym, pip):
    """JPY có pip 0,01; các cặp còn lại 0,0001. Nhầm chỗ này là sai 100 lần."""
    assert AP.get(sym).pip == pytest.approx(pip)


def test_commission_xxxusd_equals_070_pip():
    """Cặp XXXUSD: 7 USD/lô khứ hồi trên 100.000 đơn vị = 0,00007 giá = 0,70 pip.

    Con số này quan trọng vì nó LỚN HƠN spread trung vị của EURUSD (0,31 pip) —
    bỏ qua commission là bỏ qua thành phần chi phí lớn nhất.
    """
    p = AP.get("EURUSD")
    c = p.commission_price_units(1.10)
    assert c == pytest.approx(7.0 / 100_000, rel=1e-6)
    assert c / p.pip == pytest.approx(0.70, rel=1e-6)


def test_commission_usdxxx_depends_on_price():
    """Cặp USDXXX: commission tính bằng tiền yết giá nên PHẢI phụ thuộc giá.

    Nếu ai đó "đơn giản hoá" thành hằng số như nhánh XXXUSD thì USDJPY sẽ sai
    khoảng 150 lần. Test này chốt sự phụ thuộc đó lại.
    """
    p = AP.get("USDJPY")
    c1 = p.commission_price_units(100.0)
    c2 = p.commission_price_units(150.0)
    assert c2 > c1
    assert c2 / c1 == pytest.approx(1.5, rel=1e-6)


def test_commission_in_pips_is_sane_for_every_pair():
    """Commission quy ra pip phải nằm trong [0,3 · 3,0] pip cho MỌI cặp.

    Đây là test bắt lỗi đơn vị: bất kỳ nhầm lẫn giữa pip/point/giá đều đẩy con số
    ra ngoài khoảng này ít nhất một bậc mười.
    """
    px = {"EURUSD": 1.10, "GBPUSD": 1.27, "AUDUSD": 0.66, "NZDUSD": 0.60,
          "USDCAD": 1.36, "USDCHF": 0.88, "USDJPY": 150.0}
    for sym, price in px.items():
        p = AP.get(sym)
        pips = p.commission_price_units(price) / p.pip
        assert 0.3 <= pips <= 3.0, f"{sym}: commission = {pips:.3f} pip — sai đơn vị?"


def test_get_raises_on_unknown_symbol():
    with pytest.raises((KeyError, ValueError)):
        AP.get("XAUUSD")


def test_no_xauusd_leftovers():
    """Hệ này là Forex-only. XAUUSD lọt vào profile là lọt cả bộ tham số của vàng."""
    for sym in AP.FX_ALL:
        assert "XAU" not in sym and "XAG" not in sym


# ── Ba mặc định của hệ vàng đã lọt qua đợt port và chỉ bị phát hiện 14/08/2026.
# Ba test dưới ghim đúng ba chỗ đó. Chúng KHÔNG kiểm "có nhắc tới XAU không" —
# docstring của repo cố ý nhắc rất nhiều để giải thích vì sao làm khác. Chúng kiểm
# **giá trị mặc định và hằng số ĐANG CHẠY** có còn là số của vàng hay không.

def test_no_canonical_m1_pointing_at_gold():
    """`paths.CANONICAL_M1` trỏ `xauusd_m1.parquet` — file không tồn tại ở repo này.

    Hệ Forex không có MỘT chuỗi canonical: nó đọc 7 file M1 theo cặp qua
    `fx_data.load_m1()`. Để hằng số cũ lại là mời người viết
    `pd.read_parquet(CANONICAL_M1)` rồi nhận FileNotFoundError ở chỗ không ngờ.
    """
    from src.python.shared import paths

    assert not hasattr(paths, "CANONICAL_M1")


def test_latest_hard_regime_requires_explicit_symbol():
    """Không được có mặc định `symbol="XAUUSD"`: gọi thiếu tham số phải BÁO LỖI.

    Mặc định im lặng trả về trạng thái của một công cụ không giao dịch là kiểu
    hỏng tệ nhất — nó trả về số, và số đó trông hợp lệ.
    """
    import inspect

    from src.python.shared import regime_taxonomy as RT

    sig = inspect.signature(RT.latest_hard_regime)
    default = sig.parameters["symbol"].default
    assert default is inspect.Parameter.empty, f"symbol vẫn có mặc định {default!r}"


def test_gap_threshold_measured_on_fx_not_gold():
    """Ngưỡng cảnh báo notional phải suy từ rổ FX, không từ gap 2,539% của vàng.

    Con số cũ 1,97x sai hai lần: sai tài sản (gap tệ nhất FX đo được 2,138%, không
    phải 2,539%) và sai khung quy chiếu (công thức giả định toàn bộ notional nằm
    trên MỘT công cụ — đúng với hệ một tài sản, vô nghĩa với sổ 27 chân hai chiều).
    Đo ở mức danh mục: thứ Hai là ngày an toàn nhất tuần, không phải nguy hiểm nhất.
    """
    from src.python.core.infra import target_mode as TM

    assert TM.NOTIONAL_GAP_WARN_X > 1.97, "vẫn đang dùng ngưỡng suy từ gap của vàng"
    assert TM.FX_WORST_WEEKEND_GAP_PCT == pytest.approx(2.138, abs=0.01)
    # Ở trần đòn bẩy thật (3,7x) cảnh báo phải IM — nếu nó kêu thì hai tầng lệch nhau.
    assert TM.notional_gap_warning(3.7 * 100_000.0, 100_000.0) is None
