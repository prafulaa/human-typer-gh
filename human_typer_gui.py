import customtkinter as ctk
import math
import threading
import time
import sys
import os
import json

import human_typer  # engine (typing behavior lives there, not here)
from ui_kit import HoverButton, Tooltip, ctk_icon, resolve, tween

IS_MACOS = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"
VERSION = human_typer.__version__
FailSafeException = human_typer.pyautogui.FailSafeException

PLACEHOLDER = "Paste your text here..."

# Global hotkeys are only wired on Windows. On macOS, global keyboard hooks
# crash (CoreText/Tk - see commit cf3f236) and on Linux `keyboard` needs root;
# there the in-app buttons remain the stop/start mechanism.
if IS_WINDOWS:
    try:
        import keyboard as _kb
    except Exception:
        _kb = None
else:
    _kb = None

# ──────────────────────────────────────────────────────────────────
# Design tokens. Surfaces are (light, dark) tuples; accents carry
# base/hover/pressed variants for the animated buttons.
# ──────────────────────────────────────────────────────────────────

COLOR_BG = ("#F4F6F1", "#0C1410")        # off-white / deep forest
COLOR_CARD = ("#FFFFFF", "#16211B")      # surface
COLOR_CARD2 = ("#F0F2EA", "#1C2A22")     # hovered surface / input bg
COLOR_TRACK = ("#E4E7DF", "#25342B")     # sliders / separators
COLOR_TEXT = ("#232A22", "#E7ECE6")
COLOR_MUTED = ("#7C8677", "#7E9183")
COLOR_ERROR = ("#DC2626", "#F87171")
COLOR_SECONDARY = ("#C4A484", "#5D4037")  # tan / dark wood (countdown)

ACCENTS = {
    "lime":   {"base": ("#6D8A3E", "#A3E635"), "hover": ("#5A7230", "#8FCC26"),
               "pressed": ("#4C6129", "#7BB31F"), "text": ("#FFFFFF", "#10240A")},
    "sky":    {"base": ("#3B82F6", "#38BDF8"), "hover": ("#2F6BD7", "#28A8E0"),
               "pressed": ("#285BB4", "#2193C4"), "text": ("#FFFFFF", "#082436")},
    "amber":  {"base": ("#D97706", "#FBBF24"), "hover": ("#B46305", "#E5AC1B"),
               "pressed": ("#965204", "#C49717"), "text": ("#FFFFFF", "#2E1C02")},
    "rose":   {"base": ("#E11D48", "#FB7185"), "hover": ("#C0173D", "#E85F72"),
               "pressed": ("#A11333", "#D14E60"), "text": ("#FFFFFF", "#33060F")},
    "violet": {"base": ("#7C3AED", "#A78BFA"), "hover": ("#6830C7", "#9275E8"),
               "pressed": ("#5728A6", "#7E63D2"), "text": ("#FFFFFF", "#1D0B3B")},
}
ACCENT_ORDER = ["lime", "sky", "amber", "rose", "violet"]

NEUTRAL_BTN = {"base": ("#56604F", "#3A4A42"), "hover": ("#47513F", "#2E3C35"),
               "pressed": ("#3B4436", "#25332C"), "text": ("#FFFFFF", "#E7ECE6")}
DANGER_BTN = {"base": ("#DC2626", "#F87171"), "hover": ("#B91C1C", "#EF4444"),
              "pressed": ("#991B1B", "#D32F2F"), "text": ("#FFFFFF", "#2B0808")}

CORNER_STYLES = {"Sharp": 6, "Soft": 14, "Round": 22}
PROFILE_LABELS = {"Chill": "chill", "Natural": "natural",
                  "Focused": "focused", "Surgeon": "surgeon"}

# MUST be set before creating any CTk window — fixes black window on macOS.
# The saved theme is applied right after the window is created (toggling
# appearance mode later, like toggle_theme does, is safe).
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("green")


