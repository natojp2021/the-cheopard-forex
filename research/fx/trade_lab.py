"""Vòng 57 — LAB CHIẾN LƯỢC THEO LỆNH: entry giá · SL · TP · time-stop cụ thể.

VÌ SAO ĐỔI HẲN CƠ CHẾ
=====================
56 vòng trước đo chiến lược TỶ TRỌNG: "hôm nay nắm 0,14 EURGBP". Dạng đó không có
"vào tại giá nào, cắt lỗ ở đâu, chốt lời ở đâu" — nên không viết được bộ quy tắc vào
lệnh kiểu `XAU-R H1`, và không kiểm soát được rủi ro TỪNG LỆNH.

Lab này đo chiến lược THEO LỆNH, và nó KHÔNG phải cùng bài toán đổi cách trình bày.
SL/TP thay đổi phân phối lợi nhuận về mặt cấu trúc:

    không SL/TP   lợi nhuận mỗi lệnh ≈ phân phối tự nhiên của công cụ
    có SL/TP      đuôi trái bị CẮT ở −1R, đuôi phải bị cắt ở +mR

Với chiến lược hồi quy trung bình, cắt đuôi trái là bất lợi (spread căng nhất đúng
lúc sắp hồi) — Zheng Nan đo được time-stop hơn stop 3σ **+85%**. Với chiến lược đà,
cắt đuôi trái là có lợi. Nên cùng một tín hiệu, thêm SL có thể đảo dấu kết quả. Đó là
lý do phải đo lại từ đầu chứ không suy ra từ các vòng trước.

TÁM HỌ TÍN HIỆU VÀO LỆNH — mỗi họ có ngưỡng số cụ thể
======================================================
    zband       |z(N)| > k, nến trước còn ngoài dải          → ngược chiều lệch
    rsi_ext     RSI(14) < 30 hoặc > 70, thoát khi về 50       → ngược chiều
    bb_pierce   đóng cửa ngoài Bollinger(20, 2σ)              → ngược chiều
    donchian    phá kênh N nến                                 → thuận chiều
    squeeze     BandWidth < phân vị 20 rồi phá kênh 20         → thuận chiều
    range_exp   nến biên độ < phân vị 15 rồi nến sau phá       → thuận chiều
    pullback    EMA50 > EMA200, giá hồi về EMA20 ± 0,5 ATR    → thuận chiều
    session_br  phá biên độ phiên Á trong giờ London          → thuận chiều

BỐN CẤU HÌNH THOÁT — tổ hợp với mọi họ
=======================================
    sl_tp_2R    SL = 1,5 ATR · TP = 2,0 R · time-stop 3× cửa sổ tín hiệu
    sl_tp_3R    SL = 1,5 ATR · TP = 3,0 R · time-stop 3× cửa sổ
    sl_be_3R    SL = 1,5 ATR · BE tại +1,0R · TP = 3,0 R
    time_only   KHÔNG SL · thoát khi tín hiệu ngược hoặc hết time-stop

Cấu hình `time_only` có mặt để đo trực tiếp giả thuyết Zheng Nan trên dữ liệu này:
nếu nó thắng ba cấu hình có SL trên họ hồi quy, kết luận của ông ấy tái lập được.

CHI PHÍ: mỗi lệnh trả một lượt khứ hồi đầy đủ (spread + commission) cộng swap mỗi đêm
giữ. Không có ngoại lệ, không có "giả định khớp giữa spread".
"""
from __future__ import annotations

import io
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import numpy as np
import pandas as pd

from src.python.research import fx_cross_pairs as CP
from src.python.shared import asset_profile as AP
from src.python.shared import carry_costs as CC
from src.python.shared import fx_data as D

pd.set_option("display.width", 260, "display.max_columns", 40, "display.max_rows", 400)
FORM_END = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"
BARS_DAY = {"M30": 48, "H1": 24, "H4": 6}
BAR_HOURS = {"M30": 0.5, "H1": 1.0, "H4": 4.0}


# ═══════════════════════════════════════════════════════ dữ liệu
@dataclass
class Instrument:
    """Một công cụ giao dịch được: OHLC + chi phí thật của nó."""
    name: str
    tf: str
    df: pd.DataFrame                  # open high low close
    cost_1rt_bps: float               # spread + commission, một lượt khứ hồi
    swap_bps_per_bar: float


