"""UI kit for Human Typer - icons, animation helpers, and small custom
widgets built on CustomTkinter.

Everything here is UI-only: no typing logic, no pyautogui.

Design rules honored by this module:
- Icons are drawn with PIL at 4x and downsampled (crisp on HiDPI), never
  emoji glyphs (emoji crash CoreText on macOS Sonoma + Tk 8.6).
- Colors are (light, dark) tuples resolved against the current appearance
  mode at draw/configure time.
- Animations are after()-based tweens; CTk has no native animation.
"""
import math
import customtkinter as ctk
from PIL import Image, ImageDraw

# ──────────────────────────────────────────────
# Color helpers
# ──────────────────────────────────────────────

def resolve(color):
    """Pick the light/dark half of a tuple for the current appearance mode."""
    if isinstance(color, (tuple, list)):
        return color[1] if ctk.get_appearance_mode().lower() == "dark" else color[0]
    return color


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#%02x%02x%02x" % rgb


def mix(c1, c2, t):
    """Linear blend between two hex colors, t in [0, 1]."""
    a, b = _hex_to_rgb(c1), _hex_to_rgb(c2)
    return _rgb_to_hex(tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)))


def ease_out(t):
    """Cubic ease-out: fast start, gentle landing."""
    return 1 - (1 - t) ** 3


# ──────────────────────────────────────────────
# Tween animation (after()-based; CTk has none native)
# ──────────────────────────────────────────────

_tween_jobs = {}  # (id(widget), attr) -> cancel flag holder


def tween(widget, attr, start_hex, end_hex, ms=140, steps=8, on_done=None):
    """Animate a color attribute of a CTk widget from start to end hex.

    Starting a new tween for the same widget+attr cancels the previous one.
    Safe to call from the main thread only (same rule as any Tk access).
    """
    key = (id(widget), attr)
    _tween_jobs[key] = {"cancel": True}

    state = {"cancel": False}
    _tween_jobs[key] = state
    step_ms = max(1, int(ms / steps))

    def run(i=0):
        if state["cancel"] or not i < steps + 1:
            return
        try:
            t = ease_out(min(1.0, i / steps))
            widget.configure(**{attr: mix(start_hex, end_hex, t)})
        except Exception:
            return  # widget destroyed mid-tween
        if i == steps:
            if on_done:
                on_done()
            return
        widget.after(step_ms, run, i + 1)

    widget.after(0, run, 0)


def tween_value(widget, attr, start, end, ms=240, steps=12, on_done=None):
    """Animate a numeric attribute (e.g. CTkProgressBar.set) with easing."""
    key = (id(widget), attr)
    state = {"cancel": False}
    _tween_jobs[key] = {"cancel": True}
    _tween_jobs[key] = state
    step_ms = max(1, int(ms / steps))

    def run(i=0):
        if state["cancel"]:
            return
        t = ease_out(min(1.0, i / steps))
        try:
            widget.configure(**{attr: start + (end - start) * t})
        except Exception:
            return
        if i == steps:
            if on_done:
                on_done()
            return
        widget.after(step_ms, run, i + 1)

    widget.after(0, run, 0)


# ──────────────────────────────────────────────
# Animated-hover button
# ──────────────────────────────────────────────

class HoverButton(ctk.CTkButton):
    """CTkButton with an animated (tweened) hover and press effect instead
    of CTk's instant hover_color jump.

    Palette is set with set_palette(base, hover, pressed, text) - each a
    (light, dark) tuple or plain hex.
    """

    def __init__(self, master, base, hover, pressed, text_color="#FFFFFF", **kw):
        kw.setdefault("hover", False)  # CTk's instant hover off; we animate
        super().__init__(master, fg_color=base, text_color=text_color, **kw)
        self._pal = {"base": base, "hover": hover, "pressed": pressed}
        self._hovering = False
        self._pressed = False
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")
        self.bind("<Button-1>", self._on_press, add="+")
        self.bind("<ButtonRelease-1>", self._on_release, add="+")

    def set_palette(self, base, hover, pressed, text_color=None):
        self._pal = {"base": base, "hover": hover, "pressed": pressed}
        if text_color is not None:
            self.configure(text_color=text_color)
        target = self._current_target()
        try:
            self.configure(fg_color=target)
        except Exception:
            pass

    def _current_target(self):
        if self._pressed:
            return resolve(self._pal["pressed"])
        if self._hovering:
            return resolve(self._pal["hover"])
        return resolve(self._pal["base"])

    def _apply_animated(self):
        try:
            current = resolve(self.cget("fg_color"))
        except Exception:
            return
        tween(self, "fg_color", current, self._current_target(), ms=130, steps=7)

    def _on_enter(self, _):
        if str(self.cget("state")) != "disabled":
            self._hovering = True
            self._apply_animated()

    def _on_leave(self, _):
        self._hovering = False
        self._pressed = False
        self._apply_animated()

    def _on_press(self, _):
        self._pressed = True
        self._apply_animated()

    def _on_release(self, _):
        self._pressed = False
        self._apply_animated()


