@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" goto :missing_venv

"%PYTHON%" main.py
set "EXIT_CODE=%ERRORLEVEL%"
if "%EXIT_CODE%"=="0" exit /b 0

echo.
echo [ERROR] Application exited with code %EXIT_CODE%.
if not defined GESTURE_PPT_NO_PAUSE pause
exit /b %EXIT_CODE%

:missing_venv
echo [INFO] Project virtual environment was not found.
echo [INFO] Run: python -m venv .venv
echo [INFO] Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
if not defined GESTURE_PPT_NO_PAUSE pause
exit /b 1
