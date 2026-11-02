# AGENTS.md

## What this is

**Human Typer** — a Python desktop app (Windows/macOS/Linux) that types text into whatever window has focus, simulating human typing (random delays, QWERTY-adjacent typos that get backspaced and corrected). Used to enter text into environments where clipboard paste is blocked (VMs, Citrix). GUI is CustomTkinter; typing goes through pyautogui, plus a native `SendInput(KEYEVENTF_UNICODE)` path for non-ASCII on Windows (pyautogui alone can only type ASCII on every platform).

## Layout

- `human_typer.py` — CLI + core typing engine (no GUI). `type_text()` is the engine; the GUI imports it. Also `ADJACENT_KEYS` (QWERTY map), `_type_unicode_windows()` (SendInput), `scan_untypeable()`, `_wait_if_paused()`/`_sleep_interruptible()`. Single source of truth for `__version__`.
- `human_typer_gui.py` — CustomTkinter app (`HumanTyperApp`) + `SettingsDialog`. Runs `type_text()` in a daemon thread with `stop_event`/`pause_event`/`progress_callback`. Design tokens (`COLOR_*`, `ACCENTS`, `CORNER_STYLES`) and settings persistence live here.
- `ui_kit.py` — UI-only kit: PIL-drawn icons (`ctk_icon`), after()-based color/numeric tweens, `HoverButton` (animated hover/press), `Tooltip`. No typing logic, no pyautogui.
- `HumanTyper.spec` — PyInstaller spec (one-file exe on Windows, .app bundle on macOS). Reads the version from `human_typer.py` by regex. **Is tracked on purpose** (the gitignore has an explicit `!HumanTyper.spec` exception — don't remove it).
- `tests/test_engine.py`, `tests/test_gui.py` — stub-based suites (no real keystrokes). Engine suite is CI-safe on all 3 OSes; GUI suite needs a display.
- `create_icon.py` — regenerates `human_typer_icon.icns`/`.ico`.
- `run_gui.bat` / `run_gui.sh` — user launchers (install deps only if missing).
- `build_mac.sh` — macOS PyInstaller build + optional .dmg (`CREATE_DMG=1` for non-interactive).
- `docs/screenshots/` — current light/dark UI screenshots used by the README.
- `QA_REPORT.md`, `CHANGELOG.md` — the 2026-10 audit and the releases built on it.

## Commands

- Run the app: `python human_typer_gui.py` (deps: `pip install -r requirements.txt`)
- Lint: `python -m pyflakes human_typer.py human_typer_gui.py create_icon.py`
- Engine tests (stubbed, no keystrokes): `python tests/test_engine.py`
- GUI tests (stubbed engine, needs a display, still zero keystrokes): `python tests/test_gui.py`
- CLI engine only: `python human_typer.py -f file.txt --wpm 60`
- Windows build: `pyinstaller HumanTyper.spec --noconfirm`
- macOS build: `bash build_mac.sh` (needs macOS; produces `dist/Human Typer.app`)

There is no formal test framework (no pytest); the suites are plain scripts with exit codes. Any test run that reaches the real engine injects real keystrokes into whatever window is focused — the suites avoid this by stubbing pyautogui before import; keep it that way when adding tests.

CI: `.github/workflows/ci.yml` runs compile + pyflakes + engine tests on ubuntu/windows/macos × py3.10/3.13 on every push to main. `.github/workflows/macos_release.yml` builds a .app on `v*` tags (signing/notarization steps only activate when secrets like `MAC_CERT_P12_BASE64` are configured).

## Architecture rules

- Keep the engine/GUI split: typing behavior, timing, and key sending live in `human_typer.py`; anything touching widgets lives in `human_typer_gui.py`.
- `type_text()` contract: returns `{"typed", "skipped", "skipped_chars"}`; accepts `stop_event`, `pause_event`, `progress_callback(done, total)`, `suppress_indent`, `verbose`. Typos are generated only for ASCII letters (guarantees every "wrong" keystroke is typeable so backspace counts always balance).
- The typing thread must never touch widgets directly — always `self.ui(fn)` (guarded `after(0, fn)`), and `run_typing()` must keep its try/except/finally so START always re-enables after any error.
- Version lives only in `human_typer.__version__`; GUI title/footer and the spec read it from there.

## macOS compatibility constraints (hard-won — see git log)

- `ctk.set_appearance_mode()` / `set_default_color_theme()` must stay at **module level**, before any CTk window is created (otherwise black window). Changing the mode later (theme toggle, loaded settings) is safe.
- **No emoji or exotic Unicode in any UI string** — Tk 8.6 + CoreText crashes on macOS Sonoma. ASCII only. CLI stdout emojis are fine (they go through `_safe_print`).
- Fonts must stay platform-gated: SF Pro Display / Menlo on macOS, Segoe UI / Consolas elsewhere. Do not introduce Roboto or other fonts not guaranteed present.
- Window icon: `.iconbitmap(...ico)` only on non-macOS, via `resource_path()` (handles `sys._MEIPASS` in the frozen build).
- **Global hotkeys are Windows-only, full stop.** Since v2.3.0 they exist again via the `keyboard` lib (imported behind `if IS_WINDOWS:`; the requirement is `keyboard; sys_platform == "win32"`), because the macOS global hook crash (commit cf3f236) is real and `keyboard` needs root on Linux. Never enable them on macOS, and never accept a combo without ctrl or alt (`normalize_combo` enforces this) — otherwise the hook can swallow the user's plain typing. The engine/GUI must keep working with hotkeys absent (all non-Windows platforms).

## UI conventions

- Colors are always (light, dark) tuples from the `COLOR_*`/`ACCENTS` tokens; never hardcode colors in widgets. Accent-recolored widgets must be registered (`_reg_accent_btn` / `_reg_accent_fg` / `_reg_accent_prog`) and corner-shaped ones via `_register_corners(w, kind)` so Settings changes restyle everything.
- Icons come from `ui_kit.ctk_icon(name, light_hex, dark_hex, px)` — PIL-drawn, never emoji (emoji crash CoreText on macOS Sonoma + Tk 8.6). ASCII-only UI strings.
- Animations are after()-based tweens from `ui_kit` (CTk has none native). Long-running tweens must be cancelable (see `_bar_to` / dot-pulse pattern).
- **CustomTkinter 6.0 gotchas learned the hard way:** `configure(border_color=None)` raises `ValueError` (toggle `border_width` instead); `grab_set()` on a not-yet-viewable `CTkToplevel` raises `TclError` (delay the grab ~250 ms); don't build tooltips from `CTkToplevel` (its withdraw/deiconify titlebar dance explodes on quick destroy — `ui_kit.Tooltip` uses plain `tk.Toplevel`); `CTkTextbox` has no `placeholder_text` (manual placeholder with `<Key>`/`<<Paste>>`/`<FocusIn>` clearing).

## Conventions

- Speed limits live in `human_typer` (`MIN_WPM`/`MAX_WPM`/`FAST_MODE_WPM`); the GUI slider reads them — don't hardcode ranges. Above `FAST_MODE_WPM` (180) the engine switches to steady fast-mode cadence, and fixed correction pauses scale by `correction_pause_scale`.

- `pyautogui.PAUSE = 0` (engine assumes it); keep delays explicit. `pyautogui.FAILSAFE` stays **enabled** — callers catch `pyautogui.FailSafeException` and report "Aborted (mouse corner)".
- Long engine sleeps must use `_sleep_interruptible()` (STOP honored within ~50 ms) — never a bare multi-second `time.sleep()`.
- Text is CRLF-normalized (`\r\n`/`\r` → `\n`) inside `type_text()`; don't pre-normalize elsewhere.
- Settings persist to `%APPDATA%/HumanTyper/settings.json` (or platform equivalent); write it via `_save_settings()` only.
