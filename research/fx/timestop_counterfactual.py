# -*- coding: utf-8 -*-
"""Time-stop đang CỨU hay đang CẮT? Đo bằng phản chứng trên đúng đường live.

    .venv311\\Scripts\\python.exe research/fx/timestop_counterfactual.py

CÂU HỎI
========
Vòng backtest 2026 cho thấy time-stop là nhánh thoát DUY NHẤT lỗ, và nó lỗ nặng:

    SIGNAL     340 lệnh   +$5.941
    MEAN       213 lệnh   +$5.831
    TIME_STOP  113 lệnh   −$6.795   ← nuốt 58% lãi của hai nhánh kia
    REVERSE      7 lệnh      +$86

Nhưng bảng đó KHÔNG trả lời được câu quan trọng: 113 lệnh ấy lỗ **vì** time-stop
cắt sớm, hay time-stop đã **cứu** chúng khỏi lỗ sâu hơn? Một lệnh đang âm khi chạm
time-stop thì đằng nào cũng âm — vấn đề là nếu giữ tiếp thì nó hồi hay tệ đi.

CÁCH ĐO — CHẠY LẠI, KHÔNG NHÌN TỚI TRƯỚC
=========================================
Cách sai: lấy 113 lệnh đó rồi tra giá vài nến sau điểm thoát. Sai vì nó giả định
mọi thứ khác giữ nguyên — trong khi giữ lệnh lâu hơn làm chân đó BỎ LỠ những lệnh
kế tiếp, và chuỗi lệnh sau đó lệch hoàn toàn.

Cách đúng: nới `time_stop` trong CONFIG rồi chạy lại `parity.replay_leg` — đúng
chuỗi `live_decision → position_book → order_plan → order_router → SimBroker`. Mọi
hệ quả dây chuyền được mô phỏng, kể cả việc lỡ lệnh sau.

BA KỊCH BẢN
============
    ×1,0   nguyên trạng (mốc so sánh)
    ×1,5   nới vừa
    ×2,0   nới mạnh

Đọc kết quả: lợi nhuận tăng mà MaxDD **không** tăng thì đáng nới. Lợi nhuận tăng
kèm MaxDD tăng thì phải cân theo thứ tự ưu tiên của dự án — Account Survival đứng
trên Profit Maximization, nên MaxDD tăng là lý do TỪ CHỐI kể cả khi lãi tăng.
"""
import copy
import dataclasses
import importlib
import io
import sys
from pathlib import Path

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
# ⚠️ THÊM HƯỚNG RÚT NGẮN 15/08/2026 — sau chẩn đoán nửa đời.
#
# `research/fx/halflife_diag.py` đo nửa đời hồi quy của cả 12 chân ZBand và cho
# một kết quả không ai ngờ: **0/12 chân có time-stop trong khoảng 1–3× nửa đời**.
# Mọi chân đều giữ DÀI HƠN 4,4 tới 14,9 lần nửa đời:
#
#     ZBandGBPNZDH4    nửa đời  2,7 nến · time-stop  12 nến →  4,4×
#     ZBandAUDCADH1    nửa đời 10,5 nến · time-stop  48 nến →  4,6×
#     ZBandEURGBPH1    nửa đời 77,1 nến · time-stop 1152 nến → 14,9×
#     trung vị: nửa đời 15,4 nến · tỷ lệ 4,72×
#
# Nghĩa là khi time-stop kích hoạt, chuỗi đã có 4–15 lần nửa đời để hồi mà KHÔNG
# hồi. Đó là bằng chứng quan hệ đã đứt, không phải bằng chứng ta thiếu kiên nhẫn.
#
# Giả thuyết ban đầu của bài này ("nới ra thì cứu được lệnh") đã bị chính nó bác
# bỏ: ×1,5 và ×2,0 đều làm TỔNG lãi giảm. Chẩn đoán nửa đời giải thích vì sao, và
# chỉ hướng NGƯỢC LẠI — cắt SỚM hơn để giải phóng vốn cho lệnh kế tiếp.
SCENARIOS = (0.5, 0.75, 1.0, 1.5, 2.0)
_TF_DIR = {"M30": "m30", "H1": "h1", "H4": "h4", "D1": "d1"}


def _legs():
    """(spec, module) của mọi chân ĐƠN — cùng cách chọn với `live_path_backtest_2026`."""
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


def _stretch(cfg, mult: float):
    """CONFIG mới với time-stop nhân `mult`. KHÔNG sửa CONFIG gốc.

    Hai họ chiến lược khai báo time-stop theo hai cách khác nhau, và nhầm chỗ này
    là nới cho một nửa số chân rồi tưởng đã nới hết:

        ZBandConfig    `window_bars × timestop_mult`   → nhân vào `timestop_mult`
        FamilyConfig   `timestop_bars` tuyệt đối       → nhân vào `timestop_bars`
    """
    if hasattr(cfg, "timestop_mult"):
        return dataclasses.replace(cfg, timestop_mult=cfg.timestop_mult * mult)
    if hasattr(cfg, "timestop_bars"):
        return dataclasses.replace(
            cfg, timestop_bars=max(1, int(round(cfg.timestop_bars * mult))))
    return cfg


