"""zband_core.py — ĐỘNG CƠ DÙNG CHUNG cho họ chiến lược Z-Band Mean Reversion.

VÌ SAO MỘT ĐỘNG CƠ, NHIỀU MODULE MỎNG
======================================
Sáu chiến lược M30/H1 vừa qua kiểm định dùng CHUNG một luật (vào khi |z| > k, thoát
khi z về 0 hoặc hết time-stop) nhưng KHÁC công cụ và khác tham số. Hai cách tổ chức:

    một module cho cả sáu     → registry chỉ thấy MỘT chiến lược, không quản được
                                 vòng đời riêng của từng cái, không tắt riêng được
    sáu module chép lại luật  → sửa một lỗi phải sửa sáu chỗ, và sẽ có chỗ bị bỏ sót

Cách ở đây: động cơ nằm một chỗ, mỗi chiến lược là một module MỎNG chỉ chứa `CONFIG`
và `RULEBOOK`. Registry thấy sáu chiến lược độc lập; lỗi logic chỉ có một chỗ để sai.
Đây cũng là cách `quant-xau/live_strategies` tổ chức: mỗi chiến lược một file với
tham số riêng, phần tính toán chung nằm ở helper dùng chung.

LUẬT — ĐẦY ĐỦ, KHÔNG CÓ THAM SỐ ẨN
===================================
    Mỗi nến đã đóng:
      1. z = (log giá − trung bình N nến) / độ lệch chuẩn N nến
      2. VÀO khi |z| > k VÀ nến TRƯỚC cũng đã ngoài dải (|z(t−1)| > k)
         · z < −k → MUA   · z > +k → BÁN
         · khớp tại giá MỞ CỬA nến kế tiếp
      3. THOÁT khi ĐẠT MỘT trong ba:
         · z về 0 (hồi quy đã xảy ra) — CHỈ KHI `exit_at_mean=True`
         · có tín hiệu NGƯỢC chiều
         · giữ đủ `timestop_mult × N` nến (TIME-STOP)
      4. KHÔNG có cắt lỗ theo giá — xem §"vì sao không có SL"

VÌ SAO KHÔNG CÓ CẮT LỖ THEO GIÁ
================================
Đo được hai lần độc lập trên chính dữ liệu này:

    vòng 57 (8 họ × 27 công cụ)   H1 hồi quy: time_only +0,035 · SL+TP 1,5ATR −2,308
                                                        · SL+BE −4,264
    vòng 59 (công cụ đã chọn)     H1: time_only +0,070 · sl3atr_tp2R −0,272
                                  M30: time_only −0,092 · sl3atr_tp2R −0,604

Tỷ lệ thắng cũng nói cùng một chuyện: 51,9% với time-stop so với 46,5% khi có SL.
Cơ chế: chiến lược hồi quy vào lệnh KHI GIÁ ĐANG ĐI NGƯỢC, nên SL đặt gần luôn bị
chạm đúng lúc trước khi hồi. Đây khớp với Zheng Nan (2025), người đo được time-stop
hơn stop 3σ **+85%** trên vũ trụ cross.

Rủi ro vì vậy được kiểm soát ở tầng CỠ VỊ THẾ và time-stop, không ở tầng giá.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.python.strategies import rulebook as RB

FORM_END = pd.Timestamp("2024-01-01")
BARS_PER_DAY = {"M30": 48, "H1": 24, "H4": 6}


@dataclass(frozen=True)
class ZBandConfig:
    """Cấu hình một chiến lược Z-Band. Mọi tham số đều lộ, không có mặc định ẩn."""
    name: str
    instrument: str               # cross tổng hợp, vd "AUDCAD"
    timeframe: str                # M30 | H1
    window_bars: int              # N — cửa sổ tính z
    entry_sigma: float            # k — ngưỡng vào
    timestop_mult: float          # time-stop = timestop_mult × N nến
    # Thoát khi z về 0 hay giữ đến time-stop. Đây là tham số THẬT, không phải tinh
    # chỉnh: với cửa sổ dài (96 nến H4 = 16 ngày giao dịch) thì z chạm 0 rất sớm so
    # với biên độ hồi quy còn lại, và thoát ở đó bỏ lại phần lớn lợi nhuận trên bàn.
    # Đo được trên GBPCAD H4: thoát ở z=0 cho net 25,41 bps/lệnh, giữ đến time-stop
    # cho 60,32 — cùng 54 lệnh. Với cửa sổ ngắn thì ngược lại, nên phải khai rõ.
    exit_at_mean: bool = True
    # THỜI ĐIỂM vào lệnh trong một lần lệch. Hai luật, khác nhau ở chỗ có đợi hồi
    # quy BẮT ĐẦU hay không:
    #
    #   "outside"  |z| > k VÀ nến trước cũng ngoài dải — vào KHI CÒN đang lệch.
    #              Giá vào tốt hơn, nhưng lệch có thể giãn tiếp.
    #   "reenter"  nến trước ngoài dải VÀ |z| ĐÃ về trong dải — đợi z quay LẠI rồi
    #              mới vào. Giá vào tệ hơn, đổi lấy bằng chứng hồi quy đã khởi động.
    #
    # "reenter" là luật của Zheng Nan · "Profitability of Pairs Trading Based on
    # Cointegration in the FX Market" · MSc thesis 2025 · §4.3.1, nêu rõ KHÔNG vào
    # khi giá vừa xuyên RA dải.
    #
    # Mặc định giữ "outside" — đổi mặc định phải có bảng đo trên ĐA SỐ chân, theo
    # đúng bài học `exit_at_mean=False` (Sharpe 0,815 → 0,865 nhưng chỉ tốt hơn ở
    # 1/7 chân, tức là bậc tự do chứ không phải phát hiện).
    entry_mode: str = "outside"
    broker_markup_pct: float = 1.0


@dataclass
class EntryDecision:
    """Bản ghi quy tắc vào lệnh — đủ để TÁI LẬP quyết định từ chính bản ghi.

    Ghi cả trạng thái các cổng, không chỉ kết quả: khi một lệnh thua bất thường phải
    phân biệt được "luật chạy đúng, thị trường đi ngược" với "một cổng đã hỏng".
    """
    timestamp: pd.Timestamp
    strategy: str
    instrument: str
    timeframe: str
    action: str                   # BUY | SELL | HOLD | FLAT
    price: float
    z_score: float
    z_prev: float
    mu: float
    sigma: float
    window_bars: int
    entry_sigma: float
    was_outside_band: bool
    bars_held: int
    timestop_bars: int
    est_cost_bps: float
    est_swap_bps_per_bar: float
    reason: str

    def to_row(self) -> Dict[str, object]:
        d = {k: v for k, v in self.__dict__.items()}
        d["timestamp"] = str(self.timestamp)
        return d

    def explain(self) -> str:
        return (f"[{self.timestamp}] {self.strategy}/{self.instrument} "
                f"{self.action} @ {self.price:.5f} · z={self.z_score:+.2f} "
                f"(ngưỡng ±{self.entry_sigma}) · ngoài dải trước={self.was_outside_band} "
                f"· giữ {self.bars_held}/{self.timestop_bars} nến · {self.reason}")


# ═══════════════════════════════════════════════════════ tín hiệu
def zscore(close: pd.Series, window: int) -> pd.Series:
    """z của log giá trên cửa sổ trượt. Giá trị tại nến t chỉ dùng nến đến t."""
    lp = np.log(close)
    mu = lp.rolling(window, min_periods=window // 2).mean()
    sd = lp.rolling(window, min_periods=window // 2).std(ddof=1)
    return (lp - mu) / sd.replace(0, np.nan)


def entry_signals(close: pd.Series, cfg: ZBandConfig
                  ) -> Tuple[pd.Series, pd.Series]:
    """(vào MUA, vào BÁN) — đã dịch một nến, khớp tại mở cửa nến kế tiếp.

    `.shift(1)` ở cuối là điều làm chuỗi này chạy được live: quyết định tại nến t chỉ
    dùng thông tin đến hết nến t−1, và lệnh khớp tại mở cửa nến t.
    """
    z = zscore(close, cfg.window_bars)
    if cfg.entry_mode == "reenter":
        # Luật Zheng: nến trước NGOÀI dải, nến này ĐÃ về trong dải → hồi quy đã bắt
        # đầu. Chiều lấy theo dấu của z_prev, vì z hiện tại đã về gần 0 và dấu của
        # nó không còn nói được lệch ban đầu nằm phía nào.
        zp = z.shift(1)
        back_in = z.abs() <= cfg.entry_sigma
        buy = (zp < -cfg.entry_sigma) & back_in
        sell = (zp > cfg.entry_sigma) & back_in
    else:
        outside_prev = z.shift(1).abs() > cfg.entry_sigma
        buy = (z < -cfg.entry_sigma) & outside_prev
        sell = (z > cfg.entry_sigma) & outside_prev
    # Ép kiểu bool TRƯỚC khi fillna: `shift` trên chuỗi bool sinh mảng object có NaN,
    # và fillna trên object phát FutureWarning hạ kiểu ngầm ở pandas 3.
    return (buy.shift(1).astype("boolean").fillna(False).astype(bool),
            sell.shift(1).astype("boolean").fillna(False).astype(bool))


# ═══════════════════════════════════════════════════════ mô phỏng theo lệnh
@dataclass
class BacktestResult:
    trades: pd.DataFrame
    pnl_daily: pd.Series
    cost_1rt_bps: float
    swap_bps_per_bar: float


def run(df: pd.DataFrame, cost_1rt_bps: float, swap_bps_per_bar: float,
        cfg: ZBandConfig) -> BacktestResult:
    """Mô phỏng THEO LỆNH: một vị thế tại một thời điểm, không chồng lệnh.

    Chi phí: mỗi lệnh trả MỘT lượt khứ hồi đầy đủ (spread + commission) cộng swap cho
    mỗi nến giữ. Không có giả định "khớp giữa spread".
    """
    o = df["open"].to_numpy()
    c = df["close"].to_numpy()
    buy, sell = entry_signals(df["close"], cfg)
    z = zscore(df["close"], cfg.window_bars).to_numpy()
    B, S = buy.to_numpy(), sell.to_numpy()
    n = len(df)
    ts = max(int(cfg.window_bars * cfg.timestop_mult), 2)

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
        exit_px, reason = None, ""
        while j < n - 1:
            j += 1
            zj = z[j]
            if cfg.exit_at_mean and np.isfinite(zj) and (
                    (side > 0 and zj >= 0.0) or (side < 0 and zj <= 0.0)):
                exit_px, reason = c[j], "MEAN"          # z về 0
                break
            if (side > 0 and S[j]) or (side < 0 and B[j]):
                exit_px, reason = c[j], "REVERSE"
                break
            if j - i >= ts:
                exit_px, reason = c[j], "TIMESTOP"
                break
        if exit_px is None:
            exit_px, reason, j = c[n - 1], "EOD", n - 1

        bars = j - i
        gross = side * (exit_px - entry) / entry * 1e4
        cost = cost_1rt_bps + bars * swap_bps_per_bar
        rows.append({"entry_time": df.index[i], "exit_time": df.index[j],
                     "side": side, "bars": bars, "reason": reason,
                     "entry_px": entry, "exit_px": exit_px,
                     "z_entry": float(z[i - 1]) if i > 0 else np.nan,
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
    daily = (T.set_index("exit_time")["net_bps"].resample("1D").sum().fillna(0.0)
             if not T.empty else pd.Series(dtype=float))
    return BacktestResult(T, daily, cost_1rt_bps, swap_bps_per_bar)


def stats(res: BacktestResult, cfg: ZBandConfig) -> Dict[str, object]:
    d = res.pnl_daily
    T = res.trades
    if T.empty or len(d) < 60:
        return {"strategy": cfg.name, "n_trades": len(T)}

    def sh(s: pd.Series) -> float:
        sd = float(s.std(ddof=1))
        return round(float(s.mean()) / sd * np.sqrt(252), 3) if sd > 0 else np.nan

    cum = d.cumsum()
    yrs = max((d.index.max() - d.index.min()).days / 365.25, 1e-9)
    v = T["net_bps"]
    return {
        "strategy": cfg.name, "instrument": cfg.instrument,
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


# ═══════════════════════════════════════════════════════ live
def live_decision(df: pd.DataFrame, cost_1rt_bps: float, swap_bps_per_bar: float,
                  cfg: ZBandConfig, bars_held: int = 0,
                  side: int = 0) -> EntryDecision:
    """Quyết định cho nến ĐÃ ĐÓNG gần nhất. Cùng đường code với backtest.

    `bars_held` là số nến đã giữ vị thế hiện tại (0 = đang không có vị thế) — bên gọi
    truyền vào từ trạng thái thật của tài khoản, module này không tự giữ trạng thái.

    `side` là CHIỀU vị thế đang giữ: +1 mua · −1 bán · 0 không có.

    ⚠️ THAM SỐ `side` THÊM 15/08/2026 ĐỂ SỬA MỘT LỖI NGHIÊM TRỌNG.
    Bản trước kiểm lối thoát "z về 0" bằng `abs(z) < 1e-9`, tức đòi z ĐÚNG BẰNG 0.
    z là số thực liên tục nên điều kiện ấy gần như KHÔNG BAO GIỜ đúng, và lối thoát
    MEAN chưa từng kích hoạt ở live — mọi lệnh chạy tới time-stop.

    Backtest thì kiểm z ĐI QUA 0 theo chiều có lợi (`zj >= 0` cho lệnh mua). Đo được
    trên 12 chân Z-Band: **88% số lệnh thoát bằng MEAN**, và chúng mang **280% tổng
    lãi** — phần còn lại (time-stop) lỗ ròng. Nghĩa là live sẽ chạy một chiến lược
    khác hẳn backtest, và là bản thua lỗ.

    Điều kiện đúng cần biết CHIỀU, mà bản cũ không nhận tham số đó — nên lỗi này
    không phải lỗi đánh máy, nó là một tham số bị bỏ quên rồi lấp bằng một điều kiện
    không cần chiều. `execution/parity.py` tìm ra nó.
    """
    z = zscore(df["close"], cfg.window_bars)
    lp = np.log(df["close"])
    mu = lp.rolling(cfg.window_bars, min_periods=cfg.window_bars // 2).mean()
    sd = lp.rolling(cfg.window_bars, min_periods=cfg.window_bars // 2).std(ddof=1)
    z_now = float(z.iloc[-1])
    z_prev = float(z.iloc[-2]) if len(z) > 1 else np.nan
    ts = max(int(cfg.window_bars * cfg.timestop_mult), 2)
    was_out = bool(np.isfinite(z_prev) and abs(z_prev) > cfg.entry_sigma)

    if not np.isfinite(z_now):
        action, reason = "FLAT", "chưa đủ dữ liệu để tính z"
    elif bars_held > 0:
        if bars_held >= ts:
            action, reason = "FLAT", f"TIME-STOP: đã giữ {bars_held} ≥ {ts} nến"
        elif cfg.exit_at_mean and side != 0 and (
                (side > 0 and z_now >= 0.0) or (side < 0 and z_now <= 0.0)):
            # ĐÚNG điều kiện của `run()`: z ĐI QUA 0 theo chiều có lợi, không phải
            # z bằng 0. Cần `side` mới kiểm được — xem docstring.
            action, reason = "FLAT", f"z = {z_now:+.2f} đã qua 0 — hồi quy xảy ra"
        else:
            action = "HOLD"
            reason = (f"giữ vị thế, z = {z_now:+.2f}"
                      + (" chưa về 0" if cfg.exit_at_mean
                         else f" — giữ đến time-stop {ts} nến, KHÔNG thoát ở z=0"))
    elif cfg.entry_mode == "reenter":
        # PHẢI khớp từng nhánh với `entry_signals` ở trên. Hai bản lệch nhau là lỗi
        # parity: backtest và live cùng đọc một cấu hình mà ra hai quyết định khác
        # nhau, và không test đơn lẻ nào bắt được vì mỗi bên tự nhất quán.
        if not was_out:
            action, reason = "FLAT", ("nến trước chưa ra ngoài dải — chưa có lệch "
                                      "nào để hồi")
        elif abs(z_now) > cfg.entry_sigma:
            action, reason = "FLAT", (f"z = {z_now:+.2f} CÒN ngoài dải — đợi z quay "
                                      f"lại trong ±{cfg.entry_sigma} mới vào")
        else:
            action = "BUY" if z_prev < 0 else "SELL"
            reason = (f"z từ {z_prev:+.2f} đã QUAY LẠI {z_now:+.2f} trong dải "
                      f"±{cfg.entry_sigma} → hồi quy đã bắt đầu, vào theo chiều hồi")
    elif abs(z_now) <= cfg.entry_sigma:
        action, reason = "FLAT", (f"|z| = {abs(z_now):.2f} chưa vượt ngưỡng "
                                  f"{cfg.entry_sigma}")
    elif not was_out:
        action, reason = "FLAT", ("nến trước CHƯA ngoài dải — chống vào lại liên tục "
                                  "khi z dao động quanh ngưỡng")
    else:
        action = "BUY" if z_now < 0 else "SELL"
        reason = (f"z = {z_now:+.2f} vượt ngưỡng ±{cfg.entry_sigma} và nến trước "
                  f"cũng ngoài dải → vào NGƯỢC chiều lệch")

    return EntryDecision(
        timestamp=df.index[-1], strategy=cfg.name, instrument=cfg.instrument,
        timeframe=cfg.timeframe, action=action, price=float(df["close"].iloc[-1]),
        z_score=z_now, z_prev=z_prev, mu=float(mu.iloc[-1]), sigma=float(sd.iloc[-1]),
        window_bars=cfg.window_bars, entry_sigma=cfg.entry_sigma,
        was_outside_band=was_out, bars_held=bars_held, timestop_bars=ts,
        est_cost_bps=cost_1rt_bps, est_swap_bps_per_bar=swap_bps_per_bar,
        reason=reason)


# ═══════════════════════════════════════════════════════ thẻ luật (một chỗ dựng)
# Mười hai chân Z-Band chạy CÙNG một bộ luật, chỉ khác công cụ và ba tham số. Trước
# 14/08/2026 mỗi file chép lại nguyên khối `RuleBook` 45 dòng — mười hai bản sao của
# cùng một thứ, và sửa luật thì phải sửa mười hai chỗ.
#
# Bố cục nay theo đúng hệ tiền nhiệm (`quant-xau/live_strategies/h1/xau_r_h1.py`):
# thẻ luật ĐỌC ĐƯỢC nằm trong docstring đầu file, thân file chỉ có hằng số và hàm.
# Khác biệt duy nhất: ở đây docstring được SINH RA từ dữ liệu này, nên nó không thể
# trôi khỏi code như docstring viết tay của hệ cũ đã từng.
SOURCES: Tuple[str, ...] = (
    'Sepp & Lucic (2026) "The Science and Practice of Trend-Following Systems", '
    'arXiv:2607.19497v1 — '
    'D:/project-learning/documents/forex-strategies/2607.19497v1.pdf',
    'Zheng Nan (2025) "Profitability of Pairs Trading Based on Cointegration in the '
    'Foreign Exchange Market", MSc thesis Waseda — '
    'D:/project-learning/documents/forex-strategies/57231515_202509.pdf',
)

FAMILY_LABEL = "Z-Band Mean Reversion (Ornstein-Uhlenbeck, không cắt lỗ theo giá)"


def rulebook(cfg: ZBandConfig, *, expectancy: str, frequency: str) -> RB.RuleBook:
    """Thẻ luật của MỘT chân Z-Band, dựng từ chính `cfg` đang chạy.

    Vì tham số lấy thẳng từ `cfg` nên thẻ luật không thể ghi một ngưỡng khác với
    ngưỡng mà backtest và live đang dùng — đó là điều bản chép tay không bảo đảm được.
    """
    ts = int(cfg.window_bars * cfg.timestop_mult)
    k, n, tf = cfg.entry_sigma, cfg.window_bars, cfg.timeframe
    return RB.RuleBook(
        name=cfg.name,
        signal_tf=tf, execution_tf=tf, direction="BOTH",
        universe=(cfg.instrument,), traded=(cfg.instrument,), max_positions=1,
        family=FAMILY_LABEL,
        source=" · ".join(SOURCES),
        hours_utc="mọi giờ",
        forbidden_hours_utc=(),
        indicators=(
            f"z = (log giá − trung bình {n} nến) / độ lệch chuẩn {n} nến",
            f"time-stop = {ts} nến {tf}",
        ),
        entry_logic="ALL",
        # DẪN XUẤT từ `cfg.entry_mode`, không chép tay. Thẻ luật ghi cứng một luật
        # trong khi code chạy luật khác là đúng thứ `tests/test_rulebook.py` sinh ra
        # để bắt: thẻ luật nói hệ ĐƯỢC PHÉP làm gì, và nó chỉ có giá trị khi không
        # thể lệch khỏi code.
        entry_rules=(
            (RB.Rule("a", f"nến TRƯỚC ngoài dải: |z(t−1)| > {k}"),
             RB.Rule("b", f"nến NÀY đã về trong dải: |z(t)| ≤ {k}"),
             RB.Rule("c", f"z(t−1) < −{k} → MUA · z(t−1) > +{k} → BÁN"))
            if cfg.entry_mode == "reenter" else
            (RB.Rule("a", f"|z| > {k}"),
             RB.Rule("b", f"nến TRƯỚC cũng ngoài dải: |z(t−1)| > {k}"),
             RB.Rule("c", f"z < −{k} → MUA · z > +{k} → BÁN"))
        ),
        entry_price="khớp tại giá MỞ CỬA nến kế tiếp sau nến tín hiệu",
        exit_rules=(
            (RB.Rule("x1", "z về 0"),) if cfg.exit_at_mean else ()
        ) + (
            RB.Rule("x2", f"time-stop {ts} nến {tf}"),
            RB.Rule("x3", "xuất hiện tín hiệu NGƯỢC chiều"),
        ),
        stop_loss="KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop",
        take_profit="không có — thoát theo tín hiệu hoặc time-stop",
        blocks=("chi phí ×5 thì hết biên — spread phải đo lại trên tài khoản thật",),
        frequency=frequency,
        avg_holding=f"{ts} nến {tf}",
        expectancy=expectancy,
        trace_signal_name="z_score",
    )
