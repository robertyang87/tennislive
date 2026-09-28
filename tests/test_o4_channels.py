"""O4 自动换图和渲前预检的渠道、日期、团体赛名单（2026-09-28）。

来路：O4 上线第一班（run 36378419750，apply=false）一张都没换成——

| 目标 | 卡在哪 | 这里的判据 |
|---|---|---|
| 杭州 ATP 三条 | 只查了 AP，而 AP 在 runner 上 403 | 渠道只登记一份（`cover_channels.CHANNELS`），每一档都出一行；AP 的 403 认成 Cloudflare 挑战页、记「没查成」 |
| safiullin-bu | spec 没有 `_match.start_utc`／`flashscore_id` | 开赛时刻按 spec 记下的 `_start_time_source`、再按首推时刻推，并说是哪一个 |
| zverev-tien（拉沃尔杯） | 8 张官网候选全卡在「只写姓」「没写对手」 | 团体赛按名单放宽（真图注录在 `fixtures/cover_upgrade/`） |

外加返工审计：窗口里 11 条第一次推的是抽帧封面——渲前预检（`cover_upgrade.preflight`）
在 match-reel render 那一步查一遍，有一张全过就不许发抽帧（手写拦、自动只报、没有就不拦）。

复审（同日）补的：只拦**第一次**渲染、推过的只报（D2）；团体赛放宽之后替补席／看台不换、
图注主语是别人的不换、EXIF 拍摄日期不是这场的不换（D3，zverev-tien 那 8 张真图注前后对照）；
列出来的开赛时间只当下界（nit 1）；预检和 `--write` 过同一道正式封面闸（nit 2）；
这一步的秒数装得进 job 预算（nit 3）。

全部走录下来的数据，**测试里不联网**。
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import cover_channels as cch  # noqa: E402
import cover_upgrade as cu  # noqa: E402
import find_cover_photo as fcp  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "cover_upgrade"
FACES = ROOT / "tests" / "fixtures" / "faces"
WONG_FRAME = FACES / "wong-vallejo-cover-frame-689.8.jpg"

#: flashscore `dc_1_fgVBhTPH`（拉沃尔杯第 10 场兹维列夫—勒纳·钱）2026-09-28 沙箱实取：
#: `DC÷1790515500`＝09-27 13:25Z、`DD÷1790522080`＝15:14:40Z
ZT_FEED = "DC÷1790515500¬DD÷1790522080¬~"
#: `dc_1_xvQdqyYj`（第 6 场兹维列夫—德米纳尔）：09-26 14:25Z ~ 16:26:09Z
ZD_FEED = "DC÷1790432700¬DD÷1790439969¬~"


class _Resp:
    """`requests` 的 HTTPError 挂着的那个 response——只要 status_code 和 headers。"""

    def __init__(self, status: int, headers: dict):
        self.status_code = status
        self.headers = headers


def _challenge(url: str, *a, **k):
    """AP 2026-09-28 实测：403 ＋ `cf-mitigated: challenge` ＋「Just a moment...」。"""
    import requests  # noqa: PLC0415

    exc = requests.HTTPError(f"403 Client Error: Forbidden for url: {url}")
    exc.response = _Resp(403, {"Server": "cloudflare", "cf-mitigated": "challenge",
                               "Content-Type": "text/html; charset=UTF-8"})
    raise exc


# ---------------------------------------------------------------- ① 一份渠道清单

def test_渠道只登记一份_人查和O4用同一张单子():
    keys = [c.key for c in cch.CHANNELS]
    assert len(keys) == len(set(keys)), keys
    # 人查逐档印细节：每一档都有自己的印法，没有漏的、没有多的
    assert set(fcp._SHOW) == set(keys), (set(fcp._SHOW) ^ set(keys))
    # O4：default_sweeps 就是这份清单，一档不落、顺序一样
    ctx = cu.MatchContext(slug="x", subject_zh="黄泽林", subject_en="Coleman Wong", surname="wong",
                          opponent_surname="vallejo", event_en="Hangzhou", tz="Asia/Shanghai",
                          tour="atp", match_dates={date(2026, 9, 26)})
    q = cu.o4_query(ctx)
    assert [name for name, _run in cu.default_sweeps(ctx)] == [c.name(q) for c in cch.CHANNELS]
    # 不许再有第二份：cover_upgrade 自己不直接调任何一档的 sweep_*，也不再登记官网域名
    import inspect  # noqa: PLC0415

    src = inspect.getsource(cu)
    for name in ("sweep_wta(", "sweep_ap(", "sweep_local_paper(", "sweep_tournament(",
                 "sweep_usopen(", "sweep_cn_media(", "_LOCAL_PAPERS"):
        assert name not in src, f"cover_upgrade 里又抄了一份渠道：{name}"
    assert all(len(row) == 3 for row in cu.EVENTS), "官网域名只在 cover_channels.EVENT_SITES 登记"
    assert cch.event_site("Laver Cup") == "lavercup.com"
    assert cch.event_site("Western & Southern Open, Cincinnati") == "cincinnatiopen.com"
    assert cch.event_site("Hangzhou") is None
    # O4 不查的每一档都写了为什么（机器闸在那一档恒过不了）
    for c in cch.CHANNELS:
        assert (c.o4_off == "") or len(c.o4_off) > 20, c.key


def test_每一档一行_查了_查空_没查成_没跑_O4不查五种说法不一样():
    rows = [cch._row("https://x/a.jpg")]
    lines = {
        "查了": cch.status_line(cch.ChannelResult("paper", "当地报纸每日图集", "ran", "当地报纸",
                                                   rows=rows, detail="www.cincinnati.com")),
        "查空": cch.status_line(cch.ChannelResult("ap", "AP 通讯社", "ran")),
        "没查成": cch.status_line(cch.ChannelResult("ap", "AP 通讯社", "blocked", why="403")),
        "没跑": cch.status_line(cch.ChannelResult("usopen", "美网官方图片接口", "skipped", why="不是美网")),
        "O4 不查": cch.status_line(cch.ChannelResult("cn-media", "中文媒体", "off", why="没有图注")),
    }
    assert lines["查了"] == "当地报纸 www.cincinnati.com：1 张"
    assert "查空" in lines["查空"] and "0 张" in lines["查空"]
    assert "没查成，不是查空" in lines["没查成"]
    assert "没跑——不是美网" in lines["没跑"]
    assert "O4 不查——没有图注" in lines["O4 不查"]
    assert len({line.split("：", 1)[1][:4] for line in lines.values()}) == 5, lines


def test_AP的Cloudflare挑战页记没查成_第一页就停(monkeypatch):
    """2026-09-28：runner 那一班报「403 Forbidden」，沙箱实测是 Cloudflare 人机挑战
    （`cf-mitigated: challenge`）——换 UA／换入口都过不去，也不该去绕。认出来、记「没查成」、
    第一页就停（原来 3 条搜索 ＋ 频道页一共撞 4 次挑战页）。"""
    asked: list[str] = []

    def fake(url, timeout=30):
        asked.append(url)
        _challenge(url)

    monkeypatch.setattr(fcp, "_get", fake)
    stats: dict = {}
    assert fcp.sweep_ap("Medvedev", "Hangzhou", stats=stats) == []
    assert stats["pages_read"] == 0 and "Cloudflare" in stats["blocked"], stats
    assert len(asked) == 1, asked
    res = cch.run_channel(cch.channel("ap"), cch.Query(player="medvedev", event="Hangzhou"), o4=True)
    assert res.status == "blocked" and "cf-mitigated: challenge" in res.why, res
    # 对照组：偶发的连接错误不是挑战页——照旧四页都试一遍，报的是那个错
    asked.clear()

    def reset(url, timeout=30):
        asked.append(url)
        raise ConnectionError("reset by peer")

    monkeypatch.setattr(fcp, "_get", reset)
    stats = {}
    fcp.sweep_ap("Medvedev", "Hangzhou", stats=stats)
    assert len(asked) == 4 and "blocked" not in stats and "ConnectionError" in stats["errors"][0]


def test_O4第一班那三条杭州ATP_每一档都有一行_一档都没查成不许说成查过(monkeypatch):
    """run 36378419750 的报告里杭州三条只有一行「AP 通讯社：取不到」，别的渠道根本不出现。
    现在七档都出一行，结论分得清「一档都没查成（结果未知）」和「查成了、没有全过」。"""
    monkeypatch.setattr(fcp, "_get", _challenge)
    for name in ("sweep_wta", "sweep_local_paper", "sweep_tournament", "sweep_usopen",
                 "sweep_wta_articles"):
        monkeypatch.setattr(fcp, name, lambda *a, **k: pytest.fail("这一档在杭州 ATP 上不该发请求"))
    ctx = cu.MatchContext(slug="medvedev-royer-hangzhou-2026-r2", subject_zh="梅德韦杰夫",
                          subject_en="Daniil Medvedev", surname="medvedev",
                          opponent_surname="royer", event_en="Hangzhou", tz="Asia/Shanghai",
                          tour="atp", start_utc=datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc),
                          match_dates={date(2026, 9, 26)})
    cands, notes, results = cu.search(ctx)
    assert cands == []
    by = {r.key: r.status for r in results}
    assert by == {"wta": "skipped", "wta-articles": "off", "ap": "blocked", "usopen": "off",
                  "paper": "skipped", "event-site": "skipped", "cn-media": "off"}, by
    assert len([n for n in notes if "：" in n]) == 7 + 1, notes          # 七档 ＋ 末尾那一行
    assert notes[-1].startswith("这一趟：没查成 1（AP 通讯社）"), notes[-1]
    assert "结果未知" in cu.verdict_line([], results)
    # 对照组：真查成了、只是没有一张全过
    ok = [cch.ChannelResult("event-site", "赛事官网 WordPress 媒体库", "ran", rows=[{}])]
    assert "查成的 1 档里 3 张候选没有一张全过" in cu.verdict_line([{}, {}, {}], ok)


# ---------------------------------------------------------------- ③ 没有开赛时刻

def _hangzhou_spec(**match) -> dict:
    return {"slug": "safiullin-bu-hangzhou-2026-qf",
            "topbar": {"line1": "2026 ATP250 杭州 1/4决赛"},
            "cover": {"eyebrow": "赛场之上", "subject": "萨菲乌林",
                      "matchup": [{"name": "萨菲乌林", "name_en": "Roman Safiullin"},
                                  {"name": "布云朝克特", "name_en": "Yunchaokete Bu"}],
                      "portrait": {"frame_at": 99.1}},
            "_match": {"status": "result_verified", "source": "official_tournament_api",
                       "source_id": "4713_2026_MS005", **match}}


def test_没有开赛时刻_按spec记下的或首推时刻推当地日期_并说是哪一个():
    pushed = datetime(2026, 9, 27, 14, 47, 45, tzinfo=timezone.utc)   # 发布账本第一次 sent
    no_flashscore = lambda _id: pytest.fail("spec 里记着开赛时刻，不该再去问 flashscore")  # noqa: E731
    # ① safiullin-bu 真 spec 的 `_start_time_source`（sofascore 列的开赛时刻）
    spec = _hangzhou_spec()
    spec["_start_time_source"] = {
        "url": "https://www.sofascore.com/tennis/match/yunchaokete-bu-roman-safiullin/FYZsCJbc",
        "reported_utc": "2026-09-27T10:45:00Z", "beijing": "2026-09-27T18:45:00+08:00"}
    ctx = cu.match_context(spec, times=no_flashscore, pushed_at=pushed)
    assert not ctx.problems and ctx.match_dates == {date(2026, 9, 27)}, ctx
    assert ctx.date_source.startswith("_start_time_source.reported_utc（www.sofascore.com")
    assert not ctx.date_window and ctx.start_utc == datetime(2026, 9, 27, 10, 45, tzinfo=timezone.utc)
    # 复审 nit 1：列出来的开赛时间 ≤ 真开赛，只是**下界**——报告里说出来
    assert ctx.start_lower_bound and "只当下界" in ctx.date_source, ctx.date_source
    assert cu.static_problems(spec) == [], "有记下的开赛时刻，--plan 不许再把它挡掉"
    # ② 什么都没记：按首推时刻推两天窗口（北京＝当地），说是哪一个
    bare = _hangzhou_spec()
    ctx = cu.match_context(bare, times=no_flashscore, pushed_at=pushed)
    assert not ctx.problems and ctx.date_window, ctx.problems
    assert ctx.match_dates == {date(2026, 9, 26), date(2026, 9, 27)}
    assert "首推时刻 09-27 14:47Z" in ctx.date_source and ctx.start_utc is None
    # 窗口下：点了对手、写了日期的过；不点对手的不过；只能靠上传时刻判的不过
    ap = "Roman Safiullin beats Yunchaokete Bu at the Hangzhou Open on Sunday, Sept. 27, 2026. (AP Photo)"
    assert cu.metadata_problems(cu.Candidate("ap", "https://a/1.jpg", caption=ap), ctx) == []
    no_opp = ap.replace("beats Yunchaokete Bu ", "celebrates ")
    assert any("两天窗口" in p for p in cu.metadata_problems(
        cu.Candidate("ap", "https://a/2.jpg", caption=no_opp), ctx))
    undated = cu.Candidate("event-site", "https://h/3.jpg", event_owned=True,
                           caption="Roman Safiullin beats Yunchaokete Bu",
                           meta_utc="2026-09-27T12:00:00")
    assert any("开赛时刻" in p for p in cu.metadata_problems(undated, ctx))
    # ③ 首推时刻也不知道（不联网的 --plan 以前的口径）：照旧判不了
    assert any("开赛时刻" in p for p in cu.match_context(bare, times=no_flashscore).problems)
    # ④ 记着 flashscore id 的照旧先问 flashscore，而且说出来
    fs = _hangzhou_spec(flashscore_id="FYZsCJbc")
    ctx = cu.match_context(fs, times=lambda _id: (datetime(2026, 9, 27, 10, 50, tzinfo=timezone.utc),
                                                  None), pushed_at=pushed)
    assert ctx.date_source == "flashscore dc_1_FYZsCJbc" and not ctx.date_window
    assert not ctx.start_lower_bound


# ---------------------------------------------------------------- ④ 团体赛名单

def _laver_media() -> list[dict]:
    return json.loads((FIX / "lavercup-media-2026-09-27.json").read_text(encoding="utf-8"))["media"]


def _laver_spec(subject="兹维列夫", subject_en="Alexander Zverev", opp="勒纳·钱",
                opp_en="Learner Tien", day="第三天", fs="fgVBhTPH") -> dict:
    return {"slug": "zverev-tien-laver-cup-2026", "topbar": {"line1": f"2026 拉沃尔杯 {day}"},
            "cover": {"eyebrow": "赛场之上", "subject": subject,
                      "matchup": [{"name": subject, "name_en": subject_en},
                                  {"name": opp, "name_en": opp_en}],
                      "portrait": {"frame_at": 126.0}},
            "_match": {"flashscore_id": fs}}


def _laver_candidates(monkeypatch, player: str) -> list:
    media = _laver_media()
    monkeypatch.setattr(fcp, "_get_json", lambda url, timeout=40: (
        media if "/media?" in url else [], {"X-WP-TotalPages": "1"}))
    got = cch.run_channel(cch.channel("event-site"),
                          cch.Query(player=player, event="Laver Cup", date="2026-09-27", days=3),
                          o4=True)
    assert got.status == "ran", got
    return [cu.Candidate(got.key, **row) for row in got.rows]


def test_拉沃尔杯官网真图注_只写姓按名单认_这一天只打一场才不要求对手(monkeypatch):
    """O4 第一班 zverev-tien 的 8 张官网候选（录在 fixtures 里，原样）：原来一律卡在「只写姓」
    「没写对手」。官网自己写的图注，拍的是他本人时**从来不写对手**；写了对手的两张，拍的恰恰
    是对手那边（「Team World's Learner Tien returns another Zverev smash.」）。"""
    ctx = cu.match_context(_laver_spec(), times=lambda _id: cu.parse_dc_feed(ZT_FEED))
    assert not ctx.problems and ctx.roster_name == "Laver Cup 2026", ctx.problems
    cands = {c.url.rsplit("/", 1)[-1]: c for c in _laver_candidates(monkeypatch, "zverev")}
    assert len(cands) == 8, sorted(cands)                     # 和 run 36378419750 报的 8 张一致

    def verdict(name):
        relaxed: list[str] = []
        return cu.metadata_problems(cands[name], ctx, relaxed), relaxed

    # 「Alexander Zverev adds another Laver Cup title to his resume.」——全名、不写对手
    probs, relaxed = verdict("JF1_7191_pmjUPNSQ_20260927042135.jpg")
    assert probs == [] and any("只打了第 10 场" in r for r in relaxed), (probs, relaxed)
    # 「Team Europe players and captains get around Zverev.」——只写姓、不写对手，两条都放宽了，
    # 可主语是一群人（复审：团队当主语的不认成拍他本人，`team_subject_problem`）
    probs, relaxed = verdict("CB_36487_4jVq5VqG_20260927041747.jpg")
    assert len(relaxed) == 2 and len(probs) == 1 and "是团队（Team Europe）当主语" in probs[0], \
        (probs, relaxed)
    # 同样只写姓、不写对手、主语是他本人的：两条都放宽、点名闸过
    alone = cu.Candidate("event-site", "https://lavercup.com/wp-content/uploads/2026/09/z1.jpg",
                         event_owned=True, meta_utc="2026-09-27T15:10:00",
                         caption="Zverev roars after clinching the Cup for Team Europe.")
    relaxed = []
    assert cu.metadata_problems(alone, ctx, relaxed) == [] and len(relaxed) == 2, relaxed
    # Getty 那张捧杯（说明写着 9 月 27 日、不写对手）
    assert verdict("GettyImages-2297411314.jpg")[0] == []
    # 前一天的图照旧挡在日期上
    probs, _ = verdict("JF1_3198_miqrpdia_20260926042538.jpg")
    assert any("2026-09-26" in p for p in probs), probs
    # 官网这批 1200 宽的图，放宽之后卡在分辨率上（口径没变：机器不替人认领放大）
    row = next(r for r in cu.evaluate(cu.Target("zverev-tien-laver-cup-2026", _laver_spec(),
                                                datetime.now(timezone.utc), Path("x")),
                                      ctx, [cands["JF1_7191_pmjUPNSQ_20260927042135.jpg"]],
                                      fetch=lambda _u: pytest.fail("分辨率不够的不下"))[1])
    assert any("分辨率不够" in p for p in row["problems"]), row

    # 同一批图注拿到 9/26 的兹维列夫身上：他那天第 6 场单打、第 8 场双打——**照旧要点对手**
    ctx26 = cu.match_context(_laver_spec(opp="德米纳尔", opp_en="Alex de Minaur", day="第二天",
                                         fs="xvQdqyYj"), times=lambda _id: cu.parse_dc_feed(ZD_FEED))
    same = cu.Candidate("event-site", "https://lavercup.com/a.jpg", event_owned=True,
                        caption="Alexander Zverev pumps his fist.", meta_utc="2026-09-26T15:00:00")
    assert any("对手" in p for p in cu.metadata_problems(same, ctx26))
    # 开赛时刻取不到、日期是按首推时刻推的两天窗口：团体赛也不放宽对手
    def down(_id):
        raise RuntimeError("flashscore 取不到")

    # 霍达尔整个窗口（9/24~9/25，首推 9/25 20:37Z）里只打了第 3 场——只看名单的话会放宽，
    # 而窗口不是开赛时刻算出来的，不许
    jodar = _laver_spec(subject="霍达尔", subject_en="Rafael Jodar", opp="布勃利克",
                        opp_en="Alexander Bublik", day="首日", fs="hheFZ9KN")
    ctxw = cu.match_context(jodar, times=down,
                            pushed_at=datetime(2026, 9, 25, 20, 37, tzinfo=timezone.utc))
    assert ctxw.date_window and not ctxw.problems, ctxw.problems
    assert len(cu.roster_matches(ctxw.roster, "jodar", ctxw.match_dates)) == 1
    debut = cu.Candidate("event-site", "https://lavercup.com/wp-content/uploads/2026/09/j.jpg",
                         event_owned=True, meta_utc="2026-09-25T21:21:15",
                         caption="Rafael Jodar Rafael Jodar makes a winning debut.")
    assert any("对手" in p for p in cu.metadata_problems(debut, ctxw))
    # 不是官网自己的图（AP／Getty 转载）不放宽对手
    ap = cu.Candidate("ap", "https://assets.apnews.com/a.jpg",
                      caption="Alexander Zverev celebrates at the Laver Cup in London on Sunday, "
                              "Sept. 27, 2026. (AP Photo)")
    assert any("对手" in p for p in cu.metadata_problems(ap, ctx))
    # 图注点了名单上的别人：他在看队友打，不放宽
    bench = cu.Candidate("event-site", "https://lavercup.com/b.jpg", event_owned=True,
                         caption="Alexander Zverev cheers for Cobolli and Mensik.",
                         meta_utc="2026-09-27T14:00:00")
    assert any("对手" in p for p in cu.metadata_problems(bench, ctx))


