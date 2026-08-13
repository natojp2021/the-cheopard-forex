# -*- coding: utf-8 -*-
"""Vì sao MT5 không kết nối — chạy TRÊN MÁY có terminal đang mở.

    .venv311\\Scripts\\python.exe scripts/check_mt5_connection.py

VÌ SAO CẦN
===========
Bảng điều khiển chỉ hiện "DISCONNECTED" và "KHÔNG ĐỌC ĐƯỢC VỊ THẾ" — hai câu không
nói được nguyên nhân. Bài này in ra ĐÚNG mã lỗi của `mt5.last_error()` kèm nghĩa,
và thử lần lượt từng cách kết nối để chỉ ra cách nào chạy được.

CÁI BẪY CHÍNH: NHIỀU TERMINAL CÙNG CHẠY
========================================
`mt5.initialize()` KHÔNG có `path` sẽ gắn vào MỘT terminal do thư viện tự chọn. Khi
có hai terminal đang mở, "một" đó có thể là cái không đăng nhập tài khoản FTMO, hoặc
là cái không cho phép kết nối API — và thư viện không nói nó chọn cái nào.

Đó là lý do `.env` phải khai `MT5_PATH` khi máy chạy nhiều terminal: nó biến việc
chọn từ ngẫu nhiên thành xác định.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Mã lỗi của thư viện MetaTrader5 (âm) — tra cứu tại chỗ để không phải đi tìm.
_ERR = {
    1: "thành công",
    -1: "lỗi chung",
    -2: "tham số sai — kiểm login/password/server",
    -3: "không đủ bộ nhớ",
    -4: "cấu trúc lịch sử không hợp lệ",
    -5: "lỗi khởi tạo — thường là KHÔNG TÌM THẤY terminal64.exe theo `path`",
    -6: "ĐĂNG NHẬP THẤT BẠI — sai login/password/server, hoặc tài khoản bị khoá",
    -7: "quyền không đủ",
    -8: "hết thời gian chờ",
    -9: "gửi lệnh thất bại",
    -10000: "IPC: mở kết nối nội bộ thất bại",
    -10001: "IPC: khởi tạo thất bại",
    -10002: "IPC: phiên bản terminal KHÔNG TƯƠNG THÍCH với thư viện Python",
    -10003: "IPC: gửi dữ liệu thất bại",
    -10004: "IPC: nhận dữ liệu thất bại",
    -10005: "IPC: HẾT THỜI GIAN CHỜ — terminal đang bận, đang khởi động, hoặc chạy "
            "ở PHIÊN WINDOWS KHÁC với tiến trình Python",
}


def _explain(err) -> str:
    try:
        code = int(err[0])
    except Exception:
        return str(err)
    return f"{err}  → {_ERR.get(code, 'mã không có trong bảng tra')}"


def _terminals() -> list:
    """Đường dẫn của mọi `terminal64.exe` đang chạy, kèm phiên Windows."""
    if os.name != "nt":
        return []
    import subprocess
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe'\" | "
          "Select-Object ProcessId,SessionId,ExecutablePath | Format-List")
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=30,
            creationflags=0x08000000)
        return [l.strip() for l in (out.stdout or "").splitlines() if l.strip()]
    except Exception as exc:
        return [f"(không liệt kê được: {exc})"]


def main() -> int:
    print("=" * 74)
    print("CHẨN ĐOÁN KẾT NỐI MT5")
    print("=" * 74)

    print(f"\nTiến trình Python: pid {os.getpid()} · phiên Windows: ", end="")
    try:
        import ctypes
        sid = ctypes.c_ulong()
        ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(),
                                                    ctypes.byref(sid))
        print(sid.value)
    except Exception:
        print("(không đọc được)")

    print("\nTERMINAL ĐANG CHẠY")
    lines = _terminals()
    if not lines:
        print("  KHÔNG có terminal64.exe nào đang chạy — đây là nguyên nhân.")
    for l in lines:
        print(f"  {l}")
    print("  ⚠️ SessionId phải TRÙNG với phiên của Python ở trên. Lệch phiên thì")
    print("     IPC không đi qua được, và lỗi trả về là -10005 (hết thời gian chờ).")

    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        print(f"\n⛔ Chưa cài thư viện MetaTrader5: {exc}")
        return 1

    from src.python.core.config import LOGIN, MT5_PATH, PASSWORD, SERVER

    print("\nCẤU HÌNH ĐỌC TỪ .env")
    print(f"  MT5_PATH   : {MT5_PATH or '(TRỐNG)'}")
    print(f"  MT5_LOGIN  : {LOGIN or '(TRỐNG)'}")
    print(f"  MT5_SERVER : {SERVER or '(TRỐNG)'}")
    print(f"  MT5_PASSWORD: {'đã khai' if PASSWORD else '(TRỐNG)'}")
    if len(lines) > 3 and not MT5_PATH:
        print("  ⚠️ CÓ NHIỀU TERMINAL mà MT5_PATH TRỐNG — thư viện tự chọn một cái,")
        print("     và có thể chọn cái không đăng nhập tài khoản FTMO.")

    # Thử lần lượt, từ cách hệ đang dùng tới cách tối giản. Cách nào chạy được là
    # câu trả lời cho "phải sửa gì trong .env".
    attempts = [
        ("đầy đủ như engine (login + password + server + path)",
         dict(login=LOGIN, password=PASSWORD, server=SERVER,
              **({"path": MT5_PATH} if MT5_PATH else {}))
         if (LOGIN and PASSWORD and SERVER) else None),
        ("chỉ path (gắn vào terminal đã đăng nhập sẵn)",
         {"path": MT5_PATH} if MT5_PATH else None),
        ("trần, không tham số", {}),
    ]

    print("\nTHỬ KẾT NỐI")
    ok_any = False
    for label, kw in attempts:
        if kw is None:
            print(f"  ⊘ {label} — BỎ QUA, thiếu cấu hình")
            continue
        try:
            mt5.shutdown()
        except Exception:
            pass
        try:
            ok = mt5.initialize(**kw)
        except Exception as exc:
            print(f"  ✗ {label} — NÉM {type(exc).__name__}: {exc}")
            continue
        if not ok:
            print(f"  ✗ {label}")
            print(f"      {_explain(mt5.last_error())}")
            continue
        ok_any = True
        ti = mt5.terminal_info()
        ai = mt5.account_info()
        print(f"  ✓ {label}")
        if ti:
            print(f"      terminal : {getattr(ti, 'path', '?')}")
            print(f"      kết nối  : {getattr(ti, 'connected', '?')} · "
                  f"cho phép giao dịch: {getattr(ti, 'trade_allowed', '?')}")
        if ai:
            print(f"      tài khoản: {ai.login} @ {ai.server} · "
                  f"balance {ai.balance:,.2f} {ai.currency}")
            if LOGIN and int(ai.login) != int(LOGIN):
                print(f"      ⛔ SAI TÀI KHOẢN — .env khai {LOGIN}. Hệ sẽ TẮT công "
                      f"tắc giao dịch khi phát hiện điều này.")
        else:
            print(f"      ⚠️ account_info() rỗng: {_explain(mt5.last_error())} — "
                  f"terminal chạy nhưng CHƯA ĐĂNG NHẬP tài khoản nào.")
        pos = mt5.positions_get()
        print(f"      vị thế   : "
              + (f"{len(pos)} lệnh" if pos is not None
                 else f"KHÔNG đọc được — {_explain(mt5.last_error())}"))
        break

    try:
        mt5.shutdown()
    except Exception:
        pass

    print()
    if ok_any:
        print("KẾT LUẬN: kết nối được. Nếu bảng điều khiển vẫn DISCONNECTED thì cách")
        print("chạy được ở trên KHÁC với cách engine đang dùng — khai đúng nó vào .env.")
    else:
        print("KẾT LUẬN: KHÔNG cách nào kết nối được. Theo thứ tự cần kiểm:")
        print("  1. Terminal có chạy CÙNG PHIÊN Windows với Python không (xem trên).")
        print("  2. Terminal đã ĐĂNG NHẬP tài khoản chưa — terminal mở mà chưa đăng")
        print("     nhập thì `account_info()` rỗng và bảng hiện N/A.")
        print("  3. Tools → Options → Expert Advisors → 'Allow algorithmic trading'.")
        print("  4. MT5_PATH trỏ đúng `terminal64.exe` của terminal FTMO chưa.")
        print("  5. MT5_SERVER phải khớp TỪNG KÝ TỰ với tên server trong terminal")
        print("     (ví dụ 'FTMO-Demo2', không phải 'FTMO Demo').")
    return 0 if ok_any else 1


if __name__ == "__main__":
    raise SystemExit(main())
