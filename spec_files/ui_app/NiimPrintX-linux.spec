# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

spec_dir = SPECPATH  # PyInstaller built-in: directory containing this .spec file
repo_root = os.path.normpath(os.path.join(spec_dir, '..', '..'))
src_path = os.path.join(repo_root, 'NiimPrintX', 'ui')

# Add custom assets
datas = [
    (os.path.join(src_path, 'icons'), 'NiimPrintX/ui/icons'),
    (os.path.join(src_path, 'assets'), 'NiimPrintX/ui/assets'),
    ('/etc/ImageMagick-6', 'imagemagick/config'),
]

# ImageMagick shared libraries required by wand at runtime
import glob
_im_libs = glob.glob('/usr/lib/x86_64-linux-gnu/libMagick*.so*')
_im_binaries = [(lib, '.') for lib in _im_libs]

# Include all submodules from PIL, tkinter, bleak, and wand
hidden_imports = collect_submodules('PIL')
hidden_imports += collect_submodules('tkinter')
hidden_imports += collect_submodules('bleak')
hidden_imports += collect_submodules('wand')
hidden_imports += ['tkinter'] + ['platformdirs', 'sv_ttk', 'cairo']  # collect_submodules omits the top-level package; add explicitly

# NOTE: Manual Tcl/Tk path resolution — PyInstaller's built-in tkinter hook
# handles this for one-dir builds. If converting to one-dir, remove this block
# and rely on collect_data_files('tkinter') instead.
import tkinter
_tcl = tkinter.Tcl()
tcl_library = os.environ.get('TCL_LIBRARY') or _tcl.eval('info library')
tk_library = os.environ.get('TK_LIBRARY') or os.path.join(os.path.dirname(tcl_library), f'tk{_tcl.eval("info patchlevel").rsplit(".", 1)[0]}')
if not os.path.isdir(tk_library):
    raise RuntimeError(f"Derived Tk library path {tk_library!r} does not exist. Set TK_LIBRARY env var.")

datas += [
    (tcl_library, 'tcl'),
    (tk_library, 'tk')
]

a = Analysis(
    [os.path.join(src_path, '__main__.py')],
    pathex=['.'],
    binaries=_im_binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[os.path.join(spec_dir, 'runtime_hook_imagemagick.py')],
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
    name='NiimPrintX',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(src_path, 'assets', 'nimx-512.png'),  # NOTE: icon= is ignored by PyInstaller on Linux; set icon via .desktop file
)
