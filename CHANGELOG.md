# Changelog

All notable changes to Human Typer are documented here.

## [2.3.0] — 2026-11-02

Design restored to the original card-based look (upgraded), configurable
global hotkeys, human typing profiles, and a merge of the parallel
multi-machine update (WPM 700, fast mode).

### Restored design (user feedback on the 2.2 layout)

- STATUS / TARGET cards are back side by side, the full-width hero
  START SESSION button is back (PAUSE/STOP appear only while running),
  sliders carry icons and value chips, and the whole window now **fits the
  screen on any DPI**: sizes are planned in logical units and scaled by
  CTk's scale factor (fixes the "goes fullscreen at 125% scaling / after
  theme toggle" bug).
- Icon+text labels use `compound="left"` — icons no longer render on top
  of the label text.

### Configurable hotkeys (Windows)

- Settings dialog gains a **Hotkeys** section: bind a Start combo and a
  Panic-Stop combo (default `ctrl+q`, matching the classic kill switch).
  Combos must include ctrl or alt (a global hook can never swallow plain
  typing) and the stop combo is suppressed from the target app.
- Windows-only by design: global keyboard hooks crash macOS (commit
  cf3f236) and need root on Linux; there the in-app PAUSE/STOP buttons
  remain the controls. A `Stop: ctrl+q` chip in the main window opens the
  bindings.
- Robust combo normalization (`ctrl+q`, `q+ctrl`, `ctrl+shift+f5` all
  validate; bare keys rejected), capture widget with live recording, and
  sensible fallback to `ctrl+q` on legacy/invalid settings.

### More human typing (engine)

- **Typing profiles**: Chill / Natural / Focused / Surgeon — scale typo
  rate, hesitation pauses, and WPM drift. Profiles change *only* timing;
  output stays byte-exact (covered by tests for all four profiles).
- WPM drift (slow random walk ±), word-start bursts, word stutters,
  pre-long-word hesitations, and paragraph-break thinking pauses.

### Merged from the parallel machine (Human Typer Project.zip)

- **WPM up to 700** (`MIN_WPM`/`MAX_WPM`/`FAST_MODE_WPM` shared by CLI
  and GUI slider, 5-WPM steps).
- **Fast mode**: above 180 WPM the cadence is steady 0.85–1.15 jitter —
  punctuation "thinking" pauses would otherwise dominate and make the
  displayed WPM fiction.
- **Correction-pause scaling**: typo "noticing"/post-correction pauses
  shrink toward zero as WPM rises, so high speeds are actually fast.
- **Atomic settings writes** (write `.tmp`, then `os.replace`) and strict
  settings-load validation with defaults.

### Fixed

- `normalize_combo` dropped letter keys when building the canonical combo
  (`ctrl+q` came out as `ctrl`) and mis-detected the modifier position.
- Fresh installs showed "Stop: off" — the hotkey default now applies on
  load, not only on save.
- Test-side: `CTkSlider` exposes its lower bound as `_from_` (not `cget
  ("from")`).

Tests: engine 21/21, GUI 22/22 (now covering screen-fit after theme
toggles, hotkey normalization/registration/panic, slider range, profile
plumbing).

## [2.2.0] — 2026-10-05

UI overhaul: customizable appearance, a real settings dialog, animations,
and a new icon set — with CustomTkinter community best practices applied
(light/dark tuples, after()-based tweening, segmented controls).

### Appearance customization (all live, all persisted)

- **5 accent colors** — Lime, Sky, Amber, Rose, Violet — applied across
  buttons, sliders, progress, switches, and the header badge.
- **3 corner styles** — Sharp / Soft / Round — reshape cards, the input,
  buttons, and chips app-wide.
- Light/Dark themes as before, now switchable from the Settings dialog too.

### New settings format

- The cramped hidden "Settings" row is now a proper **modal dialog** with
  sections: Appearance (theme / accent / corners), Typing (start delay:
  3/5/10 s — previously hardcoded 5 s), and Reset defaults / Done.
- Anti-Double Indent moved to a visible **Smart Mode switch** in the main
  window (it is a per-session toggle).

### Animations & polish

- Eased **hover/press color tweens** on the action buttons (new `HoverButton`).
- **Smooth tweened progress bar** for countdown and typing progress, plus a
  live percent readout.
- **Pulsing live dot** while a session is running (solid accent when done).
- Subtle **window fade-in** on launch (skipped silently where unsupported).
- **Crisp PIL-drawn icons** (play/pause/stop/gear/sun/moon/leaf/doc) at 4x
  supersampling — no emoji glyphs, HiDPI-safe, macOS-safe.
- **Tooltips** on every control (dependency-free implementation).
- Layout redesigned: status strip with live dot + percent inside the input
  card, value chips on sliders, version chip in the header.

### New module

- `ui_kit.py` — icons, color/easing tween helpers, `HoverButton`,
  `Tooltip`. UI-only; no typing logic.

### Fixed along the way (found by the test suite)

- `CTk` rejects `border_color=None` — swatch refresh now toggles width only.
- `grab_set()` on a not-yet-viewable `CTkToplevel` raises `TclError` — the
  dialog grabs after a short delay, guarded.
- Tooltips use plain `tk.Toplevel` (CTkToplevel's internal
  withdraw/deiconify titlebar dance breaks noisily on quick destroy).

