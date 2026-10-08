"""赛场之上原声双语字幕的回归测试。"""

from pathlib import Path

import pytest

from tennislive.video import explainer as E
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


def test_原声字幕的中文行不带标点上屏英文行原样():
    """「屏幕上不写标点（只留？！）」是全站规矩，可 bilingual quote 一直把
    spec 文本原样烧上屏——zheng-burel 的中文行带着「回球越来越短。」的句号，
    和同一条片子里旁白字幕（从来不带）摆在一起是两种样子。英文行不动：
    那是他真说的话，标点是语法的一部分（撇号逗号都得在）。"""
    cues = explicit_quote_cues(
        (
            {"at": 0.0, "end": 2.0,
             "text": "Just taking the ball shorter and shorter there,\n回球越来越短。"},
            {"at": 2.0, "end": 4.0,
             "text": "I don't know, honestly.\n说真的，我也不知道。"},
            {"at": 4.0, "end": 6.0, "text": "Can you believe it?\n你敢信吗？"},
        ),
        span=6.0,
        offset=0.0,
    )
    shown = [text for _, _, text in cues]
    assert shown[0] == "Just taking the ball shorter and shorter there,\n回球越来越短"
    # 中文行句内标点换成空格（和旁白字幕同一份规矩），英文行一个字符不动
    assert shown[1] == "I don't know, honestly.\n说真的 我也不知道"
    # ？！是仅有的两个留在屏幕上的标点——「这是一问」换页表达不了
    assert shown[2] == "Can you believe it?\n你敢信吗？"
    # 按字数摊的那条路（不写 at）走的是同一份显示规则
    weighted = explicit_quote_cues(("Thank you so much.\n谢谢大家。",), 3.0, 0.0)
    assert weighted[0][2] == "Thank you so much.\n谢谢大家"


def test_一行英文加多行中文仍按双语小字号排版(tmp_path: Path):
    path = write_subtitles(
        [(1.49, 5.09, "English reference line\n中文翻译第一行\n中文翻译第二行")],
        tmp_path / "subtitles.ass",
        height=1440,
        margin_v=1284,
    )
    body = path.read_text("utf-8")
    # 英文行换成 Inter SemiBold、细描边（2026-09-26 账号所有者选的），行尾把样式还给中文
    assert E.ass_en_row("English reference line", outline=3) in body
    assert r"\N中文翻译第一行\N中文翻译第二行" in body
    assert "MarginV" in body


@pytest.mark.parametrize("score", ["40-15", "40–15", "40—15", "40−15"])
def test_broadcast_score_keeps_english_literal_and_chinese_display(score):
    """英文比分不能被整条 readable() 转成中文，实际原声字幕必须可核验。"""
    english = f"Oh, and Kalinskaya, from {score} up…"
    text = english + f"\n噢，卡林斯卡娅刚才还{score}领先……"
    explicit = explicit_quote_cues(
        ({"at": 6.44, "end": 10.18, "text": text},),
        span=10.30,
        offset=152.28,
    )
    assert explicit[0][:2] == pytest.approx((158.72, 162.46))
    assert explicit[0][2] == english + "\n噢 卡林斯卡娅刚才还40比15领先"
    weighted = explicit_quote_cues((text,), span=3.74, offset=0.0)
    assert weighted[0][2] == explicit[0][2]
