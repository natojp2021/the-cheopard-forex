# -*- coding: utf-8 -*-
"""Nửa đời hồi quy của 12 chân ZBand — time-stop có khớp với tốc độ hồi thật không?

    .venv311\\Scripts\\python.exe research/fx/halflife_diag.py

VÌ SAO ĐO TRƯỚC KHI ĐỌC XONG TÀI LIỆU
======================================
Nhánh TIME-STOP là chỗ chảy máu duy nhất của hệ: 113/673 lệnh, winrate 35,4%,
−$6.795 — trong khi ba nhánh còn lại đều lãi. Bất kỳ đề xuất nào từ tài liệu
pairs-trading cũng sẽ đụng tới cùng một câu hỏi: **thời hạn giữ có khớp với tốc
độ hồi quy thật của chuỗi không?**

Nửa đời (half-life) trả lời câu đó bằng một con số, và nó là CHẨN ĐOÁN — đo được
TRƯỚC khi backtest, không tốn bậc tự do nào. Đây đúng loại công cụ mà CLAUDE.md
xếp ưu tiên 2 trong "Tìm chiến lược — chỉ chấp nhận cơ sở KHOA HỌC", cùng hạng với
ngưỡng hoà vốn `c*` của Sepp & Lucic đã chấm dứt 57 vòng quét mù.

CÔNG THỨC — Ornstein-Uhlenbeck rời rạc
=======================================
Hồi quy `Δz_t = a + b·z_{t-1} + ε` trên chính chuỗi z mà chiến lược dùng. Với
`b < 0` (có hồi quy), nửa đời là:

    HL = −ln(2) / ln(1 + b)          [đơn vị: SỐ NẾN]

`b ≥ 0` nghĩa là chuỗi KHÔNG hồi quy trong cửa sổ đó — trả vô cực.

Chuẩn quen dùng trong tài liệu pairs-trading: thời hạn giữ nên ở khoảng
1–3 lần nửa đời. Ngắn hơn thì cắt trước khi kịp hồi; dài hơn thì giam vốn vào một
vị thế mà giả thuyết đã hết hạn.

KẾT QUẢ ĐÃ ĐO — ĐỌC TRƯỚC KHI DIỄN GIẢI BẢNG BÊN DƯỚI (16/08/2026)
==================================================================
Bảng này in "TS DÀI hơn 3× nửa đời" cho cả 12 chân, và đọc thoáng thì tưởng là một
lỗi cần sửa. **KHÔNG PHẢI.** Hai điều đã đo sau đó:

1. CỬA SỔ ĐANG ĐÚNG, và đây là phát hiện đáng giữ nhất của bài. Tỷ lệ
   `window_bars / nửa đời` của cả 12 chân nằm trong **4,37–4,98**, trùng với hằng
   số 4,32 = ln(1/0,05)/ln2 mà Zheng suy từ lý thuyết OU. Các cửa sổ này tìm bằng
   quét lưới, hoàn toàn độc lập với bài báo — hai đường gặp nhau ở cùng một chỗ.

2. ÉP THỜI HẠN VỀ ĐÚNG LUẬT LẠI TỆ HƠN. `timestop_halflife_rule.py` đặt
   `timestop_mult = 1,0` cho cả 12 chân (tỷ lệ về 4,4–5,0) rồi chạy đường live:
   lãi −0,18 điểm %, và nhánh TIME_STOP tệ đi (−$9.992 → −$11.924, winrate
   35,4% → 31,7%). Từng chân: 2 tốt hơn, 3 tệ hơn.

Cộng với hai phản chứng nới ×1,5 và ×2,0 cũng làm lãi giảm, kết luận là: **thời hạn
giữ không phải biến giải thích**. 113 lệnh TIME_STOP thua vì chúng là những lần hồi
quy thật sự không xảy ra — cắt sớm hơn hay muộn hơn đều không cứu được. Hướng đã vào
`registry.REJECTED_DIRECTIONS` với tên `TimeStopAtHalfLife_Zheng432`.

⚠️ ĐÂY LÀ CHẨN ĐOÁN, KHÔNG PHẢI ĐỀ XUẤT ĐỔI THAM SỐ
====================================================
Bài này chỉ TRẢ LỜI "time-stop hiện tại nằm ở đâu so với nửa đời". Đổi tham số
phải qua đủ 6 kiểm định + cổng PBO, và phải đo trên CÙNG ĐƯỜNG CODE với sản xuất
— bài học đã thành quy tắc sau vụ `ZBandGBPCAD_H4_exit_at_mean_False` (lab cho
Sharpe 0,815, động cơ thật cho 0,557, vì lab thiếu nhánh thoát khi z về 0).
"""
import importlib
import io
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

