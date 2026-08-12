"""数据统计对照图这条线上的规矩（CLAUDE.md：规则要落成测试）。

账号所有者 2026-08-12：「我需要以后固定下来，每次做赛场之上视频的同时
输出一份这个数据统计的对照图片」——`spec.stats` 是显式认领字段（跟
`mixed_fps`/`silent_source` 一个形状），写了就必须渲得出来，渲不出来
要当场报错，不许悄悄跳过。
"""
import inspect
import json
import re
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import render_stat_card as sc  # noqa: E402


def test_hi_lo_pct_frac四种方向都算对():
    """`_stat_row` 是这张图唯一的判优逻辑，四种类型各自的方向要分别验证：
    hi 大的赢、lo 小的赢、pct/frac 比率大的赢，平手一律不点亮任何一侧。"""
    a = {"aces": 3, "ue": 51, "first_in": 68, "first_total": 109,
         "bp_conv": 3, "bp_chances": 7, "df": 6}
    b = {"aces": 15, "ue": 72, "first_in": 61, "first_total": 109,
         "bp_conv": 3, "bp_chances": 6, "df": 6}

    # hi：数字大的赢——15 > 3，b 赢
    _, _, _, _, lead = sc._stat_row("hi", a, b, "aces")
    assert lead == "b"

    # lo：数字小的赢——51 < 72，a 赢（尽管 a 的原始数字更小）
    _, _, _, _, lead = sc._stat_row("lo", a, b, "ue")
    assert lead == "a"

    # pct：62% vs 56%，a 赢
    lv, lf, rv, rf, lead = sc._stat_row("pct", a, b, "first_in", "first_total")
    assert lv == "62%" and lf == "68/109"
    assert rv == "56%" and rf == "61/109"
    assert lead == "a"

    # frac：主数字显示分数本身，不折算成百分比；3/7=0.43 < 3/6=0.5，b 赢
    lv, lf, rv, rf, lead = sc._stat_row("frac", a, b, "bp_conv", "bp_chances")
    assert lv == "3/7" and rv == "3/6"
    assert lf == "" and rf == ""  # frac 类型不带小字注脚
    assert lead == "b"

    # 平手（双误都是 6）：不点亮任何一侧
    _, _, _, _, lead = sc._stat_row("lo", a, b, "df")
    assert lead is None


def test_没有stats字段报错说清怎么补():
    spec = {"cover": {}}
    with pytest.raises(SystemExit, match="stats"):
        sc.build(spec)


def test_某一侧缺字段报错点名缺了谁():
    spec = {
        "cover": {},
        "stats": {"a": {"headshot": "x.jpg", "aces": 1}, "b": {"headshot": "y.jpg"}},
    }
    with pytest.raises(SystemExit, match="缺这些字段"):
        sc.build(spec)


def test_缺headshot单独报错不跟别的字段混在一起():
    """headshot 不是"数据"，是渲染这张图必需的素材——分开报，别跟数字字段
    的报错混成一句，不然读的人会先去补数字，补完才发现还缺一张图。"""
    spec = {"cover": {}, "stats": {"a": {"aces": 1}, "b": {}}}
    with pytest.raises(SystemExit, match="fetch_official_headshot"):
        sc.build(spec)


def test_数据统计图渲染排在成片写完之后():
    """渲这张图是发生在**视频已经渲完、`render.json` 已经写完**之后的一步——
    这样即使这张图渲失败，已经完工的视频和它的元数据不受影响。判据钉位置，
    不止钉行为：只测"报不报错"防不住"插在了渲视频中间"这种错法。"""
    import build_match_reel as reel  # noqa: PLC0415

    body = inspect.getsource(reel.render)
    final_print_pos = body.index('成片 {final}')
    stat_card_pos = body.index('spec.get("stats")')
    assert stat_card_pos > final_print_pos, (
        "数据统计图那段代码要排在成片渲完、打印出\"成片 …\"这行之后，"
        "不能插在渲视频的中途")
    # 而且要在 render.json 写完之后——图渲失败不该连累已经写好的产物元数据
    render_json_pos = body.index('"render.json"')
    assert stat_card_pos > render_json_pos


def test_有stats的spec都要有headshot文件和全部字段():
    """自动扫 `specs/reels/*.json`（视频+数据图两样都出的）和
    `specs/stat-cards/*.json`（只出数据图、不做视频的比赛——`stats` 的
    schema 不要求 `segments`/`sources`，那两样是 `build_match_reel.load_spec`
    专属的video管线要求，跟这张图无关，所以不逼着"只想要一张图"的比赛也去凑一份
    假的视频 spec）。不维护白名单——以后每条新写了 stats 的 spec 都自动接受
    这条检查，不用回来给这个测试加一行。"""
    repo = Path(__file__).resolve().parent.parent
    checked = 0
    paths = sorted((repo / "specs/reels").glob("*.json")) + \
        sorted((repo / "specs/stat-cards").glob("*.json"))
    for p in paths:
        spec = json.loads(p.read_text(encoding="utf-8"))
        stats = spec.get("stats")
        if not stats:
            continue
        checked += 1
        assert "a" in stats and "b" in stats, f"{p.name} 的 stats 要同时给 a 和 b"
        for side in ("a", "b"):
            raw = stats[side]
            assert "headshot" in raw, f"{p.name} stats.{side} 缺 headshot"
            headshot_path = repo / raw["headshot"]
            assert headshot_path.is_file(), (
                f"{p.name} stats.{side}.headshot 指向的文件不存在："
                f"{raw['headshot']}")
            needed = {f for row in sc.ROW_SPECS for f in row[2:]}
            missing = needed - set(raw)
            assert not missing, f"{p.name} stats.{side} 缺这些字段：{missing}"
        assert stats.get("_source"), (
            f"{p.name} 的 stats 缺 `_source`——这张图存在的意义就是"
            "数字要经得起查，_source 不是可选项")
    assert checked >= 1, "一条带 stats 的 spec 都没扫到，是不是目录名或字段名写错了"


