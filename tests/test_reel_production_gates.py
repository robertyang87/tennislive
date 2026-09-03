from __future__ import annotations

import importlib.util
import json
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
                      "chapters": ["首盘失守", "第二盘反过来", "五个赛点"],
                      "human_context": "乙首次击败前十。",
                      "narration": ["首盘", "转折", "为什么会爆冷？"]},
        "segments": [
            {"start": 140, "end": 150, "narration": "", "quote": ["Great shot!\n好球！"],
             "_ending_payoff_required": True},
            {"start": 10, "end": 18, "narration": "坐标"},
            {"start": 40, "end": 48, "narration": "首盘"},
            {"start": 80, "end": 88, "narration": "转折"},
            {"start": 140, "end": 150, "narration": "为什么会爆冷？"}],
        "stats": {"a": {"pts_won": 56, "headshot": str(photo)},
                  "b": {"pts_won": 67, "headshot": str(photo)}},
        "push": {"summary": "乙爆冷击败甲", "lead": "乙两盘取胜。", "auto": True},
    }


def test_promote缺数据图头像就留waiting并说怎么补(tmp_path):
    """render 末尾那次「渲给推送用」的数据图缺 headshot 是 SystemExit——转正了就是
    一趟必红的 render。2026-09-03 量过：49 份 pending 草稿全带 stats、零份带
    headshot，而自动链里没有任何工具写过这个字段。闸装在转正那一刻，报错正文
    要说出路（机械补的命令 + ATP 的手动命令）。"""
    promote = load("promote_reel_draft")
    draft = _ready_draft(tmp_path)
    del draft["stats"]["b"]["headshot"]
    reasons = promote.waiting_reasons(draft)
    hit = [r for r in reasons if "头像" in r]
    assert hit and "stats.b" in hit[0] and "乙" in hit[0]
    assert "headshot_index.py" in hit[0] and "fetch_official_headshot.py atp" in hit[0]
    with pytest.raises(ValueError, match="头像"):
        promote.promote(draft)
    # 两侧都在就不报
    draft = _ready_draft(tmp_path)
    assert not [r for r in promote.waiting_reasons(draft) if "头像" in r]


def test_promote转正时在收官段之前机械插一段数据图(tmp_path):
    """review 路线 ④：131 条已发 spec 带 stats、0 条烧进片子。DeepSeek 不写
    segments，所以证据段也机械插——收官段之前、旁白只讲总得分（汉字数字给
    TTS 念、方向机械算）。三个不插的情形都是确定性的，各验一头。"""
    promote = load("promote_reel_draft")
    spec = promote.promote(_ready_draft(tmp_path))
    segs = spec["segments"]
    card = [s for s in segs if s.get("stat_card")]
    # 收官段之前——收官 beat 自己的章节卡（路线 ⑤）插在它前面，数据图再前一格
    assert len(card) == 1 and segs[-3] is card[0] and segs[-2].get("title_card"), \
        "要插在收官段之前，只插一段"
    assert card[0]["narration"] == "全场总得分，乙六十七比五十六，多拿了十一分。"
    assert card[0]["seconds"] >= 4.0 and "score_inset" not in card[0]
    assert "image" in card[0] and card[0]["image"] == "<stat_card>", \
        "validate_spec 走了 load_spec 之外的路，占位符要由 parse_segments 归一"
    # ① 段数已到上限不插（waiting_reasons 那条「5-10 段」会拒 11 段）
    draft = _ready_draft(tmp_path)
    draft["segments"] = draft["segments"][:4] + [
        {"start": 100 + i, "end": 101 + i, "narration": f"第{i}"} for i in range(5)
    ] + draft["segments"][-1:]
    assert len(draft["segments"]) == 10
    assert not any(s.get("stat_card") for s in promote.promote(draft)["segments"])
    # ② 总得分算不出不插
    draft = _ready_draft(tmp_path)
    del draft["stats"]["a"]["pts_won"]
    assert not any(s.get("stat_card") for s in promote.promote(draft)["segments"])
    # ③ 已经有一段就不重复插
    draft = _ready_draft(tmp_path)
    draft["segments"].insert(2, {"stat_card": True, "seconds": 5, "narration": "手写的。"})
    assert sum(1 for s in promote.promote(draft)["segments"] if s.get("stat_card")) == 1


