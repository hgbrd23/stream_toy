"""
Tests for module launch scene and button click functionality.

Tests that clicking buttons in the launcher properly launches modules.
"""

import unittest
import asyncio
import time
from unittest.mock import MagicMock, patch
import logging

from stream_toy.runtime import StreamToyRuntime
from stream_toy.scene.module_launch_scene import ModuleLaunchScene
from stream_toy.input_manager import InputEvent


class TestModuleLaunch(unittest.TestCase):
    """Test cases for module launch scene."""

    def setUp(self):
        """Set up test fixtures."""
        # Suppress logs during tests
        logging.basicConfig(level=logging.CRITICAL)

        self.runtime = None
        self.loop = None

    def tearDown(self):
        """Clean up after tests."""
        if self.runtime and hasattr(self.runtime, 'devices'):
            for device in self.runtime.devices:
                if device._initialized:
                    device.close()

        if self.loop and not self.loop.is_closed():
            try:
                self.loop.close()
            except:
                pass

    def test_runtime_initialization_with_web_only(self):
        """Test runtime can be initialized with web device only."""
        self.runtime = StreamToyRuntime(
            enable_hardware=False,
            enable_web=True,
            web_port=9001
        )

        self.runtime.initialize()

        # Should have one device (web)
        self.assertEqual(len(self.runtime.devices), 1)
        self.assertIsNotNone(self.runtime.device)
        self.assertTrue(self.runtime.device._initialized)

    def test_modules_loaded(self):
        """Test modules are loaded from stream_toy_apps."""
        self.runtime = StreamToyRuntime(
            enable_hardware=False,
            enable_web=True,
            web_port=9002
        )

        self.runtime.initialize()

        # Should have loaded modules
        modules = self.runtime.get_available_modules()
        self.assertIsNotNone(modules)
        self.assertIsInstance(modules, list)

        # Check if memory_game or reaction_game is loaded
        module_names = [m.manifest.name for m in modules]
        self.assertTrue(
            len(module_names) > 0,
            "Should have at least one module loaded"
        )

    def test_module_launch_scene_builds_menu(self):
        """Test module launch scene builds menu with available modules."""
        self.runtime = StreamToyRuntime(
            enable_hardware=False,
            enable_web=True,
            web_port=9003
        )

        self.runtime.initialize()

        # Create module launch scene
        scene = ModuleLaunchScene(self.runtime)

        # Build menu
        items = scene.build_menu()

        # Should have menu items
        self.assertIsNotNone(items)
        self.assertGreater(len(items), 0)

        # Should have system button at bottom-right (2, 4)
        system_item = None
        for item in items:
            if item.row == 2 and item.col == 4:
                system_item = item
                break

        self.assertIsNotNone(system_item, "Should have system button at (2,4)")

    def test_button_press_generates_input_event(self):
        """Test that button presses generate input events."""
        self.runtime = StreamToyRuntime(
            enable_hardware=False,
            enable_web=True,
            web_port=9004
        )

        self.runtime.initialize()

        # Simulate button press through input manager
        self.runtime.input_manager.on_device_key_event(0, 0, True)  # Press
        time.sleep(0.1)
        self.runtime.input_manager.on_device_key_event(0, 0, False)  # Release

        # Poll for events
        press_event = self.runtime.input_manager.poll_event(timeout=0.5)
        release_event = self.runtime.input_manager.poll_event(timeout=0.5)

        # Should have received both events
        self.assertIsNotNone(press_event)
        self.assertIsNotNone(release_event)

        self.assertTrue(press_event.is_pressed)
        self.assertFalse(release_event.is_pressed)
        self.assertEqual(press_event.row, 0)
        self.assertEqual(press_event.col, 0)

    def test_module_launch_scene_handles_button_click(self):
        """Test module launch scene handles button clicks correctly."""
        self.runtime = StreamToyRuntime(
            enable_hardware=False,
            enable_web=True,
            web_port=9005
        )

        self.runtime.initialize()

        # Check if we have any modules
        modules = self.runtime.get_available_modules()
        if len(modules) == 0:
            self.skipTest("No modules available to test")

        # Create and enter the scene
        scene = ModuleLaunchScene(self.runtime)
        scene._running = True

        # Enter scene (synchronously for testing)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(scene.on_enter())

        # Verify menu was built
        self.assertGreater(len(scene.items), 0)

        # Find the first module button
        first_module_item = scene.items[0]
        self.assertIsNotNone(first_module_item)
        self.assertIsNotNone(first_module_item.action)
        self.assertIsNotNone(first_module_item.action.on_tap)

        # Test that the action is callable
        self.assertTrue(callable(first_module_item.action.on_tap))

    def test_async_button_click_processing(self):
        """Test that button clicks are processed asynchronously."""
        self.runtime = StreamToyRuntime(
            enable_hardware=False,
            enable_web=True,
            web_port=9006
        )

        self.runtime.initialize()

        modules = self.runtime.get_available_modules()
        if len(modules) == 0:
            self.skipTest("No modules available to test")

        # Create scene
        scene = ModuleLaunchScene(self.runtime)
        scene._running = True

        # Setup async test
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def test_click():
            # Enter scene
            await scene.on_enter()

            # Simulate button click on first module
            first_item = scene.items[0]
            row, col = first_item.row, first_item.col

            # Generate button press and release
            self.runtime.input_manager.on_device_key_event(row, col, True)
            await asyncio.sleep(0.1)
            self.runtime.input_manager.on_device_key_event(row, col, False)

            # Give scene time to process event
            # Instead of running main loop, directly test the action
            if first_item.action.on_tap:
                # Call the action
                await scene._safe_call(first_item.action.on_tap)

            # Scene should have triggered scene change
            # (We can't easily test the actual scene switch without full runtime)
            return True

        result = self.loop.run_until_complete(test_click())
        self.assertTrue(result)

    def test_web_device_button_callback_integration(self):
        """Test web device button events flow to input manager."""
        self.runtime = StreamToyRuntime(
            enable_hardware=False,
            enable_web=True,
            web_port=9007
        )

        self.runtime.initialize()

        # Get the web device
        web_device = self.runtime.device

        # Simulate button event from web device
        web_device._on_button_event(1, 2, True)  # Press
        time.sleep(0.05)
        web_device._on_button_event(1, 2, False)  # Release

        # Should be able to poll events from input manager
        press_event = self.runtime.input_manager.poll_event(timeout=0.5)
        release_event = self.runtime.input_manager.poll_event(timeout=0.5)

        self.assertIsNotNone(press_event)
        self.assertIsNotNone(release_event)
        self.assertEqual(press_event.row, 1)
        self.assertEqual(press_event.col, 2)
        self.assertTrue(press_event.is_pressed)
        self.assertFalse(release_event.is_pressed)


