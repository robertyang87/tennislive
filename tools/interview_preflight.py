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


def _run_gate(fn, *args) -> tuple[str | None, str]:
    """跑一道会 `SystemExit` 的闸 → (红的原因 或 None, 它打印的东西)。

    ⚠️ **stdout 必须收住**：`pick_interview_renders` 的 stdout 第二行起是 dispatch
    名单（workflow 拿 `tail -n +2` 切），闸里一句 `[解读卡] 自有画面…` 漏出去就是
    把一行废话当 slug 投出去。
    """
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            fn(*args)
    except SystemExit as exc:
        return (str(exc.code) if exc.code not in (None, 0) else None), buf.getvalue()
    except ImportError as exc:
        raise PreflightUnavailable(f"{getattr(fn, '__name__', fn)}：{exc}") from exc
    except Exception as exc:  # noqa: BLE001 —— 缺字段的 spec 在 runner 上一样会崩在这一步
        # ⚠️ 别让一条坏 spec 把 `pick_interview_renders` 整个带崩——那样同一趟里
        # 别的 slug 也投不出去。它在 runner 上照样会红，所以记成红，不是放行。
        return f"{type(exc).__name__}: {exc}", buf.getvalue()
    return None, buf.getvalue()


def _materialize_captions(slug: str, dest: Path) -> bool:
    """把仓库里这条的字幕缓存放进 `dest`。工作区里有就拷，没有就从 HEAD 取
    （interview-auto-render 的稀疏检出不带 output/，而 index 里全量都在）。"""
    src = OUTPUT / slug
    found = False
    if src.is_dir():
        for p in src.glob("cap_*.json3"):
            shutil.copy2(p, dest / p.name)
            found = True
        return found
    listing = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", f"output/interviews/{slug}/"],
        capture_output=True, text=True, check=False, timeout=30).stdout.split()
    for rel in listing:
        name = rel.rsplit("/", 1)[-1]
        if name.startswith("cap_") and name.endswith(".json3"):
            blob = subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:{rel}"],
                                  capture_output=True, check=False, timeout=30)
            if blob.returncode == 0:
                (dest / name).write_bytes(blob.stdout)
                found = True
    return found


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


def copy_problem(slug: str, date: str = "") -> str | None:
    """`push_reel --stage check`：tag ≤ 5、标题 ≤ 20 字位——runner「发布文案前置检查」同一条命令。"""
    from production_preflight import check_copy  # noqa: PLC0415
    date = date or datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    try:
        check_copy(SPECS / f"{slug}.xhs.txt", "赛后开麦", date=date, quiet=True)
    except subprocess.CalledProcessError as exc:
        tail = (exc.stderr or exc.stdout or "").strip().splitlines()[-3:]
        return "文案（push_reel --stage check）：" + " / ".join(tail)
    return None


def spec_problems(spec: dict, *, copy: bool = True,
                  date: str = "") -> tuple[list[str], list[str]]:
    """一条 spec 的离线预检 → (红, 提示)。环境不全抛 `PreflightUnavailable`。"""
    _require_env()
    import build_interview_clip as clip  # noqa: PLC0415

    problems: list[str] = []
    notes: list[str] = []
    slug = str(spec.get("slug") or "")
    for gate in (clip.check_source_contract, clip.check_topline_format,
                 clip.check_score_orientation, clip.check_opening,
                 clip.check_lead_in, clip.check_trail_in, clip.check_copy_page,
                 clip.check_takeaway):
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
