"""Vòng 56 — KIỂM ĐỊNH ĐẦY ĐỦ họ ĐUÔI (`jump`) và họ ĐỘ SÂU (`drawdown`).

NĂM ỨNG VIÊN TỪ VÒNG 55
=======================
    H1  jump_126d      ALL 0,483 · FORM 0,349 · OOS 0,758 · vòng quay 0,2/năm
    M30 jump_126d      ALL 0,481 · FORM 0,338 · OOS 0,752 · vòng quay 0,2/năm
    M30 jump_63d       ALL 0,452 · FORM 0,225 · OOS 0,874 · vòng quay 0,4/năm
    H1  drawdown_63d   ALL 0,444 · FORM 0,118 · OOS 1,015 · vòng quay 5,2/năm
    H1  jump_63d       ALL 0,404 · FORM 0,127 · OOS 0,932 · vòng quay 0,5/năm

Kiểm chứng đặt trước ở vòng 55 đã ĐẠT: trong sáu họ đo bất đối xứng, đúng hai họ có
gross dương phổ quát (jump 7/8 và 7/8 ô, drawdown 7/8 và 8/8), bốn họ còn lại âm đều.
Nếu chỉ MỘT họ dương thì đó là nhiễu; hai họ đo hai thứ khác nhau mà cùng dương thì
đáng đo tiếp.

NGHI VẤN LỚN NHẤT PHẢI GIẢI QUYẾT TRƯỚC MỌI THỨ KHÁC
=====================================================
Vòng quay **0,2/năm** nghĩa là vị thế gần như KHÔNG ĐỔI suốt 6,5 năm. Với một rổ gần
tĩnh thì Sharpe 0,48 có thể đến từ hai nguồn hoàn toàn khác nhau:

    (a) tín hiệu chọn đúng cross nào đáng nắm  ← cái ta muốn
    (b) chỉ đơn giản là nắm một rổ cross nào đó trong giai đoạn nó tăng  ← vô giá trị

Phân biệt hai cái CHỈ có một cách: control giữ nguyên cấu trúc vị thế (số công cụ, độ
lớn, tần suất đổi) nhưng CHỌN NGẪU NHIÊN công cụ. Nếu control cũng ra Sharpe tương tự
thì tín hiệu không đóng góp gì và phải loại — bất kể FORM/OOS đẹp đến đâu.

Đây là cùng loại sai lầm mà hệ XAUUSD cũ mắc: control vào lệnh ngẫu nhiên cũng có lãi
trên 2023-2026, nên "chiến lược có lãi" không chứng minh được gì.

SÁU KIỂM ĐỊNH
=============
    1. CONTROL RỔ NGẪU NHIÊN  — quan trọng nhất, xem trên
    2. BOOTSTRAP KHỐI 21 ngày, 2000 lần → CI95 và P(<0)
    3. ỔN ĐỊNH NĂM
    4. LOẠI NGOẠI LAI — bỏ 5 tháng tốt nhất, có giữ dấu không
    5. STRESS CHI PHÍ ×2 ×5 ×10 và biên swap 0-3%/năm
    6. ĐỘC LẬP với năm chân đang chạy
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

from src.python.research import fx_cross_lab as LAB
from research.fx.carver_lab import (FORM_END, VOL_SPAN_BARS, _vol, apply_buffer,
                                    forecast_to_position, scale_and_cap, sharpe)
from research.fx.shape_lab import sig_drawdown, sig_jump

pd.set_option("display.width", 240, "display.max_columns", 30)
OUT = ROOT / "reports" / "fx_research"
BARS_DAY = {"M30": 48, "H1": 24}

# (khung, họ, số ngày cửa sổ)
CANDIDATES: Tuple[Tuple[str, str, int], ...] = (
    ("H1", "jump", 126), ("M30", "jump", 126), ("M30", "jump", 63),
    ("H1", "drawdown", 63), ("H1", "jump", 63),
)


def build_positions(panel, tf: str, family: str, days: int) -> pd.DataFrame:
    """Vị thế của một ứng viên — cùng đường code với lab, không viết lại."""
    bpd = BARS_DAY[tf]
    w = max(days * bpd, 40)
    logp = panel.logp
    vol = _vol(logp, VOL_SPAN_BARS[tf])
    raw = (sig_jump(logp, w, 3.0, False) if family == "jump"
           else sig_drawdown(logp, w, False))
    pos = apply_buffer(forecast_to_position(scale_and_cap(raw), vol, 1.0))
    g = pos.abs().sum(axis=1).replace(0, np.nan)
    return pos.div(g, axis=0).fillna(0.0)


def random_control(pos_real: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Control: giữ NGUYÊN vector độ lớn vị thế theo thời gian, HOÁN VỊ công cụ.

    Đây là control đúng cho tín hiệu vị thế liên tục. Nó bảo toàn: số công cụ có vị
    thế, phân phối độ lớn, thời điểm và tần suất đổi vị thế, tổng phơi nhiễm. Thứ DUY
    NHẤT bị phá là ánh xạ "độ lớn nào thuộc về cross nào" — tức chính THÔNG TIN.

    Hoán vị dùng CÙNG một permutation cho cả chuỗi thời gian, không đổi mỗi nến: đổi
    mỗi nến sẽ tạo ra vòng quay giả khổng lồ và control sẽ thua vì chi phí, không vì
    thiếu thông tin — so sánh đó vô nghĩa.
    """
    rng = np.random.default_rng(seed)
    cols = list(pos_real.columns)
    perm = list(rng.permutation(len(cols)))
    out = pos_real.copy()
    out.columns = [cols[i] for i in perm]
    return out[cols]