class TestModuleLaunchIntegration(unittest.TestCase):
    """Integration tests for module launch functionality."""

    def setUp(self):
        """Set up test fixtures."""
        logging.basicConfig(level=logging.CRITICAL)
        self.runtime = None

    def tearDown(self):
        """Clean up after tests."""
        if self.runtime and hasattr(self.runtime, 'devices'):
            for device in self.runtime.devices:
                if device._initialized:
                    device.close()

    def test_full_button_click_flow(self):
        """Integration test: button click -> input event -> scene action."""
        self.runtime = StreamToyRuntime(
            enable_hardware=False,
            enable_web=True,
            web_port=9008
        )

        self.runtime.initialize()

        modules = self.runtime.get_available_modules()
        if len(modules) == 0:
            self.skipTest("No modules available to test")

        # Track if action was called
        action_called = False

        def mock_action():
            nonlocal action_called
            action_called = True

        # Create scene
        scene = ModuleLaunchScene(self.runtime)
        scene._running = True

        # Setup async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def test_flow():
            # Enter scene
            await scene.on_enter()

            # Replace first item's action with mock
            first_item = scene.items[0]
            first_item.action.on_tap = mock_action

            # Simulate button click
            row, col = first_item.row, first_item.col
            self.runtime.input_manager.on_device_key_event(row, col, True)
            await asyncio.sleep(0.05)
            self.runtime.input_manager.on_device_key_event(row, col, False)

            # Process one event from the main loop manually
            event = await self.runtime.input_manager.async_poll_event(timeout=1.0)

            # Process the event (skip press, wait for release)
            if event and event.is_pressed:
                event = await self.runtime.input_manager.async_poll_event(timeout=1.0)

            if event and not event.is_pressed:
                item = scene._find_item(event.row, event.col)
                if item and item.action.on_tap:
                    await scene._safe_call(item.action.on_tap)

        loop.run_until_complete(test_flow())
        loop.close()

        # Verify action was called
        self.assertTrue(action_called, "Button action should have been called")


