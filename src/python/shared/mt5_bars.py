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

from datetime import datetime, timezone
from typing import Dict, Optional

import numpy as np
import pandas as pd

# Số nến M1 lấy về cho mỗi lần gọi. 200.000 nến M1 ≈ 5 tháng giao dịch — thừa cho
# cửa sổ dài nhất đang dùng (chân H4 cần 96 nến H4 = 5.760 nến M1) và vẫn nhanh.
DEFAULT_BARS = 200_000

# ═══════════════════════════════════════════════════════════════════════════════
# MÚI GIỜ: MT5 TRẢ GIỜ MÁY CHỦ, PARQUET LÀ UTC — PHẢI QUY ĐỔI
#
# LỖI PHÁT HIỆN 22/08/2026 (kiểm toán chéo từ hệ `hệ một-tài-sản`)
# ═══════════════════════════════════════════════════════════════════════════════
# `load_m1()` làm `pd.to_datetime(rates["time"], unit="s")` rồi trả luôn. Nhưng
# `rates["time"]` của MT5 mang **giờ MÁY CHỦ** (FTMO/MetaQuotes chạy giờ Đông Âu:
# UTC+3 mùa hè, UTC+2 mùa đông), trong khi `fx_data._load_m1_parquet` trả **UTC**
# — và docstring của `fx_data.load_m1` khai cả hai nhánh đều "index UTC naive".
#
# Hai nguồn vì thế LỆCH 2-3 GIỜ, và cả module này tồn tại để bảo đảm "hai nguồn
# cho ra CÙNG một hình dạng dữ liệu — cùng tên cột, cùng đơn vị, cùng múi giờ".
#
# HẬU QUẢ ĐO ĐƯỢC, theo thứ tự nghiêm trọng:
#
# 1. chân hồi quy trên cặp chéo (H1) chặn theo giờ: `EXECUTION_WINDOW_UTC = 10..16`,
#    `FORBIDDEN_HOURS_UTC = 20..23`, đọc `ts.hour` của chỉ mục nến. Ở backtest `ts`
#    là UTC nên cửa sổ đúng; ở live `ts` là giờ máy chủ nên cửa sổ THẬT chạy vào
#    **07-13 UTC** và giờ bị cấm THẬT là **17-20 UTC**. Chân này giao dịch đúng
#    những giờ mà nghiên cứu đã loại, và bị cấm ở những giờ nó muốn vào.
# 2. `fx_data.build_bars("4h")` và `fx_data.daily_bars()` gộp theo
#    `origin="start_day"` trên chỉ mục. Lệch 2-3 giờ ⟹ BIÊN nến H4/D1 lệch ⟹ bốn
#    chân H4 và ba chân D1 nhìn một chuỗi nến khác hẳn chuỗi backtest đã kiểm định.
#    (Khung M30/H1 KHÔNG bị: lệch nguyên giờ không đổi lưới 30 phút/1 giờ.)
# 3. `freshness()` so `pd.Timestamp.utcnow()` với nến cuối. Nến cuối mang giờ máy
#    chủ nên LỚN HƠN utcnow 2-3 giờ ⟹ tuổi dữ liệu ra ÂM ⟹ cổng chặn dữ liệu ôi
#    không bao giờ kích hoạt cho tới khi dữ liệu đã cũ hơn 2-3 giờ. Đúng lớp bảo
#    vệ mà module này được viết ra để dựng.
#
# Máy chủ có DST nên offset KHÔNG phải hằng số: mọi cách vá bằng một con số cứng
# sẽ đúng nửa năm và sai nửa năm còn lại.
SERVER_DST_OFFSET_H = 3      # EEST — chủ nhật cuối tháng 3 -> chủ nhật cuối tháng 10
SERVER_STD_OFFSET_H = 2      # EET  — phần còn lại của năm

# Ngưỡng tin cậy khi ĐO offset bằng tick. Ngoài dải này thì tick đã cũ (cuối tuần,
# terminal mất kết nối) và phép trừ không còn đo múi giờ nữa — rơi về lịch DST.
_OFFSET_MEASURE_MAX_H = 6.5
_OFFSET_CACHE_TTL_S = 1800.0
_offset_cache: Dict[str, tuple] = {}


def _last_sunday(year: int, month: int) -> datetime:
    """Chủ nhật cuối cùng của tháng — mốc chuyển giờ châu Âu."""
    d = datetime(year, month, 31, tzinfo=timezone.utc)
    while d.month != month:
        d = d.replace(day=d.day - 1)
    return d - pd.Timedelta(days=(d.weekday() + 1) % 7).to_pytimedelta()


