"""Load the versioned production skill injected into interview model prompts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = ROOT / "skills" / "tennis-interview-production"


def _read(relative: str) -> str:
    path = SKILL_ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(f"missing interview production skill resource: {path}")
    return path.read_text(encoding="utf-8").strip()


def model_instructions(role: str) -> str:
    """Return the shared contract plus the requested role and quality gates."""
    if role not in {"deepseek", "minimax"}:
        raise ValueError(f"unsupported interview skill role: {role}")
    shared = _read("SKILL.md")
    reference = _read(f"references/{role}.md")
    gates = _read("references/quality-gates.md")
    return f"\n\n【赛后开麦制作 Skill】\n{shared}\n\n{reference}\n\n{gates}\n"
