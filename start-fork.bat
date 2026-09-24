@echo off
REM === Transformusic FORK — start both servers (detached, survive session exit) ===
REM Backend on 8001, frontend on 3201. Your original app on 8000/3200 is unaffected.

set ROOT=%~dp0

REM --- Backend (port 8001) ---
set RUN_PORT=8001
start "" /B "%ROOT%backend\.venv\Scripts\python.exe" run_app.py ^
  > "%ROOT%backend\server_out.log" 2> "%ROOT%backend\server_err.log"

REM --- Frontend (port 3201) ---
cd /d "%ROOT%frontend"
start "" /B cmd /c "npx vite --port 3201 > "%ROOT%frontend\vite_out.log" 2>&1"

echo Fork starting...
echo   Backend  : http://localhost:8001  (docs at /docs)
echo   Frontend : http://localhost:3201
echo.
echo Logs: backend\server_err.log  and  frontend\vite_out.log
echo Give it ~10 seconds, then open http://localhost:3201
