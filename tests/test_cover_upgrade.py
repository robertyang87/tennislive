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
import re
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
    big = frame.resize((2560, 1440), Image.LANCZOS)            # 铺满正好 1.00×，脸在 y67~568
    if kind == "ok":                                           # 往下挪 150px：脸在 y217~718，
        canvas = Image.new("RGB", (2560, 1440), (40, 60, 40))  # 台头（0~170）和钩子（790 起）之间
        canvas.paste(big, (0, 150))
        return _jpeg(canvas)
    if kind == "face-high":                                    # 原样：脸上沿 y67 压进台头（N5）
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


def _ap(url: str = "https://assets.apnews.com/x/5f0c2a9e.jpg", caption: str = AP_CAPTION):
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
                          surname="wong", opponent_surname="vallejo", event_en="Hangzhou",
                          tz="Asia/Shanghai", start_utc=START,
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
    weekday = cu.Candidate("event-site", "https://e/x.jpg",
                           caption="Coleman Wong beats Vallejo on Friday night",
                           meta_date="2026-09-26", meta_utc="2026-09-26T13:40:00",
                           event_owned=True)
    assert any("friday" in p for p in cu.metadata_problems(weekday, ctx))
    # 赛事自己的媒体库：赛事由站点担保，日期看元数据（上传时刻要晚于开赛，见 B3 那条）
    owned = cu.Candidate("event-site", "https://e/x.jpg",
                         caption="Coleman Wong celebrates against Vallejo",
                         meta_date="2026-09-26", meta_utc="2026-09-26T13:40:00",
                         event_owned=True)
    assert cu.metadata_problems(owned, ctx) == []
    # 当地哪一天按上传时刻（UTC）换算到赛事时区，不看站点时区的 `date`（评审第二轮）
    owned.meta_date, owned.meta_utc = "2026-09-26", "2026-09-27T13:40:00"
    assert any("元数据日期 2026-09-27" in p for p in cu.metadata_problems(owned, ctx))
    owned.meta_date, owned.meta_utc = "", ""
    assert any("都没有日期" in p for p in cu.metadata_problems(owned, ctx))
    # WTA 文件名里是下划线——不先抹掉的话 \bswiatek\b 恒不命中。点名那一半认得出；
    # 而图床文件名不写对手、URL 里只有上传的日子没有时刻，所以这一张**不换**（B1/B3）
    wta = cu.Candidate(
        "wta", "https://photoresources.wtatennis.com/photo-resources/2026/08/16/u/"
               "Iga_Swiatek_-_Cincinnati_Open_2026_-_Day_6-DSC_2955.jpg?width=4000",
        name="Iga_Swiatek_-_Cincinnati_Open_2026_-_Day_6-DSC_2955.jpg")
    got = cu.metadata_problems(wta, _ctx(surname="swiatek", subject_en="Iga Swiatek",
                                         opponent_surname="gauff", event_en="Cincinnati",
                                         tz="America/New_York",
                                         match_dates={date(2026, 8, 16)}))
    assert not any("Iga Swiatek" in p or "赛事" in p for p in got), got
    assert any("对手" in p for p in got) and any("上传时刻" in p for p in got), got


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


AP_NEWS_CONF = ("Coleman Wong of Hong Kong speaks during a news conference after his "
                "second-round match at the Hangzhou Open in Hangzhou, China, on "
                "Saturday, Sept. 26, 2026. (AP Photo)")


@pytest.mark.parametrize("caption, expect", [
    # 评审 B1 原样复现的两条：认人认得出是他，认不出他在开发布会／在训练
    (AP_NEWS_CONF, "对手"),
    (AP_NEWS_CONF.replace("match at", "match against Adolfo Daniel Vallejo at"), "news conference"),
    (AP_CAPTION.replace("reacts after winning a point against", "practices ahead of his match against"),
     "practices"),
    (AP_CAPTION.replace("reacts after winning a point", "warms up before his match"), "warms"),
    (AP_CAPTION.replace("reacts after winning a point", "signs autographs after his win"), "autographs"),
    (AP_CAPTION.replace("reacts after winning a point", "arrives for his match"), "arrives"),
    (AP_CAPTION.replace("reacts after winning a point", "poses for a portrait before playing"), "poses"),
    (AP_CAPTION.replace("reacts after winning a point", "talks in an interview after playing"), "interview"),
    (AP_CAPTION.replace("reacts after winning a point", "plays a men's doubles match"), "doubles"),
    (AP_CAPTION.replace("reacts after winning a point", "plays a mixed match"), "mixed"),
    (AP_CAPTION.replace("reacts after winning a point", "during a press conference after beating"),
     "press conference"),
    (AP_CAPTION.replace("reacts after winning a point", "during a training session with"), "training"),
    # 评审第二轮：真 metadata_problems 在 wong-vallejo 上复现过、原来全过的六条——
    # 全名、对手、Hangzhou Open、Sept. 26, 2026 全在，拍的是记者会／定妆／赛前练球
    (AP_CAPTION.replace("reacts after winning a point against Adolfo Daniel Vallejo",
                        "speaks to the media after his second-round win over Adolfo Daniel Vallejo"),
     "media"),
    (AP_CAPTION.replace("reacts after winning a point against", "talks to reporters after his win against"),
     "reporters"),
    (AP_CAPTION.replace("reacts after winning a point against",
                        "attends a media session after beating"), "media"),
    (AP_CAPTION.replace("reacts after winning a point against", "at a photocall before facing"),
     "photocall"),
    (AP_CAPTION.replace("reacts after winning a point against", "headshot, before his match against"),
     "headshot"),
    (AP_CAPTION.replace("reacts after winning a point against",
                        "hits during a session ahead of his match against"), "hits during a session"),
    # 评审第三轮 nit：团体赛里在场边看队友打——全名、对手、日期全在
    (AP_CAPTION.replace("reacts after winning a point against",
                        "reacts on the bench as teammate Zhang Zhizhen plays"), "on the bench"),
    (AP_CAPTION.replace("reacts after winning a point against", "cheers on teammate Zhang against"),
     "cheers on"),
    (AP_CAPTION.replace("reacts after winning a point against", "watches on as his teammate plays"),
     "watches on as"),
    (AP_CAPTION.replace("reacts after winning a point against", "watches from the sidelines as Zhang plays"),
     "watches from"),
    # 评审第四轮 nit：收窄之后，看别人打的那几种照样拦
    (AP_CAPTION.replace("reacts after winning a point against", "reacts on the sideline as teammate Zhang plays"),
     "on the sideline"),
    (AP_CAPTION.replace("reacts after winning a point against", "cheers on his teammate Zhang against"),
     "cheers on his teammate"),
])
def test_说明不点对手或写的不是比赛本身_不换(caption, expect):
    """B1：同一个人在同一站不止一个时刻——发布会、训练、双打（拉沃尔杯单打双打都打）。
    认人闸分不开，只能靠说明自己的字：**要点名对手**，而且不许是那几类场合。"""
    got = cu.metadata_problems(_ap(caption=caption), _ctx())
    assert any(expect in p for p in got), got
    assert cu.metadata_problems(_ap(), _ctx()) == [], "对照组：AP 的比赛图（点了对手）要过"
    # 对照组：AP 比赛图常写「during the night session」——裸的 session 不许拦
    night = AP_CAPTION.replace("during the Hangzhou Open", "during the night session of the Hangzhou Open")
    assert cu.metadata_problems(_ap(caption=night), _ctx()) == []
    # 对照组：他自己在打的那一刻——裸的 cheers／watches、「cheers on court」不许拦
    # 评审第四轮 nit（原来收宽了）：「cheers on <场地>」「down the sideline」也是他自己在打
    for mine in ("cheers after winning a point against", "cheers on court after beating",
                 "watches the ball during his match against",
                 "cheers on centre court after winning a point against",
                 "cheers on Arthur Ashe Stadium after winning a point against",
                 "hits a forehand down the sideline against"):
        own = AP_CAPTION.replace("reacts after winning a point against", mine)
        assert cu.metadata_problems(_ap(caption=own), _ctx()) == [], mine


def test_拉沃尔杯BS2_8696那张的说明过得了点名闸():
    """B1 的反方向：6b49049b 手动换上的那张（官网 WP 媒体库 21299，20:57:38Z 上传），
    图注写的是「takes the singles against Fritz on Saturday night」——对手、单打、星期都在。
    `singles` 不许被当成 `doubles` 那一类拦掉。"""
    spec = json.loads((ROOT / "specs" / "reels" / "alcaraz-fritz-laver-cup-2026.json")
                      .read_text("utf-8"))
    start = datetime(2026, 9, 26, 18, 0, tzinfo=timezone.utc)
    ctx = cu.match_context(spec, times=lambda _id: (start, start + timedelta(hours=2)))
    assert not ctx.problems and ctx.opponent_surname == "fritz" and ctx.site == "lavercup.com"
    cand = cu.Candidate(
        "event-site", "https://lavercup.com/wp-content/uploads/2026/09/BS2_8696.jpg",
        caption="Carlos Alcaraz Carlos Alcaraz takes the singles against Fritz on Saturday night.",
        name="BS2_8696.jpg", meta_date="2026-09-26", meta_utc="2026-09-26T20:57:38",
        event_owned=True)
    assert cu.metadata_problems(cand, ctx) == []


