"""
LED Playground Module Manifest
"""

from stream_toy.module import ModuleManifest


def get_manifest() -> ModuleManifest:
    """Return module manifest."""
    return ModuleManifest(
        name="LED Playground",
        version="1.0.0",
        author="StreamToy Team",
        description="Interactive LED effects playground with customizable animations",
        icon_path="icon.png",
        main_scene="LEDPlaygroundScene"
    )
