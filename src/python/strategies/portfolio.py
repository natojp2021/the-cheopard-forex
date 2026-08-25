"""portfolio.py — DANH MỤC MỘT CHÂN của The Cheopard Forex. Điểm vào duy nhất cho live.

═══════════════════════════════════════════════════════════════════════════════
1. VÌ SAO CÓ MODULE NÀY KHI CHỈ CÓ MỘT CHIẾN LƯỢC
═══════════════════════════════════════════════════════════════════════════════
Vì `execution/order_plan.build()` — ĐƯỜNG DUY NHẤT ra lệnh — nhận một đối tượng
`PortfolioTargets`, và `engine`, `position_book`, `ops_view` đều đọc qua đây. Không có
module này thì mỗi bên gọi phải tự dựng mục tiêu, và mỗi bên sẽ dựng hơi khác nhau.

Nó là một lớp MỎNG: gọi chân duy nhất, gói quyết định vào `PortfolioTargets`, ghi sổ.
Nó KHÔNG gộp tỷ trọng, KHÔNG triệt tiêu chân ngược chiều, KHÔNG chuẩn hoá biến động —
cả ba việc đó chỉ có nghĩa khi có nhiều chân, nhưng chỗ để thêm chúng đã có tên sẵn.

═══════════════════════════════════════════════════════════════════════════════
2. RỦI RO ĐI TỪ KHOẢNG CÁCH SL, KHÔNG TỪ TỶ TRỌNG
═══════════════════════════════════════════════════════════════════════════════
    lot = equity x risk_pct / (SL_pip x giá trị 1 pip / lot)

`AsiaSweepH1` khai SL theo giá và đặt nó TRÊN SERVER broker cùng lệnh mở, nên rủi ro
mỗi lệnh là số ĐÃ BIẾT TRƯỚC — và rủi ro cả ngày là phép CỘNG, chặn được TRƯỚC khi gửi
lệnh thay vì ước lượng từ biến động lịch sử. `execution/risk_sizing.py` là chỗ duy
nhất hiện thực công thức này.

`target_weights()` dưới đây vẫn phát ra một vector tỷ trọng, nhưng đó là MÔ TẢ PHƠI
NHIỄM cho tầng hiển thị và báo cáo — **cỡ lệnh thật không đi qua nó**. Đây là chỗ dễ
đọc sai nhất của module, nên nó được ghi lại lần nữa trong docstring của chính hàm đó.

═══════════════════════════════════════════════════════════════════════════════
3. HAI LOẠI DỪNG LỖ, KHÔNG ĐƯỢC LẪN
═══════════════════════════════════════════════════════════════════════════════
    SL chiến lược    cực trị nến quét ± đệm, 24-32 pip — đây là luật GIAO DỊCH
    disaster_stop    >= 8xATR — đây là CẦU CHÌ hạ tầng

SL chiến lược LUÔN gần hơn cầu chì, nên trong thực tế cầu chì không bao giờ chạm. Giữ
nó vẫn đúng: nếu một lượt gửi lệnh nào đó thiếu SL (broker từ chối, gửi lại), cầu chì
là lớp cuối. Điều KHÔNG được làm là để cầu chì THAY SL chiến lược — 8xATR trên EURUSD
là ~80 pip, tức gần BA LẦN rủi ro dự kiến của một lệnh.

Bốn con số rủi ro cần đo lại trước khi cấp vốn: xem `registry.PORTFOLIO["can_do_lai"]`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.python.execution import decision_log as DLOG
from src.python.strategies.h1 import asia_sweep as AS

PORTFOLIO_NAME = "AsiaSweepSingleLeg"
FORM_END = pd.Timestamp("2024-01-01")

# MỘT chân. Giữ `LEG_WEIGHTS` để `tests/test_portfolio.py` và `position_book` không
# phải biết danh mục có bao nhiêu chân — chúng chỉ hỏi "chân nào, tỷ trọng nào".
LEG_WEIGHTS: Dict[str, float] = {"asia_sweep": 1.0}

# Nhóm rủi ro: một chân thì một nhóm. Ba công cụ trong chân KHÔNG phải ba nhóm — chúng
# chung một luật, và tương quan giữa chúng là tương quan của cùng một tín hiệu áp lên
# ba cặp có chung chân USD, tức KHÔNG hề trực giao.
RISK_GROUPS: Dict[str, tuple] = {"asia_sweep": ("asia_sweep",)}

# ═════════════════════════════════════════════════════════ khoá CHÂN
# Một CHIẾN LƯỢC chạy trên BA CÔNG CỤ, và sổ vị thế phải phân biệt được ba lệnh đó —
# nếu không thì `bars_held` và `sides()` của ba lệnh trộn vào nhau. Nên khoá chân là
# `asia_sweep:<CÔNG CỤ>`, và có HAI bảng tra vì `position_book` cần hai thứ khác nhau:
#
#     SINGLE_LEGS      khoá chân -> tên CHIẾN LƯỢC (để tra `registry.by_name`)
#     LEG_INSTRUMENT   khoá chân -> CÔNG CỤ        (để đặt lệnh)
#
# Gộp hai bảng làm một là chỗ đã sinh ra lỗi: `spec.symbols[0]` luôn trả EURUSD, nên
# cả ba chân cùng ghi vị thế lên EURUSD. Khoá phải khớp `rule_trace.signal_name`.
SINGLE_LEGS: Dict[str, str] = {
    f"asia_sweep:{s}": AS.NAME for s in AS.INSTRUMENTS}

LEG_INSTRUMENT: Dict[str, str] = {
    f"asia_sweep:{s}": s for s in AS.INSTRUMENTS}


def _side_of(decision: object, previous: int = 0) -> int:
    """Chiều mục tiêu của một quyết định. `HOLD` = GIỮ chiều đang có.

    Quyết định không vào lệnh KHÔNG có nghĩa là "đóng vị thế": chân này chỉ phát tín
    hiệu MỞ, còn việc đóng do SL/TP trên server hoặc mốc `flat_utc` lo. Trả 0 cho mọi
    trạng thái không-ENTRY sẽ làm mọi phiên không có setup trông như một chỉ thị đóng
    hết — và vị thế bị đóng sớm ngay sau khi mở.
    """
    if isinstance(decision, Exception) or decision is None:
        return int(previous)
    if getattr(decision, "enter", False):
        return int(getattr(decision, "side", 0) or 0)
    return int(previous)


# ═════════════════════════════════════════════════════════ giao diện LIVE
@dataclass
class PortfolioTargets:
    """Mục tiêu của danh mục cho phiên hiện tại.

    `single_decisions` là trường duy nhất chân hiện tại dùng. Ba trường
    `pair_weights` / `cross_decisions` / `rank_weights` luôn rỗng: chúng dành cho họ
    chân XẾP HẠNG CẮT NGANG (chọn k công cụ tốt nhất trong một rổ) và họ chân theo
    ĐỒNG TIỀN — hai hình dạng mục tiêu mà `order_plan` và `ops_view` đã biết đọc. Giữ
    trường rỗng thay vì xoá để thêm một chân họ khác không phải sửa `order_plan`, và
    để một `getattr` thiếu trường không thành `AttributeError` lúc 03:00.
    """
    asof: str
    single_decisions: Dict[str, object] = field(default_factory=dict)
    leg_scale: Dict[str, float] = field(default_factory=dict)
    regime: str = "NORMAL"
    pair_weights: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    cross_decisions: List[object] = field(default_factory=list)
    rank_weights: Dict[str, pd.Series] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    @property
    def entries(self) -> Dict[str, object]:
        """Chỉ những quyết định THẬT SỰ vào lệnh, khoá theo CÔNG CỤ."""
        out: Dict[str, object] = {}
        for leg, d in self.single_decisions.items():
            if isinstance(d, Exception) or not getattr(d, "enter", False):
                continue
            out[str(getattr(d, "instrument", leg.split(":")[-1]))] = d
        return out


def live_targets(start: str = "2020-01-01", *,
                 broker_markup_pct: float = 1.0,
                 bars_held: Optional[Dict[str, int]] = None,
                 log: bool = True) -> PortfolioTargets:
    """Mục tiêu của chân duy nhất cho phiên hiện tại + ghi sổ quyết định.

    `start`, `broker_markup_pct`, `bars_held` giữ trong chữ ký để bên gọi cũ
    (`engine`, `order_plan`, `ops_ctl`) không phải đổi. Chân này không dùng chúng:
    biên Á chốt theo GIỜ trong phiên chứ không theo số nến đã giữ, và chi phí được
    đọc từ spread THẬT tại phút khớp thay vì từ một biên ước lượng.

    Một quyết định LỖI của một công cụ KHÔNG được giết cả lượt: nó được gói lại
    thành `Exception` trong `single_decisions` và `order_plan` bỏ qua công cụ đó.
    Đây là fail-closed ở mức CÔNG CỤ — mất một cơ hội, không mất cả phiên.
    """
    decisions: Dict[str, object] = {}
    notes: List[str] = []
    for sym in AS.INSTRUMENTS:
        leg = f"asia_sweep:{sym}"
        try:
            decisions[leg] = AS.live_decision(sym)
        except Exception as exc:                      # noqa: BLE001
            decisions[leg] = exc
            notes.append(f"{sym}: KHÔNG ra được quyết định ({type(exc).__name__}: "
                         f"{exc}) — công cụ này bị bỏ lượt này")

    asof = ""
    for d in decisions.values():
        if not isinstance(d, Exception):
            asof = str(getattr(d, "asof", "")) or asof

    t = PortfolioTargets(
        asof=asof, single_decisions=decisions,
        leg_scale={"asia_sweep": 1.0},
        notes=notes + [f"preset {AS.ACTIVE_PRESET} · rủi ro "
                       f"{AS.RISK_PCT_PER_TRADE:.2f}%/lệnh"])
    if log:
        _log_decisions(t)
    return t


def _log_decisions(t: PortfolioTargets) -> None:
    """Ghi JSONL MỌI quyết định, kể cả KHÔNG vào lệnh.

    Chân này bỏ setup ở SÁU trạng thái khác nhau (`RANGE_REJECTED`,
    `SWEPT_NO_RECLAIM`, `BIAS_MISMATCH`, `RR_TOO_LOW`...). Chỉ ghi lệnh đã vào thì
    khi live lệch khỏi backtest không ai biết nó lệch ở BƯỚC nào — mà đó chính là
    thứ cần biết trước tiên.
    """
    rows = []
    for leg, d in t.single_decisions.items():
        if isinstance(d, Exception):
            rows.append({"leg": leg, "state": "ERROR", "detail": str(d)})
            continue
        rows.append({
            "leg": leg, "instrument": getattr(d, "instrument", ""),
            "asof": getattr(d, "asof", ""), "state": getattr(d, "state", ""),
            "side": getattr(d, "side", 0),
            "entry_px": getattr(d, "entry_px", float("nan")),
            "stop_px": getattr(d, "stop_px", float("nan")),
            "tp_px": getattr(d, "tp_px", float("nan")),
            "sl_pips": getattr(d, "sl_pips", float("nan")),
            "rr": getattr(d, "rr", float("nan")),
            "asia_range_pips": getattr(d, "asia_range_pips", float("nan")),
            "depth_pips": getattr(d, "depth_pips", float("nan")),
            "steps": [list(s) for s in getattr(d, "steps", ())],
        })
    try:
        DLOG.record_many(rows)
    except Exception:                                 # noqa: BLE001
        # Ghi sổ hỏng KHÔNG được chặn giao dịch — nhưng cũng không được im lặng.
        # `decision_log` tự in cảnh báo; ở đây chỉ đảm bảo ngoại lệ không lan lên.
        pass


def target_weights(targets: "PortfolioTargets", *,
                   positions: Optional[Dict[str, int]] = None) -> pd.Series:
    """Tỷ trọng RÒNG theo CÔNG CỤ — CHỈ để báo cáo phơi nhiễm, KHÔNG để tính lot.

    ⚠️ ĐỌC KỸ. Tỷ trọng ở đây KHÔNG phải cỡ lệnh. Cỡ lệnh đến từ
    `risk_sizing.lots_for_risk()` dựa trên khoảng cách SL. Nhân tỷ trọng này với
    equity và đòn bẩy để ra lot là SAI — và sai IM LẶNG, vì kết quả vẫn là một con số
    lot trông hợp lý.

    Hàm tồn tại vì `ops_view` và `netting_report` cần một vector phơi nhiễm để hiển
    thị, và vì `registry.PORTFOLIO["target_weights"]` trỏ vào đây. Giá trị trả về là
    **chia đều cho các công cụ ĐANG có lệnh**, chuẩn hoá tổng trị tuyệt đối bằng
    1,0 — một mô tả phơi nhiễm, không phải một chỉ thị cỡ lệnh.
    """
    pos = positions or {}
    raw: Dict[str, float] = {}
    for leg, d in targets.single_decisions.items():
        if isinstance(d, Exception):
            continue
        sym = str(getattr(d, "instrument", "") or leg.split(":")[-1])
        side = int(getattr(d, "side", 0)) if getattr(d, "enter", False) else 0
        if side == 0:
            # Không có tín hiệu mới thì GIỮ chiều đang giữ — nếu không, mọi phiên
            # không có setup sẽ trông như một chỉ thị ĐÓNG hết vị thế đang mở.
            side = int(pos.get(leg, 0))
        if side:
            raw[sym] = raw.get(sym, 0.0) + float(side)
    s = pd.Series(raw, dtype=float).sort_index()
    gross = float(s.abs().sum())
    return (s / gross).round(6) if gross > 0 else s


def stop_targets(targets: "PortfolioTargets") -> Dict[str, Dict[str, float]]:
    """SL/TP theo CÔNG CỤ — đầu vào của `risk_sizing` và của lệnh gửi broker.

    Đây là hợp đồng giữa chiến lược và tầng thực thi: có SL thì có sizing, không có
    SL thì `order_plan` KHÔNG mở vị thế (fail-closed). Trả về rỗng nghĩa là phiên này
    không có lệnh mới nào.
    """
    out: Dict[str, Dict[str, float]] = {}
    for sym, d in targets.entries.items():
        out[sym] = {
            "side": float(getattr(d, "side", 0)),
            "entry": float(getattr(d, "entry_px", float("nan"))),
            "stop": float(getattr(d, "stop_px", float("nan"))),
            "tp": float(getattr(d, "tp_px", float("nan"))),
            "sl_pips": float(getattr(d, "sl_pips", float("nan"))),
            "rr": float(getattr(d, "rr", float("nan"))),
        }
    return out


def netting_report(targets: "PortfolioTargets",
                   positions: Optional[Dict[str, int]] = None) -> pd.DataFrame:
    """Trước/sau triệt tiêu, theo công cụ.

    Với MỘT chân thì không có gì để triệt tiêu — `gross_legs` luôn bằng `|net|`. Giữ
    hàm để `ops_view` và `registry.PORTFOLIO["netting_report"]` không phải phân
    nhánh, và để khi có chân thứ hai thì chỗ cần sửa đã có sẵn tên.
    """
    w = target_weights(targets, positions=positions)
    if w.empty:
        return pd.DataFrame(columns=["gross_legs", "net", "saved"])
    return pd.DataFrame({"gross_legs": w.abs(), "net": w,
                         "saved": 0.0}).sort_index()


def exposure_report(targets: PortfolioTargets) -> pd.DataFrame:
    """Phơi nhiễm theo ĐỒNG TIỀN. Một vị thế EURUSD là long EUR + short USD.

    Vẫn cần dù chỉ một chân: ba cặp của rổ đều có chân USD, nên ba lệnh cùng chiều
    USD là MỘT cược vào USD gấp ba, không phải ba cược độc lập.
    """
    from src.python.shared import asset_profile as AP

    acc: Dict[str, float] = {}
    for sym, d in targets.entries.items():
        prof = AP.get(sym)
        side = float(getattr(d, "side", 0))
        acc[prof.base] = acc.get(prof.base, 0.0) + side
        acc[prof.quote] = acc.get(prof.quote, 0.0) - side
    if not acc:
        return pd.DataFrame(columns=["exposure"])
    return (pd.DataFrame({"exposure": pd.Series(acc)})
            .sort_values("exposure", ascending=False))


# ═════════════════════════════════════════════════════════ backtest / thống kê
@dataclass
class PortfolioResult:
    pnl: pd.Series                      # % equity mỗi ngày
    per_leg: Dict[str, pd.Series]       # R mỗi ngày, từng công cụ
    trades: pd.DataFrame


def backtest(start: str = "2020-01-01", *, broker_markup_pct: float = 1.0,
             preset: str = "") -> PortfolioResult:
    """Backtest cả rổ. Đơn vị của `pnl` là **% equity**, ở `RISK_PCT_PER_TRADE`."""
    per_leg: Dict[str, pd.Series] = {}
    frames: List[pd.DataFrame] = []
    for sym in AS.INSTRUMENTS:
        res = AS.backtest(sym, preset=preset)
        if len(res.trades):
            frames.append(res.trades)
        per_leg[sym] = AS.daily_pnl(sym, preset=preset)
    # ĐƠN VỊ: một R bằng `RISK_PCT_PER_TRADE` PHẦN TRĂM equity, nên NHÂN, không chia
    # thêm 100 — xem cảnh báo ở `asia_sweep.portfolio_daily_pnl`.
    total = (pd.concat(per_leg.values(), axis=1).fillna(0.0).sum(axis=1)
             * AS.RISK_PCT_PER_TRADE)
    T = (pd.concat(frames, ignore_index=True) if frames
         else pd.DataFrame(columns=["r_net"]))
    return PortfolioResult(pnl=total, per_leg=per_leg, trades=T)


def stats(pnl: pd.Series, label: str = "") -> Dict[str, object]:
    """Chỉ số một trader đọc là hiểu. `pnl` tính bằng % equity mỗi ngày."""
    if pnl.empty:
        return {"nhãn": label, "n ngày": 0}
    curve = (1.0 + pnl / 100.0).cumprod()
    dd = (curve / curve.cummax() - 1.0) * 100.0
    # DD so với vốn BAN ĐẦU TĨNH — đúng luật FTMO, không neo theo đỉnh equity
    dd_static = (curve - 1.0) * 100.0
    ann = float(pnl.mean()) * 252.0
    sd = float(pnl.std(ddof=1))
    return {
        "nhãn": label,
        "n ngày": int(len(pnl)),
        "lãi/năm %": round(ann, 2),
        "Sharpe": round(ann / (sd * np.sqrt(252.0)), 3) if sd > 0 else float("nan"),
        "MaxDD từ đỉnh %": round(float(dd.min()), 2),
        "đáy so vốn ban đầu %": round(float(dd_static.min()), 2),
        "ngày tệ nhất %": round(float(pnl.min()), 3),
        "số ngày âm > 1%": int((pnl < -1.0).sum()),
        "sàn nội bộ": "-9,00%",
        "luật FTMO": "-10,00%",
    }


def correlation_matrix(res: PortfolioResult) -> pd.DataFrame:
    """Tương quan giữa ba CÔNG CỤ trong cùng một chân.

    KHÔNG phải bằng chứng đa dạng hoá: ba cặp chung luật và chung chân USD. Bảng này
    tồn tại để thấy phần chồng lấn LỚN đến đâu, không để khoe nó nhỏ.
    """
    return pd.concat(res.per_leg, axis=1).fillna(0.0).corr().round(3)


def group_correlation(res: PortfolioResult) -> pd.DataFrame:
    """Một nhóm rủi ro thì ma trận 1x1. Giữ tên để `ops_view` không phải phân nhánh."""
    return pd.DataFrame([[1.0]], index=["asia_sweep"], columns=["asia_sweep"])


def single_leg_decisions(start: str = "2020-01-01", *,
                         broker_markup_pct: float = 1.0,
                         bars_held: Optional[Dict[str, int]] = None
                         ) -> Dict[str, object]:
    """Quyết định của các chân một-công-cụ. Với danh mục này là TOÀN BỘ danh mục."""
    return live_targets(start, broker_markup_pct=broker_markup_pct,
                        bars_held=bars_held, log=False).single_decisions


if __name__ == "__main__":
    import json
    import sys

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    res = backtest()
    print(json.dumps(stats(res.pnl, PORTFOLIO_NAME), indent=2, ensure_ascii=False))
    print()
    print(correlation_matrix(res).to_string())
