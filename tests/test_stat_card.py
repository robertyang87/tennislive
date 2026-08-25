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


def test_截图前必须等头像完整解码():
    """大头像固定等 400ms 会留下“上半张脸、下半块底色”的半解码截图。"""
    body = inspect.getsource(sc.render)
    assert "img.decode()" in body
    assert body.index("img.decode()") < body.index("tab.screenshot")


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


def test_双打headshot给列表时两张脸都渲染且共享同一个队伍描边():
    """`stats.a.headshot` 给两个路径的列表（双打，一队两个人）——两张
    `<img>` 都要出现，而且都带队伍的胜负描边（`h2h-ring--pair win`），
    不是给其中一个人单独判定。反向验证过：把两张改成同一张路径，
    `<img>` 计数不变（还是 2 个 `<img src=` 标签，只是 data URI 相同），
    证明是按列表长度渲的，不是按去重后的路径数渲的。"""
    repo = Path(__file__).resolve().parent.parent
    shots = sorted((repo / "assets/players/headshots").glob("*.png"))[:2]
    assert len(shots) == 2, "仓库里至少要有两张头像素材才能跑这条测试"
    rel = [str(p.relative_to(repo)) for p in shots]

    import versus_poster as vp  # noqa: E402

    vp._DURATION_CACHE["fake://match-duration"] = "1:18"  # noqa: SLF001
    spec = {
        "cover": {
            "winner": "队伍A",
            "result": "6-2 6-3",
            "matchup": [
                {"name": "队伍A", "name_en": "Team A", "country": "USA", "rank": None},
                {"name": "队伍B", "name_en": "Team B", "country": None, "rank": None},
            ],
            "scoreboard": {
                "court": "Grandstand",
                "duration_source": {"url": "fake://match-duration"},
            },
        },
        "stats": {
            # 凑够 `MIN_ROWS=7`（跳过可选的 winners/ue）——这条测试要走到
            # `build()` 里渲头像那一段，不能被 `usable_rows` 的行数下限拦住。
            "a": {"headshot": rel, "aces": 3, "df": 2,
                  "first_in": 27, "first_total": 49, "first_won": 20,
                  "second_won": 9, "second_total": 22,
                  "bp_conv": 2, "bp_chances": 5, "pts_won": 50},
            "b": {"headshot": rel[0], "aces": 1, "df": 4,
                  "first_in": 32, "first_total": 51, "first_won": 23,
                  "second_won": 7, "second_total": 19,
                  "bp_conv": 2, "bp_chances": 7, "pts_won": 50},
        },
    }

    import os

    os.chdir(repo)  # `_data_uri` 按仓库根解相对路径
    out = sc.build(spec)

    # ⚠️ 不能用裸的 "h2h-mid" 当分界——它先出现在 `<style>` 块的 CSS 选择器
    # 里（`.h2h-mid{…}`），比 body 里真正的 `<div class="h2h-mid">` 早得多，
    # 拿它切片会切出一个空字符串。要锚在真实的开标签上。
    mid_tag = '<div class="h2h-mid">'
    a_block = out[out.index('<div class="h2h-side">'):out.index(mid_tag)]
    b_block = out[out.index(mid_tag):]

    # a_block 里除了两张头像，国旗（country="USA"）也是一个 <img>——
    # 只数 `.h2h-pair` 到 `.h2h-cn` 之间那一段，别被国旗的 <img> 混进来数错。
    pair_start = a_block.index('<div class="h2h-pair">')
    pair_end = a_block.index('<div class="h2h-cn">')
    pair_block = a_block[pair_start:pair_end]
    assert pair_block.count("<img") == 2, "队伍A给了两张头像，HTML 里应该有两个 <img>"
    assert 'class="h2h-pair"' in a_block
    assert 'h2h-ring h2h-ring--pair win' in a_block, "两张脸都要带上队伍赢球的描边"
    # 队伍B仍然是单张（字符串路径），走的还是原来那条单人路径——list 和
    # str 两种写法互不干扰，改一边不该连累另一边。国籍留空，没有国旗 <img>，
    # 所以整个 b_block 里唯一的 <img> 就是它的单张头像。
    assert b_block.count("<img") == 1
    assert 'class="h2h-ring win"' not in b_block  # 队伍B输了，不带 win 描边
    assert 'class="h2h-ring"' in b_block


