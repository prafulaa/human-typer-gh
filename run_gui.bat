@echo off
REM Human Typer Launcher
REM Uses %LocalAppData% to handle different usernames
REM Also falls back to system PATH

set PYTHON_PATH=%LocalAppData%\Programs\Python\Python314\python.exe

if exist "%PYTHON_PATH%" (
    set PY=%PYTHON_PATH%
) else (
    set PY=python
)

REM Only install dependencies if they are actually missing (fast start)
"%PY%" -c "import customtkinter, pyautogui, PIL" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    "%PY%" -m pip install -r requirements.txt
)

"%PY%" human_typer_gui.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Could not launch Human Typer.
    echo Please ensure Python is installed and added to PATH.
    pause
)
