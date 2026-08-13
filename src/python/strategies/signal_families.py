"""signal_families.py — ĐỘNG CƠ dùng chung cho ba họ tín hiệu KHÔNG PHẢI z-band.

VÌ SAO CẦN HỌ KHÁC Z-BAND
=========================
Bảy chân H1 đầu tiên đều đọc CÙNG MỘT đại lượng: khoảng cách chuẩn hoá từ giá tới
trung bình động của chính nó. Chúng khác nhau ở công cụ và tham số, không khác ở CÁCH
NHÌN thị trường. Hệ quả đo được: hai chân cùng công cụ khác khung tương quan 0,712,
và danh mục phải gộp nhóm rủi ro để không âm thầm nhân ba phơi nhiễm.

Thêm một chân z-band thứ tám không giải quyết gì — nó chỉ làm nhóm đã có dày thêm.

Ba họ ở đây đọc ba đại lượng khác hẳn, và |tương quan| với toàn bộ 17 chân đang chạy
đo được **tối đa 0,206**:

    RSI_DIV     QUAN HỆ giữa hai chuỗi — giá lập cực trị mới mà RSI thì không.
                Không phải mức của một chuỗi, mà là hai chuỗi nói ngược nhau.
    STREAK      ĐẾM nến cùng chiều liên tiếp. Miễn nhiễm hoàn toàn với độ lớn, nên
                về cấu tạo nó KHÔNG THỂ trùng z-score.
    VOL_REGIME  TỶ SỐ hai độ lệch chuẩn (ngắn/dài). Cược biến động hồi quy, không
                cược giá hồi quy — hai thứ này thực nghiệm gần như trực giao.

Một chân Sharpe 0,80 độc lập đóng góp cho danh mục nhiều hơn một chân Sharpe 1,00
tương quan 0,7 với chân đã có. Đó là lý do các chân ở đây không phải chân mạnh nhất.

LUẬT CHUNG — KHÔNG CẮT LỖ THEO GIÁ
===================================
Cả ba họ dùng cùng cơ chế thoát với z-band: tín hiệu ngược HOẶC time-stop, không có
SL theo ATR. Đo được hai lần độc lập (vòng 57 trên 8 họ × 27 công cụ, vòng 59 trên
công cụ đã chọn) rằng SL theo ATR làm tệ hơn trên FX — chiến lược hồi quy vào lệnh
khi giá ĐANG đi ngược, nên SL đặt gần luôn bị chạm trước khi hồi.

Giữ chung cơ chế thoát cũng để so sánh giữa các họ là công bằng: nếu mỗi họ một kiểu
thoát thì khác biệt về cách thoát sẽ trộn lẫn vào khác biệt về tín hiệu.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.python.strategies import rulebook as RB

FORM_END = pd.Timestamp("2024-01-01")


@dataclass(frozen=True)
class FamilyConfig:
    """Cấu hình một chiến lược thuộc họ tín hiệu. Mọi tham số đều lộ."""
    name: str
    family: str                   # rsi_div | streak | vol_regime
    instrument: str
    timeframe: str
    window: int                   # N — cửa sổ tính tín hiệu
    threshold: float              # k — ngưỡng lọc, ý nghĩa tuỳ họ
    timestop_bars: int            # thoát cưỡng bức sau bao nhiêu nến
    broker_markup_pct: float = 1.0


@dataclass
class EntryDecision:
    """Bản ghi quy tắc vào lệnh — đủ để TÁI LẬP quyết định từ chính bản ghi."""
    timestamp: pd.Timestamp
    strategy: str
    family: str
    instrument: str
    timeframe: str
    action: str                   # BUY | SELL | HOLD | FLAT
    price: float
    signal_value: float           # giá trị đại lượng của họ tại nến này
    threshold: float
    window: int
    bars_held: int
    timestop_bars: int
    est_cost_bps: float
    est_swap_bps_per_bar: float
    reason: str

    def to_row(self) -> Dict[str, object]:
        d = dict(self.__dict__)
        d["timestamp"] = str(self.timestamp)
        return d

    def explain(self) -> str:
        return (f"[{self.timestamp}] {self.strategy}/{self.instrument} "
                f"{self.action} @ {self.price:.5f} · {self.family}="
                f"{self.signal_value:+.3f} (ngưỡng {self.threshold}) · "
                f"giữ {self.bars_held}/{self.timestop_bars} nến · {self.reason}")


# ═══════════════════════════════════════════════════════ chỉ báo nền
def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    g = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(),
                    (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


# Cờ tắt phép dịch, chỉ dùng cho đường LIVE. Xem `live_decision`.
_SHIFT_ENABLED = True


def _shift(s: pd.Series) -> pd.Series:
    """Dịch một nến rồi ép bool — quyết định tại t chỉ dùng dữ liệu tới t−1.

    ⚠️ HAI ĐƯỜNG DÙNG CHUỖI NÀY THEO HAI CÁCH KHÁC NHAU — sửa 15/08/2026.

    BACKTEST đọc `B[i]` rồi vào lệnh ở `o[i]`: chuỗi đã dịch nên `B[i]` dựng từ dữ
    liệu tới hết nến `i−1`, và lệnh khớp ở mở cửa nến `i`. Đúng.

    LIVE đứng ở nến `i` VỪA ĐÓNG và hỏi "có vào lệnh ở mở cửa nến `i+1` không?".
    Câu trả lời là tín hiệu THÔ tại nến `i`, tức `B[i+1]` của chuỗi đã dịch — một
    giá trị chưa tồn tại. Bản cũ đọc `B[i]` (`buy.iloc[-1]`), tức tín hiệu của nến
    TRƯỚC, nên mọi lệnh live vào TRỄ ĐÚNG MỘT NẾN.

    Đo bằng kiểm định parity: chân AccelGBPNZDH1 khớp điểm vào **0%** — mọi lệnh
    live lệch đúng một giờ so với backtest.

    Cách sửa: `live_decision` tắt phép dịch (`_SHIFT_ENABLED = False`) để đọc tín
    hiệu THÔ tại nến vừa đóng. Không đụng tới backtest, và không thêm tham số vào
    năm hàm `sig_*`.
    """
    if not _SHIFT_ENABLED:
        return s.astype("boolean").fillna(False).astype(bool)
    return s.shift(1).astype("boolean").fillna(False).astype(bool)


# ═══════════════════════════════════════════════════════ ba họ tín hiệu
def sig_rsi_div(df: pd.DataFrame, n: int, k: float
                ) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """PHÂN KỲ giá/RSI. Trả (mua, bán, giá trị tín hiệu).

    Giá lập đỉnh cao hơn `n` nến trước nhưng RSI KHÔNG theo → đà đang yếu đi dù giá
    còn lên → vào NGƯỢC. `k` là khoảng cách RSI tối thiểu để coi là phân kỳ thật.

    Đại lượng là QUAN HỆ giữa hai chuỗi, không phải mức của một chuỗi — đó là lý do
    nó độc lập với z-band về mặt cấu tạo, không chỉ về mặt thực nghiệm.
    """
    c = df["close"]
    r = rsi(c)
    price_high = c > c.rolling(n, min_periods=n // 2).max().shift(1)
    price_low = c < c.rolling(n, min_periods=n // 2).min().shift(1)
    rsi_weak = r < r.rolling(n, min_periods=n // 2).max().shift(1) - k
    rsi_strong = r > r.rolling(n, min_periods=n // 2).min().shift(1) + k
    # giá trị tín hiệu: RSI lệch bao nhiêu so với cực trị của chính nó
    val = r - r.rolling(n, min_periods=n // 2).max().shift(1)
    return _shift(price_low & rsi_strong), _shift(price_high & rsi_weak), val


def sig_streak(df: pd.DataFrame, n: int, k: float
               ) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """CHUỖI nến cùng chiều liên tiếp. Trả (mua, bán, độ dài chuỗi có dấu).

    Chuỗi đủ dài (`n` nến) → vào NGƯỢC. Giả thuyết: chuỗi dài phản ánh dòng lệnh
    một chiều đã cạn, và nến kế tiếp có xác suất đảo cao hơn.

    `k` lọc theo biên độ: chỉ tính chuỗi mà tổng dịch chuyển vượt k lần ATR·√n — để
    loại những chuỗi 5 nến toàn nến ruồi, vốn chỉ là nhiễu vi cấu trúc.
    """
    r = np.log(df["close"]).diff()
    sign = np.sign(r)
    streak = sign.groupby((sign != sign.shift()).cumsum()).cumcount() + 1
    a = atr(df) / df["close"]
    total_move = r.rolling(n, min_periods=n).sum().abs()
    long_enough = (streak >= n) & (total_move > k * a * np.sqrt(n))
    return _shift(long_enough & (sign < 0)), _shift(long_enough & (sign > 0)), streak * sign


def sig_vol_regime(df: pd.DataFrame, n: int, k: float
                   ) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """CHẾ ĐỘ BIẾN ĐỘNG: σ ngắn hạn so với σ dài hạn. Trả (mua, bán, tỷ số).

    Khi σ ngắn vọt lên quá `k` lần σ dài, thị trường vừa nhận cú sốc — và sau cú sốc
    thì giá thường hồi một phần. Vào NGƯỢC chiều cú sốc.

    Cược vào việc BIẾN ĐỘNG hồi quy, không phải giá hồi quy. Hai thứ này thực nghiệm
    gần như trực giao: |tương quan| với chân z-band cùng công cụ chỉ 0,119.
    """
    r = np.log(df["close"]).diff()
    vol_short = r.rolling(max(n // 4, 3), min_periods=2).std()
    vol_long = r.rolling(n, min_periods=n // 2).std()
    vol_ratio = vol_short / vol_long.replace(0, np.nan)
    shock = vol_ratio > k
    going_down = r.rolling(max(n // 4, 3), min_periods=2).sum() < 0
    return _shift(shock & going_down), _shift(shock & ~going_down), vol_ratio


def sig_accel(df: pd.DataFrame, n: int, k: float
              ) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """GIA TỐC giá — đạo hàm bậc HAI. Trả (mua, bán, z của gia tốc).

    Hiệu của hai lợi nhuận `n` nến liên tiếp, chuẩn hoá theo σ của chính nó. Mọi họ
    khác trong dự án đo bậc không (giá cách trung bình bao xa) hoặc bậc một (đà).
    Đây là họ duy nhất đo đà đang MẠNH LÊN hay CHẬM LẠI.

    Gia tốc âm mạnh = đà đang tắt nhanh → vào NGƯỢC chiều đà đang tắt.
    """
    lp = np.log(df["close"])
    r = lp - lp.shift(n)
    gt = r - r.shift(n)
    sd = gt.rolling(n * 4, min_periods=n * 2).std()
    z = gt / sd.replace(0, np.nan)
    return _shift(z < -k), _shift(z > k), z


SIGNALS: Dict[str, Callable] = {
    "rsi_div": sig_rsi_div, "streak": sig_streak, "vol_regime": sig_vol_regime,
    "accel": sig_accel,
}


# ═══════════════════════════════════════════════════════ mô phỏng theo lệnh
@dataclass
class BacktestResult:
    trades: pd.DataFrame
    pnl_daily: pd.Series
    cost_1rt_bps: float
    swap_bps_per_bar: float


def run(df: pd.DataFrame, cost_1rt_bps: float, swap_bps_per_bar: float,
        cfg: FamilyConfig) -> BacktestResult:
    """Một vị thế tại một thời điểm, không chồng lệnh.

    Thoát khi có tín hiệu NGƯỢC hoặc hết time-stop. Chi phí: một lượt khứ hồi đầy đủ
    mỗi lệnh, cộng swap cho mỗi nến giữ.
    """
    buy, sell, _ = SIGNALS[cfg.family](df, cfg.window, cfg.threshold)
    o, c = df["open"].to_numpy(), df["close"].to_numpy()
    B, S = buy.to_numpy(), sell.to_numpy()
    n = len(df)

    rows: List[Dict] = []
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
        reason_text = "EOD"
        while j < n - 1:
            j += 1
            if (side > 0 and S[j]) or (side < 0 and B[j]):
                reason_text = "REVERSE"
                break
            if j - i >= cfg.timestop_bars:
                reason_text = "TIMESTOP"
                break
        bars = j - i
        gross = side * (c[j] - entry) / entry * 1e4
        cost = cost_1rt_bps + bars * swap_bps_per_bar
        rows.append({"entry_time": df.index[i], "exit_time": df.index[j],
                     "side": side, "bars": bars, "reason": reason_text,
                     "entry_px": entry, "exit_px": c[j],
                     "gross_bps": gross, "cost_bps": cost,
                     "net_bps": gross - cost})
        # ⚠️ `j + 1`, KHÔNG phải `j` — sửa 15/08/2026, look-ahead phát hiện bằng
        # kiểm định parity (`execution/parity.py`).
        #
        # Bản cũ đặt `i = j`, nên lệnh KẾ TIẾP vào ở `o[j]` — giá MỞ CỬA của chính
        # nến vừa thoát ở `c[j]` (giá ĐÓNG CỬA). Mở cửa đến TRƯỚC đóng cửa, nên lệnh
        # mới vào trước khi lệnh cũ ra: không thực hiện được với `max_positions=1`,
        # và là nhìn trước dữ liệu.
        #
        # ĐO ĐƯỢC trên 22 chân một-công-cụ: 1.791/9.538 lệnh (18,8%) là loại này, và
        # chúng mang 27,0% tổng lãi. Sửa xong: Sharpe trung vị 0,815 → 0,748 (−9,6%),
        # 20/22 chân tệ đi, tổng net −13,6%. Chân StreakAUDCADM30 nặng nhất — 91,9%
        # số lệnh của nó là vào-lại-cùng-nến.
        i = j + 1

    T = pd.DataFrame(rows)
    d = (T.set_index("exit_time")["net_bps"].resample("1D").sum().fillna(0.0)
         if not T.empty else pd.Series(dtype=float))
    return BacktestResult(T, d, cost_1rt_bps, swap_bps_per_bar)


def stats(res: BacktestResult, cfg: FamilyConfig) -> Dict[str, object]:
    d, T = res.pnl_daily, res.trades
    if T.empty or len(d) < 60:
        return {"strategy": cfg.name, "n_trades": len(T)}

    def sh(s: pd.Series) -> float:
        sd = float(s.std(ddof=1))
        return round(float(s.mean()) / sd * np.sqrt(252), 3) if sd > 0 else np.nan

    cum = d.cumsum()
    yrs = max((d.index.max() - d.index.min()).days / 365.25, 1e-9)
    v = T["net_bps"]
    return {
        "strategy": cfg.name, "family": cfg.family, "instrument": cfg.instrument,
        "timeframe": cfg.timeframe,
        "sharpe_all": sh(d), "sharpe_form": sh(d[d.index < FORM_END]),
        "sharpe_oos": sh(d[d.index >= FORM_END]),
        "n_trades": len(T),
        "win_pct": round(float((v > 0).mean()) * 100, 1),
        "net_bps_per_trade": round(float(v.mean()), 2),
        "t_stat": round(float(v.mean()) / float(v.std(ddof=1)) * np.sqrt(len(v)), 2),
        "ann_pct": round(float(cum.iloc[-1]) / 100.0 / yrs, 2),
        "max_dd_pct": round(float((cum.cummax() - cum).max()) / 100.0, 2),
        "avg_bars_held": round(float(T["bars"].mean()), 1),
        "exit_mix": T["reason"].value_counts().to_dict(),
    }


def live_decision(df: pd.DataFrame, cost_1rt_bps: float, swap_bps_per_bar: float,
                  cfg: FamilyConfig, bars_held: int = 0,
                  side: int = 0) -> EntryDecision:
    """Quyết định cho nến ĐÃ ĐÓNG gần nhất. Cùng đường code với backtest.

    `side` là CHIỀU vị thế đang giữ: +1 mua · −1 bán · 0 không có.

    ⚠️ THAM SỐ `side` THÊM 15/08/2026 ĐỂ SỬA MỘT LỖI CÙNG HỌ VỚI LỖI CỦA Z-BAND.
    Bản trước thoát khi `b or s` — tức thoát khi có BẤT KỲ tín hiệu nào. Nhưng
    `run()` chỉ thoát khi tín hiệu NGƯỢC chiều:

        run()            `(side > 0 and S[j]) or (side < 0 and B[j])`
        live_decision()  `b or s`                          ← SAI

    Hệ quả: một vị thế MUA gặp tín hiệu MUA mới thì backtest GIỮ còn live THOÁT.
    Đo bằng kiểm định parity: chân AccelGBPNZDH1 khớp điểm vào **0%**, StreakGBPAUDH1
    khớp **14,3%** — tức live chạy một chuỗi lệnh gần như không liên quan gì tới
    chuỗi mà backtest đo.

    Cùng nguyên nhân gốc với lỗi Z-Band: điều kiện thoát ĐÚNG cần biết CHIỀU, mà
    hàm không nhận tham số đó, nên người viết lấp bằng một điều kiện không cần chiều.
    """
    # HAI BỘ TÍN HIỆU, VÌ BACKTEST DÙNG HAI QUY ƯỚC KHÁC NHAU cho vào và ra.
    #
    #     VÀO   `run()` đọc `B[i]` (đã dịch = thô tại i−1) rồi vào ở MỞ CỬA nến i.
    #           Live đứng ở nến i hỏi "vào ở mở cửa i+1 chứ?" → cần tín hiệu THÔ
    #           tại nến i.
    #     RA    `run()` đọc `S[j]` (đã dịch = thô tại j−1) rồi ra ở ĐÓNG CỬA nến j.
    #           Live đứng ở nến i và ra ngay tại đóng cửa i → cần tín hiệu ĐÃ DỊCH.
    #
    # Không đối xứng, và nó là đặc tính của backtest chứ không phải lựa chọn ở đây.
    # Dùng nhầm một trong hai làm lệnh lệch đúng MỘT NẾN: đo được chân
    # AccelGBPNZDH1 khớp 0% khi vào dùng chuỗi đã dịch, và VolRegimeGBPAUDH1 khớp
    # 27,8% khi ra dùng chuỗi thô.
    global _SHIFT_ENABLED
    _saved = _SHIFT_ENABLED
    _SHIFT_ENABLED = False
    try:
        buy_raw, sell_raw, val = SIGNALS[cfg.family](df, cfg.window, cfg.threshold)
    finally:
        _SHIFT_ENABLED = _saved
    buy_sh, sell_sh, _ = SIGNALS[cfg.family](df, cfg.window, cfg.threshold)

    b, s = bool(buy_raw.iloc[-1]), bool(sell_raw.iloc[-1])          # để VÀO
    b_x, s_x = bool(buy_sh.iloc[-1]), bool(sell_sh.iloc[-1])        # để RA
    v = float(val.iloc[-1]) if np.isfinite(val.iloc[-1]) else float("nan")

    if bars_held > 0:
        if bars_held >= cfg.timestop_bars:
            action, reason = "FLAT", (f"TIME-STOP: đã giữ {bars_held} ≥ "
                                      f"{cfg.timestop_bars} nến")
        elif (side > 0 and s_x) or (side < 0 and b_x):
            # ĐÚNG điều kiện của `run()`: chỉ tín hiệu NGƯỢC chiều mới đóng lệnh.
            # `side == 0` mà `bars_held > 0` là mâu thuẫn (đang giữ mà không rõ
            # chiều) — rơi xuống HOLD, và đối soát sổ sẽ phát hiện.
            action, reason = "FLAT", "xuất hiện tín hiệu NGƯỢC chiều"
        else:
            action, reason = "HOLD", "chưa có tín hiệu ngược, chưa hết time-stop"
    elif b:
        action, reason = "BUY", f"{cfg.family} kích hoạt chiều MUA (ngưỡng {cfg.threshold})"
    elif s:
        action, reason = "SELL", f"{cfg.family} kích hoạt chiều BÁN (ngưỡng {cfg.threshold})"
    else:
        action, reason = "FLAT", f"{cfg.family} chưa vượt ngưỡng {cfg.threshold}"

    return EntryDecision(
        timestamp=df.index[-1], strategy=cfg.name, family=cfg.family,
        instrument=cfg.instrument, timeframe=cfg.timeframe, action=action,
        price=float(df["close"].iloc[-1]), signal_value=v,
        threshold=cfg.threshold, window=cfg.window, bars_held=bars_held,
        timestop_bars=cfg.timestop_bars, est_cost_bps=cost_1rt_bps,
        est_swap_bps_per_bar=swap_bps_per_bar, reason=reason)


# ═══════════════════════════════════════════════════════ thẻ luật (một chỗ dựng)
# Mười chân thuộc bốn họ dưới đây trước 14/08/2026 mỗi file chép lại nguyên khối
# `RuleBook` 45 dòng. Luật của MỘT họ là như nhau ở mọi công cụ — chỉ tham số đổi —
# nên chép tay là mười bản sao của cùng một thứ, và sửa luật phải sửa mười chỗ.
#
# Bố cục nay theo hệ tiền nhiệm (`quant-xau/live_strategies/h1/xau_r_h1.py`): thẻ
# luật ĐỌC ĐƯỢC nằm trong docstring đầu file, thân file chỉ có hằng số và hàm. Khác
# biệt: ở đây docstring được SINH RA từ dữ liệu này nên nó không trôi khỏi code được.

_D = "D:/project-learning/documents/forex-strategies"

SOURCES_BY_FAMILY: Dict[str, Tuple[str, ...]] = {
    "rsi_div": (
        'Wilder (1978) "New Concepts in Technical Trading Systems", Trend Research — '
        'KHÔNG có bản gốc trong kho; RSI cài lại từ định nghĩa gốc ở '
        '`shared/indicators.py`',
    ),
    "streak": (
        'Lo & MacKinlay (1990) "When Are Contrarian Profits Due to Stock Market '
        f'Overreaction?", Review of Financial Studies 3(2) — KHÔNG có bản gốc trong '
        f'kho, trích gián tiếp qua {_D}/2607.19497v1.md',
    ),
    "vol_regime": (
        'Cont (2001) "Empirical properties of asset returns: stylized facts and '
        'statistical issues", Quantitative Finance 1(2) — KHÔNG có bản gốc trong kho, '
        f'dẫn lại trong {_D}/1404.3274v1.md',
    ),
    "accel": (
        'Carver (2015) "Systematic Trading", Harriman House — quy tắc "accel" = đạo '
        'hàm của EWMAC; bản cài đặt ở '
        '`project-refer/carver-systematic-trading/core/forecast.py`. Ở đây dùng NGƯỢC '
        'chiều Carver',
        'Sepp & Lucic (2026) "The Science and Practice of Trend-Following Systems", '
        f'arXiv:2607.19497v1 — {_D}/2607.19497v1.pdf',
    ),
}

FAMILY_LABEL: Dict[str, str] = {
    "rsi_div": "Phân kỳ giá/RSI (quan hệ giữa hai chuỗi)",
    "streak": "Chuỗi nến cùng chiều (đếm, miễn nhiễm với độ lớn)",
    "vol_regime": "Chế độ biến động (tỷ số σ ngắn / σ dài)",
    "accel": "Gia tốc giá (đạo hàm bậc hai)",
}


def _indicators(cfg: FamilyConfig) -> Tuple[str, ...]:
    n, f = cfg.window, cfg.family
    if f == "rsi_div":
        return (f"RSI(14) của giá đóng cửa",
                f"cực trị {n} nến của GIÁ và của RSI, so riêng")
    if f == "streak":
        return ("số nến cùng dấu liên tiếp (chuỗi)",
                "ATR(14) chuẩn hoá theo giá, để lọc chuỗi nến ruồi")
    if f == "vol_regime":
        return (f"σ ngắn hạn: độ lệch chuẩn lợi nhuận log {max(n // 4, 3)} nến",
                f"σ dài hạn: độ lệch chuẩn {n} nến")
    return (f"lợi nhuận log {n} nến, và hiệu của hai lợi nhuận liên tiếp",
            f"σ({n * 4} nến) của gia tốc, để chuẩn hoá")


def _entry_rules(cfg: FamilyConfig) -> Tuple[RB.Rule, ...]:
    n, k, f = cfg.window, cfg.threshold, cfg.family
    if f == "rsi_div":
        return (
            RB.Rule("a", f"giá lập cực trị mới so với {n} nến trước"),
            RB.Rule("b", f"RSI lệch ít nhất {k} điểm khỏi cực trị RSI cùng cửa sổ"),
            RB.Rule("c", f"giá ĐÁY mới + RSI cao hơn đáy RSI ≥ {k} điểm → MUA · "
                         f"giá ĐỈNH mới + RSI thấp hơn đỉnh RSI ≥ {k} điểm → BÁN"),
        )
    if f == "streak":
        return (
            RB.Rule("a", f"chuỗi ≥ {n} nến cùng chiều liên tiếp"),
            RB.Rule("b", f"tổng dịch chuyển > {k} × ATR × √{n}"),
            RB.Rule("c", f"chuỗi {n} nến GIẢM → MUA · {n} nến TĂNG → BÁN"),
        )
    if f == "vol_regime":
        return (
            RB.Rule("a", f"σ({max(n // 4, 3)} nến) / σ({n} nến) > {k}"),
            RB.Rule("b", f"tổng lợi nhuận {max(n // 4, 3)} nến gần nhất < 0 → MUA · "
                         f"> 0 → BÁN"),
        )
    return (
        RB.Rule("a", f"gia tốc = lợi nhuận({n} nến) − lợi nhuận({n} nến trước đó), "
                     f"chuẩn hoá theo σ của chính nó"),
        RB.Rule("b", f"|z(gia tốc)| > {k}"),
        RB.Rule("c", f"z < −{k} → MUA · z > +{k} → BÁN"),
    )


def rulebook(cfg: FamilyConfig, *, expectancy: str, frequency: str) -> RB.RuleBook:
    """Thẻ luật của MỘT chân, dựng từ chính `cfg` mà backtest và live đang dùng."""
    tf = cfg.timeframe
    return RB.RuleBook(
        name=cfg.name,
        signal_tf=tf, execution_tf=tf, direction="BOTH",
        universe=(cfg.instrument,), traded=(cfg.instrument,), max_positions=1,
        family=FAMILY_LABEL[cfg.family],
        source=" · ".join(SOURCES_BY_FAMILY[cfg.family]),
        hours_utc="mọi giờ",
        forbidden_hours_utc=(),
        indicators=_indicators(cfg),
        entry_logic="ALL",
        entry_rules=_entry_rules(cfg),
        entry_price="khớp tại giá MỞ CỬA nến kế tiếp sau nến tín hiệu",
        exit_rules=(
            RB.Rule("x1", "xuất hiện tín hiệu NGƯỢC chiều"),
            RB.Rule("x2", f"time-stop {cfg.timestop_bars} nến {tf}"),
        ),
        stop_loss="KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop",
        take_profit="không có — thoát theo tín hiệu hoặc time-stop",
        blocks=("spread ước lượng cho cross — phải đo lại trên tài khoản thật",),
        frequency=frequency,
        avg_holding=f"tối đa {cfg.timestop_bars} nến {tf}",
        expectancy=expectancy,
        trace_signal_name="signal_value",
    )