def dst_calendar_offset_hours(now_utc: Optional[datetime] = None) -> int:
    """Offset giờ máy chủ theo LỊCH giờ Đông Âu — phương án dự phòng khi không đo được.

    EEST (UTC+3) từ 01:00 UTC chủ nhật cuối tháng 3 tới 01:00 UTC chủ nhật cuối
    tháng 10; còn lại EET (UTC+2).
    """
    t = now_utc or datetime.now(timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    start = _last_sunday(t.year, 3) + pd.Timedelta(hours=1).to_pytimedelta()
    end = _last_sunday(t.year, 10) + pd.Timedelta(hours=1).to_pytimedelta()
    return SERVER_DST_OFFSET_H if start <= t < end else SERVER_STD_OFFSET_H


def server_offset_hours(mt5, symbol: str, now_utc: Optional[datetime] = None) -> int:
    """Chênh lệch GIỜ MÁY CHỦ − UTC, tính bằng giờ nguyên.

    ĐO trước, LỊCH sau. Đo bằng `symbol_info_tick().time` là cách duy nhất đúng cho
    MỌI broker (không phải broker nào cũng chạy giờ Đông Âu); lịch DST chỉ là lưới
    an toàn cho lúc tick không dùng được — cuối tuần, terminal chưa kết nối, hoặc
    symbol chưa vào Market Watch.

    Cache 30 phút cho mỗi symbol: hàm này bị gọi mỗi chu kỳ × mỗi công cụ, còn
    offset thì chỉ đổi hai lần mỗi năm. Cache có TTL chứ không vĩnh viễn, vì một
    tiến trình live chạy liên tục qua mốc chuyển giờ phải tự nhận ra.
    """
    import time as _time

    t_now = now_utc or datetime.now(timezone.utc)
    if t_now.tzinfo is None:
        t_now = t_now.replace(tzinfo=timezone.utc)
    cached = _offset_cache.get(symbol)
    if cached is not None and (_time.time() - cached[1]) < _OFFSET_CACHE_TTL_S:
        return int(cached[0])

    off = dst_calendar_offset_hours(t_now)
    try:
        tick = mt5.symbol_info_tick(symbol)
        epoch = int(getattr(tick, "time", 0) or 0)
        if epoch > 0:
            # `tick.time` là epoch nhưng ĐÃ mang giờ máy chủ (xem
            # `core/infra/broker_time.py`), nên `utcfromtimestamp` cho đúng giờ
            # trên chart MT5 — không chuyển múi giờ thêm lần nữa.
            srv_wall = datetime.fromtimestamp(epoch, tz=timezone.utc)
            diff_h = (srv_wall - t_now).total_seconds() / 3600.0
            if abs(diff_h) <= _OFFSET_MEASURE_MAX_H:
                off = int(round(diff_h))
    except Exception:
        pass
    _offset_cache[symbol] = (off, _time.time())
    return int(off)


def reset_offset_cache() -> None:
    """Xoá cache offset — gọi ở đầu mỗi lượt backtest/test để không rò rỉ giữa các lượt."""
    _offset_cache.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# SỔ TUỔI DỮ LIỆU — nguyên liệu cho cổng chặn dữ liệu ôi
# ═══════════════════════════════════════════════════════════════════════════════
# `freshness()` dưới đây tồn tại từ 15/08/2026 và hai docstring trong `fx_data.py`
# khai rằng cổng chặn dữ liệu ôi nằm ở `engine._build_plan`. Rà 22/08/2026:
# `grep -rn "freshness("` toàn repo chỉ thấy ĐÚNG định nghĩa hàm và hai dòng
# docstring đó — **lớp bảo vệ được mô tả chưa bao giờ tồn tại**. Đúng họ lỗi tệ
# nhất: một cổng an toàn chỉ có trên giấy, mà người đọc tài liệu lại tin là có.
#
# Vấn đề khi wire nó vào: `freshness()` nhận một DataFrame, còn `_build_plan` không
# giữ DataFrame nào — nến được nạp sâu bên trong `portfolio.live_targets()` cho 27
# chân. Gọi lại `load_m1` cho 27 công cụ chỉ để đo tuổi là 27 × 200.000 nến, tức
# trả giá bằng cả chu kỳ.
#
# Nên: GHI SỔ ngay tại chỗ nến vừa được nạp (không thêm một lần đọc nào), rồi
# `_build_plan` chỉ đọc sổ. `fx_data.load_m1()` gọi `note_bars()` cho CẢ HAI nhánh
# — MT5 và parquet — vì nhánh parquet chính là tình huống nguy hiểm nhất: nó trả
# một DataFrame hoàn toàn hợp lệ của tháng trước.
_LAST_BAR_UTC: Dict[str, pd.Timestamp] = {}

# Ngưỡng chặn: nến mới nhất cũ hơn mức này thì KHÔNG mở/tăng phơi nhiễm.
#
# Chọn 2 giờ, không chặt hơn, vì hai lý do đo được:
#   · Bình thường nến M1 về mỗi phút; ngay cả cross mỏng (AUDCAD, NZDCAD) cũng
#     không đứng 2 giờ không tick trong giờ giao dịch. Ngưỡng chặt hơn sẽ chặn oan.
#   · Sự cố mà cổng này sinh ra để bắt được đo ở mức **28 NGÀY** (15/08/2026,
#     parquet cũ 28 ngày trên VPS). 2 giờ bắt được nó với biên 300 lần.
# Thị trường đóng cửa thì tuổi vượt ngưỡng và cổng chặn entry — đúng hành vi muốn
# có, và vô hại vì lúc đó không có gì để vào.
STALE_MAX_AGE_H = 2.0


def note_bars(symbol: str, df: Optional[pd.DataFrame]) -> None:
    """Ghi lại nhãn nến MỚI NHẤT vừa nạp cho `symbol`. Không tốn thêm lần đọc nào."""
    if df is None or len(df) == 0:
        return
    try:
        last = pd.Timestamp(df.index.max())
        if last.tzinfo is not None:
            last = last.tz_localize(None)
        _LAST_BAR_UTC[symbol] = last
    except Exception:
        return


def staleness(now: Optional[pd.Timestamp] = None) -> Dict[str, float]:
    """Tuổi (GIỜ) của nến mới nhất từng nạp, theo từng công cụ."""
    t = pd.Timestamp(now) if now is not None else pd.Timestamp.utcnow()
    if t.tzinfo is not None:
        t = t.tz_localize(None)
    return {sym: float((t - last).total_seconds() / 3600.0)
            for sym, last in _LAST_BAR_UTC.items()}


def stale_symbols(max_age_h: float = STALE_MAX_AGE_H,
                  now: Optional[pd.Timestamp] = None) -> Dict[str, float]:
    """Công cụ có dữ liệu ÔI hơn `max_age_h` — rỗng nghĩa là mọi thứ đều tươi."""
    return {s: age for s, age in staleness(now).items() if age > float(max_age_h)}


def reset_staleness() -> None:
    """Xoá sổ tuổi dữ liệu — gọi đầu mỗi lượt backtest/test."""
    _LAST_BAR_UTC.clear()

# BẬC GIẢM DẦN số nến khi terminal không trả nổi mức đang xin.
#
# LỖI ĐÃ SỬA 19/08/2026 — MỘT CÔNG CỤ HỎNG VĨNH VIỄN, MỖI GIỜ BA DÒNG LỖI
# =======================================================================
# Nhật ký VPS 18/08 lặp lại y nguyên mỗi giờ, suốt cả ngày, chỉ với EURUSD:
#
#     [FX-M1] fetch dữ liệu MT5 thất bại/không đủ bar cho EURUSD
#             (copy_rates_from_pos trả về 0/1 bar, thử lại 2 lần đều hỏng)
#     ⚠️ DỮ LIỆU CŨ · EURUSD → đang dùng PARQUET LỊCH SỬ
#     LỖI · dựng kế hoạch lệnh: Không tìm thấy M1 cho EURUSD
#
# Vòng thử lại CŨ chỉ lặp lại **đúng một yêu cầu 200.000 nến** sau 0,3s rồi 1,0s.
# Nó chữa được sự cố THOÁNG QUA (đúng thứ nó sinh ra để chữa), nhưng ở đây nguyên
# nhân không thoáng qua: terminal chỉ đơn giản KHÔNG CÓ 200.000 nến M1 cho công cụ
# đó — chưa tải xong lịch sử, hoặc bị chặn bởi "Max bars in chart" của chính
# terminal. Xin lại cùng con số đó thêm hai lần thì lần nào cũng hỏng, mãi mãi.
#
# Điều trái khoáy: hàm này khai `min_bars=1` — nó nói rõ "chỉ cần biết CÓ nến hay
# không". Vậy mà nó không bao giờ thử XIN ít hơn. Yêu cầu và điều kiện chấp nhận
# lệch nhau 200.000 lần.
#
# Các bậc dưới đây đi từ mức thừa thãi xuống mức tối thiểu dùng được. 5.760 nến M1 =
# 96 nến H4, tức cửa sổ dài nhất của cả danh mục; 2.000 là mức "có dữ liệu để tính
# gì đó" cho các chân M30/H1. Nến ít hơn mức chân cần thì cổng chặn ở TẦNG CHIẾN
# LƯỢC lo — nơi biết cửa sổ của chính nó, chứ không phải ở đây.
DEGRADE_BARS = (200_000, 50_000, 10_000, 2_000)


def _timeframe_const(mt5, minutes: int = 1):
    return getattr(mt5, "TIMEFRAME_M1")


_fetch_failure_last_logged: dict = {}


def log_fetch_failure_throttled(tag: str, symbol: str, reason: str,
                                min_interval_s: float = 300.0) -> None:
    """SSOT cảnh báo khi `mt5.copy_rates_from_pos()` thất bại / không đủ bar.

    CLONE từ `live_strategies/market_guards.py` của một hệ một-tài-sản, giữ nguyên tên hàm,
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
# Đếm chứ không chỉ vá: bản một-tài-sản ghi thẳng trong docstring rằng phép thăm dò 240
# lần liên tiếp KHÔNG tái hiện được lần hỏng nào, tức chưa chứng minh được "gọi lại
# sau 0,3s sẽ thành công". Bộ đếm này là cách để sau vài ngày có số liệu thật, thay
# vì để một bản vá không ai kiểm chứng nằm mãi trong code.
_fetch_retry_stats = {"lan_hong": 0, "cuu_duoc": 0, "ngoai_le": 0}


def copy_rates_retry(mt5, symbol: str, timeframe, count: int, *, tag: str,
                     min_bars: Optional[int] = None,
                     wait_seconds: tuple = (0.3, 1.0),
                     quiet: bool = False):
    """SSOT fetch nến có THỬ LẠI. Trả `rates` hoặc `None` (đã log giúp bên gọi).

    CLONE từ `live_strategies/market_guards.copy_rates_retry` của một hệ một-tài-sản.

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

    `quiet=True` vẫn thử lại và vẫn đếm thống kê, nhưng KHÔNG ghi log thất bại. Dành
    cho người gọi đã có phương án dự phòng và sẽ tự báo kết quả cuối cùng — xem
    `_fetch_degrading`. Không có cờ này thì một lượt giảm-dần bốn bậc sinh bốn dòng
    lỗi cho một sự cố duy nhất.
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
            if not quiet:
                log_fetch_failure_throttled(
                    tag, symbol, f"copy_rates_from_pos NÉM LỖI: {exc}")
            return None

    rates = _fetch_once()
    if _enough_bars(rates):
        return rates

    n0 = 0 if rates is None else len(rates)
    _fetch_retry_stats["lan_hong"] += 1

    if not isinstance(get_clock(), RealClock):
        if not quiet:
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

    if not quiet:
        log_fetch_failure_throttled(
            tag, symbol,
            f"copy_rates_from_pos trả về {n0}/{can} bar, thử lại "
            f"{len(wait_seconds)} lần đều hỏng")
    return None


def _fetch_degrading(mt5, symbol: str, n_bars: int):
    """Xin nến, GIẢM DẦN số lượng cho tới khi terminal trả được — hoặc hết bậc.

    Vì sao phải giảm dần chứ không xin lại cùng con số: xem `DEGRADE_BARS`.

    Chỉ bậc CUỐI CÙNG được phép ghi log thất bại. Các bậc giữa hỏng là chuyện bình
    thường (terminal mới chỉ tải một phần lịch sử), và ghi log cho từng bậc sẽ biến
    một bản vá chống spam thành bốn dòng thay cho một.
    """
    tf = _timeframe_const(mt5)
    steps = [c for c in DEGRADE_BARS if c <= n_bars] or [n_bars]
    if steps[0] != n_bars:
        steps.insert(0, n_bars)
    for i, count in enumerate(steps):
        last = i == len(steps) - 1
        # HAI vòng thử lại này giải quyết HAI giả thuyết khác nhau, và trộn chúng
        # làm hại cả hai:
        #
        #   `copy_rates_retry`  "terminal vừa chớp tắt"      -> chờ rồi xin LẠI
        #   giảm dần bậc        "terminal không có đủ nến"   -> xin ÍT HƠN
        #
        # Chờ thêm 1,3 giây rồi xin lại ĐÚNG con số vừa hỏng vì thiếu lịch sử không
        # mang thêm thông tin nào. Đo được lúc viết test: bốn bậc × ba lượt = 12 lần
        # gọi và ~5,2 giây `sleep` cho một lượt hỏng hoàn toàn — nhân bảy công cụ là
        # 36 giây chặn vòng lặp mỗi lần dựng kế hoạch. Vòng lặp chạy mỗi 5 giây.
        # Thử lại kèm `sleep` ở bậc ĐẦU (bắt sự cố thoáng qua) và bậc CUỐI (trước
        # khi tuyên bố hỏng hoàn toàn thì chờ thêm một nhịp là đáng). Các bậc GIỮA
        # không chờ: chúng chỉ đang thăm dò xem terminal có bao nhiêu nến.
        raw = copy_rates_retry(mt5, symbol, tf, count, tag="FX-M1", min_bars=1,
                               quiet=not last,
                               wait_seconds=(0.3, 1.0) if (i == 0 or last) else ())
        if raw is not None and len(raw) > 0:
            if i:
                # Bậc thấp hơn CÓ chạy được -> nói rõ hệ đang chạy trên bao nhiêu
                # nến. Đây là dòng phân biệt "terminal chưa tải xong lịch sử" với
                # "terminal hỏng", và không có nó thì hệ chạy trên mẫu ngắn mà
                # không ai biết là ngắn.
                from src.python.utils.logger import log

                log(f"[FX-M1] {symbol}: terminal không trả nổi {steps[0]:,} nến, "
                    f"đã hạ xuống {count:,} và lấy được {len(raw):,} nến. "
                    f"Chân dài nhất cần 5.760 nến M1 — "
                    f"{'ĐỦ' if len(raw) >= 5760 else 'CHƯA ĐỦ, mở biểu đồ M1 để ép tải'}.")
            return raw
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
    raw = _fetch_degrading(mt5, symbol, int(n_bars))
    if raw is None or len(raw) == 0:
        return None

    df = pd.DataFrame(raw)
    # QUY VỀ UTC. `rates["time"]` mang giờ MÁY CHỦ; parquet là UTC; và cả module này
    # tồn tại để hai nguồn thay thế được cho nhau. Xem khối "MÚI GIỜ" đầu file cho
    # ba hậu quả đo được của việc bỏ dòng này (cửa sổ giờ của chân hồi quy trên cặp chéo
    # lệch 3 giờ, biên nến H4/D1 lệch, cổng dữ liệu ôi không bao giờ kích hoạt).
    off_h = server_offset_hours(mt5, symbol)
    df["time"] = pd.to_datetime(df["time"].astype("int64") - off_h * 3600, unit="s")
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
            df["spread_usd"] = _live_spread_fallback(symbol, point, len(df))
        else:
            df["spread_usd"] = sp
    else:
        df["spread_usd"] = _live_spread_fallback(symbol, point, len(df))

    df["volume"] = df.get("tick_volume", pd.Series(index=df.index, dtype=float))
    return df[["open", "high", "low", "close", "spread_usd", "volume"]]


# Spread ĐO ĐƯỢC gần nhất theo công cụ, dùng khi `symbol_info().spread` chớp về 0.
# Chỉ chứa số đã ĐO — không có giá trị mặc định nào được nạp sẵn vào đây, vì một
# hằng số bịa ra chính là thứ cả module này tồn tại để ngăn.
_LAST_GOOD_SPREAD: Dict[str, float] = {}

# Lần cuối đã NÓI về spread thay thế của từng công cụ, theo `time.time()`.
#
# Hàm này được gọi mỗi lần nạp nến, tức nhiều lần mỗi giây khi nhiều chân cùng dựng
# kế hoạch. Đo 19:14 ngày 20/08/2026: dòng `[SPREAD] EURUSD ...` chiếm 14 trong 15
# dòng cuối của nhật ký và đẩy mọi dòng có ích ra ngoài màn hình — đúng họ lỗi mà
# CLAUDE.md gọi là "sửa từ GỐC ở điểm ghi log". Trạng thái ổn định thì nói MỘT LẦN
# mỗi 30 phút; đổi trạng thái thì nói NGAY.
#
# CHỈ CÓ HAI TRẠNG THÁI, và ranh giới nằm ĐÚNG chỗ này: `measured` (còn số đo, dù
# là spread sống hay số nhớ lần trước) và `nan` (mất hẳn nguồn đo). Bản đầu tách
# `live` với `cached` thành hai trạng thái riêng, và vì spread sống của EURUSD
# chớp 1/0 liên tục nên hai trạng thái đó ĐỔI QUA LẠI mỗi lần gọi — mỗi lần đổi
# lại "nói NGAY", tức bộ nén không nén được gì. Đo 19:20 ngày 20/08/2026: vẫn 2
# dòng mỗi giây sau khi đã thêm throttle.
#
# Bài học chung: nén theo trạng thái chỉ có tác dụng khi trạng thái ổn định hơn
# sự kiện. Chia trạng thái quá mịn thì chính nó thành nguồn nhiễu.
_SPREAD_LOG_AT: Dict[str, float] = {}
_SPREAD_LOG_KIND: Dict[str, str] = {}
_SPREAD_LOG_EVERY = 1800.0


def _say_once(symbol: str, kind: str, msg: str, *, level: str = "error") -> None:
    """Ghi `msg` nếu trạng thái ĐỔI, hoặc đã quá `_SPREAD_LOG_EVERY` giây.

    MỨC LOG PHẢI KHỚP Ý NGHĨA — sửa 21/08/2026
    ===========================================
    Bản đầu ghi MỌI nhánh ở mức ERROR, kể cả nhánh nói rằng mọi thứ đã được xử
    lý đúng ("dùng spread SỐNG", "dùng số ĐO GẦN NHẤT"). Hai hệ quả, và cái thứ
    hai nặng hơn:

      * Bộ soát log theo giờ đếm nó là LỖI MỚI mỗi lần câu chữ đổi.
      * Người vận hành học được rằng dòng ERROR ở đây thường vô hại — và đó
        chính là cách một dòng ERROR THẬT bị lướt qua.

    Chỉ nhánh cuối (không đo được gì, công cụ rụng khỏi rổ) mới là ERROR: lúc đó
    hệ thật sự mất một công cụ.
    """
    import time

    from src.python.utils import logger as _lg

    now = time.time()
    changed = _SPREAD_LOG_KIND.get(symbol) != kind
    if changed or now - _SPREAD_LOG_AT.get(symbol, 0.0) >= _SPREAD_LOG_EVERY:
        _SPREAD_LOG_KIND[symbol] = kind
        _SPREAD_LOG_AT[symbol] = now
        (_lg.log_error if level == "error" else _lg.log)(msg)


def _live_spread_fallback(symbol: str, point: float, n_bars: int):
    """Spread thay thế khi cột spread của nến LỊCH SỬ không dùng được.

    VÌ SAO KHÔNG TRẢ `np.nan` NHƯ BẢN CŨ — SỰ CỐ 20/08/2026
    =======================================================
    Ý định của bản cũ đúng: chi phí bằng 0 là dối trá nguy hiểm hơn chi phí bị
    thiếu, nên "để NaN cho phép tính NỔ" thay vì âm thầm coi phí bằng 0.

    Nhưng NaN không nổ ở chỗ ai cũng thấy. Nó đi thẳng vào
    `fx_data.build_bars`, nơi có `dropna(subset=[..., "spread_usd"])` — và XOÁ
    SẠCH mọi nến của công cụ đó. Đo lúc 18:53 ngày 20/08/2026:

        EURUSD   m1 = 200.000 nến   ->   H1 = 0 nến

    EURUSD nằm trong `FX_ALL`, mà `build_crosses` gộp 7 cặp USD bằng
    `DataFrame(px).dropna()`. Một cột rỗng làm giao của mọi cột thành RỖNG: cả
    rổ cặp chéo mất sạch dữ liệu, `evaluate_cross` gọi `idx[-1]` trên chỉ mục rỗng
    và ném `IndexError`, `_build_plan` hỏng — nên **toàn bộ các chân không vào được
    lệnh nào**, mỗi chu kỳ, im lặng, trong khi nhịp tim vẫn báo "MT5 OK".

    Một công cụ có dữ liệu spread kém đã hạ toàn bộ danh mục.

    ĐƯỜNG RA ĐÚNG: KHÔNG PHẢI 0, VÀ CŨNG KHÔNG PHẢI NaN
    ====================================================
    `symbol_info(symbol).spread` là spread THẬT tại thời điểm hỏi — cùng con số
    mà `engine._log_spread_survey` đã đối chiếu với bảng ước lượng mỗi 30 phút.
    Nó là một PHÉP ĐO, không phải giả định, nên dùng nó không vi phạm nguyên tắc
    "không bịa chi phí bằng 0".

    Điều nó KHÔNG làm được: nó là một con số cho mọi nến, nên biến động spread
    theo phiên biến mất. Vì thế nó chỉ hợp cho đường LIVE (nơi lệnh khớp ở
    spread HIỆN TẠI, không phải spread của tháng trước). Backtest vẫn đọc parquet
    — `fx_data.load_m1` từ chối cờ `FX_BARS_FROM_MT5` trong khối backtest — nên
    số liệu kiểm định không bị con số này chạm vào.

    Hết đường đo thì mới trả NaN: lúc đó đúng là KHÔNG BIẾT chi phí, và mất công
    cụ còn hơn giao dịch mù.
    """
    # ĐỌC NHIỀU LẦN, LẤY LẦN NÀO RA SỐ.
    #
    # `symbol_info(EURUSD).spread` trên feed demo này chớp 1 → 0 → 3 → 0 trong
    # vòng vài giây. Đọc đúng MỘT lần rồi kết luận "không đo được" là kết luận
    # dựa trên một mẫu duy nhất của một đại lượng nhiễu — và cái giá của kết
    # luận sai là mất cả công cụ, kéo theo rổ rổ cặp chéo và toàn bộ các chân.
    #
    # Năm lần đọc cách nhau 0,1 giây tốn nửa giây mỗi lần nạp nến, và chỉ chạy ở
    # nhánh spread lịch sử đã hỏng.
    pts = 0.0
    try:
        import time as _time

        import MetaTrader5 as mt5

        for attempt in range(5):
            info = mt5.symbol_info(symbol)
            got = float(getattr(info, "spread", 0) or 0) if info is not None else 0.0
            if got > 0:
                pts = got
                break
            if attempt < 4:
                _time.sleep(0.1)
    except Exception:
        pts = 0.0

    if pts > 0:
        val = pts * point
        _LAST_GOOD_SPREAD[symbol] = val
        _say_once(symbol, "measured", level="info", msg=
                  f"[SPREAD] {symbol}: cột spread của nến lịch sử = 0 trên "
                  f"{n_bars} nến — dùng spread SỐNG {pts:.0f} điểm = {val:.6f} "
                  f"đơn vị giá cho mọi nến. Đây là phép ĐO, không phải 0 bịa ra; "
                  f"nhưng nó phẳng theo phiên nên chỉ dùng cho LIVE.")
        return val

    # SPREAD SỐNG CŨNG BẰNG 0: giữ số ĐO GẦN NHẤT thay vì làm rụng công cụ.
    #
    # Đo 20/08/2026 trên chính tài khoản demo này: `symbol_info("EURUSD").spread`
    # trả 0 rồi 1 rồi 0 trong vòng vài giây. Không nhớ số cũ thì EURUSD rụng khỏi
    # rổ ở chu kỳ này và quay lại ở chu kỳ sau — rổ rổ cặp chéo đổi thành phần theo
    # nhịp ngẫu nhiên, tức chiến lược chạy trên một vũ trụ không xác định. Đó là
    # thứ tệ hơn cả hai lựa chọn ban đầu.
    cached = _LAST_GOOD_SPREAD.get(symbol)
    if cached is not None:
        _say_once(symbol, "measured", level="info", msg=
                  f"[SPREAD] {symbol}: spread sống trả 0 — dùng số ĐO GẦN NHẤT "
                  f"{cached:.6f} đơn vị giá. Giữ công cụ trong rổ để vũ trụ giao "
                  f"dịch không đổi theo từng chu kỳ.")
        return cached

    _say_once(symbol, "nan",
              f"[SPREAD] {symbol}: KHÔNG đo được spread — nến lịch sử, spread "
              f"sống và bộ nhớ đo gần nhất đều trống. Trả NaN: công cụ này sẽ "
              f"rụng khỏi rổ, và đó là kết quả ĐÚNG khi không biết chi phí.")
    return np.nan


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
