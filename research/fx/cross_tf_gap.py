"""Vòng 50 — LẤP KHOẢNG TRỐNG KHUNG: họ cross ở M30 / H4 / D1 có phải chiến lược RIÊNG?

CÂU HỎI DUY NHẤT CỦA VÒNG NÀY
=============================
Danh mục hiện có 4 chân: 1 ở H1, 3 ở D1. Mục tiêu người dùng là M30 ≥ 3, H1 ≥ 4,
H4 ≥ 2, D1 ≥ 2. Câu hỏi thẳng: chạy CÙNG họ tín hiệu ở khung khác thì có ra chiến
lược MỚI, hay chỉ ra cùng một chiến lược với tần suất khác?

Đây không phải câu hỏi tu từ. Nó có ngưỡng số học: **|corr| < 0,7**. Trên ngưỡng đó
thì hai chân chỉ là một cược ở hai kích cỡ — thêm vào danh mục không giảm rủi ro,
chỉ tăng phí. Vòng 30 đã đo 28/28 tổ hợp "một ý tưởng ở 4 khung" đều > 0,7, nhưng
lần đó đo trên họ Donchian; họ z-score chưa từng đo. Đo lại, không suy diễn.

HAI CÔNG THỨC ĐƯỢC ĐO — chúng KHÁC NHAU về cấu trúc, không chỉ khác tham số
===========================================================================
  A. `band` — máy trạng thái TỪNG cross: vào khi |z| > 2, ra khi z về 0.
     Đây là công thức của chân H1 đang LIVE. Số vị thế thay đổi theo thời gian.
  B. `xs_z`  — XẾP HẠNG CẮT NGANG 20 cross theo z: mua N cross âm nhất, bán N cross
     dương nhất, tái cân bằng định kỳ. Luôn có 2N vị thế, tổng phơi nhiễm ≈ 0.

Khác biệt cốt lõi: A cược "cross này lệch khỏi CHÍNH NÓ"; B cược "cross này lệch
nhiều hơn 19 cross khác". B khử được cú sốc chung toàn rổ mà A phải chịu. Nên hai
công thức có thể tương quan thấp DÙ dùng chung một đại lượng z.
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

pd.set_option("display.width", 240, "display.max_columns", 30, "display.max_rows", 200)
t0 = time.time()
DEV = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"

# nến/năm để quy đổi half-life và chu kỳ tái cân bằng sang từng khung
BARS_YEAR = {"M30": 252 * 48, "H1": 252 * 24, "H4": 252 * 6, "D1": 252}


def sig_xs_zscore(panel, *, window: int, n_leg: int = 5, rebalance: int = 1,
                  ) -> pd.DataFrame:
    """Xếp hạng cắt ngang theo z-score: mua N cross âm nhất, bán N cross dương nhất.

    z tính trên cửa sổ `window` nến KẾT THÚC ở nến trước — nhân quả. Chuẩn hoá mỗi
    chân về tổng tuyệt đối = 1 để tổng phơi nhiễm gộp không đổi theo thời gian.
    """
    lp = panel.logp
    mu = lp.rolling(window, min_periods=window // 2).mean()
    sd = lp.rolling(window, min_periods=window // 2).std(ddof=1)
    z = ((lp - mu) / sd.replace(0, np.nan)).shift(1)

    Zv = z.to_numpy()
    n, m = Zv.shape
    pos = np.zeros((n, m))
    cur = np.zeros(m)
    for i in range(window, n):
        if i % rebalance == 0:
            row = Zv[i]
            ok = np.isfinite(row)
            if ok.sum() >= 2 * n_leg:
                cur = np.zeros(m)
                idx = np.where(ok)[0]
                order = idx[np.argsort(row[idx])]
                lo, hi = order[:n_leg], order[-n_leg:]
                cur[lo] = +1.0 / n_leg          # z thấp nhất → mua (kỳ vọng hồi lên)
                cur[hi] = -1.0 / n_leg
        pos[i] = cur
    return pd.DataFrame(pos, index=lp.index, columns=lp.columns)


def sh(s, lo=None, hi=None):
    if lo is not None:
        s = s[s.index >= lo]
    if hi is not None:
        s = s[s.index < hi]
    sd = float(s.std(ddof=1))
    return float(s.mean()) / sd * np.sqrt(252) if sd > 0 and len(s) > 60 else np.nan


def main():
    rows = []
    series = {}
    for tf in ("M30", "H1", "H4", "D1"):
        panel = LAB.build_panel(tf, start="2020-01-01")
        by = BARS_YEAR[tf]
        print(f"── {tf}: {len(panel.logp):,} nến × {len(panel.logp.columns)} cross"
              f"  ·  chi phí trung vị {float(panel.cost_1rt_bps.median()):.2f} bps",
              flush=True)

        # A. máy trạng thái từng cross — công thức của chân H1 đang LIVE
        for hl_mult in (4.32,):
            for ent in (2.0, 2.5):
                p = LAB.sig_zscore_band(panel, hl_mult=hl_mult, entry_sigma=ent,
                                        use_timestop=True)
                r = LAB.simulate_positions(panel, p, name=f"band_s{ent}")
                d = r.pnl_daily
                key = f"{tf}:band_s{ent}"
                series[key] = d
                rows.append({"tf": tf, "form": f"band_s{ent}",
                             "ALL": round(sh(d), 3), "FORM": round(sh(d, hi=DEV), 3),
                             "OOS": round(sh(d, lo=DEV), 3),
                             "gross": round(r.gross_bps_bar, 4),
                             "phi": round(r.trade_cost_bps_bar
                                          + r.carry_cost_bps_bar, 4),
                             "turn/nam": round(r.turnover_per_year, 1),
                             "%tt": round(r.time_in_market, 3)})

        # B. xếp hạng cắt ngang theo z — cửa sổ ~5 ngày và ~20 ngày giao dịch
        for days, nl in ((5, 5), (20, 5)):
            w = max(int(round(by / 252 * days)), 10)
            reb = max(int(round(by / 252 * max(days // 4, 1))), 1)
            p = sig_xs_zscore(panel, window=w, n_leg=nl, rebalance=reb)
            r = LAB.simulate_positions(panel, p, name=f"xs_z{days}d")
            d = r.pnl_daily
            key = f"{tf}:xs_z{days}d"
            series[key] = d
            rows.append({"tf": tf, "form": f"xs_z{days}d",
                         "ALL": round(sh(d), 3), "FORM": round(sh(d, hi=DEV), 3),
                         "OOS": round(sh(d, lo=DEV), 3),
                         "gross": round(r.gross_bps_bar, 4),
                         "phi": round(r.trade_cost_bps_bar + r.carry_cost_bps_bar, 4),
                         "turn/nam": round(r.turnover_per_year, 1),
                         "%tt": round(r.time_in_market, 3)})

    T = pd.DataFrame(rows)
    T.to_csv(OUT / "cross_tf_gap.csv", index=False)
    print()
    print("=" * 130)
    print("KẾT QUẢ — 4 khung × 4 công thức")
    print("=" * 130)
    print(T.sort_values("ALL", ascending=False).to_string(index=False))

    print()
    print("=" * 130)
    print("CỔNG: FORM>0 & OOS>0 & ALL>0,5")
    print("=" * 130)
    k = T[(T["FORM"] > 0) & (T["OOS"] > 0) & (T["ALL"] > 0.5)]
    print(k.to_string(index=False) if len(k) else "  KHÔNG CÓ")

    print()
    print("=" * 130)
    print("TƯƠNG QUAN P&L NGÀY — ngưỡng độc lập |corr| < 0,7")
    print("=" * 130)
    keep = [k_ for k_ in series if T.set_index(
        ["tf", "form"]).loc[tuple(k_.split(":")), "ALL"] > 0.2]
    if len(keep) >= 2:
        C = pd.DataFrame({k_: series[k_] for k_ in keep}).fillna(0.0).corr()
        print(C.round(3).to_string())
        print()
        pairs = [(a, b, C.loc[a, b]) for i, a in enumerate(keep)
                 for b in keep[i + 1:]]
        indep = [(a, b, v) for a, b, v in pairs if abs(v) < 0.7]
        print(f"{len(indep)}/{len(pairs)} tổ hợp có |corr| < 0,7:")
        for a, b, v in sorted(indep, key=lambda x: abs(x[2]))[:20]:
            print(f"    {a:22s} ↔ {b:22s}  {v:+.3f}")
    else:
        print("  Không đủ chân ALL>0,2 để đo tương quan")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
