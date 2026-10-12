"""
StreamDock 293V3 hardware device implementation.

Wraps the StreamDock SDK to provide the StreamToyDevice interface.
"""
import ctypes
import threading
import time
from pathlib import Path
from typing import Dict, Tuple, Union
import logging

from .. import tile_cache
from .stream_toy_device import StreamToyDevice

logger = logging.getLogger(__name__)


class DisplayTileManager:
    """
    Tracks which tiles are currently displayed on the device.

    Uses cache keys instead of image comparison to determine if a tile needs updating.
    """

    def __init__(self):
        """Initialize the manager."""
        self._displayed_tiles: Dict[Tuple[int, int], str] = {}  # (row, col) -> cache_key

    def set_displayed(self, row: int, col: int, cache_key: str) -> None:
        """
        Mark a tile as displayed with a specific cache key.

        Args:
            row: Tile row
            col: Tile column
            cache_key: Cache key of the displayed tile
        """
        self._displayed_tiles[(row, col)] = cache_key

    def is_displayed(self, row: int, col: int, cache_key: str) -> bool:
        """
        Check if a tile is already displaying the given cache key.

        Args:
            row: Tile row
            col: Tile column
            cache_key: Cache key to check

        Returns:
            True if the tile is already displaying this cache key
        """
        return self._displayed_tiles.get((row, col)) == cache_key

    def clear(self) -> None:
        """Clear all tracked tiles."""
        self._displayed_tiles.clear()


