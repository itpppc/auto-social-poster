# Ton.AI Auto Poster — Windows Service Installer
# รันใน PowerShell as Administrator:
#   Set-ExecutionPolicy Bypass -Scope Process -Force
#   .\install_service.ps1

$TaskName = "TonAI-AutoPoster"
$Python   = "C:\Python313\python.exe"
$Script   = "F:\ProjectAI\auto_poster\run_service.py"
$WorkDir  = "F:\ProjectAI\auto_poster"

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Ton.AI Auto Poster Service Install" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Verify Python exists
if (-not (Test-Path $Python)) {
    Write-Host "ERROR: Python not found at $Python" -ForegroundColor Red
    exit 1
}

# Verify script exists
if (-not (Test-Path $Script)) {
    Write-Host "ERROR: Script not found at $Script" -ForegroundColor Red
    exit 1
}

# Remove old tasks
Write-Host "Removing old tasks..." -ForegroundColor Yellow
@("AutoSocialPoster", "AutoPoster", $TaskName) | ForEach-Object {
    Unregister-ScheduledTask -TaskName $_ -Confirm:$false -ErrorAction SilentlyContinue
}

# Create scheduled task
$action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument $Script `
    -WorkingDirectory $WorkDir

# Run at system startup
$trigger = New-ScheduledTaskTrigger -AtStartup

# Settings: no time limit, restart on failure (up to 999 times)
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -Priority 7

# S4U = runs even when user is NOT logged in (no password needed)
$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Highest

$task = Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Ton.AI Auto Poster — Scheduler + Dashboard Service" `
    -Force

if ($task) {
    Write-Host ""
    Write-Host "Service installed successfully!" -ForegroundColor Green
    Write-Host "  Task name : $TaskName" -ForegroundColor White
    Write-Host "  Runs as   : $env:USERNAME (no login needed)" -ForegroundColor White
    Write-Host "  Startup   : Automatic (at boot)" -ForegroundColor White
    Write-Host "  Auto-restart: Every 1 min if crashed" -ForegroundColor White
    Write-Host ""

    $start = Read-Host "Start service now? (Y/N)"
    if ($start -match "^[Yy]") {
        Start-ScheduledTask -TaskName $TaskName
        Start-Sleep -Seconds 2
        $info = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host "Service started! Last run: $($info.LastRunTime)" -ForegroundColor Green
        Write-Host ""
        Write-Host "Dashboard: http://localhost:5001" -ForegroundColor Cyan
        Write-Host "Log file : $WorkDir\service.log" -ForegroundColor Cyan
    }
} else {
    Write-Host "ERROR: Failed to register task." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Use service_control.bat to Start/Stop/Status" -ForegroundColor Yellow
