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

**红（runner 上一定会红的）**：全称断言要认领两个源（runner「发布文案前置检查」那一步
的 `check_interview_claims`）、L0 来源身份、Tennis TV 台标挪没挪出窗口、顶栏赛事行格式、
顶栏比分方向、开场认领、冷开场／片尾那两段、**已知带片尾板的源（拉沃尔杯、Tennis TV）上手写
spec 的 `end` 离最后一个词太远**（`interview_tail.quiet_tail_problem`，认领 `_end_why`）、
小红书正文在不在、文案不提字幕规格、封面 `hook_accent`、
账号所有者的口味闸（`check_taste`：标题和推送标题同一个数只能有一个说法；
`check_taste_extra`：总分差、赛点同义反复、小红书正文 markdown）、解读卡（含「一行放得下」）、
文案的 tag／标题（`push_reel --stage check`，和 runner 的「发布文案前置检查」同一条命令）、以及
**按仓库里的字幕缓存重切一遍行**之后走 `write_ass` 那一整套（`en_fixed` 行号错位、
行数对齐、中英超宽、吊尾虚词、顶栏宽度、`highlight_en`）；以及**已提交的封面扫描记录**
（`cover_candidates.json`）和 `cover.frame_at` 对不对得上（`cover_scan_problem`，2026-09-28）——
记录外没扫过的一格、或者记录里明写着没过闸**而 render 自动换帧也救不了**的那一格，runner 的
`--check`／推送闸一样拦，不必等装完依赖、下完源片（红的时候顺手报出记录里能换的那一格，
或者过闸的那几格）；记录里已经有一格 render 会自动换上的，不拦、只提示（D3，`render_would_swap`）。

**⚠️（只报不拦）**：没有字幕缓存所以行数没对上号；`end` 离最后一个词还有好几秒
（片尾板要在出片那一趟按帧量，见 `interview_tail`）；转正那道措辞闸的口径。

**转写那两道闸（分歧、空档）按 subs 交的判定判**（2026-09-28，`build_interview_clip.subs_verdict`）：
当前转写指纹上已经量出来的红，两种口径都是红；**缺**判定（没有字幕缓存、没有当前指纹的
第二份 ASR 量数或 VAD 证据）在本地默认口径下只提示，`--require-subs`（dispatch 口径：
interview-clip 的 render 那一趟、`pick_interview_renders` 自动 dispatch 之前）下是带
`NEEDS_SUBS` 的红——自动链见到只卡在这一类上的，先投 `mode=subs`。来路：9/20~9/28 六趟
render 红在「空档没销账／转写分歧超阈」，0/6 在 dispatch 之前拦得住。

⭐ **interview-clip 的 render 那一趟只对自动链拨的 run 用 dispatch 口径**（`--dispatched-by`，
2026-09-28 会话决定，时效第一）：`--require-subs` 原来对每一趟 render 都开，而已推送的 54 条
采访里 46 条在 dispatch 口径下是 `NEEDS_SUBS`（判定是老产物、没记区间和源——wp/round3-int
HEAD 上按 `subtitle_findings(require_subs=True)` 实测），手动重渲一条就得先多拨一趟
`mode=subs`（取字幕约 1 分钟＋第二份 ASR 3~5 分钟，工作流顶上那张表）。
手动拨的（派发者是个人）缺判定只提示，同一个 job 里「转写交叉校验」那一步在判定不是 ok 时现量第二份 ASR
（上线 subs 之前的老路，`--stage verify` 在判定不是 ok 时本来就重量）；**已经量出来的红照旧红**。
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
    # 切行的老尺子（已发 spec 按当年那支字体重切）也是量宽度要的字体，一样查
    missing = [p for p, _ in (*clip._FONT_FILES.values(), *clip._RULER_FONT_FILES.values())
               if not Path(p).exists()]
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


