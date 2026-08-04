"""发布包清单 + 本地发布脚本的判据。

这条线的形状和别处不同：**真正要验的那一步在沙箱和 CI 上都走不到**——它要
一台有登录态的国内机器，而验一次的代价是把内容发给陌生人。CLAUDE.md 里那条
最贵的教训（「判据只在发布路径上才走得到，它就永远验不了」）在这儿正面撞上。

所以判据分两层，都不碰浏览器：

- **能验死的**：清单里的字和复制页里的字是不是同一段（真渲两份逐字节比）、
  `~` 展没展开、报错说不说得出出路。
- **只能盯位置的**：发布按钮不许被点、清单那一步排在提交之前。
  这类查的是**代码结构**，防的是「有人把它改坏了」，防不住「它从来没工作过」——
  后者只有那台机器上跑一次才知道，所以这个文件不假装验过。
"""

from __future__ import annotations

import ast
import html
import json
import os
import re
import sys
from pathlib import Path

import pytest

TOOL = Path("tools/publish_local.py")
PUSH = Path("tools/push_reel.py")
WORKFLOW = Path(".github/workflows/match-reel.yml")


def _mod(name: str):
    sys.path.insert(0, str(Path("tools").resolve()))
    sys.path.insert(0, str(Path("src").resolve()))
    return __import__(name)


def test_发布只能走核对过的那一条路():
    """点发布的地方**只许有一处**，而且它必须先核对页面上的内容。

    2026-08-04 账号所有者：「那可以直接点击发帖么」——所以「绝不自己点发布」
    那条规矩让位了。**但让位的是「谁来按」，不是「按之前要不要核对」。**

    停在发布按钮前买的从来不是那个点击动作，是**有人确认过三个格子真的填对了**。
    那部分可以用机器做：`verify_filled` 把页面上真实的标题和正文读回来跟清单比。
    标题填空了、正文被截断了、视频还在转码——这几种在页面上长得都很正常，
    只有读回来才分得出来。又一次「查产物不查信号」。

    所以判据从「一次都不许点」换成「只能从那一条核对过的路上点」。
    """
    src = TOOL.read_text(encoding="utf-8")
    tree = ast.parse(src)

    # ⚠️ **按调用链扫是不够的，而且错在危险的那一头。**
    # `_click_publish` 里写的是
    #     btn = page.locator(plat.publish_hint).first
    #     btn.click()
    # 按 `.click()` 的接收方扫，源码片段只有 `btn`，看不到 `publish_hint`——
    # 于是老那条「一次都不许点」会**在代码真的会发布的情况下报绿**。
    # 改成按**函数作用域**判：函数体里同时出现 `publish_hint` 和 `.click()`
    # 就算「这个函数会点发布」。
    clickers = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        body = ast.get_source_segment(src, node) or ""
        if "publish_hint" in body and ".click()" in body:
            clickers.append(node.name)
    assert clickers == ["_click_publish"], (
        f"会点发布的函数是 {clickers}——只许 `_click_publish` 一个，"
        "而且它必须先核对")

    # 那一处必须先核对，而且核对不过要 return，不是打一行日志就往下走
    gate = src[src.index("def _click_publish("):src.index("def _click_draft(")]
    assert gate.index("verify_filled(") < gate.index("btn.click()"), (
        "先点了再核对——那时候已经发出去了")
    assert "return False" in gate[:gate.index("btn.click()")], (
        "核对不过没有 return，会继续往下点")


def test_发布不是默认行为():
    """默认必须停在按钮前。**不可逆的动作不许是默认值。**"""
    src = TOOL.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and getattr(node.func, "attr", "") == "add_argument"
                and any(getattr(a, "value", None) == "--publish" for a in node.args)):
            kw = {k.arg: k.value for k in node.keywords}
            assert getattr(kw.get("action"), "value", "") == "store_true", (
                "--publish 不是 store_true，默认值可能不是 False")
            break
    else:
        raise AssertionError("没有 --publish 这个开关，这条判据的主语没了")

    # 函数签名那一头也要默认关着——工作流/别的调用方可能绕过 argparse。
    mod = _mod("publish_local")
    import inspect  # noqa: PLC0415

    sig = inspect.signature(mod.publish_one)
    assert sig.parameters["publish"].default is False, "publish_one 默认就在发"
    assert sig.parameters["draft"].default is False


