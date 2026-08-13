# -*- coding: utf-8 -*-
"""Trần đòn bẩy 3,5x còn đúng không — đo lại trên TOÀN MẪU gồm 2026.

    .venv311\\Scripts\\python.exe research/fx/leverage_frontier_2026.py

VÌ SAO PHẢI ĐO LẠI
===================
`ftmo_leverage_policy.LEVERAGE_MAX = 3.5` đo trên mẫu 2020→2024 (3,51x cho MaxDD
đúng 9,00%). Từ đó tới nay có thêm hai năm rưỡi dữ liệu, và mô hình chi phí cross
vừa đổi (`spread_pips` từ ×1,5 sang `max(×3,0, sàn FTMO)`) — chi phí đắt hơn 2–3
lần thì đường lợi nhuận đổi, và MaxDD theo đòn bẩy cũng đổi.

Vòng 2026 cho MaxDD chỉ 3,09% ở đúng 3,5x, tức đòn bẩy CHẠM TRẦN suốt kỳ mà chưa
dùng hết một phần ba ngân sách rủi ro. Câu hỏi tự nhiên: có nới được không?

⚠️ KHÔNG ĐƯỢC TRẢ LỜI BẰNG 6,5 THÁNG ÊM
========================================
MaxDD **không** tỷ lệ thuận đòn bẩy. Tương quan giữa các chân tăng lên đúng lúc
thị trường căng, nên nhân đôi đòn bẩy có thể nhân ba MaxDD. 2026 là giai đoạn êm;
suy từ nó ra trần mới là đúng cách mất tài khoản.

Bài này quét đòn bẩy trên TOÀN chuỗi 2020→2026 — gồm cả cú sốc 2020 và 2022 — rồi
đọc ba con số cho mỗi mức:

    MaxDD toàn mẫu      so với sàn nội bộ 9% và luật FTMO 10%
    ngày tệ nhất        so với mốc ngày 5%
    P(vi phạm)          quét mọi cửa sổ 252 ngày, đếm cửa sổ chạm ngưỡng chết

Con số thứ ba mới là con số quyết định: MaxDD trung bình không nói gì về xác suất
mất tài khoản, mà FTMO chỉ cần chạm MỘT LẦN là hết.
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
FLOOR_ABS = ACCOUNT * (1 - POL.DD_SELF_CAP)      # sàn nội bộ 9% → $91.000
HARD_ABS = ACCOUNT * (1 - ftmo.MAX_LOSS_HARD)    # luật FTMO 10% → $90.000
LEVELS = (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0)


def _walk(r: np.ndarray, lev: float) -> dict:
    """Chạy equity qua chuỗi lợi nhuận ngày ở đòn bẩy `lev`. `r` tính bằng **bps**.

    ⚠️ PHẢI DÙNG `res.net_bps`, KHÔNG PHẢI `res.net`.
    Bản đầu của bài này dùng `res.net` (chuỗi đã CHUẨN HOÁ theo σ từng chân) rồi
    quy ước "1,0x = 1%/ngày". Sai đơn vị: `net.std` = 0,232 chứ không phải 1,0, nên
    phép quy đổi thổi phồng biến động **2,6 lần** và cho ra MaxDD 18,35% ở 3,5x —
    mâu thuẫn thẳng với số đã đo trong `ftmo_leverage_policy` (3,51x → 9,00%).

    Con số đúng nằm ở `net_bps`: đơn vị bps THẬT trên giá, `std` = 9,05 bps/ngày ở
    phơi nhiễm 1,0x. Đây cũng chính là đại lượng mà `portfolio_sizing` dùng —
    `lot_i = equity × leverage × w_i / notional_i` cho phơi nhiễm `leverage` lần
    equity, và lợi nhuận ngày bằng `equity × leverage × bps/1e4`.

    Mâu thuẫn với một con số đã đo là dấu hiệu công thức sai, không phải phát hiện
    mới — kiểm lại đơn vị trước khi tin kết quả.
    """
    eq = ACCOUNT
    peak = eq
    max_dd = 0.0
    worst_day = 0.0
    day_start = eq
    hit_floor = hit_hard = hit_daily = 0
    curve = np.empty(len(r))
    for i, x in enumerate(r):
        day_start = eq
        eq *= (1.0 + x * lev / 1e4)
        curve[i] = eq
        peak = max(peak, eq)
        max_dd = max(max_dd, (peak - eq) / peak * 100.0)
        d = (eq - day_start) / day_start * 100.0
        worst_day = min(worst_day, d)
        if d <= -ftmo.DAILY_LOSS_HARD * 100:
            hit_daily += 1
        if eq <= FLOOR_ABS:
            hit_floor += 1
        if eq <= HARD_ABS:
            hit_hard += 1
    return {"equity_cuoi": eq, "max_dd": max_dd, "ngay_te_nhat": worst_day,
            "cham_san_9": hit_floor, "cham_luat_10": hit_hard,
            "cham_ngay_5": hit_daily, "curve": curve}


def _p_violate(r: np.ndarray, lev: float, window: int = 252) -> float:
    """P(vi phạm) — tỷ lệ cửa sổ 252 ngày có ÍT NHẤT MỘT lần chạm ngưỡng chết.

    Quét mọi điểm bắt đầu cách nhau 21 ngày. Đây là con số quyết định: FTMO neo
    max loss vào SỐ DƯ BAN ĐẦU TĨNH, nên mỗi cửa sổ là một "lần thi" độc lập, và
    chỉ cần chạm $90.000 một lần trong cửa sổ đó là mất tài khoản.
    """
    if len(r) <= window:
        return float("nan")
    bad = tot = 0
    for s in range(0, len(r) - window, 21):
        eq = ACCOUNT
        viol = False
        for x in r[s:s + window]:
            ds = eq
            eq *= (1.0 + x * lev / 1e4)
            if eq <= HARD_ABS or (eq - ds) / ds <= -ftmo.DAILY_LOSS_HARD:
                viol = True
                break
        bad += viol
        tot += 1
    return bad / tot * 100.0 if tot else float("nan")


def main() -> int:
    print("Đang chạy backtest danh mục 27 chân (chi phí MỚI)… (~2 phút)")
    res = PF.backtest(start="2020-01-01")
    # `net_bps` = lợi nhuận ngày của danh mục tính bằng BPS ở phơi nhiễm 1,0x.
    net = res.net_bps.dropna()
    r = net.to_numpy()
    print(f"  {len(r)} ngày · {net.index[0]:%Y-%m-%d} → {net.index[-1]:%Y-%m-%d}")
    print(f"  trần hiện tại {POL.LEVERAGE_MAX:.2f}x · sàn nội bộ "
          f"{POL.DD_SELF_CAP:.0%} · luật FTMO {ftmo.MAX_LOSS_HARD:.0%}")
    print()

    print("=" * 92)
    print("BIÊN ĐÒN BẨY — TOÀN MẪU 2020→2026 (gồm sốc 2020 và 2022)")
    print("=" * 92)
    print(f"{'đòn bẩy':>8} {'số dư cuối':>13} {'MaxDD':>8} {'ngày tệ nhất':>13} "
          f"{'chạm 9%':>8} {'chạm 10%':>9} {'P(vi phạm)':>11}  kết luận")
    print("-" * 92)

    for lev in LEVELS:
        w = _walk(r, lev)
        pv = _p_violate(r, lev)
        # ⚠️ TIÊU CHÍ PHẢI LÀ NGƯỠNG TUYỆT ĐỐI, KHÔNG PHẢI MaxDD TỪ ĐỈNH.
        #
        # Bản đầu so `max_dd` (rút từ ĐỈNH chạy dần) với `DD_SELF_CAP` — sai, và
        # sai đúng kiểu đã từng sửa ở `research/fx/account_report.py` ngày 14/08.
        # Luật FTMO neo vào SỐ DƯ BAN ĐẦU TĨNH: tài khoản lên $130k rồi rơi về
        # $95k là DD 27% từ đỉnh nhưng VẪN HỢP LỆ; chạm $89.999 một lần là hết.
        # `ftmo_leverage_policy` cũng vậy — `floor_abs = account × (1 − 0,09)` là
        # mốc $91.000 tuyệt đối.
        #
        # Nên cột quyết định là `cham_san_9` / `cham_luat_10` (số lần equity chạm
        # ngưỡng) và `P(vi phạm)`, KHÔNG phải `max_dd`.
        if w["cham_luat_10"] > 0:
            verdict = "VI PHẠM LUẬT — loại"
        elif w["cham_san_9"] > 0:
            verdict = "chạm sàn nội bộ — loại"
        elif abs(w["ngay_te_nhat"]) >= ftmo.DAILY_LOSS_HARD * 100:
            verdict = "VI PHẠM mốc ngày 5%"
        elif pv > 0.0:
            verdict = f"P(vi phạm) {pv:.1f}% — RỦI RO"
        else:
            verdict = "an toàn"
        mark = " ←ĐANG DÙNG" if abs(lev - POL.LEVERAGE_MAX) < 1e-9 else ""
        print(f"{lev:7.1f}x ${w['equity_cuoi']:>12,.0f} {w['max_dd']:7.2f}% "
              f"{w['ngay_te_nhat']:12.2f}% {w['cham_san_9']:8} "
              f"{w['cham_luat_10']:9} {pv:10.1f}%  {verdict}{mark}")

    # ── Mức LỚN NHẤT còn giữ MaxDD dưới sàn nội bộ
    print()
    # Mức lớn nhất mà equity KHÔNG chạm sàn tuyệt đối VÀ P(vi phạm) = 0.
    #
    # Hai điều kiện, không phải một: không chạm trên chuỗi lịch sử là điều kiện
    # cần; P(vi phạm) = 0 trên mọi cửa sổ 252 ngày mới là điều kiện đủ. Một mức
    # đòn bẩy sống sót được chuỗi ĐẦY ĐỦ vẫn có thể giết một tài khoản BẮT ĐẦU
    # SAI THỜI ĐIỂM — và người vận hành thật thì bắt đầu ở một thời điểm cụ thể.
    best = None
    for lev in np.arange(1.0, 8.01, 0.05):
        w = _walk(r, float(lev))
        if (w["cham_san_9"] == 0 and w["cham_luat_10"] == 0
                and _p_violate(r, float(lev)) <= 0.0):
            best = (float(lev), w["max_dd"])
        else:
            break
    if best:
        print(f"ĐÒN BẨY LỚN NHẤT không chạm sàn {POL.DD_SELF_CAP:.0%} "
              f"VÀ P(vi phạm)=0: **{best[0]:.2f}x** "
              f"(MaxDD từ đỉnh {best[1]:.2f}%)")
        d = best[0] - POL.LEVERAGE_MAX
        if d > 0.05:
            print(f"  → cao hơn trần hiện tại {POL.LEVERAGE_MAX:.2f}x "
                  f"{d:+.2f}x. Nới được, NHƯNG xem cảnh báo bên dưới.")
        elif d < -0.05:
            print(f"  → THẤP HƠN trần hiện tại {POL.LEVERAGE_MAX:.2f}x "
                  f"{d:+.2f}x — trần đang QUÁ CAO với chi phí mới. Phải hạ.")
        else:
            print(f"  → khớp trần hiện tại. Giữ nguyên {POL.LEVERAGE_MAX:.2f}x.")

    print()
    print("⚠️ ĐỌC KỸ TRƯỚC KHI ĐỔI `LEVERAGE_MAX`")
    print("  · MaxDD toàn mẫu là MỘT lần rút xuống sâu nhất ĐÃ XẢY RA, không phải")
    print("    chặn trên. Cú sốc chưa từng thấy thì mẫu không chứa nó.")
    print("  · Cột P(vi phạm) mới là con số quyết định: nó đếm bao nhiêu cửa sổ")
    print("    252 ngày sẽ MẤT TÀI KHOẢN. MaxDD trung bình đẹp mà P(vi phạm) > 0")
    print("    thì vẫn là loại — FTMO chỉ cần chạm một lần.")
    print("  · Thứ tự ưu tiên: Account Survival > FTMO Compliance > … > Profit.")
    print("    Nới đòn bẩy là đánh đổi TRỰC TIẾP hai vế đầu lấy vế cuối.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
