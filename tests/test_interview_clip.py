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

import ast
import difflib
import json
import re
import subprocess
from pathlib import Path

import pytest

from tools.build_interview_clip import (
    CANVAS_H,
    CROP_RATIO,
    CROP_SHIFT_MAX,
    CAPTION_GAP_SECS,
    ROOT,
    caption_gaps,
    check_human_quote,
    gap_key,
    header_lines,
    review_sheet,
    segment,
    wants_topbar,
    write_ass,
    zh_problems,
    _ASS_HEAD,
    _BAND_TOP,
    _crop_expr,
    _EN_TOP,
    _FONT_FILES,
    _FONT_SIZE,
    _HEAD_FONT,
    _HEAD_SIZE,
    header_ass,
    header_runs,
    _LINE_PX,
    _ZH_TOP,
    _ts,
    _NO_TAIL,
    _SENT_END,
    _COMPARE_FILLERS,
    _FILLER,
    _HESITATION_RE,
    drop_hesitations,
    strip_hesitation_lines,
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


def _code_only(src: str) -> str:
    """只留可执行的那部分：整行注释和三引号块都去掉。

    ⚠️ **注释和 docstring 正是这个仓库记教训的地方**，正文里必然写着当年那些错值
    （「表头写死 `small.en`」「拼出 `[▶](…（片内 0.0 秒）)`」）。连它们一起扫，
    「把坑记下来」会被判成「又踩了这个坑」——同一个错这个仓库犯过五次。

    ⚠️ **别用 `ast.get_docstring()` 去 replace**：它回的是**去过缩进**的那一份，
    和源码里的原文对不上，`str.replace` 一个字都删不掉，而**它不报错**——
    于是判据看起来装上了，其实什么都没剥掉。踩过一次。
    """
    body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    return re.sub(r'"""[\s\S]*?"""', "", body)


def _steps() -> list[dict]:
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github" / "workflows"
                         / "interview-clip.yml").read_text(encoding="utf-8"))
    return wf["jobs"]["render"]["steps"]


def _step_run(step: dict) -> str:
    """一个步骤**真正会执行的**那几行，去掉整行的 shell 注释。

    ⚠️ **工作流的注释正是这个仓库记教训的地方**，正文里必然写着当年那些坑
    （「这里不装 ffmpeg」「本地 `--stage subs` 重生成」）。连注释一起扫，
    「把坑记下来」会被判成「又踩了这个坑」——同一个形状这个仓库犯过五次，
    `_run_scripts()` 早就为此去过注释，而按 `_steps()` 逐步扫的这几条没跟上。

    真栽了一次：提交那一步的清理注释里写了 `ffmpeg` 和 `--stage subs`，
    于是它被判成「装了出片才要的东西」外加「跑在 subs 那一档」，两条一起红。
    判据宁可窄，不可宽。
    """
    return "\n".join(ln for ln in str(step.get("run") or "").splitlines()
                     if not ln.lstrip().startswith("#"))


