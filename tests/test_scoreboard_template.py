from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image


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
    # ⚠️ **盒高从常量推，别写死。** 原来这儿是 `h=150`，而 `TOPBAR_H`
    # 2026-08-15 收到了 126（账号所有者要顶栏矮一点）——写死的话，这条本来只
    # 管「比赛画面有没有铺满」的判据会因为一次纯粹的版式调整而红，读的人还得
    # 先弄明白 150 是打哪儿来的。顶栏该多高归
    # `test_顶栏盒子要装得下两行字并且留出余量` 管，那条真渲一帧量墨迹。
    assert f"drawbox=x=0:y=0:w=iw:h={build_match_reel.TOPBAR_H}" in graph
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
    #
    # ⚠️ **这一档 2026-08-29 从三盘挪到了五盘。** 新版式（两行高亮长条）给名字
    #    腾出的宽度比旧表格多得多——三盘 448px vs 285px——`亚历山德罗娃（19）`
    #    在 52px 下只要 356px，三盘**已经装得下了**。拿三盘去验「会不会缩」，
    #    验的是一个不再存在的情形；五盘（大满贯男单）那一档才是今天真的会咬人
    #    的地方（只剩 264px）。
    longest = [{"name": "亚历山德罗娃", "rank": 19}, {"name": "斯维托丽娜", "rank": 9}]
    small = vp.score_cn_px(longest, 5)
    assert small < vp.SCORE_CN_MAX_PX, "六个字的名字五盘还给满字号，那一格装不下"
    assert small == vp.score_cn_px(list(reversed(longest)), 5), "换个顺序算出两个数"

    # ③ 盘数少 → 名字那一格宽 → 同样的名字能给更大的字号（这一条同时钉住盘数
    #    真的被读进去了；`_set_count` 写错时它会退化成恒等）
    assert vp.score_cn_px(longest, 4) > small

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
    # ⚠️ **两条 cover 走的是两条不同的路**：短名字三盘吃满上限，长名字五盘被
    #    宽度压下来。而两条都要和 `score_cn_px` 独立算出来的数逐个对上——
    #    只断言「长的比短的小」的话，把 CSS 里的字号写死成任意两个数也能过。
    short_pair = [{"name": "汤森德", "name_en": "T. TOWNSEND", "country": "USA", "rank": 94},
                  {"name": "奥索里奥", "name_en": "C. OSORIO", "country": "COL", "rank": 55}]
    long_pair = [{"name": "亚历山德罗娃", "name_en": "E. ALEXANDROVA", "country": "RUS", "rank": 19},
                 {"name": "斯维托丽娜", "name_en": "E. SVITOLINA", "country": "UKR", "rank": 9}]
    short = _rendered_cn_px(monkeypatch, {
        "winner": "汤森德", "result": "3-6 6-3 6-3",
        "scoreboard": {"court": "Stadium 3", "duration_source": {"url": "fixture"}},
        "matchup": short_pair,
    })
    long_ = _rendered_cn_px(monkeypatch, {
        "winner": "斯维托丽娜", "result": "6-4 3-6 6-7(5) 7-6(3) 6-2",
        "scoreboard": {"court": "Stadium 3", "duration_source": {"url": "fixture"}},
        "matchup": long_pair,
    })
    assert short == versus_poster.SCORE_CN_MAX_PX, (
        f"短名字渲出来是 {short}px，而上限是 {versus_poster.SCORE_CN_MAX_PX}px"
        "——多半是 CSS 里那个字号被写死了，`score_cn_px` 算完没人读")
    assert long_ == versus_poster.score_cn_px(long_pair, 5) < short, (
        f"六个字的名字五盘渲出来是 {long_}px，而 `score_cn_px` 算的是 "
        f"{versus_poster.score_cn_px(long_pair, 5)}px（上限 {short}px）"
        "——CSS 没有跟着 spec 变")


def test_中文名的字号上限只许往上调():
    """账号所有者说的是「再大一些」，那这个数就不该被谁顺手调回去。

    和 `test_成片的编码参数不许为了压体积往下调` 同一个形状：它拦的不是手滑，
    是下一次有人重新论证「小一点也看得清」。
    """
    assert versus_poster.SCORE_CN_MAX_PX >= 52, (
        f"中文名上限被调到了 {versus_poster.SCORE_CN_MAX_PX}px，"
        "而账号所有者 2026-08-14 要求「再大一些」（33px→44px），"
        "2026-08-29 换成美网那套两行版式之后又提到 52px")
    # ⚠️ **换了主语**：旧版名字占几份（`SCORE_NAME_COL_FR ≥ 2.3`）是表格时代的
    #    说法，新版式没有网格列了。守的东西一个字没变——**名字那一格的宽度是
    #    字号涨得上去的前提，收窄它等于把字号又压回来**——只是现在要拿真的像素
    #    来量。285px 是旧表格三盘时给名字的宽度，新版式给 448px，不许退回去。
    assert versus_poster.score_name_avail_px(3) >= 285, (
        f"三盘时名字那一格只剩 {versus_poster.score_name_avail_px(3):.0f}px，"
        "比旧版那个表格（285px）还窄——字号会被压回去")


