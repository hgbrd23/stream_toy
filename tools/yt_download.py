#!/usr/bin/env python3
"""
Download YouTube videos (or entire playlists) as MP3 + thumbnail image.

Output format matches the audio_player convention:
    <target_dir>/<title>.mp3
    <target_dir>/<title>.jpg
Playlist entries are prefixed with their zero-padded playlist index
("03 - <title>.mp3") so alphabetical order equals playlist order.

Usage:
    # Single video
    python tools/yt_download.py "https://www.youtube.com/watch?v=VIDEO_ID"

    # Playlist
    python tools/yt_download.py "https://www.youtube.com/watch?v=...&list=PLAYLIST_ID"

    # Custom output directory
    python tools/yt_download.py -o data/audio_player/Music/MyAlbum "URL"

    # Force single video even if URL contains a playlist param
    python tools/yt_download.py --no-playlist "URL"

    # Download only items 1-5 from a playlist
    python tools/yt_download.py --items 1-5 "URL"
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def get_ytdlp_executable() -> str:
    """Find yt-dlp: first in the current Python's venv, then in PATH."""
    python_dir = Path(sys.executable).parent
    for name in ('yt-dlp', 'yt-dlp.exe'):
        candidate = python_dir / name
        if candidate.is_file():
            return str(candidate)

    found = shutil.which('yt-dlp')
    if found:
        return found

    # Check the emulator venv as a fallback
    project_root = Path(__file__).resolve().parent.parent
    emulator_ytdlp = project_root / '.venv-emulator' / 'bin' / 'yt-dlp'
    if emulator_ytdlp.is_file():
        return str(emulator_ytdlp)

    print("ERROR: yt-dlp not found. Install it with: pip install yt-dlp",
          file=sys.stderr)
    sys.exit(1)


def download(url: str, target_dir: Path, playlist: bool = True,
             items: str | None = None) -> None:
    """Run yt-dlp to download audio + thumbnail."""
    ytdlp = get_ytdlp_executable()

    target_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        ytdlp,
        '--extract-audio',
        '--audio-format', 'mp3',
        '--write-thumbnail',
        '--convert-thumbnails', 'jpg',
        '--newline',
        '--progress',
        # Put each file directly in target_dir with a clean title-based name.
        # Playlist entries get a zero-padded index prefix ('03 - Title') so
        # alphabetical sorting preserves playlist order; for single videos the
        # prefix collapses to nothing.
        '-o', '%(playlist_index&{:02d} - |)s%(title)s.%(ext)s',
    ]

    if not playlist:
        cmd.append('--no-playlist')

    if items:
        cmd.extend(['--playlist-items', items])

    cmd.append(url)

    print(f"Downloading to: {target_dir}")
    print(f"Command: {' '.join(cmd)}\n")

    process = subprocess.Popen(
        cmd,
        cwd=str(target_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    for line in process.stdout:
        line = line.rstrip()
        if line:
            print(line)

    process.wait()

    if process.returncode != 0:
        print(f"\nERROR: yt-dlp exited with code {process.returncode}",
              file=sys.stderr)
        sys.exit(process.returncode)

    # Report results
    mp3_files = sorted(target_dir.glob('*.mp3'))
    jpg_files = sorted(target_dir.glob('*.jpg'))
    print(f"\nDone! Downloaded {len(mp3_files)} MP3(s) and {len(jpg_files)} thumbnail(s) to {target_dir}")


def main():
    parser = argparse.ArgumentParser(
        description='Download YouTube videos as MP3 + thumbnail image.'
    )
    parser.add_argument('url', help='YouTube video or playlist URL')
    parser.add_argument(
        '-o', '--output-dir',
        type=Path,
        default=None,
        help='Target directory (default: data/audio_player/Music/YouTube)',
    )
    parser.add_argument(
        '--no-playlist',
        action='store_true',
        help='Download only the single video, even if the URL contains a playlist',
    )
    parser.add_argument(
        '--items',
        type=str,
        default=None,
        help='Playlist item range, e.g. "1-5", "2,4,7", "10-20" (default: all)',
    )

    args = parser.parse_args()

    if args.output_dir is None:
        project_root = Path(__file__).resolve().parent.parent
        target_dir = project_root / 'data' / 'audio_player' / 'Music' / 'YouTube'
    else:
        target_dir = args.output_dir.resolve()

    download(args.url, target_dir, playlist=not args.no_playlist,
             items=args.items)


if __name__ == '__main__':
    main()
