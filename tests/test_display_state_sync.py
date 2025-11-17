"""
Test that display state is synchronized across multiple viewer devices.
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from stream_toy.display_state_manager import DisplayStateManager


class MockViewerDevice:
    """Mock device that acts as a viewer."""

    def __init__(self, name):
        self.name = name
        self.tile_updates = []  # Track tile updates
        self.submits = 0  # Track submit calls

    def _on_state_tile_update(self, row, col, image_path, cache_key):
        """Called by state manager when tiles are updated."""
        self.tile_updates.append({
            'row': row,
            'col': col,
            'image_path': str(image_path),
            'cache_key': cache_key
        })

    def submit_tiles(self):
        """Called by state manager to flush updates."""
        self.submits += 1


class TestDisplayStateSync(unittest.TestCase):
    """Test display state synchronization across multiple devices."""

    def setUp(self):
        """Set up test fixtures."""
        self.state_manager = DisplayStateManager()

        # Create two mock viewer devices (simulating web + hardware)
        self.device1 = MockViewerDevice("Device1")
        self.device2 = MockViewerDevice("Device2")

        # Register both devices as viewers
        self.state_manager.register_viewer(
            self.device1._on_state_tile_update,
            device=self.device1
        )
        self.state_manager.register_viewer(
            self.device2._on_state_tile_update,
            device=self.device2
        )

    def test_tile_update_propagates_to_all_viewers(self):
        """Test that a tile update is sent to all registered viewers."""
        # Create a temporary test image
        test_image = Path(__file__).parent / "test_data" / "test_image.png"

        # Update a tile through state manager
        self.state_manager.set_tile(0, 0, test_image, cache_key="test_key")

        # Verify both devices received the update
        self.assertEqual(len(self.device1.tile_updates), 1)
        self.assertEqual(len(self.device2.tile_updates), 1)

        # Verify update contents match
        update1 = self.device1.tile_updates[0]
        update2 = self.device2.tile_updates[0]

        self.assertEqual(update1['row'], 0)
        self.assertEqual(update1['col'], 0)
        self.assertEqual(update1['cache_key'], 'test_key')

        self.assertEqual(update2, update1)  # Both devices got identical data

    def test_submit_calls_all_viewers(self):
        """Test that submit() triggers submit_tiles() on all viewers."""
        # Initial state - no submits
        self.assertEqual(self.device1.submits, 0)
        self.assertEqual(self.device2.submits, 0)

        # Call submit on state manager
        self.state_manager.submit()

        # Verify both devices received submit call
        self.assertEqual(self.device1.submits, 1)
        self.assertEqual(self.device2.submits, 1)

    def test_multiple_tile_updates_stay_synced(self):
        """Test that multiple tile updates keep all viewers in sync."""
        test_image = Path(__file__).parent / "test_data" / "test_image.png"

        # Update multiple tiles
        updates = [
            (0, 0, "key1"),
            (0, 1, "key2"),
            (1, 0, "key3"),
            (2, 4, "key4"),
        ]

        for row, col, key in updates:
            self.state_manager.set_tile(row, col, test_image, cache_key=key)

        # Verify both devices received all updates
        self.assertEqual(len(self.device1.tile_updates), 4)
        self.assertEqual(len(self.device2.tile_updates), 4)

        # Verify updates match
        for i in range(4):
            self.assertEqual(
                self.device1.tile_updates[i],
                self.device2.tile_updates[i]
            )

    def test_get_tile_state_returns_current_state(self):
        """Test that get_tile_state returns the current tile state."""
        test_image = Path(__file__).parent / "test_data" / "test_image.png"

        # Set a tile
        self.state_manager.set_tile(1, 2, test_image, cache_key="test_state")

        # Retrieve state
        state = self.state_manager.get_tile_state(1, 2)

        self.assertIsNotNone(state)
        self.assertEqual(str(state[0]), str(test_image))
        self.assertEqual(state[1], "test_state")

    def test_led_manager_centralized(self):
        """Test that LED manager is centralized and shared."""
        # Initialize central LED manager
        self.state_manager.initialize_led_manager(pin=None, num_leds=90)

        # Verify LED manager exists and is started
        self.assertIsNotNone(self.state_manager.led_manager)
        self.assertTrue(self.state_manager.led_manager._running)

        # Test setting background animation
        mock_animation = MagicMock()
        self.state_manager.set_background_led_animation(mock_animation)

        # Verify animation was set on central manager
        self.assertEqual(
            self.state_manager.led_manager.background_animation,
            mock_animation
        )

        # Cleanup
        self.state_manager.stop_led_manager()

    def test_viewer_receives_all_tile_state_on_registration(self):
        """Test that a late-joining viewer can get all current state."""
        test_image = Path(__file__).parent / "test_data" / "test_image.png"

        # Set some tiles before registering new viewer
        self.state_manager.set_tile(0, 0, test_image, cache_key="key1")
        self.state_manager.set_tile(0, 1, test_image, cache_key="key2")

        # Get all current state
        all_state = self.state_manager.get_all_tile_state()

        # Verify state contains both tiles
        self.assertEqual(len(all_state), 2)
        self.assertIn((0, 0), all_state)
        self.assertIn((0, 1), all_state)


if __name__ == '__main__':
    unittest.main()
