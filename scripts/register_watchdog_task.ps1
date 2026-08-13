# register_watchdog_task.ps1 — Retail Trader Evolution (25/07)
#
# Đăng ký Windows Scheduled Task gọi `fleet_supervisor.py watchdog` định kỳ
# (mặc định mỗi 5 phút) — thay thế cơ chế `scripts/watchdog.py` cũ đã bị xoá
# hoàn toàn ở v4.6.0 (cùng `scripts/register_windows_task.ps1` cũ).
#
# KHÁC BẢN CŨ: bản cũ tự chạy 1 process Python nền liên tục tự poll heartbeat.
# Bản mới nhẹ hơn — Task Scheduler tự đánh thức 1 lệnh CLI ngắn mỗi N phút rồi
# thoát ngay (fleet_supervisor.py watchdog đọc heartbeat.json, restart nếu
# treo, rồi kết thúc), không có process nền nào phải tự quản lý vòng lặp.
#
# QUAN TRỌNG: script này KHÔNG tự chạy khi bạn Read nó — phải tự tay chạy
# (PowerShell, quyền Administrator) khi bạn quyết định muốn bật cơ chế này.
# Đây là thay đổi hệ thống thật (Windows Task Scheduler), không phải chỉ sửa
# code trong repo — hãy tự xác nhận trước khi chạy.
#
# Cách dùng:
#   powershell -ExecutionPolicy Bypass -File scripts\register_watchdog_task.ps1
#
# Gỡ bỏ:
#   Unregister-ScheduledTask -TaskName "CheopardWatchdog" -Confirm:$false

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $RepoRoot ".venv311\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    Write-Host "Khong tim thay $PythonExe -- kiem tra lai duong dan .venv311." -ForegroundColor Red
    exit 1
}

$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "-m src.python.fleet_supervisor watchdog" `
    -WorkingDirectory $RepoRoot

$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration ([TimeSpan]::MaxValue)

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 3) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName "CheopardWatchdog" `
    -Action $Action -Trigger $Trigger -Settings $Settings `
    -Description "Kiem tra heartbeat.json cua fleet_supervisor moi 5 phut, tu restart account bi treo (deadlock)." `
    -Force

Write-Host "Da dang ky task 'CheopardWatchdog' -- goi 'fleet_supervisor.py watchdog' moi 5 phut." -ForegroundColor Green
Write-Host "Kiem tra: Get-ScheduledTask -TaskName CheopardWatchdog | Get-ScheduledTaskInfo"
