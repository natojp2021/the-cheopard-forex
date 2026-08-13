"""overfitting_stats.py — Deflated Sharpe Ratio (DSR) và Probability of Backtest
Overfitting (PBO) qua CSCV (Combinatorially Symmetric Cross-Validation).

Nguồn: Bailey & López de Prado (2014), "The Deflated Sharpe Ratio: Correcting
for Selection Bias, Backtest Overfitting and Non-Normality", Journal of
Portfolio Management; và Bailey, Borwein, López de Prado, Zhu (2017),
"The Probability of Backtest Overfitting", Journal of Computational Finance.

Triết học (Câu hỏi 34 — Q&A-system.md): hệ thống đã có Walk-Forward/Holdout
(spec 06) nhưng CHƯA có cơ chế phạt (penalize) theo SỐ LƯỢNG bài test đã thử.
Module này CHỈ là công cụ đo lường/cảnh báo (giống decay_monitor.py: tự động
hoá PHẦN ĐO LƯỜNG, không tự động hoá PHẦN QUYẾT ĐỊNH) — không tự động loại bỏ
strategy nào, chỉ trả về con số + khuyến nghị để user tự quyết.

Tích hợp: dùng trực tiếp trên các cột đã có sẵn trong scope_ledger.csv /
portfolio_v3_trades.parquet (netR) hoặc bất kỳ ma trận return nào (T x N).
KHÔNG phụ thuộc statsmodels/sklearn — chỉ numpy/pandas/scipy (đã có sẵn,
xem requirements.txt).
"""
from __future__ import annotations

import math
from itertools import combinations
from typing import Optional, Sequence, Union

import numpy as np
import pandas as pd
from scipy import stats

_EULER_MASCHERONI = 0.5772156649015329


def sharpe_ratio(returns: Union[pd.Series, np.ndarray], periods_per_year: float = 1.0) -> float:
    """Sharpe ratio đơn giản (không annualize nếu periods_per_year=1 — truyền
    252 cho daily returns, v.v. nếu cần annualize)."""
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 2 or np.std(r, ddof=1) == 0:
        return 0.0
    return float(np.mean(r) / np.std(r, ddof=1) * math.sqrt(periods_per_year))


def expected_max_sharpe_under_null(n_trials: int, sr_variance: float) -> float:
    """SR0* — Sharpe kỳ vọng CAO NHẤT trong số N thử nghiệm ĐỘC LẬP dưới giả
    thuyết null (không có edge thật, chỉ là may mắn chọn lọc). Công thức
    (Bailey & López de Prado 2014, eq. 8), dùng xấp xỉ Gumbel cho max của N
    biến ngẫu nhiên chuẩn:

        SR0* = sqrt(V) * [ (1-gamma)*Z^-1(1 - 1/N) + gamma*Z^-1(1 - 1/(N*e)) ]

    V = phương sai của các ước lượng Sharpe qua N thử nghiệm (sr_variance).
    gamma = hằng số Euler-Mascheroni (~0.5772). N=1 -> trả về 0 (không có
    selection bias khi chỉ thử 1 lần)."""
    n = int(n_trials)
    if n <= 1:
        return 0.0
    v = max(0.0, float(sr_variance))
    if v == 0.0:
        return 0.0
    z1 = stats.norm.ppf(1.0 - 1.0 / n)
    z2 = stats.norm.ppf(1.0 - 1.0 / (n * math.e))
    return math.sqrt(v) * ((1.0 - _EULER_MASCHERONI) * z1 + _EULER_MASCHERONI * z2)


def deflated_sharpe_ratio(
    sr_observed: float,
    n_trials: int,
    n_obs: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
    sr_trials: Optional[Sequence[float]] = None,
    sr_variance: Optional[float] = None,
) -> dict:
    """DSR — xác suất Sharpe quan sát được (sr_observed) THỰC SỰ vượt trội hơn
    0, SAU KHI đã trừ hao selection bias từ việc thử N bộ tham số/chiến lược
    và tính phi-chuẩn (skew/kurtosis) của return.

    Tham số:
      sr_observed: Sharpe ratio của chiến lược/tham số ĐƯỢC CHỌN (chưa annualize
        theo năm nếu không cần — giữ cùng đơn vị với n_obs).
      n_trials: SỐ LƯỢNG bộ tham số/chiến lược ĐÃ THỬ (N) trước khi chọn ra
        sr_observed. Đây là nguồn của "selection bias" — càng lớn càng phải
        deflate mạnh.
      n_obs: số quan sát (T) dùng để ước lượng sr_observed (vd số lệnh, hoặc
        số kỳ quan sát return).
      skew, kurtosis: độ lệch/độ nhọn của PHÂN PHỐI RETURN (không phải của
        Sharpe) — mặc định 0/3 (phân phối chuẩn, không deflate thêm vì phi-chuẩn).
      sr_trials: (tùy chọn) mảng Sharpe ratio của TOÀN BỘ N thử nghiệm — nếu có,
        sr_variance tự động tính từ đây (ưu tiên hơn sr_variance truyền thẳng).
      sr_variance: (tùy chọn) phương sai Sharpe qua N thử nghiệm, nếu không có
        dữ liệu từng thử nghiệm riêng lẻ (sr_trials).

    Trả về dict: {dsr, sr0_star, psr_denominator, z_score, n_trials, n_obs}.
    DSR ở dạng xác suất (0..1) — Bailey & López de Prado khuyến nghị dsr>=0.95
    trước khi tin một chiến lược là có edge thật."""
    sr = float(sr_observed)
    t = int(n_obs)
    if t < 2:
        raise ValueError("n_obs (T) phải >= 2 để ước lượng phương sai Sharpe")

    if sr_trials is not None and len(sr_trials) > 1:
        v = float(np.var(np.asarray(sr_trials, dtype=float), ddof=1))
    elif sr_variance is not None:
        v = float(sr_variance)
    else:
        raise ValueError("Cần truyền sr_trials (mảng Sharpe của N thử nghiệm) "
                          "hoặc sr_variance (phương sai đã biết trước)")

    sr0_star = expected_max_sharpe_under_null(n_trials, v)

    denom = math.sqrt(max(1e-12, 1.0 - skew * sr + (kurtosis - 1.0) / 4.0 * sr * sr))
    z = (sr - sr0_star) * math.sqrt(t - 1) / denom
    dsr = float(stats.norm.cdf(z))

    return {
        "dsr": dsr,
        "sr0_star": sr0_star,
        "psr_denominator": denom,
        "z_score": z,
        "n_trials": int(n_trials),
        "n_obs": t,
        "sr_variance_used": v,
    }


