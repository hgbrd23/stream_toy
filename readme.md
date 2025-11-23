# StreamToy - Interactive Game Framework for StreamDock

> A standalone children's toy built with Raspberry Pi Zero 2 W and StreamDock USB device

StreamToy transforms a MiraBox HSV 293V3 StreamDock (15-button USB device with individual LCD displays per button) into an interactive, battery-powered children's toy. It provides a modular framework for creating games and apps with physical buttons, colorful displays, stereo audio, and LED animations.

## Table of Contents

- [What Is This?](#what-is-this)
- [Features](#features)
- [Available Apps](#available-apps)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Development](#development)
- [Hardware Documentation](#hardware-documentation)
  - [Power Supply](#power-supply)
  - [PIN Assignments](#pin-assignments)
  - [System Requirements](#system-requirements)
  - [Parts List](#parts-list)

## What Is This?

StreamToy is a **complete hardware + software project** that creates a portable, kid-friendly game console:

- **Hardware**: Raspberry Pi Zero 2 W + StreamDock USB device + MAX98357A audio amps + WS2812B LEDs + 18650 battery pack
- **Software**: Python framework with modular apps (games, audio player, LED playground)
- **Display**: 15 individual 112x112 LCD buttons in a 3×5 grid
- **Audio**: Stereo I2S output with software volume control (max 30% for safety)
- **LEDs**: 90 WS2812B NeoPixels around the device with animations
- **Power**: Battery-powered with 4× 18650 cells (~13,200mAh)

## Features

- **Modular App System**: Easy to add new games and apps
- **Multiple Input Devices**: Real hardware + web browser emulator for development
- **Persistent Settings**: Volume and playback positions saved across reboots
- **Audio Player**: Play MP3/FLAC with resume, seek controls, cover art, and YouTube download support
- **Interactive Games**: Memory game, reaction game, LED playground
- **LED Animations**: Background animations with support for adafruit-led-animation library
- **Scene-Based Architecture**: Clean scene management with async/await patterns
- **Production Ready**: Systemd service, auto-start, resource limits, comprehensive logging

## Available Apps

| App | Description |
|-----|-------------|
| **Audio Player** | Play audiobooks and music with playback resume, seek controls, folder navigation, and YouTube downloads |
| **Memory Game** | Classic memory matching game with multiple tile sets |
| **Reaction Game** | Test your reflexes with fast-paced button pressing |
| **LED Playground** | Experiment with different LED animation effects |

## Quick Start

### Installation (Raspberry Pi)

```bash
# Clone the repository
git clone <repository-url>
cd stream_toy

# Run automated installer (requires sudo)
sudo ./install.sh

# Reboot to apply configuration
sudo reboot
```

After reboot, StreamToy starts automatically! See [INSTALL.md](INSTALL.md) for details.

### Development (Local Machine)

```bash
# Install emulator dependencies
python3 -m venv .venv-emulator
source .venv-emulator/bin/activate
pip install -r requirements-emulator.txt

# Run with web emulator only
python3 main.py --no-hardware

# Open browser to http://localhost:5000
```

### Exiting the Application

**Long-press the bottom-right button (⚙ gear icon)** on the main launcher screen to exit.

## Project Structure

```
stream_toy/                    # Core framework
├── device/                    # Device abstraction layer
│   ├── stream_toy_device.py  # Base device class
│   ├── streamdock_device.py  # Real hardware device
│   └── web_device.py          # Web browser emulator
├── scene/                     # Scene management
│   ├── base_scene.py         # Base scene class
│   ├── menu_scene.py         # Menu scene base
│   └── module_launch_scene.py # Main launcher
├── runtime.py                 # Main runtime manager
├── sound_manager.py          # Audio playback system
├── settings_manager.py       # Persistent settings
└── led_manager.py            # LED animation manager

stream_toy_apps/              # Modular applications
├── audio_player/             # Audio/audiobook player
├── memory_game/              # Memory matching game
├── reaction_game/            # Reaction time game
└── led_playground/           # LED animation tester

StreamDock-Device-SDK/        # StreamDock USB SDK (submodule)
main.py                       # Entry point
install.sh                    # Production installer
```

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Quick reference for common tasks
- **[INSTALL.md](INSTALL.md)** - Complete installation guide
- **[CLAUDE.md](CLAUDE.md)** - Project architecture and development guidelines
- **Hardware Documentation** - See sections below

## Service Management

Once installed, control the service:

```bash
# Check status
sudo systemctl status stream_toy

# View logs (live)
sudo journalctl -u stream_toy -f

# Restart after changes
sudo systemctl restart stream_toy
```

## Troubleshooting

**Service won't start?**
```bash
sudo journalctl -u stream_toy -n 50
```

**No audio?**
```bash
speaker-test -t wav -c 2 -l 1
```

**StreamDock not detected?**
```bash
ls -la /dev/bus/usb/001/
```

See [INSTALL.md](INSTALL.md) for detailed troubleshooting.

## Development

### Creating a New App

1. Create a directory in `stream_toy_apps/your_app/`
2. Add `manifest.py` with app name and icon
3. Create `main.py` with a scene class
4. The app appears automatically in the launcher!

See existing apps for examples.

### Running Tests

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

### Code Style

- Follow PEP-8
- Use async/await for scene methods
- Keep imports absolute
- Document hardware-specific assumptions

---

# Hardware Documentation

This section contains detailed hardware wiring diagrams and configuration for building the physical device.

## Power Supply

**Battery Configuration**: 4× 18650 cells with IP5310 power bank module

- **Configuration**: 4P (Parallel) - 3.7V nominal, 13,200mAh total capacity
- **Power Management**: IP5310 module with USB charging input and 5V output
- **Power Distribution**: Custom PCB with 2× 1000µF capacitors for load spike protection

```
Cell 1 ─┐
Cell 2 ─┼─ 3.7V nominal, 13,200mAh ─── IP5310 ─── 5V Output ─── Power Distribution Board
Cell 3 ─┤                                                        (2× 1000µF caps)
Cell 4 ─┘
```

## PIN Assignments

### Audio (MAX98357A I2S Amplifiers)

**Components**: 2× MAX98357A breakout boards for stereo output (3W per channel)

**Note**: To prevent interference, use shielded cable (e.g., USB cable). Connect shield to GND on RPi side only.

| Signal   | Pi Pin         | Left Amp  | Right Amp     | Color    |
|----------|----------------|-----------|---------------|----------|
| BCLK     | 12 (GPIO 18)   | BCLK      | BCLK          | green    |
| LRCLK    | 35 (GPIO 19)   | LRCLK     | LRCLK         | white    |
| DIN      | 40 (GPIO 21)   | DIN       | DIN           | black    |
| SD_MODE  | 16 (GPIO 23)   | Direct    | Through 200kΩ | red      |
| Shield   | 20 (GND)       |           |               |          |
| -------- | -------------- | --------- | -----------   | -------- |
| 5V       | 2 (5V)         | VDD       | VDD           | yellow   |
| GND      | 9 (GND)        | GND       | GND           | brown    |

### Diagram SD_MODE
```
GPIO23 (3.3V) ──┬─────────────→ Left amp SD_MODE (3.3V)
                │
                └── 200kΩ ────→ Right amp SD_MODE (1.1V)
                                      ↓
                                   100kΩ (internal)
                                      ↓
                                    GND
```
#### Power Supply Filtering for Audio

**Problem**: Audio quality issues on battery power due to IP5310 switching noise (clicking, poor L/R separation)

**Solution**: Add capacitors at each amplifier VDD input:
```
Each amp VDD -> GND:
    ├── 0.1µF ceramic (closest!)
    Amp 2
    ├── 10µF ceramic (close!)
    ├── 0.1µF ceramic (closest!)
    Amp 1
```

### LEDs (Neopixel WS2812B)

**Components**: 90× WS2812B LEDs arranged around the StreamDock perimeter

**Layout**:
- Back left: 14 LEDs
- Left side: 17 LEDs
- Front: 28 LEDs
- Right side: 17 LEDs
- Back right: 14 LEDs

**Wiring**:

| Signal | Pi Pin       | Notes                    |
|--------|--------------|--------------------------|
| DATA   | GPIO 10      | NeoPixel data (orange)   |
| ACT_LED| GPIO 26      | Activity LED via 10kΩ    |
| 5V     | Power Module | From power distribution  |
| GND    | Power Module | Common ground            |

**Activity LED**: White LED with 10kΩ resistor for subtle glow (heartbeat pattern).

## System Requirements

### Operating System

**Raspberry Pi OS ARM64 Lite** (Bookworm or later)
- Minimal installation without desktop environment
- ARM64 (64-bit) architecture required

### Manual Installation (Advanced)

The `install.sh` script handles all of this automatically. For manual setup:

#### 1. Install System Packages

```bash
sudo apt install -y \
  libudev-dev libusb-1.0-0-dev libhidapi-libusb0 \
  python3-dev python3-pil python3-pyudev python3-venv \
  libegl1 libgl1 libopengl0 libxcb-cursor0 libxkbcommon0 \
  mpg123 portaudio19-dev python3-pyaudio ffmpeg git
```

#### 2. Configure Boot Settings

On **Raspberry Pi OS Bookworm and later**, config file is at `/boot/firmware/config.txt`

**Add to beginning of file:**
```ini
# Enable I²S audio for MAX98357A amps
dtparam=i2s=on

# Enable SPI for LEDs
dtparam=spi=on

# Enable UART
enable_uart=1

# Disable built-in analog audio
#dtparam=audio=on
```

**Add to `[all]` section:**

```ini
# Use two MAX98357A amps (manual L/R via SD pins)
dtoverlay=max98357a,sdmode-pin=23

# Enable GPIO activity LED
dtparam=act_led_gpio=26
dtparam=act_led_trigger=heartbeat
```

#### 3. Configure ALSA Sound

Create/edit `/etc/asound.conf`:
```
# Default device uses plug for automatic conversion
pcm.!default {
  type plug
  slave.pcm "dmixer"
}

# Dmix configuration
pcm.dmixer {
  type dmix
  ipc_key 1024
  slave {
      pcm "hw:0,0"
      rate 48000
  }
}

# Control device
ctl.!default {
  type hw
  card 0
}

```

#### 4. Reboot

```bash
sudo reboot
```

#### 5. Test Audio

```bash
# Test stereo output
speaker-test -t wav -c 2 -l 1

# Play MP3
mpg123 sample.mp3
```

**Note**: Hardware volume control not available; volume managed in software.

### Known Issues

**USB Permission Issues**: If you get segmentation faults:
```bash
sudo chown root:$USER /dev/bus/usb/001/00*
```

The `install.sh` script creates udev rules to handle this automatically.

## Parts List

### Main Components

| Component | Description | Link |
|-----------|-------------|------|
| **StreamDock** | MiraBox HSV 293V3 / StreamDock 293V3 USB device | Search "StreamDock 293V3" |
| **Raspberry Pi** | Raspberry Pi Zero 2 W | Official distributor |
| **Audio Amplifier** | MAX98357A I2S Class D Amplifier (3W) - 3 pack | [Amazon DE](https://www.amazon.de/-/en/dp/B0CJY1C287) |
| **Speakers** | 3W 4Ω Micro Speakers (2 pack) | [Amazon DE](https://www.amazon.de/-/en/dp/B09JHSZ7KJ) |
| **LEDs** | WS2812B NeoPixel LED Strip (90+ LEDs) | Common electronics supplier |
| **Batteries** | 18650 Rechargeable 3.7V 3300mAh Flat Top (4 pack) | [Amazon DE](https://www.amazon.de/-/en/dp/B0DCK4PTXS) |
| **Battery Holder** | 18650 Battery Holder (4-cell) | [Amazon DE](https://www.amazon.de/-/en/dp/B0D2D6SDP1) |
| **Power Module** | IP5310 Power Bank Module | Common electronics supplier |
| **Enclosure** | ABS Plastic IP65 Box (200×120×56mm) | [Amazon DE](https://www.amazon.de/-/en/dp/B0CZ3GPHN3) |

### Additional Parts

- Power distribution board (custom or perfboard)
- Capacitors: 2× 1000µF (power), 3× 0.1µF ceramic, 1× 10µF ceramic (audio filtering)
- Resistors: 1× 200kΩ (stereo separation), 1× 10kΩ (activity LED)
- White LED (activity indicator)
- Shielded cable (USB cable works well)
- Wire, solder, mounting hardware

---

## Contributing

Contributions welcome!

**Before contributing**, please review the [Contributor License Agreement](CONTRIBUTORS.md). By submitting a contribution, you agree to grant the project maintainer rights to relicense your work if needed.

**When contributing**:
- Follow the code style guidelines in [CLAUDE.md](CLAUDE.md)
- Add tests for new features
- Update documentation as needed
- Test on both hardware and web emulator
- Include "I agree to the Contributor License Agreement" in your pull request

For questions: streamtoy@sckoch.eu

## License

This project is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License** (CC BY-NC-SA 4.0).

See the [LICENSE](LICENSE) file for the complete legal text.

### What This Means

**You CAN:**
- ✅ Build this for yourself, family, or friends
- ✅ Modify and improve the design
- ✅ Share your modifications (under the same license)
- ✅ Use in educational settings (schools, workshops, makerspaces)
- ✅ Use for research purposes
- ✅ Learn from the code and hardware design

**You CANNOT:**
- ❌ Sell devices with this code/design
- ❌ Manufacture and sell commercially
- ❌ Include in commercial products
- ❌ Use for commercial advantage or monetary compensation

### Why Non-Commercial?

This is a passion project designed for children's education and entertainment. Keeping it non-commercial ensures it remains accessible to everyone and prevents exploitative commercial use while encouraging learning and creativity.

### Commercial Licensing

Interested in commercial use, partnerships, or licensing?

**Contact**: streamtoy@sckoch.eu

Schools, non-profits, and educational institutions: please reach out for guidance on permitted uses.

### Contributing

By contributing to this project, you agree to the [Contributor License Agreement](CONTRIBUTORS.md), which grants the project maintainer the right to relicense contributions if needed. This ensures the project can evolve while protecting contributors.

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for details.

## Acknowledgments

- StreamDock SDK for device communication
- Adafruit for LED animation libraries
- Community contributors and testers

