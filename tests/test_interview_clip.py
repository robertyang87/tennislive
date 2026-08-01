"""「赛后开麦」双语字幕片：转写这一步的判据。

这条线发的是**英语学习素材**，所以发错的英文比没有更糟。而唯一现成的转写
（YouTube 自动字幕）实测错得不轻——人名全错、整句语法不成立、介词听反。
所以这里的每条测试都在钉同一件事：**一份 ASR 不算数，必须有第二个源**。

两个源各有各的边界，别互相顶替：

- `verify_transcript` 跑第二份 ASR（faster-whisper）。覆盖全段，
  **但只有 runner 上跑得动**——沙箱的 IP 被 YouTube 挡了，音频都下不到
- `check_human_quote` 比赛事官网战报里的**人工引语**。不联网、本地就能跑，
  **但只覆盖记者抄走的那几句**
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tools.build_interview_clip import (
    CANVAS_H,
    CAPTION_GAP_SECS,
    ROOT,
    caption_gaps,
    check_human_quote,
    gap_key,
    header_lines,
    review_sheet,
    segment,
    write_ass,
    zh_problems,
    _BAND_TOP,
    _EN_TOP,
    _FONT_SIZE,
    _LINE_PX,
    _ZH_TOP,
    _ts,
    _NO_TAIL,
    _SENT_END,
    _FILLER,
    _bare,
    _caption_spans,
    _en_width,
    _norm_en,
    _quote_span,
    _unresolved_gaps,
    _unresolved_suspects,
    _yt_at,
)

SPECS = ROOT / "specs" / "interviews"


def _specs() -> list[Path]:
    return sorted(SPECS.glob("*.json")) if SPECS.exists() else []


def _lines(en: list[str]) -> list[dict]:
    return [{"a": i * 3.0, "b": i * 3.0 + 2.8, "en": t} for i, t in enumerate(en)]


# ---------------------------------------------------------------- 人工引语

def test_人工引语能抓出ASR听错的介词(tmp_path):
    """这是真实踩到的那一处，反向验证过：去掉 en_fixed 这条测试立刻红。

    ASR 听成 `respect **to** her`，WTA 战报里的人工引语写的是
    `respect **for** her`。一个介词，意思不一样——而它长得完全不像错。
    """
    spec = {
        "slug": "t",
        "human_quote": {
            "url": "https://example.invalid/report",
            "text": "There's so much respect for her for that, and I'm really excited.",
        },
    }
    bad = _lines(["uh there's so much respect to her for that and I'm really excited."])
    with pytest.raises(SystemExit) as e:
        check_human_quote(spec, bad, tmp_path)
    assert "`to` → `for`" in str(e.value)

    good = _lines(["uh there's so much respect for her for that and I'm really excited."])
    assert check_human_quote(spec, good, tmp_path) is not None


def test_记者删掉的词不算分歧(tmp_path):
    """印出来的引语本来就是片段：引入语、口头语会被整段拿掉。

    **删不能设闸**——引语里少一个词只说明记者删了，推不出 ASR 错在哪。
    但要在报告里露出来，删的是口头语还是实词得分得清。
    """
    spec = {"slug": "t", "human_quote": {"text": "She is such an accomplished player."}}
    # `uh` 要摆在引语覆盖到的区间**里面**——摆在末尾会落到区间之外，
    # 走的是「前后不算分歧」那条路，验不到口头语这一档。
    lines = _lines(["Yes, she is of course such an uh accomplished player."])
    path = check_human_quote(spec, lines, tmp_path)
    body = path.read_text(encoding="utf-8")
    assert "of course`（实词）" in body
    assert "uh`（口头语）" in body


def test_引语区间之外的话不算分歧(tmp_path):
    """引语只抄了采访的一小段，前后几十句不能被算成「对不上」。"""
    spec = {"slug": "t", "human_quote": {"text": "I am really excited."}}
    lines = _lines([
        "Well, Alex congratulations through to the semifinal here.",
        "I'm really excited.",
        "Ladies and gentlemen, through the semifinals, Alexandra Eala",
    ])
    assert check_human_quote(spec, lines, tmp_path) is not None


def test_缩写两边都展开再比(tmp_path):
    """战报写 `She's`，ASR 听成 `she is`——那不是分歧，是排版习惯。"""
    assert _norm_en("She's") == _norm_en("she is")
    assert _norm_en("I haven't") == _norm_en("i have not")
    spec = {"slug": "t", "human_quote": {"text": "She's made waves on and off the court."}}
    assert check_human_quote(spec, _lines(
        ["she is made waves on and off the court"]), tmp_path) is not None


def test_口头语表里不许混进实词():
    """判据宁可窄，不可宽。

    `well` / `so` / `like` / `right` 塞进来看着像口头语，但它们同样能是实词——
    一旦放进去，「记者删掉的是口头语」这句话就不成立了，报告里的分类跟着失真。
    **扩大化的判据不吭声**：它不会告诉你拦错了。
    """
    assert _FILLER <= {"uh", "um", "erm", "er", "ah", "mm", "hmm", "mhm"}
    for w in ("well", "so", "like", "right", "now", "yeah", "no", "not"):
        assert w not in _FILLER, f"{w} 是实词，不能当口头语删掉"


def test_引语一个词都对不上要报错而不是默默放过(tmp_path):
    """**空结果先自证是真空**：对不上零处和「完全没比」长得一模一样。

    抄错了场次、抄的是发布会而不是场上采访——这两种都会得到零命中，
    而零命中如果被读成「没有分歧」，这道闸就等于没装。
    """
    spec = {"slug": "t", "human_quote": {"text": "zzz qqq xxx"}}
    with pytest.raises(SystemExit) as e:
        check_human_quote(spec, _lines(["completely different words here"]), tmp_path)
    assert "一个词都对不上" in str(e.value)


def test_没写人工引语的spec直接跳过不报错(tmp_path):
    """引语是加料不是必需品——不是每场都有战报抄原话。"""
    assert check_human_quote({"slug": "t"}, _lines(["anything"]), tmp_path) is None


# ---------------------------------------------------------------- 断行

def _words(text: str, step: float = 0.4) -> list[tuple[float, str]]:
    return [(i * step, w) for i, w in enumerate(text.split())]


def test_不许把词组劈成两半():
    """账号所有者：「同一个词或者是意思或者一句话，不要换行或者换页。」

    原来是「数满 62 个字符就断」，于是满篇 `Elina hit some good ／ shots.`、
    `I think she's ／ made waves`、`thank all your ／ Filipino fans`——
    字符数对，词组被劈成两半。这条钉的就是那几个真实的失败例。
    """
    text = ("I think I was playing really well and of course Elina hit some good "
            "shots. She was being aggressive, especially in that second set.")
    lines = segment(_words(text), 0, 999)
    joined = [ln["en"] for ln in lines]
    for pair in ("good shots", "was playing", "second set"):
        assert any(pair in ln for ln in joined), f"「{pair}」被劈开了：{joined}"


def test_一行不许收在虚词上():
    """断点在短语开头**还不够**，上一行还得收得住。

    只管「起得来」会切出 `and you beat your ／ same opponent`——断点确实在
    短语开头（`same` 前面），可上一行吊在物主代词上，读起来照样是半截。
    """
    text = ("Well, Alex congratulations through to the semifinal here. "
            "The crazy thing is the last semi-final you made was not that long "
            "ago in Berlin and you beat your same opponent the same score line.")
    lines = segment(_words(text), 0, 999)
    for i, ln in enumerate(lines[:-1]):
        if ln["en"].rstrip().endswith(_SENT_END):
            continue        # 句子到此为止，收在哪个词上都不算吊
        assert _bare(ln["en"].split()[-1]) not in _NO_TAIL, \
            f"第 {i+1} 行吊在虚词上：…{ln['en'][-28:]}"


def test_行宽按量出来的算不按字符数():
    """**超宽不报错，只是被 libass 悄悄折成两行**，折在哪儿没人管。

    这是同一条规矩的隐形版：原来 37 行里有 22 行超宽，看上去一切正常。
    所以宽度得在切行那一步就卡住，不能指望渲染层。
    """
    text = ("about kind of what it takes to sustain this level, both physically "
            "and mentally, and just the effort you need to have to hang with "
            "these top players and stay there.")
    for ln in segment(_words(text), 0, 999):
        assert _en_width(ln["en"]) <= _LINE_PX, \
            f"{_en_width(ln['en']):.0f}px 超过 {_LINE_PX}：{ln['en']}"


def test_两句话不许压在同一行():
    """一句一行，停顿靠换行表达。

    试过「极短的句子并进上一行」，切出来是
    `through to the semifinal here. The crazy Yes.`——没劈开词组，
    却把两个意思压在了一行，正是同一条规矩的另一面。
    **例外只有一个**：短到读不完的句子（`Yeah.` 只停 0.32 秒）并进**下一句**，
    并的是两个完整的句子，不会把谁劈开。
    """
    text = "through to the semifinal here. The crazy Yes. round of applause."
    for ln in segment(_words(text, step=1.5), 0, 999):
        assert ln["en"].rstrip().rstrip(".?!").count(".") == 0, \
            f"两句压在一行：{ln['en']}"


def test_中文那行也要不超宽不吊在虚词上():
    """英文的两条规矩，中文一字不差地也要守——它们是同一件事。

    ⚠️ 判据只收**单字虚词**，而且只在这一行不是句尾时才算：
    `身体上和心理上都是`（都是＝完整的谓语）、`你也是看着她长大的`
    （是…的 结构）都以虚词收尾却是完整的。**扩大化的判据不吭声**。
    """
    lines = [{"en": "and just the effort you need"}, {"en": "to hang with them."}]
    assert zh_problems(lines, ["还有你必须付出的努力", "才能跟他们周旋"]) == []
    assert zh_problems(lines, ["还有你必须付出的", "才能跟他们周旋"])
    assert zh_problems(lines, ["还" * 60, "才能跟他们周旋"])
    # 句尾那行收在「的」上不算吊
    assert zh_problems([{"en": "watching her."}], ["我想你也是看着她长大的"]) == []


# ---------------------------------------------------------------- 核对表 / 挂账

def test_可疑行只能靠改或听销账():
    """**让 `suspect` 是判据，不是注释。**

    写成散文注（「#2 #5 #13 可疑」）的坏处是它不吭声：改完忘了删，下一个人
    读到的是过时的清单；一条都没改，`transcript_verified` 照样打得上。
    所以销账只有两条路——改（`en_fixed`）或听过确认没问题（`suspect_ok`）。
    """
    spec = {"suspect": {"2": "a", "5": "b", "13": "c"},
            "en_fixed": {"5": "fixed"}, "suspect_ok": {"13": "听过，本来就对"}}
    assert _unresolved_suspects(spec) == ["2"]
    spec["suspect_ok"]["2"] = "也听过了"
    assert _unresolved_suspects(spec) == []


def test_跳转链接的秒数必须是整数():
    """YouTube 的 `&t=` **不吃小数**——带小数它整个参数忽略，点过去跳回开头。

    而字幕行的起点天然带小数（`297.4`）。这条拦的就是顺手把浮点塞进去。
    """
    assert _yt_at("https://www.youtube.com/watch?v=AiBTDJd_ekQ", 297.4) == \
        "https://youtu.be/AiBTDJd_ekQ?t=297"
    assert "." not in _yt_at("https://youtu.be/abc123", 12.9).split("t=")[-1]


def test_核对表把人工引语覆盖到的行圈出来(tmp_path):
    """引语只覆盖一段，**表上要看得出覆盖到哪儿为止**。

    看不出的话，「有第二个源」这句话会被读成整段都验过——而实际上只有
    记者抄走的那几句验过，其余仍然是一份 ASR 说了算。
    """
    lines = _lines(["aaa bbb ccc", "ddd eee fff", "ggg hhh iii", "jjj kkk lll"])
    spec = {"slug": "t", "url": "https://youtu.be/x", "start": 0.0, "end": 12.0,
            "zh": ["一", "二", "三", "四"],
            "human_quote": {"text": "ddd eee fff ggg hhh iii"}}
    assert _quote_span(spec, lines) == (2, 3)
    body = review_sheet(spec, lines, tmp_path).read_text(encoding="utf-8")
    rows = [r for r in body.splitlines() if r.startswith("| ") and "▶" in r]
    assert "✅ 人工引语" not in rows[0] and "✅ 人工引语" in rows[1]
    assert "✅ 人工引语" in rows[2] and "✅ 人工引语" not in rows[3]


def test_核对表把还欠着的单独列出来(tmp_path):
    """**检查工具要把不合格的也列出来。** 只在全绿时出声的表证明不了它看过。"""
    lines = _lines(["one two", "three four", "five six"])
    spec = {"slug": "t", "url": "https://youtu.be/x", "start": 0.0, "end": 9.0,
            "zh": ["一", "二", "三"], "suspect": {"2": "这句听着不对"}}
    body = review_sheet(spec, lines, tmp_path).read_text(encoding="utf-8")
    assert "## 还欠着的" in body
    assert "**#2**" in body and "这句听着不对" in body


# ------------------------------------------------------- 自动字幕的空档

def _cap(tmp_path: Path, events: list[tuple[float, float, str]]) -> Path:
    """写一份 json3，`events` 是 (起, 止, 文本)。"""
    (tmp_path / "cap_x.json3").write_text(json.dumps({"events": [
        {"tStartMs": int(a * 1000), "dDurationMs": int((b - a) * 1000),
         "segs": [{"utf8": t}]} for a, b, t in events]}), encoding="utf-8")
    return tmp_path


def test_源什么都没说的那几秒要被认出来(tmp_path):
    """**这是伊埃拉那条漏掉的 3.2 秒。**

    两道旧闸都拦不住它：`verify_transcript` 比的是两份 ASR 的词对不对得上，
    `check_human_quote` 比的是战报抄走的那几句——**没有词就没有分歧**，
    空白反而让分歧率更好看。所以要单独查「源什么都没说」。
    """
    _cap(tmp_path, [(0.0, 5.0, "hello there"), (8.4, 12.0, "and we are back")])
    spec = {"start": 0.0, "end": 12.0}
    assert caption_gaps(spec, tmp_path) == [(5.0, 8.4)]


def test_掌声不算空档(tmp_path):
    """`[applause]` / `[cheering]` 是**源自己出的声**：「我听见了，只是不是人话」。

    切行时 `_NOISE` 把它们丢掉是对的（那不是台词），但在空档这条判据里
    它们必须算数——否则每一次鼓掌都会被报成漏词，而**一个天天误报的检查
    等于没有检查**，下一个人就会开始无脑销账。

    数是真的：伊埃拉那条 302.67→304.58 那 1.9 秒两头正好夹着 `[cheering]`
    和 `[applause]`。
    """
    _cap(tmp_path, [(0.0, 5.0, "thank you"), (5.0, 9.0, "[cheering]"),
                    (9.0, 12.0, "[applause]"), (12.0, 15.0, "okay")])
    assert caption_gaps({"start": 0.0, "end": 15.0}, tmp_path) == []


def test_空档只看采访区间里的(tmp_path):
    """集锦前面那十几分钟是打球，没有台词很正常——报出来只是噪音。"""
    _cap(tmp_path, [(0.0, 2.0, "match point"), (100.0, 104.0, "congratulations"),
                    (110.0, 114.0, "thank you")])
    assert caption_gaps({"start": 99.0, "end": 114.0}, tmp_path) == [(104.0, 110.0)]


def test_短过阈值的抖动不报(tmp_path):
    """事件之间零点几秒的缝是编码抖动，不是漏。阈值是从真实分布量出来的。"""
    _cap(tmp_path, [(0.0, 5.0, "a"), (5.0 + CAPTION_GAP_SECS - 0.1, 9.0, "b")])
    assert caption_gaps({"start": 0.0, "end": 9.0}, tmp_path) == []
    _cap(tmp_path, [(0.0, 5.0, "a"), (5.0 + CAPTION_GAP_SECS + 0.1, 9.0, "b")])
    assert len(caption_gaps({"start": 0.0, "end": 9.0}, tmp_path)) == 1


def test_重叠的滚动字幕要先合并(tmp_path):
    """YouTube 的自动字幕是**滚动窗口**，事件互相重叠、起点不单调。

    不合并就会把「上一条还没结束、下一条已经开始」算成负空档，或者更糟——
    按事件顺序两两相减，中间夹一条长事件时算出一个凭空的大空档。
    """
    _cap(tmp_path, [(0.0, 6.0, "one two three"), (2.0, 8.0, "three four five"),
                    (4.0, 10.0, "five six seven")])
    assert _caption_spans(tmp_path) == [[0.0, 10.0]]
    assert caption_gaps({"start": 0.0, "end": 10.0}, tmp_path) == []


def test_空档要销账才放行():
    """和 `suspect` 同一个形状：**结论必须留在 spec 里**，不能靠人记得。

    ⚠️ 销账的意思是「人听过并作出了决定」，**不是「这里没问题」**——伊埃拉
    那条销账的值写的就是「真漏了」。把一个已知的洞抹平比留着它更糟。
    """
    gaps = [(431.6, 434.9), (12.0, 15.0)]
    assert _unresolved_gaps({}, gaps) == gaps
    spec = {"caption_gaps_ok": {"431.6-434.9": "真漏了，她在说菲律宾语"}}
    assert _unresolved_gaps(spec, gaps) == [(12.0, 15.0)]


def test_空档的键按秒写不按序号():
    """按序号写的话，前面多出一个空档就全体错位，**销的账会落到别的空档上**——
    而且它不吭声：数量对得上，内容全串了。"""
    assert gap_key(431.64, 434.88) == "431.6-434.9"
    assert gap_key(5.0, 8.4) == "5.0-8.4"


def test_核对表把空档单独列一节(tmp_path):
    """逐行那张表走的是「源说了什么」，**走不到「源什么都没说」的地方**——
    那几秒在表里根本不占一行，翻一百遍也看不见。所以要单独列。"""
    _cap(tmp_path, [(0.0, 3.0, "one"), (9.0, 12.0, "two")])
    lines = _lines(["one", "two"])
    spec = {"slug": "t", "url": "https://youtu.be/x", "start": 0.0, "end": 12.0,
            "zh": ["一", "二"]}
    body = review_sheet(spec, lines, tmp_path).read_text(encoding="utf-8")
    assert "## 自动字幕的空档" in body
    assert "**还没销账**" in body and "3.0–9.0 秒" in body
    spec["caption_gaps_ok"] = {"3.0-9.0": "听过了：全场欢呼，没人说话"}
    body = review_sheet(spec, lines, tmp_path).read_text(encoding="utf-8")
    assert "**还没销账**" not in body and "全场欢呼" in body


def test_探空档不许再加一个多语种模型():
    """账号所有者定的：**不要多语种。**

    机器分不出「没人说话」和「不是英语」——`small.en` 两种情况都给空白。
    再加一个大模型也只是把一个需要人复核的空白换成一个需要人复核的猜测，
    却要多下几百 MB、每趟多跑一遍。

    这条**拦的不是手滑**，是下一次有人重新论证「多语种模型能听出来」。
    源码文本断言在这儿是对的用法：它防的是「这条规矩别被删掉」，
    不是「这个功能能跑」（后者由下面那条行为测试管）。
    """
    import inspect

    from tools.build_interview_clip import probe_gap_speech

    src = inspect.getsource(probe_gap_speech)
    assert "WhisperModel" not in src, "探空档又去加载模型了——不要多语种"
    assert "subprocess" not in src, "探空档又去切音频了——它只该摊已经跑完的那份结果"


def test_探空档两种结果都要出声(tmp_path, capsys):
    """**「没听出来」不等于「没有」，报告里必须分开写。**

    这是这一整条线上最贵的那个混淆：`small.en` 对着非英语给空白，和
    「这几秒真没人说话」长得一模一样。报告要是只写一句「无」，
    下一个人读到的就是「确认过了，没人说话」——而那正是漏掉的那 3.2 秒。
    """
    from tools.build_interview_clip import probe_gap_speech

    spec = {"slug": "t", "url": "https://youtu.be/x", "start": 0.0, "end": 20.0}
    gaps = [(3.0, 6.0), (10.0, 13.0)]
    words = [(4.0, "thank"), (4.4, "you"), (4.8, "everyone")]
    body = probe_gap_speech(spec, gaps, words, tmp_path).read_text(encoding="utf-8")
    assert "thank you everyone" in body and "en_fixed" in body
    assert "**什么都没有**" in body
    # 空白那一档必须把两种可能都摆出来，不能只写「无」
    assert "没人说话" in body and "不是英语" in body


def test_没有空档的时候也要出声(capsys, tmp_path):
    """只在发现问题时出声的检查，没法证明它真的看过。"""
    from tools.build_interview_clip import probe_gap_speech

    assert probe_gap_speech({"slug": "t", "start": 0.0}, [], [], tmp_path) is None
    assert "没有空档" in capsys.readouterr().out


def test_真实那条片子只报出该报的那一处():
    """**拿存量验一遍**，别只用合成数据——合成数据验的是「实现符合我的假设」。

    伊埃拉那条的缓存字幕就在仓库里。整段 146 秒里只有一处空档，就是她对
    菲律宾球迷说话的那 3.2 秒；1.9 秒那个掌声空档不许被报出来。
    """
    spec_path = SPECS / "eala-svitolina-dc2026-qf.json"
    outdir = ROOT / "output" / "interviews" / "eala-svitolina-dc2026-qf"
    if not spec_path.exists() or not list(outdir.glob("cap_*.json3")):
        pytest.skip("这条片子的缓存字幕不在（sparse checkout）")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert caption_gaps(spec, outdir) == [(431.64, 434.88)]
    assert _unresolved_gaps(spec, caption_gaps(spec, outdir)) == []


# ---------------------------------------------------------------- 版式

# 墨迹相对字号的比例，**烧真帧量出来的**（不是字体表里的 ascent/descent）：
# 40/48 那版量到 EN 墨高 29、ZH 墨高 31，46/62 这版量到 34 / 40。
_INK_TOP = 0.21                      # 墨迹上沿离 MarginV 多远
_INK_H = {"en": 0.74, "zh": 0.645}   # 墨高


def _ink(kind: str, margin_v: int) -> tuple[float, float]:
    fs = _FONT_SIZE[kind]
    top = margin_v + _INK_TOP * fs
    return top, top + _INK_H[kind] * fs


def test_字幕这一对要落在字幕带的正中():
    """账号所有者：「下面字幕空间太大」。

    **不是带子太宽，是字全堆在上半截。** 原来 `_EN_TOP` 写成「视频下沿 + 100」，
    墨迹落在 1069–1147：上面空 109，**下面空 293**——同一条 480px 的带子，
    一头挤一头空，看起来就是「下面一大片没用」。

    这条拦的是**改了字号却没重新算位置**：字号一变，墨块高度跟着变，
    还钉在老的 `_EN_TOP` 上就会重新偏到一头去，而**它不报错**。
    """
    en_top, en_bot = _ink("en", _EN_TOP)
    zh_top, zh_bot = _ink("zh", _ZH_TOP)
    above, below = en_top - _BAND_TOP, CANVAS_H - zh_bot
    assert abs(above - below) <= 40, (
        f"字幕没落在带子中间：上空 {above:.0f}px、下空 {below:.0f}px。"
        f"改过字号就要重新量 `_EN_TOP`（当前 {_EN_TOP}）。")
    assert en_bot < zh_top, "英文和中文的墨迹叠在一起了"


def test_两行之间的空白要跟着字号重新量():
    """`_ZH_GAP` 是**墨迹间距**，不是字号的比例——40/48 下是 47，46/62 下是 53。

    按比例推会得到 47×62/48 = 61，渲出来两行就散开了。目标区间是
    「中文墨高的 0.45–0.70 倍」，量出来 0.56 正好（43 挤、51 松，比过三档）。
    """
    _, en_bot = _ink("en", _EN_TOP)
    zh_top, zh_bot = _ink("zh", _ZH_TOP)
    white = zh_top - en_bot
    ratio = white / (zh_bot - zh_top)
    assert 0.45 <= ratio <= 0.70, (
        f"两行之间空白 {white:.0f}px ＝ 中文墨高的 {ratio:.2f} 倍，"
        "超出 0.45–0.70。改字号要重新量 `_ZH_GAP`。")


def test_中文字号不许大到让行放不下():
    """中文那侧的天花板是 952px 可用宽。

    **68 号就有行超出**（伊埃拉那条最宽的一行 967px），所以 64 是上限。
    这条拦的是「中文那侧几乎免费」被读成「随便调」。
    """
    assert _FONT_SIZE["zh"] <= 64, (
        f"中文字号 {_FONT_SIZE['zh']} 超过 64——952px 的行宽装不下，"
        "写稿的人会被逼着把句子切碎。")


def test_顶栏说清这是哪一场():
    """账号所有者：「顶部文字说明当前是什么比赛的赛后采访，不然好多人不知道背景」。

    刷到中段的人没看过封面（而封面只有 1.8 秒），画面上只有一个人在说话。
    """
    spec = {"slug": "t", "event": "2026 华盛顿 WTA500 女单八强",
            "push": {"matchup": "伊埃拉 vs 斯维托丽娜"}}
    a, b = header_lines(spec)
    assert a == "2026 华盛顿 WTA500 女单八强"
    assert "伊埃拉 vs 斯维托丽娜" in b and "赛后" in b


def test_顶栏不写比分():
    """**`matchup` 的顺序不保证是胜者在前。**

    `@wta` 的标题就按签位排——我照着推过一次「标题里在前的是赢家」，推错了
    （`Zheng Qinwen vs. Clara Tauson` 赢的是 Tauson）。把比分插进两个名字
    中间等于用词序断言谁赢了，而这个断言站不住。
    """
    spec = {"slug": "t", "event": "2026 华盛顿 WTA500 女单八强",
            "push": {"matchup": "伊埃拉 vs 斯维托丽娜", "score": "6-3 6-4"}}
    assert all("6-3" not in line and "6-4" not in line for line in header_lines(spec))


def test_顶栏缺字段要报错而不是印半句():
    """空着比错着更难发现：顶栏印出「 · 赛后场上采访」，看着像设计如此。"""
    for spec in ({"slug": "t", "push": {"matchup": "甲 vs 乙"}},
                 {"slug": "t", "event": "某站某轮"}):
        with pytest.raises(SystemExit):
            header_lines(spec)


def test_顶栏从头挂到尾(tmp_path):
    """顶栏不是开场卡：**整条片子任何一帧都要能回答「这是哪一场」。**"""
    lines = _lines(["one two", "three four"])
    spec = {"slug": "t", "event": "某站八强", "push": {"matchup": "甲 vs 乙"},
            "zh": ["一", "二"]}
    path = tmp_path / "t.ass"
    write_ass(lines, spec["zh"], 0.0, path, spec)
    body = path.read_text(encoding="utf-8")
    head = [r for r in body.splitlines() if r.startswith("Dialogue") and "HEAD" in r]
    assert len(head) == 2, "顶栏该有两行"
    assert all(",0:00:00.00," in r for r in head), "顶栏要从第 0 秒就在"
    end = _ts(lines[-1]["b"])
    assert all(end in r for r in head), f"顶栏要挂到最后一行结束（{end}）"


def test_改字号会让行号失准要在报错里说出来(tmp_path):
    """`en_fixed` 的键是行号。**字号一改断行就变，行号跟着失准**——而它不吭声：
    键还在范围内，订正只是悄悄落到了别的行上。

    这里唯一能拦住的地方就是「中文行数和英文行数对不上」那道闸，
    所以它的报错必须把这个成因说出来，不能只说「对不上」。
    """
    with pytest.raises(SystemExit) as e:
        write_ass(_lines(["a b", "c d", "e f"]), ["一", "二"], 0.0, tmp_path / "t.ass")
    assert "字号" in str(e.value) and "en_fixed" in str(e.value)


# ---------------------------------------------------------------- spec 本身

@pytest.mark.parametrize("path", _specs(), ids=lambda p: p.stem)
def test_spec里的人工引语和en_fixed是自洽的(path, tmp_path):
    """spec 里存着的那份订正，必须真的把引语的分歧消掉。

    只断言「`en_fixed` 非空」是查信号不是查产物——**它证明有人写了东西，
    不证明写对了**。这里把订正套上去重跑一遍那道闸。
    """
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not (spec.get("human_quote") or {}).get("text"):
        pytest.skip("这条 spec 没有人工引语可比")
    lines_path = ROOT / "output" / "interviews" / spec["slug"] / "lines.json"
    if not lines_path.exists():
        pytest.skip(f"还没跑过 --stage subs：{lines_path}")
    check_human_quote(spec, json.loads(lines_path.read_text(encoding="utf-8")), tmp_path)


@pytest.mark.parametrize("path", _specs(), ids=lambda p: p.stem)
def test_没验过转写的spec不许标verified(path):
    """`transcript_verified` 是人看完之后手动置的，不能凭「跑过工具」就置上。

    工具只出报告，判断是人做的——所以标了 true 的 spec 必须同时有订正
    或显式声明「一处都不用改」，不能是个空壳；挂着的可疑行也必须销完账。
    """
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not spec.get("transcript_verified"):
        return
    assert spec.get("en_fixed") or spec.get("_verified_clean"), (
        f"{path.name} 标了 transcript_verified 却没有任何订正记录。"
        "真的一处都不用改，就写 `_verified_clean` 说明是谁在什么时候听的。")
    assert not _unresolved_suspects(spec), (
        f"{path.name} 标了 transcript_verified，第 "
        f"{'、'.join(_unresolved_suspects(spec))} 行却还挂在 suspect 里。")


@pytest.mark.parametrize("path", _specs(), ids=lambda p: p.stem)
def test_挂账的行号得真的存在(path):
    """行号是手写的，写错了**不吭声**——它只会安静地指不到任何一行。

    改过切行规则之后行数会变（这次就从 37 变成了 56），旧行号跟着失准，
    而那正是「一个常年挂着的待办和没有待办长得一模一样」的由来。

    拿 `zh` 的长度当行数，**不去读 `output/`**：`write_ass` 已经钉死了
    「中文行数＝英文行数」，而 CI 是 sparse-checkout，读 output/ 的测试
    在那儿只会永远 skip。
    """
    spec = json.loads(path.read_text(encoding="utf-8"))
    keys = {*(spec.get("suspect") or {}), *(spec.get("suspect_ok") or {}),
            *(spec.get("en_fixed") or {})}
    if not keys:
        pytest.skip("这条 spec 没有挂账")
    n = len(spec.get("zh") or [])
    assert n, f"{path.name} 挂了账却还没有中文，行号无从校验"
    bad = [k for k in keys if not 1 <= int(k) <= n]
    assert not bad, f"{path.name} 里的行号 {bad} 超出了实际的 {n} 行"


@pytest.mark.parametrize("path", _specs(), ids=lambda p: p.stem)
def test_销掉的空档得真的是空档(path):
    """销账的键也是手写的，写错了同样**不吭声**——它会安静地指不到任何一个
    空档，而那个真空档仍然敞着，`--stage render` 却已经放行了。

    和上一条同源：**销账要能被验，不然它只是一句「我看过了」。**
    """
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not (ok := spec.get("caption_gaps_ok") or {}):
        pytest.skip("这条 spec 没有销过空档")
    outdir = ROOT / "output" / "interviews" / spec["slug"]
    if not list(outdir.glob("cap_*.json3")):
        pytest.skip("缓存字幕不在，验不了")
    real = {gap_key(*g) for g in caption_gaps(spec, outdir)}
    assert not (stale := sorted(set(ok) - real)), (
        f"{path.name} 销了 {stale}，但现在的字幕里没有这些空档——"
        "要么键写错了，要么阈值改过。")


# ---------------------------------------------------------------- 下载

def _fake_run(monkeypatch, sink: list):
    import tools.build_interview_clip as clip

    monkeypatch.setattr(clip.subprocess, "run",
                        lambda cmd, **kw: sink.append(cmd) or None)


def test_下载落到别的后缀要认出来(tmp_path, monkeypatch, capsys):
    """**`-o` 是模板不是保证。**

    `bv*+ba` 合流时，最佳的那对不是 mp4 装得下的编码（VP9 / Opus）就会被
    yt-dlp 自己改成 `.mkv`，并 warn 一句——而我们开着 `--no-warnings`，
    那句被吞掉。下游 ffmpeg 拿 `source.mp4` 去开，报 ENOENT，
    退出码 `-2 & 0xff = 254`，日志里只剩一个数字，
    **而 artifact 里明明躺着 66 MB 的视频**。这是真实踩到的那次。
    """
    from tools.build_interview_clip import yt_download

    _fake_run(monkeypatch, [])
    (tmp_path / "source.mkv").write_bytes(b"x" * 99)
    got = yt_download("u", tmp_path / "source.mp4", "f", {})
    assert got.name == "source.mkv"
    assert "落到了 source.mkv" in capsys.readouterr().out


def test_下载不到要把目录里有什么列出来(tmp_path, monkeypatch):
    """**空结果先自证是真空。** 只说「文件不存在」，下一个人还得自己去翻。"""
    from tools.build_interview_clip import yt_download

    _fake_run(monkeypatch, [])
    with pytest.raises(SystemExit) as e:
        yt_download("u", tmp_path / "source.mp4", "f", {})
    assert "目录里有" in str(e.value)


def _capture(monkeypatch, dest: Path) -> list:
    import tools.build_interview_clip as clip

    cmds: list = []
    monkeypatch.setattr(clip.subprocess, "run",
                        lambda cmd, **kw: cmds.append(cmd) or dest.write_bytes(b"x"))
    return cmds


def test_要合流才加merge参数纯音轨不加(tmp_path, monkeypatch):
    """**加保险也要验它对每条路都成立。**

    为了「别留一条没有保险的路」，我把下音频那条也接进了 `yt_download`——
    于是 `-f ba` → `.m4a` 也被加上 `--merge-output-format m4a`，而 yt-dlp
    只认视频容器：`error: invalid merge output format "m4a" given`，
    **一秒退出**，看起来像网络问题。**本来通的那条被我弄坏了。**
    """
    from tools.build_interview_clip import yt_download

    vid = tmp_path / "s.mp4"
    cmds = _capture(monkeypatch, vid)
    yt_download("u", vid, "bv*[height<=720]+ba/b[height<=720]", {})
    assert "--merge-output-format" in cmds[0]
    assert cmds[0][cmds[0].index("--merge-output-format") + 1] == "mp4"

    aud = tmp_path / "a.m4a"
    cmds = _capture(monkeypatch, aud)
    yt_download("u", aud, "ba", {})
    assert "--merge-output-format" not in cmds[0], \
        "纯音轨那条路不该合流，加了 yt-dlp 直接报参数非法"


def test_拼出来的参数yt_dlp真的认(tmp_path, monkeypatch):
    """**查产物不查信号**：断言「参数长这样」证明不了 yt-dlp 收得下。

    不联网也能验——不给 URL 跑一遍，yt-dlp 先解析选项再检查 URL：
    选项合法 → `You must provide at least one URL.`；
    选项非法 → `invalid merge output format "m4a" given`。两句分得开。
    """
    import shutil
    import subprocess as sp

    from tools.build_interview_clip import yt_download

    if not shutil.which("yt-dlp"):
        pytest.skip("这台机器没装 yt-dlp")
    # ⚠️ 真的 `run` 要**先抓在手里**：`_capture` 打的桩落在 subprocess 模块上，
    # 而这里的 `sp` 是同一个模块对象——不先存下来，等会儿调的是自己的桩，
    # 拿到一个 int 然后报 `'int' object has no attribute 'stderr'`。
    real_run = sp.run
    for name, fmt in (("s.mp4", "bv*+ba"), ("a.m4a", "ba")):
        dest = tmp_path / name
        cmds = _capture(monkeypatch, dest)
        yt_download("u", dest, fmt, {})
        args = [a for a in cmds[0] if a != "u"]           # 去掉那个假 URL
        r = real_run(args, capture_output=True, text=True, timeout=120)
        assert "You must provide at least one URL" in r.stderr, \
            f"{name} 这组参数 yt-dlp 不认：{r.stderr.strip().splitlines()[-1:]}"


# ---------------------------------------------------------------- 找 Chromium

@pytest.mark.parametrize("layout", ["chrome-linux", "chrome-linux64"])
def test_找chromium认新旧两种目录名(layout, tmp_path, monkeypatch):
    """**新版 playwright 把可执行文件挪进了 `chrome-linux64`。**

    原来只按 `chromium*/chrome-linux/chrome` glob，于是 runner 上装好了却报
    「找不到 Chromium」——日志上一行还写着 `downloaded to …`。预检确实在第 4 秒
    就炸了（它该干的活干了），**但炸的原因是检查工具自己写错了**。

    喂一个假的目录结构让它真去找，而不是断言源码里有没有那个字符串——
    `assert "chrome-linux64" in source` 只能证明有人写过，证明不了它能找到。
    """
    import playwright.sync_api as pw

    from tools.build_interview_clip import _chromium

    # 先把「问 playwright」那条路堵掉：这台机器上它可能答得出真的 Chromium
    monkeypatch.setattr(pw, "sync_playwright", lambda: (_ for _ in ()).throw(RuntimeError))
    exe = tmp_path / "chromium-1234" / layout / "chrome"
    exe.parent.mkdir(parents=True)
    exe.write_text("#!/bin/sh\n")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))
    assert _chromium() == str(exe)


def test_这台机器上真的找得到chromium():
    """**查产物不查信号**：路径存在还不够，得真能跑起来报出版本号。

    缺 Chromium 时这条要红，不许 skip——封面走 HTML 渲染，没有它出不了片，
    而一个常年跳过的检查和常年红是同一个毛病。
    """
    import subprocess

    from tools.build_interview_clip import _chromium

    exe = Path(_chromium())
    assert exe.exists(), exe
    out = subprocess.run([str(exe), "--version"], capture_output=True, text=True,
                         timeout=60).stdout
    assert "Chromium" in out or "Chrome" in out, f"跑不出版本号：{out!r}"


# ---------------------------------------------------------------- 产物 / 自检

# 出片目录里**只许留**这些。别的都是中间物。
_KEEP_SUFFIX = {".mp4", ".jpg", ".ass", ".md", ".json", ".json3"}
# ⚠️ **判据是文件名，不是后缀。** 这个目录里有两个 `.html`，一个是产物一个是垃圾：
# `copy.html` 是**发出去的东西**（GitHub Pages 就靠它，微信里那三个复制按钮全在
# 这一页上）；`cover.html` 是渲封面时的中间物，12.5 MB 全是 base64 内嵌的字体。
# 第一版按后缀判，写的时候目录里只有 `cover.html`，等推送接上、`copy.html`
# 落进来就误报了——**判据宁可窄不可宽，但「窄」要窄在对的那一维上**。
_KEEP_NAMES = {"copy.html"}
_DROP_NAMES = {"cover.html", "whisper.json"}


@pytest.mark.parametrize("path", _specs(), ids=lambda p: p.stem)
def test_中间物不许进仓库(path):
    """第七趟出片时跟着进仓库的中间物比成片的三分之一还多。

    工作流原来只 `rm -f source.mp4`，于是 `_audio.m4a`（6.6 MB）、
    `cover.html`（**12.5 MB**，字体 base64 内嵌的那份）、`whisper.json`
    全被提交了——**每条片子来一份**。清理清单写「留哪些」比写「删哪些」稳：
    以后新增一个中间物，这条会红。
    """
    spec = json.loads(path.read_text(encoding="utf-8"))
    outdir = ROOT / "output" / "interviews" / spec["slug"]
    if not outdir.exists():
        pytest.skip("这条还没出过片")
    bad = [p.name for p in outdir.iterdir()
           if p.name in _DROP_NAMES or p.name.startswith(("source.", "_"))
           or (p.suffix not in _KEEP_SUFFIX and p.name not in _KEEP_NAMES)]
    assert not bad, f"{outdir} 里有中间物：{bad}——工作流的清理步骤要跟着加"


def test_复制页写在提交之前推送排在提交之后():
    """**这条规矩在别的线上踩过四次，别在这儿踩第五次。**

    - 复制页排在提交**之后** → 文件只活在 runner 的工作区，推送里那个按钮
      点开 404（run 30342567879 / 30339377013）
    - 探链接排在提交**之前** → Pages 那时还取不到，按钮**每次都被摘掉**，
      连一分钟后本来能用的也一起摘（run 30432435525）

    所以顺序是死的：**写复制页 → 提交 → 推送**。只测行为拦不住位置错，
    所以这条盯的是**位置**。
    """
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github" / "workflows"
                         / "interview-clip.yml").read_text(encoding="utf-8"))
    names = [str(s.get("name") or "") for s in wf["jobs"]["render"]["steps"]]
    at = {k: next(i for i, n in enumerate(names) if k in n)
          for k in ("写复制页", "提交成片", "推送到微信")}
    assert at["写复制页"] < at["提交成片"] < at["推送到微信"], names

    # 而且渲染那条路上不许出现推送用的探测（闸装在「发」那一步，不是「渲」那一步）
    render_step = next(s for s in wf["jobs"]["render"]["steps"]
                       if "剪 + 烧字幕" in str(s.get("name") or ""))
    assert "push_reel" not in str(render_step.get("run") or "")


def test_按slug存的线要能显式给日期(tmp_path):
    """`push_reel` 原来**只从目录路径解日期**（`output/2026-07-28/reel/…`）。

    赛后开麦按 slug 存（`output/interviews/<slug>/`）——同一场采访哪天发都可能，
    目录里没有日期是**故意的**。于是第一次推送在「写复制页」那步 0 秒失败：
    `从 output/interviews/… 里取不到日期`。**闸装对了**：失败发生在提交之前，
    微信一个字都没出去。
    """
    from tools.push_reel import headline

    od = tmp_path / "output" / "interviews" / "x"
    title = headline(od, "赛后开麦", "甲 vs 乙", "6-3 6-4",
                     summary="伊埃拉再胜斯维托丽娜", date="2026-08-01")
    assert title.startswith("8.1 赛后开麦"), title
    with pytest.raises(SystemExit) as e:      # 不给日期、路径里也没有 → 报错要说出路
        headline(od, "赛后开麦", "甲 vs 乙")
    assert "--date" in str(e.value)
    with pytest.raises(SystemExit):           # 格式不对不许放过
        headline(od, "赛后开麦", "甲 vs 乙", date="2026/08/01")


@pytest.mark.parametrize("path", _specs(), ids=lambda p: p.stem)
def test_spec里的推送字段拼得出合格标题(path):
    """**标题上限 20 字位，超了 `push_reel` 直接拒发。**

    这是在 runner 上跑一趟才发现的第二个问题（第一个是日期）——本来该在
    这儿一秒就知道。判据放在测试里，spec 一改就重算。
    """
    spec = json.loads(path.read_text(encoding="utf-8"))
    if not (push := spec.get("push")):
        pytest.skip("这条 spec 还不推送")
    from tools.push_reel import headline

    assert push.get("matchup"), f"{path.name} 的 push.matchup 是空的"
    title = headline(ROOT / "output" / "interviews" / spec["slug"],
                     spec["column"], push["matchup"], push.get("score", ""),
                     push.get("event", ""), push.get("summary", ""),
                     date="2026-12-31")     # 用固定日期，别让测试跟着今天变
    print(f"{path.stem} → {title}")
    # 换行只对**工作流真正导出的那几个**字段有害（`$GITHUB_OUTPUT` 一行一个
    # `k=v`）。`_why` 这种注释字段随便换行——**判据宁可窄不可宽**，
    # 第一版把它也算上，报了个假错。要导出哪几个从工作流里读，别再抄一份。
    exported = re.search(r'for k in \(([^)]*)\)',
                         _run_scripts("interview-clip.yml")).group(1)
    for k in re.findall(r'"(\w+)"', exported):
        assert "\n" not in str(push.get(k, "")), \
            f"push.{k} 里有换行，塞不进 GITHUB_OUTPUT"


def test_只推送时不做出片那一堆准备():
    """**非关键阶段失败之后重跑，别把前面所有阶段的准备再做一遍。**

    账号所有者：「有些非关键步骤失败了，不要从第一步开始再做，中间能否接上
    继续做，你要有一定的判断。」

    push 模式什么重依赖都不需要——封面已经在仓库里、不转写、不下载、不编码，
    `push_reel.py` 只用 requests 和 tennislive 自己那几个模块。原来照样装
    apt 字体 + ffmpeg + Chromium + faster-whisper，**白等三分钟**，
    而真正要跑的那一步只要二十秒。

    判据：出片专用的准备步骤必须都挂着 `mode != 'push'`。
    """
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github" / "workflows"
                         / "interview-clip.yml").read_text(encoding="utf-8"))
    heavy = ("playwright", "faster-whisper", "yt-dlp", "ffmpeg", "fonts-noto")
    for step in wf["jobs"]["render"]["steps"]:
        run = str(step.get("run") or "")
        if not any(h in run for h in heavy):
            continue
        assert "mode != 'push'" in str(step.get("if", "")), (
            f"步骤「{step.get('name')}」装/用了出片才要的东西，"
            "却没挂 mode != 'push'——只推送的时候它是白跑的")


def test_封面文件名是push_reel认的那个():
    """`push_reel.py` 只认 `poster.jpg`。改名等于推送里少一整屏海报，
    而它**只打印一行提示，不报错**——又一个不吭声的兜底。"""
    from tools.build_interview_clip import ROOT as _R  # noqa: F401
    from tools.push_reel import POSTER_NAME

    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    assert f'"{POSTER_NAME}"' in src, \
        f"build_cover 写出来的名字不是 {POSTER_NAME}，push_reel 找不到它"


def test_自检脚本从工作流里读pip行不另写一份():
    """**两处各写一份必分叉**，而分叉的表现是「本地全绿、runner 上 ModuleNotFound」。

    自检脚本存在的意义就是「本地跑一遍工作流会跑的东西」，它要是自己
    另写一份依赖清单，就变成了「本地跑一遍我以为工作流会跑的东西」。
    """
    from tools.interview_clip_selftest import _pip_line

    line = _pip_line()
    assert line.startswith("pip install"), line
    assert "-e ." in line, "工作流的 pip 行里没有 -e .，自检读到的是别的行？"


# ---------------------------------------------------------------- 工作流依赖

def _run_scripts(workflow: str) -> str:
    """工作流里**真正会执行的那些 `run:` 脚本**，去掉 shell 注释。

    ⚠️ 别拿整个 yml 的文本去搜关键字。第一版就是这么写的，反向验证时
    「把 `-e .` 从 pip 行删掉」**照样绿**——因为我在上面的注释里写了
    「`-e .` 不能漏」，`in` 直接命中了注释。**注释不会被执行。**
    这是「断言全绿不等于页面对」的静态版：查的东西和跑的东西不是一回事。
    """
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github" / "workflows"
                         / workflow).read_text(encoding="utf-8"))
    out = []
    for job in (wf.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            for ln in str(step.get("run") or "").splitlines():
                if not ln.lstrip().startswith("#"):
                    out.append(ln)
    return "\n".join(out)


# 工具里的第三方顶层模块 → 装它要往 pip 行里写什么。
# **这张表要盖住全部**，下面那条测试会拦住漏网的新 import。
_PROVIDES = {
    "PIL": "-e .",              # Pillow 是项目自己声明的依赖
    "tennislive": "-e .",       # 还拖着 requests / rich / pypdf
    "playwright": "playwright",
    "faster_whisper": "faster-whisper",
}


def test_工作流装的依赖覆盖工具import的每一个():
    """**加新能力要同时改三处：代码、工作流的依赖、开跑前的预检。**

    这条规矩一天之内咬了三次，一次比一次靠后：

    1. `fonts-noto-core` 加进了 interview-clip.yml，忘了 ci.yml
    2. Chromium 找得到了，但 `_chromium()` 按旧目录名 glob
    3. pip 行只装了三个第三方包，**没装项目自己**——跑到预检报
       `No module named 'PIL'`

    每次都是「本地装着不等于 CI 装着」：沙箱是长期攒出来的环境，runner 每次
    都是干净的。所以判据不是「装了哪几个包」，是**工具 import 的每一个都在**，
    而且这张对照表**必须盖住全部**——新加一个第三方 import 就红，逼你同时
    改工作流。
    """
    import sys

    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    wf = _run_scripts("interview-clip.yml")
    mods = set(re.findall(r"^\s*(?:from|import)\s+([A-Za-z_]\w*)", src, re.M))
    mods -= set(sys.stdlib_module_names) | {"__future__", "build_interview_clip"}

    unknown = mods - set(_PROVIDES)
    assert not unknown, (
        f"这些第三方 import 没登记在 _PROVIDES 里：{sorted(unknown)}。"
        "登记它，并确认 interview-clip.yml 的 pip 行装了它——"
        "**代码、工作流依赖、开跑前预检，三处一起改。**")
    for mod in sorted(mods):
        assert _PROVIDES[mod] in wf, (
            f"工具 import 了 `{mod}`，但 interview-clip.yml 没装 "
            f"`{_PROVIDES[mod]}`。跑到预检才会报 ModuleNotFoundError。")


def test_每个要下载的步骤都带着cookie():
    """**cookie 从环境变量走，而且每个下载的步骤都得有。**

    踩到的：`verify` 和 `render` 都要 yt-dlp 下东西，但工作流只在 `render`
    那一步把 cookie 路径注进 spec（跑完还得 `git checkout --` 撤掉）。于是
    verify 裸下，yt-dlp 立刻吃 `Sign in to confirm you're not a bot`——
    **而 cookie 文件明明就在那儿，路径还打在日志的 env 里**。

    判据：凡是 `run:` 里跑 `--stage verify` 或 `--stage render` 的步骤，
    `env` 里必须有 `COOKIES`。顺带钉住「别再把 secret 写进 spec」。
    """
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github" / "workflows"
                         / "interview-clip.yml").read_text(encoding="utf-8"))
    seen = 0
    for job in (wf.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            run = str(step.get("run") or "")
            if not any(f"--stage {s}" in run for s in ("verify", "render")):
                continue
            seen += 1
            assert "COOKIES" in (step.get("env") or {}), (
                f"步骤「{step.get('name')}」要下载却没有 COOKIES 环境变量")
            assert '"cookies"' not in run and "d[\"cookies\"]" not in run, (
                f"步骤「{step.get('name')}」还在把 cookie 路径写进 spec。"
                "secret 不该经过仓库里的文件——`cookie_args()` 读环境变量就够了。")
    assert seen >= 2, f"只找到 {seen} 个下载步骤，verify 和 render 都该算上"


def test_没有cookie时要出声不能悄悄裸下(capsys, monkeypatch, tmp_path):
    """**拿没拿到都要说。**

    没 cookie 时 yt-dlp 未必立刻失败（公开视频在某些 IP 上裸下得动），
    失败时报的又是 `Sign in to confirm you're not a bot`——和「视频没了」
    长得一样。不出声就得从头猜。
    """
    from tools.build_interview_clip import cookie_args

    monkeypatch.delenv("COOKIES", raising=False)
    assert cookie_args({}) == []
    assert "没有 cookie" in capsys.readouterr().out

    ck = tmp_path / "c.txt"
    ck.write_text("# netscape\n")
    monkeypatch.setenv("COOKIES", str(ck))
    assert cookie_args({}) == ["--cookies", str(ck)]
    assert "带 cookie 下载" in capsys.readouterr().out
    # spec 里显式给的优先（本地手工跑时用）
    other = tmp_path / "d.txt"
    other.write_text("x")
    assert cookie_args({"cookies": str(other)}) == ["--cookies", str(other)]


def test_ci装的字体覆盖代码要的每一个():
    """**加新能力要同时改三处：代码、工作流的依赖、开跑前的预检。**

    这条又栽了一次：切行改成量真实字宽之后，我把 `fonts-noto-core` 加进了
    `interview-clip.yml`，**忘了 `ci.yml`**——于是四条测试在 CI 上红，
    本地全绿。沙箱是长期攒出来的环境，runner 每次都是干净的。

    判据不是「装了哪几个包」，是「代码点名要的每一个包都在」——
    以后 `_FONT_FILES` 里加字体，这条会替我记得。
    """
    import tools.build_interview_clip as clip

    ci = _run_scripts("ci.yml")
    for kind, (path, pkg) in clip._FONT_FILES.items():
        assert pkg in ci, (
            f"代码量 {kind} 的宽度要 {path}（{pkg}），ci.yml 里没装它。"
            "缺了会悄悄回退到别的字体，量出来的行宽和渲出来的对不上。")


def _ci_sparse_block() -> list[str]:
    """`ci.yml` 里 `sparse-checkout: |` 那个块的原始行。"""
    import yaml  # noqa: PLC0415

    ci = yaml.safe_load((ROOT / ".github" / "workflows"
                         / "ci.yml").read_text(encoding="utf-8"))
    for step in ci["jobs"]["test"]["steps"]:
        if (block := (step.get("with") or {}).get("sparse-checkout")):
            return [ln for ln in block.splitlines() if ln.strip()]
    return []


def test_ci能看到赛后开麦的转写产物():
    """CI 是 sparse-checkout，**默认不含 `output/`**（那目录 1 GB+）。

    `test_spec里的人工引语和en_fixed是自洽的` 要读 `lines.json`，
    没有它就永远 skip——而常年不变的 skip 和常年不变的 fail 是同一个毛病。
    """
    block = _ci_sparse_block()
    assert not block or "output/interviews" in [ln.strip() for ln in block], \
        "ci.yml 用了 sparse-checkout 却没带上 output/interviews，spec 测试会永远 skip"


def test_ci的sparse块里不许有注释():
    """**那个块是纯路径列表，不是 YAML。**

    在里面写 `#` 不会被当成注释，会原样传给 `git sparse-checkout set`：

        git sparse-checkout set .github assets … tools # 「赛后开麦」那条线的… output/interviews
        fatal: specify directories rather than patterns

    而且它**在 checkout 那一步就炸**，一条测试都跑不到——报错信息里也完全
    看不出是注释惹的祸。说明只能写在块外面。
    """
    for ln in _ci_sparse_block():
        assert "#" not in ln, f"sparse-checkout 块里有注释，会被当成路径：{ln.strip()}"
        assert not set("*?[]\\") & set(ln), f"sparse-checkout 只吃目录名：{ln.strip()}"