def test_只写姓_名单上撞姓就不认_不是团体赛照旧要全名():
    ctx = cu.match_context(_laver_spec(), times=lambda _id: cu.parse_dc_feed(ZT_FEED))
    only = cu.Candidate("event-site", "https://lavercup.com/c.jpg", event_owned=True,
                        caption="Zverev against Tien on Sunday.", meta_utc="2026-09-27T14:00:00")
    assert cu.metadata_problems(only, ctx) == []
    # 名单上多一个同姓的（塞伦多洛兄弟那种）：只写姓认不出是谁
    twin = json.loads(json.dumps(ctx.roster))
    twin["teams"]["Team Europe"]["alternates"].append("Mischa Zverev")
    ctx.roster = twin
    assert any("只有姓" in p for p in cu.metadata_problems(only, ctx))
    # 不是团体赛（没有名单）：照旧要全名
    wong = cu.MatchContext(slug="w", subject_zh="黄泽林", subject_en="Coleman Wong", surname="wong",
                           opponent_surname="vallejo", event_en="Hangzhou", tz="Asia/Shanghai",
                           start_utc=datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc),
                           match_dates={date(2026, 9, 26)})
    ap = cu.Candidate("ap", "https://a/w.jpg", caption="Wong beats Vallejo at the Hangzhou Open on "
                                                       "Saturday, Sept. 26, 2026.")
    assert any("只有姓" in p for p in cu.metadata_problems(ap, wong))


