from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from NiimPrintX.ui.config import CanvasState, ImmutableConfig, PrinterState, mm_to_pixels

from .CanvasOperation import CanvasOperation

if TYPE_CHECKING:
    from NiimPrintX.ui.widget.ImageOperation import ImageOperation
    from NiimPrintX.ui.widget.TextOperation import TextOperation


class CanvasSelector:
    def __init__(
        self,
        parent: tk.Tk,
        immutable: ImmutableConfig,
        canvas_state: CanvasState,
        printer: PrinterState,
        text_op: TextOperation,
        img_op: ImageOperation,
    ) -> None:
        self.parent: tk.Tk = parent
        self.immutable: ImmutableConfig = immutable
        self.canvas_state: CanvasState = canvas_state
        self.printer: PrinterState = printer
        self.frame: ttk.Frame = ttk.Frame(parent)
        self.canvas_op: CanvasOperation = CanvasOperation(canvas_state, text_op, img_op)
        self.create_widgets()

    def create_widgets(self) -> None:
        device_label = tk.Label(self.frame, text="Device")
        device_label.pack(side=tk.LEFT, padx=10)
        self.selected_device = tk.StringVar(value=self.printer.device.upper())
        device_option = ttk.Combobox(
            self.frame,
            textvariable=self.selected_device,
            values=[x.upper() for x in self.immutable.label_sizes],
            state="readonly",
        )
        device_option.pack(side=tk.LEFT, padx=10)
        device_option.bind("<<ComboboxSelected>>", self.update_device_label_size)
        label_size_label = tk.Label(self.frame, text="Label size")
        label_size_label.pack(side=tk.LEFT, padx=10)
        self.selected_label_size = tk.StringVar()
        self.label_size_option = ttk.Combobox(self.frame, textvariable=self.selected_label_size, state="readonly")
        self.update_device_label_size()
        self.label_size_option.pack(side=tk.LEFT, padx=10)
        self.label_size_option.bind("<<ComboboxSelected>>", self.update_canvas_size)
        self.update_canvas_size()
        self.frame.pack(side=tk.LEFT)

    def update_device_label_size(self, event: tk.Event | None = None) -> None:
        device = self.selected_device.get().lower()
        if device:
            # Reset connection state when device changes
            if device != self.printer.device:
                self.printer.printer_connected = False
            label_sizes = list(self.immutable.label_sizes[device]["size"].keys())
            self.printer.device = device
        else:
            label_sizes = []
        self.label_size_option["values"] = label_sizes
        if label_sizes:
            self.label_size_option.current(0)
        else:
            self.selected_label_size.set("")
        self.update_canvas_size()

    def update_canvas_size(self, event: tk.Event | None = None) -> None:
        """Update the canvas size based on the selected label size."""
        device = self.selected_device.get().lower()
        label_size = self.selected_label_size.get()
        if not device or device not in self.immutable.label_sizes or not label_size:
            return
        self.printer.device = device
        self.printer.current_label_size = label_size
        label_width_mm, label_height_mm = self.immutable.label_sizes[self.printer.device]["size"][
            self.printer.current_label_size
        ]

        # Convert the label size to pixels
        dpi = self.immutable.label_sizes[self.printer.device]["print_dpi"]
        self.bounding_box_width = mm_to_pixels(label_width_mm, dpi)
        self.bounding_box_height = mm_to_pixels(label_height_mm, dpi)

        self.print_area_width = max(1, self.bounding_box_width - mm_to_pixels(2, dpi))
        self.print_area_height = max(1, self.bounding_box_height - mm_to_pixels(4, dpi))

        # Set the new canvas dimensions with padding
        padding = 150  # total canvas padding
        self.canvas_width = self.bounding_box_width + padding
        self.canvas_height = self.bounding_box_height + padding

        # If a canvas exists, destroy it and clear stale items
        if hasattr(self.canvas_state, "canvas") and self.canvas_state.canvas is not None:
            self.canvas_state.canvas.unbind("<Button-1>")
            self.canvas_state.canvas.destroy()
        for item in self.canvas_state.text_items.values():
            if "font_image" in item and hasattr(item["font_image"], "close"):
                with contextlib.suppress(Exception):
                    item["font_image"].close()
        self.canvas_state.text_items = {}
        for item in self.canvas_state.image_items.values():
            orig = item.get("original_image")
            if orig is not None:
                with contextlib.suppress(Exception):
                    orig.close()
        self.canvas_state.image_items = {}
        self.canvas_state.current_selected = None
        self.canvas_state.current_selected_image = None

        # Create a new canvas with updated dimensions
        self.canvas_state.canvas = tk.Canvas(
            self.canvas_state.frames["top_frame"],
            width=self.canvas_width,
            height=self.canvas_height,
            highlightthickness=0,
            bg="lightgray",
        )
        self.canvas_state.canvas.pack(padx=0, pady=0)

        # Create a centered bounding box
        x_center = self.canvas_width // 2
        y_center = self.canvas_height // 2

        self.canvas_state.bounding_box = self.canvas_state.canvas.create_rectangle(
            x_center - self.bounding_box_width // 2,
            y_center - self.bounding_box_height // 2,
            x_center + self.bounding_box_width // 2,
            y_center + self.bounding_box_height // 2,
            outline="blue",
            width=1,
            fill="white",
            tags="label_box",
        )

        self.canvas_state.canvas.create_rectangle(
            x_center - self.print_area_width // 2,
            y_center - self.print_area_height // 2,
            x_center + self.print_area_width // 2,
            y_center + self.print_area_height // 2,
            outline="red",
            width=1,
            dash=(4, 4),
            fill="white",
            tags="label_box",
        )

        self.canvas_state.canvas.bind("<Button-1>", self.canvas_op.canvas_click_handler)
