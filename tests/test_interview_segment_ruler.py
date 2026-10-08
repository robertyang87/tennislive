"""赛后开麦：已渲的 spec 重切一遍，行必须和发出去那一版一字不差——切行的尺子按 slug 钉死。

来路（2026-09-28 取证）：34cb737f（2026-09-27）把英文字幕换成 Inter，`_FONT_FILES["en"]`
跟着换，**切行量宽度的尺子也就换了**。`segment()` 每次出片都现切，而 `zh` 逐行手写、
`en_fixed` 按行号挂——108 条已渲 spec 按新尺子重切，65 条行数对不上（`write_ass` 当场红、
或先红在 `en_fixed` 错行），另有 17 条行数碰巧对上、边界却挪了（中文静静配到隔壁那句
英文上）。O1 重核、O4 换封面、24 小时修订，任何一次重渲都会撞上。

而这件事**一条测试都没有**：没有谁拿仓库里落着的字幕缓存把 `segment()` 重跑一遍。
这里补的就是那一条，外加老尺子表的自检、切行提速的等价性、老尺子字体的工作流依赖。
尺子的定义和每一把的年代见 `tools/build_interview_clip.py` 的 `SEGMENT_RULERS`。
"""
from __future__ import annotations

import contextlib
import functools
import hashlib
import io
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import build_interview_clip as clip  # noqa: E402

SPECS = ROOT / "specs" / "interviews"
OUTPUT = ROOT / "output" / "interviews"

#: 老尺子表的条数上限。**只许往下改**：表里的每一条都是「这把老尺子才复现得了已发成片」
#: 的已渲 spec，新 spec 一律走默认尺子，不该有任何理由往里加。
_LEGACY_RULER_CAP = 82


def _pytest_needs_fonts() -> None:
    pytest.importorskip("PIL")
    for path, _pkg in (*clip._FONT_FILES.values(), *clip._RULER_FONT_FILES.values()):
        if not Path(path).exists():
            pytest.skip(f"{path} 不在（系统字体没装）——CI 上 ci.yml 装着它")


def _rendered_corpus() -> list[tuple[dict, list, list[float] | None, bool]]:
    """已渲（有 render.json）、仓库里落着这条 URL 字幕缓存的正式 spec →
    [(spec, 字幕词流, lines.json 的每行起点 或 None, 落地那一趟是不是就是这份 spec)]。

    「落地那一趟是不是这份 spec」按 `qc_attestation.spec_sha256` 认（没有 QC 的老片子
    算是）：推完以后 spec 又被改过的（比如 ruud-cerundolo 发布会推完才按新尺子重挂中文），
    lines.json 记的是上一版成片，边界不拿它比，只比行数和 `en_fixed`。"""
    rows = []
    for path in sorted(SPECS.glob("*.json")):
        if path.name.endswith(".draft.json"):
            continue
        spec = json.loads(path.read_text(encoding="utf-8"))
        out = OUTPUT / str(spec.get("slug") or path.stem)
        if not (out / "render.json").is_file() or not spec.get("zh"):
            continue
        words = clip.cached_words(str(spec.get("url") or ""), out, spec)
        if not words:
            continue
        bounds = None
        if (out / "lines.json").is_file():
            bounds = [round(ln["a"], 2)
                      for ln in json.loads((out / "lines.json").read_text(encoding="utf-8"))]
        current = True
        if (out / "qc_attestation.json").is_file():
            qc = json.loads((out / "qc_attestation.json").read_text(encoding="utf-8"))
            current = qc.get("spec_sha256") == hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append((spec, words, bounds, current))
    return rows


def _resegment(spec: dict, words: list, ruler: str) -> tuple[list[dict], list[str]]:
    """出片那一趟 `main()` 的同一串：切行 → 查 `en_fixed` 挂没挂错行 → 套 `en_fixed` →
    去语气词。回 (行, en_fixed 错行的说明)。"""
    with contextlib.redirect_stdout(io.StringIO()):
        lines = clip.segment(words, spec["start"], spec["end"],
                             budget=spec.get("segment_budget_px"),
                             word_fix=spec.get("word_fix"), ruler=ruler,
                             language_windows=clip.transcript_language_windows(spec))
    bad = clip.en_fixed_misaligned(lines, spec.get("en_fixed") or {})
    for k, v in (spec.get("en_fixed") or {}).items():
        idx = int(k) - 1
        if 0 <= idx < len(lines):
            lines[idx]["en"] = v
    with contextlib.redirect_stdout(io.StringIO()):
        clip.strip_hesitation_lines(lines)
    return lines, bad


