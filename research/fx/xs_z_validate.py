"""Vòng 52 — KIỂM ĐỊNH ĐẦY ĐỦ hai ứng viên `xs_z` (H4 và M30) trước khi nhận vào danh mục.

HAI ỨNG VIÊN TỪ VÒNG 51
=======================
    H4 : cửa sổ 5 ngày  · 7 cross/chân · tái cân bằng 2 ngày → ALL 0,460 FORM 0,505 OOS 0,381
    M30: cửa sổ 10 ngày · 7 cross/chân · tái cân bằng 2 ngày → ALL 0,410 FORM 0,410 OOS 0,417

Điểm đáng tin nhất KHÔNG phải con số Sharpe, mà là: cùng một vùng tham số
(n_leg = 7, tái cân bằng = 2 ngày) tốt trên CẢ HAI khung. Vùng tham số tái lập được
qua khung là bằng chứng cấu trúc; một ô đẹp trên một khung thì không.

SÁU KIỂM ĐỊNH — theo `docs/knowledge/research_process.md` và bộ stress test của dự án
=====================================================================================
    1. CONTROL NGẪU NHIÊN   giữ nguyên số vị thế và tần suất, CHỌN CROSS NGẪU NHIÊN.
                            Nếu Sharpe thật không nằm trên phân vị 95 của control thì
                            edge không phân biệt được với "cứ giao dịch cái gì đó".
    2. BOOTSTRAP KHỐI       khối 21 ngày, 2000 lần → CI95 và P(Sharpe < 0)
    3. ỔN ĐỊNH NĂM          bao nhiêu năm dương — 7 năm mẫu
    4. LOẠI NGOẠI LAI       bỏ 5 tháng tốt nhất, có GIỮ DẤU không
    5. STRESS CHI PHÍ       ×2 ×5 ×10 chi phí, và biên swap broker 0-3%/năm
    6. ĐỘC LẬP              tương quan với CẢ BỐN chân đang chạy, và với nhau
"""
import sys
import io
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd

from src.python.research import fx_cross_lab as LAB
from research.fx.xs_z_grid import sig_xs_zscore, sh

pd.set_option("display.width", 240, "display.max_columns", 30)
t0 = time.time()
DEV = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"
BARS_DAY = {"M30": 48, "H1": 24, "H4": 6}

CAND = {"H4": dict(win_d=5, n_leg=7, reb_d=2),
        "M30": dict(win_d=10, n_leg=7, reb_d=2)}


def sig_random(panel, *, n_leg: int, rebalance: int, seed: int) -> pd.DataFrame:
    """Control: CÙNG số vị thế, CÙNG tần suất, nhưng chọn cross NGẪU NHIÊN.

    Đây là control đúng cho chiến lược xếp hạng — nó giữ nguyên mọi thứ trừ THÔNG TIN.
    Control kiểu "xáo trộn giá" sẽ phá luôn cấu trúc chi phí, không so được.
    """
    rng = np.random.default_rng(seed)
    lp = panel.logp
    n, m = lp.shape
    pos = np.zeros((n, m))
    cur = np.zeros(m)
    for i in range(rebalance, n):
        if i % rebalance == 0:
            cur = np.zeros(m)
            pick = rng.permutation(m)
            cur[pick[:n_leg]] = +1.0 / n_leg
            cur[pick[n_leg:2 * n_leg]] = -1.0 / n_leg
        pos[i] = cur
    return pd.DataFrame(pos, index=lp.index, columns=lp.columns)


