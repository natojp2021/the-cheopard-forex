"""Kiểm định CỔNG TIN VĨ MÔ — một tầng, fail-soft, chỉ chặn mở lệnh mới.

VÌ SAO TEST NÀY QUAN TRỌNG HƠN VẺ NGOÀI CỦA NÓ
===============================================
Một cổng chặn có hai cách hỏng, và cách thứ hai nguy hiểm hơn nhiều:

    hỏng kiểu MỞ    cổng không chặn khi cần → ăn trọn một cú nhảy tin
    hỏng kiểu ĐÓNG  cổng chặn khi không cần → hệ ngừng giao dịch mà KHÔNG BÁO LỖI

Hỏng kiểu đóng không sinh exception, không sinh log lỗi, chỉ sinh ra một tài khoản
đứng yên. Nó có thể chạy nhiều tuần trước khi ai đó hỏi "sao lâu rồi không có lệnh".
Vì vậy `test_fail_soft_*` là nhóm test quan trọng nhất ở đây: mọi lỗi của tầng LLM
và mọi thiếu hụt dữ liệu đều phải dẫn tới KHÔNG CHẶN.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.python.ai import news_guard as NG


@pytest.fixture
def calendar_file(tmp_path) -> Path:
    """Lịch kinh tế giả: NFP ngày 10, ECB_RATE ngày 12 lúc 12:00."""
    df = pd.DataFrame({
        "time": pd.to_datetime(["2026-08-10 12:30", "2026-08-12 12:00"], utc=True),
        "event": ["NFP", "ECB_RATE"],
        "currency": ["USD", "EUR"],
    })
    p = tmp_path / "cal.parquet"
    df.to_parquet(p)
    NG._cache["df"], NG._cache["mtime"] = None, None
    return p


# ═══════════════════════════════════════════════════════ tầng 0 — lịch
def test_high_impact_event_blocks_whole_day(calendar_file):
    """NFP chặn CẢ NGÀY, không chỉ ±60 phút — thanh khoản mỏng từ nhiều giờ trước."""
    for hour in ("00:30", "08:00", "12:30", "20:00"):
        d = NG.decide(pd.Timestamp(f"2026-08-10 {hour}", tz="UTC"), calendar_path=calendar_file, force=True)
        assert d.blocked, f"{hour} không bị chặn dù hôm nay có NFP"
        assert d.severity == "HIGH"
        assert "NFP" in d.events


def test_normal_event_blocks_narrow_window_only(calendar_file):
    """ECB_RATE chỉ chặn ±60 phút — chặn cả ngày cho mọi tin là mất quá nhiều edge."""
    in_window = NG.decide(pd.Timestamp("2026-08-12 11:30", tz="UTC"), calendar_path=calendar_file, force=True)
    assert in_window.blocked and in_window.severity == "MEDIUM"

    out_of_window = NG.decide(pd.Timestamp("2026-08-12 08:00", tz="UTC"), calendar_path=calendar_file, force=True)
    assert not out_of_window.blocked, "8h sáng cách ECB 4 tiếng mà vẫn chặn — quá rộng"


def test_day_without_events_is_clear(calendar_file):
    d = NG.decide(pd.Timestamp("2026-08-11 12:00", tz="UTC"), calendar_path=calendar_file, force=True)
    assert not d.blocked
    assert d.source == "CALENDAR"


def test_blocks_only_instruments_of_the_currency(calendar_file):
    """NFP là tin USD — không có lý do gì chặn AUDNZD."""
    d = NG.decide(pd.Timestamp("2026-08-10 12:00", tz="UTC"), calendar_path=calendar_file, force=True)
    assert d.blocks_instrument("EURUSD")
    assert d.blocks_instrument("USDCAD")
    assert not d.blocks_instrument("AUDNZD"), "AUDNZD không chứa USD mà vẫn bị chặn"
    assert not d.blocks_instrument("GBPAUD")


def test_empty_currencies_blocks_everything():
    d = NG.GuardDecision(timestamp=pd.Timestamp("2026-08-10"), blocked=True,
                         source="LLM", currencies=())
    for s in ("AUDCAD", "EURUSD", "GBPNZD"):
        assert d.blocks_instrument(s)


# ═══════════════════════════════════════════════════════ fail-soft
def test_fail_soft_when_calendar_missing(tmp_path):
    """Thiếu tệp lịch → THÔNG, không chặn. Cổng hỏng mà chặn hết = hệ ngừng chạy."""
    NG._cache["df"], NG._cache["mtime"] = None, None
    d = NG.decide(pd.Timestamp("2026-08-10 12:00", tz="UTC"),
                  calendar_path=tmp_path / "khong_ton_tai.parquet", force=True)
    assert not d.blocked
    assert d.source == "NONE"


def test_fail_soft_when_llm_raises(calendar_file):
    """LLM lỗi → giữ nguyên kết quả tầng lịch, ghi lỗi, KHÔNG chặn thêm."""
    def broken_llm(_prompt):
        raise RuntimeError("hết hạn mức API")

    d = NG.decide(pd.Timestamp("2026-08-11 12:00", tz="UTC"),
                  headlines=["ECB giữ nguyên lãi suất"], call_llm=broken_llm,
                  calendar_path=calendar_file, force=True)
    assert not d.blocked
    assert not d.llm_used
    assert "hết hạn mức" in d.llm_error


def test_fail_soft_when_llm_returns_garbage(calendar_file):
    def garbage_llm(_prompt):
        return "xin lỗi, tôi không chắc"

    d = NG.decide(pd.Timestamp("2026-08-11 12:00", tz="UTC"),
                  headlines=["tin gì đó"], call_llm=garbage_llm, calendar_path=calendar_file, force=True)
    assert not d.blocked
    assert d.llm_error


def test_llm_cannot_lift_calendar_block(calendar_file):
    """LLM nói không chặn nhưng lịch có NFP → VẪN CHẶN.

    Tầng 1 chỉ được phép THÊM lệnh chặn, không được gỡ. Nếu gỡ được thì một câu trả
    lời sai của model đủ để mở cửa cho cả ngày NFP.
    """
    def llm_says_no(_p):
        return json.dumps({"block": False, "severity": "NONE",
                           "currencies": [], "reason": "không có gì"})

    d = NG.decide(pd.Timestamp("2026-08-10 12:00", tz="UTC"),
                  headlines=["thị trường yên ắng"], call_llm=llm_says_no,
                  calendar_path=calendar_file, force=True)
    assert d.blocked, "LLM đã gỡ được lệnh chặn của lịch — lỗ hổng nghiêm trọng"
    assert d.source == "CALENDAR"


# ═══════════════════════════════════════════════════════ tầng 1 — LLM
def test_llm_can_add_a_block(calendar_file):
    """Ngày không có lịch nhưng có tin sốc → LLM chặn được."""
    def llm_says_block(_p):
        return json.dumps({"block": True, "severity": "HIGH",
                           "currencies": ["JPY"],
                           "reason": "BOJ can thiệp ngoại hối bất ngờ"})

    d = NG.decide(pd.Timestamp("2026-08-11 12:00", tz="UTC"),
                  headlines=["BOJ intervenes in FX market"], call_llm=llm_says_block,
                  calendar_path=calendar_file, force=True)
    assert d.blocked and d.source == "LLM" and d.llm_used
    assert d.currencies == ("JPY",)
    assert d.blocks_instrument("CADJPY")
    assert not d.blocks_instrument("AUDCAD")


def test_parse_llm_extracts_json_from_code_fence():
    txt = '```json\n{"block": true, "severity": "HIGH", "currencies": ["USD"], ' \
          '"reason": "khẩn cấp"}\n```'
    d = NG.parse_llm_response(txt)
    assert d["block"] is True and d["currencies"] == ["USD"]


def test_prompt_is_single_layer_and_demands_json():
    """Prompt phải yêu cầu JOSN thuần và KHÔNG có tầng chuyên gia/chủ tịch."""
    cal = NG.GuardDecision(timestamp=pd.Timestamp("2026-08-11"), blocked=False,
                           source="CALENDAR")
    p = NG.build_prompt(pd.Timestamp("2026-08-11 12:00", tz="UTC"),
                        ["tin 1", "tin 2"], ["AUDCAD"], cal)
    assert "JSON only" in p
    assert "mean-reversion" in p.lower()
    for tu in ("expert", "chairman", "panel", "debate", "layer 2"):
        assert tu not in p.lower(), f"prompt còn dấu vết kiến trúc nhiều tầng: {tu}"


def test_prompt_states_normal_news_is_not_blocked():
    """Chặn thừa tốn edge thật. Prompt phải nói rõ điều đó, không để model tự đoán."""
    cal = NG.GuardDecision(timestamp=pd.Timestamp("2026-08-11"), blocked=False,
                           source="CALENDAR")
    p = NG.build_prompt(pd.Timestamp("2026-08-11 12:00", tz="UTC"), ["x"], [], cal)
    assert "DO NOT block" in p
    assert "false block costs real edge" in p


# ═══════════════════════════════════════════════════════ bản ghi
def test_records_even_when_not_blocking(calendar_file):
    """Cổng phải ghi cả lúc THÔNG — nếu không thì không trả lời được câu hỏi
    'vì sao hôm nay không có lệnh nào'."""
    d = NG.decide(pd.Timestamp("2026-08-11 12:00", tz="UTC"), calendar_path=calendar_file, force=True)
    row = d.to_row()
    for k in ("timestamp", "blocked", "source", "severity", "reason"):
        assert k in row
    assert row["reason"]
    json.dumps(row)


def test_explain_is_readable(calendar_file):
    d = NG.decide(pd.Timestamp("2026-08-10 12:00", tz="UTC"), calendar_path=calendar_file, force=True)
    s = d.explain()
    assert "CHẶN" in s and "NFP" in s


# ═══════════════════════════════════════════════════════ công tắc
def test_disabled_by_default(calendar_file, monkeypatch):
    """Cổng phải TẮT theo mặc định — đo được nó làm hại trên rổ cross hiện tại.

    Vòng 63: lệnh vào ngày tin có net +10,33 bps so với +6,35 ngày thường, và chặn
    mọi tin kéo Sharpe trung vị 0,811 → 0,622. Cross không chứa USD phản ứng thái quá
    với tin Mỹ rồi hồi về — sự lệch đó CHÍNH LÀ thứ chiến lược khai thác.
    """
    monkeypatch.delenv("NEWS_GUARD", raising=False)
    d = NG.decide(pd.Timestamp("2026-08-10 12:00", tz="UTC"), calendar_path=calendar_file)
    assert not d.blocked, "cổng bật mặc định — sẽ lấy đi 23% Sharpe"
    assert d.source == "DISABLED"
    assert "0,811" in d.reason or "TẮT" in d.reason


def test_enabled_via_environment_variable(calendar_file, monkeypatch):
    monkeypatch.setenv("NEWS_GUARD", "1")
    d = NG.decide(pd.Timestamp("2026-08-10 12:00", tz="UTC"), calendar_path=calendar_file)
    assert d.blocked and d.source == "CALENDAR"

    monkeypatch.setenv("NEWS_GUARD", "0")
    d2 = NG.decide(pd.Timestamp("2026-08-10 12:00", tz="UTC"), calendar_path=calendar_file)
    assert not d2.blocked


def test_reads_the_time_utc_column(tmp_path, monkeypatch):
    """Lịch thật dùng cột `time_utc`. Đọc trượt tên cột làm cổng THÔNG âm thầm.

    Đây là lỗi đã xảy ra: module tìm cột `time`, lịch có `time_utc`, và cổng trả
    THÔNG suốt mà không báo lỗi nào — đúng dạng hỏng im lặng nguy hiểm nhất.
    """
    df = pd.DataFrame({
        "time_utc": pd.to_datetime(["2026-08-10 12:30"]),
        "event": ["NFP"], "impact": ["high"], "source": ["forexfactory"]})
    p = tmp_path / "cal.parquet"
    df.to_parquet(p)
    NG._cache["df"], NG._cache["mtime"] = None, None
    monkeypatch.setenv("NEWS_GUARD", "1")
    d = NG.decide(pd.Timestamp("2026-08-10 09:00", tz="UTC"), calendar_path=p)
    assert d.blocked and "NFP" in d.events


def test_maps_event_to_currency():
    """Lịch không có cột tiền tệ — phải suy từ tên sự kiện, và suy đúng."""
    assert NG._currencies_of(["NFP"]) == ("USD",)
    assert NG._currencies_of(["ECB_RATE"]) == ("EUR",)
    assert NG._currencies_of(["BOE_RATE"]) == ("GBP",)
    assert set(NG._currencies_of(["NFP", "ECB_RATE"])) == {"USD", "EUR"}
    assert NG._currencies_of(["KHONG_BIET"]) == ()