def test_英文名要退成注脚但还读得出(monkeypatch: pytest.MonkeyPatch):
    """账号所有者 2026-08-14：「英文名可以字号小一些」（中文名涨到 44px 之后
    22px 的英文行跟着显得抢戏）。

    两头都要钉：**小到位**（不然这条反馈等于没做），**又不能小到读不出**——
    渲了 22/20/19/18/17 五档摆一起看，17px 配着 1.5px 的字距开始发虚。

    还要盯**它真的写进了 CSS**：常量改对而占位符没换，渲出来还是老样子，
    而这种错这个仓库栽过好几次（同一轮里就有一次，见
    `test_算出来的字号要真的写进CSS`）。
    """
    vp = versus_poster
    assert vp.SCORE_EN_PX <= 20, (
        f"英文名还是 {vp.SCORE_EN_PX}px，账号所有者要的是比原来的 22px 小一些")
    assert vp.SCORE_EN_PX >= 16, (
        f"英文名 {vp.SCORE_EN_PX}px 太小了：1080 宽的画布放到手机上，"
        "17px 配 1.5px 字距就已经开始发虚")
    assert vp.SCORE_EN_PX < vp.SCORE_CN_MAX_PX, "英文名是注脚，不许和中文名一样大"

    monkeypatch.setattr(vp, "_fetch_match_duration", lambda source, where: "1:51")
    _, css = vp._solo_body({
        **_cover(), "eyebrow": "赛场之上", "layout": "solo", "hook": "赢了",
        "portrait": {"image": "assets/logo/brand/icon.png"},
    })
    hit = re.search(r"\.score-en\{[^}]*?font-size:(\d+)px", css, re.S)
    assert hit and int(hit.group(1)) == vp.SCORE_EN_PX, (
        f"CSS 里英文名的字号是 {hit.group(1) if hit else '缺'}，"
        f"而常量是 {vp.SCORE_EN_PX}——占位符没换上")


def test_盘分那几列和名字那一格都够用():
    """版式的两头都要留得住：盘分列装得下那个字号的数字，名字那一格不许被挤没。

    ⚠️ **换了主语**（2026-08-29）：旧版名字那一列是 `2.3fr`，这条判据算的是
    `928/(fr+盘数)`。新版式没有网格了，盘分列是**写死的像素**、名字吃剩下的，
    所以同一件事要拿像素来量。它守的东西没变——加宽一头就是压窄另一头，
    这条钉的是两头都还够用。

    五盘（大满贯男单）是最紧的一档：名字只剩 264px，六个字的名字会缩到 38px
    上下——还读得出，但不能再窄了。
    """
    vp = versus_poster
    assert vp.SCORE_SET_COL_PX >= vp.SCORE_NUM_PX + 20, (
        f"盘分列只剩 {vp.SCORE_SET_COL_PX}px，装 {vp.SCORE_NUM_PX}px 的数字"
        "加一个抢七上标太挤")
    # ⚠️ 名字那一头的判据**不拍一个像素数**（拍出来的数只会在下次微调版式时
    #    变成挡路的），而是问那个真正的后果：**库里最长的名字会不会被压到下限
    #    以下**。压到下限 `score_cn_px` 会打印告警并硬渲，那一行就顶到盘分上了。
    longest = [{"name": "亚历山德罗娃", "rank": 19}, {"name": "斯维托丽娜", "rank": 9}]
    for sets in (2, 3, 5):
        px = vp.score_cn_px(longest, sets)
        assert px > vp.SCORE_CN_MIN_PX, (
            f"{sets} 盘时最长的名字只能给到 {px}px，已经掉到下限 "
            f"{vp.SCORE_CN_MIN_PX}px——名字会压到盘分上")
    assert vp.score_name_avail_px(5) < vp.score_name_avail_px(3) < vp.score_name_avail_px(2), (
        "盘越多名字那一格越窄，这是 `score_cn_px` 那套算法的全部前提")


