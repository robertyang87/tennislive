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

import ast
import copy
import importlib
import importlib.util
import inspect
import io
import json
import re
import sys
import tokenize
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


def test_预检的词表就是闸的那一份(tp):
    """预检原来自己抄了一份术语和总分差的正则，`ACE` 的边界、「至少/最多」那一刀
    都已经和 `tools/taste_gates.py` 分了叉——摆出来的事实和 `--dry-run` 红的理由对不上。
    现在只从闸那里取。"""
    import taste_gates as gates  # noqa: PLC0415

    assert tp.TOTAL_MARGIN is gates.TOTAL_POINTS
    assert tp.HOOK_TERMS.pattern == gates.hook_terms_regex().pattern
    for text in ("二发Ace破局", "德约对看台说晚安", "至少3分", "多9分却输球", "世界第一发球"):
        assert bool(tp.HOOK_TERMS.search(text)) == bool(gates.jargon_hits(text)), text
        assert bool(tp.TOTAL_MARGIN.search(text)) == bool(gates.TOTAL_POINTS.search(text)), text


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

    # This fixture isolates reporting/exit-code behavior; evidence failures have dedicated tests.
    monkeypatch.setattr(importlib.import_module("winners_ue_gate"), "problem", lambda spec: None)
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


def test_采访的预检也跑口味闸(tp):
    """`build_interview_clip.main()` 第一道是 `check_taste_extra`（总分差、赛点同义反复、
    小红书 markdown）。预检按名字列采访线的闸——漏了它，预检会对一条 `main()`
    当场拦下的采访报全绿。"""
    bad = {"slug": "x-interview", "cover": {"title": ["全场只多赢三分", "「我一直相信自己」"]},
           "push": {"summary": "兹维列夫只多赢三分"}}
    gates = {g.name: g for g in tp.run_interview_checks(bad, "")}
    assert "check_taste_extra" in gates, sorted(gates)
    assert gates["check_taste_extra"].status == "fail"
    assert "总分差" in gates["check_taste_extra"].detail
    good = {**bad, "cover": {"title": ["决胜盘一度落后", "他赢了"]}, "push": {"summary": "他赢了"}}
    gates = {g.name: g for g in tp.run_interview_checks(good, "")}
    assert gates["check_taste_extra"].status == "pass"
    gates = {g.name: g for g in tp.run_interview_checks(good, "**加粗**的正文")}
    assert gates["check_taste_extra"].status == "fail", "小红书正文那一面也要跑到"


# ————————————————— 推断出来的规则：只自查，永不做成闸 —————————————————
# 账号所有者 2026-09-27 选定：SKILL 里「转述」来的规则（没有他的原话——从他挑了哪一个、
# 怎么改的里推出来，或者只有会话转述；例：C4「被否后给 3～4 个候选并排」）只当提醒。
#
# ⚠️ 判据分三层，因为**只查编号是挡不住的**（review 当场复现过）：在途的
# `wp/taste-gates-verify-rest` 在 `tools/taste_gates_extra.py` 里写了
# `peng_shuai_problem`，按「彭帅」拦、接进 `spec_taste_extra` 的硬名单、`validate_spec`
# 吃这张名单——一个编号都没写，老判据照样绿。所以：
#
# 1. 编号（名义）：规则编号不许进闸的名单、登记表、工作流；
# 2. 特征词（换了名也换不掉的字）：每条推断规则一行正则，代码里（去掉注释和
#    docstring）出现了就红——除了译名表、预检自己，和第 3 层真跑过的口味闸模块；
# 3. 行为：拿一条过得了闸的真 spec，把特征词和一个同形的中性词各注进去一遍，
#    过 `validate_spec`、`enforce_spec_wording`、口味闸模块的每个 `*_taste_extra`
#    入口——**硬的那一半必须一模一样**。只报（soft）可以不一样：只报不是闸。

