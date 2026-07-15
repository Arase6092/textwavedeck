# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


project_root = Path.cwd()
block_cipher = None

datas = [
    (str(project_root / "README.md"), "."),
    (str(project_root / "README.zh-CN.md"), "."),
    (str(project_root / "LICENSE"), "."),
]

resources_dir = project_root / "resources"
if resources_dir.exists():
    datas.append((str(resources_dir), "resources"))

datas += copy_metadata("mediapipe")
datas += collect_data_files("mediapipe")
datas += collect_data_files("cv2")

hiddenimports = [
    "pythoncom",
    "pywintypes",
    "win32com",
    "win32com.client",
    "win32com.server",
    "win32timezone",
]
hiddenimports += collect_submodules("mediapipe")

excludes = [
    "matplotlib",
    "tkinter",
    "pytest",
    "setuptools",
    "IPython",
    "jedi",
]

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
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
    name="WaveDeck",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "resources" / "branding" / "wavedeck.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="WaveDeck",
)
