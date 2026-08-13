# -*- coding: utf-8 -*-
"""Backtest 2026 chạy qua ĐÚNG ĐƯỜNG VÀO LỆNH THẬT, báo cáo bằng ngôn ngữ trader.

    .venv311\\Scripts\\python.exe research/fx/live_path_backtest_2026.py

VÌ SAO CẦN MỘT BÀI RIÊNG, KHÔNG DÙNG `portfolio.backtest()`
============================================================
`portfolio.backtest()` là bài toán PHÂN TÍCH: nó cộng chuỗi lợi nhuận bps của từng
chân rồi chuẩn hoá. Nó KHÔNG đi qua `live_decision`, KHÔNG qua `position_book`,
KHÔNG qua `order_plan`/`order_router`, KHÔNG có cầu chì, KHÔNG có làm tròn lot,
KHÔNG có spread thật. Bảy lớp giữa "tín hiệu" và "tiền" đều vắng mặt.

Bài này thay bảy lớp đó bằng chính chúng: mỗi chân chạy qua `parity.replay_leg`,
tức chuỗi `live_decision → position_book → order_plan → order_router → SimBroker`
— đúng những hàm mà tiền thật đi qua. Khác biệt duy nhất là broker: `SimBroker`
thay MT5, và nó quét dừng lỗ bằng bóng nến TRƯỚC khi chiến lược được hỏi, đúng
như dừng lỗ nằm trên server.

GIAI ĐOẠN 2026 LÀ MẪU NGOÀI THẬT SỰ
====================================
Chia mẫu chuẩn của dự án: FORM 2020→2024-01-01, OOS 2024-01-01→nay. Tham số của
27 chân chốt trước 2024, nên 2026 chưa từng được nhìn thấy dưới bất kỳ hình thức
nào — không chọn tham số, không chọn chân, không chuẩn hoá biến động.

ĐIỀU BÀI NÀY **KHÔNG** MÔ PHỎNG — phải nói rõ để không đọc quá số liệu
======================================================================
  · TRIỆT TIÊU GIỮA CÁC CHÂN. Đường live gộp 27 chân thành tỷ trọng RÒNG theo
    công cụ trước khi gửi lệnh (`portfolio.target_weights`), nên hai chân ngược
    chiều trên AUDCAD triệt tiêu nhau và KHÔNG trả spread. Ở đây mỗi chân chạy
    độc lập nên chi phí bị tính ĐỦ cho cả hai — tức bài này BI QUAN hơn thực tế
    ở khoản phí, và số lệnh đếm được nhiều hơn số lệnh thật sẽ gửi.
  · CỔNG CẤP DANH MỤC. `entry_gate` và `ftmo_guard` chặn theo trạng thái toàn
    tài khoản; chạy từng chân thì không có trạng thái ấy.
  · SPREAD CROSS LÀ ƯỚC LƯỢNG. 20 cross tổng hợp chưa đo spread thật của broker.

Đòn bẩy và cỡ lệnh thì CÓ mô phỏng đúng: `ftmo_leverage_policy.decide()` chạy trên
equity chạy dần, và MaxDD được kiểm thẳng với sàn nội bộ 9% cùng luật FTMO 10%.
"""
import importlib
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
from src.python.execution import parity as PARITY  # noqa: E402
from src.python.strategies import registry as REG  # noqa: E402

START = "2026-01-01"
EQUITY0 = 100_000.0

# Mỗi chân một module. Suy từ REGISTRY chứ không gõ tay — danh sách gõ tay là danh
# sách sẽ thiếu đúng chân mới thêm.
_TF_DIR = {"M30": "m30", "H1": "h1", "H4": "h4", "D1": "d1"}


def _leg_modules():
    """(spec, module) của mọi chân ĐƠN chạy được qua đường live.

    Ba chân danh mục (`CurrencyCarry`, `CurrencyReversal`, `Cross*`) không có
    `live_decision` một-công-cụ nên không replay theo chân được — chúng quyết định
    trên CẢ RỔ. Bỏ qua chúng ở đây và ghi rõ trong báo cáo, thay vì lặng lẽ đếm
    thiếu.
    """
    out, skipped = [], []
    for spec in REG.STRATEGIES:
        if spec.stage not in (REG.LIVE, REG.FORWARD_TEST):
            continue
        d = _TF_DIR.get(spec.signal_tf)
        found = None
        if d:
            for p in sorted((ROOT / "src/python/strategies" / d).glob("*.py")):
                if p.name.startswith("__"):
                    continue
                try:
                    m = importlib.import_module(
                        f"src.python.strategies.{d}.{p.stem}")
                except Exception:
                    continue
                if getattr(m, "NAME", None) == spec.name and hasattr(m, "live_decision"):
                    found = m
                    break
        if found is not None:
            out.append((spec, found))
        else:
            skipped.append(spec.name)
    return out, skipped


