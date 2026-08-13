# -*- coding: utf-8 -*-
"""Vào khi z QUAY LẠI vào dải (Zheng) thay vì khi còn ngoài dải — winrate đổi bao nhiêu?

    .venv311\\Scripts\\python.exe research/fx/entry_mode_reenter.py

CƠ SỞ — CÓ TRƯỚC BACKTEST
==========================
Zheng Nan · "Profitability of Pairs Trading Based on Cointegration in the FX
Market" · MSc thesis 2025 · §4.3.1, mục lọc xác nhận vào lệnh: KHÔNG vào khi giá
vừa xuyên RA khỏi dải; chỉ vào khi giá QUAY TRỞ LẠI vào trong dải.

Lý do kinh tế nêu trong bài: xuyên ra chỉ chứng minh có lệch, không chứng minh lệch
sắp đóng. Đợi giá quay lại là đợi bằng chứng đầu tiên rằng hồi quy đã khởi động.

Hai luật, khác nhau đúng một chỗ — thời điểm trong cùng một lần lệch:

    "outside"  |z| > k VÀ nến trước cũng ngoài dải     vào KHI CÒN lệch
    "reenter"  nến trước ngoài dải VÀ |z| ĐÃ về trong  vào SAU KHI bắt đầu hồi

Đánh đổi dự kiến, và bài này để kiểm chính nó:
    · giá vào TỆ HƠN (một phần đường hồi đã đi mất) → R:R giảm
    · xác suất hồi CAO HƠN (đã có bằng chứng) → winrate tăng
    · số lệnh ÍT HƠN (bỏ các lần xuyên ra rồi giãn tiếp)

VÌ SAO ĐÁNG ĐO Ở ĐÚNG HỆ NÀY
=============================
Yêu cầu người vận hành đặt ra là TĂNG TỶ LỆ THẮNG và GIẢM DRAWDOWN. Bảng thoát lệnh
2026 chỉ ra chỗ chảy máu nằm ở nhánh TIME_STOP — 113 lệnh, winrate 35,4%, −$6.795.
Đó chính là nhóm lệnh "vào khi còn lệch rồi lệch giãn tiếp và không bao giờ hồi".
Luật "reenter" nhắm thẳng vào nhóm đó: nó không vào những lần ấy ngay từ đầu.

CÁCH ĐỌC — LUẬT HAY MAY MẮN
============================
In kết quả TỪNG CHÂN. Tiền lệ `exit_at_mean=False`: một tham số cho Sharpe đẹp ở
đúng chân mình cần nó đẹp, nhưng chỉ tốt hơn ở 1/7 chân, và kết luận đã thành quy
tắc — *một tham số chỉ đúng đúng ô mình cần là bậc tự do, không phải phát hiện*.

Ngưỡng nhận ở đây: cải thiện ở ĐA SỐ trong 12 chân ZBand, không phải ở tổng.
"""
import dataclasses
import importlib
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
_TF_DIR = {"M30": "m30", "H1": "h1", "H4": "h4", "D1": "d1"}


def _legs():
    out = []
    for spec in REG.STRATEGIES:
        if spec.stage not in (REG.LIVE, REG.FORWARD_TEST):
            continue
        d = _TF_DIR.get(spec.signal_tf)
        if not d:
            continue
        for p in sorted((ROOT / "src/python/strategies" / d).glob("*.py")):
            if p.name.startswith("__"):
                continue
            try:
                m = importlib.import_module(f"src.python.strategies.{d}.{p.stem}")
            except Exception:
                continue
            if getattr(m, "NAME", None) == spec.name and hasattr(m, "live_decision"):
                out.append((spec, m))
                break
    return out


