# -*- coding: utf-8 -*-
"""Neo time-stop vào NỬA ĐỜI thay vì tinh chỉnh từng chân — luật Zheng 4,32.

    .venv311\\Scripts\\python.exe research/fx/timestop_halflife_rule.py

CƠ SỞ KHOA HỌC — CÓ TRƯỚC BACKTEST
===================================
Zheng Nan · "Profitability of Pairs Trading Based on Cointegration in the FX
Market" · MSc thesis 2025 · §4.3.1 và §5.1.4 — đúng bài toán của hệ này (hồi quy
trung bình trên FX, không phải cổ phiếu).

Bài đó neo CẢ cửa sổ Bollinger LẪN thời hạn giữ vào nửa đời hồi quy:

    cửa sổ = thời hạn giữ = 4,32 × HL,   4,32 = ln(1/0,05) / ln(2) = 2,996/0,693

4,32 không phải tham số tinh chỉnh: nó là số lần nửa đời cần để một quá trình OU
phân rã hết 95% độ lệch. Chọn nó KHÔNG tiêu bậc tự do nào — đúng loại công cụ
CLAUDE.md xếp ưu tiên 2, cùng hạng với ngưỡng hoà vốn `c*` của Sepp & Lucic.

Zheng đo được (Bảng 3/4/5, ¥100tr gross mỗi cặp):

    cửa sổ 252 ngày CỐ ĐỊNH   P&L ¥14,3tr · 0,65% · 120 lệnh · win 73,3% · 103,2 nến
    cửa sổ 4,32×HL + TIME-STOP  P&L ¥72,1tr · 3,28% · 225 lệnh · win 78,2% ·  53,1 nến
    cửa sổ 4,32×HL + STOP GIÁ 3σ  P&L ¥38,8tr · 1,76% · 258 lệnh · win 68,2% · 47,5 nến

Hai kết luận, cả hai đều khớp với hệ này:
  · neo cửa sổ vào HL thay vì cố định: **+400% P&L**, winrate 73,3 → 78,2%
  · stop theo GIÁ hại, stop theo THỜI GIAN lợi — trùng phép đo `sl_test.py` của
    repo (mọi mức SL đều tệ hơn, 1×ATR mất 23% Sharpe VÀ làm MaxDD tệ đi)

PHÁT HIỆN KHI ĐỐI CHIẾU — CỬA SỔ ĐÃ ĐÚNG, THỜI HẠN THÌ KHÔNG
==============================================================
`halflife_diag.py` đo nửa đời cả 12 chân ZBand. Tỷ lệ cửa sổ / nửa đời:

    ZBandGBPAUDM30 4,41 · ZBandGBPNZDH4 4,37 · ZBandGBPUSDH1 4,38 · ZBandNZDCADH1 4,46
    ZBandGBPAUDH4  4,46 · ZBandGBPAUDH1 4,45 · ZBandAUDCADH4 4,58 · ZBandAUDCADH1 4,58
    ZBandNZDCADM30 4,65 · ZBandEURCHFH1 4,73 · ZBandAUDCADM30 4,79 · ZBandEURGBPH1 4,98

**Cả 12 nằm trong 4,37–4,98** — quanh đúng 4,32 của Zheng. Các cửa sổ này tìm ra
bằng quét lưới, còn 4,32 suy từ lý thuyết OU; hai đường độc lập gặp nhau ở cùng một
chỗ. Đó là bằng chứng mạnh rằng cửa sổ đang đúng.

Nhưng thời hạn giữ = cửa sổ × `timestop_mult`, và 5 chân có mult 2,0–3,0:

    ZBandEURCHFH1  ×3 → 14,19 lần HL      ZBandEURGBPH1 ×3 → 14,94 lần HL
    ZBandGBPAUDH4  ×3 → 13,38 lần HL      ZBandAUDCADH4 ×2 →  9,17 lần HL
    ZBandGBPUSDH1  ×2 →  8,76 lần HL

Giữ 9–15 lần nửa đời nghĩa là chuỗi đã có 9–15 cơ hội hồi mà không hồi. Theo mô
hình OU thì xác suất còn lại của độ lệch ban đầu ở mốc 14 nửa đời là 2⁻¹⁴ ≈ 0,006%
— giả thuyết vào lệnh đã hết hạn từ lâu, vốn vẫn bị giam.

GIẢ THUYẾT ĐO Ở ĐÂY
====================
Đặt `timestop_mult = 1,0` cho MỌI chân ZBand → tỷ lệ về 4,37–4,98, đúng luật Zheng.

Đây là thay đổi LÀM GIẢM bậc tự do: 5 tham số tinh chỉnh riêng từng chân biến mất,
thay bằng một luật có công thức. Ngược hướng với overfit.

CÁCH ĐỌC KẾT QUẢ — BÀI HỌC `exit_at_mean=False`
================================================
Chân ZBandGBPCAD_H4 từng "được cứu" bằng một tham số mới cho Sharpe 0,815 → 0,865,
nhưng đo trên cả bảy chân thì nó chỉ tốt hơn ở **1/7**. Kết luận đã thành quy tắc:
*một tham số chỉ đúng đúng ô mình cần nó đúng là bậc tự do, không phải phát hiện.*

Nên bài này in **kết quả TỪNG CHÂN**, không chỉ tổng. Luật chỉ được nhận nếu nó cải
thiện ĐA SỐ trong 5 chân bị đổi — thắng ở 1/5 thì là may, không phải luật.
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

# Hằng số Zheng: số lần nửa đời để quá trình OU phân rã 95% độ lệch.
ZHENG_K = np.log(1.0 / 0.05) / np.log(2.0)      # = 4,3219…


def _legs():
    """(spec, module) của mọi chân ĐƠN — cùng cách chọn với các bài 2026 khác."""
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


def _run(apply_rule: bool) -> pd.DataFrame:
    """Chạy mọi chân; `apply_rule=True` ép `timestop_mult=1,0` cho chân ZBand."""
    frames = []
    for spec, mod in _legs():
        original = mod.CONFIG
        try:
            cfg = original
            if apply_rule and hasattr(cfg, "timestop_mult"):
                # Chỉ đụng ZBand. Bốn họ tín hiệu dùng `timestop_bars` tuyệt đối và
                # KHÔNG phải hồi quy trung bình theo z — luật Zheng không nói gì về
                # chúng, nên áp sang đó là suy diễn ngoài tài liệu.
                mod.CONFIG = dataclasses.replace(cfg, timestop_mult=1.0)
            ins = mod._load()
            df = ins.df
            i0 = int(df.index.searchsorted(pd.Timestamp(START)))
            if i0 >= len(df):
                continue
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
            # TRẢ LẠI CONFIG GỐC dù có lỗi hay không — module nằm trong `sys.modules`,
            # một CONFIG sót lại làm mọi lượt sau chạy sai tham số mà không ai báo.
            mod.CONFIG = original
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _curve(tr: pd.DataFrame) -> tuple:
    """(số dư cuối, MaxDD %, bảng có pnl_usd) — cùng công thức mọi bài 2026."""
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
    win = tr[tr["pnl_usd"] > 0]
    loss = tr[tr["pnl_usd"] <= 0]
    aw = float(win["pnl_usd"].mean()) if len(win) else 0.0
    al = float(loss["pnl_usd"].mean()) if len(loss) else 0.0
    gl = abs(float(loss["pnl_usd"].sum()))
    ts = tr[tr["reason"].astype(str).str.contains("TIME_STOP", na=False)]
    return {
        "lệnh": len(tr),
        "thắng": len(win),
        "thua": len(loss),
        "winrate": len(win) / max(len(tr), 1) * 100.0,
        "rr": abs(aw / al) if al else 0.0,
        "pf": float(win["pnl_usd"].sum()) / gl if gl else 0.0,
        "ts lệnh": len(ts),
        "ts pnl": float(ts["pnl_usd"].sum()) if len(ts) else 0.0,
        "ts win": float((ts["pnl_usd"] > 0).mean() * 100.0) if len(ts) else 0.0,
    }


def main() -> int:
    print(f"Hằng số Zheng k = ln(1/0,05)/ln2 = {ZHENG_K:.4f}")
    print("Chạy hai kịch bản qua ĐƯỜNG LIVE (parity.replay_leg)… (~8 phút)\n")

    runs = {}
    for label, rule in (("HIỆN TẠI", False), ("LUẬT 4,32", True)):
        print(f"  đang chạy {label}…")
        tr = _run(rule)
        if tr.empty:
            print(f"  {label}: không có lệnh")
            return 1
        eq, dd, tr = _curve(tr)
        runs[label] = {"equity": eq, "dd": dd, "tr": tr, **_stats(tr)}

    a, b = runs["HIỆN TẠI"], runs["LUẬT 4,32"]

    print()
    print("=" * 78)
    print("NEO TIME-STOP VÀO NỬA ĐỜI — 2026, đường vào lệnh thật")
    print("=" * 78)
    print(f"\n{'':24} {'HIỆN TẠI':>14} {'LUẬT 4,32':>14} {'chênh':>13}")
    print("-" * 68)

    def row(name, ka, kb, fmt="{:.2f}", suffix=""):
        va, vb = ka, kb
        d = vb - va
        print(f"{name:24} {fmt.format(va) + suffix:>14} "
              f"{fmt.format(vb) + suffix:>14} {fmt.format(d) + suffix:>13}")

    print(f"{'Số dư cuối':24} {'$' + format(a['equity'], ',.0f'):>14} "
          f"{'$' + format(b['equity'], ',.0f'):>14} "
          f"{'$' + format(b['equity'] - a['equity'], '+,.0f'):>13}")
    row("Lãi/lỗ %", (a["equity"] - EQUITY0) / EQUITY0 * 100,
        (b["equity"] - EQUITY0) / EQUITY0 * 100, "{:+.2f}", "%")
    row("MaxDD", a["dd"], b["dd"], "{:.2f}", "%")
    print()
    row("Tổng lệnh", a["lệnh"], b["lệnh"], "{:.0f}")
    row("Thắng / thua", a["thắng"], b["thắng"], "{:.0f}")
    row("Winrate", a["winrate"], b["winrate"], "{:.1f}", "%")
    row("R:R", a["rr"], b["rr"])
    row("Profit Factor", a["pf"], b["pf"])
    print()
    row("Lệnh TIME-STOP", a["ts lệnh"], b["ts lệnh"], "{:.0f}")
    print(f"{'Lãi/lỗ TIME-STOP':24} {'$' + format(a['ts pnl'], '+,.0f'):>14} "
          f"{'$' + format(b['ts pnl'], '+,.0f'):>14} "
          f"{'$' + format(b['ts pnl'] - a['ts pnl'], '+,.0f'):>13}")
    row("Winrate TIME-STOP", a["ts win"], b["ts win"], "{:.1f}", "%")

    # ── TỪNG CHÂN — chỗ phân biệt LUẬT với MAY MẮN.
    print()
    print("TỪNG CHÂN (chỉ 5 chân bị đổi mới có ý nghĩa; 7 chân kia phải KHÔNG đổi)")
    print(f"  {'CHÂN':22} {'hiện tại':>11} {'luật 4,32':>11} {'chênh':>11}  đánh giá")
    print("  " + "-" * 74)
    changed = {"ZBandEURCHFH1", "ZBandGBPUSDH1", "ZBandEURGBPH1",
               "ZBandAUDCADH4", "ZBandGBPAUDH4"}
    better = worse = 0
    for leg in sorted(set(a["tr"]["leg"]) | set(b["tr"]["leg"])):
        pa = float(a["tr"][a["tr"]["leg"] == leg]["pnl_usd"].sum())
        pb = float(b["tr"][b["tr"]["leg"] == leg]["pnl_usd"].sum())
        d = pb - pa
        if leg in changed:
            mark = "ĐỔI  " + ("tốt hơn" if d > 1 else
                              "tệ hơn" if d < -1 else "không đổi")
            if d > 1:
                better += 1
            elif d < -1:
                worse += 1
        else:
            # Chân KHÔNG bị đổi cấu hình vẫn có `pnl_usd` lệch chút ít, và đó KHÔNG
            # phải rò rỉ tham số — đã kiểm chứng riêng: ZBandNZDCADH1 cho đúng 40
            # lệnh và đúng −81,7 bps gộp ở cả hai kịch bản.
            #
            # Nguyên nhân là GHÉP NỐI DANH MỤC: `_curve` chạy tuần tự mọi lệnh của
            # mọi chân theo `exit_time`, và đòn bẩy do chính sách cấp phụ thuộc equity
            # đang chạy. Đổi lệnh của một chân là dịch đường equity, và mọi lệnh SAU
            # đó ở MỌI chân được cấp đòn bẩy khác đi.
            #
            # Nên so chân không đổi phải so `gross_bps` (bất biến), không so `pnl_usd`.
            mark = "" if abs(d) < 1 else "(lệch do ghép nối danh mục, không phải rò rỉ)"
        print(f"  {leg:22} ${pa:>10,.0f} ${pb:>10,.0f} ${d:>+10,.0f}  {mark}")

    print()
    print("PHÁN QUYẾT")
    print(f"  Trong 5 chân bị đổi: {better} tốt hơn · {worse} tệ hơn")
    d_pnl = b["equity"] - a["equity"]
    d_dd = b["dd"] - a["dd"]
    if better >= 3 and d_pnl > 0 and d_dd <= 0.01:
        print("  → NHẬN: đa số chân cải thiện, lãi tăng, MaxDD không tăng.")
    elif better >= 3 and d_pnl > 0:
        print(f"  → CÂN NHẮC: lãi +${d_pnl:,.0f} nhưng MaxDD +{d_dd:.2f} điểm %. "
              f"Account Survival đứng trên Profit — chỉ nhận nếu MaxDD vẫn dưới 9%.")
    elif better <= 1:
        print("  → TỪ CHỐI: cải thiện chỉ ở 0-1 chân = bậc tự do, không phải luật "
              "(tiền lệ `exit_at_mean=False`, 1/7 chân).")
    else:
        print(f"  → KHÔNG ĐỦ BẰNG CHỨNG: {better}/5 chân. Cần đo thêm.")

    print()
    print("Giới hạn: 6,5 tháng, 22/27 chân, một mẫu. Nhận luật vẫn phải qua đủ 6")
    print("kiểm định + cổng PBO trước khi vào `registry.STRATEGIES`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
