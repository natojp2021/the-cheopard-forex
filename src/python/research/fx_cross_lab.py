"""fx_cross_lab.py — lab quét NHIỀU họ tín hiệu × 4 khung thời gian trên 20 cặp chéo.

VÌ SAO MỞ RỘNG TRÊN CROSS, KHÔNG PHẢI TRÊN CẶP USD
===================================================
`cross_mean_reversion` (H1) là chiến lược duy nhất qua được cổng sau 13 hướng nội
ngày thất bại, và lý do nó thắng là CẤU TRÚC: cross là spread giữa hai đồng tiền,
nên thành phần USD đã bị triệt tiêu và cùng một mức lệch giá là tỷ lệ lớn hơn nhiều.

Đo được sự khác biệt đó:
    EURUSD/GBPUSD (2 chân USD)  net +1,31 bps · OOS −1,11
    EURGBP        (1 cross)     net +15,35 bps · OOS +1,96

Nếu lợi thế đến từ cấu trúc thì nó KHÔNG chỉ áp cho một họ tín hiệu và một khung.
Lab này kiểm điều đó một cách hệ thống thay vì đoán.

THIẾT KẾ DỰA TRÊN VỊ THẾ, KHÔNG DỰA TRÊN LỆNH
==============================================
Mỗi họ tín hiệu trả về một **chuỗi vị thế** (+1/−1/0) cho từng cross. Bộ mô phỏng
duy nhất quy vị thế thành P&L kèm chi phí. Lợi ích: mọi họ đi qua đúng một đường
tính chi phí, nên không thể có chuyện một họ được tính phí nhẹ hơn họ khác — đó là
cách so sánh giữa các họ trở nên có nghĩa.

Chi phí gồm hai thành phần và chúng scale khác nhau theo khung:
    giao dịch = |Δvị thế| × chi phí khứ hồi / 2      -> tỷ lệ với TẦN SUẤT
    swap      = |vị thế| × swap mỗi đêm × (giờ/nến)/24 -> tỷ lệ với THỜI GIAN GIỮ
Khung ngắn tăng vế đầu; khung dài tăng vế sau. Không có khung nào "rẻ" tuyệt đối.

NĂM HỌ TÍN HIỆU — MỖI HỌ MỘT NGUỒN
===================================
1. `zscore_band`  Mean reversion quanh trung bình động (Zheng Nan 2025). Đây là họ
                  đã thắng ở H1; đưa vào đây để có mốc so sánh trên cùng bộ máy.
2. `donchian`     Phá vỡ biên N nến + thoát khi chạm biên đối diện (Turtle; AdTurtle
                  — Vezeris et al., JRFM 2019, đo trên chính Forex).
3. `cross_carry`  Long cross có chênh lệch lãi suất dương, short cross âm
                  (Burnside/Eichenbaum/Rebelo NBER w16942; Olszweski & Zhou 2014).
                  Trên cross thì carry là chênh lệch TRỰC TIẾP giữa hai đồng, không
                  phải qua USD — mạnh hơn và sạch hơn bản trên cặp USD.
4. `xs_reversal`  Xếp hạng 20 cross với nhau, long yếu nhất / short mạnh nhất
                  (PAMR — Li/Zhao/Hoi 2012; Menkhoff et al. BIS WP366).
5. `tsmom`        Time-series momentum: theo dấu lợi nhuận `lookback` nến trước
                  (Moskowitz/Ooi/Pedersen JFE 2012). Họ đo momentum bền 1-12 tháng.

⚠️ CẢNH BÁO VỀ "ĐẾM SỐ CHIẾN LƯỢC" — ĐÃ ĐO ĐƯỢC, KHÔNG PHẢI GIẢ THIẾT
======================================================================
Cùng một họ tín hiệu ở hai khung khác nhau KHÔNG tự động là hai chiến lược. Kiểm
toán vòng 40 đo trên chính lab này: 8 "ứng viên" (2 họ × 4 khung) cho **28/28 cặp
có tương quan > 0,7** — xs_momentum giữa các khung 0,93-0,97; tsmom 0,95-0,98.

Nguyên nhân là ở THAM SỐ, không ở dữ liệu: mặc định `lookback = bars_per_year/12`
tức "một tháng" ở MỌI khung. Một chiến lược lookback-1-tháng / tái-cân-bằng-1-tháng
có kinh tế học y hệt nhau dù nến là 30 phút hay 1 ngày — cỡ nến chỉ đổi độ phân giải
của điểm vào, không đổi bản chất cược.

Muốn có chiến lược THẬT SỰ khác nhau theo khung thì **HORIZON phải khác nhau**, tức
lookback/thời gian giữ tính theo SỐ NẾN phải cho ra khoảng thời gian lịch khác nhau.
Đó là lý do `scan_horizon_scaled()` truyền tham số tường minh cho từng khung thay vì
dùng mặc định.

`correlation_report()` là cổng bắt buộc, và mọi kết luận về SỐ LƯỢNG chiến lược phải
đọc kèm nó.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.python.research import fx_cross_pairs as CX
from src.python.shared import carry_costs as CC

FORM_END = pd.Timestamp("2024-01-01")

# Số giờ mỗi nến — dùng để quy swap (tính theo đêm) về mỗi nến.
BAR_HOURS: Dict[str, float] = {"M30": 0.5, "H1": 1.0, "H4": 4.0, "D1": 24.0}
BARS_PER_YEAR: Dict[str, float] = {"M30": 252 * 48, "H1": 252 * 24,
                                   "H4": 252 * 6, "D1": 252}


# ═══════════════════════════════════════════════════════ nền dữ liệu
@dataclass
class CrossPanel:
    timeframe: str
    price: pd.DataFrame                  # index=time, cols=cross
    logp: pd.DataFrame
    specs: Dict[str, CX.CrossSpec]
    cost_1rt_bps: pd.Series              # chi phí khứ hồi mỗi cross (bps)
    carry_bps_per_bar: pd.DataFrame      # phí carry mỗi nến khi LONG cross (bps)


def build_panel(timeframe: str = "H1", start: str = "2020-01-01",
                broker_markup_pct: float = 1.0) -> CrossPanel:
    """Dựng bảng giá cross + hai bảng chi phí, tất cả trên cùng lưới thời gian."""
    P, specs = CX.build_crosses(timeframe, start=start)
    logp = np.log(P)

    cost = {}
    for name, sp in specs.items():
        px = float(P[name].median())
        cost[name] = sp.cost_1rt_bps_at(px)

    # carry mỗi nến khi LONG cross: −(r_base − r_quote) + biên broker, quy về nến
    days = pd.DatetimeIndex(sorted(set(P.index.normalize())))
    rates = CC.rate_series(days)
    k = CC.SWAP_CALENDAR_MULTIPLIER / 365.0 * 100.0 * (BAR_HOURS[timeframe] / 24.0)
    carry = {}
    for name, sp in specs.items():
        diff = (rates.get(sp.base, 0.0) - rates.get(sp.quote, 0.0))
        if isinstance(diff, float):
            diff = pd.Series(diff, index=days)
        carry[name] = (-diff + broker_markup_pct) * k
    C = pd.DataFrame(carry).reindex(P.index.normalize()).set_index(P.index)

    return CrossPanel(timeframe=timeframe, price=P, logp=logp, specs=specs,
                      cost_1rt_bps=pd.Series(cost), carry_bps_per_bar=C)


# ═══════════════════════════════════════════════════════ mô phỏng chung
@dataclass
class SimResult:
    name: str
    timeframe: str
    pnl_bar: pd.Series                   # bps mỗi nến, danh mục
    pnl_daily: pd.Series                 # bps mỗi ngày
    gross_bps_bar: float
    trade_cost_bps_bar: float
    carry_cost_bps_bar: float
    turnover_per_year: float
    time_in_market: float
    positions: pd.DataFrame = field(repr=False, default_factory=pd.DataFrame)


def simulate_positions(panel: CrossPanel, pos: pd.DataFrame,
                       name: str = "") -> SimResult:
    """Quy chuỗi vị thế thành P&L kèm ĐỦ chi phí.

    Vị thế tại nến `t` áp cho lợi nhuận của nến `t+1` — `.shift(1)` trên lợi nhuận
    thay vì trên vị thế, để không có nến nào ăn lợi nhuận của chính nến sinh tín
    hiệu. Đây là chỗ dễ tạo look-ahead nhất trong toàn bộ lab.
    """
    ret = panel.logp.diff() * 1e4                    # bps, nến t
    pos = pos.reindex(index=ret.index, columns=ret.columns).fillna(0.0)

    gross = (pos.shift(1) * ret).sum(axis=1)
    turn = pos.diff().abs().fillna(pos.abs())
    tcost = (turn * panel.cost_1rt_bps.reindex(pos.columns) / 2.0).sum(axis=1)
    ccost = (pos.abs().shift(1) * panel.carry_bps_per_bar).sum(axis=1)

    n_active = pos.abs().sum(axis=1).replace(0, np.nan)
    scale = 1.0 / n_active                            # chia đều giữa cross đang mở
    pnl = ((gross - tcost - ccost) * scale.fillna(0.0)).fillna(0.0)

    bars_per_year = BARS_PER_YEAR[panel.timeframe]
    years = max(len(pnl) / bars_per_year, 1e-9)
    return SimResult(
        name=name, timeframe=panel.timeframe,
        pnl_bar=pnl, pnl_daily=pnl.resample("1D").sum().fillna(0.0),
        gross_bps_bar=float((gross * scale.fillna(0.0)).fillna(0.0).mean()),
        trade_cost_bps_bar=float((tcost * scale.fillna(0.0)).fillna(0.0).mean()),
        carry_cost_bps_bar=float((ccost * scale.fillna(0.0)).fillna(0.0).mean()),
        turnover_per_year=float(turn.sum().sum() / years / max(len(pos.columns), 1)),
        time_in_market=float((pos.abs().sum(axis=1) > 0).mean()),
        positions=pos)


# ═══════════════════════════════════════════════════════ năm họ tín hiệu
def _half_life_rolling(lp: pd.Series, window: int, step: int) -> pd.Series:
    """Half-life ước lượng lại mỗi `step` nến trên `window` nến trước. Nhân quả."""
    out = pd.Series(np.nan, index=lp.index)
    v = lp.to_numpy()
    for i in range(window, len(v), step):
        seg = v[i - window:i]
        out.iloc[i] = CX.half_life(seg - seg.mean())
    return out.ffill()


def sig_zscore_band(panel: CrossPanel, *, hl_mult: float = 4.32,
                    entry_sigma: float = 2.0, min_hl: int = 4,
                    max_hl: int = 120, reest: int = 500,
                    use_timestop: bool = True) -> pd.DataFrame:
    """Mean reversion quanh trung bình động, cửa sổ = HL × hệ số (Zheng Nan).

    ⚠️ `use_timestop` KHÔNG phải tuỳ chọn phong cách — bản đầu của hàm này thiếu nó
    và đó là một BUG đã đo được (kiểm toán vòng 40): không time-stop thì vị thế thua
    bị giữ vô hạn, thời gian giữ trung bình 31,4 ngày thay vì 6,4, và Sharpe H1 rơi
    từ **+1,059 xuống −0,241**. Đây chính là điều Zheng Nan đo được khi so time-stop
    với stop 3σ (+85% P&L) — bản thiếu time-stop không chỉ kém hơn, nó ÂM.
    Để `False` chỉ khi cố ý đo lại chính hiệu ứng đó.
    """
    pos = pd.DataFrame(0.0, index=panel.logp.index, columns=panel.logp.columns)
    for name in panel.logp.columns:
        lp = panel.logp[name].dropna()
        hl = _half_life_rolling(lp, min(2000, len(lp) // 2), reest)
        win = (hl * hl_mult).clip(lower=min_hl * hl_mult,
                                  upper=max_hl * hl_mult).round()
        ok = hl.between(min_hl, max_hl)
        p = np.zeros(len(lp))
        v = lp.to_numpy()
        w_arr = win.to_numpy()
        ok_arr = ok.to_numpy()
        state = 0
        was = 0
        held = 0
        for i in range(int(min_hl * hl_mult) + 10, len(v)):
            w = int(w_arr[i]) if np.isfinite(w_arr[i]) else 0
            if not ok_arr[i] or w < 10 or i < w:
                # ĐÓNG vị thế, không giữ. Bản đầu viết `p[i] = state; continue` —
                # tức khi half-life ra ngoài dải thì vị thế bị ĐÓNG BĂNG vô hạn.
                # Đo được (kiểm toán vòng 40): thời gian trong thị trường 93%, giữ
                # trung bình 31,4 ngày thay vì 6,4, Sharpe H1 −0,234 thay vì +1,059.
                # Half-life ra ngoài dải nghĩa là "không còn cơ sở để ở trong lệnh",
                # nên phản ứng đúng là THOÁT.
                state, held, was = 0, 0, 0
                p[i] = 0.0
                continue
            h = v[i - w:i]
            mu, sd = h.mean(), h.std(ddof=1)
            if sd <= 0:
                p[i] = state
                continue
            z = (v[i] - mu) / sd
            if state != 0:
                held += 1
                hit_mean = (state == 1 and v[i] >= mu) or (state == -1 and v[i] <= mu)
                timeout = use_timestop and held >= max(int(w), 1)
                if hit_mean or timeout:
                    state, held = 0, 0
            else:
                if z > entry_sigma:
                    was = 1
                elif z < -entry_sigma:
                    was = -1
                elif was == 1:
                    state, was, held = -1, 0, 0
                elif was == -1:
                    state, was, held = 1, 0, 0
            p[i] = state
        pos[name] = pd.Series(p, index=lp.index)
    return pos.fillna(0.0)


def sig_donchian(panel: CrossPanel, *, lookback: int = 55,
                 exit_lookback: int = 20) -> pd.DataFrame:
    """Phá vỡ biên `lookback` nến, thoát khi chạm biên `exit_lookback` đối diện.

    Đây là luật Turtle nguyên bản (Faith, *Way of the Turtle*), và AdTurtle
    (Vezeris et al., JRFM 2019) đo nó trên chính Forex. Dùng `shift(1)` trên biên
    để không so giá hiện tại với biên đã chứa chính nó.
    """
    pos = pd.DataFrame(0.0, index=panel.price.index, columns=panel.price.columns)
    for name in panel.price.columns:
        p = panel.price[name]
        hi = p.rolling(lookback).max().shift(1)
        lo = p.rolling(lookback).min().shift(1)
        xhi = p.rolling(exit_lookback).max().shift(1)
        xlo = p.rolling(exit_lookback).min().shift(1)
        state = np.zeros(len(p))
        s = 0
        pv, hiv, lov, xhv, xlv = (p.to_numpy(), hi.to_numpy(), lo.to_numpy(),
                                  xhi.to_numpy(), xlo.to_numpy())
        for i in range(lookback + 1, len(pv)):
            if s == 0:
                if np.isfinite(hiv[i]) and pv[i] > hiv[i]:
                    s = 1
                elif np.isfinite(lov[i]) and pv[i] < lov[i]:
                    s = -1
            elif s == 1 and np.isfinite(xlv[i]) and pv[i] < xlv[i]:
                s = 0
            elif s == -1 and np.isfinite(xhv[i]) and pv[i] > xhv[i]:
                s = 0
            state[i] = s
        pos[name] = pd.Series(state, index=p.index)
    return pos


def sig_cross_carry(panel: CrossPanel, *, n_leg: int = 5,
                    rebalance_bars: int = 0) -> pd.DataFrame:
    """Long cross có chênh lệch lãi suất CAO nhất, short THẤP nhất.

    Trên cross, carry là chênh lệch TRỰC TIẾP giữa hai đồng tiền (r_base − r_quote),
    không phải suy qua USD. Điều đó cho dải chênh lệch rộng hơn nhiều — ví dụ
    AUDJPY mang cả AUD cao lẫn JPY thấp trên cùng một công cụ.
    """
    if rebalance_bars <= 0:
        rebalance_bars = int(BARS_PER_YEAR[panel.timeframe] / 12)   # ~1 tháng
    days = pd.DatetimeIndex(sorted(set(panel.price.index.normalize())))
    rates = CC.rate_series(days)
    diff = {}
    for name, sp in panel.specs.items():
        d = rates.get(sp.base, 0.0) - rates.get(sp.quote, 0.0)
        diff[name] = d if not isinstance(d, float) else pd.Series(d, index=days)
    D = pd.DataFrame(diff).reindex(panel.price.index.normalize()).set_index(panel.price.index)

    pos = pd.DataFrame(0.0, index=panel.price.index, columns=panel.price.columns)
    held = pd.Series(0.0, index=panel.price.columns)
    for i, t in enumerate(panel.price.index):
        if i % rebalance_bars == 0 and i > 0:
            s = D.iloc[i - 1].dropna()
            if len(s) >= 2 * n_leg:
                o = s.sort_values(ascending=False)
                held = pd.Series(0.0, index=panel.price.columns)
                held[list(o.index[:n_leg])] = 1.0
                held[list(o.index[-n_leg:])] = -1.0
        pos.iloc[i] = held
    return pos


def sig_xs_reversal(panel: CrossPanel, *, lookback: int = 0, n_leg: int = 5,
                    rebalance_bars: int = 0, sign: int = -1) -> pd.DataFrame:
    """Xếp hạng 20 cross với nhau: long yếu nhất / short mạnh nhất (`sign=−1`).

    `sign=+1` cho momentum cắt ngang. Cả hai chiều đều phải đo vì Menkhoff et al.
    (*Currency Value* 2014) cảnh báo chiều của tín hiệu cắt ngang trên FX không
    hiển nhiên — và ở thang 21 ngày ta đã đo được dấu ĐẢO so với 1-12 tháng.
    """
    bpy = BARS_PER_YEAR[panel.timeframe]
    if lookback <= 0:
        lookback = int(bpy / 12)
    if rebalance_bars <= 0:
        rebalance_bars = lookback
    cum = panel.logp.cumsum()
    mom = sign * (cum - cum.shift(lookback))
    vol = panel.logp.diff().rolling(max(lookback * 3, 60), min_periods=30).std()

    pos = pd.DataFrame(0.0, index=panel.logp.index, columns=panel.logp.columns)
    held = pd.Series(0.0, index=panel.logp.columns)
    for i in range(len(pos)):
        if i % rebalance_bars == 0 and i > lookback:
            s, v = mom.iloc[i - 1].dropna(), vol.iloc[i - 1]
            if len(s) >= 2 * n_leg:
                o = s.sort_values(ascending=False)
                held = pd.Series(0.0, index=panel.logp.columns)
                for grp, sg in ((list(o.index[:n_leg]), 1.0),
                                (list(o.index[-n_leg:]), -1.0)):
                    iv = (1.0 / v[grp].replace(0, np.nan)).fillna(0.0)
                    if iv.sum() > 0:
                        held[grp] = sg * iv / iv.sum() * n_leg
        pos.iloc[i] = held
    return pos


def sig_tsmom(panel: CrossPanel, *, lookback: int = 0,
              rebalance_bars: int = 0) -> pd.DataFrame:
    """Time-series momentum: theo dấu lợi nhuận `lookback` nến trước (TSMOM).

    Moskowitz/Ooi/Pedersen đo momentum bền 1-12 tháng rồi ĐẢO ở horizon dài hơn.
    Mặc định lookback ≈ 3 tháng, nằm trong dải họ báo là có tín hiệu.
    """
    bpy = BARS_PER_YEAR[panel.timeframe]
    if lookback <= 0:
        lookback = int(bpy / 4)
    if rebalance_bars <= 0:
        rebalance_bars = max(int(bpy / 12), 1)
    cum = panel.logp.cumsum()
    sig = np.sign(cum - cum.shift(lookback))

    pos = pd.DataFrame(0.0, index=panel.logp.index, columns=panel.logp.columns)
    held = pd.Series(0.0, index=panel.logp.columns)
    for i in range(len(pos)):
        if i % rebalance_bars == 0 and i > lookback:
            s = sig.iloc[i - 1]
            if s.notna().sum() >= 5:
                held = s.fillna(0.0)
        pos.iloc[i] = held
    return pos


SIGNAL_FAMILIES: Dict[str, Callable[..., pd.DataFrame]] = {
    "zscore_band": sig_zscore_band,
    "donchian": sig_donchian,
    "cross_carry": sig_cross_carry,
    "xs_reversal": sig_xs_reversal,
    "tsmom": sig_tsmom,
}


# ═══════════════════════════════════════════════════════ báo cáo
def stats(pnl_daily: pd.Series, label: str = "") -> Dict[str, object]:
    s = pnl_daily[pnl_daily.index >= pd.Timestamp("2020-04-01")]
    if len(s) < 60:
        return {"label": label, "n": len(s)}
    cum = s.cumsum()
    dd = cum.cummax() - cum
    sd = float(s.std(ddof=1))
    yrs = max((s.index.max() - s.index.min()).days / 365.25, 1e-9)
    return {
        "label": label,
        "sharpe": round(float(s.mean()) / sd * np.sqrt(252), 3) if sd > 0 else np.nan,
        "ann_pct": round(float(cum.iloc[-1]) / 100.0 / yrs, 2),
        "vol_pct": round(sd * np.sqrt(252) / 100.0, 2),
        "max_dd_pct": round(float(dd.max()) / 100.0, 2),
        "hit": round(float((s[s != 0] > 0).mean()), 3) if (s != 0).any() else np.nan,
    }


def split_report(res: SimResult) -> Dict[str, object]:
    d = res.pnl_daily
    a = stats(d, "ALL")
    f = stats(d[d.index < FORM_END], "FORM")
    o = stats(d[d.index >= FORM_END], "OOS")
    return {
        "family": res.name, "tf": res.timeframe,
        "ALL": a.get("sharpe"), "FORM": f.get("sharpe"), "OOS": o.get("sharpe"),
        "ann%": a.get("ann_pct"), "vol%": a.get("vol_pct"),
        "maxDD%": a.get("max_dd_pct"),
        "gross": round(res.gross_bps_bar, 4),
        "phi_gd": round(res.trade_cost_bps_bar, 4),
        "swap": round(res.carry_cost_bps_bar, 4),
        "turn/năm": round(res.turnover_per_year, 1),
        "%trong_tt": round(res.time_in_market, 3),
    }


def correlation_report(results: Sequence[SimResult]) -> pd.DataFrame:
    """Tương quan giữa các ứng viên — cổng chống 'đếm trùng chiến lược'.

    Hai ứng viên tương quan > ~0,7 là MỘT chiến lược chạy hai cỡ, không phải hai.
    """
    frame = {}
    for r in results:
        key = f"{r.name}.{r.timeframe}"
        frame[key] = r.pnl_daily
    return pd.DataFrame(frame).corr().round(3)
