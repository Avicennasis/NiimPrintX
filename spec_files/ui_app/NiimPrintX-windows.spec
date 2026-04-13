# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

# Spec-relative paths
spec_dir = SPECPATH  # PyInstaller built-in: directory containing this .spec file
repo_root = os.path.normpath(os.path.join(spec_dir, '..', '..'))
src_path = os.path.join(repo_root, 'NiimPrintX', 'ui')

# Path to the extracted ImageMagick directory
imagemagick_path = os.path.join(repo_root, 'resources', 'ImageMagick')
if not os.path.isdir(imagemagick_path):
    raise RuntimeError(
        f"ImageMagick not found at {imagemagick_path}. "
        "Extract the portable ImageMagick build to resources/ImageMagick/ first."
    )

# Collect ImageMagick files, splitting binaries from data
imagemagick_binaries = []
imagemagick_datas = []

for root, _, files in os.walk(imagemagick_path):
    for f in files:
        full_path = os.path.join(root, f)
        rel_path = os.path.relpath(root, imagemagick_path)
        target_path = os.path.join('imagemagick', rel_path)
        if f.endswith(('.dll', '.exe')):
            imagemagick_binaries.append((full_path, target_path))
        else:
            imagemagick_datas.append((full_path, target_path))

datas = imagemagick_datas

# Include all submodules from PIL, tkinter, bleak, and wand
hiddenimports = collect_submodules('PIL')
hiddenimports += collect_submodules('tkinter')
hiddenimports += collect_submodules('bleak')
hiddenimports += collect_submodules('wand')
hiddenimports += ['platformdirs', 'sv_ttk', 'cairo']

# Add custom assets
datas += [
    (os.path.join(src_path, 'icons'), 'NiimPrintX/ui/icons'),
    (os.path.join(src_path, 'assets'), 'NiimPrintX/ui/assets')
]


a = Analysis(
    [os.path.join(src_path, '__main__.py')],
    pathex=['.'],
    binaries=imagemagick_binaries,
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
    [],
    exclude_binaries=True,
    name='NiimPrintX',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # Set to False for a GUI application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(src_path, 'assets', 'icon.ico'),  # Use .ico for Windows
    onefile=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='NiimPrintX',
)
