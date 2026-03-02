#!/bin/bash
# ============================================
# Human Typer - macOS Build Script
# Builds a .app bundle and optional .dmg
# ============================================
set -e

echo "=== Human Typer macOS Build ==="
echo ""

# 1. Install dependencies
echo "[1/4] Installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install pyinstaller

# 2. Clean previous builds
echo "[2/4] Cleaning previous builds..."
rm -rf build dist

# 3. Build the .app bundle using the spec file
echo "[3/4] Building Human Typer.app..."
python3 -m PyInstaller HumanTyper.spec --noconfirm

echo ""
echo "=== Build Complete ==="
echo "Your app is at: dist/Human Typer.app"
echo ""

# 4. Optional: Create a .dmg installer
read -p "Create a .dmg installer? (y/n): " CREATE_DMG
if [ "$CREATE_DMG" = "y" ] || [ "$CREATE_DMG" = "Y" ]; then
    echo "[4/4] Creating DMG..."
    
    DMG_NAME="HumanTyper-macOS.dmg"
    DMG_DIR="dmg_temp"
    
    rm -rf "$DMG_DIR" "$DMG_NAME"
    mkdir -p "$DMG_DIR"
    
    # Copy the .app into the temp dir
    cp -R "dist/Human Typer.app" "$DMG_DIR/"
    
    # Create a symlink to /Applications for drag-and-drop install
    ln -s /Applications "$DMG_DIR/Applications"
    
    # Create the DMG
    hdiutil create -volname "Human Typer" \
        -srcfolder "$DMG_DIR" \
        -ov -format UDZO \
        "$DMG_NAME"
    
    rm -rf "$DMG_DIR"
    
    echo ""
    echo "=== DMG Created: $DMG_NAME ==="
fi

echo ""
echo "Done! To run: open \"dist/Human Typer.app\""
