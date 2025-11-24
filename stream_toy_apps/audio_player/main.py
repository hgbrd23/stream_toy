"""
Audio Player Scene - Browse and play audio files
"""

import asyncio
from pathlib import Path
from typing import List, Optional, Union
import logging

from stream_toy.scene.base_scene import BaseScene
from stream_toy.sound_manager import PlaybackStatus

logger = logging.getLogger(__name__)


class FileItem:
    """Represents a file or folder in the browser."""

    def __init__(self, path: Path, is_folder: bool):
        self.path = path
        self.is_folder = is_folder
        self.name = path.name

    def __repr__(self):
        return f"FileItem({self.name}, folder={self.is_folder})"


class AudioPlayerScene(BaseScene):
    """
    Audio player with folder browser.

    Layout:
    - Columns 0-3 (12 buttons): File/folder listing
    - Column 4 (3 buttons): Up, Down, Back navigation
    """

    # UI Layout
    LIST_COLS = 4  # Columns for file listing
    LIST_ROWS = 3  # Rows for file listing
    ITEMS_PER_PAGE = LIST_COLS * LIST_ROWS  # 12 items visible

    NAV_COL = 4  # Navigation column (rightmost)
    BTN_UP = 0  # Up button row
    BTN_DOWN = 1  # Down button row
    BTN_BACK_EXIT = 2  # Back/Exit button row (Back when in folder, Exit when at root)

    # Audio file extensions
    AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a'}

    # Image file extensions for cover art
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}

    def __init__(self, runtime, start_dir: Optional[Path] = None):
        super().__init__(runtime)

        # Data directory
        self.data_root = Path(__file__).parent.parent.parent / "data" / "audio_player"

        # Navigation state
        self.current_dir = start_dir if start_dir else self.data_root
        self.items: List[FileItem] = []
        self.scroll_offset = 0  # Current scroll position

        # Playback state
        self.current_file: Optional[Path] = None
        self.playing_button: Optional[int] = None  # Button index currently playing

    async def on_enter(self):
        """Initialize the scene."""
        logger.info("Entering Audio Player")

        # Ensure data directory exists
        self.data_root.mkdir(parents=True, exist_ok=True)

        # Set up audio callbacks
        sound_mgr = self.runtime.device.sound_manager
        if sound_mgr:
            sound_mgr.set_status_callback(self.on_status_change)
            sound_mgr.set_position_callback(self.on_position_update)

        # Load current directory
        await self.load_directory(self.current_dir)

    async def on_exit(self):
        """Cleanup when leaving scene."""
        logger.info("Exiting Audio Player")

        # Clear audio callbacks
        sound_mgr = self.runtime.device.sound_manager
        if sound_mgr:
            sound_mgr.set_status_callback(None)
            sound_mgr.set_position_callback(None)
            sound_mgr.stop()

    async def load_directory(self, path: Path):
        """
        Load and display directory contents.

        Args:
            path: Directory path to load
        """
        logger.info(f"Loading directory: {path}")

        self.current_dir = path
        self.items = []
        self.scroll_offset = 0

        # Scan directory
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))

            for entry in entries:
                if entry.is_dir():
                    # Add folder
                    self.items.append(FileItem(entry, is_folder=True))
                elif entry.is_file() and entry.suffix.lower() in self.AUDIO_EXTENSIONS:
                    # Add audio file
                    self.items.append(FileItem(entry, is_folder=False))

        except Exception as e:
            logger.error(f"Error loading directory {path}: {e}")

        # Update display
        await self.update_display()

    async def update_display(self):
        """Update button display with current items and navigation."""
        # Clear all tiles first
        for row in range(self.LIST_ROWS):
            for col in range(5):  # All columns
                self.set_tile_text(row, col, "", font_size=13)

        # Display items (columns 0-3)
        visible_items = self.items[self.scroll_offset:self.scroll_offset + self.ITEMS_PER_PAGE]

        for idx, item in enumerate(visible_items):
            row = idx // self.LIST_COLS
            col = idx % self.LIST_COLS

            # Get filename without extension
            name_stem = Path(item.name).stem

            # Determine display text and color
            if item.is_folder:
                # Folder: show name with folder icon (Font Awesome folder from Nerd Font)
                text = f"\uf07b\n{name_stem}"
                self.set_tile_text(row, col, text, font_size=11, wrap=True)
            else:
                # Audio file: check for cover art
                audio_path = item.path
                cover_art = self.find_cover_art(audio_path)

                # Determine text
                text = f"♪\n{name_stem}"

                # Highlight if currently playing
                button_idx = self.scroll_offset + idx
                if button_idx == self.playing_button:
                    sound_mgr = self.runtime.device.sound_manager
                    if sound_mgr and sound_mgr.get_status() == PlaybackStatus.PLAYING:
                        text = f"▶\n{name_stem}"

                # Use cover art if available, otherwise text only
                if cover_art:
                    self.set_tile_image_with_text(row, col, str(cover_art), text, font_size=11, wrap=True)
                else:
                    self.set_tile_text(row, col, text, font_size=11, wrap=True)

        # Navigation buttons (column 4) - smaller font for nav
        # Up button
        if self.scroll_offset > 0:
            self.set_tile_text(self.BTN_UP, self.NAV_COL, "▲\nUp", font_size=17)
        else:
            self.set_tile_text(self.BTN_UP, self.NAV_COL, "", font_size=13)

        # Down button
        if self.scroll_offset + self.ITEMS_PER_PAGE < len(self.items):
            self.set_tile_text(self.BTN_DOWN, self.NAV_COL, "▼\nDown", font_size=17)
        else:
            self.set_tile_text(self.BTN_DOWN, self.NAV_COL, "", font_size=13)

        # Back/Exit button (bottom right)
        if self.current_dir != self.data_root:
            # In a folder - show Back button
            self.set_tile_text(self.BTN_BACK_EXIT, self.NAV_COL, "←\nBack", font_size=17)
        else:
            # At root - show Exit button
            self.set_tile_text(self.BTN_BACK_EXIT, self.NAV_COL, "✕\nExit", font_size=17)

        # Submit all changes
        self.submit_tiles()

        # Log current state
        logger.debug(f"Display updated: {len(self.items)} items, offset={self.scroll_offset}")

    def find_cover_art(self, audio_file: Path) -> Optional[Path]:
        """
        Find cover art image for an audio file.

        Looks for an image file with the same name as the audio file.

        Args:
            audio_file: Path to audio file

        Returns:
            Path to cover art image, or None if not found
        """
        # Get the stem (filename without extension)
        stem = audio_file.stem

        # Check for image files with same name
        for ext in self.IMAGE_EXTENSIONS:
            cover_path = audio_file.parent / f"{stem}{ext}"
            if cover_path.exists():
                logger.debug(f"Found cover art: {cover_path}")
                return cover_path

        return None

    async def on_key_press(self, row: int, col: int, long_press: bool = False):
        """
        Handle button press.

        Args:
            row: Button row (0-2)
            col: Button column (0-4)
            long_press: True if this was a long press
        """
        logger.debug(f"Button pressed: ({row}, {col}), long_press={long_press}")

        # Navigation buttons (column 4)
        if col == self.NAV_COL:
            if row == self.BTN_UP:
                await self.scroll_up()
            elif row == self.BTN_DOWN:
                await self.scroll_down()
            elif row == self.BTN_BACK_EXIT:
                if self.current_dir != self.data_root:
                    # In a folder
                    if long_press:
                        # Long press - exit to app selection
                        await self.exit_to_launcher()
                    else:
                        # Normal press - go back to parent folder
                        await self.go_back()
                else:
                    # At root - exit to app selection
                    await self.exit_to_launcher()
            return

        # File/folder buttons (columns 0-3)
        button_idx = row * self.LIST_COLS + col
        item_idx = self.scroll_offset + button_idx

        if item_idx < len(self.items):
            item = self.items[item_idx]

            if item.is_folder:
                # Navigate into folder
                await self.load_directory(item.path)
            else:
                # Play audio file
                await self.play_file(item.path, button_idx)

    async def scroll_up(self):
        """Scroll list up (show earlier items)."""
        if self.scroll_offset > 0:
            self.scroll_offset = max(0, self.scroll_offset - self.ITEMS_PER_PAGE)
            await self.update_display()
            logger.debug(f"Scrolled up to offset {self.scroll_offset}")

    async def scroll_down(self):
        """Scroll list down (show later items)."""
        max_offset = max(0, len(self.items) - self.ITEMS_PER_PAGE)
        if self.scroll_offset < max_offset:
            self.scroll_offset = min(max_offset, self.scroll_offset + self.ITEMS_PER_PAGE)
            await self.update_display()
            logger.debug(f"Scrolled down to offset {self.scroll_offset}")

    async def go_back(self):
        """Navigate to parent directory."""
        if self.current_dir != self.data_root:
            parent = self.current_dir.parent
            await self.load_directory(parent)
            logger.debug(f"Navigated back to {parent}")

    async def exit_to_launcher(self):
        """Exit audio player and return to module launcher."""
        logger.info("Exiting to module launcher")

        # Import here to avoid circular dependency
        from stream_toy.scene.module_launch_scene import ModuleLaunchScene

        # Stop any playing audio
        sound_mgr = self.runtime.device.sound_manager
        if sound_mgr:
            sound_mgr.stop()

        # Switch to launcher
        self.switch_scene(ModuleLaunchScene)

    async def play_file(self, file_path: Path, button_idx: int):
        """
        Launch player scene for audio file.

        Args:
            file_path: Path to audio file
            button_idx: Button index (for tracking which is playing)
        """
        sound_mgr = self.runtime.device.sound_manager
        if not sound_mgr or not sound_mgr.is_available():
            logger.warning("Sound manager not available")
            # Show error message
            self.set_tile_text(1, 1, "Audio\nNot\nAvail", font_size=15)
            self.submit_tiles()
            await asyncio.sleep(2)
            await self.update_display()
            return

        # Import here to avoid circular dependency
        from .player_scene import PlayerScene

        logger.info(f"Launching player for: {file_path.name}")

        # Switch to player scene, pass current directory to return to
        self.switch_scene(PlayerScene, audio_file=file_path, return_dir=self.current_dir)

    def on_status_change(self, status: PlaybackStatus):
        """
        Handle playback status changes.

        Args:
            status: New playback status
        """
        logger.debug(f"Playback status changed: {status}")

        if status == PlaybackStatus.STOPPED:
            # Playback finished
            self.current_file = None
            self.playing_button = None

            # Update display (remove play indicator)
            asyncio.create_task(self.update_display())

    def on_position_update(self, position: float, duration: float):
        """
        Handle playback position updates.

        Args:
            position: Current position in seconds
            duration: Total duration in seconds
        """
        # Could update a progress display here if desired
        pass

    async def on_key_release(self, row: int, col: int):
        """Handle button release (not used currently)."""
        pass

    async def main_loop(self):
        """Main scene loop."""
        logger.info("Audio Player main loop started")

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

        logger.info("Audio Player main loop ended")
