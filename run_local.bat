@echo off
title FlexPave Local Runner
cd /d "%~dp0"

echo ==========================================
echo Starting FlexPave System
echo ==========================================

:: Detect Virtual Environment
set "VENV_PATH="
if exist ".venv\Scripts\activate.bat" (
    set "VENV_PATH=.venv"
) else if exist "venv\Scripts\activate.bat" (
    set "VENV_PATH=venv"
)

if "%VENV_PATH%"=="" (
    echo [WARNING] Python virtual environment not found (.venv or venv).
    echo Please make sure you have run backend setup steps.
    echo Attempting to run python backend globally...
    echo.
    start "FlexPave Backend" cmd /k "python -m mep_opt.web.main"
) else (
    echo Starting FastAPI Backend using %VENV_PATH%...
    start "FlexPave Backend" cmd /k "call %VENV_PATH%\Scripts\activate.bat && python -m mep_opt.web.main"
)

:: Check if node_modules exists in frontend
if not exist "frontend\node_modules" (
    echo [WARNING] frontend/node_modules not found.
    echo Running 'npm install' in frontend folder...
    echo.
    start "FlexPave Frontend" cmd /k "cd frontend && call npm install && npm run dev"
) else (
    echo Starting React/Vite Frontend Dev Server...
    start "FlexPave Frontend" cmd /k "cd frontend && npm run dev"
)

:: Wait a few seconds for servers to start, then open browser
echo.
echo Waiting 4 seconds for servers to initialize...
timeout /t 4 /nobreak >nul
echo Opening Cockpit Dashboard in browser...
start http://localhost:5173/

echo.
echo ===================================================
echo FlexPave is now running!
echo Backend API: http://127.0.0.1:8000
echo Frontend UI: http://localhost:5173
echo.
echo Keep the separate console windows open.
echo Close them to stop the servers.
echo ===================================================
echo.
pause
