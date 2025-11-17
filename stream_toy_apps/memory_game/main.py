"""
Memory Game - Classic card matching game

Players flip cards to find matching pairs. The game tracks score
and provides visual feedback.
"""

import random
import asyncio
from pathlib import Path
from typing import Optional, List, Dict
import logging

from stream_toy.scene.base_scene import BaseScene
from stream_toy.scene.module_launch_scene import ModuleLaunchScene

logger = logging.getLogger(__name__)


class MemoryGameScene(BaseScene):
    """Memory card matching game."""

    def __init__(self, runtime):
        super().__init__(runtime)
        self.cards: List[Path] = []
        self.revealed: Dict[int, bool] = {}
        self.matched: set = set()
        self.first_card: Optional[int] = None
        self.score: int = 0
        self.moves: int = 0
        self.game_won: bool = False

    async def on_enter(self) -> None:
        """Initialize game."""
        logger.info("Starting Memory Game")

        # Reset game state
        self.game_won = False
        self.matched.clear()
        self.revealed.clear()
        self.first_card = None
        self.score = 0
        self.moves = 0

        # Reset LEDs to dim white before starting sparkle
        try:
            if self.state_manager.led_manager:
                # Clear any previous animations
                self.state_manager.led_manager.background_animation = None
                self.state_manager.led_manager.foreground_animation = None
                # Set dim white (30% brightness of full white)
                dim_white = (77, 77, 77)
                self.state_manager.led_manager.set_all(dim_white)
                await asyncio.sleep(0.2)  # Brief pause to ensure it's set
        except Exception as e:
            logger.debug(f"Failed to reset LEDs: {e}")

        # Set Sparkle LED animation for background
        try:
            from adafruit_led_animation.animation.sparkle import Sparkle
            from adafruit_led_animation.color import WHITE

            if self.state_manager.led_manager:
                sparkle = Sparkle(
                    self.state_manager.led_manager.pixels,
                    speed=1.0,  # 1s interval
                    color=WHITE,
                    num_sparkles=1
                )
                self.device.set_background_led_animation(sparkle)
                logger.debug("Sparkle LED animation set for memory game")
        except Exception as e:
            logger.debug(f"Failed to set Sparkle animation: {e}")

        # Load tile images from module assets
        # Use tile_set_01 by default, can be made configurable later
        assets_dir = Path(__file__).parent / "assets" / "tiles" / "tile_set_01"

        # Try to find tile images
        images = list(assets_dir.glob("tile_*.png")) if assets_dir.exists() else []
        logger.info(f"Found {len(images)} tile images in module assets")

        if len(images) < 7:
            logger.warning(f"Not enough card images ({len(images)}), using text cards")
            await self._show_text_game()
            return

        # Setup card pairs (7 pairs = 14 cards, 1 button for exit)
        # Randomly select 7 tiles from available images
        selected_images = random.sample(images, 7)
        self.cards = self._create_card_deck(selected_images)

        # Render initial state
        await self._render_game_board()

        logger.info("Memory Game initialized")

    def _create_card_deck(self, images: List[Path]) -> List[Path]:
        """Create and shuffle card pairs."""
        deck = images * 2  # Create pairs
        random.shuffle(deck)
        return deck

    async def _render_game_board(self) -> None:
        """Render all cards face-down."""
        for idx in range(14):
            row = idx // 5
            col = idx % 5
            if row == 2 and col == 4:
                continue  # Skip last position (exit button)
            self._render_card_back(row, col)

        # Exit button
        self.set_tile_text(2, 4, "←", font_size=48, fg_color="yellow")

        self.submit_tiles()

    def _render_card_back(self, row: int, col: int) -> None:
        """Show card back."""
        self.set_tile_text(row, col, "?", font_size=64, fg_color="cyan", bg_color="darkblue")

    def _render_card_face(self, row: int, col: int, idx: int) -> None:
        """Show card face."""
        try:
            self.set_tile_file(row, col, str(self.cards[idx]))
        except Exception as e:
            logger.error(f"Failed to render card {idx}: {e}")
            self.set_tile_text(row, col, str(idx % 9 + 1), font_size=48)

    async def _show_text_game(self) -> None:
        """Fallback: number matching game."""
        logger.info("Using text-based memory game")

        # Create number pairs
        numbers = list(range(1, 8)) * 2
        random.shuffle(numbers)
        self.cards = numbers  # Store numbers instead of paths

        # Render cards
        for idx in range(14):
            row = idx // 5
            col = idx % 5
            if row == 2 and col == 4:
                continue
            self._render_card_back(row, col)

        # Exit button
        self.set_tile_text(2, 4, "←", font_size=48, fg_color="yellow")
        self.submit_tiles()

    async def main_loop(self) -> None:
        """Main game loop."""
        logger.debug("Memory Game main loop started")

        while self._running:
            event = await self.input_manager.async_poll_event(timeout=1.0)

            if event is None:
                continue

            # Handle long press on release events (long_press flag only set on release)
            if not event.is_pressed and event.long_press:
                if event.row == 2 and event.col == 4:
                    logger.info("Exit requested (long press)")
                    self.switch_scene(ModuleLaunchScene)
                    return
                continue

            # Skip other release events (we only care about presses)
            if not event.is_pressed:
                continue

            # Handle back button (short press)
            if event.row == 2 and event.col == 4:
                # Short press: restart game (or exit if game won)
                if self.game_won:
                    logger.info("Exit from victory screen")
                    self.switch_scene(ModuleLaunchScene)
                    return
                else:
                    logger.info("Restart requested")
                    await self.on_exit()
                    await self.on_enter()
                continue

            # If game is won, ignore other button presses
            if self.game_won:
                continue

            # Handle card tap
            await self._handle_card_tap(event.row, event.col)

    async def _handle_card_tap(self, row: int, col: int) -> None:
        """Process card selection."""
        idx = row * 5 + col

        # Ignore invalid positions
        if idx >= 14 or (row == 2 and col == 4):
            return

        # Ignore if already matched or revealed
        if idx in self.matched or idx in self.revealed:
            logger.debug(f"Card {idx} already matched or revealed")
            return

        logger.debug(f"Card {idx} selected")

        # Reveal card
        self.revealed[idx] = True

        # Render face
        if isinstance(self.cards, list) and isinstance(self.cards[0], Path):
            self._render_card_face(row, col, idx)
        else:
            # Text mode
            self.set_tile_text(row, col, str(self.cards[idx]), font_size=64, fg_color="white", bg_color="green")

        self.submit_tiles()

        # Play reveal animation
        await self._play_reveal_animation()

        if self.first_card is None:
            # First card of pair
            self.first_card = idx
            logger.debug(f"First card: {idx}")
        else:
            # Second card of pair
            self.moves += 1
            logger.debug(f"Second card: {idx}, checking match...")

            # Check for match
            if self.cards[self.first_card] == self.cards[idx]:
                # Match!
                logger.info(f"Match found: {self.first_card} and {idx}")
                self.matched.add(self.first_card)
                self.matched.add(idx)
                self.score += 10

                # Play success animation
                await self._play_match_animation()

                # Check win condition
                if len(self.matched) == 14:
                    await self._show_win_screen()
                    return
            else:
                # No match
                logger.debug(f"No match: {self.first_card} and {idx}")

                # Play mismatch animation
                await self._play_mismatch_animation()

                await asyncio.sleep(0.5)  # Brief pause before hiding cards

                # Hide both cards
                first_row = self.first_card // 5
                first_col = self.first_card % 5
                self._render_card_back(first_row, first_col)
                self._render_card_back(row, col)
                self.submit_tiles()

            # Reset for next pair
            self.revealed.clear()
            self.first_card = None

    async def _play_reveal_animation(self) -> None:
        """Play card reveal animation."""
        await asyncio.sleep(0.2)

    async def _reset_leds_to_dim_white(self) -> None:
        """Reset all LEDs to dim white and clear foreground animations."""
        try:
            from adafruit_led_animation.animation.solid import Solid

            if self.state_manager.led_manager:
                # Set dim white (30% brightness of full white)
                dim_white = (77, 77, 77)
                # Use a brief Solid animation to properly reset within the animation system
                solid = Solid(self.state_manager.led_manager.pixels, color=dim_white)
                self.device.run_led_animation(solid, duration=0.3)
                await asyncio.sleep(0.35)  # Wait for solid animation to complete
        except Exception as e:
            logger.debug(f"LED reset failed: {e}")

    async def _play_match_animation(self) -> None:
        """Play success animation for matched pair."""
        try:
            from adafruit_led_animation.animation.pulse import Pulse
            from adafruit_led_animation.color import GREEN

            if self.state_manager.led_manager:
                pulse = Pulse(self.state_manager.led_manager.pixels, speed=0.05, color=GREEN, period=1)
                self.device.run_led_animation(pulse, duration=1.0)
                await asyncio.sleep(1.1)  # Wait for animation to complete
        except Exception as e:
            logger.debug(f"LED animation failed: {e}")

        # Reset LEDs to dim white
        await self._reset_leds_to_dim_white()

    async def _play_mismatch_animation(self) -> None:
        """Play animation for mismatched pair."""
        try:
            from adafruit_led_animation.animation.pulse import Pulse
            from adafruit_led_animation.color import RED

            if self.state_manager.led_manager:
                pulse = Pulse(self.state_manager.led_manager.pixels, speed=0.05, color=RED, period=1)
                self.device.run_led_animation(pulse, duration=0.8)
                await asyncio.sleep(0.9)  # Wait for animation to complete
        except Exception as e:
            logger.debug(f"LED animation failed: {e}")

        # Reset LEDs to dim white
        await self._reset_leds_to_dim_white()

    async def _show_win_screen(self) -> None:
        """Display victory screen."""
        logger.info(f"Game won! Score: {self.score}, Moves: {self.moves}")

        # Set game won flag
        self.game_won = True

        # Show celebration
        for row in range(3):
            for col in range(5):
                if row == 2 and col == 4:
                    continue
                self.set_tile_text(row, col, "★", font_size=48, bg_color="gold")

        # Keep back button visible
        self.set_tile_text(2, 4, "←", font_size=48, fg_color="yellow")

        self.submit_tiles()

        # Set continuous rainbow animation as background
        try:
            from adafruit_led_animation.animation.rainbow import Rainbow

            if self.state_manager.led_manager:
                rainbow = Rainbow(self.state_manager.led_manager.pixels, speed=0.1, period=2)
                self.device.set_background_led_animation(rainbow)
                logger.debug("Rainbow LED animation set for victory screen (continuous)")
        except Exception as e:
            logger.debug(f"Failed to set rainbow animation: {e}")

        # Don't automatically return - wait for user to press back button
        logger.info("Victory! Press back button to return to menu")

    async def on_exit(self) -> None:
        """Cleanup on exit."""
        logger.info("Exiting Memory Game")
