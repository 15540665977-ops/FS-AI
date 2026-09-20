@echo off
chcp 65001 >nul
title 谱图系统 - 配置开机自启

echo ================================================
echo  谱图智能分析系统 - 配置开机自启（无需管理员）
echo ================================================
echo.
echo 方法：将启动脚本放入用户启动文件夹
echo 路径：%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
echo.

REM 创建启动文件夹中的快捷方式 VBScript
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SCRIPT=%~dp0启动系统.bat"
set "SHORTCUT=%STARTUP%\谱图智能分析系统.lnk"
set "VBS=%TEMP%\create_spectral_shortcut.vbs"

echo Set oWS = WScript.CreateObject("WScript.Shell") > "%VBS%"
echo sLinkFile = "%SHORTCUT%" >> "%VBS%"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%VBS%"
echo oLink.TargetPath = "%SCRIPT%" >> "%VBS%"
echo oLink.WorkingDirectory = "%~dp0" >> "%VBS%"
echo oLink.Description = "谱图智能分析系统自启动" >> "%VBS%"
echo oLink.WindowStyle = 7 >> "%VBS%"
echo oLink.Save >> "%VBS%"

cscript //nologo "%VBS%"
del "%VBS%"

if exist "%SHORTCUT%" (
    echo.
    echo [成功] 开机自启已配置！
    echo   快捷方式位置：%SHORTCUT%
    echo.
    echo 系统重启后将自动启动谱图分析服务。
) else (
    echo.
    echo [失败] 快捷方式创建失败，请手动将"启动系统.bat"
    echo   复制到：%STARTUP%
)

echo.
pause
