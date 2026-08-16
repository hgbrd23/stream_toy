"""
Audio Player Playback Scene

Shows playback controls for currently playing audio file.
"""

import asyncio
from pathlib import Path
from typing import Optional
import logging
import time

from stream_toy.scene.base_scene import BaseScene
from stream_toy.sound_manager import PlaybackStatus
from stream_toy.audio_metadata_service import AudioMetadataService
from stream_toy.settings_manager import SettingsManager

from .audio_files import find_cover_art, get_next_audio_file

logger = logging.getLogger(__name__)

# Icon paths
ICONS_DIR = Path(__file__).parent.parent.parent / "assets" / "tiles"
ICON_SEEK_BACK_5MIN = str(ICONS_DIR / "audio-seek-back-5min.png")
ICON_SEEK_BACK_1MIN = str(ICONS_DIR / "audio-seek-back-1min.png")
ICON_SEEK_START = str(ICONS_DIR / "audio-seek-start.png")
ICON_SEEK_FWD_1MIN = str(ICONS_DIR / "audio-seek-forward-1min.png")
ICON_SEEK_FWD_5MIN = str(ICONS_DIR / "audio-seek-forward-5min.png")
ICON_VOLUME_DOWN = str(ICONS_DIR / "volume-down.png")
ICON_VOLUME_UP = str(ICONS_DIR / "volume-up.png")
ICON_BACK = str(ICONS_DIR / "back.png")


