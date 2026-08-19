# -*- coding: utf-8 -*-
"""CONSOLE VẬN HÀNH — bốn nhóm bất biến, mỗi nhóm neo vào một sự cố đã đo được.

BẰNG CHỨNG GỐC: nhật ký VPS ngày 18/08/2026
============================================
    04:11:34 | spread VƯỢT trần 3.0 bps: AUDCAD 7.0, AUDCHF 8.85, AUDJPY 6.27, …
    04:11:38 | spread VƯỢT trần 3.0 bps: AUDCAD 7.0, AUDCHF 8.85, AUDJPY 6.35, …
    … lặp mỗi 5 giây, ~590 dòng trong 49 phút, mỗi dòng liệt kê 20 công cụ

Hệ đã có HAI lớp khử lặp và cả hai đều không chặn được, vì cùng một lý do: dấu vân
tay dedup CÓ CHỨA những con số đổi mỗi tick. Bài học chung — dấu vân tay của một
trạng thái phải chỉ chứa phần ĐỊNH TÍNH; nhồi số đo vào đó là tự vô hiệu hoá lớp
dedup mà vẫn tưởng đang có nó.

Bốn nhóm:
  1. `_Squelch` — nén được ĐÚNG hình dạng spam đã xảy ra, và vẫn nhả dòng nhắc lại.
  2. `classify` — nhóm/mức đúng, kể cả ca chữ tốt và chữ xấu nằm trong cùng một dòng.
  3. Sổ JSONL — nén ở console KHÔNG được làm mất bản ghi.
  4. Nhịp tim và báo cáo — trả lời được năm câu hỏi, và không ném khi trạng thái rỗng.
"""
from __future__ import annotations

import json

import pytest

from src.python.core import ops_console as OC


# ─────────────────────────────────────────── 1. bộ nén spam
def _spread_line(n: float) -> str:
    """Đúng hình dạng dòng đã ngập nhật ký — chỉ khác nhau ở con số."""
    return (f"spread VƯỢT trần 3.0 bps: AUDCAD 7.0, AUDCHF {n}, AUDJPY 6.27, "
            f"AUDNZD 10.55, CADCHF 9.58")


def test_squelch_collapses_the_real_spread_episode():
    """Tái hiện ĐÚNG đợt spam đã đo: 590 nhịp cách nhau 5 giây (49 phút).

    Kỳ vọng KHÔNG phải "một dòng duy nhất", và đó là chủ ý. Bộ nén nhả lại một dòng
    mỗi `SQUELCH_WINDOW`, nên một đợt 49 phút cho ra khoảng 10 dòng. Nén xuống đúng
    MỘT dòng cho cả 49 phút sẽ đổi vấn đề ngập log thành vấn đề tệ hơn: im lặng suốt
    lúc đang hỏng, không có cách nào biết đợt đó còn tiếp diễn hay đã hết.

    Con số cần kiểm là ĐỘ GIẢM, không phải giá trị tuyệt đối: 590 -> khoảng 10 là
    khoảng 59 lần.
    """
    sq = OC._Squelch()
    shown = sum(1 for i in range(590)
                if sq.allow(_spread_line(8.0 + i * 0.01), now=1000.0 + i * 5.0)[0])
    expected = 2950.0 / OC.SQUELCH_WINDOW
    assert shown <= expected + 1, f"nén không ăn: vẫn in {shown} dòng"
    assert shown >= 2, "nén quá tay: cả đợt 49 phút chỉ còn một dòng"
    assert 590 / shown > 50, f"chỉ giảm được {590 / shown:.0f} lần"


