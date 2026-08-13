# -*- coding: utf-8 -*-
"""Trọng số NGHỊCH ĐẢO BIẾN ĐỘNG thay vì đều theo notional — giảm MaxDD?

    .venv311\\Scripts\\python.exe research/fx/invvol_weights.py

VẤN ĐỀ ĐO ĐƯỢC
===============
`LEG_WEIGHTS` chia đều 21 nhóm rủi ro, đã gộp theo tương quan (ngưỡng 0,70). Nhưng
"đều" ở đây là đều theo NOTIONAL, không phải đều theo RỦI RO: chân biến động gấp
đôi chân khác mà nhận cùng tỷ trọng thì nó đóng góp gấp đôi vào phương sai danh mục.

Hệ quả cụ thể, đo trên 2026: `cross_h1` là chân đóng góp lớn nhất CẢ HAI chiều —
+3.835 bps trong 6 tháng, −2.513 bps riêng tháng 1. Tháng 1 lỗ −6,26% và chân này
gây gần hết. Một chân đuôi dày nhận cùng suất với chân hiền là chỗ MaxDD sinh ra.

CƠ SỞ KHOA HỌC — BỐN NGUỒN ĐỘC LẬP CÙNG MỘT LUẬT
=================================================
Moskowitz, Ooi & Pedersen · "Time Series Momentum" · JFE 104(2) 2012 · §2.4 (1):
    vị thế = σ_đích / σ_i,  σ_đích = 40%/năm,  σ ước lượng EWMA
    trọng tâm 60 ngày, DÙNG σ tại t−1 cho lợi nhuận tại t (chống nhìn trước)

Hurst, Ooi & Pedersen · "A Century of Evidence on Trend-Following" · AQR 2014 · §2:
    mỗi vị thế cùng MỨC BIẾN ĐỘNG; danh mục scale về vol ex-ante 10%/năm.
    Đo được: vol thực hiện 9,7% so với mục tiêu 10% (1880–2013)

Olszweski & Zhou · "Strategy diversification: Combining momentum and carry within
an FX portfolio" · J. Derivatives & Hedge Funds 19(4):311–320, 2014 · Bảng 4:
    vị thế tỷ lệ NGHỊCH ĐẢO độ lệch chuẩn cuộn 1 THÁNG (20 ngày giao dịch)
    | | Momentum | Carry | Equal-weight | MinVar |
    | MaxDD | −17,42% | −29,16% | **−8,95%** | **−8,41%** |
    | Sharpe | 0,79 | 0,63 | 0,98 | 0,97 |
    MinVar: κ = σ₂²/(σ₁²+σ₂²), 20 ngày đầu dùng equal-weight

Levy & Lopes · "Dynamic Momentum Learning" · §2 (3): EWMA δ = 0,97, σ_đích 40%/năm

Bốn bài, bốn rổ tài sản, bốn nhóm tác giả — cùng một kết luận. Đây không phải một
ý tưởng cần kiểm chứng lại từ đầu; nó là chuẩn ngành. Câu hỏi duy nhất còn lại là
nó có giúp ĐÚNG danh mục này không.

BA KỊCH BẢN
============
    ĐỀU        `LEG_WEIGHTS` hiện tại (mốc so sánh)
    INV-VOL 20 w_i ∝ 1/σ_i, σ = độ lệch chuẩn cuộn 20 ngày   (Olszweski)
    INV-VOL 60 w_i ∝ 1/σ_i, σ = độ lệch chuẩn cuộn 60 ngày   (MOP)

⚠️ CHỐNG NHÌN TRƯỚC — CHỖ DỄ SAI NHẤT CỦA CẢ BÀI
=================================================
σ dùng cho ngày t phải tính XONG trước khi ngày t bắt đầu. Quên `.shift(1)` ở đây
cho ra một hệ biết trước ngày nào sẽ biến động rồi tránh đúng ngày đó — MaxDD sẽ
đẹp một cách vô lý. Bài này `.shift(1)` và có kiểm tra khẳng định ở cuối.

Đây đúng lớp lỗi mà `tests/test_no_lookahead.py` sinh ra để bắt.
"""
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

from src.python.core.infra import ftmo  # noqa: E402
from src.python.execution import ftmo_leverage_policy as POL  # noqa: E402
from src.python.strategies import portfolio as PF  # noqa: E402

