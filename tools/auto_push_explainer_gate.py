"""解说片「合进 main 就自动发」的四道闸。

和 `auto_push_gate.py`（竖版短片那条线）是同一套形状，**共用它的
`Skip` / `tracked` / `record` / `MARKER`**——那四个函数一个字都不该抄第二遍，
「一个数写两处必分叉」这条在这儿同样成立。

两条线只有两处真的不同：

1. **产物路径**：reel 是 `output/<日期>/reel/<slug>/render.json`，
   解说片是 `output/<日期>/explainer/<slug>/narration.json`
2. ⚠️ **认领的载体**：reel 的 spec 是 `specs/reels/<slug>.json`，一行
   `"auto": true` 就够；**而解说片的脚本活在代码里**（`explainer.py` 的
   `_SCRIPTS` / `_OPENINGS`），没有 per-slug 的 JSON 可写。所以认领改成
   `explainer.py` 里一个显式集合 `AUTO_PUSH_SLUGS`。

   形状没变，变的只是它写在哪儿：**没写就不发，而且要说清怎么开**。
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auto_push_gate import MARKER, Skip, record, tracked  # noqa: E402

# `output/2026-08-04/explainer/nadal-academy/narration.json`
#
# ⚠️ 盯 narration.json 而不是 explainer.mp4：mp4 是二进制大文件，改一个字
# 也会重新落一份，而 narration.json 是渲染器在**成片出来之后**写的那份元数据
# （`generate_explainer_video` 落的，记着 voice / rate）。它变了才说明真的
# 出了一版新的。
_NARRATION_JSON = re.compile(
    r"^output/(\d{4}-\d\d-\d\d)/explainer/([^/]+)/narration\.json$")


def candidate(path: str, repo: Path) -> tuple[str, Path]:
    """一个改动的文件 → (slug, outdir)，不合格就 `Skip`。"""
    match = _NARRATION_JSON.match(path)
    if not match:
        raise Skip(
            f"{path}：不是 output/<日期>/explainer/<slug>/narration.json")
    slug = match.group(2)
    outdir = repo / "output" / match.group(1) / "explainer" / slug
    return slug, outdir


def _claimed(repo: Path) -> frozenset[str]:
    """读 `explainer.py` 里那份显式认领名单。

    ⚠️ 用 import 读，不用正则扫源码——「判断译名改没改对，直接调 player_zh()，
    别看文件内容」是同一条：**要验的是 import 出来的值，不是磁盘上的字样**。
    """
    src = repo / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from tennislive.video.explainer import AUTO_PUSH_SLUGS  # noqa: PLC0415

    return AUTO_PUSH_SLUGS


def wants_auto_push(repo: Path, slug: str, outdir: Path) -> None:
    """三道闸，过不了就 `Skip`（**带理由**）。"""
    claimed = _claimed(repo)
    if slug not in claimed:
        raise Skip(
            f"{slug}：没在 AUTO_PUSH_SLUGS 里认领，不自动发"
            f"（要开：把 \"{slug}\" 加进 src/tennislive/video/explainer.py "
            f"的 AUTO_PUSH_SLUGS）")

    marker = outdir / MARKER
    if tracked(repo, marker):
        # 稀疏检出下这个文件可能不在工作区，读不到内容也要拦得住——
        # **拦住是主要的，时间和运行地址是加餐**。
        raise Skip(f"{slug}：已经推过了（{marker} 在仓库里），不重复发")


def pick(changed: list[str], repo: Path) -> tuple[str, Path] | None:
    """从这次合并带进来的改动里挑出**唯一**该发的那一条。"""
    picked: list[tuple[str, Path]] = []
    for path in changed:
        try:
            slug, outdir = candidate(path, repo)
            wants_auto_push(repo, slug, outdir)
        except Skip as why:
            print(f"[自动推送] 跳过 {why}")
            continue
        picked.append((slug, outdir))

    if not picked:
        print("[自动推送] 这次没有要发的解说片")
        return None
    if len(picked) > 1:
        # ⚠️ 一趟带进来两条就一条都不发。批量自动发微信，错一次就是错一片，
        # 而微信那条消息发出去收不回来。
        names = "、".join(slug for slug, _ in picked)
        print(f"[自动推送] 这一趟带进来 {len(picked)} 条（{names}），"
              f"一条都不发——批量自动发微信，错一次就是错一片。"
              f"要发请走 push-existing 手动推。")
        return None
    return picked[0]


def _emit(slug: str, outdir: Path) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    print(f"[自动推送] 这次要发：{slug}（{outdir}）")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"slug={slug}\noutdir={outdir.as_posix()}\nfound=true\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--changed", nargs="*", default=[])
    ap.add_argument("--record", default="")
    ap.add_argument("--run", default="")
    ap.add_argument("--now", default="")
    ap.add_argument("--repo", default=".")
    args = ap.parse_args(argv)

    if args.record:
        record(Path(args.record), args.run, args.now)
        return 0

    found = pick(args.changed, Path(args.repo))
    if found:
        _emit(*found)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
