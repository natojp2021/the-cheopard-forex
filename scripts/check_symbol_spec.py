"""Kiểm tra broker thực sự dùng `contract_size` hay `tick_value/tick_size`.

    python scripts/check_symbol_spec.py [SYMBOL]        # mặc định XAUUSD

Vì sao cần: chọn sai nguồn thì `loss_per_lot` lệch 10 lần, tức MỌI cỡ lệnh lệch
10 lần theo đúng tỷ lệ đó — xem `core/infra/symbol_spec.py::loss_per_lot`.
Chạy lại sau mỗi lần đổi broker/tài khoản.

KHÔNG ĐẶT LỆNH NÀO. Hai phép đo độc lập, cả hai chỉ ĐỌC:

  A. `order_calc_profit()` — chính terminal/broker tính lãi cho một lệnh GIẢ ĐỊNH.
     Đây là câu trả lời có thẩm quyền: nếu 1 lot đi đúng 1,00 USD giá cho ra
     100 USD thì `contract_size` đúng; nếu cho 10 USD thì `tick_value` đúng.
  B. `history_deals_get()` — tính lại hệ số ẩn từ MỌI lệnh đã đóng:
     |profit| / (|Δgiá| × volume). Chứng cứ nhiều mẫu, không phải n=1.
"""
import sys
from datetime import datetime, timedelta

import MetaTrader5 as mt5

SYM = sys.argv[1] if len(sys.argv) > 1 else "XAUUSD"

if not mt5.initialize():
    print("initialize FAIL:", mt5.last_error())
    sys.exit(1)

ai = mt5.account_info()
print(f"Tài khoản: {ai.login} @ {ai.server}  (leverage 1:{ai.leverage})")
mt5.symbol_select(SYM, True)
si = mt5.symbol_info(SYM)
if si is None:
    print(f"Không có symbol {SYM}"); mt5.shutdown(); sys.exit(1)

tv, ts, cs = si.trade_tick_value, si.trade_tick_size, si.trade_contract_size
by_tick = (tv / ts) if ts else float("nan")
print(f"\n--- Broker khai gì cho {SYM} ---")
print(f"  trade_tick_value    = {tv}")
print(f"  trade_tick_size     = {ts}")
print(f"  trade_contract_size = {cs}")
print(f"  => theo tick_value/tick_size : {theo_tick:.2f} USD / 1 USD giá / lot")
print(f"  => theo contract_size        : {cs:.2f} USD / 1 USD giá / lot")
print(f"  LỆCH: {abs(theo_tick - cs) / cs * 100:.0f}%" if cs else "")

# ---- A. order_calc_profit: broker tự tính, KHÔNG đặt lệnh ----
tick = mt5.symbol_info_tick(SYM)
p0 = float(tick.ask)
p1 = p0 + 1.0                      # đi đúng 1,00 USD giá
profit = mt5.order_calc_profit(mt5.ORDER_TYPE_BUY, SYM, 1.0, p0, p1)
print(f"\n--- A. order_calc_profit (1 lot, {p0:.2f} -> {p1:.2f}, +1,00 USD giá) ---")
if profit is None:
    print("  order_calc_profit trả None:", mt5.last_error())
else:
    print(f"  Broker tính lãi = {lai:.4f} USD")
    if abs(profit - cs) < abs(profit - by_tick):
        print(f"  ==> KHỚP contract_size ({cs:.0f}). Code ĐANG DÙNG ĐÚNG.")
    else:
        print(f"  ==> KHỚP tick_value/tick_size ({theo_tick:.0f}). "
              f"*** CODE ĐANG SAI — cỡ lệnh lệch {cs / theo_tick:.0f} lần ***")

# ---- B. tính lại từ MỌI lệnh đã đóng ----
print(f"\n--- B. Hệ số ẩn từ lệnh ĐÃ ĐÓNG (900 ngày) ---")
deals = mt5.history_deals_get(datetime.now() - timedelta(days=900), datetime.now())
if not deals:
    print("  Không có lịch sử deal nào trên tài khoản này.")
else:
    by_position = {}
    for d in deals:
        if d.symbol != SYM or d.entry not in (0, 1):   # 0=IN, 1=OUT
            continue
        by_position.setdefault(d.position_id, []).append(d)
    weight = []
    for pid, ds in by_position.items():
        entered = [d for d in ds if d.entry == 0]
        ra = [d for d in ds if d.entry == 1]
        if not entered or not ra:
            continue
        v = entered[0].volume
        dg = abs(ra[-1].price - entered[0].price)
        pnl = abs(sum(d.profit for d in ra))
        if v > 0 and dg > 1e-9 and pnl > 1e-9:
            weight.append(pnl / (dg * v))
    if not weight:
        print("  Không có vị thế đóng nào đủ dữ liệu để tính.")
    else:
        weight.sort()
        midpoint = weight[len(weight) // 2]
        print(f"  n = {len(weight)} vị thế · trung vị hệ số = {giua:.2f} "
              f"USD / 1 USD giá / lot")
        print(f"  (min {min(weight):.2f} · max {max(weight):.2f})")
        print(f"  ==> {'KHỚP contract_size' if abs(giua - cs) < abs(giua - theo_tick) else '*** KHỚP tick_value — CODE SAI ***'}")

mt5.shutdown()
