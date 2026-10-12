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
    previous = sys.modules.get(name)
    sys.modules[name] = module  # dataclass 注解解析要回 sys.modules 查本模块
    try:
        spec.loader.exec_module(module)
    finally:
        # 只在 exec 期间登记，装完把先前那份还回去（先前没有就保持原样）。
        # 留着不还会把别的测试正常 import 的那份顶掉：新这份带着它 exec 那一刻
        # 读到的模块级状态（如 reel_facts.REEL_LEDGER_DIR＝真账本路径），而别的
        # 测试 monkeypatch 的是老那份、`validate_spec` 调用时现 import 拿到的
        # 却是新这份——判据测试就这么静静读了真账本（CI run 38249109896：
        # test_time_sensitive_facts 排在本文件之后跑就红，换个 worker 顺序就绿）。
        if previous is not None:
            sys.modules[name] = previous
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


def _ready_draft(tmp_path: Path) -> dict:
    # 真图，不是占位字节：`validate_spec` 现在要把引用的每张图解到底
    # （tools/reel_asset_gates.py，zheng-you 那张半截 PNG 白渲两趟之后加的）
    from PIL import Image
    photo = tmp_path / "cover.jpg"
    Image.new("RGB", (1600, 2000), (40, 90, 60)).save(photo, "JPEG")  # 撑得满 1080×1440
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


