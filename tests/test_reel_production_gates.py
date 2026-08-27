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


def test_deepseek草稿把连字符比分规范成汉字几比几():
    """medvedev-damm 的旁白写着「达姆7-5、6-3爆冷」——TTS 把连字符读出声，
    显示端还印成「7 比 5」的松散一串。prompt 要求模型直接写「七比五」，
    这条是执法：模型没照做也在源头救回来。两侧最多两位数（局分/盘分/抢七），
    四位年份区间不是比分。"""
    draft = load("draft_spec")
    assert draft.normalize_editorial_for_speech(
        "达姆7-5、6-3爆冷，总分67比56。"
    ) == "达姆七比五、六比三爆冷，总分67比56。"
    assert draft.normalize_editorial_for_speech(
        "抢七10-8拿下"
    ) == "抢七十比八拿下"
    assert draft.normalize_editorial_for_speech(
        "2016-2026 共十届，2020 年停办"
    ) == "2016-2026 共十届，2020 年停办"


def test_deepseek旁白prompt带着断句和比分写法的规矩():
    """断句的机器味一半靠拆行代码兜底，另一半要在源头教模型：子句 ≤16 字
    （一行字幕的宽度）、比分写汉字、顿号只连并列项。prompt 被删了这半就
    只剩兜底。"""
    draft = load("draft_spec")
    for rule in ("子句 ≤ 16 字", "比分一律写汉字", "顿号只连并列的词",
                 "≤ 35 字"):
        assert rule in draft.system_prompt(), rule


def test_import草稿工具不许要求教材在盘上():
    """2026-08-27 reel-auto-ready 栽的：`draft_spec` 原来在 import 那一刻就拼
    SYSTEM prompt、读 `skills/…/SKILL.md`，而那条工作流的稀疏检出没有 skills——
    `refresh_reel_cover` 只想借 `assemble_spec` 两个小函数，整条 import 链炸在
    教材缺席上，第一条真实的 pending 草稿一次都没被重试过。

    判据：教材读不到时 import 必须照样成功，**真要起草时**才当场响。"""
    import importlib

    import pytest

    sys.path.insert(0, str(TOOLS))
    import draft_spec
    import reel_skill

    def boom(role):
        raise FileNotFoundError("教材不在盘上（模拟稀疏检出没有 skills/）")

    orig = reel_skill.model_instructions
    reel_skill.model_instructions = boom
    try:
        module = importlib.reload(draft_spec)   # 不许炸
        module.system_prompt.cache_clear()
        module.push_system_prompt.cache_clear()
        with pytest.raises(FileNotFoundError):
            module.system_prompt()              # 真要用了才响
    finally:
        reel_skill.model_instructions = orig
        module = importlib.reload(draft_spec)
        module.system_prompt.cache_clear()
        module.push_system_prompt.cache_clear()


def test_跑教材工具的工作流都要检出skills目录():
    """`analyze_reel_visuals` 在**调用时**要读生产 skill 给 MiniMax/DeepSeek 拼
    prompt——工作流的稀疏检出漏了 `skills`，失败要等跑到那一步才炸。哪些工具
    需要教材从 import 图自己推（直接或间接沾 `reel_skill` 的都算，宁可保守：
    几个 markdown 的检出成本是零），不维护名单。"""
    import ast
    import re

    tool_files = {p.stem: p for p in TOOLS.glob("*.py")}

    def imported(name: str) -> set[str]:
        mods: set[str] = set()
        for node in ast.walk(ast.parse(tool_files[name].read_text("utf-8"))):
            if isinstance(node, ast.Import):
                mods |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
        return mods

    graph = {name: imported(name) & (set(tool_files) | {"reel_skill"})
             for name in tool_files}

    def needs_skill(name: str, seen: frozenset = frozenset()) -> bool:
        if name == "reel_skill":
            return True
        if name in seen or name not in graph:
            return False
        return any(needs_skill(m, seen | {name}) for m in graph[name])

    needy = {n for n in tool_files if needs_skill(n)}
    # 判据自己的判据：推导空了要出声，不许变一盏恒真的绿灯
    assert {"draft_spec", "assemble_spec", "analyze_reel_visuals",
            "refresh_reel_cover"} <= needy, needy

    checked = 0
    for wf in (ROOT / ".github/workflows").glob("*.yml"):
        body = wf.read_text("utf-8")
        used = {m.group(1) for m in re.finditer(r"tools/(\w+)\.py", body)}
        if not (used & needy) or "sparse-checkout" not in body:
            continue   # 不跑这些工具，或全量检出（自然带 skills）
        checked += 1
        assert re.search(r"^\s+skills\s*$", body, re.M), (
            f"{wf.name} 跑 {sorted(used & needy)}，稀疏检出却没有 skills——"
            "import 现在是安全的，但真起草/审视觉证据那一刻要读教材")
    assert checked >= 2, "一个工作流都没校到，判据的主语丢了"


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


