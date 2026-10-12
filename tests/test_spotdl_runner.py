"""
Tests for the spotDL runner workaround (YouTube Music client language).
"""

import importlib.util
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

HAS_SPOTDL = importlib.util.find_spec('spotdl') is not None


@unittest.skipUnless(HAS_SPOTDL, "requires spotdl")
class TestSpotdlRunner(unittest.TestCase):

    def test_patch_uses_default_language_client(self):
        from spotdl.providers.audio import ytmusic
        from stream_toy.spotdl_runner import patch_youtube_music_client

        original = ytmusic.YouTubeMusic._create_client
        try:
            patch_youtube_music_client()
            client = ytmusic.YouTubeMusic._create_client()
            self.assertEqual(client.language, 'en')
        finally:
            ytmusic.YouTubeMusic._create_client = original


if __name__ == '__main__':
    unittest.main()
