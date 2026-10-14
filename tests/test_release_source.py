"""probe 有 Release 存档就用存档、yt-dlp 不许无限期挂着（2026-10-12 那趟挂了 23 分钟）。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_match_reel as reel  # noqa: E402
import probe_claims  # noqa: E402
import release_source  # noqa: E402

YT = "https://m.youtube.com/watch?v=y9d6IHw0cZk"
REL = ("https://github.com/robertyang87/tennislive/releases/download/"
       "source-y9d6IHw0cZk/y9d6IHw0cZk.mp4")


def test_有存档就改用Release直链():
    got, why = release_source.resolve(YT, "robertyang87/tennislive", exists=lambda u: u == REL)
    assert got == REL, why


def test_没有存档或不是YouTube就原样返回():
    assert release_source.resolve(YT, "robertyang87/tennislive",
                                  exists=lambda u: False)[0] == YT
    direct = "https://example.com/a.mp4"
    assert release_source.resolve(direct, "robertyang87/tennislive",
                                  exists=lambda u: True)[0] == direct


def test_Release地址和YouTube地址是同一个去重键():
    """不认的话，probe 改用存档之后去重和认领会把它当成另一条源片。"""
    assert probe_claims.video_key(REL) == probe_claims.video_key(YT) == "y9d6IHw0cZk"


def test_probe和自动草稿用的是同一个解析后的地址():
    """probe.json 的 url 和草稿的 source_url 按 URL 对账，两边必须是同一个。"""
    wf = yaml.safe_load((ROOT / ".github/workflows/match-reel.yml").read_text(encoding="utf-8"))
    steps = [s for job in wf["jobs"].values() for s in job.get("steps") or []]
    names = [s.get("name", "") for s in steps]
    resolve_at = names.index("probe — 有 Release 存档就用存档")
    probe_at = names.index("probe — 下载 + 缩略图墙")
    assert resolve_at < probe_at
    resolved = "steps.src.outputs.url || github.event.inputs.url"
    assert resolved in steps[probe_at]["run"]
    drafts = [s for s in steps if "--source-url" in (s.get("run") or "")]
    assert drafts and all(resolved in s["run"] for s in drafts)


def test_yt_dlp带socket超时():
    assert "--socket-timeout" in reel.YTDLP_BASE


def test_梯子里某一档挂住会超时换下一档(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(kw.get("timeout"))
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
        Path(cmd[cmd.index("-o") + 1]).write_bytes(b"x" * 100)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(reel.subprocess, "run", fake_run)
    monkeypatch.setattr(reel, "probe_size", lambda p: (1920, 1080))
    monkeypatch.setattr(reel, "_cached_source", lambda *a, **k: None)
    monkeypatch.setattr(reel, "_keep_source", lambda *a, **k: None)
    monkeypatch.setattr(reel, "_resolve_media_url", lambda u: u)
    monkeypatch.setattr(reel.shutil, "which", lambda name: "/usr/bin/yt-dlp")
    out = reel._download_one(YT, tmp_path / "src.mp4")
    assert out.is_file()
    assert len(calls) == 2 and all(t == reel.YTDLP_ATTEMPT_TIMEOUT for t in calls)


def test_probe用了Release存档_dry_run照样按YouTube地址认领上():
    """probe.json 的 url 是 Release 直链，spec 写 YouTube 地址——按视频 id 认（梅西恩怨片十条源一条都没认上）。"""
    import probe_sources

    assert probe_sources.spec_url_for(REL, [YT]) == YT
    assert probe_sources.spec_url_for(YT, [YT]) == YT
    assert probe_sources.spec_url_for(REL, ["https://www.youtube.com/watch?v=aaaaaaaaaaa"]) is None
    assert probe_sources.spec_url_for("https://example.com/a.mp4", [YT]) is None


def test_claim_probes按视频id认领并换成spec里的地址(tmp_path, monkeypatch):
    import json as _json

    d = tmp_path / "output/2026-10-15/reel/x"
    d.mkdir(parents=True)
    (d / "probe.json").write_text(_json.dumps({"url": REL, "scene_cuts": [1.0]}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    found, missing = reel.claim_probes({"sources": {"a": YT}})
    assert missing == [] and found[YT][1]["url"] == YT and found[YT][1]["_probed_url"] == REL


def test_原地址探过的probe优先_不被Release存档那份盖掉(tmp_path, monkeypatch):
    """原地址那份可能带着人给的 --scorebox 量的死球时刻；按存档重探的没有——盖掉会让段尾硬闸失明。"""
    import json as _json
    import probe_sources

    for day, url, cuts in (("2026-10-14", YT, [1.0]), ("2026-10-15", REL, [2.0])):
        d = tmp_path / f"output/{day}/reel/x"
        d.mkdir(parents=True)
        (d / "probe.json").write_text(_json.dumps({"url": url, "scene_cuts": cuts}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    found, _missing = reel.claim_probes({"sources": {"a": YT}})
    assert found[YT][1]["scene_cuts"] == [1.0]
    assert probe_sources.probe_for(YT, {REL: {"k": 2}, YT: {"k": 1}}) == {"k": 1}
    assert probe_sources.probe_for(YT, {REL: {"k": 2}}) == {"k": 2}
