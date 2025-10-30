# StreamDockKeyboard – Project Guidelines

This document captures practical, project‑specific knowledge to help advanced developers build, test, and extend this repository quickly and safely.

# Project Overview
The goal of this project is to create a UI for a standalone childrens toy.
The hardware used is a StreamDock keyboard connected to a Raspberry Pi zero 2 W.

The StreamDock is a USB device normally used by content streamers. The model is MiraBox HSV 293. It has a total of 15 
buttons in 3 rows and 5 columns. Behind the buttons is a TFT display that can be controlled as one screen or 15 
individual buttons.

Button presses can be detected.

## Architecture
There is a library called StreamToy in the subdirectory /stream_toy. It provides common functionality for modules
that are stored in /stream_toy_modules.
Each StreamToy module can provide a unique game that can be played using the buttons and their displays. The modules are 
loaded and executed by the StreamToy library.

## StreamToy library
The library provides several layers of functionality:
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
- Create a venv and install Python deps:
  ```bash
  python -m venv .venv
  . .venv/bin/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
  pip install -U pip wheel
  pip install -r requirements.txt
  ```
- `requirements.txt` currently lists `pyudev` only. For development utilities used in scripts, also install:
  ```bash
  pip install pillow
  ```
  `split_image.py` uses Pillow, but it is not required to run the HID device demo in `main.py`.

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

### Windows and macOS notes
- This repo vendors a Linux and a macOS ARM64 SDK. The Python demo (`main.py`) is Linux‑oriented and relies on `pyudev` and `hidapi/libusb` stack. On Windows, HID transport will require the proper backend (HIDAPI/WinUSB). The Windows SDK variant isn’t currently wired in `main.py`.
- If you need cross‑platform support, introduce a transport selection layer that chooses the correct backend per OS and conditionally installs platform packages.

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

### Emulator test (GUI visible) — Windows friendly
- The repository includes a pure‑Python Stream Dock emulator with a small PySide6 (Qt) GUI.
- The test `tests/test_emulator_screenshot.py` imports `main.run_demo()` directly, runs with the emulator, shows the GUI during the test, and writes a screenshot to `tests/artifacts/emulator_screenshot.png`.
- Artifacts directory: `tests/artifacts/` (ignored by git).

### Windows emulator venv (.venv-emulator)
- Create and use a minimal venv for emulator work on Windows (no USB libs needed):
  ```powershell
  # From project root
  .\scripts\setup-emulator-venv.ps1
  # Later, to activate:
  . .\.venv-emulator\Scripts\Activate.ps1
  ```
- This installs `requirements-emulator.txt` (Pillow only). Use it to run emulator and tests without Linux HID deps.

### Writing new tests
- Create test files under `tests/` named `test_*.py`.
- Keep tests hardware‑agnostic unless you explicitly gate them.
  - Avoid importing `StreamDock` device modules in unit tests unless you mock transports; they will try to talk to USB HID devices.
  - Prefer smoke tests that validate our glue code and configuration surfaces (e.g., presence of expected files, simple pure functions, image helpers with Pillow, etc.).
- If you must test device logic:
  - Abstract I/O behind a small interface (e.g., a `Transport` with `send/recv`), then inject a fake for tests.
  - Provide environment flags to skip hardware tests by default, e.g. `@unittest.skipUnless(os.getenv("HW_TESTS") == "1", "requires hardware")`.

### Example test (validated during this change)
- A simple, safe test was temporarily created and executed to demonstrate setup:
  - Location: `tests/test_sanity.py`
  - Content: verified that `readme.md` contains the "System Requirements" header and `main.py` contains the `print("Hello World")` literal.
  - Execution proof:
    ```text
    test_main_prints_hello_world_literal ... ok
    test_readme_has_system_requirements_section ... ok
    Ran 2 tests in 0.001s
    OK
    ```
  - Cleanup: The file was deleted after validation to avoid polluting the repo with scaffolding.

## 3) Running the demo app

- Ensure `PYTHONPATH` includes `StreamDock-Device-SDK/Python-Linux-SDK/src` (see above).
- On Linux, install the native libs and address permissions as described earlier.
- Then run:
  ```bash
  python main.py
  ```
- Behavior notes:
  - `main.py` currently executes a broad `chown` against `/dev/bus/usb/001/00*`. This is fragile and not portable. Replace with udev rules for production.
  - The script enumerates devices, opens each, sets brightness, starts a background read thread, and populates key images from `img/memory/set_01/animal_XX.png`. It will sleep for a long period (`time.sleep(10000)`) at the end.
  - For `StreamDockN1`, it switches mode 0 if detected.

## 4) Image assets and helpers
- `split_image.py` demonstrates cropping a sprite sheet into button images. It assumes a specific asset at `img/memory/SSP_Memory_game_Farm_Animals-4.jpg` and writes PNG tiles into `img/memory/`.
- The UI keys are set to 64×64 in comments; adjust cropping/resizing accordingly to the device’s native key resolution. Prefer `Image.LANCZOS` for downscaling.

## 5) Code style and contribution notes
- Match the existing Python style (PEP‑8-ish with pragmatic line lengths).
- Keep imports absolute.
- Avoid side effects at import time; device opening should happen under `if __name__ == "__main__":`.
- Encapsulate device operations behind interfaces to enable mocking and cross‑platform support.
- When touching SDK code under `StreamDock-Device-SDK/...`, prefer upstreaming changes to the SDK repository rather than diverging here.
