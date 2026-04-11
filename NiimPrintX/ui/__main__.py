import os
import sys
import platform
from NiimPrintX.ui.main import LabelPrinterApp

from NiimPrintX.ui.SplashScreen import SplashScreen


def load_libraries():
    if hasattr(sys, '_MEIPASS'):
        base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
        magick_path = os.path.join(base_path, 'imagemagick')

        if platform.system() == "Linux" or platform.system() == "Darwin":
            os.environ['MAGICK_HOME'] = magick_path
            os.environ['PATH'] = os.path.join(magick_path, 'bin') + os.pathsep + os.environ.get('PATH', '')
            os.environ['LD_LIBRARY_PATH'] = os.path.join(magick_path, 'lib') + os.pathsep + os.environ.get('LD_LIBRARY_PATH', '')
            os.environ['MAGICK_CONFIGURE_PATH'] = os.path.join(magick_path, 'etc', 'ImageMagick-7')
            os.environ['DYLD_LIBRARY_PATH'] = magick_path + ':' + os.environ.get('DYLD_LIBRARY_PATH', '')
        elif platform.system() == "Windows":
            os.environ['MAGICK_HOME'] = magick_path
            os.environ['PATH'] = magick_path + os.pathsep + os.environ.get('PATH', '')


load_libraries()


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    else:
        base_path = os.path.realpath(".")

    return os.path.realpath(os.path.join(base_path, relative_path))


def main():
    try:
        app = LabelPrinterApp()
        image_path = resource_path('NiimPrintX/ui/assets/Niimprintx.png')
        splash = SplashScreen(image_path, app)  # Create the splash screen

        # Hide the main window initially
        # app.withdraw()
        app.load_resources()  # Start loading resources, then show the main window
        app.after(5000, splash.destroy)  # Automatically destroy the splash screen after 5 seconds
        app.after(5000, app.deiconify)

        # Open file from command-line if provided
        if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
            app.after(100, lambda: app.file_menu.load_from_file(sys.argv[1]))

        app.mainloop()
    except Exception as e:
        print(f"Error {e}")
        raise


if __name__ == "__main__":
    main()
