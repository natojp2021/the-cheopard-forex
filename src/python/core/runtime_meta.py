"""RUNTIME METADATA MODULE — Trung tâm Quản lý Phiên bản.

Source of truth (SSOT) để trả lời câu hỏi: Báo cáo/Log/GUI đang hiển thị dữ liệu sinh ra từ 
version code nào, phiên bản chiến lược nào, hay file cấu hình nào?

Hỗ trợ lấy version qua Git commit hoặc file VERSION (when deploy production). 
Tích hợp các tiện ích để gắn footer phiên bản vào Email và Log.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
import os
import platform
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from src.python.core.config import PROJECT_ROOT

ROOT = Path(PROJECT_ROOT)
VERSION_FILE = ROOT / "data" / "VERSION"          # fallback when thiếu git
MODEL_MANIFEST = ROOT / "models" / "model_bundle.json"
CONFIG_FILES = [ROOT / ".env", ROOT / "src" / "python" / "core" / "config.py"]

# ---------------------------------------------------------------- registry
# Version NGỮ NGHĨA của từng chiến lược (bump khi đổi rule, ghi rõ lý do).
# SSOT rule: docs/research/specs/10_Danh-muc-chien-luoc.md
def _strategies_from_registry() -> dict:
    """Bảng chiến lược cho attribution — SINH từ registry Forex.

    Bản XAU khai tay 12 mục ở đây (WaveRider, SwingDON, XAU-R…), và danh sách đó là
    một nguồn sự thật THỨ HAI: thêm chiến lược mà quên sửa nó thì nhật ký quyết định
    ghi thiếu, mà không có gì báo. Sinh từ registry thì lỗi đó hết đường xảy ra.
    """
    try:
        from src.python.core import strategy_registry as _sr
        return {g.name: {"ver": "1.0", "magic": g.magic, "tag": g.gui_tag,
                         "tf": g.signal_tf, "stage": g.stage,
                         "note": (g.hypothesis or "")[:120]}
                for g in _sr.all_specs()}
    except Exception:
        return {}


STRATEGIES = _strategies_from_registry()



_cache: dict = {}


# ---------------------------------------------------------------- git layer
def _git(*args: str) -> Optional[str]:
    try:
        creationflags = 0
        if os.name == "nt":
            creationflags = 0x08000000  # CREATE_NO_WINDOW
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                             text=True, timeout=10, creationflags=creationflags)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def _git_info() -> dict:
    commit = _git("rev-parse", "--short=7", "HEAD")
    if not commit:
        if VERSION_FILE.is_file():
            try:
                return {"version": VERSION_FILE.read_text(encoding="utf-8").strip(),
                        "commit": None, "branch": None}
            except Exception:
                pass
        return {"version": "", "commit": None, "branch": None}
    date_time = _git("show", "-s", "--format=%cd", "--date=format:%Y.%m.%d_%H:%M:%S", "HEAD") or "0.0.0"
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    # Định dạng GIỮ NGUYÊN của một hệ một-tài-sản: `v<ngày giờ commit>+<hash>`. Không hậu tố.
    #
    # Bản 14/08 có thêm `-dirty@HH:MM` lấy từ mtime tệp `.py` mới nhất, để phân biệt
    # "đã sửa code chưa commit" với bản đã commit. Bỏ 15/08: thứ nó định chữa —
    # nhấn VBS mà vẫn chạy build cũ — không phải do stamp mà do khoá chống chạy
    # nhiều bản đưa cửa sổ CŨ lên trước. Chỗ ấy đã sửa ở `live_server.py`, nên hậu
    # tố chỉ còn là rác trên thanh tiêu đề.
    return {"version": f"v{date_time}+{commit}", "commit": commit, "branch": branch}


# ---------------------------------------------------------------- model/config
def _model_info() -> dict:
    """Đọc bundle manifest đã publish (không load model). Fail-soft."""
    try:
        m = json.loads(MODEL_MANIFEST.read_text(encoding="utf-8"))
        mid = m.get("manifest_sha256") or m.get("bundle_sha256") or ""
        return {"bundle": f"{m.get('features_version', '?')}@{str(mid)[:8] or 'nohash'}",
                "trained_at": m.get("created_at") or m.get("trained_at")}
    except Exception:
        return {"bundle": "none", "trained_at": None}


def _config_hash() -> str:
    """Hash gộp các file config vận hành (không lộ nội dung .env)."""
    h = hashlib.sha256()
    for fp in CONFIG_FILES:
        try:
            h.update(fp.read_bytes())
        except Exception:
            h.update(b"missing:" + str(fp).encode())
    return h.hexdigest()[:8]


# ---------------------------------------------------------------- public API
def get_meta(refresh: bool = False) -> dict:
    global _cache
    if _cache and not refresh:
        return _cache
    g = _git_info()
    _cache = {
        "system": g,
        "strategies": {k: dict(v) for k, v in STRATEGIES.items()},
        "model": _model_info(),
        "config_hash": _config_hash(),
        "python": platform.python_version(),
    }
    return _cache


def refresh() -> dict:
    return get_meta(refresh=True)


def version() -> str:
    return get_meta()["system"]["version"]


def strategy_tag(name: str) -> str:
    """'WaveRider/1.1' — gắn vào comment lệnh/journal của từng chiến lược."""
    s = STRATEGIES.get(name)
    return f"{name}/{s['ver']}" if s else name


def banner() -> str:
    """Tạo chuỗi định danh ngắn cho log/GUI lúc khởi động.
    
    Định dạng: BUILD <version> | <danh_sách_chiến_lược_live>
    Lưu ý: Không chứa thông tin chi tiết về branch/model/config để hiển thị gọn gàng.
    Thông tin attribution đầy đủ được ghi riêng vào decision journal thông qua
    `record_startup_attribution()`.
    """
    m = get_meta()
    return f"BUILD {m['system']['version']} | {_live_snapshot()}"


def _live_snapshot() -> str:
    """Trả về chuỗi 'Tên/ver' của các chiến lược ĐANG LIVE.
    
    Lấy nguồn sự thật (SSOT) từ `strategy_registry` (kiểm tra `stage == LIVE`),
    đảm bảo chỉ hiển thị những chiến lược thực sự đang hoạt động trong hệ thống.
    """
    m = get_meta()
    try:
        from src.python.core import strategy_registry as _sr
        magic_live = {s.magic for s in _sr.ALL
                      if str(getattr(s, "stage", "")).upper() == "LIVE"}
    except Exception:
        magic_live = None       # fail-soft: thà hiện thừa còn hơn chặn khởi động
    cap = [(k, v) for k, v in m["strategies"].items()
           if magic_live is None or v.get("magic") in magic_live]
    return " ".join(f"{k}/{v['ver']}" for k, v in cap) or "(không có chiến lược LIVE)"


def banner_full() -> str:
    """Bản ĐẦY ĐỦ (build + branch + model bundle + config hash + strategy version).
    Dùng cho audit/journal, không dùng cho dòng log GUI — xem `banner()`."""
    m = get_meta()
    return (f"BUILD {m['system']['version']} (branch {m['system'].get('branch') or '?'}) | "
            f"model {m['model']['bundle']} | cfg {m['config_hash']} | {_live_snapshot()}")


def record_startup_attribution() -> None:
    """Ghi attribution đầy đủ của session vào decision journal (1 lần lúc khởi động).
    
    Đảm bảo khả năng truy vết "kết quả này sinh ra từ code/config/model nào"
    dù thông tin hiển thị trên GUI đã được rút gọn. Fail-soft: lỗi journal không 
    block khởi động engine.
    """
    try:
        from src.python.utils import decision_journal
        m = get_meta()
        decision_journal.record(
            "RISK", "startup_attribution",
            build=m["system"]["version"],
            branch=m["system"].get("branch"),
            model_bundle=m["model"]["bundle"],
            config_hash=m["config_hash"],
            python=m.get("python"),
            strategies={k: v["ver"] for k, v in m["strategies"].items()},
        )
    except Exception:
        pass


def stamp() -> dict:
    """Dict gọn để nhúng vào report/run-manifest/CSV."""
    m = get_meta()
    return {
        "build": m["system"]["version"],
        "strategies": {k: v["ver"] for k, v in m["strategies"].items()},
        "model_bundle": m["model"]["bundle"],
        "config_hash": m["config_hash"],
    }


def email_footer() -> Tuple[str, str]:
    """(text, html) — gắn cuối mọi email để truy vết."""
    return "", ""
