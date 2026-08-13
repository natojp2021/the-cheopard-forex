"""cross_mean_reversion.py — CrossMeanReversion

20 cặp: EURGBP, EURAUD, EURNZD… · H1 · BOTH · Mean Reversion trên spread
(Ornstein-Uhlenbeck)

┌─ QUY TẮC VÀO LỆNH ────────────────────────────────────────────────────────────┐
│  VÀO   (đủ CẢ)                                                                │
│     a. 4 <= half_life <= 120 nến H1                                           │
│     b. |z| > 2.0                                                              │
│     c. nến TRƯỚC còn NGOÀI dải: |z(t−1)| > 2.0 (was_outside_band)             │
│     d. giờ UTC thuộc (10, 11, 12, 13, 14, 15, 16)                             │
│     e. z < 0 → MUA cross · z > 0 → BÁN cross                                  │
│     → khớp thị trường trên hai chân của cross tổng hợp — một spread, không phải│
│       hai (thành phần USD triệt tiêu)                                         │
│     giờ CẤM (UTC): 20, 21, 22, 23                                             │
│                                                                               │
│  THOÁT                                                                        │
│     · z về 0 → chốt (hồi quy đã xảy ra)                                      │
│     · giữ đủ ceil(4.32 × HL) nến → TIME-STOP                                  │
│     · half-life rơi ra ngoài dải → thoát ngay, không giữ                      │
│                                                                               │
│  CẮT LỖ  KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop       │
│  VỊ THẾ  tối đa 20                                                            │
└───────────────────────────────────────────────────────────────────────────────┘

KẾT QUẢ   Sharpe 1,059 ALL · 1,121 OOS · PBO 0,2571 (đầu tiên của dự án dưới ngưỡng
          0,50) · control p = 0,0000 · 15/15 ô tham số dương
TẦN SUẤT  ≈ 6,6 vòng quay/năm · 65% thời gian có ít nhất một vị thế · giữ 4-6 ngày
CHỈ BÁO   half-life từ AR(1) trên log giá cross, khớp lại mỗi 500 nến · cửa sổ z =
          half_life × 4.32 (= ln(1/0,05)/ln2, phân rã 95%) · z = (logp − trung bình cửa
          sổ) / σ cửa sổ, mọi thống kê tính đến nến t−1
PHÂN LOẠI HIỆN ĐẠI — tham số lấy NGUYÊN từ luận văn Zheng Nan 2025

NGUỒN
  · Zheng Nan (2025) "Profitability of Pairs Trading Based on Cointegration in the
    Foreign Exchange Market", MSc thesis Waseda
    D:/project-learning/documents/forex-strategies/57231515_202509.pdf

Số liệu SAU ĐỦ CHI PHÍ (spread đo thật trên MT5 14/08/2026 ×1,5 + commission + swap +
biên broker 1,0%/năm). OOS từ 2024-01-01 chưa từng dùng để chọn gì. Spread là của tài
khoản DEMO — đo lại bằng `scripts/measure_broker_costs.py` trước khi cấp vốn.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.python.research import fx_cross_pairs as CX
from src.python.shared import carry_costs as CC
from src.python.strategies import rulebook as RB
from src.python.research import fx_cross_pairs as _CP

# ═════════════════════════════════════════════════════════ tham số (SSOT)
# Lấy NGUYÊN từ Zheng Nan (2025). Không tinh chỉnh — xem §2.
WINDOW_HL_MULT = 4.32       # ln(1/0,05)/ln 2 — thời gian phân rã 95%
ENTRY_SIGMA = 2.0
MIN_HL_BARS = 4
MAX_HL_BARS = 120
REESTIMATE_BARS = 500

# Cửa sổ khớp lệnh, đo được trên H1 2020+ (rẻ nhất 15:00 UTC = 1,6567 bps/khứ hồi
# rổ, đắt nhất 22:00 = 2,3043). Dải 10:00-16:00 nằm trong 1% của nhau.
EXECUTION_WINDOW_UTC: Tuple[int, ...] = (10, 11, 12, 13, 14, 15, 16)
FORBIDDEN_HOURS_UTC: Tuple[int, ...] = (20, 21, 22, 23)

DEV_END = pd.Timestamp("2024-01-01")


@dataclass(frozen=True)
class Config:
    window_hl_mult: float = WINDOW_HL_MULT
    entry_sigma: float = ENTRY_SIGMA
    min_hl_bars: int = MIN_HL_BARS
    max_hl_bars: int = MAX_HL_BARS
    reestimate_bars: int = REESTIMATE_BARS
    broker_markup_pct: float = 1.0

    def to_cx(self) -> CX.Config:
        return CX.Config(lookback_hl_mult=self.window_hl_mult,
                         entry_sigma=self.entry_sigma,
                         min_hl_bars=self.min_hl_bars,
                         max_hl_bars=self.max_hl_bars,
                         reestimate_bars=self.reestimate_bars,
                         require_reentry=True,
                         markup_pct=self.broker_markup_pct)


# ═════════════════════════════════════════════════════════ LOG QUY TẮC VÀO LỆNH
@dataclass
class EntryDecision:
    """Bản ghi ĐẦY ĐỦ một quyết định vào lệnh — mọi số đã dẫn tới nó.

    Vì sao cần: log nghiên cứu trả lời "chiến lược lãi bao nhiêu"; log này trả lời
    "vì sao lệnh NÀY được mở". Khi một lệnh live thua bất thường, chỉ log này mới
    cho phép truy ngược xem tín hiệu có đúng luật không, hay dữ liệu/tham số đã
    trôi. Không có nó thì mọi tranh luận về một lệnh cụ thể đều là suy đoán.
    """
    timestamp: pd.Timestamp
    cross: str
    action: str                 # BUY | SELL | HOLD | SKIP
    # ── trạng thái tín hiệu
    price: float
    log_price: float
    z_score: float
    mu: float
    sigma: float
    # ── tham số đang hiệu lực
    half_life_bars: float
    window_bars: int
    entry_sigma: float
    bars_since_reestimate: int
    # ── điều kiện của luật (mỗi cái là một mệnh đề kiểm được)
    was_outside_band: int       # −1 dưới, +1 trên, 0 không
    reentered: bool
    hl_in_range: bool
    execution_hour_ok: bool
    # ── kinh tế dự kiến
    est_cost_bps: float
    est_swap_bps_per_night: float
    timestop_bars: int
    reason: str

    def to_row(self) -> Dict[str, object]:
        d = self.__dict__.copy()
        d["timestamp"] = str(self.timestamp)
        return d

    def explain(self) -> str:
        """Một dòng người đọc được — dùng cho log vận hành."""
        return (f"[{self.timestamp}] {self.cross} {self.action} · "
                f"z={self.z_score:+.2f} (µ={self.mu:.5f} σ={self.sigma:.5f}) · "
                f"HL={self.half_life_bars:.0f} cửa sổ={self.window_bars} · "
                f"timestop={self.timestop_bars} nến · chi phí≈{self.est_cost_bps:.2f}bps · "
                f"{self.reason}")


def _half_life(x: np.ndarray) -> float:
    return CX.half_life(x)


def evaluate_cross(name: str, price: pd.Series, spec: CX.CrossSpec,
                   cfg: Config = Config(), *,
                   now_utc: Optional[pd.Timestamp] = None,
                   state: Optional[Dict[str, object]] = None) -> EntryDecision:
    """Đánh giá MỘT cross tại nến mới nhất và trả bản ghi quyết định đầy đủ.

    `state` mang `was_outside` giữa các lần gọi ở live (backtest tự giữ trong vòng
    lặp). Truyền `None` sẽ tính lại `was_outside` từ 50 nến gần nhất — kém chính xác
    hơn nhưng dùng được khi khởi động lại tiến trình.
    """
    p = price.dropna()
    if len(p) == 0:
        # KHÔNG CÓ DỮ LIỆU THÌ TRẢ SKIP, KHÔNG NÉM NGOẠI LỆ.
        #
        # Sự cố 20/08/2026: một công cụ trong rổ (EURUSD) mất sạch nến, nên MỌI
        # cross rỗng theo. Dòng dưới đây trước là `idx[-1]` trên chỉ mục rỗng →
        # `IndexError` → `portfolio.live_targets` hỏng → `_build_plan` hỏng →
        # **cả 27 chân đứng im**, mỗi chu kỳ, trong khi nhịp tim vẫn "MT5 OK".
        #
        # Một chân thiếu dữ liệu phải TỰ đứng ngoài, không được kéo theo 26 chân
        # còn lại. Nguyên nhân gốc sửa ở `shared/mt5_bars.py`; đây là lớp chặn để
        # cùng hình dạng lỗi lần sau không hạ được cả danh mục.
        return EntryDecision(
            timestamp=pd.Timestamp(now_utc) if now_utc is not None
            else pd.Timestamp.utcnow(),
            cross=name, action="SKIP",
            price=float("nan"), log_price=float("nan"), z_score=float("nan"),
            mu=float("nan"), sigma=float("nan"),
            half_life_bars=float("inf"), window_bars=0,
            entry_sigma=cfg.entry_sigma, bars_since_reestimate=0,
            was_outside_band=0, reentered=False, hl_in_range=False,
            execution_hour_ok=False,
            est_cost_bps=float("nan"), est_swap_bps_per_night=float("nan"),
            timestop_bars=0,
            reason="KHÔNG CÓ NẾN cho cross này — chân đứng ngoài chu kỳ này")
    lp = np.log(p).to_numpy()
    idx = p.index
    i = len(lp) - 1
    ts = pd.Timestamp(now_utc) if now_utc is not None else idx[-1]

    # ── half-life trên 2000 nến trước
    w = lp[max(0, i - 2000):i]
    hl = _half_life(w - np.mean(w)) if len(w) > 100 else float("inf")
    hl_ok = cfg.min_hl_bars <= hl <= cfg.max_hl_bars
    window = int(np.ceil(hl * cfg.window_hl_mult)) if hl_ok else 0

    mu = sigma = z = float("nan")
    if hl_ok and window > 0:
        hist = lp[max(0, i - window):i]
        if len(hist) >= max(20, window // 2):
            mu, sigma = float(np.mean(hist)), float(np.std(hist, ddof=1))
            if sigma > 0:
                z = (lp[i] - mu) / sigma

    # ── trạng thái "đã ra ngoài dải"
    was_outside = int((state or {}).get("was_outside", 0))
    if state is None and np.isfinite(z):
        for k in range(max(0, i - 50), i):
            hz = (lp[k] - mu) / sigma if sigma > 0 else 0.0
            if hz > cfg.entry_sigma:
                was_outside = 1
            elif hz < -cfg.entry_sigma:
                was_outside = -1
            elif abs(hz) <= cfg.entry_sigma:
                pass

    hour_ok = ts.hour in EXECUTION_WINDOW_UTC and ts.hour not in FORBIDDEN_HOURS_UTC
    px = float(p.iloc[-1])
    cost = spec.cost_1rt_bps_at(px)
    swap_night = CC.SWAP_CALENDAR_MULTIPLIER * cfg.broker_markup_pct / 365.0 * 100.0

    # ── áp luật
    action, reentered, reason = "HOLD", False, ""
    if not hl_ok:
        action, reason = "SKIP", f"half-life {hl:.1f} ngoài dải [{cfg.min_hl_bars},{cfg.max_hl_bars}]"
    elif not np.isfinite(z):
        action, reason = "SKIP", "chưa đủ lịch sử để tính µ/σ"
    elif z > cfg.entry_sigma:
        was_outside, reason = 1, f"z={z:+.2f} vượt +{cfg.entry_sigma}σ — CHỜ quay vào dải"
    elif z < -cfg.entry_sigma:
        was_outside, reason = -1, f"z={z:+.2f} vượt −{cfg.entry_sigma}σ — CHỜ quay vào dải"
    elif was_outside == 1:
        reentered = True
        action = "SELL" if hour_ok else "HOLD"
        reason = (f"đã ra ngoài +{cfg.entry_sigma}σ rồi quay vào (z={z:+.2f}) → BÁN"
                  if hour_ok else f"tín hiệu BÁN nhưng {ts.hour:02d}:00 UTC ngoài cửa sổ khớp")
    elif was_outside == -1:
        reentered = True
        action = "BUY" if hour_ok else "HOLD"
        reason = (f"đã ra ngoài −{cfg.entry_sigma}σ rồi quay vào (z={z:+.2f}) → MUA"
                  if hour_ok else f"tín hiệu MUA nhưng {ts.hour:02d}:00 UTC ngoài cửa sổ khớp")
    else:
        reason = f"z={z:+.2f} trong dải, chưa có lệch đủ lớn"

    if state is not None:
        state["was_outside"] = 0 if reentered else was_outside

    return EntryDecision(
        timestamp=ts, cross=name, action=action, price=px, log_price=float(lp[i]),
        z_score=round(float(z), 4) if np.isfinite(z) else float("nan"),
        mu=round(mu, 8) if np.isfinite(mu) else float("nan"),
        sigma=round(sigma, 8) if np.isfinite(sigma) else float("nan"),
        half_life_bars=round(hl, 2) if np.isfinite(hl) else float("inf"),
        window_bars=window, entry_sigma=cfg.entry_sigma,
        bars_since_reestimate=int(i % cfg.reestimate_bars),
        was_outside_band=was_outside, reentered=reentered, hl_in_range=hl_ok,
        execution_hour_ok=hour_ok, est_cost_bps=round(cost, 3),
        est_swap_bps_per_night=round(swap_night, 3),
        timestop_bars=int(np.ceil(hl * cfg.window_hl_mult)) if hl_ok else 0,
        reason=reason)


# ═════════════════════════════════════════════════════════ backtest
def backtest(cfg: Config = Config(), start: str = "2020-01-01",
             crosses: Optional[Sequence[str]] = None) -> pd.DataFrame:
    """Toàn bộ lệnh trên mọi cross, đủ chi phí (spread + commission + swap)."""
    P, specs = CX.build_crosses("H1", start=start)
    rates = CC.rate_series(pd.DatetimeIndex(sorted(set(P.index.normalize()))))
    names = list(crosses) if crosses else list(P.columns)
    k = CC.SWAP_CALENDAR_MULTIPLIER / 365.0 * 100.0

    rows: List[Dict[str, object]] = []
    for name in names:
        spec = specs[name]
        for t in CX.simulate(name, P[name], spec, cfg.to_cx()):
            d0 = pd.Timestamp(t.entry_time).normalize()
            d1 = pd.Timestamp(t.exit_time).normalize()
            nights = max((d1 - d0).days, 0)
            try:
                r = rates.loc[d0]
            except KeyError:
                r = rates.iloc[rates.index.searchsorted(d0)]
            diff = float(r.get(spec.base, 0.0) - r.get(spec.quote, 0.0))
            swap = (-t.side * diff + cfg.broker_markup_pct) * k * nights
            rows.append({
                "entry_time": pd.Timestamp(t.entry_time),
                "exit_time": pd.Timestamp(t.exit_time),
                "cross": name, "side": t.side, "entry_z": t.entry_z,
                "exit_reason": t.exit_reason, "bars_held": t.bars_held,
                "gross_bps": t.gross_bps, "cost_bps": t.cost_bps,
                "swap_bps": round(swap, 3),
                "net_bps": round(t.gross_bps - t.cost_bps - swap, 3)})
    if not rows:
        # KHONG CO LENH NAO VAN PHAI TRA VE KHUNG DUNG HINH DANG.
        #
        # `pd.DataFrame([])` khong co cot nao, nen `sort_values("entry_time")`
        # nem `KeyError: 'entry_time'`. Do 21:52:42 ngay 20/08/2026: ro cross
        # rong (EURUSD mat nen) -> khong lenh nao -> `_build_plan` hong -> CA 27
        # CHAN dung im. Dung ho lo cu, lop vo moi: mot ro rong la trang thai
        # BINH THUONG cua thi truong, khong phai loi lap trinh.
        #
        # `daily_pnl` va `stats` deu chay duoc tren khung rong co cot; chung chi
        # chet khi khung KHONG CO COT.
        # KIEU DU LIEU CUNG PHAI DUNG, KHONG CHI TEN COT.
        #
        # `DataFrame(columns=[...])` cho moi cot dtype `object`. `daily_pnl` lam
        # `set_index("entry_time").resample("1D")`, va resample tren `Index`
        # kieu object nem `TypeError: Only valid with DatetimeIndex`. Tuc la sua
        # nua voi thi chi doi mot ngoai le nay lay mot ngoai le khac.
        return pd.DataFrame({
            "entry_time": pd.Series(dtype="datetime64[ns]"),
            "exit_time": pd.Series(dtype="datetime64[ns]"),
            "cross": pd.Series(dtype="object"),
            "side": pd.Series(dtype="int64"),
            "entry_z": pd.Series(dtype="float64"),
            "exit_reason": pd.Series(dtype="object"),
            "bars_held": pd.Series(dtype="int64"),
            "gross_bps": pd.Series(dtype="float64"),
            "cost_bps": pd.Series(dtype="float64"),
            "swap_bps": pd.Series(dtype="float64"),
            "net_bps": pd.Series(dtype="float64")})
    return pd.DataFrame(rows).sort_values("entry_time").reset_index(drop=True)


def daily_pnl(trades: pd.DataFrame, start: str = "2020-04-01") -> pd.Series:
    s = trades.set_index("entry_time")["net_bps"].resample("1D").sum().fillna(0.0)
    return s[s.index >= pd.Timestamp(start)]


def stats(pnl: pd.Series, label: str = "") -> Dict[str, object]:
    if len(pnl) < 30:
        return {"label": label, "n": len(pnl)}
    cum = pnl.cumsum()
    dd = cum.cummax() - cum
    sd = float(pnl.std(ddof=1))
    yrs = max((pnl.index.max() - pnl.index.min()).days / 365.25, 1e-9)
    return {
        "label": label, "n_days": len(pnl),
        "tong_bps": round(float(cum.iloc[-1]), 0),
        "bps_ngay": round(float(pnl.mean()), 3),
        "ann_pct": round(float(cum.iloc[-1]) / 100.0 / yrs, 2),
        "vol_pct": round(sd * np.sqrt(252) / 100.0, 2),
        "sharpe": round(float(pnl.mean()) / sd * np.sqrt(252), 3) if sd > 0 else np.nan,
        "max_dd_bps": round(float(dd.max()), 0),
    }


# ═════════════════════════════════════════════════════════ giao diện LIVE
def live_decisions(cfg: Config = Config(), start: str = "2020-01-01",
                   now_utc: Optional[pd.Timestamp] = None) -> List[EntryDecision]:
    """Quyết định cho MỌI cross tại nến H1 mới nhất — đây là thứ dispatcher gọi.

    Trả bản ghi ĐẦY ĐỦ cho mọi cross, kể cả cross không vào lệnh: log phải ghi cả
    những lần KHÔNG giao dịch, vì "vì sao hôm nay không có lệnh nào" là câu hỏi
    vận hành thường gặp nhất và không trả lời được nếu chỉ log lệnh đã mở.
    """
    P, specs = CX.build_crosses("H1", start=start)
    return [evaluate_cross(name, P[name], specs[name], cfg, now_utc=now_utc)
            for name in P.columns]


# Rổ 20 cross tổng hợp — lấy từ SSOT `research/fx_cross_pairs.CROSS_DEFS` thay vì
# viết lại, để không có hai danh sách trôi khỏi nhau.
_CROSS_UNIVERSE = tuple(d[0] for d in _CP.CROSS_DEFS)

# ══ NGUỒN GỐC — mỗi dòng một bài, kèm đường dẫn mở được
SOURCES = (
    "Zheng Nan (2025) \"Profitability of Pairs Trading Based on Cointegration in the "
    "Foreign Exchange Market\", MSc thesis Waseda — "
    "D:/project-learning/documents/forex-strategies/57231515_202509.pdf",
)

# ══ THẺ LUẬT — dữ liệu cho GUI và tests/test_rulebook.py.
# ══ Bản người đọc là khối QUY TẮC VÀO LỆNH ở ĐẦU FILE, sinh ra từ đây.
RULEBOOK = RB.RuleBook(
    name="CrossMeanReversion",
    signal_tf="H1", execution_tf="H1", direction="BOTH",
    universe=_CROSS_UNIVERSE,
    max_positions=len(_CROSS_UNIVERSE),
    family="Mean Reversion trên spread (Ornstein-Uhlenbeck)",
    source=" · ".join(SOURCES),
    hours_utc=f"khớp trong cửa sổ {EXECUTION_WINDOW_UTC[0]:02d}-"
              f"{EXECUTION_WINDOW_UTC[-1]:02d}:00 UTC",
    forbidden_hours_utc=FORBIDDEN_HOURS_UTC,
    indicators=(
        f"half-life từ AR(1) trên log giá cross, khớp lại mỗi {REESTIMATE_BARS} nến",
        f"cửa sổ z = half_life × {WINDOW_HL_MULT} (= ln(1/0,05)/ln2, phân rã 95%)",
        "z = (logp − trung bình cửa sổ) / σ cửa sổ, mọi thống kê tính đến nến t−1",
    ),
    entry_logic="ALL",
    entry_rules=(
        RB.Rule("a", f"{MIN_HL_BARS} <= half_life <= {MAX_HL_BARS} nến H1",
                "ngoài khoảng này thì cross không hồi quy đủ nhanh để bù chi phí; "
                "khi rơi ra ngoài phải THOÁT, không được giữ (lỗi giữ vị thế cũ "
                "làm 93% thời gian trong thị trường, Sharpe −0,234)"),
        RB.Rule("b", f"|z| > {ENTRY_SIGMA}", "ngưỡng vào của Zheng Nan, không tinh chỉnh"),
        RB.Rule("c", f"nến TRƯỚC còn NGOÀI dải: |z(t−1)| > {ENTRY_SIGMA} "
                     f"(was_outside_band)",
                "chống vào lại liên tục khi z dao động quanh ngưỡng"),
        RB.Rule("d", f"giờ UTC thuộc {EXECUTION_WINDOW_UTC}"),
        RB.Rule("e", "z < 0 → MUA cross · z > 0 → BÁN cross"),
    ),
    entry_price="khớp thị trường trên hai chân của cross tổng hợp — một spread, "
                "không phải hai (thành phần USD triệt tiêu)",
    exit_rules=(
        RB.Rule("x1", "z về 0 → chốt (hồi quy đã xảy ra)"),
        RB.Rule("x2", f"giữ đủ ceil({WINDOW_HL_MULT} × HL) nến → TIME-STOP",
                "Zheng Nan đo time-stop hơn stop 3σ +85% — cắt lỗ theo giá trên spread "
                "hồi quy là cắt đúng lúc spread căng nhất"),
        RB.Rule("x3", "half-life rơi ra ngoài dải → thoát ngay, không giữ"),
    ),
    stop_loss="KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop",
    take_profit="không có — thoát theo tín hiệu hoặc time-stop",
    blocks=(
        f"giờ CẤM UTC {FORBIDDEN_HOURS_UTC}",
        "chết ở chi phí ×2 — chi phí cross là ƯỚC LƯỢNG, phải đo thật trước khi cấp vốn",
    ),
    frequency="≈ 6,6 vòng quay/năm · 65% thời gian có ít nhất một vị thế",
    avg_holding="4-6 ngày",
    expectancy="Sharpe 1,059 ALL · 1,121 OOS · PBO 0,2571 (đầu tiên của dự án dưới "
               "ngưỡng 0,50) · control p = 0,0000 · 15/15 ô tham số dương",
    trace_signal_name="z_score",
)
