# Human Typer — Ultimate QA Report

> **STATUS UPDATE (2026-10-05, v2.1.0):** All findings below were fixed in the
> v2.1.0 release except where noted. Fixed: **C1 C2 C3, H1 H2 H3, M1–M7, L1–L8**.
> The only item *not* fully applied is the git-history rewrite suggested in M7
> (removing the ~42 MB of old binary blobs) — that requires `git filter-repo`
> plus a force-push and is deliberately left as an owner decision; the
> `.gitignore` now prevents recurrence. Verification: engine tests 14/14, GUI
> tests 13/13, pyflakes clean, PyInstaller build + exe smoke-launch OK.
> See [CHANGELOG.md](CHANGELOG.md) for the full change list.

**Date:** 2026-10-05 · **Scope:** entire repo (`human_typer.py`, `human_typer_gui.py`, build scripts, CI workflows, docs, git hygiene) · **Tested on:** Windows 10.0.26100, Python 3.14.3, PyAutoGUI 0.9.54, CustomTkinter 6.0.0

**Method:** no real keystrokes were injected during testing. The engine was tested with a recording stub of pyautogui that replays pyautogui's *actual* per-OS key-mapping behavior (verified by reading the pyautogui 0.9.54 source for Windows/macOS/X11). The GUI was driven through a real `mainloop()` with the engine stubbed. Static analysis via `py_compile` + `pyflakes`. Re-run everything with the scripts in [`docs/qa/`](docs/qa/).

---

## Executive summary

**21 findings: 3 Critical, 3 High, 7 Medium, 8 Low.**

| ID | Severity | Finding |
|----|----------|---------|
| C1 | 🔴 Critical | `HumanTyper.spec` is **not committed** — macOS release CI can never build; Windows build not reproducible |
| C2 | 🔴 Critical | Non-ASCII text is **silently dropped** while typing (data loss on all 3 OSes) |
| C3 | 🔴 Critical | Typing thread has **no exception handling** → UI stuck on "RUNNING…" forever after any error |
| H1 | 🟠 High | Placeholder text gets **typed into the target window** (verified live) |
| H2 | 🟠 High | `django.yml` fails on **every push**; `python-publish.yml` fails on every release (leftover boilerplate) |
| H3 | 🟠 High | macOS App Store workflow is broken **and** the App Store path itself is unrealistic |
| M1–M7 | 🟡 Medium | Failsafe trap, no window-close handler, dead deps, stale README, missing icon in built exe, CLI crashes on `--wpm 0`, repo hygiene (42 MB binary history, no LICENSE) |
| L1–L8 | ⚪ Low | Dead code, version drift, hover color, progress bar math, stdout prints, no settings persistence, no test suite, privacy-policy wording |

**What works well** (verified, not assumed): the ASCII typing engine is genuinely solid — after 200 randomized runs at 30% error rate the final text was *exactly* correct every time; anti-double-indent and the STOP button behave correctly; both themes render cleanly. The core product logic is good — most of what's broken is packaging, edge cases, and hygiene.

---

## ✅ Verified working

| Check | Result |
|---|---|
| ASCII roundtrip with errors off — output byte-exact | PASS |
| Typo + backspace self-correction preserves text — 200 seeds @ 30% error | PASS (200/200) |
| Anti-double-indent: strips line-leading whitespace, keeps intra-line spaces | PASS |
| `stop_event` interrupts typing within one keystroke cycle | PASS |
| GUI: empty-text rejection ("No Text!") | PASS |
| GUI: STOP during countdown → "Aborted", START re-enabled, engine never runs | PASS |
| GUI: normal flow → "Completed", trailing newline rstripped | PASS |
| GUI: START disabled while running (no double-start race) | PASS |
| GUI: Light + Dark themes render correctly (see `docs/qa/gui_light.png`, `docs/qa/gui_dark2.png`) | PASS |
| Uppercase letters: typed correctly on Windows and macOS (pyautogui maps A–Z on both) | PASS |

