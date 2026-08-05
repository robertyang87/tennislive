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

from build_match_reel import SEG_FADE, segments_straddling_cuts  # noqa: E402


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

    straddling, unchecked, tail_cuts = segments_straddling_cuts(spec, probes)
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
        elif any(t["index"] == index for t in tail_cuts):
            # 溶解的底料跨了切点：多叠进来一个镜头，但只有一两帧、而且是半透明。
            # 和段体跨切点差着量级，所以只提示，不判红。
            hit = next(t for t in tail_cuts if t["index"] == index)
            mark, tail = "~", (f"  溶解底料跨切点 {hit['cuts']}"
                               f"（叠进来那一层 {hit['opacity']:.0%} 起，渐隐）")
        else:
            mark, tail = "✓", ""
        # `source` 只有多源的 spec 才写（采访那条线）。「赛场之上」是单源，
        # 段里根本没有这个键——原来按 `seg['source']` 硬取，于是这个检查器
        # **对整条赛场之上从来没跑起来过**（KeyError 在第一段就炸）。
        # 判据落在 `test_跨切点检查器对单源的赛场之上也要跑得起来`。
        #
        # ⚠️ **`narration` 是同一个坑的第二半，而它躲过了那次修。** 冷开场和
        # 现场声那几段**故意不配旁白**（`shang-rublev` 第 1 段、
        # `zhang-ostapenko` 第 1 段、`chwalinska-gibson` 第 1 段都是），
        # 段里就没有这个键。2026-08-05 才炸出来——因为那条测试取的是
        # **排序第一条**单源 spec，`chwalinska-gibson` 一加进来就排到了最前面，
        # 而它的第 1 段正好是无旁白的冷开场。**在那之前它一直碰巧取到有旁白的。**
        # 「碰巧对」和「真的接上了」长得一模一样，而且前者会一直绿。
        said = seg.get("narration") or seg.get("quote") or ""
        if isinstance(said, list):          # `quote` 可以是逐条的列表
            first = said[0]
            said = first.get("text", "") if isinstance(first, dict) else str(first)
        said = said.replace("\n", " ")[:22] or "（无旁白）"
        print(f"  {mark} 第 {index:>2} 段 [{seg.get('source') or '单源'}] "
              f"{seg['start']}–{seg['end']}  {said}{tail}")

    print()
    if tail_cuts:
        print(f"{len(tail_cuts)} 段的**溶解底料**跨了切点（记号 ~）：段尾之后那"
              f"{SEG_FADE}s 是下一个接缝的底，源片在那儿换了镜头，于是溶解里会"
              "多叠进一两帧。窗口切在源片自己的镜头边界上时这很常见，"
              "**不判红**——真看出来了就把 end 往前收几帧。")
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
