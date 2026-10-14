"""拿两档转写在写 spec 时就查原声窗口（2026-10-12 那条是对着转写用眼睛排、手搓审听包的）。

用的是仓库里真的那份转写（data/source_asr/y9d6IHw0cZk，王曦雨对王欣瑜）和已经过了
render 审听闸的那条 spec——正样本是「真过了闸的」，反样本是在它上面各拆一处。
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import asr_plan  # noqa: E402
import foreground_audio_gate  # noqa: E402

SPEC = ROOT / "specs/reels/wangxiyu-wangxinyu-wuhan-2026-r1.json"
VIDEO = "y9d6IHw0cZk"


@pytest.fixture(scope="module")
def sents():
    if not asr_plan.asr_dir(VIDEO).is_dir():
        pytest.skip("这份 checkout 没有 data/source_asr")
    docs, _sha = asr_plan.load(VIDEO)
    return asr_plan.sentences(docs)


def _spec() -> dict:
    return json.loads(SPEC.read_text(encoding="utf-8"))


def test_过了审听闸的spec一处硬伤都没有(sents):
    hard, _soft = asr_plan.check(_spec(), sents)
    assert hard == []


@pytest.mark.parametrize("break_it, kind", [
    # 第 3 段 12.25–14.45 是「And there it is.」——给它配上中文旁白
    (lambda s: s["segments"][2].update(narration="这一拍打得漂亮。", quote=None), "配了中文旁白"),
    # 把同一段收到句子中间
    (lambda s: s["segments"][2].update(end=13.4), "切断了英文句子"),
    # 第 5 段的第二条字幕删掉：「Needs three tries…」就没人盖了
    (lambda s: s["segments"][4]["quote"].pop(1), "没有中英字幕盖住"),
])
def test_三类审听闸的硬伤写spec时就报(sents, break_it, kind):
    spec = _spec()
    break_it(spec)
    hard, _soft = asr_plan.check(spec, sents)
    assert any(kind in line for line in hard), hard


def test_旁白空当和手排的一致_疑似幻听不算英文(sents):
    got = asr_plan.gaps(sents, 0, 297)
    assert any(a <= 19.7 and b >= 25.0 for a, b in got)        # 第 4 段旁白放的那截
    assert any(a <= 226.4 and b >= 264.0 for a, b in got)      # 第二盘那一大段
    tail = asr_plan.gaps(sents, 365, 424.4, min_gap=5)
    assert tail, "片尾只有 medium.en 低置信编出来的句子，不该把空当吃掉"


def test_生成的审听包过得了真的审听闸(sents, tmp_path):
    spec = _spec()
    _docs, sha = asr_plan.load(VIDEO)
    asr_plan.write_review(spec, VIDEO, sha, root=tmp_path)
    required = foreground_audio_gate.inspect(copy.deepcopy(spec), root=tmp_path)
    assert required, "这条片子留了原声，审听闸应该要求一串双语字幕"
