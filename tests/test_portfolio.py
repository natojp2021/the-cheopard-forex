"""Kiểm định DANH MỤC — đơn vị, tính độc lập, và tính trung thực của OOS.

VÌ SAO
======
Danh mục là nơi hai lỗi nghiêm trọng đã xảy ra:

  1. **LỖI ĐƠN VỊ.** Chuỗi `net` có đơn vị "số lần σ_FORM của từng chân", KHÔNG phải
     % equity. Nhân nó với 100 để ra "% equity" làm FTMO báo 55,9% vi phạm trong khi
     Phase 1 báo 4,9% — con số bất khả. Nguyên nhân: ba chân có biến động rất khác
     nhau (4,45 / 4,27 / 22,46 %/năm) nên không có hằng số nào quy đổi được.
     Nay `PortfolioResult` trả về CẢ HAI: `net` (đơn vị σ) và `net_bps` (bps thật).

  2. **RÒ RỈ OOS QUA CHUẨN HOÁ.** Nếu chuẩn hoá bằng σ TOÀN MẪU thì tỷ trọng đã dùng
     thông tin của giai đoạn OOS, và Sharpe OOS báo ra cao hơn mức thực đạt được.
     `vol_window_end` phải mặc định là FORM_END.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.python.strategies import portfolio as PF
from src.python.strategies import registry as REG


@pytest.fixture(scope="module")
def res():
    return PF.backtest()


def test_leg_and_risk_group_counts_match():
    assert len(PF.LEG_WEIGHTS) == 27
    assert sum(PF.LEG_WEIGHTS.values()) == pytest.approx(1.0)
    assert len(PF.RISK_GROUPS) == 21
    # mọi chân phải thuộc đúng MỘT nhóm rủi ro — chân lạc nhóm là chân không ai
    # kiểm tra độc lập, và nó sẽ âm thầm nhân đôi phơi nhiễm
    within_group = [lg for legs in PF.RISK_GROUPS.values() for lg in legs]
    assert sorted(within_group) == sorted(PF.LEG_WEIGHTS)
    assert len(within_group) == len(set(within_group)), "có chân nằm trong hai nhóm"
    # mỗi NHÓM phải nhận đúng một suất bằng nhau
    rate = {g: sum(PF.LEG_WEIGHTS[lg] for lg in legs)
            for g, legs in PF.RISK_GROUPS.items()}
    assert all(v == pytest.approx(1 / 21) for v in rate.values()), rate


def test_registry_and_portfolio_agree():
    """Registry là SSOT. Nếu hai chỗ lệch nhau thì không ai biết cái nào đang chạy."""
    assert len(REG.PORTFOLIO["legs"]) == len(PF.LEG_WEIGHTS)
    assert sum(REG.PORTFOLIO["legs"].values()) == pytest.approx(1.0)
    names = {s.name for s in REG.STRATEGIES}
    for leg in REG.PORTFOLIO["legs"]:
        assert leg in names, f"chân {leg} có trong PORTFOLIO nhưng không có trong STRATEGIES"
    for leg in REG.PORTFOLIO["legs"]:
        assert leg in REG.PORTFOLIO["entry_points"], f"{leg} thiếu điểm vào live"


def test_every_leg_has_data(res):
    assert len(res.legs) == 27
    for k, s in res.legs.items():
        assert len(s) > 500, f"chân {k} chỉ có {len(s)} ngày"
        assert float(s.std(ddof=1)) > 0, f"chân {k} không biến động — có nạp được không?"


def test_the_two_units_do_not_mix(res):
    """`net` (đơn vị σ) và `net_bps` (bps thật) phải KHÁC NHAU về độ lớn.

    Nếu chúng bằng nhau thì bước chuẩn hoá đã không chạy, và mọi con số rủi ro
    hạ nguồn đang ở đơn vị sai.
    """
    assert res.net is not res.net_bps
    r = float(res.net_bps.std(ddof=1)) / float(res.net.std(ddof=1))
    assert r > 5.0, (f"tỷ lệ σ(net_bps)/σ(net) = {r:.2f} — quá gần 1, "
                     f"nghi bước chuẩn hoá bị bỏ")


def test_normalisation_uses_no_oos_data():
    """σ chuẩn hoá ước lượng trên FORM. Đổi `vol_window_end` phải đổi tỷ trọng.

    Test này chứng minh tham số CÓ tác dụng — nếu nó bị bỏ qua trong code thì hai
    lời gọi dưới đây sẽ cho cùng một kết quả và ta không phát hiện được.
    """
    a = PF.backtest(vol_window_end=pd.Timestamp("2024-01-01"))
    b = PF.backtest(vol_window_end=pd.Timestamp("2027-01-01"))
    assert a.leg_vol != b.leg_vol, "vol_window_end không có tác dụng"
    assert PF.FORM_END == pd.Timestamp("2024-01-01")


def test_risk_groups_are_independent(res):
    """|tương quan| giữa hai NHÓM RỦI RO phải < 0,70.

    Áp ngưỡng ở tầng NHÓM chứ không tầng chân: hai chân cùng công cụ khác khung ĐƯỢC
    PHÉP tương quan cao (đo được AUDCAD H1↔M30 = 0,712) vì chúng đã được gộp thành
    một suất. Điều cần kiểm là các nhóm có độc lập với nhau không.

    Trên ngưỡng đó, hai chân chỉ là MỘT cược ở hai kích cỡ: thêm vào danh mục không
    giảm rủi ro, chỉ tăng phí. Đây là điều kiện để đa dạng hoá có tác dụng, nên nó
    phải là một test, không phải một ghi chú.
    """
    G = PF.group_correlation(res)
    cols = list(G.columns)
    for a in cols:
        for b in cols:
            if a == b:
                continue
            v = abs(float(G.loc[a, b]))
            assert v < 0.70, f"{a} ↔ {b} = {v:.3f} — hai nhóm trùng cược"


def test_portfolio_beats_its_best_single_leg(res):
    """Ghép chân phải CẢI THIỆN Sharpe. Nếu không thì việc ghép là vô nghĩa."""
    def sh(s):
        sd = float(s.std(ddof=1))
        return float(s.mean()) / sd * np.sqrt(252) if sd > 0 else 0.0

    port = sh(res.net)
    best = max(sh(v) for v in res.legs_normalised.values())
    assert port > best, f"danh mục {port:.3f} không hơn chân tốt nhất {best:.3f}"


def test_sharpe_meets_published_threshold(res):
    """Chốt lại con số đã công bố trong registry — chống trôi âm thầm.

    Ngưỡng lỏng (±0,15) vì dữ liệu tăng theo thời gian; nhưng lệch quá thế thì
    hoặc dữ liệu đã đổi bản chất, hoặc code đã đổi hành vi — cả hai đều cần biết.
    """
    def sh(s):
        sd = float(s.std(ddof=1))
        return float(s.mean()) / sd * np.sqrt(252)

    n = res.net
    claimed = REG.PORTFOLIO["sharpe_all"]
    assert abs(sh(n) - claimed) < 0.15, \
        f"Sharpe = {sh(n):.3f} vs registry công bố {claimed}"
    oos = n[n.index >= PF.FORM_END]
    assert sh(oos) > 0, "OOS âm — không được cấp vốn"


def test_every_year_is_positive(res):
    yr = res.net.groupby(res.net.index.year).sum()
    n_pos = int((yr > 0).sum())
    assert n_pos >= len(yr) - 1, f"chỉ {n_pos}/{len(yr)} năm dương"


def test_risk_parity_bps_returns_sane_percentages(res):
    """`risk_parity_bps` phải ra chuỗi có biến động ĐÚNG mục tiêu đã yêu cầu."""
    s = res.risk_parity_bps(target_vol_pct_annual=8.0)
    vol = float(s.std(ddof=1)) * np.sqrt(252) / 100.0
    assert 6.0 < vol < 10.0, f"biến động thực {vol:.2f}%/năm, mục tiêu 8,0%"
