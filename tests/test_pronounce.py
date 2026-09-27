"""配音多音字换字表（`video/pronounce.py`）和出片前的多音字预检（`tools/check_polyphones.py`）。

账号所有者 2026-09-27：「配音 tts 里的多音字最好在生成语音时候替换成同音的字」。

四件事各有一组判据：
1. 表本身：每一条字数 1:1、带证据、例句真的会换、守卫句一个字不动；
2. 只进合成器：每个 TTS 入口都喂 `speakable()`，字幕／切词报告拿的是显示那份，
   时间轴不漂（多处换字的一句话逐个 token 对位）；
3. 老四条（挑→选、硬地→硬帝、〇→零、柏林→伯林）在全库旁白上和原实现一字不差；
4. 预检：只报换字表管不到的，dry-run 和采访片每一趟开头真的印出来。
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from tennislive.video import pronounce as P  # noqa: E402
from tennislive.video.explainer import (  # noqa: E402
    _boundary_marks, readable, speakable, subtitle_cues,
)


def _width(pattern: str) -> tuple[int, int]:
    try:
        from re import _parser as sre_parse  # 3.11+
    except ImportError:  # pragma: no cover - 3.10
        import sre_parse  # type: ignore[no-redef]
    lo, hi = sre_parse.parse(pattern).getwidth()
    return lo, hi


def _legacy_speakable(text: str) -> str:
    """2026-09-27 之前 `speakable()` 的原实现，一字不改抄过来当对照组。"""
    text = re.sub(r"挑(?![战衅拨逗剔眉])", "选", readable(text))
    return (text.replace("硬地", "硬帝").replace("〇", "零")
            .replace("柏林", "伯林"))


def _corpus() -> list[tuple[str, str]]:
    """仓库里所有会过 TTS 的原文：(出处, 原文)。"""
    from build_interview_clip import _takeaway_speech  # noqa: PLC0415

    from tennislive.video import explainer as E  # noqa: PLC0415
    from tennislive.video.outro_page import NARRATION  # noqa: PLC0415

    out = [("outro", NARRATION)]
    for path in sorted((ROOT / "specs/reels").rglob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        cover = spec.get("cover") or {}
        if isinstance(cover, dict) and isinstance(cover.get("narration"), str):
            out.append((f"{path.name}:cover", cover["narration"]))
        for i, seg in enumerate(spec.get("segments") or []):
            if isinstance(seg, dict) and isinstance(seg.get("narration"), str):
                out.append((f"{path.name}:{i}", seg["narration"]))
    for path in sorted((ROOT / "specs/interviews").rglob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        for which, card in (spec.get("takeaway") or {}).items():
            if isinstance(card, dict):
                out.append((f"{path.name}:{which}", _takeaway_speech(card)))
    for path in sorted((ROOT / "specs/explainers").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        for i, beat in enumerate(spec.get("beats") or []):
            if isinstance(beat, dict) and isinstance(beat.get("narration"), str):
                out.append((f"{path.name}:{i}", beat["narration"]))
    for slug, beats in E._SCRIPTS.items():
        for i, beat in enumerate(beats):
            if len(beat) > 3 and isinstance(beat[3], str):
                out.append((f"{slug}:{i}", beat[3]))
    for slug, opening in E._OPENINGS.items():
        if isinstance(opening.get("narration"), str):
            out.append((f"{slug}:cover", opening["narration"]))
    return [(k, v) for k, v in out if v.strip()]


# ---------------------------------------------------------------- 1. 表本身
def test_换字表每一条都不改字数():
    """字幕时间轴是按字位把合成器报的 token 对回显示那份的——换字改了字数，
    整段字幕就漂（「硬地→硬场地」实测漂 1~2 个字，长句里 `find` 会跳到后面同一个
    字上，**不报错**）。所以不靠例句碰运气，直接问正则：它能匹配的串**只有一种
    长度**，而且等于替换串的长度。"""
    bad = []
    for h in P.HOMOPHONES:
        lo, hi = _width(h.pattern)
        if not (lo == hi == len(h.replace)):
            bad.append(f"{h.key}：pattern 宽 {lo}~{hi}，replace「{h.replace}」{len(h.replace)} 个字")
    assert not bad, "\n".join(bad)
    # 运行时那道保险也在：真撞上了当场抛，不让它悄悄漂
    with pytest.raises(P.PronounceError):
        rogue = P.Homophone(key="x", pattern="柏林", replace="伯尔林", word="", reading="",
                            evidence="", examples=())
        old = P._COMPILED
        try:
            P._COMPILED = ((rogue, re.compile(rogue.pattern)),)
            P.apply("两年前柏林")
        finally:
            P._COMPILED = old


def test_换字表每一条都有证据_例句真的会换_守卫句一字不动():
    """**没有证据的行不许进表**：只收「原句量出来读错、换字之后量出来读对」的，
    或者账号所有者亲耳听出来的。换一个本来就读对的字只会冒出新的错
    （换字会改切词——`种子→肿子` 连「子」的轻声都丢了）。"""
    keys = [h.key for h in P.HOMOPHONES]
    assert len(keys) == len(set(keys)), "key 重复"
    assert set(P.LEGACY_KEYS) <= set(keys)
    problems = []
    for h in P.HOMOPHONES:
        if not re.search(r"2026-\d\d-\d\d", h.evidence) or not re.search(
                r"账号所有者|实测|复测", h.evidence):
            problems.append(f"{h.key}：evidence 要带日期和出处（账号所有者原话 / 实测的数）")
        if not h.examples:
            problems.append(f"{h.key}：没有例句")
        for before, after in h.examples:
            got = P.apply(before, only=[h.key])
            if got != after:
                problems.append(f"{h.key}：「{before}」换出来是「{got}」，表里写的是「{after}」")
            if got == before:
                problems.append(f"{h.key}：例句「{before}」一个字都没换——这条规则没咬上")
        for guard in h.guards:
            if P.apply(guard, only=[h.key]) != guard:
                problems.append(f"{h.key}：守卫句「{guard}」被换成了「{P.apply(guard, only=[h.key])}」")
    assert not problems, "\n".join(problems)


def test_换字只在量过的上下文里咬():
    """几条窄规则的边界，各钉一个会被放宽的方向（放宽了就会换掉本来读对的字）。"""
    cases = {
        "天空在下雨": "天空在下雨",            # kōng，不是腾出来的那个
        "球场上空出现一架无人机": "球场上空出现一架无人机",
        "首轮轮空出战": "首轮轮空出战",
        "空着手回来": "空着手回来",
        "其中一个": "其中一个",
        "十中八九": "十中八九",
        "数十个国家": "数十个国家",
        "局数十二比六": "局数十二比六",
        "队长回合": "队长回合",
        "布鲁塞尔": "布鲁塞尔",
        "拆了重做的": "拆了重做的",
        "挑战": "挑战",
        "松柏": "松柏",
    }
    for text, want in cases.items():
        assert P.apply(text) == want, (text, P.apply(text))


# ------------------------------------------------ 2. 只进合成器，不上屏幕
def test_多处换字的一句话字幕还是原字_时间轴逐个token对位():
    """一句话里四处换字（柏林→伯林、硬地→硬帝、空出→控出、四中三→四众三）。

    token 是合成器念的那份切出来的。原来 `_boundary_marks` 只在显示那份里找，
    带换过字的 token 一个都找不到，只能沿用上一处——实测「伯林」被钉在逗号上，
    早了一个字。现在先在合成那份里找，找到的字位原样对回显示那份。"""
    display = readable("两年前，柏林揭幕战在硬地上开打，名单上空出一格，破发点他四中三。")
    spoken = speakable(display)
    assert len(spoken) == len(display)
    for w in ("伯林", "硬帝", "控出", "四众三"):
        assert w in spoken, (w, spoken)
    tokens = ["两年", "前", "伯林", "揭幕", "战", "在", "硬", "帝上", "开打", "名单",
              "上", "控出", "一", "格", "破发点", "他", "四众三"]
    expected, cur = [], 0
    for t in tokens:
        cur = spoken.index(t, cur)
        expected.append(cur)
        cur += len(t)
    boundaries = [{"text": t, "offset": int(i * 0.3 * 1e7)} for i, t in enumerate(tokens)]
    marks = _boundary_marks(boundaries, display)
    assert [m[0] for m in marks] == expected, list(zip(tokens, [m[0] for m in marks], expected))

    cues = subtitle_cues(display, len(tokens) * 0.3 + 0.5, boundaries=boundaries)
    shown = "".join(c[2] for c in cues)
    for word in ("柏林", "硬地", "空出"):
        assert word in shown, (word, shown)
    for word in ("伯林", "硬帝", "控出", "众"):
        assert word not in shown, (word, shown)


def test_字幕一律用显示那份_不许把speakable喂给subtitle_cues():
    """换字只许进合成器。`build_shelton_ncaa_story` 原来写的是
    `subtitle_cues(E.speakable(...))`——那时表里只有 〇→零 这类碰巧看不出来的，
    表一扩，「控出」「伯林」就直接烧上屏幕了。扫全部调用点，不维护名单。"""
    bad = []
    for path in [*(ROOT / "src").rglob("*.py"), *(ROOT / "tools").glob("*.py")]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            f = node.func
            name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
            if name == "subtitle_cues" and "speakable" in ast.dump(node.args[0]):
                bad.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not bad, f"字幕拿了喂合成器那份（换过字的）：{bad}"


def test_每个合成入口都喂speakable():
    """所有 `tts_one(...)` 调用（三条出片线 ＋ 故事片工具），第一个参数都要过
    `speakable()`——换字表只有这一个入口。自动扫，不维护名单；`tts_one` 那层薄
    包装自己（收的已经是换过的那份）不算。"""
    calls, bad = 0, []
    for path in [*(ROOT / "src").rglob("*.py"), *(ROOT / "tools").glob("*.py")]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        wrappers = {n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name in ("tts_one", "_tts_one_uncached")}
        inside = {id(c) for w in wrappers for c in ast.walk(w)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or id(node) in inside or not node.args:
                continue
            f = node.func
            name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
            if name != "tts_one":
                continue
            calls += 1
            if "speakable" not in ast.dump(node.args[0]):
                bad.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert calls >= 5, f"判据失效了：只扫到 {calls} 个 tts_one 调用"
    assert not bad, f"这些合成调用绕过了 speakable()（换字表管不到）：{bad}"


def test_真合成时喂进去的是换过字的那份(monkeypatch, tmp_path):
    """上一条是读源码；这条真调一遍三条线的入口，看合成器收到的是什么。"""
    import build_interview_clip as I  # noqa: PLC0415
    import build_match_reel as R  # noqa: PLC0415

    from tennislive.video import explainer as E  # noqa: PLC0415
    from tennislive.video import tts as T  # noqa: PLC0415

    heard: list[str] = []

    def fake(text, path, *a, **k):
        heard.append(text)
        Path(path).write_bytes(b"x")
        return []

    monkeypatch.setattr(T, "tts_one", fake)
    monkeypatch.setattr(R, "tts_one", fake)
    line = "名单上空出一格，两年前柏林揭幕战他四中三。"

    E.synthesize_narration([E.ExplainerSegment("x", "x", "x", line)], tmp_path / "e")
    R.synthesize([R.Segment(start=0.0, end=3.0, cx=None, narration=line)], tmp_path,
                 "zh-CN-YunjianNeural", "+6%")
    R.synth_cover({"column": "网球有故事", "cover": {"narration": line}},
                  tmp_path, "zh-CN-YunjianNeural", "+6%")
    I._takeaway_voice({"takeaway": {"close": {"lead": line}}}, "close", tmp_path)
    assert len(heard) == 4, heard
    for text in heard:
        assert "控出" in text and "伯林" in text and "四众三" in text, text
        assert "空出" not in text and "柏林" not in text


def test_切词报告的专名按念出来的样子找():
    """名字里有字被换了（「鲁塞娃」→「鲁赛娃」），拿原名去换过字的那份里找一处都
    找不到，骑边界的 token 就一声不吭地放过去了。"""
    import build_match_reel as R  # noqa: PLC0415

    spec = {"cover": {"matchup": [{"name": "鲁塞娃"}, {"name": "伊埃拉"}]}}

    class Seg:
        narration = "最后一分，鲁塞娃的回球下网。"

    marks = [{"text": t} for t in ["最后", "一", "分", "鲁赛", "娃的", "回球", "下网"]]
    (_, _, crossing, _, spoken, _), = R._word_splits(spec, [Seg()], [(None, marks)])
    assert "鲁赛娃" in spoken
    assert crossing and "娃的" in crossing[0], crossing


# ------------------------------------------------ 3. 老四条一字不差
def test_老四条换字在全库旁白上和原实现一字不差_新条目只换量过的地方():
    """回归判据：挑→选、硬地→硬帝、〇→零、柏林→伯林 搬进表之后，在仓库里每一句
    会过 TTS 的原文上，输出和搬之前的实现逐字相同；新加的条目只在它自己咬上的
    地方改字，且全库每一句换字前后字数都一样。"""
    corpus = _corpus()
    assert len(corpus) > 3000, f"语料只扫到 {len(corpus)} 句——扫描面塌了"
    new_keys = [h.key for h in P.HOMOPHONES if h.key not in P.LEGACY_KEYS]
    changed = 0
    for where, raw in corpus:
        shown = readable(raw)
        old = _legacy_speakable(raw)
        assert P.apply(shown, only=P.LEGACY_KEYS) == old, where
        new = speakable(raw)
        assert new == P.apply(old, only=new_keys), where
        assert len(new) == len(shown), (where, raw)
        changed += new != old
    # 2026-09-27 全库 5215 句：新条目在 35 句上咬（长回合 14、空出 7、鲁塞 6……），逐条读过
    assert 20 <= changed <= 120, f"新条目改了 {changed} 句——扫一眼是不是规则放宽了"


# ------------------------------------------------ 4. 出片前的预检
def test_多音字预检只报换字表管不到的非常用读音():
    import check_polyphones as C  # noqa: PLC0415

    texts = [C.Spoken("第 1 段", readable("她赛后自己说，那场雨来得正是时候。"), "+6%"),
             C.Spoken("第 2 段", readable("名单上空出一格，他在国家银行公开赛拿了冠军。"), "+6%"),
             C.Spoken("第 3 段", readable("四比五，他还得再守一次。"), "+6%")]
    lines, risks = C.static_report(texts, "demo")
    shown = [r for r in risks if not r.lexicon]
    assert [(r.label, r.char, r.intended) for r in shown] == [("第 1 段", "场", "chang2")], shown
    text = "\n".join(lines)
    assert "场 应读 cháng" in text and "--slug demo --measure" in text
    # 空出：换字表管了；银行：词典词只计数；还得（děi）：这个读音整类量过读对
    assert "空" not in "".join(r.char for r in shown)
    assert "词典词" in text and "量过读对" in text

    clean = C.static_report([C.Spoken("第 1 段", "他赢了。", "+6%")])[0]
    assert clean[0].startswith("[多音字] 没有"), clean


def test_多音字预检缺pypinyin要出声不许拖垮出片(monkeypatch):
    import check_polyphones as C  # noqa: PLC0415

    monkeypatch.setitem(sys.modules, "pypinyin", None)
    lines = C.report_lines([C.Spoken("第 1 段", "那场雨", "+6%")])
    assert len(lines) == 1 and "没查" in lines[0] and "pypinyin" in lines[0], lines


def test_采访片每一趟开头报解读卡口播的多音字(capsys):
    import build_interview_clip as I  # noqa: PLC0415

    I.report_takeaway_polyphones({"slug": "demo", "takeaway": {"close": {
        "lead": "那场雨之后她变了", "point": "名单上空出一格"}}})
    out = capsys.readouterr().out
    assert "[多音字]" in out and "场 应读 cháng" in out, out
    I.report_takeaway_polyphones({"slug": "demo"})
    assert capsys.readouterr().out == "", "没有解读卡就不该出声"
    # 而且 `main()` 每一趟都调它（和 check_opening 那几道一起排在最前面）
    tree = ast.parse(Path(I.__file__).read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    called = {c.func.id for c in ast.walk(main)
              if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert {"check_opening", "report_takeaway_polyphones"} <= called


def test_dry_run真的印出多音字预检(tmp_path):
    """「写了」不等于「跑过」：真跑一遍 `render --dry-run`，旁白里塞一处表外的
    多音字（「那场雨」的 cháng），它得出现在输出里——而且不改退出码（只报不拦）。"""
    slug = "tiafoe-musetti-cincinnati-2026-qf"
    spec = json.loads((ROOT / f"specs/reels/{slug}.json").read_text(encoding="utf-8"))
    last = [s for s in spec["segments"] if s.get("narration")][-1]
    last["narration"] = "那场雨，" + last["narration"]
    path = tmp_path / f"{slug}.json"
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "tools/build_match_reel.py", "render", "--spec", str(path),
         "--outdir", str(tmp_path / "out"), "--dry-run"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout[-800:] + proc.stderr[-800:]
    assert "[多音字] 1 处" in proc.stdout and "场 应读 cháng" in proc.stdout, proc.stdout
