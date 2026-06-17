@echo off
title Ton.AI Service Control
color 0B

:menu
cls
echo.
echo  =========================================
echo    Ton.AI Auto Poster -- Service Control
echo  =========================================
echo.

REM Check if running
tasklist /FI "IMAGENAME eq python.exe" 2>nul | find /I "python.exe" >nul
if %ERRORLEVEL%==0 (
    echo  Status: [RUNNING]
) else (
    echo  Status: [STOPPED]
)

echo.
echo  [1] Start Service
echo  [2] Stop Service
echo  [3] Restart Service
echo  [4] View Live Log  (Ctrl+C to exit)
echo  [5] Open Dashboard (browser)
echo  [0] Exit
echo.
set /p choice="  Select: "

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto restart
if "%choice%"=="4" goto log
if "%choice%"=="5" goto dashboard
if "%choice%"=="0" exit
goto menu

:start
echo.
echo  Starting service...
start /min "" "F:\ProjectAI\auto_poster\venv\Scripts\python.exe" "F:\ProjectAI\auto_poster\run_service.py"
timeout /t 3 /nobreak >nul
echo  Done!
echo.
pause
goto menu

:stop
echo.
echo  Stopping all Python processes...
taskkill /F /IM python.exe /T >nul 2>&1
echo  Stopped.
echo.
pause
goto menu

:restart
echo.
echo  Restarting service...
taskkill /F /IM python.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul
start /min "" "F:\ProjectAI\auto_poster\venv\Scripts\python.exe" "F:\ProjectAI\auto_poster\run_service.py"
timeout /t 3 /nobreak >nul
echo  Restarted!
echo.
pause
goto menu

:log
echo.
echo  === Live Log (Ctrl+C to return) ===
echo.
powershell -NoProfile -Command "Get-Content 'F:\ProjectAI\auto_poster\service.log' -Wait -Tail 30"
goto menu

:dashboard
start "" "http://localhost:5001"
goto menu
