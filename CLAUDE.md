# StreamDockKeyboard – Project Guidelines
This document captures practical, project‑specific knowledge to help advanced developers build, test, and extend this 
repository quickly and safely.

# Project Overview
The goal of this project is to create a UI for a standalone childrens toy.
The hardware used is a Raspberry Pi zero 2 W.

# StreamDock
The SteamDock is connected to the Raspberry PI via USB.  
The StreamDock is a USB device normally used by content streamers. The model is MiraBox HSV 293V3 / StreamDock 293V3. 
It has a total of 15 buttons in 3 rows and 5 columns. Behind the buttons is a TFT display that can be controlled as one 
screen or 15 individual buttons.

This model uses the class StreamDock293V3.

The background image has dimensions of 800 * 480. The tile image for buttons is 112x112.
Buttons start at 0,4. Gap between buttons is 40x42.

Button presses can be detected, even while the device is refreshing.

## Device Refresh Behavior

**Individual Button Tiles (112x112):**
- Fast updates, typically < 100ms per tile
- Multiple tiles can be updated without waiting for ACK
- Just call `device.refresh()` after `set_key_image()` - no need to wait
- The device handles these asynchronously

**Full Screen Background Image (800x480):**
- Very slow updates, takes 500ms to 3+ seconds
- Device can crash if too many commands are sent during background refresh
- MUST wait for ACK callback after `device.refresh()` with this data:
  `(b'ACK\x00\x00OK\x00\x00\x00\x00\x00\x00', 'ACK', 'OK', 0, 0)`
- ACK is indicated by bytes[3] and bytes[4] both being 0

**Best Practice:**
- Use individual button tiles for UI updates (fast, responsive)
- Avoid full screen background images if possible - use tiles instead
- Only use background images for static content that rarely changes

## Native JPEG Encoding for Button Tiles

The StreamDock 293V3 requires button images to be in JPEG format (112x112 pixels, rotated 180°). The device has specific limitations:

**JPEG Quality Setting:**
- **MUST use quality=85** when saving native JPEG files
- Higher quality (95) creates larger files that cause display corruption
- The device likely has buffer size limits that are exceeded with high-quality JPEGs
- This is especially critical for composite images with:
  - Alpha blending (semi-transparent overlays)
  - Text rendering (creates sharp edges)
  - Multiple color gradients

**Why This Matters:**
- PNG cache files in `data/cache/scene_tiles/` display correctly in web emulator
- Native JPEG cache files (`*_native.jpg`) are generated on-demand for hardware
- If JPEG quality is too high, images display corrupted ONLY on hardware device (not in emulator or on PC)

**Implementation:**
```python
native_image.save(cache_path, format='JPEG', quality=85)
```

**Symptoms of Incorrect Quality:**
- Web emulator shows images correctly
- Real device shows corrupted/broken images (looks like partial JPEG decode failure)
- Downloading the JPEG files and viewing on PC shows no corruption

# Neopixel LEDs
Neopixel WS2812b (eco) LEDs are connected to GPIO 10 of the RPI.

They are laid out around the StreamDock keyboard in this configuration as one string in this order:

14 LEDs: back left
17 LEDs: left
28 LEDs: front
17 LEDs: right
14 LEDs: back right

Effects can be sent to this strip using the neopixel and adafruit_led_animation libs.

## Architecture
There is a library called StreamToy in the subdirectory /stream_toy. It provides common functionality for modules
that are stored in /stream_toy_apps.
Each StreamToy app can provide a unique game that can be played using the buttons and their displays. The modules are 
loaded and executed by the StreamToy library.

## StreamToy library
The library provides several layers of functionality:

### Device abstraction
The StreamToy library provides different UIs as "devices". One will be an "emulated" device that is accessible via web 
browser.

There is an abstract base class StreamToyDevice for this case. The class provides the following fucntionality:
* set_tile(): Receives a tile image as PIL image. Stores it to send it to the device.
* submit(): Sends all queued tile changes to the device. Should block until the changes are accepted and processed by 
  the device.
* register_key_callback(): Allows registering a callback for key presses and releases.
* A background thread for LED animations
* set_background_led_animation: Submits an LED animation that runs when no other animation is active.
* run_led_animation(animation object, duration): Runs the given LED animation. The background animation is paused and 
  continues after this animation ended. When no duration is given, the animation runs for one cycle. 

Child classes:
* One class StreamDock293V3Device for the real device.
* Another one WebDevice for the emulator web device.
* Both can be disabled using he command line. By default both are enabled.

#### WebDevice
Use the data of the StreakDock like background size, button tiles and the information of LEDs around it to emulate
the real device in a web browser.

The WebDevice proves a webserver with realtime functionality to send updates for button tiles and LEDs to the web 
browser and receive button events. 

It contains a fake neopixel class that can be used by adafruit_led_animation. Instead of sending the LED data to a
GPIO, it sends them to the web browser.

### Runtime management
* Device initialisation
* Loading of all modules from stream_modules
* Displaying menus and settings, which are each a scene.

### Base Scene
An abstract base scene providing functionality to be inherited in other scenes.

It provides the following functionality:
* Receiving input events.
* Can call the runtime to switch to another scene by giving its class name.
* A main async method that runs while the scene is active. It can async poll for input events.
* Methods and properties for setting button tiles or a whole screen tile. The tiles can be set either as a PNG, SVG 
  or text. For text a fixed font is used with a default size that can be customized when setting the text.

### Menu Scene
An abstract scene representing a menu. A menu is used by the user to activate other functionality like executing 
actions or navigating to other scenes.

Each button can be configured to execute actions either on tap or long press. Long press means 3 seconds.

