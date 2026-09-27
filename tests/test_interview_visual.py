"""赛后开麦的**画面**：颜色、字幕、顶栏、封面、收尾卡、接缝。

2026-09-27 UI / VI 评审 WP3 落的判据，每一条对应评审表里的一行（I1/I2/I3/I9/I11）
或账号所有者当天拍板的一题（Q1/Q2/Q4/Q7/Q17）。能不起浏览器、不起 ffmpeg 的
尽量不起；非得看像素的（断行、基线、接缝）才真渲。

⚠️ 已发的片子一律不重渲——这些判据管的是**以后**渲出来的样子。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "specs" / "interviews"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import build_interview_clip as clip  # noqa: E402
from tennislive.design_tokens import DARK, SCORE, ass, ass_inline  # noqa: E402


def _specs() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(SPECS.glob("*.json")) if not p.name.endswith(".draft.json")]


def _spec(slug: str) -> dict:
    return json.loads((SPECS / f"{slug}.json").read_text(encoding="utf-8"))


def _style(name: str) -> list[str]:
    row = next(r for r in clip._ASS_HEAD.splitlines() if r.startswith(f"Style: {name},"))
    return row.split(",")


def _burn(ass_text: str, tmp: Path, h: int = 1440):
    """把一份 ASS 烧到纯黑底上，回一张灰度数组。和成片同一个 `fontsdir`。"""
    import numpy as np
    from PIL import Image

    (tmp / "t.ass").write_text(ass_text, encoding="utf-8")
    png = tmp / "t.png"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"color=c=black:s={clip.CANVAS_W}x{h}:d=0.5",
         "-vf", f"subtitles={tmp / 't.ass'}:fontsdir={ROOT / 'assets/fonts'}",
         "-ss", "0.2", "-frames:v", "1", str(png)], check=True, timeout=120)
    return np.asarray(Image.open(png).convert("L")).astype(int)


# ── Q2 / Q17 / 颜色出处 ────────────────────────────────────────────────────

def test_中英字幕一律近白_和赛场之上原声字幕同一套():
    """Q2：中文字幕原来是 `&H0074DCC3`——想写 #74dcc3，ASS 是 BGR，渲出来是 #c3dc74
    那支淡黄绿。Q17：英文 44、中文 68 数字放大到 78，和「赛场之上」原声字幕同一套。
    这几个数从 `explainer` 现抠，两边再分开就当场红。"""
    from tennislive.video import explainer as E

    en, zh = _style("EN"), _style("ZH")
    assert en[3] == zh[3] == ass(DARK["subtitle-foreground"]) == "&H00ECF3E7"
    assert zh[3] != "&H0074DCC3", "BGR 写反的那支淡黄绿又回来了"
    assert "&H00ECF3E7" in E._ass_header(), "赛场之上原声字幕换了颜色，这边要跟着改"
    assert (clip._EN_RENDER_PX, clip._ZH_RENDER_PX, clip._ZH_NUM_PX) == (
        E._ASS_BILINGUAL_EN_SIZE, E._ASS_SIZE, E._ASS_NUM_SIZE) == (44, 68, 78)
    assert (int(en[2]), int(zh[2])) == (clip._EN_RENDER_PX, clip._ZH_RENDER_PX)


def test_顶栏主行近白_赢盘薄荷_连字符压暗和赛场之上同一支():
    """评审 3.4：顶栏标题 #fff → #f4fbf7；Q17：比分 40、连字符压暗；Q1：薄荷只表示「赢」。"""
    reel = __import__("build_match_reel")
    assert _style("HEADA")[3] == ass(DARK["foreground"])
    assert clip._SCORE_PX == reel.TOPBAR_SCORE_SIZE == 40
    assert "{" + clip._MARK_COLOUR + "}" == reel.TOPBAR_SETWIN_ASS == ass_inline(SCORE["win_video"])
    # 连字符：和赛场之上同一支灰（那边写成带 alpha 字节的 &H009CA793，值一样）
    dash = re.search(r"&H([0-9A-F]{6,8})&", clip._DASH_TAG).group(1)[-6:]
    assert dash == re.search(r"&H([0-9A-F]{6,8})&", reel.TOPBAR_SETDASH_ASS).group(1)[-6:]
    assert dash == ass_inline(SCORE["dash"])[5:11]

    spec = {"slug": "t", "event": "2026 某站 1/4决赛", "winner": "甲",
            "interview_kind": "赛后场上采访",
            "push": {"matchup": "甲 vs 乙", "score": "7-6(3) 4-6 6-4"}}
    runs = clip.header_runs(spec)[1]
    dashes = [tags for text, kind, tags, _ in runs if kind == "num" and text == "-"]
    assert len(dashes) == 3, f"每一盘一个单独的连字符段：{runs}"
    assert all(t == clip._DASH_TAG and clip._MARK_COLOUR not in t for t in dashes), (
        "连字符不许再跟着赢盘那个数字一起绿、一起粗")
    digits = [text for text, kind, _, _ in runs if kind == "num" and text.strip() not in {"-", "³"}]
    assert [d.strip() for d in digits] == ["7", "6", "4", "6", "6", "4"]


