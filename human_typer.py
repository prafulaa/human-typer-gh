#!/usr/bin/env python3
"""
Human Typer - Types text into any active window like a real human.
Makes realistic typos then backspaces and corrects them.
Final output is 100% correct (ASCII always; full Unicode on Windows).

Usage:
  python3 human_typer.py                  # Interactive mode - paste/type text, press Enter twice to start
  python3 human_typer.py -f input.txt     # Type contents of a file
  python3 human_typer.py -t "some text"   # Type the given text directly

Options:
  --wpm 60          Words per minute (default: 60, range 1-700)
  --error-rate 0.06 Typo probability 0.0-1.0 (default: 0.06 = 6%)
  --delay 3         Seconds to wait before typing starts (default: 3)
"""

import time
import random
import string
import argparse
import sys

__version__ = "2.3.0"

try:
    import pyautogui
except ImportError:
    print("=" * 60)
    print("  pyautogui is required but not installed.")
    print("  Install it with:  pip install pyautogui")
    print("=" * 60)
    sys.exit(1)

# Disable pyautogui's failsafe pause for smoother typing.
# NOTE: pyautogui.FAILSAFE stays enabled on purpose - slamming the mouse into a
# screen corner is a legitimate panic stop. Callers should catch
# pyautogui.FailSafeException and report it instead of crashing.
pyautogui.PAUSE = 0

IS_WINDOWS = sys.platform == "win32"

# ──────────────────────────────────────────────────────
# Speed limits shared by the CLI and the GUI slider. Above FAST_MODE_WPM
# the cadence switches to steady jitter: at those speeds the punctuation
# "thinking" pauses would dominate the per-character budget and the
# displayed WPM would be fiction. (Merged from the multi-machine update.)
# ──────────────────────────────────────────────────────
MIN_WPM = 30
MAX_WPM = 700
FAST_MODE_WPM = 180

# ──────────────────────────────────────────────────────
# Windows Unicode typing via SendInput(KEYEVENTF_UNICODE)
# pyautogui can only type ASCII (its key maps are ASCII-only on every
# platform), so non-ASCII characters need a native path. On Windows we send
# UTF-16 code units directly, which types ANY character (accents, Devanagari,
# CJK, emoji). On macOS/Linux no native path is wired up yet, so non-ASCII
# characters are counted and skipped (see scan_untypeable()).
# ──────────────────────────────────────────────────────

if IS_WINDOWS:
    import ctypes
    import ctypes.wintypes as wintypes

    _INPUT_KEYBOARD = 1
    _KEYEVENTF_KEYUP = 0x0002
    _KEYEVENTF_UNICODE = 0x0004

    _PUL = ctypes.POINTER(ctypes.c_ulong)

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = (("wVk", wintypes.WORD),
                    ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", _PUL))

    class _INPUT(ctypes.Structure):
        _fields_ = (("type", wintypes.DWORD),
                    ("ki", _KEYBDINPUT))

    _SendInput = ctypes.windll.user32.SendInput
    _SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
    _SendInput.restype = wintypes.UINT

    def _type_unicode_windows(char):
        """Type one character (any codepoint) via KEYEVENTF_UNICODE."""
        data = char.encode("utf-16-le", errors="ignore")
        for k in range(0, len(data), 2):
            unit = data[k] | (data[k + 1] << 8)
            for flags in (0, _KEYEVENTF_KEYUP):
                inp = _INPUT(_INPUT_KEYBOARD, _KEYBDINPUT(0, unit,
                           _KEYEVENTF_UNICODE | flags, 0, None))
                _SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))
        return True

_UNICODE_SUPPORT = IS_WINDOWS

# ──────────────────────────────────────────────────────
# Human profiles: tune how "machine-like" vs "human" the session feels.
# err_mult scales the typo rate, pause_mult scales hesitation pauses,
# drift is the WPM random-walk amplitude, stutter is the chance of a
# mid-word "rethink" pause (types a correct prefix, pauses, continues).
# ──────────────────────────────────────────────────────
PROFILES = {
    "chill":   {"err_mult": 1.6, "pause_mult": 1.6, "drift": 0.22, "stutter": 0.012},
    "natural": {"err_mult": 1.0, "pause_mult": 1.0, "drift": 0.15, "stutter": 0.007},
    "focused": {"err_mult": 0.45, "pause_mult": 0.55, "drift": 0.08, "stutter": 0.0},
    "surgeon": {"err_mult": 0.0, "pause_mult": 0.35, "drift": 0.05, "stutter": 0.0},
}


