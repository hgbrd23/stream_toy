"""
Tests for extracting embedded cover art into a sidecar image file.
"""

import shutil
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from mutagen.id3 import ID3, APIC, TIT2
    HAS_MUTAGEN = True
except ImportError:  # pragma: no cover
    HAS_MUTAGEN = False

from PIL import Image

from stream_toy.cover_art import extract_embedded_cover


def _image_bytes(fmt: str) -> bytes:
    buf = BytesIO()
    Image.new('RGB', (8, 8), (200, 50, 50)).save(buf, format=fmt)
    return buf.getvalue()


@unittest.skipUnless(HAS_MUTAGEN, "requires mutagen")
class TestExtractEmbeddedCover(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _tagged_mp3(self, name: str, picture: bytes | None, mime: str = 'image/jpeg') -> Path:
        """Create a file with an ID3 tag (no audio frames needed for tag I/O)."""
        path = self.tmp / name
        path.write_bytes(b'')
        tags = ID3()
        tags.add(TIT2(encoding=3, text='Test'))
        if picture is not None:
            tags.add(APIC(encoding=3, mime=mime, type=3, desc='Cover', data=picture))
        tags.save(path)
        return path

    def test_jpeg_cover_is_written_as_jpg(self):
        jpeg = _image_bytes('JPEG')
        mp3 = self._tagged_mp3('01 Song.mp3', jpeg)

        cover = extract_embedded_cover(mp3)

        self.assertEqual(cover, self.tmp / '01 Song.jpg')
        self.assertEqual(cover.read_bytes(), jpeg)

    def test_png_cover_keeps_png_extension(self):
        png = _image_bytes('PNG')
        mp3 = self._tagged_mp3('song.mp3', png, mime='image/png')

        cover = extract_embedded_cover(mp3)

        self.assertEqual(cover, self.tmp / 'song.png')
        self.assertEqual(cover.read_bytes(), png)

    def test_unknown_mime_is_sniffed(self):
        png = _image_bytes('PNG')
        mp3 = self._tagged_mp3('song.mp3', png, mime='')

        cover = extract_embedded_cover(mp3)

        self.assertEqual(cover.suffix, '.png')

    def test_no_cover_returns_none(self):
        mp3 = self._tagged_mp3('plain.mp3', None)

        self.assertIsNone(extract_embedded_cover(mp3))
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ['plain.mp3'])

    def test_existing_sidecar_is_kept(self):
        mp3 = self._tagged_mp3('song.mp3', _image_bytes('JPEG'))
        existing = self.tmp / 'song.jpg'
        existing.write_bytes(b'keep me')

        cover = extract_embedded_cover(mp3)

        self.assertEqual(cover, existing)
        self.assertEqual(existing.read_bytes(), b'keep me')

    def test_existing_sidecar_can_be_overwritten(self):
        jpeg = _image_bytes('JPEG')
        mp3 = self._tagged_mp3('song.mp3', jpeg)
        (self.tmp / 'song.jpg').write_bytes(b'old')

        cover = extract_embedded_cover(mp3, overwrite=True)

        self.assertEqual(cover.read_bytes(), jpeg)

    def test_file_without_tags_returns_none(self):
        path = self.tmp / 'garbage.mp3'
        path.write_bytes(b'not an audio file')

        self.assertIsNone(extract_embedded_cover(path))

    def test_missing_file_returns_none(self):
        self.assertIsNone(extract_embedded_cover(self.tmp / 'missing.mp3'))


if __name__ == '__main__':
    unittest.main()
