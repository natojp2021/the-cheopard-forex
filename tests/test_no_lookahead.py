"""Kiểm định KHÔNG CÓ LOOK-AHEAD — test chống lỗi tốn kém nhất của dự án.

VÌ SAO
======
Lỗi look-ahead đã xảy ra THẬT trong dự án này. Bản quét momentum H1 dùng
`s, v = Sv[i], Vv[i]` — tín hiệu tại nến `i` (đã chứa lợi nhuận của nến `i`) rồi ăn
chính lợi nhuận đó. Kết quả: Sharpe **+1,744**. Sau khi sửa thành `Sv[i-1], Vv[i-1]`
thì MỌI ô đều âm.

Đặc điểm làm nó nguy hiểm: kết quả trông ĐẸP, không trông SAI. Không có exception,
không có NaN, không có cảnh báo. Chỉ có một con số quá tốt — mà "quá tốt" là điều
người ta muốn thấy nên ít ai đi kiểm tra.

CÁCH TEST — GHIM DỮ LIỆU TƯƠNG LAI
==================================
Nguyên tắc: nếu tín hiệu tại thời điểm `t` chỉ dùng dữ liệu đến `t−1` thì THAY ĐỔI
dữ liệu SAU `t` không được làm thay đổi tín hiệu tại `t`. Test dựng hai bản dữ liệu
giống hệt nhau tới điểm cắt, khác hẳn nhau sau đó, rồi đòi tín hiệu trước điểm cắt
phải TRÙNG KHỚP TỪNG PHẦN TỬ.

Đây là test đúng bản chất: nó không kiểm tra code có `.shift(1)` hay không (dễ lách,
dễ hiểu sai), nó kiểm tra HÀNH VI có phụ thuộc tương lai hay không.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _fake_logp(n: int = 900, n_ins: int = 20, seed: int = 11) -> pd.DataFrame:
    """Bảng log giá giả — bước đi ngẫu nhiên, đủ dài cho mọi cửa sổ đang dùng."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="4h")
    cols = [f"X{i:02d}" for i in range(n_ins)]
    steps = rng.normal(0, 0.0015, size=(n, n_ins))
    return pd.DataFrame(np.cumsum(steps, axis=0), index=idx, columns=cols)


def test_zscore_uses_no_future_data():
    """`cross_xs_reversion.zscore` — z tại t chỉ được dùng dữ liệu đến t−1."""
    from src.python.strategies.h4 import cross_xs_reversion as XXS

    A = _fake_logp()
    cut = 600
    B = A.copy()
    # phá hoại toàn bộ phần sau điểm cắt — bằng giá trị khác bậc độ lớn
    B.iloc[cut:] = B.iloc[cut:] + 5.0

    za = XXS.zscore(A, XXS.WINDOW_BARS)
    zb = XXS.zscore(B, XXS.WINDOW_BARS)
    pd.testing.assert_frame_equal(za.iloc[:cut], zb.iloc[:cut])


def test_target_weights_use_no_future_data():
    """Tỷ trọng mục tiêu trước điểm cắt phải bất biến khi tương lai đổi."""
    from src.python.strategies.h4 import cross_xs_reversion as XXS

    A = _fake_logp()
    cut = 600
    B = A.copy()
    B.iloc[cut:] = B.iloc[cut:] + 5.0

    wa = XXS.target_weights(A)
    wb = XXS.target_weights(B)
    pd.testing.assert_frame_equal(wa.iloc[:cut], wb.iloc[:cut])


def test_zscore_is_shifted_exactly_one_bar():
    """z tại nến t phải bằng z thô tính đến hết nến t−1 — không sớm, không muộn.

    Lệch một nến theo chiều SAI là look-ahead; lệch theo chiều ĐÚNG thì mất tín hiệu.
    Test chốt cả hai chiều bằng cách tính tay trên dữ liệu giả.
    """
    from src.python.strategies.h4 import cross_xs_reversion as XXS

    A = _fake_logp(n=200, n_ins=3)
    w = 30
    z = XXS.zscore(A, w)
    col = A.columns[0]
    t = 120
    win = A[col].iloc[t - w:t]              # KẾT THÚC ở t−1, không gồm t
    expect = (A[col].iloc[t - 1] - win.mean()) / win.std(ddof=1)
    assert z[col].iloc[t] == pytest.approx(float(expect), rel=1e-9)


def test_regime_gate_uses_rolling_quantile_not_full_sample():
    """Cổng chế độ của `currency_reversal` — ngưỡng phải là phân vị TRƯỢT.

    Phân vị toàn mẫu dùng thông tin tương lai và KHÔNG chạy được live: vào ngày
    2020-03-18 ta chưa biết phân vị 80 của cả giai đoạn 2020-2026.
    """
    from src.python.strategies.d1 import currency_reversal as CR

    rng = np.random.default_rng(3)
    idx = pd.date_range("2020-01-01", periods=800, freq="B")
    F = pd.DataFrame(rng.normal(0, 30, size=(800, 8)), index=idx,
                     columns=list("ABCDEFGH"))
    cut = 500
    G = F.copy()
    G.iloc[cut:] = G.iloc[cut:] * 40.0      # tương lai biến động cực lớn

    ra = CR.regime_is_crisis(F, CR.Config())
    rb = CR.regime_is_crisis(G, CR.Config())
    pd.testing.assert_series_equal(ra.iloc[:cut], rb.iloc[:cut])