def test_squelch_releases_a_reminder_and_reports_how_many_it_ate():
    """Sự cố dai dẳng KHÔNG được biến mất hoàn toàn — phải có dòng nhắc kèm số đã nén.

    Nén vĩnh viễn là cách đổi một vấn đề (ngập log) thành một vấn đề tệ hơn (im lặng
    trong lúc đang hỏng). Dòng nhắc là chỗ phân biệt hai thứ đó.
    """
    sq = OC._Squelch()
    assert sq.allow(_spread_line(8.0), now=0.0)[0] is True
    for i in range(1, 50):
        sq.allow(_spread_line(8.0 + i * 0.01), now=float(i))
    show, suffix = sq.allow(_spread_line(9.9), now=OC.SQUELCH_REMIND + 1.0)
    assert show is True, "đợt dai dẳng bị nén vĩnh viễn"
    assert "đã nén" in suffix and "49" in suffix, suffix


def test_squelch_does_not_merge_genuinely_different_lines():
    """Hai sự kiện KHÁC NHAU không được nuốt nhau chỉ vì đi liền nhau."""
    sq = OC._Squelch()
    assert sq.allow("🏦 [FTMO] Ngày giao dịch mới 2026-08-18", now=0.0)[0] is True
    assert sq.allow("⚠️ [FX-M1] fetch thất bại cho EURUSD", now=1.0)[0] is True
    assert sq.allow("🚨 [FTMO GUARD] chạm mốc lỗ ngày", now=2.0)[0] is True


def test_squelch_forgets_old_fingerprints():
    """Bộ nhớ vân tay phải được dọn — chạy hàng tuần thì nó là một chỗ rò rỉ chậm."""
    sq = OC._Squelch()
    for i in range(2100):
        sq.allow(f"dòng khác nhau về CHỮ số {chr(65 + i % 26)}{i}", now=0.0)
    sq.allow("mốc mới", now=OC.SQUELCH_REMIND * 3)
    assert len(sq._seen) < 2100, "không dọn vân tay cũ"


# ─────────────────────────────────────────── 2. phân loại
@pytest.mark.parametrize("msg,category", [
    ("🏦 [FTMO] Ngày giao dịch mới — mốc balance $100,000.00", "risk"),
    ("spread VƯỢT trần 3.0 bps: 20/27 công cụ", "risk"),
    ("⚠️ [FX-M1] fetch dữ liệu MT5 thất bại cho EURUSD", "market"),
    ("SPREAD THẬT 27 công cụ · trung vị lệch -66%", "market"),
    ("[SỔ] zb_audcad_h1: mở vị thế", "trading"),
    ("[API_BUDGET] còn 12/25 lượt hôm nay", "ai"),
])
def test_classify_assigns_expected_category(msg, category):
    assert OC.classify(msg)[0] == category, msg


@pytest.mark.parametrize("msg,level", [
    ("LỖI · dựng kế hoạch lệnh: thiếu M1", "error"),
    ("⛔ Không nối được MT5 lúc khởi động", "error"),
    ("⚠️ DỮ LIỆU CŨ · EURUSD", "warn"),
    ("spread VƯỢT trần 3.0 bps: 20/27 công cụ", "warn"),
    ("🔌 Kết nối thành công | build f379eaa", "good"),
    ("spread mọi công cụ đã về dưới trần 3.0 bps", "good"),
])
def test_classify_assigns_expected_level(msg, level):
    assert OC.classify(msg)[1] == level, msg


def test_classify_prefers_good_over_warn_in_mixed_summary_lines():
    """"Hoàn tất … 3 lệnh CHƯA khớp sổ" là tin TỐT (đã chạy xong), không phải cảnh báo.

    Nếu `warn` thắng thì mọi dòng tổng kết có kèm số liệu xấu đều bị tô hổ phách, và
    người vận hành mất khả năng phân biệt "đã xong" với "đang hỏng" — đúng thứ mà
    việc tô màu sinh ra để làm.
    """
    msg = "🔍 [ĐỐI SOÁT] Hoàn tất đối chiếu khởi động: 3 lệnh CHƯA khớp sổ"
    assert OC.classify(msg)[1] == "good"


