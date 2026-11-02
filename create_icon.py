"""Regenerates the app icons (human_typer_icon.ico / .icns) with Pillow.

Run after changing any of the drawing code below:
    python create_icon.py
"""
from PIL import Image, ImageDraw


def create_icon():
    # Natural Flow theme colors
    color_primary = "#5D7052"  # Olive/Sage Green
    color_bg = "#F2F4EC"       # Soft Cream

    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Soft rounded-square background
    draw.rounded_rectangle([10, 10, 246, 246], radius=60, fill=color_bg)

    # Green circle
    margin = 20
    draw.ellipse([margin, margin, 256 - margin, 256 - margin], fill=color_primary)

    # Stylized leaf (diamond) above a typing cursor (underscore bar)
    leaf_pts = [
        (128, 60),   # top
        (180, 120),  # right
        (128, 140),  # bottom
        (76, 120),   # left
    ]
    draw.polygon(leaf_pts, fill="white")

    cursor_w, cursor_h = 120, 20
    cursor_x = (256 - cursor_w) // 2
    cursor_y = 160
    draw.rectangle([cursor_x, cursor_y, cursor_x + cursor_w, cursor_y + cursor_h],
                   fill="white")

    # Save as ICO (Windows) and ICNS (macOS)
    image.save("human_typer_icon.ico", format="ICO",
               sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    image.save("human_typer_icon.icns", format="ICNS")

    print("Icons created successfully (.ico and .icns).")


if __name__ == "__main__":
    try:
        create_icon()
    except ImportError:
        print("PIL not installed. Please install pillow.")
