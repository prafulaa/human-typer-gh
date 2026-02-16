from PIL import Image, ImageDraw

def create_icon():
    # Natural Flow Theme Colors
    COLOR_PRIMARY = "#5D7052"  # Olive/Sage Green
    COLOR_BG = "#F2F4EC"       # Soft Cream
    
    size = (256, 256)
    image = Image.new("RGBA", size, (0, 0, 0, 0)) # Transparent background
    draw = ImageDraw.Draw(image)
    
    # Draw a stylized leaf shape
    # Simple leaf: Two quadratic curves meeting at tips
    
    # Background Circle (optional, maybe cleaner without)
    # let's do a soft rounded rect or circle background? 
    # User showed a rounded white icon in example.
    
    # Draw White Rounded Square Background
    rect_coords = [10, 10, 246, 246]
    draw.rounded_rectangle(rect_coords, radius=60, fill=COLOR_BG)
    
    # Draw Leaf
    # Leaf path... intricate for PIL basic draw. Let's do a simple organic shape.
    # Standard lanceolate leaf shape
    # Start bottom center, curve out left, meet top, curve out right, back bottom.
    
    center_x, center_y = 128, 128
    
    # Leaf coords
    leaf_color = COLOR_PRIMARY
    
    # Simple leaf using polygon/chord logic is tricky.
    # Let's draw an ellipse and rotate it?
    # Ellipse 1
    # overlay a rotated ellipse to form a leaf shape intersection?
    
    # Easier: Draw a simple teardrop shape.
    # Circle at bottom, triangle at top? No.
    
    # Let's draw a standard "Typewriter + Leaf" idea?
    # Just a nice big Sage Green Leaf.
    
    # Drawing a leaf using pieslice/arc
    # An easy way to draw a leaf is intersection of two circles.
    
    # Left circle
    # draw.pieslice(...)
    
    # Let's just draw a "H" inside a circle for Human Typer?
    # User wanted "matches the theme".
    # Theme is nature.
    # Let's draw a green circle with a white "H" and a small leaf.
    
    # Green Circle
    margin = 20
    draw.ellipse([margin, margin, 256-margin, 256-margin], fill=COLOR_PRIMARY)
    
    # White "H" text
    try:
        # Standard PIL font handling is annoying without .ttf files. 
        # fallback to drawing shapes.
        pass
    except:
        pass
        
    # Draw a stylized "cursor" (underscore)
    cursor_w = 120
    cursor_h = 20
    cursor_x = (256 - cursor_w) // 2
    cursor_y = 160
    draw.rectangle([cursor_x, cursor_y, cursor_x+cursor_w, cursor_y+cursor_h], fill="white")
    
    # Draw two dots for eyes? Making it a "face"?
    # No, keep it abstract.
    
    # Draw a leaf shape above cursor
    # (Ellipse rotated 45 deg)
    # Using a simple polygon for a diamond/leaf shape
    leaf_pts = [
        (128, 60),  # Top
        (180, 120), # Right
        (128, 140), # Bottom
        (76, 120)   # Left
    ]
    draw.polygon(leaf_pts, fill="white")
    
    # Save as ICO
    image.save("human_typer_icon.ico", format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("Icon created successfully.")

if __name__ == "__main__":
    try:
        create_icon()
    except ImportError:
        print("PIL not installed. Please install pillow.")
