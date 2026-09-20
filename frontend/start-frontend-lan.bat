@echo off
setlocal

set "FRONTEND_DIR=%~dp0"
cd /d "%FRONTEND_DIR%"

if not exist "node_modules" (
  echo [ERROR] Frontend dependencies were not found.
  echo Run npm ci in this directory first.
  pause
  exit /b 1
)

if "%VITE_PORT%"=="" set "VITE_PORT=5173"
echo Starting frontend for local network access on port %VITE_PORT%...
call npm run dev:lan