Tests extended to 16 GUI checks (settings dialog, accent + corner
persistence) and CI now lints `ui_kit.py`.

## [2.1.0] — 2026-10-05

Full audit-driven release: every Critical and High finding from [QA_REPORT.md](QA_REPORT.md)
is fixed, plus most Medium and Low findings.

### Critical fixes

- **Build spec committed** — `HumanTyper.spec` was matched by the `*.spec`
  gitignore rule and never reached the repository, so the macOS release build
  could never succeed and the Windows exe was not reproducible. The ignore
  rule is now scoped so the spec is tracked.
- **Unicode typing on Windows** — pyautogui silently drops every non-ASCII
  character (its key maps are ASCII-only on all platforms), which silently
  corrupted non-English text. The engine now types any codepoint (accents,
  Devanagari, CJK, emoji) natively via `SendInput(KEYEVENTF_UNICODE)`. On
  macOS/Linux, untypeable characters are reported up front (GUI warning) and
  counted in the completion status instead of vanishing silently.
- **Typing thread is now exception-safe** — any error mid-session (pyautogui
  failsafe, missing Accessibility permission, engine bug) previously killed
  the worker thread and left the UI stuck on "RUNNING…" forever. `run_typing`
  now uses try/except/finally: the START button always comes back and the
  status explains what happened ("Aborted (mouse corner)", "Error - see
  console" with a traceback printed for diagnosis).

### High fixes

- **Placeholder no longer typed** — leaving "Paste your text here..." in the
  box (with text appended after it) used to send the placeholder to the
  target window. The placeholder now clears on first keypress/paste/focus,
  and an untouched placeholder is rejected as empty input.
- **CI overhauled** — deleted the leftover `django.yml` (red X on every
  push: no `manage.py` exists) and `python-publish.yml` (no Python package
  exists). Added `ci.yml`: compile check, pyflakes, and the stubbed engine
  test suite on Ubuntu/Windows/macOS × Python 3.10/3.13. Also included CLI
  argument-validation checks.
- **macOS release workflow rewritten** — the old job used the retired
  `xcrun altool`, an ambiguous signing identity, and App Store entitlements
  that are incompatible with an Accessibility-requiring typing app. It now
  builds and uploads a .app artifact, with optional Developer ID signing +
  `notarytool` notarization that activates only when secrets are configured.

### New features

- **Pause / Resume** — suspend a session mid-typing and continue exactly
  where it left off (new PAUSE button; engine `pause_event`).
- **Live progress** — status card shows "Injecting... N%" with a progress
  bar driven by an engine `progress_callback`; the countdown bar now fills
  to 100%.
- **Session stats** — word/character count and estimated duration update as
  you type; a SESSION card shows the payload size.
- **Settings persistence** — theme, speed, variation, and anti-double-indent
  are saved to a local JSON file and restored on launch.
- **Stop latency** — long "natural break" pauses are now interruptible;
  STOP/cancel is honored within ~50 ms instead of up to 3 s.
- **CRLF handling** — `\r\n` and lone `\r` are normalized to `\n` before
  typing (previously produced double newlines or dropped lines).
- **Pre-flight character scan** — `scan_untypeable()` tells you exactly
  which characters cannot be typed on the current platform before you start.

### Improvements

- Window close during a session now stops the thread cleanly (no Tk
  "main thread is not in main loop" errors, no stuck modifier keys). The
  close handler pumps the event loop while joining to avoid a shutdown
  deadlock.
- Window icon loads from `sys._MEIPASS` in the frozen build — the packaged
  exe finally shows its icon.
- Version is single-sourced from `human_typer.__version__` (GUI title,
  footer, and the PyInstaller spec's `CFBundleShortVersionString` read it).
- CLI arguments are validated (`--wpm` 1–500, `--error-rate` 0.0–1.0) with
  clear errors instead of `ZeroDivisionError` or garbage behavior; missing
  input files and Ctrl+C/failsafe aborts produce friendly messages.
- Dead code removed throughout (unused `keyboard`/`pynput`/`platform`
  imports and their misleading startup warning, unused variables in
  `create_icon.py`, placeholder-less f-strings, scratch comments in the
  anti-indent logic).
- `keyboard` and `pynput` dropped from `requirements.txt`; launchers now
  install dependencies only when missing (fast start).
- `build_mac.sh` supports non-interactive DMG creation (`CREATE_DMG=1`).
- Hover colors adapt per theme (tuples instead of light-only colors).
- README rewritten to match reality (features, controls, platform
  limitations, responsible-use section, development instructions);
  screenshots included. Privacy policy covers macOS and the local settings
  file.
- LICENSE (MIT) and `.gitattributes` (LF for `.sh`/`.py`, CRLF for `.bat`)
  added; `.msix`/`.exe` artifacts ignored to keep binaries out of history.
- Test suite added (`tests/`): 14 engine tests + 13 GUI tests, fully
  stubbed — no real keystrokes, CI-safe.

## [2.0.0] — 2026-02/03

- Natural Flow redesign, macOS compatibility series (SF Pro/Menlo fonts,
  no emoji in UI strings, module-level appearance mode, in-app STOP button
  replacing the crashing global hotkey), PyInstaller packaging, MSIX build.

## [1.0.0] — 2026-02

- Initial release: CLI + cyberpunk GUI, QWERTY-adjacent typos with
  self-correction, anti-double-indent.
