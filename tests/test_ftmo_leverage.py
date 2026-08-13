"""Kiểm định CHÍNH SÁCH ĐÒN BẨY FTMO — ràng buộc TAIL là trọng tâm.

VÌ SAO
======
Bản đầu của chính sách này giả định phân phối chuẩn: σ = 0,504%/ngày, nên "3σ = 1,5%"
trông an toàn dưới giới hạn lỗ ngày 5% của FTMO. Nhưng ngày tệ nhất đo được là
**−5,47% = 10,8σ**. Ở đòn bẩy 1,73x mà chính sách cho phép, ngày đó thành −9,47% —
vi phạm giới hạn ngày. Mô phỏng cho 29-57% tài khoản funded bị vi phạm.

Sửa: thêm ràng buộc TAIL lấy từ ngày TỆ NHẤT ĐÃ QUAN SÁT, nhân `TAIL_BUFFER = 1,3`,
và lấy MIN của ba ràng buộc. Kết quả: vi phạm **0,0%**, p10 equity từ −6,84% → +0,64%.

Bài học đằng sau: trên FX, σ mô tả phần giữa của phân phối và không nói gì về đuôi.
Ràng buộc rủi ro phải neo vào QUAN SÁT tệ nhất, không vào một bội số của σ.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.python.execution import ftmo_leverage_policy as POL


def test_safety_constants_match_calibration():
    """Ghim SÁU hằng số hiệu chuẩn — đổi một cái phải qua đây.

    Test này CỐ Ý đỏ mỗi khi ai đó chỉnh tham số rủi ro. Nó không kiểm đúng/sai,
    nó buộc người sửa phải đọc lại bảng đo trước khi cập nhật con số ở đây — và
    đó là lớp phòng vệ cuối cùng chống việc nới rủi ro âm thầm.

    CẬP NHẬT 15/08/2026 — ba con số đổi, mỗi cái có một bảng đo đứng sau:
        LEVERAGE_MAX  3,5 → 6,0   `research/fx/leverage_scan_full.py`
        TAIL_BUFFER   1,3 → 1,2   `research/fx/risk_budget_tune.py`
        (ngưỡng HALT  4,0% → 1,0% đệm tổng, không nằm trong test này)

    Chọn theo CẤU TRÚC chứ không theo lợi nhuận: `LEVERAGE_MAX` đặt tại điểm mà
    trần cứng hết tác dụng (đòn bẩy thực bão hoà 5,25x), `TAIL_BUFFER` đặt tại
    bậc cuối trước ĐIỂM GÃY — hạ tiếp xuống 1,1 làm tỷ lệ cửa sổ bị cắt nhảy từ
    0% lên 23,5%.
    """
    assert POL.SAFETY_SIGMA_DAILY == pytest.approx(3.0)
    assert POL.SAFETY_SIGMA_TOTAL == pytest.approx(2.5)
    assert POL.SAFETY_HORIZON_DAYS == 21
    assert POL.TAIL_BUFFER == pytest.approx(1.2)
    assert POL.LEVERAGE_MAX == pytest.approx(6.0)
    assert POL.DD_SELF_CAP == pytest.approx(0.09)


def test_internal_floor_is_tighter_than_ftmo_rule():
    """Sàn tính toán phải là 9%, KHÔNG phải mốc 10% của FTMO.

    Chính sách cũ bám đúng mốc 10% và cho đòn bẩy 4,85x — đo được MaxDD −10,74%,
    tức chuỗi ngày xấu liên tiếp vượt trần tổng dù không ngày nào riêng lẻ vi phạm.
    Ba ràng buộc bên dưới chỉ bó MỘT ngày hoặc MỘT cửa sổ 21 ngày, không cái nào
    bó drawdown tích luỹ — nên biên phải nằm ở sàn.
    """
    from src.python.core.infra import ftmo

    assert POL.DD_SELF_CAP < ftmo.MAX_LOSS_HARD

    # Ở equity $91.500 tài khoản còn hợp lệ theo FTMO (sàn thật $90.000) nhưng đã
    # dưới sàn nội bộ $91.000 → chính sách phải DỪNG HẲN, không cấp đòn bẩy.
    r = POL.decide(equity=90_900, day_start_balance=90_900, daily_vol_bps=50.0)
    assert r.leverage == 0.0 and r.state == "HALT"


def test_leverage_always_within_valid_range():
    for eq in (95_000, 100_000, 103_000, 110_000):
        for vol in (20.0, 50.0, 120.0):
            lev = POL.decide(equity=eq, day_start_balance=100_000,
                             daily_vol_bps=vol)
            lev = float(lev if not hasattr(lev, "leverage") else lev.leverage)
            assert 0.0 <= lev <= POL.LEVERAGE_MAX


def test_tail_constraint_reduces_leverage():
    """Truyền `worst_day_bps` phải làm đòn bẩy GIẢM hoặc giữ nguyên, không tăng.

    Đây là test cốt lõi: nếu ràng buộc TAIL không được đưa vào phép MIN thì nó chỉ
    là một tham số trang trí, và lỗi 29-57% vi phạm quay lại.
    """
    def _lev(**kw):
        r = POL.decide(equity=100_000, day_start_balance=100_000,
                       daily_vol_bps=50.0, **kw)
        return float(r if not hasattr(r, "leverage") else r.leverage)

    base = _lev()
    with_tail = _lev(worst_day_bps=547.0)
    assert with_tail <= base
    assert with_tail < base, "ràng buộc TAIL không có tác dụng ở đuôi 10,8σ"


def test_worse_tail_gives_lower_leverage():
    """Đơn điệu: ngày tệ nhất càng xấu thì đòn bẩy cho phép càng nhỏ."""
    def _lev(worst):
        r = POL.decide(equity=100_000, day_start_balance=100_000,
                       daily_vol_bps=50.0, worst_day_bps=worst)
        return float(r if not hasattr(r, "leverage") else r.leverage)

    levs = [_lev(w) for w in (100.0, 300.0, 547.0, 900.0)]
    assert all(levs[i] >= levs[i + 1] for i in range(len(levs) - 1)), levs


def test_thin_equity_buffer_reduces_leverage():
    """Gần ngưỡng lỗ tổng thì đòn bẩy phải co lại — đây là cơ chế sống sót."""
    def _lev(eq):
        r = POL.decide(equity=eq, day_start_balance=eq, daily_vol_bps=50.0,
                       worst_day_bps=547.0)
        return float(r if not hasattr(r, "leverage") else r.leverage)

    assert _lev(91_000) < _lev(100_000) <= _lev(108_000)


def test_higher_volatility_reduces_leverage():
    def _lev(vol):
        r = POL.decide(equity=100_000, day_start_balance=100_000,
                       daily_vol_bps=vol, worst_day_bps=547.0)
        return float(r if not hasattr(r, "leverage") else r.leverage)

    assert _lev(150.0) < _lev(50.0)


def test_simulation_never_breaches_daily_limit():
    """Chạy đường equity mô phỏng với ĐUÔI THẬT: không được vi phạm giới hạn 5%/ngày.

    Chuỗi thử được cố ý nhồi một ngày −5,47% (ngày tệ nhất đã quan sát của danh mục)
    để kiểm tra đúng tình huống đã làm bản cũ vỡ.
    """
    rng = np.random.default_rng(5)
    n_viol_tail = n_viol_bare = 0
    for seed in range(60):
        rng = np.random.default_rng(seed)
        r = rng.normal(0.0, 50.0, size=250)      # bps/ngày ở đòn bẩy 1,0
        r[120] = -547.0                          # ngày tệ nhất đã quan sát
        with_tail = POL.simulate_path(r, 50.0, target_pct=None,
                                      worst_day_bps=547.0)[0]
        bare = POL.simulate_path(r, 50.0, target_pct=None)[0]
        n_viol_tail += int(with_tail == "DAILY")
        n_viol_bare += int(bare == "DAILY")

    # CÓ ràng buộc TAIL: không đường nào vi phạm giới hạn ngày.
    assert n_viol_tail == 0, \
        f"{n_viol_tail}/60 đường vi phạm giới hạn ngày dù đã bật TAIL"
    # KHÔNG có nó: phải vi phạm — nếu không thì test này không kiểm được gì cả,
    # và ràng buộc TAIL có thể bị xoá mà không ai phát hiện.
    assert n_viol_bare > 0, \
        "không bật TAIL mà vẫn không vi phạm — test mất khả năng phát hiện lỗi"
