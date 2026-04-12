"""Tests for NiimPrintX.ui.config — ImmutableConfig, CanvasState, PrinterState, mm_to_pixels."""

import os
from unittest.mock import MagicMock

from NiimPrintX.ui.config import CanvasState, ImmutableConfig, PrinterState, mm_to_pixels

# ---------------------------------------------------------------------------
# ImmutableConfig
# ---------------------------------------------------------------------------


def test_immutable_config_defaults():
    cfg = ImmutableConfig()
    assert isinstance(cfg.os_system, str)
    assert os.path.isdir(cfg.current_dir)
    assert cfg.icon_folder.endswith("icons")
    assert isinstance(cfg.cache_dir, str)
    assert len(cfg.cache_dir) > 0
    assert len(cfg.label_sizes) == 8


def test_immutable_config_label_sizes_structure():
    cfg = ImmutableConfig()
    required = {"size", "density", "print_dpi", "rotation"}
    for device, conf in cfg.label_sizes.items():
        missing = required - set(conf.keys())
        assert not missing, f"{device} missing keys: {missing}"


def test_immutable_config_no_merge_when_callables_none():
    cfg = ImmutableConfig(load_user_config=None, merge_label_sizes=None)
    expected = {"d110", "d11", "d11_h", "d101", "d110_m", "b18", "b21", "b1"}
    assert set(cfg.label_sizes.keys()) == expected


def test_immutable_config_merge_called():
    custom = {"custom_dev": {"size": {"10mm x 5mm": (10, 5)}, "density": 2, "print_dpi": 203, "rotation": 0}}
    load = MagicMock(return_value=custom)
    merge = MagicMock(side_effect=lambda base, user: {**base, **user})

    cfg = ImmutableConfig(load_user_config=load, merge_label_sizes=merge)

    load.assert_called_once()
    merge.assert_called_once()
    assert "custom_dev" in cfg.label_sizes


def test_immutable_config_merge_skipped_when_user_config_empty():
    load = MagicMock(return_value=None)
    merge = MagicMock()

    cfg = ImmutableConfig(load_user_config=load, merge_label_sizes=merge)

    load.assert_called_once()
    merge.assert_not_called()
    # label_sizes should remain the built-in set
    assert len(cfg.label_sizes) == 8


# ---------------------------------------------------------------------------
# CanvasState
# ---------------------------------------------------------------------------


def test_canvas_state_defaults():
    cs = CanvasState()
    assert cs.canvas is None
    assert cs.bounding_box is None
    assert cs.text_items == {}
    assert cs.image_items == {}
    assert cs.current_selected is None
    assert cs.current_selected_image is None
    assert cs.frames == {}


def test_canvas_state_mutable():
    cs = CanvasState()
    cs.canvas = "mock_canvas"
    cs.text_items = {"item1": "hello"}
    cs.bounding_box = (0, 0, 100, 100)
    cs.current_selected = 42
    cs.current_selected_image = "img.png"
    cs.frames = {"main": "frame_obj"}

    assert cs.canvas == "mock_canvas"
    assert cs.text_items == {"item1": "hello"}
    assert cs.bounding_box == (0, 0, 100, 100)
    assert cs.current_selected == 42
    assert cs.current_selected_image == "img.png"
    assert cs.frames == {"main": "frame_obj"}


# ---------------------------------------------------------------------------
# PrinterState
# ---------------------------------------------------------------------------


def test_printer_state_defaults():
    ps = PrinterState(default_device="d110")
    assert ps.device == "d110"
    assert ps.current_label_size is None
    assert ps.printer_connected is False
    assert ps.print_job is False


def test_printer_state_mutable():
    ps = PrinterState(default_device="d110")
    ps.device = "b21"
    ps.printer_connected = True
    ps.print_job = True

    assert ps.device == "b21"
    assert ps.printer_connected is True
    assert ps.print_job is True


# ---------------------------------------------------------------------------
# mm_to_pixels
# ---------------------------------------------------------------------------


def test_mm_to_pixels_203dpi():
    assert mm_to_pixels(30, 203) == round(30 / 25.4 * 203)  # 240


def test_mm_to_pixels_300dpi():
    assert mm_to_pixels(30, 300) == round(30 / 25.4 * 300)  # 354


def test_mm_to_pixels_zero():
    assert mm_to_pixels(0, 203) == 0


def test_mm_to_pixels_fractional():
    assert mm_to_pixels(12.5, 203) == round(12.5 / 25.4 * 203)  # 100