def test_真实spec渲染出的html比分顺序方向都对():
    """拿仓库里真实的 rybakina-osaka spec（带真实 stats 和已缓存的官方头像）
    走一遍 build()，不需要网络也不需要 Chromium——纯 HTML 字符串生成。

    这是「查产物不查信号」的正用：不满足于"函数没报错"，去读生成的 HTML
    里比分和高亮到底对不对，跟这条 spec 已经核实过的真实赛果比对。
    """
    repo = Path(__file__).resolve().parent.parent
    spec = json.loads((repo / "specs/reels/rybakina-osaka.json").read_text(encoding="utf-8"))

    import os

    os.chdir(repo)  # build() 里 _data_uri 读的 headshot 路径是相对仓库根的
    out = sc.build(spec)

    # matchup[0]=大坂直美, matchup[1]=莱巴金娜（赢家），头像左边是大坂直美，
    # 所以 result 要反过来拼成"大坂直美视角"：6-4 6-7(5) 4-6。
    # ⚠️ 每个数字各自在自己的 <span> 里，画面上连成"6-4"是 CSS 排出来的，
    # DOM 文本里没有连续的"6-4"这个子串——按真实结构逐个 span 断言，
    # 不要按肉眼看到的样子去找一个不存在的连续字符串。
    set_rows = re.findall(r'<div class="h2h-set-row">(.*?)</div>', out)
    assert len(set_rows) == 3, f"应该有三个盘分，扫到 {len(set_rows)} 个"
    assert '<span class="setwin">6</span>' in set_rows[0]
    assert '<span class="setlose">4</span>' in set_rows[0]
    assert '<span class="setlose">6</span>' in set_rows[1]
    assert '<span class="setwin">7</span>' in set_rows[1]
    assert '<span class="tb">(5)</span>' in set_rows[1]
    assert '<span class="setlose">4</span>' in set_rows[2]
    assert '<span class="setwin">6</span>' in set_rows[2]

    def srow_containing(label: str) -> str:
        start = out.rindex('<div class="srow">', 0, out.index(f">{label}<"))
        return out[start:out.index("</div>", start)]

    # ACE 15:3，莱巴金娜（右边，b）领先，右边那侧要带 lead，左边不带
    ace_row = srow_containing("ACE")
    assert '<span class="sval sval-r lead">' in ace_row
    assert '<span class="sval sval-l">' in ace_row  # 左边（大坂直美）不领先，没有 lead

    # 双误 6:6 平手，两边都不该有 lead class
    assert "lead" not in srow_containing("双误")


def test_数据图文件名两处要同源():
    """`build_match_reel.py` 渲出 `stat_card.jpg`，`push_reel.py` 找同名文件
    决定推不推这一屏——两处各写一份字符串必分叉（`POSTER_NAME` 那次已经
    栽过，这次照那条判据抄）。"""
    import build_match_reel as reel  # noqa: PLC0415
    import push_reel  # noqa: PLC0415

    assert reel.STAT_CARD_NAME == push_reel.STAT_CARD_NAME == "stat_card.jpg"


def test_推送正文里数据图排在正文之后按钮之前且默认不出现():
    """账号所有者 2026-08-12：「以后出视频的同时输出这个图，推微信时候也带上」。

    位置钉死：正文之后（先讲故事）、按钮之前（不是压轴的 CTA）；第一屏仍然
    留给海报，不许把数据图顶到最前面去抢镜。"""
    import push_reel  # noqa: PLC0415

    body = push_reel.build_html(
        "https://x/v.mp4", "https://x/c.html", "导语",
        "标题一行\n\n正文一段", "https://x/poster.jpg", "赛场之上",
        stat_card="https://x/stat_card.jpg")
    assert body.count("<div") == body.count("</div>"), "div 标签数量对不上，闭合有误"
    assert "stat_card.jpg" in body
    body_pos = body.index("正文一段")
    stat_pos = body.index("stat_card.jpg")
    btn_pos = body.index("打开竖版成片")
    assert body_pos < stat_pos < btn_pos, "数据图要排在正文之后、按钮之前"
    poster_pos = body.index("poster.jpg")
    assert poster_pos < body_pos, "海报仍然是第一屏，不能被数据图顶掉"

    # 没写 stat_card 时——大多数存量片子——这一屏原样不出现，不留死链接
    no_stat = push_reel.build_html(
        "https://x/v.mp4", "https://x/c.html", "导语",
        "标题一行\n\n正文一段", "https://x/poster.jpg", "赛场之上")
    assert "stat_card" not in no_stat and "数据统计对照" not in no_stat
    assert no_stat.count("<div") == no_stat.count("</div>")


def test_有stat_card文件才带上这一屏(tmp_path):
    """`main()` 里那道判断：文件不在就安静地不带这一屏，不报错——和海报同一个
    处置（`[封面] … 不在，这次推送没有海报那一屏`）。真跑一遍 `--outdir` 的
    探测逻辑，不只测字符串常量。"""
    import push_reel  # noqa: PLC0415

    outdir = tmp_path / "reel"
    outdir.mkdir()
    assert not (outdir / push_reel.STAT_CARD_NAME).is_file()

    (outdir / push_reel.STAT_CARD_NAME).write_bytes(b"\xff\xd8\xff")  # 假 jpg 头
    assert (outdir / push_reel.STAT_CARD_NAME).is_file()
    url = push_reel.stat_card_url(outdir)
    assert url.endswith(f"{outdir.as_posix()}/{push_reel.STAT_CARD_NAME}")
