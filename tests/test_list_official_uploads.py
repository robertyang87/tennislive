"""官方频道 36 小时内的上传：列出来、对 spec.sources、dry-run 离线印没用上的（只报不拦）。

来路：`eala-jovic-us-open-2026-r3` 漏了美网官方频道的出场视频（5053eafb，账号所有者
点名要加）；`osaka-four-slams-2026` 九月一号发、源片当天上传，封面却是六月温网的图
（3a82caee）。两次都是**东西一直在，只是没人去列一遍**。
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import list_official_uploads as lu  # noqa: E402

NOW = dt.datetime(2026, 9, 1, 12, 0, tzinfo=dt.timezone.utc)


def _feed(channel_id: str, items: list[tuple[str, str, str]]) -> str:
    """最小的上传 RSS：`(video_id, title, published)`。频道身份照 YouTube 的写法去掉 UC。"""
    body = "".join(
        f"<entry><yt:videoId>{vid}</yt:videoId><title>{title}</title>"
        f"<published>{when}</published></entry>" for vid, title, when in items)
    return (f'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" '
            f'xmlns:yt="http://www.youtube.com/xml/schemas/2015">'
            f"<yt:channelId>{channel_id[2:]}</yt:channelId>{body}</feed>")


def _playlist(items: list[tuple[str, str, str]]) -> str:
    """上传列表页里那份 ytInitialData：`(video_id, title, "12h ago")`。"""
    locks = [{"lockupViewModel": {
        "contentId": vid,
        "metadata": {"lockupMetadataViewModel": {
            "title": {"content": title},
            "metadata": {"contentMetadataViewModel": {"metadataRows": [
                {"metadataParts": [{"text": {"content": "US Open Tennis Championships"}}]},
                {"metadataParts": [{"text": {"content": "7.1K"}},
                                   {"text": {"content": age}}]}]}}}}}}
        for vid, title, age in items]
    return ("<script>var ytInitialData = " + json.dumps({"contents": locks})
            + ";</script>")


def test_按姓认要整词去重音():
    assert lu.title_hits("Bublik vs Mensik | Laver Cup", ["Bu"]) == []
    assert lu.title_hits("Bu Yunchaokete vs. Kamil Majchrzak Highlights", ["Bu"]) == ["Bu"]
    assert lu.title_hits("Karolina Muchová wins in Seoul", ["Muchova"]) == ["Muchova"]
    assert lu.title_hits("Felix Auger-Aliassime reacts", ["Auger-Aliassime"]) \
        == ["Auger-Aliassime"]
    assert lu.title_hits("Alex de Minaur's walkout", ["Minaur"]) == ["Minaur"]


def test_spec里认英文姓_中国球员两个词都认():
    spec = {"cover": {"matchup": [
        {"name": "布云朝克特", "name_en": "Yunchaokete Bu", "country": "CHN"},
        {"name": "迈赫扎克", "name_en": "Kamil Majchrzak", "country": "POL"}]}}
    assert lu.spec_surnames(spec) == ["Bu", "Yunchaokete", "Majchrzak"]
    assert lu.spec_surnames({"_match": {"winner_en": "Alex de Minaur"}}) == ["Minaur"]
    assert lu.spec_surnames({"cover": {}}) == []
    # 双打一边是「A / B」、country 是列表：四个人都要认出来（原来整串只取最后一个词）
    doubles = {"cover": {"matchup": [
        {"name_en": "C. Alcaraz / J. Mensik", "country": ["ESP", "CZE"]},
        {"name_en": "A. Bublik / T. Fritz", "country": ["KAZ", "USA"]}]}}
    assert lu.spec_surnames(doubles) == ["Alcaraz", "Mensik", "Bublik", "Fritz"]
    assert lu.spec_surnames({"cover": {"matchup": [
        {"name_en": "Zhang Shuai / Wang Xinyu", "country": ["CHN", "CHN"]}]}}) \
        == ["Shuai", "Zhang", "Xinyu", "Wang"]
    assert lu.used_video_ids({"sources": {
        "a": "https://www.youtube.com/watch?v=Fphz30iUGMw",
        "b": "https://youtu.be/eZSXaGpkmsU",
        "c": "https://www.tennistv.com/videos/4582104/x"}}) == {"Fphz30iUGMw", "eZSXaGpkmsU"}


def test_列表页的相对时间换成最晚可能时刻并标约数():
    rows = lu.parse_uploads_page(_playlist([
        ("aaaaaaaaaaa", "Naomi Osaka Stuns in her Walk-Out Outfit!", "12h ago"),
        ("bbbbbbbbbbb", "Osaka vs Zakharova Highlights", "1d ago"),
        ("ccccccccccc", "Old one", "Streamed 13d ago")]), NOW)
    got = {r["video_id"]: r for r in rows}
    assert got["aaaaaaaaaaa"]["published"] == NOW - dt.timedelta(hours=12)
    assert got["bbbbbbbbbbb"]["published"] == NOW - dt.timedelta(hours=24)
    assert got["ccccccccccc"]["published"] == NOW - dt.timedelta(days=13)
    assert all(r["approx"] for r in rows)


def test_RSS被截断要翻列表页补而且要说出来():
    """大满贯期间美网频道一天几十条，RSS 只给 15 条——最早那条还在窗口里就说明截断了。"""
    cid = "UCXbboag48Qlr78zzz6SkzkQ"
    recent = [(f"v{i:010d}", f"clip {i}", (NOW - dt.timedelta(hours=i)).isoformat())
              for i in range(1, 16)]                          # 15 条全在 36 小时内
    feed = _feed(cid, recent)
    page = _playlist([("Fphz30iUGMw", "Alex Eala's walkout at Arthur Ashe", "20h ago"),
                      ("zzzzzzzzzzz", "Too old", "3d ago")])

    def get(url):
        return feed if "feeds/videos.xml" in url else page

    entries, notes = lu.fetch_uploads({"USOPEN": cid}, now=NOW, get=get)
    ids = {e["video_id"] for e in entries}
    assert "Fphz30iUGMw" in ids, "截断之后没去翻列表页——出场视频就是这么漏掉的"
    assert "zzzzzzzzzzz" not in ids
    assert any("15 条全在窗口里" in n for n in notes), notes

    # 没截断就不翻：RSS 最早一条已经出了窗口
    old = recent[:5] + [("oldoldoldol", "old", (NOW - dt.timedelta(hours=60)).isoformat())]
    entries, notes = lu.fetch_uploads({"USOPEN": cid}, now=NOW,
                                      get=lambda url: _feed(cid, old)
                                      if "feeds" in url else pytest.fail("不该翻列表页"))
    assert len(entries) == 5 and not notes


def test_取不到的频道要说没查():
    def get(url):
        raise OSError("boom")
    entries, notes = lu.fetch_uploads({"WTA": "UCaBIVVpHjq6j3tSyxwTE-8Q"}, now=NOW, get=get)
    assert not entries and "没查" in notes[0]


def _snapshot(entries, fetched=NOW):
    return {"slug": "eala-jovic-us-open-2026-r3", "fetched_at": fetched.isoformat(),
            "hours": 36, "surnames": ["Eala", "Jovic"], "channels": ["USOPEN"],
            "notes": [], "entries": entries}


def test_没用上的官方上传要列出来_用上的不列():
    spec = {"slug": "eala-jovic-us-open-2026-r3",
            "sources": {"main": "https://www.youtube.com/watch?v=MAINMAINMAI"}}
    snap = _snapshot([
        {"video_id": "MAINMAINMAI", "title": "Alex Eala vs. Iva Jovic Highlights",
         "published": (NOW - dt.timedelta(hours=3)).isoformat(), "channel": "USOPEN"},
        {"video_id": "Fphz30iUGMw", "title": "Alex Eala walks out to Arthur Ashe",
         "published": (NOW - dt.timedelta(hours=5)).isoformat(), "channel": "USOPEN"},
        {"video_id": "OTHEROTHERO", "title": "Sinner vs Shelton Highlights",
         "published": (NOW - dt.timedelta(hours=2)).isoformat(), "channel": "USOPEN"}])
    text = "\n".join(lu.report_lines(spec, snap, now=NOW))
    assert "没用上的 1 条" in text, text
    assert "Fphz30iUGMw" in text and "MAINMAINMAI" not in text.split("没用上的")[1]
    assert "OTHEROTHERO" not in text, "标题里没这两个人的不该列"

    stale = "\n".join(lu.report_lines(spec, _snapshot([], NOW - dt.timedelta(hours=40)),
                                      now=NOW))
    assert "过期" in stale


def test_dry_run离线读快照_没有快照就给命令(tmp_path, monkeypatch):
    monkeypatch.setenv("TENNISLIVE_UPLOADS_CACHE", str(tmp_path))
    spec = {"slug": "eala-jovic-us-open-2026-r3",
            "cover": {"matchup": [{"name_en": "Alex Eala"}, {"name_en": "Iva Jovic"}]},
            "sources": {"main": "https://www.youtube.com/watch?v=MAINMAINMAI"}}
    lines = lu.dry_run_lines(spec, "specs/reels/eala-jovic-us-open-2026-r3.json", now=NOW)
    assert len(lines) == 1 and "list_official_uploads.py --spec" in lines[0]
    lu.save_snapshot(spec["slug"], _snapshot([
        {"video_id": "Fphz30iUGMw", "title": "Alex Eala walks out to Arthur Ashe",
         "published": (NOW - dt.timedelta(hours=5)).isoformat(), "channel": "USOPEN"}]))
    text = "\n".join(lu.dry_run_lines(spec, None, now=NOW))
    assert "Fphz30iUGMw" in text and "没用上的 1 条" in text


def _jpeg_with_capture(path: Path, stamp: str) -> Path:
    from PIL import Image

    img = Image.new("RGB", (40, 30), (120, 80, 40))
    exif = Image.Exif()
    exif.get_ifd(0x8769)[36867] = stamp
    img.save(path, exif=exif)
    return path


def test_封面比这条片子的源片旧就提醒(tmp_path):
    """osaka-four-slams：源片 walk 9/01 上传，封面是 6/29 温网那张（EXIF）。"""
    old = _jpeg_with_capture(tmp_path / "old.jpg", "2026:06:29 15:36:55")
    new = _jpeg_with_capture(tmp_path / "new.jpg", "2026:08:31 23:50:00")
    spec = {"cover": {"portrait": {"image": str(old)}},
            "sources": {"walk": "https://www.youtube.com/watch?v=eZSXaGpkmsU"}}
    snap = {"entries": [{"video_id": "eZSXaGpkmsU", "channel": "USOPEN",
                         "published": "2026-09-01T03:00:00+00:00"}]}
    msg = lu.stale_cover_problem(spec, snap)
    assert msg and "2026-06-29" in msg and "64 天" in msg, msg
    # 夜场：当地 8/31 拍、9/01 上传——正常差，不报
    spec["cover"]["portrait"]["image"] = str(new)
    assert lu.stale_cover_problem(spec, snap) is None
    # 没有「这一天」的证据就不判（讲历史的片子封面本来可以是旧图）
    spec["cover"]["portrait"]["image"] = str(old)
    assert lu.stale_cover_problem(spec, {"entries": []}) is None
    # `_match` 的开球时刻也算证据
    assert lu.stale_cover_problem(
        {**spec, "_match": {"start_utc": "2026-08-22T00:19:44Z"}}, None)
    # 讲历史、故意用当年的图：认领了就不提醒
    claimed = {"cover": {"portrait": {"image": str(old), "_old_photo_why": "讲 2025 年那座杯"}},
               "sources": spec["sources"]}
    assert lu.stale_cover_problem(claimed, snap) is None
    # 快照里别的片子的源片不算（不是这条片子的素材）
    other = {"entries": [{"video_id": "zzzzzzzzzzz", "published": "2026-09-01T03:00:00Z"}]}
    assert lu.stale_cover_problem(spec, other) is None


def test_dry_run真的印官方上传那一段而且不碰网络(tmp_path):
    """真跑一遍 `render --dry-run`：那一段要出现、退出码 0、秒级返回（它只读快照）。"""
    env = {**__import__("os").environ, "TENNISLIVE_UPLOADS_CACHE": str(tmp_path),
           "PYTHONPATH": f"{ROOT / 'src'}:{ROOT / 'tools'}"}
    spec = json.loads((ROOT / "specs/reels/tiafoe-musetti-cincinnati-2026-qf.json")
                      .read_text(encoding="utf-8"))
    path = tmp_path / "tiafoe-musetti-cincinnati-2026-qf.json"
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/build_match_reel.py"), "render",
         "--spec", str(path), "--outdir", str(tmp_path / "out"), "--dry-run"],
        capture_output=True, text=True, timeout=120, cwd=ROOT, env=env, check=False)
    assert proc.returncode == 0, proc.stderr[-600:]
    assert "[官方上传]" in proc.stdout, proc.stdout[-1500:]
    assert time.perf_counter() - started < 30


def test_全库赛场之上跑一遍报告_不许出错():
    """扫全部 spec：没有快照时每条都只印一行，不许抛异常（它挂在 dry-run 上）。"""
    import os

    old = os.environ.get("TENNISLIVE_UPLOADS_CACHE")
    os.environ["TENNISLIVE_UPLOADS_CACHE"] = str(ROOT / ".no-such-cache-dir")
    try:
        n = 0
        for path in sorted((ROOT / "specs" / "reels").glob("*.json")):
            spec = json.loads(path.read_text(encoding="utf-8"))
            lines = lu.dry_run_lines(spec, str(path.relative_to(ROOT)))
            assert lines and lines[0].startswith("[官方上传]"), (path.name, lines)
            n += 1
        assert n > 250
    finally:
        if old is None:
            os.environ.pop("TENNISLIVE_UPLOADS_CACHE", None)
        else:
            os.environ["TENNISLIVE_UPLOADS_CACHE"] = old