def scan_untypeable(text):
    """Return a sorted string of the characters this platform cannot type.
    Empty string means every character in `text` is typeable."""
    bad = set()
    for ch in set(text):
        if ch in "\n\t":
            continue
        if ch in string.printable:
            continue
        if _UNICODE_SUPPORT:
            continue
        bad.add(ch)
    return "".join(sorted(bad))


# ──────────────────────────────────────────────────────
# QWERTY adjacent key map for realistic typos
# ──────────────────────────────────────────────────────
ADJACENT_KEYS = {
    'q': ['w', 'a'],
    'w': ['q', 'e', 'a', 's'],
    'e': ['w', 'r', 's', 'd'],
    'r': ['e', 't', 'd', 'f'],
    't': ['r', 'y', 'f', 'g'],
    'y': ['t', 'u', 'g', 'h'],
    'u': ['y', 'i', 'h', 'j'],
    'i': ['u', 'o', 'j', 'k'],
    'o': ['i', 'p', 'k', 'l'],
    'p': ['o', 'l'],
    'a': ['q', 'w', 's', 'z'],
    's': ['a', 'w', 'e', 'd', 'z', 'x'],
    'd': ['s', 'e', 'r', 'f', 'x', 'c'],
    'f': ['d', 'r', 't', 'g', 'c', 'v'],
    'g': ['f', 't', 'y', 'h', 'v', 'b'],
    'h': ['g', 'y', 'u', 'j', 'b', 'n'],
    'j': ['h', 'u', 'i', 'k', 'n', 'm'],
    'k': ['j', 'i', 'o', 'l', 'm'],
    'l': ['k', 'o', 'p'],
    'z': ['a', 's', 'x'],
    'x': ['z', 's', 'd', 'c'],
    'c': ['x', 'd', 'f', 'v'],
    'v': ['c', 'f', 'g', 'b'],
    'b': ['v', 'g', 'h', 'n'],
    'n': ['b', 'h', 'j', 'm'],
    'm': ['n', 'j', 'k'],
}


# ──────────────────────────────────────────────────────
# Typo generators (ASCII letters only - keeps every "wrong" keystroke
# typeable by pyautogui so backspace counts always line up)
# ──────────────────────────────────────────────────────

def get_adjacent_typo(char):
    """Return a nearby key on QWERTY layout."""
    lower = char.lower()
    if lower in ADJACENT_KEYS:
        typo = random.choice(ADJACENT_KEYS[lower])
        return typo.upper() if char.isupper() else typo
    return char


def generate_typo(char, next_char=None):
    """
    Generate a realistic typo. Returns (typo_string, num_backspaces_needed).
    Types:
      - Adjacent key hit (most common)
      - Double strike
      - Transposition (swap with next char)
      - Extra random letter
    """
    roll = random.random()

    if roll < 0.50:
        # Adjacent key hit
        typo = get_adjacent_typo(char)
        if typo == char:  # fallback if no adjacent found
            typo = random.choice(string.ascii_lowercase)
        return typo, 1

    elif roll < 0.70:
        # Double strike: type the char twice
        return char + char, 2  # typed 2 chars, need to delete both and retype 1

    elif roll < 0.85 and next_char and next_char.isalpha() and next_char.isascii():
        # Transposition: type next_char first, then current char, backspace both
        return next_char + char, 2

    else:
        # Random extra letter inserted before the real char
        extra = random.choice(string.ascii_lowercase)
        return extra, 1


# ──────────────────────────────────────────────────────
# Core typing engine
# ──────────────────────────────────────────────────────

