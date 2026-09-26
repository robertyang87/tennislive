"""文案手艺的三道闸：技战术、复读、句式模子。

来路：账号所有者 2026-09-19 转达读者——「**文案不专业，剪辑也不专业，
技战术也交代不清楚**」。判据和量出来的账在 `tools/reel_craft.py` 的模块
docstring 里。
"""

import copy
import json
import sys
from pathlib import Path

import pytest

# `tools/` 不是包，和 test_match_reel.py 里那几处 `sys.path.insert` 一个道理；
# 这个模块整份都在测 reel_craft，所以提到模块级来插一次。
sys.path.insert(0, str(Path("tools").resolve()))

from reel_craft import (ECHO_LEGACY, ECHO_MAX, MOLD_LEGACY, MOLD_MAX,
                        SHOT_CRAFT_LEGACY, SHOT_MIN_SEGMENTS, SHOT_WORDS,
                        echo_narration_problem, sentence_mold_problem,
                        shot_craft_problem)

SPECS = sorted(Path("specs/reels").glob("*.json"))


def _load(name):
    spec = json.loads(Path(f"specs/reels/{name}.json").read_text(encoding="utf-8"))
    spec.setdefault("slug", name)
    return spec


def _strip_shots(spec):
    out = copy.deepcopy(spec)
    for seg in out["segments"]:
        text = seg.get("narration", "")
        for word in SHOT_WORDS:
            text = text.replace(word, "东西")
        seg["narration"] = text
    return out


# ───────────────────────── ① 技战术 ─────────────────────────

def test_赛场之上的旁白必须说得出球路():
    """68% 的存量一句球路都没有——新片子不许再这样。

    ⚠️ 这条规矩 2026-08-21 就写在 tennis-editorial「⭐ 旁白要有技战术拆解」
    里了，**一个月之后 68% 的片子一句球路都没有**。一条没有判据的规矩拦不住
    下一个会话——这次轮到它自己。
    """
    spec = _load("chung-nagal-davis-cup-2026")
    assert shot_craft_problem(spec) is None, "这条有 3 段球路，不该红"

    naked = _strip_shots(spec)
    assert shot_craft_problem(naked), "一段球路都没有，必须红"

    # 认领口
    claimed = copy.deepcopy(naked)
    claimed["_tactics_why"] = "源片全是远景宽拍，看不出球路"
    assert shot_craft_problem(claimed) is None, "写了 _tactics_why 就该放行"

    # 只管「赛场之上」——网球有故事讲的是人，不是某一球怎么打的
    story = copy.deepcopy(naked)
    story["cover"] = dict(story["cover"], eyebrow="网球有故事")
    assert shot_craft_problem(story) is None, "网球有故事不受这条管"

    # 门槛真的是 2，不是 1
    one = copy.deepcopy(naked)
    one["segments"][3]["narration"] = "他一记反手直线打穿了对手。"
    assert shot_craft_problem(one), f"只有 1 段球路，门槛是 {SHOT_MIN_SEGMENTS}，该红"
    one["segments"][5]["narration"] = "第二个盘点，他上网截击拿下。"
    assert shot_craft_problem(one) is None, "补到 2 段就该放行"


# ───────────────────────── ② 复读 ─────────────────────────

def test_相邻两段旁白不许说同一句话():
    """来路就是 `heide-wawrinka-davis-cup-2026-wg1` 自己。

    第 9、10 段一模一样地说了两遍「海德又拿到四个破发点，瓦林卡四个全救了
    回来」，就这么推上了微信。
    """
    real = _load("heide-wawrinka-davis-cup-2026-wg1")
    assert echo_narration_problem(real), "这条就是来路，不给豁免时必须红"
    assert echo_narration_problem(real, legacy=ECHO_LEGACY) is None, \
        "已发的不重渲，挂进 legacy 就放行"

    spec = _load("chung-nagal-davis-cup-2026")
    assert echo_narration_problem(spec) is None

    dup = copy.deepcopy(spec)
    dup["segments"][5]["narration"] = dup["segments"][4]["narration"]
    assert echo_narration_problem(dup), "一字不差地复制，必须红"


def test_有意的排比不算复读():
    """⚠️ 这个阈值的下界是 `tsitsipas-royer`。

    「第一个，没了。」「第二个，也没了。」相似度正好 0.80——那是**有意的
    排比**，不是复读。阈值再松一档（0.75）就会把它误伤，而一条会误伤合格
    写法的闸，会把人训练成不看它。
    """
    spec = _load("chung-nagal-davis-cup-2026")
    para = copy.deepcopy(spec)
    para["segments"][5]["narration"] = "第一个，没了。"
    para["segments"][6]["narration"] = "第二个，也没了。"
    assert echo_narration_problem(para) is None, \
        f"有意的排比不该被当成复读（阈值 {ECHO_MAX}）"


# ───────────────────────── ③ 句式模子 ─────────────────────────

def test_同一个句式不许在一条片子里反复套():
    """`comeback-five-love-down` 19 段里「N 个破发点」说了 10 遍。"""
    spec = _load("chung-nagal-davis-cup-2026")
    assert sentence_mold_problem(spec), "这条「X 比 Y，谁发球」用了 5 次，该红"
    assert sentence_mold_problem(spec, legacy=MOLD_LEGACY) is None

    clean = copy.deepcopy(spec)
    for index, seg in enumerate(clean["segments"]):
        if seg.get("narration", "").strip():
            seg["narration"] = f"这是第{index}段，讲的是一次反手直线。"
    assert sentence_mold_problem(clean) is None, "没有模子就该放行"

    for index, seg in enumerate(clean["segments"][:9]):
        if seg.get("narration", "").strip():
            seg["narration"] = f"第{index}局他拿到三个破发点，随后一记反手直线得分。"
    assert sentence_mold_problem(clean), f"同一模子超过 {MOLD_MAX} 次必须红"