def _is_subs_input(name: str) -> bool:
    """预检离线要读的那几份：字幕缓存，外加 subs 那一趟交的判定（`SUBS_VERDICT_FILES`）。

    判定文件名从 `build_interview_clip` 取、函数里 import——顶层只许标准库（探针的系统
    python3），而名单只许有一份（写两处必分叉）。"""
    from build_interview_clip import SUBS_VERDICT_FILES  # noqa: PLC0415
    return _is_caption(name) or name in SUBS_VERDICT_FILES


def _head_captions(slug: str) -> list[tuple[str, str]] | None:
    """HEAD 里这条的字幕缓存和 subs 判定（`_is_subs_input`）→ [(文件名, blob 号)]；
    git 用不了返回 None。

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
        if len(parts) == 3 and parts[1] == "blob" and _is_subs_input(name):
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
            if p.is_file() and _is_subs_input(p.name):
                shutil.copy2(p, dest / p.name)
                found = found or _is_caption(p.name)
        return found
    for name, blob_id in _head_captions(slug) or []:
        blob = subprocess.run(["git", "-C", str(ROOT), "cat-file", "blob", blob_id],
                              capture_output=True, check=False, timeout=30)
        if blob.returncode == 0:
            (dest / name).write_bytes(blob.stdout)
            found = found or _is_caption(name)
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
    git 用不了返回 None（不用缓存）。

    ⚠️ **subs 交的判定（`SUBS_VERDICT_FILES`）也在里面**（2026-09-28）：预检要读它判
    「这一版转写能不能投 render」，一趟 subs 落了新判定、字幕缓存一个字节没变——
    键不跟着变的话，探针会拿「当时还缺判定」那份旧结论一直顶到北京日期翻过去。"""
    src = OUTPUT / slug
    if src.is_dir():
        return sorted(f"{p.name}:{_blob_id(p.read_bytes())}" for p in src.iterdir()
                      if p.is_file() and _is_subs_input(p.name))
    rows = _head_captions(slug)
    return None if rows is None else sorted(f"{name}:{blob}" for name, blob in rows)


#: 「当前这一版还缺 subs 那一趟的判定」——不是 spec 写错了，是**还没量**。
#: `pick_interview_renders` 见到一条 spec 只卡在这一类上，就先投 `mode=subs`
#: 而不是 render（也不是干等人）；别的红混在里面就照旧进等待名单。
NEEDS_SUBS = "［要先跑 subs］"
#: 派发者登录名以它结尾 ＝ 工作流用 `GH_TOKEN: github.token` 派发的（interview-auto-render 的
#: pick 那一步）。和 `build_dashboard_snapshot.is_unattended` 同一个判法——那边 2026-09-27 实测：
#: 编排链派发的 `interview-clip` 36337385713 的 `triggering_actor` 是 `github-actions[bot]`，
#: 会话拨的 run 是个人登录名。
BOT_SUFFIX = "[bot]"
#: subs 已在当前转写指纹上量出来的红（分歧超闸没认领够、VAD 在空档里听到了人声）的前缀。
#: ⚠️ 不写「render 会红在这儿」：render 的 verify 在判定不是 ok 时会**重量**一遍
#: （第二份 ASR 不是确定性的），它红不红要看那一趟——这里只说量出来了什么。
SUBS_RED = "转写（subs 在当前转写指纹上量出来的）："
#: **碰转写本身**的红（2026-09-28 D2）：有它在，自动链不先投 subs——subs 那一趟自己也死在
#: 同一处（L0、`en_fixed` 挂错行、人工引语对不上、切行崩了，`main()` 在切行前后拦，不分档），
#: 或者改完这一处转写指纹多半跟着变，这一趟量的就是旧的那一版。**不在这张表里的红**
#: （中文、封面、文案、解读卡、冷开场、顶栏……）不碰转写指纹，subs 那两档只报不拦
#: （`build_interview_clip.TRANSCRIPT_STAGES`），**不挡 subs**——第二份 ASR 和写中文、挑封面并行跑。
EN_FIXED_RED = "`en_fixed` 行号像是挂错了行"
HUMAN_QUOTE_RED = "人工引语对不上："
RESEGMENT_RED = "字幕重切："
#: 「已知带片尾板的源上 `end` 离最后一个词太远」那道红的开头——它由另一条同期改动加进
#: `subtitle_findings`（`interview_tail.quiet_tail_problem`，报 `片尾板：…`），那边没合进来之前
#: 这一项不命中任何东西。改的是 `end`，第二份 ASR 量的区间跟着变，先投的那趟 subs 白跑一趟
#: （复审第四轮：两边哪个先合，这一项都认得出）
TAIL_BOARD_RED = "片尾板："
TRANSCRIPT_REDS = ("check_source_contract：", EN_FIXED_RED, HUMAN_QUOTE_RED, RESEGMENT_RED,
                   TAIL_BOARD_RED)


