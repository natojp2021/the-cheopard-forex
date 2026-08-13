"""fx_fix_portfolio.py — cổng trung thực: chọn luật trên DEV, đọc kết quả trên OOS.

VẤN ĐỀ PHẢI GIẢI
================
`scratch/fx_fix_run02.py` quét 7 cặp × 24 giờ × 2 chiều × (thô | hi-vol | me1 | me3)
= **1.344 phép thử**. Ở ngưỡng p<0,05 thì riêng ngẫu nhiên đã sinh ~67 "phát hiện".
Bảng có vài ô t≈3 KHÔNG chứng minh gì cả cho đến khi qua được ba cổng:

  CỔNG 1 — TÁCH MẪU. Chọn luật CHỈ trên DEV (2020→2024). Đọc verdict CHỈ trên
  OOS (2024→nay). Đây là cổng duy nhất không thể lách bằng thống kê.

  CỔNG 2 — CONTROL NGẪU NHIÊN. So danh mục đã chọn với danh mục gồm CÙNG SỐ LUẬT
  rút ngẫu nhiên từ cùng không gian. Nếu chọn-theo-DEV không thắng rút-ngẫu-nhiên
  trên OOS thì quy trình chọn không có giá trị — dù các luật có t bao nhiêu.

  CỔNG 3 — HIỆU CHỈNH ĐA KIỂM ĐỊNH. Deflated Sharpe Ratio (Bailey & López de Prado)
  trên số phép thử THẬT, không phải trên một luật đã được chọn ra.

THIẾT KẾ DANH MỤC — theo Olszweski & Zhou (2014)
===============================================
Đo được trên 20 năm FX: **chia đều thắng tối ưu hoá mean-variance** (Sharpe 0,98 vs
0,70) vì sai số ước lượng kỳ vọng lợi nhuận. Min-variance (chỉ dùng phương sai) tốt
bằng chia đều. Nên ở đây: **chia đều**, và chỉ dùng biến động để chuẩn hoá rủi ro
giữa các cặp — KHÔNG dùng lợi nhuận DEV để đặt tỷ trọng.

Lợi ích chính kỳ vọng cũng theo họ: không phải tăng lợi nhuận mà **cắt drawdown**
(−17,4%/−29,2% → −8,95%). Các luật ở đây nằm trên các cặp/giờ/ngày khác nhau nên
phần lớn là cược độc lập — đúng điều kiện để đa dạng hoá có tác dụng.

LOẠI ARTIFACT
=============
Giờ quanh lúc thị trường đóng/rollover có rất ít nến (n ≈ 200 so với ≈ 1.700) và
biên độ khổng lồ (AUDUSD h23 Frankfurt: −5,3 bps). Đó là hiệu ứng thanh khoản mỏng
cuối tuần, không phải cấu trúc phiên. Mọi giờ có `n < MIN_COVERAGE × n_max` bị loại
TRƯỚC khi chọn, không phải sau khi nhìn kết quả.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy import stats

from src.python.research import fx_clock as C
from src.python.research import fx_fix_lab as FL
from src.python.shared import asset_profile as AP

DEV_START = pd.Timestamp("2020-01-01")
DEV_END = pd.Timestamp("2024-01-01")

MIN_COVERAGE = 0.80        # giờ phải có >= 80% số ngày so với giờ dày nhất
MIN_TRADES_DEV = 60
MIN_TRADES_OOS = 25


# ═══════════════════════════════════════════════════ chuỗi lợi nhuận của một luật
@dataclass(frozen=True)
class RuleSpec:
    symbol: str
    tz_name: str            # "FFT" | "LDN" | "NY" | "TYO"
    hour: int
    usd_side: int
    regime: str             # "all" | "hivol" | "me1" | "me3"

    @property
    def key(self) -> str:
        return f"{self.symbol}|{self.tz_name}|h{self.hour:02d}|usd{self.usd_side:+d}|{self.regime}"


_TZ = {"FFT": C.TZ_FRANKFURT, "LDN": C.TZ_LONDON, "NY": C.TZ_NY, "TYO": C.TZ_TOKYO}


def rule_series(spec: RuleSpec, panel: pd.DataFrame, cost_1rt: float) -> pd.Series:
    """Chuỗi lợi nhuận RÒNG (bps) theo ngày của một luật. Index = ngày địa phương."""
    if spec.hour not in panel.columns:
        return pd.Series(dtype=float)
    if spec.regime == "all":
        mask = pd.Series(True, index=panel.index)
    elif spec.regime == "hivol":
        mask = FL.rolling_quintile_mask(panel, "prev_range_bps", 0.80)
    elif spec.regime == "me1":
        mask = panel["is_month_end_1"]
    elif spec.regime == "me3":
        mask = panel["is_month_end_3"]
    else:
        raise ValueError(spec.regime)
    dol = panel.loc[mask.reindex(panel.index, fill_value=False), spec.hour].dropna()
    return (-spec.usd_side * dol) - cost_1rt


def build_universe(symbols: Sequence[str] = AP.FX_ALL,
                   tz_names: Sequence[str] = ("FFT",),
                   regimes: Sequence[str] = ("all", "hivol", "me1", "me3"),
                   ) -> Tuple[Dict[str, pd.Series], int]:
    """Toàn bộ không gian luật -> {key: chuỗi lợi nhuận ròng theo ngày}.

    Trả kèm SỐ PHÉP THỬ để hiệu chỉnh đa kiểm định. Số này phải là kích thước không
    gian ĐÃ QUÉT, không phải số luật cuối cùng được giữ.
    """
    out: Dict[str, pd.Series] = {}
    for tzn in tz_names:
        tz = _TZ[tzn]
        for sym in symbols:
            panel = FL.hour_panel(sym, tz, start=str(DEV_START.date()))
            c1 = FL.cost_round_trip_bps(sym)
            # loại giờ thanh khoản mỏng TRƯỚC khi xét bất cứ kết quả nào
            counts = panel[[c for c in panel.columns if isinstance(c, (int, np.integer))]].notna().sum()
            keep = set(counts[counts >= MIN_COVERAGE * counts.max()].index)
            for h in sorted(keep):
                for side in (+1, -1):
                    for reg in regimes:
                        spec = RuleSpec(sym, tzn, int(h), side, reg)
                        s = rule_series(spec, panel, c1)
                        if len(s):
                            out[spec.key] = s
    return out, len(out)


# ═══════════════════════════════════════════════════ chỉ số
def ann_factor(s: pd.Series) -> float:
    span_years = (s.index.max() - s.index.min()).days / 365.25
    return len(s) / max(span_years, 1e-9)


def sharpe(s: pd.Series) -> float:
    sd = float(s.std(ddof=1))
    if sd <= 0 or len(s) < 5:
        return float("nan")
    return float(s.mean()) / sd * np.sqrt(ann_factor(s))


def deflated_sharpe(sr_obs: float, n_trials: int, n_obs: int,
                    skew: float = 0.0, kurt: float = 3.0) -> float:
    """DSR (Bailey & López de Prado 2014) — xác suất Sharpe thật > 0 sau khi trừ
    kỳ vọng Sharpe cao nhất đạt được bởi `n_trials` phép thử thuần ngẫu nhiên."""
    if not np.isfinite(sr_obs) or n_trials < 2 or n_obs < 10:
        return float("nan")
    eg = 0.5772156649
    e_max = (1 - eg) * stats.norm.ppf(1 - 1.0 / n_trials) + \
            eg * stats.norm.ppf(1 - 1.0 / (n_trials * np.e))
    denom = np.sqrt(max(1e-12, 1 - skew * sr_obs + (kurt - 1) / 4 * sr_obs ** 2))
    return float(stats.norm.cdf((sr_obs - e_max) * np.sqrt(n_obs - 1) / denom))


# ═══════════════════════════════════════════════════ chọn trên DEV
def select_on_dev(universe: Dict[str, pd.Series], *, top_n: int = 12,
                  min_t: float = 2.0) -> List[str]:
    """Chọn luật bằng t-stat trên DEV. Không dùng OOS ở bất kỳ bước nào.

    Thêm một ràng buộc ĐA DẠNG HOÁ, không phải tối ưu hoá: tối đa 2 luật mỗi cặp.
    Lý do: 12 luật tốt nhất theo t rất dễ là 12 biến thể của cùng một giờ trên cùng
    một cặp — đó là tăng tỷ trọng, không phải đa dạng hoá (đúng vấn đề mà
    `strategies_system/README.md` đã ghi nhận với MtfBreakoutM30/H1 trên vàng).
    """
    rows = []
    for k, s in universe.items():
        d = s[s.index < DEV_END]
        if len(d) < MIN_TRADES_DEV:
            continue
        sd = float(d.std(ddof=1))
        if sd <= 0:
            continue
        t = float(d.mean()) / (sd / np.sqrt(len(d)))
        rows.append((k, t, sharpe(d), len(d)))
    rows.sort(key=lambda r: -r[1])
    picked, per_sym = [], {}
    for k, t, sh, n in rows:
        if t < min_t:
            break
        sym = k.split("|")[0]
        if per_sym.get(sym, 0) >= 2:
            continue
        picked.append(k)
        per_sym[sym] = per_sym.get(sym, 0) + 1
        if len(picked) >= top_n:
            break
    return picked


def portfolio_series(universe: Dict[str, pd.Series], keys: Sequence[str], *,
                     vol_target_bps: Optional[float] = None,
                     vol_ref: Optional[Dict[str, float]] = None) -> pd.Series:
    """Danh mục CHIA ĐỀU trên các luật, chuẩn hoá rủi ro bằng biến động DEV.

    `vol_ref[k]` = std của luật k trên DEV. Chia cho nó để mỗi luật góp cùng một
    lượng rủi ro (inverse-vol, dùng CHỈ phương sai — không dùng lợi nhuận, theo
    Olszweski & Zhou). Nếu None thì chia đều thô.
    """
    parts = []
    for k in keys:
        s = universe[k]
        w = 1.0
        if vol_ref is not None and vol_ref.get(k):
            w = 1.0 / vol_ref[k]
        parts.append((s * w).rename(k))
    if not parts:
        return pd.Series(dtype=float)
    frame = pd.concat(parts, axis=1)
    # Mỗi ngày: trung bình các luật CÓ tín hiệu hôm đó (luật cuối tháng phần lớn NaN)
    port = frame.mean(axis=1, skipna=True).dropna()
    if vol_target_bps:
        sd = float(port.std(ddof=1))
        if sd > 0:
            port = port * (vol_target_bps / sd)
    return port.sort_index()


def dev_vol(universe: Dict[str, pd.Series], keys: Sequence[str]) -> Dict[str, float]:
    out = {}
    for k in keys:
        d = universe[k]
        d = d[d.index < DEV_END]
        out[k] = float(d.std(ddof=1)) if len(d) > 5 else None
    return out


# ═══════════════════════════════════════════════════ control ngẫu nhiên
def random_control(universe: Dict[str, pd.Series], n_rules: int, *,
                   n_draws: int = 400, seed: int = 11) -> Dict[str, float]:
    """Phân phối Sharpe OOS của danh mục gồm `n_rules` luật RÚT NGẪU NHIÊN.

    Đây là cổng 2. Nếu Sharpe OOS của danh mục đã chọn không nằm ở đuôi trên của
    phân phối này, thì quy trình chọn-theo-DEV không mang thông tin — bất kể các
    luật riêng lẻ có t-stat bao nhiêu trên DEV.
    """
    rng = np.random.default_rng(seed)
    keys = list(universe)
    out = []
    for _ in range(n_draws):
        pick = list(rng.choice(keys, size=min(n_rules, len(keys)), replace=False))
        vr = dev_vol(universe, pick)
        p = portfolio_series(universe, pick, vol_ref=vr)
        o = p[p.index >= DEV_END]
        if len(o) >= MIN_TRADES_OOS:
            out.append(sharpe(o))
    arr = np.array([x for x in out if np.isfinite(x)])
    if not len(arr):
        return {}
    return {"n": len(arr), "p05": float(np.percentile(arr, 5)),
            "p50": float(np.percentile(arr, 50)),
            "p95": float(np.percentile(arr, 95)),
            "mean": float(arr.mean()), "samples": arr}
