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

        # Display worker: flushes device queues off the asyncio loop so USB
        # and image I/O never block input handling or audio. submit() only
        # signals; several submits before the worker wakes up collapse into
        # one flush (devices drain their whole queue at once).
        self._submit_requested = threading.Event()
        self._idle = threading.Event()
        self._idle.set()
        self._worker_running = False
        self._worker: Optional[threading.Thread] = None

        # Central LED manager (single instance shared by all devices)
        self.led_manager: Optional[LEDManager] = None

        logger.info("DisplayStateManager initialized")

    def initialize_led_manager(self, pin=None, num_leds: int = 90, brightness: float = 0.2, pixel_order=None) -> None:
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

        Called after a batch of set_tile operations. Returns immediately; the
        display worker thread performs the flush. Use wait_idle() when the
        caller has to know the tiles reached the devices (tests, shutdown).
        """
        self._idle.clear()
        self._submit_requested.set()
        if not self._worker_running:
            self._start_worker()

    def wait_idle(self, timeout: Optional[float] = None) -> bool:
        """Block until all requested flushes are done. Returns False on timeout."""
        return self._idle.wait(timeout)

    def _start_worker(self) -> None:
        with self._lock:
            if self._worker_running:
                return
            self._worker_running = True
            self._worker = threading.Thread(target=self._worker_loop, name="display-worker", daemon=True)
            self._worker.start()
        logger.info("Display worker thread started")

    def _worker_loop(self) -> None:
        while self._worker_running:
            if not self._submit_requested.wait(timeout=0.5):
                continue
            if not self._worker_running:
                break  # woken by shutdown()
            self._submit_requested.clear()
            self._flush_all()
            # Requests that arrived during the flush keep the event set and
            # are handled by the next iteration before we report idle.
            if not self._submit_requested.is_set():
                self._idle.set()

    def _flush_all(self) -> None:
        with self._lock:
            devices = self._viewer_devices.copy()

        for device in devices:
            try:
                device.submit_tiles()
            except Exception as e:
                logger.error(f"Error calling submit_tiles on viewer {type(device).__name__}: {e}", exc_info=True)

        logger.debug(f"Submitted tile updates to {len(devices)} viewer(s)")

    def shutdown(self) -> None:
        """Flush pending tiles and stop the display worker and LED manager."""
        if self._worker_running:
            self.wait_idle(timeout=5.0)
            self._worker_running = False
            self._submit_requested.set()  # wake the worker so it can exit
            if self._worker:
                self._worker.join(timeout=2.0)
            logger.info("Display worker thread stopped")
        self.stop_led_manager()

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
