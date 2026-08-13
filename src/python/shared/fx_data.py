"""fx_data.py — nạp dữ liệu thị trường cho The Cheopard Forex. SSOT, không phụ thuộc chiến lược.

Module này thay `research/fx_lab.py` (đã xoá 13/08/2026). `fx_lab` tồn tại để trả lời
đúng MỘT câu hỏi — "8 strategy family của hệ XAUUSD có edge trên Forex không?" — và câu
trả lời đã có, dứt khoát: **KHÔNG** (28/33 biến thể NO_INFORMATION, MFE/|MAE| ≈ 1,00;
xem `docs/forex/00_ket_qua_vong_1.md`). Giữ lại nó chỉ mời gọi việc lặp lại một hướng
đã bị bác bỏ, nên phần nạp dữ liệu — thứ duy nhất còn giá trị — được tách về đây.

NGUỒN DỮ LIỆU
=============
    D:/data-ticks-train/_m1/<SYMBOL>_m1.parquet
Nến M1 dựng từ tick Dukascopy. Cột: time · open · high · low · close · spread · n_tick.
EURUSD có từ 2015; 6 cặp còn lại từ 2020. (`_BUILD_REPORT.md` trong cùng thư mục.)

HAI QUY ƯỚC CẦN BIẾT
====================
* `spread` trong file gốc ĐÃ LÀ ĐƠN VỊ GIÁ, không phải điểm broker (EURUSD: 0,000030
  = 0,30 pip). Đổi tên thành `spread_usd` để giữ tương thích với engine mô phỏng, dù
  với FX thì "usd" là tên gọi lịch sử — đơn vị thật là đơn vị giá của chính cặp.
* `n_tick` -> `volume`. Đây là TICK VOLUME, đúng đại lượng MT5 cấp ở live
  (`tick_volume`), nên dùng nó là parity chứ không phải xấp xỉ.
"""
from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

M1_DIR = Path("D:/data-ticks-train/_m1")

# Quy tắc resample theo tên khung — SSOT để mọi module dùng chung một định nghĩa.
TF_RULE: Dict[str, str] = {
    "M5": "5min", "M15": "15min", "M30": "30min",
    "H1": "1h", "H4": "4h", "D1": "1D",
}


# Công tắc nguồn dữ liệu cho đường LIVE. `True` = ưu tiên lấy nến từ MT5.
#
# VÌ SAO CẦN — phát hiện 15/08/2026 khi triển khai VPS: parquet ở
# `D:/data-ticks-train/_m1/` dựng theo lô từ tick Dukascopy nên nó LUÔN TRỄ. Đo được
# hôm đó: nến mới nhất 2026-07-17, tức **cũ 28 ngày**. Chân Z-Band H1 tính z trên 48
# nến, nên với dữ liệu đó hệ sẽ giao dịch hôm nay theo giá tháng trước — và không có
# exception nào, `load_m1` vẫn trả một DataFrame hợp lệ, chỉ hợp lệ cho quá khứ.
#
# Bật cờ này thì `load_m1` lấy nến từ chính broker sẽ khớp lệnh. Backtest KHÔNG bật
# (nó cần 6,5 năm cố định, tái lập được); engine live bật.
USE_MT5_BARS = os.getenv("FX_BARS_FROM_MT5", "0").strip().lower() in (
    "1", "true", "yes", "on")


_PARQUET_ONLY = threading.local()


def _parquet_forced() -> bool:
    return bool(getattr(_PARQUET_ONLY, "on", False))


@contextmanager
def parquet_only():
    """Trong khối này, `load_m1` LUÔN đọc parquet — kể cả khi `FX_BARS_FROM_MT5=1`.

    LỖI ĐÃ TÌM RA 16/08/2026 — MẪU NGẮN HƠN 11 LẦN MÀ KHÔNG AI BIẾT
    ================================================================
    `USE_MT5_BARS` là một cờ TOÀN CỤC đọc từ biến môi trường, nhưng cùng một
    `load_m1` phục vụ HAI mục đích trái ngược nhau:

        · TÍN HIỆU LIVE  cần nến MỚI NHẤT, đúng nguồn giá sẽ khớp   → MT5
        · BACKTEST       cần 6,5 năm CỐ ĐỊNH, tái lập được          → parquet

    Docstring của `USE_MT5_BARS` đã ghi đúng ý định đó, nhưng không có đường nào để
    backtest từ chối cờ. Nên trên VPS (`FX_BARS_FROM_MT5=1`), `engine._read_portfolio`
    → `PF.backtest()` → `daily_bars()` → `load_m1()` nhận về nến MT5:

        200.000 nến M1 = 6,6 THÁNG, trong khi backtest cần 6,5 NĂM

    Mẫu ngắn hơn **11 lần**, và mọi chỉ số danh mục (`sharpe_all`, `max_dd_sd`,
    `worst_day_sd`, `years_positive`) vẫn được báo như số toàn mẫu. Không có lỗi
    nào, không có cảnh báo nào — đúng họ "hỏng thì im lặng".

    XOÁ LUÔN MỘT ĐUA LUỒNG
    =======================
    Giao diện chạy `update_mt5_status` trên luồng riêng ngay lúc dựng cửa sổ, và nó
    gọi `_maybe_read_portfolio()`. Trên VPS nhánh đó đọc nến MT5 lúc 13:02:58, tức
    TRƯỚC khi `_prime_symbols()` tải xong lịch sử lúc 13:03:02 — sinh ra cảnh báo
    "DỮ LIỆU CŨ · EURUSD" tự khỏi bốn giây sau. Backtest không đụng MT5 nữa thì cả
    lớp cảnh báo giả đó biến mất cùng lúc.

    THREAD-LOCAL, không phải cờ module: vòng lặp live và lượt backtest chạy trên hai
    luồng khác nhau, và một cờ chung sẽ để lượt backtest ép luồng live đọc parquet —
    tức biến một bản vá thành đúng cái bệnh nó chữa, chỉ đổi chiều.
    """
    prev = _parquet_forced()
    _PARQUET_ONLY.on = True
    try:
        yield
    finally:
        _PARQUET_ONLY.on = prev


