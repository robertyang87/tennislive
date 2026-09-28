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
    inmatch = p("x-inmatch.jpg", "2026-09-27T09:10:41Z", 400)
    moment = p("a.jpg", "2026-09-27T10:49:00Z", 150)
    blur = p("b.jpg", "2026-09-27T09:30:00Z", 500, clear=False)
    side = p("c.jpg", "2026-09-27T09:30:00Z", 450, frontal=False)
    # 复审 nit：`270927-l-fernandez-vs-t-gibson-5` 真模型 EAR 0.1628——过睁眼线（0.16），眼皮是垂着的。
    # 不拦，排在所有眼睛睁开的后面（它比赛中、脸最大，原来排第三）
    lowered = p("270927-l-fernandez-vs-t-gibson-5.jpg", "2026-09-27T09:10:41Z", 600)
    lowered["evidence"]["face"]["ear"] = 0.1628
    ranked = sorted([inmatch, blur, lowered, side, moment, trophy], reverse=True,
                    key=lambda x: cu.taste_key(x, ctx))
    assert [x["candidate"].filename for x in ranked] == [
        "270927-singles-vc-5.jpg", "a.jpg", "x-inmatch.jpg", "b.jpg", "c.jpg",
        "270927-l-fernandez-vs-t-gibson-5.jpg"]
    # 压线的捧杯照也排在睁眼的比赛图后面；离线 0.02 以外（0.181）不算压线
    trophy["evidence"]["face"]["ear"] = 0.17
    assert cu.taste_key(trophy, ctx) < cu.taste_key(inmatch, ctx)
    trophy["evidence"]["face"]["ear"] = 0.181
    assert cu.taste_key(trophy, ctx) > cu.taste_key(moment, ctx)
    # 不是决赛：没有捧杯这一格；主角输了：没有「赢球那一刻」
    ctx.final = False
    assert cu.taste_key(trophy, ctx)[1] is False
    ctx.subject_won = False
    assert cu.taste_key(moment, ctx)[2] is False
    # 替身／老凭证没有 pose、没有 EAR：退回原来的「脸最大」
    bare = p("d.jpg", "", 300)
    bare["evidence"]["face"].pop("pose")
    assert cu.taste_key(bare, ctx)[0] is True and cu.taste_key(bare, ctx)[3:5] == (True, True)


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
    monkeypatch.chdir(tmp_path)
    blob = _plain_jpeg(5402, 3601)
    c = cu.Candidate("atp-media", "https://x/Daniil-Medvedev-012.jpg", item_id="4582136")
    found = {"chosen": {"candidate": c, "blob": blob}, "report": ["[照片接口] …"],
             "portrait": {"focus": 0.6, "focus_y": 0.4, "zoom": 1.0, "_why": "自动链照片接口…", "_gates": "g"}}
    draft, note = rrc.refresh(_draft(), pick=lambda d, now, **kw: found)
    por = draft["cover"]["portrait"]
    assert por["image"] == "assets/reel/medvedev-royer-cover.jpg" and por["focus"] == 0.6, por
    assert (tmp_path / por["image"]).read_bytes() == blob, "存原图字节，不重编码"
    assert por["_portrait_why"].startswith("自动链照片接口") and "4582136" in note
    assert por["_source_url"] == c.url, "记下挑的是哪一张：视觉审核判掉之后要排除它"
    # 没有：照原来那条路（Tennis TV 页头图）
    called = []
    monkeypatch.setattr(rrc, "fetch_tennistv_cover",
                        lambda url, event, out: called.append(url) or "Tennis TV 头图")
    d2, note2 = rrc.refresh(_draft(source_url="https://www.tennistv.com/videos/x"),
                            pick=lambda d, now, **kw: {"chosen": None, "report": []})
    assert called and note2 == "Tennis TV 头图"
    # 那一档炸了也照原来的路走，不拦
    called.clear()

    def boom(d, now, **kw):
        raise RuntimeError("接口挂了")
    rrc.refresh(_draft(source_url="https://www.tennistv.com/videos/x"), pick=boom)
    assert called
    # 不带 --write：只报，不写图
    (tmp_path / "assets/reel/medvedev-royer-cover.jpg").unlink()
    rrc.refresh(_draft(), pick=lambda d, now, **kw: found, write=False)
    assert not (tmp_path / "assets/reel/medvedev-royer-cover.jpg").exists()


def test_自动链_已有封面不换_只有卡死在视觉审核上的才换(tmp_path, monkeypatch):
    import refresh_reel_cover as rrc  # noqa: PLC0415

    img = tmp_path / "cover.jpg"
    img.write_bytes(_plain_jpeg(100, 100))
    asked = []

    def pick(d, now, **kw):
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


# ---------------------------------------------------------------- ⑩ 复审 FIX ROUND 1：墙钟上限

