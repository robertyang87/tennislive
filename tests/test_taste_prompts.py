"""喂给模型的教材和账号所有者的口味对齐：提示词不许教闸会拦的东西。

账号所有者 2026-09-27：「形成一个通用的规则在做视频前就拦掉，而不是说做了一半又返工」。
挖口味规则那一轮量出来，**自动链自己的教材在跟自己的闸打架**：

| 教材里写的 | 闸／口径要的 |
|---|---|
| reel `deepseek.md`「Open on a counterintuitive match-specific question」 | 钩子两行＝关键局面＋结果（09-25），不是问句 |
| `draft_segments.SYSTEM`「冷开场 → 坐标」、每段都要旁白 | `cold_open_problem`：第 1 段不许有中文旁白；开场三格中间还有一句落点 |
| `draft_segments.SYSTEM`「不要写『她压线』这种逐球解说」 | `shot_craft_problem`：至少两段写球路 |
| `match_stat_hooks` 把「总分差」当狠数据候选头一个吐出去 | 09-13「不要写总分差距了」、09-19「不要把这个放在封面的钩子上」 |
| `upset_cover_brief` 要输家「失落、落寞」的近景 | 08-15 拍输家拍他在拼，不拍他垮掉 |
| 赛后开麦 `SKILL.md`「新闻发布会……均拒绝」「MiniMax 负责视觉事实」 | L0 认发布会；生产链 08-30 起不再调 MiniMax |

`specs/reels/pending/` 那 126 份自动草稿里 34 份（2026-09-27 按 `TOTAL_MARGIN` 量）钩子在拿总分说事——**教材教什么，
模型就产什么**。这里每一条都钉在「拼出来的那份 prompt」或「代码真实行为」上，
不钉在某个文件的某一行。
"""

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


def test_reel教材不再教反直觉问句开场_改教钩子合同():
    prompt = load("reel_skill").model_instructions("deepseek")
    assert "counterintuitive" not in prompt, "「Open on a counterintuitive question」跟 09-25 的钩子合同打架"
    for phrase in ("Poster `hook` contract", "Line 1 is the key moment", "Line 2 is the result",
                   "破发", "抢七", "total-points margin", "pay off before you ask"):
        assert phrase in prompt, phrase
    # 草稿那一头真的把这份教材拼进去了（查拼出来的 prompt，不查文件）
    draft = load("draft_spec")
    draft.system_prompt.cache_clear()
    assert "Poster `hook` contract" in draft.system_prompt()


def test_教材里被选的钩子自己过得了口味词表():
    """few-shot 里标 Accepted 的钩子是给模型照着学的——它自己要是带术语、带总分差，
    或者一行超过 10 个字，就是在教模型产被否的东西。判据从预检工具的词表推，不另抄。"""
    terms, margin = _hook_terms()
    text = (REEL_SKILL / "references" / "deepseek.md").read_text(encoding="utf-8")
    accepted = re.findall(r"Accepted(?: shape)?: 「([^」]+)」", text)
    assert len(accepted) >= 3, f"few-shot 里只找到 {len(accepted)} 条被选的钩子"
    for hook in accepted:
        assert not terms.search(hook), f"被选的钩子带术语：{hook}"
        assert not margin.search(hook), f"被选的钩子拿总分说事：{hook}"
        lines = hook.split("／")
        assert len(lines) == 2 and all(len(x) <= 10 for x in lines), f"不是两行 ≤10 字：{hook}"
    # 被否的那几条要真的在（没有对照就不是 few-shot）
    assert len(re.findall(r"^- Rejected", text, re.M)) >= 4


def test_推送教材不再拿术语当标题范例():
    draft = load("draft_spec")
    draft.push_system_prompt.cache_clear()
    terms, margin = _hook_terms()
    examples = re.findall(r"像「([^」]+)」", draft._PUSH_RULES)
    assert examples, "推送标题的范例不见了"
    for ex in examples:
        assert not terms.search(ex) and not margin.search(ex), ex


def test_窗口起草教开场三格_不再禁球路():
    ds = load("draft_segments")
    system = ds.SYSTEM
    for phrase in ("开场三格", "冷开场", "narration 写空字符串", "quote", "一句落点",
                   "不许复读封面钩子", "坐标", "至少两段讲清某一球是怎么打的", "字幕里没讲的不编"):
        assert phrase in system, phrase
    assert "她压线" not in system, "「不要写她压线」教的正是 shot_craft_problem 要的那一类"
    assert "quote" in ds.SCHEMA["properties"]["segments"]["items"]["properties"]
    assert "冷开场（最抓人的那一分/赛点/逆转瞬间）→ 坐标" not in system, "中间少了落点那一格"


