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
    # 第三轮复审 nit：原来 SystemExit／StatsError 整类算可重试，4xx（明确拒绝）也重试三次
    assert not a.is_transient_feed_error(SystemExit(
        "https://…/df_mh_1_x\n  HTTP 404 —— 被挡还是不存在，看状态码和 Content-Type")), "4xx 是明确拒绝"
    assert not a.is_transient_feed_error(fs.StatsError("Flashscore HTTP 403（x）"))
    assert not a.is_transient_feed_error(fs.StatsError("统计喂料是空的"))
    assert a.is_transient_feed_error(SystemExit("https://…\n  HTTP 429 —— 被挡还是不存在")), "限流是晚点再来"
    assert a.is_transient_feed_error(SystemExit("https://…\n  连了 3 次都失败（URLError）"))
    assert a.is_transient_feed_error(fs.FeedUnavailable("Flashscore HTTP 503（x，试了 3 次）"))


def test_补齐比分之后拿同几道闸核一遍已经起草的文案_对不上就撤(flash):
    """probe 那一趟文案是在没有比分的情况下起草的，`editorial_score_problem` 当时拿空比分
    放行了它。补齐之后不核，就是一份没对过比分的文案被自动转正。只核不重写（不碰模型）。"""
    flash.down = {"df_mh_1"}
    draft = _assemble()
    draft["editorial"] = {"thesis": "萨巴伦卡 6-2 6-1 横扫", "narration": ["开局"]}
    draft["push"] = {"summary": "萨巴伦卡横扫", "lead": "两盘", "auto": True}
    flash.down.clear()
    assert a.retry_feed_blocks(draft) == "copy_dropped", "撤了文案不是「读通了」——没有东西会再起草它"
    assert "editorial" not in draft and "push" not in draft
    assert "备料补齐之后文案对不上" in "\n".join(draft["_notes"])
    assert "文案对不上" in draft["_feed_retry"]["needs_human"][0], "要人看——记账，pipeline_health 按它点名"

    flash.down = {"df_mh_1"}
    ok = _assemble()
    ok["editorial"] = {"thesis": "诺斯科娃 6-4 6-3 赢下", "narration": ["开局"]}
    flash.down.clear()
    assert a.retry_feed_blocks(ok) == "healed" and "editorial" in ok


# ── reel-auto-ready 的那一步 ───────────────────────────────────────────────

