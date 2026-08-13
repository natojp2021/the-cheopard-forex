"""Vòng 11 — CÂU HỎI QUYẾT ĐỊNH: chiến lược có pass nổi FTMO $100k không?
Mô phỏng cửa sổ trượt trên chuỗi lợi nhuận thật, áp ĐÚNG luật FTMO."""
import sys, io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np, pandas as pd
from src.python.strategies.d1 import currency_carry as CY, currency_reversal as CR
from src.python.execution import portfolio_sizing as PS
from src.python.core.infra import ftmo
pd.set_option("display.width",250,"display.max_columns",30)

net,parts,W = CY.combined(start="2020-01-01", weight_reversal=0.5)
daily_vol_bps = float(net.std(ddof=1))
ann_vol = daily_vol_bps*np.sqrt(252)/100
ann_ret = float(net.mean())*252/100
cum=net.cumsum(); maxdd = float((cum.cummax()-cum).max())/100

print("="*112); print("A. HỒ SƠ CHIẾN LƯỢC Ở ĐÒN BẨY 1,0"); print("="*112)
print(f"  lợi nhuận {ann_ret:+.2f}%/năm · biến động {ann_vol:.2f}%/năm · MaxDD {maxdd:.2f}% · Calmar {ann_ret/maxdd:.3f}")
print()
print("  RÀNG BUỘC FTMO (docs/ftmo/ftmo.md):")
print(f"    MAX_LOSS_HARD    {ftmo.MAX_LOSS_HARD*100:.0f}%  = ${100_000*ftmo.MAX_LOSS_HARD:,.0f}  (mất tài khoản)")
print(f"    DAILY_LOSS_HARD  {ftmo.DAILY_LOSS_HARD*100:.0f}%  = ${100_000*ftmo.DAILY_LOSS_HARD:,.0f}")
print(f"    MAX_OPEN_RISK    {ftmo.MAX_OPEN_RISK*100:.0f}%")

print(); print("="*112); print("B. ĐÒN BẨY — bị chặn bởi cái gì?"); print("="*112)
for dd_budget in (4.0, 6.0, 8.0):
    lev_dd = PS.max_leverage_for_drawdown(maxdd, dd_budget)
    print(f"  ngân sách DD {dd_budget:.0f}%: đòn bẩy tối đa {lev_dd:.2f}x -> "
          f"lợi nhuận {ann_ret*lev_dd:+.2f}%/năm · vol {ann_vol*lev_dd:.2f}% · "
          f"open_risk {PS.open_risk_estimate(daily_vol_bps,lev_dd):.2f}%")

print(); print("="*112); print("C. MÔ PHỎNG FTMO — cửa sổ trượt, luật đầy đủ"); print("="*112)
print("  Phase 1: +10% trong tối đa 1 năm | Phase 2: +5% | vi phạm: DD ngày 5% hoặc tổng 10%")
def simulate(r, lev, target_pct, max_days=252):
    """Trả (pass, days, breach_reason). Mốc lỗ ngày tính lại theo balance đầu ngày."""
    eq = 100_000.0; peak_floor = 90_000.0
    for i,(t,x) in enumerate(r.items()):
        if i>=max_days: return False, i, "hết hạn"
        day_start = eq
        eq *= (1.0 + x*lev/1e4)
        if eq < peak_floor: return False, i, "MAX_LOSS 10%"
        if eq < day_start*(1-ftmo.DAILY_LOSS_HARD): return False, i, "DAILY_LOSS 5%"
        if eq >= 100_000*(1+target_pct): return True, i, "PASS"
    return False, max_days, "hết hạn"

for dd_budget,lev in [(4.0,PS.max_leverage_for_drawdown(maxdd,4.0)),
                      (6.0,PS.max_leverage_for_drawdown(maxdd,6.0)),
                      (8.0,PS.max_leverage_for_drawdown(maxdd,8.0))]:
    res=[]
    starts = range(0, len(net)-252, 21)
    for s in starts:
        r = net.iloc[s:]
        ok,d,why = simulate(r, lev, 0.10)
        res.append((ok,d,why))
    n=len(res); npass=sum(1 for x in res if x[0])
    breach=sum(1 for x in res if x[2].startswith(("MAX_LOSS","DAILY")))
    expire=sum(1 for x in res if x[2]=="hết hạn")
    md = np.median([x[1] for x in res if x[0]]) if npass else float('nan')
    print(f"  DD budget {dd_budget:.0f}% (lev {lev:.2f}x): {n} cửa sổ -> "
          f"PASS {npass/n:>5.1%} · VI PHẠM {breach/n:>5.1%} · hết hạn {expire/n:>5.1%}"
          + (f" · trung vị {md:.0f} ngày" if npass else ""))

print(); print("="*112); print("D. KẾT LUẬN SIZING THỰC TẾ"); print("="*112)
prices = {}
from src.python.shared import fx_data as D
for s in CR.PAIRS:
    prices[s] = float(D.daily_bars(s, start="2026-01-01")["close"].iloc[-1])
lev6 = PS.max_leverage_for_drawdown(maxdd, 6.0)
res = PS.size_portfolio(CR.pair_weights(W).iloc[-1], prices, daily_vol_bps=daily_vol_bps, max_dd_pct=maxdd,
                        equity_usd=100_000.0, target_vol_pct_annual=6.0, dd_budget_pct=6.0)
print(f"  đòn bẩy chọn: {res.leverage:.2f}x · vol ước tính {res.est_portfolio_vol_pct:.2f}%/năm")
print(f"  notional gộp: ${res.gross_notional_usd:,.0f} · open_risk {res.open_risk_pct:.2f}% · FTMO ok: {res.ftmo_ok}")
for n in res.notes: print(f"    ! {n}")
print()
for o in res.orders:
    if o.direction!="FLAT":
        print(f"    {o.symbol}  {o.direction:<4} {o.lots:>6.2f} lot  ${o.notional_usd:>10,.0f}  (w={o.weight:+.4f})")
