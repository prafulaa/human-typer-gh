<div align="center">
  <img src="logo.png" alt="Human Typer Logo" width="200">
  <h1 align="center">HUMAN Typer</h1>
  <p>
    
    A Python tool that types text into any active window (VMs, Citrix, Docs, etc.) simulating realistic human typing behavior.
  </p>
</div>

**Now with a GUI!**

---

## Features

- **Human-like Typing**: Random intervals, pauses after punctuation.
- **Realistic Typos**: Makes mistakes based on QWERTY adjacency, then backspaces and corrects them.
- **Cyberpunk GUI**: Dark mode, matrix green aesthetics, and sound effects (visual only).
- **Anti-Double Indent**: "Smart Mode" for pasting code into IDEs (VS Code, IntelliJ) to prevent staircase indentation.
- **Stop Hotkey**: Panic button (Default: `Ctrl+Q`) to stop typing instantly.

---

## Quick Start

### Windows 🪟
1.  **Install Python** (Ensure "Add to PATH" is checked).
3.  **Dependencies**: The script will automatically install required libraries (`pyautogui`, `customtkinter`, etc.) on the first run.
4.  Double-click **`run_gui.bat`** to start.

### macOS 🍎 / Linux 🐧
1.  Open Terminal.
2.  Run: `bash run_gui.sh`
    -   The script will automatically install required dependencies.
    -   *Note: On macOS, you must grant "Accessibility" permissions to Terminal/Python when prompts appear.*

---

## Installation (Manual)

If you prefer using the command line:

```bash
pip install customtkinter pyautogui keyboard Pillow
```

> **Linux users**: You might need: `sudo apt install python3-tk python3-xdotool xdotool`

---

## Usage

1.  **Launch the App**: `python human_typer_gui.py`
2.  **Paste Text**: Put your payload in the main window.
3.  **Configure**:
    -   **INJECTION_SPEED**: Words per minute.
    -   **HUMAN_ERROR_SIM**: Toggle realistic typos.
    -   **ANTI_DOUBLE_INDENT**: Check this if pasting into a code editor.
    -   **KILL_SWITCH**: Set your emergency stop hotkey (Default: `ctrl+q`).
4.  **EXECUTE**: Click the button, you have 5 seconds to switch to your target window.

---

## Troubleshooting

-   **macOS Permissions**: If it doesn't type, go to `System Settings > Privacy & Security > Accessibility` and ensure your Terminal or Python is allowed to control your computer.
-   **"Staircase" Text**: If pasting code results in weird indentation, check the **ANTI_DOUBLE_INDENT** box.

