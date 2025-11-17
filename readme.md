# PIN Assignments
## Audio
2x MAX98357A breakout boards

| Signal | Pi Pin       | Left Amp | Right Amp | Color |
|--------|--------------|----------|-----------|-------|
| BCLK | 12 (GPIO 18) | BCLK | BCLK | green |
| LRCLK | 35 (GPIO 19) | LRCLK | LRCLK | yellow |
| DIN | 40 (GPIO 21) | DIN | DIN | blue |
| 5V | Power Module | VDD | VDD | red |
| GND | Power Module | GND | GND | brown |
| SD_MODE | 16 (GPIO 23) | Direct | Through 200kΩ | purple |

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

## LEDs
| Signal | Pi Pin       | Color | Function             |
|--------|--------------|-------|----------------------|
| DATA   | GPIO 10      | orange| Neopixel             |
 | ACT_LED | GPIO 26      | | Activity LED via 10k |
| 5V     | Power Module | 
| GND    | Power Module | 

The Activity LED is connected via a 10k resistor so it just glows a bit. I used a white LED.

# System Requirements
Install the ARM64 lite Pi OS package.

```shell
apt install -y libudev-dev libusb-1.0-0-dev libhidapi-libusb0 python3-dev python3-pil python3-pyudev libegl1 libgl1 \
  libopengl0 libxcb-cursor0 libxkbcommon0 mpg123 portaudio19-dev python3-pyaudio ffmpeg 
```

On **Raspberry Pi OS Bookworm and later**, the config file lives at
`/boot/firmware/config.txt` (instead of `/boot/config.txt`).

---

### 🧾 Here’s exactly what to change

1. **Enable I²S**
   Find this commented line:

   ```bash
   #dtparam=i2s=on
   ```

   and **uncomment** it (remove the `#`):

   ```bash
   dtparam=i2s=on
   ```

2. **Disable the built-in analog audio**
   The line:

   ```bash
   dtparam=audio=on
   ```

   enables the Pi’s onboard PWM audio, which conflicts with the I²S interface.
   Comment it out:

   ```bash
   #dtparam=audio=on
   ```

3. **Add the MAX98357A overlay**
   Scroll to the very end of the file (after `[all]`) and add:

   ```bash
   dtoverlay=max98357a,sdmode-pin=23
   ```

   The `sdmode-pin=23` flag tells the Pi to use this GPIO for shutdown to reduce clicking noises.

---

### ✅ Your edited `/boot/firmware/config.txt` should contain these relevant lines:

```bash
# Enable I²S audio for MAX98357A amps
dtparam=i2s=on
# Enable SPI for LEDs
dtparam=spi=on
enable_uart=1
# Disable built-in analog audio
#dtparam=audio=on
# Use two MAX98357A amps (manual L/R via SD pins)
dtoverlay=max98357a,sdmode-pin=23
# Enable GPIO activity LED
dtparam=act_led_gpio=26
dtparam=act_led_trigger=heartbeat

```

```
pcm.!default {
    type softvol
    slave.pcm "dmixer"
    control {
        name "Master"
        card 0
    }
    min_dB -30.0
    max_dB 0.0
}

pcm.dmixer {
    type dmix
    ipc_key 1024
    slave.pcm "hw:0,0"
    slave.rate 48000
}

ctl.!default {
    type hw
    card 0
}

```
```
speaker-test -t wav -c 2 -l 1
amixer scontrols
mpg123 sample-15s.mp3
amixer set Master 80%
alsamixer
```


# Quirks
If you get a segmentation fault when opening:
```shell
sudo chown root:$USER /dev/bus/usb/001/00*
```

# Hardware
Hailege 3pcs MAX98357 Class D Audio Amplifier Board I2S 3W 
https://www.amazon.de/-/en/dp/B0CJY1C287?ref=ppx_yo2ov_dt_b_fed_asin_title

Micro Speakers 3 Watt 4 Ohm
https://www.amazon.de/-/en/dp/B09JHSZ7KJ?ref=ppx_yo2ov_dt_b_fed_asin_title&th=1

Project Box ABS Plastic Distribution Box IP65 Waterproof Electrical Boxes Universal Housing Black Outer Size 200 x 120 x 56 mm
https://www.amazon.de/-/en/dp/B0CZ3GPHN3?ref=ppx_yo2ov_dt_b_fed_asin_title

4 Rechargeable 3.7 V Batteries, Flat Top 3300 mAh
https://www.amazon.de/-/en/dp/B0DCK4PTXS?ref=ppx_yo2ov_dt_b_fed_asin_title

18650 Battery Holder
https://www.amazon.de/-/en/dp/B0D2D6SDP1?ref=ppx_yo2ov_dt_b_fed_asin_title

