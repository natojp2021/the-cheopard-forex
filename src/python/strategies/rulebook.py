"""rulebook.py — BỘ QUY TẮC VÀO LỆNH, dạng KHAI BÁO và KIỂM ĐỊNH ĐƯỢC.

VÌ SAO MODULE NÀY PHẢI TỒN TẠI, BÊN CẠNH `rule_trace.py`
========================================================
Hai thứ khác nhau, và thiếu một trong hai là thiếu thật:

    `rule_trace.py`   bản ghi RUNTIME — "hôm nay EURGBP được mua vì hạng 3/20"
    `rulebook.py`     thẻ luật KHAI BÁO — "luật của chiến lược này là gì"

Bản ghi runtime trả lời "hôm nay xảy ra chuyện gì". Thẻ luật trả lời "hệ thống được
PHÉP làm gì". Khi một lệnh thua bất thường, phải đối chiếu HAI cái với nhau: nếu bản
ghi khớp thẻ luật thì luật chạy đúng và thị trường đi ngược; nếu lệch thì code đã trôi
khỏi luật. Chỉ có một trong hai thì không phân biệt được hai tình huống đó.

CHUẨN LẤY TỪ `quant-xau/src/python/live_strategies/h1/xau_r_h1.py`
==================================================================
Hệ XAUUSD ghi thẻ luật trong docstring, bảy mục đánh số: định danh · khung giờ · chỉ
báo · vào lệnh · thoát lệnh · chặn riêng · tần suất. Cấu trúc đó đúng và được giữ
nguyên ở đây. Điều được ĐỔI: docstring là văn bản tự do, không ai kiểm được nó có đủ
bảy mục không, và nó trôi khỏi code mà không ai biết. Bản này là dữ liệu — nên
`tests/test_rulebook.py` kiểm được tính đầy đủ, và GUI render được thẳng.

MỘT THẺ LUẬT HỢP LỆ PHẢI TRẢ LỜI ĐƯỢC BẢY CÂU
==============================================
    1. cái gì được giao dịch, ở khung nào, tối đa bao nhiêu vị thế
    2. khớp lệnh trong giờ nào, giờ nào cấm
    3. dùng đúng những đại lượng nào (không có đại lượng ẩn)
    4. điều kiện vào lệnh — ĐỦ ngưỡng số, không phải mô tả định tính
    5. ra lệnh bằng đường nào, và cắt lỗ ở đâu
    6. chặn riêng gì (spread cap, chế độ thị trường, sự kiện)
    7. tần suất kỳ vọng — để phát hiện ngay khi live lệch khỏi backtest
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Rule:
    """Một điều kiện đơn, có ngưỡng số kiểm chứng được.

    `expr` phải là biểu thức đọc được kèm SỐ, không phải mô tả định tính. "đà đủ
    mạnh" là vô dụng khi truy vết; "ret_h1_12 / ATR >= 2,0" thì không.
    """
    code: str                  # a, b, c... — để bản ghi runtime trỏ ngược về đây
    expr: str                  # "z_score <= −2,0"
    why: str = ""              # vì sao có điều kiện này


@dataclass(frozen=True)
class RuleBook:
    """Bộ quy tắc vào lệnh đầy đủ của MỘT chiến lược."""

    # ── 1. ĐỊNH DANH
    name: str
    signal_tf: str
    execution_tf: str
    direction: str                        # LONG_ONLY | SHORT_ONLY | BOTH
    universe: Tuple[str, ...]             # rổ XẾP HẠNG / sinh tín hiệu
    # Rổ GIAO DỊCH — thường TRÙNG `universe`, nhưng không phải luôn. Chân currency
    # xếp hạng 8 ĐỒNG TIỀN rồi quy sang 7 CẶP để khớp: hai rổ khác nhau về bản chất,
    # và gộp chúng làm một là cách để một hôm nào đó có người đặt lệnh lên "EUR".
    traded: Tuple[str, ...] = ()
    max_positions: Optional[int] = None   # None = không giới hạn cứng
    family: str = ""                      # họ chiến lược
    source: str = ""                      # nguồn học thuật

    # ── 2. KHUNG GIỜ
    hours_utc: str = ""                   # mô tả khung giờ khớp lệnh
    forbidden_hours_utc: Tuple[int, ...] = ()

    # ── 3. CHỈ BÁO
    indicators: Tuple[str, ...] = ()

    # ── 4. VÀO LỆNH
    entry_logic: str = "ALL"              # ALL = đủ mọi điều kiện | RANK = xếp hạng
    entry_rules: Tuple[Rule, ...] = ()
    entry_price: str = ""                 # khớp ở đâu

    # ── 5. THOÁT LỆNH
    exit_rules: Tuple[Rule, ...] = ()
    stop_loss: str = ""
    take_profit: str = ""

    # ── 6. CHẶN RIÊNG
    blocks: Tuple[str, ...] = ()

    # ── 7. TẦN SUẤT
    frequency: str = ""
    avg_holding: str = ""

    # ── bằng chứng, để đối chiếu khi live lệch
    expectancy: str = ""

    # ── liên kết sang bản ghi runtime
    trace_signal_name: str = ""           # PHẢI khớp `RuleTrace.signal_name`

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def render(self) -> str:
        """Bản in bảy mục — cùng bố cục thẻ luật của hệ XAUUSD."""
        L: List[str] = []
        bar = "=" * 79
        L.append(bar)
        L.append(f"BỘ QUY TẮC VÀO LỆNH — {self.name}")
        L.append(bar)

        L.append("")
        L.append(f"1. ĐỊNH DANH:  {self.name} · tín hiệu {self.signal_tf} → "
                 f"khớp {self.execution_tf} · {self.direction}")
        if self.family:
            L.append(f"               họ: {self.family}")
        L.append(f"               rổ XẾP HẠNG ({len(self.universe)}): "
                 f"{', '.join(self.universe[:6])}"
                 + (f" … (+{len(self.universe) - 6})" if len(self.universe) > 6 else ""))
        tr = self.traded or self.universe
        if tuple(tr) != tuple(self.universe):
            L.append(f"               rổ GIAO DỊCH ({len(tr)}): {', '.join(tr[:6])}"
                     + (f" … (+{len(tr) - 6})" if len(tr) > 6 else ""))
        if self.max_positions is not None:
            L.append(f"               tối đa {self.max_positions} vị thế")
        if self.source:
            L.append(f"               nguồn: {self.source}")

        L.append("")
        L.append(f"2. KHUNG GIỜ:  {self.hours_utc or '— không ràng buộc'}")
        if self.forbidden_hours_utc:
            L.append("               giờ CẤM (UTC): "
                     + ", ".join(f"{h:02d}" for h in self.forbidden_hours_utc))

        L.append("")
        L.append("3. CHỈ BÁO:    " + ("\n               ".join(self.indicators)
                                      if self.indicators else "—"))

        L.append("")
        mode = ("đủ CẢ" if self.entry_logic == "ALL" else "xếp hạng cắt ngang")
        L.append(f"4. VÀO LỆNH ({mode}, {len(self.entry_rules)} điều kiện):")
        for r in self.entry_rules:
            L.append(f"     {r.code}. {r.expr}")
            if r.why:
                L.append(f"        ({r.why})")
        if self.entry_price:
            L.append(f"   -> {self.entry_price}")

        L.append("")
        L.append("5. THOÁT LỆNH:")
        for r in self.exit_rules:
            L.append(f"     · {r.expr}" + (f"  ({r.why})" if r.why else ""))
        if self.stop_loss:
            L.append(f"     · CẮT LỖ: {self.stop_loss}")
        if self.take_profit:
            L.append(f"     · CHỐT LỜI: {self.take_profit}")

        L.append("")
        L.append("6. CHẶN RIÊNG: " + ("\n               ".join(self.blocks)
                                      if self.blocks else "—"))

        L.append("")
        L.append(f"7. TẦN SUẤT:   {self.frequency or '—'}")
        if self.avg_holding:
            L.append(f"               giữ lệnh trung bình: {self.avg_holding}")
        if self.expectancy:
            L.append(f"               kỳ vọng: {self.expectancy}")
        L.append("")
        return "\n".join(L)


# ═══════════════════════════════════════════════════════ kiểm tra tính đầy đủ
REQUIRED = ("name", "signal_tf", "execution_tf", "direction", "universe",
            "indicators", "entry_rules", "exit_rules", "frequency",
            "trace_signal_name")


def traded_universe(rb: RuleBook) -> Tuple[str, ...]:
    """Rổ thực sự đặt lệnh. Mặc định trùng rổ xếp hạng."""
    return tuple(rb.traded) if rb.traded else tuple(rb.universe)


def missing_fields(rb: RuleBook) -> List[str]:
    """Trường bắt buộc còn trống. Rỗng = thẻ luật đầy đủ."""
    out = []
    for f in REQUIRED:
        v = getattr(rb, f, None)
        if v is None or (hasattr(v, "__len__") and len(v) == 0):
            out.append(f)
    return out


def rules_have_thresholds(rb: RuleBook) -> List[str]:
    """Điều kiện vào lệnh KHÔNG có số là điều kiện không kiểm chứng được.

    Trả về mã của các điều kiện thiếu ngưỡng số. Đây là thứ phân biệt một thẻ luật
    dùng được với một đoạn mô tả nghe hợp lý.
    """
    bad = []
    for r in rb.entry_rules:
        if not any(ch.isdigit() for ch in r.expr):
            bad.append(r.code)
    return bad


def collect() -> Dict[str, RuleBook]:
    """Thu thập thẻ luật của MỌI chiến lược đã đăng ký. Dùng cho GUI và test."""
    from src.python.strategies import registry as REG

    out: Dict[str, RuleBook] = {}
    for spec in REG.STRATEGIES:
        mod = spec.load()
        rb = getattr(mod, "RULEBOOK", None)
        if rb is not None:
            out[spec.name] = rb
    return out


def render_all() -> str:
    books = collect()
    return "\n\n".join(rb.render() for rb in books.values())


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(render_all())
