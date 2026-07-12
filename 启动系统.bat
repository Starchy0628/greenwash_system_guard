@echo off
REM ============================================================
REM  谛观 GreenwashGuard — 一键启动脚本
REM  功能：同时启动后端 FastAPI 和前端 Vite 开发服务器
REM ============================================================

chcp 65001 >nul
title 谛观 GreenwashGuard — 一键启动

echo.
echo  ==========================================================
echo    🌿 谛观 GreenwashGuard
echo    企业漂绿风险监测系统
echo  ==========================================================
echo.
echo  [启动后端] FastAPI — http://localhost:8000
echo  [启动前端] Vue 3 — http://localhost:5173
echo.

cd /d "%~dp0"

echo  [1/2] 启动后端 API 服务...
start "GreenwashGuard-Backend" cmd /k "cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo         后端已启动 (端口 8000)

echo  [2/2] 启动前端开发服务器...
start "GreenwashGuard-Frontend" cmd /k "cd frontend && npx vite --host"
echo         前端已启动 (端口 5173)

echo.
echo  ==========================================================
echo    ✅ 系统启动完成！
echo    请在浏览器打开: http://localhost:5173
echo    后端 API 文档: http://localhost:8000/docs
echo  ==========================================================
echo.
echo  按任意键停止所有服务...
pause >nul

taskkill /FI "WINDOWTITLE eq GreenwashGuard-*" /T /F >nul 2>&1
echo  已停止所有服务
