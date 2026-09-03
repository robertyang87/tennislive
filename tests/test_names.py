"""英文名取姓只有一份出处（`src/tennislive/names.py`，review 路线 ⑥ 第一刀）。"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tennislive.names import surname_en  # noqa: E402


def test_两种形状_全名取末词_缩写名取首词():
    assert surname_en("Alexandra Eala") == "Eala"
    assert surname_en("alex de minaur") == "minaur"
    assert surname_en("Kenin S.") == "Kenin"
    assert surname_en("Gorzny S.") == "Gorzny"
    assert surname_en("Wolf J.J.") == "Wolf"      # 双首字母也是缩写名
    assert surname_en("Bu Y.") == "Bu"
    assert surname_en("单名") == "单名"
    assert surname_en("") == "" and surname_en(None) == ""
    assert surname_en("S.") == "S."               # 只有一个词，没别的可取


def test_三条线的_surname都走同一份():
    """orchestrate / assemble_spec / prepare_alignment 各自的 `_surname` 必须委托
    给 `surname_en`——原来三份各抄一遍，两份对缩写名是错的（`Bu Y.` 取到 `Y.`）。"""
    for name in ("orchestrate", "assemble_spec", "prepare_alignment"):
        src = (ROOT / "tools" / f"{name}.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_surname"]
        assert len(defs) == 1, f"{name}: _surname 定义了 {len(defs)} 次"
        calls = {n.func.id for n in ast.walk(defs[0])
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "surname_en" in calls, f"{name}._surname 没有委托给 surname_en"
