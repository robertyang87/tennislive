"""推送正文里的图片 URL 必须钉在 commit 上，不许停在 `@main`。

来路（2026-09-22，`bouzkova-kartal-bjk-cup-2026-qf` 连推三次量出来的）：
`auto-push-reel.yml` 里 `TENNISLIVE_ASSET_REV: ${{ github.sha }}` 早就设上了，
注释还写着「钉 commit，别停在 @main……微信的图片缓存按路径算」——
**而 `push_reel.poster_url` / `stat_card_url` 写死的是 `BRANCH`**，
于是变量设了等于没设。三条推送的日志里都是

    [数据图] 带上这一屏：…/gh/robertyang87/tennislive@main/output/2026-09-23/…/stat_card.jpg

而同一步的环境里 `TENNISLIVE_ASSET_REV: 606db061b524…` 明明印着。
后果：同一条片子重渲之后路径不变，微信按路径缓存，卡上那张图停在上一版。

⚠️ 这是「一个数写两处必分叉」的又一例，而**分叉的样子是「配好了」**
（yml 里有、注释里也写着为什么要有），只有把真发出去的 URL 抠出来才看得见。
所以这条判据钉的是**函数的返回值**，不是 yml 的文本。
"""

from __future__ import annotations

import importlib
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

SHA = "606db061b524c632dc67dd9f2eb0f6fe3f231c83"
OUTDIR = Path("output/2026-09-23/reel/bouzkova-kartal-bjk-cup-2026-qf")


def _fresh(monkeypatch, rev: str | None):
    """带着指定的 `TENNISLIVE_ASSET_REV` 重新导入 `push_reel`。

    ⚠️ 模块级的 `REPO` / `BRANCH` 是导入时从环境读的，所以不能只改环境变量
    就调函数——**必须重新导入**，否则测的是上一次导入留下的那份。
    """
    if rev is None:
        monkeypatch.delenv("TENNISLIVE_ASSET_REV", raising=False)
    else:
        monkeypatch.setenv("TENNISLIVE_ASSET_REV", rev)
    monkeypatch.setenv("GITHUB_REPOSITORY", "robertyang87/tennislive")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    sys.modules.pop("push_reel", None)
    return importlib.import_module("push_reel")


@pytest.mark.parametrize("builder", ["poster_url", "stat_card_url"])
def test_配了ASSET_REV就要钉在commit上_不许停在main(monkeypatch, builder):
    """两个 URL 构造器**都要**钉——只钉一个就是下一次分叉。"""
    mod = _fresh(monkeypatch, SHA)
    url = getattr(mod, builder)(OUTDIR)

    assert "@main/" not in url, (
        f"{builder}() 还停在 @main：{url}\n"
        "配了 TENNISLIVE_ASSET_REV 就必须钉在 commit 上，否则同一条片子重渲之后"
        "路径不变，微信按路径缓存，卡上那张图停在上一版（而且不吭声）。"
    )
    # `cdn.pin_ref` 把 sha 截到 10 位（实测 jsDelivr 40/12/10/7 位全 200）。
    assert f"@{SHA[:10]}/" in url, (
        f"{builder}() 没有钉成 10 位短 sha：{url}\n"
        "截断只许有 cdn.pin_ref 那一处实现——这儿要的就是它的结果。"
    )
    assert url.endswith(f"/{OUTDIR.as_posix()}/{Path(getattr(mod, 'POSTER_NAME') if builder == 'poster_url' else getattr(mod, 'STAT_CARD_NAME')).name}"), (
        f"{builder}() 的路径部分被改坏了：{url}")


@pytest.mark.parametrize("builder", ["poster_url", "stat_card_url"])
def test_没配ASSET_REV时退回分支名_不许拼出空的ref(monkeypatch, builder):
    """本地手跑、没有这个变量时要退回 `BRANCH`，不是拼出 `@/`。

    ⚠️ 钉住这一头是因为**只钉前一头的话，`return REPO + "@" + rev` 里
    `rev` 取空字符串也能让上一条测试过**，而那会拼出
    `…/tennislive@/output/…`——jsDelivr 404，推送前那道图片探活会拦，
    但那是「靠下游兜住上游的 bug」。
    """
    mod = _fresh(monkeypatch, None)
    url = getattr(mod, builder)(OUTDIR)
    assert "@main/" in url, f"{builder}() 没有退回分支名：{url}"
    assert "@/" not in url, f"{builder}() 拼出了空 ref：{url}"


def test_两个构造器共用同一个ref来源(monkeypatch):
    """海报和数据图必须是同一个 ref——一条消息里两张图钉在不同版本上更难查。"""
    mod = _fresh(monkeypatch, SHA)
    a = mod.poster_url(OUTDIR).split("/output/")[0]
    b = mod.stat_card_url(OUTDIR).split("/output/")[0]
    assert a == b, f"海报和数据图的 ref 不一致：\n  {a}\n  {b}"


@contextmanager
def _delivery_server(respond):
    """真 HTTP，响应由用例决定；关服前收束 handler 和服务线程。"""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, payload = respond(self.path, dict(self.headers))
            self.send_response(status)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()


def _sender(monkeypatch, tmp_path, mod, *, text="正文", card=True):
    # These cases isolate CDN/copy ordering. Actual voice completeness and
    # network-before-review failures are exercised by test_voice_quality_gate.
    import voice_quality_gate
    monkeypatch.setattr(voice_quality_gate, "require_publish", lambda *a, **kw: None)
    import publication_revision
    monkeypatch.setattr(publication_revision, "has_revision", lambda *a: False)
    outdir = tmp_path / "film"
    outdir.mkdir()
    (outdir / "copy.html").write_text("测试标题")
    (outdir / "film.mp4").write_bytes(b"fixture")
    if card:
        (outdir / mod.STAT_CARD_NAME).write_bytes(b"fixture")
    monkeypatch.setattr(mod, "prepare_copy", lambda *a, **kw: ("赛场之上", "测试标题", text))
    monkeypatch.setattr(sys, "argv", ["push_reel.py", "--outdir", str(outdir),
                                     "--copy", str(tmp_path / "copy.txt")])
    sent = []
    monkeypatch.setattr(mod, "push", lambda *a, **kw: sent.append((a, kw)) or "receipt")
    return outdir, sent