def _run(mode: str) -> pd.DataFrame:
    """Chạy mọi chân; chân ZBand dùng `entry_mode=mode`, chân họ khác giữ nguyên."""
    frames = []
    for spec, mod in _legs():
        original = mod.CONFIG
        try:
            if hasattr(original, "entry_mode") and mode != original.entry_mode:
                mod.CONFIG = dataclasses.replace(original, entry_mode=mode)
            ins = mod._load()
            i0 = int(ins.df.index.searchsorted(pd.Timestamp(START)))
            if i0 >= len(ins.df):
                continue
            out = PARITY.replay_leg(mod, start=max(i0, 2), equity_usd=EQUITY0,
                                    spread_bps=ins.cost_1rt_bps,
                                    with_disaster_stop=True)
            rt = out["broker"].round_trips()
            if rt.empty:
                continue
            rt["leg"] = spec.name
            rt["is_zband"] = hasattr(original, "entry_mode")
            frames.append(rt)
        except Exception as exc:
            print(f"  {spec.name:22} LỖI {type(exc).__name__}: {str(exc)[:50]}")
        finally:
            mod.CONFIG = original       # TRẢ LẠI dù lỗi hay không
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _curve(tr: pd.DataFrame) -> tuple:
    tr = tr.sort_values("exit_time")
    w = 1.0 / max(len(set(tr["leg"])), 1)
    equity, day_start, cur = EQUITY0, EQUITY0, None
    eq, pnls = [], []
    for _, t in tr.iterrows():
        d = pd.Timestamp(t["exit_time"]).date()
        if d != cur:
            cur, day_start = d, equity
        dec = POL.decide(equity, day_start, 9.33, worst_day_bps=79.4)
        pnl = equity * dec.leverage * w * float(t["gross_bps"]) / 1e4
        equity += pnl
        eq.append(equity)
        pnls.append(pnl)
    s = pd.Series([EQUITY0] + eq)
    tr = tr.copy()
    tr["pnl_usd"] = pnls
    return equity, float(((s.cummax() - s) / s.cummax() * 100.0).max()), tr


def _stats(tr: pd.DataFrame) -> dict:
    win, loss = tr[tr["pnl_usd"] > 0], tr[tr["pnl_usd"] <= 0]
    aw = float(win["pnl_usd"].mean()) if len(win) else 0.0
    al = float(loss["pnl_usd"].mean()) if len(loss) else 0.0
    gl = abs(float(loss["pnl_usd"].sum()))
    ts = tr[tr["reason"].astype(str).str.contains("TIME_STOP", na=False)]
    return {"lệnh": len(tr), "thắng": len(win), "winrate": len(win) / max(len(tr), 1) * 100,
            "rr": abs(aw / al) if al else 0.0,
            "pf": float(win["pnl_usd"].sum()) / gl if gl else 0.0,
            "ts": len(ts), "ts_pnl": float(ts["pnl_usd"].sum()) if len(ts) else 0.0,
            "ts_win": float((ts["pnl_usd"] > 0).mean() * 100) if len(ts) else 0.0}


