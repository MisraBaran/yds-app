#!/usr/bin/env python3
"""Uygulama ikonlarini programatik olarak uretir (internet gerekmez).
Sade bir monogram: koyu zemin + altin "Y" harfi, uygulamanin renk
temasiyla (bkz css/styles.css --bg / --accent) tutarli.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ICONS_DIR = ROOT / "icons"
ICONS_DIR.mkdir(exist_ok=True)

BG = (22, 21, 26, 255)      # --bg
ACCENT = (214, 162, 78, 255)  # --accent


def draw_icon(size: int, maskable: bool = False) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(img)

    if maskable:
        # maskable ikonlarda guvenli alan disina tasma olmamasi icin
        # ikon biraz kucultulup ortalanir.
        pad = size * 0.18
    else:
        pad = size * 0.08
        radius = size * 0.22
        draw.rounded_rectangle([0, 0, size, size], radius=radius, fill=BG)

    # basit "Y" monogrami
    font_size = int(size * 0.52)
    font = None
    for candidate in ["arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"]:
        try:
            font = ImageFont.truetype(candidate, font_size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    text = "Y"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=ACCENT)

    # alt cizgi vurgusu
    line_y = size * 0.74
    draw.rectangle([size * 0.30, line_y, size * 0.70, line_y + size * 0.02], fill=ACCENT)

    return img


sizes = [
    ("icon-180.png", 180, False),
    ("icon-192.png", 192, False),
    ("icon-512.png", 512, False),
    ("icon-192-maskable.png", 192, True),
    ("icon-512-maskable.png", 512, True),
]

for name, size, maskable in sizes:
    img = draw_icon(size, maskable)
    img.save(ICONS_DIR / name)
    print(f"-> icons/{name}")
