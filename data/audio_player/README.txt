Audio Player Data Directory
===========================

Place your audio files in this directory structure.

Supported formats:
- MP3 (.mp3)
- WAV (.wav)
- FLAC (.flac)
- OGG Vorbis (.ogg)
- M4A (.m4a)

Example structure:
/data/audio_player/
  ├── Music/
  │   ├── Rock/
  │   │   ├── song1.mp3
  │   │   └── song2.mp3
  │   └── Jazz/
  │       └── track1.mp3
  ├── Audiobooks/
  │   └── book_chapter1.mp3
  └── Podcasts/
      └── episode1.mp3

The audio player will automatically:
- Show folders first, then files (alphabetically)
- Support navigation through multiple folder levels
- Allow scrolling through more than 12 items
- Play/pause audio files
- Show which file is currently playing
