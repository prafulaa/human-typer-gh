@echo off
REM Human Typer Launcher
REM Uses %LocalAppData% to handle different usernames
REM Also falls back to system PATH

set PYTHON_PATH=%LocalAppData%\Programs\Python\Python314\python.exe

if exist "%PYTHON_PATH%" (
    echo Launching with Python 3.14...
    "%PYTHON_PATH%" -m pip install -r requirements.txt
    "%PYTHON_PATH%" human_typer_gui.py
) else (
    echo Python 3.14 not found in default location.
    echo Trying system PATH...
    python -m pip install -r requirements.txt
    python human_typer_gui.py
)

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Could not launch Human Typer.
    echo Please ensure Python is installed and added to PATH.
    pause
)