def test_窗口起草把钩子交给模型_并清掉不合格的原声(capsys):
    ds = load("draft_segments")

    class Chat:
        user = ""

        def ask(self, system, user, **kw):
            Chat.user = user
            return {"segments": [
                {"start": 300.0, "end": 306.0, "narration": "", "quote": "Match point!\n赛点！",
                 "_beat": 0},
                {"start": 10.0, "end": 16.0, "narration": "落点", "quote": "a\nb", "_beat": 0},
                {"start": 20.0, "end": 26.0, "narration": "", "quote": "only one line"},
            ]}

    out = ds.draft_segments(Chat(), captions_text="1.00: hi", cuts=[], beats="b",
                            home="甲", away="乙", hook="决胜盘一度落后／甲逆转乙")
    assert "决胜盘一度落后／甲逆转乙" in Chat.user
    segs = out["segments"]
    # 一元素列表＝一条两行的双语字幕；写成字符串会被按标点切成先后两条单语字幕
    assert segs[0]["quote"] == ["Match point!\n赛点！"] and segs[0]["narration"] == ""
    mr = load("build_match_reel")
    assert mr._quote_cues(segs[0]["quote"]) == ("Match point!\n赛点！",)
    assert "quote" not in segs[1], "同一段不许既有旁白又有原声"
    assert "quote" not in segs[2], "原声要英文一行、中文一行"
    assert "去掉 2 条不合格的 quote" in capsys.readouterr().out


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


def test_reel的MiniMax教材带封面口味对照():
    prompt = load("reel_skill").model_instructions("minimax")
    for phrase in ("Owner-reviewed cover criteria", "both eyes open", "still fighting",
                   "Photograph a losing player"):
        assert phrase in prompt, phrase


def test_赛后开麦的合同和闸说的是同一件事():
    """合同里点名的内容类型要和 L0 的 `REQUESTED_KINDS` 一一对上——从闸推，不维护名单。
    「MiniMax 只在影子基准里」要和代码对上：生产工具里没有谁拿 interview 教材去问 MiniMax。"""
    skill = (INTERVIEW_SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "新闻发布会、混采区、演播室、远程连线和来源不明均拒绝" not in skill
    gate = load("interview_source_gate")
    for kind in gate.REQUESTED_KINDS:
        assert f"`{kind}`" in skill, f"L0 认 {kind}，合同里没写"
    named = set(re.findall(r"（`([a-z_]+)`）", skill))
    assert named <= set(gate.REQUESTED_KINDS), f"合同点名了 L0 不认的类型：{named - set(gate.REQUESTED_KINDS)}"

    assert "MiniMax 只在影子基准里" in skill
    users = [p.name for p in TOOLS.glob("*.py")
             if 'from interview_skill import' in p.read_text(encoding="utf-8")
             and 'model_instructions("minimax")' in p.read_text(encoding="utf-8")]
    assert users == ["benchmark_interview_models.py"], users

    prompt = load("interview_skill").model_instructions("deepseek")
    assert "账号所有者的口味" in prompt and "赛点上他敢放小球／阿尔卡拉斯险胜弗里茨" in prompt
    minimax = load("interview_skill").model_instructions("minimax")
    assert "账号所有者的口味" in minimax and "双眼睁开" in minimax


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
    # 语料上验证过的六道文案／结构闸由另一包实现；规则书要按规则编号点到它们，
    # 并且挂在对应的那条规则上（不是只在图例里列一遍）
    for rule_id in ("hook-key-moment-and-result", "hook-no-jargon-or-allusion",
                    "copy-fields-one-source-of-truth", "narration-match-flow-every-set",
                    "post-win-celebration-kept", "story-info-band-per-match"):
        assert f"〔在途闸〕`{rule_id}`" in text or f"〔闸〕`{rule_id}`" in text, rule_id


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
            if not list((ROOT / "skills").glob(f"*/references/{tok}")):
                missing.append(tok)
            continue
        name = re.split(r"[=(]", tok)[0].split(".")[-1]
        if not re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", corpus):
            missing.append(tok)
    assert not missing, f"规则书里点名了、仓库里找不到：{missing}"
