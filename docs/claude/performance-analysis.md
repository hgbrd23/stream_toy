# Startup and drawing performance analysis

Static analysis of the app, the SDK and `libtransport` (2026-10-12). The Pi was
not reachable from the analysis container, so all timings are estimates
(local CPU time scaled by roughly 10-15x for the Pi Zero 2 W). Measure on the
device before implementing: `lsusb -t` (bus speed), `perf_counter` around each
`setKeyImgDualDevice` call and around a full `submit()`, whether the 1 s ACK
wait at init always times out, and `journalctl -u <service>` timestamps per
startup stage.

## What libtransport actually does

`libtransport_arm.so` imports only hidapi plus `stat`, `std::ifstream`,
`memcpy`, `memset`. It contains no JPEG encoder, no sleeps, no mutex and no ACK
handling. All image conversion happens in Python.

* `TranSport_setKeyImgDualDevice(path, key)` (the call we use): `stat(path)`,
  one 1025-byte header report (`CRT..BAT <size> <key>`), then the file in
  1024-byte chunks, one synchronous `hid_write` each.
* `TranSport_refresh`: one small `CRT..STP` report, returns immediately.
* `setKeyImgDataDualDevice` is the same file-based code. `setKeyImg` uses the
  legacy 513-byte protocol (twice the writes). `setBackgroundImg(buf, size)`
  takes memory but uses the legacy protocol. `setKeyImgData_(vector)` is C++
  only. There is no batch or no-ACK mode.
* The only in-memory route is `TranSport_write(buf, 1025)` with the BAT
  header and chunks built in Python. That reimplements library logic (needs an
  explicit decision); the gain is one stat/open/read per tile plus the SD-card
  write for one-off tiles.
* Tile sizes at quality 85: text tiles 1.4-1.7 KB (3 reports), cover/card
  tiles 4.6-5.3 KB (6-7 reports). A full 15-tile screen is 60-100 reports. At
  USB full speed each report costs about 16 ms, so a full screen could take
  over a second; at high speed tens of ms.

## Startup pipeline

| # | Stage | Where | Estimate on Pi |
|---|-------|-------|----------------|
| 1 | Interpreter + `import stream_toy.runtime` (PIL, yaml, asyncio, adafruit) | main.py:24 | 1-2 s |
| 2 | LED init (board/neopixel import, Rainbow, LED thread) runs before the device | runtime.py:83-98 | 0.3-1 s |
| 3 | `sudo chown` subprocess (service runs as root, udev rule exists) | streamdock293v3_device.py:113 | 0.1-0.5 s |
| 4 | `DeviceManager.enumerate()`: 15 `hid_enumerate` calls | :121-122 | 0.1-0.4 s |
| 5 | `init()` + `_wait_for_ack(1.0)` (ACK may never come, so a fixed 1 s) | :150-162 | up to 1 s |
| 6 | Background thread: flask/socketio import (largest import), miniaudio, manifests | runtime.py:125-144 | 3-6 s, overlapped |
| 7 | Splash via SDK `set_touchscreen_image`: PNG decode, rotate, JPEG encode, temp file in cwd, ~53 reports, ACK wait | runtime.py:198, StreamDock293V3.py:27-36 | 0.1-0.3 s CPU + 0.5-3 s device |
| 8 | After key press: black background, same path + ACK | runtime.py:234-235 | 0.5-3 s |
| 9 | `pip install --upgrade yt-dlp[default]` on every boot | runtime.py:181, 241-264 | 10-30 s CPU, competing |
| 10 | Launcher: `asyncio.sleep(0.2)`, `clear_all_tiles` (15 tiles + web pass), then menu | module_launch_scene.py:53, menu_scene.py:75 | 0.5-1 s |

Ranked changes:

1. Remove or raise `CPUQuota=90%` (install.sh:447) and defer or `nice` the
   yt-dlp upgrade (runtime.py:181). The quota caps the whole service at 0.9 of
   one core on a 4-core Pi, and pip starves the first menu render.
2. Show the splash sooner: move LED init after the splash, drop the
   `sudo chown`, shorten the initial `_wait_for_ack(1.0)` if it always times
   out. Together 1-2.5 s earlier.
3. Pre-encode the splash and the black background as rotated native JPEGs
   (cached like tiles) and call `transport.setBackgroundImgDualDevice`
   directly instead of `set_touchscreen_image`.
4. Enumerate only the 293V3 IDs (VID 0x6603, PIDs 0x1005/0x1006/0x1010).
5. Smaller: drop the `asyncio.sleep(0.2)`; precompile `.pyc` in install.sh
   (rsync excludes `__pycache__`, so the first boot after each deploy compiles
   everything); use yaml's `CSafeLoader`.

## Drawing path (cache hit)

1. Scene `set_tile_*`: build key, md5, stat cache file (base_scene.py:295-302).
2. `DisplayStateManager.set_tile` takes its lock and calls each device, which
   does `Path.exists()` and queues (display_state_manager.py:121,
   streamdock293v3_device.py:539-543, web_device.py:183-187).
