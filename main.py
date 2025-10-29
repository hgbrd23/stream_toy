from StreamDock.DeviceManager import DeviceManager
from StreamDock.Devices.StreamDockN1 import StreamDockN1
import threading
import time
import os

print("Hello World")



if __name__ == "__main__":
    # Fix for Segmentation Fault when access rights to USB port not available.
    # TODO: Only needed for some systems, find a better way to handle this. also don't set this to all USB devices
    #   on USB controller 1
    os.system('sudo chown root:$USER /dev/bus/usb/001/00*')
    manner = DeviceManager()
    streamdocks= manner.enumerate()
    # listen plug/unplug
    t = threading.Thread(target=manner.listen)
    t.daemon = True
    t.start()
    print("Found {} Stream Dock(s).".format(len(streamdocks)))
    for device in streamdocks:
        print("Opening")
        # open device
        device.open()
        print("Init")
        device.init()
        device.set_brightness(10)
        print("Thread")
        # new thread to get device's feedback
        t = threading.Thread(target = device.whileread)
        t.daemon = True
        t.start()
        # set background image
        print("set background image")
        #res = device.set_touchscreen_image("StreamDock-Device-SDK/Python-Linux-SDK/img/YiFei320.png")
        #device.refresh()
        #time.sleep(2)
        for i in range(1, 16):
            #device.set_key_image(i, "StreamDock-Device-SDK/Python-Linux-SDK/img/tiga64.png")
            device.set_key_image(i, "img/memory/set_01/animal_{:02d}.png".format(i % 9 + 1))
            device.refresh()
        time.sleep(2)
        # clear specialize key
        #device.cleaerIcon(3)
        #device.refresh()
        #time.sleep(1)
        # clear all key
        #device.clearAllIcon()
        #device.refresh()
        #time.sleep(0)
        # N1 switch mode
        if isinstance(device, StreamDockN1):
            device.switch_mode(0)
        # close device
        #device.close()
    time.sleep(10000)