# ──────────────────────────────────────────────
# Tooltip (no external dependency)
# ──────────────────────────────────────────────

class Tooltip:
    """Small hover tooltip for any widget. ASCII text only (macOS rule).

    Deliberately uses a plain tk.Toplevel, not CTkToplevel: CTk's toplevel
    does an internal withdraw/deiconify dance for titlebar colors that
    breaks noisily when the tooltip is destroyed quickly.
    """

    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._tip = None
        self._job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _=None):
        self._cancel()
        self._job = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _show(self):
        if self._tip is not None or not self.text:
            return
        try:
            if not self.widget.winfo_exists():
                return
            x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2)
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        except Exception:
            return
        import tkinter as tk
        from tkinter import font as tkfont
        self._tip = tk.Toplevel(self.widget)
        self._tip.withdraw()
        self._tip.overrideredirect(True)
        try:
            self._tip.attributes("-topmost", True)
        except Exception:
            pass
        base_font = tkfont.nametofont("TkDefaultFont")
        tiny = base_font.copy()
        tiny.configure(size=9)
        tk.Label(self._tip, text=self.text, font=tiny,
                 background="#1F2429", foreground="#E8ECE8",
                 padx=10, pady=5, borderwidth=0).pack()
        self._tip.update_idletasks()
        w = self._tip.winfo_reqwidth()
        self._tip.geometry(f"+{max(0, x - w // 2)}+{y}")
        self._tip.deiconify()

    def _hide(self, _=None):
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


# ──────────────────────────────────────────────
# Icon rendering (PIL, 4x supersampled)
# ──────────────────────────────────────────────

def _new_layer(px, scale):
    size = px * scale
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), size


def _punch_hole(img, cx, cy, r):
    """Make a circular area transparent (for gear/moon shapes)."""
    alpha = img.split()[3]
    mask = ImageDraw.Draw(alpha)
    mask.ellipse([cx - r, cy - r, cx + r, cy + r], fill=0)
    img.putalpha(alpha)
    return img


def _finish(img, px):
    return img.resize((px, px), Image.LANCZOS)


def _icon_play(color, px, scale):
    img, d, s = _new_layer(px, scale)
    m = s * 0.22
    d.polygon([(m, m), (s - m, s / 2), (m, s - m)], fill=color)
    return _finish(img, px)


def _icon_pause(color, px, scale):
    img, d, s = _new_layer(px, scale)
    m, w, r = s * 0.24, s * 0.14, s * 0.06
    d.rounded_rectangle([m, m, m + w, s - m], radius=r, fill=color)
    d.rounded_rectangle([s - m - w, m, s - m, s - m], radius=r, fill=color)
    return _finish(img, px)


def _icon_stop(color, px, scale):
    img, d, s = _new_layer(px, scale)
    m = s * 0.26
    d.rounded_rectangle([m, m, s - m, s - m], radius=s * 0.12, fill=color)
    return _finish(img, px)


def _icon_gear(color, px, scale):
    img, d, s = _new_layer(px, scale)
    c = s / 2
    R = s * 0.30
    d.ellipse([c - R, c - R, c + R, c + R], fill=color)
    for k in range(8):
        a = k * math.pi / 4
        tx, ty = c + math.cos(a) * s * 0.38, c + math.sin(a) * s * 0.38
        tr = s * 0.085
        d.ellipse([tx - tr, ty - tr, tx + tr, ty + tr], fill=color)
    img = _punch_hole(img, c, c, s * 0.13)
    return _finish(img, px)


def _icon_sun(color, px, scale):
    img, d, s = _new_layer(px, scale)
    c = s / 2
    R = s * 0.22
    d.ellipse([c - R, c - R, c + R, c + R], fill=color)
    for k in range(8):
        a = k * math.pi / 4
        x1, y1 = c + math.cos(a) * s * 0.32, c + math.sin(a) * s * 0.32
        x2, y2 = c + math.cos(a) * s * 0.44, c + math.sin(a) * s * 0.44
        d.line([x1, y1, x2, y2], fill=color, width=int(s * 0.055))
    return _finish(img, px)


def _icon_moon(color, px, scale):
    img, d, s = _new_layer(px, scale)
    c = s / 2
    R = s * 0.34
    d.ellipse([c - R, c - R, c + R, c + R], fill=color)
    img = _punch_hole(img, c + s * 0.22, c - s * 0.10, s * 0.28)
    return _finish(img, px)


def _icon_leaf(color, px, scale):
    img, d, s = _new_layer(px, scale)
    m = s * 0.20
    d.ellipse([m, m, s - m, s - m], fill=color)
    d.line([s * 0.30, s * 0.70, s * 0.70, s * 0.30],
           fill=(0, 0, 0, 0), width=int(s * 0.05))
    img = img.rotate(-35, resample=Image.BICUBIC)
    return _finish(img, px)


