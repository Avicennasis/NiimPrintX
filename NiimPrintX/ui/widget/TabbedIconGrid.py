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
        self.tab_names = {}  # tab_index → original folder name

        self.notebook = ttk.Notebook(self)
        self.create_tabs()
        self.notebook.pack(fill="both", expand=True)

    def create_tabs(self):
        """Create a tab for each subfolder."""
        for subfolder in sorted(os.listdir(self.base_folder)):
            subfolder_path = os.path.join(self.base_folder, subfolder)
            if os.path.isdir(subfolder_path):
                tab_frame = tk.Frame(self.notebook)
                tab_index = self.notebook.index("end")
                self.notebook.add(tab_frame, text=subfolder.capitalize())
                self.tab_names[tab_index] = subfolder  # store original name
        self.notebook.bind("<<NotebookTabChanged>>", self.load_tab_icons)

        # C18: Force-load the first tab since NotebookTabChanged doesn't fire on initial render
        if self.notebook.tabs():
            first_tab_index = 0
            first_subfolder = self.tab_names.get(first_tab_index)
            if first_subfolder:
                self._load_tab_by_index(first_tab_index, first_subfolder)

    def load_tab_icons(self, event):
        """Load icons when a tab is selected."""
        notebook = event.widget
        selected_tab_index = notebook.index(notebook.select())
        subfolder_name = self.tab_names.get(selected_tab_index,
                                             notebook.tab(selected_tab_index, "text").lower())
        self._load_tab_by_index(selected_tab_index, subfolder_name)

    def _load_tab_by_index(self, tab_index, subfolder_name):
        """Load icons for a tab by index and subfolder name (extracted for direct calls)."""
        tab_frame = self.notebook.nametowidget(self.notebook.tabs()[tab_index])

        # Check if icons are cached and load asynchronously if not
        if subfolder_name not in self.icon_cache:
            subfolder_path = os.path.join(self.base_folder, subfolder_name)
            self.icon_cache[subfolder_name] = self.create_icon_grid(tab_frame, subfolder_path, subfolder_name)
        # I17: Scroll bindings are established in create_icon_grid; no duplicate bindings needed here.
        # M13: scrollregion is configured in _create_icon_widgets after all widgets are placed.

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

        # I18: Bind all scroll events on the canvas at construction time
        canvas.bind("<MouseWheel>", lambda e, c=canvas: self.on_mouse_wheel(e, c))
        canvas.bind("<Button-4>", lambda e, c=canvas: c.yview_scroll(-3, "units"))
        canvas.bind("<Button-5>", lambda e, c=canvas: c.yview_scroll(3, "units"))

        # Asynchronous loading of icons
        # M13: scrollregion is configured in _create_icon_widgets after the bg thread completes
        threading.Thread(target=self.load_icons, args=(scrollable_frame, folder, subfolder_name, canvas), daemon=True).start()

        return canvas

    def load_icons(self, frame, folder, subfolder_name, canvas):
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
                    # I16: img.load() forces full pixel decode into memory in this thread.
                    # After this call the PIL Image holds a fully-decoded raster buffer
                    # and the bg thread never mutates it again, so handing it to the main
                    # thread via after() is safe (no lazy I/O or shared mutable state).
                    img.load()
                    pil_images.append((filename, img, subfolder_name))
                except Exception:
                    pass  # skip corrupt files
        try:
            frame.after(0, lambda: self._create_icon_widgets(frame, pil_images, subfolder_name, canvas))
        except tk.TclError:
            pass  # widget destroyed before thread completed

    def _create_icon_widgets(self, frame, pil_images, subfolder_name, canvas):
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

        # M13: Configure scrollregion AFTER all widgets are placed, not before the bg thread completes
        canvas.configure(scrollregion=canvas.bbox("all"))

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
