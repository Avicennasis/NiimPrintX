"""Tests covering the biggest UserConfig coverage gaps."""

import copy
import os
import tempfile
from unittest.mock import patch

from NiimPrintX.ui.UserConfig import _validate_dims, load_user_config, merge_label_sizes


def _make_builtin():
    """Return a minimal built-in sizes dict for testing."""
    return {
        "d110": {
            "size": {
                "12x40": (12.0, 40.0),
                "15x30": (15.0, 30.0),
            },
            "density": 3,
            "print_dpi": 203,
            "rotation": 270,
        }
    }


# ---------------------------------------------------------------------------
# 1. load_user_config — OSError returns {} gracefully
# ---------------------------------------------------------------------------


def test_load_user_config_os_error():
    """When open() raises OSError, load_user_config should return {} gracefully."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("[devices]\n")
        tmp_path = f.name
    try:
        with (
            patch("NiimPrintX.ui.UserConfig.CONFIG_FILE", tmp_path),
            patch("builtins.open", side_effect=OSError("permission denied")),
        ):
            result = load_user_config()
        assert result == {}
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# 2. merge_label_sizes — does not mutate input dict
# ---------------------------------------------------------------------------


def test_merge_does_not_mutate_input():
    """Passing a builtin_sizes dict to merge_label_sizes must not modify it."""
    builtin = _make_builtin()
    original = copy.deepcopy(builtin)
    user_config = {
        "devices": {
            "d110": {
                "size": {
                    "20x50": [20, 50],
                },
            },
        },
    }
    merge_label_sizes(builtin, user_config)
    assert builtin == original, "merge_label_sizes mutated the input builtin_sizes dict"


# ---------------------------------------------------------------------------
# 3. merge — ignores non-size keys on a built-in device and logs warning
# ---------------------------------------------------------------------------


def test_merge_ignores_non_size_keys_on_builtin():
    """Setting density on a built-in device should be ignored; a warning logged."""
    builtin = _make_builtin()
    user_config = {
        "devices": {
            "d110": {
                "density": 5,
                "size": {
                    "20x50": [20, 50],
                },
            },
        },
    }
    with patch("NiimPrintX.ui.UserConfig.logger") as mock_logger:
        result = merge_label_sizes(builtin, user_config)
    # density should be the original, NOT 5
    assert result["d110"]["density"] == 3
    # A warning about ignored keys should have been logged
    mock_logger.warning.assert_called()
    warning_text = mock_logger.warning.call_args[0][0]
    assert "ignored" in warning_text.lower()


# ---------------------------------------------------------------------------
# 4. merge — custom device defaults rotation to 270
# ---------------------------------------------------------------------------


def test_merge_custom_device_default_rotation():
    """A custom device with no rotation specified should default to 270."""
    builtin = _make_builtin()
    user_config = {
        "devices": {
            "z999": {
                "size": {"10x20": [10, 20]},
            },
        },
    }
    result = merge_label_sizes(builtin, user_config)
    assert result["z999"]["rotation"] == 270


def test_merge_custom_device_negative_rotation():
    """rotation: -90 should be accepted and stored as 270 (matching README docs)."""
    builtin = _make_builtin()
    user_config = {
        "devices": {
            "z999": {
                "size": {"10x20": [10, 20]},
                "rotation": -90,
            },
        },
    }
    result = merge_label_sizes(builtin, user_config)
    assert result["z999"]["rotation"] == 270


# ---------------------------------------------------------------------------
# 5. merge — custom device with invalid rotation defaults to 270 + warning
# ---------------------------------------------------------------------------


def test_merge_custom_device_invalid_rotation():
    """rotation: 45 should be clamped/defaulted to 270 with a warning."""
    builtin = _make_builtin()
    user_config = {
        "devices": {
            "z999": {
                "size": {"10x20": [10, 20]},
                "rotation": 45,
            },
        },
    }
    with patch("NiimPrintX.ui.UserConfig.logger") as mock_logger:
        result = merge_label_sizes(builtin, user_config)
    assert result["z999"]["rotation"] == 270
    # Should have logged a warning about invalid rotation
    mock_logger.warning.assert_called()
    warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
    assert any("rotation" in msg.lower() for msg in warning_calls)


# ---------------------------------------------------------------------------
# 6. _validate_dims — non-numeric strings return None
# ---------------------------------------------------------------------------


def test_validate_dims_non_numeric():
    """Passing non-numeric strings as dims should return None."""
    assert _validate_dims(["abc", "def"]) is None


# ---------------------------------------------------------------------------
# 7. _validate_dims — negative values return None
# ---------------------------------------------------------------------------


def test_validate_dims_negative():
    """Passing a negative value in dims should return None."""
    assert _validate_dims([-5, 10]) is None