def test_同姓的兄弟姐妹要点到名_不能只认姓():
    """B4：普利斯科娃是同卵双胞胎，塞伦多洛、西西帕斯是兄弟俩——认人闸分不开，
    说明里只有姓不换；名字的顺序不管（中文名两种英文写法都有）。"""
    ctx = _ctx(subject_zh="普利斯科娃", subject_en="Karolina Pliskova", surname="pliskova",
               opponent_surname="bejlek")
    base = ("{} of Czech Republic returns a shot against Sara Bejlek during the Hangzhou "
            "Open on Saturday, Sept. 26, 2026. (AP Photo)")
    assert cu.metadata_problems(_ap(caption=base.format("Karolina Pliskova")), ctx) == []
    twin = cu.metadata_problems(_ap(caption=base.format("Kristyna Pliskova")), ctx)
    assert any("karolina" in p for p in twin), twin
    bare = cu.metadata_problems(_ap(caption=base.format("Pliskova")), ctx)
    assert any("karolina" in p for p in bare), bare
    zhang = _ctx(subject_en="Zhizhen Zhang", surname="zhang", opponent_surname="vallejo")
    assert cu.metadata_problems(_ap(caption=AP_CAPTION.replace(
        "Coleman Wong of Hong Kong", "Zhang Zhizhen of China")), zhang) == []


def test_中文的_production_event_不许把赛事认成美网():
    """B2：`_key("杭州") == ""`，空串是任何串的子串——原来认成 EVENTS 第一行（美网、
    纽约时区），03:00Z 开赛算成当地 9/25，真实是 9/26；赛事名那道闸也拿空串去比、恒过。"""
    spec = _spec()
    spec["_production"] = {"event": "杭州"}
    start = datetime(2026, 9, 26, 3, 0, tzinfo=timezone.utc)
    ctx = cu.match_context(spec, times=lambda _id: (start, None))
    assert not ctx.problems, ctx.problems
    assert (ctx.event_en, ctx.tz, ctx.match_dates) == (
        "Hangzhou", "Asia/Shanghai", {date(2026, 9, 26)}), (ctx.event_en, ctx.tz, ctx.match_dates)
    chengdu = _ap(caption="Coleman Wong reacts against Adolfo Daniel Vallejo during the "
                          "Chengdu Open in Chengdu, China, on Friday, Sept. 25, 2026. (AP Photo)")
    assert cu.metadata_problems(chengdu, ctx), "成都那一站前一天的图放进来了"
    # 英文的照旧认；表里的名字**包含在** prod 里才算，残片「Open」不许认成 US Open
    assert cu.event_of({"_production": {"event": "US OPEN"}, "topbar": {}})[1] == "America/New_York"
    assert cu.event_of({"_production": {"event": "Open"}, "topbar": {}})[1] is None
    # 评审第二轮：event_of 给了 tz None 之后，match_context 还会去官方 OOP 那张表按别名
    # 补时区——原来那里也是子串匹配，「Open」认成「Prague Open」、时区 Europe/Prague，
    # 赛事名那道闸拿 `open` 去比说明，成都那一站的图照样过
    open_only = _spec()
    open_only["_production"] = {"event": "Open"}
    open_only["topbar"]["line1"] = "2026 ATP250 某个没登记的城市 第二轮"
    ctx = cu.match_context(open_only, times=lambda _id: (START, None))
    assert ctx.tz is None and any("时区不在" in p for p in ctx.problems), (ctx.tz, ctx.problems)
    assert cu._registry_tz("Open") is None and cu._registry_tz("Prague") is None
    assert cu._registry_tz("Prague Open") == "Europe/Prague", "整名相等的照旧认"
    # 中文 prod ＋ 顶栏也认不出：不猜
    assert cu.event_of({"_production": {"event": "美网资格赛"}, "topbar": {"line1": "x"}}) is None
    # 赛事名归一出来是空的：点名闸自己也要拦（fail closed），赛事官网担保的也一样
    blank = _ctx(event_en="美网")
    assert any("归一之后是空的" in p for p in cu.metadata_problems(_ap(), blank))
    owned = cu.Candidate("event-site", "https://e/x.jpg", caption=AP_CAPTION, event_owned=True)
    assert any("归一之后是空的" in p for p in cu.metadata_problems(owned, blank))


def test_说明没写日期时上传时刻要晚于开赛():
    """B3：前一晚夜场的图过了当地午夜才传，上传的**日子**和第二天这一场一样。
    说明没写日期就看 WordPress 的 `date_gmt`：早于开赛的不是这一场；只有日子没有时刻的
    判不了，不换。"""
    ctx = _ctx()                                                # 开赛 9/26 12:00Z
    def owned(**kw):
        return cu.Candidate("event-site", "https://e/wp-content/uploads/2026/09/x.jpg",
                            caption="Coleman Wong against Vallejo", event_owned=True, **kw)
    assert cu.metadata_problems(owned(meta_date="2026-09-26", meta_utc="2026-09-26T13:40:00"),
                                ctx) == []
    last_night = cu.metadata_problems(owned(meta_date="2026-09-26",
                                            meta_utc="2026-09-25T16:30:00"), ctx)
    assert any("比这场开赛" in p for p in last_night), last_night
    day_only = cu.metadata_problems(owned(meta_date="2026-09-26"), ctx)
    assert any("没有上传时刻" in p for p in day_only), day_only
    url_only = cu.metadata_problems(owned(), ctx)               # 只有 URL 路径里的 /2026/09/
    assert url_only, url_only
    # 带 Z 的也认；日子按赛事当地（上海）从 UTC 换算
    assert cu.metadata_problems(owned(meta_utc="2026-09-26T13:40:00Z"), ctx) == []
    assert any("元数据日期 2026-09-27" in p
               for p in cu.metadata_problems(owned(meta_utc="2026-09-26T16:30:00Z"), ctx))
    # 评审第二轮：WordPress 的 `date` 是**站点**时区的钟点，不是赛事当地。美网夜场
    # 19:00 EDT 开打、21:30 EDT（01:30Z）传的图，站点设成 UTC 就把 `date` 记成第二天——
    # 当地哪一天要按赛事时区从上传时刻算
    ny = _ctx(tz="America/New_York", start_utc=datetime(2026, 9, 1, 23, 0, tzinfo=timezone.utc),
              match_dates={date(2026, 9, 1)})
    assert cu.metadata_problems(owned(meta_date="2026-09-02",
                                      meta_utc="2026-09-02T01:30:00"), ny) == []
    # 反过来：站点时区把第二天的上传记成这一天，也不许借它混过去
    assert any("元数据日期 2026-09-02" in p for p in cu.metadata_problems(
        owned(meta_date="2026-09-01", meta_utc="2026-09-02T05:00:00"), ny))


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
    no_tz["topbar"]["line1"] = "2026 ATP250 某个没登记的城市 第二轮"
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
    # 比利·简·金杯：2026 年只有 9 月的总决赛在深圳；4 月资格赛、11 月附加赛在别处，
    # 时区不知道就不换（评审第二轮：原来整年都按上海算）
    bjk = _spec()
    bjk["topbar"]["line1"] = "2026 比利·简·金杯 半决赛"
    finals = datetime(2026, 9, 26, 8, 0, tzinfo=timezone.utc)
    ctx = cu.match_context(bjk, times=lambda _id: (finals, None))
    assert ctx.tz == "Asia/Shanghai" and ctx.match_dates == {date(2026, 9, 26)}, ctx.problems
    for elsewhere in (datetime(2026, 4, 11, 15, 0, tzinfo=timezone.utc),
                      datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)):
        ctx = cu.match_context(bjk, times=lambda _id, s=elsewhere: (s, None))
        assert ctx.tz is None and any("时区不在" in p for p in ctx.problems), (elsewhere, ctx.tz)


# ---------------------------------------------------------------- 铺图几何（不要模型）

def test_铺图几何_脸落进钩子带就推zoom_推不动就不换():
    top = cu.hook_top()
    ok = cu.place_face(2560, 1440, (1275, 217, 1652, 718), top)
    assert ok["ok"] and ok["zoom"] == 1.0 and ok["face_out"][3] <= top, ok
    assert ok["face_out"][1] >= cu.HEAD_BAND, ok
    assert 0.55 < ok["focus"] < 0.7, "脸横向没放到正中"
    # N5：图在纵向没有余量（1440 高铺 1440）时偏移被夹住，脸就照原位落进台头——不许放行
    high = cu.place_face(2560, 1440, (1275, 67, 1652, 568), top)
    assert not high["ok"] and "台头" in high["why"], high
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
    ("ok", "巴列霍", None, "这张脸是黄泽林"),                   # 认成对手（cover_target 那一支）
    ("ok", "黄泽林", {"a": {}, "b": {}}, "认人没过（unknown）"),   # 没有官方头像：不敢判
    ("face-low", "黄泽林", None, "钩子带"),
    ("face-high", "黄泽林", None, "压进台头"),                     # N5：脸落在台头底下
])
def test_过不了闸的不换(tmp_path, model, kind, subject, headshots, expect):
    spec = _spec(subject=subject)
    if subject == "巴列霍":
        spec["cover"]["matchup"][1]["name_en"] = "Adolfo Daniel Vallejo"
        cand = _ap(caption=AP_CAPTION.replace("Coleman Wong of Hong Kong", "Adolfo Daniel Vallejo")
                   .replace("against Adolfo Daniel Vallejo", "against Coleman Wong"))
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
    assert cu.upgraded_slugs(repo) == set(), "没换也记了一笔「upgraded」"


