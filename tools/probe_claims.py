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
  源片、而且看得出是在做这一场（`blocks_dispatch`），就**不再点 run**
- **probe 那一步**（match-reel.yml）：只**出声**（`::warning::` 带着可复用的目录），
  不拦——会话有时就是要重 probe（换 `--scorebox`、换区间、故事片借源）

用法::

    python tools/probe_claims.py probe-step --url URL --slug SLUG --branch B --run-id N
    python tools/probe_claims.py check --url URL --slug SLUG [--ref origin/main]
    python tools/probe_claims.py release --url URL --slug SLUG
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass
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


def names_hit(surnames: list[str], slug: str) -> bool:
    """slug 里带不带这场球员的姓（整词；≥4 个字母的姓也认前缀——会话写过
    `wangxiyu-swiatek`，编排器的姓是 `wang`）。"""
    words = slug_words(slug)
    for s in (x.lower() for x in surnames if x):
        for w in words:
            if w == s or (len(s) >= 4 and w.startswith(s)):
                return True
    return False


@dataclass(frozen=True)
class Prior:
    slug: str
    kind: str      # "probe"（产物已落库）| "claim"（开跑时的认领）
    where: str     # 可复用的目录（probe 目录，或认领里记的产物目录）
    ref: str       # 在哪儿看到的：origin/main / HEAD / 工作区
    at: str        # 日期（probe）或认领时刻
    branch: str = ""

    def describe(self) -> str:
        if self.kind == "probe":
            return f"已经被 `{self.slug}` probe 过，产物在 {self.where}（{self.ref}，{self.at}）"
        br = f"，分支 {self.branch}" if self.branch else ""
        return (f"已经被 `{self.slug}` 认领（{self.at} 开跑{br}），"
                f"产物会落在 {self.where}")


def blocks_dispatch(prior: Prior, slug: str, surnames: list[str]) -> bool:
    """编排器看到这条先例要不要**不点 run**。三个条件都要成立：

    - 不是自己（同 slug 的先例是编排器自己上一趟，去重归 state 管——probe 失败
      摘了 state 要重试，不许被自己那条认领压住）
    - 不是故事片借源：`<题目>-src-<键>` 是「网球有故事」为了别的题目 probe 的，
      它不会产出这一场的「赛场之上」，拦了就漏一场
    - slug 里带着这场球员的姓：看得出在做这一场

    回放过：历史上 144 趟带自动备料的 probe 里有 8 趟撞了先例，8 趟的先例 slug 都带着
    这场的姓、没有一条是 `-src-`——这两个条件没有让任何一条该拦的漏掉。
    """
    if prior.slug == slug:
        return False
    if "src" in slug_words(prior.slug):
        return False
    return names_hit(surnames, prior.slug)


# ---------------------------------------------------------------- 读先例


def _claim_priors(doc: dict | None, *, ref: str, now: datetime, days: int) -> list[Prior]:
    out = []
    for c in (doc or {}).get("claims") or []:
        try:
            at = datetime.fromisoformat(str(c.get("claimed_at", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if now - at > timedelta(days=days):
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

    dates = recent_dates(today, days)
    if root is not None:
        root = Path(root)
        cp = root / claim_path(key)
        if cp.is_file():
            for p in _claim_priors(_load_json(cp.read_bytes()), ref="工作区", now=now, days=days):
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
        for p in _claim_priors(_load_json(git_blobs.show(ref, claim_path(key), cwd=cwd)),
                               ref=ref, now=now, days=days):
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
    return list(seen.values())


# ---------------------------------------------------------------- 写认领


def with_claim(doc: dict | None, *, key: str, url: str, slug: str, branch: str,
               run_id: str, outdir: str, now: datetime) -> dict:
    """在认领文件里加（或刷新）这个 slug 的那一条，顺手清掉过期的。"""
    keep = []
    for c in (doc or {}).get("claims") or []:
        if c.get("slug") == slug:
            continue
        try:
            at = datetime.fromisoformat(str(c.get("claimed_at", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if now - at <= timedelta(days=CLAIM_TTL_DAYS):
            keep.append(c)
    keep.append({"slug": slug, "url": url, "branch": branch, "run_id": str(run_id),
                 "outdir": outdir, "claimed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return {"video_key": key,
            "_why": "probe 一开跑就写的认领（tools/probe_claims.py）：编排器按它不再"
                    "重复点 run，会话 probe 时按它提示可复用的目录",
            "claims": keep}


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
                 fetch: bool = True) -> str:
    """把 `data/probe_claims/<key>.json` 改成 `mutate(旧内容)` 并直接推到 main。

    **不碰当前分支、不碰工作区、不碰索引**：临时索引读 main 的树、只换这一个
    文件、`commit-tree` 接在 main 上、推 `<提交>:refs/heads/main`。probe 可能跑在
    任何分支上，而编排器只看 main。撞车（main 被别人抢先）就重读 main 重做，
    最多 `attempts` 次。返回推上去的提交；内容没变返回空串。

    `write-tree --missing-ok`：runner 是 `--filter=blob:none` 的部分克隆，别的文件
    的 blob 本来就不在本地，校验它们「存在」会触发几千次懒取。
    """
    path = claim_path(key)
    remote_ref = f"refs/remotes/{remote}/{branch}"
    last = ""
    for attempt in range(1, attempts + 1):
        if fetch:
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
    ap.add_argument("action", choices=["probe-step", "check", "release"])
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
        except git_blobs.GitError as exc:
            print(f"::error::源片认领没摘掉（{exc}）——编排器三天内会以为「{args.slug} 在做」而"
                  f"不点这条源片；手动删 main 上的 {claim_path(key)} 里这一条")
            return 1
        print(f"[认领] 已摘 {args.slug} 的认领 {commit[:10] or '（本来就没有）'}")
        return 0

    if not args.no_fetch:
        try:
            git_blobs.fetch_ref("origin", "main")
        except git_blobs.GitError as exc:
            print(f"::warning::fetch main 失败，只能按本地已有的对象查先例：{exc}")
    try:
        priors = find_priors(key, refs=refs, root=Path("."), slug_hint=args.slug,
                             today=today, days=args.days)
    except git_blobs.GitError as exc:
        # 查不了要说查不了（「没查」和「查过没有」长得一样）；认领照写
        print(f"::warning::按视频 id 查先例失败，这一趟**没查**：{exc}")
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
            message=f"probe: 认领源片 {key}（{args.slug}）", fetch=not args.no_fetch)
    except git_blobs.GitError as exc:
        # 认领只是给别人看的告示，推不上不该让 probe 本身红——但必须出声：
        # 这一趟编排器看不见，可能会被重复点一次
        print(f"::warning::源片认领没推上 main（{exc}）——这一趟编排器看不见，可能被重复 probe")
        return 0
    print(f"[认领] 已在 main 上认领源片 {key} → {claim_path(key)}（{commit[:10] or '已是最新'}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