def test_命令行_写回草稿_试满打warning写run摘要(flash, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(rfb, "_now", lambda: datetime.now(timezone.utc) + timedelta(days=1))
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
    assert out.strip().splitlines()[-1] == "exhausted"
    assert "::warning::" not in out, "试满那一班已经告警过、pipeline_health 在点名——不许每一班再刷一遍"
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
    # 第三轮复审 nit：flashscore 挂住不回时一趟能拖 2~6 分钟（job 才 15 分钟）；被掐掉要补记这一趟
    line = run[run.rindex("\n", 0, at) + 1:run.index("\n", at)]
    assert line.lstrip().startswith("timeout "), f"重跑要有墙钟上限：{line}"
    assert "|| FEED_RC=$?" in line, "被掐掉不许让 bash -e 带崩整个循环"
    fallback = run[at:at + 600]
    assert '"$FEED_RC" = "124"' in fallback and "--timed-out" in fallback, "被掐掉（124）要补记一趟"
    guard = run[run.rindex("._feed_retry.blocks", 0, at):at]
    assert "._feed_retry.exhausted_at" in guard, "停手了的不再进这一步（不然每一班刷一遍 warning）"
    # 第四轮复审 nit：每份 120s 只包住一份；同一班五六份一起到期、flashscore 挂住不回，累计冲过
    # job 的 timeout-minutes → 落库那步不跑、tries 不涨、下一班原样重演。整班要有累计预算
    budget = run[run.rindex("if [", 0, at):at]
    assert '"$SECONDS" -ge "$FEED_RETRY_BUDGET"' in budget, "过了整班预算，剩下的这一班不重跑"
    assert budget.index("[later]") < budget.index("else"), "预算用满那一支不能跑重跑"
    import re  # noqa: PLC0415
    import yaml  # noqa: PLC0415
    seconds = int(re.search(r"^\s*FEED_RETRY_BUDGET=(\d+)$", run, re.M).group(1))
    assert run.index("FEED_RETRY_BUDGET=") < run.index("for DRAFT in"), "预算是整班的，不是每份的"
    wf = yaml.safe_load((ROOT / ".github/workflows/reel-auto-ready.yml").read_text(encoding="utf-8"))
    minutes = wf["jobs"]["ready"]["timeout-minutes"]
    # 最后一份在预算边上开跑还要 120s（＋补记一趟）；再留 3 分钟给装依赖和后面的审核、落库
    assert seconds + 120 + 30 + 180 <= minutes * 60, (seconds, minutes)
    # 第四轮复审 nit：先写临时文件再换名，被掐在两步之间留下的 .tmp 不许被 git add 带进去
    commit = run[run.index("git add specs/reels") - 200:run.index("git add specs/reels")]
    assert "rm -f specs/reels/pending/*.tmp" in commit


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
        # 第三轮复审 nit：撤了文案／重读也一样的错／重跑崩了——账上没有要重读的块，也要点名
        {"slug": "copy-gone", "_production": {"received_at": fresh},
         "_feed_retry": {"blocks": [], "tries": 1, "needs_human": ["备料补齐之后文案对不上（…）"],
                         "needs_human_at": "2026-09-28T11:00:00Z"}},
    ]
    seen = []
    monkeypatch.setattr(ph, "_tracked_jsons", lambda pattern: seen.append(pattern) or drafts)
    stuck = ph.feed_retry_stuck(now)
    assert seen == ["specs/reels/pending/*.draft.json"]
    assert len(stuck) == 2 and "stuck-one" in stuck[1] and "points" in stuck[1]
    assert "copy-gone" in stuck[0] and "文案对不上" in stuck[0]
    stuck = stuck[1:]
    _report, alerts = ph.render_report([], [], (0, 0, 0.0), [], None, feed_stuck=stuck)
    assert stuck[0] in alerts and "stuck-one" in _report
    assert "--rearm --write" in _report, "告警要带上怎么让它重来，不让人去翻 skill"
    # 去重按 slug：同一份草稿换了一句错误文字，不算新告警
    assert ph.alert_keys(stuck) == ["feed_retry:stuck-one"]
    assert ph.alert_keys([stuck[0].replace("points", "points、tiebreaks")]) == ["feed_retry:stuck-one"]


def test_健康检查的稀疏检出带着草稿和新鲜窗的出处():
    wf = (ROOT / ".github/workflows/pipeline-health.yml").read_text(encoding="utf-8")
    checkout = wf.split("actions/checkout@v4", 1)[1].split("- name:", 1)[0]
    assert "specs/reels/pending/*.draft.json" in checkout
    assert "tools/promote_reel_draft.py" in checkout, "feed_retry_stuck import 它的 PENDING_MAX_AGE"
    body = (ROOT / "tools/pipeline_health.py").read_text(encoding="utf-8")
    # 只钉「main() 那一处调用里把它按关键字交出去了」，不钉整行原文：别的分支在同一处调用后面
    # 再加关键字参数（采访 subs 停车那一项）时，括号不在这一行收尾
    call = body[body.index("report, alerts = render_report("):]
    assert "feed_stuck=feed_retry_stuck()" in call[:300], "main 要真的把它交给报表"
    # 第四轮复审 nit：只收关键字——别的分支在同一个位置加了列表参数，按位置传会串栏
    import inspect  # noqa: PLC0415
    import tools.pipeline_health as ph  # noqa: PLC0415
    kind = inspect.signature(ph.render_report).parameters["feed_stuck"].kind
    assert kind is inspect.Parameter.KEYWORD_ONLY


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


