"""Vòng 72 — TRAILING STOP và BREAK-EVEN có chỗ đứng trong danh mục này không?

CÂU HỎI
=======
Pipeline chuẩn của hệ XAUUSD có quản lý lệnh sau khi mở: dời dừng lỗ về hoà vốn tại
+3R, và trước 23/07 còn có trailing theo ATR. Hệ Forex hiện KHÔNG có gì — mở lệnh
xong là chờ tín hiệu ngược hoặc time-stop.

Câu hỏi không phải "hệ cũ có nên ta cũng phải có". Câu hỏi là: **trên chính danh mục
này, dời stop theo giá có làm tốt hơn không?**

HAI ĐIỀU PHẢI BIẾT TRƯỚC KHI ĐỌC KẾT QUẢ
=========================================
1. Chính hệ XAUUSD đã **LOẠI BỎ trailing** ngày 23/07 sau khi đo — nó chỉ còn
   break-even. Nên "sao chép hệ cũ" ở đây nghĩa là sao chép cả quyết định loại bỏ,
   không phải sao chép một nhánh code đã chết.
2. Dừng lỗ theo giá đã được đo trên chính 22 chân này (`research/fx/sl_test.py`) và
   kết quả dứt khoát: MỌI mức đều tệ hơn, và ở 1×ATR nó còn làm MaxDD TỆ ĐI
   (4,00σ → 5,03σ). Trailing là một dạng dừng lỗ di động, nên giả thuyết mặc định
   phải là nó cũng gây hại — vòng này đo để xác nhận hoặc bác bỏ.

CÁCH ĐO
=======
Với mỗi lệnh, quét lại chuỗi giá TRONG lệnh và mô phỏng:

    TRAILING   stop bám theo giá tốt nhất đã đạt, cách `k × ATR`. Chạm thì ra.
    BREAK-EVEN khi lãi chưa thực hiện đạt `m × ATR`, dời stop về giá vào. Chạm thì ra.

Dùng `high`/`low` chứ không phải `close`: stop nằm trên server broker thì nó bị quét
bởi bóng nến, không đợi nến đóng. Thứ tự trong nến không biết được, nên khi cả hai
điều kiện cùng xảy ra trong một nến, mô phỏng lấy phía BẤT LỢI — kết luận "trailing
làm tệ hơn" vì vậy là cận trên của mức tệ, không phải cận dưới.
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd

from src.python.shared.indicators import atr as _atr
from src.python.strategies import portfolio as PF
from src.python.strategies import registry as REG

OUT = ROOT / "reports" / "fx_research"
TRAIL_MULTS = (1.0, 2.0, 3.0, 4.0, 6.0, 8.0)
BE_MULTS = (0.5, 1.0, 2.0, 3.0)
FORM_END = pd.Timestamp("2024-01-01")


def sharpe(d: pd.Series) -> float:
    if len(d) < 30:
        return float("nan")
    sd = float(d.std(ddof=1))
    return float(d.mean()) / sd * np.sqrt(252) if sd > 0 else float("nan")


def simulate_exit(df: pd.DataFrame, trades: pd.DataFrame, atr_bps: pd.Series,
                  *, trail_mult: Optional[float] = None,
                  be_mult: Optional[float] = None) -> pd.DataFrame:
    """Thay kết quả lệnh bằng kết quả sau khi áp trailing / break-even.

    Trả bảng lệnh đã sửa, thêm cột `stopped_by` để đếm cơ chế nào đã đóng lệnh.
    """
    hi = df["high"].to_numpy()
    lo = df["low"].to_numpy()
    idx = {t: i for i, t in enumerate(df.index)}

    out_net: List[float] = []
    out_by: List[str] = []
    for k, t in trades.iterrows():
        i, j = idx.get(t["entry_time"]), idx.get(t["exit_time"])
        entry = float(t.get("entry_px", 0.0) or 0.0)
        if i is None or j is None or j <= i or entry <= 0:
            out_net.append(float(t["net_bps"]))
            out_by.append("gốc")
            continue

        side = int(t["side"])
        a = float(atr_bps.iloc[i]) if i < len(atr_bps) else float(atr_bps.median())
        if not np.isfinite(a) or a <= 0:
            out_net.append(float(t["net_bps"]))
            out_by.append("gốc")
            continue

        best = 0.0                       # lãi chưa thực hiện tốt nhất, bps
        stop_bps: Optional[float] = None  # mức stop tính theo bps so với giá vào
        hit = None
        for b in range(i + 1, j + 1):
            fav = side * ((hi[b] if side > 0 else lo[b]) - entry) / entry * 1e4
            adv = side * ((lo[b] if side > 0 else hi[b]) - entry) / entry * 1e4
            best = max(best, fav)

            # BẤT LỢI TRƯỚC: trong một nến không biết thứ tự, lấy phía tệ hơn.
            if stop_bps is not None and adv <= stop_bps:
                hit = stop_bps
                break

            if be_mult is not None and best >= be_mult * a:
                stop_bps = max(stop_bps if stop_bps is not None else -1e18, 0.0)
            if trail_mult is not None and best > 0:
                cand = best - trail_mult * a
                stop_bps = cand if stop_bps is None else max(stop_bps, cand)

        if hit is None:
            out_net.append(float(t["net_bps"]))
            out_by.append("gốc")
        else:
            out_net.append(hit - float(t["cost_bps"]))
            out_by.append("trailing" if trail_mult is not None else "break-even")

    T = trades.copy()
    T["net_bps"] = out_net
    T["stopped_by"] = out_by
    return T


def daily(T: pd.DataFrame) -> pd.Series:
    s = pd.Series(T["net_bps"].to_numpy(),
                  index=pd.DatetimeIndex(T["exit_time"]).normalize())
    return s.groupby(s.index).sum()


def main() -> None:
    t0 = time.time()
    legs = sorted(PF.SINGLE_LEGS.values())
    print(f"Quét trailing + break-even trên {len(legs)} chân")
    print("=" * 110)

    per_leg: List[Dict] = []
    daily_by: Dict[str, List[pd.Series]] = {"không có": []}
    for m in TRAIL_MULTS:
        daily_by[f"trail {m:g}×ATR"] = []
    for m in BE_MULTS:
        daily_by[f"BE {m:g}×ATR"] = []

    for name in legs:
        mod = next(s for s in REG.STRATEGIES if s.name == name).load()
        ins = mod._load()
        res = mod.backtest()
        T = res.trades
        if T.empty or "entry_px" not in T.columns:
            continue
        bpd = {"M30": 48, "H1": 24, "H4": 6}.get(mod.TIMEFRAME, 24)
        atr_bps = _atr(ins.df, 14) / ins.df["close"] * 1e4 * np.sqrt(bpd)

        row = {"chân": name, "không có": round(sharpe(daily(T)), 3)}
        daily_by["không có"].append(daily(T))
        for m in TRAIL_MULTS:
            adj = simulate_exit(ins.df, T, atr_bps, trail_mult=m)
            row[f"trail {m:g}"] = round(sharpe(daily(adj)), 3)
            daily_by[f"trail {m:g}×ATR"].append(daily(adj))
        for m in BE_MULTS:
            adj = simulate_exit(ins.df, T, atr_bps, be_mult=m)
            row[f"BE {m:g}"] = round(sharpe(daily(adj)), 3)
            daily_by[f"BE {m:g}×ATR"].append(daily(adj))
        per_leg.append(row)
        print(f"   {name:22} xong")

    P = pd.DataFrame(per_leg)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    P.to_csv(OUT / "trailing_by_leg.csv", index=False)

    print()
    print("=" * 110)
    print("THEO CHÂN — Sharpe trung vị và số chân TỆ ĐI so với KHÔNG CÓ gì")
    print("=" * 110)
    base = P["không có"]
    rows = []
    for col in P.columns:
        if col == "chân":
            continue
        worse = int((P[col] < base).sum()) if col != "không có" else 0
        rows.append({"cơ chế": col, "Sharpe trung vị": round(float(P[col].median()), 3),
                     "chân TỆ ĐI": f"{worse}/{len(P)}"})
    print(pd.DataFrame(rows).to_string(index=False))

    print()
    print("=" * 110)
    print("DANH MỤC GỘP (chuẩn hoá σ FORM rồi chia đều)")
    print("=" * 110)
    rows = []
    for lab, series in daily_by.items():
        idx = None
        for s in series:
            idx = s.index if idx is None else idx.union(s.index)
        norm = []
        for s in series:
            s = s.reindex(idx).fillna(0.0)
            f = s[s.index < FORM_END]
            sd = float(f.std(ddof=1)) if len(f) > 30 else float(s.std(ddof=1))
            norm.append(s / sd if sd > 0 else s * 0.0)
        port = sum(norm) / len(norm)
        cum = port.cumsum()
        rows.append({"cơ chế": lab, "Sharpe": round(sharpe(port), 3),
                     "OOS": round(sharpe(port[port.index >= FORM_END]), 3),
                     "MaxDD (σ)": round(float((cum.cummax() - cum).max()), 2)})
    R = pd.DataFrame(rows)
    print(R.to_string(index=False))
    R.to_csv(OUT / "trailing_portfolio.csv", index=False)

    b = float(R[R["cơ chế"] == "không có"]["Sharpe"].iloc[0])
    best = R[R["cơ chế"] != "không có"].sort_values("Sharpe", ascending=False).iloc[0]
    print()
    print(f"KẾT LUẬN: không có gì → {b:.3f} · tốt nhất là {best['cơ chế']} "
          f"→ {best['Sharpe']:.3f} "
          f"({'TỐT HƠN' if best['Sharpe'] > b else 'VẪN TỆ HƠN'})")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
