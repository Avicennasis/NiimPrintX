import os
import platform
import sys

from NiimPrintX.nimmy.logger_config import setup_logger
from NiimPrintX.ui.main import LabelPrinterApp
from NiimPrintX.ui.SplashScreen import SplashScreen


def load_libraries():
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
        magick_path = os.path.join(base_path, "imagemagick")

        match platform.system():
            case "Linux":
                os.environ["MAGICK_HOME"] = magick_path
                os.environ["PATH"] = os.path.join(magick_path, "bin") + os.pathsep + os.environ.get("PATH", "")
                os.environ["LD_LIBRARY_PATH"] = (
                    os.path.join(magick_path, "lib") + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")
                )
                os.environ["MAGICK_CONFIGURE_PATH"] = os.path.join(magick_path, "etc", "ImageMagick-7")
            case "Darwin":
                os.environ["MAGICK_HOME"] = magick_path
                os.environ["PATH"] = os.path.join(magick_path, "bin") + os.pathsep + os.environ.get("PATH", "")
                os.environ["DYLD_LIBRARY_PATH"] = (
                    os.path.join(magick_path, "lib") + os.pathsep + os.environ.get("DYLD_LIBRARY_PATH", "")
                )
                os.environ["MAGICK_CONFIGURE_PATH"] = os.path.join(magick_path, "etc", "ImageMagick-7")
            case "Windows":
                os.environ["MAGICK_HOME"] = magick_path
                os.environ["PATH"] = magick_path + os.pathsep + os.environ.get("PATH", "")


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        # Two levels up from NiimPrintX/ui/__main__.py → package root
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.realpath(os.path.join(base_path, relative_path))


def main():
    load_libraries()
    setup_logger()
    app = None
    splash = None
    try:
        app = LabelPrinterApp()
        image_path = resource_path("NiimPrintX/ui/assets/Niimprintx.png")
        splash = SplashScreen(image_path, app)  # Create the splash screen
        import contextlib as _ctx  # noqa: PLC0415 — lazy import for splash guard
        import tkinter  # noqa: PLC0415

        with _ctx.suppress(tkinter.TclError):
            splash.update()  # Force Tk to paint before blocking on load_resources

        app.load_resources()  # Start loading resources, then show the main window
        splash.close()  # Use close() which suppresses TclError on double-destroy
        splash = None
        app.deiconify()

        # Open file from command-line if provided (after deiconify so resources are ready)
        if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
            file_arg = sys.argv[1]  # capture value to avoid late-binding closure
            app.after(100, lambda: app.file_menu.load_from_file(file_arg))

        app.mainloop()
    except Exception as e:
        import contextlib  # noqa: PLC0415 — lazy import for error handling
        import tkinter.messagebox as mb  # noqa: PLC0415 — lazy import for error handling

        with contextlib.suppress(Exception):
            if splash is not None:
                splash.close()
        with contextlib.suppress(Exception):
            mb.showerror("Startup Error", f"NiimPrintX failed to start:\n{e}")
        with contextlib.suppress(Exception):
            if app is not None:
                app.destroy()
        raise


if __name__ == "__main__":
    main()