_TRANSCRIBED = re.compile(r"转述[：「（]")      # 规则的来源写成「转述」；「不拿旁白转述。」不算
_GATE_MARKS = ("〔闸〕", "〔CI〕", "〔在途闸〕")
#: 闸住在这些地方：代码、数据里的豁免表／登记表、工作流、喂模型的生产教材。
#: taste_preflight 自己不写死编号（从 SKILL 读），它只列提醒。
_REGISTRY_DIRS = ("tools", "src", "data", ".github", "skills")

#: 每条推断规则一行特征词：要是有人把它做成闸，闸里必然写着这几个字——编号可以换名，
#: 规则本身的字换不掉。新加一条推断规则不在这里给特征词，下面那条测试会红。
_INFERRED_SIGNATURES: dict[str, re.Pattern] = {
    "peng-shuai-not-mentioned": re.compile(r"彭帅|Peng\s*Shuai|Shuai\s*Peng", re.I),
    # 「局差」单独一个词是通用的网球统计标签（评审 09-27 nit：以后哪个统计卡写个「局差」
    # 就会被误报成「推断规则做成了闸」）；闸要拦门槛，必然带着比较和数
    "compilation-thresholds": re.compile(r"局数落差|局差\s*(?:[≥>]=?|不少于|至少)\s*[\d四]"),
    "rework-offer-candidates-side-by-side": re.compile(
        r"并排候选|候选并排|[3三]\s*[～~–-]\s*[4四]\s*个(?:并排)?候选"),
}
#: 特征词自己的对照：通用的网球词不许命中（命中就是拿一个天天出现的词当特征，
#: 迟早误报在不相干的 PR 上）。
_GENERIC_TENNIS_WORDS = ("局差", "局差 +3", "局差：2", "盘差", "候选", "并排", "两个候选",
                         "破发", "抢七", "李娜", "郑钦文", "张帅")
#: 出现特征词也不是闸的文件：译名表（「彭帅」是一个要译对的名字）、预检（只列提醒）。
_SIGNATURE_OK = frozenset({"src/tennislive/zh/players.py", "tools/taste_preflight.py"})
#: 口味闸的公共入口住在这里：特征词可以在（只报的那一半要用），因为第 3 层把这个模块
#: 每个 `*_taste_extra` 入口都真跑一遍。模块还不存在（在途分支没合进来）就跳过。
_PROBED_MODULES = {"tools/taste_gates_extra.py": "taste_gates_extra"}
_CODE_GLOBS = ("tools/**/*.py", "src/**/*.py", "tools/**/*.sh",
               ".github/**/*.yml", ".github/**/*.yaml")
#: 第 3 层：推断规则里写得成一句话的那几条，注进去的词和同形的对照词。
#: 另外两条（合集门槛、被否后给并排候选）是选题和流程上的，没有能注进 spec 的字——
#: 它们靠第 1、2 层。
_INFERRED_PROBES = {"peng-shuai-not-mentioned": ("彭帅", "李娜")}
#: 底稿按顺序试，用第一条（注进对照词之后）过得了闸的——以后哪道新闸红了其中一条老 spec，
#: 顺到下一条，而不是让这条测试红在那道闸不相干的 PR 上（评审 09-27 nit）。三条全红才红。
#: 第一条 `test_quote的at超出段长在dry_run就红` 也钉着它原样过 `validate_spec`；
#: 稀疏检出要带上 `assets/reel/<slug>.jpg`（`validate_spec` 查封面大图在不在）。
_PROBE_REELS = tuple(ROOT / "specs" / "reels" / f"{s}.json" for s in (
    "cobolli-tien-laver-cup-2026", "alcaraz-fritz-laver-cup-2026", "mensik-nakashima-laver-cup-2026"))
_PROBE_INTERVIEW = ROOT / "specs" / "interviews" / "tien-cobolli-laver-cup-2026-interview.json"


