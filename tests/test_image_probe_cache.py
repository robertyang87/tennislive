"""Complete decode reuse cannot hide changed bytes, decoder policy or roots."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageFile, ImageOps, PngImagePlugin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import image_probe_cache as P


@pytest.fixture(autouse=True)
def clear_cache():
    P._SUCCESS.clear()
    yield
    P._SUCCESS.clear()


def _png(path: Path) -> bytes:
    Image.new('RGB', (41, 23), (50, 100, 150)).save(path)
    return path.read_bytes()


def test_identical_bytes_reuse_complete_decode_metadata(tmp_path, monkeypatch):
    path = tmp_path / 'valid.png'
    _png(path)
    calls = []
    original = Image.open
    def opened(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)
    monkeypatch.setattr(Image, 'open', opened)
    a = P.probe_image(path)
    b = P.probe_image(path)
    assert a == b == P.ImageProbe((41, 23), (41, 23), None)
    assert len(calls) == 1


def test_corrupted_same_size_bytes_with_restored_mtime_cannot_reuse_success(tmp_path, monkeypatch):
    path = tmp_path / 'changed.png'
    data = _png(path)
    assert P.probe_image(path).problem is None
    stat = path.stat()
    # Even a filesystem/caller reporting exactly the old identity cannot hide
    # changed compressed bytes: the lookup must still hash their contents.
    signature = P._signature(path)
    monkeypatch.setattr(P, '_signature', lambda _: signature)
    damaged = bytearray(data)
    damaged[damaged.index(b'IDAT') + 6] ^= 0xff
    path.write_bytes(damaged)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert path.stat().st_size == stat.st_size
    assert P.probe_image(path).problem
    path.write_bytes(data)
    assert P.probe_image(path).problem is None


def test_replacement_inode_and_missing_file_cannot_reuse_success(tmp_path, monkeypatch):
    path = tmp_path / 'replaced.png'
    _png(path)
    assert P.probe_image(path).problem is None
    replacement = tmp_path / 'replacement.png'
    _png(replacement)
    replacement.replace(path)
    calls = []
    original = Image.open
    def opened(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)
    monkeypatch.setattr(Image, 'open', opened)
    assert P.probe_image(path).problem is None
    assert len(calls) == 1
    path.unlink()
    assert 'FileNotFoundError' in P.probe_image(path).problem


def test_relative_cwd_and_changed_symlink_target_are_distinct(tmp_path, monkeypatch):
    good, bad = tmp_path / 'good', tmp_path / 'bad'
    good.mkdir(); bad.mkdir()
    _png(good / 'same.png')
    (bad / 'same.png').write_bytes(b'not an image')
    monkeypatch.chdir(good)
    assert P.probe_image(Path('same.png')).problem is None
    monkeypatch.chdir(bad)
    assert P.probe_image(Path('same.png')).problem
    link = tmp_path / 'linked.png'
    link.symlink_to(good / 'same.png')
    assert P.probe_image(link).problem is None
    link.unlink(); link.symlink_to(bad / 'same.png')
    assert P.probe_image(link).problem


@pytest.mark.parametrize('entry', ['open', 'png_load'])
def test_replaced_loader_does_not_inherit_old_success(tmp_path, monkeypatch, entry):
    path = tmp_path / 'loader.png'
    _png(path)
    assert P.probe_image(path).problem is None
    def broken(*args, **kwargs):
        raise OSError('new decoder failure')
    if entry == 'open':
        monkeypatch.setattr(Image, 'open', broken)
    else:
        monkeypatch.setattr(PngImagePlugin.PngImageFile, 'load', broken)
    assert 'new decoder failure' in P.probe_image(path).problem


def test_tightened_pixel_limit_cannot_reuse_success(tmp_path, monkeypatch):
    path = tmp_path / 'limit.png'
    _png(path)
    assert P.probe_image(path).problem is None
    monkeypatch.setattr(Image, 'MAX_IMAGE_PIXELS', 1)
    assert 'DecompressionBombError' in P.probe_image(path).problem


def test_truncation_policy_change_requires_full_decode_again(tmp_path, monkeypatch):
    path = tmp_path / 'cut.jpg'
    Image.new('RGB', (512, 512), 'red').save(path)
    path.write_bytes(path.read_bytes()[:-100])
    monkeypatch.setattr(ImageFile, 'LOAD_TRUNCATED_IMAGES', True)
    assert P.probe_image(path).problem is None
    monkeypatch.setattr(ImageFile, 'LOAD_TRUNCATED_IMAGES', False)
    assert P.probe_image(path).problem


@pytest.mark.parametrize('orientation', range(1, 9))
def test_oriented_dimensions_equal_actual_exif_transpose_before_jpeg_draft(tmp_path, orientation):
    path = tmp_path / 'orientation.jpg'
    exif = Image.Exif(); exif[274] = orientation
    Image.new('RGB', (41, 23), 'blue').save(path, exif=exif)
    with Image.open(path) as image:
        expected = ImageOps.exif_transpose(image).size
    info = P.probe_image(path)
    assert info.problem is None
    assert info.size == (41, 23)
    assert info.oriented_size == expected


def test_unreadable_exif_does_not_invent_oriented_dimensions(tmp_path, monkeypatch):
    path = tmp_path / 'exif.png'
    _png(path)
    def broken(*args):
        raise ValueError('bad exif')
    monkeypatch.setattr(Image.Image, 'getexif', broken)
    info = P.probe_image(path)
    assert info == P.ImageProbe((41, 23), None, None)


def test_success_cache_is_bounded_and_contains_no_pixels(tmp_path, monkeypatch):
    monkeypatch.setattr(P, '_CAPACITY', 2)
    for n in range(3):
        path = tmp_path / f'{n}.png'
        _png(path)
        assert P.probe_image(path).problem is None
    assert len(P._SUCCESS) == 2
    assert all(isinstance(value, P.ImageProbe) for value in P._SUCCESS.values())
