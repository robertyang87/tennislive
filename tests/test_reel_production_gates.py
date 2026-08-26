from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def load(name: str):
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verified_match_fact永远生成赢家视角比分():
    facts = load("reel_facts")
    fact = facts.verified_match_fact(
        [{"name": "梅德韦杰夫"}, {"name": "小马丁·达姆"}],
        [(5, 7), (3, 6)], "YJMDWfvf")
    assert fact["winner"] == "小马丁·达姆"
    assert fact["winner_result"] == "7-5 6-3"
    assert fact["loser_result"] == "5-7 3-6"
    assert fact["set_scores_home_away"] == [[5, 7], [3, 6]]


def test_render不再让三处一起抄错的比分过关():
    facts = load("reel_facts")
    spec = {
        "_match": {
            "status": "result_verified",
            "participants": ["梅德韦杰夫", "小马丁·达姆"],
            "set_scores_home_away": [[5, 7], [3, 6]],
            "winner": "小马丁·达姆", "loser": "梅德韦杰夫",
            "winner_result": "5-7 3-6",
        },
        "cover": {"winner": "小马丁·达姆", "result": "5-7 3-6"},
    }
    problem = facts.verified_result_problem(spec)
    assert "应为 小马丁·达姆 7-5 6-3 梅德韦杰夫" in problem


def test_visual_gate要求结尾覆盖冷开场且封面选对爆冷输家(tmp_path):
    visual = load("analyze_reel_visuals")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"photo")
    draft = {
        "_match": {"winner": "小马丁·达姆"},
        "_cover_brief": {"preferred_subject": "梅德韦杰夫"},
        "cover": {"portrait": {"image": str(cover)}},
    }
    raw = {
        "cold_open": {"start": 140, "end": 150, "kind": "winner_celebration",
                      "winner_visible": True, "reason": "赢家握拳", "confidence": .95},
        "ending": {"start": 142, "end": 152, "kind": "aftermath",
                   "winner_visible": True, "reason": "握手", "confidence": .94},
        "cover": {"same_match": True, "subject": "小马丁·达姆",
                  "moment": "winner_celebration", "wrong_or_old": False,
                  "reason": "本场", "confidence": .96},
    }
    report, problems = visual.clean_report(raw, draft, 160)
    assert report["status"] == "waiting"
    assert any("完整覆盖" in p for p in problems)
    assert any("封面人物应为 梅德韦杰夫" in p for p in problems)
    assert any("loser_disappointed" in p for p in problems)


def test_visual_gate覆盖全片且保留最后两张收官证据(tmp_path):
    visual = load("analyze_reel_visuals")
    paths = []
    for index in range(9):
        path = tmp_path / f"contact_{index:02d}.jpg"
        path.write_bytes(str(index).encode())
        paths.append(path)
    chosen = visual.select_contact_sheets(paths)
    assert [path.name for path in chosen] == [
        "contact_00.jpg", "contact_03.jpg", "contact_06.jpg",
        "contact_07.jpg", "contact_08.jpg",
    ]


def test_visual_gate十二张样片不能漏掉赛点所在倒数第二张(tmp_path):
    visual = load("analyze_reel_visuals")
    paths = []
    for index in range(12):
        path = tmp_path / f"contact_{index:02d}.jpg"
        path.write_bytes(str(index).encode())
        paths.append(path)
    chosen = visual.select_contact_sheets(paths)
    assert [path.name for path in chosen] == [
        "contact_00.jpg", "contact_04.jpg", "contact_09.jpg",
        "contact_10.jpg", "contact_11.jpg",
    ]


def test_visual_gate理由引用窗口外画面就不能pass(tmp_path):
    visual = load("analyze_reel_visuals")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"photo")
    draft = {
        "_match": {"winner": "菲斯"},
        "_cover_brief": {"preferred_subject": "菲斯"},
        "cover": {"portrait": {"image": str(cover)}},
    }
    raw = {
        "cold_open": {"start": 317.72, "end": 329.84, "kind": "match_point",
                      "winner_visible": True, "reason": "332.5s 才看见握手",
                      "confidence": .9},
        "ending": {"start": 317.5, "end": 333.08, "kind": "aftermath",
                   "winner_visible": True, "reason": "332.5s 完成握手",
                   "confidence": .9},
        "cover": {"same_match": True, "subject": "菲斯",
                  "moment": "winner_celebration", "wrong_or_old": False,
                  "reason": "本场赢家", "confidence": .9},
    }
    report, problems = visual.clean_report(raw, draft, 340)
    assert report["status"] == "waiting"
    assert any("cold_open 理由引用窗口外时间" in problem for problem in problems)