def test_闭眼的不换(tmp_path, model):
    spec = _spec(subject="鲁德")
    spec["topbar"]["line1"] = "2026 拉沃尔杯 首日"
    spec["cover"]["matchup"] = [{"name": "鲁德", "name_en": "Casper Ruud"},
                                {"name": "塞伦多洛", "name_en": "Francisco Cerundolo"}]
    spec["stats"] = {"a": {"headshot": "assets/players/headshots/atp-RH16.png"},
                     "b": {"headshot": "assets/players/headshots/atp-C0AU.png"}}
    repo = _repo(tmp_path, {SLUG: (spec, NOW - timedelta(hours=6))})
    cand = cu.Candidate("event-site", "https://lavercup.com/wp-content/uploads/2026/09/r.jpg",
                        caption="Casper Ruud against Cerundolo on Saturday",
                        meta_date="2026-09-26", meta_utc="2026-09-26T19:30:00",
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
                 checker=lambda img, exp, **_kw: {"status": "unavailable", "error": "没装 onnxruntime"},
                 final_gate=lambda spec: None)
    assert got["upgraded"] == []
    assert any("人脸模型不可用" in line for line in got["report"])


def test_人脸模型不可用_这一班只下第一张_剩下的不下也不记tried(tmp_path):
    """复审 nit（2026-09-28）：「装认人依赖」装不上的那一班，原来照样把过了元数据的原图挨张
    下满 `MAX_DOWNLOADS`——一张都判不了、一张都不记 tried，下一班又下一遍。"""
    urls = [f"https://assets.apnews.com/x/{i:08x}.jpg" for i in range(4)]
    fetched: list[str] = []
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))})

    def sweeps_for(_ctx):
        return [("测试渠道", lambda: [_ap(u) for u in urls])]

    def fetch(url):
        fetched.append(url)
        return _photo("ok")

    got = cu.run(repo, NOW, apply=True, sweeps_for=sweeps_for,
                 times=lambda _id: (START, None), fetch=fetch,
                 checker=lambda img, exp, **_kw: {"status": "unavailable", "error": "没装 onnxruntime"},
                 final_gate=lambda spec: None)
    assert got["upgraded"] == []
    assert fetched == urls[:1], f"模型不可用之后还在下：{fetched}"
    assert sum("这一班不再下" in line for line in got["report"]) >= 1, "\n".join(got["report"])
    assert not (cu.load_ledger(repo)["attempts"].get(SLUG) or {}).get("tried"), "模型不可用不许记 tried"


def test_换完过不了正式的封面闸就全部退回(tmp_path, model):
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))})
    before = (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes()
    got = cu.run(repo, NOW, apply=True, sweeps_for=_one(_ap()),
                 times=lambda _id: (START, None), fetch=lambda _url: _photo("ok"),
                 final_gate=lambda spec: "封面大图撑不满卡片",
                 baseline_gate=lambda spec: None)
    assert got["upgraded"] == [] and got["reverted"] == [SLUG]
    assert any(line.startswith("::error::") and "已退回" in line for line in got["report"])
    assert (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes() == before
    assert not (repo / "assets" / "reel" / f"{SLUG}-official.jpg").exists()
    assert cu.upgraded_slugs(repo) == set(), "退回了还记成 upgraded"


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
        "--plan", "pip install", "tools/face_checks.py fetch", "tools/cover_upgrade.py",
        "push_with_rebase_retry main", "gh workflow run match-reel.yml")}
    assert at["--plan"] < at["pip install"] < at["tools/face_checks.py fetch"] \
        < at["tools/cover_upgrade.py"] < at["push_with_rebase_retry main"] \
        < at["gh workflow run match-reel.yml"], (
        "顺序：先不装依赖找目标对账 → 装包 → 备好模型 → 换 → spec 推上 main → "
        "才派发 render（render 只认 main 上的 spec）")
    assert "--apply" in runs[at["tools/cover_upgrade.py"]], "定时班次要真换，不是只报告"
    dispatch = runs[at["gh workflow run match-reel.yml"]]
    assert "mode=render" in dispatch and "push=true" in dispatch, "换完要重渲重推"
    commit = runs[at["push_with_rebase_retry main"]]
    assert "git add --sparse" in commit, "assets/reel 不在稀疏检出里，裸 git add 会静默丢图"


def test_没有目标就不装依赖_不拉模型():
    """N4：一天 72 班，绝大多数是 0 条。装包、缓存模型、拉模型、查图四步都要挂在
    `--plan` 算出来的目标数上；`--plan` 本身只许用标准库。"""
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "reel-cover-upgrade.yml")
                        .read_text("utf-8"))
    steps = [s for job in wf["jobs"].values() for s in job["steps"]]
    plan = next(s for s in steps if "--plan" in str(s.get("run") or ""))
    assert plan.get("id") == "plan" and "targets=" in plan["run"] and "GITHUB_OUTPUT" in plan["run"]
    heavy = [s for s in steps
             if str(s.get("uses") or "").startswith("actions/setup-python")
             or any(k in str(s.get("run") or "") + str(s.get("with") or {})
                    for k in ("pip install", "face-models", "face_checks.py fetch",
                              "tools/cover_upgrade.py"))]
    # setup-python、装包、取缓存、备好模型、存缓存、查图——六步
    assert len(heavy) == 6, [s.get("name") or s.get("uses") for s in heavy]
    for step in heavy:
        assert "steps.plan.outputs.targets != '0'" in str(step.get("if") or ""), (
            step.get("name") or step.get("uses"))
    # 评审第二轮：setup-python 的 pip 缓存还原每一班都跑（包括 0 条的）——`--plan`
    # 用 runner 自带的 python3，排在 setup-python 之前；0 条那一班照样要提交账（对账
    # 重派），提交那一步也只用 python3
    i_plan = steps.index(plan)
    i_setup = next(i for i, s in enumerate(steps) if "setup-python" in str(s.get("uses") or ""))
    assert i_plan < i_setup and "python3 -m cover_upgrade" in plan["run"], "`--plan` 要在 setup-python 之前、用 python3"
    commit = next(s for s in steps if "push_with_rebase_retry main" in str(s.get("run") or ""))
    assert "python3 tools/check_staged_file_sizes.py" in commit["run"]
    assert not re.search(r"(?m)^\s*python\s", commit["run"]), "0 条那一班没装 setup-python，裸 python 可能不在"
    # 真跑一遍 --plan：一个重模块都不许 import（装包那一步被跳过时它照样要能跑）
    probe = (
        "import sys; sys.path.insert(0, 'tools'); import cover_upgrade as cu; "
        "rc = cu.main(['--plan', '--repo', sys.argv[1], '--now', '2026-09-27T03:00:00Z']); "
        "bad = [m for m in ('PIL', 'cv2', 'onnxruntime', 'numpy', 'requests', "
        "'build_match_reel', 'face_checks', 'find_cover_photo') if m in sys.modules]; "
        "print('HEAVY', bad); sys.exit(rc or bool(bad))")
    out = subprocess.run([sys.executable, "-c", probe, str(ROOT)], cwd=ROOT,
                         capture_output=True, text=True, check=False)
    assert out.returncode == 0 and "HEAVY []" in out.stdout, out.stdout + out.stderr


def test_派发失败要重试_下一班对账补派(tmp_path):
    """N1：`gh workflow run` 失败一次，spec 已经在 main 上用新图、成片还是抽帧，账里记着
    upgraded——原来从此没人再派。现在：工作流每条重试三次；下一班的对账看到「换了图、
    一小时了发布账本里没有新的推送尝试」就重派，最多两次。"""
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))})
    ledger = {"upgrades": {SLUG: {"status": "upgraded",
                                  "at": (NOW - timedelta(minutes=90)).strftime("%Y-%m-%dT%H:%M:%SZ")}}}
    (repo / cu.LEDGER).parent.mkdir(parents=True, exist_ok=True)
    (repo / cu.LEDGER).write_text(json.dumps(ledger), "utf-8")
    due, notes = cu.redispatch_plan(repo, NOW)
    assert due == [SLUG], notes
    # --plan --apply：把这次重派记进账，并写出清单给工作流
    out_t, out_r = tmp_path / "t.txt", tmp_path / "r.txt"
    rc = cu.main(["--plan", "--apply", "--repo", str(repo), "--now", NOW.isoformat(),
                  "--out-targets", str(out_t), "--out-redispatch", str(out_r)])
    assert rc == 0 and out_r.read_text("utf-8") == f"{SLUG}\n"
    row = cu.load_ledger(repo)["upgrades"][SLUG]
    assert len(row["dispatches"]) == 1
    # 刚重派过：一小时内不再派
    assert cu.redispatch_plan(repo, NOW + timedelta(minutes=30))[0] == []
    # 又过了一小时还没推：第二次；再往后：不派了，要人看
    later = NOW + timedelta(minutes=70)
    assert cu.redispatch_plan(repo, later)[0] == [SLUG]
    cu.mark_redispatched(repo, [SLUG], later)
    due, notes = cu.redispatch_plan(repo, later + timedelta(minutes=70))
    assert due == [] and any("::warning::" in n and "要人看" in n for n in notes), notes
    report = cu.plan(repo, later + timedelta(minutes=70))["report"]
    assert any(line.startswith("::warning::") for line in report), "注解要顶格，不然 Actions 不认"
    # 换图之后发布账本里有了新的推送尝试（sent／uncertain 都算走到了）：不再派
    led = repo / "data" / "reel_publish_ledger" / f"{SLUG}.json"
    data = json.loads(led.read_text("utf-8"))
    data["attempts"].append({"status": "uncertain", "at": (NOW - timedelta(minutes=60))
                             .strftime("%Y-%m-%dT%H:%M:%SZ")})
    led.write_text(json.dumps(data), "utf-8")
    ledger["upgrades"][SLUG].pop("dispatches", None)
    (repo / cu.LEDGER).write_text(json.dumps(ledger), "utf-8")
    assert cu.redispatch_plan(repo, NOW) == ([], [])
    # 工作流：每条重试三次、不读循环的 stdin、清单里带对账那一份、失败要红
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "reel-cover-upgrade.yml")
                        .read_text("utf-8"))
    runs = [str(s.get("run") or "") for job in wf["jobs"].values() for s in job["steps"]]
    step = next(r for r in runs if "gh workflow run match-reel.yml" in r)
    assert "for n in 1 2 3" in step and "</dev/null" in step and "redispatch.txt" in step
    assert "exit 1" in step


