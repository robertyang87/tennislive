"""tools/crop_zoom_limit.py —— 纯数学，不联网。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _mod():
    sys.path.insert(0, str(Path("tools").resolve()))
    import crop_zoom_limit  # noqa: PLC0415

    return crop_zoom_limit


def test_和gea_shapovalov那次手算的数对得上():
    m = _mod()
    # CLAUDE.md「转播主机位的宽景，裁不出更紧的景别」：near=0.83 far=0.10
    # safe_limit=0.86 top_margin=0.03 → 手算「缩放上限只有 1.14」
    zmax = m.zoom_limit(0.83, 0.10, safe_limit=0.86, top_margin=0.03)
    assert zmax == pytest.approx(1.1370, abs=1e-3)


def test_默认safe_limit和top_margin就是那次实测值():
    m = _mod()
    assert m.zoom_limit(0.83, 0.10) == pytest.approx(1.1370, abs=1e-3)


def test_近端和远端坐标填反了要报错():
    m = _mod()
    with pytest.raises(ValueError, match="填反"):
        m.zoom_limit(0.10, 0.83)


def test_近端和远端相等也要报错():
    m = _mod()
    with pytest.raises(ValueError):
        m.zoom_limit(0.5, 0.5)


def test_safe_limit小于等于top_margin要报错():
    m = _mod()
    with pytest.raises(ValueError):
        m.zoom_limit(0.83, 0.10, safe_limit=0.03, top_margin=0.86)


def test_两个人占满整幅画面时上限小于1():
    m = _mod()
    # 近端几乎贴底、远端几乎贴顶——比 gea-shapovalov 那次更极端
    zmax = m.zoom_limit(0.98, 0.02, safe_limit=0.86, top_margin=0.03)
    assert zmax < 1.0


def test_命令行打印安全上限(capsys):
    m = _mod()
    old_argv = sys.argv
    try:
        sys.argv = ["crop_zoom_limit.py", "--near-bottom", "0.83", "--far-top", "0.10"]
        code = m.main()
    finally:
        sys.argv = old_argv
    assert code == 0
    out = capsys.readouterr().out
    assert "1.14" in out


def test_命令行遇到非法输入返回1而不是抛栈(capsys):
    m = _mod()
    old_argv = sys.argv
    try:
        sys.argv = ["crop_zoom_limit.py", "--near-bottom", "0.10", "--far-top", "0.83"]
        code = m.main()
    finally:
        sys.argv = old_argv
    assert code == 1
    assert "算不出来" in capsys.readouterr().out