def _mismatch(spec: dict, words: list, bounds, current: bool, ruler: str) -> str | None:
    """这把尺子重切出来和已发那一版差在哪；对得上回 None。"""
    lines, bad = _resegment(spec, words, ruler)
    zh = spec.get("zh") or []
    why = []
    if bad:
        why.append(f"en_fixed 错行 {len(bad)} 处")
    if len(lines) != len(zh):
        why.append(f"zh {len(zh)} 行、重切 {len(lines)} 行")
    if bounds is not None and current and [round(ln["a"], 2) for ln in lines] != bounds:
        moved = sum(1 for a, b in zip(bounds, (round(ln["a"], 2) for ln in lines)) if a != b)
        why.append(f"和 lines.json 的行边界对不上（{len(bounds)} 行里挪了 ≥{moved} 处）")
    if wide := clip.en_problems(lines, ruler):
        why.append(f"英文超宽 {len(wide)} 行（{wide[0]}）")
    return "；".join(why) or None


@functools.lru_cache(maxsize=None)
def _default_ruler_mismatches() -> dict[str, str | None]:
    """老尺子表里的每一条，按默认尺子重切的结果（自检「这条真的要老尺子」用）。"""
    legacy = clip.legacy_segment_rulers()
    return {spec["slug"]: _mismatch(spec, words, bounds, current, clip.SEGMENT_RULER)
            for spec, words, bounds, current in _rendered_corpus() if spec["slug"] in legacy}


def test_已渲的采访spec按钉死的尺子重切_行一行不差():
    """**每一条已渲的正式 spec**：按 `segment_ruler(spec)` 重切 → 套 `en_fixed` → 去语气词，
    行数必须等于 `zh`、`en_fixed` 不许挂错行、英文不许超宽，而且（落地那一趟就是这份
    spec 时）每行起点和 `lines.json` 一字不差——也就是重渲出来的字幕和发出去的那一版
    是同一份。

    这条红了就是「有已发的片子一重渲就红，或者重渲出来中英错位」。报错按条数给账：
    多半是有人又换了英文字体／字号／词类归一，而没把换之前渲的 slug 钉到老尺子上
    （做法写在 `SEGMENT_RULERS` 上面那段注释里）。
    """
    if not OUTPUT.is_dir():
        pytest.skip("工作区没有 output/interviews（精简 worktree）——CI 的稀疏检出带着 *.json3")
    _pytest_needs_fonts()
    import build_interview_request as req  # noqa: PLC0415

    corpus = _rendered_corpus()
    assert len(corpus) >= 100, (
        f"只找到 {len(corpus)} 条带字幕缓存的已渲 spec——多半是字幕缓存（cap_*.json3）"
        "没检出来，这条判据没在查任何东西")
    bad, auto = [], {}
    for spec, words, bounds, current in corpus:
        ruler = clip.segment_ruler(spec)
        if (why := _mismatch(spec, words, bounds, current, ruler)) is None:
            continue
        if req.unverified_auto_spec(spec, spec["slug"]):
            auto[spec["slug"]] = why       # 自动链刚提交、没核也没发：渲染闸照拦，这里只报
        else:
            bad.append(f"{spec['slug']}（尺子 {ruler}）：{why}")
    req.report_unverified_auto("已渲的采访spec按钉死的尺子重切", auto)
    assert not bad, (
        f"{len(bad)}/{len(corpus)} 条已渲的采访 spec 重切对不上发出去那一版：\n  "
        + "\n  ".join(bad))


