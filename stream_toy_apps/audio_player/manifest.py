"""
Audio Player App Manifest
"""

from stream_toy.module import ModuleManifest


def get_manifest() -> ModuleManifest:
    """Return module manifest."""
    return ModuleManifest(
        name="Audio Player",
        version="1.0.0",
        author="StreamToy",
        description="Browse and play audio files from folders",
        icon_path="assets/icon.png",
        main_scene="AudioPlayerScene"
    )
