import os
import threading
import time
from typing import Optional

print("Hello World")


def run_demo(
        use_emulator: bool = False,
        show_gui: bool = True,
        screenshot_path: Optional[str] = None,
        visible_delay_seconds: Optional[float] = None,
    ):
    """
    Run the demo programmatically. Returns after rendering when using the emulator.
    - use_emulator: run against the built-in emulator instead of USB device
    - show_gui: when using emulator, show GUI window (Tk) if True
    - screenshot_path: when using emulator, path to save a screenshot image
    - visible_delay_seconds: when using emulator, how long to keep the GUI open before closing.
      If None, reads env var STREAMDOCK_EMULATOR_VISIBLE_DELAY; falls back to 0.2s (fast for tests).
    """
    # Fix for Segmentation Fault when access rights to USB port not available.
    # Only attempt on Linux and when not using the emulator.
    if not use_emulator and os.name != "nt":
        os.system('sudo chown root:$USER /dev/bus/usb/001/00*')

    # Propagate emulator configuration via environment, as emulator reads env
    if use_emulator:
        os.environ["STREAMDOCK_USE_EMULATOR"] = "1"
        os.environ["STREAMDOCK_EMULATOR_HEADLESS"] = "0" if show_gui else "1"
        if screenshot_path:
            os.environ["STREAMDOCK_EMULATOR_SCREENSHOT"] = screenshot_path

    # Import chosen backend lazily here to honor use_emulator flag
    if use_emulator:
        from stream_dock_emulator import DeviceManager as _DeviceManager, StreamDockN1 as _StreamDockN1
    else:
        from StreamDock.DeviceManager import DeviceManager as _DeviceManager
        from StreamDock.Devices.StreamDockN1 import StreamDockN1 as _StreamDockN1

    manner = _DeviceManager()
    streamdocks = manner.enumerate()

    # listen plug/unplug (background)
    listen_thread = threading.Thread(target=manner.listen)
    listen_thread.daemon = True
    listen_thread.start()

    print("Found {} Stream Dock(s).".format(len(streamdocks)))
    read_threads = []
    for device in streamdocks:
        print("Opening")
        # open device
        device.open()
        print("Init")
        device.init()
        device.set_brightness(10)
        print("Thread")
        # new thread to get device's feedback
        t = threading.Thread(target=device.whileread)
        t.daemon = True
        t.start()
        read_threads.append(t)
        # set background image
        print("set background image")
        # Optional: set full-screen background in emulator via env var
        if use_emulator:
            bg_path = os.getenv("STREAMDOCK_EMULATOR_BG")
            if bg_path and hasattr(device, "set_touchscreen_image"):
                try:
                    device.set_touchscreen_image(bg_path)
                    device.refresh()
                except Exception:
                    pass
        # Resolve assets directory relative to this file to be robust to CWD
        assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img", "memory", "set_01")
        for i in range(1, 16):
            img_path = os.path.join(assets_dir, "animal_{:02d}.png".format(i % 9 + 1))
            device.set_key_image(i, img_path)
            device.refresh()
        # Give some time for any async rendering
        time.sleep(0.2 if use_emulator else 2)
        # N1 switch mode
        if isinstance(device, _StreamDockN1):
            device.switch_mode(0)

    # In emulator mode, optionally keep the GUI visible before shutting down
    if use_emulator:
        # Determine how long to keep the window visible
        delay = 0.2
        if visible_delay_seconds is not None:
            try:
                delay = float(visible_delay_seconds)
            except Exception:
                delay = 0.2
        else:
            env_delay = os.getenv("STREAMDOCK_EMULATOR_VISIBLE_DELAY")
            if env_delay:
                try:
                    delay = float(env_delay)
                except Exception:
                    delay = 0.2
        # If emulator device provides a blocking GUI show, use it on the main thread
        try:
            for device in streamdocks:
                wait_visible = getattr(device, "wait_visible", None)
                if callable(wait_visible):
                    wait_visible(max(0.0, delay))
                else:
                    time.sleep(max(0.0, delay))
        except Exception:
            time.sleep(max(0.0, delay))
        # Attempt to close devices to stop threads if supported
        try:
            for device in streamdocks:
                close = getattr(device, "close", None)
                if callable(close):
                    close()
        except Exception:
            pass
        return

    # On real hardware, keep the app running
    time.sleep(10000)


if __name__ == "__main__":
    # Determine options from environment for CLI usage
    use_emul = os.getenv("STREAMDOCK_USE_EMULATOR", "0") == "1"
    show_gui = os.getenv("STREAMDOCK_EMULATOR_HEADLESS", "0") != "1"
    screenshot = os.getenv("STREAMDOCK_EMULATOR_SCREENSHOT")
    run_demo(use_emulator=use_emul, show_gui=show_gui, screenshot_path=screenshot)