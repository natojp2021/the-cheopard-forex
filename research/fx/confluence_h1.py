"""Vòng 48 — HỢP LƯU ĐA ĐIỀU KIỆN (confluence), khung H1/M30.

NGUỒN: `project-refer/freqtrade-strategies/user_data/strategies` (người dùng chỉ ra).
Bốn luật được trích NGUYÊN VĂN, không tinh chỉnh trước khi đo:

  HLHB (`hlhb.py` — babypips, viết RIÊNG cho forex):
      long  = RSI(10) cắt lên 50  &  EMA5 cắt lên EMA10  &  ADX > 25
      short = đối xứng. Thoát = hợp lưu ngược.
  TRIPLE SUPERTREND (`Supertrend.py`):
      long khi CẢ BA supertrend (3 bộ tham số khác nhau) cùng hướng lên
  BANDTASTIC (`Bandtastic.py`):
      long = RSI thấp & MFI thấp & EMA nhanh > EMA chậm & giá < BB dưới
  TRENDRIDER pullback (`TrendRiderStrategy.py`):
      long = EMA50>EMA200 & giá hồi về EMA20 & RSI trong dải & ADX>ngưỡng & +DI>−DI

VÌ SAO ĐÂY LÀ HƯỚNG MỚI, KHÔNG PHẢI LẶP LẠI VÒNG 40-46
  `fx_ta_lab` đo TỪNG HỌ riêng lẻ; `fx_ta_conditional` đo MỘT họ + MỘT cổng.
  Đây là N ĐIỀU KIỆN ĐỘC LẬP cùng lúc — giả thiết là mỗi điều kiện riêng lẻ quá yếu
  (đã đo: IC tối đa 0,018) nhưng GIAO của chúng lọc ra tập con đủ mạnh để bù chi phí.
  Giả thiết này KIỂM ĐỊNH ĐƯỢC: nếu đúng, số lệnh giảm mạnh mà net/lệnh phải tăng.

CẢNH BÁO OVERFIT ĐÃ DỰNG SẴN: 4 luật × 2 khung × 7 cặp = 56 ô. Ngưỡng để gọi là
"có edge" phải là FORM>0 VÀ OOS>0 VÀ phổ quát ≥50% công cụ — không dùng một ô đẹp.
"""
import sys
import io
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd

from src.python.research import fx_ta_lab as TA
from src.python.shared import asset_profile as AP

pd.set_option("display.width", 260, "display.max_columns", 40, "display.max_rows", 200)
t0 = time.time()
DEV = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"


# ═══════════════════════════════════════════════════════ chỉ báo bổ sung
def _ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def _rsi(c, n):
    d = c.diff()
    g = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))


