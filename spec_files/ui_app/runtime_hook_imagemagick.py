import os
import sys

if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    os.environ['MAGICK_CONFIGURE_PATH'] = os.path.join(bundle_dir, 'imagemagick', 'config')
