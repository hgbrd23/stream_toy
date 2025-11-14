"""
Menu scene implementation for StreamToy.

Provides a base class for creating menu-based interfaces with
configurable button actions.
"""

from abc import abstractmethod
from typing import List, Optional, Callable, TYPE_CHECKING
from dataclasses import dataclass
import asyncio
import logging

from .base_scene import BaseScene

if TYPE_CHECKING:
    from ..runtime import StreamToyRuntime

logger = logging.getLogger(__name__)


@dataclass
class ButtonAction:
    """Defines what happens on tap or long press."""

    on_tap: Optional[Callable] = None
    on_long_press: Optional[Callable] = None


@dataclass
class MenuItem:
    """Menu item with visual and action."""

    row: int
    col: int
    label: Optional[str] = None
    icon: Optional[str] = None  # Path to image file
    action: Optional[ButtonAction] = None

    def __post_init__(self):
        if self.action is None:
            self.action = ButtonAction()


class MenuScene(BaseScene):
    """
    Abstract menu scene with configurable button actions.

    Each button can execute actions on tap or long press.
    Override build_menu() to define menu items.
    """

    def __init__(self, runtime: 'StreamToyRuntime'):
        super().__init__(runtime)
        self.items: List[MenuItem] = []

    @abstractmethod
    def build_menu(self) -> List[MenuItem]:
        """
        Override to define menu items.

        Returns:
            List of MenuItem objects defining the menu layout
        """
        pass

    async def on_enter(self) -> None:
        """Initialize menu and render items."""
        logger.info(f"Entering menu scene: {self.__class__.__name__}")

        # Build menu structure
        self.items = self.build_menu()

        # Clear all tiles first
        self.clear_all_tiles()

        # Render each menu item
        for item in self.items:
            try:
                if item.icon:
                    self.set_tile_file(item.row, item.col, item.icon)
                    logger.debug(f"Rendered icon for button ({item.row},{item.col}): {item.icon}")
                elif item.label:
                    self.set_tile_text(item.row, item.col, item.label)
                    logger.debug(f"Rendered label for button ({item.row},{item.col}): {item.label}")
            except Exception as e:
                logger.error(f"Failed to render menu item at ({item.row},{item.col}): {e}")
                # Render error indicator
                self.set_tile_text(item.row, item.col, "?", font_size=32, fg_color="red")

        # Submit all tiles
        self.submit_tiles()
        logger.debug(f"Menu rendered with {len(self.items)} items")

    async def main_loop(self) -> None:
        """Process input events and dispatch to menu items."""
        logger.info(f"[MENU LOOP] Starting main loop for {self.__class__.__name__}")

        while self._running:
            # Wait for input event
            logger.debug(f"[MENU LOOP] Waiting for event (running={self._running})")
            event = await self.input_manager.async_poll_event(timeout=1.0)

            if event is None:
                logger.debug(f"[MENU LOOP] No event received (timeout)")
                continue

            logger.info(f"[MENU LOOP] Received event: {event}")

            # Only process button releases
            if event.is_pressed:
                logger.debug(f"[MENU LOOP] Ignoring button press: ({event.row},{event.col})")
                continue

            logger.info(f"[MENU LOOP] Processing button release: ({event.row},{event.col}), long_press={event.long_press}")

            # Find matching menu item
            item = self._find_item(event.row, event.col)

            if item is None:
                logger.warning(f"[MENU LOOP] No menu item at ({event.row},{event.col})")
                continue

            logger.info(f"[MENU LOOP] Found menu item at ({event.row},{event.col})")

            # Dispatch action
            try:
                if event.long_press and item.action.on_long_press:
                    logger.info(f"[MENU LOOP] Executing long-press action for ({event.row},{event.col})")
                    await self._safe_call(item.action.on_long_press)
                elif not event.long_press and item.action.on_tap:
                    logger.info(f"[MENU LOOP] Executing tap action for ({event.row},{event.col})")
                    await self._safe_call(item.action.on_tap)
                else:
                    logger.warning(f"[MENU LOOP] No action defined for event at ({event.row},{event.col})")
            except Exception as e:
                logger.error(f"[MENU LOOP] Error executing action for ({event.row},{event.col}): {e}", exc_info=True)

    def _find_item(self, row: int, col: int) -> Optional[MenuItem]:
        """
        Find menu item at given coordinates.

        Args:
            row: Button row
            col: Button column

        Returns:
            MenuItem or None if not found
        """
        for item in self.items:
            if item.row == row and item.col == col:
                return item
        return None

    async def _safe_call(self, func: Callable) -> None:
        """
        Call function, handling both sync and async.

        Args:
            func: Function to call
        """
        if asyncio.iscoroutinefunction(func):
            await func()
        else:
            func()

    async def on_exit(self) -> None:
        """Cleanup on scene exit."""
        logger.info(f"Exiting menu scene: {self.__class__.__name__}")
