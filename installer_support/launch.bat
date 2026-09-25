@echo off
cd /d "%~dp0..\backend"
set FPCALC=%~dp0..\backend\fpcalc.exe
start "" /B "%~dp0..\backend\.venv\Scripts\python.exe" run_app.py
timeout /t 3 /nobreak >nul
start http://localhost:8001