def test_发布和存草稿是互斥的():
    """两个终点性质不同，**不许猜**——猜错的那一半收不回来。"""
    src = TOOL.read_text(encoding="utf-8")
    assert "--publish 和 --draft 只能选一个" in src, "没拦同时给两个开关"


def test_核对正文只比开头一段():
    """全文比必然误报，而**一个天天误报的闸等于没有闸**。

    平台的编辑器会把 `#话题` 变成药丸、把长文折叠，尾部本来就读不全；
    开头那一段是纯散文，取得回来也最能证明「粘的是这一版」。
    """
    src = TOOL.read_text(encoding="utf-8")
    body = src[src.index("def verify_filled("):src.index("def _click_publish(")]
    assert "[:120]" in body, "正文比的不是开头一段"
    assert "_norm(" in body, "没有归一化——空白重排会让逐字节比必然失败"
    # 标题反过来要**整句**比：它短，而且是最容易被受控组件吃掉的那一格。
    assert '_norm(manifest["title"])' in body, "标题没有整句比"


def test_登录态目录要展开波浪号():
    """`Path("~/…")` 是一个**名叫 `~` 的相对目录**，不是 home。

    CLAUDE.md 记着这笔老账：源片缓存写成 `~/.cache/…` 之后两趟 run 全绿，
    一个字节都没缓存——`actions/cache` 找的是真的 `$HOME`，而 Python 在工作区
    里建了个叫 `~` 的目录。这儿同样的形状，只是丢的是登录态。
    """
    mod = _mod("publish_local")
    assert "~" not in mod.STATE_DIR.parts, (
        f"登录态目录没展开：{mod.STATE_DIR}——会在当前目录建一个名叫 ~ 的文件夹")
    assert mod.STATE_DIR.is_absolute(), f"{mod.STATE_DIR} 不是绝对路径"
    assert str(mod.STATE_DIR).startswith(str(Path.home())), (
        f"{mod.STATE_DIR} 没落在 home 底下")
    # 截图目录同理——它是出错时唯一的线索，落错地方等于没有。
    assert "~" not in mod.SHOT_DIR.parts


def test_登录态过期和平台改版要分开报():
    """两者都表现为「找不到那个框」，但处置完全相反。

    混成一句「填不进去」，下一个人得自己再跑一趟才知道该扫码还是该改选择器。
    这和 CLAUDE.md 里「『读不到运行列表』和『没跑起来』处置相反，日志里不许
    混成一句」是同一条。
    """
    src = TOOL.read_text(encoding="utf-8")
    fill = src[src.index("def _fill("):src.index("def publish_one(")]
    assert "--login" in fill, "报错里没说「登录态过期了去重扫码」这条路"
    assert "改版" in fill and "选择器" in fill, "报错里没说「平台改版了去改选择器」这条路"
    assert "截图" in fill, "报错里没让人去看截图——那是分辨这两种情况的唯一依据"


def test_判登录态要认登录页的特征不认发布页的():
    """判据是「登录页出现了」，不是「发布页没出现」。

    后者在**改版**时也成立，于是改版会被误报成掉登录，人白扫一次码而问题还在。
    又一次「判据宁可窄，不可宽」。
    """
    mod = _mod("publish_local")
    for plat in mod.PLATFORMS.values():
        assert plat.logged_out_hint, f"{plat.name} 没写掉登录的特征"
        # 拿发布页自己的选择器去判掉登录，就是上面说的那个错法。
        assert plat.logged_out_hint not in (plat.title_box, plat.body_box,
                                            plat.file_input, plat.publish_hint), (
            f"{plat.name} 拿发布页的选择器在判登录态——改版会被误报成掉登录")