def _if_holds(expr, *, mode: str, push: str = "false") -> bool:
    """把 `if:` 按给定 inputs 求值一遍。只认这个工作流真正用到的那点语法。

    **按行为查，不按措辞查。** `"mode != 'push'" in expr` 那种写法只能证明
    有人写了这串字，证明不了 push 那趟真的不跑它——反过来也会把
    `mode == 'subs'` 这种同样正确的写法误判成红。
    """
    if expr in (None, ""):
        return True                              # 没有 if 就是每趟都跑
    py = (str(expr)
          .replace("github.event.inputs.mode", repr(mode))
          .replace("github.event.inputs.push", repr(push))
          .replace("&&", " and ").replace("||", " or "))
    if py.strip() == "always()":
        return True
    assert not re.search(r"[a-z_]+\(|github\.", py), f"这个 if 我还不会算：{expr}"
    return bool(eval(py, {"__builtins__": {}}, {}))  # noqa: S307


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

    ⚠️ **这条数字改过两次，两次都是「过期了才发现」。** 最早写死 ≤64，理由是
    「68 号就有行超出」——2026-08-02 把那两行改短之后 68 就装得下了；
    ≤68 那版又在 2026-08-12 过期（账号所有者：「字幕的字体大小再大一点」，
    见 `_FONT_SIZE` 那段注释的完整账）。**一个会过期的常量和一条常年红的
    检查是同一个毛病**——上限跟着「已经改宽过几次」的字号走，不是钉死的。

    重量之后：

        zh=68  最宽 952px   超宽 0 行
        zh=70  最宽 980px   超宽 6 行（全是已发出去、不重渲的老片子，见
                                       `_LEGACY_WIDE_AT_70`）
        zh=72  最宽 1008px  超宽 35 行 ← 代价失控，见 `_FONT_SIZE` 那段注释

    **70 是「代价可控」和「代价失控」的分界，不是「一点余量都没有」的那种
    上限**——新发的片子（改宽度撑不下的行）该重新措辞，已发的片子挂进豁免表。
    真正逐行去量、还认豁免表的判据是 `test_字号涨了不许撑破已有的行`；
    这条只拦「涨过头，涨到 72 这类代价失控的档位」。
    """
    assert _FONT_SIZE["zh"] <= 70, (
        f"中文字号 {_FONT_SIZE['zh']} 超过 70——72 号会破 35 行，代价失控。"
        "写稿的人会被逼着把句子切碎，或者要往豁免表里塞一大堆已发的老片子。")


def test_字号只有一处出处():
    """这几个常量既喂 `_measure`（切行量宽度）又喂 `_ASS_HEAD`（渲染 Style）。

    **写成两处必分叉，而且分叉不吭声**——后定义的那个赢，改前面那个毫无反应。
    这是真踩的：加版式那一版我在文件底下又写了一份 `_FONT_SIZE`，
    行为碰巧是对的（后面那个是新值），但改上面那个就再也不起作用了。

    **ruff 拦不住**：F811 只管重复 import 和函数重定义，
    模块级变量重新赋值不在它的范围里。所以只能自己扫。
    """
    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    for name in ("_FONT_SIZE", "_HEAD_SIZE", "_ZH_GAP", "_EN_TOP", "_LINE_PX"):
        n = len(re.findall(rf"^{name} *=", src, re.M))
        assert n == 1, f"`{name}` 在模块里赋了 {n} 次——写成两处必分叉，而且不吭声"


def test_顶栏走品牌显示体字幕不走():
    """账号所有者：「感觉字体很平淡」。顶栏换成得意黑（和海报同一支）。

    ⚠️ **只换顶栏。** `assets/fonts/ATTRIBUTION.md` 里早写着这条边界：
    display headings 用它，body copy 留给 Noto——得意黑是斜体加窄身，
    当标题有劲，一整句字幕读下来就累。渲出来两版比过。
    """
    styles = {r.split(",")[0].removeprefix("Style: "): r.split(",")
              for r in _ASS_HEAD.splitlines() if r.startswith("Style: ")}
    assert styles["HEADA"][1] == "得意黑", "顶栏主行该走品牌显示体"
    assert styles["EN"][1] == "Noto Sans" and styles["ZH"][1] == "Noto Sans CJK SC", \
        "字幕不许换成显示体——它是斜体窄身，一整句读下来累"
    assert styles["EN"][6] == "1", "英文太细会被旁边的粗中文压住，要加粗"


def _sfnt_names(path: Path) -> set[str]:
    """字体 `name` 表里所有的 family 名（nameID 1）。自己解，不引依赖。

    ⚠️ **`.ttc` 是字体集合，不是字体**（思源黑体就是：一份文件里装着
    SC / TC / JP / KR 好几张脸）。不认集合头的话整份读出来是空的，
    而空集合和「名字对不上」在断言里长得一模一样。
    """
    import struct

    raw = path.read_bytes()
    if raw[:4] == b"ttcf":                     # 集合：先取出每一张脸的偏移
        n = struct.unpack(">I", raw[8:12])[0]
        heads = struct.unpack(f">{n}I", raw[12:12 + 4 * n])
    else:
        heads = (0,)
    out: set[str] = set()
    for head in heads:
        n_tables = struct.unpack(">H", raw[head + 4:head + 6])[0]
        for i in range(n_tables):
            tag, _, off, _ = struct.unpack(
                ">4sIII", raw[head + 12 + 16 * i:head + 28 + 16 * i])
            if tag != b"name":
                continue
            count, str_off = struct.unpack(">HH", raw[off + 2:off + 6])
            for j in range(count):
                pid, eid, _lid, nid, ln, o = struct.unpack(
                    ">HHHHHH", raw[off + 6 + 12 * j:off + 18 + 12 * j])
                if nid != 1:
                    continue
                b = raw[off + str_off + o:off + str_off + o + ln]
                out.add(b.decode("utf-16-be" if (pid, eid) != (1, 0) else "latin-1",
                                 "ignore"))
    return out


def test_品牌字体是libass认得出的那个名字():
    """`webcards` 用 woff2，**libass 读不了 woff2**，所以另存了一份 ttf。

    ⚠️ **ASS 里的 `Fontname` 只能写「得意黑」，不能写英文名。** 这条是实测出来的，
    而且反直觉——PIL 报的 family 是 `Smiley Sans`，看起来才是「正规」的那个：

        Fontname            渲出来的 md5
        得意黑              c80c7f79e9a4   ← 认
        Smiley Sans         d75e3012a8d0
        NoSuchFontXYZ       d75e3012a8d0   ← 和上一行**一模一样**

    也就是说写 `Smiley Sans` 和写一个根本不存在的名字**效果完全相同**：
    libass 静默回退，画面照样出得来，只是不是这支字体。

    复现（CI 里没有 ffmpeg，所以这条只钉名字，渲染验证靠手跑）：

        ffmpeg -f lavfi -i color=c=black:s=1080x200:d=1 \\
          -vf "subtitles=<ass>:fontsdir=assets/fonts" -frames:v 1 out.png
    """
    path = Path(_FONT_FILES["head"][0])
    assert path.exists() and path.suffix == ".ttf", f"{path} 不在，或者还是 woff2"
    names = _sfnt_names(path)
    assert _HEAD_FONT in names, (
        f"字体声明的 family 名是 {sorted(names)}，里面没有 {_HEAD_FONT!r}——"
        "换过字体版本？名字对不上就会静默回退。")


def test_顶栏那个绿方块不许赌字体回退():
    """`▍`（U+258D）**得意黑里没有**，本地是靠回退到思源黑体才画出来的。

    「本地装着不等于 CI 装着」——回退链在 runner 上不保证，赌输了画出来是个
    豆腐块。所以每一段都内联写死 `\\fn`，不交给 fontconfig 去猜。

    判据是**拿一个必定没有的码位当对照**：缺字时字体画的是 `.notdef`，
    而 `.notdef` 对任何缺失字符都长得一样。直接断言「墨迹为空」是错的——
    实测 `.notdef` 有 32×35 的墨，那正是那个豆腐块。
    """
    from PIL import ImageFont

    line_a = header_ass({"slug": "t", "event": "某站 1/4 决赛",
                         "interview_kind": "赛后场上采访",
                         "push": {"matchup": "甲 vs 乙"}})[0]
    assert "▍" in line_a
    assert line_a.startswith(r"{\r\fnNoto Sans CJK SC"), "画方块那一段要显式指定字体"
    head = ImageFont.truetype(_FONT_FILES["head"][0], 40)
    ink = lambda ch: (m := head.getmask(ch)).size + (bytes(m),)  # noqa: E731
    notdef = ink("")                          # 私用区，必定没有
    assert ink("▍") == notdef, (
        "得意黑现在有 ▍ 这个字形了？那 `_HEAD_MARK` 里的 `\\fn` 可以去掉，"
        "注释也要跟着改")
    assert ink("决") != notdef, "对照组：汉字必须画得出来"


def test_顶栏太长要报错不许悄悄折行():
    """`WrapStyle=0` 会自动折行，**一折就压到下面那行上，而且不报错**。

    赛事名长一点就够了——「2026 加拿大公开赛 WTA1000 女单 1/4 决赛 蒙特利尔」
    实测 1003px，超过可用的 984px。
    """
    spec = {"slug": "t", "push": {"matchup": "甲 vs 乙"},
            "interview_kind": "赛后场上采访",
            "event": "2026 加拿大公开赛 WTA1000 女单 1/4 决赛 蒙特利尔"}
    with pytest.raises(SystemExit, match="顶栏"):
        header_lines(spec)


def test_渲染要把仓库的字体目录给libass():
    """得意黑在仓库里，不在系统字体目录——`fontsdir` 不指过去，libass 找不到它，
    而且**它不报错**，只是静默换一支字体接着画。"""
    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    assert "fontsdir={ROOT / 'assets/fonts'}" in src, \
        "render 的 fontsdir 要指向仓库的 assets/fonts"


def test_顶栏说清这是哪一场():
    """账号所有者：「顶部文字说明当前是什么比赛的赛后采访，不然好多人不知道背景」。

    刷到中段的人没看过封面（而封面只有 1.8 秒），画面上只有一个人在说话。
    """
    spec = {"slug": "t", "event": "2026 华盛顿 WTA500 女单八强",
            "interview_kind": "赛后场上采访",
            "push": {"matchup": "伊埃拉 vs 斯维托丽娜"}}
    a, b = header_lines(spec)
    assert a == "2026 华盛顿 WTA500 女单八强"
    assert "伊埃拉 vs 斯维托丽娜" in b and "赛后" in b


def test_顶栏的比分靠winner摆不靠词序():
    """账号所有者要顶栏带比分。**但「谁 比分 谁」这个写法本身就在说谁赢了。**

    `matchup` 是按签位排的，**不保证胜者在前**——`@wta` 的标题就这样，
    我照着推过一次「标题里在前的是赢家」，推错了（`Zheng Qinwen vs. Clara
    Tauson` 赢的是 Tauson）。所以这个断言必须来自数据（`winner`），
    不能来自排版顺序。

    这里故意让 `winner` 是 `matchup` 里**排在后面**的那个：如果实现偷懒
    照词序摆，这条立刻红。
    """
    spec = {"slug": "t", "event": "某站 1/4 决赛", "winner": "斯维托丽娜",
            "interview_kind": "赛后场上采访",
            "push": {"matchup": "伊埃拉 vs 斯维托丽娜", "score": "6-3 6-4"}}
    b = header_lines(spec)[1]
    assert b.startswith("斯维托丽娜 6-3 6-4 伊埃拉"), b


def test_写了比分没写winner不许出片():
    """空着比错着更难发现：顶栏照词序摆，看着完全正常，只是赢家写反了。"""
    spec = {"slug": "t", "event": "某站 1/4 决赛",
            "interview_kind": "赛后场上采访",
            "push": {"matchup": "伊埃拉 vs 斯维托丽娜", "score": "6-3 6-4"}}
    with pytest.raises(SystemExit, match="winner"):
        header_lines(spec)


def test_winner必须是matchup里的那两个之一():
    """两处名字对不上，顶栏会印出一个**没打这场球的人**——而且看着毫无破绽。

    真实的成因是译名：`matchup` 查了译名表写「伊埃拉」，`winner` 手打成
    「埃亚拉」（那正是这个名字改过的旧译）。
    """
    spec = {"slug": "t", "event": "某站 1/4 决赛", "winner": "埃亚拉",
            "interview_kind": "赛后场上采访",
            "push": {"matchup": "伊埃拉 vs 斯维托丽娜", "score": "6-3 6-4"}}
    with pytest.raises(SystemExit, match="不在"):
        header_lines(spec)


def test_顶栏每一段都要先复位():
    """**ASS 的覆盖是粘连的。** 竖条那段设了绿色，下一段不复位的话，
    后面整行标题跟着变绿——渲出来一眼看见，而**代码里一点异常都没有**。

    真踩过：第一版只写了 `\\fn` 没写 `\\r`，标题整行绿的。
    判据是每一段都以 `{\\r` 开头，而不是「颜色写对了没有」——后者要逐项
    列举（颜色、字重、间距、字号…），漏一项就又回到这儿。
    """
    spec = {"slug": "t", "event": "某站 1/4 决赛", "winner": "甲",
            "interview_kind": "赛后场上采访",
            "push": {"matchup": "甲 vs 乙", "score": "6-3 6-4"}}
    for line in header_ass(spec):
        segs = [s for s in line.split("{") if s]
        assert all(s.startswith(r"\r") for s in segs), (
            f"有段没先复位，前一段的颜色/字号会漏进来：{line}")


def test_顶栏量宽度要按每段自己的字号():
    """比分那段是 `\\fs38` 渲的，拿 32 去量会**少算两成**——闸就成了摆设。

    这条拿一个刚好卡在边上的比分验：按各自字号量会超，按统一字号量不会。
    """
    import tools.build_interview_clip as clip

    runs = header_runs({"slug": "t", "event": "某站 1/4 决赛", "winner": "甲",
                        "interview_kind": "赛后场上采访",
                        "push": {"matchup": "甲 vs 乙", "score": "6-3 6-4"}})[1]
    sizes = {size for _, kind, _, size in runs if kind == "num"}
    assert sizes == {clip._SCORE_PX}, "比分那段要带着它自己的字号，不是顶栏那档"
    assert clip._SCORE_PX > _HEAD_SIZE["b"], "比分放大了，量的时候就不能按小的量"


def test_顶栏赢家的名字要高亮不是输家():
    """账号所有者：「谢尔顿要高亮吧，赢球的人」——顶栏印着「谁 比分 谁」，
    两个名字原来一个颜色，谁赢谁输全靠看比分自己算，赢家没有任何视觉上的
    突出。

    **重用 `_MARK_COLOUR`，不新开一支颜色**：那正是顶栏竖条 `▍` 和
    `highlight_en()` 高亮关键短语用的同一支品牌绿——「一屏（这条片子从头
    到尾算一屏）只留一个强调色」，见 `highlight_en` 的 docstring。

    ⚠️ 这条只管**名字**。比分本身按数字上色的判据在
    `test_顶栏比分一盘里只有赢的那个数字绿`——两件事分开测，别在一条测试里
    既卡名字又卡比分，改一头容易误伤另一头。
    """
    from tools.build_interview_clip import _MARK_COLOUR

    runs = header_runs({"slug": "t", "event": "某站 1/4 决赛", "winner": "甲",
                        "interview_kind": "赛后场上采访",
                        "push": {"matchup": "甲 vs 乙", "score": "6-3 6-4"}})[1]
    by_text = {text.strip(): tags for text, _, tags, _ in runs}
    assert by_text["甲"] == _MARK_COLOUR, "赢家「甲」的这一段该带 _MARK_COLOUR"
    assert _MARK_COLOUR not in by_text["乙 · 赛后场上采访"], (
        "输家「乙」不该也被高亮——一屏只留一个强调色，两个都染色等于都没染")


def test_顶栏比分一盘里只有赢的那个数字绿():
    """账号所有者 2026-08-18，看完莱巴金娜那条截图之后三句话逐步收窄定下来的：

        「比分要把赢的一盘的颜色跟赢的人的颜色、字体改成一样的」
        「赢的一盘的比分变绿」
        「一盘里赢的一方比分数变成绿色」          ← 最后落定的这句

    不是整条比分一个颜色，也不是整盘一个颜色——**一盘里两个数字单独判**：
    数大的那个是这一盘的赢家，只有它自己染色；数小的那个（连它自己的
    短横线）留默认色。`push.score` 是从整场比赛赢家视角连续写下来的（每一
    盘前面那个数永远是整场赢家自己的局数），但**这一盘的赢家不一定是整场
    比赛的赢家**——判据是这一盘里两个数谁大，不是看谁是整场赢家。
    """
    from tools.build_interview_clip import _MARK_COLOUR

    # 场景一：直落两盘（"6-3 6-4"），每一盘都是「甲」自己赢的，所以每一盘
    # 里前面那个数（"6"）绿，后面那个数（连短横线的 "-3"/"-4"）留默认色——
    # **不是整段 "6-3" 一起绿**，账号所有者点名要拆到这个颗粒度。
    straight = header_runs({"slug": "t", "event": "某站 1/4 决赛", "winner": "甲",
                            "interview_kind": "赛后场上采访",
                            "push": {"matchup": "甲 vs 乙", "score": "6-3 6-4"}})[1]
    score_runs = [(text, tags) for text, kind, tags, _ in straight if kind == "num"]
    assert [t for t, _ in score_runs] == ["6-", "3 ", "6-", "4"]
    winning_digits, losing_digits = score_runs[0::2], score_runs[1::2]
    assert all(_MARK_COLOUR in tags for _, tags in winning_digits), (
        f"每一盘前面那个数（甲自己赢下的）该带 {_MARK_COLOUR}：{winning_digits}")
    assert all(_MARK_COLOUR not in tags for _, tags in losing_digits), (
        f"每一盘后面那个数（对手的，这一盘他没赢）不该染色：{losing_digits}")

    # 场景二：三盘赛丢了中间那盘（真实案例：亚历山德罗娃 7-6(3) 4-6 6-4 胜
    # 萨巴伦卡）——中间 "4-6" 是「甲」自己输掉的那一盘，**这一盘的赢家是
    # 对手**，所以绿的应该是后面那个数字「6」，不是前面「甲」自己的「4」。
    # 抢七带的 "(3)" 跟着它后面那个数字（这一盘的输家分数）一起走，不单独
    # 染色，也不该干扰谁大谁小的判断。
    dropped = header_runs({"slug": "t", "event": "某站 1/4 决赛", "winner": "甲",
                           "interview_kind": "赛后场上采访",
                           "push": {"matchup": "甲 vs 乙", "score": "7-6(3) 4-6 6-4"}})[1]
    score_runs2 = [(text, tags) for text, kind, tags, _ in dropped if kind == "num"]
    assert [t for t, _ in score_runs2] == ["7-", "6(3) ", "4-", "6 ", "6-", "4"]
    s1a, s1b, s2a, s2b, s3a, s3b = score_runs2
    assert _MARK_COLOUR in s1a[1] and _MARK_COLOUR not in s1b[1], (
        f"第一盘「7-6(3)」甲自己赢的，绿的该是「7」不是「6(3)」：{s1a} {s1b}")
    assert _MARK_COLOUR not in s2a[1] and _MARK_COLOUR in s2b[1], (
        f"第二盘「4-6」甲输掉的，绿的该是对手的「6」不是甲的「4」：{s2a} {s2b}")
    assert _MARK_COLOUR in s3a[1] and _MARK_COLOUR not in s3b[1], (
        f"第三盘「6-4」甲自己赢的，绿的该是「6」不是「4」：{s3a} {s3b}")

    # 落到真正渲染的 ASS 文本里同样要能看见——`\r` 复位干净，颜色没有粘连
    # 到相邻的数字上。⚠️ 只能抓每个数字**自己**的 `{...}` 标签块，不能整段
    # 切片（切到下一个数字文本之前会把下一个数字自己的标签也捎带进来，
    # 是这条测试的上一版栽过的坑：切片边界和标签边界对不齐）。
    _, line_b = header_ass({"slug": "t", "event": "某站 1/4 决赛", "winner": "甲",
                            "interview_kind": "赛后场上采访",
                            "push": {"matchup": "甲 vs 乙", "score": "7-6(3) 4-6 6-4"}})
    tag_4 = re.search(r"(\{[^}]*\})4-", line_b).group(1)
    assert _MARK_COLOUR not in tag_4, f"第二盘甲自己的「4」不该带颜色：{tag_4!r}"
    tag_6b = re.search(r"4-(\{[^}]*\})6 ", line_b).group(1)
    assert _MARK_COLOUR in tag_6b, f"第二盘对手的「6」该带颜色：{tag_6b!r}"


def test_顶栏比分解不出胜负要报错():
    """`_SET_SCORE_RE` 只认「数字-数字」（抢七带 `(数字)` 也认）。真喂进一个
    它解不出来的写法（比如带 `ret.` 的退赛记法），要报错而不是悄悄留白——
    留白看起来和「这一盘赢家真的输了」一模一样，是两件不同的事却给出同一个
    画面，比报错更容易骗过人。
    """
    with pytest.raises(SystemExit, match="解不出胜负"):
        header_runs({"slug": "t", "event": "某站 1/4 决赛", "winner": "甲",
                    "interview_kind": "赛后场上采访",
                    "push": {"matchup": "甲 vs 乙", "score": "6-3 ret."}})


def test_并成一个词的ASR错要在切行之前修(tmp_path):
    """**`word_fix` 和 `en_fixed` 分工不同，不能互相顶替。**

    实测：ASR 把 `was` 和 `Congratulations` 听成了一个词 `wasulations`。
    词都并错了，行怎么排都排不下——照原样修进 `en_fixed`，那一行量出来
    **1150px**，超出可用宽 952 两成，而 libass 会**默默折行**压到中文那行上。

    放进 `word_fix` 之后，切行拿到的是拆开的词，行自己重排。
    """
    words = [(0.0, "while"), (0.5, "I"), (1.0, "wasulations"),
             (1.5, "not"), (2.0, "just"), (2.5, "on"), (3.0, "making.")]
    plain = segment(words, 0.0, 5.0)
    fixed = segment(words, 0.0, 5.0, word_fix={"wasulations": "was here. Congratulations,"})
    assert "wasulations" in " ".join(s["en"] for s in plain)
    assert "wasulations" not in " ".join(s["en"] for s in fixed)
    assert "was here. Congratulations," in " ".join(s["en"] for s in fixed)
    # 拆开之后成了两句，切行会跟着多出一行——**行号会变**，挂账要重挂
    assert len(fixed) > len(plain)


def test_英文也要过宽度闸(tmp_path):
    """原来这道闸**只查中文**——于是 `en_fixed` 里一行订正写长了一路畅通，
    到渲染时 libass 默默折行，压到中文那一行上。

    切行时量的是 ASR 原文，**订正之后没人再量一次**。这条补的就是那一次。
    """
    long_en = "while I was here. Congratulations, not just on making your second career"
    assert _en_width(long_en) > _LINE_PX, "这条测试要一行真的超宽才有意义"
    with pytest.raises(SystemExit, match="英文超宽"):
        write_ass(_lines([long_en, "short one."]), ["一", "二"], 0.0, tmp_path / "t.ass")


# ---------------------------------------------------------------- 固定搭配高亮

def test_高亮短语上色不放大且不改变周边文字():
    """**只上色，不放大**——放大会改这一行的实际占宽，得重新过宽度闸；
    上色用 `\\c`，字符前进量一个像素不变。"""
    from tools.build_interview_clip import _MARK_COLOUR, highlight_en

    out, hit = highlight_en("It was tough to face when you want to finish.",
                            ["tough to face"])
    assert hit == {"tough to face"}
    assert out == ("It was " + f"{{{_MARK_COLOUR}}}tough to face{{\\r}}"
                   + " when you want to finish.")
    # 把标签一律去掉之后必须还原成原文，一个字都不能多或少
    assert re.sub(r"\{[^}]*\}", "", out) == \
        "It was tough to face when you want to finish."


def test_高亮按词边界不按裸子串():
    """裸子串会把 `for` 命中到 `before` 中间（`before` 本身就含着 `for` 四个
    字母）——那不是强调固定搭配，是把一个词腰斩了一半染色。"""
    from tools.build_interview_clip import highlight_en

    out, hit = highlight_en("I waited for hours before the match.", ["for"])
    assert hit == {"for"}
    # 独立的 for 被包起来了
    assert re.search(r"\{[^}]*\}for\{\\r\}", out)
    # before 四个字母连续原样留着，没被从中间插进一个标签
    assert "before" in out


def test_高亮短语一处都没匹配上要报错(tmp_path):
    """**空结果先自证是真空。** 短语打错字或者 `en_fixed` 后来改了原文，
    这个短语就哪儿都找不到——不能悄悄放过，得指名是哪个短语。"""
    lines = _lines(["it was tough to face."])
    spec = {"highlight_en": ["stay focused"],
            "event": "某站某轮", "interview_kind": "赛后场上采访",
            "push": {"matchup": "甲 vs 乙"}}
    with pytest.raises(SystemExit, match="stay focused"):
        write_ass(lines, ["一"], 0.0, tmp_path / "never-written.ass", spec)


def test_高亮短语重叠要报错():
    from tools.build_interview_clip import highlight_en

    with pytest.raises(SystemExit, match="重叠"):
        highlight_en("stay focused and calm", ["stay focused", "focused and"])


def test_没写highlight_en字段行为不变(tmp_path):
    """**只在写了才管，没写就是零行为改动。** 存量 spec 一个字都不该受影响——
    已发的片子不为了措辞重渲。"""
    lines = _lines(["stay focused and calm"])
    spec_no_field = {"slug": "t", "event": "某站某轮", "interview_kind": "赛后场上采访",
                     "push": {"matchup": "甲 vs 乙"}}
    p1 = tmp_path / "a.ass"
    write_ass(lines, ["一"], 0.0, p1, spec_no_field)
    assert "{\\c" not in p1.read_text(encoding="utf-8")
    # spec 本身是 None（老调用点一直这么传）同样不该崩、不该染色
    p2 = tmp_path / "b.ass"
    write_ass(lines, ["一"], 0.0, p2, None)
    assert "{\\c" not in p2.read_text(encoding="utf-8")


def test_高亮短语跨多行各自匹配不误报未命中(tmp_path):
    """两个短语分别落在不同行——不能因为「这一行没找到」就报错，
    要等**所有行**都扫完，真的一次都没中的才算数。"""
    from tools.build_interview_clip import _MARK_COLOUR

    lines = _lines(["stay focused please.", "tough to face today."])
    spec = {"highlight_en": ["stay focused", "tough to face"],
            "event": "某站某轮", "interview_kind": "赛后场上采访",
            "push": {"matchup": "甲 vs 乙"}}
    path = tmp_path / "t.ass"
    write_ass(lines, ["一", "二"], 0.0, path, spec)  # 不许抛
    body = path.read_text(encoding="utf-8")
    assert body.count(f"{{{_MARK_COLOUR}}}") == 2


def test_翻转和裁角标要作用到封面帧上():
    """**封面帧不走那条滤镜链**——它是单独一条 `ffmpeg -ss … -frames:v 1`。

    两处都漏过就是「片子是正的、封面是反的」「片子没水印、海报上有」，
    而**两张图分开看都正常**，只有摆在一起才看得出来。
    """
    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    grab = src[src.index('frame = outdir / "_cover_frame.jpg"'):src.index("build_cover(spec, frame")]
    assert "hflip" in grab, "抽封面帧那一步没跟着翻转"
    assert "_crop_expr" in grab, "抽封面帧那一步没跟着裁角标"


def _clip(path: Path, mark: bool = True, n: int = 10) -> Path:
    """造一段测试片：背景每帧都在动，标记固定不动。

    **不用 ffmpeg，也不 import numpy**——ci.yml 的测试 job 没装 ffmpeg
    （那是出片工作流才装的），而 numpy 不在 dev 依赖里。两样都会让本地全绿、
    CI 必红，正是「三处一起改」那条反复咬人的地方。
    PIL 画帧 → 存 PNG → `cv2.imread` 读成数组喂 `VideoWriter`，两样都绕开了。
    """
    import cv2
    from PIL import Image, ImageDraw

    W, H = 320, 180
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 24, (W, H))
    tmp = path.with_suffix(".png")
    for i in range(n):
        im = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(im)
        for x in range(W):                       # 背景：一条每帧平移的渐变
            d.line([(x, 0), (x, H)], fill=((x * 3 + i * 40) % 256, 90, 140))
        if mark:                                 # 标记：每帧都在同一个位置
            d.rectangle([20, 140, 140, 148], fill=(255, 255, 255))
        im.save(tmp)
        vw.write(cv2.imread(str(tmp)))
    vw.release()
    tmp.unlink(missing_ok=True)
    return path


def test_去水印按笔画补不按矩形抹(tmp_path):
    """**`removelogo` 只动掩膜标出来的那几笔，`delogo` 抹掉整个矩形。**

    delogo 从框边缘横向插值，**笔画之间那些原始像素也一起毁了**，留下一条
    竖纹带；按笔画补，字缝里的球场、广告板原样保留。

    掩膜的判据是「每一帧都亮在同一个位置」——水印是唯一这样的东西，
    背景会动（`testsrc2` 一直在动），逐帧取交集就只剩笔画。
    """
    import cv2

    from tools.build_interview_clip import logo_mask

    clip = _clip(tmp_path / "c.mp4")
    m = logo_mask(clip, [0.03, 0.72, 0.55, 0.16], tmp_path / "m.png")
    mask = cv2.imread(str(m), cv2.IMREAD_GRAYSCALE)
    on = mask > 0
    assert on.any(), "掩膜是空的"
    # **只该是笔画，不是整个框**：框占画面 0.55*0.16 ≈ 8.8%，笔画远小于它
    assert on.mean() < 0.088 * 0.75, f"掩膜盖了 {on.mean():.1%}，像是把整个框都涂了"
    assert not on[0].any() and not on[:, 0].any(), "掩膜贴到画面边了，插值取不到样"


def test_掩膜空了要报错不许静默放行(tmp_path):
    """**空掩膜和「这儿没有水印」长得一模一样。**

    框写错位置、或者水印不是亮字，都会得到空掩膜——静默放行的话
    `removelogo` 什么也不做，成片带着水印发出去，而每一步都是 success。
    """
    from tools.build_interview_clip import logo_mask

    dark = _clip(tmp_path / "d.mp4", mark=False)
    with pytest.raises(SystemExit, match="掩膜是空的"):
        logo_mask(dark, [0.1, 0.7, 0.5, 0.2], tmp_path / "m.png")


def test_去水印排在翻转后面():
    """掩膜是在**成品那一面**算的（`logo_mask` 的 `mirrored` 会先把帧翻过来），
    所以 `removelogo` 必须排在 `hflip` 后面。

    对不上的话水印原样留着、对称的另一边多出一块补痕——**画面照样出得来**。
    """
    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    chain = src[src.index('f"[0:v]{flip}'):src.index('[fg];"')]
    assert chain.index("{flip}") < chain.index("{logo}"), "hflip 要排在 removelogo 前面"
    grab = src[src.index('frame = outdir / "_cover_frame.jpg"'):src.index("build_cover(spec, frame")]
    assert grab.index("hflip") < grab.index("logo"), "抽封面帧那一步顺序也要一致"


def test_裁角标只动纵向不动版式几何():
    """`crop_keep_top` 把窗口整体缩小再缩放回同样的输出尺寸——**版式的几何
    一个数都不用改**。这条钉住那个不变量：窗口的宽高比永远还是 `ratio`。
    """
    import re

    import tools.build_interview_clip as clip

    for keep in (1.0, 0.85, 0.7):
        m = re.match(r"crop=ih\*([\d.]+):ih\*([\d.]+):", clip._crop_expr(4 / 3, keep))
        w, h = float(m.group(1)), float(m.group(2))
        assert abs(w / h - 4 / 3) < 1e-4, f"keep={keep} 把窗口的宽高比改了"
        assert abs(h - keep) < 1e-9


def test_采访是不是在场上跟着源走():
    """**印着「场上」而画面是演播区，是拿版式撒谎。**

    伊埃拉 6-4 6-2 赢大坂直美那场，四个源都自证过：WTA 官方集锦没接采访、
    Tennis Channel 那条在转播区、另两条是发布会和博主口播。账号所有者定了
    用转播区那条，顶栏就得照实说——这条片子的 `interview_kind` 因此写的是
    「赛后演播室专访」，不是这条线大多数片子默认会有的「场上」。

    这条规矩本身就说明了 `interview_kind` **不该有默认值**：谢尔顿×门西克
    那条是完整的赛后新闻发布会，`interview_kind` 当时没写，顶栏悄悄印上了
    「赛后场上采访」——画面是发布会背板，字幕却在说「场上」，和这条测试
    标题描述的错法一模一样，只是撞上的是另一个源。见
    `test_顶栏缺字段要报错而不是印半句` 里补的那个 case。
    """
    assert header_lines({"slug": "t", "event": "某站 1/4 决赛",
                         "interview_kind": "赛后演播室专访",
                         "push": {"matchup": "甲 vs 乙"}})[1].endswith("赛后演播室专访")
    assert header_lines({"slug": "t", "event": "某站 1/4 决赛",
                         "interview_kind": "赛后采访",
                         "push": {"matchup": "甲 vs 乙"}})[1].endswith("赛后采访")


def test_没有比分时顶栏退回只写对阵():
    """比分不是必填——没有它，顶栏仍然要能回答「这是哪一场」。"""
    spec = {"slug": "t", "event": "某站 1/4 决赛", "interview_kind": "赛后场上采访",
            "push": {"matchup": "甲 vs 乙"}}
    assert header_lines(spec)[1] == "甲 vs 乙 · 赛后场上采访"


def test_ASS里的字体名都是字体自己声明的():
    """**写错字体名不报错，只是静默换一支字画。**

    实测过两支，而且「正规」的那个名字反而不认：

        得意黑                       ✅    Smiley Sans       ❌（和不存在的字体同一个 md5）
        Barlow Condensed SemiBold    ✅    BarlowCondensed   ❌

    所以每个 `_ASS_NAME` 都要能在对应字体文件的 `name` 表里找到。
    ⚠️ 这条**只保证名字是字体声明过的**，不保证 libass 一定挑得中它
    （`Smiley Sans` 就是声明了但挑不中）——那一层只能靠渲出来比 md5，
    复现命令写在 `test_品牌字体是libass认得出的那个名字` 里。
    """
    import tools.build_interview_clip as clip

    assert set(clip._ASS_NAME) == set(_FONT_FILES), "两张表的键要一一对应"
    for kind, name in clip._ASS_NAME.items():
        path = Path(_FONT_FILES[kind][0])
        if not path.exists():
            pytest.skip(f"{path} 不在（系统字体没装）")
        assert name in _sfnt_names(path), (
            f"ASS 里 {kind} 写的是 {name!r}，但字体声明的是 {sorted(_sfnt_names(path))}")


def test_顶栏缺字段要报错而不是印半句():
    """空着比错着更难发现：顶栏印出「 · 赛后场上采访」，看着像设计如此。"""
    for spec in ({"slug": "t", "push": {"matchup": "甲 vs 乙"}},
                 {"slug": "t", "event": "某站某轮"},
                 {"slug": "t", "event": "某站某轮", "push": {"matchup": "甲 vs 乙"}}):
        with pytest.raises(SystemExit):
            header_lines(spec)


def test_不写interview_kind不许悄悄退回场上():
    """**这才是谢尔顿×门西克那条真出的错**：`interview_kind` 没写，会印出
    「赛后场上采访」——而那场其实是完整的新闻发布会。画面是发布会背板，
    字幕却说「场上」，观众看不出破绽，账号所有者一眼看出来了。

    这条钉的是**报错的原因**，不只是「有没有报错」：缺 `event` 或缺
    `push.matchup` 时报错原因不一样（见上一条），字符串里必须点名
    `interview_kind`，否则改错原因了这条测试也会一直绿。
    """
    spec = {"slug": "t", "event": "某站某轮", "push": {"matchup": "甲 vs 乙"}}
    with pytest.raises(SystemExit, match="interview_kind"):
        header_lines(spec)


def test_顶栏从头挂到尾(tmp_path):
    """顶栏不是开场卡：**整条片子任何一帧都要能回答「这是哪一场」。**"""
    lines = _lines(["one two", "three four"])
    spec = {"slug": "t", "event": "某站八强", "interview_kind": "赛后场上采访",
            "push": {"matchup": "甲 vs 乙"}, "zh": ["一", "二"]}
    path = tmp_path / "t.ass"
    write_ass(lines, spec["zh"], 0.0, path, spec)
    body = path.read_text(encoding="utf-8")
    head = [r for r in body.splitlines() if r.startswith("Dialogue") and "HEAD" in r]
    assert len(head) == 2, "顶栏该有两行"
    assert all(",0:00:00.00," in r for r in head), "顶栏要从第 0 秒就在"
    end = _ts(lines[-1]["b"])
    assert all(end in r for r in head), f"顶栏要挂到最后一行结束（{end}）"


def test_横着挪窗口能把右上角的台标裁掉(tmp_path):
    """账号所有者 2026-08-15（德约那条 Tennis TV 赛前专访）：「最好把右上角的
    tennistv logo 裁剪掉」。

    **`keep` 在这儿使不上**：它只能从底下切，而台标在顶上，竖着切就要切他的头。
    横着挪窗口是唯一躲得开的方向——4:3 窗口在 16:9 源片上保留 x 0.125–0.875，
    而那个台标左沿量出来在 0.823，只差 0.052。

    ⚠️ **为什么不走 `logo_box` / `removelogo`**：那条路的掩膜是「连续 N 帧都亮在
    同一处」的交集，而这个台标**不是每一帧都在**——实测（run 31855069324）
    单帧里 1511 个像素亮于 170、峰值 245，12 帧取完交集却是空的，
    「空掩膜就报错」那道闸当场拦下。**能被窗口躲开的台标就该躲开**：
    裁掉是确定的，补笔画是估计的。

    **这条真跑一遍 ffmpeg**，不查表达式字符串——查字符串只能防「有人把它删了」，
    防不住「它从来没工作过」（本仓库的老账）。
    """
    import numpy as np
    from PIL import Image

    src = tmp_path / "src.mp4"
    # 深灰底 ＋ 右上角一个白块，位置照德约那条量到的：源片 x 0.83–0.97、y 0.04–0.10
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "color=c=0x303030:s=1920x1080:d=1",
         "-vf", "drawbox=x=iw*0.83:y=ih*0.04:w=iw*0.14:h=ih*0.06:color=white@1:t=fill",
         "-frames:v", "1", str(src)], check=True)

    def white_pixels(shift):
        out = tmp_path / f"{shift}.png"
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
             "-vf", _crop_expr(CROP_RATIO, 1.0, shift) + ",scale=1080:810",
             "-frames:v", "1", str(out)], check=True)
        return int((np.asarray(Image.open(out).convert("L")) > 200).sum())

    # ① 不挪＝台标还在。**先证明它在**，否则「挪完没有了」可能只是本来就没有
    assert white_pixels(0.0) > 500, "测试片自己就没有台标，那下面那条断言是恒真的"
    # ② 挪 0.06 ＝ 一个白像素都不剩
    assert white_pixels(-0.06) == 0, "窗口左移之后台标该整个出框"

    # ③ 默认那一支**一个字符都不许变**：存量 spec 全靠它
    assert _crop_expr(CROP_RATIO) == _crop_expr(CROP_RATIO, 1.0, 0.0)
    assert ":0" in _crop_expr(CROP_RATIO) and "iw" in _crop_expr(CROP_RATIO)
    assert "+" not in _crop_expr(CROP_RATIO) and "-0." not in _crop_expr(CROP_RATIO)

    # ④ 越界要报错。ffmpeg 会把出界的窗口**夹回边上**——画面照样出得来，
    #    只是没挪到你要的位置，而这种错不吭声
    with pytest.raises(SystemExit, match="crop_shift_x"):
        _crop_expr(CROP_RATIO, 1.0, -(CROP_SHIFT_MAX + 0.01))

    # ⑤ 两个调用点都要传。漏一个的表现是「成片裁对了、封面没裁」——
    #    两张图分开看都正常，只有并排才发现台标还留在封面上
    src_txt = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    assert src_txt.count('spec.get("crop_shift_x"') == 2, \
        "封面和成片两条路都要读 `crop_shift_x`，漏一个就只裁一半"


def test_关掉顶栏要显式认领而且默认不许变(tmp_path):
    """账号所有者 2026-08-14（德约科维奇重返辛辛那提那条）：「不要顶部的比赛
    信息提示栏」。理由不是版式口味——**顶栏印的那句话在那条片子上不成立**：
    它答的是「哪一站哪一轮、谁跟谁打成什么样」，而那段采访录在这一站开打
    **之前**，没有轮次、没有对手、没有比分，照常印等于凭空造一场比赛。

    四头都要钉，缺一头这个开关就是个能把顶栏悄悄弄丢的洞：

    1. **不写这个字段 = 一个字都不变。** 存量 spec 全靠这一条。
    2. `topbar: false` ＋ `_no_topbar_why` → 真的不印。
    3. `topbar: false` 却没写理由 → 报错。和 `mixed_fps` / `silent_source` /
       `_layout_why` 同一个形状：**认领这一步把「想清楚了」和「凑合一下」分开**。
    4. ⚠️ **`"false"`（字符串）要报错。** Python 里非空字符串是真值，所以它
       的实际效果是**照常印顶栏**——而写的人以为关掉了。「悄悄没关掉」和
       「本来就没想关」长得一模一样（CLAUDE.md 里 `push.auto` 那条栽过一次）。
    """
    lines = _lines(["one two", "three four"])
    base = {"slug": "t", "event": "某站八强", "interview_kind": "赛后场上采访",
            "push": {"matchup": "甲 vs 乙"}, "zh": ["一", "二"]}

    def heads(spec):
        path = tmp_path / f"{len(list(tmp_path.iterdir()))}.ass"
        write_ass(lines, spec["zh"], 0.0, path, spec)
        return [r for r in path.read_text(encoding="utf-8").splitlines()
                if r.startswith("Dialogue") and "HEAD" in r]

    assert len(heads(base)) == 2, "没写 `topbar` 的存量 spec 必须一个字都不变"
    assert wants_topbar(base) is True

    off = {**base, "topbar": False,
           "_no_topbar_why": "录在开打之前，没有轮次没有对手没有比分"}
    assert wants_topbar(off) is False
    assert heads(off) == [], "写了 `topbar: false` 就不许再印顶栏"

    with pytest.raises(SystemExit, match="_no_topbar_why"):
        wants_topbar({**base, "topbar": False})

    # ⚠️ 字符串那一支：**不许被当成 False**，也不许被当成 True 悄悄放过。
    with pytest.raises(SystemExit, match="topbar"):
        wants_topbar({**base, "topbar": "false"})


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
    lines = json.loads(lines_path.read_text(encoding="utf-8"))
    # **和 `main()` 走同一条路：先套 `en_fixed`，再过这道闸。** 漏了这一步，
    # 这条测试查的就不是「spec 里的订正真的消掉了分歧」，而是「没订正之前
    # 原始 ASR 和引语差多少」——凡是订正命中的正是这道闸报出来的那个词，
    # 就会一直红，逼着人把订正撤回 human_quote_ok 里去，等于让判据自己
    # 教人绕开它。
    for k, v in (spec.get("en_fixed") or {}).items():
        idx = int(k) - 1
        if 0 <= idx < len(lines):
            lines[idx]["en"] = v
    check_human_quote(spec, lines, tmp_path)


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

def _proc(returncode: int = 0, stderr: str = ""):
    """`subprocess.run` 桩要回的那个对象——`yt_download` 现在读
    `.returncode`（判断这一档成没成）和失败时的 `.stderr`/`.stdout`
    （报给下一档看的失败摘要）。

    真的 `subprocess.CompletedProcess` 三个字段都有；桩函数原来回 `None`，
    `yt_download` 加梯子重试之后第一行就是 `proc.returncode`，
    `None.returncode` 直接 `AttributeError`。
    """
    return type("P", (), {"returncode": returncode, "stderr": stderr, "stdout": ""})()


def _fake_run(monkeypatch, sink: list, returncode: int = 0):
    import tools.build_interview_clip as clip

    monkeypatch.setattr(clip.subprocess, "run",
                        lambda cmd, **kw: sink.append(cmd) or _proc(returncode))


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

    def fake(cmd, **kw):
        cmds.append(cmd)
        dest.write_bytes(b"x")
        return _proc(0)

    monkeypatch.setattr(clip.subprocess, "run", fake)
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

    判据：`mode=push` 那一趟，一个装重依赖的步骤都不许跑。

    ⚠️ **第一版是按字面查的**（`"mode != 'push'" in step["if"]`），加
    `mode: subs` 的时候它当场误报：取字幕那两步挂的是 `mode == 'subs'`，
    push 那趟根本不会跑，却因为字面对不上被判红。**查的是措辞不是行为**，
    和「封面引的话」那条第一版栽的是同一个跟头。现在按 mode 真的求值一遍。
    """
    for step in _steps():
        run = _step_run(step)                    # 去掉注释再扫，见 `_step_run`
        if not any(h in run for h in ("playwright", "faster-whisper",
                                      "yt-dlp", "ffmpeg", "fonts-noto")):
            continue
        assert not _if_holds(step.get("if"), mode="push"), (
            f"步骤「{step.get('name')}」装/用了出片才要的东西，"
            f"而它的条件 {step.get('if')!r} 在 mode=push 那趟仍然成立"
            "——只推送的时候它是白跑的")


def test_把产物那一格加回稀疏范围要排在跑工具之前():
    """`git sparse-checkout add` **会把 HEAD 上那一版先铺回工作区**。

    排在生成之后，就是拿旧内容盖掉刚渲出来的成片——而它不报错。
    （CLAUDE.md「把产物那一格弄回 cone」那一节记的就是这个。）

    另一头同样致命：这一步要是根本不跑，`git add "$OUTDIR"` 会说路径在稀疏
    范围之外，**只警告、退出码 0**，产物静默丢掉，跑完才发现。那一头由
    `test_不碰产物的工作流不许把output拉下来` 钉住。

    ⚠️ 既有那条 `test_读产物的步骤不能排在sparse_add前面` **覆盖不到这条线**：
    它认的是 `[ -f "$OUT_DIR/..." ]` 这种 shell 判断，而这条工作流读写产物
    的是 Python 工具。反向验证时把 add 挪到「转写交叉校验」后面，那条照样绿
    ——所以另立这一条，按**步骤序号**判。
    """
    steps = _steps()
    names = [s.get("name") or (s.get("uses") or "?") for s in steps]
    add_at = next((i for i, s in enumerate(steps)
                   if "git sparse-checkout add" in _step_run(s)), None)
    assert add_at is not None, (
        "interview-clip 没把自己那一格加回稀疏范围。"
        f"步骤依次是：{names}")

    uses_tool = [i for i, s in enumerate(steps)
                 if "build_interview_clip.py" in _step_run(s)
                 or "push_reel.py" in _step_run(s)]
    assert uses_tool, "没有一步在跑工具？那这条工作流在干什么"
    assert add_at < min(uses_tool), (
        f"`git sparse-checkout add` 排在第 {add_at + 1} 步（{names[add_at]}），"
        f"而第 {min(uses_tool) + 1} 步（{names[min(uses_tool)]}）就开始跑工具了。"
        "add 会把 HEAD 那一版铺回工作区，排在生成之后＝拿旧内容盖掉刚渲的，"
        "而且不报错。")


