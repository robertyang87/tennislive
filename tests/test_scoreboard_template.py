from __future__ import annotations

import json
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


#: 冻结的浏览器实测：`.score-cn` 的 `scrollWidth`（px），在**改动之前**的
#: 33px 字号下、用 Chromium 量的（1080×1440，device_scale_factor=1）。
#:
#: 它的作用是给 `_name_width_px` 那套 PIL 量法当靠山：我们在 Python 里算宽度、
#: 决定字号，而**真正排版的是浏览器**——两边只要有一处对不上（换字体、改
#: `.score-rank` 的 em、加了 letter-spacing），算出来的字号就会悄悄不够，
#: 名字压到框线上而没有任何东西报错。
_BROWSER_NAME_PX_AT_33 = {
    ("亚历山德罗娃", 19): 226,
    ("安尼西莫娃", 10): 200,
    ("巴图什科娃", 42): 200,
    ("费尔南德斯", 34): 200,
    ("麦克纳莉", 73): 173,
    ("奥索里奥", 55): 173,
    ("汤森德", 94): 147,
}


def test_量名字宽度要和浏览器对得上():
    """PIL 量出来的比 Chromium 稳定**小 1~2px**（字体一样，取整口径不同）。

    判据钉两头：不许偏大（偏大就等于高估了占地，字号被无谓压小），也不许小
    太多（小太多就会算出一个其实放不下的字号）。`SCORE_NAME_SLACK_PX` 就是
    按这个偏差留的余量。
    """
    worst = 0.0
    for (name, rank), browser in _BROWSER_NAME_PX_AT_33.items():
        got = versus_poster._name_width_px(name, rank, 33)
        gap = got - browser
        assert -versus_poster.SCORE_NAME_SLACK_PX <= gap <= 0.5, (
            f"{name}（{rank}）：PIL 量出 {got:.1f}px，浏览器是 {browser}px，"
            f"差 {gap:+.1f}px——超出 `SCORE_NAME_SLACK_PX` 能兜住的范围了")
        worst = min(worst, gap)
    assert abs(worst) <= versus_poster.SCORE_NAME_SLACK_PX, (
        f"最坏偏差 {worst:.1f}px，而余量只留了 "
        f"{versus_poster.SCORE_NAME_SLACK_PX}px")


def test_每盘一列算宽度不许把赛果整串拿去匹配():
    """`_SET_RE` 是锚死的（`^…$`），拿它 `findall` 整串恒为 0。

    第一版就是这么写的：每块板都按「1 盘」算名字那一列，于是它以为有 528px
    可用——**名字反而更大，而且一个字都不报错**。所以这条判据钉的是数出来的
    盘数，不是「有没有调用某个函数」。
    """
    assert versus_poster._set_count("6-3 4-6 6-4") == 3
    assert versus_poster._set_count("7-6(3) 4-6 6-4") == 3
    assert versus_poster._set_count("6-1 6-2") == 2
    assert versus_poster._set_count("") == 0
    # 盘越多、名字那一列越窄，这是这套算法的全部前提
    assert (versus_poster.score_name_avail_px(3)
            < versus_poster.score_name_avail_px(2))


def test_中文名字号按最长的名字算不许超出那一列():
    """账号所有者 2026-08-14：「球员的中文名字号再大一些，现在太小了」。

    字号因此不是写死的，而是 `min(上限, 这一列装得下的最大值)`——和封面钩子
    的 `hook_title_px` 同一个形状。**必须算**：`亚历山德罗娃（19）` 在原来的
    33px 下就要 226px，而那一列当时只有 198px，也就是加大之前它已经压在右边
    那道框线上了（36 张比分板里有 4 条名字如此）。
    """
    vp = versus_poster
    # ① 短名字拿满上限
    short = [{"name": "汤森德", "rank": 94}, {"name": "奥索里奥", "rank": 55}]
    assert vp.score_cn_px(short, 3) == vp.SCORE_CN_MAX_PX

    # ② 最长的那一对要缩下来，而且**两个人共用一个字号**
    longest = [{"name": "亚历山德罗娃", "rank": 19}, {"name": "斯维托丽娜", "rank": 9}]
    small = vp.score_cn_px(longest, 3)
    assert small < vp.SCORE_CN_MAX_PX, "六个字的名字还给满字号，那一列装不下"
    assert small == vp.score_cn_px(list(reversed(longest)), 3), "换个顺序算出两个数"

    # ③ 盘数少 → 那一列宽 → 同样的名字能给更大的字号（这一条同时钉住盘数真的
    #    被读进去了；`_set_count` 写错时它会退化成恒等）
    assert vp.score_cn_px(longest, 2) > small

    # ④ 算出来的字号必须**真的装得下**，逐条 spec 验
    checked = 0
    for path in sorted(ROOT.glob("specs/reels/*.json")):
        cover = json.loads(path.read_text("utf-8")).get("cover") or {}
        if str(cover.get("layout", "")).strip() != "solo" or not cover.get("scoreboard"):
            continue
        matchup = cover.get("matchup") or []
        sets = vp._set_count(cover.get("result"))
        px = vp.score_cn_px(matchup, sets)
        room = vp.score_name_avail_px(sets)
        for meta in matchup:
            width = vp._name_width_px(str(meta.get("name") or ""), meta.get("rank"), px)
            assert width + vp.SCORE_NAME_SLACK_PX <= room, (
                f"{path.name}：{meta.get('name')} 在 {px}px 下要 {width:.0f}px，"
                f"而 {sets} 盘那一列只有 {room:.0f}px")
        checked += 1
    assert checked >= 30, f"只校到 {checked} 块比分板，主语多半没了"


