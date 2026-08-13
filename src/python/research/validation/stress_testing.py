"""stress_testing.py — 4/5 kỹ thuật "tra tấn" chiến lược (Câu hỏi 35,
Q&A-system.md): Noise Injection, Monte Carlo Permutation, Parameter
Stability (Parameter Cliff), Outlier Removal.

Triết học: đây là công cụ ĐO LƯỜNG/CẢNH BÁO (giống decay_monitor.py và
overfitting_stats.py — tự động hoá PHẦN PHÁT HIỆN, không tự động hoá PHẦN
QUYẾT ĐỊNH). Không tự động loại bỏ chiến lược nào; chỉ trả về số liệu +
verdict để user tự quyết định, đúng triết lý xuyên suốt dự án.

Kỹ thuật thứ 5 (Synthetic Data Generation) ở module riêng
`research/synthetic_data.py` (Level 1: GBM/Merton Jump/GARCH; Level 2: Block
Bootstrap) — Level 3 (TimeGAN/SDV) CHƯA triển khai, xem docstring đầu file đó."""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd


# ============================================================================
# 1) Noise Injection — biến giá OHLCV đi 1 chút + giãn spread ngẫu nhiên, xem
#    chiến lược có "gãy" (đổi từ lãi sang lỗ) chỉ vì sai lệch vĩ mô hay không.
# ============================================================================
def inject_noise(
    ohlcv: pd.DataFrame,
    price_noise_pct: float = 0.0002,
    spread_widen_prob: float = 0.01,
    spread_widen_mult: float = 3.0,
    seed: Optional[int] = None,
) -> pd.DataFrame:
    """Trả về BẢN SAO của `ohlcv` (cột open/high/low/close, tùy chọn
    spread_usd) đã bị:
      1. Nhiễu giá ngẫu nhiên +-price_noise_pct (tương đối, áp dụng ĐỒNG THỜI
         cho open/high/low/close của CÙNG 1 bar để không phá vỡ tính chất
         high>=open,close,low — noise thêm vào high/low được clip lại để
         đảm bảo OHLC vẫn hợp lệ).
      2. Với xác suất spread_widen_prob MỖI bar, spread_usd (nếu có) bị nhân
         lên spread_widen_mult lần (mô phỏng tin tức/thanh khoản mỏng đột ngột).

    Dùng: chạy lại `_signals()`/`add_core_features()` trên bản sao NHIỄU này,
    so sánh với kết quả trên dữ liệu gốc — nếu lãi/lỗ đổi dấu chỉ vì nhiễu
    nhỏ, chiến lược đang overfit vào 1 vi kịch bản cụ thể (không phải edge
    thật, xem Câu hỏi 35 mục 1)."""
    rng = np.random.default_rng(seed)
    out = ohlcv.copy()
    n = len(out)
    price_cols = [c for c in ("open", "high", "low", "close") if c in out.columns]
    if price_cols:
        noise = rng.normal(0.0, price_noise_pct, n)
        for col in price_cols:
            out[col] = out[col] * (1.0 + noise)
        # đảm bảo OHLC vẫn hợp lệ sau khi nhiễu độc lập từng cột: high/low
        # cuối cùng là max/min của CẢ 4 giá trị đã nhiễu (open/high/low/close),
        # tính đồng thời từ bản ghi TRƯỚC khi ghi đè để tránh phụ thuộc thứ tự.
        if {"high", "low", "open", "close"}.issubset(out.columns):
            all_four = np.stack([out["open"].to_numpy(), out["high"].to_numpy(),
                                 out["low"].to_numpy(), out["close"].to_numpy()], axis=1)
            out["high"] = all_four.max(axis=1)
            out["low"] = all_four.min(axis=1)

    if "spread_usd" in out.columns:
        widen_mask = rng.random(n) < spread_widen_prob
        out.loc[widen_mask, "spread_usd"] = out.loc[widen_mask, "spread_usd"] * spread_widen_mult

    return out


def noise_injection_stability(
    baseline_metric: float,
    noisy_metrics: Sequence[float],
    sign_flip_is_failure: bool = True,
) -> dict:
    """Tóm tắt kết quả chạy nhiều lần inject_noise() + tính lại metric (vd
    tổng netR, Sharpe...): tỷ lệ lần metric ĐỔI DẤU so với baseline (lãi
    thành lỗ hoặc ngược lại) — tỷ lệ này cao (vd >20%) là dấu hiệu overfit
    vào vi kịch bản, không phải edge thật."""
    arr = np.asarray(noisy_metrics, dtype=float)
    if sign_flip_is_failure:
        flips = np.sign(arr) != np.sign(baseline_metric)
    else:
        flips = np.zeros_like(arr, dtype=bool)
    return {
        "baseline_metric": float(baseline_metric),
        "n_runs": len(arr),
        "mean_noisy_metric": float(np.mean(arr)) if len(arr) else float("nan"),
        "std_noisy_metric": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
        "sign_flip_rate": float(np.mean(flips)) if len(arr) else float("nan"),
        "fragile": bool(len(arr) and np.mean(flips) > 0.2),
    }


