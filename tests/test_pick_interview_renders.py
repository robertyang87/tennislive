"""tools/pick_interview_renders.py —— 挑待 dispatch 的采访 spec。

三层判据，缺一层都出过真事故：

1. 已 render / 已 dispatch 的不再投——否则定时任务每 30 分钟把历史采访重渲一遍；
2. **终审没补齐的不许投**：render 有三道人工编辑闸（opening /
   transcript_verified / takeaway），字段不全的 spec 投出去必死在闸上、又被
   永久记成「已 dispatch」——`swiatek-shnaider-tor2026-qf` 就这么卡死过：
   既不算已 render（没有 render.json），又因为记了状态永远不会再被投；
3. **先投后记 + 查产物**：dispatch 失败的不许记（先记后投＝那条从此消失且
   不吭声）；投出去很久没有 render.json 的要能点出来（「投了」是信号，
   render.json 才是产物）。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


def _complete_body() -> dict:
    """能过 render 三道编辑闸的最小 spec 形状（和 `missing_for_render` 同口径）。"""
    from interview_source_gate import finalize_source_contract

    spec = {
        "slug": "fixture",
        "url": "https://example.test/oncourt",
        "requested_content_type": "on_court",
        "interview_kind": "赛后场上采访",
        "source_verification": {
            "status": "verified", "detected_type": "on_court",
            "method": "human_visual_verdict",
            "source_url": "https://example.test/oncourt",
            "evidence": [{"kind": "visual_verdict", "by": "test"}],
        },
        "match": {
            "id": "2026:test:qf:winner", "event": "测试赛", "round": "四分之一决赛",
            "winner": "赢家", "loser": "输家", "participants": ["赢家", "输家"],
        },
        "opening": {"kind": "match_end", "lead_in": 10.0,
                    "why": "正文源开头含同场赛点和现场解说"},
        "zh": ["第一行"],
        "transcript_verified": True,
        "takeaway": {"close": {"point": "x"}},
        "cover": {"frame_at": 1.0},
    }
    return finalize_source_contract(spec)


def _write_spec(specs: Path, slug: str, body: dict, *, xhs: bool = True) -> None:
    body = json.loads(json.dumps(body))
    body["slug"] = slug
    if body.get("match"):
        body["match"]["id"] = f"2026:test:qf:{slug}"
        from interview_source_gate import finalize_source_contract
        body = finalize_source_contract(body)
    (specs / f"{slug}.json").write_text(
        json.dumps(body, ensure_ascii=False), encoding="utf-8")
    if xhs:
        (specs / f"{slug}.xhs.txt").write_text("文案", encoding="utf-8")


@pytest.fixture()
def tool(monkeypatch, tmp_path):
    sys.path.insert(0, str(_TOOLS))
    import pick_interview_renders as p  # noqa: PLC0415

    specs = tmp_path / "specs" / "interviews"
    specs.mkdir(parents=True)
    # 一个已 render、一个补齐待投、一个草稿、一个只有骨架（等终审）
    _write_spec(specs, "a-done", _complete_body())
    _write_spec(specs, "b-todo", _complete_body())
    (specs / "c-draft.draft.json").write_text("{}")
    _write_spec(specs, "d-bare", {}, xhs=False)
    monkeypatch.setattr(p, "SPECS", specs)
    monkeypatch.setattr(p, "STATE",
                        tmp_path / "data" / "interview_render_dispatched.json")
    monkeypatch.setattr(p, "_rendered_slugs", lambda: {"a-done"})
    return p


def test_todo排除已render和草稿(tool):
    """a-done 已 render、c-draft 是草稿，只有 b-todo 该 dispatch。"""
    ready, _ = tool.todo_slugs()
    assert ready == ["b-todo"]


def test_mark记录dispatch防重(tool):
    """记录过 dispatch 的 slug 不能再 dispatch（否则每 30 分钟重渲历史）。"""
    tool.mark_one("b-todo")
    ready, _ = tool.todo_slugs()
    assert ready == [], "记录过 dispatch 的不能再 dispatch"
    state = json.loads(tool.STATE.read_text(encoding="utf-8"))
    assert state["slugs"] == ["b-todo"]
    assert state["at"]["b-todo"], "投出时刻要记下来——stale 反查靠它"


def test_终审没补齐的不许投而且要说缺什么(tool):
    """**这条就是 swiatek-shnaider 卡死事故的判据。** 骨架 spec 不进
    dispatch 名单，进「等终审」并逐项点出缺什么——「不投」和「忘了投」
    必须分得开。"""
    ready, waiting = tool.todo_slugs()
    assert "d-bare" not in ready
    by_slug = dict(waiting)
    assert "d-bare" in by_slug
    missing = "、".join(by_slug["d-bare"])
    for want in ("opening", "zh", "transcript_verified", "takeaway", "cover",
                 "xhs"):
        assert want in missing, f"缺 {want} 没被点出来：{missing}"


def test_判定和闸共用同一张豁免表(tool):
    """老 spec 靠 `_LEGACY_NO_OPENING` / `_NO_TAKEAWAY_LEGACY` 过闸——判定
    比闸更严的话，会把这些本来渲得动的 spec 拦在门外永远不投。
    拿表里**真实的** slug 验（表自带自检：写错名字当场 KeyError 式失败）。
    """
    import build_interview_clip as clip  # noqa: PLC0415

    legacy_open = sorted(clip._LEGACY_NO_OPENING)[0]
    legacy_tk = sorted(clip._NO_TAKEAWAY_LEGACY)[0]
    assert legacy_open, "豁免表空了，判据失效"

    body = _complete_body()
    del body["opening"]
    _write_spec(tool.SPECS, legacy_open, body)
    body2 = _complete_body()
    del body2["takeaway"]
    _write_spec(tool.SPECS, legacy_tk, body2)
    ready, waiting = tool.todo_slugs()
    assert legacy_open in ready, "在 _LEGACY_NO_OPENING 里的不该因缺 opening 被拦"
    assert legacy_tk in ready, "在 _NO_TAKEAWAY_LEGACY 里的不该因缺 takeaway 被拦"
    # 反向：同样缺 opening 但不在表里的（d-bare）仍然在等终审
    assert "d-bare" in dict(waiting)


def test_stale判产物不判信号(tool, monkeypatch):
    """投出去超过 3 小时还没有 render.json 的要点出来；有 render.json 的、
    刚投的都不算。老状态（bulk mark 时代）没记时刻的一律算 stale。"""
    now = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    old = (now - timedelta(hours=4)).strftime("%FT%TZ")
    fresh = (now - timedelta(minutes=20)).strftime("%FT%TZ")
    tool.mark_one("old-no-render", now=old)
    tool.mark_one("fresh-no-render", now=fresh)
    tool.mark_one("old-rendered", now=old)
    # 手写一个没有 at 的老条目
    state = json.loads(tool.STATE.read_text(encoding="utf-8"))
    state["slugs"] = sorted({*state["slugs"], "ancient"})
    tool.STATE.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(tool, "_rendered_slugs", lambda: {"old-rendered"})

    stale = dict(tool.stale_dispatches(now=now))
    assert "old-no-render" in stale, "投了 4 小时没产物的没被点出来"
    assert "ancient" in stale, "老状态没记时刻的要一律算 stale"
    assert "fresh-no-render" not in stale, "刚投 20 分钟的不该报"
    assert "old-rendered" not in stale, "render.json 落库了就不是 stale——判产物"


def test_stale自动释放回dispatch队列而新任务不重复(tool, monkeypatch):
    now = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    old = (now - timedelta(hours=4)).strftime("%FT%TZ")
    fresh = (now - timedelta(minutes=20)).strftime("%FT%TZ")
    tool.mark_one("b-todo", now=old)
    ready, _ = tool.todo_slugs(now=now)
    assert "b-todo" in ready, "超过 3 小时无产物要自动重投，不能只报警等人"

    tool.mark_one("b-todo", now=fresh)
    ready, _ = tool.todo_slugs(now=now)
    assert "b-todo" not in ready, "刚投出的还在跑，不许并发重复 dispatch"


def test_stdout第二行起是名单等终审走stderr(tool, monkeypatch, capsys):
    """workflow 拿 `tail -n +2` 切 stdout 当 dispatch 名单——等终审的一旦混进
    stdout，就会把一条不齐的 spec 投出去，正是这次修的卡死。"""
    monkeypatch.setattr(sys, "argv", ["pick_interview_renders.py"])
    assert tool.main() == 0
    out, err = capsys.readouterr()
    lines = out.splitlines()
    assert lines[0].startswith("待 dispatch")
    assert lines[1:] == ["b-todo"], f"stdout 第二行起必须只有名单：{lines!r}"
    assert "等自动补齐 / 例外复核" in err and "d-bare" in err
