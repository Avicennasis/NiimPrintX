"""Tests for Round 9 UI guards — data/logic layer only, no tkinter required."""

from unittest.mock import patch

import pytest

from NiimPrintX.nimmy.packet import NiimbotPacket, packet_to_int
from NiimPrintX.ui.UserConfig import _validate_dims, merge_label_sizes

# ---------------------------------------------------------------------------
# 1. AppConfig.device defaults to first key in label_sizes
# ---------------------------------------------------------------------------


def test_appconfig_device_defaults_to_first_key():
    """AppConfig().device must not be None and must equal the first key
    of label_sizes (currently 'd110')."""
    with (
        patch("NiimPrintX.ui.AppConfig.load_user_config", return_value={}),
        patch("NiimPrintX.ui.AppConfig.merge_label_sizes", side_effect=lambda b, u: b),
    ):
        from NiimPrintX.ui.AppConfig import AppConfig

        config = AppConfig()
        assert config.device is not None
        first_key = next(iter(config.label_sizes))
        assert config.device == first_key


# ---------------------------------------------------------------------------
# 2. merge_label_sizes deep-copies — mutating result leaves original intact
# ---------------------------------------------------------------------------


def test_merge_label_sizes_deep_copy():
    """Mutating the dict returned by merge_label_sizes must not affect the
    original builtin_sizes dict passed in."""
    original = {
        "test_printer": {
            "size": {"10mm x 10mm": (10, 10)},
            "density": 3,
            "print_dpi": 203,
            "rotation": 0,
        }
    }
    # Snapshot the original value before merge
    orig_size_tuple = original["test_printer"]["size"]["10mm x 10mm"]

    result = merge_label_sizes(original, {})

    # Mutate the result
    result["test_printer"]["size"]["10mm x 10mm"] = (99, 99)
    result["test_printer"]["density"] = 1

    # Original must be unchanged
    assert original["test_printer"]["size"]["10mm x 10mm"] == orig_size_tuple
    assert original["test_printer"]["density"] == 3


# ---------------------------------------------------------------------------
# 3. _validate_dims — valid input returns (float, float)
# ---------------------------------------------------------------------------


def test_validate_dims_valid():
    """_validate_dims must return a (float, float) tuple for valid input."""
    result = _validate_dims([30, 15])
    assert result is not None
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert result == (30.0, 15.0)


# ---------------------------------------------------------------------------
# 4. _validate_dims — single-element list returns None
# ---------------------------------------------------------------------------


def test_validate_dims_too_short():
    """_validate_dims must return None when given a single-element list."""
    assert _validate_dims([30]) is None


# ---------------------------------------------------------------------------
# 5. packet_to_int — empty data raises ValueError
# ---------------------------------------------------------------------------


def test_packet_to_int_empty_raises():
    """packet_to_int must raise ValueError when packet data is empty."""
    pkt = NiimbotPacket(0x00, b"")
    with pytest.raises(ValueError, match="empty"):
        packet_to_int(pkt)
