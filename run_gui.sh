#!/bin/bash
# Human Typer Launcher (macOS/Linux)

# Ensure dependencies are installed
echo "Checking dependencies..."
python3 -m pip install -r requirements.txt --break-system-packages 2>/dev/null || python3 -m pip install -r requirements.txt

# macOS: Remind about Accessibility permissions
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo ""
    echo "⚠️  macOS: Make sure you've granted Accessibility access!"
    echo "   System Settings > Privacy & Security > Accessibility"
    echo "   Add 'Terminal' (or your terminal app) to the list."
    echo ""
fi

echo "Initializing Human Typer..."
python3 human_typer_gui.py