# ============================================================================
# 2) Monte Carlo Permutation — xáo trộn THỨ TỰ các lệnh (không đổi bản thân
#    từng lệnh) để xem chuỗi thua liên tiếp XUI NHẤT có thể xảy ra là gì.
# ============================================================================
def monte_carlo_permutation(
    trade_returns: Sequence[float],
    n_paths: int = 1000,
    starting_equity: float = 1.0,
    risk_fraction: float = 1.0,
    seed: Optional[int] = None,
) -> dict:
    """Xáo trộn ngẫu nhiên THỨ TỰ của `trade_returns` (mỗi lệnh là 1 giá trị
    R-multiple hoặc % return, KHÔNG đổi giá trị từng lệnh — chỉ đổi thứ tự
    xuất hiện) `n_paths` lần, mô phỏng equity curve compound trên mỗi hoán
    vị, trả về phân phối maxDD/P(cháy tài khoản).

    Câu hỏi trả lời: "Nếu xui, chuỗi thua 20 lệnh liên tiếp xuất hiện NGAY
    ĐẦU (thay vì rải đều qua thời gian như lịch sử thật), tài khoản có
    cháy không?" — Monte Carlo Permutation cho THẤY chính xác phân phối các
    khả năng sắp xếp khác nhau của CÙNG một tập lệnh.

    starting_equity/risk_fraction: mô phỏng compound đơn giản (equity *=
    (1 + risk_fraction * r) mỗi lệnh) — dùng risk_fraction=1.0 nếu
    trade_returns đã là % thay đổi equity thực tế (không cần nhân thêm)."""
    r = np.asarray(trade_returns, dtype=float)
    if len(r) == 0:
        raise ValueError("trade_returns rỗng")
    rng = np.random.default_rng(seed)

    max_dds = np.empty(n_paths)
    final_equities = np.empty(n_paths)
    ruin_flags = np.zeros(n_paths, dtype=bool)

    for i in range(n_paths):
        perm = rng.permutation(r)
        equity = starting_equity
        peak = starting_equity
        max_dd = 0.0
        ruined = False
        for ret in perm:
            equity *= (1.0 + risk_fraction * ret)
            if equity <= 0:
                ruined = True
                equity = 0.0
                break
            peak = max(peak, equity)
            dd = 1.0 - equity / peak
            max_dd = max(max_dd, dd)
        max_dds[i] = max_dd if not ruined else 1.0
        final_equities[i] = equity
        ruin_flags[i] = ruined

    return {
        "n_paths": n_paths,
        "n_trades": len(r),
        "max_dd_p50": float(np.percentile(max_dds, 50)),
        "max_dd_p90": float(np.percentile(max_dds, 90)),
        "max_dd_p99": float(np.percentile(max_dds, 99)),
        "max_dd_worst": float(np.max(max_dds)),
        "prob_ruin": float(np.mean(ruin_flags)),
        "final_equity_p50": float(np.percentile(final_equities, 50)),
        "final_equity_p10": float(np.percentile(final_equities, 10)),
    }


