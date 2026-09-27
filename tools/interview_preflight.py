#!/usr/bin/env python3
"""赛后开麦的**离线预检**——「赛场之上」`--dry-run` 在这条线上的对应物。

只读 spec、仓库里落着的字幕缓存和字体，**不联网、不下源片、几秒跑完**，把
runner 上必红的那些「只看 spec 就判得出」的错在 dispatch 之前报出来。

    python tools/interview_preflight.py --slug <slug>
    python tools/interview_preflight.py --spec specs/interviews/<slug>.json --skip-copy

退出码：0＝没有红（可能带 ⚠️ 提示），1＝有红，2＝环境不全（缺 PIL／字体），判不了。

## 来路

2026-09-25~27 三天里，下面这些**只看 spec 就判得出**的错，都是在 runner 上
装完依赖、取完字幕（中位 146 秒）甚至渲完整条片子之后才报出来的：

| 错 | 次数／例子 | 在 runner 上哪一步才报 |
|---|---|---|
| 中文超宽 952px／吊在「的」上／中英行数对不上 | 12 趟（alcaraz-fritz 117:114 等） | `--stage subs/verify/render` 的 `write_ass` |
| 小红书 tag 超过 5 个、标题超 20 字位 | 9 趟（tien-cobolli 653b6d60、nakashima f8de57d3） | 「发布文案前置检查」 |
| 收尾卡那一句折成两行、折在人名中间 | jodar-bublik 48a60760、deminaur 617db353 | **渲完抽帧才看见** |
| 顶栏比分写成输家视角 | zheng-rybakina 857f1fbc | 没有闸 |

这些判据**原来就在** `build_interview_clip.py` 里（除了后两条新加的，在
`interview_spec_gates`），只是每一道都排在装依赖、联网之后。这里按出片那一趟
**同一个顺序、同一份函数**调一遍——不抄第二份，写两处必分叉（`pick_interview_renders`
的 docstring 记过它的代价：判定和闸一分叉，就是白烧一趟 runner 再永久卡死）。

## 查什么

**红（runner 上一定会红的）**：L0 来源身份、顶栏赛事行格式、顶栏比分方向、开场认领、
冷开场／片尾那两段、小红书正文在不在、解读卡（含「一行放得下」）、文案的 tag／标题
（`push_reel --stage check`，和 runner 的「发布文案前置检查」同一条命令）、以及
**按仓库里的字幕缓存重切一遍行**之后走 `write_ass` 那一整套（行数对齐、中英超宽、
吊尾虚词、顶栏宽度、`highlight_en`）。

**⚠️（只报不拦）**：没有字幕缓存所以行数没对上号；`end` 离最后一个词还有好几秒
（片尾板要在出片那一趟按帧量，见 `interview_tail`）；转正那道措辞闸的口径。
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "specs" / "interviews"
OUTPUT = ROOT / "output" / "interviews"
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))


class PreflightUnavailable(RuntimeError):
    """环境不全（缺 PIL／字体／项目包），**判不了**——和「判了没问题」要分开。"""


def _require_env() -> None:
    import build_interview_clip as clip  # noqa: PLC0415
    from interview_spec_gates import POINT_FONT  # noqa: PLC0415
    try:
        import PIL  # noqa: F401, PLC0415
    except ImportError as exc:
        raise PreflightUnavailable("缺 PIL（`pip install -e .`）") from exc
    missing = [p for p, _ in clip._FONT_FILES.values() if not Path(p).exists()]
    if not POINT_FONT.exists():
        missing.append(str(POINT_FONT))
    if missing:
        raise PreflightUnavailable(
            "量宽度要的字体不在：" + "、".join(missing)
            + "（中文那支是 apt 的 fonts-noto-cjk，别拿回退字体凑合）")


def _run_gate(fn, *args,
              env_errors: tuple[type[BaseException], ...] = (ImportError,)
              ) -> tuple[str | None, str]:
    """跑一道会 `SystemExit` 的闸 → (红的原因 或 None, 它打印的东西)。

    ⚠️ **stdout 必须收住**：`pick_interview_renders` 的 stdout 第二行起是 dispatch
    名单（workflow 拿 `tail -n +2` 切），闸里一句 `[解读卡] 自有画面…` 漏出去就是
    把一行废话当 slug 投出去。

    `env_errors`：哪些异常算「环境不全、判不了」（抛 `PreflightUnavailable`），
    其余异常记成红。全量模式只认 ImportError——`_require_env` 先把字体查过了；
    探针（`probe_problems`）连 OSError 也算判不了，见那边的 docstring。
    """
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            fn(*args)
    except SystemExit as exc:
        return (str(exc.code) if exc.code not in (None, 0) else None), buf.getvalue()
    except env_errors as exc:
        raise PreflightUnavailable(f"{getattr(fn, '__name__', fn)}：{exc}") from exc
    except Exception as exc:  # noqa: BLE001 —— 缺字段的 spec 在 runner 上一样会崩在这一步
        # ⚠️ 别让一条坏 spec 把 `pick_interview_renders` 整个带崩——那样同一趟里
        # 别的 slug 也投不出去。它在 runner 上照样会红，所以记成红，不是放行。
        return f"{type(exc).__name__}: {exc}", buf.getvalue()
    return None, buf.getvalue()


def _is_caption(name: str) -> bool:
    return name.startswith("cap_") and name.endswith(".json3")


def _head_captions(slug: str) -> list[tuple[str, str]] | None:
    """HEAD 里这条的字幕缓存 → [(文件名, blob 号)]；git 用不了返回 None。

    interview-auto-render 的稀疏检出不带 output/，而 HEAD 的树里全量都在。"""
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), "ls-tree", "-r", "HEAD", "--", f"output/interviews/{slug}/"],
            capture_output=True, text=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    rows = []
    for ln in proc.stdout.splitlines():
        meta, _, rel = ln.partition("\t")
        parts = meta.split()
        name = rel.rsplit("/", 1)[-1]
        if len(parts) == 3 and parts[1] == "blob" and _is_caption(name):
            rows.append((name, parts[2]))
    return rows


def _materialize_captions(slug: str, dest: Path) -> bool:
    """把仓库里这条的字幕缓存放进 `dest`。工作区里有这个目录就**只**拷工作区的
    （含还没提交的），没有就从 HEAD 取。⚠️ 这个分支口径和 `caption_fingerprint`
    是同一份——预检结论缓存按后者作废，两边读的不是同一组文件，缓存就会替一份
    没判过的输入说话。"""
    src = OUTPUT / slug
    found = False
    if src.is_dir():
        for p in src.iterdir():
            if p.is_file() and _is_caption(p.name):
                shutil.copy2(p, dest / p.name)
                found = True
        return found
    for name, blob_id in _head_captions(slug) or []:
        blob = subprocess.run(["git", "-C", str(ROOT), "cat-file", "blob", blob_id],
                              capture_output=True, check=False, timeout=30)
        if blob.returncode == 0:
            (dest / name).write_bytes(blob.stdout)
            found = True
    return found


def _blob_id(data: bytes) -> str:
    """和 `git hash-object` 同一个算法：工作区里没改过的文件，和 HEAD 里那份指纹一样。"""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def caption_fingerprint(slug: str) -> list[str] | None:
    """`_materialize_captions` 会放进去的**那几份**字幕缓存的指纹 → ["文件名:blob 号"]。

    给 `pick_interview_renders.verdict_key` 用（review 那条）：原来那边按 `git ls-files`
    （index）记字幕，而这里工作区有目录就读工作区——interview-auto-render 把待处理请求的
    产物格加回稀疏范围、只提交其中的 `cap_asr.json3`，于是全量预检吃的是没提交的
    `cap_*`，记的却是下一趟 HEAD 一模一样能复现的键。现在两边走同一个分支；工作区的
    文件按 git 的 blob 算法取指纹，内容和 HEAD 一样时键也一样（不多逼一趟全量）。
    git 用不了返回 None（不用缓存）。"""
    src = OUTPUT / slug
    if src.is_dir():
        return sorted(f"{p.name}:{_blob_id(p.read_bytes())}" for p in src.iterdir()
                      if p.is_file() and _is_caption(p.name))
    rows = _head_captions(slug)
    return None if rows is None else sorted(f"{name}:{blob}" for name, blob in rows)


def subtitle_findings(spec: dict) -> tuple[list[str], list[str]]:
    """按仓库里的字幕缓存重切一遍行，再走出片那一趟的 `write_ass` 全套 → (红, 提示)。"""
    import build_interview_clip as clip  # noqa: PLC0415
    from interview_tail import cache_word_spans, quiet_tail_note  # noqa: PLC0415

    slug = str(spec.get("slug") or "")
    problems: list[str] = []
    notes: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        if not _materialize_captions(slug, work):
            notes.append("仓库里没有这条的字幕缓存（cap_*.json3），行数对齐和字幕宽度"
                         "要等 runner 的 `--stage subs` 取完字幕才判得了")
            return problems, notes
        words = clip.cached_words(str(spec.get("url") or ""), work, spec)
        if words is None:
            notes.append("字幕缓存和这条 URL 对不上（换过候选视频？），行数对齐没法离线判")
            return problems, notes
        if note := quiet_tail_note(spec, cache_word_spans(work, spec)):
            notes.append(note)
        with contextlib.redirect_stdout(io.StringIO()):
            lines = clip.segment(words, spec["start"], spec["end"],
                                 budget=spec.get("segment_budget_px"),
                                 word_fix=spec.get("word_fix"))
        for k, v in (spec.get("en_fixed") or {}).items():
            idx = int(k) - 1
            if 0 <= idx < len(lines):
                lines[idx]["en"] = v
        with contextlib.redirect_stdout(io.StringIO()):
            clip.strip_hesitation_lines(lines)
        err, _ = _run_gate(clip.check_human_quote, spec, lines, work)
        if err:
            problems.append(f"人工引语对不上：{err}")
        zh = spec.get("zh") or []
        if not zh:
            notes.append(f"切出 {len(lines)} 行英文，spec 里还没有中文")
            return problems, notes
        err, _ = _run_gate(clip.write_ass, lines, zh, spec["start"], work / "x.ass",
                           spec)
        if err:
            problems.append(f"字幕（出片那一趟 write_ass 会红在这儿）：{err}")
    return problems, notes


#: 这一条红**不是判据判的**，是工具自己崩了（`push_reel` 抛了 Traceback）——runner 上
#: 那一步未必同样崩。`pick_interview_renders` 见到它就**不记进预检结论缓存**：不然一次
#: 偶发的崩溃会被探针当成「同一份输入判过是红的」一直重放到北京日期翻过去（review 那条）。
CRASHED = "［工具崩了，不是判据红］"


def copy_problem(slug: str, date: str = "") -> str | None:
    """`push_reel --stage check`：tag ≤ 5、标题 ≤ 20 字位——runner「发布文案前置检查」同一条命令。"""
    from production_preflight import check_copy  # noqa: PLC0415
    date = date or datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    try:
        check_copy(SPECS / f"{slug}.xhs.txt", "赛后开麦", date=date, quiet=True)
    except subprocess.CalledProcessError as exc:
        out = exc.stderr or exc.stdout or ""
        tail = out.strip().splitlines()[-3:]
        crashed = CRASHED if "Traceback (most recent call last)" in out else ""
        return f"文案（push_reel --stage check）{crashed}：" + " / ".join(tail)
    return None


def _spec_gates(clip) -> tuple:
    """出片那一趟 `main()`／`render()` 开头的只读 spec 的闸，同一个顺序。"""
    return (clip.check_source_contract, clip.check_topline_format,
            clip.check_score_orientation, clip.check_opening,
            clip.check_lead_in, clip.check_trail_in, clip.check_copy_page,
            clip.check_takeaway)


#: 缺 PIL／字体时判不了的那几项（`probe_problems` 原样报出来，不当成判过了）。
NEEDS_RENDER_ENV = ("文案（push_reel --stage check）", "字幕重切（write_ass 量宽）")


def probe_problems(spec: dict) -> tuple[list[str], list[str]]:
    """**不要 PIL／字体**的那一半预检 → (红, 判不了的项)。

    给 interview-auto-render 那个「没活就早退」的探针用：它跑在 runner 的系统
    python3 上（没有 PIL，2026-09-09 的日志：`No module named 'PIL'`），`spec_problems`
    在那儿一律抛 `PreflightUnavailable`，于是只要有一条 spec 过了便宜的几项，就逼着
    整个 job 装一遍依赖——一条卡在量宽度上的红 spec 能让它每 10 分钟全量跑一趟。
    这里只跑不要量宽度的闸（和 `spec_problems` **同一组函数、同一个顺序**）；
    要 PIL 的那几项（解读卡一行放不放得下、文案、字幕重切）**记成判不了**，
    由调用方决定怎么处理——`pick_interview_renders --probe` 拿上一趟全量预检记下的
    结论顶上，没有就交给全量那一趟。

    ⚠️ **OSError 在这儿也算判不了**（review 那条）：探针排在 apt 装 fonts-noto-cjk
    之前，哪天系统 python3 带上了 PIL，`check_trail_in`／`check_lead_in` 量双语字幕宽度
    就会撞上「中文字体不在」的 OSError——那是环境不全，记成红就是一次「没活就早退」的
    假早退。全量模式不放宽：`_require_env` 已经先把字体查过了。
    """
    import build_interview_clip as clip  # noqa: PLC0415

    problems: list[str] = []
    unknown: list[str] = []
    for gate in _spec_gates(clip):
        try:
            err, _ = _run_gate(gate, spec, env_errors=(ImportError, OSError))
        except PreflightUnavailable as exc:
            unknown.append(f"{gate.__name__}（{exc}）")
            continue
        if err:
            problems.append(f"{gate.__name__}：{err}")
    return problems, unknown + list(NEEDS_RENDER_ENV)


def spec_problems(spec: dict, *, copy: bool = True,
                  date: str = "") -> tuple[list[str], list[str]]:
    """一条 spec 的离线预检 → (红, 提示)。环境不全抛 `PreflightUnavailable`。"""
    _require_env()
    import build_interview_clip as clip  # noqa: PLC0415

    problems: list[str] = []
    notes: list[str] = []
    slug = str(spec.get("slug") or "")
    for gate in _spec_gates(clip):
        err, _ = _run_gate(gate, spec)
        if err:
            problems.append(f"{gate.__name__}：{err}")
    if copy and (SPECS / f"{slug}.xhs.txt").is_file():
        if err := copy_problem(slug, date):
            problems.append(err)
    try:
        sub_bad, sub_notes = subtitle_findings(spec)
    except ImportError as exc:
        raise PreflightUnavailable(f"字幕重切：{exc}") from exc
    except Exception as exc:  # noqa: BLE001 —— 同 `_run_gate`：坏 spec 记红，不带崩调用方
        sub_bad, sub_notes = [f"字幕重切：{type(exc).__name__}: {exc}"], []
    problems += sub_bad
    notes += sub_notes
    from spec_wording import check_interview_copy_wording  # noqa: PLC0415
    xhs = SPECS / f"{slug}.xhs.txt"
    wording = check_interview_copy_wording(
        spec, xhs.read_text(encoding="utf-8") if xhs.is_file() else None)
    notes += [f"措辞（转正那道闸的口径，runner 不拦）：{w}" for w in wording]
    return problems, notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--slug")
    who.add_argument("--spec")
    ap.add_argument("--skip-copy", action="store_true",
                    help="不跑 push_reel --stage check（工作流前面那一步已经跑过）")
    ap.add_argument("--date", default="", help="标题里的日期，默认今天（北京时间）")
    args = ap.parse_args(argv)
    path = Path(args.spec) if args.spec else SPECS / f"{args.slug}.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    try:
        problems, notes = spec_problems(spec, copy=not args.skip_copy, date=args.date)
    except PreflightUnavailable as exc:
        print(f"[预检] 判不了：{exc}")
        return 2
    for n in notes:
        print(f"⚠️ {n}")
    for p in problems:
        print(f"❌ {p}")
    print(f"[预检] {spec.get('slug')}：{len(problems)} 处红，{len(notes)} 条提示"
          + ("——修完再 dispatch" if problems else "——可以 dispatch"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
