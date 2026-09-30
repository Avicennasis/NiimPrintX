"""September review regression coverage."""

import base64
import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image

from NiimPrintX.ui.widget.FileMenu import FileMenu
from NiimPrintX.ui.widget.TextOperation import TextOperation
from tests.gui_helpers import add_raster, exporter


@pytest.fixture
def file_menu(editor, monkeypatch):
    root, state, option = editor
    menu = FileMenu.__new__(FileMenu)
    menu.root = root
    menu.immutable = option.immutable
    menu.canvas_state = state
    menu.printer = option.printer
    menu.printer.current_label_size = "30mm x 15mm"
    menu._on_deselect_all = MagicMock()
    menu._on_bind_text_select = MagicMock()
    menu._on_bind_image_select = MagicMock()

    def replace_canvas(*_):
        for props in state.image_items.values():
            props["original_image"].close()
        state.canvas.delete("all")
        state.text_items.clear()
        state.image_items.clear()
        state.bounding_box = state.canvas.create_rectangle(75, 75, 315, 195)

    menu._on_load_canvas_config = MagicMock(side_effect=replace_canvas)
    monkeypatch.setattr("NiimPrintX.ui.widget.FileMenu.messagebox.showerror", MagicMock())
    monkeypatch.setattr("NiimPrintX.ui.widget.FileMenu.messagebox.showwarning", MagicMock())
    monkeypatch.setattr("NiimPrintX.ui.widget.FileMenu.messagebox.askyesno", lambda *_: True)
    return menu


def png_data():
    with Image.new("RGBA", (4, 3), "black") as image, io.BytesIO() as buffer:
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")


def design(**kwargs):
    return {"device": "d110", "current_label_size": "30mm x 15mm", "text": {}, "image": {}, **kwargs}


@pytest.mark.parametrize("invalid", [None, [], 12, "device", True])
def test_invalid_json_root_preserves_design(file_menu, tmp_path, invalid):
    path = tmp_path / "bad.niim"
    path.write_text(json.dumps(invalid))
    file_menu.load_from_file(str(path))
    file_menu._on_load_canvas_config.assert_not_called()


def test_invalid_item_preserves_design(file_menu, tmp_path):
    path = tmp_path / "bad.niim"
    path.write_text(
        json.dumps(design(image={"1": {"coords": [0, 0], "original_image": png_data(), "image": "corrupt"}}))
    )
    file_menu.load_from_file(str(path))
    file_menu._on_load_canvas_config.assert_not_called()


@pytest.mark.parametrize("order", [[["image", "missing"]], [["image", "1"], ["image", "1"]], [None]])
def test_invalid_stacking_order_preserves_design(file_menu, tmp_path, order):
    path = tmp_path / "bad.niim"
    image = {"coords": [0, 0], "original_image": png_data(), "image": png_data()}
    path.write_text(json.dumps(design(image={"1": image}, order=order)))
    file_menu.load_from_file(str(path))
    file_menu._on_load_canvas_config.assert_not_called()


def test_file_roundtrip_preserves_pixels_and_stacking(editor, file_menu, tmp_path, monkeypatch):
    _, state, option = editor
    add_raster(state, "text", "black")
    add_raster(state, "image", "red")
    path = tmp_path / "design.niim"
    monkeypatch.setattr("NiimPrintX.ui.widget.FileMenu.filedialog.asksaveasfilename", lambda **_: str(path))
    with exporter(option) as before:
        file_menu.save_to_file()
        file_menu.load_from_file(str(path))
        with exporter(option) as after:
            assert before.tobytes() == after.tobytes()
    assert len(state.text_items) == len(state.image_items) == 1


def test_wand_text_roundtrip(file_menu, editor, tmp_path, monkeypatch):
    pytest.importorskip("wand.image")
    root, state, _ = editor
    parent = SimpleNamespace()
    props = {
        "family": "DejaVu Sans",
        "size": 16,
        "slant": "roman",
        "weight": "normal",
        "underline": False,
        "kerning": 0,
    }
    photo = TextOperation(parent, state).create_text_image(props, "Hello")
    item = state.canvas.create_image(80, 80, image=photo, anchor="nw")
    state.text_items[item] = {"font_image": photo, "font_props": props, "content": "Hello"}
    path = tmp_path / "text.niim"
    monkeypatch.setattr("NiimPrintX.ui.widget.FileMenu.filedialog.asksaveasfilename", lambda **_: str(path))
    file_menu.save_to_file()
    file_menu.load_from_file(str(path))
    assert next(iter(state.text_items.values()))["content"] == "Hello"
    root.update()


def test_open_during_print_does_not_replace_canvas(file_menu, tmp_path):
    path = tmp_path / "empty.niim"
    path.write_text(json.dumps(design()))
    file_menu.printer.print_job = True
    file_menu.load_from_file(str(path))
    file_menu._on_load_canvas_config.assert_not_called()


def test_replacement_limit_counts_incoming_items_only(file_menu, tmp_path):
    file_menu.canvas_state.text_items.update({i: {} for i in range(100)})
    path = tmp_path / "empty.niim"
    path.write_text(json.dumps(design()))
    file_menu.load_from_file(str(path))
    file_menu._on_load_canvas_config.assert_called_once()


def test_failed_save_preserves_existing_file(file_menu, tmp_path, monkeypatch):
    path = tmp_path / "design.niim"
    path.write_text("previous design")
    file_menu.canvas_state.text_items.update({i: {} for i in range(101)})
    monkeypatch.setattr("NiimPrintX.ui.widget.FileMenu.filedialog.asksaveasfilename", lambda **_: str(path))
    file_menu.save_to_file()
    assert path.read_text() == "previous design"


def test_declined_open_preserves_design(file_menu, tmp_path, monkeypatch):
    path = tmp_path / "empty.niim"
    path.write_text(json.dumps(design()))
    file_menu.canvas_state.text_items[42] = {}
    monkeypatch.setattr("NiimPrintX.ui.widget.FileMenu.messagebox.askyesno", lambda *_: False)
    file_menu.load_from_file(str(path))
    file_menu._on_load_canvas_config.assert_not_called()
    assert 42 in file_menu.canvas_state.text_items
