"""
env_loader.py — Module tải biến môi trường từ tệp .env tại thư mục gốc dự án.
Được nạp đầu tiên tại config.py và email_reporter.py để đảm bảo toàn bộ thông số
(MT5 credentials, SMTP Email, hằng số cấu hình) được quản lý tập trung từ duy nhất 1 file (.env).
"""

import os
from typing import List, Optional, Sequence
from pathlib import Path

def load_env_file(dotenv_path: Optional[str] = None) -> None:
    """
    Tải cấu hình từ file .env vào os.environ.
    Ưu tiên giữ nguyên giá trị nếu biến môi trường đã được đặt trước đó trong system.
    """
    if dotenv_path is None:
        # Xác định đường dẫn thư mục gốc dự án (the-cheopard-forex/.env)
        root_dir = Path(__file__).resolve().parent.parent.parent.parent
        dotenv_path = str(root_dir / ".env")

    if not os.path.isfile(dotenv_path):
        return

    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Bỏ qua dòng trống hoặc comment #
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    # Loại bỏ dấu nháy bao quanh nếu có (' hoặc ")
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    else:
                        # Bỏ qua inline comment (cắt chuỗi từ ' #').
                        hash_idx = val.find(" #")
                        if hash_idx != -1:
                            val = val[:hash_idx].rstrip()
                    if key and key not in os.environ:
                        os.environ[key] = val
    except Exception as e:
        print(f"[ENV LOADER] Cảnh báo lỗi đọc tệp .env: {e}", flush=True)

# Đọc N-key (danh sách) cho các provider để xoay vòng, tương thích ngược với cấu hình key đơn cũ.
def resolve_api_keys(env_prefix: str, legacy_names: Sequence[str] = ()) -> List[str]:
    """Đọc danh sách API key cho 1 provider theo thứ tự ưu tiên:
    1. `{env_prefix}S` dạng danh sách phân tách bằng dấu phẩy (vd `GEMINI_API_KEYS=k1,k2,k3`).
    2. Các biến `legacy_names` riêng lẻ (vd `ALPHA_VANTAGE_API_KEY_1`, `_2`) — tương
       thích ngược với quy ước 2-key thủ công đã có trước đây.
    3. Biến đơn `{env_prefix}` (vd `GEMINI_API_KEY=k1`) — tương thích ngược với
       cấu hình chỉ có 1 key.
    Trả về list rỗng nếu không cấu hình gì (caller tự fail-soft như hiện tại)."""
    plural_raw = os.environ.get(f"{env_prefix}S", "")
    keys = [k.strip() for k in plural_raw.split(",") if k.strip()]
    if keys:
        return keys
    legacy_keys = [os.environ.get(name, "").strip() for name in legacy_names]
    legacy_keys = [k for k in legacy_keys if k]
    if legacy_keys:
        return legacy_keys
    single = os.environ.get(env_prefix, "").strip()
    return [single] if single else []


# Tự động thực thi ngay khi import module
load_env_file()
