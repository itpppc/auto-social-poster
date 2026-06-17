# ═══════════════════════════════════════════════════════════
# Ton.AI Wake-on-Schedule Setup
# ตั้งให้ PC ตื่นเอง → โพสต์ → ปิดเอง อัตโนมัติ
# รัน: powershell -ExecutionPolicy Bypass -File setup_wake_schedule.ps1
# ═══════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]"Administrator")) {
    Write-Host "[!] ต้องรันใน PowerShell as Administrator" -ForegroundColor Red
    Write-Host "    คลิกขวาที่ PowerShell → Run as Administrator → รันใหม่"
    exit 1
}

Write-Host ""
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Ton.AI — Wake-on-Schedule Setup" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Post times in Thai time (Bangkok)
$POST_TIMES = @("06:55", "11:55", "17:55")  # โพสต์ 3 รอบ: 07:00, 12:00, 18:00
$SHUTDOWN_AFTER_MIN = 10  # นาทีหลังจาก wake → shutdown

$PYTHON = "F:\ProjectAI\auto_poster\venv\Scripts\python.exe"
$SCRIPT = "F:\ProjectAI\auto_poster\main.py"

# ─── 1. ลบ tasks เก่า ────────────────────────────────────────
Write-Host "[1] ลบ scheduled tasks เก่า..." -ForegroundColor Yellow
$existingTasks = @("TonAI-Wake", "TonAI-Post", "TonAI-Shutdown")
foreach ($n in $existingTasks) {
    Get-ScheduledTask -TaskName "$n*" -ErrorAction SilentlyContinue | ForEach-Object {
        Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false
        Write-Host "    Removed: $($_.TaskName)" -ForegroundColor Gray
    }
}

# ─── 2. สร้าง Wake + Post tasks ──────────────────────────────
Write-Host ""
Write-Host "[2] สร้าง wake + post tasks ทุก 2 ชม. ..." -ForegroundColor Yellow

foreach ($time in $POST_TIMES) {
    $taskName = "TonAI-Post-$time"
    $trigger = New-ScheduledTaskTrigger -Daily -At $time
    $trigger.Repetition = $null

    # Wake the computer to run this task
    $settings = New-ScheduledTaskSettingsSet `
        -WakeToRun `
        -StartWhenAvailable `
        -DontStopOnIdleEnd `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

    $action = New-ScheduledTaskAction `
        -Execute $PYTHON `
        -Argument "$SCRIPT --now" `
        -WorkingDirectory "F:\ProjectAI\auto_poster"

    # S4U principal — runs without login
    $principal = New-ScheduledTaskPrincipal `
        -UserId "$env:USERDOMAIN\$env:USERNAME" `
        -LogonType S4U `
        -RunLevel Highest

    Register-ScheduledTask `
        -TaskName $taskName `
        -Trigger $trigger `
        -Settings $settings `
        -Action $action `
        -Principal $principal `
        -Description "Ton.AI Auto Post at $time (wakes PC)" `
        -Force | Out-Null

    Write-Host "    Created: $taskName" -ForegroundColor Green
}

# ─── 3. สร้าง Shutdown task (10 นาทีหลัง wake) ──────────────
Write-Host ""
Write-Host "[3] สร้าง shutdown tasks (10 นาทีหลัง wake)..." -ForegroundColor Yellow

foreach ($time in $POST_TIMES) {
    $shutdownTime = (Get-Date $time).AddMinutes($SHUTDOWN_AFTER_MIN).ToString("HH:mm")
    $taskName = "TonAI-Shutdown-$shutdownTime"
    $trigger = New-ScheduledTaskTrigger -Daily -At $shutdownTime
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries
    $action = New-ScheduledTaskAction -Execute "shutdown.exe" -Argument "/s /t 30 /c `"Ton.AI auto shutdown after post`""
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Highest

    Register-ScheduledTask -TaskName $taskName -Trigger $trigger -Settings $settings -Action $action -Principal $principal -Force | Out-Null
    Write-Host "    Created: $taskName" -ForegroundColor Green
}

# ─── 4. ตั้ง Power options ───────────────────────────────────
Write-Host ""
Write-Host "[4] ตั้งค่า BIOS Power options..." -ForegroundColor Yellow

# Enable wake timers
powercfg /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP RTCWAKE 1 2>&1 | Out-Null
powercfg /SETDCVALUEINDEX SCHEME_CURRENT SUB_SLEEP RTCWAKE 1 2>&1 | Out-Null
powercfg /SETACTIVE SCHEME_CURRENT
Write-Host "    Wake timers: ENABLED" -ForegroundColor Green

# ─── 5. สรุป ────────────────────────────────────────────────
Write-Host ""
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  ✅ Setup เสร็จสมบูรณ์!" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "📅 ตารางทำงาน (เวลาไทย):" -ForegroundColor Cyan
foreach ($time in $POST_TIMES) {
    $shutdown = (Get-Date $time).AddMinutes($SHUTDOWN_AFTER_MIN).ToString("HH:mm")
    Write-Host "    🌅 $time น. → ตื่น → โพสต์ → 🌙 $shutdown น. ปิดเอง" -ForegroundColor White
}
Write-Host ""
Write-Host "🔋 ประมาณการค่าไฟ:" -ForegroundColor Cyan
Write-Host "    เปิดแค่ 8 × 10 นาที = 80 นาที/วัน" -ForegroundColor White
Write-Host "    ค่าไฟประมาณ ฿20-30/เดือน (ถูกกว่าเปิด 24 ชม. ~5 เท่า)" -ForegroundColor White
Write-Host ""
Write-Host "📌 ขั้นตอนสุดท้าย:" -ForegroundColor Yellow
Write-Host "    1. ปิดคอม (Shutdown ปกติ — ไม่ใช่ Sleep)"
Write-Host "    2. ตรวจ BIOS Settings → Wake on RTC = Enabled"
Write-Host "       (ส่วนมาก default เปิดอยู่)"
Write-Host "    3. ที่ 07:55 น. PC จะตื่นเอง → โพสต์ → ปิดเอง"
Write-Host ""
Write-Host "🔍 ดู scheduled tasks:" -ForegroundColor Yellow
Write-Host '    Get-ScheduledTask -TaskName "TonAI-*"' -ForegroundColor Gray
Write-Host ""