def test_英文短语高亮是品牌黄绿_薄荷只留给赢():
    """Q1（2026-09-27）：黄绿 `primary` 是唯一品牌强调色，薄荷只表示「这一方赢了」。
    `highlight_en` 原来借的是顶栏那支薄荷（评审 WP3 nit 1）——一句英文里的固定搭配
    不是「赢」。"""
    assert "{" + clip._PHRASE_COLOUR + "}" == ass_inline(DARK["primary"])
    out, hit = clip.highlight_en("It was tough to face.", ["tough to face"])
    assert hit == {"tough to face"}
    assert "{" + clip._PHRASE_COLOUR + "}tough to face" in out
    assert clip._MARK_COLOUR not in out, "英文短语又染成了表示「赢」的薄荷"


# ── I1：中文字幕不写标点 ────────────────────────────────────────────────────

def test_中文字幕烧上屏不带标点_只留问号叹号(tmp_path):
    """文件开头的 docstring 一直写着「中文按仓库规矩去标点」，`write_ass` 从来没做——
    已发 24 条 spec 共 972 行中文带着全角标点进了画面。英文那行照旧留标点。"""
    lines = [{"a": 0.0, "b": 1.0, "en": "We would lose very, very quickly."},
             {"a": 1.0, "b": 2.0, "en": "Can you hold on?"}]
    path = tmp_path / "t.ass"
    clip.write_ass(lines, ["我们会非常非常快就输掉。", "欧洲队7比5，守得住吗？"], 0.0, path)
    ev = [ln.split(",", 9) for ln in path.read_text(encoding="utf-8").splitlines()
          if ln.startswith("Dialogue:")]
    zh = [f[9] for f in ev if f[3] == "ZH"]
    en = [f[9] for f in ev if f[3] == "EN"]
    assert not any(ch in "".join(zh) for ch in "，。、：；"), zh
    assert zh[1].endswith("？"), "问号要留——少了它一问就成了陈述句"
    assert en[0].endswith("quickly.") and "," in en[0], "英文是学习素材，标点不动"

    # 全库：spec 里写的每一行中文，烧上屏的那一份都不许带这几个标点
    bad = []
    for spec in _specs():
        for cn in spec.get("zh") or []:
            shown = re.sub(r"\{[^}]*\}", "", clip.zh_display(cn))
            if any(ch in shown for ch in "，。、：；") or (cn.strip() and not shown.strip()):
                bad.append(f"{spec['slug']}: {cn!r} → {shown!r}")
    assert not bad, "\n".join(bad[:20])


def test_中文字幕放大数字和赛场之上是同一个式子():
    """`_ZH_RUN` 抄的是 `explainer._ASS_RUN`（不 import 的理由写在定义那儿：explainer
    一 import 2.4 秒）。抄的就得钉住：式子逐字相等，同一批句子烧出来的标记逐字节相等
    （评审 WP3 nit 6）。"""
    from tennislive.video import explainer as E
    from tennislive.video.subtitle_text import drop_punctuation

    assert (clip._ZH_RUN.pattern, clip._ZH_RUN.flags) == (E._ASS_RUN.pattern, E._ASS_RUN.flags)
    for cn in ("欧洲队7比5，守得住吗？", "他打出了第12个ACE。", "2026年美网", "我们会赢！"):
        assert clip.zh_display(cn) == E._ass_text(drop_punctuation(cn)), cn


def test_中文字幕带数字的那一条基线不许跳(tmp_path):
    """数字放大到 78 会把上锚那一行的 ascent 撑高约 8px，整行往下掉——字幕在 cue
    之间上下跳。`_zh_margin_v` 把带放大段的那一条提回去，汉字墨迹一个像素都不动。"""
    import numpy as np

    def first_char_rows(zh: str) -> tuple[int, int]:
        path = tmp_path / "z.ass"
        clip.write_ass([{"a": 0.0, "b": 1.0, "en": "We played well."}], [zh], 0.0, path)
        a = _burn(path.read_text(encoding="utf-8"), tmp_path)[clip._ZH_TOP - 20:]
        cols = np.where(a.max(0) > 100)[0]
        band = a[:, cols[0]:cols[0] + 44]
        rows = np.where(band.max(1) > 100)[0]
        return int(rows[0]), int(rows[-1])

    plain, digits = first_char_rows("我们今天打了好局"), first_char_rows("我们今天打了11局")
    assert plain == digits, f"带数字那一条的「我」墨迹 {digits}，不带的 {plain}——基线跳了"
    assert clip._zh_margin_v(clip.zh_display("我们今天打了11局")) < clip._ZH_TOP
    assert clip._zh_margin_v(clip.zh_display("我们今天打了好局")) == 0


