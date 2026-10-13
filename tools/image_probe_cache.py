"""Bounded, process-local image decode facts, never a publication approval.

Every lookup hashes the current file bytes. Only successful complete decodes are
reused, under the same Pillow loader and policy; pixels are never retained.
"""
from __future__ import annotations

import hashlib
import warnings
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImageProbe:
    size: tuple[int, int] | None
    oriented_size: tuple[int, int] | None
    problem: str | None


_CAPACITY = 1024
_SUCCESS: OrderedDict[tuple, ImageProbe] = OrderedDict()


def _signature(path: Path) -> tuple:
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _policy() -> tuple:
    from PIL import Image, ImageFile, PngImagePlugin

    # Initialize lazy plugins before taking their identities. Include format
    # implementations as well as common entry points: tests and callers can
    # replace a JPEG/PNG loader without replacing Image.open itself.
    Image.init()
    formats = tuple((name, factory, accept,
                     getattr(factory, 'load', None), getattr(factory, 'draft', None),
                     getattr(factory, 'getexif', None))
                    for name, (factory, accept) in sorted(Image.OPEN.items()))
    return (Image.open, Image.Image.load, ImageFile.ImageFile.load,
            Image.Image.getexif, Image._getdecoder,
            Image.MAX_IMAGE_PIXELS, ImageFile.LOAD_TRUNCATED_IMAGES,
            ImageFile.MAXBLOCK, tuple(warnings.filters),
            tuple(sorted(Image.DECODERS.items())),
            PngImagePlugin.MAX_TEXT_CHUNK, PngImagePlugin.MAX_TEXT_MEMORY, formats)


def probe_image(path: Path) -> ImageProbe:
    """Decode all compressed data and report the dimensions before JPEG draft.

    The decoder remains the existing draft JPEG / full other-format decoder.
    Metadata-only changes and content changes both invalidate the cache. Failed
    decodes are retried; missing files can never inherit an earlier success.
    """
    from PIL import Image

    size = oriented = None
    try:
        path = Path(path).resolve()
        before = _signature(path)
        digest = hashlib.sha256()
        with path.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(chunk)
        policy = _policy()
        key = (str(path), before, digest.digest(), policy)
        stable = _signature(path) == before
        if stable and key in _SUCCESS:
            _SUCCESS.move_to_end(key)
            return _SUCCESS[key]
        with Image.open(path) as image:
            size = image.size
            if image.format == 'JPEG':
                image.draft('RGB', (max(1, size[0] // 8), max(1, size[1] // 8)))
            image.load()
            try:
                orientation = image.getexif().get(274, 1)
                oriented = size[::-1] if orientation in (5, 6, 7, 8) else size
            except Exception:
                # The existing dimensions gate declines to judge unreadable
                # EXIF; that is independent of the complete decode gate.
                oriented = None
        result = ImageProbe(size, oriented, None)
        if stable and _signature(path) == before and _policy() == policy:
            _SUCCESS[key] = result
            _SUCCESS.move_to_end(key)
            while len(_SUCCESS) > _CAPACITY:
                _SUCCESS.popitem(last=False)
        return result
    except Exception as exc:
        return ImageProbe(size, oriented, f'{type(exc).__name__}: {exc}')
