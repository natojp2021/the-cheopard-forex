"""Vòng 71 — BÁO CÁO THEO TÀI KHOẢN $100.000, ngôn ngữ trader.

VÌ SAO CẦN
==========
Mọi báo cáo trước dùng đơn vị "σ danh mục" — số lần độ lệch chuẩn ngày của từng chân
sau khi chuẩn hoá. Đơn vị đó ĐÚNG cho việc so sánh chiến lược với nhau và bất biến
theo đòn bẩy, nhưng nó không trả lời câu hỏi mà người vận hành thật sự hỏi:

    "Bỏ 100.000 đô vào thì một năm được bao nhiêu, và có lúc nào tụt bao nhiêu?"

Module này quy toàn bộ sang đô-la và phần trăm tài khoản, kèm các chỉ số quen thuộc:
tỷ lệ thắng, R:R, profit factor, drawdown, chuỗi tháng thua dài nhất.

ĐÒN BẨY LÀ THAM SỐ, KHÔNG PHẢI HẰNG SỐ — VÀ ĐÂY LÀ CHỖ DỄ TỰ LỪA NHẤT
======================================================================
Sharpe không đổi theo đòn bẩy; lợi nhuận và drawdown thì đổi TUYẾN TÍNH. Nên một báo
cáo "lãi 60%/năm" không nói gì nếu không kèm drawdown và mức đòn bẩy đã dùng.

Ở đây báo cáo BA kịch bản, và mỗi kịch bản neo vào một ràng buộc THẬT:

    THẬN TRỌNG   mục tiêu biến động 6%/năm   — dư địa lớn cho ngày xấu bất thường
    CHUẨN        mục tiêu biến động 10%/năm  — mức thường dùng cho tài khoản quỹ
    FTMO         đòn bẩy do `ftmo_leverage_policy` quyết, có ràng buộc TAIL

Kịch bản FTMO là kịch bản DUY NHẤT dùng được cho kỳ thi: nó tính đòn bẩy từ biên độ
equity còn lại VÀ từ ngày tệ nhất đã quan sát, chứ không từ một con số chọn sẵn.

MỘT CẢNH BÁO PHẢI ĐỌC TRƯỚC MỌI CON SỐ
=======================================
Backtest KHÔNG có: trượt giá khi tin ra, spread giãn lúc thanh khoản mỏng, lệnh bị
từ chối, và chênh lệch giữa spread tài khoản demo với tài khoản thật. Mọi con số
dưới đây là GIỚI HẠN TRÊN của cái đạt được, không phải kỳ vọng.
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

from src.python.strategies import portfolio as PF
from src.python.strategies import registry as REG

pd.set_option("display.width", 220, "display.max_columns", 30, "display.max_rows", 100)
EQUITY = 100_000.0
FORM = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports"


def account_metrics(pnl_pct: pd.Series, equity: float = EQUITY) -> Dict[str, float]:
    """Chỉ số theo ngôn ngữ trader từ chuỗi lợi nhuận NGÀY tính bằng % tài khoản.

    Dùng equity CỘNG DỒN (không tái đầu tư) chứ không nhân lãi kép: quỹ cấp vốn tính
    mục tiêu và hạn mức trên số dư ban đầu, nên cộng dồn là cách đọc khớp với luật
    của họ. Nhân lãi kép sẽ thổi phồng con số cuối mà không đổi được rủi ro thật.
    """
    eq = equity * (1 + pnl_pct.cumsum() / 100.0)
    dd_abs = eq.cummax() - eq
    dd_pct = dd_abs / eq.cummax() * 100.0
    yrs = max((pnl_pct.index.max() - pnl_pct.index.min()).days / 365.25, 1e-9)
    profit = float(eq.iloc[-1] - equity)
    days_with = pnl_pct[pnl_pct != 0]
    month = pnl_pct.resample("MS").sum()

    # chuỗi tháng thua dài nhất — con số người vận hành cảm nhận được
    streak, max_streak = 0, 0
    for v in month:
        streak = streak + 1 if v < 0 else 0
        max_streak = max(max_streak, streak)

    daily_profit = pnl_pct[pnl_pct > 0].sum()
    daily_loss = -pnl_pct[pnl_pct < 0].sum()
    sd = float(pnl_pct.std(ddof=1))
    dsd = float(pnl_pct[pnl_pct < 0].std(ddof=1))
    return {
        "lãi_usd": profit,
        "lãi_pct": profit / equity * 100.0,
        "lãi_năm_usd": profit / yrs,
        "lãi_năm_pct": profit / equity * 100.0 / yrs,
        "maxdd_usd": float(dd_abs.max()),
        "maxdd_pct": float(dd_pct.max()),
        "dd_ngày_dài_nhất": int((dd_abs > 0).astype(int).groupby(
            (dd_abs == 0).cumsum()).sum().max() or 0),
        "vol_năm_pct": sd * np.sqrt(252),
        "sharpe": float(pnl_pct.mean()) / sd * np.sqrt(252) if sd > 0 else np.nan,
        "sortino": float(pnl_pct.mean()) / dsd * np.sqrt(252) if dsd > 0 else np.nan,
        "calmar": (profit / equity * 100.0 / yrs) / max(float(dd_pct.max()), 1e-9),
        "ngày_thắng_pct": float((days_with > 0).mean()) * 100.0 if len(days_with) else np.nan,
        "profit_factor": daily_profit / daily_loss if daily_loss > 0 else np.inf,
        "ngày_tốt_nhất_usd": float(pnl_pct.max()) / 100 * equity,
        "ngày_tệ_nhất_usd": float(pnl_pct.min()) / 100 * equity,
        "tháng_thắng_pct": float((month > 0).mean()) * 100.0,
        "chuỗi_tháng_thua": max_streak,
        "equity_cuối": float(eq.iloc[-1]),
    }


def pool_trades() -> pd.DataFrame:
    """Gộp TOÀN BỘ lệnh của mọi chân theo-lệnh để tính R:R và tỷ lệ thắng thật.

    Chỉ gộp được các chân sinh ra LỆNH RIÊNG (z-band và bốn họ tín hiệu). Bốn chân
    D1/H4 kiểu tỷ trọng không có khái niệm "lệnh" — chúng tái cân bằng chứ không
    vào/ra, nên đưa vào bảng lệnh sẽ trộn hai thứ khác bản chất.
    """
    from importlib import import_module
    rows = []
    for s in REG.STRATEGIES:
        mod_path = f"src.python.strategies.{s.signal_tf.lower()}.{s.module}"
        try:
            m = import_module(mod_path)
            bt = m.backtest()
            T = getattr(bt, "trades", None)
            if T is None or T.empty:
                continue
        except Exception:
            continue
        t = T.copy()
        t["strategy"] = s.name
        t["tf"] = s.signal_tf
        rows.append(t[["strategy", "tf", "entry_time", "exit_time", "bars",
                       "net_bps", "gross_bps", "cost_bps"]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def main() -> None:
    t0 = time.time()
    print("đang chạy backtest 27 chân…", file=sys.stderr)
    res = PF.backtest()

    print("=" * 118)
    print("BÁO CÁO TÀI KHOẢN $100.000 — ba mức rủi ro")
    print("=" * 118)
    print()

    summary = {}
    for name_text, vol_target in (("THẬN TRỌNG", 6.0), ("CHUẨN", 10.0), ("MẠO HIỂM", 15.0)):
        bps = res.risk_parity_bps(target_vol_pct_annual=vol_target)
        pct = bps / 100.0                      # bps → % tài khoản
        summary[name_text] = account_metrics(pct)
        summary[name_text]["mục_tiêu_vol"] = vol_target

    B = pd.DataFrame(summary).T
    current = ["lãi_năm_pct", "lãi_năm_usd", "maxdd_pct", "maxdd_usd", "vol_năm_pct",
            "sharpe", "sortino", "calmar", "profit_factor", "ngày_thắng_pct",
            "tháng_thắng_pct", "chuỗi_tháng_thua", "ngày_tệ_nhất_usd"]
    print(B[current].round(2).to_string())
    print()
    print("   lãi_năm_*  = trung bình mỗi năm trên 6,5 năm, KHÔNG nhân lãi kép")
    print("   maxdd_*    = sụt vốn sâu nhất từ đỉnh, tính trên equity cộng dồn")
    print("   calmar     = lãi năm ÷ MaxDD — bao nhiêu lợi nhuận cho mỗi đơn vị đau")

    # ── chi tiết mức CHUẨN
    print()
    print("=" * 118)
    print("CHI TIẾT MỨC CHUẨN (mục tiêu biến động 10%/năm)")
    print("=" * 118)
    bps = res.risk_parity_bps(target_vol_pct_annual=10.0)
    pct = bps / 100.0
    k = summary["CHUẨN"]
    eq = EQUITY * (1 + pct.cumsum() / 100.0)
    print(f"   Vốn ban đầu        ${EQUITY:>12,.0f}")
    print(f"   Equity cuối kỳ     ${k['equity_cuối']:>12,.0f}")
    print(f"   Tổng lãi           ${k['lãi_usd']:>12,.0f}   ({k['lãi_pct']:+.1f}%)")
    print(f"   Lãi mỗi năm        ${k['lãi_năm_usd']:>12,.0f}   ({k['lãi_năm_pct']:+.1f}%/năm)")
    print(f"   Sụt vốn sâu nhất  −${k['maxdd_usd']:>12,.0f}   (−{k['maxdd_pct']:.1f}%)")
    print(f"   Ngày tệ nhất      −${abs(k['ngày_tệ_nhất_usd']):>12,.0f}")
    print(f"   Ngày tốt nhất      ${k['ngày_tốt_nhất_usd']:>12,.0f}")
    print(f"   Thời gian dưới đỉnh {k['dd_ngày_dài_nhất']:>10.0f} ngày liên tiếp")
    print()
    yr = pct.groupby(pct.index.year).sum()
    print("   LỢI NHUẬN TỪNG NĂM")
    for y, v in yr.items():
        sub = pct[pct.index.year == y]
        e = EQUITY * (1 + sub.cumsum() / 100)
        d = float((e.cummax() - e).max()) / EQUITY * 100
        print(f"     {int(y)}   {v:+7.2f}%   ${v / 100 * EQUITY:>+10,.0f}   "
              f"DD trong năm −{d:.1f}%")

    # ── thống kê theo LỆNH
    print()
    print("=" * 118)
    print("THỐNG KÊ THEO LỆNH — gộp toàn bộ chân theo-lệnh")
    print("=" * 118)
    T = pool_trades()
    if not T.empty:
        v = T["net_bps"]
        wins = v[v > 0]
        losses = v[v <= 0]
        rr = float(wins.mean()) / abs(float(losses.mean())) if len(losses) else np.inf
        print(f"   Tổng số lệnh          {len(T):>10,}")
        print(f"   Tỷ lệ thắng           {float((v > 0).mean()) * 100:>9.1f}%")
        print(f"   Lãi trung bình/lệnh   {float(wins.mean()):>9.2f} bps")
        print(f"   Lỗ trung bình/lệnh    {float(losses.mean()):>9.2f} bps")
        print(f"   **R:R trung bình**    {rr:>9.2f}  (lãi TB ÷ |lỗ TB|)")
        print(f"   Profit factor         {float(wins.sum()) / abs(float(losses.sum())):>9.2f}")
        print(f"   Kỳ vọng mỗi lệnh      {float(v.mean()):>9.2f} bps")
        print(f"   Chi phí mỗi lệnh      {float(T['cost_bps'].mean()):>9.2f} bps "
              f"({float(T['cost_bps'].sum()) / float(T['gross_bps'].sum()) * 100:.0f}% "
              f"lợi nhuận gộp)")
        print(f"   Giữ lệnh trung bình   {float(T['bars'].mean()):>9.1f} nến")
        print()
        print("   THEO KHUNG")
        g = T.groupby("tf").agg(
            lệnh=("net_bps", "size"),
            thắng_pct=("net_bps", lambda x: round(float((x > 0).mean()) * 100, 1)),
            net_bps=("net_bps", lambda x: round(float(x.mean()), 2)),
            phí_bps=("cost_bps", lambda x: round(float(x.mean()), 2)))
        print("   " + g.to_string().replace("\n", "\n   "))
        print()
        print(f"   Số lệnh mỗi năm       {len(T) / 6.5:>9.0f}")
        print(f"   Số lệnh mỗi tuần      {len(T) / 6.5 / 52:>9.1f}")
        T.to_csv(OUT / "all_trades.csv", index=False)

    # ── FTMO
    print()
    print("=" * 118)
    print("KỊCH BẢN FTMO $100.000 — đòn bẩy do chính sách quyết, có ràng buộc TAIL")
    print("=" * 118)
    try:
        from src.python.execution import ftmo_leverage_policy as POL
        daily_vol_bps = float(res.net_bps.std(ddof=1))
        worst_bps = abs(float(res.net_bps.min()))
        lev = POL.decide(equity=EQUITY, day_start_balance=EQUITY,
                         daily_vol_bps=daily_vol_bps, worst_day_bps=worst_bps)
        lev = float(lev if not hasattr(lev, "leverage") else lev.leverage)
        print(f"   σ ngày của danh mục   {daily_vol_bps:>9.1f} bps "
              f"({daily_vol_bps / 100:.2f}% tài khoản)")
        print(f"   Ngày tệ nhất đã thấy  {worst_bps:>9.1f} bps "
              f"({worst_bps / 100:.2f}%)  = {worst_bps / daily_vol_bps:.1f}σ")
        print(f"   **Đòn bẩy cho phép**  {lev:>9.2f}x")
        p_ftmo = res.net_bps * lev / 100.0
        kf = account_metrics(p_ftmo)
        print()
        print(f"   Lãi mỗi năm           ${kf['lãi_năm_usd']:>10,.0f}   "
              f"({kf['lãi_năm_pct']:+.1f}%/năm)")
        print(f"   Sụt vốn sâu nhất     −${kf['maxdd_usd']:>10,.0f}   "
              f"(−{kf['maxdd_pct']:.1f}%)")
        print(f"   Ngày tệ nhất         −${abs(kf['ngày_tệ_nhất_usd']):>10,.0f}   "
              f"(−{abs(kf['ngày_tệ_nhất_usd']) / EQUITY * 100:.2f}%)")
        print()
        print(f"   Giới hạn FTMO: lỗ NGÀY 5% (${EQUITY * 0.05:,.0f}) · "
              f"lỗ TỔNG 10% (${EQUITY * 0.10:,.0f})")
        # ⚠️ SO SAI MỐC — sửa 15/08/2026. Bản trước so `maxdd_usd` (đo từ ĐỈNH
        # equity) với hạn mức 10% của FTMO (neo vào BALANCE BAN ĐẦU TĨNH), rồi báo
        # "VI PHẠM" cho một đường equity hoàn toàn hợp lệ.
        #
        # Đây đúng cái bẫy thứ ba ghi ở đầu `core/infra/ftmo.py`: tài khoản lên
        # $137k rồi rơi về $125k là drawdown $12k tính từ đỉnh, nhưng equity chưa
        # bao giờ xuống dưới $90k nên KHÔNG vi phạm gì cả. Thứ FTMO đo là
        # equity THẤP NHẤT so với $100.000, không phải biên độ sụt từ đỉnh.
        # Đường equity của CHÍNH kịch bản FTMO — không dùng lại `eq` của mức
        # CHUẨN ở trên, đó là một đòn bẩy khác và một đường khác.
        eq_ftmo = EQUITY * (1 + p_ftmo.cumsum() / 100.0)
        eq_floor = float(eq_ftmo.min())
        daily_ok = abs(kf['ngày_tệ_nhất_usd']) < EQUITY * 0.05
        total_ok = eq_floor > EQUITY * 0.90
        print(f"   Equity THẤP NHẤT      ${eq_floor:>10,.0f}   "
              f"(sàn tuyệt đối ${EQUITY * 0.90:,.0f})")
        print(f"   → ngày tệ nhất {'AN TOÀN' if daily_ok else 'VI PHẠM'} · "
              f"sàn tuyệt đối {'AN TOÀN' if total_ok else 'VI PHẠM'}")
        print(f"   (MaxDD {kf['maxdd_pct']:.1f}% đo từ ĐỈNH — KHÔNG phải mốc FTMO. "
              f"Mốc nội bộ của hệ là 9%, xem ftmo_leverage_policy.DD_SELF_CAP.)")
        print(f"   → mục tiêu Phase 1 (+10% = ${EQUITY * 0.10:,.0f}) đạt sau khoảng "
              f"{EQUITY * 0.10 / max(kf['lãi_năm_usd'], 1) * 12:.1f} tháng")
        summary["FTMO"] = kf
    except Exception as exc:
        print(f"   không tính được: {exc}")

    pd.DataFrame(summary).T.to_csv(OUT / "account_report.csv")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
