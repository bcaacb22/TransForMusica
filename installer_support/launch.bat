@echo off
cd /d "%~dp0backend"
set FPCALC=%~dp0backend\fpcalc.exe
start "" /B "%~dp0venv\Scripts\python.exe" run_app.py
timeout /t 3 /nobreak >nul
start http://localhost:8001
