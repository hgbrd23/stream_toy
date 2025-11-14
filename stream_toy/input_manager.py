"""
Input management system for StreamToy.

Handles input event queuing, long-press detection, and thread-safe event delivery.
"""

import queue
import threading
import time
import asyncio
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class InputEvent:
    """Represents a single input event."""

    row: int
    col: int
    is_pressed: bool
    timestamp: float
    long_press: bool = False

    def __repr__(self) -> str:
        action = "long-press" if self.long_press else ("press" if self.is_pressed else "release")
        return f"InputEvent(row={self.row}, col={self.col}, action={action}, time={self.timestamp:.3f})"


class InputManager:
    """
    Manages input event queue with thread-safe operations.

    Provides both synchronous and asynchronous event polling,
    and automatic long-press detection.
    """

    def __init__(self, long_press_threshold: float = 3.0):
        """
        Initialize the input manager.

        Args:
            long_press_threshold: Duration in seconds to detect long press
        """
        self._queue: queue.Queue[InputEvent] = queue.Queue()
        self._long_press_threshold = long_press_threshold
        self._active_presses: Dict[Tuple[int, int], float] = {}
        self._lock = threading.Lock()

    def on_device_key_event(self, row: int, col: int, is_pressed: bool) -> None:
        """
        Called by device callback when a key event occurs.

        This method is thread-safe and can be called from device callback threads.

        Args:
            row: Button row (0-2)
            col: Button column (0-4)
            is_pressed: True on press, False on release
        """
        key = (row, col)
        duration = 0.0

        with self._lock:
            if is_pressed:
                # Record press start time
                self._active_presses[key] = time.time()
                logger.debug(f"Key press detected: row={row}, col={col}")
            else:
                # Calculate press duration
                if key in self._active_presses:
                    duration = time.time() - self._active_presses[key]
                    del self._active_presses[key]
                    logger.debug(f"Key release detected: row={row}, col={col}, duration={duration:.3f}s")

        # Create and queue event
        event = InputEvent(row, col, is_pressed, time.time())

        # Mark as long press if release after threshold
        if not is_pressed and duration >= self._long_press_threshold:
            event.long_press = True
            logger.info(f"Long press detected: row={row}, col={col}, duration={duration:.3f}s")

        self._queue.put(event)

    def poll_event(self, timeout: float = 0.1) -> Optional[InputEvent]:
        """
        Non-blocking poll for next event.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            InputEvent or None if timeout
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    async def async_poll_event(self, timeout: float = 10.0) -> Optional[InputEvent]:
        """
        Async version for asyncio event loops.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            InputEvent or None if timeout
        """
        loop = asyncio.get_event_loop()
        end_time = loop.time() + timeout

        while loop.time() < end_time:
            try:
                # Use a short timeout (0.1s) so executor threads don't block forever
                # This prevents orphaned threads from consuming events
                event = await loop.run_in_executor(
                    None,
                    lambda: self._queue.get(block=True, timeout=0.1)
                )
                logger.debug(f"async_poll_event got event: {event}")
                return event
            except queue.Empty:
                # No event yet, keep trying until overall timeout
                continue

        return None

    def clear_queue(self) -> None:
        """Clear all pending events from the queue."""
        with self._lock:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
            logger.debug("Event queue cleared")

    def set_long_press_threshold(self, seconds: float) -> None:
        """
        Change the long press detection threshold.

        Args:
            seconds: New threshold in seconds
        """
        with self._lock:
            self._long_press_threshold = seconds
            logger.info(f"Long press threshold set to {seconds}s")

    def get_active_presses(self) -> Dict[Tuple[int, int], float]:
        """
        Get currently active (held) button presses.

        Returns:
            Dictionary mapping (row, col) to press start time
        """
        with self._lock:
            return self._active_presses.copy()

    def queue_size(self) -> int:
        """
        Get number of pending events in queue.

        Returns:
            Number of events waiting to be processed
        """
        return self._queue.qsize()
