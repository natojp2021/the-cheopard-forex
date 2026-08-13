"""Vòng 69 — ASIAN SESSION RANGE BREAKOUT trên USDJPY. Luật do người dùng cung cấp.

LUẬT NGUYÊN VĂN (không tinh chỉnh trước khi đo)
================================================
    Công cụ    USDJPY
    Cửa sổ     03:00-06:00 giờ BROKER (GMT+2 mùa đông / GMT+3 mùa hè)
    Vào lệnh   phá biên độ của cửa sổ đó
    Thoát      19:00 giờ broker
    Cắt lỗ     đầu kia của biên độ
    Tần suất   ĐÚNG 1 lệnh mỗi ngày

Người cung cấp nói: có lãi suốt giai đoạn backtest từ 2011, và có người chạy tiền
thật từ 2023.

VÌ SAO PHẢI ĐO LẠI CHỨ KHÔNG TIN NGAY — VÀ ĐO CÁI GÌ
=====================================================
Chiến lược này THUẬN CHIỀU (breakout). 68 vòng trước của dự án đo được: trên FX, mọi
họ thuận chiều đều thua ở mọi khung — EWMAC 6 tốc độ, breakout Donchian 6 cửa sổ,
range expansion, squeeze, session breakout. Đó là bằng chứng mạnh CHỐNG lại luật này.

Nhưng bản này khác bốn điểm so với `sig_session_break` mà vòng 57 đã bác bỏ, và mỗi
điểm đều có thể là điểm quyết định:

    vòng 57                          bản này
    ─────────────────────────────    ────────────────────────────────
    biên độ phiên Á 00-07 UTC        cửa sổ HẸP 3 tiếng
    vào trong 07-12 UTC              vào bất cứ lúc nào sau cửa sổ
    thoát bằng time-stop theo nến    thoát ở GIỜ CỐ ĐỊNH 19:00
    không có SL                      SL = đầu kia của biên độ
    nhiều lệnh/ngày                  ĐÚNG 1 lệnh/ngày

Nên nó xứng đáng được đo riêng thay vì suy từ kết quả cũ.

MÚI GIỜ LÀ CHỖ DỄ SAI NHẤT — VÀ SAI Ở ĐÂY THÌ KẾT QUẢ VÔ NGHĨA
===============================================================
Dữ liệu của dự án là UTC. Giờ broker GMT+2/+3 đổi theo DST châu Âu (chủ nhật cuối
tháng 3 → chủ nhật cuối tháng 10). Quy đổi:

    mùa đông (GMT+2)  03:00-06:00 broker = 01:00-04:00 UTC · thoát 19:00 = 17:00 UTC
    mùa hè   (GMT+3)  03:00-06:00 broker = 00:00-03:00 UTC · thoát 19:00 = 16:00 UTC

Nếu dùng một mốc UTC cố định cho cả năm thì nửa số ngày lệch một tiếng, và cửa sổ
3 tiếng lệch một tiếng là lệch một phần ba. Script này tính DST đúng, VÀ đo thêm ba
biến thể múi giờ để xem kết quả có nhạy cảm với giả định đó không — nếu nhạy thì
"chiến lược" thật ra chỉ là một mốc giờ may mắn.

GIỚI HẠN DỮ LIỆU PHẢI NÓI TRƯỚC
================================
Dự án có dữ liệu từ 2020-01, KHÔNG có từ 2011. Nên đây là 6,5 năm chứ không phải 15
năm, và không kiểm chứng được phần lịch sử mà người cung cấp nhắc tới. Cái đo được ở
đây là: luật này có còn hiệu lực trong 6,5 năm gần nhất không.
"""
from __future__ import annotations

import io
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import numpy as np
import pandas as pd

from src.python.shared import asset_profile as AP
from src.python.shared import carry_costs as CC
from src.python.shared import fx_data as D

