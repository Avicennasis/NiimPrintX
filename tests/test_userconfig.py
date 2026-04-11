import copy

from NiimPrintX.ui.UserConfig import _validate_dims, merge_label_sizes


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
