"""
Spotify URL classification.

Pure helper module (standard library only, no Flask/device imports) used by the
web downloader to decide whether a pasted link belongs to Spotify and, if so,
whether it means "one track" or "a whole collection" (album, playlist, artist).

Recognised forms:
* ``https://open.spotify.com/track/<id>`` (also album, playlist, artist)
* ``https://open.spotify.com/intl-de/track/<id>`` (localised links)
* ``https://open.spotify.com/embed/track/<id>`` (embed player links)
* ``spotify:track:<id>`` URIs
* ``https://spotify.link/<code>`` short links from the mobile app. Their target
  is unknown without a network round trip, so they classify as UNKNOWN and
  have to be resolved to an ``open.spotify.com`` URL first.
"""

from urllib.parse import urlparse

# Classification results
TRACK = 'track'
ALBUM = 'album'
PLAYLIST = 'playlist'
ARTIST = 'artist'
UNKNOWN = 'unknown'

# Everything but a single track downloads many files
COLLECTION_KINDS = (ALBUM, PLAYLIST, ARTIST)

_SPOTIFY_HOSTS = ('open.spotify.com', 'play.spotify.com')
_SHORT_LINK_HOSTS = ('spotify.link', 'spotify.app.link')
_KNOWN_KINDS = (TRACK, ALBUM, PLAYLIST, ARTIST)


def _host(parsed) -> str:
    """Lower-case host without credentials or port."""
    host = parsed.netloc.lower()
    if '@' in host:
        host = host.split('@', 1)[1]
    if ':' in host:
        host = host.split(':', 1)[0]
    if host.startswith('www.'):
        host = host[4:]
    return host


def is_spotify_url(url: str) -> bool:
    """Return True if the URL points at Spotify (web link, short link or URI)."""
    if not url or not url.strip():
        return False
    url = url.strip()
    if url.lower().startswith('spotify:'):
        return True
    host = _host(urlparse(url))
    return host in _SPOTIFY_HOSTS or host in _SHORT_LINK_HOSTS


def is_spotify_short_link(url: str) -> bool:
    """Return True for ``spotify.link`` style redirect links."""
    if not url or not url.strip():
        return False
    return _host(urlparse(url.strip())) in _SHORT_LINK_HOSTS


def classify_spotify_url(url: str) -> str:
    """
    Classify a Spotify URL as TRACK, ALBUM, PLAYLIST, ARTIST or UNKNOWN.

    Args:
        url: The URL pasted by the user (must be a Spotify URL, see
            is_spotify_url())

    Returns:
        One of TRACK, ALBUM, PLAYLIST, ARTIST or UNKNOWN. UNKNOWN covers short
        links, podcasts (episode/show) and anything else spotDL cannot handle
        directly.
    """
    if not url or not url.strip():
        return UNKNOWN
    url = url.strip()

    # spotify:track:<id> URIs
    if url.lower().startswith('spotify:'):
        parts = url.split(':')
        if len(parts) >= 3 and parts[1].lower() in _KNOWN_KINDS and parts[2]:
            return parts[1].lower()
        return UNKNOWN

    parsed = urlparse(url)
    if _host(parsed) not in _SPOTIFY_HOSTS:
        return UNKNOWN

    segments = [s for s in parsed.path.split('/') if s]
    # Skip optional prefixes: "intl-de", "embed", "embed-podcast", ...
    while segments and (segments[0].startswith('intl-') or segments[0].startswith('embed')):
        segments = segments[1:]

    if len(segments) >= 2 and segments[0].lower() in _KNOWN_KINDS and segments[1]:
        return segments[0].lower()
    return UNKNOWN


def is_collection(kind: str) -> bool:
    """Return True if the classification means many tracks get downloaded."""
    return kind in COLLECTION_KINDS
