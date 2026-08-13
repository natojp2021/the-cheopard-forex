"""Causal feature pipeline built on canonical closed M5 bars.

Timestamps represent the *open* of an M5 bar.  Every feature on row ``t`` may
use that bar's OHLC, but the row is only actionable at ``t + 5 minutes``.
Higher-timeframe values are aligned by their availability time, never by the
start of an unfinished H1 bar.
"""
import math
import pandas as pd
import numpy as np


# Session codes (khớp EA)
# 0=Asia Build  1=Asia Trade  2=London Judas  3=London Trade
# 4=Dead Zone   5=NY Open     6=NY Prime       7=Overnight
SESSION_NAMES = {
    0: "asia_build", 1: "asia_trade", 2: "london_judas", 3: "london_trade",
    4: "dead_zone",  5: "ny_open",    6: "ny_prime",     7: "overnight",
}


def true_range(df):
    """True Range (max của 3 phép tính, truyền NaN qua np.maximum chain)."""
    return np.maximum(df["high"] - df["low"], np.maximum(
        (df["close"].shift() - df["low"]).abs(), (df["high"] - df["close"].shift()).abs()))


def sma_atr(df, n=14):
    """ATR theo kiểu SMA (rolling mean của True Range)."""
    return true_range(df).rolling(n).mean()


