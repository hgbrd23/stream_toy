#!/usr/bin/env python3
"""
Run spotDL with a workaround for its broken YouTube Music search.

spotDL creates its YouTube Music client with ``YTMusic(language="de")``
(hard-coded since 2022). With current ytmusicapi (1.12.x) a German-language
client returns zero results for the ``songs`` filter, so every track logs
"YouTube Music returned no usable results ... after 3 attempts" and spotDL
falls back to a plain YouTube video search. That fallback has stricter
title/artist matching and misses "Topic" uploads, which is why audiobooks and
less popular tracks end with "LookupError: No results found"
(spotDL issue #2779).

This wrapper replaces the client factory with a default (English) client,
which returns the full song results again, and then runs spotDL's normal
command line. It is started by the web downloader instead of the ``spotdl``
console script and takes exactly the same arguments.

Standalone (no project imports) so it can be run from any working directory:
    python stream_toy/spotdl_runner.py download <url> --output ...
"""

import sys


def patch_youtube_music_client() -> None:
    """Make spotDL's YouTube Music provider use a default-language client."""
    from ytmusicapi import YTMusic
    from spotdl.providers.audio import ytmusic

    ytmusic.YouTubeMusic._create_client = staticmethod(lambda: YTMusic())


def main() -> int:
    patch_youtube_music_client()
    from spotdl import console_entry_point

    return console_entry_point() or 0


if __name__ == '__main__':
    sys.exit(main())
