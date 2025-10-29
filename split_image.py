#!/usr/bin/env python3
from PIL import Image
import os

# Load the uploaded image
img_path = os.path.join(os.path.dirname(__file__), 'img','memory', 'SSP_Memory_game_Farm_Animals-4.jpg')
img = Image.open(img_path)

# Define grid size
rows, cols = 4, 6  # 5 rows and 6 columns
margins = [20, 27, 20, 31]  # left, top, right, bottom margins
spacing = [25, 25]  # horizontal and vertical spacing
button_width = (img.width - margins[0] - margins[2] - (cols - 1) * spacing[0]) // cols
button_height = (img.height - margins[1] - margins[3] - (rows - 1) * spacing[0]) // rows

output_dir = os.path.dirname(img_path)
# Crop and save each button as an individual PNG
button_paths = []
for row in range(rows):
    for col in range(cols):
        left = margins[0] + col * button_width + col * spacing[0]
        upper = margins[1] + row * button_height + row * spacing[1]
        right = left + button_width
        lower = upper + button_height
        button = img.crop((left, upper, right, lower))
        # resize the button to 64x64
        #button = button.resize((64, 64), Image.LANCZOS)
        button_path = os.path.join(output_dir, f"button_{str(col+1).zfill(2)}_{str(row+1).zfill(2)}.png")
        button.save(button_path, "PNG")
        button_paths.append(button_path)

button_paths[:5]  # Show the first few paths as confirmation