def test_visual_gate把机械错误回传给minimax且最多自修复一次(tmp_path, monkeypatch):
    visual = load("analyze_reel_visuals")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"photo")
    draft = {
        "_match": {"winner": "菲斯"},
        "cover": {"portrait": {"image": str(cover)}},
    }
    invalid = {
        "cold_open": {"start": 317.72, "end": 329.84, "kind": "match_point",
                      "winner_visible": True, "reason": "330.5s 开始庆祝",
                      "confidence": .9},
        "ending": {"start": 317.5, "end": 329.84, "kind": "aftermath",
                   "winner_visible": True, "reason": "332.5s 完成握手",
                   "confidence": .9},
        "cover": {"same_match": True, "subject": "菲斯",
                  "moment": "winner_celebration", "wrong_or_old": False,
                  "reason": "本场赢家", "confidence": .9},
    }
    repaired = {
        **invalid,
        "cold_open": {**invalid["cold_open"], "end": 333.08,
                      "reason": "317.72s 赛点开始，332.5s 完成握手"},
        "ending": {**invalid["ending"], "end": 333.08,
                   "reason": "317.5s 开始收官，332.5s 完成握手"},
    }
    calls = []

    def fake_ask(*args, **kwargs):
        calls.append(kwargs)
        return invalid if len(calls) == 1 else repaired

    monkeypatch.setattr(visual, "ask_minimax", fake_ask)
    report, problems = visual.verified_minimax_report(
        draft, [], cover, {"duration": 340}, "secret")

    assert problems == []
    assert report["status"] == "pass"
    assert report["model_attempts"] == 2
    assert len(calls) == 2
    assert calls[0]["previous"] is None
    assert calls[1]["previous"] == invalid
    assert any("引用窗口外时间" in problem
               for problem in calls[1]["validation_problems"])


def test_visual_gate低置信度属于证据失败不得靠重问刷高(tmp_path, monkeypatch):
    visual = load("analyze_reel_visuals")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"photo")
    draft = {
        "_match": {"winner": "菲斯"},
        "cover": {"portrait": {"image": str(cover)}},
    }
    uncertain = {
        "cold_open": {"start": 317.72, "end": 329.84, "kind": "match_point",
                      "winner_visible": True, "reason": "赛点与庆祝",
                      "confidence": .5},
        "ending": {"start": 317.5, "end": 329.84, "kind": "aftermath",
                   "winner_visible": True, "reason": "完整收官",
                   "confidence": .9},
        "cover": {"same_match": True, "subject": "菲斯",
                  "moment": "winner_celebration", "wrong_or_old": False,
                  "reason": "本场赢家", "confidence": .9},
    }
    calls = []

    def fake_ask(*args, **kwargs):
        calls.append(kwargs)
        return uncertain

    monkeypatch.setattr(visual, "ask_minimax", fake_ask)
    report, problems = visual.verified_minimax_report(
        draft, [], cover, {"duration": 340}, "secret")

    assert report["status"] == "waiting"
    assert report["model_attempts"] == 1
    assert any("置信度" in problem for problem in problems)
    assert len(calls) == 1


