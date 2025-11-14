"""
Abstract base class for StreamToy devices.

Provides a unified interface for physical and emulated devices.
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional, Tuple, Dict
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class StreamToyDevice(ABC):
    """Abstract base class for all StreamToy devices."""

    # Device configuration
    SCREEN_WIDTH: int = 800
    SCREEN_HEIGHT: int = 480
    TILE_SIZE: int = 128
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
        self._tile_queue: Dict[Tuple[int, int], Image.Image] = {}
        self._initialized = False

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the device hardware/connection.

        Raises:
            RuntimeError: If device cannot be initialized
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the device and cleanup resources."""
        pass

    @abstractmethod
    def set_tile(self, row: int, col: int, image: Image.Image) -> None:
        """
        Queue a tile image update.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            image: PIL Image (will be resized to TILE_SIZE x TILE_SIZE)

        Raises:
            ValueError: If row/col out of range
        """
        pass

    @abstractmethod
    def submit(self) -> None:
        """
        Send all queued tile changes to device.

        This method should block until the device has accepted and processed
        all pending updates.
        """
        pass

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
        logger.info(f"Registering key callback: {callback}")
        self._key_callback = callback
        logger.info(f"Key callback registered successfully, _key_callback is now: {self._key_callback}")

    @abstractmethod
    def set_background_led_animation(self, animation) -> None:
        """
        Set the idle LED animation.

        Args:
            animation: Animation object compatible with adafruit_led_animation
        """
        pass

    @abstractmethod
    def run_led_animation(self, animation, duration: Optional[float] = None) -> None:
        """
        Run a foreground LED animation, pausing background.

        Args:
            animation: Animation object compatible with adafruit_led_animation
            duration: Duration in seconds (None = one cycle)
        """
        pass

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
