"""
Reaction Game Module Manifest
"""

from stream_toy.module import ModuleManifest


def get_manifest() -> ModuleManifest:
    """Return module manifest."""
    return ModuleManifest(
        name="Reaction",
        version="1.0.0",
        author="StreamToy Team",
        description="Test your reaction time - hit the button when it lights up!",
        icon_path="icon.png",
        main_scene="ReactionGameScene"
    )
