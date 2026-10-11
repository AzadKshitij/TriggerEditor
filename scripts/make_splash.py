"""Generate the Trigger Designer splash screen.

Produces ``src/trigger_designer/resources/splash.png`` (960x540, RGBA) in the
same visual language as the old ``classic.png``: a dark rounded panel with soft
diagonal bands, the app logo, a magenta-to-cyan gradient wordmark and a torn
paper tape banner ("ALPHA!!!").

The QSplashScreen overlays the copyright and version text along the bottom
centre, so the lower band is left comparatively clean.

Run from the project root::

    uv run --project . python scripts/make_splash.py
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "src" / "trigger_designer" / "resources"

# Rendered at 2x and downsampled once at the end for smooth edges.
SCALE = 2
W, H = 960 * SCALE, 540 * SCALE
RADIUS = 34 * SCALE

FONT_BLACK = r"C:\Windows\Fonts\ariblk.ttf"
FONT_MARKER = r"C:\Windows\Fonts\segoeprb.ttf"

BASE = np.array([10, 1, 32], dtype=np.float32)
BAND_PURPLE = np.array([27, 6, 55], dtype=np.float32)
BAND_BLUE = np.array([8, 26, 56], dtype=np.float32)


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255
    )
    return mask


def diagonal_background() -> Image.Image:
    """Dark navy panel with soft diagonal purple/blue bands and a glow."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

    # Bands run along a ~28 degree diagonal.
    angle = math.radians(28)
    t = xx * math.cos(angle) + yy * math.sin(angle)
    period = 250.0 * SCALE
    f1 = 0.5 + 0.5 * np.sin(2 * math.pi * t / period)
    f2 = 0.5 + 0.5 * np.sin(2 * math.pi * t / period + 1.3)

    rgb = np.zeros((H, W, 3), dtype=np.float32) + BASE
    rgb += (BAND_PURPLE - BASE)[None, None, :] * f1[..., None] * 0.95
    rgb += (BAND_BLUE - BASE)[None, None, :] * f2[..., None] * 0.85

    # A broad magenta glow behind the logo and a cyan one behind the wordmark.
    for (cx, cy), colour, strength, radius in (
        ((0.16 * W, 0.42 * H), np.array([150, 39, 190], np.float32), 0.55, 0.42 * W),
        ((0.80 * W, 0.38 * H), np.array([30, 120, 190], np.float32), 0.40, 0.44 * W),
    ):
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        glow = np.clip(1.0 - dist / radius, 0.0, 1.0) ** 2
        rgb += colour[None, None, :] * glow[..., None] * strength

    # Subtle vignette so the corners sink into the panel.
    edge = (np.minimum.reduce([xx, W - 1 - xx, yy, H - 1 - yy]) / (0.28 * W)).clip(0, 1)
    rgb *= (0.72 + 0.28 * edge)[..., None]

    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    im = Image.fromarray(rgb, "RGB").convert("RGBA")
    im = im.filter(ImageFilter.GaussianBlur(1.2 * SCALE))
    im.putalpha(rounded_mask((W, H), RADIUS))
    return im


def gradient_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    stops: list[str],
    outline: str = "#d6e6ff",
    outline_w: int = 3,
) -> Image.Image:
    """Render ``text`` filled with a horizontal multi-stop gradient + outline.

    Returns a tightly cropped RGBA layer including the outline and drop shadow.
    """
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    bbox = probe.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    mask = Image.new("L", (w + 8, h + 8), 0)
    ImageDraw.Draw(mask).text((4 - bbox[0], 4 - bbox[1]), text, font=font, fill=255)
    w, h = mask.size

    cols = np.array([hex_rgb(c) for c in stops], dtype=np.float32)
    xs = np.linspace(0.0, 1.0, w)
    src = np.linspace(0.0, 1.0, len(cols))
    grad = np.zeros((h, w, 3), dtype=np.uint8)
    for c in range(3):
        grad[:, :, c] = np.interp(xs, src, cols[:, c]).astype(np.uint8)[None, :]
    grad_img = Image.fromarray(grad, "RGB").convert("RGBA")

    ow = outline_w * SCALE
    out_mask = mask.filter(ImageFilter.MaxFilter(2 * ow + 1))
    pad = ow + 26 * SCALE
    layer = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))

    shadow = out_mask.filter(ImageFilter.GaussianBlur(9 * SCALE))
    layer.paste(
        Image.new("RGBA", out_mask.size, (5, 0, 22, 205)),
        (pad + 3 * SCALE, pad + 9 * SCALE),
        shadow,
    )
    layer.paste(
        Image.new("RGBA", out_mask.size, hex_rgb(outline) + (255,)),
        (pad, pad),
        out_mask,
    )
    grad_img.putalpha(mask)
    layer.paste(grad_img, (pad, pad), mask)

    return layer.crop(layer.getbbox())  # type: ignore[arg-type]


