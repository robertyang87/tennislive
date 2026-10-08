"""Owner 2026-10-04: official-source gaps may use honest native cards.

Verify both model roles receive the shared policy; this is no waiver of QC.
"""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('role', ['deepseek', 'minimax'])
def test_shared_prompt_injects_official_gap_fallback_for_both_roles(monkeypatch, role):
    sys.path.insert(0, str(ROOT / 'tools'))
    import reel_skill

    read = reel_skill._read
    # Only the shared resource is relevant here; sparse workspaces may omit
    # role/reference archives. Keep the real policy resource under test.
    monkeypatch.setattr(reel_skill, '_read', lambda path: read(path) if path == 'SKILL.md' else '')
    monkeypatch.setattr(reel_skill, 'model_learning_instructions', lambda *_: '')
    prompt = reel_skill.model_instructions(role)
    assert 'use official footage only' in prompt
    assert 'Search available official sources first' in prompt
    assert 'native `title_card`' in prompt
    assert 'keep footage gaps in internal production and QC records only' in prompt
    assert 'Do not mention missing official highlights or footage in audience-facing' in prompt
    assert 'explicitly disclosing' not in prompt
    assert 'Never substitute another rally' in prompt
    assert 'does not waive statistics' in prompt
    assert 'full-window audio review, bilingual subtitles, final QC or publication evidence' in prompt
    assert 'including AP, Getty and Jimmie48' in prompt


def test_latest_owner_policy_replaces_missing_footage_blocker_without_qc_waiver():
    taste = (ROOT / '.claude/skills/tennis-owner-taste/SKILL.md').read_text()
    quality = (ROOT / 'docs/forward-production-quality.md').read_text()
    summary = (ROOT / 'CLAUDE.md').read_text()
    assert '缺关键素材先补找，说明文字不能当作' not in taste
    assert '都用官方素材，如果实在缺少关键点就用文字说明' in taste
    assert '原生 `title_card` 与旁白事实说明继续制作' in taste
    assert '不能拿其他回合冒充缺失关键点' in taste
    assert '统计、原声审听、双语字幕、成片质检及发布凭据要求不豁免' in taste
    assert 'native `title_card` and evidence-backed narration' in quality
    assert 'Never substitute another rally' in quality
    assert 'does not waive statistics, audio-review, bilingual-subtitle, final-QC or publication-evidence' in quality
    assert '查过可用官方来源仍缺关键点' in summary
    assert '封面沿用既有正式来源口径' in summary