def test_字幕渲染字号换了一个行都不许多(monkeypatch):
    """Q17 的前提：「断行仍按 46 量，不许错行」。

    ① 切行只看 `_FONT_SIZE`：把渲染字号改成任何值，`segment()` 切出来的行一个字不变；
    ② 渲出来的每一行不宽于量出来的那一行（libass 的 em ＝ 字号 ÷ winAscent+winDescent，
       78 号数字的 em 只有 53.9，比量宽用的 70 还小），所以 libass 不会自己再折一次；
    ③ 全库 spec 的中文逐行按渲染的样子量一遍，都在 952 以内。
    """
    from PIL import ImageFont

    assert clip._FONT_SIZE == {"en": 46, "zh": 70}, "量宽的字号不许跟着渲染字号动"
    words = [(i * 0.4, w) for i, w in enumerate(
        ("And doubles guys definitely volley better than us, so we tried "
         "to keep the ball low and make them hit up, which worked tonight.").split())]
    before = clip.segment(words, 0.0, 60.0)
    monkeypatch.setattr(clip, "_EN_RENDER_PX", 60)
    monkeypatch.setattr(clip, "_ZH_RENDER_PX", 90)
    assert clip.segment(words, 0.0, 60.0) == before
    monkeypatch.undo()

    zh_file = clip._FONT_FILES["zh"][0]
    ratio = clip._libass_em_ratio("zh")
    assert clip._ZH_NUM_PX / ratio < clip._FONT_SIZE["zh"]
    assert clip._EN_RENDER_PX / clip._libass_em_ratio("en") < clip._FONT_SIZE["en"]
    f_zh = ImageFont.truetype(zh_file, clip._ZH_RENDER_PX)
    f_num = ImageFont.truetype(zh_file, clip._ZH_NUM_PX)

    def rendered(shown: str) -> float:
        w = 0.0
        for part in re.split(r"(\{\\fs\d+\}[^{]*)", shown):
            m = re.match(r"\{\\fs(\d+)\}(.*)", part)
            if m:
                w += (f_num if int(m.group(1)) == clip._ZH_NUM_PX else f_zh).getlength(m.group(2))
            else:
                w += f_zh.getlength(part)
        return w / ratio

    worst, n = 0.0, 0
    for spec in _specs():
        rows = list(spec.get("zh") or [])
        for key in ("lead_in", "trail_in"):
            rows += [c["zh"] for c in ((spec.get(key) or {}).get("subs") or [])]
        for cn in rows:
            got = rendered(clip.zh_display(cn))
            assert got <= clip._zh_width(cn) + 1, f"{spec['slug']}: {cn} 渲出来比量的还宽"
            worst, n = max(worst, got), n + 1
    assert n > 1000, f"只扫到 {n} 行中文，判据的主语不够"
    assert worst <= clip._LINE_PX, f"最宽一行渲出来 {worst:.0f}px，超过 {clip._LINE_PX}"


# ── I9：顶栏宽度尺 ─────────────────────────────────────────────────────────

def test_双打顶栏第二行字号和单打一样():
    """PIL 按 em 量比 libass 渲出来宽 1.448 倍，双打那两条被量成 958~968px，
    缩到 35/41 号——而真渲只有 ~690px。量准之后双打和单打一个字号。"""
    for slug in ("ruud-zverev-laver-cup-2026-doubles-interview",
                 "alcaraz-mensik-laver-cup-2026-interview"):
        runs = clip.header_runs(_spec(slug))[1]
        sizes = {kind: {size for _, k, _, size in runs if k == kind} for kind in ("zh", "num")}
        assert sizes == {"zh": {clip._HEAD_SIZE["b"]}, "num": {clip._SCORE_PX}}, (slug, sizes)


def test_顶栏宽度尺量的是libass真渲出来的宽(tmp_path):
    """`_topbar_width` 的预测要和真烧出来的墨迹宽对得上（±4%，差的是字形两侧的
    side bearing 和描边）。拿最宽的那条双打顶栏真烧一次。"""
    import numpy as np

    spec = _spec("ruud-zverev-laver-cup-2026-doubles-interview")
    _, runs = clip.header_runs(spec)
    predicted = sum(clip._run_width(k, size, text) for text, k, _, size in runs)
    head_b = clip.header_ass(spec)[1]
    a = _burn(clip._ASS_HEAD + f"Dialogue: 0,0:00:00.00,0:00:01.00,HEADB,,0,0,0,,{head_b}\n",
              tmp_path)
    cols = np.where(a[80:140].max(0) > 60)[0]
    ink = cols[-1] - cols[0] + 1
    assert abs(ink - predicted) / predicted < 0.04, f"预测 {predicted:.0f}px，真烧 {ink}px"
    assert ink < clip._HEAD_PX

    # 反过来：真装不下的照样要报错（量准了不等于闸没了）
    with pytest.raises(SystemExit, match="顶栏"):
        clip.header_lines({"slug": "t", "push": {"matchup": "甲 vs 乙"},
                           "interview_kind": "赛后场上采访",
                           "event": "2026 加拿大公开赛 WTA1000 女单 1/4 决赛 蒙特利尔 "
                                    "国家银行公开赛 第三场 夜场"})


