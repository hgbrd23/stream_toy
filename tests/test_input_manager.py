"""
Unit tests for InputManager
"""

import unittest
import time
from stream_toy.input_manager import InputManager, InputEvent


class TestInputManager(unittest.TestCase):
    """Test InputManager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.manager = InputManager(long_press_threshold=0.5)

    def test_event_queue(self):
        """Test basic event queueing."""
        self.manager.on_device_key_event(0, 0, True)
        self.manager.on_device_key_event(0, 0, False)

        event1 = self.manager.poll_event()
        self.assertIsNotNone(event1)
        self.assertEqual(event1.row, 0)
        self.assertEqual(event1.col, 0)
        self.assertTrue(event1.is_pressed)

        event2 = self.manager.poll_event()
        self.assertIsNotNone(event2)
        self.assertEqual(event2.row, 0)
        self.assertEqual(event2.col, 0)
        self.assertFalse(event2.is_pressed)

    def test_long_press_detection(self):
        """Test long press detection."""
        self.manager.on_device_key_event(1, 1, True)
        time.sleep(0.6)  # Exceed threshold
        self.manager.on_device_key_event(1, 1, False)

        # Consume press event
        press_event = self.manager.poll_event()
        self.assertTrue(press_event.is_pressed)

        # Check release event has long_press flag
        release_event = self.manager.poll_event()
        self.assertFalse(release_event.is_pressed)
        self.assertTrue(release_event.long_press)

    def test_short_press(self):
        """Test short press does not trigger long press."""
        self.manager.on_device_key_event(2, 2, True)
        time.sleep(0.1)  # Below threshold
        self.manager.on_device_key_event(2, 2, False)

        # Consume press event
        self.manager.poll_event()

        # Check release event
        release_event = self.manager.poll_event()
        self.assertFalse(release_event.long_press)

    def test_queue_size(self):
        """Test queue size tracking."""
        self.assertEqual(self.manager.queue_size(), 0)

        self.manager.on_device_key_event(0, 0, True)
        self.assertEqual(self.manager.queue_size(), 1)

        self.manager.on_device_key_event(0, 0, False)
        self.assertEqual(self.manager.queue_size(), 2)

        self.manager.poll_event()
        self.assertEqual(self.manager.queue_size(), 1)

    def test_clear_queue(self):
        """Test queue clearing."""
        self.manager.on_device_key_event(0, 0, True)
        self.manager.on_device_key_event(0, 1, True)
        self.manager.on_device_key_event(0, 2, True)

        self.assertEqual(self.manager.queue_size(), 3)

        self.manager.clear_queue()
        self.assertEqual(self.manager.queue_size(), 0)

    def test_timeout(self):
        """Test poll timeout."""
        event = self.manager.poll_event(timeout=0.1)
        self.assertIsNone(event)


if __name__ == '__main__':
    unittest.main()
