# Windows Task Scheduler Auto Install

$ProjectDir = "F:\ProjectAI\auto_poster"
$PythonPath = (Get-Command python).Source
$ScriptPath = Join-Path $ProjectDir "main.py"
$TaskName   = "AutoSocialPoster"

Write-Host ""
Write-Host "Installing Windows Task Scheduler..." -ForegroundColor Blue
Write-Host ""

# Remove old task if exists
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "  -> Removed old task" -ForegroundColor Yellow
}

# Action
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "-X utf8 `"$ScriptPath`" --now" `
    -WorkingDirectory $ProjectDir

# Triggers: 3 times per day
$Triggers = @(
    $(New-ScheduledTaskTrigger -Daily -At "08:00"),
    $(New-ScheduledTaskTrigger -Daily -At "12:00"),
    $(New-ScheduledTaskTrigger -Daily -At "18:00")
)

# Settings
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -MultipleInstances IgnoreNew

# Register (current user, no admin needed)
$Principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Triggers `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Auto Social Media Poster" `
    -Force | Out-Null

Write-Host "  [OK] Task Scheduler installed!" -ForegroundColor Green
Write-Host ""
Write-Host "  Schedule: 08:00 | 12:00 | 18:00 daily" -ForegroundColor Cyan
Write-Host ""

# Test run now
Write-Host "  -> Running test now..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 5

$Info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Host "  [OK] Last run: $($Info.LastRunTime)" -ForegroundColor Green
Write-Host "  [OK] Last result: $($Info.LastTaskResult)" -ForegroundColor Green
Write-Host ""
Write-Host "  Log: $ProjectDir\auto_poster.log" -ForegroundColor White
Write-Host "  Post logs: $ProjectDir\post_logs\" -ForegroundColor White
Write-Host ""
