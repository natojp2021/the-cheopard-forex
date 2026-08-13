"""Kiểm định BẢN GHI QUY TẮC VÀO LỆNH — yêu cầu vận hành, không phải tiện ích.

VÌ SAO ĐÂY LÀ TEST, KHÔNG PHẢI GHI CHÚ
======================================
Yêu cầu: "khi một chiến lược vượt qua tất cả rào cản → apply vào live, ngoài log
research, cần LOG QUY TẮC VÀO LỆNH". Một bản ghi hợp lệ phải cho phép người đọc,
chỉ với bản ghi đó, TÁI LẬP quyết định:

    giá trị tín hiệu · thứ hạng · ngưỡng cắt · tỷ trọng suy ra

Thiếu một phần là không tái lập được. Biết tỷ trọng mà không biết thứ hạng thì không
phân biệt được "AUD thật sự mạnh nhất" với "AUD được chọn vì USDJPY thiếu dữ liệu".

MỘT LỖI THẬT MÀ TEST NÀY BẮT
============================
Bản đầu của `explain_decisions` ghép tỷ trọng HÔM NAY với tín hiệu HÔM NAY, trong khi
vị thế được GIỮ giữa hai lần tái cân bằng. Kết quả là bản ghi TỰ MÂU THUẪN:

    "EURGBP BUY w=+0.1429 · neg_zscore=+0.1893 hạng 12/20 — thuộc top 7"

Hạng 12 không thể thuộc top 7. Bản ghi tự mâu thuẫn thì vô dụng đúng lúc cần nó nhất
— lúc truy vết một lệnh thua bất thường. `test_no_self_contradicting_trace` chốt
lại điều đó cho CẢ BỐN chân xếp hạng.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.python.execution import rule_trace as RT

RANKING_LEGS = [
    ("CurrencyReversal", "src.python.strategies.d1.currency_reversal"),
    ("CurrencyCarry", "src.python.strategies.d1.currency_carry"),
    ("CrossMomentum", "src.python.strategies.d1.cross_momentum"),
    ("CrossXsReversion", "src.python.strategies.h4.cross_xs_reversion"),
]


@pytest.fixture(scope="module")
def traces():
    from importlib import import_module
    out = {}
    for name, path in RANKING_LEGS:
        out[name] = import_module(path).explain_decisions()
    return out


def test_every_ranking_leg_emits_a_trace(traces):
    for name, tr in traces.items():
        assert tr, f"{name} không phát bản ghi nào"
        assert all(isinstance(x, RT.RuleTrace) for x in tr)


def test_records_instruments_that_were_not_picked(traces):
    """Phải có dòng cho MỌI công cụ trong rổ, kể cả công cụ FLAT.

    Câu hỏi "vì sao EURUSD hôm nay không có vị thế" chỉ trả lời được nếu có dòng của
    EURUSD kèm thứ hạng. Chỉ ghi công cụ được chọn là ghi một nửa.
    """
    for name, tr in traces.items():
        n_flat = sum(1 for x in tr if x.action in ("FLAT", "SKIP"))
        assert n_flat > 0, f"{name} chỉ ghi công cụ có vị thế — thiếu phần FLAT"


def test_trace_carries_all_four_components(traces):
    """Mỗi bản ghi phải có: tín hiệu · thứ hạng · cỡ rổ · ngưỡng cắt."""
    for name, tr in traces.items():
        for x in tr:
            assert x.signal_name, f"{name}/{x.instrument}: thiếu tên tín hiệu"
            assert x.signal_universe_size and x.signal_universe_size > 1
            assert x.threshold_desc, f"{name}/{x.instrument}: thiếu ngưỡng cắt"
            if x.gate_data_ok:
                assert x.signal_value is not None
                assert x.signal_rank is not None
            assert x.reason, f"{name}/{x.instrument}: thiếu lý do"


def test_no_self_contradicting_trace(traces):
    """Công cụ có vị thế MUA phải nằm trong top N theo đúng thứ hạng đã ghi.

    Đây là test bắt lỗi "ghép tỷ trọng hôm nay với tín hiệu hôm nay" khi vị thế được
    giữ qua nhiều nến — lỗi làm bản ghi nói 'hạng 12/20 thuộc top 7'.
    """
    for name, tr in traces.items():
        n = tr[0].signal_universe_size
        n_leg = max(sum(1 for x in tr if x.target_weight > 1e-9), 1)
        for x in tr:
            if x.gate_regime_blocking or not x.gate_data_ok:
                continue
            if x.target_weight > 1e-9:
                assert x.signal_rank <= n_leg, (
                    f"{name}/{x.instrument}: MUA nhưng hạng {x.signal_rank}/{n} "
                    f"trong khi chỉ {n_leg} công cụ được mua — bản ghi tự mâu thuẫn")
            elif x.target_weight < -1e-9:
                assert x.signal_rank > n - n_leg - 1, (
                    f"{name}/{x.instrument}: BÁN nhưng hạng {x.signal_rank}/{n} "
                    f"— bản ghi tự mâu thuẫn")


def test_the_two_legs_weights_cancel_out(traces):
    """Chiến lược xếp hạng phải trung hoà: tổng tỷ trọng ≈ 0.

    Không trung hoà thì nó đang cược HƯỚNG (vd USD yếu), không cược TƯƠNG ĐỐI — và
    toàn bộ lý lẽ 'phơi nhiễm USD ròng ≈ 0 theo xây dựng' sụp.
    """
    for name, tr in traces.items():
        total_w = sum(x.target_weight for x in tr)
        gross = sum(abs(x.target_weight) for x in tr)
        if gross < 1e-9:
            continue                       # cổng chế độ đang chặn — hợp lệ
        assert abs(total_w) < 0.02 * gross, \
            f"{name}: tổng tỷ trọng {total_w:+.4f} trên gross {gross:.4f} — không trung hoà"


def test_explain_returns_one_readable_line(traces):
    for name, tr in traces.items():
        for x in tr[:3]:
            s = x.explain()
            assert x.instrument in s and x.action in s
            assert len(s) > 40


def test_to_row_serialises_to_json(traces):
    import json
    for name, tr in traces.items():
        for x in tr[:3]:
            json.dumps(x.to_row())          # phải không raise


def test_summarise_returns_correctly_sorted_table(traces):
    for name, tr in traces.items():
        df = RT.summarise(tr)
        assert len(df) == len(tr)
        for c in ("instrument", "action", "weight", "rank", "reason"):
            assert c in df.columns
        # BUY phải xếp trước FLAT
        acts = list(df["action"])
        if "BUY" in acts and "FLAT" in acts:
            assert acts.index("BUY") < acts.index("FLAT")


def test_rank_of_is_correct():
    s = pd.Series({"A": 3.0, "B": 1.0, "C": 2.0})
    assert RT.rank_of(s, "A") == 1
    assert RT.rank_of(s, "C") == 2
    assert RT.rank_of(s, "B") == 3
    assert RT.rank_of(s, "Z") is None


def test_decision_log_round_trips(tmp_path, monkeypatch, traces):
    """Ghi ra JSONL rồi đọc lại phải ra đúng số bản ghi — không mất, không nhân đôi."""
    from src.python.execution import decision_log as DLOG

    monkeypatch.setattr(DLOG, "LOG_DIR", tmp_path, raising=False)
    tr = traces["CrossXsReversion"]
    DLOG.record_many([x.to_row() for x in tr], strategy="TestLeg",
                     extra={"portfolio": "TEST"})
    files = list(tmp_path.rglob("*.jsonl"))
    assert files, "không có tệp log nào được tạo"
    total = sum(sum(1 for _ in f.open(encoding="utf-8")) for f in files)
    assert total == len(tr), f"ghi {len(tr)} bản ghi nhưng đọc lại {total}"