def _board_css(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(versus_poster, "_fetch_match_duration", lambda source, where: "1:51")
    _, css = versus_poster._solo_body({
        **_cover(), "eyebrow": "赛场之上", "layout": "solo", "hook": "赢了",
        "portrait": {"image": "assets/logo/brand/icon.png"},
    })
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _rule(css: str, selector: str) -> str:
    hit = re.search(re.escape(selector) + r"\{([^}]*)\}", css)
    assert hit, f"渲出来的 CSS 里没有 `{selector}`：多半是选择器改名了"
    return hit.group(1)


def test_比分板两行的盘分要上下对齐(monkeypatch: pytest.MonkeyPatch):
    """两行是**分开渲**的，盘分能不能上下对齐全靠三样东西同时成立。

    ⚠️ **换了主语**（2026-08-29）：旧版比分板是一个 `grid`，两位球员在同一个
    `.scoreboard-players` 格子里、盘分在右边几条轨道上，所以那条判据解的是
    `grid-template-columns`（它当年抓到过一个真 bug：轨道列表用逗号分隔，
    整条声明被浏览器丢掉、grid 退回单列）。账号所有者 2026-08-29 换成美网那套
    **两行**版式之后，网格没有了——`grid-template-columns` 这个主语不存在，
    留着那条判据就是一条常年红。

    它守的东西一个字没变：**盘分要排在名字右边，而且两行的列要对得齐。**
    只是保证它的机制换了，所以判据也跟着换：

    1. **HTML**：每一行都是「名字在前、盘分在后」，两行的格子数一样多
    2. **列宽写死**：`.score-number` 的 `flex` 必须是固定像素基准。换成 `flex:1`
       的话，盘分那一块会缩到内容宽度，而「6」和带抢七上标的「6(3)」不一样宽，
       两行当场错开
    3. **名字那一格可以缩**：`.score-names` 要有 `min-width:0`。少了它，一个长
       名字撑不下时会把盘分整块往右推，而**只有那一行被推**
    4. **抢七小分不占位**：`.score-number sup` 要绝对定位。留在流里的话，
       带小分的那一格宽出三十来像素，数字被挤离列心——`cirstea-kalinskaya`
       实测 `6(4)` 比另一行的 `7` 左了 40px（改成绝对定位之后两者都在 718）

    真渲量过（`zheng-pridankina-us-open-2026-q3`，三盘，1080×1440）：Chromium
    报的盒子逐个和常量吻合——`.score-row` 940×104、`.score-fill` x=92 w=896、
    `.score-names` x=222 w=448（正是 `score_name_avail_px(3)` 算出来的数）、
    `.score-number` x=670 w=96、端帽 12×104。三列数字的墨迹中心因此落在
    **718 / 813 / 909**，两行逐列相差不超过 2px（差的是 `3` 和 `6` 的字形宽度，
    不是版式）。
    """
    monkeypatch.setattr(versus_poster, "_fetch_match_duration",
                        lambda source, where: "1:51")
    html_out = versus_poster._scoreboard_html(_cover())      # 三盘
    rows = re.findall(r'<div class="score-row score-row--(win|lose)">(.*?)(?=<div class="score-row|$)',
                      html_out, re.S)
    assert [kind for kind, _ in rows] == ["win", "lose"], (
        f"比分板要一行赢家一行输家，解出来却是 {[k for k, _ in rows]}：\n{html_out}")
    for kind, body in rows:
        assert body.index('class="score-names"') < body.index('class="score-sets"'), (
            f"{kind} 那一行的盘分排在名字前面了：{body}")
        cells = body.count('class="score-number ')
        assert cells == 3, (
            f"{kind} 那一行有 {cells} 个盘分格子，三盘应该是 3 个：{body}")

    css = _board_css(monkeypatch)
    flex = re.search(r"flex:0 0 (\d+)px", _rule(css, ".score-number"))
    assert flex and int(flex.group(1)) == versus_poster.SCORE_SET_COL_PX, (
        f"`.score-number` 的列宽不是写死的 {versus_poster.SCORE_SET_COL_PX}px："
        f"{_rule(css, '.score-number')!r}\n"
        "列宽一旦跟着内容走，带抢七上标的那一格就会比别人宽，两行错开。")
    assert "min-width:0" in _rule(css, ".score-names"), (
        "`.score-names` 少了 `min-width:0`：长名字撑不下时会把这一行的盘分"
        "整块往右推，而另一行不会跟着推")
    assert "position:absolute" in _rule(css, ".score-number sup"), (
        "抢七小分留在文档流里了：带小分的那一格会多出三十来像素，数字被推离"
        "列心——实测 `cirstea-kalinskaya` 的 `6(4)` 和另一行的 `7` 差 40px。")


def test_比分板底下那层要是一条长坡不许陡到看得出边(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch):
    """账号所有者 2026-08-29：「背景也要渐变的，你看原图里**最上面的背景和封面图
    没有明显的分割**感觉」。

    在那之前是 `top:-70px` ＋ 110px 淡到 0.86——**坡陡了五倍**，顶上就有一条
    看得出来的边。参考图那条坡是量出来的：两列独立取样（x=0.93w / 0.98w，
    两列逐行几乎相同，所以是叠上去的一层而不是照片本身），拿照片底色 91、
    面板色亮度 18 代进 `alpha=(91-L)/73` 反解——

        离藏青条上沿   -360  -300  -240  -180  -120   -60  +120  +240
        参考图 alpha   0.02  0.03  0.07  0.16  0.34  0.52  0.83  0.99
        我们 alpha     0.07  0.07  0.14  0.25  0.37  0.48  0.78  0.93

    也就是**五百多像素的坡，末端不透明**。

    ⚠️ **不能拿 CSS 文本当判据**（和 `test_封面不许再压一层居中的阴影` 同一个
    理由）：上面这段注释里正引着 `-70px` 和 `0.86` 这两个老写法，按文本扫会把
    「把坑记下来」判成「又踩了这个坑」。所以这一条**渲出来量像素**——底图给
    一张纯白，每一行的灰度直接就是 `1 - alpha`，不依赖任何一张真照片。

    ⚠️ **判据钉的是「坡有多长」，不是「有没有硬边」。** 老写法也没有硬边，
    它只是陡；拿「相邻行不许跳变」当判据，老写法照样能过。所以量的是
    **alpha 从 0.10 走到 0.80 跨了多少像素**：现在约 420px，老写法约 90px。
    门槛 300 落在两者中间，不贴着任何一版。

    另外两头也要钉，缺一头都不算判据：

    - **画布上半必须基本没被压暗**——只钉「坡够长」的话，把整幅铺一层灰
      也能得到一条很长的坡，而那会把人脸一起压掉。
    - **末端要够暗**——只钉上面两条的话，一条又长又浅的坡也能过，而那托不住
      比分板上的白字（输家那一行和场地/用时那一行直接压在照片上，赢家那一行
      有实心藏青条，永远不受影响）。
      ⚠️ **这一头 2026-08-29 从 0.90 降到 0.70**：账号所有者「背景底色可以再
      透明些」，`SCORE_PANEL_END_ALPHA` 从参考图那档 1.0 降到 0.78。
      **0.70 这个地板是算出来的，不是拍的**——白字压在最坏的底（纯白照片）上，
      合成底色 `L = 255(1−a) + 18a`，要拿到 WCAG 4.5:1 需要 `L ≤ 119`，
      也就是 `a ≥ 0.58`；留一档余量取 0.70。这里量到的是**合成值**（这层底
      ＋ 封面自己那条 scrim 的底边），所以它比常量本身高。
    """
    white = tmp_path / "white.png"
    Image.new("RGB", (1080, 1440), (255, 255, 255)).save(white)
    monkeypatch.setattr(versus_poster, "_fetch_match_duration",
                        lambda source, where: "2:19")
    body, css = versus_poster._solo_body({
        **_cover(), "eyebrow": "赛场之上", "layout": "solo", "hook": "赢了",
        "portrait": {"image": str(white)},
    })
    from tennislive.render.webcards import _font_css  # noqa: PLC0415
    shot = versus_poster._render_html(
        f"<!doctype html><meta charset=utf-8>"
        f"<style>{_font_css()}{css}</style>{body}", tmp_path / "probe.jpg")

    a = np.asarray(Image.open(shot).convert("L")).astype(float)
    # 右边一条，避开人物和文字
    alpha = 1 - a[:, 1030:1050].mean(axis=1) / 255

    # ⚠️ **量的窗口要从 y=500 起。** 封面顶上另有一条 scrim（给台头垫的，
    #    2026-08-17 定的「正中不压暗但文字那两条边要留」），它在 y=40 处
    #    alpha 0.50、到 y≈480 才落回底噪。把它算进来的话「alpha 第一次到
    #    0.10」会落在顶栏那一带，量出来的是它、不是这层底。
    PANEL_FROM = 500
    lower = alpha[PANEL_FROM:]

    def first_at(level: float) -> int:
        hit = np.where(lower >= level)[0]
        assert hit.size, f"整幅都没到 alpha {level}：这层底根本没渲出来？"
        return PANEL_FROM + int(hit[0])

    ramp = first_at(0.80) - first_at(0.10)
    assert ramp >= 300, (
        f"alpha 从 0.10 到 0.80 只用了 {ramp}px——坡太陡，顶上会看得出一条边。\n"
        "账号所有者要的是「和封面图没有明显的分割」，参考图那条坡跨五百多像素。")
    # 坡上方必须真有一段**没被压暗**的画面（人脸、上半身在那儿）。
    # ⚠️ 这一头不能钉一个绝对的 y：`.storycopy` 的钩子有几行，比分板就跟着
    #    上下浮动，写死一个高度会在钩子长的封面上落进坡里。改成「坡开始之前
    #    那一段」，并要求它**够宽**——一条铺满整幅的灰会让坡从画布顶上就开始，
    #    这一段当场缩没，判据自己就报出来。
    clean_to = first_at(0.10) - 40
    assert clean_to - PANEL_FROM >= 80, (
        f"坡从 y={first_at(0.10)} 就开始了，上面几乎没有干净的画面——"
        "这层底怕是铺满了整幅，而不是收在比分板那一带。")
    middle = alpha[PANEL_FROM:clean_to].max()
    assert middle < 0.15, (
        f"坡上方那一段最暗处 alpha {middle:.2f}——这层底爬到人脸上去了。\n"
        "坡要长，但不能靠「整幅铺一层灰」来凑长。")
    assert alpha[-1] >= 0.70, (
        f"画布最底下 alpha 只有 {alpha[-1]:.2f}——白字压在纯白照片上时，"
        "要拿到 4.5:1 需要 alpha ≥ 0.58，这里留一档余量取 0.70。\n"
        "账号所有者要的是「再透明些」，不是「透到托不住字」。")


def test_五盘也放得下(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """五盘是这块板最紧的一档——**而紧到什么程度只有渲出来才看得见**。

    账号所有者 2026-08-29：「同时看下如果是五盘数据能否放下」。

    五盘那一档名字只剩 300px（三盘 492、两盘 588），而且末一盘可能带一个
    **两位数的抢七小分**（`7-6(10)`），那个上标是绝对定位、伸到列与列之间的
    空当里——最后一列往右伸就直接顶着板子的右沿。两头都不在 HTML 字符串里
    看得出来，也不在 `score_cn_px` 的返回值里看得出来。

    实测（1080×1440，Chromium）——

        库里最长的名字 `胡安·曼努埃尔·塞伦多洛（51）`（12 个字）配五盘：
        字号压到下限 28px，名字墨迹到 x=484，名字那一格右边界 490，
        第一个盘分从 547 起 → **还剩 63px**
        末一盘 `7-6(10)`：输家那一行墨迹到 x=1006，板子右沿 1010 → **还剩 4px**

    ⚠️ 上面这组数 2026-08-29 重量过一遍：盘分改成右对齐、`SCORE_FILL_PAD_R`
    从 30 提到 40 之后，名字那一格从 300px 收到 290px，而末一盘那个两位数
    抢七走的是 `.scoreboard--tbwide` 那档小一号的上标（见
    `test_抢七小分右对齐之后也不许伸出板子`）。

    ⚠️ **`score_cn_px` 的告警在这一档是保守的**：它算出「要 27px 才放得下」
    并按下限 28px 渲，可渲出来根本没顶上去。所以那句告警只说「已经最小了，
    自己看一眼」，不说「会顶到盘分上」——**一句没量过的话写进告警，下一个人
    会拿它当判据**。

    判据钉两头，缺一头都不算：

    1. **名字不许压到盘分上**——只钉这一头的话，把盘分列缩窄也能过
    2. **末一盘的抢七小分不许伸出板子**——只钉这一头的话，名字压上去照样绿
    """
    white = tmp_path / "w.png"
    Image.new("RGB", (1080, 1440), (255, 255, 255)).save(white)
    monkeypatch.setattr(versus_poster, "_fetch_match_duration",
                        lambda source, where: "4:12")
    vp = versus_poster
    long_name = "胡安·曼努埃尔·塞伦多洛"      # 库里最长的中文名，12 个字
    body, css = vp._solo_body({
        "winner": long_name,
        # 末一盘带两位数抢七：小分挂在**输**的那个数字上，也就是最后一列
        "result": "6-4 3-6 7-6(5) 4-6 7-6(10)",
        "scoreboard": {"court": "Court Philippe-Chatrier",
                       "duration_source": {"url": "fixture"}},
        "matchup": [{"name": long_name, "name_en": "J. M. CERUNDOLO",
                     "country": "ARG", "rank": 51},
                    {"name": "范德赞德舒尔普", "name_en": "B. VAN DE ZANDSCHULP",
                     "country": "NED", "rank": 70}],
        "eyebrow": "赛场之上", "layout": "solo", "hook": "五盘四小时",
        "portrait": {"image": str(white)},
    })
    from tennislive.render.webcards import _font_css  # noqa: PLC0415
    shot = vp._render_html(
        f"<!doctype html><meta charset=utf-8>"
        f"<style>{_font_css()}{css}</style>{body}", tmp_path / "five.jpg")

    px = np.asarray(Image.open(shot).convert("RGB")).astype(int)
    lum = np.asarray(Image.open(shot).convert("L")).astype(float)
    # 赢家那条长条的行范围——按藏青底色找，不按写死的 y（钩子几行会让板子上下浮动）
    navy = ((np.abs(px[:, :, 0] - 0x17) < 26) & (np.abs(px[:, :, 1] - 0x27) < 26)
            & (np.abs(px[:, :, 2] - 0x86) < 32))
    rows = np.where(navy.sum(axis=1) > vp.SCORE_BOARD_W * 0.4)[0]
    assert rows.size, "没找到赢家那条长条——底色改了？"

    def ink_cols(y0: int, y1: int) -> np.ndarray:
        return np.where((lum[y0:y1] > 200).any(axis=0))[0]

    # 版式里那几个边界，从常量算，不写死
    board_l = (1080 - vp.SCORE_BOARD_W) // 2
    name_l = board_l + vp.SCORE_FILL_PAD_L + vp.SCORE_FLAG_W + vp.SCORE_FLAG_GAP
    name_r = name_l + vp.score_name_avail_px(5)
    board_r = board_l + vp.SCORE_BOARD_W

    # ① 名字不许压到盘分上：名字那一格右边界之后、第一个盘分之前必须是空的
    win = ink_cols(rows.min() + 8, rows.max() - 6)
    in_gap = win[(win > name_r) & (win < name_r + vp.SCORE_FILL_PAD_L)]
    assert in_gap.size == 0, (
        f"名字压过了它那一格的右边界（{name_r:.0f}px），"
        f"墨迹出现在 {in_gap[:6].tolist()}——五盘那一档名字只剩 "
        f"{vp.score_name_avail_px(5):.0f}px，长名字会顶到盘分上。")

    # ② 末一盘的两位数抢七小分不许伸出板子（输家那一行，板子下面没有底色）
    lose = ink_cols(rows.max() + 16, rows.max() + 16 + vp.SCORE_ROW_H)
    assert lose.size, "输家那一行一个字都没渲出来"
    assert lose.max() <= board_r, (
        f"输家那一行的墨迹到了 x={lose.max()}，而板子右沿是 {board_r}——"
        "多半是末一盘那个两位数抢七小分伸出去了。"
        "`.score-number sup` 是绝对定位、往右伸进列与列之间的空当，"
        "最后一列没有下一列可伸，只能靠 `SCORE_FILL_PAD_R` 那点余量。")


def _render_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **over) -> Path:
    """按真流程渲一张 solo 封面出来（底片纯白，量什么都是最坏情况）。"""
    white = tmp_path / "white.png"
    if not white.exists():
        Image.new("RGB", (1080, 1440), (255, 255, 255)).save(white)
    monkeypatch.setattr(versus_poster, "_fetch_match_duration",
                        lambda source, where: "2:19")
    cover = {**_cover(), "eyebrow": "赛场之上", "layout": "solo", "hook": "赢了",
             "portrait": {"image": str(white)}, **over}
    body, css = versus_poster._solo_body(cover)
    from tennislive.render.webcards import _font_css  # noqa: PLC0415
    return versus_poster._render_html(
        f"<!doctype html><meta charset=utf-8>"
        f"<style>{_font_css()}{css}</style>{body}",
        tmp_path / f"board{len(list(tmp_path.glob('board*.jpg')))}.jpg")


def _navy_rows(shot: Path) -> tuple[int, int]:
    """赢家那条藏青条的行范围——按底色找，不按写死的 y（钩子几行会让板子浮动）。"""
    px = np.asarray(Image.open(shot).convert("RGB")).astype(int)
    navy = ((np.abs(px[:, :, 0] - 0x17) < 26) & (np.abs(px[:, :, 1] - 0x27) < 26)
            & (np.abs(px[:, :, 2] - 0x86) < 32))
    rows = np.where(navy.sum(axis=1) > versus_poster.SCORE_BOARD_W * 0.4)[0]
    assert rows.size, "没找到赢家那条长条——底色改了？"
    return int(rows.min()), int(rows.max())


def _ink(shot: Path, y0: int, y1: int, thr: int = 200) -> np.ndarray:
    lum = np.asarray(Image.open(shot).convert("L")).astype(float)
    return np.where((lum[y0:y1] > thr).any(axis=0))[0]


def test_盘分右对齐而且和用时落在同一条右边线上(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """账号所有者 2026-08-29：「比分建议右对齐」。

    在这之前盘分是 `text-align:center`——每一列 96px、数字只占 42px 上下，
    于是末一盘那个数字的右沿停在 x=949，而它正上方的用时「2:19」是贴着
    `SCORE_HEAD_PAD_R` 右对齐的、右沿在 977。**两条右边线差了 28px**，
    比分因此看起来像浮在条子中间。

    ⚠️ **单看「两行的列对不对得齐」是看不出来的**：居中和右对齐都让两行对齐
    （每个数字都是单字符、等宽），差别只在整组数字离右边多远。所以这条判据
    钉的是**另一件事**——数字的右沿和它头顶那一行的右沿是不是同一条线。

    钉两头，缺一头都不算：

    1. **数字右对齐到它那一列的右沿**（不是居中）——只钉第 2 头的话，把
       `SCORE_HEAD_PAD_R` 调大也能让两条线重合，而数字还浮在中间。
    2. **和用时同一条右边线**——只钉第 1 头的话，头一行的内边距漂走了也不红。
    """
    shot = _render_board(tmp_path, monkeypatch)
    top, bot = _navy_rows(shot)
    board_l = (1080 - versus_poster.SCORE_BOARD_W) // 2
    col_r = board_l + versus_poster.SCORE_BOARD_W - versus_poster.SCORE_FILL_PAD_R

    win = _ink(shot, top + 8, bot - 6)
    head = _ink(shot, top - versus_poster.SCORE_ROW_H, top - 6)
    assert win.size and head.size, "板子上一个字都没渲出来"

    # ① 右对齐：末一盘那个数字的右沿要贴着这一列的右沿（差的只是字形的右边距）
    assert col_r - win.max() <= 8, (
        f"末一盘那个数字的右沿在 x={win.max()}，而这一列的右沿是 {col_r}——"
        f"差了 {col_r - win.max()}px，多半是又退回 `text-align:center` 了。")

    # ② 和用时同一条右边线
    assert abs(win.max() - head.max()) <= 6, (
        f"盘分右沿 x={win.max()}、用时右沿 x={head.max()}，两条线差 "
        f"{abs(win.max() - head.max())}px。账号所有者要的「右对齐」就是这两条"
        "线要重合——它们一个在长条里、一个在长条外，各自的内边距必须是同一个数。")


@pytest.mark.parametrize("result,tag", [
    ("6-1 4-6 6-2", "无抢七"),
    ("6-1 4-6 7-6(5)", "末盘单位数抢七"),
    ("6-1 4-6 7-6(12)", "末盘两位数抢七"),
])
def test_抢七小分右对齐之后也不许伸出板子(
        result: str, tag: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """数字右对齐之后，抢七小分是**唯一**还会往右伸的东西。

    小分是绝对定位、挂在数字右肩上（`left:100%`），所以它伸进的是末一盘右边
    那点内边距。实测（1080×1440，Chromium）：

        `(5)`  从列右沿起 36px —— `SCORE_FILL_PAD_R` 40px，还剩 9px
        `(12)` 从列右沿起 52px —— 40px 装不下，会伸出板子 7px

    所以两位数那一档**整块板的上标换小一号**（`.scoreboard--tbwide`，`.32em`）。
    ⚠️ 上标是绝对定位的，改它的字号**不影响任何布局**——数字、列宽、名字那一格
    一个像素都不变，所以这一档只花在它自己身上。

    ⚠️ 155 条已发的 spec 里**末一盘两位数抢七一条都没有**（末一盘带抢七的 17
    条全是单位数）。这一档今天走不到，它防的是以后真出现一次时**不吭声地伸出
    板子**——而那和「就是这么渲的」在成片上长得一模一样。
    """
    shot = _render_board(tmp_path, monkeypatch, result=result)
    top, bot = _navy_rows(shot)
    board_r = (1080 - versus_poster.SCORE_BOARD_W) // 2 + versus_poster.SCORE_BOARD_W
    lose = _ink(shot, bot + versus_poster.SCORE_ROW_GAP + 6,
                bot + versus_poster.SCORE_ROW_GAP + versus_poster.SCORE_ROW_H)
    assert lose.size, "输家那一行一个字都没渲出来"
    assert lose.max() <= board_r, (
        f"[{tag}] 输家那一行的墨迹到了 x={lose.max()}，板子右沿是 {board_r}——"
        "抢七小分伸出去了。要么把 `SCORE_FILL_PAD_R` 加宽，要么让这一档走"
        "`.scoreboard--tbwide` 那个小一号的上标。")


def test_场地和用时前面各有一个白色小图标(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """账号所有者 2026-08-29：「球场和比赛用时前面各加一个小 logo 表示下」
    「小 icon，白色的就行」「不然很多人不知道是啥」。

    判据**不查 HTML 里有没有 `<svg>`**——那只能防「有人把它删了」，防不住
    「它渲出来是空的」：`.score-icon` 写的是 `fill:none;stroke:currentColor`，
    描边那一半没画上的话 svg 照样在 HTML 里，画面上什么都没有。

    所以渲两版比：**把两个图标换成空串**再渲一次。

    - 场地在左边、左对齐 → 有图标时**文字被往右推**，那一块的右沿跟着右移
    - 用时在右边、右对齐 → 有图标时**图标长在文字左边**，那一块的左沿左移

    两边各是一个图标，所以这是两头独立的判据：只画一个的话另一头当场红。

    另外两头：图标得是白的（他点名的），以及**颜色只有一处出处**——两个 svg
    自己不许写死颜色，靠 `.score-icon` 的 `currentColor` 跟着文字走，这样
    「文字全部纯白」那条一改，图标自己跟上，不会分叉成两处。
    """
    # ⚠️ **先把两个 svg 的原文抄下来。** 下面要把它们 monkeypatch 成空串去渲
    # 「没有图标」那一版，而第 ③ 头读的正是这两个模块属性——不先抄下来的话它
    # 读到的是空串，`'stroke="' not in ""` 恒真，那一头就成了一盏绿灯。
    # （这一条是反向验证抓出来的：往 svg 里写死一个 `stroke="#fff"`，它照样绿。）
    icons = (versus_poster._COURT_ICON, versus_poster._CLOCK_ICON)

    shot = _render_board(tmp_path, monkeypatch)
    top, _ = _navy_rows(shot)
    head_y = (top - versus_poster.SCORE_ROW_H, top - 6)
    MID = 600                      # 左边是场地、右边是用时，中间是空的

    def halves(s: Path) -> tuple[np.ndarray, np.ndarray]:
        ink = _ink(s, *head_y)
        return ink[ink < MID], ink[ink >= MID]

    court_on, clock_on = halves(shot)

    # ② 图标是白的——先在「有图标」这一版上量，别等 monkeypatch 退掉
    lum = np.asarray(Image.open(shot).convert("L")).astype(float)
    x0 = (1080 - versus_poster.SCORE_BOARD_W) // 2 + versus_poster.SCORE_HEAD_PAD_L
    box = lum[head_y[0]:head_y[1], x0:x0 + 34]
    assert box.max() >= 235, (
        f"场地那个图标所在的一格最亮只有 {box.max():.0f}——他点名「白色的就行」。")

    monkeypatch.setattr(versus_poster, "_COURT_ICON", "")
    monkeypatch.setattr(versus_poster, "_CLOCK_ICON", "")
    court_off, clock_off = halves(_render_board(tmp_path, monkeypatch))

    # ① 两个图标各占各的位
    assert court_on.min() == pytest.approx(court_off.min(), abs=4), (
        "场地那一块的左沿动了——图标该从文字原来那条左边线开始，"
        "把文字往右推，而不是自己挤到左边线外面去。")
    court_push = int(court_on.max() - court_off.max())
    assert court_push >= 20, (
        f"带图标和不带图标，场地那一块的右沿只差 {court_push}px——"
        "球场那个图标多半根本没渲出来。")
    assert clock_on.max() == pytest.approx(clock_off.max(), abs=4), (
        "用时那一块的右沿动了——它是右对齐的，图标只该往左长。")
    clock_push = int(clock_off.min() - clock_on.min())
    assert clock_push >= 20, (
        f"带图标和不带图标，用时那一块的左沿只差 {clock_push}px——"
        "钟那个图标多半根本没渲出来。")

    # ③ 颜色只有一处出处
    src = Path(versus_poster.__file__).read_text(encoding="utf-8")
    assert "stroke:currentColor" in src, "图标的颜色要跟着文字走，别另写一份"
    for svg in icons:
        assert 'stroke="' not in svg and 'fill="' not in svg, (
            "颜色写进 svg 自己就分叉了——`.score-icon` 那条 `currentColor` "
            "才是唯一的出处。")


def test_球场那个图标要画成网球场的样子(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """账号所有者 2026-08-29 说了两次：「小 icon，白色的就行，不然很多人不知道
    是啥」→「球场的 icon 要画成网球场的样子啊」。

    前两版都过了「图标渲出来了、是白的」那条判据，**而它们都不像网球场**：

        第一版  竖的方框、里面切四格            缩到 27px 读出来是**一扇窗**
        第二版  横的外框 ＋ 球网 ＋ 一个内框     读出来是**一块多米诺骨牌**

    所以「有没有图标」和「像不像网球场」是两件事，各要一条判据。像不像当然
    机械判不了，**但那三笔认得出来的特征量得出来**——把图标那一格抠出来
    二值化，三头（实测值见断言里的注释，三版逐个量过）：

        宽高比   贯通全宽的横线   最上一行的墨宽
        1.76           4              0.05      ← 现在这版（真球场）
        2.00           2              0.95      ← 第二版：只有上下两条外框
        0.91           5              0.90      ← 第一版：竖的，宽高比就不对

    1. **横的**（宽高比 ≥ 1.5）——网球场是 2:1 的横图，竖着画就成了窗
    2. **四条贯通全宽的横线**（底线两条 ＋ 单打边线两条）——第二版的内框边
       不贯通，只有两条；这一头钉的正是「双打边道」那两笔
    3. **球网出头**（最上一行的墨只有球网那一竖，占宽 ≤ 0.25）——网柱在界外，
       所以那条竖线上下各伸出一点；两个旧版最上一行都是贯通的外框边

    ⚠️ 三头缺一不可：第一版过得了第 2 头，第二版过得了第 1 头。
    """
    shot = _render_board(tmp_path, monkeypatch)
    top, _ = _navy_rows(shot)
    lum = np.asarray(Image.open(shot).convert("L")).astype(float)
    y0, y1 = top - versus_poster.SCORE_ROW_H, top - 6
    x0 = (1080 - versus_poster.SCORE_BOARD_W) // 2 + versus_poster.SCORE_HEAD_PAD_L
    # 图标那一格：从场地那一行的左边线起，取到文字之前（图标和文字之间有缝）
    band = lum[y0:y1, x0:x0 + 70] > 190
    cols = np.where(band.any(axis=0))[0]
    assert cols.size, "场地那一行的最左边一个像素都没有——图标没渲出来？"
    end = cols[0]
    for c in cols:
        if c - end > 6:      # 图标和文字之间那道缝
            break
        end = c
    glyph = band[:, cols[0]:end + 1]
    rows = np.where(glyph.any(axis=1))[0]
    glyph = glyph[rows.min():rows.max() + 1]
    h, w = glyph.shape
    widths = glyph.sum(axis=1) / w

    assert w / h >= 1.5, (
        f"图标是 {w}×{h}，宽高比只有 {w / h:.2f}——网球场是 2:1 的横图，"
        "画进方框里就成了一扇窗（第一版就是这么来的）。")

    wide = widths >= 0.8
    bands = int((wide[:-1] & ~wide[1:]).sum() + bool(wide[-1]))
    assert bands >= 4, (
        f"贯通全宽的横线只有 {bands} 条——网球场要有四条（上下底线 ＋ 两条"
        "单打边线，也就是双打边道那两笔）。只有两条的话画的是「外框套内框」，"
        "读出来是一块多米诺骨牌。")

    assert widths[0] <= 0.25 and widths[-1] <= 0.25, (
        f"最上/最下一行的墨占宽 {widths[0]:.2f}/{widths[-1]:.2f}——"
        "网柱在界外，球网那一竖要上下各伸出一点，所以最上和最下那一行"
        "应该只有球网、不该是贯通的外框边。")
