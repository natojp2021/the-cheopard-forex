"""Vòng 54 — MÔ-MEN BẬC CAO và THỜI VỤ NỘI NGÀY trên cross, khung M30 và H1.

VÒNG 53 ĐÃ LOẠI ĐƯỢC GÌ VÀ CHỈ RA GÌ
=====================================
19 họ quy tắc Carver × 2 khung: **mọi họ theo xu hướng đều có gross ÂM** ở mọi tốc độ
(EWMAC 2/8 đến 64/256, breakout 10 đến 320). Đây là kết luận về TÍN HIỆU, không phải
về chi phí — cơ chế dự báo liên tục + buffer đã kéo vòng quay xuống 1,8/năm ở họ chậm
nhất mà gross vẫn âm. Xu hướng không tồn tại trên cross tổng hợp.

Hai thứ sống sót, và cả hai đều KHÔNG phải mô-men bậc nhất:
    skew (mô-men bậc BA)   H1: FORM +0,157 · OOS +0,431 · vòng quay 1,9/năm
    meanrev_slow           H1: FORM +0,090 · OOS +0,214 · gross dương

Vòng này đào đúng chỗ đó: **thông tin trên FX không nằm ở HƯỚNG mà ở HÌNH DẠNG phân
phối**. Đó cũng là điều giải thích vì sao 53 vòng tìm hướng đều đổ.

BỐN NHÓM ĐO
===========
  A. SKEW      độ lệch, nhiều cửa sổ · tuyệt đối và tương đối (so với rổ)
  B. KURTOSIS  độ nhọn — công cụ có đuôi dày được trả phần bù
  C. VOL-CARRY biến động ngắn so với dài: cấu trúc kỳ hạn của biến động
  D. SEASON    thời vụ NỘI NGÀY trên cross — chưa từng đo trên rổ này

VÌ SAO SKEW CÓ CƠ SỞ, KHÔNG PHẢI ĐÀO DỮ LIỆU
=============================================
Carver (Ch. 25) và Lemperiere et al. (2016, "Risk Premia: Asymmetric Tail Risks and
Excess Returns") lập luận: tài sản có skew ÂM trả phần bù rủi ro, vì người nắm giữ
chịu rủi ro sụp đột ngột. Trên FX đây là hiệu ứng ĐÃ ĐƯỢC ĐO nhiều lần — carry trade
chính là bán skew, và "up by the stairs, down by the elevator" là mô tả dân dã của nó.

Nên dấu của tín hiệu được ĐẶT TRƯỚC theo lý thuyết: **mua công cụ skew âm**. Nếu đo ra
dấu ngược thì loại, không đảo dấu để lấy kết quả đẹp.

CỔNG CHẤP NHẬN — ĐẶT TRƯỚC KHI XEM KẾT QUẢ
===========================================
    1. FORM > 0 VÀ OOS > 0
    2. ALL > 0,40
    3. gross > 0 (nếu gross âm thì không có tín hiệu, dừng)
    4. vùng tham số: ô lân cận cùng dấu
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import numpy as np
import pandas as pd

from src.python.research import fx_cross_lab as LAB
from research.fx.carver_lab import (FORM_END, apply_buffer, forecast_to_position,
                                    scale_and_cap, sharpe, _vol, VOL_SPAN_BARS)

pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 400)
OUT = ROOT / "reports" / "fx_research"
BARS_DAY = {"M30": 48, "H1": 24}


# ═══════════════════════════════════════════════════════ A · SKEW
def sig_skew(logp: pd.DataFrame, window: int, relative: bool = False
             ) -> pd.DataFrame:
    """Độ lệch phân phối lợi nhuận, ĐẢO DẤU — mua công cụ skew âm.

    `relative=True` thì trừ trung bình rổ trước: khi cả rổ cùng lệch âm (giai đoạn
    căng thẳng), tín hiệu tuyệt đối bảo mua TẤT CẢ, tức không còn là cược tương đối.
    """
    s = -logp.diff().rolling(window, min_periods=window // 2).skew()
    return s.sub(s.mean(axis=1), axis=0) if relative else s


# ═══════════════════════════════════════════════════════ B · KURTOSIS
def sig_kurtosis(logp: pd.DataFrame, window: int, relative: bool = False
                 ) -> pd.DataFrame:
    """Độ nhọn, ĐẢO DẤU — công cụ đuôi dày được trả phần bù để bù rủi ro đuôi."""
    k = -logp.diff().rolling(window, min_periods=window // 2).kurt()
    return k.sub(k.mean(axis=1), axis=0) if relative else k


# ═══════════════════════════════════════════════════════ C · VOL CARRY
def sig_vol_carry(logp: pd.DataFrame, short: int, long_: int,
                  relative: bool = False) -> pd.DataFrame:
    """Cấu trúc kỳ hạn của biến động: σ ngắn / σ dài, đảo dấu.

    σ ngắn < σ dài (thị trường vừa dịu lại) → tín hiệu DƯƠNG. Đây là cược vào việc
    biến động hồi về trung bình, thứ đã đo được là bền hơn nhiều so với hướng giá.
    """
    r = logp.diff()
    v_s = r.rolling(short, min_periods=short // 2).std()
    v_l = r.rolling(long_, min_periods=long_ // 2).std()
    v = -(v_s / v_l.replace(0, np.nan))
    return v.sub(v.mean(axis=1), axis=0) if relative else v


# ═══════════════════════════════════════════════════════ D · THỜI VỤ NỘI NGÀY
def sig_intraday_season(logp: pd.DataFrame, lookback_days: int, bars_per_day: int
                        ) -> pd.DataFrame:
    """Lợi nhuận trung bình của ĐÚNG khung giờ này trong `lookback_days` ngày trước.

    Giả thuyết: dòng tiền định kỳ (fix ngân hàng, mở/đóng phiên, tái cân bằng quỹ) để
    lại dấu vết lặp theo giờ. Ước lượng NHÂN QUẢ hoàn toàn: chỉ dùng các ngày TRƯỚC
    ngày hiện tại, và với cùng chỉ số nến trong ngày.

    Đây là kiểm định trực tiếp một giả thuyết đã bị bác bỏ ở dạng khác (hiệu ứng fix
    theo giờ trên MAJOR, vòng 12): lần này trên CROSS, nơi thành phần USD đã triệt tiêu.
    """
    r = logp.diff()
    R = r.to_numpy(dtype=float)
    n, m = R.shape
    out = np.full((n, m), np.nan)
    win = lookback_days * bars_per_day
    for i in range(win + bars_per_day, n):
        # các nến CÙNG giờ trong ngày, thuộc `lookback_days` ngày TRƯỚC
        idx = np.arange(i - win, i, bars_per_day)
        seg = R[idx]
        if np.isfinite(seg).sum() >= len(idx) // 2:
            out[i] = np.nanmean(seg, axis=0)
    S = pd.DataFrame(out, index=logp.index, columns=logp.columns)
    return S.sub(S.mean(axis=1), axis=0)


def evaluate(panel, logp, vol, raw: pd.DataFrame, name: str, tf: str,
             rows: List[Dict], series: Dict[str, pd.Series]) -> None:
    """Dự báo thô → chuẩn hoá → vị thế → buffer → mô phỏng đủ chi phí."""
    fc = scale_and_cap(raw)
    pos = apply_buffer(forecast_to_position(fc, vol, 1.0))
    gross_exp = pos.abs().sum(axis=1).replace(0, np.nan)
    pos = pos.div(gross_exp, axis=0).fillna(0.0)

    res = LAB.simulate_positions(panel, pos, name=name)
    d = res.pnl_daily
    series[f"{tf}|{name}"] = d
    rows.append({
        "tf": tf, "rule": name,
        "ALL": round(sharpe(d), 3),
        "FORM": round(sharpe(d, hi=FORM_END), 3),
        "OOS": round(sharpe(d, lo=FORM_END), 3),
        "gross": round(res.gross_bps_bar, 5),
        "phi": round(res.trade_cost_bps_bar + res.carry_cost_bps_bar, 5),
        "turn/năm": round(res.turnover_per_year, 1)})


def main() -> None:
    t0 = time.time()
    rows: List[Dict] = []
    series: Dict[str, pd.Series] = {}

    for tf in ("H1", "M30"):
        bpd = BARS_DAY[tf]
        panel = LAB.build_panel(tf, start="2020-01-01")
        logp = panel.logp
        vol = _vol(logp, VOL_SPAN_BARS[tf])
        print(f"── {tf}: {len(logp):,} nến", flush=True)

        # A · skew ở nhiều cửa sổ, hai biến thể
        for days in (21, 42, 63, 126, 252):
            w = max(days * bpd, 40)
            for rel in (False, True):
                evaluate(panel, logp, vol, sig_skew(logp, w, rel),
                         f"skew_{days}d{'_rel' if rel else ''}", tf, rows, series)

        # B · kurtosis
        for days in (42, 63, 126):
            w = max(days * bpd, 40)
            for rel in (False, True):
                evaluate(panel, logp, vol, sig_kurtosis(logp, w, rel),
                         f"kurt_{days}d{'_rel' if rel else ''}", tf, rows, series)

        # C · vol carry
        for s_d, l_d in ((5, 63), (10, 126), (21, 252)):
            for rel in (False, True):
                evaluate(panel, logp, vol,
                         sig_vol_carry(logp, max(s_d * bpd, 10), max(l_d * bpd, 60), rel),
                         f"volcarry_{s_d}_{l_d}{'_rel' if rel else ''}", tf, rows, series)

        # D · thời vụ nội ngày
        for lb in (21, 63, 126):
            evaluate(panel, logp, vol, sig_intraday_season(logp, lb, bpd),
                     f"season_{lb}d", tf, rows, series)
        print(f"   xong ({time.time() - t0:.0f}s)", flush=True)

    T = pd.DataFrame(rows)
    T.to_csv(OUT / "moments_lab.csv", index=False)

    print()
    print("=" * 120)
    print("KẾT QUẢ")
    print("=" * 120)
    print(T.sort_values("ALL", ascending=False).to_string(index=False))

    print()
    print("=" * 120)
    print("CỔNG 3 — gross > 0 (không có tín hiệu thì dừng, không xét tiếp)")
    print("=" * 120)
    g = T[T["gross"] > 0]
    print(f"{len(g)}/{len(T)} ô có gross dương")
    print(g.sort_values("ALL", ascending=False).to_string(index=False))

    print()
    print("=" * 120)
    print("CỔNG 1-2-3: FORM>0 & OOS>0 & ALL>0,40 & gross>0")
    print("=" * 120)
    k = T[(T["FORM"] > 0) & (T["OOS"] > 0) & (T["ALL"] > 0.40)
          & (T["gross"] > 0)].sort_values("ALL", ascending=False)
    print(k.to_string(index=False) if len(k) else "  KHÔNG CÓ")

    import pickle
    with open(OUT / "moments_lab_pnl.pkl", "wb") as fh:
        pickle.dump(series, fh)
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
