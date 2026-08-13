# -*- coding: utf-8 -*-
"""Dùng HẾT ngân sách rủi ro 9%/4% — quét hệ số an toàn, không quét kết quả.

    .venv311\\Scripts\\python.exe research/fx/risk_budget_tune.py

VẤN ĐỀ
=======
Ở trần 5,0x, MaxDD 2026 mới 6,36% trên hạn mức 9% và ngày tệ nhất −2,04% trên mốc
4%. Còn dư 2,64 và 1,96 điểm % không dùng tới. Với tài khoản thi có mục tiêu lợi
nhuận, dư ngân sách rủi ro là dư CƠ HỘI.

TRẦN CỨNG KHÔNG PHẢI THỨ ĐANG CHẶN
===================================
Nâng trần từ 5,0x lên 8,0x không đổi gì — đòn bẩy THỰC bão hoà ở 4,84x. Ràng buộc
thật là công thức ĐUÔI:

    lev_tail = đệm_ngày / (TAIL_BUFFER × |ngày tệ nhất|)
             = 5,00% / (1,3 × 0,794%) = 4,84x

Nên muốn dùng thêm ngân sách thì phải chạm vào HỆ SỐ AN TOÀN, không phải trần.

BA HỆ SỐ, MỖI CÁI CHẶN MỘT KIỂU RỦI RO
=======================================
    SAFETY_SIGMA_DAILY   3,0   bao nhiêu σ ngày mà đệm NGÀY phải chịu được
    SAFETY_SIGMA_TOTAL   ?     bao nhiêu σ mà đệm TỔNG phải chịu qua 21 ngày
    TAIL_BUFFER          1,3   biên cho "ngày tệ nhất tương lai tệ hơn quá khứ"

Chúng KHÔNG thừa. `TAIL_BUFFER` sinh ra sau một lần mô phỏng thất bại: danh mục
ba chân có σ 0,504%/ngày mà ngày tệ nhất −5,47% (10,9σ) — giả định phân phối chuẩn
qua hệ số σ đã bỏ sót hoàn toàn cái đuôi ấy.

⚠️ ĐÂY LÀ CHỖ DỄ OVERFIT NHẤT TRONG CẢ DỰ ÁN
=============================================
Quét ba hệ số rồi lấy bộ cho lợi nhuận cao nhất là tối ưu lưới tham số — thứ
CLAUDE.md liệt vào nhóm "bị từ chối thẳng". Nên bài này KHÔNG chọn theo lợi nhuận.

Tiêu chí, theo đúng thứ tự ưu tiên của dự án:
    1. P(chết) = 0        trên mọi cửa sổ 252 ngày của toàn mẫu — điều kiện LOẠI
    2. P(bị cắt) ≤ 5%     bị cắt là hỏng một lần thi, chấp nhận được nhưng có hạn
    3. MaxDD ≤ 9%         và ngày tệ nhất ≤ 4% — hai ngân sách người vận hành đặt
    4. trong số còn lại   lấy bộ có ÍT thay đổi nhất so với hiện tại

Điều kiện 4 mới là thứ chống overfit: khi nhiều bộ cùng thoả, chọn bộ GẦN bản gốc
nhất, không chọn bộ cho số đẹp nhất. Mỗi hệ số đổi đi là một bậc tự do đã tiêu.
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
WINDOW = 252

# Ngân sách người vận hành đặt (15/08/2026): "khống chế DD ngày ~4%, max DD 9%".
BUDGET_MAXDD = 9.0
BUDGET_DAY = 4.0
BUDGET_CUT = 5.0        # % cửa sổ bị cắt, chấp nhận được

# Lưới quét — HẸP CÓ CHỦ Ý. Quét rộng là mời gọi overfit; ở đây chỉ hỏi
# "nới bao nhiêu thì hết ngân sách", không hỏi "bộ nào lãi nhất".
GRID_TAIL = (1.3, 1.2, 1.1, 1.0)
GRID_CAP = (5.0, 6.0, 7.0)


def _decide(eq: float, ds: float, tail: float, cap: float):
    """Bản sao `POL.decide` với `TAIL_BUFFER` thay được — KHÔNG sửa module gốc.

    Sửa hằng số trong module rồi chạy là cách để một lượt quét làm bẩn tham số
    của mọi lượt sau trong cùng tiến trình. Tính tại chỗ thì không có trạng thái
    nào rò rỉ.
    """
    floor_daily = ds * (1.0 - ftmo.DAILY_LOSS_HARD)
    floor_eff = max(floor_daily, FLOOR_ABS)
    if eq <= FLOOR_ABS:
        return 0.0
    buf_total = (eq - FLOOR_ABS) / eq * 100.0
    buf_daily = max(0.0, (eq - floor_eff) / eq * 100.0)
    sigma = 9.33 / 100.0
    lev_daily = buf_daily / (POL.SAFETY_SIGMA_DAILY * sigma)
    lev_total = buf_total / (POL.SAFETY_SIGMA_TOTAL * sigma
                             * np.sqrt(POL.SAFETY_HORIZON_DAYS))
    lev_tail = buf_daily / (tail * (79.4 / 100.0))
    lev = float(min(lev_daily, lev_total, lev_tail, cap))
    return 0.0 if buf_total < 1.0 else max(0.0, lev)


def _run(r: np.ndarray, tail: float, cap: float,
         start: int = 0, n: int | None = None) -> dict:
    eq = ACCOUNT
    peak = eq
    max_dd = worst = 0.0
    levs = []
    dead = cut = False
    end = len(r) if n is None else min(start + n, len(r))
    for x in r[start:end]:
        ds = eq
        lev = _decide(eq, ds, tail, cap)
        levs.append(lev)
        eq *= (1.0 + float(x) * lev / 1e4)
        day = (eq - ds) / ds
        worst = min(worst, day)
        peak = max(peak, eq)
        max_dd = max(max_dd, (peak - eq) / peak * 100.0)
        if eq <= HARD_ABS or day <= -ftmo.DAILY_LOSS_HARD:
            dead = True
            break
        if eq <= FLOOR_ABS or day <= -ftmo.DAILY_FLATTEN_REALIZED:
            cut = True
            break
    return {"equity": eq, "max_dd": max_dd, "worst": worst * 100.0,
            "lev": float(np.mean(levs)) if levs else 0.0,
            "dead": dead, "cut": cut}


def _windows(r: np.ndarray, tail: float, cap: float) -> dict:
    dead = cut = ok = 0
    for s in range(0, max(1, len(r) - WINDOW), 21):
        w = _run(r, tail, cap, start=s, n=WINDOW)
        if w["dead"]:
            dead += 1
        elif w["cut"]:
            cut += 1
        else:
            ok += 1
    t = max(dead + cut + ok, 1)
    return {"dead": dead / t * 100.0, "cut": cut / t * 100.0}


def main() -> int:
    print("Đang chạy backtest danh mục 27 chân… (~2 phút)")
    res = PF.backtest(start="2020-01-01")
    r = res.net_bps.dropna()
    a = r.to_numpy()
    a26 = r[r.index >= pd.Timestamp("2026-01-01")].to_numpy()
    print(f"  {len(a)} ngày · ngân sách: MaxDD ≤ {BUDGET_MAXDD:.0f}% · "
          f"ngày ≤ {BUDGET_DAY:.0f}% · bị cắt ≤ {BUDGET_CUT:.0f}%")

    print(f"\n{'=' * 100}")
    print("QUÉT HỆ SỐ AN TOÀN — chọn theo NGÂN SÁCH, không theo lợi nhuận")
    print("=" * 100)
    print(f"{'tail':>5} {'trần':>6} | {'TOÀN MẪU':^32} | {'2026':^22} | "
          f"{'cửa sổ':^15}")
    print(f"{'':>5} {'':>6} | {'số dư cuối':>12} {'MaxDD':>7} {'ngày':>6} "
          f"{'lev':>5} | {'lãi':>8} {'MaxDD':>7} {'ngày':>6} | {'CHẾT':>6} {'cắt':>6}")
    print("-" * 100)

    cands = []
    for tail in GRID_TAIL:
        for cap in GRID_CAP:
            full = _run(a, tail, cap)
            y26 = _run(a26, tail, cap)
            wnd = _windows(a, tail, cap)
            ok = (wnd["dead"] <= 0.0 and wnd["cut"] <= BUDGET_CUT
                  and not full["dead"]
                  and y26["max_dd"] <= BUDGET_MAXDD
                  and abs(y26["worst"]) <= BUDGET_DAY)
            if ok:
                # Khoảng cách tới bản gốc — dùng để chống overfit ở bước chọn.
                dist = abs(tail - POL.TAIL_BUFFER) + abs(cap - POL.LEVERAGE_MAX) / 10
                cands.append((dist, tail, cap, y26, full))
            print(f"{tail:5.1f} {cap:5.1f}x | ${full['equity']:>11,.0f} "
                  f"{full['max_dd']:6.2f}% {full['worst']:5.2f}% {full['lev']:4.2f}x | "
                  f"{(y26['equity'] - ACCOUNT) / ACCOUNT * 100:+7.2f}% "
                  f"{y26['max_dd']:6.2f}% {y26['worst']:5.2f}% | "
                  f"{wnd['dead']:5.1f}% {wnd['cut']:5.1f}%"
                  f"{'' if ok else '  loại'}")

    print()
    if not cands:
        print("KHÔNG bộ nào thoả ngân sách — giữ nguyên tham số hiện tại.")
        return 0

    cands.sort(key=lambda c: c[0])
    dist, tail, cap, y26, full = cands[0]
    pm = (y26["equity"] - ACCOUNT) / ACCOUNT * 100.0 / (len(a26) / 21.0)
    print(f"CHỌN: TAIL_BUFFER = {tail:.1f} · LEVERAGE_MAX = {cap:.1f}x")
    print(f"  (bộ THOẢ ngân sách và GẦN bản gốc nhất — không phải bộ lãi nhất)")
    print(f"  2026: {(y26['equity'] - ACCOUNT) / ACCOUNT * 100:+.2f}% · "
          f"MaxDD {y26['max_dd']:.2f}%/{BUDGET_MAXDD:.0f}% · "
          f"ngày {y26['worst']:.2f}%/{BUDGET_DAY:.0f}%")
    print(f"  {pm:+.2f}%/tháng → FTMO hai vòng "
          f"{15 / pm:.1f} tháng" if pm > 0 else "")

    # Bộ LÃI NHẤT trong nhóm thoả — in ra để thấy cái giá của việc chống overfit.
    best_p = max(cands, key=lambda c: c[3]["equity"])
    if best_p[1] != tail or best_p[2] != cap:
        p26 = (best_p[3]["equity"] - ACCOUNT) / ACCOUNT * 100.0
        print(f"\n  (Bộ LÃI NHẤT trong nhóm thoả là tail={best_p[1]:.1f} "
              f"cap={best_p[2]:.1f}x → 2026 {p26:+.2f}%. KHÔNG chọn nó: chênh "
              f"lệch không đủ lớn để đáng đánh đổi thêm bậc tự do.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