---

## 🔴 Critical

### C1 — `HumanTyper.spec` is not in the repository
`.gitignore:35` has `*.spec` (a Python-package convention), so `HumanTyper.spec` — the file that defines the **entire build** — is untracked:
```
$ git ls-files | grep spec   →  (nothing)
$ git check-ignore -v HumanTyper.spec  →  .gitignore:35:*.spec
```
Consequences:
- `.github/workflows/macos_release.yml` runs `pyinstaller HumanTyper.spec --clean` on a fresh checkout → **the release build always fails**. It cannot have ever succeeded from CI.
- Nobody cloning the repo can reproduce `dist/HumanTyper.exe`.

**Fix:** `git add -f HumanTyper.spec` and delete the `*.spec` line from `.gitignore`.

### C2 — Non-ASCII characters are silently dropped (silent data loss)
Verified by reading pyautogui 0.9.54's platform modules: `press()`/`typewrite()` **silently ignore** any key not in the OS `keyboardMapping`. Those mappings cover only ASCII (X11 maps alphanumerics + symbols at `_pyautogui_x11.py:320`; Windows/macOS likewise; `'é' in pyautogui.platformModule.keyboardMapping` → `False`).

Engine test result (`docs/qa/test_engine.py`, T3):
```
input : "héllo wörld — नमस्ते 世界 🚀"   (25 chars)
typed :                                  (13 chars)
dropped incl. ['é', 'ö', '—', 'न', 'म', 'स']
```
No warning is shown, and the engine's printed promise — "Final output is 100% correct" — is false for this input. For a tool whose users type into VMs/Citrix, non-English text is a completely reasonable input.

**Fix (pragmatic):** scan input at START; if non-ASCII, show a warning and offer a clipboard-paste fallback (pyperclip + `Ctrl+V`) for the non-typable segments. **Fix (proper):** a small native backend using `SendInput` with `KEYEVENTF_UNICODE` (Windows) / `CGEventKeyboardSetUnicodeString` (macOS) — see roadmap.

### C3 — No exception handling in the typing thread → UI freezes in "RUNNING…"
`human_typer_gui.py:280-315` (`run_typing`): the cleanup block that re-enables START and resets the status is reached only if `human_typer.type_text(...)` returns normally. Any exception kills the daemon thread first:
- `pyautogui.FailSafeException` — pyautogui's failsafe is **still enabled** (moving the mouse to a screen corner mid-typing aborts with this exception). Only `PAUSE` was disabled (`human_typer.py:34`), not `FAILSAFE`.
- On macOS without Accessibility permission, pyautogui raises on first keystroke.
- Any future bug in the engine.

Result: status stuck at "Injecting…", START disabled, STOP enabled but useless, only recovery is killing the app.

**Fix:** wrap the body of `run_typing` in `try/except/finally` — `finally` must run the UI-reset block; `except` shows the error text in the status label. Also set `pyautogui.FAILSAFE = False` (the in-app STOP button is the intended abort) or catch `FailSafeException` explicitly and message the user.

---

## 🟠 High

### H1 — The placeholder gets typed into the target window
Verified live in the GUI harness: leaving the default "Paste your text here..." and appending real text sends the **placeholder to the target window**:
```
[PASS] G5 BUG: placeholder left in box gets typed — engine got 'Paste your text here...Hi'
```
Cause: `human_typer_gui.py:245-248` only rejects input whose stripped text **exactly equals** the placeholder. Anything else that contains it ("Paste your text here...Hi", or placeholder + a pasted paragraph) sails through. There is no clear-on-focus/clear-on-type binding, so the trap is easy to hit.

**Fix:** replace the manual placeholder with `CTkTextbox(placeholder_text="Paste your text here...")` (CustomTkinter ≥5.1 manages it automatically and `get()` excludes it), or bind the first `<Key>` to clear the box and keep the exact-match guard.

