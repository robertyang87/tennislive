"""O4 自动换图和渲前预检的渠道、日期、团体赛名单（2026-09-28）。

来路：O4 上线第一班（run 36378419750，apply=false）一张都没换成——

| 目标 | 卡在哪 | 这里的判据 |
|---|---|---|
| 杭州 ATP 三条 | 只查了 AP，而 AP 在 runner 上 403 | 渠道只登记一份（`cover_channels.CHANNELS`），每一档都出一行；AP 的 403 认成 Cloudflare 挑战页、记「没查成」 |
| safiullin-bu | spec 没有 `_match.start_utc`／`flashscore_id` | 开赛时刻按 spec 记下的 `_start_time_source`、再按首推时刻推，并说是哪一个 |
| zverev-tien（拉沃尔杯） | 8 张官网候选全卡在「只写姓」「没写对手」 | 团体赛按名单放宽（真图注录在 `fixtures/cover_upgrade/`） |

外加返工审计：窗口里 11 条第一次推的是抽帧封面——渲前预检（`cover_upgrade.preflight`）
在 match-reel render 那一步查一遍，有一张全过就不许发抽帧（手写拦、自动只报、没有就不拦）。

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
    # 「Team Europe players and captains get around Zverev.」——只写姓、不写对手：两条都放宽
    probs, relaxed = verdict("CB_36487_4jVq5VqG_20260927041747.jpg")
    assert probs == [] and len(relaxed) == 2, (probs, relaxed)
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


def _preflight(tmp_path, spec, cands, *, calls=None, slug="wong-vallejo-hangzhou-2026-r2"):
    (tmp_path / "specs" / "reels").mkdir(parents=True, exist_ok=True)
    (tmp_path / "specs" / "reels" / f"{slug}.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def sweeps_for(ctx):
        if calls is not None:
            calls.append(ctx.slug)
        return [("测试渠道", lambda: list(cands))]
    return cu.preflight(tmp_path, slug, NOW, spec=spec, sweeps_for=sweeps_for,
                        times=lambda _id: (START, START + timedelta(hours=2)),
                        fetch=lambda _u: _big_photo(), checker=_ok_checker)


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


def test_渲前预检豁免表只许减不许加_每条都还是已发的抽帧封面():
    """定规矩那天（2026-09-28）对全库抽帧封面在沙箱跑过一遍，命中 0 条——表是空的。
    以后要往里加，说明那一条推出去之后渲前预检才有了能换的官方图：那是 O4 的活，不是豁免。"""
    assert len(cu.PREFLIGHT_LEGACY) <= 0, "只许减不许加（定规矩那天 0 条）"
    for slug in sorted(cu.PREFLIGHT_LEGACY):
        spec = json.loads((ROOT / "specs" / "reels" / f"{slug}.json").read_text(encoding="utf-8"))
        assert cu.is_frame_cover(spec), f"{slug} 已经不是抽帧封面，从豁免表删掉"
        assert cu.first_sent(ROOT, slug), f"{slug} 没推过，不是存量"


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


@pytest.mark.parametrize("rc, exit_code, says", [
    (0, 0, ""), (3, 1, ""), (124, 0, "超时"), (1, 0, "自己出错"), (2, 0, "自己出错")])
def test_渲前预检那一步只在找到了才红(tmp_path, rc, exit_code, says):
    """真跑那段 bash：退出码 3（找到了、手写）才红；超时、工具炸了一律只告警不拦。"""
    script = _preflight_step()["step"]["run"].replace("${{ github.event.inputs.slug }}", "x")
    stub = tmp_path / "bin"
    stub.mkdir()
    (stub / "python").write_text(f"#!/bin/sh\nexit {rc}\n", encoding="utf-8")
    (stub / "python").chmod(0o755)
    env = {**os.environ, "PATH": f"{stub}:{os.environ['PATH']}",
           "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md")}
    run = subprocess.run(["bash", "-e", "-c", script], capture_output=True, text=True, env=env,
                         cwd=tmp_path)
    assert run.returncode == exit_code, (run.stdout, run.stderr)
    if says:
        assert says in run.stdout and "::warning::" in run.stdout, run.stdout


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