def main() -> int:
    print("Chạy hai luật vào lệnh qua ĐƯỜNG LIVE (parity.replay_leg)… (~8 phút)\n")
    runs = {}
    for label, mode in (("OUTSIDE (hiện tại)", "outside"), ("REENTER (Zheng)", "reenter")):
        print(f"  đang chạy {label}…")
        tr = _run(mode)
        if tr.empty:
            print(f"  {label}: không có lệnh")
            return 1
        eq, dd, tr = _curve(tr)
        runs[label] = {"equity": eq, "dd": dd, "tr": tr, **_stats(tr)}

    a, b = runs["OUTSIDE (hiện tại)"], runs["REENTER (Zheng)"]
    print()
    print("=" * 78)
    print("LUẬT VÀO LỆNH — 2026, đường vào lệnh thật")
    print("=" * 78)
    print(f"\n{'':24} {'OUTSIDE':>14} {'REENTER':>14} {'chênh':>13}")
    print("-" * 68)
    print(f"{'Số dư cuối':24} {'$' + format(a['equity'], ',.0f'):>14} "
          f"{'$' + format(b['equity'], ',.0f'):>14} "
          f"{'$' + format(b['equity'] - a['equity'], '+,.0f'):>13}")

    def row(n, va, vb, f="{:.2f}", s=""):
        print(f"{n:24} {f.format(va) + s:>14} {f.format(vb) + s:>14} "
              f"{f.format(vb - va) + s:>13}")

    row("Lãi/lỗ %", (a["equity"] - EQUITY0) / EQUITY0 * 100,
        (b["equity"] - EQUITY0) / EQUITY0 * 100, "{:+.2f}", "%")
    row("MaxDD", a["dd"], b["dd"], "{:.2f}", "%")
    print()
    row("Tổng lệnh", a["lệnh"], b["lệnh"], "{:.0f}")
    row("WINRATE", a["winrate"], b["winrate"], "{:.1f}", "%")
    row("R:R", a["rr"], b["rr"])
    row("Profit Factor", a["pf"], b["pf"])
    print()
    row("Lệnh TIME-STOP", a["ts"], b["ts"], "{:.0f}")
    print(f"{'Lãi/lỗ TIME-STOP':24} {'$' + format(a['ts_pnl'], '+,.0f'):>14} "
          f"{'$' + format(b['ts_pnl'], '+,.0f'):>14} "
          f"{'$' + format(b['ts_pnl'] - a['ts_pnl'], '+,.0f'):>13}")
    row("Winrate TIME-STOP", a["ts_win"], b["ts_win"], "{:.1f}", "%")

    print()
    print("TỪNG CHÂN ZBAND (chân họ khác phải KHÔNG đổi)")
    print(f"  {'CHÂN':22} {'outside':>10} {'reenter':>10} {'chênh':>10} "
          f"{'win out':>8} {'win re':>7}")
    print("  " + "-" * 72)
    better = worse = 0
    zb = set(a["tr"][a["tr"]["is_zband"]]["leg"]) | set(b["tr"][b["tr"]["is_zband"]]["leg"])
    for leg in sorted(set(a["tr"]["leg"]) | set(b["tr"]["leg"])):
        ta, tb = a["tr"][a["tr"]["leg"] == leg], b["tr"][b["tr"]["leg"] == leg]
        pa, pb = float(ta["pnl_usd"].sum()), float(tb["pnl_usd"].sum())
        wa = float((ta["pnl_usd"] > 0).mean() * 100) if len(ta) else 0.0
        wb = float((tb["pnl_usd"] > 0).mean() * 100) if len(tb) else 0.0
        if leg in zb:
            better += (pb - pa > 1)
            worse += (pb - pa < -1)
            mark = ""
        else:
            # Xem giải thích ghép nối danh mục ở `timestop_halflife_rule.py`.
            mark = "" if abs(pb - pa) < 1 else "  (ghép nối danh mục)"
        print(f"  {leg:22} ${pa:>9,.0f} ${pb:>9,.0f} ${pb - pa:>+9,.0f} "
              f"{wa:7.1f}% {wb:6.1f}%{mark}")

    print()
    print("PHÁN QUYẾT")
    print(f"  Trong {len(zb)} chân ZBand: {better} tốt hơn · {worse} tệ hơn")
    d_w = b["winrate"] - a["winrate"]
    d_p = b["equity"] - a["equity"]
    d_dd = b["dd"] - a["dd"]
    if better > len(zb) / 2 and d_p > 0 and d_dd <= 0.01:
        print("  → NHẬN: đa số chân tốt hơn, lãi tăng, MaxDD không tăng.")
    elif d_w > 0 and d_p <= 0:
        print(f"  → TỪ CHỐI: winrate {d_w:+.1f} điểm % nhưng lãi {d_p:+,.0f} $. "
              f"Winrate cao mà lãi thấp là đổi R:R lấy cảm giác an toàn.")
    elif better <= 1:
        print("  → TỪ CHỐI: cải thiện chỉ ở 0-1 chân = bậc tự do (tiền lệ "
              "`exit_at_mean=False`, 1/7 chân).")
    else:
        print(f"  → CHƯA ĐỦ: {better}/{len(zb)} chân, lãi {d_p:+,.0f} $, "
              f"MaxDD {d_dd:+.2f} đ%. Cần đo thêm.")

    print()
    print("Giới hạn: 6,5 tháng, một mẫu. Nhận luật vẫn phải qua đủ 6 kiểm định +")
    print("cổng PBO trước khi đổi mặc định trong `zband_core.ZBandConfig`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
