"""Vòng 55 — HÌNH DẠNG PHÂN PHỐI: sáu họ nữa, khung M30 và H1.

PHÁT HIỆN CỦA VÒNG 53-54 DẪN ĐẾN VÒNG NÀY
==========================================
Vòng 53: mọi họ theo XU HƯỚNG có gross ÂM ở mọi tốc độ (19 họ × 2 khung).
Vòng 54: **20/20 biến thể SKEW có gross DƯƠNG** ở cả hai khung, mọi cửa sổ 21-252 ngày.

Hai kết quả đó cùng nói một điều: trên cross tổng hợp, thông tin khai thác được không
nằm ở HƯỚNG của phân phối lợi nhuận mà ở HÌNH DẠNG của nó. Điều này khớp với lý thuyết
phần bù rủi ro (Lemperiere et al. 2016): người nắm tài sản có đuôi trái dày được trả
tiền để chịu rủi ro đó, và phần trả đó KHÔNG phụ thuộc vào việc giá đang lên hay xuống.

Vòng này đo sáu thống kê hình dạng KHÁC, tất cả độc lập với mô-men bậc nhất:

  A. SEMIDEV      σ chiều xuống so với σ chiều lên — bất đối xứng ở mức mô-men BẬC HAI,
                  khác skew (bậc ba) ở chỗ nó không bị đuôi cực đoan chi phối
  B. DRAWDOWN     khoảng cách từ đỉnh trượt, chuẩn hoá theo σ — "đã đi được bao xa
                  xuống dưới" là một biến trạng thái, không phải một dự báo hướng
  C. VOL-OF-VOL   biến động của biến động — bất ổn về bất ổn
  D. NOISE        σ nội nến (Parkinson từ high-low) so với σ đóng-đóng.
                  Tỷ số này đo NHIỄU so với DI CHUYỂN — cao = đi lại nhiều mà không tới đâu
  E. JUMP         tần suất nến có |lợi nhuận| > 3σ — đo mật độ đuôi trực tiếp,
                  không qua mô-men (mô-men bị một quan sát cực đoan kéo lệch)
  F. UPDOWN       tỷ lệ nến dương — bất đối xứng ở mức ĐẾM, miễn nhiễm với độ lớn

VÌ SAO ĐÂY KHÔNG PHẢI ĐÀO DỮ LIỆU
==================================
Sáu họ này là sáu CÁCH ĐO KHÁC NHAU của cùng một đại lượng kinh tế: mức bất đối xứng
mà người nắm giữ phải chịu. Nếu phần bù skew là thật thì phần lớn trong sáu họ phải
cùng dấu — đó là điều kiện kiểm chứng đặt TRƯỚC. Nếu chỉ một họ dương còn năm họ âm
thì họ đó là nhiễu, bất kể Sharpe của nó đẹp đến đâu.

Dấu của mọi tín hiệu ĐẶT TRƯỚC theo lý thuyết phần bù: mua công cụ bất đối xứng bất
lợi hơn. Không đảo dấu để lấy kết quả đẹp.
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import numpy as np
import pandas as pd

from src.python.research import fx_cross_lab as LAB
from research.fx.carver_lab import (FORM_END, VOL_SPAN_BARS, _vol, apply_buffer,
                                    forecast_to_position, scale_and_cap, sharpe)
from research.fx.moments_lab import evaluate

pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 400)
OUT = ROOT / "reports" / "fx_research"
BARS_DAY = {"M30": 48, "H1": 24}


# ═══════════════════════════════════════════════════════ A · bán độ lệch
def sig_semidev(logp: pd.DataFrame, window: int, relative: bool = True
                ) -> pd.DataFrame:
    """σ(chiều xuống) / σ(chiều lên), đảo dấu — mua công cụ có chiều xuống dữ hơn.

    Khác skew ở chỗ nó không bị MỘT quan sát cực đoan kéo lệch: skew nâng luỹ thừa ba
    nên một nến −6σ chi phối cả cửa sổ. Bán độ lệch chỉ nâng luỹ thừa hai.
    """
    r = logp.diff()
    dn = r.where(r < 0).rolling(window, min_periods=window // 4).std()
    up = r.where(r > 0).rolling(window, min_periods=window // 4).std()
    s = -(dn / up.replace(0, np.nan))
    return s.sub(s.mean(axis=1), axis=0) if relative else s


# ═══════════════════════════════════════════════════════ B · drawdown
def sig_drawdown(logp: pd.DataFrame, window: int, relative: bool = True
                 ) -> pd.DataFrame:
    """Khoảng cách từ đỉnh trượt, chuẩn hoá theo σ. Càng sâu → tín hiệu càng DƯƠNG."""
    peak = logp.rolling(window, min_periods=window // 2).max()
    sd = logp.diff().rolling(window, min_periods=window // 2).std()
    d = (peak - logp) / (sd.replace(0, np.nan) * np.sqrt(window))
    return d.sub(d.mean(axis=1), axis=0) if relative else d


# ═══════════════════════════════════════════════════════ C · biến động của biến động
def sig_vol_of_vol(logp: pd.DataFrame, window: int, relative: bool = True
                   ) -> pd.DataFrame:
    """σ của σ, đảo dấu — bất ổn về mức bất ổn cũng là một rủi ro được trả tiền."""
    v = logp.diff().rolling(max(window // 4, 5), min_periods=3).std()
    vv = -(v.rolling(window, min_periods=window // 2).std()
           / v.rolling(window, min_periods=window // 2).mean().replace(0, np.nan))
    return vv.sub(vv.mean(axis=1), axis=0) if relative else vv


# ═══════════════════════════════════════════════════════ D · nhiễu nội nến
def sig_noise(panel, window: int, relative: bool = True) -> pd.DataFrame:
    """σ Parkinson (từ high-low) chia σ đóng-đóng — tỷ số NHIỄU trên DI CHUYỂN.

    Tỷ số cao nghĩa là giá đi lại nhiều trong nến mà không tới đâu — đặc trưng của
    thị trường đi ngang. Đảo dấu: mua công cụ đang ĐI ĐÂU ĐÓ, bán công cụ đang lắc.

    Không có chuỗi high/low cho cross tổng hợp, nên biên độ nội nến được xấp xỉ bằng
    độ lệch tuyệt đối trung bình trên cửa sổ ngắn — cùng ý nghĩa, khác hằng số nhân.
    """
    r = panel.logp.diff()
    intrabar = r.abs().rolling(max(window // 8, 3), min_periods=2).mean() * np.sqrt(
        np.pi / 2.0)
    c2c = r.rolling(window, min_periods=window // 2).std()
    n = -(intrabar / c2c.replace(0, np.nan))
    return n.sub(n.mean(axis=1), axis=0) if relative else n


# ═══════════════════════════════════════════════════════ E · mật độ đuôi
def sig_jump(logp: pd.DataFrame, window: int, k: float = 3.0,
             relative: bool = True) -> pd.DataFrame:
    """Tần suất nến |lợi nhuận| > k·σ — đo mật độ đuôi TRỰC TIẾP, không qua mô-men.

    Ưu điểm so với kurtosis: đếm thì không bị một quan sát cực đoan chi phối, còn
    mô-men bậc bốn thì bị hoàn toàn.
    """
    r = logp.diff()
    sd = r.rolling(window, min_periods=window // 2).std()
    hit = (r.abs() > k * sd).astype(float)
    j = hit.rolling(window, min_periods=window // 2).mean()
    return j.sub(j.mean(axis=1), axis=0) if relative else j


# ═══════════════════════════════════════════════════════ F · tỷ lệ nến dương
def sig_updown(logp: pd.DataFrame, window: int, relative: bool = True
               ) -> pd.DataFrame:
    """Tỷ lệ nến dương, ĐẢO DẤU — bất đối xứng ở mức ĐẾM.

    Công cụ tăng đều đặn từng chút rồi sụp mạnh có tỷ lệ nến dương CAO nhưng skew ÂM.
    Đây là "up by the stairs, down by the elevator" đo bằng cách khác hẳn skew, nên
    nó là kiểm chứng ĐỘC LẬP cho cùng giả thuyết.
    """
    r = logp.diff()
    u = -(r > 0).astype(float).rolling(window, min_periods=window // 2).mean()
    return u.sub(u.mean(axis=1), axis=0) if relative else u


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

        for days in (21, 63, 126, 252):
            w = max(days * bpd, 40)
            for rel in (True, False):
                sfx = "_rel" if rel else ""
                evaluate(panel, logp, vol, sig_semidev(logp, w, rel),
                         f"semidev_{days}d{sfx}", tf, rows, series)
                evaluate(panel, logp, vol, sig_drawdown(logp, w, rel),
                         f"drawdown_{days}d{sfx}", tf, rows, series)
                evaluate(panel, logp, vol, sig_vol_of_vol(logp, w, rel),
                         f"volvol_{days}d{sfx}", tf, rows, series)
                evaluate(panel, logp, vol, sig_noise(panel, w, rel),
                         f"noise_{days}d{sfx}", tf, rows, series)
                evaluate(panel, logp, vol, sig_jump(logp, w, 3.0, rel),
                         f"jump_{days}d{sfx}", tf, rows, series)
                evaluate(panel, logp, vol, sig_updown(logp, w, rel),
                         f"updown_{days}d{sfx}", tf, rows, series)
        print(f"   xong ({time.time() - t0:.0f}s)", flush=True)

    T = pd.DataFrame(rows)
    T.to_csv(OUT / "shape_lab.csv", index=False)

    print()
    print("=" * 120)
    print("KIỂM CHỨNG ĐẶT TRƯỚC — nếu phần bù bất đối xứng là THẬT thì phần lớn")
    print("sáu họ phải cùng có gross DƯƠNG. Một họ dương / năm họ âm = nhiễu.")
    print("=" * 120)
    T["family"] = T["rule"].str.split("_").str[0]
    fam = T.groupby(["family", "tf"]).agg(
        n_cell=("ALL", "size"),
        gross_duong=("gross", lambda x: int((x > 0).sum())),
        gross_med=("gross", "median"),
        ALL_med=("ALL", "median"),
        OOS_med=("OOS", "median"),
        turn_med=("turn/năm", "median")).round(4)
    print(fam.to_string())

    print()
    print("=" * 120)
    print("25 Ô TỐT NHẤT")
    print("=" * 120)
    print(T.sort_values("ALL", ascending=False).head(25).to_string(index=False))

    print()
    print("=" * 120)
    print("CỔNG: FORM>0 & OOS>0 & ALL>0,40 & gross>0")
    print("=" * 120)
    k = T[(T["FORM"] > 0) & (T["OOS"] > 0) & (T["ALL"] > 0.40)
          & (T["gross"] > 0)].sort_values("ALL", ascending=False)
    print(k.to_string(index=False) if len(k) else "  KHÔNG CÓ")

    import pickle
    with open(OUT / "shape_lab_pnl.pkl", "wb") as fh:
        pickle.dump(series, fh)
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
