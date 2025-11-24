"""
Settings manager for persistent system-wide configuration.

Handles reading and writing settings to /data/.settings.yml
"""

import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional
import yaml


logger = logging.getLogger(__name__)


def _get_default_settings_path() -> Path:
    """Get the default settings file path relative to project root."""
    # Get project root (parent of stream_toy directory)
    project_root = Path(__file__).parent.parent
    return project_root / "data" / ".settings.yml"


class SettingsManager:
    """Manages persistent system settings stored in YAML format."""

    # Default settings
    DEFAULT_SETTINGS = {
        'volume': 0.1,  # Default volume 10%
    }

    # Maximum allowed volume (safety limit for children's toy)
    MAX_VOLUME = 0.75

    # Maximum allowed volume on startup (safety limit for children's toy)
    MAX_STARTUP_VOLUME = 0.2

    def __init__(self, settings_file: Optional[Path] = None):
        """
        Initialize the settings manager.

        Args:
            settings_file: Path to the settings YAML file (default: {project_root}/data/.settings.yml)
        """
        self._settings_file = settings_file if settings_file else _get_default_settings_path()
        self._lock = threading.Lock()
        self._settings: Dict[str, Any] = {}
        logger.info(f"SettingsManager using path: {self._settings_file}")
        self._load_settings()

    def _load_settings(self) -> None:
        """Load settings from file, applying defaults and limits."""
        with self._lock:
            try:
                if self._settings_file.exists():
                    with open(self._settings_file, 'r') as f:
                        loaded_settings = yaml.safe_load(f) or {}
                    logger.info(f"Loaded settings from {self._settings_file}")
                else:
                    loaded_settings = {}
                    logger.info(f"No settings file found, using defaults")

                # Start with defaults and update with loaded values
                self._settings = self.DEFAULT_SETTINGS.copy()
                self._settings.update(loaded_settings)

                # Apply volume limit on startup
                if 'volume' in self._settings:
                    original_volume = self._settings['volume']
                    self._settings['volume'] = min(original_volume, self.MAX_STARTUP_VOLUME)
                    if original_volume > self.MAX_STARTUP_VOLUME:
                        logger.info(
                            f"Volume capped from {original_volume:.2f} to "
                            f"{self.MAX_STARTUP_VOLUME:.2f} for safety"
                        )

                logger.debug(f"Current settings: {self._settings}")

            except Exception as e:
                logger.error(f"Failed to load settings: {e}", exc_info=True)
                self._settings = self.DEFAULT_SETTINGS.copy()

    def _save_settings(self) -> bool:
        """
        Save current settings to file.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            self._settings_file.parent.mkdir(parents=True, exist_ok=True)

            # Write settings to YAML
            with open(self._settings_file, 'w') as f:
                yaml.dump(self._settings, f, default_flow_style=False)

            logger.debug(f"Settings saved to {self._settings_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save settings: {e}", exc_info=True)
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.

        Args:
            key: Setting key
            default: Default value if key not found

        Returns:
            Setting value or default
        """
        with self._lock:
            return self._settings.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> bool:
        """
        Set a setting value.

        Args:
            key: Setting key
            value: Setting value
            save: Whether to immediately save to disk

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            self._settings[key] = value
            logger.debug(f"Setting '{key}' = {value}")

            if save:
                return self._save_settings()
            return True

    def get_volume(self) -> float:
        """
        Get the current volume setting.

        Returns:
            Volume level (0.0 to 1.0)
        """
        return self.get('volume', self.DEFAULT_SETTINGS['volume'])

    def set_volume(self, volume: float) -> bool:
        """
        Set the volume setting and save to disk.

        Args:
            volume: Volume level (0.0 to MAX_VOLUME)

        Returns:
            True if successful, False otherwise
        """
        # Clamp volume to valid range (0.0 to MAX_VOLUME)
        volume = max(0.0, min(self.MAX_VOLUME, volume))
        return self.set('volume', volume, save=True)

    def reset_to_defaults(self) -> bool:
        """
        Reset all settings to defaults.

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            self._settings = self.DEFAULT_SETTINGS.copy()
            logger.info("Settings reset to defaults")
            return self._save_settings()