def test_双打headshot列表长度不对就报错():
    stat_fields = {"aces": 1, "df": 1, "first_in": 1, "first_total": 2,
                   "first_won": 1, "second_won": 1, "second_total": 1,
                   "bp_conv": 1, "bp_chances": 1, "pts_won": 50}
    spec = {
        "cover": {"winner": "队伍A", "result": "6-2 6-3", "matchup": [
            {"name": "队伍A", "name_en": "A", "country": None, "rank": None},
            {"name": "队伍B", "name_en": "B", "country": None, "rank": None},
        ], "scoreboard": {"court": "x", "duration_source": {"url": "fake://x"}}},
        "stats": {
            "a": {"headshot": ["only-one.jpg"], **stat_fields},
            "b": {"headshot": "y.jpg", **stat_fields},
        },
    }
    import versus_poster as vp  # noqa: E402

    vp._DURATION_CACHE["fake://x"] = "1:00"  # noqa: SLF001
    with pytest.raises(SystemExit, match="正好两张"):
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
            # 双打：headshot 可以是两个路径的列表（见 render_stat_card 模块
            # docstring「双打：两个人一队」），逐个查文件是不是真的在。
            shots = raw["headshot"] if isinstance(raw["headshot"], list) else [raw["headshot"]]
            if isinstance(raw["headshot"], list):
                assert len(shots) == 2, (
                    f"{p.name} stats.{side}.headshot 给了列表就必须正好两张，"
                    f"现在是 {len(shots)} 张")
            for shot in shots:
                assert (repo / shot).is_file(), (
                    f"{p.name} stats.{side}.headshot 指向的文件不存在：{shot}")
            # ⚠️ 制胜分 / 非受迫失误可以缺——**WTA 巡回赛拿不到那两项**
            # （见 `render_stat_card` 模块 docstring 和 CLAUDE.md），账号所有者
            # 2026-08-14 定的口径是「没有的话这两条就不显示」。其余字段照旧必填。
            needed = {f for row in sc.ROW_SPECS for f in row[3:]} - sc.OPTIONAL_FIELDS
            missing = needed - set(raw)
            assert not missing, f"{p.name} stats.{side} 缺这些字段：{missing}"
        # ⚠️ 可缺归可缺，**两边必须缺得一样**：只有一边有的时候那一行会把
        # 两个人的数放在同一行里比，而图上看起来完全正常。
        for field in sorted(sc.OPTIONAL_FIELDS):
            have = [side for side in ("a", "b") if field in stats[side]]
            assert len(have) != 1, (
                f"{p.name} 的 `{field}` 只有 stats.{have[0]} 有——两边都没有才算"
                "「拿不到」，只有一边有是数据对不齐")
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


def test_每一行都要有英文标签():
    """账号所有者 2026-08-15：「中间的技术统计再加一行写对应的英文，**后续都
    这么做**」。所以这不是某一张图的临时加工，是模板的一部分——以后往
    `ROW_SPECS` 里加一行忘了写英文，这条当场红。

    英文和中文写在**同一条 `ROW_SPECS`** 里，不另开一张对照表：两处必分叉，
    而分叉的样子是「某一行的英文是上一行的」，图上完全看不出来。

    ⚠️ **英文写空串是允许的，但只对「中文标签本身就是英文」的那种**（ACE，
    账号所有者 2026-08-15：「ACE 就不要英文了」——底下再写一行 `Aces` 是把同一个
    词说两遍）。中文是真中文却把英文留空，照旧红：那是漏填，不是认领。
    """
    seen = set()
    for row in sc.ROW_SPECS:
        cn, en = row[0], row[1]
        assert isinstance(en, str), f"「{cn}」的英文标签不是字符串"
        if not en:
            assert cn.isascii(), (
                f"「{cn}」把英文留空了。只有中文标签本身就是英文的那种"
                "（ACE）才允许留空——底下再写一遍是重复；中文标签留空串"
                "是漏填，不是认领")
            continue
        assert en.isascii(), f"「{cn}」的英文标签 {en!r} 里有非 ASCII 字符"
        assert en != cn, f"「{cn}」的英文位置填的还是中文"
        assert en not in seen, (
            f"英文标签 {en!r} 重复了——两行印同一个英文，读的人分不出哪行是哪行")
        seen.add(en)
    # 方向那一位现在排在第 2 位（cn, en, kind, *fields），别又滑回去
    assert {row[2] for row in sc.ROW_SPECS} <= {"hi", "lo", "pct", "frac"}, \
        "ROW_SPECS 的第 2 位不是方向了——加英文时索引挪错了"


