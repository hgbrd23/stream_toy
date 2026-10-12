"""
Web-based emulator device implementation.

Provides a browser-based emulation of the StreamDock device
using Flask and Socket.IO for real-time updates.
"""

import threading
import base64
from pathlib import Path
from typing import Optional, Dict, Tuple
import logging
import time

from .stream_toy_device import StreamToyDevice
from .. import tile_cache

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

        # What the browser shows: (row, col) -> base64 PNG, resent to
        # reconnecting clients without re-encoding
        self._tile_cache: Dict[Tuple[int, int], str] = {}
        # (row, col) -> cache_key of the tile in _tile_cache, for dedup
        self._shown_keys: Dict[Tuple[int, int], str] = {}
        # Guards _tile_cache/_shown_keys: written by the display worker,
        # read by the server thread on client connect
        self._tile_cache_lock = threading.Lock()

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

            self._wait_for_server(timeout=10.0)

            # Start LED update pusher
            self._start_led_updates()

            self._initialized = True
            logger.info(f"WebDevice initialized successfully at http://{self.host}:{self.port}")

        except Exception as e:
            logger.error(f"Failed to initialize WebDevice: {e}", exc_info=True)
            raise RuntimeError(f"WebDevice initialization failed: {e}")

    def _wait_for_server(self, timeout: float) -> None:
        """
        Wait until the web server accepts connections.

        Args:
            timeout: Maximum seconds to wait

        Raises:
            RuntimeError: If the server is not reachable within the timeout
        """
        import socket

        connect_host = '127.0.0.1' if self.host == '0.0.0.0' else self.host
        deadline = time.time() + timeout

        while True:
            try:
                with socket.create_connection((connect_host, self.port), timeout=0.5):
                    return
            except OSError:
                if time.time() > deadline:
                    raise RuntimeError(
                        f"Web server did not start listening on {connect_host}:{self.port} "
                        f"within {timeout}s"
                    )
                time.sleep(0.05)

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
                if not server.has_clients():
                    # Nobody is watching, don't build or push LED frames
                    time.sleep(0.25)
                    continue

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

    def flush_tiles(self, tiles: Dict[Tuple[int, int], Tuple[Path, str]]) -> None:
        """
        Send a batch of tile updates to the browser.

        Tiles whose non-empty cache_key matches what the browser already shows
        are skipped. The PNG comes from tile_cache (already 112x112), so it is
        only read and base64-encoded. Without a connected client the cache is
        still updated so the next client gets the current screen.
        """
        from ..web import server

        sent = 0

        for (row, col), (image_path, cache_key) in tiles.items():
            with self._tile_cache_lock:
                if cache_key and self._shown_keys.get((row, col)) == cache_key:
                    continue

            try:
                png_path = tile_cache.web_png(image_path)
                img_base64 = base64.b64encode(png_path.read_bytes()).decode('ascii')
            except Exception as e:
                logger.error(f"[SUBMIT] Could not prepare tile ({row},{col}) from {image_path}: {e}",
                             exc_info=True)
                continue

            with self._tile_cache_lock:
                self._tile_cache[(row, col)] = img_base64
                self._shown_keys[(row, col)] = cache_key

            # Checked after storing: a client connecting meanwhile either gets
            # this tile from on_client_connected() or from this emit
            if server.has_clients():
                server.emit_tile_update(row, col, img_base64)
                sent += 1

        logger.debug(f"[SUBMIT] {len(tiles)} tiles flushed, {sent} sent to browser, "
                     f"cache has {len(self._tile_cache)} tiles")

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
        """Called when a client connects to the web interface: resend the current screen."""
        from ..web import server

        with self._tile_cache_lock:
            cached = list(self._tile_cache.items())

        logger.info(f"[CLIENT CONNECT] Client connected, sending {len(cached)} cached tiles")

        for (row, col), img_base64 in cached:
            server.emit_tile_update(row, col, img_base64)