def picker_dispatched(actor: str | None) -> bool:
    """interview-clip 这一趟 render 是不是**自动链的 pick** 派发的（`github.triggering_actor`）。

    是 → dispatch 口径（`require_subs`）：pick 投 render 之前已经按同一个口径判过「判定干净」
    （`pick_interview_renders`，缺判定就先投 subs），runner 上再判一次防的是 pick 和 run 之间
    spec 被改了——自动链行为不变。
    不是（会话／人手动拨的、GitHub 页面上点的重跑）→ 本地口径：缺判定只提示，「转写交叉校验」
    那一步在同一个 job 里现量第二份 ASR（2026-09-28 会话决定：已推送的 54 条里 46 条的判定
    是没记区间和源的老产物，手动重渲不该先多拨一趟 `mode=subs`（取字幕约 1 分钟＋第二份 ASR 3~5 分钟））。
    **认不出（空串）按手动算**：那一支照样验转写，只是慢几分钟；按自动算会把人挡在门外。"""
    return str(actor or "").strip().endswith(BOT_SUFFIX)


def subtitle_findings(spec: dict, *, require_subs: bool = False
                      ) -> tuple[list[str], list[str]]:
    """按仓库里的字幕缓存重切一遍行，再走出片那一趟的 `write_ass` 全套 → (红, 提示)。

    `require_subs`（dispatch 那一刻的口径，2026-09-28）：**缺字幕缓存、缺当前转写指纹
    的 subs 判定都记成红**（带 `NEEDS_SUBS`），不再只是提示——原来缺缓存只报一句 ⚠️，
    自动链照投 render，于是字幕排版那一整套闸和转写那两道闸都要等 runner 装完依赖、
    下完源片才判（interview 线第一趟就成的只有 2/13）。本地 CLI 默认仍是提示，
    `--require-subs` 打开；**已经量出来的红**（`subs_verdict` 判 red）两种口径都是红。"""
    import build_interview_clip as clip  # noqa: PLC0415
    from interview_tail import cache_word_spans, quiet_tail_problem  # noqa: PLC0415

    slug = str(spec.get("slug") or "")
    problems: list[str] = []
    notes: list[str] = []

    def not_yet(msg: str) -> None:
        if require_subs:
            problems.append(f"{NEEDS_SUBS}{msg}——先投 `mode=subs`（取字幕切行＋第二份 ASR），"
                            "判定落库了再投 render")
        else:
            notes.append(msg)

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        if not _materialize_captions(slug, work):
            not_yet("仓库里没有这条的字幕缓存（cap_*.json3），行数对齐、字幕宽度和转写那两道闸"
                    "要等 runner 的 `--stage subs` 取完字幕才判得了")
            return problems, notes
        words = clip.cached_words(str(spec.get("url") or ""), work, spec)
        if words is None:
            not_yet("字幕缓存和这条 URL 对不上（换过候选视频？），行数对齐没法离线判")
            return problems, notes
        tail_red, tail_note = quiet_tail_problem(spec, cache_word_spans(work, spec))
        if tail_red:
            problems.append(f"片尾板：{tail_red}")
        if tail_note:
            notes.append(tail_note)
        with contextlib.redirect_stdout(io.StringIO()):
            lines = clip.segment(words, spec["start"], spec["end"],
                                 budget=spec.get("segment_budget_px"),
                                 word_fix=spec.get("word_fix"),
                                 ruler=clip.segment_ruler(spec),
                                 language_windows=clip.transcript_language_windows(spec))
        # `main()` 在套 `en_fixed` 之前先查行号挂没挂错（0 起写成 1 起就整体错一行），
        # 挂错了当场 SystemExit——这里同一个位置、同一个函数；后面的量宽建在错位的行上，
        # 报出来也是噪声，所以和 runner 一样到此为止。
        if bad := clip.en_fixed_misaligned(lines, spec.get("en_fixed") or {}):
            problems.append(f"{EN_FIXED_RED}（键是 **1 起** 的行号）："
                            + "；".join(bad))
            return problems, notes
        for k, v in (spec.get("en_fixed") or {}).items():
            idx = int(k) - 1
            if 0 <= idx < len(lines):
                lines[idx]["en"] = v
        with contextlib.redirect_stdout(io.StringIO()):
            clip.strip_hesitation_lines(lines)
        # **转写那两道闸（分歧、空档）按 subs 交的判定判**——和 render 的 verify 一步
        # 同一个函数、同一份行（`main()` 在同一个位置算指纹）。
        verdict = clip.subs_verdict(spec, lines, work)
        problems += [f"{SUBS_RED}{r}" for r in verdict.reds]
        if verdict.state == "needs_subs":
            not_yet("；".join(verdict.pending))
        err, _ = _run_gate(clip.check_human_quote, spec, lines, work)
        if err:
            problems.append(f"{HUMAN_QUOTE_RED}{err}")
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