def test_visual_story写双语原声冷开场并在末尾完整兑现():
    visual = load("analyze_reel_visuals")
    draft = {
        "editorial": {"question": "这场爆冷，真正的分水岭在哪？"},
        "segments": [
            {"start": 10, "end": 18, "narration": "比赛坐标。"},
            {"start": 50, "end": 60, "narration": "首盘转折。"},
            {"start": 90, "end": 100, "narration": "次盘走势。"},
        ],
    }
    report = {
        "status": "pass",
        "cold_open": {"start": 140, "end": 150, "reason": "赛点与庆祝"},
        "ending": {"start": 139.9, "end": 150.1, "reason": "完整重放"},
        "cover": {},
    }
    out = visual.apply_story(
        draft, report, [(142.0, "What a finish!")],
        [("What a finish!", "不可思议的收官！")])
    assert out["segments"][0]["narration"] == ""
    assert out["segments"][0]["quote"][0]["text"].count("\n") == 1
    assert out["segments"][0]["_ending_payoff_required"] is True
    assert out["segments"][-1]["start"] <= out["segments"][0]["start"]
    assert out["segments"][-1]["end"] >= out["segments"][0]["end"]


def test_英文原声只允许按已核实名单纠正asr人名():
    visual = load("analyze_reel_visuals")
    names = ["Arthur Fils", "Flavio Cobolli"]
    assert visual.english_name_only_edit(
        "It is feast into the final", "It is Fils into the final", names)
    assert visual.english_name_only_edit(
        "It is Fils into the final", "It is Fils into the final", names)
    assert not visual.english_name_only_edit(
        "It is feast into the final", "It is Fils into the semifinal", names)
    assert not visual.english_name_only_edit(
        "It is feast into the final", "It is the final", names)


def test_已核实asr别名只在对应球员确实参赛时确定性纠正():
    visual = load("analyze_reel_visuals")
    source = "It is feast into the final here in Cincinnati."
    assert visual.correct_verified_asr_names(
        source, ["Arthur Fils", "Flavio Cobolli"]
    ) == "It is Fils into the final here in Cincinnati."
    assert visual.correct_verified_asr_names(
        source, ["Jannik Sinner", "Carlos Alcaraz"]
    ) == source


def test_双语字幕调用也实际加载制作skill并纠正核实人名():
    visual = load("analyze_reel_visuals")
    captured = {}

    class FakeChat:
        ready = True

        def ask(self, system, user, *, schema, max_tokens):
            captured["system"] = system
            return {"lines": [{"en": "It is Fils into the final",
                               "zh": "菲斯闯进决赛"}]}

    got = visual.translate_quotes(
        FakeChat(), ["It is feast into the final"],
        player_names=["Arthur Fils", "Flavio Cobolli"])
    assert got == [("It is Fils into the final", "菲斯闯进决赛")]
    assert "tennis-reel-production" in captured["system"]


def _ready_draft(tmp_path: Path) -> dict:
    photo = tmp_path / "cover.jpg"
    photo.write_bytes(b"photo")
    return {
        "_draft": True,
        "slug": "demo-match",
        "source_url": "https://example.test/highlights",
        "_production": {"kind": "orchestrated_reel", "event": "Demo Open",
                        "year": 2026, "round": "第二轮", "court": "Stadium Court",
                        "received_at": datetime.now(timezone.utc).isoformat()},
        "_match": {"status": "result_verified", "flashscore_id": "abc",
                   "participants": ["甲", "乙"], "set_scores_home_away": [[5, 7], [3, 6]],
                   "winner": "乙", "loser": "甲", "winner_result": "7-5 6-3"},
        "_visual_evidence": {"status": "pass", "cover": {"subject": "乙"}},
        "_durations": [["全场", "1:22"]],
        "_hit_data": [{"detail": "乙全场多拿十一分"}],
        "cover": {"matchup": [
            {"name": "甲", "name_en": "Player A", "country": "USA", "rank": 8},
            {"name": "乙", "name_en": "Player B", "country": "USA", "rank": 92}],
            "portrait": {"image": str(photo)}, "winner": "乙", "result": "7-5 6-3"},
        "editorial": {"hook": ["爆冷", "生涯一胜"], "question": "为什么会爆冷？",
                      "thesis": "乙靠关键分拿下比赛。", "beats": ["首盘", "转折", "收官"],
                      "human_context": "乙首次击败前十。", "narration": ["一", "二", "三"]},
        "segments": [
            {"start": 140, "end": 150, "narration": "", "quote": ["Great shot!\n好球！"],
             "_ending_payoff_required": True},
            {"start": 10, "end": 18, "narration": "坐标"},
            {"start": 40, "end": 48, "narration": "首盘"},
            {"start": 80, "end": 88, "narration": "转折"},
            {"start": 140, "end": 150, "narration": "为什么会爆冷？"}],
        "stats": {"a": {"pts_won": 56}, "b": {"pts_won": 67}},
        "push": {"summary": "乙爆冷击败甲", "lead": "乙两盘取胜。", "auto": True},
    }


