# Simple GUI for the Stream Dock emulator
# Uses Tkinter to present a 5x3 grid (96x96 per key) as a single canvas image.

import threading
import tkinter as tk
from PIL import Image, ImageTk


class EmulatorGUI:
    def __init__(self, width: int, height: int, title: str = "StreamDock Emulator"):
        self.width = width
        self.height = height
        self.title = title
        self._thread = None
        self._root = None
        self._label = None
        self._photo = None
        self._stop = threading.Event()

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        self._root = tk.Tk()
        self._root.title(self.title)
        self._root.protocol("WM_DELETE_WINDOW", self.stop)
        self._label = tk.Label(self._root)
        self._label.pack()
        self._root.geometry(f"{self.width}x{self.height}")
        self._root.resizable(False, False)
        def pump():
            if self._stop.is_set():
                try:
                    self._root.destroy()
                except Exception:
                    pass
                return
            self._root.after(33, pump)  # ~30 FPS pump
        self._root.after(33, pump)
        try:
            self._root.mainloop()
        except Exception:
            pass

    def update_image(self, pil_image: Image.Image):
        if self._label is None:
            return
        img = pil_image.resize((self.width, self.height), Image.NEAREST)
        self._photo = ImageTk.PhotoImage(img)
        self._label.configure(image=self._photo)

    def stop(self):
        self._stop.set()
