"""
StreamDock 293V3 hardware device implementation.

Wraps the StreamDock SDK to provide the StreamToyDevice interface.
"""
import subprocess
import threading
import time
import os
import hashlib
from pathlib import Path
from typing import Optional, Dict, Tuple, Union
from PIL import Image
import logging

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
    - Tile image updates with queueing
    - Device refresh synchronization (wait for ACK)
    - Button press event translation
    - Neopixel LED control
    """

    # Cache directory for button tiles
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "button_tiles"

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

        # Display tile manager for tracking what's currently shown
        self._display_manager = DisplayTileManager()

        # Ensure cache directory exists
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        """Initialize the StreamDock hardware."""
        try:
            # Set USB device permissions
            subprocess.run('sudo chown root:$USER /dev/bus/usb/001/00*', check=True, shell=True)

            from StreamDock.DeviceManager import DeviceManager
            from StreamDock.Devices.StreamDock293V3 import StreamDock293V3

            logger.info("Initializing StreamDock 293V3 device...")

            # Create device manager
            self.manager = DeviceManager()
            streamdocks = self.manager.enumerate()

            if not streamdocks:
                raise RuntimeError("No StreamDock devices found")

            # Use first device
            self.sdk_device = streamdocks[0]

            # Verify it's a 293V3
            if not isinstance(self.sdk_device, StreamDock293V3):
                logger.warning(f"Device is {type(self.sdk_device).__name__}, not StreamDock293V3")

            # IMPORTANT: Disable SDK's automatic read thread by replacing _setup_reader
            # We will use our own read thread that calls transport.read_() directly
            def dummy_setup_reader(*args, **kwargs):
                logger.info("SDK's _setup_reader disabled - using custom read loop")
                pass

            self.sdk_device._setup_reader = dummy_setup_reader

            # Open device - won't start SDK's read thread due to override
            self.sdk_device.transport.open(bytes(self.sdk_device.path, 'utf-8'))
            logger.info("Device opened with custom read loop")

            # Initialize device (calls wakeScreen, set_brightness, clearAllIcon, refresh)
            self.sdk_device.init()
            logger.info("Device initialized")

            # Start our custom read thread
            self._read_running = True
            self._read_thread = threading.Thread(target=self._custom_read_loop, daemon=True)
            self._read_thread.start()
            logger.info("Custom read thread started")

            # Wait for initial refresh
            time.sleep(1)

            self._initialized = True
            logger.info("StreamDock 293V3 device initialized successfully")

        except ImportError as e:
            raise RuntimeError(f"StreamDock SDK not found: {e}. Ensure PYTHONPATH includes SDK.")
        except Exception as e:
            logger.error(f"Failed to initialize device: {e}", exc_info=True)
            raise RuntimeError(f"Device initialization failed: {e}")

    def _to_native_format(self, image: Image.Image) -> Image.Image:
        """
        Convert PIL Image to native StreamDock 293V3 format.

        Follows SDK's _to_native_format logic:
        - Rotates by 180 degrees
        - Resizes to 112x112
        - Converts to RGB

        Args:
            image: Source PIL Image

        Returns:
            Processed PIL Image ready for JPEG encoding
        """
        # Key image format for StreamDock 293V3
        size = (112, 112)
        rotation = 180

        # Determine if rotation should expand canvas
        expand = True
        if image.size[1] == size[0] and image.size[0] == size[1]:
            expand = False

        # Rotate first
        if rotation:
            image = image.rotate(rotation, expand=expand)

        # Resize if needed
        if image.size != size:
            image = image.resize(size, Image.LANCZOS)

        # Convert to RGB (required for JPEG)
        image = image.convert('RGB')

        return image

    def _get_cached_native_path(self, source_path: Union[str, Path]) -> Path:
        """
        Get path for cached native JPEG file.

        Args:
            source_path: Path to source image file

        Returns:
            Path to cached native JPEG (with _native.jpg suffix)
        """
        source_path = Path(source_path)
        # Replace extension with _native.jpg
        cache_path = source_path.parent / f"{source_path.stem}_native.jpg"
        return cache_path

    def _ensure_native_cached(self, source_path: Union[str, Path]) -> Path:
        """
        Ensure a native JPEG cache exists for the source image.
        Regenerates cache if source is newer than cache.

        Args:
            source_path: Path to source image file

        Returns:
            Path to cached native JPEG file
        """
        source_path = Path(source_path)
        cache_path = self._get_cached_native_path(source_path)

        # Check if cache exists and is up-to-date
        need_regenerate = False

        if not cache_path.exists():
            logger.debug(f"Cache miss: {cache_path}")
            need_regenerate = True
        else:
            # Compare modification times
            source_mtime = source_path.stat().st_mtime
            cache_mtime = cache_path.stat().st_mtime

            if source_mtime > cache_mtime:
                logger.debug(f"Cache outdated: {cache_path}")
                need_regenerate = True
            else:
                logger.debug(f"Cache hit: {cache_path}")

        # Regenerate cache if needed
        if need_regenerate:
            logger.info(f"Generating native cache: {source_path} -> {cache_path}")

            # Load source image
            image = Image.open(source_path)

            # Convert to native format
            native_image = self._to_native_format(image)

            # Save as JPEG with high quality
            native_image.save(cache_path, format='JPEG', quality=95)

            logger.info(f"Cache generated: {cache_path}")

        return cache_path

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

                # Check for device ready ACK (bytes [3] and [4] both zero means device is ready)
                # This happens after a refresh() call completes
                if result_bytes[3] == 0 and result_bytes[4] == 0 and self._device_busy:
                    logger.debug("Device ACK received, ready for next command")
                    self._device_busy = False

                # Check for button event (key is valid and not 0xFF)
                if key != 0xFF and 1 <= key <= 15:
                    logger.info(f"RAW BUTTON EVENT DETECTED: key={key}, status={status}, result_bytes={result_bytes.hex()}")

                    # Map the raw key index through KEY_MAPPING to get logical button
                    # The SDK applies KEY_MAPPING to invert rows
                    mapped_key = KEY_MAPPING[key]

                    # Translate status (0x01 = pressed, 0x00/0x02 = released)
                    is_pressed = (status == 0x01)

                    logger.info(f"Button event: raw_key={key}, mapped={mapped_key}, pressed={is_pressed}")

                    # Convert mapped key to tile coordinates
                    if mapped_key in self.CALLBACK_BUTTON_TO_TILE:
                        row, col = self.CALLBACK_BUTTON_TO_TILE[mapped_key]
                        logger.info(f"Button -> tile: key={mapped_key} -> ({row},{col})")

                        # Call registered callback
                        callback = self._key_callback
                        logger.info(f"Calling callback: {callback}")
                        if callback is not None:
                            try:
                                logger.info(f"Invoking callback with: row={row}, col={col}, is_pressed={is_pressed}")
                                callback(row, col, is_pressed)
                                logger.info(f"Callback executed successfully: ({row},{col}) pressed={is_pressed}")
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

    def _on_sdk_key_event(self, device, key: int, state: int) -> None:
        """
        [DEPRECATED] Callback from SDK when a key event occurs.
        Not used anymore - we use _custom_read_loop instead.

        Args:
            device: SDK device object (ignored)
            key: SDK key index (1-15 AFTER KEY_MAPPING is applied by SDK)
            state: Key state (1 = pressed, 0 = released)
        """
        logger.info(f"SDK key event: key={key}, state={state}")

        # Convert SDK callback key index to tile coordinates
        if key in self.CALLBACK_BUTTON_TO_TILE:
            row, col = self.CALLBACK_BUTTON_TO_TILE[key]
            is_pressed = (state == 1)

            logger.info(f"Button event: key={key} -> ({row},{col}), pressed={is_pressed}")

            # Call registered callback (may be None during early initialization)
            callback = self._key_callback
            if callback is not None:
                try:
                    callback(row, col, is_pressed)
                    logger.info("Callback executed successfully")
                except Exception as e:
                    logger.error(f"Callback error: {e}", exc_info=True)
            else:
                logger.debug(f"Event received but no callback registered yet (normal during init)")
        else:
            logger.warning(f"Unknown button index: {key}")

    def close(self) -> None:
        """Close device and cleanup."""
        logger.info("Closing StreamDock device")

        # Stop custom read thread
        if self._read_running:
            logger.info("Stopping custom read thread...")
            self._read_running = False
            if self._read_thread and self._read_thread.is_alive():
                self._read_thread.join(timeout=2.0)
            logger.info("Custom read thread stopped")

        # Close SDK device
        if self.sdk_device:
            try:
                self.sdk_device.clearAllIcon()
                self.sdk_device.refresh()
                self.sdk_device.transport.close()
            except Exception as e:
                logger.error(f"Error closing device: {e}")

        self._initialized = False

    def set_tile(
        self,
        row: int,
        col: int,
        image_path: Union[str, Path],
        cache_key: Optional[str] = None
    ) -> None:
        """
        Queue a tile image update with optional caching.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            image_path: Path to image file (str/Path)
            cache_key: Optional cache key for tracking

        Raises:
            ValueError: If row/col out of range
            FileNotFoundError: If image_path doesn't exist
        """
        self.validate_tile_coords(row, col)

        # Convert to Path
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Queue the image path with cache_key
        self._tile_queue[(row, col)] = (image_path, cache_key or "")

    def submit_tiles(self) -> None:
        """Flush queued tile updates to device hardware."""
        if not self._tile_queue:
            logger.debug("No tiles to submit")
            return

        if not self.sdk_device:
            raise RuntimeError("Device not initialized")

        # Filter queue to only include changed tiles using DisplayTileManager
        changed_tiles = {}
        for (row, col), (image_path, cache_key) in self._tile_queue.items():
            # Check if this tile needs updating using cache key comparison
            if cache_key:
                if not self._display_manager.is_displayed(row, col, cache_key):
                    changed_tiles[(row, col)] = (image_path, cache_key)
            else:
                # No cache key - always update
                changed_tiles[(row, col)] = (image_path, cache_key)

        if not changed_tiles:
            logger.debug("No tile changes detected - skipping submit")
            self._tile_queue.clear()
            return

        logger.debug(f"Submitting {len(changed_tiles)} tile updates (skipped {len(self._tile_queue) - len(changed_tiles)} unchanged)")

        try:
            # Import ctypes for direct transport call
            import ctypes

            for (row, col), (image_path, cache_key) in changed_tiles.items():
                # Convert tile coordinates to physical button index (1-15)
                button_idx = self.TILE_TO_BUTTON.get((row, col))

                if button_idx is None:
                    logger.error(f"Failed to map tile ({row},{col}) to button index")
                    continue

                # Ensure native JPEG exists (creates cache if needed)
                native_path = self._ensure_native_cached(image_path)

                if not native_path.exists():
                    logger.error(f"Native cache file not found: {native_path}")
                    continue

                # Send native JPEG to device using SDK's transport method
                path_bytes = str(native_path).encode('utf-8')
                c_path = ctypes.c_char_p(path_bytes)

                # Get SDK's button key (maps physical button 1-15 to device protocol)
                sdk_key = self.sdk_device.key(button_idx)

                # Call transport's setKeyImgDualDevice directly
                result = self.sdk_device.transport.setKeyImgDualDevice(c_path, sdk_key)

                if result != 1:
                    logger.warning(f"Failed to set key image for button {button_idx}: result={result}")
                else:
                    logger.debug(f"Set tile ({row},{col}) -> button {button_idx}")
                    # Update display manager with cache key
                    if cache_key:
                        self._display_manager.set_displayed(row, col, cache_key)

            # Clear queue
            num_tiles = len(self._tile_queue)
            self._tile_queue.clear()

            # Refresh device (fire and forget for tile updates)
            # Note: No need to wait for ACK when updating tiles.
            # ACK is only needed for full screen background image updates.
            self.sdk_device.refresh()
            logger.debug(f"Submitted {num_tiles} tile update(s)")

        except Exception as e:
            logger.error(f"Error in submit_tiles: {e}", exc_info=True)
            raise

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
