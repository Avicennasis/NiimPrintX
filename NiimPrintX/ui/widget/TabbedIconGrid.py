import os
import math
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import threading

class TabbedIconGrid(tk.Frame):
    def __init__(self, parent, base_folder, icon_size=(50, 50), columns=8, on_icon_selected=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.base_folder = base_folder
        self.icon_size = icon_size
        self.columns = columns
        self.on_icon_selected = on_icon_selected
        self.icon_cache = {}  # Store loaded icons to avoid redundant processing
        self.icon_references = {}  # Prevent PhotoImage GC

        self.notebook = ttk.Notebook(self)
        self.create_tabs()
        self.notebook.pack(fill="both", expand=True)

    def create_tabs(self):
        """Create a tab for each subfolder."""
        for subfolder in sorted(os.listdir(self.base_folder)):
            subfolder_path = os.path.join(self.base_folder, subfolder)
            if os.path.isdir(subfolder_path):
                tab_frame = tk.Frame(self.notebook)
                self.notebook.add(tab_frame, text=subfolder.capitalize())
        self.notebook.bind("<<NotebookTabChanged>>", self.load_tab_icons)

    def load_tab_icons(self, event):
        """Load icons when a tab is selected."""
        notebook = event.widget
        selected_tab_index = notebook.index(notebook.select())  # Get the selected tab index
        subfolder_name = notebook.tab(selected_tab_index, "text").lower()

        # Get the corresponding tab frame
        tab_frame = notebook.nametowidget(notebook.tabs()[selected_tab_index])

        # Check if icons are cached and load asynchronously if not
        if subfolder_name not in self.icon_cache:
            subfolder_path = os.path.join(self.base_folder, subfolder_name)
            self.icon_cache[subfolder_name] = self.create_icon_grid(tab_frame, subfolder_path, subfolder_name)
            self.icon_cache[subfolder_name].bind("<MouseWheel>",
                                                 lambda e, canvas=self.icon_cache[subfolder_name]: self.on_mouse_wheel(
                                                     e, canvas))

        # Ensure the correct canvas is used for mouse wheel event
        self.icon_cache[subfolder_name].configure(scrollregion=self.icon_cache[subfolder_name].bbox("all"))
        self.icon_cache[subfolder_name].bind("<MouseWheel>",
                                             lambda e, canvas=self.icon_cache[subfolder_name]: self.on_mouse_wheel(e,
                                                                                                                   canvas))

    def create_icon_grid(self, parent, folder, subfolder_name):
        """Create a scrollable icon grid for a given folder."""
        canvas = tk.Canvas(parent)  # Create canvas
        v_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)  # Set up scrollbar
        h_scrollbar = ttk.Scrollbar(parent, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        scrollable_frame = tk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all"),
            )
        )


        # Add the scrollable frame to the canvas
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        v_scrollbar.pack(side="right", fill="y")  # Pack the vertical scrollbar
        h_scrollbar.pack(side="bottom", fill="x")  # Pack the horizontal scrollbar
        canvas.pack(side="left", fill="both", expand=True)

        # canvas.grid(row=0, column=0, sticky="nsew")  # Fill the parent container with the canvas
        # v_scrollbar.grid(row=0, column=1, sticky="ns")  # Attach the vertical scrollbar
        # h_scrollbar.grid(row=1, column=0, sticky="ew")

        # Asynchronous loading of icons
        threading.Thread(target=self.load_icons, args=(scrollable_frame, folder, subfolder_name), daemon=True).start()
        canvas.after(200, lambda: canvas.configure(scrollregion=canvas.bbox("all")))

        # parent.grid_rowconfigure(0, weight=1)  # Allow the first row to expand
        # parent.grid_columnconfigure(0, weight=1)

        return canvas

    def load_icons(self, frame, folder, subfolder_name):
        """Load PIL images in background thread, then create PhotoImages + widgets on main thread."""
        icon_folder = os.path.join(folder, "50x50")
        pil_images = []
        try:
            filenames = os.listdir(icon_folder)
        except OSError:
            return  # silently skip if 50x50/ doesn't exist
        for filename in filenames:
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_path = os.path.join(icon_folder, filename)
                try:
                    img = Image.open(image_path)
                    img.load()  # force decode here, not lazily on main thread
                    pil_images.append((filename, img, subfolder_name))
                except Exception:
                    pass  # skip corrupt files
        try:
            frame.after(0, lambda: self._create_icon_widgets(frame, pil_images, subfolder_name))
        except Exception:
            pass  # widget destroyed before thread completed

    def _create_icon_widgets(self, frame, pil_images, subfolder_name):
        """Create PhotoImages and icon grid widgets — must run on main thread."""
        icons = []
        for filename, pil_img, sub_name in pil_images:
            photo = ImageTk.PhotoImage(pil_img)
            icons.append((filename, photo, sub_name))

        # Retain references to prevent GC
        self.icon_references[subfolder_name] = [photo for _, photo, _ in icons]

        grid_rows = math.ceil(len(icons) / self.columns)
        for row in range(grid_rows):
            for col in range(self.columns):
                index = row * self.columns + col
                if index < len(icons):
                    filename, photo, sub_name = icons[index]
                    icon_label = tk.Label(
                        frame,
                        image=photo,
                        cursor="hand2",
                        bd=2,
                        relief=tk.RAISED,
                        bg="white"
                    )
                    icon_label.grid(row=row, column=col, padx=5, pady=5)
                    icon_label.bind("<Button-1>", lambda event, idx=index: self.on_icon_click(idx, icons))

    def on_mouse_wheel(self, event, canvas):
        """Handle mouse wheel scrolling."""
        direction = 1 if event.delta < 0 else -1
        for _ in range(3):  # More scrolling with each wheel event
            canvas.yview_scroll(direction, "units")

    def on_icon_click(self, index, icons):
        """Handle icon click and trigger callback."""
        filename, _, subfolder_name = icons[index]
        subpath = os.path.join(subfolder_name, "original", filename)
        if self.on_icon_selected:
            self.on_icon_selected(subpath)
