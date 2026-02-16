#!/usr/bin/env python3
"""
Human Typer - Types text into any active window like a real human.
Makes realistic typos then backspaces and corrects them.
Final output is 100% correct.

Usage:
  python3 human_typer.py                  # Interactive mode - paste/type text, press Enter twice to start
  python3 human_typer.py -f input.txt     # Type contents of a file
  python3 human_typer.py -t "some text"   # Type the given text directly

Options:
  --wpm 60          Words per minute (default: 60)
  --error-rate 0.06 Typo probability 0.0-1.0 (default: 0.06 = 6%)
  --delay 3         Seconds to wait before typing starts (default: 3)
"""

import time
import random
import string
import argparse
import sys

try:
    import pyautogui
except ImportError:
    print("=" * 60)
    print("  pyautogui is required but not installed.")
    print("  Install it with:  pip install pyautogui")
    print("=" * 60)
    sys.exit(1)

# Disable pyautogui's failsafe pause for smoother typing
pyautogui.PAUSE = 0

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
# Typo generators
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

    elif roll < 0.85 and next_char and next_char.isalpha():
        # Transposition: type next_char first, then current char, backspace both
        return next_char + char, 2  # will need to delete both and retype correctly

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


def type_text(text, wpm=60, error_rate=0.06, start_delay=3, stop_event=None, suppress_indent=False):
    """
    Types text into the currently focused window with human-like behavior.
    Makes typos and corrects them. Final output is 100% correct.
    Supports a stop_event to interrupt typing.
    suppress_indent: If True, skips leading whitespace of new lines (useful for IDEs that auto-indent).
    """
    # Base delay per character from WPM (avg 5 chars per word)
    base_delay = 60.0 / (wpm * 5)

    print(f"\n{'='*60}")
    print(f"  HUMAN TYPER")
    print(f"  Speed: ~{wpm} WPM | Error rate: {error_rate*100:.0f}%")
    print(f"  Text length: {len(text)} characters")
    print(f"{'='*60}")
    
    if start_delay > 0:
        print(f"\n  ⏳ Typing starts in {start_delay} seconds...")
        print(f"  👉 Click on the target window/field NOW!\n")

        # Countdown
        for i in range(start_delay, 0, -1):
            if stop_event and stop_event.is_set():
                print("🛑 Typing cancelled before start.")
                return
            print(f"     {i}...")
            time.sleep(1)
            
    print(f"     ✏️  Typing!\n")

    prev_char = ''
    i = 0

    while i < len(text):
        # Check for stop signal
        if stop_event and stop_event.is_set():
            print("\n🛑 Typing interrupted by user.")
            break

        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else None
        
        # Determine if we should skip this character (Anti-Auto-Indent)
        skip_char = False
        if suppress_indent and char in ' \t':
             # If previous char was newline, we are in indentation
             if prev_char == '\n' or (i == 0):
                 skip_char = True
             # If we are in a sequence of spaces that follow a newline, keep skipping
             # But we only look back one char. We need a way to know if we are 'in indentation'.
             # More robust: check if all chars since last \n are whitespace
             # This simple check prev_char == '\n' only catches the FIRST space.
             
             # Better logic: Check if we are currently at the start of a line (only whitespace before us on this line)
             j = i - 1
             is_indentation = True
             while j >= 0:
                 if text[j] == '\n':
                     break # Found start of line, so yes we are in indentation
                 if text[j] not in ' \t':
                     is_indentation = False # Found non-whitespace, so not indentation
                     break
                 j -= 1
             # Provide fallback if start of text
             if j < 0 and i > 0: # Start of text, check if all before were whitespace
                 # reuse is_indentation logic above which defaults to True
                 pass
             
             if is_indentation:
                 # It is indentation space, skip it!
                 skip_char = True

        if skip_char:
            i += 1
            continue

        # Decide if we make a typo on this character
        make_error = (
            random.random() < error_rate
            and char.isalpha()          # Only typo on letters
            and prev_char not in '.!?\n'  # Don't typo right after sentence end
        )

        if make_error:
            # Generate and type the typo
            typo_str, backspaces = generate_typo(char, next_char)

            # Type the wrong character(s)
            for tc in typo_str:
                if stop_event and stop_event.is_set(): break
                pyautogui.press(tc) if len(tc) == 1 and tc in string.printable else pyautogui.typewrite(tc, interval=0)
                time.sleep(base_delay * random.uniform(0.5, 1.0))
            
            if stop_event and stop_event.is_set(): break

            # Brief pause — "noticing" the mistake
            time.sleep(random.uniform(0.1, 0.4))

            # Backspace to fix
            for _ in range(backspaces):
                if stop_event and stop_event.is_set(): break
                pyautogui.press('backspace')
                time.sleep(random.uniform(0.03, 0.08))
            
            if stop_event and stop_event.is_set(): break

            # Small pause after correction
            time.sleep(random.uniform(0.05, 0.15))

            # Now type the correct character
            _type_char(char)
            time.sleep(human_delay(base_delay, char, prev_char))

        else:
            # Normal typing
            _type_char(char)
            time.sleep(human_delay(base_delay, char, prev_char))

        prev_char = char
        i += 1

        # Occasional natural break (every ~200-500 chars)
        if random.random() < 0.003:
            time.sleep(random.uniform(1.0, 3.0))

    if not (stop_event and stop_event.is_set()):
        print(f"\n  ✅ Done! Typed {i} characters.")


def _type_char(char):
    """Type a single character handling special keys."""
    if char == '\n':
        pyautogui.press('enter')
    elif char == '\t':
        pyautogui.press('tab')
    else:
        pyautogui.typewrite(char, interval=0) if char in string.printable and char not in '\t\n\r\x0b\x0c' else pyautogui.press(char)


# ──────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────

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
    parser.add_argument('--wpm', type=int, default=60, help='Words per minute (default: 60)')
    parser.add_argument('--error-rate', type=float, default=0.06, help='Typo probability 0.0-1.0 (default: 0.06)')
    parser.add_argument('--delay', type=int, default=3, help='Seconds before typing starts (default: 3)')

    args = parser.parse_args()

    # Get the text
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read()
        print(f"📄 Loaded {len(text)} characters from: {args.file}")

    elif args.text:
        text = args.text

    else:
        # Interactive mode
        print("=" * 60)
        print("  HUMAN TYPER — Interactive Mode")
        print("=" * 60)
        print("\nPaste or type your text below.")
        print("Press ENTER on an empty line to start typing.\n")
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
        print("❌ No text provided. Exiting.")
        sys.exit(1)

    type_text(text, wpm=args.wpm, error_rate=args.error_rate, start_delay=args.delay)


if __name__ == '__main__':
    main()
