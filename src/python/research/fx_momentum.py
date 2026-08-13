"""fx_momentum.py — nhân momentum thang D1, thực thi trên H1.

VÌ SAO CHUYỂN SANG ĐÂY (kết quả đo được, không phải đổi ý)
=========================================================
Ba cổng trung thực đã BÁC BỎ hướng khai thác hiệu ứng fix ở cấp giờ
(`fx_fix_portfolio`, `reports/fx_research/fix_selected_rules.csv`):
  * 1/1104 luật có net t >= 2,0 trên DEV → OOS Sharpe **−1,34** (DEV +1,01)
  * danh mục đã chọn nằm ở **phân vị 44%** của control ngẫu nhiên, p = 0,56
  * DSR = 0,0000 với 1104 phép thử
Và phân phối control cho p50 OOS Sharpe = −1,21: *trung bình* mọi luật trong không
gian đó lỗ sau chi phí. Tín hiệu fix là THẬT (EURUSD h13 Frankfurt, gross t = −3,83,
đặc tả trước bởi Krohn) nhưng độ lớn của nó ≈ đúng MỘT lượt khứ hồi, nên sau chi phí
phân phối kết quả nằm quanh 0 và không phép chọn nào thắng được nhiễu.

Nguyên tắc 2 của `docs/forex/02_kien_thuc_nen_internet.md` §6 chỉ đúng đường ra:
ràng buộc thật là **SỐ LƯỢT KHỨ HỒI**. Phá nó không bằng tín hiệu tốt hơn mà bằng
**giữ vị thế lâu hơn**:

    hiệu ứng fix   1 lượt/ngày   → chi phí 0,91 bps trên drift ~1,0 bps → ratio ~1
    momentum D1    ~6 lượt/NĂM  → chi phí ~5 bps/năm trên lợi nhuận ~700 bps → ratio ~140

Chênh nhau hai bậc độ lớn. Đây là lý do cấu trúc, không phải một lựa chọn tham số.

GIẢ THUYẾT — ĐẶC TẢ TRƯỚC, MỘT LUẬT DUY NHẤT
============================================
Olszweski, F. & Zhou, G. (2014). "Strategy diversification: Combining momentum and
carry strategies within a foreign exchange portfolio." *Journal of Derivatives &
Hedge Funds* 19(4), 311-320.

Nguồn này là bằng chứng mạnh nhất trong toàn bộ corpus vì bốn lý do: 20 năm
(4/1993–3/2013), FX majors chiếm 88% turnover toàn cầu (BIS 2010), **đã bao gồm
commission và slippage**, và tác giả là người quản $500M thật tại Eclipse Capital.

Luật của họ, nguyên văn, không thêm không bớt:
  * **Giao MA 20 ngày / MA 120 ngày.** Long khi MA20 > MA120, short khi MA20 < MA120.
  * **LUÔN có vị thế — không có vùng trung tính** ("pure reversal strategy").
  * **Sizing = nghịch đảo biến động**: mỗi thị trường nhận tỷ trọng ∝ 1/σ, với σ là
    độ lệch chuẩn trượt 1 tháng.
  * Kết quả họ báo: lợi nhuận 7,08%/năm · std 8,93% · MaxDD −17,42% · **Sharpe 0,79**
    · Calmar 0,41.

⚠️ KHÔNG được tinh chỉnh 20/120. Đó là con số của nguồn, và Burghardt et al. (2010)
độc lập xác nhận nó đại diện cho khung thời gian mà nhiều quỹ managed-futures dùng.
Quét quanh nó là biến một phép thử xác nhận thành một cuộc dò dẫm 1104-phép-thử nữa
— chính thứ vừa thất bại. Việc kiểm tra độ ổn định quanh (20,120) là một bài
sensitivity RIÊNG, chạy SAU khi luật gốc đã cho verdict, và chỉ để xem có vách đá
hay không.

VAI TRÒ CỦA H1 — khung giao dịch chính
======================================
Tín hiệu sinh ra ở D1, nhưng H1 là nơi mọi thứ khác xảy ra:
  * **thực thi**: cú đảo vị thế được khớp ở giờ H1 có spread rẻ nhất, không phải
    mù quáng tại D1 close (đo được: EURUSD spread 0,27 pip lúc 12-18 UTC vs 0,34
    lúc 00 UTC — chênh 26%)
  * **quản trị rủi ro**: mọi cổng chặn/đóng lệnh đánh giá theo nến H1
  * **kiểm định**: `execution_hour=None` (khớp tại D1 close) là baseline; mọi giờ H1
    khác được đo so với nó để biết thực thi H1 có thêm giá trị thật hay không
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.python.research import fx_clock as C
from src.python.shared import fx_data as D
from src.python.shared import asset_profile as AP

# ── tham số của NGUỒN. Không tinh chỉnh.
MA_FAST = 20
MA_SLOW = 120
VOL_WINDOW = 20          # "rolling 1-month standard deviation"

DEV_END = pd.Timestamp("2024-01-01")


# ═══════════════════════════════════════════════════════════ dữ liệu
def daily_frame(symbol: str, start: str = "2015-01-01") -> pd.DataFrame:
    """Nến D1 từ M1 (bao phủ nới — một ngày FX không bao giờ đủ 1440 nến M1).

    Index = ngày UTC. `ret` = lợi nhuận log của CHÍNH CẶP (không phải DOL) vì
    momentum giao dịch theo hướng của cặp, không cần quy ước dollar-factor.
    """
    m1 = D.load_m1(symbol)
    g = m1.resample("1D", origin="start_day")
    d = g.agg({"open": "first", "high": "max", "low": "min", "close": "last",
               "spread_usd": "median"}).dropna(subset=["open", "high", "low", "close"])
    d = d[d.index >= start]
    d["ret"] = np.log(d["close"]).diff()
    return d


def signal_frame(symbol: str, start: str = "2015-01-01") -> pd.DataFrame:
    """Tín hiệu momentum trên nến D1 ĐÃ ĐÓNG. `side` dùng được từ ngày KẾ TIẾP.

    `.shift(1)` là điểm chống look-ahead: MA tính đến hết ngày D quyết định vị thế
    của ngày D+1. Không shift thì chiến lược biết close của chính ngày nó giao dịch.
    """
    d = daily_frame(symbol, start=start)
    ma_f = d["close"].rolling(MA_FAST, min_periods=MA_FAST).mean()
    ma_s = d["close"].rolling(MA_SLOW, min_periods=MA_SLOW).mean()
    raw = np.sign(ma_f - ma_s)                       # luôn ±1, không có vùng phẳng
    d["side"] = raw.shift(1)
    # biến động trượt 1 tháng, cũng dịch 1 ngày
    d["vol"] = d["ret"].rolling(VOL_WINDOW, min_periods=VOL_WINDOW).std().shift(1)
    return d.dropna(subset=["side", "vol", "ret"])


# ═══════════════════════════════════════════════════════════ mô phỏng 1 cặp
@dataclass
class LegResult:
    symbol: str
    n_days: int
    n_flips: int
    flips_per_year: float
    gross_bps_day: float
    cost_bps_day: float
    net_bps_day: float
    sharpe_gross: float
    sharpe_net: float
    max_dd_bps: float
    series: pd.Series = field(repr=False, default_factory=lambda: pd.Series(dtype=float))


def run_leg(symbol: str, *, start: str = "2015-01-01",
            end: Optional[str] = None) -> LegResult:
    """Momentum trên MỘT cặp, chưa chuẩn hoá tỷ trọng. Đơn vị bps/ngày.

    Chi phí chỉ tính khi vị thế THAY ĐỔI: `|Δside|/2` lượt khứ hồi (đảo từ +1 sang
    −1 là |Δ| = 2, tức đóng một chiều và mở chiều kia = 1 khứ hồi trọn vẹn).
    """
    d = signal_frame(symbol, start=start)
    if end:
        d = d[d.index < pd.Timestamp(end)]
    prof = AP.get(symbol)
    px = float(d["close"].median())
    sp = float(d["spread_usd"].median())
    cost_1rt_bps = (sp + prof.commission_price_units(px)) / px * 1e4

    side = d["side"].to_numpy()
    ret_bps = d["ret"].to_numpy() * 1e4
    gross = side * ret_bps
    dside = np.abs(np.diff(side, prepend=side[0]))
    cost = (dside / 2.0) * cost_1rt_bps
    net = gross - cost

    s_net = pd.Series(net, index=d.index)
    cum = s_net.cumsum()
    ann = 252.0
    def sh(x):
        sd = float(np.std(x, ddof=1))
        return float(np.mean(x)) / sd * np.sqrt(ann) if sd > 0 else float("nan")
    n_flips = int((dside > 0).sum())
    years = max((d.index.max() - d.index.min()).days / 365.25, 1e-9)
    return LegResult(
        symbol=symbol, n_days=len(d), n_flips=n_flips,
        flips_per_year=round(n_flips / years, 2),
        gross_bps_day=round(float(gross.mean()), 4),
        cost_bps_day=round(float(cost.mean()), 4),
        net_bps_day=round(float(net.mean()), 4),
        sharpe_gross=round(sh(gross), 3), sharpe_net=round(sh(net), 3),
        max_dd_bps=round(float((cum.cummax() - cum).max()), 1),
        series=s_net,
    )


# ═══════════════════════════════════════════════════════════ danh mục
def run_portfolio(symbols: Sequence[str] = AP.FX_ALL, *,
                  start: str = "2020-01-01",
                  end: Optional[str] = None,
                  inverse_vol: bool = True) -> Tuple[pd.Series, pd.DataFrame]:
    """Danh mục momentum, **tỷ trọng nghịch đảo biến động** theo Olszweski & Zhou.

    Tỷ trọng dùng CHỈ biến động (không dùng lợi nhuận kỳ vọng) — đây là ranh giới mà
    chính nguồn xác lập: Min-Var (chỉ phương sai) tốt bằng chia đều, còn Max-Utility
    (dùng kỳ vọng lợi nhuận) cho Sharpe 0,70 < 0,79 của momentum đơn lẻ.
    """
    legs, frames = {}, {}
    for sym in symbols:
        d = signal_frame(sym, start=start)
        if end:
            d = d[d.index < pd.Timestamp(end)]
        prof = AP.get(sym)
        px = float(d["close"].median()); sp = float(d["spread_usd"].median())
        c1 = (sp + prof.commission_price_units(px)) / px * 1e4
        side = d["side"]
        dside = side.diff().abs().fillna(0.0)
        frames[sym] = pd.DataFrame({
            "gross": side * d["ret"] * 1e4,
            "cost": (dside / 2.0) * c1,
            "invvol": 1.0 / d["vol"].replace(0, np.nan),
        })
    idx = sorted(set().union(*[f.index for f in frames.values()]))
    G = pd.DataFrame({s: f["gross"] for s, f in frames.items()}).reindex(idx)
    K = pd.DataFrame({s: f["cost"] for s, f in frames.items()}).reindex(idx)
    V = pd.DataFrame({s: f["invvol"] for s, f in frames.items()}).reindex(idx)
    W = V.div(V.sum(axis=1), axis=0) if inverse_vol else \
        pd.DataFrame(1.0, index=idx, columns=G.columns).where(G.notna()).pipe(
            lambda x: x.div(x.sum(axis=1), axis=0))
    gross = (G * W).sum(axis=1, min_count=1)
    cost = (K * W).sum(axis=1, min_count=1)
    net = (gross - cost).dropna()
    detail = pd.DataFrame({"gross_bps": gross, "cost_bps": cost, "net_bps": net})
    return net, detail


def stats(s: pd.Series, label: str = "") -> Dict[str, float]:
    if len(s) < 20:
        return {}
    cum = s.cumsum()
    dd = (cum.cummax() - cum)
    ann = 252.0
    sd = float(s.std(ddof=1))
    tot_pct = float(cum.iloc[-1]) / 100.0
    years = max((s.index.max() - s.index.min()).days / 365.25, 1e-9)
    downside = float(s[s < 0].std(ddof=1)) if (s < 0).any() else np.nan
    return {
        "label": label, "n_days": len(s),
        "ann_ret_pct": round(tot_pct / years, 2),
        "ann_vol_pct": round(sd * np.sqrt(ann) / 100.0, 2),
        "sharpe": round(float(s.mean()) / sd * np.sqrt(ann), 3) if sd > 0 else np.nan,
        "sortino": round(float(s.mean()) / downside * np.sqrt(ann), 3) if downside and downside > 0 else np.nan,
        "max_dd_pct": round(float(dd.max()) / 100.0, 2),
        "calmar": round((tot_pct / years) / (float(dd.max()) / 100.0), 3) if dd.max() > 0 else np.nan,
        "hit_rate": round(float((s > 0).mean()), 3),
        "worst_day_pct": round(float(s.min()) / 100.0, 3),
    }
