# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir build for the WITNESS Qt desktop app.

Build this on Windows. PyInstaller is intentionally used in onedir mode: Inno
Setup owns installation/updating while the executable starts quickly and does
not need to unpack itself on every launch.
"""
from pathlib import Path

root = Path.cwd().resolve()
search_paths = [
    root,
    root / "shared",
    root / "character",
    root / "core",
    root / "_archive",
    root / "insight",
]

datas = [(str(root / "release_channel.json"), ".")]
sound_dir = root / "ui_qt" / "assets" / "sounds"
if sound_dir.exists():
    for wav in sound_dir.glob("*.wav"):
        datas.append((str(wav), "ui_qt/assets/sounds"))

# The current Qt shell intentionally does not start the legacy Layer-1 runtime,
# so only modules reachable from qt_main.py are bundled. The source remains in
# the repo for the upcoming runtime-integration pass.
a = Analysis(
    [str(root / "qt_main.py")],
    pathex=[str(p) for p in search_paths],
    binaries=[],
    datas=datas,
    hiddenimports=["winsound"],
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
