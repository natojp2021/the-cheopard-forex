import sys, time, traceback, pathlib
sys.path.insert(0, ".")
out = pathlib.Path("scratch/probe.txt")
lines = []
def w(m):
    lines.append(f"{time.strftime('%H:%M:%S')} {m}")
    out.write_text("\n".join(lines), encoding="utf-8")
try:
    w("A import engine")
    from src.python.core.engine import TradingEngine
    w("B tao engine")
    e = TradingEngine(log_callback=lambda m: w(f"LOG> {m[:70]}"))
    w("C read_broker")
    e._read_broker()
    w(f"D mt5_connected={e.state['mt5_connected']} err={e.state['positions_read_error'][:50]}")
    w("E read_guards")
    e._read_guards()
    w(f"F guards={list(e.state['guards'])}")
    w("G read_portfolio")
    e._maybe_read_portfolio()
    w(f"H portfolio={e.state['portfolio'].get('sharpe_all')}")
except Exception:
    w("LOI:\n" + traceback.format_exc())