def test_promote按chapters在每个beat的第一段前插章节卡(tmp_path):
    """review 路线 ⑤（学「小丝瓜🎾」的 01/02/03 章节页）：DeepSeek 合同多一个
    `chapters`（三条 ≤10 字的标题，一条对应一个 beat），转正时按**旁白原文**认出
    每个 beat 的那一段，在它前面插一张 title_card。钥匙是逐字相同的 narration
    （align_points 就是这么挂的）——认不到的 beat 不插、要出声。"""
    promote = load("promote_reel_draft")
    spec = promote.promote(_ready_draft(tmp_path))
    segs = spec["segments"]
    cards = [(i, s) for i, s in enumerate(segs) if s.get("title_card")]
    assert [s["title_card"] for _, s in cards] == ["首盘失守", "第二盘反过来", "五个赛点"]
    assert [s["kicker"] for _, s in cards] == ["01", "02", "03"]
    for i, s in cards:
        assert s["seconds"] >= 2.0 and "score_inset" not in s and "narration" not in s
    # 每张卡紧挨着它那个 beat 的段
    nxt = [segs[i + 1].get("narration") for i, _ in cards]
    assert nxt == ["首盘", "转折", "为什么会爆冷？"]
    assert not segs[0].get("title_card") and "_chapter_cards_why" not in spec
    # ① 硬钥匙 `_beat`：模型写窗口那条路旁白全是改写过的（47 份 pending 草稿
    #    量过，按原文一条都认不到），段上标了 _beat 就按它定位，不看旁白
    draft = _ready_draft(tmp_path)
    for seg, beat in zip(draft["segments"][1:], (0, 1, 2, 3), strict=True):
        seg["narration"] = "模型改写过：" + seg["narration"]
        seg["_beat"] = beat
    draft["segments"].insert(3, {"start": 60, "end": 66, "narration": "同一 beat 的第二段",
                                 "_beat": 1})
    spec = promote.promote(draft)
    cards = [(i, s) for i, s in enumerate(spec["segments"]) if s.get("title_card")]
    assert [s["kicker"] for _, s in cards] == ["01", "02", "03"]
    assert [spec["segments"][i + 1].get("_beat") for i, _ in cards] == [1, 2, 3]
    assert spec["segments"][cards[0][0] + 1]["narration"].endswith("首盘"), \
        "同一 beat 有几段时，卡插在第一段前面"
    # ② 两把钥匙都认不到的 beat 不插，但要出声
    draft = _ready_draft(tmp_path)
    draft["segments"][2]["narration"] = "首盘，模型改写过的一句。"
    spec = promote.promote(draft)
    assert sum(1 for s in spec["segments"] if s.get("title_card")) == 2
    assert "beat 1" in spec["_chapter_cards_why"]
    # ③ 形状不合（带标点 / 超长 / 条数对不上 / 没这个字段）都不拦转正，只出声
    for bad, why in ((["首盘失守。", "二", "三"], "标点"),
                     (["这个标题写得实在是太长了", "二", "三"], "超过"),
                     (["一", "二"], "对不上"), (None, "没有 chapters")):
        draft = _ready_draft(tmp_path)
        if bad is None:
            del draft["editorial"]["chapters"]
        else:
            draft["editorial"]["chapters"] = bad
        spec = promote.promote(draft)
        assert not any(s.get("title_card") for s in spec["segments"])
        assert why in spec["_chapter_cards_why"], (bad, spec["_chapter_cards_why"])
    # ④ 手写过章节卡的不再机械插
    draft = _ready_draft(tmp_path)
    draft["segments"].insert(2, {"title_card": "手写的", "seconds": 2.5})
    spec = promote.promote(draft)
    assert sum(1 for s in spec["segments"] if s.get("title_card")) == 1
    # ⑤ 教材和 prompt 真的教过这个字段——模型没处学就永远不会产
    draft_spec = load("draft_spec")
    assert "chapters" in draft_spec.SCHEMA["required"]
    assert "chapters" in draft_spec.system_prompt() and "10 字" in draft_spec.system_prompt()


def test_教材教了收尾先兑现再抛问和反应镜头():
    """review 3.2 的 B6 / D10（教模型那一半）：DeepSeek 的收尾要先用一个数字回答
    开场的 question 再抛问；MiniMax 挑 ending 时有反应镜头（输家的脸 / 教练席 /
    握手）就优先——纪录片的情绪几乎全在反应镜头里。查的是真拼出来的 prompt。"""
    skill = load("reel_skill")
    draft = load("draft_spec")
    deepseek = draft.system_prompt()
    assert "先兑现" in deepseek and "回答开场的 question" in deepseek
    assert "pay off before you ask" in skill.model_instructions("deepseek")
    minimax = skill.model_instructions("minimax")
    for phrase in ("loser's reaction", "coach box", "handshake", "never invent"):
        assert phrase in minimax, phrase


def test_promote零证据上屏要出声但不拦(tmp_path):
    """review 3.2 A3 的软报告：一处数字/文字都没上屏（没数据图段、章节卡段、
    贴图、脉冲）就写 `_evidence_on_screen_why`，有一处就不写。不拦转正——
    机械插不进来的各自已经出声，这儿是给终审的汇总。"""
    promote = load("promote_reel_draft")
    spec = promote.promote(_ready_draft(tmp_path))
    assert "_evidence_on_screen_why" not in spec and promote.evidence_on_screen(spec) >= 1
    bare = _ready_draft(tmp_path)
    del bare["stats"]["a"]["pts_won"]           # 数据图插不进来
    del bare["editorial"]["chapters"]           # 章节卡插不进来
    spec = promote.promote(bare)
    assert promote.evidence_on_screen(spec) == 0
    assert "零证据上屏" in spec["_evidence_on_screen_why"]
    # 手写一处（比如一张章节卡）就够
    bare = _ready_draft(tmp_path)
    del bare["stats"]["a"]["pts_won"]; del bare["editorial"]["chapters"]
    bare["segments"].insert(2, {"title_card": "手写章节", "seconds": 2.5})
    assert "_evidence_on_screen_why" not in promote.promote(bare)


def test_editorial的chapters写了就要是短标题列表():
    """spec 那头：chapters 可选；写了就得装得进整屏大字（render_title_card 两行的上限）。"""
    reel = load("build_match_reel")
    base = {"mode": "match_review", "question": "为什么？", "thesis": "因为。",
            "beats": ["一", "二", "三"]}
    reel._validate_editorial_contract({"editorial": base})
    reel._validate_editorial_contract({"editorial": {**base, "chapters": ["首盘失守"]}})
    with pytest.raises(reel.ReelError, match="chapters"):
        reel._validate_editorial_contract({"editorial": {**base, "chapters": []}})
    with pytest.raises(reel.ReelError, match="最多"):
        reel._validate_editorial_contract(
            {"editorial": {**base, "chapters": ["这一条章节标题长到两行大字都装不下了呀"]}})
    bench = load("benchmark_reel_models")
    _, issues = bench.deepseek_score(
        {"hook": ["a", "b"], "question": "q", "thesis": "t", "human_context": "h",
         "beats": ["1", "2", "3"], "narration": ["1", "2", "3"],
         "chapters": ["带标点。", "二", "三"]}, {"summary": "s", "lead": "l"})
    assert any("chapters" in x for x in issues)