def _rule_blocks(text: str) -> list[str]:
    """SKILL 规则正文里的一条条规则：`- **标题**…` 起，连着缩进两格的续行。"""
    blocks: list[list[str]] = []
    cur: list[str] | None = None
    for ln in text.split("\n"):
        if re.match(r"^- \*\*", ln):
            cur = [ln]
            blocks.append(cur)
        elif cur is not None and ln.startswith("  "):
            cur.append(ln)
        else:
            cur = None
    return ["\n".join(b) for b in blocks]


_DROP = object()


def _prune_inferred(node, tag: str):
    """导出的规则书（比如以后的 learned-rules.json）里标了推断的那一条不算登记——
    它本来就该带着编号待在那儿。剪掉 `inferred: true` 或带推断标记的那一整条。"""
    if isinstance(node, dict):
        if node.get("inferred") is True or any(
                isinstance(v, str) and tag in v for v in node.values()):
            return _DROP
        return {k: v for k, v in ((k, _prune_inferred(v, tag)) for k, v in node.items())
                if v is not _DROP}
    if isinstance(node, list):
        return [v for v in (_prune_inferred(v, tag) for v in node) if v is not _DROP]
    return node


def _registers(path: Path, rid: str, tag: str) -> bool:
    """这个文件是不是把推断规则的编号登记成了闸（名单、豁免表、工作流里的一行）。"""
    raw = path.read_bytes()
    if rid.encode() not in raw:
        return False
    if path.suffix != ".json":
        return True
    try:
        doc = json.loads(raw)
    except ValueError:
        return True
    pruned = _prune_inferred(doc, tag)
    return pruned is not _DROP and rid in json.dumps(pruned, ensure_ascii=False)


def _code_lines(path: Path, text: str) -> list[tuple[int, str]]:
    """去掉注释和 docstring 的代码：写在说明里的「彭帅」不是闸，写在正则和字符串里的才可能是。"""
    if path.suffix != ".py":
        return [(i, ln) for i, ln in enumerate(text.split("\n"), 1)
                if not ln.lstrip().startswith("#")]
    docs = set()
    for node in ast.walk(ast.parse(text)):
        body = getattr(node, "body", None)
        if (isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str)):
            docs.add(body[0].lineno)
    return [(tok.start[0], tok.string)
            for tok in tokenize.generate_tokens(io.StringIO(text).readline)
            if tok.type != tokenize.COMMENT
            and not (tok.type == tokenize.STRING and tok.start[0] in docs)]


