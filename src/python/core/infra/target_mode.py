"""TARGET-MODE sizing — SSOT quy đổi rủi ro sang cỡ lệnh cho mọi chiến lược.

"""

from __future__ import annotations

import math
from typing import Optional

# ---------------------------------------------------------------- FTMO sizing
# Mọi hằng số $1.500 (F_ATTACK 4%, F_BOOTSTRAP 7,5%, BOOTSTRAP_EQUITY, F_LOCKED,
# LOCK_EQUITY, HYSTERESIS_FLOOR, trần danh mục 6%/30%) ĐÃ XOÁ ngày 31/07 cùng
# với mô hình target-lock. Chúng thuộc về bài toán "nhân vốn từ tài khoản nhỏ",
# không có nghĩa gì trong môi trường FTMO vốn cố định.
#
# Giữ lại đúng những gì `ftmo.py` không sở hữu: quy đổi USD và guard margin.
from src.python.core.infra import ftmo as _ftmo   # noqa: E402

MAX_PORTFOLIO_OPEN_RISK_PCT = _ftmo.MAX_OPEN_RISK


def risk_fraction(equity: float, use_hysteresis: bool = False) -> float:
    """Tỷ lệ rủi ro mỗi lệnh — uỷ quyền hoàn toàn cho tầng FTMO.

    `use_hysteresis` giữ trong chữ ký cho tương thích ngược (target-lock cũ dùng
    nó); nay KHÔNG còn ý nghĩa vì không còn ngưỡng khoá lời theo equity. Tầng
    FTMO điều tiết risk theo TRẠNG THÁI DRAWDOWN và lãi tháng, không theo mốc
    tăng trưởng.

    Trả 0.0 khi tầng FTMO chặn (đã chạm ngưỡng khẩn cấp, hoặc đã đạt mục tiêu
    pha) — `size_for_risk()` sẽ cho lot 0 và chiến lược không vào lệnh.
    """
    try:
        return _ftmo.risk_fraction(float(equity))
    except Exception:
        # FAIL-CLOSED, không phải "mức sàn".
        #
        # Trả một mức risk DƯƠNG nghĩa là VẪN VÀO LỆNH trong lúc tầng FTMO đang hỏng
        # — trái thẳng thứ tự ưu tiên "Bảo vệ tài khoản > mọi thứ". Không đánh giá
        # được tuân thủ thì không được cấp ngân sách rủi ro nào cả.
        return 0.0


def risk_usd(equity: float) -> float:
    """USD risk cho lệnh kế tiếp."""
    # Hàm này là SSOT sizing gọi trực tiếp từ các chiến lược. Nếu đọc equity 
    # từ broker gặp lỗi không hợp lệ (None/chuỗi/NaN), fail-safe sẽ trả về 
    # 0 risk để tránh làm crash chu kỳ entry.
    try:
        eq = float(equity)
    except Exception:
        return 0.0
    if not math.isfinite(eq):
        return 0.0
    return eq * risk_fraction(eq)


def portfolio_risk_cap_pct(equity: float) -> float:
    """Trần TỔNG rủi ro của mọi vị thế đang mở — hằng số, không còn theo bậc equity.

    Bậc BOOTSTRAP 30% (vốn $1.500) đã bị xoá 31/07. Trong môi trường FTMO, trần
    danh mục phải nhỏ hơn ngưỡng daily-loss tự đặt: nếu MỌI vị thế đang mở cùng
    chạm SL trong một ngày thì tổn thất đúng bằng trần này. Ở 2%, kịch bản xấu
    nhất đó vẫn nằm dưới vùng cảnh báo 2% và cách rất xa giới hạn cứng 5%.
    """
    return _ftmo.MAX_OPEN_RISK


def check_portfolio_risk_cap(current_open_risk_usd: float, new_risk_usd: float, equity: float) -> bool:
    """Tổng rủi ro mở (Open Risk) của danh mục không vượt trần THEO BẬC equity."""
    if equity <= 0:
        return False
    total_risk_pct = (current_open_risk_usd + new_risk_usd) / equity
    return total_risk_pct <= portfolio_risk_cap_pct(equity)


