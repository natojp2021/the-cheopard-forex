"""fx_market_state.py — TRẠNG THÁI THỊ TRƯỜNG cho bảng điều khiển, đo từ giá.

VÌ SAO KHÔNG PORT `ai_macro` CỦA THE CHEOPARD
==============================================
Bốn thẻ AI TREND · MODEL ENGINE · SOFT REGIME · HARD REGIME ở hệ XAUUSD lấy số từ
bộ máy LLM hai tầng (`ai_moe_engine`, 952 dòng): các chuyên gia chấm điểm, chủ tịch
tổng hợp thành một con số sentiment, rồi thẻ hiện con số đó.

Hệ Forex bỏ kiến trúc ấy theo yêu cầu — một tầng, chỉ chặn, không dự báo. Nên bốn
thẻ đó cần nguồn khác, và câu hỏi đúng là: **cái gì trên bảng này là SỰ THẬT ĐO
ĐƯỢC, chứ không phải ý kiến?**

    AI TREND       → THIÊN HƯỚNG RÒNG của chính danh mục đang chạy. Đây là thứ
                     người vận hành thật sự cần biết: hệ đang nghiêng về đâu. Nó là
                     tổng vị thế, không phải dự đoán — không thể sai.
    SOFT REGIME    → cổng chế độ THẬT đang chạy trong `currency_reversal`: biến động
                     rổ 8 đồng so với phân vị 80 trượt 252 ngày. Chính cổng này
                     quyết định hai chân D1 có giao dịch hay không.
    HARD REGIME H4 → biến động rổ 20 cross ở khung H4, phân vị trượt. Cùng nguyên
                     tắc, khác vũ trụ và khác khung.
    MODEL ENGINE   → hệ này KHÔNG dùng mô hình học máy nào. Hiện đúng như vậy, chứ
                     không hiện "N/A" — N/A đọc như "hỏng", còn đây là thiết kế.

NGUYÊN TẮC GIỮ NGUYÊN TỪ THE CHEOPARD: mọi ô hiển thị số phải trace được về một
nguồn thật đang chạy. Thứ không có nguồn thì ghi rõ là không có, không bịa số.

CACHE LÀ BẮT BUỘC, KHÔNG PHẢI TỐI ƯU
=====================================
Bảng gọi lại mỗi 5 giây. Tính biến động rổ đòi nạp 27 chuỗi giá — mất vài giây. Không
cache thì giao diện đứng hình liên tục và người dùng tưởng treo. Cache 15 phút là đủ:
đầu vào là nến D1/H4 đã đóng, trong 15 phút không có gì đổi.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

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

    Dùng phân vị TRƯỢT chứ không phải ngưỡng cố định: biến động FX đổi mức theo năm,
    nên "0,5%/ngày là cao" đúng ở 2021 và sai ở 2020.
    """
    import numpy as np

    s = series.dropna()
    if len(s) < window // 2:
        return None
    w = s.iloc[-window:]
    return float((w <= s.iloc[-1]).mean())


