# How to Add Audio Files

## Quick Start

1. Copy your audio files to this directory or create subfolders
2. Organize files however you like (by genre, artist, album, etc.)
3. Launch the Audio Player app on your StreamToy device

## Example Commands

### Copy a single file
```bash
cp /path/to/your/song.mp3 /workspace/data/audio_player/Music/
```

### Copy a folder of files
```bash
cp -r /path/to/your/music/album /workspace/data/audio_player/Music/
```

### Create organized structure
```bash
mkdir -p /workspace/data/audio_player/Music/MyArtist/Album1
cp /path/to/songs/*.mp3 /workspace/data/audio_player/Music/MyArtist/Album1/
```

## Supported Formats

- `.mp3` - MP3 audio
- `.wav` - WAV audio
- `.flac` - FLAC lossless
- `.ogg` - OGG Vorbis
- `.m4a` - M4A/AAC audio

## Organization Tips

### By Genre
```
Music/
├── Rock/
├── Jazz/
├── Classical/
└── Electronic/
```

### By Artist/Album
```
Music/
├── The Beatles/
│   ├── Abbey Road/
│   └── Let It Be/
└── Pink Floyd/
    └── Dark Side of the Moon/
```

### For Audiobooks
```
Audiobooks/
├── Fiction/
│   └── Book Title/
│       ├── Chapter 01.mp3
│       ├── Chapter 02.mp3
│       └── ...
└── Non-Fiction/
    └── Another Book/
        └── ...
```

### For Podcasts
```
Podcasts/
├── Tech Show/
│   ├── Episode 001.mp3
│   ├── Episode 002.mp3
│   └── ...
└── News Podcast/
    └── ...
```

## Testing with Sample Audio

If you don't have audio files yet, you can:

1. **Download free music** from sources like:
   - Free Music Archive (freemusicarchive.org)
   - CC Mixter (ccmixter.org)
   - YouTube Audio Library (with proper download)

2. **Use text-to-speech** to create test files:
   ```bash
   # Example using espeak (if installed)
   espeak "This is a test audio file" --stdout > test.wav
   ```

3. **Create silent test files** using ffmpeg (if available):
   ```bash
   ffmpeg -f lavfi -i anullsrc=r=44100:cl=stereo -t 10 -acodec libmp3lame test.mp3
   ```

## Troubleshooting

### Files don't appear in the app
- Check file extensions are supported (.mp3, .wav, .flac, .ogg, .m4a)
- Ensure files are not hidden (don't start with `.`)
- Verify files are in `/workspace/data/audio_player/` or its subfolders

### Can't play files
- Check the SoundManager is initialized (see logs)
- Verify ALSA is configured correctly (see main readme.md)
- Test audio with: `speaker-test -t wav -c 2 -l 1`

### Files are cut off in display
- Filenames are truncated to ~10 characters on buttons
- Full filename is still used for playback
- Consider using shorter, descriptive names
