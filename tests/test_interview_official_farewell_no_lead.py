"""哪几种内容形态可以没有冷开场——L0 的例外表和 L2 的落地闸必须是同一份。"""

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_interview_landed import bilingual_lead_ok
import interview_source_gate as gate

def spec(kind="farewell", status="verified", method="official_explicit_farewell"):
    return {
        "requested_content_type": kind,
        "opening": {"kind": "none"},
        "source_verification": {"status": status, "method": method},
    }

def test_verified_official_farewell_may_skip_separate_lead(tmp_path):
    ok, detail = bilingual_lead_ok(tmp_path / "missing.ass", spec())
    assert ok and "显式例外" in detail

def test_ordinary_interview_still_requires_lead(tmp_path):
    ok, _ = bilingual_lead_ok(tmp_path / "missing.ass", spec(kind="on_court"))
    assert not ok

def test_unverified_farewell_still_requires_lead(tmp_path):
    ok, _ = bilingual_lead_ok(tmp_path / "missing.ass", spec(status="pending"))
    assert not ok


def _walk_on(**kw):
    kw.setdefault("kind", "walk_on")
    kw.setdefault("method", "official_explicit_walk_on")
    return spec(**kw)


def test_赛前出场秀也不用另接冷开场(tmp_path):
    """**出场秀发生在开赛之前，源片里一个回合都没有——冷开场是结构性拿不到的。**

    `build_interview_clip._OPENING_KINDS` 的 `none` 那一行本来就把它写成了合法
    情形（「发布会、演播室专访、**赛前出场秀**」），只有这道 L2 落地闸不认识它。

    ⚠️ 判据钉在 `bilingual_lead_ok` 上，不是只钉那个谓词——2026-09-01
    加 `walk_on` 时 L0 那四处全改了、`check_opening` 也放行了，
    **红的却是这儿**：成片渲完、封面过闸，最后一项报「spec.lead_in.subs 为空」，
    白烧一趟 render。「谓词对了」和「这条线上每一道闸都认它」是两件事。
    """
    ok, detail = bilingual_lead_ok(tmp_path / "missing.ass", _walk_on())
    assert ok and "显式例外" in detail


def test_只有人工目视判定的出场秀仍然要冷开场(tmp_path):
    """**反向：例外只认官方明写的那一种判据，和 farewell／名人堂两支同一个门槛。**

    `APPROVED_METHODS['walk_on']` 里还有 `human_visual_verdict`——那一支能进生产，
    但拿不到这条例外。判据宁可窄不可宽：真出现一条只靠人工判词的出场秀，
    它要在这儿红出来让人显式决定，而不是被一条宽口径悄悄放过。
    """
    ok, _ = bilingual_lead_ok(tmp_path / "missing.ass",
                              _walk_on(method="human_visual_verdict"))
    assert not ok


def test_每种内容形态都要表态能不能没有冷开场():
    """**这张表自己从 `REQUESTED_KINDS` 推，不维护第二份名单。**

    这一条防的正是 2026-09-01 那次漏改：加第四种类型时改了 L0 的四处，
    漏了这一处，而它在 L2 最后一项才报出来。以后再加第五种类型，
    不在 `NO_LEAD_EXCEPTION_METHOD` 里表态就当场红——把「要记得改这儿」
    换成「不表态就红」，这一类漏改才算真的堵住。
    """
    assert set(gate.NO_LEAD_EXCEPTION_METHOD) == set(gate.REQUESTED_KINDS), (
        "有内容形态没在「能不能没有冷开场」这张表里表态："
        f"{set(gate.REQUESTED_KINDS) ^ set(gate.NO_LEAD_EXCEPTION_METHOD)}"
    )
    # 表里写的方法名必须真的是那一类被批准的判据之一，写错一个字母
    # 这条例外就永远为假，而那和「这一类必须有冷开场」长得一模一样。
    for kind, method in gate.NO_LEAD_EXCEPTION_METHOD.items():
        if method is not None:
            assert method in gate.APPROVED_METHODS[kind], (
                f"{kind} 的免冷开场判据 {method} 不在 APPROVED_METHODS[{kind}] 里")
