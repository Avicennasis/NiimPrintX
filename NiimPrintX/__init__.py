from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("NiimPrintX")
except PackageNotFoundError:
    __version__ = "unknown"
