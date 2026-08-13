# -*- coding: utf-8 -*-
"""Đòn bẩy TỐI ƯU THEO PHA — tối đa P(pass), khống chế P(vi phạm).

    .venv311\\Scripts\\python.exe research/fx/leverage_by_phase.py

VÌ SAO MỘT TRẦN CỨNG LÀ SAI BÀI TOÁN
=====================================
`LEVERAGE_MAX = 3.5` áp chung cho mọi pha. Nhưng ba pha có HÀM MỤC TIÊU khác nhau,
và mất tài khoản ở mỗi pha có giá khác nhau:

    CHALLENGE      mục tiêu +10%, không giới hạn thời gian.
                   Mất = mất PHÍ THI (vài trăm đô) + thời gian.
    VERIFICATION   mục tiêu +5%.  Mất = mất phí thi + công của vòng 1.
    FUNDED         không có mục tiêu, chỉ có "đừng chết".
                   Mất = mất NGUỒN THU NHẬP.

Ở hai pha thi, chậm cũng là một dạng thua: mỗi tháng không pass là một tháng không
có gì. Ở pha funded thì ngược lại — không có phần thưởng nào cho việc đi nhanh, và
tài khoản sống là toàn bộ giá trị.

Đây KHÔNG phải cái cớ để nới rủi ro bừa. Hai drawdown của FTMO (ngày 5%, tổng 10%)
vẫn là ràng buộc CỨNG ở mọi pha — cái đổi là mức P(vi phạm) chấp nhận được để đánh
đổi lấy tốc độ.

ĐO ĐÚNG CÁCH: CỬA SỔ LÀ THỜI GIAN ĐỂ PASS, KHÔNG PHẢI 252 NGÀY
===============================================================
`leverage_frontier_2026.py` quét cửa sổ 252 ngày cố định và cho P(vi phạm) 1,0% ở
3,5x. Nhưng ở pha CHALLENGE, tài khoản KHÔNG chạy 252 ngày — nó dừng ngay khi chạm
+10%. Nếu thường pass trong 60 ngày thì con số rủi ro đúng phải đo trên 60 ngày,
không phải 252. Đo trên cửa sổ dài hơn thực tế là tự phạt mình.

Mô phỏng ở đây dừng ở BA điều kiện, đúng như tài khoản thật:
    1. equity ≥ mục tiêu           → PASS
    2. equity ≤ $90.000            → VI PHẠM max loss
    3. lỗ ngày ≥ 5%                → VI PHẠM daily loss
    4. hết `max_days`              → HẾT HẠN (không pass, không chết)

TIÊU CHÍ CHỌN
==============
Chọn mức đòn bẩy LỚN NHẤT có P(vi phạm) ≤ ngưỡng của pha. Ngưỡng do người vận hành
đặt, và nó là một quyết định KINH DOANH chứ không phải kỹ thuật — nên nó nằm ở
hằng số có tên, không giấu trong công thức.
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
HARD_ABS = ACCOUNT * (1 - ftmo.MAX_LOSS_HARD)     # $90.000 — chạm là MẤT TÀI KHOẢN
LEVELS = np.arange(2.0, 10.01, 0.5)

# ── LỚP CẮT NỘI BỘ — chặn TRƯỚC luật, và đây là thứ đổi cả bài toán.
#
# `ftmo_guard.check()` đóng sạch vị thế khi chạm ngưỡng nội bộ. Nhờ nó, chạm sàn
# nội bộ và chạm luật FTMO là HAI KẾT CỤC KHÁC HẲN NHAU:
#
#     chạm sàn nội bộ (9% tổng / 4% ngày)  → BỊ CẮT. Lần thi đó hỏng, nhưng tài
#                                             khoản còn, thi lại được.
#     chạm luật FTMO  (10% tổng / 5% ngày) → MẤT TÀI KHOẢN. Hết.
#
# Bản đầu của bài này gộp cả hai vào một cột "vi phạm" — sai, và sai theo hướng
# quá thận trọng: nó phạt đòn bẩy cao vì những lần lẽ ra chỉ bị cắt.
#
# Khoảng giữa 9% và 10% (hay 4% và 5%) là BIÊN AN TOÀN, và nó tồn tại để hấp thụ
# đúng thứ backtest không có: trượt giá, spread giãn, lệnh bị từ chối, độ trễ giữa
# lúc quyết định đóng và lúc broker khớp.
DAILY_SELF_CAP = 0.04      # cắt ở 4%/ngày, luật là 5%
TOTAL_SELF_CAP = POL.DD_SELF_CAP   # 9% tổng, luật là 10%

# Ngưỡng P(vi phạm) chấp nhận được, theo pha. QUYẾT ĐỊNH KINH DOANH.
#
# CHALLENGE 5%: mất một lần thi là mất phí thi, không mất nguồn thu. Đổi lại tốc
#   độ — và tốc độ ở đây có giá trị thật vì mỗi tháng chưa pass là một tháng không
#   có thu nhập.
# VERIFICATION 3%: chặt hơn vì đã tốn công qua vòng 1, mất là mất cả hai.
# FUNDED 0%: không đánh đổi. Tài khoản funded là nguồn thu; không có phần thưởng
#   nào cho việc đi nhanh, nên không có lý do chấp nhận bất kỳ xác suất chết nào
#   đo được trên mẫu.
# Ngân sách áp cho cột CHẾT (mất tài khoản), không phải cột BỊ CẮT.
PHASE_RISK_BUDGET = {
    ftmo.PHASE_CHALLENGE: 1.0,
    ftmo.PHASE_VERIFICATION: 1.0,
    ftmo.PHASE_FUNDED: 0.0,
}

# Số ngày tối đa cho một lần thi. FTMO Swing không giới hạn thời gian, nhưng phải
# có mốc để mô phỏng kết thúc — 252 ngày = một năm giao dịch.
MAX_DAYS = 252


def _simulate(r: np.ndarray, lev: float, target: float | None,
              max_days: int = MAX_DAYS) -> dict:
    """Quét mọi cửa sổ, mỗi cửa sổ là MỘT lần thi. Trả tỷ lệ pass/vi phạm/hết hạn.

    `target=None` (pha FUNDED) thì không có điều kiện thắng — chạy hết cửa sổ và
    chỉ đếm vi phạm. Đó đúng là bài toán của tài khoản đã cấp vốn.
    """
    n_pass = n_cut = n_dead = n_exp = 0
    days_to_pass = []
    floor_abs = ACCOUNT * (1 - TOTAL_SELF_CAP)
    for s in range(0, max(1, len(r) - max_days), 21):
        eq = ACCOUNT
        done = False
        for i, x in enumerate(r[s:s + max_days]):
            ds = eq
            eq *= (1.0 + x * lev / 1e4)
            day_ret = (eq - ds) / ds

            # LUẬT trước — nếu một cú nhảy vượt thẳng qua cả hai mốc thì đó là
            # mất tài khoản THẬT, lớp cắt không kịp. Kiểm luật trước lớp cắt để
            # không tự khai là "chỉ bị cắt" một tình huống đã chết.
            if eq <= HARD_ABS or day_ret <= -ftmo.DAILY_LOSS_HARD:
                n_dead += 1
                done = True
                break
            # Lớp cắt nội bộ: `ftmo_guard` đóng sạch, lần thi hỏng nhưng còn sống.
            if eq <= floor_abs or day_ret <= -DAILY_SELF_CAP:
                n_cut += 1
                done = True
                break
            if target is not None and eq >= ACCOUNT * (1 + target):
                n_pass += 1
                days_to_pass.append(i + 1)
                done = True
                break
        if not done:
            n_exp += 1
    tot = max(n_pass + n_cut + n_dead + n_exp, 1)
    return {
        "pass_%": n_pass / tot * 100.0,
        "cut_%": n_cut / tot * 100.0,
        "dead_%": n_dead / tot * 100.0,
        "expire_%": n_exp / tot * 100.0,
        "ngay_TV": float(np.median(days_to_pass)) if days_to_pass else float("nan"),
        "n": tot,
    }


def _table(r: np.ndarray, phase: str, target: float | None) -> float | None:
    budget = PHASE_RISK_BUDGET[phase]
    tgt_txt = f"+{target:.0%}" if target is not None else "không có (chỉ sống sót)"
    print(f"\n{'=' * 84}")
    print(f"PHA {phase} · mục tiêu {tgt_txt} · ngân sách P(vi phạm) ≤ {budget:.0f}%")
    print("=" * 84)
    print(f"{'đòn bẩy':>8} {'PASS':>8} {'bị CẮT':>8} {'CHẾT':>7} {'hết hạn':>8} "
          f"{'ngày TV':>8} {'tháng':>6}  kết luận")
    print("-" * 84)

    best = None
    _broken = False
    for lev in LEVELS:
        s = _simulate(r, float(lev), target)
        # NGÂN SÁCH ÁP CHO CỘT "CHẾT", KHÔNG PHẢI CỘT "BỊ CẮT".
        # Bị cắt là mất một lần thi; chết là mất tài khoản. Chỉ cái thứ hai mới
        # là thứ thứ tự ưu tiên "Account Survival" nói tới.
        ok = s["dead_%"] <= budget
        # CHỌN THEO ĐƠN ĐIỆU: mức lớn nhất mà MỌI mức từ đó trở xuống đều thoả.
        #
        # Bản đầu lấy "mức cuối cùng thoả", và bảng đo cho thấy vì sao sai: ở pha
        # CHALLENGE, 4,5x chết 2,0% và 5,0x chết 2,9% (vượt), nhưng 5,5x và 6,0x
        # lại chỉ 1,0% (thoả). Rủi ro KHÔNG thể giảm khi đòn bẩy tăng — đó là
        # nhiễu của mẫu ~100 cửa sổ, không phải quy luật.
        #
        # Lấy mức cao nhất trong vùng ấy là chọn đỉnh nhiễu, đúng thứ
        # `REJECTED_DIRECTIONS` đã ghi lại một lần. Dừng ở mức ĐẦU TIÊN vượt ngân
        # sách và lấy mức ngay trước nó.
        if ok and not _broken:
            best = float(lev)
        elif not ok:
            _broken = True
        months = s["ngay_TV"] / 21.0 if s["ngay_TV"] == s["ngay_TV"] else float("nan")
        verdict = "trong ngân sách" if ok else "VƯỢT ngân sách"
        mark = " ←hiện tại" if abs(lev - POL.LEVERAGE_MAX) < 0.01 else ""
        print(f"{lev:7.1f}x {s['pass_%']:7.1f}% {s['cut_%']:7.1f}% "
              f"{s['dead_%']:6.1f}% {s['expire_%']:7.1f}% "
              f"{s['ngay_TV']:8.0f} {months:6.1f}  {verdict}{mark}")
    return best


def main() -> int:
    print("Đang chạy backtest danh mục 27 chân (chi phí MỚI)… (~2 phút)")
    res = PF.backtest(start="2020-01-01")
    r = res.net_bps.dropna().to_numpy()
    print(f"  {len(r)} ngày · trần hiện tại {POL.LEVERAGE_MAX:.2f}x")

    chosen = {}
    for phase, target in ((ftmo.PHASE_CHALLENGE, 0.10),
                          (ftmo.PHASE_VERIFICATION, 0.05),
                          (ftmo.PHASE_FUNDED, None)):
        chosen[phase] = _table(r, phase, target)

    print(f"\n{'=' * 84}")
    print("ĐỀ XUẤT TRẦN ĐÒN BẨY THEO PHA")
    print("=" * 84)
    for phase, lev in chosen.items():
        cur = POL.LEVERAGE_MAX
        if lev is None:
            print(f"  {phase:14} KHÔNG mức nào trong ngân sách "
                  f"{PHASE_RISK_BUDGET[phase]:.0f}% — giữ mức thấp nhất đo được")
            continue
        d = lev - cur
        arrow = "TĂNG" if d > 0.01 else ("HẠ" if d < -0.01 else "GIỮ")
        print(f"  {phase:14} {lev:.2f}x   ({arrow} từ {cur:.2f}x, {d:+.2f})")

    print("\n⚠️ HAI DRAWDOWN VẪN LÀ RÀNG BUỘC CỨNG Ở MỌI PHA")
    print("   Bảng này KHÔNG nới mốc 5%/ngày hay 10%/tổng — chúng là luật FTMO.")
    print("   Nó chỉ chọn đòn bẩy sao cho XÁC SUẤT chạm hai mốc đó nằm trong ngân")
    print("   sách rủi ro của từng pha. Ngân sách là quyết định kinh doanh, ghi ở")
    print("   `PHASE_RISK_BUDGET` — đổi nó là đổi khẩu vị rủi ro, phải có chủ ý.")
    print("\n   Mẫu 2020–2026 chứa sốc 2020 và 2022 nhưng KHÔNG chứa cú sốc chưa")
    print("   từng xảy ra. P(vi phạm) = 0 trên mẫu không phải P(vi phạm) = 0 thật.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
