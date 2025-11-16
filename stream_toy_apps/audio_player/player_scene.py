"""
Audio Player Playback Scene

Shows playback controls for currently playing audio file.
"""

import asyncio
from pathlib import Path
from typing import Optional
import logging

from stream_toy.scene.base_scene import BaseScene
from stream_toy.sound_manager import PlaybackStatus

logger = logging.getLogger(__name__)


class PlayerScene(BaseScene):
    """
    Audio playback control scene.

    Layout:
    Row 0: [<<10min] [<<1min] [<<10s] [>>10s] [>>1min]
    Row 1: [Vol-]   [Pause ] [Vol+] [      ] [      ]
    Row 2: [Time Display................] [Back  ]
    """

    # Button positions
    BTN_SKIP_BACK_10MIN = (0, 0)
    BTN_SKIP_BACK_1MIN = (0, 1)
    BTN_SKIP_BACK_10S = (0, 2)
    BTN_SKIP_FWD_10S = (0, 3)
    BTN_SKIP_FWD_1MIN = (0, 4)

    BTN_VOL_DOWN = (1, 0)
    BTN_PAUSE = (1, 1)
    BTN_VOL_UP = (1, 2)

    BTN_TIME_DISPLAY = [(2, 0), (2, 1), (2, 2), (2, 3)]  # Multi-tile time display
    BTN_BACK = (2, 4)

    # Image file extensions for cover art
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}

    def __init__(self, runtime, audio_file: Path, return_dir: Optional[Path] = None):
        """
        Initialize player scene.

        Args:
            runtime: StreamToyRuntime instance
            audio_file: Path to audio file to play
            return_dir: Directory to return to when going back (defaults to file's parent)
        """
        super().__init__(runtime)
        self.audio_file = audio_file
        self.return_dir = return_dir if return_dir else audio_file.parent

        # Load current volume from sound manager (which reads from persistent settings)
        sound_mgr = runtime.device.sound_manager if runtime.device else None
        if sound_mgr and sound_mgr.is_available():
            self.current_volume = sound_mgr._volume
        else:
            self.current_volume = 0.1  # Fallback if sound manager not available

        self.update_task: Optional[asyncio.Task] = None
        self.cover_art: Optional[Path] = None

        # Track which static tiles have been initialized
        self._static_tiles_initialized = False

    async def on_enter(self):
        """Initialize the scene and start playback."""
        logger.info(f"Entering Player Scene for {self.audio_file.name}")

        # Find cover art
        self.cover_art = self.find_cover_art()

        sound_mgr = self.runtime.device.sound_manager
        if not sound_mgr or not sound_mgr.is_available():
            logger.error("Sound manager not available!")
            # Show error and return to browser
            await self._show_error("Audio not\navailable")
            await asyncio.sleep(2)
            await self.go_back()
            return

        # Set up callbacks
        sound_mgr.set_status_callback(self.on_status_change)
        sound_mgr.set_position_callback(self.on_position_update)

        # Start playback
        sound_mgr.play_music(self.audio_file, volume=self.current_volume)

        # Render UI
        await self.render_ui()

        # Start update task for time display
        self.update_task = asyncio.create_task(self._update_loop())

    async def on_exit(self):
        """Cleanup when leaving scene."""
        logger.info("Exiting Player Scene")

        # Cancel update task
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

        # Clear callbacks (but don't stop playback - let browser scene handle that)
        sound_mgr = self.runtime.device.sound_manager
        if sound_mgr:
            sound_mgr.set_status_callback(None)
            sound_mgr.set_position_callback(None)

    async def render_ui(self):
        """Render all player controls."""
        # Row 0: Skip controls
        self.set_tile_text(0, 0, "<<\n10min", font_size=12)
        self.set_tile_text(0, 1, "<<\n1min", font_size=12)
        self.set_tile_text(0, 2, "<<\n10s", font_size=14)
        self.set_tile_text(0, 3, ">>\n10s", font_size=14)
        self.set_tile_text(0, 4, ">>\n1min", font_size=12)

        # Row 1: Volume, pause, and cover art
        self.set_tile_text(1, 0, "Vol\n-", font_size=16)
        await self._update_pause_button()
        self.set_tile_text(1, 2, "Vol\n+", font_size=16)

        # Show cover art if available, otherwise empty
        if self.cover_art:
            self.set_tile_file(1, 3, str(self.cover_art))
        else:
            self.set_tile_text(1, 3, "", font_size=12)

        self.set_tile_text(1, 4, "", font_size=12)  # Empty

        # Row 2: Time display and back button
        await self._update_time_display()
        self.set_tile_text(2, 4, "←\nBack", font_size=16)

        self.submit_tiles()

    def find_cover_art(self) -> Optional[Path]:
        """
        Find cover art image for the current audio file.

        Looks for an image file with the same name as the audio file.

        Returns:
            Path to cover art image, or None if not found
        """
        # Get the stem (filename without extension)
        stem = self.audio_file.stem

        # Check for image files with same name
        for ext in self.IMAGE_EXTENSIONS:
            cover_path = self.audio_file.parent / f"{stem}{ext}"
            if cover_path.exists():
                logger.info(f"Found cover art: {cover_path}")
                return cover_path

        return None

    async def _update_pause_button(self):
        """Update pause/play button based on current state."""
        sound_mgr = self.runtime.device.sound_manager
        if not sound_mgr:
            return

        status = sound_mgr.get_status()
        if status == PlaybackStatus.PLAYING:
            self.set_tile_text(1, 1, "❚❚\nPause", font_size=14)
        elif status == PlaybackStatus.PAUSED:
            self.set_tile_text(1, 1, "▶\nPlay", font_size=16)
        else:  # STOPPED
            # Check if stopped at the end (finished) or just stopped
            position = sound_mgr.get_position()
            duration = sound_mgr.get_duration()
            if duration > 0 and position >= duration - 1.0:
                # Finished playing - show replay option
                self.set_tile_text(1, 1, "↻\nReplay", font_size=14)
            else:
                # Stopped for other reason
                self.set_tile_text(1, 1, "▶\nPlay", font_size=16)

    async def _update_time_display(self, force_all: bool = False):
        """
        Update time display tiles.

        Args:
            force_all: If True, update all tiles including static ones (duration, filename)
        """
        sound_mgr = self.runtime.device.sound_manager
        if not sound_mgr:
            return

        position = sound_mgr.get_position()
        duration = sound_mgr.get_duration()

        # Format times as MM:SS
        pos_min = int(position // 60)
        pos_sec = int(position % 60)
        dur_min = int(duration // 60)
        dur_sec = int(duration % 60)

        # Calculate progress percentage
        if duration > 0:
            progress = (position / duration) * 100
        else:
            progress = 0

        # ALWAYS update: Position (2,0) - changes every second
        self.set_tile_text(2, 0, f"{pos_min}:{pos_sec:02d}", font_size=18)

        # ALWAYS update: Progress (2,2) - changes as position changes
        self.set_tile_text(2, 2, f"{progress:.0f}%", font_size=18)

        # Only update static tiles on first call or when forced
        if not self._static_tiles_initialized or force_all:
            # STATIC: Duration (2,1) - doesn't change after file starts
            self.set_tile_text(2, 1, f"{dur_min}:{dur_sec:02d}", font_size=18)

            # STATIC: Filename (2,3) - doesn't change
            filename = self.audio_file.stem
            self.set_tile_text(2, 3, filename, font_size=10, wrap=True)

            self._static_tiles_initialized = True
            logger.debug("Updated static tiles (duration, filename)")

    async def _show_error(self, message: str):
        """Show error message."""
        for row in range(3):
            for col in range(5):
                self.set_tile_text(row, col, "", font_size=12)

        self.set_tile_text(1, 2, message, font_size=16)
        self.submit_tiles()

    async def _update_loop(self):
        """Background loop to update time display."""
        # Track previous values to avoid unnecessary updates
        last_position = -1
        last_status = None

        while self._running:
            try:
                sound_mgr = self.runtime.device.sound_manager
                if not sound_mgr:
                    break

                # Get current values
                position = sound_mgr.get_position()
                status = sound_mgr.get_status()

                # Only update if values changed
                pos_changed = abs(position - last_position) >= 1.0  # Update every second
                status_changed = status != last_status

                if pos_changed or status_changed:
                    await self._update_time_display()
                    await self._update_pause_button()
                    self.submit_tiles()

                    last_position = position
                    last_status = status

                await asyncio.sleep(1.0)  # Check once per second (time only changes every second)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                await asyncio.sleep(0.5)

    def on_status_change(self, status: PlaybackStatus):
        """Handle playback status changes."""
        logger.debug(f"Playback status changed: {status}")
        # Note: We don't auto-exit when playback finishes.
        # User can replay or manually go back.

    def on_position_update(self, position: float, duration: float):
        """Handle playback position updates."""
        # Position is updated via _update_loop, no need to do anything here
        pass

    async def on_key_press(self, row: int, col: int, long_press: bool = False):
        """Handle button press."""
        logger.debug(f"Button pressed: ({row}, {col}), long_press={long_press}")

        sound_mgr = self.runtime.device.sound_manager
        if not sound_mgr:
            return

        button = (row, col)

        # Skip controls (Row 0)
        if button == self.BTN_SKIP_BACK_10MIN:
            sound_mgr.seek(-600)  # -10 minutes
        elif button == self.BTN_SKIP_BACK_1MIN:
            sound_mgr.seek(-60)  # -1 minute
        elif button == self.BTN_SKIP_BACK_10S:
            sound_mgr.seek(-10)  # -10 seconds
        elif button == self.BTN_SKIP_FWD_10S:
            sound_mgr.seek(10)  # +10 seconds
        elif button == self.BTN_SKIP_FWD_1MIN:
            sound_mgr.seek(60)  # +1 minute

        # Volume and pause (Row 1)
        elif button == self.BTN_VOL_DOWN:
            self.current_volume = max(0.01, self.current_volume - 0.05)
            sound_mgr.set_volume(self.current_volume)
            logger.info(f"Volume: {self.current_volume:.2f}")
        elif button == self.BTN_PAUSE:
            status = sound_mgr.get_status()
            if status == PlaybackStatus.PLAYING:
                sound_mgr.pause()
            elif status == PlaybackStatus.PAUSED:
                sound_mgr.resume()
            elif status == PlaybackStatus.STOPPED:
                # Restart playback from beginning
                logger.info("Restarting playback from beginning")
                sound_mgr.stop()  # Ensure clean state
                sound_mgr.play_music(self.audio_file, volume=self.current_volume)
        elif button == self.BTN_VOL_UP:
            self.current_volume = min(1.0, self.current_volume + 0.05)
            sound_mgr.set_volume(self.current_volume)
            logger.info(f"Volume: {self.current_volume:.2f}")

        # Back button (Row 2)
        elif button == self.BTN_BACK:
            await self.go_back()

        # Update UI immediately
        await self._update_pause_button()
        await self._update_time_display()
        self.submit_tiles()

    async def go_back(self):
        """Return to audio browser scene."""
        logger.info(f"Returning to audio browser at {self.return_dir}")

        # Import here to avoid circular dependency
        from .main import AudioPlayerScene

        # Stop playback when going back
        sound_mgr = self.runtime.device.sound_manager
        if sound_mgr:
            sound_mgr.stop()

        # Switch to browser scene, passing the directory to return to
        self.switch_scene(AudioPlayerScene, start_dir=self.return_dir)

    async def main_loop(self):
        """Main scene loop."""
        logger.info("Player Scene main loop started")

        while self._running:
            # Poll for input events
            event = await self.input_manager.async_poll_event(timeout=1.0)

            if event is None:
                continue

            # Handle press and release events
            if event.is_pressed:
                # Button pressed - ignore for now
                pass
            else:
                # Button released - execute action
                await self.on_key_press(event.row, event.col, long_press=event.long_press)

        logger.info("Player Scene main loop ended")