def test_momentum_signal_uses_no_future_data():
    """`fx_cross_lab.sig_xs_reversal` đọc `mom.iloc[i-1]` — chốt lại hành vi đó."""
    from src.python.research import fx_cross_lab as LAB

    A = _fake_logp(n=700, n_ins=20)
    cut = 450

    class _P:
        timeframe = "H4"
        logp = A

    pa = LAB.sig_xs_reversal(_P(), lookback=30, n_leg=5, rebalance_bars=12)
    B = A.copy()
    B.iloc[cut:] = B.iloc[cut:] + 5.0
    _P.logp = B
    pb = LAB.sig_xs_reversal(_P(), lookback=30, n_leg=5, rebalance_bars=12)
    pd.testing.assert_frame_equal(pa.iloc[:cut], pb.iloc[:cut])


def test_zband_entry_modes_agree_between_vector_and_live():
    """`entry_signals` và `live_decision` phải cho CÙNG quyết định ở CẢ HAI luật vào.

    VÌ SAO BẤT BIẾN NÀY ĐÁNG MỘT TEST RIÊNG
    ========================================
    `zband_core` có hai hiện thực của cùng một luật: `entry_signals` (vector, dùng
    trong backtest) và `live_decision` (từng nến, dùng khi chạy thật). Hai bản lệch
    nhau là lớp lỗi ĐẮT NHẤT của dự án và nó đã xảy ra một lần: `ZBandGBPCAD_H4` ra
    Sharpe 0,815 ở lab nhưng 0,557 ở động cơ sản xuất, vì lab thiếu nhánh thoát khi
    z về 0. Mỗi bản tự nhất quán nên không test đơn lẻ nào bắt được — chỉ phép so
    CHÉO hai bản mới thấy.

    Tham số `entry_mode` (thêm 16/08/2026) nhân đôi số nhánh phải khớp, nên nó nhân
    đôi luôn cả rủi ro đó. Test này so từng nến, cho cả hai luật.
    """
    from src.python.strategies import zband_core as ZB

    rng = np.random.default_rng(7)
    n = 500
    idx = pd.date_range("2021-01-01", periods=n, freq="1h")
    # Bước đi ngẫu nhiên CÓ hồi quy — cần z vượt ngưỡng đủ nhiều lần để cả hai luật
    # đều phát tín hiệu; bước đi thuần có thể trôi đi và không bao giờ quay lại.
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = 0.97 * x[i - 1] + rng.normal(0, 0.004)
    close = pd.Series(np.exp(x), index=idx)
    df = pd.DataFrame({"open": close, "high": close, "low": close, "close": close})

    for mode in ("outside", "reenter"):
        cfg = ZB.ZBandConfig(name="T", instrument="AUDCAD", timeframe="H1",
                             window_bars=48, entry_sigma=1.5, timestop_mult=1.0,
                             entry_mode=mode)
        buy, sell = ZB.entry_signals(close, cfg)
        n_sig = 0
        for i in range(60, n):
            # `entry_signals` đã `.shift(1)`: tín hiệu tại i dựng từ z đến i−1, tức
            # cùng thông tin mà `live_decision` thấy khi chỉ được đưa df[:i].
            d = ZB.live_decision(df.iloc[:i], 0.0, 0.0, cfg, bars_held=0, side=0)
            want = "BUY" if bool(buy.iloc[i]) else "SELL" if bool(sell.iloc[i]) else "FLAT"
            assert d.action == want, (
                f"luật {mode!r} lệch tại nến {i} ({idx[i]}): vector nói {want}, "
                f"live nói {d.action} — {d.reason}")
            n_sig += want != "FLAT"
        # Một test không bao giờ thấy tín hiệu nào là một test không kiểm gì cả.
        assert n_sig >= 5, f"luật {mode!r} chỉ phát {n_sig} tín hiệu — test rỗng"


def test_zband_reenter_waits_for_z_to_come_back_inside():
    """Luật `reenter` phải vào MUỘN HƠN `outside`, không phải vào chỗ khác.

    Kiểm HÀNH VI chứ không kiểm sự hiện diện của một dòng code: dựng một lần lệch
    duy nhất đi ra rồi quay lại, rồi đòi `outside` vào khi z CÒN ngoài dải và
    `reenter` vào khi z ĐÃ về trong dải.
    """
    from src.python.strategies import zband_core as ZB

    n = 400
    idx = pd.date_range("2021-01-01", periods=n, freq="1h")
    x = np.zeros(n)
    x[250:270] = np.linspace(0, 0.02, 20)      # đi RA khỏi dải
    x[270:300] = np.linspace(0.02, 0.0, 30)    # QUAY LẠI vào trong
    x[300:] = 0.0
    close = pd.Series(np.exp(x), index=idx)

    z = ZB.zscore(close, 48)
    fired = {}
    for mode in ("outside", "reenter"):
        cfg = ZB.ZBandConfig(name="T", instrument="AUDCAD", timeframe="H1",
                             window_bars=48, entry_sigma=1.5, timestop_mult=1.0,
                             entry_mode=mode)
        buy, sell = ZB.entry_signals(close, cfg)
        hits = [i for i in range(n) if bool(buy.iloc[i]) or bool(sell.iloc[i])]
        assert hits, f"luật {mode!r} không phát tín hiệu nào trên chuỗi dựng sẵn"
        fired[mode] = hits[0]
        # z tại nến QUYẾT ĐỊNH là i−1 (vì `entry_signals` đã dịch một nến).
        zd = abs(float(z.iloc[hits[0] - 1]))
        if mode == "outside":
            assert zd > cfg.entry_sigma, f"outside vào khi |z|={zd:.2f} đã trong dải"
        else:
            assert zd <= cfg.entry_sigma, f"reenter vào khi |z|={zd:.2f} còn ngoài dải"

    assert fired["reenter"] > fired["outside"], (
        f"reenter vào tại nến {fired['reenter']}, KHÔNG muộn hơn outside tại "
        f"{fired['outside']} — luật đợi hồi quy mà lại vào trước là sai")
