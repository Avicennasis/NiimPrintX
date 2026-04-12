# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

spec_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.normpath(os.path.join(spec_dir, '..', '..'))
src_path = os.path.join(repo_root, 'NiimPrintX', 'cli')

a = Analysis(
    [os.path.join(src_path, '__main__.py')],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['click', 'loguru', 'rich', 'platformdirs'] + collect_submodules('PIL') + collect_submodules('bleak'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', '_tkinter', 'PIL.ImageTk', 'wand', 'sv_ttk', 'cairo'],
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
    name='niimprintx',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=os.path.join(repo_root, 'entitlements.plist'),  # Bluetooth TCC; requires codesign_identity
)
