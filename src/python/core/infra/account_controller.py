"""Account Controller Module (SSOT Account & Storage Context)
============================================================
Quản lý thông tin tài khoản MT5 hiện tại và cung cấp thư mục lưu trữ (storage path)
được cách ly riêng biệt theo Account ID (MT5_LOGIN). Tất cả các module trong hệ thống
đều truy xuất đường dẫn live data qua module này hoặc qua `config.LIVE_DIR`.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, Optional

from src.python.utils.env_loader import load_env_file

class AccountController:
    """SSOT Controller quản lý thông tin tài khoản và không gian lưu trữ (isolated workspace)."""
    
    _account_id: Optional[str] = None
    _live_dir: Optional[Path] = None

    # VẤN ĐỀ: Cần xác định chính xác thư mục gốc của repository để lưu dữ liệu đúng chỗ.
    # `__file__` = <repo>/src/python/core/infra/account_controller.py
    # parents[0]=infra, [1]=core, [2]=python, [3]=src, [4]=<repo>
    _REPO_ROOT_DEPTH = 4

    @classmethod
    def initialize(cls) -> str:
        """Đọc biến môi trường và thiết lập Account ID + LIVE_DIR.
        
        VÌ SAO CẦN: Đảm bảo thư mục lưu trữ live data luôn trỏ đúng 
        về `<repo>/data/live/<login>/` cho tất cả các tiến trình (supervisor, engine,...),
        tránh tình trạng ghi và đọc ở hai thư mục khác nhau do sai lệch cấp thư mục.
        """
        load_env_file()
        login = os.environ.get("MT5_LOGIN", "").strip()
        cls._account_id = login if login else "default"

        repo_root = Path(__file__).resolve().parents[cls._REPO_ROOT_DEPTH]
        cls._live_dir = repo_root / "data" / "live" / cls._account_id
        cls._live_dir.mkdir(parents=True, exist_ok=True)
        return cls._account_id

    @classmethod
    def get_account_id(cls) -> str:
        """Lấy thông tin Account ID (tự động khởi tạo nếu chưa có)."""
        if cls._account_id is None:
            cls.initialize()
        return cls._account_id

    @classmethod
    def get_live_dir(cls) -> Path:
        """Lấy đường dẫn thư mục lưu trữ dữ liệu (tự động khởi tạo nếu chưa có)."""
        if cls._live_dir is None:
            cls.initialize()
        return cls._live_dir

    @classmethod
    def get_file_path(cls, filename: str) -> Path:
        """Trả về đường dẫn tuyệt đối của tệp tin thuộc không gian tài khoản hiện tại."""
        return cls.get_live_dir() / filename

    @classmethod
    def get_credentials(cls) -> Dict[str, Any]:
        """Lấy thông tin đăng nhập MT5 đã parse an toàn."""
        load_env_file()
        login_raw = os.environ.get("MT5_LOGIN")
        login = int(login_raw) if login_raw and login_raw.isdigit() else None
        return {
            "login": login,
            "password": os.environ.get("MT5_PASSWORD", ""),
            "server": os.environ.get("MT5_SERVER", ""),
            "path": os.environ.get("MT5_PATH", ""),
        }