class StreamDock293V3Device(StreamToyDevice):
    """
    Hardware implementation for StreamDock 293V3 device.

    Wraps the StreamDock SDK and manages:
    - Tile image updates (deduplicated by cache key)
    - Device refresh synchronization (wait for ACK on background images)
    - Button press event translation

    All USB writes go through _transport_lock: tile flushes run on the display
    worker thread while set_background_image() may run on another thread, and
    no tile may be sent while a background refresh is still in progress.
    """

    # Physical button numbering for set_key_image (1-15, top to bottom)
    TILE_TO_BUTTON = {
        (0, 0): 1, (0, 1): 2, (0, 2): 3, (0, 3): 4, (0, 4): 5,      # top row
        (1, 0): 6, (1, 1): 7, (1, 2): 8, (1, 3): 9, (1, 4): 10,     # middle row
        (2, 0): 11, (2, 1): 12, (2, 2): 13, (2, 3): 14, (2, 4): 15, # bottom row
    }

    # SDK callback button indices to tile coordinates (AFTER KEY_MAPPING is applied)
    # SDK applies KEY_MAPPING which inverts rows before calling our callback:
    #   Physical top row (1-5) → SDK callback receives (11-15)
    #   Physical middle (6-10) → SDK callback receives (6-10)
    #   Physical bottom (11-15) → SDK callback receives (1-5)
    CALLBACK_BUTTON_TO_TILE = {
        11: (0, 0), 12: (0, 1), 13: (0, 2), 14: (0, 3), 15: (0, 4),  # top row
        6: (1, 0), 7: (1, 1), 8: (1, 2), 9: (1, 3), 10: (1, 4),      # middle row
        1: (2, 0), 2: (2, 1), 3: (2, 2), 4: (2, 3), 5: (2, 4),       # bottom row
    }

    def __init__(self):
        """Initialize the device wrapper."""
        super().__init__()
        self.sdk_device = None
        self.manager = None
        self._device_busy = False
        self._read_thread = None
        self._read_running = False

        # Serialises all USB writes (tiles, background image + its ACK wait)
        self._transport_lock = threading.Lock()

        # Display tile manager for tracking what's currently shown
        self._display_manager = DisplayTileManager()

    def initialize(self) -> None:
        """Initialize the StreamDock hardware."""
        try:
            # USB permissions come from the udev rule installed by install.sh
            from StreamDock.DeviceManager import DeviceManager
            from StreamDock.Devices.StreamDock293V3 import StreamDock293V3
            from StreamDock.ProductIDs import g_products

            logger.info("Initializing StreamDock 293V3 device...")

            # Only probe the 293V3 product ids instead of DeviceManager.enumerate(),
            # which scans every StreamDock model the SDK knows about
            self.manager = DeviceManager()
            streamdocks = []
            for vid, pid, class_type in g_products:
                if class_type is not StreamDock293V3:
                    continue
                for found in self.manager.transport.enumerate(vid=vid, pid=pid):
                    streamdocks.append(StreamDock293V3(self.manager.transport, found))

            if not streamdocks:
                raise RuntimeError("No StreamDock 293V3 devices found")

            # Use first device
            self.sdk_device = streamdocks[0]

            # IMPORTANT: Disable SDK's automatic read thread by replacing _setup_reader
            # We will use our own read thread that calls transport.read_() directly
            def dummy_setup_reader(*args, **kwargs):
                logger.info("SDK's _setup_reader disabled - using custom read loop")
                pass

            self.sdk_device._setup_reader = dummy_setup_reader

            # Open device - won't start SDK's read thread due to override
            self.sdk_device.transport.open(bytes(self.sdk_device.path, 'utf-8'))
            logger.info("Device opened with custom read loop")

            # Initialize device (calls wakeScreen, set_brightness, clearAllIcon, refresh).
            # Reading from the transport during init() crashes the SDK's native code,
            # so the read thread must only start afterwards.
            self._device_busy = True
            self.sdk_device.init()
            logger.info("Device initialized")

            # Start our custom read thread
            self._read_running = True
            self._read_thread = threading.Thread(target=self._custom_read_loop, daemon=True)
            self._read_thread.start()
            logger.info("Custom read thread started")

            # Wait for the init refresh to complete; the ACK may have arrived before the
            # read thread started (or never come), so a timeout here is not an error
            if not self._wait_for_ack(timeout=1.0):
                logger.debug("No ACK for initial refresh within 1s, continuing")

            self._initialized = True
            logger.info("StreamDock 293V3 device initialized successfully")

        except ImportError as e:
            raise RuntimeError(f"StreamDock SDK not found: {e}. Ensure PYTHONPATH includes SDK.")
        except Exception as e:
            logger.error(f"Failed to initialize device: {e}", exc_info=True)
            raise RuntimeError(f"Device initialization failed: {e}")

    def _wait_for_ack(self, timeout: float) -> bool:
        """
        Wait until the device ACKs the last refresh (clears the busy flag).

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if ACK received, False on timeout (busy flag is reset)
        """
        start_time = time.time()

        while self._device_busy:
            if time.time() - start_time > timeout:
                self._device_busy = False
                logger.debug(f"ACK wait timed out after {time.time() - start_time:.3f}s")
                return False
            time.sleep(0.01)  # 10ms poll interval

        logger.debug(f"ACK wait took {time.time() - start_time:.3f}s")
        return True

    @staticmethod
    def _is_ready_ack(result_bytes: bytes, key: int) -> bool:
        """
        True if a read report is the device-ready ACK sent after a refresh.

        The ready ACK is ``ACK\\0\\0OK`` followed by zeros. Button events carry
        the same prefix, so they are told apart by the key in byte 9 (1..15).
        """
        return result_bytes[3] == 0 and result_bytes[4] == 0 and not (1 <= key <= 15)

    def _custom_read_loop(self) -> None:
        """
        Custom read loop that directly calls transport.read_() to get key events.
        This bypasses the SDK's broken read thread.
        """
        logger.info("Custom read loop started - thread is RUNNING")
        logger.info(f"Initial callback state: {self._key_callback}")

        # Import KEY_MAPPING from SDK
        from StreamDock.Devices.StreamDock import KEY_MAPPING

        loop_count = 0
        while self._read_running:
            loop_count += 1
            if loop_count % 1000 == 0:
                logger.debug(f"Read loop alive - iteration {loop_count}, callback={self._key_callback is not None}")
            try:
                # Call transport.read_() directly - returns tuple or None
                try:
                    result = self.sdk_device.transport.read_(13)
                except Exception as read_error:
                    logger.error(f"Error calling transport.read_(): {read_error}", exc_info=True)
                    time.sleep(0.1)
                    continue

                if result is None:
                    time.sleep(0.005)  # Small delay (5ms) to avoid busy loop
                    continue

                # result is a tuple: (bytes, ack_str, ok_str, key, status)
                result_bytes, ack_response, ok_response, key, status = result

                # Device ready ACK after a refresh() completes. Button events have
                # the same prefix; treating them as ACK would end a background
                # refresh wait early and let tiles through mid-refresh.
                if self._device_busy and self._is_ready_ack(result_bytes, key):
                    logger.debug("Device ACK received, ready for next command")
                    self._device_busy = False

                # Check for button event (key is valid and not 0xFF)
                if key != 0xFF and 1 <= key <= 15:
                    logger.debug(f"RAW BUTTON EVENT DETECTED: key={key}, status={status}, result_bytes={result_bytes.hex()}")

                    # Map the raw key index through KEY_MAPPING to get logical button
                    # The SDK applies KEY_MAPPING to invert rows
                    mapped_key = KEY_MAPPING[key]

                    # Translate status (0x01 = pressed, 0x00/0x02 = released)
                    is_pressed = (status == 0x01)

                    logger.debug(f"Button event: raw_key={key}, mapped={mapped_key}, pressed={is_pressed}")

                    # Convert mapped key to tile coordinates
                    if mapped_key in self.CALLBACK_BUTTON_TO_TILE:
                        row, col = self.CALLBACK_BUTTON_TO_TILE[mapped_key]
                        logger.debug(f"Button -> tile: key={mapped_key} -> ({row},{col})")

                        # Call registered callback
                        callback = self._key_callback
                        logger.debug(f"Calling callback: {callback}")
                        if callback is not None:
                            try:
                                logger.debug(f"Invoking callback with: row={row}, col={col}, is_pressed={is_pressed}")
                                callback(row, col, is_pressed)
                                logger.debug(f"Callback executed successfully: ({row},{col}) pressed={is_pressed}")
                            except Exception as e:
                                logger.error(f"Callback error: {e}", exc_info=True)
                        else:
                            logger.warning(f"Event received but no callback registered yet! Button ({row},{col})")
                    else:
                        logger.warning(f"Unknown mapped button index: {mapped_key}")

                # Don't sleep here - immediately poll for next event to minimize latency

            except Exception as e:
                logger.error(f"Error in custom read loop: {e}", exc_info=True)
                time.sleep(0.1)

        logger.info("Custom read loop stopped")

    def close(self) -> None:
        """Close device and cleanup."""
        logger.info("Closing StreamDock device")

        # Signal read thread to stop
        self._read_running = False
        logger.info("Signaled read thread to stop")

        # Wait briefly for read thread to notice the signal
        # Note: Thread may be blocked in transport.read_(), so it might not
        # exit immediately. We give it a chance but don't force it.
        if self._read_thread and self._read_thread.is_alive():
            logger.info("Waiting for read thread to stop...")
            self._read_thread.join(timeout=1.0)

            if self._read_thread.is_alive():
                logger.info("Read thread still running (normal - blocked in USB read)")
            else:
                logger.info("Read thread stopped")

        # DO NOT close the transport explicitly
        # The read thread may still be blocked in transport.read_(), and closing
        # the transport while a USB read is in progress causes libusb mutex
        # deadlocks (SIGABRT). Let the OS clean up USB resources on process exit.
        logger.info("Skipping transport close (OS will clean up USB resources)")

        self._initialized = False
        logger.info("StreamDock device closed")

    def set_background_image(self, image_path: Union[str, Path], wait_for_ack: bool = True, timeout: float = 5.0) -> bool:
        """
        Set full screen background image (800x480).

        Full screen images take 500ms to 3+ seconds to update and require ACK
        waiting. The transport lock is held through the ACK wait so no tiles
        are sent while the device is still refreshing.

        Args:
            image_path: Path to background image file
            wait_for_ack: Whether to wait for device ACK (default: True)
            timeout: Maximum seconds to wait for ACK (default: 5.0)

        Returns:
            True if successful, False otherwise
        """
        if not self.sdk_device:
            logger.error("Device not initialized")
            return False

        image_path = Path(image_path)
        if not image_path.exists():
            logger.error(f"Background image not found: {image_path}")
            return False

        try:
            # Cached rotated JPEG; avoids the SDK's per-call decode/encode/temp file
            native_path = tile_cache.native_background_jpeg(image_path)
        except Exception as e:
            logger.error(f"Error converting background image: {e}", exc_info=True)
            return False

        with self._transport_lock:
            try:
                logger.info(f"Setting background image: {image_path}")

                # Set device busy flag before sending image
                if wait_for_ack:
                    self._device_busy = True

                c_path = ctypes.c_char_p(str(native_path).encode('utf-8'))
                result = self.sdk_device.transport.setBackgroundImgDualDevice(c_path)

                if result != 1:
                    logger.warning(f"Failed to set background image: result={result}")
                    self._device_busy = False
                    return False

                # Trigger refresh
                self.sdk_device.refresh()
                logger.debug("Background image set, refresh triggered")

                # The background overwrites the key areas: every tile has to
                # be sent again even if its cache key was displayed before
                self._display_manager.clear()

                # Wait for ACK if requested
                if wait_for_ack:
                    logger.info(f"Waiting for device ACK (timeout: {timeout}s)...")
                    start_time = time.time()

                    if not self._wait_for_ack(timeout):
                        logger.error(f"Timeout waiting for device ACK after {timeout}s")
                        return False

                    elapsed = time.time() - start_time
                    logger.info(f"Device ACK received after {elapsed:.2f}s")

                return True

            except Exception as e:
                logger.error(f"Error setting background image: {e}", exc_info=True)
                self._device_busy = False
                return False

    def flush_tiles(self, tiles: Dict[Tuple[int, int], Tuple[Path, str]]) -> None:
        """
        Send changed tiles to the device and refresh once.

        Tiles whose cache key is already displayed are skipped; tiles without
        a cache key are always sent. No ACK wait: key tiles are handled
        asynchronously by the device (see CLAUDE.md).
        """
        if not self.sdk_device:
            raise RuntimeError("Device not initialized")

        # Filter to changed tiles and resolve their native JPEGs before taking
        # the transport lock; generating a cache file can take a while.
        changed_tiles = []
        for (row, col), (image_path, cache_key) in tiles.items():
            if cache_key and self._display_manager.is_displayed(row, col, cache_key):
                continue

            button_idx = self.TILE_TO_BUTTON.get((row, col))
            if button_idx is None:
                logger.error(f"Failed to map tile ({row},{col}) to button index")
                continue

            try:
                native_path = tile_cache.native_key_jpeg(image_path)
            except Exception as e:
                logger.error(f"Cannot convert tile ({row},{col}) {image_path}: {e}")
                continue
            changed_tiles.append((row, col, button_idx, native_path, cache_key))

        if not changed_tiles:
            logger.debug("No tile changes detected - skipping submit")
            return

        logger.debug(f"Submitting {len(changed_tiles)} tile updates (skipped {len(tiles) - len(changed_tiles)})")

        with self._transport_lock:
            for row, col, button_idx, native_path, cache_key in changed_tiles:
                c_path = ctypes.c_char_p(str(native_path).encode('utf-8'))
                sdk_key = self.sdk_device.key(button_idx)
                result = self.sdk_device.transport.setKeyImgDualDevice(c_path, sdk_key)

                if result != 1:
                    logger.warning(f"Failed to set key image for button {button_idx}: result={result}")
                else:
                    logger.debug(f"Set tile ({row},{col}) -> button {button_idx}")
                    if cache_key:
                        self._display_manager.set_displayed(row, col, cache_key)

            # Refresh device once after all tiles
            self.sdk_device.refresh()
