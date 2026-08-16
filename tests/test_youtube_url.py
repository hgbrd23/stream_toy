"""
Tests for YouTube URL classification.

Verifies that pasted URLs are classified as single video, whole playlist or
ambiguous (video + playlist), and that the playlist choice is resolved
correctly for the downloader.
"""

import unittest
from pathlib import Path
import sys

# Add stream_toy to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from stream_toy.youtube_url import (
    AMBIGUOUS,
    PLAYLIST,
    VIDEO,
    classify_youtube_url,
    is_mix_playlist_id,
    resolve_playlist_choice,
)


class TestClassifyYoutubeUrl(unittest.TestCase):
    """Test cases for classify_youtube_url()."""

    def test_plain_watch_url_is_video(self):
        """A watch URL without a list parameter is a single video."""
        self.assertEqual(
            classify_youtube_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
            VIDEO
        )

    def test_watch_url_with_list_is_ambiguous(self):
        """A watch URL with a playlist parameter needs a user decision."""
        self.assertEqual(
            classify_youtube_url(
                'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc123'),
            AMBIGUOUS
        )

    def test_watch_url_with_list_and_index_is_ambiguous(self):
        """Extra parameters like index do not change the classification."""
        self.assertEqual(
            classify_youtube_url(
                'https://www.youtube.com/watch?v=abc&list=PLabc123&index=4'),
            AMBIGUOUS
        )

    def test_playlist_url_is_playlist(self):
        """A pure playlist URL downloads the whole playlist without asking."""
        self.assertEqual(
            classify_youtube_url('https://www.youtube.com/playlist?list=PLabc123'),
            PLAYLIST
        )

    def test_playlist_url_with_trailing_slash_is_playlist(self):
        """Trailing slashes must not break playlist detection."""
        self.assertEqual(
            classify_youtube_url('https://www.youtube.com/playlist/?list=PLabc123'),
            PLAYLIST
        )

    def test_short_link_is_video(self):
        """youtu.be short links without a list are single videos."""
        self.assertEqual(
            classify_youtube_url('https://youtu.be/dQw4w9WgXcQ'),
            VIDEO
        )

    def test_short_link_with_list_is_ambiguous(self):
        """youtu.be short links with a list parameter are ambiguous."""
        self.assertEqual(
            classify_youtube_url('https://youtu.be/dQw4w9WgXcQ?list=PLabc123'),
            AMBIGUOUS
        )

    def test_short_link_with_timestamp_is_video(self):
        """A start-time parameter is not a playlist reference."""
        self.assertEqual(
            classify_youtube_url('https://youtu.be/dQw4w9WgXcQ?t=42'),
            VIDEO
        )

    def test_shorts_url_is_video(self):
        """Shorts URLs are single videos."""
        self.assertEqual(
            classify_youtube_url('https://www.youtube.com/shorts/abc123'),
            VIDEO
        )

    def test_shorts_url_with_list_is_ambiguous(self):
        """Shorts can be part of a playlist too."""
        self.assertEqual(
            classify_youtube_url('https://www.youtube.com/shorts/abc123?list=PLxyz'),
            AMBIGUOUS
        )

    def test_embed_url_is_video(self):
        """Embed URLs are single videos."""
        self.assertEqual(
            classify_youtube_url('https://www.youtube.com/embed/abc123'),
            VIDEO
        )

    def test_mobile_and_music_hosts_are_supported(self):
        """m.youtube.com and music.youtube.com behave like the main host."""
        self.assertEqual(
            classify_youtube_url('https://m.youtube.com/watch?v=abc&list=PLxyz'),
            AMBIGUOUS
        )
        self.assertEqual(
            classify_youtube_url('https://music.youtube.com/playlist?list=PLxyz'),
            PLAYLIST
        )

    def test_radio_mix_list_on_watch_url_is_video(self):
        """RD... mixes are endless auto-generated lists - download the track."""
        self.assertEqual(
            classify_youtube_url(
                'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ'),
            VIDEO
        )

    def test_radio_mix_list_on_short_link_is_video(self):
        """The RD rule also applies to youtu.be links."""
        self.assertEqual(
            classify_youtube_url('https://youtu.be/abc123?list=RDabc123'),
            VIDEO
        )

    def test_radio_mix_playlist_page_is_playlist(self):
        """A bare mix playlist page has no single video to fall back to."""
        self.assertEqual(
            classify_youtube_url('https://www.youtube.com/playlist?list=RDabc123'),
            PLAYLIST
        )

    def test_watch_later_list_is_ambiguous(self):
        """Watch Later is a real playlist, not a mix."""
        self.assertEqual(
            classify_youtube_url('https://www.youtube.com/watch?v=abc&list=WL'),
            AMBIGUOUS
        )

    def test_empty_list_parameter_is_video(self):
        """An empty list parameter is not a playlist reference."""
        self.assertEqual(
            classify_youtube_url('https://www.youtube.com/watch?v=abc&list='),
            VIDEO
        )

    def test_watch_url_without_video_id_and_with_list_is_playlist(self):
        """watch?list=... without v is effectively a playlist URL."""
        self.assertEqual(
            classify_youtube_url('https://www.youtube.com/watch?list=PLabc123'),
            PLAYLIST
        )

    def test_unknown_url_defaults_to_video(self):
        """Non-YouTube URLs default to a single download, never a bulk one."""
        self.assertEqual(
            classify_youtube_url('https://example.com/media/song.mp3'),
            VIDEO
        )

    def test_empty_url_defaults_to_video(self):
        """Empty input must not raise."""
        self.assertEqual(classify_youtube_url(''), VIDEO)
        self.assertEqual(classify_youtube_url('   '), VIDEO)

    def test_is_mix_playlist_id(self):
        """Only RD-prefixed ids are mixes."""
        self.assertTrue(is_mix_playlist_id('RDabc123'))
        self.assertTrue(is_mix_playlist_id('RDMMabc'))
        self.assertFalse(is_mix_playlist_id('PLabc123'))
        self.assertFalse(is_mix_playlist_id('WL'))
        self.assertFalse(is_mix_playlist_id(''))


class TestResolvePlaylistChoice(unittest.TestCase):
    """Test cases for resolve_playlist_choice()."""

    def test_pure_playlist_always_downloads_playlist(self):
        """The classification wins - a client cannot downgrade it."""
        url = 'https://www.youtube.com/playlist?list=PLabc123'
        self.assertTrue(resolve_playlist_choice(url, None))
        self.assertTrue(resolve_playlist_choice(url, False))

    def test_plain_video_never_downloads_playlist(self):
        """The classification wins - a client cannot force a bulk download."""
        url = 'https://www.youtube.com/watch?v=abc'
        self.assertFalse(resolve_playlist_choice(url, None))
        self.assertFalse(resolve_playlist_choice(url, True))

    def test_ambiguous_uses_user_choice(self):
        """For ambiguous URLs the user's answer decides."""
        url = 'https://www.youtube.com/watch?v=abc&list=PLabc123'
        self.assertTrue(resolve_playlist_choice(url, True))
        self.assertFalse(resolve_playlist_choice(url, False))

    def test_ambiguous_without_choice_raises(self):
        """An unanswered ambiguous URL must not start a download."""
        url = 'https://www.youtube.com/watch?v=abc&list=PLabc123'
        with self.assertRaises(ValueError):
            resolve_playlist_choice(url, None)


if __name__ == '__main__':
    unittest.main()