# ĐO LẠI TRÊN FX 14/08/2026 — con số cũ 1,97x lấy từ VÀNG và sai hai lần.
#
# Bản kế thừa đặt `NOTIONAL_GAP_WARN_X = 1,97`, suy ra từ gap cuối tuần tệ nhất
# của XAUUSD trong 23 năm (2,539%). Hai chỗ sai khi mang sang hệ Forex:
#
#   1. SAI TÀI SẢN. Đo lại trên chính rổ đang giao dịch (9.648 lần gap, 27 công
#      cụ, nến M1 2015-2026): gap tệ nhất **2,138%** (CADJPY, 26/01/2026), phân
#      vị 99,9% chỉ 1,538%, trung vị 0,063%. Vàng gap rộng hơn FX.
#   2. SAI KHUNG QUY CHIẾU, và đây mới là chỗ chết người. Công thức
#      `notional <= 5% / gap` giả định TOÀN BỘ notional nằm trên MỘT công cụ —
#      đúng với một hệ một-tài-sản một tài sản, vô nghĩa với sổ nhiều chân hai chiều.
#
# Đo trực tiếp ở mức DANH MỤC cho kết quả ngược hẳn trực giác: thứ Hai là ngày
# AN TOÀN NHẤT trong tuần, không phải nguy hiểm nhất.
#
#     thứ    n     TB (bps)   σ      tệ nhất
#     Hai   341     +2,76    9,69    −32,34     <- ngày nhận gap
#     Ba    341     +1,92   10,32    −58,50
#     Tư    341     +2,79   11,48    −79,35     <- ngày tệ nhất thật sự
#     Năm   342     +2,12   12,05    −76,63
#     Sáu   342     +2,10   10,90    −61,03
#
# Lý do: gap đánh toàn bộ các chân cùng lúc, nhưng chúng nằm hai chiều trên 8 đồng tiền
# nên phần lớn cú sốc triệt tiêu nhau. Rủi ro thật nằm ở ngày thị trường đi MỘT
# CHIỀU kéo dài, không ở cú nhảy qua cuối tuần.
#
# Vì vậy ngưỡng ở đây neo vào **ngày tệ nhất ĐÃ QUAN SÁT của chính danh mục**
# (79,4 bps ở đòn bẩy 1,0), giống hệt cách `ftmo_leverage_policy.TAIL_BUFFER`
# làm — chứ không neo vào gap của một công cụ đơn lẻ:
#     notional_max = 5% / 0,794% ≈ 6,3x
# Trần đòn bẩy thực tế là 3,7x (do ràng buộc drawdown, chặt hơn nhiều), nên
# cảnh báo này gần như không bao giờ kêu — đúng như mong đợi cho một sổ đã
# đa dạng hoá.
NOTIONAL_GAP_WARN_X = 6.3

# Gap tệ nhất đo được của rổ FX, dùng trong thông điệp cảnh báo.
FX_WORST_WEEKEND_GAP_PCT = 2.138


def notional_gap_warning(notional_usd: float, equity: float) -> Optional[str]:
    """Cảnh báo khi tổng notional đủ lớn để một ngày xấu xoá tài khoản.

    VÌ SAO CÓ HÀM NÀY (04/08)
    --------------------------
    `ftmo.py` đã bàn về notional nhưng CHỈ theo góc ký quỹ, và kết luận đúng
    rằng "ràng buộc thật là drawdown, không phải ký quỹ". Góc còn thiếu là cú
    NHẢY GIÁ: `MAX_OPEN_RISK` đo khoảng cách tới dừng lỗ, mà gap thì NHẢY QUA
    dừng lỗ — nên trần rủi ro hiện có không ràng buộc gì trước một cú nhảy.

    Ở hệ Forex danh mục, nội dung cảnh báo đã đổi cùng với hằng số: nó không
    còn hỏi "một gap vàng có xoá tài khoản không" mà hỏi "ngày tệ nhất đã quan
    sát của CHÍNH danh mục này, nhân với notional hiện tại, có vượt giới hạn
    ngày 5% không".

    CHỈ CẢNH BÁO, KHÔNG CHẶN — có chủ đích. Việc chặn thuộc về
    `ftmo_leverage_policy.decide()`, nơi trần 3,7x đã bó chặt hơn ngưỡng này.
    Hàm này là lớp phát hiện bất thường: nếu nó kêu, nghĩa là tầng sizing đã
    tính ra thứ mà tầng đòn bẩy lẽ ra phải chặn — tức có lỗi, không phải có rủi ro.
    """
    if equity <= 0 or notional_usd <= 0:
        return None
    multiple = notional_usd / equity
    if multiple <= NOTIONAL_GAP_WARN_X:
        return None
    return (f"notional danh mục {multiple:.2f}x equity (${notional_usd:,.0f}) vượt "
            f"ngưỡng {NOTIONAL_GAP_WARN_X:.2f}x. Ngày tệ nhất đã quan sát của danh "
            f"mục (0,794%) sẽ thành lỗ ~{multiple * 0.00794:.2%} equity so với giới "
            f"hạn ngày 5%. Trần đòn bẩy 3,7x lẽ ra đã chặn trước mức này — kêu ở đây "
            f"nghĩa là tầng sizing và tầng đòn bẩy đang lệch nhau.")


