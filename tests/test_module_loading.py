"""
Unit tests for module loading system
"""

import unittest
from pathlib import Path
from stream_toy.module import ModuleManifest, StreamToyModule, load_module_manifest


class TestModuleManifest(unittest.TestCase):
    """Test ModuleManifest dataclass."""

    def test_manifest_creation(self):
        """Test creating a manifest."""
        manifest = ModuleManifest(
            name="Test Module",
            version="1.0.0",
            author="Test Author",
            description="Test description",
            icon_path="icon.png",
            main_scene="TestScene"
        )

        self.assertEqual(manifest.name, "Test Module")
        self.assertEqual(manifest.version, "1.0.0")
        self.assertEqual(manifest.author, "Test Author")


class TestModuleLoading(unittest.TestCase):
    """Test module loading functionality."""

    def test_load_memory_game_manifest(self):
        """Test loading memory game manifest."""
        module_dir = Path(__file__).parent.parent / "stream_toy_apps" / "memory_game"

        if not module_dir.exists():
            self.skipTest("Memory game module not found")

        manifest = load_module_manifest(module_dir)

        self.assertEqual(manifest.name, "Memory Game")
        self.assertEqual(manifest.version, "1.0.0")
        self.assertEqual(manifest.main_scene, "MemoryGameScene")

    def test_load_reaction_game_manifest(self):
        """Test loading reaction game manifest."""
        module_dir = Path(__file__).parent.parent / "stream_toy_apps" / "reaction_game"

        if not module_dir.exists():
            self.skipTest("Reaction game module not found")

        manifest = load_module_manifest(module_dir)

        self.assertEqual(manifest.name, "Reaction")
        self.assertEqual(manifest.main_scene, "ReactionGameScene")


if __name__ == '__main__':
    unittest.main()