def _cover_record_raw(slug: str) -> bytes | None:
    """已提交的封面扫描记录原文。**和字幕缓存同一个分支口径**（`_materialize_captions`）：
    工作区有这条的产物目录就只认工作区，没有就从 HEAD 取——interview-auto-render 的稀疏
    检出不带 output/，而 HEAD 的树里全量都在。没有记录返回 None。"""
    from interview_cover_scan import RECORD_NAME  # noqa: PLC0415

    src = OUTPUT / slug
    if src.is_dir():
        path = src / RECORD_NAME
        return path.read_bytes() if path.is_file() else None
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"HEAD:output/interviews/{slug}/{RECORD_NAME}"],
            capture_output=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def cover_record_fingerprint(slug: str) -> str:
    """封面扫描记录的 blob 号（没有就是空串）。`pick_interview_renders.verdict_key` 要它：
    记录一换（`mode=cover` 重扫、render 自动换帧），缓存里那条预检结论就作废。"""
    raw = _cover_record_raw(slug)
    return "" if raw is None else _blob_id(raw)


def cover_scan_verdict(spec: dict) -> tuple[str | None, str | None]:
    """已提交的封面扫描记录和 `cover.frame_at` → (红的原因, 提示)。对得上（或没有记录）→ (None, None)。

    判据就是 runner 那一步 `interview_cover_scan.py --check` 和推送闸 `cover_scan_gate`
    调的同一个 `record_problem`（取景变过、尺子变过的旧记录都不管）。

    ⭐ **frame_at 在记录里没过闸、可记录里已经有一格 render 会自动换上的**（`render_would_swap`：
    同一个窗口、同一个间隔、取景和尺子都没变，render 红了就地重扫量出来的就是这几格）→
    **不拦**，只给一条提示：render 的封面前置那一步自己会换（2026-09-28 D3）。拦下来等人
    把那个数抄进 spec，只是多等一个来回——时效第一。

    红的时候：记录里有机器能换、但 render 未必扫得到的一格（窗口／间隔对不上）→ 报出来，
    改一个数就能 dispatch；**过闸的有、机器一格都换不了**（主角没官方头像、认人拿不准……）→
    把过闸的那几格列出来让人挑，不说「换一段重扫」——重扫扫出来的还是这几格；一格都没过闸
    才叫人换一段（cover.scan_window）重扫。
    """
    from interview_cover_scan import (  # noqa: PLC0415
        blocked_summary,
        find_entry,
        pick,
        record_problem,
        render_would_swap,
    )

    raw = _cover_record_raw(str(spec.get("slug") or ""))
    if raw is None:
        return None, None
    try:
        record = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        record = {"method": "unreadable"}
    problem = record_problem(record, spec)
    if not problem:
        return None, None
    swap = render_would_swap(record, spec)
    if swap is not None:
        return None, (f"封面 cover.frame_at={(spec.get('cover') or {}).get('frame_at')} 在已提交的扫描记录里"
                      f"没过闸，记录里已经有一格 render 会自动换上的（{swap['frame_at']:g} 秒：过闸、认得出是"
                      "封面主角、眼睛睁着）——不拦，render 的封面前置那一步自己换")
    best = pick(record, spec) if isinstance(record, dict) else None
    passing = [t for t in (record.get("passing") or [])] if isinstance(record, dict) else []
    if best is not None:
        hint = (f"记录里过闸、认得出是封面主角、眼睛睁着、余量最大的是 {best['frame_at']:g} 秒——"
                "改成它就行")
    elif passing:
        entries = [e for t in passing if (e := find_entry(record, t)) is not None]
        hint = (f"记录里过闸的有 {'、'.join(f'{t:g}' for t in passing[:5])} 秒"
                f"（按余量排{'，共 ' + str(len(passing)) + ' 格' if len(passing) > 5 else ''}），"
                f"可没有一格机器能自动换（{blocked_summary(entries, spec)}）——在这几格里挑一格写进"
                " frame_at（mode=cover 的候选墙上看过眼睛和是不是本人；认人拿不准的写 cover._face_check_why）")
    else:
        hint = "记录里一格都没过闸——换一段（cover.scan_window）重扫"
    return f"{problem}（{hint}）", None