from src.python.strategies import registry as REG  # noqa: E402

_TF_DIR = {"M30": "m30", "H1": "h1", "H4": "h4", "D1": "d1"}


def half_life(z: pd.Series) -> float:
    """Nửa đời hồi quy của chuỗi `z`, tính bằng SỐ NẾN. inf nếu không hồi quy."""
    s = pd.Series(z).dropna()
    if len(s) < 100:
        return float("nan")
    lag = s.shift(1).dropna()
    d = (s - s.shift(1)).dropna()
    n = min(len(lag), len(d))
    lag, d = lag.iloc[-n:], d.iloc[-n:]
    x = np.column_stack([np.ones(n), lag.to_numpy()])
    try:
        b = float(np.linalg.lstsq(x, d.to_numpy(), rcond=None)[0][1])
    except Exception:
        return float("nan")
    if b >= 0:
        return float("inf")
    return float(-np.log(2.0) / np.log(1.0 + b))


def _zband_legs():
    """(spec, module) của các chân ZBand — chúng dùng chung `zband_core`."""
    out = []
    for spec in REG.STRATEGIES:
        if spec.stage not in (REG.LIVE, REG.FORWARD_TEST):
            continue
        if not spec.name.startswith("ZBand"):
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
            if getattr(m, "NAME", None) == spec.name:
                out.append((spec, m))
                break
    return out


def main() -> int:
    legs = _zband_legs()
    print(f"Đo nửa đời hồi quy của {len(legs)} chân ZBand… (~2 phút)\n")
    print("=" * 92)
    print("NỬA ĐỜI HỒI QUY vs THỜI HẠN GIỮ (time-stop)")
    print("=" * 92)
    print(f"{'CHÂN':22} {'khung':>5} {'cửa sổ z':>9} {'time-stop':>10} "
          f"{'nửa đời':>9} {'TS/HL':>7}  đánh giá")
    print("-" * 92)

    rows = []
    for spec, mod in legs:
        try:
            ins = mod._load()
            cfg = mod.CONFIG
            w = int(cfg.window_bars)
            ts = int(round(w * cfg.timestop_mult))
            c = ins.df["close"]
            z = (c - c.rolling(w).mean()) / c.rolling(w).std(ddof=1)
            hl = half_life(z)
            ratio = ts / hl if np.isfinite(hl) and hl > 0 else float("nan")
            # Chuẩn tài liệu pairs-trading: thời hạn nên nằm trong 1–3 lần nửa đời.
            if not np.isfinite(ratio):
                verdict = "không đo được"
            elif ratio < 1.0:
                verdict = "TS NGẮN hơn nửa đời — cắt trước khi kịp hồi"
            elif ratio <= 3.0:
                verdict = "trong khoảng 1–3× (chuẩn thường dùng)"
            else:
                verdict = "TS DÀI hơn 3× nửa đời"
            rows.append({"chân": spec.name, "ts": ts, "hl": hl, "tỷ lệ": ratio})
            print(f"{spec.name:22} {spec.signal_tf:>5} {w:9} {ts:10} "
                  f"{hl:9.1f} {ratio:7.2f}  {verdict}")
        except Exception as exc:
            print(f"{spec.name:22} LỖI {type(exc).__name__}: {str(exc)[:40]}")

    if rows:
        d = pd.DataFrame(rows)
        ok = d[(d["tỷ lệ"] >= 1.0) & (d["tỷ lệ"] <= 3.0)]
        short = d[d["tỷ lệ"] < 1.0]
        print()
        print(f"TỔNG KẾT: {len(ok)}/{len(d)} chân có time-stop trong khoảng 1–3× nửa đời")
        if len(short):
            print(f"  {len(short)} chân có time-stop NGẮN HƠN nửa đời: "
                  f"{', '.join(short['chân'].tolist())}")
            print("  → đây là ứng viên giải thích vì sao nhánh TIME-STOP thua "
                  "(35,4% winrate)")
        print(f"  Nửa đời trung vị: {d['hl'].median():.1f} nến · "
              f"tỷ lệ TS/HL trung vị: {d['tỷ lệ'].median():.2f}")

    print()
    print("⚠️ CHẨN ĐOÁN, KHÔNG PHẢI ĐỀ XUẤT. Nửa đời đo trên TOÀN chuỗi; nó không")
    print("   nói tốc độ hồi tại thời điểm VÀO LỆNH. Và bài phản chứng đã đo:")
    print("   nới time-stop ×1,5 và ×2,0 đều làm TỔNG lãi GIẢM — giữ lâu hơn thì")
    print("   bỏ lỡ lệnh kế tiếp. Nên nếu có sửa, phải sửa theo hướng khác chứ")
    print("   không phải kéo dài thời hạn.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
