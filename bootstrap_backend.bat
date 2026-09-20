@echo off
chcp 65001 >nul
title 谱图分析服务配置

echo ================================================
echo  谱图智能分析系统 - 开机自启动配置
echo ================================================
echo.

REM 删除旧任务
schtasks /delete /tn "Spectral_BP_Backend" /f 2>nul
schtasks /delete /tn "Spectral_BP_Frontend" /f 2>nul

echo [1/2] 正在配置后端启动任务 (端口 8000)...
echo.

cd /d "C:\Users\zhangxuan7\spectral_analysis_system\backend"
python main.py > "C:\Users\zhangxuan7\spectral_analysis_system\backend\start.log" 2>&1 &
start "" "C:\Users\zhangxuan7\spectral_analysis_system\backend\start.log"
timeout /t 2 >nul
echo [配置完成] 后端启动脚本已创建
echo.

cd /d "C:\Users\zhangxuan7\spectral_analysis_system\frontend"
npm run dev -- --host 0.0.0.0 > "C:\Users\zhangxuan7\spectral_analysis_system\frontend\start.log" 2>&1 &
start "" "C:\Users\zhangxuan7\spectral_analysis_system\frontend\start.log"
timeout /t 2 >nul
echo [配置完成] 前端启动脚本已创建 && goto end

:schtasks
echo.
echo 使用 schtasks 任务的完全版 (如需开机真正自启动):
echo   schtasks /create /tn "Spectral_BP_Backend" /tr "cd C:\Users\zhangxuan7\spectral_analysis_system\backend ^&^& python main.py" /sc onstartu /ru LOCALSYSTEM
echo   schtasks /create /tn "Spectral_BP_Frontend" /tr "cd C:\Users\zhangxuan7\spectral_analysis_system\frontend ^&^& npm run dev" /sc onstartu /ru LOCALSYSTEM

:end
echo.
echo 访问地址:
echo   后端：http://localhost:8000
echo   前端：http://localhost:5173
echo.
pause
