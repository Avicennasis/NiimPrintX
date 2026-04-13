from __future__ import annotations

import asyncio
import contextlib
import io
import os
import tempfile
import tkinter as tk
import tkinter.messagebox as mb
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

try:
    import cairo
except ImportError:
    cairo = None
from PIL import Image, ImageTk

from NiimPrintX.ui.config import CanvasState, ImmutableConfig, PrinterState, mm_to_pixels

from .PrinterOperation import PrinterOperation

if TYPE_CHECKING:
    from NiimPrintX.nimmy.types import HeartbeatResponse
    from NiimPrintX.ui.main import LabelPrinterApp


class PrintOption:
    def __init__(
        self,
        root: LabelPrinterApp,
        parent: tk.Frame,
        immutable: ImmutableConfig,
        canvas_state: CanvasState,
        printer: PrinterState,
    ) -> None:
        self.root = root
        self.parent = parent
        self.immutable: ImmutableConfig = immutable
        self.canvas_state: CanvasState = canvas_state
        self.printer: PrinterState = printer
        self.frame = ttk.Frame(parent)
        self.create_widgets()
        self.print_op = PrinterOperation(self.printer)
        self._connecting = False
        self._heartbeat_active = False
        self.print_image: Image.Image | None = None
        self._popup_ref: tk.Toplevel | None = None
        self.image_label: tk.Label | None = None
        self.check_heartbeat()

    def check_heartbeat(self) -> None:
        if self._heartbeat_active:
            return
        asyncio.run_coroutine_threadsafe(self.schedule_heartbeat(), self.root.async_loop)

    async def schedule_heartbeat(self) -> None:
        self._heartbeat_active = True
        try:
            await self._heartbeat_loop()
        except asyncio.CancelledError:
            pass
        finally:
            self._heartbeat_active = False

    async def _heartbeat_loop(self) -> None:
        while self._heartbeat_active:
            try:
                if self.print_op.is_connected and not self.printer.print_job:
                    state, hb = await self.print_op.heartbeat()
                    try:
                        self.root.after(0, lambda s=state, h=hb: self.update_status(s, h))
                    except tk.TclError:
                        self._heartbeat_active = False
                        break
                elif not self.printer.print_job:
                    try:
                        self.root.after(0, lambda: self.update_status(False))
                    except tk.TclError:
                        self._heartbeat_active = False
                        break
            except tk.TclError:
                self._heartbeat_active = False
                break  # Root destroyed, exit heartbeat loop cleanly
            await asyncio.sleep(5)

    def update_status(self, connected: bool = False, hb_data: HeartbeatResponse | None = None) -> None:
        if self._connecting:
            return
        self.printer.printer_connected = connected
        if not connected and self.connect_button["state"] != tk.DISABLED:
            self.connect_button.config(text="Connect")
            self.connect_button.config(state=tk.NORMAL)
        with contextlib.suppress(tk.TclError):
            self.root.status_bar.update_status(connected)

    def create_widgets(self) -> None:
        self.toolbar_print_button = tk.Button(self.parent, text="Print", command=self.display_print)
        self.toolbar_print_button.pack(side=tk.RIGHT, padx=10)
        save_image_button = tk.Button(self.parent, text="Save Image", command=self.save_image)
        save_image_button.pack(side=tk.RIGHT, padx=10)
        self.connect_button = tk.Button(self.parent, text="Connect", command=self.printer_connect)
        self.connect_button.pack(side=tk.RIGHT, padx=10)

    def printer_connect(self) -> None:
        self.connect_button.config(state=tk.DISABLED)
        self._connecting = True
        if not self.printer.printer_connected:
            future = asyncio.run_coroutine_threadsafe(
                self.print_op.printer_connect(self.printer.device), self.root.async_loop
            )
            future.add_done_callback(lambda f: self._update_device_status(f, was_connecting=True))
        else:
            future = asyncio.run_coroutine_threadsafe(self.print_op.printer_disconnect(), self.root.async_loop)
            future.add_done_callback(lambda f: self._update_device_status(f, was_connecting=False))

    def _update_device_status(self, future: asyncio.Future[bool], *, was_connecting: bool) -> None:
        try:
            result = future.result()
        except Exception:  # noqa: BLE001 — GUI callback; any async failure means "not connected"
            result = False

        def _update():
            self._connecting = False
            if was_connecting and result:
                self.printer.printer_connected = True
                self.connect_button.config(text="Disconnect")
            elif not was_connecting and result:
                self.printer.printer_connected = False
                self.connect_button.config(text="Connect")
            # On failure, leave button text matching current state
            self.connect_button.config(state=tk.NORMAL)
            with contextlib.suppress(tk.TclError):
                self.root.status_bar.update_status(self.printer.printer_connected)

        try:
            self.root.after(0, _update)
        except tk.TclError:
            self._connecting = False

    def display_print(self) -> None:
        if self.printer.print_job:
            return
        self.toolbar_print_button.config(state=tk.DISABLED)
        try:
            # Export to PNG and display it in a pop-up window
            if self.immutable.os_system == "Windows":
                # Windows-specific: close fd immediately so Cairo can reopen by path
                fd, tmp_file_path = tempfile.mkstemp(suffix=".png")
                os.close(fd)
                try:
                    self.export_to_png(tmp_file_path)  # Save to file
                    self.display_image_in_popup(tmp_file_path)  # Display in pop-up window
                finally:
                    with contextlib.suppress(OSError):
                        os.remove(tmp_file_path)
            else:
                with tempfile.NamedTemporaryFile(suffix=".png") as tmp_file:
                    self.export_to_png(tmp_file.name)  # Save to file
                    self.display_image_in_popup(tmp_file.name)
        except Exception as e:  # noqa: BLE001 — GUI must re-enable button on any export failure
            self.toolbar_print_button.config(state=tk.NORMAL)
            mb.showerror("Export Error", f"Failed to prepare print preview:\n{e}")

    def save_image(self) -> None:
        if self.printer.print_job:
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
            try:
                self.export_to_png(file_path)
                self.display_image_in_popup(file_path)
            except Exception as e:  # noqa: BLE001 — UI-facing catch-all for user feedback dialog
                mb.showerror("Save Error", f"Failed to save image:\n{e}")

    def export_to_png(
        self, output_filename: str | None = None, horizontal_offset: float = 0.0, vertical_offset: float = 0.0
    ) -> Image.Image | None:
        if cairo is None:
            raise ImportError("GUI extras not installed. Run: pip install NiimPrintX[gui]")
        if self.canvas_state.canvas is None or self.canvas_state.bounding_box is None:
            return None
        width = self.canvas_state.canvas.winfo_width()
        height = self.canvas_state.canvas.winfo_height()

        dpi = self.immutable.label_sizes[self.printer.device]["print_dpi"]
        horizontal_offset_pixels = mm_to_pixels(horizontal_offset, dpi)
        vertical_offset_pixels = mm_to_pixels(vertical_offset, dpi)

        x1, y1, x2, y2 = self.canvas_state.canvas.bbox(self.canvas_state.bounding_box)

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
        if self.canvas_state.image_items:
            for img_id, img_props in self.canvas_state.image_items.items():
                coords = self.canvas_state.canvas.coords(img_id)
                resized_image = ImageTk.getimage(img_props["image"])
                with io.BytesIO() as buffer:
                    resized_image.save(buffer, format="PNG")
                    buffer.seek(0)
                    img_surface = cairo.ImageSurface.create_from_png(buffer)
                ctx.set_source_surface(img_surface, coords[0], coords[1])
                ctx.paint()
                img_surface.finish()  # release native Cairo memory

        # Drawing text items
        if self.canvas_state.text_items:
            for text_id, text_props in self.canvas_state.text_items.items():
                coords = self.canvas_state.canvas.coords(text_id)
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
                img_surface.finish()  # release native Cairo memory

        # Create a cropped surface to save
        cropped_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(bbox_width), int(bbox_height))
        cropped_ctx = cairo.Context(cropped_surface)
        cropped_ctx.set_source_surface(surface, -x1, -y1)
        cropped_ctx.paint()
        try:
            if output_filename:
                cropped_surface.write_to_png(output_filename)
                return None
            stride = cropped_surface.get_stride()
            image_bytes = bytes(cropped_surface.get_data())  # copy before finish()
            return Image.frombuffer("RGBA", (int(bbox_width), int(bbox_height)), image_bytes, "raw", "BGRA", stride, 1)
        finally:
            cropped_surface.finish()
            surface.finish()

    def display_image_in_popup(self, filename: str) -> None:
        # Create a new Toplevel window
        popup = tk.Toplevel(self.root)
        popup.title("Preview Image")
        popup.grab_set()  # Make modal — prevents opening multiple popups

        # Load the PNG image with PIL and convert to ImageTk
        if self.print_image is not None:
            with contextlib.suppress(Exception):
                self.print_image.close()
        Image.MAX_IMAGE_PIXELS = 5_000_000
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
        self.print_density.set(str(min(3, self.immutable.label_sizes[self.printer.device]["density"])))
        tk.Label(option_frame, text="Density").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        density_slider = tk.Spinbox(
            option_frame,
            from_=1,
            to=self.immutable.label_sizes[self.printer.device]["density"],
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
        device_rotation = self.immutable.label_sizes[self.printer.device].get("rotation", -90)
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
            if self.print_image is not None:
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

    def update_image_offset(self) -> None:
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
        if self.print_image is not None:
            with contextlib.suppress(Exception):
                self.print_image.close()
        self.print_image = result
        img_tk = ImageTk.PhotoImage(self.print_image)
        with contextlib.suppress(tk.TclError):
            self.image_label.config(image=img_tk)
            self.image_label.image = img_tk

    def print_label(self, image: Image.Image, density: str, quantity: str) -> None:
        self.print_button.config(state=tk.DISABLED)
        self._popup_ref = self.image_label.winfo_toplevel()
        self.printer.print_job = True

        # Validate density
        try:
            density = int(density)
        except (ValueError, TypeError):
            density = 3
        density = max(1, min(density, self.immutable.label_sizes[self.printer.device]["density"]))

        # Validate quantity
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            quantity = 1
        quantity = max(1, min(quantity, 65535))

        try:
            rotation = int(self.print_rotation.get())
        except (ValueError, AttributeError):
            rotation = self.immutable.label_sizes[self.printer.device].get("rotation", -90) % 360

        # PIL rotates counter-clockwise, so negate for clockwise
        rotation = -rotation
        try:
            self._rotated_image = image.rotate(rotation, expand=True)
            future = asyncio.run_coroutine_threadsafe(
                self.print_op.print(self._rotated_image, density, quantity), self.root.async_loop
            )
            future.add_done_callback(self._print_handler)
        except Exception:
            self.printer.print_job = False
            with contextlib.suppress(tk.TclError):
                self.print_button.config(state=tk.NORMAL)
            raise

    def _print_handler(self, future: asyncio.Future[bool]) -> None:
        try:
            result = future.result()
        except BaseException:  # noqa: BLE001 — catches CancelledError + any async failure; GUI must not crash
            result = False

        def _update():
            self.printer.print_job = False
            if hasattr(self, "_rotated_image") and self._rotated_image is not None:
                with contextlib.suppress(Exception):
                    self._rotated_image.close()
                self._rotated_image = None
            if result:
                with contextlib.suppress(tk.TclError):
                    self.root.status_bar.update_status(self.printer.printer_connected)
            else:
                popup_alive = self._popup_ref is not None
                if popup_alive:
                    with contextlib.suppress(tk.TclError):
                        popup_alive = self._popup_ref.winfo_exists()
                if popup_alive:
                    with contextlib.suppress(tk.TclError):
                        mb.showerror(
                            "Print Failed", "The print job failed. Check the printer connection and try again."
                        )
            with contextlib.suppress(tk.TclError):
                self.print_button.config(state=tk.NORMAL)
            with contextlib.suppress(tk.TclError):
                self.toolbar_print_button.config(state=tk.NORMAL)

        try:
            self.root.after(0, _update)
        except tk.TclError:
            # Root destroyed during print — reset state directly
            self.printer.print_job = False
