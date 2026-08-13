"""robustness_diagnostics.py — ba phép chẩn đoán tính bền của hệ thống giao dịch.

REFERENCES
==========
Primary Reference
-----------------
Kirkpatrick, C.D. & Dahlquist, J.R. (2011). *Technical Analysis: The Complete
Resource for Financial Market Technicians*, 2nd ed. FT Press. Ch. 22 "System
Design and Testing", tr. 546-560. Ba phép chẩn đoán cài ở đây lấy nguyên từ
chương này:

  * tr. 547 — chia mẫu tối ưu thành **phần mười** và kiểm tính nhất quán trên
    từng khúc. Dẫn Ruggiero (2005): *"The actual amount of net profit is less
    important for each stage than are the determinants of risk and the
    consistency of results. If the results are not consistent, the system has a
    major problem and should be optimized using other means or discarded."*
  * tr. 549 — so sánh trong-mẫu với ngoài-mẫu phải xét **cấu trúc**, không chỉ
    hiệu suất: *"the comparisons between in-sample and out-of-sample results
    should differ in performance but should not materially differ in average
    duration of trades, maximum consecutive winners and losers, the worst losing
    trade, and the average losing trade."*
  * tr. 549 — kiểm **tính giòn**: *"we should test for brittleness, the
    phenomenon when one or more of the rules are never triggered."*

Supporting References
---------------------
* López de Prado, M. (2018). *AFML*. Ch. 11 tr. 155 — một đường kiểm thử duy
  nhất lặp lại được cho tới khi ra dương tính giả; cần nhiều đường. Phép kiểm
  phần mười cho mười điểm quan sát thay vì hai.
* Aronson, D. (2007). *EBTA*. Ch. 6 tr. 262-264 — hiệu suất ngoài mẫu GIẢM là
  điều bình thường và dự đoán được; vì vậy phép so cấu trúc mới có giá trị chẩn
  đoán, còn phép so hiệu suất thì không.
* Wright, K. (2013). *Building Reliable Trading Systems*. Ch. 2 tr. 13-19 — sai
  số chuẩn theo cỡ mẫu; dùng cho ngưỡng cảnh báo số lệnh.

Confirmed by: Kirkpatrick & Dahlquist (2011) ch.22; tinh thần nhất quán với
López de Prado (2018) ch.11 và Aronson (2007) ch.6.

VÌ SAO MODULE NÀY TỒN TẠI
==========================
Ngày 03/08, `SqueezeBreakdown` ra **0 lệnh bốn lần liên tiếp** vì bốn lỗi kỹ
thuật khác nhau, và **không một test nào trong 3.700 test của dự án bắt được**.
Driver fail-mềm nuốt exception, backtest chạy xong, ra con số 0, và không ai
biết đó là lỗi chứ không phải kết quả.

Kirkpatrick & Dahlquist gọi đúng tên hiện tượng ấy là *brittleness* và xếp nó
vào danh sách kiểm bắt buộc. Nếu phép kiểm này có sẵn từ đầu, cả bốn lần đều bị
chặn ngay.

Hai phép còn lại bổ sung cho dev/holdout hiện tại — vốn chỉ cho **hai** điểm
quan sát và chỉ so hiệu suất.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd


# ----------------------------------------------------------------- tính giòn

@dataclass
class BrittlenessReport:
    """Kết quả kiểm tính giòn cho một chiến lược."""

    n_trades: int
    rules_never_fired: List[str] = field(default_factory=list)
    rules_always_fired: List[str] = field(default_factory=list)
    rule_fire_rate: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_brittle(self) -> bool:
        return bool(self.rules_never_fired) or self.n_trades == 0

    def summary(self) -> str:
        if self.n_trades == 0:
            return ("GIÒN: chiến lược sinh 0 LỆNH. Đây gần như luôn là lỗi kỹ "
                    "thuật, không phải kết quả nghiên cứu — kiểm `rejects` của "
                    "driver trước khi đọc bất kỳ con số nào.")
        rows = [f"{self.n_trades} lệnh"]
        if self.rules_never_fired:
            rows.append(f"GIÒN — luật KHÔNG BAO GIỜ kích hoạt: "
                        f"{', '.join(self.rules_never_fired)}")
        if self.rules_always_fired:
            rows.append(f"luật LUÔN đúng (có thể là hằng số thừa): "
                        f"{', '.join(self.rules_always_fired)}")
        rows.extend(self.warnings)
        return "\n  ".join(rows)


def check_brittleness(
    rule_outcomes: Dict[str, Sequence[bool]],
    n_trades: int,
    min_fire_rate: float = 0.0,
) -> BrittlenessReport:
    """Phát hiện luật không bao giờ kích hoạt, hoặc luôn đúng.

    Args:
        rule_outcomes: {tên luật: chuỗi bool, mỗi phần tử là một lần đánh giá}.
            Ví dụ `{"squeeze": [...], "breakout": [...]}` cho từng nến.
        n_trades: số lệnh chiến lược thực sự mở. Truyền 0 nếu backtest ra 0 lệnh.
        min_fire_rate: tỉ lệ kích hoạt tối thiểu; dưới ngưỡng thì cảnh báo.
            Mặc định 0,0 nghĩa là chỉ cảnh báo khi TUYỆT ĐỐI không bao giờ đúng.

    Trả về `BrittlenessReport`. Kiểm `.is_brittle` trước khi tin bất kỳ con số
    hiệu suất nào — Kirkpatrick & Dahlquist tr.549 xếp đây vào bước kiểm bắt
    buộc trước khi xem thống kê hiệu suất.
    """
    rep = BrittlenessReport(n_trades=int(n_trades))
    for name, outcomes in rule_outcomes.items():
        arr = np.asarray(outcomes, dtype=bool)
        if arr.size == 0:
            rep.rules_never_fired.append(f"{name} (không có lần đánh giá nào)")
            continue
        ratio = float(arr.mean())
        rep.rule_fire_rate[name] = ratio
        if ratio <= 0.0:
            rep.rules_never_fired.append(name)
        elif ratio >= 1.0:
            rep.rules_always_fired.append(name)
        elif ratio < min_fire_rate:
            rep.warnings.append(
                f"luật '{name}' chỉ đúng {ratio:.2%} — dưới ngưỡng {min_fire_rate:.2%}")

    if n_trades == 0 and not rep.rules_never_fired:
        # Mọi luật đều có lúc đúng nhưng vẫn 0 lệnh → chúng không bao giờ đúng
        # ĐỒNG THỜI, hoặc có lỗi ở tầng khớp lệnh. Cả hai đều đáng báo động.
        rep.warnings.append(
            "0 lệnh dù mọi luật đều có lúc đúng — hoặc các điều kiện không bao "
            "giờ đúng CÙNG LÚC, hoặc tầng khớp lệnh đang nuốt lỗi.")
    return rep


# --------------------------------------------- nhất quán theo phần mười

@dataclass
class ConsistencySegment:
    idx: int
    start: pd.Timestamp
    end: pd.Timestamp
    n_trades: int
    total_r: float
    mean_r: float
    max_drawdown_r: float
    max_consecutive_losses: int


@dataclass
class ConsistencyReport:
    segments: List[ConsistencySegment]
    n_segments_positive: int
    n_segments: int
    trade_count_cv: float          # hệ số biến thiên của số lệnh giữa các khúc
    empty_segments: List[int]

    @property
    def is_consistent(self) -> bool:
        """Nhất quán theo tiêu chí của K&D tr.547.

        Ba điều kiện, tất cả về RỦI RO và ĐỘ ỔN ĐỊNH chứ không về lợi nhuận —
        đúng như Ruggiero (2005) dẫn trong K&D: *"the actual amount of net
        profit is less important than the determinants of risk and the
        consistency of results."*
        """
        return (not self.empty_segments
                and self.n_segments_positive >= self.n_segments * 0.6
                and self.trade_count_cv < 0.8)

    def summary(self) -> str:
        rows = [f"{self.n_segments} khúc · {self.n_segments_positive} khúc dương "
                f"· hệ số biến thiên số lệnh {self.trade_count_cv:.2f}"]
        if self.empty_segments:
            rows.append(f"KHÚC RỖNG (0 lệnh): {self.empty_segments} — hệ thống "
                        f"ngừng giao dịch hẳn ở những giai đoạn này")
        rows.append("NHẤT QUÁN" if self.is_consistent else "KHÔNG nhất quán")
        return "\n  ".join(rows)


def _max_drawdown_r(r: np.ndarray) -> float:
    if r.size == 0:
        return 0.0
    eq = np.cumsum(r)
    return float((eq - np.maximum.accumulate(eq)).min())


def _max_consecutive_losses(r: np.ndarray) -> int:
    best = cur = 0
    for x in r:
        if x <= 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return int(best)


def tenths_consistency(
    entry_times: Sequence[pd.Timestamp],
    r_multiples: Sequence[float],
    n_segments: int = 10,
) -> ConsistencyReport:
    """Chia trục THỜI GIAN thành `n_segments` khúc bằng nhau và đo từng khúc.

    Kirkpatrick & Dahlquist tr.547 chia theo *thời gian*, không theo số lệnh —
    điều đó quan trọng: chia theo số lệnh sẽ che mất đúng thứ cần thấy, là
    những giai đoạn hệ thống **ngừng giao dịch hẳn**.

    Args:
        entry_times: mốc vào lệnh, cùng độ dài với `r_multiples`.
        r_multiples: bội số R của từng lệnh.
        n_segments: số khúc; K&D dùng 10.
    """
    ts = pd.to_datetime(pd.Series(list(entry_times)), utc=True, errors="coerce")
    r = np.asarray(r_multiples, dtype=np.float64)
    if len(ts) != len(r):
        raise ValueError(f"entry_times ({len(ts)}) và r_multiples ({len(r)}) "
                         f"phải cùng độ dài.")
    if len(r) == 0:
        raise ValueError("không có lệnh nào để chia khúc.")
    if not np.isfinite(r).all():
        raise ValueError("r_multiples chứa NaN/inf.")

    t0, t1 = ts.min(), ts.max()
    variants = pd.date_range(t0, t1, periods=n_segments + 1)
    segs: List[ConsistencySegment] = []
    empty: List[int] = []
    for i in range(n_segments):
        lo, hi = variants[i], variants[i + 1]
        mask = (ts >= lo) & (ts < hi) if i < n_segments - 1 else (ts >= lo) & (ts <= hi)
        rr = r[mask.to_numpy()]
        if rr.size == 0:
            empty.append(i + 1)
        segs.append(ConsistencySegment(
            idx=i + 1, start=lo, end=hi, n_trades=int(rr.size),
            total_r=float(rr.sum()), mean_r=float(rr.mean()) if rr.size else 0.0,
            max_drawdown_r=_max_drawdown_r(rr),
            max_consecutive_losses=_max_consecutive_losses(rr)))

    counts = np.array([s.n_trades for s in segs], dtype=np.float64)
    cv = float(counts.std() / counts.mean()) if counts.mean() > 0 else float("inf")
    return ConsistencyReport(
        segments=segs,
        n_segments_positive=sum(1 for s in segs if s.total_r > 0),
        n_segments=n_segments, trade_count_cv=cv, empty_segments=empty)


# ------------------------------- so sánh CẤU TRÚC trong mẫu / ngoài mẫu

@dataclass
class StructuralComparison:
    metrics_is: Dict[str, float]
    metrics_oos: Dict[str, float]
    relative_change: Dict[str, float]
    structural_breaks: List[str]

    @property
    def structure_held(self) -> bool:
        return not self.structural_breaks

    def summary(self) -> str:
        rows = []
        for k in self.metrics_is:
            rows.append(f"{k:26s} trong mẫu {self.metrics_is[k]:+9.3f} · "
                        f"ngoài mẫu {self.metrics_oos[k]:+9.3f} · "
                        f"đổi {self.relative_change[k]:+7.1%}")
        if self.structural_breaks:
            rows.append("GÃY CẤU TRÚC: " + ", ".join(self.structural_breaks))
        else:
            rows.append("cấu trúc GIỮ NGUYÊN — chênh lệch chỉ ở hiệu suất")
        return "\n  ".join(rows)


def compare_structure(
    r_is: Sequence[float],
    r_oos: Sequence[float],
    hold_bars_is: Optional[Sequence[float]] = None,
    hold_bars_oos: Optional[Sequence[float]] = None,
    tolerance: float = 0.50,
) -> StructuralComparison:
    """So CẤU TRÚC tập lệnh giữa trong mẫu và ngoài mẫu.

    Kirkpatrick & Dahlquist tr.549: hai giai đoạn **được phép** khác nhau về
    hiệu suất, nhưng **không được** khác nhau đáng kể về thời gian giữ trung
    bình, chuỗi thắng/thua dài nhất, lệnh thua tệ nhất, và lệnh thua trung bình.

    Vì sao phép so này có giá trị chẩn đoán còn phép so hiệu suất thì không:
    Aronson ch.6 tr.262-264 chỉ ra hiệu suất ngoài mẫu GIẢM là điều bình thường
    và dự đoán được — nó không phân biệt được chiến lược tốt với chiến lược tồi.
    Cấu trúc thì khác: nếu chiến lược vẫn làm CÙNG một việc, cấu trúc phải giữ.

    Args:
        tolerance: ngưỡng thay đổi tương đối coi là gãy cấu trúc. Mặc định 0,50
            (tức đổi quá 50%). K&D nói "materially differ" mà không cho con số,
            nên ngưỡng này là **lựa chọn của ta**, ghi rõ để ai cũng chỉnh được.
    """
    a = np.asarray(r_is, dtype=np.float64)
    b = np.asarray(r_oos, dtype=np.float64)
    if a.size < 5 or b.size < 5:
        raise ValueError("cần ít nhất 5 lệnh mỗi bên để so cấu trúc.")

    def _metric_set(r: np.ndarray, hold: Optional[Sequence[float]]) -> Dict[str, float]:
        surplus = r[r <= 0]
        d = {
            "lệnh thua tệ nhất": float(r.min()),
            "lệnh thua trung bình": float(surplus.mean()) if surplus.size else 0.0,
            "chuỗi thua dài nhất": float(_max_consecutive_losses(r)),
            "chuỗi thắng dài nhất": float(_max_consecutive_losses(-r)),
            "độ lệch chuẩn R": float(r.std(ddof=1)),
        }
        if hold is not None:
            d["thời gian giữ TB"] = float(np.mean(np.asarray(hold, dtype=np.float64)))
        return d

    m_is = _metric_set(a, hold_bars_is)
    m_oos = _metric_set(b, hold_bars_oos)
    changed, gay = {}, []
    for k in m_is:
        base = abs(m_is[k])
        changed[k] = (m_oos[k] - m_is[k]) / base if base > 1e-12 else 0.0
        if abs(changed[k]) > tolerance:
            gay.append(f"{k} ({changed[k]:+.0%})")
    return StructuralComparison(metrics_is=m_is, metrics_oos=m_oos,
                                relative_change=changed, structural_breaks=gay)
