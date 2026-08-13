"""check_broker_swap.py — đo biên swap THẬT của broker, quy về %/năm.

VÌ SAO SCRIPT NÀY LÀ ĐIỀU KIỆN TIÊN QUYẾT ĐỂ TRIỂN KHAI
=======================================================
`currency_reversal` giữ vị thế 21 ngày, tức trả swap ~21 đêm mỗi chu kỳ. Đo được
(`docs/forex/04_ket_qua_cuoi_cung.md` §3), toàn bộ khả năng sống của chiến lược nằm
ở đúng một tham số KHÔNG nằm trong code:

    biên swap broker    ALL Sharpe   OOS Sharpe   phán quyết
    0,00 %/năm             0,880        0,780     tốt
    0,50 %/năm             0,728        0,587     dùng được
    1,00 %/năm             0,576        0,395     ranh giới
    2,00 %/năm             0,272        0,009     KHÔNG dùng được

Script này đọc `swap_long` / `swap_short` thật từ MT5 rồi tách phần biên broker ra
khỏi phần chênh lệch lãi suất, để trả lời dứt khoát: broker này có dùng được không.

CÁCH TÁCH BIÊN
==============
Với một cặp, nếu thị trường liên ngân hàng công bằng thì swap hai chiều phải đối
xứng: `swap_long ≈ −swap_short`. Broker phá vỡ đối xứng đó bằng cách cộng biên vào
CẢ HAI chiều, nên:

    biên (điểm/đêm) = −(swap_long + swap_short) / 2

Tổng hai chiều càng âm thì broker giữ càng nhiều. Phần đối xứng còn lại
`(swap_long − swap_short)/2` chính là chênh lệch lãi suất thật.

CHẠY
====
    .venv311\\Scripts\\python.exe scripts\\check_broker_swap.py

Yêu cầu: MT5 terminal đang mở và đã đăng nhập (xem HUONG_DAN_SETUP_MT5.md).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Ngưỡng phán quyết, lấy thẳng từ bảng độ nhạy đo được ở trên.
MARKUP_GOOD_PCT = 0.50       # <= mức này: dùng được thoải mái
MARKUP_MARGINAL_PCT = 1.00   # <= mức này: ranh giới, cần theo dõi sát
# > MARKUP_MARGINAL_PCT: không triển khai

# Quy ước MT5: SYMBOL_SWAP_MODE_POINTS = 0 (swap tính bằng điểm giá).
SWAP_MODE_POINTS = 0


def collect_swaps(symbols: List[str]) -> List[Dict[str, object]]:
    """Đọc swap thật từ MT5 và quy về %/năm cho từng cặp."""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        raise SystemExit(
            "Chưa cài MetaTrader5. Chạy:\n"
            "  .venv311\\Scripts\\python.exe -m pip install MetaTrader5")

    if not mt5.initialize():
        raise SystemExit(f"Không kết nối được MT5: {mt5.last_error()}\n"
                         "Mở MT5 terminal và đăng nhập trước khi chạy script này.")

    rows: List[Dict[str, object]] = []
    try:
        for sym in symbols:
            info = mt5.symbol_info(sym)
            if info is None:
                if not mt5.symbol_select(sym, True):
                    rows.append({"symbol": sym, "error": "không có trên broker này"})
                    continue
                info = mt5.symbol_info(sym)
            if info is None:
                rows.append({"symbol": sym, "error": "không đọc được symbol_info"})
                continue

            tick = mt5.symbol_info_tick(sym)
            price = float(tick.bid) if tick and tick.bid else float(info.bid or 0.0)
            if price <= 0:
                rows.append({"symbol": sym, "error": "không có giá"})
                continue

            sl, ss = float(info.swap_long), float(info.swap_short)
            point = float(info.point)

            # Quy swap về TỶ LỆ trên notional. Chỉ hỗ trợ chế độ POINTS —
            # các chế độ khác (theo %, theo tiền tệ) cần công thức riêng nên
            # báo rõ thay vì tính sai âm thầm.
            if int(getattr(info, "swap_mode", SWAP_MODE_POINTS)) != SWAP_MODE_POINTS:
                rows.append({"symbol": sym, "swap_long": sl, "swap_short": ss,
                             "error": f"swap_mode={info.swap_mode} chưa hỗ trợ"})
                continue

            long_pct_yr = sl * point / price * 365.0 * 100.0
            short_pct_yr = ss * point / price * 365.0 * 100.0
            markup_pct_yr = -(long_pct_yr + short_pct_yr) / 2.0
            rate_diff_pct_yr = (long_pct_yr - short_pct_yr) / 2.0

            rows.append({
                "symbol": sym,
                "swap_long_pts": round(sl, 3),
                "swap_short_pts": round(ss, 3),
                "long_%/yr": round(long_pct_yr, 3),
                "short_%/yr": round(short_pct_yr, 3),
                "markup_%/yr": round(markup_pct_yr, 3),
                "rate_diff_%/yr": round(rate_diff_pct_yr, 3),
                "swap_3day": int(getattr(info, "swap_rollover3days", -1)),
            })
    finally:
        mt5.shutdown()
    return rows


def verdict(mean_markup: float) -> str:
    if mean_markup <= MARKUP_GOOD_PCT:
        return ("✅ DÙNG ĐƯỢC — biên swap thấp. Kỳ vọng Sharpe gần mức 0,73 (ALL) "
                "trong bảng độ nhạy.")
    if mean_markup <= MARKUP_MARGINAL_PCT:
        return ("⚠️ RANH GIỚI — chiến lược còn dương nhưng Sharpe rơi về ~0,58 (ALL) "
                "/ ~0,40 (OOS). Nên tìm broker tốt hơn trước khi cấp vốn thật.")
    return ("❌ KHÔNG TRIỂN KHAI trên broker này — biên swap ăn hết edge. "
            "Tìm tài khoản raw/ECN có swap tốt hơn, hoặc tài khoản swap-free.")


def main() -> None:
    from src.python.shared import asset_profile as AP

    symbols = list(AP.FX_ALL)
    print("=" * 96)
    print("ĐO BIÊN SWAP THẬT CỦA BROKER — điều kiện tiên quyết để triển khai")
    print("=" * 96)
    rows = collect_swaps(symbols)

    ok = [r for r in rows if "error" not in r]
    bad = [r for r in rows if "error" in r]

    if ok:
        import pandas as pd
        df = pd.DataFrame(ok)
        pd.set_option("display.width", 200, "display.max_columns", 20)
        print(df.to_string(index=False))
        mean_markup = float(df["markup_%/yr"].mean())
        print()
        print(f"  BIÊN SWAP TRUNG BÌNH: {mean_markup:.3f} %/năm")
        print(f"  (cao nhất: {df.loc[df['markup_%/yr'].idxmax(), 'symbol']} "
              f"{df['markup_%/yr'].max():.3f}%  ·  "
              f"thấp nhất: {df.loc[df['markup_%/yr'].idxmin(), 'symbol']} "
              f"{df['markup_%/yr'].min():.3f}%)")
        print()
        print("  " + verdict(mean_markup))
        print()
        print("  Chạy lại backtest với con số THẬT này:")
        print(f"    from src.python.strategies.d1 import currency_carry as CY")
        print(f"    r = CR.backtest(broker_markup_pct={mean_markup:.3f})")
    if bad:
        print("\n  Cặp không đọc được:")
        for r in bad:
            print(f"    {r['symbol']}: {r['error']}")


if __name__ == "__main__":
    main()
