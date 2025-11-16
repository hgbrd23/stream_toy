# Audio Usage Guide

This guide explains how to use the SoundManager in StreamToy apps.

## Overview

The SoundManager provides audio playback capabilities for StreamToy applications. It supports:
- Simple sound effects (fire and forget)
- Streaming music playback with full controls
- Pause, resume, stop, and seek functionality
- Callbacks for playback status and position updates

## Accessing the SoundManager

The SoundManager is available through the device object in your scene:

```python
class MyScene(BaseScene):
    async def on_enter(self):
        # Access sound manager
        sound_mgr = self.runtime.device.sound_manager

        # Check if audio is available
        if sound_mgr and sound_mgr.is_available():
            print("Audio system ready!")
        else:
            print("Audio not available")
```

## Playing Sound Effects

For short sound effects (button clicks, notifications, etc.), use `play_sound()`:

```python
from pathlib import Path

# Play a sound effect at default volume
sound_mgr.play_sound(Path("assets/sounds/click.mp3"))

# Play with custom volume (0.0 to 1.0)
sound_mgr.play_sound(Path("assets/sounds/beep.mp3"), volume=0.5)
```

**Note:** Sound effects play independently and don't interfere with music playback.

## Playing Music

For longer audio files (music, audiobooks, etc.), use `play_music()`:

```python
from pathlib import Path

# Play music from the beginning
sound_mgr.play_music(Path("assets/music/song.mp3"))

# Play with custom volume
sound_mgr.play_music(Path("assets/music/song.mp3"), volume=0.7)

# Start from a specific position (in seconds)
sound_mgr.play_music(Path("assets/music/song.mp3"), start_pos=30.0)
```

## Controlling Playback

### Pause and Resume

```python
# Pause playback
sound_mgr.pause()

# Resume playback
sound_mgr.resume()

# Toggle pause/resume
if sound_mgr.get_status() == PlaybackStatus.PLAYING:
    sound_mgr.pause()
else:
    sound_mgr.resume()
```

### Stop

```python
# Stop playback completely
sound_mgr.stop()
```

### Seek

```python
# Skip forward 10 seconds
sound_mgr.seek(10.0)

# Go back 5 seconds
sound_mgr.seek(-5.0)

# Jump to specific position (stop, then play from new position)
current_pos = sound_mgr.get_position()
new_pos = 60.0  # Jump to 1 minute
sound_mgr.seek(new_pos - current_pos)
```

### Volume Control

```python
# Set volume (0.0 to 1.0)
sound_mgr.set_volume(0.8)

# Increase volume by 10%
current_vol = sound_mgr.get_volume()
sound_mgr.set_volume(min(1.0, current_vol + 0.1))

# Decrease volume by 10%
current_vol = sound_mgr.get_volume()
sound_mgr.set_volume(max(0.0, current_vol - 0.1))
```

## Getting Playback Information

### Status

```python
from stream_toy.sound_manager import PlaybackStatus

status = sound_mgr.get_status()

if status == PlaybackStatus.PLAYING:
    print("Currently playing")
elif status == PlaybackStatus.PAUSED:
    print("Paused")
elif status == PlaybackStatus.STOPPED:
    print("Stopped")
```

### Position and Duration

```python
# Get current position in seconds
position = sound_mgr.get_position()
print(f"Current position: {position:.1f}s")

# Get total duration in seconds
duration = sound_mgr.get_duration()
print(f"Total duration: {duration:.1f}s")

# Calculate percentage complete
if duration > 0:
    percent = (position / duration) * 100
    print(f"Progress: {percent:.1f}%")
```

## Using Callbacks

### Status Change Callback

Get notified when playback status changes:

```python
from stream_toy.sound_manager import PlaybackStatus

def on_status_change(status: PlaybackStatus):
    if status == PlaybackStatus.PLAYING:
        print("Started playing")
    elif status == PlaybackStatus.PAUSED:
        print("Paused")
    elif status == PlaybackStatus.STOPPED:
        print("Stopped/finished")

# Register callback
sound_mgr.set_status_callback(on_status_change)
```

### Position Update Callback

Get periodic updates during playback (approximately every 100ms):

```python
def on_position_update(position: float, duration: float):
    if duration > 0:
        percent = (position / duration) * 100
        print(f"Position: {position:.1f}s / {duration:.1f}s ({percent:.1f}%)")

# Register callback
sound_mgr.set_position_callback(on_position_update)
```

## Complete Example: Music Player Scene

