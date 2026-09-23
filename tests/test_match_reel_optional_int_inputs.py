"""手动 probe 只填 home/away 时，`year` 是空串——空串传给 `--year`（`type=int`）
argparse 当场报 `invalid int value: ''`，自动备料那一步红掉、probe 产物一个都不提交
（run 35869102144，putintseva-bucsa-bjk-cup-2026）。

判据：凡是 `assemble_spec.py` 里 `type=int` 的参数，工作流都必须**先判空再追加**，
不许写成无条件的 `--year "${{ … }}" \\`。按 argparse 定义自动推导，不维护名单。
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _int_flags() -> list[str]:
    src = (ROOT / "tools" / "assemble_spec.py").read_text(encoding="utf-8")
    return re.findall(r'add_argument\("(--[a-z-]+)"[^)]*type=int', src)


def test_assemble_spec的整数参数空的就不传():
    flags = _int_flags()
    assert "--year" in flags, "推导不出任何 type=int 参数，判据本身失效了"
    yml = (ROOT / ".github" / "workflows" / "match-reel.yml").read_text(encoding="utf-8")
    bad = [f for f in flags
           if re.search(rf'^\s*{re.escape(f)} "\$\{{\{{ github\.event\.inputs\.[a-z_]+ \}}\}}" \\\s*$',
                        yml, re.M)]
    assert not bad, f"这些整数参数被无条件传给 assemble_spec，空串会让 argparse 报错：{bad}"