def margin_safe_lot(mt5, symbol: str, order_type, price: float, lot: float,
                    spec, use_frac: float = 0.8):
    """Đảm bảo kích thước lot an toàn so với margin.
    
    Guard này thực hiện:
    - Giữ nguyên lot nếu margin cần thiết <= use_frac * free margin
    - Ngược lại scale xuống (floor theo lot step); trả 0.0 nếu không đủ
    Mỗi lần clip = LỆCH PARITY có chủ đích -> caller PHẢI log rõ.
    """
    if lot <= 0:
        return lot
    if not math.isfinite(lot):
        # Fail-closed: Nếu lot là NaN/Infinity, không được phép gửi 
        # volume không hợp lệ ra broker.
        return 0.0
    try:
        acc = mt5.account_info()
        free = float(getattr(acc, "margin_free", 0.0) or 0.0)
        need = mt5.order_calc_margin(order_type, symbol, lot, float(price))
        if need is None or need <= 0:
            return lot                      # không tính được → để broker quyết
        if need <= free * use_frac:
            return lot
        scaled = lot * (free * use_frac) / need
        return spec.floor_lot_for_risk(scaled)
    except Exception:
        return lot                          # fail-soft: không chặn trade vì guard lỗi


# ---------------------------------------------------------------- daily circuit breaker
# Breaker: Khi equity sụt qua ngưỡng so với đỉnh equity ĐẦU NGÀY -> chặn MỌI 
# entry mới đến hết ngày (positions vẫn được quản lý).
# Đây là protective halt khi gặp ngày thảm họa (flash crash, lỗi data). 
# Mỗi lần kích hoạt là lệch parity CÓ CHỦ ĐÍCH, phải log.
import json as _json
import threading as _threading
from datetime import datetime as _datetime, timezone as _timezone
from pathlib import Path as _Path

# Mốc "ngày" cần đọc qua `get_clock()` để backtest hoạt động đúng theo thời gian
# mô phỏng. Nếu dùng đồng hồ hệ thống, toàn bộ cửa sổ lịch sử backtest sẽ bị coi
# là cùng một ngày, khiến daily cap/circuit breaker không bao giờ reset.
from src.python.core.infra.clock import get_clock as _get_clock


def _now_utc() -> _datetime:
    return _get_clock().now()

# Khóa IO cho `daily_guard.json`. Giữ lock do `daily_entries_allowed()` 
# là chu trình đọc-quyết-định-ghi, và engine/GUI đọc `breaker_status()` từ thread khác.
_GUARD_LOCK = _threading.Lock()

# Ngưỡng -3% khớp ngưỡng "nguy hiểm" của `ftmo.py`.
#
# Lớp này CHỒNG với `ftmo.evaluate()` (chặn ở -4%) là CỐ Ý, không phải trùng lặp:
# hai lớp dùng hai baseline độc lập (risk_guard.day_start_equity ở đây, mốc
# ftmo_state ở kia). Nếu một baseline hỏng, lớp còn lại vẫn chặn.
DAILY_STOP_DD = 0.03     # −3% so với equity đầu ngày → ngừng entry mới
# Ngưỡng MỞ KHÓA thấp hơn ngưỡng KÍCH HOẠT (band hysteresis).
# Giúp bot tự mở lại nếu giá hồi phục trong cùng ngày, tránh flicker bật/tắt liên tục
# quanh một ranh giới. Mọi trip đều là auto-trip (DD thật).
DAILY_RECOVER_DD = 0.02  # equity hồi phục về <= -2% (từ -3% lúc trip) -> tự mở lại
_GUARD_FILE = None       # lazy — tranh import PROJECT_ROOT vong


