import os
import sys
import shutil
from pathlib import Path

def extract_bundled_files():
    # Path to the temporary directory where PyInstaller extracts bundled files
    temp_dir = sys._MEIPASS

    # Destination directory for the extracted files
    dest_dir = Path.home() / '.NiimPrintX_bundled'

    if dest_dir.exists():
        # Check if already current by comparing mtime
        if dest_dir.stat().st_mtime >= temp_dir.stat().st_mtime:
            os.environ["MAGICK_HOME"] = str(dest_dir)
            return
        shutil.rmtree(dest_dir)
    shutil.copytree(temp_dir, dest_dir)

    # Set the environment variable for ImageMagick
    os.environ['MAGICK_HOME'] = str(dest_dir / 'imagemagick')

extract_bundled_files()
