#Requires -RunAsAdministrator
# Ton.AI Wake-on-Schedule Setup (using schtasks.exe - more reliable)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  Ton.AI Wake-on-Schedule Setup" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

$POST_TIMES = @("06:55", "11:55", "17:55")
$PYTHON = "F:\ProjectAI\auto_poster\venv\Scripts\python.exe"
$SCRIPT = "F:\ProjectAI\auto_poster\main.py"
$WORKDIR = "F:\ProjectAI\auto_poster"

# 1. Remove old tasks
Write-Host "[1] Removing old TonAI tasks..." -ForegroundColor Yellow
schtasks.exe /query /fo csv 2>$null | Select-String "TonAI-" | ForEach-Object {
    $name = ($_ -split ',')[0].Trim('"').Trim('\')
    schtasks.exe /delete /tn $name /f 2>&1 | Out-Null
    Write-Host "    Removed: $name" -ForegroundColor Gray
}

# 2. Create POST tasks with wake-to-run
Write-Host ""
Write-Host "[2] Creating wake + post tasks..." -ForegroundColor Yellow

foreach ($time in $POST_TIMES) {
    $safeName = $time.Replace(":", "")  # 06:55 -> 0655 (colons not allowed in task names)
    $taskName = "TonAI-Post-$safeName"
    $cmd = "`"$PYTHON`" `"$SCRIPT`" --now"

    # /sc DAILY /st <time> /ru <user> /rl HIGHEST
    $output = schtasks.exe /create /tn $taskName /tr $cmd /sc DAILY /st $time `
        /rl HIGHEST /ru "$env:USERNAME" /f 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "    Created: $taskName at $time" -ForegroundColor Green

        # Enable Wake-to-Run via XML modification
        $xml = schtasks.exe /query /tn $taskName /xml 2>&1
        if ($xml) {
            $xmlStr = ($xml -join "`n")
            # Add WakeToRun if not present
            if ($xmlStr -notmatch "<WakeToRun>") {
                $xmlStr = $xmlStr -replace "(<Settings>)", "`$1`n    <WakeToRun>true</WakeToRun>"
            } else {
                $xmlStr = $xmlStr -replace "<WakeToRun>false</WakeToRun>", "<WakeToRun>true</WakeToRun>"
            }
            # Also ensure starts when available
            if ($xmlStr -notmatch "<StartWhenAvailable>") {
                $xmlStr = $xmlStr -replace "(<Settings>)", "`$1`n    <StartWhenAvailable>true</StartWhenAvailable>"
            }
            # Save modified XML
            $tmpXml = "$env:TEMP\$taskName.xml"
            [System.IO.File]::WriteAllText($tmpXml, $xmlStr, [System.Text.Encoding]::Unicode)
            schtasks.exe /delete /tn $taskName /f 2>&1 | Out-Null
            schtasks.exe /create /tn $taskName /xml $tmpXml /ru "$env:USERNAME" 2>&1 | Out-Null
            Remove-Item $tmpXml -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "    FAIL $taskName : $output" -ForegroundColor Red
    }
}

# 3. Create SHUTDOWN tasks (10 min after wake)
Write-Host ""
Write-Host "[3] Creating shutdown tasks..." -ForegroundColor Yellow

foreach ($time in $POST_TIMES) {
    $wakeTime = [DateTime]::ParseExact($time, "HH:mm", $null)
    $shutdownTime = $wakeTime.AddMinutes(10).ToString("HH:mm")
    $safeShutdown = $shutdownTime.Replace(":", "")
    $taskName = "TonAI-Shutdown-$safeShutdown"

    schtasks.exe /create /tn $taskName `
        /tr "shutdown.exe /s /t 30 /c `"Ton.AI auto shutdown`"" `
        /sc DAILY /st $shutdownTime /rl HIGHEST /ru "$env:USERNAME" /f 2>&1 | Out-Null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "    Created: $taskName at $shutdownTime" -ForegroundColor Green
    } else {
        Write-Host "    FAIL $taskName" -ForegroundColor Red
    }
}

# 4. Enable wake timers in power plan
Write-Host ""
Write-Host "[4] Enabling Wake Timers in power plan..." -ForegroundColor Yellow
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP RTCWAKE 1 2>&1 | Out-Null
powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_SLEEP RTCWAKE 1 2>&1 | Out-Null
powercfg /SETACTIVE SCHEME_CURRENT
Write-Host "    Wake Timers: ENABLED" -ForegroundColor Green

# 5. Show created tasks
Write-Host ""
Write-Host "[5] Verifying tasks..." -ForegroundColor Yellow
schtasks.exe /query /fo TABLE /nh 2>$null | Select-String "TonAI-" | ForEach-Object {
    Write-Host "    $_" -ForegroundColor White
}

# 6. Summary
Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "  SETUP COMPLETE!" -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Schedule (Bangkok time):" -ForegroundColor Cyan
foreach ($time in $POST_TIMES) {
    $wakeTime = [DateTime]::ParseExact($time, "HH:mm", $null)
    $postTime = $wakeTime.AddMinutes(5).ToString("HH:mm")
    $shutdownTime = $wakeTime.AddMinutes(10).ToString("HH:mm")
    Write-Host "    Wake $time -> Post $postTime -> Shutdown $shutdownTime" -ForegroundColor White
}
Write-Host ""
Write-Host "Power usage: ~30 min/day (vs 24h)" -ForegroundColor Cyan
Write-Host "Electricity cost: ~15-25 baht/month" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Enable BIOS 'Wake on RTC' (Restart -> press Del/F2 during boot)"
Write-Host "  2. Shutdown PC normally"
Write-Host "  3. PC will wake at 06:55 and post automatically"
Write-Host ""
