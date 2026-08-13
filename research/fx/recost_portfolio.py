# -*- coding: utf-8 -*-
"""Đo lại số liệu danh mục SAU khi đổi mô hình chi phí cross (15/08/2026).

    .venv311\\Scripts\\python.exe research/fx/recost_portfolio.py

VÌ SAO PHẢI CHẠY BÀI NÀY
=========================
`fx_cross_pairs.spread_pips()` đổi từ `đo_được × 1,5` sang
`max(đo_được × 3,0, sàn tham chiếu FTMO)` — chi phí của 20 cross tăng 2–3 lần.
Mọi con số Sharpe đang nằm trong `registry.STRATEGIES` và `registry.PORTFOLIO`
đều tính trên mô hình CŨ, nên chúng nay là số của một hệ không còn tồn tại.

Dùng số cũ để quyết định giữ hay bỏ một chân là quyết định trên dữ liệu sai. Bài
này in ra cặp CŨ ↔ MỚI để thấy chân nào thật sự sống sót khi chi phí đúng hơn.

CHI PHÍ LÀ NƠI HỆ NÀY GẦN CHẾT NHẤT
====================================
Tiền lệ ghi trong CLAUDE.md: Sharpe **+0,216** sau spread+commission nhưng
**−0,456** sau swap. Một lớp chi phí bị bỏ sót đã từng đảo dấu cả một kết luận.
Ở đây không phải bỏ sót mà là ĐÁNH GIÁ THẤP — hệ quả cùng loại, chỉ nhẹ hơn.
"""
import io
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from src.python.research import fx_cross_pairs as XP  # noqa: E402
from src.python.strategies import portfolio as PF  # noqa: E402
from src.python.strategies import registry as REG  # noqa: E402

DEV = pd.Timestamp("2024-01-01")


def main() -> int:
    t0 = time.time()
    print("MÔ HÌNH CHI PHÍ ĐANG DÙNG")
    print(f"  hệ số an toàn        {XP.SPREAD_SAFETY_FACTOR}")
    print(f"  sàn theo cặp         {len(XP.FTMO_SPREAD_FLOOR_PIPS)} cặp")
    n_floor = sum(1 for k in XP.FTMO_SPREAD_FLOOR_PIPS
                  if XP.spread_pips(k) > XP.TYPICAL_SPREAD_PIPS.get(k, 1.0)
                  * XP.SPREAD_SAFETY_FACTOR - 1e-9
                  and XP.spread_pips(k) == XP.FTMO_SPREAD_FLOOR_PIPS[k])
    print(f"  cặp bị SÀN nâng lên  {n_floor}")
    print(f"  commission           ${XP.COMMISSION_USD_PER_LOT_RT:.2f}/lot khứ hồi")
    print()

    print("Đang chạy backtest danh mục 27 chân với chi phí MỚI… (~2 phút)")
    res = PF.backtest(start="2020-01-01")
    net = res.net
    rows = [PF.stats(net[net.index < DEV], "FORM"),
            PF.stats(net[net.index >= DEV], "OOS"),
            PF.stats(net, "ALL")]
    print()
    print(pd.DataFrame(rows).to_string(index=False))

    # ── So với số ĐANG GHI trong registry
    old = REG.PORTFOLIO or {}
    print()
    print("SO VỚI SỐ ĐANG GHI TRONG REGISTRY")
    new_all = rows[2].get("sharpe")
    new_oos = rows[1].get("sharpe")
    for label, o, n in (("Sharpe ALL", old.get("sharpe_all"), new_all),
                        ("Sharpe OOS", old.get("sharpe_oos"), new_oos)):
        if o is None or n is None:
            print(f"  {label:12} cũ {o} → mới {n}")
            continue
        d = (n - o) / abs(o) * 100.0 if o else float("nan")
        print(f"  {label:12} cũ {o:.3f} → mới {n:.3f}   ({d:+.1f}%)")

    # ── Từng chân: chân nào chết khi chi phí đúng hơn
    print()
    print("TỪNG CHÂN — Sharpe OOS với chi phí MỚI")
    print(f"  {'CHÂN':24} {'FORM':>8} {'OOS':>8}  {'kết luận'}")
    print("  " + "-" * 56)
    dead = []
    for name, s in sorted(res.legs.items()):
        f = PF.stats(s[s.index < DEV], name).get("sharpe")
        o = PF.stats(s[s.index >= DEV], name).get("sharpe")
        if f is None or o is None:
            continue
        # "Chết" = OOS âm. KHÔNG kết luận bỏ chân từ một con số — xem ghi chú cuối.
        flag = "OOS ÂM" if o < 0 else ("yếu" if o < 0.3 else "")
        if o < 0:
            dead.append(name)
        print(f"  {name:24} {f:8.3f} {o:8.3f}  {flag}")

    print()
    if dead:
        print(f"CHÂN CÓ OOS ÂM với chi phí mới: {len(dead)}")
        print(f"  {', '.join(dead)}")
        print()
        print("  ⚠️ KHÔNG bỏ chân chỉ vì dòng này. Quy trình thăng cấp đòi 6 kiểm")
        print("     định + cổng PBO, và tiêu chí 6 là ĐỘC LẬP — giá trị của một")
        print("     chân nằm ở tính trực giao, không ở Sharpe riêng của nó. Một")
        print("     chân Sharpe thấp nhưng không tương quan vẫn hạ MaxDD danh mục.")
    else:
        print("Không chân nào có OOS âm với chi phí mới.")

    print()
    print(f"({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
