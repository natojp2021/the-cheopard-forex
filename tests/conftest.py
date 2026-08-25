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

# TAT SMTP THAT NGAY TU DAU, TRUOC MOI IMPORT — cung ly do voi dong tren.
#
# SU CO 25/08/2026: mot dot chay pytest gui THAT mot email "vao lenh SELL
# AUDCAD" toi hop thu van hanh, du danh muc dang chay chi con 3 cap EU/GU/UJ —
# du lieu AUDCAD/trade_id gia (#12345) la cua mot FIXTURE test, khong phai
# giao dich that. `.env` cua repo nay dat APP_ENV=PROD (bat buoc cho bot LIVE),
# va conftest truoc do KHONG co dong nao chan `mailer.send()` doc lai bien do —
# nen MOI test cham vao duong gui email deu gui THAT ra SMTP that, khong can
# mock rieng. Ep APP_ENV khac PROD o day, TRUOC khi `core.config` import va
# chot IS_PROD, la lop chan DAU TIEN.
os.environ["APP_ENV"] = "test"


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


@pytest.fixture(autouse=True)
def _block_real_smtp(monkeypatch):
    """HAI lop chan, khac tang, cung chan MOT lop hong khong keo sap ca hai:

    1. `core.config.IS_PROD` ep False — phong khi mot module da import bien
       nay TRUOC dong `os.environ["APP_ENV"]` o dau file (vd mot plugin pytest
       khac import som hon).
    2. `smtplib.SMTP`/`SMTP_SSL` NEM LOI ngay khi khoi tao — lop chan tan cung,
       giong het `quant-xau/tests/conftest.py` (repo em cung mandate, da dung
       pattern nay truoc va chua tung bi vuot qua). Dai dien cho truong hop
       MOT ham `mailer.send()` khac trong tuong lai bo qua kiem tra `IS_PROD`
       (vd mot nhanh code moi, mot ham gui thu rieng cho bao cao) — lop nay
       van chan duoc du khong biet truoc ham do la gi.
    """
    try:
        from src.python.core import config as _cfg

        monkeypatch.setattr(_cfg, "IS_PROD", False, raising=False)
    except Exception:
        pass

    import smtplib

    class _NoSMTP:
        def __init__(self, *a, **k):
            raise AssertionError(
                "Test cam mo ket noi SMTP that - mock send_email/_email o tang cao hon.")

    monkeypatch.setattr(smtplib, "SMTP", _NoSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", _NoSMTP, raising=False)
    yield