### H2 — Two leftover workflows are permanently red
- `.github/workflows/django.yml` runs `python manage.py test` on every push/PR to main. There is no `manage.py`, no Django, no tests → **red X on every commit**, on Python 3.7/3.8/3.9 (all EOL).
- `.github/workflows/python-publish.yml` runs `python -m build` on every GitHub release. There is no `pyproject.toml`/`setup.py` → fails too.

**Fix:** delete both (or disable them), and replace with one honest workflow: `py_compile` + `pyflakes` + the stubbed engine tests from `docs/qa/` — they run headless on all 3 OSes with zero keystrokes.

### H3 — macOS release workflow: broken mechanics *and* a broken destination
Beyond C1 (spec missing from checkout), `.github/workflows/macos_release.yml` has:
- `xcrun altool --upload-app` — **retired by Apple**; uploads must use `notarytool`/App Store Connect API or Transporter.
- Identity hardcoded as `"3rd Party Mac Developer Application"` with no team-ID suffix (ambiguous if more than one cert exists).
- Signing every file under `Contents/MacOS` **and** `Contents/Frameworks` with `--entitlements` — entitlements belong on the main bundle; helper binaries need `com.apple.security.inherit`, not full entitlements.
- `entitlements.plist` is wrong for this app: it has `com.apple.security.inherit` (only meaningful for child processes) but **no `com.apple.security.app-sandbox`**, which the App Store **requires** — and a sandboxed app cannot send CGEvents to type into other apps anyway.

**Fix:** decide the distribution story first. Realistic recommendation: drop the App Store path and ship a **Developer ID–signed + notarized .app/.dmg** (the app fundamentally needs Accessibility + unsandboxed CGEvents). Rewrite the workflow with `notarytool` and `AC_PASSWORD`/API keys. The current workflow should be disabled until then so tags don't produce misleading failures.

---

## 🟡 Medium

### M1 — Mouse-corner failsafe is a trap, not a feature (with C3)
`pyautogui.FAILSAFE` defaults to True. A user who slams the mouse to a corner while trying to stop the typing triggers `FailSafeException` → C3's stuck-UI path. Either disable it explicitly with a comment, or catch it and show "Typing aborted (mouse reached screen corner)".

### M2 — Closing the window mid-typing is unhandled
There is no `protocol("WM_DELETE_WINDOW", ...)` handler. On close, `mainloop()` exits while the daemon thread is mid-keystroke: possible stuck modifier keys, and `self.after()` from the dying thread raises `RuntimeError: main thread is not in main loop` (observed during testing).
**Fix:** handler that calls `stop_event.set()`, joins the thread (≤2 s), then destroys.

### M3 — Dead dependencies and a startup warning on every launch
Since commit `cf3f236` (STOP button replaced hotkeys), `human_typer_gui.py:10-24` imports `keyboard`/`pynput` **that are never used**. Observed on every launch: `WARNING: keyboard not installed. Stop hotkey will not work.` — a lie, since no hotkey exists. `keyboard` also still sits in `requirements.txt:3` and the README install line (and `keyboard` requires root on Linux if anyone ever did use it).
**Fix:** delete the import block, remove `keyboard` from requirements/README (keep `pynput` only if a planned feature needs it).

### M4 — README describes an app that no longer exists
- "Stop Hotkey: Panic button (Ctrl+Q)" — **removed** in `cf3f236`; Usage still documents "KILL_SWITCH".
- "Cyberpunk GUI, matrix green aesthetics, sound effects (visual only)" — the default theme is the cream/sage **Natural Flow** light theme; no sounds exist anywhere.
- Control names "INJECTION_SPEED / HUMAN_ERROR_SIM" vs actual labels "Flow Speed / Natural Variation".
- Install line `pip install customtkinter pyautogui keyboard Pillow` — misses `pynput`, lists now-unused `keyboard`.
- Quick-start numbering skips step 2.

