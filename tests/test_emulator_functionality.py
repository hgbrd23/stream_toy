import os
import threading
import time
import unittest
from typing import List, Tuple

try:
    from PIL import Image
    _PIL_AVAILABLE = True
except Exception:  # pragma: no cover - environment without Pillow
    _PIL_AVAILABLE = False

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
ARTIFACTS_DIR = os.path.join(PROJECT_ROOT, "tests", "artifacts")


@unittest.skipUnless(_PIL_AVAILABLE, "Pillow not installed")
class TestEmulatorFunctionality(unittest.TestCase):
    def setUp(self):
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    def _make_tmp_image(self, size=(64, 64), color=(255, 0, 0), path_name="tmp.png") -> str:
        path = os.path.join(ARTIFACTS_DIR, path_name)
        img = Image.new("RGB", size, color)
        img.save(path)
        return path

    def test_background_and_tile_composition(self):
        # Import emulator device directly
        from stream_dock_emulator.devices import StreamDockN1

        # Create emulator in headless mode for deterministic testing
        dev = StreamDockN1(headless=True)
        dev.open()
        dev.init()

        # Create a blue background and a red tile
        bg_path = self._make_tmp_image(size=(480, 288), color=(0, 0, 255), path_name="bg.png")
        tile_path = self._make_tmp_image(size=(96, 96), color=(255, 0, 0), path_name="tile.png")

        # Apply background and a single key image (key 1 at (0,0))
        self.assertEqual(0, dev.set_touchscreen_image(bg_path))
        self.assertEqual(0, dev.set_key_image(1, tile_path))

        # Save composed screenshot
        shot_path = os.path.join(ARTIFACTS_DIR, "composition.png")
        dev.save_screenshot(shot_path)
        self.assertTrue(os.path.exists(shot_path))
        img = Image.open(shot_path).convert("RGB")

        # Ensure canvas size as expected (5x3 keys of 96)
        self.assertEqual(img.size, (5 * 96, 3 * 96))

        # Pixel inside key 1 should be red
        self.assertEqual((255, 0, 0), img.getpixel((10, 10)))
        # Pixel at next column (still first row) should be background blue
        self.assertEqual((0, 0, 255), img.getpixel((96 + 10, 10)))

        # Also test another placed tile mapping (key 7: row 2 (index 1), col 2 (index 1))
        # Key 7 should be at (96, 96)
        self.assertEqual(0, dev.set_key_image(7, tile_path))
        dev.save_screenshot(shot_path)
        img2 = Image.open(shot_path).convert("RGB")
        self.assertEqual((255, 0, 0), img2.getpixel((96 + 10, 96 + 10)))

    def test_set_key_image_error_conditions(self):
        from stream_dock_emulator.devices import StreamDockN1
        dev = StreamDockN1(headless=True)
        dev.open()
        dev.init()

        # Invalid key index
        self.assertEqual(-1, dev.set_key_image(0, "does_not_matter.png"))
        self.assertEqual(-1, dev.set_key_image(16, "does_not_matter.png"))

        # Missing file
        self.assertEqual(-1, dev.set_key_image(1, os.path.join(ARTIFACTS_DIR, "nope.png")))

        # Valid file
        valid = self._make_tmp_image(size=(32, 32), color=(0, 255, 0), path_name="valid.png")
        self.assertEqual(0, dev.set_key_image(1, valid))

    def test_keyboard_event_dispatch_via_callback(self):
        from stream_dock_emulator.devices import StreamDockN1

        dev = StreamDockN1(headless=True)
        dev.open()
        dev.init()

        # Collect events from callback: (key, pressed, ts)
        received: List[Tuple[int, bool, float]] = []
        dev.register_key_callback(lambda k, p, t: received.append((k, p, t)))

        # Start the read loop in a background thread
        t = threading.Thread(target=dev.whileread, daemon=True)
        t.start()

        # Enqueue a few events directly (simulate key press/release)
        # Using the emulator's internal helper is acceptable in tests.
        now = time.time()
        dev._enqueue_event(3, True, now)   # key 3 down
        dev._enqueue_event(3, False, now + 0.01)  # key 3 up
        dev._enqueue_event(12, True, now + 0.02)  # key 12 down

        # Allow the read loop to process
        time.sleep(0.1)
        dev.close()
        t.join(timeout=1.0)

        # Validate ordering and content (timestamps monotonic per our enqueue)
        self.assertGreaterEqual(len(received), 3)
        k1, p1, ts1 = received[0]
        k2, p2, ts2 = received[1]
        k3, p3, ts3 = received[2]
        self.assertEqual((k1, p1), (3, True))
        self.assertEqual((k2, p2), (3, False))
        self.assertEqual((k3, p3), (12, True))
        self.assertLess(ts1, ts2)
        self.assertLess(ts2, ts3)

    def test_wait_visible_headless_returns_quickly(self):
        from stream_dock_emulator.devices import StreamDockN1

        dev = StreamDockN1(headless=True)
        start = time.time()
        dev.wait_visible(0.1)  # Should not raise and should sleep briefly only
        self.assertGreaterEqual(time.time() - start, 0.09)


if __name__ == "__main__":
    unittest.main()