class _Clock:
    """假的墙钟：挂住的请求按它拿到的超时往前拨，测「一份草稿最多花多少秒」不用真等。"""

    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def _hang(clock: _Clock, log: list, kind: str):
    """一个挂住的请求：按给它的超时把钟往前拨，然后超时。"""
    import requests  # noqa: PLC0415

    def call(url, *a, timeout=None, **kw):
        log.append((kind, url, timeout))
        clock.t += float(timeout)
        raise requests.exceptions.ReadTimeout(f"{kind} 挂住了（{timeout}s）")
    return call


def test_自动链封面那一步有墙钟上限_挂住也不冲过job(monkeypatch):
    """复审 BLOCKING 1：`refresh_reel_cover --draft` 没有任何时间上限——flashscore `dc_1` 走 `match_feed._get`
    的 3 × 40 秒、照片接口每页／每个头 40 秒、每张原图 60 秒，挂住时一份草稿 80~130 秒，一班最多 18 份，
    冲过 job 的 15 分钟，落库和派发两步不跑，**封面早就好了的草稿也一起挡住**。

    ① 一份草稿的总账（`Budget`）：flashscore 和照片接口**一起**挂住，假钟上花掉的不超过给它的秒数；
       flashscore 只问一次、10 秒；男女认得出（这份草稿没有官方头像，按 top500 认）只翻一档
    ② 草稿里记过开赛／结束（`_cover_api.times`）就不问 flashscore
    ③ 工作流：和 FEED_RETRY_BUDGET 同一个 `$SECONDS` 钟的整班截止、每份的上限、外面一层 timeout，
       加起来留得出装依赖和落库、派发的时间"""
    import official_photo_apis as apis  # noqa: PLC0415

    clock, log = _Clock(), []
    monkeypatch.setattr(apis, "get_json", _hang(clock, log, "page"))
    monkeypatch.setattr(apis, "get_head", _hang(clock, log, "head"))
    monkeypatch.setattr(cu, "fetch_image", _hang(clock, log, "original"))

    def fs(match_id, *, attempts=3, timeout=40):
        log.append(("flashscore", match_id, (attempts, timeout)))
        clock.t += attempts * timeout
        raise RuntimeError("flashscore 挂住了")
    monkeypatch.setattr(cu, "flashscore_times", fs)
    draft = _draft(stats={})                                      # 没有官方头像：spec_tour 是 None
    assert cu.draft_tour(draft) == "atp"                          # 按 top500 认得出 Daniil Medvedev
    budget = apis.Budget(60, clock=clock)
    t0 = clock.t
    got = cu.pick_for_draft(draft, _u("2026-09-26T14:30:00Z"), budget=budget)
    spent = clock.t - t0
    assert spent <= 60, (spent, log)
    assert [x[2] for x in log if x[0] == "flashscore"] == [(1, cu.FS_QUICK_TIMEOUT)], log
    pages = [x[1] for x in log if x[0] == "page"]
    assert pages and all(u.startswith(apis.ATP_MEDIA_API) for u in pages), pages   # 只翻一档
    assert all(x[2] <= apis.PAGE_TIMEOUT for x in log if x[0] == "page"), log
    assert got["chosen"] is None and got["complete"] is False, "挂住的这一趟是「没查完」，不是「查过、没有」"
    assert "没查完" in got["report"][-1] or "没查成" in got["report"][-1], got["report"]
    # 同一个账再来一趟：两趟合起来还是不超过 60 秒；用完之后一个请求都不再发
    got = cu.pick_for_draft(draft, _u("2026-09-26T14:30:00Z"), budget=budget)
    assert clock.t - t0 <= 60 and budget.spent, (clock.t - t0, log)
    n = len(log)
    got = cu.pick_for_draft(draft, _u("2026-09-26T14:30:00Z"), budget=budget)
    assert len(log) == n and not got["complete"], log[n:]
    # ② 记过开赛／结束：不问 flashscore
    log.clear()
    known = {"flashscore_id": "OWZ0gYVj", "start_utc": "2026-09-26T11:35:00Z", "end_utc": "2026-09-26T13:20:51Z"}
    got = cu.pick_for_draft(draft, _u("2026-09-26T14:30:00Z"), budget=apis.Budget(30, clock=clock),
                            known_times=known)
    assert not [x for x in log if x[0] == "flashscore"], log
    assert got["ctx"].date_source.startswith("flashscore dc_1_OWZ0gYVj"), got["ctx"].date_source
    # 下原图也从同一个账里扣：页和头都正常（录下来的），两张能过点名闸的原图挂住——只下得了预算里那一张
    log.clear()
    k = replay.kit(_u("2026-09-26T14:30:00Z"))
    t1 = clock.t
    got = cu.pick_for_draft(draft, _u("2026-09-26T14:30:00Z"), budget=apis.Budget(60, clock=clock),
                            known_times=known, sweeps_for=k["sweeps_for"], checker=k["checker"])
    originals = [x for x in log if x[0] == "original"]
    assert originals and all(x[2] <= cu.ORIGINAL_TIMEOUT for x in originals), log
    assert clock.t - t1 <= 60 and not got["complete"], (clock.t - t1, log)

    # ③ 工作流
    import re  # noqa: PLC0415

    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github/workflows/reel-auto-ready.yml").read_text(encoding="utf-8"))
    run = "\n".join(str(st.get("run") or "") for st in wf["jobs"]["ready"]["steps"])
    num = {k: int(re.search(rf"^\s*{k}=(\d+)$", run, re.M).group(1))
           for k in ("FEED_RETRY_BUDGET", "COVER_API_DEADLINE", "COVER_API_PER_DRAFT", "COVER_REFRESH_TIMEOUT")}
    loop = run.index("for DRAFT in")
    assert all(run.index(f"{k}=") < loop for k in num), "预算是整班的，不是每份的"
    call = next(line for line in run.splitlines() if "tools/refresh_reel_cover.py --draft" in line)
    assert call.lstrip().startswith('timeout "$COVER_REFRESH_TIMEOUT"') and "$API_ARGS" in call, call
    around = run[run.index("API_LEFT=$((COVER_API_DEADLINE - SECONDS))"):run.index(call)]
    assert "--api-budget" in around and "--no-api" in around, around
    assert num["COVER_API_DEADLINE"] <= num["FEED_RETRY_BUDGET"], "接口档不许比备料重跑的截止还晚"
    assert num["COVER_REFRESH_TIMEOUT"] >= num["COVER_API_PER_DRAFT"] + 60, "外面那层要留出原来那两条路的时间"
    minutes = wf["jobs"]["ready"]["timeout-minutes"]
    # 截止前最后一份：接口在截止前停（进程内预算），原来那两条路再跑到 timeout；留 3 分钟给装依赖、审核、落库、派发
    assert num["COVER_API_DEADLINE"] + num["COVER_REFRESH_TIMEOUT"] + 180 <= minutes * 60, num