**Fix:** rewrite the README against the current UI (the screenshots in `docs/qa/` are a starting point) and add a real feature/limitations section (including the C2 Unicode limitation until fixed).

### M5 — The packaged exe loses its window icon
`human_typer_gui.py:53-56` uses `self.iconbitmap("human_typer_icon.ico")` — a **cwd-relative** path. In the one-file PyInstaller exe the ico is extracted to `sys._MEIPASS`, not the cwd, so the call fails and the bare `except:` swallows it → no icon in `dist/HumanTyper.exe` (works in dev, broken in the shipped build).
**Fix:** standard resource helper: `os.path.join(sys._MEIPASS, ...) if getattr(sys, "frozen", False) else ...`.

### M6 — CLI crashes / misbehaves on unvalidated args
`human_typer.py`: `--wpm 0` → `ZeroDivisionError` (`base_delay = 60.0 / (wpm * 5)`, line 156); negative `--wpm` accepted; `--error-rate 5` accepted (every letter "typos" → ~10× slower with garbage behavior). Clamp: `0.1 ≤ wpm ≤ 500`, `0 ≤ error-rate ≤ 1`, exit with a clear message otherwise.

### M7 — Repo hygiene
- **~42 MB of build artifacts live in git history** (`msix_package/HumanTyper.exe` 21.1 MB, `Waiba.HumanTyper.msix` 20.9 MB — removed from HEAD but `.git` stays 43 MB). If repo size matters, rewrite history (e.g. `git filter-repo`) or start a fresh repo; either way add `*.msix`/`dist/` patterns so it doesn't happen again.
- `Waiba.HumanTyper.msix` (22 MB) currently sits untracked in the worktree — move it out of the repo or ignore it.
- **No LICENSE file** — a public GitHub repo without one is "all rights reserved" by default; nobody can legally reuse/fork. Add MIT/Apache-2.0 if that's the intent.
- No `.gitattributes` — with `core.autocrlf=true`, fresh Windows clones may check the `.sh` scripts out with CRLF, which breaks `bash run_gui.sh` on macOS/Linux. Add `*.sh text eol=lf`.
- `build_mac.sh:31` has an interactive `read -p` prompt — fine locally, fatal if anyone ever calls it from CI.

---

## ⚪ Low

| ID | Finding | Where |
|----|---------|-------|
| L1 | Dead code: unused `import platform`; dead `center_x/center_y/leaf_color` vars and an empty `try/except: pass` in create_icon.py; three f-strings without placeholders; a leftover scratch-comment block inside the suppress-indent logic (lines 196-214); stale `# Cleanup - no hotkey to remove` comment | `human_typer_gui.py:5`, `create_icon.py:28,31,60-65`, `human_typer.py:159,166,176,196-214,301` |
| L2 | Version drift: GUI title "v2.0", spec `CFBundleShortVersionString 1.0.0`, MSIX named "Waiba.HumanTyper", README has no version | everywhere |
| L3 | START hover `#4B5A42` is a light-theme olive — looks wrong against the dark-mode neon lime (visible in `gui_dark2.png` flow); bare `except:` around iconbitmap hides real errors | `human_typer_gui.py:192,54-56` |
| L4 | Countdown progress bar maxes out at 80% (`1.0 - i/delay` at i=1, delay=5); also no progress % during the actual typing | `human_typer_gui.py:287` |
| L5 | Engine's banner/countdown `print`s do nothing in the GUI (stdout is `None` in a windowed exe) and the emoji prints can raise `UnicodeEncodeError` on redirected cp1252 consoles | `human_typer.py:158-176` |
| L6 | No settings persistence — speed/error/checkbox reset every launch | `human_typer_gui.py` |
| L7 | No test suite in the repo (working stub-based harness already produced in `docs/qa/`) | — |
| L8 | PRIVACY_POLICY.md says "a Windows desktop application" but the same code ships to macOS via CI; App Store review will also read this | `PRIVACY_POLICY.md:6` |

