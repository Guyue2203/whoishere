@echo off
echo Starting WhoIsHere Service in background...

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found
    pause
    exit /b 1
)

echo Service started. Check system tray for icon.
echo Access URL: http://localhost:51472

REM Run completely in background
pythonw main.py
