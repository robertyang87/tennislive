"""Consume reviewed learning rules from the production skill, never research drafts."""
from __future__ import annotations

import json
import logging
from pathlib import Path

LOG = logging.getLogger(__name__)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _eligible(rule, role):
    if not isinstance(rule, dict) or rule.get('status') != 'validated':
        return False
    if not all(_text(rule.get(k)) for k in ('id', 'version', 'instruction', 'applicability', 'rollback')):
        return False
    roles = rule.get('roles')
    if not isinstance(roles, list) or role not in roles:
        return False
    evidence = rule.get('evidence')
    if not isinstance(evidence, list) or not evidence or not all(_text(x) for x in evidence):
        return False
    validation = rule.get('validation')
    if not isinstance(validation, dict):
        return False
    return (validation.get('qc_passed') is True
            and validation.get('outcome_passed') is True
            and all(_text(validation.get(k)) for k in
                    ('qc_receipt', 'outcome_receipt', 'primary_metric', 'observation_window', 'reviewed_at')))


def model_learning_instructions(skill_root: Path, role: str) -> str:
    """Return eligible versioned rules; optional/malformed registry cannot change base rules."""
    path = skill_root / 'references' / 'learned-rules.json'
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return ''
    except (OSError, ValueError) as exc:
        LOG.warning('Learning registry unavailable: %s: %s', path, exc)
        return ''
    if not isinstance(raw, dict) or raw.get('schema_version') != 1 or not isinstance(raw.get('rules'), list):
        LOG.warning('Invalid learning registry schema: %s', path)
        return ''
    rules = raw['rules']
    # A duplicate ID may hide a revocation behind an older validated version.
    ids = [r.get('id') for r in rules if isinstance(r, dict) and _text(r.get('id'))]
    selected = [r for r in rules if _eligible(r, role) and ids.count(r['id']) == 1]
    if not selected:
        return ''
    rows = ['\n【已验证的作品学习规则】',
            '仅在适用条件满足时采用。原有事实、品牌、翻译和完整结尾约束优先。',
            '在制作审计记录中保留实际采用的规则ID和版本；不适用则说明原因。']
    for rule in selected:
        rows.extend([f"规则 {rule['id']}@{rule['version']}",
                     f"适用：{rule['applicability']}", rule['instruction'],
                     f"回滚：{rule['rollback']}"])
        LOG.info('Loaded learning rule %s@%s for %s', rule['id'], rule['version'], role)
    return '\n'.join(rows) + '\n'
