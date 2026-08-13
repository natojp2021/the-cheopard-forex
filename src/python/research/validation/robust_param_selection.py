"""
robust_param_selection.py — Chọn tham số theo "vùng cao nguyên" (plateau) thay vì
đỉnh đơn lẻ của Optuna, áp dụng cho tiến trình tối ưu tham số của 7 chiến lược v3.

Bối cảnh (đề xuất 19/07, tham khảo best-practice từ review project-refer):
`study.best_trial` của Optuna lấy đúng 1 điểm điểm-số-cao-nhất — dễ là "lucky
peak": một toạ độ tham số ăn may trên tập fold cụ thể, xung quanh toàn tham số
tệ. Khi chạy live, thị trường lệch nhẹ khỏi điều kiện lúc backtest là tham số
rơi khỏi đỉnh và thất bại.

KHÔNG dùng KMeans thô trên các trial thô: với search TPE-adaptive (khác grid
đều), mật độ điểm phản ánh nơi sampler chọn khám phá nhiều hơn là nơi tham số
thực sự ổn định — dễ làm KMeans nhầm "TPE tò mò nhiều" thành "vùng ổn định".
Với ít trial (vd 30), KMeans còn dễ tạo cụm rỗng/nhiễu.

Thay vào đó: làm mượt (kernel-smooth) điểm số theo khoảng cách trong không gian
tham số đã chuẩn hoá [0,1] — chọn điểm có TRUNG BÌNH LÂN CẬN cao nhất, không
phải điểm đơn lẻ cao nhất. Đơn giản, không cần chọn số cụm, suy biến êm khi ít
trial (báo cáo diagnostics rõ ràng thay vì giả vờ tự tin).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence


@dataclass(frozen=True)
class TrialResult:
    """Một trial độc lập với Optuna — dễ test, dễ tái dùng."""
    params: dict
    value: float


@dataclass
class RobustSelection:
    trial: TrialResult
    smoothed_score: float
    raw_best_value: float
    raw_best_params: dict
    n_neighbors: int
    neighbor_score_std: float
    is_same_as_raw_best: bool
    warnings: list = field(default_factory=list)


def _normalize_params(trials: Sequence[TrialResult], param_names: Sequence[str],
                       bounds: Optional[dict] = None) -> list[list[float]]:
    """Chuẩn hoá mỗi tham số về [0,1] theo min/max quan sát được (hoặc bounds
    truyền vào — ưu tiên bounds vì phản ánh đúng search space, không phải chỉ
    phạm vi các trial đã chạy)."""
    lo_hi = {}
    for name in param_names:
        vals = [t.params[name] for t in trials]
        if bounds and name in bounds:
            lo, hi = bounds[name]
        else:
            lo, hi = min(vals), max(vals)
        lo_hi[name] = (lo, hi if hi > lo else lo + 1e-9)

    normed = []
    for t in trials:
        row = []
        for name in param_names:
            lo, hi = lo_hi[name]
            row.append((t.params[name] - lo) / (hi - lo))
        normed.append(row)
    return normed


def _euclid(a: Sequence[float], b: Sequence[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def robust_select(trials: Sequence[TrialResult], param_names: Sequence[str],
                   bounds: Optional[dict] = None, k: int = 5,
                   min_trials_for_smoothing: int = 8) -> RobustSelection:
    """Chọn trial có TRUNG BÌNH điểm số của k-lân-cận-gần-nhất (trong không gian
    tham số đã chuẩn hoá) cao nhất — thay cho argmax điểm số đơn lẻ.

    `bounds`: dict tên_tham_số -> (lo, hi) của search space (khuyến khích truyền
    vào; nếu không có sẽ dùng min/max của chính các trial, kém chính xác hơn).
    `k`: số lân cận (kể cả chính nó) dùng để làm mượt điểm số.
    `min_trials_for_smoothing`: nếu số trial ít hơn ngưỡng này, làm mượt không
    đáng tin (thống kê quá thưa) — trả lại đúng argmax kèm cảnh báo rõ ràng
    thay vì giả vờ đã có "vùng ổn định".
    """
    if not trials:
        raise ValueError("robust_select: cần ít nhất 1 trial")

    warnings: list[str] = []
    raw_best = max(trials, key=lambda t: t.value)

    if len(trials) < min_trials_for_smoothing:
        warnings.append(
            f"Chỉ {len(trials)} trial (< {min_trials_for_smoothing}) — không đủ "
            f"để đánh giá độ ổn định lân cận; trả về argmax thô, XEM NHƯ THĂM DÒ, "
            f"KHÔNG đưa thẳng vào production (tăng n_trials trước khi tin tưởng)."
        )
        return RobustSelection(
            trial=raw_best, smoothed_score=raw_best.value,
            raw_best_value=raw_best.value, raw_best_params=raw_best.params,
            n_neighbors=1, neighbor_score_std=0.0,
            is_same_as_raw_best=True, warnings=warnings,
        )

    k_eff = min(k, len(trials))
    normed = _normalize_params(trials, param_names, bounds)

    best_idx = None
    best_smoothed = -math.inf
    best_neighbor_std = 0.0
    best_n = 0

    for i in range(len(trials)):
        dists = sorted(
            (( _euclid(normed[i], normed[j]), j) for j in range(len(trials))),
            key=lambda x: x[0],
        )[:k_eff]
        neigh_vals = [trials[j].value for _, j in dists]
        smoothed = sum(neigh_vals) / len(neigh_vals)
        if smoothed > best_smoothed:
            best_smoothed = smoothed
            best_idx = i
            best_neighbor_std = _std(neigh_vals)
            best_n = len(neigh_vals)

    chosen = trials[best_idx]
    is_same = chosen is raw_best or chosen.params == raw_best.params

    if best_neighbor_std > 0 and abs(chosen.value) > 1e-12:
        rel_spread = best_neighbor_std / max(abs(chosen.value), 1e-9)
        if rel_spread > 0.5:
            warnings.append(
                f"Độ lệch chuẩn điểm số trong vùng lân cận đã chọn khá lớn "
                f"(std={best_neighbor_std:.4g}, ~{rel_spread:.0%} so với điểm) — "
                f"'vùng ổn định' này chưa thực sự đồng nhất, cân nhắc tăng trials."
            )

    return RobustSelection(
        trial=chosen, smoothed_score=best_smoothed,
        raw_best_value=raw_best.value, raw_best_params=raw_best.params,
        n_neighbors=best_n, neighbor_score_std=best_neighbor_std,
        is_same_as_raw_best=is_same, warnings=warnings,
    )


def _std(vals: Sequence[float]) -> float:
    n = len(vals)
    if n < 2:
        return 0.0
    m = sum(vals) / n
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (n - 1))


def select_from_optuna_study(study, param_names: Optional[Sequence[str]] = None,
                              k: int = 5) -> RobustSelection:
    """Wrapper mỏng cho optuna.Study thật (completed trials only)."""
    completed = [t for t in study.trials if t.value is not None]
    trials = [TrialResult(params=dict(t.params), value=float(t.value)) for t in completed]
    names = list(param_names) if param_names else (list(trials[0].params.keys()) if trials else [])
    bounds = None
    if hasattr(study, "sampler") and hasattr(study, "get_trials"):
        # Optuna không expose bounds trực tiếp từ study; caller nên truyền
        # `bounds` qua robust_select() nếu cần chính xác tuyệt đối. Ở đây dùng
        # None để robust_select tự suy ra min/max từ các trial đã chạy.
        pass
    return robust_select(trials, names, bounds=bounds, k=k)
