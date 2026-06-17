# Ton.AI Auto Poster — GitHub Secrets Setup
# รัน: powershell -ExecutionPolicy Bypass -File setup_github_secrets.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Ton.AI — GitHub Secrets Setup" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ─── Check gh CLI ──────────────────────────────────────
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "GitHub CLI (gh) ยังไม่ได้ติดตั้ง" -ForegroundColor Yellow
    Write-Host "กำลังติดตั้งผ่าน winget..." -ForegroundColor Yellow
    winget install --id GitHub.cli --silent --accept-source-agreements --accept-package-agreements
    Write-Host ""
    Write-Host "ติดตั้งเสร็จ — กรุณาปิด/เปิด PowerShell ใหม่ แล้วรัน script นี้อีกครั้ง" -ForegroundColor Green
    exit 0
}

Write-Host "✓ GitHub CLI พบแล้ว" -ForegroundColor Green

# ─── Check auth ────────────────────────────────────────
$authStatus = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ยังไม่ได้ login GitHub" -ForegroundColor Yellow
    Write-Host "กำลังเปิด browser ให้ login..." -ForegroundColor Yellow
    gh auth login --web --git-protocol https
}

Write-Host "✓ GitHub auth พร้อม" -ForegroundColor Green

# ─── Parse .env ────────────────────────────────────────
$envPath = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envPath)) {
    Write-Host "ไม่พบ .env file ที่: $envPath" -ForegroundColor Red
    exit 1
}

$envVars = @{}
Get-Content $envPath -Encoding UTF8 | ForEach-Object {
    if ($_ -match "^([A-Z_]+)=(.*)$") {
        $envVars[$matches[1]] = $matches[2]
    }
}

# ─── Secrets to push ───────────────────────────────────
$secrets = @(
    "GEMINI_API_KEY",
    "PEXELS_API_KEY",
    "FACEBOOK_PAGE_ID",
    "FACEBOOK_ACCESS_TOKEN",
    "FACEBOOK_PAGES",
    "LINE_CHANNEL_ACCESS_TOKEN",
    "TIKTOK_CLIENT_KEY",
    "TIKTOK_CLIENT_SECRET",
    "TIKTOK_ACCESS_TOKEN",
    "CONTENT_NICHE",
    "LINE_CONTENT_NICHE"
)

Write-Host ""
Write-Host "Pushing secrets to GitHub..." -ForegroundColor Cyan
Write-Host ""

$pushed = 0
$skipped = 0
foreach ($key in $secrets) {
    if ($envVars.ContainsKey($key) -and $envVars[$key]) {
        $value = $envVars[$key]
        try {
            $value | gh secret set $key 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  ✓ $key" -ForegroundColor Green
                $pushed++
            } else {
                Write-Host "  ✗ $key — failed" -ForegroundColor Red
            }
        } catch {
            Write-Host "  ✗ $key — error: $_" -ForegroundColor Red
        }
    } else {
        Write-Host "  - $key (ว่างใน .env)" -ForegroundColor DarkGray
        $skipped++
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  $pushed secrets pushed | $skipped skipped" -ForegroundColor White
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "ดู secrets ทั้งหมด: gh secret list" -ForegroundColor Yellow
Write-Host "ทดสอบรัน workflow: gh workflow run auto_post.yml" -ForegroundColor Yellow
Write-Host ""
