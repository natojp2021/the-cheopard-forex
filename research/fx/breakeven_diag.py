"""Vòng 58 — CHẨN ĐOÁN NGƯỠNG HOÀ VỐN Sepp & Lucic (2026). Tính TRƯỚC khi backtest.

VÌ SAO VÒNG NÀY KHÁC 57 VÒNG TRƯỚC
===================================
57 vòng trước đều là QUÉT: thử một họ tín hiệu, đo Sharpe, giữ hay loại. Cách đó có
hai vấn đề — mỗi lần thử là một bậc tự do (nguy cơ overfit), và khi thất bại nó không
nói được vì sao thất bại hay nên thử gì tiếp.

Sepp & Lucic (arXiv 2607.19497, "The Science and Practice of Trend-Following Systems",
07/2026) cho một công cụ khác hẳn: **ngưỡng chi phí hoà vốn tính thẳng từ dữ liệu**,
không cần backtest, không tốn bậc tự do.

    c* = sqrt(π / (2a)) × φ / (1 − φ)          (phương trình 6.13, giới hạn span dài)

    a  = số kỳ mỗi năm của khung đang xét
    φ  = tự tương quan bậc một của lợi nhuận ĐÃ CHUẨN HOÁ theo biến động

Ý nghĩa: nếu chi phí khứ hồi thực tế **vượt** c* thì KHÔNG span nào cứu được — mọi
chiến lược dựa trên tự tương quan bậc một trên công cụ đó, ở khung đó, đều lỗ. Bài
báo tính cho a = 260 và φ = 0,05 ra c* ≈ 37-41 bp, và ghi rằng chi phí thực tế trên
hợp đồng tương lai là 40-60 bp — tức trend-following ở khung ngày chỉ vừa đủ hoà vốn.

HAI CHIỀU, KHÔNG CHỈ MỘT
========================
Công thức đối xứng theo dấu của φ:
    φ > 0  → có ĐÀ. Chiến lược thuận chiều khai thác được.
    φ < 0  → có HỒI QUY. Chiến lược ngược chiều khai thác được, cùng ngưỡng |c*|.

Đây là lý do vòng này trả lời được câu hỏi mà 57 vòng quét không trả lời được: **ở
khung nào, trên công cụ nào, còn chỗ cho bất kỳ chiến lược nào.**

DỰ ĐOÁN ĐẶT TRƯỚC (ghi lại để không tự lừa mình sau khi thấy kết quả)
======================================================================
Các vòng trước đo được: mọi họ xu hướng có gross ÂM ở M30/H1 trên cross (vòng 53),
và họ hồi quy có gross DƯƠNG (vòng 50-51, 57). Nếu chẩn đoán này đúng thì φ trên
cross ở M30/H1 phải ÂM. Nếu nó ra dương thì hoặc chẩn đoán không áp dụng được cho
FX, hoặc một trong hai phép đo sai — cả hai đều phải điều tra trước khi đi tiếp.
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

from research.fx.trade_lab import load_crosses, load_majors
from src.python.shared import asset_profile as AP

pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 400)
OUT = ROOT / "reports" / "fx_research"
FORM_END = pd.Timestamp("2024-01-01")

# Số kỳ mỗi năm. FX chạy 24/5 nên một ngày giao dịch có đủ 24 giờ.
PERIODS_YEAR = {"M30": 252 * 48, "H1": 252 * 24, "H4": 252 * 6, "D1": 252}
VOL_SPAN = {"M30": 33 * 48, "H1": 33 * 24, "H4": 33 * 6, "D1": 33}


def breakeven_cost_bps(cost_bps: float, periods_per_year: int) -> float:
    """Ngưỡng chi phí hoà vốn, đơn vị bps. Sepp & Lucic phương trình 6.13.

    Trả giá trị TUYỆT ĐỐI: dấu của φ cho biết chiến lược nào khai thác được (đà hay
    hồi quy), còn độ lớn cho biết chi phí tối đa chịu được.
    """
    if not np.isfinite(cost_bps) or abs(cost_bps) >= 1.0:
        return np.nan
    return float(np.sqrt(np.pi / (2.0 * periods_per_year))
                 * abs(cost_bps) / (1.0 - abs(cost_bps)) * 1e4)


def vol_normalised_returns(close: pd.Series, span: int) -> pd.Series:
    """Lợi nhuận log chia cho σ trượt — chuẩn hoá của Sepp & Lucic §5.

    Chuẩn hoá là bắt buộc, không phải tuỳ chọn: tự tương quan của lợi nhuận THÔ trên
    FX bị chi phối bởi cụm biến động (giai đoạn động thì mọi lợi nhuận đều lớn), và
    thứ đó không giao dịch được. Chia cho σ trượt tách cụm biến động ra khỏi tín hiệu.
    """
    r = np.log(close).diff()
    sd = r.ewm(span=span, min_periods=span // 4).std()
    return (r / sd.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)


def autocorr(z: pd.Series, lag: int = 1) -> float:
    s = z.dropna()
    if len(s) < 500:
        return np.nan
    return float(s.autocorr(lag=lag))


def t_stat(cost_bps: float, n: int) -> float:
    """t của tự tương quan. Nhiễu trắng có sai số chuẩn ≈ 1/√n."""
    if not np.isfinite(cost_bps) or n < 30:
        return np.nan
    return cost_bps * np.sqrt(n)


def main() -> None:
    t0 = time.time()
    rows: List[Dict] = []
    for tf in ("M30", "H1", "H4"):
        a = PERIODS_YEAR[tf]
        span = VOL_SPAN[tf]
        universe = load_crosses(tf) + load_majors(tf)
        print(f"── {tf}: {len(universe)} công cụ · a = {a:,} kỳ/năm", flush=True)
        for ins in universe:
            z = vol_normalised_returns(ins.df["close"], span)
            n = int(z.notna().sum())
            cost_bps = autocorr(z, 1)
            cost_form = autocorr(z[z.index < FORM_END], 1)
            cost_oos = autocorr(z[z.index >= FORM_END], 1)
            c_star = breakeven_cost_bps(cost_bps, a)
            cost = ins.cost_1rt_bps
            rows.append({
                "tf": tf, "công cụ": ins.name,
                "loại": "major" if ins.name in AP.FX_ALL else "cross",
                "n": n,
                "φ": round(cost_bps, 5) if np.isfinite(cost_bps) else np.nan,
                "t(φ)": round(t_stat(cost_bps, n), 2),
                "φ_FORM": round(cost_form, 5) if np.isfinite(cost_form) else np.nan,
                "φ_OOS": round(cost_oos, 5) if np.isfinite(cost_oos) else np.nan,
                "cùng dấu": bool(np.isfinite(cost_form) and np.isfinite(cost_oos)
                                 and np.sign(cost_form) == np.sign(cost_oos)),
                "c* bps": round(c_star, 3),
                "chi phí bps": round(cost, 3),
                "biên": round(c_star - cost, 3),
                "khai thác": ("HỒI QUY" if cost_bps < 0 else "ĐÀ") if np.isfinite(cost_bps) else "—",
            })
        print(f"   xong ({time.time() - t0:.0f}s)", flush=True)

    T = pd.DataFrame(rows)
    T.to_csv(OUT / "breakeven_diag.csv", index=False)

    print()
    print("=" * 135)
    print("A. TỔNG QUAN THEO KHUNG — φ là tự tương quan bậc 1 của lợi nhuận chuẩn hoá")
    print("=" * 135)
    g = T.groupby(["tf", "loại"]).agg(
        n_cụ=("φ", "size"),
        φ_trung_vị=("φ", "median"),
        t_trung_vị=("t(φ)", "median"),
        cùng_dấu=("cùng dấu", "sum"),
        c_star_tv=("c* bps", "median"),
        chi_phí_tv=("chi phí bps", "median"),
        biên_tv=("biên", "median"),
        số_dương_biên=("biên", lambda x: int((x > 0).sum()))).round(4)
    print(g.to_string())

    print()
    print("=" * 135)
    print("B. CÔNG CỤ CÓ BIÊN DƯƠNG (c* > chi phí) — nơi CÒN CHỖ cho chiến lược")
    print("=" * 135)
    k = T[T["biên"] > 0].sort_values("biên", ascending=False)
    print(f"{len(k)}/{len(T)} ô có biên dương")
    print(k.head(40).to_string(index=False) if len(k) else "  KHÔNG CÓ Ô NÀO")

    print()
    print("=" * 135)
    print("C. LỌC CHẶT: biên > 0 VÀ |t(φ)| > 3 VÀ φ CÙNG DẤU trên FORM và OOS")
    print("=" * 135)
    kk = T[(T["biên"] > 0) & (T["t(φ)"].abs() > 3.0) & T["cùng dấu"]].sort_values(
        "biên", ascending=False)
    print(kk.to_string(index=False) if len(kk) else "  KHÔNG CÓ Ô NÀO")

    print()
    print("── KIỂM CHỨNG DỰ ĐOÁN ĐẶT TRƯỚC: φ trên cross ở M30/H1 phải ÂM")
    for tf in ("M30", "H1"):
        sub = T[(T["tf"] == tf) & (T["loại"] == "cross")]
        if len(sub):
            print(f"   {tf} cross: φ trung vị {sub['φ'].median():+.5f} · "
                  f"{int((sub['φ'] < 0).sum())}/{len(sub)} công cụ có φ âm  "
                  f"{'KHỚP dự đoán' if sub['φ'].median() < 0 else 'NGƯỢC dự đoán'}")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
