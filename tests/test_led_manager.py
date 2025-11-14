"""
Unit tests for LEDManager
"""

import unittest
import time
from stream_toy.led_manager import LEDManager, FakeNeoPixel


class TestFakeNeoPixel(unittest.TestCase):
    """Test FakeNeoPixel implementation."""

    def test_initialization(self):
        """Test pixel strip initialization."""
        pixels = FakeNeoPixel(10, brightness=0.5)

        self.assertEqual(len(pixels), 10)
        self.assertEqual(pixels.brightness, 0.5)

    def test_set_pixel(self):
        """Test setting individual pixel."""
        pixels = FakeNeoPixel(10)

        pixels[0] = (255, 0, 0)
        self.assertEqual(pixels[0], (255, 0, 0))

        pixels[5] = (0, 255, 0)
        self.assertEqual(pixels[5], (0, 255, 0))

    def test_fill(self):
        """Test filling all pixels."""
        pixels = FakeNeoPixel(10)

        pixels.fill((100, 100, 100))

        for i in range(10):
            self.assertEqual(pixels[i], (100, 100, 100))


class TestLEDManager(unittest.TestCase):
    """Test LEDManager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Use fake mode (no hardware)
        self.manager = LEDManager(pin=None, num_leds=90, brightness=0.5)

    def test_initialization(self):
        """Test LED manager initialization."""
        self.assertEqual(self.manager.num_leds, 90)
        self.assertEqual(self.manager.brightness, 0.5)
        self.assertIsNotNone(self.manager.pixels)

    def test_start_stop(self):
        """Test starting and stopping LED manager."""
        self.manager.start()
        time.sleep(0.2)
        self.assertTrue(self.manager._running)

        self.manager.stop()
        time.sleep(0.2)
        self.assertFalse(self.manager._running)

    def test_set_all(self):
        """Test setting all LEDs."""
        self.manager.set_all((255, 0, 0))

        # Verify all pixels are red
        for i in range(self.manager.num_leds):
            self.assertEqual(self.manager.pixels[i], (255, 0, 0))


if __name__ == '__main__':
    unittest.main()
