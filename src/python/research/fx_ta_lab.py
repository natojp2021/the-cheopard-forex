"""fx_ta_lab.py — lab PHÂN TÍCH KỸ THUẬT THUẦN trên EURUSD + GBPUSD.

VÌ SAO TẬP TRUNG ĐÚNG HAI CẶP NÀY
==================================
Đo được (`reports/fx_recon/pair_profile.csv`, H1 2020+), chi phí khứ hồi:

    EURUSD  0,91 bps   <- RẺ NHẤT trong toàn bộ vũ trụ khả dụng
    GBPUSD  1,20 bps
    USDJPY  1,07 bps
    ...
    NZDUSD  2,90 bps   <- gấp hơn 3 lần EURUSD

Chi phí là ràng buộc quyết định của mọi chiến lược nội ngày (đã chứng minh 13 lần).
Một tín hiệu yếu vẫn có thể sống trên EURUSD mà chết trên NZDUSD. Nên nếu TA thuần
có chỗ nào hoạt động được trên FX, chỗ đó phải là EU và GU.

BỐI CẢNH — NHỮNG GÌ ĐÃ THẤT BẠI TRÊN CHÍNH HAI CẶP NÀY
=======================================================
Phải ghi rõ để không lặp lại:
    8 price-action family (M30/H1/H4)   28/33 NO_INFORMATION, MFE/|MAE| ~ 1,00
    quét IC 15 đặc trưng giá × 5 horizon  |IC| max = 0,0180
    quét IC 8 đặc trưng vi cấu trúc (M1)  |IC| max = 0,0102
    MA 20/120 (Olszweski & Zhou)       Sharpe −0,07, EURUSD 11 năm −0,13
    RSI-difference pairs (IEEE)         chính tác giả báo không đạt

Lab này KHÁC ở ba điểm, không phải chạy lại cùng thứ:
  1. **Nhóm BIẾN ĐỘNG** chưa từng thử. Haeri et al. (JACST 2015) đo trên EURJPY:
     dự báo HƯỚNG chỉ 53,9% nhưng dự báo BIÊN ĐỘ đạt **72-90%**. Biến động là chiều
     thông tin khác hẳn hướng, và mọi thứ đã thử đều là cược HƯỚNG.
  2. **Bộ lọc chế độ** (ADX, BandWidth) làm điều kiện, không làm tín hiệu — đúng cách
     tài liệu dùng chúng, khác với việc dùng chúng làm trigger như HELIX
     (`project-refer/tradingsystem`) đã thất bại.
  3. **Chi phí đúng từng cặp** ngay trong vòng lặp, nên không có ô nào trông tốt chỉ
     vì phí bị tính nhẹ.

MƯỜI HỌ TÍN HIỆU — MỖI HỌ MỘT NGUỒN
====================================
Nhóm XU HƯỚNG
 1. `ma_cross`      Giao hai trung bình (Zhu & Zhou, *JFE* 2009 — "Technical
                    analysis: an asset allocation perspective on moving averages")
 2. `macd`          MACD histogram đổi dấu (Appel; dùng rộng trong freqtrade)
 3. `donchian`      Phá biên N nến, thoát biên đối diện (Turtle; AdTurtle JRFM 2019)
 4. `keltner`       Phá kênh ATR quanh EMA (Keltner; AdTurtle dùng ATR làm biên)
 5. `adx_trend`     MA cross nhưng CHỈ khi ADX > ngưỡng (Wilder 1978)

Nhóm HỒI QUY
 6. `rsi_mr`        RSI cực trị rồi quay lại (Wilder 1978)
 7. `bb_mr`         Giá ra ngoài dải Bollinger rồi quay vào (Bollinger 2001)
 8. `stoch_mr`      Stochastic cực trị (Lane)

Nhóm BIẾN ĐỘNG — chưa từng thử, và là lý do chính lab này tồn tại
 9. `squeeze`       BandWidth co xuống phân vị thấp rồi BUNG (Bollinger Squeeze;
                    John Carter *Mastering the Trade* — Squeeze Momentum)
10. `range_expand`  Nến hẹp bất thường (NR7) rồi phá biên nến đó
                    (Toby Crabel, *Day Trading with Short Term Price Patterns*)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.python.shared import asset_profile as AP
from src.python.shared import carry_costs as CC
from src.python.shared import fx_data as D

TIER1: Tuple[str, ...] = ("EURUSD", "GBPUSD")
FORM_END = pd.Timestamp("2024-01-01")

BAR_HOURS: Dict[str, float] = {"M30": 0.5, "H1": 1.0, "H4": 4.0, "D1": 24.0}
BARS_PER_YEAR: Dict[str, float] = {"M30": 252 * 48, "H1": 252 * 24,
                                   "H4": 252 * 6, "D1": 252}


# ═══════════════════════════════════════════════════════ dữ liệu + chỉ báo
@dataclass
class Bars:
    symbol: str
    timeframe: str
    df: pd.DataFrame
    cost_1rt_bps: float
    swap_bps_per_bar: float


def load(symbol: str, timeframe: str = "H1", start: str = "2020-01-01",
         broker_markup_pct: float = 1.0) -> Bars:
    """Nến + chỉ báo, kèm chi phí thật của cặp.

    Mọi chỉ báo đều dùng dữ liệu ĐÃ ĐÓNG. Các hàm tín hiệu bên dưới còn `.shift(1)`
    thêm một nến nữa khi so sánh, nên không có đường nào chạm được nến tương lai.
    """
    b = D.build_bars(D.load_m1(symbol), timeframe)
    b = b[b.index >= start].copy()
    prof = AP.get(symbol)
    c, h, l, o = b["close"], b["high"], b["low"], b["open"]

    # ── xu hướng
    for n in (10, 20, 50, 100, 200):
        b[f"ema{n}"] = c.ewm(span=n, adjust=False).mean()
        b[f"sma{n}"] = c.rolling(n).mean()
    ema12, ema26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    b["macd"] = ema12 - ema26
    b["macd_sig"] = b["macd"].ewm(span=9, adjust=False).mean()
    b["macd_hist"] = b["macd"] - b["macd_sig"]

    # ── ATR (Wilder)
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    b["atr14"] = tr.ewm(alpha=1 / 14, adjust=False).mean()

    # ── ADX (Wilder)
    up_move, dn_move = h.diff(), -l.diff()
    plus_dm = np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0)
    atr = b["atr14"].replace(0, np.nan)
    pdi = 100 * pd.Series(plus_dm, index=b.index).ewm(alpha=1 / 14, adjust=False).mean() / atr
    mdi = 100 * pd.Series(minus_dm, index=b.index).ewm(alpha=1 / 14, adjust=False).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    b["adx"] = dx.ewm(alpha=1 / 14, adjust=False).mean()

    # ── RSI (Wilder)
    d = c.diff()
    gain = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    b["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    # ── Bollinger + BandWidth (thước đo nén biến động)
    ma20, sd20 = c.rolling(20).mean(), c.rolling(20).std(ddof=1)
    b["bb_up"], b["bb_dn"], b["bb_mid"] = ma20 + 2 * sd20, ma20 - 2 * sd20, ma20
    b["bb_width"] = (b["bb_up"] - b["bb_dn"]) / ma20.replace(0, np.nan)

    # ── Keltner (kênh ATR quanh EMA20)
    b["kc_up"] = b["ema20"] + 2.0 * b["atr14"]
    b["kc_dn"] = b["ema20"] - 2.0 * b["atr14"]

    # ── Stochastic %K (14)
    hh, ll = h.rolling(14).max(), l.rolling(14).min()
    b["stoch"] = 100 * (c - ll) / (hh - ll).replace(0, np.nan)

    # ── biên độ nến, chuẩn hoá — nền của nhóm BIẾN ĐỘNG
    b["range"] = (h - l) / c
    b["range_rank"] = b["range"].rolling(50).apply(
        lambda x: float((x[-1] <= x).mean()), raw=True)

    px = float(c.median())
    sp = float(b["spread_usd"].median())
    cost = (sp + prof.commission_price_units(px)) / px * 1e4
    swap = (CC.SWAP_CALENDAR_MULTIPLIER * broker_markup_pct / 365.0 * 100.0
            * BAR_HOURS[timeframe] / 24.0)
    return Bars(symbol=symbol, timeframe=timeframe, df=b.dropna(subset=["close"]),
                cost_1rt_bps=cost, swap_bps_per_bar=swap)


# ═══════════════════════════════════════════════════════ mô phỏng
@dataclass
class TAResult:
    name: str
    symbol: str
    timeframe: str
    pnl_daily: pd.Series
    n_trades: int
    gross_bps_trade: float
    cost_bps_trade: float
    swap_bps_trade: float
    net_bps_trade: float
    bars_held_avg: float
    time_in_market: float


def simulate(bars: Bars, pos: pd.Series, name: str = "") -> TAResult:
    """Vị thế tại nến t ăn lợi nhuận nến t+1. Chi phí: spread khi đổi + swap khi giữ."""
    b = bars.df
    ret = np.log(b["close"]).diff() * 1e4
    pos = pos.reindex(ret.index).fillna(0.0)

    gross = pos.shift(1) * ret
    turn = pos.diff().abs().fillna(pos.abs())
    tcost = turn * bars.cost_1rt_bps / 2.0
    scost = pos.abs().shift(1).fillna(0.0) * bars.swap_bps_per_bar
    pnl = (gross - tcost - scost).fillna(0.0)

    flips = int((turn > 0).sum())
    n_tr = max(flips // 2, 1)
    held = float(pos.abs().sum() / max(flips / 2.0, 1.0))
    return TAResult(
        name=name, symbol=bars.symbol, timeframe=bars.timeframe,
        pnl_daily=pnl.resample("1D").sum().fillna(0.0),
        n_trades=n_tr,
        gross_bps_trade=float(gross.sum() / n_tr),
        cost_bps_trade=float(tcost.sum() / n_tr),
        swap_bps_trade=float(scost.sum() / n_tr),
        net_bps_trade=float(pnl.sum() / n_tr),
        bars_held_avg=held,
        time_in_market=float((pos.abs() > 0).mean()))


# ═══════════════════════════════════════════════════════ 10 họ tín hiệu
def _state_machine(entry_long, entry_short, exit_long, exit_short) -> pd.Series:
    """Máy trạng thái chung: vào khi entry, ra khi exit. Không đảo trực tiếp.

    Dùng chung cho mọi họ để logic vào/ra không khác nhau giữa các họ — nếu mỗi họ
    tự viết vòng lặp thì khác biệt về cách thoát sẽ trộn lẫn vào so sánh.
    """
    el, es = entry_long.fillna(False).to_numpy(), entry_short.fillna(False).to_numpy()
    xl, xs = exit_long.fillna(False).to_numpy(), exit_short.fillna(False).to_numpy()
    out = np.zeros(len(el))
    s = 0
    for i in range(len(el)):
        if s == 0:
            if el[i]:
                s = 1
            elif es[i]:
                s = -1
        elif s == 1 and xl[i]:
            s = 0
        elif s == -1 and xs[i]:
            s = 0
        out[i] = s
    return pd.Series(out, index=entry_long.index)


def sig_ma_cross(bars: Bars, fast: int = 20, slow: int = 100) -> pd.Series:
    """Giao hai trung bình (Zhu & Zhou 2009). Luôn có vị thế — luật gốc không có vùng phẳng."""
    b = bars.df
    f, s = b[f"ema{fast}"], b[f"ema{slow}"]
    return np.sign(f - s).shift(1).fillna(0.0)


def sig_macd(bars: Bars) -> pd.Series:
    """MACD histogram đổi dấu → vào; đổi dấu ngược → ra."""
    h = bars.df["macd_hist"]
    up = (h > 0) & (h.shift(1) <= 0)
    dn = (h < 0) & (h.shift(1) >= 0)
    return _state_machine(up.shift(1), dn.shift(1), dn.shift(1), up.shift(1))


def sig_donchian(bars: Bars, lookback: int = 55, exit_lb: int = 20) -> pd.Series:
    b = bars.df
    hi, lo = b["high"].rolling(lookback).max(), b["low"].rolling(lookback).min()
    xhi, xlo = b["high"].rolling(exit_lb).max(), b["low"].rolling(exit_lb).min()
    return _state_machine(b["close"] > hi.shift(1), b["close"] < lo.shift(1),
                          b["close"] < xlo.shift(1), b["close"] > xhi.shift(1))


def sig_keltner(bars: Bars) -> pd.Series:
    """Phá kênh ATR quanh EMA20, thoát khi về EMA20."""
    b = bars.df
    return _state_machine(b["close"] > b["kc_up"].shift(1),
                          b["close"] < b["kc_dn"].shift(1),
                          b["close"] < b["ema20"].shift(1),
                          b["close"] > b["ema20"].shift(1))


def sig_adx_trend(bars: Bars, adx_min: float = 25.0,
                  fast: int = 20, slow: int = 100) -> pd.Series:
    """MA cross nhưng CHỈ khi ADX > ngưỡng — ADX làm BỘ LỌC, không làm trigger.

    Đây là cách tài liệu dùng ADX (Wilder). HELIX trong `project-refer/tradingsystem`
    thất bại vì dùng chỉ báo chế độ làm trigger vào lệnh: *"Spectral Entropy chỉ sắp
    xếp lại lệnh, không tạo edge... trong tài liệu nó là bộ lọc CHẾ ĐỘ, không phải
    trigger vào lệnh"*.
    """
    b = bars.df
    raw = np.sign(b[f"ema{fast}"] - b[f"ema{slow}"])
    ok = b["adx"] > adx_min
    return (raw * ok.astype(float)).shift(1).fillna(0.0)


def sig_rsi_mr(bars: Bars, lo: float = 30.0, hi: float = 70.0) -> pd.Series:
    """RSI ra vùng cực trị RỒI QUAY LẠI → vào ngược chiều; thoát khi RSI về 50.

    "Rồi quay lại" thay vì "vào ngay khi cực trị" là bài học đo được từ Zheng Nan
    (§4.3.1) và nó cải thiện cả trên spread lẫn trên giá đơn.
    """
    r = bars.df["rsi"]
    was_lo = (r.shift(1) < lo) & (r >= lo)
    was_hi = (r.shift(1) > hi) & (r <= hi)
    return _state_machine(was_lo.shift(1), was_hi.shift(1),
                          (r >= 50).shift(1), (r <= 50).shift(1))


def sig_bb_mr(bars: Bars) -> pd.Series:
    """Giá ra ngoài dải Bollinger RỒI QUAY VÀO → vào ngược; thoát tại đường giữa."""
    b = bars.df
    c = b["close"]
    back_up = (c.shift(1) < b["bb_dn"].shift(1)) & (c >= b["bb_dn"])
    back_dn = (c.shift(1) > b["bb_up"].shift(1)) & (c <= b["bb_up"])
    return _state_machine(back_up.shift(1), back_dn.shift(1),
                          (c >= b["bb_mid"]).shift(1), (c <= b["bb_mid"]).shift(1))


def sig_stoch_mr(bars: Bars, lo: float = 20.0, hi: float = 80.0) -> pd.Series:
    s = bars.df["stoch"]
    back_up = (s.shift(1) < lo) & (s >= lo)
    back_dn = (s.shift(1) > hi) & (s <= hi)
    return _state_machine(back_up.shift(1), back_dn.shift(1),
                          (s >= 50).shift(1), (s <= 50).shift(1))


def sig_squeeze(bars: Bars, bw_pct: float = 0.20, lookback: int = 100,
                hold_bars: int = 0) -> pd.Series:
    """BANDWIDTH co xuống phân vị thấp rồi BUNG — nhóm BIẾN ĐỘNG.

    Bollinger Squeeze / Carter "Squeeze Momentum": biến động nén báo trước một cú
    bung, và HƯỚNG bung được lấy từ nến phá biên. Đây là cược vào BIÊN ĐỘ trước,
    hướng sau — khác hẳn mọi thứ đã thử (đều là cược hướng thuần).

    Cơ sở: Haeri et al. (JACST 2015) đo trên EURJPY thấy dự báo HƯỚNG chỉ 53,9%
    nhưng dự báo BIÊN ĐỘ đạt 72-90%.
    """
    b = bars.df
    if hold_bars <= 0:
        hold_bars = 24 if bars.timeframe in ("M30", "H1") else 5
    thr = b["bb_width"].rolling(lookback).quantile(bw_pct)
    squeezed = (b["bb_width"] <= thr).shift(1).fillna(False)
    hh = b["high"].rolling(20).max().shift(1)
    ll = b["low"].rolling(20).min().shift(1)
    long_e = squeezed & (b["close"] > hh)
    short_e = squeezed & (b["close"] < ll)

    pos = np.zeros(len(b))
    s, held = 0, 0
    le, se = long_e.fillna(False).to_numpy(), short_e.fillna(False).to_numpy()
    for i in range(len(b)):
        if s != 0:
            held += 1
            if held >= hold_bars:
                s, held = 0, 0
        if s == 0:
            if le[i]:
                s, held = 1, 0
            elif se[i]:
                s, held = -1, 0
        pos[i] = s
    return pd.Series(pos, index=b.index)


def sig_range_expand(bars: Bars, nr_pct: float = 0.15,
                     hold_bars: int = 0) -> pd.Series:
    """Nến HẸP bất thường (NR7-style) rồi phá biên chính nến đó — nhóm BIẾN ĐỘNG.

    Toby Crabel, *Day Trading with Short Term Price Patterns*: biên độ co lại báo
    trước giãn ra, và hướng giãn lấy từ phía bị phá. `range_rank` là phân vị biên độ
    của nến trong 50 nến trước, nên "hẹp bất thường" được định nghĩa tương đối chứ
    không bằng một ngưỡng pip cố định.
    """
    b = bars.df
    if hold_bars <= 0:
        hold_bars = 12 if bars.timeframe in ("M30", "H1") else 3
    narrow = (b["range_rank"] <= nr_pct).shift(1).fillna(False)
    ph, pl = b["high"].shift(1), b["low"].shift(1)
    long_e = narrow & (b["close"] > ph)
    short_e = narrow & (b["close"] < pl)

    pos = np.zeros(len(b))
    s, held = 0, 0
    le, se = long_e.fillna(False).to_numpy(), short_e.fillna(False).to_numpy()
    for i in range(len(b)):
        if s != 0:
            held += 1
            if held >= hold_bars:
                s, held = 0, 0
        if s == 0:
            if le[i]:
                s, held = 1, 0
            elif se[i]:
                s, held = -1, 0
        pos[i] = s
    return pd.Series(pos, index=b.index)


FAMILIES: Dict[str, Callable[..., pd.Series]] = {
    "ma_cross": sig_ma_cross, "macd": sig_macd, "donchian": sig_donchian,
    "keltner": sig_keltner, "adx_trend": sig_adx_trend,
    "rsi_mr": sig_rsi_mr, "bb_mr": sig_bb_mr, "stoch_mr": sig_stoch_mr,
    "squeeze": sig_squeeze, "range_expand": sig_range_expand,
}
GROUPS = {
    "ma_cross": "XU HƯỚNG", "macd": "XU HƯỚNG", "donchian": "XU HƯỚNG",
    "keltner": "XU HƯỚNG", "adx_trend": "XU HƯỚNG",
    "rsi_mr": "HỒI QUY", "bb_mr": "HỒI QUY", "stoch_mr": "HỒI QUY",
    "squeeze": "BIẾN ĐỘNG", "range_expand": "BIẾN ĐỘNG",
}


# ═══════════════════════════════════════════════════════ báo cáo
def stats(pnl: pd.Series, label: str = "") -> Dict[str, object]:
    s = pnl[pnl.index >= pd.Timestamp("2020-04-01")]
    if len(s) < 60 or float(s.std(ddof=1)) <= 0:
        return {"label": label, "sharpe": np.nan}
    cum = s.cumsum()
    dd = cum.cummax() - cum
    yrs = max((s.index.max() - s.index.min()).days / 365.25, 1e-9)
    return {
        "label": label,
        "sharpe": round(float(s.mean()) / float(s.std(ddof=1)) * np.sqrt(252), 3),
        "ann_pct": round(float(cum.iloc[-1]) / 100.0 / yrs, 2),
        "max_dd_pct": round(float(dd.max()) / 100.0, 2),
    }


def row(res: TAResult) -> Dict[str, object]:
    d = res.pnl_daily
    a, f, o = (stats(d, "ALL"), stats(d[d.index < FORM_END], "FORM"),
               stats(d[d.index >= FORM_END], "OOS"))
    return {
        "nhóm": GROUPS.get(res.name, "?"), "họ": res.name,
        "cặp": res.symbol, "tf": res.timeframe,
        "ALL": a["sharpe"], "FORM": f["sharpe"], "OOS": o["sharpe"],
        "ann%": a.get("ann_pct"), "maxDD%": a.get("max_dd_pct"),
        "n_lệnh": res.n_trades,
        "gross": round(res.gross_bps_trade, 2),
        "phí": round(res.cost_bps_trade, 2),
        "swap": round(res.swap_bps_trade, 2),
        "net": round(res.net_bps_trade, 2),
        "giữ": round(res.bars_held_avg, 1),
        "%tt": round(res.time_in_market, 2),
    }