def block_bootstrap(d: pd.Series, block: int = 21, n_iter: int = 2000,
                    seed: int = 7) -> dict:
    """Bootstrap khối — giữ tự tương quan trong khối, xáo trộn thứ tự khối."""
    rng = np.random.default_rng(seed)
    v = d.to_numpy()
    n = len(v)
    nb = max(n // block, 1)
    out = np.empty(n_iter)
    for k in range(n_iter):
        starts = rng.integers(0, max(n - block, 1), size=nb)
        samp = np.concatenate([v[s:s + block] for s in starts])
        sd = samp.std(ddof=1)
        out[k] = samp.mean() / sd * np.sqrt(252) if sd > 0 else 0.0
    return {"mean": float(out.mean()),
            "ci_lo": float(np.percentile(out, 2.5)),
            "ci_hi": float(np.percentile(out, 97.5)),
            "p_neg": float((out < 0).mean())}


def main():
    # ── chân đang chạy, để đo độc lập
    from src.python.strategies.h1 import cross_mean_reversion as CMR
    from src.python.strategies.d1 import (currency_reversal as CR,
                                          currency_carry as CY,
                                          cross_momentum as CM)
    live = {"CrossMeanRev_H1": CMR.daily_pnl(CMR.backtest()),
            "CurrencyReversal_D1": CR.backtest().net,
            "CurrencyCarry_D1": CY.backtest().net,
            "CrossMomentum_D1": CM.daily_pnl()}

    cand_series = {}
    for tf, cfg in CAND.items():
        bd = BARS_DAY[tf]
        w = int(round(cfg["win_d"] * bd))
        rb = max(int(round(cfg["reb_d"] * bd)), 1)
        panel = LAB.build_panel(tf, start="2020-01-01")

        print()
        print("█" * 120)
        print(f"█ ỨNG VIÊN {tf}  ·  cửa sổ {cfg['win_d']}d ({w} nến)  ·  "
              f"{cfg['n_leg']} cross/chân  ·  tái cân bằng {cfg['reb_d']}d ({rb} nến)")
        print("█" * 120)

        p = sig_xs_zscore(panel, window=w, n_leg=cfg["n_leg"], rebalance=rb)
        r = LAB.simulate_positions(panel, p, name=f"xs_z_{tf}")
        d = r.pnl_daily
        cand_series[f"XsZ_{tf}"] = d
        s_all, s_form, s_oos = sh(d), sh(d, hi=DEV), sh(d, lo=DEV)
        yrs = max((d.index.max() - d.index.min()).days / 365.25, 1e-9)
        cum = d.cumsum()
        dd = float((cum.cummax() - cum).max())
        print(f"  Sharpe   ALL {s_all:+.3f}  ·  FORM {s_form:+.3f}  ·  OOS {s_oos:+.3f}")
        print(f"  Lợi nhuận {float(cum.iloc[-1]) / 100 / yrs:+.2f} %/năm  ·  "
              f"MaxDD {dd / 100:.2f}%  ·  vòng quay {r.turnover_per_year:.1f}/năm")
        print(f"  gross {r.gross_bps_bar:.4f} bps/nến  ·  "
              f"chi phí {r.trade_cost_bps_bar + r.carry_cost_bps_bar:.4f}  "
              f"({(r.trade_cost_bps_bar + r.carry_cost_bps_bar) / r.gross_bps_bar * 100:.0f}% gross)")

        # ── 1. control ngẫu nhiên
        ctrl = []
        for sd_ in range(300):
            pc = sig_random(panel, n_leg=cfg["n_leg"], rebalance=rb, seed=sd_)
            ctrl.append(sh(LAB.simulate_positions(panel, pc).pnl_daily))
        ctrl = np.array([c for c in ctrl if np.isfinite(c)])
        pct = float((ctrl < s_all).mean())
        print(f"\n  1. CONTROL NGẪU NHIÊN (300 lần, cùng số vị thế & tần suất)")
        print(f"     thật {s_all:+.3f}  vs  control p50 {np.median(ctrl):+.3f} "
              f"[p5 {np.percentile(ctrl, 5):+.3f} · p95 {np.percentile(ctrl, 95):+.3f}]")
        print(f"     phân vị {pct:.1%}  ·  p = {1 - pct:.4f}  "
              f"{'ĐẠT' if pct >= 0.95 else 'KHÔNG ĐẠT'}")

        # ── 2. bootstrap khối
        bs = block_bootstrap(d)
        print(f"\n  2. BOOTSTRAP KHỐI 21 ngày (2000 lần)")
        print(f"     Sharpe {bs['mean']:+.3f}  CI95 [{bs['ci_lo']:+.3f} · "
              f"{bs['ci_hi']:+.3f}]  P(<0) = {bs['p_neg']:.1%}  "
              f"{'ĐẠT' if bs['p_neg'] < 0.10 else 'KHÔNG ĐẠT'}")

        # ── 3. ổn định năm
        yr = d.groupby(d.index.year).sum() / 100.0
        print(f"\n  3. ỔN ĐỊNH NĂM ({int((yr > 0).sum())}/{len(yr)} năm dương)")
        print("     " + "  ".join(f"{int(y)}: {v:+.2f}%" for y, v in yr.items()))

        # ── 4. loại ngoại lai
        mo = d.resample("MS").sum()
        top5 = mo.nlargest(5)
        share = float(top5.sum() / mo.sum()) if mo.sum() != 0 else np.nan
        rest = float((mo.sum() - top5.sum()) / 100.0)
        print(f"\n  4. LOẠI NGOẠI LAI — 5 tháng tốt nhất = {share:.1%} lợi nhuận")
        print(f"     bỏ đi còn {rest:+.2f}%  "
              f"{'GIỮ DẤU — ĐẠT' if rest > 0 else 'ĐỔI DẤU — KHÔNG ĐẠT'}")

        # ── 5. stress chi phí
        print(f"\n  5. STRESS CHI PHÍ")
        base_cost = panel.cost_1rt_bps.copy()
        for mult in (1, 2, 5, 10):
            panel.cost_1rt_bps = base_cost * mult
            rr = LAB.simulate_positions(panel, p)
            print(f"     ×{mult:<3d} chi phí  Sharpe {sh(rr.pnl_daily):+.3f}")
        panel.cost_1rt_bps = base_cost
        for mk in (0.0, 1.0, 2.0, 3.0):
            pn = LAB.build_panel(tf, start="2020-01-01", broker_markup_pct=mk)
            pp = sig_xs_zscore(pn, window=w, n_leg=cfg["n_leg"], rebalance=rb)
            print(f"     biên swap {mk:.1f}%/năm  Sharpe "
                  f"{sh(LAB.simulate_positions(pn, pp).pnl_daily):+.3f}")

    # ── 6. độc lập
    print()
    print("█" * 120)
    print("█ 6. ĐỘC LẬP — tương quan P&L ngày (ngưỡng |corr| < 0,7)")
    print("█" * 120)
    # chuẩn hoá index về ngày — bốn chân đang chạy có index ở đơn vị khác nhau
    # (chân H1 lấy từ `entry_time`), ghép thẳng sẽ tràn dtype datetime
    def _daily(s: pd.Series) -> pd.Series:
        s = s.copy()
        # phải ép về đơn vị ns: bốn chân trả index datetime64[ms], ghép với [ns]
        # làm pandas đổi đơn vị và tràn biên
        s.index = pd.DatetimeIndex(s.index).as_unit("ns").normalize()
        s = s[s.index.notna()]
        s = s[(s.index >= "2020-01-01") & (s.index <= "2027-01-01")]
        return s.groupby(s.index).sum()

    allser = {k: _daily(v) for k, v in {**cand_series, **live}.items()}
    C = pd.DataFrame(allser).fillna(0.0).corr()
    print(C.round(3).to_string())
    print()
    bad = [(a, b, C.loc[a, b]) for a in cand_series for b in allser
           if a != b and abs(C.loc[a, b]) >= 0.7]
    if bad:
        for a, b, v in bad:
            print(f"  TRÙNG: {a} ↔ {b} = {v:+.3f}")
    else:
        print("  Cả hai ứng viên ĐỘC LẬP với toàn bộ chân đang chạy "
              f"(|corr| tối đa "
              f"{max(abs(C.loc[a, b]) for a in cand_series for b in allser if a != b):.3f})")
    pd.DataFrame(allser).to_csv(OUT / "xs_z_validate_pnl.csv")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