def load_m1(symbol: str) -> pd.DataFrame:
    """M1 thật: open/high/low/close/spread_usd/volume, index UTC naive, đã sắp xếp.

    Nguồn phụ thuộc `USE_MT5_BARS`:
        False  parquet lịch sử — dùng cho backtest, cố định và tái lập được
        True   MT5 trực tiếp   — dùng cho live, luôn mới và đúng nguồn giá sẽ khớp

    Bật cờ mà MT5 không trả được nến thì QUAY VỀ parquet, và ghi cảnh báo. Đây là
    fail-soft có chủ ý ở tầng DỮ LIỆU: không có nến thì không có tín hiệu, và "không
    có tín hiệu" im lặng còn tệ hơn một cảnh báo kèm dữ liệu cũ. Chặn giao dịch trên
    dữ liệu ôi là việc của `engine._build_plan`, nơi có `mt5_bars.freshness()`.
    """
    if USE_MT5_BARS and not _parquet_forced():
        # KHÔNG cache nhánh này. `@lru_cache` trên `load_m1` là đúng cho parquet
        # (file tĩnh, nạp lại là phí), nhưng với nến LIVE nó giữ ảnh chụp đầu tiên
        # mãi mãi — hệ sẽ quyết định trên nến của lần gọi đầu tiên suốt cả phiên.
        # Đúng họ lỗi "dữ liệu ôi mà không có exception" mà công tắc này sinh ra
        # để sửa, chỉ đổi từ ôi-28-ngày thành ôi-từ-lúc-khởi-động.
        from src.python.shared import mt5_bars

        df = mt5_bars.load_m1(symbol)
        if df is not None and not df.empty:
            _MT5_BARS_MISSING.pop(symbol, None)
            return df
        _warn_stale_source(symbol)

    return _load_m1_parquet(symbol)


# Lần cuối đã cảnh báo thiếu nến MT5, theo từng công cụ.
_MT5_BARS_MISSING: dict = {}
# Nhắc lại sau ngần này giây. 15 phút: đủ thưa để không lấp nhật ký, đủ dày để
# người vận hành không quên mất hệ đang chạy trên dữ liệu lịch sử.
_STALE_WARN_EVERY = 900.0