def _subject_spec(name: str, kind: str) -> dict:
    spec = _spec("federer-ithf-2026-induction-speech")
    spec["subject"] = {**spec["subject"], "name": name}
    spec["interview_kind"] = kind
    return spec


def test_人物主标题顶栏按PNG真画的宽量_画不下要报错(tmp_path):
    """评审阻塞项（2026-09-27）：I9 把顶栏的尺子换成 libass 的（PIL ÷ 1.448）之后，
    **人物主标题那条路也跟着换了**——可它不走 libass，是 `_subject_topbar_png` 拿 PIL
    按字号＝em 直接画成像素的。闸于是宽松了 1.448 倍：「阿格涅什卡·拉德万斯卡 ·
    国际网球名人堂入选致辞」闸量 842px 放行，PNG 上真画 1266px，两头被 1080 的画布
    切掉，而那张 PNG 的像素闸只数够不够亮，照样过。

    三件事：画不下的要报错；量的那把尺子就是画的那一支字体（TTC index 2 简体，
    不是 `_measure_at` 读的 index 0 日文——「·」在两个 face 里是 54 对 30px）；
    装得下的那条，预测宽 = PNG 上真画出来的墨迹宽，而且没贴画布边。
    """
    import numpy as np
    from PIL import Image

    size = clip._HEAD_SIZE["a"]
    # ① 评审的复现：真画 1266px
    big = _subject_spec("阿格涅什卡·拉德万斯卡", "国际网球名人堂入选致辞")
    assert clip._subject_head_width(size, clip.header_runs(big)[0][0][0]) > clip._HEAD_PX
    with pytest.raises(SystemExit, match="顶栏这行 1266px"):
        clip.header_lines(big)
    with pytest.raises(SystemExit, match="两头会被画布切掉"):
        clip._subject_topbar_png(big, tmp_path)

    # ② 贴边那一种：按日文 face 量 901px 放得下，按真画的简体 face 是 996px——
    #    拿 `_measure_at` 顶替画字那支字体，这一条就漏过去
    edge = _subject_spec("玛丽亚·何塞·马丁内斯·桑切斯", "致辞")
    main = clip.header_runs(edge)[0][0][0]
    assert clip._measure_at("zh", size, main) <= clip._HEAD_PX < clip._subject_head_width(size, main)
    with pytest.raises(SystemExit, match="顶栏这行"):
        clip.header_lines(edge)

    # ③ 装得下的那条：量的就是画的
    ok = _spec("federer-ithf-2026-induction-speech")
    png = clip._subject_topbar_png(ok, tmp_path)
    alpha = np.asarray(Image.open(png).getchannel("A"))
    cols = np.where(alpha[:clip._TOPBAR_BAND_SPLIT_Y].max(0) > 0)[0]
    ink = cols[-1] - cols[0] + 1
    predicted = clip._subject_head_width(size, clip.header_lines(ok)[0])
    assert abs(ink - predicted) / predicted < 0.03, f"预测 {predicted:.0f}px，PNG 上画了 {ink}px"
    assert 0 < cols[0] and cols[-1] < clip.CANVAS_W - 1, "装得下的那条也不许贴画布边"


# ── Q7 / I11：封面 ─────────────────────────────────────────────────────────

def _frame(tmp: Path) -> Path:
    from PIL import Image

    p = tmp / "f.jpg"
    Image.new("RGB", (1080, 810), (60, 70, 90)).save(p, quality=90)
    return p


def test_封面对齐赛场之上_标题94_副标题赛事对阵_没有底部标签(tmp_path):
    """Q7：标题 94（= versus_poster.HOOK_TITLE_PX）、副标题「赛事 · A VS B」、
    删掉底部那颗青绿标签；I11：文字列和台头同在 x=70。"""
    import versus_poster

    spec = _spec("ruud-zverev-laver-cup-2026-doubles-interview")
    html = clip.cover_html(spec, _frame(tmp_path))
    assert clip._TITLE_PX == versus_poster.HOOK_TITLE_PX == 94
    assert re.search(r"\.title\{[^}]*font-size:94px", html)
    assert "class=tag" not in html and ".tag" not in html and "#74dcc3" not in html.lower()
    assert "拉沃尔杯 第二天 · 鲁德 / 兹维列夫 VS 布勃利克 / 中岛布兰登" in html
    assert re.search(r"\.band\{[^}]*padding:\d+px 70px 0", html)
    assert re.search(r"\.head\{[^}]*left:70px", html)
    assert html.count("网球时差 · 赛后开麦") == 1, "栏目名只许印一次"


