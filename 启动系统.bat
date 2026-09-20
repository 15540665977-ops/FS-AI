@echo off
chcp 65001 >nul
color 0A
title 谱图智能分析系统

echo ================================================
echo     谱图智能分析系统 - 启动中...
echo ================================================
echo.

REM 直接用 PowerShell ExecutionPolicy Bypass 运行启动脚本，无需管理员权限
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_services.ps1"

echo.
echo [完成] 服务已在后台启动
echo   后端 API：http://localhost:8000
echo   前端界面：http://localhost:5173
echo   局域网访问：http://本机IPv4地址:5173
echo.
echo 浏览器将在 8 秒后自动打开...
timeout /t 8 >nul
start "" "http://localhost:5173"
