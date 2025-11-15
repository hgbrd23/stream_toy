"""
Web-based emulator device implementation.

Provides a browser-based emulation of the StreamDock device
using Flask and Socket.IO for real-time updates.
"""

import threading
import base64
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, Tuple, Union
from PIL import Image
import logging
import time

from .stream_toy_device import StreamToyDevice
from ..led_manager import LEDManager

logger = logging.getLogger(__name__)


class WebDevice(StreamToyDevice):
    """
    Browser-based emulator for StreamDock device.

    Renders device in HTML5 canvas and handles input via WebSocket.
    """

    # Cache directory for button tiles (shared with hardware device)
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "button_tiles"

    def __init__(self, host: str = '0.0.0.0', port: int = 5000):
        """
        Initialize web device.

        Args:
            host: Host address to bind
            port: Port for web server
        """
        super().__init__()
        self.host = host
        self.port = port
        self._server_thread: Optional[threading.Thread] = None

        # Persistent tile cache for reconnecting clients
        self._tile_cache: Dict[Tuple[int, int], Image.Image] = {}

        # LED Manager in fake mode (sends to browser)
        self.led_manager = LEDManager(pin=None, num_leds=90, brightness=0.5)

        # LED update thread
        self._led_update_running = False
        self._led_update_thread: Optional[threading.Thread] = None

        # Ensure cache directory exists
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, cache_key: str) -> Path:
        """
        Get cache file path for a given cache key.

        Args:
            cache_key: Unique identifier for the cached tile

        Returns:
            Path to cached PNG file (web device uses PNG instead of JPEG)
        """
        # Sanitize cache key to make it filesystem-safe
        safe_key = "".join(c if c.isalnum() or c in "._-" else "_" for c in cache_key)
        # Web device uses PNG for simplicity
        return self.CACHE_DIR / f"{safe_key}_web.png"

    def has_cached_tile(self, cache_key: str) -> bool:
        """
        Check if a cached tile exists for the given cache key.

        Args:
            cache_key: Unique identifier for the cached tile

        Returns:
            True if cache exists, False otherwise
        """
        cache_path = self._get_cache_path(cache_key)
        exists = cache_path.exists()
        logger.debug(f"Cache check for '{cache_key}': {exists} ({cache_path})")
        return exists

    def set_tile_with_cache_key(self, row: int, col: int, image: Image.Image, cache_key: str) -> None:
        """
        Set a tile using a PIL Image and cache it with a cache key.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            image: PIL Image to display and cache
            cache_key: Unique identifier for caching this image

        Raises:
            ValueError: If row/col out of range
        """
        self.validate_tile_coords(row, col)

        # Get cache path
        cache_path = self._get_cache_path(cache_key)

        # Resize if needed
        if image.size != (self.TILE_SIZE, self.TILE_SIZE):
            image = image.resize((self.TILE_SIZE, self.TILE_SIZE), Image.LANCZOS)

        # Cache the image as PNG
        image.save(cache_path, format='PNG')
        logger.info(f"Cached tile '{cache_key}' at {cache_path}")

        # Queue the cached file for display
        self._tile_queue[(row, col)] = cache_path

    def set_tile_from_cache(self, row: int, col: int, cache_key: str) -> None:
        """
        Set a tile using a previously cached image.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            cache_key: Unique identifier for the cached tile

        Raises:
            ValueError: If row/col out of range or cache_key not found
        """
        self.validate_tile_coords(row, col)

        # Get cache path
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            raise ValueError(f"Cache key '{cache_key}' not found at {cache_path}")

        logger.debug(f"Using cached tile '{cache_key}' for ({row},{col})")

        # Queue the cached file for display
        self._tile_queue[(row, col)] = cache_path

    def initialize(self) -> None:
        """Initialize web server in background thread."""
        try:
            logger.info(f"Initializing WebDevice on {self.host}:{self.port}")

            # Import and configure server
            from ..web import server

            # Set reference to this device
            server.set_web_device(self)

            # Start server in background thread
            self._server_thread = threading.Thread(
                target=server.run_server,
                args=(self.host, self.port),
                daemon=True
            )
            self._server_thread.start()

            # Give server time to start
            time.sleep(1)

            # Start LED manager
            self.led_manager.start()

            # Start LED update pusher
            self._start_led_updates()

            # Set default LED animation
            self._set_default_led_animation()

            self._initialized = True
            logger.info(f"WebDevice initialized successfully at http://{self.host}:{self.port}")

        except Exception as e:
            logger.error(f"Failed to initialize WebDevice: {e}", exc_info=True)
            raise RuntimeError(f"WebDevice initialization failed: {e}")

    def _set_default_led_animation(self) -> None:
        """Set default rainbow background animation."""
        try:
            from adafruit_led_animation.animation.rainbow import Rainbow

            rainbow = Rainbow(self.led_manager.pixels, speed=0.05, period=5)
            self.led_manager.set_background_animation(rainbow)
            logger.debug("Default rainbow LED animation set")
        except Exception as e:
            logger.warning(f"Failed to set default LED animation: {e}")
            # Fallback: Set all LEDs to a dim cyan color
            logger.info("Using fallback: setting LEDs to dim cyan")
            self.led_manager.set_all((0, 40, 40))

    def _start_led_updates(self) -> None:
        """Start thread to push LED updates to browser."""
        self._led_update_running = True
        self._led_update_thread = threading.Thread(
            target=self._led_update_loop,
            daemon=True
        )
        self._led_update_thread.start()
        logger.debug("LED update thread started")

    def _led_update_loop(self) -> None:
        """Periodically push LED state to browser."""
        from ..web import server

        logger.info("[LED UPDATE LOOP] Starting LED update loop")

        while self._led_update_running:
            try:
                # Get current LED colors
                led_data = self.led_manager.get_pixel_data()

                # Send to browser
                server.emit_led_update(led_data)

                # Update at ~10 Hz (100ms)
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"[LED UPDATE LOOP] Error in LED update loop: {e}", exc_info=True)
                time.sleep(0.5)

        logger.info("[LED UPDATE LOOP] LED update loop stopped")

    def close(self) -> None:
        """Close web device and cleanup."""
        logger.info("Closing WebDevice")

        # Stop LED updates
        self._led_update_running = False
        if self._led_update_thread:
            self._led_update_thread.join(timeout=2)

        # Stop LED manager
        self.led_manager.stop()

        # Server thread will continue running (daemon)
        logger.info("WebDevice closed")

        self._initialized = False

    def set_tile(self, row: int, col: int, image: Union[Image.Image, str, Path]) -> None:
        """
        Queue a tile image update.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            image: PIL Image object or path to image file (str/Path)
        """
        self.validate_tile_coords(row, col)

        # Store in queue - can be either PIL Image or file path
        # We'll process it in submit()
        self._tile_queue[(row, col)] = image

    def submit(self) -> None:
        """Send all queued tile changes to browser."""
        if not self._tile_queue:
            logger.debug("No tiles to submit")
            return

        from ..web import server

        logger.info(f"[SUBMIT] Preparing to send {len(self._tile_queue)} tile updates to browser")

        for (row, col), image_or_path in self._tile_queue.items():
            # Load image if it's a file path
            if isinstance(image_or_path, (str, Path)):
                image = Image.open(image_or_path)
                logger.debug(f"[SUBMIT] Loaded image from path: {image_or_path}")
            else:
                image = image_or_path

            # Resize if needed
            if image.size != (self.TILE_SIZE, self.TILE_SIZE):
                image = image.resize((self.TILE_SIZE, self.TILE_SIZE), Image.LANCZOS)

            # Convert image to base64 PNG
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            logger.debug(f"[SUBMIT] Converted tile ({row},{col}) to base64, size={len(img_base64)} bytes")

            # Send to browser
            server.emit_tile_update(row, col, img_base64)

            # Update cache for reconnecting clients
            self._tile_cache[(row, col)] = image.copy()

        # Clear queue
        self._tile_queue.clear()

        logger.info(f"[SUBMIT] All tiles submitted successfully, cache now has {len(self._tile_cache)} tiles")

        # Small delay to simulate device behavior
        time.sleep(0.1)

    def set_background_led_animation(self, animation) -> None:
        """Set the idle LED animation."""
        logger.info(f"[LED] Setting background LED animation: {type(animation).__name__}")
        self.led_manager.set_background_animation(animation)

    def run_led_animation(self, animation, duration: Optional[float] = None) -> None:
        """Run a foreground LED animation."""
        duration_str = f"{duration}s" if duration else "one cycle"
        logger.info(f"[LED] Running foreground LED animation: {type(animation).__name__} for {duration_str}")
        self.led_manager.run_animation(animation, duration)

    def _on_button_event(self, row: int, col: int, is_pressed: bool) -> None:
        """
        Called by web server when button event received.

        Args:
            row: Button row (0-2)
            col: Button column (0-4)
            is_pressed: True on press, False on release
        """
        event_type = "PRESSED" if is_pressed else "RELEASED"
        logger.info(f"[BUTTON EVENT] Button ({row},{col}) {event_type}")

        if self._key_callback:
            logger.debug(f"[BUTTON EVENT] Invoking key callback for ({row},{col})")
            self._key_callback(row, col, is_pressed)
        else:
            logger.warning(f"[BUTTON EVENT] No key callback registered for button ({row},{col})")

    def on_client_connected(self) -> None:
        """Called when a client connects to the web interface."""
        logger.info(f"[CLIENT CONNECT] Client connected, sending current state ({len(self._tile_cache)} tiles in cache)")

        # Resend all tiles
        from ..web import server

        if len(self._tile_cache) == 0:
            logger.warning("[CLIENT CONNECT] Tile cache is empty, no tiles to send to client")
        else:
            logger.info(f"[CLIENT CONNECT] Sending {len(self._tile_cache)} cached tiles to new client")

        for (row, col), image in self._tile_cache.items():
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            server.emit_tile_update(row, col, img_base64)
            logger.debug(f"[CLIENT CONNECT] Sent cached tile ({row},{col}) to client, size={len(img_base64)} bytes")

        logger.info(f"[CLIENT CONNECT] Finished sending {len(self._tile_cache)} tiles to new client")
