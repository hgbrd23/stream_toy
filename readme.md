# System Requirements
Install the ARM64 lite Pi OS package.

```shell
apt install -y libudev-dev libusb-1.0-0-dev libhidapi-libusb0 python3-pil python3-pyudev
```

# Quirks
If you get a segmentation fault when opening:
```shell
sudo chown root:$USER /dev/bus/usb/001/002
```

