"""
StreamDock 293V3 hardware device implementation.

Wraps the StreamDock SDK to provide the StreamToyDevice interface.
"""
import subprocess
import threading
import time
import os
from typing import Optional, Dict, Tuple
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

    def _OLD_read_loop(self) -> None:
        """Background thread to process device feedback."""
        logger.info(f"Read loop started, callback registered: {self._key_callback is not None}")

        loop_count = 0
        last_log_time = time.time()

        while self._read_running:
            try:
                loop_count += 1
                current_time = time.time()

                # Log progress every 5 seconds to prove thread is alive
                if current_time - last_log_time >= 5.0:
                    logger.info(f"Read loop alive: iteration {loop_count}, callback: {self._key_callback is not None}")
                    last_log_time = current_time

                # Call read() - should be non-blocking now with auto-read enabled
                if loop_count <= 3:
                    logger.info(f"About to call sdk_device.read() (iteration {loop_count})")

                try:
                    arr = self.sdk_device.read()
                except Exception as read_err:
                    logger.error(f"Read error: {read_err}")
                    time.sleep(0.1)
                    continue

                if loop_count <= 3:
                    logger.info(f"Returned from sdk_device.read() (iteration {loop_count})")

                # Small sleep to avoid busy loop if no data
                if not arr:
                    time.sleep(0.01)
                    continue

                # Debug: log what we received
                if arr:
                    logger.info(f"Read from device: len={len(arr)}, data={list(arr[:15]) if len(arr) >= 15 else list(arr)}")

                if arr and len(arr) >= 11:
                    # Check for ACK OK response (device ready)
                    if arr[3] == 0 and arr[4] == 0:
                        if self._device_busy:
                            logger.debug("Device ACK received, ready for next command")
                            self._device_busy = False

                    # Check for button event
                    if arr[9] != 0xFF and 1 <= arr[9] <= 15:
                        button_idx = arr[9]
                        state = arr[10]

                        logger.info(f"Button event detected: idx={button_idx}, state={state}")

                        # Translate button state (0x01 = press, 0x00/0x02 = release)
                        is_pressed = (state == 0x01)

                        # Convert SDK button index to tile coordinates
                        if button_idx in self.BUTTON_TO_TILE:
                            row, col = self.BUTTON_TO_TILE[button_idx]
                            logger.info(f"Button event: idx={button_idx} -> ({row},{col}), pressed={is_pressed}")

                            # Call registered callback
                            callback = self._key_callback  # Capture current callback
                            if callback:
                                logger.info(f"Calling key callback with row={row}, col={col}, pressed={is_pressed}")
                                try:
                                    callback(row, col, is_pressed)
                                    logger.info("Callback executed successfully")
                                except Exception as cb_err:
                                    logger.error(f"Callback error: {cb_err}", exc_info=True)
                            else:
                                logger.warning("No key callback registered!")
                        else:
                            logger.warning(f"Unknown button index: {button_idx}")

                # Clean up array
                del arr

            except Exception as e:
                logger.error(f"Error in read loop: {e}", exc_info=True)
                time.sleep(0.1)

        logger.info("Read loop stopped")

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

    def set_tile(self, row: int, col: int, image: Image.Image) -> None:
        """Queue a tile image update."""
        self.validate_tile_coords(row, col)

        # Resize if needed
        if image.size != (self.TILE_SIZE, self.TILE_SIZE):
            image = image.resize((self.TILE_SIZE, self.TILE_SIZE), Image.LANCZOS)

        # Store in queue
        self._tile_queue[(row, col)] = image

    def submit(self) -> None:
        """Send all queued tile changes to device."""
        if not self._tile_queue:
            logger.debug("No tiles to submit")
            return

        if not self.sdk_device:
            raise RuntimeError("Device not initialized")

        logger.debug(f"Submitting {len(self._tile_queue)} tile updates")

        # Save images to temp files and send to device
        temp_files = []

        try:
            for (row, col), image in self._tile_queue.items():
                # Convert tile coordinates to physical button index (1-15)
                button_idx = self.TILE_TO_BUTTON.get((row, col))

                if button_idx is None:
                    logger.error(f"Failed to map tile ({row},{col}) to button index")
                    continue

                # Save to temp file
                temp_path = f"/tmp/streamtoy_tile_{row}_{col}_{time.time()}.png"
                image.save(temp_path)
                temp_files.append(temp_path)

                # Send to device
                result = self.sdk_device.set_key_image(button_idx, temp_path)
                if result != 1:
                    logger.warning(f"Failed to set key image for button {button_idx}: result={result}")

            # Clear queue
            num_tiles = len(self._tile_queue)
            self._tile_queue.clear()

            # Refresh device (fire and forget for tile updates)
            # Note: No need to wait for ACK when updating tiles.
            # ACK is only needed for full screen background image updates.
            self.sdk_device.refresh()
            logger.debug(f"Submitted {num_tiles} tile update(s)")

        finally:
            # Cleanup temp files
            for temp_path in temp_files:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temp file {temp_path}: {e}")

    def set_background_led_animation(self, animation) -> None:
        """Set the idle LED animation."""
        self.led_manager.set_background_animation(animation)

    def run_led_animation(self, animation, duration: Optional[float] = None) -> None:
        """Run a foreground LED animation."""
        self.led_manager.run_animation(animation, duration)
