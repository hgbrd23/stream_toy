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
import hashlib

if TYPE_CHECKING:
    from ..runtime import StreamToyRuntime

logger = logging.getLogger(__name__)


# Module-level font cache to avoid reloading fonts
_FONT_CACHE: Dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}


class BaseScene(ABC):
    """
    Abstract base class for all scenes.

    Scenes represent different states/screens in the application,
    such as menus, games, or settings screens.
    """

    # Cache directory for generated tile images
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "scene_tiles"

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

        # Ensure cache directory exists
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

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

    def _get_cache_path(self, cache_key: str) -> Path:
        """
        Get the file path for a cached image.

        Args:
            cache_key: Unique identifier for the image

        Returns:
            Path where the cached image should be stored
        """
        # Sanitize first 30 chars for readability
        prefix = "".join(c if c.isalnum() or c in "._-" else "_" for c in cache_key[:30])

        # Hash complete cache key for uniqueness
        key_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()[:12]

        # Combine: prefix + hash
        filename = f"{prefix}_{key_hash}.png"
        return self.CACHE_DIR / filename

    def _is_cached(self, cache_key: str) -> bool:
        """
        Check if an image is already cached on disk.

        Args:
            cache_key: Unique identifier for the image

        Returns:
            True if cache file exists, False otherwise
        """
        cache_path = self._get_cache_path(cache_key)
        return cache_path.exists()

    def _cache_image(self, cache_key: str, image: Image.Image) -> Path:
        """
        Save a PIL Image to the file cache.

        Args:
            cache_key: Unique identifier for the image
            image: PIL Image to cache

        Returns:
            Path to the cached file
        """
        cache_path = self._get_cache_path(cache_key)

        # Save to cache if not already there
        if not cache_path.exists():
            image.save(cache_path, format='PNG')
            logger.debug(f"Cached image to: {cache_path.name}")

        return cache_path

    def _get_font(self, font_size: int) -> ImageFont.FreeTypeFont:
        """
        Get a cached font object or load it.

        Args:
            font_size: Font size in points

        Returns:
            Font object
        """
        global _FONT_CACHE

        # Check cache first
        noto_dir = Path(__file__).parent.parent.parent / "assets" / "fonts" / "Noto_Sans"
        font_path = str(noto_dir / "NotoSans-Bold.ttf")

        cache_key = (font_path, font_size)
        if cache_key in _FONT_CACHE:
            return _FONT_CACHE[cache_key]

        # Not in cache, load font
        font_paths = [
            str(noto_dir / "NotoSans-Bold.ttf"),
            str(noto_dir / "NotoSans-Regular.ttf"),
            str(noto_dir / "NotoSans-Medium.ttf"),
        ]

        font = None
        for path in font_paths:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, font_size)
                    cache_key = (path, font_size)
                    _FONT_CACHE[cache_key] = font
                    logger.debug(f"Loaded and cached font: {Path(path).name} size {font_size}")
                    return font
                except Exception:
                    continue

        # Fallback to default font
        if font is None:
            font = ImageFont.load_default()
            logger.warning("Using default font, Noto Sans fonts not found")

        return font

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
        # Generate cache key based on all parameters that affect the output
        cache_key = f"text|{text}|fs{font_size}|fg{fg_color}|bg{bg_color}|w{wrap}|ts{self.device.TILE_SIZE}"

        # Check if we have this image cached
        if self._is_cached(cache_key):
            cache_path = self._get_cache_path(cache_key)
            logger.debug(f"Using cached text image: {cache_path.name}")
            self.device.set_tile(row, col, cache_path, cache_key=cache_key)
            return

        # Image not cached, generate it
        img = Image.new('RGB', (self.device.TILE_SIZE, self.device.TILE_SIZE), bg_color)
        draw = ImageDraw.Draw(img)

        # Get cached font (much faster than reloading)
        font = self._get_font(font_size)

        # Fast path for simple text without wrapping (common case for time display, etc.)
        # Skip expensive text measurement if wrapping is disabled
        if not wrap:
            lines = text.split('\n')
        else:
            # Handle wrapping and multi-line text
            if max_width is None:
                max_width = int(self.device.TILE_SIZE * 0.9)

            lines = []

            # Split by existing newlines first
            text_lines = text.split('\n')

            for line in text_lines:
                if line:
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

        # Cache the generated image to file and send path to device
        cache_path = self._cache_image(cache_key, img)
        self.device.set_tile(row, col, cache_path, cache_key=cache_key)

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

        # Generate cache key based on SVG path and tile size
        cache_key = f"svg|{svg_path}|ts{self.device.TILE_SIZE}"

        # Check if we have this image cached
        if self._is_cached(cache_key):
            cache_path = self._get_cache_path(cache_key)
            logger.debug(f"Using cached SVG image: {cache_path.name}")
            self.device.set_tile(row, col, cache_path, cache_key=cache_key)
            return

        # Image not cached, generate it
        png_data = svg2png(
            url=svg_path,
            output_width=self.device.TILE_SIZE,
            output_height=self.device.TILE_SIZE
        )
        img = Image.open(BytesIO(png_data))

        # Cache the generated image to file and send path to device
        cache_path = self._cache_image(cache_key, img)
        self.device.set_tile(row, col, cache_path, cache_key=cache_key)

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

        # Generate a cache key based on image data hash (for uncached PIL Images)
        import hashlib
        img_bytes = image.tobytes()
        img_hash = hashlib.md5(img_bytes).hexdigest()[:16]
        cache_key = f"img|{img_hash}|ts{self.device.TILE_SIZE}"

        # Cache to file and send path to device
        cache_path = self._cache_image(cache_key, image)
        self.device.set_tile(row, col, cache_path, cache_key=cache_key)

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

        # Generate cache key from file path
        cache_key = f"file|{image_path}"

        # Pass the file path directly to the device
        self.device.set_tile(row, col, image_path, cache_key=cache_key)

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

        # Generate cache key based on image path and text overlay parameters
        cache_key = f"img_text|{image_path}|{text}|fs{font_size}|fg{fg_color}|op{bg_opacity}|ts{self.device.TILE_SIZE}"

        # Check if we have this image cached
        if self._is_cached(cache_key):
            cache_path = self._get_cache_path(cache_key)
            logger.debug(f"Using cached image+text: {cache_path.name}")
            self.device.set_tile(row, col, cache_path, cache_key=cache_key)
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

        # Cache the generated image to file and send path to device
        cache_path = self._cache_image(cache_key, img)
        self.device.set_tile(row, col, cache_path, cache_key=cache_key)

    def clear_tile(self, row: int, col: int, color: str = "black") -> None:
        """
        Clear a tile to a solid color.

        Args:
            row: Tile row (0-2)
            col: Tile column (0-4)
            color: Color name or hex
        """
        # Generate cache key for solid color tiles
        cache_key = f"color|{color}|ts{self.device.TILE_SIZE}"

        # Check if we have this cached
        if self._is_cached(cache_key):
            cache_path = self._get_cache_path(cache_key)
            logger.debug(f"Using cached color tile: {cache_path.name}")
            self.device.set_tile(row, col, cache_path, cache_key=cache_key)
            return

        # Generate and cache
        img = Image.new('RGB', (self.device.TILE_SIZE, self.device.TILE_SIZE), color)
        cache_path = self._cache_image(cache_key, img)
        self.device.set_tile(row, col, cache_path, cache_key=cache_key)

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