def test_封面副标题和赛场之上是同一个格式():
    """`event_matchup_topic` 和 `reel_facts.cover_topic`（赛场之上 2026-09-26 那条全局
    规则）拼出来必须一字不差；赢家在前；没有对阵的退回 `push.summary`。"""
    import reel_facts

    for spec in _specs():
        got = clip.event_matchup_topic(spec)
        if not got:
            continue
        a, b = got.split(" · ", 1)[1].split(" VS ")
        want = reel_facts.cover_topic(spec["event"], {"matchup": [{"name": a}, {"name": b}]})
        assert got == want
        if spec.get("winner"):
            assert a.replace(" / ", "/") == spec["winner"], (spec["slug"], got)
    assert clip.cover_topic({"event": "2026 名人堂入选典礼", "push": {"summary": "费德勒入选"}},
                            {}) == "费德勒入选"
    assert clip.cover_topic({"event": "2026 美网 男单决赛", "winner": "乙",
                             "push": {"matchup": "甲 vs 乙"}}, {"topic": "手写的"}) == "手写的"


def test_封面标题一行写长了等比缩_不折行():
    """存量 106 条里 21 条按 74 写、到 94 放不下：整行等比缩到刚好 940px 以内。"""
    short = ["场边看比上场还紧张", "鲁德兹维列夫拿下双打"]
    long_ = ["大威拿第一个大满贯时 她还没出生", "「从小在电视上看她」"]
    assert clip._title_px(short) == 94
    px = clip._title_px(long_)
    assert px < 94
    assert max(clip._measure_at("head", px, ln) for ln in long_) <= clip._TITLE_W


def test_封面重点词只能一个_不许整行():
    """可选一个黄绿重点词（`cover.hook_accent`，和赛场之上同一个字段）：正好出现一次、
    不许是整行（R6：整行都亮就没有重点）。"""
    lines = ["阿加西：我怀疑他是AI", "中岛布兰登逆转门西克"]
    out = clip._title_html(lines, "AI")
    assert out.count("<span class=accent>AI</span>") == 1
    assert clip._title_html(lines, "") == "<div>阿加西：我怀疑他是AI</div><div>中岛布兰登逆转门西克</div>"
    for bad in ("不存在", "西", "中岛布兰登逆转门西克"):   # 0 次 / 2 次 / 整行
        with pytest.raises(SystemExit, match="hook_accent"):
            clip._title_html(lines, bad)


def test_封面重点词写错了在spec闸就红_不等出封面(tmp_path, monkeypatch):
    """评审 WP3 nit 5：`hook_accent` 原来只在渲封面（`_title_html`）时才查，写错了要等到
    出封面那一步。现在 `check_cover_hook` 坐在 `main()` 开头那排只读 spec 的闸里，
    排在联网取字幕、切行之前；存量 spec 一条都不许被它误伤。"""
    title = ["阿加西：我怀疑他是AI", "中岛布兰登逆转门西克"]
    for bad in ("不存在", "西", "中岛布兰登逆转门西克"):
        with pytest.raises(SystemExit, match="hook_accent"):
            clip.check_cover_hook({"slug": "t", "cover": {"title": title, "hook_accent": bad}})
    clip.check_cover_hook({"slug": "t", "cover": {"title": title, "hook_accent": "AI"}})
    clip.check_cover_hook({"slug": "t", "cover": {"title": title}})     # 没写＝零行为
    clip.check_cover_hook({"slug": "t"})
    for spec in _specs():
        clip.check_cover_hook(spec)

    # 真跑一遍 `main() --stage subs`（评审 WP3 修正轮 nit：源码里有这一行调用证明不了它
    # 真的跑、真的排在联网之前）。联网 / 下源片那几步换成桩：走到桩就说明闸没拦住，
    # 或者排在了它们后面。
    class _Reached(Exception):
        pass

    def _stub(name):
        def f(*a, **k):
            raise _Reached(name)
        return f

    for name in ("storyboard_sheet", "fetch_words", "segment", "write_ass"):
        monkeypatch.setattr(clip, name, _stub(name))
    monkeypatch.setattr(clip, "OUTDIR", tmp_path / "out")

    def run(accent: str) -> str:
        spec = _spec("ruud-zverev-laver-cup-2026-doubles-interview")
        spec["cover"]["hook_accent"] = accent
        p = tmp_path / f"{spec['slug']}.json"
        p.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["build_interview_clip.py", "--spec", str(p),
                                          "--stage", "subs"])
        try:
            clip.main()
        except _Reached as e:
            return f"走到了 {e}"
        except SystemExit as e:
            return f"拦下：{e}"
        return "跑完了"

    # 对照组：合规的重点词，前面那排闸全放行，一路走到第一个联网的步骤——桩是接上的
    assert run("紧张") == "走到了 storyboard_sheet"
    out = run("不存在")
    assert out.startswith("拦下") and "hook_accent" in out, (
        f"重点词写错了，`main()` 却{out}——它只读 spec，该在联网之前第一秒就报")


