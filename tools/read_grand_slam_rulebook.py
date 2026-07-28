"""在大满贯规则书正文里查条款，带页码。

为什么要有这个脚本：选题里的规则事实**一律要引正文，不引媒体转述**——而这份
PDF 有两道坎，每次现搓都要重踩一遍：

1. **WebFetch 读不出。** 1.1 MB 的 PDF 是压缩流，抓下来只有字体和流数据，
   小模型看到的是一片二进制，会回你一句「这里面没有关于外卡的内容」。
   那是**空结果不自证**的又一个变种：读不出来 ≠ 没写。
2. **`import pypdf` 在这个环境里直接 panic**（`pyo3_runtime.PanicException`，
   来自 `cryptography` 的 rust 绑定）。pypdf 只在解密 PDF 时才需要
   `cryptography`，把它 stub 掉就能正常抽文本。

踩过之后拿到的东西值这个脚本：媒体说「抽筋不能治」，正文说的是
「**抽筋可以治，但只能在换边和盘间治；不能为它叫医疗暂停；被判定为抽筋却已经
停下来的人，主裁要命令他立即恢复比赛**」——完全是两回事。

用法：

    python3 tools/read_grand_slam_rulebook.py "wild card"
    python3 tools/read_grand_slam_rulebook.py cramp --context 900
    python3 tools/read_grand_slam_rulebook.py --dump out.txt

查不到时会**把总页数和总字数印出来**，好让你分得清「规则里没这条」和
「PDF 没抽出来」——这两件事长得一模一样。
"""

from __future__ import annotations

import argparse
import re
import sys
import types
from pathlib import Path

import requests

URL = "https://www.itftennis.com/media/5986/grand-slam-rulebook-2026-f2.pdf"
CACHE = Path("tools/broll/grand-slam-rulebook-2026.pdf")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def _reader(path: Path):
    # pypdf 只有解密加密 PDF 时才用 cryptography；这个环境里它的 rust 绑定
    # 一 import 就 panic，所以先占位。规则书没有加密，走不到那条路。
    sys.modules.setdefault("cryptography", types.ModuleType("cryptography"))
    from pypdf import PdfReader

    return PdfReader(str(path))


def pages(path: Path | None = None) -> list[str]:
    """规则书每一页的纯文本，索引 0 对应 PDF 第 1 页。"""
    path = path or CACHE
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(URL, headers=UA, timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
    return [p.extract_text() or "" for p in _reader(path).pages]


def find(term: str, context: int = 600, texts: list[str] | None = None) -> list[tuple[int, str]]:
    """命中的 (PDF 页码, 上下文)。页码是 PDF 的页，不是页脚印的那个数。"""
    texts = pages() if texts is None else texts
    out = []
    for i, text in enumerate(texts, start=1):
        flat = " ".join(text.split())
        for m in re.finditer(re.escape(term), flat, re.I):
            s, e = max(0, m.start() - context // 2), min(len(flat), m.end() + context)
            out.append((i, flat[s:e]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("term", nargs="?", help="要查的词，大小写不敏感")
    ap.add_argument("--context", type=int, default=600, help="命中处前后印多少字符")
    ap.add_argument("--max", type=int, default=6, help="最多印几处")
    ap.add_argument("--dump", metavar="FILE", help="把全文写到文件，带页码标记")
    args = ap.parse_args()

    texts = pages()
    if args.dump:
        Path(args.dump).write_text(
            "\n".join(f"\n<<<PAGE {i}>>>\n{t}" for i, t in enumerate(texts, 1)),
            encoding="utf-8")
        print(f"写了 {args.dump}：{len(texts)} 页")
        return

    if not args.term:
        ap.error("要么给一个查询词，要么用 --dump")

    hits = find(args.term, args.context, texts)
    if not hits:
        # 空结果要自证是真空：把抽出来的规模印出来，好分清「规则没写」
        # 和「PDF 没抽出来」。
        chars = sum(len(t) for t in texts)
        print(f"「{args.term}」在正文里 0 处。"
              f"（抽出 {len(texts)} 页 / {chars} 字符——规模正常就说明是真的没有）")
        return

    print(f"「{args.term}」命中 {len(hits)} 处，印前 {min(args.max, len(hits))} 处：")
    for page, snippet in hits[:args.max]:
        print(f"\n--- PDF 第 {page} 页 ---\n{snippet}")


if __name__ == "__main__":
    main()
