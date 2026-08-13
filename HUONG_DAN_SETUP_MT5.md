# Hướng dẫn cài đặt và vận hành MT5

Hệ thống chạy theo mô hình **Pure Python API**: Python đọc dữ liệu, đánh giá tín hiệu, tính khối lượng, gửi lệnh và quản lý vị thế trực tiếp qua MetaTrader 5. KHÔNG dùng EA MQL5.

> **Tài liệu hệ thống đầy đủ**: `docs/research/specs/README.md` (kiến trúc, dữ liệu, AI, backtest, live trading, runbook). Tài liệu này chỉ hướng dẫn cài đặt.
>
> **Một tiến trình vận hành**: Engine XAUUSD `start_live_server.bat` — hiện chạy chế độ MONITOR-ONLY.

## 1. Yêu cầu

- Windows 10/11 hoặc Windows Server/VPS.
- MetaTrader 5 terminal của broker, đã đăng nhập đúng tài khoản.
- Python **3.11 64-bit**. Trình khởi động `start_live_server.bat` mặc định dùng `.venv311`.
- Git (chỉ cần nếu lấy/cập nhật mã nguồn bằng Git).

Gói `MetaTrader5` chỉ được cài trên Windows theo điều kiện trong `requirements.txt`. GUI dùng `customtkinter`; chế độ CLI không cần mở cửa sổ giao diện.

## 2. Cài đặt Python

Mở PowerShell tại thư mục gốc dự án và chạy:

```powershell
py -3.11 -m venv .venv311
.\.venv311\Scripts\python.exe -m pip install --upgrade pip
.\.venv311\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Cấu hình MetaTrader 5

1. Cài và mở MT5 terminal của broker.
2. Đăng nhập tài khoản **Demo** hoặc **FTMO** tương ứng với dự án.
3. Vào `Tools` → `Options` → `Expert Advisors` và bật `Allow algorithmic trading`.
4. Bật nút **Algo Trading** trên thanh công cụ.
5. Giữ MT5 chạy trong lúc Python kết nối và giao dịch.

`Allow DLL imports` không phải yêu cầu của Python API trong kiến trúc hiện tại. Chỉ bật nếu một công cụ MT5 khác của bạn thực sự cần DLL.

---

## 4. Setup Chạy 2 Dự Án / 2 Tài Khoản Trên Cùng 1 VPS (Multi-Instance MT5)

Khi vận hành 2 dự án (ví dụ: dự án `quant-xau` và dự án `the-cheopard-forex`) hoặc 2 tài khoản FTMO độc lập trên cùng 1 VPS Windows:

### Nguyên Lý & Ràng Buộc Kỹ Thuật

- **Thư viện MetaTrader5 Python API**: Mỗi tiến trình Python chỉ có thể kết nối tới **1 MT5 terminal tại một thời điểm**. Hai dự án chạy 2 tiến trình Python độc lập trỏ tới 2 MT5 terminal riêng.
- **Chế độ Portable (`/portable`)**: Mặc định, các bản MT5 cài đặt trên cùng máy dùng chung thư mục dữ liệu `AppData\Roaming\MetaQuotes\Terminal\<hash>`. Nếu dùng chung, 2 terminal sẽ đè profile/cấu hình của nhau. Cờ `/portable` ép terminal lưu dữ liệu trực tiếp trong thư mục cài đặt của nó, giúp 2 terminal hoàn toàn tách biệt.

### Các Bước Cài Đặt MT5 Thứ Hai

1. **Dựng thư mục MT5 riêng biệt (không cài chồng)**:
   Bộ cài MT5 mặc định sẽ nâng cấp bản đã cài thay vì cho chọn thư mục mới. Do đó, bạn sao chép thư mục MT5 hiện có ra thư mục riêng (ví dụ: `C:\Program Files\MetaTrader 5 - Forex`).
   Dự án có sẵn script PowerShell tự động hoá việc này:

   ```powershell
   # Mở PowerShell với quyền Administrator
   .\scripts\setup_second_mt5.ps1 -Source "C:\Program Files\MetaTrader 5" -Target "C:\Program Files\MetaTrader 5 - Forex"
   ```

2. **Khởi chạy terminal ở chế độ Portable**:
   Chạy file vừa tạo: `C:\Program Files\MetaTrader 5 - Forex\start_mt5_forex.bat` (file này gọi `terminal64.exe /portable`).
   - Đăng nhập tài khoản FTMO tương ứng của dự án này.
   - Bật **Algo Trading** (`Ctrl+E`).

3. **Cấu hình đường dẫn trong tệp `.env`**:
   Mỗi dự án cần trỏ chính xác đường dẫn `MT5_PATH` tới terminal tương ứng trong tệp `.env` của mình:

   **Dự án 1 (ví dụ: `quant-xau`):**

   ```ini
   MT5_LOGIN=11111111
   MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
   ```

   **Dự án 2 (`the-cheopard-forex`):**

   ```ini
   MT5_LOGIN=22222222
   MT5_PATH=C:\Program Files\MetaTrader 5 - Forex\terminal64.exe
   ```

   _Lưu ý: Nếu để trống `MT5_PATH`, thư viện Python MT5 sẽ tự động nối vào terminal nào nó tìm thấy trước, dẫn tới nguy cơ đặt lệnh nhầm tài khoản giữa 2 dự án._

---

## 5. Khởi chạy

### GUI (mặc định)

Nhấp đúp `start_live_server.bat`, hoặc chạy:

```powershell
.\start_live_server.bat
```

Lệnh Python tương đương:

```powershell
.\.venv311\Scripts\python.exe src\python\gui_launcher.py
```

### CLI

```powershell
.\.venv311\Scripts\python.exe -m src.python.core.engine
```

Sau khi khởi động GUI:

1. Kiểm tra trạng thái tài khoản và server (Đèn báo kết nối MT5 màu xanh).
2. Dùng **RECONNECT** nếu trạng thái là `DISCONNECTED`.
3. Nhấn **STOP ENGINE** hoặc `Ctrl+C` ở chế độ CLI để dừng an toàn.
