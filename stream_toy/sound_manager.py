"""
Sound management system for StreamToy.

Manages audio playback with support for simple sound effects and
streaming music with full playback controls (pause, stop, seek).

Uses miniaudio for audio decoding and playback.
"""

import threading
import time
from pathlib import Path
from typing import Optional, Callable, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PlaybackStatus(Enum):
    """Playback status enumeration."""
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class SoundManager:
    """
    Manages audio playback for StreamToy.

    Features:
    - Simple MP3 playback (fire and forget)
    - Streaming playback with pause/resume/seek controls
    - Callbacks for playback position and status changes
    - Thread-safe operation
    """

    def __init__(self, sample_rate: int = 48000, settings_manager=None):
        """
        Initialize sound manager.

        Args:
            sample_rate: Sample rate (default: 48000 Hz to match ALSA config)
            settings_manager: Optional SettingsManager for persistent volume
        """
        self.sample_rate = sample_rate
        self._settings_manager = settings_manager

        # Playback state
        self._status = PlaybackStatus.STOPPED
        self._current_file: Optional[Path] = None
        self._position: float = 0.0  # Current position in seconds
        self._duration: float = 0.0  # Total duration in seconds

        # Load volume from settings, or use default
        if settings_manager:
            self._volume: float = settings_manager.get_volume()
            logger.info(f"Loaded volume from settings: {self._volume:.2f}")
        else:
            self._volume: float = 1.0  # Volume (0.0-1.0)
            logger.warning("No settings_manager provided - volume changes will not persist!")

        # Callbacks
        self._status_callback: Optional[Callable[[PlaybackStatus], None]] = None
        self._position_callback: Optional[Callable[[float, float], None]] = None

        # Threading
        self._lock = threading.Lock()
        self._playback_thread: Optional[threading.Thread] = None
        self._monitoring_thread: Optional[threading.Thread] = None
        self._running = False
        self._paused_event = threading.Event()
        self._stop_event = threading.Event()

        # miniaudio components
        self._device = None
        self._decoder = None
        self._initialized = False

        # Initialize audio backend
        self._initialize_audio()

    def _initialize_audio(self) -> None:
        """Initialize miniaudio for audio playback."""
        try:
            import miniaudio

            # Create playback device
            self._device = miniaudio.PlaybackDevice(
                sample_rate=self.sample_rate,
                output_format=miniaudio.SampleFormat.SIGNED16,
                nchannels=2  # Stereo
            )

            self._initialized = True
            logger.info(f"Sound Manager initialized with miniaudio: {self.sample_rate}Hz, stereo")

        except Exception as e:
            logger.error(f"Failed to initialize miniaudio: {e}")
            logger.warning("Sound Manager running in DISABLED mode")
            self._initialized = False

    def is_available(self) -> bool:
        """
        Check if sound system is available.

        Returns:
            True if audio playback is available
        """
        return self._initialized

    def play_sound(self, file_path: Path, volume: float = 1.0) -> bool:
        """
        Play a simple sound effect in a background thread.

        This is suitable for short sound effects. The sound plays independently
        and doesn't interfere with music playback.

        Args:
            file_path: Path to audio file (MP3, WAV, FLAC, etc.)
            volume: Volume level (0.0-1.0)

        Returns:
            True if playback started successfully
        """
        if not self._initialized:
            logger.warning("Cannot play sound: audio not initialized")
            return False

        try:
            file_path = Path(file_path)
            if not file_path.exists():
                logger.error(f"Sound file not found: {file_path}")
                return False

            # Start sound playback in background thread
            thread = threading.Thread(
                target=self._play_sound_internal,
                args=(file_path, volume),
                daemon=True
            )
            thread.start()

            logger.debug(f"Playing sound: {file_path.name}")
            return True

        except Exception as e:
            logger.error(f"Error playing sound {file_path}: {e}")
            return False

    def _play_sound_internal(self, file_path: Path, volume: float) -> None:
        """
        Internal method to play a sound effect.

        Args:
            file_path: Path to audio file
            volume: Volume level (0.0-1.0)
        """
        try:
            import miniaudio

            # Decode entire file
            decoded = miniaudio.decode_file(str(file_path))

            # Apply volume
            volume = max(0.0, min(1.0, volume))
            if volume != 1.0:
                import array
                samples = array.array(decoded.samples.typecode, decoded.samples)
                for i in range(len(samples)):
                    samples[i] = int(samples[i] * volume)
                decoded = miniaudio.DecodedSoundFile(
                    decoded.name,
                    decoded.nchannels,
                    decoded.sample_rate,
                    decoded.sample_format,
                    samples
                )

            # Play sound (blocking)
            stream = miniaudio.stream_file(str(file_path))
            with miniaudio.PlaybackDevice(
                sample_rate=stream.sample_rate,
                output_format=stream.sample_format,
                nchannels=stream.nchannels
            ) as device:
                # Apply volume to stream
                for chunk in stream:
                    if volume != 1.0:
                        import array
                        samples = array.array(chunk.typecode, chunk)
                        for i in range(len(samples)):
                            samples[i] = int(samples[i] * volume)
                        device.write(samples)
                    else:
                        device.write(chunk)

        except Exception as e:
            logger.error(f"Error in sound playback thread: {e}")

    def play_music(self, file_path: Path, volume: float = 1.0, start_pos: float = 0.0) -> bool:
        """
        Start streaming music playback.

        This is suitable for long audio files. Supports pause/resume/seek.

        Args:
            file_path: Path to audio file (MP3, WAV, FLAC, etc.)
            volume: Volume level (0.0-1.0)
            start_pos: Starting position in seconds

        Returns:
            True if playback started successfully
        """
        if not self._initialized:
            logger.warning("Cannot play music: audio not initialized")
            return False

        try:
            file_path = Path(file_path)
            if not file_path.exists():
                logger.error(f"Music file not found: {file_path}")
                return False

            # Stop current playback
            self.stop()

            with self._lock:
                self._current_file = file_path
                self._position = start_pos
                self._volume = max(0.0, min(1.0, volume))
                self._status = PlaybackStatus.PLAYING

                # Get duration
                try:
                    import miniaudio
                    info = miniaudio.get_file_info(str(file_path))
                    self._duration = info.duration
                except Exception as e:
                    logger.debug(f"Could not determine audio duration: {e}")
                    self._duration = 0.0

                # Reset events
                self._stop_event.clear()
                self._paused_event.clear()

            # Start playback thread
            self._running = True
            self._playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
            self._playback_thread.start()

            # Start position monitoring
            self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self._monitoring_thread.start()

            # Notify status change
            self._notify_status_change(PlaybackStatus.PLAYING)

            logger.info(f"Playing music: {file_path.name} (duration: {self._duration:.1f}s)")
            return True

        except Exception as e:
            logger.error(f"Error playing music {file_path}: {e}")
            return False

    def _playback_loop(self) -> None:
        """Background thread for streaming music playback."""
        logger.info("[PLAYBACK THREAD] Starting playback loop")
        try:
            import miniaudio
            import pyaudio
            import array

            with self._lock:
                file_path = self._current_file
                start_pos = self._position

            logger.info(f"[PLAYBACK THREAD] File: {file_path}, start_pos: {start_pos}")

            if not file_path:
                logger.warning("[PLAYBACK THREAD] No file_path set, exiting")
                return

            # Decode audio file completely
            logger.info(f"[PLAYBACK THREAD] Decoding file: {file_path}")
            decoded = miniaudio.decode_file(str(file_path))
            logger.info(f"[PLAYBACK THREAD] Decoded: {decoded.sample_rate}Hz, {decoded.nchannels} channels")

            # Use native sample rate - dmix will handle resampling
            sample_rate = decoded.sample_rate
            nchannels = decoded.nchannels
            samples = array.array('h', decoded.samples)

            logger.info(f"[PLAYBACK THREAD] Using native rate {sample_rate}Hz - dmix will handle resampling")

            # Calculate starting position
            start_sample = 0
            if start_pos > 0:
                start_sample = int(start_pos * sample_rate * nchannels)

            # Initialize PyAudio
            logger.info("[PLAYBACK THREAD] Initializing PyAudio...")
            p = pyaudio.PyAudio()
            logger.info(f"[PLAYBACK THREAD] PyAudio initialized, found {p.get_device_count()} devices")

            # Try to use hardware device directly via ALSA
            # Use hw:0,0 which is the raw hardware device (MAX98357A I2S)
            # This bypasses ALSA's software layers (dmix, etc.) that only support 48000 Hz
            stream = None
            device_name = None
            output_device_index = None  # Will be set if we find a hardware device

            # Strategy 1: Try hardware device directly (hw:0,0)
            try:
                logger.info("[PLAYBACK THREAD] Attempting to open ALSA hardware device 'hw:0,0'...")
                import alsaaudio
                # Check if alsaaudio can see the device
                logger.info("[PLAYBACK THREAD] ALSA devices available via alsaaudio: {}".format(alsaaudio.pcms()))

                # PyAudio can't use ALSA device names directly, but we can find it by matching
                device_count = p.get_device_count()
                logger.info(f"[PLAYBACK THREAD] Searching through {device_count} PyAudio devices...")

                output_device_index = None
                for i in range(device_count):
                    dev_info = p.get_device_info_by_index(i)
                    logger.debug(f"[PLAYBACK THREAD] Device {i}: '{dev_info['name']}' (outputs={dev_info['maxOutputChannels']}, rate={dev_info['defaultSampleRate']})")

                    # Look for hw:0,0 or MAX98357 or bcm2835
                    if dev_info['maxOutputChannels'] > 0:
                        dev_name = dev_info['name']
                        if 'hw:0,0' in dev_name or 'MAX98357' in dev_name or 'bcm2835' in dev_name or 'HiFi' in dev_name:
                            output_device_index = i
                            device_name = dev_name
                            logger.info(f"[PLAYBACK THREAD] Found hardware device {i}: {dev_name}")
                            break

                if output_device_index is not None:
                    logger.info(f"[PLAYBACK THREAD] Opening audio stream on device {output_device_index}: {device_name}, rate={sample_rate}Hz, channels={nchannels}")
                    stream = p.open(
                        format=pyaudio.paInt16,
                        channels=nchannels,
                        rate=sample_rate,
                        output=True,
                        output_device_index=output_device_index,
                        frames_per_buffer=1024
                    )
            except ImportError:
                logger.debug("[PLAYBACK THREAD] alsaaudio not available, will use PyAudio enumeration only")
            except Exception as e:
                logger.warning(f"[PLAYBACK THREAD] Could not open hardware device directly: {e}")

            # Strategy 2: If Strategy 1 failed, try plughw:0,0 (ALSA plugin layer with hardware)
            if stream is None:
                try:
                    logger.info("[PLAYBACK THREAD] Trying to find plughw:0,0 device...")
                    for i in range(p.get_device_count()):
                        dev_info = p.get_device_info_by_index(i)
                        if 'plughw' in dev_info['name'] and dev_info['maxOutputChannels'] > 0:
                            output_device_index = i
                            device_name = dev_info['name']
                            logger.info(f"[PLAYBACK THREAD] Found plughw device {i}: {device_name}")
                            stream = p.open(
                                format=pyaudio.paInt16,
                                channels=nchannels,
                                rate=sample_rate,
                                output=True,
                                output_device_index=output_device_index,
                                frames_per_buffer=1024
                            )
                            break
                except Exception as e:
                    logger.warning(f"[PLAYBACK THREAD] Could not open plughw device: {e}")

            # Strategy 3: Fallback to default device (will fail with 44100 Hz, but we'll know)
            if stream is None:
                logger.warning("[PLAYBACK THREAD] No hardware device found, using default (may fail with Invalid sample rate)")
                logger.info(f"[PLAYBACK THREAD] Opening audio stream on default device, rate={sample_rate}Hz, channels={nchannels}")
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=nchannels,
                    rate=sample_rate,
                    output=True,
                    frames_per_buffer=1024
                )
            logger.info(f"[PLAYBACK THREAD] Audio stream opened successfully!")

            try:
                # Stream audio in chunks
                # Use smaller chunks (0.1 seconds) to avoid blocking and stuttering
                chunk_size = int(sample_rate * nchannels * 0.1)  # 0.1 second chunks
                position_samples = start_sample
                total_samples = len(samples)
                chunks_written = 0

                while position_samples < total_samples:
                    # Check if stop requested
                    if self._stop_event.is_set():
                        break

                    # Handle pause
                    if self._paused_event.is_set():
                        # Wait until unpaused or stopped
                        while self._paused_event.is_set() and not self._stop_event.is_set():
                            time.sleep(0.01)

                        # If stopped while paused, exit
                        if self._stop_event.is_set():
                            break

                    # Get chunk of audio
                    end_sample = min(position_samples + chunk_size, total_samples)
                    chunk = samples[position_samples:end_sample]

                    # Apply volume
                    with self._lock:
                        volume = self._volume

                    if volume != 1.0:
                        chunk_adjusted = array.array('h', chunk)
                        for i in range(len(chunk_adjusted)):
                            chunk_adjusted[i] = int(chunk_adjusted[i] * volume)
                        stream.write(chunk_adjusted.tobytes())
                    else:
                        stream.write(chunk.tobytes())

                    chunks_written += 1
                    if chunks_written == 1:
                        logger.info(f"Audio playback started, writing chunks to device {output_device_index}")

                    # Update position
                    chunk_duration = len(chunk) / (sample_rate * nchannels)
                    with self._lock:
                        self._position += chunk_duration

                    position_samples = end_sample

            finally:
                # Close PyAudio stream
                stream.stop_stream()
                stream.close()
                p.terminate()

            # Playback finished
            if not self._stop_event.is_set():
                logger.debug("Music playback finished naturally")
                with self._lock:
                    self._status = PlaybackStatus.STOPPED
                    self._current_file = None
                    self._position = 0.0
                self._notify_status_change(PlaybackStatus.STOPPED)

        except Exception as e:
            logger.error(f"[PLAYBACK THREAD] Error in playback thread: {e}", exc_info=True)
            with self._lock:
                self._status = PlaybackStatus.STOPPED
            self._notify_status_change(PlaybackStatus.STOPPED)
        finally:
            self._running = False

    def _monitoring_loop(self) -> None:
        """Background thread to monitor playback position and send callbacks."""
        while self._running:
            try:
                with self._lock:
                    if self._status == PlaybackStatus.PLAYING:
                        self._notify_position_update(self._position, self._duration)

                time.sleep(0.1)  # Update every 100ms

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(0.1)

    def pause(self) -> bool:
        """
        Pause music playback.

        Returns:
            True if paused successfully
        """
        if not self._initialized:
            return False

        try:
            with self._lock:
                if self._status == PlaybackStatus.PLAYING:
                    self._paused_event.set()
                    self._status = PlaybackStatus.PAUSED
                    self._notify_status_change(PlaybackStatus.PAUSED)
                    logger.debug("Music paused")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error pausing music: {e}")
            return False

    def resume(self) -> bool:
        """
        Resume paused music playback.

        Returns:
            True if resumed successfully
        """
        if not self._initialized:
            return False

        try:
            with self._lock:
                if self._status == PlaybackStatus.PAUSED:
                    self._paused_event.clear()
                    self._status = PlaybackStatus.PLAYING
                    self._notify_status_change(PlaybackStatus.PLAYING)
                    logger.debug("Music resumed")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error resuming music: {e}")
            return False

    def stop(self) -> bool:
        """
        Stop music playback.

        Returns:
            True if stopped successfully
        """
        if not self._initialized:
            return False

        try:
            with self._lock:
                if self._status == PlaybackStatus.STOPPED:
                    return True

                self._status = PlaybackStatus.STOPPED
                self._stop_event.set()
                self._paused_event.clear()

            # Wait for playback thread to finish
            if self._playback_thread and self._playback_thread.is_alive():
                self._playback_thread.join(timeout=1.0)

            # Wait for monitoring thread
            if self._monitoring_thread and self._monitoring_thread.is_alive():
                self._monitoring_thread.join(timeout=0.5)

            with self._lock:
                self._current_file = None
                self._position = 0.0
                self._duration = 0.0

            self._notify_status_change(PlaybackStatus.STOPPED)
            logger.debug("Music stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping music: {e}")
            return False

    def seek(self, seconds: float) -> bool:
        """
        Seek forward or backward in the current track.

        This restarts playback from the new position.

        Args:
            seconds: Number of seconds to seek (positive = forward, negative = backward)

        Returns:
            True if seek successful
        """
        if not self._initialized:
            return False

        try:
            with self._lock:
                if self._status == PlaybackStatus.STOPPED or not self._current_file:
                    logger.warning("Cannot seek: no music playing")
                    return False

                # Calculate new position
                new_pos = max(0.0, self._position + seconds)
                if self._duration > 0:
                    # Clamp to slightly before the end to avoid immediate finish
                    new_pos = min(new_pos, self._duration - 0.5)

                # Remember state
                current_file = self._current_file
                was_paused = self._status == PlaybackStatus.PAUSED
                current_volume = self._volume

            # Stop current playback
            self.stop()

            # Restart from new position
            self.play_music(current_file, volume=current_volume, start_pos=new_pos)

            # Pause if we were paused
            if was_paused:
                self.pause()

            logger.debug(f"Seeked to {new_pos:.2f}s")
            return True

        except Exception as e:
            logger.error(f"Error seeking: {e}")
            return False

    def set_volume(self, volume: float) -> bool:
        """
        Set music volume and persist to settings.

        Args:
            volume: Volume level (0.0-0.3)

        Returns:
            True if volume set successfully (or saved even when audio unavailable)
        """
        try:
            # Import here to avoid circular dependency
            from stream_toy.settings_manager import SettingsManager

            with self._lock:
                self._volume = max(0.0, min(SettingsManager.MAX_VOLUME, volume))

            # Persist to settings if available (even when audio backend is disabled)
            if self._settings_manager:
                self._settings_manager.set_volume(self._volume)
                logger.info(f"Volume set to {self._volume:.2f} (saved to settings)")
            else:
                logger.warning(f"Volume set to {self._volume:.2f} (NOT SAVED - no settings_manager)")

            # Return False only if audio backend is unavailable
            # (but settings are still saved above)
            if not self._initialized:
                logger.debug("Volume saved to settings, but audio backend unavailable")
                return True  # Still return True since settings were saved

            return True
        except Exception as e:
            logger.error(f"Error setting volume: {e}")
            return False

    def get_status(self) -> PlaybackStatus:
        """
        Get current playback status.

        Returns:
            Current PlaybackStatus
        """
        with self._lock:
            return self._status

    def get_position(self) -> float:
        """
        Get current playback position.

        Returns:
            Position in seconds
        """
        with self._lock:
            return self._position

    def get_duration(self) -> float:
        """
        Get total duration of current track.

        Returns:
            Duration in seconds (0.0 if unknown)
        """
        with self._lock:
            return self._duration

    def set_status_callback(self, callback: Optional[Callable[[PlaybackStatus], None]]) -> None:
        """
        Set callback for playback status changes.

        Args:
            callback: Function called with (status) when playback status changes
        """
        with self._lock:
            self._status_callback = callback

    def set_position_callback(self, callback: Optional[Callable[[float, float], None]]) -> None:
        """
        Set callback for playback position updates.

        Called periodically during playback (approximately every 100ms).

        Args:
            callback: Function called with (position, duration) during playback
        """
        with self._lock:
            self._position_callback = callback

    def _notify_status_change(self, status: PlaybackStatus) -> None:
        """
        Notify status callback of status change.

        Args:
            status: New playback status
        """
        if self._status_callback:
            try:
                self._status_callback(status)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    def _notify_position_update(self, position: float, duration: float) -> None:
        """
        Notify position callback of position update.

        Args:
            position: Current position in seconds
            duration: Total duration in seconds
        """
        if self._position_callback:
            try:
                self._position_callback(position, duration)
            except Exception as e:
                logger.error(f"Error in position callback: {e}")

    def shutdown(self) -> None:
        """Shutdown sound manager and cleanup resources."""
        logger.info("Shutting down Sound Manager")

        # Stop playback
        self.stop()

        # Close device
        if self._device:
            try:
                self._device.close()
            except Exception as e:
                logger.error(f"Error closing audio device: {e}")

        logger.info("Sound Manager shutdown complete")
