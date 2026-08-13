"""Vòng 59 — HỒI QUY TRUNG BÌNH trên công cụ ĐÃ CHỌN bằng chẩn đoán, M30 và H1.

VÌ SAO 57 VÒNG TRƯỚC TRƯỢT, VÀ VÒNG NÀY KHÁC Ở ĐÂU
===================================================
Mọi lab trước đều chạy trên RỔ 20 cross chia đều. Vòng 58 cho thấy vì sao cách đó
không thể thắng: biên hoà vốn phân tán cực rộng giữa các công cụ.

    AUDNZD  M30  φ = −0,0634 (t = −15,8)  c* = 7,71 bps  chi phí 1,38  biên **+6,33**
    CADJPY  M30  φ ≈  0       không đạt ngưỡng            biên ÂM

Chia đều 20 cross nghĩa là lấy một công cụ có biên +6,33 trộn với 19 công cụ phần lớn
biên âm. Kết quả là một danh mục có biên gần 0 — và đó đúng là thứ 57 vòng đo được.

Vòng này chỉ giao dịch công cụ QUA ĐƯỢC ba cổng chẩn đoán, đặt TRƯỚC khi backtest:
    1. biên = c* − chi phí > 1,0 bps
    2. |t(φ)| > 3,0
    3. φ CÙNG DẤU trên FORM và OOS

Việc chọn công cụ dựa trên MỘT thống kê (tự tương quan bậc một) chứ không dựa trên
Sharpe của backtest. Đó là khác biệt quan trọng về bậc tự do: chọn theo Sharpe là
chọn theo chính đại lượng sẽ báo cáo, chọn theo φ thì không.

BỘ QUY TẮC — HỒI QUY CÓ SL/TP CỤ THỂ
=====================================
    vào lệnh    |z(N)| > k, và nến TRƯỚC còn ngoài dải  → vào ngược chiều lệch
    thoát       z về 0 · time-stop · và ba biến thể SL/TP để đo
    khớp        MỞ CỬA nến kế tiếp sau nến tín hiệu — không nhìn trước

Vòng 57 đã đo được trên FX: `time_only` thắng mọi cấu hình có SL (H1 hồi quy: +0,035
vs −2,308 vs −4,264). Vòng này đo lại trên công cụ ĐÃ CHỌN — nếu kết luận đó tái lập,
bộ quy tắc cuối cùng sẽ dùng time-stop chứ không dùng SL theo ATR.
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

from research.fx.trade_lab import (ExitCfg, load_crosses, load_majors,
                                   run_trades, sharpe, sig_zband)

pd.set_option("display.width", 250, "display.max_columns", 40, "display.max_rows", 400)
FORM_END = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"

MIN_MARGIN_BPS = 1.0
MIN_ABS_T = 3.0

EXITS: Tuple[ExitCfg, ...] = (
    ExitCfg("time_only", None, None, None, 1.0),
    ExitCfg("time_only_2x", None, None, None, 2.0),
    ExitCfg("sl3atr_tp2R", 3.0, 2.0, None, 2.0),
    ExitCfg("sl4atr_tp3R", 4.0, 3.0, None, 2.0),
)


def selected_instruments() -> pd.DataFrame:
    """Công cụ qua ba cổng chẩn đoán của vòng 58. Đọc từ CSV, không tính lại."""
    d = pd.read_csv(OUT / "breakeven_diag.csv")
    return d[(d["biên"] > MIN_MARGIN_BPS) & (d["t(φ)"].abs() > MIN_ABS_T)
             & (d["cùng dấu"]) & (d["khai thác"] == "HỒI QUY")
             & (d["tf"].isin(["M30", "H1"]))].copy()


def main() -> None:
    t0 = time.time()
    sel = selected_instruments()
    print(f"Công cụ qua chẩn đoán: {len(sel)} ô "
          f"({sel['tf'].value_counts().to_dict()})")
    print(sel[["tf", "công cụ", "φ", "t(φ)", "c* bps", "chi phí bps", "biên"]]
          .to_string(index=False))

    rows: List[Dict] = []
    trades_keep: Dict[str, pd.DataFrame] = {}
    for tf in ("M30", "H1"):
        names = set(sel[sel["tf"] == tf]["công cụ"])
        if not names:
            continue
        universe = [i for i in (load_crosses(tf) + load_majors(tf))
                    if i.name in names]
        print(f"\n── {tf}: {len(universe)} công cụ", flush=True)
        for ins in universe:
            for n_bar in (24, 48, 96, 192):
                for k in (1.5, 2.0, 2.5):
                    el, es, w = sig_zband(ins.df, n=n_bar, k=k)
                    for cfg in EXITS:
                        res = run_trades(ins, el, es, w, cfg)
                        if res.trades.empty or len(res.trades) < 30:
                            continue
                        T = res.trades
                        d = res.pnl_daily
                        rows.append({
                            "tf": tf, "công cụ": ins.name, "N": n_bar, "k": k,
                            "thoát": cfg.name,
                            "ALL": round(sharpe(d), 3),
                            "FORM": round(sharpe(d, hi=FORM_END), 3),
                            "OOS": round(sharpe(d, lo=FORM_END), 3),
                            "n_lệnh": len(T),
                            "thắng%": round(float((T["net_bps"] > 0).mean()) * 100, 1),
                            "gross/lệnh": round(float(T["gross_bps"].mean()), 2),
                            "phí/lệnh": round(float(T["cost_bps"].mean()), 2),
                            "net/lệnh": round(float(T["net_bps"].mean()), 2),
                            "nến/lệnh": round(float(T["bars"].mean()), 1)})
                        key = f"{tf}|{ins.name}|N{n_bar}|k{k}|{cfg.name}"
                        trades_keep[key] = T
        print(f"   xong ({time.time() - t0:.0f}s)", flush=True)

    R = pd.DataFrame(rows)
    R.to_csv(OUT / "focused_mr.csv", index=False)

    print()
    print("=" * 145)
    print("A. SO SÁNH CẤU HÌNH THOÁT — kiểm định lại kết luận vòng 57 trên công cụ đã chọn")
    print("=" * 145)
    print(R.groupby(["thoát", "tf"]).agg(
        ALL_tv=("ALL", "median"), OOS_tv=("OOS", "median"),
        net_tv=("net/lệnh", "median"), thắng_tv=("thắng%", "median"),
        n_ô=("ALL", "size")).round(3).to_string())

    print()
    print("=" * 145)
    print("B. 30 Ô TỐT NHẤT")
    print("=" * 145)
    print(R.sort_values("ALL", ascending=False).head(30).to_string(index=False))

    print()
    print("=" * 145)
    print("C. CỔNG: FORM>0 & OOS>0 & ALL>0,50 & net/lệnh>0 & n_lệnh>=50")
    print("=" * 145)
    k = R[(R["FORM"] > 0) & (R["OOS"] > 0) & (R["ALL"] > 0.50)
          & (R["net/lệnh"] > 0) & (R["n_lệnh"] >= 50)].sort_values(
        "ALL", ascending=False)
    print(k.to_string(index=False) if len(k) else "  KHÔNG CÓ")

    if len(k):
        print()
        print("── VÙNG THAM SỐ quanh mỗi ô qua cổng (kiểm tra không phải đỉnh cô lập)")
        for _, r in k.head(6).iterrows():
            nb = R[(R["tf"] == r.tf) & (R["công cụ"] == r["công cụ"])
                   & (R["thoát"] == r["thoát"])]
            piv = nb.pivot_table(index="N", columns="k", values="ALL")
            print(f"\n   {r.tf} · {r['công cụ']} · {r['thoát']}")
            print("   " + piv.round(3).to_string().replace("\n", "\n   "))
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