def test_老尺子表只许减_每条都真的要它():
    """`data/legacy_interview_segment_metric.json` 的自检，四头：

    ① 表里每条都是**已渲**的正式 spec（新 spec 不许挂老尺子）；
    ② 表里每条按**默认尺子**重切都对不上——对得上就说明它不需要老尺子，删掉；
    ③ 条数只许减（`_LEGACY_RULER_CAP`）；
    ④ ②里那些「对不上」要两种坏法都有：行数变了（重渲当场红），和**行数碰巧没变、
       边界挪了**（不红、中文静静配到隔壁那句英文上）——后一种最该拦，判据只看行数
       就漏掉它。②＋④就是「把钉子整个拔掉」之后的样子，反向那一头写在测试里。
    """
    if not OUTPUT.is_dir():
        pytest.skip("工作区没有 output/interviews（精简 worktree）")
    _pytest_needs_fonts()
    legacy = clip.legacy_segment_rulers()
    # 不断言「非空」：表按规矩减到零是终点，不是故障。路径或尺子名写错不会读成空表——
    # `legacy_segment_rulers` 读不到文件、认不出尺子名都当场 SystemExit（复审 nit）。
    assert len(legacy) <= _LEGACY_RULER_CAP, (
        f"老尺子表 {len(legacy)} 条，超过上限 {_LEGACY_RULER_CAP}——只许减不许加，"
        "新 spec 一律走默认尺子")
    default = _default_ruler_mismatches()
    stray = sorted(set(legacy) - set(default))
    assert not stray, f"这些挂了老尺子，却不是带字幕缓存的已渲 spec：{stray}"
    needless = sorted(s for s, why in default.items() if why is None)
    assert not needless, (
        f"这些按默认尺子重切也和已发那一版一字不差，不需要老尺子，从表里删掉：{needless}")
    assert any("行、重切" in why for why in default.values())
    assert any("行、重切" not in why and "边界" in why for why in default.values()), \
        "该有「行数碰巧对上、边界挪了」的那一类——那是不红的错位"


def test_默认尺子就是英文字幕那把_老尺子是冻住的():
    """默认尺子和 `en_problems` 用的 `_en_width` 必须是同一把——两处量的不一样，
    切出来的行和验宽的闸就各说各话。老尺子的字号是历史事实，写死的数。"""
    _pytest_needs_fonts()
    probe = "Just talk a little bit about these last six years"
    assert clip.ruler_width(clip.SEGMENT_RULER)(probe) == clip._en_width(probe)
    assert clip.SEGMENT_RULERS[clip.SEGMENT_RULER][2] is clip._bare
    assert {k: v[:2] for k, v in clip.SEGMENT_RULERS.items() if k != clip.SEGMENT_RULER} == {
        "noto-46": ("en_noto", 46), "noto-46-bare-0805": ("en_noto", 46),
        "noto-40": ("en_noto", 40)}
    # 那一个月的 `_bare` 不转小写、剥掉撇号——就是这一点让 And/The 认不出来
    assert clip._bare_0805("And,") == "And" and clip._bare_0805("don't") == "dont"
    assert clip.segment_ruler({"slug": "zz-new-spec"}) == clip.SEGMENT_RULER


def test_老尺子表认不出就报错_不回退到默认尺子(tmp_path, monkeypatch):
    """回退到默认尺子就是 2026-09-27 那次事故本身：已发的片子按新尺子切，不吭声。"""
    monkeypatch.setattr(clip, "_LEGACY_RULER_CACHE", {})
    monkeypatch.setattr(clip, "LEGACY_SEGMENT_RULER_FILE", tmp_path / "missing.json")
    with pytest.raises(SystemExit, match="读不到"):
        clip.segment_ruler({"slug": "x"})
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"inter-46": ["x"]}), encoding="utf-8")
    monkeypatch.setattr(clip, "LEGACY_SEGMENT_RULER_FILE", bad)
    with pytest.raises(SystemExit, match="不是一把老尺子"):
        clip.segment_ruler({"slug": "x"})
    bad.write_text(json.dumps({"noto-46": ["x"], "noto-40": ["x"]}), encoding="utf-8")
    monkeypatch.setattr(clip, "_LEGACY_RULER_CACHE", {})
    with pytest.raises(SystemExit, match="两把尺子"):
        clip.segment_ruler({"slug": "x"})