# ── 第三轮复审：赛果补齐之后，probe 那一趟的视觉结论就过时了 ─────────────────
#
# match-reel.yml 的 probe 在 assemble 之后同一趟紧接着跑 analyze_reel_visuals；df_mh_1 读失败时
# 模型看到的 `_match` 只有 flashscore_id，`clean_report` 不核封面人物、情绪退回 winner_celebration。
# 重跑补上赛果之后，reel-auto-ready 要不要重审只看封面路径／状态／retryable／图片字节哈希——
# 不看 `_match`。回放 rv5_stale_visual_repro.py：输家当封面主角的 pass 原样留着，promote 照抄。

import analyze_reel_visuals as visual  # noqa: E402


def _probe_verdict(draft: dict, *, subject: str, moment: str, winner_visible: bool = True) -> dict:
    """probe 那一趟：模型按看得见的给答案，`clean_report` 按**当时**的草稿核，钉上图片哈希。"""
    draft["cover"]["portrait"] = {"image": "assets/reel/sabalenka-noskova-cover.jpg"}
    window = {"start": 100, "end": 110, "kind": "match_point", "winner_visible": winner_visible,
              "reason": "赛点 105s 落地", "confidence": 0.9}
    raw = {"cold_open": dict(window), "ending": dict(window),
           "cover": {"same_match": True, "subject": subject, "moment": moment,
                     "reason": "同场、握拳", "confidence": 0.9}}
    report, _ = visual.clean_report(raw, draft, 200.0)
    report.update(input_sha256="bytes-the-model-saw",
                  cover_image=draft["cover"]["portrait"]["image"])
    draft["_visual_evidence"] = report
    return report


def _workflow_rereviews(draft: dict, current_hash: str = "bytes-the-model-saw") -> bool:
    """reel-auto-ready.yml 那道重审条件（原样照抄；图片字节没变）。"""
    ev = draft.get("_visual_evidence") or {}
    return (ev.get("cover_image", "__missing__") == "__missing__"
            or draft["cover"]["portrait"]["image"] != ev.get("cover_image")
            or ev.get("visual_status") == "error" or ev.get("retryable") is True
            or current_hash != ev.get("input_sha256"))


def _analyze_reuses(draft: dict, current_hash: str = "bytes-the-model-saw") -> bool:
    """analyze_reel_visuals.main 的复用条件：同一批字节的 pass 不再问模型。"""
    ev = draft.get("_visual_evidence") or {}
    return ev.get("visual_status") == "pass" and ev.get("input_sha256") == current_hash


def test_赛果补齐之后_probe时给的封面人物是输家_不许带着旧pass转正(flash):
    flash.down = {"df_mh_1"}
    draft = _assemble()
    assert "winner" not in draft["_match"]
    # 封面照片是萨巴伦卡——这个世界里她是输家（feed home 诺斯科娃 6-4 6-3）；probe 那一趟不知道
    assert _probe_verdict(draft, subject="萨巴伦卡", moment="winner_celebration")["visual_status"] == "pass"

    flash.down.clear()
    assert a.retry_feed_blocks(draft) == "healed" and draft["_match"]["winner"] == "诺斯科娃"
    ev = draft["_visual_evidence"]
    assert ev["visual_status"] == "waiting" and ev["status"] == "waiting", (
        "赛果补齐之后旧 pass 原样留着——promote 会把输家抄进 cover.subject、自动渲、自动推")
    assert any("封面人物应为 诺斯科娃" in x for x in ev["problems"]), ev["problems"]
    assert visual.STALE_VERDICT in ev["problems"]
    assert "MiniMax 冷开场/结尾/封面视觉证据未通过" in promote.waiting_reasons(draft)
    # 第四轮复审：原来这里断言「同一张照片、同一份回答：不再花一次模型」——那份回答是 probe 那一趟
    # **瞎答的**（prompt 里没名字、没赢家），不能凭它判定照片里是输家；不重审就不告警地躺到过期
    assert _workflow_rereviews(draft) and "input_sha256" not in ev and ev["retryable"] is True
    assert not _analyze_reuses(draft)
    assert "本来也不过" in "\n".join(draft["_notes"])