def _guard_file():
    global _GUARD_FILE
    if _GUARD_FILE is None:
        from src.python.core.config import LIVE_DIR as _LD
        _GUARD_FILE = _Path(_LD) / "daily_guard.json"
    return _GUARD_FILE


def _read_guard_state(fp, log_fn=None):
    """Trạng thái cầu dao trong file. `{}` = chưa có file; `None` = ĐỌC LỖI.

    PHÂN BIỆT HAI TRƯỜNG HỢP NÀY LÀ TOÀN BỘ Ý NGHĨA CỦA HÀM
    -------------------------------------------------------
    Bản cũ gộp cả hai vào `st = {}`, và hệ quả của trường hợp thứ hai rất nặng:
    `st.get("day") != today` thành True -> baseline đặt lại theo equity HIỆN TẠI
    (đã sụt) và cờ `tripped` BỊ MẤT — tức **cầu dao tự mở lại trong im lặng** sau
    một lỗi I/O thoáng qua (đĩa bận, tranh chấp với GUI đang đọc cùng file,
    permission blip).

    Đúng họ lỗi đã được vá ở ĐƯỜNG GHI của `daily_entries_allowed` ("nếu gặp lỗi
    I/O thoáng qua thì breaker KHÔNG BAO GIỜ thực sự kích hoạt") nhưng còn nguyên
    ở ĐƯỜNG ĐỌC.

    File chưa tồn tại là chuyện BÌNH THƯỜNG (chu kỳ đầu của ngày) -> `{}` đúng.
    Mọi lỗi khác -> `None`, caller fail-closed CHO CHU KỲ NÀY và không đổi trạng
    thái: một lần đọc lỗi không nên khoá cả ngày, chu kỳ sau đọc lại được thì tự
    phục hồi (cùng cách xử lý equity không hợp lệ ở đầu hàm).
    """
    if not fp.exists():
        return {}
    try:
        # QUA SSOT `load_json` — nó thử bản `.bak` trước khi bỏ cuộc.
        # Một file bị cắt ngắn (kill/crash trước khi OS flush) có thể làm chặn
        # sạch entry cho tới khi có người xoá file bằng tay nếu không có .bak.
        from src.python.core.infra.state_store import load_json
        data = load_json(str(fp))
        if data is None:
            raise ValueError("load_json trả None (cả bản .bak đều hỏng)")
        return data
    except Exception as e:
        if log_fn:
            try:
                log_fn(f"⚡ [CIRCUIT BREAKER] File guard TỒN TẠI nhưng đọc lỗi "
                       f"({e!r}) — CHẶN entry chu kỳ này. Coi như 'chưa có file' "
                       f"sẽ xoá mất cờ tripped và đặt lại baseline theo equity "
                       f"đã sụt.")
            except Exception:
                pass
        return None


def _write_guard_state(fp, st: dict, log_fn=None) -> None:
    """Ghi trạng thái cầu dao QUA SSOT — fsync + bản `.bak` + khoá I/O.

    Đảm bảo an toàn dữ liệu, tránh trường hợp kill/crash để lại file rỗng.
    Nếu file hỏng, bot ngừng vào lệnh cho tới khi có người xoá file bằng tay,
    nên SSOT với bản .bak rất quan trọng để tự phục hồi.
    """
    fp.parent.mkdir(parents=True, exist_ok=True)
    from src.python.core.infra.state_store import save_json_atomic
    if not save_json_atomic(str(fp), st) and log_fn:
        try:
            log_fn(f"⚡ [CIRCUIT BREAKER] KHÔNG ghi được {fp.name} — trạng thái "
                   f"cầu dao có thể mất sau khi khởi động lại.")
        except Exception:
            pass


