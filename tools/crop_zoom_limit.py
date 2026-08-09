#!/usr/bin/env python3
"""crop_zoom 安全上限：把 gea-shapovalov 那次手算的公式沉淀成一次性小工具，
下次遇到同类机位别再重新推一遍。

来路见 CLAUDE.md「转播主机位的宽景，裁不出更紧的景别」——底线后方高机位的
宽景里，两个人几乎占满整幅高度。往里收（crop_zoom > 1）一定会先把近端球员
的脚挤出画面/压进字幕安全区，或者把远端球员的头挤出画面顶部，上限由这两条
约束一起卡死：

    近端最低点不能压进字幕安全区：  (near_bottom_y − y0) / h ≤ safe_limit
    远端最高点不能被挤出画面顶部：  (far_top_y   − y0) / h ≥ top_margin

`y0`（裁切窗口顶部）和 `h`（裁切窗口高度）都是全画幅归一化坐标（0=画面最上，
1=最下）里的自由变量；要 `h` 最小（也就是 `crop_zoom = 1/h` 最大），两条
不等式在最优点同时取等号，解出：

    zoom_max = (safe_limit − top_margin) / (near_bottom_y − far_top_y)

gea-shapovalov 那次实测：near_bottom_y=0.83、far_top_y=0.10、
safe_limit=0.86、top_margin=0.03 → zoom_max = 0.83/0.73 ≈ 1.14，和当时
手算的数一致（见 `test_和gea_shapovalov那次手算的数对得上`）。

用法：从缩略图墙上量出这两个坐标（都是 0~1 归一化空间，拿画面实际高度去除），
跑：

    python tools/crop_zoom_limit.py --near-bottom 0.83 --far-top 0.10

`--safe-limit`/`--top-margin` 默认沿用这次实测的 0.86/0.03（当时是给
「字幕安全区上锚」和「画面顶部留一点余量」定的），画布或字幕版式换了要跟着改，
别当成放之四海皆准的常量。
"""

from __future__ import annotations

import argparse
import sys

DEFAULT_SAFE_LIMIT = 0.86   # 字幕安全区上锚，压过这条线就撞字幕
DEFAULT_TOP_MARGIN = 0.03   # 画面顶部留白，头顶贴边不好看，也容易被裁切误差吃掉


def zoom_limit(near_bottom_y: float, far_top_y: float,
               safe_limit: float = DEFAULT_SAFE_LIMIT,
               top_margin: float = DEFAULT_TOP_MARGIN) -> float:
    """解那两条不等式，返回安全的 crop_zoom 上限（可能小于 1，意味着连裁都不能裁）。"""
    if near_bottom_y <= far_top_y:
        raise ValueError(
            f"near_bottom_y({near_bottom_y}) 应该比 far_top_y({far_top_y}) 大——"
            "近端在下、远端在上，两个坐标像是填反了")
    if safe_limit <= top_margin:
        raise ValueError(f"safe_limit({safe_limit}) 必须大于 top_margin({top_margin})")
    return (safe_limit - top_margin) / (near_bottom_y - far_top_y)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--near-bottom", type=float, required=True,
                     help="近端球员最低点的归一化 y（0=画面最上，1=最下）")
    ap.add_argument("--far-top", type=float, required=True,
                     help="远端球员最高点的归一化 y")
    ap.add_argument("--safe-limit", type=float, default=DEFAULT_SAFE_LIMIT,
                     help=f"字幕安全区上锚，默认 {DEFAULT_SAFE_LIMIT}（gea-shapovalov 那次实测值）")
    ap.add_argument("--top-margin", type=float, default=DEFAULT_TOP_MARGIN,
                     help=f"画面顶部留白，默认 {DEFAULT_TOP_MARGIN}")
    args = ap.parse_args()

    try:
        zmax = zoom_limit(args.near_bottom, args.far_top, args.safe_limit, args.top_margin)
    except ValueError as exc:
        print(f"算不出来：{exc}")
        return 1

    print(f"crop_zoom 安全上限 ≈ {zmax:.2f}")
    if zmax <= 1.0:
        print("  ≤ 1.0——这个机位往里收一定会切人，别写 crop_zoom（留默认 1.0）")
    elif zmax < 1.2:
        print(f"  只能放大 {(zmax - 1) * 100:.0f}%，值不值得为这点差别重渲一轮自己看着办"
              "（gea-shapovalov 那次算出 1.14 之后就没用这个字段）")
    else:
        print(f"  能放大 {(zmax - 1) * 100:.0f}%，写进 spec 的 crop_zoom 别超过这个数")
    return 0


if __name__ == "__main__":
    sys.exit(main())