class PlayerScene(BaseScene):
    """
    Audio playback control scene.

    Layout:
    Row 0: [-5min] [-1min] [Start] [+1min] [+5min]
    Row 1: [Vol-]  [Pause] [Vol+]  [Cover] [     ]
    Row 2: [Time Display..................] [Back]
    """

    # Button positions
    BTN_SKIP_BACK_5MIN = (0, 0)
    BTN_SKIP_BACK_1MIN = (0, 1)
    BTN_SEEK_START = (0, 2)
    BTN_SKIP_FWD_1MIN = (0, 3)
    BTN_SKIP_FWD_5MIN = (0, 4)

    BTN_VOL_DOWN = (1, 0)
    BTN_PAUSE = (1, 1)
    BTN_VOL_UP = (1, 2)

    BTN_TIME_DISPLAY = [(2, 0), (2, 1), (2, 2), (2, 3)]  # Multi-tile time display
    BTN_BACK = (2, 4)

    # How close to the duration the last reported position must be for playback
    # to count as "finished naturally". Position updates arrive every 100ms and
    # container/decoder durations can differ slightly from the decoded length.
    FINISH_TOLERANCE = 2.0  # seconds

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

        # Metadata service for position tracking
        self.metadata = AudioMetadataService.get_metadata(audio_file)
        self._last_position_save = 0  # Timestamp of last position save

        # Playback finish tracking.
        # The sound manager resets its position to 0 before reporting STOPPED,
        # so the last position seen via the position callback is what tells us
        # whether the track ran to the end.
        self._last_reported_position = 0.0
        self._finished = False  # Track played to the end (shows "Replay")
        self._auto_advance_pending = False  # Set by the callback, consumed by main_loop

    async def on_enter(self):
        """Initialize the scene and start playback."""
        logger.info(f"Entering Player Scene for {self.audio_file.name}")

        # Find cover art
        self.cover_art = find_cover_art(self.audio_file)

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

        # Update last play time in metadata
        self.metadata.set_last_play_time()

        # Resume from saved position if available (only if >= 10 minutes in)
        saved_position = self.metadata.get_playback_position()
        start_pos = 0.0
        if saved_position is not None and saved_position >= 600:
            start_pos = saved_position
            logger.info(f"Resuming playback from saved position: {saved_position:.1f}s")
        elif saved_position is not None and saved_position > 0:
            logger.info(f"Saved position {saved_position:.1f}s is less than 10 min, starting from beginning")

        # Start playback (with resume position if available)
        sound_mgr.play_music(self.audio_file, volume=self.current_volume, start_pos=start_pos)

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

        # Save current position before exiting (unless finished)
        sound_mgr = self.runtime.device.sound_manager
        if sound_mgr:
            position = sound_mgr.get_position()
            duration = sound_mgr.get_duration()
            status = sound_mgr.get_status()

            # Save unless we're at the very end (finished playback) or less than 10 min in
            if position >= 600 and not (duration > 0 and position >= duration - 1.0):
                self.metadata.set_playback_position(position)
                logger.info(f"Saved playback position on exit: {position:.1f}s (status: {status})")

            # Clear callbacks (but don't stop playback - let browser scene handle that)
            sound_mgr.set_status_callback(None)
            sound_mgr.set_position_callback(None)

    async def render_ui(self):
        """Render all player controls."""
        # Row 0: Skip controls using icon images
        self.set_tile_file(0, 0, ICON_SEEK_BACK_5MIN)
        self.set_tile_file(0, 1, ICON_SEEK_BACK_1MIN)
        self.set_tile_file(0, 2, ICON_SEEK_START)
        self.set_tile_file(0, 3, ICON_SEEK_FWD_1MIN)
        self.set_tile_file(0, 4, ICON_SEEK_FWD_5MIN)

        # Row 1: Volume, pause, and cover art
        self.set_tile_file(1, 0, ICON_VOLUME_DOWN)
        await self._update_pause_button()
        self.set_tile_file(1, 2, ICON_VOLUME_UP)

        # Show cover art if available, otherwise empty
        if self.cover_art:
            self.set_tile_file(1, 3, str(self.cover_art))
        else:
            self.set_tile_text(1, 3, "", font_size=13)

        self.set_tile_text(1, 4, "", font_size=13)  # Empty

        # Row 2: Time display and back button
        await self._update_time_display()
        self.set_tile_file(2, 4, ICON_BACK)

        self.submit_tiles()

    async def _update_pause_button(self):
        """Update pause/play button based on current state."""
        sound_mgr = self.runtime.device.sound_manager
        if not sound_mgr:
            return

        status = sound_mgr.get_status()
        if status == PlaybackStatus.PLAYING:
            self.set_tile_text(1, 1, "❚❚\nPause", font_size=15)
        elif status == PlaybackStatus.PAUSED:
            self.set_tile_text(1, 1, "▶\nPlay", font_size=17)
        elif self._finished:
            # Played to the end and no next file to advance to - offer replay
            self.set_tile_text(1, 1, "↻\nReplay", font_size=15)
        else:
            # Stopped for other reason
            self.set_tile_text(1, 1, "▶\nPlay", font_size=17)

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
        self.set_tile_text(2, 0, f"{pos_min}:{pos_sec:02d}", font_size=19)

        # ALWAYS update: Progress (2,2) - changes as position changes
        self.set_tile_text(2, 2, f"{progress:.0f}%", font_size=19)

        # Only update static tiles on first call or when forced
        if not self._static_tiles_initialized or force_all:
            # STATIC: Duration (2,1) - doesn't change after file starts
            self.set_tile_text(2, 1, f"{dur_min}:{dur_sec:02d}", font_size=19)

            # STATIC: Filename (2,3) - doesn't change
            filename = self.audio_file.stem
            self.set_tile_text(2, 3, filename, font_size=11, wrap=True)

            self._static_tiles_initialized = True
            logger.debug("Updated static tiles (duration, filename)")

    async def _show_error(self, message: str):
        """Show error message."""
        for row in range(3):
            for col in range(5):
                self.set_tile_text(row, col, "", font_size=13)

        self.set_tile_text(1, 2, message, font_size=17)
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

                # Save playback position every 30 seconds (only if playing and >= 10 min in)
                current_time = time.time()
                if status == PlaybackStatus.PLAYING:
                    if current_time - self._last_position_save >= 30:
                        if position >= 600:
                            self.metadata.set_playback_position(position)
                            logger.debug(f"Saved playback position: {position:.1f}s")
                        self._last_position_save = current_time

                await asyncio.sleep(1.0)  # Check once per second (time only changes every second)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                await asyncio.sleep(0.5)

    def _is_natural_finish(self) -> bool:
        """
        Check whether the STOPPED status we just received means the track ran out.

        A manual stop (Back button, seek, replay, leaving the scene) goes through
        SoundManager.stop(), which resets the duration to 0 before notifying. A
        track that ends by itself keeps its duration, so a non-zero duration plus
        a last reported position at the end identifies a natural finish.

        Returns:
            True if playback finished naturally
        """
        sound_mgr = self.runtime.device.sound_manager
        if not sound_mgr:
            return False

        duration = sound_mgr.get_duration()
        if duration <= 0:
            return False

        return self._last_reported_position >= duration - self.FINISH_TOLERANCE

    def on_status_change(self, status: PlaybackStatus):
        """
        Handle playback status changes.

        Called by the sound manager from its playback thread, so this only
        records state. Acting on it (switching scenes) happens in main_loop.
        """
        logger.debug(f"Playback status changed: {status}")

        if status != PlaybackStatus.STOPPED:
            return

        if not self._is_natural_finish():
            # Manual stop, seek or scene change - nothing to do
            return

        logger.info("Playback finished - clearing saved position")
        self._finished = True
        self.metadata.clear_playback_position()

        # Request auto-advance; main_loop picks this up on the event loop
        self._auto_advance_pending = True

    def on_position_update(self, position: float, duration: float):
        """Handle playback position updates."""
        # Remember the last position: the sound manager zeroes its own position
        # before reporting STOPPED, so this is our only end-of-track evidence.
        self._last_reported_position = position

    async def _auto_advance(self):
        """
        Advance to the next audio file in the folder after a natural finish.

        Switches to a fresh PlayerScene so metadata, cover art, static tiles and
        saved-position handling are set up for the new file by on_enter.
        If the current file is the last one, we stay here and show "Replay".
        """
        next_file = get_next_audio_file(self.audio_file)

        if next_file is None:
            logger.info(f"{self.audio_file.name} is the last file in the folder - not advancing")
            return

        logger.info(f"Auto-advancing to next file: {next_file.name}")
        self.switch_scene(PlayerScene, audio_file=next_file, return_dir=self.return_dir)

    async def on_key_press(self, row: int, col: int, long_press: bool = False):
        """Handle button press."""
        logger.debug(f"Button pressed: ({row}, {col}), long_press={long_press}")

        sound_mgr = self.runtime.device.sound_manager
        if not sound_mgr:
            return

        button = (row, col)

        # Skip controls (Row 0)
        if button == self.BTN_SKIP_BACK_5MIN:
            sound_mgr.seek(-300)  # -5 minutes
        elif button == self.BTN_SKIP_BACK_1MIN:
            sound_mgr.seek(-60)  # -1 minute
        elif button == self.BTN_SEEK_START:
            sound_mgr.seek(-sound_mgr.get_position())  # Go to start
        elif button == self.BTN_SKIP_FWD_1MIN:
            sound_mgr.seek(60)  # +1 minute
        elif button == self.BTN_SKIP_FWD_5MIN:
            sound_mgr.seek(300)  # +5 minutes

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
                self._finished = False
                self._auto_advance_pending = False
                self._last_reported_position = 0.0
                sound_mgr.stop()  # Ensure clean state
                sound_mgr.play_music(self.audio_file, volume=self.current_volume)
        elif button == self.BTN_VOL_UP:
            self.current_volume = min(SettingsManager.MAX_VOLUME, self.current_volume + 0.05)
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

        # Save current position BEFORE stopping playback
        sound_mgr = self.runtime.device.sound_manager
        if sound_mgr and sound_mgr.is_available():
            status = sound_mgr.get_status()
            if status in (PlaybackStatus.PLAYING, PlaybackStatus.PAUSED):
                position = sound_mgr.get_position()
                if position >= 600:
                    self.metadata.set_playback_position(position)
                    logger.info(f"Saved playback position before going back: {position:.1f}s")
                else:
                    logger.info(f"Position {position:.1f}s is less than 10 min, not saving")

            # Now stop playback
            sound_mgr.stop()

        # Switch to browser scene, passing the directory to return to
        self.switch_scene(AudioPlayerScene, start_dir=self.return_dir)

    async def main_loop(self):
        """Main scene loop."""
        logger.info("Player Scene main loop started")

        while self._running:
            # Track finished on its own - move on to the next file in the folder
            if self._auto_advance_pending:
                self._auto_advance_pending = False
                await self._auto_advance()

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
