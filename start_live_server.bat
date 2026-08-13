@echo off
REM ============================================================
REM  The Cheopard Forex - CHAY BOT (console-only tu 19/08/2026)
REM
REM  Cua so nay CHINH LA ung dung. Dong no la dung bot.
REM
REM  DA XOA `start_live_server.vbs` cung dot nay: tep do chay bang
REM  `pythonw.exe` de an cua so den, va `pythonw` KHONG CO console.
REM  Voi mot app console-only thi no khong hien duoc gi ca - bot chay
REM  ma khong co dau vet nao, dung cai loi "nhan vao ma khong thay gi"
REM  ma chinh tep VBS do sinh ra hoi 14/08.
REM
REM  DIEU KHIEN BOT (thay cac nut cua bang dieu khien cu):
REM      python -m src.python.ops_ctl status
REM      python -m src.python.ops_ctl run ^| stop
REM      python -m src.python.ops_ctl positions
REM      python -m src.python.ops_ctl flatten --confirm
REM  Chung chay o TIEN TRINH KHAC va noi chuyen qua cong tac tren dia, nen
REM  doi duoc tu mot cua so thu hai ma khong cham vao tien trinh bot.
REM
REM  Muon dung EM tu ben ngoai (watchdog, task theo lich):
REM      tao tep data\live\STOP_REQUESTED
REM  Dung `taskkill` co the cat giua luc gui lenh -> vi the khong co SL.
REM
REM  Bat buoc dung .venv311 (Python 3.11): thu vien MetaTrader5 chi ho
REM  tro Python <= 3.11.
REM ============================================================
setlocal
cd /d "%~dp0"

set "PYEXE=%~dp0.venv311\Scripts\python.exe"

if not exist "%PYEXE%" (
    echo [LOI] Khong tim thay venv Python 3.11 tai: %PYEXE%
    echo.
    echo Tao truoc bang:
    echo     py -3.11 -m venv .venv311
    echo     .venv311\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

REM UTF-8 cho console Windows. Khong co dong nay thi cac dong log co emoji
REM (`[FTMO]` chot von ban dau, moc lo ngay) bi mat hoac ra dau hoi - dung ba
REM dong quan trong nhat luc khoi dong.
chcp 65001 >nul 2>&1

echo Dang khoi dong The Cheopard Forex...
echo.
"%PYEXE%" -m src.python.live_server %*

echo.
echo Bot da dung.
pause
endlocal
