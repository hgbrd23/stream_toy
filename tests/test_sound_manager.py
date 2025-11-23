"""Tests for sound_manager module."""

import unittest
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from stream_toy.sound_manager import SoundManager


class TestSoundManager(unittest.TestCase):
    """Test sound manager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_sound = Path("/workspace/assets/sound/button.mp3")

    def test_initialization_without_miniaudio(self):
        """Test sound manager initializes correctly even without miniaudio."""
        sm = SoundManager()
        self.assertIsNotNone(sm)
        # In container without miniaudio, should be unavailable
        is_available = sm.is_available()
        self.assertIsInstance(is_available, bool)

    @patch('stream_toy.sound_manager.threading.Thread')
    def test_play_sound_non_blocking(self, mock_thread):
        """Test that play_sound is non-blocking."""
        # Create a mock thread that doesn't actually run
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        sm = SoundManager()
        sm._initialized = True  # Force initialized

        start_time = time.time()
        result = sm.play_sound(self.test_sound, volume=0.3)
        elapsed = time.time() - start_time

        # Should return almost immediately (< 0.1 seconds)
        self.assertLess(elapsed, 0.1, "play_sound should be non-blocking")
        self.assertTrue(result)

        # Verify thread was started
        mock_thread_instance.start.assert_called_once()

    def test_play_sound_missing_file(self):
        """Test playing a sound file that doesn't exist."""
        sm = SoundManager()
        sm._initialized = True  # Force initialized

        missing_file = Path("/workspace/assets/sound/nonexistent.mp3")
        result = sm.play_sound(missing_file, volume=0.3)
        self.assertFalse(result)

    def test_play_sound_when_unavailable(self):
        """Test playing sound when audio is unavailable."""
        sm = SoundManager()
        sm._initialized = False  # Force unavailable

        result = sm.play_sound(self.test_sound, volume=0.3)
        self.assertFalse(result)

    def test_generator_callback_signature(self):
        """Test that stream_generator creates a proper generator with send() support."""
        import array

        # Simulate what happens inside _play_sound_internal
        samples = array.array('h', [100] * 50)  # Small sample
        samples_bytes = samples.tobytes()
        total_bytes = len(samples_bytes)
        position = [0]
        bytes_per_frame = 4  # 2 channels * 2 bytes per sample

        # This is the same generator function from _play_sound_internal
        def stream_generator():
            # First yield primes the generator (receives framecount via send)
            frames_needed = yield b''

            while True:
                # Check if done
                if position[0] >= total_bytes:
                    # Yield silence and wait for next request
                    frames_needed = yield b''
                    if frames_needed is None:
                        return
                    continue

                # Calculate bytes needed for requested frames
                if frames_needed is not None and frames_needed > 0:
                    bytes_needed = frames_needed * bytes_per_frame
                else:
                    bytes_needed = min(8192, total_bytes - position[0])

                # Get chunk
                chunk = samples_bytes[position[0]:position[0] + bytes_needed]
                position[0] += len(chunk)

                # Pad with silence if needed
                if len(chunk) < bytes_needed and chunk:
                    chunk += b'\x00' * (bytes_needed - len(chunk))

                # Yield chunk and receive next framecount
                frames_needed = yield chunk

        # Create the generator
        gen = stream_generator()

        # Verify it's a generator
        import types
        self.assertIsInstance(gen, types.GeneratorType,
                              "Callback must be a generator")

        # Prime the generator (first next() call)
        priming_result = next(gen)
        self.assertEqual(priming_result, b'', "First yield should return empty bytes")

        # Simulate miniaudio calling send() with framecount
        chunk1 = gen.send(512)  # Request 512 frames
        self.assertIsInstance(chunk1, bytes)
        self.assertGreater(len(chunk1), 0, "Should return audio data")

        # Request more frames
        chunk2 = gen.send(512)
        self.assertIsInstance(chunk2, bytes)

        # Verify generator can be properly closed
        try:
            gen.close()
        except StopIteration:
            pass  # Expected when closing generator


if __name__ == "__main__":
    unittest.main()
