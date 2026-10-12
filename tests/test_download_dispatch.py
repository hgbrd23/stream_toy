"""
Tests for the web downloader's provider dispatch (YouTube vs. Spotify).
"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from stream_toy.web.server import (
    build_spotdl_command,
    classify_download_url,
    resolve_spotify_short_link,
)
from stream_toy import spotify_url


class TestClassifyDownloadUrl(unittest.TestCase):

    def test_youtube_video(self):
        result = classify_download_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
        self.assertEqual(result, {'provider': 'youtube', 'kind': 'video'})

    def test_youtube_ambiguous(self):
        result = classify_download_url(
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc123')
        self.assertEqual(result, {'provider': 'youtube', 'kind': 'ambiguous'})

    def test_spotify_track(self):
        result = classify_download_url(
            'https://open.spotify.com/intl-de/track/4uLU6hMCjMI75M1A2tKUQC?si=1')
        self.assertEqual(result, {'provider': 'spotify', 'kind': 'track'})

    def test_spotify_playlist(self):
        result = classify_download_url(
            'https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M')
        self.assertEqual(result, {'provider': 'spotify', 'kind': 'playlist'})

    def test_spotify_short_link(self):
        result = classify_download_url('https://spotify.link/abc123')
        self.assertEqual(result, {'provider': 'spotify', 'kind': 'unknown'})

    def test_other_sites_go_to_ytdlp(self):
        result = classify_download_url('https://soundcloud.com/artist/track')
        self.assertEqual(result['provider'], 'youtube')


class TestResolveSpotifyShortLink(unittest.TestCase):

    def test_non_short_links_are_returned_unchanged(self):
        """No network access for regular links."""
        url = 'https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC'
        self.assertEqual(resolve_spotify_short_link(url), url)
        yt = 'https://youtu.be/dQw4w9WgXcQ'
        self.assertEqual(resolve_spotify_short_link(yt), yt)


class TestBuildSpotdlCommand(unittest.TestCase):

    TARGET = Path('/music/Kids')
    URL = 'https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M'

    def _output(self, cmd):
        return cmd[cmd.index('--output') + 1]

    def test_playlist_goes_into_named_folder_with_position_prefix(self):
        cmd = build_spotdl_command(self.URL, spotify_url.PLAYLIST, self.TARGET,
                                   ['/venv/bin/python', '/app/spotdl_runner.py'])

        self.assertEqual(cmd[:4], ['/venv/bin/python', '/app/spotdl_runner.py', 'download', self.URL])
        self.assertEqual(self._output(cmd),
                         str(self.TARGET / '{list-name}/{list-position} {title}.{output-ext}'))

    def test_album_uses_track_number(self):
        cmd = build_spotdl_command(self.URL, spotify_url.ALBUM, self.TARGET, ['spotdl'])

        self.assertEqual(self._output(cmd),
                         str(self.TARGET / '{list-name}/{track-number} {title}.{output-ext}'))

    def test_single_track_lands_in_target_dir(self):
        cmd = build_spotdl_command(self.URL, spotify_url.TRACK, self.TARGET, ['spotdl'])

        self.assertEqual(self._output(cmd), str(self.TARGET / '{artist} - {title}.{output-ext}'))

    def test_mp3_simple_tui_and_ffmpeg(self):
        cmd = build_spotdl_command(self.URL, spotify_url.TRACK, self.TARGET, ['spotdl'],
                                   ffmpeg='/usr/bin/ffmpeg')

        self.assertIn('--simple-tui', cmd)
        self.assertIn('--print-errors', cmd)
        self.assertEqual(cmd[cmd.index('--format') + 1], 'mp3')
        self.assertEqual(cmd[cmd.index('--ffmpeg') + 1], '/usr/bin/ffmpeg')

    def test_without_ffmpeg_path(self):
        cmd = build_spotdl_command(self.URL, spotify_url.TRACK, self.TARGET, ['spotdl'])
        self.assertNotIn('--ffmpeg', cmd)

    def test_artist_and_unknown_are_rejected(self):
        for kind in (spotify_url.ARTIST, spotify_url.UNKNOWN):
            with self.assertRaises(ValueError):
                build_spotdl_command(self.URL, kind, self.TARGET, ['spotdl'])

    def test_runner_command_uses_current_interpreter(self):
        import sys
        from stream_toy.web.server import get_spotdl_command
        prefix = get_spotdl_command()
        self.assertEqual(prefix[0], sys.executable)
        self.assertTrue(Path(prefix[1]).is_file())
        self.assertEqual(Path(prefix[1]).name, 'spotdl_runner.py')


if __name__ == '__main__':
    unittest.main()
