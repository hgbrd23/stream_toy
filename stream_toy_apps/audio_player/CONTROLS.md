# Audio Player - Quick Controls Reference

## Button Layout

### At Root Directory (`/data/audio_player/`)
```
┌─────────┬─────────┬─────────┬─────────┬─────────┐
│ File 1  │ File 2  │ File 3  │ File 4  │    ▲    │
│  📁/♪   │  📁/♪   │  📁/♪   │  📁/♪   │   Up    │
├─────────┼─────────┼─────────┼─────────┼─────────┤
│ File 5  │ File 6  │ File 7  │ File 8  │    ▼    │
│  📁/♪   │  📁/♪   │  📁/♪   │  📁/♪   │  Down   │
├─────────┼─────────┼─────────┼─────────┼─────────┤
│ File 9  │ File 10 │ File 11 │ File 12 │    ✕    │
│  📁/♪   │  📁/♪   │  📁/♪   │  📁/♪   │  EXIT   │
└─────────┴─────────┴─────────┴─────────┴─────────┘
```

### Inside a Folder
```
┌─────────┬─────────┬─────────┬─────────┬─────────┐
│ File 1  │ File 2  │ File 3  │ File 4  │    ▲    │
│  📁/♪   │  📁/♪   │  📁/♪   │  📁/♪   │   Up    │
├─────────┼─────────┼─────────┼─────────┼─────────┤
│ File 5  │ File 6  │ File 7  │ File 8  │    ▼    │
│  📁/♪   │  📁/♪   │  📁/♪   │  📁/♪   │  Down   │
├─────────┼─────────┼─────────┼─────────┼─────────┤
│ File 9  │ File 10 │ File 11 │ File 12 │    ←    │
│  📁/♪   │  📁/♪   │  📁/♪   │  📁/♪   │  BACK   │
└─────────┴─────────┴─────────┴─────────┴─────────┘
```

## All Controls

| Button | Action | What Happens |
|--------|--------|--------------|
| **Folder tile (📁)** | Tap | Open folder and show its contents |
| **Audio tile (♪)** | Tap | **Open player screen and start playback** |
| **Up (▲)** | Tap | Scroll up 12 items |
| **Down (▼)** | Tap | Scroll down 12 items |
| **Back (←)** | Tap | Go to parent folder |
| **Back (←)** | **LONG PRESS (3 sec)** | **Exit to app selection** |
| **Exit (✕)** | Tap | Return to app selection |

## Icons Explained

| Icon | Meaning |
|------|---------|
| 📁 | Folder - tap to open |
| ♪ | Audio file - tap to play |
| ▶ | Currently playing - tap to pause/resume |
| ▲ | Scroll up (appears when items above) |
| ▼ | Scroll down (appears when items below) |
| ← | Back to parent folder |
| ✕ | Exit to app launcher |

## Common Tasks

### Navigate to a Song Deep in Folders
1. Tap folders to navigate deeper
2. Use Up/Down to scroll through files
3. Tap the song to play

### Exit Quickly
**Option 1:** Navigate back to root, tap Exit button
**Option 2:** From any folder, **long-press Back button (3 seconds)**

### Listen While Browsing
1. Play a song (tap audio file)
2. Navigate to other folders (music keeps playing)
3. Tap another song to switch tracks

### Return to Main Menu Fast
**Long-press the Back button for 3 seconds** from any folder level

## Tips

- **Long filenames?** They wrap to 2-3 lines automatically (14px font)
- **Lost your place?** The scroll position resets when you enter a folder
- **Quick exit?** Long-press Back from anywhere (3 seconds)
- **No audio?** Check that miniaudio is installed and ALSA is configured

## Exit Behavior

| Current Location | Exit Method | Result |
|-----------------|-------------|---------|
| At root | Tap "Exit" button | → App selection |
| In folder | Long-press "Back" (3 sec) | → App selection |
| In folder | Tap "Back" normally | → Parent folder |
| During playback | Any exit method | Audio stops, then exits |

---

## Player Screen Controls

See **[PLAYER.md](PLAYER.md)** for complete player screen documentation.

**Quick reference:**
- Skip: 10s, 1min, 10min forward/backward
- Volume: +/- in 10% increments
- Pause/Play: Toggle playback
- Back: Return to browser (stops audio)

---

**Remember:**
- Tap audio file → Opens player screen
- Player Back button → Returns to browser
- Browser Back button (3-sec hold) → Exit to app launcher
