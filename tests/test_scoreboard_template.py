from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_match_reel  # noqa: E402
import versus_poster  # noqa: E402


def _cover() -> dict:
    return {
        "winner": "伊埃拉",
        "result": "6-1 4-6 6-2",
        "matchup": [
            {"name": "伊埃拉", "name_en": "A. EALA", "country": "PHI", "rank": 25},
            {"name": "帕克斯", "name_en": "A. PARKS", "country": "USA", "rank": 71},
        ],
        "scoreboard": {"court": "Centre Court", "duration_source": {"url": "fixture"}},
    }


def test_scoreboard_uses_real_duration_and_per_set_winners(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(versus_poster, "_fetch_match_duration", lambda source, where: "1:51")
    html = versus_poster._scoreboard_html(_cover())

    assert "1:51" in html
    assert 'class="score-flag"' in html
    assert "🇵🇭" not in html and "🇺🇸" not in html
    assert "伊埃拉" in html and "（25）" in html and "A. EALA" in html
    assert "帕克斯" in html and "（71）" in html and "A. PARKS" in html
    assert html.count('class="score-number setwin"') == 3
    assert html.count('class="score-number setlose"') == 3


def test_duration_parser_hides_seconds():
    assert versus_poster._duration_seconds("01:51:42") == 6702
    hours, minutes = divmod(6702 // 60, 60)
    assert f"{hours}:{minutes:02d}" == "1:51"


def test_scoreboard_requires_rank(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(versus_poster, "_fetch_match_duration", lambda source, where: "1:51")
    cover = _cover()
    del cover["matchup"][1]["rank"]
    with pytest.raises(SystemExit, match="缺 `rank`"):
        versus_poster._scoreboard_html(cover)


def test_match_video_remains_full_bleed():
    graph = build_match_reel.topbar_filtergraph(
        1.8, 10.0, Path("topbar.ass"), Path("subtitles.ass")
    )
    assert "crop=1080:1440" in graph
    assert "drawbox=x=0:y=0:w=iw:h=150" in graph
    assert "scale=-2:1290" not in graph
    assert "match_bg_src" not in graph
    assert "overlay=(W-w)/2" not in graph


def _tracks(value: str) -> list[str]:
    """按**浏览器的读法**把轨道列表拆开：只在括号外的空白处断。

    `grid-template-columns` 是一个**空格分隔**的轨道列表；`minmax(0,1fr)`
    里面那个逗号在括号内，不算分隔符。**顶层出现逗号是非法的**，整条声明
    会被丢掉——所以这儿同时把顶层逗号数出来。
    """
    tracks: list[str] = []
    depth = 0
    cur = ""
    for ch in value.strip():
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth == 0 and (ch.isspace() or ch == ","):
            if ch == ",":
                cur += "\0"          # 顶层逗号：留个记号让断言看得见
            if cur.strip():
                tracks.append(cur.strip())
            cur = ""
            continue
        cur += ch
    if cur.strip():
        tracks.append(cur.strip())
    return tracks


def test_比分板的盘分要真的排在名字右边(monkeypatch: pytest.MonkeyPatch):
    """轨道列表**用空格分隔**。第一版写的是 `",".join(...)`。

    渲出来是 `grid-template-columns:minmax(0,1fr),minmax(86px,1fr)`——顶层带
    逗号在 CSS 里是**非法值**，整条声明被丢掉，grid 退回单列：两位球员在上、
    四个盘分竖着排在下面。也就是说这块比分板**从来没有正确渲出来过**。

    ⚠️ **它为什么一直没被发现**：`_scoreboard_html` 的既有测试全在比 HTML
    字符串（有没有 `score-flag`、几个 `setwin`），而字符串里有没有逗号看不出
    对错；已发的 `eala-parks` 那张 `poster.jpg` 又是这套模板落地**之前**渲的，
    仓库里那份走的还是老的一行赛果。又一次「断言全绿不等于页面对」。

    所以判据不查文本，**按浏览器的读法把值解析一遍**：几条轨道就是几列。
    反向验证：把 `" ".join` 换回 `",".join`，`_tracks` 只解出 1 条，当场红。
    """
    monkeypatch.setattr(versus_poster, "_fetch_match_duration", lambda source, where: "1:51")
    cover = _cover()                      # result = "6-1 4-6 6-2"，三盘
    html = versus_poster._scoreboard_html(cover)

    match = re.search(r"grid-template-columns:([^\"';]+)", html)
    assert match, "比分板没有写 grid-template-columns"
    value = match.group(1)
    tracks = _tracks(value)

    assert "\0" not in "".join(tracks), (
        f"轨道列表顶层出现逗号，浏览器会把整条声明丢掉、grid 退回单列：{value!r}")
    assert len(tracks) == 1 + 3, (
        f"名字一列 + 每盘一列 = 4 条轨道，解出来却是 {len(tracks)} 条：{value!r}\n"
        "盘分会竖着堆在名字底下，而 HTML 字符串断言看不出这一点。")
    # 名字那一列要比盘分列宽：`A. SABALENKA` 比一个 `6` 长得多，等分会挤到换行。
    assert "1.55fr" in tracks[0], f"名字那列没留够宽度：{tracks[0]!r}"
