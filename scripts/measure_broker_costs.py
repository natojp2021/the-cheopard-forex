"""measure_broker_costs.py — ĐO CHI PHÍ THẬT trên MT5. Cổng go/no-go của toàn hệ.

VÌ SAO SCRIPT NÀY QUYẾT ĐỊNH MỌI THỨ
=====================================
Mọi con số Sharpe trong dự án đứng trên HAI GIẢ ĐỊNH chưa từng đo:

  1. **Spread của 20 cross** lấy từ bảng công bố của broker (`TYPICAL_SPREAD_PIPS`),
     không phải đo từ luồng giá. Dữ liệu lịch sử `D:/data-ticks-train` chỉ có 7 cặp
     vs USD, không có chuỗi cross nào.
  2. **Biên swap broker 1,0%/năm.** Đây là lớp chi phí LỚN NHẤT đo được (1,457%/năm
     so với spread 0,355 và chênh lệch lãi suất 0,184). Ở 2,0%/năm phần lớn chiến
     lược về ~0; ở 3,0%/năm danh mục âm.

Script này đo cả hai từ terminal thật và ghi ra `reports/broker_costs.json`.

CÁCH ĐỌC KẾT QUẢ
================
    spread thật < ước lượng  → mọi biên hoà vốn RỘNG hơn báo cáo, chiến lược an toàn hơn
    spread thật > ước lượng  → phải chạy lại toàn bộ, và những ô sát ngưỡng sẽ rụng
    biên swap > 2,0%/năm     → ĐỔI BROKER, không có cách nào khác

BIÊN SWAP TÍNH NHƯ THẾ NÀO
==========================
Broker công bố swap long và swap short riêng. Chênh lệch lãi suất thật nằm ở HIỆU của
chúng; phần broker ăn nằm ở TRUNG BÌNH:

    biên broker (điểm/đêm) = −(swap_long + swap_short) / 2

Nếu thị trường công bằng thì swap_long = −swap_short và trung bình bằng 0. Trung bình
âm là phần broker giữ lại — trả trên CẢ hai chiều, nên không thể né bằng cách chọn chiều.

⚠️ SỐ ĐO ĐƯỢC LÀ CỦA TÀI KHOẢN ĐANG ĐĂNG NHẬP. Tài khoản demo MetaQuotes có điều kiện
KHÁC tài khoản FTMO thật — số đo trên demo là chỉ dấu, không phải kết luận. Phải chạy
lại trên chính tài khoản sẽ giao dịch trước khi cấp vốn.
"""
from __future__ import annotations

import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import numpy as np
import pandas as pd

from src.python.research import fx_cross_pairs as CP
from src.python.shared import asset_profile as AP
from src.python.shared import carry_costs as CC

OUT = ROOT / "reports"
SAMPLE_SECONDS = 60          # thời gian lấy mẫu tick cho spread tức thời
TICK_BARS = 20_000           # số tick lịch sử dùng cho spread trung vị


def resolve_symbol(mt5, want: str) -> Optional[str]:
    """Tìm tên symbol thật trên broker — nhiều broker gắn hậu tố (.raw, m, _ecn…)."""
    if mt5.symbol_info(want) is not None:
        return want
    for s in mt5.symbols_get():
        n = s.name
        if n.upper().startswith(want.upper()) and len(n) <= len(want) + 5:
            return n
    return None


