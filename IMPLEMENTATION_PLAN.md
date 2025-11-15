# StreamToyKeyboard Implementation Plan

## Executive Summary
This document outlines the comprehensive implementation plan for the StreamToyKeyboard project - a children's toy UI system using a StreamDock 293V3 device connected to a Raspberry Pi Zero 2 W. The system includes a modular game/app architecture, device abstraction layer, and web-based emulator.

## Current State Analysis

### Completed Components
- `demo.py`: Basic StreamDock 293V3 device demo showing key image updates
- `led_test.py`: Neopixel LED testing functionality
- `split_image.py`: Image processing utilities
- `/stream_toy_apps/memory_game/assets/tiles/tile_set_01/`: Sample assets (tile images)
- `StreamDock-Device-SDK/`: External SDK for hardware communication

### Missing Components (To Be Implemented)
- `/stream_toy/`: Core library (empty directory)
- `/stream_toy_apps/`: Application modules (empty directory)
- All architecture components described in CLAUDE.md

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│            StreamToy Runtime Manager                │
│  (Device init, module loading, scene switching)     │
└─────────────────┬───────────────────────────────────┘
                  │
      ┌───────────┴───────────┐
      │                       │
┌─────▼──────┐       ┌────────▼─────┐
│   Scenes   │       │   Devices    │
│            │       │              │
│ - Base     │◄──────┤ - Abstract   │
│ - Menu     │       │ - StreamDock │
│ - Launch   │       │ - WebDevice  │
└────────────┘       └──────┬───────┘
                            │
                    ┌───────▼────────┐
                    │  LED Manager   │
                    │ (Neopixel WS2812b)│
                    └────────────────┘
```

---

## Phase 1: Core StreamToy Library Foundation

### 1.1 Device Abstraction Layer (`/stream_toy/device/`)

#### File: `stream_toy_device.py`
Abstract base class providing unified interface for physical and emulated devices.

**Class: `StreamToyDevice` (ABC)**

**Properties:**
- `SCREEN_WIDTH`: int = 800
- `SCREEN_HEIGHT`: int = 480
- `TILE_SIZE`: int = 112
- `TILE_COLS`: int = 5
- `TILE_ROWS`: int = 3
- `TILE_GAP_X`: int = 40
- `TILE_GAP_Y`: int = 42
- `TILE_START_X`: int = 0
- `TILE_START_Y`: int = 4
- `LED_COUNT`: int = 90 (14+17+28+17+14)
- `LED_SEGMENTS`: dict = {'back_left': 14, 'left': 17, 'front': 28, 'right': 17, 'back_right': 14}

**Methods to implement:**
```python
@abstractmethod
def set_tile(self, row: int, col: int, image: Image.Image) -> None:
    """Queue a tile image update (0-indexed, 3 rows x 5 cols)."""
    pass

@abstractmethod
def submit(self) -> None:
    """Send all queued tile changes to device. Blocks until complete."""
    pass

@abstractmethod
def register_key_callback(self, callback: Callable[[int, int, bool], None]) -> None:
    """Register callback for key events: callback(row, col, is_pressed)."""
    pass

@abstractmethod
def set_background_led_animation(self, animation) -> None:
    """Set the idle LED animation."""
    pass

@abstractmethod
def run_led_animation(self, animation, duration: Optional[float] = None) -> None:
    """Run a foreground LED animation, pausing background."""
    pass

def get_tile_position(self, row: int, col: int) -> Tuple[int, int]:
    """Calculate pixel position for a tile."""
    x = self.TILE_START_X + col * (self.TILE_SIZE + self.TILE_GAP_X)
    y = self.TILE_START_Y + row * (self.TILE_SIZE + self.TILE_GAP_Y)
    return (x, y)
```

#### File: `streamdock293v3_device.py`
Real hardware device implementation.

**Class: `StreamDock293V3Device(StreamToyDevice)`**

**Implementation details:**
- Wraps `StreamDock.Devices.StreamDock293V3`
- Manages tile update queue (dict mapping button index to PIL Image)
- Implements `submit()` to batch send tiles via SDK's `set_key_image()` + `refresh()`
- Monitors device ACK callback to know when refresh completes
- Translates SDK button indices (1-15) to (row, col) coordinates
- Uses GPIO 10 for Neopixel strip with `neopixel` and `adafruit_led_animation`
- Background thread for LED animations with pause/resume capability

**Key challenges:**
- Device refresh is slow (500ms-3s), must wait for ACK before next update
- Button presses can be detected during refresh (293V3 feature)
- Device may crash if commands sent too quickly

**Dependencies:**
- `StreamDock.DeviceManager`
- `StreamDock.Devices.StreamDock293V3`
- `neopixel`
- `adafruit_led_animation`
- `board` (for GPIO definitions)

#### File: `web_device.py`
Browser-based emulator implementation.

**Class: `WebDevice(StreamToyDevice)`**

**Implementation details:**
- Flask/FastAPI web server with WebSocket support (Socket.IO)
- Serves HTML5 canvas rendering StreamDock layout
- CSS to draw LED strip around the device visualization
- Sends tile updates as base64-encoded PNG images via WebSocket
- Receives button clicks from browser, emits to registered callback
- Fake neopixel class compatible with `adafruit_led_animation` API
- LED updates sent to browser as RGB array via WebSocket

**Endpoints:**
- `GET /`: Serve HTML emulator page
- `WebSocket /events`: Bidirectional communication
  - Server → Client: `tile_update`, `led_update`
  - Client → Server: `button_press`, `button_release`

**HTML/JS structure:**
```html
<canvas id="streamdock" width="800" height="480"></canvas>
<div id="led-strip"><!-- 90 LED divs --></div>
<script>
  // WebSocket connection
  // Canvas drawing for tiles
  // Mouse event handling for buttons
  // LED visualization
