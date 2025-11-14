"""
Base scene class for StreamToy applications.

Provides common functionality for all scenes including tile management,
input handling, and scene transitions.
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple, Optional, TYPE_CHECKING
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
        bg_color: str = "black"
    ) -> None:
        """
        Render text to a tile.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            text: Text to render
            font_size: Font size in points
            fg_color: Text color (name or hex)
            bg_color: Background color (name or hex)
        """
        img = Image.new('RGB', (self.device.TILE_SIZE, self.device.TILE_SIZE), bg_color)
        draw = ImageDraw.Draw(img)

        # Try to load a nice font, fall back to default
        font = None
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
            "C:\\Windows\\Fonts\\arial.ttf",  # Windows
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
            logger.warning("Using default font, system fonts not found")

        # Center text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (self.device.TILE_SIZE - text_width) // 2
        y = (self.device.TILE_SIZE - text_height) // 2

        draw.text((x, y), text, fill=fg_color, font=font)
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
