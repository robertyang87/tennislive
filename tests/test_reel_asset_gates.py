"""「赛场之上」dry-run 的素材与格式闸（`tools/reel_asset_gates.py`）。

来路：2026-09-27 返工取证 P1——封面用时 `1:27` 被读成 87 秒（bucsa-noskova 5bd09938）、
数据统计图只在合并之后的推送闸上要（hu-kopriva run 35950951376）、半截 PNG 头像渲出
「上半张脸」（zheng-you 4d35f28f／aedb4504）、封面借了已发片子的图（wang-prozorova
9f1169aa → 81ec82b4）、字幕把两个比分粘成一个（本文件量出来 12 条已发）、以及 dry-run
自己拼标题永远拿不到日期、字数闸在本地一次都没跑过。每一条原来都要付一趟 render
甚至一次重推；判它们要的东西在写 spec 那一刻全在盘上。

判据分三层：每道闸各自的正反例（fixture）；全库扫一遍存量零误报、豁免表只许减；
`validate_spec` / dry-run 真的接上了（拆掉那一刀，这里当场红）。
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import build_match_reel as reel  # noqa: E402
import reel_asset_gates as gates  # noqa: E402

NONE = frozenset()


def _data_url(value) -> str:
    return "data:application/json," + urllib.parse.quote(json.dumps({"duration": value}))


def _court(**extra) -> dict:
    """最小的一条「赛场之上」：只有闸会读的那几个字段。"""
    spec = {
        "slug": "fixture-reel",
        "cover": {"eyebrow": "赛场之上", "result": "6-4 6-3",
                  "matchup": [{"name": "甲", "country": "CHN", "rank": 1},
                              {"name": "乙", "country": "USA", "rank": 2}],
                  "scoreboard": {"court": "中心球场",
                                 "duration_source": {"url": _data_url("1:27:00"),
                                                     "field": "duration"}}},
        "segments": [{"source": "main", "start": 1.0, "end": 5.0, "narration": "坐标。"}],
        "stats": {"a": {"headshot": "assets/players/headshots/wta-322451.jpg"},
                  "b": {"headshot": "assets/players/headshots/wta-322451.jpg"}},
    }
    spec.update(extra)
    return spec


# ─────────────────────────────────────────────────────────── ① 封面用时 ──

@pytest.mark.parametrize("value", ["1:27", "4:28", " 2:05 "])
def test_封面用时写成两段式在dry_run就红(value):
    spec = _court()
    spec["cover"]["scoreboard"]["duration_source"]["url"] = _data_url(value)
    problem = gates.duration_problem(spec)
    assert problem and "两段式" in problem, problem


@pytest.mark.parametrize("value", ["1:27:00", 5220, "5220", "3:02:10"])
def test_封面用时写成时分秒或秒数就过(value):
    spec = _court()
    spec["cover"]["scoreboard"]["duration_source"]["url"] = _data_url(value)
    assert gates.duration_problem(spec) is None


def test_封面用时短得不像一场比赛要认领():
    spec = _court()
    spec["cover"]["scoreboard"]["duration_source"]["url"] = _data_url("0:15:00")
    assert "只有 900 秒" in gates.duration_problem(spec)
    spec["cover"]["result"] = "6-0 4-0 退赛"
    assert gates.duration_problem(spec) is None, "退赛本来就短"
    spec["cover"]["result"] = "6-4 6-3"
    spec["_short_match_why"] = "官方接口就是这个数"
    assert gates.duration_problem(spec) is None
    # 真接口要联网，归渲染那一头——这儿一个字节都不碰
    spec["cover"]["scoreboard"]["duration_source"]["url"] = "https://api.wtatennis.com/x"
    del spec["_short_match_why"]
    assert gates.duration_problem(spec) is None


# ─────────────────────────────────────────────────────── ② 数据统计图 ──

def test_赛场之上没带数据统计图在dry_run就红_不认no_stats_why():
    spec = _court()
    del spec["stats"]
    assert "stat_card" in gates.stats_card_problem(spec, legacy_set=NONE)
    # 推送那道闸从来不认这个认领，这儿跟它走（hu-kopriva 就是认领了之后合并才红）
    spec["_no_stats_why"] = "WTA 查不到制胜分"
    assert gates.stats_card_problem(spec, legacy_set=NONE)
    spec["stats"] = {"a": {"headshot": "x.jpg"}, "b": {}}
    assert "stats.b" in gates.stats_card_problem(spec, legacy_set=NONE)
    spec["stats"]["b"]["headshot"] = "y.jpg"
    assert gates.stats_card_problem(spec, legacy_set=NONE) is None
    # 不归它管的：网球有故事、没有段落的精简统计图 JSON、豁免表里的
    story = _court(cover={"eyebrow": "网球有故事"})
    del story["stats"]
    assert gates.stats_card_problem(story, legacy_set=NONE) is None
    bare = _court(segments=[])
    del bare["stats"]
    assert gates.stats_card_problem(bare, legacy_set=NONE) is None
    del spec["stats"]
    assert gates.stats_card_problem(spec, legacy_set=frozenset({"fixture-reel"})) is None


# ────────────────────────────────────────────────────────── ③ 图片解码 ──

def _png(path: Path) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 30, 30)).save(buf, "PNG")
    path.write_bytes(buf.getvalue())
    return buf.getvalue()


def _jpg(path: Path) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.effect_noise((320, 240), 60).convert("RGB").save(buf, "JPEG", quality=90)
    path.write_bytes(buf.getvalue())
    return buf.getvalue()


def test_引用的图要在而且要解得开(tmp_path):
    (tmp_path / "assets").mkdir()
    good = _png(tmp_path / "assets" / "good.png")
    jpg = _jpg(tmp_path / "assets" / "good.jpg")
    # zheng-you 那种：头是对的、Image.open 打得开，只有解到 IDAT 才报
    broken = bytearray(good)
    broken[broken.index(b"IDAT") + 6] ^= 0xFF
    (tmp_path / "assets" / "badcrc.png").write_bytes(bytes(broken))
    (tmp_path / "assets" / "cut.jpg").write_bytes(jpg[: len(jpg) * 2 // 3])
    spec = {"slug": "x", "cover": {"portrait": {"image": "assets/good.jpg",
                                                "_photo_why": "assets/ignored.png"}},
            "segments": [{"image": "assets/good.png"}, {"image": "<stat_card>"},
                         {"inset": {"image": "assets/cut.jpg"}}],
            "stats": {"a": {"headshot": ["assets/badcrc.png", "assets/good.png"]},
                      "b": {"headshot": "assets/missing.jpg"}},
            "editorial": {"sources": ["https://example.com/a.jpg"]}}
    problems = "\n".join(gates.image_problems(spec, root=tmp_path))
    assert "badcrc.png" in problems and "cut.jpg" in problems, problems
    assert "missing.jpg" in problems and "不在仓库里" in problems
    for fine in ("good.png", "good.jpg", "ignored.png", "example.com", "<stat_card>"):
        assert fine not in problems, f"{fine} 不该被报：{problems}"


def test_比分板的国旗换算不出来在dry_run就红():
    spec = _court()
    spec["cover"]["matchup"][1]["country"] = "PRY"       # wong-vallejo run 36259013573
    problems = gates.image_problems(spec)
    assert any("ISO2" in p for p in problems), problems
    spec["cover"]["matchup"][1]["country"] = "PAR"
    assert gates.image_problems(spec) == []
    spec["cover"]["matchup"][1]["country"] = None         # 中立身份：不画旗
    assert gates.image_problems(spec) == []


def test_仓库里的图都解得开():
    """全库结构扫：PNG 逐块校验 CRC，JPEG 必须收在 EOI，其余格式整张解。

    dry-run 那一头对**这条 spec 引用的图**整张解码（`image_load_problem`）；这条测试
    管的是**所有提交进来的图**——不整张解（1097 张要 20 秒），但半截文件和坏块
    （zheng-you 那张 `wta-322451.png` 就是 IDAT 校验和错）一样逃不掉。
    """
    from PIL import Image
    files = subprocess.run(["git", "ls-files", "assets"], cwd=ROOT, capture_output=True,
                           text=True, check=True).stdout.split("\n")
    images = [f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    assert len(images) > 500, f"只扫到 {len(images)} 张，判据的主语像是没了"
    bad = []
    for rel in images:
        path = ROOT / rel
        try:
            with Image.open(path) as image:
                kind = image.format
                if kind == "PNG":
                    image.verify()
                elif kind == "JPEG":
                    if path.read_bytes().rstrip(b"\x00")[-2:] != b"\xff\xd9":
                        raise OSError("JPEG 没收在 EOI（FFD9）——文件是半截的")
                else:
                    image.load()
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{rel}: {type(exc).__name__}: {exc}")
    assert not bad, "这些图解不开：\n  " + "\n  ".join(bad)


# ────────────────────────────────────────────────────────── ④ 封面复用 ──

def _reuse_world(tmp_path: Path) -> dict:
    specs, ledger, output = tmp_path / "specs", tmp_path / "ledger", tmp_path / "output"
    for folder in (specs, ledger, output, tmp_path / "assets"):
        folder.mkdir()
    photo = _jpg(tmp_path / "assets" / "wang-garland.jpg")
    (tmp_path / "assets" / "wang-copy.jpg").write_bytes(photo)          # 同一张图、换了个名
    sent = {"slug": "wang-garland", "cover": {"portrait": {"image": "assets/wang-garland.jpg"}}}
    (specs / "wang-garland.json").write_text(json.dumps(sent), encoding="utf-8")
    (ledger / "wang-garland.json").write_text(json.dumps({"attempts": [
        {"status": "rejected", "at": "2026-09-24T09:00:00Z"},
        {"status": "sent", "at": "2026-09-24T10:41:46Z"}]}), encoding="utf-8")
    return {"specs": specs, "ledger": ledger, "output": output, "root": tmp_path,
            "legacy_set": NONE}


def test_封面照片已经在另一条发出去过就红(tmp_path):
    kw = _reuse_world(tmp_path)
    ledger = kw["ledger"]
    new = {"slug": "wang-prozorova", "cover": {"portrait": {"image": "assets/wang-garland.jpg"}}}
    problem = gates.cover_reuse_problem(new, **kw)
    assert problem and "wang-garland" in problem and "2026-09-24T10:41:46Z" in problem
    # 换了文件名、内容一样也认得出（按大小＋哈希）
    new["cover"]["portrait"]["image"] = "assets/wang-copy.jpg"
    assert gates.cover_reuse_problem(new, **kw)
    # 认领口
    assert gates.cover_reuse_problem({**new, "_cover_reuse_why": "系列片沿用"}, **kw) is None
    # 按要求重做（revision_of 互指）不算
    assert gates.cover_reuse_problem({**new, "revision_of": "wang-garland"}, **kw) is None
    # 我比它先发出去：不是我借了它的图
    (ledger / "wang-prozorova.json").write_text(json.dumps({"attempts": [
        {"status": "sent", "at": "2026-09-20T00:00:00Z"}]}), encoding="utf-8")
    assert gates.cover_reuse_problem(new, **kw) is None
    # 它只是 rejected、从没 sent 过：也不算
    (ledger / "wang-prozorova.json").unlink()
    (ledger / "wang-garland.json").write_text(json.dumps({"attempts": [
        {"status": "rejected", "at": "2026-09-24T09:00:00Z"}]}), encoding="utf-8")
    assert gates.cover_reuse_problem(new, **kw) is None


def test_封面复用的先后要认账本之前发的pushed_json(tmp_path):
    """发布账本 2026-08-24 才有；更早发的片子只在 `output/<日期>/reel/<slug>/pushed.json`。
    只认账本的话方向会整个反过来：wangxiyu-keys（08-20 发）被判成「借了
    asiad-2026-women-draw（09-27 发）的图」——全库扫出来的第一个误报就是这个形状。"""
    kw = _reuse_world(tmp_path)
    (kw["ledger"] / "wang-garland.json").unlink()                        # 它在账本之前发的
    pushed = kw["output"] / "2026-08-20" / "reel" / "wang-garland"
    pushed.mkdir(parents=True)
    (pushed / "pushed.json").write_text(json.dumps({"at": "2026-08-20T09:13:38Z"}),
                                        encoding="utf-8")
    new = {"slug": "asiad-draw", "cover": {"portrait": {"image": "assets/wang-copy.jpg"}}}
    assert "2026-08-20T09:13:38Z" in gates.cover_reuse_problem(new, **kw)
    # 反过来问老片子：它先发，后来者借它的图不算它的错
    (kw["specs"] / "asiad-draw.json").write_text(json.dumps(new), encoding="utf-8")
    (kw["ledger"] / "asiad-draw.json").write_text(json.dumps({"attempts": [
        {"status": "sent", "at": "2026-09-27T06:16:40Z"}]}), encoding="utf-8")
    old = json.loads((kw["specs"] / "wang-garland.json").read_text(encoding="utf-8"))
    assert gates.cover_reuse_problem(old, **kw) is None


def test_runner上看不见老片子发没发过_借图的一方认领了就不反咬原主(tmp_path):
    """runner 的稀疏检出没有 `output/`，08-24 之前发的片子在那儿「没发过」。
    原主（账本里没有）对上一个已发、**已认领借图**的后来者：不算原主的错，本地和
    runner 一样绿。后来者没认领的话照旧红——那一条在本地就先红了、先要认领。"""
    kw = _reuse_world(tmp_path)
    (kw["ledger"] / "wang-garland.json").unlink()               # 原主：runner 上查不到它发过
    borrower = {"slug": "asiad-draw", "_cover_reuse_why": "签表片借她 R2 那张",
                "cover": {"portrait": {"image": "assets/wang-copy.jpg"}}}
    (kw["specs"] / "asiad-draw.json").write_text(json.dumps(borrower), encoding="utf-8")
    (kw["ledger"] / "asiad-draw.json").write_text(json.dumps({"attempts": [
        {"status": "sent", "at": "2026-09-27T06:16:40Z"}]}), encoding="utf-8")
    origin = json.loads((kw["specs"] / "wang-garland.json").read_text(encoding="utf-8"))
    assert gates.cover_reuse_problem(origin, **kw) is None
    kw["legacy_set"] = frozenset({"asiad-draw"})                 # 挂在豁免表里也算认领
    del borrower["_cover_reuse_why"]
    (kw["specs"] / "asiad-draw.json").write_text(json.dumps(borrower), encoding="utf-8")
    assert gates.cover_reuse_problem(origin, **kw) is None
    kw["legacy_set"] = NONE                                      # 谁都没认领：原主这头也红
    assert gates.cover_reuse_problem(origin, **kw)


# ─────────────────────────────────────────────────────── ⑥ 字幕里的数字 ──

def _narrated(text: str) -> dict:
    return {"slug": "fixture-reel", "segments": [
        {"narration": text}, {"quote": "Wow\n哇", "narration": ""}]}


@pytest.mark.parametrize("text", [
    "七比六六比四，贝莱克掀翻了世界第一。",       # → 7比6比四（bejlek-sabalenka 已发）
    "他六比三七比五拿下西西帕斯。",               # → 6比7比五
    "科斯秋克照样四比六六比零六比二逆转。",       # → 4比6比6比2
])
def test_字幕里两个比分粘成一个在dry_run就红(text):
    problems = gates.numeral_display_problems(_narrated(text), legacy_set=NONE)
    assert problems and "顿号" in problems[0], problems


@pytest.mark.parametrize("shown", [
    "两小时40分钟",          # 288ed727 之前那种「换算只接了一半」
    "北京时间9月一号",
    "12胜三负",
    "四分之一决赛",
    "赢了12三局",            # 兜底：汉字数字贴着阿拉伯数字
    "前三12名",
])
def test_换算只换了一半的形状在dry_run就红(shown, monkeypatch):
    """换算规则现在接住了这几种（numeral_halves / 288ed727），所以直接喂「字幕已经
    印成这样」的那一行：下一种没接住的结构长这样时，dry-run 要红。"""
    import tennislive.video.explainer as ex
    monkeypatch.setattr(ex, "subtitle_lines", lambda text: [(0, len(text), shown)])
    problems = gates.numeral_display_problems(_narrated("占位。"), legacy_set=NONE)
    assert problems and "一半阿拉伯一半中文" in problems[0], (shown, problems)


@pytest.mark.parametrize("text", [
    "七比六、六比四，贝莱克掀翻了世界第一。",
    "他六比三，七比五拿下西西帕斯。",
    "两小时四十分钟，三盘。",                     # 换算规则补上之后这一类不再半截
    "而光第二盘就打了一小时十二。",               # sabalenka-gibson 那一处
    "北京时间九月一号凌晨快四点。",
    "十二胜三负。",
    "抢七七比九，第二盘开始了。",                 # 抢七是术语：→ 抢七7比9
    "四分之一决赛对萨菲乌林。",
    "第一次打进WTA1000八强。",                    # N 强是轮次名（bejlek-keys 那一句），归轮次那条规矩
    "一小时十几分钟。",                           # 约数：两半都留中文
])
def test_字幕数字换算正常的不许误报(text):
    assert gates.numeral_display_problems(_narrated(text), legacy_set=NONE) == []


def test_字幕数字的认领口和豁免():
    spec = _narrated("七比六六比四。")
    assert gates.numeral_display_problems(
        {**spec, "_numeral_display_why": "故意"}, legacy_set=NONE) == []
    assert gates.numeral_display_problems(spec, legacy_set=frozenset({"fixture-reel"})) == []


def test_同一个数不许一半中文一半阿拉伯():
    """`arabic_numerals` 对裸「一」「两」、以及不跟量词的数不动（「唯一一次」「两盘」
    「三分之一」要留住），可同一个数的另一截照换——于是「两小时40分钟」「9月一号」
    「12胜三负」。2026-09-27 全库字幕按行换算量出时长 111、日期 12、胜负 4 处
    （98 条 spec），`numeral_halves.other_half_is_arabic` 补上这三种结构；
    另一半不在场的照旧不动。"""
    from tennislive.video import explainer, numeral_halves
    A = explainer.arabic_numerals
    assert set(numeral_halves.NUM) == explainer._NUM_CHARS, "两边的数字字表分叉了"  # noqa: SLF001
    for src, want in [
        ("两小时四十分钟", "2小时40分钟"), ("一小时四十八分钟", "1小时48分钟"),
        ("三小时二十四分钟", "3小时24分钟"), ("两小时零八分", "2小时8分"),
        ("两小时五分钟", "2小时5分钟"), ("两个小时四十分钟", "2个小时40分钟"),
        ("一小时十二", "1小时12"), ("一小时十二局", "1小时12局"),
        ("北京时间九月一号凌晨", "北京时间9月1号凌晨"), ("八月一日", "8月1日"),
        ("一月十九号", "1月19号"), ("十二胜三负", "12胜3负"), ("五胜十九负", "5胜19负"),
        ("十胜两负", "10胜2负"), ("三胜一负", "3胜1负"),
    ]:
        assert A(src) == want, f"{src} → {A(src)}，应该是 {want}"
    for src in ("一小时之后", "打了两小时", "两胜", "一月", "唯一一次", "两盘", "三分之一",
                "一发", "第一次", "有一点点慢", "一小时十几分钟"):
        assert A(src) == src, f"{src} 被误伤成 {A(src)}"


# ─────────────────────────────────────────────────── 全库：零误报、只许减 ──

def _specs():
    for path in sorted((ROOT / "specs" / "reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        yield str(spec.get("slug") or path.stem), spec


def test_全库存量对新闸零误报():
    """用户可见的每一道都扫全库：不在豁免表里的，一条都不许红。

    图片这里只查**在不在**（整张解码 300 条 spec 要 20 秒，交给 dry-run 按条做；
    坏块由 `test_仓库里的图都解得开` 在全库那一层兜住）。
    """
    bad = []
    for slug, spec in _specs():
        found = [gates.duration_problem(spec), gates.stats_card_problem(spec),
                 gates.cover_reuse_problem(spec), *gates.numeral_display_problems(spec)]
        found += [f"{where} 指的 {rel} 不在"
                  for where, rel in gates._images_in(spec) if not (ROOT / rel).is_file()]
        bad += [f"{slug}: {p.splitlines()[0]}" for p in found if p]
    assert not bad, "新闸在存量上红了：\n  " + "\n  ".join(bad)


def test_runner视角下封面复用那道闸和本地一样零误报():
    """runner 上不检出 `output/`（只剩发布账本）。这道闸在那儿要么和本地一样判，
    要么少报——**不许多报**：多报就是本地绿、runner 红，正是这次要消掉的分叉。"""
    no_output = ROOT / "does-not-exist-output"
    bad = [slug for slug, spec in _specs()
           if gates.cover_reuse_problem(spec, output=no_output)]
    assert not bad, f"runner 视角下这几条会红、本地却是绿的：{bad}"


@pytest.mark.parametrize("kind,check,cap", [
    ("no_stats", lambda s: gates.stats_card_problem(s, legacy_set=NONE), 53),
    ("cover_reuse", lambda s: gates.cover_reuse_problem(s, legacy_set=NONE), 7),
    ("numeral_display", lambda s: gates.numeral_display_problems(s, legacy_set=NONE), 12),
])
def test_豁免表只许减不许加(kind, check, cap):
    legacy = gates.legacy(kind)
    assert legacy, f"{kind} 豁免表读不到——路径或键名写错了，整条判据会静静失效"
    seen = dict(_specs())
    missing = sorted(s for s in legacy if s not in seen)
    assert not missing, f"{kind} 豁免表里的 slug 不存在：{missing}"
    fixed = sorted(s for s in legacy if not check(seen[s]))
    assert not fixed, f"这些已经过了 {kind} 那道闸，从豁免表里删掉：{fixed}"
    # 2026-09-27 定规矩那天量出来的条数；只许往下走
    assert len(legacy) <= cap


# ────────────────────────────────────────────────── 真的接上了：dry-run ──

def test_validate_spec接了这道闸():
    spec = reel.load_spec(ROOT / "specs" / "reels" / "medvedev-royer-hangzhou-2026-r2.json")
    reel.validate_spec(spec)                       # 原样是绿的
    spec["cover"]["scoreboard"]["duration_source"]["url"] = _data_url("1:49")
    with pytest.raises(reel.ReelError, match="两段式"):
        reel.validate_spec(spec)


def test_dry_run的推送标题和runner同一个函数(tmp_path, monkeypatch, capsys):
    """原来 dry-run 自己拼标题、拿 `/tmp/dryrun` 调 `headline()`，永远取不到日期、
    退回占位标题——`push.summary` 写到 26 字位，本地退出 0，runner 上的
    production_preflight 退出 1。现在两边都走 `push_reel.prepare_copy`。"""
    slug = "medvedev-royer-hangzhou-2026-r2"
    src = ROOT / "specs" / "reels"
    spec = json.loads((src / f"{slug}.json").read_text(encoding="utf-8"))
    spec["push"]["summary"] = "梅德韦杰夫直落两盘击败去年杭州亚军鲁瓦耶进八强"
    (tmp_path / f"{slug}.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    shutil.copy(src / f"{slug}.xhs.txt", tmp_path / f"{slug}.xhs.txt")
    _t, _b, problem = gates.push_copy_check(tmp_path / f"{slug}.xhs.txt", date="2026-09-27")
    assert problem and "超过 13" in problem, problem
    monkeypatch.setattr(sys, "argv", ["build_match_reel.py", "render", "--dry-run",
                                      "--spec", str(tmp_path / f"{slug}.json"),
                                      "--outdir", str(tmp_path / "dry")])
    assert reel.main() == 1
    assert "推送文案前置检查不过" in capsys.readouterr().out
