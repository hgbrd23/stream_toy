"""
Web server for StreamToy emulator.

Provides Flask + Socket.IO server for real-time device emulation.
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import base64
from io import BytesIO
import logging
from typing import Optional, List, Tuple, Dict
from pathlib import Path
import subprocess
import json
import threading
import sys
import shutil
import urllib.error
import urllib.parse
import urllib.request

from stream_toy.youtube_url import classify_youtube_url, resolve_playlist_choice

logger = logging.getLogger(__name__)

# Marker prefix used with yt-dlp's --print so we can map each finished file to
# the video it came from without polluting the log shown to the user.
_PRINT_MARKER = 'STREAMTOY_FILE'


def get_ytdlp_executable() -> str:
    """
    Get path to yt-dlp executable.

    First tries to find it in the same venv as the current Python,
    otherwise falls back to system PATH.
    """
    # Try to find yt-dlp in the same directory as the Python executable
    python_dir = Path(sys.executable).parent
    ytdlp_path = python_dir / 'yt-dlp'

    if ytdlp_path.exists() and ytdlp_path.is_file():
        return str(ytdlp_path)

    # Try with .exe extension (Windows)
    ytdlp_exe = python_dir / 'yt-dlp.exe'
    if ytdlp_exe.exists() and ytdlp_exe.is_file():
        return str(ytdlp_exe)

    # Fall back to searching in PATH
    ytdlp_in_path = shutil.which('yt-dlp')
    if ytdlp_in_path:
        return ytdlp_in_path

    # Last resort - just return 'yt-dlp' and hope it's in PATH
    logger.warning("yt-dlp not found in venv or PATH, using 'yt-dlp' as fallback")
    return 'yt-dlp'

# Global references
app = Flask(__name__)
app.config['SECRET_KEY'] = 'streamtoy-emulator-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

_web_device = None


def set_web_device(device) -> None:
    """
    Set reference to WebDevice instance.

    Args:
        device: WebDevice instance
    """
    global _web_device
    _web_device = device
    logger.info("WebDevice reference set in server")


@app.route('/')
def index():
    """Serve emulator HTML page."""
    return render_template('emulator.html')


@socketio.on('connect')
def handle_connect(auth=None):
    """Handle client connection."""
    logger.info("[INCOMING] Client connected to emulator")
    if _web_device:
        _web_device.on_client_connected()
    else:
        logger.warning("[INCOMING] Client connected but no WebDevice set")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("[INCOMING] Client disconnected from emulator")


@socketio.on('button_press')
def handle_button_press(data):
    """Handle button press from client."""
    logger.debug(f"[INCOMING] button_press: {data}")

    row = data.get('row')
    col = data.get('col')

    if row is None or col is None:
        logger.warning(f"Invalid button_press data: {data}")
        return

    logger.info(f"[INCOMING] Button press received: row={row}, col={col}")

    if _web_device:
        _web_device._on_button_event(row, col, True)


@socketio.on('button_release')
def handle_button_release(data):
    """Handle button release from client."""
    logger.debug(f"[INCOMING] button_release: {data}")

    row = data.get('row')
    col = data.get('col')

    if row is None or col is None:
        logger.warning(f"Invalid button_release data: {data}")
        return

    logger.info(f"[INCOMING] Button release received: row={row}, col={col}")

    if _web_device:
        _web_device._on_button_event(row, col, False)


def emit_tile_update(row: int, col: int, image_base64: str) -> None:
    """
    Emit tile update to all connected clients.

    Args:
        row: Tile row
        col: Tile column
        image_base64: Base64-encoded PNG image
    """
    image_size_bytes = len(image_base64)
    logger.info(f"[OUTGOING] tile_update: row={row}, col={col}, image_size={image_size_bytes} bytes")
    logger.debug(f"[OUTGOING] tile_update data: row={row}, col={col}, image_base64={image_base64[:50]}...")

    socketio.emit('tile_update', {
        'row': row,
        'col': col,
        'image': image_base64
    })


def emit_led_update(led_data: List[Tuple[int, int, int]]) -> None:
    """
    Emit LED color update to all connected clients.

    Args:
        led_data: List of (R, G, B) tuples
    """
    socketio.emit('led_update', {'leds': led_data})


# YouTube Downloader Routes

@app.route('/youtube-downloader')
def youtube_downloader():
    """Serve YouTube downloader page."""
    return render_template('youtube_downloader.html')


@app.route('/api/youtube/classify', methods=['POST'])
def classify_youtube_download():
    """Classify a URL as a single video, a whole playlist or ambiguous.

    Purely local (no network), so the downloader page can ask the playlist
    question immediately - even when YouTube is unreachable.
    """
    try:
        data = request.get_json()
        url = (data or {}).get('url', '').strip()

        if not url:
            return jsonify({'error': 'URL is required'}), 400

        return jsonify({'kind': classify_youtube_url(url)})

    except Exception as e:
        logger.error(f"Error classifying YouTube URL: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/youtube/title', methods=['POST'])
def get_youtube_title():
    """Get video title from YouTube URL via the oEmbed API.

    Deliberately avoids yt-dlp: a full extraction takes ~60s on the
    Pi Zero 2 W, while oEmbed answers in well under a second. The title is
    informational only - downloads must not depend on this endpoint.
    """
    url = ''
    try:
        data = request.get_json()
        url = data.get('url', '').strip()

        if not url:
            return jsonify({'error': 'URL is required'}), 400

        oembed_url = 'https://www.youtube.com/oembed?' + urllib.parse.urlencode(
            {'url': url, 'format': 'json'})
        with urllib.request.urlopen(oembed_url, timeout=10) as response:
            payload = json.load(response)

        title = payload.get('title', '').strip()
        if not title:
            return jsonify({'error': 'No title found'}), 400

        return jsonify({'title': title})

    except urllib.error.HTTPError as e:
        # 400/404: invalid or unknown video; 401/403: embedding disabled
        logger.warning(f"oEmbed title lookup failed for {url}: HTTP {e.code}")
        return jsonify({'error': 'Could not fetch video title'}), 400
    except urllib.error.URLError as e:
        logger.error(f"oEmbed title lookup unreachable for {url}: {e}")
        return jsonify({'error': 'YouTube not reachable'}), 408
    except Exception as e:
        logger.error(f"Error fetching YouTube title: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/audio/list', methods=['POST'])
def list_audio_files():
    """List audio files in a directory."""
    try:
        data = request.get_json()
        current_path = data.get('path', 'data/audio_player')

        # Ensure path is relative to project root (parent of stream_toy/)
        base_path = Path(__file__).parent.parent.parent.resolve()
        full_path = base_path / current_path

        # Security: prevent directory traversal
        try:
            full_path = full_path.resolve()
            if not str(full_path).startswith(str(base_path)):
                return jsonify({'error': 'Invalid path'}), 403
        except Exception:
            return jsonify({'error': 'Invalid path'}), 403

        # Create directory if it doesn't exist (for initial setup)
        if not full_path.exists():
            # Only create if it's under data/audio_player
            if str(full_path).startswith(str(base_path / 'data' / 'audio_player')):
                full_path.mkdir(parents=True, exist_ok=True)
            else:
                return jsonify({'error': 'Directory does not exist'}), 404

        if not full_path.is_dir():
            return jsonify({'error': 'Path is not a directory'}), 400

        # Audio file extensions
        audio_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma'}

        items = []

        # List directories
        for item in sorted(full_path.iterdir()):
            if item.is_dir():
                items.append({
                    'name': item.name,
                    'type': 'directory',
                    'path': str(item.relative_to(base_path))
                })

        # List audio files
        for item in sorted(full_path.iterdir()):
            if item.is_file() and item.suffix.lower() in audio_extensions:
                items.append({
                    'name': item.name,
                    'type': 'file',
                    'path': str(item.relative_to(base_path)),
                    'size': item.stat().st_size
                })

        # Get parent path for breadcrumb
        parent_path = None
        if full_path != base_path / 'data' / 'audio_player':
            parent = full_path.parent
            if str(parent).startswith(str(base_path / 'data' / 'audio_player')):
                parent_path = str(parent.relative_to(base_path))

        return jsonify({
            'items': items,
            'current_path': str(full_path.relative_to(base_path)),
            'parent_path': parent_path
        })

    except Exception as e:
        logger.error(f"Error listing audio files: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/audio/create-dir', methods=['POST'])
def create_audio_directory():
    """Create a new directory for audio files."""
    try:
        data = request.get_json()
        current_path = data.get('current_path', 'data/audio_player')
        dir_name = data.get('dir_name', '').strip()

        if not dir_name:
            return jsonify({'error': 'Directory name is required'}), 400

        # Validate directory name (no path separators, hidden files, etc.)
        if '/' in dir_name or '\\' in dir_name or dir_name.startswith('.'):
            return jsonify({'error': 'Invalid directory name'}), 400

        # Ensure path is relative to project root (parent of stream_toy/)
        base_path = Path(__file__).parent.parent.parent.resolve()
        parent_path = base_path / current_path
        new_dir_path = parent_path / dir_name

        # Security: prevent directory traversal
        try:
            new_dir_path = new_dir_path.resolve()
            parent_path = parent_path.resolve()
            if not str(new_dir_path).startswith(str(base_path / 'data' / 'audio_player')):
                return jsonify({'error': 'Invalid path'}), 403
            if not str(parent_path).startswith(str(base_path / 'data' / 'audio_player')):
                return jsonify({'error': 'Invalid parent path'}), 403
        except Exception:
            return jsonify({'error': 'Invalid path'}), 403

        # Check if directory already exists
        if new_dir_path.exists():
            return jsonify({'error': 'Directory already exists'}), 409

        # Create the directory
        new_dir_path.mkdir(parents=True, exist_ok=False)
        logger.info(f"Created directory: {new_dir_path}")

        return jsonify({
            'success': True,
            'path': str(new_dir_path.relative_to(base_path)),
            'message': f'Directory "{dir_name}" created successfully'
        })

    except Exception as e:
        logger.error(f"Error creating directory: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/audio/delete', methods=['POST'])
def delete_audio_item():
    """Delete a file or directory."""
    try:
        data = request.get_json()
        item_path = data.get('path', '').strip()
        force = data.get('force', False)  # Force delete non-empty directories

        if not item_path:
            return jsonify({'error': 'Path is required'}), 400

        # Ensure path is relative to project root (parent of stream_toy/)
        base_path = Path(__file__).parent.parent.parent.resolve()
        full_path = base_path / item_path

        # Security: prevent directory traversal
        try:
            full_path = full_path.resolve()
            if not str(full_path).startswith(str(base_path / 'data' / 'audio_player')):
                return jsonify({'error': 'Invalid path'}), 403
        except Exception:
            return jsonify({'error': 'Invalid path'}), 403

        # Check if path exists
        if not full_path.exists():
            return jsonify({'error': 'Path does not exist'}), 404

        # Handle directory deletion
        if full_path.is_dir():
            # Check if directory has visible items (directories and audio files)
            # Ignore hidden files (starting with .) like .DS_Store, .directory, etc.
            audio_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma'}
            visible_items = [
                item for item in full_path.iterdir()
                if not item.name.startswith('.')  # Skip hidden files
                and (item.is_dir() or (item.is_file() and item.suffix.lower() in audio_extensions))
            ]

            if visible_items and not force:
                return jsonify({
                    'error': 'Directory is not empty',
                    'requires_confirmation': True,
                    'item_count': len(visible_items)
                }), 400

            # Delete directory (and contents if force=True)
            import shutil
            shutil.rmtree(full_path)
            logger.info(f"Deleted directory: {full_path}")
            return jsonify({
                'success': True,
                'message': f'Directory deleted successfully'
            })

        # Handle file deletion
        elif full_path.is_file():
            # Audio file extensions
            audio_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma'}

            if full_path.suffix.lower() in audio_extensions:
                # Delete associated files (thumbnail and settings)
                stem = full_path.stem
                parent = full_path.parent

                # Delete thumbnail (.jpg with same name)
                thumbnail_path = parent / f"{stem}.jpg"
                if thumbnail_path.exists():
                    thumbnail_path.unlink()
                    logger.info(f"Deleted thumbnail: {thumbnail_path}")

                # Delete settings (.yml with same name)
                settings_path = parent / f"{stem}.yml"
                if settings_path.exists():
                    settings_path.unlink()
                    logger.info(f"Deleted settings: {settings_path}")

            # Delete the main file
            full_path.unlink()
            logger.info(f"Deleted file: {full_path}")

            return jsonify({
                'success': True,
                'message': f'File deleted successfully'
            })

        else:
            return jsonify({'error': 'Path is neither a file nor a directory'}), 400

    except Exception as e:
        logger.error(f"Error deleting item: {e}")
        return jsonify({'error': str(e)}), 500


@socketio.on('start_download')
def handle_download(data):
    """Handle YouTube download request."""
    try:
        url = data.get('url', '').strip()
        target_dir = data.get('target_dir', 'data/audio_player')
        requested_playlist = data.get('playlist')

        if not url:
            emit('download_error', {'error': 'URL is required'})
            return

        # Decide single video vs. whole playlist. Ambiguous URLs (video + list)
        # require an explicit answer from the client.
        try:
            download_playlist = resolve_playlist_choice(url, requested_playlist)
        except ValueError as e:
            emit('download_error', {'error': str(e), 'needs_playlist_choice': True})
            return

        # Ensure path is relative to project root (parent of stream_toy/)
        base_path = Path(__file__).parent.parent.parent.resolve()
        full_target_dir = base_path / target_dir

        # Security: prevent directory traversal
        try:
            full_target_dir = full_target_dir.resolve()
            if not str(full_target_dir).startswith(str(base_path)):
                emit('download_error', {'error': 'Invalid target directory'})
                return
        except Exception:
            emit('download_error', {'error': 'Invalid target directory'})
            return

        # Create directory if it doesn't exist
        full_target_dir.mkdir(parents=True, exist_ok=True)

        # Start download in background thread
        thread = threading.Thread(
            target=_run_download,
            args=(url, full_target_dir, request.sid, download_playlist)
        )
        thread.daemon = True
        thread.start()

        emit('download_started', {
            'message': 'Downloading whole playlist...' if download_playlist else 'Download started',
            'playlist': download_playlist
        })

    except Exception as e:
        logger.error(f"Error starting download: {e}")
        emit('download_error', {'error': str(e)})


def _snapshot_mp3_files(target_dir: Path) -> Dict[Path, float]:
    """Map of mp3 files in target_dir to their modification time."""
    snapshot = {}
    for mp3 in target_dir.glob('*.mp3'):
        try:
            snapshot[mp3] = mp3.stat().st_mtime
        except OSError:
            continue
    return snapshot


def _find_new_mp3_files(target_dir: Path, before: Dict[Path, float]) -> List[Path]:
    """Return mp3 files that were created or overwritten since the snapshot."""
    changed = []
    for mp3, mtime in sorted(_snapshot_mp3_files(target_dir).items()):
        if mp3 not in before or before[mp3] != mtime:
            changed.append(mp3)
    return changed


def _run_download(url: str, target_dir: Path, client_sid: str, download_playlist: bool = False):
    """Run yt-dlp download and stream output to client.

    Args:
        url: YouTube video or playlist URL
        target_dir: Directory the mp3/jpg files are written to (flat, no
            per-playlist subfolder)
        client_sid: Socket.IO room to stream the log to
        download_playlist: True to download every entry of the playlist
    """
    try:
        # Get yt-dlp executable path
        ytdlp = get_ytdlp_executable()

        # Files present before the run, so we can tell afterwards which ones
        # this run produced (a playlist produces many).
        before = _snapshot_mp3_files(target_dir)

        # --yes-playlist / --no-playlist decides single video vs. whole playlist
        # --convert-thumbnails jpg converts webp and other formats to jpg for compatibility
        # --print maps each finished file to its source video (filtered from the log)
        process = subprocess.Popen(
            [
                ytdlp,
                '--extract-audio',
                '--audio-format', 'mp3',
                '--write-thumbnail',
                '--convert-thumbnails', 'jpg',
                '--yes-playlist' if download_playlist else '--no-playlist',
                '--newline',
                '--progress',
                # --print switches yt-dlp to quiet mode by default, --no-quiet
                # keeps the log lines we stream to the client
                '--print', f'after_move:{_PRINT_MARKER}\t%(filepath)s\t%(webpage_url)s',
                '--no-quiet',
                # Clean title-based name without the video ID (default template
                # is '%(title)s [%(id)s].%(ext)s'), matching tools/yt_download.py.
                # Relative to cwd, so playlist entries land flat in target_dir.
                '-o', '%(title)s.%(ext)s',
                url
            ],
            cwd=str(target_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Stream output to client, collecting the file -> source URL mapping
        file_urls: Dict[str, str] = {}
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            if line.startswith(_PRINT_MARKER + '\t'):
                parts = line.split('\t')
                if len(parts) == 3 and parts[2] and parts[2] != 'NA':
                    file_urls[Path(parts[1]).name] = parts[2]
                continue
            socketio.emit('download_log', {'line': line}, room=client_sid)

        process.wait()

        # Save metadata for every file of this run. Done even on failure: when
        # a playlist entry is unavailable yt-dlp continues with the next one
        # and still exits non-zero.
        from stream_toy.audio_metadata_service import AudioMetadataService

        downloaded = _find_new_mp3_files(target_dir, before)
        for audio_file in downloaded:
            metadata = AudioMetadataService.get_metadata(audio_file)
            # Prefer the concrete video URL over the (possibly playlist) input
            metadata.set_download_info(file_urls.get(audio_file.name, url))
            logger.info(f"Saved download metadata for {audio_file.name}")

        if process.returncode == 0:
            if download_playlist:
                message = f'Playlist download completed - {len(downloaded)} track(s)'
            else:
                message = 'Download completed successfully'

            socketio.emit('download_complete', {
                'message': message,
                'file_count': len(downloaded)
            }, room=client_sid)
        else:
            error = f'Download failed with code {process.returncode}'
            if downloaded:
                error += f' ({len(downloaded)} file(s) saved)'
            socketio.emit('download_error', {'error': error}, room=client_sid)

    except Exception as e:
        logger.error(f"Error during download: {e}")
        socketio.emit('download_error', {'error': str(e)}, room=client_sid)


def run_server(host: str = '0.0.0.0', port: int = 5000) -> None:
    """
    Run the web server (blocking).

    Args:
        host: Host address to bind
        port: Port to listen on
    """
    # Log yt-dlp location for diagnostics
    ytdlp_path = get_ytdlp_executable()
    logger.info(f"Using yt-dlp from: {ytdlp_path}")

    logger.info(f"Starting emulator web server on {host}:{port}")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