def _split_wide_reference(sent, budget, width, bare):
    """2026-09-28 提速之前的 `_split_wide`，一字不改：对每个终点把所有起点都量一遍。"""
    n = len(sent)
    if width(clip._text(sent)) <= budget:
        return [sent], False
    inf = float("inf")
    best, prev, hard = [inf] * (n + 1), [0] * (n + 1), [False] * (n + 1)
    best[0] = 0.0
    for j in range(1, n + 1):
        for i in range(j):
            if best[i] == inf:
                continue
            w = width(clip._text(sent[i:j]))
            if w > budget and j - i > 1:
                continue
            rank = 0 if i == 0 else clip._break_rank(sent, i, bare)
            pen = (clip._FORCE_PENALTY if rank is None else rank * clip._RANK_PENALTY) * budget
            slack = 0.0 if j == n else (budget - w) ** 2 / budget
            if (c := best[i] + slack + pen) < best[j]:
                best[j], prev[j] = c, i
                hard[j] = hard[i] or (i > 0 and clip._break_rank(sent, i, bare) is None)
    cuts, j = [n], n
    while j:
        j = prev[j]
        cuts.append(j)
    cuts.reverse()
    return [sent[a:b] for a, b in zip(cuts, cuts[1:])], hard[n]


def test_太宽的候选不量_切出来的行和逐个量一字不差():
    """`_split_wide` 从「每个起点都量」改成「量到放不下就停」，**切出来的行不许变一个字**。

    全库那一遍（112 条有字幕缓存的 spec × 四把尺子＝448 趟，和 origin/main 那版逐行比，
    0 趟不同；逐个量 247 秒、量到放不下就停 77 秒）是提交前跑的，太慢不进 CI；这里拿真字幕里最长的那些句子（没标点的 ASR 长句正是提速的对象）
    加几条构造的边角，四把尺子各比一遍。
    """
    if not OUTPUT.is_dir():
        pytest.skip("工作区没有 output/interviews（精简 worktree）")
    _pytest_needs_fonts()
    def longest(slug: str, k: int) -> list:
        spec = json.loads((SPECS / f"{slug}.json").read_text(encoding="utf-8"))
        words = clip.cached_words(spec["url"], OUTPUT / slug, spec)
        assert words, f"{slug} 的字幕缓存不在"
        keep = [(t, w) for t, w in words if spec["start"] <= t <= spec["end"]]
        return sorted(clip._sentences(keep), key=len, reverse=True)[:k]

    # 逐个量的参照是 O(n²)：最长的 304 词那一句（拉沃尔杯捧杯，ASR 一个标点都没打）
    # 一把尺子就要量四万多次，留给提交前那一遍全库比；这里 38~101 词的几句四把尺子都比
    sents = (longest("zheng-swiatek-us-open-2026-r4-presser", 3)
             + longest("federer-ithf-2026-induction-speech", 2)
             + longest("jodar-bublik-laver-cup-2026-interview", 1)
             + [[(0.0, "Supercalifragilisticexpialidocious" * 3)],    # 单个词就超宽
                [(float(i), w) for i, w in enumerate(
                    ("And the " + "Supercalifragilistic " * 6 + "and so on.").split())]])
    assert max(map(len, sents)) >= 90, "没挑到长句，这条就没测到提速的那一段"
    cases = [(name, sent) for name in clip.SEGMENT_RULERS for sent in sents]
    for name, sent in cases:
        width, bare = clip.ruler_width(name), clip.SEGMENT_RULERS[name][2]
        assert clip._split_wide(sent, clip._LINE_PX, width, bare) == \
            _split_wide_reference(sent, clip._LINE_PX, width, bare), (
                f"尺子 {name} 下这一句（{len(sent)} 词）切得不一样了：{clip._text(sent)[:80]}…")


