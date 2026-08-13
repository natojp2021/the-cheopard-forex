"""strategy_registry.py — CẦU NỐI cho GUI kế thừa. Không phải nguồn sự thật.

VÌ SAO CÓ TỆP NÀY
=================
`gui_command_center.py` được KẾ THỪA nguyên vẹn từ hệ XAUUSD — 1.875 dòng dựng giao
diện đã chạy ổn định. Nó đọc chiến lược qua ba thứ:

    _strategy_registry.live()   danh sách chiến lược đang chạy
    spec.gui_tag                nhãn ngắn hiện trên thẻ
    spec.gui_desc               "Hạng mục · Khung · Mô tả"

Nguồn sự thật của hệ Forex là `src/python/strategies/registry.py`, và nó có cấu trúc
khác (không có `gui_tag`, không có `magic`). Hai lựa chọn:

    sửa GUI đọc registry mới   → phải đụng vào 1.875 dòng đã chạy ổn định
    viết CẦU NỐI ở đây         → GUI không sửa một chữ, registry cũng không phải
                                  gánh thêm trường chỉ dùng cho giao diện

Chọn cách thứ hai. Tệp này KHÔNG khai báo chiến lược nào — nó ĐỌC registry thật rồi
dịch sang hình dạng mà GUI mong đợi. Thêm chiến lược vào `strategies/registry.py` là
nó tự hiện trên GUI, không phải sửa hai chỗ.

MAGIC NUMBER SINH TỪ TÊN, KHÔNG KHAI TAY
=========================================
Hệ XAU gán magic tay cho từng chiến lược (260717, 260801…). Với 14 chiến lược Forex
và còn tăng, gán tay là một danh sách nữa để trôi khỏi registry. Ở đây magic sinh
tất định từ tên bằng băm — cùng tên luôn cho cùng số, tên khác gần như chắc chắn cho
số khác (không gian 100.000 giá trị, 14 tên thì xác suất đụng < 0,1%).

`test_gui_adapter.py` chốt lại tính tất định và tính duy nhất đó.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from src.python.strategies import registry as _REG

# Dải magic dành cho hệ Forex. Cố ý KHÔNG trùng dải của hệ XAUUSD (2607xx) để nếu
# hai hệ vô tình cùng chạy trên một tài khoản thì lệnh của chúng vẫn phân biệt được.
MAGIC_BASE = 5100000


def _magic_of(name: str) -> int:
    """Magic tất định từ tên chiến lược. Cùng tên → cùng số, mọi lúc, mọi máy."""
    h = hashlib.sha1(name.encode("utf-8")).hexdigest()
    return MAGIC_BASE + int(h[:8], 16) % 100_000


# Tiền tố ngắn cho từng HỌ tín hiệu. Nhãn dựng theo mẫu `<HỌ>-<CẶP>-<KHUNG>`.
_FAMILY_PREFIX = (
    ("ZBand", "ZB"),
    ("VolRegime", "VOLR"),
    ("RsiDiv", "RSID"),
    ("Streak", "STRK"),
    ("Accel", "ACC"),
)
_TIMEFRAMES = ("M30", "H1", "H4", "D1")


def _tag_of(name: str) -> str:
    """Nhãn ngắn hiện trên thẻ GUI. Ưu tiên đọc được hơn là ngắn tuyệt đối.

    ⚠️ NHÃN PHẢI DUY NHẤT — xem `_assert_tags_unique`.

    Bản trước cắt cụt `name[:12].upper()` cho mọi họ trừ ZBand. Hai cặp ĐÂM NHAU:
    `RsiDivNZDCADH1` và `RsiDivNZDCADM30` cùng ra `RSIDIVNZDCAD`, `VolRegimeGBPAUDH1`
    và `VolRegimeGBPCHFM30` cùng ra `VOLREGIMEGBP` — đúng chỗ khung thời gian và ký
    tự phân biệt cặp tiền bị cắt mất. Giao diện dùng nhãn làm KHOÁ của
    `matrix_rows`, nên hai chiến lược dựng hai hàng nhưng chỉ một khoá: hàng thứ
    hai không bao giờ được cập nhật và đứng nguyên "—" giữa bảng, kể cả lúc thị
    trường đóng khi mọi hàng khác hiện STAND BY.

    Nay mọi họ đều tách `<HỌ>-<CẶP>-<KHUNG>` như ZBand vẫn làm — vừa duy nhất, vừa
    đọc được cặp và khung mà không phải tra tên đầy đủ.
    """
    special = {
        "CurrencyReversal": "CCY-REV", "CurrencyCarry": "CCY-CARRY",
        "CrossMeanReversion": "X-MR-H1", "CrossMomentum": "X-MOM-D1",
        "CrossXsReversion": "X-XS-H4",
    }
    if name in special:
        return special[name]
    for family, prefix in _FAMILY_PREFIX:
        if not name.startswith(family):
            continue
        rest = name[len(family):]
        for tf in _TIMEFRAMES:
            if rest.endswith(tf):
                return f"{prefix}-{rest[:-len(tf)]}-{tf}"
    return name[:12].upper()


_CATEGORY = {"M30": "Intraday", "H1": "Day", "H4": "Swing", "D1": "Position"}


@dataclass(frozen=True)
class GuiSpec:
    """Hình dạng mà GUI mong đợi. Mọi trường suy ra từ registry thật."""
    name: str
    gui_tag: str
    gui_desc: str            # "Hạng mục · Khung · Mô tả"
    magic: int
    symbol: str
    symbols: Tuple[str, ...]
    stage: str
    signal_tf: str
    execution_tf: str
    sharpe_all: Optional[float]
    sharpe_oos: Optional[float]
    max_dd_pct: Optional[float]
    hypothesis: str
    # Hệ XAU có `confirm_symbols` (bạc xác nhận cho vàng). Hệ Forex không có chiến
    # lược nào dùng công cụ xác nhận, nhưng GUI có thể hỏi nên khai rỗng cho an toàn.
    confirm_symbols: Tuple[str, ...] = ()
    regimes_allowed = None


def _to_gui(spec) -> GuiSpec:
    fam = spec.hypothesis.split(".")[0].strip()
    if len(fam) > 62:
        fam = fam[:59] + "…"
    return GuiSpec(
        name=spec.name,
        gui_tag=_tag_of(spec.name),
        gui_desc=f"{_CATEGORY.get(spec.signal_tf, 'Day')} · {spec.signal_tf} · {fam}",
        magic=_magic_of(spec.name),
        symbol=spec.symbols[0] if spec.symbols else "",
        symbols=tuple(spec.symbols),
        stage=spec.stage,
        signal_tf=spec.signal_tf,
        execution_tf=spec.execution_tf,
        sharpe_all=spec.sharpe_all,
        sharpe_oos=spec.sharpe_oos,
        max_dd_pct=spec.max_dd_pct,
        hypothesis=spec.hypothesis)


def all_specs() -> List[GuiSpec]:
    specs = [_to_gui(s) for s in _REG.STRATEGIES]
    _assert_tags_unique(specs)
    return specs


def _assert_tags_unique(specs: List[GuiSpec]) -> None:
    """NỔ nếu hai chiến lược dùng chung một `gui_tag`.

    Giao diện lấy nhãn làm KHOÁ (`matrix_rows[tag]`), nên nhãn trùng không gây lỗi
    — nó lặng lẽ nuốt một chiến lược: hàng vẫn được vẽ nhưng không bao giờ được
    cập nhật, và đứng nguyên "—" giữa bảng. Người vận hành nhìn 27 hàng và tưởng
    đang theo dõi 27 chân, trong khi hai chân không hề được báo cáo trạng thái.
    Đã xảy ra 15/08/2026 với `RSIDIVNZDCAD` và `VOLREGIMEGBP`.

    Fail-closed ngay ở nguồn: nhãn là dữ liệu SINH RA, nên chỗ duy nhất bắt được
    là chỗ sinh.
    """
    seen: dict = {}
    for g in specs:
        if g.gui_tag in seen:
            raise ValueError(
                f"gui_tag trùng: {seen[g.gui_tag]!r} và {g.name!r} cùng ra "
                f"{g.gui_tag!r}. Sửa `_tag_of` — nhãn là KHOÁ của bảng giao diện.")
        seen[g.gui_tag] = g.name


def live() -> List[GuiSpec]:
    """Chiến lược GUI phải hiện.

    Hệ Forex hiện chưa có chiến lược nào ở giai đoạn LIVE — cả 14 đang FORWARD_TEST.
    Trả cả FORWARD_TEST là có chủ ý: nếu chỉ trả LIVE thì bảng vận hành rỗng trơn và
    người dùng không thấy gì, đúng cái bẫy mà GUI XAU từng mắc theo chiều ngược lại
    (chiến lược đang tiêu tiền thật biến mất khỏi bảng mà không cảnh báo).
    """
    keep = (_REG.LIVE, _REG.FORWARD_TEST)
    return [g for g in all_specs() if g.stage in keep]


def by_tag(tag: str) -> Optional[GuiSpec]:
    for g in all_specs():
        if g.gui_tag == tag:
            return g
    return None


def by_magic(magic: int) -> Optional[GuiSpec]:
    for g in all_specs():
        if g.magic == magic:
            return g
    return None


def display_order() -> List[str]:
    """Thứ tự hiện trên GUI — nhóm theo KHUNG (M30 → H1 → H4 → D1).

    Cùng nguyên tắc nhóm-theo-khung mà GUI XAU dùng, nhưng SINH RA từ registry chứ
    không viết tay. Danh sách viết tay chính là chỗ mà GUI XAU từng để sót 5 chiến
    lược LIVE — chúng biến mất khỏi bảng mà không có cảnh báo nào.
    """
    order = {"M30": 0, "H1": 1, "H4": 2, "D1": 3}
    gs = sorted(live(), key=lambda g: (order.get(g.signal_tf, 9),
                                       -(g.sharpe_all or 0.0)))
    return [g.gui_tag for g in gs]