def test_封面文字列真渲出来和台头图标左对齐(tmp_path):
    """I11：原来 `.band` 是 64，标题墨迹比台头图标左偏 3~9px。量真渲的墨迹。"""
    import numpy as np
    from PIL import Image

    spec = {"slug": "t", "column": "赛后开麦", "event": "2026 拉沃尔杯 第二天",
            "winner": "甲", "push": {"matchup": "甲 vs 乙"},
            "cover": {"title": ["标题第一行字", "标题第二行字"], "sub": "副标题"}}
    out = clip.build_cover(spec, _frame(tmp_path), tmp_path / "c.png")
    a = np.asarray(Image.open(out).convert("L")).astype(int)
    icon_x = np.where(a[50:90, :200].max(0) > 150)[0][0]
    title_rows = a[980:1300, :300]
    title_x = np.where(title_rows.max(0) > 200)[0][0]
    # 实测：70 时标题墨迹 73、图标 72；退回 64 时标题 67——差 5px，肉眼就是「没对齐」
    assert abs(title_x - icon_x) <= 3, f"标题墨迹 x={title_x}，台头图标 x={icon_x}"


# ── I2 / I3：收尾卡 ─────────────────────────────────────────────────────────

def test_收尾卡台头就是封面那一块_没有青绿眉题():
    """I3 / Q1：品牌块用封面那一套（`_LOCKUP_CSS`），青绿斜体眉题删掉，
    一屏只剩黄绿一支强调色。"""
    spec = _spec("ruud-zverev-laver-cup-2026-doubles-interview")
    card = clip.takeaway_html(spec, "close")
    assert clip._LOCKUP_CSS in card and clip._LOCKUP_CSS in clip.cover_html(spec, ROOT / "assets/logo/brand/icon.png")
    assert "网球时差 · 赛后开麦" in card and "eyebrow" not in card
    assert "#74dcc3" not in card.lower()
    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8").lower()
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "74dcc3" not in code, "青绿那支（和它 BGR 写反的淡黄绿）不许回来"


_LINES_JS = """
(sel) => [...document.querySelectorAll(sel)].map(el => {
  const out = []; let top = null; let buf = '';
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    for (let i = 0; i < node.data.length; i++) {
      const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + 1);
      const rect = r.getClientRects()[0];
      if (!rect) { buf += node.data[i]; continue; }
      if (top !== null && Math.abs(rect.top - top) > 8) { out.push(buf); buf = ''; }
      top = rect.top; buf += node.data[i];
    }
  }
  out.push(buf); return out;
})
"""


def _card_lines(specs: list[dict]) -> dict[str, dict[str, list[list[str]]]]:
    """真渲每一张收尾卡，逐字取行（Range 的 client rect），按 slug 回每个块的行。"""
    from playwright.sync_api import sync_playwright

    got = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=clip._chromium(), args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": clip.CANVAS_W, "height": clip.CANVAS_H})
        first = clip.takeaway_html(specs[0], "close")
        pg.set_content(first)
        pg.wait_for_timeout(500)
        for spec in specs:
            html = clip.takeaway_html(spec, "close")
            pg.evaluate("h => { document.body.innerHTML = h; }", html.split("</style>", 1)[1])
            got[spec["slug"]] = {sel: pg.evaluate(_LINES_JS, sel)
                                 for sel in (".point", ".ask", ".lead", ".facts li")}
        b.close()
    return got


def test_收尾卡断行只在空格处_不劈词():
    """I2：Chromium 缺省在任意两个汉字之间断，已推的 ruud-zverev 收尾卡是
    「单打选手打双打 他说靠的是正／手」，chwalinska-mertens「滋／味」。
    `word-break:keep-all` 之后只在空格（文案里代替标点的那个）处断。

    全库每一张收尾卡真渲一遍：每一处断行都要落在空格上——除非一个子句本身比
    栏宽还长（`overflow-wrap:anywhere` 的兜底）。"""
    specs = [s for s in _specs() if (s.get("takeaway") or {}).get("close")]
    assert len(specs) > 80
    got = _card_lines(specs)

    rz = got["ruud-zverev-laver-cup-2026-doubles-interview"][".point"][0]
    assert [ln.strip() for ln in rz] == ["单打选手打双打", "他说靠的是正手"], rz
    cm = got["chwalinska-mertens-singapore-2026-qf-interview"][".point"][0]
    assert not any(ln.endswith("滋") for ln in cm), cm

    from PIL import ImageFont
    disp = ImageFont.truetype(clip._FONT_FILES["head"][0], 76)
    col = clip.CANVAS_W - clip._CARD_PAD_L - 150
    bad = []
    for slug, blocks in got.items():
        for sel, elems in blocks.items():
            for lines in elems:
                for prev, nxt in zip(lines, lines[1:]):
                    if prev.endswith((" ", "，", "。", "？", "！", "、", "：", "；", "」")) \
                            or nxt.startswith(" "):
                        continue
                    chunk = (prev.split(" ")[-1] + nxt.split(" ")[0])
                    if sel == ".point" and disp.getlength(chunk) > col:
                        continue          # 一个子句本身比栏宽，兜底断是对的
                    bad.append(f"{slug} {sel}: 「{prev}／{nxt}」")
    assert not bad, "收尾卡把词劈开了：\n" + "\n".join(bad[:20])


# ── Q4：接缝溶解 ───────────────────────────────────────────────────────────

