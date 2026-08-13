"""decision_log.py — sổ ghi QUYẾT ĐỊNH VÀO LỆNH, tách khỏi log nghiên cứu.

VÌ SAO HAI LOẠI LOG, KHÔNG PHẢI MỘT
====================================
Log nghiên cứu (`reports/fx_research/*.csv`) trả lời: *"chiến lược này lãi bao
nhiêu trên dữ liệu lịch sử"*. Nó tổng hợp, và tổng hợp thì che mất từng lệnh.

Sổ này trả lời một câu khác hẳn: *"vì sao LỆNH NÀY được mở, tại đúng thời điểm đó,
với đúng những con số đó"*. Khi một lệnh tiền thật thua bất thường, chỉ có bản ghi
đầy đủ tham số tại thời điểm quyết định mới cho phép phân biệt ba khả năng:

    (a) tín hiệu đúng luật, thị trường đi ngược  -> bình thường, không sửa gì
    (b) tham số đã TRÔI (half-life, µ, σ lệch khỏi giá trị đã kiểm chứng)
    (c) dữ liệu vào sai (nến thiếu, giá lệch, sai múi giờ)

Không có sổ này thì cả ba trông giống hệt nhau, và mọi tranh luận về một lệnh cụ
thể đều là suy đoán. Đây cũng là điều kiện để tái lập: một lệnh live phải tái tạo
được từ chính bản ghi của nó.

GHI CẢ NHỮNG LẦN KHÔNG GIAO DỊCH
================================
Sổ ghi MỌI đánh giá, kể cả `HOLD` và `SKIP`. Lý do: câu hỏi vận hành thường gặp
nhất không phải "vì sao mở lệnh này" mà là **"vì sao hôm nay không có lệnh nào"**.
Nếu chỉ ghi lệnh đã mở thì câu đó không trả lời được, và người vận hành sẽ đoán —
thường là đoán sai theo hướng "hệ thống hỏng rồi".

ĐỊNH DẠNG
=========
JSON Lines (`.jsonl`), một dòng một quyết định, xoay theo THÁNG. Chọn JSONL vì:
mỗi dòng độc lập (file hỏng giữa chừng vẫn đọc được phần trước), append được mà
không phải nạp lại, và đọc bằng `pandas.read_json(lines=True)`.
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import pandas as pd

from src.python.shared.paths import PROJECT_ROOT

LOG_DIR = PROJECT_ROOT / "logs" / "decisions"


def _serialise(v: Any) -> Any:
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    if isinstance(v, (bool, int, str)) or v is None:
        return v
    try:
        f = float(v)
        # NaN/Inf không hợp lệ trong JSON chuẩn — ghi thành null thay vì tạo file
        # mà parser khác từ chối đọc.
        return f if f == f and abs(f) != float("inf") else None
    except (TypeError, ValueError):
        return str(v)


def _path_for(ts: pd.Timestamp) -> Path:
    return LOG_DIR / f"decisions_{pd.Timestamp(ts):%Y-%m}.jsonl"


def record(decision: Any, *, strategy: str, extra: Optional[Dict[str, Any]] = None
           ) -> Path:
    """Ghi MỘT quyết định. Nhận dataclass (vd `EntryDecision`) hoặc dict.

    Không ném lỗi ra ngoài: mất một dòng log không được phép làm dừng vòng giao
    dịch. Lỗi ghi được in ra stderr qua logger để vẫn thấy được.
    """
    d = asdict(decision) if is_dataclass(decision) else dict(decision)
    ts = pd.Timestamp(d.get("timestamp") or datetime.now(timezone.utc))
    row = {"logged_at_utc": datetime.now(timezone.utc).isoformat(),
           "strategy": strategy,
           **{k: _serialise(v) for k, v in d.items()}}
    if extra:
        row.update({k: _serialise(v) for k, v in extra.items()})
    p = _path_for(ts)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:      # pragma: no cover
        from src.python.utils.logger import get_logger
        get_logger(__name__).error("decision_log: không ghi được %s: %s", p, exc)
    return p


def record_many(decisions: Iterable[Any], *, strategy: str,
                extra: Optional[Dict[str, Any]] = None) -> int:
    n = 0
    for d in decisions:
        record(d, strategy=strategy, extra=extra)
        n += 1
    return n


def load(month: Optional[str] = None, strategy: Optional[str] = None
         ) -> pd.DataFrame:
    """Đọc sổ. `month` dạng "2026-08"; None = mọi tháng."""
    files = sorted(LOG_DIR.glob(f"decisions_{month}.jsonl" if month
                                else "decisions_*.jsonl"))
    if not files:
        return pd.DataFrame()
    frames = [pd.read_json(f, lines=True) for f in files if f.stat().st_size > 0]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if strategy:
        df = df[df["strategy"] == strategy]
    if "timestamp" in df:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.sort_values("timestamp").reset_index(drop=True)


def audit_trade(cross: str, entry_time: str, month: Optional[str] = None
                ) -> pd.DataFrame:
    """Truy ngược một lệnh cụ thể: mọi đánh giá của `cross` quanh `entry_time`.

    Đây là hàm dùng khi một lệnh live có kết quả bất thường — nó trả về đúng bối
    cảnh mà hệ thống đã thấy lúc quyết định, gồm cả các nến TRƯỚC đó (để xem
    `was_outside_band` được đặt lúc nào) và SAU đó.
    """
    df = load(month=month)
    if df.empty:
        return df
    t = pd.Timestamp(entry_time)
    m = (df["cross"] == cross) & df["timestamp"].between(
        t - pd.Timedelta(hours=48), t + pd.Timedelta(hours=12))
    cols = [c for c in ("timestamp", "cross", "action", "z_score", "mu", "sigma",
                        "half_life_bars", "window_bars", "was_outside_band",
                        "reentered", "execution_hour_ok", "est_cost_bps", "reason")
            if c in df.columns]
    return df[m][cols].reset_index(drop=True)


def daily_summary(day: Optional[str] = None) -> pd.DataFrame:
    """Tóm tắt một ngày: mỗi cross một dòng, hành động và lý do.

    Dùng cho báo cáo vận hành hằng ngày — trả lời được cả "đã mở gì" lẫn
    "vì sao không mở gì".
    """
    df = load()
    if df.empty:
        return df
    d = pd.Timestamp(day).normalize() if day else df["timestamp"].max().normalize()
    sub = df[df["timestamp"].dt.normalize() == d]
    if sub.empty:
        return sub
    last = sub.sort_values("timestamp").groupby("cross").tail(1)
    cols = [c for c in ("timestamp", "cross", "action", "z_score",
                        "half_life_bars", "reason") if c in last.columns]
    return last[cols].sort_values("cross").reset_index(drop=True)