def human_delay(base_delay, char, prev_char):
    """
    Calculate a human-like delay with natural variation.
    - Faster for common bigrams
    - Slower after spaces/punctuation (thinking)
    - Random jitter
    """
    delay = base_delay

    # Fast mode: above FAST_MODE_WPM the cadence is steady jitter - the
    # punctuation/space "thinking" pauses below would dwarf the per-char
    # budget and make the displayed WPM meaningless.
    if base_delay <= 60.0 / (FAST_MODE_WPM * 5):
        return max(0.005, base_delay * random.uniform(0.85, 1.15))

    # Add jitter (±40%)
    delay *= random.uniform(0.6, 1.4)

    # Slow down after sentence-ending punctuation (thinking pause)
    if prev_char in '.!?\n':
        delay += random.uniform(0.2, 0.8)

    # Slight pause after spaces (between words)
    elif prev_char == ' ':
        delay += random.uniform(0.02, 0.12)

    # Speed up for common bigrams
    fast_bigrams = ['th', 'he', 'in', 'er', 'an', 're', 'on', 'at', 'en', 'nd', 'st', 'es', 'or', 'te', 'of', 'it', 'is']
    if prev_char and (prev_char.lower() + char.lower()) in fast_bigrams:
        delay *= 0.7

    # Occasional micro-pause (cognitive hesitation)
    if random.random() < 0.03:
        delay += random.uniform(0.3, 1.0)

    return max(0.01, delay)


def _is_indentation(text, i):
    """True if position i is inside the leading whitespace of its line."""
    j = i - 1
    while j >= 0 and text[j] != '\n':
        if text[j] not in ' \t':
            return False
        j -= 1
    return True


def _wait_if_paused(pause_event, stop_event=None):
    """Block while the pause event is set. Returns early if stop is set."""
    while pause_event is not None and pause_event.is_set():
        if stop_event is not None and stop_event.is_set():
            return
        time.sleep(0.05)


def _sleep_interruptible(seconds, stop_event=None):
    """Sleep in small slices so a stop request is honored within ~50ms,
    even during long 'natural break' pauses."""
    end = time.time() + seconds
    while time.time() < end:
        if stop_event is not None and stop_event.is_set():
            return
        time.sleep(min(0.05, end - time.time()))


def _type_char(char):
    """Type a single character. Returns True if something was actually sent."""
    if char == '\n':
        pyautogui.press('enter')
        return True
    if char == '\t':
        pyautogui.press('tab')
        return True
    if char in string.printable and char not in '\t\n\r\x0b\x0c':
        pyautogui.typewrite(char, interval=0)
        return True
    if _UNICODE_SUPPORT:
        return _type_unicode_windows(char)
    return False  # cannot type this character on this platform


