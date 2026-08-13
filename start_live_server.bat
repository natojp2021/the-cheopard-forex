@echo off
REM ============================================================
REM  The Cheopard Forex - BANG DIEU KHIEN
REM
REM  Ban CO CUA SO LOG di kem. Dung khi can xem loi; muon chay
REM  khong co cua so den thi nhan dup vao start_live_server.vbs.
REM
REM  Bat buoc dung .venv311 (Python 3.11) vi thu vien MetaTrader5
REM  chi ho tro Python <= 3.11.
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

echo Dang mo bang dieu khien The Cheopard Forex...
echo Cua so hien ra NGAY; backtest 14 chan chay o luong nen.
echo.
"%PYEXE%" -m src.python.live_server %*

echo.
echo Da dong bang dieu khien.
pause
endlocal