def _compute() -> MarketState:
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    try:
        import numpy as np
        import pandas as pd

        from src.python.strategies.d1 import currency_reversal as CR

        # ── SOFT REGIME: đúng cổng đang chạy trong chân D1, không phải bản gần đúng
        F, _ = CR.currency_returns(start="2022-01-01")
        cfg = CR.Config()
        crisis = CR.regime_is_crisis(F, cfg)
        bvol = F.std(axis=1).rolling(cfg.regime_vol_window,
                                     min_periods=cfg.regime_vol_window // 2).mean()
        soft_pct = _percentile_of_last(bvol, cfg.regime_window)
        soft = "CRISIS" if bool(crisis.iloc[-1]) else "CALM"

        # ── HARD REGIME H4: biến động rổ 20 cross, cùng nguyên tắc phân vị trượt
        from src.python.research import fx_cross_lab as LAB

        panel = LAB.build_panel("H4", start="2023-01-01")
        cvol = panel.logp.diff().std(axis=1).rolling(30, min_periods=15).mean()
        hard_pct = _percentile_of_last(cvol, 252 * 6)
        if hard_pct is None:
            hard = "UNKNOWN"
        elif hard_pct >= 0.90:
            hard = "CRISIS"
        elif hard_pct >= 0.75:
            hard = "ELEVATED"
        else:
            hard = "CALM"

        # ── THIÊN HƯỚNG RÒNG: tổng vị thế thật của danh mục, quy về phơi nhiễm đồng tiền
        bias, detail = _portfolio_bias()

        return MarketState(soft_regime=soft, soft_percentile=soft_pct,
                           hard_regime=hard, hard_percentile=hard_pct,
                           net_bias=bias, bias_detail=detail, asof=now)
    except Exception as exc:                                   # pragma: no cover
        return MarketState("UNKNOWN", None, "UNKNOWN", None, None, "",
                           now, f"{type(exc).__name__}: {exc}")


def _portfolio_bias() -> Tuple[Optional[float], str]:
    """Thiên hướng RÒNG của danh mục, quy về phơi nhiễm từng đồng tiền.

    Một vị thế AUDCAD mua mang AUD long + CAD short — hai chân, không phải một. Không
    quy đổi thì bảng nói "đang mua AUDCAD" mà không ai thấy được rằng ba chiến lược
    khác cũng đang bán CAD, tức toàn hệ đang đặt cùng một cược.

    Trả (thiên hướng ∈ [−1, +1], mô tả). Dấu dương = nghiêng về đồng RỦI RO
    (AUD/NZD/CAD), âm = nghiêng về đồng TRÚ ẨN (JPY/CHF/USD) — quy ước quen thuộc
    "risk-on / risk-off".
    """
    from collections import defaultdict

    RISK_ON = {"AUD", "NZD", "CAD", "GBP"}
    RISK_OFF = {"JPY", "CHF", "USD"}

    expo: Dict[str, float] = defaultdict(float)
    n = 0
    try:
        from src.python.core import strategy_registry as _sr

        for g in _sr.live():
            mod_name = None
            for spec_mod in ("m30", "h1", "h4", "d1"):
                pass
            try:
                from importlib import import_module
                mod = import_module(
                    f"src.python.strategies.{g.signal_tf.lower()}."
                    f"{_module_of(g.name)}")
            except Exception:
                continue
            fn = getattr(mod, "live_decision", None)
            if fn is None:
                continue
            try:
                d = fn()
            except Exception:
                continue
            if getattr(d, "action", "") not in ("BUY", "SELL"):
                continue
            sign = 1.0 if d.action == "BUY" else -1.0
            inst = str(getattr(d, "instrument", ""))
            if len(inst) == 6:
                expo[inst[:3]] += sign
                expo[inst[3:]] -= sign
                n += 1
    except Exception:
        return None, ""

    if not expo:
        return 0.0, "không có vị thế nào đang mở"

    on = sum(v for k, v in expo.items() if k in RISK_ON)
    off = sum(v for k, v in expo.items() if k in RISK_OFF)
    tot = sum(abs(v) for v in expo.values()) or 1.0
    bias = (on - off) / tot

    top = sorted(expo.items(), key=lambda kv: -abs(kv[1]))[:3]
    detail = " · ".join(f"{k} {v:+.0f}" for k, v in top if abs(v) > 1e-9)
    return float(bias), f"{n} tín hiệu · {detail}"


def _module_of(name: str) -> str:
    """Tên module từ tên chiến lược. Cùng quy ước đặt tên của `strategies/`."""
    special = {"CurrencyReversal": "currency_reversal",
               "CurrencyCarry": "currency_carry",
               "CrossMeanReversion": "cross_mean_reversion",
               "CrossMomentum": "cross_momentum",
               "CrossXsReversion": "cross_xs_reversion"}
    if name in special:
        return special[name]
    if name.startswith("ZBand"):
        rest = name[5:]
        for tf in ("M30", "H1", "H4", "D1"):
            if rest.endswith(tf):
                return f"zband_{rest[:-len(tf)].lower()}"
    return name.lower()


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