def test_命令行_no_api不查接口_api_budget传进去_没学到东西不写草稿(tmp_path, monkeypatch, capsys):
    import refresh_reel_cover as rrc  # noqa: PLC0415

    monkeypatch.chdir(tmp_path)
    path = tmp_path / "medvedev-royer.draft.json"
    draft = _draft()
    # 原来的格式和 json.dumps 不一样（紧凑写法）：什么都没学到时不许被「重排版」写一遍
    path.write_text(json.dumps(draft, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    seen = []

    def pick(d, now, **kw):
        seen.append(kw)
        return {"chosen": None, "report": [], "complete": False}
    monkeypatch.setattr(cu, "pick_for_draft", pick)
    monkeypatch.setattr(rrc, "fetch_tennistv_cover", lambda *a: (_ for _ in ()).throw(RuntimeError("x")))
    import fetch_match_pbp  # noqa: PLC0415
    monkeypatch.setattr(fetch_match_pbp, "find_match", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("离线")))
    before = path.read_bytes()
    monkeypatch.setattr(sys, "argv", ["x", "--draft", str(path), "--write", "--no-api"])
    assert rrc.main() == 0 and seen == [] and path.read_bytes() == before
    monkeypatch.setattr(sys, "argv", ["x", "--draft", str(path), "--write", "--api-budget", "42"])
    assert rrc.main() == 0 and seen[-1]["budget"] == 42.0 and path.read_bytes() == before
    # 学到了（问到开赛／结束）：记进 `_cover_api`，写草稿；下一班 pick 拿到 known_times
    times = {"flashscore_id": "OWZ0gYVj", "start_utc": "2026-09-26T11:35:00Z",
             "end_utc": "2026-09-26T13:20:51Z", "source": "flashscore dc_1_OWZ0gYVj（DC／DD）"}
    monkeypatch.setattr(cu, "pick_for_draft",
                        lambda d, now, **kw: seen.append(kw) or {"chosen": None, "report": [], "times": times})
    assert rrc.main() == 0
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["_cover_api"]["times"] == times and "cover" in saved and "portrait" not in saved["cover"]
    assert "[waiting]" in capsys.readouterr().out
    assert rrc.main() == 0 and seen[-1]["known_times"] == times


def test_命令行_need_faces_只看有probe的新鲜草稿(tmp_path, monkeypatch, capsys):
    """工作流「这一班要不要认人」：循环里没有已落库 probe 的草稿这一班跳过，不为它装认人依赖。"""
    import refresh_reel_cover as rrc  # noqa: PLC0415

    fresh = _draft(_production={**_draft()["_production"],
                                "received_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")})
    path = tmp_path / "medvedev-royer.draft.json"
    path.write_text(json.dumps(fresh, ensure_ascii=False), encoding="utf-8")
    for probed, want in ((set(), "false"), ({"medvedev-royer"}, "true"), (None, "true")):
        monkeypatch.setattr(rrc, "slugs_with_probe", lambda probed=probed: probed)
        monkeypatch.setattr(sys, "argv", ["x", "--need-faces", str(path)])
        assert rrc.main() == 0 and capsys.readouterr().out.strip() == want, probed