# ============================================================================
# 3) Parameter Stability — phát hiện "Vách đá tham số" (Parameter Cliff) vs
#    "Bình nguyên tham số" (Parameter Plateau).
# ============================================================================
def parameter_stability_scan(
    param_values: Sequence[float],
    metric_values: Sequence[float],
    cliff_ratio_threshold: float = 0.5,
) -> pd.DataFrame:
    """Với 1 lưới tham số 1 chiều ĐÃ SẮP XẾP TĂNG DẦN (vd RSI period =
    12,13,14,15,16) và metric tương ứng (vd tổng netR/Sharpe cho từng giá
    trị), phát hiện bước nhảy (step) nào là "vách đá": |delta metric| giữa
    2 giá trị LIỀN KỀ vượt quá `cliff_ratio_threshold` x |metric trung bình|
    trên toàn lưới.

    Trả về DataFrame 1 dòng/giá trị tham số: param, metric, delta_to_prev,
    delta_to_next, is_cliff_neighbor (True nếu 1 trong 2 cạnh kề sát là vách
    đá). Chiến lược AN TOÀN phải có ít nhất 1 vùng liên tiếp KHÔNG có
    is_cliff_neighbor bao quanh giá trị đang dùng (bình nguyên), không phải
    đứng đúng 1 điểm đơn lẻ giữa 2 vách đá."""
    params = np.asarray(param_values, dtype=float)
    metrics = np.asarray(metric_values, dtype=float)
    if len(params) != len(metrics):
        raise ValueError("param_values và metric_values phải cùng độ dài")
    if len(params) < 2:
        raise ValueError("Cần ít nhất 2 giá trị tham số để đánh giá độ ổn định")
    if not np.all(np.diff(params) > 0):
        raise ValueError("param_values phải sắp xếp TĂNG DẦN, không trùng lặp")

    avg_abs_metric = float(np.mean(np.abs(metrics))) or 1e-9
    deltas = np.diff(metrics)
    threshold = cliff_ratio_threshold * avg_abs_metric

    delta_to_prev = np.concatenate([[np.nan], deltas])
    delta_to_next = np.concatenate([deltas, [np.nan]])
    is_cliff_prev = np.abs(delta_to_prev) > threshold
    is_cliff_next = np.abs(delta_to_next) > threshold
    is_cliff_neighbor = np.nan_to_num(is_cliff_prev, nan=False) | np.nan_to_num(is_cliff_next, nan=False)

    return pd.DataFrame({
        "param": params,
        "metric": metrics,
        "delta_to_prev": delta_to_prev,
        "delta_to_next": delta_to_next,
        "is_cliff_neighbor": is_cliff_neighbor,
    })


def find_stable_plateau(report: pd.DataFrame, min_plateau_width: int = 3) -> Optional[dict]:
    """Tìm DẢI LIÊN TIẾP dài nhất các dòng KHÔNG phải is_cliff_neighbor trong
    kết quả parameter_stability_scan(). Trả về None nếu không có dải nào đạt
    `min_plateau_width` — nghĩa là KHÔNG có bình nguyên đủ rộng, mọi vùng đều
    gần vách đá (chiến lược đang ở đỉnh nhọn, rủi ro Parameter Cliff cao)."""
    stable = (~report["is_cliff_neighbor"]).to_numpy()
    best_start, best_len = None, 0
    cur_start, cur_len = None, 0
    for i, ok in enumerate(stable):
        if ok:
            if cur_start is None:
                cur_start = i
            cur_len += 1
            if cur_len > best_len:
                best_len, best_start = cur_len, cur_start
        else:
            cur_start, cur_len = None, 0
    if best_start is None or best_len < min_plateau_width:
        return None
    window = report.iloc[best_start: best_start + best_len]
    return {
        "start_param": float(window["param"].iloc[0]),
        "end_param": float(window["param"].iloc[-1]),
        "width": best_len,
        "mean_metric": float(window["metric"].mean()),
    }


# ============================================================================
# 4) Outlier Removal — xoá N lệnh thắng lớn nhất, xem edge có còn không.
# ============================================================================
def outlier_removal_test(
    trade_returns: Sequence[float],
    n_remove: int = 5,
    compound: bool = False,
    starting_equity: float = 1.0,
) -> dict:
    """Xoá `n_remove` lệnh THẮNG LỚN NHẤT (không đồng với lệnh THUA lớn nhất
    — mục đích là kiểm tra edge có phụ thuộc vào vài "thiên nga trắng" hiếm
    hỏi không, không phải kiểm tra risk của tail-loss) khỏi `trade_returns`,
    tính lại tổng return (compound hoặc cộng đơn giản). Nếu từ dương chuyển
    sang âm sau khi xoá, chiến lược KHÔNG có edge thực sự phân bổ đều — chỉ
    ăn may trúng 1 vài sự kiện hiếm."""
    r = np.asarray(trade_returns, dtype=float)
    if n_remove >= len(r):
        raise ValueError(f"n_remove ({n_remove}) phải < tổng số lệnh ({len(r)})")

    order = np.argsort(r)  # tăng dần
    top_n_idx = order[-n_remove:]
    removed_returns = r[top_n_idx]
    kept = np.delete(r, top_n_idx)

    def _total(returns):
        if compound:
            eq = starting_equity
            for x in returns:
                eq *= (1.0 + x)
            return eq - starting_equity
        return float(np.sum(returns)) * starting_equity

    total_before = _total(r)
    total_after = _total(kept)

    return {
        "n_trades_total": len(r),
        "n_removed": n_remove,
        "removed_returns": removed_returns.tolist(),
        "total_return_before": float(total_before),
        "total_return_after": float(total_after),
        "sign_flipped_to_loss": bool(total_before > 0 and total_after <= 0),
        "pct_of_profit_from_outliers": (
            float(1.0 - total_after / total_before) if total_before > 0 else float("nan")
        ),
    }

