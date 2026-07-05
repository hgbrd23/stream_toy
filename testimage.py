from PIL import Image, ImageDraw
import os

# Image dimensions
WIDTH, HEIGHT = 800, 480

# Key parameters
KEY_SIZE = 128
COLS, ROWS = 5, 3

# Calculate spacing
H_GAP = (WIDTH - COLS * KEY_SIZE) / (COLS - 1)  # 4 gaps between 5 keys
V_GAP = 44  # Fixed vertical gap

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'fullscreen')


def create_checkerboard():
    """Create a checkerboard pattern background."""
    img = Image.new('RGB', (WIDTH, HEIGHT))
    pixels = img.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if (x + y) % 2 == 0:
                pixels[x, y] = (255, 255, 255)  # White
            else:
                pixels[x, y] = (0, 0, 0)  # Black
    return img


def get_key_positions():
    """Generate key positions as (x, y) tuples."""
    positions = []
    for row in range(ROWS):
        for col in range(COLS):
            x = col * (KEY_SIZE + H_GAP)
            y = row * (KEY_SIZE + V_GAP)
            positions.append((x, y))
    return positions


def create_test_image_with_background():
    """Create test.png: checkerboard background with 50% black key overlays."""
    img = create_checkerboard()

    overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    grey_color = (0, 0, 0, 128)  # 50% opacity black

    for x, y in get_key_positions():
        draw.rectangle([x, y, x + KEY_SIZE, y + KEY_SIZE], fill=grey_color)

    img = img.convert('RGBA')
    img = Image.alpha_composite(img, overlay)
    img = img.convert('RGB')

    return img


def create_test_image_without_background():
    """Create test2.png: transparent keys with 50% black gaps."""
    img = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 128))  # 50% black
    draw = ImageDraw.Draw(img)

    transparent = (0, 0, 0, 0)

    for x, y in get_key_positions():
        draw.rectangle([x, y, x + KEY_SIZE, y + KEY_SIZE], fill=transparent)

    return img


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Create test.png with checkerboard background
    test1 = create_test_image_with_background()
    test1_path = os.path.join(OUTPUT_DIR, 'test.png')
    test1.save(test1_path)
    print(f"Created {test1_path}")

    # Create test2.png without background
    test2 = create_test_image_without_background()
    test2_path = os.path.join(OUTPUT_DIR, 'test2.png')
    test2.save(test2_path)
    print(f"Created {test2_path}")

    # Print layout info
    last_row_bottom = 2 * (KEY_SIZE + V_GAP) + KEY_SIZE
    bottom_gap = HEIGHT - last_row_bottom
    print(f"\nLayout: {WIDTH}x{HEIGHT}")
    print(f"Keys: {KEY_SIZE}x{KEY_SIZE}, {COLS} cols x {ROWS} rows")
    print(f"Horizontal gap: {H_GAP:.2f}px")
    print(f"Vertical gap: {V_GAP}px")
    print(f"Bottom gap: {bottom_gap}px")


if __name__ == '__main__':
    main()
