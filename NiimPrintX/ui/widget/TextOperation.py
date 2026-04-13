from __future__ import annotations

import base64
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING, Any

try:
    from wand.color import Color
    from wand.drawing import Drawing as WandDrawing
    from wand.image import Image as WandImage
except ImportError:
    WandImage = None
    WandDrawing = None
    Color = None

if TYPE_CHECKING:
    from NiimPrintX.ui.config import CanvasState
    from NiimPrintX.ui.types import FontProps

    from .TextTab import TextTab


class TextOperation:
    def __init__(self, parent: TextTab, canvas_state: CanvasState) -> None:
        self.parent: TextTab = parent
        self.canvas_state: CanvasState = canvas_state

    # Function to add text to canvas and make it draggable
    def create_text_image(self, font_props: FontProps, text: str) -> tk.PhotoImage | None:
        if WandImage is None:
            raise ImportError("GUI extras not installed. Run: pip install NiimPrintX[gui]")
        if not text or not text.strip():
            return None
        with WandDrawing() as draw:
            draw.font_family = font_props["family"]
            draw.font_size = font_props["size"]
            if font_props["slant"] == "italic":
                draw.font_style = "italic"
            if font_props["weight"] == "bold":
                draw.font_weight = 700
            if font_props["underline"]:
                draw.text_decoration = "underline"
            draw.text_kerning = font_props["kerning"]
            draw.fill_color = Color("black")
            # Get font metrics using a context-managed probe image
            with WandImage(width=1, height=1) as probe:
                metrics = draw.get_font_metrics(probe, text, multiline=True)
            text_width = max(1, int(metrics.text_width) + 5)
            text_height = max(1, int(metrics.text_height) + 2)

            with WandImage(width=text_width, height=text_height, background=Color("transparent")) as img:
                draw.text(x=2, y=int(metrics.ascender), body=text)
                draw(img)

                # Ensure the image is in RGBA format
                img.format = "png"
                img.alpha_channel = "activate"  # Ensure alpha channel is active
                img_blob = img.make_blob("png")
                # Convert to format displayable in Tkinter
                return tk.PhotoImage(data=base64.b64encode(img_blob).decode("ascii"))

    def add_text_to_canvas(self) -> None:
        # Get the current text in the content_entry Entry widget
        text: str = self.parent.content_entry.get("1.0", "end-1c")

        font_props: FontProps = self.parent.get_font_properties()
        if not text:
            messagebox.showerror("Error", "Please enter text in content to add.")
            return

        tk_image: tk.PhotoImage | None = self.create_text_image(font_props, text)
        if tk_image is None:
            return
        text_id: int = self.canvas_state.canvas.create_image(
            0,
            0,
            image=tk_image,
            anchor="nw",
        )

        self.canvas_state.canvas.tag_bind(
            text_id, "<Button-1>", lambda event, tid=text_id: self.select_text(event, tid)
        )
        self.canvas_state.text_items[text_id] = {
            "font_props": font_props,
            "font_image": tk_image,
            "content": text,
            "handle": None,
            "bbox": None,
        }

    def delete_text(self) -> None:
        if self.canvas_state.current_selected and self.canvas_state.current_selected in self.canvas_state.text_items:
            self.canvas_state.canvas.delete(self.canvas_state.current_selected)
            item: dict[str, Any] = self.canvas_state.text_items[self.canvas_state.current_selected]
            if item.get("bbox") is not None:
                self.canvas_state.canvas.delete(item["bbox"])
            if item.get("handle") is not None:
                self.canvas_state.canvas.delete(item["handle"])
            del self.canvas_state.text_items[self.canvas_state.current_selected]
            self.canvas_state.current_selected = None
            self.parent.add_button.config(text="Add", command=self.add_text_to_canvas)

    def select_text(self, event: tk.Event, text_id: int) -> None:
        self.deselect_text()
        self.canvas_state.current_selected = text_id
        self.update_widgets(text_id)
        self.draw_bounding_box(event, text_id)

    def update_widgets(self, text_id: int) -> None:
        font_prop: FontProps = self.canvas_state.text_items[text_id]["font_props"]
        text: str = self.canvas_state.text_items[text_id]["content"]

        self.parent.content_entry.delete("1.0", tk.END)
        self.parent.content_entry.insert("1.0", text)

        self.parent.font_family_dropdown.set(font_prop["family"])
        self.parent.size_var.set(font_prop["size"])
        self.parent.kerning_var.set(font_prop["kerning"])

        self.parent.italic_var.set(font_prop["slant"] != "roman")
        self.parent.bold_var.set(font_prop["weight"] != "normal")
        self.parent.underline_var.set(bool(font_prop["underline"]))

        self.parent.add_button.config(text="Update", command=lambda t_id=text_id: self.update_canvas_text(t_id))

    def update_canvas_text(self, text_id: int) -> None:
        if text_id not in self.canvas_state.text_items:
            return  # item was deleted during debounce window
        text: str = self.parent.content_entry.get("1.0", "end-1c")
        font_props: FontProps = self.parent.get_font_properties()
        tk_image: tk.PhotoImage | None = self.create_text_image(font_props, text)
        if tk_image is None:
            return
        self.canvas_state.text_items[text_id]["content"] = text
        self.canvas_state.text_items[text_id]["font_props"] = font_props
        self.canvas_state.canvas.itemconfig(text_id, image=tk_image)
        self.canvas_state.text_items[text_id]["font_image"] = tk_image
        self.update_bbox_and_handle(text_id)

    def draw_bounding_box(self, event: tk.Event, text_id: int) -> None:
        bb: tuple[int, int, int, int] | None = self.canvas_state.canvas.bbox(text_id)
        if bb is None:
            return
        bbox: int = self.canvas_state.canvas.create_rectangle(bb, outline="blue", width=2, tags="bounding_box")
        handle: int = self.canvas_state.canvas.create_oval(
            bb[2] - 5, bb[3] - 5, bb[2] + 5, bb[3] + 5, outline="blue", fill="gray"
        )
        self.canvas_state.text_items[text_id].update(
            {
                "bbox": bbox,
                "handle": handle,
                "initial_x": event.x,
                "initial_y": event.y,
                "initial_size": self.canvas_state.text_items[text_id]["font_props"]["size"],
            }
        )

        self.canvas_state.canvas.tag_unbind(text_id, "<B1-Motion>")
        self.canvas_state.canvas.tag_bind(text_id, "<B1-Motion>", lambda e, tid=text_id: self.move_text(e, tid))
        self.canvas_state.canvas.tag_bind(handle, "<B1-Motion>", lambda e, tid=text_id: self.resize_text(e, tid))
        self.canvas_state.canvas.tag_bind(handle, "<Button-1>", lambda e: self.start_resize(e, text_id))

    def move_text(self, event: tk.Event, text_id: int) -> None:
        if text_id not in self.canvas_state.text_items:
            return
        if self.canvas_state.text_items[text_id].get("bbox") is None:
            return
        dx: int = event.x - self.canvas_state.text_items[text_id]["initial_x"]
        dy: int = event.y - self.canvas_state.text_items[text_id]["initial_y"]
        self.canvas_state.canvas.move(text_id, dx, dy)
        self.canvas_state.canvas.move(self.canvas_state.text_items[text_id]["bbox"], dx, dy)
        self.canvas_state.canvas.move(self.canvas_state.text_items[text_id]["handle"], dx, dy)
        self.canvas_state.text_items[text_id]["initial_x"] = event.x
        self.canvas_state.text_items[text_id]["initial_y"] = event.y

    def start_resize(self, event: tk.Event, text_id: int) -> None:
        self.canvas_state.text_items[text_id]["initial_x"] = event.x
        self.canvas_state.text_items[text_id]["initial_y"] = event.y
        self.canvas_state.text_items[text_id]["initial_size"] = self.canvas_state.text_items[text_id]["font_props"][
            "size"
        ]

    def resize_text(self, event: tk.Event, text_id: int) -> None:
        if text_id not in self.canvas_state.text_items:
            return
        dy: int = event.y - self.canvas_state.text_items[text_id]["initial_y"]
        new_size: int = max(8, self.canvas_state.text_items[text_id]["initial_size"] + round(dy / 10))
        # Skip expensive re-render if size hasn't actually changed
        if new_size == self.canvas_state.text_items[text_id]["font_props"]["size"]:
            return
        tk_image: tk.PhotoImage | None = self.create_text_image(
            {**self.canvas_state.text_items[text_id]["font_props"], "size": new_size},
            self.canvas_state.text_items[text_id]["content"],
        )
        if tk_image is None:
            return
        self.canvas_state.text_items[text_id]["font_props"]["size"] = new_size
        self.canvas_state.canvas.itemconfig(text_id, image=tk_image)
        self.canvas_state.text_items[text_id]["font_image"] = tk_image
        self.update_bbox_and_handle(text_id)

        self.parent.size_var.set(new_size)

    def update_bbox_and_handle(self, text_id: int) -> None:
        if self.canvas_state.text_items[text_id].get("bbox") is None:
            return
        bbox_coords: tuple[int, int, int, int] | None = self.canvas_state.canvas.bbox(text_id)
        if bbox_coords is None:
            return
        self.canvas_state.canvas.coords(self.canvas_state.text_items[text_id]["bbox"], bbox_coords)
        self.canvas_state.canvas.coords(
            self.canvas_state.text_items[text_id]["handle"],
            bbox_coords[2] - 5,
            bbox_coords[3] - 5,
            bbox_coords[2] + 5,
            bbox_coords[3] + 5,
        )

    def deselect_text(self) -> None:
        if self.canvas_state.current_selected:
            self.delete_bounding_box(self.canvas_state.current_selected)
            self.canvas_state.current_selected = None
            self.parent.add_button.config(text="Add", command=self.add_text_to_canvas)

    def delete_bounding_box(self, text_id: int) -> None:
        if self.canvas_state.text_items[text_id].get("bbox") is not None:
            self.canvas_state.canvas.delete(self.canvas_state.text_items[text_id]["bbox"])
            self.canvas_state.canvas.delete(self.canvas_state.text_items[text_id]["handle"])
            self.canvas_state.text_items[text_id]["bbox"] = None
            self.canvas_state.text_items[text_id]["handle"] = None