def test_classify_never_raises_on_odd_input():
    """Tầng trình bày không được ném vì một dòng log lạ."""
    for bad in ("", None, "x" * 5000, "[/]", "\x00\x01"):
        category, level = OC.classify(bad)  # type: ignore[arg-type]
        assert category and level


# ─────────────────────────────────────────── 3. nén ở console không mất bản ghi
def test_squelched_lines_still_reach_the_jsonl_ledger(tmp_path, capsys):
    """Nén là việc của MÀN HÌNH, không phải của SỔ.

    Đảo thứ tự hai bước (nén trước, ghi sau) sẽ đánh mất chính những dòng cần cho
    việc truy vết về sau — và nó là một lỗi không ai phát hiện được cho tới lúc phải
    dựng lại một sự cố đã qua.
    """
    from src.python.utils import ops_log

    ops_log.set_root(tmp_path)
    try:
        console = OC.OpsConsole(heartbeat_seconds=9999.0)
        for i in range(30):
            console.event(_spread_line(8.0 + i * 0.01))
    finally:
        ops_log.set_root(None)

    printed = [ln for ln in capsys.readouterr().out.splitlines() if "spread" in ln]
    assert len(printed) == 1, f"màn hình nhận {len(printed)} dòng, phải là 1"

    rows = [json.loads(ln) for ln in
            (tmp_path / "risk").glob("*.jsonl").__iter__().__next__()
            .read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(rows) == 30, f"sổ chỉ giữ {len(rows)}/30 bản ghi"
    assert all(r["level"] == "warn" for r in rows)


def test_ops_log_survives_an_unwritable_directory(monkeypatch, tmp_path):
    """Ghi sổ hỏng KHÔNG được ném ra ngoài — nó là tầng quan sát, không phải nghiệp vụ."""
    from src.python.utils import ops_log

    ops_log.set_root(tmp_path)
    monkeypatch.setattr(ops_log.Path, "mkdir",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("ổ đầy")))
    try:
        ops_log.emit("system", "thử", value=1)      # không được ném
    finally:
        ops_log.set_root(None)


def test_ops_log_skips_corrupt_lines_when_reading_back(tmp_path):
    """Dòng hỏng (bị kill giữa lúc ghi) chỉ mất chính nó, không làm hỏng cả lượt đọc.

    Đây là lý do chọn JSONL thay vì một tệp JSON duy nhất: hệ này chạy trên VPS bị
    watchdog kill, nên "hỏng dòng cuối" là chuyện sẽ xảy ra.
    """
    from datetime import datetime

    from src.python.utils import ops_log

    ops_log.set_root(tmp_path)
    try:
        ops_log.emit("system", "ok1")
        path = next((tmp_path / "system").glob("*.jsonl"))
        with path.open("a", encoding="utf-8") as fh:
            fh.write('{"ts": "cut off in the middl\n')
        ops_log.emit("system", "ok2")
        rows = ops_log.read_today("system")
    finally:
        ops_log.set_root(None)
    assert [r["event"] for r in rows] == ["ok1", "ok2"]
    assert datetime.now().strftime("%Y-%m-%d") in path.name


# ─────────────────────────────────────────── 4. nhịp tim & báo cáo
def test_heartbeat_answers_the_five_questions(tmp_path, capsys):
    """Một dòng nhịp tim phải chứa đủ: sống? · thị trường? · làm gì? · rủi ro? · vừa gì?"""
    from src.python.utils import ops_log

    ops_log.set_root(tmp_path)
    try:
        console = OC.OpsConsole(heartbeat_seconds=0.0)
        console.status({
            "mt5_connected": True, "equity": 99451.29, "daily_profit": -281.4,
            "positions_list": [{"magic": 1}],
            "guards": {"dd_pct": 0.28, "breaker_tripped": False,
                       "spread": {"over": {"GBPNZD": 13.9}}},
            "sentiment": {"regime": "STRUCTURAL_TREND"},
        })
    finally:
        ops_log.set_root(None)
    line = [ln for ln in capsys.readouterr().out.splitlines() if "MT5" in ln][-1]
    for token in ("MT5 OK", "eq $99,451.29", "dd 0.28%", "pos 1",
                  "STRUCTURAL_TREND", "AN TOÀN"):
        assert token in line, f"nhịp tim thiếu {token!r}: {line}"


