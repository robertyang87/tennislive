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


def test_find_opponent按姓找对手(tool, monkeypatch):
    """受访者姓 zverev，赛果里他的对手是 Atmane——返回 (兹维列夫, 阿特马内, 对阵)。"""
    class _Digest:
        results = [_match("Zverev A.", "Atmane T.")]

    monkeypatch.setattr("tennislive.zh.player_zh", lambda en: {
        "Zverev A.": "兹维列夫", "Atmane T.": "阿特马内",
        "Alexander Zverev": "兹维列夫"}.get(en, en))
    got = tool.find_opponent(_Digest(), "zverev")
    assert got == ("兹维列夫", "阿特马内", "兹维列夫 vs 阿特马内")
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
