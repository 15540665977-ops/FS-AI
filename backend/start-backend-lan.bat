@echo off
setlocal

set "BACKEND_DIR=%~dp0"
cd /d "%BACKEND_DIR%"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Python virtual environment was not found.
  echo Run the installation steps in README.md first.
  pause
  exit /b 1
)

if not exist ".env" (
  echo [ERROR] backend\.env was not found.
  echo Copy .env.example to .env and configure ANTHROPIC_API_KEY before starting analysis.
  pause
  exit /b 1
)

if "%SPECTRAL_PORT%"=="" set "SPECTRAL_PORT=8000"
echo Starting backend on all network interfaces: http://0.0.0.0:%SPECTRAL_PORT%
".venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port %SPECTRAL_PORT%
