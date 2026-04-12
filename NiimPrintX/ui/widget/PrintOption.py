import asyncio
import contextlib
import io
import os
import tempfile
import tkinter as tk
import tkinter.messagebox as mb
from tkinter import filedialog, ttk

try:
    import cairo
except ImportError:
    cairo = None
from PIL import Image, ImageTk

from .PrinterOperation import PrinterOperation


class PrintOption:
    def __init__(self, root, parent, config):
        self.root = root
        self.parent = parent
        self.config = config
        self.frame = ttk.Frame(parent)
        self.create_widgets()
        self.print_op = PrinterOperation(self.config)
        self._heartbeat_active = False
        self.check_heartbeat()

    def check_heartbeat(self):
        asyncio.run_coroutine_threadsafe(self.schedule_heartbeat(), self.root.async_loop)

    async def schedule_heartbeat(self):
        self._heartbeat_active = True
        while self._heartbeat_active:
            try:
                if self.print_op.printer and not self.config.print_job:
                    state, hb = await self.print_op.heartbeat()
                    self.root.after(0, lambda s=state, h=hb: self.update_status(s, h))
                elif not self.config.print_job:
                    self.root.after(0, lambda: self.update_status(False))
            except tk.TclError:
                break  # Root destroyed, exit heartbeat loop cleanly
            await asyncio.sleep(5)

    def update_status(self, connected=False, hb_data=None):
        self.config.printer_connected = connected
        if not connected and self.connect_button["state"] != tk.DISABLED:
            self.connect_button.config(text="Connect")
            self.connect_button.config(state=tk.NORMAL)
        with contextlib.suppress(tk.TclError):
            self.root.status_bar.update_status(connected)

    def create_widgets(self):
        self.toolbar_print_button = tk.Button(self.parent, text="Print", command=self.display_print)
        self.toolbar_print_button.pack(side=tk.RIGHT, padx=10)
        save_image_button = tk.Button(self.parent, text="Save Image", command=self.save_image)
        save_image_button.pack(side=tk.RIGHT, padx=10)
        self.connect_button = tk.Button(self.parent, text="Connect", command=self.printer_connect)
        self.connect_button.pack(side=tk.RIGHT, padx=10)

    def printer_connect(self):
        self.connect_button.config(state=tk.DISABLED)
        if not self.config.printer_connected:
            future = asyncio.run_coroutine_threadsafe(
                self.print_op.printer_connect(self.config.device), self.root.async_loop
            )
            future.add_done_callback(self._update_device_status)
        else:
            future = asyncio.run_coroutine_threadsafe(self.print_op.printer_disconnect(), self.root.async_loop)
            future.add_done_callback(self._update_device_status)

    def _update_device_status(self, future):
        try:
            result = future.result()
        except Exception:  # noqa: BLE001 — GUI callback; any async failure means "not connected"
            result = False

        def _update():
            if self.config.printer_connected:
                self.connect_button.config(text="Disconnect")
                self.connect_button.config(state=tk.NORMAL)
            else:
                self.connect_button.config(text="Connect")
                self.connect_button.config(state=tk.NORMAL)
            with contextlib.suppress(tk.TclError):
                self.root.status_bar.update_status(result if self.config.printer_connected else False)

        self.root.after(0, _update)

    def display_print(self):
        if self.config.print_job:
            return
        self.toolbar_print_button.config(state=tk.DISABLED)
        # Export to PNG and display it in a pop-up window
        if self.config.os_system == "Windows":
            # Windows-specific logic using tempfile.mkstemp()
            fd, tmp_file_path = tempfile.mkstemp(suffix=".png")
            try:
                self.export_to_png(tmp_file_path)  # Save to file
                self.display_image_in_popup(tmp_file_path)  # Display in pop-up window
            finally:
                os.close(fd)  # Close the file descriptor
                os.remove(tmp_file_path)  # Remove the temporary file
        else:
            with tempfile.NamedTemporaryFile(suffix=".png") as tmp_file:
                self.export_to_png(tmp_file.name)  # Save to file
                self.display_image_in_popup(tmp_file.name)

    def save_image(self):
        if self.config.print_job:
            return
        options = {
            "defaultextension": ".png",
            "filetypes": [("PNG files", "*.png")],
            "initialfile": "niimprintx.png",  # Specify an initial file name
            "title": "Save as PNG",
        }
        # Open the save as dialog and get the selected file name
        file_path = filedialog.asksaveasfilename(**options)
        if file_path:
            self.export_to_png(file_path)
            self.display_image_in_popup(file_path)

    def mm_to_pixels(self, mm):
        inches = mm / 25.4
        return int(inches * self.config.label_sizes[self.config.device]["print_dpi"])

    def export_to_png(self, output_filename=None, horizontal_offset=0.0, vertical_offset=0.0):
        if cairo is None:
            raise ImportError("GUI extras not installed. Run: pip install NiimPrintX[gui]")
        if self.config.canvas is None or self.config.bounding_box is None:
            return None
        width = self.config.canvas.winfo_reqwidth()
        height = self.config.canvas.winfo_reqheight()

        horizontal_offset_pixels = self.mm_to_pixels(horizontal_offset)
        vertical_offset_pixels = self.mm_to_pixels(vertical_offset)

        x1, y1, x2, y2 = self.config.canvas.bbox(self.config.bounding_box)

        x1 += horizontal_offset_pixels
        y1 += vertical_offset_pixels
        x2 += horizontal_offset_pixels
        y2 += vertical_offset_pixels

        bbox_width = x2 - x1
        bbox_height = y2 - y1

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        ctx = cairo.Context(surface)
        ctx.set_source_rgb(1, 1, 1)  # White background
        ctx.paint()

        # Drawing images (if any)
        if self.config.image_items:
            for img_id, img_props in self.config.image_items.items():
                coords = self.config.canvas.coords(img_id)
                resized_image = ImageTk.getimage(img_props["image"])
                with io.BytesIO() as buffer:
                    resized_image.save(buffer, format="PNG")
                    buffer.seek(0)
                    img_surface = cairo.ImageSurface.create_from_png(buffer)
                ctx.set_source_surface(img_surface, coords[0], coords[1])
                ctx.paint()

        # Drawing text items
        if self.config.text_items:
            for text_id, text_props in self.config.text_items.items():
                coords = self.config.canvas.coords(text_id)
                font_img_widget = text_props["font_image"]
                if isinstance(font_img_widget, ImageTk.PhotoImage):
                    resized_image = ImageTk.getimage(font_img_widget)
                else:
                    # tk.PhotoImage (from Wand text) — extract via Tcl
                    import base64 as b64  # noqa: PLC0415 — lazy import; only needed for tk.PhotoImage path

                    png_b64 = font_img_widget.tk.call(str(font_img_widget), "data", "-format", "png")
                    resized_image = Image.open(io.BytesIO(b64.b64decode(png_b64)))
                with io.BytesIO() as buffer:
                    resized_image.save(buffer, format="PNG")
                    buffer.seek(0)
                    img_surface = cairo.ImageSurface.create_from_png(buffer)
                ctx.set_source_surface(img_surface, coords[0], coords[1])
                ctx.paint()

        # Create a cropped surface to save
        cropped_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(bbox_width), int(bbox_height))
        cropped_ctx = cairo.Context(cropped_surface)
        cropped_ctx.set_source_surface(surface, -x1, -y1)
        cropped_ctx.paint()
        if output_filename:
            cropped_surface.write_to_png(output_filename)
            return None
        image_bytes = cropped_surface.get_data()
        return Image.frombuffer("RGBA", (int(bbox_width), int(bbox_height)), image_bytes, "raw", "BGRA", 0, 1)

    def display_image_in_popup(self, filename):
        # Create a new Toplevel window
        popup = tk.Toplevel(self.root)
        popup.title("Preview Image")
        popup.grab_set()  # Make modal — prevents opening multiple popups

        # Load the PNG image with PIL and convert to ImageTk
        if hasattr(self, "print_image") and self.print_image is not None:
            with contextlib.suppress(Exception):
                self.print_image.close()
        self.print_image = Image.open(filename)
        self.print_image.load()  # Force decode before tempfile is removed
        img_tk = ImageTk.PhotoImage(self.print_image)

        # Create a Label to display the image
        self.image_label = tk.Label(popup, image=img_tk)
        self.image_label.image = img_tk  # Keep a reference to avoid garbage collection
        self.image_label.grid(row=0, column=0, columnspan=4, padx=10, pady=10)

        option_frame = tk.Frame(popup)
        option_frame.grid(row=1, column=0, columnspan=4, padx=20, pady=10, sticky="ew")

        self.print_density = tk.StringVar()
        self.print_density.set("3")
        tk.Label(option_frame, text="Density").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        density_slider = tk.Spinbox(
            option_frame,
            from_=1,
            to=self.config.label_sizes[self.config.device]["density"],
            textvariable=self.print_density,
            width=4,
        )
        density_slider.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        tk.Label(option_frame, text="Copies").grid(row=0, column=2, padx=20, pady=5, sticky="e")
        self.print_copy = tk.StringVar()
        self.print_copy.set("1")
        print_copy_dropdown = tk.Spinbox(option_frame, from_=1, to=65535, textvariable=self.print_copy, width=4)
        print_copy_dropdown.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        tk.Label(option_frame, text="Rotation").grid(row=0, column=4, padx=20, pady=5, sticky="e")
        device_rotation = self.config.label_sizes[self.config.device].get("rotation", -90)
        rotation_choices = ["0", "90", "180", "270"]
        self.print_rotation = tk.StringVar()
        # Set default to the device's configured rotation (convert negative to positive for display)
        default_rot = str(device_rotation % 360)
        self.print_rotation.set(default_rot)
        rotation_dropdown = ttk.Combobox(
            option_frame, textvariable=self.print_rotation, values=rotation_choices, state="readonly", width=4
        )
        rotation_dropdown.grid(row=0, column=5, padx=5, pady=5, sticky="w")

        offset_frame = tk.Frame(popup)
        offset_frame.grid(row=2, column=0, columnspan=4, padx=20, pady=10, sticky="ew")

        self.horizontal_offset = tk.DoubleVar()
        self.horizontal_offset.set(0.0)
        tk.Label(offset_frame, text="Horizontal\nOffset").grid(row=0, column=0, padx=2, pady=5, sticky="e")
        horizontal_offset_dropdown = tk.Spinbox(
            offset_frame,
            from_=-5,
            to=5,
            textvariable=self.horizontal_offset,
            increment=0.5,
            format="%.1f",
            width=4,
            command=self.update_image_offset,
        )
        horizontal_offset_dropdown.grid(row=0, column=1, padx=2, pady=5, sticky="w")
        horizontal_offset_dropdown.bind("<FocusOut>", lambda event: self.update_image_offset())

        tk.Label(offset_frame, text="Vertical\nOffset").grid(row=0, column=2, padx=10, pady=5, sticky="e")
        self.vertical_offset = tk.DoubleVar()
        self.vertical_offset.set(0.0)
        vertical_offset_dropdown = tk.Spinbox(
            offset_frame,
            from_=-5,
            to=5,
            textvariable=self.vertical_offset,
            increment=0.5,
            format="%.1f",
            width=4,
            command=self.update_image_offset,
        )
        vertical_offset_dropdown.grid(row=0, column=3, padx=2, pady=5, sticky="w")
        vertical_offset_dropdown.bind("<FocusOut>", lambda event: self.update_image_offset())

        button_frame = tk.Frame(popup)
        button_frame.grid(row=3, column=0, columnspan=4, padx=20, pady=10, sticky="ew")

        self.print_button = tk.Button(
            button_frame,
            text="Print",
            command=lambda: self.print_label(self.print_image, self.print_density.get(), self.print_copy.get()),
        )
        self.print_button.grid(row=0, column=0, padx=5, pady=10, sticky="ew")

        def _on_popup_close():
            with contextlib.suppress(tk.TclError):
                self.toolbar_print_button.config(state=tk.NORMAL)
            if hasattr(self, "print_image") and self.print_image is not None:
                with contextlib.suppress(Exception):
                    self.print_image.close()
                self.print_image = None
            popup.destroy()

        close_button = tk.Button(button_frame, text="Close", command=_on_popup_close)
        close_button.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        popup.protocol("WM_DELETE_WINDOW", _on_popup_close)

        # Ensure the buttons are evenly spaced
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)

        # Ensure the frames are evenly spaced
        option_frame.grid_columnconfigure(1, weight=1)
        option_frame.grid_columnconfigure(3, weight=1)
        option_frame.grid_columnconfigure(5, weight=1)
        offset_frame.grid_columnconfigure(1, weight=1)
        offset_frame.grid_columnconfigure(3, weight=1)

    def update_image_offset(self):
        try:
            horizontal_offset = self.horizontal_offset.get()
            vertical_offset = self.vertical_offset.get()
        except tk.TclError:
            return
        result = self.export_to_png(
            output_filename=None, horizontal_offset=horizontal_offset, vertical_offset=vertical_offset
        )
        if result is None:
            return
        if hasattr(self, "print_image") and self.print_image is not None:
            with contextlib.suppress(Exception):
                self.print_image.close()
        self.print_image = result
        img_tk = ImageTk.PhotoImage(self.print_image)
        self.image_label.config(image=img_tk)
        self.image_label.image = img_tk

    def print_label(self, image, density, quantity):
        self.print_button.config(state=tk.DISABLED)
        self.config.print_job = True

        # Validate density
        try:
            density = int(density)
        except (ValueError, TypeError):
            density = 3
        density = max(1, min(density, self.config.label_sizes[self.config.device]["density"]))

        # Validate quantity
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            quantity = 1
        quantity = max(1, min(quantity, 65535))

        try:
            rotation = int(self.print_rotation.get())
        except (ValueError, AttributeError):
            rotation = self.config.label_sizes[self.config.device].get("rotation", -90) % 360

        # PIL rotates counter-clockwise, so negate for clockwise
        rotation = -rotation
        image = image.rotate(rotation, Image.NEAREST, expand=True)
        future = asyncio.run_coroutine_threadsafe(self.print_op.print(image, density, quantity), self.root.async_loop)
        future.add_done_callback(self._print_handler)

    def _print_handler(self, future):
        try:
            result = future.result()
        except BaseException:  # noqa: BLE001 — catches CancelledError + any async failure; GUI must not crash
            result = False

        def _update():
            self.config.print_job = False
            if result:
                with contextlib.suppress(tk.TclError):
                    self.root.status_bar.update_status(result)
            else:
                with contextlib.suppress(tk.TclError):
                    mb.showerror("Print Failed", "The print job failed. Check the printer connection and try again.")
            with contextlib.suppress(tk.TclError):
                self.print_button.config(state=tk.NORMAL)
            with contextlib.suppress(tk.TclError):
                self.toolbar_print_button.config(state=tk.NORMAL)

        self.root.after(0, _update)