def test_每行英文不许把行高撑高():
    """账号所有者同一句话里的第二个要求：「**每行的高度不变**，同时还是居中显示」。

    实测过（wang-vandewinkel 2160×3840）：加英文前后七条分隔线的 y 坐标
    **一个像素都没动**（1502 / 1740 / 1978 / 2216 / 2454 / 2692 / 2930，
    间距恒为 238），页脚那条也在原位。这条测试钉住做到这件事的那套机制，
    因为**行高变了在产物上不报错**，只是整张图悄悄变长。

    三头都要钉：

    1. 英文那个 span **嵌在 `.slabel` 里面**——`.srow` 是 `1fr auto 1fr` 三列，
       它要是变成第四个子元素就多一列，整行版式塌掉；
    2. `.slabel-en` 必须 `position:absolute`——绝对定位才不参与行盒高度，
       改成流内每行就会长高；
    3. 水平居中靠 `left:50%` + `translateX(-50%)`，不是 `left:0;right:0`——
       那一格的宽度是中文撑出来的，而英文更宽（`Break Points Converted`），
       撑在格子里会换行。
    """
    repo = Path(__file__).resolve().parent.parent
    spec = json.loads((repo / "specs/reels/rybakina-osaka.json").read_text(encoding="utf-8"))

    import os

    os.chdir(repo)
    out = sc.build(spec)

    # ① 结构：查真渲出来的 HTML，不查源码文本
    nested = re.findall(
        r'<span class="slabel">[^<]+<span class="slabel-en">[^<]+</span></span>', out)
    n_rows = out.count('<div class="srow">')
    # ACE 那一行故意没有英文（`.slabel--solo`），所以分母是「有英文的行数」，
    # 不是总行数——拿总行数当分母的话，以后再有一行认领「不要英文」这条就会
    # 误伤，而误伤会逼下一个人把检查删掉。
    n_en = sum(1 for row in sc.usable_rows(spec["stats"]["a"], spec["stats"]["b"])
               if row[1])
    # ⚠️ 数 markup 里的，不是裸 `slabel--solo`——那个串在 CSS 规则里也出现一次，
    # 按裸串数会多算一个（第一版就是这么写的，当场把 7 行数成 8 行）。
    n_solo = out.count('<span class="slabel slabel--solo">')
    assert n_rows >= sc.MIN_ROWS, f"只渲出 {n_rows} 行，样本 spec 不对"
    assert n_en and n_solo, "样本里要同时有带英文和不带英文的行，否则这条只验了一半"
    assert n_en + n_solo == n_rows, (
        f"{n_rows} 行里带英文 {n_en} 行 + 不带英文 {n_solo} 行对不上总数")
    assert len(nested) == n_en, (
        f"{n_en} 个有英文的行里只有 {len(nested)} 行的英文嵌在 .slabel 内。"
        "英文单独成一个网格项会多出一列，三列版式塌掉")

    # ② + ③ 机制：那两条 CSS 规则本身
    en_rule = re.search(r"\.slabel-en\{([^}]*)\}", out)
    assert en_rule, "CSS 里没有 .slabel-en 规则"
    css = en_rule.group(1).replace(" ", "")
    assert "position:absolute" in css, (
        "`.slabel-en` 不是绝对定位——它会参与行盒高度，每行都会长高，"
        "而这件事在产物上不报错，只是整张图悄悄变长")
    assert "left:50%" in css and "translateX(-50%)" in css, (
        "英文的水平居中要靠 left:50% + translateX(-50%)。"
        "`.slabel` 那一格是按中文宽度撑的，英文更宽，撑在格子里会换行")

    cn_rule = re.search(r"\n\.slabel\{([^}]*)\}", out)
    assert cn_rule, "CSS 里没有 .slabel 规则"
    cn_css = cn_rule.group(1).replace(" ", "")
    assert "position:relative" in cn_css, \
        "`.slabel-en` 的绝对定位要以 `.slabel` 为基准，后者必须 position:relative"
    assert re.search(r"top:-\d+px", cn_css), (
        "`.slabel` 少了往上提的那个位移——中文会留在原来的基线上，"
        "「中文 + 英文」这一对整体偏下，压到分隔线上")


