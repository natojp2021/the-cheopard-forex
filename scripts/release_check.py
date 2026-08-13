# -*- coding: utf-8 -*-
"""RELEASE CHECK — một lệnh xác thực hệ thống trước khi triển khai:

    .venv311\\Scripts\\python.exe scripts/release_check.py

Mã thoát 0 = SẴN SÀNG.

BÀI HỌC MANG SANG TỪ HỆ XAUUSD: MỘT CỔNG LUÔN ĐỎ KHÔNG CÒN LÀ CỔNG
===================================================================
Bản `release_check.py` bên đó từng luôn đỏ vì ba lý do lỗi thời — trỏ vào thư mục
test không tồn tại, biên dịch một file đã đổi tên, và dùng một script `ONE_OFF`
đối chiếu lại báo cáo cũ làm cổng thường trực. Một cổng luôn đỏ thì bị bỏ qua,
cùng hội chứng với một test không bao giờ đỏ, chỉ khác đầu.

Nên ở đây MỌI danh sách đều DẪN XUẤT, không gõ tay:
  · module biên dịch = quét `src/python/**/*.py`, trừ các nhánh cố ý không nạp được
  · test = cả thư mục `tests/`

Danh sách gõ tay là danh sách sẽ thiếu đúng file mới nhất — nơi lỗi dễ xảy ra nhất.

BỐN BƯỚC, THEO THỨ TỰ RẺ → ĐẮT
===============================
  1. BIÊN DỊCH        — bắt lỗi cú pháp trong một giây, trước khi tốn hai phút test
  2. IMPORT ĐƯỜNG LIVE — biên dịch được KHÔNG có nghĩa import được; đúng lỗ hổng đã
                        để `position_execution_service` hỏng âm thầm suốt nhiều ngày
  3. BẤT BIẾN RỦI RO   — bốn hằng số FTMO phải đúng bằng giá trị ĐÃ ĐO. Đây là bước
                        KHÔNG có ở bản XAU, và nó là bước quan trọng nhất: một lần
                        nới `LEVERAGE_MAX` hay `DD_SELF_CAP` mà quên đo lại là mất
                        tài khoản, mà không test nào khác bắt được
  4. TEST              — toàn bộ `tests/`
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Nhánh KHÔNG biên dịch, kèm lý do — danh sách loại trừ phải tự giải thích được,
# nếu không nó sẽ phình ra mỗi lần có file hỏng.
SKIP_DIRS = (
    "__pycache__",
)


def _modules() -> list:
    """Mọi file `.py` dưới `src/python`. QUÉT, không gõ tay."""
    out = []
    for p in sorted((ROOT / "src" / "python").rglob("*.py")):
        if any(s in p.parts for s in SKIP_DIRS):
            continue
        out.append(str(p.relative_to(ROOT)))
    return out


# Module PHẢI import được — không chỉ biên dịch được.
#
# Biên dịch chỉ kiểm cú pháp. `position_execution_service.py` biên dịch sạch suốt
# nhiều ngày trong khi import của nó ném `ImportError` vì ba module không tồn tại,
# và nút break-even trên giao diện im lặng hỏng vì `except` nuốt mất. Bước này bắt
# đúng lớp lỗi đó.
LIVE_IMPORTS = [
    "src.python.core.engine",
    "src.python.live_server",
    "src.python.ops_ctl",
    # THAY 19/08/2026 cho `gui_command_center` (đã xoá cùng đợt chuyển console-only).
    # Ba module dưới là đường TRÌNH BÀY mới, và chúng phải nằm trong danh sách này
    # chứ không chỉ được biên dịch: `ops_view` import registry + config + asset
    # profile, `ops_console` import rich + ops_log. Một trong số đó vỡ thì bot khởi
    # động rồi chết ngay ở dòng dựng console — tức không quan sát được gì, đúng lớp
    # lỗi mà bước này sinh ra để bắt.
    "src.python.core.ops_console",
    "src.python.core.ops_theme",
    "src.python.core.ops_view",
    "src.python.utils.ops_log",
    "src.python.core.runtime_meta",
    "src.python.core.infra.ftmo",
    "src.python.core.infra.ftmo_guard",
    "src.python.core.infra.risk_guard",
    "src.python.core.infra.mt5_bridge",
    "src.python.core.infra.target_mode",
    "src.python.core.broker.circuit_breaker",
    "src.python.core.broker.order_state_machine",
    "src.python.core.intelligence.strategy_scoring",
    "src.python.execution.order_plan",
    "src.python.execution.order_router",
    "src.python.execution.entry_gate",
    "src.python.execution.ftmo_leverage_policy",
    "src.python.execution.disaster_stop",
    "src.python.execution.portfolio_sizing",
    "src.python.execution.position_book",
    "src.python.execution.exit_manager",
    "src.python.execution.trading_control",
    "src.python.shared.notifications.emails",
    "src.python.shared.notifications.session_report",
    "src.python.strategies.portfolio",
    "src.python.strategies.registry",
    "src.python.strategies.rulebook",
    "src.python.utils.alerts",
    "src.python.utils.mailer",
    "src.python.utils.timeline_log",
]

_IMPORT_PROBE = (
    "import sys;"
    "sys.path.insert(0, r'{root}');"
    "mods = {mods!r};"
    "bad = [];"
    "\nfor m in mods:\n"
    "    try:\n"
    "        __import__(m)\n"
    "    except Exception as e:\n"
    "        bad.append(f'{{m}}: {{type(e).__name__}}: {{e}}')\n"
    "print(f'{{len(mods) - len(bad)}}/{{len(mods)}} module import được')\n"
    "for b in bad:\n"
    "    print('  KHONG IMPORT DUOC ' + b)\n"
    "sys.exit(1 if bad else 0)\n"
)

# BẤT BIẾN RỦI RO — mỗi con số là một GIÁ TRỊ ĐÃ ĐO, không phải một lựa chọn.
#
#   DD_SELF_CAP   0,09  sàn nội bộ, chặt hơn luật FTMO 10%. Đo được: 4,85x cho
#                       MaxDD 10,74% = VI PHẠM.
#   LEVERAGE_MAX  6,0   đòn bẩy THỰC bão hoà ở 5,25x — trên mức đó trần cứng
#                       hết tác dụng, ràng buộc ĐUÔI chặn trước.
#   TAIL_BUFFER   1,2   bậc cuối trước ĐIỂM GÃY: 1,1 làm 23,5% cửa sổ bị cắt.
#   DAILY_LOSS_HARD 0,05 / MAX_LOSS_HARD 0,10   luật gốc FTMO, neo `docs/ftmo/ftmo.md`.
#   PER_POSITION_BUDGET_PCT 2,0  ngân sách cầu chì mỗi vị thế.
#
# Bốn số này là HÀM CỦA DANH MỤC HIỆN TẠI. Thêm hay bớt một chân là phải đo lại.
# Bước này không cho phép ai nới chúng bằng một dòng sửa lặng lẽ.
_INVARIANT_PROBE = """
import sys
sys.path.insert(0, r'{root}')
from src.python.core.infra import ftmo
from src.python.execution import ftmo_leverage_policy as POL
from src.python.execution import disaster_stop as DS

