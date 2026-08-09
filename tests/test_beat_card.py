"""字卡（数据卡/转折卡）：抖音官方创作建议 2026-08-09 点名的两种视觉呈现。

卡是贴在比赛画面上的**贴纸**（走 inset 机制），所以判据的重心是：
底必须透明（方形底就是「深色球衣压深色背景留一块方底」的字卡版）、
卡身必须真的画出来了（不是一张全透明的空图）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from render_beat_card import build_html, render  # noqa: E402


def test_两种卡二选一():
    with pytest.raises(SystemExit, match="二选一"):
        build_html(value="0/3", title="第一盘")
    with pytest.raises(SystemExit, match="二选一"):
        build_html()
    assert "0/3" in build_html(value="0/3", label="破发点")
    assert "决胜时刻" in build_html(title="第一盘 决胜时刻")


def test_文本要转义():
    html = build_html(title="a<b>&c")
    assert "<b>" not in html.split('id="card"')[1]
    assert "a&lt;b&gt;&amp;c" in html


def test_渲出来的卡底透明卡身实在(tmp_path):
    """真渲一张——「写了」不等于「跑过」。四角 alpha 必须是 0（贴纸），
    中心必须不透明（卡身真的在）。只验其一的话，一张全透明的空图也能过。"""
    from PIL import Image  # noqa: PLC0415

    out = render(build_html(value="0/3", label="第一盘 破发点"),
                 tmp_path / "card.png")
    with Image.open(out) as im:
        assert im.mode == "RGBA"
        w, h = im.size
        assert w > 300 and h > 200, f"卡小得不像话（{w}×{h}）"
        px = im.load()
        for x, y in ((1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2)):
            assert px[x, y][3] < 16, f"角 ({x},{y}) alpha={px[x, y][3]}，底不透明"
        centre = px[w // 2, h // 2]
        assert centre[3] > 200, "卡身是透明的——渲了个寂寞"


def test_cli入口跑得通(tmp_path):
    done = subprocess.run(
        [sys.executable, str(Path("tools/render_beat_card.py").resolve()),
         "--title", "第二盘 抢七", "--out", str(tmp_path / "t.png")],
        check=True, capture_output=True, text=True)
    assert "已渲" in done.stdout and (tmp_path / "t.png").is_file()
