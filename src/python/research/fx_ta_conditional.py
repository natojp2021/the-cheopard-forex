"""fx_ta_conditional.py — TA CÓ ĐIỀU KIỆN trên EURUSD + GBPUSD.

VÌ SAO VÒNG NÀY, SAU KHI 78/80 TỔ HỢP TA THUẦN THẤT BẠI
========================================================
`fx_ta_lab` quét 10 trường phái × 2 cặp × 4 khung. Kết quả (vòng 43):

    HỒI QUY     trung bình −0,204   tốt nhất **+0,351** (rsi_mr EURUSD H4)
    BIẾN ĐỘNG   trung bình −0,368   tốt nhất  +0,163
    XU HƯỚNG    trung bình −0,500   tốt nhất  +0,092

Một thông tin dùng được nằm trong đó: **chỉ nhóm HỒI QUY có dấu hiệu sống**, và nó
sống trên cặp rẻ nhất (EURUSD) ở khung mà phí qua đêm chưa đè nặng (H4). Nhóm xu
hướng thì âm ở 40/40 — không phải vì phí mà vì **lãi gộp đã âm trước khi trả phí**.

Vòng này KHÔNG chạy lại các trường phái đó. Nó làm hai việc khác:

  A. **ĐIỀU KIỆN HOÁ tín hiệu hồi quy.** Một tín hiệu Sharpe 0,35 có hai cách hỏng:
     nó yếu ở mọi lúc, hoặc nó mạnh ở một số lúc và âm ở lúc khác. Hai trường hợp
     đó cần phản ứng ngược nhau, và trung bình toàn kỳ không phân biệt được. Ba
     điều kiện được thử, mỗi cái có nguồn:
       * PHIÊN — cấu trúc phiên FX đo được rất mạnh và ổn định
         (`reports/fx_recon/session_profile.csv`: biên độ H1 giờ 13-14 UTC gấp 3-4
         lần giờ 21-23 trên mọi cặp)
       * CHẾ ĐỘ BIẾN ĐỘNG — hồi quy hoạt động khi thị trường đi ngang, thất bại khi
         có xu hướng mạnh (Brière & Drut đo được cấu trúc đảo vai này trên carry/PPP)
       * BỘ LỌC KHUNG CAO — chỉ fade khi khung trên KHÔNG có xu hướng (nguyên tắc
         chuẩn của phân tích đa khung)

  B. **PHÁ VỠ BIÊN PHIÊN.** Chưa từng thử đúng cách trên EU/GU. Đây là hướng duy
     nhất còn lại có cơ chế thanh khoản rõ ràng: phiên Á mỏng tạo biên hẹp, thanh
     khoản London vào lúc 07:00-08:00 UTC tạo cú phá. Tôi đã tìm và ghi nhận rằng
     hướng này **không có nền bình duyệt** (`02_kien_thuc_nen_internet.md` §4.6) —
     nên nó vào đây như một phép thử, không như một giả thuyết có nguồn.

KỶ LUẬT ĐẾM PHÉP THỬ
=====================
Vòng này thêm ~40 phép thử vào tổng số. Cộng với 80 của vòng 43 và các vòng trước,
ngưỡng ý nghĩa phải chặt: một ô Sharpe 0,4 trong 120 phép thử **không** là phát hiện.
Cổng dùng ở đây: FORM > 0 **và** OOS > 0 **và** ALL > 0,5 — cao hơn ngưỡng 0,3 của
vòng 43 đúng vì số phép thử đã tăng.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.python.research import fx_ta_lab as TA

FORM_END = TA.FORM_END

# Phiên theo giờ UTC — ranh giới lấy từ cấu trúc thanh khoản ĐO ĐƯỢC, không phải
# quy ước sách vở. Xem `reports/fx_recon/session_profile.csv`.
SESSIONS: Dict[str, Tuple[int, int]] = {
    "ASIA": (0, 7),        # mỏng nhất, biên độ nhỏ nhất
    "LONDON": (7, 12),     # thanh khoản vào
    "OVERLAP": (12, 16),   # London+NY, biên độ LỚN NHẤT
    "NY": (16, 20),
    "ROLLOVER": (20, 24),  # spread giãn 1,4-3 lần — vùng cấm
}


def session_mask(index: pd.DatetimeIndex, names: Sequence[str]) -> pd.Series:
    h = index.hour
    m = np.zeros(len(index), dtype=bool)
    for n in names:
        lo, hi = SESSIONS[n]
        m |= (h >= lo) & (h < hi)
    return pd.Series(m, index=index)


# ═══════════════════════════════════════════════════════ A. điều kiện hoá
def gate_session(bars: TA.Bars, pos: pd.Series,
                 allow: Sequence[str]) -> pd.Series:
    """Chỉ MỞ vị thế mới trong phiên cho phép; vị thế đã mở được giữ tới khi tín
    hiệu gốc đóng.

    Phân biệt "mở" và "giữ" là điểm quan trọng: chặn cả việc giữ sẽ biến bộ lọc
    phiên thành một luật thoát, và khi đó ta đo lẫn hai thứ.
    """
    ok = session_mask(bars.df.index, allow).to_numpy()
    p = pos.to_numpy()
    out = np.zeros(len(p))
    s = 0
    for i in range(len(p)):
        if s == 0:
            if p[i] != 0 and ok[i]:
                s = p[i]
        else:
            if p[i] == 0 or np.sign(p[i]) != np.sign(s):
                s = p[i] if (p[i] != 0 and ok[i]) else 0
        out[i] = s
    return pd.Series(out, index=pos.index)


def gate_vol_regime(bars: TA.Bars, pos: pd.Series, *, low: bool = True,
                    quantile: float = 0.5, window: int = 500) -> pd.Series:
    """Chỉ giao dịch khi biến động ở nửa THẤP (`low=True`) hoặc CAO của lịch sử.

    Ngưỡng là phân vị TRƯỢT của `window` nến TRƯỚC — nhân quả, chạy được ở live.
    Phân vị toàn mẫu sẽ dùng thông tin tương lai.
    """
    atr = bars.df["atr14"] / bars.df["close"]
    thr = atr.shift(1).rolling(window, min_periods=window // 4).quantile(quantile)
    ok = (atr.shift(1) <= thr) if low else (atr.shift(1) >= thr)
    return (pos * ok.fillna(False).astype(float)).fillna(0.0)


def gate_htf_range(bars: TA.Bars, pos: pd.Series, *,
                   adx_max: float = 25.0) -> pd.Series:
    """Chỉ fade khi thị trường KHÔNG có xu hướng mạnh (ADX dưới ngưỡng).

    Đây là dùng ADX làm BỘ LỌC CHẾ ĐỘ, đúng cách Wilder đề xuất — không phải làm
    trigger vào lệnh. HELIX trong `project-refer/tradingsystem` bị deprecate chính
    vì dùng chỉ báo chế độ làm trigger.
    """
    ok = bars.df["adx"].shift(1) < adx_max
    return (pos * ok.fillna(False).astype(float)).fillna(0.0)


# ═══════════════════════════════════════════════════════ B. phá vỡ biên phiên
def sig_session_breakout(bars: TA.Bars, *, range_session: str = "ASIA",
                         trade_session: str = "LONDON",
                         buffer_atr: float = 0.0,
                         exit_at_session_end: bool = True) -> pd.Series:
    """Lấy biên cao/thấp của `range_session`, giao dịch phá vỡ trong `trade_session`.

    Cơ chế được viện dẫn rộng rãi: phiên Á thanh khoản mỏng nên biên hẹp; khi
    thanh khoản châu Âu vào, cú phá biên đó đi tiếp. **Không có nền bình duyệt** —
    tôi đã tìm và chỉ thấy blog/broker (`02_kien_thuc_nen_internet.md` §4.6). Vào đây
    như phép thử, không như giả thuyết có nguồn.

    `buffer_atr` > 0 đòi giá phá thêm một phần ATR — chống phá vỡ giả sát biên.
    """
    b = bars.df
    day = b.index.normalize()
    r_lo, r_hi = SESSIONS[range_session]
    t_lo, t_hi = SESSIONS[trade_session]
    in_range = (b.index.hour >= r_lo) & (b.index.hour < r_hi)
    in_trade = (b.index.hour >= t_lo) & (b.index.hour < t_hi)

    hi = pd.Series(np.where(in_range, b["high"], np.nan), index=b.index)
    lo = pd.Series(np.where(in_range, b["low"], np.nan), index=b.index)
    rng_hi = hi.groupby(day).transform("max")
    rng_lo = lo.groupby(day).transform("min")
    buf = buffer_atr * b["atr14"]

    long_e = pd.Series(in_trade, index=b.index) & (b["close"] > rng_hi + buf)
    short_e = pd.Series(in_trade, index=b.index) & (b["close"] < rng_lo - buf)

    p = np.zeros(len(b))
    s = 0
    cur_day = None
    le = long_e.fillna(False).to_numpy()
    se = short_e.fillna(False).to_numpy()
    it = np.asarray(in_trade)
    for i in range(len(b)):
        d = day[i]
        if d != cur_day:
            cur_day, s = d, 0
        if exit_at_session_end and not it[i]:
            s = 0
        elif s == 0:
            if le[i]:
                s = 1
            elif se[i]:
                s = -1
        p[i] = s
    return pd.Series(p, index=b.index)


def sig_prev_day_breakout(bars: TA.Bars, *, buffer_atr: float = 0.1,
                          hold_bars: int = 0) -> pd.Series:
    """Phá đỉnh/đáy NGÀY TRƯỚC (pivot cổ điển; Crabel).

    Khác `sig_session_breakout` ở chỗ biên tham chiếu là cả ngày trước, không phải
    một phiên trong ngày — nên nó là tín hiệu chậm hơn, ít nhiễu hơn.
    """
    b = bars.df
    day = b.index.normalize()
    dh = b["high"].groupby(day).transform("max").groupby(day).first()
    dl = b["low"].groupby(day).transform("min").groupby(day).first()
    prev_h = dh.shift(1).reindex(day).to_numpy()
    prev_l = dl.shift(1).reindex(day).to_numpy()
    if hold_bars <= 0:
        hold_bars = {"M30": 24, "H1": 12, "H4": 3, "D1": 2}[bars.timeframe]
    buf = (buffer_atr * b["atr14"]).to_numpy()
    c = b["close"].to_numpy()

    p = np.zeros(len(b))
    s, held = 0, 0
    for i in range(len(b)):
        if s != 0:
            held += 1
            if held >= hold_bars:
                s, held = 0, 0
        if s == 0 and np.isfinite(prev_h[i]):
            if c[i] > prev_h[i] + buf[i]:
                s, held = 1, 0
            elif c[i] < prev_l[i] - buf[i]:
                s, held = -1, 0
        p[i] = s
    return pd.Series(p, index=b.index)


def sig_confluence_mr(bars: TA.Bars, *, need: int = 2) -> pd.Series:
    """Hồi quy đòi `need` chỉ báo ĐỒNG THUẬN cùng lúc, thay vì từng cái riêng.

    Ba phiếu: RSI ngoài 30/70 · giá ngoài dải Bollinger · Stochastic ngoài 20/80.
    Giả thuyết: mỗi chỉ báo đơn lẻ nhiễu, nhưng nhiễu của chúng độc lập một phần
    nên đòi đồng thuận sẽ lọc được nhiễu mà giữ tín hiệu.

    Thoát khi giá về đường giữa Bollinger — một luật thoát duy nhất cho mọi cấu
    hình, để `need` là biến duy nhất thay đổi.
    """
    b = bars.df
    c = b["close"]
    vote_lo = ((b["rsi"] < 30).astype(int) + (c < b["bb_dn"]).astype(int)
               + (b["stoch"] < 20).astype(int))
    vote_hi = ((b["rsi"] > 70).astype(int) + (c > b["bb_up"]).astype(int)
               + (b["stoch"] > 80).astype(int))
    was_lo = (vote_lo.shift(1) >= need) & (vote_lo < need)
    was_hi = (vote_hi.shift(1) >= need) & (vote_hi < need)
    return TA._state_machine(was_lo.shift(1), was_hi.shift(1),
                             (c >= b["bb_mid"]).shift(1),
                             (c <= b["bb_mid"]).shift(1))


def sig_mtf_mr(bars: TA.Bars, bars_htf: TA.Bars) -> pd.Series:
    """Hồi quy Bollinger ở khung hiện tại, CHỈ khi khung CAO đi ngang (ADX < 25).

    Bộ lọc khung cao được lấy bằng `reindex(..., method="ffill")` trên nhãn thời
    gian của khung thấp — tức chỉ dùng giá trị khung cao ĐÃ ĐÓNG tại thời điểm đó,
    không phải giá trị của nến khung cao đang hình thành.
    """
    base = TA.sig_bb_mr(bars)
    adx_h = bars_htf.df["adx"].reindex(bars.df.index, method="ffill")
    ok = adx_h.shift(1) < 25.0
    return (base * ok.fillna(False).astype(float)).fillna(0.0)
