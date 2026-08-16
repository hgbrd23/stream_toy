# Audio Player - Player Screen Guide

## Opening the Player

1. Navigate to a folder containing audio files
2. Tap an audio file button
3. Player screen opens automatically and starts playback

## Player Screen Layout

```
┌─────────┬─────────┬─────────┬─────────┬─────────┐
│  <<     │  <<     │  <<     │  >>     │  >>     │
│ 10min   │  1min   │  10s    │  10s    │  1min   │
├─────────┼─────────┼─────────┼─────────┼─────────┤
│  Vol    │  ❚❚/▶   │  Vol    │         │         │
│   -     │ Pause   │   +     │         │         │
├─────────┼─────────┼─────────┼─────────┼─────────┤
│         Time Display          │         │    ←    │
│      (4 tiles wide)            │         │  Back   │
└─────────┴─────────┴─────────┴─────────┴─────────┘
```

## Controls

### Skip Backward/Forward (Row 0)
- **<<10min**: Jump back 10 minutes
- **<<1min**: Jump back 1 minute
- **<<10s**: Jump back 10 seconds
- **>>10s**: Jump forward 10 seconds
- **>>1min**: Jump forward 1 minute

### Volume & Playback (Row 1)
- **Vol-**: Decrease volume by 10%
- **Pause/Play**: Toggle between pause and play
  - Shows "❚❚ Pause" when playing
  - Shows "▶ Play" when paused
- **Vol+**: Increase volume by 10%

### Information Display (Row 2)
- **Time Display** (tiles 2,0 through 2,3):
  - Tile 1: Current time (MM:SS)
  - Tile 2: Total duration (MM:SS)
  - Tile 3: Progress percentage
  - Tile 4: Filename (truncated)
- **Back**: Exit player and return to file browser

## Usage Examples

### Quick Skip Forward
Tap **>>10s** multiple times to skip ahead quickly through a podcast intro.

### Fine-Tune Position
Use **<<10s** and **>>10s** to find a specific spot in a song.

### Jump to Near the End
Tap **>>1min** several times to quickly get to the end of a long audio file.

### Adjust Volume While Playing
- Too loud? Tap **Vol-** a few times
- Too quiet? Tap **Vol+** a few times
- Changes apply immediately

### Pause and Browse
1. Tap **Pause** to pause playback
2. Tap **Back** to return to browser
3. Navigate to other files
4. Playback remains paused

## Time Display Format

The time display shows:
```
3:45        10:22       34%         Song Na..
Current     Total    Progress     Filename
```

Updates automatically every 0.5 seconds while playing.

## Behavior

### Automatic Playback
- Player starts immediately when opened
- Audio begins from the beginning (or specified start position)

### Stopping Playback
- Tap **Back** button → Stops audio and returns to browser
- Track reaches the end → Auto-advance to the next file (see below)

### Auto-Advance at the End of a Track
- When a track finishes **on its own**, the player automatically opens the next
  audio file of the same folder and starts playing it
- "Next" means the entry after the current file in the browser listing
  (audio files only, sorted case-insensitively by name)
- The new file gets its own cover art, duration, filename tile and resume handling
- If the current file is the **last one in the folder**, the player stays open and
  the Pause button turns into **↻ Replay** — tap it to play the file again
- Auto-advance never happens on a manual stop, on pause, while seeking, or when
  you leave the player with **Back**

### Volume Persistence
- Volume level is remembered within the player session
- Starts at 80% by default
- Range: 0% (mute) to 100% (max)

### Seeking Limits
- Can't seek before the beginning (stays at 0:00)
- Can't seek past the end (limited to track duration)
- Seeking while paused maintains pause state

## Tips

- **Quick skip**: Use 10s buttons for precise control
- **Long skip**: Use 1min/10min buttons for longer files
- **Volume**: Adjust in 10% increments (10 clicks = 0% to 100%)
- **Progress**: Check the percentage to see how far through you are
- **Filename**: If truncated, remember the full name from the browser

## Troubleshooting

### "Audio Not Avail" Message
**Problem**: miniaudio not installed
**Solution**:
```bash
pip install miniaudio
```

### Player Opens But No Sound
- Check ALSA configuration (see main readme.md)
- Test with: `speaker-test -t wav -c 2 -l 1`
- Adjust volume: `amixer set Master 80%`

### Can't Seek or Controls Don't Work
- Check logs for errors
- Ensure audio file is not corrupted
- Try a different audio file

### Player Jumps to Another File
- The previous track finished and auto-advance opened the next file in the folder
- To stay on one file, use **Back** before it reaches the end

### Auto-Advance Does Not Happen
- The file is the last audio file in its folder (there is no wrap-around)
- The file duration could not be determined (must be > 0)
- Verify the next file has a supported audio extension

---

**Note**: All playback stops when you exit the player using the Back button.