def atr(df, n=14):
    tr = pd.concat([df.high - df.low,
                    (df.high - df.close.shift()).abs(),
                    (df.low  - df.close.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()


def adx(df, n=14):
    """ADX chuẩn Wilder (+DI/-DI tính từ high/low, Wilder smoothing alpha=1/n)."""
    # `close` không cần ở đây: nó chỉ tham gia qua `atr(df, n)` bên dưới (Wilder TR).
    high, low = df["high"], df["low"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
    atr_wilder = atr(df, n)
    safe_atr = atr_wilder.replace(0, np.nan)
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean() / safe_atr
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean() / safe_atr
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum
    return dx.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean().fillna(0.0)


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def momentum_over_atr(df, atr_col, lag=12):
    """Momentum chuẩn hóa theo ATR: (close - close.shift(lag)) / atr_col."""
    return (df["close"] - df["close"].shift(lag)) / df[atr_col].replace(0, np.nan)


def rolling_z(s, window=288, min_periods=60):
    """Z-score nhân quả: (x - rolling_mean) / (rolling_std + eps)."""
    mu = s.rolling(window, min_periods=min_periods).mean()
    sd = s.rolling(window, min_periods=min_periods).std()
    return (s - mu) / (sd + 1e-12)


def rsi(s, n=14):
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def resample(df, rule):
    out = pd.DataFrame({
        "open":       df.open.resample(rule).first(),
        "high":       df.high.resample(rule).max(),
        "low":        df.low.resample(rule).min(),
        "close":      df.close.resample(rule).last(),
        "spread_usd": df.spread_usd.resample(rule).mean(),
    }).dropna()
    return out


def range_table(m5, h0, h1):
    """Completed daily range for a GMT window, using canonical M5 bars."""
    mask = (m5.index.hour >= h0) & (m5.index.hour < h1)
    a = m5[mask]
    g = a.groupby(a.index.date)
    tbl = pd.DataFrame({"hi": g.high.max(), "lo": g.low.min(), "bars": g.close.count()})
    return tbl[tbl.bars >= 12 * (h1 - h0) * 0.7]  # loại ngày thiếu >30%


def _validate_m5(df):
    """Normalize and reject non-M5 inputs instead of silently resampling them."""
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"M5 data missing columns: {sorted(missing)}")
    out = df.copy().sort_index()
    out = out[~out.index.duplicated(keep="last")]
    if len(out) >= 3:
        minutes = out.index.to_series().diff().dropna().dt.total_seconds() / 60.0
        positive = minutes[minutes > 0]
        if len(positive) and not np.isclose(float(positive.median()), 5.0):
            raise ValueError(
                f"Canonical feature input must be M5; median interval={positive.median():.2f} minutes"
            )
    if "spread_usd" not in out.columns:
        if "spread" in out.columns:
            out["spread_usd"] = pd.to_numeric(out["spread"], errors="coerce") * 0.01
        else:
            raise ValueError("M5 data requires spread_usd (or broker spread points)")
    return out


def _align_closed_h1(series, m5_index):
    """Align H1 values to M5 bar-close time, preventing unfinished-H1 leakage."""
    available = series.copy()
    available.index = available.index + pd.Timedelta(hours=1)
    query = pd.DatetimeIndex(m5_index) + pd.Timedelta(minutes=5)
    aligned = available.reindex(query, method="ffill")
    aligned.index = m5_index
    return aligned


def _align_closed(series, m5_index, timeframe):
    """Align a higher-timeframe value only after its source bar has closed."""
    delta = pd.Timedelta(timeframe)
    available = series.copy()
    available.index = available.index + delta
    query = pd.DatetimeIndex(m5_index) + pd.Timedelta(minutes=5)
    aligned = available.reindex(query, method="ffill")
    aligned.index = m5_index
    return aligned


def _session_code(hour_float):
    """Trả về session code (0-7) theo giờ GMT (float)."""
    h = hour_float
    if h < 4.0:  return 0
    if h < 7.0:  return 1
    if h < 9.5:  return 2
    if h < 12.5: return 3
    if h < 13.5: return 4
    if h < 14.0: return 5
    if h < 17.0: return 6
    return 7


def detect_fvg(m5):
    """
    Phát hiện Fair Value Gap (FVG) tại mỗi bar M5.
    Bull FVG: candle[i-2].high < candle[i].low  (gap lên)
    Bear FVG: candle[i-2].low  > candle[i].high (gap xuống)
    Trả về cột: fvg_bull (mid), fvg_bear (mid), 0 nếu không có.
    """
    hi = m5.high.values
    lo = m5.low.values
    n = len(m5)
    bull_mid = np.zeros(n)
    bear_mid = np.zeros(n)
    for i in range(2, n):
        if hi[i-2] < lo[i]:        # bull FVG
            bull_mid[i] = (hi[i-2] + lo[i]) / 2.0
        if lo[i-2] > hi[i]:        # bear FVG
            bear_mid[i] = (lo[i-2] + hi[i]) / 2.0
    m5 = m5.copy()
    m5["fvg_bull"] = bull_mid
    m5["fvg_bear"] = bear_mid
    return m5


def detect_mss(m5):
    """
    Market Structure Shift: nến đóng vượt qua swing high/low gần nhất ngược chiều.
    mss_bull: đóng trên swing high trong 10 bar trước (sau downswing)
    mss_bear: đóng dưới swing low trong 10 bar trước (sau upswing)
    """
    close = m5.close.values
    high  = m5.high.values
    low   = m5.low.values
    n = len(m5)
    W = 10
    mss_bull = np.zeros(n, dtype=bool)
    mss_bear = np.zeros(n, dtype=bool)
    for i in range(W, n):
        window_hi = high[i-W:i].max()
        window_lo = low[i-W:i].min()
        if close[i] > window_hi:
            mss_bull[i] = True
        if close[i] < window_lo:
            mss_bear[i] = True
    m5 = m5.copy()
    m5["mss_bull"] = mss_bull
    m5["mss_bear"] = mss_bear
    return m5


def add_core_features(bars_m5, anchor="london"):
    """
    Tính đầy đủ features cho 24/7 backtesting.

    anchor:
      "london"       — range 07:00-12:00, dùng cho A/B/D/D+/E strategies
      "asia"         — range 00:00-07:00, dùng cho F strategy
      "london_prime" — chỉ NY Prime window
    """
    m5 = _validate_m5(bars_m5)
    m15 = resample(m5, "15min")
    h1 = resample(m5, "1h")

    # === ATR và EMA ===
    m5["atr_m5"]  = atr(m5, 14)
    h1["ema50"]   = ema(h1.close, 50)
    h1["ema34"]   = ema(h1.close, 34)
    h1["atr_h1"]  = atr(h1, 14)
    m5["ema50_h1"]   = _align_closed_h1(h1.ema50, m5.index)
    m5["atr_h1"]     = _align_closed_h1(h1.atr_h1, m5.index)
    m5["ema34_h1"]   = _align_closed_h1(h1.ema34, m5.index)
    m5["ema34_hi"]   = ema(m5.high, 34)
    m5["ema34_lo"]   = ema(m5.low, 34)
    m5["rsi_m5"]     = rsi(m5.close, 14)
    # Scale-free causal momentum/regime features for automatic edge discovery.
    for lag in (1, 3, 12):
        m5[f"ret_m5_{lag}_atr"] = (m5.close - m5.close.shift(lag)) / m5["atr_m5"].replace(0, np.nan)
    m5["atr_regime_ratio"] = m5["atr_m5"] / m5["atr_m5"].rolling(288, min_periods=72).median()
    m15["atr_m15"] = atr(m15, 14)
    m15["ema34_m15"] = ema(m15.close, 34)
    m15["momentum_m15"] = m15.close.pct_change(3)
    m5["atr_m15"] = _align_closed(m15.atr_m15, m5.index, "15min")
    m5["ema34_m15"] = _align_closed(m15.ema34_m15, m5.index, "15min")
    m5["momentum_m15"] = _align_closed(m15.momentum_m15, m5.index, "15min")

    # === Session code và flags ===
    hrs = m5.index.hour + m5.index.minute / 60.0
    m5["hrs_gmt"]  = hrs
    m5["session"]  = hrs.map(_session_code).astype(int)

    # Cửa sổ chặn cuối tuần: Thứ Hai < 08:00 GMT (chờ đóng gap đầu tuần) 
    # và Thứ Sáu >= 17:00 GMT (không giữ vị thế qua tuần).
    dow = m5.index.dayofweek
    m5["in_win"] = True
    m5.loc[(dow == 0) & (hrs < 8.0),  "in_win"] = False  # Mon trước 08:00 GMT (spec §2.3)
    m5.loc[(dow == 4) & (hrs >= 17.0), "in_win"] = False  # Fri sau 17:00 GMT (spec §2.3)

    # Hệ số khối lượng theo phiên: 0,5 với Á/Overnight/NY_Open, 1,0 với London/Prime
    m5["session_mult"] = np.where(m5["session"].isin([0,1,5,7]), 0.5, 1.0)

    # === Daily Open Bias ===
    # Lấy giá mở cửa đầu ngày (00:00 GMT) mỗi ngày
    dates = pd.Series(m5.index.date, index=m5.index)
    daily_open = (m5.groupby(m5.index.date)["open"].first()
                    .rename("daily_open"))
    m5["daily_open"] = dates.map(daily_open)
    m5["daily_bias"] = np.where(m5.close > m5.daily_open, 1,
                        np.where(m5.close < m5.daily_open, -1, 0))

    # === Dragon Slope (EMA34 H1, slope qua 3 bar) ===
    ema34_h1_vals = _align_closed_h1(h1.ema34, m5.index)
    ema34_h1_lag3 = _align_closed_h1(h1.ema34.shift(3), m5.index)
    slope = ema34_h1_vals - ema34_h1_lag3
    atr_h1_v = m5["atr_h1"]
    m5["dragon_slope"] = np.where(slope > 0.08 * atr_h1_v, 1,
                          np.where(slope < -0.08 * atr_h1_v, -1, 0))

    # === Ranges per session ===
    dser = pd.Series(m5.index.date, index=m5.index)

    # Asia range: 00:00-07:00 GMT
    asia_rng = range_table(m5, 0, 7)
    m5["asia_hi"] = dser.map(asia_rng.hi)
    m5["asia_lo"] = dser.map(asia_rng.lo)
    m5.loc[hrs < 7.0, ["asia_hi", "asia_lo"]] = np.nan

    # London range: 07:00-12:00 GMT
    large_range = range_table(m5, 7, 12)
    m5["rng_hi"] = dser.map(large_range.hi)
    m5["rng_lo"] = dser.map(large_range.lo)
    m5["rng_w"]  = m5.rng_hi - m5.rng_lo
    m5.loc[hrs < 12.0, ["rng_hi", "rng_lo", "rng_w"]] = np.nan

    # Biên độ buổi sáng (08:00-13:00 GMT) — đặc trưng của hệ XAUUSD. Hệ Forex
    # KHÔNG dùng cột này trong bất kỳ chiến lược nào: 63 vòng nghiên cứu cho thấy
    # mọi hướng theo phiên trên FX đều thua chi phí, và vòng 69-70 đo riêng Asian
    # Range Breakout cũng trượt kiểm định (xem `registry.REJECTED_DIRECTIONS`).
    # Cột vẫn sinh ra vì đường ống feature kế thừa đọc nó; đừng xây luật mới trên nó.
    morn_rng = range_table(m5, 8, 13)
    m5["morning_hi"] = dser.map(morn_rng.hi)
    m5["morning_lo"] = dser.map(morn_rng.lo)
    m5.loc[hrs < 13.0, ["morning_hi", "morning_lo"]] = np.nan

    # anchor ATR M5 (London session làm baseline)
    large_mask = (m5.index.hour >= 7) & (m5.index.hour < 12)
    anchor_atr = m5.atr_m5[large_mask].groupby(m5.index[large_mask].date).mean()
    m5["anchor_atr_m5"] = dser.map(anchor_atr)
    m5.loc[hrs < 12.0, "anchor_atr_m5"] = np.nan

    # === FVG và MSS detection ===
    m5 = detect_fvg(m5)
    m5 = detect_mss(m5)

    # Khối "00/50 level proximity" ĐÃ XOÁ 13/08/2026: ngưỡng của nó là 2,0 ĐƠN VỊ GIÁ
    # TUYỆT ĐỐI — hợp lý với vàng ở $2.000, vô nghĩa với EURUSD ở 1,10 (2,0 tương
    # đương 18.000 pip). Mốc tròn trên FX phải tính theo pip, không theo đô-la.

    # === ML Indicators (ADX, EMA) ===
    m5["ema_m5"] = ema(m5.close, 22)

    # Tính ADX M5 bằng công thức chuẩn Wilder.
    m5["adx_m5"] = adx(m5, 14)

    return m5, large_range
