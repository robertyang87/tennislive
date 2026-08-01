#!/usr/bin/env python3
"""查一条 reel spec 里有没有哪一段跨过了源片的场景切点。

**为什么要有这个：** 跨切点的那一段中途会换镜头，而换过去的那个镜头里常常是
另一个人。郑钦文那条第一版三处都是这么错的——末屏那句「你定闹钟吗？」压在
对手握拳庆祝的近景上，「往回爬」那句前两秒是对手的背影，巴黎那段最重的
「亚洲的第一枚奥运网球单打金牌」整句落在维基奇身上。渲染一次都没报错。

挑段仍然要靠眼睛看缩略图墙，这个脚本只拦「窗口中途换了镜头而我没看见」。

    PYTHONPATH=tools python3 tools/check_reel_cuts.py \
        specs/reels/zheng-lanlana.json output/2026-08-01/reel/*/probe.json

**合格的也要列出来**（CLAUDE.md：只在成功时出声的检查，没法证明它真的看过），
没查成的源片单独报——probe 没给全时「零命中」和「全合格」长得一模一样。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_match_reel import segments_straddling_cuts  # noqa: E402


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    spec_path, *probe_paths = sys.argv[1:]
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    probes = [json.loads(Path(p).read_text(encoding="utf-8"))
              for p in probe_paths]

    by_url = {p.get("url"): p for p in probes}
    urls = dict(spec.get("sources") or {}) or {"": spec.get("source_url", "")}
    for name, url in sorted(urls.items()):
        probe = by_url.get(url)
        if probe is None:
            print(f"  ?  {name or '(单源)'}  没有对应的 probe.json —— 查不了")
        else:
            print(f"  ·  {name or '(单源)'}  {len(probe.get('scene_cuts') or [])}"
                  f" 个切点，时长 {probe.get('duration', 0):.1f}s")

    straddling, unchecked = segments_straddling_cuts(spec, probes)
    print()
    for index, seg in enumerate(spec["segments"]):
        hit = next((b for b in straddling if b["index"] == index), None)
        why = seg.get("crosses_cut")
        if hit:
            mark, tail = "✗", f"  跨切点 {hit['cuts']}"
        elif seg.get("source", "") in unchecked:
            mark, tail = "?", "  没查"
        elif why:
            mark, tail = "!", f"  显式跨切点：{why}"
        else:
            mark, tail = "✓", ""
        print(f"  {mark} 第 {index:>2} 段 [{seg['source'] or '单源'}] "
              f"{seg['start']}–{seg['end']}  {seg['narration'][:22]}{tail}")

    print()
    if unchecked:
        print(f"没查成的源片：{unchecked}（probe 不全，上面的结论不完整）")
    if straddling:
        print(f"{len(straddling)} 段跨了切点。要么改窗口，"
              f"要么在那一段写 \"crosses_cut\": \"<为什么可以跨>\"。")
        return 1
    print("每一段都待在同一个镜头里。")
    return 0 if not unchecked else 1


if __name__ == "__main__":
    raise SystemExit(main())