### Module Launch Scene
This inherits the menu scene. It is the start scene when running the app. It shows a list of all modules, one per button, each with 
a module icon loaded from the stream_module. Long-pressing the bottom right of button is reserved for system 
functionality.

### Input management
Input events should be queued until received by a scene.

## StreamToy modules
Each module implements a unique game. This can be for example a memory game, quick reaction game, playing audio books 
etc.
Properties of a module:
* Has a manifest python file that is read to get the module name and icon
* A main scene that is executed when opening the module from the module launch scene.
* When long/pressing the bottom right button the user returns to the module launch scene.

# 1) Build and Configuration

### Python version
- Target Python 3.10+ (3.11 also fine). The SDK code is pure Python but depends on native HID/USB libraries at runtime.

### Virtual environment and dependencies
#### Real device
- Create a venv and install Python deps:
  ```bash
  python -m venv .venv
  . .venv/bin/activate
  pip install -U pip wheel
  pip install -r requirements.txt
  ```
- `requirements.txt` currently lists `pyudev` only. For development utilities used in scripts, also install:
  ```bash
  pip install pillow
  ```
  `split_image.py` uses Pillow, but it is not required to run the HID device demo in `main.py`.

#### WebDevice
Use the venv in .venv-emulator with requirements-emulator.

### Native system libraries (Linux)
- `readme.md` documents the baseline system packages:
  ```bash
  sudo apt install -y libudev-dev libusb-1.0-0-dev libhidapi-libusb0 python3-pil python3-pyudev
  ```
- udev permissions: by default, access to `/dev/bus/usb/*` may require elevated privileges. The current demo uses a coarse workaround:
  ```bash
  sudo chown root:$USER /dev/bus/usb/001/00*
  ```
  This is only a stop‑gap. Prefer a udev rule for the StreamDock VID/PID allowing your user group to access the device without sudo. Document the rule when VID/PID are finalized.


### Python import path for the SDK
- The code imports from `StreamDock` directly:
  ```python
  from StreamDock.DeviceManager import DeviceManager
  ```
  The SDK sources live at: `StreamDock-Device-SDK/Python-Linux-SDK/src/`. Ensure this path is on `PYTHONPATH` when running from the project root, e.g.:
  - Temporary per‑shell:
    ```bash
    export PYTHONPATH="$PWD/StreamDock-Device-SDK/Python-Linux-SDK/src:$PYTHONPATH"
    # PowerShell:
    $env:PYTHONPATH = ("$PWD/StreamDock-Device-SDK/Python-Linux-SDK/src;" + $env:PYTHONPATH)
    ```
  - Or run via `python -m` with `PYTHONPATH` set, or add a minimal launcher that amends `sys.path` before imports.

### Git submodules
- The `StreamDock-Device-SDK` directory is tracked (and may be a submodule). If you clone this repo fresh, make sure submodules are initialized:
  ```bash
  git submodule update --init --recursive
  ```

## 2) Testing

### Test runner
- We use the standard library `unittest` runner; no extra test harness is required.
- Discovery command from the project root:
  ```bash
  python -m unittest discover -s tests -p "test_*.py" -v
  ```

### Emulator test 
- The repository includes a pure‑Python Stream Dock emulator with a web interface.
- The emulator should run without ALSA/sound output and any other hardware related functionality. It will not have 
  access to the keyboard device connected via USB or LED control. 

### Writing new tests
- Create test files under `tests/` named `test_*.py`.
- Keep tests hardware‑agnostic unless you explicitly gate them.
  - Avoid importing `StreamDock` device modules in unit tests unless you mock transports; they will try to talk to USB HID devices.
  - Prefer smoke tests that validate our glue code and configuration surfaces (e.g., presence of expected files, simple pure functions, image helpers with Pillow, etc.).
- If you must test device logic:
  - Abstract I/O behind a small interface (e.g., a `Transport` with `send/recv`), then inject a fake for tests.
  - Provide environment flags to skip hardware tests by default, e.g. `@unittest.skipUnless(os.getenv("HW_TESTS") == "1", "requires hardware")`.


## 3) Running the demo app

- Ensure `PYTHONPATH` includes `StreamDock-Device-SDK/Python-Linux-SDK/src` (see above).
- On Linux, install the native libs and address permissions as described earlier.
- Then run:
  ```bash
  python demo.py
  ```
- Behavior notes:
  - `main.py` currently executes a broad `chown` against `/dev/bus/usb/001/00*`. This is fragile and not portable. Replace with udev rules for production.
  - The script enumerates devices, opens each, sets brightness, starts a background read thread, and populates key images from `stream_toy_apps/memory_game/assets/tiles/tile_set_01/tile_XX.png`. It will sleep for a long period (`time.sleep(10000)`) at the end.

## 5) Code style and contribution notes
- Match the existing Python style (PEP‑8-ish with pragmatic line lengths).
- Keep imports absolute.
- Avoid side effects at import time; device opening should happen under `if __name__ == "__main__":`.
- Encapsulate device operations behind interfaces to enable mocking and cross‑platform support.
- Do not touch SDK code under `StreamDock-Device-SDK/...`
- Don't add ENV/configuration unless explicitly asked.
- Don't reimplement stuff that is in the libraries unless explicitly asked. If you think it would be better ask the user.
- When improving code, don't create a new version of anything. Refactor the existing one or create a new one and remove the old one.
- When fixing something and your code did not fix the problem, remove it unless it provides some very clear benefits.
- Never use hardcoded paths. Always use a path relative to our modules.
- Don't create test scripts. Write unittests in the tests directory.
- You are running in a container and can't access ALSA or the physical device.
- Acknowledge every time you read CLAUDE.md and output a line so the user knows.