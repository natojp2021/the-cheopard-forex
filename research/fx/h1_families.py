"""Vòng 65 — SĂN CHIẾN LƯỢC H1 bằng HỌ TÍN HIỆU KHÁC Z-BAND.

VÌ SAO PHẢI ĐỔI HỌ
==================
Bảy chân H1 hiện có: sáu chân Z-Band + `CrossMeanReversion`. Cả bảy đều đọc CÙNG MỘT
đại lượng — khoảng cách chuẩn hoá từ giá tới trung bình động của chính nó. Chúng khác
nhau ở công cụ và tham số, không khác ở CÁCH NHÌN thị trường.

Hệ quả đo được: `zb_audcad_h1 ↔ zb_audcad_m30` = 0,712, và phải gộp nhóm rủi ro để
danh mục không âm thầm nhân ba phơi nhiễm. Thêm chân Z-Band thứ tám không giải quyết
được gì — nó chỉ làm nhóm đã có dày thêm.

Cái danh mục thiếu là một họ đọc THỨ KHÁC. Năm họ dưới đây mỗi họ nhìn một đại lượng
riêng, và không họ nào dùng "giá cách trung bình bao xa":

    A. RANGE_BREAK   biên độ nến so với biên độ TRUNG BÌNH — đo mức MỞ RỘNG biến
                     động, không đo vị trí giá. Vào theo hướng nến mở rộng.
    B. RSI_DIV       phân kỳ giữa giá và RSI: giá lập đỉnh mới mà RSI không —
                     đại lượng là QUAN HỆ giữa hai chuỗi, không phải mức của một chuỗi.
    C. VOL_REGIME    σ ngắn hạn so với σ dài hạn. Cược vào biến động hồi quy, không
                     cược vào giá hồi quy. Hai thứ này thực nghiệm gần như trực giao.
    D. TIME_OF_DAY   lợi nhuận trung bình theo GIỜ trong ngày, ước lượng nhân quả.
                     Đại lượng là NHỊP LẶP, không phải mức giá.
    E. STREAK        chuỗi nến cùng chiều liên tiếp. Đại lượng là ĐẾM, miễn nhiễm
                     với độ lớn — nên nó không thể trùng với z-score về mặt cấu tạo.

CỔNG ĐẶT TRƯỚC — quan trọng hơn ở vòng này
===========================================
Ngoài các cổng thường lệ, thêm MỘT cổng riêng cho mục đích của vòng: ứng viên phải
có |tương quan| < 0,50 với MỌI chân H1 hiện có. Ngưỡng chặt hơn 0,70 thường dùng, vì
mục tiêu ở đây không phải "thêm một chân" mà là "thêm một CÁCH NHÌN". Một họ mới mà
tương quan 0,65 với z-band thì nó chỉ là z-band viết kiểu khác.

    FORM > 0 · OOS > 0 · ALL > 0,50 · t(net) > 2,0 · n >= 60
    · |corr| với mọi chân H1 < 0,50 · vùng tham số: đa số ô lân cận cùng dấu
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

from research.fx.trade_lab import load_crosses, load_majors

pd.set_option("display.width", 235, "display.max_columns", 30, "display.max_rows", 300)
FORM_END = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"


# ═══════════════════════════════════════════════════════ chỉ báo nền
def _atr(df: pd.DataFrame, n: int) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(),
                    (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    g = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))


def _shift(s: pd.Series) -> pd.Series:
    """Dịch một nến rồi ép bool — quyết định tại t chỉ dùng dữ liệu tới t−1."""
    return s.shift(1).astype("boolean").fillna(False).astype(bool)


# ═══════════════════════════════════════════════════════ năm họ tín hiệu
def sig_range_break(df: pd.DataFrame, n: int, k: float):
    """A · MỞ RỘNG BIÊN ĐỘ: nến có biên độ > k lần trung bình `n` nến.

    Đại lượng là ĐỘ RỘNG của nến, không phải vị trí giá. Vào THUẬN chiều nến mở
    rộng — giả thuyết: mở rộng biên độ báo hiệu dòng lệnh một chiều đang vào.
    """
    rng = (df["high"] - df["low"]) / df["close"]
    avg = rng.rolling(n, min_periods=n // 2).mean()
    strong = rng > k * avg
    rising = df["close"] > df["open"]
    return _shift(strong & rising), _shift(strong & ~rising)


def sig_rsi_div(df: pd.DataFrame, n: int, k: float):
    """B · PHÂN KỲ giá/RSI: giá lập cực trị mới mà RSI thì không.

    Đại lượng là QUAN HỆ giữa hai chuỗi. Giá cao hơn `n` nến trước nhưng RSI thấp
    hơn → đà đang yếu đi dù giá còn lên → vào NGƯỢC. `k` là khoảng cách RSI tối
    thiểu để coi là phân kỳ thật, chống nhiễu.
    """
    c, r = df["close"], _rsi(df["close"])
    price_high = c > c.rolling(n, min_periods=n // 2).max().shift(1)
    price_low = c < c.rolling(n, min_periods=n // 2).min().shift(1)
    rsi_weak = r < r.rolling(n, min_periods=n // 2).max().shift(1) - k
    rsi_strong = r > r.rolling(n, min_periods=n // 2).min().shift(1) + k
    return _shift(price_low & rsi_strong), _shift(price_high & rsi_weak)


def sig_vol_regime(df: pd.DataFrame, n: int, k: float):
    """C · CHẾ ĐỘ BIẾN ĐỘNG: σ ngắn hạn so với σ dài hạn.

    Cược vào việc BIẾN ĐỘNG hồi quy, không phải giá hồi quy. Khi σ ngắn vọt lên
    quá k lần σ dài, thị trường vừa có cú sốc — và sau cú sốc thì giá thường hồi
    một phần. Vào NGƯỢC chiều cú sốc.
    """
    r = np.log(df["close"]).diff()
    vol_short = r.rolling(max(n // 4, 3), min_periods=2).std()
    vol_long = r.rolling(n, min_periods=n // 2).std()
    soc = vol_short > k * vol_long
    falling = r.rolling(max(n // 4, 3), min_periods=2).sum() < 0
    return _shift(soc & falling), _shift(soc & ~falling)


def sig_time_of_day(df: pd.DataFrame, n: int, k: float):
    """D · NHỊP THEO GIỜ: lợi nhuận trung bình của ĐÚNG giờ này trong `n` ngày trước.

    Ước lượng HOÀN TOÀN nhân quả: chỉ dùng các ngày TRƯỚC ngày hiện tại, cùng chỉ
    số giờ. Vào theo dấu của nhịp khi độ lớn vượt `k` lần độ lệch chuẩn của nó.

    Giả thuyết: dòng tiền định kỳ (fix ngân hàng, mở/đóng phiên) để lại nhịp lặp.
    Bản trên CROSS ở vòng 54 thất bại nặng (Sharpe −11); bản này khác ở chỗ nó chạy
    trên TỪNG công cụ với ngưỡng độ lớn, không phải xếp hạng cắt ngang.
    """
    r = np.log(df["close"]).diff()
    hour = df.index.hour
    cadence = pd.Series(np.nan, index=df.index)
    deviation = pd.Series(np.nan, index=df.index)
    for h in range(24):
        m = hour == h
        if m.sum() < n + 5:
            continue
        s = r[m]
        cadence[m] = s.shift(1).rolling(n, min_periods=n // 2).mean()
        deviation[m] = s.shift(1).rolling(n, min_periods=n // 2).std()
    strong = cadence.abs() > k * deviation.replace(0, np.nan)
    return _shift(strong & (cadence > 0)), _shift(strong & (cadence < 0))


def sig_streak(df: pd.DataFrame, n: int, k: float):
    """E · CHUỖI NẾN cùng chiều: đếm bao nhiêu nến liên tiếp cùng dấu.

    Đại lượng là ĐẾM — miễn nhiễm hoàn toàn với độ lớn, nên về cấu tạo nó không thể
    trùng với z-score. Chuỗi đủ dài (`n` nến) → vào NGƯỢC, giả thuyết là chuỗi dài
    phản ánh dòng lệnh một chiều đã cạn.

    `k` lọc thêm theo biên độ: chỉ tính chuỗi mà tổng dịch chuyển vượt k lần ATR,
    để loại những chuỗi 5 nến toàn nến ruồi.
    """
    r = np.log(df["close"]).diff()
    sign = np.sign(r)
    streak = sign.groupby((sign != sign.shift()).cumsum()).cumcount() + 1
    atr = _atr(df, 14) / df["close"]
    total_move = r.rolling(n, min_periods=n).sum().abs()
    long_enough = (streak >= n) & (total_move > k * atr * np.sqrt(n))
    return _shift(long_enough & (sign < 0)), _shift(long_enough & (sign > 0))


FAMILIES = {
    "range_break": (sig_range_break, (10, 20, 40, 80), (1.5, 2.0, 2.5)),
    "rsi_div": (sig_rsi_div, (12, 24, 48, 96), (3.0, 6.0, 10.0)),
    "vol_regime": (sig_vol_regime, (24, 48, 96, 192), (1.3, 1.6, 2.0)),
    "time_of_day": (sig_time_of_day, (20, 40, 60), (1.0, 1.5, 2.0)),
    "streak": (sig_streak, (4, 5, 6, 8), (0.5, 1.0, 1.5)),
}


# ═══════════════════════════════════════════════════════ mô phỏng theo lệnh
def run(df: pd.DataFrame, cost: float, swap: float, buy, sell, ts_bars: int):
    """Một vị thế tại một thời điểm. Thoát khi tín hiệu ngược hoặc hết time-stop.

    KHÔNG có cắt lỗ theo giá — đo được hai lần (vòng 57 và 59) rằng SL theo ATR làm
    tệ hơn trên FX, và giữ đúng cơ chế thoát đó để so sánh công bằng với z-band.
    """
    o, c = df["open"].to_numpy(), df["close"].to_numpy()
    B, S = buy.to_numpy(), sell.to_numpy()
    n = len(df)
    rows = []
    i = 0
    while i < n - 1:
        side = 1 if B[i] else (-1 if S[i] else 0)
        if side == 0:
            i += 1
            continue
        entry = o[i]
        if not np.isfinite(entry) or entry <= 0:
            i += 1
            continue
        j = i
        while j < n - 1:
            j += 1
            if (side > 0 and S[j]) or (side < 0 and B[j]) or (j - i >= ts_bars):
                break
        bars = j - i
        gross = side * (c[j] - entry) / entry * 1e4
        rows.append({"entry_time": df.index[i], "exit_time": df.index[j],
                     "bars": bars, "gross_bps": gross,
                     "net_bps": gross - cost - bars * swap})
        i = j
    T = pd.DataFrame(rows)
    d = (T.set_index("exit_time")["net_bps"].resample("1D").sum().fillna(0.0)
         if not T.empty else pd.Series(dtype=float))
    return T, d


def sharpe(s: pd.Series, lo=None, hi=None) -> float:
    if lo is not None:
        s = s[s.index >= lo]
    if hi is not None:
        s = s[s.index < hi]
    sd = float(s.std(ddof=1))
    return float(s.mean()) / sd * np.sqrt(252) if sd > 0 and len(s) > 60 else np.nan


def main() -> None:
    t0 = time.time()
    diag = pd.read_csv(OUT / "breakeven_diag.csv")
    best = diag[(diag["tf"] == "H1") & (diag["biên"] > 0.8)]["công cụ"].tolist()
    univ = {i.name: i for i in (load_crosses("H1") + load_majors("H1"))}
    names = [n for n in best if n in univ]
    print(f"{len(names)} công cụ H1 có biên dương · {len(FAMILIES)} họ tín hiệu\n")

    rows: List[Dict] = []
    series: Dict[str, pd.Series] = {}
    for fam, (fn, Ns, Ks) in FAMILIES.items():
        for nm in names:
            ins = univ[nm]
            for N in Ns:
                for k in Ks:
                    for ts in (24, 96):
                        try:
                            b, s = fn(ins.df, N, k)
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
                            "họ": fam, "công cụ": nm, "N": N, "k": k, "ts": ts,
                            "ALL": round(sharpe(d), 3),
                            "FORM": round(sharpe(d, hi=FORM_END), 3),
                            "OOS": round(sharpe(d, lo=FORM_END), 3),
                            "n": len(T),
                            "thắng%": round(float((v > 0).mean()) * 100, 1),
                            "net": round(float(v.mean()), 2),
                            "t": round(float(v.mean()) / float(v.std(ddof=1))
                                       * np.sqrt(len(v)), 2),
                            "năm+": f"{int((yr > 0).sum())}/{len(yr)}"})
        print(f"  {fam} xong ({time.time() - t0:.0f}s)", flush=True)

    R = pd.DataFrame(rows)
    R.to_csv(OUT / "h1_families.csv", index=False)

    print()
    print("=" * 140)
    print("TỔNG QUAN THEO HỌ — họ nào có tín hiệu, họ nào không")
    print("=" * 140)
    g = R.groupby("họ").agg(
        n_ô=("ALL", "size"), ALL_tv=("ALL", "median"), ALL_max=("ALL", "max"),
        net_tv=("net", "median"), n_duong=("ALL", lambda x: int((x > 0).sum()))).round(3)
    g["%_dương"] = (g["n_duong"] / g["n_ô"] * 100).round(1)
    print(g.to_string())

    print()
    print("=" * 140)
    print("CỔNG: FORM>0 & OOS>0 & ALL>0,50 & t>2,0 & n>=60")
    print("=" * 140)
    k = R[(R["FORM"] > 0) & (R["OOS"] > 0) & (R["ALL"] > 0.50)
          & (R["t"] > 2.0) & (R["n"] >= 60)].sort_values("ALL", ascending=False)
    print(f"{len(k)}/{len(R)} ô qua cổng")
    print(k.head(25).to_string(index=False) if len(k) else "  KHÔNG CÓ")

    if len(k):
        print()
        print("=" * 140)
        print("CỔNG RIÊNG CỦA VÒNG NÀY: |corr| với MỌI chân H1 hiện có < 0,50")
        print("=" * 140)
        from src.python.strategies import portfolio as PF

        def day(s):
            s = s.copy()
            s.index = pd.DatetimeIndex(s.index).as_unit("ns").normalize()
            return s.groupby(s.index).sum()

        res = PF.backtest()
        h1_legs = {n: day(v) for n, v in res.legs.items()
                   if n.endswith("_h1") or n == "cross_h1"}
        for _, r in k.head(14).iterrows():
            key = f"{r['họ']}|{r['công cụ']}|N{r.N}|k{r.k}|ts{r.ts}"
            d = day(series[key])
            cors = {n: abs(float(pd.DataFrame({"a": d, "b": v}).fillna(0.0)
                                 .corr().iloc[0, 1])) for n, v in h1_legs.items()}
            mx = max(cors.values())
            print(f"  {key:44s} ALL {r.ALL:+.3f} · |corr| max {mx:.3f} "
                  f"({max(cors, key=cors.get)})  "
                  f"{'ĐỘC LẬP THẬT' if mx < 0.50 else 'trùng z-band'}")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
