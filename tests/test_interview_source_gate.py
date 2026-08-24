"""赛后开麦 L0 内容身份契约：不联网的正反向判据。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import interview_source_gate as gate  # noqa: E402


def _item(**extra) -> dict:
    row = {
        "id": "vid1",
        "url": "https://example.test/vid1",
        "title": "Alexander Zverev On-Court Interview | Cincinnati 2026",
        "source": "Cincinnati Open",
    }
    row.update(extra)
    return row


def _formal_spec() -> dict:
    verification = gate.candidate_verification(_item(), verdicts={})
    spec = {
        "slug": "zverev-cincinnati-2026-qf",
        "url": "https://example.test/vid1",
        "requested_content_type": "on_court",
        "interview_kind": "赛后场上采访",
        "source_verification": verification,
        "match": {
            "id": "2026:cincinnati:qf:alexander-zverev",
            "event": "辛辛那提大师赛",
            "round": "四分之一决赛",
            "winner": "兹维列夫",
            "loser": "阿特马内",
            "participants": ["兹维列夫", "阿特马内"],
        },
    }
    return gate.finalize_source_contract(spec)


def _ceremony_item(**extra) -> dict:
    """颁奖典礼致辞的候选素材——`ceremony` 是这道闸认的第二种合法类型，
    不是 `_item()` 那种 on_court 的降级版，所以单独一份 fixture。
    """
    row = {
        "id": "vid-ceremony-1",
        "url": "https://example.test/vid-ceremony-1",
        "title": "Arthur Fils Champion Speech | 2026 Cincinnati Open",
        "source": "Cincinnati Open",
    }
    row.update(extra)
    return row


def _formal_ceremony_spec() -> dict:
    verification = gate.candidate_verification(_ceremony_item(), verdicts={})
    spec = {
        "slug": "fils-cincinnati-2026-final-ceremony",
        "url": "https://example.test/vid-ceremony-1",
        "requested_content_type": "ceremony",
        "interview_kind": "赛后捧杯致辞",
        "source_verification": verification,
        "match": {
            "id": "2026:cincinnati:final:arthur-fils",
            "event": "辛辛那提大师赛",
            "round": "决赛",
            "winner": "菲斯",
            "loser": "蒂亚福",
            "participants": ["菲斯", "蒂亚福"],
        },
    }
    return gate.finalize_source_contract(spec)


def test_未知频道标题写oncourt也只能待复核():
    got = gate.candidate_verification(_item(source="Unknown Uploads"), verdicts={})
    assert got["status"] == "pending" and got["method"] == "needs_visual_review"


def test_注册官方源且标题明确场上采访可进入生产():
    got = gate.candidate_verification(_item(), verdicts={})
    assert got["status"] == "verified"
    assert got["method"] == "official_explicit_oncourt"


def test_WTA集锦片尾含采访但起点未知只能待复核():
    got = gate.candidate_verification(_item(
        source="WTA", tail_interview=True, duration_s=347,
        title="MATCH HIGHLIGHTS | Cincinnati 2026"), verdicts={})
    assert got["status"] == "pending"
    assert got["method"] == "wta_highlight_tail"
    assert "起点" in got["reason"]


def test_人工判成发布会优先级高于标题规则():
    got = gate.candidate_verification(
        _item(), verdicts={"vid1": {"verdict": "press", "by": "reviewer"}})
    assert got["status"] == "rejected" and got["detected_type"] == "press"


def test_正式契约绑定来源与比赛且改字即失效():
    spec = _formal_spec()
    attestation = gate.validate_source_contract(spec)
    assert len(attestation) == 64

    spec["match"]["loser"] = "另一位球员"
    with pytest.raises(gate.SourceContractError, match="attestation_sha256"):
        gate.validate_source_contract(spec)


def test_演播室不能靠重新签名伪装成场上采访():
    spec = _formal_spec()
    spec["source_verification"].update({
        "status": "rejected", "detected_type": "studio", "method": "human_visual_verdict",
    })
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="status.*verified|detected_type"):
        gate.validate_source_contract(spec)


def test_轮次或逐场ID仍是unknown不能签成正式来源():
    spec = _formal_spec()
    spec["match"]["round"] = "unknown"
    spec["match"]["id"] = "2026:cincinnati:unknown:alexander-zverev"
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="占位值|unknown"):
        gate.validate_source_contract(spec)


def test_官方源标题明确颁奖致辞可进入生产():
    """ceremony 不是被这道闸拦下的例外，是它认的第二种合法类型——账号所有者
    原话「颁奖致辞就是赛后开麦场上采访的一种形式而已，都要做」。受信官方
    频道 + 标题明确写着冠军致辞，应该直接给出 verified，不用等人工判词。
    """
    got = gate.candidate_verification(_ceremony_item(), verdicts={})
    assert got["status"] == "verified"
    assert got["method"] == "official_explicit_ceremony"
    assert got["detected_type"] == "ceremony"


def test_人工判成颁奖致辞也能进入生产():
    """标题不满足任何正则时，人工看过画面记进 oncourt_verify.json 同样能让
    ceremony 走到 verified——跟 on_court 的 human_visual_verdict 是同一条路，
    不是只给 on_court 开的后门。"""
    got = gate.candidate_verification(
        _ceremony_item(title="没有任何标题正则能命中的一句话"),
        verdicts={"vid-ceremony-1": {"verdict": "ceremony", "by": "reviewer"}})
    assert got["status"] == "verified"
    assert got["detected_type"] == "ceremony"
    assert got["method"] == "human_visual_verdict"


def test_颁奖致辞的正式契约通过验证且改字即失效():
    spec = _formal_ceremony_spec()
    attestation = gate.validate_source_contract(spec)
    assert len(attestation) == 64

    spec["match"]["loser"] = "另一位球员"
    with pytest.raises(gate.SourceContractError, match="attestation_sha256"):
        gate.validate_source_contract(spec)


def test_ceremony素材不能签成on_court发布():
    """来源被核验成 ceremony，却在 spec 里声明 requested_content_type=on_court——
    这不是同一件事升级／降级，是两种不同的合法类型，混着用要当场报错，
    不能靠重新签名把不匹配的类型盖过去（这条测试特意在改字段**之后**才
    调用 `finalize_source_contract`，模拟"攻击者也会重新签名"，逼判据落在
    detected_type 本身，而不是侥幸靠一个过期的哈希拦下来）。
    """
    verification = gate.candidate_verification(_ceremony_item(), verdicts={})
    spec = {
        "slug": "mismatched-ceremony-as-on-court",
        "url": _ceremony_item()["url"],
        "requested_content_type": "on_court",
        "interview_kind": "赛后场上采访",
        "source_verification": verification,
        "match": {
            "id": "2026:cincinnati:final:arthur-fils",
            "event": "辛辛那提大师赛",
            "round": "决赛",
            "winner": "菲斯",
            "loser": "蒂亚福",
            "participants": ["菲斯", "蒂亚福"],
        },
    }
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="detected_type"):
        gate.validate_source_contract(spec)


def test_on_court素材不能签成ceremony发布():
    """反过来同理：on_court 已核验的素材，不能靠改个字段名和重新签名就冒充
    颁奖致辞。两个方向都要测，只测一个方向拦不住"generalization 只对了一半"。
    """
    verification = gate.candidate_verification(_item(), verdicts={})
    spec = {
        "slug": "mismatched-on-court-as-ceremony",
        "url": _item()["url"],
        "requested_content_type": "ceremony",
        "interview_kind": "赛后捧杯致辞",
        "source_verification": verification,
        "match": {
            "id": "2026:cincinnati:qf:alexander-zverev",
            "event": "辛辛那提大师赛",
            "round": "四分之一决赛",
            "winner": "兹维列夫",
            "loser": "阿特马内",
            "participants": ["兹维列夫", "阿特马内"],
        },
    }
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="detected_type"):
        gate.validate_source_contract(spec)


def test_requested_content_type不在登记表里直接报错():
    """`REQUESTED_KINDS` 只登记了 on_court／ceremony 两种；写第三个值
    （比如发布会 press）不能靠重新签名蒙混过去。"""
    spec = _formal_spec()
    spec["requested_content_type"] = "press"
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="on_court/ceremony 之一"):
        gate.validate_source_contract(spec)