#: zverev-tien 那 8 张官网候选（`_laver_candidates`，录的原样）**复审 D3 之后**的点名闸：
#: None＝点名闸过了（接着卡分辨率）；否则是报错里必须有的几句。
#: 之前：7 张过点名闸、6 张卡 1200 宽，剩下那张（-scaled 替补席）下下来只有认人闸拦得住（mismatch 0.13）。
#: 复审第二轮：「Team Europe celebrate after …」「Team Europe players and captains get around …」
#: 团队当主语，也拦在点名闸上——过点名闸的剩 2 张（Getty 捧杯、JF1_7191），全卡 1200 宽。
ZT_AFTER = {
    "GettyImages-2297411314.jpg": None,               # Zverev celebrates with the Laver Cup trophy
    "TD2_6943_UhmuiH5g_20260927042054.jpg": ("是团队（Team Europe）当主语",),  # 全名＋对手都点了，没放宽
    "CB_36487_4jVq5VqG_20260927041747.jpg": ("是团队（Team Europe）当主语",),  # players and captains …
    "JF1_7191_pmjUPNSQ_20260927042135.jpg": None,     # Alexander Zverev adds another Laver Cup title
    "JF2_5479_oQpjCT2q_20260927052924.jpg": ("最先点名的是名单上的「tien」", "「support」"),
    "JF1_6497_6vkUqRmf_20260927035914.jpg": ("最先点名的是名单上的「tien」",),
    "TD2_6943_vfR8lRDz_20260927042054-scaled.jpg": ("「bench」",),
    "JF1_3198_miqrpdia_20260926042538.jpg": ("说明写的是 2026-09-26",),
}