def _cands(n: int) -> list:
    return [_ap(url=f"https://assets.apnews.com/x/{i:02d}.jpg") for i in range(n)]


def _stub_checker(img, expected, **_kw):
    return {"status": "ok", "identity": {"verdict": "match", "name": "黄泽林",
                                         "face": [1275, 217, 1652, 718],
                                         "similarity": {"黄泽林": 0.6}},
            "eyes": {"verdict": "open", "ear": 0.3}}


def test_下过没过闸的记进账_下一班轮得到第11张(tmp_path):
    """N3：原来每一班按同样的顺序重下同样的前十张，第 11 张永远轮不到。"""
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))})
    cands = _cands(12)
    fetched: list = []

    def go(now, blob=None, checker=_stub_checker):
        def fetch(url):
            fetched.append(url)
            return blob if blob is not None else _photo("low-res")
        return cu.run(repo, now, apply=True, sweeps_for=lambda ctx: [("测试渠道", lambda: cands)],
                      times=lambda _id: (START, None), fetch=fetch, checker=checker,
                      final_gate=lambda spec: None)

    first = go(NOW)
    assert first["upgraded"] == [] and fetched == [c.url for c in cands[:10]]
    assert sorted(cu.load_ledger(repo)["attempts"][SLUG]["tried"]) == [c.url for c in cands[:10]]
    fetched.clear()
    second = go(NOW + timedelta(minutes=20))
    assert fetched == [c.url for c in cands[10:]], fetched
    assert any("跳过 10 张" in line for line in second["report"]), second["report"]
    # 模型没加载上的那一班什么都没查成：不记，下一班还要再下
    repo2 = _repo(tmp_path / "b", {SLUG: (_spec(), NOW - timedelta(hours=6))})
    got = cu.run(repo2, NOW, apply=True, sweeps_for=_one(_ap()), times=lambda _id: (START, None),
                 fetch=lambda _url: _photo("ok"),
                 checker=lambda img, exp, **_kw: {"status": "unavailable", "error": "没装"},
                 final_gate=lambda spec: None)
    assert got["upgraded"] == []
    assert SLUG not in cu.load_ledger(repo2)["attempts"], "模型不可用也记成下过了"
    # 干跑不写账
    repo3 = _repo(tmp_path / "c", {SLUG: (_spec(), NOW - timedelta(hours=6))})
    cu.run(repo3, NOW, apply=False, sweeps_for=_one(_ap()), times=lambda _id: (START, None),
           fetch=lambda _url: _photo("low-res"), checker=_stub_checker)
    assert not (repo3 / cu.LEDGER).exists()


def test_退回的要退避_不许每班都红(tmp_path):
    """N2：换完过不了正式封面闸、已退回的，原来每 20 分钟重来一次、红一次（48 小时红一百多次）。
    现在那张图记成下过，这一条退避 2 小时起、每次翻倍。"""
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))})
    cands = [_ap(url="https://assets.apnews.com/x/a.jpg"), _ap(url="https://assets.apnews.com/x/b.jpg")]
    calls: list = []
    fetched: list = []

    def go(now):
        def sweeps_for(ctx):
            calls.append(now)
            return [("测试渠道", lambda: cands)]
        def fetch(url):
            fetched.append(url)
            return _photo("ok")
        return cu.run(repo, now, apply=True, sweeps_for=sweeps_for,
                      times=lambda _id: (START, None), fetch=fetch, checker=_stub_checker,
                      final_gate=lambda spec: "封面大图撑不满卡片",
                      baseline_gate=lambda spec: None)

    first = go(NOW)
    assert first["reverted"] == [SLUG]
    row = cu.load_ledger(repo)["attempts"][SLUG]
    assert row["next_at"] == (NOW + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert cu.main(["--plan", "--repo", str(repo), "--now",
                    (NOW + timedelta(minutes=20)).isoformat()]) == 0
    soon = go(NOW + timedelta(minutes=20))
    assert soon["reverted"] == [] and len(calls) == 1, "退避期内又去查了"
    assert any("退避到" in line for line in soon["report"]), soon["report"]
    fetched.clear()
    later = go(NOW + timedelta(hours=2, minutes=1))
    assert later["reverted"] == [SLUG] and "https://assets.apnews.com/x/a.jpg" not in fetched, \
        "退回过的那张又下了一遍"
    row = cu.load_ledger(repo)["attempts"][SLUG]
    assert len(row["reverts"]) == 2
    assert row["next_at"] == (NOW + timedelta(hours=2, minutes=1) + timedelta(hours=4)) \
        .strftime("%Y-%m-%dT%H:%M:%SZ"), "第二次要翻倍"


# ---------------------------------------------------------------- 评审第二轮

URL_A = "https://assets.apnews.com/x/5f0c2a9e.jpg"
FLAGS_MISSING = ("validate_spec 没过：`cover.matchup[0].country` 指的 assets/flags/hk.png "
                 "不在仓库里")


def _go(repo, now, **kw):
    kw.setdefault("sweeps_for", _one(_ap(url=URL_A)))
    kw.setdefault("fetch", lambda _url: _photo("ok"))
    return cu.run(repo, now, apply=True, times=lambda _id: (START, None),
                  checker=_stub_checker, **kw)


def test_原spec本来就过不了的_退避但不拉黑那张图(tmp_path):
    """评审第二轮：工作流少检出 `assets/flags` 那一次，每一条换好的图都被「assets/flags/hk.png
    不在仓库里」退回——而原来退回一律把那张图记成下过（「这张图不再试」），每条的**第一张
    合格官方图**被永久烧掉。判据：换图之前的原 spec 在这个检出里也过不了，拦的就不是图，
    只退避、不拉黑。"""
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))})
    before = (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes()
    got = _go(repo, NOW, final_gate=lambda spec: FLAGS_MISSING,
              baseline_gate=lambda spec: FLAGS_MISSING)
    assert got["reverted"] == [SLUG] and got["upgraded"] == []
    assert (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes() == before
    row = cu.load_ledger(repo)["attempts"][SLUG]
    assert URL_A not in (row.get("tried") or []), "不是图的错，图被拉黑了"
    assert row["reverts"][-1]["blame_image"] is False and row["next_at"]
    assert any("图不拉黑" in line for line in got["report"]), got["report"]
    # 环境修好、退避期满：同一张图照样换得上
    later = _go(repo, NOW + timedelta(hours=2, minutes=1), final_gate=lambda spec: None)
    assert later["upgraded"] == [SLUG], later["report"]
    # 对照：原 spec 过得了、换上它才过不了——是图的错，拉黑
    repo2 = _repo(tmp_path / "b", {SLUG: (_spec(), NOW - timedelta(hours=6))})
    _go(repo2, NOW, final_gate=lambda spec: "封面大图撑不满卡片",
        baseline_gate=lambda spec: None)
    assert URL_A in cu.load_ledger(repo2)["attempts"][SLUG]["tried"]


def test_最终那道闸自己炸了_文件照样退回不穿出去(tmp_path):
    """稀疏检出里缺个数据文件，`validate_spec` 抛的是 `FileNotFoundError`——原来只接
    `ReelError / SystemExit / ValueError`，它从 `apply_upgrade` 里直接穿出去：spec 和图
    **已经写了、没退回**，这一班后面的条也不查了。"""
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))})
    before = (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes()

    def boom(_spec):
        raise FileNotFoundError("data/legacy_something.json")
    got = _go(repo, NOW, final_gate=boom, baseline_gate=boom)
    assert got["reverted"] == [SLUG]
    assert (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes() == before
    assert not (repo / "assets" / "reel" / f"{SLUG}-official.jpg").exists()
    assert any("FileNotFoundError" in line for line in got["report"]), got["report"]


def test_换好的slug先进清单再记账(tmp_path, monkeypatch):
    """进程死在「记账」和「进清单」之间：原来先记账——提交那一步只推上去账（upgraded），
    spec 没跟上，豁免表减掉了、spec 还是抽帧，render 和 CI 一起红。现在先进清单。"""
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))})
    out = tmp_path / "upgraded.txt"

    class Died(BaseException):
        pass

    def die(*_a, **_k):
        raise Died()
    monkeypatch.setattr(cu, "save_ledger", die)
    with pytest.raises(Died):
        _go(repo, NOW, final_gate=lambda spec: None, out_slugs=out)
    assert out.read_text("utf-8").split() == [SLUG], "账还没写，清单上就该有这一条了"
    assert not (repo / cu.LEDGER).exists()


