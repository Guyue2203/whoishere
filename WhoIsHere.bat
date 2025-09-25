@echo off
echo Starting Remote Desktop Monitor Service...

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found at .venv\Scripts\activate.bat
    echo Please ensure virtual environment is created
    pause
    exit /b 1
)

echo Access URL: http://localhost:51472
echo Service will continue running in system tray after closing CMD window
echo Right-click tray icon to view status or exit service
echo.

start "WhoIsHere Service" python main.py