def test_regime_change_is_reported_immediately_not_at_next_heartbeat(tmp_path, capsys):
    """Trạng thái thị trường đổi là sự kiện phải thấy NGAY.

    Chờ tới nhịp tim kế tiếp có thể là 45 giây sau, và trong 45 giây đó người vận
    hành đọc màn hình sẽ thấy trạng thái CŨ — tức thông tin sai, không phải thông tin
    chậm.
    """
    from src.python.utils import ops_log

    ops_log.set_root(tmp_path)
    try:
        console = OC.OpsConsole(heartbeat_seconds=9999.0)
        console.status({"sentiment": {"regime": "ROUTINE_NORMAL"}})
        console.status({"sentiment": {"regime": "CRISIS_SHOCK"}})
    finally:
        ops_log.set_root(None)
    out = capsys.readouterr().out
    assert "TRẠNG THÁI ĐỔI" in out
    assert "ROUTINE_NORMAL" in out and "CRISIS_SHOCK" in out


def test_first_regime_reading_is_not_reported_as_a_change(tmp_path, capsys):
    """Lần đọc ĐẦU là khởi động, không phải một lần ĐỔI — báo nó là báo động giả."""
    from src.python.utils import ops_log

    ops_log.set_root(tmp_path)
    try:
        console = OC.OpsConsole(heartbeat_seconds=9999.0)
        console.status({"sentiment": {"regime": "ROUTINE_NORMAL"}})
    finally:
        ops_log.set_root(None)
    assert "TRẠNG THÁI ĐỔI" not in capsys.readouterr().out


def test_shutdown_report_shouts_about_positions_left_open(tmp_path, capsys):
    """Dừng bot KHÔNG đóng lệnh — báo cáo tắt máy phải nói thẳng điều đó.

    Đây là dòng quan trọng nhất của cả báo cáo: từ giây đó không còn ai chạy
    trailing/BE/time-stop cho những vị thế ấy. Một người vận hành đóng cửa sổ mà
    tưởng đã "tắt hết" là cách mất tài khoản.
    """
    from src.python.utils import ops_log

    ops_log.set_root(tmp_path)
    try:
        console = OC.OpsConsole(heartbeat_seconds=9999.0)
        console.status({"positions_list": [{"magic": 1}, {"magic": 2}],
                        "equity": 99000.0, "guards": {}})
        console.shutdown_report("Ctrl+C")
    finally:
        ops_log.set_root(None)
    out = capsys.readouterr().out
    assert "2 vị thế VẪN MỞ" in out
    assert "KHÔNG CÓ hệ nào quản lý" in out


def test_rich_markup_in_log_text_is_escaped_not_interpreted(tmp_path, capsys):
    """`[FTMO]`, `[SỔ]`, `[FX-M1]` là NỘI DUNG, không phải thẻ định dạng.

    Không escape thì Rich ném `MarkupError` hoặc âm thầm ăn mất đoạn chữ — và nó xảy
    ra trên ĐÚNG những dòng quan trọng nhất (mốc FTMO, sự cố dữ liệu, sổ vị thế).
    """
    from src.python.utils import ops_log

    ops_log.set_root(tmp_path)
    try:
        console = OC.OpsConsole(heartbeat_seconds=9999.0)
        console.event("[SỔ] zb_audcad_h1: mở vị thế 1.0 lot")
    finally:
        ops_log.set_root(None)
    out = capsys.readouterr().out
    assert "[SỔ]" in out, out
    assert "zb_audcad_h1" in out
