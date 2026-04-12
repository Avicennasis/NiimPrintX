from __future__ import annotations

import contextlib
import tkinter as tk


class SplashScreen(tk.Toplevel):
    def __init__(self, image_path: str, master: tk.Tk, **kwargs: object) -> None:
        super().__init__(master, **kwargs)
        self.image: tk.PhotoImage | None = None
        self.withdraw()
        self.overrideredirect(True)  # Remove window decorations

        # Load the image
        try:
            self.image = tk.PhotoImage(file=image_path)
        except tk.TclError:
            self.destroy()
            return
        label = tk.Label(self, image=self.image)
        label.pack()
        self.update_idletasks()  # compute geometry before withdraw
        width = label.winfo_reqwidth()
        height = label.winfo_reqheight()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.deiconify()

    def close(self) -> None:
        self.image = None
        with contextlib.suppress(tk.TclError):
            self.destroy()
