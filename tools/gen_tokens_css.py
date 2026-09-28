#!/usr/bin/env python3
"""把 `src/tennislive/design_tokens.py` 生成成网页用的 tokens.css（每个消费方一份）。

网页（看板、以后的复制页）只写 `var(--tl-…)`，数从这一份 CSS 来；而这份 CSS 的数
又只从 token 模块来——**一个数写两处必分叉**，所以 CSS 是生成物，不是手写的。

内容：与主题无关的 `:root`（圆角、字阶、字体、动效、彩条，**不带 `color-scheme`**）、
钉死主题的 `:root[data-theme="dark|light"]` 两块、按消费方默认主题生成的「没钉死」
那一份（跟随系统：浅色在 `@media` 外面兜底、深色在 `prefers-color-scheme: dark` 里覆盖），最后是
`prefers-reduced-motion` 块。浅色块声明的变量 = 深色块 − 画布专用的
（`DARK_ONLY` 和图表）。

**消费方表 `OUTPUTS`**：每个消费方在这儿认领自己的默认主题，没有缺省值——
「裸 `:root` 上写 `color-scheme: dark`」那种隐含的默认，会把每个链接了它的页面
的浏览器画布都翻成深色（评审 WP0 复核时在 Chromium 里量出来的）。

- `dashboard/tokens.css` → `system`（账号所有者 2026-09-27 Q10：看板跟随系统）

**变量名一律 `--tl-` 前缀**（`design_tokens.css_var()`）。看板 `styles.css` 现有的
变量和 token 的对照（WP1 接 token 时照这张换；右边的值和左边不同的，是**改值**，
要出对比图）：

    styles.css 现在      意思                 接到
    --bg      #06100c    页面底               --tl-background
    --panel   rgba(…)    卡片                 --tl-card
    --panel-2 #10271d    凸起                 --tl-muted          ← 面
    --line    rgba(…)    分隔线               --tl-border
    --text    #f4f8f5    正文                 --tl-foreground
    --muted   #91a99b    次级**字色**          --tl-subtle-foreground（不是 --tl-muted）
    --green / --green-strong  成功／装饰      状态 → --tl-success，装饰 → --tl-primary（评审 3.1）
    --amber / --red / --blue  状态            --tl-warning / --tl-destructive / --tl-info
    --radius  20px       卡片圆角             不在刻度上：卡片 --tl-radius-lg，首屏／面板 --tl-radius-xl

用法：
    python3 tools/gen_tokens_css.py            # 写表里每一份
    python3 tools/gen_tokens_css.py --check    # 只比对，不一致退出 1（CI / 自查用）

判据 `tests/test_design_tokens.py::test_tokens_css是生成物`：表里每一份都必须和
`design_tokens.tokens_css(default=…)` 逐字节相等——改了 token 模块忘了重跑，当场红。
"""

from __future__ import annotations

# design-tokens: enforced
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from tennislive.design_tokens import tokens_css  # noqa: E402

#: 生成物（相对仓库根）→ 这个消费方没钉 `data-theme` 时的默认主题。
OUTPUTS: dict[str, str] = {
    "dashboard/tokens.css": "system",  # Q10：看板跟随系统
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="只比对，不写")
    args = ap.parse_args()

    stale = 0
    for rel, default in OUTPUTS.items():
        path = REPO / rel
        css = tokens_css(default=default)
        if args.check:
            current = path.read_text(encoding="utf-8") if path.exists() else None
            if current != css:
                stale += 1
                print(f"✗ {rel} 和 design_tokens.tokens_css(default={default!r}) 不一致——"
                      "重跑 python3 tools/gen_tokens_css.py")
            else:
                print(f"✓ {rel} 和 token 模块一致（默认 {default}，{len(css)} 字符）")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(css, encoding="utf-8")
        print(f"写了 {rel}（默认 {default}，{len(css)} 字符）")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
