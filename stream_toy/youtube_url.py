"""
YouTube URL classification.

Pure helper module (standard library only, no Flask/device imports) used by the
web downloader to decide whether a pasted URL means "one video", "a whole
playlist" or "could be either - ask the user".

Classification rules:
* A video reference is a ``watch?v=<id>`` URL, a ``youtu.be/<id>`` short link or
  a ``/shorts/<id>``, ``/embed/<id>``, ``/live/<id>`` or ``/v/<id>`` path.
* A playlist reference is a non-empty ``list`` query parameter, or a
  ``/playlist`` path.
* ``list`` values starting with ``RD`` are YouTube's auto-generated radio/mix
  pseudo-playlists. They are endless algorithmic recommendations rather than a
  curated list, so downloading "the whole playlist" is almost never what the
  user wants. They are therefore ignored whenever the URL also points at a
  concrete video (result: SINGLE VIDEO, no question asked). A bare
  ``playlist?list=RD...`` URL has no single video to fall back to and is
  treated as a normal playlist.
* Video + playlist  -> AMBIGUOUS (the UI has to ask).
* Playlist only     -> PLAYLIST.
* Anything else (including non-YouTube URLs, which yt-dlp may still handle)
  -> VIDEO. That is the safe default: it never triggers a bulk download.
"""

from urllib.parse import urlparse, parse_qs

# Classification results
VIDEO = 'video'
PLAYLIST = 'playlist'
AMBIGUOUS = 'ambiguous'

# Path prefixes that identify a single video on youtube.com
_VIDEO_PATH_PREFIXES = ('/shorts/', '/embed/', '/live/', '/v/')

_YOUTUBE_HOSTS = (
    'youtube.com',
    'www.youtube.com',
    'm.youtube.com',
    'music.youtube.com',
    'youtube-nocookie.com',
    'www.youtube-nocookie.com',
)

_SHORT_HOSTS = ('youtu.be', 'www.youtu.be')


def _has_video_reference(host: str, path: str, query: dict) -> bool:
    """Check whether the URL parts point at one concrete video."""
    if host in _SHORT_HOSTS:
        # youtu.be/<id> - the path itself is the video id
        return len(path.strip('/')) > 0

    if host in _YOUTUBE_HOSTS:
        if path in ('/watch', '/watch/') and query.get('v', [''])[0]:
            return True
        if any(path.startswith(prefix) and len(path) > len(prefix)
               for prefix in _VIDEO_PATH_PREFIXES):
            return True

    return False


def _playlist_id(query: dict) -> str:
    """Return the ``list`` query parameter value (empty string if absent)."""
    values = query.get('list', [])
    return values[0].strip() if values else ''


def is_mix_playlist_id(playlist_id: str) -> bool:
    """Return True for YouTube's auto-generated radio/mix playlist ids."""
    return playlist_id.startswith('RD')


def classify_youtube_url(url: str) -> str:
    """
    Classify a URL as a single video, a whole playlist or ambiguous.

    Args:
        url: The URL pasted by the user

    Returns:
        One of VIDEO, PLAYLIST or AMBIGUOUS
    """
    if not url or not url.strip():
        return VIDEO

    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    # Strip credentials/port so "youtube.com:443" still matches
    if '@' in host:
        host = host.split('@', 1)[1]
    if ':' in host:
        host = host.split(':', 1)[0]

    path = parsed.path.rstrip('/') or parsed.path
    query = parse_qs(parsed.query)

    has_video = _has_video_reference(host, parsed.path, query)
    playlist_id = _playlist_id(query)
    is_playlist_page = host in _YOUTUBE_HOSTS and path in ('/playlist', '/playlist/')

    has_playlist = bool(playlist_id) or is_playlist_page

    if has_video and has_playlist:
        # Radio/mix pseudo-playlists are ignored in favour of the single video
        if playlist_id and is_mix_playlist_id(playlist_id):
            return VIDEO
        return AMBIGUOUS

    if has_playlist:
        return PLAYLIST

    return VIDEO


def resolve_playlist_choice(url: str, requested: bool | None) -> bool:
    """
    Decide whether yt-dlp should download the whole playlist.

    The classification always wins for unambiguous URLs so a client can never
    turn a plain video link into a bulk download (or vice versa). Only for
    ambiguous URLs does the user's choice apply.

    Args:
        url: The URL to download
        requested: The user's choice for ambiguous URLs (None if not answered)

    Returns:
        True to download the whole playlist, False for a single video

    Raises:
        ValueError: If the URL is ambiguous but no choice was made
    """
    kind = classify_youtube_url(url)

    if kind == PLAYLIST:
        return True
    if kind == VIDEO:
        return False

    if requested is None:
        raise ValueError(
            'This URL contains both a video and a playlist - '
            'a playlist choice is required'
        )
    return bool(requested)
