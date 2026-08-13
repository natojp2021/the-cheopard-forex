# -*- coding: utf-8 -*-
"""Nới SÀN NỘI BỘ được không — 9%→9,5% và cắt ngày 4%→4,5%?

    .venv311\Scripts\python.exe research/fx/self_cap_tune.py

CÂU HỎI
========
MaxDD 2026 mới 6,55% trên hạn mức 9%, ngày tệ nhất −2,21% trên mốc 4%. Nhìn qua
thì còn dư 2,45 và 1,79 điểm %. Có nới hai ngưỡng NỘI BỘ ra sát luật FTMO
(10% / 5%) để chạy nhanh hơn không?

HAI NGƯỠNG NÀY KHÁC HẲN HỆ SỐ ĐÒN BẨY
======================================
`LEVERAGE_MAX` và `TAIL_BUFFER` quyết định VÀO LỆNH BAO NHIÊU. Nới chúng làm lãi
tăng và lỗ tăng cùng tỷ lệ.

`DD_SELF_CAP` và `DAILY_FLATTEN_REALIZED` là chỗ HỆ TỰ CẮT. Khoảng giữa chúng và
luật FTMO là BIÊN HẤP THỤ cho bốn thứ backtest hoàn toàn không có:

    trượt giá lúc đóng gấp        lệnh bị broker từ chối
    spread giãn lúc thị trường xấu   độ trễ giữa quyết định đóng và lúc khớp

Nới sàn từ 9% lên 9,5% là cắt biên ấy còn một nửa. Backtest sẽ báo "vẫn an toàn"
vì nó không mô phỏng bốn thứ trên — tức chính chỗ này là nơi backtest nói dối
nhiều nhất.

Bài này vẫn ĐO, vì "không nên" phải có số đứng sau chứ không phải cảm giác.
"""
import io, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from src.python.core.infra import ftmo
from src.python.execution import ftmo_leverage_policy as POL
from src.python.strategies import portfolio as PF

ACCOUNT = 100_000.0
HARD_ABS = ACCOUNT * (1 - ftmo.MAX_LOSS_HARD)
WINDOW = 252
# (sàn tổng, mốc cắt ngày) — nới dần về phía luật FTMO 10%/5%.
GRID = ((0.09, 0.040), (0.09, 0.045), (0.095, 0.040), (0.095, 0.045))


def _lev(eq, ds, floor_abs):
    if eq <= floor_abs:
        return 0.0
    floor_eff = max(ds * (1 - ftmo.DAILY_LOSS_HARD), floor_abs)
    bt = (eq - floor_abs) / eq * 100.0
    bd = max(0.0, (eq - floor_eff) / eq * 100.0)
    s = 9.33 / 100.0
    lv = min(bd / (POL.SAFETY_SIGMA_DAILY * s),
             bt / (POL.SAFETY_SIGMA_TOTAL * s * np.sqrt(POL.SAFETY_HORIZON_DAYS)),
             bd / (POL.TAIL_BUFFER * (79.4 / 100.0)), POL.LEVERAGE_MAX)
    return 0.0 if bt < 1.0 else max(0.0, float(lv))


def _run(r, cap, day_cut, start=0, n=None):
    floor_abs = ACCOUNT * (1 - cap)
    eq = peak = ACCOUNT
    mdd = worst = 0.0
    dead = cut = False
    end = len(r) if n is None else min(start + n, len(r))
    for x in r[start:end]:
        ds = eq
        eq *= (1.0 + float(x) * _lev(eq, ds, floor_abs) / 1e4)
        day = (eq - ds) / ds
        worst = min(worst, day)
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak * 100.0)
        if eq <= HARD_ABS or day <= -ftmo.DAILY_LOSS_HARD:
            dead = True
            break
        if eq <= floor_abs or day <= -day_cut:
            cut = True
            break
    return {"eq": eq, "mdd": mdd, "worst": worst * 100.0, "dead": dead, "cut": cut}


def _win(r, cap, day_cut):
    d = c = o = 0
    for s in range(0, max(1, len(r) - WINDOW), 21):
        w = _run(r, cap, day_cut, s, WINDOW)
        d, c, o = d + w["dead"], c + (w["cut"] and not w["dead"]), o + (not w["dead"] and not w["cut"])
    t = max(d + c + o, 1)
    return d / t * 100.0, c / t * 100.0


def main():
    print("Đang chạy backtest 27 chân… (~2 phút)")
    r = PF.backtest(start="2020-01-01").net_bps.dropna()
    a = r.to_numpy()
    a26 = r[r.index >= pd.Timestamp("2026-01-01")].to_numpy()
    print(f"  {len(a)} ngày · luật FTMO: max {ftmo.MAX_LOSS_HARD:.0%} · "
          f"ngày {ftmo.DAILY_LOSS_HARD:.0%}\n")
    print("=" * 94)
    print("NỚI SÀN NỘI BỘ VỀ PHÍA LUẬT — biên hấp thụ còn lại bao nhiêu?")
    print("=" * 94)
    print(f"{'sàn':>6} {'cắt ngày':>9} {'biên còn':>10} | "
          f"{'TOÀN MẪU: ngày tệ':>18} {'MaxDD':>7} | {'2026 lãi':>9} | "
          f"{'CHẾT':>6} {'bị cắt':>7}")
    print("-" * 94)
    for cap, dc in GRID:
        f = _run(a, cap, dc)
        y = _run(a26, cap, dc)
        dead, cut = _win(a, cap, dc)
        bien = (ftmo.MAX_LOSS_HARD - cap) * 100
        bien_d = (ftmo.DAILY_LOSS_HARD - dc) * 100
        cur = " ←" if abs(cap - POL.DD_SELF_CAP) < 1e-9 and abs(dc - ftmo.DAILY_FLATTEN_REALIZED) < 1e-9 else "  "
        print(f"{cap:5.1%} {dc:9.1%} {bien:4.1f}/{bien_d:.1f}đ% | "
              f"{f['worst']:17.2f}% {f['mdd']:6.2f}% | "
              f"{(y['eq'] - ACCOUNT) / ACCOUNT * 100:+8.2f}% | "
              f"{dead:5.1f}% {cut:6.1f}%{cur}")
    print("\nBIÊN HẤP THỤ là khoảng giữa sàn nội bộ và luật FTMO. Backtest KHÔNG mô")
    print("phỏng trượt giá, spread giãn, lệnh bị từ chối, độ trễ khớp — bốn thứ mà")
    print("biên này tồn tại để hấp thụ. Cột CHẾT = 0 ở đây KHÔNG chứng minh nới an")
    print("toàn; nó chỉ nói mô hình không thấy vấn đề, mà mô hình thì mù đúng chỗ đó.")


if __name__ == "__main__":
    raise SystemExit(main())