def test_每个平台的选择器都齐了():
    """半个是最坏的情况：填到一半才发现少一格，视频已经传上去了。"""
    mod = _mod("publish_local")
    assert set(mod.PLATFORMS) == {"xiaohongshu", "douyin", "channels"}, (
        "平台清单变了——三个平台是账号所有者点名的那三个")
    for key, plat in mod.PLATFORMS.items():
        assert plat.key == key, f"{key} 的 key 和字典键对不上"
        for field in ("name", "publish_url", "login_url", "logged_out_hint",
                      "file_input", "title_box", "body_box", "publish_hint"):
            assert getattr(plat, field), f"{plat.name} 少了 {field}"
        assert plat.publish_url.startswith("https://"), f"{plat.name} 的发布页不是 https"


def _fake_outdir(tmp_path: Path, slug: str) -> Path:
    """造一个长得像真产物的目录：日期在路径里，mp4 有大小。

    **成片用稀疏文件**（`os.truncate`），不真写 36 MB——CLAUDE.md 那条
    「需要『一个大文件』这类真实条件时，`os.truncate` 造一个就够，别去
    `output/` 里找」正是为这种情形写的，而且 CI 上根本没有 `output/`。
    """
    outdir = tmp_path / "output" / "2026-08-04" / "reel" / slug
    outdir.mkdir(parents=True)
    mp4 = outdir / f"{slug}.mp4"
    mp4.touch()
    os.truncate(mp4, 36 * 1024 * 1024)
    (outdir / "poster.jpg").write_bytes(b"\xff\xd8\xff")
    return outdir


def _title_and_body(push, outdir: Path, copy_path: Path):
    """按 `push_reel.main` 那一段原样算一次标题和正文。"""
    import argparse  # noqa: PLC0415

    text = push.cut_at_tags(copy_path.read_text(encoding="utf-8"))
    column = push.column_of(copy_path)
    args = argparse.Namespace(matchup="", score="", event="", summary="", lead="")
    meta = push.resolve_meta(copy_path, args)
    title = push.headline(outdir, column, meta["matchup"], meta["score"],
                          meta["event"], meta["summary"], "")
    return column, f"{title}\n\n{text}"


# 豁免表和「真发出去的是哪一段」都收在 `conftest.py`——`test_小红书正文不许
# 超一千字` 和这个文件共用同一份。**两处各写一份必分叉**，而分叉的后果是
# 一边豁免了一边没豁免，然后有人去改文案迁就那条红的。
from conftest import (  # noqa: E402
    OVERLONG_LEGACY as _OVERLONG_LEGACY,
    assert_legacy_still_overlong as _assert_legacy_overlong,
    shipped_body as _shipped_body,
)


def _specs_with_push_block():
    """能算出标题的那些 spec。只吃 `specs/`——CI 上没有 `output/`。"""
    out = []
    for spec in sorted(Path("specs/reels").glob("*.json")):
        copy_path = spec.with_suffix(".xhs.txt")
        if not copy_path.is_file():
            continue
        doc = json.loads(spec.read_text(encoding="utf-8"))
        cover = doc.get("cover") or {}
        # 标题末尾那一格要么来自对阵，要么来自 push.summary，两个都没有的
        # `resolve_meta` 会报错——那是它该报的，不是这条判据要测的。
        if (cover.get("versus") or {}).get("names") or cover.get("matchup") \
                or (doc.get("push") or {}).get("summary"):
            out.append(copy_path)
    return out


