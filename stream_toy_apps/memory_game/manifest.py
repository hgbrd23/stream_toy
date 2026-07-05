"""
Memory Game Module Manifest
"""

from stream_toy.module import ModuleManifest


def get_manifest() -> ModuleManifest:
    """Return module manifest."""
    return ModuleManifest(
        name="Memory Game",
        version="1.0.0",
        author="StreamToy Team",
        description="Classic memory matching game with animals",
        icon_path="../../assets/tiles/memory_icon.png",
        main_scene="MemoryGameScene"
    )
