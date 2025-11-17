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

logger = logging.getLogger(__name__)


class WebDevice(StreamToyDevice):
    """
    Browser-based emulator for StreamDock device.

    Renders device in HTML5 canvas and handles input via WebSocket.
    """

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

        # Persistent tile cache for reconnecting clients (stores Images)
        self._tile_cache: Dict[Tuple[int, int], Image.Image] = {}

        # LED update thread
        self._led_update_running = False
        self._led_update_thread: Optional[threading.Thread] = None

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

            # Start LED update pusher
            self._start_led_updates()

            self._initialized = True
            logger.info(f"WebDevice initialized successfully at http://{self.host}:{self.port}")

        except Exception as e:
            logger.error(f"Failed to initialize WebDevice: {e}", exc_info=True)
            raise RuntimeError(f"WebDevice initialization failed: {e}")

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
                # Get current LED colors from central LED manager
                if self.state_manager and self.state_manager.led_manager:
                    led_data = self.state_manager.led_manager.get_pixel_data()
                    # Send to browser
                    server.emit_led_update(led_data)
                else:
                    # No central LED manager yet, send black LEDs
                    led_data = [(0, 0, 0)] * 90
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

        # Server thread will continue running (daemon)
        logger.info("WebDevice closed")

        self._initialized = False

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
            cache_key: Optional cache key (ignored by web device)

        Raises:
            ValueError: If row/col out of range
            FileNotFoundError: If image_path doesn't exist
        """
        self.validate_tile_coords(row, col)

        # Convert to Path
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Queue the image path (cache_key ignored by web device)
        self._tile_queue[(row, col)] = (image_path, cache_key or "")

    def submit_tiles(self) -> None:
        """Flush queued tile updates to browser."""
        if not self._tile_queue:
            logger.debug("No tiles to submit")
            return

        from ..web import server

        logger.info(f"[SUBMIT] Preparing to send {len(self._tile_queue)} tile updates to browser")

        for (row, col), (image_path, cache_key) in self._tile_queue.items():
            # Load image from file path
            image = Image.open(image_path)
            logger.debug(f"[SUBMIT] Loaded image from path: {image_path}")

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

    def _on_state_tile_update(self, row: int, col: int, image_path: Union[str, Path], cache_key: str) -> None:
        """
        Callback from central state manager when a tile is updated.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            image_path: Path to image file
            cache_key: Cache key for tracking
        """
        # Queue the tile update locally
        self.set_tile(row, col, image_path, cache_key)

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
