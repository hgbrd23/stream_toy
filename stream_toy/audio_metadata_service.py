"""
Audio metadata service for audio files.

Manages YAML metadata files alongside audio files, storing:
- Download information (URL, timestamp)
- Playback information (last play time, current position)
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AudioMetadata:
    """Represents metadata for an audio file."""

    def __init__(self, audio_file: Path):
        """
        Initialize metadata for an audio file.

        Args:
            audio_file: Path to the audio file
        """
        self.audio_file = audio_file
        self.metadata_file = audio_file.with_suffix(audio_file.suffix + '.yml')
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load metadata from YAML file if it exists."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self._data = yaml.safe_load(f) or {}
                logger.debug(f"Loaded metadata from {self.metadata_file}")
            except Exception as e:
                logger.error(f"Failed to load metadata from {self.metadata_file}: {e}")
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        """Save metadata to YAML file."""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(self._data, f, default_flow_style=False, allow_unicode=True)
            logger.debug(f"Saved metadata to {self.metadata_file}")
        except Exception as e:
            logger.error(f"Failed to save metadata to {self.metadata_file}: {e}")

    # Download metadata

    def set_download_info(self, url: str, timestamp: Optional[datetime] = None) -> None:
        """
        Set download information.

        Args:
            url: Download URL
            timestamp: Download timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        self._data['download'] = {
            'url': url,
            'timestamp': timestamp.isoformat()
        }
        self._save()
        logger.info(f"Set download info for {self.audio_file.name}: {url}")

    def get_download_url(self) -> Optional[str]:
        """Get download URL if available."""
        return self._data.get('download', {}).get('url')

    def get_download_timestamp(self) -> Optional[datetime]:
        """Get download timestamp if available."""
        ts = self._data.get('download', {}).get('timestamp')
        if ts:
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                return None
        return None

    # Playback metadata

    def set_last_play_time(self, timestamp: Optional[datetime] = None) -> None:
        """
        Set last play time.

        Args:
            timestamp: Play timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        if 'playback' not in self._data:
            self._data['playback'] = {}

        self._data['playback']['last_play_time'] = timestamp.isoformat()
        self._save()
        logger.debug(f"Set last play time for {self.audio_file.name}")

    def get_last_play_time(self) -> Optional[datetime]:
        """Get last play time if available."""
        ts = self._data.get('playback', {}).get('last_play_time')
        if ts:
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                return None
        return None

    def set_playback_position(self, position: float) -> None:
        """
        Set current playback position in seconds.

        Args:
            position: Position in seconds
        """
        if 'playback' not in self._data:
            self._data['playback'] = {}

        self._data['playback']['position'] = position
        self._save()
        logger.debug(f"Set playback position for {self.audio_file.name}: {position:.1f}s")

    def get_playback_position(self) -> Optional[float]:
        """Get saved playback position if available."""
        return self._data.get('playback', {}).get('position')

    def clear_playback_position(self) -> None:
        """Clear saved playback position (called when playback finishes)."""
        if 'playback' in self._data and 'position' in self._data['playback']:
            del self._data['playback']['position']
            self._save()
            logger.debug(f"Cleared playback position for {self.audio_file.name}")


class AudioMetadataService:
    """Service for managing audio file metadata."""

    @staticmethod
    def get_metadata(audio_file: Path) -> AudioMetadata:
        """
        Get metadata for an audio file.

        Args:
            audio_file: Path to audio file

        Returns:
            AudioMetadata instance
        """
        return AudioMetadata(audio_file)