def test_推断出来的口味规则永不做成闸(tp):
    text = tp.SKILL.read_text(encoding="utf-8")
    tag = f"〔{tp.INFERRED_TAG}〕`"
    blocks = _rule_blocks(text)
    assert len(blocks) >= 80, f"只切出 {len(blocks)} 条规则，判据失效了"
    # 先逐条查标记：去掉一条的标记时，要红在「来源是转述要标」这一句上，
    # 而不是红在下面的计数上（那样读起来像「格式变了」）
    for block in blocks:
        head = block.split("\n")[0]
        if _TRANSCRIBED.search(head):
            assert tag in block, (
                f"这条规则的来源是「转述」（没有他的原话），要标〔{tp.INFERRED_TAG}〕：{head[:60]}")
        if tag in block:
            hit = [m for m in _GATE_MARKS if m in block]
            assert not hit, f"推断规则挂上了 {hit}——推断永不做成闸：{head[:60]}"

    inferred = tp.parse_inferred(text)
    ids = [r.id for r in inferred]
    assert len(ids) >= 3 and len(set(ids)) == len(ids), f"推断规则读出来是 {ids}——格式变了？"
    assert "rework-offer-candidates-side-by-side" in ids and any(
        "C4" in r.items for r in inferred), "C4「被否后给 3～4 个候选并排」是推断的样板"
    assert set(ids) == set(_INFERRED_SIGNATURES), (
        f"每条推断规则要在 _INFERRED_SIGNATURES 里有一行特征词（只查编号挡不住换了名的闸）："
        f"缺 {sorted(set(ids) - set(_INFERRED_SIGNATURES))}，"
        f"多 {sorted(set(_INFERRED_SIGNATURES) - set(ids))}")

    # 特征词自证：命中它自己那条规则的原文（不然是拿一个规则里根本没有的词当特征）、
    # 不命中通用词（不然会误报在不相干的代码上）
    for rid, sig in _INFERRED_SIGNATURES.items():
        own = [b for b in blocks if f"`{rid}`" in b]
        assert own and sig.search(own[0]), f"`{rid}` 的特征词在它自己那条规则里都找不到：{sig.pattern}"
        generic = [w for w in _GENERIC_TENNIS_WORDS if sig.search(w)]
        assert not generic, f"`{rid}` 的特征词命中了通用网球词 {generic}——收窄：{sig.pattern}"

    # ① 编号
    for rid in ids:
        assert text.count(f"`{rid}`") == 1, (
            f"`{rid}` 在 SKILL 里不止出现在它自己那一条（〔在途闸〕名单、图例都算闸的名单）")
        for node, label in tp.TASTE_CI_TESTS:
            assert rid not in node and rid not in label, f"{rid} 进了 TASTE_CI_TESTS"
        for base in _REGISTRY_DIRS:
            for path in (ROOT / base).rglob("*"):
                if not path.is_file() or path.suffix not in {".py", ".json", ".yml", ".yaml", ".md", ".sh"}:
                    continue
                if path == TOOLS / "taste_preflight.py":
                    continue
                assert not _registers(path, rid, tp.INFERRED_TAG), (
                    f"推断规则 `{rid}` 出现在 {path.relative_to(ROOT)}——推断只自查，永不做成闸")

    # ② 特征词
    hits = []
    for pattern in _CODE_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            rel = path.relative_to(ROOT).as_posix()
            if not path.is_file() or rel in _SIGNATURE_OK or rel in _PROBED_MODULES:
                continue
            body = path.read_text(encoding="utf-8", errors="replace")
            sigs = [(rid, sig) for rid, sig in _INFERRED_SIGNATURES.items() if sig.search(body)]
            for lineno, code in _code_lines(path, body) if sigs else []:
                hits += [f"{rel}:{lineno} `{rid}`：{code.strip()[:50]}"
                         for rid, sig in sigs if sig.search(code)]
    assert not hits, (
        "推断规则的特征词写进了代码——换了名字也是按推断规则拦（推断只自查，永不做成闸）。"
        "要么拿掉，要么让它只报、住进口味闸模块（_PROBED_MODULES，第 3 层会真跑它）：\n  "
        + "\n  ".join(hits))


def _inject(spec: dict, xhs: str, word: str) -> tuple[dict, str]:
    """把 `word` 注进会发出去的几处：最后一段旁白、推送导语、采访字幕、小红书正文。"""
    spec, line = copy.deepcopy(spec), f"{word}那件事。"
    for seg in reversed(spec.get("segments") or []):
        if isinstance(seg, dict) and seg.get("narration"):
            seg["narration"] += line
            break
    push = spec.setdefault("push", {})
    push["lead"] = str(push.get("lead") or "") + line
    if isinstance(spec.get("zh"), list) and spec["zh"]:
        spec["zh"][-1] = str(spec["zh"][-1]) + line
    return spec, f"{xhs}\n{line}"


