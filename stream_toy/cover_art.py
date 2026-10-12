"""
Extract embedded cover art from audio files into a sidecar image.

The audio player shows a cover image when a file named like the audio file
(``<stem>.jpg`` / ``<stem>.png``) exists next to it (see
stream_toy_apps/audio_player/audio_files.py). yt-dlp writes such a file with
``--write-thumbnail``; spotDL only embeds the cover into the audio tags, so it
is extracted here after a Spotify download.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Mime type -> sidecar file extension (must match audio_files.IMAGE_EXTENSIONS)
_MIME_EXTENSIONS = {
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/bmp': '.bmp',
}


def _embedded_picture(audio_file: Path):
    """Return (bytes, mime) of the first embedded picture, or None."""
    import mutagen
    from mutagen.id3 import ID3, ID3NoHeaderError

    # ID3 (mp3) first: works even for files whose MPEG frames mutagen cannot
    # sync to, and APIC frames carry the mime type we need.
    try:
        tags = ID3(audio_file)
        for frame in tags.getall('APIC'):
            if frame.data:
                return frame.data, frame.mime
        return None
    except ID3NoHeaderError:
        pass

    audio = mutagen.File(audio_file)
    if audio is None:
        return None

    # FLAC / Ogg store Picture blocks
    for picture in getattr(audio, 'pictures', None) or []:
        if picture.data:
            return picture.data, picture.mime

    # MP4 / M4A store raw cover bytes
    tags = getattr(audio, 'tags', None)
    covers = tags.get('covr') if tags else None
    if covers:
        cover = covers[0]
        mime = 'image/png' if bytes(cover).startswith(b'\x89PNG') else 'image/jpeg'
        return bytes(cover), mime
    return None


def extract_embedded_cover(audio_file: Path, overwrite: bool = False) -> Optional[Path]:
    """
    Write the embedded cover art of an audio file to ``<stem>.<ext>`` next to it.

    Args:
        audio_file: The audio file to read the tags from
        overwrite: Replace an existing sidecar image (default: keep it)

    Returns:
        Path of the written (or already existing) image, None if the file has
        no embedded cover or mutagen is not available.
    """
    audio_file = Path(audio_file)

    for ext in _MIME_EXTENSIONS.values():
        existing = audio_file.with_suffix(ext)
        if existing.exists() and not overwrite:
            return existing

    try:
        picture = _embedded_picture(audio_file)
    except ImportError:
        logger.warning("mutagen not installed - cannot extract cover art")
        return None
    except Exception as e:
        logger.warning(f"Could not read tags of {audio_file.name}: {e}")
        return None

    if not picture:
        logger.debug(f"No embedded cover in {audio_file.name}")
        return None

    data, mime = picture
    ext = _MIME_EXTENSIONS.get((mime or '').lower())
    if ext is None:
        # Sniff the bytes when the tag's mime type is missing or odd
        ext = '.png' if data.startswith(b'\x89PNG') else '.jpg'

    cover_path = audio_file.with_suffix(ext)
    try:
        cover_path.write_bytes(data)
    except OSError as e:
        logger.warning(f"Could not write cover art {cover_path}: {e}")
        return None

    logger.info(f"Extracted cover art to {cover_path.name}")
    return cover_path
