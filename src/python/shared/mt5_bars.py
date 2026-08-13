"""mt5_bars.py — nạp nến TRỰC TIẾP TỪ MT5 cho đường LIVE.

LỖI MÀ MODULE NÀY BỊT — PHÁT HIỆN 15/08/2026 KHI TRIỂN KHAI LÊN VPS
====================================================================
Mọi chân gọi `live_decision()`, hàm này gọi `_load()`, và `_load()` đọc file parquet
lịch sử ở `D:/data-ticks-train/_m1/`. Nghĩa là **quyết định LIVE được tính trên dữ
liệu OFFLINE**.

Đo được ngày 15/08/2026:

    nến M1 mới nhất trong parquet   2026-07-17 20:59
    hôm nay                          2026-08-15
    ⟹ DỮ LIỆU CŨ 28 NGÀY

Chân Z-Band H1 tính z trên cửa sổ 48 nến. Với dữ liệu cũ 28 ngày, cửa sổ đó nằm trọn
trong tháng Bảy, và hệ sẽ mua bán hôm nay theo mức giá của tháng trước. Không có
exception nào — `load_m1` trả về một DataFrame hợp lệ, chỉ là hợp lệ cho quá khứ.

Đây KHÔNG phải vấn đề "quên copy file lên VPS". Copy file lên cũng không sửa được:
parquet dựng từ tick Dukascopy theo lô, nó luôn trễ. Đường live phải lấy nến từ chính
broker sẽ khớp lệnh — vừa mới, vừa đúng nguồn giá mà lệnh sẽ khớp vào.

BACKTEST VẪN DÙNG PARQUET, CÓ CHỦ Ý
====================================
    backtest  →  parquet   6,5 năm lịch sử, cố định, tái lập được
    live      →  MT5       vài nghìn nến gần nhất, luôn mới

Hai nguồn khác nhau là ĐÚNG cho hai mục đích khác nhau. Điều phải giữ là hai nguồn
cho ra CÙNG một hình dạng dữ liệu — cùng tên cột, cùng đơn vị, cùng múi giờ — nếu
không thì mọi kiểm định parity đều đo nhầm thứ.

SPREAD Ở HAI NGUỒN KHÔNG CÙNG ĐƠN VỊ — CHỖ DỄ SAI NHẤT
=======================================================
    parquet   cột `spread` ĐÃ LÀ ĐƠN VỊ GIÁ (EURUSD 0,000030 = 0,30 pip)
    MT5       cột `spread` là ĐIỂM broker (số nguyên, EURUSD 3 = 0,30 pip)
Quy đổi sai chỗ này làm chi phí lệch 10.000 lần mà kết quả vẫn là số dương trông hợp
lý. Hàm dưới đây nhân với `point` để trả về ĐƠN VỊ GIÁ, khớp parquet.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

# Số nến M1 lấy về cho mỗi lần gọi. 200.000 nến M1 ≈ 5 tháng giao dịch — thừa cho
# cửa sổ dài nhất đang dùng (chân H4 cần 96 nến H4 = 5.760 nến M1) và vẫn nhanh.
DEFAULT_BARS = 200_000


def _timeframe_const(mt5, minutes: int = 1):
    return getattr(mt5, "TIMEFRAME_M1")


_fetch_failure_last_logged: dict = {}


def log_fetch_failure_throttled(tag: str, symbol: str, reason: str,
                                min_interval_s: float = 300.0) -> None:
    """SSOT cảnh báo khi `mt5.copy_rates_from_pos()` thất bại / không đủ bar.

    CLONE từ `live_strategies/market_guards.py` của hệ XAUUSD, giữ nguyên tên hàm,
    tên khoá thống kê và cấu trúc thông điệp.

    Trước bản vá đó, mọi `_fetch_*()` coi `rates is None or len(rates) < N` như nhau
    và `return None` HOÀN TOÀN IM LẶNG. Ở live ổn định, terminal luôn có thừa lịch
    sử cho mọi ngưỡng — nên nhánh này lặp lại liên tục là dấu hiệu THẬT của lỗi
    (symbol sai, terminal mất kết nối, broker gỡ symbol), không phải "chưa đủ dữ
    liệu" bình thường.

    Throttle theo `(tag, symbol)` để không lấp nhật ký khi lỗi kéo dài, nhưng KHÔNG
    BAO GIỜ im lặng hoàn toàn như bug gốc.
    """
    import time as _time

    from src.python.utils.logger import log_error

    key = (tag, symbol)
    now = _time.monotonic()
    last = _fetch_failure_last_logged.get(key, 0.0)
    if now - last >= min_interval_s:
        _fetch_failure_last_logged[key] = now
        log_error(f"⚠️ [{tag}] fetch dữ liệu MT5 thất bại/không đủ bar cho {symbol} "
                  f"({reason}) — nếu lặp lại liên tục, kiểm tra kết nối MT5/tên "
                  f"symbol.")


# Đếm sự cố fetch để biết bản vá retry có tác dụng THẬT hay không.
#   lan_hong  : số lần fetch đầu tiên không đủ nến
#   cuu_duoc  : trong số đó, bao nhiêu lần thử lại thành công
#   ngoai_le  : số lần `copy_rates_from_pos` NÉM LỖI
#
# Đếm chứ không chỉ vá: bản XAUUSD ghi thẳng trong docstring rằng phép thăm dò 240
# lần liên tiếp KHÔNG tái hiện được lần hỏng nào, tức chưa chứng minh được "gọi lại
# sau 0,3s sẽ thành công". Bộ đếm này là cách để sau vài ngày có số liệu thật, thay
# vì để một bản vá không ai kiểm chứng nằm mãi trong code.
_fetch_retry_stats = {"lan_hong": 0, "cuu_duoc": 0, "ngoai_le": 0}


def copy_rates_retry(mt5, symbol: str, timeframe, count: int, *, tag: str,
                     min_bars: Optional[int] = None,
                     wait_seconds: tuple = (0.3, 1.0)):
    """SSOT fetch nến có THỬ LẠI. Trả `rates` hoặc `None` (đã log giúp bên gọi).

    CLONE từ `live_strategies/market_guards.copy_rates_retry` của hệ XAUUSD.

    VÌ SAO CÓ (bằng chứng đo được bên đó, 03/08/2026)
    ==================================================
    Trước hàm này, 14 chỗ `_fetch_*()` gọi `copy_rates_from_pos` đúng MỘT lần; trả
    `None`/thiếu bar là bỏ trọn một chu kỳ đánh giá. Nhật ký một ngày cho thấy điều
    đó xảy ra **90 lần**, riêng H4-METALS 40 lần trên ~288 chu kỳ — tức khoảng
    **14% số lần kiểm tín hiệu không bao giờ chạy**, âm thầm.

    BẰNG CHỨNG SỰ CỐ LÀ THOÁNG QUA: gom 90 lần hỏng theo cửa sổ 60 giây được 51
    cụm; các cụm lớn cho thấy nhiều chiến lược KHÁC NHAU cùng hỏng trên CÙNG một
    symbol trong cùng khoảnh khắc. Khác chiến lược nhưng cùng symbol, cùng lúc →
    nguyên nhân ở TERMINAL, không ở logic. Chu kỳ trước và sau vẫn fetch được.

    NGOẠI LỆ CŨNG PHẢI BẮT: `copy_rates_from_pos` có thể NÉM thay vì trả `None`.
    Bản đầu bên XAUUSD không bọc `try`, nên ngoại lệ bay thẳng ra ngoài và làm gãy
    CẢ CHU KỲ — vòng thử lại nằm ngay bên dưới nhưng không bao giờ chạy tới.

    KHÔNG ĐỔI KẾT QUẢ BACKTEST: khi đồng hồ không phải `RealClock` (tức đang
    backtest/SimBroker), hàm trả `None` NGAY, không retry và không `sleep`. Dữ liệu
    backtest tất định nên gọi lại chắc chắn ra cùng kết quả, và `sleep` trong vòng
    lặp hàng chục nghìn chu kỳ sẽ treo backtest. Nhờ vậy parity giữ nguyên tuyệt đối.
    """
    import time as _time

    from src.python.core.infra.clock import RealClock, get_clock

    can = count if min_bars is None else min_bars

    def _enough_bars(r) -> bool:
        return r is not None and len(r) >= can

    def _fetch_once():
        """Một lượt fetch. NGOẠI LỆ = KHÔNG CÓ NẾN, không phải sự cố chết người."""
        try:
            return mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        except Exception as exc:                                   # noqa: BLE001
            _fetch_retry_stats["ngoai_le"] = _fetch_retry_stats.get("ngoai_le", 0) + 1
            log_fetch_failure_throttled(
                tag, symbol, f"copy_rates_from_pos NÉM LỖI: {exc}")
            return None

    rates = _fetch_once()
    if _enough_bars(rates):
        return rates

    n0 = 0 if rates is None else len(rates)
    _fetch_retry_stats["lan_hong"] += 1

    if not isinstance(get_clock(), RealClock):
        log_fetch_failure_throttled(
            tag, symbol, f"copy_rates_from_pos trả về {n0}/{can} bar")
        return None

    for attempt, waited in enumerate(wait_seconds, start=1):
        _time.sleep(waited)
        rates = _fetch_once()
        if _enough_bars(rates):
            _fetch_retry_stats["cuu_duoc"] += 1
            from src.python.utils.logger import log

            log(f"[{tag}] fetch {symbol} trả {n0}/{can} bar, thử lại lần {attempt} "
                f"(sau {waited}s) THÀNH CÔNG — chu kỳ này KHÔNG bị bỏ lỡ. "
                f"(cứu được {_fetch_retry_stats['cuu_duoc']}/"
                f"{_fetch_retry_stats['lan_hong']} lần hỏng từ lúc khởi động)")
            return rates

    log_fetch_failure_throttled(
        tag, symbol,
        f"copy_rates_from_pos trả về {n0}/{can} bar, thử lại "
        f"{len(wait_seconds)} lần đều hỏng")
    return None


def load_m1(symbol: str, mt5=None, *, n_bars: int = DEFAULT_BARS
            ) -> Optional[pd.DataFrame]:
    """Nến M1 gần nhất từ MT5, CÙNG HÌNH DẠNG với `fx_data.load_m1`.

    Trả `None` khi không lấy được — bên gọi quyết định fallback. KHÔNG ném lỗi vì
    đây là đường dữ liệu, và một lần MT5 chớp tắt không nên làm sập vòng lặp; nhưng
    cũng KHÔNG trả DataFrame rỗng, vì rỗng sẽ lặng lẽ thành "không có tín hiệu".
    """
    if mt5 is None:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except ImportError:
            return None
    try:
        mt5.symbol_select(symbol, True)
    except Exception:
        # `symbol_select` hỏng KHÔNG phải lý do bỏ cuộc: symbol có thể đã nằm sẵn
        # trong Market Watch. Cứ thử fetch, `copy_rates_retry` sẽ nói kết quả thật.
        pass
    # `min_bars=1` chứ không phải `n_bars`: đây là đường DỮ LIỆU, nó chỉ cần biết
    # "có nến hay không". Đòi đủ 200.000 nến sẽ coi một terminal mới tải được 5.000
    # nến là HỎNG và ném đi toàn bộ số nến đó — trong khi 5.000 nến M1 đã đủ cho
    # chân dài nhất (96 nến H4 = 5.760 nến M1 · các chân khác ít hơn nhiều).
    #
    # Cổng chặn "không đủ dữ liệu" nằm ở tầng chiến lược, nơi biết cửa sổ của chính
    # nó; đặt ngưỡng ở đây là đặt sai chỗ.
    raw = copy_rates_retry(mt5, symbol, _timeframe_const(mt5), int(n_bars),
                           tag="FX-M1", min_bars=1)
    if raw is None or len(raw) == 0:
        return None

    df = pd.DataFrame(raw)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("time").sort_index()
    df = df[~df.index.duplicated(keep="last")]

    # ĐƠN VỊ SPREAD: MT5 trả ĐIỂM broker, parquet dùng ĐƠN VỊ GIÁ. Quy về đơn vị giá
    # để hai nguồn thay thế được cho nhau — xem docstring đầu file.
    point = 1e-5
    try:
        info = mt5.symbol_info(symbol)
        if info is not None and getattr(info, "point", 0):
            point = float(info.point)
    except Exception:
        pass
    # ⚠️ SPREAD TỪ MT5 THƯỜNG VÔ DỤNG — đo được 15/08/2026 trên tài khoản demo:
    # cột `spread` của nến LỊCH SỬ trả 0 ở phần lớn nến, nên trung vị = 0,000000.
    #
    # Để nguyên là thảm hoạ im lặng: `trade_lab.load_majors` tính chi phí bằng
    # `b["spread_usd"].median()`, nên chi phí thành **0** và mọi chân bỗng "có lãi".
    # Chi phí là nơi hệ này gần chết nhất — bỏ một lớp đã đo được là đảo dấu kết
    # luận (Sharpe +0,216 sau spread+commission nhưng −0,456 sau swap).
    #
    # Nên: spread không dùng được thì trả NaN, KHÔNG trả 0. NaN lan ra và làm phép
    # tính chi phí nổ; 0 thì lặng lẽ cho kết quả đẹp. Nguồn chi phí đúng cho live là
    # số ĐO THẬT từ `scripts/log_cross_spread.py`, không phải cột này.
    if "spread" in df.columns:
        sp = df["spread"].astype(float) * point
        if float(sp.median()) <= 0:
            from src.python.utils.logger import log_error
            log_error(f"MT5 trả spread = 0 cho {symbol} trên nến lịch sử — đặt NaN "
                      f"để phép tính chi phí NỔ thay vì âm thầm coi phí bằng 0. "
                      f"Dùng số đo từ scripts/log_cross_spread.py.")
            df["spread_usd"] = np.nan
        else:
            df["spread_usd"] = sp
    else:
        df["spread_usd"] = np.nan

    df["volume"] = df.get("tick_volume", pd.Series(index=df.index, dtype=float))
    return df[["open", "high", "low", "close", "spread_usd", "volume"]]


def freshness(df: pd.DataFrame, now: Optional[pd.Timestamp] = None) -> float:
    """Nến mới nhất cũ bao nhiêu GIỜ. Dùng để chặn giao dịch trên dữ liệu ôi."""
    if df is None or df.empty:
        return float("inf")
    # Chỉ mục nến ở đây là UTC NAIVE (khớp `fx_data.load_m1`), nên mốc so sánh cũng
    # phải naive. Trộn naive với tz-aware là `TypeError` — và nếu ai đó "sửa" bằng
    # cách bỏ qua lỗi thì hàm trả `inf` và hệ tưởng dữ liệu luôn ôi.
    t = pd.Timestamp(now) if now is not None else pd.Timestamp.utcnow()
    if t.tzinfo is not None:
        t = t.tz_convert(None)
    last = df.index.max()
    if getattr(last, "tzinfo", None) is not None:
        last = last.tz_convert(None)
    return float((t - last).total_seconds() / 3600.0)
