"""Load the versioned production skill injected into DeepSeek and MiniMax prompts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = ROOT / "skills" / "tennis-reel-production"


def _read(relative: str) -> str:
    path = SKILL_ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(f"missing production skill resource: {path}")
    return path.read_text(encoding="utf-8").strip()


def model_instructions(role: str) -> str:
    """Return the shared contract plus the requested role and promotion gates."""
    if role not in {"deepseek", "minimax"}:
        raise ValueError(f"unsupported reel skill role: {role}")
    shared = _read("SKILL.md")
    reference = _read(f"references/{role}.md")
    gates = _read("references/quality-gates.md")
    return f"\n\n【赛场之上制作 Skill】\n{shared}\n\n{reference}\n\n{gates}\n"
