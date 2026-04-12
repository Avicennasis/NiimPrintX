class NiimPrintXException(Exception):
    """Base exception for all NiimPrintX errors."""


class BLEException(NiimPrintXException):
    """Raised for Bluetooth/BLE transport errors."""


class PrinterException(NiimPrintXException):
    """Raised for printer-level protocol errors."""


class ConfigException(NiimPrintXException):
    """Raised for configuration validation or loading errors."""