def test_赛果补齐之后_重审只多一次_真是输家的照片停在waiting不反复问(flash, tmp_path, monkeypatch):
    """代价的上界：作废之后走的是**原来那条**重审路，`analyze_reel_visuals.main` 按新赛果核完把
    `retryable` 写回 false、哈希钉上——真是输家的照片停在 waiting（和 main 一样），下一班不再问。"""
    flash.down = {"df_mh_1"}
    draft = _assemble()
    _probe_verdict(draft, subject="萨巴伦卡", moment="winner_celebration")
    flash.down.clear()
    assert a.retry_feed_blocks(draft) == "healed"

    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"official photo")
    for i in range(2):
        (tmp_path / f"contact_{i:03d}.jpg").write_bytes(b"frame%d" % i)
    (tmp_path / "probe.json").write_text(json.dumps({"duration": 200.0}), encoding="utf-8")
    draft["cover"]["portrait"] = {"image": str(cover)}
    draft["_visual_evidence"]["cover_image"] = str(cover)
    path = tmp_path / "d.draft.json"
    path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    current = visual.evidence_hash(visual.select_contact_sheets(list(tmp_path.glob("contact_*.jpg"))), cover)
    assert _workflow_rereviews(draft, current)

    asked = []

    def model(draft, frames, cover, probe, key):  # 这一趟 prompt 里带着完整 _match：它认出了输家
        asked.append(draft["_match"]["winner"])
        window = {"start": 100, "end": 110, "kind": "match_point", "winner_visible": True,
                  "reason": "赛点 105s 落地", "confidence": 0.9}
        return visual.clean_report({"cold_open": dict(window), "ending": dict(window),
                                    "cover": {"same_match": True, "subject": "萨巴伦卡",
                                              "moment": "winner_celebration",
                                              "reason": "同场、握拳", "confidence": 0.9}},
                                   draft, float(probe["duration"]))

    monkeypatch.setattr(visual, "verified_minimax_report", model)
    monkeypatch.setenv("MINIMAX_API_KEY", "k")
    monkeypatch.setattr(sys, "argv", ["analyze_reel_visuals.py", "--draft", str(path),
                                      "--outdir", str(tmp_path), "--write"])
    assert visual.main() == 0 and asked == ["诺斯科娃"]
    after = json.loads(path.read_text(encoding="utf-8"))
    ev = after["_visual_evidence"]
    assert ev["visual_status"] == "waiting" and ev["retryable"] is False
    assert any("封面人物应为 诺斯科娃" in x for x in ev["problems"])
    assert not _workflow_rereviews(after, current), "重审过一次就停——不许每一班再问一遍"


@pytest.mark.parametrize("subject, winner_visible", [
    ("", True),            # 模型当时不认得这张脸，按提示「认不出留空」
    ("诺斯柯娃", True),     # 表外译名
    ("诺斯科娃", False),    # 当时不知道谁赢，winner_visible 蒙成 false
], ids=["subject空", "表外译名", "winner_visible蒙错"])
def test_赛果补齐之后_probe时瞎答的赢家照片_不许凭那份回答判死(flash, subject, winner_visible):
    """第四轮复审：probe 那一趟 `_match` 只有 flashscore_id、没有 `_cover_brief`，prompt 里一个名字都没有。
    照片**就是赢家**（诺斯科娃），模型只是没认出来——按新赛果核那份回答必然不过；这时留着哈希、
    `retryable` false，工作流不重审、`refresh_reel_cover` 见「已有封面」不换、`_feed_retry` 在 healed
    时摘掉，**不告警地躺到 PENDING_MAX_AGE**（回放 rv5r_stuck_after_heal.py，三种全卡）。"""
    flash.down = {"df_mh_1"}
    draft = _assemble()
    ev = _probe_verdict(draft, subject=subject, moment="winner_celebration",
                        winner_visible=winner_visible)
    # probe 那一趟：subject 核不了（不知道赢家）→ pass；winner_visible 蒙成 false → waiting、不可重试
    assert ev["visual_status"] == ("pass" if winner_visible else "waiting")
    assert not _workflow_rereviews(draft), "哈希钉着、不可重试：不补赛果就不会再审"
    flash.down.clear()
    assert a.retry_feed_blocks(draft) == "healed" and "_feed_retry" not in draft
    ev = draft["_visual_evidence"]
    assert len(ev["problems"]) > 1, "那份回答按新赛果本来也不过——两句都留着给人看"
    assert ev["visual_status"] == "waiting", "旧回答不过，照样不许转正"
    assert "MiniMax 冷开场/结尾/封面视觉证据未通过" in promote.waiting_reasons(draft)
    assert _workflow_rereviews(draft), "不重审就是不告警地丢掉这一场"
    assert not _analyze_reuses(draft)