def load_majors(tf: str, start: str = "2020-01-01",
                broker_markup_pct: float = 1.0) -> List[Instrument]:
    out = []
    for sym in AP.FX_ALL:
        b = D.build_bars(D.load_m1(sym), tf)
        b = b[b.index >= start]
        px = float(b["close"].median())
        prof = AP.get(sym)
        cost = (float(b["spread_usd"].median())
                + prof.commission_price_units(px)) / px * 1e4
        swap = (CC.SWAP_CALENDAR_MULTIPLIER * broker_markup_pct / 365.0 * 100.0
                * BAR_HOURS[tf] / 24.0)
        out.append(Instrument(sym, tf, b[["open", "high", "low", "close"]],
                              cost, swap))
    return out


def load_crosses(tf: str, start: str = "2020-01-01",
                 broker_markup_pct: float = 1.0) -> List[Instrument]:
    """Cross tổng hợp — OHLC dựng từ hai chân major theo đúng định nghĩa của SSOT.

    High/low của cross KHÔNG bằng tỷ số high/low của hai chân (hai chân không đạt
    cực trị cùng lúc). Xấp xỉ bảo thủ: dùng biên độ của chân biến động hơn, cộng lại
    theo căn bậc hai — nếu xấp xỉ này sai thì nó sai theo hướng làm SL dễ chạm hơn
    thực tế, tức kết quả bi quan hơn thực tế.
    """
    base = {}
    for sym in AP.FX_ALL:
        b = D.build_bars(D.load_m1(sym), tf)
        base[sym] = b[b.index >= start]
    idx = None
    for b in base.values():
        idx = b.index if idx is None else idx.intersection(b.index)

    out = []
    swap = (CC.SWAP_CALENDAR_MULTIPLIER * broker_markup_pct / 365.0 * 100.0
            * BAR_HOURS[tf] / 24.0) * 2.0            # cross = HAI chân, swap gấp đôi
    for name, a, b_, how in CP.CROSS_DEFS:
        pa, pb = base[a].loc[idx], base[b_].loc[idx]
        # "mult" nhân, "ratio"/"inv" chia — DÙNG CHUNG công thức chia, xem
        # `fx_cross_pairs` §dựng giá. Bỏ qua nhánh `how` cho ra giá sai bậc độ lớn
        # và chi phí quy theo bps phồng lên hàng nghìn.
        if how == "mult":
            c = pa["close"] * pb["close"]
            o = pa["open"] * pb["open"]
        else:
            c = pa["close"] / pb["close"]
            o = pa["open"] / pb["open"]
        # biên độ tương đối của từng chân, gộp theo căn bậc hai của tổng bình phương
        ra = (pa["high"] - pa["low"]) / pa["close"]
        rb = (pb["high"] - pb["low"]) / pb["close"]
        rr = np.sqrt(ra ** 2 + rb ** 2)
        mid = (o + c) / 2.0
        df = pd.DataFrame({
            "open": o, "close": c,
            "high": np.maximum(o, c) + mid * rr / 2.0,
            "low": np.minimum(o, c) - mid * rr / 2.0}, index=idx)
        sp = CP.spread_pips(name)      # đo thật × hệ số an toàn
        pip = 0.01 if name.endswith("JPY") else 0.0001
        cost = sp * pip / float(c.median()) * 1e4
        out.append(Instrument(name, tf, df, cost, swap))
    return out


# ═══════════════════════════════════════════════════════ chỉ báo
def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(),
                    (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    g = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))


# ═══════════════════════════════════════════════════════ tám họ tín hiệu
# Mỗi hàm trả (entry_long, entry_short, window) — window dùng cho time-stop.
def _shifted(s: pd.Series) -> pd.Series:
    """Dịch một nến rồi ép kiểu bool. Ép kiểu TRƯỚC fillna vì `shift` trên chuỗi bool
    sinh mảng object có NaN, và fillna trên object phát FutureWarning ở pandas 3."""
    return s.shift(1).astype("boolean").fillna(False).astype(bool)


