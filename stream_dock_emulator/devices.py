try:
    from PIL import Image, ImageDraw
except Exception:
    Image = None  # Pillow is optional at import; required at runtime when using emulator
import threading
import time
import os
from typing import Optional, Tuple, Callable

# GUI backend: PySide6 is used exclusively for the emulator window.


class StreamDockN1:
    """
    Emulated StreamDockN1 device.
    Provides a minimal subset of the real SDK surface used by main.py.
    Keys: 15 (3 rows x 5 cols), each 96x96.
    """

    def __init__(self, headless: bool = False, screenshot_path: Optional[str] = None):
        if Image is None:
            raise RuntimeError("Pillow is required for the emulator. Please install pillow.")
        self.headless = headless
        self.screenshot_path = screenshot_path
        self.size = (5 * 96, 3 * 96)
        # Layers: background + key tiles => composed into _canvas
        self._bg_image: Optional[Image.Image] = Image.new("RGB", self.size, (30, 30, 30))
        self._tiles = {i: None for i in range(1, 16)}  # type: ignore[var-annotated]
        self._canvas = Image.new("RGB", self.size, (30, 30, 30))
        self._dirty = True
        self._brightness = 10
        self._mode = 2
        self._opened = False
        self._stop_read = threading.Event()
        self._gui = None
        # Input handling
        self._event_queue = []  # list of tuples (key_index, pressed_bool, timestamp)
        self._queue_lock = threading.Lock()
        self._key_callback = None

    # SDK-like methods
    def open(self):
        # Mark as opened; GUI will be created in wait_visible() on the main thread for reliability.
        self._opened = True
        # Do not start Tk in a background thread here, as some environments require Tk in the main thread.
        return 0

    def init(self):
        # No-op for emulator
        pass

    def close(self):
        self._stop_read.set()
        if self._gui is not None:
            try:
                self._gui.stop()
            except Exception:
                pass
            self._gui = None

    def set_brightness(self, percent: int):
        self._brightness = max(0, min(100, int(percent)))
        return 0

    def switch_mode(self, mode: int):
        self._mode = int(mode)
        return 0

    def set_key_image(self, key: int, path: str):
        if key < 1 or key > 15:
            return -1
        if not os.path.exists(path):
            return -1
        try:
            img = Image.open(path).convert("RGB")
            img = img.resize((96, 96), Image.LANCZOS)
            self._tiles[key] = img
            self._dirty = True
            return 0
        except Exception:
            return -1

    def refresh(self):
        # Recompose if needed
        if self._dirty:
            self._compose()
        # On refresh, optionally dump a screenshot if a path is provided
        if self.screenshot_path:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.screenshot_path), exist_ok=True)
            self._canvas.save(self.screenshot_path)
        # Update GUI if present (legacy path; currently we prefer showing on main thread in wait_visible)
        self._update_gui()

    # New: set full-screen background image (touchscreen image)
    def set_touchscreen_image(self, path: str):
        if not os.path.exists(path):
            return -1
        try:
            img = Image.open(path).convert("RGB")
            img = img.resize(self.size, Image.LANCZOS)
            self._bg_image = img
            self._dirty = True
            return 0
        except Exception:
            return -1

    def register_key_callback(self, callback: Callable[[int, bool, float], None]):
        self._key_callback = callback

    def _compose(self):
        # Start with background
        base = (self._bg_image if self._bg_image is not None else Image.new("RGB", self.size, (30, 30, 30))).copy()
        # Paste tiles
        for key, tile in self._tiles.items():
            if tile is not None:
                x, y = self._key_to_xy(key)
                base.paste(tile, (x, y))
        # Optional overlay to show pressed keys
        if hasattr(self, "_pressed_keys") and self._pressed_keys:
            draw = ImageDraw.Draw(base)
            for key in self._pressed_keys:
                x, y = self._key_to_xy(key)
                draw.rectangle([x, y, x + 95, y + 95], outline=(255, 255, 0), width=3)
        self._canvas = base
        self._dirty = False

    def _update_gui(self):
        if self._gui is not None:
            try:
                self._gui.update_image(self._canvas)
            except Exception:
                pass

    def wait_visible(self, seconds: float):
        """Block and display the current canvas in a PySide6 window for the given seconds.
        Also capture keyboard events and emit them as device key events.
        Mapping:
          1..5 -> keys 1..5
          Q W E R T -> keys 6..10
          A S D F G -> keys 11..15
        """
        try:
            secs = max(0.0, float(seconds))
        except Exception:
            secs = 0.0
        if secs <= 0:
            return
        if self.headless:
            time.sleep(secs)
            return
        # Create a PySide6 window on the main thread, no fallbacks
        try:
            from PySide6 import QtWidgets, QtGui, QtCore  # type: ignore
        except Exception as e:
            raise RuntimeError("PySide6 is required for the emulator GUI. Please install PySide6 in the emulator venv.") from e

        # Ensure there is a QApplication
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication([])

        # Build window
        win = QtWidgets.QMainWindow()
        win.setWindowTitle("StreamDock Emulator")
        win.setFixedSize(self.size[0], self.size[1])
        label = QtWidgets.QLabel()
        label.setFixedSize(self.size[0], self.size[1])
        win.setCentralWidget(label)

        # Key mapping
        from PySide6.QtCore import Qt
        key_map = {
            Qt.Key.Key_1: 1, Qt.Key.Key_2: 2, Qt.Key.Key_3: 3, Qt.Key.Key_4: 4, Qt.Key.Key_5: 5,
            Qt.Key.Key_Q: 6, Qt.Key.Key_W: 7, Qt.Key.Key_E: 8, Qt.Key.Key_R: 9, Qt.Key.Key_T: 10,
            Qt.Key.Key_A: 11, Qt.Key.Key_S: 12, Qt.Key.Key_D: 13, Qt.Key.Key_F: 14, Qt.Key.Key_G: 15,
        }
        self._pressed_keys = set()

        def pil_to_pixmap(pil_img):
            p = pil_img.resize(self.size, Image.NEAREST).convert("RGB")
            data = p.tobytes("raw", "RGB")
            qimg = QtGui.QImage(data, p.width, p.height, p.width * 3, QtGui.QImage.Format.Format_RGB888)
            return QtGui.QPixmap.fromImage(qimg)

        # Ensure initial compose
        if self._dirty:
            self._compose()
        label.setPixmap(pil_to_pixmap(self._canvas))

        # Event handlers
        def handle_event(qkey, pressed: bool):
            if qkey in key_map:
                key_index = key_map[qkey]
                now = time.time()
                # pressed set management for highlight
                if pressed:
                    self._pressed_keys.add(key_index)
                else:
                    self._pressed_keys.discard(key_index)
                # enqueue event
                self._enqueue_event(key_index, pressed, now)
                # redraw with highlight
                self._dirty = True

        def keyPressEvent(event):
            handle_event(event.key(), True)

        def keyReleaseEvent(event):
            handle_event(event.key(), False)

        # Install handlers on the central widget
        win.keyPressEvent = keyPressEvent  # type: ignore
        win.keyReleaseEvent = keyReleaseEvent  # type: ignore

        # Periodic repaint to reflect highlights
        repaint_timer = QtCore.QTimer()
        repaint_timer.setInterval(50)  # ~20 FPS
        def repaint():
            if self._dirty:
                self._compose()
                label.setPixmap(pil_to_pixmap(self._canvas))
        repaint_timer.timeout.connect(repaint)
        repaint_timer.start()

        # Show window and close after delay
        win.show()
        close_timer = QtCore.QTimer()
        close_timer.setSingleShot(True)
        close_timer.timeout.connect(win.close)
        close_timer.start(int(secs * 1000))
        app.exec()

    def whileread(self):
        # Simulate a blocking read loop until closed
        log_keys = os.getenv("STREAMDOCK_EMULATOR_LOG_KEYS", "0") == "1"
        while not self._stop_read.is_set():
            events = self._drain_events()
            if events:
                cb = self._key_callback
                for key_index, pressed, ts in events:
                    if cb:
                        try:
                            cb(key_index, pressed, ts)
                        except Exception:
                            pass
                    elif log_keys:
                        state = "down" if pressed else "up"
                        print(f"[emulator] key {key_index} {state} @ {ts:.3f}")
            time.sleep(0.01)

    # Helper methods specific to emulator
    def save_screenshot(self, path: str):
        # Ensure latest composition before saving
        if self._dirty:
            self._compose()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._canvas.save(path)

    def _enqueue_event(self, key_index: int, pressed: bool, ts: float):
        with self._queue_lock:
            self._event_queue.append((key_index, pressed, ts))

    def _drain_events(self):
        with self._queue_lock:
            ev = self._event_queue
            self._event_queue = []
        return ev

    def _key_to_xy(self, key: int) -> Tuple[int, int]:
        idx = key - 1
        row = idx // 5
        col = idx % 5
        return col * 96, row * 96
