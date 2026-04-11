import asyncio
import contextlib
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
        self.title('NiimPrintX')
        width=1100
        height=800
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(width=True, height=True)  # Allow window to be resizable
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.withdraw()

    def load_resources(self):
        self.async_loop = asyncio.new_event_loop()
        threading.Thread(target=self.start_asyncio_loop, daemon=True).start()

        self.app_config = AppConfig()
        if self.app_config.os_system == "Darwin":
            style = ttk.Style(self)
            style.theme_use('aqua')
        elif self.app_config.os_system == "Windows":
            style = ttk.Style(self)
            style.theme_use('xpnative')
        else:
            try:
                import sv_ttk
                sv_ttk.set_theme("light")
            except ImportError:
                style = ttk.Style(self)
                style.theme_use('clam')

        self.create_widgets()
        self.create_menu()
        self.printer = None

    def create_menu(self):
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)
        self.file_menu = FileMenu(self, menu_bar, self.app_config)


    def create_widgets(self):
        # Top frame to hold the canvas and Notebook
        self.app_config.frames["top_frame"] = tk.Frame(self)
        self.app_config.screen_dpi = int(self.app_config.frames["top_frame"].winfo_fpixels('1i'))

        self.app_config.frames["top_frame"].pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tab_control = ttk.Notebook(self)
        self.text_tab = TextTab(self.tab_control, self.app_config)
        self.icon_tab = IconTab(self.tab_control, self.app_config)

        self.tab_control.add(self.text_tab.frame, text='Text')
        self.tab_control.add(self.icon_tab.frame, text='Icon')
        self.tab_control.pack(expand=1, fill='both', side=tk.TOP)


        # Bottom frame with label size and print button
        self.app_config.frames["bottom_frame"] = tk.Frame(self)

        self.canvas_selector = CanvasSelector(self.app_config.frames["bottom_frame"], self.app_config,
                                              self.text_tab.get_text_operation(),
                                              self.icon_tab.get_image_operation())

        self.print_option = PrintOption(self,self.app_config.frames["bottom_frame"], self.app_config)

        self.app_config.frames["bottom_frame"].pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        self.app_config.frames["status_frame"] = tk.Frame(self)
        self.status_bar = StatusBar(self.app_config.frames["status_frame"], self.app_config)
        self.app_config.frames["status_frame"].pack(side=tk.BOTTOM, fill=tk.X)

    def start_asyncio_loop(self):
        asyncio.set_event_loop(self.async_loop)
        self.async_loop.run_forever()

    def on_close(self):
        if getattr(self, '_shutting_down', False):
            return
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self._shutting_down = True
            self._shutdown_complete = threading.Event()

            async def _shutdown():
                # Disconnect printer if connected
                if hasattr(self, 'print_option') and self.print_option.print_op.printer:
                    with contextlib.suppress(Exception):
                        await self.print_option.print_op.printer.disconnect()
                # Stop heartbeat
                if hasattr(self, 'print_option'):
                    self.print_option._heartbeat_active = False
                # Cancel remaining tasks
                tasks = [t for t in asyncio.all_tasks(self.async_loop)
                         if not t.done() and t is not asyncio.current_task()]
                for t in tasks:
                    t.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                self._shutdown_complete.set()

            asyncio.run_coroutine_threadsafe(_shutdown(), self.async_loop)
            self._poll_shutdown()

    def _poll_shutdown(self, attempts=0):
        if self._shutdown_complete.is_set() or attempts >= 30:
            self.async_loop.call_soon_threadsafe(self.async_loop.stop)
            self.destroy()
        else:
            self.after(100, lambda: self._poll_shutdown(attempts + 1))

# Entry point: use __main__.main() which handles ImageMagick setup and splash screen