def sig_zband(df: pd.DataFrame, n: int = 48, k: float = 2.0):
    c = np.log(df["close"])
    mu = c.rolling(n, min_periods=n // 2).mean()
    sd = c.rolling(n, min_periods=n // 2).std(ddof=1)
    z = (c - mu) / sd.replace(0, np.nan)
    prev_out = (z.shift(1).abs() > k)
    el = (z < -k) & prev_out
    es = (z > k) & prev_out
    return _shifted(el), _shifted(es), n


def sig_rsi_ext(df: pd.DataFrame, lo: float = 30.0, hi: float = 70.0):
    r = _rsi(df["close"])
    el = (r < lo) & (r.shift(1) >= lo)
    es = (r > hi) & (r.shift(1) <= hi)
    return _shifted(el), _shifted(es), 48


def sig_bb_pierce(df: pd.DataFrame, n: int = 20, k: float = 2.0):
    c = df["close"]
    ma = c.rolling(n, min_periods=n // 2).mean()
    sd = c.rolling(n, min_periods=n // 2).std(ddof=1)
    el = c < ma - k * sd
    es = c > ma + k * sd
    return _shifted(el), _shifted(es), n * 2


def sig_donchian(df: pd.DataFrame, n: int = 55):
    hi = df["high"].rolling(n, min_periods=n // 2).max()
    lo = df["low"].rolling(n, min_periods=n // 2).min()
    el = df["close"] >= hi
    es = df["close"] <= lo
    return _shifted(el), _shifted(es), n


def sig_squeeze(df: pd.DataFrame, n: int = 20, look: int = 100):
    c = df["close"]
    ma = c.rolling(n, min_periods=n // 2).mean()
    sd = c.rolling(n, min_periods=n // 2).std(ddof=1)
    bw = (4 * sd) / ma.replace(0, np.nan)
    tight = bw <= bw.rolling(look, min_periods=look // 2).quantile(0.20)
    hi = df["high"].rolling(n, min_periods=n // 2).max()
    lo = df["low"].rolling(n, min_periods=n // 2).min()
    el = tight.shift(1).fillna(False) & (c >= hi)
    es = tight.shift(1).fillna(False) & (c <= lo)
    return _shifted(el), _shifted(es), n * 2


def sig_range_exp(df: pd.DataFrame, look: int = 50):
    rng = (df["high"] - df["low"]) / df["close"]
    narrow = rng <= rng.rolling(look, min_periods=look // 2).quantile(0.15)
    el = narrow.shift(1).fillna(False) & (df["close"] > df["high"].shift(1))
    es = narrow.shift(1).fillna(False) & (df["close"] < df["low"].shift(1))
    return _shifted(el), _shifted(es), 24


def sig_pullback(df: pd.DataFrame):
    c = df["close"]
    e20 = c.ewm(span=20, adjust=False).mean()
    e50 = c.ewm(span=50, adjust=False).mean()
    e200 = c.ewm(span=200, adjust=False).mean()
    atr = _atr(df)
    near = (c - e20).abs() < 0.5 * atr
    el = (e50 > e200) & near
    es = (e50 < e200) & near
    return _shifted(el), _shifted(es), 48


def sig_session_break(df: pd.DataFrame):
    """Phá biên độ phiên Á (00-07 UTC) trong giờ London (07-12 UTC).

    Biên độ phiên Á tính trên các nến ĐÃ ĐÓNG của chính ngày hôm đó — nhân quả.
    """
    h = df.index.hour
    asia = (h >= 0) & (h < 7)
    day = df.index.normalize()
    hi_asia = df["high"].where(asia).groupby(day).cummax().groupby(day).ffill()
    lo_asia = df["low"].where(asia).groupby(day).cummin().groupby(day).ffill()
    big = (h >= 7) & (h < 12)
    el = pd.Series(big, index=df.index) & (df["close"] > hi_asia)
    es = pd.Series(big, index=df.index) & (df["close"] < lo_asia)
    return _shifted(el), _shifted(es), 24


FAMILIES: Dict[str, Callable] = {
    "zband": sig_zband, "rsi_ext": sig_rsi_ext, "bb_pierce": sig_bb_pierce,
    "donchian": sig_donchian, "squeeze": sig_squeeze, "range_exp": sig_range_exp,
    "pullback": sig_pullback, "session_br": sig_session_break,
}
MEAN_REVERTING = {"zband", "rsi_ext", "bb_pierce"}


# ═══════════════════════════════════════════════════════ bốn cấu hình thoát
@dataclass(frozen=True)
class ExitCfg:
    name: str
    sl_atr: Optional[float]           # None = không có SL
    tp_r: Optional[float]             # bội số R
    be_r: Optional[float]             # dời SL về hoà vốn tại +xR
    timestop_mult: float              # × cửa sổ tín hiệu


EXITS: Tuple[ExitCfg, ...] = (
    ExitCfg("sl_tp_2R", 1.5, 2.0, None, 3.0),
    ExitCfg("sl_tp_3R", 1.5, 3.0, None, 3.0),
    ExitCfg("sl_be_3R", 1.5, 3.0, 1.0, 3.0),
    ExitCfg("time_only", None, None, None, 3.0),
)


@dataclass
class TradeResult:
    trades: pd.DataFrame
    pnl_daily: pd.Series


def run_trades(ins: Instrument, el: pd.Series, es: pd.Series, window: int,
               cfg: ExitCfg) -> TradeResult:
    """Mô phỏng theo LỆNH: một vị thế tại một thời điểm, thoát theo SL/TP/time-stop.

    SL và TP kiểm tra trên high/low của nến — nếu cả hai bị chạm trong CÙNG một nến
    thì tính là chạm SL. Đây là giả định bi quan có chủ ý: không biết thứ tự trong
    nến, và giả định lạc quan ở đây là cách kinh điển để backtest đẹp hơn thực tế.
    """
    df = ins.df
    o = df["open"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()
    atr = _atr(df).to_numpy()
    ELv, ESv = el.to_numpy(), es.to_numpy()
    n = len(df)
    ts = max(int(window * cfg.timestop_mult), 2)

    rows = []
    i = 0
    while i < n - 1:
        side = 1 if ELv[i] else (-1 if ESv[i] else 0)
        if side == 0 or not np.isfinite(atr[i]) or atr[i] <= 0:
            i += 1
            continue
        entry = o[i + 1]                            # khớp ở MỞ CỬA nến kế — không nhìn trước
        if not np.isfinite(entry) or entry <= 0:
            i += 1
            continue
        a = atr[i]
        sl = (entry - side * cfg.sl_atr * a) if cfg.sl_atr else None
        r_unit = abs(entry - sl) if sl is not None else cfg.timestop_mult * a
        tp = (entry + side * cfg.tp_r * r_unit) if cfg.tp_r else None
        moved_be = False

        j = i + 1
        exit_px, reason = None, ""
        while j < n:
            if sl is not None:
                hit_sl = (l[j] <= sl) if side > 0 else (h[j] >= sl)
                if hit_sl:
                    exit_px, reason = sl, ("BE" if moved_be else "SL")
                    break
            if tp is not None:
                hit_tp = (h[j] >= tp) if side > 0 else (l[j] <= tp)
                if hit_tp:
                    exit_px, reason = tp, "TP"
                    break
            if cfg.be_r is not None and not moved_be and sl is not None:
                prog = (h[j] - entry) if side > 0 else (entry - l[j])
                if prog >= cfg.be_r * r_unit:
                    sl, moved_be = entry, True
            if (side > 0 and ESv[j]) or (side < 0 and ELv[j]):
                exit_px, reason = c[j], "REVERSE"
                break
            if j - i >= ts:
                exit_px, reason = c[j], "TIMESTOP"
                break
            j += 1
        if exit_px is None:
            exit_px, reason, j = c[n - 1], "EOD", n - 1

        bars = j - i
        gross = side * (exit_px - entry) / entry * 1e4
        cost = ins.cost_1rt_bps + bars * ins.swap_bps_per_bar
        rows.append({"entry_time": df.index[i + 1], "exit_time": df.index[j],
                     "side": side, "bars": bars, "reason": reason,
                     "gross_bps": gross, "cost_bps": cost,
                     "net_bps": gross - cost,
                     "r_multiple": (gross - cost) / max(r_unit / entry * 1e4, 1e-9)})
        i = j                                        # không chồng lệnh

    T = pd.DataFrame(rows)
    if T.empty:
        return TradeResult(T, pd.Series(dtype=float))
    daily = T.set_index("exit_time")["net_bps"].resample("1D").sum().fillna(0.0)
    return TradeResult(T, daily)


def sharpe(s: pd.Series, lo=None, hi=None) -> float:
    if lo is not None:
        s = s[s.index >= lo]
    if hi is not None:
        s = s[s.index < hi]
    sd = float(s.std(ddof=1))
    return float(s.mean()) / sd * np.sqrt(252) if sd > 0 and len(s) > 60 else np.nan


def main() -> None:
    t0 = time.time()
    rows: List[Dict] = []
    for tf in ("H1", "M30"):
        universe = load_crosses(tf) + load_majors(tf)
        print(f"── {tf}: {len(universe)} công cụ × {len(FAMILIES)} họ × "
              f"{len(EXITS)} cấu hình thoát", flush=True)
        for fam_name, fam in FAMILIES.items():
            for cfg in EXITS:
                pnl, n_tr, wins, gross, cost = [], 0, 0, 0.0, 0.0
                per_ins = {}
                for ins in universe:
                    el, es, w = fam(ins.df)
                    res = run_trades(ins, el, es, w, cfg)
                    if res.trades.empty:
                        continue
                    per_ins[ins.name] = res.pnl_daily
                    n_tr += len(res.trades)
                    wins += int((res.trades["net_bps"] > 0).sum())
                    gross += float(res.trades["gross_bps"].sum())
                    cost += float(res.trades["cost_bps"].sum())
                if not per_ins:
                    continue
                P = pd.DataFrame(per_ins).fillna(0.0)
                d = P.mean(axis=1)                   # chia đều giữa các công cụ
                rows.append({
                    "tf": tf, "family": fam_name, "exit": cfg.name,
                    "ALL": round(sharpe(d), 3),
                    "FORM": round(sharpe(d, hi=FORM_END), 3),
                    "OOS": round(sharpe(d, lo=FORM_END), 3),
                    "n_lệnh": n_tr,
                    "thắng%": round(wins / max(n_tr, 1) * 100, 1),
                    "gross/lệnh": round(gross / max(n_tr, 1), 2),
                    "phí/lệnh": round(cost / max(n_tr, 1), 2),
                    "net/lệnh": round((gross - cost) / max(n_tr, 1), 2),
                    "n_cụ": len(per_ins)})
            print(f"   {fam_name} xong ({time.time() - t0:.0f}s)", flush=True)

    T = pd.DataFrame(rows)
    T.to_csv(OUT / "trade_lab.csv", index=False)

    print()
    print("=" * 140)
    print("KẾT QUẢ — 30 ô tốt nhất")
    print("=" * 140)
    print(T.sort_values("ALL", ascending=False).head(30).to_string(index=False))

    print()
    print("=" * 140)
    print("SO SÁNH CẤU HÌNH THOÁT trên họ HỒI QUY — kiểm định Zheng Nan (time-stop "
          "hơn stop giá +85%)")
    print("=" * 140)
    mr = T[T["family"].isin(MEAN_REVERTING)]
    print(mr.groupby(["exit", "tf"]).agg(
        ALL_med=("ALL", "median"), OOS_med=("OOS", "median"),
        net_med=("net/lệnh", "median"), thắng=("thắng%", "median")).round(3).to_string())

    print()
    print("── và trên họ THUẬN CHIỀU (kỳ vọng ngược lại: SL có lợi)")
    tr = T[~T["family"].isin(MEAN_REVERTING)]
    print(tr.groupby(["exit", "tf"]).agg(
        ALL_med=("ALL", "median"), OOS_med=("OOS", "median"),
        net_med=("net/lệnh", "median"), thắng=("thắng%", "median")).round(3).to_string())

    print()
    print("=" * 140)
    print("CỔNG: FORM>0 & OOS>0 & ALL>0,40 & net/lệnh>0")
    print("=" * 140)
    k = T[(T["FORM"] > 0) & (T["OOS"] > 0) & (T["ALL"] > 0.40)
          & (T["net/lệnh"] > 0)].sort_values("ALL", ascending=False)
    print(k.to_string(index=False) if len(k) else "  KHÔNG CÓ")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