</script>
```

**Dependencies:**
- Flask or FastAPI
- python-socketio
- Pillow (for image encoding)

---

### 1.2 Input Management (`/stream_toy/input_manager.py`)

**Class: `InputManager`**

Manages input event queue with thread-safe operations.

```python
class InputEvent:
    def __init__(self, row: int, col: int, is_pressed: bool, timestamp: float):
        self.row = row
        self.col = col
        self.is_pressed = is_pressed
        self.timestamp = timestamp
        self.long_press = False  # Set by long-press detector

class InputManager:
    def __init__(self):
        self._queue: queue.Queue[InputEvent] = queue.Queue()
        self._long_press_threshold: float = 3.0  # seconds
        self._active_presses: Dict[Tuple[int, int], float] = {}
        self._lock = threading.Lock()

    def on_device_key_event(self, row: int, col: int, is_pressed: bool):
        """Called by device callback."""
        with self._lock:
            key = (row, col)
            if is_pressed:
                self._active_presses[key] = time.time()
            else:
                # Check if long press
                if key in self._active_presses:
                    duration = time.time() - self._active_presses[key]
                    del self._active_presses[key]

        event = InputEvent(row, col, is_pressed, time.time())
        if not is_pressed and duration >= self._long_press_threshold:
            event.long_press = True
        self._queue.put(event)

    def poll_event(self, timeout: float = 0.1) -> Optional[InputEvent]:
        """Non-blocking poll for next event."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    async def async_poll_event(self) -> InputEvent:
        """Async version for asyncio."""
        return await asyncio.get_event_loop().run_in_executor(
            None, self._queue.get
        )
```

---

### 1.3 Scene System (`/stream_toy/scene/`)

#### File: `base_scene.py`

**Class: `BaseScene` (ABC)**

Base class for all scenes with common functionality.

```python
class BaseScene(ABC):
    def __init__(self, runtime: 'StreamToyRuntime'):
        self.runtime = runtime
        self.device = runtime.device
        self.input_manager = runtime.input_manager
        self._running = False
        self._tile_cache: Dict[Tuple[int, int], Image.Image] = {}

    @abstractmethod
    async def on_enter(self):
        """Called when scene becomes active."""
        pass

    @abstractmethod
    async def on_exit(self):
        """Called when scene becomes inactive."""
        pass

    @abstractmethod
    async def main_loop(self):
        """Main async loop for the scene."""
        pass

    def set_tile_text(self, row: int, col: int, text: str,
                      font_size: int = 24,
                      fg_color: str = "white",
                      bg_color: str = "black"):
        """Render text to a tile."""
        img = Image.new('RGB', (self.device.TILE_SIZE, self.device.TILE_SIZE), bg_color)
        draw = ImageDraw.Draw(img)

        # Use a default font or load custom
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()

        # Center text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (self.device.TILE_SIZE - text_width) // 2
        y = (self.device.TILE_SIZE - text_height) // 2

        draw.text((x, y), text, fill=fg_color, font=font)
        self.set_tile_image(row, col, img)

    def set_tile_svg(self, row: int, col: int, svg_path: str):
        """Render SVG to a tile."""
        from cairosvg import svg2png
        from io import BytesIO

        png_data = svg2png(url=svg_path, output_width=self.device.TILE_SIZE,
                           output_height=self.device.TILE_SIZE)
        img = Image.open(BytesIO(png_data))
        self.set_tile_image(row, col, img)

    def set_tile_image(self, row: int, col: int, image: Image.Image):
        """Set a tile to a PIL image."""
        self._tile_cache[(row, col)] = image
        self.device.set_tile(row, col, image)

    def set_tile_file(self, row: int, col: int, image_path: str):
        """Load and set tile from file."""
        img = Image.open(image_path)
        img = img.resize((self.device.TILE_SIZE, self.device.TILE_SIZE))
        self.set_tile_image(row, col, img)

    def submit_tiles(self):
        """Submit all queued tile updates."""
        self.device.submit()

    def switch_scene(self, scene_class: Type['BaseScene'], **kwargs):
        """Request scene transition."""
        self.runtime.switch_scene(scene_class, **kwargs)
```

#### File: `menu_scene.py`

**Class: `MenuScene(BaseScene)` (ABC)**

Abstract menu with configurable button actions.

```python
class ButtonAction:
    """Defines what happens on tap or long press."""
    def __init__(self, on_tap: Optional[Callable] = None,
                 on_long_press: Optional[Callable] = None):
        self.on_tap = on_tap
        self.on_long_press = on_long_press

class MenuItem:
    """Menu item with visual and action."""
    def __init__(self, row: int, col: int,
                 label: Optional[str] = None,
                 icon: Optional[str] = None,
                 action: Optional[ButtonAction] = None):
        self.row = row
        self.col = col
        self.label = label
        self.icon = icon  # Path to image file
        self.action = action or ButtonAction()

class MenuScene(BaseScene):
    def __init__(self, runtime: 'StreamToyRuntime'):
        super().__init__(runtime)
        self.items: List[MenuItem] = []

    @abstractmethod
    def build_menu(self) -> List[MenuItem]:
        """Override to define menu items."""
        pass

    async def on_enter(self):
        self.items = self.build_menu()
        for item in self.items:
            if item.icon:
                self.set_tile_file(item.row, item.col, item.icon)
            elif item.label:
                self.set_tile_text(item.row, item.col, item.label)
        self.submit_tiles()

    async def main_loop(self):
        while self._running:
            event = await self.input_manager.async_poll_event()
            if not event.is_pressed:  # Button release
                # Find matching menu item
                item = next((i for i in self.items
                            if i.row == event.row and i.col == event.col), None)
                if item and item.action:
                    if event.long_press and item.action.on_long_press:
                        await self._safe_call(item.action.on_long_press)
                    elif not event.long_press and item.action.on_tap:
                        await self._safe_call(item.action.on_tap)

    async def _safe_call(self, func):
        """Call function, handling both sync and async."""
        if asyncio.iscoroutinefunction(func):
            await func()
        else:
            func()
```

#### File: `module_launch_scene.py`

**Class: `ModuleLaunchScene(MenuScene)`**

Main launcher showing all available modules.

```python
class ModuleLaunchScene(MenuScene):
    def build_menu(self) -> List[MenuItem]:
        modules = self.runtime.get_available_modules()
        items = []

        for idx, module in enumerate(modules[:14]):  # Max 14 modules (reserve bottom-right)
            row = idx // 5
            col = idx % 5

            items.append(MenuItem(
                row=row,
                col=col,
                icon=module.manifest.icon_path,
                action=ButtonAction(
                    on_tap=lambda m=module: self.launch_module(m)
                )
            ))

        # Bottom-right reserved for system menu
        items.append(MenuItem(
            row=2, col=4,
            label="⚙",  # Settings icon
            action=ButtonAction(
                on_long_press=self.show_system_menu
            )
        ))

        return items

    def launch_module(self, module: 'StreamToyModule'):
        """Launch a module."""
        self.switch_scene(module.main_scene_class)

    def show_system_menu(self):
        """Show system settings."""
        self.switch_scene(SystemMenuScene)
```

---

### 1.4 Runtime Manager (`/stream_toy/runtime.py`)

**Class: `StreamToyRuntime`**

Central coordinator for the entire system.

```python
class StreamToyRuntime:
    def __init__(self, enable_hardware: bool = True, enable_web: bool = True):
        self.enable_hardware = enable_hardware
        self.enable_web = enable_web

        self.devices: List[StreamToyDevice] = []
        self.input_manager = InputManager()
        self.modules: List[StreamToyModule] = []

        self.current_scene: Optional[BaseScene] = None
        self.scene_stack: List[BaseScene] = []

        self._running = False
        self._main_task: Optional[asyncio.Task] = None

    def initialize(self):
        """Initialize devices and load modules."""
        # Initialize hardware device
        if self.enable_hardware:
            try:
                hw_device = StreamDock293V3Device()
                hw_device.initialize()
                hw_device.register_key_callback(self.input_manager.on_device_key_event)
                self.devices.append(hw_device)
                logger.info("Hardware device initialized")
            except Exception as e:
                logger.error(f"Failed to initialize hardware: {e}")

        # Initialize web device
        if self.enable_web:
            try:
                web_device = WebDevice(port=5000)
                web_device.initialize()
                web_device.register_key_callback(self.input_manager.on_device_key_event)
                self.devices.append(web_device)
                logger.info("Web device initialized on http://localhost:5000")
            except Exception as e:
                logger.error(f"Failed to initialize web device: {e}")

        if not self.devices:
            raise RuntimeError("No devices available!")

        # Primary device for scenes
        self.device = self.devices[0]

        # Load all modules
        self.load_modules()

    def load_modules(self):
        """Scan and load all modules from stream_toy_apps/."""
        apps_dir = Path(__file__).parent.parent / "stream_toy_apps"
        for module_dir in apps_dir.iterdir():
            if module_dir.is_dir() and (module_dir / "manifest.py").exists():
                try:
                    module = self.load_module(module_dir)
                    self.modules.append(module)
                    logger.info(f"Loaded module: {module.manifest.name}")
                except Exception as e:
                    logger.error(f"Failed to load module {module_dir.name}: {e}")

    def load_module(self, module_dir: Path) -> 'StreamToyModule':
        """Load a single module."""
        # Import manifest.py
        spec = importlib.util.spec_from_file_location(
            f"stream_toy_apps.{module_dir.name}.manifest",
            module_dir / "manifest.py"
        )
        manifest_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(manifest_module)

        manifest = manifest_module.get_manifest()
        return StreamToyModule(module_dir, manifest)

    def get_available_modules(self) -> List['StreamToyModule']:
        """Get all loaded modules."""
        return self.modules

    def switch_scene(self, scene_class: Type[BaseScene], **kwargs):
        """Switch to a new scene."""
        asyncio.create_task(self._switch_scene_async(scene_class, **kwargs))

    async def _switch_scene_async(self, scene_class: Type[BaseScene], **kwargs):
        """Internal async scene switching."""
        if self.current_scene:
            self.current_scene._running = False
            await self.current_scene.on_exit()

        self.current_scene = scene_class(self, **kwargs)
        self.current_scene._running = True
        await self.current_scene.on_enter()

        # Start scene main loop
        asyncio.create_task(self.current_scene.main_loop())

    async def run(self):
        """Main runtime loop."""
        self._running = True

        # Start with module launch scene
        await self._switch_scene_async(ModuleLaunchScene)

        # Keep runtime alive
        while self._running:
            await asyncio.sleep(0.1)

    def start(self):
        """Start the runtime (blocking)."""
        self.initialize()
        asyncio.run(self.run())

    def shutdown(self):
        """Graceful shutdown."""
        self._running = False
        for device in self.devices:
            device.close()
```

---

## Phase 2: Module System

### 2.1 Module Structure (`/stream_toy/module.py`)

**Class: `ModuleManifest`**

```python
@dataclass
class ModuleManifest:
    """Module metadata."""
    name: str
    version: str
    author: str
    description: str
    icon_path: str  # Relative to module directory
    main_scene: str  # Module name of main scene class

class StreamToyModule:
    """Represents a loaded module."""
    def __init__(self, path: Path, manifest: ModuleManifest):
        self.path = path
        self.manifest = manifest
        self._main_scene_class = None

    @property
    def main_scene_class(self) -> Type[BaseScene]:
        """Lazy load main scene class."""
        if not self._main_scene_class:
            spec = importlib.util.spec_from_file_location(
                f"stream_toy_apps.{self.path.name}.main",
                self.path / "main.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._main_scene_class = getattr(module, self.manifest.main_scene)
        return self._main_scene_class
```

### 2.2 Module Template

Each module in `/stream_toy_apps/<module_name>/` contains:

```
memory_game/
├── manifest.py       # Module metadata
├── main.py          # Main scene class
├── icon.png         # Module icon (112x112)
└── assets/          # Module-specific resources
    ├── tiles/       # Tile sets for the game
    │   ├── tile_set_01/
    │   └── tile_set_02/
    └── sounds/
```

**Example: `manifest.py`**

```python
from stream_toy.module import ModuleManifest

def get_manifest() -> ModuleManifest:
    return ModuleManifest(
        name="Memory Game",
        version="1.0.0",
        author="StreamToy Team",
        description="Classic memory matching game with animals",
        icon_path="icon.png",
        main_scene="MemoryGameScene"
    )
```

**Example: `main.py`**

```python
from stream_toy.scene.base_scene import BaseScene
import random
from pathlib import Path

class MemoryGameScene(BaseScene):
    async def on_enter(self):
        """Initialize game."""
        self.cards = self._shuffle_cards()
        self.revealed = {}
        self.matched = set()
        self.first_card = None
        self.score = 0

        self._render_all_cards()
        self.submit_tiles()

        # Show back button
        self.set_tile_text(2, 4, "←")
        self.device.submit()

    def _shuffle_cards(self):
        """Create card pairs and shuffle."""
        assets = Path(__file__).parent / "assets" / "tiles" / "tile_set_01"
        images = list(assets.glob("tile_*.png"))[:7]  # 7 pairs = 14 cards
        cards = images * 2  # Duplicate for pairs
        random.shuffle(cards)
        return cards

    async def main_loop(self):
        while self._running:
            event = await self.input_manager.async_poll_event()

            if not event.is_pressed:
                continue

            # Check for exit (long press bottom-right)
            if event.row == 2 and event.col == 4 and event.long_press:
                from stream_toy.scene.module_launch_scene import ModuleLaunchScene
                self.switch_scene(ModuleLaunchScene)
                return

            # Handle card selection
            await self._handle_card_tap(event.row, event.col)

    async def _handle_card_tap(self, row: int, col: int):
        """Process card tap."""
        idx = row * 5 + col

        # Ignore if already matched or revealed
        if idx in self.matched or idx in self.revealed:
            return

        # Reveal card
        self.revealed[idx] = True
        self.set_tile_file(row, col, str(self.cards[idx]))
        self.submit_tiles()

        if self.first_card is None:
            self.first_card = idx
        else:
            # Check for match
            if self.cards[self.first_card] == self.cards[idx]:
                # Match!
                self.matched.add(self.first_card)
                self.matched.add(idx)
                self.score += 1

                # Check win condition
                if len(self.matched) == len(self.cards):
                    await self._show_win_screen()
            else:
                # No match, hide after delay
                await asyncio.sleep(1)
                self._hide_card(self.first_card // 5, self.first_card % 5)
                self._hide_card(row, col)
                self.submit_tiles()

            self.revealed.clear()
            self.first_card = None

    def _hide_card(self, row: int, col: int):
        """Show card back."""
        self.set_tile_text(row, col, "?", font_size=48)

    def _render_all_cards(self):
        """Render all cards face-down."""
        for row in range(3):
            for col in range(5):
                if row == 2 and col == 4:
                    continue  # Reserve for exit
                self._hide_card(row, col)

    async def _show_win_screen(self):
        """Display victory."""
        for row in range(3):
            for col in range(5):
                self.set_tile_text(row, col, "🎉", font_size=64)
        self.submit_tiles()

        await asyncio.sleep(3)

        from stream_toy.scene.module_launch_scene import ModuleLaunchScene
        self.switch_scene(ModuleLaunchScene)

    async def on_exit(self):
        """Cleanup."""
        pass
```

---

## Phase 3: Web Emulator

### 3.1 Web Server (`/stream_toy/web/server.py`)

**Flask + Socket.IO implementation:**

```python
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import base64
from io import BytesIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Reference to WebDevice instance
_web_device = None

def set_web_device(device):
    global _web_device
    _web_device = device

@app.route('/')
def index():
    return render_template('emulator.html')

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    # Send initial state
    if _web_device:
        _web_device.on_client_connected()

@socketio.on('button_press')
def handle_button_press(data):
    row, col = data['row'], data['col']
    if _web_device:
        _web_device._on_button_event(row, col, True)

@socketio.on('button_release')
def handle_button_release(data):
    row, col = data['row'], data['col']
    if _web_device:
        _web_device._on_button_event(row, col, False)

def emit_tile_update(row, col, image_base64):
    """Called by WebDevice to push updates."""
    socketio.emit('tile_update', {
        'row': row,
        'col': col,
        'image': image_base64
    })

def emit_led_update(led_data):
    """Push LED colors to client."""
    socketio.emit('led_update', {'leds': led_data})

def run_server(port=5000):
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
```

### 3.2 HTML Template (`/stream_toy/web/templates/emulator.html`)

```html
<!DOCTYPE html>
<html>
<head>
    <title>StreamToy Emulator</title>
    <style>
        body {
            margin: 0;
            background: #222;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            font-family: Arial, sans-serif;
        }

        #container {
            position: relative;
            width: 900px;
            height: 580px;
        }

        #streamdock {
            border: 10px solid #444;
            border-radius: 20px;
            background: black;
            display: block;
            margin: 20px auto;
        }

        .led-strip {
            position: absolute;
            display: flex;
        }

        .led {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin: 2px;
            background: #333;
        }

        #led-back-left { top: 0; left: 0; }
        #led-left { top: 80px; left: 0; flex-direction: column; }
        #led-front { bottom: 0; left: 0; }
        #led-right { top: 80px; right: 0; flex-direction: column; }
        #led-back-right { top: 0; right: 0; }

        .button-overlay {
            position: absolute;
            width: 112px;
            height: 112px;
            cursor: pointer;
            border: 2px solid transparent;
            transition: border 0.1s;
        }

        .button-overlay:hover {
            border-color: rgba(255, 255, 255, 0.3);
        }

        .button-overlay:active {
            border-color: rgba(255, 255, 255, 0.6);
        }
    </style>
</head>
<body>
    <div id="container">
        <canvas id="streamdock" width="800" height="480"></canvas>

        <!-- LED strips -->
        <div id="led-back-left" class="led-strip"></div>
        <div id="led-left" class="led-strip"></div>
        <div id="led-front" class="led-strip"></div>
        <div id="led-right" class="led-strip"></div>
        <div id="led-back-right" class="led-strip"></div>

        <!-- Button overlays -->
        <div id="button-overlays"></div>
    </div>

    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        const canvas = document.getElementById('streamdock');
        const ctx = canvas.getContext('2d');
        const socket = io();

        // StreamDock configuration
        const TILE_SIZE = 112;
        const TILE_GAP_X = 40;
        const TILE_GAP_Y = 42;
        const TILE_START_X = 0;
        const TILE_START_Y = 4;
        const COLS = 5;
        const ROWS = 3;

        // Initialize LEDs
        const ledSegments = {
            'back_left': 14,
            'left': 17,
            'front': 28,
            'right': 17,
            'back_right': 14
        };

        Object.entries(ledSegments).forEach(([name, count]) => {
            const container = document.getElementById(`led-${name.replace('_', '-')}`);
            for (let i = 0; i < count; i++) {
                const led = document.createElement('div');
                led.className = 'led';
                led.dataset.segment = name;
                led.dataset.index = i;
                container.appendChild(led);
            }
        });

        // Initialize button overlays
        const overlayContainer = document.getElementById('button-overlays');
        for (let row = 0; row < ROWS; row++) {
            for (let col = 0; col < COLS; col++) {
                const x = TILE_START_X + col * (TILE_SIZE + TILE_GAP_X);
                const y = TILE_START_Y + row * (TILE_SIZE + TILE_GAP_Y);

                const overlay = document.createElement('div');
                overlay.className = 'button-overlay';
                overlay.style.left = `${x + 20}px`;
                overlay.style.top = `${y + 20}px`;
                overlay.dataset.row = row;
                overlay.dataset.col = col;

                overlay.addEventListener('mousedown', () => {
                    socket.emit('button_press', { row, col });
                });

                overlay.addEventListener('mouseup', () => {
                    socket.emit('button_release', { row, col });
                });

                overlayContainer.appendChild(overlay);
            }
        }

        // Socket.IO event handlers
        socket.on('tile_update', (data) => {
            const img = new Image();
            img.onload = () => {
                const x = TILE_START_X + data.col * (TILE_SIZE + TILE_GAP_X);
                const y = TILE_START_Y + data.row * (TILE_SIZE + TILE_GAP_Y);
                ctx.drawImage(img, x, y, TILE_SIZE, TILE_SIZE);
            };
            img.src = 'data:image/png;base64,' + data.image;
        });

        socket.on('led_update', (data) => {
            data.leds.forEach((rgb, idx) => {
                const led = document.querySelectorAll('.led')[idx];
                if (led) {
                    led.style.background = `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
                }
            });
        });

        // Clear canvas initially
        ctx.fillStyle = 'black';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    </script>
</body>
</html>
```

---

## Phase 4: LED System

### 4.1 LED Manager (`/stream_toy/led_manager.py`)

**Integration with adafruit_led_animation:**

```python
import board
import neopixel
from adafruit_led_animation.animation import Animation
import threading
import time

class LEDManager:
    """Manages Neopixel LED strip with background/foreground animations."""

    def __init__(self, pin=board.D10, num_leds=90, brightness=0.5):
        self.pixels = neopixel.NeoPixel(
            pin, num_leds,
            brightness=brightness,
            auto_write=False
        )

        self.background_animation: Optional[Animation] = None
        self.foreground_animation: Optional[Animation] = None
        self.foreground_duration: Optional[float] = None
        self.foreground_start_time: Optional[float] = None

        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start LED animation thread."""
        self._running = True
        self._thread = threading.Thread(target=self._animation_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop LED thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def set_background_animation(self, animation: Animation):
        """Set idle background animation."""
        with self._lock:
            self.background_animation = animation

    def run_animation(self, animation: Animation, duration: Optional[float] = None):
        """Run foreground animation, pausing background."""
        with self._lock:
            self.foreground_animation = animation
            self.foreground_duration = duration
            self.foreground_start_time = time.time()

    def _animation_loop(self):
        """Main animation update loop."""
        while self._running:
            with self._lock:
                # Check if foreground animation should stop
                if self.foreground_animation:
                    if self.foreground_duration:
                        elapsed = time.time() - self.foreground_start_time
                        if elapsed >= self.foreground_duration:
                            self.foreground_animation = None

                    # Animate foreground
                    if self.foreground_animation:
                        self.foreground_animation.animate()
                else:
                    # Animate background
                    if self.background_animation:
                        self.background_animation.animate()

            self.pixels.show()
            time.sleep(0.05)  # ~20 FPS
```

**Usage in StreamDock293V3Device:**

```python
from adafruit_led_animation.animation.rainbow import Rainbow
from adafruit_led_animation.animation.pulse import Pulse
from adafruit_led_animation.color import RED, GREEN, BLUE

class StreamDock293V3Device(StreamToyDevice):
    def __init__(self):
        super().__init__()
        self.led_manager = LEDManager()

        # Set default background animation
        rainbow = Rainbow(self.led_manager.pixels, speed=0.1, period=5)
        self.led_manager.set_background_animation(rainbow)
        self.led_manager.start()

    def run_led_animation(self, animation, duration=None):
        self.led_manager.run_animation(animation, duration)

    # Example: Play success animation
    def play_success_animation(self):
        pulse = Pulse(self.led_manager.pixels, speed=0.1, color=GREEN, period=2)
        self.run_led_animation(pulse, duration=2.0)
```

---

## Phase 5: Testing & Configuration

### 5.1 Main Entry Point (`/main.py`)

```python
#!/usr/bin/env python3
import argparse
import logging
from stream_toy.runtime import StreamToyRuntime

def main():
    parser = argparse.ArgumentParser(description="StreamToy Runtime")
    parser.add_argument('--no-hardware', action='store_true',
                       help='Disable real hardware device')
    parser.add_argument('--no-web', action='store_true',
                       help='Disable web emulator')
    parser.add_argument('--web-port', type=int, default=5000,
                       help='Web emulator port (default: 5000)')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    runtime = StreamToyRuntime(
        enable_hardware=not args.no_hardware,
        enable_web=not args.no_web
    )

    try:
        runtime.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        runtime.shutdown()

if __name__ == '__main__':
    main()
```

### 5.2 Unit Tests (`/tests/`)

**Test structure:**

```
tests/
├── test_input_manager.py
├── test_scene_system.py
├── test_module_loading.py
├── test_led_manager.py
└── test_integration.py
```

**Example: `test_input_manager.py`**

```python
import unittest
import time
from stream_toy.input_manager import InputManager, InputEvent

class TestInputManager(unittest.TestCase):
    def setUp(self):
        self.manager = InputManager()

    def test_event_queue(self):
        """Test basic event queueing."""
        self.manager.on_device_key_event(0, 0, True)
        self.manager.on_device_key_event(0, 0, False)

        event1 = self.manager.poll_event()
        self.assertIsNotNone(event1)
        self.assertTrue(event1.is_pressed)

        event2 = self.manager.poll_event()
        self.assertIsNotNone(event2)
        self.assertFalse(event2.is_pressed)

    def test_long_press_detection(self):
        """Test long press detection."""
        self.manager._long_press_threshold = 0.5  # Short for testing

        self.manager.on_device_key_event(1, 1, True)
        time.sleep(0.6)
        self.manager.on_device_key_event(1, 1, False)

        event = self.manager.poll_event()
        self.assertTrue(event.long_press)

if __name__ == '__main__':
    unittest.main()
```

### 5.3 Requirements Files

**`requirements.txt` (Hardware):**
```
pyudev>=0.24
Pillow>=10.0
neopixel>=6.3
adafruit-circuitpython-led-animation>=2.7
cairosvg>=2.7  # For SVG rendering
```

**`requirements-emulator.txt` (Web):**
```
flask>=2.3
flask-socketio>=5.3
python-socketio>=5.9
Pillow>=10.0
cairosvg>=2.7
```

---

## Implementation Phases Summary

### Phase 1: Core Foundation (Week 1-2)
1. Create `StreamToyDevice` abstract base
2. Implement `StreamDock293V3Device` wrapper
3. Implement `InputManager`
4. Create `BaseScene` and `MenuScene`
5. Basic `StreamToyRuntime` initialization

**Deliverable:** Can display static tiles on hardware and handle button presses

### Phase 2: Scene System & Modules (Week 2-3)
1. Implement `ModuleLaunchScene`
2. Create module loading system
3. Build first example module (Memory Game)
4. Test scene transitions

**Deliverable:** Functional module launcher with one playable game

### Phase 3: Web Emulator (Week 3-4)
1. Implement `WebDevice`
2. Create Flask server with Socket.IO
3. Build HTML/JS emulator UI
4. Test synchronization between hardware and web

**Deliverable:** Full emulator accessible in browser, synced with hardware

### Phase 4: LED System (Week 4)
1. Implement `LEDManager`
2. Integrate with `StreamDock293V3Device`
3. Create default animations
4. Test with physical LED strip

**Deliverable:** Working LED animations synchronized with games

### Phase 5: Polish & Testing (Week 5)
1. Write comprehensive unit tests
2. Add error handling and logging
3. Create more example modules
4. Documentation and README updates

**Deliverable:** Production-ready system with multiple games

---

## Key Technical Decisions

### 1. Async Architecture
- Use `asyncio` for all scene logic to enable non-blocking operations
- Scenes can await user input without blocking device updates
- Simplifies timeout and animation handling

### 2. Device Abstraction
- Abstract interface allows hardware and emulator to coexist
- Future support for different StreamDock models requires only new device class
- Testing can be done entirely in emulator

### 3. Module Isolation
- Each module is self-contained with manifest
- Modules cannot access each other's state
- Runtime provides controlled access to device and input

### 4. LED Background Threading
- LED animations run on separate thread to avoid blocking main loop
- Foreground/background system allows temporary effects
- Web emulator fakes LED updates via WebSocket

### 5. Input Event Queue
- Thread-safe queue decouples device callbacks from scene logic
- Long-press detection handled at input layer, not scene layer
- Scenes can poll synchronously or asynchronously

---

## File Structure Reference

```
/workspace/
├── stream_toy/                      # Core library
│   ├── __init__.py
│   ├── runtime.py                   # StreamToyRuntime
│   ├── module.py                    # Module system
│   ├── input_manager.py             # InputManager
│   ├── led_manager.py               # LEDManager
│   │
│   ├── device/
│   │   ├── __init__.py
│   │   ├── stream_toy_device.py    # Abstract base
│   │   ├── streamdock293v3_device.py
│   │   └── web_device.py
│   │
│   ├── scene/
│   │   ├── __init__.py
│   │   ├── base_scene.py
│   │   ├── menu_scene.py
│   │   └── module_launch_scene.py
│   │
│   └── web/                         # Web emulator
│       ├── __init__.py
│       ├── server.py
│       └── templates/
│           └── emulator.html
│
├── stream_toy_apps/                 # User modules
│   ├── memory_game/
│   │   ├── manifest.py
│   │   ├── main.py
│   │   ├── icon.png
│   │   └── assets/
│   │
│   ├── reaction_game/
│   └── audio_player/
│
├── tests/                           # Unit tests
│   ├── test_input_manager.py
│   ├── test_scene_system.py
│   └── test_module_loading.py
│
├── main.py                          # Entry point
├── demo.py                          # Hardware demo (existing)
├── requirements.txt
├── requirements-emulator.txt
├── CLAUDE.md                        # Project docs
├── IMPLEMENTATION_PLAN.md           # This file
└── README.md
```

---

## Risk Mitigation

### 1. Device Instability
**Risk:** StreamDock crashes with rapid commands
**Mitigation:**
- Always wait for ACK callback before sending next refresh
- Implement retry logic with exponential backoff
- Add device watchdog to detect and recover from hangs

### 2. Web Emulator Sync
**Risk:** Web and hardware out of sync
**Mitigation:**
- Use event-driven updates, not polling
- Maintain single source of truth in runtime
- Test with both devices enabled simultaneously

### 3. Module Crashes
**Risk:** Buggy module crashes entire system
**Mitigation:**
- Wrap module loading in try/except with logging
- Scene transitions should catch exceptions
- Implement watchdog to detect frozen scenes

### 4. LED Performance
**Risk:** LED updates slow down main loop
**Mitigation:**
- LEDs run on separate thread
- Use `pixels.auto_write=False` for batch updates
- Target 20 FPS (50ms updates), not higher

### 5. Input Latency
**Risk:** Button presses feel unresponsive
**Mitigation:**
- Process input events immediately in callback
- Visual feedback (e.g., button highlight) before action
- Long-press threshold tunable per-scene

---

## Future Enhancements (Post-MVP)

1. **Persistent Storage**
   - Save game progress, high scores
   - User preferences (brightness, animation speed)
   - Module state persistence

2. **Audio System**
   - Background music per scene
   - Sound effects for button presses
   - Text-to-speech for audiobooks

3. **Network Features**
   - Download new modules from repository
   - Over-the-air updates
   - Cloud save sync

4. **Advanced LED Patterns**
   - Per-button LED zones
   - Music-reactive animations
   - Game-specific patterns

5. **Accessibility**
   - High contrast mode
   - Larger text options
   - Audio cues for navigation

6. **Developer Tools**
   - Hot-reload for module development
   - Performance profiler
   - Module debugging UI in emulator

---

## Success Criteria

### Functional Requirements
- ✅ Launches with both hardware and web emulator
- ✅ Module launcher shows all available games
- ✅ Can play at least 3 different game modules
- ✅ Button presses detected reliably (< 100ms latency)
- ✅ LED animations run smoothly (no visible stuttering)
- ✅ Long-press bottom-right returns to launcher from any module
- ✅ Web emulator accurately reflects hardware state

### Performance Requirements
- ✅ Tile updates complete within 3 seconds
- ✅ No device crashes during normal operation
- ✅ LED animations maintain 20+ FPS
- ✅ Web emulator responsive on local network

### Code Quality Requirements
- ✅ All core modules have unit tests (>70% coverage)
- ✅ No circular imports
- ✅ Clean separation of concerns (device/scene/module layers)
- ✅ Comprehensive error logging
- ✅ Type hints on all public APIs

---

## Conclusion

This implementation plan provides a complete roadmap for building the StreamToyKeyboard system as specified in CLAUDE.md. The architecture emphasizes:

- **Modularity:** Clean separation between device layer, scene system, and modules
- **Flexibility:** Abstract interfaces allow for multiple devices and easy testing
- **Extensibility:** New games can be added without modifying core library
- **Robustness:** Error handling and device stability measures throughout
- **Developer Experience:** Web emulator enables rapid development without hardware

The phased approach allows for incremental development and testing, with each phase building on the previous. The system is designed to be maintainable, testable, and extensible for future enhancements.