def _reel():
    sys.path.insert(0, str(TOOLS))
    import build_match_reel as reel  # noqa: PLC0415
    return reel


def test_源片静音区间趁probe量出来(tmp_path):
    """zheng-burel（run 33000830101）：段窗口尾部撞上源片静音秒，QC 在渲染
    5 分钟后才报，整趟 8 分半白烧。修法和 point_ends 同款：趁源片还在时量，
    写进 probe.json。真跑 ffmpeg——查源码只能防「有人把它删了」。"""
    import subprocess  # noqa: PLC0415

    reel = _reel()
    src = tmp_path / "s.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", "testsrc2=duration=6:size=64x64:rate=10",
         "-f", "lavfi", "-i",
         "aevalsrc='if(between(t,2,4),0,0.4*sin(2*PI*440*t))':d=6",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
         "-shortest", str(src)], check=True)
    spans = reel.silent_audio_spans(src)
    assert spans and len(spans) == 1, spans
    lo, hi = spans[0]
    assert 1.5 <= lo <= 2.5 and 3.5 <= hi <= 4.5, spans
    # 没有音轨 → None（「没音轨」和「量过为空」不能长一样）
    mute = tmp_path / "m.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc2=duration=2:size=64x64:rate=10",
         "-c:v", "libx264", "-preset", "ultrafast", str(mute)], check=True)
    assert reel.silent_audio_spans(mute) is None


def test_静音风险的账_zheng_burel那一类要预判出来():
    reel = _reel()
    # 失败版第 8 段的真实数字：窗口 181.0–192.57，源片静音区约 191.3–192.5，
    # 旁白离线估 ~9.7s。当晚它是「大概率红」——真的红了，白烧一趟渲染。
    risks = reel.silence_risk(181.0, 192.57, 9.66, [[191.3, 192.5]])
    assert len(risks) == 1
    _lo, _hi, certain, probable = risks[0]
    assert probable >= 0.5, "当晚白烧的那一类必须被标成「大概率红」"
    assert certain < 2.0, "旁白最长估能盖住大半——不该标成必红"
    # 无旁白段（quote/纯画面）的音频就是现场声本身：撞上 3 秒静音是必红
    (_l, _h, certain2, _p), = reel.silence_risk(10.0, 20.0, None, [[12.0, 15.0]])
    assert certain2 >= 2.0
    # 旁白完全盖得住的：一条都不报（别刷屏——哑场那道闸的老教训）
    assert reel.silence_risk(0.0, 12.0, 11.0, [[3.0, 4.0]]) == []