def test_发布包清单和复制页是同一段字(tmp_path):
    """清单里的标题/正文，必须和复制页那两格**逐字节相同**。

    这是这条线的核心判据。三个发布页和微信推送用的要是两套算法，迟早出现
    「微信标题说张帅赢了、小红书标题说普汀塞娃赢了」——`wang-samsonova` 那次
    海报和标题在同一条推送里说反赛果，就是同一个形状，而消息发出去收不回来。

    ⚠️ **两边都用真渲染器的输出，不手搓页面。** CLAUDE.md 记着这笔账：
    「是不是这一版」那道闸恒真了一个月，根因就是判据喂的是手搓的假页面
    （`tmp_copy_page("<h1>…</h1>")`），它证明的是「函数能从 h1 里抠字」，
    而不是「真页面的 h1 是当期标题」。
    """
    push = _mod("push_reel")
    from tennislive.render.pushmsg import to_copy_page  # noqa: PLC0415

    checked = 0
    for copy_path in _specs_with_push_block():
        slug = copy_path.name.split(".")[0]
        if slug in _OVERLONG_LEGACY:
            raw = push.cut_at_tags(copy_path.read_text(encoding="utf-8"))
            _assert_legacy_overlong(slug, _shipped_body(raw), push.BODY_MAX)
            continue
        outdir = _fake_outdir(tmp_path / slug, slug)
        column, copy_text = _title_and_body(push, outdir, copy_path)
        manifest = push.build_manifest(
            outdir, *push.split_copy(copy_text), column, f"{slug}.mp4")

        page = to_copy_page(copy_text)
        for key in ("title", "body"):
            found = re.search(rf'<textarea id="{key}"[^>]*>(.*?)</textarea>',
                              page, re.S)
            assert found, f"{slug}：复制页里没有 {key} 那一格"
            assert manifest[key] == html.unescape(found.group(1)), (
                f"{slug} 的 {key} 对不上——清单和复制页算出了两段不同的字\n"
                f"  清单  {manifest[key][:80]!r}\n"
                f"  复制页 {html.unescape(found.group(1))[:80]!r}")
        checked += 1

    # 判据自己的判据：主语没了要出声，而不是变成一条恒真的绿灯。
    # CLAUDE.md：那句 `assert checked >= 9` 没白写——「要是没有它，这条测试会在
    # CI 上『通过』整整一年，一条 spec 都没校过」。
    assert checked >= 9, f"只校到 {checked} 条 spec，判据的主语没了"


def test_清单里的话题就是正文里的那几个(tmp_path):
    """话题不许另写一份——两处写迟早对不上，而读者看到的是正文那份。"""
    push = _mod("push_reel")
    from tennislive.render.hashtags import hashtags  # noqa: PLC0415

    checked = 0
    for copy_path in _specs_with_push_block():
        slug = copy_path.name.split(".")[0]
        if slug in _OVERLONG_LEGACY:
            raw = push.cut_at_tags(copy_path.read_text(encoding="utf-8"))
            _assert_legacy_overlong(slug, _shipped_body(raw), push.BODY_MAX)
            continue
        outdir = _fake_outdir(tmp_path / slug, slug)
        column, copy_text = _title_and_body(push, outdir, copy_path)
        manifest = push.build_manifest(
            outdir, *push.split_copy(copy_text), column, f"{slug}.mp4")
        assert manifest["hashtags"] == hashtags(manifest["body"]), (
            f"{slug}：清单里的话题和正文里的对不上")
        checked += 1
    assert checked >= 9, f"只校到 {checked} 条 spec"


def test_走了Release的片子清单里不许留一个假路径(tmp_path):
    """本地没有那份 mp4 的时候，`path` 要是空的，`released` 要是真的。

    **不能按文件大小去猜走了哪条路**：走了 Release 之后本地文件已经删了，
    `stat()` 会直接炸；而更坏的是算出一个 raw 链接发出去——那个路径上根本
    没有文件（CLAUDE.md 记过这一条）。
    """
    push = _mod("push_reel")
    slug = "eala-osaka"
    outdir = tmp_path / "output" / "2026-08-04" / "reel" / slug
    outdir.mkdir(parents=True)
    url = "https://github.com/robertyang87/tennislive/releases/download/x/eala-osaka.mp4"
    (outdir / "render.json").write_text(json.dumps({"video_url": url}),
                                        encoding="utf-8")

    manifest = push.build_manifest(outdir, "标题", "正文", "赛场之上", f"{slug}.mp4")
    assert manifest["video"]["released"] is True
    assert manifest["video"]["path"] == "", (
        "本地没有那份 mp4，清单却给了一个路径——下游会去找一个不存在的文件")
    assert manifest["video"]["url"] == url

    # 反过来：mp4 真在仓库里的时候，path 必须给出来，别让下游白下一遍。
    local = _fake_outdir(tmp_path / "local", slug)
    m2 = push.build_manifest(local, "标题", "正文", "赛场之上", f"{slug}.mp4")
    assert m2["video"]["released"] is False
    assert m2["video"]["path"].endswith(f"{slug}.mp4")


