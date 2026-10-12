"""
Tests for the shared on-disk tile cache (device JPEGs and browser PNGs).
"""

import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image

from stream_toy import tile_cache


class TestTileCache(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cache_dir = self.tmp / 'cache'
        self._patch = mock.patch.object(tile_cache, 'CACHE_DIR', self.cache_dir)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _png(self, name: str, size=(1024, 1024), color=(200, 30, 30)) -> Path:
        path = self.tmp / name
        Image.new('RGB', size, color).save(path, format='PNG')
        return path

    def test_native_key_jpeg_is_112_rotated_jpeg_q85(self):
        source = self._png('icon.png')
        # Mark one corner so the rotation can be checked
        with Image.open(source) as img:
            img = img.copy()
        img.paste((0, 0, 255), (0, 0, 256, 256))  # top-left blue
        img.save(source, format='PNG')

        path = tile_cache.native_key_jpeg(source)

        self.assertTrue(path.is_file())
        self.assertTrue(path.name.startswith('icon_'))
        self.assertTrue(path.name.endswith('_native.jpg'))
        self.assertEqual(path.parent, self.cache_dir)
        with Image.open(path) as out:
            self.assertEqual(out.format, 'JPEG')
            self.assertEqual(out.size, (112, 112))
            # Rotated by 180 degrees: blue corner is now bottom-right
            r, g, b = out.getpixel((110, 110))
            self.assertGreater(b, 150)
            self.assertLess(r, 100)

    def test_cache_hit_is_reused(self):
        source = self._png('icon.png')
        first = tile_cache.native_key_jpeg(source)
        mtime = first.stat().st_mtime_ns

        second = tile_cache.native_key_jpeg(source)

        self.assertEqual(first, second)
        self.assertEqual(second.stat().st_mtime_ns, mtime)

    def test_newer_source_regenerates(self):
        source = self._png('icon.png')
        cached = tile_cache.native_key_jpeg(source)
        old = cached.read_bytes()
        time.sleep(0.02)
        self._png('icon.png', color=(0, 200, 0))

        regenerated = tile_cache.native_key_jpeg(source)

        self.assertEqual(regenerated, cached)
        self.assertNotEqual(regenerated.read_bytes(), old)

    def test_empty_cache_file_is_regenerated(self):
        source = self._png('icon.png')
        cached = tile_cache.cache_path_for(source, '_native.jpg')
        cached.parent.mkdir(parents=True)
        cached.write_bytes(b'')
        # Make the empty file newer than the source so only the size check triggers
        time.sleep(0.02)
        cached.touch()

        result = tile_cache.native_key_jpeg(source)

        self.assertEqual(result, cached)
        self.assertGreater(cached.stat().st_size, 0)
        self.assertEqual([], [p for p in self.cache_dir.iterdir() if p.name.startswith('.tmp_')])

    def test_same_stem_different_dirs_do_not_collide(self):
        a = self._png('icon.png')
        (self.tmp / 'other').mkdir()
        b = self.tmp / 'other' / 'icon.png'
        Image.new('RGB', (64, 64), (0, 0, 0)).save(b, format='PNG')

        self.assertNotEqual(tile_cache.native_key_jpeg(a), tile_cache.native_key_jpeg(b))

    def test_background_jpeg_is_800x480(self):
        source = self._png('splash.png', size=(800, 480))

        path = tile_cache.native_background_jpeg(source)

        with Image.open(path) as out:
            self.assertEqual(out.format, 'JPEG')
            self.assertEqual(out.size, (800, 480))

    def test_web_png_returns_tile_sized_source_unchanged(self):
        source = self._png('tile.png', size=(112, 112))

        self.assertEqual(tile_cache.web_png(source), source)
        self.assertFalse(self.cache_dir.exists())

    def test_web_png_resizes_large_source(self):
        source = self._png('icon.png')

        path = tile_cache.web_png(source)

        self.assertNotEqual(path, source)
        with Image.open(path) as out:
            self.assertEqual(out.format, 'PNG')
            self.assertEqual(out.size, (112, 112))

    def test_web_png_converts_jpeg_cover(self):
        source = self.tmp / 'cover.jpg'
        Image.new('RGB', (640, 640), (1, 2, 3)).save(source, format='JPEG')

        path = tile_cache.web_png(source)

        self.assertTrue(path.name.endswith('_web.png'))
        with Image.open(path) as out:
            self.assertEqual(out.size, (112, 112))

    def test_prewarm_generates_missing_and_skips_fresh(self):
        a = self._png('a.png')
        b = self._png('b.png')
        tile_cache.native_key_jpeg(a)

        generated = tile_cache.prewarm([a, b, self.tmp / 'missing.png'], native=True, web=True)

        # a: web only; b: native + web
        self.assertEqual(generated, 3)
        self.assertEqual(tile_cache.prewarm([a, b]), 0)


if __name__ == '__main__':
    unittest.main()