# ───────────────────── 三张豁免表的自检 ─────────────────────

@pytest.mark.parametrize("name,table,probe", [
    ("SHOT_CRAFT_LEGACY", SHOT_CRAFT_LEGACY, shot_craft_problem),
    ("ECHO_LEGACY", ECHO_LEGACY, echo_narration_problem),
    ("MOLD_LEGACY", MOLD_LEGACY, sentence_mold_problem),
])
def test_三张手艺豁免表只许减不许加且每条都真的存在(name, table, probe):
    """⚠️ **豁免表要自证它豁免的是真的还在违规。**

    名字写错、或者那条片子后来被改好了，它都会变成一盏永远亮着的绿灯——
    而绿灯和「真的守住了」长得一模一样（`_LEGACY_AMBIGUOUS_POINT` 那次的老账）。
    """
    stems = {p.stem for p in SPECS}
    missing = table - stems
    assert not missing, f"{name} 里这些 slug 在 specs/reels 下不存在：{sorted(missing)}"

    stale = set()
    for slug in table:
        spec = _load(slug)
        if probe(spec) is None:
            stale.add(slug)
    assert not stale, (
        f"{sorted(stale)} 已经不违规了（或者名字写错了），从 {name} 里删掉"
        "——这张表只许减不许加")


def test_存量一条都不许被这三道闸拦下():
    """装闸不许把已发的片子变成红的——它们全在豁免表里，一条都不该漏。"""
    bad = []
    for path in SPECS:
        spec = json.loads(path.read_text(encoding="utf-8"))
        spec.setdefault("slug", path.stem)
        for probe, legacy in ((shot_craft_problem, SHOT_CRAFT_LEGACY),
                              (echo_narration_problem, ECHO_LEGACY),
                              (sentence_mold_problem, MOLD_LEGACY)):
            found = probe(spec, legacy=legacy)
            if found:
                bad.append(f"{path.stem}: {found.splitlines()[0]}")
    assert not bad, "存量被拦下了，豁免表漏了：\n  " + "\n  ".join(bad)


# ---------------------------------------------------------------- 「解说说」
# 账号所有者 2026-09-26：「配音的 tts 里不要再说解说说这三个字了」。

from reel_craft import (COMMENTATOR_SAID, COMMENTATOR_SAID_LEGACY,  # noqa: E402
                        commentator_said_problem)


def test_配音里不许出现解说说():
    spec = {"slug": "new-one", "cover": {"narration": "开场"},
            "segments": [{"narration": "这一分打了很久。"},
                         {"narration": "解说说，这一拍太漂亮了。"},
                         {"narration": "转播解说说，他回来了。"}]}
    problem = commentator_said_problem(spec, legacy=COMMENTATOR_SAID_LEGACY)
    assert problem and "第 2 段" in problem and "第 3 段" in problem, problem
    # 封面口播也是 TTS
    spec2 = {"slug": "new-one", "cover": {"narration": "解说说今晚最好"}, "segments": []}
    assert "封面" in (commentator_said_problem(spec2) or "")
    # 原声段（quote）和注解字段不是配音，不管
    ok = {"slug": "new-one", "segments": [
        {"narration": "", "quote": ["解说说什么都行"], "_why": "解说说了 X"}]}
    assert commentator_said_problem(ok) is None


def test_新写的reel配音里一条都没有解说说():
    bad = []
    for path in SPECS:
        if path.name.endswith(".draft.json"):
            continue
        spec = json.loads(path.read_text(encoding="utf-8"))
        spec.setdefault("slug", path.stem)
        problem = commentator_said_problem(spec, legacy=COMMENTATOR_SAID_LEGACY)
        if problem:
            bad.append(f"{path.stem}: {problem.splitlines()[0]}")
    assert not bad, "\n  ".join(["这些 spec 的配音里有「解说说」："] + bad)


def test_解说说豁免表只许减不许加_每条都真的存在且真的还有():
    assert COMMENTATOR_SAID_LEGACY, "豁免表是空的——导入错了会让整条判据静静失效"
    assert len(COMMENTATOR_SAID_LEGACY) <= 19, "只许减不许加（定规矩那天 19 条）"
    for slug in sorted(COMMENTATOR_SAID_LEGACY):
        path = Path(f"specs/reels/{slug}.json")
        assert path.is_file(), f"豁免表里的 {slug} 不存在"
        spec = json.loads(path.read_text(encoding="utf-8"))
        spec["slug"] = "probe-" + slug
        assert commentator_said_problem(spec), (
            f"{slug} 的配音里已经没有「{COMMENTATOR_SAID}」了，从豁免表删掉")


def test_解说说那道闸接在dry_run上():
    import build_match_reel as reel
    spec = _load("medvedev-royer-hangzhou-2026-r2")
    spec["segments"][2]["narration"] = "解说说，" + spec["segments"][2]["narration"]
    with pytest.raises(reel.ReelError, match="解说说"):
        reel._narration_craft(spec)
    reel._narration_craft(_load("medvedev-royer-hangzhou-2026-r2"))
