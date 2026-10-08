"""tools/promote_interview_draft.py —— 草稿提升（不联网，mock digest）。

核心判据：render 顶栏硬要求 `winner` 且在 `push.matchup` 里（build_interview_clip
1159 行的闸），所以提升必须从赛果反查对手——查不到就不提升，宁可留草稿。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture()
def tool(monkeypatch):
    sys.path.insert(0, str(_TOOLS))
    import promote_interview_draft as p  # noqa: PLC0415

    return p


def _match(home_name, away_name, winner_idx=0, *, event="", round_name=""):
    """造一个最小 Match 形状（home/away 各一个 Player，winner_players 返回赢家）。"""
    class _P:
        def __init__(self, name):
            self.name = name

    class _M:
        def __init__(self):
            self.home = [_P(home_name)]
            self.away = [_P(away_name)]
            self.winner = home_name if winner_idx == 0 else away_name
            self.round_name = round_name
            if event:
                self.tournament = type("Tournament", (), {"name": event})()

        def winner_players(self):
            return self.home if self.winner == self.home[0].name else self.away

    return _M()


def _draft(**extra):
    """能进入提升环节的最小 L0 草稿；正式签名由 promote 在赛果补齐后生成。"""
    base = {
        "_draft": True,
        "slug": "zverev-cincinnati-2026-r3",
        "url": "https://example.test/oncourt",
        "requested_content_type": "on_court",
        "interview_kind": "赛后场上采访",
        "event": "2026 辛辛那提大师赛",
        "zh": ["a"],
        "_interviewee_en": "Alexander Zverev",
        "match": {
            "id": "2026:cincinnati:r3:alexander-zverev",
            "event": "辛辛那提大师赛",
            "event_search": "Cincinnati Open",
            "year": 2026,
            "round": "第三轮",
            "interviewee_en": "Alexander Zverev",
        },
        "source_verification": {
            "status": "verified", "detected_type": "on_court",
            "method": "human_visual_verdict",
            "source_url": "https://example.test/oncourt",
            "evidence": [{"kind": "visual_verdict", "by": "test"}],
        },
    }
    base.update(extra)
    return base


def test_find_opponent按姓找对手(tool):
    """按 feed 姓氏找到对手，并采用实际译名 resolver 的统一结果。"""
    from tennislive.zh import player_zh

    class _Digest:
        results = [_match("Zverev A.", "Atmane T.")]

    winner = player_zh("Alexander Zverev")
    loser = player_zh("Terence Atmane")
    assert winner != "Alexander Zverev" and loser != "Terence Atmane"
    got = tool.find_opponent(_Digest(), "zverev")
    assert got == (winner, loser, f"{winner} vs {loser}")
    details = tool.find_match_details(_Digest(), "zverev")
    assert details["winner_en"] == "Zverev" and details["loser_en"] == "Atmane", \
        "feed 的 Surname X. 不能把 X. 当成集锦搜索姓氏"


def test_find_opponent受访者不是赢家返回None(tool):
    """赛后采访都是赢球后，受访者不是赢家就返回 None（别猜）。"""
    class _Digest:
        results = [_match("Atmane T.", "Zverev A.", winner_idx=0)]

    assert tool.find_opponent(_Digest(), "zverev") is None


def test_find_opponent赛果里没有这位球员返回None(tool):
    class _Digest:
        results = [_match("Sinner J.", "Alcaraz C.")]

    assert tool.find_opponent(_Digest(), "zverev") is None


def test_同姓同日多场必须用全名赛事轮次锁定(tool, monkeypatch):
    """不能拿 feed 第一条同姓结果凑对手；比赛身份必须同时吻合。"""
    class _Digest:
        results = [
            _match("Zhang S.", "Wrong A.", event="Montreal Open", round_name="Final"),
            _match("Zhang S.", "Right B.", event="Cincinnati Open", round_name="Semifinal"),
        ]

    draft = _draft(
        _interviewee_en="Shuai Zhang",
        match={
            **_draft()["match"],
            "id": "2026:cincinnati:sf:shuai-zhang",
            "round": "半决赛",
            "interviewee_en": "Shuai Zhang",
        },
    )
    monkeypatch.setattr(tool, "player_zh", lambda en: en)
    got = tool.find_match_details(_Digest(), "zhang", draft)
    assert got is not None and got["loser"] == "Right B."


def test_同姓结果仍有多条时拒绝猜第一条(tool):
    class _Digest:
        results = [_match("Zhang S.", "One A."), _match("Zhang S.", "Two B.")]

    assert tool.find_match_details(_Digest(), "zhang") is None


def test_promote补winner和push(tool):
    draft = _draft()
    spec = tool.promote(draft, ("兹维列夫", "阿特马内", "兹维列夫 vs 阿特马内"))
    assert "_draft" not in spec, "正式 spec 不带草稿标记"
    assert spec["winner"] == "兹维列夫"
    assert spec["push"]["matchup"] == "兹维列夫 vs 阿特马内"
    assert spec["push"]["auto"] is True, "质检通过即推送，不再等人工补开关"
    assert spec["zh"] == ["a"], "草稿已有的 zh 要保留"
    assert spec["source_verification"]["match_id"] == spec["match"]["id"]
    assert spec["source_verification"]["attestation_sha256"]


def test_promote给TennisTV草稿补台标那一挪_渲染闸放行(tool):
    """`check_tennistv_logo`（`main()` 开头）不写 `crop_shift_x` 就拦出片，而转正原来
    不补——main 上 winston-salem 三份 Tennis TV 草稿转正后会一条条停在那道闸上
    （2026-09-27 评审）。这个数是台标左沿推出来的，不是编辑口味，转正就补上。
    """
    import build_interview_clip as clip  # noqa: PLC0415

    tv = "https://www.tennistv.com/videos/x-on-court-interview"
    who = ("兹维列夫", "阿特马内", "兹维列夫 vs 阿特马内")
    draft = _draft(url=tv)
    draft["source_verification"] = dict(draft["source_verification"], source_url=tv)
    spec = tool.promote(draft, who)
    assert spec.get("crop_shift_x") == clip.TENNISTV_CROP_SHIFT, "转正没给 Tennis TV 草稿补台标那一挪"
    assert clip.tennistv_logo_problem(spec) is None, "补了还过不了渲染那道闸"
    assert "crop_shift_x" in (clip.tennistv_logo_problem(draft) or ""), "对照组：草稿本身过不了"

    kept = dict(draft, crop_shift_x=-0.1)
    assert tool.promote(kept, who).get("crop_shift_x") == -0.1, "人写过的不许覆盖"
    boxed = dict(draft, logo_box=[1, 2, 3, 4])
    assert "crop_shift_x" not in tool.promote(boxed, who), "走 logo_box 的不再挪窗口"
    assert "crop_shift_x" not in tool.promote(_draft(), who), "不是 Tennis TV 的不挪"


def test_promote保留给终审的注解键(tool):
    """`_zh_draft` / `_notes` 是写给终审的（机器译文参考、cap_asr 没有说话人
    标记的提醒）。旧版一刀剥掉全部 `_` 键，提示就这么丢过——只许剥
    `_draft` 这个状态标记。"""
    draft = _draft(slug="s", zh=[], _zh_draft=["机器译文"], _notes=["提醒"])
    spec = tool.promote(draft, ("兹维列夫", "阿特马内", "兹维列夫 vs 阿特马内"))
    assert "_draft" not in spec
    assert spec["_zh_draft"] == ["机器译文"]
    assert spec["_notes"] == ["提醒"]
    assert spec["_interviewee_en"] == "Alexander Zverev"


def test_受访者的姓从草稿里读不再从标题猜(tool, capsys):
    """draft_interview_spec 已经拿名册认过人（`_interviewee_en`），promote
    再从标题猜一遍就是两处各写一遍必分叉——而且标题猜那条在真实标题上
    几乎全错（受访者在开头、赛事名在结尾）。老草稿没有这个键才退回猜，
    **退路要出声**。"""
    got = tool._draft_surname(
        {"_interviewee_en": "Karen Khachanov",
         "source_title": "Karen Khachanov on-court interview | Hopman Cup 2018"},
        "x.draft.json")
    assert got == "khachanov", "主路读 _interviewee_en，标题里的 Hopman/Cup 不该掺和"
    # 老草稿：退回标题猜 + 出声
    tool._draft_surname(
        {"source_title": "Cincinnati 2026 R3 Zverev Interview"}, "old.draft.json")
    err = capsys.readouterr().err
    assert "老草稿" in err and "warning" in err, \
        "退路必须出声，不然查不到对手时没人怀疑姓认错了"


def test_没有草稿时不抓赛果(tool, monkeypatch, tmp_path):
    """**先看有没有草稿，再去抓赛果**。反过来（旧版）等于每一趟定时都白抓
    一轮网络赛果，而绝大多数趟根本没有草稿。"""
    specs = tmp_path / "specs" / "interviews"
    specs.mkdir(parents=True)
    monkeypatch.setattr(tool, "SPECS", specs)

    def _boom():
        raise AssertionError("没有草稿还去抓赛果")

    monkeypatch.setattr(tool, "_collect_digests", _boom)
    assert tool.promote_all(write=False) == ([], [])


def test_按天找人停在他第一次出现的那天(tool, monkeypatch, tmp_path):
    """今天他输了、前天他赢过——**不许翻到前天那场去提升**：那是另一场比赛，
    对阵整个错掉而且不吭声。判据：停在他第一次出现的那天，那天不是赢家
    就跳过。"""
    specs = tmp_path / "specs" / "interviews"
    specs.mkdir(parents=True)
    (specs / "zverev-cincinnati-2026-r3.draft.json").write_text(json.dumps({
        **_draft(),
        "_zh_draft": ["a"],
        "source_title": "Cincinnati 2026 R3 Alexander Zverev Interview"}),
        encoding="utf-8")
    monkeypatch.setattr(tool, "SPECS", specs)

    class _Today:
        results = [_match("Atmane T.", "Zverev A.", winner_idx=0)]  # 今天他输了

    class _Earlier:
        results = [_match("Zverev A.", "Nobody X.", winner_idx=0)]  # 前天他赢过

    monkeypatch.setattr(tool, "_collect_digests", lambda: [_Today(), _Earlier()])
    promoted, skipped = tool.promote_all(write=False)
    assert promoted == [], "不许翻到更早那天他赢的另一场"
    assert any("不是赢家" in s for s in skipped), skipped


def test_promote_all写盘时保留注解并删草稿(tool, monkeypatch, tmp_path):
    specs = tmp_path / "specs" / "interviews"
    specs.mkdir(parents=True)
    draft_p = specs / "zverev-cincinnati-2026-r3.draft.json"
    draft_p.write_text(json.dumps({
        **_draft(zh=[]),
        "_zh_draft": ["机器译文"],
        "source_title": "Cincinnati 2026 R3 Alexander Zverev Interview"}),
        encoding="utf-8")
    monkeypatch.setattr(tool, "SPECS", specs)

    class _Digest:
        results = [_match("Zverev A.", "Atmane T.", winner_idx=0)]

    monkeypatch.setattr(tool, "_collect_digests", lambda: [_Digest()])
    monkeypatch.setattr(tool, "player_zh", lambda en: {
        "Zverev A.": "兹维列夫", "Atmane T.": "阿特马内"}.get(en, en))
    promoted, skipped = tool.promote_all(write=True)
    assert promoted and not skipped, (promoted, skipped)
    assert not draft_p.exists(), "提升后草稿要删掉"
    spec = json.loads((specs / "zverev-cincinnati-2026-r3.json").read_text())
    assert spec["winner"] == "兹维列夫"
    assert spec["push"]["matchup"] == "兹维列夫 vs 阿特马内"
    assert spec["_zh_draft"] == ["机器译文"], "注解键要跟着进正式 spec"


# ── 自动收尾卡那一句要一行放得下（interview_spec_gates 那道闸的同一把尺）──────


def _top500_names() -> list[str]:
    table = json.loads((_TOOLS.parent / "src" / "tennislive" / "zh"
                        / "player_names_top500.json").read_text(encoding="utf-8"))
    return sorted({row["name_zh"] for rows in table["tours"].values()
                   for row in rows if row.get("name_zh")})


@pytest.mark.parametrize("win", [
    # review 量出来会折行的 top-100：WTA #5 / #19 / #25、ATP #25
    "米拉·安德烈耶娃", "亚历山德罗娃", "克雷吉茨科娃", "达维多维奇·福基纳",
])
def test_promote的自动收尾卡长名字也放得下一行(tool, win):
    """原模板 `{win}赢球后的第一反应` 在这几个名字上量出来 858~1002px，卡上一行当时只有
    838px（main 收左边距之后 860px，安德烈耶娃 940、福基纳 1002 照样放不下）——提升出来的
    spec 在 picker 预检和 render 的 check_takeaway 都红，而自动链没有任何一步会替它改短，
    只能永久躺在等待名单里。"""
    pytest.importorskip("PIL")
    import interview_spec_gates as gates  # noqa: PLC0415

    spec = tool.promote(_draft(), (win, "对手", f"{win} vs 对手"))
    point = spec["takeaway"]["close"]["point"]
    assert gates.takeaway_point_problems(spec) == [], point
    assert gates.point_width(point) <= gates.point_box_px()


def test_promote的自动收尾卡短名字照旧用全句(tool):
    """退路只在放不下时才用——放得下的名字不许被顺手砍短。"""
    pytest.importorskip("PIL")
    spec = tool.promote(_draft(), ("兹维列夫", "阿特马内", "兹维列夫 vs 阿特马内"))
    assert spec["takeaway"]["close"]["point"] == "兹维列夫赢球后的第一反应"


def test_promote的自动收尾卡_译名表里每个名字都放得下一行(tool):
    """全表扫：top-500 译名表里的每一个中文名，自动模板都要落在一行里。"""
    pytest.importorskip("PIL")
    import interview_spec_gates as gates  # noqa: PLC0415

    box = gates.point_box_px()
    too_wide = [(win, tool.auto_takeaway_point(win)) for win in _top500_names()
                if gates.point_width(tool.auto_takeaway_point(win)) > box]
    assert not too_wide, too_wide


def test_手改过的草稿带着没认领的全称断言_转正时留草稿(tool, monkeypatch, tmp_path):
    """转正之后 interview-clip 会被自动 dispatch，而前置检查里那道全称断言闸是
    硬的（`production_preflight.check_interview_claims`）。有人往 `.draft.json`
    里手补了文案、写了「N 次打进，N 次都…」却没在 `_claims` 认领两个源——拦在
    promote 这一关，草稿留在原地等终审，别让它变成一趟红着的 render。认领够了照常转正。

    ⚠️ 人工请求（`requests/interviews/*.json`）**不走这儿**：`build_interview_request`
    直接写正式 spec，它的闸在 `check_request`（`tests/test_absolute_claims.py`
    `test_人工请求的_claims跟进正式spec_没认领在build那一刻就红`）。"""
    specs = tmp_path / "specs" / "interviews"
    specs.mkdir(parents=True)
    claim = "他此前六次打进正赛，六次全部首轮出局。"
    base = {**_draft(), "_zh_draft": ["a"],
            "source_title": "Cincinnati 2026 R3 Alexander Zverev Interview",
            "push": {"lead": claim}}
    draft_p = specs / "zverev-cincinnati-2026-r3.draft.json"
    draft_p.write_text(json.dumps(base), encoding="utf-8")
    monkeypatch.setattr(tool, "SPECS", specs)

    class _Digest:
        results = [_match("Zverev A.", "Atmane T.", winner_idx=0)]

    monkeypatch.setattr(tool, "_collect_digests", lambda: [_Digest()])
    monkeypatch.setattr(tool, "player_zh", lambda en: {
        "Zverev A.": "兹维列夫", "Atmane T.": "阿特马内"}.get(en, en))
    promoted, skipped = tool.promote_all(write=True)
    assert promoted == [], promoted
    assert any("全称断言" in s for s in skipped), skipped
    assert draft_p.exists(), "拦下来的草稿要留在原地等终审"
    assert not (specs / "zverev-cincinnati-2026-r3.json").exists()

    # 认领了两个不同主机的源 → 照常转正（闸不是一刀切掉人写的文案）
    draft_p.write_text(json.dumps({**base, "_claims": {
        claim: "逐场表核过 https://a.example/x ；https://b.example/y"}}),
        encoding="utf-8")
    promoted, skipped = tool.promote_all(write=True)
    assert promoted and not skipped, (promoted, skipped)


def test_字幕译文把轮次写成N强_转正时留草稿(tool, monkeypatch, tmp_path):
    """`check_interview_copy_wording` 故意不扫 `zh`（译文），而全库测试
    `test_轮次写分数式不写N强` 扫整份 spec、含 `zh`，对自动 spec 也是硬的——转正直推
    main 就是 main 红。主语是 main 上真草稿 `bonzi-winston-salem-2026-r` 的那一行
    （评审 2026-09-27）。改成 1/4决赛 照常转正（闸不是一刀切掉译文）。"""
    specs = tmp_path / "specs" / "interviews"
    specs.mkdir(parents=True)
    draft_p = specs / "zverev-cincinnati-2026-r3.draft.json"
    base = {**_draft(), "source_title": "Cincinnati 2026 R3 Alexander Zverev Interview"}
    monkeypatch.setattr(tool, "SPECS", specs)

    class _Digest:
        results = [_match("Zverev A.", "Atmane T.", winner_idx=0)]

    monkeypatch.setattr(tool, "_collect_digests", lambda: [_Digest()])
    monkeypatch.setattr(tool, "player_zh", lambda en: {
        "Zverev A.": "兹维列夫", "Atmane T.": "阿特马内"}.get(en, en))

    draft_p.write_text(json.dumps({**base, "zh": ["大概是八强左右，所以是的，我很开心"]}),
                       encoding="utf-8")
    promoted, skipped = tool.promote_all(write=True)
    assert promoted == [], promoted
    assert any("N 强" in s and "八强" in s for s in skipped), skipped
    assert draft_p.exists(), "拦下来的草稿要留在原地等终审"
    assert not (specs / "zverev-cincinnati-2026-r3.json").exists()

    draft_p.write_text(json.dumps({**base, "zh": ["大概是 1/4 决赛左右，所以是的，我很开心"]}),
                       encoding="utf-8")
    promoted, skipped = tool.promote_all(write=True)
    assert promoted and not skipped, (promoted, skipped)


def test_手改草稿的标题和推送标题数字打架_转正时留草稿(tool, monkeypatch, tmp_path):
    """批次 4 复审 nit：`taste_gates.interview_taste_findings` 的硬的那一组（标题和推送标题
    同一个数两个说法）原来在 promote 只报——转出去的 spec 渲染入口 `check_taste` 照拦、
    永远渲不成，`test_全库当前零误报` 对采访又是硬的。和 `interview_taste_extra` 同一个处置：
    留草稿。两边说法一致就照常转正。"""
    specs = tmp_path / "specs" / "interviews"
    specs.mkdir(parents=True)
    draft_p = specs / "zverev-cincinnati-2026-r3.draft.json"
    base = {**_draft(), "source_title": "Cincinnati 2026 R3 Alexander Zverev Interview"}
    monkeypatch.setattr(tool, "SPECS", specs)

    class _Digest:
        results = [_match("Zverev A.", "Atmane T.", winner_idx=0)]

    monkeypatch.setattr(tool, "_collect_digests", lambda: [_Digest()])
    monkeypatch.setattr(tool, "player_zh", lambda en: {
        "Zverev A.": "兹维列夫", "Atmane T.": "阿特马内"}.get(en, en))

    clash = {**base, "cover": {**(base.get("cover") or {}), "title": ["救下3个赛点", "兹维列夫赢了"]},
             "push": {"summary": "兹维列夫救下2个赛点"}}
    draft_p.write_text(json.dumps(clash), encoding="utf-8")
    promoted, skipped = tool.promote_all(write=True)
    assert promoted == [], promoted
    assert any("口味闸不过" in s for s in skipped), skipped
    assert draft_p.exists(), "拦下来的草稿要留在原地等终审"
    assert not (specs / "zverev-cincinnati-2026-r3.json").exists()

    draft_p.write_text(json.dumps({**clash, "push": {"summary": "兹维列夫救下3个赛点"}}),
                       encoding="utf-8")
    promoted, skipped = tool.promote_all(write=True)
    assert promoted and not skipped, (promoted, skipped)

    # 批次复审 blocking (a)：草稿带着 `auto_pending` 章，默认分法下大标题术语只报——
    # 可非模板的标题只可能是人改的；放过去转正后渲染闸也只报、推出去就是带术语的封面。
    # promote 按手写判（`auto=False`），留草稿。
    (specs / "zverev-cincinnati-2026-r3.json").unlink()
    (specs / "zverev-cincinnati-2026-r3.xhs.txt").unlink(missing_ok=True)
    jargon = {**base, "transcript_verification": "auto_pending",
              "cover": {**(base.get("cover") or {}), "title": ["抢七扳平之后", "兹维列夫赢了"]}}
    draft_p.write_text(json.dumps(jargon, ensure_ascii=False), encoding="utf-8")
    promoted, skipped = tool.promote_all(write=True)
    assert promoted == [] and any("口味闸不过" in s and "抢七" in s for s in skipped), skipped
    assert draft_p.exists()
