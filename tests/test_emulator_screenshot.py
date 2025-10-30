import os
import tempfile
import time
import unittest

try:
    from PIL import Image, ImageChops
    _PIL_AVAILABLE = True
except Exception:
    _PIL_AVAILABLE = False

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
ARTIFACTS_DIR = os.path.join(PROJECT_ROOT, "tests", "artifacts")


@unittest.skipUnless(_PIL_AVAILABLE, "Pillow not installed")
class TestEmulatorScreenshot(unittest.TestCase):
    def run_main_with_emulator(self, screenshot_path: str):
        # Import main and run in-process with emulator and GUI visible
        import main as main_module
        # Ensure artifacts directory exists
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        main_module.run_demo(use_emulator=True, show_gui=True, screenshot_path=screenshot_path)
        # Allow filesystem to flush
        time.sleep(0.2)
        self.assertTrue(os.path.exists(screenshot_path), "Screenshot not created")

    def _tile_box(self, key: int):
        idx = key - 1
        row = idx // 5
        col = idx % 5
        x0 = col * 96
        y0 = row * 96
        return (x0, y0, x0 + 96, y0 + 96)

    def assert_tile_matches(self, screenshot: Image.Image, key: int, expected_img_path: str):
        tile = screenshot.crop(self._tile_box(key)).convert("RGB")
        expected = Image.open(expected_img_path).convert("RGB").resize((96, 96), Image.LANCZOS)
        diff = ImageChops.difference(tile, expected)
        bbox = diff.getbbox()
        if bbox is not None:
            # For debugging, save intermediate images under artifacts dir
            base = os.path.join(ARTIFACTS_DIR, "debug")
            os.makedirs(base, exist_ok=True)
            tile.save(os.path.join(base, f"tile_k{key}.png"))
            expected.save(os.path.join(base, f"expected_k{key}.png"))
            diff.save(os.path.join(base, f"diff_k{key}.png"))
        self.assertIsNone(bbox, f"Tile for key {key} does not match expected image {expected_img_path}")

    def test_emulator_renders_expected_grid(self):
        os.makedirs(ARTIFACTS_DIR, exist_ok=True)
        screenshot_path = os.path.join(ARTIFACTS_DIR, "emulator_screenshot.png")
        self.run_main_with_emulator(screenshot_path)
        img = Image.open(screenshot_path).convert("RGB")
        # Verify canvas size
        self.assertEqual(img.size, (5 * 96, 3 * 96))

        # main sets keys 1..15 to animal_{(i % 9) + 1}
        def animal(n):
            return os.path.join(PROJECT_ROOT, "img", "memory", "set_01", f"animal_{n:02d}.png")

        # Check a few representative keys
        checks = [
            (1, animal(2)),   # key 1 -> 2
            (5, animal(6)),   # key 5 -> 6
            (9, animal(1)),   # key 9 -> 1
            (10, animal(2)),  # key 10 -> 2
            (15, animal(7)),  # key 15 -> 7
        ]
        for key, path in checks:
            self.assertTrue(os.path.exists(path), f"Missing expected asset: {path}")
            self.assert_tile_matches(img, key, path)


if __name__ == "__main__":
    unittest.main()
