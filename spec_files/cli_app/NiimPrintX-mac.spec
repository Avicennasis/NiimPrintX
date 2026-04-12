# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

current_path = os.getcwd()
if os.path.basename(current_path) == "cli_app":
    src_path = os.path.join(current_path, '..', '..', 'NiimPrintX', 'cli')
elif os.path.basename(current_path) == "NiimPrintX":
    src_path = os.path.join(current_path, 'NiimPrintX', 'cli')
else:
    src_path = os.path.join(current_path, 'cli')

a = Analysis(
    [os.path.join(src_path, '__main__.py')],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['click', 'loguru', 'rich', 'platformdirs'] + collect_submodules('PIL') + collect_submodules('bleak'),
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
    entitlements_file=None,
)