def test_认人只认封面主角_和封面闸同一个target():
    """评审第二轮 nit：main 的 `check_frame` 有了 `target=`，换图这一头和封面闸
    （`reel_face_gate.cover_target`）用同一个判法——对手的脸是 mismatch。"""
    seen: list = []

    def spy(img, expected, **kw):
        seen.append(kw.get("target"))
        return _stub_checker(img, expected)
    got = cu.image_verdict(_photo("ok"), _spec(), _ctx(), checker=spy)
    assert got["problems"] == [] and seen == [["黄泽林"]], (got, seen)
    cu.image_verdict(_photo("ok"), _spec(subject="巴列霍"), _ctx(subject_zh="巴列霍"), checker=spy)
    assert seen[-1] == ["巴列霍"]


# ------------------------------------------- 最终那道闸：工作流的稀疏检出 vs 全量检出

#: 工作流会往这儿写图，视图里它必须是真目录（全量视图里其余文件照旧链回仓库）
_WRITES = "assets/reel"
#: 视图里要**复制**、不能链接的：各模块的 ROOT 是 `Path(__file__).resolve().parents[…]`，
#: 链接会被 resolve 回原仓库，等于没切
_COPIED = ("tools", "src")


def _workflow_sparse() -> list[str]:
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "reel-cover-upgrade.yml")
                        .read_text("utf-8"))
    steps = [s for job in wf["jobs"].values() for s in job["steps"]]
    co = next(s for s in steps if str(s.get("uses") or "").startswith("actions/checkout"))
    opts = co.get("with") or {}
    assert opts.get("sparse-checkout-cone-mode", True) is True, "下面按 cone 模式展开"
    return [ln.strip().strip("/") for ln in str(opts["sparse-checkout"]).splitlines() if ln.strip()]


def _checkout_view(dest: Path, cone: list[str] | None, extra: tuple[str, ...] = ()) -> Path:
    """`ROOT` 的一份只读「检出」：`cone=None` 是全量，否则按 actions/checkout 的 cone
    模式展开——列出的目录整棵、它们每一层上级目录里的**文件**、仓库根上的文件。
    `extra`：工作流在 cone 之外单独检出的文件（「检出目标 spec 点名的素材」那一步）。"""
    import shutil  # noqa: PLC0415

    def covered(rel: str) -> bool:
        return cone is None or any(rel == c or rel.startswith(c + "/") for c in cone)

    def above(rel: str) -> bool:
        return cone is not None and any(c.startswith(rel + "/") for c in cone)

    def walk(src: Path, dst: Path, rel: str) -> None:
        dst.mkdir(parents=True, exist_ok=True)
        for child in sorted(src.iterdir()):
            sub = f"{rel}/{child.name}" if rel else child.name
            if child.name in (".git", "__pycache__", ".pytest_cache"):
                continue
            if child.is_dir() and not child.is_symlink():
                writes = sub == _WRITES or _WRITES.startswith(sub + "/")
                if sub in _COPIED and covered(sub):
                    shutil.copytree(child, dst / child.name,
                                    ignore=shutil.ignore_patterns("__pycache__"))
                elif (writes and covered(sub)) or above(sub):
                    walk(child, dst / child.name, sub)
                elif covered(sub):
                    (dst / child.name).symlink_to(child, target_is_directory=True)
            elif rel == "" or covered(rel) or above(rel):
                (dst / child.name).symlink_to(child)

    walk(ROOT, dest, "")
    (dest / _WRITES).mkdir(parents=True, exist_ok=True)
    for rel in extra:
        if (ROOT / rel).is_file() and not (dest / rel).exists():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            (dest / rel).symlink_to(ROOT / rel)
    return dest