def _icon_doc(color, px, scale):
    img, d, s = _new_layer(px, scale)
    m, r = s * 0.24, s * 0.10
    d.rounded_rectangle([m, m, s - m, s - m], radius=r, outline=color,
                        width=int(s * 0.075))
    for i, yy in enumerate((0.38, 0.52, 0.66)):
        x_end = (s - m) if i == 2 else (s - m - s * 0.14)
        d.line([s * 0.36, s * yy, x_end, s * yy], fill=color,
               width=int(s * 0.055))
    return _finish(img, px)


def _icon_bolt(color, px, scale):
    img, d, s = _new_layer(px, scale)
    # classic lightning bolt
    pts = [(s * 0.55, s * 0.08), (s * 0.25, s * 0.55), (s * 0.45, s * 0.55),
           (s * 0.38, s * 0.92), (s * 0.75, s * 0.42), (s * 0.52, s * 0.42)]
    d.polygon(pts, fill=color)
    return _finish(img, px)


def _icon_wave(color, px, scale):
    img, d, s = _new_layer(px, scale)
    w = int(s * 0.07)
    for offset in (0.22, 0.50, 0.78):
        pts = []
        for k in range(13):
            x = s * (0.10 + 0.80 * k / 12)
            y = s * (offset + 0.10 * math.sin(k * math.pi / 3 + offset * 9))
            pts.append((x, y))
        d.line(pts, fill=color, width=w, joint="curve")
    return _finish(img, px)


def _icon_target(color, px, scale):
    img, d, s = _new_layer(px, scale)
    c = s / 2
    for r in (0.40, 0.24):
        d.ellipse([c - s * r, c - s * r, c + s * r, c + s * r],
                  outline=color, width=int(s * 0.06))
    d.ellipse([c - s * 0.07, c - s * 0.07, c + s * 0.07, c + s * 0.07],
              fill=color)
    # crosshair ticks
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        x1, y1 = c + dx * s * 0.44, c + dy * s * 0.44
        x2, y2 = c + dx * s * 0.30, c + dy * s * 0.30
        d.line([x1, y1, x2, y2], fill=color, width=int(s * 0.055))
    return _finish(img, px)


def _icon_tree(color, px, scale):
    img, d, s = _new_layer(px, scale)
    # pine: three stacked triangles + trunk
    for k, (top, half) in enumerate(((0.08, 0.30), (0.30, 0.38), (0.52, 0.46))):
        d.polygon([(s / 2, s * top), (s / 2 - s * half, s * (top + 0.26)),
                   (s / 2 + s * half, s * (top + 0.26))], fill=color)
    d.rectangle([s * 0.44, s * 0.76, s * 0.56, s * 0.92], fill=color)
    return _finish(img, px)


def _icon_keyboard(color, px, scale):
    img, d, s = _new_layer(px, scale)
    m, r = s * 0.08, s * 0.12
    d.rounded_rectangle([m, s * 0.24, s - m, s * 0.76], radius=r,
                        outline=color, width=int(s * 0.055))
    kw = (s - 2 * m - s * 0.10) / 8
    for row in range(2):
        y = s * (0.36 + 0.14 * row)
        for col in range(8):
            x = m + s * 0.05 + col * kw
            d.ellipse([x - s * 0.02, y - s * 0.02, x + s * 0.02, y + s * 0.02],
                      fill=color)
    d.line([s * 0.38, s * 0.64, s * 0.62, s * 0.64], fill=color,
           width=int(s * 0.05))
    return _finish(img, px)


def _icon_refresh(color, px, scale):
    img, d, s = _new_layer(px, scale)
    c = s / 2
    d.arc([c - s * 0.34, c - s * 0.34, c + s * 0.34, c + s * 0.34],
          start=-60, end=200, fill=color, width=int(s * 0.07))
    # arrowhead at the arc's end
    d.polygon([(c + s * 0.20, c - s * 0.36), (c + s * 0.40, c - s * 0.22),
               (c + s * 0.16, c - s * 0.12)], fill=color)
    return _finish(img, px)


_RENDERERS = {
    "play": _icon_play, "pause": _icon_pause, "stop": _icon_stop,
    "gear": _icon_gear, "sun": _icon_sun, "moon": _icon_moon,
    "leaf": _icon_leaf, "doc": _icon_doc,
    "bolt": _icon_bolt, "wave": _icon_wave, "target": _icon_target,
    "tree": _icon_tree, "keyboard": _icon_keyboard, "refresh": _icon_refresh,
}


def ctk_icon(name, light_hex, dark_hex=None, px=20):
    """Render an icon as a CTkImage with light/dark variants."""
    if dark_hex is None:
        dark_hex = light_hex
    return ctk.CTkImage(
        light_image=_RENDERERS[name](light_hex, px * 4, 4),
        dark_image=_RENDERERS[name](dark_hex, px * 4, 4),
        size=(px, px),
    )