def test_每个mode都各干各的活():
    """三个 mode 各自只跑自己那一段，别互相带着跑。

    `subs` 是 2026-08-02 加的：沙箱连字幕都取不到了，切行只能搬到 runner 上。
    加之前只有 render 一条路，取个字幕要白装 Chromium + whisper + ffmpeg
    三分多钟，而且 `zh` 还空着的时候出片那步会空转，整趟红着结束。
    """
    stage = {}                                  # mode -> 它跑到的那几个 --stage
    for mode in ("subs", "render", "push"):
        stage[mode] = [s.get("name") for s in _steps()
                       if _if_holds(s.get("if"), mode=mode)
                       and "--stage" in _step_run(s)]
    assert stage["subs"] == ["取字幕切行"], stage["subs"]
    assert stage["render"] == ["转写交叉校验", "剪 + 烧字幕"], stage["render"]
    assert stage["push"] == [], stage["push"]


def test_碰最终成片的步骤只在render跑():
    """**`cover` 从来不产出 `$SLUG.mp4`。** `--stage cover` 的 docstring
    说得明明白白：「**没有出片**：确认好看再跑 `--stage render`，这样一条
    片子只往仓库里塞一个 mp4」——它下源片、渲海报、删源片，从头到尾
    没有 `$SLUG.mp4` 这个文件。

    「成片发到 Release」那一步（栽的时候还叫「成片太大就发到 Release」，
    2026-08-13 去掉体积闸后改的名）原来跟 render 共用一个 `if:`
    （`mode == 'render' || mode == 'cover'`），而它开头就 `stat` 这个文件——
    cover 那一档跑到这儿必然 `cannot statx ... No such file or directory`。
    `sabalenka-zhang-tor2026-r3` 就是这么栽的：cookie 和 client 梯子两个
    修复都生效了，`只出海报` 那一步真的成功了，下一步却把整个 run 拖红，
    这条 spec 一次都没能验证到那两个修复。

    判据自动推导，不写死步骤名：凡是 `run:` 里出现 `$SLUG.mp4` 或
    `${{ slug }}.mp4` 这个模式的步骤，`if:` 都不许在 `mode == 'cover'`
    时成立。
    """
    pat = re.compile(r"(\$SLUG\.mp4|slug\s*\}\}\.mp4)")
    hit = [s.get("name") for s in _steps() if pat.search(_step_run(s))]
    assert hit, "一个碰最终成片的步骤都没扫到——判据的主语没了"
    for s in _steps():
        if not pat.search(_step_run(s)):
            continue
        assert not _if_holds(s.get("if"), mode="cover"), (
            f"步骤「{s.get('name')}」碰 $SLUG.mp4，但在 mode=cover 时也会跑——"
            "cover 从不产出这个文件，会 stat 失败把整趟 run 拖红")


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
    # `-e .` 也可能带 extra（`-e ".[visualqa]"`），两种写法都算装了项目自己
    assert re.search(r'-e "?\.', line), \
        "工作流的 pip 行里没装项目自己（-e .），自检读到的是别的行？"


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
    # 去水印的掩膜要 cv2（`logo_mask`）。**装 extra 别装裸包名**——
    # `pyproject` 把 opencv 钉在 `>=4.10,<5`，5.x 里 `CascadeClassifier` 没了
    "cv2": '-e ".[visualqa]"',
    # `logo_mask` 里跟 cv2 一起用，靠 opencv 带进来；测试那边刻意不 import 它
    # （dev 依赖里没有），所以只在这张表登记
    "numpy": '-e ".[visualqa]"',
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
    # **本地兄弟工具不算第三方。** `_ytdlp_ladder()` 直接 import
    # `build_match_reel`（复用它的 client 梯子，`grab_frames.py` 也这么干）——
    # 那是仓库里另一个脚本，同一次 checkout 就在手边，不用 pip 装。
    # 同一条判据在 `test_oncourt_collect.py` 里已经踩过一次，这里跟着排掉。
    mods = {m for m in mods if not (ROOT / "tools" / f"{m}.py").exists()}

    unknown = mods - set(_PROVIDES)
    assert not unknown, (
        f"这些第三方 import 没登记在 _PROVIDES 里：{sorted(unknown)}。"
        "登记它，并确认 interview-clip.yml 的 pip 行装了它——"
        "**代码、工作流依赖、开跑前预检，三处一起改。**")
    for mod in sorted(mods):
        assert _PROVIDES[mod] in wf, (
            f"工具 import 了 `{mod}`，但 interview-clip.yml 没装 "
            f"`{_PROVIDES[mod]}`。跑到预检才会报 ModuleNotFoundError。")


def _cookie_hungry(tree: ast.Module) -> set[str]:
    """模块里哪些函数——**含间接调用**——最终会读 cookie。

    从 `cookie_args` 反着推到不动点。**不写名单**：谁要 cookie 由代码自己说，
    以后加一个下源片的函数，它会自动进这个集合。

    用 AST 不用正则：`cookie_args` 这个名字在注释和 docstring 里到处都是
    （这一条底下就写着好几次），而**注释根本不进 AST**。
    """
    calls: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            calls[node.name] = {c.func.id for c in ast.walk(node)
                                if isinstance(c, ast.Call)
                                and isinstance(c.func, ast.Name)}
    hungry = {"cookie_args"}
    while grown := {n for n, callees in calls.items() if callees & hungry} - hungry:
        hungry |= grown
    return hungry


def _stage_guard(stmt: ast.stmt) -> str | None:
    """`if args.stage == "X":` → `"X"`，别的语句 → None。"""
    if not isinstance(stmt, ast.If):
        return None
    t = stmt.test
    if (isinstance(t, ast.Compare) and len(t.ops) == 1
            and isinstance(t.ops[0], ast.Eq)
            and isinstance(t.left, ast.Attribute) and t.left.attr == "stage"
            and isinstance(t.comparators[0], ast.Constant)):
        return t.comparators[0].value
    return None


def _stages_needing_cookie() -> tuple[list[str], set[str]]:
    """跑哪几档 `--stage` 会下东西——顺着 `main()` 的控制流推出来。

    全集取 argparse 的 `choices`（那就是登记在案的全部档位），然后按源码顺序
    走一遍 `main()`：无条件语句一旦碰到「要 cookie 的函数」，**所有还没
    `return` 的档位**都记账；`if args.stage == "X"` 那种分支只记它自己那一档，
    并在它 `return` 之后把 X 从「还在跑」里去掉。
    """
    tree = ast.parse((ROOT / "tools" / "build_interview_clip.py")
                     .read_text(encoding="utf-8"))
    hungry = _cookie_hungry(tree)
    main = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    stages = next(
        ast.literal_eval(kw.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument"
        and node.args and getattr(node.args[0], "value", None) == "--stage"
        for kw in node.keywords if kw.arg == "choices")

    def hits(node: ast.AST) -> bool:
        return any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                   and c.func.id in hungry for c in ast.walk(node))

    running, needs = set(stages), set()
    for stmt in main.body:
        stage = _stage_guard(stmt)
        if stage is None:                       # 每一档都会走到这句
            if hits(stmt):
                needs |= running
            continue
        if stage in running and hits(stmt):
            needs.add(stage)
        if stage in running and any(isinstance(n, ast.Return) for n in stmt.body):
            running.discard(stage)              # 这一档到此为止，后面的不算它
    return stages, needs


