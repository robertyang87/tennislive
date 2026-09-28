#!/usr/bin/env python3
"""扫 `specs/interviews/*.json`（正式 spec）→ 挑出**能 render 而且还没 dispatch**的 slug。

这是 interview-auto-render 的最后一环：把「提升成正式 spec 的采访」转成
`interview-clip.yml` 的 dispatch 列表。每 slug 一个 run，interview-clip 的
concurrency 按 slug 分组 → 不同采访天然并行。

⚠️ **只放行生产契约完整的 spec。** render 那头有来源、字幕和内容完整性闸
（opening / transcript_verified / takeaway，见 `build_interview_clip.main`），
字段不全的 spec dispatch 出去**必死在闸上**——而 2026-08-21 之前这里不查，
`swiatek-shnaider-tor2026-qf`（一个只有骨架的 spec）就这么被 dispatch、
永久记进了「已 dispatch」状态：**死在闸上的 run 不产 render.json，于是它
既不算「已 render」、又因为记了状态永远不会再被投**，整条卡死且不吭声。
所以判定和闸**用同一张豁免表**（从 `build_interview_clip` import，
不抄第二份——写两处必分叉）；不齐的列成「等自动补齐 / 例外复核」打到 stderr，
让每一趟 run 的日志都看得见还有谁在等。

已 dispatch 过的记在 `data/interview_render_dispatched.json`：
`slugs` 是名单，`at` 记每条是什么时候投的，`spec_sha256` 记这趟实际投的
输入指纹——**投一条记一条**
（`--mark-one`，dispatch 成功之后才记），不是先记后投：先记后投的下场是
dispatch 失败的那条从此再也不会被投，而且不吭声。
`--stale` 拿 `at` 反查「投出去超过 N 分钟还没有当前输入的成片」的条目；这些
条目同时会自动释放回 dispatch 队列，下一次成功 dispatch 刷新时刻——
「投了」只是信号，render.json 落库才是产物。

⚠️ **render.json 存在不等于当前 spec 已经出片。** 同一个 slug 修字幕、封面或
空档销账后，旧逻辑只看目录里有没有 render.json，于是 workflow 绿着早退，
新 spec 永远不会重渲。现在有 QC 的新产物必须满足
`qc_attestation.spec_sha256 == 当前 spec sha256` 才算已 render；历史产物没有
QC 的仍按已 render 兼容，避免上线时把几十条存量一起重跑。

⚠️ **render 之前先要 subs 那一趟的判定**（2026-09-28）。`interview_preflight` 在
dispatch 口径（`require_subs`）下，缺字幕缓存、缺**当前转写指纹**的第二份 ASR
判定都记成红、带 `NEEDS_SUBS`——一条 spec 只卡在这一类上，就进「先投 subs」名单
（`--subs-list`），workflow 投 `mode=subs`、`--mark-subs` 记一笔；判定落库之后
下一趟再判：干净就投 render，量出分歧／空档就进等待名单等人改或认领。
来路：9/20~9/28 六趟 render 红在「空档没销账／转写分歧超阈」（alcaraz-fritz ×3、
tien-cobolli ×2、chwalinska ×1，25.4 runner-分钟），**0/6 在 dispatch 之前拦得住**，
其中四趟是这里投的——第二份 ASR 的结论只活在 runner 上。

用法：
    python tools/pick_interview_renders.py               # 打印待 dispatch 的
    python tools/pick_interview_renders.py --subs-list F # 另把「先投 subs」的写进 F
    python tools/pick_interview_renders.py --mark-one X  # X dispatch 成功后记一笔
    python tools/pick_interview_renders.py --mark-subs X # X 的 subs dispatch 成功后记一笔
    python tools/pick_interview_renders.py --stale       # 投了很久没产物的（查产物）

stdout 协议（workflow 靠它切）：第一行是给人看的题头，**第二行起每行一个
待 dispatch 的 slug**；「等自动补齐 / 例外复核」走 stderr，不混进这份名单。
「先投 subs」的**不进 stdout**（那份名单是投 render 的），只写 `--subs-list` 那个文件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# 三道编辑闸的豁免表从闸自己那儿 import（`build_interview_clip` 顶层只 import
# 标准库，system python 就能跑——interview-auto-render 的「没活就早退」靠这个，
# 别往那个模块顶层加第三方 import）。
from build_interview_clip import (  # noqa: E402
    _LEGACY_NO_OPENING,
    _NO_TAKEAWAY_LEGACY,
    check_lead_in,
)
from interview_revision import post_push_edit  # noqa: E402
from interview_source_gate import SourceContractError, validate_source_contract  # noqa: E402
from build_interview_request import AUTO_PENDING  # noqa: E402  自动章只定义一处

SPECS = ROOT / "specs" / "interviews"
STATE = ROOT / "data" / "interview_render_dispatched.json"
OUTPUT = ROOT / "output" / "interviews"
LEGACY_INPUT_BASELINE = ROOT / "data" / "interview_render_legacy_baseline.json"

# 「投出去多久还没有当前输入的成片才自动释放」。普通采访约 9 分钟，今天这条
# 28 分钟完整致辞也在一小时内完成；固定 3 小时会让一次红灯拖掉半天。60 分钟
# 给长片留足预算。
# ⚠️ 必须**大于** interview-clip.yml 的 `timeout-minutes`（65）：那条工作流是
# `cancel-in-progress`，窗口比 job 超时短的话，一趟还在跑的长片会在第 60 分钟
# 被重投的那趟掐掉——同一个形状这文件头部记过一次（45 对 49）。
STALE_MINUTES = 70

# 「先投 subs」的重投窗口和次数上限。subs 一趟（取字幕＋第二份 ASR）实测 5~8 分钟；
# 40 分钟还没交判定＝那趟死了或被同 slug 的 dispatch 掐了（concurrency 是
# cancel-in-progress），再投一次。同一份转写输入投满 `SUBS_MAX_TRIES` 趟还没判定就停下、
# 进等待名单喊人——下不动源片这类毛病，每 40 分钟重投一趟也修不好，只会刷红
# pipeline-health。**转写输入**（`build_interview_clip.SUBS_INPUT_KEYS`：url／start／end／
# en_fixed／word_fix／切行宽度／两份 ASR 的模型）一改，次数清零；改 zh／封面／文案不算——
# 那些不动转写，而每次提交 spec 都会经 on:push 叫醒这里，按整份 spec 认的话，
# 一趟还在跑的 subs 会被同 slug 的重投掐掉（cancel-in-progress）、从头再来。
SUBS_STALE_MINUTES = 40
SUBS_MAX_TRIES = 3


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_bytes(path: Path) -> bytes | None:
    """读工作区或 HEAD 里的文件，兼容 workflow 的 sparse checkout。"""
    if path.is_file():
        return path.read_bytes()
    try:
        rel = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return None
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"HEAD:{rel}"],
        capture_output=True, check=False, timeout=30,
    )
    return proc.stdout if proc.returncode == 0 else None


def _render_matches_current_spec(slug: str) -> bool:
    """有 QC 的产物必须绑定当前 spec；无 QC 的历史产物保守兼容。"""
    spec_path = SPECS / f"{slug}.json"
    if not spec_path.is_file():
        # 没有正式 spec 的旧产物不会进入 todo；这里保守视为已落地。
        return True
    qc_raw = _repo_bytes(OUTPUT / slug / "qc_attestation.json")
    if qc_raw is None:
        # 2026-08-15 之前的 58 条采访没有 QC。不能因为部署本规则就批量重渲。
        return True
    try:
        qc = json.loads(qc_raw)
    except (ValueError, UnicodeDecodeError):
        return False
    if not isinstance(qc, dict) or qc.get("status") != "pass":
        return False
    landed_sha = str(qc.get("spec_sha256") or "")
    current_sha = _sha256(spec_path)
    if landed_sha and landed_sha == current_sha:
        return True
    # 指纹规则上线前有极少数已发布产物在同一次旧工作流里“先写 QC、后补 spec
    # 运营字段”，导致两份 SHA 天生不同。部署新规则不能把这些旧消息重新推一遍。
    # 基线只豁免当时那一份明确 SHA；spec 再改一个字就立刻失效并重新渲染。
    try:
        baseline = json.loads(LEGACY_INPUT_BASELINE.read_text(encoding="utf-8"))
        row = (baseline.get("slugs") or {}).get(slug) or {}
    except (OSError, ValueError, AttributeError):
        row = {}
    return row.get("spec_sha256") == current_sha


def _current_rendered_slugs(rendered: set[str] | None = None) -> set[str]:
    rendered = _rendered_slugs() if rendered is None else rendered
    return {slug for slug in rendered if _render_matches_current_spec(slug)}


def _rendered_slugs() -> set[str]:
    """仓库里 `output/interviews/<slug>/render.json` 已存在的 slug（已 render 过）。

    用 `git ls-files` 从 index 读，**不受 sparse-checkout 影响**——workflow 的
    checkout 没拉 output/（1.36 GB），但 index 里全量文件都在。
    """
    try:
        out = subprocess.run(["git", "ls-files", "output/interviews/"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:  # noqa: BLE001 —— 拿不到就当没有，宁可多 dispatch 一次
        return set()
    return {line.split("/")[2] for line in out.splitlines()
            if line.count("/") >= 3 and "/render.json" in line}


def missing_for_render(slug: str, spec: dict) -> list[str]:
    """render 的三道编辑闸 + 推送要的文案，这条 spec 还缺哪几样。

    **判定必须和闸同一个口径**（含豁免表）：这儿判「齐了」而闸判「不齐」，
    dispatch 出去就是白烧一趟 runner 再永久卡死；反过来（这儿更严）会把
    豁免过的老 spec 拦在门外。
    """
    missing: list[str] = []
    try:
        validate_source_contract(spec)
    except SourceContractError as exc:
        missing.append(f"L0 本场场上采访身份（{exc}）")
    if not spec.get("opening") and slug not in _LEGACY_NO_OPENING:
        missing.append("opening（开场认领，check_opening 那道闸）")
    if not spec.get("zh"):
        # zh 空时 `build_interview_clip.main` 打印一份英文行就 return 0——
        # 不渲、不报错、不产 render.json，dispatch 出去就是一趟静默的空跑
        missing.append("zh（中文字幕还没填）")
    if spec.get("transcript_verified") is not True and \
            spec.get("transcript_verification") != AUTO_PENDING:
        missing.append("transcript_verified / auto_pending（转写没有核验路径）")
    if not spec.get("takeaway") and slug not in _NO_TAKEAWAY_LEGACY:
        missing.append("takeaway（收尾解读卡）")
    if not spec.get("cover"):
        missing.append("cover（封面）")
    if not (SPECS / f"{slug}.xhs.txt").is_file():
        missing.append("xhs.txt（推送文案）")
    # 独立场上采访必须配同场获胜画面和解说。复用 render 的同一条闸，不在
    # 调度器里另抄一份字段判断；否则两处迟早分叉。
    unknown = False
    try:
        check_lead_in(spec)
    except SystemExit as exc:
        missing.append(f"lead_in（{str(exc).splitlines()[0]}）")
    except (ImportError, OSError):
        # 冷开场那段的双语字幕要量宽度（PIL＋中文字体）——探针的系统 python3 上判不了：
        # 没有 PIL 是 ImportError，有 PIL 没字体（探针排在 apt 装字体之前）是 OSError。
        # 全量模式照旧抛（判不了不许当成判过了）。
        if not PROBE:
            raise
        unknown = True
    if not missing:
        pre, pre_unknown = _preflight_problems(slug, spec)
        missing += pre
        unknown = unknown or pre_unknown
    if not PROBE:
        _remember(slug, missing)
        return missing
    if missing or not unknown:
        return missing          # 不要 PIL 的闸已经判红，或者这一趟本来就判得全
    return _cached_verdict(slug)


#: `--probe`：interview-auto-render「没活就早退」那一步（runner 的系统 python3，没有 PIL）。
PROBE = False
#: 上一趟**全量**预检记下的结论（slug → {key, problems}），探针拿它顶「判不了」的那几项。
#: 存在 actions/cache 里（interview-auto-render 的「预检结论缓存」那两步），不进 git。
VERDICT_CACHE = Path(os.environ.get("INTERVIEW_PREFLIGHT_CACHE")
                     or Path.home() / ".cache" / "tennislive-preflight" / "interview_verdicts.json")
_VERDICTS: dict | None = None
_VERDICTS_DIRTY = False
_UNKNOWN: list[str] = []
_CODE_FP: str | None = None


def _git(*args: str) -> str | None:
    try:
        proc = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                              text=True, check=False, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _code_fingerprint() -> str | None:
    """预检判据的代码和豁免表：`tools/`、`src/`、仓库字体、`data/legacy_*.json` 的 git 对象号。"""
    global _CODE_FP
    if _CODE_FP is None:
        trees = _git("rev-parse", "HEAD:tools", "HEAD:src", "HEAD:assets/fonts")
        data = _git("ls-tree", "HEAD", "data/")
        if trees is None or data is None:
            return None
        legacy = [ln for ln in data.splitlines() if "\tdata/legacy_" in ln]
        _CODE_FP = hashlib.sha256((trees + "\n".join(legacy)).encode()).hexdigest()
    return _CODE_FP


def verdict_key(slug: str) -> str | None:
    """全量预检这条 spec 的全部输入的指纹：判据代码、spec、文案、字幕缓存、北京日期
    （文案标题带日期）。任何一样变了，缓存的结论就作废——**缓存只省 runner，不许
    替一个没判过的输入说话**。拿不到（没有 git）返回 None，不用缓存。"""
    if not (SPECS / f"{slug}.json").is_file():
        return None
    import interview_preflight  # noqa: PLC0415 —— 顶层只 import 标准库，探针的系统 python3 能跑

    code = _code_fingerprint()
    # ⚠️ 字幕按预检**实际读的那几份**取指纹（`caption_fingerprint` 和 `_materialize_captions`
    # 同一个分支：工作区有目录就只认工作区）。原来按 `git ls-files` 记 index——auto-render
    # 把请求的产物格加回稀疏范围、只提交 `cap_asr.json3`，全量判的是没提交的 `cap_*`，
    # 记下的键却是下一趟 HEAD 能原样复现的（review 那条）。
    caps = interview_preflight.caption_fingerprint(slug)
    if code is None or caps is None:
        return None
    xhs = SPECS / f"{slug}.xhs.txt"
    blob = json.dumps({
        "code": code,
        "date": datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
        "spec": _sha256(SPECS / f"{slug}.json"),
        "xhs": _sha256(xhs) if xhs.is_file() else "",
        "captions": caps,
    }, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def _verdicts() -> dict:
    global _VERDICTS
    if _VERDICTS is None:
        try:
            data = json.loads(VERDICT_CACHE.read_text(encoding="utf-8"))
            _VERDICTS = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            _VERDICTS = {}
    return _VERDICTS


def save_verdicts() -> None:
    """全量那一趟跑完把结论落盘（actions/cache 带给下一趟的探针）。写不了只告警。"""
    if not _VERDICTS_DIRTY:
        return
    try:
        VERDICT_CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = VERDICT_CACHE.with_suffix(".tmp")
        # sort_keys：同样的结论写出同样的字节——工作流按文件指纹判「有变才另存一份缓存」
        tmp.write_text(json.dumps(_verdicts(), ensure_ascii=False, indent=1, sort_keys=True),
                       encoding="utf-8")
        tmp.replace(VERDICT_CACHE)
    except OSError as exc:
        print(f"[预检缓存] 写不了 {VERDICT_CACHE}（{exc}）——下一趟探针判不了的会照常走全量",
              file=sys.stderr)


def _remember(slug: str, missing: list[str]) -> None:
    """全量那一趟判完一条：把「还缺什么」按 `verdict_key` 记下来（空列表＝判过、全绿）。

    ⚠️ 有一项是**工具崩了**（`interview_preflight.CRASHED`，不是判据判的红）就不记，
    连旧的一起删掉：偶发的崩溃记进去，探针会拿它当「同一份输入判过是红的」一直重放到
    北京日期翻过去；不记，下一趟探针判不了、交给全量重判。"""
    global _VERDICTS_DIRTY
    from interview_preflight import CRASHED  # noqa: PLC0415
    if any(CRASHED in m for m in missing):
        if _verdicts().pop(slug, None) is not None:
            _VERDICTS_DIRTY = True
        return
    if (key := verdict_key(slug)) is not None:
        _verdicts()[slug] = {"key": key, "missing": list(missing)}
        _VERDICTS_DIRTY = True


def _cached_verdict(slug: str) -> list[str]:
    """探针判不全的一条：同一份输入全量判过就用那一份，没有就当「要全量那一趟来判」。"""
    key = verdict_key(slug)
    row = _verdicts().get(slug) or {}
    if key is not None and isinstance(row, dict) and row.get("key") == key \
            and isinstance(row.get("missing"), list):
        return [f"{m}（上一趟全量预检判的，输入没变）" for m in row["missing"]]
    _UNKNOWN.append(slug)
    return []


def _preflight_problems(slug: str, spec: dict) -> tuple[list[str], bool]:
    """dispatch 之前把 runner 上必红的「只看 spec 就判得出」的错拦下来 → (红, 判不全)。

    来路：2026-09-06 之后 interview-clip 有 12 趟红在中文字幕（超宽／吊「的」／
    117:114 行数对不上）、9 趟红在 tag／标题——全是 spec 本身的错，却都要等 runner
    装完依赖、取完字幕才报；自动链投出去的那条红了还会占住 70 分钟的「已投」窗口。
    判据全在 `interview_preflight.spec_problems`（和出片那一趟同一份函数），这里只取
    每条红的第一行。

    ⚠️ **全量模式**（dispatch 那一步）环境不全时抛 `PreflightUnavailable`，**不在这儿吞**
    ——吞掉就成了「判不了」当「判过了」。判完由 `missing_for_render` 按 `verdict_key`
    记下来。

    ⚠️ **探针模式**（`--probe`，系统 python3 没有 PIL）：不要 PIL 的那几道照跑
    （`probe_problems`），红了就是红；量宽度那几项判不了——由 `missing_for_render`
    拿上一趟全量预检**同一份输入**记下的结论顶上，没有就当「要全量那一趟来判」
    放进待投名单（探针只拿它数数，不 dispatch）。原来这里一律抛，于是一条卡在
    量宽度上的红 spec 每 10 分钟逼一次全量 job（review 量的）。
    """
    from interview_preflight import (  # noqa: PLC0415
        PreflightUnavailable,
        probe_problems,
        spec_problems,
    )
    try:
        problems, _notes = spec_problems(spec, require_subs=True)
        return [f"预检：{p.splitlines()[0]}" for p in problems], False
    except PreflightUnavailable:
        if not PROBE:
            raise
    red, _unknown = probe_problems(spec)
    return [f"预检：{p.splitlines()[0]}" for p in red], True


def _load_state() -> dict:
    if not STATE.is_file():
        return {"slugs": [], "at": {}, "spec_sha256": {}}
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"slugs": [], "at": {}, "spec_sha256": {}}
    data.setdefault("slugs", [])
    data.setdefault("at", {})
    data.setdefault("spec_sha256", {})
    if not isinstance(data["spec_sha256"], dict):
        data["spec_sha256"] = {}
    if not isinstance(data.get("subs", {}), dict):
        data["subs"] = {}
    return data


def _utc(raw: object) -> datetime | None:
    try:
        return datetime.strptime(str(raw), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def needs_subs_only(missing: list[str]) -> bool:
    """这条 spec 是不是**只**卡在「当前指纹还缺 subs 的判定」上（别的红一条都没有）。

    混着别的红（字幕超宽、en_fixed 挂错行……）就不投 subs：人改完那一处，转写指纹
    多半跟着变，这一趟 subs 量的就是旧的那一版。"""
    from interview_preflight import NEEDS_SUBS  # noqa: PLC0415 —— 顶层只 import 标准库
    return bool(missing) and all(NEEDS_SUBS in m for m in missing)


def _subs_inputs(slug: str) -> str:
    """这条 spec 的**转写输入**指纹（`build_interview_clip.transcript_inputs_sha`）；读不了是空串。"""
    from build_interview_clip import transcript_inputs_sha  # noqa: PLC0415 —— 顶层只 import 标准库

    try:
        spec = json.loads((SPECS / f"{slug}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return ""
    return transcript_inputs_sha(spec) if isinstance(spec, dict) else ""


def subs_dispatch_block(slug: str, *, now: datetime,
                        state: dict | None = None) -> str | None:
    """这条该投 subs 时，有什么理由**先不投** → 理由（None＝投）。

    认领按**转写输入**的指纹（`_subs_inputs`），不按整份 spec：转写输入一改（新的转写要
    重新量），上一趟 subs 的认领就不算数；只改了 zh／封面／文案，认领照旧——不然每次
    提交 spec 都把还在跑的那趟 subs 掐掉重来（同 slug 的 concurrency 是 cancel-in-progress）。"""
    rec = ((state or _load_state()).get("subs") or {}).get(slug) or {}
    inputs = _subs_inputs(slug)
    if not isinstance(rec, dict) or not inputs or rec.get("inputs_sha256") != inputs:
        return None
    at = _utc(rec.get("at"))
    if at is not None and now - at < timedelta(minutes=SUBS_STALE_MINUTES):
        return f"已投 subs（{rec.get('at')}），等它交判定"
    tries = int(rec.get("tries") or 0)
    if tries >= SUBS_MAX_TRIES:
        return (f"同一份转写输入已投 {tries} 趟 subs，预检还是认不出当前指纹的判定。两种可能："
                f"① 那几趟没交判定——去看「interview-clip · subs · {slug}」的日志"
                "（下不动源片／字幕多半是这个）；② 交了，但判定绑的指纹和预检按仓库里的字幕缓存"
                f"重切出来的对不上——比一下 output/interviews/{slug}/second_asr_verdict.json 的 "
                "`sha256`／`window` 和本地 `python tools/interview_preflight.py --slug "
                f"{slug} --require-subs` 报的。修好之后手动 dispatch 一次 mode=subs")
    return None


def mark_subs(slug: str, *, now: str = "") -> None:
    """X 的 `mode=subs` dispatch **成功之后**记一笔（先投后记，和 `mark_one` 同一个顺序）。"""
    state = _load_state()
    inputs = _subs_inputs(slug)
    rec = (state.setdefault("subs", {}).get(slug) or {})
    tries = int(rec.get("tries") or 0) + 1 if rec.get("inputs_sha256") == inputs else 1
    state["subs"][slug] = {"at": now or datetime.now(timezone.utc).strftime("%FT%TZ"),
                           "inputs_sha256": inputs, "tries": tries}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                     encoding="utf-8")


def _fresh_dispatches(*, now: datetime, rendered: set[str],
                      changed_inputs: set[str] | None = None) -> set[str]:
    """同一份输入已 dispatch 且仍在合理窗口内的 slug。"""
    state = _load_state()
    changed_inputs = changed_inputs or set()
    fresh: set[str] = set()
    for slug in state.get("slugs", []):
        if slug in rendered:
            continue
        spec_path = SPECS / f"{slug}.json"
        current_sha = _sha256(spec_path) if spec_path.is_file() else ""
        dispatched_sha = str(state.get("spec_sha256", {}).get(slug) or "")
        if dispatched_sha and current_sha and dispatched_sha != current_sha:
            # 这条状态认领的是旧 spec，新输入不该被它再拦一个小时。
            continue
        if slug in changed_inputs and current_sha and not dispatched_sha:
            # 迁移前的状态没有输入指纹；QC 已明确证明产物绑定的是旧 spec，
            # 所以让证据胜过那个无指纹的“投过了”信号，立即恢复。
            continue
        raw = state.get("at", {}).get(slug, "")
        try:
            at = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if now - at < timedelta(minutes=STALE_MINUTES):
            fresh.add(slug)
    return fresh


def todo_slugs(*, now: datetime | None = None) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """→ (该 dispatch render 的, [(还差自动补齐/复核的 slug, 缺什么)])。「先投 subs」的见 `todo_plan`。"""
    ready, waiting, _subs = todo_plan(now=now)
    return ready, waiting


def todo_plan(*, now: datetime | None = None
              ) -> tuple[list[str], list[tuple[str, list[str]]], list[str]]:
    """→ (该 dispatch render 的, [(还差自动补齐/复核的 slug, 缺什么)], 该先 dispatch subs 的)。

    三份都不含「已 render」和「最近刚 dispatch」的。dispatch 超过 STALE_MINUTES 仍无
    render.json 的自动释放回 ready；再次 mark 会刷新时刻，实现环境抖动自愈。
    **只**卡在「当前指纹缺 subs 判定」上的进第三份（`needs_subs_only`），刚投过 subs、
    还在窗口里的进等待名单说一声（`subs_dispatch_block`）。
    """
    now = now or datetime.now(timezone.utc)
    state = _load_state()
    rendered = _rendered_slugs()
    current_rendered = _current_rendered_slugs(rendered)
    changed_inputs = rendered - current_rendered
    blocked = current_rendered | _fresh_dispatches(
        now=now, rendered=current_rendered,
        changed_inputs=changed_inputs)
    ready: list[str] = []
    waiting: list[tuple[str, list[str]]] = []
    subs: list[str] = []
    for p in sorted(SPECS.glob("*.json")):
        if p.name.endswith(".draft.json") or p.stem in blocked:
            continue
        try:
            spec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            waiting.append((p.stem, ["spec 读不了（JSON 坏了）"]))
            continue
        pushed_raw = _repo_bytes(OUTPUT / p.stem / "pushed.json")
        if pushed_raw:
            try:
                pushed = json.loads(pushed_raw)
            except (ValueError, UnicodeDecodeError):
                waiting.append((p.stem, ["已发布记录无法核对，拒绝自动重渲"]))
                continue
            revision = spec.get("_publication_revision") or {}
            if not (revision.get("id") and revision.get("base_film_sha256")
                    and revision.get("base_film_sha256") == pushed.get("film_sha256")):
                # A stale generator changing spec bytes is not a new user request.
                if revision:
                    continue
                # 没写修订标记：推送之后改了会进成片的字段、而且还在自动修订窗口里，
                # 就当成一次修订（09-22「重渲之后默认就是重推」）；窗口外的说一声，
                # 只改注解的照旧安静跳过。判据和来路见 interview_revision。
                qc_raw = _repo_bytes(OUTPUT / p.stem / "qc_attestation.json")
                try:
                    qc = json.loads(qc_raw) if qc_raw else None
                except (ValueError, UnicodeDecodeError):
                    qc = None
                revise, why = post_push_edit(
                    spec, pushed, qc if isinstance(qc, dict) else None, now)
                if not revise:
                    if why:
                        waiting.append((p.stem, [why]))
                    continue
        missing = missing_for_render(p.stem, spec)
        if missing and needs_subs_only(missing):
            if why := subs_dispatch_block(p.stem, now=now, state=state):
                waiting.append((p.stem, [why]))
            else:
                subs.append(p.stem)
        elif missing:
            waiting.append((p.stem, missing))
        else:
            ready.append(p.stem)
    return ready, waiting, subs


def mark_one(slug: str, *, now: str = "") -> None:
    """X dispatch **成功之后**记一笔。先投后记，顺序不许反：
    先记后投的话，dispatch 失败的那条从此再也不会被投，而且不吭声。"""
    state = _load_state()
    if slug not in state["slugs"]:
        state["slugs"] = sorted({*state["slugs"], slug})
    state["at"][slug] = now or datetime.now(timezone.utc).strftime("%FT%TZ")
    spec_path = SPECS / f"{slug}.json"
    if spec_path.is_file():
        state["spec_sha256"][slug] = _sha256(spec_path)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                     encoding="utf-8")


def stale_dispatches(*, now: datetime | None = None) -> list[tuple[str, str]]:
    """投出去超过 `STALE_MINUTES` 还没有当前成片的 → [(slug, 投出时刻)]。

    「投了」只是信号，render.json 才是产物——run 可以死在编辑闸上、被
    concurrency 顶掉、或者干脆没跑起来，而这些在状态文件上长得和「正在渲」
    一模一样。⚠️ 老状态里没有 `at` 的条目（bulk --mark 时代记的）查不了
    时刻，一律算 stale——它们至少投出去一整天了。
    """
    state = _load_state()
    rendered = _current_rendered_slugs()
    now = now or datetime.now(timezone.utc)
    out: list[tuple[str, str]] = []
    for slug in state.get("slugs", []):
        if slug in rendered:
            continue
        at_raw = state.get("at", {}).get(slug, "")
        if at_raw:
            try:
                at = datetime.strptime(at_raw, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc)
            except ValueError:
                at = None
            if at is not None and now - at < timedelta(minutes=STALE_MINUTES):
                continue
        out.append((slug, at_raw or "时刻没记（老状态）"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mark-one", default="",
                    help="这条 slug dispatch 成功了，记进状态（投一条记一条）")
    ap.add_argument("--at", default="",
                    help="配合 --mark-one：写入这次 dispatch 的 UTC 时刻")
    ap.add_argument("--stale", action="store_true",
                    help="列出投了超过 %d 分钟还没有当前成片的" % STALE_MINUTES)
    ap.add_argument("--probe", action="store_true",
                    help="「没活就早退」的探针：缺 PIL 时量宽度那几项拿上一趟全量预检的结论顶，"
                         "没有就算待投（只数数，不 dispatch）")
    ap.add_argument("--subs-list", default="",
                    help="把「当前指纹还缺 subs 判定、先投 mode=subs」的 slug 写进这个文件"
                         "（每行一个；没有也写一个空文件）")
    ap.add_argument("--mark-subs", default="",
                    help="这条 slug 的 mode=subs dispatch 成功了，记进状态")
    args = ap.parse_args()
    global PROBE
    PROBE = bool(args.probe)

    if args.mark_one:
        mark_one(args.mark_one, now=args.at)
        print(f"已记：{args.mark_one}")
        return 0
    if args.mark_subs:
        mark_subs(args.mark_subs, now=args.at)
        print(f"已记 subs：{args.mark_subs}")
        return 0

    if args.stale:
        stale = stale_dispatches()
        print(f"投出去超过 {STALE_MINUTES} 分钟还没有当前成片的：{len(stale)} 条")
        for slug, at in stale:
            print(f"  {slug}（投于 {at}）——去查那趟 interview-clip run 的日志，"
                  "或人工重新 dispatch")
        return 0

    ready, waiting, subs = todo_plan()
    if not PROBE:
        save_verdicts()
    if args.subs_list:
        Path(args.subs_list).write_text("".join(f"{s}\n" for s in subs), encoding="utf-8")
    unknown = [s for s in ready if s in _UNKNOWN]
    print(f"待 dispatch {len(ready)} 条：" + (
        f"（其中 {len(unknown)} 条量宽度那几项这里判不了、也没有同一份输入的全量结论，"
        f"交给全量那一趟判：{'、'.join(unknown)}）" if unknown else "") + (
        f"［另有 {len(subs)} 条当前转写指纹还缺 subs 的判定，先投 mode=subs："
        f"{'、'.join(subs)}］" if subs else ""))
    for s in ready:
        print(s)
    # 等自动补齐/例外复核的走 stderr：stdout 第二行起是给 workflow 切的名单，混进去就会把
    # 一条不齐的 spec dispatch 出去——正是这次要修的那个卡死
    if waiting:
        print(f"[等自动补齐 / 例外复核] {len(waiting)} 条（不 dispatch）：", file=sys.stderr)
        for slug, missing in waiting:
            print(f"  {slug}：缺 {'、'.join(missing)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
