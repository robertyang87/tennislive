"""源片与 probe 的健壮性（2026-09-28 返工审计「22 趟不回放的失败」那一包）。

审计里 82 趟失败 run，有 22 趟是 probe／外部源／基础设施，当时判为「不回放」。按形状拆开，
七类都有一个便宜的判据，这一份把它们钉住，**每一条都拿当时那一趟的真实输入回放**：

| 类 | 趟数 | 当时 | 现在 |
|---|---|---|---|
| YouTube cookie 失效 | 5 | 09-19 17:15–22:52Z 只有会话手动拨的 run 在红，Q9 不推 | source-health 每 6 小时派发 `mode=cookies`，红了按 `match-reel:cookies` 推一次 |
| cookies 自检传了搜索词 | 1 | 搜出 0 条，报「没下到媒体流」 | 第一步红：「是搜索词不是视频」 |
| probe 空 URL＋默认 slug | 1 | 第 1.4 分钟 `curl: (3)` | 第一步红，两处都点名 |
| X CDN 直链 403 | 2 | 一句 curl 403 | 主地址写帖子地址、下载时现解；直链只当 `source_fallbacks` |
| 1080p 的框配 720p 源 | 2 | 源片下完才红，probe 产物全丢 | 按高度等比缩（`98,920,519,1029` → `65,613,346,686`），probe 照样出完 |
| 派发 render 的 assert 撞手写 spec | 1 | 裸 AssertionError | `[skip]`，自动 spec 的合同照旧硬 |
| frame-grab 推送 5 次失败 | 1 | 睡在 fetch 和 push 之间，每一轮都撞车 | 共享重试：先睡、再 rebase、立刻推 |
| 上游 HTTP 5xx（备料） | 1 | 那一趟其实是 MiniMax 500（base 47f9f2b6d 已降级）；flashscore 这一侧 SystemExit 穿过 `except Exception` | feed 先重试，assemble 接住 SystemExit 只报；**matchup 归位核不出不退回命令行顺序**，按 home/away 排的几块整块不写 |

`assemble_spec --year ''`（3 趟）在 base 的 09e091851 已修，`test_match_reel_optional_int_inputs` 钉着。
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_match_reel as reel  # noqa: E402
import probe_dispatch_gate as gate  # noqa: E402
import source_url_check as suc  # noqa: E402

WORKFLOWS = ROOT / ".github" / "workflows"


def _yaml(name: str) -> dict:
    import yaml  # noqa: PLC0415

    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _steps(name: str, job: str) -> list[dict]:
    return _yaml(name)["jobs"][job]["steps"]


def _step(name: str, job: str, title: str) -> dict:
    hits = [s for s in _steps(name, job) if s.get("name") == title]
    assert len(hits) == 1, f"{name} 里找不到（或不止一个）步骤「{title}」"
    return hits[0]


# ── ③ 表单自检：空 URL／默认 slug／搜索词／框格式，第一步就红 ─────────────────

def test_表单默认slug读的就是yml里那一份():
    """自检认的「默认 slug」只许从 yml 读，不许自己再写一份（写两处必分叉）。"""
    form = _yaml("match-reel.yml")[True]["workflow_dispatch"]["inputs"]
    assert suc.form_default("slug") == form["slug"]["default"] == "eala-zheng"
    assert suc.form_default("url") == form["url"]["default"] == ""
    assert suc.form_default("不存在的输入") is None


def test_回放_空URL加默认slug的probe在第一步红_两处都点名():
    """run 36304133786：url 空、slug 还是 eala-zheng，原来第 1.4 分钟才红在 curl: (3)。"""
    problems = suc.probe_problems("", "eala-zheng", "", default_slug=suc.form_default("slug"))
    assert len(problems) == 2, problems
    assert "url` 是空的" in problems[0] and "eala-zheng" in problems[1]
    assert suc.main(["--mode", "probe", "--url", "", "--slug", "eala-zheng"]) == 1


def test_默认slug的老片子自己的源片_重probe放行_换地址照旧红(tmp_path):
    """默认 slug 那一条原来没有出口：`eala-zheng` 这条已发片子一趟都重 probe 不了。
    认领口是 `url` 就是它 spec 里那条源片；换一条地址顶着默认 slug 照旧红。"""
    default = suc.form_default("slug")
    own = suc.published_source_urls(default)
    assert own, f"specs/reels/{default}.json 里读不出源片地址——认领口是哑的"
    assert suc.probe_problems(next(iter(own)), default, "", default_slug=default) == []
    other = "https://www.youtube.com/watch?v=aINLTXtRWbE"
    assert other not in own
    (problem,) = suc.probe_problems(other, default, "", default_slug=default)
    assert default in problem and "url` 填它 spec 里那条源片" in problem
    # 读不到那份 spec（被删、目录不对）就一律按「没改」红，不许因为读不到而放行
    assert suc.probe_problems(next(iter(own)), default, "", default_slug=default,
                              specs=tmp_path) != []


def test_回放_cookies自检传了搜索词_第一步就说它是搜索词():
    """run 35478525370：`ytsearch8:…` 搜出 0 条，原来报「没下到媒体流」，看着像 cookie 坏了。"""
    term = "ytsearch8:Davis Cup 2026 Norway China doubles highlights Kjaer Durasovic"
    (problem,) = suc.cookies_problems(term)
    assert "搜索词" in problem
    assert suc.main(["--mode", "cookies", "--url", term]) == 1
    # cookies 模式 url 可以空（用默认视频），填了真视频地址放行
    assert suc.cookies_problems("") == []
    assert suc.cookies_problems("https://www.youtube.com/watch?v=HyKTXynnI9c") == []


def test_合法的probe表单不误伤_框格式错才红():
    ok = suc.probe_problems("https://www.youtube.com/watch?v=aINLTXtRWbE",
                            "medvedev-wong-hangzhou-2026-qf", "98,920,519,1029",
                            default_slug="eala-zheng")
    assert ok == []
    for bad in ("1,2,3", "a,b,c,d", "100,10,50,20", "-1,0,10,10"):
        assert suc.scorebox_problem(bad), bad
    assert suc.scorebox_problem("") is None
    # X 帖子地址、Tennis TV 页面、官网直链都是合法地址
    for url in ("https://x.com/janniksin/status/2103431955874226576",
                "https://www.tennistv.com/videos/123/demo",
                "https://video.twimg.com/amplify_video/1/vid/avc1/1x1/a.mp4?tag=1"):
        assert suc.url_problem(url) is None, url
    assert suc.probe_warnings("https://video.twimg.com/amplify_video/1/vid/avc1/1x1/a.mp4") != []
    assert suc.probe_warnings("https://x.com/a/status/12345") == []


def test_表单自检排在认领源片和装依赖之前_只管probe和cookies():
    steps = _steps("match-reel.yml", "reel")
    names = [s.get("name") or s.get("uses") for s in steps]
    check = "probe／cookies — 表单自检（空 URL、搜索词、默认 slug、框格式）"
    at = names.index(check)
    assert at < names.index("probe — 认领源片（同一条集锦别 probe 两遍）") < names.index("装依赖")
    assert at > names.index("actions/setup-python@v5"), (
        "要排在 setup-python 之后：自检红了，failure() 那两步清理要用 `python`")
    step = steps[at]
    assert "mode == 'probe'" in step["if"] and "mode == 'cookies'" in step["if"]
    assert "tools/source_url_check.py" in step["run"]
    for var in ("MODE", "URL", "SLUG", "SCOREBOX"):
        assert f'"${var}"' in step["run"] and var in step["env"], var


def test_probe主函数在下源片之前就拦空地址和坏框(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(reel, "download", lambda *a, **kw: called.append(a))
    for extra in (["--url", ""], ["--url", "https://youtu.be/aaaaaaaaaaa", "--scorebox", "1,2,3"]):
        monkeypatch.setattr(sys, "argv", ["build_match_reel.py", "probe", *extra,
                                          "--outdir", str(tmp_path / "p")])
        with pytest.raises(reel.ReelError):
            reel.main()
    assert called == [], "表单错了还去下源片——几百 MB 白下"


# ── ① cookie 自检只有一份；定时派发、红了走 Q9 阻塞推送 ───────────────────────

def _fake_ytdlp(tmp_path: Path, body: str) -> dict:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    fake = bindir / "yt-dlp"
    fake.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    fake.chmod(0o755)
    (bindir / "calls").write_text("", encoding="utf-8")
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}",
           "RUNNER_TEMP": str(tmp_path / "rt"), "YT_COOKIES": ""}
    (tmp_path / "rt").mkdir(exist_ok=True)
    return env


def _cookie_check(env: dict, url: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(ROOT / "tools/yt_cookie_check.sh"), url],
                          capture_output=True, text=True, env=env, cwd=ROOT)


def test_cookie自检_回放机器人验证_分因报cookie过期(tmp_path):
    """09-19 17:23Z 那几趟日志原文：`Sign in to confirm you’re not a bot`（弯引号）。"""
    env = _fake_ytdlp(tmp_path, 'echo "$@" >> "$(dirname "$0")/calls"\n'
                      "echo \"ERROR: [youtube] HyKTXynnI9c: Sign in to confirm you’re not a bot.\" >&2\n"
                      "exit 1\n")
    proc = _cookie_check(env)
    assert proc.returncode == 1
    assert "::error::撞上了机器人验证" in proc.stdout, proc.stdout


def test_cookie自检_搜索词在调yt_dlp之前就红(tmp_path):
    env = _fake_ytdlp(tmp_path, 'echo "$@" >> "$(dirname "$0")/calls"\nexit 0\n')
    proc = _cookie_check(env, "ytsearch8:Davis Cup 2026 Norway China doubles")
    assert proc.returncode == 1 and "搜索词" in proc.stdout
    assert (tmp_path / "bin/calls").read_text(encoding="utf-8") == "", "搜索词还是交给了 yt-dlp"


def test_cookie自检_真下到媒体流才算绿_几百字节的错误页不算(tmp_path):
    grab = ('out=""; while [ $# -gt 0 ]; do [ "$1" = "-o" ] && out="$2"; shift; done\n'
            'f="${out%.%(ext)s}.mp4"\n')
    env = _fake_ytdlp(tmp_path, grab + 'head -c 60000 /dev/zero > "$f"\n')
    proc = _cookie_check(env)
    assert proc.returncode == 0 and "YouTube 下载可用" in proc.stdout, proc.stdout + proc.stderr
    env = _fake_ytdlp(tmp_path, grab + 'head -c 300 /dev/zero > "$f"\n')
    proc = _cookie_check(env)
    assert proc.returncode == 1 and "不是媒体流" in proc.stdout


def test_cookie自检只有一份_定时派发走阻塞推送():
    """真下三秒媒体流那段只在 tools/yt_cookie_check.sh；match-reel 的 cookies 模式调它，
    source-health 定时派发这一档（派发者是 github-actions[bot]＝无人值守）。"""
    step = _step("match-reel.yml", "reel", "cookies — 只验 YouTube 还能不能下")
    assert "bash tools/yt_cookie_check.sh" in step["run"]
    assert "yt-dlp" not in step["run"], "cookies 那一步又手搓了一份 yt-dlp 检查"
    script = (ROOT / "tools/yt_cookie_check.sh").read_text(encoding="utf-8")
    assert "--download-sections" in script and "stat -c%s" in script
    assert "source_url_check.py\" --mode cookies" in script

    health = _yaml("source-health.yml")
    assert health[True]["schedule"], "source-health 不再是定时的，cookie 就没人定时看了"
    job = health["jobs"]["youtube-cookies"]
    assert job["permissions"] == {"contents": "read", "actions": "write"}
    run = "\n".join(str(s.get("run") or "") for s in job["steps"])
    env = {k: v for s in job["steps"] for k, v in (s.get("env") or {}).items()}
    assert "gh workflow run match-reel.yml" in run and "-f mode=cookies" in run
    assert "--ref main" in run and env.get("GH_TOKEN") == "${{ github.token }}"
    # 比分源那个 job 的「所有来源失效时通知」是 job 级的 failure()——cookie 红了不许再走它自推一条
    assert "pushplus" not in json.dumps(job, ensure_ascii=False).lower()


def _cookie_run(minutes_ago: int, conclusion: str, actor: str, event: str = "workflow_dispatch",
                rid: int = 1) -> dict:
    at = datetime(2026, 9, 19, 23, 0, tzinfo=timezone.utc) - timedelta(minutes=minutes_ago)
    iso = at.strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": rid, "name": "match-reel", "path": ".github/workflows/match-reel.yml",
            "status": "completed", "conclusion": conclusion, "created_at": iso,
            "updated_at": iso, "html_url": f"https://github.com/o/r/actions/runs/{rid}",
            "display_title": "match-reel · cookies · eala-zheng", "event": event,
            "triggering_actor": {"login": actor, "type": "Bot" if actor.endswith("[bot]") else "User"}}


def test_回放0919_会话拨的cookie红不推_定时派发的红推一次且不重复(tmp_path):
    """09-19 那五趟全是会话拨的（`robertyang87`）：按 Q9 本来就不推——所以没人被叫醒。
    定时派发的那一趟（github-actions[bot]）红了：`match-reel:cookies` 这一处推一次，
    下一班还红着不再推（只在转入阻塞时推）。"""
    import build_dashboard_snapshot as dashboard  # noqa: PLC0415
    import pipeline_health  # noqa: PLC0415

    now = datetime(2026, 9, 19, 23, 0, tzinfo=timezone.utc)
    session = [_cookie_run(m, "failure", "robertyang87", rid=m) for m in (97, 18, 8)]
    (b,) = dashboard.blocked_runs(session, now)
    assert b["key"] == "match-reel:cookies" and b["unattended"] is False
    assert pipeline_health.pushable([b]) == [], "会话拨的红按 Q9 不推——这正是当时没人被叫醒的原因"

    scheduled = session + [_cookie_run(2, "failure", "github-actions[bot]", rid=999)]
    (b,) = dashboard.blocked_runs(scheduled, now)
    assert b["unattended"] is True and b["stages"] == ["发现"] and b["slug"] is None
    state = tmp_path / "alert.json"
    notify, title, message = pipeline_health.blocked_transition(pipeline_health.pushable([b]), state, now)
    assert notify and "match-reel（cookies）" in message and "发现" in title
    again = pipeline_health.blocked_transition(
        pipeline_health.pushable([b]), state, now + timedelta(hours=6, minutes=5))
    assert again[0] is False, "还红着的同一处不许再推（Q9：不重复推）"


# ── ② X：帖子地址下载时现解，直链只当备用 ─────────────────────────────────────

#: 2026-09-28 沙箱 `yt-dlp -J https://x.com/janniksin/status/2103431955874226576` 的格式表
#: （地址换成占位；只留选择器要读的字段）
_SINNER_X_FORMATS = [
    {"format_id": f"hls-audio-{a}-Audio", "protocol": "m3u8_native", "ext": "mp4",
     "vcodec": "none", "acodec": None, "tbr": a // 1000} for a in (32000, 64000, 128000)
] + [
    {"format_id": fid, "protocol": proto, "ext": "mp4", "width": w, "height": h,
     "vcodec": vc, "acodec": ac, "tbr": tbr}
    for fid, proto, w, h, vc, ac, tbr in (
        ("http-632", "https", 320, 568, None, None, 632),
        ("hls-157", "m3u8_native", 320, 568, "avc1.4D4015", "none", 157.6),
        ("http-950", "https", 480, 852, None, None, 950),
        ("hls-315", "m3u8_native", 480, 852, "avc1.4D401E", "none", 316.0),
        ("http-2176", "https", 720, 1280, None, None, 2176),
        ("hls-642", "m3u8_native", 720, 1280, "avc1.64001F", "none", 642.2),
        ("http-10368", "https", 1080, 1920, None, None, 10368),
        ("hls-2270", "m3u8_native", 1080, 1920, "avc1.640032", "none", 2271.0),
    )
]


def _select(selector: str) -> tuple[str, int, int]:
    yt_dlp = pytest.importorskip("yt_dlp")
    formats = copy.deepcopy(_SINNER_X_FORMATS)
    for f in formats:
        f["url"] = f"https://video.twimg.com/fixture/{f['format_id']}.mp4"
    info = {"id": "x", "title": "t", "extractor": "twitter", "extractor_key": "Twitter",
            "webpage_url": "https://x.com/janniksin/status/2103431955874226576", "formats": formats}
    with yt_dlp.YoutubeDL({"format": selector, "format_sort": reel.FMT_SORT.split(","),
                           "quiet": True, "simulate": True}) as ydl:
        got = ydl.process_ie_result(info, download=False)
    return got["format_id"], got.get("width"), got.get("height")


def test_X竖版_老选择器只挑到480x852_帖子地址选择器拿到1080x1920():
    """这就是 tennis-media-sources 原来教人「别写帖子地址、写 CDN 直链」的根子（run 36133328467）。"""
    assert _select(reel.FMT_SELECTOR)[1:] == (480, 852)
    assert _select(reel.X_FMT_SELECTOR) == ("http-10368", 1080, 1920)


def test_X帖子地址不走curl_直接交给yt_dlp按X选择器下(monkeypatch, tmp_path):
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        dest = Path(cmd[cmd.index("-o") + 1])
        dest.write_bytes(b"x" * 10)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(reel.subprocess, "run", fake_run)
    monkeypatch.setattr(reel.shutil, "which", lambda name: "/fake/yt-dlp")
    monkeypatch.setattr(reel, "probe_size", lambda p: (1080, 1920))
    monkeypatch.delenv("TENNISLIVE_SOURCE_CACHE", raising=False)
    reel.download("https://x.com/janniksin/status/2103431955874226576", tmp_path / "s.mp4")
    assert len(calls) == 1 and calls[0][0] == "/fake/yt-dlp"
    assert calls[0][calls[0].index("-f") + 1] == reel.X_FMT_SELECTOR
    assert not any(c[0] == "curl" for c in calls), "帖子地址不该先 curl 一个 HTML 壳"


def test_回放_X直链403_报错说清去写帖子地址(monkeypatch, tmp_path):
    """run 36231247557 / 36231253272：原来只有一句 `curl: (22) … 403`。"""
    monkeypatch.setattr(reel.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(
        cmd, 22, "", "curl: (22) The requested URL returned error: 403"))
    monkeypatch.delenv("TENNISLIVE_SOURCE_CACHE", raising=False)
    url = "https://video.twimg.com/amplify_video/2103558452475797505/vid/avc1/1920x1080/F.mp4?tag=16"
    with pytest.raises(reel.ReelError, match=r"x\.com/<账号>/status/<id>"):
        reel.download(url, tmp_path / "s.mp4")


def test_主地址下不下来就改下source_fallbacks那条_两条都不通才红(monkeypatch, tmp_path):
    tried: list[str] = []

    def fake_one(url, dest, *, archival=False):
        tried.append(url)
        if "x.com" in url:
            raise reel.ReelError("X 帖子地址解不出视频")
        return dest

    monkeypatch.setattr(reel, "_download_one", fake_one)
    status, cdn = "https://x.com/a/status/12345", "https://video.twimg.com/amplify_video/1/v.mp4"
    assert reel.download(status, tmp_path / "s.mp4", fallback=cdn) == tmp_path / "s.mp4"
    assert tried == [status, cdn]
    with pytest.raises(reel.ReelError, match="主地址和备用地址都下不下来"):
        reel.download(status, tmp_path / "s.mp4", fallback="https://x.com/b/status/67890")
    with pytest.raises(reel.ReelError, match="解不出"):
        reel.download(status, tmp_path / "s.mp4")          # 没给备用：原样红


def test_source_fallbacks的形状_键对得上sources_备用也过签名源那道闸():
    base = {"sources": {"xvid": "https://x.com/a/status/12345",
                        "main": "https://www.youtube.com/watch?v=aaaaaaaaaaa"}}
    ok = {**base, "source_fallbacks": {"xvid": "https://video.twimg.com/amplify_video/1/v.mp4"}}
    assert reel.spec_source_fallbacks(ok) == {"xvid": ok["source_fallbacks"]["xvid"]}
    single = {"source_url": "https://x.com/a/status/12345",
              "source_fallbacks": {"source_url": "https://video.twimg.com/amplify_video/1/v.mp4"}}
    assert reel.spec_source_fallbacks(single) == {"": single["source_fallbacks"]["source_url"]}
    for bad in ({"nope": "https://a.b/c.mp4"}, {"xvid": "ytsearch1:foo"}, ["https://a.b/c.mp4"],
                {"xvid": "https://cdn.example/v.m3u8?token=" + "a" * 40}):
        with pytest.raises(reel.ReelError):
            reel.spec_source_fallbacks({**base, "source_fallbacks": bad})
    assert reel.spec_source_fallbacks(base) == {}


def test_写成下划线的source_fallbacks要被拦_不许静静地不生效():
    """`_REAL_FIELDS` 由 `test_真字段表要盖住每条spec里出现过的字段` 从语料推——而
    语料里还没有一条 spec 写过 `source_fallbacks`，那条判据要等第一条照 X 直链闸
    的建议挪了直链的手写 spec 才会红。在那之前 `_source_fallbacks` 这种手滑整块
    被当注解跳过，主地址 403 时备用那条根本不会被试。"""
    fallback = {"xvid": "https://video.twimg.com/amplify_video/1/v.mp4"}
    with pytest.raises(reel.ReelError, match="source_fallbacks"):
        reel._reject_underscored_fields({"_source_fallbacks": fallback})
    reel._reject_underscored_fields({"source_fallbacks": fallback,
                                     "_source_fallbacks_why": "帖子被删时的兜底"})


def test_新写的spec主地址不许是X直链_认领或存量放行():
    cdn = "https://video.twimg.com/amplify_video/1/vid/avc1/1080x1920/a.mp4?tag=29"
    spec = {"slug": "new-x-story-2026", "sources": {"main": "https://youtu.be/aaaaaaaaaaa", "xvid": cdn}}
    problem = reel.x_cdn_source_problem(spec)
    assert problem and "`xvid`" in problem and "source_fallbacks" in problem
    moved = {**spec, "sources": {**spec["sources"], "xvid": "https://x.com/a/status/12345"},
             "source_fallbacks": {"xvid": cdn}}
    assert reel.x_cdn_source_problem(moved) is None, "直链挪进备用之后就该放行"
    assert reel.x_cdn_source_problem({**spec, "_x_cdn_why": "帖子已删，只剩直链"}) is None
    legacy = next(iter(reel.LEGACY_X_CDN_PRIMARY))
    assert reel.x_cdn_source_problem({**spec, "slug": legacy}) is None


def test_X直链当主地址的闸接在validate_spec上_手写硬_自动只报(capsys):
    """接线判据：闸写出来了没人调，这个仓库栽过。拿一条真存量换个新 slug（前面几道闸
    按 slug 认的认领补上），看它红在这一句；挪成「帖子地址＋备用直链」就放行。"""
    spec = json.loads((ROOT / "specs/reels/sinner-beijing-withdrawal-2026.json").read_text("utf-8"))
    spec.update(slug="sinner-x-cdn-gate-probe",
                _social_search={"x": "@janniksin 9/25 有退赛视频（已用）", "instagram": "只有图文"},
                _cover_reuse_why="判据回放：同一条片子换 slug")
    cdn = spec["sources"]["xvid"]
    with pytest.raises(reel.ReelError, match="X 的 CDN 直链"):
        reel.validate_spec(spec)
    capsys.readouterr()
    reel.validate_spec({**spec, "_production": {"status": "ready_for_render"}})
    assert "[X 直链] 自动 spec，只报不拦" in capsys.readouterr().out
    moved = {**spec, "sources": {**spec["sources"],
                                 "xvid": "https://x.com/janniksin/status/2103431955874226576"},
             "source_fallbacks": {"xvid": cdn}}
    reel.validate_spec(moved)                      # 帖子地址当主、直链当备用：放行


def test_X直链当主地址的存量只许减不许加_全库零误伤():
    """表自带自检：每一条都真的还挂着直链当主地址（改好了就从表里删）；全库其余 spec 零命中。"""
    hits = []
    for path in sorted((ROOT / "specs/reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            continue
        slug = spec.get("slug") or path.stem
        try:
            primaries = reel.spec_sources(spec).values()
        except reel.ReelError:
            continue
        if any(suc.is_x_cdn_url(u) for u in primaries):
            hits.append(slug)
        assert reel.x_cdn_source_problem(spec) is None, f"{slug} 红了——存量表漏了它，还是新写的？"
    assert sorted(hits) == sorted(reel.LEGACY_X_CDN_PRIMARY), (
        f"存量表和全库对不上：表里多了 {sorted(set(reel.LEGACY_X_CDN_PRIMARY) - set(hits))}"
        f"（改好了就删），全库多了 {sorted(set(hits) - set(reel.LEGACY_X_CDN_PRIMARY))}（只许减不许加）")


# ── ④ 1080p 量的框配 720p 源：按高度等比缩，缩不进退回猜框，probe 不许红 ─────

def test_回放medvedev_wong_1080p的框按高度缩到720p():
    """run 36331431180 / 36333879418：同一条地址那一趟只下到 1280×720。后来下到 1920×1080
    的那一趟，这个框量出 97 个死球时刻——框是对的，错的只是分辨率。"""
    box, note = reel.fit_scorebox_to_frame("98,920,519,1029", (1280, 720))
    assert box == "65,613,346,686" and note and "1920×1080" in note
    assert reel.fit_scorebox_to_frame("98,920,519,1029", (1920, 1080)) == ("98,920,519,1029", None)
    assert reel.fit_scorebox_to_frame("", (1280, 720)) == ("", None)
    # 哪一档都装不下（宽过 4K 的框）→ 不用这个框，退回猜框
    box, note = reel.fit_scorebox_to_frame("100,100,9000,200", (1280, 720))
    assert box == "" and "退回猜框" in note


def _flip_video(path: Path, size: str = "320x240") -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s={size}:r=25:d=4",
         "-vf", "drawbox=x=0:y=0:w=80:h=60:color=black:t=fill:enable='lt(mod(t,2),1)'",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(path)], check=True)


def test_框落在画面外_量死球只报不崩_不是cv2的empty断言(tmp_path, capsys):
    pytest.importorskip("cv2")
    if not shutil.which("ffmpeg"):
        pytest.skip("没有 ffmpeg")
    import find_point_ends as fpe  # noqa: PLC0415

    video = tmp_path / "v.mp4"
    _flip_video(video)
    with pytest.raises(ValueError, match="画面外"):
        fpe.scan(video, (400, 300, 500, 400), 0.1)


def test_量不了的框记None_不和量过零次的空表混(monkeypatch, capsys):
    """`scan` 报 ValueError（框落在画面外）时原来返回 `[]`——而 `[]` 在
    `point_ends_guess` 里就是「量过、零次」，dry-run 会说「框多半猜错了」。"""
    import find_point_ends as fpe  # noqa: PLC0415

    def outside(*_a, **_kw):
        raise ValueError("框 (1, 2, 30, 40) 落在 0×0 的画面外——框是按别的分辨率量的")

    monkeypatch.setattr(fpe, "scan", outside)
    monkeypatch.setattr(reel, "_video_frame_size", lambda _src: None)
    assert reel.point_end_candidates(Path("x.mp4"), "1,2,30,40") is None
    assert "没量成" in capsys.readouterr().out
    assert reel.point_end_candidates(Path("x.mp4"), "") == [], "没给框仍是 []（跳过）"
    # 猜的框量不了记 []：None 在 point_ends_guess 里是「这趟没猜」（dry-run 会说「老 probe」）
    monkeypatch.setattr(reel, "suggest_scorebox", lambda _src: "1,2,30,40")
    assert reel.measure_point_ends(Path("x.mp4"), "") == ([], "1,2,30,40", [])
    assert reel.measure_point_ends(Path("x.mp4"), "1,2,30,40") == (None, None, None)
    monkeypatch.setattr(fpe, "scan", lambda *_a, **_kw: [])
    assert reel.point_end_candidates(Path("x.mp4"), "1,2,30,40") == [], "量过零次仍是 []"


def test_probe一趟_框出界也照样出完probe_json_并记下缩放(monkeypatch, tmp_path):
    """整条 probe 路：720p 源 ＋ 1080p 的框 → 不红，量死球拿到的是缩过的框，probe.json 记着。"""
    if not shutil.which("ffmpeg"):
        pytest.skip("没有 ffmpeg")
    source = tmp_path / "src.mp4"
    _flip_video(source, "1280x720")
    seen = {}
    monkeypatch.setattr(reel, "download", lambda url, dest, **kw: source)
    monkeypatch.setattr(reel, "scene_changes", lambda *a, **kw: [])
    monkeypatch.setattr(reel, "contact_sheet", lambda *a, **kw: [])
    monkeypatch.setattr(reel, "fetch_captions", lambda *a, **kw: None)
    monkeypatch.setattr(reel, "measure_point_ends",
                        lambda src, box: seen.setdefault("box", box) and ([1.0], None, None))
    out = tmp_path / "probe"
    monkeypatch.setattr(sys, "argv", ["build_match_reel.py", "probe", "--url",
                                      "https://www.youtube.com/watch?v=aINLTXtRWbE",
                                      "--scorebox", "98,920,519,1029", "--outdir", str(out)])
    assert reel.main() == 0
    assert seen["box"] == "65,613,346,686"
    probe = json.loads((out / "probe.json").read_text(encoding="utf-8"))
    assert probe["scorebox_fitted"]["used"] == "65,613,346,686"
    assert probe["scorebox_fitted"]["given"] == "98,920,519,1029"


# ── ⑤ probe 派发 render：手写 spec 跳过，自动 spec 合同照旧硬 ─────────────────

def test_回放_手写spec重probe不再裸assert(tmp_path, capsys):
    """run 36331363124：cobolli-mensik-doubles-laver-cup-2026 是手写 spec（没有 _production）。"""
    path = ROOT / "specs/reels/cobolli-mensik-doubles-laver-cup-2026.json"
    assert gate.main(["--spec", str(path)]) == 0
    assert capsys.readouterr().out.strip() == "skip"
    assert gate.decide(None)[0] == "waiting"
    ready = {"_production": {"status": "ready_for_render"}, "push": {"auto": True}}
    assert gate.decide(ready)[0] == "dispatch"
    assert gate.decide({**ready, "push": {}})[0] == "error"
    assert gate.decide({**ready, "_production": {"status": "waiting"}})[0] == "error"
    missing = tmp_path / "none.json"
    assert gate.main(["--spec", str(missing)]) == 0 and capsys.readouterr().out.strip() == "waiting"


def test_全库自动spec都派得出去_手写spec一律跳过():
    kinds = {"dispatch": 0, "skip": 0, "error": []}
    for path in sorted((ROOT / "specs/reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            continue
        action, _why = gate.decide(spec)
        if action == "error":
            kinds["error"].append(path.stem)
        else:
            kinds[action] += 1
    assert kinds["dispatch"] >= 1 and kinds["skip"] >= 100, kinds
    # 带 _production 却不是 ready 的（历史上留下的）照旧红——那是合同对不上，不是这次放宽的
    for slug in kinds["error"]:
        spec = json.loads((ROOT / f"specs/reels/{slug}.json").read_text(encoding="utf-8"))
        assert spec.get("_production"), slug


def test_派发那一步读判据工具_不再裸assert():
    step = _step("match-reel.yml", "reel", "probe 正式 spec 就绪后自动派发 render")
    assert "tools/probe_dispatch_gate.py" in step["run"]
    assert "assert" not in step["run"]
    assert '[ "$ACTION" != "dispatch" ]' in step["run"]


# ── ⑥ push 重试：先退避、再 rebase、立刻推 ───────────────────────────────────

def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout


def _racing_push(tmp_path: Path, retry_body: str) -> subprocess.CompletedProcess:
    """一个在我们退避期间一定会往 main 推一次的「对手」：它挂在 `sleep` 上。
    重试脚本要是睡在 rebase 和 push 之间（frame-grab 原来那种），每一轮都撞车。"""
    remote, ours, rival = tmp_path / "remote.git", tmp_path / "ours", tmp_path / "rival"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    for repo in (ours, rival):
        _git(tmp_path, "clone", "-q", str(remote), str(repo))
        _git(repo, "config", "user.email", "t@t")
        _git(repo, "config", "user.name", "t")
    _git(rival, "commit", "-q", "--allow-empty", "-m", "base")
    _git(rival, "push", "-q", "origin", "HEAD:main")
    _git(ours, "pull", "-q", "origin", "main")
    (ours / "frames").mkdir()
    (ours / "frames/0001.jpg").write_bytes(b"jpg")
    _git(ours, "add", "frames")
    _git(ours, "commit", "-q", "-m", "frames")
    _git(rival, "commit", "-q", "--allow-empty", "-m", "rival-0")
    _git(rival, "push", "-q", "origin", "HEAD:main")       # 第一次 push 必被拒
    script = (f"set -u\ncd {ours}\n{retry_body}\n"
              f"sleep() {{ (cd {rival} && git commit -q --allow-empty -m r && "
              f"git push -q origin HEAD:main); }}\n"
              "push_with_rebase_retry main 4\n")
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True)


def test_共享push重试_退避期间别人推了也推得上(tmp_path):
    proc = _racing_push(tmp_path, f"source {ROOT / 'tools/git_push_retry.sh'}")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_反例_睡在rebase和push之间的老写法每一轮都撞车(tmp_path):
    """这条是判据咬得动的证明：run 36317540680 那种顺序，在同一个对手面前推不上去。"""
    old = r'''push_with_rebase_retry() {
  local ref="$1" attempts="${2:-5}" attempt
  for attempt in $(seq 1 "$attempts"); do
    git push origin "HEAD:${ref}" && return 0
    git pull --rebase --autostash origin "$ref" || { git rebase --abort 2>/dev/null || true; }
    sleep 1
  done
  return 1
}'''
    proc = _racing_push(tmp_path, old)
    assert proc.returncode != 0, "老顺序居然推上了——对手没在退避窗口里推，这条反例失效了"


def test_frame_grab推送走共享重试_同slug排队():
    wf = _yaml("frame-grab.yml")
    step = _step("frame-grab.yml", "grab", "提交候选帧")
    assert "source tools/git_push_retry.sh" in step["run"]
    assert "push_with_rebase_retry" in step["run"]
    assert "git push origin" not in step["run"] and "sleep" not in step["run"]
    assert "frame-grab-${{ github.event.inputs.slug }}" in wf["concurrency"]["group"]
    assert wf["concurrency"]["cancel-in-progress"] is False


# ── ⑦ 上游 5xx：feed 先重试，备料接住 SystemExit 只报 ─────────────────────────

def test_flashscore喂料5xx先重试_还不行才报StatsError(monkeypatch):
    import fetch_match_stats_fs as fs  # noqa: PLC0415

    calls = []

    def flaky(req, timeout=0):
        calls.append(req.full_url)
        if len(calls) < 3:
            raise urllib.error.HTTPError(req.full_url, 500, "boom", {}, None)

        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"ok"
        return Resp()

    monkeypatch.setattr(fs.urllib.request, "urlopen", flaky)
    assert fs.feed("f_2_0_2_en_1", sleep=lambda s: None) == "ok" and len(calls) == 3

    def down(req, timeout=0):
        raise urllib.error.URLError("connection reset")

    monkeypatch.setattr(fs.urllib.request, "urlopen", down)
    with pytest.raises(fs.StatsError, match="试了 3 次"):
        fs.feed("f_2_0_2_en_1", sleep=lambda s: None)

    calls.clear()

    def forbidden(req, timeout=0):
        calls.append(1)
        raise urllib.error.HTTPError(req.full_url, 403, "no", {}, None)

    monkeypatch.setattr(fs.urllib.request, "urlopen", forbidden)
    with pytest.raises(fs.StatsError, match="HTTP 403"):
        fs.feed("x", sleep=lambda s: None)
    assert calls == [1], "4xx 是明确拒绝，不许重试"


def test_flashscore_5xx重试之后仍失败_备料降级成只报不拖垮probe(monkeypatch):
    """`match_feed._get` 5xx 重试三次后抛 SystemExit——原来穿过每一处 `except Exception`。"""
    import assemble_spec as a  # noqa: PLC0415

    def http500(*_a, **_kw):
        raise SystemExit("https://www.flashscore.com/x/feed\n  HTTP 500 —— 被挡还是不存在")

    # df_hh_1 读得到（home/away 核上了），其余四块都 5xx——只报、不拖垮。
    # df_hh_1 本身读不到是另一回事：见下一条，那时连这四块都不许写。
    monkeypatch.setattr(a, "fs_feed",
                        lambda *_a: "KP÷4CYI9Ick¬FH÷Eala A.¬FK÷Ruse E.¬~")
    for name in ("stats_block", "collect", "points", "set_pairs"):
        monkeypatch.setattr(a, name, http500)
    monkeypatch.setattr(a, "resolve_match_id", lambda h, aw: "4CYI9Ick")

    class NotReady:
        ready = False

    monkeypatch.setattr(a, "Chat", lambda: NotReady())
    draft = a.assemble(slug="x", home="Alexandra Eala", away="Elena-Gabriela Ruse",
                       event="Cincinnati", year=2026, fixture="北京时间",
                       flashscore_id="4CYI9Ick")
    joined = "\n".join(draft["_notes"])
    assert "stats 块没成（SystemExit" in joined and "转折局没成（SystemExit" in joined
    assert "stats" not in draft and "_turning_points" not in draft


def _df_hh_1_assemble(monkeypatch, df_hh_1):
    """回放 2026-09-28 复审那一趟：flashscore 的 home 是诺斯科娃（6-4 6-3 赢了），
    编排器给的 --home 是萨巴伦卡；逐局表、统计都取得到，只有 df_hh_1 看 `df_hh_1` 桩。"""
    import assemble_spec as a  # noqa: PLC0415
    import promote_reel_draft as promote  # noqa: PLC0415

    games = [{"set": str(n), "home_games": h, "away_games": w, "points": [],
              "server": "home", "winner": "home"}
             for n, (h, w) in enumerate([(6, 4), (6, 3)], 1)]
    called: list[str] = []

    def rec(name, value):
        def _f(*_a, **_kw):
            called.append(name)
            return value
        return _f

    monkeypatch.setattr(a, "fs_feed", df_hh_1)
    monkeypatch.setattr(a, "points", rec("points", games))
    monkeypatch.setattr(a, "rank_games", lambda g: [])
    monkeypatch.setattr(a, "set_pairs", rec("set_pairs", [(6, 4), (6, 3)]))
    monkeypatch.setattr(a, "stats_block", rec("stats_block", {
        "a": {"aces": 9}, "b": {"aces": 1},
        "_missing_required": [], "_has_winners_ue": False}))
    monkeypatch.setattr(a, "collect", rec("collect", {"candidates": [], "durations": []}))
    monkeypatch.setattr(a, "fetch_rankings",
                        lambda: type("R", (), {"atp": [], "wta": []})())

    class NotReady:
        ready = False

    monkeypatch.setattr(a, "Chat", lambda: NotReady())
    draft = a.assemble(slug="sabalenka-noskova", home="Aryna Sabalenka",
                       away="Linda Noskova", event="Cincinnati", year=2026,
                       fixture="北京时间", flashscore_id="8QYQMw6l",
                       tactical_packet={"status": "skipped"})
    return draft, called, promote.waiting_reasons(draft)


def test_df_hh_1读不到时不许出result_verified(monkeypatch):
    """matchup 顺序核不出（df_hh_1 5xx 重试完仍 SystemExit），**赛果事实和按 feed
    home/away 排的几块一块都不写**，草稿留在 waiting。

    复审回放（2026-09-28）：把 SystemExit 接住、退回命令行顺序之后，这一趟产出
    `_match.status=result_verified winner=萨巴伦卡 6-4 6-3 loser=诺斯科娃`，stats.a
    挂在萨巴伦卡名下——赢的是 flashscore 的 home 诺斯科娃，而 `verified_result_problem`
    拿 `_match` 自己的字段反推，一道都不响。"""
    def down(name, mid):
        raise SystemExit(f"https://…/{name}_{mid}\n  HTTP 503 —— 被挡还是不存在")

    draft, called, waiting = _df_hh_1_assemble(monkeypatch, down)
    match = draft.get("_match") or {}
    assert match.get("status") != "result_verified", (
        f"顺序没核上还出了赛果事实：{match.get('winner')} {match.get('winner_result')}")
    assert "winner" not in draft["cover"] and "result" not in draft["cover"]
    assert "stats" not in draft and "_hit_data" not in draft
    assert "_turning_points" not in draft
    assert called == [], f"顺序不认时不该再去读按 home/away 排的 feed：{called}"
    assert "结构化赛果尚未 verified" in waiting
    joined = "\n".join(draft["_notes"])
    assert "matchup 顺序没核上" in joined and "HTTP 503" in joined, (
        "退路要写进 _notes，不许只 print 到 stdout")
    assert match.get("flashscore_id") == "8QYQMw6l"


def test_df_hh_1读得到时同一趟出诺斯科娃赢(monkeypatch):
    """上一条的对照组：同样的逐局表，df_hh_1 给出本场 home=诺斯科娃，赢家就是她。"""
    body = "SA÷2¬~KP÷8QYQMw6l¬FH÷Noskova L.¬FK÷Sabalenka A.¬~"
    draft, called, _waiting = _df_hh_1_assemble(monkeypatch, lambda *_a: body)
    match = draft["_match"]
    assert match["status"] == "result_verified"
    assert (match["winner"], match["winner_result"], match["loser"]) == (
        "诺斯科娃", "6-4 6-3", "萨巴伦卡")
    assert [p["name_en"] for p in draft["cover"]["matchup"]] == [
        "Linda Noskova", "Aryna Sabalenka"]
    assert draft["stats"]["a"]["aces"] == 9, "stats.a 跟 feed 的 home（诺斯科娃）"
    assert {"stats_block", "points", "set_pairs", "collect"} <= set(called)