def test_promote缺视觉证据就只留waiting(tmp_path):
    promote = load("promote_reel_draft")
    draft = _ready_draft(tmp_path)
    draft["_visual_evidence"]["status"] = "waiting"
    assert any("MiniMax" in reason for reason in promote.waiting_reasons(draft))
    with pytest.raises(ValueError, match="MiniMax"):
        promote.promote(draft)


def test_promote拒绝没有新鲜度证据的自动草稿(tmp_path):
    promote = load("promote_reel_draft")
    draft = _ready_draft(tmp_path)
    draft["_production"]["received_at"] = ""
    assert any("received_at" in reason for reason in promote.waiting_reasons(draft))


def test_promote只在最终validate_spec通过后ready(tmp_path, monkeypatch):
    promote = load("promote_reel_draft")
    draft = _ready_draft(tmp_path)
    checked = []
    fake = type("M", (), {"validate_spec": staticmethod(lambda spec: checked.append(spec))})()
    monkeypatch.setitem(sys.modules, "build_match_reel", fake)
    spec = promote.promote(draft)
    assert checked == [spec]
    assert spec["cover"]["result"] == "7-5 6-3"
    assert spec["topbar"]["line2"] == "乙 7-5 6-3 甲"
    assert spec["_production"]["status"] == "ready_for_render"
    assert spec["push"]["auto"] is True


def test_workflow只有正式ready才从probe派发render():
    body = (ROOT / ".github/workflows/match-reel.yml").read_text(encoding="utf-8")
    step = body.split("probe 正式 spec 就绪后自动派发 render", 1)[1].split(
        "render 质检落库后读取 spec", 1)[0]
    assert 'status") == "ready_for_render"' in step
    assert "gh workflow run match-reel.yml --ref main" in step
    assert "-f mode=render" in step
    assert "[waiting]" in step


def test_match_reel_dispatch表单绝不超过github的25项硬限制():
    body = (ROOT / ".github/workflows/match-reel.yml").read_text(encoding="utf-8")
    inputs = body.split("    inputs:\n", 1)[1].split("\npermissions:", 1)[0]
    names = [
        line.strip()[:-1]
        for line in inputs.splitlines()
        if line.startswith("      ")
        and not line.startswith("        ")
        and line.rstrip().endswith(":")
    ]
    assert len(names) <= 25, names
    assert "every" not in names
    assert '--every "2"' in body


def test_模型练手工作流只读且绝不发布():
    body = (ROOT / ".github/workflows/reel-model-benchmark.yml").read_text(
        encoding="utf-8")
    assert "contents: read" in body
    assert "PUSHPLUS_TOKEN" not in body
    assert "git push" not in body
    assert "gh workflow run" not in body
    assert "push:" in body
    assert "branches: [main]" in body
    assert "            skills\n" in body


def test_制作skill确实注入deepseek和minimax而不是只写文档():
    skill = load("reel_skill")
    deepseek = skill.model_instructions("deepseek")
    minimax = skill.model_instructions("minimax")
    assert "name: tennis-reel-production" in deepseek
    assert "fils-cobolli-cincinnati-2026-sf" in deepseek
    assert "Return JSON only" in deepseek
    assert "fils-cobolli-cincinnati-2026-sf" in minimax
    assert "time-coded contact sheets" in minimax
    assert "successful PushPlus response" in minimax

    draft = (TOOLS / "draft_spec.py").read_text(encoding="utf-8")
    visual = (TOOLS / "analyze_reel_visuals.py").read_text(encoding="utf-8")
    assert 'model_instructions("deepseek")' in draft
    assert 'model_instructions("minimax")' in visual


