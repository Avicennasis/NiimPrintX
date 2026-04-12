from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

from .ImageOperation import ImageOperation
from .TabbedIconGrid import TabbedIconGrid

if TYPE_CHECKING:
    from NiimPrintX.ui.config import CanvasState, ImmutableConfig


class IconTab:
    def __init__(self, parent: ttk.Notebook, immutable: ImmutableConfig, canvas_state: CanvasState) -> None:
        self.parent: ttk.Notebook = parent
        self.immutable: ImmutableConfig = immutable
        self.canvas_state: CanvasState = canvas_state
        self.frame: ttk.Frame = ttk.Frame(parent)
        self.image_op: ImageOperation = ImageOperation(canvas_state)
        self.create_widgets()

    def create_widgets(self) -> None:
        if self.immutable.os_system == "Darwin":
            default_bg = "systemWindowBackgroundColor1"
        elif self.immutable.os_system == "Windows":
            default_bg = "systemButtonFace"
        else:
            default_bg = "grey85"
        icon_tab_frame = tk.Frame(self.frame, bg=default_bg)
        icon_tab_frame.pack(fill="both", expand=True)

        # Define a grid structure to arrange elements
        icon_tab_frame.columnconfigure(0, minsize=50, weight=0)  # For the buttons on the left
        icon_tab_frame.columnconfigure(1, weight=1)  # For the grid on the right

        # Create a frame for the buttons and stack them vertically
        button_frame = tk.Frame(icon_tab_frame, bg=default_bg, pady=50)
        button_frame.grid(row=0, column=0, sticky="ns")  # Left side, vertically stacked

        # Add the buttons to the frame
        load_image = tk.Button(
            button_frame, text="Add Image", width=10, highlightbackground=default_bg, command=self.import_image
        )
        delete_image = tk.Button(
            button_frame, text="Delete", width=10, highlightbackground=default_bg, command=self.image_op.delete_image
        )

        # Stack the buttons vertically
        load_image.pack(pady=5)  # Adjust padding as needed
        delete_image.pack(pady=5)

        # Create the TabbedIconGrid and align it to the right
        tabbed_icon_grid = TabbedIconGrid(
            icon_tab_frame,
            self.immutable.icon_folder,
            on_icon_selected=lambda sub_path: self.image_op.load_image(
                os.path.join(self.immutable.icon_folder, sub_path)
            ),
        )

        tabbed_icon_grid.grid(row=0, column=1, sticky="nsew", padx=10, pady=20)
        icon_tab_frame.rowconfigure(0, weight=1)

    def import_image(self) -> None:
        """Load an image into the canvas."""
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.gif")])

        if not file_path:
            return
        self.image_op.load_image(file_path)

    def get_image_operation(self) -> ImageOperation:
        return self.image_op