def test_拉沃尔杯官网8张_放宽之后替补席看台和主语是别人的不换_一张都不用下(monkeypatch):
    """复审 D3(a)(b)：团体赛放宽（名单认姓、官网图注不写对手）之后，认错人原来只剩认人闸一道——
    「Team World's Learner Tien returns another Zverev smash.」「Team World support Learner Tien against
    Zverev.」主语是勒纳·钱；「The Team Europe bench rise to celebrate Zverev's …」拍的是替补席
    （那张 -scaled 原图下下来认人 mismatch 0.13）。现在三张都在点名闸上就拦住；复审第二轮再收
    「Team Europe celebrate after …」「Team Europe players and captains get around …」（团队当主语），
    剩下 2 张（Getty 捧杯、JF1_7191）全卡 1200 宽——**一张都不用下**。"""
    ctx = cu.match_context(_laver_spec(), times=lambda _id: cu.parse_dc_feed(ZT_FEED))
    cands = {c.filename: c for c in _laver_candidates(monkeypatch, "zverev")}
    assert set(cands) == set(ZT_AFTER), sorted(cands)
    for name, want in ZT_AFTER.items():
        probs = cu.metadata_problems(cands[name], ctx)
        if want is None:
            assert probs == [], (name, probs)
        else:
            for says in want:
                assert any(says in p for p in probs), (name, says, probs)
    _chosen, rows = cu.evaluate(cu.Target("zverev-tien-laver-cup-2026", _laver_spec(),
                                          datetime.now(timezone.utc), Path("x")),
                                ctx, list(cands.values()),
                                fetch=lambda _u: pytest.fail("这 8 张一张都不该下"))
    assert all(r["problems"] for r in rows), rows
    # (b) 只管**放宽过**的：全名 ＋ 对手都点了的（AP 那种「Y … against X」）照旧交给认人闸
    ap = cu.Candidate("ap", "https://assets.apnews.com/t.jpg",
                      caption="Learner Tien of Team World returns to Alexander Zverev of Team Europe "
                              "at the Laver Cup in London on Sunday, Sept. 27, 2026. (AP Photo)")
    assert cu.metadata_problems(ap, ctx) == []
    # 主语是别人、只是没放宽的那一半（名单认姓）也要拦：只写姓 ＋ 点了对手
    tien_first = cu.Candidate("event-site", "https://lavercup.com/t2.jpg", event_owned=True,
                              caption="Tien chases down a Zverev drop shot.",
                              meta_utc="2026-09-27T14:00:00")
    assert any("最先点名的是名单上的「tien」" in p for p in cu.metadata_problems(tien_first, ctx))
    assert cu.first_roster_named("team europe players and captains get around zverev",
                                 ctx.roster) == "zverev"
    assert cu.first_roster_named("alex de minaur and taylor fritz pair up", ctx.roster) == "minaur"



def test_团队当主语的图注_不分放宽没放宽都不认成拍他本人(monkeypatch):
    """复审第二轮：录下的 lavercup.com 9/27 媒体库里 `TD2_6943_UhmuiH5g` 的 Getty 图注是
    「LONDON, ENGLAND – SEPTEMBER 27: Team Europe celebrate after Alexander Zverev of Team Europe defeats
    Learner Tien of Team World …」——全名 ＋ 对手 ＋ 日期全点了、**一条放宽都没走**，原来点名闸放行；
    而它和替补席那张 `TD2_6943_vfR8lRDz…-scaled` 是**同一个帧号**。团队当主语的一律不认成拍他本人、不下图，
    不是团体赛（没有名单）也一样。"""
    import dataclasses  # noqa: PLC0415

    ctx = cu.match_context(_laver_spec(), times=lambda _id: cu.parse_dc_feed(ZT_FEED))
    team = {c.filename: c for c in _laver_candidates(monkeypatch, "zverev")}[
        "TD2_6943_UhmuiH5g_20260927042054.jpg"]
    assert "SEPTEMBER 27: Team Europe celebrate after Alexander Zverev of Team Europe defeats Learner Tien" \
        in team.caption, team.caption                    # 录的原样，不是手写的
    relaxed: list[str] = []
    probs = cu.metadata_problems(team, ctx, relaxed)
    assert relaxed == [], "全名＋对手都点了——没走放宽，拦它的只能是这一条"
    assert len(probs) == 1 and "是团队（Team Europe）当主语" in probs[0], probs
    target = cu.Target("zverev-tien-laver-cup-2026", _laver_spec(), datetime.now(timezone.utc), Path("x"))
    chosen, rows = cu.evaluate(target, ctx, [team], fetch=lambda _u: pytest.fail("团队当主语的不下图"))
    assert chosen is None and rows[0]["problems"] == probs, rows
    # 没有名单（不是团体赛的那条路）也拦
    plain = dataclasses.replace(ctx, roster=None, roster_name="")
    assert any("当主语" in p for p in cu.metadata_problems(team, plain)), "不分放宽没放宽"

    def says(caption: str) -> str | None:
        return cu.team_subject_problem(cu.Candidate("ap", "https://a/t.jpg", caption=caption), ctx)

    # 团队只是他的头衔／定语：认
    assert says("Alexander Zverev of Team Europe celebrates after defeating Learner Tien of Team World.") is None
    assert says("Team Europe's Alexander Zverev celebrates his win over Learner Tien.") is None
    assert says("Team Europe player Alexander Zverev celebrates his win over Learner Tien.") is None
    assert says("Zverev roars after clinching the Cup for Team Europe.") is None
    assert says("Alexander Zverev celebrates with his team after beating Learner Tien.") is None
    # 团队当主语、或者主语是队里的别人：不认
    assert "当主语" in says("Team Europe players and captains get around Zverev.")
    assert "的别人" in says("Team Europe captain Yannick Noah embraces Alexander Zverev.")
    assert "的别人" in says("Team World's Learner Tien returns another Zverev smash.")


@pytest.mark.parametrize("word, hit", [
    ("crowd", True), ("crowds", True), ("fan", True), ("fans", True),
    ("spectator", True), ("spectators", True),
    ("fantastic", False), ("crowded", False),             # 整词：不是这几个词就不拦
])
def test_看台那几个词_crowd_fan_spectator_单复数都拦(word, hit):
    """复审 D3(a) 收进 `NOT_IN_MATCH` 的看台名词：画面主体是一群人，最大那张脸不一定是他。
    bench／support 由拉沃尔杯那 8 张真图注钉着；这几个词没有真图注，在这儿逐个钉住（删掉哪个哪格红）。"""
    ctx = cu.match_context(_laver_spec(), times=lambda _id: cu.parse_dc_feed(ZT_FEED))
    c = cu.Candidate("ap", "https://assets.apnews.com/w.jpg",
                     caption=f"Alexander Zverev of Team Europe plays in front of the {word} against Learner "
                             "Tien of Team World at the Laver Cup in London on Sunday, Sept. 27, 2026.")
    probs = cu.metadata_problems(c, ctx)
    if hit:
        assert len(probs) == 1 and f"说明里有「{word}」" in probs[0], probs
    else:
        assert probs == [], probs

def test_列出来的开赛时间只当下界_团体赛不写对手的放宽不给():
    """复审 nit 1：`_start_time_source.reported_utc`（sofascore 那种列出来的开赛时间）≤ 真开赛——
    「上传晚于开赛」拿它比是**更松**；团体赛「不写对手」的放宽要真开赛时刻算出来的日期，不给。"""
    zt = _laver_spec()
    zt["_match"] = {}
    zt["_start_time_source"] = {"url": "https://www.sofascore.com/x", "reported_utc": "2026-09-27T13:00:00Z"}
    ctx = cu.match_context(zt, times=lambda _id: pytest.fail("记着开赛时刻，不问 flashscore"))
    assert not ctx.problems and ctx.start_lower_bound and ctx.match_dates == {date(2026, 9, 27)}
    no_opp = cu.Candidate("event-site", "https://lavercup.com/wp-content/uploads/2026/09/z.jpg",
                          event_owned=True, meta_utc="2026-09-27T15:42:44",
                          caption="Alexander Zverev adds another Laver Cup title to his resume.")
    assert any("对手" in p for p in cu.metadata_problems(no_opp, ctx))
    # 对照组：flashscore 给的是真开赛时刻——放宽照给
    real = cu.match_context(_laver_spec(), times=lambda _id: cu.parse_dc_feed(ZT_FEED))
    assert not real.start_lower_bound and cu.metadata_problems(no_opp, real) == []


