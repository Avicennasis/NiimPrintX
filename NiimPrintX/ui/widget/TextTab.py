import threading
import tkinter as tk
from tkinter import font as tk_font
from tkinter import ttk

from ..component.FontList import fonts
from .TextOperation import TextOperation


class TextTab:
    def __init__(self, parent, config):
        self.parent = parent
        self.config = config
        self.frame = ttk.Frame(parent)
        self.text_op = TextOperation(self, config)
        self.fonts = {}  # populated async by _load_fonts thread
        self.create_widgets()
        threading.Thread(target=self._load_fonts, daemon=True).start()

    def _load_fonts(self):
        """Load system fonts in a background thread to avoid blocking the UI."""
        import contextlib  # noqa: PLC0415

        result = fonts()
        self.fonts = result
        with contextlib.suppress(tk.TclError):
            self.frame.after(0, lambda: self.font_family_dropdown.config(values=list(result.keys())))

    def create_widgets(self):
        if self.config.os_system == "Darwin":
            default_bg = "systemWindowBackgroundColor1"
        elif self.config.os_system == "Windows":
            default_bg = "systemButtonFace"
        else:
            default_bg = "grey85"

        # Content label and multi-line text entry with scrollbar
        tk.Label(self.frame, text="Content", bg=default_bg).grid(row=0, column=0, sticky="nw")

        # Create frame to hold text widget and scrollbar
        text_frame = tk.Frame(self.frame, bg=default_bg)
        text_frame.grid(row=0, column=1, sticky="ew", padx=5)

        self.content_entry = tk.Text(text_frame, highlightbackground=default_bg, height=3, width=30)
        self.content_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add scrollbar for longer text
        scrollbar = tk.Scrollbar(text_frame, command=self.content_entry.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.content_entry.config(yscrollcommand=scrollbar.set)

        self.content_entry.insert("1.0", "Text")

        self.sample_text_label = tk.Label(self.frame, text="Sample Text", font=("Arial", 14), bg=default_bg)
        self.sample_text_label.grid(row=0, column=2, sticky="w", columnspan=3)

        tk.Label(self.frame, text="Font Family", bg=default_bg).grid(row=1, column=0, sticky="w")
        self.font_family_dropdown = ttk.Combobox(self.frame, values=list(self.fonts.keys()))
        self.font_family_dropdown.grid(row=1, column=1, sticky="ew", padx=5)
        self.font_family_dropdown.set("Arial")
        self.font_family_dropdown.bind("<<ComboboxSelected>>", self.update_text_properties)
        # Initialize sample text label with default font
        self.sample_text_label.config(font=tk_font.Font(family="Arial", size=14), text="Text in Arial")

        self.bold_var = tk.BooleanVar()
        bold_button = tk.Checkbutton(
            self.frame, text="Bold", variable=self.bold_var, bg=default_bg, command=self.update_text_properties
        )
        bold_button.grid(row=1, column=2, sticky="w")
        self.italic_var = tk.BooleanVar()
        italic_button = tk.Checkbutton(
            self.frame, text="Italic", variable=self.italic_var, bg=default_bg, command=self.update_text_properties
        )
        italic_button.grid(row=1, column=3, sticky="w")
        self.underline_var = tk.BooleanVar()
        underline_button = tk.Checkbutton(
            self.frame,
            text="Underline",
            variable=self.underline_var,
            bg=default_bg,
            command=self.update_text_properties,
        )
        underline_button.grid(row=1, column=4, sticky="w")

        tk.Label(self.frame, text="Font Size", bg=default_bg).grid(row=2, column=0, sticky="w")
        self.size_var = tk.IntVar()
        self.size_var.set(16)
        self.font_size_dropdown = tk.Spinbox(
            self.frame,
            from_=4,
            to=100,
            textvariable=self.size_var,
            highlightbackground=default_bg,
            command=self.update_text_properties,
        )
        self.font_size_dropdown.bind("<FocusOut>", self.update_text_properties)
        self.font_size_dropdown.grid(row=2, column=1, sticky="ew", padx=5)

        tk.Label(self.frame, text="Font Kerning", bg=default_bg).grid(row=3, column=0, sticky="w")
        self.kerning_var = tk.StringVar()
        self.kerning_var.set("0")
        self.font_kerning_dropdown = tk.Spinbox(
            self.frame,
            from_=0,
            to=20,
            increment=0.1,
            format="%.1f",
            textvariable=self.kerning_var,
            highlightbackground=default_bg,
            command=self.update_text_properties,
        )
        self.font_kerning_dropdown.bind("<FocusOut>", self.update_text_properties)
        self.font_kerning_dropdown.grid(row=3, column=1, sticky="ew", padx=5)

        button_frame = tk.Frame(self.frame)
        self.add_button = tk.Button(
            button_frame, text="Add", highlightbackground=default_bg, command=self.text_op.add_text_to_canvas
        )

        self.delete_button = tk.Button(
            button_frame, text="Delete", highlightbackground=default_bg, command=self.text_op.delete_text
        )
        self.add_button.pack(side=tk.LEFT)
        self.delete_button.pack(side=tk.LEFT)
        button_frame.grid(row=4, column=1, sticky="w")

    def update_text_properties(self, event=None):
        font_props = self.get_font_properties()
        content = self.content_entry.get("1.0", "end-1c")
        label_font = tk_font.Font(
            family=font_props["family"], size=14, weight=font_props["weight"], slant=font_props["slant"]
        )
        self.sample_text_label.config(font=label_font, text=f"{content} in {font_props['family'].replace('-', ' ')}")
        if self.config.current_selected:
            self.text_op.update_canvas_text(self.config.current_selected)

    def get_font_properties(self):
        family = self.font_family_dropdown.get().strip()
        if not family or family not in self.fonts:
            family = next(iter(self.fonts), "Arial")
        try:
            size = max(4, min(int(self.font_size_dropdown.get()), 500))
        except (ValueError, tk.TclError):
            size = 16
        self.size_var.set(size)
        try:
            kerning = float(self.font_kerning_dropdown.get())
        except (ValueError, tk.TclError):
            kerning = 0.0
            self.kerning_var.set("0")
        weight = "bold" if self.bold_var.get() else "normal"
        slant = "italic" if self.italic_var.get() else "roman"
        underline = self.underline_var.get()

        return {
            "family": family,
            "size": size,
            "kerning": kerning,
            "weight": weight,
            "slant": slant,
            "underline": underline,
        }

    def get_text_operation(self):
        return self.text_op