def test_deepseek基准评分要求硬事实和三段故事():
    bench = load("benchmark_reel_models")
    editorial = {
        "hook": ["三次交手", "一次没赢"],
        "question": "为什么世界第十还是过不了这一关？",
        "thesis": "6-3 6-4背后，是22比3的制胜分差。",
        "beats": ["首盘", "次盘", "三次交手"],
        "narration": ["首盘菲斯先破局。", "次盘差距扩大到二十二比三。",
                      "三场比赛，科博利一次都没赢。"],
        "human_context": "他们从青年组打到大师赛。",
    }
    push = {"summary": "三次交手一次没赢",
            "lead": "菲斯两盘取胜，制胜分22比3，三次交手继续保持全胜。"}
    score, issues = bench.deepseek_score(editorial, push)
    assert score == 100
    assert issues == []


def test_deepseek基准有明确缺项时绝不能仍显示满分():
    bench = load("benchmark_reel_models")
    editorial = {
        "hook": ["排名低十一位", "赢下三种场地"],
        "question": "菲斯为什么能连续击败科博利？",
        "thesis": "6-3 6-4背后，是22比3的制胜分差。",
        "beats": ["首盘6-3", "次盘6-4", "全场22比3"],
        "narration": ["首盘六比三。", "次盘六比四。", "制胜分二十二比三。"],
        "human_context": "他们从室内硬地打到红土和室外硬地。",
    }
    push = {"summary": "菲斯晋级",
            "lead": "菲斯以6比3、6比4取胜，全场制胜分22比3。"}
    score, issues = bench.deepseek_score(editorial, push)
    assert score == 90
    assert any("三次交手" in issue for issue in issues)


def test_模型练手拒绝把提示词示例抄成比赛事实():
    bench = load("benchmark_reel_models")
    editorial = {
        "hook": ["三次交手", "一次没赢"],
        "question": "决胜盘四比一领先还能输掉？",
        "thesis": "6-3 6-4背后，是22比3的制胜分差。",
        "beats": ["首盘", "次盘", "三次交手"],
        "narration": ["首盘菲斯先破局。", "次盘差距扩大到二十二比三。",
                      "三场比赛，科博利一次都没赢。"],
        "human_context": "他们从青年组打到大师赛。",
    }
    push = {"summary": "三次交手一次没赢",
            "lead": "菲斯两盘取胜，制胜分22比3，三次交手继续保持全胜。"}
    score, issues = bench.deepseek_score(editorial, push)
    assert score < 80
    assert any("事实包不存在" in issue for issue in issues)


def test_模型练手拒绝配音字段里的百分号():
    bench = load("benchmark_reel_models")
    editorial = {
        "hook": ["三次交手", "一次没赢"],
        "question": "为什么世界第十还是过不了这一关？",
        "thesis": "6-3 6-4背后，是22比3的制胜分差。",
        "beats": ["首盘", "次盘", "三次交手"],
        "narration": ["首盘菲斯先破局。", "一发得分率82%。",
                      "三场比赛，科博利一次都没赢。"],
        "human_context": "他们从青年组打到大师赛。",
    }
    push = {"summary": "三次交手一次没赢",
            "lead": "菲斯两盘取胜，制胜分22比3，三次交手继续保持全胜。"}
    score, issues = bench.deepseek_score(editorial, push)
    assert score < 80
    assert any("百分号" in issue for issue in issues)


def test_模型练手拒绝把已计入h2h的本场又加一次():
    bench = load("benchmark_reel_models")
    editorial = {
        "hook": ["排名低十一", "却三次全胜"],
        "question": "为何菲斯三次都赢？",
        "thesis": "22比3的制胜分决定胜负。",
        "beats": ["首盘6-3", "次盘6-4", "全场22比3"],
        "human_context": "此前3胜0负，今日再胜，完成四种场地连胜。",
        "narration": ["首盘六比三。", "次盘六比四。", "制胜分二十二比三。"],
    }
    push = {"summary": "菲斯晋级", "lead": "菲斯以6-3、6-4取胜，制胜分22比3。"}
    score, issues = bench.deepseek_score(editorial, push)
    assert score < 80
    assert any("今日再胜" in issue and "四种场地" in issue for issue in issues)


