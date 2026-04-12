from unittest.mock import patch

import pytest

from NiimPrintX.ui.AppConfig import AppConfig


@pytest.fixture(autouse=True)
def no_user_config():
    with (
        patch("NiimPrintX.ui.AppConfig.load_user_config", return_value={}),
        patch("NiimPrintX.ui.AppConfig.merge_label_sizes", side_effect=lambda b, u: b),
    ):
        yield


def test_all_devices_have_required_keys():
    """Every device must have size, density, print_dpi, and rotation."""
    config = AppConfig()
    required = {"size", "density", "print_dpi", "rotation"}
    for device, conf in config.label_sizes.items():
        missing = required - set(conf.keys())
        assert not missing, f"{device} missing keys: {missing}"


def test_all_devices_have_at_least_one_size():
    config = AppConfig()
    for device, conf in config.label_sizes.items():
        assert len(conf["size"]) > 0, f"{device} has no label sizes"


def test_density_in_valid_range():
    config = AppConfig()
    for device, conf in config.label_sizes.items():
        assert 1 <= conf["density"] <= 5, f"{device} density {conf['density']} out of range"


def test_print_dpi_is_known_value():
    config = AppConfig()
    for device, conf in config.label_sizes.items():
        assert conf["print_dpi"] in (203, 300), f"{device} has unexpected DPI {conf['print_dpi']}"


def test_rotation_is_valid():
    config = AppConfig()
    for device, conf in config.label_sizes.items():
        assert conf["rotation"] in (0, -90, 90, 180), f"{device} has unexpected rotation {conf['rotation']}"


def test_expected_devices_present():
    """All known supported devices should be in the config."""
    config = AppConfig()
    expected = {"d110", "d11", "d11_h", "d110_m", "d101", "b18", "b21", "b1"}
    actual = set(config.label_sizes.keys())
    missing = expected - actual
    assert not missing, f"Missing devices: {missing}"


def test_device_is_first_label_size_key():
    config = AppConfig()
    assert config.device == next(iter(config.label_sizes))


def test_icon_folder_exists_or_is_valid_path():
    config = AppConfig()
    assert isinstance(config.icon_folder, str)
    assert config.icon_folder.endswith("/icons")


def test_user_config_merged():
    custom = {"custom_printer": {"size": {"10mm x 5mm": (10, 5)}, "density": 2, "print_dpi": 203, "rotation": 0}}
    with (
        patch("NiimPrintX.ui.AppConfig.load_user_config", return_value=custom),
        patch("NiimPrintX.ui.AppConfig.merge_label_sizes", side_effect=lambda b, u: {**b, **u}),
    ):
        config = AppConfig()
    assert "custom_printer" in config.label_sizes


def test_initial_state():
    config = AppConfig()
    assert config.canvas is None
    assert config.bounding_box is None
    assert config.text_items == {}
    assert config.image_items == {}
    assert config.current_selected is None
    assert config.print_job is False
    assert config.printer_connected is False


def test_cache_dir_is_string():
    config = AppConfig()
    assert isinstance(config.cache_dir, str)
    assert len(config.cache_dir) > 0
