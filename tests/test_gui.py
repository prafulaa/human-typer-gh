"""GUI tests for human_typer_gui.py — runs inside a real mainloop() so
cross-thread after() works exactly like the shipping app.

The engine is STUBBED: no real keystrokes are ever sent.

Run:  python tests/test_gui.py   (needs a display)
"""
import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import human_typer

# Stub the keyboard lib BEFORE human_typer_gui import (Windows hotkey path)
class FakeKB:
    def __init__(self):
        self.registered = []
        self.removed = []
    def add_hotkey(self, combo, fn, suppress=False):
        self.registered.append((combo, fn, suppress))
        return ("job", combo)
    def remove_hotkey(self, job):
        self.removed.append(job)

KB = FakeKB()
sys.modules.setdefault('keyboard', KB)

TYPE_CALLS = []
HOLD = {"t": 0.0}
RAISE = {"e": None}


def stub_type_text(text, **kw):
    TYPE_CALLS.append((text, kw))
    if RAISE["e"]:
        raise RAISE["e"]
    stop_event = kw.get("stop_event")
    if HOLD["t"]:
        # interruptible hold: honors stop like the real engine does
        end = time.time() + HOLD["t"]
        while time.time() < end:
            if stop_event is not None and stop_event.is_set():
                break
            time.sleep(0.05)
    return {"typed": len(text), "skipped": 0, "skipped_chars": ""}


human_typer.type_text = stub_type_text
# GUI reads FailSafeException from human_typer.pyautogui - keep real class

import human_typer_gui  # noqa: E402
from PIL import ImageGrab  # noqa: E402

# isolate settings from the developer's real settings
TEST_SETTINGS = os.path.join(os.environ.get("TEMP", "/tmp"), "ht_test_settings.json")
human_typer_gui.SETTINGS_FILE = TEST_SETTINGS
if os.path.exists(TEST_SETTINGS):
    os.remove(TEST_SETTINGS)

app = human_typer_gui.HumanTyperApp()
app.geometry("470x860+50+20")
FAILS = []
TOTAL = {"n": 0}


def check(name, ok, detail=""):
    TOTAL["n"] += 1
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)
    if not ok:
        FAILS.append(name)


def shot(name):
    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    ImageGrab.grab(bbox=(x - 10, y - 10, x + w + 10, y + h + 40)).save(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs",
                     "screenshots", f"{name}.png"))


def after_session(cb, tries=120):
    """Wait until no typing thread is running and START is re-enabled."""
    def poll(n=[0]):
        t = app.typing_thread
        done = (t is None or not t.is_alive()) and \
            str(app.btn_start.cget("state")) == "normal"
        if done or n[0] >= tries:
            time.sleep(0.2)
            app.update_idletasks()
            cb()
        else:
            n[0] += 1
            app.after(100, poll)
    app.after(100, poll)


def phase1():  # visuals + basics
    os.makedirs(os.path.join("docs", "screenshots"), exist_ok=True)
    app.update_idletasks()
    app.after(300, lambda: (shot("gui_light"),
                             check("G1 title shows version",
                                   human_typer.__version__ in app.title(), app.title()),
                             phase1b()))


def phase1b():
    app.toggle_theme()
    app.update_idletasks()
    check("G2 theme toggles to Dark", app.theme_mode == "Dark")
    app.after(500, lambda: (shot("gui_dark"), phase1c()))


def phase1c():
    app.toggle_theme()
    app.update_idletasks()
    check("G2b settings persisted (dark saved)",
          json.load(open(TEST_SETTINGS)).get("theme") == "Light")
    app.toggle_settings()
    app.update_idletasks()
    check("G3 settings panel toggles", app.settings_visible)
    app.toggle_settings()
    app.after(10, phase2)


def phase2():  # placeholder fix (was H1: placeholder got typed)
    TYPE_CALLS.clear()
    # simulate a user typing into the box: first key clears the placeholder
    app.text_area.focus_force()
    app.text_area.event_generate("<FocusIn>")
    app.update()
    app.text_area.insert("end", "Real text")
    app.update_idletasks()
    check("G4 stats label populated", "words" in app.lbl_stats.cget("text"),
          app.lbl_stats.cget("text"))
    app.start_typing_thread()
    app.after(5800, lambda: check("G5 placeholder NOT typed; real text typed",
                                  TYPE_CALLS and TYPE_CALLS[0][0] == "Real text",
                                  f"got {[c[0] for c in TYPE_CALLS]}") or phase2b())


def phase2b():
    after_session(phase3)


def phase3():  # empty/placeholder-only rejection
    TYPE_CALLS.clear()
    app.text_area.configure(state="normal")
    app.text_area.delete("0.0", "end")
    app.text_area.insert("0.0", human_typer_gui.PLACEHOLDER)  # simulate untouched box
    app.start_typing_thread()
    app.update_idletasks()
    ok = app.lbl_status_val.cget("text") == "No Text!" and not TYPE_CALLS
    check("G6 untouched placeholder rejected as empty", ok,
          f"status={app.lbl_status_val.cget('text')} calls={len(TYPE_CALLS)}")
    app.after(10, phase4)