def test_自动产的spec静音悬案按硬闸算_手写只报():
    """自动 spec 的另一头是模型，改一句旁白比烧一趟渲染便宜——「大概率红」
    也按硬算；手写 spec 守住「哑场离线估只提醒不拍板」的老规矩，只报。"""
    reel = _reel()
    seg = reel.Segment(start=181.0, end=192.57, cx=None,
                       narration="六比一。")   # 估 ~1s，远盖不到窗口尾
    probes = {"URL": {"silent_audio": [[190.5, 192.5]]}}
    urls = {"": "URL"}
    auto = {"_production": {"status": "ready_for_render"}}
    hard, soft = reel.silence_findings(auto, [seg], probes, urls)
    assert hard and not soft, (hard, soft)
    # 必红的对手写 spec 也是硬的；「大概率」那一档才分严格度，用下面这形状验
    prob_seg = reel.Segment(start=0.0, end=12.0, cx=None,
                            narration="六比一。", source="")
    prob_probes = {"URL": {"silent_audio": [[10.0, 11.5]]}}
    h2, s2 = reel.silence_findings({}, [prob_seg], prob_probes, urls)
    assert not h2 and s2, (h2, s2)
    h3, s3 = reel.silence_findings(auto, [prob_seg], prob_probes, urls)
    assert h3 and not s3, (h3, s3)
    # 老 probe（没有 silent_audio 键）→「还没量过」只提示，不硬拦
    h4, s4 = reel.silence_findings({}, [seg], {"URL": {}}, urls)
    assert not h4 and any("还没量过" in s for s in s4)
    # 源片没音轨（None）→ 这儿不报（silent_source 认领那道闸管）
    h5, s5 = reel.silence_findings({}, [seg], {"URL": {"silent_audio": None}}, urls)
    assert not h5 and not s5
    # 接线：probe 落库这个键，dry-run 真的调 silence_findings
    body = Path("tools/build_match_reel.py").read_text("utf-8")
    assert '"silent_audio": silent_audio,' in body
    dry = body[body.index("def probe_dry_run"):body.index("def _cover_frame_spots")]
    assert "silence_findings(spec, segments, probes, urls)" in dry


def test_判据回喂只删不改写_quote段和越权字段整体丢弃():
    """QC 回喂修复的头号红线：模型不许借「修一下」发明新事实。旁白只认
    「按顺序删字符」（子序列），改写/换词/新增一个字都整体丢弃；quote 段的
    双语字幕钉在真实时刻上，一个字段都不许动。"""
    repairer = load("repair_reel_spec")
    assert repairer.deletion_only("三个赛点摆在她面前，她只兑现了最后一个。",
                                  "三个赛点，她只兑现了最后一个。")
    assert not repairer.deletion_only("她赢了这一局。", "她拿下了这一局。")

    spec = {"segments": [
        {"source": "", "start": 10.0, "end": 20.0,
         "narration": "第一句。", "quote": ["x"]},
        {"source": "", "start": 30.0, "end": 44.0,
         "narration": "三个赛点摆在她面前，她只兑现了最后一个。"},
    ]}
    revised, detail = repairer.apply_bounded(
        spec, [{}, {"end": 41.5, "narration": "三个赛点，她只兑现了最后一个。"}])
    assert revised is not None, detail
    assert revised["segments"][1]["end"] == 41.5
    assert revised["segments"][0] == spec["segments"][0]

    for patch, marker in [
        ([{"end": 19.0}, {}], "quote"),                       # 动 quote 段
        ([{}, {"narration": "她拿下了这一局。"}], "只删不改写"),  # 改写
        ([{}, {"speed": 0.5}], "越权"),                        # 越权字段
        ([{}, {"narration": ""}], "删空"),                     # 删空旁白
        ([{}], "段数"),                                        # 段数不符
        ([{}, {}], "一处都没改"),                              # 空修订
    ]:
        bad, why = repairer.apply_bounded(spec, patch)
        assert bad is None and marker in why, (patch, why)


def test_判据回喂只认自动spec最多两轮_环境错和绿日志不喂模型(tmp_path):
    """四个 skip 口，每个都是一层边界：手写 spec 不自动改；两轮修不好就还给
    会话；环境错（下载/apt）改 spec 修不了；**「共 0 项不合格」的绿日志**
    （render 全绿、死在后面 commit/push 步的 run）不许被裸的「不合格」三个字
    误认成内容失败。"""
    import json as _json
    repairer = load("repair_reel_spec")
    spec_path = tmp_path / "x.json"

    spec_path.write_text(_json.dumps({"slug": "x", "segments": []}), "utf-8")
    assert "不是自动 spec" in repairer.repair(
        spec_path, "[不合格] 数字静音", tmp_path, write=False)

    spec_path.write_text(_json.dumps({
        "slug": "x", "segments": [],
        "_production": {"status": "ready_for_render", "qc_repair_attempts": 2},
    }), "utf-8")
    assert "已自动修过 2 轮" in repairer.repair(
        spec_path, "[不合格] 数字静音", tmp_path, write=False)

    spec_path.write_text(_json.dumps({
        "slug": "x", "segments": [],
        "_production": {"status": "ready_for_render"},
    }), "utf-8")
    assert "环境错" in repairer.repair(
        spec_path, "ERROR: apt-get install timed out\n共 0 项不合格",
        tmp_path, write=False)
    assert not repairer.CONTENT_CLASS.search("共 0 项不合格")
    assert repairer.CONTENT_CLASS.search("[不合格] 封面之后还有 1 秒是数字静音")