def test_promote转正时完整收官后全画布展示数据10秒(tmp_path):
    """review 路线 ④：131 条已发 spec 带 stats、0 条烧进片子。起草工具不写
    segments，所以证据段也机械插——收官段之前、旁白只讲总得分（汉字数字给
    TTS 念、方向机械算）。三个不插的情形都是确定性的，各验一头。"""
    promote = load("promote_reel_draft")
    spec = promote.promote(_ready_draft(tmp_path))
    segs = spec["segments"]
    card = [s for s in segs if s.get("stat_card")]
    assert len(card) == 1 and segs[-1] is card[0] and "start" in segs[-2]
    assert spec["stat_card_full_canvas"] is True
    assert card[0]["narration"] == "全场总得分，乙六十七比五十六，多拿了十一分。"
    assert card[0]["seconds"] == 10.0 and "score_inset" not in card[0]
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
    """review 路线 ⑤（学「小丝瓜🎾」的 01/02/03 章节页）：起草合同多一个
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
def test_数据图那段的旁白方向机械算持平也说得通():
    promote = load("promote_reel_draft")
    m = [{"name": "甲"}, {"name": "乙"}]
    assert promote.stat_card_narration({"a": {"pts_won": 80}, "b": {"pts_won": 71}}, m) \
        == "全场总得分，甲八十比七十一，多拿了九分。"
    assert promote.stat_card_narration({"a": {"pts_won": 60}, "b": {"pts_won": 60}}, m) \
        == "全场总得分六十比六十，一分不差。"
    assert promote.stat_card_narration({"a": {}, "b": {"pts_won": 60}}, m) == ""


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


def test_promote_合集源片里的另一场球不算同一场(tmp_path, monkeypatch):
    """Tennis TV 把同一天两场半决赛剪进一条集锦（2026-09-28 杭州 `nSaTYP-T8sM`「Rublev vs
    Jacquet & Medvedev vs Safiullin」）：源片那把钥匙对上了，两条讲的却是两场球。两条都记了
    flashscore 场次 id、id 不同就放行；同一个 id、或者草稿没记 id，照旧拦。"""
    promote = load("promote_reel_draft")
    published = tmp_path / "formal"
    published.mkdir()
    (published / "rublev-jacquet.json").write_text(json.dumps({
        "slug": "rublev-jacquet", "source_url": "https://www.youtube.com/watch?v=nSaTYP-T8sM",
        "_match": {"flashscore_id": "M7514hNb"}, "cover": {"eyebrow": "赛场之上"},
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(promote, "FORMAL", published)

    def reasons(fsid):
        draft = _ready_draft(tmp_path)
        draft["sources"] = {"ttv": "https://youtu.be/nSaTYP-T8sM"}
        draft["source_url"] = "https://youtu.be/nSaTYP-T8sM"
        draft["_match"]["flashscore_id"] = fsid
        return [r for r in promote.waiting_reasons(draft) if "已经有正式" in r]

    assert reasons("QmOLdkIG") == [], "合集源片里的另一场球被当成同一场拦了"
    assert reasons("M7514hNb"), "同一个场次 id——就是同一场，要拦"
    assert reasons(""), "没记场次 id 时只剩源片认得出——不许放行"


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


def test_promote全出血草稿按probe的框注入比分板回贴(tmp_path, monkeypatch):
    """账号所有者 2026-09-24（杭州 bu-zheng）：全出血也把转播比分板贴边、同比放大
    贴回左下，「后续比赛也要用同样的方式把这个能力固定下来」。

    自动 spec 在 parse_segments 那头只报不拦，所以注入必须在转正时自己做：
    scorebox 取 probe 的 scorebox_guess，**右缘预留两列盘分**（猜的那一帧是
    首盘的板，渲染时右缘封顶在 x1——按猜的写会把第二盘长出来的列裁掉）。
    没有 probe 或猜不出框就什么都不加；终审显式写的 false 原样保住。
    """
    promote = load("promote_reel_draft")
    fake = type("M", (), {"validate_spec": staticmethod(lambda spec: None)})()
    monkeypatch.setitem(sys.modules, "build_match_reel", fake)

    draft = _ready_draft(tmp_path)
    draft["_production"]["event"] = "Singapore"          # 标定过的转播（WTA500）
    draft["segments"][1]["score_inset"] = False
    draft["segments"].insert(2, {"title_card": "手写章节", "seconds": 2.5})
    probe = {"scorebox_guess": "98,920,405,1029", "width": 1920}
    spec = promote.promote(draft, probe)
    assert "layout" not in spec, "全出血不改版式"
    assert spec["scorebox"] == [98, 920, 405 + promote.FULLBLEED_SCOREBOX_GROW, 1029]
    flags = [s.get("score_inset") for s in spec["segments"]
             if not (s.get("image") or s.get("stat_card") or s.get("title_card"))]
    assert flags.count(False) == 1 and flags.count(True) == len(flags) - 1, flags
    assert all("score_inset" not in s for s in spec["segments"] if s.get("title_card"))

    assert promote.fullbleed_scorebox(None) is None
    assert promote.fullbleed_scorebox({"scorebox_guess": ""}) is None
    assert promote.fullbleed_scorebox({"scorebox_guess": "a,b,c,d"}) is None
    assert promote.fullbleed_scorebox(
        {"scorebox_guess": "1800,900,1900,1000", "width": 1920})[2] == 1920, "右缘不许越过画幅"


def test_promote认不出转播的全出血草稿不注入回贴(tmp_path, monkeypatch):
    """账号所有者 2026-09-24「那去彻底解决啊」：比分板回贴只认标定过的转播，
    认不出的在渲染时报错、不再退回老的整段矩形回贴（「狗皮膏药」「右边多一块补丁」）。
    自动链不能因此卡成「今天没有候选」，所以转正时**不注入**，只记一句为什么。"""
    promote = load("promote_reel_draft")
    fake = type("M", (), {"validate_spec": staticmethod(lambda spec: None)})()
    monkeypatch.setitem(sys.modules, "build_match_reel", fake)
    draft = _ready_draft(tmp_path)                      # 「Demo Open」：没标定过
    spec = promote.promote(draft, {"scorebox_guess": "98,920,405,1029", "width": 1920})
    assert "scorebox" not in spec
    assert not any(s.get("score_inset") for s in spec["segments"])
    assert "不是标定过的转播" in spec["_score_inset_why"]


def test_workflow只有正式ready才从probe派发render():
    body = (ROOT / ".github/workflows/match-reel.yml").read_text(encoding="utf-8")
    step = body.split("probe 正式 spec 就绪后自动派发 render", 1)[1].split(
        "render 质检落库后读取 spec", 1)[0]
    # 判据 2026-09-28 挪进 tools/probe_dispatch_gate.py（手写 spec 不再裸 assert，
    # run 36331363124）；ready ＋ push.auto 的合同在那边，这里钉接线
    assert "tools/probe_dispatch_gate.py" in step
    gate = (ROOT / "tools/probe_dispatch_gate.py").read_text(encoding="utf-8")
    assert 'status != "ready_for_render"' in gate and '.get("auto") is not True' in gate
    assert "[waiting]" in gate
    assert "gh workflow run match-reel.yml --ref main" in step
    assert "-f mode=render" in step


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


def test_算术闸拒绝数字都真实但差值算错():
    """`arithmetic_claim_problem` 原来在已删除的起草工具里，2026-10-12 随
    机械半截搬进 `assemble_spec`——判据不变：数字都是真的、差值算错也要拦。"""
    asm = load("assemble_spec")
    wrong = {"beats": ["总得分五十六比四十五只领先九分。"]}
    right = {"beats": ["总得分五十六比四十五领先十一分。"]}
    assert "相差11分" in asm.arithmetic_claim_problem(wrong)
    assert asm.arithmetic_claim_problem(right) is None


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


def test_promote转正时剥掉备料重跑的账(tmp_path):
    """`_feed_retry` 是草稿专用的账（flashscore 哪几块还欠着，reel-auto-ready 重跑用）。
    转正之后没有哪一班再重跑正式 spec，账留着只会让读的人以为还欠着什么（2026-09-28 D1）。"""
    promote = load("promote_reel_draft")
    draft = _ready_draft(tmp_path)
    draft["_feed_retry"] = {"blocks": ["hit_data"], "errors": {"hit_data": "SystemExit: HTTP 503"},
                            "tries": 3, "last_at": "2026-09-28T07:00:00Z",
                            "exhausted_at": "2026-09-28T07:00:00Z"}
    # 照片接口那一档的账（`refresh_reel_cover`：问过的开赛时刻、下过没过的、被视觉审核判掉的）同理
    draft["_cover_api"] = {"tried": ["https://x/a.jpg"], "rejected": ["https://x/b.jpg"],
                           "stuck_checked": "https://x/b.jpg#h1"}
    spec = promote.promote(draft)
    assert "_feed_retry" not in spec and "_draft" not in spec and "_cover_api" not in spec
