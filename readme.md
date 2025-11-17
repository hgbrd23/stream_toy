# Power Supply
4x 18650 cells with IP5310 power bank module.

The IP5310 module has one USB input (maybe can also be used as output?) for charging, a battery connection and a 5V/USB 
output.  
I attached a self made power distribution board to the 5V output. 

The power distribution board has 2x 1000uF capacitors to help with load spikes.

## Cell Configuration
Parallel (4P)
```
Cell 1 ─┐
Cell 2 ─┼─ 3.7V nominal, 13,200mAh ─── IP5310
Cell 3 ─┤
Cell 4 ─┘
```

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
### Diagram Capacitors
There were some problems with audio quality, especially on battery. Most likely due to switching noise from 
the IP5310 power IC. SOmetimes even L/R separation of the amps was not working and lots of noise/clicking.

So 3 capacitors solved it at the amps:
```
Each amp VDD -> GND:
    ├── 0.1µF ceramic (closest!)
    Amp 2
    ├── 10µF ceramic (close!)
    ├── 0.1µF ceramic (closest!)
    Amp 1
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
Use the ARM64 lite Pi OS package.

## Install packages
```shell
apt install -y libudev-dev libusb-1.0-0-dev libhidapi-libusb0 python3-dev python3-pil python3-pyudev libegl1 libgl1 \
  libopengl0 libxcb-cursor0 libxkbcommon0 mpg123 portaudio19-dev python3-pyaudio ffmpeg 
```

On **Raspberry Pi OS Bookworm and later**, the config file lives at
`/boot/firmware/config.txt` (instead of `/boot/config.txt`).


## Edit `/boot/firmware/config.txt`
Should contain these relevant lines in the last section of the config:

Right in the beginning of the file:
```bash
# Enable I²S audio for MAX98357A amps
dtparam=i2s=on
# Enable SPI for LEDs
dtparam=spi=on
enable_uart=1
# Disable built-in analog audio
#dtparam=audio=on
```
In section `[all]`
```bash
# Use two MAX98357A amps (manual L/R via SD pins)
dtoverlay=max98357a,sdmode-pin=23
# Enable GPIO activity LED
dtparam=act_led_gpio=26
dtparam=act_led_trigger=heartbeat
```
## Sound configuration
Paste this into `/etc/asound.conf`:
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
## Reboot
After the changes above, reboot.

## Testing sound
Commands for testing sound output:
```
speaker-test -t wav -c 2 -l 1
amixer scontrols
mpg123 sample-15s.mp3
# Mixer not working, we are doing our own volume in Python
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