def cover_scan_problem(spec: dict) -> str | None:
    """`cover_scan_verdict` 的红那一半（dispatch 之前拦不拦）。"""
    return cover_scan_verdict(spec)[0]


def _cover_scan_note(spec: dict) -> str | None:
    """`cover_scan_verdict` 的提示那一半（不拦）；判不了（坏记录抛了）就不提示——红那一半
    在 `_check_cover_scan` 里照样跑、照样记。"""
    try:
        return cover_scan_verdict(spec)[1]
    except Exception:  # noqa: BLE001
        return None


def _check_cover_scan(spec: dict) -> None:
    """`cover_scan_problem` 的闸形状（红就 SystemExit），给 `_run_gate` 用。"""
    if problem := cover_scan_problem(spec):
        raise SystemExit(problem)


def _spec_gates(clip) -> tuple:
    """runner 上只读 spec 的闸，**同一份函数、同一个顺序**：

    1. 「发布文案前置检查」那一步（`production_preflight.main`）的全称断言闸——
       那一步排在出片之前，文案那一半是 `copy_problem`；
    2. 出片那一趟 `main()` 开头那一排 `check_*(spec)`；
    3. `render()` 开头的 `check_takeaway`。

    ⚠️ 2、3 两段**不许手抄**：判据 `test_预检的闸和出片那一趟main开头那一排是同一份`
    按 ast 从 `main()`／`render()` 抠出来比。手抄过一次就漏了 `check_cover_hook`
    （review 那条：`hook_accent` 不在标题里，预检绿、runner 第一秒红、stale 规则
    每 70 分钟重投一次）。
    """
    from production_preflight import check_interview_spec_claims  # noqa: PLC0415
    return (check_interview_spec_claims,
            clip.check_source_contract, clip.check_tennistv_logo, clip.check_topline_format,
            clip.check_score_orientation, clip.check_opening,
            clip.check_lead_in, clip.check_trail_in, clip.check_copy_page,
            clip.check_copy_bilingual, clip.check_cover_hook, clip.check_taste,
            clip.check_taste_extra,
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
    for gate in (*_spec_gates(clip), _check_cover_scan):
        try:
            err, _ = _run_gate(gate, spec, env_errors=(ImportError, OSError))
        except PreflightUnavailable as exc:
            unknown.append(f"{gate.__name__}（{exc}）")
            continue
        if err:
            problems.append(f"{gate.__name__}：{err}")
    return problems, unknown + list(NEEDS_RENDER_ENV)


def spec_problems(spec: dict, *, copy: bool = True, date: str = "",
                  require_subs: bool = False) -> tuple[list[str], list[str]]:
    """一条 spec 的离线预检 → (红, 提示)。环境不全抛 `PreflightUnavailable`。

    `require_subs`：dispatch 口径——缺字幕缓存／缺当前指纹的 subs 判定也算红
    （带 `NEEDS_SUBS`），见 `subtitle_findings`。"""
    _require_env()
    import build_interview_clip as clip  # noqa: PLC0415

    problems: list[str] = []
    notes: list[str] = []
    slug = str(spec.get("slug") or "")
    # 封面扫描记录那一道不在 `_spec_gates` 里（那一排按 ast 钉死是 `main()` 开头那几个
    # `check_*`）；它在 runner 上是封面前置那一步的 `--check`，不要 PIL，探针也跑
    for gate in (*_spec_gates(clip), _check_cover_scan):
        err, _ = _run_gate(gate, spec)
        if err:
            problems.append(f"{gate.__name__}：{err}")
    if (note := _cover_scan_note(spec)):
        notes.append(note)
    if copy and (SPECS / f"{slug}.xhs.txt").is_file():
        if err := copy_problem(slug, date):
            problems.append(err)
    try:
        sub_bad, sub_notes = subtitle_findings(spec, require_subs=require_subs)
    except ImportError as exc:
        raise PreflightUnavailable(f"{RESEGMENT_RED}{exc}") from exc
    except Exception as exc:  # noqa: BLE001 —— 同 `_run_gate`：坏 spec 记红，不带崩调用方
        sub_bad, sub_notes = [f"{RESEGMENT_RED}{type(exc).__name__}: {exc}"], []
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
    ap.add_argument("--require-subs", action="store_true",
                    help="dispatch render 的口径：缺字幕缓存、缺当前转写指纹的 subs 判定也算红"
                         "（自动链 pick 投 render 之前就是这么判的）")
    ap.add_argument("--dispatched-by", metavar="ACTOR", default=None,
                    help="interview-clip 的 render 那一趟传 `github.triggering_actor`：以 [bot] 结尾"
                         "（自动链 pick 派发的）才开 --require-subs；个人拨的缺判定只提示，"
                         "同一个 job 里现量第二份 ASR（picker_dispatched）")
    args = ap.parse_args(argv)
    path = Path(args.spec) if args.spec else SPECS / f"{args.slug}.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    require_subs = args.require_subs
    if args.dispatched_by is not None:
        auto = picker_dispatched(args.dispatched_by)
        require_subs = require_subs or auto
        print(f"[预检] 派发者 {args.dispatched_by or '（认不出）'}："
              + ("自动链派发——缺 subs 判定算红（pick 投之前就是这么判的）" if auto else
                 "手动拨的——缺 subs 判定只提示，「转写交叉校验」那一步在判定不是 ok 时现量第二份 ASR"))
    try:
        problems, notes = spec_problems(spec, copy=not args.skip_copy, date=args.date,
                                        require_subs=require_subs)
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
