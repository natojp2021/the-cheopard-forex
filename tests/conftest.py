"""Cach ly trang thai runtime cho toan bo test suite.

VI SAO TEP NAY RA DOI — 21/08/2026
==================================
`tests/test_reconcile_magic_20260820.py` bong do sau nhieu ngay xanh:

    ReconcileResult(closed_elsewhere=['rsidiv_nzdcad_h1', 'rsidiv_nzdcad_m30',
                                      'streak_gbpaud_h1'])

Ba khoa do la CHAN THAT dang giu vi the tren tai khoan live. Test goi
`PositionBook()` khong truyen duong dan, va mac dinh cua no la
`BOOK_PATH` — SO VI THE CUA TAI KHOAN THAT. Test truoc do xanh chi vi so
tinh co dang rong.

Doc so that da du te. Nhung `reconcile(auto_close_missing=True)` — mac dinh cua
chinh no — con XOA chan khoi so. Mot test chay dung luc bot dang giu vi the co
the xoa ban ghi chan khoi so THAT, va hau qua thi `position_book.py` da ghi ro:
time-stop khong bao gio kich hoat, hai chan nguoc chieu khong triet tieu nhau,
va `open()` tu choi mo lai chan do.

He XAU song song da dung phai dung ho lo nay ba lan trong mot ngay
(`trade_journal`, `allocation_policy`, `durable_event_log`). Day la lan thu tu,
o repo khac. Nen tep nay ton tai truoc khi co lan thu nam.
"""
from __future__ import annotations

import os

import pytest

# TAT GHI FILE LOG NGAY TU DAU, TRUOC MOI IMPORT.
#
# Do 17:37:26 ngay 21/08/2026: dong `[CIRCUIT BREAKER OPEN] retcode=10019 (loi
# cap tai khoan)` nam trong `logs/cheopard_forex.log` cua bot dang chay LIVE.
# `loi cap tai khoan` la chuoi `comment=` cua mot FIXTURE trong
# `test_min_lots_per_symbol_20260821`.
#
# Bo soat log theo gio doc chung nhu su co THAT cua tai khoan. Dat o day chu
# khong trong fixture vi handler file duoc tao LUC IMPORT module logger.
os.environ.setdefault("CHEOPARD_DISABLE_FILE_LOG", "1")


@pytest.fixture(autouse=True)
def _isolate_position_book(monkeypatch, tmp_path):
    """Moi test doc/ghi so vi the o `tmp_path`, khong bao gio o tai khoan that."""
    try:
        from src.python.execution import position_book as _pb

        monkeypatch.setattr(_pb, "BOOK_PATH", tmp_path / "position_book.json",
                            raising=False)
    except Exception:
        pass
    yield