def _exif_photo(taken: str | None, offset: str | None = None) -> bytes:
    from PIL import Image  # noqa: PLC0415

    img = Image.new("RGB", (2560, 1600), (40, 60, 40))
    exif = Image.Exif()
    if taken:
        sub = exif.get_ifd(0x8769)
        sub[0x9003] = taken
        if offset:
            sub[0x9011] = offset
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90, exif=exif)
    return buf.getvalue()


def _zverev_checker(img, expected, target=None):
    return {"status": "ok",
            "identity": {"verdict": "match", "name": "兹维列夫", "similarity": {"兹维列夫": 0.55},
                         "face": [1180, 420, 1380, 660], "face_px": 240},
            "eyes": {"verdict": "open", "ear": 0.24}}


@pytest.mark.parametrize("taken, offset, bad", [
    ("2026:09:26 20:00:00", None, "2026-09-26"),      # 前一天的图（没写时差：当地钟点）
    ("2026:09:27 14:05:00", None, None),               # 这一天
    ("2026:09:26 23:30:00", "+00:00", None),           # UTC 23:30＝伦敦 9/27 00:30（夏令时）
    ("2026:09:27 00:30:00", "+03:00", "2026-09-26"),   # 换到伦敦是 9/26 22:30
    (None, None, None),                                # 没有 EXIF：不判
    ("0000:00:00 00:00:00", None, None),               # 全零：当没有
])
def test_照片EXIF拍摄日期不是这场的当地日子就不换(taken, offset, bad):
    """复审 D3(c)：说明没写日期时只能拿上传时刻判——而前一天的图第二天才批量传上来是真事
    （拉沃尔杯官网第二天的图 9/27 14:14Z 才上传，比第三天那场 13:25Z 开赛还晚，上传那道闸放行）。
    照片自己记着按快门的那一刻：有 `DateTimeOriginal` 就必须落在这场的当地日子（±0 天）。"""
    ctx = cu.match_context(_laver_spec(), times=lambda _id: cu.parse_dc_feed(ZT_FEED))
    got = cu.image_verdict(_exif_photo(taken, offset), _laver_spec(), ctx, checker=_zverev_checker)
    exif = [p for p in got["problems"] if "EXIF" in p]
    if bad:
        assert exif and bad in exif[0], got["problems"]
    else:
        assert exif == [], got["problems"]
    if taken and taken[0] != "0":
        assert got["evidence"]["exif_taken"].startswith(taken), got["evidence"]


def test_前一天的图晚传上来_上传那道闸放行_EXIF拦住():
    """端到端：图注不写日期、上传时刻晚于这场开赛（`_upload_problems` 过了），团体赛放宽也给了——
    只有 EXIF 说它是前一天拍的。对照组：同一张换成当天的 EXIF 就选中。"""
    ctx = cu.match_context(_laver_spec(), times=lambda _id: cu.parse_dc_feed(ZT_FEED))
    late = cu.Candidate("event-site", "https://lavercup.com/wp-content/uploads/2026/09/late.jpg",
                        event_owned=True, meta_utc="2026-09-27T14:14:41",
                        caption="Alexander Zverev pumps his fist.")
    assert cu.metadata_problems(late, ctx) == []
    target = cu.Target("zverev-tien-laver-cup-2026", _laver_spec(), datetime.now(timezone.utc), Path("x"))
    chosen, rows = cu.evaluate(target, ctx, [late], checker=_zverev_checker,
                               fetch=lambda _u: _exif_photo("2026:09:26 19:40:00"))
    assert chosen is None and any("EXIF" in p for p in rows[0]["problems"]), rows
    assert rows[0].get("tried"), "EXIF 日期不对是图本身的毛病，下一班不用再下"
    chosen, _rows = cu.evaluate(target, ctx, [late], checker=_zverev_checker,
                                fetch=lambda _u: _exif_photo("2026:09:27 14:02:00"))
    assert chosen is not None



def test_只有开赛时刻时_夜场过了午夜拍的图被EXIF拦下还记进tried_知道结束时刻就不拦():
    """`exif_date_problem`／`image_verdict` docstring 那句：只记了开赛时刻（`_match.start_utc`）时
    `match_dates` 只有开赛那一天——当地 22:30 开打的夜场，过了午夜拍的图 EXIF 是第二天，拦下、而且
    记进 `tried`（安全方向：漏换一张，不换成别的比赛日）。知道结束时刻（flashscore 的 DD）就两天都认。"""
    cap = ("Alexander Zverev of Team Europe reacts against Learner Tien of Team World at the Laver Cup "
           "in London on Sunday, Sept. 27, 2026.")
    cand = cu.Candidate("ap", "https://assets.apnews.com/night.jpg", caption=cap)
    night = _exif_photo("2026:09:28 00:20:00")               # 当地（伦敦）9/28 00:20
    spec = _laver_spec()
    spec["_match"] = {"start_utc": "2026-09-27T21:30:00Z"}   # 伦敦 22:30 开打
    ctx = cu.match_context(spec, times=lambda _id: pytest.fail("记着开赛时刻，不问 flashscore"))
    assert ctx.match_dates == {date(2026, 9, 27)} and ctx.end_utc is None, ctx
    assert cu.metadata_problems(cand, ctx) == []
    target = cu.Target("zverev-tien-laver-cup-2026", spec, datetime.now(timezone.utc), Path("x"))
    chosen, rows = cu.evaluate(target, ctx, [cand], checker=_zverev_checker, fetch=lambda _u: night)
    assert chosen is None and any("EXIF" in p and "2026-09-28" in p for p in rows[0]["problems"]), rows
    assert rows[0].get("tried"), "EXIF 日期对不上算图本身的毛病——记进 tried，下一班不再下"
    # 对照组：flashscore 给了结束时刻（DD＝伦敦 9/28 00:40），两天都是这一场
    both = _laver_spec()
    ctx2 = cu.match_context(both, times=lambda _id: cu.parse_dc_feed("DC÷1790544600¬DD÷1790552400¬~"))
    assert ctx2.match_dates == {date(2026, 9, 27), date(2026, 9, 28)}, ctx2.match_dates
    chosen, _rows = cu.evaluate(cu.Target("zverev-tien-laver-cup-2026", both, datetime.now(timezone.utc),
                                          Path("x")), ctx2, [cand], checker=_zverev_checker,
                                fetch=lambda _u: night)
    assert chosen is not None, _rows

