# -*- coding: utf-8 -*-
"""ops_console.py — DÒNG SỰ KIỆN VẬN HÀNH trên terminal, thay cho bảng điều khiển Tk.

VÌ SAO KHÔNG BÊ NGUYÊN GIAO DIỆN SANG CHỮ
==========================================
Giao diện đồ hoạ VẼ LẠI cùng một vùng màn hình, nên nó được phép hiển thị TRẠNG
THÁI: 27 hàng ma trận chiến lược, thẻ tài khoản, bảng vị thế, tất cả cập nhật mỗi 5
giây mà không tốn thêm chỗ. Terminal không có đặc quyền đó — mỗi dòng in ra là một
dòng cộng thêm vĩnh viễn.

Nên "console hoá" bằng cách in lại nội dung các thẻ sẽ cho ra thứ TỆ HƠN cả GUI:
vẫn dày đặc dữ liệu như cũ, mất khả năng ghi đè, và nuốt luôn những dòng có ích.
Nhật ký VPS 18/08/2026 là bằng chứng: 590 dòng cổng spread trong 49 phút cộng 1.344
dòng bảng spread mỗi ngày, trong đó phần người vận hành thật sự cần đọc là **hai
dòng** — lúc spread giãn và lúc nó về bình thường.

Nên module này đảo vai: console kể SỰ KIỆN và ĐỔI TRẠNG THÁI, còn trạng thái đầy đủ
đi vào `utils/ops_log` (JSONL) để truy vết về sau.

    console   sự kiện · đổi trạng thái · cảnh báo · nhịp tim   ← người, vài giây
    JSONL     mọi số đo, mọi trường, mọi lần                   ← máy, về sau

NĂM CÂU HỎI LÀ THƯỚC ĐO THIẾT KẾ
=================================
Người vận hành SSH vào lúc 3 giờ sáng, nhìn 20-30 dòng cuối, phải trả lời được:

    1. BOT còn sống không?               -> nhịp tim, mục BOT/MT5
    2. Thị trường đang ở trạng thái nào?  -> nhịp tim, mục regime
    3. BOT đang làm gì?                   -> dòng sự kiện gần nhất
    4. Rủi ro/vị thế hiện tại ra sao?     -> nhịp tim, mục equity/dd/pos/guard
    5. Vừa xảy ra chuyện gì quan trọng?   -> dòng cảnh báo, tô màu

Bất cứ thứ gì không phục vụ một trong năm câu đó thì không lên console.

BỘ NÉN SPAM Ở ĐÂY LÀ LỚP THỨ HAI, CÓ CHỦ Ý
===========================================
`engine._log_spread_gate` đã sửa đúng nguyên nhân gốc của đợt spam đã biết. Bộ nén
`_Squelch` dưới đây bắt các đợt CHƯA biết: nó so dấu vân tay của dòng log sau khi
XOÁ HẾT CHỮ SỐ, nên hai dòng chỉ khác nhau ở con số vẫn bị coi là một.

Đó chính là chỗ hai lớp khử lặp cũ của engine cùng thất bại: cả hai đều so nội dung
CÓ CHỨA số đo đổi mỗi tick. Sửa từng chỗ phát sinh là cần, nhưng một hệ có hàng trăm
điểm ghi log thì phải có một lớp chặn không phụ thuộc điểm ghi nào.
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

from src.python.core import ops_theme as T
from src.python.utils import ops_log

# Nhịp tim. 45 giây: đủ dày để một terminal im lặng quá một phút là dấu hiệu treo,
# đủ thưa để một ngày chỉ thêm ~1.900 dòng — khoảng một phần ba số dòng mà riêng
# bảng spread cũ sinh ra.
HEARTBEAT_SECONDS = 45.0

# Nén spam: cùng một dấu vân tay trong ngần này giây thì chỉ in dòng ĐẦU.
SQUELCH_WINDOW = 300.0
# In lại sau ngần này giây dù vẫn đang bị nén, kèm số dòng đã nén — để một sự cố dai
# dẳng không biến mất hoàn toàn khỏi console.
SQUELCH_REMIND = 900.0

_DIGITS = re.compile(r"[-+]?\d[\d.,:]*")
_MARKUP = re.compile(r"\[/?[^\]]*\]")


class _Squelch:
    """Nén các dòng log chỉ khác nhau ở con số.

    Dấu vân tay = nội dung đã xoá hết chữ số. Dòng `spread VƯỢT trần 3.0 bps: AUDCAD
    7.0, AUDCHF 8.85, …` và chính nó năm giây sau cho ra CÙNG một vân tay, nên dòng
    thứ hai bị nén — kể cả khi không ai sửa điểm ghi log sinh ra nó.

    Trả `(có_in, hậu_tố)`. `hậu_tố` khác rỗng khi đây là dòng nhắc lại của một đợt
    đang bị nén, để dòng in ra nói rõ nó đại diện cho bao nhiêu dòng.
    """

    def __init__(self) -> None:
        # vân tay -> [mốc lần in gần nhất, số dòng đã nén từ lúc đó]
        self._seen: Dict[str, list] = {}
        self._lock = threading.Lock()

    @staticmethod
    def fingerprint(msg: str) -> str:
        return _DIGITS.sub("#", msg)[:220]

    def allow(self, msg: str, now: Optional[float] = None):
        now = time.time() if now is None else now
        fp = self.fingerprint(msg)
        with self._lock:
            rec = self._seen.get(fp)
            if rec is None:
                self._seen[fp] = [now, 0]
                self._gc(now)
                return True, ""
            last, held = rec
            if now - last >= SQUELCH_REMIND:
                rec[0], rec[1] = now, 0
                return True, (f" (đã nén {held} dòng tương tự trong "
                              f"{int(SQUELCH_REMIND / 60)} phút qua)" if held else "")
            if now - last >= SQUELCH_WINDOW:
                rec[0], rec[1] = now, 0
                return True, (f" (đã nén {held} dòng tương tự)" if held else "")
            rec[1] = held + 1
            return False, ""

    def _gc(self, now: float) -> None:
        """Dọn vân tay cũ.

        Không dọn thì một tiến trình chạy hàng tuần giữ lại mọi vân tay từng thấy —
        rò rỉ bộ nhớ chậm ở đúng tầng không được phép gây sự cố.
        """
        if len(self._seen) < 2000:
            return
        cutoff = now - SQUELCH_REMIND * 2
        for key in [k for k, v in self._seen.items() if v[0] < cutoff]:
            self._seen.pop(key, None)


# ─────────────────────────────────────────── phân loại dòng log sẵn có
#
# VÌ SAO PHÂN LOẠI THAY VÌ VIẾT LẠI TỪNG ĐIỂM GHI LOG
# ====================================================
# Hệ có hàng trăm lệnh `log(...)` rải khắp engine, execution, strategies. Đổi hết
# sang một API sự-kiện-có-cấu-trúc trong một lượt là sửa hàng trăm chỗ trong đúng
# phần code quyết định tiền thật — rủi ro cao, mà lợi ích (nhóm + màu) đạt được bằng
# cách đọc tiền tố có sẵn.
#
# Các tiền tố này KHÔNG phải quy ước mới đặt ra: chúng đã nằm trong code từ trước
# (`🏦 [FTMO]`, `⚠️ [FX-M1]`, `🔍 [ĐỐI SOÁT]`, `LỖI ·`). Bảng dưới chỉ đọc thứ đã có.
#
# Điểm ghi log MỚI nên gọi thẳng `OpsConsole.event(..., category=...)`; bảng này là
# đường tương thích cho code cũ, không phải cơ chế được khuyến khích.
_CATEGORY_RULES = (
    ("risk", ("[FTMO", "[REWARD]", "[STATE_MACHINE]", "[CLOSE_ALL]", "[ALERT]",
              "LỚP PHÒNG THỦ", "KILL", "spread ", "cầu dao", "sụt vốn")),
    ("trading", ("[SỔ]", "[MANUAL]", "kế hoạch lệnh", "ORDER", "lệnh ", "vị thế",
                 "[ĐỐI SOÁT]")),
    ("market", ("[FX-M1]", "SPREAD THẬT", "DỮ LIỆU CŨ", "Thị trường", "regime",
                "REGIME", "phiên ")),
    ("ai", ("[AI", "[MoE", "[API_BUDGET]", "cổng tin", "news")),
    ("strategy", ("[CHIẾN LƯỢC]", "tín hiệu", "SIGNAL")),
    ("system", ("[Email]", "[SPLASH]", "MT5", "vòng lặp", "build", "Kết nối",
                "động cơ")),
)

# Mức nghiêm trọng đọc từ dấu hiệu đã có trong chính thông điệp.
_ERROR_MARKS = ("LỖI ·", "⛔", "🚨", "HỎNG", "VỠ", "XUNG ĐỘT", "thất bại",
                "KHÔNG dừng được", "KHÔNG gửi được", "KHÔNG ghi được",
                "KHÔNG đọc được", "KHÔNG đối soát được", "KHÔNG cập nhật được")
_WARN_MARKS = ("⚠️", "BỎ QUA", "VƯỢT", "💤", "⏳", "CŨ", "CHƯA", "TẮT")
_GOOD_MARKS = ("✅", "Kết nối thành công", "Hoàn tất", "THÀNH CÔNG", "đã gửi",
               "đã về dưới trần")


def classify(msg: str):
    """`(nhóm, mức)` của một dòng log tự do. Không khớp gì -> `("system", "info")`.

    Thứ tự kiểm MỨC là error -> good -> warn, không phải error -> warn -> good, và đó
    là chủ ý. Dòng "Hoàn tất đối chiếu khởi động: 3 lệnh CHƯA khớp sổ" chứa cả `Hoàn
    tất` lẫn `CHƯA`; nó là tin tốt (đối soát đã chạy xong) nên phải ra `good`. Để
    `warn` thắng thì mọi dòng tổng kết có kèm số liệu xấu đều bị tô hổ phách, và
    người vận hành mất khả năng phân biệt "đã xong" với "đang hỏng".
    """
    text = msg or ""
    level = "info"
    if any(m in text for m in _ERROR_MARKS):
        level = "error"
    elif any(m in text for m in _GOOD_MARKS):
        level = "good"
    elif any(m in text for m in _WARN_MARKS):
        level = "warn"
    for category, marks in _CATEGORY_RULES:
        if any(m in text for m in marks):
            return category, level
    return "system", level


def _fmt_money(value) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_pct(value) -> str:
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "n/a"


def _escape(text: str) -> str:
    """Chặn markup Rich trong nội dung log.

    Thông điệp log của hệ chứa `[FTMO]`, `[FX-M1]`, `[SỔ]` — Rich đọc chúng như thẻ
    định dạng, rồi ném `MarkupError` hoặc âm thầm ăn mất đoạn chữ đó. Đây là lỗi chỉ
    nổ trên ĐÚNG những dòng quan trọng nhất (mốc FTMO, sự cố dữ liệu), nên không thể
    để nó phụ thuộc vào việc ai đó nhớ escape ở từng điểm gọi.
    """
    return str(text).replace("[", r"\[")


class OpsConsole:
    """Bộ hiển thị vận hành. Là `log_callback` + `status_callback` của engine.

    KHÔNG giữ tham chiếu tới engine: nó chỉ nhận chuỗi log và ảnh chụp trạng thái.
    Nhờ vậy nó dùng được cho `run_cli`, cho script chẩn đoán, và cho test — và một
    lỗi hiển thị không bao giờ với tới được vòng lặp giao dịch.
    """

    def __init__(self, *, heartbeat_seconds: float = HEARTBEAT_SECONDS,
                 structured: bool = True, quiet: bool = False) -> None:
        self._console = _make_console()
        self._squelch = _Squelch()
        self._heartbeat_every = float(heartbeat_seconds)
        self._structured = bool(structured)
        self._quiet = bool(quiet)
        self._last_heartbeat = 0.0
        self._started_at = time.time()
        self._state: Dict[str, Any] = {}
        self._lock = threading.Lock()
        # Bộ đếm cho báo cáo tắt máy. Đếm ở đây chứ không đọc lại JSONL lúc tắt, vì
        # tắt máy là lúc dễ hỏng nhất (ổ đầy, tiến trình bị kill): một báo cáo dựng
        # từ bộ đếm trong RAM vẫn ra được khi đường đĩa đã hỏng.
        self._counts: Dict[str, int] = {}
        self._last_regime = ""
        self._suppressed = 0
        # Quyết định gần nhất của từng chân, để phát sự kiện khi nó ĐỔI. Bảng 27
        # hàng chỉ in một lần lúc khởi động; sau đó console chỉ nói về thay đổi.
        self._last_decision: Dict[str, str] = {}

    # ─────────────────────────────────────────── dòng sự kiện
    def event(self, message: str, *, category: Optional[str] = None,
              level: Optional[str] = None, **fields: Any) -> None:
        """In MỘT dòng sự kiện và ghi bản có cấu trúc.

        `category`/`level` để trống thì suy từ nội dung — xem `classify()`.
        """
        if category is None or level is None:
            guess_cat, guess_level = classify(message)
            category = category or guess_cat
            level = level or guess_level
        key = f"{category}.{level}"
        self._counts[key] = self._counts.get(key, 0) + 1

        if self._structured:
            ops_log.emit(category, "log", level=level, message=message, **fields)

        # Nén CHỈ ở tầng hiển thị, và CHỈ SAU khi đã ghi sổ. Sổ JSONL ở trên giữ đủ
        # mọi dòng, nên nén ở đây không làm mất dữ liệu — chỉ làm mất tiếng ồn. Đảo
        # thứ tự hai bước này là đánh mất chính những dòng cần cho việc truy vết.
        show, suffix = self._squelch.allow(message)
        if not show:
            self._suppressed += 1
            return
        if self._quiet and level in ("info", "good"):
            return
        self._write_line(category, level, message + suffix)

    def _write_line(self, category: str, level: str, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        cat_color = T.CATEGORY_COLOR.get(category, T.C_TEXT_MUT)
        lvl_color = T.LEVEL_COLOR.get(level, T.C_TEXT)
        self._print(f"[{T.C_TEXT_DIM}]{stamp}[/] "
                    f"[{cat_color}]{category.upper():<8}[/] "
                    f"[{lvl_color}]{_escape(message)}[/]")

    def log(self, message: str) -> None:
        """`log_callback` của engine trỏ vào đây."""
        self.event(str(message))

    # ─────────────────────────────────────────── trạng thái + nhịp tim
    def status(self, state: Dict[str, Any]) -> None:
        """`status_callback` của engine: giữ ảnh chụp mới nhất, phát nhịp tim khi tới hạn.

        Trạng thái KHÔNG được in ra mỗi lần cập nhật (5 giây một lần) — đó đúng là
        cái bẫy "GUI bằng chữ". Nó chỉ dùng cho nhịp tim theo lịch, cho các dòng
        đổi-trạng-thái, và cho báo cáo tắt máy.
        """
        with self._lock:
            self._state = dict(state or {})
        self._regime_change()
        self._strategy_changes()
        if time.time() - self._last_heartbeat >= self._heartbeat_every:
            self.heartbeat()

    def _regime_change(self) -> None:
        """Trạng thái thị trường đổi là sự kiện phải thấy NGAY, không chờ nhịp tim."""
        label = str((self._state.get("sentiment") or {}).get("regime") or "")
        if not label or label == self._last_regime:
            return
        prev, self._last_regime = self._last_regime, label
        if not prev:
            return          # lần đầu là khởi động, không phải một lần ĐỔI
        color = T.color_for_regime(label)
        self._print(f"[{T.C_TEXT_DIM}]{datetime.now():%H:%M:%S}[/] "
                    f"[{T.CATEGORY_COLOR['market']}]{'MARKET':<8}[/] "
                    f"TRẠNG THÁI ĐỔI  {_escape(prev)} → [{color}]{_escape(label)}[/]")
        ops_log.emit("market", "regime_change", previous=prev, current=label)

    def _strategy_changes(self) -> None:
        """Chân nào ĐỔI quyết định thì nói; 27 chân đứng yên thì im.

        VÌ SAO KHÔNG IN LẠI CẢ BẢNG
        ============================
        Bảng ma trận 27 hàng là thứ giao diện vẽ lại mỗi 5 giây mà không tốn chỗ. In
        nó ra console theo cùng nhịp cho 27 dòng × 720 lượt = ~19.000 dòng mỗi giờ,
        trong đó phần mang tin mới gần bằng không: một chân chuyển SCANNING ->
        ACTIVE là một sự kiện; một chân vẫn SCANNING không phải sự kiện nào.

        `REGIME OFF` được nói riêng vì nó trả lời đúng câu hỏi hay bị hỏi nhất khi
        bot im lặng nhiều giờ — "sao không có lệnh nào?".
        """
        try:
            from src.python.core import ops_view
            rows = ops_view.get_decision_matrix_rows(self._state)
        except Exception:
            return                     # tầng trình bày: hỏng thì im, không kéo theo ai
        first = not self._last_decision
        for row in rows:
            name = row.get("name")
            now_dec = str(row.get("decision") or "")
            prev = self._last_decision.get(name)
            self._last_decision[name] = now_dec
            if first or prev is None or prev == now_dec:
                continue
            level = {"ACTIVE": "good", "STOPPED": "warn",
                     "REGIME OFF": "warn"}.get(now_dec, "info")
            self.event(f"{name}: {prev} → {now_dec}"
                       + (f" (R {row.get('r')})" if row.get("r") not in (None, "—") else ""),
                       category="strategy", level=level,
                       strategy=name, previous=prev, decision=now_dec)

    def strategy_table(self, state: Optional[Dict[str, Any]] = None) -> None:
        """Bảng 27 chân, in ĐÚNG MỘT LẦN lúc khởi động.

        Sau dòng này console không in lại bảng nữa — thay đổi đi qua
        `_strategy_changes()`, và số đếm gọn nằm trong nhịp tim.
        """
        s = dict(state or self._state or {})
        try:
            from rich.table import Table

            from src.python.core import ops_view
            rows = ops_view.get_decision_matrix_rows(s)
        except Exception as exc:
            self.event(f"KHÔNG dựng được bảng chiến lược: {exc}",
                       category="strategy", level="error")
            return
        table = Table(box=None, pad_edge=False, show_edge=False,
                      header_style=T.C_TEXT_DIM)
        table.add_column("chân", style=T.C_TEXT, no_wrap=True)
        table.add_column("quyết định", no_wrap=True)
        table.add_column("R", justify="right", no_wrap=True)
        colors = {"ACTIVE": T.C_GREEN, "SCANNING": T.C_TEXT_MUT,
                  "REGIME OFF": T.C_AMBER, "STAND BY": T.C_TEXT_DIM,
                  "STOPPED": T.C_RED}
        for row in rows:
            dec = str(row.get("decision") or "")
            table.add_row(str(row.get("name")),
                          f"[{colors.get(dec, T.C_TEXT)}]{dec}[/]",
                          str(row.get("r") or ""))
        self._rule(f"CHIẾN LƯỢC · {len(rows)} chân")
        try:
            self._console.print(table)
        except Exception:
            for row in rows:
                self._print(f"  {row.get('name')}  {row.get('decision')}")
        if self._structured:
            ops_log.emit("strategy", "matrix_snapshot", rows=rows)

    # Nhịp tim IM khi không có gì đổi, tối đa bao lâu thì vẫn phải kêu một tiếng.
    #
    # ĐO 21/08/2026: nhịp 45 giây in 80 dòng mỗi giờ, và trong một mẫu 11 phút
    # thì 16/16 dòng giống hệt nhau trừ vài chữ số equity:
    #
    #     07:41:05 NHỊP MT5 OK · eq $100,199.05 · pnl $206.49 · dd 0.00% · pos 40 ...
    #     07:41:50 NHỊP MT5 OK · eq $100,196.48 · pnl $203.92 · dd 0.00% · pos 40 ...
    #     07:42:35 NHỊP MT5 OK · eq $100,192.17 · pnl $199.61 · dd 0.00% · pos 40 ...
    #
    # Ba dòng đó nói đúng MỘT điều: "vẫn sống, không có gì đổi". Nói điều đó 80
    # lần mỗi giờ thì mọi dòng CÓ ích bị đẩy khỏi màn hình — đúng họ lỗi mà
    # CLAUDE.md gọi là "sửa từ GỐC ở điểm ghi log".
    #
    # Bộ nén `_Squelch` không cứu được vì nó so dấu vân tay SAU KHI xoá chữ số,
    # mà nhịp tim vốn được miễn nén (nó là bằng chứng còn sống).
    #
    # Nên: sổ JSONL vẫn nhận ĐỦ 45 giây một bản ghi — không mất số liệu nào.
    # Console chỉ nhận dòng khi trạng thái VẬT CHẤT đổi, hoặc khi đã im quá lâu.
    HEARTBEAT_QUIET_SECONDS = 900.0

    def _heartbeat_fingerprint(self, mt5_ok, pos, regime, halted, spread_over,
                               active, live, dd_pct) -> tuple:
        """Những gì ĐỔI thì đáng nói; equity nhích vài đô thì không.

        `dd_pct` làm tròn về bậc 0,1 điểm phần trăm và VẪN nằm trong dấu vân tay:
        nhịp tim này mang khoảng cách tới hạn mức FTMO, và một con số rủi ro đang
        dịch chuyển là thứ phải nói ngay — khác hẳn equity dao động quanh chỗ cũ.
        """
        try:
            dd_bucket = round(float(dd_pct or 0.0), 1)
        except (TypeError, ValueError):
            dd_bucket = None
        return (bool(mt5_ok), int(pos), str(regime), bool(halted),
                int(spread_over), int(active), int(live),
                bool(self._state.get("market_closed")), dd_bucket)

    def heartbeat(self) -> None:
        """MỘT dòng trả lời cả năm câu hỏi. Xem docstring đầu file."""
        self._last_heartbeat = time.time()
        s = self._state
        g = s.get("guards") or {}
        mt5_ok = bool(s.get("mt5_connected"))
        pnl = s.get("daily_profit")
        pos = len(s.get("positions_list") or [])
        regime = str((s.get("sentiment") or {}).get("regime") or "n/a")
        halted = bool(g.get("breaker_tripped"))
        spread_over = len((g.get("spread") or {}).get("over") or {})

        parts = [
            f"[{T.C_GREEN if mt5_ok else T.C_RED}]MT5 {'OK' if mt5_ok else 'MẤT'}[/]",
            f"eq {_fmt_money(s.get('equity'))}",
            f"pnl [{T.color_for_pnl(pnl)}]{_fmt_money(pnl)}[/]",
            f"dd {_fmt_pct(g.get('dd_pct'))}",
            f"pos {pos}",
            f"regime [{T.color_for_regime(regime)}]{_escape(regime)}[/]",
            f"guard [{T.C_RED if halted else T.C_GREEN}]"
            f"{'DỪNG' if halted else 'AN TOÀN'}[/]",
        ]
        live = sum(1 for d in self._last_decision.values()
                   if d in ("SCANNING", "ACTIVE"))
        active = sum(1 for d in self._last_decision.values() if d == "ACTIVE")
        if self._last_decision:
            parts.append(f"chân {active} có lệnh / {live} sẵn sàng "
                         f"/ {len(self._last_decision)}")
        if spread_over:
            parts.append(f"[{T.C_AMBER}]spread {spread_over} vượt[/]")
        if s.get("market_closed"):
            parts.append(f"[{T.C_TEXT_DIM}]thị trường ĐÓNG[/]")
        if self._suppressed:
            parts.append(f"[{T.C_TEXT_DIM}]{self._suppressed} dòng đã nén[/]")

        fp = self._heartbeat_fingerprint(mt5_ok, pos, regime, halted,
                                         spread_over, active, live,
                                         g.get("dd_pct"))
        now = time.time()
        quiet_for = now - getattr(self, "_last_heartbeat_print", 0.0)
        changed = fp != getattr(self, "_last_heartbeat_fp", None)
        if changed or quiet_for >= self.HEARTBEAT_QUIET_SECONDS:
            if not changed:
                parts.append(f"[{T.C_TEXT_DIM}]không đổi {int(quiet_for // 60)}'[/]")
            self._last_heartbeat_fp = fp
            self._last_heartbeat_print = now
            self._print(f"[{T.C_TEXT_DIM}]{datetime.now():%H:%M:%S}[/] "
                        f"[{T.C_BLUE}]{'NHỊP':<8}[/] " + " · ".join(parts))
        if self._structured:
            ops_log.emit("system", "heartbeat", mt5=mt5_ok, equity=s.get("equity"),
                         daily_pnl=pnl, dd_pct=g.get("dd_pct"), positions=pos,
                         regime=regime, halted=halted, spread_over=spread_over,
                         market_closed=bool(s.get("market_closed")),
                         strategies_active=active, strategies_ready=live,
                         squelched=self._suppressed)

    # ─────────────────────────────────────────── báo cáo khởi động
    def boot_report(self, state: Optional[Dict[str, Any]] = None) -> None:
        """Ảnh chụp MỘT LẦN lúc khởi động: hệ đang chạy với cấu hình gì.

        Đây là thứ duy nhất trong module được phép in dạng bảng nhiều dòng, vì nó
        chạy đúng một lần. Sau nó, console chuyển hẳn sang dòng sự kiện.
        """
        s = dict(state or self._state or {})
        rows = _boot_rows(s)
        width = max((len(k) for k, _ in rows), default=12)
        self._rule("THE CHEOPARD FOREX · KHỞI ĐỘNG")
        for key, (value, color) in rows:
            self._print(f"  [{T.C_TEXT_DIM}]{key:<{width}}[/]  "
                        f"[{color}]{_escape(value)}[/]")
        self._rule("DÒNG SỰ KIỆN")
        if self._structured:
            ops_log.emit("system", "boot",
                         **{k.replace(" ", "_"): v for k, (v, _) in rows})

    # ─────────────────────────────────────────── báo cáo tắt máy
    def shutdown_report(self, reason: str = "") -> None:
        """Tổng kết phiên. Chạy được CẢ KHI đường đĩa đã hỏng — xem `self._counts`."""
        s = self._state
        g = s.get("guards") or {}
        up = int(time.time() - self._started_at)
        errors = sum(v for k, v in self._counts.items() if k.endswith(".error"))
        warns = sum(v for k, v in self._counts.items() if k.endswith(".warn"))
        open_pos = len(s.get("positions_list") or [])
        rows = [
            ("thời gian chạy", (f"{up // 3600}h {up % 3600 // 60:02d}m", T.C_TEXT)),
            ("lý do dừng", (reason or "cửa sổ đóng / Ctrl+C", T.C_TEXT_MUT)),
            ("equity cuối", (_fmt_money(s.get("equity")), T.C_TEXT)),
            ("lãi/lỗ ngày", (_fmt_money(s.get("daily_profit")),
                             T.color_for_pnl(s.get("daily_profit")))),
            ("sụt vốn ngày", (_fmt_pct(g.get("dd_pct")), T.C_TEXT)),
            ("lệnh đã đóng hôm nay", (len(s.get("closed_trades_today") or []),
                                      T.C_TEXT)),
            ("vị thế còn mở", (open_pos, T.C_AMBER if open_pos else T.C_TEXT)),
            ("cầu dao", ("ĐÃ NGẮT" if g.get("breaker_tripped") else "bình thường",
                         T.C_RED if g.get("breaker_tripped") else T.C_GREEN)),
            ("cảnh báo · lỗi", (f"{warns} · {errors}",
                                T.C_RED if errors else T.C_TEXT_MUT)),
            ("dòng log đã nén", (self._suppressed, T.C_TEXT_DIM)),
        ]
        width = max(len(k) for k, _ in rows)
        self._rule("TỔNG KẾT PHIÊN")
        for key, (value, color) in rows:
            self._print(f"  [{T.C_TEXT_DIM}]{key:<{width}}[/]  "
                        f"[{color}]{_escape(value)}[/]")
        # DÒNG QUAN TRỌNG NHẤT của cả báo cáo: tắt bảng điều khiển KHÔNG đóng lệnh.
        # Người vận hành phải biết mình vừa để lại cái gì trên thị trường mà từ giờ
        # không còn ai quản lý trailing/BE/time-stop.
        if open_pos:
            self._print(f"  [{T.C_RED}]!! {open_pos} vị thế VẪN MỞ và từ giờ KHÔNG "
                        f"CÓ hệ nào quản lý — đóng bằng tay hoặc chạy lại bot.[/]")
        self._rule("")
        if self._structured:
            ops_log.emit("system", "shutdown", reason=reason,
                         **{k.replace(" ", "_").replace("·", "va"): v
                            for k, (v, _) in rows})

    # ─────────────────────────────────────────── hạ tầng in
    def _print(self, markup: str) -> None:
        try:
            self._console.print(markup, highlight=False, soft_wrap=True)
        except Exception:
            # Console hỏng KHÔNG được làm chết vòng lặp giao dịch. Cùng nguyên tắc
            # với `logger._usable_stream`: tầng quan sát xuống cấp im lặng, phần
            # nghiệp vụ chạy tiếp.
            try:
                sys.stderr.write(_MARKUP.sub("", markup) + "\n")
            except Exception:
                pass

    def _rule(self, title: str) -> None:
        try:
            if title:
                self._console.rule(f"[{T.C_BLUE}]{title}[/]", style=T.C_BORDER)
            else:
                self._console.rule(style=T.C_BORDER)
        except Exception:
            self._print(f"-- {title} --")


def use_utf8_stdout() -> None:
    """Ép `stdout`/`stderr` sang UTF-8, bỏ qua ký tự không in được.

    VÌ SAO PHẢI GỌI SỚM, VÀ TỪ NHIỀU CHỖ
    =====================================
    Console Windows mặc định là cp1252. Mọi dòng có emoji hoặc chữ Việt có dấu ném
    `UnicodeEncodeError` ở đó — và đúng những dòng quan trọng nhất lúc khởi động là
    những dòng đó: mốc vốn FTMO, mốc lỗ ngày, cảnh báo dữ liệu cũ.

    Hàm là PUBLIC vì `_make_console()` gọi nó quá muộn cho một số đường: `argparse`
    in phần trợ giúp TRƯỚC khi bất cứ console nào được dựng, nên `ops_ctl --help` vẫn
    nổ. Bất cứ điểm vào nào in ra terminal đều phải gọi hàm này ở dòng đầu.

    `errors="replace"` để một ký tự không in được làm mất một KÝ TỰ, chứ không làm mất
    cả DÒNG — cùng lý do với `logger._usable_stream`.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _make_console():
    from rich.console import Console

    use_utf8_stdout()
    tty = False
    try:
        tty = bool(sys.stdout.isatty())
    except Exception:
        pass
    return Console(
        highlight=False,
        # `OPS_FORCE_COLOR` cho trường hợp chạy dưới dịch vụ/`nohup`: stdout không
        # phải TTY nên Rich bỏ hết màu — đúng lúc màu có ích nhất.
        force_terminal=True if os.getenv("OPS_FORCE_COLOR") else None,
        # KHÔNG để Rich rơi về 80 cột khi không có TTY: mặc định đó CẮT giữa thông
        # điệp, tức làm mất chữ trong tệp log đã chuyển hướng.
        width=None if tty else 200,
    )


