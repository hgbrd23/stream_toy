"""
StreamDock 293V3 hardware device implementation.

Wraps the StreamDock SDK to provide the StreamToyDevice interface.
"""
import subprocess
import threading
import time
import os
from pathlib import Path
from typing import Optional, Dict, Tuple, Union
from PIL import Image
import logging

from .stream_toy_device import StreamToyDevice
from ..led_manager import LEDManager

logger = logging.getLogger(__name__)


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

        # LED Manager (GPIO 10)
        try:
            import board
            self.led_manager = LEDManager(pin=board.D10, num_leds=90, brightness=0.1)
        except Exception as e:
            logger.warning(f"Failed to initialize LED manager with real hardware: {e}")
            # Fall back to fake mode
            self.led_manager = LEDManager(pin=None, num_leds=90, brightness=0.1)

        # Ensure cache directory exists
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, cache_key: str) -> Path:
        """
        Get cache file path for a given cache key.

        Args:
            cache_key: Unique identifier for the cached tile

        Returns:
            Path to cached native JPEG file
        """
        # Sanitize cache key to make it filesystem-safe
        safe_key = "".join(c if c.isalnum() or c in "._-" else "_" for c in cache_key)
        return self.CACHE_DIR / f"{safe_key}_native.jpg"

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

        The image is converted to native format and cached. Future calls can use
        set_tile_from_cache() with the same cache_key to avoid reprocessing.

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

        # Convert to native format and cache
        native_image = self._to_native_format(image)
        native_image.save(cache_path, format='JPEG', quality=95)
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

            # Start LED manager
            self.led_manager.start()

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
        logger.info("Custom read loop started")

        # Import KEY_MAPPING from SDK
        from StreamDock.Devices.StreamDock import KEY_MAPPING

        while self._read_running:
            try:
                # Call transport.read_() directly - returns tuple or None
                result = self.sdk_device.transport.read_(13)

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
                        if callback is not None:
                            try:
                                callback(row, col, is_pressed)
                                logger.info(f"Callback executed: ({row},{col}) pressed={is_pressed}")
                            except Exception as e:
                                logger.error(f"Callback error: {e}", exc_info=True)
                        else:
                            logger.debug("Event received but no callback registered yet")
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

        # Stop LED manager
        self.led_manager.stop()

        # Close SDK device
        if self.sdk_device:
            try:
                self.sdk_device.clearAllIcon()
                self.sdk_device.refresh()
                self.sdk_device.transport.close()
            except Exception as e:
                logger.error(f"Error closing device: {e}")

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
        # We'll process it in submit() to leverage caching for file paths
        self._tile_queue[(row, col)] = image

    def submit(self) -> None:
        """Send all queued tile changes to device."""
        if not self._tile_queue:
            logger.debug("No tiles to submit")
            return

        if not self.sdk_device:
            raise RuntimeError("Device not initialized")

        # Filter queue to only include changed tiles
        changed_tiles = {}
        for (row, col), image_or_path in self._tile_queue.items():
            # Check if this tile is different from what's currently displayed
            current = self._current_tiles.get((row, col))

            # Compare based on type
            is_different = False
            if current is None:
                # Tile not set yet
                is_different = True
            elif isinstance(image_or_path, (str, Path)) and isinstance(current, (str, Path)):
                # Both are file paths - compare paths
                is_different = Path(image_or_path) != Path(current)
            elif isinstance(image_or_path, Image.Image) and isinstance(current, Image.Image):
                # Both are PIL Images - compare bytes (expensive but accurate)
                is_different = image_or_path.tobytes() != current.tobytes()
            else:
                # Different types - definitely different
                is_different = True

            if is_different:
                changed_tiles[(row, col)] = image_or_path

        if not changed_tiles:
            logger.debug("No tile changes detected - skipping submit")
            self._tile_queue.clear()
            return

        logger.debug(f"Submitting {len(changed_tiles)} tile updates (skipped {len(self._tile_queue) - len(changed_tiles)} unchanged)")

        # Track temporary files to clean up
        temp_files = []

        try:
            # Import ctypes for direct transport call
            import ctypes

            for (row, col), image_or_path in changed_tiles.items():
                # Convert tile coordinates to physical button index (1-15)
                button_idx = self.TILE_TO_BUTTON.get((row, col))

                if button_idx is None:
                    logger.error(f"Failed to map tile ({row},{col}) to button index")
                    continue

                # Determine native JPEG path
                native_path = None

                if isinstance(image_or_path, (str, Path)):
                    # File path provided - use cached native JPEG
                    source_path = Path(image_or_path)
                    if not source_path.exists():
                        logger.error(f"Image file not found: {source_path}")
                        continue

                    # Get or create cached native JPEG
                    native_path = self._ensure_native_cached(source_path)
                    logger.debug(f"Using cached native: {native_path}")

                elif isinstance(image_or_path, Image.Image):
                    # PIL Image provided - create temporary native JPEG
                    # Convert to native format
                    native_image = self._to_native_format(image_or_path)

                    # Create temp directory if needed
                    temp_dir = Path("/tmp/streamtoy")
                    temp_dir.mkdir(parents=True, exist_ok=True)

                    # Save to temp file
                    temp_path = temp_dir / f"tile_{row}_{col}_{time.time()}.jpg"
                    native_image.save(temp_path, format='JPEG', quality=95)
                    temp_files.append(str(temp_path))
                    native_path = temp_path
                    logger.debug(f"Created temp native: {native_path}")

                else:
                    logger.error(f"Invalid image type: {type(image_or_path)}")
                    continue

                # Send native JPEG to device using SDK's transport method
                # This bypasses SDK's set_key_image and uses the pre-processed JPEG directly
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
                    # Update current tiles tracking - store what we sent
                    self._current_tiles[(row, col)] = image_or_path

            # Clear queue
            num_tiles = len(self._tile_queue)
            self._tile_queue.clear()

            # Refresh device (fire and forget for tile updates)
            # Note: No need to wait for ACK when updating tiles.
            # ACK is only needed for full screen background image updates.
            self.sdk_device.refresh()
            logger.debug(f"Submitted {num_tiles} tile update(s)")

        finally:
            # Cleanup temp files (only PIL Image temps, not cached files)
            for temp_path in temp_files:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                        logger.debug(f"Removed temp file: {temp_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove temp file {temp_path}: {e}")

    def set_background_led_animation(self, animation) -> None:
        """Set the idle LED animation."""
        self.led_manager.set_background_animation(animation)

    def run_led_animation(self, animation, duration: Optional[float] = None) -> None:
        """Run a foreground LED animation."""
        self.led_manager.run_animation(animation, duration)
