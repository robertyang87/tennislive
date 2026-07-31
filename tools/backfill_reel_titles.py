#!/usr/bin/env python3
"""给已经发出去的成片补上 `xiaohongshu.txt`，让它们能被统计对上。

`tools/push_reel.py --stage page` 从现在起会写这个文件（见 `write_posted_title`），
但**之前发的十几条没有**，于是 `platform_stats.index_output()` 一条都索引不到，
后台导出里每条「赛场之上」都落在「未匹配」一节里。

标题不用猜，也不许猜：`copy.html` 里 `<textarea id="title">` 那一格**就是**
发出去的标题（微信通知栏、复制页、这里，三处同一句）。正文同理，取第二个
textarea。**产物自证**，和 `index_output` 拿第一行当标题是同一条规矩。

    python tools/backfill_reel_titles.py --check     # 只报缺哪些，不写
    python tools/backfill_reel_titles.py             # 补齐

已经有 `xiaohongshu.txt` 的一律不碰——那是 push_reel 写的，比这里从 HTML 里
反解出来的更可信。
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

_FIELD = re.compile(r'<textarea id="(title|body)"[^>]*>(.*?)</textarea>', re.S)

POSTED_TITLE_FILE = "xiaohongshu.txt"


def fields_of(copy_html: str) -> dict[str, str]:
    """从复制页里取回标题和正文。取不到就返回缺的那一格，别硬拼。"""
    got = {k: html.unescape(v).strip() for k, v in _FIELD.findall(copy_html)}
    return {k: v for k, v in got.items() if v}


def posted_text(copy_html: str) -> str | None:
    """标题和正文**两格都要拿到**，缺一格就认输，别只写半份。

    第一版把 id 写成了 `copy`（实际是 `body`），于是正文一直匹配不上，
    只把标题写进去——而 `index_output()` 只读第一行，**索引照样能用**，
    产物看起来一切正常。缺了一半却不吭声，正是「兜底出事的时候不吭声」。
    """
    got = fields_of(copy_html)
    if "title" not in got or "body" not in got:
        return None
    return f"{got['title']}\n\n{got['body']}\n"


def find_gaps(root: Path) -> tuple[list[Path], list[tuple[Path, str]]]:
    """返回 (能补的复制页, 补不了的和原因)。

    **两样都要返回。** 只报成功的检查没法证明它真的看过——补不了的那些
    才是要人去看的（复制页格式变了、或者这个目录压根不是成片）。
    """
    ok, blocked = [], []
    for page in sorted(root.rglob("copy.html")):
        if (page.parent / POSTED_TITLE_FILE).is_file():
            continue
        try:
            text = page.read_text(encoding="utf-8")
        except OSError as exc:
            blocked.append((page, f"读不了：{exc}"))
            continue
        if posted_text(text) is None:
            blocked.append((page, '复制页里没有 <textarea id="title">'))
            continue
        ok.append(page)
    return ok, blocked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default="output", type=Path)
    ap.add_argument("--check", action="store_true", help="只报，不写")
    args = ap.parse_args()

    ok, blocked = find_gaps(args.root)
    for page in ok:
        title = fields_of(page.read_text(encoding="utf-8"))["title"]
        dest = page.parent / POSTED_TITLE_FILE
        if not args.check:
            dest.write_text(posted_text(page.read_text(encoding="utf-8")),
                            encoding="utf-8")
        print(f"{'缺' if args.check else '已补'} {dest}\n     {title}")
    for page, why in blocked:
        print(f"补不了 {page}\n     {why}", file=sys.stderr)
    print(f"\n{'缺' if args.check else '补了'} {len(ok)} 份，补不了 {len(blocked)} 份")
    return 1 if (args.check and ok) or blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