def measure_spread(mt5, sym: str, n_ticks: int = TICK_BARS) -> Dict[str, float]:
    """Spread từ tick lịch sử — trung vị và các phân vị.

    Dùng trung vị chứ không dùng trung bình: phân phối spread có đuôi phải rất dày
    (tin tức, giao phiên), và trung bình bị vài phần trăm số tick kéo lệch.
    """
    now = datetime.now(timezone.utc)
    ticks = mt5.copy_ticks_from(sym, now, n_ticks, mt5.COPY_TICKS_ALL)
    if ticks is None or len(ticks) == 0:
        return {}
    t = pd.DataFrame(ticks)
    t = t[(t["ask"] > 0) & (t["bid"] > 0)]
    if t.empty:
        return {}
    sp = (t["ask"] - t["bid"]).to_numpy()
    mid = ((t["ask"] + t["bid"]) / 2.0).to_numpy()
    bps = sp / mid * 1e4
    return {"n_ticks": int(len(t)),
            "spread_price_med": float(np.median(sp)),
            "spread_bps_med": float(np.median(bps)),
            "spread_bps_p25": float(np.percentile(bps, 25)),
            "spread_bps_p75": float(np.percentile(bps, 75)),
            "spread_bps_p95": float(np.percentile(bps, 95)),
            "mid": float(np.median(mid))}


def measure_swap(mt5, sym: str) -> Dict[str, float]:
    """Swap long/short từ đặc tả symbol, quy sang %/năm và tách biên broker."""
    info = mt5.symbol_info(sym)
    if info is None:
        return {}
    sl, ss = float(info.swap_long), float(info.swap_short)
    mode = int(info.swap_mode)
    mid = float(info.bid + info.ask) / 2.0 if info.ask > 0 else float(info.bid)
    point = float(info.point)
    contract = float(info.trade_contract_size)

    # Quy swap sang %/năm trên notional. `swap_mode` quyết định đơn vị:
    #   1 = điểm · 2 = tiền tệ cơ sở · 3 = lãi suất · 5/6 = phần trăm/năm
    if mode == 5 or mode == 6:
        pct_long, pct_short = sl, ss
    elif mode == 1 and mid > 0:
        pct_long = sl * point / mid * 365.0 * 100.0
        pct_short = ss * point / mid * 365.0 * 100.0
    elif mode == 2 and mid > 0 and contract > 0:
        pct_long = sl / (contract * mid) * 365.0 * 100.0
        pct_short = ss / (contract * mid) * 365.0 * 100.0
    else:
        pct_long = pct_short = float("nan")

    # Biên broker = phần bị giữ lại trên CẢ hai chiều
    markup = -(pct_long + pct_short) / 2.0 if np.isfinite(pct_long) else float("nan")
    return {"swap_long_raw": sl, "swap_short_raw": ss, "swap_mode": mode,
            "swap_long_pct_year": pct_long, "swap_short_pct_year": pct_short,
            "broker_markup_pct_year": markup,
            "point": point, "contract": contract, "digits": int(info.digits)}


