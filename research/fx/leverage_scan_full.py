# -*- coding: utf-8 -*-
"""Quét trần đòn bẩy qua CHÍNH SÁCH THẬT, trên TOÀN MẪU 2020–2026.

    .venv311\\Scripts\\python.exe research/fx/leverage_scan_full.py

KHÁC HAI BÀI TRƯỚC Ở CHỖ NÀO
=============================
    leverage_frontier_2026   đòn bẩy CỐ ĐỊNH, không qua chính sách
    leverage_by_phase        đòn bẩy CỐ ĐỊNH + lớp cắt, theo pha
    bài này                  chạy `POL.decide()` MỖI NGÀY, đúng như live

Khác biệt không nhỏ: chính sách tự thu hẹp đòn bẩy khi đệm tới sàn mỏng đi, nên
đòn bẩy THẬT luôn ≤ trần và MaxDD thấp hơn mô phỏng đòn bẩy cố định. Đo bằng trần
cố định rồi kết luận về trần chính sách là so hai thứ khác nhau.

⚠️ CHỐNG OVERFIT — VÌ SAO KHÔNG CHỌN THEO 2026
==============================================
MaxDD 2026 chỉ 5,73% ở trần 4,0x, còn 3,27 điểm % tới sàn 9%. Nhìn con số đó rồi
nới trần là **chọn tham số theo một giai đoạn êm**, đúng loại overfit mà
`REJECTED_DIRECTIONS` đã ghi lại.

Bài này quét trên TOÀN chuỗi 2020–2026 (1.630 ngày, gồm sốc COVID 2020 và chu kỳ
tăng lãi suất 2022) và báo ba con số cho mỗi trần:

    MaxDD toàn mẫu     rút sâu nhất ĐÃ xảy ra
    P(chết)            % cửa sổ 252 ngày chạm luật FTMO → MẤT TÀI KHOẢN
    P(bị cắt)          % cửa sổ chạm sàn nội bộ → hỏng lần thi, còn tài khoản

Tiêu chí chọn: trần LỚN NHẤT có **P(chết) = 0** và MaxDD dưới sàn nội bộ 9%, chọn
theo ĐƠN ĐIỆU (dừng ở mức đầu tiên vi phạm). Không lấy mức cao hơn dù bảng thô
trông như cho phép — bảng ~100 cửa sổ có nhiễu, và lấy đỉnh nhiễu là overfit ở
dạng tinh vi hơn.
"""
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from src.python.core.infra import ftmo  # noqa: E402
from src.python.execution import ftmo_leverage_policy as POL  # noqa: E402
from src.python.strategies import portfolio as PF  # noqa: E402

ACCOUNT = 100_000.0
HARD_ABS = ACCOUNT * (1 - ftmo.MAX_LOSS_HARD)
FLOOR_ABS = ACCOUNT * (1 - POL.DD_SELF_CAP)
CAPS = (3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 7.0, 8.0)
WINDOW = 252


def _run(r: np.ndarray, cap: float, start: int = 0,
         n: int | None = None) -> dict:
    """Chạy equity qua chính sách THẬT với trần `cap`."""
    eq = ACCOUNT
    peak = eq
    max_dd = 0.0
    worst = 0.0
    levs = []
    dead = cut = False
    end = len(r) if n is None else min(start + n, len(r))
    for x in r[start:end]:
        ds = eq
        dec = POL.decide(eq, ds, 9.33, leverage_max=cap, worst_day_bps=79.4)
        levs.append(dec.leverage)
        eq *= (1.0 + float(x) * dec.leverage / 1e4)
        day = (eq - ds) / ds
        worst = min(worst, day)
        peak = max(peak, eq)
        max_dd = max(max_dd, (peak - eq) / peak * 100.0)
        # LUẬT trước lớp cắt — một cú nhảy qua cả hai mốc là chết thật.
        if eq <= HARD_ABS or day <= -ftmo.DAILY_LOSS_HARD:
            dead = True
            break
        if eq <= FLOOR_ABS or day <= -ftmo.DAILY_FLATTEN_REALIZED:
            cut = True
            break
    return {"equity": eq, "max_dd": max_dd, "worst_day": worst * 100.0,
            "lev_tb": float(np.mean(levs)) if levs else 0.0,
            "dead": dead, "cut": cut}


def _windows(r: np.ndarray, cap: float) -> dict:
    """Quét mọi cửa sổ 252 ngày. Mỗi cửa sổ là một lần thi độc lập."""
    dead = cut = ok = 0
    for s in range(0, max(1, len(r) - WINDOW), 21):
        w = _run(r, cap, start=s, n=WINDOW)
        if w["dead"]:
            dead += 1
        elif w["cut"]:
            cut += 1
        else:
            ok += 1
    tot = max(dead + cut + ok, 1)
    return {"dead_%": dead / tot * 100.0, "cut_%": cut / tot * 100.0, "n": tot}


