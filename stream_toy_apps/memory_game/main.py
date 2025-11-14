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

    async def on_enter(self) -> None:
        """Initialize game."""
        logger.info("Starting Memory Game")

        # Use animal images from demo if available
        assets_dir = Path(__file__).parent / "assets" / "images"
        demo_assets = Path(__file__).parent.parent.parent / "img" / "memory" / "set_01"

        # Try to find card images
        if demo_assets.exists():
            images = list(demo_assets.glob("animal_*.png"))
            logger.info(f"Found {len(images)} animal images in demo assets")
        else:
            images = list(assets_dir.glob("*.png")) if assets_dir.exists() else []
            logger.info(f"Found {len(images)} images in module assets")

        if len(images) < 7:
            logger.warning(f"Not enough card images ({len(images)}), using text cards")
            await self._show_text_game()
            return

        # Setup card pairs (7 pairs = 14 cards, 1 button for exit)
        self.cards = self._create_card_deck(images[:7])

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

            if not event.is_pressed:
                continue

            # Handle exit (long press bottom-right)
            if event.row == 2 and event.col == 4:
                if event.long_press:
                    logger.info("Exit requested")
                    self.switch_scene(ModuleLaunchScene)
                    return
                else:
                    # Short press: restart game
                    logger.info("Restart requested")
                    await self.on_exit()
                    await self.on_enter()
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
                await asyncio.sleep(1.5)

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

    async def _play_match_animation(self) -> None:
        """Play success animation for matched pair."""
        try:
            from adafruit_led_animation.animation.pulse import Pulse
            from adafruit_led_animation.color import GREEN

            pulse = Pulse(self.device.led_manager.pixels, speed=0.05, color=GREEN, period=1)
            self.device.run_led_animation(pulse, duration=1.0)
        except Exception as e:
            logger.debug(f"LED animation failed: {e}")

        await asyncio.sleep(0.5)

    async def _show_win_screen(self) -> None:
        """Display victory screen."""
        logger.info(f"Game won! Score: {self.score}, Moves: {self.moves}")

        # Show celebration
        for row in range(3):
            for col in range(5):
                if row == 2 and col == 4:
                    continue
                self.set_tile_text(row, col, "🎉", font_size=48, bg_color="gold")

        self.submit_tiles()

        # Play victory animation
        try:
            from adafruit_led_animation.animation.rainbow import Rainbow

            rainbow = Rainbow(self.device.led_manager.pixels, speed=0.1, period=2)
            self.device.run_led_animation(rainbow, duration=3.0)
        except Exception:
            pass

        await asyncio.sleep(3)

        # Return to launcher
        self.switch_scene(ModuleLaunchScene)

    async def on_exit(self) -> None:
        """Cleanup on exit."""
        logger.info("Exiting Memory Game")
