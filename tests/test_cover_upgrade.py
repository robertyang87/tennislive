"""抽帧封面推出去之后，官方图一到自动换图重推（`tools/cover_upgrade.py`，O4）。

账号所有者 2026-09-27 选的 O4「自动换图重推」。来路是三次手动补救：
`alcaraz-fritz`（6b49049b，推送 4 分钟后官网就上传了本场实拍）、
`bu-majchrzak`（5beecfa6）、`zverev-deminaur`（1a4f92d3）——都是他在微信里看见、
开口抱怨，会话才去换。

这里的判据分三层，每层都拿**仓库里现成的夹具字节**现场合成候选图（不给仓库多添
一个字节）：

| 层 | 测什么 | 要不要人脸模型 |
|---|---|---|
| 找目标 | 近 48 小时推过、封面还是抽帧；换过的、认领了的不再找 | 不要 |
| 点名闸 | 说明／元数据里有人、有赛事、有**当地**同一天（和星期几） | 不要 |
| 图的闸 | 分辨率不放大、认得出是封面主角、睁眼、脸不进钩子带 | **要**（CI 上必须在） |

⚠️ 模型不在就跳过——CI 上不许跳（和 `test_face_checks.py` 同一个口径）。
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

import cover_upgrade as cu  # noqa: E402

FACES = ROOT / "tests" / "fixtures" / "faces"
WONG_FRAME = FACES / "wong-vallejo-cover-frame-689.8.jpg"          # 1920×1080，黄泽林睁眼
RUUD_CLOSED = FACES / "ruud-cerundolo-poster-9380e58f-eyes-closed.jpg"  # 1080×1440，鲁德闭眼

#: flashscore `dc_1_hheFZ9KN` 2026-09-27 实测原文（拉沃尔杯首日霍达尔—布勃利克）
DC_FEED = ("DA÷3¬DZ÷3¬DB÷3¬DD÷1790365740¬AW÷1¬DC÷1790360700¬DS÷0¬DE÷2¬DF÷0¬"
           "DG÷2¬DH÷0¬DI÷-1¬DK÷1790365749¬DL÷3¬~")

SLUG = "wong-vallejo-hangzhou-2026-r2"
#: 杭州 2026-09-26 北京 20:00 开打的一场（北京就是当地）
START = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 9, 27, 3, 0, tzinfo=timezone.utc)        # 北京 9/27 11:00
AP_CAPTION = ("Coleman Wong of Hong Kong reacts after winning a point against Adolfo "
              "Daniel Vallejo during the Hangzhou Open in Hangzhou, China, on "
              "Saturday, Sept. 26, 2026. (AP Photo)")


@pytest.fixture
def model():
    import face_checks  # noqa: PLC0415

    try:
        return face_checks.load()
    except face_checks.ModelUnavailable as exc:
        if os.environ.get("CI"):
            pytest.fail(f"CI 上人脸模型必须在（ci.yml「备好人脸模型」那一步）：{exc}")
        pytest.skip(f"本机没有人脸模型（python tools/face_checks.py fetch）：{exc}")


def _jpeg(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def _photo(kind: str) -> bytes:
    """现场合成的候选图——全从仓库里已有的夹具字节来。"""
    from PIL import Image  # noqa: PLC0415

    if kind == "ruud-closed":
        return RUUD_CLOSED.read_bytes()
    with Image.open(WONG_FRAME) as raw:
        frame = raw.convert("RGB")
    if kind == "low-res":
        return _jpeg(frame)                                   # 1920×1080：铺满要放大 1.33
    big = frame.resize((2560, 1440), Image.LANCZOS)            # 铺满正好 1.00×，脸在上半截
    if kind == "ok":
        return _jpeg(big)
    if kind == "face-low":                                     # 同一张脸往下挪 720px
        canvas = Image.new("RGB", (2560, 1440), (40, 60, 40))
        canvas.paste(big, (0, 720))
        return _jpeg(canvas)
    raise ValueError(kind)


def _spec(subject: str = "黄泽林", **cover_extra) -> dict:
    return {
        "slug": SLUG,
        "topbar": {"line1": "2026 ATP250 杭州 第二轮", "line2": "黄泽林 7-6(2) 4-6 6-3 巴列霍"},
        "cover": {
            "eyebrow": "赛场之上", "layout": "solo", "subject": subject,
            "hook": "前10次机会全落空\n黄泽林挺进8强",
            "matchup": [{"name": "黄泽林", "name_en": "Coleman Wong"},
                        {"name": "巴列霍", "name_en": "Adolfo Daniel Vallejo"}],
            "portrait": {"frame_at": 689.8, "focus": 0.58, "focus_y": 0.5, "zoom": 1.0,
                         "_frame_why": "抽帧"},
            **cover_extra,
        },
        "_match": {"flashscore_id": "x0TAQY2b"},
        "stats": {"a": {"headshot": "assets/players/headshots/atp-W0BH.png"},
                  "b": {"headshot": "assets/players/headshots/atp-V0DP.png"}},
        "push": {"auto": True},
    }


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True).stdout


def _repo(tmp_path: Path, specs: dict[str, tuple[dict, datetime]],
          outputs: dict[str, list[str]] | None = None) -> Path:
    """一个最小的仓库：发布账本 ＋ spec ＋（可选）output 下的产物，提交进 git。"""
    repo = tmp_path / "repo"
    for slug, (spec, sent) in specs.items():
        led = repo / "data" / "reel_publish_ledger" / f"{slug}.json"
        led.parent.mkdir(parents=True, exist_ok=True)
        led.write_text(json.dumps({"slug": slug, "attempts": [
            {"status": "sent", "at": sent.strftime("%Y-%m-%dT%H:%M:%SZ")}]}), "utf-8")
        path = repo / "specs" / "reels" / f"{slug}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", "utf-8")
    for rel in [p for paths in (outputs or {}).values() for p in paths]:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("{}\n", "utf-8")
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
    return repo


def _one(candidate: cu.Candidate, calls: list | None = None):
    def sweeps_for(ctx):
        if calls is not None:
            calls.append(ctx.slug)
        return [("测试渠道", lambda: [candidate])]
    return sweeps_for


def _ap(url: str = "https://assets.apnews.com/x/wong.jpg", caption: str = AP_CAPTION):
    return cu.Candidate("ap", url, caption=caption, page="https://apnews.com/article/x")


def _run(repo: Path, blob: bytes, candidate=None, *, apply=True, calls=None, fetched=None):
    def fetch(url):
        if fetched is not None:
            fetched.append(url)
        return blob
    return cu.run(repo, NOW, apply=apply, sweeps_for=_one(candidate or _ap(), calls),
                  times=lambda _id: (START, START + timedelta(hours=2)),
                  fetch=fetch, final_gate=lambda spec: None)


# ---------------------------------------------------------------- 找目标（不要模型）

def test_找目标只要近48小时推过且封面还是抽帧的(tmp_path):
    recent = NOW - timedelta(hours=10)
    image = _spec()
    image["cover"]["portrait"] = {"image": "assets/reel/x.jpg"}
    kept = _spec()
    kept["cover"]["portrait"][cu.KEEP_FRAME_WHY] = "账号所有者当面点过就用这一帧"
    story = _spec()
    story["cover"]["eyebrow"] = "网球有故事"
    repo = _repo(tmp_path, {
        "frame-recent": (_spec(), recent),
        "image-recent": (image, recent),
        "frame-old": (_spec(), NOW - timedelta(hours=49)),
        "frame-kept": (kept, recent),
        "frame-done": (_spec(), recent),
        "frame-story": (story, recent),
    })
    (repo / cu.LEDGER).write_text(json.dumps(
        {"upgrades": {"frame-done": {"status": "upgraded"}}}), "utf-8")
    found, notes = cu.targets(repo, NOW)
    assert [t.slug for t in found] == ["frame-recent"], found
    text = "\n".join(notes)
    assert "frame-done" in text and "只换一次" in text, "换过的要说出为什么不查"
    assert "frame-kept" in text and cu.KEEP_FRAME_WHY in text, "认领了这一帧的要说出来"
    assert "frame-story" in text and "赛场之上" in text


# ---------------------------------------------------------------- 点名闸（不要模型）

def _ctx(**kw) -> cu.MatchContext:
    ctx = cu.MatchContext(slug=SLUG, subject_zh="黄泽林", subject_en="Coleman Wong",
                          surname="wong", event_en="Hangzhou", tz="Asia/Shanghai",
                          match_dates={date(2026, 9, 26)})
    for k, v in kw.items():
        setattr(ctx, k, v)
    return ctx


def test_说明点名三件事_人赛事日期缺一不换():
    ctx = _ctx()
    assert cu.metadata_problems(_ap(), ctx) == []
    wrong_day = _ap(caption=AP_CAPTION.replace("Sept. 26", "Sept. 24").replace("Saturday", "Thursday"))
    assert any("2026-09-24" in p for p in cu.metadata_problems(wrong_day, ctx)), \
        "前一轮的图（说明写着 9/24）也放进来了——认人认得出是他，认不出是哪一场"
    no_name = _ap(caption=AP_CAPTION.replace("Coleman Wong", "Juncheng Shang"))
    assert any("Coleman Wong" in p for p in cu.metadata_problems(no_name, ctx))
    other_event = _ap(caption=AP_CAPTION.replace("Hangzhou", "Chengdu"))
    assert any("Hangzhou" in p for p in cu.metadata_problems(other_event, ctx))
    # 说明写的星期几和这场对不上（资料图最常见的样子：图注只写「on Friday night」）
    weekday = cu.Candidate("event-site", "https://e/x.jpg", caption="Coleman Wong on Friday night",
                           meta_date="2026-09-26", event_owned=True)
    assert any("friday" in p for p in cu.metadata_problems(weekday, ctx))
    # 赛事自己的媒体库：赛事由站点担保，日期看元数据
    owned = cu.Candidate("event-site", "https://e/x.jpg", caption="Coleman Wong celebrates",
                         meta_date="2026-09-26", event_owned=True)
    assert cu.metadata_problems(owned, ctx) == []
    owned.meta_date = "2026-09-25"
    assert any("元数据日期" in p for p in cu.metadata_problems(owned, ctx))
    owned.meta_date = ""
    assert any("都没有日期" in p for p in cu.metadata_problems(owned, ctx))
    # WTA 文件名里是下划线——不先抹掉的话 \bswiatek\b 恒不命中
    wta = cu.Candidate(
        "wta", "https://photoresources.wtatennis.com/photo-resources/2026/08/16/u/"
               "Iga_Swiatek_-_Cincinnati_Open_2026_-_Day_6-DSC_2955.jpg?width=4000",
        name="Iga_Swiatek_-_Cincinnati_Open_2026_-_Day_6-DSC_2955.jpg")
    assert cu.metadata_problems(wta, _ctx(surname="swiatek", subject_en="Iga Swiatek",
                                          event_en="Cincinnati",
                                          match_dates={date(2026, 8, 16)})) == []


def test_说明里的日期几种写法都认得():
    assert cu.caption_dates("on Thursday, Aug. 13, 2026. (AP)") == {date(2026, 8, 13)}
    assert cu.caption_dates("Saturday, August 15, 2026") == {date(2026, 8, 15)}
    assert cu.caption_dates("on Sept. 26, 2026") == {date(2026, 9, 26)}
    assert cu.caption_dates("LONDON - SEPTEMBER 24: ... on September 24, 2026 in London") \
        == {date(2026, 9, 24)}
    assert cu.caption_dates("15 August 2026") == {date(2026, 8, 15)}
    assert cu.caption_dates("USTA1234_20260901_Z9.jpg") == {date(2026, 9, 1)}
    # 14 位的时间戳不是日期（拉沃尔杯的文件名 `…_20260924123713.jpg`）
    assert cu.caption_dates("TD1_4251_3uk3Lh7f_20260924123713.jpg") == set()


def test_时区不知道就判不了同一天_不换():
    spec = _spec()
    ctx = cu.match_context(spec, times=lambda _id: (START, START + timedelta(hours=2)))
    assert not ctx.problems and ctx.tz == "Asia/Shanghai"
    assert ctx.match_dates == {date(2026, 9, 26)}
    assert ctx.opponent_surname == "vallejo"
    # 拉沃尔杯：flashscore 原文 → 伦敦当地 9/25
    laver = _spec()
    laver["topbar"]["line1"] = "2026 拉沃尔杯 首日"
    ctx = cu.match_context(laver, times=lambda _id: cu.parse_dc_feed(DC_FEED))
    assert ctx.event_en == "Laver Cup" and ctx.site == "lavercup.com"
    assert ctx.match_dates == {date(2026, 9, 25)}, ctx.match_dates
    # 夜场跨过当地午夜：两天都算这一场
    late = datetime(2026, 9, 26, 15, 30, tzinfo=timezone.utc)      # 北京 23:30 开打
    ctx = cu.match_context(spec, times=lambda _id: (late, late + timedelta(hours=2)))
    assert ctx.match_dates == {date(2026, 9, 26), date(2026, 9, 27)}
    # 认得出赛事、却不知道它在哪个时区（自动草稿带来的英文名，表里没有）：不换，
    # 别退回 UTC 或一个两天宽的窗口——同一个人前后两天各打一场时会放进别场的图
    no_tz = _spec()
    no_tz["_production"] = {"event": "Nowhere Open"}
    ctx = cu.match_context(no_tz, times=lambda _id: (START, None))
    assert ctx.event_en == "Nowhere Open" and not ctx.match_dates
    assert any("时区不在" in p for p in ctx.problems), ctx.problems
    # 认不出的赛事、开赛时刻取不到：不换，并说出为什么
    unknown = _spec()
    unknown["topbar"]["line1"] = "2026 ATP250 某个没登记的城市 第二轮"
    assert any("认不出赛事" in p for p in cu.match_context(unknown).problems)
    def boom(_id):
        raise RuntimeError("HTTP 403")
    assert any("开赛时刻取不到" in p for p in cu.match_context(spec, times=boom).problems)
    doubles = _spec(subject="阿尔卡拉斯 / 门西克")
    assert any("双打" in p for p in cu.match_context(doubles).problems)


# ---------------------------------------------------------------- 铺图几何（不要模型）

def test_铺图几何_脸落进钩子带就推zoom_推不动就不换():
    top = cu.hook_top()
    ok = cu.place_face(2560, 1440, (1275, 67, 1652, 568), top)
    assert ok["ok"] and ok["zoom"] == 1.0 and ok["face_out"][3] <= top, ok
    assert 0.55 < ok["focus"] < 0.7, "脸横向没放到正中"
    # 2560×1440 铺满正好 1.00×：脸低了也不许靠放大去躲（一放大就过不了分辨率）
    low = cu.place_face(2560, 1440, (1275, 787, 1652, 1288), top)
    assert not low["ok"] and "钩子带" in low["why"] and "放大" in low["why"], low
    # 原图够大就能推 zoom：4000×2667 里脸在 45%~60%，zoom 1.0 落进钩子带，推到 1.2 躲开
    big = cu.place_face(4000, 2667, (1800, 1200, 2200, 1600), top)
    assert big["ok"] and big["zoom"] > 1.0 and big["fill"] >= 1.0, big
    assert big["face_out"][3] <= top


def test_铺满倍数和封面闸是同一个式子(tmp_path):
    """`fill_ratio` 挑图、`cover_photo_problem` 把关——两处必须同一个式子，
    否则挑出来的图过不了闸（或者闸放过了挑图没算到的放大）。"""
    from PIL import Image  # noqa: PLC0415

    sys.path.insert(0, str(ROOT / "tools"))
    import build_match_reel as reel  # noqa: PLC0415

    for (w, h), zoom in (((1080, 1440), 1.0), ((1079, 1440), 1.0), ((2560, 1440), 1.0),
                         ((2560, 1439), 1.0), ((1320, 1760), 1.2), ((1320, 1760), 1.3)):
        path = tmp_path / f"{w}x{h}.jpg"
        Image.new("RGB", (w, h), (90, 90, 90)).save(path)
        spec = {"cover": {"portrait": {"image": str(path), "zoom": zoom}}}
        assert (reel.cover_photo_problem(spec) is None) == (cu.fill_ratio(w, h, zoom) >= 1.0), \
            (w, h, zoom)


def test_换出来的portrait过得了正式的封面闸(tmp_path):
    """机器写的 `cover.portrait` 形状，拿**真的** `validate_spec` ＋ `cover_photo_problem`
    过一遍（去掉 slug，不走豁免表）——挑图那套算得再好，正式的闸不认也是白换。"""
    from PIL import Image  # noqa: PLC0415

    spec = json.loads((ROOT / "specs" / "reels" / f"{SLUG}.json").read_text("utf-8"))
    ctx = _ctx()
    for (w, h), expect_ok in (((2560, 1440), True), ((1920, 1080), False)):
        path = tmp_path / f"{w}.jpg"
        Image.new("RGB", (w, h), (90, 90, 90)).save(path)
        chosen = {"candidate": _ap(), "evidence": {
            "size": [w, h],
            "layout": {"zoom": 1.0, "focus": 0.6, "focus_y": 0.5, "face_out": [300, 60, 700, 560],
                       "fill": cu.fill_ratio(w, h, 1.0)},
            "face": {"similarity": {"黄泽林": 0.52}, "ear": 0.31}}}
        spec["cover"]["portrait"] = cu.upgraded_portrait(
            {"frame_at": 689.8}, chosen, ctx, str(path))
        problem = cu._final_gate(spec)
        assert (problem is None) == expect_ok, problem


# ---------------------------------------------------------------- 图的闸（要模型）

def test_官方图全过闸就换_写图改spec删同日的pushed并记账(tmp_path, model):
    today = cu.beijing_today(NOW).isoformat()
    outdir = f"output/{today}/reel/{SLUG}"
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))},
                 {SLUG: [f"{outdir}/render.json", f"{outdir}/pushed.json"]})
    blob = _photo("ok")
    got = _run(repo, blob)
    assert got["upgraded"] == [SLUG], "\n".join(got["report"])
    spec = json.loads((repo / "specs" / "reels" / f"{SLUG}.json").read_text("utf-8"))
    art = spec["cover"]["portrait"]
    assert art["image"] == f"assets/reel/{SLUG}-official.jpg" and "frame_at" not in art
    assert (repo / art["image"]).read_bytes() == blob, "原图字节要原样存，不重编码"
    assert art["zoom"] == 1.0 and 0.55 < art["focus"] < 0.7
    assert "Hangzhou" in art["_gates"] and "黄泽林" in art["_gates"] and AP_CAPTION[:40] in art["_why"]
    assert not _git(repo, "ls-files", f"{outdir}/pushed.json").strip(), \
        "同日重渲会撞上的 pushed.json 没删——合并后不会重推（09-22 那条）"
    entry = json.loads((repo / cu.LEDGER).read_text("utf-8"))["upgrades"][SLUG]
    assert entry["status"] == "upgraded" and entry["removed_markers"] == [f"{outdir}/pushed.json"]
    assert entry["previous_portrait"]["frame_at"] == 689.8
    assert entry["gates"]["face"]["name"] == "黄泽林" and entry["gates"]["face"]["eyes"] == "open"


def test_一个slug只换一次_第二趟连查都不查(tmp_path, model):
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))})
    calls: list = []
    first = _run(repo, _photo("ok"), calls=calls)
    assert first["upgraded"] == [SLUG] and calls == [SLUG]
    spec_after = (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes()
    # 就算有人把封面又改回抽帧，账里记着换过，这条也不再动
    reverted = json.loads(spec_after)
    reverted["cover"]["portrait"] = _spec()["cover"]["portrait"]
    (repo / "specs" / "reels" / f"{SLUG}.json").write_text(
        json.dumps(reverted, ensure_ascii=False, indent=2) + "\n", "utf-8")
    second = _run(repo, _photo("ok"), calls=calls)
    assert second["upgraded"] == [] and calls == [SLUG], "第二趟又去查了"
    assert any("只换一次" in line for line in second["report"]), second["report"]


def test_日期对不上不下图(tmp_path):
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))})
    fetched: list = []
    got = _run(repo, b"", _ap(caption=AP_CAPTION.replace("Sept. 26", "Sept. 25")
                              .replace("Saturday", "Friday")), fetched=fetched)
    assert got["upgraded"] == [] and fetched == [], "元数据闸没过还去下图了"
    assert any("2026-09-25" in line for line in got["report"])


@pytest.mark.parametrize("kind, subject, headshots, expect", [
    ("low-res", "黄泽林", None, "分辨率不够"),
    ("ok", "巴列霍", None, "认出来是黄泽林"),                   # 认成对手
    ("ok", "黄泽林", {"a": {}, "b": {}}, "认人没过（unknown）"),   # 没有官方头像：不敢判
    ("face-low", "黄泽林", None, "钩子带"),
])
def test_过不了闸的不换(tmp_path, model, kind, subject, headshots, expect):
    spec = _spec(subject=subject)
    if subject == "巴列霍":
        spec["cover"]["matchup"][1]["name_en"] = "Adolfo Daniel Vallejo"
        cand = _ap(caption=AP_CAPTION.replace("Coleman Wong of Hong Kong reacts",
                                              "Adolfo Daniel Vallejo reacts"))
    else:
        cand = _ap()
    if headshots is not None:
        spec["stats"] = headshots
        spec["cover"]["matchup"] = [{"name": "黄泽林甲", "name_en": "Coleman Wong"},
                                    {"name": "巴列霍乙", "name_en": "Adolfo Daniel Vallejo"}]
        spec["cover"]["subject"] = "黄泽林甲"
    repo = _repo(tmp_path, {SLUG: (spec, NOW - timedelta(hours=6))})
    before = (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes()
    got = _run(repo, _photo(kind), cand)
    assert got["upgraded"] == [], "\n".join(got["report"])
    assert any(expect in line for line in got["report"]), "\n".join(got["report"])
    assert (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes() == before
    assert not (repo / cu.LEDGER).exists(), "没换也记了一笔「upgraded」"


def test_闭眼的不换(tmp_path, model):
    spec = _spec(subject="鲁德")
    spec["topbar"]["line1"] = "2026 拉沃尔杯 首日"
    spec["cover"]["matchup"] = [{"name": "鲁德", "name_en": "Casper Ruud"},
                                {"name": "塞伦多洛", "name_en": "Francisco Cerundolo"}]
    spec["stats"] = {"a": {"headshot": "assets/players/headshots/atp-RH16.png"},
                     "b": {"headshot": "assets/players/headshots/atp-C0AU.png"}}
    repo = _repo(tmp_path, {SLUG: (spec, NOW - timedelta(hours=6))})
    cand = cu.Candidate("event-site", "https://lavercup.com/wp-content/uploads/2026/09/r.jpg",
                        caption="Casper Ruud on Saturday", meta_date="2026-09-26",
                        event_owned=True)
    got = cu.run(repo, NOW, apply=True, sweeps_for=_one(cand),
                 times=lambda _id: (datetime(2026, 9, 26, 18, 0, tzinfo=timezone.utc), None),
                 fetch=lambda _url: _photo("ruud-closed"), final_gate=lambda spec: None)
    assert got["upgraded"] == []
    assert any("睁眼没过" in line for line in got["report"]), "\n".join(got["report"])


def test_人脸模型不可用就不换(tmp_path):
    """大声降级：模型加载不了＝认人和睁眼都没查，**不许当成通过**。"""
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))})
    got = cu.run(repo, NOW, apply=True, sweeps_for=_one(_ap()),
                 times=lambda _id: (START, None), fetch=lambda _url: _photo("ok"),
                 checker=lambda img, exp: {"status": "unavailable", "error": "没装 onnxruntime"},
                 final_gate=lambda spec: None)
    assert got["upgraded"] == []
    assert any("人脸模型不可用" in line for line in got["report"])


def test_换完过不了正式的封面闸就全部退回(tmp_path, model):
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))})
    before = (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes()
    got = cu.run(repo, NOW, apply=True, sweeps_for=_one(_ap()),
                 times=lambda _id: (START, None), fetch=lambda _url: _photo("ok"),
                 final_gate=lambda spec: "封面大图撑不满卡片")
    assert got["upgraded"] == [] and got["reverted"] == [SLUG]
    assert any(line.startswith("::error::") and "已退回" in line for line in got["report"])
    assert (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes() == before
    assert not (repo / "assets" / "reel" / f"{SLUG}-official.jpg").exists()
    assert not (repo / cu.LEDGER).exists()


# ---------------------------------------------------------------- 重推（不要模型）

def test_只删同日那一格的pushed(tmp_path):
    old = f"output/2026-09-26/reel/{SLUG}"
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW)},
                 {SLUG: [f"{old}/render.json", f"{old}/pushed.json"]})
    assert cu.beijing_today(NOW) == date(2026, 9, 27)
    assert cu.stale_markers(repo, SLUG, NOW) == [], \
        "最晚那一格是 9/26，重渲落进 9/27——删它没必要（账本里历史还在，但别动不相干的）"
    today = f"output/2026-09-27/reel/{SLUG}"
    for rel in (f"{today}/render.json", f"{today}/pushed.json"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("{}\n", "utf-8")
    _git(repo, "add", f"{today}/render.json")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "r")
    assert cu.stale_markers(repo, SLUG, NOW) == [], "没提交的 pushed.json 本来就不算数"
    _git(repo, "add", f"{today}/pushed.json")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "p")
    assert cu.stale_markers(repo, SLUG, NOW) == [f"{today}/pushed.json"]


def test_自动换过图的slug从抽帧豁免表里减掉(tmp_path):
    import inspect  # noqa: PLC0415

    import build_match_reel as reel  # noqa: PLC0415

    ledger = tmp_path / "cover_upgrades.json"
    ledger.write_text(json.dumps({"upgrades": {
        "a": {"status": "upgraded"}, "b": {"status": "reverted"}, "c": "坏行"}}), "utf-8")
    assert reel.auto_upgraded_frame_covers(ledger) == {"a"}
    assert reel.auto_upgraded_frame_covers(tmp_path / "没有.json") == frozenset(), \
        "账读不到就当没换过——豁免照旧，闸不会因此变松"
    src = inspect.getsource(reel)
    assert ("OWNER_APPROVED_FRAME_COVERS = OWNER_APPROVED_FRAME_COVERS - "
            "auto_upgraded_frame_covers()") in src, "表没接上那份账——换完图 CI 会红在豁免表自检上"
    # 账不许撒谎：记了 upgraded 的，spec 真的已经是图
    real = ROOT / cu.LEDGER
    rows = json.loads(real.read_text("utf-8"))["upgrades"] if real.is_file() else {}
    for slug, row in rows.items():
        if row.get("status") != "upgraded":
            continue
        spec = json.loads((ROOT / "specs" / "reels" / f"{slug}.json").read_text("utf-8"))
        assert not cu.is_frame_cover(spec), f"{slug} 记着换过图，spec 还是抽帧"


def test_定时班次的接线():
    import yaml  # noqa: PLC0415

    path = ROOT / ".github" / "workflows" / "reel-cover-upgrade.yml"
    wf = yaml.safe_load(path.read_text("utf-8"))
    triggers = wf.get(True) or wf.get("on")
    assert "schedule" in triggers and "workflow_dispatch" in triggers
    steps = [s for job in wf["jobs"].values() for s in job["steps"]]
    runs = [str(s.get("run") or "") for s in steps]
    at = {key: next(i for i, r in enumerate(runs) if key in r) for key in (
        "tools/face_checks.py fetch", "tools/cover_upgrade.py",
        "push_with_rebase_retry main", "gh workflow run match-reel.yml")}
    assert at["tools/face_checks.py fetch"] < at["tools/cover_upgrade.py"] \
        < at["push_with_rebase_retry main"] < at["gh workflow run match-reel.yml"], (
        "顺序：备好模型 → 换 → spec 推上 main → 才派发 render（render 只认 main 上的 spec）")
    assert "--apply" in runs[at["tools/cover_upgrade.py"]], "定时班次要真换，不是只报告"
    dispatch = runs[at["gh workflow run match-reel.yml"]]
    assert "mode=render" in dispatch and "push=true" in dispatch, "换完要重渲重推"
    commit = runs[at["push_with_rebase_retry main"]]
    assert "git add --sparse" in commit, "assets/reel 不在稀疏检出里，裸 git add 会静默丢图"