def _run(mult: float) -> pd.DataFrame:
    """Chạy toàn bộ chân với time-stop × `mult`, trả bảng lệnh đã đóng."""
    frames = []
    for spec, mod in _legs():
        original = mod.CONFIG
        try:
            ins = mod._load()
            df = ins.df
            i0 = int(df.index.searchsorted(pd.Timestamp(START)))
            if i0 >= len(df):
                continue
            mod.CONFIG = _stretch(original, mult)
            out = PARITY.replay_leg(mod, start=max(i0, 2), equity_usd=EQUITY0,
                                    spread_bps=ins.cost_1rt_bps,
                                    with_disaster_stop=True)
            rt = out["broker"].round_trips()
            if rt.empty:
                continue
            rt["leg"] = spec.name
            frames.append(rt)
        except Exception as exc:
            print(f"  {spec.name:22} LỖI {type(exc).__name__}: {str(exc)[:50]}")
        finally:
            # TRẢ LẠI CONFIG GỐC dù có lỗi hay không. Module đã import nằm trong
            # `sys.modules`, nên một CONFIG bị sửa sót lại sẽ làm mọi bài chạy sau
            # trong cùng tiến trình dùng tham số sai mà không có gì báo.
            mod.CONFIG = original
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _equity_curve(tr: pd.DataFrame) -> tuple:
    """(số dư cuối, MaxDD %, bảng lệnh có pnl_usd) — cùng công thức bài 2026."""
    tr = tr.sort_values("exit_time")
    n_legs = max(len(set(tr["leg"])), 1)
    w = 1.0 / n_legs
    equity, day_start, cur_day = EQUITY0, EQUITY0, None
    eq, pnls = [], []
    for _, t in tr.iterrows():
        d = pd.Timestamp(t["exit_time"]).date()
        if d != cur_day:
            cur_day, day_start = d, equity
        dec = POL.decide(equity, day_start, 9.33, worst_day_bps=79.4)
        pnl = equity * dec.leverage * w * float(t["gross_bps"]) / 1e4
        equity += pnl
        eq.append(equity)
        pnls.append(pnl)
    s = pd.Series([EQUITY0] + eq)
    dd = ((s.cummax() - s) / s.cummax() * 100.0).max()
    tr = tr.copy()
    tr["pnl_usd"] = pnls
    return equity, float(dd), tr


def main() -> int:
    results = {}
    for m in SCENARIOS:
        print(f"Đang chạy time-stop ×{m:.1f}…")
        tr = _run(m)
        if tr.empty:
            print("  không có lệnh nào")
            continue
        equity, dd, tr = _equity_curve(tr)
        ts = tr[tr["reason"].astype(str).str.contains("TIME_STOP", na=False)]
        results[m] = {
            "số dư cuối": equity,
            "lãi/lỗ": equity - EQUITY0,
            "MaxDD %": dd,
            "số lệnh": len(tr),
            "lệnh time-stop": len(ts),
            "lãi/lỗ time-stop": float(ts["pnl_usd"].sum()) if len(ts) else 0.0,
            "winrate %": float((tr["pnl_usd"] > 0).mean() * 100.0),
        }

    if not results:
        return 1

    print()
    print("=" * 78)
    print("PHẢN CHỨNG TIME-STOP — 2026, đường vào lệnh thật")
    print("=" * 78)
    base = results.get(1.0, {})
    print(f"\n{'kịch bản':12} {'số dư cuối':>13} {'lãi/lỗ':>11} {'MaxDD':>8} "
          f"{'lệnh':>6} {'TS lệnh':>8} {'TS lãi/lỗ':>11} {'win%':>6}")
    print("-" * 78)
    for m, r in results.items():
        print(f"×{m:<11.1f} ${r['số dư cuối']:>12,.0f} "
              f"${r['lãi/lỗ']:>+10,.0f} {r['MaxDD %']:>7.2f}% "
              f"{r['số lệnh']:>6} {r['lệnh time-stop']:>8} "
              f"${r['lãi/lỗ time-stop']:>+10,.0f} {r['winrate %']:>5.1f}%")

    print()
    print("KẾT LUẬN")
    for m, r in results.items():
        if m == 1.0 or not base:
            continue
        d_pnl = r["lãi/lỗ"] - base["lãi/lỗ"]
        d_dd = r["MaxDD %"] - base["MaxDD %"]
        if d_pnl > 0 and d_dd <= 0.01:
            verdict = "ĐÁNG NỚI — lãi tăng, MaxDD không tăng"
        elif d_pnl > 0:
            verdict = (f"lãi tăng nhưng MaxDD +{d_dd:.2f} điểm % — "
                       f"TỪ CHỐI theo thứ tự ưu tiên (Account Survival > Profit)")
        else:
            verdict = "KHÔNG nới — time-stop đang CỨU, không phải cắt"
        print(f"  ×{m:.1f}: lãi {d_pnl:+,.0f} $ · MaxDD {d_dd:+.2f} điểm % → {verdict}")

    print()
    print("Giới hạn: 6,5 tháng và 22/27 chân. Kết luận này là GỢI Ý HƯỚNG, chưa đủ")
    print("để đổi tham số — đổi time-stop phải qua đủ 6 kiểm định + cổng PBO.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
