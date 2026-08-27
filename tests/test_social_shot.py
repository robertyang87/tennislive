"""社媒截图：手机视口、预设怎么解析、登录墙拦得住。

来路：账号所有者 2026-08-27「**最好截取手机版的**」「**最好用 Instagram**」。

⚠️ **`capture()` 本身跑不了**（要真 Chromium，而这台沙箱的 Chromium 过不了
出网代理）。所以这里测的是**能在本地判的那一半**：预设怎么解析、UA 和视口配不配
套、登录墙的判据认不认得 Instagram、请求文件的形状对不对。真正打开页面那一步
归 `social-shot.yml`，判据是产出的 `.png.json` 旁证。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("tools").resolve()))
import capture_social_shot as cap  # noqa: E402


def _resolve(**kw):
    """把 capture 里那段预设解析原样跑一遍——它是纯算术，不用开浏览器。"""
    mobile = kw.get("mobile", False)
    preset = cap._MOBILE if mobile else cap._DESKTOP
    return {
        "width": preset["width"] if kw.get("width") is None else kw["width"],
        "height": preset["height"] if kw.get("height") is None else kw["height"],
        "scale": preset["scale"] if kw.get("scale") is None else kw["scale"],
        "user_agent": preset["user_agent"],
    }


def test_手机视口和手机UA要一起换():
    """**三样要一起给**：视口、UA、`is_mobile`/`has_touch`。

    只换 UA 不换视口，站点按桌面版排版却提示你「下载 App」；只换视口不换 UA，
    很多站照旧发桌面版 HTML。两种都**不报错**，只是截回来的东西不对。
    """
    m, d = _resolve(mobile=True), _resolve(mobile=False)
    assert m["width"] < d["width"], "手机视口该比桌面窄"
    assert m["height"] > m["width"], "手机视口该是竖的——社媒帖子本来就是竖的"
    assert m["scale"] >= 3, "手机是高密度屏，2 倍截出来字会软"
    assert "iPhone" in m["user_agent"] and "Mobile" in m["user_agent"]
    assert "Macintosh" in d["user_agent"] and "iPhone" not in d["user_agent"]

    src = Path("tools/capture_social_shot.py").read_text(encoding="utf-8")
    for flag in ("is_mobile=mobile", "has_touch=mobile"):
        assert flag in src, f"新建页面时没把 {flag} 跟着 UA 一起给"


def test_没给尺寸要用None表示不能拿具体数当哨兵():
    """第一版拿 `width == 1000` 当「没给」——于是「真的想要 1000 宽的手机视口」
    这件事表达不出来，而它坏起来一声不吭。

    ⚠️ 这条同时钉住**调用方**：`run_social_shot_requests.py` 没写尺寸时必须传
    `None`，在那儿写死一组数会把手机预设整个盖掉。
    """
    assert _resolve(mobile=True) == _resolve(mobile=True, width=None,
                                             height=None, scale=None)
    # 显式给的要盖过预设，哪怕给的正好等于另一档的预设值
    got = _resolve(mobile=True, width=1000)
    assert got["width"] == 1000 and got["height"] == cap._MOBILE["height"]

    runner = Path("tools/run_social_shot_requests.py").read_text(encoding="utf-8")
    for key in ("width", "height", "scale"):
        assert f'shot.get("{key}") else None' in runner, (
            f"请求文件里没写 {key} 时，runner 应该传 None 让 capture 去填预设")


def test_登录墙的判据要认得出Instagram():
    """撞上登录墙**报错不交图**——一张登录框的截图和一张帖子的截图在文件系统里
    没有任何区别，交出去就是一条假证据。

    ⚠️ 判据要窄：**不许只认「Log in」这个词**，正文里随便一句话都可能带上它。
    认的是各家自己那几句固定文案。
    """
    wall = cap._LOGIN_WALL
    assert any("Instagram" in w for w in wall), "Instagram 的登录墙没进判据"
    assert any("X" in w for w in wall), "X 的登录墙没进判据"
    for w in wall:
        assert len(w) >= 10, f"{w!r} 太短了，会误伤正文"
    # 这几句是真帖子里可能出现的话，一句都不许命中
    for innocent in ("I will log in to the stadium",
                     "Sign up for the newsletter about my page",
                     "Thank you, New York. Forever grateful."):
        assert not any(w in innocent for w in wall), f"误伤了：{innocent!r}"

    src = Path("tools/capture_social_shot.py").read_text(encoding="utf-8")
    assert "out.unlink(missing_ok=True)" in src, "撞墙之后没有把图删掉"
    assert "raise SystemExit(2)" in src, "撞墙之后没有非零退出"


def test_截图请求文件的形状():
    """请求文件本身就是这张图的来路——每一条都要能说清是谁、截什么、为什么。"""
    files = sorted(Path("data/social_shot_requests").glob("*.json"))
    assert files, "一个请求文件都没有，这条判据的主语没了"
    for path in files:
        req = json.loads(path.read_text(encoding="utf-8"))
        assert req.get("slug"), f"{path.name} 没有 slug"
        assert str(req.get("_why") or "").strip(), f"{path.name} 没写为什么要这几张"
        names = [s.get("name") for s in req["shots"]]
        assert len(names) == len(set(names)), f"{path.name} 里有重名的 shot"
        for shot in req["shots"]:
            assert shot.get("url", "").startswith("https://"), shot
            assert str(shot.get("_why") or "").strip(), (
                f"{path.name} 的 {shot.get('name')} 没写为什么要这一张")
            assert int(shot.get("revision", 1)) >= 1
