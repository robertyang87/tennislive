"""ATP Media／WTA 照片接口两档、EXIF 绑场次、发布限制、两人同框、预裁抽帧、自动链封面那一步（2026-09-28）。

来路（`tools/official_photo_apis.py` 模块 docstring 那张表）：17 条「赛场之上」里 10 条首推是抽帧，
**其中 6 条在首推之前**，主角对、铺满不放大的官方原图就已经在这两个接口里了。

全部走录下来的数据（`fixtures/official_photo_apis/`：两个接口的条目、候选原图的头、真模型认人结果），
**测试里不联网**（`conftest._no_official_photo_api_network`）。
"""
from __future__ import annotations

import io
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import cover_channels as cch  # noqa: E402
import cover_upgrade as cu  # noqa: E402
import official_photo_apis as apis  # noqa: E402
import official_photo_replay as replay  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "official_photo_apis"
HEADS = FIX / "heads"
UTC = timezone.utc


def _u(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _head(name: str) -> bytes:
    return next(HEADS.glob(f"{name}*.jpghead")).read_bytes()


# ---------------------------------------------------------------- ① 读原图的头

def test_原图前缀里的EXIF和IPTC_真字节读得出():
    """Range 取回来的是文件的**前缀**——录下来的是真原图到 SOS 之前那一截。"""
    med = apis.parse_head(_head("atp-4582136"))
    assert med["taken"] == "2026:09:26 19:35:22" and med["offset"] == "", med   # 杭州：没写时差
    assert apis.parse_head(_head("atp-4582166"))["taken"] == "", "Medvedev-020 没有 EXIF"
    afp = apis.parse_head(_head("wta-4578951"))
    assert afp["taken"] == "2026:09:19 16:49:24" and afp["offset"] == "-08:00", afp
    assert afp["caption"].startswith("US Iva Jovic returns to US Peyton Stearns"), afp
    assert "AFP" in afp["credit"] and afp["instructions"] == "Not Released (NR)", afp
    fern = apis.parse_head(_head("wta-4582352"))
    assert fern["taken"] == "2026:09:27 17:10:41" and fern["offset"] == "+08:00", fern
    getty = apis.parse_head(_head("getty-2296808078"))
    assert getty["caption"].endswith("/ China OUT"), getty
    # 截断的、不是 JPEG 的：不抛，全是空串
    assert apis.parse_head(_head("atp-4582136")[:3000])["taken"] == ""
    assert apis.parse_head(b"<html>403</html>")["taken"] == ""


def test_录下来的头和解析结果是同一个函数读的():
    """`heads_parsed.json`（回放用）是 `parse_head` 读真头读出来的——拿录了原始字节的几张对一遍。"""
    parsed = replay.load_heads()
    for f in HEADS.glob("*-4*.jpghead"):
        iid = int(f.name.split("-")[1])
        rec = next((v for v in parsed.values() if v["item_id"] == iid), None)
        assert rec is not None, f.name
        got = apis.parse_head(f.read_bytes())
        for key in ("taken", "offset", "caption", "instructions", "credit"):
            assert got[key] == rec[key], (f.name, key)


# ---------------------------------------------------------------- ② 发布限制

@pytest.mark.parametrize("text, hit", [
    # Getty 上 AFP 的真图注（2026-09-28 录的）
    ("… Hangzhou, in China's eastern Zhejiang province on September 27, 2026. (Photo by AFP via "
     "Getty Images) / China OUT", "China OUT"),
    ("… in Trondheim on September 18, 2026. (Photo by Ole Martin Wold / NTB / AFP via Getty Images) "
     "/ Norway OUT", "Norway OUT"),
    ("REUTERS/Tingshu Wang CHINA OUT. NO COMMERCIAL OR EDITORIAL SALES IN CHINA", "CHINA OUT"),
    ("Editorial use only. NO USE IN CHINA", "NO USE IN CHINA"),
    # 不许误伤：比赛图注里的 out、全名大写、编辑用途
    ("Coleman Wong of Hong Kong reacts after winning a point against Adolfo Daniel Vallejo during the "
     "Hangzhou Open in Hangzhou, China, on Saturday, Sept. 26, 2026. (AP Photo)", ""),
    ("Alexander Zverev figures out a way past Learner Tien. (Photo by Julian Finney/Getty Images for "
     "Laver Cup)", ""),
    ("Editorial use only.", ""),
    ("Not Released (NR)", ""),
    ("2026 Hangzhou Medvedev", ""),
])
def test_带地区发布限制的一律认出来(text, hit):
    got = apis.restriction(text)
    assert bool(got) == bool(hit) and hit in got, got


def test_任何渠道的候选_说明或原图里带ChinaOUT都不换():
    """点名闸（说明那一层）和 `image_verdict`（原图里嵌的 IPTC 那一层）各拦一次——AP、官网、接口一视同仁。"""
    ctx = _ctx_rublev()
    cap = ("Russia's Andrey Rublev hits a return to France's Hugo Gaston during their men's singles "
           "quarter-final match at the Hangzhou Open tennis tournament in Hangzhou, in China's eastern "
           "Zhejiang province on September 27, 2026. (Photo by AFP via Getty Images)")
    clean = cu.Candidate("ap", "https://x/a.jpg", caption=cap)
    assert cu.metadata_problems(clean, ctx) == [], cu.metadata_problems(clean, ctx)
    dirty = cu.Candidate("ap", "https://x/a.jpg", caption=cap + " / China OUT")
    assert any("China OUT" in p for p in cu.metadata_problems(dirty, ctx))
    # 列表页上干净、原图里嵌着限制（Getty 那张 612 预览的真 APP 段拼到一张大图上）
    blob = _splice(_head("getty-2296808078"), _plain_jpeg(5000, 3300))
    got = cu.image_verdict(blob, _spec_rublev(), ctx, checker=_checker("卢布列夫"))
    assert any("原图嵌的说明里" in p and "China OUT" in p for p in got["problems"]), got["problems"]
    # 对照组：同一张图不嵌那段说明
    got = cu.image_verdict(_plain_jpeg(5000, 3300), _spec_rublev(), ctx, checker=_checker("卢布列夫"))
    assert not any("China OUT" in p for p in got["problems"]), got["problems"]


# ---------------------------------------------------------------- ③ EXIF 绑场次

R2 = dict(tz="Asia/Shanghai", start=_u("2026-09-26T11:35:00Z"), end=_u("2026-09-26T13:20:51Z"))


@pytest.mark.parametrize("taken, offset, extra, ok, says", [
    ("2026:09:26 19:35:22", "", {}, True, "落在这场的窗口"),                   # Medvedev-012
    ("2026:09:26 21:21:41", "", {}, True, "落在这场的窗口"),                   # 握手：终场后 50 秒
    ("2026:09:26 19:28:00", "", {}, False, "不在这场的窗口"),                  # 开赛前 7 分钟：热身
    ("2026:09:26 21:40:00", "", {}, False, "不在这场的窗口"),                  # 终场后 19 分钟
    ("2026:09:26 21:40:00", "", {"final": True}, True, "决赛"),                # 决赛：颁奖算
    ("2026:09:27 21:25:40", "", {}, False, "不在这场的窗口"),                  # 第二天那场（QF）
    ("", "", {}, False, "没有 EXIF"),
    ("2026:09:26 19:35:22", "-08:00", {}, False, "时差"),                      # 钟不可信
    ("2026:09:26 19:35:22", "+08:00", {}, True, "落在"),                       # 写了、和当地一样
    ("2026:09:26 19:35:22", "", {"publish": _u("2026-09-26T11:00:00Z")}, False, "比接口发布"),
    ("2026:09:26 19:35:22", "", {"start_lower_bound": True}, False, "下界"),
    ("2026:09:26 20:20:00", "", {"end": None}, True, "开赛后 50 分钟"),
    ("2026:09:26 20:30:00", "", {"end": None}, False, "开赛后 50 分钟"),
])
def test_EXIF拍摄时刻按赛事当地钟点落在窗口里才算这一场(taken, offset, extra, ok, says):
    kw = {**R2, **extra}
    got, why, _t = apis.window_verdict(taken, offset, **kw)
    assert got is ok and says in why, why


def test_真接口数据_梅德韦杰夫第二轮_绑得上的就是那几张():
    """录下来的 ATP Media 条目重新分页：只有杭州 R2 那几张绑上；握手照点名了鲁瓦耶、Medvedev-020
    没 EXIF、第二天 QF 那三张拍摄时刻不在窗口——都不算。翻页翻到开赛前两小时就停。"""
    items = replay.load_items("atp_media_items.json.gz")
    asked: list[str] = []
    fetch = replay.pager(items, _u("2026-09-28T00:00:00Z"))
    heads = replay.load_heads()
    got = apis.sweep_atp_media(
        full_name="Daniil Medvedev", surname="Medvedev", player_id="MM58", event="Hangzhou",
        year="2026", **R2, final=False,
        fetch=lambda u: asked.append(u) or fetch(u),
        head=lambda u: replay.synth_head(heads.get(u)))
    by = {r["name"] + "#" + r["item_id"]: r for r in got["rows"]}
    bound = sorted(k for k, r in by.items() if r["bound"] and not r["others"])
    assert bound == ["Daniil-Medvedev-012.jpg#4582136", "Daniil-Medvedev-014.jpg#4582138",
                     "Daniil-Medvedev-014.jpg#4582167"], bound
    hand = by["Daniil-Medvedev-026.jpg#4582168"]
    assert hand["bound"] and hand["others"] == ["royer"], hand      # 时刻对、是握手照
    assert "没有 EXIF" in by["Daniil-Medvedev-020.jpg#4582166"]["bind_why"]
    qf = [r for r in got["rows"] if r["item_id"] in ("4582615", "4582616", "4582617")]
    assert len(qf) == 3 and not any(r["bound"] for r in qf), qf
    assert got["pages_read"] == len(asked) == 1, asked              # 一页就翻到开赛前两小时
    # 鲁瓦耶自己的图（标题只有 Royer）不是梅德韦杰夫的候选
    assert not any("Royer" in r["name"] for r in got["rows"]), got["rows"]


def test_接口翻不到的一档记没查成_翻满没翻完要说出来():
    def boom(_url):
        raise ConnectionError("reset")
    got = apis.sweep_wta_photos(full_name="Iva Jovic", surname="Jovic", player_id="332285",
                                event="Guadalajara", year="2026", tz="America/Mexico_City",
                                start=_u("2026-09-19T23:05:00Z"), end=None, fetch=boom)
    assert got["pages_read"] == 0 and "ConnectionError" in got["notes"][0], got
    res = cch._sweep_api("wta-photos", "WTA 照片接口", lambda **kw: got, cch.Query(player="Jovic"))
    assert res.status == "blocked" and "没查成" in cch.status_line(res)
    # 每一页都比 until 新：翻满 MAX_PAGES 停下、报「没翻完」
    fresh = [{"id": i, "title": "x", "publishFrom": 1_900_000_000_000, "imageUrl": f"https://x/{i}.jpg"}
             for i in range(3)]
    items, stats = apis.pages(apis.WTA_PHOTO_API, _u("2026-09-01T00:00:00Z"),
                              fetch=lambda u: {"content": fresh}, max_pages=4)
    assert stats["truncated"] and stats["pages_read"] == 4 and len(items) == 12, stats


def test_单元测试里这两个接口不联网():
    with pytest.raises(apis.NetworkOff):
        apis.get_json(apis.page_url(apis.ATP_MEDIA_API, 0))
    with pytest.raises(apis.NetworkOff):
        apis.get_head("https://resources.prod.atpmedia.pulselive.com/x.jpg")


# ---------------------------------------------------------------- ④ 回放：实测那几场

def _replays() -> dict[str, tuple]:
    out = {}
    for m in replay.MATCHES:
        at, first = replay.first_pick(m)
        when, got = replay.decision(m, at)
        key = m.slug + ("#spec" if not m.inject_times else "")
        out[key] = (m, at, when, got or first)
    return out


@pytest.fixture(scope="module")
def replays():
    return _replays()


EXPECTED = {
    # slug → (第一次有能过闸的, 那时会挑的文件名)；None＝一直没有（抽帧照发）
    "bu-majchrzak-hangzhou-2026-r2": ("2026-09-26T11:38:32Z", "Yunchaokete-Bu-012.jpg"),
    "medvedev-royer-hangzhou-2026-r2": ("2026-09-26T13:35:35Z", "Daniil-Medvedev-012.jpg"),
    "wong-vallejo-hangzhou-2026-r2": None,          # 010 那张脸隔着拍线、认人 0.24；另外三张没 EXIF／两个人
    "rublev-gaston-hangzhou-2026-qf": ("2026-09-27T13:24:26Z", "Andrey-Rublev-034.jpg"),
    "safiullin-bu-hangzhou-2026-qf#spec": None,     # 开赛只是列出来的时间（下界）：不按 EXIF 绑
    "safiullin-bu-hangzhou-2026-qf": ("2026-09-27T13:24:25Z", "Roman-Safiullin-022.jpg"),
    "medvedev-wong-hangzhou-2026-qf": ("2026-09-27T15:17:44Z", "Daniil-Medvedev-022.jpg"),
    "fernandez-gibson-singapore-2026-final": ("2026-09-27T10:47:46Z", "270927-singles-vc-5.jpg"),
    "jovic-stearns-guadalajara-2026-final": ("2026-09-20T00:44:18Z", "GettyImages-2295584327.jpg"),
    "wang-prozorova-singapore-2026-qf": None,       # 王欣瑜是输家：接口里本场 0 张
}


def test_回放十场_什么时候有_挑哪张_和实测对得上(replays):
    """首推之前就有的 6 场里，接口这两档**机器闸全过**的有 5 场（黄泽林那张隔着拍线认不出，不换）；
    决赛两场挑的都是捧杯（fernandez 他亲口点的「举起奖杯的照片」、jovic 人手挑的也是这张）；
    medvedev-wong 三张里挑正脸清楚的 022，不挑动感模糊的侧脸 019。"""
    assert set(replays) == set(EXPECTED)
    for key, want in EXPECTED.items():
        m, at, when, got = replays[key]
        chosen = got.get("chosen")
        if want is None:
            assert at is None and chosen is None, (key, at)
            continue
        assert at.replace(microsecond=0) == _u(want[0]), (key, at)
        assert chosen is not None and chosen["candidate"].filename == want[1], (
            key, chosen and chosen["candidate"].filename)


def test_回放挑中的每一张_人对_场对_零误选(replays):
    """挑中的认人结果（真模型真原图录下来的）就是封面主角；拍摄时刻（EXIF，或说明写的日期）落在这一场。"""
    faces = replay.load_faces()
    picked = 0
    for key, (m, _at, _when, got) in replays.items():
        chosen = got.get("chosen")
        if chosen is None:
            continue
        picked += 1
        c = chosen["candidate"]
        spec = replay.spec_of(m.slug)
        rep = faces[c.url]["rep"]
        assert rep["identity"]["verdict"] == "match" and rep["identity"]["name"] == spec["cover"]["subject"]
        if any("按照片 EXIF" in r for r in chosen["relaxed"]):
            lo, hi = apis.window(_u(m.start), _u(m.end), final=got["ctx"].final)
            assert lo <= _u(c.taken_utc) <= hi, (key, c.taken_utc, lo, hi)
        else:
            # 说明那条路绑的（jovic 那张 AFP 的钟写的时差不对，EXIF 不绑）：说明写的就是这场的当地日期、
            # 点了对手或写了决赛
            assert cu.caption_dates(c.caption) & got["ctx"].match_dates, c.caption
            assert "Stearns" in c.caption or "final" in c.caption, c.caption
    assert picked == 7, picked


def test_换成对手当主角_录下来的每一张都认不成(replays):
    """「认错人」这一格拿真相似度再判一遍：每张候选换成**对手**当 target，没有一张是 match——
    同一个脸向量、同一个 `identity_verdict`，只换了要认的人。"""
    import face_checks  # noqa: PLC0415

    faces = replay.load_faces()
    for url, rec in faces.items():
        sims = rec["rep"]["identity"]["similarity"]
        if not sims:
            continue
        spec = replay.spec_of(rec["slug"])
        other = next(e["name"] for e in spec["cover"]["matchup"] if e["name"] != spec["cover"]["subject"])
        verdict, _name, _why = face_checks.identity_verdict(
            sims, [], rec["rep"]["identity"]["face_px"], [other])
        assert verdict != "match", (url, other, sims)


def test_握手照_两张脸差不多大_不换():
    """Medvedev-026（握手）真模型检出的脸：第二张是第一张的 0.81——两人同框，最大那张脸是他也不换。"""
    rec = next(v for k, v in replay.load_faces().items() if k.endswith("Daniil-Medvedev-026.jpg"))
    faces = rec["rep"]["faces"]
    assert cu.second_face(faces[0], faces) == pytest.approx(0.81, abs=0.01)
    ctx = _ctx_medvedev()
    got = cu.image_verdict(_plain_jpeg(*rec["size"]), _spec_medvedev(), ctx,
                           checker=lambda *a, **k: rec["rep"])
    assert any(p.startswith("两人同框") for p in got["problems"]), got["problems"]
    solo = next(v for k, v in replay.load_faces().items() if k.endswith("Daniil-Medvedev-012.jpg"))
    assert cu.second_face(solo["rep"]["faces"][0], solo["rep"]["faces"]) is None


def test_接口候选_两人同框_撞姓_别站_别的年份_开赛前发布的都不算():
    """点名那一层（不下图）：标题里还点了别人的、只对得上姓的（双胞胎／兄弟）、不是这一站的、
    年份不对的、开赛前就发布的——这几类在渠道那头或点名闸上就拦下。"""
    ctx = _ctx_medvedev()
    hand = cu.Candidate("atp-media", "https://x/Daniil-Medvedev-026.jpg", caption="2026 Hangzhou Medvedev Royer",
                        bind="exif", taken="2026:09:26 21:21:41", others=["royer"],
                        publish_utc="2026-09-26T17:11:15Z")
    assert any(p.startswith("标题／引用里除了主角还有 royer") for p in cu.metadata_problems(hand, ctx))
    solo = cu.Candidate("atp-media", "https://x/Daniil-Medvedev-012.jpg", caption="2026 Hangzhou Medvedev",
                        bind="exif", taken="2026:09:26 19:35:22", publish_utc="2026-09-26T13:35:35Z")
    relaxed: list[str] = []
    assert cu.metadata_problems(solo, ctx, relaxed) == [] and "按照片 EXIF" in relaxed[0], relaxed
    # 同一张换成只有姓的文件名：全名那一格过不了（普利斯科娃双胞胎、塞伦多洛兄弟）
    bare = cu.Candidate("atp-media", "https://x/Medvedev-012.jpg", caption="2026 Hangzhou Medvedev",
                        bind="exif", taken="2026:09:26 19:35:22", publish_utc="2026-09-26T13:35:35Z")
    assert any("只有姓" in p for p in cu.metadata_problems(bare, ctx))
    assert not apis.subject_hit("Karolina Pliskova", "Pliskova", "2026 Prague Pliskova",
                                "Kristyna Pliskova 001.jpg")
    assert apis.subject_hit("Roman Safiullin", "Safiullin", "2026 Hangzhou Safiulin", "Roman Safiullin 015.JPG")
    # 渠道那头：别站、别的年份、开赛前发布的都不进候选
    item = {"id": 1, "title": "2026 Hangzhou Medvedev", "publishFrom": 1790429735000,
            "imageUrl": "https://x/Daniil-Medvedev-012.jpg", "originalDetails": {"width": 5402, "height": 3601},
            "references": [{"type": "ATP_PLAYER", "sid": "MM58"}]}

    def run(**over):
        it = {**item, **over}
        return apis.sweep_atp_media(full_name="Daniil Medvedev", surname="Medvedev", player_id="MM58",
                                    event="Hangzhou", year="2026", **R2,
                                    fetch=lambda u: {"content": [it]},
                                    head=lambda u: replay.synth_head({"taken": "2026:09:26 19:35:22"}))
    assert [r["bound"] for r in run()["rows"]] == [True]
    assert run(title="2026 Chengdu Medvedev")["skipped"] == {"标题不是这一站": 1}
    assert run(title="2025 Hangzhou Medvedev")["skipped"] == {"标题年份不对": 1}
    assert run(publishFrom=1790420000000)["skipped"] == {"发布早于开赛": 1}
    assert run(originalDetails={"width": 1280, "height": 720})["skipped"] == {"原图铺不满 1080×1440": 1}
    two = run(references=[{"type": "ATP_PLAYER", "sid": "MM58"}, {"type": "ATP_PLAYER", "sid": "R0EB"}])
    assert two["rows"][0]["others"] == ["球员 id R0EB"], two["rows"]


# ---------------------------------------------------------------- ⑤ 排序：口味

def test_决赛捧杯排最前_赢球那一刻其次_然后正脸_清楚_脸大():
    ctx = cu.MatchContext(slug="x", final=True, subject_won=True,
                          end_utc=_u("2026-09-27T10:48:30Z"))

    def p(name, taken, h, frontal=True, clear=True, sim=0.5):
        c = cu.Candidate("wta-photos", f"https://x/{name}", taken_utc=taken)
        return {"candidate": c, "evidence": {
            "layout": {"face_out": [0, 300, 100, 300 + h]},
            "face": {"similarity": {"a": sim}, "pose": {"frontal": frontal, "clear": clear}}}}
    trophy = p("270927-singles-vc-5.jpg", "2026-09-27T11:18:58Z", 200)
    inmatch = p("270927-l-fernandez-vs-t-gibson-5.jpg", "2026-09-27T09:10:41Z", 400)
    moment = p("a.jpg", "2026-09-27T10:49:00Z", 150)
    blur = p("b.jpg", "2026-09-27T09:30:00Z", 500, clear=False)
    side = p("c.jpg", "2026-09-27T09:30:00Z", 450, frontal=False)
    ranked = sorted([inmatch, blur, side, moment, trophy], reverse=True, key=lambda x: cu.taste_key(x, ctx))
    assert [x["candidate"].filename for x in ranked] == [
        "270927-singles-vc-5.jpg", "a.jpg", "270927-l-fernandez-vs-t-gibson-5.jpg", "b.jpg", "c.jpg"]
    # 不是决赛：没有捧杯这一格；主角输了：没有「赢球那一刻」
    ctx.final = False
    assert cu.taste_key(trophy, ctx)[0] is False
    ctx.subject_won = False
    assert cu.taste_key(moment, ctx)[1] is False
    # 替身／老凭证没有 pose：退回原来的「脸最大」
    bare = p("d.jpg", "", 300)
    bare["evidence"]["face"].pop("pose")
    assert cu.taste_key(bare, ctx)[2:4] == (True, True)


# ---------------------------------------------------------------- ⑥ 决赛的图注不写对手

def test_决赛_说明写了final和日期_不点对手也认():
    ctx = cu.match_context(replay.spec_of("jovic-stearns-guadalajara-2026-final"),
                           times=lambda _id: (_u("2026-09-19T23:05:00Z"), _u("2026-09-20T00:35:20Z")))
    assert ctx.final and ctx.subject_won, ctx
    cap = ("US Iva Jovic lifts the trophy after winning the women's singles final match of the WTA "
           "Guadalajara Open tournament at the Panamerican Tennis Center in Zapopan, Mexico on "
           "September 19, 2026. (Photo by ULISES RUIZ / AFP)")
    relaxed: list[str] = []
    assert cu.metadata_problems(cu.Candidate("wta-photos", "https://x/t.jpg", caption=cap), ctx,
                                relaxed) == []
    assert relaxed and relaxed[0].startswith("决赛"), relaxed
    # 半决赛、没写日期、日期不对、不是决赛那一条 spec：都不放宽
    for bad in (cap.replace("singles final", "singles semi-final"),
                cap.replace(" on September 19, 2026", ""),
                cap.replace("September 19", "September 18")):
        assert cu.metadata_problems(cu.Candidate("wta-photos", "https://x/t.jpg", caption=bad), ctx), bad
    ctx.final = False
    assert cu.metadata_problems(cu.Candidate("wta-photos", "https://x/t.jpg", caption=cap), ctx)


def test_是不是决赛_看顶栏和轮次():
    assert cu.is_final({"topbar": {"line1": "2026 WTA500 新加坡 决赛"}})
    assert cu.is_final({"_match": {"round": "Women's Singles Final"}})
    for line in ("2026 ATP250 杭州站 半决赛", "2026 ATP250 杭州站 1/4决赛", "2026 美网 资格赛决赛",
                 "2026 ATP250 杭州站 第二轮"):
        assert not cu.is_final({"topbar": {"line1": line}}), line
    assert not cu.is_final({"_match": {"round": "Semi-Final"}})


# ---------------------------------------------------------------- ⑦ 预裁的抽帧也是抽帧

#: 仓库里 `cover.portrait.image` 指着的是**视频帧**的那几条（2026-09-28 全库扫的）：fernandez 那张
#: `_frame_why` 开头就是「⚠️ 抽帧」；成都四条 `_low_res_why` 开头是「源片 1920×1080」
PRECROPPED_FRAMES = {"fernandez-gibson-singapore-2026-final", "cerundolo-zhou-chengdu-2026-r1",
                     "shang-mannarino-chengdu-2026-r1", "tabilo-mannarino-chengdu-2026-r2",
                     "vacherot-harris-chengdu-2026-r2"}


def test_预裁进仓库的抽帧_O4认得出_官方实拍的一张都不误认():
    found = set()
    for path in sorted((ROOT / "specs" / "reels").glob("*.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        art = ((spec.get("cover") or {}).get("portrait")) or {}
        if isinstance(art, dict) and art.get("image") and cu.is_frame_cover(spec):
            found.add(path.stem)
    assert found == PRECROPPED_FRAMES, found ^ PRECROPPED_FRAMES
    # 反例就在仓库里：`_frame_why` 写着「不是抽帧」「换掉了抽帧」「没有用 frame_at 抽帧」的官方实拍
    for slug in ("eala-jovic-us-open-2026-r3", "fery-deminaur", "wang-kalinskaya-us-open-2026-r2",
                 "paul-cobolli", "jovic-stearns-guadalajara-2026-final"):
        assert not cu.is_frame_cover(replay.spec_of(slug)), slug
    assert cu.is_frame_cover({"cover": {"portrait": {"frame_at": 161.4}}})


def test_fernandez那条_O4现在是目标(tmp_path):
    """首推 09-27 14:57Z，48 小时窗口里；原来 `is_frame_cover` 只认 `frame_at`，它不在目标里。"""
    spec = replay.spec_of("fernandez-gibson-singapore-2026-final")
    (tmp_path / "specs" / "reels").mkdir(parents=True)
    (tmp_path / "specs" / "reels" / f"{spec['slug']}.json").write_text(json.dumps(spec), encoding="utf-8")
    (tmp_path / "data" / "reel_publish_ledger").mkdir(parents=True)
    (tmp_path / "data" / "reel_publish_ledger" / f"{spec['slug']}.json").write_text(json.dumps(
        {"attempts": [{"status": "sent", "at": "2026-09-27T14:57:07Z"}]}), encoding="utf-8")
    found, _notes = cu.targets(tmp_path, _u("2026-09-28T13:00:00Z"))
    assert [t.slug for t in found] == [spec["slug"]]
    # 换上去的 `_why` 说清换掉的是哪张预裁图
    ctx = cu.match_context(spec, times=lambda _id: (_u("2026-09-27T09:05:00Z"), _u("2026-09-27T10:48:30Z")))
    chosen = {"candidate": cu.Candidate("wta-photos", "https://x/vc.jpg", item_id="4582447",
                                        publish_utc="2026-09-27T12:05:19Z", taken="2026:09:27 19:18:58",
                                        offset="+08:00", taken_utc="2026-09-27T11:18:58Z", wh=(6562, 4377)),
              "evidence": {"size": [6562, 4377], "face": {"similarity": {"费尔南德斯": 0.53}, "ear": 0.24},
                           "layout": {"zoom": 1.0, "fill": 3.04, "face_out": [300, 258, 560, 558],
                                      "focus": 0.5, "focus_y": 0.5}},
              "relaxed": [], "row": {}}
    por = cu.upgraded_portrait(spec["cover"]["portrait"], chosen, ctx, "assets/reel/x-official.jpg")
    assert "预裁的抽帧 assets/reel/fernandez-gibson-final-trophy.jpg" in por["_why"], por["_why"]
    assert "条目 #4582447" in por["_why"] and "EXIF 拍摄 2026:09:27 19:18:58+08:00" in por["_why"]


# ---------------------------------------------------------------- ⑧ 渠道顺序、人查挂着等

def test_ATP的比赛第一档是ATP_Media_WTA的比赛第一档是WTA照片接口():
    assert [c.key for c in cch.CHANNELS][:2] == ["atp-media", "wta-photos"]
    for tour, first in (("atp", "atp-media"), ("wta", "wta-photos")):
        q = cch.Query(player="x", tour=tour)
        runs = [c.key for c in cch.CHANNELS if not c.skip(q)]
        assert runs[0] == first, (tour, runs)
    # O4 也用这两档（`o4_off` 空），`o4_query` 把窗口带过去
    assert not cch.channel("atp-media").o4_off and not cch.channel("wta-photos").o4_off
    ctx = _ctx_medvedev()
    q = cu.o4_query(ctx)
    assert (q.full_name, q.player_id, q.tz, q.start_utc, q.end_utc) == (
        "Daniil Medvedev", "MM58", "Asia/Shanghai", ctx.start_utc, ctx.end_utc)


def test_人查挂着等_每5分钟查一次_绑上一张就退出0_到点退出2(capsys):
    import find_cover_photo as fcp  # noqa: PLC0415

    clock = [datetime(2026, 9, 26, 13, 20, tzinfo=UTC)]
    slept: list[int] = []
    rows = {"n": 0}

    def fake_run(ch, q, o4=False):
        rows["n"] += 1
        hit = rows["n"] >= 3                     # 第三次才有
        raw = {"rows": [{"bound": hit, "others": [], "restriction": "", "item_id": "1", "title": "t",
                         "name": "n.jpg", "wh": (5000, 3300), "publish_utc": "", "bind_why": "w",
                         "url": "https://x"}], "pages_read": 1}
        return cch.ChannelResult(ch.key, ch.label, "ran", raw=raw, rows=[{}])

    def sleep(sec):
        slept.append(sec)
        clock[0] += timedelta(seconds=sec)

    q = cch.Query(player="Medvedev", tour="atp", start_utc=clock[0])
    orig = cch.run_channel
    cch.run_channel = fake_run
    try:
        assert fcp.wait_for_photo(q, "+60", now=lambda: clock[0], sleep=sleep) == 0
        assert slept == [300, 300] and rows["n"] == 3, (slept, rows)
        rows["n"] = -100
        slept.clear()
        assert fcp.wait_for_photo(q, "+12", now=lambda: clock[0], sleep=sleep) == 2
        assert slept == [300, 300], slept                       # 12 分钟：查三次、睡两次
        # 没有开赛时刻：绑不了场次，等也白等
        assert fcp.wait_for_photo(cch.Query(player="x", tour="atp"), "+60", now=lambda: clock[0],
                                  sleep=sleep) == 2
    finally:
        cch.run_channel = orig
    # 截止时刻：+分钟／ISO，最多 WAIT_MAX_MINUTES
    now = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
    assert fcp.wait_deadline("+45", now) == now + timedelta(minutes=45)
    assert fcp.wait_deadline("2026-09-26T13:00:00Z", now) == now + timedelta(hours=1)
    assert fcp.wait_deadline("+9999", now) == now + timedelta(minutes=fcp.WAIT_MAX_MINUTES)
    assert [c.key for c in fcp.preferred_channels(cch.Query(tour="wta"))] == ["wta-photos"]


# ---------------------------------------------------------------- ⑨ 自动链的封面那一步

def _draft(**extra) -> dict:
    d = {"slug": "medvedev-royer", "_production": {"kind": "orchestrated_reel", "event": "HANGZHOU",
                                                     "received_at": "2026-09-26T13:30:00Z", "round": "第二轮"},
         "_match": {"flashscore_id": "OWZ0gYVj", "winner": "梅德韦杰夫"},
         "cover": {"matchup": [{"name": "梅德韦杰夫", "name_en": "daniil medvedev"},
                               {"name": "鲁瓦耶", "name_en": "valentin royer"}]},
         "stats": {"a": {"headshot": "assets/players/headshots/atp-MM58.png"},
                   "b": {"headshot": "assets/players/headshots/atp-R0EB.png"}}}
    d.update(extra)
    return d


def test_自动链_照片接口那一档先查_找到了写原图_没有就照原来的路走(tmp_path, monkeypatch):
    import refresh_reel_cover as rrc  # noqa: PLC0415

    monkeypatch.setattr(rrc, "ROOT", tmp_path)
    blob = _plain_jpeg(5402, 3601)
    c = cu.Candidate("atp-media", "https://x/Daniil-Medvedev-012.jpg", item_id="4582136")
    found = {"chosen": {"candidate": c, "blob": blob}, "report": ["[照片接口] …"],
             "portrait": {"focus": 0.6, "focus_y": 0.4, "zoom": 1.0, "_why": "自动链照片接口…", "_gates": "g"}}
    draft, note = rrc.refresh(_draft(), pick=lambda d, now: found)
    por = draft["cover"]["portrait"]
    assert por["image"] == "assets/reel/medvedev-royer-cover.jpg" and por["focus"] == 0.6, por
    assert (tmp_path / por["image"]).read_bytes() == blob, "存原图字节，不重编码"
    assert por["_portrait_why"].startswith("自动链照片接口") and "4582136" in note
    # 没有：照原来那条路（Tennis TV 页头图）
    called = []
    monkeypatch.setattr(rrc, "fetch_tennistv_cover",
                        lambda url, event, out: called.append(url) or "Tennis TV 头图")
    d2, note2 = rrc.refresh(_draft(source_url="https://www.tennistv.com/videos/x"),
                            pick=lambda d, now: {"chosen": None, "report": []})
    assert called and note2 == "Tennis TV 头图"
    # 那一档炸了也照原来的路走，不拦
    called.clear()

    def boom(d, now):
        raise RuntimeError("接口挂了")
    rrc.refresh(_draft(source_url="https://www.tennistv.com/videos/x"), pick=boom)
    assert called
    # 不带 --write：只报，不写图
    (tmp_path / "assets/reel/medvedev-royer-cover.jpg").unlink()
    rrc.refresh(_draft(), pick=lambda d, now: found, write=False)
    assert not (tmp_path / "assets/reel/medvedev-royer-cover.jpg").exists()


def test_自动链_已有封面不换_只有卡死在视觉审核上的才换(tmp_path, monkeypatch):
    import refresh_reel_cover as rrc  # noqa: PLC0415

    img = tmp_path / "cover.jpg"
    img.write_bytes(_plain_jpeg(100, 100))
    asked = []

    def pick(d, now):
        asked.append(d["slug"])
        return {"chosen": None, "report": []}
    has = _draft(cover={**_draft()["cover"], "portrait": {"image": str(img)}})
    assert rrc.refresh(has, pick=pick)[1] == "已有封面" and asked == []
    for vis in ({"status": "pass", "cover_image": str(img)},                         # 过了：不动
                {"status": "waiting", "cover_image": str(img), "retryable": True},   # 还会重审：不动
                {"status": "waiting", "cover_image": "other.jpg", "retryable": False}):
        assert not rrc.stuck_on_cover({**has, "_visual_evidence": vis}), vis
    stuck = {**has, "_visual_evidence": {"status": "waiting", "cover_image": str(img), "retryable": False}}
    assert rrc.stuck_on_cover(stuck)
    _d, note = rrc.refresh(stuck, pick=pick)
    assert asked == ["medvedev-royer"] and "卡在视觉审核上" in note
    # 工作流「这一班要不要认人」：新鲜的自动草稿、没封面或卡死的才要
    now = _u("2026-09-26T14:00:00Z")
    assert rrc.needs_official_pick(_draft(), now)
    assert not rrc.needs_official_pick(has, now) and rrc.needs_official_pick(stuck, now)
    assert not rrc.needs_official_pick(_draft(), now + timedelta(days=2))
    assert not rrc.needs_official_pick({**_draft(), "_production": {"kind": "manual"}}, now)


def test_自动草稿的封面主角_默认赢家_爆冷认领了就是明星输家():
    assert cu.draft_subject(_draft()) == "梅德韦杰夫"
    assert cu.draft_subject(_draft(_cover_brief={"preferred_subject": "鲁瓦耶"})) == "鲁瓦耶"


def test_自动草稿走和O4同一套闸(monkeypatch):
    """`pick_for_draft`：从草稿推出 subject／赛事（`_production.event` 大写也认）／球员 id，只开照片接口两档。"""
    got = cu.pick_for_draft(_draft(), _u("2026-09-26T14:00:00Z"),
                            times=lambda _id: (_u(R2["start"].isoformat()), _u(R2["end"].isoformat())),
                            sweeps_for=lambda ctx: [("测试", lambda: [])])
    ctx = got["ctx"]
    assert (ctx.subject_zh, ctx.event_en.lower(), ctx.tz, ctx.player_id) == (
        "梅德韦杰夫", "hangzhou", "Asia/Shanghai", "MM58"), ctx
    assert got["chosen"] is None and "这一班没有" in got["report"][-1]
    names = [n for n, _r in cu.default_sweeps(ctx, cu.API_CHANNELS)]
    assert names == ["ATP Media 照片接口", "WTA 照片接口"], names


# ---------------------------------------------------------------- 小工具

def _plain_jpeg(w: int, h: int) -> bytes:
    from PIL import Image  # noqa: PLC0415

    buf = io.BytesIO()
    Image.new("RGB", (w, h), (40, 60, 40)).save(buf, "JPEG", quality=40)
    return buf.getvalue()


def _splice(head: bytes, jpeg: bytes) -> bytes:
    """把录下来的 APP 段（EXIF／XMP／IPTC）拼进一张新图：SOI ＋ 那几段 ＋ 新图 SOI 之后的全部。"""
    segs = [(m, p) for m, p in apis.jpeg_segments(head) if 0xE1 <= m <= 0xEF]
    out = b"\xff\xd8" + b"".join(bytes([0xFF, m]) + (len(p) + 2).to_bytes(2, "big") + p for m, p in segs)
    return out + jpeg[2:]


def _checker(name: str):
    def check(img, expected, target=None):
        return {"status": "ok",
                "identity": {"verdict": "match", "name": name, "similarity": {name: 0.5},
                             "face": [2400, 500, 2700, 850], "face_px": 350},
                "eyes": {"verdict": "open", "ear": 0.25}}
    return check


def _spec_rublev() -> dict:
    return replay.spec_of("rublev-gaston-hangzhou-2026-qf")


def _ctx_rublev():
    return cu.match_context(_spec_rublev(), times=lambda _id: (_u("2026-09-27T07:45:00Z"),
                                                               _u("2026-09-27T10:39:06Z")))


def _spec_medvedev() -> dict:
    return replay.spec_of("medvedev-royer-hangzhou-2026-r2")


def _ctx_medvedev():
    return cu.match_context(_spec_medvedev(), times=lambda _id: (_u("2026-09-26T11:35:00Z"),
                                                                 _u("2026-09-26T13:20:51Z")))


def test_splice替身本身读得回说明():
    blob = _splice(_head("getty-2296808078"), _plain_jpeg(50, 40))
    assert apis.parse_head(blob)["caption"].endswith("China OUT")
    from PIL import Image  # noqa: PLC0415
    assert Image.open(io.BytesIO(blob)).size == (50, 40)
    assert date(2026, 9, 27) in cu.caption_dates(apis.parse_head(blob)["caption"])