def test_复制页和成片同时探活仍核对当前标题和Range(monkeypatch):
    mod = _fresh(monkeypatch, SHA)
    monkeypatch.setenv("TENNISLIVE_COPYPAGE_ATTEMPTS", "2")
    monkeypatch.setenv("TENNISLIVE_COPYPAGE_RETRY_SECONDS", "0")
    barrier = threading.Barrier(2)
    calls = []
    triggers, ticks = [], []
    monkeypatch.setattr(mod, "trigger_pages_build", lambda: triggers.append(True))
    monkeypatch.setattr(mod.PagesWatchdog, "tick", lambda self: ticks.append(True))

    def respond(path, headers):
        calls.append((path, headers))
        # 串行退回会在这里超时，不能靠断言线程数假装并行。
        if len([c for c in calls if c[0] == path]) == 1:
            barrier.wait(timeout=3)
        if path == "/copy" and len([c for c in calls if c[0] == path]) == 1:
            return 200, b"previous-title"
        return (200, b"current &amp; title") if path == "/copy" else (206, b"movie")

    with _delivery_server(respond) as base:
        mod.wait_for_delivery(base + "/copy", "current & title", base + "/video")
    assert [c[0] for c in calls].count("/copy") == 2
    assert [c[0] for c in calls].count("/video") == 1
    assert triggers == [True] and len(ticks) == 2
    assert all(c[1]["Cache-Control"] == "no-cache" for c in calls if c[0] == "/copy")
    assert [c[1]["Range"] for c in calls if c[0] == "/video"] == ["bytes=0-1023"]


@pytest.mark.parametrize("failure", ["old-page", "video-404", "video-exception"])
def test_任一道探活失败都不推送并收束两个worker(monkeypatch, tmp_path, failure):
    mod = _fresh(monkeypatch, SHA)
    _, sent = _sender(monkeypatch, tmp_path, mod)
    monkeypatch.setenv("TENNISLIVE_COPYPAGE_ATTEMPTS", "1")
    monkeypatch.setattr(mod, "trigger_pages_build", lambda: None)
    monkeypatch.setattr(mod.PagesWatchdog, "tick", lambda self: None)
    original_video = mod.wait_for_video
    monkeypatch.setattr(mod, "wait_for_video", lambda url: original_video(url, attempts=1, delay=0))
    if failure == "video-exception":
        def broken(url):
            raise RuntimeError("unexpected probe failure")
        monkeypatch.setattr(mod, "wait_for_video", broken)
    requests_seen = []

    def respond(path, headers):
        requests_seen.append(path)
        if path == "/copy":
            return 200, ("旧标题" if failure == "old-page" else "测试标题").encode()
        return (404 if failure == "video-404" else 206), b"movie"

    with _delivery_server(respond) as base:
        monkeypatch.setattr(mod, "copy_page_url", lambda *a: base + "/copy")
        monkeypatch.setattr(mod, "video_url", lambda *a: base + "/video")
        error_type = RuntimeError if failure == "video-exception" else SystemExit
        error_text = {"old-page": "没等到这一版", "video-404": "成片链接",
                      "video-exception": "unexpected probe failure"}[failure]
        with pytest.raises(error_type, match=error_text):
            mod.main()
    assert sent == []
    assert "/copy" in requests_seen
    if failure != "video-exception":
        assert "/video" in requests_seen
    assert not any(t.name.startswith("reel-delivery") for t in threading.enumerate())


@pytest.mark.parametrize("problem", ["missing-card", "long-copy"])
def test_本地缺产物或文案超限不先等待网络(monkeypatch, tmp_path, problem):
    mod = _fresh(monkeypatch, SHA)
    _, sent = _sender(monkeypatch, tmp_path, mod,
                      text="字" * (mod.BODY_MAX + 1) if problem == "long-copy" else "正文",
                      card=problem != "missing-card")
    def unexpected(*args):
        pytest.fail("本地门禁没过，不应等待 Pages/CDN")
    monkeypatch.setattr(mod, "wait_for_delivery", unexpected)
    with pytest.raises(SystemExit, match="统计图|超过"):
        mod.main()
    assert sent == []


def test_两道探活都过才唯一一次推送且前缀不进入标题比对(monkeypatch, tmp_path):
    mod = _fresh(monkeypatch, SHA)
    _, sent = _sender(monkeypatch, tmp_path, mod)
    monkeypatch.setattr(sys, "argv", [*sys.argv, "--title-prefix", "自检 "])
    checks = []
    monkeypatch.setattr(mod, "wait_for_copy_page", lambda url, title: checks.append(("page", title)))
    monkeypatch.setattr(mod, "wait_for_video", lambda url: checks.append(("video", url)))
    def push_after_checks(*args, **kwargs):
        assert len(checks) == 2 and ("page", "测试标题") in checks
        sent.append((args, kwargs))
        return "receipt"
    monkeypatch.setattr(mod, "push", push_after_checks)
    assert mod.main() == 0
    assert len(checks) == 2 and ("page", "测试标题") in checks
    assert len(sent) == 1 and sent[0][0][0] == "自检 测试标题"
    assert "stat_card.jpg" in sent[0][0][1]
