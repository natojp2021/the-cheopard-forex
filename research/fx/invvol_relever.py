# -*- coding: utf-8 -*-
"""Trọng số nghịch đảo σ + TÁI CẤP đòn bẩy trên ngân sách vừa giải phóng.

    .venv311\\Scripts\\python.exe research/fx/invvol_relever.py

VÌ SAO PHẢI CÓ VÒNG HAI
========================
`invvol_weights.py` đo trọng số nghịch đảo σ ở ĐÒN BẨY GIỮ NGUYÊN và kết luận nghe
như một sự đánh đổi tồi:

    lãi 2026 −1,60 điểm % · MaxDD −0,22 điểm %

Nhưng so ở cùng đòn bẩy là so SAI, vì đòn bẩy trong hệ này không phải hằng số —
nó là HÀM của rủi ro đo được:

    lev_tail = đệm_ngày / (TAIL_BUFFER × |ngày tệ nhất|)

Và trọng số nghịch đảo σ đổi đúng cái mẫu số đó:

    | sơ đồ      | ngày tệ nhất | σ ngày | lev_tail |
    | ĐỀU        |     76,0 bps | 9,05   |   5,48x  |
    | INV-VOL 20 |     48,0 bps | 6,85   |   8,68x → chạm trần 6,0x |
    | INV-VOL 60 |     98,0 bps | 6,70   |   4,25x  |

Đuôi mỏng đi 37% thì ràng buộc đuôi HẾT chặn, và trần cứng 6,0x thành thứ chặn.
Phần lãi "mất" ở vòng một là lãi chưa lấy lại — đo lại sau khi tái cấp đòn bẩy mới
là phép so công bằng.

INV-VOL 60 đi hướng ngược: đuôi DÀY LÊN (98,0 bps) và 4,9% cửa sổ CHẾT. Cửa sổ dài
làm trọng số phản ứng chậm, giữ nguyên tỷ trọng lớn ở chân vừa chuyển sang chế độ
biến động cao. Nó bị loại, và nó cũng là bằng chứng rằng 20 ngày không phải "cửa sổ
nào cũng được" — con số 20 của Olszweski có nội dung.

CHỌN THEO NGÂN SÁCH, KHÔNG THEO LỢI NHUẬN
==========================================
Cùng bộ tiêu chí với `risk_budget_tune.py`, theo đúng thứ tự ưu tiên của dự án:

    1. P(chết) = 0        trên mọi cửa sổ 252 ngày — điều kiện LOẠI
    2. P(bị cắt) ≤ 5%
    3. MaxDD ≤ 9% và ngày tệ nhất ≤ 4%
    4. trong số còn lại, lấy trần THẤP NHẤT còn thoả — không lấy trần lãi nhất

Điều 4 là chỗ chống overfit: dừng ở bậc đầu tiên đủ dùng, không leo tới đỉnh bảng.
`worst_day_bps` truyền vào chính sách là SỐ ĐO của chính sơ đồ trọng số đó, không
phải một tham số được chọn.
"""
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

sys.argv = ["invvol_relever"]
import research.fx.invvol_weights as IV  # noqa: E402

ACCOUNT = 100_000.0
HARD_ABS = ACCOUNT * (1 - ftmo.MAX_LOSS_HARD)
FLOOR_ABS = ACCOUNT * (1 - POL.DD_SELF_CAP)
START26 = pd.Timestamp("2026-01-01")
WINDOW = 252

BUDGET_MAXDD, BUDGET_DAY, BUDGET_CUT = 9.0, 4.0, 5.0
GRID_CAP = (5.0, 6.0, 7.0, 8.0, 9.0)


def _decide(eq: float, ds: float, wd_bps: float, cap: float) -> float:
    """Bản sao `POL.decide` với `worst_day_bps` và trần thay được, KHÔNG sửa module."""
    floor_daily = ds * (1.0 - ftmo.DAILY_LOSS_HARD)
    floor_eff = max(floor_daily, FLOOR_ABS)
    if eq <= FLOOR_ABS:
        return 0.0
    buf_total = (eq - FLOOR_ABS) / eq * 100.0
    buf_daily = max(0.0, (eq - floor_eff) / eq * 100.0)
    sigma = 9.33 / 100.0
    lev = min(buf_daily / (POL.SAFETY_SIGMA_DAILY * sigma),
              buf_total / (POL.SAFETY_SIGMA_TOTAL * sigma
                           * np.sqrt(POL.SAFETY_HORIZON_DAYS)),
              buf_daily / (POL.TAIL_BUFFER * wd_bps / 100.0),
              cap)
    return 0.0 if buf_total < 1.0 else max(0.0, float(lev))


def _run(r: np.ndarray, wd: float, cap: float, start=0, n=None) -> dict:
    eq = peak = ACCOUNT
    mdd = worst = 0.0
    levs = []
    dead = cut = False
    end = len(r) if n is None else min(start + n, len(r))
    for x in r[start:end]:
        ds = eq
        lev = _decide(eq, ds, wd, cap)
        levs.append(lev)
        eq *= (1.0 + float(x) * lev / 1e4)
        day = (eq - ds) / ds
        worst = min(worst, day)
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak * 100.0)
        if eq <= HARD_ABS or day <= -ftmo.DAILY_LOSS_HARD:
            dead = True
            break
        if eq <= FLOOR_ABS or day <= -ftmo.DAILY_FLATTEN_REALIZED:
            cut = True
            break
    return {"equity": eq, "mdd": mdd, "worst": worst * 100.0, "dead": dead,
            "cut": cut, "lev": float(np.mean(levs)) if levs else 0.0}


