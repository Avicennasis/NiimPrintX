"""September review regression coverage."""

import tkinter as tk
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image, ImageTk

from NiimPrintX.ui.widget.CanvasSelector import CanvasSelector
from NiimPrintX.ui.widget.ImageOperation import ImageOperation
from NiimPrintX.ui.widget.TextOperation import TextOperation
from tests.gui_helpers import add_raster, exporter


def test_export_dimensions_ignore_outline(editor):
    _, state, option = editor
    assert state.canvas.bbox(state.bounding_box) == (74, 74, 316, 196)
    with exporter(option) as image:
        assert image.size == (240, 120)
        assert image.getpixel((0, 0)) == (255, 255, 255, 255)


@pytest.mark.parametrize("kind", ["text", "image"])
def test_export_preserves_mixed_stacking_order(editor, kind):
    _, state, option = editor
    add_raster(state, kind, "black")
    add_raster(state, "image" if kind == "text" else "text", "red")
    with exporter(option) as image:
        assert image.getpixel((10, 10)) == (255, 0, 0, 255)


def test_export_outside_widget_and_offset_padding(editor):
    _, state, option = editor
    state.canvas.configure(width=20, height=20)
    add_raster(state, "image", "black")
    with exporter(option, horizontal_offset=1, vertical_offset=1) as image:
        assert image.size == (240, 120)
        assert image.getpixel((0, 0)) == (255, 255, 255, 255)
        assert image.getpixel((10, 10)) == (0, 0, 0, 255)


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_preview_pixels_match_print_payload(editor, monkeypatch, angle):
    root, _, option = editor
    option.image_label = tk.Label(root)
    option.print_button = tk.Button(root)
    option.print_rotation = tk.StringVar(root, value=str(angle))
    option.print_image = Image.new("RGBA", (3, 2), "white")
    option.print_image.putpixel((0, 0), (0, 0, 0, 255))
    option.print_op = SimpleNamespace(print=MagicMock(return_value=object()))
    root.async_loop = object()
    monkeypatch.setattr("NiimPrintX.ui.widget.PrintOption.asyncio.run_coroutine_threadsafe", lambda *_: Future())
    option.update_preview()
    with ImageTk.getimage(option.image_label.image) as preview:
        option.print_label(option.print_image, "3", "1")
        try:
            assert preview.size == option._rotated_image.size
            assert preview.tobytes() == option._rotated_image.tobytes()
        finally:
            option._rotated_image.close()


def test_popup_is_singleton(editor):
    _, _, option = editor
    option._popup_ref = MagicMock()
    option.display_image_in_popup("does-not-exist.png")
    option._popup_ref.lift.assert_called_once()


def test_new_text_is_inside_label(editor):
    pytest.importorskip("wand.image")
    root, state, _ = editor
    entry = tk.Text(root)
    entry.insert("1.0", "Hello\nWorld")
    props = {
        "family": "DejaVu Sans",
        "size": 16,
        "slant": "roman",
        "weight": "normal",
        "underline": False,
        "kerning": 0,
    }
    parent = SimpleNamespace(content_entry=entry, get_font_properties=lambda: props)
    operation = TextOperation(parent, state)
    operation.add_text_to_canvas()
    item = next(iter(state.text_items))
    x1, y1, x2, y2 = state.canvas.coords(state.bounding_box)
    bx1, by1, bx2, by2 = state.canvas.bbox(item)
    assert x1 <= bx1 < bx2 <= x2
    assert y1 <= by1 < by2 <= y2


def test_import_honors_exif_orientation(editor, tmp_path):
    _, state, _ = editor
    path = tmp_path / "camera.jpg"
    with Image.new("RGB", (40, 20), "red") as image:
        exif = image.getexif()
        exif[274] = 6
        image.save(path, exif=exif)
    ImageOperation(state).load_image(str(path))
    original = next(iter(state.image_items.values()))["original_image"]
    assert original.size == (20, 40)


def test_extreme_aspect_image_import_and_resize(editor, tmp_path):
    _, state, _ = editor
    path = tmp_path / "tall.png"
    with Image.new("RGB", (1, 10_000), "black") as image:
        image.save(path)
    operation = ImageOperation(state)
    operation.load_image(str(path))
    item = next(iter(state.image_items))
    props = state.image_items[item]
    assert props["image"].width() == 1
    operation.select_image(SimpleNamespace(x=0, y=0), item)
    operation.resize_image(SimpleNamespace(x=100_000, y=0), item)
    assert props["image"].width() >= 1
    assert props["image"].height() <= 4096


def test_selector_preserves_odd_pixel_dimensions(editor):
    root, state, option = editor
    state.frames["top_frame"] = tk.Frame(root)
    option.immutable.label_sizes["d110"]["size"] = {"odd": (101 * 25.4 / 203, 51 * 25.4 / 203)}
    selector = CanvasSelector(root, option.immutable, state, option.printer, MagicMock(), MagicMock())
    x1, y1, x2, y2 = state.canvas.coords(state.bounding_box)
    assert (x2 - x1, y2 - y1) == (101, 51)
    canvas = state.canvas
    selector.on_device_selected()
    selector.on_label_size_selected()
    assert state.canvas is canvas
