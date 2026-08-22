#!/usr/bin/env python3
"""合进 main 之后，判断该不该自动把这条**赛后开麦**推到微信。

**为什么这条线单独要一个（2026-08-14 补的）。** `auto-push-reel` 那条路
**结构性地够不着这条线**：它的路径正则写着
`output/<日期>/reel/<slug>/render.json`，而采访产物存在
`output/interviews/<slug>/` ——**没有日期那一层**。这不是谁漏了，是故意的
（`push_reel.headline` 的注释写着「同一场采访哪天发都可能，目录里没有日期是
**故意的**」）。两个形状对不上，于是这条线一直没有自动推送。

量出来的代价（2026-08-14）：`specs/interviews/` 下 18 条 spec，**0 条**写了
`push.auto`；`output/interviews/` 下 18 个产物目录，`pushed.json` **0 个**。
也就是说这条线的每一次推送都得人合完 PR 之后记得回来点一次 dispatch——
**而它是时效最紧的一条**（赛后采访过一夜就没人看了）。

**闸一道都不少，和 reel 那条完全同口径**，因为微信那条消息发出去收不回来：

1. **路径形状**必须是 `output/interviews/<slug>/render.json`
2. spec 里必须显式写 `"push": {"auto": true}` ——**默认关**，
   和 `mixed_fps` / `silent_source` 一个形状：认领这一步把「想清楚了」和
   「凑合一下」分开
3. 这条**没推过**：`<outdir>/pushed.json` 在仓库里就说明发过了。
   查产物，不查信号——「工作流跑过一次」证明不了消息发出去了。
   ⚠️ 查的是 **`git ls-files`，不是 `test -f`**：这个脚本排在
   `git sparse-checkout add` **之前**，`output/` 那一格不在工作区，
   按文件存不存在判**恒为假**，那道闸等于没装
4. **海报在仓库里**：`<outdir>/poster.jpg` 是推送正文的第一屏，没有它这条
   消息只剩两个按钮。见 `wants_auto_push` 里那一段——这条线现在
   **一张海报都没有**，所以它上来就会把所有存量拦下，那是对的
5. 一趟**最多一条**。一次合并带进来两条成片就一条都不发，报出来让人手动。
   批量自动发微信，错一次就是错一片

**共用的部分是 import 来的，不是抄的。** `Skip` / `tracked` / `MARKER` /
`record` 跟哪条线无关，从 `auto_push_gate` 直接拿——「一个数写两处必分叉」。
真正分叉的只有路径形状和 spec 目录，那两样本来就该两条线各写各的。
⚠️ `auto_push_gate.candidate()` 把 reel 的形状写死在函数体里、`pick()` 又
直接调它，所以复用不到 `pick` 那一层；能不能参数化成一份代码见 PR 正文。

用法：

    auto_push_interview_gate.py --changed <改动的文件…>   # 列出该发的那一条
    auto_push_interview_gate.py --slug <slug>             # 手动/被叫醒时只查这一条
    auto_push_interview_gate.py --record <outdir> --run <运行地址>   # 发完记一笔

⚠️ `--slug` 不是绕闸的近路：它只是把「这次改了哪些文件」换成
「就查这一条的 render.json」，**五道闸一道不少**——render 提交是 GITHUB_TOKEN
推的、不触发 on:push（GitHub 防递归），所以 interview-clip 渲完要用
`workflow_dispatch -f slug=…` 把这条工作流叫醒，闸在这儿照样把关。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# **共用的四样，import 不抄。** 它们一个字都不涉及「哪条线」：
# `Skip` 是「跳过要说出为什么」这条约定本身，`tracked` 是稀疏检出下唯一
# 靠得住的存在性判据，`MARKER` 是已推送标记的文件名，`record` 是写它的那一笔。
# 抄第二份的下场是可预见的：改了 reel 那头的标记名，这头静默失配，
# 于是同一条片子被发第二次。
from auto_push_gate import MARKER, Skip, record, tracked  # noqa: E402

# `output/interviews/eala-parks-toronto-2026/render.json`
# ⚠️ **没有日期那一层**，和 reel 的 `output/<日期>/reel/<slug>/` 差的就是这个。
# 两头都锚：`^` 是给读的人看的（`re.match` 本来就从头匹配），**`$` 是干活的
# 那一个**——少了它 `…/render.json.bak` 这类也会中，而 slug 照样解得出来，
# 于是一个备份文件被当成「这条采访渲完了」。`([^/]+)` 也不许放宽成 `(.+)`：
# 那样 `output/interviews/a/b/render.json` 会解出 slug `a/b`。
# **判据宁可窄，不可宽**——扫得太宽的判据不吭声。
_RENDER_JSON = re.compile(r"^output/interviews/([^/]+)/render\.json$")

SPEC_DIR = Path("specs/interviews")


def shanghai_today() -> str:
    """推送标题上印的那个日期（`8.14 赛后开麦 | …`）。

    **这条线的产物目录里没有日期**，所以 `push_reel` 解不出来，必须显式传
    `--date`（那个函数的报错原话就是「产物不按日期分目录的线请显式传
    --date」）。

    ⚠️ **算一次，两处共用。** `--stage page` 和真正发微信那次**各算一遍标题**，
    而 `wait_for_copy_page(expect=title)` 要求两次算出同一句——两步之间跨过
    上海午夜的话，两次 `date +%F` 会给出两个日期，于是复制页会去等一句
    **永远不会出现**的话，等满窗口（60×40s）再静静把按钮摘掉，**run 还是绿的**。
    概率很低，但它的表现是「按钮偶尔没有」，而那正是这个仓库在复制页上
    栽过六次的那个样子。

    ⚠️ 用固定的 UTC+8，不用 `ZoneInfo("Asia/Shanghai")`：中国 1991 年起不再
    实行夏令时，这个偏移是恒定的；而 `ZoneInfo` 要系统的 tzdata，缺了它抛
    `ZoneInfoNotFoundError`——排在最前面的一步抛出一个跟日期毫无关系的错，
    表现就是整条自动推送不发。
    """
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d")


def candidate(path: str, repo: Path) -> tuple[str, Path]:
    """一个改动的文件 → (slug, outdir)，不合格就 `Skip`。"""
    match = _RENDER_JSON.match(path)
    if not match:
        raise Skip(f"{path}：不是 output/interviews/<slug>/render.json")
    slug = match.group(1)
    return slug, repo / "output" / "interviews" / slug


def _spec_paths(repo: Path, slug: str) -> tuple[Path, Path]:
    return (repo / SPEC_DIR / f"{slug}.json",
            repo / SPEC_DIR / f"{slug}.xhs.txt")


def wants_auto_push(repo: Path, slug: str, outdir: Path) -> None:
    """五道闸，过不了就 `Skip`（带理由）。"""
    # **render.json 必须还在仓库里。** 工作流那头已经用 --diff-filter=AM 滤掉了
    # 删除项，这儿再兜一层：被删的旧产物不是新渲完的片子，它的 spec 往往还写着
    # auto:true、目录里又没有 pushed.json——不拦的话会凑成「一次 N 条」把真该
    # 发的一起拦死。用 tracked() 不用 is_file()：稀疏检出下两者分家。
    if not tracked(repo, outdir / "render.json"):
        raise Skip(f"{slug}：{outdir}/render.json 不在仓库里——要么是这次合并"
                   "删掉的旧产物，要么这条采访根本还没 render 过")
    spec, copy_path = _spec_paths(repo, slug)
    if not spec.is_file():
        raise Skip(f"{slug}：没有 {spec}，不知道该发什么")
    if not copy_path.is_file():
        raise Skip(f"{slug}：没有文案 {copy_path}")

    # 复用 push_reel 那份读法，别在这儿另解一遍 JSON——「一个数写两处必分叉」。
    # 惰性 import 和 reel 那条同一个理由：`--record` 只写一个 json，
    # 不该因为 publish 那一串依赖没装就跑不起来。
    from push_reel import POSTER_NAME, push_is_auto  # noqa: PLC0415

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

    # **海报这道闸在这条线上现在会拦下所有存量，那是对的，不是 bug。**
    #
    # 来路（2026-08-13）：`archive-media.yml mode=purge` 用 git filter-repo 从
    # 全史抹掉了 output/ 下所有 jpg（账号所有者认领过的取舍，17 GB → 789 MB）。
    # 量过（2026-08-14）：`git ls-files 'output/interviews/*/poster*'` **零命中**,
    # 18 个产物目录一张海报都不剩。reel 那条线是 122 个目录 122 个都没有——
    # 同一次 purge，两条线一样。
    #
    # **为什么整条不发，而不是发一条没有海报的**：这不是这儿现挑的口径，是
    # 手动那条路早就定了的——`match-reel.yml` 的 push 预检写着
    # `test -f .../poster.jpg || exit 1`。同一个问题两条路给两个答案，就是
    # 「一个数写两处必分叉」的政策版：同一条片子手动推被拦下、自动推却降级
    # 发了出去，而微信那条消息收不回来。
    #
    # ⚠️ **`push_reel.py` 那条软降级不算数。** 它在缺海报时只打一行
    # 「[封面] … 不在」，而那是发之前最后一步的一句 print、这一趟还是绿的
    # ——「没有人会去读一条绿 run 的日志」。而且它拦不住：没有海报就没有
    # `<img>`，`prepare_image_delivery` / `wait_for_images` 两道现成的闸
    # **一道都走不到**。
    #
    # ⚠️ **查 `tracked()` 不查 `is_file()`**，和上面「已经推过」同一个理由，
    # 而且这里更硬：这一步排在 `git sparse-checkout add` **之前**，`output/`
    # 那一格根本不在工作区，按 `is_file()` 判就是**恒为假**——那不是漏发一条，
    # 是**每一条都不发**，整条自动推送静静地死掉。
    # 判据 `test_稀疏检出下海报也要认得出`。
    poster = outdir / POSTER_NAME
    if not tracked(repo, poster):
        raise Skip(
            f"{slug}：{poster} 不在仓库里，不发——推送第一屏就是海报，"
            "没有它这条消息只剩两个按钮，看不出这是谁的采访。\n"
            "        来路：2026-08-13 那次 purge 从全史抹掉了所有 jpg，"
            "purge 之前渲好、之后才推的采访都会撞上这条。\n"
            "        出路：跑一趟 interview-clip mode=cover（push=false）——"
            "它下源片、抽帧、渲海报、删源片，一个 mp4 都不产生，"
            "海报会随那一趟提交进仓库，这条闸自然就过了。")


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
        print("[自动推送] 这次没有该自动发的采访。")
        return None
    if len(picked) > 1:
        names = "、".join(slug for slug, _ in picked)
        print(f"::error::一次带进来 {len(picked)} 条该自动发的采访（{names}），"
              "一条都不发。")
        print("::error::批量自动发微信错一次就是错一片，而消息收不回来——"
              "手动一条一条跑 interview-clip mode=push。")
        raise SystemExit(1)
    return picked[0]


def _emit(slug: str, outdir: Path) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    # `date` 也从这儿出：见 `shanghai_today` 的注释——两步各算一次会在跨午夜时
    # 分叉，而分叉的样子是「复制页按钮偶尔没有」，run 照样绿。
    date = shanghai_today()
    lines = [f"slug={slug}", f"outdir={outdir.as_posix()}",
             f"date={date}", "found=true"]
    print(f"[自动推送] 这次要发：{slug}（{outdir}），标题日期 {date}")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--changed", nargs="*", default=[],
                    help="这次合并改动的文件（仓库相对路径）")
    ap.add_argument("--slug", default="",
                    help="只查这一条（workflow_dispatch 那条路），五道闸照过")
    ap.add_argument("--record", default="",
                    help="发完之后在这个 outdir 里记一笔")
    ap.add_argument("--run", default="", help="--record：这次运行的地址")
    ap.add_argument("--now", default="", help="--record：时间戳")
    ap.add_argument("--repo", default=".", help="仓库根目录")
    args = ap.parse_args(argv)

    repo = Path(args.repo)
    if args.record:
        # 记一笔的写法和 reel 那条**必须一模一样**（同一个 `record`），
        # 否则两条线的 `pushed.json` 会长出两种形状，而读它的是同一段代码。
        record(Path(args.record), args.run, args.now)
        return 0

    changed = args.changed
    if args.slug:
        if args.changed:
            # 两个入口一起给，没有一种读法是对的——宁可当场红。
            print("::error::--slug 和 --changed 不能同时给")
            raise SystemExit(2)
        # 复用 `pick` 那条路：把 slug 折成它的 render.json 路径，
        # `candidate` 解回 slug、`wants_auto_push` 过五道闸——**不另写一条
        # 只属于 dispatch 的判定**，写两处必分叉，而分叉的样子是
        # 「叫醒的那条路少一道闸」。
        changed = [f"output/interviews/{args.slug}/render.json"]

    found = pick(changed, repo)
    if found:
        _emit(*found)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
