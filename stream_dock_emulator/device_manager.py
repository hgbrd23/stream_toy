import os
import time
from .devices import StreamDockN1


class DeviceManager:
    """
    Minimal emulator of the SDK's DeviceManager.
    - enumerate(): returns a list with a single emulated StreamDockN1
    - listen(): dummy hotplug listener (keeps thread alive)
    """

    def __init__(self, transport=None):
        self.transport = transport
        self._devices = []
        self._inited = False

    def enumerate(self):
        if not self._inited:
            # Create a single emulated device
            headless = os.getenv("STREAMDOCK_EMULATOR_HEADLESS", "0") == "1"
            screenshot_path = os.getenv("STREAMDOCK_EMULATOR_SCREENSHOT")
            self._devices = [StreamDockN1(headless=headless, screenshot_path=screenshot_path)]
            self._inited = True
        return self._devices

    def listen(self):
        # Keep thread alive to mimic hot-plug monitoring
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            return