def test_中英那一对的垂直位置是量出来的一组数():
    """账号所有者 2026-08-15 第二次反馈：「把中文往上移，英文在下面，然后它们
    并行居中。**垂直居中**」。

    第一版 `top:-11px` 只够把英文塞进去——「中文 + 英文」这一对的光学中心仍然
    比两侧那个大号数字低 18~25px（2160 空间），整块往下坠。−20/−21/−22 三档
    都真渲过、扫墨迹比过两个中心，−21px 的平均偏移 +0.6px 最正（那张表在
    `render_stat_card` 的 docstring 里）。

    ⚠️ **这条锁的不是 `top` 一个数，是量那一次的整组输入。** 光学中心由
    「中文字号 + 英文字号 + 两行间距 + top」四个数一起决定，改任何一个，
    −21px 就不再是量出来的那个答案了——而**歪掉在产物上不报错**，只是每一行
    的标签整体偏一点，谁也不会注意到。所以四个一起钉：动其中任何一个，这条
    当场红，逼着重量一次而不是顺手改个数。
    """
    src = Path(sc.__file__).read_text(encoding="utf-8")

    def decl(rule: str, prop: str) -> str:
        m = re.search(rf"\n\.{rule}\{{{{([^}}]*)\}}}}", src)
        assert m, f"CSS 里没有 .{rule} 规则"
        got = re.search(rf"(?<![\w-]){prop}:(-?[\d.]+)px", m.group(1).replace(" ", ""))
        assert got, f".{rule} 少了 {prop}"
        return got.group(1)

    measured = {
        (".slabel", "top"): "-24",          # 量出来的那个位移（英文 24px 那一版）
        (".slabel", "font-size"): "32",     # 下面三个是量那一次的前提
        ("slabel-en", "font-size"): "24",
        ("slabel-en", "margin-top"): "4",
        # 没有英文的那一行（ACE）单独量的一档：纯中文在 top:0 时比数字中心
        # 低 10.6px，取 -5px，实测偏移 +2
        ("slabel--solo", "top"): "-5",
    }
    for (rule, prop), want in measured.items():
        got = decl(rule.lstrip("."), prop)
        assert got == want, (
            f"`.{rule.lstrip('.')}` 的 {prop} 从 {want}px 变成了 {got}px。"
            "中英那一对的垂直居中是拿这四个数一起量出来的（中文字号 32、"
            "英文字号 19、行距 4、位移 -21），改任何一个都要照 "
            "render_stat_card 的 docstring 重新扫一次墨迹中心，"
            "不是顺手把这条测试里的数字改掉")


def test_球场和用时分两行():
    """账号所有者 2026-08-15：「比赛时间和球场分两行」。

    原来是 `7 号球场 · 1:47` 挤在一行。判据查**真渲出来的 HTML**：两个值各占
    一个 `.h2h-meta`，而且中间那个间隔点没了——只查「有没有两个 div」防不住
    「分了行但还留着 `·`」，只查「没有 `·`」防不住「换成别的符号还是一行」。
    """
    repo = Path(__file__).resolve().parent.parent
    spec = json.loads((repo / "specs/reels/rybakina-osaka.json").read_text(encoding="utf-8"))

    import os

    os.chdir(repo)
    out = sc.build(spec)

    metas = re.findall(r'<div class="h2h-meta[^"]*">([^<]*)</div>', out)
    assert len(metas) == 2, f"球场和用时要各占一行，扫到 {len(metas)} 行：{metas}"
    court = str(spec["cover"]["scoreboard"]["court"]).strip()
    assert metas[0] == court, f"第一行应该是球场，实际是 {metas[0]!r}"
    assert re.fullmatch(r"\d+:\d\d", metas[1]), f"第二行应该是用时，实际是 {metas[1]!r}"
    assert "·" not in "".join(metas), "分了行就不要那个间隔点了"


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