def test_接缝计划_正文中间直拷_静图整段进接缝块():
    """纯函数：按关键帧把各段排成「接缝块 / 直拷」。"""
    fps = clip._FPS
    parts = [(50, [0.0]),                                   # 封面 2.0s
             (301, [0.0, 1.0, 6.84, 11.0]),                 # 冷开场 12.04s
             (1751, [0.0, 1.0, 11.0, 21.0, 61.0, 69.0]),    # 正文 70.04s
             (155, [0.0]),                                  # 收尾卡
             (105, [0.0])]                                  # 片尾
    plan = clip.seam_plan(parts)
    assert plan == [("run", 0, 0, 50), ("run", 1, 0, fps), ("copy", 1, fps, 275),
                    ("run", 1, 275, 301), ("run", 2, 0, fps), ("copy", 2, fps, 1725),
                    ("run", 2, 1725, 1751), ("run", 3, 0, 155), ("run", 4, 0, 105)]
    copied = sum(f1 - f0 for k, _, f0, f1 in plan if k == "copy")
    assert copied / 1751 > 0.9, "正文的绝大部分必须直拷"
    # 切不开的长段（没有强制关键帧）整段进块——正确但贵，所以编码时一定要加
    assert clip.seam_plan([(50, [0.0]), (1751, [0.0, 10.0, 20.0])]) == [
        ("run", 0, 0, 50), ("run", 1, 0, 1751)]
    assert clip._seam_keyframes(214.37) == ["-force_key_frames", "1,213.370"]
    assert clip._seam_keyframes(2.0) == []
    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    assert src.count("*_seam_keyframes(dur)") == 2, "正文和冷开场/捧杯两处编码都要强制关键帧"
    assert src.count("*_seam_keyframes(secs)") == 1, "静图（收尾卡）也要，只重编贴着接缝那一秒"


def _clip(dest: Path, dur: float, *, still: bool = False, tone: int = 0,
          delay: float = 0.0, hue: int = 0) -> Path:
    src = (f"color=c=0x{40 + hue:02x}5060:s=320x240:d={dur}:r=25" if still
           else f"testsrc2=s=320x240:d={dur}:r=25")
    audio = (f"sine=f={tone}:d={dur}" if tone else f"anullsrc=r=48000:cl=stereo:d={dur}")
    af = f"adelay={round(delay * 1000)}:all=1,apad=whole_dur={dur}" if delay else "anull"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src,
         "-f", "lavfi", "-i", audio, "-af", af, "-t", str(dur),
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
         *clip._seam_keyframes(dur), "-r", "25", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", str(dest)],
        check=True, timeout=120)
    return dest


def _md5s(path: Path) -> list[str]:
    out = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-map", "0:v:0",
                          "-f", "framemd5", "-"], capture_output=True, text=True).stdout
    return [ln.rsplit(",", 1)[-1].strip() for ln in out.splitlines() if ln and ln[0] != "#"]