def make_tape(label: str) -> Image.Image:
    """A torn paper strip with a red marker word, rotated with a matching shadow."""
    tw, th = 430 * SCALE, 120 * SCALE

    rng = random.Random(11)
    pts: list[tuple[int, int]] = []

    def jitter(amount: int) -> int:
        return rng.randint(0, amount)

    for x in range(0, tw + 1, max(1, tw // 22)):
        pts.append((x, jitter(5 * SCALE)))
    for y in range(0, th + 1, max(1, th // 10)):
        pts.append((tw - jitter(12 * SCALE), y))
    for x in range(tw, -1, -max(1, tw // 22)):
        pts.append((x, th - jitter(5 * SCALE)))
    for y in range(th, -1, -max(1, th // 10)):
        pts.append((jitter(12 * SCALE), y))

    shape = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(shape).polygon(pts, fill=255)

    # Paper grain + smudged lower edge + soft top highlight.
    noise = np.random.default_rng(3).normal(0, 9, (th, tw, 1)).astype(np.float32)
    paper_arr = np.full((th, tw, 3), hex_rgb("#eceaf3"), dtype=np.float32) + noise
    paper = Image.fromarray(np.clip(paper_arr, 0, 255).astype(np.uint8), "RGB")

    overlay = Image.new("RGB", (tw, th), hex_rgb("#eceaf3"))
    od = ImageDraw.Draw(overlay)
    od.rectangle([0, th * 3 // 4, tw, th], fill=(176, 174, 190))
    od.rectangle([0, 0, tw, th // 3], fill=(255, 255, 255))
    paper = Image.blend(paper, overlay, 0.45)

    tape = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    tape.paste(paper.convert("RGBA"), (0, 0), shape)

    marker_font = ImageFont.truetype(FONT_MARKER, 76 * SCALE)
    md = ImageDraw.Draw(tape)
    box = md.textbbox((0, 0), label, font=marker_font)
    md.text(
        ((tw - (box[2] - box[0])) / 2 - box[0], (th - (box[3] - box[1])) / 2 - box[1]),
        label,
        font=marker_font,
        fill=hex_rgb("#d21f2c") + (255,),
    )

    # Rotate paper and shadow together so they stay aligned.
    rotated = tape.rotate(-6.5, resample=Image.BICUBIC, expand=True)
    margin = 34 * SCALE
    canvas = Image.new(
        "RGBA", (rotated.width + 2 * margin, rotated.height + 2 * margin), (0, 0, 0, 0)
    )
    shadow = rotated.split()[3].filter(ImageFilter.GaussianBlur(8 * SCALE))
    canvas.paste(
        Image.new("RGBA", rotated.size, (0, 0, 0, 130)),
        (margin + 4 * SCALE, margin + 11 * SCALE),
        shadow,
    )
    canvas.alpha_composite(rotated, (margin, margin))
    return canvas


def main() -> None:
    bg = diagonal_background()

    # Logo (navy + magenta triangle), ~230px tall at 1x, with a magenta halo.
    logo = Image.open(RESOURCES / "TriEditorLogo.png").convert("RGBA")
    logo_h = 232 * SCALE
    logo = logo.resize(
        (round(logo.width * logo_h / logo.height), logo_h), Image.LANCZOS
    )
    logo_x, logo_y = 70 * SCALE, (H - logo_h) // 2 - 16 * SCALE

    halo_mask = Image.new("L", (W, H), 0)
    halo_mask.paste(logo.split()[3], (logo_x, logo_y))
    halo_mask = halo_mask.filter(ImageFilter.GaussianBlur(24 * SCALE))
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    halo.paste(
        Image.new("RGBA", (W, H), hex_rgb("#ff35d8") + (120,)), (0, 0), halo_mask
    )
    bg.alpha_composite(halo)
    bg.alpha_composite(logo, (logo_x, logo_y))

    # Wordmark: "Trigger Designer" in a magenta -> violet -> cyan gradient.
    word_font = ImageFont.truetype(FONT_BLACK, 96 * SCALE)
    word = gradient_text(
        "Trigger Designer",
        word_font,
        ["#ff2bd6", "#a855f7", "#38e8f0"],
        outline="#d9ecff",
        outline_w=3,
    )
    target_w = 578 * SCALE
    word = word.resize(
        (target_w, round(word.height * target_w / word.width)), Image.LANCZOS
    )
    bg.alpha_composite(word, (248 * SCALE, 134 * SCALE))

    # Torn tape, overlapping the wordmark's lower right like the reference.
    tape = make_tape("ALPHA!!!")
    centre = (548 * SCALE, 338 * SCALE)
    pos = (centre[0] - tape.width // 2, centre[1] - tape.height // 2)
    bg.alpha_composite(tape, pos)

    final = bg.resize((W // SCALE, H // SCALE), Image.LANCZOS)
    out = RESOURCES / "splash.png"
    final.save(out)
    print("wrote", out, final.size, final.mode)


if __name__ == "__main__":
    main()
