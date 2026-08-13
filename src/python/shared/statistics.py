"""Hàm thống kê thuần dùng chung cho Live và Research."""
from __future__ import annotations

import numpy as np


def bootstrap_lcb_mean(r: np.ndarray, n_boot: int = 10000, ci: float = 0.95,
                        seed: int = 7) -> dict:
    """LCB cua MEAN-R (khong phai final equity) — dung cho G2.

    `seed` co dinh (7) la CO Y: gate nghien cuu phai tai lap duoc bit-for-bit
    giua cac lan chay, khong duoc phu thuoc trang thai RNG toan cuc.
    """
    if len(r) == 0:
        return {"mean": float("nan"), "lcb": float("nan"), "n": 0}
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    for i in range(n_boot):
        means[i] = rng.choice(r, size=len(r), replace=True).mean()
    alpha = (1.0 - ci) * 100.0
    return {
        "mean": float(r.mean()),
        "lcb": float(np.percentile(means, alpha)),
        "n": int(len(r)),
    }
