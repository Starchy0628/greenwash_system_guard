@echo off
REM ============================================================
REM  GreenwashGuard - Developer Debug Startup (with console)
REM  开发者调试启动（显示控制台窗口，可查看日志输出）
REM  普通用户请双击：启动系统.vbs（静默无窗口）
REM ============================================================

chcp 65001 >nul
title GreenwashGuard - Developer Mode

echo.
echo  ==========================================================
echo    GreenwashGuard - Developer Debug Mode
echo    (For normal use, please double-click: 启动系统.vbs)
echo  ==========================================================
echo.

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

REM Check Python
echo  [Check] Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo         [ERROR] Python not found. Please install Python 3.10+
    echo         Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo         [OK] Python found

REM Check .env
if not exist "backend\.env" (
    echo  [Config] Creating .env from .env.example...
    copy "backend\.env.example" "backend\.env" >nul
)

REM Check dependencies
echo.
echo  [Check] Python dependencies...
python -c "import fastapi" >nul 2>&1
if %errorlevel% neq 0 (
    echo         Installing dependencies...
    cd /d "%ROOT_DIR%backend"
    pip install -r requirements.txt
    cd /d "%ROOT_DIR%"
)
echo         [OK] Dependencies ready

echo.
echo  ==========================================================
echo    Starting server at http://localhost:8000
echo    Press Ctrl+C to stop
echo  ==========================================================
echo.

cd /d "%ROOT_DIR%backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
