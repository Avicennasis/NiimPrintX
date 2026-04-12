from __future__ import annotations

import tkinter as tk
from typing import Any


class StatusBar:
    def __init__(self, parent: tk.Tk, config: Any) -> None:
        self.parent = parent
        self.config = config
        self.create_widgets()

    def create_widgets(self) -> None:
        """Create a status bar at the bottom of the tkinter application with a status message."""

        # Create a frame for the status bar at the bottom of the root window
        self.status_frame = tk.Frame(self.parent, bd=1, relief=tk.SUNKEN)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Create a canvas for the status circle
        self.circle_canvas = tk.Canvas(self.status_frame, width=20, height=20, bd=0, highlightthickness=0)
        self.circle_id = self.circle_canvas.create_oval(4, 4, 16, 16, fill="red")
        self.circle_canvas.pack(side=tk.RIGHT, padx=10, pady=5)

        # Create a label for the status message
        self.status_label = tk.Label(self.status_frame, text="Not Connected", fg="red", font=("Arial", 10))
        self.status_label.pack(side=tk.RIGHT, padx=5)

    def update_status(self, connection: bool = True) -> None:
        """Update the status message and circle color to indicate connection."""

        if connection:
            text = "Connected"
            color = "green"
        else:
            text = "Not Connected"
            color = "red"
        try:
            self.status_label.config(text=text, fg=color)
            self.circle_canvas.itemconfig(self.circle_id, fill=color)
        except tk.TclError:
            pass
