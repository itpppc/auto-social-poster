@echo off
cd /d "F:\ProjectAI\auto_poster"
set PYTHONPATH=C:\Users\ITM\AppData\Roaming\Python\Python313\site-packages
set PYTHONUTF8=1
C:\Python313\python.exe -X utf8 main.py --now 2>> task_error.log
exit /b 0
