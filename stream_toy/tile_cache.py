"""
On-disk cache of device-ready tile and background images.

Source images (module icons, scene tile renders, cover art) can be any size
and format - the shipped icons are 1024x1024 PNGs of about 2 MB each. Both
devices need a small derived image per source:

* the StreamDock wants a 112x112 JPEG rotated by 180 degrees (quality 85,
  larger files corrupt on the device, see CLAUDE.md),
* the web emulator wants a 112x112 PNG it can send to the browser as-is.

Deriving these on every draw costs about a quarter of a second per icon on the
Pi Zero 2 W, so they are cached in ``data/cache/button_tiles``. ``data`` is
excluded from the deploy rsync, so the cache survives updates. Cache files are
keyed by the source path and refreshed when the source is newer.

Tiles rendered in memory by scenes (text, solid colours, cover + title
composites) are stored once, directly as the device JPEG via
``save_native_key_jpeg``. Such a file is recognised by its ``_native.jpg``
suffix: the device sends it as-is and the browser PNG is derived from it by
rotating back, so a new text tile costs one encode and one SD write.
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Tuple, Union

from PIL import Image

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "button_tiles"

TILE_SIZE = (112, 112)
BACKGROUND_SIZE = (800, 480)
ROTATION = 180

# Quality 85 is mandatory for key tiles (CLAUDE.md). Backgrounds keep PIL's
# default (75), which is what the SDK's own set_touchscreen_image produces.
KEY_JPEG_QUALITY = 85

# Suffix of a file that already is a device-ready key tile (rotated JPEG)
NATIVE_SUFFIX = '_native.jpg'


def cache_path_for(source: Union[str, Path], suffix: str) -> Path:
    """Cache file for a source image: ``<stem>_<hash of absolute path><suffix>``."""
    source = Path(source).resolve()
    digest = hashlib.md5(str(source).encode('utf-8')).hexdigest()[:12]
    return CACHE_DIR / f"{source.stem}_{digest}{suffix}"


def is_fresh(cache_path: Path, source: Path) -> bool:
    """True if the cache file exists, is non-empty and not older than the source."""
    try:
        cache_stat = cache_path.stat()
    except OSError:
        return False
    if cache_stat.st_size == 0:
        # Interrupted write; the device silently drops empty JPEGs
        logger.warning(f"Empty cache file, regenerating: {cache_path.name}")
        return False
    return cache_stat.st_mtime >= source.stat().st_mtime


def atomic_save(image: Image.Image, cache_path: Path, **save_kwargs) -> None:
    """Save via a temp file + rename so a crash never leaves a truncated cache file."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = cache_path.parent / f".tmp_{os.getpid()}_{cache_path.name}"
    try:
        image.save(tmp_path, **save_kwargs)
        os.replace(tmp_path, cache_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def to_native_format(image: Image.Image, size: Tuple[int, int]) -> Image.Image:
    """Rotate by 180 degrees, resize and convert to RGB for the device (SDK logic)."""
    expand = not (image.size[1] == size[0] and image.size[0] == size[1])
    image = image.rotate(ROTATION, expand=expand)
    if image.size != size:
        image = image.resize(size, Image.LANCZOS)
    return image.convert('RGB')


def is_native_key_jpeg(path: Union[str, Path]) -> bool:
    """True if the file was written by save_native_key_jpeg (or native_key_jpeg)."""
    return Path(path).name.endswith(NATIVE_SUFFIX)


def save_native_key_jpeg(image: Image.Image, cache_path: Path) -> None:
    """
    Store an in-memory tile (display orientation) as a device-ready key JPEG.

    ``cache_path`` must end in NATIVE_SUFFIX so the devices recognise it.
    """
    if not is_native_key_jpeg(cache_path):
        raise ValueError(f"Native tile cache files must end in {NATIVE_SUFFIX}: {cache_path.name}")
    atomic_save(to_native_format(image, TILE_SIZE), cache_path,
                format='JPEG', quality=KEY_JPEG_QUALITY)


def _derive(source: Union[str, Path], suffix: str, convert, **save_kwargs) -> Path:
    source = Path(source)
    cache_path = cache_path_for(source, suffix)
    if is_fresh(cache_path, source):
        return cache_path

    logger.info(f"Generating cache: {source.name} -> {cache_path.name}")
    with Image.open(source) as image:
        image.load()
        derived = convert(image)
    atomic_save(derived, cache_path, **save_kwargs)
    return cache_path


def native_key_jpeg(source: Union[str, Path]) -> Path:
    """Device-ready 112x112 JPEG for a key tile: the source itself if it already is one, else cached."""
    source = Path(source)
    if is_native_key_jpeg(source):
        return source
    return _derive(source, NATIVE_SUFFIX,
                   lambda img: to_native_format(img, TILE_SIZE),
                   format='JPEG', quality=KEY_JPEG_QUALITY)


def native_background_jpeg(source: Union[str, Path]) -> Path:
    """Device-ready 800x480 JPEG for the background (cached)."""
    return _derive(source, '_background.jpg',
                   lambda img: to_native_format(img, BACKGROUND_SIZE),
                   format='JPEG')


def _is_tile_sized_png(source: Path) -> bool:
    """True if the source can be sent to the browser without conversion."""
    if source.suffix.lower() != '.png':
        return False
    try:
        with Image.open(source) as image:
            return image.size == TILE_SIZE
    except Exception:
        return False


def _to_web_format(image: Image.Image, rotate_back: bool) -> Image.Image:
    image = image.convert('RGB')
    if rotate_back:
        # Native tiles are stored rotated for the device; undo that for the browser
        image = image.rotate(ROTATION)
    if image.size != TILE_SIZE:
        image = image.resize(TILE_SIZE, Image.LANCZOS)
    return image


def web_png(source: Union[str, Path]) -> Path:
    """112x112 PNG for the browser: the source itself when it already is one, else cached."""
    source = Path(source)
    if _is_tile_sized_png(source):
        return source
    rotate_back = is_native_key_jpeg(source)
    return _derive(source, '_web.png',
                   lambda img: _to_web_format(img, rotate_back),
                   format='PNG')


def prewarm(sources, native: bool = True, web: bool = True) -> int:
    """Generate missing cache files for many sources. Returns the number generated."""
    generated = 0
    for source in sources:
        source = Path(source)
        if not source.is_file():
            continue
        try:
            for enabled, derive, suffix in (
                (native, native_key_jpeg, NATIVE_SUFFIX),
                (web, web_png, '_web.png'),
            ):
                if enabled and not is_fresh(cache_path_for(source, suffix), source):
                    derive(source)
                    generated += 1
        except Exception as e:
            logger.warning(f"Could not prewarm cache for {source.name}: {e}")
    return generated
