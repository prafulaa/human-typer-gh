"""Engine tests for human_typer with a recording stub of pyautogui.

No real keystrokes are ever sent: pyautogui is stubbed before import, and the
Windows SendInput Unicode path is stubbed/disabled explicitly. The stub models
pyautogui's REAL per-OS behavior (keys absent from the platform key map are
silently dropped), verified against the pyautogui 0.9.54 source.

Run:  python tests/test_engine.py
"""
import sys
import os
import types
import random
import string
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KEY_NAMES = set(string.ascii_lowercase + string.ascii_uppercase + string.digits
                + " \t\n!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")

calls = []

fake = types.ModuleType('pyautogui')
fake.PAUSE = 0
class FailSafeException(Exception):
    pass
fake.FailSafeException = FailSafeException


def press(k, *a, **kw):
    calls.append(('press', k))


def typewrite(t, *a, **kw):
    calls.append(('type', t))


fake.press = press
fake.typewrite = typewrite
sys.modules['pyautogui'] = fake

# Collapse engine sleeps so the suite is fast; restore for the pause test.
_orig_sleep = time.sleep
time.sleep = lambda s: _orig_sleep(min(s, 0.0002))

import human_typer  # noqa: E402  (imports the stubbed pyautogui)


def reconstruct(calls_list, platform_map):
    """Simulate what the target window receives given a platform key map.
    Keys not in the map are silently dropped (pyautogui's real behavior)."""
    buf = []
    for kind, val in calls_list:
        items = [val] if kind == 'press' else list(val)
        for it in items:
            if it == '\n' or it in ('enter', 'return'):
                buf.append('\n')
            elif it == '\t':
                buf.append('\t')
            elif it == 'backspace':
                if buf:
                    buf.pop()
            elif it == 'space':
                buf.append(' ')
            elif it in platform_map:
                buf.append(it)
    return ''.join(buf)


results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)


def run(text, wpm=1000, err=0.0, suppress=False, seed=42, **kw):
    global calls
    calls = []
    random.seed(seed)
    summary = human_typer.type_text(text, wpm=wpm, error_rate=err,
                                    start_delay=0, suppress_indent=suppress, **kw)
    return list(calls), summary


# ── T1: baseline ASCII, no errors → output must be exact ──
src = "Hello World! This is line one.\nLine two: 42 + 7 = 49."
calls_made, summary = run(src)
out = reconstruct(calls_made, KEY_NAMES)
check("T1 ASCII no-error roundtrip", out == src and summary["typed"] == len(src),
      f"got {out!r}")

# ── T2: ASCII with typos → corrections must restore exact text ──
src = "The quick brown Fox JUMPS over 12 lazy dogs. Testing UPPERCASE typos here."
bad = None
for seed in range(200):
    calls_made, _ = run(src, err=0.3, seed=seed)
    out = reconstruct(calls_made, KEY_NAMES)
    if out != src:
        bad = (seed, out)
        break
check("T2 typo self-correction preserves text (200 seeds)", bad is None,
      "" if bad is None else f"seed {bad[0]} corrupted: {bad[1]!r}")

# ── T3: Unicode without native support → dropped AND reported in summary ──
src = "héllo wörld — नमस्ते 世界 🚀"
human_typer._UNICODE_SUPPORT = False
calls_made, summary = run(src)
out = reconstruct(calls_made, KEY_NAMES)
check("T3 unicode skipped+reported when unsupported",
      len(out) < len(src) and summary["skipped"] > 0 and "é" in summary["skipped_chars"],
      f"out={out!r} summary={summary}")

# ── T4: Unicode WITH native path → routed through _type_unicode_windows ──
uni_calls = []
human_typer._type_unicode_windows = lambda ch: uni_calls.append(ch) or True
human_typer._UNICODE_SUPPORT = True
calls_made, summary = run(src)
out = reconstruct(calls_made, KEY_NAMES) + "".join(uni_calls)
uni_expected = [c for c in src if c not in string.printable]
check("T4 unicode routed to native path (no data loss)",
      summary["skipped"] == 0 and sorted(uni_calls) == sorted(uni_expected),
      f"native={uni_calls} summary={summary}")
human_typer._UNICODE_SUPPORT = sys.platform == "win32"

# ── T5: suppress_indent strips leading whitespace, keeps intra-line spaces ──
calls_made, _ = run("def foo():\n    return 1\n\tprint(2)", suppress=True)
out = reconstruct(calls_made, KEY_NAMES)
check("T5a anti-double-indent strips line-leading ws", out == "def foo():\nreturn 1\nprint(2)",
      f"got {out!r}")
calls_made, _ = run("a b  c\n  d", suppress=True)
out = reconstruct(calls_made, KEY_NAMES)
check("T5b anti-indent keeps intra-line spaces", out == "a b  c\nd", f"got {out!r}")

# ── T6: stop_event interrupts promptly ──
global_calls = []
ev = threading.Event()
random.seed(1)
count = {'n': 0}
orig = time.sleep