def _fmt_money(x: float) -> str:
    return f"${x:,.2f}"


def _drawdown(equity: pd.Series) -> tuple:
    """(MaxDD %, MaxDD $, đáy tuyệt đối) — theo ĐỈNH chạy dần.

    Trả CẢ HAI cách đo vì FTMO dùng cách thứ hai: luật neo vào SỐ DƯ BAN ĐẦU TĨNH,
    không trôi theo đỉnh. Tài khoản lên $130k rồi về $95k là DD 27% từ đỉnh nhưng
    VẪN HỢP LỆ; chạm $89.999 một lần là mất tài khoản dù DD từ đỉnh chỉ 10%.
    """
    peak = equity.cummax()
    dd_abs = peak - equity
    dd_pct = (dd_abs / peak * 100.0).max()
    return float(dd_pct), float(dd_abs.max()), float(equity.min())


def main() -> int:
    legs, skipped = _leg_modules()
    print(f"Đang chạy {len(legs)} chân qua ĐƯỜNG LIVE, dữ liệu từ {START}…\n")

    all_trades = []
    per_leg = []
    for spec, mod in legs:
        try:
            ins = mod._load()
            df = ins.df
            # `df.index >= ts` trả về ndarray thuần cho DatetimeIndex, không phải
            # Series — nên `.values` không tồn tại. Dùng `searchsorted` vừa đúng
            # kiểu vừa nhanh hơn: chỉ mục đã sắp xếp sẵn.
            i0 = int(df.index.searchsorted(pd.Timestamp(START)))
            if i0 >= len(df):
                continue
            out = PARITY.replay_leg(mod, start=max(i0, 2),
                                    equity_usd=EQUITY0,
                                    spread_bps=ins.cost_1rt_bps,
                                    with_disaster_stop=True)
            rt = out["broker"].round_trips()
            if rt.empty:
                per_leg.append((spec.name, 0, 0.0))
                continue
            rt["leg"] = spec.name
            rt["symbol"] = spec.symbols[0] if spec.symbols else rt["symbol"]
            all_trades.append(rt)
            per_leg.append((spec.name, len(rt), float(rt["gross_bps"].sum())))
            print(f"  {spec.name:22} {len(rt):3} lệnh  "
                  f"{rt['gross_bps'].sum():+8.1f} bps")
        except Exception as exc:
            print(f"  {spec.name:22} LỖI {type(exc).__name__}: {str(exc)[:60]}")

    if not all_trades:
        print("\nKhông có lệnh nào — kiểm tra dữ liệu 2026.")
        return 1

    tr = pd.concat(all_trades, ignore_index=True).sort_values("exit_time")

    # ── Quy bps → TIỀN qua đúng công thức cỡ lệnh của hệ.
    #
    # `lot = equity × leverage × w / notional`, nên lãi/lỗ USD của một lệnh bằng
    # `equity × leverage × w × gross_bps/1e4`. Tỷ trọng mỗi chân = 1/N (đều nhau,
    # đúng như `LEG_WEIGHTS` hiện tại), và đòn bẩy lấy từ CHÍNH sách chạy trên
    # equity chạy dần — không phải một hằng số áp cứng.
    n_legs = max(len(set(tr["leg"])), 1)
    w = 1.0 / n_legs
    equity = EQUITY0
    day_start = EQUITY0
    cur_day = None
    rows = []
    for _, t in tr.iterrows():
        d = pd.Timestamp(t["exit_time"]).date()
        if d != cur_day:
            cur_day, day_start = d, equity
        dec = POL.decide(equity, day_start, 9.33, worst_day_bps=79.4)
        pnl = equity * dec.leverage * w * float(t["gross_bps"]) / 1e4
        equity += pnl
        rows.append({**t.to_dict(), "leverage": dec.leverage, "pnl_usd": pnl,
                     "equity": equity})
    res = pd.DataFrame(rows)
    eq = pd.Series(res["equity"].values,
                   index=pd.to_datetime(res["exit_time"]))

    wins = res[res["pnl_usd"] > 0]
    losses = res[res["pnl_usd"] <= 0]
    gp = float(wins["pnl_usd"].sum())
    gl = abs(float(losses["pnl_usd"].sum()))
    dd_pct, dd_usd, eq_min = _drawdown(pd.concat([pd.Series([EQUITY0]), eq]))

    # Chuỗi thua dài nhất
    streak = best_streak = 0
    for p in res["pnl_usd"]:
        streak = streak + 1 if p <= 0 else 0
        best_streak = max(best_streak, streak)

    daily = res.groupby(pd.to_datetime(res["exit_time"]).dt.date)["pnl_usd"].sum()
    worst_day = float(daily.min()) if len(daily) else 0.0
    worst_day_pct = worst_day / EQUITY0 * 100.0
    months = max(len(set(pd.to_datetime(res["exit_time"]).dt.to_period("M"))), 1)

    avg_win = float(wins["pnl_usd"].mean()) if len(wins) else 0.0
    avg_loss = float(losses["pnl_usd"].mean()) if len(losses) else 0.0
    rr = abs(avg_win / avg_loss) if avg_loss else float("nan")
    net = equity - EQUITY0

    print(f"\n{'='*66}")
    print(f"BÁO CÁO BACKTEST — ĐƯỜNG VÀO LỆNH THẬT · {START} → "
          f"{pd.Timestamp(res['exit_time'].iloc[-1]):%Y-%m-%d}")
    print("=" * 66)

    print("\nKẾT QUẢ")
    print(f"  Số dư đầu               {_fmt_money(EQUITY0)}")
    print(f"  Số dư cuối              {_fmt_money(equity)}")
    print(f"  Lãi/lỗ ròng             {_fmt_money(net)}  ({net / EQUITY0 * 100:+.2f}%)")

    print("\nRỦI RO")
    print(f"  MaxDD (từ đỉnh)         {dd_pct:.2f}%  ({_fmt_money(dd_usd)})")
    print(f"  Equity thấp nhất        {_fmt_money(eq_min)}")
    print(f"  Ngày tệ nhất            {_fmt_money(worst_day)}  ({worst_day_pct:+.2f}%)")
    print(f"  ├─ so SÀN NỘI BỘ 9%     {'ĐẠT' if dd_pct < 9 else 'VƯỢT'}"
          f"  · còn {9 - dd_pct:+.2f} điểm %")
    print(f"  ├─ so LUẬT FTMO 10%     {'ĐẠT' if dd_pct < 10 else 'VI PHẠM'}"
          f"  · còn {10 - dd_pct:+.2f} điểm %")
    print(f"  └─ ngày so MỐC 5%       "
          f"{'ĐẠT' if abs(worst_day_pct) < 5 else 'VI PHẠM'}"
          f"  · còn {5 - abs(worst_day_pct):+.2f} điểm %")

    print("\nCHẤT LƯỢNG LỆNH")
    print(f"  Tổng số lệnh            {len(res)}")
    print(f"  Thắng / thua            {len(wins)} / {len(losses)}")
    print(f"  Winrate                 {len(wins) / len(res) * 100:.1f}%")
    # ⚠️ SỬA 15/08/2026 — NHÃN CŨ ĐỌC NGƯỢC.
    # Bản trước in "1 : {rr}" với rr = lãi_TB/lỗ_TB. Với rr = 0,70 nó hiện
    # "1 : 0,70", đọc là "được 1 rủi 0,70" — tức lãi LỚN HƠN lỗ. Sự thật ngược
    # lại: lãi TB $42,12 còn lỗ TB $60,01. Quy ước R:R là reward TRƯỚC risk sau,
    # nên phải in "0,70 : 1".
    print(f"  R:R (lãi TB : lỗ TB)    {rr:.2f} : 1" if rr == rr else "  R:R  —")
    print(f"  Profit Factor           {gp / gl:.2f}" if gl > 0 else "  Profit Factor  —")

    print("\nPHÂN BỐ")
    print(f"  Lệnh lãi lớn nhất       {_fmt_money(float(res['pnl_usd'].max()))}")
    print(f"  Lệnh lỗ lớn nhất        {_fmt_money(float(res['pnl_usd'].min()))}")
    print(f"  Lãi trung bình          {_fmt_money(avg_win)}")
    print(f"  Lỗ trung bình           {_fmt_money(avg_loss)}")
    print(f"  Chuỗi thua dài nhất     {best_streak} lệnh")

    print("\nTHỜI GIAN")
    print(f"  Nắm giữ trung bình      {res['bars'].mean():.1f} nến")
    print(f"  Số lệnh mỗi tháng       {len(res) / months:.1f}")
    print(f"  Đòn bẩy trung bình      {res['leverage'].mean():.2f}x "
          f"(trần {POL.LEVERAGE_MAX:.2f}x)")

    by_reason = res.groupby("reason")["pnl_usd"].agg(["count", "sum"])
    print("\nLÝ DO ĐÓNG LỆNH")
    for r, row in by_reason.sort_values("count", ascending=False).iterrows():
        print(f"  {str(r):22} {int(row['count']):4} lệnh  "
              f"{_fmt_money(float(row['sum']))}")

    if skipped:
        print(f"\nKHÔNG replay được ({len(skipped)} chân danh mục, quyết định trên "
              f"CẢ RỔ nên không tách theo chân được):")
        print(f"  {', '.join(skipped)}")

    out_csv = ROOT / "reports" / "fx_research" / "live_path_backtest_2026.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(out_csv, index=False, encoding="utf-8")
    print(f"\nChi tiết từng lệnh: {out_csv.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