def _dur(path: Path, stream: str) -> float:
    return float(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries",
         "stream=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True).stdout.strip())


def test_接缝溶解_正文中间逐帧不变_音画等长_没有黑帧(tmp_path):
    """Q4：封面→正文→收尾卡→片尾四个接缝溶解，正文中间那一大段直拷。

    - 总长 ＝ Σ 各段 − 接缝数 × 重叠（画面和声音逐采样等长）
    - 正文中间那段**解码出来逐帧 md5 相同**——证明它没被重编
    - 接缝处亮度分几帧走完（不是一帧跳过去），中间没有一帧比两边都暗（没有黑帧）
    """
    import numpy as np

    parts = [_clip(tmp_path / "_cover.mp4", 2.0, still=True, hue=0),
             _clip(tmp_path / "_body.mp4", 8.0, tone=440),
             _clip(tmp_path / "_card.mp4", 3.0, still=True, tone=660, delay=0.2, hue=90),
             _clip(tmp_path / "_outro.mp4", 2.0, still=True, hue=160)]
    out = clip.dissolve_concat(parts, tmp_path / "film.mp4")
    lengths = [clip._probe_frames(p)[0] / clip._FPS for p in parts]
    want = sum(lengths) - 3 * clip._OVERLAP_S
    v, a = _dur(out, "v:0"), _dur(out, "a:0")
    assert abs(v - want) < 0.001 and abs(a - want) < 0.001, (v, a, want)
    assert not (tmp_path / "_seams").exists(), "中间件要清干净"

    body, film = _md5s(parts[1]), _md5s(out)
    mid = body[clip._FPS: len(body) - clip._FPS]
    start = 2 * clip._FPS - clip._OVERLAP_FRAMES + clip._FPS
    assert film[start:start + len(mid)] == mid, "正文中间那段被重编了（或者位置错了一帧）"

    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(out), "-vf",
                          "format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, 240, 320).astype(float)
    luma = frames.mean((1, 2))
    jump = np.abs(np.diff(frames, axis=0)).mean((1, 2))
    seam = round((2.0 - clip._OVERLAP_S) * clip._FPS)      # 封面 → 正文
    window = jump[seam - 1:seam + clip._OVERLAP_FRAMES + 1]
    assert (window > 1).sum() >= clip._OVERLAP_FRAMES - 1, f"接缝没溶解开：{window}"
    for s in range(1, len(luma) - 1):
        assert luma[s] >= min(luma[s - 1], luma[s + 1]) - 8, f"第 {s} 帧比两边都暗——有黑帧"


def _render_stubbed(tmp_path: Path, monkeypatch, *, fail_dissolve: bool) -> dict:
    """真跑一遍 `render()` 的拼接那一段：正文 8 秒 ＋ 片尾 2 秒（都带 `_seam_keyframes`），
    只打桩跑不动的那几件事（下源片、正文那趟 filter_complex、顶栏像素闸）。
    和 `test_interview_film_seconds` 同一个做法。回 `render.json`。"""
    outdir = tmp_path / "out"
    outdir.mkdir()
    monkeypatch.setattr(clip, "check_takeaway", lambda spec: None)
    monkeypatch.setattr(clip, "yt_download",
                        lambda *a, **k: _clip(outdir / "source.mp4", 1.0))
    monkeypatch.setattr(clip, "_takeaway_segments", lambda *a, **k: [])
    monkeypatch.setattr(clip, "assert_rendered_topbar", lambda *a, **k: None)
    monkeypatch.setattr(clip, "assert_topbar_font_log", lambda *a, **k: None)
    monkeypatch.setattr(clip, "_build_outro",
                        lambda d: _clip(d / "_outro.mp4", 2.0, still=True, hue=160))
    if fail_dissolve:
        def boom(parts, out):
            raise SystemExit("_body.mp4 在关键帧处直拷切开之后第 1 截帧数不对（要 150）")
        monkeypatch.setattr(clip, "dissolve_concat", boom)
    real_run = subprocess.run

    def fake_run(cmd, *a, **k):
        # 只替正文那一趟编码和顶栏预检（输出是 `_body.mp4` / `_topbar_probe.mp4`）；
        # 接缝那几趟也带 filter_complex，照常真跑
        name = Path(str(cmd[-1])).name
        if cmd[0] == "ffmpeg" and "-filter_complex" in cmd and name in {
                "_body.mp4", "_topbar_probe.mp4"}:
            if name == "_body.mp4":
                _clip(outdir / "_body.mp4", 8.0, tone=440)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(clip.subprocess, "run", fake_run)
    (outdir / "render.json").write_text('{"video_url": "https://example.invalid/v.mp4"}\n',
                                        encoding="utf-8")
    spec = {"slug": "demo", "url": "https://example.invalid/x", "start": 10.0, "end": 18.0,
            "zh": [], "en": []}
    assert clip.render(spec, outdir / "subs.ass", outdir).is_file()
    return json.loads((outdir / "render.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("fail_dissolve", [False, True], ids=["溶解", "退回硬切"])
def test_接缝是溶解还是退回了硬切_记进render_json(tmp_path, monkeypatch, capsys, fail_dissolve):
    """评审 WP3 nit 2：溶解失败退回硬切，原来只在日志里打一行 `[拼接] ⚠️`——没有哪道闸
    看得见。现在 `render()` 把接法写进 `render.json` 的 `seams`，`check_interview_landed`
    读它、退回硬切时点名（片子照样能发，不计不合格）。合并写，不覆盖 `video_url`。"""
    data = _render_stubbed(tmp_path, monkeypatch, fail_dissolve=fail_dissolve)
    seams = data["seams"]
    assert data["video_url"] == "https://example.invalid/v.mp4", "把 render.json 覆盖了"
    assert seams["count"] == 1
    sys.path.insert(0, str(ROOT / "tools"))
    import check_interview_landed as ci

    line = ci.report_seams(data)
    if fail_dissolve:
        assert seams["transition"] == "hard_cut", seams
        assert "帧数不对" in seams["fallback_reason"]
        assert line.startswith("[注意]") and "硬切" in line and "帧数不对" in line
    else:
        assert seams["transition"] == "dissolve", seams
        assert line.startswith("[ok]")
    assert "[跳过]" in ci.report_seams({}), "老片子没记接缝要说「没记」，不许当成 ok"


def test_收尾卡口播等溶解走完再开口(tmp_path):
    """卡是溶解着进来的：前 `_OVERLAP_S` 秒只有画面，口播从那之后才开口。"""
    import numpy as np
    from PIL import Image

    png = tmp_path / "c.png"
    Image.new("RGB", (320, 240), (20, 40, 30)).save(png)
    tone = tmp_path / "v.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "sine=f=500:d=1", str(tone)], check=True)
    seg = clip._still_segment(png, 1.6, tmp_path / "c.mp4", tone, audio_delay=clip._OVERLAP_S)
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(seg), "-ac", "1",
                          "-ar", "48000", "-f", "s16le", "-"], capture_output=True).stdout
    pcm = np.abs(np.frombuffer(raw, np.int16))
    onset = np.argmax(pcm > 1000) / 48000
    assert clip._OVERLAP_S - 0.02 <= onset <= clip._OVERLAP_S + 0.06, onset
