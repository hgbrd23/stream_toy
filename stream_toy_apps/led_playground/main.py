"""
LED Playground - Interactive LED effects playground

Allows users to experiment with different LED animations and parameters.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Tuple

from stream_toy.scene.base_scene import BaseScene
from stream_toy.scene.module_launch_scene import ModuleLaunchScene

logger = logging.getLogger(__name__)


class LEDPlaygroundScene(BaseScene):
    """Interactive LED effects playground."""

    # Available effects with their display names and parameter info
    EFFECTS = [
        {"name": "Solid", "module": "solid", "class": "Solid", "params": ["color"]},
        {"name": "Blink", "module": "blink", "class": "Blink", "params": ["speed", "color"]},
        {"name": "Pulse", "module": "pulse", "class": "Pulse", "params": ["speed", "color", "period"]},
        {"name": "Sparkle", "module": "sparkle", "class": "Sparkle", "params": ["speed", "color", "num_sparkles"]},
        {"name": "Chase", "module": "chase", "class": "Chase", "params": ["speed", "color", "size"]},
        {"name": "Comet", "module": "comet", "class": "Comet", "params": ["speed", "color", "tail_length"]},
        {"name": "Rainbow", "module": "rainbow", "class": "Rainbow", "params": ["speed", "period"]},
        {"name": "R.Chase", "module": "rainbowchase", "class": "RainbowChase", "params": ["speed", "size"]},
        {"name": "R.Comet", "module": "rainbowcomet", "class": "RainbowComet", "params": ["speed", "tail_length"]},
    ]

    # Predefined colors
    COLORS = [
        {"name": "White", "value": (255, 255, 255)},
        {"name": "Red", "value": (255, 0, 0)},
        {"name": "Green", "value": (0, 255, 0)},
        {"name": "Blue", "value": (0, 0, 255)},
        {"name": "Yellow", "value": (255, 255, 0)},
        {"name": "Cyan", "value": (0, 255, 255)},
        {"name": "Magenta", "value": (255, 0, 255)},
        {"name": "Orange", "value": (255, 128, 0)},
        {"name": "Purple", "value": (128, 0, 255)},
    ]

    # Speed presets (lower = faster)
    SPEEDS = [
        {"name": "Slow", "value": 0.5},
        {"name": "Medium", "value": 0.1},
        {"name": "Fast", "value": 0.05},
        {"name": "V.Fast", "value": 0.01},
    ]

    # Brightness levels (max 50% to avoid power supply instability)
    # Actual values: 5%, 10%, 25%, 50% - labeled as 10%, 20%, 50%, 100% for user-friendliness
    BRIGHTNESS_LEVELS = [0.05, 0.10, 0.25, 0.50]
    BRIGHTNESS_LABELS = ["10%", "20%", "50%", "100%"]

    def __init__(self, runtime):
        super().__init__(runtime)
        self.current_page = "effect"  # effect, color, speed, params
        self.selected_effect_idx = 0
        self.selected_color_idx = 0
        self.selected_speed_idx = 1  # Medium by default
        self.brightness_idx = 1  # 0.10 (labeled as 20%) by default
        self.effect_params: Dict[str, Any] = {}
        self.current_animation = None

    async def on_enter(self) -> None:
        """Initialize LED playground."""
        logger.info("Starting LED Playground")

        # Set initial effect parameters
        self._reset_effect_params()

        # Render initial UI
        await self._render_ui()

        # Start initial effect
        await self._apply_effect()

        logger.info("LED Playground initialized")

    def _reset_effect_params(self) -> None:
        """Reset effect parameters to defaults."""
        self.effect_params = {
            "num_sparkles": 3,
            "size": 3,
            "tail_length": 7,
            "period": 2,
        }

    async def _render_ui(self) -> None:
        """Render current UI based on page."""
        if self.current_page == "effect":
            await self._render_effect_page()
        elif self.current_page == "color":
            await self._render_color_page()
        elif self.current_page == "speed":
            await self._render_speed_page()
        elif self.current_page == "params":
            await self._render_params_page()

    async def _render_effect_page(self) -> None:
        """Render effect selection page."""
        self.clear_all_tiles(color="black")

        # Show effects in rows 0-1 (5 effects per row)
        for idx, effect in enumerate(self.EFFECTS[:9]):
            if idx < 5:
                row = 0
                col = idx
            else:
                row = 1
                col = idx - 5

            if idx == self.selected_effect_idx:
                bg = "blue"
                fg = "yellow"
            else:
                bg = "darkblue"
                fg = "white"

            self.set_tile_text(row, col, effect["name"], font_size=16,
                             fg_color=fg, bg_color=bg)

        # Page label and navigation at bottom
        self.set_tile_text(2, 0, "Effect", font_size=14, fg_color="cyan")
        self.set_tile_text(2, 3, "→", font_size=32, fg_color="green")  # Next page
        self.set_tile_text(2, 4, "←", font_size=32, fg_color="yellow")  # Back

        self.submit_tiles()

    async def _render_color_page(self) -> None:
        """Render color selection page."""
        self.clear_all_tiles(color="black")

        # Show colors in rows 0-1 (5 colors per row)
        for idx, color_info in enumerate(self.COLORS[:9]):
            if idx < 5:
                row = 0
                col = idx
            else:
                row = 1
                col = idx - 5

            if idx == self.selected_color_idx:
                # Show color with frame and name
                self._render_color_tile_with_frame(row, col, color_info["value"], color_info["name"])
            else:
                # Show color as background
                self.set_tile_text(row, col, "", bg_color=color_info["value"])

        # Page label and navigation at bottom
        self.set_tile_text(2, 0, "Color", font_size=14, fg_color="cyan")
        self.set_tile_text(2, 2, "←", font_size=32, fg_color="green")  # Prev page
        self.set_tile_text(2, 3, "→", font_size=32, fg_color="green")  # Next page
        self.set_tile_text(2, 4, "←", font_size=32, fg_color="yellow")  # Back

        self.submit_tiles()

    def _render_color_tile_with_frame(self, row: int, col: int, color: tuple, name: str) -> None:
        """Render a color tile with a white frame and color name."""
        from PIL import Image, ImageDraw

        # Create image with the color as background
        img = Image.new('RGB', (self.device.TILE_SIZE, self.device.TILE_SIZE), color)
        draw = ImageDraw.Draw(img)

        # Draw white frame
        frame_width = 4
        # Outer rectangle (white)
        draw.rectangle([0, 0, self.device.TILE_SIZE - 1, self.device.TILE_SIZE - 1],
                      outline=(255, 255, 255), width=frame_width)

        # Add color name at bottom with semi-transparent background
        font = self._get_font(14)
        text = name
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Semi-transparent black background for text
        text_bg_height = text_height + 8
        for y in range(self.device.TILE_SIZE - text_bg_height, self.device.TILE_SIZE):
            for x in range(self.device.TILE_SIZE):
                r, g, b = img.getpixel((x, y))
                # Darken by blending with black (70% opacity)
                img.putpixel((x, y), (int(r * 0.3), int(g * 0.3), int(b * 0.3)))

        # Draw text
        text_x = (self.device.TILE_SIZE - text_width) // 2
        text_y = self.device.TILE_SIZE - text_height - 4
        draw.text((text_x, text_y), text, fill=(255, 255, 255), font=font)

        # Set the tile
        self.set_tile_image(row, col, img)

    async def _render_speed_page(self) -> None:
        """Render speed and brightness control page."""
        self.clear_all_tiles(color="black")

        # Row 0: Speed label + 4 speed options
        self.set_tile_text(0, 0, "Speed", font_size=14, fg_color="cyan")
        for idx, speed in enumerate(self.SPEEDS):
            col = idx + 1

            if idx == self.selected_speed_idx:
                bg = "blue"
                fg = "yellow"
            else:
                bg = "darkblue"
                fg = "white"

            self.set_tile_text(0, col, speed["name"], font_size=16,
                             fg_color=fg, bg_color=bg)

        # Row 1: Brightness label + 4 brightness levels
        self.set_tile_text(1, 0, "Bright", font_size=14, fg_color="cyan")
        for idx in range(len(self.BRIGHTNESS_LEVELS)):
            col = idx + 1

            if idx == self.brightness_idx:
                bg = "orange"
                fg = "black"
            else:
                bg = "gray"
                fg = "white"

            self.set_tile_text(1, col, self.BRIGHTNESS_LABELS[idx], font_size=14,
                             fg_color=fg, bg_color=bg)

        # Row 2: Page label + navigation
        self.set_tile_text(2, 0, "S&B", font_size=14, fg_color="cyan")
        self.set_tile_text(2, 2, "←", font_size=32, fg_color="green")  # Prev page
        self.set_tile_text(2, 3, "→", font_size=32, fg_color="green")  # Next page (params)
        self.set_tile_text(2, 4, "←", font_size=32, fg_color="yellow")  # Back

        self.submit_tiles()

    async def _render_params_page(self) -> None:
        """Render effect parameters page."""
        self.clear_all_tiles(color="black")

        effect = self.EFFECTS[self.selected_effect_idx]

        # Show adjustable parameters - each in its own row
        param_row = 0

        if "num_sparkles" in effect["params"]:
            self.set_tile_text(param_row, 0, "Sprkl", font_size=14, fg_color="white")
            self.set_tile_text(param_row, 1, "-", font_size=24, fg_color="red", bg_color="darkred")
            self.set_tile_text(param_row, 2, str(self.effect_params["num_sparkles"]),
                             font_size=20, fg_color="yellow")
            self.set_tile_text(param_row, 3, "+", font_size=24, fg_color="green", bg_color="darkgreen")
            param_row += 1

        if "size" in effect["params"]:
            self.set_tile_text(param_row, 0, "Size", font_size=14, fg_color="white")
            self.set_tile_text(param_row, 1, "-", font_size=24, fg_color="red", bg_color="darkred")
            self.set_tile_text(param_row, 2, str(self.effect_params["size"]),
                             font_size=20, fg_color="yellow")
            self.set_tile_text(param_row, 3, "+", font_size=24, fg_color="green", bg_color="darkgreen")
            param_row += 1

        if "tail_length" in effect["params"]:
            self.set_tile_text(param_row, 0, "Tail", font_size=14, fg_color="white")
            self.set_tile_text(param_row, 1, "-", font_size=24, fg_color="red", bg_color="darkred")
            self.set_tile_text(param_row, 2, str(self.effect_params["tail_length"]),
                             font_size=20, fg_color="yellow")
            self.set_tile_text(param_row, 3, "+", font_size=24, fg_color="green", bg_color="darkgreen")
            param_row += 1

        if "period" in effect["params"]:
            # If we're at row 2, shift columns to avoid back button
            if param_row < 2:
                col_offset = 0
            else:
                col_offset = 0  # Keep at col 0, navigation will be at col 2-4

            self.set_tile_text(param_row, col_offset, "Period", font_size=14, fg_color="white")
            self.set_tile_text(param_row, col_offset + 1, "-", font_size=24, fg_color="red", bg_color="darkred")
            # Only show value and + if not at row 2 col 3-4 (navigation area)
            if param_row < 2:
                self.set_tile_text(param_row, col_offset + 2, str(self.effect_params["period"]),
                                 font_size=20, fg_color="yellow")
                self.set_tile_text(param_row, col_offset + 3, "+", font_size=24, fg_color="green", bg_color="darkgreen")

        # Page label and navigation at bottom
        self.set_tile_text(2, 0, "Params", font_size=14, fg_color="cyan")
        self.set_tile_text(2, 2, "←", font_size=32, fg_color="green")  # Prev page (speed)
        self.set_tile_text(2, 4, "←", font_size=32, fg_color="yellow")  # Back

        self.submit_tiles()

    async def _apply_effect(self) -> None:
        """Apply currently selected effect with current settings."""
        if not self.state_manager.led_manager:
            logger.warning("No LED manager available")
            return

        effect = self.EFFECTS[self.selected_effect_idx]
        color = self.COLORS[self.selected_color_idx]["value"]
        speed = self.SPEEDS[self.selected_speed_idx]["value"]
        brightness = self.BRIGHTNESS_LEVELS[self.brightness_idx]

        # Update LED manager brightness
        self.state_manager.led_manager.pixels.brightness = brightness

        try:
            # Import the animation class
            module_name = f"adafruit_led_animation.animation.{effect['module']}"
            class_name = effect["class"]

            animation_module = __import__(module_name, fromlist=[class_name])
            animation_class = getattr(animation_module, class_name)

            # Build kwargs based on effect parameters
            kwargs = {}

            if "speed" in effect["params"]:
                kwargs["speed"] = speed

            if "color" in effect["params"]:
                # Convert RGB tuple to integer color format (0xRRGGBB)
                # Some animations work better with integer format
                r, g, b = color
                color_int = (r << 16) | (g << 8) | b
                kwargs["color"] = color_int

            if "num_sparkles" in effect["params"]:
                kwargs["num_sparkles"] = self.effect_params["num_sparkles"]

            if "size" in effect["params"]:
                kwargs["size"] = self.effect_params["size"]

            if "tail_length" in effect["params"]:
                kwargs["tail_length"] = self.effect_params["tail_length"]

            if "period" in effect["params"]:
                kwargs["period"] = self.effect_params["period"]

            # Create animation
            animation = animation_class(self.state_manager.led_manager.pixels, **kwargs)

            # Set as background animation
            self.device.set_background_led_animation(animation)

            # Log effect application
            if "color" in effect["params"]:
                logger.info(f"Applied effect: {effect['name']} with color={color} (0x{color_int:06X}), params: {kwargs}")
            else:
                logger.info(f"Applied effect: {effect['name']}, params: {kwargs}")

        except Exception as e:
            logger.error(f"Failed to apply effect {effect['name']}: {e}", exc_info=True)

    async def main_loop(self) -> None:
        """Main game loop."""
        logger.debug("LED Playground main loop started")

        while self._running:
            event = await self.input_manager.async_poll_event(timeout=1.0)

            if event is None:
                continue

            # Handle long press on release events
            if not event.is_pressed and event.long_press:
                if event.row == 2 and event.col == 4:
                    logger.info("Exit requested (long press)")
                    self.switch_scene(ModuleLaunchScene)
                    return
                continue

            # Skip other release events
            if not event.is_pressed:
                continue

            # Handle button press based on current page
            await self._handle_button_press(event.row, event.col)

    async def _handle_button_press(self, row: int, col: int) -> None:
        """Handle button press based on current page."""

        # Back button (short press)
        if row == 2 and col == 4:
            logger.info("Exit requested")
            self.switch_scene(ModuleLaunchScene)
            return

        if self.current_page == "effect":
            await self._handle_effect_page_press(row, col)
        elif self.current_page == "color":
            await self._handle_color_page_press(row, col)
        elif self.current_page == "speed":
            await self._handle_speed_page_press(row, col)
        elif self.current_page == "params":
            await self._handle_params_page_press(row, col)

    async def _handle_effect_page_press(self, row: int, col: int) -> None:
        """Handle button press on effect page."""
        # Next page button
        if row == 2 and col == 3:
            self.current_page = "color"
            await self._render_ui()
            return

        # Effect selection (rows 0-1, 5 per row)
        if row == 0 and col <= 4:
            idx = col
            if idx < len(self.EFFECTS):
                self.selected_effect_idx = idx
                await self._render_ui()
                await self._apply_effect()
        elif row == 1 and col <= 3:
            idx = 5 + col
            if idx < len(self.EFFECTS):
                self.selected_effect_idx = idx
                await self._render_ui()
                await self._apply_effect()

    async def _handle_color_page_press(self, row: int, col: int) -> None:
        """Handle button press on color page."""
        # Prev page button
        if row == 2 and col == 2:
            self.current_page = "effect"
            await self._render_ui()
            return

        # Next page button
        if row == 2 and col == 3:
            self.current_page = "speed"
            await self._render_ui()
            return

        # Color selection (rows 0-1, 5 per row)
        if row == 0 and col <= 4:
            idx = col
            if idx < len(self.COLORS):
                self.selected_color_idx = idx
                await self._render_ui()
                await self._apply_effect()
        elif row == 1 and col <= 3:
            idx = 5 + col
            if idx < len(self.COLORS):
                self.selected_color_idx = idx
                await self._render_ui()
                await self._apply_effect()

    async def _handle_speed_page_press(self, row: int, col: int) -> None:
        """Handle button press on speed page."""
        # Prev page button
        if row == 2 and col == 2:
            self.current_page = "color"
            await self._render_ui()
            return

        # Next page button (params)
        if row == 2 and col == 3:
            self.current_page = "params"
            await self._render_ui()
            return

        # Speed selection (row 0, cols 1-4)
        if row == 0 and 1 <= col <= 4:
            idx = col - 1
            if idx < len(self.SPEEDS):
                self.selected_speed_idx = idx
                await self._render_ui()
                await self._apply_effect()

        # Brightness selection (row 1, cols 1-4)
        if row == 1 and 1 <= col <= 4:
            idx = col - 1
            if idx < len(self.BRIGHTNESS_LEVELS):
                self.brightness_idx = idx
                await self._render_ui()
                await self._apply_effect()

    async def _handle_params_page_press(self, row: int, col: int) -> None:
        """Handle button press on params page."""
        # Prev page button
        if row == 2 and col == 2:
            self.current_page = "speed"
            await self._render_ui()
            return

        effect = self.EFFECTS[self.selected_effect_idx]

        # Determine which parameter is at which row based on what's enabled
        param_row = 0

        # Track which parameter is at which row
        num_sparkles_row = None
        size_row = None
        tail_length_row = None
        period_row = None

        if "num_sparkles" in effect["params"]:
            num_sparkles_row = param_row
            param_row += 1

        if "size" in effect["params"]:
            size_row = param_row
            param_row += 1

        if "tail_length" in effect["params"]:
            tail_length_row = param_row
            param_row += 1

        if "period" in effect["params"]:
            period_row = param_row

        # All parameters use cols 0(label), 1(-), 2(value), 3(+)
        # Handle button presses based on which parameter is at this row
        if row == num_sparkles_row and num_sparkles_row is not None:
            if col == 1:  # Decrease
                self.effect_params["num_sparkles"] = max(1, self.effect_params["num_sparkles"] - 1)
                await self._render_ui()
                await self._apply_effect()
            elif col == 3:  # Increase
                self.effect_params["num_sparkles"] = min(20, self.effect_params["num_sparkles"] + 1)
                await self._render_ui()
                await self._apply_effect()

        elif row == size_row and size_row is not None:
            if col == 1:  # Decrease
                self.effect_params["size"] = max(1, self.effect_params["size"] - 1)
                await self._render_ui()
                await self._apply_effect()
            elif col == 3:  # Increase
                self.effect_params["size"] = min(20, self.effect_params["size"] + 1)
                await self._render_ui()
                await self._apply_effect()

        elif row == tail_length_row and tail_length_row is not None:
            if col == 1:  # Decrease
                self.effect_params["tail_length"] = max(1, self.effect_params["tail_length"] - 1)
                await self._render_ui()
                await self._apply_effect()
            elif col == 3:  # Increase
                self.effect_params["tail_length"] = min(30, self.effect_params["tail_length"] + 1)
                await self._render_ui()
                await self._apply_effect()

        elif row == period_row and period_row is not None and period_row < 2:
            # Only handle period if not at row 2 (where navigation is)
            if col == 1:  # Decrease
                self.effect_params["period"] = max(1, self.effect_params["period"] - 1)
                await self._render_ui()
                await self._apply_effect()
            elif col == 3:  # Increase
                self.effect_params["period"] = min(10, self.effect_params["period"] + 1)
                await self._render_ui()
                await self._apply_effect()

    async def on_exit(self) -> None:
        """Cleanup on exit."""
        logger.info("Exiting LED Playground")

        # Reset brightness to 0.05 (5%) to avoid power issues on next module
        if self.state_manager.led_manager:
            self.state_manager.led_manager.pixels.brightness = 0.05
            logger.info("LED brightness reset to 0.05 (5%)")
