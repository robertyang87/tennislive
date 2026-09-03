"""一个模块里同名的顶层定义不许出现两次（review 路线 ⑥ 第一刀，2026-09-03）。

来路两条，都是真 bug、都不吭声：

- `tools/orchestrate.py` 的 `_surname` 定义了两遍（第 93 / 362 行），后一份静默
  盖掉前一份，两份的缩写规则还不一样
- `tools/build_interview_clip.py` 的 `_bare`：第 793 行那份给切行排断点用
  （转小写、剥标点），第 3673 行那份给比对引文用（剥掉所有非字），**模块加载
  完之后所有调用都拿到后一份**——`_RANK` / `_NO_TAIL` 全是小写词表，于是
  `And` / `The` / `But` 起头的词在断点排序里一律认不出来，英文字幕的断行
  质量悄悄差了一档

ruff 的 F811 拦不住：前一份在被盖掉之前已经被引用过，它就算「用过了」。
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _dupes(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    seen: dict[str, list[int]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            seen.setdefault(node.name, []).append(node.lineno)
    return [f"{path.relative_to(ROOT)}: {name} 定义在 {lines}"
            for name, lines in seen.items() if len(lines) > 1]


def test_同一个模块里顶层定义不许同名两次():
    files = [*sorted((ROOT / "tools").glob("*.py")),
             *sorted((ROOT / "src" / "tennislive").rglob("*.py"))]
    assert len(files) > 50, "主语没了：扫到的文件太少"
    offenders = [line for path in files for line in _dupes(path)]
    assert not offenders, "\n".join(offenders)


def test_判据自己咬得动():
    tree = ast.parse("def f():\n    return 1\n\ndef g():\n    return 2\n\ndef f():\n    return 3\n")
    seen: dict[str, list[int]] = {}
    for node in tree.body:
        seen.setdefault(node.name, []).append(node.lineno)
    assert seen["f"] == [1, 7]