def test_数据图那段的旁白方向机械算持平也说得通():
    promote = load("promote_reel_draft")
    m = [{"name": "甲"}, {"name": "乙"}]
    assert promote.stat_card_narration({"a": {"pts_won": 80}, "b": {"pts_won": 71}}, m) \
        == "全场总得分，甲八十比七十一，多拿了九分。"
    assert promote.stat_card_narration({"a": {"pts_won": 60}, "b": {"pts_won": 60}}, m) \
        == "全场总得分六十比六十，一分不差。"
    assert promote.stat_card_narration({"a": {}, "b": {"pts_won": 60}}, m) == ""


def test_promote缺视觉证据就只留waiting(tmp_path):
    promote = load("promote_reel_draft")
    draft = _ready_draft(tmp_path)
    draft["_visual_evidence"]["status"] = "waiting"
    assert any("MiniMax" in reason for reason in promote.waiting_reasons(draft))
    with pytest.raises(ValueError, match="MiniMax"):
        promote.promote(draft)


def test_promote不许在同一个栏目里发第二条讲同一场球的片子(tmp_path):
    """同一场球已经有正式「赛场之上」了，自动草稿就不许再转正。

    来路：2026-09-01 编排器 01:55 产的 `swiatek-wang` 和人写的
    `wangxiyu-swiatek-us-open-2026-r1` 是**同一场球、同一条源片**，只是视角不同；
    量过当时 24 份 pending 里有 6 份是这个形状。撞上就是同一场球发第二条微信，
    而那条消息发出去收不回来。

    三头分别验，缺一头这条闸就是半哑的：
      ① 场次 id 认得出（同一场球换一版官方集锦，视频地址不同）
      ② 源片认得出，**而且要归一化**（`youtu.be/<id>` 和 `watch?v=<id>` 是同一条）
      ③ **跨栏目不许误伤**——「网球有故事」复用同一段素材是仓库明写允许的
    """
    promote = load("promote_reel_draft")
    published = tmp_path / "formal"
    published.mkdir()

    def write(slug, eyebrow, url, fsid):
        (published / f"{slug}.json").write_text(json.dumps({
            "slug": slug, "source_url": url,
            "_match": {"flashscore_id": fsid},
            "cover": {"eyebrow": eyebrow},
        }, ensure_ascii=False), encoding="utf-8")

    write("已发的这一场", "赛场之上", "https://youtu.be/na565GRLNpg", "KWGdlmdC")
    write("别人的故事片", "网球有故事", "https://youtu.be/story999", "STORY999")
    index = promote._published_reel_matches(published)

    # ① 场次 id：视频换了一版，照样认得出是同一场
    assert index.get("fs:KWGdlmdC") == "已发的这一场"
    # ② 源片：两种写法归一到同一把钥匙
    assert promote._video_key("https://www.youtube.com/watch?v=na565GRLNpg") == \
           promote._video_key("https://youtu.be/na565GRLNpg")
    assert index.get("yt:na565GRLNpg") == "已发的这一场"
    # ③ 跨栏目不进这张表——「同一件事，不同栏目各讲一次不算重复」
    assert "fs:STORY999" not in index and "yt:story999" not in index

    draft = _ready_draft(tmp_path)
    draft["_match"]["flashscore_id"] = "KWGdlmdC"
    assert any("已经有正式" in reason for reason in promote.waiting_reasons(draft))
    with pytest.raises(ValueError, match="已经有正式"):
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


def test_promote美网草稿自动带式(tmp_path, monkeypatch):
    """账号所有者 2026-08-28：「美网期间的比赛都用这个比例做视频」。

    自动链的美网草稿转正时**机器自己带上**带式两件套——模型和终审都不用记得：
    layout: band + scorebox（五盘满列宽度，reel_facts.US_OPEN_SCOREBOX 单一
    出处）。parse_segments 那头有同一判据的硬闸兜着——这里漏了注入，转正时
    validate_spec 会当场红，废不了片但会卡住整条自动链。

    `score_inset` 跟着一起注入（每个非贴图段），因为不贴的代价是**名字被画面
    左缘裁掉**——账号所有者 2026-08-28：「你这比分板没展示全啊」。居中窗口固定
    切掉板左边 208px（正是名字那一段），所以回贴是这条线的默认，不是可选项。

    ⚠️ 注入走 `setdefault`：终审显式写 `false` 的段（比如画面主体正好压在
    左下角那几段）要**原样保住**——自动注入不许把人已经想清楚的决定盖掉。

    反向钉一头：非美网的草稿（Demo Open）一个字段都不许多——注入的判据是
    line1 里的赛事，不是「所有自动草稿」。
    """
    promote = load("promote_reel_draft")
    fake = type("M", (), {"validate_spec": staticmethod(lambda spec: None)})()
    monkeypatch.setitem(sys.modules, "build_match_reel", fake)

    uso = _ready_draft(tmp_path)
    uso["_production"]["event"] = "US Open"
    uso["segments"][2]["score_inset"] = False   # 终审显式不要回贴的那一段
    # 手写的数据图段（stat_card）不是源片段，回贴对它没有意义——注入要跳过它
    uso["segments"].insert(3, {"stat_card": True, "seconds": 5, "narration": "手写的。"})
    # 手写的章节卡（title_card）同理：它进 parse_segments 走的是 image 那一支，
    # 带着 score_inset 会当场红——注入必须跳过它（反向验证：拆掉那个跳过就红）
    uso["segments"].insert(2, {"title_card": "手写章节", "seconds": 2.5})
    spec = promote.promote(uso)
    assert all("score_inset" not in s for s in spec["segments"] if s.get("stat_card"))
    assert spec["layout"] == "band"
    assert spec["scorebox"] == [104, 888, 736, 978]
    flags = [s.get("score_inset") for s in spec["segments"]
             if not (s.get("image") or s.get("stat_card") or s.get("title_card"))]
    assert all("score_inset" not in s for s in spec["segments"] if s.get("title_card"))
    assert flags.count(False) == 1 and flags.count(True) == len(flags) - 1, (
        f"回贴要自动注入，而终审显式写的 false 要原样保住：{flags}")

    plain = promote.promote(_ready_draft(tmp_path))
    assert "layout" not in plain and "scorebox" not in plain
    assert all("score_inset" not in s for s in plain["segments"])


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


