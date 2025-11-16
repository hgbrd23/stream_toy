#!/usr/bin/env python3
"""List available PyAudio devices."""

import pyaudio

p = pyaudio.PyAudio()

print("=" * 60)
print("Available Audio Devices")
print("=" * 60)

default_output = p.get_default_output_device_info()
print(f"\nDefault Output Device: {default_output['index']} - {default_output['name']}")
print()

for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)

    # Only show output devices (maxOutputChannels > 0)
    if info['maxOutputChannels'] > 0:
        is_default = " [DEFAULT]" if i == default_output['index'] else ""
        print(f"Device {i}: {info['name']}{is_default}")
        print(f"  Max Output Channels: {info['maxOutputChannels']}")
        print(f"  Default Sample Rate: {int(info['defaultSampleRate'])} Hz")
        print(f"  Host API: {p.get_host_api_info_by_index(info['hostApi'])['name']}")
        print()

p.terminate()

print("=" * 60)
print("Recommendation: Look for a device with 'MAX98357' or 'I2S' in the name")
print("=" * 60)
