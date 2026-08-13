"""Kiểm định BỘ QUY TẮC VÀO LỆNH — mọi chiến lược đăng ký PHẢI có thẻ luật đầy đủ.

VÌ SAO ĐÂY LÀ TEST CHỨ KHÔNG PHẢI QUY ƯỚC
=========================================
Khoảng trống này đã tồn tại thật: `m30/news_overreaction.py` nằm trong thư mục chiến
lược nhưng không có bộ quy tắc nào, vì nó đã BỊ BÁC BỎ và bị bỏ quên tại chỗ. Nhìn từ
ngoài, thư mục nói "có một chiến lược M30" trong khi registry nói không.

Quy ước không chặn được việc đó tái diễn — chỉ test chặn được. Ba bất biến ở đây:

    1. mọi chiến lược trong registry đều có `RULEBOOK` ĐẦY ĐỦ
    2. mọi module trong `strategies/<tf>/` đều nằm trong registry (không có kẻ lạc)
    3. thẻ luật KHỚP với code: khung thời gian, giờ cấm, tên tín hiệu, cỡ rổ

Bất biến 3 quan trọng nhất: một thẻ luật ĐÚNG ĐỊNH DẠNG nhưng SAI NỘI DUNG còn tệ hơn
không có thẻ, vì nó tạo cảm giác đã kiểm soát được luật.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.python.strategies import registry as REG
from src.python.strategies import rulebook as RB

ROOT = Path(__file__).resolve().parents[1]
STRAT_DIR = ROOT / "src" / "python" / "strategies"


@pytest.fixture(scope="module")
def books():
    return RB.collect()


def test_every_registered_strategy_has_a_rulebook(books):
    names = {s.name for s in REG.STRATEGIES}
    missing = names - set(books)
    assert not missing, f"chiến lược thiếu RULEBOOK: {sorted(missing)}"


def test_no_orphan_strategy_module():
    """Mọi file trong `strategies/<tf>/` phải nằm trong registry.

    Một chiến lược đã bị bác bỏ mà vẫn nằm trong thư mục chiến lược làm người đọc
    tưởng nó đang chạy. Chỗ của nó là `REJECTED_DIRECTIONS` + `research/fx/rejected/`.
    """
    registered = {s.module for s in REG.STRATEGIES}
    for tf in ("m30", "h1", "h4", "d1"):
        d = STRAT_DIR / tf
        if not d.is_dir():
            continue
        for f in d.glob("*.py"):
            if f.stem == "__init__":
                continue
            assert f.stem in registered, (
                f"{tf}/{f.name} nằm trong thư mục chiến lược nhưng KHÔNG có trong "
                f"registry — hoặc đăng ký nó, hoặc chuyển sang research/fx/rejected/")


def test_rulebook_has_all_required_fields(books):
    for name, rb in books.items():
        missing = RB.missing_fields(rb)
        assert not missing, f"{name}: thẻ luật thiếu {missing}"


def test_every_entry_rule_has_a_numeric_threshold(books):
    """"Đà đủ mạnh" là vô dụng khi truy vết; "ret/ATR >= 2,0" thì không."""
    for name, rb in books.items():
        without_numbers = RB.rules_have_thresholds(rb)
        assert not without_numbers, \
            f"{name}: điều kiện {without_numbers} không có ngưỡng số kiểm chứng được"


def test_rulebook_matches_registry(books):
    specs = {s.name: s for s in REG.STRATEGIES}
    for name, rb in books.items():
        s = specs[name]
        assert rb.signal_tf == s.signal_tf, \
            f"{name}: thẻ luật nói {rb.signal_tf}, registry nói {s.signal_tf}"
        assert rb.execution_tf == s.execution_tf
        # so rổ GIAO DỊCH, không phải rổ xếp hạng — registry khai công cụ ĐẶT LỆNH.
        # Chân currency xếp hạng 8 ĐỒNG nhưng khớp trên 7 CẶP; gộp hai rổ làm một là
        # cách để một hôm nào đó có người cố đặt lệnh lên "EUR".
        tr = RB.traded_universe(rb)
        assert set(tr) == set(s.symbols), (
            f"{name}: rổ giao dịch thẻ luật ({len(tr)}) khác registry "
            f"({len(s.symbols)}) — lệch: {sorted(set(tr) ^ set(s.symbols))}")


def test_rulebook_matches_code_constants(books):
    """Giờ cấm trong thẻ luật phải bằng đúng hằng số module đang dùng."""
    specs = {s.name: s for s in REG.STRATEGIES}
    for name, rb in books.items():
        mod = specs[name].load()
        actual = getattr(mod, "FORBIDDEN_HOURS_UTC", None)
        if actual is not None:
            assert tuple(rb.forbidden_hours_utc) == tuple(actual), (
                f"{name}: thẻ luật ghi giờ cấm {rb.forbidden_hours_utc}, "
                f"code dùng {actual}")


def test_signal_name_matches_runtime_trace(books):
    """`trace_signal_name` PHẢI bằng `signal_name` mà `explain_decisions` phát ra.

    Đây là mối nối giữa thẻ luật KHAI BÁO và bản ghi RUNTIME. Lệch nhau thì không
    đối chiếu được hai bên, và toàn bộ lý do có cả hai sụp.
    """
    specs = {s.name: s for s in REG.STRATEGIES}
    for name, rb in books.items():
        mod = specs[name].load()
        fn = getattr(mod, "explain_decisions", None)
        if fn is None:
            continue                      # chân H1 dùng EntryDecision riêng
        tr = fn()
        assert tr, f"{name}: explain_decisions không phát bản ghi nào"
        rec = tr[0]
        # Hai dạng bản ghi cùng tồn tại và đều hợp lệ:
        #   RuleTrace     (chiến lược XẾP HẠNG) mang `signal_name` là TÊN đại lượng
        #   EntryDecision (chiến lược MỘT công cụ) mang thẳng TRƯỜNG, vd `z_score`
        # Thẻ luật phải trỏ đúng vào cái mà runtime thật sự phát ra — đây chính là
        # mối nối giữa thẻ luật khai báo và bản ghi runtime; lệch thì không đối chiếu
        # được hai bên khi truy vết một lệnh thua.
        actual = getattr(rec, "signal_name", None)
        if actual is None:
            assert hasattr(rec, rb.trace_signal_name), (
                f"{name}: thẻ luật ghi '{rb.trace_signal_name}' nhưng bản ghi runtime "
                f"({type(rec).__name__}) không có trường đó")
        else:
            assert actual == rb.trace_signal_name, (
                f"{name}: thẻ luật ghi '{rb.trace_signal_name}', runtime phát '{actual}'")


def test_every_rulebook_renders(books):
    for name, rb in books.items():
        s = rb.render()
        for level in ("1. ĐỊNH DANH", "2. KHUNG GIỜ", "3. CHỈ BÁO", "4. VÀO LỆNH",
                    "5. THOÁT LỆNH", "6. CHẶN RIÊNG", "7. TẦN SUẤT"):
            assert level in s, f"{name}: bản in thiếu mục {level}"
        assert name in s


def test_rulebook_serialises(books):
    import json
    for name, rb in books.items():
        json.dumps(rb.to_dict())


def test_rulebook_records_expectancy_for_live_comparison(books):
    """Thiếu kỳ vọng thì không phát hiện được live đang lệch khỏi backtest."""
    for name, rb in books.items():
        assert rb.expectancy, f"{name}: thẻ luật không ghi kỳ vọng"
        assert any(ch.isdigit() for ch in rb.expectancy)
        assert rb.frequency, f"{name}: thẻ luật không ghi tần suất"
