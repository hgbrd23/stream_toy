"""
Tests for SettingsManager.

Verifies persistent settings storage and retrieval.
"""

import unittest
import tempfile
from pathlib import Path
import sys

# Add stream_toy to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from stream_toy.settings_manager import SettingsManager


class TestSettingsManager(unittest.TestCase):
    """Test cases for SettingsManager."""

    def setUp(self):
        """Create temporary settings file for each test."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False)
        self.temp_file.close()
        self.settings_path = Path(self.temp_file.name)

    def tearDown(self):
        """Clean up temporary file."""
        if self.settings_path.exists():
            self.settings_path.unlink()

    def test_default_volume(self):
        """Test that default volume is loaded when no settings file exists."""
        # Use non-existent path in temp directory
        temp_dir = Path(tempfile.mkdtemp())
        non_existent = temp_dir / "test_settings_nonexistent.yml"

        settings = SettingsManager(non_existent)
        volume = settings.get_volume()

        self.assertEqual(volume, 0.1, "Default volume should be 0.1")

        # Cleanup
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir)

    def test_save_and_load_volume(self):
        """Test that volume is saved and can be loaded (respecting startup cap)."""
        # Create settings manager and set volume to 0.18 (below cap)
        settings1 = SettingsManager(self.settings_path)
        result = settings1.set_volume(0.18)

        self.assertTrue(result, "set_volume should return True")
        self.assertEqual(settings1.get_volume(), 0.18, "Volume should be 0.18")

        # Create new settings manager to verify persistence
        settings2 = SettingsManager(self.settings_path)
        loaded_volume = settings2.get_volume()

        self.assertEqual(loaded_volume, 0.18, "Loaded volume should be 0.18")

    def test_volume_cap_on_startup(self):
        """Test that volume is capped at MAX_STARTUP_VOLUME (0.2) on startup."""
        # Create settings manager and set volume to 0.28 (above startup cap but below MAX_VOLUME)
        settings1 = SettingsManager(self.settings_path)
        settings1.set_volume(0.28)

        # Verify it was saved as 0.28
        self.assertEqual(settings1.get_volume(), 0.28, "Volume should be saved as 0.28")

        # Create new settings manager - volume should be capped at 0.2 on startup
        settings2 = SettingsManager(self.settings_path)
        loaded_volume = settings2.get_volume()

        self.assertEqual(loaded_volume, 0.2, "Volume should be capped at 0.2 on startup")

    def test_volume_below_cap_not_affected(self):
        """Test that volume below MAX_STARTUP_VOLUME is not affected."""
        # Create settings manager and set low volume
        settings1 = SettingsManager(self.settings_path)
        settings1.set_volume(0.15)

        # Create new settings manager - volume should remain 0.15
        settings2 = SettingsManager(self.settings_path)
        loaded_volume = settings2.get_volume()

        self.assertEqual(loaded_volume, 0.15, "Volume below cap should not be affected")

    def test_volume_clamping(self):
        """Test that volume is clamped to valid range (0.0-0.3)."""
        settings = SettingsManager(self.settings_path)

        # Test upper bound
        settings.set_volume(1.5)
        self.assertEqual(settings.get_volume(), 0.3, "Volume should be clamped to 0.3 (MAX_VOLUME)")

        # Test lower bound
        settings.set_volume(-0.5)
        self.assertEqual(settings.get_volume(), 0.0, "Volume should be clamped to 0.0")

    def test_generic_get_set(self):
        """Test generic get/set methods."""
        settings = SettingsManager(self.settings_path)

        # Set and get custom key
        settings.set('test_key', 'test_value')
        value = settings.get('test_key')

        self.assertEqual(value, 'test_value', "Should retrieve stored value")

        # Get with default
        default_value = settings.get('nonexistent_key', 'default')
        self.assertEqual(default_value, 'default', "Should return default for missing key")

    def test_reset_to_defaults(self):
        """Test resetting settings to defaults."""
        settings = SettingsManager(self.settings_path)

        # Change volume to 0.25 (within MAX_VOLUME of 0.3)
        settings.set_volume(0.25)
        self.assertEqual(settings.get_volume(), 0.25)

        # Reset to defaults
        result = settings.reset_to_defaults()
        self.assertTrue(result, "reset_to_defaults should return True")

        # Volume should be back to default
        self.assertEqual(settings.get_volume(), 0.1, "Volume should be reset to 0.1")


if __name__ == '__main__':
    unittest.main()
