"""rule_trace.py — BẢN GHI QUY TẮC VÀO LỆNH, chuẩn chung cho MỌI chiến lược.

VÌ SAO MODULE NÀY PHẢI TỒN TẠI
===============================
`decision_log.py` lo việc GHI. Module này lo việc **quyết định cần ghi những gì**.

Một chiến lược có thể bỏ một setup ở nhiều bước khác nhau. Không ghi lại BƯỚC nào
đã chặn thì khi live lệch khỏi backtest chỉ thấy "ít lệnh hơn dự kiến" và không lần
ra được vì sao. Bản ghi runtime tồn tại để trả lời đúng câu đó, và nó chỉ ghi một dòng
tổng hợp kiểu "đã tái cân bằng, đây là tỷ trọng". Dòng đó KHÔNG trả lời được câu
hỏi vận hành quan trọng nhất:

    "Vì sao AUDUSD được mua 0,33 mà GBPUSD chỉ 0,03, đúng hôm nay?"

Với chiến lược XẾP HẠNG, câu trả lời gồm bốn phần và thiếu một phần là không tái
lập được: **giá trị tín hiệu · thứ hạng · ngưỡng cắt · tỷ trọng suy ra**. Biết tỷ
trọng mà không biết thứ hạng thì không phân biệt được "AUD thật sự mạnh nhất" với
"AUD được chọn vì USDJPY thiếu dữ liệu hôm đó".

NGUYÊN TẮC: BẢN GHI PHẢI TÁI LẬP ĐƯỢC QUYẾT ĐỊNH
=================================================
Một bản ghi hợp lệ phải cho phép người đọc, chỉ với bản ghi đó, nói được:
  1. tín hiệu là bao nhiêu, và nó đứng thứ mấy trong rổ
  2. ngưỡng nào đã cắt, và công cụ này nằm bên nào của ngưỡng
  3. tỷ trọng cuối cùng, và nó suy ra từ tín hiệu bằng phép gì
  4. có cổng nào đang chặn không, và cổng nào
  5. chi phí dự kiến, để đối chiếu với chi phí thật sau khi khớp

Ba khả năng mà chỉ bản ghi đầy đủ mới phân biệt được khi một lệnh thua bất thường:
    (a) tín hiệu đúng luật, thị trường đi ngược  -> bình thường
    (b) tham số đã TRÔI khỏi giá trị đã kiểm chứng
    (c) dữ liệu vào SAI (nến thiếu, sai múi giờ, giá lệch)
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd


@dataclass
class RuleTrace:
    """Bản ghi quy tắc vào lệnh — chuẩn chung cho mọi chiến lược.

    Trường `signal_*` mô tả TÍN HIỆU; `gate_*` mô tả các CỔNG chặn; `target_*` mô tả
    KẾT QUẢ. Tách ba nhóm để khi đọc log biết ngay vấn đề nằm ở tín hiệu, ở cổng,
    hay ở khâu quy đổi.
    """
    timestamp: pd.Timestamp
    strategy: str
    instrument: str
    action: str                       # BUY | SELL | FLAT | HOLD | SKIP

    # ── TÍN HIỆU
    signal_name: str = ""             # tên đại lượng, vd "reversal_21d", "s_score"
    signal_value: Optional[float] = None
    signal_rank: Optional[int] = None      # 1 = cao nhất trong rổ
    signal_universe_size: Optional[int] = None
    threshold_desc: str = ""               # ngưỡng đã cắt, dạng chữ

    # ── CỔNG
    gate_regime: str = ""                  # CALM | CRISIS | ...
    gate_regime_blocking: bool = False
    gate_hour_ok: Optional[bool] = None
    gate_data_ok: bool = True
    gate_notes: str = ""

    # ── KẾT QUẢ
    target_weight: float = 0.0
    vol_used: Optional[float] = None       # σ dùng để chuẩn hoá rủi ro
    bars_since_rebalance: Optional[int] = None
    bars_to_next_rebalance: Optional[int] = None
    est_cost_bps: Optional[float] = None
    est_swap_bps_per_night: Optional[float] = None

    reason: str = ""

    def to_row(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = str(self.timestamp)
        return d

    def explain(self) -> str:
        """Một dòng người đọc được — dùng cho log vận hành và báo cáo hằng ngày."""
        rank = ""
        if self.signal_rank and self.signal_universe_size:
            rank = f" hạng {self.signal_rank}/{self.signal_universe_size}"
        sig = ("—" if self.signal_value is None
               else f"{self.signal_value:+.4f}")
        gate = ""
        if self.gate_regime_blocking:
            gate = f" [CHẶN: {self.gate_regime}]"
        elif self.gate_hour_ok is False:
            gate = " [CHẶN: ngoài giờ khớp]"
        elif not self.gate_data_ok:
            gate = " [CHẶN: dữ liệu]"
        return (f"[{self.timestamp}] {self.strategy}/{self.instrument} "
                f"{self.action} w={self.target_weight:+.4f} · "
                f"{self.signal_name}={sig}{rank}{gate} · {self.reason}")


# ═══════════════════════════════════════════════════════ tiện ích dựng bản ghi
def rank_of(series: pd.Series, name: str) -> Optional[int]:
    """Thứ hạng của `name` trong `series` (1 = giá trị cao nhất). None nếu thiếu."""
    s = series.dropna()
    if name not in s.index:
        return None
    return int((s > s[name]).sum()) + 1


def traces_from_ranking(*, timestamp: pd.Timestamp, strategy: str,
                        signal_name: str, signal: pd.Series,
                        weights: pd.Series, n_leg: int,
                        regime: str = "CALM", regime_blocking: bool = False,
                        vol: Optional[pd.Series] = None,
                        cost_bps: Optional[pd.Series] = None,
                        swap_bps: Optional[pd.Series] = None,
                        bars_since: Optional[int] = None,
                        bars_next: Optional[int] = None,
                        hour_ok: Optional[bool] = None) -> List[RuleTrace]:
    """Dựng bản ghi cho chiến lược kiểu XẾP HẠNG (long top-N / short bottom-N).

    Ghi bản ghi cho **MỌI** công cụ trong rổ, kể cả công cụ không được chọn — vì câu
    hỏi "vì sao EURUSD hôm nay không có vị thế" chỉ trả lời được nếu có dòng của
    EURUSD kèm thứ hạng của nó.
    """
    s = signal.dropna()
    n = len(s)
    out: List[RuleTrace] = []
    for inst in signal.index:
        v = signal.get(inst)
        w = float(weights.get(inst, 0.0))
        r = rank_of(signal, inst)
        data_ok = bool(pd.notna(v))

        if regime_blocking:
            action, reason = "FLAT", f"cổng chế độ {regime} đang chặn toàn bộ chân"
        elif not data_ok:
            action, reason = "SKIP", "thiếu dữ liệu tín hiệu"
        elif abs(w) < 1e-9:
            action = "FLAT"
            reason = (f"hạng {r}/{n} — không nằm trong top {n_leg} "
                      f"cũng không trong bottom {n_leg}")
        else:
            action = "BUY" if w > 0 else "SELL"
            side = f"top {n_leg}" if w > 0 else f"bottom {n_leg}"
            reason = f"hạng {r}/{n} — thuộc {side}"

        out.append(RuleTrace(
            timestamp=timestamp, strategy=strategy, instrument=str(inst),
            action=action, signal_name=signal_name,
            signal_value=float(v) if data_ok else None,
            signal_rank=r, signal_universe_size=n,
            threshold_desc=f"long hạng 1-{n_leg} · short hạng {max(n - n_leg + 1, 1)}-{n}",
            gate_regime=regime, gate_regime_blocking=regime_blocking,
            gate_hour_ok=hour_ok, gate_data_ok=data_ok,
            target_weight=round(w, 5),
            vol_used=(round(float(vol[inst]), 6)
                      if vol is not None and inst in vol.index
                      and pd.notna(vol.get(inst)) else None),
            bars_since_rebalance=bars_since, bars_to_next_rebalance=bars_next,
            est_cost_bps=(round(float(cost_bps[inst]), 3)
                          if cost_bps is not None and inst in cost_bps.index else None),
            est_swap_bps_per_night=(round(float(swap_bps[inst]), 4)
                                    if swap_bps is not None and inst in swap_bps.index
                                    else None),
            reason=reason))
    return out


def summarise(traces: Sequence[RuleTrace]) -> pd.DataFrame:
    """Bảng gọn cho báo cáo vận hành hằng ngày."""
    if not traces:
        return pd.DataFrame()
    rows = []
    for t in traces:
        rows.append({
            "strategy": t.strategy, "instrument": t.instrument, "action": t.action,
            "signal": t.signal_name,
            "value": None if t.signal_value is None else round(t.signal_value, 4),
            "rank": t.signal_rank, "weight": t.target_weight,
            "regime": t.gate_regime, "reason": t.reason,
        })
    df = pd.DataFrame(rows)
    order = {"BUY": 0, "SELL": 1, "HOLD": 2, "FLAT": 3, "SKIP": 4}
    return df.sort_values(
        ["strategy", "action", "rank"],
        key=lambda c: c.map(order) if c.name == "action" else c
    ).reset_index(drop=True)