def _run_scripts(workflow: str) -> str:
    """工作流里真会执行的 `run:` 脚本（去掉 shell 注释）——别拿整份 yml 的文本搜。"""
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8"))
    out = []
    for job in (wf.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            for ln in str(step.get("run") or "").splitlines():
                if not ln.lstrip().startswith("#"):
                    out.append(ln)
    return "\n".join(out)


@pytest.mark.parametrize("workflow", ["ci.yml", "interview-clip.yml",
                                      "interview-auto-render.yml"])
def test_老尺子的字体三个工作流都装着(workflow):
    """老尺子要量 Noto Sans 的字宽，它是 apt 的 `fonts-noto-core`。英文字幕换成仓库里的
    Inter 之后，**渲染已经用不着它了**——最容易被人当成死依赖删掉。删了的样子是
    `_measure_at` 报「量宽度要 …NotoSans-Regular.ttf，没有」，而且只在重渲已发片子时才撞上。
    出片（interview-clip）、dispatch 前预检（interview-auto-render）、CI 三处都要装。"""
    scripts = _run_scripts(workflow)
    for _path, pkg in clip._RULER_FONT_FILES.values():
        assert re.search(rf"(?<![\w-]){re.escape(pkg)}(?![\w-])", scripts), (
            f"{workflow} 没装 {pkg}——老尺子重切已发采访要量它的字宽")


def test_出片和预检都按spec的尺子切():
    """`segment()` 的出片、预检、人工请求建 spec 三个调用方都要把 `segment_ruler(spec)`
    传进去——漏一个就是那一处按默认尺子切，和另一处各说各话（预检绿、runner 红；或者
    请求按新尺子切行写好 `zh`，渲染按老尺子重切对不上）。`draft_interview_spec` 只建新
    slug（撞名就换名），新 slug 本来就是默认尺子，不在这张表里。"""
    import ast  # noqa: PLC0415

    for rel, owner in (("tools/build_interview_clip.py", "main"),
                       ("tools/interview_preflight.py", "subtitle_findings"),
                       ("tools/build_interview_request.py", "_build_one_unlocked")):
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == owner)
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                 and getattr(n.func, "attr", getattr(n.func, "id", "")) == "segment"]
        assert calls, f"{rel}::{owner} 里找不到 segment() 调用——判据没对上代码"
        for call in calls:
            kw = {k.arg: k.value for k in call.keywords}
            assert "ruler" in kw, f"{rel}::{owner} 调 segment() 没传 ruler"
    src = (ROOT / "tools/build_interview_clip.py").read_text(encoding="utf-8")
    assert "ruler := segment_ruler(spec)" in src


def test_预检按老尺子重切_已发的对得上(monkeypatch):
    """行为那一头：`interview_preflight.subtitle_findings`（dispatch 前的离线预检）对一条
    挂在老尺子上的已发 spec 重切——钉着就没有字幕红，把钉子拔掉就红在行数上。"""
    if not OUTPUT.is_dir():
        pytest.skip("工作区没有 output/interviews（精简 worktree）")
    _pytest_needs_fonts()
    import interview_preflight as pf  # noqa: PLC0415

    slug = "jodar-bublik-laver-cup-2026-interview"
    assert clip.segment_ruler({"slug": slug}) != clip.SEGMENT_RULER, "这条该挂在老尺子上"
    spec = json.loads((SPECS / f"{slug}.json").read_text(encoding="utf-8"))
    problems, _ = pf.subtitle_findings(spec)
    assert not [p for p in problems if "对不上" in p or "en_fixed" in p], problems
    monkeypatch.setattr(clip, "segment_ruler", lambda _spec: clip.SEGMENT_RULER)
    problems, _ = pf.subtitle_findings(spec)
    # 按默认尺子切成 99 行（zh 100 行）；出片那一趟先查 `en_fixed` 挂没挂错行，就红在那儿
    assert problems and "`en_fixed` 行号像是挂错了行" in problems[0], problems


def test_改老尺子表会叫醒auto_render():
    """老尺子表一改，dispatch 前预检重切字幕的结论就变——和另外两张存量表一样要在
    interview-auto-render 的 `on.push.paths` 里，不然要干等下一趟定时班次。
    （预检结论缓存的键按 `data/legacy_*.json` 取指纹，文件名带 `legacy_` 前缀才进得去。）"""
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github/workflows/interview-auto-render.yml").read_text(
        encoding="utf-8"))
    rel = clip.LEGACY_SEGMENT_RULER_FILE.relative_to(ROOT).as_posix()
    assert rel in (wf.get(True) or wf.get("on"))["push"]["paths"]
    assert clip.LEGACY_SEGMENT_RULER_FILE.name.startswith("legacy_")