def test_模型练手拒绝把世界第十偷换成第十次交手():
    bench = load("benchmark_reel_models")
    editorial = {
        "hook": ["排名反差", "三战全胜"],
        "question": "为何世界第十过不了菲斯？",
        "thesis": "菲斯第10次直面前十，靠22比3的制胜分取胜。",
        "beats": ["首盘6比3", "次盘6比4", "三战全胜"],
        "human_context": "三种场地，菲斯保持3比0。",
        "narration": ["首盘六比三。", "次盘六比四。", "制胜分二十二比三。"],
    }
    push = {"summary": "菲斯晋级",
            "lead": "菲斯以6比3、6比4取胜，制胜分22比3，三战全胜。"}
    score, issues = bench.deepseek_score(editorial, push)
    assert score < 80
    assert any("第10次" in issue for issue in issues)


def test_deepseek算术闸拒绝数字都真实但差值算错():
    draft = load("draft_spec")
    wrong = {"beats": ["总得分五十六比四十五只领先九分。"]}
    right = {"beats": ["总得分五十六比四十五领先十一分。"]}
    assert "相差11分" in draft.arithmetic_claim_problem(wrong)
    assert draft.arithmetic_claim_problem(right) is None


def test_模型练手不能靠错误算术拿满分():
    bench = load("benchmark_reel_models")
    editorial = {
        "hook": ["三次交手", "一次没赢"],
        "question": "为什么世界第十还是过不了这一关？",
        "thesis": "6-3 6-4背后，是22比3的制胜分差。",
        "beats": ["首盘", "总得分五十六比四十五只领先九分", "三次交手"],
        "narration": ["首盘菲斯先破局。", "次盘差距扩大到二十二比三。",
                      "三场比赛，科博利一次都没赢。"],
        "human_context": "他们从青年组打到大师赛。",
    }
    push = {"summary": "三次交手一次没赢",
            "lead": "菲斯两盘取胜，制胜分22比3，三次交手继续保持全胜。"}
    score, issues = bench.deepseek_score(editorial, push)
    assert score < 80
    assert any("算术关系错误" in issue for issue in issues)


def test_deepseek草稿确定性规范化所有配音字段百分比():
    draft = load("draft_spec")
    editorial = {
        "beats": ["一发得分率82%"],
        "narration": ["科博利73％的一发得分率不够。"],
        "human_context": "抢七胜率100%",
    }
    clean = draft.normalize_editorial_for_speech(editorial)
    assert clean == {
        "beats": ["一发得分率百分之八十二"],
        "narration": ["科博利百分之七十三的一发得分率不够。"],
        "human_context": "抢七胜率百分之一百",
    }


def test_deepseek草稿移除中文词间会让tts异常停顿的空格():
    draft = load("draft_spec")
    assert draft.normalize_editorial_for_speech(
        "今天 他击出22记制胜分，ATP 1000首进决赛。"
    ) == "今天他击出22记制胜分，ATP 1000首进决赛。"


def test_模型练手拒绝minimax拿窗口外画面当证据():
    bench = load("benchmark_reel_models")
    report = {
        "visual_status": "pass",
        "cold_open": {"start": 317.72, "end": 329.84,
                      "reason": "330.5-332.5s 才看见握手"},
        "ending": {"start": 317.5, "end": 329.84,
                   "reason": "317.5-329.8s 完整收官"},
        "cover": {"subject": "菲斯", "moment": "winner_celebration",
                  "same_match": True},
    }
    score, issues = bench.minimax_score(report, [])
    assert score < 85
    assert any("窗口外时间" in issue for issue in issues)


def test_orchestrate把轮次球场国别排名和SLO起点传进probe():
    body = (TOOLS / "orchestrate.py").read_text(encoding="utf-8")
    for value in ("round=", "court=", "home_country=", "away_country=",
                  "home_rank=", "away_rank=", "received_at="):
        assert value in body


