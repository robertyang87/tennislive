#!/usr/bin/env python3
"""开工前口味清单 ＋ main 上已有的口味闸：发 render 之前跑这一条。

账号所有者 2026-09-27：「你要总结我的口味和品味这种个性化的要求，形成一个通用的规则
在做视频前就烂掉，而不是说做了一半又返工」（原话如此，「烂掉」指拦掉）。

规则全文和清单在 `.claude/skills/tennis-owner-taste/SKILL.md`——**清单的问题只有
那一份**。这里按行首编号（A1、B2……）把它读进来，在每个问题底下贴上这条 spec 的
实际字段（钩子两行、副标题、封面主体和赢家、封面图用没用过……），然后跑 main 上
已经存在的口味闸：

- 赛场之上／网球有故事：``build_match_reel.py render --dry-run`` 那一趟
  （``validate_spec`` ＋ 措辞闸 ＋ probe 判据 ＋ 文案闸，秒级），再加一批**只活在
  pytest 里**的口味判据（``TASTE_CI_TESTS``）——它们扫全库，红了按 slug 认领：
  红在这一条上才算这一条的；
- 赛后开麦：``build_interview_clip`` 里只读 spec 的那几道闸 ＋
  ``spec_wording.check_interview_copy_wording``。

退出码：0 ＝ main 上的闸对这一条都绿；1 ＝ 有闸红在这一条上；2 ＝ 找不到 spec。
**清单本身不影响退出码**：那是自查题，没有机械判据——硬凑一个判据比没有更糟
（CLAUDE.md「判断题写不成测试」）。清单里的「字段里出现了……」只是把事实摆出来，
不是判定。

**推断出来的规则只当提醒**（账号所有者 2026-09-27 选定）：SKILL 里标着
〔推断·只自查，永不做成闸〕的规则没有他的原话，只是从他的挑选里推出来、或者会话转述的。
这里把它们单列成「提醒」、在清单对应编号后面挂上标记，**永远不进退出码**；
`test_推断出来的口味规则永不做成闸` 钉住它们也不出现在任何一张闸的名单里。

用法：

    python3 tools/taste_preflight.py --slug wong-vallejo-hangzhou-2026-r2
    python3 tools/taste_preflight.py --line 赛场之上          # spec 还没写：空白清单
    python3 tools/taste_preflight.py --slug X --no-ci-tests  # 只跑 dry-run，秒级
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
import taste_gates as _taste_gates  # noqa: E402

SKILL = ROOT / ".claude" / "skills" / "tennis-owner-taste" / "SKILL.md"
REELS = ROOT / "specs" / "reels"
INTERVIEWS = ROOT / "specs" / "interviews"

LINES = ("赛场之上", "网球有故事", "赛后开麦")

#: 清单行的格式（SKILL.md「开工前清单」）：
#: ``- [ ] **B1** 〔赛场之上〕问题？　❌ 被否的　✅ 被选的``
#: ⚠️ 改 SKILL 里的格式就要同时改这里——`test_清单只有一份` 会红。
_ITEM = re.compile(
    r"^- \[ \] \*\*(?P<id>[A-D]\d{1,2})\*\* 〔(?P<lines>[^〕]+)〕(?P<q>.+?)"
    r"　❌\s*(?P<bad>.+?)　✅\s*(?P<good>.+)$")

#: 钩子里要解释才懂的词（账号所有者 2026-09-22「最后一局破发到 0 是啥意思」、
#: 09-25「读不懂」、**09-27 定的 O6：钩子里「破发」「抢七」也不用**）和全场总得分差
#: （09-13「不要写总分差距了」、09-19「其实网球差距就在一两分的关键分」）。
#: ⚠️ **词表只有一份，在 `tools/taste_gates.py`**（闸用的就是它）：这里原来自己抄了
#: 一份，`ACE` 的边界写法和「至少/最多」那一刀当场就和闸分了叉——摆出来的事实和
#: `--dry-run` 红的理由对不上。这里只拿来把字段里的事实摆出来，不是闸。
HOOK_TERMS = _taste_gates.hook_terms_regex()
#: 全场总得分差（账号所有者 2026-09-13「不要写总分差距了」、09-19「其实网球差距
#: 就在一两分的关键分」）。**单一出处在 `taste_gates_extra.TOTAL_MARGIN`**——那是
#: `--dry-run` 真拦的那一份，`taste_gates.TOTAL_POINTS` 也就是它（同一个对象）；
#: 这里摆事实用同一份，清单上摆出来的就是闸会红的。
#: 原来两边各写一份，一个把「全场多次破发」摆成总分说法、另一个漏了「总分落后18分」。
TOTAL_MARGIN = _taste_gates.TOTAL_POINTS

#: 推断出来的规则：SKILL 规则正文末尾写 ``〔推断·只自查，永不做成闸〕`<规则编号>```，
#: 连着的 ``〔自查 C4〕`` 是它挂在清单上的编号。头部和图例里提到这个标记时后面不跟
#: 反引号编号，不会被认成一条规则。
INFERRED_TAG = "推断·只自查，永不做成闸"
_INFERRED = re.compile(
    r"〔推断·只自查，永不做成闸〕`(?P<id>[a-z0-9-]+)`"
    r"(?:〔自查 (?P<items>[A-D]\d{1,2}(?:[ 、][A-D]\d{1,2})*)〕)?")
_RULE_TITLE = re.compile(r"^- \*\*(?P<title>.+?)\*\*")

#: 只活在 pytest 里的口味判据：`--dry-run` 看不见它们，会话手写的 spec 要等 CI
#: 才红——正是「做了一半又返工」的来源之一。节点名写死，
#: `test_口味CI判据的名单都真的存在` 钉住它们不会悄悄改名失效。
TASTE_CI_TESTS: tuple[tuple[str, str], ...] = (
    ("tests/test_match_reel.py::test_小红书正文不许用markdown", "小红书正文纯文本"),
    ("tests/test_match_reel.py::test_旁白不许用指示语指画面", "旁白不用指示语"),
    ("tests/test_match_reel.py::test_旁白不许把每一局都念一遍", "不逐局念"),
    ("tests/test_match_reel.py::test_钩子和文案里写的排名要和matchup对得上", "钩子排名＝matchup"),
    ("tests/test_match_reel.py::test_赛场之上要留一段精彩的原声解说_不留要写明为什么", "精彩原声"),
    ("tests/test_match_reel.py::test_原声解说的字幕一律中英双语", "原声双语"),
    ("tests/test_match_reel.py::test_收尾要落在一问上不能停在数据上", "收尾一问"),
    ("tests/test_match_reel.py::test_旁白里的分不许读成分钟", "「分」不读成分钟"),
    ("tests/test_match_reel.py::test_赛场之上的quote段不许是赛后采访", "不收采访"),
    ("tests/test_match_reel.py::test_用TennisTV的源片要说清片尾和台标怎么剪掉", "片尾台标"),
    ("tests/test_match_reel.py::test_赛场之上的封面一律用solo", "solo 封面"),
    ("tests/test_reel_editorial.py::test_开场旁白不许复读封面钩子", "落点不复读钩子"),
    ("tests/test_reel_editorial.py::test_钩子不许复述赛果条和顶栏印着的东西", "钩子不复述赛果条"),
    ("tests/test_reel_editorial.py::test_推送标题不许只有名字加赛果", "推送标题有内容"),
    ("tests/test_reel_editorial.py::test_赛场之上要么有狠数据要么说清为什么没有", "狠数据认领"),
    ("tests/test_reel_editorial.py::test_赛场之上要么带数据统计图要么说清为什么不带", "统计图"),
    ("tests/test_reel_editorial.py::test_数据图缺制胜分和UE的要说清TNNS那趟跑出来是什么", "制胜分和 UE"),
)


# ————————————————————————— 清单 —————————————————————————


@dataclass
class Item:
    id: str
    lines: frozenset[str]
    question: str
    bad: str
    good: str

    def applies(self, line: str | None) -> bool:
        return line is None or "全部" in self.lines or line in self.lines


def parse_checklist(text: str) -> list[Item]:
    items = []
    for raw in text.split("\n"):
        m = _ITEM.match(raw.strip())
        if m:
            items.append(Item(m["id"], frozenset(m["lines"].split("·")),
                              m["q"].strip(), m["bad"].strip(), m["good"].strip()))
    return items


@dataclass(frozen=True)
class Inferred:
    """一条推断出来的规则：只提醒，永不做成闸。"""
    id: str
    title: str
    items: tuple[str, ...]


def parse_inferred(text: str) -> list[Inferred]:
    out, title = [], ""
    for raw in text.split("\n"):
        m = _RULE_TITLE.match(raw)
        if m:
            title = m["title"]
        hit = _INFERRED.search(raw)
        if hit and title:
            out.append(Inferred(hit["id"], title,
                                tuple(re.findall(r"[A-D]\d{1,2}", hit["items"] or ""))))
    return out


def load_inferred(path: Path = SKILL) -> list[Inferred]:
    return parse_inferred(path.read_text(encoding="utf-8")) if path.is_file() else []


def load_checklist(path: Path = SKILL) -> list[Item]:
    if not path.is_file():
        raise SystemExit(f"找不到口味规则 {path}——清单只有那一份，不在这里另抄")
    items = parse_checklist(path.read_text(encoding="utf-8"))
    if not items:
        raise SystemExit(f"{path} 里一条清单都没读出来——格式变了？见 `_ITEM`")
    return items


# ————————————————————————— spec 与字段 —————————————————————————


@dataclass
class Ctx:
    slug: str
    path: Path | None
    kind: str                       # reel / interview / none
    line: str | None
    spec: dict = field(default_factory=dict)
    xhs: str = ""


def find_spec(slug: str) -> tuple[str, Path] | None:
    for kind, base in (("reel", REELS), ("interview", INTERVIEWS)):
        path = base / f"{slug}.json"
        if path.is_file():
            return kind, path
    production = ROOT / "specs" / "explainers" / f"{slug}.production.json"
    if production.is_file():
        return "explainer", production
    return None


def line_of(kind: str, spec: dict) -> str | None:
    if kind == "explainer":
        return str(spec.get("column") or "")
    if kind == "interview":
        return "赛后开麦"
    eyebrow = (spec.get("cover") or {}).get("eyebrow") or spec.get("_column")
    return str(eyebrow) if eyebrow else None


def _hook_lines(spec: dict) -> list[str]:
    cover = spec.get("cover") or {}
    hook = cover.get("hook") if cover.get("hook") is not None else cover.get("title")
    if isinstance(hook, list):
        return [str(x) for x in hook]
    return [x for x in str(hook or "").split("\n") if x] if hook else []


def _terms(text: str, pattern: re.Pattern) -> list[str]:
    return sorted({m.group(0) for m in pattern.finditer(text or "")})


def _xhs_first_line(xhs: str) -> str:
    return next((ln.strip() for ln in (xhs or "").split("\n") if ln.strip()), "")


def _reused_by(ctx: Ctx) -> list[str]:
    """同一个封面图路径还挂在哪些别的 spec 上（B7：同一张照片不给第二条片子）。

    ⚠️ 这只是**摆事实**，而且故意比闸宽：闸是 `reel_asset_gates.cover_reuse_problem`
    （dry-run 里跑，只认**已经发出去**的、按路径或内容哈希），这里连没发的也列——
    选图那一刻就该知道别人手上也挂着这张，不必等 dry-run。"""
    image = str(((ctx.spec.get("cover") or {}).get("portrait") or {}).get("image") or "")
    if not image or image.upper().startswith("PENDING"):
        return []
    index = _portrait_index(str(REELS), str(INTERVIEWS))
    return [slug for slug in index.get(image, ()) if slug != ctx.slug]


@functools.lru_cache(maxsize=4)
def _portrait_index(*dirs: str) -> dict[str, tuple[str, ...]]:
    """封面图路径 → 挂着它的 slug。全库只读一遍（按目录缓存，测试换目录就换一份）。"""
    index: dict[str, list[str]] = {}
    for base in map(Path, dirs):
        for path in sorted(base.glob("*.json")):
            try:
                spec = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            portrait = ((spec.get("cover") or {}) if isinstance(spec, dict) else {}).get(
                "portrait") or {}
            image = str(portrait.get("image") or "") if isinstance(portrait, dict) else ""
            if image:
                index.setdefault(image, []).append(path.stem)
    return {k: tuple(v) for k, v in index.items()}


def _longest_silent_run(spec: dict) -> tuple[float, str]:
    """同一条源片连续不配旁白的最长一段（B18：别整条搬运官方集锦）。"""
    best, where, run, run_src, run_start = 0.0, "", 0.0, None, None
    for seg in spec.get("segments") or []:
        if not isinstance(seg, dict) or seg.get("image") or "start" not in seg:
            run, run_src = 0.0, None
            continue
        src = seg.get("source")
        try:
            length = float(seg["end"]) - float(seg["start"])
        except (KeyError, TypeError, ValueError):
            continue
        if str(seg.get("narration") or "").strip():
            run, run_src = 0.0, None
            continue
        if src == run_src and run:
            run += length
        else:
            run, run_src, run_start = length, src, seg.get("start")
        if run > best:
            best, where = run, f"源 {src or '主源'} 自 {run_start}s 起"
    return best, where


def _fmt(value, limit: int = 160) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = text.replace("\n", " ⏎ ")
    return text if len(text) <= limit else text[:limit] + "…"


def _get(d: dict, dotted: str):
    cur = d
    for key in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _show(ctx: Ctx, *paths: str) -> list[str]:
    out = []
    for p in paths:
        value = _get(ctx.spec, p)
        if value not in (None, "", [], {}):
            out.append(f"`{p}`：{_fmt(value)}")
    return out


def _f_hook(ctx: Ctx) -> list[str]:
    lines = _hook_lines(ctx.spec)
    if not lines:
        return ["（钩子还没写）"]
    return [f"钩子第 {i} 行：「{ln}」" for i, ln in enumerate(lines, 1)]


def _f_hook_terms(ctx: Ctx) -> list[str]:
    out = _f_hook(ctx)
    hits = _terms("\n".join(_hook_lines(ctx.spec)), HOOK_TERMS)
    out.append(f"字段里出现了清单上的词：{'、'.join(hits)}" if hits
               else "钩子里没有清单上的词")
    return out


def _f_total_margin(ctx: Ctx) -> list[str]:
    summary = str(_get(ctx.spec, "push.summary") or "")
    out = _f_hook(ctx) + ([f"推送标题：「{summary}」"] if summary else [])
    hits = _terms("\n".join(_hook_lines(ctx.spec)) + "\n" + summary, TOTAL_MARGIN)
    out.append(f"字段里出现了总分说法：{'、'.join(hits)}" if hits
               else "钩子和推送标题里没有总分说法")
    return out


def _f_subject(ctx: Ctx) -> list[str]:
    cover = ctx.spec.get("cover") or {}
    subject, winner = cover.get("subject"), cover.get("winner") or _get(
        ctx.spec, "_match.winner")
    out = []
    if subject or winner:
        who = "赢家" if subject and subject == winner else "不是赢家"
        out.append(f"封面主体：{subject or '（没写）'}；赢家：{winner or '（没写）'}"
                   + (f"（主体{who}）" if subject and winner else ""))
    for m in cover.get("matchup") or []:
        if isinstance(m, dict):
            out.append(f"对阵：{m.get('name')} {m.get('country', '')} 世界第 {m.get('rank', '?')}")
    return out + _show(ctx, "cover._subject_why")


def _f_portrait(ctx: Ctx) -> list[str]:
    out = _show(ctx, "cover.portrait.image", "cover.portrait.frame_at", "cover.frame_at",
                "cover.portrait._portrait_why", "cover.portrait._frame_why",
                "cover.portrait._low_res_why", "cover._why")
    reused = _reused_by(ctx)
    if reused:
        out.append(f"同一个封面图路径也挂在：{'、'.join(reused)}")
    return out or ["（封面图还没定）"]


def _f_frame(ctx: Ctx) -> list[str]:
    return _show(ctx, "cover.layout", "cover.portrait.fit", "cover.portrait.zoom",
                 "cover.portrait.focus", "cover.portrait.focus_y", "cover.topic") or [
        "（版式字段还没写）"]


def _f_segments(ctx: Ctx) -> list[str]:
    segs = [s for s in ctx.spec.get("segments") or [] if isinstance(s, dict)]
    if not segs:
        return ["（segments 还没写）"]
    narrated = [s for s in segs if str(s.get("narration") or "").strip()]
    first = segs[0]
    out = [f"{len(segs)} 段，其中 {len(narrated)} 段配旁白"]
    out.append("第 1 段：" + (f"旁白「{_fmt(first.get('narration'), 60)}」"
                              if str(first.get("narration") or "").strip()
                              else "不配旁白" + ("、带原声字幕" if first.get("quote") else "")))
    return out


def _f_backstory(ctx: Ctx) -> list[str]:
    narr = [str(s.get("narration")) for s in ctx.spec.get("segments") or []
            if isinstance(s, dict) and str(s.get("narration") or "").strip()]
    out = [f"旁白第 {i} 段：「{_fmt(t, 70)}」" for i, t in enumerate(narr[:3], 1)]
    return (out + _show(ctx, "push.lead")) or ["（旁白和 `push.lead` 都还没写）"]


def _f_ending(ctx: Ctx) -> list[str]:
    narr = [str(s.get("narration")) for s in ctx.spec.get("segments") or []
            if isinstance(s, dict) and str(s.get("narration") or "").strip()]
    out = [f"最后几段旁白：「{_fmt(t, 70)}」" for t in narr[-2:]]
    return out + _show(ctx, "takeaway.close")


def _f_result(ctx: Ctx) -> list[str]:
    return _show(ctx, "_match.status", "_match.winner", "_match.winner_result",
                 "_match.source", "match.winner", "match.loser", "match.round",
                 "push.score") or ["（`_match`／`match` 还没写）"]


def _f_matchday(ctx: Ctx) -> list[str]:
    return _show(ctx, "topbar.line1", "event", "_match.flashscore_id", "_match._match_day_why",
                 "_production.received_at") + [
        "比赛日在 flashscore `f_2_0`（今天）／`f_2_-1`（上一个）里核，推送前再核一次"]


def _f_heat(ctx: Ctx) -> list[str]:
    out = []
    for m in (ctx.spec.get("cover") or {}).get("matchup") or []:
        if isinstance(m, dict):
            out.append(f"{m.get('name')}：{m.get('country', '?')}，世界第 {m.get('rank', '?')}")
    return out + _show(ctx, "cover._heat_why")


def _f_topic(ctx: Ctx) -> list[str]:
    return _show(ctx, "slug", "cover.topic", "cover.question") + _f_hook(ctx)


def _f_silent(ctx: Ctx) -> list[str]:
    secs, where = _longest_silent_run(ctx.spec)
    return [f"同一条源片连续不配旁白最长 {secs:.1f} 秒" + (f"（{where}）" if where else "")]


def _f_owner(ctx: Ctx) -> list[str]:
    return _show(ctx, "cover._owner_words", "cover._hook_why") or [
        "（没有 `cover._owner_words`——他这条没给过原话就不用管）"]


def _f_facts(ctx: Ctx) -> list[str]:
    out = []
    for key in ("_facts", "_claims", "_hit_data"):
        value = ctx.spec.get(key)
        if isinstance(value, (list, dict)) and value:
            out.append(f"`{key}` 记了 {len(value)} 条")
    return out or ["（`_facts`／`_claims`／`_hit_data` 都是空的——查过什么要写进去）"]


def _f_story(ctx: Ctx) -> list[str]:
    return _f_segments(ctx) + _show(ctx, "_editing_why")


def _f_visual(ctx: Ctx) -> list[str]:
    topic = str(_get(ctx.spec, "cover.topic") or "")
    return _show(ctx, "cover.layout", "cover.scrim") + (
        [f"副标题 {len(topic)} 字：「{topic}」"] if topic else [])


def _nothing(_ctx: Ctx) -> list[str]:
    return []


#: 每个清单编号贴哪些字段。**编号只有一份在 SKILL.md**；这张表缺一个、多一个，
#: `test_清单只有一份_每条都有字段` 都会红。流程题（C、D）没有字段可贴。
FIELDS: dict[str, Callable[[Ctx], list[str]]] = {
    "A1": _f_matchday, "A2": _f_heat, "A3": _f_topic, "A4": _f_topic,
    "A5": _f_portrait, "A6": _f_facts,
    "B1": _f_hook, "B2": _f_hook_terms, "B3": _f_hook, "B4": _f_total_margin,
    "B5": _f_owner, "B6": _f_subject, "B7": _f_portrait, "B8": _f_portrait,
    "B9": _f_frame, "B10": _f_story, "B11": _f_story, "B12": _f_segments,
    "B13": _f_backstory, "B14": _f_ending, "B15": _nothing, "B16": _nothing,
    "B17": _f_result, "B18": _f_silent, "B19": _nothing, "B20": _f_visual,
    "C1": _nothing, "C2": _nothing, "C3": _nothing, "C4": _nothing,
    "D1": _nothing, "D2": _nothing, "D3": _nothing,
}


def fill(items: list[Item], ctx: Ctx) -> list[tuple[Item, list[str]]]:
    out = []
    for item in items:
        if not item.applies(ctx.line):
            continue
        facts = FIELDS[item.id](ctx) if ctx.spec else []
        out.append((item, facts))
    return out


# ————————————————————————— main 上的闸 —————————————————————————


@dataclass
class GateResult:
    name: str
    status: str                     # pass / fail / other / env / skip
    detail: str = ""


def _env() -> dict:
    env = dict(os.environ)
    extra = [str(ROOT / "src"), str(ROOT / "tools")]
    env["PYTHONPATH"] = os.pathsep.join(extra + [p for p in [env.get("PYTHONPATH")] if p])
    return env


def run_reel_dry_run(spec_path: Path, *, tail: int = 40) -> GateResult:
    """跑一趟真的 `--dry-run`：`validate_spec`（含 `reel_asset_gates` 那几道素材闸）＋
    措辞闸 ＋ probe 判据 ＋ 推送文案前置检查。`--outdir` 给一个临时目录——dry-run
    不写产物，推送标题的日期它自己取北京今天。"""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            proc = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "build_match_reel.py"), "render",
                 "--spec", str(spec_path), "--outdir", tmp, "--dry-run"],
                cwd=ROOT, env=_env(), capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            return GateResult("build_match_reel --dry-run", "fail", "超过 300 秒没跑完")
    text = (proc.stdout + proc.stderr).strip().split("\n")
    detail = "\n".join(text[-tail:])
    return GateResult("build_match_reel --dry-run",
                      "pass" if proc.returncode == 0 else "fail", detail)


_ENV_MISS = re.compile(r"(FileNotFoundError|No such file or directory)[^\n]*(assets|output)/")


def classify_failure(slug: str, message: str) -> str:
    """一条全库扫描的判据红了，红的是不是这一条。

    ⚠️ slug 要按边界认：`zverev-sonego` 不许认领 `zverev-sonego-us-open-2026-r1`
    的红（草稿 slug 是正式 slug 的前缀，仓库里真有这种形状）。
    """
    if re.search(rf"(?<![a-z0-9-]){re.escape(slug)}(?![a-z0-9-])", message or ""):
        return "fail"
    if _ENV_MISS.search(message or ""):
        return "env"
    return "other"


def run_ci_tests(slug: str, tests=TASTE_CI_TESTS) -> list[GateResult]:
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "junit.xml"
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
               f"--junitxml={xml}", *(node for node, _ in tests)]
        if importlib.util.find_spec("xdist") is not None:
            cmd[3:3] = ["-n", "0"]
        try:
            subprocess.run(cmd, cwd=ROOT, env=_env(), capture_output=True, text=True,
                           timeout=600)
        except subprocess.TimeoutExpired:
            return [GateResult("pytest 口味判据", "env", "超过 600 秒没跑完")]
        if not xml.is_file():
            return [GateResult("pytest 口味判据", "env", "pytest 没产出 junit 报告")]
        return parse_junit(slug, xml.read_text(encoding="utf-8"), tests)


def parse_junit(slug: str, xml_text: str, tests=TASTE_CI_TESTS) -> list[GateResult]:
    label = {node.split("::")[-1]: name for node, name in tests}
    seen: dict[str, GateResult] = {}
    for case in ET.fromstring(xml_text).iter("testcase"):
        test = case.get("name", "")
        name = f"{label.get(test, test)}（{test}）"
        bad = case.find("failure")
        if bad is None:
            bad = case.find("error")
        if case.find("skipped") is not None:
            seen[test] = GateResult(name, "skip")
        elif bad is None:
            seen[test] = GateResult(name, "pass")
        else:
            message = (bad.get("message") or "") + "\n" + (bad.text or "")
            status = classify_failure(slug, message)
            lines = [ln for ln in message.split("\n") if slug in ln][:6]
            seen[test] = GateResult(name, status, "\n".join(lines) if status == "fail"
                                    else _fmt(bad.get("message") or "", 200))
    missing = [label[t] for t in label if t not in seen]
    out = list(seen.values())
    out += [GateResult(f"{m}", "env", "pytest 没跑到这一条") for m in missing]
    return out


def run_interview_checks(spec: dict, xhs: str) -> list[GateResult]:
    """采访线：出片那一趟开头只读 spec 的那一排闸，**同一份名单**——
    `interview_preflight._spec_gates`（它和 `build_interview_clip.main()`／`render()` 开头那排
    按 ast 比过，`test_预检的闸和出片那一趟main开头那一排是同一份`）。

    原来这里手抄了一份名字元组：删掉 `check_score_orientation`，`test_taste_preflight.py`
    照样全绿（批次 4 复审 nit）。现在不抄，判据 `test_采访线预检的闸和出片那一趟是同一份名单`。"""
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
    import build_interview_clip as bic  # noqa: PLC0415
    import interview_preflight  # noqa: PLC0415
    from spec_wording import check_interview_copy_wording  # noqa: PLC0415
    from taste_gates_extra import interview_taste_extra  # noqa: PLC0415

    def taste_extra() -> None:
        # `check_taste_extra` 读的是 spec 旁边的 `.xhs.txt`；这里正文已经在手上（可能是
        # 还没落盘的草稿），直接调它背后那一刀
        hard, _ = interview_taste_extra(spec, xhs or None)
        if hard:
            raise SystemExit("；".join(hard))

    checks: list[tuple[str, Callable[[], object]]] = []
    for gate in interview_preflight._spec_gates(bic):
        name = gate.__name__
        if name == "check_takeaway" and not spec.get("takeaway"):
            continue
        checks.append((name, taste_extra if name == "check_taste_extra"
                       else (lambda f=gate: f(spec))))
    out = []
    for name, call in checks:
        buf = io.StringIO()
        try:
            with redirect_stdout(buf), redirect_stderr(buf):
                call()
            # 只报的口味发现（自动 spec 的采访封面大标题术语）印在 stdout，通过也要摆出来
            out.append(GateResult(name, "pass", _fmt(buf.getvalue(), 400)
                                  if name == "check_taste" else ""))
        except BaseException as exc:  # noqa: BLE001 —— 闸用 SystemExit 报红
            if isinstance(exc, KeyboardInterrupt):
                raise
            out.append(GateResult(name, "fail", _fmt(str(exc) or buf.getvalue(), 400)))
    problems = check_interview_copy_wording(spec, xhs or None)
    out.append(GateResult("check_interview_copy_wording",
                          "fail" if problems else "pass", "；".join(problems)))
    return out


# ————————————————————————— 输出 —————————————————————————

_MARK = {"pass": "✅", "fail": "❌", "other": "⚪", "env": "⚠️", "skip": "·"}
#: ⚪ 不等于过了：全库扫描的判据多半在第一处红就停（`assert not offenders` 之前先扫存量表、
#: 或者逐条 assert），别人的红会**遮住**这一条——它有没有红，这一趟看不出来。
_NOTE = {"other": "红在别的 spec 上；判据在第一处红就停，这一条被遮住了、判不了，不等于过了",
         "env": "环境缺文件或没跑到，判不了"}


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def reminders(inferred: list[Inferred], filled) -> list[Inferred]:
    """这条线用得上的推断规则：没挂清单编号的都列，挂了的只在那条清单也列出来时列。"""
    shown = {item.id for item, _ in filled}
    return [r for r in inferred if not r.items or set(r.items) & shown]


def report(ctx: Ctx, filled, gates: list[GateResult] | None,
           inferred: list[Inferred] | None = None) -> str:
    inferred = inferred or []
    tagged = {i for r in inferred for i in r.items}
    rows = [f"# 口味预检：{ctx.slug or '（还没有 spec）'}",
            f"线：{ctx.line or '（没认出栏目，只列「全部」那几条）'}"
            + (f"　spec：{_rel(ctx.path)}" if ctx.path else ""),
            "", "## 清单（自查——答「否」就先改，别带着进 render）", ""]
    for item, facts in filled:
        rows.append(f"[{item.id}] {item.question}"
                    + (f"　〔{INFERRED_TAG}〕" if item.id in tagged else ""))
        rows.extend(f"      · {f}" for f in facts)
        rows.append(f"      ❌ {item.bad}")
        rows.append(f"      ✅ {item.good}")
    shown = reminders(inferred, filled)
    if shown:
        rows += ["", f"## 提醒：推断出来的规则（{INFERRED_TAG}——不是他的原话，不判、不影响退出码）", ""]
        for r in shown:
            rows.append(f"· {r.title}（`{r.id}`"
                        + (f"，清单 {'、'.join(r.items)}" if r.items else "") + "）")
    if gates is not None:
        rows += ["", "## main 上已有的口味闸", ""]
        for g in gates:
            note = _NOTE.get(g.status, "")
            rows.append(f"{_MARK.get(g.status, '?')} {g.name}" + (f"　（{note}）" if note else ""))
            shows_notes = g.name.startswith("build_match_reel") or g.name == "check_taste"
            if g.detail and (g.status in ("fail", "env") or shows_notes):
                rows.extend("      " + ln for ln in g.detail.split("\n") if ln.strip())
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--slug", default="")
    ap.add_argument("--line", choices=LINES, help="spec 还没写时，按哪条线列空白清单")
    ap.add_argument("--no-gates", action="store_true", help="只列清单，不跑闸")
    ap.add_argument("--no-ci-tests", action="store_true",
                    help="不跑 pytest 那批口味判据（它们要 20 多秒）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    items = load_checklist()
    inferred = load_inferred()
    found = find_spec(args.slug) if args.slug else None
    if args.slug and not found and not args.line:
        print(f"找不到 specs/reels/{args.slug}.json 或 specs/interviews/{args.slug}.json；"
              "spec 还没写就加 `--line 赛场之上|网球有故事|赛后开麦` 列空白清单")
        return 2
    if found:
        kind, path = found
        spec = json.loads(path.read_text(encoding="utf-8"))
        xhs_path = path.with_suffix(".xhs.txt")
        ctx = Ctx(args.slug, path, kind, line_of(kind, spec), spec,
                  xhs_path.read_text(encoding="utf-8") if xhs_path.is_file() else "")
    else:
        ctx = Ctx(args.slug, None, "none", args.line)

    filled = fill(items, ctx)
    gates: list[GateResult] | None = None
    if found and not args.no_gates:
        if ctx.kind == "reel":
            from winners_ue_gate import problem as winners_ue_problem  # noqa: PLC0415
            stats_problem = winners_ue_problem(ctx.spec)
            gates = [GateResult("Winners/UE 证据", "fail" if stats_problem else "pass", stats_problem or "")]
            gates += [run_reel_dry_run(ctx.path)]
            if not args.no_ci_tests:
                gates += run_ci_tests(ctx.slug)
        elif ctx.kind == "explainer":
            from explainer_preflight import preflight
            gates = [GateResult(name, "fail" if problems else "pass", "\n".join(problems))
                     for name, problems in preflight(ctx.slug)]
            problems = []
            if ctx.spec.get("aspect_ratio") != "3:4": problems.append("portrait aspect must3:4")
            if not ctx.spec.get("chapters") or any(not c.get("claim_ids") for c in ctx.spec["chapters"]): problems.append("chapter claim evidence missing")
            if not ctx.spec.get("sound_direction"): problems.append("sourceaudio editorial direction missing")
            gates.append(GateResult("mixed-video editorial evidence", "fail" if problems else "pass", "\n".join(problems)))
            if not args.no_ci_tests: gates += run_ci_tests(ctx.slug)
        else:
            gates = run_interview_checks(ctx.spec, ctx.xhs)

    if args.json:
        tagged = {i for r in inferred for i in r.items}
        print(json.dumps({
            "slug": ctx.slug, "line": ctx.line,
            "checklist": [{"id": i.id, "question": i.question, "facts": f,
                           "rejected": i.bad, "accepted": i.good,
                           "inferred": i.id in tagged} for i, f in filled],
            "reminders": [{"id": r.id, "rule": r.title, "items": list(r.items)}
                          for r in reminders(inferred, filled)],
            "gates": None if gates is None else [g.__dict__ for g in gates],
        }, ensure_ascii=False, indent=1))
    else:
        print(report(ctx, filled, gates, inferred))
    red = [g for g in gates or [] if g.status == "fail"]
    if red and not args.json:
        print(f"\n❌ {len(red)} 道闸红在这一条上——先修，别发 render。")
    masked = [g for g in gates or [] if g.status == "other"]
    if masked and not args.json:
        print(f"\n⚪ {len(masked)} 道判据红在别的 spec 上，这一条被遮住了：退出码不算它们，"
              "但也没证明这一条过了——单独核一下，或等那几处修好再跑一遍。")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