def test_团体赛名单自洽_和仓库里拉沃尔杯的spec对得上():
    """名单是从官网抄的，抄错一个姓，放宽就放错人。拿仓库里自己的拉沃尔杯 spec 对一遍：
    每条单打 spec 的两个人都在名单上，每一场的每个姓在名单上恰好对得上一个人。"""
    data = json.loads((ROOT / cu.ROSTERS).read_text(encoding="utf-8"))
    roster = data["Laver Cup"]["2026"]
    people = cu.roster_people(roster)
    assert len(people) == len(set(people)) == 18, people       # 12 名球员 ＋ 2 替补 ＋ 4 队长
    lasts = [cu._last(p) for p in people]
    for m in roster["matches"]:
        for side in m["sides"]:
            for name in side:
                assert lasts.count(cu._last(name)) == 1, (m, name)
    nos = [m["no"] for m in roster["matches"]]
    assert nos == sorted(nos) == list(range(1, len(nos) + 1)), nos
    days = {"首日": "2026-09-25", "第二天": "2026-09-26", "第三天": "2026-09-27"}
    checked = 0
    for path in sorted((ROOT / "specs" / "reels").glob("*laver-cup-2026*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        names = [m.get("name_en") for m in (spec.get("cover") or {}).get("matchup") or []]
        day = next((d for k, d in days.items() if k in str((spec.get("topbar") or {}).get("line1"))), None)
        if len(names) != 2 or not all(names) or not day:
            continue
        # 单打是「名 姓」，双打是「C. Ruud / A. Zverev」——每一边拆成姓的集合
        want = [frozenset(cu._last(x) for x in n.split("/")) for n in names]
        for side in want:
            assert side <= set(lasts), (path.name, side)
        hit = [m for m in roster["matches"]
               if {frozenset(cu._last(x) for x in side) for side in m["sides"]} == set(want)]
        assert len(hit) == 1 and hit[0]["date"] == day, (path.name, want, day, hit)
        checked += 1
    assert checked >= 9, checked                              # 仓库里 7 条单打 ＋ 3 条双打


# ---------------------------------------------------------------- ⑤ 渲前预检

def _jpeg(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _big_photo() -> bytes:
    from PIL import Image  # noqa: PLC0415

    return _jpeg(Image.new("RGB", (2560, 1600), (40, 60, 40)))


def _ok_checker(img, expected, target=None):
    """认人＋睁眼的替身：脸在 (1180, 420)~(1380, 660)，认出是黄泽林、睁眼。"""
    return {"status": "ok",
            "identity": {"verdict": "match", "name": "黄泽林", "similarity": {"黄泽林": 0.52},
                         "face": [1180, 420, 1380, 660], "face_px": 240},
            "eyes": {"verdict": "open", "ear": 0.24}}


START = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
AP_OK = ("Coleman Wong of Hong Kong reacts after winning a point against Adolfo Daniel Vallejo "
         "during the Hangzhou Open in Hangzhou, China, on Saturday, Sept. 26, 2026. (AP Photo)")


def _wong_spec(**extra) -> dict:
    spec = {"slug": "wong-vallejo-hangzhou-2026-r2",
            "topbar": {"line1": "2026 ATP250 杭州 第二轮"},
            "cover": {"eyebrow": "赛场之上", "layout": "solo", "subject": "黄泽林",
                      "matchup": [{"name": "黄泽林", "name_en": "Coleman Wong"},
                                  {"name": "巴列霍", "name_en": "Adolfo Daniel Vallejo"}],
                      "portrait": {"frame_at": 689.8, "focus": 0.58, "_frame_why": "抽帧"}},
            "_match": {"flashscore_id": "x0TAQY2b"},
            "stats": {"a": {"headshot": "assets/players/headshots/atp-W0BH.png"},
                      "b": {"headshot": "assets/players/headshots/atp-V0DP.png"}}}
    for k, v in extra.items():
        spec[k] = v
    return spec


def _preflight(tmp_path, spec, cands, *, calls=None, slug="wong-vallejo-hangzhou-2026-r2",
               final_gate=lambda spec: None):
    """正式封面闸默认放行（它要 `import build_match_reel` 读一整套素材，测试里用替身；
    「预检和 `--write` 过的是同一道闸」由 `test_渲前预检拦下的那张_write一定写得进去` 钉）。"""
    (tmp_path / "specs" / "reels").mkdir(parents=True, exist_ok=True)
    (tmp_path / "specs" / "reels" / f"{slug}.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def sweeps_for(ctx):
        if calls is not None:
            calls.append(ctx.slug)
        return [("测试渠道", lambda: list(cands))]
    return cu.preflight(tmp_path, slug, NOW, spec=spec, sweeps_for=sweeps_for,
                        times=lambda _id: (START, START + timedelta(hours=2)),
                        fetch=lambda _u: _big_photo(), checker=_ok_checker, final_gate=final_gate)


def test_渲前预检_有一张全过就拦手写的_给出换法(tmp_path):
    got = _preflight(tmp_path, _wong_spec(), [cu.Candidate("ap", "https://assets.apnews.com/x.jpg",
                                                          caption=AP_OK)])
    assert got["found"], "\n".join(got["report"])
    code, last = cu.preflight_exit(got)
    assert code == cu.PREFLIGHT_FOUND == 3 and last.startswith("::error::"), last
    text = "\n".join(got["report"])
    assert '"image": "assets/reel/wong-vallejo-hangzhou-2026-r2-official.jpg"' in text, text
    assert "--preflight --slug wong-vallejo-hangzhou-2026-r2 --write" in text, text
    # 预检写的 `_why` 不许长得像 O4 换过的（不然 reconcile_orphans 会替它补一笔 O4 的账）
    assert got["portrait"]["_why"].startswith(cu.PREFLIGHT_WHY_PREFIX)
    assert not got["portrait"]["_why"].startswith(cu.AUTO_WHY_PREFIX)
    # 自动 spec：只报不拦
    auto = _wong_spec(_production={"status": "ready_for_render"})
    code, last = cu.preflight_exit(_preflight(tmp_path, auto, [cu.Candidate(
        "ap", "https://assets.apnews.com/x.jpg", caption=AP_OK)]))
    assert code == 0 and last.startswith("::warning::"), last


def test_渲前预检_没有能过闸的官方图就不拦(tmp_path):
    """2026-09-26 账号所有者：没有高清大图时抽帧可以直接用——这几种一律不拦。"""
    wrong_day = cu.Candidate("ap", "https://assets.apnews.com/y.jpg",
                             caption=AP_OK.replace("Sept. 26", "Sept. 24").replace("Saturday", "Thursday"))
    for cands in ([], [wrong_day]):
        got = _preflight(tmp_path, _wong_spec(), cands)
        assert not got["found"] and cu.preflight_exit(got) == (0, ""), got["report"]
        assert "不拦" in got["report"][-1], got["report"]

    def blocked():
        raise RuntimeError("Cloudflare 人机挑战")

    (tmp_path / "specs" / "reels").mkdir(parents=True, exist_ok=True)
    spec = _wong_spec()
    got = cu.preflight(tmp_path, "wong-vallejo-hangzhou-2026-r2", NOW, spec=spec,
                       sweeps_for=lambda ctx: [("AP 通讯社", blocked)],
                       times=lambda _id: (START, None), fetch=lambda _u: b"", checker=_ok_checker)
    assert not got["found"] and "结果未知" in got["report"][-1], got["report"]
    # 认领过这一帧、不是抽帧、不是赛场之上：连查都不查
    calls: list = []
    keep = _wong_spec()
    keep["cover"]["portrait"]["_keep_frame_why"] = "账号所有者当面点过就用这一帧"
    image = _wong_spec()
    image["cover"]["portrait"] = {"image": "assets/reel/x.jpg"}
    story = _wong_spec()
    story["cover"]["eyebrow"] = "网球有故事"
    for spec in (keep, image, story):
        got = _preflight(tmp_path, spec, [cu.Candidate("ap", "https://x/y.jpg", caption=AP_OK)],
                         calls=calls)
        assert not got["found"] and cu.preflight_exit(got)[0] == 0
    assert calls == [], calls


def test_渲前预检write_写图改spec_过不了正式封面闸就全部退回(tmp_path):
    got = _preflight(tmp_path, _wong_spec(), [cu.Candidate("ap", "https://assets.apnews.com/x.jpg",
                                                          caption=AP_OK)])
    spec_path = tmp_path / "specs" / "reels" / "wong-vallejo-hangzhou-2026-r2.json"
    before = spec_path.read_text(encoding="utf-8")
    problem = cu.write_preflight(tmp_path, got, final_gate=lambda spec: "封面闸：不许")
    assert problem == "封面闸：不许"
    assert spec_path.read_text(encoding="utf-8") == before
    assert not (tmp_path / got["image_rel"]).exists()
    assert cu.write_preflight(tmp_path, got, final_gate=lambda spec: None) is None
    written = json.loads(spec_path.read_text(encoding="utf-8"))
    assert written["cover"]["portrait"]["image"] == got["image_rel"]
    assert (tmp_path / got["image_rel"]).read_bytes() == got["chosen"]["blob"]
    # 渲前预检写进去的不进 O4 的账：reconcile_orphans 认不出它
    assert cu.reconcile_orphans(tmp_path, NOW)[0] == []


def _sent(tmp_path, slug="wong-vallejo-hangzhou-2026-r2", status="sent") -> None:
    ledger = tmp_path / "data" / "reel_publish_ledger" / f"{slug}.json"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(json.dumps({"slug": slug, "channel": "pushplus", "attempts": [
        {"key": f"pushplus:reel:{slug}:abc", "status": status, "at": "2026-09-26T14:10:00Z"}]}),
        encoding="utf-8")


def _tree(tmp_path) -> dict[str, bytes]:
    return {p.relative_to(tmp_path).as_posix(): p.read_bytes()
            for p in sorted(tmp_path.rglob("*")) if p.is_file() and ".git" not in p.parts}


def test_渲前预检只拦第一次渲染_推过的只报_不试写不改spec(tmp_path, capsys):
    """复审 D2：拦的是**第一次**渲染（发布账本和 pushed.json 都没有）；已经推过的只报——推出去之后
    换图归 O4（它认 `_keep_frame_why`），这里不试写、不改已发的 spec，`--write` 也不写。"""
    slug = "wong-vallejo-hangzhou-2026-r2"
    ap = [cu.Candidate("ap", "https://assets.apnews.com/x.jpg", caption=AP_OK)]
    got = _preflight(tmp_path, _wong_spec(), ap)
    assert got["pushed"] == "" and cu.preflight_exit(got)[0] == cu.PREFLIGHT_FOUND
    assert cu.preflight_budget(tmp_path, slug) == cu.PREFLIGHT_BUDGET_BLOCKING
    # 账本里只有 rejected：没发出去过，照旧是第一次
    _sent(tmp_path, status="rejected")
    assert cu.preflight_exit(_preflight(tmp_path, _wong_spec(), ap))[0] == cu.PREFLIGHT_FOUND
    # 推过了（账本 sent）：只报、不试写
    _sent(tmp_path)
    before = _tree(tmp_path)
    gate_calls: list = []
    got = _preflight(tmp_path, _wong_spec(), ap, final_gate=lambda spec: gate_calls.append(1))
    code, last = cu.preflight_exit(got)
    assert got["found"] and "sent" in got["pushed"], got["pushed"]
    assert code == 0 and last.startswith("::warning::") and "O4" in last, last
    assert gate_calls == [], "推过的不试写（试写会动 assets/reel）"
    assert _tree(tmp_path) == before, "推过的 spec 和素材一个字节都不许动"
    refused = cu.write_preflight(tmp_path, got, final_gate=lambda spec: None)
    assert refused and "已经推过" in refused and _tree(tmp_path) == before, refused
    assert cu.preflight_budget(tmp_path, slug) == cu.PREFLIGHT_BUDGET_REPORT
    assert cu.main(["--preflight-budget", "--slug", slug, "--repo", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == str(cu.PREFLIGHT_BUDGET_REPORT)
    # 账本读不了：状态不明按推过算（只报）
    (tmp_path / "data" / "reel_publish_ledger" / f"{slug}.json").write_text("{坏", encoding="utf-8")
    assert "状态不明" in cu.already_pushed(tmp_path, slug)
    # 推过的另一处凭据：git 跟踪着的 output/<日期>/reel/<slug>/pushed.json
    (tmp_path / "data" / "reel_publish_ledger" / f"{slug}.json").unlink()
    assert cu.already_pushed(tmp_path, slug) == ""
    marker = tmp_path / "output" / "2026-09-26" / "reel" / slug / "pushed.json"
    marker.parent.mkdir(parents=True)
    marker.write_text("{}", encoding="utf-8")
    for cmd in (["init", "-q"], ["add", "output"]):
        subprocess.run(["git", "-C", str(tmp_path), *cmd], check=True, capture_output=True)
    assert cu.already_pushed(tmp_path, slug) == f"仓库里有 output/2026-09-26/reel/{slug}/pushed.json"
    assert cu.preflight_exit(_preflight(tmp_path, _wong_spec(), ap))[0] == 0
    # 自动 spec 也只报：秒数给只报那一档
    auto_slug = "wong-auto"
    (tmp_path / "specs" / "reels" / f"{auto_slug}.json").write_text(json.dumps(
        _wong_spec(_production={"status": "ready_for_render"})), encoding="utf-8")
    assert cu.preflight_budget(tmp_path, auto_slug) == cu.PREFLIGHT_BUDGET_REPORT



#: 发布账本的第一笔（`data/reel_publish_ledger/fils-tiafoe-cincinnati-2026-final.json`，420d663cf）。
LEDGER_START = "2026-08-24"


def _tracked(*patterns: str) -> list[str]:
    return subprocess.run(["git", "-C", str(ROOT), "ls-files", "--", *patterns],
                          capture_output=True, text=True, check=True).stdout.split()


def test_发布账本之前推过的抽帧封面_登记表只许减_每条都查得到(tmp_path):
    """复审：`already_pushed` 只认发布账本和 `pushed.json`，81 条抽帧封面「赛场之上」里漏了 22 条——
    2026-08-02~08-08 合进 main 的，那时账本还没有（首笔 2026-08-24）、`pushed.json` 只有 `push.auto`
    那条路写。漏掉的重渲时会被当成第一次渲染拦下、`--write` 还会改已发的 spec。冻进
    `data/legacy_prepush_reels.json`，**只许减不许加**，表自带自检。"""
    legacy = cu.prepush_legacy(ROOT)
    assert legacy, "登记表读不到——路径或键名写错了，整条判据会静静失效"
    raw = json.loads((ROOT / cu.PREPUSH_LEGACY).read_text(encoding="utf-8"))
    assert raw.get("_why") and raw["reels"] == sorted(set(raw["reels"])), "要写 _why；排好序、不重复"
    assert len(legacy) <= 22, "只许减不许加——账本之后推的片子由发布账本认，不往这儿加"
    renders: dict[str, list[str]] = {}
    for path in _tracked("output/*/reel/*/render.json"):
        parts = path.split("/")
        renders.setdefault(parts[3], []).append(parts[1])
    assert len(renders) > 100, f"只找到 {len(renders)} 条 render.json——git ls-files 是不是没看到 output/"
    pushed = {p.split("/")[3] for p in _tracked("output/*/reel/*/pushed.json")}
    for slug in sorted(legacy):
        spec_path = ROOT / cu.SPEC_DIR / f"{slug}.json"
        assert spec_path.is_file(), f"{slug}：specs/reels 里没有这条"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        assert cu.is_frame_cover(spec) and spec["cover"].get("eyebrow") == "赛场之上", \
            f"{slug}：不再是抽帧封面「赛场之上」了——预检不看它，从登记表删掉"
        assert not (ROOT / cu.PUBLISH_LEDGER / f"{slug}.json").exists(), \
            f"{slug}：发布账本里有了——账本认得出，从登记表删掉"
        assert slug not in pushed, f"{slug}：有了 pushed.json——从登记表删掉"
        assert min(renders.get(slug) or ["9999"]) < LEDGER_START, \
            f"{slug}：没有账本之前就合进 main 的 render.json——登记的只能是账本之前推的"
    # 反过来：账本之前就合进 main 的抽帧封面「赛场之上」，already_pushed 一条都不许漏
    checked = 0
    for spec_path in sorted((ROOT / cu.SPEC_DIR).glob("*.json")):
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if not (isinstance(spec, dict) and cu.is_frame_cover(spec)
                and (spec.get("cover") or {}).get("eyebrow") == "赛场之上"):
            continue
        if min(renders.get(spec_path.stem) or ["9999"]) >= LEDGER_START:
            continue
        checked += 1
        assert cu.already_pushed(ROOT, spec_path.stem), \
            f"{spec_path.stem}：账本之前就合进 main 的抽帧封面，already_pushed 认不出"
    assert checked >= 60, f"只校了 {checked} 条（2026-09-28 是 72）——扫描面没了，这条会变成恒真的绿灯"
    # 登记表本身：登记过的认、读不了的按推过算（只报不拦）
    (tmp_path / "data").mkdir()
    assert cu.already_pushed(tmp_path, "chwalinska-gibson") == ""
    (tmp_path / cu.PREPUSH_LEGACY).write_text(json.dumps({"reels": ["chwalinska-gibson"]}), encoding="utf-8")
    assert "登记过" in cu.already_pushed(tmp_path, "chwalinska-gibson")
    assert cu.already_pushed(tmp_path, "someone-else") == ""
    (tmp_path / cu.PREPUSH_LEGACY).write_text("{坏", encoding="utf-8")
    assert "状态不明" in cu.already_pushed(tmp_path, "someone-else")

def test_渲前预检拦下的那张_write一定写得进去_同一道正式封面闸(tmp_path):
    """复审 nit 2：预检原来只过机器闸就报「找到了」（退出码 3），`--write` 再过正式封面闸——两道判得
    不一样时，手写 spec 被拦住、照着报告换又换不上。现在预检挑图时就拿 `--write` 那个函数试一遍
    （`_formal_gate_on`，同一份输入、试完退回）：退出码 3 只在 `--write` 会成功时出现。"""
    slug = "wong-vallejo-hangzhou-2026-r2"
    a = cu.Candidate("ap", "https://assets.apnews.com/a.jpg", caption=AP_OK)
    b = cu.Candidate("ap", "https://assets.apnews.com/b.png", caption=AP_OK)
    seen: list[str] = []

    def gate(spec):
        art = spec["cover"]["portrait"]
        assert Path(art["image"]).is_file(), "正式闸看到的得是真写下去的那张图（cwd＝仓库）"
        seen.append(art["image"])
        return "封面闸：a 不许" if "/a.jpg" in art["_why"] else None

    got = _preflight(tmp_path, _wong_spec(), [a, b], final_gate=gate)
    assert got["found"] and got["chosen"]["candidate"] is b, got["report"]
    assert seen == [f"assets/reel/{slug}-official.jpg", f"assets/reel/{slug}-official.png"], seen
    assert "正式封面闸没过" in "\n".join(got["report"]), got["report"]
    assert not (tmp_path / "assets" / "reel" / f"{slug}-official.png").exists(), "试完要退回"
    assert cu.preflight_exit(got)[0] == cu.PREFLIGHT_FOUND
    assert cu.write_preflight(tmp_path, got, final_gate=gate) is None
    spec = json.loads((tmp_path / "specs" / "reels" / f"{slug}.json").read_text(encoding="utf-8"))
    assert spec["cover"]["portrait"]["image"] == f"assets/reel/{slug}-official.png"
    # 正式闸一张都不放：不拦（机器闸过了也不算找到），spec 和素材原样
    spec_path = tmp_path / "specs" / "reels" / f"{slug}.json"
    spec_path.write_text(json.dumps(_wong_spec(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (tmp_path / "assets" / "reel" / f"{slug}-official.png").unlink()
    before = _tree(tmp_path)
    got = _preflight(tmp_path, _wong_spec(), [a, b], final_gate=lambda spec: "封面闸：都不许")
    assert not got["found"] and cu.preflight_exit(got) == (0, ""), got["report"]
    assert _tree(tmp_path) == before


def _preflight_step() -> dict:
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "match-reel.yml").read_text(encoding="utf-8"))
    steps = wf["jobs"]["reel"]["steps"]
    names = [s.get("name") or "" for s in steps]
    i = names.index("抽帧封面先查官方图（有能过机器闸的就不许发抽帧）")
    return {"steps": steps, "names": names, "i": i, "step": steps[i]}


def test_渲前预检接在match_reel的render那一步_排在人脸模型和dry_run之后():
    got = _preflight_step()
    step, names, i = got["step"], got["names"], got["i"]
    assert step["if"].strip() == "github.event.inputs.mode == 'render'", step["if"]
    assert "tools/cover_upgrade.py --preflight" in step["run"]
    fetch = next(j for j, s in enumerate(got["steps"]) if "face_checks.py fetch" in str(s.get("run")))
    dry = names.index("dry-run — 先把 spec 的形状错拦在编码之前")
    apt = next(j for j, n in enumerate(names) if n.startswith("缓存 apt 包"))
    assert fetch < dry < i < apt, (fetch, dry, i, apt)
    # 只看命令行、不看注释（注释里正写着为什么不 tee——「判据被自己的注释误伤」那一类）
    code = "\n".join(ln for ln in step["run"].splitlines() if not ln.lstrip().startswith("#"))
    assert "render-findings" not in code, "换图不归模型管：别把预检的话喂给判据回喂"


@pytest.mark.parametrize("rc, exit_code, says, budget", [
    (0, 0, "", "100"), (3, 1, "", "100"), (124, 0, "超时（100 秒）", "100"),
    (124, 0, "超时（60 秒）", "60"), (124, 0, "超时（60 秒）", "炸了"),
    (1, 0, "自己出错", "100"), (2, 0, "自己出错", "100")])
def test_渲前预检那一步只在找到了才红(tmp_path, rc, exit_code, says, budget):
    """真跑那段 bash：退出码 3（找到了、手写、第一次渲染）才红；超时、工具炸了一律只告警不拦。
    秒数是 `--preflight-budget` 印的，印不出数就按 60（`budget="炸了"`）。"""
    script = _preflight_step()["step"]["run"].replace("${{ github.event.inputs.slug }}", "x")
    stub = tmp_path / "bin"
    stub.mkdir()
    printed = f"echo {budget}; exit 0" if budget.isdigit() else "echo Traceback >&2; exit 1"
    (stub / "python").write_text(
        f'#!/bin/sh\ncase "$*" in *--preflight-budget*) {printed} ;; esac\n'
        f'echo "args: $*"\nexit {rc}\n', encoding="utf-8")
    (stub / "python").chmod(0o755)
    env = {**os.environ, "PATH": f"{stub}:{os.environ['PATH']}",
           "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md")}
    run = subprocess.run(["bash", "-e", "-c", script], capture_output=True, text=True, env=env,
                         cwd=tmp_path)
    assert run.returncode == exit_code, (run.stdout, run.stderr)
    assert "args: tools/cover_upgrade.py --preflight --slug x" in run.stdout, run.stdout
    if says:
        assert says in run.stdout and "::warning::" in run.stdout, run.stdout


def test_渲前预检那一步的秒数装得进步骤超时_job留足三分钟余量():
    """复审 nit 3：match-reel 各步骤声明的最坏预算之和原来 62、job 63——只剩 1 分钟。这一步收到
    2 分钟：会拦的 100 秒、只报的（自动 spec、已经推过的）60 秒，外加 python 起进程的余量。"""
    import yaml  # noqa: PLC0415

    got = _preflight_step()
    limit = int(got["step"]["timeout-minutes"]) * 60
    assert cu.PREFLIGHT_BUDGET_REPORT <= 60, cu.PREFLIGHT_BUDGET_REPORT
    assert cu.PREFLIGHT_BUDGET_BLOCKING + 15 <= limit, (cu.PREFLIGHT_BUDGET_BLOCKING, limit)
    code = "\n".join(ln for ln in got["step"]["run"].splitlines() if not ln.lstrip().startswith("#"))
    assert "--preflight-budget" in code and 'timeout "$LIMIT"' in code, code
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "match-reel.yml").read_text(encoding="utf-8"))
    job = wf["jobs"]["reel"]
    steps = sum(int(s.get("timeout-minutes") or 0) for s in job["steps"])
    assert int(job["timeout-minutes"]) - steps >= 3, (job["timeout-minutes"], steps)


def test_人查的时候_给了赛事名就自动带上登记过的官网(monkeypatch, capsys):
    """原来 `find_cover_photo --event "Laver Cup"` 不给 `--site` 这一档整个不跑（官网域名只登记在
    O4 那边）；合成一份之后人查也认得出。"""
    media = _laver_media()
    asked: list[str] = []

    def fake_json(url, timeout=40):
        asked.append(url)
        return (media if "/media?" in url else [], {"X-WP-TotalPages": "1"})

    monkeypatch.setattr(fcp, "_get_json", fake_json)
    for name in ("sweep_wta", "sweep_ap"):
        monkeypatch.setattr(fcp, name, lambda *a, stats=None, **k: (stats or {}).update(pages_read=1) or [])
    monkeypatch.setattr(fcp, "sweep_wta_articles",
                        lambda *a, **k: {"rows": [], "notes": [], "window": "w", "pages_read": 1})
    monkeypatch.setattr(sys, "argv", ["find_cover_photo.py", "--player", "Zverev", "--event",
                                      "Laver Cup", "--date", "2026-09-27", "--days", "3"])
    assert fcp.main() == 0
    out = capsys.readouterr().out
    assert asked and asked[0].startswith("https://lavercup.com/wp-json/wp/v2/media"), asked
    assert "=== lavercup.com 的 WordPress 媒体库" in out
    ran = out.split("=== 这一趟查了什么")[1].split("没跑")[0]
    assert "赛事官网 WordPress 媒体库" in ran, ran