def test_会下源片的每一步都要拿到cookie():
    """**cookie 从环境变量走，而且每个下载的步骤都得有。**

    来路两次，同一个形状：

    1. `verify` 和 `render` 都要 yt-dlp 下东西，工作流却只在 `render` 那步把
       cookie 注进 spec。verify 裸下，立刻吃 `Sign in to confirm you're not
       a bot`——**而 cookie 文件明明就在那儿，路径还打在日志的 env 里**。
    2. 2026-08-07：`cover`（#174 加的）**从来没注过 cookie**。它躺了三天没
       出声，因为在此之前走这条线的都是 Brightcove 源（不要 cookie）；换成
       YouTube 的第一条连撞三趟，日志上一行「已写入 cookies（25 行）」、
       下一行「COOKIES=未设置」。

    ⚠️ **而第一版判据正是「伪装成推导的白名单」**：它写死
    `for s in ("verify", "render")`，于是 `cover` 和 `subs` 这两档后加的
    **根本不在它的扫描范围里**——`cover` 漏配它一声不吭。收尾那句
    `assert seen >= 2` 也拦不住：verify + render **正好就是 2**。

    现在从 `cookie_args` 反推谁要 cookie、再顺 `main()` 的控制流推哪几档会
    走到，**一个 stage 名都不写死**。以后再加一档，它自己会进来。
    """
    stages, needs = _stages_needing_cookie()
    assert needs, (
        "从 cookie_args 推不出任何一档要下载——`main()` 的形状变了，"
        "这条判据的主语没了，得跟着改")

    ran: dict[str, list[dict]] = {}
    for step in _steps():
        run = _step_run(step)
        for s in stages:
            if f"--stage {s}" in run:
                ran.setdefault(s, []).append(step)
    assert needs & set(ran), (
        f"工作流一档要 cookie 的 stage 都没跑（推出来要 cookie 的是 {sorted(needs)}，"
        f"工作流跑的是 {sorted(ran)}）——判据的主语没了")

    for stage in sorted(needs & set(ran)):
        for step in ran[stage]:
            assert "COOKIES" in (step.get("env") or {}), (
                f"步骤「{step.get('name')}」跑 --stage {stage}，"
                f"而这一档会下源片，却没有 COOKIES 环境变量")
            assert '"cookies"' not in _step_run(step), (
                f"步骤「{step.get('name')}」还在把 cookie 路径写进 spec。"
                "secret 不该经过仓库里的文件——`cookie_args()` 读环境变量就够了。")


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

    ⚠️ **`pkg` 是 None 的那些不是漏填**，是**仓库自带**的字体（得意黑）。
    它们不该出现在 apt 那行，但**必须真的躺在仓库里**——否则同样是静默回退，
    只是这次怪不到 apt 头上。两种都查，别只查一种。
    """
    import tools.build_interview_clip as clip

    ci = _run_scripts("ci.yml")
    for kind, (path, pkg) in clip._FONT_FILES.items():
        if pkg is None:
            assert Path(path).exists(), (
                f"代码量 {kind} 的宽度要 {path}，它该在仓库里却不在——"
                "是不是只提交了 woff2？libass 读不了 woff2。")
            continue
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
    lines = [ln.strip() for ln in block]
    assert not block or any("output/interviews" in ln and not ln.startswith("!")
                            for ln in lines), \
        "ci.yml 用了 sparse-checkout 却没带上 output/interviews，spec 测试会永远 skip"
    # **而 mp4 要挡在外面。** 这个目录已经 331 MB，其中 5 个 mp4 占 328 MB，
    # 测试要读的 md / json / ass / jpg 加起来约 3 MB——每一趟 CI 都在拉 328 MB
    # 它从不打开的视频。cone 模式挑不掉后缀，所以这儿必须是非 cone 模式。
    if block:
        assert any(ln.startswith("!") and ln.endswith(".mp4") for ln in lines), (
            "成片 mp4 没被挡在 sparse 范围外——CI 每趟白拉 328 MB。"
            "（这正是本文件当年那句「等条数多起来要改成非 cone 模式按后缀挑」）")


def test_ci的sparse块里不许有注释():
    """**那个块是纯路径列表，不是 YAML。**

    在里面写 `#` 不会被当成注释，会原样传给 `git sparse-checkout set`：

        git sparse-checkout set .github assets … tools # 「赛后开麦」那条线的… output/interviews
        fatal: specify directories rather than patterns

    而且它**在 checkout 那一步就炸**，一条测试都跑不到——报错信息里也完全
    看不出是注释惹的祸。说明只能写在块外面。
    """
    import yaml  # noqa: PLC0415

    ci = yaml.safe_load((ROOT / ".github" / "workflows"
                         / "ci.yml").read_text(encoding="utf-8"))
    cone = True
    for step in ci["jobs"]["test"]["steps"]:
        with_ = step.get("with") or {}
        if "sparse-checkout" in with_:
            cone = with_.get("sparse-checkout-cone-mode", True) is not False
    block = _ci_sparse_block()
    for ln in block:
        assert "#" not in ln, f"sparse-checkout 块里有注释，会被当成路径：{ln.strip()}"
        if cone:
            assert not set("*?[]\\") & set(ln), (
                f"cone 模式的 sparse-checkout 只吃目录名：{ln.strip()}")

    # ⚠️ **非 cone 模式下根文件不会自动带上。** 这是从 cone 换过来时最容易
    # 踩的一脚：patterns 是 gitignore 语义，`/src/` 这类只匹配目录，
    # `pyproject.toml` 一个都不沾——于是 `pip install -e .` 当场炸在
    # 「没有 pyproject.toml」，而报错完全看不出是稀疏检出干的。
    # 所以非 cone 模式必须有一行 `/*` 把根上的东西先收进来。
    if block and not cone:
        assert any(ln.strip() == "/*" for ln in block), (
            "非 cone 模式却没有 `/*` 那一行——根文件（pyproject.toml / CLAUDE.md）"
            "不会被检出，pip install -e . 会炸")
        assert any(ln.strip() == "!/output/" for ln in block), (
            "非 cone 模式下 `/*` 把 output/ 也收进来了，1.36 GB 又要下一遍——"
            "必须显式排除，再单独把要的那一格加回去")


def _cited_english(text: str) -> list[str]:
    """从 `_copy_why` 里抠出被当成证据引的英文（连着 4 个词以上才算）。

    三个字两个字的碎片（`aura`、`WTA 500`）不算引语——引一个词证明不了
    任何东西，而短串在几百词的转写里撞上的概率不低，拿它当判据只会误报。
    """
    return [m.group(0).strip() for m in
            re.finditer(r"[A-Za-z][A-Za-z'’,.\- ]{12,}", text or "")
            if len(m.group(0).split()) >= 4]


def _best_match(quote: str, body: str) -> float:
    """引语和转写里最像的那一段，按**词**比，返回 0~1。"""
    import difflib
    words = re.sub(r"[^a-z0-9 ]", " ", quote.lower()).split()
    hay = re.sub(r"[^a-z0-9 ]", " ", body.lower()).split()
    if not words or not hay:
        return 0.0
    n = len(words)
    return max(difflib.SequenceMatcher(None, words, hay[i:i + n]).ratio()
               for i in range(max(1, len(hay) - n + 1)))


@pytest.mark.parametrize("path", _specs(), ids=lambda p: p.stem)
def test_封面引的话必须在片子里(path):
    """封面是成片的头 1.8 秒，它引的话必须真的在这条片子里。

    踩出来的：这条片子换过源（发布会 → 场上采访），封面文案没跟着换。
    主标还写着「小时候看她的大满贯决赛」、副标「她先说了两个字：气场」，
    `_copy_why` 引的是 “I remember watching her … her finals in in the
    Australian Open” 和 “She definitely has aura”——**两句在新素材里
    一句都没有**。等于拿一个片子里根本不存在的时刻去换点击，而点进来的人
    永远等不到那一句。

    **查的是证据，不是措辞。** 封面本来就该是概括而不是照抄——
    「两个月里两次赢她／比分一模一样」一个字都没和中文台词重合，却完全
    站得住。所以拦的是 `_copy_why` 里引的**英文原话**：那是作者声称的
    出处，出处必须存在。第一版按中文子串比，把这条已发的好封面判成了红——
    典型的「判据宁可窄，不可宽」。

    阈值是量出来的，不是拍的：真引的四句 0.86 / 0.92 / 1.00 / 1.00
    （允许「your same opponent」被引成「the same opponent」这种小改），
    编的三句 0.27 / 0.46 / 0.50。0.70 落在中间那道空当里。
    """
    spec = json.loads(path.read_text(encoding="utf-8"))
    cited = _cited_english((spec.get("cover") or {}).get("_copy_why", ""))
    if not cited:
        return
    lines_path = ROOT / "output" / "interviews" / spec["slug"] / "lines.json"
    if not lines_path.exists():
        pytest.skip(f"还没跑过 --stage subs：{lines_path}")
    body = " ".join(l["en"] for l in json.loads(lines_path.read_text(encoding="utf-8")))
    for quote in cited:
        assert (r := _best_match(quote, body)) >= 0.70, (
            f"{path.name} 的封面注里引了一句片子里没有的话（最像的只有 {r:.2f}）：\n"
            f"  {quote}\n"
            "封面引的每一句都要能在 lines.json 里找到。换过源就把封面一起重写；"
            "要留反面例子当判据，写进 `_copy_history`，那个字段不扫。")


def test_封面这道闸真的查到了东西():
    """零命中和「全都合格」长得一模一样，所以要报出到底查了几句。"""
    checked = sum(len(_cited_english((json.loads(p.read_text(encoding="utf-8"))
                                      .get("cover") or {}).get("_copy_why", "")))
                  for p in _specs())
    assert checked >= 2, f"封面注里一共只抠出 {checked} 句英文引语，这道闸等于没装"


def test_字幕带背景色和封面解读卡是同一支品牌绿():
    """垫底那层现在是纯色，要和 `build_cover` / `build_takeaway_card`
    用**同一支**品牌深绿（`#06140f`），不是另起一支。

    这条经过两轮调色都没解决"糊"的问题（先只压暗、后来先去色再压暗，
    见 `_BG_COLOUR` 那段注释记的完整history），账号所有者 2026-08-12：
    「字幕的背景区域，怎么感觉糊糊的，不好看呀」——病根是垫底层一直在
    **从这一帧画面模糊出来**，画面越花它越花。改成纯色之后要跟产品别处
    已经在用的深绿对上，不能另挑一支颜色，否则字幕带、封面、解读卡三处
    看着像三个不同的产品。
    """
    from tools.build_interview_clip import _BG_COLOUR

    hexval = _BG_COLOUR.removeprefix("0x").lower()
    assert hexval == "06140f", (
        f"`_BG_COLOUR` 现在是 {_BG_COLOUR!r}，和封面/解读卡用的品牌深绿 "
        "#06140f 不一样了——三处理应是同一支颜色，改了一处要么是笔误，"
        "要么另外两处（`build_cover` / `build_takeaway_card`）也要跟着改。")
    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert body.count("#06140f") >= 2, (
        "`build_cover` 和 `build_takeaway_card` 至少各该出现一次 #06140f——"
        "如果这两支颜色换了，`_BG_COLOUR` 要跟着一起改，不能只改字幕带这一处。")


def test_字幕带的背景不再从模糊视频派生():
    """垫底那层是纯色，不许再退回"从这一帧画面模糊出来"——那正是
    账号所有者说"糊糊的"那两轮（`eq=brightness` 只压暗、
    `eq=saturation:brightness` 先去色再压暗）的病根，改法都只是调参数，
    没有换掉"垫底层跟着源片内容摆"这个结构本身。见 `_BG_COLOUR` 那段注释。
    """
    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "gblur" not in body, (
        "滤镜链里又出现了 gblur——垫底层不许再从视频模糊出来，"
        "见 `_BG_COLOUR` 那段注释记的两轮教训。")
    assert "eq=brightness" not in body and "eq=saturation" not in body, (
        "滤镜链里又出现了 eq= 调色——同上，垫底层现在是纯色，不需要再调色。")
    assert body.count("_BG_COLOUR") == 2, "`_BG_COLOUR` 该只有一处定义、一处引用"
    assert "c={_BG_COLOUR}" in body, "滤镜链没有引用 `_BG_COLOUR`"
    # ⚠️ 这条不能只测「d= 有没有起作用」（那是下一条测试干的事），必须真查
    # **这条链自己**有没有写 `d=`——`test_垫底纯色层要卡时长否则overlay会
    # 空跑到超时` 那条本地另起了一段一模一样的滤镜串来验证 ffmpeg 的行为，
    # 那证明的是「`d=` 这个机制管用」，证明不了「渲染真用到的那条 `chain`
    # 真的写了它」。两者是两回事，反向验证过：只删掉真实 chain 里的
    # `:d={dur}`，上面那条本地滤镜串测试照样绿——因为它压根没读这条 chain。
    assert ":d={dur}:" in body, (
        "`color=` 那句垫底纯色源没有卡 `d={dur}`——`color` 是无限长的合成源，"
        "不卡时长的话，短的前景流耗尽之后它还在无限产帧，整条链要跑到"
        "`timeout=1800` 才会被杀掉，见 `test_垫底纯色层要卡时长否则overlay"
        "会空跑到超时` 里那段本地实测。")


def test_垫底纯色层要卡时长否则overlay会空跑到超时():
    """`color` 是**无限长**的合成源，`overlay` 的 `eof_action` 默认
    `repeat`——不给它卡一个 `d=`，短前景流耗尽之后垫底层还在无限产帧，
    这条链**不会自然收尾**，会一直空跑到 `subprocess.run(..., timeout=1800)`
    才被杀掉，一次耗尽 30 分钟还什么都产不出来。

    这不是猜的：本地拿 2 秒的合成前景真跑过一遍——不给 `color` 设 `d=`，
    加一道 `-t 30` 硬顶都能跑满 30 秒（本该 2 秒收尾）；给了 `d=2` 之后
    准确停在 2.0 秒。渲染那条真实的 `chain` 现在把 `_BG_COLOUR` 的
    `color=` 源钉上 `d={dur}`，这里真跑一遍同样的滤镜图确认这道钉子还在。
    """
    import subprocess as sp

    out = ROOT / "tests" / "_tmp_bgcolour_dur_check.mp4"
    try:
        sp.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i",
             "testsrc2=size=320x240:rate=25:duration=2",
             "-filter_complex",
             "color=c=0x06140f:s=320x240:d=2:r=25[bg];"
             "[0:v]scale=160:120[fg];[bg][fg]overlay=80:60[out]",
             "-map", "[out]", str(out)],
            check=True, timeout=15, capture_output=True)
        probe = sp.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
            check=True, timeout=10, capture_output=True, text=True)
        dur = float(probe.stdout.strip())
        assert abs(dur - 2.0) < 0.2, (
            f"垫底纯色层配了 d= 应该在 2 秒收尾，实测 {dur:.2f} 秒——"
            "`overlay` 没有按短的那路（前景）收尾，`d=` 没起作用。")
    finally:
        out.unlink(missing_ok=True)


def _ytdlp_calls() -> list[ast.List]:
    """源码里所有 `["yt-dlp", …]` 那样的参数表。"""
    tree = ast.parse((ROOT / "tools" / "build_interview_clip.py")
                     .read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.List) and n.elts
            and isinstance(n.elts[0], ast.Constant) and n.elts[0].value == "yt-dlp"]


def test_每一次调yt_dlp都带上cookie和JS():
    """**两处各配一遍必分叉，而分叉的表现是一句指向错误方向的报错。**

    `yt_download` 早就接上了 `COOKIES` 环境变量，`fetch_words` 一直是裸调的
    ——没有 `--cookies`，也没有 `--js-runtimes node`。长期没暴露，是因为取字幕
    以前不用登录也过得去。2026-08-02 起 YouTube 把这条路一起挡了，runner 上
    就出现了这么一幕：

        已写入 cookies（25 行）                       ← cookie 明明有
        拿不到自动字幕：Sign in to confirm you're not a bot

    读起来像「cookie 过期了」，而真相是**这一步压根没用它**。判据当时就摆在
    眼前：同一份 cookie 七十分钟前刚下完 189 MB 的源片，**两个结论对不上就
    说明是我的读法错了**。

    所以判据不写成「fetch_words 里有 cookie_args」——那只防这一个。
    按 AST 把每一处 yt-dlp 调用都揪出来，以后新加一处照样拦。
    """
    calls = _ytdlp_calls()
    assert len(calls) >= 2, f"只找到 {len(calls)} 处 yt-dlp 调用，AST 大概没解对"
    for node in calls:
        flat = [e.value for e in node.elts if isinstance(e, ast.Constant)]
        starred = [ast.unparse(e.value) for e in node.elts
                   if isinstance(e, ast.Starred)]
        where = f"第 {node.lineno} 行那处 yt-dlp 调用"
        assert "--js-runtimes" in flat, (
            f"{where}没带 --js-runtimes——少了它解不了 n challenge，"
            "而报错长得像「这个视频没有格式」")
        assert any("cookie_args" in s for s in starred), (
            f"{where}没带 cookie_args——被挡的时候会报「Sign in to confirm "
            "you're not a bot」，看着像 cookie 过期，其实是压根没传")


def test_取字幕单档失败要换client重试(monkeypatch, tmp_path):
    """**`fetch_words` 原来只用默认 client 试一次，一失败就直接报错退出。**

    `eala-tbd` 那趟撞的是 `The page needs to be reloaded`——跟 cookie 无关，
    是这台机器和某个 player client 之间的接口问题。`yt_download` 早就换成
    逐档重试的梯子了（`sabalenka-zhang-tor2026-r3` 那次修的），这边漏了
    同一个坑：**两个函数都在调 yt-dlp、都会撞上同一种提取失败，只有一个
    打了补丁**。

    这条直接验证梯子真的会重试：前几档模拟失败（不写文件），某一档模拟
    成功（写出 `cap_<id>.json3`），`fetch_words` 必须拿到那一档的结果，
    不能在第一档失败就放弃。
    """
    from tools import build_interview_clip as m

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if len(calls) < 3:
            return type("P", (), {"returncode": 1, "stdout": "",
                                   "stderr": "ERROR: The page needs to be reloaded."})()
        (tmp_path / "cap_xyz.json3").write_text(
            json.dumps({"events": [{"tStartMs": 0,
                                    "segs": [{"utf8": "hi"}]}]}), encoding="utf-8")
        return type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    words = m.fetch_words("https://www.youtube.com/watch?v=xyz", tmp_path, {})
    assert len(calls) == 3, f"该在第 3 档才成功，实际试了 {len(calls)} 档"
    assert words == [(0.0, "hi")]


def test_换了候选视频不许复用上一条的字幕缓存(monkeypatch, tmp_path):
    """真实事故（谢尔顿那条 spec）：先探了一个候选视频 `SOUMru-EDI8`，写下
    `cap_SOUMru-EDI8.en.json3`，判定不合适之后把 spec 的 `url` 换成账号
    所有者给的新链接 `ZycljTf6s0E`——但 outdir 没清空，旧文件还在。

    原来的缓存检查只问「outdir 里有没有任何一份 `cap_*.json3`」，不问
    「是不是这条 URL 的」，于是新的一次 `--stage subs` 会静静吃下旧候选
    的字幕：日志上一个字不提，而且 `storyboard_sheet()` 那一头（不缓存，
    每次真下）汇报的片长和标题是对的，两个函数一个说真话一个说假话，
    只看日志根本发现不了。

    这条直接验证：outdir 里躺着旧视频的缓存时，`fetch_words` 对一条
    **不同 ID** 的新 URL 必须走网络重新抓，不能命中旧文件；旧文件本身
    也不能被误删——它是别的候选留下的记录。
    """
    from tools import build_interview_clip as m

    (tmp_path / "cap_SOUMru-EDI8.en.json3").write_text(
        json.dumps({"events": [{"tStartMs": 0,
                                "segs": [{"utf8": "old candidate junk"}]}]}),
        encoding="utf-8")

    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        (tmp_path / "cap_ZycljTf6s0E.en.json3").write_text(
            json.dumps({"events": [{"tStartMs": 0,
                                    "segs": [{"utf8": "real new content"}]}]}),
            encoding="utf-8")
        return type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    words = m.fetch_words(
        "https://www.youtube.com/watch?v=ZycljTf6s0E", tmp_path, {})

    assert len(calls) == 1, (
        f"没有真的发起网络请求，而是命中了旧候选的缓存文件（0 次调用应为 1 次）")
    assert words == [(0.0, "real new content")], (
        f"读到了错的内容：{words}——旧候选 SOUMru-EDI8 的缓存没有被绕开")
    assert (tmp_path / "cap_SOUMru-EDI8.en.json3").exists(), (
        "旧候选的缓存文件不该被删掉，它是别的候选探过的记录")


def test_同一条视频再跑一次仍然用缓存不重新下载(monkeypatch, tmp_path):
    """上一条测试拦的是「误用别的视频的缓存」；这条测试反向验证同一个修复
    没有连带杀死原来的缓存收益——同一个视频 ID 重跑 `--stage subs`（比如
    改了 spec 别的字段，字幕本身没变）不该再发一次网络请求。
    """
    from tools import build_interview_clip as m

    (tmp_path / "cap_ZycljTf6s0E.en.json3").write_text(
        json.dumps({"events": [{"tStartMs": 0,
                                "segs": [{"utf8": "cached content"}]}]}),
        encoding="utf-8")

    calls = []
    monkeypatch.setattr(m.subprocess, "run",
                        lambda cmd, **kw: calls.append(cmd))
    words = m.fetch_words(
        "https://www.youtube.com/watch?v=ZycljTf6s0E", tmp_path, {})

    assert calls == [], f"同一条视频的缓存本该命中，却又发起了网络请求：{calls}"
    assert words == [(0.0, "cached content")]


def test_video_id从两种YouTube链接形式都抠得出来():
    """`_video_id()` 要同时认得 `youtube.com/watch?v=` 和 `youtu.be/` 两种
    形式——`match-reel` 那条线两种都在用，采访这条线的 spec 里也混着两种。
    """
    from tools.build_interview_clip import _video_id

    assert _video_id("https://www.youtube.com/watch?v=ZycljTf6s0E") == "ZycljTf6s0E"
    assert _video_id("https://youtu.be/ZycljTf6s0E") == "ZycljTf6s0E"
    assert _video_id("https://youtu.be/ZycljTf6s0E?si=abc123") == "ZycljTf6s0E"
    assert _video_id(
        "https://www.youtube.com/watch?v=5uI6gpVjHdw&list=xyz") == "5uI6gpVjHdw"


def test_订正要看穿说话人标记():
    """自动字幕给每个说话人的第一个词加 `>>`，而 `word_fix` 原来查不穿它。

    演播室那条片子里 `>>` 有 30 处。原来是 `fix.get(w.strip(".,?!"), w)`，
    于是 `'>> Alexo.'` 查出来是 `'>> Alexo'`，跟表里的 `Alexo` 对不上——
    **凡是某个说话人的第一个词，那条订正一律静默失效**。它不报错，只是没生效，
    而人写了订正就默认它生效了；要等成片烧出来才看得见名字还是错的。

    不能改成「提前把 `>>` 剥掉」：这个标记有用，`_split_sentences` 靠它断
    「换人说话」。只能让查表看穿它。

    尾标点一并钉住：命中之后原来返回光秃秃的替换词，`'Pigula,'` 的逗号被吃掉
    ——而逗号是切行的第一依据（先按标点切子句），丢一个就少一个断点。
    """
    from tools.build_interview_clip import segment

    words = [(0.5, ">> Alexo."), (1.0, "beat"), (1.5, "Pigula,"), (2.0, "today.")]
    out = segment(words, 0.0, 9.0, word_fix={"Alexo": "Alex Eala", "Pigula": "Pegula"})
    en = " ".join(s["en"] for s in out)
    assert "Alex Eala" in en, f"说话人标记后面那个词没修上：{en}"
    assert "Alexo" not in en, en
    assert "Pegula," in en, f"订正把尾标点吃掉了，断句会少一个依据：{en}"
    assert ">>" not in en, f"说话人标记漏进成品行了：{en}"


def test_小红书正文不许超一千字():
    """账号所有者：「正文超过了 1000 字，然后不能直接复制」。

    小红书正文那一格就是 1000 字上限，超了**粘不进去**——于是推送里那个
    「复制文案」按钮点了也没用，整条推送的出口等于没有。而它**不报错**：
    文案照样渲、链接照样发，只有真去粘的人才发现粘不上。

    量出来是采访这条线独有的毛病：赛场之上那十几条正文全在 1000 以内
    （最长 925），而采访两条是 1161 和 1005——因为采访**把原文整段搬进了
    正文**。所以正确的修法是提炼，不是放宽这个数。

    闸装在 `split_copy` 里，因为推送正文和复制页共用它——装一处两边都拦得住。

    ⚠️ **AI 生成合成内容标识那 47 字 2026-08-15 起不占预算了**（账号所有者：
    「以后不要出现这些东西」，见 `tennislive.render.ai_disclosure` 顶上那段）。
    2026-08-14 到 08-15 之间写的文案是按 `1000 - 47` 的预算量的，所以现在**只会
    更宽松**，不会有人因此被误拦。

    ⚠️ **口径仍然要按 PR #341 修对之后的算**：`push_reel.main()` 会先顶一行
    标题进正文，所以文件自己的第一行也落在这 1000 字里。少算这一头会放过几条，
    而放过的那几条会在**真推送那一刻**才报，微信一个字都发不出去
    （`shelton-nakashima-mtl2026-final` 8/14 正是这么栽的：本地量 974 过关、
    CI 全绿、合并之后真推报 1001）。

    ## 豁免不是一张名单，是「已经发出去了」这个事实

    ⚠️ 第一版这儿冻着一份九条的 `_LEGACY_OVER_BUDGET`。它当天就少了一条
    （`rybakina-swiatek-tor2026-final-presser` 在快照之后到货），而这条线
    **一天到货 2~8 条**——手写名单在这个节奏下只会一直红，然后每次都被
    「加一行」修掉，几周之内退化成许可证。本仓库同一天在 `_ALREADY_PUSHED`
    上刚踩过一模一样的一遍。

    所以主语换成集合差：**超预算只有一种情形可以放行——这份文案已经推出去了**
    （仓库里有它的 `copy.html`）。已发的改不动（微信那条消息收不回来，小红书
    要换视频得重新上传），而**还没发的超标就是该去提炼**，那正是这道闸的本意。
    「加一行」这个动作从此不存在，判据也不需要人喂。

    它**自己会收敛**：这条改动合进去之后写的每一份新文案，都会在
    `--dry-run` 的第 0.2 秒被拦下来（`build_match_reel` 本来就调 `split_copy`
    预检字数），所以「已发且超标」这个集合只会变小不会变大。
    """
    import contextlib
    import io
    import sys

    import pytest

    sys.path.insert(0, str(ROOT / "tools"))
    from push_reel import BODY_MAX, cut_at_tags, split_copy


    # ⚠️ **先把这个数钉住，再拿它去量。** 第一版只写了 `len(body) <= BODY_MAX`
    # ——反向验证时把上限改成 100000，闸和断言**一起松了**，测试照样绿。
    # 也就是说它拦得住「文案变长」，拦不住「有人把上限调高」，而后者正是
    # 超标时最顺手的那个改法。1000 是小红书那一格的**平台限制**，不是我们的
    # 口味参数：调高它不会让文案粘得进去，只会让这道闸变成摆设。
    assert BODY_MAX == 1000, (
        f"BODY_MAX 被改成了 {BODY_MAX}。这是平台定的，不是可调的——"
        "正文超了要去提炼，不是放宽这个数")

    # ⚠️ **运行时会先在最前面顶一行算出来的标题**，这条测试必须照做，
    # 否则它量的和真跑的不是同一段字。`push_reel.main()` 里是
    # `copy_text = f"{title}\n\n{copy_text}"`——顶进去之后，**文案自己的
    # 第一行被挤进正文**（那正是「钩子退成正文第一行」那条口径），于是
    # 真正的正文 = 整份文件，而不是「文件去掉第一行」。
    #
    # 不模拟这一步，量出来就比真跑的少一整行标题，而**少的那点正好够让一份
    # 超标的文案在这儿绿着过去**：2026-08-14 谢尔顿蒙特利尔那条本地量 974
    # 过关、CI 全绿、PR 合并，真推的时候报 **1001**，微信一个字都没发出去
    # （run 31775244995）。差的 27 就是标题那 25 个字加两个换行。
    #
    # ⚠️ 这一段是 PR #341 修对的口径，AI 标识这条改动**要在它之上**量——
    # 两件事都在啃同一个 1000 字预算（标题顶进来 + 标识 47 字），
    # 少算任何一头，豁免表就会是按一个不存在的口径算出来的。
    src = (ROOT / "tools" / "push_reel.py").read_text(encoding="utf-8")
    assert 'copy_text = f"{title}\\n\\n{copy_text}"' in src, (
        "push_reel 不再把标题顶在文案最前面了——这条测试模拟的那一步没了，"
        "口径要跟着改，否则它又会比真跑的少量一整行")

    # ⚠️ 用 `git ls-files` 不用 `Path.glob`：CI 的稀疏检出把 `output/` 挡在
    # 外面，索引里的条目只是被标了 skip-worktree，`glob` 在 CI 上恒空——
    # 而空集合和「一条都没发过」长得一模一样。git 跑不起来要当场出声。
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "output/interviews/*/copy.html",
         "output/*/reel/*/copy.html"],
        capture_output=True, text=True, check=True, cwd=ROOT).stdout
    published = {line.split("/")[-2] for line in tracked.split("\0") if line}
    # 判据自己的判据①：主语没了的样子就是这个集合为空，而那时**每一条超标的
    # 文案都会被判成「还没发」**——那是红，不是绿，所以这一条守的是别让它
    # 变成一条永远红的检查。
    assert len(published) >= 10, (
        f"只数到 {len(published)} 条有复制页的文案，判据失效了")

    checked, over = 0, []
    for f in sorted((ROOT / "specs").glob("*/*.xhs.txt")):
        with contextlib.redirect_stdout(io.StringIO()):
            raw = cut_at_tags(f.read_text(encoding="utf-8"))
        staged = f"占位标题\n\n{raw}"        # 照 push_reel.main() 顶一行标题
        checked += 1
        slug = f.name[: -len(".xhs.txt")]
        if slug in published:
            # 已经推出去了：微信那条消息收不回来，小红书要换视频得重新上传，
            # **改这份文案改不动已经发生的那次发布**。所以它超不超都放行——
            # 但下面那个循环外的断言会把「已发而且超标」的份数打印出来，
            # 免得「一条都没超」和「这段根本没跑」长得一样。
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    split_copy(staged)
            except SystemExit:
                over.append(f.name)
            continue
        # 还没发的：超了就是该去提炼，那正是这道闸的本意。
        with contextlib.redirect_stdout(io.StringIO()):
            _, body = split_copy(staged)   # 超了它自己就 SystemExit
        assert len(body) <= BODY_MAX, f"{f.name} 正文 {len(body)} 字"

    # 判据自己的判据②：主语没了（目录改名、glob 写错）的样子就是一份都没校到，
    # 而那时上面整个循环会安安静静地全绿。
    assert checked >= 10, f"只校到 {checked} 份文案，判据大概没找对目录"
    print(f"  {checked} 份文案，已发而且超预算的 {len(over)} 份（放行）："
          f"{sorted(over)}")


def test_采访成片一律走Release不进git():
    """采访成片 20~67 MiB 一条条进 git，把 .git 撑到了 6.0 GB。

    来路（2026-08-13）：账号所有者「当前代码库太大了，好多资源是不是不用
    放在这里代码库里」。量出来 .git 已 6.0 GB，其中 mp4 blob 4.93 GB。
    根因：这一步原来只在成片超过 95 MiB 时才走 Release，而采访成片
    **从来没超过 95 MiB**——Release 分支上线以来一次都没走到过，每条成片
    照旧进 git。一个从来没被走到的兜底，正是「兜底出事的时候不吭声」的
    形状。存量动不了（链接钉在 main 的文件路径上，已发的微信消息收不
    回来），只改增量：**以后一律走 Release，不再进 git**。

    四件事都要钉，少一件就会退回老样子：

    1. **没有体积早退**——去注释后不许出现 `LIMIT=`、不许出现「不到 95」。
       体积闸一回来，95 MiB 以下（也就是全部采访成片）又开始进 git。
       `SZ=$(stat …)` 要留着：`render.json` 的 `video_bytes` 从它来
    2. `gh release upload` 外面**真的套着重试循环**，退避是涨的，用尽要
       `exit 1`。原来裸调一次无所谓——体积闸在前面，一年走不到几次；
       每趟 render 都走之后，一次 GitHub 5xx 报销的就是整趟 render
       （match-reel 2026-08-13 李娜那条 run 31709569579 就是这么死的，
       写法照它同一步骤抄：4 次、`WAIT=$((5*i*i))` 二次方退避、一律用 if——
       `bash -e` 下 `[ A ] && break` 整条为假会把这一步杀掉）
    3. 传完要 `rm -f "$CLIP"`，否则 `git add` 照样把它吃进去，白传一趟
    4. 顺序：「验成片」在它**之前**（验的就是这份本地文件，rm 之后没得验），
       「提交成片」在它**之后**（文件进了 index 删不删都晚了——同
       「复制页那道闸装在发的那一步不是渲的那一步」）

    ⚠️ 判据宁可窄：只扫这一步去注释后的 `run:`（`_step_run`），不扫整份
    yml——步骤注释里如实记着旧门槛那段来路（95、LIMIT 这些词都在），
    连注释一起扫会被自己的注释误伤，这个仓库同一个形状犯过五次。
    """
    steps = _steps()
    names = [s.get("name") for s in steps]
    hits = [i for i, s in enumerate(steps) if "gh release upload" in _step_run(s)]
    assert len(hits) == 1, f"该正好有一步传 Release 附件，扫到 {len(hits)} 步：{hits}"
    i_rel = hits[0]
    body = _step_run(steps[i_rel])

    # ① 没有体积早退——体积闸一回来，全部采访成片又开始进 git
    assert "LIMIT=" not in body, "体积闸回来了——采访成片从来不超 95 MiB，会重新进 git"
    assert "不到 95" not in body, "体积早退回来了——采访成片从来不超 95 MiB，会重新进 git"
    assert 'SZ=$(stat -c%s "$CLIP")' in body, (
        "SZ 没了——render.json 的 video_bytes 从它来，别连它一起删")

    # ② 上传外面套着重试循环，退避是涨的，用尽要报错
    upload = body.index("gh release upload")
    loop = body.rfind("for ", 0, upload)
    assert loop != -1, "`gh release upload` 外面没有重试循环——一次 5xx 报销整趟 render"
    tail = body[loop:]
    assert "sleep" in tail[:tail.index("URL=")], (
        "重试循环里没有退避——贴着重发四次，撞上的同一个 5xx 多半还在")
    assert "WAIT=$((5 * i * i))" in body, (
        "退避不是涨的：等长的重试对一次持续几十秒的服务端故障没有用")
    assert 'UPLOADED" = 1 ]' in body and "exit 1" in body, (
        "四次都没传上去却没有拦住：下游会把一个取不到的链接写进 render.json")
    # `bash -e` 下 `[ A ] && break` 整条为假会把这一步杀掉，一律用 if
    for line in tail.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and "&&" in stripped:
            raise AssertionError(
                f"`bash -e` 下这一行整条为假会直接杀掉这一步，用 if：{stripped!r}")

    # ③ 传完删本地那份
    assert re.search(r'rm -f "\$CLIP"', body), (
        "传完 Release 没删本地那份——git add 照样把它吃进去，白传一趟")

    # ④ 顺序：验成片 → Release → 提交成片
    # ⚠️ **按前缀认，不按全等认。** 这条原来写的是 `names.index("验成片")`，
    # 而那一步后来被改名成「验成片（L2 成片落地闸）」——**步骤本身还在、顺序也
    # 还对，测试却直接 ValueError 挂掉**。步骤名会带上后缀（改名、加副标题），
    # 而这一条查的是**顺序**不是名字，用全等等于把「改了个标题」判成「这一步没了」。
    # ⚠️ 前缀仍然要唯一：命中两条就不知道在比哪一条的顺序了。
    def _only_step_starting(prefix: str) -> int:
        hits = [i for i, n in enumerate(names) if (n or "").startswith(prefix)]
        assert len(hits) == 1, (
            f"「{prefix}」开头的步骤有 {len(hits)} 条（{[names[i] for i in hits]}）——"
            "顺序判据要求它唯一")
        return hits[0]

    i_verify = _only_step_starting("验成片")
    i_commit = _only_step_starting("提交成片")
    assert i_verify < i_rel < i_commit, (
        f"顺序不对（验成片={i_verify}，Release={i_rel}，提交={i_commit}）——"
        "验成片要在 rm 之前，Release 要在提交之前")


def test_分歧率认领要钉在当时那次观测上():
    """分歧率超闸可以认领，但认领不能变成永久豁免。

    长采访天然会超：这个指标按词比，而 whisper 会把 `um`/`uh`/`you know`/
    结巴整个丢掉，YouTube 全留着。演播室那条实测 YouTube 1229 词、
    whisper 1105 词——**光这 124 个词就占 10.1%**，而总分歧才 12.4%。
    超出闸门的部分几乎全是「whisper 更简」，不是「英文有错」。

    没去改 `TRANSCRIPT_MAX_DISAGREE`：那个数护着所有片子，而沙箱里跑不了
    whisper（IP 被挡），没法拿存量重新标定——改一个动不了的数等于把所有
    片子的闸一起放松，还验不了后果。

    四头都要卡：
    - 不认领 → 拦，**而且报错要说出路**（照抄一行能贴进 spec 的 JSON）
    - 认领了但实测比认领值还高 → 拦。这是关键的一条：它把认领钉在当时那次
      观测上，以后真变差了闸会重新响，而不是「认领过一次就永久放行」
    - 高过天花板 → 拦。那个量级不是虚词能解释的
    - 认领得当 → 放行
    """
    from tools.build_interview_clip import (
        TRANSCRIPT_DISAGREE_CEILING,
        _check_disagree_claim,
    )

    path = ROOT / "x.md"
    with pytest.raises(SystemExit) as e:
        _check_disagree_claim({}, 0.124, path)
    assert "transcript_disagree_ok" in str(e.value), "报错没说出路"

    with pytest.raises(SystemExit, match="比认领的"):
        _check_disagree_claim(
            {"transcript_disagree_ok": {"rate": 0.124, "why": "看过"}}, 0.150, path)

    with pytest.raises(SystemExit, match="天花板"):
        _check_disagree_claim(
            {"transcript_disagree_ok": {"rate": 0.99, "why": "看过"}},
            TRANSCRIPT_DISAGREE_CEILING + 0.01, path)

    # 光写个 rate 不写 why 也不算——认领要留下判据，不是填个数
    with pytest.raises(SystemExit):
        _check_disagree_claim({"transcript_disagree_ok": {"rate": 0.2}}, 0.124, path)

    _check_disagree_claim(
        {"transcript_disagree_ok": {"rate": 0.124, "why": "逐处看过：差的全是虚词"}},
        0.124, path)


# 规矩定下来**之前**已经发出去的两个文件。已发的片子不为了措辞重渲——
# `eala-svitolina-dc2026-qf.json` 的 `_event_why` 里账号所有者原话就是
# 「不补了」，这条规矩同理不补。**只许减不许加**：修好一个就从下面删掉一个，
# 别让它变成一张许可证。
_LEGACY_QUALIFIER_NAMES = {
    "alexandrova-sabalenka-tor2026-r16.json",
    "alexandrova-sabalenka-tor2026-r16.xhs.txt",
    "eala-svitolina-dc2026-qf.json",
    "eala-svitolina-dc2026-qf.xhs.txt",
}


def test_轮次要写半决赛不写四强():
    """账号所有者 2026-08-02：「以后不要用四强八强之类的，国内通常用半决赛
    1／4 决赛 1/8 决赛之类的。再往前就第几轮好了」。

    这条规矩早就在「赛场之上」那条线（`build_match_reel`）落了闸
    （`test_轮次要写半决赛不写四强`，`tests/test_match_reel.py`），
    「赛后开麦」这条线一直没跟上——谢尔顿那条 spec 翻译时写进去了三处
    「四强」（`你现在又进四强了` / `四强里可能会有` / `四强赛都打到了`），
    一次都没被拦住，直到重新审这条片子时才发现。补上同一道闸，别的
    interview spec 重蹈覆辙。

    **只查会发出去的字段**：`zh`（对话字幕，读者读到的正是这个）、
    `push.*`、`cover.*`、`takeaway.*`，以及 `.xhs.txt` 小红书正文。
    `_` 开头的是写给下一个人的注解（`_note` / `_why` / `_event_why` 这类，
    里面正引着账号所有者那句原话，或者是在解释这场球本身打到了第几轮）——
    连它一起扫会把「把规矩记下来」判成「又违反了规矩」，同一个错这个仓库
    已经犯过好几次。
    """
    import re as _re

    bad = _re.compile(r"[四八]强|十六强|三十二强|(?<!\d)(?:16|32|64)\s*强")

    def outward(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str) and k.startswith("_"):
                    continue
                yield from outward(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from outward(v)
        elif isinstance(obj, str):
            yield obj

    offenders = {}
    for path in _specs():
        hits = sorted({m.group(0) for text in outward(
            json.loads(path.read_text(encoding="utf-8"))) for m in bad.finditer(text)})
        if hits:
            offenders[path.name] = hits
    for path in sorted(SPECS.glob("*.xhs.txt")):
        hits = sorted({m.group(0) for m in bad.finditer(path.read_text(encoding="utf-8"))})
        if hits:
            offenders[path.name] = hits

    fresh = {k: v for k, v in offenders.items() if k not in _LEGACY_QUALIFIER_NAMES}
    assert not fresh, (
        f"这些地方还在写强字轮次：{fresh}。"
        "改成 半决赛 / 1/4 决赛 / 1/8 决赛，再往前写「第几轮」。")
    # ⚠️ `set(offenders) <= _LEGACY_QUALIFIER_NAMES`（上面那条断言）只挡得住
    # 「有真违规却没被豁免」，挡不住反过来那种：豁免表里混进一个根本不违规
    # （或者压根不存在）的名字——那种名字会一直静静地绿着，是一盏恒真的灯。
    # 这条 match-reel 那份原版没有，是反向验证时才发现的漏洞，这里补上。
    missing = _LEGACY_QUALIFIER_NAMES - set(offenders)
    assert not missing, (
        f"豁免表里这些条目已经不违规了（或者文件名写错了）：{sorted(missing)}。"
        "清单只许减不许加——修好了就把它删掉，别留着变成一张许可证。")


# 中文 68→70（2026-08-12）之前就已经发出去、行超宽了的文件。已发的片子
# 不为了字号重渲——这几条不会再被渲染，涨字号对它们没有意义，改宽度预算
# 也换不回一次已经发出去的推送。**只许减不许加**：修好一个（或者它被删除）
# 就从下面拿掉一个。
_LEGACY_WIDE_AT_70 = {
    "eala-osaka-dc2026-sf-studio.json",
    "eala-osaka-dc2026-sf.json",
    "eala-parks-toronto-2026.json",
    "eala-pegula-dc2026-final.json",
    "eala-svitolina-dc2026-qf.json",
    "rybakina-osaka-tor2026-qf.json",
}


def test_字号涨了不许撑破已有的行():
    """**字号不是想涨就能涨的**，它由可用宽和已有的行共同决定。

    2026-08-02 把中文从 62 提到 68（中文是主读行，英文是原文参照，
    62/46 = 1.35 两行几乎一样重，68/46 = 1.48 层级才立住）。
    2026-08-12 又从 68 提到 70——账号所有者：「字幕的字体大小再大一点」。

    能涨多少是量出来的：中文 62→68 只有 2 行超宽（手写的，普遍偏短，有余量），
    68→70 时**新发出去的**（谢尔顿那条，写这次的过程中重新对齐过）0 行超宽，
    但全库里另有 6 个**已经推送过**的老文件超了——它们不重渲，进
    `_LEGACY_WIDE_AT_70`。**而英文 46→50 就有 22 行超**——英文行是切行算法
    按 `_LINE_PX` 排满的，一放大必然大面积溢出，所以这次只动了中文，
    `_LINE_PX`／英文字号原样不动（动 `_LINE_PX` 就是在动折行本身，
    `segment()` 每次 render 都会用它重新切一遍，不是读缓存）。

    这条测试就是那个算式：谁再想调字号，它会当场把代价报出来。
    """
    import json as _json

    from tools.build_interview_clip import _FONT_CACHE, _LINE_PX, _zh_width

    _FONT_CACHE.clear()
    over, checked = {}, 0
    for path in _specs():
        spec = _json.loads(path.read_text(encoding="utf-8"))
        hits = []
        for i, line in enumerate(spec.get("zh") or [], 1):
            checked += 1
            if (w := _zh_width(line)) > _LINE_PX:
                hits.append(f"#{i} {w:.0f}px（可用 {_LINE_PX}）：{line}")
        if hits:
            over[path.name] = hits
    assert checked >= 100, f"只量到 {checked} 行中文，判据大概没找对目录"

    fresh = {k: v for k, v in over.items() if k not in _LEGACY_WIDE_AT_70}
    assert not fresh, (
        "字号撑破了这些行（且不在豁免表里），要么把字号调回去，"
        "要么把这些行改短：\n" + "\n".join(f"{k}: {v}" for k, v in fresh.items()))
    # 反过来也要卡：豁免表里混进一个其实没超宽（或者压根不存在）的名字，
    # 会一直静静地绿着，是一盏恒真的灯。
    missing = _LEGACY_WIDE_AT_70 - set(over)
    assert not missing, (
        f"豁免表里这些条目其实没有超宽（或者文件名写错了）：{sorted(missing)}。"
        "清单只许减不许加——没有真的超宽就把它删掉。")


def test_缩略图墙每一格都要标出秒数():
    """**没有秒数就没法拿它挑封面**——那就退回「听转写猜一个数」。

    封面是唯一决定人点不点的那一屏，而沙箱下不了媒体：以前挑 `frame_at`
    只能猜，渲完十分钟打开看，不对就重渲一趟。storyboard 几百 KB、不用
    ffmpeg，在取字幕那一趟顺手就拿到了。

    yt-dlp 在沙箱里跑不了（IP 被挡），所以这里只测拿到格子之后的那一半：
    **拼图和标秒数**。下载那一半靠 runner 上第一次真跑暴露，
    而它是**加速不是闸**——拿不到就打印原因往下走。
    """
    from PIL import Image

    from tools.build_interview_clip import _tile_sheet

    tiles = [(i, Image.new("RGB", (160, 90), (i * 20 % 256, 60, 90))) for i in range(9)]
    dest = _tile_sheet(tiles, step=1.91, cols=3, dest=ROOT / "_t.jpg")
    try:
        assert dest.exists() and dest.stat().st_size > 0
        sheet = Image.open(dest)
        # 3 列 9 格 → 3 行；每格还要留一条写秒数的地方，所以比 90×3 高
        assert sheet.width >= 160 * 3, sheet.size
        assert sheet.height > 90 * 3, f"没给秒数留位置：{sheet.size}"
    finally:
        dest.unlink(missing_ok=True)


def test_噪声标记要看穿说话人标记():
    """`[applause]` 不是台词，可它带上 `>>` 之后就漏进字幕了。

    自动字幕把 `>>` 和后面那个词并成一个 token，换人说话时的掌声于是是
    `>> [applause]` 而不是 `[applause]`——裸的 `^\\[.*\\]$` 匹配不上。
    冠军致辞那条切出来的第 19 行就是光秃秃的「[applause]」，**它会作为一行
    字幕烧在画面上**。

    和 `test_订正要看穿说话人标记` 是同一个 token 形状咬的第二次，只是
    **后果反过来**：那次是订正悄悄不生效（不吭声），这次是把一个非台词
    印在脸上（很吵，但要渲出来才看得见）。

    反面锚点：`[inaudible] she said` 这种**标记后面还有台词**的不许被丢掉，
    否则「判据宁可窄，不可宽」又要犯一次。
    """
    from tools.build_interview_clip import _NOISE, segment

    for noise in (">> [applause]", "[applause]", ">> [cheering]", ">>", "&gt;&gt;"):
        assert _NOISE.match(noise), f"{noise!r} 该被当成噪声丢掉"
    for real in ("Good", ">> Good", "[inaudible] she said"):
        assert not _NOISE.match(real), f"{real!r} 是台词，不许丢"

    words = [(0.5, ">> So"), (1.0, "thank"), (1.5, "you."),
             (2.0, ">> [applause]"), (5.0, ">> Um,"), (5.5, "yeah.")]
    en = " ".join(s["en"] for s in segment(words, 0.0, 9.0))
    assert "applause" not in en.lower(), f"噪声标记漏进字幕了：{en}"
    assert "thank you." in en and "yeah." in en, f"把台词一起丢了：{en}"


def test_缩略图墙的秒数不许自己摊():
    """秒数要按 storyboard 自己的帧率算，**不能拿「片长 ÷ 存活格数」去摊**。

    两个坑叠在一起，冠军致辞那条同时踩了：

    ① **最后一张 sheet 是残的。** 这条片子的 sb0 前四张 800×450（5×5），
       第五张只有 **800×180**（5×2，装最后 10 帧）。照声明的 5 行硬切，等于
       把它切成 25 条 160×36 的碎条——拼出来是一排「上半截有画面、下半截全黑」
       的格子，**看起来像片尾卡，其实是切错了**。
    ② 碎条大多不是纯黑，于是滤黑之后还剩 121 格（真实是 108）。步长摊成
       4.42 秒，而 YouTube 报的 fps=0.2019 说的是 **4.95 秒一格**。

    错了 12%，**而且不吭声**：标签照印、图照出。判据是拿另一条时间轴对——
    按摊出来的秒数，她**跪地庆祝在 221 秒**，而记分牌上的赛点在 232 秒：
    庆祝早于赛点，不可能。乘回 1.121 正好落在 247.8 秒那句
    `It's Eala's. Magical moment.` 上。

    这张图唯一的用途就是挑 `cover.frame_at`，所以骗的正是它要干的那件事。
    """
    import email.mime.image
    import email.mime.multipart
    import io as _io

    from PIL import Image

    from tools.build_interview_clip import _mhtml_tiles

    # ⚠️ **黑格要有一个落在中间**，不能只放在末尾。真实数据的黑格都在最后
    # （5×5×4 + 8 帧），而那种情况下「按原位编号」和「按存活第几个编号」
    # **算出来一模一样**——拿它当 fixture，序号那条断言就是恒真的。
    # 第一版就是这么写的：把实现退回 `len(tiles)` 重跑，测试照样绿。
    # 中间那一格黑（画面淡入淡出就会有）才让两种编号分叉。
    blanks = {7, 33, 34}                            # 中间一格 + 末尾两格

    def sheet(rows: int, base: int) -> bytes:
        im = Image.new("RGB", (160 * 5, 90 * rows))
        for iy in range(rows):
            for ix in range(5):
                idx = base + iy * 5 + ix
                rgb = (0, 0, 0) if idx in blanks else (40 + idx % 200, 90, 60)
                im.paste(Image.new("RGB", (160, 90), rgb), (ix * 160, iy * 90))
        buf = _io.BytesIO()
        im.save(buf, "JPEG")
        return buf.getvalue()

    msg = email.mime.multipart.MIMEMultipart()
    for rows, base in ((5, 0), (2, 25)):           # 一张满的 + 一张残的
        msg.attach(email.mime.image.MIMEImage(sheet(rows, base), "jpeg"))
    path = ROOT / "_sb_test.mhtml"
    path.write_bytes(msg.as_bytes())
    try:
        tiles = _mhtml_tiles(path, rows=5, columns=5, tile_w=160, tile_h=90)
    finally:
        path.unlink(missing_ok=True)

    want = [i for i in range(35) if i not in blanks]
    assert [t.size for _, t in tiles] == [(160, 90)] * len(want), (
        "残 sheet 被按整格网格硬切了——切出来的是碎条，不是缩略图："
        f"{sorted({t.size for _, t in tiles})}")
    assert [i for i, _ in tiles] == want, (
        "序号不是原位：丢掉中间那格黑的之后，后面每一格的时刻都会往前挪，"
        f"而标签看起来一样权威。拿到的是 {[i for i, _ in tiles]}")

    # 步长的出处：`fps` 优先，按格数摊只能是退路。
    # **真调一次函数**——查源码文本的断言防得住「有人把它删了」，
    # 防不住「条件写反了」（第一版就是那么写的，把 `fps > 0` 改成
    # `fps < 0` 照样绿）。喂的是当时真实的那组数。
    from tools.build_interview_clip import storyboard_step

    sb0 = {"fps": 0.20186915887850468}              # 这条片子 sb0 报的
    dur, buggy_n = 534.84, 121                      # 碎条没滤干净时的格数
    step, shared = storyboard_step(sb0, dur, buggy_n)
    assert not shared, "报了 fps 还去摊"
    assert abs(step - 4.954) < 0.01, f"步长该是 1/fps＝4.954 秒，拿到 {step:.3f}"
    assert abs(step - dur / buggy_n) > 0.4, (
        f"步长跟「片长÷格数」（{dur / buggy_n:.3f}）一样——那正是错了 12% 的那个数")

    fallback, shared = storyboard_step({}, dur, 108)
    assert shared and abs(fallback - dur / 108) < 0.01, "没有 fps 时要退回摊，并且说出来"


def test_缩略图墙只在取字幕那一趟出():
    """出片那趟不该再下一次——它已经有源片了，而且那趟最贵。"""
    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    call = body.index("storyboard_sheet(spec[")
    guard = body.rindex('args.stage == "subs"', 0, call)
    assert call - guard < 300, "缩略图墙没挂在 subs 那一档上"


def test_缩略图墙两头都不许进仓库():
    """缩略图墙是**挑封面用的草稿**，runner 和本地两头都要挡住。

    这条规矩原来只写在了 runner 那一半：「丢掉不进仓库的中间物」里有
    `rm -f "$D"/storyboard.jpg`。可**本地** `--stage subs` 生成的那一份
    没有任何东西管它——2026-08-04 一张 617 KB 的图就这么躺在
    `output/interviews/pegula-eala-dc2026-final/` 里等着被 `git add` 吃进去，
    是 stop hook 报「有未跟踪文件」才发现的。

    又是「两处各配一遍必分叉」。所以两头一起钉：

    - `.gitignore` 要有一条能匹配上它的规则（**真跑一次 `git check-ignore`**，
      不是查文件里有没有这串字——`output/**/storyboard.jpg` 写成
      `output/*/storyboard.jpg` 同样能通过文本断言，却匹配不上真实路径）
    - 工作流那条 `rm` 不许被删掉（本地忽略了，runner 上还是会生成一份，
      而 runner 那边 `git add <目录>` 吃的是索引不是 .gitignore 之外的判断）

    ⚠️ 顺带钉住**仓库里现在一张都没有**——防的是「规则加上了，可之前
    已经提交进去的那些还在」，那种情况下这条测试会假绿。
    """
    import subprocess  # noqa: PLC0415

    probe = "output/interviews/__probe__/storyboard.jpg"
    r = subprocess.run(["git", "check-ignore", "-q", probe],
                       cwd=ROOT, capture_output=True)
    assert r.returncode == 0, (
        f".gitignore 没挡住 {probe}——本地 `--stage subs` 生成的缩略图墙"
        "会被 `git add` 吃进仓库（一张就是六百多 KB）")

    step = next((s for s in _steps() if "storyboard.jpg" in _step_run(s)), None)
    assert step is not None, (
        "工作流里没有一步删 storyboard.jpg。**本地忽略了不等于 runner 上安全**："
        "runner 那边是 `git add <目录>`，走的是索引")
    assert re.search(r"rm\s+-f\b[^\n]*storyboard\.jpg", _step_run(step)), (
        f"步骤「{step.get('name')}」提到了 storyboard.jpg，但不是在删它")

    tracked = subprocess.run(["git", "ls-files", "output/**/storyboard.jpg"],
                             cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert not tracked, (
        f"仓库里已经躺着 {len(tracked)} 张缩略图墙：{tracked[:3]}。"
        "加规则挡不住已经提交进去的——要 `git rm --cached` 一遍，"
        "否则这条测试对它们是绿的")


def test_只出海报那一档要够得着而且真的短():
    """**开关落在 CLI 里不算落地，工作流够不着就等于零。**

    `match-reel` 的 `--dry-run` / `--cover-only` 就是这么白做的：加进 CLI 的
    那个提交没动工作流的 `mode`，而源片只在 runner 上活过几分钟——
    「能用的那台机器上没有开关，有开关的那台机器上没有源片」。

    这一档存在的理由是账：2026-08-04 一晚渲了五趟，**四趟是为了换封面**，
    每趟六分钟外加一个 50~70 MB 的永久 blob，而真正变的只有第一帧。
    量过：`.git` 6.4 GB 里 2.9 GiB 是同一路径的旧版本。
    所以两头都要钉：**入口够得着** + **那条路真的短**。
    """
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github" / "workflows"
                         / "interview-clip.yml").read_text(encoding="utf-8"))
    on = wf.get("on") or wf[True]      # YAML 1.1 把裸的 on 解析成布尔 True
    options = on["workflow_dispatch"]["inputs"]["mode"]["options"]
    assert "cover" in options, f"工作流的 mode 只有 {options}——CLI 加了也够不着"

    step, = [s for s in _steps() if s.get("name") == "只出海报（不出片）"]
    assert step.get("if") == "github.event.inputs.mode == 'cover'"
    run = _step_run(step)
    assert "--stage cover" in run, "那一步没跑 `--stage cover`"
    # **短**的判据是它不碰这几样：碰了就说明有人把它写成了完整 render
    for banned in ("--stage render", "--stage verify", "push_reel.py",
                   "faster_whisper"):
        assert banned not in run, (
            f"「只出海报」那一步出现了 `{banned}`——它就不短了，"
            "这一档的全部意义是不出片、不往仓库里塞 mp4")


def test_出海报只有一份实现():
    """`render` 和 `--stage cover` 必须走**同一个** `cover_poster`。

    复制一份进快速预览，分叉的表现是「预览看着对、成片里不对」——最难查的
    那一类。这个仓库为 `_still_to_clip` 那对函数栽过两次：一次加参数没跟着
    委托链改到底，一次是一个函数两个 return 只改了一个。
    """
    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    assert src.count("def cover_poster(") == 1, "cover_poster 有不止一份定义"
    assert src.count('"-frames:v", "1"') == 1, (
        "抽封面帧那句 ffmpeg 出现了不止一次——多半是复制了一份进 cover 那一档")
    body = src.split("def render(")[1]
    assert "cover_poster(spec, src, outdir" in body, (
        "render 没有走 cover_poster，两处必分叉")


def test_出海报那一档不许被出片的闸挡住():
    """挑封面排在转写核对**之前**——拿出片的闸挡它，等于逼人先把校验走完
    才能看一眼封面，而那正是这一档要省掉的那六分钟。
    """
    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    cover = src.split('if args.stage == "cover":')[1].split(
        'if args.stage == "render":')[0]
    # ⚠️ **先去掉整行注释再扫。** 这一档的注释里正写着「不设
    # `transcript_verified` 那几道闸」——连注释一起扫，「把理由记下来」会被
    # 判成「又挂上了那道闸」。写这条测试时当场被自己的注释误伤了一次，
    # 而这个形状这个仓库已经犯过五次（`_step_run` 的 docstring 记着）。
    cover = "\n".join(ln for ln in cover.splitlines()
                      if not ln.lstrip().startswith("#"))
    for gate in ("transcript_verified", "_unresolved_suspects",
                 "_unresolved_gaps"):
        assert gate not in cover, f"cover 那一档挂着出片的闸 `{gate}`"
    # 反过来：出片那一档必须仍然挂着，别为了放行 cover 把它一起拆了
    render_stage = src.split('if args.stage == "render":')[1]
    assert "transcript_verified" in render_stage, "出片那道闸没了"


# ── 第二个源：Tennis TV ──────────────────────────────────────────────
#
# 2026-08-05 商竣程那条起，这条线不再只有 `@wta` 的 YouTube 集锦一个源。
# 起因是**结构性的**：ATP 男子的场上采访不上 YouTube。蒙特利尔那一站扫遍
# ATP Tour / Tennis TV / 赛事官方（深扫 90 条）/ Tennis Channel / 三个专搬
# 采访的频道 / 五组英法查询词，一条都没有；而**同一组查询词在多伦多（女子）
# 那边有**——所以这不是「没搜到」，是这一站男子不公开发。
#
# 下面这几条钉的是：接第二个源之后，原来那些「反正是 YouTube」的假设不许
# 悄悄失效。


def test_判是不是YouTube要按主机名():
    """⚠️ **不许按字符串里有没有 `youtube` 判。**

    `https://example.com/?ref=youtube.com` 会从中间匹配上，于是一条根本不是
    YouTube 的源会被当成 YouTube——然后去拉一个不存在的自动字幕轨，报出来的
    错指向完全错误的方向。判据宁可窄，不可宽。
    """
    from tools.build_interview_clip import is_youtube

    for url in ("https://www.youtube.com/watch?v=abc",
                "https://youtube.com/watch?v=abc",
                "https://youtu.be/abc",
                "https://m.youtube.com/watch?v=abc"):
        assert is_youtube(url), url
    for url in ("https://www.tennistv.com/videos/4554084/montreal-2026-r2-shang-interview",
                "https://example.com/?ref=youtube.com",
                "https://notyoutube.com/watch?v=abc",
                "https://tennis-tv.vod.streamamg.com/x.m3u8"):
        assert not is_youtube(url), url


def test_只有TennisTV那条要解析别的源原样传过去(monkeypatch):
    """`media_url` 是**页面地址 → 真能下的地址**那一步，只对 Tennis TV 生效。

    反面同样重要：YouTube 和任何别的地址必须**原样返回**，一旦顺手把它们也
    塞进解析器，这条线上跑了半年的六条 spec 会一起坏掉。
    """
    from tools import build_interview_clip as m

    called = []

    def _fake(candidate, **kw):
        called.append(candidate.url)
        return type("M", (), {"playback_url": "https://cdn.example/x.m3u8",
                              "duration_ms": 74000})()

    monkeypatch.setattr(
        "tennislive.video.official.fetch_tennistv_video_metadata", _fake)

    yt = "https://www.youtube.com/watch?v=abc"
    assert m.media_url(yt) == yt
    assert m.media_url("https://cdn.example/already.m3u8") == \
        "https://cdn.example/already.m3u8"
    assert not called, f"非 Tennis TV 的地址也去解析了：{called}"

    tt = "https://www.tennistv.com/videos/4554084/montreal-2026-r2-shang-interview"
    assert m.media_url(tt) == "https://cdn.example/x.m3u8"
    assert called == [tt]


def test_下载那一步真的走了解析(monkeypatch, tmp_path):
    """**只测 `media_url` 自己对拦不住位置错**：它写出来了、`yt_download` 不调，
    行为测试照样绿，而出片那一步会拿页面地址去喂 yt-dlp，报
    `This video is only available for registered users`——一句指向
    「cookie 过期了」的错，而真相是这条路根本没接上。
    """
    from tools import build_interview_clip as m

    seen = {}

    def _fake_run(cmd, **kw):
        seen["url"] = cmd[-1]
        (tmp_path / "s.mp4").write_bytes(b"x")
        return type("P", (), {"returncode": 0})()

    monkeypatch.setattr(m, "media_url", lambda u: f"RESOLVED::{u}")
    monkeypatch.setattr(m.subprocess, "run", _fake_run)
    m.yt_download("https://www.tennistv.com/videos/1/x", tmp_path / "s.mp4",
                  "b", {})
    assert seen["url"] == "RESOLVED::https://www.tennistv.com/videos/1/x", \
        "yt_download 没走 media_url，页面地址直接喂给了 yt-dlp"


def test_非YouTube的源不许编一条带时刻的YouTube链接():
    """核对表是**给人对着听的那一张表**，链接指错地方比没有链接坏得多。

    原来是无条件按 `/` 切最后一段当 video id：喂一条 Tennis TV 地址进去会拼出
    `https://youtu.be/montreal-2026-r2-shang-interview?t=17`——**看着能点，
    点开是 404**。又一次「喊错了是主动给出一个错答案」。
    """
    from tools.build_interview_clip import _yt_at

    assert _yt_at("https://www.youtube.com/watch?v=abc", 17.4) == \
        "https://youtu.be/abc?t=17"
    out = _yt_at("https://www.tennistv.com/videos/4554084/x-interview", 17.4)
    assert "youtu" not in out, f"给非 YouTube 的源编了 YouTube 链接：{out}"
    assert "17.4" in out and out.startswith("https://www.tennistv.com/"), out


def test_非YouTube的源不许在核对表里编一颗点不动的按钮():
    """上一条只管住了 `_yt_at` 自己，**调用方把它又破了一次**。

    `_yt_at` 对非 YouTube 的源**故意**回一句带汉字的说明
    （`<url>（片内 18.7 秒）`），而核对表无条件包上 markdown 链接语法，
    于是那句说明连同括号一起进了 href：

        [▶](https://players.brightcove.net/…?videoId=6402850037112（片内 0.0 秒）)

    渲出来是一颗**点不动的按钮**，而它和一颗点得动的长得一模一样——正是
    `_yt_at` 的 docstring 要防的那件事，只是躲到了外面一层。

    判据钉两头：`_jump_md` 的行为，**以及没有别的地方再去包 `_yt_at`**。
    只验行为拦不住这个错——`_yt_at` 单测一直是绿的，坏的一直是调用方。
    """
    from tools.build_interview_clip import _jump_md

    yt = _jump_md("https://www.youtube.com/watch?v=abc", 17.4, "▶")
    assert yt == "[▶](https://youtu.be/abc?t=17)", yt

    other = _jump_md("https://players.brightcove.net/1/x_default/"
                     "index.html?videoId=640285", 18.74, "跳过去")
    assert "](" not in other, f"给钉不住时刻的源编了一颗点不动的按钮：{other}"
    assert "18.7" in other, other

    # 位置这一头：源码里不许再出现 `[…]({_yt_at(…)})`。
    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    bad = re.findall(r"\]\(\{_yt_at\(", _code_only(src))
    assert not bad, ("又把 `_yt_at` 包进 markdown 链接了——"
                     f"非 YouTube 的源会渲出一颗点不动的按钮（{len(bad)} 处）")


def test_非YouTube的源没有自动字幕轨要说清楚而不是去拉(monkeypatch, tmp_path):
    """只有 YouTube 有自动字幕轨。对别的源调 yt-dlp 只会拿到一句方向完全错误的
    报错（Tennis TV 报的是「只对注册用户开放」，读起来像 cookie 过期）。

    而**真相是这条路根本不存在**，第一份转写得自己跑 ASR——报错要把这条出路
    说出来，还要提醒 `asr_model` 那道闸（见下一条）。
    """
    from tools import build_interview_clip as m

    monkeypatch.setattr(m.subprocess, "run",
                        lambda *a, **k: pytest.fail("不该去拉自动字幕"))
    with pytest.raises(SystemExit) as e:
        m.fetch_words("https://www.tennistv.com/videos/1/x", tmp_path, {})
    said = str(e.value)
    assert "不是 YouTube" in said
    assert "ASR" in said and "cap_" in said, f"没说出路：{said}"
    assert "asr_model" in said, f"没提醒第二份 ASR 那道闸：{said}"


def test_算分歧率之前要把填词从两边一起去掉():
    """⚠️ **这道闸量的是「源可不可信」，不是「说话人有多磕巴」。**

    `uh`/`um` 这类填词 whisper 系统性地会丢，丢不丢跟第一份源可不可信毫无关系
    ——它是这把尺子自己的噪声。留着它们，一个磕巴的人就会把分歧率顶穿天花板，
    而逐处看下来一句语义分歧都没有（2026-08-14 中岛布兰登那条：`small.en`
    19.8%、`medium.en` 19.0%，双双越过 0.18，而 394 词里 42 个是填词）。

    **去掉不是把闸放松**：两边共同的噪声消掉之后，剩下的差异全是真实词分歧，
    同样的门槛对真问题更敏感。下面第 3 段就是钉这一头的。
    """
    from tools import build_interview_clip as m

    # ① 只差填词 → 去掉之后必须是 0
    first = "Um, I'd like to uh thank my team, uh, all of you."
    second = "I'd like to thank my team, all of you."
    rate, a, b, _ = m.disagree_rate(first, second)
    assert rate == 0, f"只差填词却报了 {rate:.1%}：{a} vs {b}"
    assert "uh" not in a and "um" not in a, f"填词没去干净：{a}"

    # ② 反向验证：**不去填词的话，同一对就是一个很难看的数**——
    #    这一段证明上面那个 0 是「去掉填词」买来的，不是这对样本本来就一样
    raw = [w for w in re.sub(r"[^\w\s']", " ", first.lower()).split() if w]
    raw2 = [w for w in re.sub(r"[^\w\s']", " ", second.lower()).split() if w]
    sm = difflib.SequenceMatcher(None, raw, raw2, autojunk=False)
    naive = 1 - sum(x.size for x in sm.get_matching_blocks()) / len(raw)
    assert naive > 0.2, f"这对样本没有区分度，反向验证是空的：{naive:.1%}"

    # ③ **真的实词分歧一个都不许被吃掉。** 去填词只许消掉填词，
    #    否则这道闸就真的被放松了——那正是它唯一不能出的错。
    rate2, _, _, _ = m.disagree_rate("I thank my team for the support",
                                     "I thank my coach for the support")
    assert rate2 > 0, "实词换掉了却报 0，这道闸被放松了"

    # ④ 名单宁可窄，不可宽：`eh` 在加拿大英语里是真词，不许当填词吃掉
    assert "eh" in m.compare_tokens("It was great, eh")
    assert "ah" in m.compare_tokens("Ah, that was close")


def test_第二份ASR必须换个模型否则那道闸是空的(monkeypatch, tmp_path):
    """⚠️ **这是接第二个源之后最容易空掉的一道闸。**

    `verify_transcript` 原来的前提是「第一份来自 YouTube 的 ASR，第二份是
    faster-whisper」——两边天然不同。而非 YouTube 的源没有自动字幕轨，
    **第一份也是 whisper 跑的**；这时候不检查的话，同一个模型跑两遍必然逐词
    一致，分歧率恒为 0%，报告一片绿，**而它什么都没验证**。

    仓库里 `en` / `en-orig` 那次记的就是这个形状：同一份 ASR 换个名字，拿它
    当交叉验证是自欺。
    """
    from tools import build_interview_clip as m

    spec = {"slug": "x", "url": "https://www.tennistv.com/videos/1/x",
            "start": 0, "end": 10, "asr_model": "small.en",
            "whisper_model": "small.en"}
    with pytest.raises(SystemExit) as e:
        m.verify_transcript(spec, [], tmp_path)
    assert "同一个模型跑两遍" in str(e.value)

    # 反过来：换了模型就不该被这道闸拦住。**用哨兵，别靠「反正会抛点什么」**——
    # 那样这半条断言在装了 faster-whisper 的机器和没装的机器上走的是两条路
    # （一条死在下载、一条死在 import），而这个仓库栽过「同一条测试在两个地方
    # 跑的是两条不同的路」。
    spec["whisper_model"] = "medium.en"
    monkeypatch.setattr(m, "yt_download",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("到下载了")))
    with pytest.raises(Exception) as e2:
        m.verify_transcript(spec, [], tmp_path)
    assert "同一个模型跑两遍" not in str(e2.value), \
        "换了模型还被拦，这道闸拦宽了"


def test_换模型那道闸要排在导入whisper之前():
    """⚠️ **只测行为拦不住位置错，而这一处的位置错只在 CI 上现形。**

    那道闸查的是 spec 的形状，一个模型都不用加载。第一版把它写在
    `from faster_whisper import WhisperModel` **后面**——于是在任何没装
    faster-whisper 的机器上它根本走不到，而那正是 CI 那台：本地全绿，
    CI 报 `No module named 'faster_whisper'`（PR #198，run 30980157757）。

    这是「形状校验里不许混进环境检查」的镜像：**环境依赖不许挡在形状校验
    前面**，否则失败发生在第 90 秒而不是第 5 秒，而且挡住的是判据本身。
    """
    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    body = src.split("def verify_transcript(")[1].split("\ndef ")[0]
    gate = body.index("同一个模型跑两遍")
    imp = body.index("from faster_whisper import")
    assert gate < imp, (
        "换模型那道闸排在 `from faster_whisper import` 后面——"
        "没装这个包的机器（CI 就是）永远走不到它")


def test_两份转写各是谁两张报告都要照实写():
    """标签原来写死是「YouTube 自动字幕」和「small.en」。

    第一份那一半接 Tennis TV 时修过；**第二份那一半漏了**——`probe_gap_speech`
    的表头一直印着 `small.en`，而萨巴伦卡那条 spec 写的是 `medium.en`，
    Brightcove 源也根本没有 YouTube 自动字幕（第一份也是我们自己跑的）。
    **闸跑的是对的，报告印的是错的**，而报告存在的全部理由就是告诉人
    「这几秒是拿谁跟谁比出来的」。

    ⚠️ 上一版的判据只扫 `verify_transcript` 的函数体——抽成公共函数之后
    **主语就没了**（`split()` 拿到的那段里再也没有 `asr_model`）。
    换成钉行为 + 钉「两张报告都调它」，两处出处合并成一处。
    """
    from tools.build_interview_clip import DEFAULT_WHISPER, _first_source_label, _second_model

    assert _first_source_label({}) == "YouTube 自动字幕", "退路（真是 YouTube 那条）没了"
    assert _first_source_label({"asr_model": "small.en"}) == "ASR（small.en）"
    assert _second_model({}) == DEFAULT_WHISPER
    assert _second_model({"whisper_model": "medium.en"}) == "medium.en"

    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    for fn in ("verify_transcript", "probe_gap_speech"):
        body = _code_only(src.split(f"def {fn}(")[1].split("\ndef ")[0])
        assert "_first_source_label(spec)" in body, f"{fn} 没按 spec 决定第一份叫什么"
        assert "_second_model(spec)" in body, f"{fn} 把第二份的模型名写死了"
        # 裸的子串，不是 `"small.en"`——写死的那次是嵌在一句中文里的
        # （`第二份 ASR 是 \\`small.en\\`（英语专用）`），带引号的判据抓不到它。
        assert "small.en" not in body, f"{fn} 里还留着写死的 small.en"
        assert "YouTube" not in body, f"{fn} 里还留着写死的「YouTube」"


def test_采访片的片尾要和正片拼得起来(tmp_path):
    """**真跑一次 `-c copy` 的 concat。**

    这条线走 `concat` demuxer + `-c copy`，是三条线里对流参数最挑的一条：
    帧率、采样率、**声道数**差一项就静默丢流，成片从某一秒起没声音，
    **而 ffmpeg 不报错**（封面那一路的注释里已经为同一件事记过一次）。

    喂现成的 PNG 当层（`layers=`），所以不碰 Chromium 也不合语音，CI 上跑得起来。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    from tennislive.video import outro_page  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"

    layers = {}
    for name in ["base"] + [k for k, *_ in outro_page.LAYERS]:
        f = tmp_path / f"{name}.png"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             f"color=c=gray:s={outro_page.VIDEO_W}x{outro_page.VIDEO_H}",
             "-frames:v", "1", "-pix_fmt", "rgba", str(f)], check=True)
        layers[name] = f

    # 片尾：参数照 `_build_outro` 传的那一组
    outro = outro_page.render_clip(
        tmp_path, 4.0, fps_expr="25", fps=25.0, chromium="",
        dest=tmp_path / "_outro.mp4", audio_rate="48000", preset="medium",
        crf="20", audio_bitrate="128k", audio_channels=2, layers=layers)

    # 「正片」：参数照 `render()` 里那一组
    body = tmp_path / "body.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "color=c=navy:s=1080x1440:r=25",
         "-f", "lavfi", "-i", "sine=frequency=200:sample_rate=48000",
         "-t", "6", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-r", "25", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
         "-ar", "48000", "-ac", "2", str(body)], check=True)

    lst = tmp_path / "cc.txt"
    lst.write_text(f"file '{body.name}'\nfile '{outro.name}'\n", encoding="utf-8")
    joined = tmp_path / "joined.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(joined)], check=True)

    def _dur(stream):
        return float(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", stream,
             "-show_entries", "stream=duration", "-of", "csv=p=0", str(joined)],
            check=True, capture_output=True,
            text=True).stdout.strip().rstrip(","))

    assert abs(_dur("v:0") - 10.0) < 0.3, (
        f"拼出来只有 {_dur('v:0'):.2f}s，要的是 6+4=10s——片尾的流参数和正片对不上")
    # **音轨也要在**：`-c copy` 参数不匹配时会丢掉其中一条流，而它不报错
    assert abs(_dur("a:0") - _dur("v:0")) < 0.4, (
        f"音轨 {_dur('a:0'):.2f}s vs 画面 {_dur('v:0'):.2f}s——concat 丢了一条流")


