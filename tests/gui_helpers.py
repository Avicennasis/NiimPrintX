"""September review regression coverage."""

import tkinter as tk

import pytest
from PIL import Image, ImageTk

from NiimPrintX.ui.config import CanvasState, ImmutableConfig, PrinterState
from NiimPrintX.ui.widget.PrintOption import PrintOption


@pytest.fixture
def editor():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display required; run under xvfb-run")
    root.geometry("500x300")
    state = CanvasState()
    state.canvas = tk.Canvas(root, width=400, height=220)
    state.canvas.pack()
    state.bounding_box = state.canvas.create_rectangle(75, 75, 315, 195, fill="white", width=1)
    root.update()
    option = PrintOption.__new__(PrintOption)
    option.root = root
    option.canvas_state = state
    option.immutable = ImmutableConfig()
    option.printer = PrinterState("d110")
    option.print_image = None
    option._popup_ref = None
    option.toolbar_print_button = tk.Button(root)
    try:
        yield root, state, option
    finally:
        if option.print_image is not None:
            option.print_image.close()
        for props in state.image_items.values():
            props["original_image"].close()
        root.destroy()


def add_raster(state, kind, color, x=75, y=75):
    with Image.new("RGBA", (40, 20), color) as image:
        photo = ImageTk.PhotoImage(image)
        original = image.copy()
    item = state.canvas.create_image(x, y, image=photo, anchor="nw")
    if kind == "image":
        state.image_items[item] = {"image": photo, "original_image": original, "bbox": None, "handle": None}
    else:
        original.close()
        state.text_items[item] = {
            "font_image": photo,
            "font_props": {
                "family": "DejaVu Sans",
                "size": 16,
                "slant": "roman",
                "weight": "normal",
                "underline": False,
                "kerning": 0,
            },
            "content": "text",
            "bbox": None,
            "handle": None,
        }
    return item


def exporter(option, **kwargs):
    pytest.importorskip("cairo")
    return option.export_to_png(**kwargs)