def main() -> int:
    print("Đang chạy backtest danh mục 27 chân… (~2 phút)")
    res = PF.backtest(start="2020-01-01")
    r = res.net_bps.dropna()
    print(f"  {len(r)} ngày · {r.index[0]:%Y-%m-%d} → {r.index[-1]:%Y-%m-%d}")
    a = r.to_numpy()

    r26 = r[r.index >= pd.Timestamp("2026-01-01")].to_numpy()

    print(f"\n{'=' * 96}")
    print("QUÉT TRẦN ĐÒN BẨY QUA CHÍNH SÁCH THẬT")
    print(f"sàn nội bộ {POL.DD_SELF_CAP:.0%} · cắt ngày "
          f"{ftmo.DAILY_FLATTEN_REALIZED:.0%} · luật FTMO "
          f"{ftmo.MAX_LOSS_HARD:.0%}/{ftmo.DAILY_LOSS_HARD:.0%}")
    print("=" * 96)
    print(f"{'trần':>6} | {'TOÀN MẪU 2020-2026':^38} | {'2026':^20} | "
          f"{'cửa sổ 252 ngày':^18}")
    print(f"{'':>6} | {'số dư cuối':>13} {'MaxDD':>7} {'ngày tệ':>8} {'lev TB':>6} | "
          f"{'lãi':>8} {'MaxDD':>7} | {'CHẾT':>7} {'bị cắt':>8}")
    print("-" * 96)

    best = None
    broken = False
    for cap in CAPS:
        full = _run(a, cap)
        y26 = _run(r26, cap)
        wnd = _windows(a, cap)
        # TIÊU CHÍ: KHÔNG chạm ngưỡng TUYỆT ĐỐI, và không cửa sổ nào chết.
        #
        # KHÔNG so `max_dd` (rút từ ĐỈNH) với `DD_SELF_CAP` — luật FTMO neo vào
        # SỐ DƯ BAN ĐẦU TĨNH. Tài khoản lên $300k rồi rơi về $260k là MaxDD 13%
        # từ đỉnh mà chưa hề chạm $91.000. Đây là lỗi đã sửa hai lần rồi ở
        # `account_report.py` và `leverage_frontier_2026.py`.
        ok = (wnd["dead_%"] <= 0.0 and wnd["cut_%"] <= 0.0
              and not full["dead"] and not full["cut"])
        if ok and not broken:
            best = cap
        elif not ok:
            broken = True
        mark = " ←" if abs(cap - POL.LEVERAGE_MAX) < 0.01 else "  "
        print(f"{cap:5.1f}x | ${full['equity']:>12,.0f} {full['max_dd']:6.2f}% "
              f"{full['worst_day']:7.2f}% {full['lev_tb']:5.2f}x | "
              f"{(y26['equity'] - ACCOUNT) / ACCOUNT * 100:+7.2f}% "
              f"{y26['max_dd']:6.2f}% | {wnd['dead_%']:6.1f}% {wnd['cut_%']:7.1f}%"
              f"{mark}{'' if ok else ' VƯỢT'}")

    print()
    if best:
        print(f"TRẦN LỚN NHẤT AN TOÀN: **{best:.1f}x**  "
              f"(không cửa sổ nào chạm sàn nội bộ hay luật FTMO)")
        # Điểm BÃO HOÀ: trần cao hơn mức này không đổi gì, vì ràng buộc ĐUÔI
        # (`lev_tail = đệm_ngày / (1,3 × |ngày tệ nhất|)`) đã chặn trước.
        sat = _run(a, 99.0)
        print(f"  Đòn bẩy THỰC bão hoà ở {sat['lev_tb']:.2f}x — trần cao hơn mức "
              f"này không còn là ràng buộc, ĐUÔI mới là.")
        if best > POL.LEVERAGE_MAX + 0.01:
            print(f"  → nới được từ {POL.LEVERAGE_MAX:.1f}x lên {best:.1f}x")
        elif best < POL.LEVERAGE_MAX - 0.01:
            print(f"  → PHẢI HẠ từ {POL.LEVERAGE_MAX:.1f}x xuống {best:.1f}x")
        else:
            print(f"  → khớp trần hiện tại {POL.LEVERAGE_MAX:.1f}x, giữ nguyên")

    print("\n⚠️ CHỐNG OVERFIT")
    print("  · Chọn theo cột TOÀN MẪU và P(chết), KHÔNG theo cột 2026.")
    print("    2026 là 6,5 tháng êm; nới trần theo nó là chọn tham số trên một")
    print("    giai đoạn thuận lợi — đúng loại lỗi đã vào `REJECTED_DIRECTIONS`.")
    print("  · Dừng ở mức ĐẦU TIÊN vượt, không lấy mức cao hơn dù bảng trông cho")
    print("    phép: ~100 cửa sổ thì P(chết) có nhiễu, lấy đỉnh nhiễu là overfit.")
    print("  · Mẫu chứa sốc 2020 và 2022, nhưng KHÔNG chứa cú sốc chưa xảy ra.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
