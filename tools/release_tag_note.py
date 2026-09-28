#!/usr/bin/env python3
"""同一条片子重渲、`gh release upload --clobber` 换掉 tag 上那份之后，给共用这个 tag
的每一份 `render.json` 挂账（`_release_tag_note`）。

## 来路

`tests/test_release_tag_collision.py`（2026-08-14）要求：几份成片记录共用一条 Release
链接、而 `video_bytes` 对不上时，**每一份**都写一句 `_release_tag_note`，而且那句话里
要有日期。在这之前挂账全靠人手写——`bouzkova-kartal-bjk-cup-2026-qf` 那次换封面重渲
（09-22、09-23 两格），两份 render.json 是会话手改的。

评审 NB1（2026-09-27，O4 自动换图重推）：机器换完图、隔天派 `match-reel mode=render
push=true`，新的一格 `output/<新日期>/reel/<slug>/render.json` 和旧的那格**同一个
video_url、不同的 video_bytes**，两份都没挂账——render 用 GITHUB_TOKEN 直接提交 main，
CI 不跑，**下一个不相干的 PR 才红**，而且没有任何东西会去补。跨天是常态不是边角：
评审当时 `--plan` 的 6 条目标里 4 条最晚那一格在前一天。

## 两个调用方，各挂自己知道的那一半

| 谁 | 什么时候 | 挂哪几份 |
|---|---|---|
| `cover_upgrade.apply_upgrade`（`supersede`） | 换完图、派发重渲之前 | 这个 slug 在 tag 上的**每一份旧记录**：「重渲一传上来，这份记的那一版就不在 tag 上了」 |
| `match-reel.yml`「成片发到 Release」（`current`） | 刚传完、刚写完 `video_url` | **新的这一份**：「那一刻 tag 上就是我」——只有这一趟知道 |
| 会话手动跨天重渲（`supersede --slug`） | 派发 `mode=render` 之前，和改 spec 同一个提交 | 同 `cover_upgrade`：这个 slug 在 tag 上的每一份旧记录 |

⚠️ `current` **不去改旧目录**：一趟 render 只提交自己那一格（CLAUDE.md「并行的生成
任务：只碰自己那一块」）。旧的没挂账的（会话手动跨天重渲），它打一行 `::warning::`
点名——不再等 CI 红了才知道。

会话手动重渲（换封面、改旁白）在**派发之前**跑一次
`python3 tools/release_tag_note.py supersede --slug <slug> --why "<为什么重渲>"`，
和改 spec 一起提交：旧的那几格就挂好了，PR 的 CI 不会为这件事红一轮（2026-09-28
`wang-prozorova` 那次就红了一轮，手写一句才过）。同日重渲也照样跑——北京 23 点以后
派的会在跑到一半时翻进第二天，事先分不出是哪一种（`superseded` 的 docstring）。

⚠️ **别在仓库里猜 tag 上是哪一份**（按日期、按字节数都挑反过，见那条测试的 docstring）：
挂账的话只写「这一趟做了什么、在什么时刻」，量法照抄——`Range: bytes=0-1` 读
`Content-Range` 的总长。

## 稀疏检出

`output/` 在两条工作流里都不在工作区：枚举用 `git ls-files`，读用 `git show :<path>`
（工作区有就读工作区），写完 `git add --sparse`（不带 `--sparse`，`git add` 对稀疏范围外
的路径只警告、退出码 0，改动就静默丢了）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
NOTE_KEY = "_release_tag_note"
#: 挂账里写的量法——`test_release_tag_collision` 报错里给的同一句
MEASURE = "要确认 tag 上现在是哪一份，量 Range: bytes=0-1 回来的 Content-Range 总长，和各份的 video_bytes 比"
_TAG_RE = re.compile(r"/releases/download/([^/]+)/")
#: `match-reel` 的产物目录按渲的那一刻的北京日期起名（`OUT_DATE=$(TZ=Asia/Shanghai date +%F)`）
BEIJING = ZoneInfo("Asia/Shanghai")


def tag_of(url: str) -> str | None:
    m = _TAG_RE.search(url or "")
    return m.group(1) if m else None


def _stamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tracked(repo: Path, slug: str) -> list[str]:
    """这个 slug 被 git 跟踪的 `render.json`（仓库相对路径，按日期排）。

    ⚠️ git 跑不起来要出声，不许退成空列表——空列表在这里的意思是「没有旧记录、不用
    挂账」，而那正是一条会让 CI 红的静默。"""
    out = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--", f"output/*/reel/{slug}/render.json"],
        capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise RuntimeError(f"git ls-files 跑不起来（{out.returncode}）：{out.stderr.strip()}")
    pat = re.compile(rf"^output/\d{{4}}-\d\d-\d\d/reel/{re.escape(slug)}/render\.json$")
    return sorted(p for p in out.stdout.split() if pat.match(p))


def read(repo: Path, rel: str) -> dict:
    """工作区有就读工作区（还没提交的改动也看得见），没有就读**索引里那份**。"""
    disk = repo / rel
    if disk.is_file():
        return json.loads(disk.read_text(encoding="utf-8"))
    out = subprocess.run(["git", "-C", str(repo), "show", f":{rel}"],
                         capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise RuntimeError(f"{rel} 工作区没有、索引里也读不出来：{out.stderr.strip()}")
    return json.loads(out.stdout)


def write(repo: Path, rel: str, data: dict, *, stage: bool) -> None:
    """和 `match-reel.yml` 写 `video_url` 那一段同一个格式（indent=2、不转义中文）。"""
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if stage:
        subprocess.run(["git", "-C", str(repo), "add", "--sparse", "--", rel], check=True)


def _append(data: dict, text: str) -> None:
    """已经挂过的（上一次重渲留下的）不覆盖——那句话记的是当时的事，接在后面。"""
    old = str(data.get(NOTE_KEY) or "").strip()
    data[NOTE_KEY] = f"{old} ｜ {text}" if old else text


def superseded(repo: Path, slug: str, now: datetime, why: str) -> list[tuple[str, dict]]:
    """**只读**：这个 slug 在 Release tag 上的每一份旧记录，挂好账之后的内容
    `[(路径, 新内容)]`。读不出来就抛——调用方在**写任何东西之前**调它（`apply_upgrade`
    据此在改 spec 之前就退出，不留半截）。

    挂**每一份**、包括同一天那一格：同日重渲会原样覆盖那格的 render.json（账随之消失，
    那一格本来就是新的那份）；而北京 23 点以后派的重渲会在跑到一半时翻进第二天
    （CLAUDE.md「日期会在一趟 render 中途翻过去」），那时同一天那格就成了旧的——
    事先分不出是哪一种，所以都挂。"""
    today = now.astimezone(BEIJING).date().isoformat()
    rows: list[tuple[str, dict]] = []
    for rel in tracked(repo, slug):
        data = read(repo, rel)
        tag = tag_of(str(data.get("video_url") or ""))
        if tag != f"reel-{slug}":
            continue          # 2026-08-13 之前的成片在 git 里，不走 Release，不会被换掉
        _append(data, (
            f"{_stamp(now)} {why}：重渲一传上 Release（`gh release upload --clobber`），"
            f"tag `{tag}` 上的附件就换成新渲的那一份（记在北京 {today} 或更晚那一格 "
            f"output/<日期>/reel/{slug}/render.json），这里记的 video_bytes "
            f"{data.get('video_bytes')} 那一版就不在 tag 上了。{MEASURE}。"))
        rows.append((rel, data))
    return rows


def write_all(repo: Path, rows: list[tuple[str, dict]], *, stage: bool) -> list[str]:
    for rel, data in rows:
        write(repo, rel, data, stage=stage)
    return [rel for rel, _ in rows]


def supersede(repo: Path, slug: str, now: datetime, why: str, *,
              stage: bool = True) -> list[str]:
    """重渲**派发之前**，给这个 slug 在 Release tag 上的每一份旧记录挂账。返回挂了的路径。"""
    return write_all(repo, superseded(repo, slug, now, why), stage=stage)


def mark_current(repo: Path, render_json: Path, run_id: str, now: datetime
                 ) -> tuple[bool, list[str]]:
    """刚传上 Release 的这一份：同一条链接还被别的已跟踪记录共用，就写一句「那一刻
    tag 上就是我」。返回 (写没写, 共用这条链接却还没挂账的旧记录)。"""
    render_json = render_json.resolve()
    rel = render_json.relative_to(repo.resolve()).as_posix()
    data = json.loads(render_json.read_text(encoding="utf-8"))
    url = str(data.get("video_url") or "")
    tag = tag_of(url)
    if not tag:
        return False, []
    slug = render_json.parent.name
    others: list[str] = []
    unnoted: list[str] = []
    for path in tracked(repo, slug):
        if path == rel:
            continue
        other = read(repo, path)
        if str(other.get("video_url") or "") != url:
            continue
        others.append(str(Path(path).parent))
        if not str(other.get(NOTE_KEY) or "").strip():
            unnoted.append(path)
    if not others:
        return False, []
    _append(data, (
        f"{_stamp(now)} run {run_id} 把这一份（video_bytes {data.get('video_bytes')}）传上 "
        f"tag `{tag}`（--clobber），那一刻 tag 上就是这一份；同一个 tag 还被 "
        f"{'、'.join(others)} 共用，那几份记的是更早传上去的版本。之后再有重渲，以更晚"
        f"传上去的那一份为准。{MEASURE}。"))
    render_json.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    return True, unnoted


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    cur = sub.add_parser("current", help="刚传上 Release 的这一份挂账（match-reel.yml 用）")
    cur.add_argument("--render-json", required=True)
    cur.add_argument("--run-id", default="?")
    cur.add_argument("--repo", default=str(ROOT))
    cur.add_argument("--now", default="", help="ISO 时刻（测试用）")
    sup = sub.add_parser("supersede", help="重渲派发之前，给这个 slug 在 tag 上的每一份旧记录挂账（会话手动重渲用）")
    sup.add_argument("--slug", required=True)
    sup.add_argument("--why", default="会话手动重渲", help="写进挂账的那句「为什么重渲」")
    sup.add_argument("--repo", default=str(ROOT))
    sup.add_argument("--now", default="", help="ISO 时刻（测试用）")
    sup.add_argument("--no-stage", action="store_true", help="只写工作区、不 git add")
    args = ap.parse_args(argv)
    now = (datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now
           else datetime.now(timezone.utc))
    if args.cmd == "supersede":
        noted = supersede(Path(args.repo), args.slug, now, args.why, stage=not args.no_stage)
        for path in noted:
            print(f"[release-tag] 挂账：{path}")
        if not noted:
            # 第一次渲、或者只有 2026-08-13 之前走 git 的老成片——没有要挂的，也要出声
            print(f"[release-tag] {args.slug} 在 Release tag 上没有旧记录，不用挂账")
        return 0
    wrote, unnoted = mark_current(Path(args.repo), Path(args.render_json), args.run_id, now)
    print(f"[release-tag] {args.render_json}：" + (
        "同一个 tag 还被别的记录共用，已挂账" if wrote else "这个 tag 没有别的记录共用，不用挂账"))
    for path in unnoted:
        # 旧目录不归这一趟 render 提交（只碰自己那一块）——点名，别等 CI 红
        print(f"::warning::{path} 和这一趟共用 Release tag、字节数多半对不上，却没挂账——"
              f"合并前给它写一句 {NOTE_KEY}（test_同一个Release_tag被两份产物共用时每一份都要挂账 会红）；"
              f"下次派发重渲之前先跑 tools/release_tag_note.py supersede --slug {Path(args.render_json).parent.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
