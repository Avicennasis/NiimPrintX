# -*- mode: python ; coding: utf-8 -*-
import os
import subprocess
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('PIL') + collect_submodules('tkinter') + collect_submodules('bleak') + collect_submodules('wand') + ['platformdirs', 'sv_ttk', 'cairo']


# Function to get the ImageMagick installation path using brew and resolve the symlink
def get_imagemagick_path():
    try:
        result = subprocess.run(['brew', '--prefix', 'imagemagick'], capture_output=True, text=True)
        result.check_returncode()
        symlink_path = result.stdout.strip()
        real_path = os.path.realpath(symlink_path)
        return real_path
    except subprocess.CalledProcessError:
        raise RuntimeError("ImageMagick is not installed via brew or brew command is not found.")


# Function to collect files and adjust their target directory
def collect_and_adjust_files(base_path, target_dir):
    collected_files = []
    for root, _, files in os.walk(base_path):
        for file in files:
            full_path = os.path.join(root, file)
            # We only need the relative path without the filename
            rel_path = os.path.relpath(root, base_path)
            target_path = os.path.join(target_dir, rel_path)
            collected_files.append((full_path, target_path))
    return collected_files


# Get the ImageMagick installation path dynamically and resolve symlink
imagemagick_path = get_imagemagick_path()

# Collect the ImageMagick binaries and libraries and specify the target directory
datas = collect_and_adjust_files(imagemagick_path, 'imagemagick')

current_path = os.getcwd()
if os.path.basename(current_path) == "ui_app":
    src_path = os.path.join(current_path, '..', '..', 'NiimPrintX', 'ui')
elif os.path.basename(current_path) == "NiimPrintX":
    src_path = os.path.join(current_path, 'NiimPrintX', 'ui')
else:
    src_path = os.path.join(current_path, 'ui')

# Add custom assets
datas += [
    (os.path.join(src_path, 'icons'), 'NiimPrintX/ui/icons'),
    (os.path.join(src_path, 'assets'), 'NiimPrintX/ui/assets')
]

a = Analysis(
    [os.path.join(src_path, '__main__.py')],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=['tkinter'] + hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],  # runtime hook removed — load_libraries() in __main__.py handles env setup
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,  # TODO: set to entitlements.plist when code signing is configured (needed for Bluetooth TCC approval)
    icon=os.path.join(src_path, 'assets', 'icon.icns'),
    onefile=False,  # Ensure this is set for onefile build
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

app = BUNDLE(
    coll,
    name='NiimPrintX.app',
    icon=os.path.join(src_path, 'assets', 'icon.icns'),
    bundle_identifier="com.niimprintx.app",
    info_plist={
        'NSBluetoothAlwaysUsageDescription': 'NiimPrintX requires Bluetooth to communicate with Niimbot printers.',
        'NSBluetoothPeripheralUsageDescription': 'NiimPrintX requires Bluetooth to communicate with Niimbot printers.',
    },
)