def _safe_print(msg):
    """print() that survives consoles which cannot encode emoji (cp1252 etc.)."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))


def type_text(text, wpm=60, error_rate=0.06, start_delay=3, stop_event=None,
              suppress_indent=False, verbose=True, progress_callback=None,
              pause_event=None, profile="natural"):
    """
    Types text into the currently focused window with human-like behavior.
    Makes typos and corrects them. Final output is 100% correct.

    Returns a summary dict: {"typed": int, "skipped": int, "skipped_chars": str}

    suppress_indent: skip leading whitespace of new lines (for IDEs that
        auto-indent, preventing the "staircase" effect).
    verbose: print the banner/countdown to stdout (CLI yes, GUI no).
    progress_callback(done, total): called roughly every 20 characters.
    pause_event: while set, typing suspends (Pause/Resume).
    profile: one of PROFILES keys - controls typo scaling, WPM drift,
        hesitation frequency ("natural" by default).
    """
    wpm = min(MAX_WPM, max(1, wpm))
    error_rate = min(1.0, max(0.0, error_rate))
    prof = PROFILES.get(profile, PROFILES["natural"])
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    total = len(text)

    # Base delay per character from WPM (avg 5 chars per word)
    base_delay = 60.0 / (wpm * 5)
    # Typo-correction "noticing" pauses are fixed-length; at high speeds
    # they would dominate, so scale them down toward zero as WPM rises.
    correction_pause_scale = min(1.0, 60.0 / wpm)

    skipped = {}

    if verbose:
        _safe_print(f"\n{'='*60}")
        _safe_print("  HUMAN TYPER")
        _safe_print(f"  Speed: ~{wpm} WPM | Error rate: {error_rate*100:.0f}%")
        _safe_print(f"  Text length: {total} characters")
        if not _UNICODE_SUPPORT:
            bad = scan_untypeable(text)
            if bad:
                _safe_print(f"  WARNING: cannot type these on this platform "
                            f"(they will be skipped): {bad[:40]}")
        _safe_print(f"{'='*60}")

    if start_delay > 0:
        if verbose:
            _safe_print(f"\n  Typing starts in {start_delay} seconds...")
            _safe_print("  Click on the target window/field NOW!\n")
        for i in range(start_delay, 0, -1):
            if stop_event and stop_event.is_set():
                if verbose:
                    _safe_print("  Typing cancelled before start.")
                return {"typed": 0, "skipped": 0, "skipped_chars": ""}
            _wait_if_paused(pause_event, stop_event)
            if verbose:
                _safe_print(f"     {i}...")
            time.sleep(1)

    if verbose:
        _safe_print("     Typing!\n")

    prev_char = ''
    i = 0
    drift = 1.0            # WPM random-walk factor (fatigue / flow)
    burst = 1.0            # temporary speed burst multiplier
    chars_in_word = 0

    while i < total:
        if stop_event and stop_event.is_set():
            if verbose:
                _safe_print("\n  Typing interrupted by user.")
            break

        _wait_if_paused(pause_event, stop_event)
        if stop_event and stop_event.is_set():
            break

        char = text[i]
        next_char = text[i + 1] if i + 1 < total else None

        # Anti-Auto-Indent: skip whitespace that starts a line
        if suppress_indent and char in ' \t' and _is_indentation(text, i):
            i += 1
            continue

        # WPM drift: slow random walk, keeps long sessions organic
        drift += random.uniform(-prof["drift"], prof["drift"]) * 0.06
        drift = min(1.25, max(0.80, drift))
        eff_delay = base_delay * drift * burst

        # Human hesitation patterns (delays only - output stays exact)
        if prev_char in ' \n' or i == 0:
            chars_in_word = 0
            # occasional burst at the start of a word
            burst = random.uniform(1.15, 1.35) if random.random() < 0.08 else 1.0
            # rethink pause at the start of a word (word stutter)
            if prof["stutter"] and random.random() < prof["stutter"]:
                _sleep_interruptible(random.uniform(0.15, 0.45) * prof["pause_mult"],
                                     stop_event)
        else:
            chars_in_word += 1
            # hesitate before long words / after capitals (thinking)
            if (chars_in_word == 0 and char.isupper()) or \
               (chars_in_word > 6 and random.random() < 0.02 * prof["pause_mult"]):
                _sleep_interruptible(random.uniform(0.1, 0.4) * prof["pause_mult"],
                                     stop_event)
        # thinking pause after paragraph breaks
        if prev_char == '\n' and char == '\n':
            _sleep_interruptible(random.uniform(0.4, 1.2) * prof["pause_mult"],
                                 stop_event)

        # Decide if we make a typo on this character (ASCII letters only,
        # never right after sentence end)
        make_error = (
            random.random() < min(1.0, error_rate * prof["err_mult"])
            and char.isalpha()
            and char.isascii()
            and prev_char not in '.!?\n'
        )

        if make_error:
            typo_str, backspaces = generate_typo(char, next_char)

            # Type the wrong character(s)
            for tc in typo_str:
                if stop_event and stop_event.is_set():
                    break
                _wait_if_paused(pause_event, stop_event)
                pyautogui.press(tc) if len(tc) == 1 and tc in string.printable else pyautogui.typewrite(tc, interval=0)
                time.sleep(eff_delay * random.uniform(0.5, 1.0))

            if stop_event and stop_event.is_set():
                break

            # Brief pause — "noticing" the mistake (scaled down at speed)
            time.sleep(random.uniform(0.1, 0.4) * correction_pause_scale)

            # Backspace to fix
            for _ in range(backspaces):
                if stop_event and stop_event.is_set():
                    break
                pyautogui.press('backspace')
                time.sleep(random.uniform(0.03, 0.08))

            if stop_event and stop_event.is_set():
                break

            # Small pause after correction (scaled down at speed)
            time.sleep(random.uniform(0.05, 0.15) * correction_pause_scale)

            # Now type the correct character
            if not _type_char(char):
                skipped[char] = skipped.get(char, 0) + 1
            time.sleep(human_delay(eff_delay, char, prev_char))

        else:
            if not _type_char(char):
                skipped[char] = skipped.get(char, 0) + 1
            time.sleep(human_delay(eff_delay, char, prev_char))

        prev_char = char
        i += 1

        if progress_callback and (i % 20 == 0 or i == total):
            try:
                progress_callback(i, total)
            except Exception:
                pass  # a UI callback must never kill the typing thread

        # Occasional natural break (every ~200-500 chars)
        if random.random() < 0.003 * prof["pause_mult"]:
            _sleep_interruptible(random.uniform(1.0, 3.0) * prof["pause_mult"],
                                 stop_event)

    stopped = bool(stop_event and stop_event.is_set())
    n_skipped = sum(skipped.values())

    if verbose and not stopped:
        _safe_print(f"\n  Done! Typed {i} characters.")
        if n_skipped:
            _safe_print(f"  WARNING: {n_skipped} characters were skipped "
                        f"(not typeable on this platform): {''.join(skipped)}")

    return {"typed": i, "skipped": n_skipped, "skipped_chars": "".join(skipped)}


# ──────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────

def _wpm_arg(value):
    try:
        iv = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer")
    if not 1 <= iv <= MAX_WPM:
        raise argparse.ArgumentTypeError(f"wpm must be between 1 and {MAX_WPM}")
    return iv


def _rate_arg(value):
    try:
        fv = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number")
    if not 0.0 <= fv <= 1.0:
        raise argparse.ArgumentTypeError("error-rate must be between 0.0 and 1.0")
    return fv


def main():
    parser = argparse.ArgumentParser(
        description="Human Typer — Types text into any window like a real human, with typos and corrections.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 human_typer.py                      # Interactive mode
  python3 human_typer.py -f essay.txt         # Type from file
  python3 human_typer.py -t "Hello world"     # Type a string
  python3 human_typer.py -f essay.txt --wpm 80 --error-rate 0.08
        """
    )
    parser.add_argument('-f', '--file', help='Path to text file to type')
    parser.add_argument('-t', '--text', help='Text string to type')
    parser.add_argument('--wpm', type=_wpm_arg, default=60, help='Words per minute (default: 60, range 1-700)')
    parser.add_argument('--error-rate', type=_rate_arg, default=0.06, metavar='RATE',
                        help='Typo probability 0.0-1.0 (default: 0.06)')
    parser.add_argument('--delay', type=int, default=3, help='Seconds before typing starts (default: 3)')

    args = parser.parse_args()

    # Get the text
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                text = f.read()
        except OSError as e:
            _safe_print(f"[ERROR] Cannot read {args.file}: {e}")
            sys.exit(1)
        _safe_print(f"Loaded {len(text)} characters from: {args.file}")

    elif args.text:
        text = args.text

    else:
        # Interactive mode
        _safe_print("=" * 60)
        _safe_print("  HUMAN TYPER — Interactive Mode")
        _safe_print("=" * 60)
        _safe_print("\nPaste or type your text below.")
        _safe_print("Press ENTER on an empty line to start typing.\n")
        lines = []
        while True:
            try:
                line = input()
                if line == '' and lines:
                    break
                lines.append(line)
            except EOFError:
                break
        text = '\n'.join(lines)

    if not text.strip():
        _safe_print("[ERROR] No text provided. Exiting.")
        sys.exit(1)

    try:
        type_text(text, wpm=args.wpm, error_rate=args.error_rate, start_delay=args.delay)
    except KeyboardInterrupt:
        _safe_print("\n[Stopped by user (Ctrl+C).]")
        sys.exit(130)
    except pyautogui.FailSafeException:
        _safe_print("\n[Stopped: mouse moved to a screen corner (pyautogui failsafe).]")
        sys.exit(130)


if __name__ == '__main__':
    main()