ACCOUNT = 100_000.0
HARD_ABS = ACCOUNT * (1 - ftmo.MAX_LOSS_HARD)
FLOOR_ABS = ACCOUNT * (1 - POL.DD_SELF_CAP)
START26 = pd.Timestamp("2026-01-01")
WINDOW = 252

# Sàn σ: chân vừa khởi động hoặc đứng im có σ ≈ 0 và 1/σ nổ ra vô cực, nuốt trọn
# danh mục. Sàn đặt ở phân vị 10 của chính chân đó — bằng dữ liệu, không phải hằng số.
SIGMA_FLOOR_Q = 0.10


def _inv_vol_weights(legs: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Ma trận trọng số nghịch đảo σ, CHUẨN HOÁ về tổng 1 mỗi ngày.

    `.shift(1)` là chỗ quyết định: σ của ngày t phải tính từ dữ liệu tới t−1. Không
    có nó thì trọng số biết trước biến động của chính ngày mình đang cân.
    """
    sigma = legs.rolling(lookback, min_periods=max(20, lookback // 3)).std(ddof=1)
    sigma = sigma.shift(1)
    # SÀN σ PHẢI NHÂN QUẢ. Bản đầu dùng `sigma.quantile(q)` trên TOÀN mẫu, và test
    # chống nhìn trước ở cuối file bắt được ngay: lệch trọng số 5,48e-01 khi cắt bỏ
    # dữ liệu tương lai. Một phân vị toàn mẫu là một con số của tương lai.
    #
    # Bản đúng: phân vị MỞ RỘNG — tại ngày t chỉ nhìn σ từ đầu mẫu tới t.
    floor = sigma.expanding(min_periods=60).quantile(SIGMA_FLOOR_Q)
    sigma = sigma.clip(lower=floor)
    inv = 1.0 / sigma
    # Chân chưa đủ dữ liệu → trọng số 0, KHÔNG phải trọng số đều: một chân chưa đo
    # được σ là một chân chưa biết rủi ro, và fail-closed nghĩa là để nó ngoài.
    inv = inv.where(np.isfinite(inv), 0.0)
    tot = inv.sum(axis=1)
    return inv.div(tot.where(tot > 0, np.nan), axis=0).fillna(0.0)


def _combine(legs: pd.DataFrame, w: pd.DataFrame | None,
             base: dict) -> pd.Series:
    """Chuỗi bps NGÀY của danh mục. `w=None` → dùng `LEG_WEIGHTS` cố định."""
    if w is None:
        ws = pd.Series({c: base.get(c, 0.0) for c in legs.columns})
        ws = ws / ws.sum()
        return (legs * ws).sum(axis=1)
    return (legs * w.reindex(columns=legs.columns).fillna(0.0)).sum(axis=1)


def _run(r: np.ndarray, start: int = 0, n: int | None = None) -> dict:
    """Mô phỏng equity dưới CHÍNH SÁCH đòn bẩy thật — cùng công thức mọi bài khác."""
    eq = peak = ACCOUNT
    mdd = worst = 0.0
    levs = []
    dead = cut = False
    end = len(r) if n is None else min(start + n, len(r))
    for x in r[start:end]:
        ds = eq
        d = POL.decide(eq, ds, 9.33, worst_day_bps=79.4)
        levs.append(d.leverage)
        eq *= (1.0 + float(x) * d.leverage / 1e4)
        day = (eq - ds) / ds
        worst = min(worst, day)
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak * 100.0)
        if eq <= HARD_ABS or day <= -ftmo.DAILY_LOSS_HARD:
            dead = True
            break
        if eq <= FLOOR_ABS or day <= -ftmo.DAILY_FLATTEN_REALIZED:
            cut = True
            break
    return {"equity": eq, "mdd": mdd, "worst": worst * 100.0, "dead": dead,
            "cut": cut, "lev": float(np.mean(levs)) if levs else 0.0}


def _windows(r: np.ndarray) -> dict:
    dead = cut = ok = 0
    for s in range(0, max(1, len(r) - WINDOW), 21):
        w = _run(r, start=s, n=WINDOW)
        dead += w["dead"]
        cut += (w["cut"] and not w["dead"])
        ok += (not w["dead"] and not w["cut"])
    t = max(dead + cut + ok, 1)
    return {"dead": dead / t * 100.0, "cut": cut / t * 100.0}


def main() -> int:
    print("Đang chạy backtest danh mục 27 chân… (~2 phút)")
    res = PF.backtest(start="2020-01-01")
    legs = pd.DataFrame({k: v for k, v in res.legs.items()}).dropna(how="all")
    legs = legs.fillna(0.0)
    print(f"  {len(legs)} ngày · {len(legs.columns)} chân")

    scen = {"ĐỀU (hiện tại)": None,
            "INV-VOL 20 ngày": _inv_vol_weights(legs, 20),
            "INV-VOL 60 ngày": _inv_vol_weights(legs, 60)}

    print(f"\n{'=' * 96}")
    print("TRỌNG SỐ NGHỊCH ĐẢO BIẾN ĐỘNG vs ĐỀU — chuẩn của MOP/AQR/Olszweski")
    print("=" * 96)
    print(f"{'kịch bản':18} | {'TOÀN MẪU 2020-2026':^34} | {'2026':^22} | "
          f"{'cửa sổ 252':^13}")
    print(f"{'':18} | {'số dư cuối':>12} {'MaxDD':>7} {'ngày':>6} {'lev':>5} | "
          f"{'lãi':>8} {'MaxDD':>7} {'ngày':>6} | {'CHẾT':>6} {'cắt':>5}")
    print("-" * 96)

    out = {}
    for name, w in scen.items():
        s = _combine(legs, w, PF.LEG_WEIGHTS).dropna()
        a = s.to_numpy()
        a26 = s[s.index >= START26].to_numpy()
        full, y26, wnd = _run(a), _run(a26), _windows(a)
        out[name] = {"full": full, "y26": y26, "wnd": wnd, "series": s}
        print(f"{name:18} | ${full['equity']:>11,.0f} {full['mdd']:6.2f}% "
              f"{full['worst']:5.2f}% {full['lev']:4.2f}x | "
              f"{(y26['equity'] - ACCOUNT) / ACCOUNT * 100:+7.2f}% "
              f"{y26['mdd']:6.2f}% {y26['worst']:5.2f}% | "
              f"{wnd['dead']:5.1f}% {wnd['cut']:4.1f}%")

    base = out["ĐỀU (hiện tại)"]
    print()
    print("CHÊNH LỆCH so với ĐỀU (điểm %)")
    for name in ("INV-VOL 20 ngày", "INV-VOL 60 ngày"):
        o = out[name]
        d26 = ((o["y26"]["equity"] - base["y26"]["equity"]) / ACCOUNT * 100.0)
        ddd = o["y26"]["mdd"] - base["y26"]["mdd"]
        dday = abs(o["full"]["worst"]) - abs(base["full"]["worst"])
        print(f"  {name:18} lãi 2026 {d26:+6.2f}đ% · MaxDD {ddd:+6.2f}đ% · "
              f"ngày tệ nhất toàn mẫu {dday:+.2f}đ%")

    # ── KIỂM TRA KHẲNG ĐỊNH: trọng số KHÔNG được biết tương lai.
    #
    # Ghim toàn bộ dữ liệu SAU một mốc cắt rồi đòi trọng số trước mốc đó không đổi.
    # Đây là kiểu test hành vi mà `tests/test_no_lookahead.py` dùng — nó bắt được
    # `.shift(1)` bị quên, thứ mà đọc mắt thường không thấy.
    cut = legs.index[len(legs) // 2]
    w_full = _inv_vol_weights(legs, 20)
    w_trunc = _inv_vol_weights(legs[legs.index <= cut], 20)
    common = w_trunc.index[w_trunc.index <= cut]
    diff = float((w_full.loc[common] - w_trunc.loc[common]).abs().to_numpy().max())
    print()
    print(f"KIỂM TRA NHÌN TRƯỚC: cắt tại {cut:%Y-%m-%d}, lệch trọng số tối đa "
          f"{diff:.2e}")
    print("  " + ("ĐẠT — trọng số không đổi khi bỏ dữ liệu tương lai"
                  if diff < 1e-12 else
                  "❌ HỎNG — trọng số ĐỔI khi thêm dữ liệu tương lai, có nhìn trước"))

    print()
    print("Đọc kết quả: MaxDD giảm mà lãi không giảm tương ứng thì đáng đổi. Lãi")
    print("giảm nhiều hơn MaxDD giảm thì không — trọng số đều đã là một lựa chọn")
    print("hợp lệ, và mỗi lớp tính toán thêm là một chỗ có thể hỏng lúc chạy thật.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
