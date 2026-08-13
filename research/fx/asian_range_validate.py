"""Vòng 70 — KIỂM ĐỊNH Asian Range Breakout. Luật cho lãi, câu hỏi là lãi có THẬT không.

KẾT QUẢ THÔ TỪ VÒNG 69
======================
    USDJPY, luật gốc, DST đúng, đủ chi phí:
        Sharpe ALL 0,319 · FORM 0,342 · OOS 0,281
        1.636 lệnh · thắng 44,1% · net +0,90 bps/lệnh · t = 0,98
        +2,24 %/năm · MaxDD 12,25% · 4/7 năm dương

Có lãi. Nhưng ba con số cùng nói một điều: **t = 0,98** (cần > 2 để phân biệt với
ngẫu nhiên), **4/7 năm dương**, và **net +0,90 bps/lệnh so với chi phí 1,20** — tức
lợi nhuận ròng chưa bằng chi phí phải trả.

BA CÂU HỎI VÒNG NÀY TRẢ LỜI
============================
  1. Lãi này có phân biệt được với ngẫu nhiên không?  → control + bootstrap
  2. Nó có phải hiệu ứng THẬT hay chỉ là một mốc giờ may mắn?  → quét toàn bộ 24 giờ
  3. Nếu chỉnh lại tham số thì có cứu được không?  → quét cửa sổ và giờ thoát

Câu 2 quan trọng nhất. Vòng 69 đã cho một tín hiệu xấu: ép cứng múi giờ khác nhau
cho Sharpe từ 0,086 đến 0,357 — chênh 4 lần chỉ vì lệch một hai tiếng. Nếu quét cả
24 giờ mà thấy nhiều mốc cũng cho kết quả tương đương, thì mốc 03:00-06:00 không có
gì đặc biệt và "chiến lược" chỉ là một ô trong lưới.
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import numpy as np
import pandas as pd

from research.fx.asian_range_breakout import Config, backtest, load_pair, sharpe
from research.fx.mr_validate import block_bootstrap

pd.set_option("display.width", 220, "display.max_columns", 30, "display.max_rows", 300)
FORM_END = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"


def control_random_day(T: pd.DataFrame, df: pd.DataFrame, seed: int) -> float:
    """Control: giữ NGUYÊN chiều và thời gian giữ, vào lệnh vào NGÀY KHÁC.

    Đây là control đúng cho một luật theo phiên: nó giữ mọi thứ trừ việc "biên độ
    phiên Á hôm đó có ý nghĩa gì". Nếu chiến lược thật không hơn control thì lãi
    đến từ nhịp vào/ra chứ không từ mức biên độ.
    """
    rng = np.random.default_rng(seed)
    c = df["close"].to_numpy()
    n = len(c)
    out = []
    for _, t in T.iterrows():
        bars = int(t["bars"])
        if bars < 1 or bars >= n - 2:
            continue
        i = int(rng.integers(0, n - bars - 1))
        side = int(t["side"])
        g = side * (c[i + bars] - c[i]) / c[i] * 1e4
        out.append(g - t["cost_bps"])
    s = pd.Series(out)
    sd = float(s.std(ddof=1))
    return float(s.mean()) / sd * np.sqrt(len(s)) if sd > 0 else np.nan


def main() -> None:
    t0 = time.time()
    df, cost, swap = load_pair("USDJPY")
    r = backtest(df, cost, swap, Config())
    T, d = r.trades, r.pnl_daily
    v = T["net_bps"]
    tm = float(v.mean()) / float(v.std(ddof=1)) * np.sqrt(len(v))

    print("USDJPY · luật gốc · DST đúng")
    print(f"  Sharpe {sharpe(d):+.3f} · FORM {sharpe(d, hi=FORM_END):+.3f} · "
          f"OOS {sharpe(d, lo=FORM_END):+.3f} · {len(T)} lệnh · "
          f"net {float(v.mean()):+.2f} bps (t = {tm:+.2f})")

    # ── 1. control ngày ngẫu nhiên
    print()
    print("=" * 118)
    print("1. CONTROL — giữ chiều và thời gian giữ, vào lệnh NGÀY NGẪU NHIÊN")
    print("=" * 118)
    ct = np.array([control_random_day(T, df, s) for s in range(300)])
    ct = ct[np.isfinite(ct)]
    pct = float((ct < tm).mean())
    print(f"   t thật {tm:+.2f}  vs  control p50 {np.median(ct):+.2f} "
          f"[p5 {np.percentile(ct, 5):+.2f} · p95 {np.percentile(ct, 95):+.2f}]")
    print(f"   phân vị {pct:.1%} · p = {1 - pct:.4f}  "
          f"{'ĐẠT' if pct >= 0.95 else 'KHÔNG ĐẠT — không phân biệt được với ngẫu nhiên'}")

    # ── 2. bootstrap
    bs = block_bootstrap(d)
    print()
    print("=" * 118)
    print("2. BOOTSTRAP KHỐI 21 ngày, 2000 lần")
    print("=" * 118)
    print(f"   Sharpe {bs['mean']:+.3f} · CI95 [{bs['ci_lo']:+.3f} · {bs['ci_hi']:+.3f}] "
          f"· P(<0) = {bs['p_neg']:.1%}  "
          f"{'ĐẠT' if bs['p_neg'] < 0.10 else 'KHÔNG ĐẠT'}")
    print(f"   → khoảng tin cậy {'CHỨA' if bs['ci_lo'] < 0 < bs['ci_hi'] else 'KHÔNG chứa'} "
          f"số 0")

    # ── 3. quét TOÀN BỘ 24 giờ bắt đầu — mốc 03:00 có gì đặc biệt không
    print()
    print("=" * 118)
    print("3. QUÉT 24 GIỜ BẮT ĐẦU — mốc 03:00 của luật gốc có đặc biệt không?")
    print("=" * 118)
    rows = []
    for h0 in range(24):
        cfg = Config(range_start_broker=h0, range_end_broker=(h0 + 3) % 24)
        rr = backtest(df, cost, swap, cfg)
        if rr.trades.empty or len(rr.trades) < 200:
            continue
        vv = rr.trades["net_bps"]
        rows.append({"giờ bắt đầu": h0, "ALL": round(sharpe(rr.pnl_daily), 3),
                     "OOS": round(sharpe(rr.pnl_daily, lo=FORM_END), 3),
                     "n": len(rr.trades),
                     "net": round(float(vv.mean()), 2),
                     "t": round(float(vv.mean()) / float(vv.std(ddof=1))
                                * np.sqrt(len(vv)), 2)})
    G = pd.DataFrame(rows).sort_values("ALL", ascending=False)
    print(G.to_string(index=False))
    baseline = G[G["giờ bắt đầu"] == 3]
    rows = int((G["ALL"] > float(baseline["ALL"].iloc[0])).sum()) + 1 if len(baseline) else 0
    print(f"\n   Mốc 03:00 của luật gốc đứng hạng **{hang}/{len(G)}** trong 24 mốc.")
    print(f"   Số mốc có ALL > 0: {int((G['ALL'] > 0).sum())}/{len(G)}")
    print(f"   Số mốc có t > 2,0: {int((G['t'] > 2.0).sum())}/{len(G)}")

    # ── 4. quét giờ thoát
    print()
    print("=" * 118)
    print("4. QUÉT GIỜ THOÁT — 19:00 có đặc biệt không?")
    print("=" * 118)
    rows = []
    for he in range(8, 24):
        cfg = Config(exit_hour_broker=he)
        rr = backtest(df, cost, swap, cfg)
        if rr.trades.empty:
            continue
        vv = rr.trades["net_bps"]
        rows.append({"giờ thoát": he, "ALL": round(sharpe(rr.pnl_daily), 3),
                     "OOS": round(sharpe(rr.pnl_daily, lo=FORM_END), 3),
                     "net": round(float(vv.mean()), 2),
                     "t": round(float(vv.mean()) / float(vv.std(ddof=1))
                                * np.sqrt(len(vv)), 2)})
    E = pd.DataFrame(rows).sort_values("ALL", ascending=False)
    print(E.to_string(index=False))

    # ── 5. phân rã: lãi đến từ đâu
    print()
    print("=" * 118)
    print("5. LÃI ĐẾN TỪ ĐÂU — phân rã theo năm và theo chiều")
    print("=" * 118)
    yr = d.groupby(d.index.year).sum() / 100.0
    print("   theo năm (%): " + "  ".join(f"{int(y)}: {x:+.2f}" for y, x in yr.items()))
    for s_ in (1, -1):
        sub = T[T["side"] == s_]
        print(f"   {'MUA ' if s_ > 0 else 'BÁN '}: {len(sub):4d} lệnh · "
              f"thắng {float((sub['net_bps'] > 0).mean()) * 100:4.1f}% · "
              f"net {float(sub['net_bps'].mean()):+6.2f} bps · "
              f"tổng {float(sub['net_bps'].sum()) / 100:+7.2f}%")
    mo = d.resample("MS").sum()
    left = float((mo.sum() - mo.nlargest(5).sum()) / 100.0)
    print(f"   bỏ 5 tháng tốt nhất: {float(mo.nlargest(5).sum()) / mo.sum():.1%} "
          f"tổng lợi nhuận → còn {con:+.2f}%  "
          f"{'GIỮ DẤU' if con > 0 else 'ĐỔI DẤU'}")

    G.to_csv(OUT / "asian_range_hours.csv", index=False)
    E.to_csv(OUT / "asian_range_exits.csv", index=False)
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
