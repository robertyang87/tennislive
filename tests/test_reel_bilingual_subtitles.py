"""赛场之上原声双语字幕的回归测试。"""

from pathlib import Path

from tennislive.video.explainer import write_subtitles
from tools.build_match_reel import explicit_quote_cues


def test_原声字幕可以显式结束而不是常驻到整段末尾():
    cues = explicit_quote_cues(
        (
            {"at": 0.29, "end": 1.89, "text": "First line\n第一句"},
            {"at": 1.89, "end": 3.89, "text": "Second line\n第二句"},
        ),
        span=23.87,
        offset=1.20,
    )
    assert cues[0][:2] == (1.49, 3.09)
    assert cues[1][:2] == (3.09, 5.09)
    assert cues[-1][1] < 1.20 + 23.87


def test_一行英文加多行中文仍按双语小字号排版(tmp_path: Path):
    path = write_subtitles(
        [(1.49, 5.09, "English reference line\n中文翻译第一行\n中文翻译第二行")],
        tmp_path / "subtitles.ass",
        height=1440,
        margin_v=1284,
    )
    body = path.read_text("utf-8")
    assert r"{\fs46}English reference line{\fs68}" in body
    assert r"\N中文翻译第一行\N中文翻译第二行" in body
    assert "MarginV" in body
