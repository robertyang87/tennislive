#!/usr/bin/env python3
"""把两个已经写好、却从没被联用过的工具拼成一份候选爆点时间轴。

- `check_crowd_rise.py --json`：观众声抬起来的时刻（只在 runner 上跑，
  ⚠️ **不许接进 render 或 CI**——账号所有者：「这个默认不要开启，会很慢，
  拖慢出片速度」。这条约束这个脚本原样继承：本脚本自己也不碰源片、不下载、
  只读两份已经算好的 JSON）
- `probe.json` 里的 `scene_cuts` / `point_ends`：写 spec 前 `mode=probe`
  就已经算出来、提交进仓库的，源片渲完就删也不影响这一步

两者各自只解决了一半：一个测声音、一个测画面切点/死球。拼起来才回答
"这条片子哪几秒最强"——目前这一步纯靠人眼看缩略图墙。这个工具只排序，
不判定；真要用哪一秒仍然要回去看画面/听声音。

用法：

    # 先在 runner 上：python tools/check_crowd_rise.py --url ... --json > crowd.json
    python tools/find_hot_moments.py --probe output/<date>/reel/<slug>/probe.json \
        --crowd crowd.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_WINDOW = 1.5   # 秒。crowd hit 和 scene_cut/point_end 差多少还算"同一时刻"


def _nearest(t: float, xs: list[float]) -> tuple[float, float] | None:
    if not xs:
        return None
    x = min(xs, key=lambda v: abs(v - t))
    return x, round(abs(x - t), 2)


def align(crowd_hits: list[float], scene_cuts: list[float], point_ends: list[float],
          window: float = DEFAULT_WINDOW) -> list[dict]:
    """给每个观众声抬升时刻，标出离它最近的场景切点/死球时刻。

    死球时刻（point_end，记分条真实翻牌）比场景切点（scene_cut，只说明镜头
    换了，不确证一分结束没结束）更能确证"这是一分的边界"，所以权重更高：
    两个信号都在 window 秒内命中的排最前。
    """
    out = []
    for t in crowd_hits:
        cut = _nearest(t, scene_cuts)
        end = _nearest(t, point_ends)
        cut_near = cut is not None and cut[1] <= window
        end_near = end is not None and end[1] <= window
        out.append({
            "t": t,
            "nearest_scene_cut": cut[0] if cut else None,
            "scene_cut_delta": cut[1] if cut else None,
            "nearest_point_end": end[0] if end else None,
            "point_end_delta": end[1] if end else None,
            "score": int(cut_near) + int(end_near) * 2,
        })
    out.sort(key=lambda c: (-c["score"], c["t"]))
    return out


def _label(c: dict) -> str:
    bits = [f"{c['t']:7.2f}s"]
    if c["score"] >= 2:
        bits.append("★ 死球时刻也在附近（最可能是一分的边界）")
    elif c["score"] == 1:
        bits.append("镜头切点也在附近")
    else:
        bits.append("只有观众声，没有画面信号印证")
    if c["nearest_point_end"] is not None:
        bits.append(f"死球 {c['nearest_point_end']:.2f}s（差{c['point_end_delta']:.2f}s）")
    if c["nearest_scene_cut"] is not None:
        bits.append(f"切点 {c['nearest_scene_cut']:.2f}s（差{c['scene_cut_delta']:.2f}s）")
    return "  ".join(bits)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--probe", required=True, help="probe.json 路径")
    ap.add_argument("--crowd", required=True, help="check_crowd_rise.py --json 的输出（文件）")
    ap.add_argument("--window", type=float, default=DEFAULT_WINDOW)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    probe = json.loads(Path(args.probe).read_text(encoding="utf-8"))
    crowd = json.loads(Path(args.crowd).read_text(encoding="utf-8"))
    hits = crowd.get("hits") or []
    scene_cuts = probe.get("scene_cuts") or []
    point_ends = probe.get("point_ends") or []

    if not hits:
        print("crowd.json 里没有 hits——先确认门槛卡对了没有（看 check_crowd_rise "
              "自己打出来的能量分布），别直接当成「这条片子没有高光」")
        return 0
    if not scene_cuts and not point_ends:
        print("probe.json 里 scene_cuts 和 point_ends 都是空的——"
              "point_ends 要给 --box 才会算，没给不代表片子没有死球")

    ranked = align(hits, scene_cuts, point_ends, args.window)
    if args.json:
        print(json.dumps(ranked, ensure_ascii=False, indent=2))
        return 0

    print(f"{len(ranked)} 个候选（观众声抬升 × 画面信号对齐，不是判定）：")
    for c in ranked:
        print("  " + _label(c))
    return 0


if __name__ == "__main__":
    sys.exit(main())