def main() -> int:
    import MetaTrader5 as mt5

    if not mt5.initialize():
        print(f"KHÔNG kết nối được MT5: {mt5.last_error()}")
        return 1
    ti, ai = mt5.terminal_info(), mt5.account_info()
    print(f"Terminal: {ti.company} · kết nối {ti.connected}")
    print(f"Tài khoản: {ai.login} @ {ai.server} ({ai.currency})")
    if "demo" in str(ai.server).lower() or ai.trade_mode == 0:
        print("⚠️  TÀI KHOẢN DEMO — điều kiện KHÁC tài khoản FTMO thật. Số đo dưới đây "
              "là chỉ dấu, PHẢI chạy lại trên tài khoản sẽ giao dịch.")
    print()

    majors = list(AP.FX_ALL)
    crosses = [d[0] for d in CP.CROSS_DEFS]
    rows: List[Dict] = []

    for want in majors + crosses:
        sym = resolve_symbol(mt5, want)
        if sym is None:
            rows.append({"muốn": want, "symbol": None, "trạng thái": "KHÔNG CÓ"})
            print(f"  {want}: broker KHÔNG có symbol này")
            continue
        if not mt5.symbol_select(sym, True):
            rows.append({"muốn": want, "symbol": sym, "trạng thái": "KHÔNG BẬT ĐƯỢC"})
            continue
        time.sleep(0.05)
        sp = measure_spread(mt5, sym)
        sw = measure_swap(mt5, sym)
        est = (CP.TYPICAL_SPREAD_PIPS.get(want)
               if want in crosses else None)
        row = {"muốn": want, "symbol": sym,
               "loại": "major" if want in majors else "cross",
               "trạng thái": "OK" if sp else "KHÔNG CÓ TICK", **sp, **sw}
        if est is not None and sp:
            pip = 0.01 if want.endswith("JPY") else 0.0001
            row["spread_ước_pip"] = est
            row["spread_thật_pip"] = sp["spread_price_med"] / pip
            row["tỷ_lệ_thật/ước"] = row["spread_thật_pip"] / est
        rows.append(row)
        if sp:
            print(f"  {want:8s} → {sym:12s} spread {sp['spread_bps_med']:5.2f} bps "
                  f"(p95 {sp['spread_bps_p95']:5.2f}) · biên swap "
                  f"{sw.get('broker_markup_pct_year', float('nan')):6.3f} %/năm")

    T = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    T.to_csv(OUT / "broker_costs.csv", index=False)

    ok = T[T["trạng thái"] == "OK"]
    print()
    print("=" * 110)
    print("A. SPREAD THẬT so với ƯỚC LƯỢNG đang dùng trong backtest")
    print("=" * 110)
    cr = ok[(ok["loại"] == "cross") & ok.get("tỷ_lệ_thật/ước").notna()] \
        if "tỷ_lệ_thật/ước" in ok else pd.DataFrame()
    if len(cr):
        print(cr[["muốn", "spread_ước_pip", "spread_thật_pip", "tỷ_lệ_thật/ước",
                  "spread_bps_med"]].round(3).to_string(index=False))
        r = float(cr["tỷ_lệ_thật/ước"].median())
        print(f"\n  Tỷ lệ trung vị thật/ước = {r:.3f}  → "
              + ("spread THẬT RẺ HƠN ước lượng, mọi biên hoà vốn RỘNG hơn báo cáo"
                 if r < 1 else
                 "spread THẬT ĐẮT HƠN ước lượng — PHẢI chạy lại toàn bộ backtest"))

    print()
    print("=" * 110)
    print("B. BIÊN SWAP BROKER — cổng go/no-go")
    print("=" * 110)
    mk = ok["broker_markup_pct_year"].dropna()
    if len(mk):
        print(f"  trung vị {mk.median():.3f} %/năm · p25 {mk.quantile(.25):.3f} · "
              f"p75 {mk.quantile(.75):.3f} · max {mk.max():.3f}")
        print(f"  giả định đang dùng trong backtest: "
              f"{CC.DEFAULT_BROKER_MARKUP_PCT:.1f} %/năm")
        m = float(mk.median())
        verdict = ("ĐẠT — thấp hơn giả định, kết quả backtest là BI QUAN"
                   if m <= CC.DEFAULT_BROKER_MARKUP_PCT else
                   "CẢNH BÁO — cao hơn giả định, phải chạy lại độ nhạy"
                   if m <= 2.0 else
                   "KHÔNG ĐẠT — biên > 2,0%/năm thì phần lớn chiến lược về 0. ĐỔI BROKER")
        print(f"  → {verdict}")

    js = {"đo_lúc": datetime.now(timezone.utc).isoformat(),
          "terminal": ti.company, "server": ai.server, "login": int(ai.login),
          "là_demo": bool("demo" in str(ai.server).lower()),
          "spread_bps_med": {r["muốn"]: r.get("spread_bps_med")
                             for _, r in ok.iterrows()},
          "broker_markup_pct_year": {r["muốn"]: r.get("broker_markup_pct_year")
                                     for _, r in ok.iterrows()}}
    (OUT / "broker_costs.json").write_text(
        json.dumps(js, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nđã ghi {OUT / 'broker_costs.csv'} và broker_costs.json")
    mt5.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
