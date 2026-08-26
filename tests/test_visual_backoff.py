"""知识帖素材预检的退避判据（2026-08-26）。

来路：knowledge-adhoc 2026-08-18~08-24 九天里六天红在同一句「知识帖素材预检
失败：候选故事均没有完整高质量图片包」——预检被拒没有任何记忆，第二天同样的
排序端出同样的坏候选（trivia-queue、trivia-rufus 反复被同两条 year/visual
判据拒掉），每日知识栏目约一半天数静默停更。修法：被拒 slug 记进
story_state.json 的 `__visual_backoff__`（保留键，先例是
`__knowledge_adhoc_date__`），候选排序把退避中的降到队尾；预检通过就摘掉；
失败路径由工作流单独把 state 提交回仓库（不落库的话记忆只活在 runner 上）。
"""

import json
from datetime import date, timedelta
from pathlib import Path

from tennislive.digest import Digest
from tennislive.render import tournament_story as ts


TODAY = date(2026, 8, 26)


def _state(monkeypatch, tmp_path, initial: dict | None = None) -> Path:
    path = tmp_path / "story_state.json"
    if initial is not None:
        path.write_text(json.dumps(initial, ensure_ascii=False),
                        encoding="utf-8")
    monkeypatch.setattr(ts, "STATE_PATH", path)
    return path


def test_记退避读退避和预检通过后摘掉(monkeypatch, tmp_path):
    path = _state(monkeypatch, tmp_path)
    ts.mark_visual_backoff(["golden-slam", "hawkeye"], TODAY)
    saved = json.loads(path.read_text("utf-8"))
    assert saved[ts.VISUAL_BACKOFF_KEY] == {
        "golden-slam": "2026-08-26", "hawkeye": "2026-08-26"}
    assert ts.visual_backoff_active("golden-slam", TODAY)
    assert ts.visual_backoff_active(
        "golden-slam", TODAY + timedelta(days=ts.VISUAL_BACKOFF_DAYS - 1))
    assert not ts.visual_backoff_active(
        "golden-slam", TODAY + timedelta(days=ts.VISUAL_BACKOFF_DAYS)), (
        "退避要过期——素材包修好之后选题必须自己回来，不是永久拉黑")
    ts.clear_visual_backoff("golden-slam")
    saved = json.loads(path.read_text("utf-8"))
    assert "golden-slam" not in saved[ts.VISUAL_BACKOFF_KEY]
    assert "hawkeye" in saved[ts.VISUAL_BACKOFF_KEY]
    # 退避是保留键，不许撞 slug 空间：`state.get(slug)` 查不到它
    assert ts.VISUAL_BACKOFF_KEY.startswith("__")


def test_候选排序把退避中的降到队尾而不是剔除(monkeypatch, tmp_path):
    _state(monkeypatch, tmp_path, {
        ts.VISUAL_BACKOFF_KEY: {"golden-slam": TODAY.isoformat()}})
    ranking = [
        {"story_slug": "golden-slam", "rank": 1},
        {"story_slug": "umag", "rank": 2},
        {"story_slug": "hawkeye", "rank": 3},
    ]
    monkeypatch.setattr(ts, "story_ranking", lambda _digest: ranking)
    slugs = [s.slug for s in
             ts.tournament_story_candidates(Digest(today=TODAY))]
    assert slugs == ["umag", "hawkeye", "golden-slam"], (
        "昨天刚被素材闸拒过的还排在最前，就是把当天的尝试名额白白烧在"
        "一个已知会拒的选题上——连续六天同因拦停的来路")
    # 过期之后要回到本来的顺序（判据自己的判据：上面那条不是恒真的）
    later = Digest(today=TODAY + timedelta(days=ts.VISUAL_BACKOFF_DAYS))
    slugs = [s.slug for s in ts.tournament_story_candidates(later)]
    assert slugs == ["golden-slam", "umag", "hawkeye"]


def test_从visual_sources报告记退避两条失败路都不抛(monkeypatch, tmp_path):
    path = _state(monkeypatch, tmp_path)
    outdir = tmp_path / "knowledge"
    outdir.mkdir()
    (outdir / "visual_sources.json").write_text(json.dumps({
        "status": "fail",
        "rejected_candidates": [
            {"story_slug": "golden-slam", "errors": ["封面人物不匹配"]},
            {"story_slug": "hawkeye", "errors": ["year_match false"]},
            {"title": "缺 slug 的坏行"},
        ],
    }), encoding="utf-8")
    assert ts.mark_visual_backoff_from_report(outdir, TODAY) == [
        "golden-slam", "hawkeye"]
    saved = json.loads(path.read_text("utf-8"))
    assert set(saved[ts.VISUAL_BACKOFF_KEY]) == {"golden-slam", "hawkeye"}
    # 报告不在/坏 JSON 按「没有拒绝记录」处置——这条路跑在失败收尾上，
    # 抛异常会把真正的失败原因盖掉
    assert ts.mark_visual_backoff_from_report(tmp_path / "missing", TODAY) == []
    (outdir / "visual_sources.json").write_text("{bad", encoding="utf-8")
    assert ts.mark_visual_backoff_from_report(outdir, TODAY) == []


def test_工作流失败也要把退避提交回仓库():
    """CLI 在失败路上写了 state，但生成步骤红了「提交内容到仓库」整个跳过
    ——不单独补一步的话退避只活在 runner 上，明天照旧同因拦停。"""
    body = Path(".github/workflows/knowledge-adhoc.yml").read_text("utf-8")
    anchor = "- name: 失败也提交素材退避"
    assert anchor in body, "失败路径没有提交 story_state 的步骤"
    block = body.split(anchor, 1)[1].split("\n      - name:", 1)[0]
    assert "if: failure()" in block
    assert "data/story_state.json" in block
    assert "push_with_rebase_retry" in block, (
        "失败收尾的这条 push 也要走共享重试——它撞车丢掉的是明天的记忆")
    # CLI 那头要真调用了记退避（接线判据；行为判据在上面三条）
    cli = Path("src/tennislive/cli.py").read_text("utf-8")
    assert "mark_visual_backoff_from_report" in cli
    assert "clear_visual_backoff" in cli