3. `submit()` calls the devices sequentially on the asyncio thread
   (display_state_manager.py:140).
4. Hardware `submit_tiles` (streamdock293v3_device.py:545-616): dedup by
   `cache_key`, `_ensure_native_cached` (about four stats), ctypes
   `setKeyImgDualDevice` (stat, open, read, 1 + ceil(size/1024) writes), one
   `refresh()` without ACK wait (correct for tiles).
5. Web `submit_tiles` (web_device.py:189-227) for every queued tile, no
   dedup: `Image.open`, LANCZOS resize, PNG re-encode, base64, emit,
   `image.copy()`, then `time.sleep(0.1)` on the event loop.

Cache miss adds: PIL render, PNG encode + write + rename (base_scene.py:178),
then PNG decode, rotate, JPEG q85 encode and a second write
(streamdock293v3_device.py:286-303). Two SD writes per new tile.

Ranked changes:

1. Fix the web device hot path (it runs in production because the service does
   not pass `--no-web`): remove the `time.sleep(0.1)` (web_device.py:227),
   dedup by `cache_key`, send the cached PNG bytes without decode/encode, skip
   the work with no client connected, and ship a 112x112 `gear.png` (currently
   1024x1024, 2.1 MB, roughly 250 ms on the Pi per launcher draw). Expected
   150-400 ms less event-loop blocking per screen update.
2. Draw a full screen once on scene switch. `MenuScene.on_enter` submits 15
   black tiles via `clear_all_tiles()` and then the real tiles
   (menu_scene.py:75, 92). Fill unused slots with black in the same batch and
   submit once: half the USB traffic and no black flash.
3. Take USB I/O off the event loop (`asyncio.to_thread` or one writer thread
   that coalesces the latest frame per tile), serialised with
   `set_background_image`.
4. Use `data/cache/button_tiles` for native JPEGs. `CACHE_DIR` is created
   (:74, :107) but `_get_cached_native_path` writes `*_native.jpg` next to the
   assets (:242), and `rsync --delete` (install.sh:337) removes them on every
   deploy. Pre-warm launcher and module icons during the splash wait.
5. Encode one-off text tiles (player `m:ss` and `%` every second,
   player_scene.py:243-246) straight from the PIL image to the native JPEG
   instead of PNG write, PNG decode, JPEG encode.

Keep: ACK waits for background images, quality 85 for every native JPEG.

## Bugs affecting performance or safety

1. Button events count as ACKs. The check is `bytes[3]==0 and bytes[4]==0`
   (streamdock293v3_device.py:346); key events share that prefix with the key
   in byte 9. The release of the button that skips the splash ends the black
   background ACK wait early, so tiles are sent while the background is still
   refreshing (the crash case from CLAUDE.md). Fix: also require key == 0.
2. Stale ACKs from tile refreshes can be queued when a background upload sets
   `_device_busy`, shortening that wait as well.
3. The web device ignores `cache_key` and re-sends unchanged tiles every
   submit (the player submits every second).
4. Double submit on every menu entry (`clear_all_tiles`), visible flicker.
5. About 8 INFO log lines per button event in the read loop (:352-375) and the
   SDK's `read_()` prints every report (LibUSBHIDAPI.py:169). Demote to DEBUG.
6. A constant 10 Hz web LED push (web_device.py:123-136) runs with no browser
   connected.

## Implemented (2026-10-12)

* Startup: hardware device opens before LED init; `sudo chown` removed; only
  the 293V3 product ids are probed; splash and black background use cached
  native JPEGs sent via `setBackgroundImgDualDevice` (no temp file); yt-dlp
  upgrade delayed by 3 minutes and run under `nice`; `CPUQuota` removed from
  the service unit; sources precompiled by install.sh; icon caches warmed
  during the splash; the 0.2 s launcher sleep removed.
* Drawing: `DisplayStateManager.submit()` only signals a display worker
  thread, which drains the device queues (several submits collapse into
  one flush, USB and image I/O never block the asyncio loop). Devices
  implement `flush_tiles(batch)`. Native JPEGs and browser PNGs live in
  `data/cache/button_tiles` (`stream_toy/tile_cache.py`), survive deploys
  and are generated once per source. The web device deduplicates by cache
  key, sends cached PNG bytes without re-encoding, skips emits and the LED
  push when no browser is connected, and no longer sleeps. Menus and the
  LED playground draw black and content in one batch.
* Bugs: button events are no longer taken as the device ACK; all USB writes
  are serialised through a transport lock held through the background ACK
  wait; the tile dedup state is reset after a background image; per-event
  INFO logs demoted to DEBUG.
* Still open: the 1 s ACK wait at init (needs a journal measurement), the
  stale-ACK race for background images, text tiles still go through the
  PNG cache before the native JPEG is produced.
