@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo   Starting Job Automation Agent (Backend + Frontend)
echo ===================================================

echo [1/2] Starting Backend FastAPI Server on Port 8000...
start "Job Agent Backend (Port 8000)" /D "%~dp0backend" cmd /k "venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/2] Starting Frontend Vite Server on Port 5173...
start "Job Agent Frontend (Port 5173)" /D "%~dp0frontend" cmd /k "npm run dev"

echo.
echo ===================================================
echo   Both servers launched!
echo ===================================================
ping 127.0.0.1 -n 3 >nul
start http://localhost:5173