def test_采访片两条路都要接片尾():
    """有封面和没封面**不许是两条不同的出片路径**。

    ⚠️ **这条判据换过一次主语，换的理由本身就是它要防的东西。**

    第一版盯的是「没有封面那一支里有没有 outro」——因为当时 `render()` 真的
    按 `if not spec.get("cover")` 分了两支、各 concat 一次，而加片尾时只改了
    一支，没有封面的片子悄悄少一页。

    加解读卡时同一件事要第三次发生，所以把清单收成了**一份**：谁进谁不进各
    只有一处决定。原来那句 `body.split('if not spec.get("cover"):')` 于是
    `IndexError`——**主语没了就得换判据**，留着它就是一条常年红。

    现在钉的是那个结构本身：片尾只有一处 append，而且**不在任何 cover 分支
    里面**。
    """
    src = Path("tools/build_interview_clip.py").read_text(encoding="utf-8")
    body = src.split("def render(")[1].split("\ndef ")[0]
    code = [ln for ln in body.splitlines() if not ln.lstrip().startswith("#")]

    outro = [i for i, ln in enumerate(code) if "_build_outro(" in ln]
    assert len(outro) == 1, f"片尾不是只有一处：{outro}"

    # **不许嵌在任何分支里面**，判据是缩进——它就是嵌套本身。
    #
    # ⚠️ 第一版判的是「前面最近的那个 `if` 是不是 cover」，当场误伤：
    # `if spec.get("cover"):` 确实排在前面，但那是**往清单里加封面**的单行块，
    # 片尾并不在它里面。又一次「判据宁可窄，不可宽」——只不过这次糊的不是
    # 范围，是层级。
    line = code[outro[0]]
    assert len(line) - len(line.lstrip()) == 4, (
        f"片尾那行缩进了 {len(line) - len(line.lstrip())} 格，说明它嵌在某个分支里。"
        "没走到那个分支的片子会悄悄少一页，而它和「本来就没有片尾」长得一模一样")

    # 而且要真的进清单
    assert "parts.append(outro)" in "".join(code), "片尾没进拼接清单"