def test_判据回喂修完先过本地闸才落盘(tmp_path, monkeypatch):
    """模型输出过了有界套用，还要过**同一套生产闸**（dry-run 子进程）才写回；
    闸红就一个字节都不落盘。反向验证：把 local_gate 的失败吞掉，第二段断言
    当场红。"""
    import json as _json
    repairer = load("repair_reel_spec")

    class FakeChat:
        ready = True
        channel = "fake"

        def ask(self, system, user, *, schema, max_tokens=0):
            return {"fixable": True, "note": "收窗口避开静音区",
                    "segments": [{"end": 41.5}]}

    import tennislive.research.brief as brief
    monkeypatch.setattr(brief, "Chat", FakeChat)

    spec = {
        "slug": "x",
        "_production": {"status": "ready_for_render", "qc_repair_attempts": 1},
        "segments": [{"source": "", "start": 30.0, "end": 44.0,
                      "narration": "三个赛点摆在她面前。"}],
    }
    spec_path = tmp_path / "x.json"
    spec_path.write_text(_json.dumps(spec, ensure_ascii=False), "utf-8")

    monkeypatch.setattr(repairer, "local_gate", lambda s, slug: "哑场闸红了")
    out = repairer.repair(spec_path, "[不合格] 数字静音", tmp_path, write=True)
    assert "仍过不了本地闸" in out and "不落盘" in out
    assert _json.loads(spec_path.read_text("utf-8")) == spec  # 一个字节没动

    monkeypatch.setattr(repairer, "local_gate", lambda s, slug: None)
    out = repairer.repair(spec_path, "[不合格] 数字静音", tmp_path, write=True)
    assert "[repaired]" in out, out
    written = _json.loads(spec_path.read_text("utf-8"))
    assert written["segments"][0]["end"] == 41.5
    assert written["_production"]["qc_repair_attempts"] == 2
    assert "收窗口避开静音区" in written["_production"]["qc_repair_note"]


def test_render红了的回喂步先commit再dispatch_三步都tee了判据():
    """工作流接线三头：① dry-run/render/QC 三步都把判据 tee 进同一份日志
    （且带 pipefail——不带的话 tee 会把失败吞成绿）；② 修复步挂在
    failure() 上、只认 mode=render + main；③ **先 commit 再 dispatch**——
    render 组是 cancel-in-progress，新 run 一启动就掐掉本 run，顺序反了
    修订就静默丢失。"""
    body = (ROOT / ".github/workflows/match-reel.yml").read_text(encoding="utf-8")
    for name, stop in [
        ("dry-run — 先把 spec 的形状错拦在编码之前", "缓存 Chromium"),
        ("render — 出成片", "写复制页"),
        ("查成片本身合不合格", "成片发到 Release"),
    ]:
        step = body.split(name, 1)[1].split(stop, 1)[0]
        assert "set -o pipefail" in step, name
        assert "tee -a /tmp/render-findings.log" in step, name

    step = body.split("render 红了把判据回喂模型修一轮", 1)[1].split(
        "推送前预占持久发布账本", 1)[0]
    assert "failure()" in step
    assert "github.event.inputs.mode == 'render'" in step
    assert "github.ref_name == 'main'" in step
    assert "repair_reel_spec.py" in step
    assert "git_push_retry.sh" in step
    assert step.index("git commit") < step.index("gh workflow run match-reel.yml")
    assert "-f mode=render" in step
    # received_at 要跟着转发：SLO 的表从确认链接那一刻起算，修一轮重渲不是
    # 重新接单——丢了它，production_sla 会把返工那趟当成一条新且飞快的生产
    assert "-f received_at=" in step