def fake_sleep(s):
    count['n'] += 1
    if count['n'] == 50:
        ev.set()
    orig(min(s, 0.001))


time.sleep = fake_sleep
try:
    calls.clear()
    human_typer.type_text("word " * 5000, wpm=1000, error_rate=0,
                          start_delay=0, stop_event=ev)
finally:
    time.sleep = lambda s: _orig_sleep(min(s, 0.0002))
check("T6 stop_event interrupts typing", len(calls) < 25000,
      f"~{len(calls)} calls before stop")

# ── T7: pause_event suspends and resumes ──
ev_p = threading.Event()
ev_s = threading.Event()
state = {'n1': None, 'n2': None, 'n3': None}


def pauser():
    _orig_sleep(0.4)      # let it type a while
    ev_p.set()            # pause
    state['n1'] = len(calls)
    _orig_sleep(0.4)
    state['n2'] = len(calls)   # must equal n1 while paused
    ev_p.clear()          # resume
    _orig_sleep(0.4)
    state['n3'] = len(calls)   # must be > n2 after resume
    ev_s.set()            # stop


calls.clear()
threading.Thread(target=pauser, daemon=True).start()
time.sleep = _orig_sleep  # real sleeps so pause is observable
try:
    human_typer.type_text("word " * 200, wpm=600, error_rate=0, start_delay=0,
                          stop_event=ev_s, pause_event=ev_p)
finally:
    time.sleep = lambda s: _orig_sleep(min(s, 0.0002))
check("T7 pause suspends keystrokes, resume continues",
      state['n1'] and state['n2'] == state['n1'] and state['n3'] > state['n2'],
      f"counts={state}")

# ── T8: CRLF / CR normalization ──
calls_made, _ = run("a\r\nb\rc")
out = reconstruct(calls_made, KEY_NAMES)
check("T8 CRLF and lone CR become newlines", out == "a\nb\nc", f"got {out!r}")

# ── T9: progress callback receives (done, total) and reaches total ──
seen = []
calls_made, _ = run("abcdefghij" * 10, progress_callback=lambda d, t: seen.append((d, t)))
check("T9 progress callback monotonic and complete",
      seen and seen[-1][0] == seen[-1][1] == 100 and
      all(seen[i][0] <= seen[i + 1][0] for i in range(len(seen) - 1)),
      f"last={seen[-1] if seen else None}")

# ── T10: wpm/error-rate clamping inside engine (CLI validates too) ──
calls_made, _ = run("abc", wpm=0, err=99)   # would ZeroDivisionError before fix
out = reconstruct(calls_made, KEY_NAMES)
check("T10 clamped wpm=0 / err=99 do not crash", out == "abc", f"got {out!r}")

# ── T11: scan_untypeable correctness ──
human_typer._UNICODE_SUPPORT = False
bad_chars = human_typer.scan_untypeable("héllo 世界 ok")
check("T11a scan_untypeable lists non-ASCII when unsupported",
      sorted(bad_chars) == sorted("é世界"), f"got {bad_chars!r}")
human_typer._UNICODE_SUPPORT = True
check("T11b scan_untypeable empty when native path available",
      human_typer.scan_untypeable("héllo 世界 🚀 ok") == "")
human_typer._UNICODE_SUPPORT = sys.platform == "win32"

# ── T12: verbose=False prints nothing ──
import io  # noqa: E402
from contextlib import redirect_stdout  # noqa: E402
buf = io.StringIO()
with redirect_stdout(buf):
    run("hello", verbose=False)
check("T12 quiet mode prints nothing", buf.getvalue() == "", f"got {buf.getvalue()!r}")

# ── T13: human profiles are delay-only - output stays byte-exact ──
src = "Paragraph one has several words here.\n\nParagraph two: Caps And LongWords follow."
for pname in ("chill", "natural", "focused", "surgeon"):
    calls_made, _ = run(src, err=0.1, seed=7, profile=pname)
    out = reconstruct(calls_made, KEY_NAMES)
    check(f"T13 profile={pname} output exact", out == src,
          f"got {out!r}" if out != src else "")

# ── T14: high WPM (400 and 700 fast-mode) works and stays exact ──
src = "hello world " * 50
calls_made, summary = run(src, wpm=400)
out = reconstruct(calls_made, KEY_NAMES)
check("T14 wpm=400 exact roundtrip", out == src and summary["typed"] == len(src),
      f"got {out!r}" if out != src else f"summary={summary}")
calls_made, summary = run(src, wpm=700)
out = reconstruct(calls_made, KEY_NAMES)
check("T14b wpm=700 fast-mode exact roundtrip", out == src and summary["typed"] == len(src),
      f"got {out!r}" if out != src else f"summary={summary}")

# ── T15: unknown profile falls back to natural without crashing ──
calls_made, _ = run("fallback test", profile="bogus-name")
out = reconstruct(calls_made, KEY_NAMES)
check("T15 unknown profile falls back safely", out == "fallback test",
      f"got {out!r}")

fails = [i for i, ok in enumerate(results) if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} passed, {len(fails)} failed", flush=True)
sys.exit(1 if fails else 0)
