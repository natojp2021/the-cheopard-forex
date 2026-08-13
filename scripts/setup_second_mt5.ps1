# setup_second_mt5.ps1 - dung BAN MT5 THU HAI cho The Cheopard Forex,
# chay song song voi ban MT5 dang phuc vu he XAUUSD.

param(
    [string]$Source = "C:\Program Files\MetaTrader 5",
    [string]$Target = "C:\Program Files\MetaTrader 5 - Forex"
)

$ErrorActionPreference = "Stop"

Write-Host "== Dung ban MT5 thu hai cho The Cheopard Forex ==" -ForegroundColor Cyan
Write-Host "   nguon : $Source"
Write-Host "   dich  : $Target"
Write-Host ""

if (-not (Test-Path $Source)) {
    throw "Khong thay ban MT5 goc o '$Source'. Truyen -Source <duong dan> neu cai o cho khac."
}
if (-not (Test-Path (Join-Path $Source "terminal64.exe"))) {
    throw "'$Source' khong chua terminal64.exe - kiem tra lai duong dan."
}

# Terminal dang chay se khoa file, sao chep se hong nua chung.
$running = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "!! Dang co $($running.Count) tien trinh terminal64 chay." -ForegroundColor Yellow
    Write-Host "   Co the can dung terminal64 khi copy hoac tiep tuc neu khong bi lock." -ForegroundColor Yellow
}

if (Test-Path $Target) {
    Write-Host "!! '$Target' da ton tai." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $Target
}

Write-Host "-> Sao chep thu muc terminal (vai tram MB, doi mot chut)..."
Copy-Item -Recurse -Force $Source $Target

# Chi giu phan can de chay.
foreach ($d in @("Bases", "Logs", "MQL5\Logs", "Tester")) {
    $p = Join-Path $Target $d
    if (Test-Path $p) { Remove-Item -Recurse -Force $p -ErrorAction SilentlyContinue }
}

$launcher = "@echo off`r`nstart `"`" `"%~dp0terminal64.exe`" /portable"
Set-Content -Path (Join-Path $Target "start_mt5_forex.bat") -Value $launcher -Encoding ASCII

Write-Host ""
Write-Host "== XONG ==" -ForegroundColor Green
Write-Host "   1. Chay: $Target\start_mt5_forex.bat"
Write-Host "   2. Dang nhap tai khoan FTMO cua he Forex trong ban nay"
Write-Host "   3. Bat Algo Trading (Ctrl+E)"
Write-Host "   4. Them dong nay vao .env cua repo Forex:"
Write-Host "         MT5_PATH=$Target\terminal64.exe" -ForegroundColor Yellow
