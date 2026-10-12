"""
Hardware-free tests for StreamDock293V3Device.

The SDK device and its transport are replaced by fakes that record calls, so
nothing here touches USB.
"""

import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from PIL import Image

from stream_toy import tile_cache
from stream_toy.device.streamdock293v3_device import StreamDock293V3Device


class FakeTransport:
    """Records USB writes made by the device wrapper."""

    def __init__(self):
        self.calls = []

    def setKeyImgDualDevice(self, c_path, key):
        self.calls.append(('key', c_path.value.decode('utf-8'), key))
        return 1

    def setBackgroundImgDualDevice(self, c_path):
        self.calls.append(('background', c_path.value.decode('utf-8')))
        return 1

    def refresh(self):
        self.calls.append(('refresh',))


class FakeSdkDevice:
    def __init__(self):
        self.transport = FakeTransport()

    def key(self, k):
        return k

    def refresh(self):
        self.transport.refresh()


class StreamDockDeviceTestBase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.original_cache_dir = tile_cache.CACHE_DIR
        tile_cache.CACHE_DIR = self.temp_dir / "cache"

        self.device = StreamDock293V3Device()
        self.device.sdk_device = FakeSdkDevice()
        self.calls = self.device.sdk_device.transport.calls

    def tearDown(self):
        tile_cache.CACHE_DIR = self.original_cache_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def make_image(self, name, size=(112, 112), color='red'):
        path = self.temp_dir / name
        Image.new('RGB', size, color).save(path)
        return path


class TestFlushTiles(StreamDockDeviceTestBase):

    def test_only_changed_cache_keys_are_sent(self):
        a = self.make_image("a.png", color='red')
        b = self.make_image("b.png", color='blue')

        self.device.flush_tiles({(0, 0): (a, "key_a"), (0, 1): (b, "key_b")})
        self.assertEqual([c[0] for c in self.calls], ['key', 'key', 'refresh'])

        self.calls.clear()
        self.device.flush_tiles({(0, 0): (a, "key_a"), (0, 1): (a, "key_a2")})
        self.assertEqual([c[0] for c in self.calls], ['key', 'refresh'])
        _, path, key = self.calls[0]
        self.assertEqual(key, StreamDock293V3Device.TILE_TO_BUTTON[(0, 1)])
        self.assertEqual(Path(path), tile_cache.cache_path_for(a, '_native.jpg'))
        with Image.open(path) as img:
            self.assertEqual(img.format, 'JPEG')
            self.assertEqual(img.size, (112, 112))

    def test_unchanged_batch_does_not_refresh(self):
        a = self.make_image("a.png")
        self.device.flush_tiles({(1, 1): (a, "key_a")})
        self.calls.clear()

        self.device.flush_tiles({(1, 1): (a, "key_a")})
        self.assertEqual(self.calls, [])

    def test_empty_cache_key_is_always_sent(self):
        a = self.make_image("a.png")
        self.device.flush_tiles({(2, 4): (a, "")})
        self.calls.clear()

        self.device.flush_tiles({(2, 4): (a, "")})
        self.assertEqual([c[0] for c in self.calls], ['key', 'refresh'])
        self.assertEqual(self.calls[0][2], 15)

    def test_submit_tiles_drains_queue(self):
        a = self.make_image("a.png")
        self.device.set_tile(0, 0, a, "key_a")
        self.device.submit_tiles()
        self.assertEqual([c[0] for c in self.calls], ['key', 'refresh'])
        self.assertEqual(self.device.pop_queued_tiles(), {})


class TestReadyAck(unittest.TestCase):

    def test_real_ack_is_detected(self):
        result = (b'ACK\x00\x00OK\x00\x00\x00\x00\x00\x00', 'ACK', 'OK', 0, 0)
        self.assertTrue(StreamDock293V3Device._is_ready_ack(result[0], result[3]))

    def test_button_event_is_not_an_ack(self):
        result_bytes = b'ACK\x00\x00OK\x00\x00\x07\x00\x00\x00'
        self.assertFalse(StreamDock293V3Device._is_ready_ack(result_bytes, 7))
        result_bytes = b'ACK\x00\x00OK\x00\x00\x0f\x01\x00\x00'
        self.assertFalse(StreamDock293V3Device._is_ready_ack(result_bytes, 15))

    def test_nonzero_status_bytes_are_not_an_ack(self):
        self.assertFalse(StreamDock293V3Device._is_ready_ack(b'ACK\x01\x00OK\x00\x00\x00\x00\x00', 0))


class TestSetBackgroundImage(StreamDockDeviceTestBase):

    def test_sends_cached_background_and_waits_for_ack(self):
        source = self.make_image("splash.png", size=(800, 480))
        timer = threading.Timer(0.1, lambda: setattr(self.device, '_device_busy', False))
        timer.start()
        try:
            self.assertTrue(self.device.set_background_image(source, timeout=2.0))
        finally:
            timer.cancel()

        self.assertEqual([c[0] for c in self.calls], ['background', 'refresh'])
        sent = Path(self.calls[0][1])
        self.assertEqual(sent, tile_cache.cache_path_for(source, '_background.jpg'))
        self.assertEqual(sent.parent, tile_cache.CACHE_DIR)
        with Image.open(sent) as img:
            self.assertEqual(img.format, 'JPEG')
            self.assertEqual(img.size, (800, 480))

    def test_returns_false_on_ack_timeout(self):
        source = self.make_image("splash.png", size=(800, 480))
        self.assertFalse(self.device.set_background_image(source, timeout=0.05))
        self.assertFalse(self.device._device_busy)

    def test_tiles_wait_for_background_refresh(self):
        source = self.make_image("splash.png", size=(800, 480))
        tile = self.make_image("a.png")
        tile_cache.native_background_jpeg(source)

        bg_thread = threading.Thread(
            target=self.device.set_background_image, args=(source,), kwargs={'timeout': 2.0})
        flush_thread = None
        bg_thread.start()
        try:
            # Wait until the background was sent and the ACK wait started
            for _ in range(200):
                if self.calls and self.device._device_busy:
                    break
                threading.Event().wait(0.01)

            flush_thread = threading.Thread(
                target=self.device.flush_tiles, args=({(0, 0): (tile, "k")},))
            flush_thread.start()
            flush_thread.join(timeout=0.2)
            self.assertTrue(flush_thread.is_alive(), "tiles sent during background refresh")
            self.assertEqual([c[0] for c in self.calls], ['background', 'refresh'])
        finally:
            self.device._device_busy = False
            bg_thread.join(timeout=2.0)
            if flush_thread is not None:
                flush_thread.join(timeout=2.0)

        self.assertEqual([c[0] for c in self.calls], ['background', 'refresh', 'key', 'refresh'])

    def test_missing_image_returns_false(self):
        self.assertFalse(self.device.set_background_image(self.temp_dir / "missing.png"))
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
