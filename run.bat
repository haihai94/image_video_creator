@echo off
echo ========================================
echo   Image to Video Creator - Launcher
echo ========================================
echo.

cd /d "%~dp0"

REM Check if venv exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate venv
call .venv\Scripts\activate.bat

REM Install dependencies
echo Checking dependencies...
pip install -r requirements.txt -q

REM Run app
echo Starting Image to Video Creator...
python main.py

pause
