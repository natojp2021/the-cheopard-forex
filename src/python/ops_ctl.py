# -*- coding: utf-8 -*-
"""ops_ctl.py — ĐIỀU KHIỂN BOT TỪ DÒNG LỆNH. Thay các nút bấm của bảng điều khiển Tk.

VÌ SAO MODULE NÀY LÀ ĐIỀU KIỆN BẮT BUỘC CỦA VIỆC XOÁ GIAO DIỆN
===============================================================
Bảng điều khiển cũ không chỉ HIỂN THỊ. Nó có ba hành động vận hành thật:

    RUN ENGINE      cho mọi chiến lược vào lệnh mới
    STOP ENGINE     TỪ CHỐI mọi lệnh mới, vị thế đang mở vẫn được quản lý
    FLATTEN ALL     đóng sạch vị thế (kill switch)

Xoá giao diện mà không thay được cả ba là biến một hệ có người điều khiển thành một hệ
không ai can thiệp được — và cái mất lớn nhất là kill switch, tức đúng thao tác chỉ cần
đến trong tình huống xấu nhất.

CLI TỐT HƠN NÚT BẤM, KHÔNG CHỈ NGANG BẰNG
==========================================
Công tắc nằm trên ĐĨA (`data/live/trading_control.json`) và `order_plan.build()` đọc
lại nó mỗi lượt. Nên công cụ này chạy ở MỘT TIẾN TRÌNH KHÁC vẫn điều khiển được bot
đang chạy:

  · đổi trạng thái từ một phiên SSH thứ hai, không cần chạm tiến trình bot
  · không có luồng giao diện nào để đua với vòng lặp — cả họ lỗi "gọi Tk từ luồng nền"
    biến mất theo, không phải được vá mà là không còn chỗ xảy ra
  · ghi được vào script/cron nếu cần

HAI THỨ KHÔNG BAO GIỜ ĐƯỢC LÀM Ở ĐÂY
=====================================
1. KHÔNG dừng vòng lặp. `stop` chỉ đóng CÔNG TẮC, đúng như nút cũ. Ứng dụng phải chạy
   bình thường để còn đọc tài khoản, đếm time-stop, đối soát sổ vị thế và canh cầu chì.
   Một vị thế đang mở mà mất người quản lý là tình trạng nguy hiểm HƠN việc vào thêm
   lệnh.
2. KHÔNG đóng lệnh mà không hỏi. `flatten` đòi `--confirm` tường minh; nó là thao tác
   không thể hoàn tác trên tiền thật.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Chờ tối đa ngần này giây cho `mt5.initialize()`. Mặc định của thư viện là 60 giây, và
# nó CÒN TỰ KHỞI CHẠY terminal nếu chưa mở — nên một lệnh chẩn đoán trên máy không có
# MT5 đang chạy sẽ treo hàng phút. Với công cụ dùng để trả lời "đang có chuyện gì", treo
# là hỏng: người ta gõ nó đúng lúc cần câu trả lời nhanh nhất.
MT5_TIMEOUT_MS = 5_000


def _console():
    from src.python.core.ops_console import OpsConsole
    # `structured=False`: đây là công cụ chạy tay, không phải tiến trình vận hành. Ghi
    # các lượt gọi của nó vào sổ JSONL sẽ trộn thao tác thủ công vào cùng dòng thời gian
    # với sự kiện của bot, mà sổ đó là nguồn dựng lại sự cố.
    return OpsConsole(heartbeat_seconds=1e9, structured=False)


def _init_mt5(con):
    """Nối MT5 với hạn chờ ngắn. `None` nếu không nối được."""
    try:
        import MetaTrader5 as mt5

        if not mt5.initialize(timeout=MT5_TIMEOUT_MS):
            con.event(f"KHÔNG nối được MT5 trong {MT5_TIMEOUT_MS // 1000}s "
                      f"(mã {mt5.last_error()}) — terminal có đang mở không?",
                      category="system", level="error")
            return None
        return mt5
    except Exception as exc:
        con.event(f"KHÔNG nối được MT5: {exc}", category="system", level="error")
        return None


def cmd_status(args) -> int:
    """Trạng thái công tắc, và (tuỳ chọn) vị thế đang mở.

    MẶC ĐỊNH KHÔNG CHẠM MT5. Công tắc nằm trên ĐĨA nên đọc được tức thời kể cả khi
    terminal đã tắt; gọi `mt5.initialize()` mặc định sẽ làm lệnh hay dùng nhất thành
    lệnh chậm nhất, và trên máy chưa mở MT5 thì nó còn TỰ KHỞI CHẠY terminal — một tác
    dụng phụ không ai xin.
    """
    from src.python.execution import trading_control as tc

    con = _console()
    state = tc.read()
    con.event(state.explain(), category="trading",
              level="good" if state.enabled else "warn")

    if not args.mt5:
        con.event("vị thế: chưa đọc (thêm --mt5 để hỏi terminal)",
                  category="trading", level="info")
    else:
        mt5 = _init_mt5(con)
        raw = None if mt5 is None else mt5.positions_get()
        if raw is None:
            # KHÔNG nói "không có vị thế" khi không đọc được. `positions_get()` trả
            # `None` khi API lỗi, và hiểu nó thành "rỗng" khiến người vận hành tin là
            # mình đang không có phơi nhiễm.
            con.event("KHÔNG đọc được vị thế — KHÔNG kết luận là đang rỗng. "
                      "Mở terminal kiểm tra bằng mắt.",
                      category="trading", level="error")
        else:
            con.event(f"VỊ THẾ đang mở: {len(raw)}", category="trading",
                      level="info" if raw else "good")
    print()
    print(f"  Đổi trạng thái:  python -m src.python.ops_ctl "
          f"{'stop' if state.enabled else 'run'}")
    print("  Đóng sạch lệnh:  python -m src.python.ops_ctl flatten --confirm")
    return 0


def cmd_run(_args) -> int:
    """Mở công tắc: mọi chiến lược được vào lệnh mới. KHÔNG chạm vòng lặp."""
    from src.python.execution import trading_control as tc

    tc.set_enabled(True, reason="RUN (ops_ctl)", by="operator")
    _console().event("RUN — công tắc MỞ, mọi chiến lược ĐƯỢC vào lệnh mới. "
                     "(Vòng lặp không bị chạm tới; nếu bot chưa chạy thì khởi động nó.)",
                     category="trading", level="good")
    return 0


def cmd_stop(_args) -> int:
    """Đóng công tắc: TỪ CHỐI lệnh mới. Vị thế đang mở VẪN được quản lý."""
    from src.python.execution import trading_control as tc

    tc.set_enabled(False, reason="STOP (ops_ctl)", by="operator")
    _console().event("STOP — công tắc TẮT, TỪ CHỐI mọi lệnh MỚI. Bot vẫn chạy bình "
                     "thường: vẫn đọc tài khoản, đếm time-stop, đối soát sổ vị thế và "
                     "canh cầu chì. Muốn ĐÓNG SẠCH thì dùng `flatten`.",
                     category="trading", level="warn")
    return 0


def cmd_positions(_args) -> int:
    """Liệt kê vị thế đang mở."""
    con = _console()
    mt5 = _init_mt5(con)
    if mt5 is None:
        return 1
    raw = mt5.positions_get()
    if raw is None:
        con.event("KHÔNG đọc được vị thế — KHÔNG kết luận là đang rỗng.",
                  category="trading", level="error")
        return 1
    if not raw:
        con.event("Không có vị thế nào đang mở.", category="trading", level="good")
        return 0
    print(f"{'ticket':>10} {'symbol':<9} {'chiều':<5} {'lot':>6} {'entry':>10} "
          f"{'SL':>10} {'TP':>10} {'lãi/lỗ':>11}  magic")
    for pos in raw:
        side = "BUY" if int(getattr(pos, "type", 0)) == 0 else "SELL"
        print(f"{int(pos.ticket):>10} {pos.symbol:<9} {side:<5} "
              f"{float(pos.volume):>6.2f} {float(pos.price_open):>10.5f} "
              f"{float(pos.sl):>10.5f} {float(pos.tp):>10.5f} "
              f"{float(pos.profit):>11.2f}  {int(pos.magic)}")
    return 0


def cmd_flatten(args) -> int:
    """KILL SWITCH: đóng toàn bộ vị thế. Đòi `--confirm`.

    Báo kết quả theo dạng `đã đóng/tổng` và nói RÕ khi không xác định được tổng — đó là
    hình dạng lỗi nặng nhất từng gặp trong họ dự án này: kill switch báo "đã đóng hết"
    khi chưa đóng gì, vì `positions_get()` trả `None` và mã gọi hiểu thành rỗng.
    """
    con = _console()
    if not args.confirm:
        con.event("FLATTEN cần --confirm. Đây là thao tác KHÔNG hoàn tác được trên "
                  "tiền thật: nó đóng mọi vị thế theo giá thị trường hiện tại.",
                  category="trading", level="warn")
        return 2
    try:
        from src.python.core.infra import mt5_bridge

        closed, total = mt5_bridge.close_all_positions(
            reason="MANUAL FLATTEN ALL (ops_ctl)")
    except Exception as exc:
        con.event(f"[MANUAL] FLATTEN LỖI: {exc}", category="trading", level="error")
        return 1
    if total is None:
        con.event("[MANUAL] FLATTEN: KHÔNG xác định được số vị thế trên broker — "
                  "KHÔNG thể khẳng định đã đóng hết. Kiểm tra terminal MT5 và chạy "
                  "lại, hoặc đóng tay.", category="trading", level="error")
        return 1
    con.event(f"[MANUAL] FLATTEN: đã đóng {closed}/{total} vị thế (MANUAL OVERRIDE).",
              category="trading", level="good" if closed == total else "error")
    return 0 if closed == total else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m src.python.ops_ctl",
        description="Điều khiển The Cheopard Forex từ dòng lệnh "
                    "(thay các nút của bảng điều khiển cũ).")
    sub = ap.add_subparsers(dest="cmd")
    p_status = sub.add_parser(
        "status", help="trạng thái công tắc (đọc đĩa, không chạm MT5)")
    p_status.add_argument("--mt5", action="store_true",
                          help="hỏi thêm MT5 số vị thế đang mở (chậm hơn)")
    p_status.set_defaults(fn=cmd_status)
    sub.add_parser("run", help="MỞ công tắc — cho vào lệnh mới").set_defaults(fn=cmd_run)
    sub.add_parser("stop", help="TẮT công tắc — từ chối lệnh MỚI, vẫn quản lý vị thế"
                   ).set_defaults(fn=cmd_stop)
    sub.add_parser("positions", help="liệt kê vị thế đang mở").set_defaults(
        fn=cmd_positions)
    p_flat = sub.add_parser("flatten", help="KILL SWITCH — đóng toàn bộ vị thế")
    p_flat.add_argument("--confirm", action="store_true",
                        help="bắt buộc: xác nhận đóng sạch")
    p_flat.set_defaults(fn=cmd_flatten)
    return ap


def main(argv=None) -> int:
    # TRƯỚC `argparse`: phần trợ giúp có chữ Việt có dấu, và nó được in trước khi bất cứ
    # `OpsConsole` nào được dựng — nên `--help` trên console cp1252 sẽ nổ
    # `UnicodeEncodeError` nếu để `_make_console()` lo việc này.
    from src.python.core.ops_console import use_utf8_stdout

    use_utf8_stdout()
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 2
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
