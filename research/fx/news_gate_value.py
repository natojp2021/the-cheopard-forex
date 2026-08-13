"""Vòng 63 — CỔNG TIN CÓ ĐÁNG CHẶN KHÔNG? Đo, không đoán.

CÂU HỎI
=======
Cổng tin chặn mở lệnh mới vào ngày có NFP/FOMC/CPI/ECB/BOE. Việc đó có hai chi phí và
một lợi ích, và cả ba đều đo được:

    chi phí 1   mất những lệnh lẽ ra có lãi
    chi phí 2   độ phức tạp vận hành + một chỗ nữa để hỏng im lặng
    lợi ích     tránh những lệnh lẽ ra lỗ nặng

Một cổng chỉ đáng giữ nếu lợi ích lớn hơn. Điều đó KHÔNG hiển nhiên: 14 chiến lược
hiện tại giao dịch cross (AUDCAD, GBPNZD, GBPAUD, NZDCAD) — những cặp KHÔNG chứa USD.
Lịch chỉ có năm loại sự kiện, ba trong đó là tin Mỹ (NFP, CPI, FOMC = 614/968 dòng).

Nếu tin Mỹ không làm cross tệ đi thì chặn theo nó là mất lệnh mà không giảm rủi ro.

CÁCH ĐO — BA TẦNG, TỪ THÔ ĐẾN TINH
===================================
  A. NGÀY tin vs ngày thường: lợi nhuận trung bình mỗi lệnh VÀO trong ngày đó
  B. tách theo LOẠI sự kiện — tin Mỹ có khác tin châu Âu không
  C. mô phỏng LẠI toàn bộ chiến lược VỚI cổng bật, so Sharpe/MaxDD với bản không cổng

Tầng C là tầng quyết định: nó tính đúng thứ ta quan tâm (Sharpe sau khi bỏ lệnh), chứ
không chỉ so trung bình. Một cổng có thể bỏ đúng những lệnh lỗ nặng mà vẫn làm Sharpe
tệ đi nếu nó bỏ quá nhiều lệnh lãi cùng lúc.

GIẢ THUYẾT ĐẶT TRƯỚC
====================
Chiến lược hồi quy trung bình thua trong chế độ có xu hướng. Tin lớn tạo bước nhảy
mang tính xu hướng. Nên DỰ ĐOÁN: lệnh vào ngày tin có net thấp hơn. Nếu đo ra ngược
lại thì cổng phải bị gỡ, không phải giữ lại "cho an toàn".
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import numpy as np
import pandas as pd

from src.python.ai import news_guard as NG
from src.python.strategies import zband_core as ZB
from research.fx.trade_lab import load_crosses

pd.set_option("display.width", 240, "display.max_columns", 30, "display.max_rows", 200)
FORM_END = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"

# 9 chân Z-Band đang chạy: (module, khung, công cụ, N, k, ts)
LEGS: Tuple[Tuple[str, str, str, int, float, float], ...] = (
    ("h1", "H1", "AUDCAD", 48, 1.5, 1.0), ("h1", "H1", "NZDCAD", 48, 1.5, 1.0),
    ("h1", "H1", "GBPAUD", 96, 2.0, 1.0),
    ("m30", "M30", "GBPAUD", 96, 2.5, 1.0), ("m30", "M30", "AUDCAD", 96, 1.5, 1.0),
    ("m30", "M30", "NZDCAD", 96, 1.5, 1.0),
    ("h4", "H4", "GBPNZD", 12, 1.5, 1.0), ("h4", "H4", "AUDCAD", 24, 2.0, 2.0),
    ("h4", "H4", "GBPAUD", 24, 1.5, 3.0),
)


def event_days() -> Dict[str, pd.DataFrame]:
    """Ngày có sự kiện, tách theo loại. Dùng chính lịch mà cổng dùng."""
    df = NG.load_calendar()
    if df is None or df.empty:
        raise SystemExit("không đọc được lịch kinh tế")
    df = df.copy()
    df["ngày"] = df["time"].dt.tz_convert("UTC").dt.normalize().dt.tz_localize(None)
    return df


def sharpe(s: pd.Series, lo=None, hi=None) -> float:
    if lo is not None:
        s = s[s.index >= lo]
    if hi is not None:
        s = s[s.index < hi]
    sd = float(s.std(ddof=1))
    return float(s.mean()) / sd * np.sqrt(252) if sd > 0 and len(s) > 60 else np.nan


def main() -> None:
    t0 = time.time()
    cal = event_days()
    us_events = {"NFP", "CPI", "FOMC"}
    us_days = set(cal[cal["event"].isin(us_events)]["ngày"])
    eu_days = set(cal[~cal["event"].isin(us_events)]["ngày"])
    news_days = us_days | eu_days
    print(f"Lịch: {len(cal)} sự kiện · {len(ngay_tin)} ngày có tin "
          f"({len(ngay_my)} ngày tin Mỹ, {len(ngay_eu)} ngày tin EU/UK)")

    cache = {tf: {i.name: i for i in load_crosses(tf)} for tf in ("M30", "H1", "H4")}
    rows_a: List[Dict] = []
    rows_c: List[Dict] = []

    for _, tf, inst, N, k, ts in LEGS:
        ins = cache[tf][inst]
        cfg = ZB.ZBandConfig(f"ZBand{inst}{tf}", inst, tf, N, k, ts)
        res = ZB.run(ins.df, ins.cost_1rt_bps, ins.swap_bps_per_bar, cfg)
        T = res.trades.copy()
        if T.empty:
            continue
        T["ngày_vào"] = pd.DatetimeIndex(T["entry_time"]).normalize()
        is_us = T["ngày_vào"].isin(us_days)
        is_eu = T["ngày_vào"].isin(eu_days)
        is_news = is_us | is_eu

        def m(mask) -> Tuple[int, float, float]:
            sub = T[mask]
            if sub.empty:
                return 0, np.nan, np.nan
            return (len(sub), float(sub["net_bps"].mean()),
                    float((sub["net_bps"] > 0).mean()) * 100)

        n_t, net_t, w_t = m(is_news)
        n_k, net_k, w_k = m(~is_news)
        n_m, net_m, _ = m(is_us)
        n_e, net_e, _ = m(is_eu)
        rows_a.append({
            "chân": f"{inst}·{tf}", "n_tổng": len(T),
            "n_ngày_tin": n_t, "net_ngày_tin": round(net_t, 2), "thắng_tin%": round(w_t, 1),
            "n_ngày_thường": n_k, "net_ngày_thường": round(net_k, 2),
            "thắng_thường%": round(w_k, 1),
            "chênh": round(net_t - net_k, 2),
            "net_tin_MỸ": round(net_m, 2), "n_Mỹ": n_m,
            "net_tin_EU": round(net_e, 2), "n_EU": n_e})

        # ── tầng C: mô phỏng lại VỚI cổng bật (bỏ lệnh vào ngày tin)
        days_without_news = res.pnl_daily
        T2 = T[~is_news]
        days_with_news = (T2.set_index("exit_time")["net_bps"].resample("1D").sum().fillna(0.0)
                if not T2.empty else pd.Series(dtype=float))
        # bản chỉ chặn tin của ĐỒNG TIỀN có trong cặp
        ccy_in = [c for c in ("USD", "EUR", "GBP") if c in inst]
        mask_lq = is_eu if ("GBP" in inst or "EUR" in inst) else pd.Series(
            False, index=T.index)
        T3 = T[~mask_lq]
        d_lq = (T3.set_index("exit_time")["net_bps"].resample("1D").sum().fillna(0.0)
                if not T3.empty else pd.Series(dtype=float))

        def dd(s: pd.Series) -> float:
            c = s.cumsum()
            return float((c.cummax() - c).max()) / 100.0

        rows_c.append({
            "chân": f"{inst}·{tf}",
            "Sharpe_không_cổng": round(sharpe(days_without_news), 3),
            "Sharpe_chặn_mọi_tin": round(sharpe(days_with_news), 3),
            "Sharpe_chặn_tin_liên_quan": round(sharpe(d_lq), 3),
            "MaxDD_không": round(dd(days_without_news), 2),
            "MaxDD_chặn_mọi": round(dd(days_with_news), 2),
            "lệnh_mất": len(T) - len(T2),
            "%lệnh_mất": round((len(T) - len(T2)) / len(T) * 100, 1)})

    A = pd.DataFrame(rows_a)
    C = pd.DataFrame(rows_c)
    A.to_csv(OUT / "news_gate_value_A.csv", index=False)
    C.to_csv(OUT / "news_gate_value_C.csv", index=False)

    print()
    print("=" * 150)
    print("A. LỆNH VÀO NGÀY CÓ TIN vs NGÀY THƯỜNG (net bps mỗi lệnh)")
    print("=" * 150)
    print(A.to_string(index=False))
    print()
    print(f"  chênh lệch trung vị: {A['chênh'].median():+.2f} bps/lệnh · "
          f"{int((A['chênh'] < 0).sum())}/{len(A)} chân TỆ HƠN vào ngày tin")
    print(f"  tin MỸ  net trung vị {A['net_tin_MỸ'].median():+.2f} bps "
          f"(ngày thường {A['net_ngày_thường'].median():+.2f})")
    print(f"  tin EU  net trung vị {A['net_tin_EU'].median():+.2f} bps")

    print()
    print("=" * 150)
    print("C. MÔ PHỎNG LẠI VỚI CỔNG BẬT — tầng quyết định")
    print("=" * 150)
    print(C.to_string(index=False))
    print()
    best_without = C["Sharpe_không_cổng"].median()
    best_new = C["Sharpe_chặn_mọi_tin"].median()
    best_liquid = C["Sharpe_chặn_tin_liên_quan"].median()
    print(f"  Sharpe trung vị — không cổng {tot_khong:.3f} · chặn MỌI tin "
          f"{tot_moi:.3f} · chặn tin LIÊN QUAN {tot_lq:.3f}")
    n_best = int((C["Sharpe_chặn_mọi_tin"] > C["Sharpe_không_cổng"]).sum())
    print(f"  chặn mọi tin làm TỐT HƠN ở {n_tot}/{len(C)} chân · "
          f"mất trung vị {C['%lệnh_mất'].median():.1f}% số lệnh")

    print()
    print("── KẾT LUẬN")
    if best_new > best_without:
        print("   Cổng chặn CÓ giá trị đo được → giữ, bật mặc định.")
    elif best_liquid > best_without:
        print("   Chặn MỌI tin thì hại, nhưng chặn tin LIÊN QUAN thì lợi →")
        print("   thu hẹp cổng về đúng đồng tiền có trong cặp.")
    else:
        print("   Cổng KHÔNG có giá trị đo được trên rổ hiện tại (toàn cross không")
        print("   chứa USD). Giữ code nhưng để MẶC ĐỊNH TẮT, và ghi rõ lý do —")
        print("   bật lại khi danh mục có công cụ chứa USD/EUR/GBP.")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