def test_赛果补齐之后_旧结论对得上也作废_走原来那条重审路(flash):
    """模型当时不知道赢家（`winner_visible` 是蒙的），对得上也只是碰巧——作废，按新赛果重审。
    `input_sha256` 必须摘掉：`analyze_reel_visuals.main` 见同一批字节的 pass 就原样复用。"""
    flash.down = {"df_mh_1"}
    draft = _assemble()
    _probe_verdict(draft, subject="诺斯科娃", moment="winner_celebration")
    flash.down.clear()
    assert a.retry_feed_blocks(draft) == "healed"
    ev = draft["_visual_evidence"]
    assert ev["visual_status"] == "waiting" and visual.STALE_VERDICT in ev["problems"]
    assert "input_sha256" not in ev, "不摘哈希，重审那一趟也会复用旧 pass"
    assert _workflow_rereviews(draft) and not _analyze_reuses(draft)
    assert "MiniMax 冷开场/结尾/封面视觉证据未通过" in promote.waiting_reasons(draft), (
        "没配 MINIMAX key、重审没发生时，也不许拿旧 pass 转正")


def test_爆冷_probe时按赢家庆祝判不合格的输家在拼_补齐之后要重审_不许卡到过期(flash):
    flash.down = {"df_mh_1"}
    draft = _assemble(away_rank=40)  # 世界第 40 的诺斯科娃赢了世界第 1
    ev = _probe_verdict(draft, subject="萨巴伦卡", moment="loser_fighting")
    assert ev["visual_status"] == "waiting" and ev["retryable"] is False
    assert not _workflow_rereviews(draft), "改之前的样子：waiting ＋ 不可重试，永远不会再审"

    flash.down.clear()
    assert a.retry_feed_blocks(draft) == "healed"
    assert draft["_cover_brief"]["preferred_moment_key"] == "loser_fighting"
    assert _workflow_rereviews(draft), "补上爆冷 brief 之后，存着的回答对得上——要按新赛果重审"
    assert "input_sha256" not in draft["_visual_evidence"]


def test_赛果没变的重跑不碰视觉结论_接口失败的也不碰(flash):
    """只补 stats（`_match` 早就 verified）不花一次模型；`error`（接口失败）本来就会重审。"""
    flash.down = {"df_st_1"}
    draft = _assemble()
    assert draft["_feed_retry"]["blocks"] == ["stats"] and draft["_match"]["winner"] == "诺斯科娃"
    kept = dict(_probe_verdict(draft, subject="诺斯科娃", moment="winner_celebration"))
    flash.down.clear()
    assert a.retry_feed_blocks(draft) == "healed"
    assert draft["_visual_evidence"] == kept

    flash.down = {"df_mh_1"}
    broken = _assemble()
    broken["_visual_evidence"] = error = {"visual_status": "error", "status": "waiting",
                                         "retryable": True, "problems": ["MiniMax API：timeout"]}
    flash.down.clear()
    assert a.retry_feed_blocks(broken) == "healed" and broken["_visual_evidence"] == error


def test_赛果还没定下来的那一趟不碰视觉结论_定下来那一趟才处置(flash, monkeypatch):
    """反查 id 和逐局表都读失败：第一班只补上 id（`_match` 变了，逐局表还挂着）——赛果没定，
    promote 本来就不收；这时作废，工作流会拿半截赛果再问一次模型，下一班补齐又作废一次。"""
    state = {"id_down": True}

    def resolve(home, away):
        if state["id_down"]:
            raise fs.FeedUnavailable("近期赛果喂料全部读取失败：-1: Flashscore HTTP 503")
        return MID

    monkeypatch.setattr(a, "resolve_match_id", resolve)
    flash.down = {"df_mh_1"}
    draft = _assemble(flashscore_id=None)
    kept = dict(_probe_verdict(draft, subject="萨巴伦卡", moment="winner_celebration"))
    state["id_down"] = False
    assert a.retry_feed_blocks(draft) == "retry"
    assert draft["_match"] == {"flashscore_id": MID}, "id 这一班补上了，`_match` 变了"
    assert draft["_visual_evidence"] == kept, "赛果没定，不花一次模型"
    flash.down.clear()
    assert a.retry_feed_blocks(draft) == "healed"
    assert draft["_visual_evidence"]["visual_status"] == "waiting", "赛果定下来那一班照样处置"