def phase4():  # STOP during countdown + abort
    TYPE_CALLS.clear()
    app.stop_event.clear()
    app.text_area.delete("0.0", "end")
    app.text_area.insert("0.0", "stop test")
    app.start_typing_thread()
    def click_stop():
        app.btn_stop.invoke()
        app.update_idletasks()
        def poll(n=[0]):
            if app.lbl_status_val.cget("text") == "Aborted" or n[0] > 90:
                check("G7 STOP during countdown aborts",
                      app.lbl_status_val.cget("text") == "Aborted"
                      and len(TYPE_CALLS) == 0
                      and str(app.btn_start.cget("state")) == "normal",
                      f"status={app.lbl_status_val.cget('text')}")
                app.after(10, phase5)
            else:
                n[0] += 1
                app.after(100, poll)
        app.after(100, poll)
    app.after(1000, click_stop)


def phase5():  # PAUSE / RESUME mid-typing
    TYPE_CALLS.clear()
    RAISE["e"] = None
    HOLD["t"] = 3.0  # engine "runs" 3s after countdown
    app.stop_event.clear()
    app.text_area.delete("0.0", "end")
    app.text_area.insert("0.0", "pause me")
    app.start_typing_thread()

    def do_pause():
        app.btn_pause.invoke()
        app.update_idletasks()
        check("G8 pause sets events + UI", app.pause_event.is_set()
              and app.btn_pause.cget("text") == "RESUME"
              and app.lbl_status_val.cget("text") == "Paused",
              f"status={app.lbl_status_val.cget('text')}")
        app.after(300, do_resume)

    def do_resume():
        app.btn_pause.invoke()
        app.update_idletasks()
        check("G9 resume clears pause", not app.pause_event.is_set()
              and app.btn_pause.cget("text") == "PAUSE")
        app.btn_stop.invoke()
        after_session(phase6)

    app.after(5600, do_pause)  # countdown(5s) + 0.6s into engine hold


def phase6():  # engine exception -> UI recovers (was C3)
    HOLD["t"] = 0.0
    RAISE["e"] = RuntimeError("boom")
    TYPE_CALLS.clear()
    app.stop_event.clear()
    app.text_area.delete("0.0", "end")
    app.text_area.insert("0.0", "will fail")
    app.start_typing_thread()

    def poll(n=[0]):
        if app.lbl_status_val.cget("text").startswith("Error") or n[0] > 120:
            check("G10 engine exception -> status Error, START re-enabled",
                  app.lbl_status_val.cget("text").startswith("Error")
                  and str(app.btn_start.cget("state")) == "normal",
                  f"status={app.lbl_status_val.cget('text')}")
            RAISE["e"] = None
            app.after(10, phase7)
        else:
            n[0] += 1
            app.after(100, poll)
    app.after(5300, lambda: poll())


def phase7():  # progress callback wired + completion status
    TYPE_CALLS.clear()
    app.stop_event.clear()
    app.text_area.delete("0.0", "end")
    app.text_area.insert("0.0", "finish line")
    app.start_typing_thread()

    def poll(n=[0]):
        if app.lbl_status_val.cget("text") == "Completed" or n[0] > 120:
            kw = TYPE_CALLS[0][1] if TYPE_CALLS else {}
            check("G11 completes; engine got progress+pause+profile hooks",
                  app.lbl_status_val.cget("text") == "Completed"
                  and kw.get("progress_callback") is not None
                  and kw.get("pause_event") is app.pause_event
                  and kw.get("verbose") is False
                  and kw.get("profile") == "natural",
                  f"status={app.lbl_status_val.cget('text')} kw={list(kw)}")
            app.after(10, phase8)
        else:
            n[0] += 1
            app.after(100, poll)
    app.after(5300, lambda: poll())


def phase8():  # appearance system + untypeable warning + clean close
    # G14: settings dialog opens and closes
    app.toggle_settings()
    app.update()
    app.update_idletasks()
    dialog_ok = (app.settings_visible and app.settings_dialog is not None
                 and app.settings_dialog.winfo_exists())
    app.after(400, lambda: shot("settings_dialog") if dialog_ok else None)
    app.after(700, phase8b)


