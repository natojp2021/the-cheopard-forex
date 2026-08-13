# -*- coding: utf-8 -*-
"""Danh mục ĐỦ 27 CHÂN trên 2026 — thay con số ngoại suy bằng số đo.

    .venv311\\Scripts\\python.exe research/fx/portfolio_27leg_2026.py

VÌ SAO CẦN
===========
`live_path_backtest_2026.py` chỉ chạy được 22 chân ĐƠN, vì `parity.replay_leg`
đòi `live_decision(df, …)` theo TỪNG công cụ. Năm chân còn lại — CurrencyCarry,
CurrencyReversal, CrossMeanReversion, CrossMomentum, CrossXsReversion — quyết định
trên CẢ RỔ và chỉ phát ra một vector TỶ TRỌNG, nên không có "một lệnh trên một
công cụ" để replay.

Trước bài này, phần đóng góp của chúng được ngoại suy bằng hệ số 1,5 (từ tỷ lệ
33,4%). Ngoại suy không phải số đo, và một kế hoạch cấp vốn không nên đứng trên
ngoại suy.

HAI ĐƯỜNG ĐO, GHÉP LẠI — VÀ NÓI RÕ CHÚNG KHÁC NHAU CHỖ NÀO
===========================================================
    22 chân đơn   ĐƯỜNG LIVE THẬT (`parity.replay_leg`): live_decision →
                  position_book → order_plan → order_router → SimBroker. Có cầu
                  chì, có làm tròn lot, có spread tại điểm khớp.

    5 chân danh mục  ĐƯỜNG PHÂN TÍCH (`<leg>.backtest()`): chuỗi lợi nhuận đã trừ
                  đủ chi phí (spread + commission + swap + biên broker) nhưng
                  KHÔNG qua tầng thực thi.

Ghép hai đường là thoả hiệp CÓ Ý THỨC, không phải sơ suất. Phần thiếu ở nhóm hai
là tầng thực thi, và với chân TÁI CÂN BẰNG THEO TỶ TRỌNG thì tầng đó mỏng hơn
nhiều so với chân vào/ra từng lệnh: không có time-stop, không có điều kiện thoát,
không có sổ vị thế theo chân — chỉ còn làm tròn lot và spread lúc tái cân bằng.

Vẫn phải nhớ: con số của 5 chân này LẠC QUAN hơn thực tế một chút. Nói ra để không
ai đọc bảng này như thể cả 27 chân đều đã qua đường live.
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

from src.python.execution import ftmo_leverage_policy as POL  # noqa: E402
from src.python.strategies import portfolio as PF  # noqa: E402

START = pd.Timestamp("2026-01-01")
EQUITY0 = 100_000.0

# Năm chân quyết định trên CẢ RỔ — khoá trong `portfolio.backtest().legs`.
PORTFOLIO_LEGS = ("reversal", "carry", "cross_h1", "cross_mom", "cross_xs_h4")


def _fmt(x: float) -> str:
    return f"${x:,.2f}"


def main() -> int:
    print("Đang chạy backtest danh mục 27 chân (chi phí MỚI)… (~2 phút)")
    res = PF.backtest(start="2020-01-01")

    # Chuỗi lợi nhuận NGÀY của cả danh mục, đã chuẩn hoá theo σ và đã gộp tỷ trọng.
    # `net_bps`: lợi nhuận ngày của danh mục tính bằng BPS ở phơi nhiễm 1,0x.
    # KHÔNG dùng `res.net` — đó là chuỗi đã CHUẨN HOÁ theo σ, sai đơn vị.
    net = res.net_bps.dropna()
    net26 = net[net.index >= START]
    if len(net26) < 20:
        print("Không đủ dữ liệu 2026.")
        return 1

    # ── Equity với đòn bẩy do CHÍNH SÁCH cấp trên equity chạy dần.
    #
    # Không áp một hằng số 3,5x: chính sách thu hẹp đòn bẩy khi đệm tới sàn cạn, và
    # bỏ qua nó là mô phỏng một hệ không có lớp phòng vệ đó.
    equity = EQUITY0
    rows = []
    for ts, x in net26.items():
        day_start = equity
        dec = POL.decide(equity, day_start, 9.33, worst_day_bps=79.4)
        # `net_bps` tính bằng BPS → chia 1e4, KHÔNG phải 100.
        # Chia 100 coi 9 bps là 9% và cho ra 36%/ngày ở đòn bẩy 4x — đúng lỗi đơn
        # vị đã mắc một lần ở `leverage_frontier_2026`. Dấu hiệu nhận ra: đòn bẩy
        # trung bình tụt về 0,61x dù trần 4,0x (chính sách tự cắt vì "lỗ" giả), và
        # toàn bộ lãi/lỗ dồn vào tháng đầu rồi im suốt.
        pnl = equity * (x * dec.leverage / 1e4)
        equity += pnl
        rows.append({"ngay": ts, "pnl": pnl, "equity": equity,
                     "lev": dec.leverage})
    d = pd.DataFrame(rows).set_index("ngay")

    s = pd.concat([pd.Series([EQUITY0]), d["equity"]])
    peak = s.cummax()
    dd_pct = float(((peak - s) / peak * 100.0).max())
    dd_usd = float((peak - s).max())
    net_usd = equity - EQUITY0

    win = d[d["pnl"] > 0]
    loss = d[d["pnl"] <= 0]
    aw = float(win["pnl"].mean()) if len(win) else 0.0
    al = float(loss["pnl"].mean()) if len(loss) else 0.0

    print()
    print("=" * 72)
    print(f"DANH MỤC ĐỦ 27 CHÂN · {net26.index[0]:%Y-%m-%d} → "
          f"{net26.index[-1]:%Y-%m-%d}")
    print("=" * 72)

    print("\nKẾT QUẢ")
    print(f"  Số dư đầu               {_fmt(EQUITY0)}")
    print(f"  Số dư cuối              {_fmt(equity)}")
    print(f"  Lãi/lỗ ròng             {_fmt(net_usd)}  "
          f"({net_usd / EQUITY0 * 100:+.2f}%)")

    months = len(net26) / 21.0
    pm = net_usd / EQUITY0 * 100.0 / months
    print(f"  Số tháng giao dịch      {months:.1f}")
    print(f"  Lợi nhuận mỗi tháng     {pm:+.2f}%")

    print("\nRỦI RO")
    print(f"  MaxDD (từ đỉnh)         {dd_pct:.2f}%  ({_fmt(dd_usd)})")
    print(f"  Equity thấp nhất        {_fmt(float(s.min()))}")
    worst = float(d["pnl"].min()) / EQUITY0 * 100.0
    print(f"  Ngày tệ nhất            {_fmt(float(d['pnl'].min()))}  ({worst:+.2f}%)")
    print(f"  ├─ so SÀN NỘI BỘ 9%     {'ĐẠT' if dd_pct < 9 else 'VƯỢT'}"
          f"  · còn {9 - dd_pct:+.2f} điểm %")
    print(f"  ├─ so LUẬT FTMO 10%     {'ĐẠT' if dd_pct < 10 else 'VI PHẠM'}"
          f"  · còn {10 - dd_pct:+.2f} điểm %")
    print(f"  └─ ngày so MỐC 5%       {'ĐẠT' if abs(worst) < 5 else 'VI PHẠM'}"
          f"  · còn {5 - abs(worst):+.2f} điểm %")

    print("\nCHẤT LƯỢNG (theo NGÀY, không theo lệnh)")
    print(f"  Số ngày giao dịch       {len(d)}")
    print(f"  Ngày lãi / lỗ           {len(win)} / {len(loss)}")
    print(f"  Tỷ lệ ngày lãi          {len(win) / len(d) * 100:.1f}%")
    if al:
        print(f"  R:R (lãi TB : lỗ TB)    {abs(aw / al):.2f} : 1")
    gl = abs(float(loss["pnl"].sum()))
    if gl:
        print(f"  Profit Factor           {float(win['pnl'].sum()) / gl:.2f}")
    print(f"  Đòn bẩy trung bình      {float(d['lev'].mean()):.2f}x "
          f"(trần {POL.LEVERAGE_MAX:.2f}x)")

    # ── THEO THÁNG
    print("\nTHEO THÁNG")
    print(f"  {'Tháng':9} {'Lãi/lỗ':>12} {'%':>8} {'MaxDD':>8}")
    print("  " + "-" * 40)
    for m, g in d.groupby(d.index.to_period("M")):
        # `g["equity"]` chứ không phải `g.equity`: DataFrame có thuộc tính `.eq`
        # (toán tử so sánh) nên truy cập bằng dấu chấm trả về HÀM, và `.iloc` trên
        # hàm ném AttributeError giữa vòng lặp.
        eq0 = float(g["equity"].iloc[0]) - float(g["pnl"].iloc[0])
        eq1 = float(g["equity"].iloc[-1])
        ss = pd.concat([pd.Series([eq0]), g["equity"]])
        mdd = float(((ss.cummax() - ss) / ss.cummax() * 100.0).max())
        print(f"  {str(m):9} {eq1 - eq0:+12,.0f} {(eq1 - eq0) / eq0 * 100:+7.2f}% "
              f"{mdd:7.2f}%")

    # ── ĐÓNG GÓP TỪNG CHÂN
    print("\nĐÓNG GÓP TỪNG CHÂN (bps, 2026)")
    contrib = []
    for k, ser in res.legs.items():
        x = ser[ser.index >= START]
        if len(x) < 10:
            continue
        contrib.append((k, float(x.sum()), k in PORTFOLIO_LEGS))
    contrib.sort(key=lambda t: -t[1])
    tot_p = sum(v for _, v, is_p in contrib if is_p)
    tot_s = sum(v for _, v, is_p in contrib if not is_p)
    for k, v, is_p in contrib:
        print(f"  {k:22} {v:9.1f}  {'DANH MỤC' if is_p else ''}")
    print(f"\n  5 chân danh mục : {tot_p:+9.1f} bps  "
          f"({tot_p / (tot_p + tot_s) * 100:.1f}%)")
    print(f"  22 chân đơn     : {tot_s:+9.1f} bps")

    # ── KỲ THI FTMO
    print("\nKỲ THI FTMO HAI VÒNG")
    if pm > 0:
        s1, s2 = 10.0 / pm, 5.0 / pm
        print(f"  Vòng 1 (+10%)           {s1:.1f} tháng")
        print(f"  Vòng 2 (+5%)            {s2:.1f} tháng")
        print(f"  TỔNG                    {s1 + s2:.1f} tháng")
    else:
        print("  KHÔNG QUA — lợi nhuận âm")

    print("\n⚠️ 5 chân danh mục đo trên ĐƯỜNG PHÂN TÍCH, không qua tầng thực thi")
    print("   (làm tròn lot, spread tại điểm khớp). Con số của chúng LẠC QUAN hơn")
    print("   thực tế một chút — xem docstring đầu file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