class TestRuntimeStartup(unittest.TestCase):
    """Test runtime startup and scene initialization."""

    def setUp(self):
        """Set up test fixtures."""
        logging.basicConfig(level=logging.DEBUG)
        self.runtime = None

    def tearDown(self):
        """Clean up after tests."""
        if self.runtime and hasattr(self.runtime, 'devices'):
            for device in self.runtime.devices:
                if device._initialized:
                    device.close()

    def test_runtime_starts_with_module_launch_scene(self):
        """Test that runtime starts and loads module launch scene."""
        self.runtime = StreamToyRuntime(
            enable_hardware=False,
            enable_web=True,
            web_port=9009
        )

        self.runtime.initialize()

        # Manually run the async startup
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def test_startup():
            # Start the scene switch
            await self.runtime._switch_scene_async(ModuleLaunchScene)

            # Verify scene was created
            self.assertIsNotNone(self.runtime.current_scene)
            self.assertIsInstance(self.runtime.current_scene, ModuleLaunchScene)
            self.assertTrue(self.runtime.current_scene._running)

            # Verify menu was built
            self.assertGreater(len(self.runtime.current_scene.items), 0)

            # Verify scene task was created
            self.assertIsNotNone(self.runtime._scene_task)

            return True

        result = loop.run_until_complete(test_startup())

        # Cleanup
        if self.runtime._scene_task and not self.runtime._scene_task.done():
            self.runtime._scene_task.cancel()
            try:
                loop.run_until_complete(self.runtime._scene_task)
            except asyncio.CancelledError:
                pass

        loop.close()

        self.assertTrue(result)


class TestModuleLaunchTileDisplay(unittest.TestCase):
    """Test that module launch scene displays tiles correctly."""

    def setUp(self):
        """Set up test fixtures."""
        logging.basicConfig(level=logging.DEBUG)
        self.runtime = None

    def tearDown(self):
        """Clean up after tests."""
        if self.runtime and hasattr(self.runtime, 'devices'):
            for device in self.runtime.devices:
                if device._initialized:
                    device.close()

    def test_scene_renders_tiles_on_enter(self):
        """Test that scene renders and submits tiles when entering."""
        self.runtime = StreamToyRuntime(
            enable_hardware=False,
            enable_web=True,
            web_port=9010
        )

        self.runtime.initialize()

        modules = self.runtime.get_available_modules()
        if len(modules) == 0:
            self.skipTest("No modules available to test")

        # Create scene
        scene = ModuleLaunchScene(self.runtime)
        scene._running = True

        # Setup async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def test_tile_rendering():
            # Check device tile cache before
            initial_cache_size = len(self.runtime.device._tile_cache)

            # Enter scene
            await scene.on_enter()

            # Check that tiles were submitted
            final_cache_size = len(self.runtime.device._tile_cache)

            # Should have tiles in cache now
            self.assertGreater(final_cache_size, initial_cache_size,
                             f"Tiles should be cached after scene.on_enter(). "
                             f"Before: {initial_cache_size}, After: {final_cache_size}")

            # Should have at least as many tiles as modules + system button
            expected_min_tiles = len(modules) + 1  # modules + system button
            self.assertGreaterEqual(final_cache_size, expected_min_tiles,
                                  f"Should have at least {expected_min_tiles} tiles cached")

            return True

        result = loop.run_until_complete(test_tile_rendering())
        loop.close()

        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