```python
from pathlib import Path
from stream_toy.scene.base_scene import BaseScene
from stream_toy.sound_manager import PlaybackStatus

class MusicPlayerScene(BaseScene):
    def __init__(self, runtime):
        super().__init__(runtime)
        self.music_files = [
            Path("assets/music/track1.mp3"),
            Path("assets/music/track2.mp3"),
            Path("assets/music/track3.mp3"),
        ]
        self.current_track = 0

    async def on_enter(self):
        """Initialize scene."""
        sound_mgr = self.runtime.device.sound_manager

        if sound_mgr:
            # Set up callbacks
            sound_mgr.set_status_callback(self.on_status_change)
            sound_mgr.set_position_callback(self.on_position_update)

            # Start playing first track
            self.play_track(self.current_track)

        # Set up button controls
        await self.setup_ui()

    async def setup_ui(self):
        """Set up button UI."""
        # Button 0: Play/Pause
        self.set_tile_text(0, 0, "Play/\nPause")

        # Button 1: Stop
        self.set_tile_text(0, 1, "Stop")

        # Button 2: Previous track
        self.set_tile_text(0, 2, "Prev")

        # Button 3: Next track
        self.set_tile_text(0, 3, "Next")

        # Button 4: Skip back 10s
        self.set_tile_text(0, 4, "<<10s")

        # Button 5: Skip forward 10s
        self.set_tile_text(1, 0, "10s>>")

        self.submit_tiles()

    def play_track(self, index: int):
        """Play track at given index."""
        if 0 <= index < len(self.music_files):
            sound_mgr = self.runtime.device.sound_manager
            if sound_mgr:
                sound_mgr.play_music(self.music_files[index], volume=0.8)
                self.current_track = index

    def on_status_change(self, status: PlaybackStatus):
        """Handle status changes."""
        if status == PlaybackStatus.STOPPED:
            # Auto-play next track when current finishes
            self.current_track = (self.current_track + 1) % len(self.music_files)
            self.play_track(self.current_track)

    def on_position_update(self, position: float, duration: float):
        """Handle position updates."""
        # Update display with current time
        if duration > 0:
            time_str = f"{int(position//60)}:{int(position%60):02d} / {int(duration//60)}:{int(duration%60):02d}"
            # Could update a display tile here
            pass

    async def on_key_press(self, row: int, col: int):
        """Handle button presses."""
        sound_mgr = self.runtime.device.sound_manager
        if not sound_mgr:
            return

        button_index = row * 5 + col

        if button_index == 0:  # Play/Pause
            if sound_mgr.get_status() == PlaybackStatus.PLAYING:
                sound_mgr.pause()
            else:
                sound_mgr.resume()

        elif button_index == 1:  # Stop
            sound_mgr.stop()

        elif button_index == 2:  # Previous track
            self.current_track = (self.current_track - 1) % len(self.music_files)
            self.play_track(self.current_track)

        elif button_index == 3:  # Next track
            self.current_track = (self.current_track + 1) % len(self.music_files)
            self.play_track(self.current_track)

        elif button_index == 4:  # Skip back 10s
            sound_mgr.seek(-10.0)

        elif button_index == 5:  # Skip forward 10s
            sound_mgr.seek(10.0)

    async def on_exit(self):
        """Cleanup when leaving scene."""
        sound_mgr = self.runtime.device.sound_manager
        if sound_mgr:
            # Clear callbacks
            sound_mgr.set_status_callback(None)
            sound_mgr.set_position_callback(None)

            # Stop playback
            sound_mgr.stop()
```

## Supported Audio Formats

The SoundManager (using miniaudio) supports:
- MP3
- WAV
- FLAC
- OGG Vorbis
- And many other formats

## Performance Notes

1. **Sound Effects**: Sound effects are decoded and played in separate threads, so they won't block your scene.

2. **Music Streaming**: Music is streamed chunk-by-chunk, so even large files don't consume much memory.

3. **Seeking**: Seeking restarts playback from the new position. For very large files, seeking might take a moment.

4. **Callbacks**: Position callbacks are called approximately every 100ms during playback. Keep callback functions fast to avoid performance issues.

## Troubleshooting

### No Audio Output

If you don't hear audio:
1. Check that ALSA is configured correctly (see readme.md)
2. Verify audio device with: `speaker-test -t wav -c 2 -l 1`
3. Adjust volume with: `amixer set Master 80%`
4. Check logs for SoundManager initialization errors

### Audio Stuttering

If audio stutters or skips:
1. Reduce other system load
2. Use lower sample rates if possible
3. Check for other processes using audio

### Can't Import miniaudio

If you get import errors:
```bash
pip install miniaudio
```

Make sure you're using the correct Python environment where requirements.txt was installed.
