import copy
import os
import tempfile
from unittest.mock import patch

from NiimPrintX.ui.UserConfig import _validate_dims, load_user_config, merge_label_sizes

# --- _validate_dims tests ---


def test_validate_dims_valid_list():
    assert _validate_dims([30, 15]) == (30.0, 15.0)


def test_validate_dims_valid_tuple():
    assert _validate_dims((30, 15)) == (30.0, 15.0)


def test_validate_dims_invalid_length():
    assert _validate_dims([30]) is None


def test_validate_dims_invalid_type():
    assert _validate_dims("30x15") is None


def test_validate_dims_non_numeric():
    assert _validate_dims(["a", "b"]) is None


# --- merge_label_sizes tests ---


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
            "rotation": -90,
        }
    }


def test_merge_adds_size_to_existing_device():
    builtin = _make_builtin()
    user_config = {
        "devices": {
            "d110": {
                "size": {
                    "20x50": [20, 50],
                },
            },
        },
    }
    result = merge_label_sizes(builtin, user_config)
    assert "20x50" in result["d110"]["size"]
    assert result["d110"]["size"]["20x50"] == (20.0, 50.0)


def test_merge_creates_new_device():
    builtin = _make_builtin()
    user_config = {
        "devices": {
            "z999": {
                "size": {"10x20": [10, 20]},
                "density": 2,
                "print_dpi": 300,
                "rotation": 0,
            },
        },
    }
    result = merge_label_sizes(builtin, user_config)
    assert "z999" in result
    assert result["z999"]["size"] == {"10x20": (10.0, 20.0)}
    assert result["z999"]["density"] == 2
    assert result["z999"]["print_dpi"] == 300
    assert result["z999"]["rotation"] == 0


def test_merge_skips_new_device_without_sizes():
    builtin = _make_builtin()
    original = copy.deepcopy(builtin)
    user_config = {
        "devices": {
            "z999": {
                "size": {"bad": ["a", "b"]},
            },
        },
    }
    result = merge_label_sizes(builtin, user_config)
    assert "z999" not in result
    assert result == original


def test_merge_skips_non_dict_device():
    builtin = _make_builtin()
    original = copy.deepcopy(builtin)
    user_config = {
        "devices": {
            "d110": "not a dict",
        },
    }
    result = merge_label_sizes(builtin, user_config)
    assert result == original


def test_merge_preserves_existing_sizes():
    builtin = _make_builtin()
    user_config = {
        "devices": {
            "d110": {
                "size": {
                    "20x50": [20, 50],
                },
            },
        },
    }
    result = merge_label_sizes(builtin, user_config)
    # Original sizes still present
    assert result["d110"]["size"]["12x40"] == (12.0, 40.0)
    assert result["d110"]["size"]["15x30"] == (15.0, 30.0)
    # New size added
    assert result["d110"]["size"]["20x50"] == (20.0, 50.0)


def test_merge_empty_user_config():
    builtin = _make_builtin()
    original = copy.deepcopy(builtin)
    result = merge_label_sizes(builtin, {})
    assert result == original


# --- Clamping / validation tests for new devices ---


def test_density_clamping_new_device():
    """density: 10 for a new device should be clamped to the max of 5."""
    builtin = _make_builtin()
    user_config = {
        "devices": {
            "z999": {
                "size": {"10x20": [10, 20]},
                "density": 10,
            },
        },
    }
    result = merge_label_sizes(builtin, user_config)
    assert result["z999"]["density"] == 5


def test_print_dpi_clamping_new_device():
    """print_dpi: 1000 for a new device should be clamped to the max of 600."""
    builtin = _make_builtin()
    user_config = {
        "devices": {
            "z999": {
                "size": {"10x20": [10, 20]},
                "print_dpi": 1000,
            },
        },
    }
    result = merge_label_sizes(builtin, user_config)
    assert result["z999"]["print_dpi"] == 600


