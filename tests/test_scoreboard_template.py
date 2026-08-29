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
