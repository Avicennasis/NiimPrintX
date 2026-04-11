import pytest
from NiimPrintX.nimmy.exception import BLEException, PrinterException
from NiimPrintX.nimmy.helper import print_success, print_error, print_info
from NiimPrintX.nimmy.logger_config import setup_logger, logger_enable, get_logger
from NiimPrintX.nimmy.packet import NiimbotPacket, packet_to_int


# ---------- exception.py ----------

def test_ble_exception_is_exception():
    """BLEException should inherit from Exception."""
    assert issubclass(BLEException, Exception)


def test_printer_exception_is_exception():
    """PrinterException should inherit from Exception."""
    assert issubclass(PrinterException, Exception)


def test_ble_exception_message():
    """BLEException should store its message in args[0]."""
    exc = BLEException("msg")
    assert exc.args[0] == "msg"


def test_printer_exception_message():
    """PrinterException should store its message in args[0]."""
    exc = PrinterException("msg")
    assert exc.args[0] == "msg"


def test_exceptions_are_distinct():
    """BLEException and PrinterException must be different classes."""
    assert BLEException is not PrinterException


# ---------- helper.py ----------

def test_print_success_no_crash():
    """print_success should not raise on a simple string."""
    print_success("test")


def test_print_error_no_crash():
    """print_error should not raise on a simple string."""
    print_error("test")


def test_print_info_no_crash():
    """print_info should not raise on a simple string."""
    print_info("test")


# ---------- logger_config.py ----------

def test_get_logger_returns_logger():
    """get_logger() should return the loguru logger instance."""
    from loguru import logger as loguru_logger
    assert get_logger() is loguru_logger


def test_setup_logger_no_crash():
    """setup_logger() should not raise."""
    setup_logger()


def test_logger_enable_zero_preserves_handlers():
    """logger_enable(0) should return early without removing handlers."""
    setup_logger()
    logger_enable(0)
    # After verbose=0, handlers should still exist
    assert len(get_logger()._core.handlers) > 0


def test_logger_enable_nonzero_changes_level():
    """logger_enable(1) should work without error."""
    setup_logger()
    logger_enable(1)


# ---------- packet.py — packet_to_int ----------

def test_packet_to_int():
    """packet_to_int with two-byte data 0x0001 should return 1."""
    pkt = NiimbotPacket(0x00, b"\x00\x01")
    assert packet_to_int(pkt) == 1


def test_packet_to_int_single_byte():
    """packet_to_int with single byte 0xFF should return 255."""
    pkt = NiimbotPacket(0x00, b"\xFF")
    assert packet_to_int(pkt) == 255