def test_rotation_validation():
    """rotation: 45 for a new device should be normalized to a valid value."""
    builtin = _make_builtin()
    user_config = {
        "devices": {
            "z999": {
                "size": {"10x20": [10, 20]},
                "rotation": 45,
            },
        },
    }
    result = merge_label_sizes(builtin, user_config)
    # 45 % 360 == 45, which is not in (0, 90, 180, 270), so it defaults to 270
    assert result["z999"]["rotation"] in (0, 90, 180, 270)
    assert result["z999"]["rotation"] == 270


def test_toml_decode_error_handling():
    """An invalid TOML file should cause load_user_config to return {} with a warning."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("this is not valid toml = = = [[[")
        tmp_path = f.name
    try:
        with patch("NiimPrintX.ui.UserConfig.CONFIG_FILE", tmp_path):
            result = load_user_config()
        assert result == {}
    finally:
        os.unlink(tmp_path)


# --- load_user_config path tests ---


def test_load_user_config_toml_parse_error():
    """A file with invalid TOML content should return {} (catches TOMLDecodeError)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("[broken\nkey without value\n!!!")
        tmp_path = f.name
    try:
        with patch("NiimPrintX.ui.UserConfig.CONFIG_FILE", tmp_path):
            result = load_user_config()
        assert result == {}
    finally:
        os.unlink(tmp_path)


def test_load_user_config_valid_config():
    """A valid TOML config with a custom device should load correctly."""
    toml_content = (
        "[devices.custom1]\n"
        "density = 3\n"
        "print_dpi = 203\n"
        "rotation = 270\n"
        "\n"
        "[devices.custom1.size]\n"
        '"50x30" = [50, 30]\n'
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        tmp_path = f.name
    try:
        with patch("NiimPrintX.ui.UserConfig.CONFIG_FILE", tmp_path):
            result = load_user_config()
        assert "devices" in result
        assert "custom1" in result["devices"]
        assert result["devices"]["custom1"]["density"] == 3
        assert result["devices"]["custom1"]["size"]["50x30"] == [50, 30]
    finally:
        os.unlink(tmp_path)


# --- merge_label_sizes additional path tests ---


def test_merge_adds_new_label_to_builtin():
    """Adding a new label size to an existing built-in device should appear in the merged result."""
    builtin = _make_builtin()
    user_config = {
        "devices": {
            "d110": {
                "size": {
                    "99x99": [99, 99],
                },
            },
        },
    }
    result = merge_label_sizes(builtin, user_config)
    assert "99x99" in result["d110"]["size"]
    assert result["d110"]["size"]["99x99"] == (99.0, 99.0)
    # Original sizes still present
    assert "12x40" in result["d110"]["size"]
    assert "15x30" in result["d110"]["size"]


def test_merge_custom_device_with_sizes():
    """A completely new device with size, density, print_dpi, rotation should appear with all fields."""
    builtin = _make_builtin()
    user_config = {
        "devices": {
            "custom1": {
                "size": {"40x60": [40, 60]},
                "density": 4,
                "print_dpi": 300,
                "rotation": 90,
            },
        },
    }
    result = merge_label_sizes(builtin, user_config)
    assert "custom1" in result
    assert result["custom1"]["size"] == {"40x60": (40.0, 60.0)}
    assert result["custom1"]["density"] == 4
    assert result["custom1"]["print_dpi"] == 300
    assert result["custom1"]["rotation"] == 90


def test_merge_custom_device_without_sizes_skipped():
    """A new device with no 'size' key should be skipped (not added to result)."""
    builtin = _make_builtin()
    original = copy.deepcopy(builtin)
    user_config = {
        "devices": {
            "custom1": {
                "density": 3,
                "print_dpi": 203,
                "rotation": 270,
            },
        },
    }
    result = merge_label_sizes(builtin, user_config)
    assert "custom1" not in result
    assert result == original
