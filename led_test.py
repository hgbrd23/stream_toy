import time

import board
import neopixel
from adafruit_led_animation import color
from adafruit_led_animation.animation.blink import Blink
from adafruit_led_animation.animation.sparkle import Sparkle

N_BACK_LEFT_RIGHT = 14
N_LEFT_RIGHT = 17
N_FRONT = 28

DATA_PIN = board.D10
pixels = neopixel.NeoPixel(DATA_PIN, n=N_BACK_LEFT_RIGHT * 2 + N_LEFT_RIGHT * 2 + N_FRONT, brightness=0.05,
                           auto_write=False)

# 14px, 0-13: left back
# 17px, 14-30: left
# 28px front
# 17px right
# 14px right back


pixels.fill((255, 255, 255))
pixels.show()
time.sleep(2)
pixels[0:N_BACK_LEFT_RIGHT] = [(255, 0, 0)] * N_BACK_LEFT_RIGHT
pixels[N_BACK_LEFT_RIGHT:N_BACK_LEFT_RIGHT + N_LEFT_RIGHT] = [(0, 255, 0)] * N_LEFT_RIGHT
pixels[N_BACK_LEFT_RIGHT + N_LEFT_RIGHT:N_BACK_LEFT_RIGHT + N_LEFT_RIGHT + N_FRONT] = [(0, 0, 255)] * N_FRONT
pixels[N_BACK_LEFT_RIGHT + N_LEFT_RIGHT + N_FRONT:N_BACK_LEFT_RIGHT + N_LEFT_RIGHT + N_FRONT + N_LEFT_RIGHT] = [(255, 255, 0)] * N_LEFT_RIGHT
pixels[N_BACK_LEFT_RIGHT + N_LEFT_RIGHT + N_FRONT + N_LEFT_RIGHT:N_BACK_LEFT_RIGHT + N_LEFT_RIGHT + N_FRONT + N_LEFT_RIGHT + N_BACK_LEFT_RIGHT] = [(255, 0, 255)] * N_BACK_LEFT_RIGHT
pixels.show()
time.sleep(5)

def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 0 or pos > 255:
        r = g = b = 0
    elif pos < 85:
        r = int(pos * 3)
        g = int(255 - pos * 3)
        b = 0
    elif pos < 170:
        pos -= 85
        r = int(255 - pos * 3)
        g = 0
        b = int(pos * 3)
    else:
        pos -= 170
        r = 0
        g = int(pos * 3)
        b = int(255 - pos * 3)
    return (r, g, b)


def rainbow_cycle(wait, rainbow_speed=100):
    """Continuous rainbow effect that cycles through all colors.

    Args:
        wait: Time to wait between frames (affects FPS)
        rainbow_speed: Speed of rainbow cycle in units per second (affects color progression)
    """
    frame_count = 0
    start_time = time.time()
    last_fps_time = start_time
    rainbow_start_time = start_time

    while True:
        frame_start = time.time()

        # Calculate rainbow position based on elapsed time, not frame count
        elapsed_time = frame_start - rainbow_start_time
        j = int((elapsed_time * rainbow_speed) % 256)

        for i in range(len(pixels)):
            rc_index = (i * 256 // len(pixels)) + j
            pixels[i] = wheel(rc_index & 255)
        pixels.show()
        time.sleep(wait)

        frame_count += 1
        current_time = time.time()

        # Calculate and display FPS every second
        if current_time - last_fps_time >= 1.0:
            fps = frame_count / (current_time - start_time)
            print(f"FPS: {fps:.2f}, Rainbow position: {j}")
            last_fps_time = current_time
            frame_count = 0
            start_time = current_time


try:
    #print("Starting rainbow cycle... Press Ctrl+C to stop")
    #rainbow_cycle(0.01)
    sparkle = Sparkle(pixels, 0.2, color.WHITE, num_sparkles=1)

    while True:
        sparkle.animate()
except KeyboardInterrupt:
    print("\nStopped by user")
    pixels.fill((0, 0, 0))  # Turn off all LEDs
    pixels.show()
finally:
    pixels.deinit()