def _baseline_or_none(st: dict):
    """Mốc equity đầu ngày, hoặc `None` nếu nó hỏng.

    Bản cũ viết `float(st.get("start_equity", eq) or eq)`: một mốc bằng 0 (hoặc
    thiếu) lặng lẽ thành equity HIỆN TẠI, tức đo sụt giảm từ chính lúc này —
    và `eq <= eq*(1-3%)` không bao giờ đúng, nên cầu dao ngày bị vô hiệu hoàn
    toàn mà không có dòng log nào.

    Trả `None` để caller fail-closed thay vì đoán một mốc.
    """
    try:
        v = float(st.get("start_equity"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or v <= 0.0:
        return None
    return v


def daily_entries_allowed(equity: float, log_fn=None, login=None) -> bool:
    """Kiểm tra xem bot có được phép vào lệnh trong ngày hay không.
    
    False = breaker ĐÃ kích hoạt hôm nay (chặn entry mới, KHÔNG chạm position cũ).
    Lưu equity đầu ngày (persist qua restart); reset khi sang ngày mới theo
    GIỜ PRAHA — cùng ranh giới ngày với FTMO.
    Key theo account login để tránh trip breaker nhầm giữa các tài khoản khác nhau.
    """
    try:
      with _GUARD_LOCK:
        eq = float(equity)
        if not math.isfinite(eq) or eq <= 0.0:
            # Equity không hợp lệ (NaN/Infinity) HOẶC <= 0 -> fail-closed cho
            # chính chu kỳ này (không đổi trạng thái ngay). Một lần đọc lỗi
            # thoáng qua không nên khoá cả ngày; chu kỳ sau sẽ tự phục hồi.
            #
            # Vế `<= 0` là bắt buộc, không phải phòng xa: `0.0` là số HỮU HẠN
            # nên nó lọt qua `isfinite`, và nếu rơi vào đúng lúc sang ngày mới
            # thì `start_equity = 0.0` được ghi xuống đĩa. Từ đó mọi phép so
            # dừng lỗ bị vô hiệu (xem chú thích tại `_baseline_or_none`) và cầu
            # dao im lặng không nổ suốt cả ngày. MT5 trả equity 0 lúc mất kết
            # nối/đăng nhập lại là chuyện có thật.
            if log_fn:
                try:
                    log_fn(f"⚡ [CIRCUIT BREAKER] Equity không hợp lệ ({equity!r}) — "
                           f"CHẶN entry chu kỳ này để an toàn (không đổi trạng thái breaker).")
                except Exception:
                    pass
            return False
        # Ngày theo giờ Praha để đồng bộ với múi giờ của FTMO.
        # Cầu dao này và tầng FTMO phải có chung một ranh giới "hôm nay". Nếu
        # lệch múi giờ, cầu dao có thể tự reset trong khi FTMO vẫn tính dư địa lỗ.
        from src.python.core.infra import ftmo as _ftmo_ngay
        today = _ftmo_ngay.trading_day().isoformat()
        fp = _guard_file()
        st = _read_guard_state(fp, log_fn)
        if st is None:
            return False                      # đọc lỗi -> fail-closed chu kỳ này
        stale_login = login is not None and st.get("login") not in (None, login)
        if st.get("day") != today or stale_login:
            # Ưu tiên dùng cùng baseline với risk_guard để đảm bảo tính đồng bộ.
            # Fallback về `eq` nếu risk_guard chưa capture được (vd chu kỳ đầu tiên khởi động).
            start_equity = eq
            try:
                from src.python.core.infra import risk_guard as _risk_guard
                _rg_baseline = float(_risk_guard.state.get("day_start_equity", 0.0) or 0.0)
                if math.isfinite(_rg_baseline) and _rg_baseline > 0:
                    # Kiểm tính hợp lý: hai nguồn equity phải nói về cùng một tài khoản.
                    # Nếu baseline lệch quá 20% so với equity hiện tại, đó có thể là do
                    # khác tài khoản (ví dụ trong backtest, nhiều tài khoản trên một máy).
                    # Trường hợp đó tin `eq` (nguồn mà caller đang thực sự giao dịch) và log lại.
                    if abs(_rg_baseline - eq) / max(eq, 1e-9) > 0.20:
                        if log_fn:
                            try:
                                log_fn(f"⚠️ [CIRCUIT BREAKER] Baseline của risk_guard "
                                       f"({_rg_baseline:,.2f}) lệch >20% so với equity "
                                       f"đang giao dịch ({eq:,.2f}) — hai nguồn không cùng "
                                       f"một tài khoản. Dùng equity của caller làm mốc.")
                            except Exception:
                                pass
                    else:
                        start_equity = _rg_baseline
            except Exception:
                pass
            if not math.isfinite(start_equity) or start_equity <= 0.0:
                if log_fn:
                    log_fn(f"⚡ [CIRCUIT BREAKER] Không lập được mốc đầu ngày hợp lệ "
                           f"({start_equity!r}) — CHẶN entry, chưa ghi state.")
                return False
            st = {"day": today, "start_equity": start_equity, "tripped": False, "login": login}
            fp.parent.mkdir(parents=True, exist_ok=True)
            _write_guard_state(fp, st, log_fn)
            return True
        if st.get("tripped"):
            # Bỏ qua cờ `manual=True` của trạng thái cũ để tránh khóa entry vĩnh viễn
            # do cơ chế PAUSE bằng tay đã bị gỡ bỏ.
            start_chk = _baseline_or_none(st)
            if start_chk is None:
                if log_fn:
                    log_fn("⚡ [CIRCUIT BREAKER] Mốc equity đầu ngày hỏng — GIỮ chặn "
                           "entry (không tự mở lại bằng một mốc không đọc được).")
                return False
            if eq >= start_chk * (1.0 - DAILY_RECOVER_DD):
                st["tripped"] = False
                _write_guard_state(fp, st, log_fn)
                if log_fn:
                    try:
                        log_fn(f"✅ [CIRCUIT BREAKER] Equity hồi phục {eq:.2f} >= "
                               f"{start_chk:.2f}*(1-{DAILY_RECOVER_DD:.0%}) — TỰ ĐỘNG mở lại entry mới "
                               f"(hysteresis, đã trip ở ngưỡng -{DAILY_STOP_DD:.0%}).")
                    except Exception:
                        pass
                return True
            return False
        start = _baseline_or_none(st)
        if start is None:
            if log_fn:
                log_fn("⚡ [CIRCUIT BREAKER] Mốc equity đầu ngày hỏng/bằng 0 — CHẶN "
                       "entry để an toàn (không có mốc thì không đo được sụt giảm).")
            return False
        if eq <= start * (1.0 - DAILY_STOP_DD):
            st["tripped"] = True
            _write_guard_state(fp, st, log_fn)
            if log_fn:
                try:
                    log_fn(f"⚡ [CIRCUIT BREAKER] Equity {eq:.2f} <= {start:.2f}*(1-{DAILY_STOP_DD:.0%}) "
                           f"— CHẶN entry mới đến hết ngày (positions vẫn được quản lý; LỆCH PARITY có chủ đích).")
                except Exception:
                    pass
            return False
        return True
    except Exception as e:
        # Fail-closed: Nếu đang ghi trạng thái xuống đĩa mà gặp lỗi I/O,
        # chặn entry để an toàn thay vì cho phép vào lệnh (fail-open).
        if log_fn:
            try:
                log_fn(f"⚡ [CIRCUIT BREAKER] Lỗi khi kiểm tra/ghi breaker ({e!r}) — "
                       f"CHẶN entry để an toàn thay vì bỏ qua im lặng.")
            except Exception:
                pass
        return False


def breaker_status(equity: float = None) -> dict:
    """Trạng thái breaker cho GUI: {tripped, start_equity, dd_pct, day}."""
    try:
        st = _json.loads(_guard_file().read_text(encoding="utf-8"))
    except Exception:
        st = {}
    start = float(st.get("start_equity", 0) or 0)
    dd = 0.0
    if equity is not None and start > 0:
        dd = max(0.0, 1 - float(equity) / start)
    return {"tripped": bool(st.get("tripped", False)), "start_equity": start,
            "dd_pct": dd, "day": st.get("day")}


# XOÁ 31/07 — `manual_pause_today()` / `resume_entries()` (nút [PAUSE TRADING]
# của GUI) đã bị gỡ cùng toàn bộ nhóm vận hành thủ công. Cầu dao ngày nay chỉ
# do drawdown THẬT kích hoạt và tự phục hồi qua ngưỡng hysteresis; không còn
# cờ `manual` nào để người vận hành bật/tắt bằng tay.
