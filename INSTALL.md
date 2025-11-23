# StreamToy Installation Guide

This guide covers installing StreamToy on a Raspberry Pi for production use.

## Prerequisites

- Raspberry Pi Zero 2 W (or compatible)
- Raspberry Pi OS ARM64 Lite (Bookworm or later)
- Internet connection
- Root/sudo access

## Quick Installation

The automated install script handles all configuration and setup:

```bash
sudo ./install.sh
```

This script will:
1. ✅ Configure Raspberry Pi boot settings (I2S audio, SPI, GPIO LED)
2. ✅ Configure ALSA sound system for MAX98357A amplifiers
3. ✅ Install required system packages
4. ✅ Copy application to `/opt/stream_toy`
5. ✅ Create Python virtual environment with dependencies
6. ✅ Configure udev rules for StreamDock USB access
7. ✅ Create and enable systemd service for autostart

### After Installation

**Reboot is required** to apply boot configuration changes:

```bash
sudo reboot
```

After reboot, the StreamToy service will start automatically.

## Service Management

### Check Status
```bash
sudo systemctl status stream_toy
```

### View Logs
```bash
# Follow live logs
sudo journalctl -u stream_toy -f

# View recent logs
sudo journalctl -u stream_toy -n 100
```

### Control Service
```bash
# Start service
sudo systemctl start stream_toy

# Stop service
sudo systemctl stop stream_toy

# Restart service
sudo systemctl restart stream_toy

# Disable autostart
sudo systemctl disable stream_toy

# Re-enable autostart
sudo systemctl enable stream_toy
```

## Development Workflow

### Exiting the Application

When developing, you can exit the application by:
- **Long-press the bottom-right button (⚙ gear icon)** on the main launcher screen
- This gracefully shuts down the application

### Making Changes

1. Stop the service:
   ```bash
   sudo systemctl stop stream_toy
   ```

2. Make your changes in `/opt/stream_toy/`

3. Restart the service:
   ```bash
   sudo systemctl restart stream_toy
   ```

### Testing Without Service

Run the application manually (without systemd):

```bash
# Stop the service first
sudo systemctl stop stream_toy

# Run manually
cd /opt/stream_toy
source .venv/bin/activate
export PYTHONPATH=/opt/stream_toy/StreamDock-Device-SDK/Python-Linux-SDK/src
python3 main.py
```

### Reinstalling

To update the installation with new code:

```bash
cd /path/to/source
sudo ./install.sh
sudo systemctl restart stream_toy
```

## File Locations

| Item | Location |
|------|----------|
| Application | `/opt/stream_toy/` |
| Virtual Environment | `/opt/stream_toy/.venv/` |
| Data Directory | `/opt/stream_toy/data/` |
| Settings File | `/opt/stream_toy/data/.settings.yml` |
| Service File | `/etc/systemd/system/stream_toy.service` |
| Boot Config | `/boot/firmware/config.txt` |
| ALSA Config | `/etc/asound.conf` |
| Udev Rules | `/etc/udev/rules.d/99-streamdock.rules` |

## Configuration Details

### Boot Configuration (`/boot/firmware/config.txt`)

The install script adds these settings:

```ini
# I2S audio for MAX98357A amplifiers
dtparam=i2s=on

# SPI for Neopixel LEDs
dtparam=spi=on

# UART support
enable_uart=1

# Disable built-in audio (commented out)
#dtparam=audio=on

# In [all] section:
dtoverlay=max98357a,sdmode-pin=23
dtparam=act_led_gpio=26
dtparam=act_led_trigger=heartbeat
```

### ALSA Configuration (`/etc/asound.conf`)

Configures 48kHz audio with dmix for the MAX98357A amplifiers.

### Udev Rules (`/etc/udev/rules.d/99-streamdock.rules`)

Allows non-root access to StreamDock USB device (VID:0c45, PID:7403).

## Troubleshooting

### Service Won't Start

Check logs for errors:
```bash
sudo journalctl -u stream_toy -n 50
```

Common issues:
- Missing boot configuration: Reboot after installation
- USB permissions: Check udev rules are loaded
- Python dependencies: Reinstall with `./install.sh`

### No Audio

1. Check ALSA configuration:
   ```bash
   aplay -l
   speaker-test -t wav -c 2 -l 1
   ```

2. Verify I2S is enabled in boot config

3. Reboot if configuration was just changed

### StreamDock Not Detected

1. Check USB connection and power

2. Verify udev rules:
   ```bash
   ls -la /dev/bus/usb/001/
   ```

3. Reload udev rules:
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

### High CPU Usage

The service has resource limits:
- Memory: 512MB max
- CPU: 80% quota

Adjust in `/etc/systemd/system/stream_toy.service` if needed.

## Uninstall

To remove StreamToy:

```bash
# Stop and disable service
sudo systemctl stop stream_toy
sudo systemctl disable stream_toy

# Remove service file
sudo rm /etc/systemd/system/stream_toy.service
sudo systemctl daemon-reload

# Remove application
sudo rm -rf /opt/stream_toy

# Optional: Remove udev rules
sudo rm /etc/udev/rules.d/99-streamdock.rules

# Optional: Restore boot config
sudo cp /boot/firmware/config.txt.backup /boot/firmware/config.txt

# Optional: Restore ALSA config
sudo cp /etc/asound.conf.backup /etc/asound.conf
```

## Hardware Wiring Reference

See [README.md](README.md) for complete hardware wiring diagrams:
- MAX98357A audio amplifier connections
- Neopixel LED connections
- Activity LED setup
- Power supply configuration

## Support

For issues or questions:
- Check logs: `sudo journalctl -u stream_toy -f`
- Review hardware connections
- Verify all configuration files are correct

---

## License

StreamToy is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License**.

This means:
- ✅ Free to use for personal, educational, and non-profit purposes
- ✅ You can modify and share improvements
- ❌ Cannot be used commercially without permission

For commercial licensing or questions: **streamtoy@sckoch.eu**

See [LICENSE](LICENSE) for full legal text.
