# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Opti (Windows). Run from repo root: pyinstaller packaging/opti.spec"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

block_cipher = None
ROOT = Path(SPECPATH).parent

pyqt_datas, pyqt_binaries, pyqt_hiddenimports = collect_all("PyQt6")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=pyqt_binaries,
    datas=[
        (str(ROOT / "config.example.json"), "."),
        *pyqt_datas,
    ],
    hiddenimports=[
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "google.genai",
        "anthropic",
        "openai",
        "PIL",
        "pystray",
        "pystray._win32",
        "win32timezone",
        *pyqt_hiddenimports,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "packaging" / "pyi_rth_qt.py")],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Opti",
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Opti",
)
