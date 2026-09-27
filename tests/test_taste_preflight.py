"""`tools/taste_preflight.py`：开工前口味清单 ＋ main 上已有的口味闸。

账号所有者 2026-09-27：「总结我的口味和品味这种个性化的要求，形成一个通用的规则
在做视频前就拦掉，而不是说做了一半又返工」。

钉五件事：

1. **清单只有一份**——在 `.claude/skills/tennis-owner-taste/SKILL.md`；工具按编号读它，
   每个编号都有字段可贴，多一个少一个都红（两份清单必然分叉）；
2. 字段贴的是**这条 spec 的真字段**，O6（钩子里破发、抢七也不用）和总分差这两样
   把字段里的事实摆出来；
3. **退出码只认红在这一条上的**：全库扫描的 pytest 判据红在别的 slug 上、或者环境缺
   素材，都不算这一条的红；slug 按边界认（草稿 slug 是正式 slug 的前缀）；
4. `--dry-run` 那一趟真的接在 `build_match_reel` 的入口上（跑一次真的子进程）；
5. 口味 CI 判据名单里的每个节点都真的存在——改名了这条会红，而不是静静跑空。
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def _load():
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location("taste_preflight", TOOLS / "taste_preflight.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["taste_preflight"] = module     # dataclass 要在 sys.modules 里找得到模块
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tp():
    return _load()


def test_清单只有一份_每条都有字段(tp):
    items = tp.load_checklist()
    ids = [i.id for i in items]
    assert len(ids) >= 30, f"只读出 {len(ids)} 条清单——SKILL.md 的格式变了？"
    assert len(ids) == len(set(ids)), f"编号重复：{sorted(ids)}"
    assert set(ids) == set(tp.FIELDS), (
        f"SKILL 里有、工具里没有：{sorted(set(ids) - set(tp.FIELDS))}；"
        f"工具里有、SKILL 里没有：{sorted(set(tp.FIELDS) - set(ids))}")
    for item in items:
        assert item.lines <= set(tp.LINES) | {"全部"}, f"{item.id} 的栏目标签不认识：{item.lines}"
        assert "？" in item.question, f"{item.id} 不是一个问题：{item.question}"
        assert item.bad and item.good, f"{item.id} 缺被否或被选的例子"


def test_清单格式认得出也拒得掉(tp):
    ok = "- [ ] **B1** 〔赛场之上〕钩子两行？　❌「甲／乙」　✅「丙／丁」"
    assert [i.id for i in tp.parse_checklist(ok)] == ["B1"]
    # 缺被选的例子、编号不合格式、栏目括号丢了——都不算清单行
    for bad in ("- [ ] **B1** 〔赛场之上〕钩子两行？　❌「甲／乙」",
                "- [ ] **Z9** 〔赛场之上〕钩子？　❌「甲」　✅「乙」",
                "- [ ] **B1** 钩子？　❌「甲」　✅「乙」"):
        assert tp.parse_checklist(bad) == [], bad


def test_清单按栏目挑题(tp):
    items = tp.load_checklist()
    reel = {i.id for i in items if i.applies("赛场之上")}
    story = {i.id for i in items if i.applies("网球有故事")}
    interview = {i.id for i in items if i.applies("赛后开麦")}
    assert "B1" in reel and "B1" not in story and "B1" not in interview
    assert "B10" in story and "B10" not in reel
    assert {"C1", "D1"} <= reel & story & interview, "流程题三条线都要问"


def _ctx(tp, spec, line="赛场之上"):
    return tp.Ctx("demo-slug", None, "reel", line, spec)


def test_字段贴的是这条spec的真字段(tp):
    spec = {
        "cover": {"eyebrow": "赛场之上", "hook": ["首盘两次破发", "全场只多赢一分"],
                  "subject": "乙", "winner": "甲",
                  "matchup": [{"name": "甲", "country": "CHN", "rank": 30},
                              {"name": "乙", "country": "USA", "rank": 90}]},
        "push": {"summary": "甲总分多3分险胜"},
        "segments": [{"start": 10, "end": 50, "narration": ""},
                     {"start": 50, "end": 80, "narration": ""},
                     {"start": 0, "end": 5, "narration": "坐标"}],
    }
    filled = dict((i.id, facts) for i, facts in tp.fill(tp.load_checklist(), _ctx(tp, spec)))
    assert "钩子第 2 行：「全场只多赢一分」" in filled["B1"]
    assert "字段里出现了清单上的词：破发" in filled["B2"], filled["B2"]
    # ⚠️ 钉在「字段里出现了总分说法」那一行上，不钉在整段：推送标题那一行本身就带
    #    「总分多3分」，钉整段的话摆事实那一行删掉了照样绿（反向验证抓到过）
    assert any(f.startswith("字段里出现了总分说法：") and "总分" in f and "多3分" in f
               for f in filled["B4"]), filled["B4"]
    assert any("主体不是赢家" in f for f in filled["B6"]), filled["B6"]
    assert any("70.0 秒" in f for f in filled["B18"]), filled["B18"]

    clean = dict(spec, cover=dict(spec["cover"], hook=["决胜盘一度落后", "甲逆转乙"],
                                  subject="甲"),
                 push={"summary": "甲逆转乙"})
    filled = dict((i.id, facts) for i, facts in tp.fill(tp.load_checklist(), _ctx(tp, clean)))
    assert "钩子里没有清单上的词" in filled["B2"]
    assert "钩子和推送标题里没有总分说法" in filled["B4"]
    assert any("主体赢家" in f for f in filled["B6"])


def test_O6的词表放行他自己用过的说法(tp):
    """赛点、盘点、决胜盘是他接受过的（「首盘错过4个盘点」09-24）；「只差一分」是关键分
    不是总分（「只差一分被拖进决胜盘」他接受过）。摆事实的词表不许把它们也摆出来。"""
    for ok in ("首盘错过4个盘点", "决胜盘一度落后", "三个赛点一个没给", "世界第一发球"):
        assert not tp.HOOK_TERMS.search(ok), ok
    for bad in ("最后一局破发到零", "抢七七比三扳平", "首秀就被逼到4比6", "7分里拿下6分",
                "德约对看台说晚安"):
        assert tp.HOOK_TERMS.search(bad), bad
    for ok in ("只差一分被拖进决胜盘", "最后4分全是她的", "多花了十分钟"):
        assert not tp.TOTAL_MARGIN.search(ok), ok
    for bad in ("全场只多赢一分", "总分多22分", "多9分却输球", "207个小分"):
        assert tp.TOTAL_MARGIN.search(bad), bad


def test_封面图被别的片子用过要列出来(tp, tmp_path, monkeypatch):
    reels = tmp_path / "reels"
    reels.mkdir()
    for slug in ("a", "b"):
        (reels / f"{slug}.json").write_text(json.dumps(
            {"cover": {"portrait": {"image": "assets/reel/same.jpg"}}}), encoding="utf-8")
    monkeypatch.setattr(tp, "REELS", reels)
    monkeypatch.setattr(tp, "INTERVIEWS", tmp_path / "none")
    ctx = tp.Ctx("a", reels / "a.json", "reel", "赛场之上",
                 {"cover": {"portrait": {"image": "assets/reel/same.jpg"}}})
    assert tp._reused_by(ctx) == ["b"]


def test_退出码只认红在这一条上的(tp):
    slug = "zverev-sonego"
    assert tp.classify_failure(slug, "offenders:\n  zverev-sonego: **加粗**") == "fail"
    # 草稿 slug 是正式 slug 的前缀：正式那条红了不许算在草稿头上
    assert tp.classify_failure(slug, "zverev-sonego-us-open-2026-r1: **加粗**") == "other"
    assert tp.classify_failure(slug, "FileNotFoundError: [Errno 2] No such file or "
                                     "directory: '/x/assets/explainer/a.jpg'") == "env"

    xml = """<testsuites><testsuite>
      <testcase classname="tests.test_match_reel" name="test_小红书正文不许用markdown">
        <failure message="assert not offenders">zverev-sonego: 星号</failure></testcase>
      <testcase classname="tests.test_match_reel" name="test_旁白不许用指示语指画面">
        <failure message="bad">wong-lehecka @3: 画面里</failure></testcase>
      <testcase classname="tests.test_match_reel" name="test_收尾要落在一问上不能停在数据上"/>
    </testsuite></testsuites>"""
    tests = tp.TASTE_CI_TESTS[:2] + (
        ("tests/test_match_reel.py::test_收尾要落在一问上不能停在数据上", "收尾一问"),
        ("tests/test_x.py::test_没跑到", "没跑到"))
    got = {g.name.split("（")[0]: g.status for g in tp.parse_junit(slug, xml, tests)}
    assert got == {"小红书正文纯文本": "fail", "旁白不用指示语": "other",
                   "收尾一问": "pass", "没跑到": "env"}, got


def test_口味CI判据的名单都真的存在(tp):
    for node, _label in tp.TASTE_CI_TESTS:
        path, name = node.split("::")
        text = (ROOT / path).read_text(encoding="utf-8")
        assert re.search(rf"^def {re.escape(name)}\(", text, re.M), (
            f"{node} 不存在了——改名了就同步改 TASTE_CI_TESTS，别让预检静静跑空")


def test_dry_run真的接在build_match_reel的入口上(tp, tmp_path):
    """跑一次真的子进程：一份一个源都没有的 spec 必须红，而且报的是入口那句。"""
    spec = tmp_path / "bad-demo.json"
    spec.write_text(json.dumps({"slug": "bad-demo", "cover": {"eyebrow": "赛场之上"},
                                "segments": []}, ensure_ascii=False), encoding="utf-8")
    result = tp.run_reel_dry_run(spec)
    assert result.status == "fail", result.detail
    assert "source" in result.detail, result.detail


def test_主入口的退出码(tp, tmp_path, monkeypatch, capsys):
    reels = tmp_path / "reels"
    reels.mkdir()
    (reels / "demo.json").write_text(json.dumps(
        {"slug": "demo", "cover": {"eyebrow": "赛场之上", "hook": ["甲", "乙"]},
         "segments": []}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(tp, "REELS", reels)
    monkeypatch.setattr(tp, "INTERVIEWS", tmp_path / "none")
    monkeypatch.setattr(tp, "ROOT", ROOT)

    monkeypatch.setattr(tp, "run_reel_dry_run", lambda p: tp.GateResult("dry", "pass"))
    monkeypatch.setattr(tp, "run_ci_tests", lambda slug: [
        tp.GateResult("别人的", "other"), tp.GateResult("环境", "env")])
    assert tp.main(["--slug", "demo"]) == 0, "红在别人身上、环境判不了，都不算这一条的红"
    out = capsys.readouterr().out
    # 但⚪不等于过了：全库判据在第一处红就停，别人的红会遮住这一条——要说出来
    assert "被遮住" in out and "没证明这一条过了" in out, out

    monkeypatch.setattr(tp, "run_ci_tests", lambda slug: [tp.GateResult("我的", "fail")])
    assert tp.main(["--slug", "demo"]) == 1
    assert "红在这一条上" in capsys.readouterr().out

    assert tp.main(["--slug", "no-such-slug"]) == 2
    assert tp.main(["--line", "赛场之上"]) == 0, "spec 还没写：只列清单，不跑闸"
