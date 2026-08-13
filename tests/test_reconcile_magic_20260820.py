"""Vị thế do CHÍNH HỆ mở không được coi là mồ côi — nhận diện bằng MAGIC.

SỰ CỐ 22:08 NGÀY 20/08/2026 — MỞ 22 LỆNH RỒI TỰ KHOÁ MÌNH
==========================================================
Bật được AutoTrading, hệ mở 22 vị thế sạch sẽ:

    [OK ] GBPJPY OPEN BUY 0.35 lot @ 216.43 · notional $47,723 · SL 207.36 · retcode 10009
    ... 22 lệnh, 0 lệnh bị từ chối

Chu kỳ sau, hệ khoá chính mình:

    [ĐỐI SOÁT] 0 khớp, 22 lạ, 0 đã đóng nơi khác
    KHÔNG GỬI LỆNH NÀO — CHẶN: đối soát khởi động CHƯA xong

Giả định sai nằm ngay trong phép so: sổ chỉ ghi `PF.SINGLE_LEGS`, còn 22 lệnh kia
do các chân XẾP HẠNG sinh ra (`X-MR-H1`, `CCY-REV`, `CCY-CARRY`, `X-XS-H4`,
`X-MOM-D1`). Chân xếp hạng giao dịch theo RỔ — một chân chạm nhiều công cụ — nên
không có khoá chân nào để ghi. So sổ-CHÂN với vị thế-CÔNG CỤ thì vị thế của chân
xếp hạng vĩnh viễn là mồ côi.

Câu hỏi `orphan` cần trả lời là "vị thế này có phải do HỆ mở không". MAGIC trả lời
được câu đó: `order_router.magic_for` sinh magic tất định trong
`[MAGIC_BASE, MAGIC_BASE + 90000)`. Đo 22:14 trên chính tài khoản: 22/22 vị thế
nằm trong khoảng đó.

Điều PHẢI GIỮ, và là lý do bộ test này tồn tại: fail-closed không được nới. Lệnh
tay, EA khác, bot khác dùng chung tài khoản — magic ngoài khoảng — vẫn phải là MỒ
CÔI và vẫn phải chặn lệnh mới.
"""
from __future__ import annotations

from src.python.execution.order_router import MAGIC_BASE
from src.python.execution.position_book import PositionBook


class _Pos:
    """Đủ các trường `reconcile()` đọc, không hơn."""

    def __init__(self, symbol: str, volume: float, magic: int, type_: int = 0):
        self.symbol, self.volume, self.magic, self.type = symbol, volume, magic, type_


def _book(tmp_path, monkeypatch) -> PositionBook:
    """So vi the trong `tmp_path`, KHONG phai so cua tai khoan that.

    Ban dau ham nay nhan `tmp_path` roi bo qua no va goi `PositionBook()` voi
    duong dan mac dinh — tuc SO CUA TAI KHOAN LIVE. Test xanh nhieu ngay chi vi
    so tinh co dang rong; ngay bot mo vi the that thi no do, voi ba khoa chan
    that trong `closed_elsewhere`.

    `tests/conftest.py` da va `BOOK_PATH` cho moi test, nhung truyen thang duong
    dan o day de test nay tu no dung ngay ca khi ai do go fixture kia.
    """
    monkeypatch.setattr("src.python.execution.position_book._login_now",
                        lambda: "test", raising=False)
    return PositionBook(path=tmp_path / "position_book.json")


def test_own_magic_is_not_orphan(tmp_path, monkeypatch) -> None:
    """22 vị thế mang magic của hệ, sổ rỗng — phải SẠCH, không phải 22 mồ côi."""
    book = _book(tmp_path, monkeypatch)
    pos = [_Pos(f"SYM{i}", 0.1, MAGIC_BASE + i * 137) for i in range(22)]
    rec = book.reconcile(pos, auto_close_missing=False)
    assert rec.orphan == []
    assert rec.ok, rec.explain()


def test_foreign_magic_still_orphan(tmp_path, monkeypatch) -> None:
    """Lệnh TAY (magic 0) vẫn là mồ côi và vẫn phải chặn lệnh mới.

    Đây là phần KHÔNG được nới. Bản vá chỉ bỏ báo động giả về vị thế của chính
    mình; một vị thế lạ trên cùng tài khoản vẫn làm mọi phép tính phơi nhiễm sai,
    nên cổng vẫn phải đóng.
    """
    book = _book(tmp_path, monkeypatch)
    rec = book.reconcile([_Pos("EURUSD", 0.5, 0)], auto_close_missing=False)
    assert rec.orphan == ["EURUSD"]
    assert not rec.ok


def test_magic_just_outside_range_is_orphan(tmp_path, monkeypatch) -> None:
    """Biên phải đóng: magic = MAGIC_BASE + span là NGOÀI dải."""
    book = _book(tmp_path, monkeypatch)
    rec = book.reconcile([_Pos("EURUSD", 0.5, MAGIC_BASE + 90_000)],
                         auto_close_missing=False)
    assert rec.orphan == ["EURUSD"]
    rec2 = book.reconcile([_Pos("EURUSD", 0.5, MAGIC_BASE - 1)],
                          auto_close_missing=False)
    assert rec2.orphan == ["EURUSD"]


def test_mixed_own_and_foreign(tmp_path, monkeypatch) -> None:
    """Có cả hai thì chỉ cái LẠ bị báo — và chỉ cần một cái lạ là cổng đóng."""
    book = _book(tmp_path, monkeypatch)
    rec = book.reconcile([_Pos("GBPJPY", 0.35, MAGIC_BASE + 12),
                          _Pos("XAUUSD", 1.00, 999999)],
                         auto_close_missing=False)
    assert rec.orphan == ["XAUUSD"]
    assert not rec.ok


def test_disabling_magic_layer_restores_old_behaviour(tmp_path, monkeypatch) -> None:
    """`own_magic_base=-1` tắt lớp nhận diện — dùng để tái hiện lỗi cũ trong test."""
    book = _book(tmp_path, monkeypatch)
    rec = book.reconcile([_Pos("GBPJPY", 0.35, MAGIC_BASE + 12)],
                         auto_close_missing=False, own_magic_base=-1)
    assert rec.orphan == ["GBPJPY"]
