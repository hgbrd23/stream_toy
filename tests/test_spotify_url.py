"""
Tests for Spotify URL classification.

Verifies that pasted links are recognised as Spotify links and classified as
single track or collection (album, playlist, artist) for the downloader.
"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from stream_toy.spotify_url import (
    ALBUM,
    ARTIST,
    PLAYLIST,
    TRACK,
    UNKNOWN,
    classify_spotify_url,
    is_collection,
    is_spotify_short_link,
    is_spotify_url,
)


class TestIsSpotifyUrl(unittest.TestCase):
    """Test cases for is_spotify_url()."""

    def test_open_spotify_link(self):
        self.assertTrue(is_spotify_url('https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC'))

    def test_open_spotify_with_www_and_port(self):
        self.assertTrue(is_spotify_url('https://www.open.spotify.com:443/album/abc'))

    def test_spotify_uri(self):
        self.assertTrue(is_spotify_url('spotify:track:4uLU6hMCjMI75M1A2tKUQC'))

    def test_short_link(self):
        self.assertTrue(is_spotify_url('https://spotify.link/abcDEF123'))
        self.assertTrue(is_spotify_short_link('https://spotify.link/abcDEF123'))

    def test_youtube_is_not_spotify(self):
        self.assertFalse(is_spotify_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ'))
        self.assertFalse(is_spotify_short_link('https://youtu.be/dQw4w9WgXcQ'))

    def test_lookalike_host_is_not_spotify(self):
        self.assertFalse(is_spotify_url('https://open.spotify.com.evil.example/track/abc'))

    def test_empty(self):
        self.assertFalse(is_spotify_url(''))
        self.assertFalse(is_spotify_url('   '))
        self.assertFalse(is_spotify_url(None))


class TestClassifySpotifyUrl(unittest.TestCase):
    """Test cases for classify_spotify_url()."""

    def test_track(self):
        self.assertEqual(
            classify_spotify_url('https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC?si=xyz'),
            TRACK)

    def test_album(self):
        self.assertEqual(
            classify_spotify_url('https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3'),
            ALBUM)

    def test_playlist(self):
        self.assertEqual(
            classify_spotify_url('https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M'),
            PLAYLIST)

    def test_artist(self):
        self.assertEqual(
            classify_spotify_url('https://open.spotify.com/artist/0OdUWJ0sBjDrqHygGUXeCF'),
            ARTIST)

    def test_localised_prefix(self):
        self.assertEqual(
            classify_spotify_url('https://open.spotify.com/intl-de/track/4uLU6hMCjMI75M1A2tKUQC'),
            TRACK)

    def test_embed_prefix(self):
        self.assertEqual(
            classify_spotify_url('https://open.spotify.com/embed/playlist/37i9dQZF1DXcBWIGoYBM5M'),
            PLAYLIST)

    def test_uri(self):
        self.assertEqual(classify_spotify_url('spotify:album:1DFixLWuPkv3KT3TnV35m3'), ALBUM)
        self.assertEqual(classify_spotify_url('spotify:nonsense'), UNKNOWN)

    def test_uppercase_kind_is_normalised(self):
        self.assertEqual(
            classify_spotify_url('https://open.spotify.com/Track/4uLU6hMCjMI75M1A2tKUQC'),
            TRACK)

    def test_podcast_is_unknown(self):
        self.assertEqual(
            classify_spotify_url('https://open.spotify.com/episode/abc'), UNKNOWN)
        self.assertEqual(
            classify_spotify_url('https://open.spotify.com/show/abc'), UNKNOWN)

    def test_short_link_is_unknown(self):
        self.assertEqual(classify_spotify_url('https://spotify.link/abcDEF123'), UNKNOWN)

    def test_missing_id_is_unknown(self):
        self.assertEqual(classify_spotify_url('https://open.spotify.com/track/'), UNKNOWN)
        self.assertEqual(classify_spotify_url('https://open.spotify.com/'), UNKNOWN)

    def test_non_spotify_is_unknown(self):
        self.assertEqual(
            classify_spotify_url('https://www.youtube.com/playlist?list=PL123'), UNKNOWN)
        self.assertEqual(classify_spotify_url(''), UNKNOWN)


class TestIsCollection(unittest.TestCase):
    """Test cases for is_collection()."""

    def test_collections(self):
        for kind in (ALBUM, PLAYLIST, ARTIST):
            self.assertTrue(is_collection(kind))

    def test_single_and_unknown(self):
        self.assertFalse(is_collection(TRACK))
        self.assertFalse(is_collection(UNKNOWN))


if __name__ == '__main__':
    unittest.main()