def test_清单那一步要排在渲染之后提交之前():
    """位置错了，闸就是空的——这条线上栽过四次。

    `--stage page` 排在渲染**之前**（让 Pages 的发布和渲染并行）；
    `--stage manifest` 相反，它要知道成片有多大，所以排在渲染**之后**、
    提交**之前**（不然它自己进不了仓库，本地那台机器就读不到）。

    CLAUDE.md：「复制页那道闸装在『渲』的那一步而不是『发』的那一步」，
    行为测试三档全绿、按钮照样每次消失——**只测行为拦不住位置错**。
    """
    if not WORKFLOW.is_file():
        pytest.skip(f"{WORKFLOW} 不在")
    body = WORKFLOW.read_text(encoding="utf-8")
    # 扫工作流一律先去掉整行注释：注释正是这个仓库记教训的地方，正文里必然
    # 写着当年那些错值，连它一起扫会把「把坑记下来」判成「又踩了这个坑」。
    yaml_only = "\n".join(
        line for line in body.splitlines() if not line.lstrip().startswith("#"))
    if "--stage manifest" not in yaml_only:
        pytest.skip("工作流还没接上 --stage manifest")
    at = yaml_only.index("--stage manifest")
    commit = yaml_only.find("git commit")
    assert commit > at, "清单那一步排在提交之后了——它自己进不了仓库"


def test_本地脚本不假装能在CI上验完():
    """这个脚本的关键路径只有那台有登录态的机器上走得到，文档里要说清楚。

    CLAUDE.md 那条最贵的教训：Pages 那个修复「写了，没跑过」躺了一天，
    因为它的判据只有真推送时才走得到。这儿的形状一样，但**拆不出去**——
    验一次的代价是把内容发给陌生人。所以退而求其次：**把这件事写明白**，
    别让下一个人以为绿灯等于验过了。
    """
    doc = TOOL.read_text(encoding="utf-8")
    assert "登录态" in doc and "机房" in doc, "没写清楚为什么不能在 Actions 上跑"
    assert "--dry-run" in doc, "没给一条不开浏览器就能自查的路"
    # 而那条路必须真的够得着，不是只写在文档里。
    mod = _mod("publish_local")
    assert "dry_run" in mod.main.__code__.co_names or "dry-run" in doc


def test_清单那条路不许碰Pages():
    """`--stage manifest` 在任何一次探活之前就 return，一次都碰不到 Pages。

    这条判据是**另一条判据的授权书**：`test_会发微信的工作流都要能触发Pages`
    原来按「跑没跑 `push_reel.py`」推，于是把清单那一步也判成「要 token」。
    收窄它的前提是「manifest 真的走不到探活」——**那句话得有人钉住**，
    不然收窄就成了一张白名单，而白名单会在下一次改动时悄悄过期。

    所以这儿从源码推：清单那一段里不许出现任何探活入口，而且它必须
    **先 return**，别只是「碰巧还没走到」。
    """
    src = PUSH.read_text(encoding="utf-8")
    body = src[src.index('if args.stage == "manifest":'):]
    body = body[:body.index("        return 0") + len("        return 0")]

    probes = ("wait_for_copy_page", "live_copy_page_url", "trigger_pages_build",
              "_probe_page", "wait_for_video", "wait_for_images", "push(")
    hit = [p for p in probes if p in body]
    assert not hit, (
        f"清单那一段碰到了 {hit}——那它就得跟别的发微信步骤一样配 token 和 "
        "actions: write，`test_会发微信的工作流都要能触发Pages` 里那个 skip 要撤掉")

    # 而且要**真的先 return**：探活那几处必须都排在这一段后面。
    at = src.index('if args.stage == "manifest":')
    for probe in ("wait_for_copy_page(", "wait_for_video("):
        assert src.index(probe, at) > at, f"{probe} 排在清单那一段前面了"

    # 判据自己的判据：这几个名字得真的还在 push_reel 里，否则这条是恒真的绿灯。
    for probe in ("wait_for_copy_page", "wait_for_video", "trigger_pages_build"):
        assert probe in src, f"{probe} 没了——这条判据的主语变了，得重写"