def _warn_stale_source(symbol: str) -> None:
    """Cảnh báo hệ đang chạy trên PARQUET thay vì nến MT5 — kèm HẬU QUẢ và cách sửa.

    VÌ SAO DÒNG NÀY PHẢI Ở LẠI (câu hỏi của người vận hành 16/08/2026)
    ==================================================================
    Nhìn thoáng thì nó giống một dòng nhiễu lúc khởi động. Thực tế nó là dòng quan
    trọng nhất trong cả nhật ký khởi động khi `FX_BARS_FROM_MT5=1`: nó nói đường dữ
    liệu LIVE không hoạt động, và hệ vừa lặng lẽ đổi sang một tệp parquet mà nến
    cuối cùng có thể cũ hàng ngày tới hàng tuần.

    Chiến lược không phân biệt được hai nguồn — chúng cùng hình dạng. Nên nếu cổng
    tươi mới ở `engine._build_plan` (`mt5_bars.freshness()`) có lúc nào đó hỏng, hệ
    sẽ vào lệnh thật dựa trên giá của tuần trước mà không có gì báo. Bỏ dòng này là
    bỏ lớp cảnh báo duy nhất đứng trước tình huống đó.

    BA ĐIỂM YẾU CỦA BẢN CŨ, ĐÃ SỬA
    ===============================
    1. KHÔNG nói hậu quả — chỉ ghi "quay về parquet lịch sử", đọc như một thao tác
       kỹ thuật bình thường chứ không như một cảnh báo.
    2. KHÔNG nói cách sửa — người vận hành không biết phải làm gì tiếp.
    3. LẶP không giới hạn — `load_m1` được gọi cho 7 công cụ ở mỗi lượt dựng kế
       hoạch, nên một terminal chưa tải lịch sử sinh ra dòng này mãi mãi. Cảnh báo
       lặp vô hạn là cảnh báo sẽ bị lọc bỏ, tức mất luôn tác dụng.

    Nguyên nhân thường gặp nhất: terminal MT5 vừa cài trên VPS CHƯA tải lịch sử về.
    `copy_rates_from_pos` trả rỗng cho tới khi terminal kéo dữ liệu từ server, và
    cuối tuần thị trường đóng thì nó chưa kéo.
    """
    import time

    now = time.time()
    if now - _MT5_BARS_MISSING.get(symbol, 0.0) < _STALE_WARN_EVERY:
        return
    _MT5_BARS_MISSING[symbol] = now

    from src.python.utils.logger import log_error

    log_error(
        f"⚠️ DỮ LIỆU CŨ · {symbol}: MT5 không trả được nến M1 → đang dùng PARQUET "
        f"LỊCH SỬ. Tín hiệu tính trên dữ liệu này KHÔNG phải giá hiện tại. "
        f"Kiểm: terminal đã tải xong lịch sử {symbol} chưa (mở biểu đồ M1 để ép "
        f"tải), và {symbol} có trong Market Watch không.")


@lru_cache(maxsize=16)
def _load_m1_parquet(symbol: str) -> pd.DataFrame:
    """Nhánh PARQUET, có cache — file tĩnh nên nạp lại là phí thuần."""
    fp = M1_DIR / f"{symbol}_m1.parquet"
    if not fp.is_file():
        raise FileNotFoundError(
            f"Không tìm thấy M1 cho {symbol}: {fp}\n"
            f"  · Backtest BẮT BUỘC cần file này (~620 MB cho 7 cặp).\n"
            f"  · Chạy LIVE trên VPS thì KHÔNG cần: đặt biến môi trường "
            f"FX_BARS_FROM_MT5=1 để lấy nến thẳng từ MT5.")
    df = pd.read_parquet(fp)
    if "time" in df.columns:
        df = df.set_index("time")
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df = df.rename(columns={"spread": "spread_usd", "n_tick": "volume"})
    cols = ["open", "high", "low", "close", "spread_usd"]
    if "volume" in df.columns:
        cols.append("volume")
    return df[cols]


def build_bars(m1: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """Gộp M1 -> khung `timeframe`, GIỮ volume.

    Ngưỡng bao phủ khác nhau theo khung, và đó là sự thật của thị trường FX chứ không
    phải nới lỏng: M5-H1 đòi bucket đủ 100% nến M1, nhưng H4/D1 chỉ đòi >= 50% vì một
    ngày giao dịch không bao giờ có đủ 1.440 nến M1 (nghỉ cuối tuần, gap phiên, ngày
    lễ) — lọc 100% cho ra ĐÚNG 0 nến D1.
    """
    rule = TF_RULE[timeframe]
    cov = 0.5 if pd.Timedelta(rule) >= pd.Timedelta("4h") else 1.0
    g = m1.resample(rule, origin="start_day", closed="left", label="left")
    agg = {"open": "first", "high": "max", "low": "min", "close": "last",
           "spread_usd": "mean"}
    if "volume" in m1.columns:
        agg["volume"] = "sum"
    out = g.agg(agg).dropna(subset=["open", "high", "low", "close", "spread_usd"])
    expected = int(pd.Timedelta(rule) / pd.Timedelta(minutes=1))
    counts = g.size().reindex(out.index, fill_value=0)
    out = out[counts >= cov * expected] if cov < 1.0 else out[counts == expected]
    last_available = m1.index.max() + pd.Timedelta(minutes=1)
    return out[out.index + pd.Timedelta(rule) <= last_available]


def daily_bars(symbol: str, start: str | None = None) -> pd.DataFrame:
    """Nến D1 (bao phủ nới) — đơn vị nền của mọi chiến lược thang ngày."""
    m1 = load_m1(symbol)
    g = m1.resample("1D", origin="start_day")
    agg = {"open": "first", "high": "max", "low": "min", "close": "last",
           "spread_usd": "median"}
    if "volume" in m1.columns:
        agg["volume"] = "sum"
    d = g.agg(agg).dropna(subset=["open", "high", "low", "close"])
    return d[d.index >= start] if start else d


def median_spread(m1: pd.DataFrame) -> float:
    return float(m1["spread_usd"].median())
