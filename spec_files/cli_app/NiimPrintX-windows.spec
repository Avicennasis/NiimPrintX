# -*- mode: python ; coding: utf-8 -*-
import os

# Determine the current path and the source path for the CLI application
current_path = os.getcwd()
if os.path.basename(current_path) == "cli_app":
    src_path = os.path.join(current_path, '..', '..', 'NiimPrintX', 'cli')
elif os.path.basename(current_path) == "NiimPrintX":
    src_path = os.path.join(current_path, 'NiimPrintX', 'cli')
else:
    src_path = os.path.join(current_path, 'cli')

# Analysis step
a = Analysis(
    [os.path.join(src_path, '__main__.py')],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
    strip=True,
)

# PYZ step
pyz = PYZ(a.pure)

# EXE step (one-file build)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='niimprintx',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add path to .ico file if you have an icon
)
