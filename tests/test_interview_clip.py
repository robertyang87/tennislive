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
from pathlib import Path

import pytest

from tools.build_interview_clip import (
    ROOT,
    check_human_quote,
    review_sheet,
    segment,
    zh_problems,
    _LINE_PX,
    _NO_TAIL,
    _SENT_END,
    _FILLER,
    _bare,
    _en_width,
    _norm_en,
    _quote_span,
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

    改过切行规则（断句长度、`_NOISE`）之后行数会变，旧行号跟着失准，
    而那正是「一个常年挂着的待办和没有待办长得一模一样」的由来。
    """
    spec = json.loads(path.read_text(encoding="utf-8"))
    keys = {*(spec.get("suspect") or {}), *(spec.get("suspect_ok") or {}),
            *(spec.get("en_fixed") or {})}
    if not keys:
        pytest.skip("这条 spec 没有挂账")
    lines_path = ROOT / "output" / "interviews" / spec["slug"] / "lines.json"
    if not lines_path.exists():
        pytest.skip(f"还没跑过 --stage subs：{lines_path}")
    n = len(json.loads(lines_path.read_text(encoding="utf-8")))
    bad = [k for k in keys if not 1 <= int(k) <= n]
    assert not bad, f"{path.name} 里的行号 {bad} 超出了实际的 {n} 行"
