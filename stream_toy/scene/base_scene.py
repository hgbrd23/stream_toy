"""
Base scene class for StreamToy applications.

Provides common functionality for all scenes including tile management,
input handling, and scene transitions.
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple, Optional, TYPE_CHECKING
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import asyncio
import logging
import os

if TYPE_CHECKING:
    from ..runtime import StreamToyRuntime

logger = logging.getLogger(__name__)


class BaseScene(ABC):
    """
    Abstract base class for all scenes.

    Scenes represent different states/screens in the application,
    such as menus, games, or settings screens.
    """

    def __init__(self, runtime: 'StreamToyRuntime'):
        """
        Initialize the scene.

        Args:
            runtime: Reference to the StreamToyRuntime instance
        """
        self.runtime = runtime
        self.device = runtime.device
        self.input_manager = runtime.input_manager
        self._running = False
        self._tile_cache: Dict[Tuple[int, int], Image.Image] = {}

    @abstractmethod
    async def on_enter(self) -> None:
        """
        Called when scene becomes active.

        Override this to initialize scene state, load assets,
        and render initial display.
        """
        pass

    @abstractmethod
    async def on_exit(self) -> None:
        """
        Called when scene becomes inactive.

        Override this to cleanup resources and save state.
        """
        pass

    @abstractmethod
    async def main_loop(self) -> None:
        """
        Main async loop for the scene.

        This is where the scene processes input and updates its state.
        The loop should respect self._running flag.

        Example:
            while self._running:
                event = await self.input_manager.async_poll_event()
                if event:
                    self.handle_event(event)
        """
        pass

    def set_tile_text(
        self,
        row: int,
        col: int,
        text: str,
        font_size: int = 24,
        fg_color: str = "white",
        bg_color: str = "black",
        wrap: bool = False,
        max_width: Optional[int] = None
    ) -> None:
        """
        Render text to a tile.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            text: Text to render (use \\n for manual line breaks)
            font_size: Font size in points
            fg_color: Text color (name or hex)
            bg_color: Background color (name or hex)
            wrap: Auto-wrap text to fit tile width
            max_width: Maximum text width before wrapping (default: 90% of tile size)
        """
        img = Image.new('RGB', (self.device.TILE_SIZE, self.device.TILE_SIZE), bg_color)
        draw = ImageDraw.Draw(img)

        # Try to load a nice font, fall back to default
        # Use Noto Sans fonts which have excellent Unicode/emoji support
        font = None
        # Path relative to this file: /workspace/stream_toy/scene/base_scene.py
        # Fonts are at: /workspace/assets/fonts/Noto_Sans/
        noto_dir = Path(__file__).parent.parent.parent / "assets" / "fonts" / "Noto_Sans"
        font_paths = [
            str(noto_dir / "NotoSans-Bold.ttf"),
            str(noto_dir / "NotoSans-Regular.ttf"),
            str(noto_dir / "NotoSans-Medium.ttf"),
        ]

        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except Exception:
                    continue

        if font is None:
            font = ImageFont.load_default()
            logger.warning("Using default font, Noto Sans fonts not found")

        # Handle wrapping and multi-line text
        if max_width is None:
            max_width = int(self.device.TILE_SIZE * 0.9)

        lines = []

        # Split by existing newlines first
        text_lines = text.split('\n')

        for line in text_lines:
            if wrap and line:
                # Auto-wrap long lines
                # First try word wrapping (split by spaces)
                words = line.split(' ') if ' ' in line else [line]
                current_line = ''

                for word in words:
                    test_line = f"{current_line} {word}".strip()
                    bbox = draw.textbbox((0, 0), test_line, font=font)
                    width = bbox[2] - bbox[0]

                    if width <= max_width:
                        current_line = test_line
                    else:
                        # Word doesn't fit, need to break it up
                        if current_line:
                            lines.append(current_line)
                            current_line = ''

                        # Check if word itself is too long (no spaces, long filename)
                        bbox_word = draw.textbbox((0, 0), word, font=font)
                        word_width = bbox_word[2] - bbox_word[0]

                        if word_width > max_width:
                            # Word is too long, break it character by character
                            for char in word:
                                test_line = current_line + char
                                bbox = draw.textbbox((0, 0), test_line, font=font)
                                width = bbox[2] - bbox[0]

                                if width <= max_width:
                                    current_line = test_line
                                else:
                                    if current_line:
                                        lines.append(current_line)
                                    current_line = char
                        else:
                            # Word fits on its own line
                            current_line = word

                if current_line:
                    lines.append(current_line)
            else:
                lines.append(line)

        # Calculate total text height
        line_height = font_size + 2  # Small spacing between lines
        total_height = len(lines) * line_height

        # Start Y position (centered vertically)
        y = (self.device.TILE_SIZE - total_height) // 2

        # Draw each line centered horizontally
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (self.device.TILE_SIZE - text_width) // 2

            draw.text((x, y), line, fill=fg_color, font=font)
            y += line_height

        self.set_tile_image(row, col, img)

    def set_tile_svg(self, row: int, col: int, svg_path: str) -> None:
        """
        Render SVG to a tile.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            svg_path: Path to SVG file

        Raises:
            ImportError: If cairosvg not installed
            FileNotFoundError: If SVG file not found
        """
        try:
            from cairosvg import svg2png
            from io import BytesIO
        except ImportError:
            logger.error("cairosvg not installed, cannot render SVG")
            self.set_tile_text(row, col, "SVG", font_size=16)
            return

        if not os.path.exists(svg_path):
            raise FileNotFoundError(f"SVG file not found: {svg_path}")

        png_data = svg2png(
            url=svg_path,
            output_width=self.device.TILE_SIZE,
            output_height=self.device.TILE_SIZE
        )
        img = Image.open(BytesIO(png_data))
        self.set_tile_image(row, col, img)

    def set_tile_image(self, row: int, col: int, image: Image.Image) -> None:
        """
        Set a tile to a PIL image.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            image: PIL Image (will be resized if needed)
        """
        # Resize if needed
        if image.size != (self.device.TILE_SIZE, self.device.TILE_SIZE):
            image = image.resize((self.device.TILE_SIZE, self.device.TILE_SIZE), Image.LANCZOS)

        self._tile_cache[(row, col)] = image
        self.device.set_tile(row, col, image)

    def set_tile_file(self, row: int, col: int, image_path: str) -> None:
        """
        Load and set tile from file.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            image_path: Path to image file

        Raises:
            FileNotFoundError: If image file not found
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        img = Image.open(image_path)
        self.set_tile_image(row, col, img)

    def set_tile_image_with_text(
        self,
        row: int,
        col: int,
        image_path: str,
        text: str,
        font_size: int = 10,
        fg_color: str = "white",
        bg_opacity: float = 0.7,
        wrap: bool = True
    ) -> None:
        """
        Set a tile to an image with overlayed text.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            image_path: Path to background image
            text: Text to overlay
            font_size: Font size for text
            fg_color: Text color
            bg_opacity: Background opacity for text area (0.0-1.0)
            wrap: Auto-wrap text to fit tile width
        """
        if not os.path.exists(image_path):
            # Fallback to text-only if image not found
            self.set_tile_text(row, col, text, font_size=font_size, fg_color=fg_color, wrap=wrap)
            return

        # Load and resize image
        img = Image.open(image_path)
        if img.size != (self.device.TILE_SIZE, self.device.TILE_SIZE):
            img = img.resize((self.device.TILE_SIZE, self.device.TILE_SIZE), Image.LANCZOS)

        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Create a semi-transparent overlay for text background
        overlay = Image.new('RGBA', (self.device.TILE_SIZE, self.device.TILE_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Add semi-transparent black background at bottom for text
        bg_alpha = int(255 * bg_opacity)
        draw.rectangle([(0, self.device.TILE_SIZE - 40), (self.device.TILE_SIZE, self.device.TILE_SIZE)],
                      fill=(0, 0, 0, bg_alpha))

        # Convert overlay to RGB and composite
        img = img.convert('RGBA')
        img = Image.alpha_composite(img, overlay)
        img = img.convert('RGB')

        # Draw text on top
        draw = ImageDraw.Draw(img)

        # Load font
        # Use Noto Sans fonts which have excellent Unicode/emoji support
        font = None
        # Path relative to this file: /workspace/stream_toy/scene/base_scene.py
        # Fonts are at: /workspace/assets/fonts/Noto_Sans/
        noto_dir = Path(__file__).parent.parent.parent / "assets" / "fonts" / "Noto_Sans"
        font_paths = [
            str(noto_dir / "NotoSans-Bold.ttf"),
            str(noto_dir / "NotoSans-Regular.ttf"),
            str(noto_dir / "NotoSans-Medium.ttf"),
        ]

        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except Exception:
                    continue

        if font is None:
            font = ImageFont.load_default()

        # Wrap text if needed
        max_width = int(self.device.TILE_SIZE * 0.9)
        lines = []
        text_lines = text.split('\n')

        for line in text_lines:
            if wrap and line:
                words = line.split(' ') if ' ' in line else [line]
                current_line = ''

                for word in words:
                    test_line = f"{current_line} {word}".strip()
                    bbox = draw.textbbox((0, 0), test_line, font=font)
                    width = bbox[2] - bbox[0]

                    if width <= max_width:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                            current_line = ''

                        bbox_word = draw.textbbox((0, 0), word, font=font)
                        word_width = bbox_word[2] - bbox_word[0]

                        if word_width > max_width:
                            for char in word:
                                test_line = current_line + char
                                bbox = draw.textbbox((0, 0), test_line, font=font)
                                width = bbox[2] - bbox[0]

                                if width <= max_width:
                                    current_line = test_line
                                else:
                                    if current_line:
                                        lines.append(current_line)
                                    current_line = char
                        else:
                            current_line = word

                if current_line:
                    lines.append(current_line)
            else:
                lines.append(line)

        # Draw text at bottom
        line_height = font_size + 2
        y_start = self.device.TILE_SIZE - 5 - (len(lines) * line_height)

        for i, line in enumerate(lines):
            if line:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                x = (self.device.TILE_SIZE - text_width) // 2
                y = y_start + (i * line_height)
                draw.text((x, y), line, fill=fg_color, font=font)

        self.set_tile_image(row, col, img)

    def clear_tile(self, row: int, col: int, color: str = "black") -> None:
        """
        Clear a tile to a solid color.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            color: Color name or hex
        """
        img = Image.new('RGB', (self.device.TILE_SIZE, self.device.TILE_SIZE), color)
        self.set_tile_image(row, col, img)

    def clear_all_tiles(self, color: str = "black") -> None:
        """
        Clear all tiles to a solid color.

        Args:
            color: Color name or hex
        """
        for row in range(self.device.TILE_ROWS):
            for col in range(self.device.TILE_COLS):
                self.clear_tile(row, col, color)

    def submit_tiles(self) -> None:
        """Submit all queued tile updates to device."""
        self.device.submit()

    def switch_scene(self, scene_class: type, **kwargs) -> None:
        """
        Request scene transition.

        Args:
            scene_class: Class of the scene to switch to
            **kwargs: Arguments to pass to scene constructor
        """
        self.runtime.switch_scene(scene_class, **kwargs)

    async def safe_sleep(self, duration: float) -> bool:
        """
        Sleep while respecting scene running state.

        Args:
            duration: Duration in seconds

        Returns:
            True if sleep completed, False if interrupted
        """
        end_time = asyncio.get_event_loop().time() + duration
        while self._running and asyncio.get_event_loop().time() < end_time:
            await asyncio.sleep(0.1)
        return self._running
