"""教材和账号所有者的口味对齐：教的东西不许和闸打架。

账号所有者 2026-09-27：「形成一个通用的规则在做视频前就烂掉，而不是说做了一半又返工」（原话如此，「烂掉」指拦掉）。
挖口味规则那一轮量出来，自动链自己的教材曾经在跟自己的闸打架（钩子教问句开场、
窗口教逐球解说、狠数据候选拿总分差打头、爆冷封面要输家「失落」的那一帧……）。

⚠️ 2026-10-12 模型通道整体移除：起草／窗口／视觉那几份教材和工具一并删了，
钉它们的判据随之删除。这里剩下的钉**还在的机械半截**：狠数据候选的排序与
标注、爆冷封面的情绪键、赛后开麦合同与 L0 闸的一致、口味规则书本身的加载
与点名闸的存在性。"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
REEL_SKILL = ROOT / "skills" / "tennis-reel-production"
INTERVIEW_SKILL = ROOT / "skills" / "tennis-interview-production"
OWNER_TASTE = ROOT / ".claude" / "skills" / "tennis-owner-taste" / "SKILL.md"


def load(name: str):
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _hook_terms():
    return load("taste_preflight").HOOK_TERMS, load("taste_preflight").TOTAL_MARGIN


def test_总分差只进正文_不当钩子候选(monkeypatch):
    sh = load("match_stat_hooks")
    idx = sh.index_stats([("Match", "Points", "Total Points Won", "49% (90/184)", "51% (94/184)")])
    gap = sh.total_points_gap(idx, "甲", "乙")
    assert gap["use"] == sh.BODY_ONLY

    monkeypatch.setattr(sh, "stats", lambda mid: [
        ("Match", "Points", "Total Points Won", "49% (90/184)", "51% (94/184)"),
        ("Match", "Return", "Break Points Converted", "2/5", "3/9")])
    monkeypatch.setattr(sh, "points", lambda mid: [])
    monkeypatch.setattr(sh, "h2h_candidate", lambda mid: None)
    monkeypatch.setattr(sh, "recent_form_candidate", lambda mid: None)
    monkeypatch.setattr(sh, "durations", lambda mid: [])
    cands = sh.collect("x", "甲", "乙")["candidates"]
    assert cands[-1]["label"] == "总分差", "总分差排最后，钩子候选先看关键分"
    assert all(c.get("use") != sh.BODY_ONLY for c in cands[:-1])

    asm = load("assemble_spec")
    text = asm.facts_text(cands)
    line = next(ln for ln in text.split("\n") if "总分差" in ln)
    assert sh.BODY_ONLY_NOTE in line, line
    assert sh.BODY_ONLY_NOTE not in next(ln for ln in text.split("\n") if "破发点" in ln)
    fact = asm.total_points_fact(
        {"a": {"pts_won": 90}, "b": {"pts_won": 94}},
        [{"name": "甲"}, {"name": "乙"}])
    assert "不写进钩子和推送标题" in fact


def test_爆冷封面要输家还在拼的那一帧():
    asm = load("assemble_spec")
    brief = asm.upset_cover_brief(
        [{"name": "甲", "rank": 5}, {"name": "乙", "rank": 90}], [(4, 6), (3, 6)])
    assert brief["preferred_subject"] == "甲"
    assert "仍在拼" in brief["preferred_moment"] and "失落" not in brief["preferred_moment"]


def test_爆冷封面的情绪键是机械枚举值():
    """brief 带的 `preferred_moment_key` 必须是那两个机械枚举值之一：
    「输家还在拼」＝ `loser_fighting`，兜底退赢家庆祝＝ `winner_celebration`。
    （原来还钉视觉模型 prompt 里列的枚举与闸认的那份一致——那个工具已于
    2026-10-12 随模型通道移除，剩下的就是 brief 这一头的键。）"""
    asm = load("assemble_spec")
    brief = asm.upset_cover_brief(
        [{"name": "甲", "rank": 5}, {"name": "乙", "rank": 90}], [(4, 6), (3, 6)])
    assert brief["preferred_moment_key"] == "loser_fighting"
    assert brief["fallback_moment_key"] == "winner_celebration"


def test_赛后开麦的合同和闸说的是同一件事():
    """合同里点名的内容类型要和 L0 的 `REQUESTED_KINDS` 一一对上——从闸推，不维护名单。
    影子基准已随模型通道移除，合同里要写明这一点，不许再暗示有模型在影子那头把关。"""
    skill = (INTERVIEW_SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "新闻发布会、混采区、演播室、远程连线和来源不明均拒绝" not in skill
    gate = load("interview_source_gate")
    for kind in gate.REQUESTED_KINDS:
        assert f"`{kind}`" in skill, f"L0 认 {kind}，合同里没写"
    named = set(re.findall(r"（`([a-z_]+)`）", skill))
    assert named <= set(gate.REQUESTED_KINDS), f"合同点名了 L0 不认的类型：{named - set(gate.REQUESTED_KINDS)}"

    assert "影子基准已随模型通道" in skill


def test_口味规则skill在做视频前就加载():
    text = OWNER_TASTE.read_text(encoding="utf-8")
    head = text.split("---")[1]
    assert re.search(r"^name: tennis-owner-taste$", head, re.M)
    assert "description: 做任何一条视频之前先加载" in head
    for dom in ("## 选题", "## 钩子和标题", "## 封面选图", "## 封面版式", "## 旁白和文案",
                "## 剪辑和节奏", "## 原声和字幕", "## 配音和 TTS", "## 数据和事实口径",
                "## 小红书正文和推送", "## 视觉和品牌", "## 流程", "## 已被取代"):
        assert dom in text, dom
    assert "破发」「抢七」也禁" in text, "09-27 的 O6 要写进去"
    assert "视觉精美且优雅" in text
    # 语料上验证过的六道文案／结构闸已经落在 tools/taste_gates.py：规则书要按规则编号
    # 点到它们、标〔闸〕（不再是〔在途闸〕），并且挂在对应的那条规则上（不是只在图例
    # 里列一遍）；点名的函数是真的由 `test_口味规则里点名的闸都真的存在` 钉住。
    # ⚠️ 不整份禁「〔在途闸〕」：O2+O3 那一包的标记在它自己合进来之前照旧合法
    for rule_id in ("hook-key-moment-and-result", "hook-no-jargon-or-allusion",
                    "copy-fields-one-source-of-truth", "narration-match-flow-every-set",
                    "post-win-celebration-kept", "story-info-band-per-match"):
        assert f"〔闸〕`{rule_id}`" in text, rule_id
        assert f"〔在途闸〕`{rule_id}`" not in text, f"{rule_id} 已经合进来了，〔在途闸〕要改成〔闸〕"
    # O2+O3 封面认人＋睁眼（`face-eye-checks` 那一包）也是在途的闸，挂在「脸要正面」那条上，
    # 别让读的人以为这条只能靠自查
    face_rule = next(ln for ln in text.split("\n") if "pegula-anisimova 318.5s" in ln)
    assert "〔在途闸〕O2+O3" in face_rule or "〔闸〕`precheck_cover_face`" in face_rule, face_rule
    # 「转述」的规则是推出来的，不是原话——规则书要说清它们只做自查
    assert "没有他的原话之前不许做成闸" in text


def test_CLAUDE_md的目录表列着每一个skill():
    """skill 只有 description 进上下文，但**目录表是会话判断该不该加载的地方**——
    新 skill 没登记进去，就等于这份规矩没人去读。"""
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    table = set(re.findall(r"^\| `([a-z0-9-]+)` \|", claude, re.M))
    dirs = {p.parent.name for p in (ROOT / ".claude" / "skills").glob("*/SKILL.md")}
    assert dirs and dirs <= table, f"没登记进 CLAUDE.md 目录表：{sorted(dirs - table)}"
    assert "tools/taste_preflight.py --slug" in claude
    assert (TOOLS / "taste_preflight.py").is_file()


def test_口味规则里点名的闸都真的存在():
    """规则书每条后面写着「由哪道闸执行」——指错比不写更坏：读的人以为有闸兜着，
    就不自查了。凡是标了〔闸〕〔CI〕〔提示词〕的那一段里点名的东西，仓库里都要找得到。"""
    text = OWNER_TASTE.read_text(encoding="utf-8")
    corpus = "\n".join(
        p.read_text(encoding="utf-8", errors="replace")
        for pattern in ("tools/*.py", "src/**/*.py", "tests/*.py")
        for p in ROOT.glob(pattern))
    named = {
        tok
        for m in re.finditer(r"〔(?:闸|CI|提示词)〕([^｜\n]*)", text)
        for tok in re.findall(r"`([^`]+)`", m.group(1))
    }
    assert len(named) >= 60, f"只认出 {len(named)} 个点名，判据失效了"
    missing = []
    for tok in sorted(named):
        if tok.startswith("-"):
            continue                                  # 命令行开关，不是标识符
        if tok.endswith(".py"):
            if not (ROOT / tok).is_file():
                missing.append(tok)
            continue
        if tok.endswith(".md"):
            # 教材在 references/ 下；规则书也会直接点名技能自己的 `SKILL.md`
            if not (list((ROOT / "skills").glob(f"*/references/{tok}"))
                    or list((ROOT / "skills").glob(f"*/{tok}"))):
                missing.append(tok)
            continue
        name = re.split(r"[=(]", tok)[0].split(".")[-1]
        if not re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", corpus):
            missing.append(tok)
    assert not missing, f"规则书里点名了、仓库里找不到：{missing}"
