"""flashscore 抖一下，这场球不许静静地躺到过期（2026-09-28 复审 D1）。

来路：`assemble_spec` 读 flashscore 失败改成「只报、草稿留在 waiting」之后，probe 不再红——
可编排器的 `_already_specced` 认得这份草稿、**永不重 probe**，reel-auto-ready 只补封面和
视觉证据、**不重跑备料**。回放（`rv2_park_repro.py`：df_hh_1 正常、只有 df_mh_1 一次 503）：

    base   SystemExit 穿出 → probe 红 → 失败自愈摘 state → 下一班编排器重 probe
    分支   草稿照写、留在 waiting（「结构化赛果尚未 verified」）→ 再没有人碰它

重 probe 要重下源片；读 feed 只要几个 HTTP 请求。所以只重跑便宜的那一半：

    assemble 读失败（可重试的）→ `_feed_retry` 记下哪几块
    reel-auto-ready 每一班 → `tools/retry_feed_blocks.py` 只重跑那几块，最多 FEED_RETRY_MAX 次
    试满仍不通 → warning ＋ run 摘要 ＋ pipeline_health 点名
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import assemble_spec as a  # noqa: E402
import fetch_match_stats_fs as fs  # noqa: E402
import promote_reel_draft as promote  # noqa: E402
import retry_feed_blocks as rfb  # noqa: E402

MID = "8QYQMw6l"
#: flashscore 的 home 是诺斯科娃（6-4 6-3 赢了）；编排器给的 --home 是萨巴伦卡
DF_HH_1 = f"SA÷2¬~KP÷{MID}¬FH÷Noskova L.¬FK÷Sabalenka A.¬~"
GAMES = [{"set": str(n), "home_games": h, "away_games": w, "points": [],
          "server": "home", "winner": "home"}
         for n, (h, w) in enumerate([(6, 4), (6, 3)], 1)]


class Flash:
    """一个 flashscore：`down` 里点名的 feed 读不到（`match_feed._get` 重试完抛的 SystemExit）。"""

    def __init__(self, *down: str) -> None:
        self.down = set(down)
        self.calls: list[str] = []

    def _read(self, name: str) -> None:
        self.calls.append(name)
        if name in self.down:
            raise SystemExit(f"https://…/{name}_{MID}\n  HTTP 503 —— 被挡还是不存在")

    def fs_feed(self, name, mid):
        self._read(name)
        return DF_HH_1

    def points(self, mid):
        self._read("df_mh_1")
        return GAMES

    def set_pairs(self, mid):
        self._read("df_sui_1")
        return [(6, 4), (6, 3)]

    def stats_block(self, mid):
        self._read("df_st_1")
        return {"a": {"aces": 9, "pts_won": 60}, "b": {"aces": 1, "pts_won": 45},
                "_missing_required": [], "_has_winners_ue": False}

    def collect(self, mid, home, away):
        self._read("collect")
        return {"candidates": [{"label": "一发", "detail": f"{home} 一发 80%"}],
                "durations": [["全场", "1:20"]]}


@pytest.fixture
def flash(monkeypatch):
    world = Flash()
    for name in ("fs_feed", "points", "set_pairs", "stats_block", "collect"):
        monkeypatch.setattr(a, name, getattr(world, name))
    monkeypatch.setattr(a, "rank_games", lambda g: [])
    import headshot_index  # noqa: PLC0415 —— 数据图头像会去 WTA 现抓，这里不联网
    monkeypatch.setattr(headshot_index, "resolve_headshots", lambda draft: [])
    monkeypatch.setattr(a, "fetch_rankings", lambda: type("R", (), {"atp": [], "wta": []})())

    class NotReady:
        ready = False

    monkeypatch.setattr(a, "Chat", lambda: NotReady())
    return world


def _assemble(**kw) -> dict:
    args = dict(slug="sabalenka-noskova", home="Aryna Sabalenka", away="Linda Noskova",
                event="Cincinnati", year=2026, fixture="北京时间", flashscore_id=MID,
                home_rank=1, received_at=datetime.now(timezone.utc).isoformat(),
                tactical_packet={"status": "skipped"})
    args.update(kw)
    return a.assemble(**args)


def _verified(draft: dict) -> bool:
    return "结构化赛果尚未 verified" not in promote.waiting_reasons(draft)


# ── 回放：只有 df_mh_1 一次 503 ─────────────────────────────────────────────

def test_回放_df_mh_1一次503_草稿记账_下一班只重跑逐局表就转成verified(flash):
    flash.down = {"df_mh_1"}
    draft = _assemble()
    assert "_feed_retry" in draft, "读失败（可重试的）要记账——不记，编排器永不重 probe，这场球就躺到过期"
    ledger = draft["_feed_retry"]
    assert ledger["blocks"] == ["points"] and ledger["tries"] == 0, ledger
    assert "HTTP 503" in ledger["errors"]["points"]
    assert not _verified(draft), "这一趟本来就该留在 waiting"
    assert "stats" in draft, "读通了的块照写"
    assert "reel-auto-ready 下一班只重跑" in "\n".join(draft["_notes"])

    flash.down.clear()
    flash.calls.clear()
    assert a.retry_feed_blocks(draft) == "healed"
    assert flash.calls == ["df_mh_1", "df_sui_1"], (
        f"只许重跑读失败的那一块（抢七小分跟着逐局表走）：{flash.calls}")
    match = draft["_match"]
    assert match["status"] == "result_verified"
    assert (match["winner"], match["winner_result"], match["loser"]) == ("诺斯科娃", "6-4 6-3", "萨巴伦卡")
    assert "_feed_retry" not in draft and _verified(draft)
    assert draft["cover"]["winner"] == "诺斯科娃"
    assert "备料重跑读通了" in "\n".join(draft["_notes"])


def test_回放_df_hh_1读不到_顺序和依赖它的三块一起重跑_赢家不许算反(flash):
    """上一轮复审的那一趟（df_hh_1 503）：顺序不认，stats／狠数据／转折局一块都不写；
    重跑读通之后 matchup 归到 feed 的 home/away，赢家是诺斯科娃，排名跟着人走。"""
    flash.down = {"df_hh_1"}
    draft = _assemble()
    assert draft["_feed_retry"]["blocks"] == ["matchup", "stats", "hit_data", "points"]
    assert [p["name_en"] for p in draft["cover"]["matchup"]] == ["Aryna Sabalenka", "Linda Noskova"]
    assert "stats" not in draft and "_match" in draft and not _verified(draft)

    flash.down.clear()
    assert a.retry_feed_blocks(draft) == "healed"
    pair = draft["cover"]["matchup"]
    assert [p["name_en"] for p in pair] == ["Linda Noskova", "Aryna Sabalenka"]
    assert pair[1].get("rank") == 1, "归位是搬动已有的两条，排名／国别跟着人走"
    assert draft["stats"]["a"]["aces"] == 9, "stats.a 跟 feed 的 home（诺斯科娃）"
    assert draft["_hit_data"][0]["detail"].startswith("诺斯科娃"), "狠数据按 feed home 的名字标"
    assert draft["_match"]["winner"] == "诺斯科娃" and _verified(draft)


def test_一直读不到_试满三次就停手_不再碰feed(flash):
    flash.down = {"df_mh_1"}
    draft = _assemble()
    got = [a.retry_feed_blocks(draft) for _ in range(a.FEED_RETRY_MAX)]
    assert got == ["retry"] * (a.FEED_RETRY_MAX - 1) + ["gave_up"]
    ledger = draft["_feed_retry"]
    assert ledger["tries"] == a.FEED_RETRY_MAX and ledger["exhausted_at"] == ledger["last_at"]
    flash.calls.clear()
    assert a.retry_feed_blocks(draft) == "exhausted"
    assert flash.calls == [], "试满之后这一班一个请求都不许发"
    assert "不再自动重跑" in "\n".join(draft["_notes"])


def test_重读也一样的错不记账(flash, monkeypatch):
    """解析错（ValueError）同一份 feed 重读一百遍还是它——只写 note，不进 `_feed_retry`。"""
    def broken(mid):
        raise ValueError("df_mh_1 的 HL 字段对不上")

    monkeypatch.setattr(a, "points", broken)
    draft = _assemble()
    assert "_feed_retry" not in draft
    assert "转折局没成（ValueError" in "\n".join(draft["_notes"])


def test_近期赛果读不到时_id也记账_重跑补上id再跑下游(flash, monkeypatch):
    """flashscore 整个抖的时候最先倒的是反查 id（近期赛果那几页）。原来 `resolve_match_id`
    把「全部读取失败」也吞成 None，草稿写一句「没反查到 id」就再也没人管。"""
    state = {"down": True}

    def resolve(home, away):
        if state["down"]:
            raise fs.FeedUnavailable("近期赛果喂料全部读取失败：-1: Flashscore HTTP 503")
        return MID

    monkeypatch.setattr(a, "resolve_match_id", resolve)
    draft = _assemble(flashscore_id=None)
    assert draft["_feed_retry"]["blocks"] == ["match_id", "matchup", "stats", "hit_data", "points"]
    assert "_match" not in draft and flash.calls == []
    assert "这不是「没有这场」" in "\n".join(draft["_notes"])

    state["down"] = False
    assert a.retry_feed_blocks(draft) == "healed"
    assert draft["_match"]["status"] == "result_verified" and draft["_match"]["flashscore_id"] == MID


def test_扫完了确实没有这场_不当成没读到(monkeypatch):
    """「没读到」和「没有」分开：有页读失败时没找到 → FeedUnavailable（那一页里可能就有它）；
    每页都读到了、就是没有 → 普通 StatsError（`resolve_match_id` 照旧回 None，不记账）。"""
    def pages(broken: set[int]):
        def feed(name: str) -> str:
            offset = int(name.split("_")[2])
            if offset in broken:
                raise fs.FeedUnavailable(f"Flashscore HTTP 503（{name}，试了 3 次）")
            return "~AA÷x¬AE÷Other A.¬AF÷Player B.¬"
        return feed

    monkeypatch.setattr(fs, "feed", pages({-1}))
    with pytest.raises(fs.FeedUnavailable, match="另有 1 页读取失败"):
        fs.find_match(["medvedev", "damm"], offsets=(-1, 0))
    monkeypatch.setattr(fs, "feed", pages(set()))
    with pytest.raises(fs.StatsError) as caught:
        fs.find_match(["medvedev", "damm"], offsets=(-1, 0))
    assert not isinstance(caught.value, fs.FeedUnavailable)
    monkeypatch.setattr(a, "find_match", lambda names: fs.find_match(names, offsets=(-1, 0)))
    assert a.resolve_match_id("Daniil Medvedev", "Martin Damm") is None
    monkeypatch.setattr(fs, "feed", pages({-1, 0}))
    with pytest.raises(fs.FeedUnavailable, match="全部读取失败"):
        a.resolve_match_id("Daniil Medvedev", "Martin Damm")


def test_flashscore喂料_5xx重试完是没读到_4xx是明确拒绝(monkeypatch):
    import urllib.error  # noqa: PLC0415

    def code(n):
        def urlopen(req, timeout=0):
            raise urllib.error.HTTPError(req.full_url, n, "x", {}, None)
        return urlopen

    monkeypatch.setattr(fs.urllib.request, "urlopen", code(503))
    with pytest.raises(fs.FeedUnavailable):
        fs.feed("x", sleep=lambda s: None)
    monkeypatch.setattr(fs.urllib.request, "urlopen", code(404))
    with pytest.raises(fs.StatsError) as caught:
        fs.feed("x", sleep=lambda s: None)
    assert not isinstance(caught.value, fs.FeedUnavailable)
    assert a.is_transient_feed_error(SystemExit("HTTP 503"))
    assert not a.is_transient_feed_error(ValueError("解析错"))
    assert not a.is_transient_feed_error(a.MatchupOrderUnverified("同姓", transient=False))


def test_补齐比分之后拿同几道闸核一遍已经起草的文案_对不上就撤(flash):
    """probe 那一趟文案是在没有比分的情况下起草的，`editorial_score_problem` 当时拿空比分
    放行了它。补齐之后不核，就是一份没对过比分的文案被自动转正。只核不重写（不碰模型）。"""
    flash.down = {"df_mh_1"}
    draft = _assemble()
    draft["editorial"] = {"thesis": "萨巴伦卡 6-2 6-1 横扫", "narration": ["开局"]}
    draft["push"] = {"summary": "萨巴伦卡横扫", "lead": "两盘", "auto": True}
    flash.down.clear()
    assert a.retry_feed_blocks(draft) == "healed"
    assert "editorial" not in draft and "push" not in draft
    assert "备料补齐之后文案对不上" in "\n".join(draft["_notes"])

    flash.down = {"df_mh_1"}
    ok = _assemble()
    ok["editorial"] = {"thesis": "诺斯科娃 6-4 6-3 赢下", "narration": ["开局"]}
    flash.down.clear()
    assert a.retry_feed_blocks(ok) == "healed" and "editorial" in ok


# ── reel-auto-ready 的那一步 ───────────────────────────────────────────────

def test_命令行_写回草稿_试满打warning写run摘要(flash, tmp_path, monkeypatch, capsys):
    flash.down = {"df_mh_1"}
    path = tmp_path / "sabalenka-noskova.draft.json"
    path.write_text(json.dumps(_assemble(), ensure_ascii=False), encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    lines = []
    for _ in range(a.FEED_RETRY_MAX):
        assert rfb.main(["--draft", str(path), "--write"]) == 0
        lines.append(capsys.readouterr().out.strip().splitlines()[-1])
    assert lines == ["retry"] * (a.FEED_RETRY_MAX - 1) + ["gave_up"]
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["_feed_retry"]["tries"] == a.FEED_RETRY_MAX and saved["_feed_retry"]["exhausted_at"]
    assert "sabalenka-noskova" in summary.read_text(encoding="utf-8")
    before = path.read_bytes()
    assert rfb.main(["--draft", str(path), "--write"]) == 0
    out = capsys.readouterr().out
    assert out.strip().splitlines()[-1] == "exhausted" and "::warning::" in out
    assert path.read_bytes() == before, "试满之后不再改草稿"


def _run(workflow: str) -> str:
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8"))
    return "\n".join(str(s.get("run") or "") for s in wf["jobs"]["ready"]["steps"])


def test_reel_auto_ready每一班先重跑欠着的备料_再补封面和转正():
    run = _run("reel-auto-ready.yml")
    call = "tools/retry_feed_blocks.py --draft \"$DRAFT\" --write"
    assert run.count(call) == 1, "每份草稿每一班只重跑一次"
    at = run.index(call)
    assert run.index("[expired]") < at, "过期的草稿不重跑"
    assert at < run.index("PROBE=$(git ls-tree"), "重跑不要 probe 证据，排在认领 probe 之前"
    assert at < run.index("tools/promote_reel_draft.py"), "补上的赛果这一班就能转正"
    assert "git add specs/reels" in run, "改过的草稿要落库"


# ── pipeline_health 点名 ───────────────────────────────────────────────────

def test_健康检查点名试满仍没读通的新鲜草稿_过期的和还在试的不报(monkeypatch):
    import tools.pipeline_health as ph  # noqa: PLC0415

    now = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=2)).isoformat()
    stale = (now - promote.PENDING_MAX_AGE - timedelta(minutes=1)).isoformat()
    ledger = {"blocks": ["points"], "errors": {"points": "SystemExit: HTTP 503"},
              "tries": 3, "last_at": "2026-09-28T11:40:00Z", "exhausted_at": "2026-09-28T11:40:00Z"}
    drafts = [
        {"slug": "stuck-one", "_production": {"received_at": fresh}, "_feed_retry": ledger},
        {"slug": "still-trying", "_production": {"received_at": fresh},
         "_feed_retry": {**ledger, "tries": 1, "exhausted_at": None}},
        {"slug": "expired-one", "_production": {"received_at": stale}, "_feed_retry": ledger},
        {"slug": "healthy", "_production": {"received_at": fresh}},
    ]
    seen = []
    monkeypatch.setattr(ph, "_tracked_jsons", lambda pattern: seen.append(pattern) or drafts)
    stuck = ph.feed_retry_stuck(now)
    assert seen == ["specs/reels/pending/*.draft.json"]
    assert len(stuck) == 1 and "stuck-one" in stuck[0] and "points" in stuck[0]
    _report, alerts = ph.render_report([], [], (0, 0, 0.0), [], None, stuck)
    assert stuck[0] in alerts and "stuck-one" in _report
    # 去重按 slug：同一份草稿换了一句错误文字，不算新告警
    assert ph.alert_keys(stuck) == ["feed_retry:stuck-one"]
    assert ph.alert_keys([stuck[0].replace("points", "points、tiebreaks")]) == ["feed_retry:stuck-one"]


def test_健康检查的稀疏检出带着草稿和新鲜窗的出处():
    wf = (ROOT / ".github/workflows/pipeline-health.yml").read_text(encoding="utf-8")
    checkout = wf.split("actions/checkout@v4", 1)[1].split("- name:", 1)[0]
    assert "specs/reels/pending/*.draft.json" in checkout
    assert "tools/promote_reel_draft.py" in checkout, "feed_retry_stuck import 它的 PENDING_MAX_AGE"
    body = (ROOT / "tools/pipeline_health.py").read_text(encoding="utf-8")
    assert "orchestrator_productivity(), feed_retry_stuck())" in body, "main 要真的把它交给报表"


# ── 账本本身：只在草稿上，转正剥掉，拼错也拦得住 ───────────────────────────

def test_账本字段_转正剥掉_不是真字段所以不会被下划线闸误拦():
    import build_match_reel as reel  # noqa: PLC0415
    import render_inputs as ri  # noqa: PLC0415

    assert "feed_retry" not in reel._REAL_FIELDS["spec"]
    reel._reject_underscored_fields({"_feed_retry": {"blocks": ["points"]}})
    gate = ri.GATE_ANNOTATIONS["_feed_retry"]
    assert gate.read_by == frozenset({"promote"}) and gate.where == ()
    assert set(a.FEED_BLOCKS) == {"match_id", "matchup", "stats", "hit_data", "points", "tiebreaks"}
    for upstream, downstream in a._FEED_DOWNSTREAM.items():
        assert upstream in a.FEED_BLOCKS and set(downstream) <= set(a.FEED_BLOCKS)
