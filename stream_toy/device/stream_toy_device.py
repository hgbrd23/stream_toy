"""
Abstract base class for StreamToy devices.

Provides a unified interface for physical and emulated devices.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional, Tuple, Dict, Union
import logging

logger = logging.getLogger(__name__)

# Import SoundManager - will be initialized per device
from ..sound_manager import SoundManager


class StreamToyDevice(ABC):
    """Abstract base class for all StreamToy devices."""

    # Device configuration
    SCREEN_WIDTH: int = 800
    SCREEN_HEIGHT: int = 480
    TILE_SIZE: int = 112
    TILE_COLS: int = 5
    TILE_ROWS: int = 3
    TILE_GAP_X: int = 40
    TILE_GAP_Y: int = 42
    TILE_START_X: int = 0
    TILE_START_Y: int = 4

    # LED configuration
    LED_COUNT: int = 90
    LED_SEGMENTS: Dict[str, int] = {
        'back_left': 14,
        'left': 17,
        'front': 28,
        'right': 17,
        'back_right': 14
    }

    def __init__(self):
        """Initialize the device."""
        self._key_callback: Optional[Callable[[int, int, bool], None]] = None
        self._tile_queue: Dict[Tuple[int, int], Tuple[Union[str, Path], str]] = {}  # (path, cache_key)
        self._initialized = False

        # Sound manager - shared across all devices
        self.sound_manager: Optional[SoundManager] = None

        # Central state manager reference (set by runtime)
        self.state_manager = None

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the device hardware/connection.

        Raises:
            RuntimeError: If device cannot be initialized
        """
        pass

    def initialize_sound(self, sample_rate: int = 48000, settings_manager=None) -> None:
        """
        Initialize sound manager for this device.

        Args:
            sample_rate: Audio sample rate (default: 48000 Hz)
            settings_manager: Optional SettingsManager for persistent volume
        """
        if self.sound_manager is None:
            self.sound_manager = SoundManager(sample_rate=sample_rate, settings_manager=settings_manager)
            if self.sound_manager.is_available():
                logger.info("Sound manager initialized successfully")
            else:
                logger.warning("Sound manager unavailable (audio disabled)")

    @abstractmethod
    def close(self) -> None:
        """Close the device and cleanup resources."""
        pass

    def close_sound(self) -> None:
        """Close sound manager and cleanup audio resources."""
        if self.sound_manager:
            self.sound_manager.shutdown()
            self.sound_manager = None

    def set_state_manager(self, state_manager) -> None:
        """
        Set reference to central state manager.

        Args:
            state_manager: DisplayStateManager instance
        """
        self.state_manager = state_manager

    @abstractmethod
    def submit_tiles(self) -> None:
        """
        Flush queued tile updates to the actual device hardware/browser.

        This is called by the central state manager after tile updates.
        Subclasses should implement this to send queued tiles to the device.
        """
        pass

    @abstractmethod
    def set_tile(
        self,
        row: int,
        col: int,
        image_path: Union[str, Path],
        cache_key: Optional[str] = None
    ) -> None:
        """
        Queue a tile image update.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            image_path: Path to image file (str/Path)
            cache_key: Optional cache key for tracking (used by device-level caching)

        Raises:
            ValueError: If row/col out of range
        """
        pass

    def submit(self) -> None:
        """
        Send all queued tile changes to device.

        This is a compatibility method that queues tiles locally and
        then calls submit_tiles() to flush to the device.

        DEPRECATED: Use state_manager.submit() instead to update all devices.
        """
        self.submit_tiles()

    def register_key_callback(self, callback: Callable[[int, int, bool], None]) -> None:
        """
        Register callback for key events.

        Args:
            callback: Function called with (row, col, is_pressed)
                     row: int (0-2)
                     col: int (0-4)
                     is_pressed: bool (True on press, False on release)
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"!!! REGISTERING KEY CALLBACK for device {type(self).__name__}: {callback}")
        logger.warning(f"!!! Callback function: {callback.__module__}.{callback.__name__ if hasattr(callback, '__name__') else callback}")
        self._key_callback = callback
        logger.warning(f"!!! Key callback registered successfully, _key_callback is now: {self._key_callback}")
        logger.warning(f"!!! Callback is callable: {callable(self._key_callback)}")

    def set_background_led_animation(self, animation) -> None:
        """
        Set the idle LED animation on central LED manager.

        Args:
            animation: Animation object compatible with adafruit_led_animation
        """
        if self.state_manager:
            self.state_manager.set_background_led_animation(animation)
        else:
            logger.warning("No state manager set, cannot set LED animation")

    def run_led_animation(self, animation, duration: Optional[float] = None) -> None:
        """
        Run a foreground LED animation on central LED manager.

        Args:
            animation: Animation object compatible with adafruit_led_animation
            duration: Duration in seconds (None = one cycle)
        """
        if self.state_manager:
            self.state_manager.run_led_animation(animation, duration)
        else:
            logger.warning("No state manager set, cannot run LED animation")

    def get_tile_position(self, row: int, col: int) -> Tuple[int, int]:
        """
        Calculate pixel position for a tile on the screen.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)

        Returns:
            Tuple of (x, y) pixel coordinates
        """
        x = self.TILE_START_X + col * (self.TILE_SIZE + self.TILE_GAP_X)
        y = self.TILE_START_Y + row * (self.TILE_SIZE + self.TILE_GAP_Y)
        return (x, y)

    def validate_tile_coords(self, row: int, col: int) -> None:
        """
        Validate tile coordinates.

        Args:
            row: Tile row
            col: Tile column

        Raises:
            ValueError: If coordinates are out of range
        """
        if not (0 <= row < self.TILE_ROWS):
            raise ValueError(f"Row {row} out of range (0-{self.TILE_ROWS-1})")
        if not (0 <= col < self.TILE_COLS):
            raise ValueError(f"Column {col} out of range (0-{self.TILE_COLS-1})")

    def tile_to_button_index(self, row: int, col: int) -> int:
        """
        Convert tile coordinates to linear button index.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)

        Returns:
            Button index (0-14)
        """
        return row * self.TILE_COLS + col

    def button_index_to_tile(self, index: int) -> Tuple[int, int]:
        """
        Convert linear button index to tile coordinates.

        Args:
            index: Button index (0-14)

        Returns:
            Tuple of (row, col)
        """
        row = index // self.TILE_COLS
        col = index % self.TILE_COLS
        return (row, col)
