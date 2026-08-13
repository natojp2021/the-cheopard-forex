"""currency_reversal.py — CurrencyReversal

7 cặp: EURUSD, GBPUSD, USDJPY… · D1 · BOTH · Cross-Sectional Currency Short-Term
Reversal

┌─ QUY TẮC VÀO LỆNH ────────────────────────────────────────────────────────────┐
│  VÀO   (xếp hạng cắt ngang)                                                   │
│     a. hôm nay là ngày tái cân bằng (mỗi 21 ngày)                             │
│     b. MUA 3 đồng có tín hiệu CAO nhất (= yếu nhất quá khứ)                   │
│     c. BÁN 3 đồng có tín hiệu THẤP nhất (= mạnh nhất quá khứ)                 │
│     d. tỷ trọng trong mỗi chân ∝ 1/σ(63), tổng mỗi chân = 1                    │
│     e. biến động rổ < phân vị 80% trượt 252 ngày                              │
│     → quy tỷ trọng ĐỒNG TIỀN → tỷ trọng CẶP qua pair_weights(), khớp thị trường│
│     giờ CẤM (UTC): 20, 21, 22, 23                                             │
│                                                                               │
│  THOÁT                                                                        │
│     · tái cân bằng kế tiếp sau 21 ngày                                       │
│     · cổng chế độ chuyển sang CRISIS → về 0 toàn bộ chân                      │
│                                                                               │
│  CẮT LỖ  KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop       │
│  VỊ THẾ  tối đa 6                                                             │
└───────────────────────────────────────────────────────────────────────────────┘

KẾT QUẢ   Sharpe 0,576 ALL · 0,395 OOS · MaxDD 8,27% (sau đủ chi phí, đòn bẩy 1,0)
TẦN SUẤT  tái cân bằng mỗi 21 ngày giao dịch ≈ 12 lần/năm · giữ 21 ngày giao dịch
CHỈ BÁO   tín hiệu = −(lợi nhuận log tích luỹ 21 ngày của từng đồng) · σ(63 ngày) của
          từng đồng — CHỈ để chia tỷ trọng, không để chọn · biến động rổ làm mượt 21
          ngày · phân vị TRƯỢT 80% của 252 ngày trước (.shift(1))
PHÂN LOẠI CỔ ĐIỂN HỌC THUẬT — luật lấy NGUYÊN VĂN từ PAMR (Li, Zhao, Hoi & Gopalkrishnan
          2012) và Menkhoff et al. JFE 2012

NGUỒN
  · Li, Zhao, Hoi & Gopalkrishnan (2012) "PAMR: Passive-Aggressive Mean Reversion
    Strategy for Portfolio Selection", Machine Learning 87(2)
    D:/project-learning/documents/forex-strategies/PAMR_ Passive-Aggressive Mean
    Reversion Strategy for Portfolio Se.pdf
  · Menkhoff, Sarno, Schmeling & Schrimpf (2012) "Currency Momentum Strategies", J.
    Financial Economics 106(3)
    D:/project-learning/documents/forex-strategies/Currency Momentum Strategies.pdf
  · Brière & Drut (2009, sửa 2010) "The Revenge of Fundamentals on Carry Trades during
    Crises", Amundi WP-005-2009
    D:/project-learning/documents/forex-strategies/Working Paper July 2009 - the revenge
    of fundamentals on carry trades during crises.pdf

Số liệu SAU ĐỦ CHI PHÍ (spread đo thật trên MT5 14/08/2026 ×1,5 + commission + swap +
biên broker 1,0%/năm). OOS từ 2024-01-01 chưa từng dùng để chọn gì. Spread là của tài
khoản DEMO — đo lại bằng `scripts/measure_broker_costs.py` trước khi cấp vốn.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.python.shared import asset_profile as AP
from src.python.shared import carry_costs as CC
from src.python.shared import fx_data as D
from src.python.strategies import rulebook as RB

# ═════════════════════════════════════════════════════════ tham số (SSOT)
LOOKBACK_DAYS = 21          # cửa sổ đo "đồng nào vừa mạnh/yếu"
REBALANCE_DAYS = 21         # tần suất tái cân bằng
N_LEG = 3                   # số đồng mỗi chân (Menkhoff et al. dùng 3/3)
VOL_WINDOW = 63             # cửa sổ σ để chuẩn hoá rủi ro giữa các đồng
REGIME_WINDOW = 252         # cửa sổ phân vị trượt cho cổng chế độ
REGIME_VOL_WINDOW = 21      # làm mượt biến động rổ
REGIME_QUANTILE = 0.80      # ≥ phân vị này = CRISIS = đứng ngoài

PAIRS: Tuple[str, ...] = AP.FX_ALL
CCYS: Tuple[str, ...] = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD")

# ── TẦNG THỰC THI H1 — khung giao dịch chính của dự án.
# Tín hiệu sinh ở D1, nhưng lệnh khớp trên nến H1, và giờ khớp là một quyết định
# CHI PHÍ có số liệu (đo trên H1 2020+, spread trung vị theo giờ, rổ 7 cặp):
#     15:00 UTC  1,6567 bps/khứ hồi   <- rẻ nhất (chồng lấn London/NY)
#     22:00 UTC  2,3043 bps           <- đắt nhất, gấp 1,39 lần
# Cả dải 10:00-16:00 UTC nằm trong khoảng 1% của nhau, nên đây là một VÙNG ổn định
# chứ không phải một điểm tối ưu mong manh — chọn 15:00 và cho phép trượt trong dải.
# Giờ 20:00-23:00 UTC bị CẤM: đó là cửa sổ rollover, spread giãn 1,4-3 lần trên mọi cặp.
EXECUTION_HOUR_UTC = 15
EXECUTION_WINDOW_UTC: Tuple[int, ...] = (10, 11, 12, 13, 14, 15, 16)
FORBIDDEN_HOURS_UTC: Tuple[int, ...] = (20, 21, 22, 23)


@dataclass(frozen=True)
class Config:
    lookback_days: int = LOOKBACK_DAYS
    rebalance_days: int = REBALANCE_DAYS
    n_leg: int = N_LEG
    vol_window: int = VOL_WINDOW
    regime_window: int = REGIME_WINDOW
    regime_vol_window: int = REGIME_VOL_WINDOW
    regime_quantile: float = REGIME_QUANTILE
    regime_gate: bool = True


# ═════════════════════════════════════════════════════════ tầng dữ liệu
def currency_returns(start: str = "2020-01-01",
                     pairs: Sequence[str] = PAIRS) -> Tuple[pd.DataFrame, pd.Series]:
    """(lợi nhuận log D1 của 8 đồng tiền tính bằng bps, chi phí khứ hồi bps mỗi cặp).

    Chuẩn hoá tổng = 0 mỗi ngày → mọi danh mục long-short trên rổ này là
    dollar-neutral theo xây dựng, không phải nhờ một ràng buộc tối ưu hoá.
    """
    rets: Dict[str, pd.Series] = {}
    costs: Dict[str, float] = {}
    for sym in pairs:
        d = D.daily_bars(sym, start=start)
        prof = AP.get(sym)
        r = np.log(d["close"]).diff() * 1e4
        foreign = prof.base if prof.quote_is_usd else prof.quote
        rets[foreign] = r if prof.quote_is_usd else -r
        px = float(d["close"].median())
        sp = float(d["spread_usd"].median())
        costs[sym] = (sp + prof.commission_price_units(px)) / px * 1e4
    F = pd.DataFrame(rets).dropna(how="all")
    F["USD"] = -F.mean(axis=1)
    F = F.sub(F.mean(axis=1), axis=0)
    return F, pd.Series(costs, name="cost_1rt_bps")


def _pair_for(ccy: str) -> Tuple[str, int]:
    """Cặp dùng để giao dịch một đồng tiền + dấu (+1: long đồng = long cặp)."""
    for sym in PAIRS:
        p = AP.get(sym)
        if p.quote_is_usd and p.base == ccy:
            return sym, +1
        if p.base == "USD" and p.quote == ccy:
            return sym, -1
    raise KeyError(f"Không có cặp cho {ccy}")


# ═════════════════════════════════════════════════════════ tầng tín hiệu
def regime_is_crisis(F: pd.DataFrame, cfg: Config = Config()) -> pd.Series:
    """CRISIS = biến động rổ ≥ phân vị trượt. Nhân quả, dùng được ở live.

    Ta KHÔNG có VIX (nguồn của Brière & Drut) nên dùng biến động rổ tiền tệ làm
    proxy risk-aversion nội-FX. `.shift(1)` ở cả giá trị lẫn ngưỡng: quyết định
    hôm nay chỉ dựa trên dữ liệu đã đóng.
    """
    bvol = F.std(axis=1).rolling(cfg.regime_vol_window).mean()
    thr = bvol.shift(1).rolling(cfg.regime_window,
                                min_periods=cfg.regime_window // 2
                                ).quantile(cfg.regime_quantile)
    return (bvol.shift(1) >= thr).fillna(False)


def target_weights(F: pd.DataFrame, cfg: Config = Config()) -> pd.DataFrame:
    """Tỷ trọng MỤC TIÊU theo ĐỒNG TIỀN cho mỗi ngày.

    Hàm này là trái tim của hệ và được dùng CHUNG bởi backtest và live — live chỉ
    lấy hàng cuối cùng (`.iloc[-1]`). Không có đường code thứ hai.
    """
    cum = F.cumsum()
    signal = -(cum - cum.shift(cfg.lookback_days))      # dấu trừ = REVERSAL
    vol = F.rolling(cfg.vol_window, min_periods=cfg.vol_window // 2).std()
    crisis = regime_is_crisis(F, cfg) if cfg.regime_gate else pd.Series(False, index=F.index)

    W = pd.DataFrame(0.0, index=F.index, columns=F.columns)
    held = pd.Series(0.0, index=F.columns)
    need = 2 * cfg.n_leg
    for i, t in enumerate(F.index):
        if i % cfg.rebalance_days == 0 and i > 0:
            s, v = signal.iloc[i - 1], vol.iloc[i - 1]
            if s.notna().sum() >= need and v.notna().sum() >= need:
                order = s.dropna().sort_values(ascending=False)
                w = pd.Series(0.0, index=F.columns)
                for grp, sgn in ((list(order.index[:cfg.n_leg]), +1.0),
                                 (list(order.index[-cfg.n_leg:]), -1.0)):
                    iv = (1.0 / v[grp].replace(0, np.nan)).fillna(0.0)
                    if iv.sum() > 0:
                        w[grp] = sgn * iv / iv.sum()
                held = w
        W.loc[t] = 0.0 if crisis.iloc[i] else held
    return W


def pair_weights(W_ccy: pd.DataFrame) -> pd.DataFrame:
    """Quy tỷ trọng ĐỒNG TIỀN -> tỷ trọng CẶP giao dịch được.

    Đây chính là Currency Exposure Engine: 8 mục tiêu theo đồng tiền được gộp
    thành 7 vị thế theo cặp, nên hai tín hiệu cùng hàm ý "USD yếu" tự động triệt
    tiêu thay vì thành hai lệnh độc lập.
    """
    P = pd.DataFrame(0.0, index=W_ccy.index, columns=list(PAIRS))
    for ccy in W_ccy.columns:
        if ccy == "USD":
            continue
        sym, sgn = _pair_for(ccy)
        P[sym] = P[sym] + sgn * W_ccy[ccy]
    return P


# ═════════════════════════════════════════════════════════ backtest
@dataclass
class BacktestResult:
    net: pd.Series
    gross: pd.Series
    cost: pd.Series                 # tổng: giao dịch + carry
    trade_cost: pd.Series = field(repr=False, default_factory=lambda: pd.Series(dtype=float))
    carry_cost: pd.Series = field(repr=False, default_factory=lambda: pd.Series(dtype=float))
    weights_ccy: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)
    weights_pair: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)


def backtest(start: str = "2020-01-01", cfg: Config = Config(), *,
             broker_markup_pct: float = CC.DEFAULT_BROKER_MARKUP_PCT) -> BacktestResult:
    """Backtest ĐỦ CHI PHÍ. Swap là mặc định, không phải tuỳ chọn.

    Thứ tự cộng chi phí lấy theo `project-refer/carver-systematic-trading`, repo đã
    ghi lại một chiến lược trông ổn ở lớp 2 rồi chết ở lớp 3:
        lớp 1  gross
        lớp 2  + spread & commission
        lớp 3  + swap chênh lệch lãi suất
        lớp 4  + biên broker trên swap        <- lớp giết chiến lược này
    `broker_markup_pct` là tham số QUAN TRỌNG NHẤT của toàn hệ — xem §7 của
    `docs/forex/04_ket_qua_cuoi_cung.md`. Đặt = 0.0 để xem con số gross-of-swap,
    nhưng KHÔNG được dùng con số đó để ra quyết định triển khai.
    """
    F, costs = currency_returns(start=start)
    W = target_weights(F, cfg)
    P = pair_weights(W)
    gross = (W * F).sum(axis=1)
    turnover = P.diff().abs().fillna(P.abs())
    trade_cost = (turnover * costs.reindex(P.columns)).sum(axis=1) / 2.0
    specs = {s: (AP.get(s).base, AP.get(s).quote) for s in P.columns}
    carry = CC.pair_carry_bps(P, specs, broker_markup_pct=broker_markup_pct)
    total_cost = trade_cost + carry["total_carry_bps"]
    return BacktestResult(net=(gross - total_cost).dropna(), gross=gross,
                          cost=total_cost, trade_cost=trade_cost,
                          carry_cost=carry["total_carry_bps"],
                          weights_ccy=W, weights_pair=P)


def stats(s: pd.Series, label: str = "") -> Dict[str, object]:
    if len(s) < 30:
        return {"label": label, "n_days": len(s)}
    cum = s.cumsum()
    dd = cum.cummax() - cum
    sd = float(s.std(ddof=1))
    years = max((s.index.max() - s.index.min()).days / 365.25, 1e-9)
    ann_ret = float(cum.iloc[-1]) / 100.0 / years
    mdd = float(dd.max()) / 100.0
    down = float(s[s < 0].std(ddof=1)) if (s < 0).any() else np.nan
    active = s[s != 0]
    return {
        "label": label, "n_days": len(s), "n_active": len(active),
        "ann_ret_pct": round(ann_ret, 2),
        "ann_vol_pct": round(sd * np.sqrt(252) / 100.0, 2),
        "sharpe": round(float(s.mean()) / sd * np.sqrt(252), 3) if sd > 0 else np.nan,
        "sortino": round(float(s.mean()) / down * np.sqrt(252), 3) if down and down > 0 else np.nan,
        "max_dd_pct": round(mdd, 2),
        "calmar": round(ann_ret / mdd, 3) if mdd > 0 else np.nan,
        "hit_rate_active": round(float((active > 0).mean()), 3) if len(active) else np.nan,
    }


# ═════════════════════════════════════════════════════════ giao diện LIVE
@dataclass
class TargetPosition:
    symbol: str
    weight: float            # ±, đơn vị "phần của một đơn vị rủi ro danh mục"
    direction: str           # "BUY" | "SELL" | "FLAT"


def live_targets(start: str = "2020-01-01",
                 cfg: Config = Config()) -> Tuple[List[TargetPosition], Dict[str, object]]:
    """Vị thế MỤC TIÊU cho phiên hiện tại + bối cảnh chẩn đoán.

    Dùng ĐÚNG `target_weights()` mà backtest dùng rồi lấy hàng cuối — đó là cách
    parity được bảo đảm bằng cấu trúc chứ không bằng kỷ luật viết code.
    """
    F, _ = currency_returns(start=start)
    W = target_weights(F, cfg)
    P = pair_weights(W)
    last = P.iloc[-1]
    crisis = bool(regime_is_crisis(F, cfg).iloc[-1])
    n = len(F)
    ctx = {
        "asof": str(F.index[-1].date()),
        "regime": "CRISIS (đứng ngoài)" if crisis else "CALM (giao dịch)",
        "days_since_rebalance": int((n - 1) % cfg.rebalance_days),
        "next_rebalance_in": int(cfg.rebalance_days - (n - 1) % cfg.rebalance_days),
        "ccy_weights": W.iloc[-1].round(4).to_dict(),
    }
    ctx["execution_hour_utc"] = EXECUTION_HOUR_UTC
    ctx["execution_window_utc"] = EXECUTION_WINDOW_UTC
    out = [TargetPosition(sym, round(float(w), 4),
                          "FLAT" if abs(w) < 1e-6 else ("BUY" if w > 0 else "SELL"))
           for sym, w in last.items()]
    return out, ctx


def explain_decisions(start: str = "2020-01-01", cfg: Config = Config()) -> List:
    """BAN GHI QUY TAC VAO LENH cho tung dong tien — khong chi ty trong.

    Truoc ham nay, chan reversal chi ghi duoc mot dong "da tai can bang". Dong do
    khong tra loi duoc "vi sao AUD duoc mua 0,33 ma GBP chi 0,03" — voi chien luoc
    xep hang thi can TIN HIEU, THU HANG, NGUONG CAT va TY TRONG, thieu mot cai la
    khong tai lap duoc quyet dinh.
    """
    from src.python.execution import rule_trace as RT

    F, _ = currency_returns(start=start)
    cum = F.cumsum()
    signal = -(cum - cum.shift(cfg.lookback_days))
    vol = F.rolling(cfg.vol_window, min_periods=cfg.vol_window // 2).std()
    crisis = regime_is_crisis(F, cfg) if cfg.regime_gate else pd.Series(False, index=F.index)
    W = target_weights(F, cfg)

    n = len(F)
    since = int((n - 1) % cfg.rebalance_days)
    # TÍN HIỆU LẤY TẠI NẾN TÁI CÂN BẰNG GẦN NHẤT, không phải nến hiện tại. Vị thế
    # được GIỮ giữa hai lần tái cân bằng nên tín hiệu hôm nay đã trôi khỏi tín hiệu
    # lúc ra quyết định; ghép hai cái đó sinh bản ghi TỰ MÂU THUẪN ("hạng 5/8 —
    # thuộc top 3"). Lệch thêm một ngày vì `target_weights` đọc `signal.iloc[i-1]`.
    j = max((n - 1) - since - 1, 0)
    return RT.traces_from_ranking(
        timestamp=F.index[-1], strategy="CurrencyReversal",
        signal_name=f"reversal_{cfg.lookback_days}d",
        signal=signal.iloc[j], weights=W.iloc[-1], n_leg=cfg.n_leg,
        regime="CRISIS" if bool(crisis.iloc[-1]) else "CALM",
        regime_blocking=bool(crisis.iloc[-1]),
        vol=vol.iloc[j], bars_since=since,
        bars_next=cfg.rebalance_days - since)


def execution_ok(now_utc: pd.Timestamp) -> Tuple[bool, str]:
    """Có được phép khớp lệnh tái cân bằng vào lúc này không.

    Tách khỏi `live_targets()` có chủ ý: tín hiệu và quyền thực thi là hai quyết
    định khác nhau (Dempster & Leemans 2004, tầng 1 vs tầng 2 — "tầng 1 nói vị thế
    nên giữ trong thế giới lý tưởng; tầng 2 xét rủi ro thế giới thật rồi mới quyết
    định có giao dịch"). Trộn chúng lại là mất khả năng chặn lệnh mà không đụng
    vào logic tín hiệu.
    """
    h = int(pd.Timestamp(now_utc).hour)
    if h in FORBIDDEN_HOURS_UTC:
        return False, f"{h:02d}:00 UTC nằm trong cửa sổ rollover — spread giãn 1,4-3 lần"
    if h not in EXECUTION_WINDOW_UTC:
        return False, f"{h:02d}:00 UTC ngoài cửa sổ rẻ 10:00-16:00 UTC"
    return True, f"{h:02d}:00 UTC hợp lệ (tối ưu {EXECUTION_HOUR_UTC:02d}:00)"


# ══ NGUỒN GỐC — mỗi dòng một bài, kèm đường dẫn mở được
SOURCES = (
    "Li, Zhao, Hoi & Gopalkrishnan (2012) \"PAMR: Passive-Aggressive Mean Reversion "
    "Strategy for Portfolio Selection\", Machine Learning 87(2) — "
    "D:/project-learning/documents/forex-strategies/PAMR_ Passive-Aggressive Mean "
    "Reversion Strategy for Portfolio Se.pdf",
    "Menkhoff, Sarno, Schmeling & Schrimpf (2012) \"Currency Momentum Strategies\", J. "
    "Financial Economics 106(3) — "
    "D:/project-learning/documents/forex-strategies/Currency Momentum Strategies.pdf",
    "Brière & Drut (2009, sửa 2010) \"The Revenge of Fundamentals on Carry Trades "
    "during Crises\", Amundi WP-005-2009 — "
    "D:/project-learning/documents/forex-strategies/Working Paper July 2009 - the "
    "revenge of fundamentals on carry trades during crises.pdf",
)

# ══ THẺ LUẬT — dữ liệu cho GUI và tests/test_rulebook.py.
# ══ Bản người đọc là khối QUY TẮC VÀO LỆNH ở ĐẦU FILE, sinh ra từ đây.
# Thẻ luật KHAI BÁO — đối chiếu với bản ghi runtime của `execution/rule_trace.py`.
# Nếu bản ghi khớp thẻ này thì luật chạy đúng và thị trường đi ngược; nếu lệch thì
# code đã trôi khỏi luật. Chỉ có một trong hai thì không phân biệt được hai việc đó.
RULEBOOK = RB.RuleBook(
    name="CurrencyReversal",
    signal_tf="D1", execution_tf="H1", direction="BOTH",
    universe=("EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "USD"),
    traded=("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"),
    max_positions=2 * N_LEG,
    family="Cross-Sectional Currency Short-Term Reversal",
    source=" · ".join(SOURCES),
    hours_utc=f"khớp lúc {EXECUTION_HOUR_UTC:02d}:00 UTC; "
              f"cửa sổ chấp nhận {EXECUTION_WINDOW_UTC[0]:02d}-"
              f"{EXECUTION_WINDOW_UTC[-1]:02d}:00 (spread rẻ nhất: 1,6567 bps khứ hồi "
              f"lúc 15:00 so với 2,3043 lúc 22:00)",
    forbidden_hours_utc=FORBIDDEN_HOURS_UTC,
    indicators=(
        f"tín hiệu = −(lợi nhuận log tích luỹ {LOOKBACK_DAYS} ngày của từng đồng)",
        f"σ({VOL_WINDOW} ngày) của từng đồng — CHỈ để chia tỷ trọng, không để chọn",
        f"biến động rổ làm mượt {REGIME_VOL_WINDOW} ngày",
        f"phân vị TRƯỢT {REGIME_QUANTILE:.0%} của {REGIME_WINDOW} ngày trước (.shift(1))",
    ),
    entry_logic="RANK",
    entry_rules=(
        RB.Rule("a", f"hôm nay là ngày tái cân bằng (mỗi {REBALANCE_DAYS} ngày)",
                "giữ vị thế giữa hai lần tái cân bằng là thứ giữ chi phí thấp"),
        RB.Rule("b", f"MUA {N_LEG} đồng có tín hiệu CAO nhất (= yếu nhất quá khứ)",
                "Menkhoff et al. dùng đúng 3 cao / 3 thấp"),
        RB.Rule("c", f"BÁN {N_LEG} đồng có tín hiệu THẤP nhất (= mạnh nhất quá khứ)",
                "hai chân đối xứng → phơi nhiễm USD ròng ≈ 0 (đo: max|sum| = 1,7e-13)"),
        RB.Rule("d", f"tỷ trọng trong mỗi chân ∝ 1/σ({VOL_WINDOW}), tổng mỗi chân = 1",
                "Olszweski & Zhou: chia đều/inverse-vol thắng mean-variance (0,98 vs 0,70)"),
        RB.Rule("e", f"biến động rổ < phân vị {REGIME_QUANTILE:.0%} trượt "
                     f"{REGIME_WINDOW} ngày",
                "CALM +5,56%/năm (Sharpe 1,049) vs CRISIS −5,34% (−0,842) — đảo dấu hoàn toàn"),
    ),
    entry_price="quy tỷ trọng ĐỒNG TIỀN → tỷ trọng CẶP qua pair_weights(), khớp thị trường",
    exit_rules=(
        RB.Rule("x1", f"tái cân bằng kế tiếp sau {REBALANCE_DAYS} ngày",
                "không có thoát theo giá — đây là chiến lược tỷ trọng, không phải theo lệnh"),
        RB.Rule("x2", "cổng chế độ chuyển sang CRISIS → về 0 toàn bộ chân"),
    ),
    stop_loss="KHÔNG có SL theo giá — rủi ro quản bằng CỠ VỊ THẾ và time-stop",
    take_profit="không có — thoát theo tín hiệu hoặc time-stop",
    blocks=(
        "cổng chế độ CRISIS (phân vị 80 trượt 252 ngày) → đứng ngoài hoàn toàn",
        f"giờ CẤM UTC {FORBIDDEN_HOURS_UTC} — spread rộng nhất trong ngày",
        "biên swap broker > 2,0%/năm → chiến lược về ~0 (Sharpe 0,272), phải đổi broker",
    ),
    frequency=f"tái cân bằng mỗi {REBALANCE_DAYS} ngày giao dịch ≈ 12 lần/năm",
    avg_holding=f"{REBALANCE_DAYS} ngày giao dịch",
    expectancy="Sharpe 0,576 ALL · 0,395 OOS · MaxDD 8,27% (sau đủ chi phí, đòn bẩy 1,0)",
    trace_signal_name=f"reversal_{LOOKBACK_DAYS}d",
)