def test_重审之后再走一遍apply_story_结尾不许放两遍():
    """作废之后重审会第二次走 apply_story；上一趟写的结尾兑现段带旁白（editorial.question），
    原来会被当成正文留下，再接一段新结尾——同一个结局放两遍。"""
    draft = {"editorial": {"question": "她还能走多远？"},
             "segments": [{"start": 10, "end": 20, "narration": "开局"},
                          {"start": 30, "end": 40, "narration": "第二盘"}]}
    report = {"cold_open": {"start": 100, "end": 110, "reason": "赛点"},
              "ending": {"start": 98, "end": 112, "reason": "赛点和握手"}}
    rows, zh = [(104, "Match point.")], [("Match point.", "赛点。")]
    once = visual.apply_story(draft, report, rows, zh)
    shape = [(seg["start"], seg["end"]) for seg in once["segments"]]
    source = once["_segments_source"]
    twice = visual.apply_story(once, report, rows, zh)
    assert [(seg["start"], seg["end"]) for seg in twice["segments"]] == shape, twice["segments"]
    assert twice["_segments_source"] == source


# ── 第三轮复审的几处小补：退避、墙钟上限、崩了、撤了文案都要记账点名、重新布置 ──────

def _cli(path: Path, *extra: str) -> str:
    import contextlib  # noqa: PLC0415
    import io  # noqa: PLC0415

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert rfb.main(["--draft", str(path), "--write", *extra]) == 0
    return buf.getvalue()


def test_重跑之间要退避_不许三班连着把次数花光(flash, tmp_path, monkeypatch):
    flash.down = {"df_mh_1"}
    draft = _assemble()
    last = datetime(2026, 9, 28, 8, tzinfo=timezone.utc)
    draft["_feed_retry"].update(tries=1, last_at="2026-09-28T08:00:00Z")
    path = tmp_path / "d.draft.json"
    path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.setattr(rfb, "_now", lambda: last + timedelta(minutes=15))
    flash.calls.clear()
    assert _cli(path).strip().splitlines()[-1] == "later"
    assert flash.calls == [] and path.read_bytes() == before, "退避期内一个请求都不发、不改草稿"
    assert a.feed_retry_due_at({"tries": 2, "last_at": "2026-09-28T08:00:00Z"}) == last + timedelta(minutes=40)
    assert a.feed_retry_due_at({"tries": 0, "last_at": "2026-09-28T08:00:00Z"}) is None, "第一次不等"
    monkeypatch.setattr(rfb, "_now", lambda: last + timedelta(minutes=21))
    assert _cli(path).strip().splitlines()[-1] == "retry" and flash.calls


def test_被工作流掐掉的那一趟也算一次_试满照样停手(flash, tmp_path):
    flash.down = {"df_mh_1"}
    path = tmp_path / "d.draft.json"
    path.write_text(json.dumps(_assemble(), ensure_ascii=False), encoding="utf-8")
    flash.calls.clear()
    got = [_cli(path, "--timed-out", "120").strip().splitlines()[-1] for _ in range(a.FEED_RETRY_MAX)]
    assert got == ["retry"] * (a.FEED_RETRY_MAX - 1) + ["gave_up"]
    assert flash.calls == [], "补记那一趟不读 feed"
    ledger = json.loads(path.read_text(encoding="utf-8"))["_feed_retry"]
    assert ledger["tries"] == a.FEED_RETRY_MAX and ledger["exhausted_at"]
    assert "120s 内没读完" in ledger["errors"]["points"]