def test_顶栏次行要在虚化背景上读得出来():
    """账号所有者 2026-08-05：「顶部的小字，灰色的看不太清，改成可以看清楚的」。

    原来是 **32 号 / `#a9bcb2` / 没有描边**。`#a9bcb2` 不是随便挑的——它正是
    CLAUDE.md 里登记的「次级灰绿」。**但那套色是为深绿实色卡定的**，而顶栏压
    的是**虚化过的比赛画面**：底色一路在变，同一个灰绿在亮的地方就糊掉了。
    调色板的适用前提换了，颜色本身却照搬了过来。

    所以三样一起改，缺一个都不够：**字号**（32→38，太小的字先输在笔画上）、
    **提亮**（`#a9bcb2`→`#d5e2db`）、**描边**（0→1.5，实色卡不需要它，
    变化的背景需要）。⚠️ 比分那段跟着从 38 提到 44——它是**故意比基准大一档**
    的强调，基准提上去而它不动，这个层级就被压平了（`test_顶栏量宽度要按每段
    自己的字号` 当场抓住了这一点）。

    这里钉的是**不许退回去**，不是钉死具体数值：三条判据各自摆出方向。
    """
    import tools.build_interview_clip as clip

    head = clip._ASS_HEAD
    b = [ln for ln in head.splitlines() if ln.startswith("Style: HEADB,")]
    assert len(b) == 1, f"HEADB 样式不是一条：{b}"
    fields = b[0].split(",")

    # ① 字号只许涨不许缩。宽度有余量（实测最宽的一条 815/984px），缩回去
    #    只会把「看不清」原样带回来
    assert clip._HEAD_SIZE["b"] >= 38, (
        f"顶栏次行缩回了 {clip._HEAD_SIZE['b']} 号——账号所有者指出过看不清")

    # ② 必须有描边。背景是**变化的画面**不是实色卡，没有描边时字在亮处会消失。
    #    ⚠️ Outline 是第 **15** 位不是 16——`split(",")` 之后 `Style: HEADB`
    #    整个算第 0 位，后面每一项都跟着挪一位。第一版按 16 取，读到的是
    #    Shadow（0），于是这条断言当场把**已经改好**的样式判成没描边。
    outline = float(fields[15])
    assert outline > 0, "顶栏次行没有描边——压在虚化画面上，亮的地方会读不出来"

    # ③ 颜色不许再暗回去。ASS 是 &H00BBGGRR，比一比亮度就够
    #    （CLAUDE.md 记过反例：一度用到 `#7f958a`，反馈就是「文字有点模糊」）
    raw = fields[3].strip().lstrip("&H").rstrip("&")
    bb, gg, rr = (int(raw[-6:-4], 16), int(raw[-4:-2], 16), int(raw[-2:], 16))
    lum = 0.2126 * rr + 0.7152 * gg + 0.0722 * bb
    old = 0.2126 * 0xA9 + 0.7152 * 0xBC + 0.0722 * 0xB2      # #a9bcb2
    assert lum > old, f"顶栏次行的颜色比原来那版还暗（{lum:.0f} ≤ {old:.0f}）"

    # ④ 比分仍然要比基准大一档——不然强调就没了
    assert clip._SCORE_PX > clip._HEAD_SIZE["b"], "比分不再比基准大，强调被压平了"


# ── 解读卡（提炼）────────────────────────────────────────────────────────
#
# 来路：视频号 2026-08-04 判了伊埃拉捧杯致辞那条「二次创作部分信息增量不足，
# 如素材简单增加标题、字幕或简易配音」。账号所有者 2026-08-05：「以后赛后开麦，
# 要找总结提炼下」，体裁定的是**保留原声主体、前后加解读卡**。


def _iv_specs():
    return sorted(Path("specs/interviews").glob("*.json"))


def test_没有解读卡的老片子只许减不许加():
    """豁免名单的**自检**：表里每个 slug 必须真的存在、而且真的还没有解读卡。

    ⚠️ 一个会过期的名单和一条常年红的检查是同一个毛病，而这条更阴——
    **写错一个名字，豁免就成了一盏恒真的绿灯**：那条 spec 既不在名单里
    （名字对不上），也没人发现名单里那个名字指向空气。
    """
    import tools.build_interview_clip as clip

    have = {p.stem for p in _iv_specs()}
    ghosts = clip._NO_TAKEAWAY_LEGACY - have
    assert not ghosts, f"豁免名单里这几个 slug 不存在，等于没豁免任何东西：{ghosts}"

    for slug in clip._NO_TAKEAWAY_LEGACY:
        d = json.loads((Path("specs/interviews") / f"{slug}.json").read_text("utf-8"))
        assert not d.get("takeaway"), (
            f"{slug} 已经写了解读卡，就该从豁免名单里划掉——"
            "名单只许减不许加")


def test_ask漏问号的豁免名单只许减不许加():
    """`_LEGACY_ASK_NO_QUESTION_MARK` 的自检，跟上一条同一个理由：表里每个
    slug 必须真的存在、而且真的还漏着问号——写错一个名字，或者哪天有人把
    那条 spec 的问号补上了，豁免就该跟着划掉，不然它会挡住一条真正的错。
    """
    import tools.build_interview_clip as clip

    have = {p.stem for p in _iv_specs()}
    ghosts = clip._LEGACY_ASK_NO_QUESTION_MARK - have
    assert not ghosts, f"豁免名单里这几个 slug 不存在，等于没豁免任何东西：{ghosts}"

    for slug in clip._LEGACY_ASK_NO_QUESTION_MARK:
        d = json.loads((Path("specs/interviews") / f"{slug}.json").read_text("utf-8"))
        ask = str((d.get("takeaway") or {}).get("close", {}).get("ask", ""))
        assert not ask.rstrip().endswith(("？", "?")), (
            f"{slug} 的 ask 已经带问号了，就该从豁免名单里划掉——"
            "名单只许减不许加")


def test_新的采访片必须有解读卡而且引的是他真说过的话():
    """两头都钉。**这条只吃 `specs/`**，不读 `output/`——CI 的稀疏检出把产物
    挡在外面，拿产物当主语的判据在 CI 上会静静地变成一盏恒真的绿灯。
    """
    import tools.build_interview_clip as clip

    checked = 0
    for p in _iv_specs():
        d = json.loads(p.read_text("utf-8"))
        if p.stem in clip._NO_TAKEAWAY_LEGACY:
            continue
        # ⚠️ **没有 `zh` 的 spec 还渲不动**，别拿这条闸拦它。
        #
        # 这是闸的第一版留下的一个死结：`mode=subs`（取字幕切行）正是产出
        # 「写解读卡所需材料」的那一步，而**它要求 spec 先进仓库**——于是
        # 「要写解读卡」和「还没有内容可写」互相挡着，新选题一条都开不了头。
        #
        # 判据跟着**这份 spec 渲不渲得动**走：`segment` 之后没有 `zh` 时
        # `--stage subs` 打印完就 `return 0`，根本走不到 `render()`。
        # 所以有 `zh` 才要求有解读卡——`render()` 那道闸一个字没松。
        if not d.get("zh"):
            continue
        checked += 1
        clip.check_takeaway(d)          # 缺字段 / 引错话 / 占比不够都会抛
    # 目前七条全在豁免名单里（都是规矩之前发的），所以 checked 可能是 0。
    # **但这条测试不许因此变成空转**——下面那两条用假 spec 证明闸真的咬得动。
    assert checked >= 0


def test_落点卡引一句他没说过的话要当场报错():
    """这张卡唯一致命的错法：「这才是真正的落点」后面跟一句他没说过的话。

    **渲出来一点异常都没有**——版式正常、时长正常、闸全绿。所以只能在 spec
    这一层拦。⚠️ 比对时两边的标点都剥掉：卡上按正常中文写（带逗号），而
    `zh` 里的字幕**按规矩不写标点**，逐字比会永远对不上。
    """
    import tools.build_interview_clip as clip

    base = {
        "slug": "fake-x", "start": 0.0, "end": 50.0, "cover": {"frame_at": 1},
        "zh": ["但更让我高兴的是 我健康了", "我百分百打出了最好的网球"],
        "takeaway": {
            "open": {"point": "「但更让我高兴的是，我健康了」",
                     "facts": ["他说了 4 次「健康」"]},
            "close": {"point": "他谈的不是赢球。", "ask": "他其实在说什么？"}},
    }
    clip.check_takeaway(base)           # 引的是真话，且标点不同也认——不许报

    bad = json.loads(json.dumps(base))
    bad["takeaway"]["open"]["point"] = "「我为整个中国网球感到骄傲」"
    with pytest.raises(SystemExit, match="找不到"):
        clip.check_takeaway(bad)


def test_自有画面占比低不再拒渲只报数(capsys):
    """2026-08-08 账号所有者撤销了「占比不够就拒渲」那道硬闸：
    「就不该有限制时长的这个闸」「要保证原始内容的完整性啊」。

    老版本这条闸曾经拿 217 秒的原声试过，逼着要么剪短要么把卡写厚——
    而那正是这次被撤销的行为：`eala-mcnally-toronto-2026-r3-presser`
    （462 秒的完整发布会）为了顶过占比，硬把一段完整问答挖成了 150.5 秒，
    账号所有者要的是完整内容，不是被这道比例倒逼出来的节选。

    现在同样的 217 秒占比很低（0.8%）也不许再拒渲，只在日志里报个数。
    """
    import tools.build_interview_clip as clip

    spec = {
        "slug": "fake-long", "start": 0.0, "end": 217.0, "cover": {"frame_at": 1},
        "zh": ["我健康了"],
        "takeaway": {"close": {"point": "他谈的不是赢球。", "ask": "为什么？"}},
    }
    clip.check_takeaway(spec)               # 不许再抛 SystemExit
    out = capsys.readouterr().out
    assert "自有画面" in out and "仅供参考，不拒渲" in out

    # 反过来：卡片本身该有的两道闸（有没有、引文对不对）一个字没松，
    # 撤销的只是「占比够不够」这一条
    bad = json.loads(json.dumps(spec))
    del bad["takeaway"]["close"]["ask"]
    with pytest.raises(SystemExit, match="是空的"):
        clip.check_takeaway(bad)


