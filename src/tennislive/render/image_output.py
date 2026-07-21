"""Shared output policy for social cards."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image


def _rgb(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "#ffffff")
        background.alpha_composite(rgba)
        return background.convert("RGB")
    return image.convert("RGB")


def save_social_image(image: Image.Image, path: str | Path) -> Path:
    """Save a crisp, upload-friendly card and return its actual path.

    JPEG 4:4:4 at quality 92 keeps small Chinese text clean while cutting the
    photo-backed 1080x1440 cards by roughly 65-80% compared with PNG. Set
    TENNISLIVE_IMAGE_FORMAT=png for lossless output when a downstream target
    explicitly requires it.
    """
    path = Path(path)
    image_format = os.environ.get("TENNISLIVE_IMAGE_FORMAT", "jpg").lower()
    if image_format == "png":
        target = path.with_suffix(".png")
        image.save(target, "PNG", optimize=True, compress_level=9)
        return target

    quality_raw = os.environ.get("TENNISLIVE_JPEG_QUALITY", "92")
    try:
        quality = min(96, max(85, int(quality_raw)))
    except ValueError:
        quality = 92
    target = path.with_suffix(".jpg")
    _rgb(image).save(
        target,
        "JPEG",
        quality=quality,
        subsampling=0,
        optimize=True,
        progressive=True,
    )
    return target
