"""
StreamToy Runtime Manager.

Central coordinator for the entire StreamToy system.
Manages devices, modules, scenes, and system lifecycle.
"""

import asyncio
from pathlib import Path
from typing import List, Optional, Type
import logging
import sys

from .device.stream_toy_device import StreamToyDevice
from .device.streamdock293v3_device import StreamDock293V3Device
from .device.web_device import WebDevice
from .input_manager import InputManager
from .module import StreamToyModule, load_module_manifest
from .scene.base_scene import BaseScene
from .scene.module_launch_scene import ModuleLaunchScene

logger = logging.getLogger(__name__)


class StreamToyRuntime:
    """
    Central runtime manager for StreamToy.

    Handles:
    - Device initialization (hardware and/or web)
    - Module loading and management
    - Scene lifecycle and transitions
    - System shutdown
    """

    def __init__(self, enable_hardware: bool = True, enable_web: bool = True, web_port: int = 5000):
        """
        Initialize runtime.

        Args:
            enable_hardware: Enable real StreamDock hardware
            enable_web: Enable web emulator
            web_port: Port for web emulator (default: 5000)
        """
        self.enable_hardware = enable_hardware
        self.enable_web = enable_web
        self.web_port = web_port

        self.devices: List[StreamToyDevice] = []
        self.device: Optional[StreamToyDevice] = None  # Primary device
        self.input_manager = InputManager()
        self.modules: List[StreamToyModule] = []

        self.current_scene: Optional[BaseScene] = None
        self.scene_stack: List[BaseScene] = []

        self._running = False
        self._main_task: Optional[asyncio.Task] = None
        self._scene_task: Optional[asyncio.Task] = None

    def initialize(self) -> None:
        """
        Initialize devices and load modules.

        Raises:
            RuntimeError: If no devices available
        """
        logger.info("Initializing StreamToy Runtime")
        logger.info(f"Hardware enabled: {self.enable_hardware}, Web enabled: {self.enable_web}")

        # Initialize hardware device
        if self.enable_hardware:
            try:
                logger.info("Initializing hardware device...")
                hw_device = StreamDock293V3Device()
                hw_device.initialize()
                hw_device.initialize_sound(sample_rate=48000)  # Match ALSA config
                hw_device.register_key_callback(self.input_manager.on_device_key_event)
                self.devices.append(hw_device)
                logger.info("Hardware device initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize hardware device: {e}", exc_info=True)
                if not self.enable_web:
                    raise RuntimeError(f"Hardware initialization failed and web disabled: {e}")

        # Initialize web device
        if self.enable_web:
            try:
                logger.info("Initializing web emulator...")
                web_device = WebDevice(port=self.web_port)
                web_device.initialize()
                web_device.initialize_sound(sample_rate=48000)  # Match ALSA config
                web_device.register_key_callback(self.input_manager.on_device_key_event)
                self.devices.append(web_device)
                logger.info(f"Web emulator initialized successfully at http://0.0.0.0:{self.web_port}")
            except Exception as e:
                logger.error(f"Failed to initialize web device: {e}", exc_info=True)
                if not self.enable_hardware or not self.devices:
                    raise RuntimeError(f"Web initialization failed: {e}")

        # Verify at least one device available
        if not self.devices:
            raise RuntimeError("No devices available! Enable hardware or web emulator.")

        # Use first device as primary
        self.device = self.devices[0]
        logger.info(f"Primary device: {type(self.device).__name__}")

        # Load all modules
        self.load_modules()

        logger.info("StreamToy Runtime initialized successfully")

    def load_modules(self) -> None:
        """Scan and load all modules from stream_toy_apps/."""
        logger.info("Loading modules...")

        # Find apps directory
        apps_dir = Path(__file__).parent.parent / "stream_toy_apps"

        if not apps_dir.exists():
            logger.warning(f"Apps directory not found: {apps_dir}")
            apps_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created apps directory: {apps_dir}")
            return

        # Scan for modules
        module_count = 0

        for module_dir in apps_dir.iterdir():
            if not module_dir.is_dir():
                continue

            manifest_path = module_dir / "manifest.py"
            if not manifest_path.exists():
                logger.debug(f"Skipping {module_dir.name} (no manifest.py)")
                continue

            try:
                # Load manifest
                manifest = load_module_manifest(module_dir)

                # Create module
                module = StreamToyModule(module_dir, manifest)
                self.modules.append(module)

                logger.info(f"Loaded module: {manifest.name} v{manifest.version} by {manifest.author}")
                module_count += 1

            except Exception as e:
                logger.error(f"Failed to load module {module_dir.name}: {e}", exc_info=True)

        logger.info(f"Loaded {module_count} module(s)")

    def get_available_modules(self) -> List[StreamToyModule]:
        """
        Get all loaded modules.

        Returns:
            List of StreamToyModule instances
        """
        return self.modules

    def switch_scene(self, scene_class: Type[BaseScene], **kwargs) -> None:
        """
        Request scene transition.

        Args:
            scene_class: Class of scene to switch to
            **kwargs: Arguments to pass to scene constructor
        """
        logger.info(f"Scene switch requested: {scene_class.__name__}")

        # Create task to perform switch
        asyncio.create_task(self._switch_scene_async(scene_class, **kwargs))

    async def _switch_scene_async(self, scene_class: Type[BaseScene], **kwargs) -> None:
        """
        Internal async scene switching.

        Args:
            scene_class: Class of scene to switch to
            **kwargs: Arguments to pass to scene constructor
        """
        logger.debug(f"Performing scene switch to {scene_class.__name__}")

        # Exit current scene
        if self.current_scene:
            logger.debug(f"Exiting scene: {type(self.current_scene).__name__}")
            self.current_scene._running = False

            # Cancel scene task
            if self._scene_task and not self._scene_task.done():
                self._scene_task.cancel()
                try:
                    await self._scene_task
                except asyncio.CancelledError:
                    pass

            try:
                await self.current_scene.on_exit()
            except Exception as e:
                logger.error(f"Error in scene on_exit: {e}", exc_info=True)

        # Create new scene
        try:
            self.current_scene = scene_class(self, **kwargs)
            self.current_scene._running = True

            # Enter new scene
            logger.debug(f"Entering scene: {scene_class.__name__}")
            await self.current_scene.on_enter()

            # Start scene main loop
            self._scene_task = asyncio.create_task(self._run_scene_loop())

            logger.info(f"Scene switch complete: {scene_class.__name__}")

        except Exception as e:
            logger.error(f"Failed to switch to scene {scene_class.__name__}: {e}", exc_info=True)
            # TODO: Switch to error scene

    async def _run_scene_loop(self) -> None:
        """Run current scene's main loop."""
        logger.info(f"[RUNTIME] Starting scene loop for {type(self.current_scene).__name__}")
        try:
            await self.current_scene.main_loop()
            logger.info(f"[RUNTIME] Scene loop exited normally for {type(self.current_scene).__name__}")
        except asyncio.CancelledError:
            logger.debug("[RUNTIME] Scene loop cancelled")
        except Exception as e:
            logger.error(f"[RUNTIME] Error in scene main loop: {e}", exc_info=True)
            # TODO: Switch to error scene

    async def run(self) -> None:
        """
        Main runtime loop (async).

        Runs until shutdown is requested.
        """
        logger.info("Starting StreamToy Runtime")
        self._running = True

        # Start with module launch scene
        await self._switch_scene_async(ModuleLaunchScene)

        # Keep runtime alive
        logger.debug("Runtime main loop started")
        try:
            while self._running:
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            logger.info("Runtime loop cancelled")

        logger.info("Runtime loop ended")

    def start(self) -> None:
        """
        Start the runtime (blocking).

        This is the main entry point for the application.
        """
        try:
            # Initialize system
            self.initialize()

            logger.info("Initialization complete, starting async runtime...")

            # Run async event loop
            asyncio.run(self.run())

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Runtime error: {e}", exc_info=True)
            raise
        finally:
            # Cleanup
            self.shutdown()

    def shutdown(self) -> None:
        """Graceful shutdown of the system."""
        logger.info("Shutting down StreamToy Runtime")

        # Stop running
        self._running = False

        # Close all devices
        for device in self.devices:
            try:
                logger.debug(f"Closing device: {type(device).__name__}")
                device.close_sound()  # Close sound manager first
                device.close()
            except Exception as e:
                logger.error(f"Error closing device: {e}", exc_info=True)

        logger.info("StreamToy Runtime shutdown complete")
        sys.exit(0)
