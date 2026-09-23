"""Процедурные «фото» нарушений для симуляции (организаторы не предоставляют реальных данных)."""
import io
import random
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_photo(kind: str, caption: str, rng: random.Random, size=(960, 640)) -> bytes:
    w, h = size
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    horizon = int(h * rng.uniform(0.38, 0.5))
    for y in range(horizon):  # небо
        d.line([(0, y), (w, y)], fill=_lerp((120, 170, 225), (205, 225, 240), y / horizon))
    # далёкие горы Каратау
    pts = [(0, horizon)] + [(x, horizon - rng.randint(15, 60)) for x in range(0, w + 80, 80)] + [(w, horizon)]
    d.polygon(pts, fill=(140, 150, 165))
    ground_top, ground_bottom = ((176, 160, 110), (140, 120, 80)) if kind != "ok" else ((120, 160, 80), (90, 130, 60))
    for y in range(horizon, h):
        d.line([(0, y), (w, y)], fill=_lerp(ground_top, ground_bottom, (y - horizon) / (h - horizon)))

    if kind == "dump":
        for _ in range(140):
            cx, cy = rng.gauss(w * 0.5, w * 0.16), rng.gauss(h * 0.72, h * 0.08)
            r = rng.randint(6, 26)
            color = rng.choice([(60, 60, 60), (230, 230, 230), (40, 90, 160), (180, 40, 40), (90, 70, 50), (20, 20, 20)])
            d.polygon([(cx + rng.randint(-r, r), cy + rng.randint(-r, r)) for _ in range(5)], fill=color)
    elif kind == "unused":
        for _ in range(900):
            x, y = rng.randint(0, w), rng.randint(horizon, h)
            ln = rng.randint(6, 22)
            d.line([(x, y), (x + rng.randint(-5, 5), y - ln)], fill=rng.choice([(150, 140, 60), (110, 120, 50), (190, 170, 90)]), width=2)
    elif kind == "seizure":
        base = int(h * 0.78)
        for x in range(40, w, 70):
            d.rectangle([x, base - 110, x + 8, base], fill=(90, 70, 50))
        for k in range(3):
            d.line([(40, base - 30 - k * 35), (w, base - 30 - k * 35)], fill=(70, 70, 70), width=2)
        d.rectangle([w * 0.62, base - 150, w * 0.9, base], fill=(170, 150, 130))
        d.polygon([(w * 0.6, base - 150), (w * 0.76, base - 210), (w * 0.92, base - 150)], fill=(120, 60, 50))

    font = _font(26)
    small = _font(18)
    d.rectangle([0, h - 70, w, h], fill=(0, 0, 0))
    d.text((20, h - 62), caption, font=font, fill=(255, 255, 255))
    d.text((20, h - 30), f"{datetime.now():%d.%m.%Y %H:%M} · симуляция", font=small, fill=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()