def _windows(r: np.ndarray, wd: float, cap: float) -> dict:
    dead = cut = ok = 0
    for s in range(0, max(1, len(r) - WINDOW), 21):
        w = _run(r, wd, cap, start=s, n=WINDOW)
        dead += w["dead"]
        cut += (w["cut"] and not w["dead"])
        ok += (not w["dead"] and not w["cut"])
    t = max(dead + cut + ok, 1)
    return {"dead": dead / t * 100.0, "cut": cut / t * 100.0}


def main() -> int:
    print("Đang chạy backtest danh mục 27 chân… (~2 phút)")
    res = PF.backtest(start="2020-01-01")
    legs = pd.DataFrame(res.legs).fillna(0.0)

    schemes = {"ĐỀU (hiện tại)": None,
               "INV-VOL 20 ngày": IV._inv_vol_weights(legs, 20)}

    print(f"\n{'=' * 100}")
    print("TÁI CẤP ĐÒN BẨY SAU KHI ĐỔI TRỌNG SỐ — chọn theo NGÂN SÁCH")
    print("=" * 100)
    print(f"{'sơ đồ':16} {'trần':>5} {'wd':>6} | "
          f"{'TOÀN MẪU':^30} | {'2026':^24} | {'cửa sổ':^13}")
    print(f"{'':16} {'':>5} {'':>6} | {'số dư cuối':>12} {'MaxDD':>7} {'ngày':>6} | "
          f"{'lãi':>8} {'MaxDD':>7} {'ngày':>6} | {'CHẾT':>6} {'cắt':>5}")
    print("-" * 100)

    cands = []
    for name, w in schemes.items():
        s = IV._combine(legs, w, PF.LEG_WEIGHTS).dropna()
        wd = abs(float(s.min()))
        a, a26 = s.to_numpy(), s[s.index >= START26].to_numpy()
        for cap in GRID_CAP:
            full, y26 = _run(a, wd, cap), _run(a26, wd, cap)
            wnd = _windows(a, wd, cap)
            ok = (wnd["dead"] <= 0.0 and wnd["cut"] <= BUDGET_CUT
                  and not full["dead"] and y26["mdd"] <= BUDGET_MAXDD
                  and abs(y26["worst"]) <= BUDGET_DAY
                  and abs(full["worst"]) <= BUDGET_DAY)
            if ok:
                cands.append((name, cap, wd, y26, full, wnd))
            print(f"{name:16} {cap:4.1f}x {wd:6.1f} | ${full['equity']:>11,.0f} "
                  f"{full['mdd']:6.2f}% {full['worst']:5.2f}% | "
                  f"{(y26['equity'] - ACCOUNT) / ACCOUNT * 100:+7.2f}% "
                  f"{y26['mdd']:6.2f}% {y26['worst']:5.2f}% | "
                  f"{wnd['dead']:5.1f}% {wnd['cut']:4.1f}%"
                  f"{'' if ok else '  loại'}")

    print()
    if not cands:
        print("KHÔNG bộ nào thoả ngân sách — giữ nguyên.")
        return 0

    # Trong mỗi sơ đồ, lấy trần THẤP NHẤT còn thoả; rồi so hai sơ đồ.
    best = {}
    for name, cap, wd, y26, full, wnd in cands:
        if name not in best:
            best[name] = (cap, wd, y26, full, wnd)

    print("BỘ THOẢ NGÂN SÁCH, TRẦN THẤP NHẤT MỖI SƠ ĐỒ")
    for name, (cap, wd, y26, full, wnd) in best.items():
        pm = (y26["equity"] - ACCOUNT) / ACCOUNT * 100.0 / (len(
            legs[legs.index >= START26]) / 21.0)
        print(f"  {name:16} trần {cap:.1f}x · wd {wd:.1f} bps → "
              f"2026 {(y26['equity'] - ACCOUNT) / ACCOUNT * 100:+.2f}% · "
              f"MaxDD {y26['mdd']:.2f}%/9% · ngày {full['worst']:.2f}%/4% · "
              f"{pm:+.2f}%/tháng" + (f" → thi {15 / pm:.1f} tháng" if pm > 0 else ""))

    print()
    print("⚠️ `worst_day_bps` ở đây là SỐ ĐO của chính sơ đồ trọng số, không phải")
    print("   tham số chọn được. Đổi trọng số là phải đo lại nó — đó là lý do bảng")
    print("   này có cột `wd`, và là lý do không được copy trần từ dòng này sang dòng")
    print("   khác. Ngoài ra: 2026 chỉ là 9,4 tháng, một mẫu; cột TOÀN MẪU và cột")
    print("   cửa sổ mới là phần nói về độ bền.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
