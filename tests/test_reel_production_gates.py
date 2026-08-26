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


def test_visual_gate均匀查看整条片而不是只看开头四张(tmp_path):
    visual = load("analyze_reel_visuals")
    paths = []
    for index in range(9):
        path = tmp_path / f"contact_{index:02d}.jpg"
        path.write_bytes(str(index).encode())
        paths.append(path)
    chosen = visual.select_contact_sheets(paths)
    assert [path.name for path in chosen] == [
        "contact_00.jpg", "contact_03.jpg", "contact_05.jpg", "contact_08.jpg"
    ]


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


def test_模型练手工作流只读且绝不发布():
    body = (ROOT / ".github/workflows/reel-model-benchmark.yml").read_text(
        encoding="utf-8")
    assert "contents: read" in body
    assert "PUSHPLUS_TOKEN" not in body
    assert "git push" not in body
    assert "gh workflow run" not in body


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


def test_orchestrate把轮次球场国别排名和SLO起点传进probe():
    body = (TOOLS / "orchestrate.py").read_text(encoding="utf-8")
    for value in ("round=", "court=", "home_country=", "away_country=",
                  "home_rank=", "away_rank=", "received_at="):
        assert value in body
