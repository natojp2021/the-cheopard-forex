"""log_cross_spread.py — ĐO spread THẬT của 28 công cụ, ghi CSV mỗi 30 phút.

VÌ SAO CẦN
==========
Giá của 21 cặp chéo trong backtest là CHÍNH XÁC (dựng bằng arbitrage tam giác từ hai
cặp USD, khớp tới từng pip). Nhưng **chi phí thì là ƯỚC LƯỢNG** — lấy từ bảng spread
công bố của broker raw-spread, không phải số đo trên tài khoản sẽ giao dịch:

    EURGBP 0,9 · EURJPY 1,0 · GBPJPY 1,8 · AUDJPY 1,3 · EURAUD 1,6 · EURCHF 1,3

Đó là giả định LỚN NHẤT còn lại của cả hệ. 22 trong 27 chân giao dịch cross, và chi
phí là nơi hệ này gần chết nhất: đo được Sharpe +0,216 sau spread+commission nhưng
**−0,456** sau khi cộng swap. Một ước lượng spread thấp hơn thực tế 2 lần đủ để đảo
dấu kết luận của vài chân.

Script này thay ước lượng bằng SỐ ĐO.

CÁCH ĐO — MỘT MẪU MỖI 30 PHÚT, KHÔNG PHẢI MỘT LẦN
==================================================
Spread FX thay đổi mạnh theo giờ: giãn gấp nhiều lần lúc giao ca Á–Âu và quanh tin.
Đo một lần lúc 15:00 London cho con số đẹp nhất trong ngày và vô dụng cho việc định
cỡ. Lấy mẫu đều 30 phút suốt tuần cho phân phối thật, và cái cần dùng để tính chi phí
là TRUNG VỊ theo giờ giao dịch của từng chân, không phải giá trị tốt nhất.

BẪY ĐÃ GẶP — PHẢI ĐỌC HAI LƯỢT
===============================
`symbol_select(sym, True)` trả `True` ngay nhưng terminal cần một khoảnh khắc mới
bơm giá. Đọc `symbol_info` ngay sau đó cho `ask = 0`, và lần đo trước đã mất 20/27
công cụ đúng vì lý do này. Nên: CHỌN hết trước, đợi, rồi mới ĐỌC hết.

CÁCH DÙNG
=========
    .\\.venv311\\Scripts\\python.exe scripts/log_cross_spread.py            # chạy liên tục
    .\\.venv311\\Scripts\\python.exe scripts/log_cross_spread.py --once     # đo một lượt
    .\\.venv311\\Scripts\\python.exe scripts/log_cross_spread.py --minutes 15

CSV nối thêm vào `reports/fx_recon/cross_spread_log.csv` — cứ để chạy cả tuần rồi
gửi lại file đó.
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd

from src.python.shared import asset_profile as AP

OUT_DIR = ROOT / "reports" / "fx_recon"
OUT_CSV = OUT_DIR / "cross_spread_log.csv"

# Thời gian chờ sau khi đưa symbol vào Market Watch, trước khi đọc giá. Xem "BẪY ĐÃ
# GẶP" ở đầu file — đọc sớm thì ask = 0 và công cụ đó biến mất khỏi bảng đo.
SELECT_SETTLE_SECONDS = 2.0

# Ước lượng spread đang dùng trong backtest (pip), để in cột chênh lệch.
# Nguồn: `src/python/research/fx_cross_pairs.py` phần docstring — bảng broker công bố.
ESTIMATED_PIPS: Dict[str, float] = {
    "EURUSD": 0.3, "GBPUSD": 0.5, "USDJPY": 0.4, "AUDUSD": 0.5,
    "USDCAD": 0.6, "USDCHF": 0.6, "NZDUSD": 0.8,
    "EURGBP": 0.9, "EURJPY": 1.0, "GBPJPY": 1.8, "AUDJPY": 1.3,
    "EURAUD": 1.6, "EURCHF": 1.3, "EURNZD": 2.0, "EURCAD": 1.5,
    "GBPAUD": 2.0, "GBPNZD": 2.5, "GBPCAD": 1.8, "GBPCHF": 1.6,
    "AUDNZD": 1.5, "AUDCAD": 1.3, "AUDCHF": 1.4, "NZDCAD": 1.6,
    "NZDCHF": 1.8, "NZDJPY": 1.5, "CADCHF": 1.5, "CADJPY": 1.4, "CHFJPY": 1.6,
}


def symbols() -> List[str]:
    """28 công cụ của rổ giao dịch: 7 major + 21 cross."""
    return list(AP.TRADED_ALL)


def measure(mt5, syms: List[str]) -> pd.DataFrame:
    """Một lượt đo. Chọn HẾT rồi mới đọc HẾT — xem bẫy ở đầu file."""
    for s in syms:
        try:
            mt5.symbol_select(s, True)
        except Exception:
            pass
    time.sleep(SELECT_SETTLE_SECONDS)

    now = datetime.now(timezone.utc)
    rows: List[Dict[str, object]] = []
    for s in syms:
        try:
            info = mt5.symbol_info(s)
            if info is None:
                rows.append({"timestamp_utc": now, "symbol": s, "bid": None,
                             "ask": None, "spread_price": None, "spread_pips": None,
                             "spread_bps": None, "note": "symbol_info trả None"})
                continue
            bid, ask = float(info.bid or 0.0), float(info.ask or 0.0)
            if bid <= 0 or ask <= 0:
                rows.append({"timestamp_utc": now, "symbol": s, "bid": bid,
                             "ask": ask, "spread_price": None, "spread_pips": None,
                             "spread_bps": None,
                             "note": "giá 0 — chưa bơm xong hoặc thị trường đóng"})
                continue
            sp = ask - bid
            mid = (ask + bid) / 2.0
            try:
                pip = AP.get(s).pip
            except Exception:
                pip = 0.01 if s.endswith("JPY") else 0.0001
            rows.append({
                "timestamp_utc": now, "symbol": s,
                "bid": round(bid, 6), "ask": round(ask, 6),
                "spread_price": round(sp, 6),
                "spread_pips": round(sp / pip, 3),
                "spread_bps": round(sp / mid * 1e4, 3),
                "note": "",
            })
        except Exception as exc:                           # pragma: no cover
            rows.append({"timestamp_utc": now, "symbol": s, "bid": None, "ask": None,
                         "spread_price": None, "spread_pips": None,
                         "spread_bps": None, "note": f"{type(exc).__name__}: {exc}"})
    return pd.DataFrame(rows)


def append_csv(df: pd.DataFrame, path: Path = OUT_CSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, mode="a", header=not path.exists(), index=False,
              encoding="utf-8")


def show(df: pd.DataFrame) -> None:
    """In bảng gọn để người vận hành copy gửi lại."""
    ok = df[df["spread_pips"].notna()].copy()
    bad = df[df["spread_pips"].isna()]

    if ok.empty:
        print("  KHÔNG đọc được công cụ nào — thị trường đóng, hoặc MT5 chưa đăng nhập.")
    else:
        ok["ước lượng"] = ok["symbol"].map(ESTIMATED_PIPS)
        ok["lệch"] = (ok["spread_pips"] - ok["ước lượng"]).round(2)
        ok["lệch %"] = ((ok["spread_pips"] / ok["ước lượng"] - 1) * 100).round(0)
        cols = ["symbol", "spread_pips", "ước lượng", "lệch", "lệch %", "spread_bps"]
        print(ok[cols].sort_values("lệch %", ascending=False).to_string(index=False))
        worse = int((ok["lệch"] > 0).sum())
        print(f"\n  {worse}/{len(ok)} công cụ có spread THẬT RỘNG HƠN ước lượng"
              f" · trung vị lệch {ok['lệch %'].median():+.0f}%")
    if len(bad):
        print(f"  {len(bad)} công cụ không đọc được: "
              f"{', '.join(bad['symbol'].tolist()[:10])}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Đo spread thật của rổ 28 công cụ")
    ap.add_argument("--once", action="store_true", help="đo một lượt rồi thoát")
    ap.add_argument("--minutes", type=float, default=30.0, help="chu kỳ đo (phút)")
    a = ap.parse_args()

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("CHƯA CÀI MetaTrader5. Chạy: .venv311\\Scripts\\pip install MetaTrader5")
        return

    from src.python.core.config import LOGIN, MT5_PATH, PASSWORD, SERVER
    from src.python.utils.env_loader import load_env_file

    load_env_file()
    kw = {"path": MT5_PATH} if MT5_PATH else {}
    ok = (mt5.initialize(login=LOGIN, password=PASSWORD, server=SERVER, **kw)
          if LOGIN else mt5.initialize(**kw))
    if not ok:
        print(f"KHÔNG kết nối được MT5: {mt5.last_error()}")
        print(f"  MT5_PATH = {MT5_PATH or '(trống — thư viện tự chọn terminal)'}")
        return

    syms = symbols()
    print(f"Đo spread {len(syms)} công cụ, mỗi {a.minutes:.0f} phút · "
          f"ghi vào {OUT_CSV.relative_to(ROOT)}")
    print("Ctrl+C để dừng. Cứ để chạy cả tuần rồi gửi lại file CSV.\n")

    try:
        while True:
            df = measure(mt5, syms)
            append_csv(df)
            print(f"═══ {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
            show(df)
            print()
            if a.once:
                break
            time.sleep(a.minutes * 60.0)
    except KeyboardInterrupt:
        print("\nđã dừng.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
