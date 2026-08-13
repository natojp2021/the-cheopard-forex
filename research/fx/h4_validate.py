"""Vòng 62 — KIỂM ĐỊNH ứng viên H4, chạy bằng ĐÚNG động cơ sản xuất `zband_core`.

VÌ SAO PHẢI CHẠY BẰNG ĐỘNG CƠ SẢN XUẤT, KHÔNG PHẢI LAB
=======================================================
Vòng 61 vừa cho một bài học tốn công: `trade_lab.run_trades` KHÔNG có nhánh thoát khi
z về 0, còn `zband_core.run` thì có. Cùng một bộ tham số cho hai kết quả khác hẳn —
GBPCAD H4 ra Sharpe 0,815 ở lab và 0,557 ở động cơ thật.

Tôi đã suýt cứu con số đó bằng cách thêm tham số `exit_at_mean=False`. Kiểm tra trên
CẢ BẢY chân cho thấy nó chỉ tốt hơn ở **1/7** — tức tham số đó chỉ đúng đúng ô mà tôi
cần nó đúng. Đó là chữ ký overfit, và GBPCAD H4 đã bị loại.

Bài học thành quy tắc: **kiểm định phải chạy trên cùng đường code với sản xuất.** Lab
dùng để quét rộng; kết luận chỉ được lấy từ động cơ thật.

BA ỨNG VIÊN — quét lại bằng `zband_core` ở vòng 61
==================================================
    GBPNZD  N=12  k=1,5  ts=1,0   ALL 1,214 · FORM 1,398 · OOS 0,879 · 7/7 năm
    AUDCAD  N=24  k=2,0  ts=2,0   ALL 1,062 · FORM 1,067 · OOS 1,059 · 7/7 năm
    GBPAUD  N=24  k=1,5  ts=3,0   ALL 0,904 · FORM 1,085 · OOS 0,563 · 7/7 năm

GBPNZD từng bị loại ở M30 (FORM 1,551 vs OOS 0,238 — chênh 6,5 lần). Ở H4 chênh lệch
là 1,6 lần, khác hẳn về mức độ. Vẫn phải qua đủ kiểm định như mọi ứng viên khác.

⚠️ AUDCAD và GBPAUD đã có chân ở khung khác. Nếu chúng qua kiểm định thì phải vào
ĐÚNG nhóm rủi ro đang có, không được tính là nhóm mới — nếu không thì danh mục âm
thầm tăng gấp rưỡi phơi nhiễm vào một công cụ.
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

from research.fx.mr_validate import block_bootstrap, control_side, control_timing
from research.fx.trade_lab import load_crosses
from src.python.strategies import zband_core as ZB

pd.set_option("display.width", 240, "display.max_columns", 30)
FORM_END = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"

# (công cụ, N, k, hệ số time-stop)
CANDIDATES: Tuple[Tuple[str, int, float, float], ...] = (
    ("GBPNZD", 12, 1.5, 1.0),
    ("AUDCAD", 24, 2.0, 2.0),
    ("GBPAUD", 24, 1.5, 3.0),
)


def sharpe(s: pd.Series, lo=None, hi=None) -> float:
    if lo is not None:
        s = s[s.index >= lo]
    if hi is not None:
        s = s[s.index < hi]
    sd = float(s.std(ddof=1))
    return float(s.mean()) / sd * np.sqrt(252) if sd > 0 and len(s) > 60 else np.nan


def main() -> None:
    t0 = time.time()
    univ = {i.name: i for i in load_crosses("H4")}
    series: Dict[str, pd.Series] = {}
    verdicts: List[Dict] = []

    for name, N, k, ts in CANDIDATES:
        ins = univ[name]
        cfg = ZB.ZBandConfig(f"ZBand{name}H4", name, "H4", N, k, ts)
        res = ZB.run(ins.df, ins.cost_1rt_bps, ins.swap_bps_per_bar, cfg)
        T, d = res.trades, res.pnl_daily
        label = f"H4·{name}·N{N}·k{k}·ts{ts}"
        series[label] = d

        v = T["net_bps"]
        tm = float(v.mean()) / float(v.std(ddof=1)) * np.sqrt(len(v))
        s_all, s_f, s_o = sharpe(d), sharpe(d, hi=FORM_END), sharpe(d, lo=FORM_END)
        cum = d.cumsum()
        yrs = max((d.index.max() - d.index.min()).days / 365.25, 1e-9)

        print()
        print("█" * 114)
        print(f"█ {label}")
        print("█" * 114)
        print(f"  Sharpe ALL {s_all:+.3f} · FORM {s_f:+.3f} · OOS {s_o:+.3f}")
        print(f"  {len(T)} lệnh · thắng {float((v > 0).mean()) * 100:.1f}% · "
              f"net {float(v.mean()):+.2f} bps/lệnh (t = {tm:+.2f}) · "
              f"giữ {float(T['bars'].mean()):.0f} nến")
        print(f"  {float(cum.iloc[-1]) / 100 / yrs:+.2f}%/năm · MaxDD "
              f"{float((cum.cummax() - cum).max()) / 100:.2f}% · "
              f"thoát: {T['reason'].value_counts().to_dict()}")

        ct = np.array([control_timing(T, ins, s) for s in range(300)])
        ct = ct[np.isfinite(ct)]
        p_t = float((ct < tm).mean())
        d1 = p_t >= 0.95
        print(f"\n  1. CONTROL THỜI ĐIỂM  t {tm:+.2f} vs p50 {np.median(ct):+.2f} "
              f"[p95 {np.percentile(ct, 95):+.2f}] · p = {1 - p_t:.4f}  "
              f"{'ĐẠT' if d1 else 'KHÔNG ĐẠT'}")

        cs = np.array([control_side(T, s) for s in range(300)])
        cs = cs[np.isfinite(cs)]
        p_s = float((cs < tm).mean())
        d2 = p_s >= 0.95
        print(f"  2. CONTROL CHIỀU      t {tm:+.2f} vs p50 {np.median(cs):+.2f} "
              f"[p95 {np.percentile(cs, 95):+.2f}] · p = {1 - p_s:.4f}  "
              f"{'ĐẠT' if d2 else 'KHÔNG ĐẠT'}")

        bs = block_bootstrap(d)
        d3 = bs["p_neg"] < 0.10
        print(f"  3. BOOTSTRAP KHỐI     {bs['mean']:+.3f} CI95 [{bs['ci_lo']:+.3f} · "
              f"{bs['ci_hi']:+.3f}] P(<0) {bs['p_neg']:.1%}  "
              f"{'ĐẠT' if d3 else 'KHÔNG ĐẠT'}")

        yr = d.groupby(d.index.year).sum() / 100.0
        d4 = int((yr > 0).sum()) >= len(yr) - 1
        print(f"  4. ỔN ĐỊNH NĂM        {int((yr > 0).sum())}/{len(yr)}  "
              f"{'ĐẠT' if d4 else 'KHÔNG ĐẠT'}")
        print("     " + "  ".join(f"{int(y)}:{x:+.2f}%" for y, x in yr.items()))

        mo = d.resample("MS").sum()
        rest = float((mo.sum() - mo.nlargest(5).sum()) / 100.0)
        d5 = rest > 0
        print(f"  5. LOẠI NGOẠI LAI     bỏ 5 tháng tốt nhất còn {rest:+.2f}%  "
              f"{'ĐẠT' if d5 else 'KHÔNG ĐẠT'}")

        base = ins.cost_1rt_bps
        line = []
        for m in (2, 3, 5):
            ins.cost_1rt_bps = base * m
            line.append(f"×{m} {sharpe(ZB.run(ins.df, ins.cost_1rt_bps, ins.swap_bps_per_bar, cfg).pnl_daily):+.3f}")
        ins.cost_1rt_bps = base
        print(f"  6. STRESS CHI PHÍ     " + "  ·  ".join(line))

        # 7. VÙNG THAM SỐ — ô lân cận phải cùng dấu
        neigh = []
        for dn in (max(N // 2, 6), N, N * 2):
            for dk in (k - 0.5, k, k + 0.5):
                if dk <= 0:
                    continue
                c2 = ZB.ZBandConfig("x", name, "H4", dn, dk, ts)
                r2 = ZB.run(ins.df, ins.cost_1rt_bps, ins.swap_bps_per_bar, c2)
                if not r2.trades.empty and len(r2.trades) >= 30:
                    neigh.append(sharpe(r2.pnl_daily))
        n_pos = sum(1 for x in neigh if np.isfinite(x) and x > 0)
        d7 = n_pos >= len(neigh) - 1
        print(f"  7. VÙNG THAM SỐ       {n_pos}/{len(neigh)} ô lân cận dương  "
              f"{'ĐẠT' if d7 else 'KHÔNG ĐẠT — đỉnh cô lập'}")

        verdicts.append({"ứng viên": label, "ALL": round(s_all, 3),
                         "FORM": round(s_f, 3), "OOS": round(s_o, 3),
                         "n": len(T), "t": round(tm, 2),
                         "p_thời_điểm": round(1 - p_t, 4), "p_chiều": round(1 - p_s, 4),
                         "boot": bs["p_neg"], "năm": f"{int((yr > 0).sum())}/{len(yr)}",
                         "bỏ_top5": round(rest, 2), "vùng": f"{n_pos}/{len(neigh)}",
                         "ĐẠT": d1 and d2 and d3 and d4 and d5 and d7})

    # độc lập với mọi chân đang chạy
    print()
    print("█" * 114)
    print("█ ĐỘC LẬP — tương quan với 11 chân đang chạy")
    print("█" * 114)
    from src.python.strategies import portfolio as PF

    def day(s):
        s = s.copy()
        s.index = pd.DatetimeIndex(s.index).as_unit("ns").normalize()
        return s.groupby(s.index).sum()

    res_pf = PF.backtest()
    allser = {**{k: day(v) for k, v in series.items()},
              **{k: day(v) for k, v in res_pf.legs.items()}}
    C = pd.DataFrame(allser).fillna(0.0).corr()
    for a in series:
        top = sorted(((abs(float(C.loc[a, b])), b) for b in allser if b != a),
                     reverse=True)[:3]
        print(f"  {a:28s} " + " · ".join(f"{b} {v:.3f}" for v, b in top))

    V = pd.DataFrame(verdicts)
    print()
    print("=" * 114)
    print("TỔNG KẾT")
    print("=" * 114)
    print(V.to_string(index=False))
    pd.DataFrame(allser).to_csv(OUT / "h4_validate_pnl.csv")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
