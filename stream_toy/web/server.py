"""
Web server for StreamToy emulator.

Provides Flask + Socket.IO server for real-time device emulation.
"""

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import base64
from io import BytesIO
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

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


def run_server(host: str = '0.0.0.0', port: int = 5000) -> None:
    """
    Run the web server (blocking).

    Args:
        host: Host address to bind
        port: Port to listen on
    """
    logger.info(f"Starting emulator web server on {host}:{port}")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
