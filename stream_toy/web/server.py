"""
Web server for StreamToy emulator.

Provides Flask + Socket.IO server for real-time device emulation.
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import base64
from io import BytesIO
import logging
from typing import Optional, List, Tuple
from pathlib import Path
import subprocess
import json
import threading
import sys
import shutil

logger = logging.getLogger(__name__)


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


@app.route('/api/youtube/title', methods=['POST'])
def get_youtube_title():
    """Get video title from YouTube URL."""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()

        if not url:
            return jsonify({'error': 'URL is required'}), 400

        # Use yt-dlp to get video title (much faster than --dump-json)
        # --no-playlist ensures we only get the single video, not the entire playlist
        ytdlp = get_ytdlp_executable()
        result = subprocess.run(
            [ytdlp, '--print', '%(title)s', '--no-warnings', '--no-playlist', url],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else 'Failed to fetch video information'
            logger.error(f"yt-dlp error: {error_msg}")
            return jsonify({'error': 'Failed to fetch video information'}), 400

        title = result.stdout.strip()
        if not title:
            return jsonify({'error': 'No title found'}), 400

        return jsonify({'title': title})

    except subprocess.TimeoutExpired:
        logger.error(f"yt-dlp timeout for URL: {url}")
        return jsonify({'error': 'Request timed out - YouTube may be slow or unreachable'}), 408
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


@socketio.on('start_download')
def handle_download(data):
    """Handle YouTube download request."""
    try:
        url = data.get('url', '').strip()
        target_dir = data.get('target_dir', 'data/audio_player')

        if not url:
            emit('download_error', {'error': 'URL is required'})
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
            args=(url, full_target_dir, request.sid)
        )
        thread.daemon = True
        thread.start()

        emit('download_started', {'message': 'Download started'})

    except Exception as e:
        logger.error(f"Error starting download: {e}")
        emit('download_error', {'error': str(e)})


def _run_download(url: str, target_dir: Path, client_sid: str):
    """Run yt-dlp download and stream output to client."""
    try:
        # Get yt-dlp executable path
        ytdlp = get_ytdlp_executable()

        # Run yt-dlp with progress output
        # --no-playlist ensures we only download the single video, not the entire playlist
        # --convert-thumbnails jpg converts webp and other formats to jpg for compatibility
        process = subprocess.Popen(
            [
                ytdlp,
                '--extract-audio',
                '--audio-format', 'mp3',
                '--write-thumbnail',
                '--convert-thumbnails', 'jpg',
                '--no-playlist',
                '--newline',
                '--progress',
                url
            ],
            cwd=str(target_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Stream output to client
        for line in process.stdout:
            line = line.strip()
            if line:
                socketio.emit('download_log', {'line': line}, room=client_sid)

        process.wait()

        if process.returncode == 0:
            # Download succeeded - save metadata
            from stream_toy.audio_metadata_service import AudioMetadataService

            # Find the downloaded file (most recent mp3)
            mp3_files = sorted(target_dir.glob('*.mp3'), key=lambda p: p.stat().st_mtime, reverse=True)
            if mp3_files:
                audio_file = mp3_files[0]
                metadata = AudioMetadataService.get_metadata(audio_file)
                metadata.set_download_info(url)
                logger.info(f"Saved download metadata for {audio_file.name}")

            socketio.emit('download_complete', {'message': 'Download completed successfully'}, room=client_sid)
        else:
            socketio.emit('download_error', {'error': f'Download failed with code {process.returncode}'}, room=client_sid)

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
