"""fx_market_state.py — TRẠNG THÁI THỊ TRƯỜNG cho console vận hành, đo TỪ GIÁ.

CÂU HỎI MODULE NÀY TRẢ LỜI
==========================
Console cần bốn ô, và câu hỏi đúng cho mỗi ô là: **cái gì ở đây là SỰ THẬT ĐO ĐƯỢC,
chứ không phải một ý kiến?**

    THIÊN HƯỚNG    → tổng phơi nhiễm THẬT của danh mục, quy về từng ĐỒNG TIỀN. Đây
                     là thứ người vận hành thật sự cần biết: hệ đang nghiêng về đâu.
                     Nó là tổng vị thế, không phải dự đoán — không thể sai.
    SOFT REGIME    → biến động rổ ở khung D1 so với phân vị TRƯỢT. Đo mức biến động
                     hiện tại đứng ở đâu so với chính nó trong một năm qua.
    HARD REGIME    → cùng nguyên tắc ở khung H4 — nhạy hơn, bắt được cú giật trong
                     phiên mà D1 làm mượt mất.
    MODEL ENGINE   → hệ này KHÔNG dùng mô hình học máy nào. Hiện đúng như vậy, chứ
                     không hiện "N/A" — N/A đọc như "hỏng", còn đây là thiết kế.

Nguyên tắc: mọi ô hiển thị số phải trace được về một nguồn thật đang chạy. Thứ không
có nguồn thì ghi rõ là không có, KHÔNG bịa số.

VÌ SAO PHÂN VỊ TRƯỢT, KHÔNG PHẢI NGƯỠNG CỐ ĐỊNH
================================================
Biến động FX đổi mức theo năm. "0,5%/ngày là cao" đúng ở 2021 và sai ở 2020. Một
ngưỡng cố định vì vậy sẽ báo CRISIS suốt một năm rồi câm suốt năm sau — tức nó không
mang thông tin nào. Phân vị trượt neo vào chính chuỗi đó nên nó luôn so được.

CACHE LÀ BẮT BUỘC, KHÔNG PHẢI TỐI ƯU
=====================================
Console gọi lại mỗi 5 giây. Tính biến động rổ đòi nạp giá của cả rổ — mất vài giây.
Không cache thì console đứng hình liên tục và người vận hành tưởng treo. Cache 15
phút là đủ: đầu vào là nến D1/H4 ĐÃ ĐÓNG, trong 15 phút không có gì đổi.

⚠️ LỚP `try/except` Ở `_compute` KHÔNG ĐƯỢC IM LẶNG
==================================================
Console không được sập vì một lỗi nạp giá, nên `_compute` bọc toàn bộ trong
`try/except`. Nhưng nhánh lỗi PHẢI điền `MarketState.error` và console PHẢI hiện nó:
một bản trước của module này bắt ngoại lệ rồi trả `UNKNOWN` mà không ai thấy lý do,
nên nó hiện UNKNOWN suốt nhiều tuần trong khi nguyên nhân chỉ là một module đã bị
xoá. Trả trạng thái "không biết" mà không nói VÌ SAO thì tệ hơn là để nó nổ.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import numpy as np

CACHE_SECONDS = 900.0          # 15 phút — nến D1/H4 không đổi nhanh hơn thế

_lock = threading.Lock()
_cache: Dict[str, Any] = {"at": 0.0, "value": None}


@dataclass(frozen=True)
class MarketState:
    """Trạng thái thị trường đo được. Mọi trường đều có nguồn, không có trường đoán."""
    soft_regime: str                  # CALM | CRISIS | UNKNOWN — cổng chân D1
    soft_percentile: Optional[float]  # biến động rổ đứng ở phân vị nào
    hard_regime: str                  # CALM | ELEVATED | CRISIS — rổ cross H4
    hard_percentile: Optional[float]
    net_bias: Optional[float]         # thiên hướng ròng của danh mục, [−1 · +1]
    bias_detail: str                  # đồng tiền được mua/bán nhiều nhất
    asof: str
    error: str = ""


def _percentile_of_last(series, window: int) -> Optional[float]:
    """Giá trị cuối đứng ở phân vị nào trong `window` kỳ trước đó.

    Dùng phân vị TRƯỢT chứ không phải ngưỡng cố định — xem docstring module.
    """
    s = series.dropna()
    if len(s) < window // 2:
        return None
    w = s.iloc[-window:]
    return float((w <= s.iloc[-1]).mean())


def _basket_vol(timeframe: str, start: str) -> "Any":
    """Độ lệch chuẩn CẮT NGANG của lợi suất rổ, làm mượt — thước đo "chợ đang động".

    Cắt ngang chứ không theo chuỗi: một cặp giật mạnh là chuyện của cặp đó, còn CẢ
    RỔ cùng giật mới là chế độ thị trường. Rổ lấy từ chính chiến lược đang chạy nên
    thước đo này luôn nói về đúng cái đang được giao dịch.
    """
    import pandas as pd

    from src.python.shared import fx_data as D
    from src.python.strategies.h1 import asia_sweep as AS

    rule = D.TF_RULE.get(timeframe, "1D")
    cols = {}
    for sym in AS.INSTRUMENTS:
        m1 = D.load_m1(sym)
        px = m1["close"].resample(rule).last().dropna()
        px = px[px.index >= pd.Timestamp(start)]
        cols[sym] = np.log(px).diff()
    panel = pd.DataFrame(cols).dropna(how="all")
    if panel.empty:
        raise ValueError("rổ không có dữ liệu để đo biến động")
    win = 30 if timeframe != "D1" else 20
    return panel.std(axis=1).rolling(win, min_periods=win // 2).mean()


def _label(pct: Optional[float]) -> str:
    """Phân vị -> nhãn chế độ. Ba mức, hai ngưỡng, và cả hai đều là SỐ.

    0,90 và 0,75 là phân vị, không phải mức biến động — nên chúng không cần đo lại
    khi thị trường đổi mức. Chúng chỉ định nghĩa "cao" nghĩa là gì.
    """
    if pct is None:
        return "UNKNOWN"
    if pct >= 0.90:
        return "CRISIS"
    if pct >= 0.75:
        return "ELEVATED"
    return "CALM"


def _compute() -> MarketState:
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    try:
        dvol = _basket_vol("D1", "2022-01-01")
        soft_pct = _percentile_of_last(dvol, 252)
        hvol = _basket_vol("H4", "2023-01-01")
        hard_pct = _percentile_of_last(hvol, 252 * 6)
        bias, detail = _portfolio_bias()
        return MarketState(soft_regime=_label(soft_pct), soft_percentile=soft_pct,
                           hard_regime=_label(hard_pct), hard_percentile=hard_pct,
                           net_bias=bias, bias_detail=detail, asof=now)
    except Exception as exc:                                   # pragma: no cover
        # KHÔNG im lặng: `error` được console hiện ra. Xem cảnh báo ở đầu module.
        return MarketState("UNKNOWN", None, "UNKNOWN", None, None, "",
                           now, f"{type(exc).__name__}: {exc}")


def _portfolio_bias() -> Tuple[Optional[float], str]:
    """Thiên hướng RÒNG của danh mục, quy về phơi nhiễm từng ĐỒNG TIỀN.

    Một vị thế EURUSD mua mang EUR long + USD short — hai chân, không phải một. Không
    quy đổi thì console nói "đang mua EURUSD" mà không ai thấy rằng hai lệnh khác
    cũng đang bán USD, tức cả hệ đang đặt CÙNG MỘT cược vào USD với cỡ gấp ba.

    Trả (thiên hướng thuộc [-1; +1], mô tả). Dấu dương = nghiêng về đồng RỦI RO
    (AUD/NZD/CAD/GBP), âm = nghiêng về đồng TRÚ ẨN (JPY/CHF/USD) — quy ước quen thuộc
    "risk-on / risk-off".

    Nguồn là `portfolio.exposure_report()`, tức CÙNG hàm mà báo cáo phơi nhiễm dùng.
    Đọc từng chiến lược rồi tự cộng lại là cách để console và báo cáo trôi khỏi nhau.
    """
    RISK_ON = {"AUD", "NZD", "CAD", "GBP"}
    RISK_OFF = {"JPY", "CHF", "USD"}

    try:
        from src.python.strategies import portfolio as PF

        targets = PF.live_targets(log=False)
        rep = PF.exposure_report(targets)
    except Exception:
        return None, ""

    if rep.empty:
        return 0.0, "không có tín hiệu vào lệnh nào"

    expo = {str(k): float(v) for k, v in rep["exposure"].items()}
    on = sum(v for k, v in expo.items() if k in RISK_ON)
    off = sum(v for k, v in expo.items() if k in RISK_OFF)
    tot = sum(abs(v) for v in expo.values()) or 1.0
    top = sorted(expo.items(), key=lambda kv: -abs(kv[1]))[:3]
    detail = " · ".join(f"{k} {v:+.0f}" for k, v in top if abs(v) > 1e-9)
    n = len(targets.entries)
    return float((on - off) / tot), f"{n} tín hiệu · {detail}"


def get_state(force: bool = False) -> MarketState:
    """Trạng thái thị trường, có cache. Giao diện gọi hàm này mỗi lần vẽ."""
    with _lock:
        if (not force and _cache["value"] is not None
                and time.time() - _cache["at"] < CACHE_SECONDS):
            return _cache["value"]           # type: ignore[return-value]
    st = _compute()
    with _lock:
        _cache["at"], _cache["value"] = time.time(), st
    return st


def next_events(limit: int = 3) -> Tuple[str, str]:
    """Sự kiện vĩ mô sắp tới — nguồn cho thẻ NEWS FEED.

    Đọc chính lịch mà cổng tin dùng (`data/economic_calendar_events.parquet`, 968 sự
    kiện đến 2027). Không gọi API tin tức ở đây: bảng vẽ lại mỗi 5 giây, và một lời
    gọi mạng trong đường vẽ là cách chắc chắn để giao diện đứng hình khi mạng chậm.
    """
    try:
        import pandas as pd

        from src.python.ai import news_guard as NG

        df = NG.load_calendar()
        if df is None or df.empty:
            return "N/A", "không đọc được lịch kinh tế"
        now = pd.Timestamp(datetime.now(timezone.utc))
        nxt = df[df["time"] >= now].sort_values("time").head(limit)
        if nxt.empty:
            return "TRỐNG", "không còn sự kiện nào trong lịch"
        r = nxt.iloc[0]
        hours_ahead = (r["time"] - now).total_seconds() / 3600.0
        event_name = str(r["event"])
        others = ", ".join(str(x) for x in nxt["event"].iloc[1:]) or "—"
        return (f"{event_name} sau {hours_ahead:.0f}h",
                f"{r['time'].strftime('%d/%m %H:%M')} UTC · kế tiếp: {others}")
    except Exception as exc:                                   # pragma: no cover
        return "N/A", f"{type(exc).__name__}"