def resource_path(name):
    """Absolute path to a bundled asset - works in dev and in the
    PyInstaller one-file build (where assets unpack to sys._MEIPASS)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def _config_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif IS_MACOS:
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    path = os.path.join(base, "HumanTyper")
    os.makedirs(path, exist_ok=True)
    return path

SETTINGS_FILE = os.path.join(_config_dir(), "settings.json")


def normalize_combo(combo):
    """Validate a hotkey combo for the `keyboard` lib. Requires at least one
    of ctrl/alt so a global hook can never swallow plain typing. Modifiers
    may appear in any order; exactly one non-modifier key is required."""
    if not combo:
        return None
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    if not parts:
        return None
    mods = [p for p in parts if p in _MODIFIER_KEYS]
    keys = [p for p in parts if p not in _MODIFIER_KEYS]
    if len(keys) != 1:
        return None
    key = keys[0]
    key_ok = (len(key) == 1 and key.isalnum()) or key in _ALLOWED_KEYS
    if not key_ok or any(m not in _MODIFIER_KEYS for m in mods):
        return None
    if not ({"ctrl", "alt"} & set(mods)):
        return None
    ordered = [m for m in ("ctrl", "alt", "shift") if m in mods]
    ordered.append(key)
    return "+".join(ordered)


_MODIFIER_KEYS = {"ctrl", "alt", "shift"}
_ALLOWED_KEYS = {"esc", "enter", "space", "tab",
                 "up", "down", "left", "right",
                 "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9",
                 "f10", "f11", "f12"}


class HotkeyCapture(ctk.CTkFrame):
    """Read-only field + Record button. Click record, press a combo with
    ctrl or alt, and it is stored via on_change."""

    def __init__(self, master, value, on_change, placeholder="-- none --"):
        super().__init__(master, fg_color="transparent")
        self.on_change = on_change
        self.recording = False
        self._value = value or ""
        self.grid_columnconfigure(0, weight=1)

        self.var = ctk.StringVar(value=value or placeholder)
        self.entry = ctk.CTkEntry(self, textvariable=self.var, state="readonly",
                                  font=ctk.CTkFont(family="Consolas", size=12),
                                  fg_color=COLOR_CARD2, text_color=COLOR_TEXT,
                                  border_color=COLOR_TRACK, corner_radius=8,
                                  height=34)
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.entry.bind("<Key>", self._on_key)

        self.btn = ctk.CTkButton(self, text="Record", width=78, height=34,
                                 fg_color=NEUTRAL_BTN["base"],
                                 hover_color=NEUTRAL_BTN["hover"],
                                 text_color=NEUTRAL_BTN["text"],
                                 font=ctk.CTkFont(size=11),
                                 command=self._toggle_record)
        self.btn.grid(row=0, column=1)

    def _toggle_record(self):
        self.recording = not self.recording
        if self.recording:
            self.entry.configure(state="normal")
            self.var.set("press keys... (esc cancels)")
            self.entry.focus_force()
            self.btn.configure(text="Cancel", fg_color=COLOR_ERROR,
                               hover_color=DANGER_BTN["hover"])
        else:
            self._stop_record()

    def _stop_record(self):
        self.recording = False
        self.entry.configure(state="readonly")
        self.btn.configure(text="Record", fg_color=NEUTRAL_BTN["base"],
                           hover_color=NEUTRAL_BTN["hover"])
        self._refresh_value()

    def _refresh_value(self):
        current = getattr(self, "_value", "") or ""
        self.var.set(current or "-- none --")

    def set_value(self, combo):
        self._value = combo
        self._refresh_value()

    def _on_key(self, event):
        if not self.recording:
            return "break"
        keysym = event.keysym
        if keysym == "Escape":
            self._toggle_record()
            return "break"
        mods = []
        if event.state & 0x0004:
            mods.append("ctrl")
        if event.state & 0x20000:
            mods.append("alt")
        if event.state & 0x0001:
            mods.append("shift")
        key = keysym.lower()
        key_map = {"return": "enter", "escape": "esc"}
        key = key_map.get(key, key)
        if key in ("control_l", "control_r", "alt_l", "alt_r",
                   "shift_l", "shift_r"):
            return "break"  # wait for the actual key
        if len(key) == 1:
            if key == " ":
                key = "space"
            if "ctrl" not in mods and "alt" not in mods:
                self.var.set("need ctrl or alt!")
                return "break"
        if key not in _ALLOWED_KEYS:
            self.var.set("unsupported key")
            return "break"
        combo = normalize_combo("+".join(mods + [key]))
        if combo is None:
            self.var.set("need ctrl or alt!")
            return "break"
        self._value = combo
        self.on_change(combo)
        self._toggle_record()  # exits recording mode + refreshes display
        return "break"


class SettingsDialog(ctk.CTkToplevel):
    """Settings modal: Appearance, Typing, Hotkeys (Windows), About."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Settings")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_CARD)
        self.transient(app)
        # grab only once the window is actually viewable - grab_set() on a
        # not-yet-mapped CTkToplevel raises TclError (CTk delays deiconify
        # for its titlebar-color handling)
        self.after(250, self._safe_grab)
        self.protocol("WM_DELETE_WINDOW", app.toggle_settings)

        pad = 24
        self.grid_columnconfigure(0, weight=1)
        row = 0

        def section_title(text):
            nonlocal row
            lbl = ctk.CTkLabel(self, text=text.upper(), font=ctk.CTkFont(size=11),
                               text_color=COLOR_MUTED)
            lbl.grid(row=row, column=0, padx=pad, pady=(20 if row else 22, 8),
                     sticky="w")
            row += 1

        def row_frame(pad_top=(0, 8)):
            nonlocal row
            f = ctk.CTkFrame(self, fg_color="transparent")
            f.grid(row=row, column=0, padx=pad, pady=pad_top, sticky="ew")
            f.grid_columnconfigure(1, weight=1)
            row += 1
            return f

        # ── Appearance ──
        section_title("Appearance")

        f = row_frame()
        ctk.CTkLabel(f, text="Theme", font=ctk.CTkFont(size=13),
                     text_color=COLOR_TEXT).grid(row=0, column=0, sticky="w")
        self.seg_theme = ctk.CTkSegmentedButton(
            f, values=["Light", "Dark"], command=self._on_theme,
            selected_color=ACCENTS[app.current_accent]["base"],
            selected_hover_color=ACCENTS[app.current_accent]["hover"],
            font=ctk.CTkFont(size=12))
        self.seg_theme.set(app.theme_mode)
        self.seg_theme.grid(row=0, column=1, sticky="e")

        f = row_frame()
        ctk.CTkLabel(f, text="Accent", font=ctk.CTkFont(size=13),
                     text_color=COLOR_TEXT).grid(row=0, column=0, sticky="w")
        sw = ctk.CTkFrame(f, fg_color="transparent")
        sw.grid(row=0, column=1, sticky="e")
        self.swatches = {}
        for i, key in enumerate(ACCENT_ORDER):
            pal = ACCENTS[key]
            b = ctk.CTkButton(sw, width=30, height=30, text="",
                              corner_radius=15, fg_color=pal["base"],
                              hover_color=pal["hover"],
                              command=lambda k=key: self._on_accent(k))
            b.grid(row=0, column=i, padx=(0, 8))
            self.swatches[key] = b

        f = row_frame((0, 2))
        ctk.CTkLabel(f, text="Corner style", font=ctk.CTkFont(size=13),
                     text_color=COLOR_TEXT).grid(row=0, column=0, sticky="w")
        self.seg_corner = ctk.CTkSegmentedButton(
            f, values=list(CORNER_STYLES), command=self._on_corners,
            selected_color=ACCENTS[app.current_accent]["base"],
            selected_hover_color=ACCENTS[app.current_accent]["hover"],
            font=ctk.CTkFont(size=12))
        self.seg_corner.set(app.corner_style)
        self.seg_corner.grid(row=0, column=1, sticky="e")

        # ── Typing ──
        section_title("Typing")

        f = row_frame()
        ctk.CTkLabel(f, text="Style", font=ctk.CTkFont(size=13),
                     text_color=COLOR_TEXT).grid(row=0, column=0, sticky="w")
        self.profile_menu = ctk.CTkOptionMenu(
            f, values=list(PROFILE_LABELS), command=self._on_profile,
            fg_color=COLOR_CARD2, button_color=COLOR_TRACK,
            button_hover_color=COLOR_TRACK, text_color=COLOR_TEXT,
            corner_radius=8, font=ctk.CTkFont(size=12),
            dropdown_fg_color=COLOR_CARD, dropdown_text_color=COLOR_TEXT,
            dropdown_hover_color=COLOR_CARD2)
        inv = {v: k for k, v in PROFILE_LABELS.items()}
        self.profile_menu.set(inv.get(app.settings.get("profile", "natural"), "Natural"))
        self.profile_menu.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(self, text="Chill = more typos and pauses  |  "
                                "Surgeon = zero typos, machine steady",
                     font=ctk.CTkFont(size=11),
                     text_color=COLOR_MUTED).grid(row=row, column=0, padx=pad,
                                                  pady=(2, 8), sticky="w")
        row += 1

        f = row_frame((0, 2))
        ctk.CTkLabel(f, text="Start delay", font=ctk.CTkFont(size=13),
                     text_color=COLOR_TEXT).grid(row=0, column=0, sticky="w")
        self.seg_delay = ctk.CTkSegmentedButton(
            f, values=["3 s", "5 s", "10 s"], command=self._on_delay,
            selected_color=ACCENTS[app.current_accent]["base"],
            selected_hover_color=ACCENTS[app.current_accent]["hover"],
            font=ctk.CTkFont(size=12))
        self.seg_delay.set(f"{app.settings.get('start_delay', 5)} s")
        self.seg_delay.grid(row=0, column=1, sticky="e")

        # ── Hotkeys (Windows only) ──
        section_title("Hotkeys")
        if _kb is not None:
            f = row_frame()
            ctk.CTkLabel(f, image=ctk_icon("keyboard", resolve(COLOR_MUTED),
                                           resolve(COLOR_MUTED), px=16),
                         text="").grid(row=0, column=0, sticky="w", padx=(0, 8))
            ctk.CTkLabel(f, text="Start typing", font=ctk.CTkFont(size=13),
                         text_color=COLOR_TEXT).grid(row=0, column=0, sticky="w",
                                                     padx=(24, 0))
            self.hk_start = HotkeyCapture(
                f, app.settings.get("start_hotkey", ""),
                on_change=lambda c: self._on_hotkey("start_hotkey", c))
            self.hk_start.grid(row=0, column=1, sticky="e")

            f = row_frame((0, 2))
            ctk.CTkLabel(f, image=ctk_icon("stop", resolve(COLOR_MUTED),
                                           resolve(COLOR_MUTED), px=14),
                         text="").grid(row=0, column=0, sticky="w", padx=(0, 8))
            ctk.CTkLabel(f, text="Panic stop", font=ctk.CTkFont(size=13),
                         text_color=COLOR_TEXT).grid(row=0, column=0, sticky="w",
                                                     padx=(24, 0))
            self.hk_stop = HotkeyCapture(
                f, app.settings.get("stop_hotkey", "ctrl+q"),
                on_change=lambda c: self._on_hotkey("stop_hotkey", c))
            self.hk_stop.grid(row=0, column=1, sticky="e")

            ctk.CTkLabel(self, text="Combos need ctrl or alt. The default "
                                    "ctrl+q is suppressed, so the target app never sees it.",
                         font=ctk.CTkFont(size=11),
                         text_color=COLOR_MUTED).grid(row=row, column=0,
                                                      padx=pad, pady=(2, 0),
                                                      sticky="w")
            row += 1
        else:
            ctk.CTkLabel(self, text="Global hotkeys are not available on this "
                                    "platform.\nThe in-app PAUSE and STOP buttons "
                                    "always work.",
                         font=ctk.CTkFont(size=11), justify="left",
                         text_color=COLOR_MUTED).grid(row=row, column=0, padx=pad,
                                                      pady=(0, 4), sticky="w")
            row += 1

        # ── Footer actions ──
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=row, column=0, padx=pad, pady=(18, 8), sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)

        def reset():
            self.app.set_accent("lime")
            self.app.set_corner_style("Soft")
            self.app.set_theme_value("Light")
            self.app.settings["start_delay"] = 5
            self.app.settings["profile"] = "natural"
            self.app.settings["start_hotkey"] = ""
            self.app.settings["stop_hotkey"] = "ctrl+q"
            self.app._save_settings()
            self.app.apply_hotkeys()
            self._sync_all()

        ctk.CTkButton(btn_row, text="Reset defaults", height=36,
                      fg_color="transparent", border_width=1,
                      border_color=COLOR_TRACK, text_color=COLOR_MUTED,
                      hover_color=COLOR_CARD2,
                      image=ctk_icon("refresh", resolve(COLOR_MUTED),
                                     resolve(COLOR_MUTED), px=14),
                      command=reset).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(btn_row, text="Done", width=96, height=36,
                      fg_color=ACCENTS[app.current_accent]["base"],
                      hover_color=ACCENTS[app.current_accent]["hover"],
                      text_color=ACCENTS[app.current_accent]["text"],
                      command=app.toggle_settings).grid(row=0, column=1,
                                                        padx=(10, 0), sticky="e")

        ctk.CTkLabel(self, text=f"Human Typer v{VERSION} - local only, no telemetry",
                     font=ctk.CTkFont(size=10), text_color=COLOR_MUTED).grid(
            row=row + 1, column=0, padx=pad, pady=(0, 16), sticky="w")

        # center over the parent window, clamped to the screen
        self.update_idletasks()
        w = self.app.win_w  # same scale-aware width as the main window
        h = self.winfo_reqheight()
        sw, sh = app.winfo_screenwidth(), app.winfo_screenheight()
        px = min(max(0, app.winfo_rootx() + (app.winfo_width() - w) // 2), sw - w - 8)
        py = min(max(0, app.winfo_rooty() + (app.winfo_height() - h) // 2), sh - h - 8)
        self.geometry(f"{w}x{h}+{px}+{py}")

    def _safe_grab(self):
        try:
            if self.winfo_exists():
                self.grab_set()
        except Exception:
            pass  # never let modal grabbing break the dialog

    def _on_theme(self, value):
        self.app.set_theme_value(value)
        self._sync()

    def _on_accent(self, key):
        self.app.set_accent(key)
        self._sync()

    def _on_corners(self, value):
        self.app.set_corner_style(value)

    def _on_profile(self, label):
        self.app.settings["profile"] = PROFILE_LABELS[label]
        self.app._save_settings()

    def _on_delay(self, value):
        self.app.settings["start_delay"] = int(value.split()[0])
        self.app._save_settings()

    def _on_hotkey(self, key, combo):
        self.app.settings[key] = combo
        self.app._save_settings()
        self.app.apply_hotkeys()

    def _sync(self):
        pal = ACCENTS[self.app.current_accent]["base"]
        hov = ACCENTS[self.app.current_accent]["hover"]
        for seg in (self.seg_theme, self.seg_corner, self.seg_delay):
            seg.configure(selected_color=pal, selected_hover_color=hov)
        self.seg_theme.set(self.app.theme_mode)
        self.seg_corner.set(self.app.corner_style)
        for key, b in self.swatches.items():
            b.configure(border_width=3 if key == self.app.current_accent else 0,
                        border_color=COLOR_TEXT)

    def _sync_all(self):
        self._sync()
        self.profile_menu.set({v: k for k, v in PROFILE_LABELS.items()}
                              .get(self.app.settings.get("profile", "natural"), "Natural"))
        self.seg_delay.set(f"{self.app.settings.get('start_delay', 5)} s")
        if _kb is not None:
            self.hk_start.set_value(self.app.settings.get("start_hotkey", ""))
            self.hk_stop.set_value(self.app.settings.get("stop_hotkey", "ctrl+q"))


class HumanTyperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings = self._load_settings()
        self.theme_mode = self.settings.get("theme", "Light")
        self.current_accent = self.settings.get("accent", "lime")
        if self.current_accent not in ACCENTS:
            self.current_accent = "lime"
        self.corner_style = self.settings.get("corners", "Soft")
        if self.corner_style not in CORNER_STYLES:
            self.corner_style = "Soft"
        self.settings_visible = False
        self._dot_pulsing = False
        self._icons = {"play": ctk_icon("play", "#FFFFFF", "#FFFFFF", px=16),
                       "pause": ctk_icon("pause", "#FFFFFF", "#FFFFFF", px=16),
                       "stop": ctk_icon("stop", "#FFFFFF", "#FFFFFF", px=15)}

        self.title(f"Human Typer v{VERSION}")
        # Fit the work area on ANY DPI: CustomTkinter scales widget sizes by
        # the OS scale factor (1.25 at 125%), and the window manager will
        # grow the window to the content's *scaled* request — so a fixed
        # logical size overflows the screen (the "goes fullscreen" bug).
        # Plan in logical units, then multiply by the scale factor.
        sh = self.winfo_screenheight()
        try:
            scale = ctk.ScalingTracker.get_widget_scaling(self)
        except Exception:
            scale = 1.0
        self.ui_scale = scale
        logical_budget = sh / scale - 56  # taskbar headroom
        logical_h = min(870, max(640, logical_budget))
        self.win_w = math.ceil(470 * scale)  # ceil: match content request
        self.win_h = int(logical_h * scale)
        self.input_h = 170 if logical_h >= 850 else (130 if logical_h >= 700 else 90)
        self.geometry(f"{self.win_w}x{self.win_h}")
        self.resizable(False, True)

        # Icon (Windows only — .ico not supported on macOS)
        if not IS_MACOS:
            try:
                self.iconbitmap(resource_path("human_typer_icon.ico"))
            except Exception:
                pass

        if self.theme_mode == "Dark":
            ctk.set_appearance_mode("Dark")

        self.configure(fg_color=COLOR_BG)

        # Fonts - use cross-platform safe fonts (Roboto not installed on macOS)
        _font_ui = "SF Pro Display" if IS_MACOS else "Segoe UI"
        _font_mono = "Menlo" if IS_MACOS else "Consolas"
        self.font_header = ctk.CTkFont(family=_font_ui, size=21, weight="bold")
        self.font_sub = ctk.CTkFont(family=_font_ui, size=12)
        self.font_label = ctk.CTkFont(family=_font_ui, size=14, weight="bold")
        self.font_body = ctk.CTkFont(family=_font_ui, size=12)
        self.font_mini = ctk.CTkFont(family=_font_ui, size=10)
        self.font_code = ctk.CTkFont(family=_font_mono, size=12)
        self.font_stat = ctk.CTkFont(family=_font_ui, size=15, weight="bold")

        # registries for live restyling (accent / corner changes)
        self._reg_accent_btn = []      # HoverButtons with accent palette
        self._reg_accent_fg = []       # plain widgets, fg_color = accent
        self._reg_accent_prog = []     # sliders, progress_color = accent
        self._reg_corners = []         # (widget, kind)

        self.grid_columnconfigure(0, weight=1)
        self._build_header()
        self._build_cards()
        self._build_input()
        self._build_controls()
        self._build_actions()
        self._build_footer()

        # Logic
        self.typing_thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.paused = False
        self._closing = False
        self.settings_dialog = None
        self._bar_job = {"id": None}
        self._hk_jobs = {}

        # Clean shutdown while a session is running
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.apply_appearance()
        self.apply_hotkeys()
        self._update_stats()
        self.update_speed_label(self.slider_speed.get())
        self.update_var_label(self.slider_var.get())

    # ════════════════════════════════════════════
    # Construction
    # ════════════════════════════════════════════

    def _round(self, kind):
        base = CORNER_STYLES[self.corner_style]
        if kind == "card":
            return base
        if kind == "input":
            return max(8, base - 6)
        if kind == "btn":
            return min(28, base + 8)
        if kind == "chip":
            return base // 2
        return base

    def _register_corners(self, w, kind):
        self._reg_corners.append((w, kind))

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=22, pady=(20, 12), sticky="ew")

        # Accent badge with tree icon
        self.badge = ctk.CTkFrame(header, width=46, height=46,
                                  corner_radius=23, fg_color=COLOR_MUTED)
        self.badge.pack(side="left", padx=(0, 12))
        self.badge.pack_propagate(False)
        self._reg_accent_fg.append(self.badge)
        self._register_corners(self.badge, "chip")
        self.badge_icon = ctk.CTkLabel(self.badge, text="",
                                       image=ctk_icon("tree", "#FFFFFF", "#FFFFFF", px=24))
        self.badge_icon.pack(expand=True)

        title_stack = ctk.CTkFrame(header, fg_color="transparent")
        title_stack.pack(side="left")
        self.title_label = ctk.CTkLabel(title_stack, text="Human Typer",
                                        font=self.font_header, text_color=COLOR_TEXT)
        self.title_label.pack(anchor="w")
        self.subtitle_label = ctk.CTkLabel(title_stack, text="Natural Flow",
                                           font=self.font_sub, text_color=COLOR_MUTED)
        self.subtitle_label.pack(anchor="w")

        self.version_chip = ctk.CTkLabel(header, text=f" v{VERSION} ",
                                         font=self.font_mini, text_color=COLOR_MUTED,
                                         fg_color=COLOR_CARD, corner_radius=8)
        self.version_chip.pack(side="left", padx=(10, 0), pady=(6, 0))

        # Theme + settings icon buttons
        self.theme_btn = ctk.CTkButton(header, width=42, height=42, text="",
                                       corner_radius=14, fg_color=COLOR_CARD,
                                       hover_color=COLOR_CARD2,
                                       command=self.toggle_theme)
        self.theme_btn.pack(side="right", padx=(8, 0))
        self._register_corners(self.theme_btn, "btn")
        Tooltip(self.theme_btn, "Toggle Light / Dark theme")

        self.settings_btn = ctk.CTkButton(header, width=42, height=42, text="",
                                          corner_radius=14, fg_color=COLOR_CARD,
                                          hover_color=COLOR_CARD2,
                                          image=ctk_icon("gear", resolve(COLOR_MUTED),
                                                         resolve(COLOR_MUTED), px=18),
                                          command=self.toggle_settings)
        self.settings_btn.pack(side="right")
        self._register_corners(self.settings_btn, "btn")
        Tooltip(self.settings_btn, "Theme, accent, corners, hotkeys")

    def _build_cards(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=1, column=0, padx=22, pady=(0, 12), sticky="ew")
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)

        # ── STATUS card ──
        self.card_status = ctk.CTkFrame(row, fg_color=COLOR_CARD, corner_radius=14)
        self.card_status.grid(row=0, column=0, padx=(0, 8), sticky="nsew")
        self._register_corners(self.card_status, "card")
        ctk.CTkLabel(self.card_status, text="STATUS", font=self.font_mini,
                     text_color=COLOR_MUTED).pack(anchor="w", padx=14, pady=(12, 0))
        strip = ctk.CTkFrame(self.card_status, fg_color="transparent")
        strip.pack(anchor="w", padx=14, fill="x")
        self.live_dot = ctk.CTkFrame(strip, width=9, height=9,
                                     corner_radius=5, fg_color=COLOR_MUTED)
        self.live_dot.pack(side="left", padx=(0, 7))
        self.lbl_status_val = ctk.CTkLabel(strip, text="Ready",
                                           font=self.font_stat, text_color=COLOR_TEXT)
        self.lbl_status_val.pack(side="left")
        self.lbl_percent = ctk.CTkLabel(self.card_status, text="", font=self.font_code,
                                        text_color=COLOR_MUTED)
        self.lbl_percent.pack(anchor="w", padx=14)
        self.bar_status = ctk.CTkProgressBar(self.card_status, height=5,
                                             corner_radius=3,
                                             progress_color=COLOR_MUTED)
        self.bar_status.set(0)
        self.bar_status.pack(fill="x", padx=14, pady=(2, 12))

        # ── TARGET card ──
        self.card_target = ctk.CTkFrame(row, fg_color=COLOR_CARD, corner_radius=14)
        self.card_target.grid(row=0, column=1, padx=(8, 0), sticky="nsew")
        self._register_corners(self.card_target, "card")
        ctk.CTkLabel(self.card_target, text="TARGET", font=self.font_mini,
                     text_color=COLOR_MUTED).pack(anchor="w", padx=14, pady=(12, 0))
        self.lbl_target_val = ctk.CTkLabel(self.card_target, text="Window",
                                           font=self.font_stat, text_color=COLOR_TEXT)
        self.lbl_target_val.pack(anchor="w", padx=14)
        self.lbl_profile = ctk.CTkLabel(self.card_target, text="natural",
                                        font=self.font_code, text_color=COLOR_MUTED)
        self.lbl_profile.pack(anchor="w", padx=14)
        self.bar_target = ctk.CTkProgressBar(self.card_target, height=5,
                                             corner_radius=3,
                                             progress_color=COLOR_SECONDARY)
        self.bar_target.set(0)
        self.bar_target.pack(fill="x", padx=14, pady=(2, 12))

    def _build_input(self):
        ctk.CTkLabel(self, image=ctk_icon("doc", resolve(COLOR_MUTED),
                                          resolve(COLOR_MUTED), px=13),
                     text="  Input Text", compound="left",
                     font=self.font_mini,
                     text_color=COLOR_MUTED).grid(row=2, column=0, padx=24,
                                                  pady=(0, 5), sticky="w")

        self.text_area = ctk.CTkTextbox(self, height=self.input_h, border_width=0,
                                        fg_color=COLOR_CARD, text_color=COLOR_TEXT,
                                        font=self.font_code, corner_radius=14)
        self.text_area.grid(row=3, column=0, padx=22, pady=(0, 4), sticky="nsew")
        self._register_corners(self.text_area, "input")

        # Manual placeholder (CTkTextbox has no placeholder_text): cleared on
        # the first keypress/paste/focus, and rejected by validation if it
        # somehow survives - it must never be sent to the target window.
        self.text_area.insert("0.0", PLACEHOLDER)
        for evt in ("<Key>", "<<Paste>>", "<FocusIn>"):
            self.text_area.bind(evt, self._clear_placeholder, add="+")
        self.text_area.bind("<KeyRelease>", self._update_stats, add="+")

        self.lbl_stats = ctk.CTkLabel(self, text="", font=self.font_mini,
                                      text_color=COLOR_MUTED, anchor="w")
        self.lbl_stats.grid(row=4, column=0, padx=26, pady=(2, 0), sticky="w")

        self.lbl_warn = ctk.CTkLabel(self, text="", font=self.font_mini,
                                     text_color=COLOR_ERROR, wraplength=410,
                                     justify="left", anchor="w")
        self.lbl_warn.grid(row=5, column=0, padx=26, pady=(1, 0), sticky="w")

    def _build_controls(self):
        card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=14)
        card.grid(row=6, column=0, padx=22, pady=(10, 10), sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        self._register_corners(card, "card")

        # Speed
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=0, padx=16, pady=(14, 2), sticky="ew")
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, image=ctk_icon("bolt", resolve(COLOR_TEXT),
                                          resolve(COLOR_TEXT), px=16),
                     text="  Flow Speed", compound="left",
                     font=self.font_label,
                     text_color=COLOR_TEXT).grid(row=0, column=0, sticky="w")
        self.lbl_speed_val = ctk.CTkLabel(head, text=" 70 WPM ",
                                          font=self.font_code, text_color=COLOR_MUTED,
                                          fg_color=COLOR_TRACK, corner_radius=8)
        self.lbl_speed_val.grid(row=0, column=1, sticky="e")

        self.slider_speed = ctk.CTkSlider(card, from_=human_typer.MIN_WPM,
                                          to=human_typer.MAX_WPM,
                                          number_of_steps=(human_typer.MAX_WPM
                                                           - human_typer.MIN_WPM) // 5,
                                          button_color=COLOR_MUTED,
                                          button_hover_color=COLOR_TEXT,
                                          progress_color=COLOR_MUTED,
                                          fg_color=COLOR_TRACK)
        self.slider_speed.set(self.settings.get("wpm", 70))
        self.slider_speed.grid(row=1, column=0, padx=16, pady=(2, 12), sticky="ew")
        self.slider_speed.configure(command=self.update_speed_label)
        self._reg_accent_prog.append(self.slider_speed)

        # Variation
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=2, column=0, padx=16, pady=(0, 2), sticky="ew")
        head.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(head, image=ctk_icon("wave", resolve(COLOR_TEXT),
                                          resolve(COLOR_TEXT), px=16),
                     text="  Natural Variation", compound="left",
                     font=self.font_label,
                     text_color=COLOR_TEXT).grid(row=0, column=0, sticky="w")
        self.lbl_var_val = ctk.CTkLabel(head, text=" 6.0 % ",
                                        font=self.font_code, text_color=COLOR_MUTED,
                                        fg_color=COLOR_TRACK, corner_radius=8)
        self.lbl_var_val.grid(row=0, column=1, sticky="e")

        self.slider_var = ctk.CTkSlider(card, from_=0, to=0.20, number_of_steps=20,
                                        button_color=COLOR_MUTED,
                                        button_hover_color=COLOR_TEXT,
                                        progress_color=COLOR_MUTED,
                                        fg_color=COLOR_TRACK)
        self.slider_var.set(self.settings.get("error_rate", 0.06))
        self.slider_var.grid(row=3, column=0, padx=16, pady=(2, 12), sticky="ew")
        self.slider_var.configure(command=self.update_var_label)
        self._reg_accent_prog.append(self.slider_var)

        # Smart mode + hotkey chips on one row
        foot = ctk.CTkFrame(card, fg_color="transparent")
        foot.grid(row=4, column=0, padx=16, pady=(0, 14), sticky="ew")
        self.chk_indent = ctk.CTkSwitch(foot, text="Smart Mode",
                                        font=self.font_body, text_color=COLOR_TEXT,
                                        fg_color=COLOR_TRACK, progress_color=COLOR_MUTED,
                                        button_color=COLOR_MUTED,
                                        button_hover_color=COLOR_TEXT,
                                        command=self._save_settings)
        if self.settings.get("anti_indent", 0):
            self.chk_indent.select()
        self.chk_indent.pack(side="left")
        Tooltip(self.chk_indent, "Skip line-leading whitespace for IDE auto-indent")

        if _kb is not None:
            self.hk_chip = ctk.CTkButton(
                foot, text=f"Stop: {self.settings.get('stop_hotkey') or 'off'}",
                font=self.font_mini, height=26, corner_radius=13,
                fg_color=COLOR_CARD2, hover_color=COLOR_TRACK,
                text_color=COLOR_MUTED, command=self.toggle_settings)
            self.hk_chip.pack(side="right")
            Tooltip(self.hk_chip, "Change start/stop hotkeys in Settings")

    def _build_actions(self):
        # Full-width hero START (old design), PAUSE+STOP row appears when running
        self.btn_start = HoverButton(self, base=COLOR_MUTED, hover=COLOR_MUTED,
                                     pressed=COLOR_MUTED, height=58,
                                     corner_radius=29,
                                     font=ctk.CTkFont(size=16, weight="bold"),
                                     text="START SESSION",
                                     image=ctk_icon("play", "#FFFFFF", "#FFFFFF", px=16),
                                     command=self.start_typing_thread)
        self.btn_start.grid(row=7, column=0, padx=40, pady=(2, 4), sticky="ew")
        self._reg_accent_btn.append(self.btn_start)
        self._register_corners(self.btn_start, "btn")
        Tooltip(self.btn_start, "Type the text into the active window")

        self.btn_row = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_row.grid(row=8, column=0, padx=40, pady=(0, 4), sticky="ew")
        self.btn_row.grid_columnconfigure(0, weight=1)
        self.btn_row.grid_columnconfigure(1, weight=1)

        self.btn_pause = HoverButton(self.btn_row, base=NEUTRAL_BTN["base"],
                                     hover=NEUTRAL_BTN["hover"],
                                     pressed=NEUTRAL_BTN["pressed"],
                                     text_color=NEUTRAL_BTN["text"], height=52,
                                     corner_radius=26,
                                     font=ctk.CTkFont(size=13, weight="bold"),
                                     text="PAUSE", state="disabled",
                                     command=self.toggle_pause)
        self.btn_pause.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self._register_corners(self.btn_pause, "btn")
        Tooltip(self.btn_pause, "Suspend typing and resume later")

        self.btn_stop = HoverButton(self.btn_row, base=DANGER_BTN["base"],
                                    hover=DANGER_BTN["hover"],
                                    pressed=DANGER_BTN["pressed"],
                                    text_color=DANGER_BTN["text"], height=52,
                                    corner_radius=26,
                                    font=ctk.CTkFont(size=13, weight="bold"),
                                    text="STOP", state="disabled",
                                    command=self.stop_typing)
        self.btn_stop.grid(row=0, column=1, padx=(6, 0), sticky="ew")
        self._register_corners(self.btn_stop, "btn")
        Tooltip(self.btn_stop, "Abort the session immediately")

        # idle state: hero START only; PAUSE+STOP row appears while running
        self.btn_row.grid_remove()

    def _build_footer(self):
        self.lbl_footer = ctk.CTkLabel(self,
                                       image=ctk_icon("leaf", resolve(COLOR_MUTED),
                                                      resolve(COLOR_MUTED), px=11),
                                       text=f"  Natural Typing Environment  |  v{VERSION}",
                                       compound="left",
                                       font=self.font_mini, text_color=COLOR_MUTED)
        self.lbl_footer.grid(row=9, column=0, pady=(6, 14))

    # ════════════════════════════════════════════
    # Appearance system (theme / accent / corners)
    # ════════════════════════════════════════════

    def apply_appearance(self):
        pal = ACCENTS[self.current_accent]
        acc, hov, prs, txt = pal["base"], pal["hover"], pal["pressed"], pal["text"]

        for b in self._reg_accent_btn:
            b.set_palette(acc, hov, prs, text_color=txt)
        for w in self._reg_accent_fg:
            try:
                w.configure(fg_color=acc)
            except Exception:
                pass
        for w in self._reg_accent_prog:
            try:
                w.configure(progress_color=acc, button_color=acc,
                            button_hover_color=hov)
            except Exception:
                pass
        for w, kind in self._reg_corners:
            try:
                w.configure(corner_radius=self._round(kind))
            except Exception:
                pass
        try:
            self.chk_indent.configure(progress_color=acc, button_color=acc,
                                      button_hover_color=hov)
        except Exception:
            pass
        if not self._dot_pulsing:
            try:
                self.live_dot.configure(fg_color=acc)
            except Exception:
                pass
        self._refresh_theme_icon()
        try:
            self.lbl_profile.configure(text=self.settings.get("profile", "natural"))
        except Exception:
            pass

    def _refresh_theme_icon(self):
        icon = ctk_icon("moon" if self.theme_mode != "Dark" else "sun",
                        resolve(COLOR_MUTED), resolve(COLOR_MUTED), px=18)
        try:
            self.theme_btn.configure(image=icon)
        except Exception:
            pass

    def set_theme_value(self, mode):
        self.theme_mode = mode
        ctk.set_appearance_mode(mode)
        self.subtitle_label.configure(text="Forest Mode" if mode == "Dark" else "Natural Flow")
        self.lbl_footer.configure(
            text=f"  {'Deep Forest Environment' if mode == 'Dark' else 'Natural Typing Environment'}  |  v{VERSION}")
        self.apply_appearance()
        self._save_settings()

    def toggle_theme(self):
        self.set_theme_value("Dark" if self.theme_mode == "Light" else "Light")

    def set_accent(self, key):
        if key not in ACCENTS:
            return
        self.current_accent = key
        self.apply_appearance()
        self._save_settings()

    def set_corner_style(self, name):
        if name not in CORNER_STYLES:
            return
        self.corner_style = name
        self.apply_appearance()
        self._save_settings()

    def toggle_settings(self):
        if self.settings_dialog is not None and self.settings_dialog.winfo_exists():
            try:
                self.settings_dialog.grab_release()
            except Exception:
                pass
            self.settings_dialog.destroy()
            self.settings_dialog = None
            self.settings_visible = False
        else:
            self.settings_dialog = SettingsDialog(self)
            self.settings_visible = True

    # ════════════════════════════════════════════
    # Global hotkeys (Windows only; safe no-op elsewhere)
    # ════════════════════════════════════════════

    def apply_hotkeys(self):
        if _kb is None:
            return
        for name, job in list(self._hk_jobs.items()):
            try:
                _kb.remove_hotkey(job)
            except Exception:
                pass
            self._hk_jobs.pop(name, None)

        combos = {
            "start": normalize_combo(self.settings.get("start_hotkey", "")),
            "stop": normalize_combo(self.settings.get("stop_hotkey", "")),
        }
        callbacks = {"start": self._hotkey_start, "stop": self._hotkey_stop}
        for name, combo in combos.items():
            if not combo:
                continue
            try:
                # suppress=True keeps the combo away from the target app
                self._hk_jobs[name] = _kb.add_hotkey(combo, callbacks[name],
                                                     suppress=True)
            except Exception:
                self._hk_jobs.pop(name, None)  # bad combo / no permission
        if hasattr(self, "hk_chip"):
            try:
                self.hk_chip.configure(
                    text=f"Stop: {combos['stop'] or 'off'}")
            except Exception:
                pass

    def _hotkey_stop(self):
        # runs on the keyboard listener thread - marshal to the UI thread
        self.stop_event.set()
        self.pause_event.clear()
        self.ui(lambda: self.lbl_status_val.configure(text="Stopping...",
                                                      text_color=COLOR_ERROR))

    def _hotkey_start(self):
        self.ui(self.start_typing_thread)

    # ════════════════════════════════════════════
    # Settings persistence
    # ════════════════════════════════════════════

    def _load_settings(self):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                # Fresh installs (and configs written before hotkeys existed)
                # get the classic ctrl+q panic stop. An invalid value is a
                # legacy artifact, not user intent (the UI can only store
                # valid combos), so it falls back to the default too.
                if not normalize_combo(data.get("stop_hotkey", "")):
                    data["stop_hotkey"] = "ctrl+q"
                if not data.get("start_hotkey"):
                    data["start_hotkey"] = ""
                return data
        except (OSError, ValueError):
            pass
        return {"stop_hotkey": "ctrl+q", "start_hotkey": ""}

    def _save_settings(self, *_):
        self.settings = {
            "theme": getattr(self, "theme_mode", "Light"),
            "accent": getattr(self, "current_accent", "lime"),
            "corners": getattr(self, "corner_style", "Soft"),
            "profile": self.settings.get("profile", "natural"),
            "start_delay": self.settings.get("start_delay", 5),
            "start_hotkey": self.settings.get("start_hotkey", ""),
            "stop_hotkey": self.settings.get("stop_hotkey", "ctrl+q"),
            "wpm": int(self.slider_speed.get()) if hasattr(self, "slider_speed") else 70,
            "error_rate": float(self.slider_var.get()) if hasattr(self, "slider_var") else 0.06,
            "anti_indent": 1 if (hasattr(self, "chk_indent") and self.chk_indent.get()) else 0,
        }
        try:
            tmp = SETTINGS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
            os.replace(tmp, SETTINGS_FILE)
        except OSError:
            pass  # settings are a convenience, never fatal

    # ════════════════════════════════════════════
    # Input helpers
    # ════════════════════════════════════════════

    def _clear_placeholder(self, _event=None):
        try:
            current = self.text_area.get("0.0", "end").rstrip("\n")
        except Exception:
            return
        if current == PLACEHOLDER:
            self.text_area.delete("0.0", "end")

    def _effective_text(self):
        text = self.text_area.get("0.0", "end").rstrip("\n")
        if text == PLACEHOLDER:
            return ""
        return text

    def _update_stats(self, _event=None):
        text = self._effective_text()
        words = len(text.split())
        chars = len(text)
        wpm = max(1, int(self.slider_speed.get()))
        secs = int(words / wpm * 60) if words else 0
        eta = f"~{secs // 60}m {secs % 60:02d}s" if secs >= 60 else f"~{secs}s"
        self.lbl_stats.configure(text=f"{words} words  |  {chars} chars  |  {eta}")

        bad = human_typer.scan_untypeable(text)
        if bad:
            shown = bad if len(bad) <= 24 else bad[:24] + "..."
            self.lbl_warn.configure(text=f"Not typeable on this platform (will be skipped): {shown}")
        else:
            self.lbl_warn.configure(text="")

    def update_speed_label(self, value):
        self.lbl_speed_val.configure(text=f" {int(value)} WPM ")
        self._update_stats()

    def update_var_label(self, value):
        self.lbl_var_val.configure(text=f" {value*100:.1f} % ")

    # ════════════════════════════════════════════
    # UI plumbing
    # ════════════════════════════════════════════

    def ui(self, fn):
        """Schedule a UI update on the main thread (required on macOS).
        Guarded so a callback landing after window destruction is ignored
        instead of raising RuntimeError inside the typing thread."""
        if self._closing:
            return
        try:
            self.after(0, fn)
        except Exception:
            pass

    def _bar_to(self, widget, value, ms=260):
        """Tween a progress bar to a value (eased, cancelable per widget)."""
        start = widget.get()
        steps, step_ms = 12, max(1, ms // 12)
        state = {"cancel": False}
        self._bar_job[id(widget)] = state

        def run(i=0):
            if self._bar_job.get(id(widget)) is not state:
                return
            t = 1 - (1 - min(1.0, i / steps)) ** 3
            try:
                widget.set(start + (value - start) * t)
            except Exception:
                return
            if i < steps:
                self.after(step_ms, run, i + 1)

        self.after(0, run, 0)

    def _start_dot_pulse(self):
        if self._dot_pulsing:
            return
        self._dot_pulsing = True
        acc = resolve(ACCENTS[self.current_accent]["base"])
        trk = resolve(COLOR_MUTED)
        dot = self.live_dot

        def pulse(dark=False):
            if not self._dot_pulsing:
                return
            try:
                tween(dot, "fg_color", trk if dark else acc,
                      acc if dark else trk, ms=650, steps=10,
                      on_done=lambda: pulse(not dark))
            except Exception:
                pass

        pulse()

    def _stop_dot_pulse(self, solid=True):
        self._dot_pulsing = False
        try:
            color = resolve(ACCENTS[self.current_accent]["base"]) if solid else COLOR_MUTED
            self.live_dot.configure(fg_color=color)
        except Exception:
            pass

    # ════════════════════════════════════════════
    # Session control
    # ════════════════════════════════════════════

    def start_typing_thread(self):
        if self.typing_thread and self.typing_thread.is_alive():
            return

        # Pre-flight refresh so the stats line and any untypeable-character
        # warning reflect exactly what is about to be typed
        self._update_stats()

        text = self._effective_text()
        if not text.strip():
            self.lbl_status_val.configure(text="No Text!", text_color=COLOR_ERROR)
            return

        text = text.rstrip()
        wpm = int(self.slider_speed.get())
        errors = self.slider_var.get()
        delay = int(self.settings.get("start_delay", 5))
        suppress_indent = self.chk_indent.get()
        profile = self.settings.get("profile", "natural")

        # Update UI state
        self.stop_event.clear()
        self.pause_event.clear()
        self.paused = False
        self.btn_start.configure(state="disabled", text="RUNNING...")
        self.btn_pause.configure(state="normal", text="PAUSE")
        self.btn_stop.configure(state="normal")
        self.text_area.configure(state="disabled")
        self.lbl_status_val.configure(text="Initializing...", text_color=COLOR_TEXT)
        self.lbl_percent.configure(text="")
        self.bar_status.configure(progress_color=COLOR_SECONDARY)
        self._bar_to(self.bar_status, 0, ms=120)
        self._start_dot_pulse()
        if getattr(self, "btn_row", None) is not None:
            self.btn_row.grid()

        self.typing_thread = threading.Thread(
            target=self.run_typing,
            args=(text, wpm, errors, delay, suppress_indent, profile),
            daemon=True)
        self.typing_thread.start()

    def toggle_pause(self):
        if not (self.typing_thread and self.typing_thread.is_alive()):
            return
        self.paused = not self.paused
        if self.paused:
            self.pause_event.set()
            self.btn_pause.configure(text="RESUME")
            self.lbl_status_val.configure(text="Paused", text_color=COLOR_SECONDARY)
            self._stop_dot_pulse(solid=False)
        else:
            self.pause_event.clear()
            self.btn_pause.configure(text="PAUSE")
            self.lbl_status_val.configure(text="Injecting...", text_color=COLOR_TEXT)
            self._start_dot_pulse()

    def stop_typing(self):
        if self.typing_thread and self.typing_thread.is_alive():
            self.ui(lambda: self.lbl_status_val.configure(text="Stopping...",
                                                          text_color=COLOR_ERROR))
            self.pause_event.clear()  # release a paused loop so it can observe stop
            self.stop_event.set()

    def run_typing(self, text, wpm, errors, delay, suppress_indent, profile):
        outcome = "completed"
        summary = {"typed": 0, "skipped": 0, "skipped_chars": ""}

        # Countdown — all UI updates go through self.ui() for macOS thread safety
        try:
            for tick in range(1, delay + 1):
                if self.stop_event.is_set():
                    outcome = "aborted"
                    break
                human_typer._wait_if_paused(self.pause_event, self.stop_event)
                if self.stop_event.is_set():
                    outcome = "aborted"
                    break
                remaining = delay - tick + 1
                self.ui(lambda r=remaining, t=tick, d=delay: (
                    self.lbl_status_val.configure(text=f"Click Window: {r}s",
                                                  text_color=COLOR_SECONDARY),
                    self._bar_to(self.bar_target, t / d),
                ))
                time.sleep(1)

            if outcome == "completed":
                self.ui(lambda: (
                    self.lbl_status_val.configure(text="Injecting...", text_color=COLOR_TEXT),
                    self.bar_status.configure(progress_color=ACCENTS[self.current_accent]["base"]),
                    self._bar_to(self.bar_status, 0, ms=100),
                    self._bar_to(self.bar_target, 1.0, ms=200),
                ))

                def on_progress(done, total):
                    frac = done / total if total else 0
                    self.ui(lambda f=frac: (
                        self.lbl_percent.configure(text=f"{int(f*100)}%"),
                        self._bar_to(self.bar_status, f),
                    ))

                summary = human_typer.type_text(
                    text, wpm=wpm, error_rate=errors, start_delay=0,
                    stop_event=self.stop_event, suppress_indent=suppress_indent,
                    verbose=False, progress_callback=on_progress,
                    pause_event=self.pause_event, profile=profile)

                if self.stop_event.is_set():
                    outcome = "aborted"
        except FailSafeException:
            outcome = "failsafe"
        except Exception:
            import traceback
            traceback.print_exc()
            outcome = "error"

        # Cleanup runs no matter what happened above — START always comes back.
        is_stopped = self.stop_event.is_set()
        n_skipped = (summary or {}).get("skipped", 0)

        def final_text():
            if outcome == "aborted" or is_stopped:
                return "Aborted"
            if outcome == "failsafe":
                return "Aborted (mouse corner)"
            if outcome == "error":
                return "Error - see console"
            return f"Completed ({n_skipped} skipped)" if n_skipped else "Completed"

        def cleanup():
            self._stop_dot_pulse(solid=(outcome == "completed" and not is_stopped))
            self.lbl_status_val.configure(
                text=final_text(),
                text_color=COLOR_ERROR if outcome in ("aborted", "failsafe", "error") else COLOR_TEXT)
            self.lbl_percent.configure(text="")
            self.btn_row.grid_remove()
            self.btn_start.configure(state="normal", text="START SESSION")
            self.btn_pause.configure(state="disabled", text="PAUSE")
            self.btn_stop.configure(state="disabled")
            self.text_area.configure(state="normal")
            self._bar_to(self.bar_target, 0, ms=200)

        self.ui(cleanup)

    # ════════════════════════════════════════════
    # Shutdown
    # ════════════════════════════════════════════

    def _on_close(self):
        """Stop any running session before destroying the window, so the
        typing thread never touches a dead Tk interpreter. The main loop is
        pumped while joining because the thread's final ui() callbacks need
        it to progress (a plain join() would deadlock until timeout)."""
        self._closing = True
        self._dot_pulsing = False
        self.pause_event.clear()
        self.stop_event.set()
        t = self.typing_thread
        if t and t.is_alive():
            deadline = time.time() + 2.0
            while time.time() < deadline and t.is_alive():
                try:
                    self.update()
                except Exception:
                    break
                time.sleep(0.02)
        if self.settings_dialog is not None:
            try:
                self.settings_dialog.destroy()
            except Exception:
                pass
        if _kb is not None:
            for job in list(self._hk_jobs.values()):
                try:
                    _kb.remove_hotkey(job)
                except Exception:
                    pass
            self._hk_jobs.clear()
        self._save_settings()
        self.destroy()


if __name__ == "__main__":
    if IS_MACOS:
        # Suppress the deprecated Tk warning on macOS
        os.environ["TK_SILENCE_DEPRECATION"] = "1"
    app = HumanTyperApp()

    # Subtle fade-in on platforms that support window alpha (skip silently
    # on others - some Linux window managers lack it).
    try:
        app.attributes("-alpha", 0.0)

        def fade(i=1, steps=9):
            try:
                app.attributes("-alpha", i / steps)
            except Exception:
                return
            if i < steps:
                app.after(18, fade, i + 1)

        app.after(60, fade, 1)
    except Exception:
        try:
            app.attributes("-alpha", 1.0)
        except Exception:
            pass

    app.mainloop()
