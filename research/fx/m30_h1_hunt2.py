"""Vòng 67 — SĂN TIẾP H1 và M30: bốn họ MỚI NỮA + ba họ cũ mở sang M30.

TÌNH TRẠNG TRƯỚC VÒNG NÀY
=========================
    H1   11 chiến lược — 6 Z-Band · 2 Streak · 1 RSI-Div · 1 Vol-Regime · 1 CrossMR
    M30   3 chiến lược — TOÀN BỘ là Z-Band

M30 là chỗ mỏng nhất: cả ba chân đọc cùng một đại lượng, nên khung này chưa có đa
dạng hoá cách nhìn nào. Ba họ vừa chứng minh có tín hiệu ở H1 (rsi_div · streak ·
vol_regime) chưa từng chạy trên M30 — đó là chỗ rẻ nhất để tìm.

BỐN HỌ MỚI HOÀN TOÀN — mỗi họ đọc một đại lượng chưa ai đọc
============================================================
  F. GAP_FADE     KHOẢNG HỞ giữa đóng cửa nến trước và mở cửa nến này, chuẩn hoá
                  theo ATR. Đại lượng là ĐỨT GÃY giá, không phải mức hay xu hướng.
                  Vào NGƯỢC chiều hở — giả thuyết: hở là mất cân bằng thanh khoản
                  tức thời, không phải thông tin mới.

  G. CLOSE_LOC    VỊ TRÍ ĐÓNG CỬA trong biên độ nến: (close − low)/(high − low).
                  Gần 1 = phe mua thắng cả nến; gần 0 = phe bán. Đại lượng NỘI TẠI
                  một nến, không so với nến nào khác — khác hẳn mọi họ đã thử.

  H. ACCEL        GIA TỐC giá: hiệu của hai lợi nhuận liên tiếp cùng cửa sổ. Đo
                  đà đang MẠNH LÊN hay CHẬM LẠI, tức đạo hàm bậc hai — trong khi
                  mọi họ trước đo bậc không (mức) hoặc bậc một (đà).

  I. HL_RANGE     BIÊN ĐỘ high-low so với biên độ trung bình, nhưng vào NGƯỢC chiều
                  (khác `range_break` đã bị loại vốn vào THUẬN chiều). Cùng một đại
                  lượng, ngược dấu — và 65 vòng cho thấy trên FX chỉ chiều ngược sống.

CỔNG — như mọi vòng, đặt trước và không nới
============================================
    FORM > 0 · OOS > 0 · ALL > 0,50 · t(net) > 2,0 · n >= 60
    · |corr| với MỌI chân cùng khung < 0,50
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

from research.fx.h1_families import _atr, _shift, run, sharpe
from research.fx.trade_lab import load_crosses, load_majors
from src.python.strategies import signal_families as SF

pd.set_option("display.width", 235, "display.max_columns", 30, "display.max_rows", 300)
FORM_END = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"


# ═══════════════════════════════════════════════════════ bốn họ mới
def sig_gap_fade(df: pd.DataFrame, n: int, k: float):
    """F · KHOẢNG HỞ: mở cửa lệch khỏi đóng cửa trước quá k lần ATR → vào NGƯỢC.

    Đại lượng là ĐỨT GÃY giá giữa hai nến, không phải mức hay xu hướng. Trên FX
    khoảng hở trong phiên hiếm và nhỏ, nên nó gần như luôn là mất cân bằng thanh
    khoản tức thời chứ không phải thông tin mới — và mất cân bằng thì hồi.
    """
    ho = (df["open"] - df["close"].shift(1)) / df["close"].shift(1)
    a = _atr(df, n) / df["close"]
    big = ho.abs() > k * a
    return _shift(big & (ho < 0)), _shift(big & (ho > 0))


def sig_close_loc(df: pd.DataFrame, n: int, k: float):
    """G · VỊ TRÍ ĐÓNG CỬA trong biên độ nến, làm mượt `n` nến.

    (close − low)/(high − low): gần 1 = phe mua thắng trọn nến, gần 0 = phe bán.
    Đại lượng NỘI TẠI một nến — không so với trung bình, không so với nến khác.

    Trung bình `n` nến vượt k (hoặc dưới 1−k) → một phe đã thắng liên tục → vào
    NGƯỢC, cùng giả thuyết "dòng lệnh một chiều đã cạn" của họ streak nhưng đo bằng
    đại lượng liên tục thay vì phép đếm.
    """
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    loc = ((df["close"] - df["low"]) / rng).rolling(n, min_periods=n // 2).mean()
    return _shift(loc < 1.0 - k), _shift(loc > k)


def sig_accel(df: pd.DataFrame, n: int, k: float):
    """H · GIA TỐC: hiệu hai lợi nhuận `n` nến liên tiếp, chuẩn hoá theo σ.

    Đạo hàm bậc HAI của giá. Mọi họ trước đo bậc không (giá cách trung bình bao xa)
    hoặc bậc một (đà). Gia tốc âm mạnh nghĩa là đà đang tắt nhanh — vào NGƯỢC chiều
    đà đang tắt, tức thuận chiều lực mới.
    """
    lp = np.log(df["close"])
    r = lp - lp.shift(n)
    gt = r - r.shift(n)
    sd = gt.rolling(n * 4, min_periods=n * 2).std()
    z = gt / sd.replace(0, np.nan)
    return _shift(z < -k), _shift(z > k)


def sig_hl_range(df: pd.DataFrame, n: int, k: float):
    """I · BIÊN ĐỘ high-low quá rộng → vào NGƯỢC chiều nến.

    Cùng đại lượng với `range_break` (đã bị loại) nhưng NGƯỢC dấu. Giữ lại phép đo
    và đảo chiều là có cơ sở: 65 vòng trên FX cho thấy mọi hướng THUẬN chiều đều
    thua, chỉ hồi quy sống. Nếu bản ngược cũng thua thì đại lượng này vô dụng ở cả
    hai chiều — và đó cũng là một kết luận đáng ghi.
    """
    rng = (df["high"] - df["low"]) / df["close"]
    avg = rng.rolling(n, min_periods=n // 2).mean()
    wide = rng > k * avg
    rising = df["close"] > df["open"]
    return _shift(wide & rising), _shift(wide & ~rising)


NEW_FAM = {
    "gap_fade": (sig_gap_fade, (14, 24, 48), (0.3, 0.5, 0.8)),
    "close_loc": (sig_close_loc, (5, 10, 20, 40), (0.62, 0.68, 0.75)),
    "accel": (sig_accel, (12, 24, 48, 96), (1.5, 2.0, 2.5)),
    "hl_range": (sig_hl_range, (10, 20, 40, 80), (1.5, 2.0, 2.5)),
}
# ba họ ĐÃ chứng minh ở H1 — mở sang M30
OLD_FAM = {
    "rsi_div": (SF.sig_rsi_div, (24, 48, 96, 192), (3.0, 6.0, 10.0)),
    "streak": (SF.sig_streak, (4, 5, 6, 8), (0.5, 1.0, 1.5)),
    "vol_regime": (SF.sig_vol_regime, (48, 96, 192), (1.3, 1.6, 2.0)),
}


def _bs(fn, df, N, k):
    """Gọi hàm tín hiệu, chuẩn hoá về (mua, bán) — họ cũ trả thêm giá trị."""
    out = fn(df, N, k)
    return (out[0], out[1]) if len(out) >= 2 else out


def scan_grid(tf: str, fams: Dict, univ: Dict, names: List[str],
         ts_list: Tuple[int, ...]) -> Tuple[pd.DataFrame, Dict[str, pd.Series]]:
    rows, series = [], {}
    for fam, (fn, Ns, Ks) in fams.items():
        for nm in names:
            ins = univ[nm]
            for N in Ns:
                for k in Ks:
                    for ts in ts_list:
                        try:
                            b, s = _bs(fn, ins.df, N, k)
                        except Exception:
                            continue
                        T, d = run(ins.df, ins.cost_1rt_bps, ins.swap_bps_per_bar,
                                   b, s, ts)
                        if T.empty or len(T) < 50:
                            continue
                        v = T["net_bps"]
                        yr = d.groupby(d.index.year).sum()
                        key = f"{fam}|{nm}|N{N}|k{k}|ts{ts}"
                        series[key] = d
                        rows.append({
                            "tf": tf, "họ": fam, "công cụ": nm, "N": N, "k": k,
                            "ts": ts, "ALL": round(sharpe(d), 3),
                            "FORM": round(sharpe(d, hi=FORM_END), 3),
                            "OOS": round(sharpe(d, lo=FORM_END), 3), "n": len(T),
                            "thắng%": round(float((v > 0).mean()) * 100, 1),
                            "net": round(float(v.mean()), 2),
                            "t": round(float(v.mean()) / float(v.std(ddof=1))
                                       * np.sqrt(len(v)), 2),
                            "năm+": f"{int((yr > 0).sum())}/{len(yr)}"})
        print(f"   {tf}·{fam} xong", flush=True)
    return pd.DataFrame(rows), series


def main() -> None:
    t0 = time.time()
    diag = pd.read_csv(OUT / "breakeven_diag.csv")
    allR, allS = [], {}

    for tf, fams, ts_list in (("H1", NEW_FAM, (24, 96)),
                              ("M30", {**NEW_FAM, **OLD_FAM}, (48, 192))):
        best = diag[(diag["tf"] == tf) & (diag["biên"] > 0.8)]["công cụ"].tolist()
        univ = {i.name: i for i in (load_crosses(tf) + load_majors(tf))}
        names = [n for n in best if n in univ]
        print(f"── {tf}: {len(names)} công cụ · {len(fams)} họ", flush=True)
        R, S = scan_grid(tf, fams, univ, names, ts_list)
        allR.append(R)
        allS.update({f"{tf}|{k}": v for k, v in S.items()})

    R = pd.concat(allR, ignore_index=True)
    R.to_csv(OUT / "m30_h1_hunt2.csv", index=False)

    print()
    print("=" * 145)
    print("TỔNG QUAN THEO HỌ × KHUNG")
    print("=" * 145)
    g = R.groupby(["họ", "tf"]).agg(
        n_ô=("ALL", "size"), ALL_tv=("ALL", "median"), ALL_max=("ALL", "max"),
        net_tv=("net", "median"),
        n_duong=("ALL", lambda x: int((x > 0).sum()))).round(3)
    g["%dương"] = (g["n_duong"] / g["n_ô"] * 100).round(1)
    print(g.to_string())

    print()
    print("=" * 145)
    print("CỔNG: FORM>0 & OOS>0 & ALL>0,50 & t>2,0 & n>=60")
    print("=" * 145)
    k = R[(R["FORM"] > 0) & (R["OOS"] > 0) & (R["ALL"] > 0.50)
          & (R["t"] > 2.0) & (R["n"] >= 60)].sort_values("ALL", ascending=False)
    print(f"{len(k)}/{len(R)} ô qua cổng")
    print(k.head(30).to_string(index=False) if len(k) else "  KHÔNG CÓ")

    if len(k):
        print()
        print("=" * 145)
        print("ĐỘC LẬP — |corr| với MỌI chân CÙNG KHUNG hiện có (ngưỡng 0,50)")
        print("=" * 145)
        from src.python.strategies import portfolio as PF

        def day(s):
            s = s.copy()
            s.index = pd.DatetimeIndex(s.index).as_unit("ns").normalize()
            return s.groupby(s.index).sum()

        res = PF.backtest()
        legs = {n: day(v) for n, v in res.legs.items()}
        for _, r in k.head(18).iterrows():
            key = f"{r.tf}|{r['họ']}|{r['công cụ']}|N{r.N}|k{r.k}|ts{r.ts}"
            d = day(allS[key])
            tail = "_h1" if r.tf == "H1" else "_m30"
            same = {n: v for n, v in legs.items() if n.endswith(tail) or n == "cross_h1"}
            cors = {n: abs(float(pd.DataFrame({"a": d, "b": v}).fillna(0.0)
                                 .corr().iloc[0, 1])) for n, v in same.items()}
            mx = max(cors.values()) if cors else 0.0
            print(f"  {key:46s} ALL {r.ALL:+.3f} · |corr| max {mx:.3f}  "
                  f"{'ĐỘC LẬP' if mx < 0.50 else 'TRÙNG'}")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
