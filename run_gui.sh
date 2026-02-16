#!/bin/bash
# Human Typer Launcher (macOS/Linux)

# Ensure dependencies are installed
echo "Checking dependencies..."
python3 -m pip install -r requirements.txt

echo "Initializing Human Typer..."
python3 human_typer_gui.py
