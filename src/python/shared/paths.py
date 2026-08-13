"""Quản lý Đường dẫn (Paths SSOT) cho toàn dự án.

Đảm bảo độc lập: Module này tuyệt đối không có side-effect (không khởi tạo MT5, 
không đọc file, không nạp env) để tránh circular import cho các tầng bên trên.

Quy ước vòng đời: Tên biến đặt theo giai đoạn vòng đời dữ liệu thay vì tên thư mục vật lý:
- RAW, NORMALIZED, CONFIG: Dữ liệu nguồn chân lý.
- FEATURE, MACRO, ARTIFACT, MODEL: Dữ liệu có thể tái tạo từ RAW + Code.
- BACKTEST, REPORT, LOG: Báo cáo đầu ra.
"""
from __future__ import annotations

from pathlib import Path

# src/python/shared/paths.py -> parents[3] = gốc repo
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]

# ------------------------------------------------------------------ vòng đời dữ liệu
DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DIR: Path = DATA_DIR / "raw"
NORMALIZED_DIR: Path = DATA_DIR / "data-ticks-train"
FEATURE_DIR: Path = DATA_DIR / "cache"
RESEARCH_DATA_DIR: Path = DATA_DIR / "research"
MACRO_DATA_DIR: Path = DATA_DIR / "macro"
RUNTIME_STATE_DIR: Path = DATA_DIR / "live"

# ĐÃ XOÁ 14/08/2026: `CANONICAL_M1` trỏ tới `xauusd_m1.parquet` — file của hệ
# tiền nhiệm, không tồn tại trong dự án này và không module nào đọc nó. Hệ Forex
# không có MỘT chuỗi canonical: nó đọc 7 file M1 theo cặp từ `M1_DIR` bên ngoài
# repo, khai báo ở `shared/fx_data.py`. Giữ hằng số này lại sẽ mời người ta viết
# `pd.read_parquet(CANONICAL_M1)` và nhận FileNotFoundError ở chỗ không ngờ.
#     nến M1 theo cặp  ->  src.python.shared.fx_data.M1_DIR / load_m1(symbol)

# ------------------------------------------------------------------ artifact & config
ARTIFACT_DIR: Path = PROJECT_ROOT / "artifacts"
MODEL_DIR: Path = PROJECT_ROOT / "src" / "models"
CONFIG_DIR: Path = PROJECT_ROOT / "configs"

# ------------------------------------------------------------------ đầu ra
BACKTEST_REPORT_DIR: Path = PROJECT_ROOT / "backtest" / "reports"
REPORT_DIR: Path = PROJECT_ROOT / "reports"
LOG_DIR: Path = PROJECT_ROOT / "logs"
DOCS_DIR: Path = PROJECT_ROOT / "docs"

# ------------------------------------------------------------------ file cụ thể
LLM_MODEL_CACHE: Path = ARTIFACT_DIR / "llm_models_cache.json"
