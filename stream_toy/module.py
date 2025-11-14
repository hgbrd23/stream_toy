"""
Module system for StreamToy applications.

Provides manifest-based module loading and management.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Type, TYPE_CHECKING
import importlib.util
import logging

if TYPE_CHECKING:
    from .scene.base_scene import BaseScene

logger = logging.getLogger(__name__)


@dataclass
class ModuleManifest:
    """
    Module metadata.

    Defines information about a StreamToy module (game/app).
    """

    name: str
    version: str
    author: str
    description: str
    icon_path: str  # Relative to module directory
    main_scene: str  # Class name of main scene

    def __repr__(self) -> str:
        return f"ModuleManifest(name='{self.name}', version='{self.version}')"


class StreamToyModule:
    """
    Represents a loaded StreamToy module.

    Handles lazy loading of module code and provides access to
    manifest information.
    """

    def __init__(self, path: Path, manifest: ModuleManifest):
        """
        Initialize module.

        Args:
            path: Path to module directory
            manifest: Module manifest
        """
        self.path = path
        self.manifest = manifest
        self._main_scene_class: Type['BaseScene'] = None
        self._loaded = False

    @property
    def main_scene_class(self) -> Type['BaseScene']:
        """
        Lazy load and return main scene class.

        Returns:
            Scene class from module's main.py

        Raises:
            ImportError: If module cannot be loaded
            AttributeError: If scene class not found
        """
        if self._main_scene_class is None:
            self._load_module()
        return self._main_scene_class

    def _load_module(self) -> None:
        """Load module code."""
        if self._loaded:
            return

        logger.info(f"Loading module: {self.manifest.name}")

        try:
            # Import main.py
            main_path = self.path / "main.py"

            if not main_path.exists():
                raise ImportError(f"Module {self.manifest.name} missing main.py")

            spec = importlib.util.spec_from_file_location(
                f"stream_toy_apps.{self.path.name}.main",
                main_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get main scene class
            if not hasattr(module, self.manifest.main_scene):
                raise AttributeError(
                    f"Module {self.manifest.name} missing scene class '{self.manifest.main_scene}'"
                )

            self._main_scene_class = getattr(module, self.manifest.main_scene)
            self._loaded = True

            logger.info(f"Module loaded successfully: {self.manifest.name}")

        except Exception as e:
            logger.error(f"Failed to load module {self.manifest.name}: {e}", exc_info=True)
            raise

    def get_icon_path(self) -> Path:
        """
        Get absolute path to module icon.

        Returns:
            Path to icon file

        Raises:
            FileNotFoundError: If icon not found
        """
        icon_path = self.path / self.manifest.icon_path

        if not icon_path.exists():
            raise FileNotFoundError(f"Module icon not found: {icon_path}")

        return icon_path

    def __repr__(self) -> str:
        return f"StreamToyModule({self.manifest.name})"


def load_module_manifest(module_dir: Path) -> ModuleManifest:
    """
    Load module manifest from manifest.py.

    Args:
        module_dir: Path to module directory

    Returns:
        ModuleManifest instance

    Raises:
        ImportError: If manifest.py cannot be loaded
        AttributeError: If get_manifest() function not found
    """
    manifest_path = module_dir / "manifest.py"

    if not manifest_path.exists():
        raise ImportError(f"Module {module_dir.name} missing manifest.py")

    # Import manifest.py
    spec = importlib.util.spec_from_file_location(
        f"stream_toy_apps.{module_dir.name}.manifest",
        manifest_path
    )
    manifest_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manifest_module)

    # Get manifest
    if not hasattr(manifest_module, 'get_manifest'):
        raise AttributeError(
            f"Module {module_dir.name} manifest missing get_manifest() function"
        )

    manifest = manifest_module.get_manifest()

    if not isinstance(manifest, ModuleManifest):
        raise TypeError(
            f"Module {module_dir.name} get_manifest() must return ModuleManifest"
        )

    return manifest