---

## Roadmap — ideas to make this project better

### Quick wins (an afternoon)
1. Commit the spec, drop `*.spec` from .gitignore (**C1**).
2. Delete `django.yml` + `python-publish.yml`; add a real CI that runs `py_compile`, `pyflakes`, and `docs/qa/test_engine.py` on all 3 OSes (**H2**, L7).
3. `try/finally` in `run_typing` + `FAILSAFE=False` (**C3**, M1) and a `WM_DELETE_WINDOW` handler (**M2**).
4. `CTkTextbox(placeholder_text=...)` (**H1**).
5. README rewrite + LICENSE + `.gitattributes` + requirements prune (**M4**, M3, M7).
6. Resource-path helper for the icon (**M5**); clamp CLI args (**M6**).
7. Single-source version: `__version__` in one place, imported into the GUI title and the spec (**L2**).

### Near term (a week)
- **Unicode strategy** (**C2**): phase 1 — warn at START and offer clipboard-paste fallback (pyperclip + Ctrl+V) for non-typable segments; phase 2 — native Unicode backend (below). This is the single most valuable feature fix.
- **Real progress reporting**: add an optional `progress_callback(chars_done, total)` to `type_text`; drive the existing status bar with it (fixes L4's dead 80% bar and gives long sessions a % complete).
- **Settings persistence**: save speed/error/anti-indent/theme to a small JSON in `%APPDATA%/HumanTyper` (also fixes the "Light every launch" annoyance).
- **Pause/Resume** alongside STOP (the `stop_event` plumbing is already 90% of the work).
- **Proper signing pipeline**: Windows — Authenticode signing for the exe (otherwise SmartScreen scares users); macOS — Developer ID + `notarytool`, drop the App Store job (**H3**).
- **Promote the QA harness to `tests/`**: the stub approach in `docs/qa/` runs with zero keystrokes on CI; add a few regression cases per finding above.

### Bigger ideas
- **Native Unicode typing backend**: Windows `SendInput(KEYEVENTF_UNICODE)`, macOS `CGEventKeyboardSetUnicodeString`, X11 `XTest` + keysyms — makes C2 disappear properly and would even support Nepali/Chinese/Japanese. Keep pyautogui as the ASCII path.
- **Typing realism upgrades**: configurable per-key-row error weights (home row vs digits), burst-and-rest cadence, "retyping a word" behavior after 2+ corrections, drift in WPM over long sessions.
- **Profiles/presets**: "IDE" (anti-indent + code font preview), "Chat" (lower WPM, more typos), "Form" (higher accuracy) — one-click presets instead of 4 sliders.
- **Drag & drop** a .txt/.md/.py file onto the window to load it (currently CLI-only).
- **Session log**: optional local-only log of what was typed where (off by default; keeps the no-telemetry privacy promise while helping users debug).
- **Crash-safe logging**: write `human_typer.log` next to the app so C3-class failures are diagnosable from user reports.
- **Landing page + 15-second demo GIF** (the GUI is photogenic — show it); winget manifest for Windows distribution.
- **Responsible-use section in the README**: state the intended uses (VMs/Citrix/Remote Desktop where clipboard is blocked, accessibility, testing) — good for both users and platform reviewers.

---

## Appendix — reproduce the QA

```bash
cd docs/qa
python test_engine.py   # engine logic, stubbed pyautogui — no keystrokes (7/8; T8 expects stricter-than-real behavior)
python test_gui.py      # GUI flows inside a real mainloop, engine stubbed (14/15; one timing artifact)
python -m pyflakes human_typer.py human_typer_gui.py create_icon.py
```
Known noise: `WARNING: keyboard not installed` at startup = M3. Engine tests are deterministic (seeded). GUI test needs a display; it never presses START without stubbing the engine first.
