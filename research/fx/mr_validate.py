"""Vòng 60 — KIỂM ĐỊNH ĐẦY ĐỦ sáu ứng viên hồi quy M30/H1 trước khi đưa vào sản xuất.

SÁU ỨNG VIÊN — chọn theo CÂN BẰNG FORM/OOS, không theo Sharpe cao nhất
=======================================================================
    H1  NZDCAD  N=48  k=2,0  time_only_2x   FORM 0,506 · OOS 1,096
    H1  AUDCAD  N=48  k=1,5  time_only      FORM 0,811 · OOS 0,592
    H1  NZDCAD  N=48  k=1,5  time_only      FORM 0,594 · OOS 0,717
    M30 GBPAUD  N=96  k=2,5  time_only      FORM 0,805 · OOS 0,935
    M30 AUDCAD  N=96  k=1,5  time_only      FORM 0,648 · OOS 0,843
    M30 NZDCAD  N=96  k=1,5  time_only      FORM 0,692 · OOS 0,579

GBPNZD BỊ LOẠI TỪ ĐẦU dù có Sharpe cao nhất toàn bộ lab (ALL 1,102): FORM 1,551 so
với OOS 0,238 — chênh 6,5 lần. Đó là chữ ký overfit, và chọn nó vì con số ALL đẹp
chính là sai lầm mà toàn bộ giao thức này được dựng ra để tránh.

KIỂM ĐỊNH ĐẶC THÙ CHO CHIẾN LƯỢC THEO LỆNH
===========================================
Khác với chiến lược tỷ trọng, ở đây control phải phá TÍN HIỆU mà giữ nguyên CẤU TRÚC
GIAO DỊCH (số lệnh, thời điểm, thời gian giữ). Hai control độc lập:

    control THỜI ĐIỂM   giữ nguyên số lệnh và phân phối thời gian giữ, nhưng vào lệnh
                        tại thời điểm NGẪU NHIÊN. Nếu chiến lược thật không hơn, thì
                        "vào lệnh lúc nào cũng được" và tín hiệu vô giá trị.
    control CHIỀU       giữ nguyên thời điểm, ĐẢO chiều ngẫu nhiên. Tách riêng phần
                        đóng góp của việc CHỌN ĐÚNG CHIỀU khỏi phần đến từ nhịp vào ra.

Hai control này bắt hai lỗi khác nhau và cả hai đều phải qua.
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

from research.fx.trade_lab import (ExitCfg, load_crosses, run_trades, sharpe,
                                   sig_zband)

pd.set_option("display.width", 240, "display.max_columns", 30)
FORM_END = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"

# (khung, công cụ, N, k, tên cấu hình thoát, hệ số time-stop)
CANDIDATES: Tuple[Tuple[str, str, int, float, str, float], ...] = (
    ("H4", "GBPCAD", 96, 1.5, "time_only_2x", 2.0),
    ("H4", "GBPCAD", 96, 2.0, "time_only_2x", 2.0),
    ("H4", "GBPCAD", 96, 2.5, "time_only", 1.0),
    ("H4", "EURCHF", 96, 2.0, "time_only", 1.0),
)


def control_timing(trades: pd.DataFrame, ins, seed: int) -> float:
    """Control THỜI ĐIỂM: giữ số lệnh và thời gian giữ, vào lệnh tại thời điểm ngẫu nhiên."""
    rng = np.random.default_rng(seed)
    c = ins.df["close"].to_numpy()
    n = len(c)
    out = []
    for _, t in trades.iterrows():
        bars = int(t["bars"])
        if bars < 1 or bars >= n - 2:
            continue
        i = int(rng.integers(0, n - bars - 1))
        side = int(t["side"])
        gross = side * (c[i + bars] - c[i]) / c[i] * 1e4
        out.append(gross - t["cost_bps"])
    if not out:
        return np.nan
    s = pd.Series(out)
    return float(s.mean()) / float(s.std(ddof=1)) * np.sqrt(len(s)) if s.std(ddof=1) > 0 else np.nan


def control_side(trades: pd.DataFrame, seed: int) -> float:
    """Control CHIỀU: giữ nguyên thời điểm và thời gian giữ, ĐẢO chiều ngẫu nhiên."""
    rng = np.random.default_rng(seed)
    flip = rng.choice([-1.0, 1.0], size=len(trades))
    v = trades["gross_bps"].to_numpy() * flip - trades["cost_bps"].to_numpy()
    s = pd.Series(v)
    return float(s.mean()) / float(s.std(ddof=1)) * np.sqrt(len(s)) if s.std(ddof=1) > 0 else np.nan


def t_of_mean(trades: pd.DataFrame) -> float:
    """t của lợi nhuận trung bình mỗi lệnh — thước đo trực tiếp nhất cho theo-lệnh."""
    v = trades["net_bps"]
    sd = float(v.std(ddof=1))
    return float(v.mean()) / sd * np.sqrt(len(v)) if sd > 0 else np.nan


def block_bootstrap(d: pd.Series, block: int = 21, n_iter: int = 2000, seed: int = 7):
    rng = np.random.default_rng(seed)
    v = d.to_numpy()
    n = len(v)
    nb = max(n // block, 1)
    out = np.empty(n_iter)
    for k in range(n_iter):
        st = rng.integers(0, max(n - block, 1), size=nb)
        samp = np.concatenate([v[s:s + block] for s in st])
        sd = samp.std(ddof=1)
        out[k] = samp.mean() / sd * np.sqrt(252) if sd > 0 else 0.0
    return {"mean": float(out.mean()), "ci_lo": float(np.percentile(out, 2.5)),
            "ci_hi": float(np.percentile(out, 97.5)),
            "p_neg": float((out < 0).mean())}


def main() -> None:
    t0 = time.time()
    cache = {tf: {i.name: i for i in load_crosses(tf)} for tf in ("H1", "M30", "H4")}
    series: Dict[str, pd.Series] = {}
    verdicts: List[Dict] = []

    for tf, name, N, k, exit_name, ts_mult in CANDIDATES:
        ins = cache[tf][name]
        cfg = ExitCfg(exit_name, None, None, None, ts_mult)
        el, es, w = sig_zband(ins.df, n=N, k=k)
        res = run_trades(ins, el, es, w, cfg)
        T, d = res.trades, res.pnl_daily
        label = f"{tf}·{name}·N{N}·k{k}"
        series[label] = d

        print()
        print("█" * 116)
        print(f"█ {label} · {exit_name}")
        print("█" * 116)
        s_all, s_f, s_o = sharpe(d), sharpe(d, hi=FORM_END), sharpe(d, lo=FORM_END)
        cum = d.cumsum()
        yrs = max((d.index.max() - d.index.min()).days / 365.25, 1e-9)
        tm = t_of_mean(T)
        print(f"  Sharpe ALL {s_all:+.3f} · FORM {s_f:+.3f} · OOS {s_o:+.3f}")
        print(f"  {len(T)} lệnh · thắng {float((T['net_bps'] > 0).mean()) * 100:.1f}% · "
              f"net {float(T['net_bps'].mean()):+.2f} bps/lệnh (t = {tm:+.2f}) · "
              f"giữ {float(T['bars'].mean()):.0f} nến")
        print(f"  {float(cum.iloc[-1]) / 100 / yrs:+.2f}%/năm · MaxDD "
              f"{float((cum.cummax() - cum).max()) / 100:.2f}%")

        # 1. control thời điểm
        ct = np.array([control_timing(T, ins, s) for s in range(300)])
        ct = ct[np.isfinite(ct)]
        p_t = float((ct < tm).mean())
        d1 = p_t >= 0.95
        print(f"\n  1. CONTROL THỜI ĐIỂM (300 lần) — t thật {tm:+.2f} vs "
              f"p50 {np.median(ct):+.2f} [p95 {np.percentile(ct, 95):+.2f}]")
        print(f"     phân vị {p_t:.1%} · p = {1 - p_t:.4f}  "
              f"{'ĐẠT' if d1 else 'KHÔNG ĐẠT'}")

        # 2. control chiều
        cs = np.array([control_side(T, s) for s in range(300)])
        cs = cs[np.isfinite(cs)]
        p_s = float((cs < tm).mean())
        d2 = p_s >= 0.95
        print(f"\n  2. CONTROL CHIỀU (300 lần) — t thật {tm:+.2f} vs "
              f"p50 {np.median(cs):+.2f} [p95 {np.percentile(cs, 95):+.2f}]")
        print(f"     phân vị {p_s:.1%} · p = {1 - p_s:.4f}  "
              f"{'ĐẠT' if d2 else 'KHÔNG ĐẠT'}")

        # 3. bootstrap
        bs = block_bootstrap(d)
        d3 = bs["p_neg"] < 0.10
        print(f"\n  3. BOOTSTRAP KHỐI: {bs['mean']:+.3f} CI95 "
              f"[{bs['ci_lo']:+.3f} · {bs['ci_hi']:+.3f}] P(<0) {bs['p_neg']:.1%}  "
              f"{'ĐẠT' if d3 else 'KHÔNG ĐẠT'}")

        # 4. ổn định năm
        yr = d.groupby(d.index.year).sum() / 100.0
        d4 = int((yr > 0).sum()) >= len(yr) - 1
        print(f"\n  4. ỔN ĐỊNH NĂM {int((yr > 0).sum())}/{len(yr)}  "
              f"{'ĐẠT' if d4 else 'KHÔNG ĐẠT'}")
        print("     " + "  ".join(f"{int(y)}:{v:+.2f}%" for y, v in yr.items()))

        # 5. loại ngoại lai
        mo = d.resample("MS").sum()
        rest = float((mo.sum() - mo.nlargest(5).sum()) / 100.0)
        d5 = rest > 0
        print(f"\n  5. LOẠI NGOẠI LAI — bỏ 5 tháng tốt nhất còn {rest:+.2f}%  "
              f"{'ĐẠT' if d5 else 'KHÔNG ĐẠT'}")

        # 6. stress chi phí
        base = ins.cost_1rt_bps
        line = []
        for m in (2, 3, 5):
            ins.cost_1rt_bps = base * m
            r2 = run_trades(ins, el, es, w, cfg)
            line.append(f"×{m} {sharpe(r2.pnl_daily):+.3f}")
        ins.cost_1rt_bps = base
        print(f"\n  6. STRESS CHI PHÍ: " + "  ·  ".join(line))

        verdicts.append({"ứng viên": label, "ALL": round(s_all, 3),
                         "FORM": round(s_f, 3), "OOS": round(s_o, 3),
                         "n_lệnh": len(T), "t(net)": round(tm, 2),
                         "p_thời_điểm": round(1 - p_t, 4),
                         "p_chiều": round(1 - p_s, 4),
                         "boot_p<0": bs["p_neg"], "năm": f"{int((yr > 0).sum())}/{len(yr)}",
                         "bỏ_top5": round(rest, 2),
                         "ĐẠT": d1 and d2 and d3 and d4 and d5})

    print()
    print("█" * 116)
    print("█ ĐỘC LẬP giữa các ứng viên và với năm chân đang chạy")
    print("█" * 116)
    from src.python.strategies.h1 import cross_mean_reversion as CMR
    from src.python.strategies.h4 import cross_xs_reversion as XXS
    from src.python.strategies.d1 import (currency_reversal as CR,
                                          currency_carry as CY, cross_momentum as CM)

    def day(s):
        s = s.copy()
        s.index = pd.DatetimeIndex(s.index).as_unit("ns").normalize()
        return s.groupby(s.index).sum()

    allser = {**{k: day(v) for k, v in series.items()},
              "CrossMeanRev_H1": day(CMR.daily_pnl(CMR.backtest())),
              "CrossXsRev_H4": day(XXS.daily_pnl()),
              "CurrRev_D1": day(CR.backtest().net),
              "CurrCarry_D1": day(CY.backtest().net),
              "CrossMom_D1": day(CM.daily_pnl())}
    C = pd.DataFrame(allser).fillna(0.0).corr()
    print(C.round(3).to_string())

    V = pd.DataFrame(verdicts)
    print()
    print("=" * 116)
    print("TỔNG KẾT")
    print("=" * 116)
    print(V.to_string(index=False))
    pd.DataFrame(allser).to_csv(OUT / "mr_validate_pnl.csv")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
