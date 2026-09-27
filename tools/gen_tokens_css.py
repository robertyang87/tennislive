#!/usr/bin/env python3
"""把 `src/tennislive/design_tokens.py` 生成成 `dashboard/tokens.css`。

网页（看板、以后的复制页）只写 `var(--…)`，数从这一份 CSS 来；而这份 CSS 的数
又只从 token 模块来——**一个数写两处必分叉**，所以 CSS 是生成物，不是手写的。

内容：深色 `:root`（颜色角色 + 状态芯片 + 图表 + 彩条 + 阴影 + 圆角 + 字阶 +
字体 + 动效）、浅色 `:root[data-theme="light"]`（只覆盖颜色和阴影）、
`prefers-reduced-motion` 块。

用法：
    python3 tools/gen_tokens_css.py            # 写 dashboard/tokens.css
    python3 tools/gen_tokens_css.py --check    # 只比对，不一致退出 1（CI / 自查用）

判据 `tests/test_design_tokens.py::test_tokens_css_是生成物`：文件必须和
`design_tokens.tokens_css()` 逐字节相等——改了 token 模块忘了重跑，当场红。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from tennislive.design_tokens import tokens_css  # noqa: E402

OUT = REPO / "dashboard" / "tokens.css"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="只比对，不写")
    ap.add_argument("-o", "--output", type=Path, default=OUT)
    args = ap.parse_args()

    css = tokens_css()
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else None
        if current != css:
            print(f"✗ {args.output} 和 design_tokens.tokens_css() 不一致——"
                  "重跑 python3 tools/gen_tokens_css.py")
            return 1
        print(f"✓ {args.output} 和 token 模块一致（{len(css)} 字符）")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(css, encoding="utf-8")
    print(f"写了 {args.output}（{len(css)} 字符）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
