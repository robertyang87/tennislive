#!/usr/bin/env python3
"""重新冻结全库超宽子句的断点表（`tests/fixtures/subtitle_hard_cuts.json`）。

**这不是一个日常要跑的工具**，它只在一件事之后跑：**有意改了断行算法，
并且逐条看过全库的 before/after diff**。跑它＝「这些变化我都看过，认了」。

来路（2026-08-31）：我改了 `_best_break` 的分数、只拿四个例子对比过就合并了，
而那次改动在全库范围内**把三条把词劈开**（「本西奇熬了3小时20｜四分钟」）——
是事后手工跑一遍全库 diff 才看见的。`test_断行的硬切不许悄悄挪位置` 就是把那次
手工 diff 变成机器做的；这个脚本是它的另一半（看过之后重新落盘）。

    python3 tools/freeze_subtitle_cuts.py            # 重新冻结
    python3 tools/freeze_subtitle_cuts.py --diff     # 只看会变什么，不写

⚠️ **`--diff` 先跑**：它逐条打印「哪一条子句的断点挪了、挪前挪后各切成什么样」，
外加断点在不在词边界上（`_break_bonus`）。**从词边界挪到非词边界的那几条，
一条都不许放过**——CLAUDE.md 反复写过「孤行好过把词劈开」。

⚠️ **`❌` 只是提示，不是判决**：`_SUB_AFTER` 那张词尾表很粗，所以 bonus==0
不等于真把词劈开。那次实测 7 条挂了 ❌，其中**真劈词的只有 4 条**
（建立／二十四／打出／蒙特利尔），另外 3 条（「北美 ｜ 硬地赛季的状态」这类）
断得其实挺好，只是表认不出来。**每一条都要自己读一遍**，别照着标记数数。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from tennislive.video.explainer import (  # noqa: E402
    _best_break,
    _break_bonus,
    _clause_spans,
    _sub_display,
    _sub_width,
    _SUB_MAX,
    readable,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
TABLE = ROOT / "tests" / "fixtures" / "subtitle_hard_cuts.json"


def current_cuts() -> dict[str, int]:
    """全库每一条超宽子句今天断在第几个字。"""
    cuts: dict[str, int] = {}
    for spec_path in sorted((ROOT / "specs" / "reels").glob("*.json")):
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        for seg in spec.get("segments", []):
            text = seg.get("narration") or ""
            if not text.strip():
                continue
            shown = readable(text)
            for lo, hi in _clause_spans(shown):
                clause = shown[lo:hi]
                if _sub_width(_sub_display(clause)) <= _SUB_MAX:
                    continue
                cuts[clause] = _best_break(clause)
    return cuts


def _split(clause: str, cut: int) -> str:
    edge = "" if _break_bonus(clause, cut) > 0 else "  ⚠️ 非词边界"
    return f"{_sub_display(clause[:cut])} ｜ {_sub_display(clause[cut:])}{edge}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--diff", action="store_true", help="只打印会变什么，不写文件")
    args = ap.parse_args()

    frozen = json.loads(TABLE.read_text(encoding="utf-8")) if TABLE.exists() else {}
    now = current_cuts()

    moved = [(c, frozen[c], now[c]) for c in now if c in frozen and frozen[c] != now[c]]
    added = sorted(c for c in now if c not in frozen)
    gone = sorted(c for c in frozen if c not in now)

    print(f"冻结表 {len(frozen)} 条 ／ 全库现有 {len(now)} 条")
    print(f"断点挪了 {len(moved)} 条 ｜ 新增 {len(added)} 条 ｜ 文案改掉/删掉 {len(gone)} 条")

    for clause, was, now_cut in moved:
        worse = _break_bonus(clause, was) > 0 and _break_bonus(clause, now_cut) <= 0
        print(f"\n  {'❌ 从词边界挪到了非词边界' if worse else '·'}")
        print(f"    旧：{_split(clause, was)}")
        print(f"    新：{_split(clause, now_cut)}")

    if args.diff:
        return 0

    TABLE.parent.mkdir(parents=True, exist_ok=True)
    TABLE.write_text(
        json.dumps(now, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"\n→ 已写入 {TABLE.relative_to(ROOT)}（{len(now)} 条）")
    return 0


if __name__ == "__main__":  # pragma: no cover - 手动跑的工具
    raise SystemExit(main())
