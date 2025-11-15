#!/usr/bin/env python3
"""
Create simple module icons
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_memory_game_icon():
    """Create icon for memory game."""
    img = Image.new('RGB', (112, 112), '#1a1a2e')
    draw = ImageDraw.Draw(img)

    # Draw question mark
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
    except:
        font = ImageFont.load_default()

    text = "?"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (112 - text_width) // 2
    y = (112 - text_height) // 2

    draw.text((x, y), text, fill='#00d9ff', font=font)

    img.save('/workspace/stream_toy_apps/memory_game/icon.png')
    print("Created memory_game icon")

def create_reaction_game_icon():
    """Create icon for reaction game."""
    img = Image.new('RGB', (112, 112), '#1a1a2e')
    draw = ImageDraw.Draw(img)

    # Draw lightning bolt  (simplified as zigzag)
    draw.polygon([(56, 18), (61, 44), (70, 44), (53, 70), (57, 53), (44, 53)], fill='#ffff00')

    img.save('/workspace/stream_toy_apps/reaction_game/icon.png')
    print("Created reaction_game icon")

if __name__ == '__main__':
    # Create directories
    os.makedirs('/workspace/stream_toy_apps/memory_game', exist_ok=True)
    os.makedirs('/workspace/stream_toy_apps/reaction_game', exist_ok=True)

    create_memory_game_icon()
    create_reaction_game_icon()

    print("All icons created successfully")
