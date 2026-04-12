import base64
import contextlib
import io
import json
import os
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox

import PIL
from PIL import Image, ImageTk

_MAX_LABEL_PIXELS = 5_000_000  # well above any real label dimensions
_MAX_ITEMS_PER_FILE = 100

PIL.Image.MAX_IMAGE_PIXELS = _MAX_LABEL_PIXELS


class FileMenu:
    def __init__(self, root, parent, config):
        self.root = root
        self.parent = parent
        self.config = config
        self.create_menu()

    def create_menu(self):
        file_menu = tk.Menu(self.parent, tearoff=0)
        self.parent.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save", command=self.save_to_file)
        file_menu.add_command(label="Open", command=self.load_from_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)

    def on_close(self):
        self.root.on_close()

    def save_to_file(self):
        try:
            file_path = filedialog.asksaveasfilename(defaultextension=".niim", filetypes=[("NIIM files", "*.niim")])
            if not file_path:
                return

            data = {
                "device": self.config.device,
                "current_label_size": self.config.current_label_size,
                "text": {},
                "image": {},
            }
            if self.config.text_items:
                for text_id, properties in self.config.text_items.items():
                    font_image_widget = properties["font_image"]
                    # Handle both tk.PhotoImage (from Wand) and ImageTk.PhotoImage (from load)
                    if isinstance(font_image_widget, ImageTk.PhotoImage):
                        pil_image = ImageTk.getimage(font_image_widget)
                    else:
                        # tk.PhotoImage — extract PNG via Tk call
                        png_b64 = font_image_widget.tk.call(str(font_image_widget), "data", "-format", "png")
                        pil_image = Image.open(io.BytesIO(base64.b64decode(png_b64)))
                    with io.BytesIO() as buffer:
                        pil_image.save(buffer, format="PNG")
                        buffer.seek(0)
                        font_img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")

                    item_data = {
                        "content": properties["content"],
                        "coords": self.config.canvas.coords(text_id),
                        "font_props": properties["font_props"],
                        "font_image": font_img_str,
                    }
                    data["text"][str(text_id)] = item_data

            if self.config.image_items:
                for image_id, properties in self.config.image_items.items():
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
                        "coords": self.config.canvas.coords(image_id),
                    }
                    data["image"][str(image_id)] = item_data

            dir_name = os.path.dirname(file_path) or "."
            with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, suffix=".tmp") as tf:
                tmp_path = tf.name
                json.dump(data, tf, indent=2)
            os.replace(tmp_path, file_path)
        except (OSError, ValueError, TypeError, tk.TclError) as e:
            messagebox.showerror("Error", f"Failed to save: {e}")

    def load_from_file(self, file_path=None):
        if file_path is None:
            file_path = filedialog.askopenfilename(filetypes=[("NIIM files", "*.niim")])
        if file_path:
            try:
                with open(file_path) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
                messagebox.showerror(
                    "Error",
                    f"Failed to open file: {e}\n\n"
                    "Only JSON .niim files are supported. Legacy pickle "
                    "files must be re-saved from an older version first.",
                )
                return

            # Validate required keys
            for key in ("device", "current_label_size", "text", "image"):
                if key not in data:
                    messagebox.showerror("Error", f"Invalid .niim file: missing '{key}'")
                    return

            if not isinstance(data.get("device"), str) or not isinstance(data.get("current_label_size"), str):
                messagebox.showerror("Error", "Invalid .niim file: 'device' and 'current_label_size' must be strings.")
                return

            existing_items = len(self.config.text_items) + len(self.config.image_items)
            file_items = len(data.get("text", {})) + len(data.get("image", {}))
            total_items = existing_items + file_items
            if total_items > _MAX_ITEMS_PER_FILE:
                messagebox.showerror(
                    "Error",
                    f"File contains too many items ({total_items}). Maximum is {_MAX_ITEMS_PER_FILE}.",
                )
                return

            device = data.get("device", "").lower()
            label_size = data.get("current_label_size", "")
            if device not in self.config.label_sizes:
                messagebox.showerror("Error", f"Device '{device}' not found in configuration.")
                return
            if label_size not in self.config.label_sizes[device].get("size", {}):
                messagebox.showerror("Error", f"Label size '{label_size}' not found for device '{device}'.")
                return

            with contextlib.suppress(Exception):
                if self.config.current_selected:
                    self.root.text_tab.text_op.deselect_text()
                if self.config.current_selected_image:
                    self.root.icon_tab.image_op.deselect_image()

            self.root.canvas_selector.selected_device.set(data["device"].upper())
            self.root.canvas_selector.update_device_label_size()  # repopulate label dropdown
            self.root.canvas_selector.selected_label_size.set(data["current_label_size"])
            self.root.canvas_selector.update_canvas_size()  # resize canvas to the saved label size

            if data.get("text"):
                for item_data in data["text"].values():
                    self.load_text(item_data)

            if data.get("image"):
                for item_data in data["image"].values():
                    self.load_image(item_data)

    def load_text(self, data):
        try:
            # Validate coords
            coords = data.get("coords")
            if (
                not isinstance(coords, (list, tuple))
                or len(coords) < 2
                or not all(isinstance(c, (int, float)) for c in coords[:2])
            ):
                raise ValueError("Invalid or missing coords: expected a list with at least 2 numeric elements")

            # Validate font_props
            fp = data.get("font_props")
            if not isinstance(fp, dict):
                raise ValueError("Invalid or missing font_props: expected a dict")
            if "size" not in fp or not isinstance(fp["size"], (int, float)) or not (1 <= fp["size"] <= 500):
                raise ValueError("font_props['size'] must be a number between 1 and 500")
            if "kerning" in fp and not isinstance(fp["kerning"], (int, float)):
                raise ValueError("font_props['kerning'] must be a number")

            # Validate content
            if not isinstance(data.get("content"), str):
                raise ValueError("'content' must be a string")

            font_img_data = base64.b64decode(data["font_image"])
            font_image = Image.open(io.BytesIO(font_img_data))
            if font_image.width * font_image.height > _MAX_LABEL_PIXELS:
                w, h = font_image.width, font_image.height
                font_image.close()
                raise ValueError(f"Image too large: {w}x{h}")
            font_image.load()
            font_img_tk = ImageTk.PhotoImage(font_image)
            font_image.close()
            text_id = self.config.canvas.create_image(coords[0], coords[1], image=font_img_tk, anchor="nw")
            self.config.canvas.tag_bind(
                text_id, "<Button-1>", lambda event, tid=text_id: self.root.text_tab.text_op.select_text(event, tid)
            )

            self.config.text_items[text_id] = {
                "font_image": font_img_tk,
                "font_props": fp,
                "content": data["content"],
                "handle": None,
                "bbox": None,
            }
        except (OSError, ValueError, TypeError, KeyError, PIL.UnidentifiedImageError) as e:
            messagebox.showwarning("Warning", f"Failed to load text item: {e}")

    def load_image(self, data):
        try:
            # Validate coords
            coords = data.get("coords")
            if (
                not isinstance(coords, (list, tuple))
                or len(coords) < 2
                or not all(isinstance(c, (int, float)) for c in coords[:2])
            ):
                raise ValueError("Invalid or missing coords: expected a list with at least 2 numeric elements")

            original_image_data = base64.b64decode(data["original_image"])
            original_image = Image.open(io.BytesIO(original_image_data))
            if original_image.width * original_image.height > _MAX_LABEL_PIXELS:
                w, h = original_image.width, original_image.height
                original_image.close()
                raise ValueError(f"Image too large: {w}x{h}")
            original_image.load()

            image_data = base64.b64decode(data["image"])
            image = Image.open(io.BytesIO(image_data))
            if image.width * image.height > _MAX_LABEL_PIXELS:
                w, h = image.width, image.height
                image.close()
                raise ValueError(f"Resized image too large: {w}x{h}")
            image.load()  # force decode before BytesIO is GC'd
            img_tk = ImageTk.PhotoImage(image)
            image.close()
            image_id = self.config.canvas.create_image(coords[0], coords[1], image=img_tk, anchor="nw")

            self.config.image_items[image_id] = {
                "image": img_tk,
                "original_image": original_image,
                "bbox": None,
                "handle": None,
            }

            self.config.canvas.tag_bind(
                image_id,
                "<Button-1>",
                lambda event, img_id=image_id: self.root.icon_tab.image_op.select_image(event, img_id),
            )
            self.config.canvas.tag_bind(
                image_id, "<B1-Motion>", lambda e, img_id=image_id: self.root.icon_tab.image_op.move_image(e, img_id)
            )
        except (OSError, ValueError, TypeError, KeyError, PIL.UnidentifiedImageError) as e:
            messagebox.showwarning("Warning", f"Failed to load image item: {e}")