pd.set_option("display.width", 235, "display.max_columns", 30, "display.max_rows", 200)
FORM_END = pd.Timestamp("2024-01-01")
OUT = ROOT / "reports" / "fx_research"


# ═══════════════════════════════════════════════════════ múi giờ
def broker_offset(idx: pd.DatetimeIndex) -> pd.Series:
    """Chênh lệch giờ broker so với UTC: +2 mùa đông, +3 mùa hè (DST châu Âu).

    DST châu Âu: bắt đầu chủ nhật CUỐI tháng 3, kết thúc chủ nhật CUỐI tháng 10.
    Tính bằng `Europe/Berlin` thay vì tự viết luật ngày — luật DST đổi theo năm và
    tự viết là cách chắc chắn để sai vài ngày mỗi năm mà không ai phát hiện.
    """
    local = idx.tz_localize("UTC").tz_convert("Europe/Berlin")
    # Berlin là GMT+1 mùa đông / GMT+2 mùa hè; broker là GMT+2 / GMT+3 → cộng 1.
    # Lấy offset qua chênh lệch giờ thay vì `.utcoffset()` (chỉ có trên Timestamp
    # đơn lẻ, không có trên DatetimeIndex).
    off = ((local.hour - idx.hour) % 24) + 1
    return pd.Series(off.astype(int), index=idx)


@dataclass(frozen=True)
class Config:
    """Cấu hình luật. Mặc định là ĐÚNG luật người dùng đưa, không đổi gì."""
    symbol: str = "USDJPY"
    range_start_broker: int = 3       # 03:00 giờ broker
    range_end_broker: int = 6         # 06:00 giờ broker (không bao gồm)
    exit_hour_broker: int = 19        # 19:00 giờ broker
    fixed_offset: Optional[int] = None  # None = dùng DST thật; số = ép cứng
    one_trade_per_day: bool = True


def hour_broker(idx: pd.DatetimeIndex, cfg: Config) -> pd.Series:
    off = (pd.Series(cfg.fixed_offset, index=idx) if cfg.fixed_offset is not None
           else broker_offset(idx))
    return (pd.Series(idx.hour, index=idx) + off) % 24


# ═══════════════════════════════════════════════════════ mô phỏng
@dataclass
class Result:
    trades: pd.DataFrame
    pnl_daily: pd.Series


