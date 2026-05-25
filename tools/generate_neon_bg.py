"""Generates a clean Neon Nexus background with slot outlines at exact pixel positions."""
from PIL import Image, ImageDraw

W, H = 1920, 1080
GREEN = (0, 255, 102)
DARK = (3, 8, 6)

# Canonical slots (matches assets/neon_nexus_layout.json)
SLOTS = {
    "question": (86, 76, 1180, 303),
    "answer_a": (86, 335, 618, 530),
    "answer_b": (648, 335, 1180, 530),
    "answer_c": (86, 548, 618, 743),
    "answer_d": (648, 548, 1180, 743),
    "footer": (86, 767, 1180, 832),
    "ladder": (1277, 76, 1814, 1004),
    "exit": (38, 22, 258, 76),
}


def main():
    img = Image.new("RGB", (W, H), DARK)
    draw = ImageDraw.Draw(img, "RGBA")

    # Subtle vertical gradient
    for y in range(H):
        t = y / H
        c = int(3 + 12 * t)
        draw.line([(0, y), (W, y)], fill=(0, c, max(2, c // 2)))

    # Hex grid dots (very subtle)
    for x in range(0, W, 48):
        for y in range(0, H, 42):
            draw.ellipse([x, y, x + 2, y + 2], fill=(0, 40, 24))

    # Play area separator
    draw.line([(1240, 40), (1240, 1040)], fill=(0, 80, 45), width=2)

    # Slot frames (empty — UI draws text on top)
    for name, box in SLOTS.items():
        x1, y1, x2, y2 = box
        draw.rounded_rectangle([x1, y1, x2, y2], radius=8, outline=GREEN, width=2)
        if name.startswith("answer"):
            # Hex-ish end caps hint
            mid_y = (y1 + y2) // 2
            draw.polygon([(x1 - 8, mid_y), (x1, y1 + 12), (x1, y2 - 12)], outline=GREEN)

    # Ladder track line
    lx = 1320
    draw.line([(lx, 120), (lx, 960)], fill=(0, 120, 60), width=2)
    for i in range(15):
        yy = 120 + int(i * (840 / 14))
        draw.ellipse([lx - 4, yy - 4, lx + 4, yy + 4], outline=(0, 180, 80))

    out = "assets/neon_nexus_bg_clean.png"
    img.save(out, "PNG")
    print(f"Wrote {out} ({W}x{H})")


if __name__ == "__main__":
    main()
