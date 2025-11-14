"""
Tests for WebDevice emulator.

Tests web server initialization, Socket.IO communication,
tile updates, button events, and client reconnection.
"""

import unittest
import time
import base64
from io import BytesIO
from PIL import Image
import random

from stream_toy.device.web_device import WebDevice
from stream_toy.web import server


class TestWebDevice(unittest.TestCase):
    """Test cases for WebDevice browser emulator."""

    def setUp(self):
        """Set up test fixtures."""
        # Use a unique random port for each test to avoid conflicts
        self.test_port = random.randint(6000, 9000)
        self.device = None

        # Track received events
        self.received_tile_updates = []
        self.received_led_updates = []
        self.button_events = []

    def tearDown(self):
        """Clean up after tests."""
        if self.device and self.device._initialized:
            self.device.close()
        # Give server time to cleanup
        time.sleep(0.3)

    def test_device_initialization(self):
        """Test WebDevice can be initialized."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)
        self.assertFalse(self.device._initialized)

        # Initialize device
        self.device.initialize()

        # Give server time to start
        time.sleep(0.5)

        self.assertTrue(self.device._initialized)
        self.assertIsNotNone(self.device._server_thread)
        self.assertTrue(self.device._led_update_running)

    def test_tile_cache_initialized(self):
        """Test tile cache is initialized."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)
        self.assertIsNotNone(self.device._tile_cache)
        self.assertIsInstance(self.device._tile_cache, dict)
        self.assertEqual(len(self.device._tile_cache), 0)

    def test_set_tile_queues_update(self):
        """Test set_tile queues updates correctly."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)

        # Create test image
        test_image = Image.new('RGB', (128, 128), color='red')

        # Set tile
        self.device.set_tile(0, 0, test_image)

        # Verify it's queued
        self.assertIn((0, 0), self.device._tile_queue)
        # Should not be in cache yet (before submit)
        self.assertNotIn((0, 0), self.device._tile_cache)

    def test_submit_updates_cache(self):
        """Test submit updates the tile cache."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)
        self.device.initialize()
        time.sleep(0.5)

        # Create and set test image
        test_image = Image.new('RGB', (128, 128), color='blue')
        self.device.set_tile(1, 2, test_image)

        # Submit
        self.device.submit()

        # Verify cache updated
        self.assertIn((1, 2), self.device._tile_cache)
        # Queue should be cleared
        self.assertNotIn((1, 2), self.device._tile_queue)
        self.assertEqual(len(self.device._tile_queue), 0)

    def test_tile_validation(self):
        """Test tile coordinate validation."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)
        test_image = Image.new('RGB', (128, 128), color='white')

        # Valid coordinates (0-2 rows, 0-4 cols)
        self.device.set_tile(0, 0, test_image)  # Should work
        self.device.set_tile(2, 4, test_image)  # Should work

        # Invalid row
        with self.assertRaises(ValueError):
            self.device.set_tile(3, 0, test_image)

        # Invalid column
        with self.assertRaises(ValueError):
            self.device.set_tile(0, 5, test_image)

        # Negative coordinates
        with self.assertRaises(ValueError):
            self.device.set_tile(-1, 0, test_image)

    def test_tile_image_resizing(self):
        """Test images are resized to tile size."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)

        # Create oversized image
        large_image = Image.new('RGB', (256, 256), color='green')

        self.device.set_tile(0, 0, large_image)

        # Verify image in queue is resized
        queued_image = self.device._tile_queue[(0, 0)]
        self.assertEqual(queued_image.size, (128, 128))

    def test_button_callback_registration(self):
        """Test button callback can be registered."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)

        def test_callback(row, col, is_pressed):
            self.button_events.append((row, col, is_pressed))

        self.device.register_key_callback(test_callback)

        # Simulate button event
        self.device._on_button_event(1, 3, True)

        # Verify callback was called
        self.assertEqual(len(self.button_events), 1)
        self.assertEqual(self.button_events[0], (1, 3, True))

    def test_button_press_and_release(self):
        """Test button press and release events."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)

        def test_callback(row, col, is_pressed):
            self.button_events.append((row, col, is_pressed))

        self.device.register_key_callback(test_callback)

        # Simulate button press
        self.device._on_button_event(0, 0, True)
        # Simulate button release
        self.device._on_button_event(0, 0, False)

        # Verify both events
        self.assertEqual(len(self.button_events), 2)
        self.assertEqual(self.button_events[0], (0, 0, True))
        self.assertEqual(self.button_events[1], (0, 0, False))

    def test_multiple_tiles_in_cache(self):
        """Test multiple tiles can be cached."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)
        self.device.initialize()
        time.sleep(0.5)

        # Set multiple tiles
        colors = ['red', 'green', 'blue', 'yellow']
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]

        for (row, col), color in zip(positions, colors):
            img = Image.new('RGB', (128, 128), color=color)
            self.device.set_tile(row, col, img)

        # Submit all at once
        self.device.submit()

        # Verify all are cached
        for pos in positions:
            self.assertIn(pos, self.device._tile_cache)

        self.assertEqual(len(self.device._tile_cache), len(positions))

    def test_on_client_connected_with_cache(self):
        """Test on_client_connected handles cached tiles."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)
        self.device.initialize()
        time.sleep(0.5)

        # Set a tile to populate cache
        test_image = Image.new('RGB', (128, 128), color='purple')
        self.device.set_tile(2, 3, test_image)
        self.device.submit()

        # Verify cache has the tile
        self.assertIn((2, 3), self.device._tile_cache)

        # Call on_client_connected (this should not crash)
        try:
            self.device.on_client_connected()
            success = True
        except AttributeError:
            success = False

        self.assertTrue(success, "on_client_connected raised AttributeError")

    def test_on_client_connected_empty_cache(self):
        """Test on_client_connected handles empty cache."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)
        self.device.initialize()
        time.sleep(0.5)

        # No tiles set, cache is empty
        self.assertEqual(len(self.device._tile_cache), 0)

        # Call on_client_connected (should not crash with empty cache)
        try:
            self.device.on_client_connected()
            success = True
        except Exception as e:
            success = False

        self.assertTrue(success, "on_client_connected failed with empty cache")

    def test_device_close(self):
        """Test device cleanup on close."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)
        self.device.initialize()
        time.sleep(0.5)

        self.assertTrue(self.device._initialized)
        self.assertTrue(self.device._led_update_running)

        # Close device
        self.device.close()

        # Verify cleanup
        self.assertFalse(self.device._initialized)
        self.assertFalse(self.device._led_update_running)

    def test_led_manager_initialized(self):
        """Test LED manager is initialized in fake mode."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)

        self.assertIsNotNone(self.device.led_manager)
        # Should be in fake mode (pin=None)
        self.assertTrue(self.device.led_manager._fake_mode)
        self.assertEqual(self.device.led_manager.num_leds, 90)

    def test_leds_have_default_color(self):
        """Test LEDs are initialized with visible color (not black)."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)
        self.device.initialize()
        time.sleep(0.5)

        # Get LED colors
        led_colors = self.device.led_manager.get_pixel_data()

        # Should have 90 LEDs
        self.assertEqual(len(led_colors), 90)

        # LEDs should not be all black (should have fallback color)
        all_black = all(r == 0 and g == 0 and b == 0 for r, g, b in led_colors)
        self.assertFalse(all_black, "LEDs should not be black - fallback color should be set")

        # Should have cyan-ish color (0, 40, 40)
        first_led = led_colors[0]
        self.assertGreater(first_led[1], 0, "Green channel should be > 0")
        self.assertGreater(first_led[2], 0, "Blue channel should be > 0")

    def test_tile_overwrite_in_queue(self):
        """Test setting the same tile multiple times before submit."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)

        # Set same tile twice with different colors
        img1 = Image.new('RGB', (128, 128), color='red')
        self.device.set_tile(0, 0, img1)

        img2 = Image.new('RGB', (128, 128), color='blue')
        self.device.set_tile(0, 0, img2)

        # Should only have one entry in queue (overwritten)
        self.assertEqual(len(self.device._tile_queue), 1)
        self.assertIn((0, 0), self.device._tile_queue)

    def test_cache_persists_after_multiple_submits(self):
        """Test cache persists and accumulates across multiple submits."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)
        self.device.initialize()
        time.sleep(0.5)

        # First submit
        img1 = Image.new('RGB', (128, 128), color='red')
        self.device.set_tile(0, 0, img1)
        self.device.submit()

        # Second submit
        img2 = Image.new('RGB', (128, 128), color='green')
        self.device.set_tile(1, 1, img2)
        self.device.submit()

        # Both should be in cache
        self.assertIn((0, 0), self.device._tile_cache)
        self.assertIn((1, 1), self.device._tile_cache)
        self.assertEqual(len(self.device._tile_cache), 2)

    def test_cache_updates_on_tile_overwrite(self):
        """Test cache updates when same tile is submitted again."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)
        self.device.initialize()
        time.sleep(0.5)

        # First color
        img1 = Image.new('RGB', (128, 128), color='red')
        self.device.set_tile(0, 0, img1)
        self.device.submit()

        # Overwrite with different color
        img2 = Image.new('RGB', (128, 128), color='blue')
        self.device.set_tile(0, 0, img2)
        self.device.submit()

        # Should still have one entry, but updated
        self.assertEqual(len(self.device._tile_cache), 1)
        self.assertIn((0, 0), self.device._tile_cache)

    def test_client_receives_tiles_on_connect_after_submit(self):
        """Test client receives tiles that were submitted before connection."""
        self.device = WebDevice(host='127.0.0.1', port=self.test_port)
        self.device.initialize()
        time.sleep(0.5)

        # Submit tiles BEFORE client connects
        colors = ['red', 'green', 'blue']
        for idx, color in enumerate(colors):
            img = Image.new('RGB', (128, 128), color=color)
            self.device.set_tile(0, idx, img)

        self.device.submit()

        # Verify tiles are in cache
        self.assertEqual(len(self.device._tile_cache), 3)

        # Now simulate client connection
        # on_client_connected should resend all cached tiles
        tile_count_before = len(self.device._tile_cache)

        # Call on_client_connected (simulating what happens when browser connects)
        try:
            self.device.on_client_connected()
            success = True
        except Exception as e:
            self.fail(f"on_client_connected() failed: {e}")
            success = False

        self.assertTrue(success)
        # Cache should still have the same tiles
        self.assertEqual(len(self.device._tile_cache), tile_count_before)


class TestWebServer(unittest.TestCase):
    """Test cases for web server module."""

    def test_server_module_imports(self):
        """Test server module can be imported."""
        from stream_toy.web import server
        self.assertIsNotNone(server.app)
        self.assertIsNotNone(server.socketio)

    def test_set_web_device(self):
        """Test set_web_device function."""
        from stream_toy.web import server

        # Create a mock device
        device = WebDevice(host='127.0.0.1', port=6789)

        # Set device
        server.set_web_device(device)

        # Verify it's set (accessing private variable for test)
        self.assertEqual(server._web_device, device)


if __name__ == '__main__':
    unittest.main()