def test_自动链_下过没过的原图不再下(tmp_path, monkeypatch):
    """复审 nit：`pick_for_draft` 不记得下过什么，闸没过的原图每一班重下（bondar-birrell 每班两张、5.8 MB）。
    wong-vallejo 录下来的：Coleman-Wong-010 认人 0.24（unknown）——结论确定，记进 `_cover_api.tried`，下一班不下。"""
    import refresh_reel_cover as rrc  # noqa: PLC0415

    monkeypatch.setattr(rrc, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    m = next(x for x in replay.MATCHES if x.slug.startswith("wong-vallejo"))
    spec = replay.spec_of(m.slug)
    draft = {"slug": "wong-vallejo", "_production": {"kind": "orchestrated_reel", "event": "Hangzhou",
                                                     "received_at": m.end, "round": "第二轮"},
             "_match": {"flashscore_id": "x", "winner": spec["cover"]["subject"]},
             "cover": {"matchup": spec["cover"]["matchup"]}, "stats": spec["stats"]}
    k = replay.kit(_u(m.first_push))

    def pick(d, now, **kw):
        return cu.pick_for_draft(d, now, sweeps_for=k["sweeps_for"], fetch=k["fetch"], checker=k["checker"],
                                 times=lambda _i: (_u(m.start), _u(m.end)), **kw)
    rrc.refresh(draft, now=_u(m.first_push), pick=pick)
    first = list(k["calls"]["downloads"])
    assert first and all(u.endswith("Coleman-Wong-010.jpg") for u in first), first
    assert draft["_cover_api"]["tried"] == first
    rrc.refresh(draft, now=_u(m.first_push), pick=pick)
    assert k["calls"]["downloads"] == first, "下过、结论确定没过的不再下"


def _reject(draft: dict, sha: str) -> None:
    """视觉审核判掉现在这张封面（最常见的那一种理由：25 份卡住的草稿里 14 份）、不会重审。"""
    draft["_visual_evidence"] = {"status": "waiting", "visual_status": "waiting", "retryable": False,
                                 "cover_image": draft["cover"]["portrait"]["image"], "input_sha256": sha,
                                 "problems": ["封面情绪应为 winner_celebration，现在是 other"]}


def test_自动链_卡在视觉审核上的照片接口图_不再挑它_没有别的就走原来的路_查完了不再要认人(tmp_path, monkeypatch):
    """复审 BLOCKING 2（录下来的数据，medvedev-royer，09-26 14:30Z）：第 1 班挑中 #4582136
    Daniil-Medvedev-012，视觉审核判掉之后，第 2~4 班**每一班重挑同一张**、草稿一个字节不变、
    `fetch_tennistv_cover` 一次没调、`needs_official_pick` 一直是 True（每 10 分钟装一遍认人依赖，最长 20 小时）。
    改之前的基线第 1 班就会走 Tennis TV。现在：
    - 被判掉的记 `_cover_api.rejected`，挑图时排除——第 2 班挑的是另一张（#4582138 Daniil-Medvedev-014）
    - 照片接口没有别的能换、而卡住的是照片接口那张：接着走原来那条路（Tennis TV 页头图）
    - 卡在 Tennis TV 那张上：照片接口完整查一遍，没有能换的就记 `stuck_checked`——之后不再查、不再要认人"""
    import refresh_reel_cover as rrc  # noqa: PLC0415

    monkeypatch.setattr(rrc, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    now = _u("2026-09-26T14:30:00Z")
    k = replay.kit(now)
    picks = []

    def pick(d, at, **kw):
        picks.append(kw)
        return cu.pick_for_draft(d, at, sweeps_for=k["sweeps_for"], fetch=k["fetch"], checker=k["checker"],
                                 times=lambda _i: (R2["start"], R2["end"]), **kw)
    ttv = []

    def tennistv(url, event, out):
        ttv.append(url)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(_plain_jpeg(1600, 2000))
        return "Tennis TV 头图"
    monkeypatch.setattr(rrc, "fetch_tennistv_cover", tennistv)
    draft = _draft(source_url="https://www.tennistv.com/videos/x")
    # 第 1 班：照片接口挑 012
    draft, note = rrc.refresh(draft, now=now, pick=pick)
    first = draft["cover"]["portrait"]["_source_url"]
    assert first.endswith("Daniil-Medvedev-012.jpg") and "4582136" in note, note
    assert not rrc.needs_official_pick(draft, now)
    # 第 2 班：012 被判掉——不再挑它，挑 014
    _reject(draft, "h1")
    assert rrc.stuck_on_cover(draft) and rrc.needs_official_pick(draft, now)
    draft, note = rrc.refresh(draft, now=now, pick=pick)
    assert draft["_cover_api"]["rejected"] == [first]
    second = draft["cover"]["portrait"]["_source_url"]
    assert second.endswith("Daniil-Medvedev-014.jpg") and second != first, second
    assert first not in k["calls"]["downloads"][2:], "被判掉的那张不再下"
    assert ttv == []
    # 换上了、这一班审核那一步没跑（旧结论还挂在同一个路径上）：新图**还没审**，不算卡住、不许记进 rejected
    n = len(picks)
    assert not rrc.stuck_on_cover(draft) and not rrc.needs_official_pick(draft, now)
    draft, note = rrc.refresh(draft, now=now, pick=pick)
    assert note == "已有封面" and len(picks) == n and draft["_cover_api"]["rejected"] == [first]
    # 第 3 班：014 也被判掉——照片接口没有别的了，卡住的是照片接口那张：走原来那条路
    _reject(draft, "h2")
    draft, note = rrc.refresh(draft, now=now, pick=pick)
    assert ttv == ["https://www.tennistv.com/videos/x"] and note == "Tennis TV 头图", note
    assert draft["cover"]["portrait"]["_portrait_why"].startswith("Tennis TV")
    assert draft["_cover_api"]["rejected"] == [first, second]
    # 换成 Tennis TV 那张、还没审：同样不算卡住
    assert not rrc.stuck_on_cover(draft) and not rrc.needs_official_pick(draft, now)
    # 第 4 班：Tennis TV 那张也被判掉——照片接口查一遍（两张都判过了），查完了记下来，不再走 Tennis TV
    _reject(draft, "h3")
    assert rrc.needs_official_pick(draft, now)
    n = len(picks)
    draft, note = rrc.refresh(draft, now=now, pick=pick)
    assert len(picks) == n + 1 and "卡在视觉审核上" in note and ttv == ["https://www.tennistv.com/videos/x"]
    assert draft["_cover_api"]["stuck_checked"] == rrc.stuck_key(draft)
    assert not rrc.needs_official_pick(draft, now), "查完了、没有能换的：不再为它装认人依赖"
    # 第 5 班：不再查
    draft, note = rrc.refresh(draft, now=now, pick=pick)
    assert len(picks) == n + 1 and "卡在视觉审核上" in note
    # 重审之后（input_sha256 变了）是新的状态，再查一遍
    _reject(draft, "h4")
    assert rrc.needs_official_pick(draft, now)


def test_自动链_卡在照片接口图上_原来的路也没有_查完了不再每班查接口(tmp_path, monkeypatch):
    """原来那条路也没有（不是 Tennis TV 的源片，WTA 赛后稿那条也找不到）：草稿照旧卡着——
    但照片接口那一档查完了就不再每一班查、不再要认人；原来那条路照旧每一班试（和改之前一样）。"""
    import fetch_match_pbp  # noqa: PLC0415
    import refresh_reel_cover as rrc  # noqa: PLC0415

    monkeypatch.setattr(rrc, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    old_path = []
    monkeypatch.setattr(fetch_match_pbp, "find_match",
                        lambda *a, **k: old_path.append(1) or (_ for _ in ()).throw(RuntimeError("没有")))
    blob = _plain_jpeg(5402, 3601)
    url = "https://x/Daniil-Medvedev-012.jpg"
    picks = []

    def pick(d, now, **kw):
        picks.append(kw)
        if url in kw["rejected"]:
            return {"chosen": None, "report": [], "complete": True}
        return {"chosen": {"candidate": cu.Candidate("atp-media", url, item_id="4582136"), "blob": blob},
                "report": [], "portrait": {"_why": cu.AUTO_DRAFT_WHY_PREFIX + "：…", "_source_url": url}}
    now = _u("2026-09-26T14:30:00Z")
    draft, _n = rrc.refresh(_draft(), now=now, pick=pick)
    _reject(draft, "h1")
    draft, note = rrc.refresh(draft, now=now, pick=pick)
    assert picks[-1]["rejected"] == [url] and old_path == [1], "照片接口没有别的：原来那条路接着试"
    assert draft["cover"]["portrait"]["_source_url"] == url and draft["_cover_api"]["stuck_checked"]
    assert not rrc.needs_official_pick(draft, now)
    draft, note = rrc.refresh(draft, now=now, pick=pick)
    assert len(picks) == 2 and old_path == [1, 1]


# ---------------------------------------------------------------- ⑪ 复审 FIX ROUND 1：nits

def test_男女认得出就只跑一档_认不出不查():
    """复审 nit：129 份自动草稿 52 份 `spec_tour` 是 None，两档都跑。`resolve_tour`：官方头像 → top500 → 赛事。"""
    assert cu.resolve_tour({}, "Daniil Medvedev")[0] == "atp"
    assert cu.resolve_tour({}, "Leylah Fernandez")[0] == "wta"
    # 大满贯、男女同站：赛事认不出，名字认得出
    assert cu.resolve_tour({"_production": {"event": "US Open"}}, "Daniil Medvedev")[0] == "atp"
    assert cu.resolve_tour({"_production": {"event": "Beijing"}}, "Leylah Fernandez")[0] == "wta"
    assert cu.resolve_tour({"_production": {"event": "MONTERREY"}}, "Nobody Known")[0] == "wta"
    assert cu.resolve_tour({"_production": {"event": "Hangzhou"}}, "Nobody Known")[0] == "atp"
    for ev in ("US Open", "Beijing", "Laver Cup", ""):
        assert cu.resolve_tour({"_production": {"event": ev}}, "Nobody Known")[0] is None, ev
    # 头像前缀优先（名字对不上也按头像）
    assert cu.resolve_tour({"stats": {"a": {"headshot": "x/wta-1.jpg"}}}, "Daniil Medvedev")[0] == "wta"
    # 认不出：照片接口那一档不查（一个请求都不发），`needs_official_pick` 也不为它装依赖
    d = _draft(stats={}, _production={**_draft()["_production"], "event": "US Open"},
               cover={"matchup": [{"name": "梅德韦杰夫", "name_en": "nobody known"},
                                  {"name": "鲁瓦耶", "name_en": "valentin royer"}]})
    swept = []
    got = cu.pick_for_draft(d, _u("2026-09-26T14:00:00Z"), times=lambda _i: (R2["start"], R2["end"]),
                            sweeps_for=lambda ctx: swept.append(1) or [])
    assert swept == [] and got["complete"] and "认不出是男子还是女子" in got["report"][-1]
    assert cu.draft_api_blocker(d, _u("2026-09-26T14:00:00Z"))
    import refresh_reel_cover as rrc  # noqa: PLC0415
    assert not rrc.needs_official_pick(d, _u("2026-09-26T14:00:00Z"))


@pytest.mark.parametrize("text, hit", [
    ("… on September 27, 2026. (Photo by STR / AFP), China OUT", "China OUT"),
    ("… on September 27, 2026. (Photo by STR / AFP) -- China OUT", "China OUT"),
    ("… (Photo by STR / AFP via Getty Images) / China and Taiwan OUT", "China and Taiwan OUT"),
    ("… (Photo by STR / AFP via Getty Images) / China Out", "China Out"),
    ("REUTERS/Stringer CHINA AND TAIWAN OUT", "CHINA AND TAIWAN OUT"),
    # 不许误伤
    ("Tennis / Nadal Out of Wimbledon with injury", ""),
    ("Coleman Wong reacts, out of breath, after the point", ""),
    ("(AP Photo/Andy Wong)", ""),
])
def test_发布限制的几种少见写法也认得出(text, hit):
    got = apis.restriction(text)
    assert bool(got) == bool(hit) and hit in got, (text, got)


def _app(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


def _iptc_app13(**records: str) -> bytes:
    """IPTC-IIM（APP13 / Photoshop IRB 0x0404）：`caption=` → 2:120、`instructions=` → 2:40。"""
    ds = {"caption": 120, "instructions": 40}
    body = b"".join(b"\x1c\x02" + bytes([ds[k]]) + len(v.encode()).to_bytes(2, "big") + v.encode()
                    for k, v in records.items())
    irb = b"8BIM" + (0x0404).to_bytes(2, "big") + b"\x00\x00" + len(body).to_bytes(4, "big") + body
    irb += b"\x00" * (len(body) % 2)
    return _app(0xED, b"Photoshop 3.0\x00" + irb)


def _exif_app1(caption: str) -> bytes:
    from PIL import Image  # noqa: PLC0415

    exif = Image.Exif()
    exif[0x010E] = caption
    return _app(0xE1, b"Exif\x00\x00" + exif.tobytes())


def test_发布限制每一格说明都扫_原图整张读():
    """复审 nit：`parse_head` 只留先读到的那一格说明、`restriction` 只扫它；`image_verdict` 只读前 128 KB。
    录下来的 wta-4578951：EXIF 那格结尾「/ AFP)」，IPTC 那格「/ AFP via Getty Images)」——Getty 的
    「/ China OUT」正追加在 IPTC 这一格。"""
    rec = apis.parse_head(_head("wta-4578951"))
    assert len(rec["texts"]) >= 2 and rec["texts"][0] != rec["texts"][1], rec["texts"]
    clean = "Leylah Fernandez hits a return during the final (Photo by X / AFP)"
    head = (b"\xff\xd8" + _exif_app1(clean)
            + _iptc_app13(caption=clean.replace(")", " via Getty Images) / China OUT")))
    got = apis.parse_head(head)
    assert got["caption"] == clean, "给人看的那一格照旧是先读到的"
    assert apis.restriction(got["caption"]) == "" and "China OUT" in apis.restriction(*got["texts"])
    # sweep 的行、image_verdict 都扫到了
    item = {"id": 1, "title": "2026 Hangzhou Medvedev", "publishFrom": 1790429735000,
            "imageUrl": "https://x/Daniil-Medvedev-012.jpg", "originalDetails": {"width": 5402, "height": 3601}}
    row = apis.sweep_atp_media(full_name="Daniil Medvedev", surname="Medvedev", player_id="MM58",
                               event="Hangzhou", year="2026", **R2, fetch=lambda u: {"content": [item]},
                               head=lambda u: head)["rows"][0]
    assert "China OUT" in row["restriction"], row
    # 限制那一格排在 128 KB 之后（前面几段大 APP 段）：原来 blob[:128 KB] 读不到
    pad = b"".join(_app(0xE2, b"ICC_PROFILE\x00" + b"\x00" * 60000) for _ in range(3))
    blob = head[:2] + _exif_app1(clean) + pad + head[2 + len(_exif_app1(clean)):] + _plain_jpeg(5000, 3300)[2:]
    assert blob.index(b"China OUT") > apis.HEAD_BYTES
    got = cu.image_verdict(blob, _spec_rublev(), _ctx_rublev(), checker=_checker("卢布列夫"))
    assert any("原图嵌的说明里" in p and "China OUT" in p for p in got["problems"]), got["problems"]


def test_翻页出错不说成翻满_中途出错是没查完不是查空():
    """复审 nit：`pages()` 出错 `break` 之后落到 `truncated = True`——挂住那一趟报「第 0 页：ReadTimeout；
    翻满 15 页还没翻到开赛前两小时」；第 1 页之后出错，这一档还记「查成」。"""
    def boom(_url):
        raise ConnectionError("reset")
    items, stats = apis.pages(apis.ATP_MEDIA_API, _u("2026-09-26T09:35:00Z"), fetch=boom)
    assert stats["pages_read"] == 0 and not stats["truncated"] and stats["incomplete"], stats
    fresh = [{"id": i, "title": "x", "publishFrom": 1_900_000_000_000, "imageUrl": f"https://x/{i}.jpg"}
             for i in range(3)]

    def second_fails(url):
        if url.endswith("page=0"):
            return {"content": fresh}
        raise ConnectionError("reset")
    got = apis.sweep_atp_media(full_name="Daniil Medvedev", surname="Medvedev", player_id="MM58",
                               event="Hangzhou", year="2026", **R2, fetch=second_fails,
                               head=lambda u: b"")
    assert got["pages_read"] == 1 and got["incomplete"], got
    assert not any("翻满" in n for n in got["notes"]) and any("没翻完" in n for n in got["notes"]), got["notes"]
    res = cch._sweep_api("atp-media", "ATP Media 照片接口", lambda **kw: got, cch.Query(player="Medvedev"))
    assert res.status == "ran" and res.partial and "没查完" in cch.status_line(res), cch.status_line(res)
    assert "——查空" not in cch.status_line(res) and "没查完 1" in cch.tally([res])
    assert "没查完" in cu.verdict_line([], [res]) and "查成的" not in cu.verdict_line([], [res])


def test_EXIF那条路_赛事名和在不在比赛_各自拦得住():
    """复审 nit：变异 M9（拆掉 `exif_bound_problems` 的赛事名那道）、M11（拆掉 EXIF 那条路的 NOT_IN_MATCH）
    原来都活着——渠道那头的标题过滤把 M9 藏住了，M11 是 WTA 那种嵌着「press conference」「practice」的图注
    落在决赛 end+45 窗口里时唯一的一道。这里直接喂 `metadata_problems`（绕开渠道那头）。"""
    ctx = _ctx_medvedev()
    base = dict(bind="exif", taken="2026:09:26 19:35:22", publish_utc="2026-09-26T13:35:35Z")
    ok = cu.Candidate("atp-media", "https://x/Daniil-Medvedev-012.jpg", caption="2026 Hangzhou Medvedev", **base)
    assert cu.metadata_problems(ok, ctx) == []
    other = cu.Candidate("atp-media", "https://x/Daniil-Medvedev-012.jpg", caption="2026 Chengdu Medvedev", **base)
    assert any("没有赛事" in p for p in cu.metadata_problems(other, ctx)), cu.metadata_problems(other, ctx)
    for words in ("speaks at a press conference", "practices on court", "warms up"):
        c = cu.Candidate("atp-media", "https://x/Daniil-Medvedev-012.jpg",
                         caption=f"2026 Hangzhou Medvedev · Daniil Medvedev {words} in Hangzhou", **base)
        assert any("不是这场单打在打的时刻" in p for p in cu.metadata_problems(c, ctx)), words


def test_决赛放宽_说明没写日期_真接口那种带上传时刻的也不放():
    """复审 nit：变异 M14（拆掉 `final_opponent_ok` 的日期要求）活着——原来的反例 Candidate 没有 `meta_utc`，
    而真接口的行带 `meta_utc＝publish_utc`：不写日期、只写「final」的图注会凭上传时刻过 `_upload_problems`。"""
    ctx = cu.match_context(replay.spec_of("jovic-stearns-guadalajara-2026-final"),
                           times=lambda _id: (_u("2026-09-19T23:05:00Z"), _u("2026-09-20T00:35:20Z")))
    cap = ("US Iva Jovic lifts the trophy after winning the women's singles final match of the WTA "
           "Guadalajara Open tournament at the Panamerican Tennis Center in Zapopan, Mexico. (Photo by AFP)")
    c = cu.Candidate("wta-photos", "https://x/t.jpg", caption=cap, meta_utc="2026-09-20T00:44:18Z",
                     publish_utc="2026-09-20T00:44:18Z")
    assert any("对手" in p for p in cu.metadata_problems(c, ctx)), cu.metadata_problems(c, ctx)


def test_年终总决赛和团体赛总决赛的小组赛不是决赛():
    """复审 nit：含「决赛」两个字就算——「年终总决赛 小组赛」会把 EXIF 窗口放到结束后 45 分钟、打开捧杯排序。"""
    for line in ("2026 WTA 年终总决赛 小组赛", "2026 ATP 年终总决赛 循环赛", "2026 比利·简·金杯总决赛 首轮",
                 "2026 戴维斯杯总决赛 1/4决赛"):
        assert not cu.is_final({"topbar": {"line1": line}}), line
    for rnd in ("ATP Finals Round Robin", "WTA Finals Group Stage", "Davis Cup Finals", "Finals Group B",
                "Finals - Round Robin"):
        assert not cu.is_final({"_match": {"round": rnd}}), rnd
    assert cu.is_final({"topbar": {"line1": "2026 WTA 年终总决赛 决赛"}})
    assert cu.is_final({"_match": {"round": "Final"}}) and cu.is_final({"_match": {"round": "Women's Singles Final"}})


def test_人查挂着等_带slug时绑上的要过图的闸才退出0(capsys):
    """复审 nit：`--wait-until` 点名层一过就打 ✅、退出 0——Bu-035（横幅上的字当成脸）、Coleman-Wong-010
    （认人 0.24）都会让等待提前结束。带 `--slug` 时过图的闸（`slug_verifier`），都没过接着等。"""
    import find_cover_photo as fcp  # noqa: PLC0415

    clock = [datetime(2026, 9, 26, 13, 20, tzinfo=UTC)]
    runs = {"n": 0}

    def fake_run(ch, q, o4=False):
        runs["n"] += 1
        raw = {"rows": [{"bound": True, "others": [], "restriction": "", "item_id": str(runs["n"]),
                         "title": "t", "name": "n.jpg", "wh": (5000, 3300), "publish_utc": "",
                         "bind_why": "w", "url": f"https://x/{runs['n']}.jpg"}], "pages_read": 1}
        return cch.ChannelResult(ch.key, ch.label, "ran", raw=raw, rows=[{}])

    verdicts = iter([("no", ["  - 认人没过"]), ("no", ["  - 睁眼没过"]), ("ok", ["  → 过了"])])
    q = cch.Query(player="Medvedev", tour="atp", start_utc=clock[0])
    orig = cch.run_channel
    cch.run_channel = fake_run
    try:
        got = fcp.wait_for_photo(q, "+60", now=lambda: clock[0], sleep=lambda s: None,
                                 verify=lambda res: next(verdicts))
        assert got == 0 and runs["n"] == 3, runs
        out = capsys.readouterr().out
        assert out.count("接着等") == 2 and "✅" not in out and "◎" in out, out
        # 本机没人脸模型：点名层过了照样退出 0，但明说认人没查
        assert fcp.wait_for_photo(q, "+60", now=lambda: clock[0], sleep=lambda s: None,
                                  verify=lambda res: ("unchecked", [])) == 0
        assert "认人／睁眼／钩子带没查" in capsys.readouterr().out
    finally:
        cch.run_channel = orig
    # 真的 verifier：Bu-035（录下来的真模型结果：最大那张「脸」是横幅上的字）过不了
    rec = next((u, v) for u, v in replay.load_faces().items() if u.endswith("Yunchaokete-Bu-035.jpg"))
    verify = fcp.slug_verifier("bu-majchrzak-hangzhou-2026-r2")
    row = cch._row(rec[0], caption="2026 Hangzhou Bu · Yunchaokete Bu", name="Yunchaokete-Bu-035.jpg",
                   meta_utc="2026-09-26T12:00:00Z", wh=tuple(rec[1]["size"]), bind="exif",
                   taken="2026:09:26 18:30:00", publish_utc="2026-09-26T12:00:00Z")
    res = cch.ChannelResult("atp-media", "ATP Media 照片接口", "ran", rows=[row])
    state, lines = verify(res, checker=lambda *a, **k: rec[1]["rep"],
                          fetch=lambda url: apis.blank_jpeg(*rec[1]["size"]))
    assert state == "no", (state, lines)
