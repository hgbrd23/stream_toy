"""
Test file-based caching in BaseScene.

Tests that BaseScene correctly caches generated images to disk
and reuses them on subsequent calls.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from PIL import Image

from stream_toy.scene.base_scene import BaseScene


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


class MockRuntime:
    """Mock runtime for testing."""
    def __init__(self, device):
        self.device = device
        self.input_manager = MockInputManager()


class TestScene(BaseScene):
    """Concrete scene for testing."""
    async def on_enter(self):
        pass

    async def on_exit(self):
        pass

    async def main_loop(self):
        pass


class TestBaseSceneCache(unittest.TestCase):
    """Test BaseScene file-based caching."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary cache directory
        self.temp_cache_dir = Path(tempfile.mkdtemp())

        # Override BaseScene.CACHE_DIR
        self.original_cache_dir = BaseScene.CACHE_DIR
        BaseScene.CACHE_DIR = self.temp_cache_dir

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

    def test_cache_directory_created(self):
        """Test that cache directory is created on initialization."""
        self.assertTrue(self.temp_cache_dir.exists())

    def test_get_cache_path(self):
        """Test cache path generation."""
        cache_key = "test|Hello|fs24|fgwhite|bgblack|wFalse|ts112"
        cache_path = self.scene._get_cache_path(cache_key)

        # Should be in temp cache dir
        self.assertEqual(cache_path.parent, self.temp_cache_dir)

        # Should end with .png
        self.assertTrue(cache_path.name.endswith('.png'))

        # Should contain sanitized prefix
        self.assertTrue(cache_path.name.startswith('test_Hello_fs24_fgwhite_bg'))

    def test_is_cached_false(self):
        """Test _is_cached returns False for non-existent cache."""
        cache_key = "test|not_cached"
        self.assertFalse(self.scene._is_cached(cache_key))

    def test_cache_image(self):
        """Test caching an image to disk."""
        cache_key = "test|blue_square"
        img = Image.new('RGB', (112, 112), 'blue')

        # Cache the image
        cache_path = self.scene._cache_image(cache_key, img)

        # Verify file was created
        self.assertTrue(cache_path.exists())
        self.assertGreater(cache_path.stat().st_size, 0)

        # Verify it's cached
        self.assertTrue(self.scene._is_cached(cache_key))

        # Verify image can be loaded back
        loaded_img = Image.open(cache_path)
        self.assertEqual(loaded_img.size, (112, 112))

    def test_cache_image_idempotent(self):
        """Test caching same image twice doesn't recreate file."""
        cache_key = "test|idempotent"
        img = Image.new('RGB', (112, 112), 'red')

        # Cache first time
        cache_path1 = self.scene._cache_image(cache_key, img)
        mtime1 = cache_path1.stat().st_mtime

        # Cache second time (should not recreate)
        cache_path2 = self.scene._cache_image(cache_key, img)
        mtime2 = cache_path2.stat().st_mtime

        # Should be same path and same mtime
        self.assertEqual(cache_path1, cache_path2)
        self.assertEqual(mtime1, mtime2)

    def test_set_tile_text_caching(self):
        """Test that set_tile_text uses caching."""
        # First call - should generate and cache
        self.scene.set_tile_text(0, 0, "Hello", font_size=24)

        # Verify device was called
        self.assertEqual(len(self.device.tile_calls), 1)
        first_call = self.device.tile_calls[0]

        # Verify cache file was created
        cache_path = Path(first_call['path'])
        self.assertTrue(cache_path.exists())

        # Second call with same parameters - should use cache
        self.device.tile_calls.clear()
        self.scene.set_tile_text(0, 0, "Hello", font_size=24)

        # Verify device was called again (but should use same cached file)
        self.assertEqual(len(self.device.tile_calls), 1)
        second_call = self.device.tile_calls[0]

        # Should use same cached file path
        self.assertEqual(first_call['path'], second_call['path'])
        self.assertEqual(first_call['cache_key'], second_call['cache_key'])

    def test_set_tile_text_different_params(self):
        """Test that different parameters create different cache entries."""
        # Call with first parameters
        self.scene.set_tile_text(0, 0, "Hello", font_size=24, fg_color="white")
        first_path = self.device.tile_calls[0]['path']

        # Call with different parameters
        self.device.tile_calls.clear()
        self.scene.set_tile_text(0, 0, "Hello", font_size=32, fg_color="white")
        second_path = self.device.tile_calls[0]['path']

        # Should create different cache files
        self.assertNotEqual(first_path, second_path)

        # Both should exist
        self.assertTrue(Path(first_path).exists())
        self.assertTrue(Path(second_path).exists())

    def test_set_tile_file(self):
        """Test set_tile_file passes path directly."""
        # Create a temporary image file
        temp_img_path = self.temp_cache_dir / "test_image.png"
        img = Image.new('RGB', (112, 112), 'green')
        img.save(temp_img_path)

        # Call set_tile_file
        self.scene.set_tile_file(0, 0, str(temp_img_path))

        # Verify device was called with the path
        self.assertEqual(len(self.device.tile_calls), 1)
        call = self.device.tile_calls[0]

        # Should pass the original file path (as string or Path)
        self.assertEqual(str(call['path']), str(temp_img_path))

    def test_clear_tile_caching(self):
        """Test that clear_tile uses caching."""
        # Clear to black
        self.scene.clear_tile(0, 0, "black")
        first_path = self.device.tile_calls[0]['path']

        # Clear another tile to black
        self.device.tile_calls.clear()
        self.scene.clear_tile(1, 1, "black")
        second_path = self.device.tile_calls[0]['path']

        # Should use same cached file
        self.assertEqual(first_path, second_path)

        # Clear to different color
        self.device.tile_calls.clear()
        self.scene.clear_tile(0, 0, "white")
        third_path = self.device.tile_calls[0]['path']

        # Should use different cached file
        self.assertNotEqual(first_path, third_path)


if __name__ == '__main__':
    unittest.main()