EXPECT = [
    ("ftmo.DAILY_LOSS_HARD", ftmo.DAILY_LOSS_HARD, 0.05),
    ("ftmo.MAX_LOSS_HARD", ftmo.MAX_LOSS_HARD, 0.10),
    ("policy.DD_SELF_CAP", POL.DD_SELF_CAP, 0.09),
    ("policy.LEVERAGE_MAX", POL.LEVERAGE_MAX, 6.0),
    ("policy.TAIL_BUFFER", POL.TAIL_BUFFER, 1.2),
    ("disaster_stop.PER_POSITION_BUDGET_PCT", DS.PER_POSITION_BUDGET_PCT, 2.0),
]
bad = []
for name, got, want in EXPECT:
    if abs(float(got) - want) > 1e-9:
        bad.append(f"{{name}} = {{got}} (phai la {{want}})")

# Sàn nội bộ PHẢI chặt hơn luật, không được bằng.
if POL.DD_SELF_CAP >= ftmo.MAX_LOSS_HARD:
    bad.append(f"DD_SELF_CAP {{POL.DD_SELF_CAP}} khong con chat hon "
               f"MAX_LOSS_HARD {{ftmo.MAX_LOSS_HARD}}")

# Đệm cạn PHẢI trả 0, không phải một mức sàn dương.
d = POL.decide(90500.0, 100000.0, 9.33, worst_day_bps=79.4)
if d.leverage != 0.0:
    bad.append(f"equity cham san noi bo van cap don bay {{d.leverage}} (phai la 0)")

print(f"{{len(EXPECT) - len(bad)}}/{{len(EXPECT)}} bat bien rui ro dung")
for b in bad:
    print("  SAI: " + b)
sys.exit(1 if bad else 0)
"""

STEPS = [
    ("BIÊN DỊCH MỌI MODULE", None),         # dựng ở `main` vì danh sách dài
    ("IMPORT ĐƯỜNG LIVE",
     [PY, "-c", _IMPORT_PROBE.format(root=str(ROOT), mods=LIVE_IMPORTS)]),
    ("BẤT BIẾN RỦI RO FTMO",
     [PY, "-c", _INVARIANT_PROBE.format(root=str(ROOT))]),
    ("UNIT + PARITY + SAFEGUARD",
     [PY, "-m", "pytest", "tests/", "-q", "--tb=short"]),
]


def main() -> int:
    import os

    os.environ["PYTHONIOENCODING"] = "utf-8"
    mods = _modules()
    steps = [(n, c if c else [PY, "-m", "py_compile", *mods]) for n, c in STEPS]

    fails = []
    for name, cmd in steps:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "").strip().splitlines()
        tail = out[-1] if out else "(không có đầu ra)"
        # Chỉ tin MÃ THOÁT. Bắt chuỗi "FAIL" trong stdout làm một test có chữ
        # "FAIL" trong TÊN cũng làm đỏ cả cổng dù pytest thoát 0.
        ok = r.returncode == 0
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {tail}")
        if not ok:
            fails.append(name)
            print((r.stdout or r.stderr or "")[-3000:])

    try:
        sys.path.insert(0, str(ROOT))
        from src.python.core.runtime_meta import banner

        print(f"[THÔNG TIN] {banner()[:110]}")
    except Exception as e:
        print(f"[CẢNH BÁO] banner: {e}")

    if fails:
        print(f"\n>>> KIỂM TRA PHÁT HÀNH THẤT BẠI: {fails}")
        return 1
    print(f"\n>>> KIỂM TRA PHÁT HÀNH: HỆ THỐNG SẴN SÀNG "
          f"({len(mods)} module, {len(LIVE_IMPORTS)} import đường live)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
