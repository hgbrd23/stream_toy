"""
LED management system for StreamToy.

Manages Neopixel LED strip with background/foreground animations
using the adafruit_led_animation library.
"""

import threading
import time
from typing import Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class LEDManager:
    """
    Manages Neopixel LED strip with background/foreground animations.

    Supports dual animation layers:
    - Background: Runs continuously when no foreground animation active
    - Foreground: Temporary animations that pause background
    """

    def __init__(self, pin=None, num_leds: int = 90, brightness: float = 0.5, pixel_order=None):
        """
        Initialize LED manager.

        Args:
            pin: GPIO pin (e.g., board.D10), None for fake mode
            num_leds: Number of LEDs in strip
            brightness: LED brightness (0.0-1.0)
            pixel_order: Pixel order (e.g., neopixel.GRB)
        """
        self.num_leds = num_leds
        self.brightness = brightness
        self.pixels = None
        self._fake_mode = pin is None

        if not self._fake_mode:
            try:
                import board
                import neopixel

                # Use provided pin or default to GPIO 10
                actual_pin = pin or board.D10
                actual_order = pixel_order or neopixel.GRB

                self.pixels = neopixel.NeoPixel(
                    actual_pin,
                    num_leds,
                    brightness=brightness,
                    auto_write=False,
                    pixel_order=actual_order
                )
                logger.info(f"LED Manager initialized with {num_leds} LEDs on pin {actual_pin}")
            except Exception as e:
                logger.warning(f"Failed to initialize real LEDs, using fake mode: {e}")
                self._fake_mode = True

        if self._fake_mode:
            logger.info(f"LED Manager in FAKE MODE with {num_leds} virtual LEDs")
            self.pixels = FakeNeoPixel(num_leds, brightness)

        self.background_animation = None
        self.foreground_animation = None
        self.foreground_duration: Optional[float] = None
        self.foreground_start_time: Optional[float] = None

        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start LED animation thread."""
        if self._running:
            logger.warning("LED Manager already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._animation_loop, daemon=True)
        self._thread.start()
        logger.info("LED Manager animation thread started")

    def stop(self) -> None:
        """Stop LED thread and turn off LEDs."""
        if not self._running:
            return

        logger.info("Stopping LED Manager")
        self._running = False

        if self._thread:
            self._thread.join(timeout=2)

        # Turn off all LEDs
        try:
            self.pixels.fill((0, 0, 0))
            self.pixels.show()
        except Exception as e:
            logger.error(f"Error turning off LEDs: {e}")

    def set_background_animation(self, animation) -> None:
        """
        Set idle background animation.

        Args:
            animation: Animation object compatible with adafruit_led_animation
        """
        with self._lock:
            self.background_animation = animation
            logger.debug(f"Background animation set: {type(animation).__name__}")

    def run_animation(self, animation, duration: Optional[float] = None) -> None:
        """
        Run foreground animation, pausing background.

        Args:
            animation: Animation object compatible with adafruit_led_animation
            duration: Duration in seconds (None = one cycle)
        """
        with self._lock:
            self.foreground_animation = animation
            self.foreground_duration = duration
            self.foreground_start_time = time.time()
            logger.debug(f"Foreground animation started: {type(animation).__name__}, duration={duration}")

    def _animation_loop(self) -> None:
        """Main animation update loop (runs on background thread)."""
        logger.debug("LED animation loop started")

        while self._running:
            try:
                with self._lock:
                    # Check if foreground animation should stop
                    if self.foreground_animation:
                        if self.foreground_duration:
                            elapsed = time.time() - self.foreground_start_time
                            if elapsed >= self.foreground_duration:
                                logger.debug("Foreground animation duration expired")
                                self.foreground_animation = None

                        # Animate foreground
                        if self.foreground_animation:
                            self.foreground_animation.animate()
                    else:
                        # Animate background
                        if self.background_animation:
                            self.background_animation.animate()

                self.pixels.show()
                time.sleep(0.05)  # ~20 FPS

            except Exception as e:
                logger.error(f"Error in LED animation loop: {e}", exc_info=True)
                time.sleep(0.1)

        logger.debug("LED animation loop stopped")

    def set_all(self, color: Tuple[int, int, int]) -> None:
        """
        Set all LEDs to a color immediately (bypasses animations).

        Args:
            color: RGB tuple (0-255, 0-255, 0-255)
        """
        with self._lock:
            self.pixels.fill(color)
            self.pixels.show()

    def get_pixel_data(self) -> List[Tuple[int, int, int]]:
        """
        Get current pixel color data (for web emulator).

        Returns:
            List of RGB tuples
        """
        with self._lock:
            result = []
            for i in range(self.num_leds):
                pixel = self.pixels[i]
                # Handle both tuple and integer formats
                if isinstance(pixel, (tuple, list)) and len(pixel) >= 3:
                    result.append((pixel[0], pixel[1], pixel[2]))
                elif isinstance(pixel, int):
                    # Convert integer to RGB
                    result.append(((pixel >> 16) & 0xFF, (pixel >> 8) & 0xFF, pixel & 0xFF))
                else:
                    result.append((0, 0, 0))  # Default to black if format unknown
            return result


class FakeNeoPixel:
    """
    Fake NeoPixel implementation for testing without hardware.

    Mimics the neopixel.NeoPixel API but stores pixel data in memory.
    """

    def __init__(self, num_pixels: int, brightness: float = 1.0):
        """
        Initialize fake pixel strip.

        Args:
            num_pixels: Number of pixels
            brightness: Brightness (0.0-1.0)
        """
        self.n = num_pixels
        self.brightness = brightness
        self._pixels: List[Tuple[int, int, int]] = [(0, 0, 0)] * num_pixels
        self._auto_write = False

    def __len__(self) -> int:
        return self.n

    def __setitem__(self, index: int, color: Tuple[int, int, int]) -> None:
        """Set pixel color."""
        if isinstance(index, slice):
            # Handle slice assignment
            start, stop, step = index.indices(self.n)
            for i in range(start, stop, step):
                self._pixels[i] = tuple(color) if isinstance(color, (list, tuple)) else color
        else:
            self._pixels[index] = tuple(color)

        if self._auto_write:
            self.show()

    def __getitem__(self, index: int) -> Tuple[int, int, int]:
        """Get pixel color."""
        return self._pixels[index]

    def fill(self, color: Tuple[int, int, int]) -> None:
        """Fill all pixels with color."""
        for i in range(self.n):
            self._pixels[i] = tuple(color)

        if self._auto_write:
            self.show()

    def show(self) -> None:
        """Update display (no-op for fake)."""
        pass

    @property
    def auto_write(self) -> bool:
        return self._auto_write

    @auto_write.setter
    def auto_write(self, value: bool) -> None:
        self._auto_write = value
