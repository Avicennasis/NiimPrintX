from __future__ import annotations

import asyncio
import contextlib
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from NiimPrintX.nimmy.logger_config import get_logger
from NiimPrintX.nimmy.userconfig import load_user_config, merge_label_sizes

from .config import CanvasState, ImmutableConfig, PrinterState
from .widget.CanvasSelector import CanvasSelector
from .widget.FileMenu import FileMenu
from .widget.IconTab import IconTab
from .widget.PrintOption import PrintOption
from .widget.StatusBar import StatusBar
from .widget.TextTab import TextTab

logger = get_logger()


class LabelPrinterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self._shutting_down = False
        self._shutdown_complete = threading.Event()
        self.title("NiimPrintX")
        width = 1100
        height = 800
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(width=True, height=True)  # Allow window to be resizable
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.withdraw()

    def load_resources(self) -> None:
        self.async_loop = asyncio.new_event_loop()
        loop_ready = threading.Event()
        threading.Thread(target=self.start_asyncio_loop, args=(loop_ready,), daemon=True).start()

        self.immutable = ImmutableConfig(
            load_user_config=load_user_config,
            merge_label_sizes=merge_label_sizes,
        )
        self.canvas_state = CanvasState()
        self.printer = PrinterState(default_device=next(iter(self.immutable.label_sizes)))
        if self.immutable.os_system == "Darwin":
            style = ttk.Style(self)
            style.theme_use("aqua")
        elif self.immutable.os_system == "Windows":
            style = ttk.Style(self)
            style.theme_use("xpnative")
        else:
            try:
                import sv_ttk  # noqa: PLC0415 — lazy import; optional dependency

                sv_ttk.set_theme("light")
            except ImportError:
                style = ttk.Style(self)
                style.theme_use("clam")

        if not loop_ready.wait(timeout=2):
            raise RuntimeError("Asyncio event loop failed to start within 2 seconds")
        self.create_menu()
        self.create_widgets()

    def _deselect_all(self) -> None:
        if self.canvas_state.current_selected:
            self.text_tab.text_op.deselect_text()
        if self.canvas_state.current_selected_image:
            self.icon_tab.image_op.deselect_image()

    def _load_canvas_config(self, device: str, label_size: str) -> None:
        self.canvas_selector.selected_device.set(device.upper())
        self.canvas_selector.update_device_label_size()
        self.canvas_selector.selected_label_size.set(label_size)
        self.canvas_selector.update_canvas_size()

    def _bind_text_select(self, text_id: int) -> None:
        self.canvas_state.canvas.tag_bind(
            text_id,
            "<Button-1>",
            lambda event, tid=text_id: self.text_tab.text_op.select_text(event, tid),
        )

    def _bind_image_select(self, image_id: int) -> None:
        self.canvas_state.canvas.tag_bind(
            image_id,
            "<Button-1>",
            lambda event, img_id=image_id: self.icon_tab.image_op.select_image(event, img_id),
        )
        self.canvas_state.canvas.tag_bind(
            image_id,
            "<B1-Motion>",
            lambda e, img_id=image_id: self.icon_tab.image_op.move_image(e, img_id),
        )

    def create_menu(self) -> None:
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)
        self.file_menu = FileMenu(
            self,
            menu_bar,
            self.immutable,
            self.canvas_state,
            self.printer,
            on_close=self.on_close,
            on_deselect_all=self._deselect_all,
            on_load_canvas_config=self._load_canvas_config,
            on_bind_text_select=self._bind_text_select,
            on_bind_image_select=self._bind_image_select,
        )

    def create_widgets(self) -> None:
        # Top frame to hold the canvas and Notebook
        self.canvas_state.frames["top_frame"] = tk.Frame(self)
        self.canvas_state.frames["top_frame"].pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tab_control = ttk.Notebook(self)
        self.text_tab = TextTab(self.tab_control, self.immutable, self.canvas_state)
        self.icon_tab = IconTab(self.tab_control, self.immutable, self.canvas_state)

        self.tab_control.add(self.text_tab.frame, text="Text")
        self.tab_control.add(self.icon_tab.frame, text="Icon")
        self.tab_control.pack(expand=1, fill="both", side=tk.TOP)

        # Bottom frame with label size and print button
        self.canvas_state.frames["bottom_frame"] = tk.Frame(self)

        self.canvas_selector = CanvasSelector(
            self.canvas_state.frames["bottom_frame"],
            self.immutable,
            self.canvas_state,
            self.printer,
            self.text_tab.get_text_operation(),
            self.icon_tab.get_image_operation(),
        )

        self.print_option = PrintOption(
            self, self.canvas_state.frames["bottom_frame"], self.immutable, self.canvas_state, self.printer
        )

        self.canvas_state.frames["bottom_frame"].pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        self.canvas_state.frames["status_frame"] = tk.Frame(self)
        self.status_bar = StatusBar(self.canvas_state.frames["status_frame"])
        self.canvas_state.frames["status_frame"].pack(side=tk.BOTTOM, fill=tk.X)

    def start_asyncio_loop(self, loop_ready: threading.Event) -> None:
        asyncio.set_event_loop(self.async_loop)
        self.async_loop.call_soon(loop_ready.set)
        self.async_loop.run_forever()

    def on_close(self) -> None:
        if self._shutting_down:
            return
        # H21: If load_resources failed before sub-objects were created, skip the
        # quit dialog entirely — there is nothing to clean up.
        printer = getattr(self, "printer", None)
        if printer is None or getattr(self, "print_option", None) is None:
            self.destroy()
            return
        if printer.print_job:
            if not messagebox.askokcancel("Quit", "A print job is in progress. Quit anyway?"):
                return
        elif not messagebox.askokcancel("Quit", "Do you want to quit?"):
            return
        self._shutting_down = True

        async def _shutdown():
            # Close PIL images to prevent leaks
            for item in self.canvas_state.image_items.values():
                orig = item.get("original_image")
                if orig is not None:
                    with contextlib.suppress(Exception):
                        orig.close()
            self.canvas_state.image_items.clear()
            self.canvas_state.text_items.clear()
            # Disconnect printer if connected
            if hasattr(self, "print_option") and self.print_option.print_op.printer:
                with contextlib.suppress(Exception):
                    await self.print_option.print_op.printer.disconnect()
            # Stop heartbeat
            if hasattr(self, "print_option"):
                self.print_option._heartbeat_active = False
            # Cancel remaining tasks
            tasks = [t for t in asyncio.all_tasks() if not t.done() and t is not asyncio.current_task()]
            for t in tasks:
                t.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self._shutdown_complete.set()

        asyncio.run_coroutine_threadsafe(_shutdown(), self.async_loop)
        self._poll_shutdown()

    def _poll_shutdown(self, attempts: int = 0) -> None:
        if self._shutdown_complete.is_set():
            # Clean shutdown: coroutine finished, safe to stop the loop.
            with contextlib.suppress(RuntimeError):
                self.async_loop.call_soon_threadsafe(self.async_loop.stop)
            with contextlib.suppress(tk.TclError):
                self.destroy()
        elif attempts >= 30:
            # C3: Max attempts exhausted (3 s).  The _shutdown coroutine may
            # still be suspended inside asyncio.gather.  Calling loop.stop()
            # directly from the Tk thread while gather is running can strand
            # the coroutine.  Use call_soon_threadsafe so the stop is
            # dispatched on the loop's own thread, giving gather a chance to
            # finalise before the loop exits.
            logger.warning(f"Shutdown timed out after {attempts} poll attempts; force-stopping event loop")
            with contextlib.suppress(RuntimeError):
                self.async_loop.call_soon_threadsafe(self.async_loop.stop)
            with contextlib.suppress(tk.TclError):
                self.destroy()
        else:
            self.after(100, lambda: self._poll_shutdown(attempts + 1))


# Entry point: use __main__.main() which handles ImageMagick setup and splash screen