def test_清单里的链接一律钉main不跟着分支走(tmp_path, monkeypatch):
    """`--stage manifest` 跑在渲染那一步，**那时候还在特性分支上**。

    `video_url` / `poster_url` 默认跟 `GITHUB_REF_NAME` 走——对推送那条路是对的
    （它必须在 main 上跑），但清单跟着走就会 baked in 一个
    `.../claude-xxx/output/...`：合并之后分支一删，链接全 404。

    **这个错几天后才发作，而且发作时看起来像「GitHub 挂了」。** 清单本来就是给
    「合并之后」用的（本地脚本默认从 main 取），所以 main 是唯一说得通的值。

    反向验证：把那两处的 `"main"` 拿掉，这条当场红。
    """
    push = _mod("push_reel")
    monkeypatch.setattr(push, "BRANCH", "claude/some-feature-branch")

    outdir = _fake_outdir(tmp_path, "demo")
    manifest = push.build_manifest(outdir, "标题", "正文", "赛场之上", "demo.mp4")

    for what, url in (("成片", manifest["video"]["url"]),
                      ("封面", manifest["poster"]["url"])):
        assert "some-feature-branch" not in url, (
            f"{what}链接跟着分支走了：{url}\n"
            "合并之后分支一删就是 404，而那要过几天才发作")
        assert "/main/" in url or "@main/" in url, f"{what}链接没钉在 main 上：{url}"

    # 判据自己的判据：`BRANCH` 得真的还在被 `video_url` 用着，否则这条测的是
    # 一个已经不存在的行为——那时候它是绿的，而清单可能正跟着别的东西跑。
    monkeypatch.setattr(push, "BRANCH", "another-branch")
    assert "another-branch" in push.video_url(outdir, "demo.mp4"), (
        "video_url 已经不看 BRANCH 了——这条判据的前提没了，得重写")


def test_doctor验的启动方式要和真发片一样():
    """`--doctor` 起浏览器的方式必须和 `main` 里真发片那次一模一样。

    第一版 doctor 验的是 `headless=True`，而填表走的是 `headless=False`。
    **新版 playwright 的无头模式是另一个可执行文件**（chromium-headless-shell），
    实测报错路径都不同：

        headless=True   .../chromium_headless_shell-1234/chrome-headless-shell-…
        headless=False  .../chromium-1234/chrome-linux64/chrome

    所以验 headless 过了、真发片起不来是可能的——**而那时候视频已经在传了**。
    又一次「查的东西和跑的东西不是一回事」。
    """
    src = TOOL.read_text(encoding="utf-8")
    modes = re.findall(r"chromium\.launch\(headless=(\w+)", src)
    assert modes, "没有任何一处起 Chromium——doctor 和发片流程都该有"
    assert set(modes) == {"False"}, (
        f"起 Chromium 的方式不一致：{modes}。doctor 验的必须是发片真用的那种，"
        "否则它会在「验过了」的情况下放行一台起不来浏览器的机器")


def test_doctor把三件事分开报():
    """装了包、下了浏览器、有登录态——**三件事的出路完全不同**。

    混成一句「环境没配好」，人得自己一件件试。这和「登录态过期和平台改版要
    分开报」是同一条，只是挪到了开跑之前。
    """
    src = TOOL.read_text(encoding="utf-8")
    body = src[src.index("def doctor("):src.index("def do_login(")]
    assert "pip install requests" in body, "没说 requests 怎么装"
    assert "pip install playwright" in body, "没说 playwright 怎么装"
    assert "playwright install chromium" in body, "没说 Chromium 怎么下"
    assert "--login" in body, "没说登录态怎么补"
    # macOS 的老坑：系统 Python 装不了包，而报错本身不会说该建 venv。
    assert "venv" in body, "没给 macOS 那条 externally-managed 的出路"


