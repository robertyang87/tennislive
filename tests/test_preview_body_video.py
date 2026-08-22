"""“开球之前”正文纯视频模式的时间轴判据。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("tools").resolve()))
sys.path.insert(0, str(Path("src").resolve()))

import build_match_reel as reel  # noqa: E402


def test_正文纯视频时顶栏从首帧开始且滤镜图没有零长封面(tmp_path):
    ass = reel.write_topbar_ass(
        ("2026 美网男单 · 开球之前", "世界第一退赛，争冠版图重写"),
        0.0, 50.0, tmp_path / "topbar.ass")
    text = ass.read_text(encoding="utf-8")
    assert "Dialogue: 0,0:00:00.00,0:00:50.00,HEAD" in text

    graph = reel.topbar_filtergraph(0.0, 50.0, ass, tmp_path / "subtitles.ass")
    assert "trim=start=0:end=0.000" not in graph
    assert "trim=start=0:end=50.000" in graph
    assert "trim=start=50.000" in graph
    assert "[match_canvas][outro]concat=n=2" in graph
    assert "[cover]" not in graph


def test_body_video_only只能是布尔值且不能吞掉封面旁白():
    with pytest.raises(reel.ReelError, match="只能是 true/false"):
        reel.validate_spec({"body_video_only": "true"})
    with pytest.raises(reel.ReelError, match="不能再写 cover.narration"):
        reel.validate_spec({
            "body_video_only": True,
            "cover": {"narration": "这句没有画面可落"},
        })
