@echo off
REM ============================================================
REM  GreenwashGuard - Startup Script for Windows
REM  Function: Check environment + start services
REM ============================================================

chcp 65001 >nul
title GreenwashGuard System

echo.
echo  ==========================================================
echo    GreenwashGuard - Corporate Greenwashing Detection System
echo  ==========================================================
echo.

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

REM ------------------------------------------------------------
REM  Check Python
REM ------------------------------------------------------------
echo  [Check] Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo         [ERROR] Python not found. Please install Python 3.10+
    echo         Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo         [OK] Python found

REM ------------------------------------------------------------
REM  Check Node.js
REM ------------------------------------------------------------
echo  [Check] Node.js...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo         [ERROR] Node.js not found. Please install Node.js 18+
    echo         Download: https://nodejs.org/
    pause
    exit /b 1
)
echo         [OK] Node.js found

REM ------------------------------------------------------------
REM  Quick check backend packages (no network call)
REM  We just check if fastapi import works, not via pip show
REM ------------------------------------------------------------
echo.
echo  [Backend] Quick package check (import test)...
cd /d "%ROOT_DIR%backend"
python -c "import fastapi; print('fastapi OK')" >nul 2>&1
if %errorlevel% neq 0 (
    echo         [WARNING] fastapi not importable, please run manually:
    echo                  cd backend ^&^& pip install -r requirements.txt
    echo         Continue anyway in 3 seconds...
    timeout /t 3 /nobreak >nul
) else (
    echo         [OK] Backend packages importable
)

REM ------------------------------------------------------------
REM  Quick check frontend node_modules
REM ------------------------------------------------------------
echo  [Frontend] Checking Node modules...
cd /d "%ROOT_DIR%frontend"
if not exist "node_modules" (
    echo         [WARNING] node_modules missing, please run manually:
    echo                  cd frontend ^&^& npm install
    echo         Continue anyway in 3 seconds...
    timeout /t 3 /nobreak >nul
) else (
    echo         [OK] Frontend modules exist
)

cd /d "%ROOT_DIR%"

REM ------------------------------------------------------------
REM  Start services
REM ------------------------------------------------------------
echo.
echo  ==========================================================
echo    Starting services...
echo  ==========================================================
echo.
echo  [1/2] Starting Backend API server (port 8000)...
start "GreenwashGuard-Backend" /d "%ROOT_DIR%backend" cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo  [2/2] Starting Frontend dev server (port 5173)...
start "GreenwashGuard-Frontend" /d "%ROOT_DIR%frontend" cmd /k "npx vite --host"

echo.
echo  Waiting for services to start (8 seconds)...
timeout /t 8 /nobreak >nul

echo.
echo  ==========================================================
echo    [OK] System started!
echo.
echo    Frontend:  http://localhost:5173
echo    API Docs:  http://localhost:8000/docs
echo    Health:    http://localhost:8000/health
echo  ==========================================================
echo.
echo  If you see errors in the opened windows, please:
echo    1) Check that all Python packages are installed
echo    2) Check that all npm packages are installed
echo.
echo  Press any key to STOP all services and close...
pause >nul

echo.
echo  Stopping services...
taskkill /FI "WINDOWTITLE eq GreenwashGuard-*" /T /F >nul 2>&1
echo  [OK] All services stopped
