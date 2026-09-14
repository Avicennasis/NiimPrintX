from importlib.metadata import PackageNotFoundError, version

from PIL import Image

try:
    __version__ = version("NiimPrintX")
except PackageNotFoundError:
    __version__ = "unknown"

# Single process-wide decompression-bomb ceiling for label images. This used to
# be assigned in five separate modules; one source avoids drift (FR-238).
MAX_IMAGE_PIXELS = 5_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