def _workflow_extra_assets() -> tuple[str, ...]:
    """工作流在 cone 之外补检出的文件：`--plan` 按 `spec_assets` 写的那张单子。这里拿
    `_GATE_PROBE` 会换图的每一条 spec 算一遍（和 probe 同一个筛法）。"""
    out: set[str] = set()
    for path in sorted((ROOT / "specs" / "reels").glob("*.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        cover = spec.get("cover") or {}
        if cu.is_frame_cover(spec) and str(cover.get("eyebrow") or "").strip() == "赛场之上":
            out.update(cu.spec_assets(spec))
    return tuple(sorted(out))


#: 在视图里跑：每一条「赛场之上」抽帧封面按机器换图的形状换成一张 2560×1440 的图，
#: 过**真的** `_final_gate`（`cover_photo_problem` ＋ `validate_spec`）。
_GATE_PROBE = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, "tools")
import cover_upgrade as cu
from PIL import Image

out = {}
for path in sorted(Path("specs/reels").glob("*.json")):
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        continue
    cover = spec.get("cover") or {}
    if not cu.is_frame_cover(spec) or str(cover.get("eyebrow") or "").strip() != "赛场之上":
        continue
    slug = str(spec.get("slug") or path.stem)
    rel = f"assets/reel/{slug}-official.jpg"
    Image.new("RGB", (2560, 1440), (90, 90, 90)).save(rel)
    ctx = cu.MatchContext(slug=slug, subject_zh=str(cover.get("subject") or ""))
    chosen = {"candidate": cu.Candidate("ap", "https://x/y.jpg"), "evidence": {
        "size": [2560, 1440], "face": {"similarity": {}, "ear": 0.3},
        "layout": {"zoom": 1.0, "focus": 0.6, "focus_y": 0.5,
                   "face_out": [300, 300, 700, 700], "fill": 1.0}}}
    spec["cover"]["portrait"] = cu.upgraded_portrait(cover.get("portrait") or {}, chosen, ctx, rel)
    out[slug] = cu._final_gate(spec)
print("GATES " + json.dumps(out, ensure_ascii=False))
"""


def test_最终那道闸在工作流的稀疏检出里和全量检出里判得一样(tmp_path):
    """评审第二轮 BLOCKING：main 的 #1104 让 `validate_spec` 查比分板国旗
    （`reel_asset_gates.image_problems` 要 `assets/flags/<iso2>.png`），而工作流的稀疏检出
    没列 `assets/flags`——**每一条**换好的图都被「assets/flags/hk.png 不在仓库里」退回。
    `test_换出来的portrait过得了正式的封面闸` 抓不到它：那条在 CI 的全量检出里跑。

    这条把工作流那张单子（`reel-cover-upgrade.yml` 的 `sparse-checkout`）按 cone 模式
    真的展开成一个检出，拿仓库里**每一条**「赛场之上」抽帧封面换成图、过真的
    `_final_gate`，和全量检出逐条比：稀疏检出**不许多出任何一个问题**。
    不按字段名列素材清单——`validate_spec` 以后再多读一样东西，这里自己会红。"""
    views = {"full": _checkout_view(tmp_path / "full", None),
             "sparse": _checkout_view(tmp_path / "sparse", _workflow_sparse(),
                                      _workflow_extra_assets())}
    procs = {}
    for name, view in views.items():
        env = {**os.environ, "PYTHONPATH": f"{view / 'src'}{os.pathsep}{view / 'tools'}",
               "PYTHONDONTWRITEBYTECODE": "1"}
        procs[name] = subprocess.Popen([sys.executable, "-c", _GATE_PROBE], cwd=view, env=env,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    got = {}
    for name, proc in procs.items():
        out, err = proc.communicate(timeout=600)
        line = next((ln for ln in out.splitlines() if ln.startswith("GATES ")), None)
        assert proc.returncode == 0 and line, f"{name}：{err[-2000:]}"
        view = str(views[name])
        got[name] = {slug: (p.replace(view, "<ROOT>") if p else p)
                     for slug, p in json.loads(line[len("GATES "):]).items()}
    full, sparse = got["full"], got["sparse"]
    assert full and sorted(full) == sorted(sparse)
    assert any(p is None for p in full.values()), (
        "全量检出里一条都过不了最终那道闸——这条对账就成了空转，先看是哪道闸把它们全拦了")
    diff = {slug: sparse[slug] for slug in full if sparse[slug] != full[slug]}
    assert not diff, ("工作流的稀疏检出比全量多拦了这些（缺的素材要加进 "
                      "reel-cover-upgrade.yml 的 sparse-checkout）：\n"
                      + "\n".join(f"  {s}: {p}" for s, p in sorted(diff.items())[:8]))


def test_点名素材那一步在真的稀疏检出里只取出那几张(tmp_path):
    """批次 4 复审 BLOCKING：`assets/reel` 不在稀疏检出里，gea-shapovalov 的三张插图段图
    让最终那道闸和基线一起红、永远退避。工作流的补法是 `--plan` 写 `--out-assets`、
    下一步只检出那几张——cone 模式的 `sparse-checkout add` 只收目录，所以这段脚本
    **真的**拿一个 cone 稀疏检出跑一遍：点名的取出来、没点名的不取、索引里没有的不炸。"""
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "reel-cover-upgrade.yml")
                        .read_text("utf-8"))
    steps = [s for job in wf["jobs"].values() for s in job["steps"]]
    plan = next(s for s in steps if "--plan" in str(s.get("run") or ""))
    assert '--out-assets "$RUNNER_TEMP/assets.txt"' in plan["run"]
    step = next(s for s in steps if "assets.txt" in str(s.get("run") or "") and s is not plan)
    assert step.get("if") == "steps.plan.outputs.targets != '0'"
    i = steps.index
    gate = next(s for s in steps if "tools/cover_upgrade.py" in str(s.get("run") or ""))
    assert i(plan) < i(step) < i(gate), "要排在 --plan 之后、查图过闸之前"

    src = tmp_path / "src"
    for rel, body in {"assets/reel/a.jpg": "A", "assets/reel/b.jpg": "B",
                      "specs/reels/x.json": "{}"}.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(body, "utf-8")
    _git(tmp_path, "init", "-q", str(src))
    _git(src, "add", "-A")
    _commit(src, "init")
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", "--sparse", f"file://{src}", str(work))
    _git(work, "sparse-checkout", "set", "specs")
    assert not (work / "assets").exists()
    runner = tmp_path / "runner"
    runner.mkdir()
    (runner / "assets.txt").write_text("assets/reel/a.jpg\nassets/reel/missing.jpg\n", "utf-8")
    env = {**os.environ, **{k: str(v) for k, v in (step.get("env") or {}).items()},
           "RUNNER_TEMP": str(runner)}
    out = subprocess.run(["bash", "-eo", "pipefail", "-c", step["run"]], cwd=work, env=env,
                         capture_output=True, text=True, check=False)
    assert out.returncode == 0, out.stdout + out.stderr
    assert (work / "assets/reel/a.jpg").read_text("utf-8") == "A"
    assert not (work / "assets/reel/b.jpg").exists(), "只取点名的，不整个拉 assets/reel"
    assert _git(work, "status", "--porcelain") == "", "取出来的文件不许变成改动"


def test_spec_assets按字符串认素材_不按字段名():
    spec = {"cover": {"portrait": {"frame_at": 3.2}},
            "segments": [{"image": "assets/reel/x.jpg"},
                         {"inset": {"image": "assets/reel/y.png"}},
                         {"narration": "assets/ 开头的旁白\n不算"},
                         {"image": "assets/../etc/passwd"}]}
    assert cu.spec_assets(spec) == ["assets/reel/x.jpg", "assets/reel/y.png"]


# ---------------------------------------------------------------- 评审第三轮

def _load_collision_judge():
    """CI 上那条判据本身（`tests/test_release_tag_collision.py`），换一个模块名载进来，
    好把它的 `ROOT` 指到临时仓库——拿真判据判，不另写一份「差不多」的。"""
    import importlib.util  # noqa: PLC0415

    path = ROOT / "tests" / "test_release_tag_collision.py"
    spec = importlib.util.spec_from_file_location("_release_tag_judge_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _commit(repo: Path, msg: str) -> None:
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", msg)


def test_跨天重渲_新旧两格render_json都挂账_tag碰撞判据不红(tmp_path, monkeypatch):
    """评审 NB1（在试合并上拿真 spec、真人脸模型、真 `_final_gate` 复现过）：最晚那一格
    在前一天（北京）时 `stale_markers` 返回 []，工作流随后 `match-reel mode=render push=true`，
    render 在**新的日期目录**写 render.json——Release 那一步 `--clobber` 传的是同一个 tag，
    `video_url` 一样、`video_bytes` 不一样，两份都没 `_release_tag_note`，而 render 用
    GITHUB_TOKEN 直推 main、CI 不跑，**下一个不相干的 PR 才红**。评审当时 `--plan` 的 6 条
    目标里 4 条最晚那一格在前一天：跨天是常态。

    判据：① 换图那一班就给旧的那格挂好账、进了索引（稀疏检出，`output/` 不在工作区）；
    ② render 传完 Release，`release_tag_note.py current` 给新的那格挂账；
    ③ 拿 CI 上那两条判据原样判这个仓库——挂账之前红、之后绿。"""
    import release_tag_note as rtn  # noqa: PLC0415

    url = f"https://github.com/o/r/releases/download/reel-{SLUG}/{SLUG}.mp4"
    old = f"output/2026-09-26/reel/{SLUG}"            # NOW 是北京 9/27：最晚那一格在前一天
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))},
                 {SLUG: [f"{old}/pushed.json"]})
    records = {f"{old}/render.json": {"video_url": url, "video_bytes": 52300555}}
    for i in range(20):                               # 判据自带「至少 20 份」的下限
        other = f"filler-{i:02d}"
        records[f"output/2026-09-20/reel/{other}/render.json"] = {
            "video_url": f"https://github.com/o/r/releases/download/reel-{other}/{other}.mp4",
            "video_bytes": 1000 + i}
    for rel, data in records.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(json.dumps(data, indent=2) + "\n", "utf-8")
    _git(repo, "add", "-A")
    _commit(repo, "renders")
    _git(repo, "sparse-checkout", "set", "--no-cone", "/*", "!/output/")   # 和工作流一样
    assert not (repo / old).exists()
    assert cu.stale_markers(repo, SLUG, NOW) == [], "前提：跨天，没有同日的 pushed.json 要删"

    got = _go(repo, NOW, final_gate=lambda spec: None)
    assert got["upgraded"] == [SLUG], got["report"]
    staged = json.loads(_git(repo, "show", f":{old}/render.json"))
    note = str(staged.get(rtn.NOTE_KEY) or "")
    assert f"reel-{SLUG}" in note and "2026-09-27" in note and "Content-Range" in note, (
        f"① 换图那一班没给 tag 上的旧 render.json 挂账（或没进索引）：{staged}")
    assert staged["video_bytes"] == 52300555, "挂账不许动原来记的数"
    assert cu.load_ledger(repo)["upgrades"][SLUG]["tag_notes"] == [f"{old}/render.json"]
    assert any("挂账" in line for line in got["report"]), got["report"]
    _commit(repo, "upgrade")

    # 派出去的 render 在北京 9/28 00:30 跑完：新的一格，同一个 tag，字节变了（封面换了）
    new = f"output/2026-09-28/reel/{SLUG}"
    (repo / new).mkdir(parents=True)
    (repo / new / "render.json").write_text(
        json.dumps({"video_url": url, "video_bytes": 52417311}, indent=2) + "\n", "utf-8")
    _git(repo, "add", "--sparse", f"{new}/render.json")
    judge = _load_collision_judge()
    monkeypatch.setattr(judge, "ROOT", repo)
    with pytest.raises(AssertionError, match=re.escape(new)):
        # 对照组：新的那格没挂账，CI 上那条判据就是这么红的——判据看得见这个仓库
        judge.test_同一个Release_tag被两份产物共用时每一份都要挂账()

    rc = rtn.main(["current", "--render-json", str(repo / new / "render.json"),
                   "--run-id", "36300000000", "--repo", str(repo),
                   "--now", "2026-09-27T16:30:00Z"])
    assert rc == 0
    fresh = json.loads((repo / new / "render.json").read_text("utf-8"))
    assert "run 36300000000" in str(fresh.get(rtn.NOTE_KEY)) and old in str(fresh.get(rtn.NOTE_KEY)), (
        f"② 传完 Release 没给新的这一份挂账：{fresh}")
    assert fresh["video_bytes"] == 52417311
    _git(repo, "add", "--sparse", f"{new}/render.json")
    judge.test_同一个Release_tag被两份产物共用时每一份都要挂账()
    judge.test_挂账那句话不许写成一句空话()


def test_旧render_json读不出来_动spec之前就退出_图不拉黑(tmp_path):
    """挂账要先读旧的 render.json（稀疏检出下走 `git show :路径`）。读不出来（坏 JSON、git
    跑不起来）时原来的顺序是：spec 和图已经写了，异常再从 `apply_upgrade` 冒出去——`run`
    按「换完过不了闸」记一笔、**拉黑这张图**，而 spec 没退回。现在先读后写：读不出来就在
    动 spec 之前退出，只退避、不拉黑（不是图的错）。"""
    old = f"output/2026-09-26/reel/{SLUG}"
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))},
                 {SLUG: [f"{old}/render.json"]})
    (repo / old / "render.json").write_text("{坏的", "utf-8")
    _git(repo, "add", "-A")
    _commit(repo, "broken")
    before = (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes()
    got = _go(repo, NOW, final_gate=lambda spec: None)
    assert got["reverted"] == [SLUG] and got["upgraded"] == [], got["report"]
    assert (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes() == before
    assert not (repo / "assets" / "reel" / f"{SLUG}-official.jpg").exists()
    row = cu.load_ledger(repo)["attempts"][SLUG]
    assert URL_A not in (row.get("tried") or []) and row["reverts"][-1]["blame_image"] is False
    assert any("挂不了账" in line for line in got["report"]), got["report"]


def test_Release挂账_不共用tag就不写_旧的没挂账要点名(tmp_path, capsys):
    """`release_tag_note.py current` 的两头：第一次渲（没有别的记录共用这个 tag）一个字都
    不写；会话手动跨天重渲（旧的那格没人挂账）——它不去改旧目录（一趟 render 只提交自己
    那一格），但要打 `::warning::` 点名，别等下一个 PR 红了才知道。"""
    import release_tag_note as rtn  # noqa: PLC0415

    url = f"https://github.com/o/r/releases/download/reel-{SLUG}/{SLUG}.mp4"
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW)})
    first = repo / f"output/2026-09-26/reel/{SLUG}/render.json"
    first.parent.mkdir(parents=True)
    first.write_text(json.dumps({"video_url": url, "video_bytes": 1}) + "\n", "utf-8")
    assert rtn.mark_current(repo, first, "1", NOW) == (False, [])
    assert rtn.NOTE_KEY not in json.loads(first.read_text("utf-8"))
    _git(repo, "add", "-A")
    _commit(repo, "first")
    second = repo / f"output/2026-09-27/reel/{SLUG}/render.json"
    second.parent.mkdir(parents=True)
    second.write_text(json.dumps({"video_url": url, "video_bytes": 2}) + "\n", "utf-8")
    assert rtn.main(["current", "--render-json", str(second), "--run-id", "2",
                     "--repo", str(repo)]) == 0
    out = capsys.readouterr().out
    assert f"::warning::output/2026-09-26/reel/{SLUG}/render.json" in out, out
    assert rtn.NOTE_KEY not in json.loads(first.read_text("utf-8")), "旧目录不归这一趟提交，不许改"
    # 2026-08-13 之前的成片在 git 里、不走 Release：不会被换掉，`supersede` 不挂
    raw = repo / f"output/2026-08-01/reel/{SLUG}/render.json"
    raw.parent.mkdir(parents=True)
    raw.write_text(json.dumps({"video_url": f"https://raw.githubusercontent.com/o/r/main/x/{SLUG}.mp4",
                               "video_bytes": 3}) + "\n", "utf-8")
    _git(repo, "add", "-A")
    _commit(repo, "raw")
    noted = rtn.supersede(repo, SLUG, NOW, "测试", stage=False)
    assert noted == [f"output/2026-09-26/reel/{SLUG}/render.json",
                     f"output/2026-09-27/reel/{SLUG}/render.json"], noted


def test_会话手动跨天重渲_派发前跑supersede_合并时tag碰撞判据不红(tmp_path, monkeypatch, capsys):
    """2026-09-28 `wang-prozorova` 换开赛时刻跨天重渲：旧的那格没人挂账，PR 的 CI 红了一轮
    （`test_同一个Release_tag被两份产物共用时每一份都要挂账`），手写一句才过。O4 那条路换图时
    自己挂（`cover_upgrade.apply_upgrade`），会话手动重渲这条路原来只有 `current` 事后点名。

    判据：派发之前跑 `release_tag_note.py supersede --slug`，旧的那格挂好、进索引；render 传完
    `current` 给新的挂上——CI 那两条判据原样判这个仓库，全绿；没有旧记录时也要出声。"""
    import release_tag_note as rtn  # noqa: PLC0415

    url = f"https://github.com/o/r/releases/download/reel-{SLUG}/{SLUG}.mp4"
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(days=2))})
    assert rtn.main(["supersede", "--slug", SLUG, "--repo", str(repo)]) == 0
    assert "没有旧记录，不用挂账" in capsys.readouterr().out, "没什么可挂也要出声"

    old = f"output/2026-09-25/reel/{SLUG}"
    records = {f"{old}/render.json": {"video_url": url, "video_bytes": 111000111}}
    for i in range(20):                               # 判据自带「至少 20 份」的下限
        other = f"filler-{i:02d}"
        records[f"output/2026-09-20/reel/{other}/render.json"] = {
            "video_url": f"https://github.com/o/r/releases/download/reel-{other}/{other}.mp4",
            "video_bytes": 1000 + i}
    for rel, data in records.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(json.dumps(data, indent=2) + "\n", "utf-8")
    _git(repo, "add", "-A")
    _commit(repo, "renders")
    _git(repo, "sparse-checkout", "set", "--no-cone", "/*", "!/output/")   # 和工作流一样

    assert rtn.main(["supersede", "--slug", SLUG, "--why", "改开赛时刻重渲", "--repo", str(repo),
                     "--now", "2026-09-28T04:40:00Z"]) == 0
    assert f"挂账：{old}/render.json" in capsys.readouterr().out
    staged = json.loads(_git(repo, "show", f":{old}/render.json"))
    note = str(staged.get(rtn.NOTE_KEY) or "")
    assert "改开赛时刻重渲" in note and "2026-09-28" in note and "Content-Range" in note, staged
    assert staged["video_bytes"] == 111000111, "挂账不许动原来记的数"
    _commit(repo, "spec + 旧的挂账")

    new = f"output/2026-09-28/reel/{SLUG}"
    (repo / new).mkdir(parents=True)
    (repo / new / "render.json").write_text(
        json.dumps({"video_url": url, "video_bytes": 111826692}, indent=2) + "\n", "utf-8")
    assert rtn.main(["current", "--render-json", str(repo / new / "render.json"),
                     "--run-id", "36424112503", "--repo", str(repo)]) == 0
    assert "::warning::" not in capsys.readouterr().out, "旧的已经挂过，不该再点名"
    _git(repo, "add", "--sparse", f"{new}/render.json")
    judge = _load_collision_judge()
    monkeypatch.setattr(judge, "ROOT", repo)
    judge.test_同一个Release_tag被两份产物共用时每一份都要挂账()
    judge.test_挂账那句话不许写成一句空话()


def test_plan不为怎么查都换不了的目标装依赖(tmp_path):
    """评审 nit：`safiullin-bu-hangzhou-2026-qf` 没有 `_match.start_utc`、也没有
    `flashscore_id`——判不了当地日期，一张图都换不上，而原来 `--plan` 照样把它算成目标，
    48 小时里每 20 分钟为它装一遍 onnxruntime／opencv、拉一遍模型。对手英文名缺的同理
    （点名闸要点对手）。有 `flashscore_id` 的（开赛时刻要联网才知道）照旧算目标。"""
    no_time = _spec()
    no_time["slug"] = "no-time"
    no_time["_match"] = {}
    no_opp = _spec()
    no_opp["slug"] = "no-opp"
    no_opp["cover"]["matchup"][1].pop("name_en")
    live = _spec()
    repo = _repo(tmp_path, {"no-time": (no_time, NOW - timedelta(hours=6)),
                            "no-opp": (no_opp, NOW - timedelta(hours=6)),
                            SLUG: (live, NOW - timedelta(hours=6))})
    got = cu.plan(repo, NOW)
    # 2026-09-28：没有开赛时刻的不再挡掉——按首推时刻推两天窗口照样查（说明必须点对手、写日期），
    # 见 `test_没有开赛时刻_按spec记下的或首推时刻推当地日期_并说是哪一个`
    assert got["targets"] == ["no-time", SLUG], got["report"]
    text = "\n".join(got["report"])
    assert "no-time：怎么查都换不了" not in text, text
    assert "no-opp：怎么查都换不了" in text and "对手" in text, text
    # 不联网也不知道首推时刻的时候（没给 pushed_at），照旧是静态判得出的「查不了」
    assert any("开赛时刻" in p for p in cu.static_problems(no_time)), cu.static_problems(no_time)
    # run 那边同一个口径：对手不知道就不查（不再每张候选各报一遍）
    calls: list = []
    ran = cu.run(repo, NOW, apply=False, only="no-opp", sweeps_for=_one(_ap(), calls),
                 times=lambda _id: (START, None), fetch=lambda _u: b"")
    assert calls == [] and any("对手的英文名" in line for line in ran["report"]), ran["report"]


def test_进程死在进清单和记账之间_下一班plan补记(tmp_path, monkeypatch):
    """评审 nit：`apply_upgrade` 先进清单再记账（宁可提交上去的是「spec 换了、账没记」）。
    可真死在两步之间，`OWNER_APPROVED_FRAME_COVERS` 减不掉这个 slug，`test_match_reel`
    豁免表自检 ⑤ 一直红——而这一条已经不是抽帧、不再是目标，没有东西会去修。
    下一班 `--plan --apply` 认出机器换过的 spec（`_why` 的开头），补记一笔，**不重派**。"""
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))})

    class Died(BaseException):
        pass

    def die(*_a, **_k):
        raise Died()
    with monkeypatch.context() as m:
        m.setattr(cu, "save_ledger", die)
        with pytest.raises(Died):
            _go(repo, NOW, final_gate=lambda spec: None)
    assert cu.upgraded_slugs(repo) == set()
    # 人手写的、图名也叫 -official 的（medvedev-damm 那种）不许被认成机器换的
    hand = _spec()
    hand["slug"] = "hand-made"
    hand["cover"]["portrait"] = {"image": "assets/reel/hand-made-official.jpg",
                                 "_why": "人挑的", "_gates": "人写的"}
    (repo / "specs" / "reels" / "hand-made.json").write_text(json.dumps(hand), "utf-8")
    later = NOW + timedelta(minutes=20)
    dry = cu.plan(repo, later)
    assert dry["reconciled"] == [SLUG] and cu.upgraded_slugs(repo) == set(), "干跑也写了账"
    got = cu.plan(repo, later, apply=True)
    assert got["reconciled"] == [SLUG], got["report"]
    row = cu.load_ledger(repo)["upgrades"][SLUG]
    assert row["status"] == "upgraded" and row["reconciled"] and row["image"].endswith("-official.jpg")
    assert cu.upgraded_slugs(repo) == {SLUG}
    assert any("补记" in line for line in got["report"]), got["report"]
    # 不重派：那一班提交之后派发照常走过；拿补记的时刻去比发布账本会白重渲一趟
    assert cu.redispatch_plan(repo, later + timedelta(hours=3))[0] == []
    assert cu.plan(repo, later + timedelta(minutes=20), apply=True)["reconciled"] == [], "补了还补"


def test_下到一半断掉的图不拉黑(monkeypatch):
    """评审 nit：`evaluate` 把「图打不开」记成下过、永久拉黑——而连接中途断了、字节只下到
    一半的图也解不开。字节数对不上 Content-Length 就当「下不下来」（不拉黑，下一班再下）。"""
    import requests  # noqa: PLC0415

    class Raw:
        def __init__(self, blob):
            self.blob = blob

        def read(self, _n, decode_content=True):
            return self.blob

    class Resp:
        def __init__(self, blob, headers):
            self.raw, self.headers = Raw(blob), headers

        def raise_for_status(self):
            return None

    full = _photo("ok")
    cut = full[: len(full) // 2]
    monkeypatch.setattr(requests, "get", lambda *_a, **_k: Resp(cut, {"Content-Length": str(len(full))}))
    with pytest.raises(OSError, match="只下到"):
        cu.fetch_image("https://assets.apnews.com/x/cut.jpg")
    monkeypatch.setattr(requests, "get", lambda *_a, **_k: Resp(full, {"Content-Length": str(len(full))}))
    assert cu.fetch_image("https://assets.apnews.com/x/ok.jpg") == full
    # 压缩传输：Content-Length 是压缩后的长度，比不了，不比
    monkeypatch.setattr(requests, "get", lambda *_a, **_k: Resp(
        full, {"Content-Length": "10", "Content-Encoding": "gzip"}))
    assert cu.fetch_image("https://assets.apnews.com/x/gz.jpg") == full
    # evaluate 那一头：下不下来的**不**记成下过
    target = cu.Target(slug=SLUG, spec=_spec(), first_sent=NOW, spec_path=Path("x"))

    def fetch(_url):
        raise OSError("只下到 1 / 2 字节（连接中途断了）")
    chosen, rows = cu.evaluate(target, _ctx(), [_ap()], fetch=fetch, checker=_stub_checker)
    assert chosen is None and not rows[0].get("tried"), rows
    assert any("下不下来" in p for p in rows[0]["problems"]), rows


def test_WTA赛后稿头图那一档拿掉了_photo_resources还在(monkeypatch):
    """评审 nit：Match Reaction 的 og:image 只带文件名、没有说明，全名／对手／日期凑不齐，
    恒换不上，却每一班为每条 WTA 目标花一次 `find_match`。photo-resources 留着——
    `GettyImages-*` 会去取 Getty 的说明。

    2026-09-28 渠道合成一份（`cover_channels.CHANNELS`）之后，赛后稿那一档**照样列在报告里**
    ——但是「O4 不查」、写着为什么，**一个请求都不发**（原来它根本不出现，和「查过、没有」
    分不出来）。"""
    import find_cover_photo as fcp  # noqa: PLC0415

    def boom(*a, **k):
        raise AssertionError("O4 不许为赛后稿那一档发请求")

    monkeypatch.setattr(fcp, "sweep_wta_articles", boom)
    sweeps = dict(cu.default_sweeps(_ctx(tour="wta", site=None)))
    assert "WTA photo-resources" in sweeps, list(sweeps)
    res = sweeps["WTA 赛后稿头图"]()
    assert res.status == "off" and "对手" in res.why, res
    assert not hasattr(cu, "wta_article")


# ---------------------------------------------------------------- 评审第四轮

def test_半截失败的一档要报出来_不许报成查空(monkeypatch):
    """评审第四轮 nit：`find_cover_photo` 的报纸档、官网档把「没翻完」写进 `notes`、不抛。
    `default_sweeps` 原来只读 `rows`——一辑都没取到的报纸档报成「0 张」，和查空一模一样。
    顺带：官网档给比赛日（翻完那几天的全部上传再按名字筛，alt_text／文件名里的名字也认得出），
    不再只靠 WordPress 的 `search`。"""
    import find_cover_photo as fcp  # noqa: PLC0415

    calls: dict = {}
    site_answer: dict = {}

    def paper(dom, event, player, day):
        calls["paper"] = (dom, day)
        return {"rows": [], "pages_read": 0,
                "notes": ["翻到 2 辑图集，一辑都没取到——**这一档没跑完，不是没有**"]}

    def site(host, day, player=None, **kw):
        calls["site"] = (host, day, kw.get("days"))
        return dict(site_answer)

    import inspect  # noqa: PLC0415

    # 替身和真函数的签名对得上（替身收 **kw，真函数改了签名替身照样绿）
    inspect.signature(fcp.sweep_tournament).bind("h", "2026-09-26", "wong", days=cu.SITE_UPLOAD_DAYS)
    assert "pages_read" in inspect.getsource(fcp.sweep_local_paper)
    monkeypatch.setattr(fcp, "sweep_local_paper", paper)
    monkeypatch.setattr(fcp, "sweep_tournament", site)
    ctx = _ctx(event_en="Cincinnati", site="cincinnatiopen.com", tour="atp")

    def notes_for(answer: dict) -> list[str]:
        site_answer.clear()
        site_answer.update(answer)
        picked = [s for s in cu.default_sweeps(ctx) if not s[0].startswith("AP")]
        return cu.search(ctx, sweeps=picked)[1]

    row = {"url": "https://cincinnatiopen.com/wp-content/uploads/2026/09/CW_0001.jpg",
           "original": "", "wh": "4000x2667", "title": "", "alt": "Coleman Wong", "caption": "",
           "date": "2026-09-26T21:00:00", "date_gmt": "2026-09-27T01:00:00"}
    got = notes_for({"by_name": [row], "media": [row],
                     "notes": ["第 2 页读不到（timeout）——**后面没翻，不是没有**"]})
    paper_line = next(n for n in got if n.startswith("当地报纸"))
    assert "取不到" in paper_line and "没跑完" in paper_line, got
    site_line = next(n for n in got if n.startswith("赛事官网"))
    assert site_line.startswith("赛事官网 cincinnatiopen.com：1 张（第 2 页读不到"), got
    assert calls["site"] == ("cincinnatiopen.com", "2026-09-26", cu.SITE_UPLOAD_DAYS), calls
    assert calls["paper"] == ("www.cincinnati.com", "2026-09-26"), calls

    got = notes_for({"error": "媒体库读不到：HTTP Error 403: Forbidden", "by_name": []})
    site_line = next(n for n in got if n.startswith("赛事官网"))
    assert "取不到" in site_line and "403" in site_line, got
    # 对照组：真查空（翻完了、没有这个人）照旧是「0 张」，不带括号，而且明说「查空」
    empty = next(n for n in notes_for({"by_name": [], "media": [], "notes": []})
                 if n.startswith("赛事官网"))
    assert empty.startswith("赛事官网 cincinnatiopen.com：0 张——查空"), empty


@pytest.mark.parametrize("sparse", [True, False])
def test_过闸之后挂账那一步炸了_索引连spec一起全部退回(tmp_path, monkeypatch, sparse):
    """评审第四轮 nit：工作流提交那一步是 always()、`git commit` 不带路径——提交**整个索引**。
    `apply_upgrade` 过闸之后先 `git rm --sparse` 同日的 pushed.json、再给 tag 上的旧
    render.json 挂账（`git add --sparse`），然后才进清单。挂账那一步抛个 `run` 不接的
    `CalledProcessError`：原来 spec 和图留着换好的样子、索引里留着「pushed.json 删了、账挂了
    一半」，而这一班别的条改了账——提交上去的就是没有 spec、也不派 render 的半截。
    判据：退回之后**索引里什么都没有**、工作区和动手之前一样、清单上没有它；记一笔退避、
    图不拉黑（不是图的错）。"""
    import release_tag_note as rtn  # noqa: PLC0415

    url = f"https://github.com/o/r/releases/download/reel-{SLUG}/{SLUG}.mp4"
    today = f"output/2026-09-27/reel/{SLUG}"          # NOW 是北京 9/27：同日，要删 pushed.json
    older = f"output/2026-09-26/reel/{SLUG}"
    repo = _repo(tmp_path, {SLUG: (_spec(), NOW - timedelta(hours=6))},
                 {SLUG: [f"{today}/pushed.json"]})
    for rel, size in ((f"{older}/render.json", 52300555), (f"{today}/render.json", 52417311)):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(json.dumps({"video_url": url, "video_bytes": size}, indent=2)
                                + "\n", "utf-8")
    _git(repo, "add", "-A")
    _commit(repo, "renders")
    if sparse:
        _git(repo, "sparse-checkout", "set", "--no-cone", "/*", "!/output/")   # 和工作流一样
    assert cu.stale_markers(repo, SLUG, NOW) == [f"{today}/pushed.json"], "前提：同日"
    spec_before = (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes()
    tree_before = {p.relative_to(repo).as_posix(): p.read_bytes()
                   for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts}

    real, seen = rtn.write, []

    def flaky(repo_, rel, data, *, stage):
        seen.append(rel)
        if len(seen) == 2:                            # 第一份已经挂好、进了索引，第二份炸
            raise subprocess.CalledProcessError(128, ["git", "add", "--sparse", "--", rel])
        return real(repo_, rel, data, stage=stage)
    monkeypatch.setattr(rtn, "write", flaky)
    out = tmp_path / "upgraded.txt"
    got = _go(repo, NOW, final_gate=lambda spec: None, out_slugs=out)

    assert got["reverted"] == [SLUG] and got["upgraded"] == [], got["report"]
    assert len(seen) == 2, f"前提：第二份挂账炸了（{seen}）"
    assert _git(repo, "diff", "--cached", "--name-only") == "", (
        "索引里还留着半截——工作流那句不带路径的 `git commit` 会把它提交上去")
    assert _git(repo, "status", "--porcelain", "--", "output", "specs", "assets") == "", (
        _git(repo, "status", "--porcelain"))
    assert (repo / "specs" / "reels" / f"{SLUG}.json").read_bytes() == spec_before
    assert not (repo / "assets" / "reel" / f"{SLUG}-official.jpg").exists()
    tree_after = {p.relative_to(repo).as_posix(): p.read_bytes()
                  for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts
                  and p.relative_to(repo).as_posix() != str(cu.LEDGER)}
    assert tree_after == tree_before
    assert not out.exists() or out.read_text("utf-8") == "", "退回了还在清单上——会派 render"
    row = cu.load_ledger(repo)["attempts"][SLUG]
    assert URL_A not in (row.get("tried") or []) and row["reverts"][-1]["blame_image"] is False
    assert SLUG not in cu.upgraded_slugs(repo)
    assert any("全部退回" in line and "CalledProcessError" in line for line in got["report"]), \
        got["report"]
