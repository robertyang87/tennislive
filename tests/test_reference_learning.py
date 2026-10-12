import importlib.util
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
from reference_learning import model_learning_instructions


def rule():
    return dict(id='question-evidence', version='1', status='validated',
                roles=['writer'], instruction='TEST_APPROVED_INSTRUCTION',
                applicability='Test fixture only', rollback='Restore baseline',
                evidence=['test://source'], validation=dict(qc_passed=True, outcome_passed=True,
                qc_receipt='test://qc', outcome_receipt='test://outcomes', primary_metric='watch_time',
                observation_window='72h', reviewed_at='2026-09-18'))


def write(root, rows):
    p = root / 'references' / 'learned-rules.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dict(schema_version=1, rules=rows)), encoding='utf-8')


def test_positive_control_and_role_scope(tmp_path):
    write(tmp_path, [rule()])
    assert 'TEST_APPROVED_INSTRUCTION' in model_learning_instructions(tmp_path, 'writer')
    assert model_learning_instructions(tmp_path, 'vision') == ''


@pytest.mark.parametrize('status', ['hypothesis', 'experiment', 'rejected', 'revoked'])
def test_unvalidated_never_enters_prompt(tmp_path, status):
    r = rule()
    r['status'] = status
    write(tmp_path, [r])
    assert model_learning_instructions(tmp_path, 'writer') == ''


@pytest.mark.parametrize('key', ['qc_receipt', 'outcome_receipt', 'primary_metric', 'observation_window', 'reviewed_at'])
def test_missing_receipts_or_protocol_blocks_promotion(tmp_path, key):
    r = rule()
    r['validation'][key] = None
    write(tmp_path, [r])
    assert model_learning_instructions(tmp_path, 'writer') == ''


def test_revocation_and_malformed_registry(tmp_path):
    r = rule()
    write(tmp_path, [r])
    assert model_learning_instructions(tmp_path, 'writer')
    r['status'] = 'revoked'
    write(tmp_path, [r])
    assert model_learning_instructions(tmp_path, 'writer') == ''


@pytest.mark.parametrize('key', ['qc_passed', 'outcome_passed'])
@pytest.mark.parametrize('value', [False, None, 'true', 1])
def test_pass_flags_must_be_actual_true(tmp_path, key, value):
    r = rule()
    r['validation'][key] = value
    write(tmp_path, [r])
    assert model_learning_instructions(tmp_path, 'writer') == ''
    write(tmp_path, [rule(), r])
    assert model_learning_instructions(tmp_path, 'writer') == ''
    p = tmp_path / 'references' / 'learned-rules.json'
    p.write_text('{broken')
    assert model_learning_instructions(tmp_path, 'writer') == ''
