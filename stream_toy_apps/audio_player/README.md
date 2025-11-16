# Audio Player App

A folder-based audio player for StreamToy that lets you browse and play audio files organized in directories.

## Features

- **Multi-level folder navigation**: Browse through nested folders
- **Multiple audio format support**: MP3, WAV, FLAC, OGG, M4A
- **Scrollable file list**: Navigate through large collections
- **Play/Pause control**: Tap a file to play, tap again to pause/resume
- **Visual playback indicator**: See which file is currently playing
- **Easy exit**: Exit button on main screen, long-press anywhere to quit

## Button Layout

The StreamDock has 15 buttons arranged in a 3x5 grid:

### At Root Directory
```
[File 1 ] [File 2 ] [File 3 ] [File 4 ] [  Up  ]
[File 5 ] [File 6 ] [File 7 ] [File 8 ] [ Down ]
[File 9 ] [File 10] [File 11] [File 12] [  ✕   ]
                                         [ Exit ]
```

### Inside a Folder
```
[File 1 ] [File 2 ] [File 3 ] [File 4 ] [  Up  ]
[File 5 ] [File 6 ] [File 7 ] [File 8 ] [ Down ]
[File 9 ] [File 10] [File 11] [File 12] [  ←   ]
                                         [ Back ]
```

### File/Folder Buttons (Columns 0-3)
- Shows up to 12 items (folders and files) at a time
- Folders display with 📁 icon
- Audio files display with ♪ icon
- Currently playing file shows ▶ icon
- **Tap folder** → Navigate into it
- **Tap file** → Play/pause audio

### Navigation Buttons (Column 4)
- **Up (▲)**: Scroll up to see previous items (only shown when applicable)
- **Down (▼)**: Scroll down to see more items (only shown when applicable)
- **Back/Exit (←/✕)**: Context-sensitive button
  - **At root**: Shows "✕ Exit" - tap to return to app selection
  - **In folder**: Shows "← Back" - tap to go to parent folder
  - **Long-press (3 sec)**: Exit to app selection from anywhere

## Usage

1. **Launch the app** from the module launcher
2. **Browse folders**: Tap a folder button to enter it
3. **Play audio**: Tap an audio file to start playback
4. **Pause/Resume**: Tap the currently playing file to pause/resume
5. **Navigate**: Use Up/Down buttons to scroll through items
6. **Go back**: Use Back button to return to parent folder
7. **Exit**:
   - At root: Tap "Exit" button to return to app selection
   - In folder: Long-press "Back" button (3 seconds) to exit to app selection

## Quick Controls Reference

| Action | Button | Details |
|--------|--------|---------|
| Open folder | Tap folder tile | Navigate into the folder |
| Play/Pause | Tap audio file | Start playback or toggle pause |
| Scroll up | Up button | View earlier items (12 at a time) |
| Scroll down | Down button | View later items (12 at a time) |
| Go back | Back button | Return to parent folder |
| **Exit to launcher** | **Exit button (at root)** | **Return to app selection** |
| **Quick exit** | **Long-press Back (3 sec)** | **Exit from anywhere** |

## File Organization

Place your audio files in: `/data/audio_player/`

Example structure:
```
/data/audio_player/
├── Music/
│   ├── Rock/
│   │   ├── song1.mp3
│   │   └── song2.mp3
│   ├── Jazz/
│   │   └── track1.mp3
│   └── Classical/
│       └── symphony.flac
├── Audiobooks/
│   └── MyBook/
│       ├── chapter01.mp3
│       └── chapter02.mp3
└── Podcasts/
    └── TechShow/
        └── episode001.mp3
```

## Behavior

- **Folders appear first**, then files (both alphabetically sorted)
- **Long filenames wrap** to multiple lines with smaller font (14px)
- **Playback continues** while browsing (can browse while listening)
- **Playback stops** when you switch to a different track
- **Auto-stop on exit**: Audio stops automatically when exiting to launcher
- When a track finishes, playback stops (no auto-advance)
- **Long-press threshold**: 3 seconds to trigger long-press exit

## Player Screen

When you tap an audio file, a full-screen player opens with these controls:

### Player Layout
```
[<<10min] [<<1min] [<<10s ] [>>10s ] [>>1min]
[ Vol-  ] [Pause ] [ Vol+ ] [      ] [      ]
[  Time Display...................] [ Back ]
```

### Player Controls

| Button | Function |
|--------|----------|
| **<<10min** | Skip backward 10 minutes |
| **<<1min** | Skip backward 1 minute |
| **<<10s** | Skip backward 10 seconds |
| **>>10s** | Skip forward 10 seconds |
| **>>1min** | Skip forward 1 minute |
| **Vol-** | Decrease volume 10% |
| **Pause/Play** | Toggle playback |
| **Vol+** | Increase volume 10% |
| **Time Display** | Shows current time, total time, progress %, filename |
| **Back** | Return to file browser (stops playback) |

## Supported Audio Formats

- **MP3** (.mp3) - Most common format
- **WAV** (.wav) - Uncompressed audio
- **FLAC** (.flac) - Lossless compression
- **OGG Vorbis** (.ogg) - Open format
- **M4A** (.m4a) - AAC audio

## Requirements

### Python Dependencies

The audio player requires **miniaudio** to be installed:

```bash
pip install miniaudio
```

If you see "Sound manager not available" errors, install miniaudio:
```bash
. .venv/bin/activate
pip install miniaudio
```

### Hardware (Raspberry Pi)

ALSA must be configured for the MAX98357A amplifiers (see main `readme.md`).

## Technical Details

- Uses the SoundManager for audio playback
- Configured for 48000 Hz sample rate (matching ALSA config)
- Supports multi-level folder hierarchies
- Thread-safe audio playback
- Automatic cleanup on scene exit

## Implementation

- **Browser Scene**: `main.py` (AudioPlayerScene)
- **Player Scene**: `player_scene.py` (PlayerScene)
- **Data Directory**: `/data/audio_player/`
- **Visible Items**: 12 per page (4 columns × 3 rows)
- **Scroll Step**: 12 items (one full page)

## Notes

- Only files with recognized audio extensions are shown
- Hidden files (starting with `.`) are ignored by default
- The bottom-right button changes based on context:
  - At root: "✕ Exit" button to return to app selection
  - In folder: "← Back" button to go to parent folder
- Up/Down buttons only appear when there are items to scroll to
- **Pro tip**: From any folder, long-press the Back button (3 sec) to quickly exit to the app launcher
- Text uses 14-16px font with word wrapping for better readability on 112x112 pixel tiles
