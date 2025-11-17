"""
Test performance optimizations in BaseScene.

Tests font caching and text rendering fast paths.
"""

import unittest
import tempfile
import shutil
from pathlib import Path

from stream_toy.scene.base_scene import BaseScene, _FONT_CACHE


class MockDevice:
    """Mock device for testing."""
    TILE_SIZE = 112
    TILE_ROWS = 3
    TILE_COLS = 5

    def __init__(self):
        self.tile_calls = []

    def set_tile(self, row, col, path, cache_key=None):
        """Track set_tile calls."""
        self.tile_calls.append({
            'row': row,
            'col': col,
            'path': path,
            'cache_key': cache_key
        })

    def submit(self):
        """Mock submit."""
        pass


class MockInputManager:
    """Mock input manager for testing."""
    pass


class MockStateManager:
    """Mock state manager for testing."""
    def __init__(self):
        self.tile_calls = []

    def set_tile(self, row, col, path, cache_key=None):
        """Track set_tile calls."""
        self.tile_calls.append({
            'row': row,
            'col': col,
            'path': path,
            'cache_key': cache_key
        })

    def submit(self):
        """Mock submit."""
        pass


class MockRuntime:
    """Mock runtime for testing."""
    def __init__(self, device):
        self.device = device
        self.input_manager = MockInputManager()
        self.state_manager = MockStateManager()


class TestScene(BaseScene):
    """Concrete scene for testing."""
    async def on_enter(self):
        pass

    async def on_exit(self):
        pass

    async def main_loop(self):
        pass


class TestSceneOptimizations(unittest.TestCase):
    """Test BaseScene performance optimizations."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary cache directory
        self.temp_cache_dir = Path(tempfile.mkdtemp())

        # Override BaseScene.CACHE_DIR
        self.original_cache_dir = BaseScene.CACHE_DIR
        BaseScene.CACHE_DIR = self.temp_cache_dir

        # Clear font cache
        global _FONT_CACHE
        _FONT_CACHE.clear()

        # Create mock device and scene
        self.device = MockDevice()
        self.runtime = MockRuntime(self.device)
        self.scene = TestScene(self.runtime)

    def tearDown(self):
        """Clean up test fixtures."""
        # Restore original cache directory
        BaseScene.CACHE_DIR = self.original_cache_dir

        # Remove temporary directory
        if self.temp_cache_dir.exists():
            shutil.rmtree(self.temp_cache_dir)

    def test_font_caching(self):
        """Test that fonts are cached and reused."""
        # Clear font cache
        _FONT_CACHE.clear()
        initial_size = len(_FONT_CACHE)
        self.assertEqual(initial_size, 0)

        # Load font first time
        font1 = self.scene._get_font(18)
        after_first_load = len(_FONT_CACHE)
        self.assertEqual(after_first_load, 1, "Font cache should have 1 entry after first load")

        # Load same font again (should use cache)
        font2 = self.scene._get_font(18)
        after_second_load = len(_FONT_CACHE)
        self.assertEqual(after_second_load, 1, "Font cache should still have 1 entry (reused)")
        self.assertIs(font1, font2, "Should return same font object from cache")

        # Load different size (should create new entry)
        font3 = self.scene._get_font(24)
        after_third_load = len(_FONT_CACHE)
        self.assertEqual(after_third_load, 2, "Font cache should have 2 entries for different sizes")
        self.assertIsNot(font1, font3, "Different sizes should have different font objects")

    def test_font_cache_persists_across_scenes(self):
        """Test that font cache is shared across different scene instances."""
        # Clear font cache
        _FONT_CACHE.clear()

        # Create first scene and load font
        scene1 = TestScene(self.runtime)
        font1 = scene1._get_font(18)
        cache_size_after_scene1 = len(_FONT_CACHE)

        # Create second scene and load same font
        scene2 = TestScene(self.runtime)
        font2 = scene2._get_font(18)
        cache_size_after_scene2 = len(_FONT_CACHE)

        # Cache size should not increase (font reused)
        self.assertEqual(cache_size_after_scene1, cache_size_after_scene2)
        self.assertIs(font1, font2, "Same font should be reused across scene instances")

    def test_text_rendering_with_cached_font(self):
        """Test that text rendering uses cached fonts."""
        # Clear font cache
        _FONT_CACHE.clear()

        # Render text twice with same font size
        self.scene.set_tile_text(0, 0, "Test1", font_size=18)
        cache_after_first = len(_FONT_CACHE)

        self.scene.set_tile_text(0, 1, "Test2", font_size=18)
        cache_after_second = len(_FONT_CACHE)

        # Font should be cached and reused
        self.assertEqual(cache_after_first, cache_after_second,
                        "Font cache should not grow when reusing same font size")

    def test_fast_path_no_wrap(self):
        """Test that simple text without wrapping uses fast path."""
        # This test verifies the code path but doesn't measure performance
        # The fast path skips textbbox calls for wrapping

        # Simple text without wrapping (default wrap=False)
        self.scene.set_tile_text(0, 0, "5:23", font_size=18)

        # Should complete without error and generate cached image
        self.assertEqual(len(self.runtime.state_manager.tile_calls), 1)

        # Verify cache was created
        cache_key = "text|5:23|fs18|fgwhite|bgblack|wFalse|ts112"
        self.assertTrue(self.scene._is_cached(cache_key))

    def test_wrap_enabled_uses_full_path(self):
        """Test that wrapped text uses full wrapping logic."""
        # Text with wrapping enabled
        self.scene.set_tile_text(0, 0, "Long filename that needs wrapping",
                                font_size=10, wrap=True)

        # Should complete without error
        self.assertEqual(len(self.runtime.state_manager.tile_calls), 1)

        # Verify cache was created
        cache_key = "text|Long filename that needs wrapping|fs10|fgwhite|bgblack|wTrue|ts112"
        self.assertTrue(self.scene._is_cached(cache_key))


if __name__ == '__main__':
    unittest.main()