def _boot_rows(s: Dict[str, Any]) -> list:
    """Các dòng của báo cáo khởi động: `(nhãn, (giá trị, màu))`.

    Đọc phòng thủ từng khoá qua `safe()` chứ không bằng một chuỗi `.get()`: báo cáo
    khởi động chạy TRƯỚC khi vòng lặp điền đủ trạng thái, nên nửa số khoá còn trống
    là chuyện bình thường — và một `AttributeError` ở đây sẽ chặn cả lần khởi động
    chỉ vì một dòng trang trí.
    """

    def safe(fn, default="n/a"):
        try:
            out = fn()
            return default if out in (None, "") else out
        except Exception:
            return default

    def n_strategies():
        from src.python.strategies import registry as REG
        return len(REG.STRATEGIES)

    def live_orders():
        from src.python.core.config import LIVE_ORDERS
        return bool(LIVE_ORDERS)

    def version():
        from src.python.core import runtime_meta
        return runtime_meta.version()

    acc = s.get("account_info") or {}
    g = s.get("guards") or {}
    real = safe(live_orders, False)
    closed = bool(s.get("market_closed"))
    connected = bool(s.get("mt5_connected"))
    return [
        ("phiên bản", (safe(version), T.C_TEXT)),
        ("môi trường", (safe(lambda: os.getenv("APP_ENV") or "DEV"), T.C_TEXT_MUT)),
        ("lệnh thật", ("BẬT — CHẠM TIỀN THẬT" if real else "TẮT (mô phỏng)",
                       T.C_RED if real else T.C_GREEN)),
        ("tài khoản", (safe(lambda: s.get("account")), T.C_TEXT)),
        ("máy chủ", (safe(lambda: acc.get("server")), T.C_TEXT_MUT)),
        ("MT5", ("ĐÃ NỐI" if connected else "CHƯA NỐI",
                 T.C_GREEN if connected else T.C_RED)),
        ("equity", (_fmt_money(s.get("equity")), T.C_TEXT)),
        ("sụt vốn ngày", (_fmt_pct(g.get("dd_pct")), T.C_TEXT)),
        ("chiến lược", (safe(n_strategies, 0), T.C_TEXT)),
        ("vị thế đang mở", (len(s.get("positions_list") or []), T.C_TEXT)),
        ("thị trường", ("ĐÓNG CỬA" if closed else "đang mở",
                        T.C_TEXT_DIM if closed else T.C_GREEN)),
        ("sổ JSONL", (str(ops_log.log_root()), T.C_TEXT_DIM)),
    ]
