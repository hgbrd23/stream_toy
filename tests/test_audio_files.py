"""Tests for the shared audio file enumeration helpers of the audio player app."""

import unittest
import tempfile
from pathlib import Path

from stream_toy_apps.audio_player.audio_files import (
    find_cover_art,
    get_next_audio_file,
    is_audio_file,
    list_audio_files,
    list_directory_entries,
)

AUDIO_FILES_LOGGER = 'stream_toy_apps.audio_player.audio_files'


class AudioFilesTestCase(unittest.TestCase):
    """Base class providing a temporary folder helper."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def make_files(self, *names: str) -> None:
        """Create empty files (or folders for names ending in '/') inside root."""
        for name in names:
            path = self.root / name
            if name.endswith('/'):
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'')


class TestIsAudioFile(AudioFilesTestCase):
    """Test audio file detection."""

    def test_supported_extensions(self):
        self.make_files('a.mp3', 'b.wav', 'c.flac', 'd.ogg', 'e.m4a')
        for name in ('a.mp3', 'b.wav', 'c.flac', 'd.ogg', 'e.m4a'):
            self.assertTrue(is_audio_file(self.root / name), name)

    def test_extension_is_case_insensitive(self):
        self.make_files('Track.MP3')
        self.assertTrue(is_audio_file(self.root / 'Track.MP3'))

    def test_non_audio_files_rejected(self):
        self.make_files('cover.jpg', 'notes.txt', 'track.mp3.yml')
        self.assertFalse(is_audio_file(self.root / 'cover.jpg'))
        self.assertFalse(is_audio_file(self.root / 'notes.txt'))
        self.assertFalse(is_audio_file(self.root / 'track.mp3.yml'))

    def test_directory_is_not_an_audio_file(self):
        self.make_files('music.mp3/')
        self.assertFalse(is_audio_file(self.root / 'music.mp3'))


class TestListing(AudioFilesTestCase):
    """Test the browser listing order and filtering."""

    def test_folders_first_then_audio_files(self):
        self.make_files('zfolder/', 'afolder/', 'b.mp3', 'a.mp3')
        names = [p.name for p in list_directory_entries(self.root)]
        self.assertEqual(names, ['afolder', 'zfolder', 'a.mp3', 'b.mp3'])

    def test_sorting_is_case_insensitive(self):
        self.make_files('Beta.mp3', 'alpha.mp3', 'Gamma.mp3')
        names = [p.name for p in list_audio_files(self.root)]
        self.assertEqual(names, ['alpha.mp3', 'Beta.mp3', 'Gamma.mp3'])

    def test_non_audio_files_are_filtered_out(self):
        self.make_files('track.mp3', 'track.jpg', 'track.mp3.yml', 'readme.txt')
        names = [p.name for p in list_directory_entries(self.root)]
        self.assertEqual(names, ['track.mp3'])

    def test_list_audio_files_excludes_folders(self):
        self.make_files('sub/', 'a.mp3')
        names = [p.name for p in list_audio_files(self.root)]
        self.assertEqual(names, ['a.mp3'])

    def test_missing_directory_returns_empty_list(self):
        with self.assertLogs(AUDIO_FILES_LOGGER, level='ERROR'):
            self.assertEqual(list_directory_entries(self.root / 'does-not-exist'), [])
            self.assertEqual(list_audio_files(self.root / 'does-not-exist'), [])

    def test_listing_matches_browser_order_used_for_next_file(self):
        """The audio files of a listing must be the listing minus the folders."""
        self.make_files('sub/', '02.mp3', '01.mp3', 'cover.png')
        entries = [p for p in list_directory_entries(self.root) if not p.is_dir()]
        self.assertEqual(entries, list_audio_files(self.root))


class TestGetNextAudioFile(AudioFilesTestCase):
    """Test next-file selection used by the player auto-advance."""

    def test_returns_following_file(self):
        self.make_files('01.mp3', '02.mp3', '03.mp3')
        nxt = get_next_audio_file(self.root / '01.mp3')
        self.assertIsNotNone(nxt)
        self.assertEqual(nxt.name, '02.mp3')

    def test_uses_browser_sort_order_not_creation_order(self):
        # Created out of order on purpose
        self.make_files('c.mp3', 'a.mp3', 'b.mp3')
        self.assertEqual(get_next_audio_file(self.root / 'a.mp3').name, 'b.mp3')
        self.assertEqual(get_next_audio_file(self.root / 'b.mp3').name, 'c.mp3')

    def test_case_insensitive_order(self):
        self.make_files('Beta.mp3', 'alpha.mp3', 'Gamma.mp3')
        self.assertEqual(get_next_audio_file(self.root / 'alpha.mp3').name, 'Beta.mp3')
        self.assertEqual(get_next_audio_file(self.root / 'Beta.mp3').name, 'Gamma.mp3')

    def test_last_file_returns_none_no_wrap_around(self):
        self.make_files('01.mp3', '02.mp3')
        self.assertIsNone(get_next_audio_file(self.root / '02.mp3'))

    def test_single_file_returns_none(self):
        self.make_files('only.mp3')
        self.assertIsNone(get_next_audio_file(self.root / 'only.mp3'))

    def test_skips_non_audio_siblings(self):
        self.make_files('01.mp3', '01.jpg', '01.mp3.yml', '02.flac', 'notes.txt')
        self.assertEqual(get_next_audio_file(self.root / '01.mp3').name, '02.flac')

    def test_folders_are_never_returned(self):
        self.make_files('01.mp3', 'zz_folder/')
        self.assertIsNone(get_next_audio_file(self.root / '01.mp3'))

    def test_mixed_extensions_are_ordered_by_name(self):
        self.make_files('a.flac', 'b.m4a', 'c.ogg', 'd.wav')
        self.assertEqual(get_next_audio_file(self.root / 'a.flac').name, 'b.m4a')
        self.assertEqual(get_next_audio_file(self.root / 'b.m4a').name, 'c.ogg')
        self.assertEqual(get_next_audio_file(self.root / 'c.ogg').name, 'd.wav')
        self.assertIsNone(get_next_audio_file(self.root / 'd.wav'))

    def test_unknown_file_returns_none(self):
        self.make_files('01.mp3', '02.mp3')
        self.assertIsNone(get_next_audio_file(self.root / 'missing.mp3'))

    def test_missing_directory_returns_none(self):
        with self.assertLogs(AUDIO_FILES_LOGGER, level='ERROR'):
            self.assertIsNone(get_next_audio_file(self.root / 'nope' / '01.mp3'))

    def test_next_file_is_stable_across_repeated_calls(self):
        self.make_files('01.mp3', '02.mp3', '03.mp3')
        first = get_next_audio_file(self.root / '01.mp3')
        second = get_next_audio_file(self.root / '01.mp3')
        self.assertEqual(first, second)

    def test_advancing_through_whole_folder(self):
        self.make_files('01.mp3', '02.mp3', '03.mp3')
        visited = [self.root / '01.mp3']
        current = visited[0]
        while True:
            current = get_next_audio_file(current)
            if current is None:
                break
            visited.append(current)
        self.assertEqual([p.name for p in visited], ['01.mp3', '02.mp3', '03.mp3'])


class TestFindCoverArt(AudioFilesTestCase):
    """Test cover art lookup shared by browser and player."""

    def test_finds_image_with_same_stem(self):
        self.make_files('track.mp3', 'track.jpg')
        cover = find_cover_art(self.root / 'track.mp3')
        self.assertIsNotNone(cover)
        self.assertEqual(cover.name, 'track.jpg')

    def test_returns_none_without_cover(self):
        self.make_files('track.mp3')
        self.assertIsNone(find_cover_art(self.root / 'track.mp3'))

    def test_ignores_image_of_other_track(self):
        self.make_files('track.mp3', 'other.png')
        self.assertIsNone(find_cover_art(self.root / 'track.mp3'))


if __name__ == '__main__':
    unittest.main()
