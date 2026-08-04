#!/usr/bin/env python3
"""合进 main 之后，判断该不该自动把这条片子推到微信。

**为什么要有这一步。** 出片和发消息是两次动作：分支上 `push=false` 渲片
（六到十四分钟），合进 main 之后 `mode=push` 只推不渲（实测 **43 秒**，
run 30755226229）。43 秒不值得优化，真正的成本是**人的往返**——渲完、开 PR、
合并、再记得回来点一次 dispatch。这个脚本要省掉的是最后那一下。

**而它是这条链上唯一新增的风险点**，因为微信那条消息发出去收不回来。
所以判据全部收在这儿（不写进 YAML，那儿测不了），四道闸一道都不能省：

1. **路径形状**必须是 `output/<日期>/reel/<slug>/render.json`
2. spec 里必须显式写 `"push": {"auto": true}` ——**默认关**，
   和 `mixed_fps` / `silent_source` 一个形状：认领这一步把「想清楚了」和
   「凑合一下」分开
3. 这条**没推过**：`<outdir>/pushed.json` 在仓库里就说明发过了。
   查产物，不查信号——「工作流跑过一次」证明不了消息发出去了。
   ⚠️ 查的是 **`git ls-files`，不是 `test -f`**，两个原因缺一不可：
   ① 这条工作流是稀疏检出的，判断时 `output/` 那一格**还没加回工作区**，
   按文件存不存在判**恒为假**——那道闸等于没装，会重复发；
   ② 只活在工作区里的标记本来就不算数（同一个毛病在复制页上踩过两次：
   日志印着链接、步骤 success、人点开 404）
4. 一趟**最多一条**。一次合并带进来两条成片就一条都不发，报出来让人手动。
   批量自动发微信，错一次就是错一片

判据在 `tests/test_auto_push.py`，每一道都反向验证过。

用法：

    auto_push_gate.py --changed <改动的文件…>     # 列出该发的那一条
    auto_push_gate.py --record <outdir> --run <运行地址>   # 发完记一笔
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# `output/2026-08-03/reel/eala-pegula/render.json`
_RENDER_JSON = re.compile(
    r"^output/(\d{4}-\d\d-\d\d)/reel/([^/]+)/render\.json$")

SPEC_DIR = Path("specs/reels")
MARKER = "pushed.json"


class Skip(Exception):
    """这一条不发，而且**要说出为什么**。

    「跳过了」和「压根没看到」在日志里长得一模一样——这个仓库里那类不吭声的
    兜底已经栽过很多次，所以每一条跳过都带着理由打出来。
    """


def candidate(path: str, repo: Path) -> tuple[str, Path]:
    """一个改动的文件 → (slug, outdir)，不合格就 `Skip`。"""
    match = _RENDER_JSON.match(path)
    if not match:
        raise Skip(f"{path}：不是 output/<日期>/reel/<slug>/render.json")
    slug = match.group(2)
    outdir = repo / "output" / match.group(1) / "reel" / slug
    return slug, outdir


def tracked(repo: Path, path: Path) -> bool:
    """这个文件在**仓库**里吗（不是在工作区里）。

    稀疏检出下这两件事会分家：`output/` 那一格不在工作区，`test -f` 一律为假，
    而 `git ls-files` 照样认得——索引里的条目只是被标了 skip-worktree。
    合成仓库上验过两种写法。
    """
    rel = path.relative_to(repo) if path.is_absolute() else path
    done = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--error-unmatch", str(rel)],
        capture_output=True, text=True, check=False)
    return done.returncode == 0


def _spec_paths(repo: Path, slug: str) -> tuple[Path, Path]:
    return (repo / SPEC_DIR / f"{slug}.json",
            repo / SPEC_DIR / f"{slug}.xhs.txt")


def wants_auto_push(repo: Path, slug: str, outdir: Path) -> None:
    """三道闸，过不了就 `Skip`（带理由）。"""
    spec, copy_path = _spec_paths(repo, slug)
    if not spec.is_file():
        raise Skip(f"{slug}：没有 {spec}，不知道该发什么")
    if not copy_path.is_file():
        raise Skip(f"{slug}：没有文案 {copy_path}")

    # 复用 push_reel 那份读法，别在这儿另解一遍 JSON——「一个数写两处必分叉」。
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from push_reel import push_is_auto  # noqa: PLC0415

    if not push_is_auto(copy_path):
        raise Skip(f"{slug}：spec 里没写 push.auto=true，不自动发"
                   f"（要开：在 {spec.name} 的 push 块里加一行 \"auto\": true）")
    marker = outdir / MARKER
    if tracked(repo, marker):
        # 稀疏检出下这个文件可能不在工作区，读不到内容也要能拦住——
        # **拦住是主要的，时间和运行地址是加餐**。
        try:
            stamp = json.loads(marker.read_text(encoding="utf-8"))
            when = f"{stamp.get('at', '时间未记')}，{stamp.get('run', '地址未记')}"
        except OSError:
            when = "详情在仓库里，这次没检出"
        raise Skip(f"{slug}：已经推过了（{when}），不重复发")


def pick(changed: list[str], repo: Path) -> tuple[str, Path] | None:
    """从这次合并带进来的改动里挑出**唯一**该发的那一条。"""
    picked: list[tuple[str, Path]] = []
    for path in changed:
        try:
            slug, outdir = candidate(path.strip(), repo)
            wants_auto_push(repo, slug, outdir)
        except Skip as why:
            print(f"[跳过] {why}")
            continue
        picked.append((slug, outdir))

    if not picked:
        print("[自动推送] 这次没有该自动发的片子。")
        return None
    if len(picked) > 1:
        names = "、".join(slug for slug, _ in picked)
        print(f"::error::一次带进来 {len(picked)} 条该自动发的片子（{names}），"
              "一条都不发。")
        print("::error::批量自动发微信错一次就是错一片，而消息收不回来——"
              "手动一条一条跑 match-reel mode=push。")
        raise SystemExit(1)
    return picked[0]


def _emit(slug: str, outdir: Path) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    lines = [f"slug={slug}", f"outdir={outdir.as_posix()}", "found=true"]
    print(f"[自动推送] 这次要发：{slug}（{outdir}）")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def record(outdir: Path, run_url: str, now: str) -> Path:
    """发完记一笔。**这就是「已经发过」的唯一判据**，所以它必须进仓库。"""
    marker = outdir / MARKER
    marker.write_text(json.dumps(
        {"at": now, "run": run_url}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"[自动推送] 记下已推送：{marker}")
    return marker


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--changed", nargs="*", default=[],
                    help="这次合并改动的文件（仓库相对路径）")
    ap.add_argument("--record", default="",
                    help="发完之后在这个 outdir 里记一笔")
    ap.add_argument("--run", default="", help="--record：这次运行的地址")
    ap.add_argument("--now", default="", help="--record：时间戳")
    ap.add_argument("--repo", default=".", help="仓库根目录")
    args = ap.parse_args(argv)

    repo = Path(args.repo)
    if args.record:
        record(Path(args.record), args.run, args.now)
        return 0

    found = pick(args.changed, repo)
    if found:
        _emit(*found)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
