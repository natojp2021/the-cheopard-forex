"""Vòng 71 — CÓ THẬT SỰ ĐƯỢC PHÉP THẢ TRÔI, KHÔNG ĐẶT DỪNG LỖ?

CÂU HỎI
=======
Toàn bộ 27 chân chạy KHÔNG có dừng lỗ theo giá. Lý do ghi trong repo dẫn về vòng 57
và 59, nhưng hai vòng đó đo trên MỘT chân và trên danh mục cũ. Danh mục nay 27 chân,
và "không có SL" là quyết định rủi ro lớn nhất của cả hệ — nó phải được đo lại trên
chính danh mục đang chạy, không được thừa hưởng bằng chứng cũ.

CÁCH ĐO — MAE, KHÔNG PHẢI CHẠY LẠI BACKTEST
============================================
Không cần viết lại engine. Với mỗi lệnh đã có (entry, exit, side, khoảng nến), quét
lại chuỗi giá TRONG lệnh để lấy **MAE** — mức lỗ sâu nhất chưa thực hiện:

    MAE = max trên các nến giữ của   side × (entry − giá) / entry

Nếu MAE >= khoảng cách SL thì lệnh đó ĐÃ BỊ dừng: thay kết quả thật bằng −SL (cộng
chi phí). Nếu không, giữ nguyên kết quả thật. Đây là mô phỏng CHÍNH XÁC cho SL dạng
"chạm là ra", chỉ bỏ qua trường hợp giá xuyên qua SL trong cùng một nến — mà bỏ qua
đó lệch về phía CÓ LỢI cho SL, nên kết luận "SL làm tệ hơn" càng chắc.

Dùng giá cao/thấp trong nến (`high`/`low`) chứ không phải giá đóng: SL nằm trên
server broker thì nó bị quét bởi bóng nến, không đợi nến đóng.

QUÉT
====
SL theo bội số ATR ngày của chính công cụ: 1 · 2 · 3 · 4 · 6 · 8 · 12 lần.
So với bản gốc không SL, trên TỪNG chân và trên CẢ danh mục.
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
SL_MULTS = (1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0)
FORM_END = pd.Timestamp("2024-01-01")


def sharpe(daily_bps: pd.Series) -> float:
    if len(daily_bps) < 30:
        return float("nan")
    sd = float(daily_bps.std(ddof=1))
    return float(daily_bps.mean()) / sd * np.sqrt(252) if sd > 0 else float("nan")


def _load_leg(name: str):
    """Trả (module, df nến, kết quả backtest) của một chân một-công-cụ."""
    mod = next(s for s in REG.STRATEGIES if s.name == name).load()
    ins = mod._load()
    res = mod.backtest()
    return mod, ins.df, res


def mae_of_trades(df: pd.DataFrame, trades: pd.DataFrame) -> pd.Series:
    """MAE của từng lệnh, đơn vị bps — quét bóng nến trong khoảng giữ lệnh."""
    hi = df["high"].to_numpy() if "high" in df else df["close"].to_numpy()
    lo = df["low"].to_numpy() if "low" in df else df["close"].to_numpy()
    idx = {t: i for i, t in enumerate(df.index)}
    out: List[float] = []
    for _, t in trades.iterrows():
        i = idx.get(t["entry_time"])
        j = idx.get(t["exit_time"])
        if i is None or j is None or j <= i:
            out.append(0.0)
            continue
        entry = float(t["entry_px"])
        if entry <= 0:
            out.append(0.0)
            continue
        side = int(t["side"])
        worst = lo[i:j + 1].min() if side > 0 else hi[i:j + 1].max()
        out.append(max(0.0, side * (entry - worst) / entry * 1e4))
    return pd.Series(out, index=trades.index)


def apply_sl(trades: pd.DataFrame, mae_bps: pd.Series, sl_bps: pd.Series
             ) -> pd.DataFrame:
    """Thay kết quả các lệnh có MAE >= SL bằng −SL. Trả bảng lệnh đã sửa."""
    t = trades.copy()
    hit = mae_bps >= sl_bps
    t["net_bps"] = np.where(hit, -sl_bps - t["cost_bps"], t["net_bps"])
    t["stopped"] = hit
    return t


def daily_from_trades(t: pd.DataFrame) -> pd.Series:
    s = pd.Series(t["net_bps"].to_numpy(),
                  index=pd.DatetimeIndex(t["exit_time"]).normalize())
    return s.groupby(s.index).sum()


def run_leg(name: str) -> Optional[pd.DataFrame]:
    """Quét SL cho MỘT chân. Trả bảng theo bội số ATR, hoặc None nếu không đo được."""
    try:
        mod, df, res = _load_leg(name)
    except Exception as exc:                                # pragma: no cover
        print(f"   {name}: KHÔNG nạp được — {exc}")
        return None
    trades = getattr(res, "trades", None)
    if trades is None or trades.empty:
        return None

    # ATR ngày quy theo bps, lấy TẠI nến vào lệnh (nhân quả, không nhìn tương lai).
    bars_per_day = {"M30": 48, "H1": 24, "H4": 6}.get(mod.TIMEFRAME, 24)
    atr_bar = _atr(df, 14) / df["close"] * 1e4
    atr_day = atr_bar * np.sqrt(bars_per_day)
    at_entry = atr_day.reindex(pd.DatetimeIndex(trades["entry_time"])).to_numpy()
    at_entry = pd.Series(at_entry, index=trades.index).ffill().fillna(
        float(atr_day.median()))

    mae = mae_of_trades(df, trades)
    base = daily_from_trades(trades)
    rows = [{"SL": "không có", "Sharpe": round(sharpe(base), 3),
             "net/lệnh": round(float(trades["net_bps"].mean()), 2),
             "% bị dừng": 0.0, "n": len(trades)}]
    for m in SL_MULTS:
        adj = apply_sl(trades, mae, at_entry * m)
        d = daily_from_trades(adj)
        rows.append({"SL": f"{m:g}×ATR",
                     "Sharpe": round(sharpe(d), 3),
                     "net/lệnh": round(float(adj["net_bps"].mean()), 2),
                     "% bị dừng": round(float(adj["stopped"].mean()) * 100, 1),
                     "n": len(adj)})
    out = pd.DataFrame(rows)
    out.insert(0, "chân", name)
    return out


def main() -> None:
    t0 = time.time()
    single = sorted(PF.SINGLE_LEGS.values())
    print(f"Quét dừng lỗ trên {len(single)} chân MỘT công cụ · "
          f"SL = {', '.join(f'{m:g}×ATR' for m in SL_MULTS)}")
    print("=" * 100)

    tables, daily_by_sl = [], {k: [] for k in ["không có"] + [f"{m:g}×ATR"
                                                             for m in SL_MULTS]}
    for name in single:
        tb = run_leg(name)
        if tb is None:
            continue
        tables.append(tb)
        # gom chuỗi ngày để dựng danh mục
        mod, df, res = _load_leg(name)
        trades = res.trades
        bars_per_day = {"M30": 48, "H1": 24, "H4": 6}.get(mod.TIMEFRAME, 24)
        atr_day = _atr(df, 14) / df["close"] * 1e4 * np.sqrt(bars_per_day)
        at_entry = pd.Series(
            atr_day.reindex(pd.DatetimeIndex(trades["entry_time"])).to_numpy(),
            index=trades.index).ffill().fillna(float(atr_day.median()))
        mae = mae_of_trades(df, trades)
        daily_by_sl["không có"].append(daily_from_trades(trades))
        for m in SL_MULTS:
            daily_by_sl[f"{m:g}×ATR"].append(
                daily_from_trades(apply_sl(trades, mae, at_entry * m)))
        print(f"   {name:22} xong")

    T = pd.concat(tables, ignore_index=True)
    T.to_csv(OUT / "sl_test_by_leg.csv", index=False)

    print()
    print("=" * 100)
    print("TỔNG HỢP THEO CHÂN — Sharpe trung vị và số chân TỆ ĐI khi thêm SL")
    print("=" * 100)
    base = T[T["SL"] == "không có"].set_index("chân")["Sharpe"]
    rows = []
    for lab in ["không có"] + [f"{m:g}×ATR" for m in SL_MULTS]:
        sub = T[T["SL"] == lab].set_index("chân")
        worse = int((sub["Sharpe"] < base).sum())
        rows.append({"SL": lab,
                     "Sharpe trung vị": round(float(sub["Sharpe"].median()), 3),
                     "chân TỆ ĐI": f"{worse}/{len(sub)}",
                     "% lệnh bị dừng": round(float(sub["% bị dừng"].mean()), 1),
                     "net/lệnh TB": round(float(sub["net/lệnh"].mean()), 2)})
    print(pd.DataFrame(rows).to_string(index=False))

    print()
    print("=" * 100)
    print("DANH MỤC 22 CHÂN GỘP (chuẩn hoá theo σ FORM rồi chia đều)")
    print("=" * 100)
    rows = []
    for lab, series_list in daily_by_sl.items():
        idx = None
        for s in series_list:
            idx = s.index if idx is None else idx.union(s.index)
        norm = []
        for s in series_list:
            s = s.reindex(idx).fillna(0.0)
            form = s[s.index < FORM_END]
            sd = float(form.std(ddof=1)) if len(form) > 30 else float(s.std(ddof=1))
            norm.append(s / sd if sd > 0 else s * 0.0)
        port = sum(norm) / len(norm)
        cum = port.cumsum()
        dd = float((cum.cummax() - cum).max())
        rows.append({"SL": lab, "Sharpe": round(sharpe(port), 3),
                     "Sharpe FORM": round(sharpe(port[port.index < FORM_END]), 3),
                     "Sharpe OOS": round(sharpe(port[port.index >= FORM_END]), 3),
                     "MaxDD (σ)": round(dd, 2)})
    P = pd.DataFrame(rows)
    print(P.to_string(index=False))
    P.to_csv(OUT / "sl_test_portfolio.csv", index=False)

    b = float(P[P["SL"] == "không có"]["Sharpe"].iloc[0])
    best = P[P["SL"] != "không có"].sort_values("Sharpe", ascending=False).iloc[0]
    print()
    print(f"KẾT LUẬN: không SL cho Sharpe {b:.3f}; mức SL TỐT NHẤT là "
          f"{best['SL']} với {best['Sharpe']:.3f} "
          f"({'TỐT HƠN' if best['Sharpe'] > b else 'VẪN TỆ HƠN'} không SL)")
    print(f"\nelapsed {time.time() - t0:.0f}s · CSV ở {OUT}")


if __name__ == "__main__":
    main()
