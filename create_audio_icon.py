#!/usr/bin/env python3
"""Create audio player icon"""

from PIL import Image, ImageDraw, ImageFont

# Create 112x112 image with blue background
img = Image.new('RGB', (112, 112), color='#2196F3')
draw = ImageDraw.Draw(img)

# Draw a simple music note symbol using basic shapes
# Note stem
draw.rectangle([65, 25, 72, 70], fill='white')

# Note head (circle)
draw.ellipse([55, 65, 75, 85], fill='white')

# Note flag (curve approximation)
draw.polygon([(72, 25), (85, 30), (85, 40), (72, 35)], fill='white')

# Save
img.save('/workspace/stream_toy_apps/audio_player/assets/icon.png')
print("Icon created successfully")