def test_存草稿的按钮不许和发布按钮是同一个():
    """`--draft` 会**点** `draft_hint`。它要是指到发布按钮上，就是自动发布。

    存草稿和发布的性质完全不同：草稿留在自己账号里、不对任何人可见；
    发布是把一条没人看过的片子推给陌生人，而且**收不回来**。所以
    「绝不自己点发布」那条规矩没有松动——松动的只是「存草稿也算发布」这个
    误解。

    ⚠️ 这三个 `draft_hint` 我**验不了**（要有登录态的国内机器），所以判据钉两层：
    这条是静态的（两个选择器不许相同、不许互相包含），运行时 `_click_draft`
    还会读一遍按钮上的字再决定点不点。
    """
    mod = _mod("publish_local")
    for plat in mod.PLATFORMS.values():
        if not plat.draft_hint:
            continue
        assert plat.draft_hint != plat.publish_hint, (
            f"{plat.name} 的存草稿和发布是同一个选择器——--draft 会把片子发出去")
        # 互相包含也不行：`has-text('发')` 会同时选中「发布」和「转发」。
        assert plat.publish_hint not in plat.draft_hint, (
            f"{plat.name} 的 draft_hint 包住了 publish_hint：{plat.draft_hint}")
        for word in mod._NEVER_CLICK:
            assert word not in plat.draft_hint, (
                f"{plat.name} 的存草稿选择器里出现了「{word}」：{plat.draft_hint}\n"
                "存草稿的按钮上不该有这种字，出现了多半是抄错了发布按钮")


def test_点存草稿之前要读一遍按钮上的字():
    """静态判据挡不住「平台改版之后 draft_hint 恰好选中了发布按钮」。

    那种情况下选择器字面上仍然写着「存草稿」，而页面上那个位置换成了别的按钮
    ——**只有读按钮自己的文字才分得出来**。又一次「查产物不查信号」：
    选择器是信号，按钮上的字才是产物。
    """
    src = TOOL.read_text(encoding="utf-8")
    body = src[src.index("def _click_draft("):src.index("def publish_one(")]
    assert "inner_text" in body, "点之前没读按钮上的字"
    assert "_NEVER_CLICK" in body, "没拿禁用词表复核"
    # 顺序要对：先读、先判，最后才点。
    assert body.index("_NEVER_CLICK") < body.index("btn.click()"), (
        "先点了再检查——那时候已经晚了")


def test_draft那条路不许顺手把片子发出去():
    """`--draft` 点的是存草稿，**不许走到 `_click_publish`**。

    加新能力最容易的失手就是给它开一个绕过老闸的后门：草稿这条路要是掉进
    发布分支，人以为存了草稿、实际发出去了，而且不会有人告诉他。
    """
    src = TOOL.read_text(encoding="utf-8")
    draft = src[src.index("def _click_draft("):src.index("def publish_one(")]
    assert "_click_publish" not in draft, "存草稿那条路里出现了发布"
    assert "publish_hint" not in draft, "存草稿那条路碰了发布按钮的选择器"

    # 而分发那一处：publish 和 draft 必须是**互斥的分支**，不是两句顺序执行。
    one = src[src.index("def publish_one("):src.index("def doctor(")]
    assert "elif draft:" in one, (
        "publish 和 draft 不是 if/elif——顺序执行的话 --publish 会先发再存草稿")


def test_网页草稿不同步手机App这件事要说出来():
    """**网页草稿和手机 App 的草稿箱是两个存储。**

    账号所有者要草稿箱正是为了「人在外面用手机发」，而手机 App 里根本看不到
    网页存的草稿——不说清楚，他会在 App 里找一个不存在的东西，然后以为脚本
    没存上。出路是手机浏览器开创作后台。

    这条查的是**脚本自己会不会说**，不是文档里写没写——人跑脚本的时候不看文档。
    """
    src = TOOL.read_text(encoding="utf-8")
    mod = _mod("publish_local")
    assert "手机 App 里看不到" in src or "手机 App" in src, "没提手机 App 看不到这回事"
    assert "手机浏览器" in src, "没给「人在外面怎么发」的出路"
    # 三个平台里至少小红书和抖音要在 notes 里各自说一遍——收尾那段是统一说的，
    # 但人可能只发一个平台，那时候只看得到这个平台的 notes。
    said = [p.name for p in mod.PLATFORMS.values()
            if any("App" in n or "手机浏览器" in n for n in p.notes)]
    assert len(said) >= 2, f"只有 {said} 在自己的注记里提了这件事"