def block_bootstrap(d: pd.Series, block: int = 21, n_iter: int = 2000,
                    seed: int = 7) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    v = d.to_numpy()
    n = len(v)
    nb = max(n // block, 1)
    out = np.empty(n_iter)
    for k in range(n_iter):
        starts = rng.integers(0, max(n - block, 1), size=nb)
        samp = np.concatenate([v[s:s + block] for s in starts])
        sd = samp.std(ddof=1)
        out[k] = samp.mean() / sd * np.sqrt(252) if sd > 0 else 0.0
    return {"mean": float(out.mean()), "ci_lo": float(np.percentile(out, 2.5)),
            "ci_hi": float(np.percentile(out, 97.5)),
            "p_neg": float((out < 0).mean())}


def live_legs() -> Dict[str, pd.Series]:
    from src.python.strategies.h1 import cross_mean_reversion as CMR
    from src.python.strategies.h4 import cross_xs_reversion as XXS
    from src.python.strategies.d1 import (currency_reversal as CR,
                                          currency_carry as CY,
                                          cross_momentum as CM)

    def day(s: pd.Series) -> pd.Series:
        s = s.copy()
        s.index = pd.DatetimeIndex(s.index).as_unit("ns").normalize()
        return s.groupby(s.index).sum()

    return {k: day(v) for k, v in (
        ("CrossMeanRev_H1", CMR.daily_pnl(CMR.backtest())),
        ("CrossXsRev_H4", XXS.daily_pnl()),
        ("CurrencyReversal_D1", CR.backtest().net),
        ("CurrencyCarry_D1", CY.backtest().net),
        ("CrossMomentum_D1", CM.daily_pnl()))}


def main() -> None:
    t0 = time.time()
    panels = {tf: LAB.build_panel(tf, start="2020-01-01") for tf in ("H1", "M30")}
    cand_series: Dict[str, pd.Series] = {}
    verdicts: List[Dict] = []

    for tf, fam, days in CANDIDATES:
        panel = panels[tf]
        label = f"{tf}·{fam}_{days}d"
        print()
        print("█" * 118)
        print(f"█ ỨNG VIÊN {label}")
        print("█" * 118)

        pos = build_positions(panel, tf, fam, days)
        res = LAB.simulate_positions(panel, pos, name=label)
        d = res.pnl_daily
        cand_series[label] = d
        s_all, s_form, s_oos = sharpe(d), sharpe(d, hi=FORM_END), sharpe(d, lo=FORM_END)
        cum = d.cumsum()
        yrs = max((d.index.max() - d.index.min()).days / 365.25, 1e-9)
        print(f"  Sharpe ALL {s_all:+.3f} · FORM {s_form:+.3f} · OOS {s_oos:+.3f}")
        print(f"  {float(cum.iloc[-1]) / 100 / yrs:+.2f}%/năm · MaxDD "
              f"{float((cum.cummax() - cum).max()) / 100:.2f}% · vòng quay "
              f"{res.turnover_per_year:.1f}/năm")

        # ── 1. CONTROL RỔ NGẪU NHIÊN — cổng quyết định
        ctrl = []
        for sd_ in range(200):
            rc = LAB.simulate_positions(panel, random_control(pos, sd_))
            ctrl.append(sharpe(rc.pnl_daily))
        ctrl = np.array([c for c in ctrl if np.isfinite(c)])
        pct = float((ctrl < s_all).mean())
        dat1 = pct >= 0.95
        print(f"\n  1. CONTROL RỔ NGẪU NHIÊN (200 hoán vị, giữ nguyên cấu trúc vị thế)")
        print(f"     thật {s_all:+.3f} vs control p50 {np.median(ctrl):+.3f} "
              f"[p5 {np.percentile(ctrl, 5):+.3f} · p95 {np.percentile(ctrl, 95):+.3f}]")
        print(f"     phân vị {pct:.1%} · p = {1 - pct:.4f}  "
              f"{'ĐẠT' if dat1 else 'KHÔNG ĐẠT — tín hiệu không đóng góp gì'}")

        # ── 2. bootstrap
        bs = block_bootstrap(d)
        dat2 = bs["p_neg"] < 0.10
        print(f"\n  2. BOOTSTRAP KHỐI 21 ngày: Sharpe {bs['mean']:+.3f} "
              f"CI95 [{bs['ci_lo']:+.3f} · {bs['ci_hi']:+.3f}] "
              f"P(<0) = {bs['p_neg']:.1%}  {'ĐẠT' if dat2 else 'KHÔNG ĐẠT'}")

        # ── 3. ổn định năm
        yr = d.groupby(d.index.year).sum() / 100.0
        dat3 = int((yr > 0).sum()) >= len(yr) - 1
        print(f"\n  3. ỔN ĐỊNH NĂM ({int((yr > 0).sum())}/{len(yr)} dương)  "
              f"{'ĐẠT' if dat3 else 'KHÔNG ĐẠT'}")
        print("     " + "  ".join(f"{int(y)}:{v:+.2f}%" for y, v in yr.items()))

        # ── 4. loại ngoại lai
        mo = d.resample("MS").sum()
        rest = float((mo.sum() - mo.nlargest(5).sum()) / 100.0)
        dat4 = rest > 0
        print(f"\n  4. LOẠI NGOẠI LAI — 5 tháng tốt nhất = "
              f"{float(mo.nlargest(5).sum() / mo.sum()):.1%}; bỏ đi còn {rest:+.2f}%  "
              f"{'GIỮ DẤU — ĐẠT' if dat4 else 'ĐỔI DẤU — KHÔNG ĐẠT'}")

        # ── 5. stress chi phí
        print(f"\n  5. STRESS CHI PHÍ")
        base = panel.cost_1rt_bps.copy()
        line = []
        for m in (2, 5, 10):
            panel.cost_1rt_bps = base * m
            line.append(f"×{m} {sharpe(LAB.simulate_positions(panel, pos).pnl_daily):+.3f}")
        panel.cost_1rt_bps = base
        print("     " + "  ·  ".join(line))
        sw = []
        for mk in (0.0, 2.0, 3.0):
            pn = LAB.build_panel(tf, start="2020-01-01", broker_markup_pct=mk)
            pp = build_positions(pn, tf, fam, days)
            sw.append(f"{mk:.0f}% {sharpe(LAB.simulate_positions(pn, pp).pnl_daily):+.3f}")
        print("     biên swap: " + "  ·  ".join(sw))

        verdicts.append({"ứng viên": label, "ALL": round(s_all, 3),
                         "FORM": round(s_form, 3), "OOS": round(s_oos, 3),
                         "control_p": round(1 - pct, 4), "boot_p_neg": bs["p_neg"],
                         "năm_dương": f"{int((yr > 0).sum())}/{len(yr)}",
                         "bỏ_top5": round(rest, 2),
                         "ĐẠT": dat1 and dat2 and dat3 and dat4})

    # ── 6. độc lập
    print()
    print("█" * 118)
    print("█ 6. ĐỘC LẬP — tương quan P&L ngày với năm chân đang chạy (ngưỡng 0,70)")
    print("█" * 118)
    def day(s):
        s = s.copy()
        s.index = pd.DatetimeIndex(s.index).as_unit("ns").normalize()
        return s.groupby(s.index).sum()
    allser = {**{k: day(v) for k, v in cand_series.items()}, **live_legs()}
    C = pd.DataFrame(allser).fillna(0.0).corr()
    print(C.round(3).to_string())

    V = pd.DataFrame(verdicts)
    print()
    print("=" * 118)
    print("TỔNG KẾT — chỉ ứng viên ĐẠT=True mới được xét đưa vào danh mục")
    print("=" * 118)
    print(V.to_string(index=False))

    ok = V[V["ĐẠT"]]["ứng viên"].tolist()
    if ok:
        print()
        print("Tương quan giữa các ứng viên ĐẠT và với chân đang chạy:")
        for a in ok:
            mx = max((abs(float(C.loc[a, b])), b) for b in allser if b != a)
            print(f"  {a:20s} |corr| lớn nhất {mx[0]:.3f} với {mx[1]}")
    pd.DataFrame(allser).to_csv(OUT / "tail_validate_pnl.csv")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