def _hard_verdicts(reel, word: str, tmp_path: Path, base_path: Path) -> dict[str, object]:
    """每个入口「硬的那一半」：validate_spec／enforce_spec_wording 抛不抛、抛什么；
    口味闸模块每个 `*_taste_extra` 返回的硬名单。注进去的词统一抹成〈词〉再比。"""
    def norm(x):
        return str(x).replace(word, "〈词〉")

    def outcome(call):
        try:
            call()
        except (reel.ReelError, SystemExit) as exc:
            return norm(exc)
        return None

    base = reel.load_spec(base_path)
    spec, xhs = _inject(base, base_path.with_suffix(".xhs.txt").read_text(encoding="utf-8"), word)
    out: dict[str, object] = {
        "validate_spec": outcome(lambda: reel.validate_spec(copy.deepcopy(spec)))}
    where = tmp_path / f"probe-{len(list(tmp_path.iterdir()))}"
    where.mkdir()
    path = where / base_path.name
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    path.with_suffix(".xhs.txt").write_text(xhs, encoding="utf-8")
    out["enforce_spec_wording"] = outcome(lambda: reel.enforce_spec_wording(copy.deepcopy(spec), path))

    interview, ixhs = _inject(json.loads(_PROBE_INTERVIEW.read_text(encoding="utf-8")),
                              _PROBE_INTERVIEW.with_suffix(".xhs.txt").read_text(encoding="utf-8"),
                              word)
    for rel, name in _PROBED_MODULES.items():
        if not (ROOT / rel).is_file():
            continue
        mod = importlib.import_module(name)
        entries = sorted((n, f) for n, f in vars(mod).items()
                         if n.endswith("_taste_extra") and inspect.isfunction(f))
        assert entries, f"{rel} 在 _PROBED_MODULES 里，却一个 `*_taste_extra` 入口都没有——第 3 层跑空了"
        for fname, fn in entries:
            s, x = (interview, ixhs) if "interview" in fname else (spec, xhs)
            positional = [p for p in inspect.signature(fn).parameters.values()
                          if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
            args = (copy.deepcopy(s),) + ((x,) if len(positional) >= 2 else ())
            out[f"{name}.{fname}"] = sorted(norm(h) for h in fn(*args)[0])
    return out


def test_推断规则在行为上也不拦_注进特征词硬闸一个都不变(tp, tmp_path):
    """第 3 层：只报（soft）可以因为特征词多一句，硬的那一半一个字都不许变。

    底稿是 `_PROBE_REELS` 里第一条过得了闸的赛场之上，和 `cobolli-tien` 的赛后开麦。
    对照词和特征词同形（两个字的中国球员名），所以其它闸对两者的反应一样——差出来的
    只能是冲着特征词去的那道闸。"""
    sys.path.insert(0, str(TOOLS))
    import build_match_reel as reel  # noqa: PLC0415

    for rid, (word, neutral) in _INFERRED_PROBES.items():
        base, tried = None, []
        for cand in _PROBE_REELS:
            control = _hard_verdicts(reel, neutral, tmp_path, cand)
            if control["validate_spec"] is None and control["enforce_spec_wording"] is None:
                base = cand
                break
            tried.append(f"{cand.stem}：{control}")
        assert base is not None, (
            f"对照组（注进「{neutral}」）在 _PROBE_REELS 每一条底稿上都过不了闸——补一条过得了的，"
            f"否则这条对照是空的：\n  " + "\n  ".join(tried))
        probed = _hard_verdicts(reel, word, tmp_path, base)
        changed = {k: (control[k], probed[k]) for k in control if control[k] != probed[k]}
        assert not changed, (
            f"推断规则 `{rid}`：注进「{word}」之后硬闸变了（对照「{neutral}」）——"
            f"推断只自查，永不做成闸，要拦就降成只报：{changed}")


def test_预检把推断规则列成提醒_从不进退出码(tp, tmp_path, monkeypatch, capsys):
    inferred = tp.load_inferred()
    c4 = next(r for r in inferred if "C4" in r.items)

    # 没有 spec：只列清单，推断的那几条挂标记、单列成提醒，退出码 0
    assert tp.main(["--line", "赛场之上", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert {"id": c4.id, "rule": c4.title, "items": ["C4"]} in doc["reminders"]
    assert [c["id"] for c in doc["checklist"] if c["inferred"]] == ["C4"]
    assert doc["gates"] is None

    # 有 spec、闸全绿：提醒照列，退出码仍是 0；闸的名单里没有一条推断规则
    reels = tmp_path / "reels"
    reels.mkdir()
    (reels / "demo.json").write_text(json.dumps(
        {"slug": "demo", "cover": {"eyebrow": "赛场之上", "hook": ["甲", "乙"]},
         "segments": []}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(tp, "REELS", reels)
    monkeypatch.setattr(tp, "INTERVIEWS", tmp_path / "none")
    # This fixture isolates reporting/exit-code behavior; evidence failures have dedicated tests.
    monkeypatch.setattr(importlib.import_module("winners_ue_gate"), "problem", lambda spec: None)
    monkeypatch.setattr(tp, "run_reel_dry_run", lambda p: tp.GateResult("dry", "pass"))
    monkeypatch.setattr(tp, "run_ci_tests", lambda slug: [tp.GateResult("ci", "pass")])
    assert tp.main(["--slug", "demo"]) == 0
    out = capsys.readouterr().out
    head, _, tail = out.partition("## main 上已有的口味闸")
    assert f"## 提醒：推断出来的规则（{tp.INFERRED_TAG}" in head
    assert "[C4] " in head and f"〔{tp.INFERRED_TAG}〕" in head.split("[C4] ")[1].split("\n")[0]
    assert all(r.id not in tail for r in inferred), "推断规则不许出现在闸那一段"
    # 图例、头部提到这个标记（后面不跟反引号编号）不许被认成一条规则
    assert tp.parse_inferred(f"标着〔{tp.INFERRED_TAG}〕的是推断\n- **x**：y｜〔{tp.INFERRED_TAG}〕**") == []


def test_采访线预检的闸和出片那一趟是同一份名单(tp):
    """批次 4 复审 nit：`run_interview_checks` 原来手抄一份名字元组，删掉
    `check_score_orientation` 这个文件照样全绿。准绳是 `interview_preflight._spec_gates`
    （它和 `main()`／`render()` 开头那排按 ast 比过）：预检**跑出来**的每一道都要和它对上。"""
    sys.path.insert(0, str(TOOLS))
    import build_interview_clip as bic  # noqa: PLC0415
    import interview_preflight as pf  # noqa: PLC0415

    spec = json.loads(_PROBE_INTERVIEW.read_text(encoding="utf-8"))
    assert spec.get("takeaway"), "对照 spec 要带解读卡，check_takeaway 才会跑"
    ran = [r.name for r in tp.run_interview_checks(spec, "")]
    want = [g.__name__ for g in pf._spec_gates(bic)]
    assert ran[:-1] == want and ran[-1] == "check_interview_copy_wording", (ran, want)


def test_采访线预检跑全了main开头那排spec闸_含封面钩子(tp):
    """`run_interview_checks` 是 `build_interview_clip.main()` 开头那排只读 spec 的闸的
    预演；少一道，预检报绿、render 第 0.2 秒红——`check_cover_hook` 原来就漏了
    （2026-09-27 评审 nit）。判据是行为：`hook_accent` 写错，预检那一行就得红。"""
    spec = json.loads(_PROBE_INTERVIEW.read_text(encoding="utf-8"))
    def hook(s: dict):
        got = {r.name: r for r in tp.run_interview_checks(s, "")}.get("check_cover_hook")
        assert got is not None, "预检没跑 check_cover_hook——main() 开头跑它，预检就得跑"
        return got

    assert hook(spec).status == "pass", "对照组：真 spec 过得了"
    bad = copy.deepcopy(spec)
    bad.setdefault("cover", {})["hook_accent"] = "标题里根本没有这几个字"
    got = hook(bad)
    assert got.status == "fail" and "hook_accent" in got.detail, got
