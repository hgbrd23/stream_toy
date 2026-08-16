"""
Shared audio file enumeration helpers for the audio player app.

The browser scene (main.py) and the player scene (player_scene.py) must agree on
which files count as audio, how a folder is sorted and which image belongs to an
audio file. All of that lives here so "the next file" always matches what the
user sees in the browser listing.
"""

from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

# Audio file extensions shown in the browser and used for playback
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a'}

# Image file extensions used as cover art
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}


def is_audio_file(path: Path) -> bool:
    """
    Check whether a path points to a supported audio file.

    Args:
        path: Path to check

    Returns:
        True if the path is a file with a supported audio extension
    """
    return path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS


def list_directory_entries(directory: Path) -> List[Path]:
    """
    List folders and audio files of a directory in browser order.

    Folders come first, then audio files, each sorted case-insensitively by name.
    Everything else (cover art, metadata files, ...) is filtered out.

    Args:
        directory: Directory to scan

    Returns:
        Ordered list of paths, empty if the directory cannot be read
    """
    try:
        entries = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError as e:
        logger.error(f"Error loading directory {directory}: {e}")
        return []

    return [entry for entry in entries if entry.is_dir() or is_audio_file(entry)]


def list_audio_files(directory: Path) -> List[Path]:
    """
    List only the audio files of a directory, in browser order.

    Args:
        directory: Directory to scan

    Returns:
        Ordered list of audio file paths
    """
    return [entry for entry in list_directory_entries(directory) if not entry.is_dir()]


def get_next_audio_file(audio_file: Path) -> Optional[Path]:
    """
    Get the audio file that follows the given one in its folder.

    Uses the same ordering as the browser listing, so the "next" file is the one
    displayed after the current file.

    Args:
        audio_file: Currently playing audio file

    Returns:
        Path of the following audio file, or None if it is the last one in the
        folder (no wrap-around) or the file is not part of the listing
    """
    siblings = list_audio_files(audio_file.parent)

    # Match by name: the paths may have been built differently (relative vs.
    # absolute) but names are unique inside a folder.
    index = next((i for i, path in enumerate(siblings) if path.name == audio_file.name), None)
    if index is None:
        logger.debug(f"{audio_file.name} not found in its folder listing")
        return None

    if index + 1 >= len(siblings):
        return None

    return siblings[index + 1]


def find_cover_art(audio_file: Path) -> Optional[Path]:
    """
    Find the cover art image belonging to an audio file.

    Looks for an image file with the same stem next to the audio file.

    Args:
        audio_file: Path to the audio file

    Returns:
        Path to the cover art image, or None if there is none
    """
    for ext in IMAGE_EXTENSIONS:
        cover_path = audio_file.parent / f"{audio_file.stem}{ext}"
        if cover_path.exists():
            logger.debug(f"Found cover art: {cover_path}")
            return cover_path

    return None
