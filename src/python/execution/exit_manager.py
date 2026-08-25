"""exit_manager.py — GHI NHẬN KHI LỆNH ĐÓNG. Không dời stop, không trailing.

CÁI GÌ ĐÓNG LỆNH — VÀ VÌ SAO KHÔNG PHẢI MODULE NÀY
===================================================
    dừng lỗ / chốt lời   nằm trên SERVER broker, đi kèm lệnh mở. Đây là lối thoát
                         chính, và với phần lớn lệnh là lối thoát DUY NHẤT.
    mốc đóng phiên       chiến lược trong phiên đóng hết ở một giờ cố định.
    cầu chì thảm hoạ     chỉ khi tiến trình chết — xem `disaster_stop.py`.

Cả ba đều KHÔNG cần một vòng lặp quản lý lệnh ở live. Đó là quyết định thiết kế, và
nó có số đo: dời stop về breakeven sau khi chốt một phần làm kỳ vọng TỤT từ +0,0893
xuống +0,0124 R mỗi lệnh trên cùng 462 lệnh (winrate tăng 10 điểm, PF giảm từ 1,260
xuống 1,039). Cơ chế: chốt một phần mua tỷ lệ thắng bằng cách bán mất phần đuôi lãi,
rồi breakeven quét nốt phần còn lại của những lệnh đang đi đúng hướng.

Hệ quả kiến trúc quan trọng hơn cả con số: MỘT dừng lỗ và MỘT chốt lời nằm trên server
thì backtest và live thoát ở ĐÚNG cùng một giá. Mỗi nhánh của một vòng lặp quản lý lệnh
là một chỗ live có thể lệch khỏi backtest mà không ai biết.

VẬY MODULE NÀY LÀM GÌ
=====================
**Ghi nhận khi đóng**: lệnh đóng vì lý do gì, giữ bao lâu, lãi lỗ bao nhiêu, đã từng
lãi nhất bao nhiêu (MFE) và lỗ sâu nhất bao nhiêu (MAE).

Thiếu nó thì không trả lời được câu hỏi vận hành quan trọng nhất khi live lệch khỏi
backtest: **lệch ở đâu?** Có phải dừng lỗ bị quét thường xuyên hơn dự kiến? Có phải
chốt lời không bao giờ tới? Không có bản ghi thì chỉ thấy "equity thấp hơn dự kiến"
và không lần ra được.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# Lý do đóng lệnh — tập ĐÓNG, khai ở đây để bản ghi không mọc ra biến thể chính tả.
REASON_SIGNAL = "SIGNAL_REVERSE"     # tín hiệu ngược chiều
REASON_TIMESTOP = "TIMESTOP"         # hết số nến cho phép giữ
REASON_FUSE = "DISASTER_STOP"        # cầu chì trên broker nổ
REASON_MANUAL = "MANUAL"             # người vận hành đóng tay
REASON_RECONCILE = "CLOSED_ELSEWHERE"  # đối soát phát hiện broker không còn vị thế
REASONS = (REASON_SIGNAL, REASON_TIMESTOP, REASON_FUSE, REASON_MANUAL,
           REASON_RECONCILE)


@dataclass
class ClosedTrade:
    """Bản ghi MỘT lệnh đã đóng. Đủ để tái lập và để so với backtest."""
    leg: str
    symbol: str
    side: str
    lots: float
    entry_bar_utc: str
    exit_bar_utc: str
    entry_price: float
    exit_price: float
    bars_held: int
    reason: str
    gross_bps: float
    mfe_bps: Optional[float] = None      # lãi chưa thực hiện TỐT NHẤT đã đạt
    mae_bps: Optional[float] = None      # lỗ chưa thực hiện SÂU NHẤT đã chịu
    stop_price: Optional[float] = None
    note: str = ""

    # ── TRƯỜNG KIỂM TOÁN, chép sang từ `LegPosition` lúc đóng (thêm 15/08/2026).
    #
    # Chép chứ không tra ngược: sổ vị thế XOÁ bản ghi khi đóng, nên sau thời điểm
    # này không còn chỗ nào giữ chúng. Không chép là mất vĩnh viễn khả năng trả
    # lời "lệnh này do bản build nào sinh ra, trên tài khoản nào, với equity bao
    # nhiêu" — ba câu hỏi của mọi cuộc điều tra sau sự cố.
    equity_at_entry: float = 0.0
    leverage_at_entry: float = 0.0
    weight_at_entry: float = 0.0
    notional_usd: float = 0.0
    ticket: int = 0
    magic: int = 0
    build: str = ""
    account_login: str = ""
    timeframe: str = ""
    # Chi phí THẬT, do bên gọi truyền từ deal của broker. `None` = CHƯA ĐO ĐƯỢC,
    # khác 0.0 (= đo được và bằng không) — email hiện "—" thay vì "+0.00 $" để
    # không nói dối rằng lệnh này không mất phí.
    swap_usd: Optional[float] = None
    commission_usd: Optional[float] = None
    pnl_usd: Optional[float] = None
    equity_at_exit: float = 0.0

    def to_row(self) -> Dict[str, object]:
        return asdict(self)

    def explain(self) -> str:
        s = (f"[{self.exit_bar_utc}] {self.leg}/{self.symbol} ĐÓNG {self.reason} · "
             f"{self.side} {self.lots:.2f} lot · {self.bars_held} nến · "
             f"{self.gross_bps:+.1f} bps")
        if self.mfe_bps is not None:
            s += f" · MFE {self.mfe_bps:+.1f} / MAE {self.mae_bps:+.1f}"
        return s


def excursions(bars: pd.DataFrame, entry_price: float, side: int,
               entry_bar_utc: str, exit_bar_utc: str) -> Dict[str, float]:
    """MFE và MAE của một lệnh, đơn vị bps.

    Quét `high`/`low` chứ không phải `close`: lệnh đã TỪNG ở mức đó, và câu hỏi mà
    hai số này trả lời là "nó đã từng ở đâu", không phải "nó đóng cửa ở đâu".
    """
    if entry_price <= 0 or bars is None or bars.empty:
        return {"mfe_bps": 0.0, "mae_bps": 0.0}
    lo = pd.Timestamp(entry_bar_utc)
    hi = pd.Timestamp(exit_bar_utc)
    w = bars[(bars.index >= lo) & (bars.index <= hi)]
    if w.empty:
        return {"mfe_bps": 0.0, "mae_bps": 0.0}
    if side > 0:
        best, worst = float(w["high"].max()), float(w["low"].min())
    else:
        best, worst = float(w["low"].min()), float(w["high"].max())
    return {
        "mfe_bps": round(side * (best - entry_price) / entry_price * 1e4, 2),
        "mae_bps": round(side * (worst - entry_price) / entry_price * 1e4, 2),
    }


def record_close(book, leg: str, *, reason: str, exit_price: float,
                 exit_bar_utc: str, bars_held: int,
                 bars: Optional[pd.DataFrame] = None,
                 note: str = "", log: bool = True,
                 swap_usd: Optional[float] = None,
                 commission_usd: Optional[float] = None,
                 pnl_usd: Optional[float] = None,
                 equity_at_exit: float = 0.0) -> Optional[ClosedTrade]:
    """Đóng một chân trong sổ VÀ ghi nhận đầy đủ. Điểm hội tụ DUY NHẤT khi đóng lệnh.

    Hệ XAUUSD học đúng bài này ở `position_lifecycle.finalize_position_closed()`:
    mọi nhánh đóng lệnh — bị động do stop chạm, hay chủ động do code gọi — đều phải
    đi qua MỘT hàm. Hai đường đóng lệnh không hội tụ nghĩa là một trong hai sẽ quên
    cập nhật sổ, và sổ lệch thì đối soát báo MỒ CÔI cho chính vị thế của mình.
    """
    if reason not in REASONS:
        raise ValueError(f"lý do đóng không hợp lệ: {reason!r}. Hợp lệ: {REASONS}")

    p = book.get(leg)
    if p is None:
        return None

    side = 1 if p.side == "BUY" else -1
    gross = (side * (float(exit_price) - p.entry_price) / p.entry_price * 1e4
             if p.entry_price > 0 else 0.0)
    ex = (excursions(bars, p.entry_price, side, p.entry_bar_utc, exit_bar_utc)
          if bars is not None else {"mfe_bps": None, "mae_bps": None})

    rec = ClosedTrade(
        leg=leg, symbol=p.symbol, side=p.side, lots=p.lots,
        entry_bar_utc=p.entry_bar_utc, exit_bar_utc=str(exit_bar_utc),
        entry_price=p.entry_price, exit_price=float(exit_price),
        bars_held=int(bars_held), reason=reason, gross_bps=round(gross, 2),
        mfe_bps=ex["mfe_bps"], mae_bps=ex["mae_bps"],
        stop_price=p.stop_price, note=note,
        # Chép trước khi `book.close()` xoá bản ghi — sau dòng đó là mất.
        equity_at_entry=getattr(p, "equity_at_entry", 0.0),
        leverage_at_entry=getattr(p, "leverage_at_entry", 0.0),
        weight_at_entry=getattr(p, "weight_at_entry", 0.0),
        notional_usd=getattr(p, "notional_usd", 0.0),
        ticket=getattr(p, "ticket", 0), magic=getattr(p, "magic", 0),
        build=getattr(p, "build", ""),
        account_login=getattr(p, "account_login", ""),
        timeframe=getattr(p, "timeframe", ""),
        swap_usd=swap_usd, commission_usd=commission_usd, pnl_usd=pnl_usd,
        equity_at_exit=float(equity_at_exit))

    book.close(leg, reason=reason)

    if log:
        try:
            from src.python.execution import decision_log as DLOG
            DLOG.record_many([rec.to_row()], strategy="ClosedTrades")
        except Exception:                                  # pragma: no cover
            pass
    return rec


def summarise(trades: List[ClosedTrade]) -> pd.DataFrame:
    """Bảng theo LÝ DO ĐÓNG — thứ đầu tiên phải nhìn khi live lệch khỏi backtest.

    Nếu tỷ lệ TIMESTOP ở live khác hẳn backtest thì đồng hồ time-stop đang sai; nếu
    DISASTER_STOP xuất hiện thường xuyên thì cầu chì đang quá gần. Cả hai đều không
    nhìn ra được từ đường equity.
    """
    if not trades:
        return pd.DataFrame()
    df = pd.DataFrame([t.to_row() for t in trades])
    g = df.groupby("reason").agg(
        lệnh=("gross_bps", "size"),
        net_bps=("gross_bps", "mean"),
        thắng_pct=("gross_bps", lambda s: float((s > 0).mean()) * 100),
        nến_giữ=("bars_held", "mean"),
        mfe=("mfe_bps", "mean"),
        mae=("mae_bps", "mean"),
    ).round(2)
    return g.sort_values("lệnh", ascending=False)
