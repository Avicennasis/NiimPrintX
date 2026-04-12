import asyncio
import contextlib
import logging
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from NiimPrintX.ui.widget.CanvasSelector import CanvasSelector
from NiimPrintX.ui.widget.FileMenu import FileMenu

from .AppConfig import AppConfig
from .widget.IconTab import IconTab
from .widget.PrintOption import PrintOption
from .widget.StatusBar import StatusBar
from .widget.TextTab import TextTab


class LabelPrinterApp(tk.Tk):
    def __init__(self):
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

    def load_resources(self):
        self.async_loop = asyncio.new_event_loop()
        loop_ready = threading.Event()
        threading.Thread(target=self.start_asyncio_loop, args=(loop_ready,), daemon=True).start()

        self.app_config = AppConfig()
        if self.app_config.os_system == "Darwin":
            style = ttk.Style(self)
            style.theme_use("aqua")
        elif self.app_config.os_system == "Windows":
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
        self.printer = None

    def create_menu(self):
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)
        self.file_menu = FileMenu(self, menu_bar, self.app_config)

    def create_widgets(self):
        # Top frame to hold the canvas and Notebook
        self.app_config.frames["top_frame"] = tk.Frame(self)
        self.app_config.frames["top_frame"].pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tab_control = ttk.Notebook(self)
        self.text_tab = TextTab(self.tab_control, self.app_config)
        self.icon_tab = IconTab(self.tab_control, self.app_config)

        self.tab_control.add(self.text_tab.frame, text="Text")
        self.tab_control.add(self.icon_tab.frame, text="Icon")
        self.tab_control.pack(expand=1, fill="both", side=tk.TOP)

        # Bottom frame with label size and print button
        self.app_config.frames["bottom_frame"] = tk.Frame(self)

        self.canvas_selector = CanvasSelector(
            self.app_config.frames["bottom_frame"],
            self.app_config,
            self.text_tab.get_text_operation(),
            self.icon_tab.get_image_operation(),
        )

        self.print_option = PrintOption(self, self.app_config.frames["bottom_frame"], self.app_config)

        self.app_config.frames["bottom_frame"].pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        self.app_config.frames["status_frame"] = tk.Frame(self)
        self.status_bar = StatusBar(self.app_config.frames["status_frame"], self.app_config)
        self.app_config.frames["status_frame"].pack(side=tk.BOTTOM, fill=tk.X)

    def start_asyncio_loop(self, loop_ready):
        asyncio.set_event_loop(self.async_loop)
        self.async_loop.call_soon(loop_ready.set)
        self.async_loop.run_forever()

    def on_close(self):
        if self._shutting_down:
            return
        # H21: If load_resources failed before app_config was created, skip the
        # quit dialog entirely — there is nothing to clean up.
        if getattr(self, "app_config", None) is None and getattr(self, "print_option", None) is None:
            self.destroy()
            return
        if getattr(self, "app_config", None) and self.app_config.print_job:
            if not messagebox.askokcancel("Quit", "A print job is in progress. Quit anyway?"):
                return
        elif not messagebox.askokcancel("Quit", "Do you want to quit?"):
            return
        self._shutting_down = True

        async def _shutdown():
            # Close PIL images to prevent leaks
            for item in self.app_config.image_items.values():
                orig = item.get("original_image")
                if orig is not None:
                    with contextlib.suppress(Exception):
                        orig.close()
            self.app_config.image_items.clear()
            self.app_config.text_items.clear()
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

    def _poll_shutdown(self, attempts=0):
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
            logging.getLogger(__name__).warning(
                "Shutdown timed out after %d poll attempts; force-stopping event loop",
                attempts,
            )
            with contextlib.suppress(RuntimeError):
                self.async_loop.call_soon_threadsafe(self.async_loop.stop)
            with contextlib.suppress(tk.TclError):
                self.destroy()
        else:
            self.after(100, lambda: self._poll_shutdown(attempts + 1))


# Entry point: use __main__.main() which handles ImageMagick setup and splash screen