def probability_of_backtest_overfitting(
    returns_matrix: Union[pd.DataFrame, np.ndarray],
    n_splits: int = 16,
    metric_fn=None,
) -> dict:
    """PBO qua CSCV (Combinatorially Symmetric Cross-Validation) — Bailey,
    Borwein, López de Prado, Zhu (2017).

    returns_matrix: T x N (T kỳ quan sát, N chiến lược/bộ tham số ĐÃ THỬ —
      mỗi cột là 1 đường return). pd.DataFrame hoặc np.ndarray đều được.
    n_splits (S): số khối (block) chia đều T thành — PHẢI CHẴN (S/2 khối làm
      IS, S/2 còn lại làm OOS mỗi tổ hợp). Số tổ hợp = C(S, S/2) — vd S=16 ->
      12,870 tổ hợp; dùng S nhỏ hơn (vd 6-8) nếu T không đủ dài.
    metric_fn: hàm nhận 1D array return -> số thực (mặc định: Sharpe ratio
      đơn giản qua sharpe_ratio()). Bất kỳ metric "càng cao càng tốt" nào
      cũng dùng được (Sharpe, mean R, Calmar...).

    Thuật toán (mỗi tổ hợp c trong C(S, S/2)):
      1. IS = nơi S/2 khối được chọn; OOS = nơi S/2 khối còn lại.
      2. Tính metric trên IS cho từng cột -> chọn n* = cột tốt nhất IS.
      3. Tính metric trên OOS cho từng cột -> xếp hạng n* trong số N (rank
         càng cao = càng tốt). omega = rank/(N+1); logit lambda = ln(omega/(1-omega)).
      4. lambda <= 0 (n* chỉ đạt trung bình-hoặc-kém trên OOS) => 1 "phiếu"
         overfit.
    PBO = tỷ lệ tổ hợp có lambda <= 0.

    Trả về dict: {pbo, logits (list), n_combinations, n_splits, n_strategies}."""
    if isinstance(returns_matrix, pd.DataFrame):
        arr = returns_matrix.to_numpy(dtype=float)
        cols = list(returns_matrix.columns)
    else:
        arr = np.asarray(returns_matrix, dtype=float)
        cols = list(range(arr.shape[1]))

    t, n = arr.shape
    if n_splits % 2 != 0:
        raise ValueError("n_splits (S) phải là số chẵn (chia đôi làm IS/OOS)")
    if n_splits < 2 or n_splits > t:
        raise ValueError(f"n_splits (S={n_splits}) phải trong [2, T={t}]")
    if metric_fn is None:
        metric_fn = sharpe_ratio

    block_edges = np.array_split(np.arange(t), n_splits)
    half = n_splits // 2
    logits = []

    for is_blocks in combinations(range(n_splits), half):
        is_idx = np.concatenate([block_edges[b] for b in is_blocks])
        oos_blocks = [b for b in range(n_splits) if b not in is_blocks]
        oos_idx = np.concatenate([block_edges[b] for b in oos_blocks])

        is_perf = np.array([metric_fn(arr[is_idx, j]) for j in range(n)])
        oos_perf = np.array([metric_fn(arr[oos_idx, j]) for j in range(n)])

        n_star = int(np.argmax(is_perf))
        # rank của n_star trong OOS (1 = kém nhất, N = tốt nhất), xử lý hòa điểm
        # bằng trung bình thứ hạng (giống scipy.stats.rankdata "average").
        ranks = stats.rankdata(oos_perf, method="average")
        rank_n_star = ranks[n_star]
        omega = rank_n_star / (n + 1.0)
        omega = min(max(omega, 1e-9), 1.0 - 1e-9)  # tránh log(0)/chia 0 ở biên
        logit = math.log(omega / (1.0 - omega))
        logits.append(logit)

    logits_arr = np.array(logits)
    pbo = float(np.mean(logits_arr <= 0.0))

    return {
        "pbo": pbo,
        "logits": logits_arr.tolist(),
        "n_combinations": len(logits),
        "n_splits": n_splits,
        "n_strategies": n,
        "strategy_names": cols,
    }

