@echo off
title Auto Poster Dashboard
echo Starting dashboard server...
set PYTHONPATH=C:\Users\ITM\AppData\Roaming\Python\Python313\site-packages
start /min "" C:\Python313\python.exe "F:\ProjectAI\auto_poster\dashboard_server.py"
timeout /t 2 /nobreak >nul
start "" "F:\ProjectAI\auto_poster\workflow_diagram.html"
echo Dashboard opened!
