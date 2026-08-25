"""asia_sweep_calibrate.py — Vòng 73. Hiệu chỉnh TẦN SUẤT của chiến lược Asia Sweep.

MỤC ĐÍCH DUY NHẤT: đo tần suất và kỳ vọng của bộ luật SẢN XUẤT để điền số THẬT vào
thẻ luật. Chủ tài khoản yêu cầu **4-8 lệnh/tuần** trên rổ ba cặp phổ thông.

Script này KHÔNG quét tìm tham số tốt nhất theo lợi nhuận. Ngưỡng lấy nguyên từ bảng
§III của `docs/the-asia-sweep/H1_INDUCEMENT_SWEEP_SPEC.md`; chỗ đặc tả không có số
(USDJPY) thì suy theo ĐÚNG tỷ lệ mà đặc tả dùng cho hai cặp kia so với biên Á trung
vị đo được — một phép quy đổi đơn vị, không phải một bậc tự do.

    biên Á trung vị đo được   EURUSD 25,3 pip · GBPUSD 32,8 · USDJPY 45,3
    dải của đặc tả            EURUSD 15-45 = [0,59; 1,78] x trung vị
                              GBPUSD 20-55 = [0,61; 1,68] x trung vị
    suy ra cho USDJPY         27-80 pip     = [0,60; 1,77] x trung vị

Chạy trên CÙNG đường code với live (`asia_sweep_core.run`) — xem ghi chú "một đường
code" ở đầu module đó.
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import pandas as pd

from src.python.shared import fx_data as D
from src.python.strategies import asia_sweep_core as SC

pd.set_option("display.width", 250, "display.max_columns", 40,
              "display.max_rows", 300)

OUT = ROOT / "reports" / "fx_research"
FORM_END = pd.Timestamp("2024-01-01")

CONFIGS = {
    "EURUSD": SC.SweepConfig(
        name="AsiaSweepEURUSD", instrument="EURUSD",
        range_min_pips=15.0, range_max_pips=45.0,
        depth_min_pips=2.0, depth_max_pips=25.0,
        sl_buffer_pips=3.0, min_rr=3.0),
    "GBPUSD": SC.SweepConfig(
        name="AsiaSweepGBPUSD", instrument="GBPUSD",
        range_min_pips=20.0, range_max_pips=55.0,
        depth_min_pips=3.0, depth_max_pips=35.0,
        sl_buffer_pips=4.0, min_rr=3.5),
    "USDJPY": SC.SweepConfig(
        name="AsiaSweepUSDJPY", instrument="USDJPY",
        range_min_pips=27.0, range_max_pips=80.0,
        depth_min_pips=3.0, depth_max_pips=35.0,
        sl_buffer_pips=4.0, min_rr=3.0),
}


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, object]] = []
    allT: List[pd.DataFrame] = []
    funnel: List[pd.Series] = []

    for sym, cfg in CONFIGS.items():
        with D.parquet_only():
            m1 = D.load_m1(sym)
        res = SC.run(m1, cfg)
        st = SC.stats(res)
        rows.append(st)
        if len(res.trades):
            allT.append(res.trades)
        f = res.decisions["state"].value_counts()
        f.name = sym
        funnel.append(f)
        print(f"{sym}: {st['n']} lệnh · {st['lệnh/tuần']} lệnh/tuần")

    print()
    print("=" * 150)
    print("A. PHỄU LOẠI — mỗi phiên dừng ở đâu")
    print("=" * 150)
    F = pd.concat(funnel, axis=1).fillna(0).astype(int)
    F.loc["TỔNG"] = F.sum()
    print(F.to_string())

    print()
    print("=" * 150)
    print("B. KẾT QUẢ TỪNG CẶP — bộ luật đặc tả, chi phí thật, cùng đường code với live")
    print("=" * 150)
    S = pd.DataFrame(rows).set_index("instrument")
    print(S.drop(columns=["phân bố kết cục", "phiên bị loại"]).to_string())
    print()
    for r in rows:
        print(f"  {r['instrument']}: {r['phân bố kết cục']}")

    T = pd.concat(allT, ignore_index=True)
    T.to_csv(OUT / "asia_sweep_prod_trades.csv", index=False, encoding="utf-8-sig")

    print()
    print("=" * 150)
    print("C. GỘP RỔ BA CẶP — con số đi vào thẻ luật")
    print("=" * 150)
    years = max((T["session"].max() - T["session"].min()).days / 365.25, 1e-9)
    r = T["r_net"]
    print(f"   mẫu            {T['session'].min().date()} -> {T['session'].max().date()}"
          f"  ({years:.1f} năm)")
    print(f"   số lệnh        {len(T)}")
    print(f"   TẦN SUẤT       {len(T) / (years * 52.0):.2f} lệnh/tuần "
          f"(mục tiêu 4-8)")
    print(f"   winrate        {100.0 * (r > 0).mean():.2f}%")
    print(f"   R:R TV (TP2)   {T['rr2'].median():.2f}")
    print(f"   SL pip TV      {T['sl_pips'].median():.1f}")
    print(f"   phí R TV       {T['cost_r'].median():.3f}")
    print(f"   R gộp/lệnh     {T['r_gross'].mean():+.4f}")
    print(f"   R ròng/lệnh    {r.mean():+.4f}")
    print(f"   t ròng         {r.mean() / r.std(ddof=1) * len(r) ** 0.5:+.2f}")
    print(f"   R ròng tổng    {r.sum():+.1f}")

    print()
    print("   FORM (< 2024-01-01) / OOS:")
    for lab, sub in (("FORM", T[T["session"] < FORM_END]),
                     ("OOS ", T[T["session"] >= FORM_END])):
        if not len(sub):
            continue
        rr = sub["r_net"]
        print(f"     {lab}  n={len(sub):4d} · thắng {100.0 * (rr > 0).mean():5.2f}% "
              f"· R ròng {rr.mean():+.4f} · tổng {rr.sum():+.1f}")

    print()
    print("=" * 150)
    print("D. QUY RA TIỀN — tài khoản FTMO $100.000, đối chiếu hạn mức")
    print("=" * 150)
    for risk_pct in (0.25, 0.50, 1.00):
        eq = 100_000.0
        per_r = eq * risk_pct / 100.0
        # đường vốn theo THỨ TỰ THỜI GIAN của rổ, để đọc được MaxDD thật
        s = T.sort_values("t_entry")
        curve = eq + (s["r_net"].cumsum() * per_r)
        peak = curve.cummax()
        dd = (curve - peak) / eq * 100.0
        # DD so với BALANCE BAN ĐẦU TĨNH — đúng luật FTMO, không neo đỉnh
        dd_static = (curve - eq) / eq * 100.0
        print(f"   rủi ro {risk_pct:.2f}%/lệnh (${per_r:,.0f}/R):")
        print(f"      số dư cuối   ${curve.iloc[-1]:,.0f}  "
              f"({(curve.iloc[-1] / eq - 1) * 100:+.2f}%)")
        print(f"      MaxDD từ đỉnh {dd.min():+.2f}%  ·  đáy so với vốn ban đầu "
              f"{dd_static.min():+.2f}%  (sàn nội bộ -9,00% · luật FTMO -10,00%)")
        print(f"      chuỗi thua dài nhất "
              f"{int((s['r_net'] < 0).groupby((s['r_net'] >= 0).cumsum()).sum().max())}"
              f" lệnh")

    print()
    print(f"xong trong {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
