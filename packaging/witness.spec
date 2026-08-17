# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir build for the WITNESS Qt desktop app.

Build this on Windows. PyInstaller is intentionally used in onedir mode: Inno
Setup owns installation/updating while the executable starts quickly and does
not need to unpack itself on every launch.
"""
from pathlib import Path

root = Path.cwd().resolve()
search_paths = [
    # Match qt_main.py runtime precedence. Keep the project root LAST so an
    # accidental legacy root-level db.py/data.py cannot shadow canonical
    # modules under shared/ during PyInstaller analysis.
    root / "insight",
    root / "_archive",
    root / "shared",
    root / "character",
    root / "core",
    root,
]

datas = [(str(root / "release_channel.json"), ".")]
sound_dir = root / "ui_qt" / "assets" / "sounds"
if sound_dir.exists():
    for wav in sound_dir.glob("*.wav"):
        datas.append((str(wav), "ui_qt/assets/sounds"))

character_dir = root / "ui_qt" / "assets" / "character"
if character_dir.exists():
    for image in character_dir.glob("*.png"):
        datas.append((str(image), "ui_qt/assets/character"))

# Qt starts the frozen Layer-1 active-window tracker plus the legacy ScreenVision
# guard through ui_qt/protection_runtime.py. Explicit multimedia/vision hidden
# imports keep embedded SOS playback and screenshot analysis reliable when frozen.
a = Analysis(
    [str(root / "qt_main.py")],
    pathex=[str(p) for p in search_paths],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "winsound", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
        "anthropic", "PIL.ImageGrab", "PIL.Image", "mss",
    ],
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
    [],
    exclude_binaries=True,
    name="WITNESS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="WITNESS",
)