def test_没有match块的反向比分也要拦得住():
    """medvedev-damm（2026-08-26 已推送）：cover.result/topbar 写成输家视角
    「5-7 3-6」，图形上宣称输的人赢了。verified_result_problem 只在
    _match.status == result_verified 时才跑——手写 spec 的 _match 全空就整套
    静默跳过。这一道不依赖 _match：完赛盘里赢家零盘、输家两盘以上必错。"""
    facts = load("reel_facts")
    bad = {"cover": {"winner": "小马丁·达姆", "result": "5-7 3-6"}}
    problem = facts.result_direction_problem(bad)
    assert problem and "一个完赛盘都没拿" in problem
    # 正常形状一个都不许误伤
    for ok in ("7-5 6-3",              # 赢家视角
               "4-6 6-4 6-2",          # 丢一盘
               "6-7(4) 6-1 5-0 Ret.",  # 退赛（未完盘 + 标记）
               "6-0 4-0 退赛"):
        assert not facts.result_direction_problem(
            {"cover": {"winner": "X", "result": ok}}), ok


def test_反向比分在渲染入口就红不等到发出去():
    """闸装在 _topbar_lines（validate_spec 调它，dry-run 0.2 秒就走到）。
    真调一次：查源码只能防「有人把它删了」，防不住「它从来没工作过」。"""
    sys.path.insert(0, str(TOOLS))
    import build_match_reel as reel  # noqa: PLC0415

    spec = {"slug": "fresh-auto-spec",
            "cover": {"eyebrow": "赛场之上", "winner": "小马丁·达姆",
                      "result": "5-7 3-6"},
            "topbar": {"line1": "ATP250 温斯顿-塞勒姆 第二轮",
                       "line2": "小马丁·达姆 5-7 3-6 梅德韦杰夫"}}
    with pytest.raises(reel.ReelError, match="一个完赛盘都没拿"):
        reel._topbar_lines(spec)


def test_全库spec的封面赛果都是赢家视角():
    """自己推导不维护名单：medvedev-damm 的 spec 已改回赢家视角（成片
    已发不重渲），从此谁再把输家视角写进 cover.result，这条当场红。"""
    import glob  # noqa: PLC0415
    import json  # noqa: PLC0415

    facts = load("reel_facts")
    checked, hits = 0, []
    for f in glob.glob(str(ROOT / "specs" / "reels" / "*.json")):
        spec = json.loads(Path(f).read_text(encoding="utf-8"))
        if (spec.get("cover") or {}).get("result"):
            checked += 1
        if facts.result_direction_problem(spec):
            hits.append(Path(f).name)
    assert checked >= 100, f"只校到 {checked} 条——主语没了"
    assert hits == [], f"这些 spec 的封面赛果不是赢家视角：{hits}"


def test_大满贯官方频道认得出来():
    """大满贯集锦不上三大巡回赛频道，而赛事频道匹配是「频道名＝赛事名」
    精确等值——US Open 的频道叫 US Open Tennis Championships，等值必拒，
    美网一开打整条自动链对它盲。显式白名单放行官方，搬运号照旧拒。"""
    det = load("detect_highlights")
    assert det.channel_ok("US Open Tennis Championships", "US Open")
    assert det.channel_ok("Wimbledon", "Wimbledon Championships")
    assert det.channel_ok("Roland-Garros", "French Open")
    assert det.channel_ok("Australian Open TV", "Australian Open")
    # 搬运号不许继承官方身份（channel_ok 的老判据，别被白名单放宽）
    assert not det.channel_ok("US Open Tennis Fan", "US Open")
    assert not det.channel_ok("Cincinnati Tennis Fan", "Cincinnati Open")


def test_段数够不等于内容够_正片时长有下界():
    """medvedev-damm：3 段合计 16 秒的成片推送出去了。5-10 段的闸挡不住
    5 段 × 3 秒的退化形状；账号所有者 2026-08-12「集锦的长度可以不要太短，
    视频一定要交代清楚具体关键点」。40 秒远低于已发语料最短正片（约 69 秒）。"""
    promote = load("promote_reel_draft")
    thin = {"segments": [{"start": i * 10.0, "end": i * 10.0 + 5.0}
                         for i in range(6)]}
    reasons = promote.waiting_reasons(thin)
    assert any("低于 40 秒" in r for r in reasons), reasons
    rich = {"segments": [{"start": i * 20.0, "end": i * 20.0 + 12.0}
                         for i in range(6)]}
    assert not any("低于 40 秒" in r for r in promote.waiting_reasons(rich))