def _rendered_cn_px(monkeypatch: pytest.MonkeyPatch, cover: dict) -> int:
    monkeypatch.setattr(versus_poster, "_fetch_match_duration", lambda source, where: "1:51")
    _, css = versus_poster._solo_body({
        **cover, "eyebrow": "赛场之上", "layout": "solo", "hook": "赢了",
        "portrait": {"image": "assets/logo/brand/icon.png"},
    })
    hit = re.search(r"\.score-cn\{[^}]*?font-size:(\d+)px", css, re.S)
    assert hit, f"渲出来的 CSS 里没有 .score-cn 的字号：{css[:200]}"
    return int(hit.group(1))


def test_算出来的字号要真的写进CSS(monkeypatch: pytest.MonkeyPatch):
    """⚠️ **只验 `score_cn_px` 算得对，拦不住「它的结果没被用上」。**

    反向验证时把 CSS 里的 `__SCORE_CN_PX__` 换回写死的 `33px`，上面那几条
    **全绿**——函数照样算出 44 和 41，只是没有人读。这个仓库为同一个形状栽过
    好几次（`_push` 写错键名而退路刚好给出对的答案、`_cut_person` 从来没跑起来
    过），共同点都是「规矩写对了，实现是空的」。

    所以这条判据**改一个值验一次**：换一对更长的名字，渲出来的字号必须跟着变。
    """
    short = _rendered_cn_px(monkeypatch, {
        "winner": "汤森德", "result": "3-6 6-3 6-3",
        "scoreboard": {"court": "Stadium 3", "duration_source": {"url": "fixture"}},
        "matchup": [{"name": "汤森德", "name_en": "T. TOWNSEND", "country": "USA", "rank": 94},
                    {"name": "奥索里奥", "name_en": "C. OSORIO", "country": "COL", "rank": 55}],
    })
    long_ = _rendered_cn_px(monkeypatch, {
        "winner": "斯维托丽娜", "result": "3-6 6-0 6-3",
        "scoreboard": {"court": "Stadium 3", "duration_source": {"url": "fixture"}},
        "matchup": [{"name": "亚历山德罗娃", "name_en": "E. ALEXANDROVA", "country": "RUS", "rank": 19},
                    {"name": "斯维托丽娜", "name_en": "E. SVITOLINA", "country": "UKR", "rank": 9}],
    })
    assert short == versus_poster.SCORE_CN_MAX_PX, (
        f"短名字渲出来是 {short}px，而上限是 {versus_poster.SCORE_CN_MAX_PX}px"
        "——多半是 CSS 里那个字号被写死了，`score_cn_px` 算完没人读")
    assert long_ < short, (
        f"换成更长的名字，渲出来的字号还是 {long_}px——CSS 没有跟着 spec 变")


def test_中文名的字号上限只许往上调():
    """账号所有者说的是「再大一些」，那这个数就不该被谁顺手调回去。

    和 `test_成片的编码参数不许为了压体积往下调` 同一个形状：它拦的不是手滑，
    是下一次有人重新论证「小一点也看得清」。
    """
    assert versus_poster.SCORE_CN_MAX_PX >= 44, (
        f"中文名上限被调到了 {versus_poster.SCORE_CN_MAX_PX}px，"
        "而账号所有者 2026-08-14 要求的是「再大一些」（当时是 33px，定在 44px）")
    assert versus_poster.SCORE_NAME_COL_FR >= 2.3, (
        "名字那一列的宽度是字号涨得上去的前提，收窄它等于把字号又压回来")


def test_名字那一列加宽之后盘分那几列还够用():
    """名字列从 1.55fr 加宽到 2.3fr，代价落在盘分那几列上——要证明它们没被压瘪。

    盘分是 60px 的数字，抢七还要挂一个 `.45em` 的上标。三盘那一档是最窄的。
    """
    fr = versus_poster.SCORE_NAME_COL_FR
    for sets in (2, 3):
        column = 928 / (fr + sets)
        assert column >= 120, (
            f"{sets} 盘时每一格盘分只剩 {column:.0f}px，装 60px 的数字太挤")
        assert column >= 86, "已经掉到 minmax 的下限 86px，网格会开始挤名字那一列"


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
    # 宽度从常量推，不写死——2026-08-14 为了让中文名字号涨上去，这一列从
    # 1.55fr 加宽到了 2.3fr，写死的话每加宽一次都要来改这条断言。
    assert f"{versus_poster.SCORE_NAME_COL_FR}fr" in tracks[0], (
        f"名字那列没留够宽度：{tracks[0]!r}")
