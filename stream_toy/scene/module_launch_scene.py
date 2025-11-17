"""
Module launcher scene.

Displays all available modules and allows launching them.
"""

from typing import List, TYPE_CHECKING
import logging

from .menu_scene import MenuScene, MenuItem, ButtonAction

if TYPE_CHECKING:
    from ..runtime import StreamToyRuntime
    from ..module import StreamToyModule

logger = logging.getLogger(__name__)


try:
    from adafruit_led_animation.animation.sparkle import Sparkle
    from adafruit_led_animation.color import WHITE
    SPARKLE_AVAILABLE = True
except ImportError:
    SPARKLE_AVAILABLE = False
    logger.warning("Sparkle animation not available")


class ModuleLaunchScene(MenuScene):
    """
    Main launcher showing all available modules.

    Each module gets a button with its icon. Bottom-right is reserved
    for system functionality.
    """

    async def on_enter(self) -> None:
        """Initialize LED animation and menu."""
        # Set Sparkle LED animation for main menu
        if SPARKLE_AVAILABLE and self.state_manager.led_manager:
            try:
                sparkle = Sparkle(self.state_manager.led_manager.pixels, speed=0.5, color=WHITE, num_sparkles=1)
                self.device.set_background_led_animation(sparkle)
                logger.debug("Sparkle LED animation set for main menu")
            except Exception as e:
                logger.warning(f"Failed to set Sparkle animation: {e}")

        # Call parent to render menu
        await super().on_enter()

    def build_menu(self) -> List[MenuItem]:
        """Build launcher menu from available modules."""
        modules = self.runtime.get_available_modules()
        items = []

        logger.info(f"Building launcher with {len(modules)} modules")

        # Place modules (max 14, reserve bottom-right for system)
        for idx, module in enumerate(modules[:14]):
            row = idx // 5
            col = idx % 5

            try:
                icon_path = str(module.get_icon_path())
            except FileNotFoundError:
                logger.warning(f"Module {module.manifest.name} icon not found, using text")
                icon_path = None

            # Create menu item
            items.append(MenuItem(
                row=row,
                col=col,
                icon=icon_path,
                label=module.manifest.name[:8] if icon_path is None else None,
                action=ButtonAction(
                    on_tap=lambda m=module: self.launch_module(m)
                )
            ))

            logger.debug(f"Added module to launcher: {module.manifest.name} at ({row},{col})")

        # Bottom-right: System menu placeholder
        items.append(MenuItem(
            row=2,
            col=4,
            label="⚙",  # Settings/system
            action=ButtonAction(
                on_tap=self.show_about,
                on_long_press=self.shutdown_system
            )
        ))

        return items

    def launch_module(self, module: 'StreamToyModule') -> None:
        """
        Launch a module.

        Args:
            module: Module to launch
        """
        logger.info(f"Launching module: {module.manifest.name}")

        try:
            # Get scene class (lazy load)
            scene_class = module.main_scene_class

            # Switch to module scene
            self.switch_scene(scene_class)

        except Exception as e:
            logger.error(f"Failed to launch module {module.manifest.name}: {e}", exc_info=True)
            # TODO: Show error scene

    def show_about(self) -> None:
        """Show about/info screen."""
        logger.info("About screen requested")
        # TODO: Implement AboutScene

    def shutdown_system(self) -> None:
        """Shutdown the system."""
        logger.info("System shutdown requested")
        self.runtime.shutdown()