def test_喂给模型的教材里不许出现会被措辞闸拦下的写法():
    """**给模型看的每一个词，它都可能照着产。** 所以教材和 prompt 里一个被闸
    拦的写法都不许出现——连当反例写都不行。

    ⚠️ 来路：2026-09-01 轮次翻面（8 强 / 4 强 / 决赛）那一轮，闸、扫描面、
    两条机械拼串的路都修了，**独独漏了模型自己写的字这条路**——而那才是旁白
    和文案的主要产出口。当时的实况是：`skills/` 里**一个字都没教**轮次叫法，
    而 prompt 里唯一的轮次例句写着旧写法（「打进半决赛」）。模型只能照着训练
    数据和那句例句产旧写法 → `check_spec_wording` 拦下 → 草稿转不了正 →
    **链子静静卡住，而它长得像「今天没有候选」**。

    判据**自己从闸推**，不维护名单：闸拦什么，教材里就不许出现什么。
    查的是**真拼出来的那份 prompt**（`_SYSTEM_RULES` ＋ SKILL.md ＋
    references/deepseek.md ＋ references/quality-gates.md），不是某个文件的
    源码——查产物不查信号。

    ⚠️ 所以教材里这条规矩**只写正例**（「只能写 决赛/4强/8强/16强/第N轮」），
    不列反例：列反例既会被这条判据拦下，也真的会让模型 pattern-match 到那个词。
    """
    from tools.spec_wording import FRACTION_ROUND, LOVE_GAME  # noqa: PLC0415

    draft = load("draft_spec")
    for name, text in (("旁白 prompt", draft.system_prompt()),
                       ("推送 prompt", draft.push_system_prompt())):
        for label, pattern in (("轮次", FRACTION_ROUND), ("爱局", LOVE_GAME)):
            hits = sorted({m.group(0) for m in pattern.finditer(text)})
            assert not hits, (
                f"{name} 里出现了会被{label}那道闸拦下的写法：{hits}——"
                f"模型会照着产，然后草稿转不了正、链子静静卡住。"
                f"教材里这条只写正例，别列反例。")

    # 而且**整份教材里要真的教过**新写法——只删掉旧写法的话，模型没有任何
    # 地方学得到，它会照训练数据的习惯产旧写法，然后照样撞闸。
    # ⚠️ 这一头查的是拼出来的整份 prompt（`_SYSTEM_RULES` 和教材都算），
    # 不是某个文件的某两行——只删其中一处它仍然成立，那是对的：教到就行。
    whole = draft.system_prompt()
    assert "4强" in whole and "8强" in whole, \
        "教材里要正面写出允许的轮次写法，不能只是不出现旧写法"


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
    需要教材从 import 图自己推（直接或间接沾这两个 skill 模块的都算，宁可保守：
    几个 markdown 的检出成本是零），不维护名单。

    ⚠️ **2026-08-29 补上 `interview_skill`：原来只认 `reel_skill`，于是这条闸
    只盖住了 reel 那一半。** `draft_interview_spec.py` 走的是
    `from interview_skill import model_instructions`，而 `oncourt-interviews.yml`
    的 `draft` job 稀疏检出没有 `skills`——真跑起来死在

        FileNotFoundError: missing interview production skill resource:
          skills/tennis-interview-production/SKILL.md

    ⚠️ 它一直被排在前面的另一个坑挡着（那个 job 还缺 ffmpeg，#653 修的），
    **ffmpeg 一补上，这个立刻就露出来了**——同一条路上排队的第二个障碍，
    不是回归。「修了一个不等于修了那一类」这次是判据自己犯的：判据推导的
    起点写死成一个模块名，另一条线用另一个名字就整个漏过去。
    """
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

    #: 两条线各有一份教材，**两个都要认**——只认一个的话另一条线整个漏过去。
    SKILL_MODULES = {"reel_skill", "interview_skill"}
    graph = {name: imported(name) & (set(tool_files) | SKILL_MODULES)
             for name in tool_files}

    def needs_skill(name: str, seen: frozenset = frozenset()) -> bool:
        if name in SKILL_MODULES:
            return True
        if name in seen or name not in graph:
            return False
        return any(needs_skill(m, seen | {name}) for m in graph[name])

    needy = {n for n in tool_files if needs_skill(n)}
    # 判据自己的判据：推导空了要出声，不许变一盏恒真的绿灯
    assert {"draft_spec", "assemble_spec", "analyze_reel_visuals",
            "refresh_reel_cover", "draft_interview_spec"} <= needy, needy

    # ⚠️ **按 job 扫，不按文件扫。** 稀疏检出是每个 job 各配一份的，而按整份
    # 文件扫只要求「这个文件里某处有 skills」——`oncourt-interviews.yml` 有
    # collect / draft 两个 job 各带一份检出，只给其中一个补上，按文件扫照样绿，
    # 而线上照炸。「只测行为拦不住位置错」在这条判据自己身上的实例。
    # 收紧时量过：9 个 job 全过，零误伤。
    checked = 0
    for wf in sorted((ROOT / ".github/workflows").glob("*.yml")):
        after_jobs = wf.read_text("utf-8").split("\njobs:", 1)[-1]
        for m in re.finditer(
                r"\n  ([a-z0-9_-]+):\n(.*?)(?=\n  [a-z0-9_-]+:\n|\Z)",
                after_jobs, re.S):
            job, body = m.group(1), m.group(2)
            used = {x.group(1) for x in re.finditer(r"tools/(\w+)\.py", body)}
            if not (used & needy) or "sparse-checkout" not in body:
                continue   # 不跑这些工具，或全量检出（自然带 skills）
            checked += 1
            assert re.search(r"^\s+skills\s*$", body, re.M), (
                f"{wf.name}::{job} 跑 {sorted(used & needy)}，稀疏检出却没有 "
                "skills——import 现在是安全的，但真起草/审视觉证据那一刻要读教材")
    assert checked >= 8, f"只校到 {checked} 个 job，判据的主语丢了"


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


def test_大满贯男子的第三盘不是决胜盘():
    """账号所有者 2026-08-31：「大满贯男子是五盘三胜，所以吴易昺第三盘不是
    决胜盘，也不是输了就输了」。

    来路：`wu-walton-us-open-2026-r1`（美网男单首轮，7-6(2) 6-2 7-5）的旁白
    和小红书正文都把第三盘叫「决胜盘」，还跟了一句「输掉这一局比赛就结束了」
    ——4-5 那一局输掉只是丢掉这一盘（2-1），比赛不会结束。

    ⚠️ **它一路过了所有闸，因为这条线上 95% 的片子是三盘两胜**（WTA 全部 ＋
    ATP 巡回赛）：「第三盘＝决胜盘」是一个默认成立到不会被怀疑的习惯，
    而它恰恰在大满贯男子这一档是错的。

    判据三头，缺哪一头它都会变成误报机器或者一盏绿灯：
    ① 男子大满贯没打满五盘时提「决胜盘」要红；
    ② 打满五盘的不许误伤（第五盘真是决胜盘）；
    ③ 女子大满贯 / 巡回赛（三盘两胜）不归它管——存量扫过 4 条两盘却提
       「决胜盘」的，**全是在讲别的比赛**（上一轮、交手史、一个没发生的
       假设），机器分不出「这一场」和「另一场」，宽到那一档就是天天误报。
    """
    facts = load("reel_facts")

    def spec(result, *, heads=("atp-A.png", "atp-B.png"), event="2026 美网 第一轮",
             text="决胜盘 4-5 他一个盘点没给"):
        return {
            "slug": "闸自己的用例",
            "topbar": {"line1": event, "line2": "甲 乙"},
            "cover": {"result": result, "winner": "甲", "hook": text},
            "stats": {"a": {"headshot": f"assets/players/headshots/{heads[0]}"},
                      "b": {"headshot": f"assets/players/headshots/{heads[1]}"}},
        }

    # ① 男子大满贯 + 三盘 → 红
    problem = facts.decider_set_problem(spec("7-6 6-2 7-5"))
    assert problem and "五盘三胜" in problem, problem
    assert "第三盘" in problem, "报错要给出路（写第三盘/第四盘），不能只说不行"
    # 四盘也一样不是决胜盘
    assert facts.decider_set_problem(spec("6-4 3-6 6-2 7-5"))

    # ② 真打满五盘 → 第五盘就是决胜盘，不许误伤
    assert facts.decider_set_problem(spec("6-4 3-6 6-2 4-6 7-5")) is None
    # 退赛不判：领先方退赛时赢家可以一个完赛盘都没有
    assert facts.decider_set_problem(spec("6-4 2-1 Ret.")) is None

    # ③ 三盘两胜那一档不归它管（女子大满贯 / 巡回赛都不许红）
    assert facts.decider_set_problem(
        spec("6-2 7-5", heads=("wta-A.png", "wta-B.png"))) is None
    assert facts.decider_set_problem(
        spec("6-2 7-5", event="2026 辛辛那提 第二轮")) is None
    # 没写「决胜盘」当然不红
    assert facts.decider_set_problem(spec("7-6 6-2 7-5", text="三个盘点一个没给")) is None
    # 认领了就放行（真要提别的比赛的决胜盘）
    claimed = dict(spec("7-6 6-2 7-5"), _decider_why="讲的是上一轮那场")
    assert facts.decider_set_problem(claimed) is None

    # 小红书正文也要扫得到——正文是另一个出口，spec 干净不代表它干净
    assert facts.decider_set_problem(
        spec("7-6 6-2 7-5", text="三个盘点一个没给"),
        ["真正的分水岭在决胜盘 4-5。"])


def test_存量里没有一条踩到五盘三胜那个坑():
    """上面那道闸装上当天扫全库的结果：**176 条 spec，命中 0**。

    这条钉的是「零误伤」这件事本身——判据要是哪天被放宽（比如把三盘两胜
    那一档也收进来），存量里那 4 条讲别的比赛的决胜盘会当场变成误报，
    而误报比没有判据更糟：人会写豁免去压噪音，把它唯一想拦的那一类
    一起关掉。
    """
    facts = load("reel_facts")
    offenders, checked = [], 0
    for path in sorted(Path("specs/reels").glob("*.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(spec, dict) or "cover" not in spec:
            continue
        checked += 1
        xhs = path.parent / f"{path.stem}.xhs.txt"
        extra = [xhs.read_text(encoding="utf-8")] if xhs.is_file() else []
        if facts.decider_set_problem(spec, extra):
            offenders.append(path.stem)
    # 判据自己的判据：主语没了要出声，而不是变成一条恒真的绿灯
    assert checked >= 150, f"只扫到 {checked} 条 spec，扫描范围坏了"
    assert not offenders, f"这几条把没打满五盘的大满贯男子比赛写成了决胜盘：{offenders}"


def test_抢七小分进机械链_事实重建带N注脚():
    """⭐ 账号所有者 2026-08-31（甩来美网官方比分图）：「封面比分板上抢七
    没有小分啊」。板和数据图的 `.tb` 上标机制早就有，可 result_verified 的
    spec **结构性写不了小分**——老 verified_result_problem 要求 cover.result
    逐字等于只按局数重建的赛果，德约那条只好留一句「cover.result 不带抢七
    小分」的注解。顺带一个更深的洞：df_mh_1 **不列抢七那一局**，
    final_set_scores 对抢七盘只能取到 6-6，带抢七的比赛在自动链上整场判
    不出赢家（home_sets == away_sets → verified_match_fact 返回 None）。

    reconcile_sets 拿 df_sui_1 的 IG/IH 一次补两个洞（语义两场四抢七实证，
    见 match_feed._parse_set_pairs）；verified_match_fact 带 tiebreaks 之后
    winner/loser 两份赛果都带 (N)，N＝输掉那一盘的人的小分、不随视角翻。
    """
    facts = load("reel_facts")
    # 德约-纳沃内的真实形状：逐局表首盘停在 6-6，sui 给小分 7/5
    scores = [(6, 6), (5, 7), (4, 6), (6, 2), (6, 1)]
    sui = [(7, 5), (5, 7), (4, 6), (6, 2), (6, 1)]
    fixed, tiebreaks = facts.reconcile_sets(scores, sui)
    assert fixed == [(7, 6), (5, 7), (4, 6), (6, 2), (6, 1)]
    assert tiebreaks == [(7, 5), None, None, None, None]
    fact = facts.verified_match_fact(
        [{"name": "纳沃内"}, {"name": "德约科维奇"}], fixed, "hbCCx5Fj",
        tiebreaks=tiebreaks)
    assert fact["winner_result"] == "7-6(5) 5-7 4-6 6-2 6-1"
    assert fact["loser_result"] == "6-7(5) 7-5 6-4 2-6 1-6"
    assert fact["tiebreaks_home_away"] == [[7, 5], None, None, None, None]

    # 穆纳尔-阿特曼（账号所有者截图那场）：两个抢七，含逐局表已是 7-6 的档
    scores2 = [(6, 7), (3, 6), (6, 1), (7, 6), (7, 5)]
    sui2 = [(5, 7), (3, 6), (6, 1), (7, 4), (7, 5)]
    fixed2, tb2 = facts.reconcile_sets(scores2, sui2)
    assert fixed2 == scores2 and tb2 == [(5, 7), None, None, (7, 4), None]

    # 对不上就 None，不猜：sui 的小分方向和盘的赢家相反
    assert facts.reconcile_sets([(6, 6)], [(5, 7)]) is not None  # away 赢 TB → 6-7 ✓
    assert facts.reconcile_sets([(7, 6)], [(5, 7)]) is None      # 局数说 home 赢
    assert facts.reconcile_sets([(6, 3)], [(6, 4)]) is None      # 普通盘对不上
    # 抢七不可能 7-6 结束：一对 (7,6) 只能是局数，认不出小分 → None
    assert facts.reconcile_sets([(6, 6)], [(7, 6)]) is None


def test_verified闸校验小分的值_旧match不带小分栏也不误伤():
    facts = load("reel_facts")

    def spec_of(result: str, tb=None, winner_result=None):
        match = {
            "status": "result_verified",
            "participants": ["纳沃内", "德约科维奇"],
            "set_scores_home_away": [[7, 6], [6, 2]],
            "winner": "纳沃内", "loser": "德约科维奇",
            "winner_result": winner_result or result,
        }
        if tb is not None:
            match["tiebreaks_home_away"] = tb
        return {"_match": match, "cover": {"winner": "纳沃内", "result": result}}

    # 带小分栏：逐字机械比对，(N) 写错当场红
    ok = spec_of("7-6(5) 6-2", tb=[[7, 5], None])
    assert facts.verified_result_problem(ok) is None
    bad_n = spec_of("7-6(3) 6-2", tb=[[7, 5], None], winner_result="7-6(3) 6-2")
    assert "不一致" in (facts.verified_result_problem(bad_n) or "")
    # 非抢七盘写小分 / 小分不是合法抢七结果，都要说清楚
    assert "不是抢七盘" in facts.verified_result_problem(
        spec_of("7-6(5) 6-2", tb=[None, [7, 5]]))
    assert "不是一个合法的抢七结果" in facts.verified_result_problem(
        spec_of("7-6(5) 6-2", tb=[[7, 6], None]))
    # 旧 _match 没有小分栏：(N) 剥掉再比，手补的小分不许被顶回去
    legacy = spec_of("7-6(5) 6-2", winner_result="7-6 6-2")
    assert facts.verified_result_problem(legacy) is None


def test_抢七盘不带小分就红_全库扫描只剩豁免表那几条():
    """7-6 的盘必然打过抢七（6-6 才进抢七），裸的 7-6 永远是漏。已发的
    7 条挂豁免（已发不重渲；重渲会撞 validate_spec 里那道不豁免的闸），
    **只许减不许加**，表自带自检——slug 要真的存在、真的还裸着。"""
    facts = load("reel_facts")
    assert "抢七" in (facts.bare_tiebreak_problem(
        {"cover": {"result": "7-6 6-2"}}) or "")
    assert "抢七" in (facts.bare_tiebreak_problem(
        {"cover": {"result": "6-7 2-1 Ret."}}) or "")
    for ok in ("7-6(5) 6-2", "7-5 6-2", "6-7(4) 7-6(10) 6-1", "6-0 4-0 退赛"):
        assert facts.bare_tiebreak_problem({"cover": {"result": ok}}) is None, ok

    import glob  # noqa: PLC0415

    # 豁免表只有一份出处（闸自己消费的那份）；这里把 slug 挖空让检测器
    # 绕过豁免真扫一遍——测的是检测器，不是豁免。
    legacy = facts.LEGACY_BARE_TIEBREAK
    checked, hits, stale = 0, [], set(legacy)
    for f in glob.glob(str(ROOT / "specs" / "reels" / "*.json")):
        spec = json.loads(Path(f).read_text(encoding="utf-8"))
        slug = Path(f).stem
        if (spec.get("cover") or {}).get("result"):
            checked += 1
        if facts.bare_tiebreak_problem({**spec, "slug": ""}):
            if slug in legacy:
                stale.discard(slug)
            else:
                hits.append(slug)
        # 闸对豁免名单真的放行（已发的不为小分重渲）
        if slug in legacy:
            assert facts.bare_tiebreak_problem({**spec, "slug": slug}) is None
    assert checked >= 100, f"只校到 {checked} 条——主语没了"
    assert hits == [], f"这些 spec 的抢七盘没带小分：{hits}"
    assert not stale, f"豁免表里这些已经不裸了/不存在了，从表里删掉：{stale}"


def test_小分闸在渲染入口就红():
    """闸装在 _topbar_lines（validate_spec 调它，dry-run 0.2 秒就走到）。"""
    sys.path.insert(0, str(TOOLS))
    import build_match_reel as reel  # noqa: PLC0415

    spec = {"slug": "fresh-tb-spec",
            "cover": {"eyebrow": "赛场之上", "winner": "纳沃内",
                      "result": "7-6 6-2"},
            "topbar": {"line1": "2026 美网 第一轮",
                       "line2": "纳沃内 7-6 6-2 德约科维奇"}}
    with pytest.raises(reel.ReelError, match="抢七"):
        reel._topbar_lines(spec)


def test_大满贯决胜盘是抢十分男女都一样():
    """⭐ 账号所有者 2026-09-01：「大满贯决胜盘 tiebreak 是抢十分的赛制，
    男女都一样。要记住咯」。2022 年起四大满贯统一：决胜盘 6-6 抢 10 分，
    其余盘照旧抢 7。

    ⚠️ **这个错渲出来一个像素都看不出来**——注脚 (N) 是输掉那一盘的人拿到
    的分，10-5 和 7-5 都印成 7-6(5)，机械重建的 winner_result 逐字节相同
    （下面第 ② 组钉的就是这一点）。老判据只要求 `max >= 7`，两个值一起放行。

    对照组全是**官方 feed 的真实数据**（美网 day8/day9 tiebreakDisplay）：
    女单 2-0 那两场第 2 盘 7-4 / 8-6 是普通盘抢 7——**末盘 ≠ 决胜盘**，
    拿「最后一盘」当判据会把它们误判。
    """
    facts = load("reel_facts")

    def spec(sets, tb, slug="x-us-open-2026-r1", result="", topic=""):
        return {"slug": slug, "cover": {"result": result, "topic": topic},
                "_match": {"set_scores_home_away": sets,
                           "tiebreaks_home_away": tb}}

    # ① 决胜盘赢家没到 10 → 红（rublev-virtanen 那次记的正是 7-5）
    five = [[6, 7], [6, 7], [6, 0], [6, 2], [7, 6]]
    for bad in ([7, 5], [9, 7], [8, 6]):
        msg = facts.decider_tiebreak_problem(
            spec(five, [[5, 7], [0, 7], None, None, bad])) or ""
        assert "决胜盘" in msg and "抢 10 分" in msg, (bad, msg)
    assert facts.decider_tiebreak_problem(
        spec(five, [[5, 7], [0, 7], None, None, [10, 5]])) is None

    # ② 为什么非要一道闸：两个值渲出来逐字节相同
    def rebuilt(tb5):
        return facts.verified_match_fact(
            [{"name": "卢布列夫"}, {"name": "维尔塔宁"}],
            [tuple(s) for s in five], "YTRmDEf5",
            tiebreaks=[(5, 7), (0, 7), None, None, tuple(tb5)])["winner_result"]
    assert rebuilt([7, 5]) == rebuilt([10, 5]) == "6-7(5) 6-7(0) 6-0 6-2 7-6(5)"

    # ③ 女单决胜盘同样抢 10（官方 feed：第 3 盘 7:10）
    w3 = [[6, 4], [4, 6], [6, 7]]
    assert facts.decider_tiebreak_problem(
        spec(w3, [None, None, [7, 10]])) is None
    assert facts.decider_tiebreak_problem(spec(w3, [None, None, [5, 7]]))

    # ④ 对照组，一个都不许误伤
    ok = [
        # 末盘 ≠ 决胜盘：女单 2-0 的第 2 盘是普通盘（官方 feed 真实小分）
        (spec([[6, 0], [7, 6]], [None, [7, 4]]), "女单 2-0 第 2 盘"),
        (spec([[2, 6], [6, 7]], [None, [6, 8]]), "女单 0-2 第 2 盘"),
        # 男单 3-1：第 4 盘不是决胜盘
        (spec([[4, 6], [7, 6], [6, 1], [6, 4]], [None, [7, 3], None, None]),
         "男单 3-1 的抢七盘"),
        # 非大满贯：巡回赛决胜盘就是抢 7
        (spec([[6, 4], [4, 6], [7, 6]], [None, None, [7, 5]],
              slug="z-cincinnati-2026-r1"), "巡回赛决胜盘"),
        # ⭐ 打满了五盘，可抢七在**第 1 盘**不在决胜盘（djokovic-navone 的真形状）
        (spec([[7, 6], [5, 7], [4, 6], [6, 2], [6, 1]],
              [[7, 5], None, None, None, None]), "打满但抢七不在末盘"),
        # 男单 3-0 横扫：前两盘的抢七是普通盘（berrettini-wawrinka 的真形状）
        (spec([[7, 6], [7, 6], [6, 0]], [[7, 4], [7, 3], None]), "3-0 横扫"),
        # 决胜盘没打抢七 / 没有 _match / 对不齐
        (spec([[6, 4], [4, 6], [6, 1]], [None, None, None]), "决胜盘不是抢七"),
        ({"slug": "w-us-open-2026-r1", "cover": {"result": "6-4 4-6 7-6(5)"}},
         "没有 _match"),
        (spec(five, [[5, 7]]), "小分栏对不齐（归 verified_result_problem 报）"),
    ]
    for s, label in ok:
        assert facts.decider_tiebreak_problem(s) is None, label
    # 退赛的盘数形状本来就不是打满
    ret = spec(five, [[5, 7], [0, 7], None, None, [7, 5]], result="… Ret.")
    assert facts.decider_tiebreak_problem(ret) is None

    # ⑤ 判据自己的判据：全库零命中（新写的 spec 撞上它才该红）
    import glob  # noqa: PLC0415

    checked, hits = 0, []
    for f in glob.glob(str(ROOT / "specs" / "reels" / "*.json")):
        s = json.loads(Path(f).read_text(encoding="utf-8"))
        # ⚠️ 有 spec 的 _match 是一句注解（字符串）不是对象——闸自己
        # isinstance 挡住了，扫描这头也要挡，否则测试红在自己身上
        m = s.get("_match")
        if isinstance(m, dict) and m.get("tiebreaks_home_away"):
            checked += 1
        if facts.decider_tiebreak_problem(s):
            hits.append(Path(f).stem)
    assert checked >= 4, f"只校到 {checked} 条带小分的 spec——主语没了"
    assert hits == [], f"这些 spec 的大满贯决胜盘小分不到 10：{hits}"


def test_决胜盘抢十那道闸在渲染入口就红():
    """和小分闸同一个座位（_topbar_lines，validate_spec 调它，dry-run 就走到）
    ——只测行为拦不住「闸装在下载源片之后」那一类。"""
    sys.path.insert(0, str(TOOLS))
    import build_match_reel as reel  # noqa: PLC0415

    spec = {"slug": "fresh-decider-spec",
            "cover": {"eyebrow": "赛场之上", "winner": "卢布列夫",
                      "result": "6-7(5) 6-7(0) 6-0 6-2 7-6(5)"},
            "topbar": {"line1": "2026 美网 第一轮",
                       "line2": "卢布列夫 6-7(5) 6-7(0) 6-0 6-2 7-6(5) 维尔塔宁"},
            "_match": {"set_scores_home_away":
                       [[6, 7], [6, 7], [6, 0], [6, 2], [7, 6]],
                       "tiebreaks_home_away":
                       [[5, 7], [0, 7], None, None, [7, 5]]}}
    with pytest.raises(reel.ReelError, match="抢 10 分"):
        reel._topbar_lines(spec)


def test_df_sui_1的每盘数字解析出IG_IH对():
    """真实 feed 的形状（块间 ~、字段 ¬）；缺字段的块给 (-1,-1) 出声占位，
    别静默丢——丢了和逐局表对齐就错位，reconcile 会拿错盘的小分。"""
    mf = load("match_feed")
    text = ("~AC÷Set 1¬IG÷5¬IH÷7¬RC÷1:15¬"
            "~AC÷Set 2¬IG÷3¬IH÷6¬RD÷0:37¬"
            "~AC÷Set 3¬IG÷6¬RE÷0:36¬"
            "~RB÷4:36¬")
    assert mf._parse_set_pairs(text) == [(5, 7), (3, 6), (-1, -1)]
