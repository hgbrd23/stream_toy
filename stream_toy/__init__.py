"""
StreamToy - A modular game framework for StreamDock devices.

This library provides device abstraction, scene management, and a module system
for creating interactive games and applications on StreamDock hardware.
"""

__version__ = "1.0.0"
__author__ = "StreamToy Team"

from .runtime import StreamToyRuntime

__all__ = ['StreamToyRuntime']
