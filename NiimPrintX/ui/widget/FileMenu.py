from __future__ import annotations

import base64
import contextlib
import io
import json
import math
import os
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import PIL
from PIL import Image, ImageTk

if TYPE_CHECKING:
    from collections.abc import Callable

    from NiimPrintX.ui.config import CanvasState, ImmutableConfig, PrinterState

_MAX_LABEL_PIXELS = 5_000_000  # well above any real label dimensions
_MAX_ITEMS_PER_FILE = 100


class FileMenu:
    def __init__(
        self,
        root: tk.Tk,
        parent: tk.Menu,
        immutable: ImmutableConfig,
        canvas_state: CanvasState,
        printer: PrinterState,
        *,
        on_close: Callable[[], None],
        on_deselect_all: Callable[[], None],
        on_load_canvas_config: Callable[[str, str], None],
        on_bind_text_select: Callable[[int], None],
        on_bind_image_select: Callable[[int], None],
    ) -> None:
        self.root: tk.Tk = root
        self.parent: tk.Menu = parent
        self.immutable: ImmutableConfig = immutable
        self.canvas_state: CanvasState = canvas_state
        self.printer: PrinterState = printer
        self._on_close: Callable[[], None] = on_close
        self._on_deselect_all: Callable[[], None] = on_deselect_all
        self._on_load_canvas_config: Callable[[str, str], None] = on_load_canvas_config
        self._on_bind_text_select: Callable[[int], None] = on_bind_text_select
        self._on_bind_image_select: Callable[[int], None] = on_bind_image_select
        self.create_menu()

    def create_menu(self) -> None:
        file_menu: tk.Menu = tk.Menu(self.parent, tearoff=0)
        self.parent.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save", command=self.save_to_file)
        file_menu.add_command(label="Open", command=self.load_from_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)

    def on_close(self) -> None:
        self._on_close()

    def save_to_file(self) -> None:
        try:
            file_path = filedialog.asksaveasfilename(defaultextension=".niim", filetypes=[("NIIM files", "*.niim")])
            if not file_path:
                return

            count = len(self.canvas_state.text_items) + len(self.canvas_state.image_items)
            if count > _MAX_ITEMS_PER_FILE:
                raise ValueError(f"Design contains {count} items; maximum is {_MAX_ITEMS_PER_FILE}")

            data = {
                "device": self.printer.device,
                "current_label_size": self.printer.current_label_size,
                "text": {},
                "image": {},
                "order": [],
            }
            if self.canvas_state.text_items:
                for text_id, properties in self.canvas_state.text_items.items():
                    font_image_widget = properties["font_image"]
                    # Handle both tk.PhotoImage (from Wand) and ImageTk.PhotoImage (from load)
                    if isinstance(font_image_widget, ImageTk.PhotoImage):
                        pil_image = ImageTk.getimage(font_image_widget)
                    else:
                        # tk.PhotoImage — extract PNG via Tk call
                        png_data = font_image_widget.tk.call(str(font_image_widget), "data", "-format", "png")
                        # Tcl may return raw bytes or base64 string depending on Tk version
                        if isinstance(png_data, bytes):
                            pil_image = Image.open(io.BytesIO(png_data))
                        else:
                            pil_image = Image.open(io.BytesIO(base64.b64decode(png_data)))
                    with io.BytesIO() as buffer:
                        pil_image.save(buffer, format="PNG")
                        buffer.seek(0)
                        font_img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

                    item_data = {
                        "content": properties["content"],
                        "coords": self.canvas_state.canvas.coords(text_id),
                        "font_props": properties["font_props"],
                        "font_image": font_img_str,
                    }
                    data["text"][str(text_id)] = item_data
                    pil_image.close()

            if self.canvas_state.image_items:
                for image_id, properties in self.canvas_state.image_items.items():
                    resized_image = ImageTk.getimage(properties["image"])
                    with io.BytesIO() as buffer:
                        resized_image.save(buffer, format="PNG")
                        buffer.seek(0)
                        resize_img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

                    with io.BytesIO() as buffer:
                        properties["original_image"].save(buffer, format="PNG")
                        buffer.seek(0)
                        original_img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

                    item_data = {
                        "image": resize_img_str,
                        "original_image": original_img_str,
                        "coords": self.canvas_state.canvas.coords(image_id),
                    }
                    data["image"][str(image_id)] = item_data
                    resized_image.close()

            for item_id in self.canvas_state.canvas.find_all():
                if item_id in self.canvas_state.text_items:
                    data["order"].append(["text", str(item_id)])
                elif item_id in self.canvas_state.image_items:
                    data["order"].append(["image", str(item_id)])

            dir_name = os.path.dirname(file_path) or "."
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, suffix=".tmp") as tf:
                    tmp_path = tf.name
                    json.dump(data, tf, indent=2)
                os.replace(tmp_path, file_path)
            except BaseException:
                if tmp_path and os.path.exists(tmp_path):
                    with contextlib.suppress(OSError):
                        os.remove(tmp_path)
                raise
        except (OSError, ValueError, TypeError, tk.TclError) as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def load_from_file(self, file_path: str | None = None) -> None:  # noqa: PLR0911 — validation exits preserve the existing design
        if self.printer.print_job:
            messagebox.showwarning("Printing", "Wait for the print job to finish before opening a design.")
            return
        if file_path is None:
            file_path = filedialog.askopenfilename(filetypes=[("NIIM files", "*.niim")])
        if file_path:
            try:
                if os.path.getsize(file_path) > 64 * 1024 * 1024:
                    raise ValueError("File exceeds the 64 MiB size limit")
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
                messagebox.showerror(
                    "Error",
                    f"Failed to open file: {e}\n\n"
                    "Only JSON .niim files are supported. Legacy pickle "
                    "files must be re-saved from an older version first.",
                )
                return

            if not isinstance(data, dict):
                messagebox.showerror("Error", "Invalid .niim file: expected a JSON object.")
                return

            # Validate required keys
            for key in ("device", "current_label_size", "text", "image"):
                if key not in data:
                    messagebox.showerror("Error", f"Invalid .niim file: missing '{key}'")
                    return

            if not isinstance(data.get("device"), str) or not isinstance(data.get("current_label_size"), str):
                messagebox.showerror("Error", "Invalid .niim file: 'device' and 'current_label_size' must be strings.")
                return

            text_data = data.get("text")
            image_data = data.get("image")
            if not isinstance(text_data, dict) or not isinstance(image_data, dict):
                messagebox.showerror("Error", "Invalid .niim file: 'text' and 'image' must be dicts.")
                return

            file_items = len(text_data) + len(image_data)
            if file_items > _MAX_ITEMS_PER_FILE:
                messagebox.showerror(
                    "Error", f"File contains too many items ({file_items}). Maximum is {_MAX_ITEMS_PER_FILE}."
                )
                return

            device = data.get("device", "").lower()
            label_size = data.get("current_label_size", "")
            if device not in self.immutable.label_sizes or label_size not in self.immutable.label_sizes[device].get(
                "size", {}
            ):
                messagebox.showerror(
                    "Error", f"Device '{device}' / label size '{label_size}' not found in configuration."
                )
                return

            # Decode and validate every item before replacing the existing
            # canvas. A corrupt item must never erase an in-progress design.
            prepared = {}
            try:
                for key, item in text_data.items():
                    prepared[("text", key)] = self._prepare_text(item)
                for key, item in image_data.items():
                    prepared[("image", key)] = self._prepare_image(item)
                order = data.get("order", [[kind, key] for kind, key in prepared])
                if not isinstance(order, list) or any(
                    not isinstance(entry, list) or len(entry) != 2 or not all(isinstance(v, str) for v in entry)
                    for entry in order
                ):
                    raise ValueError("Invalid item stacking order")
                keys = [tuple(entry) for entry in order]
                if len(keys) != len(prepared) or set(keys) != set(prepared):
                    raise ValueError("Item stacking order must list each item exactly once")
                if (self.canvas_state.text_items or self.canvas_state.image_items) and not messagebox.askyesno(
                    "Replace design?", "Opening this file replaces the current design. Continue?"
                ):
                    return
                self._on_deselect_all()
                self._on_load_canvas_config(device, label_size)
                for kind, key in keys:
                    self._place_item(kind, prepared[(kind, key)])
                prepared.clear()  # original images now belong to canvas state
            except (OSError, ValueError, TypeError, KeyError, tk.TclError) as e:
                messagebox.showerror("Error", f"Failed to open design: {e}")
            finally:
                for _, props in prepared.values():
                    if "original_image" in props:
                        props["original_image"].close()

    @staticmethod
    def _coords(data: dict) -> list | tuple:
        if not isinstance(data, dict):
            raise ValueError("Item must be an object")
        coords = data.get("coords")
        if not isinstance(coords, list | tuple) or len(coords) != 2:
            raise ValueError("coords must contain exactly two numbers")
        if not all(isinstance(c, int | float) and not isinstance(c, bool) and math.isfinite(c) for c in coords):
            raise ValueError("coords must be finite numbers")
        return coords

    @staticmethod
    def _decode_png(raw: object) -> Image.Image:
        if not isinstance(raw, str) or len(raw) > 10 * 1024 * 1024:
            raise ValueError("Image data too large or wrong type")
        with Image.open(io.BytesIO(base64.b64decode(raw, validate=True))) as image:
            if image.format != "PNG":
                raise ValueError(f"Expected PNG image, got {image.format}")
            if image.width * image.height > _MAX_LABEL_PIXELS:
                raise ValueError(f"Image too large: {image.width}x{image.height}")
            image.load()
            return image.copy()

    def _prepare_text(self, data: dict) -> tuple:
        coords = self._coords(data)
        fp = data.get("font_props")
        if not isinstance(fp, dict):
            raise ValueError("Invalid or missing font_props")
        for key in ("family", "size", "slant", "weight", "underline", "kerning"):
            if key not in fp:
                raise ValueError(f"font_props missing '{key}'")
        if not isinstance(fp["family"], str) or len(fp["family"]) > 256:
            raise ValueError("font family must be a string of at most 256 characters")
        if not isinstance(fp["size"], int | float) or not (1 <= fp["size"] <= 500):
            raise ValueError("font size must be between 1 and 500")
        if (
            not isinstance(fp["kerning"], int | float)
            or not math.isfinite(fp["kerning"])
            or not (-100 <= fp["kerning"] <= 100)
        ):
            raise ValueError("font kerning must be finite and between -100 and 100")
        if fp["slant"] not in ("roman", "italic") or fp["weight"] not in ("normal", "bold"):
            raise ValueError("Invalid font style")
        if not isinstance(fp["underline"], bool):
            raise ValueError("font underline must be a bool")
        if not isinstance(data.get("content"), str) or len(data["content"]) > 10_000:
            raise ValueError("content must be a string of at most 10,000 characters")
        with self._decode_png(data.get("font_image")) as image:
            photo = ImageTk.PhotoImage(image)
        return coords, {"font_image": photo, "font_props": fp, "content": data["content"], "handle": None, "bbox": None}

    def _prepare_image(self, data: dict) -> tuple:
        coords = self._coords(data)
        original = self._decode_png(data.get("original_image"))
        try:
            with self._decode_png(data.get("image")) as image:
                photo = ImageTk.PhotoImage(image)
            return coords, {"image": photo, "original_image": original, "handle": None, "bbox": None}
        except BaseException:
            original.close()
            raise

    def _place_item(self, kind: str, prepared: tuple) -> None:
        coords, props = prepared
        widget = props["font_image"] if kind == "text" else props["image"]
        item_id = self.canvas_state.canvas.create_image(*coords, image=widget, anchor="nw")
        if kind == "text":
            self.canvas_state.text_items[item_id] = props
            self._on_bind_text_select(item_id)
        else:
            self.canvas_state.image_items[item_id] = props
            self._on_bind_image_select(item_id)

    def load_text(self, data: dict[str, object]) -> None:
        try:
            self._place_item("text", self._prepare_text(data))
        except (OSError, ValueError, TypeError, KeyError, PIL.UnidentifiedImageError, tk.TclError) as e:
            messagebox.showwarning("Warning", f"Failed to load text item: {e}")

    def load_image(self, data: dict[str, object]) -> None:
        prepared = None
        try:
            prepared = self._prepare_image(data)
            self._place_item("image", prepared)
        except (OSError, ValueError, TypeError, KeyError, PIL.UnidentifiedImageError, tk.TclError) as e:
            if prepared is not None:
                prepared[1]["original_image"].close()
            messagebox.showwarning("Warning", f"Failed to load image item: {e}")