def backtest(df: pd.DataFrame, cost_bps: float, swap_bps_bar: float,
             cfg: Config = Config()) -> Result:
    """Một lệnh mỗi ngày, khớp tại nến ĐÓNG CỬA vượt biên độ.

    Giả định khớp lệnh CỐ Ý BI QUAN ở ba chỗ, vì backtest breakout rất dễ đẹp giả:
      · vào lệnh ở giá ĐÓNG CỬA của nến phá, không phải ở mức biên độ. Vào ở mức
        biên là giả định lệnh chờ khớp đúng giá — trên thị trường thật, nến phá
        thường đã đi qua mức đó rồi.
      · SL kiểm tra trên LOW/HIGH của nến. Nếu trong cùng một nến chạm cả SL lẫn
        giờ thoát thì tính là chạm SL.
      · chi phí trừ đủ: một lượt khứ hồi + swap cho mỗi nến giữ.
    """
    hb = hour_broker(df.index, cfg)
    day_key = pd.Series(df.index.normalize(), index=df.index)
    in_range = (hb >= cfg.range_start_broker) & (hb < cfg.range_end_broker)
    after_range = hb >= cfg.range_end_broker
    exit_hour = hb >= cfg.exit_hour_broker

    o = df["open"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()
    TR = in_range.to_numpy()
    SA = after_range.to_numpy()
    GT = exit_hour.to_numpy()
    day_index = day_key.to_numpy()
    n = len(df)

    rows: List[Dict] = []
    i = 0
    while i < n:
        d0 = day_index[i]
        # gom nến của MỘT ngày
        j = i
        while j < n and day_index[j] == d0:
            j += 1
        sl_idx = slice(i, j)

        m_range = TR[sl_idx]
        if m_range.sum() < 2:                   # ngày thiếu dữ liệu phiên Á
            i = j
            continue
        hi_r = float(np.nanmax(h[sl_idx][m_range]))
        lo_r = float(np.nanmin(l[sl_idx][m_range]))
        if not (np.isfinite(hi_r) and np.isfinite(lo_r) and hi_r > lo_r):
            i = j
            continue

        # quét các nến SAU cửa sổ, tìm nến phá đầu tiên
        entered = None
        for t in range(i, j):
            if not SA[t] or GT[t]:
                continue
            if c[t] > hi_r:
                entered = (t, 1, hi_r, lo_r)
                break
            if c[t] < lo_r:
                entered = (t, -1, lo_r, hi_r)
                break
        if entered is None:
            i = j
            continue

        t0, side, break_level, sl_px = entered
        entry = c[t0]
        reason_text, exit_px, t1 = "EOD", c[j - 1], j - 1
        for t in range(t0 + 1, j):
            hit_sl = (l[t] <= sl_px) if side > 0 else (h[t] >= sl_px)
            if hit_sl:
                reason_text, exit_px, t1 = "SL", sl_px, t
                break
            if GT[t]:
                reason_text, exit_px, t1 = "TIME_EXIT", c[t], t
                break

        bars = t1 - t0
        gross = side * (exit_px - entry) / entry * 1e4
        cost_bps = cost_bps + bars * swap_bps_bar
        rows.append({
            "ngay": pd.Timestamp(d0), "entry_time": df.index[t0],
            "exit_time": df.index[t1], "side": side, "bars": bars,
            "reason": reason_text, "range_bps": (hi_r - lo_r) / lo_r * 1e4,
            "entry_px": entry, "exit_px": exit_px, "sl_px": sl_px,
            "gross_bps": gross, "cost_bps": cost_bps, "net_bps": gross - cost_bps})
        i = j

    T = pd.DataFrame(rows)
    d = (T.set_index("exit_time")["net_bps"].resample("1D").sum().fillna(0.0)
         if not T.empty else pd.Series(dtype=float))
    return Result(T, d)


def sharpe(s: pd.Series, lo=None, hi=None) -> float:
    if lo is not None:
        s = s[s.index >= lo]
    if hi is not None:
        s = s[s.index < hi]
    sd = float(s.std(ddof=1))
    return float(s.mean()) / sd * np.sqrt(252) if sd > 0 and len(s) > 60 else np.nan


def load_pair(symbol: str, tf: str = "M30", broker_markup_pct: float = 1.0):
    b = D.build_bars(D.load_m1(symbol), tf)
    b = b[b.index >= "2020-01-01"]
    px = float(b["close"].median())
    prof = AP.get(symbol)
    cost = (float(b["spread_usd"].median()) + prof.commission_price_units(px)) / px * 1e4
    swap = (CC.SWAP_CALENDAR_MULTIPLIER * broker_markup_pct / 365.0 * 100.0
            * (0.5 if tf == "M30" else 1.0) / 24.0)
    return b[["open", "high", "low", "close"]], cost, swap


def report(T: pd.DataFrame, d: pd.Series, name_text: str) -> Dict:
    if T.empty:
        return {"biến thể": name_text, "n": 0}
    v = T["net_bps"]
    cum = d.cumsum()
    yrs = max((d.index.max() - d.index.min()).days / 365.25, 1e-9)
    yr = d.groupby(d.index.year).sum()
    return {
        "biến thể": name_text, "ALL": round(sharpe(d), 3),
        "FORM": round(sharpe(d, hi=FORM_END), 3),
        "OOS": round(sharpe(d, lo=FORM_END), 3),
        "n": len(T), "thắng%": round(float((v > 0).mean()) * 100, 1),
        "gross/lệnh": round(float(T["gross_bps"].mean()), 2),
        "phí/lệnh": round(float(T["cost_bps"].mean()), 2),
        "net/lệnh": round(float(v.mean()), 2),
        "t": round(float(v.mean()) / float(v.std(ddof=1)) * np.sqrt(len(v)), 2),
        "%/năm": round(float(cum.iloc[-1]) / 100 / yrs, 2),
        "MaxDD%": round(float((cum.cummax() - cum).max()) / 100, 2),
        "năm+": f"{int((yr > 0).sum())}/{len(yr)}",
    }


def main() -> None:
    t0 = time.time()
    print("LUẬT ĐO NGUYÊN VĂN: USDJPY · range 03:00-06:00 giờ broker · vào khi phá ·")
    print("thoát 19:00 · SL = đầu kia của range · 1 lệnh/ngày")
    print("Dữ liệu: 2020-01 → nay (dự án KHÔNG có dữ liệu từ 2011)\n")

    df, cost, swap = load_pair("USDJPY")
    print(f"USDJPY M30: {len(df):,} nến · chi phí khứ hồi {cost:.3f} bps · "
          f"swap {swap:.4f} bps/nến\n")

    # ── A. luật gốc, DST đúng
    r = backtest(df, cost, swap, Config())
    rows = [report(r.trades, r.pnl_daily, "GỐC (DST đúng)")]

    # ── B. độ nhạy múi giờ — nếu kết quả đổi nhiều thì đó là mốc giờ may mắn
    for off in (0, 1, 2, 3, 4):
        cfg = Config(fixed_offset=off)
        rr = backtest(df, cost, swap, cfg)
        rows.append(report(rr.trades, rr.pnl_daily, f"ép cứng GMT+{off}"))

    A = pd.DataFrame(rows)
    print("=" * 150)
    print("A. LUẬT GỐC và ĐỘ NHẠY MÚI GIỜ")
    print("=" * 150)
    print(A.to_string(index=False))

    # ── C. cùng luật trên các major khác — luật thật phải sống ở nhiều nơi
    print()
    print("=" * 150)
    print("B. CÙNG LUẬT trên 6 major khác — luật có tín hiệu thật thì không chỉ")
    print("   sống trên đúng một cặp")
    print("=" * 150)
    rows = []
    for sym in AP.FX_ALL:
        d2, c2, s2 = load_pair(sym)
        rr = backtest(d2, c2, s2, Config(symbol=sym))
        rows.append({**report(rr.trades, rr.pnl_daily, sym)})
    B = pd.DataFrame(rows).sort_values("ALL", ascending=False)
    print(B.to_string(index=False))

    # ── D. phân rã theo năm và theo lý do thoát
    print()
    print("=" * 150)
    print("C. USDJPY — PHÂN RÃ")
    print("=" * 150)
    T, d = r.trades, r.pnl_daily
    yr = d.groupby(d.index.year).sum() / 100.0
    print("   theo năm (%):  " + "  ".join(f"{int(y)}: {v:+.2f}" for y, v in yr.items()))
    print("   lý do thoát:   " + str(T["reason"].value_counts().to_dict()))
    for ly in T["reason"].unique():
        s = T[T["reason"] == ly]
        print(f"     {ly:10s} {len(s):4d} lệnh · net trung bình "
              f"{float(s['net_bps'].mean()):+7.2f} bps")
    print(f"   biên độ range trung vị: {float(T['range_bps'].median()):.1f} bps · "
          f"chi phí {cost:.2f} bps = {cost / float(T['range_bps'].median()) * 100:.1f}% biên độ")
    print(f"   giữ lệnh trung bình: {float(T['bars'].mean()):.1f} nến M30 "
          f"({float(T['bars'].mean()) / 2:.1f} giờ)")

    A.to_csv(OUT / "asian_range_A.csv", index=False)
    B.to_csv(OUT / "asian_range_B.csv", index=False)
    T.to_csv(OUT / "asian_range_trades.csv", index=False)
    print(f"\nelapsed {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
