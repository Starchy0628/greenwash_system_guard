@echo off
REM ============================================================
REM  谛观 GreenwashGuard — 一键启动脚本
REM  功能：检查环境 + 安装依赖 + 启动后端和前端服务
REM ============================================================

chcp 65001 >nul
title 谛观 GreenwashGuard — 一键启动

echo.
echo  ==========================================================
echo    🌿 谛观 GreenwashGuard
echo    企业漂绿风险监测系统
echo  ==========================================================
echo.

cd /d "%~dp0"

REM ------------------------------------------------------------
REM  检查 Python
REM ------------------------------------------------------------
echo  [检查环境] Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo         ❌ 未找到 Python，请先安装 Python 3.10+
    echo         下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo         ✅ Python 已安装

REM ------------------------------------------------------------
REM  检查 Node.js
REM ------------------------------------------------------------
echo  [检查环境] Node.js...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo         ❌ 未找到 Node.js，请先安装 Node.js 18+
    echo         下载地址: https://nodejs.org/
    pause
    exit /b 1
)
echo         ✅ Node.js 已安装

REM ------------------------------------------------------------
REM  检查并安装后端依赖
REM ------------------------------------------------------------
echo.
echo  [后端依赖] 检查 Python 包...
cd backend
pip show fastapi >nul 2>&1
if %errorlevel% neq 0 (
    echo         正在安装后端依赖...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo         ❌ 后端依赖安装失败
        cd ..
        pause
        exit /b 1
    )
) else (
    echo         ✅ 后端依赖已安装
)
cd ..

REM ------------------------------------------------------------
REM  检查并安装前端依赖
REM ------------------------------------------------------------
echo  [前端依赖] 检查 Node 模块...
cd frontend
if not exist "node_modules" (
    echo         正在安装前端依赖...
    call npm install
    if %errorlevel% neq 0 (
        echo         ❌ 前端依赖安装失败
        cd ..
        pause
        exit /b 1
    )
) else (
    echo         ✅ 前端依赖已安装
)
cd ..

REM ------------------------------------------------------------
REM  启动服务
REM ------------------------------------------------------------
echo.
echo  ==========================================================
echo    正在启动服务...
echo  ==========================================================
echo.
echo  [1/2] 启动后端 API 服务 (端口 8000)...
start "GreenwashGuard-Backend" cmd /k "cd /d "%~dp0backend" && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo  [2/2] 启动前端开发服务器 (端口 5173)...
start "GreenwashGuard-Frontend" cmd /k "cd /d "%~dp0frontend" && npx vite --host"

echo.
echo  等待服务启动...
timeout /t 3 /nobreak >nul

echo.
echo  ==========================================================
echo    ✅ 系统启动完成！
echo.
echo    🌐 前端页面: http://localhost:5173
echo    📚 API 文档: http://localhost:8000/docs
echo    ❤️  健康检查: http://localhost:8000/health
echo  ==========================================================
echo.
echo  提示: 请等待几秒钟让服务完全启动
echo  提示: 关闭此窗口可停止所有服务
echo.

REM 等待用户按键，然后清理
pause >nul

echo.
echo  正在停止服务...
taskkill /FI "WINDOWTITLE eq GreenwashGuard-*" /T /F >nul 2>&1
echo  ✅ 已停止所有服务