def test_重跑崩了_记账停手点名_不写半截改动(flash, tmp_path, monkeypatch):
    flash.down = {"df_mh_1"}
    path = tmp_path / "d.draft.json"
    draft = _assemble()
    order = [p["name_en"] for p in draft["cover"]["matchup"]]
    path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    def crash(draft):
        draft["cover"]["matchup"].reverse()  # 改了一半再崩
        raise ValueError("草稿 cover.matchup 不是两位带英文名的球员")

    monkeypatch.setattr(rfb, "retry_feed_blocks", crash)
    out = _cli(path)
    assert out.strip().splitlines()[-1] == "broken" and "::warning::" in out
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [p["name_en"] for p in saved["cover"]["matchup"]] == order, "从盘上那份记账，不写改了一半的"
    assert saved["_feed_retry"]["exhausted_at"] and "崩了" in saved["_feed_retry"]["needs_human"][0]
    assert "崩了" in summary.read_text(encoding="utf-8")
    flash.calls.clear()
    assert a.retry_feed_blocks(saved) == "exhausted", "崩过、停手了的，下一次调用不再读 feed"
    assert flash.calls == []


def test_撤了文案和重读也一样的错_打warning写摘要_只打一次(flash, tmp_path, monkeypatch):
    flash.down = {"df_mh_1"}
    draft = _assemble()
    draft["editorial"] = {"thesis": "萨巴伦卡 6-2 6-1 横扫", "narration": ["开局"]}
    path = tmp_path / "d.draft.json"
    path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    flash.down.clear()
    out = _cli(path)
    assert out.strip().splitlines()[-1] == "copy_dropped" and "::warning::" in out
    assert "文案对不上" in summary.read_text(encoding="utf-8")
    assert _cli(path).strip().splitlines()[-1] == "none", "账上没有要重读的块了"

    flash.down = {"df_mh_1"}
    path.write_text(json.dumps(_assemble(), ensure_ascii=False), encoding="utf-8")

    def garbled(mid):
        raise ValueError("df_mh_1 的 HL 字段对不上")

    monkeypatch.setattr(a, "points", garbled)
    out = _cli(path)
    assert out.strip().splitlines()[-1] == "dropped" and "::warning::" in out
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert "重读也一样的错" in saved["_feed_retry"]["needs_human"][0]
    assert "重读也一样的错" in summary.read_text(encoding="utf-8")


def test_人看过之后重新布置_次数清零_没得重读的整个摘掉(flash, tmp_path):
    flash.down = {"df_mh_1"}
    draft = _assemble()
    draft["_feed_retry"].update(tries=3, exhausted_at="2026-09-28T08:00:00Z")
    path = tmp_path / "d.draft.json"
    path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    assert _cli(path, "--rearm").strip().splitlines()[-1] == "rearmed"
    ledger = json.loads(path.read_text(encoding="utf-8"))["_feed_retry"]
    assert ledger["tries"] == 0 and "exhausted_at" not in ledger and ledger["blocks"] == ["points"]

    done = {"slug": "x", "_feed_retry": {"blocks": [], "needs_human": ["撤了文案"]}}
    assert a.rearm_feed_retry(done) and "_feed_retry" not in done


def test_要人看的账跨班留着_后一班读通了也不摘(flash):
    """这一班补上逐局表、撤了文案，stats 还没读到（retry）；下一班 stats 也读通了——
    账要是跟着「全读通了」一起摘掉，撤文案那一句告警就没了，草稿照样躺到过期。"""
    flash.down = {"df_mh_1", "df_st_1"}
    draft = _assemble()
    assert draft["_feed_retry"]["blocks"] == ["stats", "points"]
    draft["editorial"] = {"thesis": "萨巴伦卡 6-2 6-1 横扫", "narration": ["开局"]}
    flash.down = {"df_st_1"}
    assert a.retry_feed_blocks(draft) == "retry" and "editorial" not in draft
    flash.down.clear()
    assert a.retry_feed_blocks(draft) == "healed"
    ledger = draft["_feed_retry"]
    assert ledger["blocks"] == [] and "文案对不上" in ledger["needs_human"][0]
