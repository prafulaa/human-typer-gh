# -*- mode: python ; coding: utf-8 -*-
import re
import sys
from PyInstaller.utils.hooks import collect_all

# Single source of truth for the version: human_typer.py
with open('human_typer.py', 'r', encoding='utf-8') as _f:
    match = re.search(r'__version__ = "([^"]+)"', _f.read())
    VERSION = match.group(1) if match else "0.0.0"

datas = [('human_typer_icon.ico', '.'), ('human_typer_icon.icns', '.'), ('logo.png', '.')]
binaries = []
hiddenimports = []
if sys.platform == 'win32':
    hiddenimports.append('keyboard')  # global hotkeys (Windows only)
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['human_typer_gui.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='HumanTyper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file='entitlements.plist' if sys.platform == 'darwin' else None,
    icon=['human_typer_icon.ico'] if sys.platform != 'darwin' else ['human_typer_icon.icns'],
)

if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='Human Typer.app',
        icon='human_typer_icon.icns',
        bundle_identifier='com.prafulaa.humantyper',
        info_plist={
            'CFBundleShortVersionString': VERSION,
            'CFBundleVersion': '1',
            'NSPrincipalClass': 'NSApplication',
            'NSAppleScriptEnabled': False,
            'LSMinimumSystemVersion': '10.13',
            'NSHighResolutionCapable': True,
        },
    )