def _atr(b, n=14):
    pc = b["close"].shift(1)
    tr = pd.concat([b["high"] - b["low"], (b["high"] - pc).abs(),
                    (b["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _supertrend_dir(b, mult, per):
    """Hướng Supertrend (+1/−1) — ATR(per) với hệ số mult, đúng công thức gốc."""
    atr = _atr(b, per)
    hl2 = (b["high"] + b["low"]) / 2
    u = (hl2 + mult * atr).to_numpy()
    d = (hl2 - mult * atr).to_numpy()
    c = b["close"].to_numpy()
    n = len(c)
    dirn = np.ones(n)
    fu, fd = u.copy(), d.copy()
    for i in range(1, n):
        fu[i] = min(u[i], fu[i - 1]) if c[i - 1] <= fu[i - 1] else u[i]
        fd[i] = max(d[i], fd[i - 1]) if c[i - 1] >= fd[i - 1] else d[i]
        if c[i] > fu[i - 1]:
            dirn[i] = 1
        elif c[i] < fd[i - 1]:
            dirn[i] = -1
        else:
            dirn[i] = dirn[i - 1]
    return pd.Series(dirn, index=b.index)


def _mfi(b, n=14):
    tp = (b["high"] + b["low"] + b["close"]) / 3
    mf = tp * b["volume"]
    up = mf.where(tp.diff() > 0, 0.0).rolling(n).sum()
    dn = mf.where(tp.diff() < 0, 0.0).rolling(n).sum()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def _xup(s, lvl):
    return (s > lvl) & (s.shift(1) <= lvl)


def _xdn(s, lvl):
    return (s < lvl) & (s.shift(1) >= lvl)


# ═══════════════════════════════════════════════════════ bốn luật hợp lưu
def sig_hlhb(bars, adx_min=25.0, confl_bars=3):
    """HLHB. `confl_bars` = số nến cho phép hai lần cắt lệch nhau (nguyên bản = 1).

    Nới lên 3 vì bản gốc đòi hai lần cắt TRONG CÙNG một nến — trên FX H1 điều đó xảy
    ra quá ít lần để có ý nghĩa thống kê.
    """
    b = bars.df
    c = b["close"]
    hl2 = (c + b["open"]) / 2
    r = _rsi(hl2, 10)
    e5, e10 = _ema(c, 5), _ema(c, 10)
    adx = b["adx"]
    rl = _xup(r, 50).rolling(confl_bars).max().astype(bool)
    rs = _xdn(r, 50).rolling(confl_bars).max().astype(bool)
    ml = _xup(e5 - e10, 0.0).rolling(confl_bars).max().astype(bool)
    ms = _xdn(e5 - e10, 0.0).rolling(confl_bars).max().astype(bool)
    el = (rl & ml & (adx > adx_min)).shift(1).fillna(False)
    es = (rs & ms & (adx > adx_min)).shift(1).fillna(False)
    return TA._state_machine(el, es, es, el)


def sig_triple_st(bars, sets=((3, 12), (2, 11), (1, 10))):
    """Ba Supertrend đồng thuận — bộ tham số mặc định của `Supertrend.py`."""
    b = bars.df
    dirs = [_supertrend_dir(b, m, p) for m, p in sets]
    allup = np.logical_and.reduce([d > 0 for d in dirs])
    alldn = np.logical_and.reduce([d < 0 for d in dirs])
    pos = pd.Series(np.where(allup, 1.0, np.where(alldn, -1.0, 0.0)), index=b.index)
    return pos.shift(1).fillna(0.0)


def sig_bandtastic(bars, rsi_max=35.0, mfi_max=35.0, fast=10, slow=50):
    """Hồi quy về trung bình CÓ cổng xu hướng — mua đáy chỉ khi xu hướng còn lên."""
    b = bars.df
    c = b["close"]
    r, m = b["rsi"], _mfi(b)
    up = _ema(c, fast) > _ema(c, slow)
    dn = _ema(c, fast) < _ema(c, slow)
    el = ((r < rsi_max) & (m < mfi_max) & up & (c < b["bb_dn"])).shift(1).fillna(False)
    es = ((r > 100 - rsi_max) & (m > 100 - mfi_max) & dn
          & (c > b["bb_up"])).shift(1).fillna(False)
    xl = (c > b["bb_mid"]).shift(1).fillna(False)
    xs = (c < b["bb_mid"]).shift(1).fillna(False)
    return TA._state_machine(el, es, xl, xs)


def sig_trendrider(bars, adx_min=20.0, rsi_lo=40.0, rsi_hi=60.0):
    """Hồi về EMA20 trong xu hướng EMA50/200, xác nhận bằng ADX và DI."""
    b = bars.df
    c = b["close"]
    bull = b["ema50"] > b["ema200"]
    bear = b["ema50"] < b["ema200"]
    near = (c - b["ema20"]).abs() < 0.5 * b["atr14"]
    up_move, dn_move = b["high"].diff(), -b["low"].diff()
    pdm = pd.Series(np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0),
                    index=b.index)
    mdm = pd.Series(np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0),
                    index=b.index)
    atr = b["atr14"].replace(0, np.nan)
    pdi = 100 * pdm.ewm(alpha=1 / 14, adjust=False).mean() / atr
    mdi = 100 * mdm.ewm(alpha=1 / 14, adjust=False).mean() / atr
    el = (bull & near & b["rsi"].between(rsi_lo, rsi_hi)
          & (b["adx"] > adx_min) & (pdi > mdi)).shift(1).fillna(False)
    es = (bear & near & b["rsi"].between(100 - rsi_hi, 100 - rsi_lo)
          & (b["adx"] > adx_min) & (mdi > pdi)).shift(1).fillna(False)
    xl = ((c > b["bb_up"]) | bear).shift(1).fillna(False)
    xs = ((c < b["bb_dn"]) | bull).shift(1).fillna(False)
    return TA._state_machine(el, es, xl, xs)


FAM = {"hlhb": sig_hlhb, "triple_st": sig_triple_st,
       "bandtastic": sig_bandtastic, "trendrider": sig_trendrider}


def sh(s, lo=None, hi=None):
    if lo is not None:
        s = s[s.index >= lo]
    if hi is not None:
        s = s[s.index < hi]
    sd = float(s.std(ddof=1))
    return float(s.mean()) / sd * np.sqrt(252) if sd > 0 and len(s) > 60 else np.nan


def main():
    pairs = list(AP.FX_ALL)
    rows = []
    print(f"Đo {len(FAM)} luật × 2 khung × {len(pairs)} cặp = "
          f"{len(FAM) * 2 * len(pairs)} ô\n")
    for tf in ("H1", "M30"):
        for sym in pairs:
            bars = TA.load(sym, tf)
            for nm, fn in FAM.items():
                try:
                    p = fn(bars)
                except Exception as exc:                      # pragma: no cover
                    print(f"  {sym} {tf} {nm}: LỖI {exc}")
                    continue
                r = TA.simulate(bars, p, name=nm)
                d = r.pnl_daily
                rows.append({"tf": tf, "sym": sym, "rule": nm,
                             "ALL": round(sh(d), 3), "FORM": round(sh(d, hi=DEV), 3),
                             "OOS": round(sh(d, lo=DEV), 3), "n": r.n_trades,
                             "gross/l": round(r.gross_bps_trade, 2),
                             "phi/l": round(r.cost_bps_trade + r.swap_bps_trade, 2),
                             "net/l": round(r.net_bps_trade, 2),
                             "hold": round(r.bars_held_avg, 1),
                             "%tt": round(r.time_in_market, 2)})
            print(f"  {sym} {tf} xong", flush=True)

    T = pd.DataFrame(rows)
    T.to_csv(OUT / "confluence_h1.csv", index=False)
    print()
    print("=" * 150)
    print("KẾT QUẢ ĐẦY ĐỦ")
    print("=" * 150)
    print(T.sort_values("ALL", ascending=False).to_string(index=False))

    print()
    print("=" * 150)
    print("PHỔ QUÁT theo luật — trung vị trên 7 cặp")
    print("=" * 150)
    g = T.groupby(["rule", "tf"]).agg(
        ALL_med=("ALL", "median"), OOS_med=("OOS", "median"),
        n_pos=("ALL", lambda x: int((x > 0).sum())), n_cell=("ALL", "size"),
        net_med=("net/l", "median"), gross_med=("gross/l", "median"),
        phi_med=("phi/l", "median"), trades=("n", "median")).round(3)
    print(g.to_string())

    print()
    print("=" * 150)
    print("CỔNG: FORM>0 & OOS>0 & ALL>0,4")
    print("=" * 150)
    k = T[(T["FORM"] > 0) & (T["OOS"] > 0) & (T["ALL"] > 0.4)]
    print(k.to_string(index=False) if len(k) else "  KHÔNG CÓ Ô NÀO QUA CỔNG")
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
