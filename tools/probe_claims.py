#!/usr/bin/env python3
"""源片认领：同一条集锦别 probe 两遍——编排器和会话之间、会话和会话之间。

来路（2026-09-27 返工取证，P6）：probe 那一趟 3~5 分钟，是整条快路里最贵的一步，
而同一条源片被两边各 probe 一遍的事一直在发生，**两边互相看不见**：

- 编排器在会话已经 probe 过之后又点了一遍：`wang-prozorova`（ff9c2278，会话那份
  `wang-prozorova-singapore-2026-qf` 23 分钟前就落在 main 上）、`swiatek-zheng`
  （10dee4a6，会话那份 8 分钟前落在**分支**上）、`fernandez-chwalinska`（34 分钟）、
  `zheng-liutova`（113 分钟）、`wang-garland`（7fb9fa50，2 分钟——两边几乎同时点的）
- 编排器自己把同一场点了两遍：两个源一个给全名、一个给缩写，`slug_for` 拼出
  `bouzas-rybakina` / `maneiro-rybakina`、`pliskova-shnaider` / `ka.-shnaider`
  两个 slug，按 slug 去重认不出来
- 会话在编排器 probe 过之后又 probe 了一遍：`zhang-fernandez`（008a8806）

全库 628 份 probe.json 里 38 条源片被不止一个 slug probe 过。**slug 认不出同一场**
（赛事后缀、赢家在前、缩写名），**源片的视频 id 认得出**。所以这里按视频 id 认：

1. `data/probe_claims/<视频 id>.json` —— 每趟 probe **一开跑**就往 main 上写一条
   认领（谁、哪个分支、哪个 run、产物会落在哪个目录）。写在开跑时不是落库时：
   probe 要跑 3~5 分钟，等产物落库再说「我做过了」，`wang-garland` 那种两分钟
   的并发永远赶不上。写到 **main**（不管 probe 跑在哪个分支）：编排器只看得见
   main，会话分支上的产物它一个字节都读不到——`swiatek-zheng` 就栽在这儿
2. 最近 `DEDUPE_DAYS` 天的 `output/*/reel/*/probe.json` —— 认领这套上线之前的
   存量，以及认领推送失败的那几趟

两个出口：
- **编排器**（`orchestrate.drop_already_probed`）：别的 slug 已经 probe／认领过这条
  源片、而且看得出是在做这一场的**赛场之上**（`blocks_dispatch`），就**不再点 run**
- **probe 那一步**（match-reel.yml）：只**出声**（`::warning::` 带着可复用的目录），
  不拦——会话有时就是要重 probe（换 `--scorebox`、换区间、故事片借源）

认领的三个终点：probe 失败 `release` 摘掉；分支上 probe 成功 `done` 标完成（产物落在
分支上，main 上看不见，只能靠这一笔）；**job 被取消／超时两样都做不了**——所以没标
完成的认领开跑 `CLAIM_STALE_MINUTES` 分钟后作废，不许它把这一场压三天。标了完成的
认领也有钟：完成之后 `DONE_CLAIM_SPEC_HOURS`（20）小时里 main 上还没有这个 slug 的
正式 spec，就不再挡（账号所有者 2026-09-27 选定，和比赛日的新鲜窗同一个数）。

用法::

    python tools/probe_claims.py probe-step --url URL --slug SLUG --branch B --run-id N
    python tools/probe_claims.py check --url URL --slug SLUG [--ref origin/main]
    python tools/probe_claims.py release --url URL --slug SLUG
    python tools/probe_claims.py done --url URL --slug SLUG
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import git_blobs  # noqa: E402

CLAIMS_DIR = "data/probe_claims"
#: 回看几天。认领和 probe 目录一律按这个窗口——三天前 probe 过的源片，比赛早就
#: 过了「本比赛日」那道选题闸（`FRESH_RESULT_HOURS = 20`），再遇到它就是另一件事了。
DEDUPE_DAYS = 3
#: 认领文件里单条记录的寿命：超过就在下一次写这个文件时顺手清掉。
CLAIM_TTL_DAYS = 7
#: 没标完成（`done_at`）的认领活多久。probe job 的 `timeout-minutes` 是 63，再给
#: 排队留一截：过了这个点还没标完成、也没摘，就是 job 被取消／超时了（`release`
#: 挂在 `failure()` 上，取消时不跑），或者摘认领那一推没推上——**这种认领不许把这一场
#: 压三天**（review 复现的死锁：编排器缩写名那趟被取消，认领还挂着，下一班同一场的
#: 全名 slug 被它挡住，两个 slug 三天里谁都不点）。
CLAIM_STALE_MINUTES = 90
#: 标了完成（`done_at`）的认领挡多久：完成之后这么多小时里，main 上还是没有这个
#: slug 的正式 spec（`FORMAL_SPEC`），认领就**不再挡**编排器。账号所有者 2026-09-27
#: 选定：「和比赛日那道新鲜窗同一个数」——`orchestrate.FRESH_RESULT_HOURS` ＝
#: `promote_reel_draft.PENDING_MAX_AGE` ＝ 20 小时（不 import：orchestrate 反过来
#: import 这里；三个数由 `test_完成的认领20小时没有正式spec就不再挡` 钉成同一个）。
#: 在这之前标了完成的认领一律挡满 `DEDUPE_DAYS`（3 天）——会话 probe 完没写成 spec
#: （换题、放弃、卡在封面），这一场就三天没人再点。
DONE_CLAIM_SPEC_HOURS = 20
FORMAL_SPEC = "specs/reels/{}.json"
#: 只有这一栏的 probe 才算「在做这一场」——故事片借同一条源片 probe，不会产出赛场之上。
MATCH_COLUMN = "赛场之上"

_YT = re.compile(r"(?:youtube\.com/(?:watch\?(?:[^#\s]*&)?v=|shorts/|live/|embed/)|youtu\.be/)"
                 r"([A-Za-z0-9_-]{11})")
_TTV = re.compile(r"tennistv\.com/videos/(\d+)")
_PROBE = re.compile(r"^output/(\d{4}-\d{2}-\d{2})/reel/([^/]+)/probe\.json$")


def video_key(url: str | None) -> str | None:
    """源片的稳定键：YouTube 取 11 位 id，Tennis TV 取 `tennistv-<数字>`。

    认不出的（brightcove、x.com、直链）返回 None——**不认领、不去重**，
    别拿整条 URL 当键：同一条片子带不带 `&t=`、`?si=` 是两个串。
    """
    m = _YT.search(url or "")
    if m:
        return m.group(1)
    m = _TTV.search(url or "")
    return f"tennistv-{m.group(1)}" if m else None


def beijing_today() -> date:
    return (datetime.now(timezone.utc) + timedelta(hours=8)).date()


def recent_dates(today: date, days: int = DEDUPE_DAYS) -> list[str]:
    return [(today - timedelta(days=i)).isoformat() for i in range(days + 1)]


def slug_words(slug: str) -> list[str]:
    return [w for w in re.split(r"[-_.]+", (slug or "").lower()) if w]


def _word_is(surname: str, word: str) -> bool:
    """整词；≥4 个字母的姓也认前缀——会话写过 `wangxiyu-swiatek`，编排器的姓是 `wang`。"""
    return word == surname or (len(surname) >= 4 and word.startswith(surname))


def names_hit(surnames: list[str], slug: str) -> bool:
    """slug 里带不带这场球员的姓（任何一个、任何位置）。"""
    words = slug_words(slug)
    return any(_word_is(s, w) for s in (x.lower() for x in surnames if x) for w in words)


def leads_with_pair(surnames: list[str], slug: str) -> bool:
    """slug **开头两个词正好是这两个姓**（先后不论）——赛场之上的命名：编排器拼
    `<home>-<away>`，会话写 `<赢家>-<输家>-<站>-<年>-<轮>`。

    故事片借源的 slug 姓也带着，只是不在开头：`comebacks-zheng-keys`（和 `keys-zheng`
    同一条视频）、`zheng-us-open-outlook-zheng`、`zheng-lanlana-hl-zheng-paris`——
    「slug 里带着姓」拦它们，就是故事片先 probe 了，这一场的赛场之上三天不点。
    """
    names = [x.lower() for x in surnames if x]
    words = slug_words(slug)[:2]
    if len(names) != 2 or len(words) != 2:
        return False
    a, b = names
    return ((_word_is(a, words[0]) and _word_is(b, words[1]))
            or (_word_is(b, words[0]) and _word_is(a, words[1])))


@dataclass(frozen=True)
class Prior:
    slug: str
    kind: str      # "probe"（产物已落库）| "claim"（开跑时的认领）| "state"（编排器自己点过）
    where: str     # 可复用的目录（probe 目录，或认领里记的产物目录）
    ref: str       # 在哪儿看到的：origin/main / HEAD / 工作区 / state
    at: str        # 日期（probe）或认领时刻
    branch: str = ""
    #: 这个 slug 的 spec／草稿自己说是哪一栏（`cover.eyebrow`，没有就 `_column`）；
    #: 看不到 spec（认领刚写、spec 在别人分支上）就是空串
    column: str = ""

    def describe(self) -> str:
        if self.kind == "state":
            return f"编排器 {self.at} 已经按同一条源片点过 `{self.slug}`，产物会落在 {self.where}"
        if self.kind == "probe":
            return f"已经被 `{self.slug}` probe 过，产物在 {self.where}（{self.ref}，{self.at}）"
        br = f"，分支 {self.branch}" if self.branch else ""
        return (f"已经被 `{self.slug}` 认领（{self.at} 开跑{br}），"
                f"产物会落在 {self.where}")


def blocks_dispatch(prior: Prior, slug: str, surnames: list[str], *,
                    own: frozenset[str] | set[str] = frozenset()) -> bool:
    """编排器看到这条先例要不要**不点 run**：要有**正面证据**说它是这一场的赛场之上。

    - 自己（同 slug）不算：去重归 state 管——probe 失败摘了 state 要重试，不许被
      自己那条认领压住
    - `own`：编排器 state 里按**同一条源片**点过的别的 slug（两个源一个全名一个
      缩写，`ka.-shnaider` / `pliskova-shnaider`）——编排器只点赛场之上，算
    - slug 里有 `src`：故事片借源的约定写法，不算
    - spec／草稿看得到栏目：是赛场之上、slug 里带着这场的姓才算；别的栏目一律不算
    - 看不到栏目（认领刚写，spec 在别人分支上）：slug **开头两个词正好是这两个姓**
      才算（`leads_with_pair`）。只看「slug 里带着姓」是 review 抓到的误拦：
      `comebacks-zheng-keys` 和 `keys-zheng` 是同一条视频

    回放（全库 628 份 probe.json 里 38 条被不止一个 slug probe 过，逐对拿编排器 slug 比）：
    会话那份（`wang-prozorova-singapore-2026-qf` 这种）一律照旧挡；缩写名那两对
    （`ka.-shnaider`、`maneiro-rybakina`）命名认不出，靠同批合组、`own` 和草稿写的栏目；老规则会挡的
    `comebacks-zheng-keys`、`zheng-us-open-outlook-zheng` 两条故事片现在不挡。
    """
    if prior.slug == slug:
        return False
    if prior.slug in own:
        return True
    if "src" in slug_words(prior.slug):
        return False
    if prior.column:
        return prior.column == MATCH_COLUMN and names_hit(surnames, prior.slug)
    return leads_with_pair(surnames, prior.slug)


# ---------------------------------------------------------------- 读先例


def _aware(at: datetime) -> datetime:
    return at if at.tzinfo is not None else at.replace(tzinfo=timezone.utc)


def _claimed_at(c) -> datetime | None:
    """认领时刻；读不出来是 None。漏了时区的（手改的、别的工具写的）按 UTC 读——
    认领一律写 UTC；不补的话 `now - at` 是 TypeError，一个坏条目把整班带崩。"""
    if not isinstance(c, dict):
        return None
    try:
        return _aware(datetime.fromisoformat(str(c.get("claimed_at", "")).replace("Z", "+00:00")))
    except (ValueError, TypeError):
        return None


def claim_is_stale(c: dict, now: datetime) -> bool:
    """没标完成、开跑超过 `CLAIM_STALE_MINUTES` 分钟：那趟 job 多半被取消／超时了。"""
    at = _claimed_at(c)
    return (at is not None and not c.get("done_at")
            and _aware(now) - at > timedelta(minutes=CLAIM_STALE_MINUTES))


def done_claim_lapsed(c: dict, now: datetime, has_spec) -> bool:
    """标了完成、完成之后超过 `DONE_CLAIM_SPEC_HOURS` 小时、`has_spec(slug)` 还是假：
    那趟 probe 跑完了，但这一场没人写成正式 spec——认领不再挡（账号所有者 2026-09-27）。
    `done_at` 读不出来就按没过期算（判不了 ≠ 过期了）。"""
    done = _claimed_at({"claimed_at": c.get("done_at")}) if isinstance(c, dict) else None
    if done is None or _aware(now) - done <= timedelta(hours=DONE_CLAIM_SPEC_HOURS):
        return False
    return not has_spec(str(c.get("slug") or ""))


def _claim_priors(doc: dict | None, *, ref: str, now: datetime, days: int,
                  has_spec=None, stale_seen: set | None = None) -> list[Prior]:
    """`has_spec(slug)`：main 上有没有这个 slug 的正式 spec。不给就不做完成认领的
    20 小时作废（查不了 spec 时照旧挡，不许因为「没查」就放行）。

    `stale_seen`：同一次查找里已经报过「不再挡」的认领。编排器按工作区和 HEAD 各读一遍
    同一个认领文件，不带它的话每条都印两遍。"""
    out = []
    now = _aware(now)
    claims = (doc or {}).get("claims") if isinstance(doc, dict) else None
    for c in claims if isinstance(claims, list) else []:
        at = _claimed_at(c)
        if at is None or now - at > timedelta(days=days):
            continue
        if claim_is_stale(c, now):
            print(f"[认领] {c.get('slug')} 的认领开跑 {int((now - at).total_seconds() // 60)} 分钟"
                  f"还没标完成（{ref}），按作废处理——那趟 job 多半被取消或超时了")
            continue
        if has_spec is not None and done_claim_lapsed(c, now, has_spec):
            seen_key = ("done", str(c.get("slug")), str(c.get("done_at")))
            if stale_seen is None or seen_key not in stale_seen:
                print(f"[认领] {c.get('slug')} 的认领 {c.get('done_at')} 就标了完成，"
                      f"{DONE_CLAIM_SPEC_HOURS} 小时过去还没有正式 spec"
                      f"（{FORMAL_SPEC.format(c.get('slug'))}），不再挡这一场")
            if stale_seen is not None:
                stale_seen.add(seen_key)
            continue
        out.append(Prior(slug=str(c.get("slug") or "?"), kind="claim",
                         where=str(c.get("outdir") or ""), ref=ref,
                         at=at.strftime("%Y-%m-%dT%H:%MZ"), branch=str(c.get("branch") or "")))
    return out


def _load_json(raw: bytes | str | None) -> dict | None:
    if raw is None:
        return None
    try:
        doc = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def claim_path(key: str) -> str:
    return f"{CLAIMS_DIR}/{key}.json"


_SPEC_PATHS = ("specs/reels/{}.json", "specs/reels/pending/{}.draft.json",
               "specs/reels/pending/{}.json")
_COLUMN_ALIAS = {"reel": MATCH_COLUMN, "preview": "开球之前", "interview": "赛后开麦"}


def spec_column(doc: dict | None) -> str:
    """spec／草稿自己说的栏目：`cover.eyebrow` 优先，没有再看 `_column`（自动草稿写
    `reel`，老 spec 写「赛场之上。讲一场对决……」这种带说明的串）。"""
    if not isinstance(doc, dict):
        return ""
    cover = doc.get("cover") if isinstance(doc.get("cover"), dict) else {}
    for raw in (cover.get("eyebrow"), doc.get("_column")):
        col = str(raw or "").strip()
        if not col:
            continue
        if col.startswith(MATCH_COLUMN):
            return MATCH_COLUMN
        return _COLUMN_ALIAS.get(col, col.split("。")[0])
    return ""


def _column_of(slug: str, *, root: Path | None, refs, cwd) -> str:
    for tpl in _SPEC_PATHS:
        path = tpl.format(slug)
        if root is not None and (Path(root) / path).is_file():
            col = spec_column(_load_json((Path(root) / path).read_bytes()))
            if col:
                return col
        for ref in refs:
            col = spec_column(_load_json(git_blobs.show(ref, path, cwd=cwd)))
            if col:
                return col
    return ""


def find_priors(key: str, *, refs: list[str] = (), root: Path | None = None,
                surnames: list[str] | None = None, slug_hint: str = "",
                today: date | None = None, now: datetime | None = None,
                days: int = DEDUPE_DAYS, cwd: Path | str | None = None) -> list[Prior]:
    """最近 `days` 天里，谁 probe／认领过这条源片。

    - `refs`：按 git 对象读（稀疏检出、部分克隆里照样读得到）
    - `root`：按工作区读（本地完整检出；编排器的 `data/` 在工作区里）
    - `surnames` / `slug_hint`：只打开 slug 里带着这些词的 probe.json——三天里
      几十份 probe.json，一份份懒取 blob 是一个个来回；不带这场姓的目录本来
      也不会被 `blocks_dispatch` 认作「在做这一场」。两样都不给就全读
    """
    today = today or beijing_today()
    now = now or datetime.now(timezone.utc)
    words = [w for w in (surnames or []) if w] + [
        w for w in slug_words(slug_hint) if len(w) >= 3 and not w.isdigit()]

    def wanted(slug: str) -> bool:
        return not words or names_hit(words, slug)

    seen: dict[tuple[str, str, str], Prior] = {}

    def add(p: Prior) -> None:
        seen.setdefault((p.slug, p.kind, p.where), p)

    live_refs = []
    stale_seen: set = set()

    def has_spec(slug: str) -> bool:
        # 工作区或任何一个给了的 ref 上有就算——编排器的 HEAD 就是 main；会话那头
        # 连自己分支也算上，只会多挡、不会误放
        path = FORMAL_SPEC.format(slug)
        if root is not None and (Path(root) / path).is_file():
            return True
        return any(git_blobs.show(r, path, cwd=cwd) is not None for r in refs)

    dates = recent_dates(today, days)
    if root is not None:
        root = Path(root)
        cp = root / claim_path(key)
        if cp.is_file():
            for p in _claim_priors(_load_json(cp.read_bytes()), ref="工作区", now=now, days=days,
                                   has_spec=has_spec, stale_seen=stale_seen):
                add(p)
        for d in dates:
            for pj in sorted((root / "output" / d / "reel").glob("*/probe.json")):
                slug = pj.parent.name
                if not wanted(slug):
                    continue
                doc = _load_json(pj.read_bytes())
                if doc and video_key(doc.get("url")) == key:
                    add(Prior(slug=slug, kind="probe", where=str(pj.parent.relative_to(root)),
                              ref="工作区", at=d))
    for ref in refs:
        if not git_blobs.rev(ref, cwd=cwd):
            print(f"[认领] {ref} 在这份检出里不存在，跳过（没 fetch？）")
            continue
        live_refs.append(ref)
        for p in _claim_priors(_load_json(git_blobs.show(ref, claim_path(key), cwd=cwd)),
                               ref=ref, now=now, days=days, has_spec=has_spec,
                               stale_seen=stale_seen):
            add(p)
        rows = [(oid, path) for oid, path in git_blobs.ls_tree(
            ref, [f"output/{d}/reel" for d in dates], cwd=cwd)
            if (m := _PROBE.match(path)) and wanted(m.group(2))]
        blobs = git_blobs.read_blobs([oid for oid, _ in rows], cwd=cwd)
        for oid, path in rows:
            doc = _load_json(blobs.get(oid))
            m = _PROBE.match(path)
            if doc and video_key(doc.get("url")) == key:
                add(Prior(slug=m.group(2), kind="probe", where=str(Path(path).parent),
                          ref=ref, at=m.group(1)))
    # 每个先例的栏目（`blocks_dispatch` 靠它分赛场之上和故事片借源）：先例一般就
    # 零到两条，逐个 `cat-file` 就够
    columns: dict[str, str] = {}
    out = []
    for p in seen.values():
        if p.slug not in columns:
            columns[p.slug] = _column_of(p.slug, root=root, refs=live_refs, cwd=cwd)
        out.append(replace(p, column=columns[p.slug]))
    return out


# ---------------------------------------------------------------- 写认领


def with_claim(doc: dict | None, *, key: str, url: str, slug: str, branch: str,
               run_id: str, outdir: str, now: datetime) -> dict:
    """在认领文件里加（或刷新）这个 slug 的那一条，顺手清掉过期的。"""
    now = _aware(now)
    keep = []
    for c in (doc or {}).get("claims") or []:
        at = _claimed_at(c)
        if at is None or c.get("slug") == slug:
            continue
        if now - at <= timedelta(days=CLAIM_TTL_DAYS):
            keep.append(c)
    keep.append({"slug": slug, "url": url, "branch": branch, "run_id": str(run_id),
                 "outdir": outdir, "claimed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return {"video_key": key,
            "_why": "probe 一开跑就写的认领（tools/probe_claims.py）：编排器按它不再"
                    "重复点 run，会话 probe 时按它提示可复用的目录",
            "claims": keep}


def with_done(doc: dict | None, *, slug: str, now: datetime) -> dict | None:
    """probe 成功：给这个 slug 的认领标 `done_at`，它就不会在 `CLAIM_STALE_MINUTES`
    之后作废。没有这条认领（开跑那一推没推上）就原样返回——不补写。"""
    if not doc:
        return doc
    claims = []
    for c in doc.get("claims") or []:
        if isinstance(c, dict) and c.get("slug") == slug and not c.get("done_at"):
            c = {**c, "done_at": _aware(now).strftime("%Y-%m-%dT%H:%M:%SZ")}
        claims.append(c)
    return {**doc, "claims": claims}


def without_claim(doc: dict | None, *, slug: str) -> dict | None:
    """probe 失败时摘掉自己那一条；摘空了返回 None（删文件）。"""
    if not doc:
        return None
    rest = [c for c in doc.get("claims") or [] if c.get("slug") != slug]
    if not rest:
        return None
    return {**doc, "claims": rest}


def push_to_main(key: str, mutate, *, message: str, cwd: Path | str | None = None,
                 remote: str = "origin", branch: str = "main", attempts: int = 5,
                 fetch: bool = True, fetched: bool = False) -> str:
    """把 `data/probe_claims/<key>.json` 改成 `mutate(旧内容)` 并直接推到 main。

    **不碰当前分支、不碰工作区、不碰索引**：临时索引读 main 的树、只换这一个
    文件、`commit-tree` 接在 main 上、推 `<提交>:refs/heads/main`。probe 可能跑在
    任何分支上，而编排器只看 main。撞车（main 被别人抢先）就重读 main 重做，
    最多 `attempts` 次。返回推上去的提交；内容没变返回空串。

    `write-tree --missing-ok`：runner 是 `--filter=blob:none` 的部分克隆，别的文件
    的 blob 本来就不在本地，校验它们「存在」会触发几千次懒取。

    `fetched`：调用方刚 fetch 过 main，第一趟不再取（probe-step 查先例前已经取过，
    再取一遍是白等两秒）；被拒之后照旧重取。
    """
    path = claim_path(key)
    remote_ref = f"refs/remotes/{remote}/{branch}"
    last = ""
    for attempt in range(1, attempts + 1):
        if fetch and not (fetched and attempt == 1):
            git_blobs.fetch_ref(remote, branch, cwd=cwd)
        base = git_blobs.rev(remote_ref, cwd=cwd)
        if not base:
            raise git_blobs.GitError(f"{remote_ref} 不存在")
        old = _load_json(git_blobs.show(base, path, cwd=cwd))
        new = mutate(old)
        if new == old:
            return ""
        with tempfile.TemporaryDirectory() as td:
            env = {"GIT_INDEX_FILE": str(Path(td) / "index"), **git_blobs.BOT_ENV}
            git_blobs.git("read-tree", base, cwd=cwd, env=env)
            if new is None:
                git_blobs.git("update-index", "--force-remove", "--", path, cwd=cwd, env=env)
            else:
                body = json.dumps(new, ensure_ascii=False, indent=2) + "\n"
                oid = git_blobs.git("hash-object", "-w", "--stdin", cwd=cwd, input=body).strip()
                git_blobs.git("update-index", "--add", "--cacheinfo",
                              f"100644,{oid},{path}", cwd=cwd, env=env)
            tree = git_blobs.git("write-tree", "--missing-ok", cwd=cwd, env=env).strip()
        commit = git_blobs.git("commit-tree", tree, "-p", base, "-m", message,
                               cwd=cwd, env=git_blobs.BOT_ENV).strip()
        try:
            git_blobs.git("push", "--quiet", remote, f"{commit}:refs/heads/{branch}", cwd=cwd)
            return commit
        except git_blobs.GitError as exc:
            last = str(exc)
            print(f"[认领] 推 {branch} 被拒（第 {attempt} 次），重读 {branch} 再做一遍")
            if not fetch:
                break
            time.sleep(min(2 * attempt, 8))
    raise git_blobs.GitError(f"连续 {attempts} 次没推上 {branch}：{last}")


# ---------------------------------------------------------------- CLI


def _outdir_for(slug: str, today: date) -> str:
    # 和 match-reel.yml「算出目录」同一个口径：北京日期
    return f"output/{today.isoformat()}/reel/{slug}"


def report(priors: list[Prior], slug: str) -> int:
    """打出别的 slug 的先例（GitHub 注解）。返回条数。"""
    others = [p for p in priors if p.slug != slug]
    for p in others:
        print(f"::warning::这条源片{p.describe()}——缩略图墙、切点、死球、静音区都在"
              f"那个目录里，能接着用就别再等这一趟（find_pending_draft.py 按姓查草稿）")
    return len(others)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("action", choices=["probe-step", "check", "release", "done"])
    ap.add_argument("--url", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--branch", default="")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--ref", action="append", default=None,
                    help="按 git 对象查先例的 ref（可给多次）；默认 origin/main 和 HEAD")
    ap.add_argument("--days", type=int, default=DEDUPE_DAYS)
    ap.add_argument("--no-fetch", action="store_true", help="不先 fetch main（测试／离线用）")
    args = ap.parse_args(argv)

    key = video_key(args.url)
    if key is None:
        print(f"[认领] 这条源片认不出稳定的视频 id（{args.url[:80]}），不认领、不查重")
        return 0
    refs = args.ref or ["refs/remotes/origin/main", "HEAD"]
    today = beijing_today()

    if args.action == "release":
        try:
            commit = push_to_main(key, lambda d: without_claim(d, slug=args.slug),
                                  message=f"probe: 摘掉 {args.slug} 对源片 {key} 的认领（probe 失败）",
                                  fetch=not args.no_fetch)
        except Exception as exc:  # noqa: BLE001 —— 认领是告示，哪种错都只出声
            print(f"::error::源片认领没摘掉（{type(exc).__name__}: {exc}）——编排器会以为"
                  f"「{args.slug} 在做」，要等 {CLAIM_STALE_MINUTES} 分钟认领作废才点这条源片；"
                  f"急的话手动删 main 上的 {claim_path(key)} 里这一条")
            return 1
        print(f"[认领] 已摘 {args.slug} 的认领 {commit[:10] or '（本来就没有）'}")
        return 0

    if args.action == "done":
        try:
            commit = push_to_main(
                key, lambda d: with_done(d, slug=args.slug, now=datetime.now(timezone.utc)),
                message=f"probe: {args.slug} 对源片 {key} 的认领标完成", fetch=not args.no_fetch)
        except Exception as exc:  # noqa: BLE001 —— 同上
            print(f"::warning::认领没标上完成（{type(exc).__name__}: {exc}）——开跑 "
                  f"{CLAIM_STALE_MINUTES} 分钟后编排器会当它作废，这一场可能被重复 probe 一次")
            return 0
        print(f"[认领] {args.slug} 的认领已标完成 {commit[:10] or '（没有这条认领，不补写）'}")
        return 0

    fetched = False
    if not args.no_fetch:
        try:
            git_blobs.fetch_ref("origin", "main")
            fetched = True
        except git_blobs.GitError as exc:
            print(f"::warning::fetch main 失败，只能按本地已有的对象查先例：{exc}")
    try:
        priors = find_priors(key, refs=refs, root=Path("."), slug_hint=args.slug,
                             today=today, days=args.days)
    except Exception as exc:  # noqa: BLE001 —— 告示查不了不许让 probe 红
        # 查不了要说查不了（「没查」和「查过没有」长得一样）；认领照写
        print(f"::warning::按视频 id 查先例失败，这一趟**没查**：{type(exc).__name__}: {exc}")
        priors = None
    if priors is not None:
        n = report(priors, args.slug)
        print(f"[认领] 源片 {key}：近 {args.days} 天别的 slug 的先例 {n} 条"
              + ("" if n else f"（按视频 id 查过 {'、'.join(refs)} 上的认领和 probe 目录，没人做过）"))
    if args.action == "check":
        return 0
    outdir = _outdir_for(args.slug, today)
    now = datetime.now(timezone.utc)
    try:
        commit = push_to_main(
            key, lambda d: with_claim(d, key=key, url=args.url, slug=args.slug,
                                      branch=args.branch, run_id=args.run_id,
                                      outdir=outdir, now=now),
            message=f"probe: 认领源片 {key}（{args.slug}）", fetch=not args.no_fetch,
            fetched=fetched)
    except Exception as exc:  # noqa: BLE001
        # 认领只是给别人看的告示，推不上不该让 probe 本身红——但必须出声：
        # 这一趟编排器看不见，可能会被重复点一次
        print(f"::warning::源片认领没推上 main（{type(exc).__name__}: {exc}）"
              "——这一趟编排器看不见，可能被重复 probe")
        return 0
    print(f"[认领] 已在 main 上认领源片 {key} → {claim_path(key)}（{commit[:10] or '已是最新'}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
