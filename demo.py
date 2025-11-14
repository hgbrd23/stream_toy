import os
import sys
import threading
import time
import subprocess
from typing import Optional, List
import logging

# Ensure StreamDock SDK is on path
SDK_PATH = os.path.join(os.path.dirname(__file__), "StreamDock-Device-SDK", "Python-Linux-SDK", "src")
if SDK_PATH not in sys.path:
    sys.path.insert(0, SDK_PATH)

from StreamDock.Transport import LibUSBHIDAPI

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)

_logger.info("Hello World")



def run_demo():
    # Set USB device permissions
    subprocess.run('sudo chown root:$USER /dev/bus/usb/001/00*', check=True, shell=True)

    from StreamDock.DeviceManager import DeviceManager as _DeviceManager
    from StreamDock.Devices.StreamDock293V3 import StreamDock293V3

    manner = _DeviceManager()
    streamdocks: List[StreamDock293V3] = manner.enumerate()

    # listen plug/unplug (background)
    listen_thread = threading.Thread(target=manner.listen)
    listen_thread.daemon = True
    listen_thread.start()

    curr_device = None

    device_busy = False

    def read_callback():
        nonlocal device_busy
        run_read_thread = True
        while run_read_thread:
            try:
                arr=curr_device.read()
                _logger.info("[demo] read callback: %s", arr)
                if arr[3] == 0 and arr[4] == 0:
                    _logger.info("[demo] device READY")
                    device_busy = False

                if len(arr) >= 10:
                    if arr[9]==0xFF:
                        pass
                        #print("写入成功")
                    else:
                        #k = KEY_MAPPING[arr[9]]
                        new = arr[10]
                        if new == 0x02:
                            new = 0
                        if new == 0x01:
                            new = 1
                        #if self.key_callback is not None:
                        #    self.key_callback(self, k, new)
                # else:
                #     print("read control", arr)
                del arr
            except Exception:
                _logger.exception("[demo] read callback failed")
                curr_device.run_read_thread = False
                curr_device.close()

    def dummy_method(*args, **kwargs):
        return

    _logger.info("Found {} Stream Dock(s).".format(len(streamdocks)))
    read_threads = []
    for device in streamdocks:
        curr_device = device
        # So the read thread is not started and we can use our own
        device._setup_reader = dummy_method
        _logger.info("Opening")

        #device.set_key_callback(key_callback)
        # open device
        _logger.info(device.open())
        _logger.info("Init")
        device.init()

        #device.run_read_thread = False
        #device.set_brightness(30)
        _logger.info("Thread")
        # new thread to get device's feedback
        t = threading.Thread(target=read_callback)
        t.daemon = True
        t.start()
        read_threads.append(t)
        # set background image
        _logger.info("set background image")
        # Log device class and touchscreen format if available
        try:
            dev_cls = type(device).__name__
            _logger.info(f"[demo] device class: {dev_cls}")
            fmt = getattr(device, "touchscreen_image_format", None)
            if callable(fmt):
                _logger.info(f"[demo] touchscreen format: {fmt()}")
        except Exception:
            pass
        # Decide which background to show and how to send it
        project_root = os.path.dirname(os.path.abspath(__file__))
        bg_path_to_use = None

        # Optional: FPS flip test (real device performance)
        fps_test = os.getenv("STREAMDOCK_FPS_TEST", "0") == "1"
        if fps_test:
            W, H = 800, 480
            fps_img = os.path.join(project_root, "StreamDock-Device-SDK", "Python-Linux-SDK", "img", "bg.png")
            iters = int(os.getenv("STREAMDOCK_FPS_ITERS", "10") or "10")
            _logger.info(f"[fps] Starting flip test: iterations={iters}, size={W}x{H}")
            t0 = time.perf_counter()
            per = []
            for i in range(iters):
                imgp = fps_img if (i % 2 == 0) else white
                t1 = time.perf_counter()
                rv = set_fullscreen_image(device, imgp, mode=bg_mode)
                _logger.info("device.refresh()")
                device_busy = True
                device.refresh()
                while device_busy:
                    time.sleep(0.1)
                t2 = time.perf_counter()
                dt = (t2 - t1)
                per.append(dt)
                _logger.info(f"[fps] iter {i+1}/{iters}: rv={rv} dt_ms={dt*1000:.2f}")
            total = time.perf_counter() - t0
            avg = (sum(per) / len(per)) if per else 0.0
            fps = (iters / total) if total > 0 else 0.0
            _logger.info(f"[fps] done: total_s={total:.3f} avg_ms={avg*1000:.2f} fps={fps:.2f}")
            # If FPS test is active, skip per-key tiles and proceed to next device
            continue
        

        #time.sleep(3)
        _logger.info("set key images")
        transport: LibUSBHIDAPI.LibUSBHIDAPI = device.transport
        transport_lib = LibUSBHIDAPI.my_transport_lib
        result = transport.disconnected()
        _logger.info(f"Device disconnected: {result}")


        # Resolve assets directory relative to this file to be robust to CWD
        assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img", "memory", "set_01")
        for i in range(1, 16):
            img_path = os.path.join(assets_dir, "animal_{:02d}.png".format(i % 9 + 1))
            device.set_key_image(i, img_path)
            device.refresh()
        # Give some time for any async rendering
        time.sleep(2)



    # On real hardware, keep the app running
    time.sleep(10000)


if __name__ == "__main__":
    # Determine options from environment for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s.%(msecs)03d %(name)s %(levelname)s_ - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    run_demo()