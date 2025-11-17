"""
Central display state manager for StreamToy.

Maintains the single source of truth for display state (tiles and LEDs)
and propagates updates to all connected viewer devices.
"""

import threading
from pathlib import Path
from typing import Dict, Tuple, List, Optional, Union, Callable
import logging

from .led_manager import LEDManager

logger = logging.getLogger(__name__)


class DisplayStateManager:
    """
    Central state manager for display and LED state.

    Maintains the authoritative state and notifies all registered
    viewer devices when changes occur.
    """

    def __init__(self):
        """Initialize the display state manager."""
        # Tile state: (row, col) -> (image_path, cache_key)
        self._tile_state: Dict[Tuple[int, int], Tuple[Union[str, Path], str]] = {}

        # Registered viewer devices that will be notified of changes
        self._viewer_callbacks: List[Callable] = []

        # Registered viewer devices (for submit)
        self._viewer_devices: List = []

        # Thread lock for state updates
        self._lock = threading.Lock()

        # Central LED manager (single instance shared by all devices)
        self.led_manager: Optional[LEDManager] = None

        logger.info("DisplayStateManager initialized")

    def initialize_led_manager(self, pin=None, num_leds: int = 90, brightness: float = 0.5, pixel_order=None) -> None:
        """
        Initialize the central LED manager.

        Args:
            pin: GPIO pin (e.g., board.D10), None for fake mode
            num_leds: Number of LEDs in strip
            brightness: LED brightness (0.0-1.0)
            pixel_order: Pixel order (e.g., neopixel.GRB)
        """
        if self.led_manager is None:
            self.led_manager = LEDManager(pin=pin, num_leds=num_leds, brightness=brightness, pixel_order=pixel_order)
            self.led_manager.start()
            logger.info("Central LED manager initialized and started")

    def stop_led_manager(self) -> None:
        """Stop the central LED manager."""
        if self.led_manager:
            self.led_manager.stop()
            logger.info("Central LED manager stopped")

    def register_viewer(self, callback: Callable[[int, int, Union[str, Path], str], None], device=None) -> None:
        """
        Register a viewer device callback.

        The callback will be called when tiles are updated.
        Signature: callback(row: int, col: int, image_path: Union[str, Path], cache_key: str)

        Args:
            callback: Function to call when tiles are updated
            device: Optional device object (for submit_tiles calls)
        """
        with self._lock:
            self._viewer_callbacks.append(callback)
            if device is not None:
                self._viewer_devices.append(device)
            logger.info(f"Registered viewer callback, total viewers: {len(self._viewer_callbacks)}")

    def unregister_viewer(self, callback: Callable) -> None:
        """
        Unregister a viewer device callback.

        Args:
            callback: The callback to remove
        """
        with self._lock:
            if callback in self._viewer_callbacks:
                self._viewer_callbacks.remove(callback)
                logger.info(f"Unregistered viewer callback, remaining viewers: {len(self._viewer_callbacks)}")

    def set_tile(
        self,
        row: int,
        col: int,
        image_path: Union[str, Path],
        cache_key: Optional[str] = None
    ) -> None:
        """
        Update tile state and notify all viewers.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            image_path: Path to image file
            cache_key: Optional cache key for tracking
        """
        image_path = Path(image_path)
        cache_key = cache_key or ""

        with self._lock:
            # Update central state
            self._tile_state[(row, col)] = (image_path, cache_key)

            # Notify all viewers
            for callback in self._viewer_callbacks:
                try:
                    callback(row, col, image_path, cache_key)
                except Exception as e:
                    logger.error(f"Error notifying viewer: {e}", exc_info=True)

        logger.debug(f"Tile state updated and propagated: ({row},{col})")

    def submit(self) -> None:
        """
        Trigger all viewers to flush their pending updates.

        This is called after a batch of set_tile operations to tell
        devices to actually send updates to hardware/browser.
        """
        with self._lock:
            devices = self._viewer_devices.copy()

        # Call submit_tiles on all viewer devices
        for device in devices:
            try:
                device.submit_tiles()
            except Exception as e:
                logger.error(f"Error calling submit_tiles on viewer {type(device).__name__}: {e}", exc_info=True)

        logger.debug(f"Submitted tile updates to {len(devices)} viewer(s)")

    def get_tile_state(self, row: int, col: int) -> Optional[Tuple[Union[str, Path], str]]:
        """
        Get current tile state.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)

        Returns:
            Tuple of (image_path, cache_key) or None if not set
        """
        with self._lock:
            return self._tile_state.get((row, col))

    def get_all_tile_state(self) -> Dict[Tuple[int, int], Tuple[Union[str, Path], str]]:
        """
        Get all current tile state.

        Returns:
            Dictionary mapping (row, col) to (image_path, cache_key)
        """
        with self._lock:
            return self._tile_state.copy()

    def set_background_led_animation(self, animation) -> None:
        """
        Set the idle LED animation on central LED manager.

        Args:
            animation: Animation object compatible with adafruit_led_animation
        """
        if self.led_manager:
            self.led_manager.set_background_animation(animation)
            logger.debug(f"Background LED animation set: {type(animation).__name__}")

    def run_led_animation(self, animation, duration: Optional[float] = None) -> None:
        """
        Run a foreground LED animation on central LED manager.

        Args:
            animation: Animation object compatible with adafruit_led_animation
            duration: Duration in seconds (None = one cycle)
        """
        if self.led_manager:
            self.led_manager.run_animation(animation, duration)
            logger.debug(f"Foreground LED animation running: {type(animation).__name__}")