def test_解读卡那道闸要排在下载之前():
    """形状错不该先付一次几百 MB 的下载。

    ⚠️ **只测行为拦不住位置错**：闸排在 `yt_download` 后面时，上面那几条
    行为判据照样全绿，而真实的代价是每次写错 spec 都要等一趟下载。
    """
    src = Path("tools/build_interview_clip.py").read_text("utf-8")
    body = src.split("def render(")[1].split("\ndef ")[0]
    body = "\n".join(ln for ln in body.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert body.index("check_takeaway(") < body.index("yt_download("), (
        "解读卡那道闸排在下载后面了——写错一个字段要等几百 MB 下完才知道")


def test_拼接清单只有一条路():
    """封面、解读卡、正片、片尾**在同一份清单里**，不许按条件分两支各拼一次。

    这儿原来按「有没有封面」分了两支，于是加片尾时只改了一支，没有封面的
    片子悄悄少一页。加解读卡是同一件事第三次——所以清单收成一份，
    **每一段只有一处决定它进不进去**。
    """
    src = Path("tools/build_interview_clip.py").read_text("utf-8")
    body = src.split("def render(")[1].split("\ndef ")[0]
    code = "\n".join(ln for ln in body.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert code.count('"-f", "concat"') == 1, (
        "render() 里 concat 了不止一次——分支一多，下次加东西又会只改一支")
    for piece in ("_takeaway_segments(spec, outdir, \"open\")",
                  "_takeaway_segments(spec, outdir, \"close\")"):
        assert piece in code, f"拼接清单里没有 {piece}"
    assert code.index('"open"') < code.index("parts.append(body)") \
        < code.index('"close"'), "解读卡的位置不对：落点卡在正片前，收尾卡在正片后"


def test_静图转段只有一处写ffmpeg参数():
    """封面和两张解读卡共用 `_still_segment`。

    这条线走 `concat` demuxer + `-c copy`，帧率/采样率/**声道数**差一项就
    静默丢流、成片从某一秒起没声音，**而 ffmpeg 不报错**。参数抄第二遍就是
    在等它分叉。
    """
    src = Path("tools/build_interview_clip.py").read_text("utf-8")
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert code.count('"anullsrc=r=48000:cl=stereo"') == 1, (
        "静音音轨的参数写了不止一处——两处必分叉，而分叉的表现是成片某一秒起没声音")


def test_解读卡的时长跟着它自己的字数走():
    """写两处必分叉，而分叉的表现是「改了文案卡还是老时长，最后一行没读完就切」。"""
    import tools.build_interview_clip as clip

    short = {"point": "他谈的不是赢球。"}
    long_ = {"point": "他谈的不是赢球。", "lead": "主持人问他脑子里在想什么，"
             "他先夸了对手，然后自己把话头转开——", "facts": ["说了 4 次健康", "赢只说了 1 次"]}
    assert clip.takeaway_seconds(short) == clip.TAKEAWAY_MIN_SECONDS
    assert clip.takeaway_seconds(long_) > clip.takeaway_seconds(short), \
        "字多了卡却没变长——那最后一行读不完就切走了"
    assert clip.takeaway_seconds(long_) <= clip.TAKEAWAY_MAX_SECONDS


def test_提炼工具要把没说的词也打出来():
    """频次榜只列**出现过**的词，「一次都没提」在榜上是看不见的。

    这正是这个仓库反复栽的「空结果 ≠ 不存在」：**缺席是信息，
    但缺席不会自己跳出来**。所以观察表是固定打印的，说 0 次也要有一行。
    """
    import tools.interview_takeaway as tk

    assert tk._WATCH, "观察表是空的"
    lines = [
        {"a": 0.0, "en": ">> What's going through your mind?"},
        {"a": 2.0, "en": ">> I'm healthy. I'm happy. Really happy to be healthy."},
    ]
    tt = tk.turns(lines)
    assert [t["who"] for t in tt] == ["主持人", "球员"]

    text = tk.report.__doc__ or ""
    assert text is not None
    # 真跑一次报告：他一个字没提「团队/家人」，报告里必须有那一行
    import json as _json
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        (out / "lines.json").write_text(_json.dumps(lines), encoding="utf-8")
        rep = tk.report({"slug": "t", "start": 0.0, "end": 10.0}, out)
    # ⚠️ **别写成 `"一次都没提" in rep`。** 第一版就是那样，而 `report` 自己的
    # 说明文字里正写着「**「一次都没提」在榜上是看不见的**」——断言被自己的解说
    # 满足了，把标记整个拆掉照样绿。反向验证时才发现（拆了，1 passed）。
    # 这个仓库为「判据被注释误伤」栽过四次，这次是它的镜像：**制造假绿**。
    # 所以要钉在**那一行**上：标签开头、同一行带标记。
    flagged = [ln.strip() for ln in rep.splitlines()
               if ln.strip().startswith("团队/家人") and "一次都没提" in ln]
    assert flagged, ("他一个字没提团队/家人，报告里却没有那一行——"
                     f"没说的词没被打出来，而那一节是这个工具的全部价值\n{rep}")


def test_提炼原料只算片内那一段():
    """`cap_*.json3` 是**整条源片**的转写，报告说的是**这条片子**——
    spec 剪过 `start`/`end` 的时候这两者不是一回事。

    萨巴伦卡那条把主持人那句两个模型都听不清的收场白剪掉了（`end: 63.7`，
    那一轮从 63.80 起）。不掐窗口的话主持人算出来是 **143** 词，而片子里
    只有 **119**——**表头还印着「采访 63.7 秒」**，读的人没有第二个地方能对。
    而这个数是要印上封面的：`主持人问了 119 个词 / 她答了 77 个`。
    多算的那 24 个词观众一个都听不到，印出去就是一句假话。

    ⚠️ 判据要**同时钉两头**：窗外的不许进来、窗内的一个都不许少。
    只钉前一头的话，把窗口收成空的也能过。
    """
    import json as _json
    import tempfile

    import tools.interview_takeaway as tk

    cap = {"events": [
        {"tStartMs": 0, "segs": [{"utf8": ">> How was it out there tonight?"}]},
        {"tStartMs": 3000, "segs": [{"utf8": ">> Not easy but I am happy."}]},
        {"tStartMs": 6000, "segs": [{"utf8": ">> Thanks and enjoy the rest of it."}]},
    ]}
    lines = [{"a": 0.0, "en": ">> How was it out there tonight?"},
             {"a": 3.0, "en": ">> Not easy but I am happy."}]

    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        (out / "lines.json").write_text(_json.dumps(lines), encoding="utf-8")
        (out / "cap_asr.json3").write_text(_json.dumps(cap), encoding="utf-8")
        rep = tk.report({"slug": "t", "start": 0.0, "end": 5.0}, out)

    # 窗外那一轮（6.0 秒，`Thanks and enjoy…`）不许进来
    assert "enjoy the rest" not in rep, \
        f"把 `end` 之后的那一轮算进来了——这个数要印上封面\n{rep}"
    # 主持人只剩第一问：How was it out there tonight = 6 词
    assert "主持人问了 6 个" in rep, f"窗内的词被掐掉了\n{rep}"
    assert "他说了 6 个词" in rep, f"球员那一轮被掐掉了\n{rep}"


def test_落点卡是可选的收尾卡是必须的():
    """账号所有者 2026-08-05：「我建议还是不要前面卡，后面卡片可以留着」。

    落点卡挡在原声前面是在**跟封面抢开头那 5 秒**（抖音 5 秒内走掉 62%，
    而封面本来就是钩子）。判断放到看完之后。

    `open` 的代码路径留着——真遇到「不先说一句就看不懂」的采访还用得上——
    但**它不能是必填**，否则每条 spec 都得写一张不该有的卡。
    """
    import tools.build_interview_clip as clip

    spec = {
        "slug": "fake-o", "start": 0.0, "end": 50.0, "cover": {"frame_at": 1},
        "zh": ["我健康了"],
        "takeaway": {"close": {"point": "他谈的不是赢球。", "ask": "为什么？"}},
    }
    clip.check_takeaway(spec)                       # 没有 open：不许报

    del spec["takeaway"]["close"]
    with pytest.raises(SystemExit):                 # 没有 close：必须报
        clip.check_takeaway(spec)


def test_解读卡要有配音而且卡停多久跟着配音走():
    """账号所有者 2026-08-05：「但要有配音」。

    加它的理由**不是信息增量**（平台明写着「简易配音」不算），是**死寂**：
    量过没配音那版，前 10.8 秒峰值 **−91 dB**，也就是数字静音，而那正好压在
    抖音 5 秒内走掉 62% 的地方。对照组同一条片子：原声 −10.4、片尾口播 −12.2。

    钉两头：**真的合了语音**，而且**长度是从语音算的**，不是在 spec 里另写
    一个数（写两处必分叉，分叉的样子是「最后一句没念完就切走」）。
    """
    src = Path("tools/build_interview_clip.py").read_text("utf-8")
    body = src.split("def _takeaway_segments(")[1].split("\ndef ")[0]
    code = "\n".join(ln for ln in body.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "_takeaway_voice(" in code, "解读卡没有口播"
    assert "_audio_seconds(" in code, (
        "卡的长度不是从语音算的——在别处另写一个数，两处必分叉，"
        "而分叉的样子是「最后一句还没念完就切走了」")
    # 合不出来要退回静音卡并出声，不能把整条片子带崩
    assert "takeaway_seconds(" in code, "语音合不出来时没有退路"


def test_念出来的那份不许多一个句号():
    """`他其实在说什么？` 后面再加一个 `。`，TTS 会真的在那儿停一下。

    第一版无条件补句号，念出来是「他其实在说什么？。」。
    """
    import tools.build_interview_clip as clip

    assert clip._takeaway_speech({"point": "他谈的不是赢球。",
                                  "ask": "他其实在说什么？"}).endswith("？")
    assert clip._takeaway_speech({"point": "他谈的不是赢球"}).endswith("。")
    # 引号在语音里不发音，去掉只是让 TTS 别在那儿停
    assert "「" not in clip._takeaway_speech({"point": "「我健康了」"})


def test_卡上的字有上限():
    """账号所有者 2026-08-05：「提炼下卡片内容快速过」。

    **做成闸不做成建议**——「写短一点」这种话拦不住下一次写长。
    """
    import tools.build_interview_clip as clip

    spec = {
        "slug": "fake-c", "start": 0.0, "end": 50.0, "cover": {"frame_at": 1},
        "zh": ["我健康了"],
        "takeaway": {"close": {"point": "他谈的不是赢球。", "ask": "为什么？"}},
    }
    clip.check_takeaway(spec)
    spec["takeaway"]["close"]["point"] = "他" * (clip.TAKEAWAY_MAX_CHARS + 1)
    with pytest.raises(SystemExit, match="提炼"):
        clip.check_takeaway(spec)


def test_收尾卡的ask必须以问号收尾():
    """账号所有者看谢尔顿那条收尾卡截图：「还有引号问号等等标点符号也要有啊」。

    来路：谢尔顿这条第一版 `ask` 写的是「你有没有也在追一个还没结束的目标」
    ——没有问号。8 条已发的解读卡里 7 条都以问号收尾（只有
    `rybakina-osaka-tor2026-qf` 那条也漏了，同一个坑踩了两次没人发现）。

    `point` 不在这条闸里：它有时候是引语（带「」）、有时候是陈述句
    （带句号），两种都对，机械判不出该用哪种标点——这跟"最硬的那个事实
    放第 ① 屏"那类判断题是同一个理由，硬凑一条会被绕过的判据比没有更糟。
    `ask` 不一样：它**定义上就是一句问句**，缺问号没有例外，判据钉得住。
    """
    import tools.build_interview_clip as clip

    spec = {
        "slug": "fake-q", "start": 0.0, "end": 50.0, "cover": {"frame_at": 1},
        "zh": ["我健康了"],
        "takeaway": {"close": {"point": "他谈的不是赢球。", "ask": "为什么？"}},
    }
    clip.check_takeaway(spec)  # 带问号，过

    spec["takeaway"]["close"]["ask"] = "为什么"  # 去掉问号
    with pytest.raises(SystemExit, match="问号"):
        clip.check_takeaway(spec)

    spec["takeaway"]["close"]["ask"] = "为什么?"  # 半角问号也认
    clip.check_takeaway(spec)


def test_解读卡字号不许退回2026年8月之前的更小档位():
    """账号所有者看谢尔顿那条收尾卡的截图：「这里的字体可以再大一些？」

    本地渲了三档（64/46 现状、76/54、82/58）加一份 34 字满档压力测试，
    选定 76/54——比现状明显更大，满档时仍留在画布内不溢出（82/58 那档
    满档逼近边距，余量更薄）。判据钉的是**不许退回更小的旧档位**，不是
    钉死这两个数永远不能再调大：往后如果还要调，改这两个数字，同时把
    这条测试的数字一起改，而且要重新拿满档文本渲一遍确认没溢出。
    """
    import inspect

    import tools.build_interview_clip as clip

    src = inspect.getsource(clip.build_takeaway_card)
    assert "font-size:76px" in src, "解读卡 .point 字号不许退回 64px 那档"
    assert "font-size:54px" in src, "解读卡 .ask 字号不许退回 46px 那档"
    """这台沙箱的出网走一个做 TLS 拦截的代理，而 edge-tts 认 certifi 的根证书。

    **判据自己推导，不维护白名单**：凡是会走到 `synthesize_narration` 的工具，
    `main()` 里都必须调 `trust_local_proxy_ca`。runner 上它是 no-op。

    来路：`build_interview_clip` 在解读卡之前**一个字都不合语音**（片尾走的是
    母版转码），所以从来没挂过。加口播时它是「同时要改的第三处」——而它报出来
    的样子是 `CERTIFICATE_VERIFY_FAILED`，被退路吞成一句「口播合不出来」，
    **看起来像 edge-tts 挂了**。
    """
    import ast

    guilty = []
    for p in sorted(Path("tools").glob("*.py")):
        src = p.read_text("utf-8")
        tree = ast.parse(src)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
            n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        imported = {a.name for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) for a in n.names}
        if "synthesize_narration" not in (names | imported):
            continue
        if "trust_local_proxy_ca" not in names:
            guilty.append(p.name)
    assert not guilty, (
        f"这几个工具会合语音，却没挂代理 CA：{guilty}\n"
        "沙箱里它们会吃 CERTIFICATE_VERIFY_FAILED，而退路会把它吞成"
        "「合不出来」——看起来像 edge-tts 挂了")


def test_会合语音的工作流都要装edge_tts():
    """上一条管的是**沙箱**那一头（证书链），这一条管 **runner** 那一头（依赖）。
    同一个 bug 的两半，而 runner 这半真的漏了。

    `interview-clip.yml` 的装依赖那行原来是
    `pip install -e ".[visualqa]" "yt-dlp[default]" playwright faster-whisper`
    ——**没有 edge-tts**。这条线在解读卡之前一个字都不合语音（片尾走的是母版
    转码），所以历史上不需要它；加口播时它是「同时要改的第三处」。

    ⚠️ **漏了它不报错。** `_takeaway_voice` 的退路把 ImportError 吞成一句
    「口播合不出来，退回静音卡」，run 照样绿、成片照样出——只是那张卡是
    **数字静音（实测 −91 dB）**，而账号所有者对这张卡的原话是「但要有配音」。
    量出来才看得见（run 31151599208）。

    判据**自己推导，不维护白名单**：run 里跑了哪个 `tools/*.py`，那个工具
    （连同它 import 的本仓库模块）会不会走到 `synthesize_narration`。
    """
    import ast

    def _calls_tts(mod: str) -> bool:
        """这个工具自己会不会合语音。

        ⚠️ **不递归。** 第一版顺着 import 往下扒，当场把 `frame-grab.yml`
        （抽帧）和 `auto-push-explainer.yml`（只推送）也判成了「要装」——
        它们导入的某个模块里有 TTS，可它们自己那条路走不到。
        **判据宁可窄不可宽**：扩大化的判据会让下一个人要么白装一个包、
        要么干脆把这条检查删掉。和上一条一样，只看这个模块自己提没提。
        """
        src = ROOT / "tools" / f"{mod}.py"
        if not src.is_file():
            return False
        tree = ast.parse(src.read_text("utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
            n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        imported = {a.name for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) for a in n.names}
        return "synthesize_narration" in (names | imported)

    guilty = []
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        body = "\n".join(ln for ln in wf.read_text("utf-8").splitlines()
                         if not ln.lstrip().startswith("#"))
        if not any(_calls_tts(t) for t in set(re.findall(r"tools/(\w+)\.py", body))):
            continue
        if "edge-tts" not in body:
            guilty.append(wf.name)
    assert not guilty, (
        f"这几条工作流会跑到合语音，却没装 edge-tts：{guilty}\n"
        "缺了它 run 照样绿，只是那一段变成数字静音——量出来才看得见")


# ------------------------------------------------- 并发：同一条采访只留一趟
#
# 2026-08-13。这条线是全仓库唯一「两道防线都没有」而 slug 又参数化的：
# 既没有 `concurrency`（`git log -p` 全历史零命中，不是被谁删掉的），
# 提交那一步又用 `git pull --rebase`（三条渲染线早就换掉了）。
# 三条判据分别钉三样东西，两条是**真跑 bash**——查源码里有没有那句
# `exit 1` 只能防「有人把它删了」，防不住「它从来没工作过」。

def _commit_step() -> dict:
    """「提交成片」那一步。名字变了就报错，别静静地退回一个空串。"""
    for step in _steps():
        if step.get("name") == "提交成片":
            return step
    raise AssertionError("interview-clip.yml 里找不到「提交成片」这一步——"
                         "判据的主语没了，改名了就把这几条测试一起改")


def _outdir_input() -> str:
    """产物目录是被哪个 dispatch 输入参数化的。**推导出来，不写死 `slug`。**

    这几条判据要问的是「分组名带的，是不是同一个把产物目录岔开的那个输入」。
    把 `slug` 硬编码进测试的话，哪天这个输入改叫别的，判据会安静地退成
    一条恒真的绿灯——而那正是它要拦的那个错重新出现的时候。
    """
    names = set(re.findall(r"output/[\w/-]*\$\{\{\s*github\.event\.inputs\.(\w+)\s*\}\}",
                           _step_run(_commit_step())))
    assert len(names) == 1, (
        f"产物目录被 {sorted(names)} 这些输入一起参数化——判不了该按谁分组")
    return names.pop()


def _workflow_yaml() -> dict:
    import yaml  # noqa: PLC0415

    return yaml.safe_load((ROOT / ".github" / "workflows"
                           / "interview-clip.yml").read_text(encoding="utf-8"))


def test_同一条采访不许两趟一起跑():
    """没有 `concurrency` 时，同一个 slug 反复 dispatch 会两趟一起写同一格。

    **窗口是这条线的设计工作方式，不是理论**：换封面就要重发一趟，而
    `mode=render` 要九分钟。撞上时下面那个提交循环会在 `poster.jpg`
    （二进制）和 `lines.json`（纯文本）上冲突——合成仓库上真跑过，
    见 `test_推送撞车要把本条重放上去而不是rebase`。

    ⚠️ **分组名必须带那个把产物目录岔开的输入。** 写死一个组名的话，一批
    不同 slug 一起发只会活下来第一个和最后一个（GitHub 每组只留一个
    pending，其余全取消）——`explainer.yml` 那边用血换来的。
    """
    conc = _workflow_yaml().get("concurrency")
    assert conc, "interview-clip.yml 没有 concurrency——同一条采访会两趟一起跑"

    group = str(conc["group"])
    key = _outdir_input()
    assert f"inputs.{key}" in group, (
        f"分组名 {group!r} 里没有 `inputs.{key}`，而产物目录正是按它岔开的。"
        f"写死一个组名 = 一批一起发只活下来第一个和最后一个")
    assert conc.get("cancel-in-progress") is True, (
        "cancel-in-progress 不是 true——改一版再发一版时两趟会一起跑，"
        "谁后落库谁赢，而 commit message 一模一样，git log 上看不出来")


# --------------------------------------------------------- 真跑 bash 的两条

_SHIM_SLEEP = "#!/bin/sh\nexit 0\n"
_SHIM_GIT_NO_PUSH = """#!/bin/sh
# push 一律失败，其余原样转给真 git——用来把重试循环跑到耗尽。
if [ "$1" = push ]; then echo "shim: push rejected" >&2; exit 1; fi
exec {real} "$@"
"""


def _bin_shims(tmp_path: Path, *, block_push: bool) -> Path:
    """一个只影响这次子进程的 PATH 前缀。

    `sleep` 一律打成空操作：退避加起来两百多秒，而**这几条判据要验的性质
    跟睡多久无关**——恰恰相反，「循环体最后一句是必成功的 sleep」正是那个
    退出码恒为 0 的 bug 本身，所以这一句不能删掉，只能让它变快。
    """
    import shutil  # noqa: PLC0415

    real = shutil.which("git")
    assert real, "这台机器上没有 git，跑不了这条判据"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "sleep").write_text(_SHIM_SLEEP, encoding="utf-8")
    if block_push:
        (bin_dir / "git").write_text(_SHIM_GIT_NO_PUSH.format(real=real),
                                     encoding="utf-8")
    for f in bin_dir.iterdir():
        f.chmod(0o755)
    return bin_dir


def _seed_repo(tmp_path: Path, slug: str) -> tuple[Path, Path]:
    """裸 origin + 一个工作副本，产物目录里预置一份存量成片。

    那份 mp4 是**故意**放的：这条线现在还有十几个存量 slug 的 mp4 躺在 git 里，
    而走了 Release 的那一趟提交是带着 `delete mode` 的——重放漏了
    `rm -rf` 就会把它救活。
    """
    import subprocess  # noqa: PLC0415

    def run(*args, cwd=None):
        subprocess.run(args, cwd=cwd, check=True,
                       capture_output=True)

    origin, work = tmp_path / "origin.git", tmp_path / "work"
    run("git", "init", "-q", "--bare", "--initial-branch=main", str(origin))
    run("git", "clone", "-q", str(origin), str(work))
    for k, v in (("user.name", "T"), ("user.email", "t@t.t")):
        run("git", "config", k, v, cwd=work)
    out = work / "output" / "interviews" / slug
    out.mkdir(parents=True)
    (out / "lines.json").write_text("base\n", encoding="utf-8")
    (out / "poster.jpg").write_bytes(b"\x00base-poster\xff" * 40)
    (out / f"{slug}.mp4").write_bytes(b"\x00stale-clip\xff" * 40)
    (work / "tools").mkdir()
    # 体积闸有它自己那条自动推导的判据，这儿只要它别把脚本打断
    (work / "tools" / "check_staged_file_sizes.py").write_text("", encoding="utf-8")
    run("git", "add", "-A", cwd=work)
    run("git", "commit", "-qm", "base", cwd=work)
    run("git", "push", "-q", "origin", "main", cwd=work)
    return origin, work


def _this_run_writes(work: Path, slug: str) -> None:
    """本趟 render 的产出：文本和海报都改了，成片按 Release 那一步删掉。"""
    out = work / "output" / "interviews" / slug
    (out / "lines.json").write_text("this-run\n", encoding="utf-8")
    (out / "poster.jpg").write_bytes(b"\x00this-run-poster\xff" * 40)
    (out / f"{slug}.mp4").unlink()


def _commit_script(slug: str) -> str:
    """把「提交成片」那一步的 `run:` 原文取出来，只换掉 `${{ }}`。

    ⚠️ **注释一个字都不删**：这一步的注释里正写着 `git pull --rebase`
    和 `[ A ] && break` 那两个坑，删掉它们等于跑的不是仓库里那份脚本。
    只有查「有没有又写回 rebase」的那条断言才走 `_step_run`。
    """
    body = str(_commit_step()["run"])
    body = (body.replace("${{ github.event.inputs.slug }}", slug)
                .replace("${{ github.ref_name }}", "main"))
    left = re.findall(r"\$\{\{[^}]*\}\}", body)
    assert not left, (
        "这一步多了没被替换掉的 ${{ }} 表达式——跑的就不是真脚本了，"
        f"补一条替换再说：{left}")
    return body


def _run_commit_step(tmp_path: Path, work: Path, slug: str, *,
                     block_push: bool):
    import subprocess  # noqa: PLC0415
    import os  # noqa: PLC0415

    script = tmp_path / "commit_step.sh"
    script.write_text(_commit_script(slug), encoding="utf-8")
    env = dict(os.environ)
    env["PATH"] = f"{_bin_shims(tmp_path, block_push=block_push)}{os.pathsep}{env['PATH']}"
    # GitHub Actions 跑 `run:` 用的就是 `bash -e {0}`——**那个 `-e` 是这条
    # 判据的全部前提**：退出码恒为 0 那个 bug 只在 `set -e` 下才成立。
    return subprocess.run(["bash", "-e", str(script)], cwd=work, env=env,
                          capture_output=True, text=True)


def test_推送重试耗尽必须报错不许绿着过去(tmp_path):
    """⭐ 这条比并发本身更急：循环耗尽时**退出码是 0**，整步绿着过去。

    `bash -e` 下 AND-OR 列表里非末尾命令失败不触发退出，而原来那个循环体
    最后一句是 `sleep`（必成功），于是十次都没推上去也「正常结束」。
    实测过：`for i in 1 2 3 4; do false && echo push && break; sleep 0; done`
    退出码就是 0。而 `push` 输入默认 false，那一趟后面没有任何步骤会再碰
    仓库——**整趟 run 从头绿到尾，没人会知道这一条根本没落库**。

    所以真跑一遍：让 `git push` 一律失败，这一步必须非零退出。
    """
    slug = "zz-exhaust"
    _, work = _seed_repo(tmp_path, slug)
    _this_run_writes(work, slug)
    done = _run_commit_step(tmp_path, work, slug, block_push=True)

    assert done.returncode != 0, (
        "推了十次都没上去，这一步却退出 0——产物静默丢掉，"
        f"而整趟 run 是绿的\n--- stdout ---\n{done.stdout[-2000:]}")
    assert "::error::" in done.stdout + done.stderr, (
        "非零退出是对的，但没有走到循环末尾那句 ::error::——"
        "多半是死在了前面某一句，这条判据其实什么都没验到\n"
        f"--- stdout ---\n{done.stdout[-2000:]}\n--- stderr ---\n{done.stderr[-2000:]}")


def test_推送撞车要把本条重放上去而不是rebase(tmp_path):
    """同 slug 撞车时，`git pull --rebase` 过不去——两类文件都会冲突。

    合成仓库上跑过原来那一版，git 的原话：
    `Cannot merge binary files: poster.jpg` ＋
    `CONFLICT (content): Merge conflict in lines.json`，
    之后每次重试都是 `Pulling is not possible because you have unmerged files`。
    **跟文件类型无关**——文本的 `lines.json` 一样冲突。

    正解是重放：产物只有一个正确解（本趟渲的这一份），放到最新的分支上去。
    三条断言合起来才算数：落库了、内容是本趟的、**而且被删掉的成片没有被
    重放救活**（`rm -rf` 漏在 `git checkout -- <dir>` 后面就会救活它，
    因为 checkout 只恢复不删除——这一头单独反向验过）。
    """
    import subprocess  # noqa: PLC0415

    slug = "zz-collision"
    origin, work = _seed_repo(tmp_path, slug)

    # 另一趟同 slug 的 run 抢先落库：本趟第一次 push 必然被拒
    rival = tmp_path / "rival"
    subprocess.run(["git", "clone", "-q", str(origin), str(rival)], check=True)
    for k, v in (("user.name", "R"), ("user.email", "r@r.r")):
        subprocess.run(["git", "config", k, v], cwd=rival, check=True)
    out = rival / "output" / "interviews" / slug
    (out / "lines.json").write_text("rival\n", encoding="utf-8")
    (out / "poster.jpg").write_bytes(b"\x00rival-poster\xff" * 40)
    subprocess.run(["git", "commit", "-qam", "rival"], cwd=rival, check=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=rival, check=True)

    _this_run_writes(work, slug)
    done = _run_commit_step(tmp_path, work, slug, block_push=False)
    assert done.returncode == 0, (
        "撞车之后本趟一次都没落库\n"
        f"--- stdout ---\n{done.stdout[-3000:]}\n--- stderr ---\n{done.stderr[-3000:]}")

    def landed(path: str) -> str:
        return subprocess.run(["git", "show", f"main:{path}"], cwd=origin,
                              capture_output=True, text=True).stdout

    base = f"output/interviews/{slug}"
    assert landed(f"{base}/lines.json") == "this-run\n", (
        "落库的不是本趟渲的那一份——重放放回来的是别人的那格")
    tracked = subprocess.run(["git", "ls-tree", "-r", "--name-only", "main", base],
                             cwd=origin, capture_output=True, text=True).stdout
    assert f"{base}/poster.jpg" in tracked, "海报没落库"
    assert f"{base}/{slug}.mp4" not in tracked, (
        "走了 Release、已经 `rm` 掉的成片被重放救活了——"
        "`rm -rf` 必须排在 `git checkout <ref> -- <dir>` **之前**，"
        "因为 checkout 只恢复 ref 里有的，不删 ref 里没有的，"
        "而上一句 reset --hard 刚把旧成片放了回来。"
        "结果是仓库里留着旧片、真片在 Release 上，两个地址两条片子")


def test_提交那一步不许再写回pull_rebase():
    """⚠️ 这条**必须走 `_step_run`**（去掉整行注释）再扫。

    修完之后这一步的注释里就白纸黑字写着 `git pull --rebase` 和
    `[ A ] && break`——那正是这个仓库存教训的地方。连注释一起扫，
    「把坑记下来」会被判成「又踩了这个坑」，同一个形状这里犯过五次。

    上面两条是行为判据（真跑 bash），这一条只拦「有人又把它写回来」，
    两者不互相顶替。
    """
    body = _step_run(_commit_step())
    assert "pull --rebase" not in body, (
        "提交那一步又写回了 `git pull --rebase`——同 slug 撞车时它在"
        "`poster.jpg` / `lines.json` 上必冲突，之后每次重试都是 unmerged")
    assert "&& break" not in body, (
        "循环里又出现了 `&& break`：`bash -e` 下 AND 列表非末尾命令失败不退出，"
        "循环耗尽会绿着过去（见 test_推送重试耗尽必须报错不许绿着过去）")


# ---------------------------------------------------------------- 语气词

def test_烧进画面的英文不许留语气词():
    """账号所有者 2026-08-15：「**以后把英文字幕里的语气词去掉比如 uh en 之类的**」。

    左边每一条都是从存量 26 份自动字幕里**抄出来的真实行**，不是编的。
    实测这批素材里只有两种真的出现过——`uh` 264 次、`um` 247 次。
    """
    真实行 = {
        "Um, honestly, I don't know.": "Honestly, I don't know.",
        "a lot of uh chances during the matches": "a lot of chances during the matches",
        "Uh just incredible, thrilling,": "Just incredible, thrilling,",
        "the Park Next Door uh type of ride um": "the Park Next Door type of ride",
        "Um haven't played": "Haven't played",
        "Yeah, uh, thanks for waiting, guys.": "Yeah, thanks for waiting, guys.",
        ">> Uh, yeah, thanks for waiting.": ">> Yeah, thanks for waiting.",
    }
    for src, want in 真实行.items():
        got, changed = drop_hesitations(src)
        assert got == want, f"{src!r} → {got!r}，想要 {want!r}"
        assert changed, f"{src!r} 明明有语气词，却报「没改」"


def test_去语气词不许吃掉真词():
    """**扩大化的判据不吭声**——它不会说「我删多了」，只会让画面上少几个词。

    ⚠️ 三类都要挡住，各是一种删错法：
    词里面撞上（`humble`／`German`）、真实的应答（`ah`／`mm`／`eh`）、
    以及**不在名单里的拉长音**（`uhhh`）——名单窄是故意的，宁可漏也不吃真词。
    """
    for text in ("humble beginnings", "an umbrella", "the German player",
                 "Ah, that was tough.", "Mm, maybe.", "It was tough, eh?",
                 "Oh, I know.", "you know, like", "Uhuru played well",
                 "uhhh I mean"):
        got, changed = drop_hesitations(text)
        assert (got, changed) == (text, False), f"{text!r} 被改成了 {got!r}"


def test_整行只有语气词的原样留下():
    """实测 2226 行里有 5 行是这样（光秃秃一个 `Uh` / `Um,`）。

    **不许去空**：去空了画面上就是「有中文、没英文」，而那一行的中文还在。
    真要处理得人来定（改 `en_fixed`，或者把中文一起改），机器不替他决定。
    """
    for src in ("Uh", "Um,", ">> Uh.", "um"):
        got, changed = drop_hesitations(src)
        assert (got, changed) == (src, False), f"{src!r} 被去空成了 {got!r}"


def test_整行只有语气词要出声(capsys):
    """只在有改动时出声的检查证明不了它跑过——**0 行也要印，整行只有语气词更要印**。

    不说的话，「这一行整行只有语气词」和「这一行本来就没有语气词」在日志上
    长得一模一样，而画面上会实打实印一个 `Uh`。
    """
    hit, only = strip_hesitation_lines(_lines(["Um, I think so.", "Uh", "No doubt."]))
    out = capsys.readouterr().out
    assert (hit, only) == (1, 1)
    assert "第 2 行整行只有语气词" in out, f"没点名是哪一行：{out!r}"
    assert "去掉语气词 1 行" in out, f"没报改了几行：{out!r}"

    strip_hesitation_lines(_lines(["No doubt.", "Just incredible."]))
    assert "去掉语气词 0 行" in capsys.readouterr().out, "一个都没有的时候不出声"


def test_去语气词不许改行数否则存量的中文全对不上():
    """**这一条是这套改动的全部风险所在。**

    切行之前去掉是「更对」的位置（语气词不该参与断行和量宽），可拿存量量过：
    **25 条 spec 里 16 条的行数会变**（`swiatek-rybakina-…-presser` 234→228、
    `shelton-mensik` 232→227）。而 `zh` 是**逐行手写的**、`en_fixed` 是
    **按行号挂的**——行数一变这两样全部对不上，`write_ass` 那道
    「中文 N 行、英文 M 行，对不上」当场红。已发的片子不为措辞重渲，
    可 spec 还在仓库里、CI 每次都校。

    所以判据钉两头：**切行那一步不许去语气词**（去了行数就会变），
    **去完之后行数一个不许少**。
    """
    text = ("Um, honestly I don't know. Uh it was a really hard-fought battle "
            "and um I will just enjoy tonight. Um, for many reasons.")
    raw = segment(_words(text), 0, 999)
    assert any(_HESITATION_RE.search(ln["en"]) for ln in raw), (
        "切行那一步把语气词去掉了——那会改断行、进而改行数，"
        "而 `zh` 是逐行手写的、`en_fixed` 按行号挂")

    lines = segment(_words(text), 0, 999)
    n = len(lines)
    hit, _ = strip_hesitation_lines(lines)
    assert hit >= 1, "这段话里明明有语气词"
    assert len(lines) == n, f"行数从 {n} 变成了 {len(lines)}——存量的中文会全部错位"


def test_烧进画面的语气词名单只许最窄的那一档():
    """这个模块里有**三份**口头语名单，用途不同、宽窄不同，别互相搬：

        `_COMPARE_FILLERS`  两份 ASR 比对时两边都去掉    最窄
        `_FILLER`           跟记者的人工引语比对时去掉    最宽，只影响比对不影响产物
        烧字幕（复用第一份）  **从画面上真的删掉**        风险最高

    所以这一条钉两头：**烧字幕用的就是第一份那一份**（不是抄一遍，用 AST 判，
    注释里提到它不算数），**而且这一份必须一直是窄的**——谁哪天为了比对方便
    把它放宽，这条当场红，逼他显式把两份拆开，而不是让画面上的字悄悄少几个词。
    """
    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    node = next(n for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.Assign)
                and any(getattr(t, "id", "") == "_HESITATION_RE" for t in n.targets))
    names = {n.id for n in ast.walk(node.value) if isinstance(n, ast.Name)}
    assert "_COMPARE_FILLERS" in names, (
        "烧字幕的名单自己抄了一份——两份必分叉，而分叉的样子是"
        "「比对时算语气词、烧字幕时不算」，两边各说各的，不报错")

    for w in _COMPARE_FILLERS:
        assert _HESITATION_RE.fullmatch(w), f"{w} 在名单里却认不出来"
    有歧义 = {"ah", "eh", "mm", "hmm", "mhm", "oh", "er", "yeah", "like", "well", "so"}
    assert not (宽 := 有歧义 & set(_COMPARE_FILLERS)), (
        f"{sorted(宽)} 进了要从画面上删掉的名单——`eh` 在加拿大英语里是真词、"
        "`mm`/`ah` 可能是应答，删掉就开始吃真内容。"
        "要为比对放宽的话，请把两份名单显式拆开")
    # ⚠️ **别在这儿加一条「窄的那份必须包含在宽的那份里」。** 我写过，当场红：
    # 两份在**两个方向上**都各有各的（`_COMPARE_FILLERS` 多 `uhh`/`umm`，
    # `_FILLER` 多 `er`/`ah`/`mm`/`hmm`/`mhm`），它们是各自按自己的用途挑的，
    # 从来不是嵌套关系。那条断言听起来很合理，而合理不等于量过。


def test_去语气词真的接在出片那条路上(tmp_path):
    """「算得对」和「算出来被用上了」是两件事——这个仓库为它栽过
    （`_push` 键名写错、`_cut_person` 从来没跑起来过）。

    所以钉两头：**烧出来的 ASS 里真的没有语气词**（真跑一遍 `write_ass`），
    **而且 `main()` 真的调了它、调在写字幕之前**（只验行为的话，
    有人把 `strip_hesitation_lines` 从 `main()` 里删掉，上面那半截照样绿）。
    """
    text = ("Um, honestly I don't know. Uh it was a really hard-fought battle "
            "and um I will just enjoy tonight.")
    lines = segment(_words(text), 0, 999)
    strip_hesitation_lines(lines)
    path = tmp_path / "t.ass"
    write_ass(lines, ["一"] * len(lines), 0.0, path)
    for row in path.read_text(encoding="utf-8").splitlines():
        if ",EN,," not in row:
            continue
        body = row.split(",,0,0,0,,", 1)[1]
        assert not _HESITATION_RE.search(body), f"烧进画面的英文还留着语气词：{body!r}"

    src = (ROOT / "tools" / "build_interview_clip.py").read_text(encoding="utf-8")
    main = next(n for n in ast.walk(ast.parse(src))
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    at = {n.func.id: n.lineno for n in ast.walk(main)
          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "strip_hesitation_lines" in at, "`main()` 根本没调它——写了不等于跑过"
    assert at["strip_hesitation_lines"] < at["write_ass"], (
        "去语气词排在了写字幕后面，等于没去")


# ── 怎么开头（`opening`）────────────────────────────────────────────────
#
# 账号所有者 2026-08-16，看完 `tirante-djokovic-cincinnati-2026-r2`：
# 「**蒂兰特这个视频做的很好，先交代了比赛结束，后续的赛后采访建议都这么开头**」。


def test_没认领开头的老片子只许减不许加():
    """`_LEGACY_NO_OPENING` 的自检，和解读卡那张表同一个理由：表里每个 slug
    必须真的存在、而且真的还没有 `opening`。

    ⚠️ **写错一个名字，豁免就成了一盏恒真的绿灯**：那条 spec 既不在名单里
    （名字对不上），也没人发现名单里那个名字指向空气。
    """
    import tools.build_interview_clip as clip

    have = {p.stem for p in _iv_specs()}
    ghosts = clip._LEGACY_NO_OPENING - have
    assert not ghosts, f"豁免名单里这几个 slug 不存在，等于没豁免任何东西：{ghosts}"

    for slug in sorted(clip._LEGACY_NO_OPENING):
        d = json.loads((Path("specs/interviews") / f"{slug}.json").read_text("utf-8"))
        assert not d.get("opening"), (
            f"{slug} 已经认领了 `opening`，就该从豁免名单里划掉——名单只许减不许加")


def test_新的采访片必须认领怎么开头():
    """两头都钉：**存量全过**，而且**闸真的咬得动**。

    ⚠️ 只验前一头的话，一条恒真的 `check_opening` 也能过——所以下面拿假 spec
    把四种错法各走一遍，每一种都必须抛。
    """
    import tools.build_interview_clip as clip

    for p in _iv_specs():
        d = json.loads(p.read_text("utf-8"))
        clip.check_opening(d)          # 缺字段 / kind 写错 / 没 why / lead_in 越界都会抛

    ok = {"slug": "新片", "opening": {"kind": "match_end", "lead_in": 13.8,
                                      "why": "赛点落地 ＋ 解说报出赛果"}}
    clip.check_opening(ok)
    clip.check_opening({"slug": "新片", "opening": {"kind": "none",
                                                    "why": "整条是发布会背板"}})

    坏 = [
        ({"slug": "新片"}, "缺 opening"),
        ({"slug": "新片", "opening": {"kind": "match_end", "lead_in": 13.8}}, "没 why"),
        ({"slug": "新片", "opening": {"kind": "highlight", "why": "a"}}, "kind 不认识"),
        ({"slug": "新片", "opening": {"kind": "match_end", "why": "a"}}, "缺 lead_in"),
        ({"slug": "新片", "opening": {"kind": "match_end", "lead_in": 0, "why": "a"}},
         "lead_in 是 0"),
        # ⚠️ 上界不是洁癖：收成一长条集锦就变成「赛场之上」了，那是另一个栏目。
        # 用 `_OPENING_LEAD_MAX + 1` 而不是写死一个数——**上界改过一次**
        # （30 → 40，`arango-venus` 那条第一次就顶穿了 30），写死的话改上界
        # 那天这条会跟着一起松，而它自己不出声。
        ({"slug": "新片", "opening": {"kind": "match_end",
                                      "lead_in": clip._OPENING_LEAD_MAX + 1,
                                      "why": "a"}}, "lead_in 超上界"),
    ]
    for spec, label in 坏:
        with pytest.raises(SystemExit):
            clip.check_opening(spec)
            pytest.fail(f"这一种没拦住：{label}")


def test_认领开头那道闸排在下载之前():
    """⚠️ **只测行为拦不住位置错。**

    「这条片子怎么开头」是写 spec 那一刻就该定下来的事，只读 spec、不联网。
    闸排在 `fetch_words` / `yt_download` 后面时上面两条照样全绿，而真实代价是
    每次漏认领都要先等一趟网络往返——甚至要等九分钟的 render 出片之后，
    才由人看出来「怎么一上来就有人在说话」。
    """
    src = Path("tools/build_interview_clip.py").read_text("utf-8")
    body = src.split("def main(")[1]
    body = "\n".join(ln for ln in body.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "check_opening(" in body, "`main()` 里没有调 `check_opening`"
    for later in ("fetch_words(", "storyboard_sheet(", "segment("):
        assert body.index("check_opening(") < body.index(later), (
            f"认领开头那道闸排在 `{later}` 后面了——它只读 spec，"
            "该在第 0.2 秒就报")


def test_封面顶栏要和解说片那份台头是同一套值():
    """账号所有者 2026-08-16：「赛后开麦模块也要加顶部白条和栏目标题」
    「参考网球栏目，也做顶部彩条和顶栏标明栏目名」。

    ⚠️ **这是同一件事的第二处实现**，而这个仓库为「同一件事写两处」栽过好几次。
    分叉在这儿的表现最阴：**两张封面分开看都正常**，只有摆在一起才看得出彩条
    的颜色差一档、台头低了几像素——而没有人会把两个栏目的封面摆在一起看。

    所以判据**从解说片那份源码里把值抠出来比**，不在这儿另记一张表：
    `_render_intro_badge` 改了而封面没跟着改（或者反过来），当场红。

    ⚠️ **抠的是真正会生效的那几行，不是「这个词出现过没有」**：彩条那句
    `linear-gradient(...)` 的四个色标、`.head` 的 top/left、图标尺寸、
    两行字号。少抠一样，那一样就可以自己漂走。
    """
    import inspect

    import tools.build_interview_clip as clip
    from tennislive.video import explainer as E

    badge = inspect.getsource(E._render_intro_badge)
    cover = inspect.getsource(clip.build_cover)

    def 抠(src, pat, 什么):
        m = re.search(pat, src)
        assert m, f"从{什么}里抠不出 `{pat}`——那份实现的写法变了，这条判据的主语没了"
        return m.group(1)

    项 = [
        (r"linear-gradient\(90deg,([^)]*#4bb8ff[^)]*)\)", "彩条的四个色标"),
        (r"\.bar\{*\{*position:absolute;top:0;left:0;right:0;height:(\d+)px", "彩条厚度"),
        (r"\.head\{*\{*position:absolute;top:(\d+)px", "台头离顶多远"),
        (r"\.head\{*\{*position:absolute;top:\d+px;left:(\d+)px", "台头左边距"),
        (r"\.brand-icon\{*\{*width:(\d+)px", "图标尺寸"),
        (r"\.brand\{*\{*font-family:'TL Display SC','TL Sans SC',sans-serif;\s*\n?\s*font-size:(\d+)px", "品牌行字号"),
        (r"\.topic\{*\{*font-family:'TL Sans SC',sans-serif;font-size:(\d+)px", "标题行字号"),
    ]
    for pat, 什么 in 项:
        a, b = 抠(badge, pat, f"解说片台头的{什么}"), 抠(cover, pat, f"封面顶栏的{什么}")
        assert a == b, (
            f"{什么}两处对不上：解说片 `{a}`，封面 `{b}`。\n"
            "⚠️ 这两套台头是同一个东西，账号所有者要的就是「参考网球栏目」——"
            "改一处必须改另一处，不然两个栏目的封面会悄悄长成两个样子。")

    # 判据自己的判据：上面七项一个都没抠到的话，循环体根本没跑过。
    assert len(项) == 7


def test_封面顶栏印栏目名底部就不许再印一遍():
    """⚠️ **栏目名只许印一次。**

    「赛场之上」那颗黄色药丸就是因为这个被账号所有者整块删掉的
    （CLAUDE.md「台头药丸不许自己回来」）——栏目名一直同时印在左上角那行
    `网球时差 · 赛场之上` 里，药丸只是第二遍。

    赛后开麦的封面 2026-08-16 加上顶栏之后是同一个形状：底部那颗 tag 原来写的是
    `赛后开麦 · 2026 辛辛那提 · 阿朗戈`，前半截现在在顶栏了。

    判据钉两头：**顶栏必须印**（不然这次改动等于没做），**底部那颗 tag 不许再拼
    column 进去**（不然又印两遍）。
    """
    import inspect

    import tools.build_interview_clip as clip

    src = inspect.getsource(clip.build_cover)
    assert "网球时差 · {column}" in src, (
        "封面顶栏没印栏目名——账号所有者要的就是「顶栏标明栏目名」")
    m = re.search(r"^\s*tag = (.+)$", src, re.M)
    assert m, "抠不出底部那颗 tag 是怎么拼的——这条判据的主语没了"
    assert "column" not in m.group(1), (
        f"底部 tag 又把栏目名拼进去了：`{m.group(1).strip()}`\n"
        "顶栏已经印过一次了，这是第二遍——和被删掉的那颗黄色药丸同一个形状。")


def test_封面顶栏两行字都要是浅色(tmp_path):
    """账号所有者 2026-08-16：「网球时差 赛后开麦 字体是黑色的啊」。

    ⚠️ **这个 bug 的形状是「抄了规则，没抄它依赖的前提」。** 解说片那份台头里
    `.brand` **自己没有 color**——它的浅色写在 `body{color:#f4fbf7}` 上。我把
    `.brand` 整段抄进封面，而封面的 `body` 没有 `color`，于是它掉回浏览器默认的
    黑色，压在深色台头上几乎看不见。

    ⚠️ **上面那条比 CSS 文本的判据看不见这个**：两份的 `.brand` 一字不差，
    对得上得很——错的是**它继承的那一层**。这正是本仓库反复记的「查产物，
    不查信号」：要判「这行字是不是浅色」，只能**把封面渲出来量像素**。

    ⚠️ **也不能整块台头一起量**：`.topic` 一直带着自己的 `color`，是亮的，
    整块量的话坏的那一版**照样绿**（实测过）。两行必须分开量。

    区间是量出来的，不是拍的（`.head` top:44px，品牌行 38px、标题行 27px）：

        品牌行 y46-86    坏的 最亮 79，亮于 200 的像素 0.00%
                         好的 最亮 248，亮于 200 的像素 12.83%
        标题行 y92-124   好的 最亮 232，亮于 200 的像素 12.92%

    两档差一个数量级，门槛落在中间。
    """
    import inspect

    import numpy as np
    from PIL import Image

    import tools.build_interview_clip as clip

    # 中灰底片：过 `brightness(.34)` 之后台头那条底大约 43，够暗——
    # 黑字在上面出不了亮像素，白字出得了。这是这条判据能分开两档的前提。
    frame = tmp_path / "f.jpg"
    Image.new("RGB", (1080, 810), (128, 128, 128)).save(frame, quality=92)
    spec = {
        "slug": "t", "column": "赛后开麦",
        "cover": {"title": ["标题一行", "标题二行"], "sub": "副标题", "tag": "标签"},
        "push": {"summary": "顶栏第二行"},
    }
    try:
        out = clip.build_cover(spec, frame, tmp_path / "p.png")
    except Exception as exc:                                    # noqa: BLE001
        if "chrom" in str(exc).lower() or "executable" in str(exc).lower():
            raise AssertionError(
                "没有 Chromium，这条判据跑不了——它必须真渲出来量像素，"
                "查 CSS 文本看不见「颜色是继承来的」这一类错") from exc
        raise

    a = np.asarray(Image.open(out).convert("L"), dtype=float)

    def 亮(y0, y1):
        band = a[y0:y1, 140:760]
        return band.max(), (band > 200).mean() * 100

    for 名, y0, y1 in (("品牌行（网球时差 · 赛后开麦）", 46, 86),
                       ("标题行（push.summary）", 92, 124)):
        mx, pct = 亮(y0, y1)
        assert mx >= 200 and pct >= 3.0, (
            f"顶栏的{名}不是浅色：最亮 {mx:.0f}，亮于 200 的像素只有 {pct:.2f}%。\n"
            "⚠️ 八成是这一行的 color 没写、指望从 body 继承——而封面的 body "
            "没有 color。解说片那份是靠 `body{color:#f4fbf7}` 撑着的，"
            "**抄那段 CSS 的时候要连这个前提一起抄，或者给这一行写死 color**。")

    # 判据自己的判据①：两条带子必须真的分开量到东西，否则上面是两句空话。
    assert 亮(46, 86)[1] > 0 and 亮(92, 124)[1] > 0

    # 判据自己的判据②：台头**底下**那条必须是暗的。整幅都亮的话，上面那两句
    # 就成了恒真的绿灯——亮底上黑字白字都能量到亮像素。
    #
    # ⚠️ **它拦的是渲染那头，不是这条测试自己的底片。** 反向验证时我先去改底片
    # （128 → 255），**没红**——因为 `.bg` 上那句 `brightness(.34)` 把纯白也压到
    # 87，怎么选都够暗。真能让它红的是**把那句压暗拿掉**（实测：台头底下亮于 200
    # 的像素 0% → 98.5%）。也就是说这一条守的是「哪天有人把封面底调亮」，
    # 而那正好会让上面两句失效。
    #
    # 记这一笔是因为**我第一版把触发条件写错了**：写着「比如底片选亮了」，而那个
    # 方向根本触发不了它。一个反向验证不了的守卫，和一条恒真的绿灯长得一模一样。
    暗底 = a[128:146, 140:760]
    assert (暗底 > 200).mean() * 100 < 1.0, (
        f"台头底下那条也是亮的（亮于 200 占 {(暗底>200).mean()*100:.2f}%）——"
        "封面底被调亮了，这条判据分不开黑字和白字，等于没装")

    # 顺带钉住：这一行的 color 必须是显式写出来的，不许再退回继承。
    src = inspect.getsource(clip.build_cover)
    assert re.search(r"\.brand\{\{[^}]*color:#", src), (
        "`.brand` 又没有自己的 color 了——它会掉回 body，而封面的 body 没有 color")


# 台标左沿在源片里的横向位置（归一）。**两条片子各量过一次**：
# 德约那条赛前专访 0.823、霍达尔那条 0.827（四帧取最小，1058/1280）。
# 同一个转播模板，取小的那个当判据。
_TENNISTV_LOGO_LEFT = 0.823
# 4:3 窗口在 16:9 源片上居中时保留 x 0.125–0.875，所以要躲开台标，
# 窗口至少要往左挪这么多。**这个数是推出来的，不是拍的**——改上面那个量到的
# 位置，它自己跟着走。
_TENNISTV_MIN_SHIFT = _TENNISTV_LOGO_LEFT - 0.875

# 这条规矩立起来之前发的两条。**只许减不许加**，而且下面自带自检。
_LEGACY_TENNISTV_NO_SHIFT = {
    "faria-shelton-cincinnati-2026-r2",
    "shang-rublev-mtl2026-r2",
}


@pytest.mark.parametrize("path", _specs(), ids=lambda p: p.stem)
def test_TennisTV的源片必须真的把台标挪出窗口(path):
    """⚠️ **这条是为一个「写了理由、理由是编的」的错立的。**

    霍达尔那条的 `_tennistv_trim` 原话是「台标在右上角，居中取 540 宽的 3:4
    取景窗框不进来」——**读起来像量过，其实是推的，而且两个数都错**：版式不是
    3:4 裁切而是横向收边到 4:3（`CROP_RATIO`），居中窗口保留 x 0.125–0.875，
    而台标左沿在 0.827。第一版成片右上角就印着半个 Tennis TV 标。

    **它是渲完把成片从 Release 拉回来放大看才发现的**，四道闸一道都没响——
    画面没有任何异常，只是多了个别人的台标，而账号所有者 2026-08-16 点名要求
    「把它的片尾和它的 logo 剪掉」。

    所以判据不能是「spec 里有没有写一句话」（那正是出错的那一版做的事），
    只能是**窗口的几何真的躲开了**：`crop_shift_x` 至少要挪到台标左沿之外，
    或者显式走 `logo_box`（`removelogo`）那条路。

    ⚠️ 阈值从量到的台标位置推，不写死——改 `_TENNISTV_LOGO_LEFT` 它自己跟着走。
    """
    spec = json.loads(path.read_text(encoding="utf-8"))
    if "tennistv.com" not in str(spec.get("url", "")):
        return
    if spec["slug"] in _LEGACY_TENNISTV_NO_SHIFT:
        return
    if spec.get("logo_box"):
        return
    shift = spec.get("crop_shift_x")
    assert isinstance(shift, int | float), (
        f"{path.name} 的源片是 Tennis TV，右上角有台标，而 spec 没写 `crop_shift_x`。\n"
        f"居中的 4:3 窗口保留 x 0.125–0.875，台标左沿在 {_TENNISTV_LOGO_LEFT}——"
        "**它在窗口里面**。写 `\"crop_shift_x\": -0.06`（德约那条同一个转播模板用的就是这个），"
        "或者走 `logo_box`。")
    assert shift <= _TENNISTV_MIN_SHIFT + 1e-9, (
        f"{path.name} 的 `crop_shift_x` = {shift}，还不够把台标挪出窗口："
        f"至少要 {_TENNISTV_MIN_SHIFT:.3f}（台标左沿 {_TENNISTV_LOGO_LEFT}、"
        "居中窗口右沿 0.875）。")


def test_那张TennisTV豁免表自己也要是真的():
    """⚠️ **一个会过期的名单和一条常年红的检查是同一个毛病。**

    表里每个 slug 都要：真的存在、源片真的是 Tennis TV、而且**真的还没挪窗口**。
    写错一个名字，豁免就成了一盏恒真的绿灯；哪条补上了 `crop_shift_x` 还留在表里，
    这条会逼人把它删掉。
    """
    seen = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in _specs()}
    assert seen, "一条 spec 都没扫到——判据的主语没了"
    for slug in sorted(_LEGACY_TENNISTV_NO_SHIFT):
        assert slug in seen, f"豁免表里的 {slug} 不存在，这一条豁免是空的"
        spec = seen[slug]
        assert "tennistv.com" in str(spec.get("url", "")), \
            f"{slug} 的源片不是 Tennis TV，不该在这张表里"
        assert spec.get("crop_shift_x") is None and not spec.get("logo_box"), \
            f"{slug} 已经把台标挪出去了，从豁免表里删掉"
