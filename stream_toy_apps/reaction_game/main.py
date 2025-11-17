"""
Reaction Game - Test your reaction time

Random buttons light up and players must press them as quickly as possible.
The game tracks reaction times and provides a final score.
"""

import random
import asyncio
import time
from typing import List, Tuple
import logging

from stream_toy.scene.base_scene import BaseScene
from stream_toy.scene.module_launch_scene import ModuleLaunchScene

logger = logging.getLogger(__name__)


class ReactionGameScene(BaseScene):
    """Quick reaction time game."""

    def __init__(self, runtime):
        super().__init__(runtime)
        self.rounds: int = 10
        self.current_round: int = 0
        self.active_button: Optional[Tuple[int, int]] = None
        self.round_start_time: float = 0
        self.reaction_times: List[float] = []
        self.game_active: bool = False

    async def on_enter(self) -> None:
        """Initialize game."""
        logger.info("Starting Reaction Game")

        # Show instructions
        await self._show_instructions()

        logger.info("Reaction Game initialized")

    async def _show_instructions(self) -> None:
        """Show game instructions."""
        # Clear board
        self.clear_all_tiles(color="black")

        # Show instructions
        self.set_tile_text(0, 1, "GET", font_size=32, fg_color="yellow")
        self.set_tile_text(0, 2, "READY", font_size=32, fg_color="yellow")
        self.set_tile_text(0, 3, "!", font_size=48, fg_color="yellow")

        self.set_tile_text(1, 0, "Hit", font_size=24, fg_color="white")
        self.set_tile_text(1, 1, "the", font_size=24, fg_color="white")
        self.set_tile_text(1, 2, "GREEN", font_size=24, fg_color="green")
        self.set_tile_text(1, 3, "button", font_size=24, fg_color="white")

        # Exit button
        self.set_tile_text(2, 4, "←", font_size=48, fg_color="red")

        # Start button
        self.set_tile_text(2, 2, "START", font_size=28, fg_color="lime", bg_color="darkgreen")

        self.submit_tiles()

    async def main_loop(self) -> None:
        """Main game loop."""
        logger.debug("Reaction Game main loop started")

        while self._running:
            event = await self.input_manager.async_poll_event(timeout=1.0)

            if event is None:
                continue

            if not event.is_pressed:
                continue

            # Handle exit
            if event.row == 2 and event.col == 4:
                logger.info("Exit requested")
                self.switch_scene(ModuleLaunchScene)
                return

            # Handle start button
            if not self.game_active and event.row == 2 and event.col == 2:
                logger.info("Game started")
                self.game_active = True
                await self._play_game()
                continue

            # Handle button press during game
            if self.game_active and self.active_button:
                await self._handle_button_press(event.row, event.col)

    async def _play_game(self) -> None:
        """Play the reaction game."""
        self.current_round = 0
        self.reaction_times = []

        # Clear board
        self.clear_all_tiles(color="black")
        self.set_tile_text(2, 4, "←", font_size=48, fg_color="red")
        self.submit_tiles()

        await asyncio.sleep(1)

        # Play rounds
        for round_num in range(1, self.rounds + 1):
            self.current_round = round_num

            logger.debug(f"Round {round_num}/{self.rounds}")

            # Show round number
            self.set_tile_text(0, 2, f"Round\n{round_num}", font_size=24, fg_color="yellow")
            self.submit_tiles()

            # Random delay before showing button
            delay = random.uniform(1.0, 3.0)
            await asyncio.sleep(delay)

            # Select random button (not exit button)
            available_buttons = [
                (r, c) for r in range(3) for c in range(5)
                if not (r == 2 and c == 4)  # Not exit button
            ]
            self.active_button = random.choice(available_buttons)

            # Light up button
            row, col = self.active_button
            self.set_tile_text(row, col, "GO!", font_size=48, fg_color="white", bg_color="green")
            self.submit_tiles()

            # Play LED animation
            await self._play_go_animation()

            # Start timer
            self.round_start_time = time.time()

            # Wait for button press (with timeout)
            timeout = 3.0
            start = time.time()

            while self.active_button and (time.time() - start) < timeout:
                await asyncio.sleep(0.1)

            # Check if button was pressed
            if self.active_button:
                # Timeout - missed
                logger.debug(f"Round {round_num}: MISS (timeout)")
                self.reaction_times.append(999.0)  # Penalty
                self.set_tile_text(row, col, "MISS", font_size=32, fg_color="white", bg_color="red")
                self.submit_tiles()
                await asyncio.sleep(1)
                self.active_button = None

            # Clear button
            self.clear_tile(row, col)
            self.submit_tiles()

            await asyncio.sleep(0.5)

        # Show results
        await self._show_results()

        self.game_active = False

    async def _handle_button_press(self, row: int, col: int) -> None:
        """Handle button press during active round."""
        if not self.active_button:
            return

        target_row, target_col = self.active_button

        if row == target_row and col == target_col:
            # Correct button!
            reaction_time = time.time() - self.round_start_time
            self.reaction_times.append(reaction_time)

            logger.info(f"Round {self.current_round}: Hit in {reaction_time:.3f}s")

            # Show feedback
            self.set_tile_text(row, col, f"{int(reaction_time*1000)}ms", font_size=24, fg_color="white", bg_color="blue")
            self.submit_tiles()

            await asyncio.sleep(0.5)

            self.active_button = None
        else:
            # Wrong button!
            logger.debug(f"Round {self.current_round}: Wrong button")
            self.set_tile_text(row, col, "X", font_size=48, fg_color="white", bg_color="red")
            self.submit_tiles()
            await asyncio.sleep(0.3)
            self.clear_tile(row, col)
            self.submit_tiles()

    async def _play_go_animation(self) -> None:
        """Play animation when button lights up."""
        try:
            from adafruit_led_animation.animation.pulse import Pulse
            from adafruit_led_animation.color import GREEN

            if self.state_manager.led_manager:
                pulse = Pulse(self.state_manager.led_manager.pixels, speed=0.1, color=GREEN, period=0.5)
                self.device.run_led_animation(pulse, duration=0.5)
        except Exception as e:
            logger.debug(f"LED animation failed: {e}")

    async def _show_results(self) -> None:
        """Show final results."""
        logger.info("Showing results")

        # Calculate stats
        valid_times = [t for t in self.reaction_times if t < 900]

        if valid_times:
            avg_time = sum(valid_times) / len(valid_times)
            best_time = min(valid_times)
            hits = len(valid_times)
        else:
            avg_time = 0
            best_time = 0
            hits = 0

        logger.info(f"Results: Hits={hits}/{self.rounds}, Avg={avg_time:.3f}s, Best={best_time:.3f}s")

        # Clear board
        self.clear_all_tiles(color="black")

        # Show results
        self.set_tile_text(0, 0, "Hits", font_size=20, fg_color="yellow")
        self.set_tile_text(0, 1, f"{hits}", font_size=32, fg_color="white")
        self.set_tile_text(0, 2, "/", font_size=24, fg_color="gray")
        self.set_tile_text(0, 3, f"{self.rounds}", font_size=32, fg_color="white")

        if valid_times:
            self.set_tile_text(1, 0, "Avg", font_size=20, fg_color="yellow")
            self.set_tile_text(1, 1, f"{int(avg_time*1000)}", font_size=28, fg_color="white")
            self.set_tile_text(1, 2, "ms", font_size=20, fg_color="gray")

            self.set_tile_text(2, 0, "Best", font_size=20, fg_color="yellow")
            self.set_tile_text(2, 1, f"{int(best_time*1000)}", font_size=28, fg_color="lime")
            self.set_tile_text(2, 2, "ms", font_size=20, fg_color="gray")

        # Exit button
        self.set_tile_text(2, 4, "←", font_size=48, fg_color="red")

        # Retry button
        self.set_tile_text(1, 4, "↻", font_size=48, fg_color="green")

        self.submit_tiles()

        # Play victory animation if good performance
        if hits >= 7 and avg_time < 0.7:
            await self._play_victory_animation()

        # Wait for exit or retry
        while self._running:
            event = await self.input_manager.async_poll_event(timeout=10.0)

            if event is None:
                # Timeout - return to launcher
                self.switch_scene(ModuleLaunchScene)
                return

            if not event.is_pressed:
                continue

            # Exit
            if event.row == 2 and event.col == 4:
                self.switch_scene(ModuleLaunchScene)
                return

            # Retry
            if event.row == 1 and event.col == 4:
                self.game_active = True
                await self._play_game()
                return

    async def _play_victory_animation(self) -> None:
        """Play celebration animation."""
        try:
            from adafruit_led_animation.animation.rainbow import Rainbow

            if self.state_manager.led_manager:
                rainbow = Rainbow(self.state_manager.led_manager.pixels, speed=0.1, period=2)
                self.device.run_led_animation(rainbow, duration=2.0)
        except Exception:
            pass

    async def on_exit(self) -> None:
        """Cleanup on exit."""
        logger.info("Exiting Reaction Game")
        self.game_active = False
