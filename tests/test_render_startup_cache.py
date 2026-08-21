"""match-reel 启动缓存的回归判据。"""

from pathlib import Path
import re


WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github/workflows/match-reel.yml"
).read_text(encoding="utf-8")


def _step_block(name: str) -> str:
    """按同级 ``- name`` 边界取一个 workflow step。"""
    lines = WORKFLOW.splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.strip() == f"- name: {name}"
    )
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = len(lines)
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if (
            len(line) - len(line.lstrip()) == indent
            and line.strip().startswith("- name:")
        ):
            end = i
            break
    return "\n".join(lines[start:end])


def test_apt缓存要能把后补的字体回写():
    """滚动键让 render 补下的字体成为下一趟可恢复的缓存。"""
    block = _step_block("缓存 apt 包（ffmpeg + 字体，绕开镜像抽风）")
    assert "github.run_id" in block
    key = re.search(r"^\s*key:\s*(.+)$", block, re.M)
    restore = re.search(r"^\s*restore-keys:\s*\|\s*\n\s*(.+)$", block, re.M)
    assert key and restore
    prefix = key.group(1).split("${{ github.run_id }}", 1)[0]
    assert restore.group(1).strip() == prefix.strip()


def test_Chromium缓存可启动就不再跑with_deps():
    """真启动成功后早退；失败仍落回原有安装路径。"""
    block = _step_block("装 Chromium")
    smoke = block.index("playwright.chromium.launch")
    fallback = block.index("python -m playwright install --with-deps chromium")
    assert smoke < fallback
    before_fallback = block[:fallback]
    assert "timeout 20 python" in before_fallback
    assert "exit 0" in before_fallback
    assert "raise SystemExit(1)" in before_fallback