def phase8b():
    dialog_ok = (app.settings_visible and app.settings_dialog is not None
                 and app.settings_dialog.winfo_exists())
    app.toggle_settings()
    app.update_idletasks()
    closed = not app.settings_visible
    check("G14 settings dialog opens/closes", dialog_ok and closed,
          f"opened={dialog_ok} closed={closed}")

    # G15: accent switch applies + persists
    before = app.btn_start.cget("fg_color")
    app.set_accent("sky")
    app.update_idletasks()
    data = json.load(open(TEST_SETTINGS))
    check("G15 accent change applied + persisted",
          app.current_accent == "sky" and data.get("accent") == "sky"
          and app.btn_start.cget("fg_color") != before,
          f"accent={app.current_accent} file={data.get('accent')}")

    # G16: corner style persists and reshapes widgets
    app.set_corner_style("Round")
    app.update_idletasks()
    data = json.load(open(TEST_SETTINGS))
    check("G16 corner style applied + persisted",
          app.corner_style == "Round" and data.get("corners") == "Round"
          and app.text_area.cget("corner_radius") == max(8, 22 - 6),
          f"corners={app.corner_style} file={data.get('corners')} "
          f"input_r={app.text_area.cget('corner_radius')}")
    app.set_accent("lime")
    app.set_corner_style("Soft")

    # G17: window must fit the screen after repeated theme toggles
    # (the "goes fullscreen on 125% DPI" bug)
    for _ in range(3):
        app.toggle_theme()
        app.update_idletasks()
    sh = app.winfo_screenheight()
    check("G17 window fits screen after theme toggles",
          app.win_h <= sh - 60 and app.winfo_height() <= sh + 1
          and app.winfo_width() == app.win_w,
          f"win={app.winfo_width()}x{app.winfo_height()} screen_h={sh} "
          f"planned={app.win_w}x{app.win_h}")

    # G18: hotkeys - registration, normalization, panic callback
    from human_typer_gui import normalize_combo
    check("G18a combo normalization",
          normalize_combo("q") is None
          and normalize_combo("shift+q") is None
          and normalize_combo("q+ctrl") == "ctrl+q"
          and normalize_combo("ctrl+shift+f5") == "ctrl+shift+f5")
    app.settings["stop_hotkey"] = "ctrl+q"
    app.settings["start_hotkey"] = ""
    KB.registered.clear()
    app.apply_hotkeys()
    stop_cbs = [fn for c, fn, sup in KB.registered if c == "ctrl+q" and sup]
    check("G18b stop hotkey registered (suppressed)",
          len(stop_cbs) == 1
          and not any(c == "" for c, _, _ in KB.registered),
          f"registered={[c for c, _, _ in KB.registered]}")
    if stop_cbs:
        stop_cbs[0]()  # simulate panic press from the listener thread
        app.update_idletasks()
        check("G18c panic hotkey sets stop_event",
              app.stop_event.is_set())
        app.stop_event.clear()

    # G19: WPM slider spans the engine's full range (30-700, merged update)
    check("G19 WPM slider max is 700",
          float(app.slider_speed.cget("to")) == float(human_typer.MAX_WPM)
          and float(getattr(app.slider_speed, "_from_", 0)) == float(human_typer.MIN_WPM),
          f"from={getattr(app.slider_speed, '_from_', '?')} to={app.slider_speed.cget('to')}")

    app.text_area.configure(state="normal")
    app.text_area.delete("0.0", "end")
    was_supported = human_typer._UNICODE_SUPPORT
    human_typer._UNICODE_SUPPORT = False  # simulate macOS
    app.text_area.insert("0.0", "héllo")
    app.text_area.event_generate("<KeyRelease>")  # simulate typing (live stats path)
    app.update_idletasks()
    warn_shown = "skipped" in app.lbl_warn.cget("text")
    if not warn_shown:
        # pre-flight path (start_typing_thread refresh) must also surface it
        app._update_stats()
        app.update_idletasks()
        warn_shown = "skipped" in app.lbl_warn.cget("text")
    human_typer._UNICODE_SUPPORT = was_supported
    check("G12 untypeable chars warned", warn_shown,
          app.lbl_warn.cget("text"))

    # close while a session is running (was M2)
    HOLD["t"] = 3.0
    app.text_area.delete("0.0", "end")
    app.text_area.insert("0.0", "close test")
    app.start_typing_thread()

    def do_close():
        exited = {"ok": False}

        orig_destroy = app.destroy

        def spy_destroy():
            exited["ok"] = True
            # thread must already be joined (or done) when destroy is called
            exited["alive"] = app.typing_thread.is_alive()
            orig_destroy()

        app.destroy = spy_destroy
        try:
            app._on_close()
        finally:
            app.destroy = orig_destroy
        check("G13 clean close joins thread then destroys",
              exited.get("ok") and not exited.get("alive"),
              f"destroyed={exited.get('ok')} thread_alive_at_destroy={exited.get('alive')}")
        print(f"\n{TOTAL['n'] - len(FAILS)}/{TOTAL['n']} passed"
              + (f", FAILED: {FAILS}" if FAILS else ""), flush=True)
        try:
            if app.winfo_exists():
                orig_destroy()
        except Exception:
            pass
        sys.exit(1 if FAILS else 0)

    app.after(5600, do_close)


app.after(300, phase1)
app.mainloop()
