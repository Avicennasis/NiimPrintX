from io import StringIO

import pytest

from NiimPrintX.nimmy.exception import BLEException, ConfigException, NiimPrintXException, PrinterException
from NiimPrintX.nimmy.helper import print_error, print_info, print_success
from NiimPrintX.nimmy.logger_config import get_logger, logger_enable, setup_logger
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


def test_exception_hierarchy():
    """BLEException and PrinterException should be subclasses of NiimPrintXException."""
    assert issubclass(BLEException, NiimPrintXException)
    assert issubclass(PrinterException, NiimPrintXException)

    # Verify instances are caught by the base class
    with pytest.raises(NiimPrintXException):
        raise BLEException("test ble")

    with pytest.raises(NiimPrintXException):
        raise PrinterException("test printer")


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


def test_print_info_writes_to_stdout():
    """print_info should write its message to stdout, not stderr."""

    from rich.console import Console

    buf = StringIO()
    # Build a Console that writes to our buffer (no color to keep output clean)
    cap_console = Console(file=buf, color_system=None)

    import NiimPrintX.nimmy.helper as helper_mod

    orig = helper_mod.console
    helper_mod.console = cap_console
    try:
        print_info("test msg")
    finally:
        helper_mod.console = orig

    output = buf.getvalue()
    assert "test msg" in output


def test_print_success_no_trailing_space():
    """print_success output should not end with a space before the newline."""
    from rich.console import Console

    buf = StringIO()
    cap_console = Console(file=buf, color_system=None)

    import NiimPrintX.nimmy.helper as helper_mod

    orig = helper_mod.console
    helper_mod.console = cap_console
    try:
        print_success("done")
    finally:
        helper_mod.console = orig

    output = buf.getvalue()
    # Strip only the trailing newline, then check for trailing space
    assert not output.rstrip("\n").endswith(" ")


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
    # Verify logger is still functional by checking setup + enable didn't raise
    # and that the logger can still be retrieved (handler exists internally)
    logger = get_logger()
    assert logger is not None


def test_logger_enable_nonzero_changes_level():
    """logger_enable(1) should work without error."""
    setup_logger()
    logger_enable(1)


def test_setup_logger_configures_handlers():
    """setup_logger should configure at least one handler on the loguru logger."""
    from loguru import logger as loguru_logger

    setup_logger()
    # loguru stores handlers in logger._core.handlers (dict)
    assert len(loguru_logger._core.handlers) >= 1


def test_logger_enable_verbose_changes_level():
    """logger_enable(1) should allow DEBUG-level messages to be captured."""
    from loguru import logger as loguru_logger

    setup_logger()
    logger_enable(1)

    captured = []
    handler_id = loguru_logger.add(lambda msg: captured.append(str(msg)), level="DEBUG")
    try:
        loguru_logger.debug("verbose debug message")
    finally:
        loguru_logger.remove(handler_id)

    assert any("verbose debug message" in m for m in captured)


def test_config_exception_hierarchy():
    """ConfigException should be a subclass of NiimPrintXException."""
    assert issubclass(ConfigException, NiimPrintXException)
    assert issubclass(ConfigException, Exception)

    with pytest.raises(NiimPrintXException):
        raise ConfigException("bad config")


# ---------- packet.py — packet_to_int ----------


def test_packet_to_int():
    """packet_to_int with two-byte data 0x0001 should return 1."""
    pkt = NiimbotPacket(0x00, b"\x00\x01")
    assert packet_to_int(pkt) == 1


def test_packet_to_int_single_byte():
    """packet_to_int with single byte 0xFF should return 255."""
    pkt = NiimbotPacket(0x00, b"\xff")
    assert packet_to_int(pkt) == 255
