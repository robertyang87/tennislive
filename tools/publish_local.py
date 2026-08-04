#!/usr/bin/env python3
"""把一条已经渲好的片子填进小红书 / 抖音 / 视频号的发布页，**停在发布按钮前**。

这一步为什么不在 GitHub Actions 上跑
------------------------------------

三个平台的官方发布 API 都走不通：**视频号根本没有**（视频号助手 API 只有小店、
橱窗、直播、罗盘，全是电商）；抖音的 `video.create` 要企业/个体工商户主体加应用
审核；小红书开放平台要企业认证。个人号一条都拿不到。

剩下的路是浏览器自动化，而它**必须跑在有登录态的那台机器上**——runner 在美国
机房，拿国内登录的 cookie 去访问必然触发异地风控。CLAUDE.md 里那条
「YouTube 对机房 IP 一律 Sign in to confirm」是同一个坑，只是换了个站。

所以这条线是：**Actions 管渲染、质检、推微信；这个脚本管最后一公里。**

用法
----

    # 一次性：每个平台扫一次码，登录态存在 ~/.tennislive-publish/ 下
    python tools/publish_local.py --login xiaohongshu

    # 日常：填好三个平台，停在发布按钮前，你扫一眼再点
    python tools/publish_local.py --slug zhang-putintseva

    # 只填一个平台
    python tools/publish_local.py --slug zhang-putintseva --only xiaohongshu

    # 不开浏览器，只看会填什么（改文案之后先跑这个）
    python tools/publish_local.py --slug zhang-putintseva --dry-run

三条硬规矩
----------

- **绝不自己点发布。** 这个脚本填完就停，`_PUBLISH_HINT` 里那个选择器只用来
  确认「走到了」，一次都不点。微信那条消息发出去收不回来，这三个平台同理，
  而且发出去的是给陌生人看的。要改这一条得先改 `test_本地发布不许自己点发布`。
- **每一步都出声，成功失败都出声。** CLAUDE.md 那条「只在成功时出声的检查，
  没法证明它真的看过」的镜像版同样成立——只在失败时出声的脚本，没法证明它
  成功过。所以每一格填完都打印一行。
- **登录态过期和平台改版要分开报。** 两者都表现为「找不到那个框」，但处置
  完全相反：前者去 `--login` 重扫一次码，后者要改选择器。混成一句
  「填不进去」，下一个人得自己去分辨。

清单从哪来
----------

`output/<日期>/reel/<slug>/publish.json`，由 `push_reel.py --stage manifest`
在渲染之后、提交之前写进仓库（见那个文件的 `build_manifest`）。

**这个脚本不读 spec，也不算标题。** 标题怎么从 `cover` 拼出来、正文怎么切、
成片走 jsDelivr 还是 Release——那些全是 `push_reel.py` 的事，这儿只管填。
一个数写两处必分叉，而这次的两处是微信和三个发布页：真让它们各算一遍，
迟早出现「微信标题说张帅赢了、小红书标题说普汀塞娃赢了」。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# 登录态存这儿，**不进仓库**。一个平台一份，互不影响：小红书过期了不该
# 连带把视频号也踢下线。
STATE_DIR = Path("~/.tennislive-publish").expanduser()

# 出错时的截图落这儿。平台改版的时候，那张图是唯一的线索——只报一句
# 「找不到标题框」，下一个人还得自己再跑一趟才知道页面长什么样。
SHOT_DIR = STATE_DIR / "shots"

# 每一格等多久。上传视频那一步单独给（见 `UPLOAD_TIMEOUT_MS`）——
# 几十 MB 的片子传上去要按分钟算，拿填表的超时去卡它必然误判成「页面坏了」。
FIELD_TIMEOUT_MS = 30_000
UPLOAD_TIMEOUT_MS = 15 * 60 * 1000


@dataclass
class Platform:
    """一个平台的发布页长什么样。

    选择器单独列出来是**故意的**：这三个页面都会改版，而改版之后要动的就是
    这几行。抖音尤其——它的 CSS 类名是随机生成的，所以一律用相对定位
    （文案里的字、`input[type=file]` 这种结构特征），别去钉 class。
    """

    key: str
    name: str
    # 发布页。直接进这个地址，省掉从首页点进去那几步。
    publish_url: str
    # 判「登录态还在不在」用的地址。一般就是发布页——没登录会被踢回登录页。
    login_url: str
    # 没登录时会出现的东西。**判据是「登录页的特征出现了」，不是「发布页的
    # 特征没出现」**：后者在页面改版时也成立，会把改版误报成掉登录。
    logged_out_hint: str
    # 视频文件的输入框。三个平台都是标准的 file input，只是藏在自定义控件底下。
    file_input: str
    # 标题那一格。
    title_box: str
    # 正文那一格。
    body_box: str
    # 发布按钮。**只用来确认走到了，一次都不点。**
    publish_hint: str
    # 这个平台标题的字数上限（小红书字位：全角 1、半角 0.5）。0 表示没量过。
    title_max: float = 0
    notes: list[str] = field(default_factory=list)


PLATFORMS: dict[str, Platform] = {
    # 小红书是三个里最好做的：创作后台明确支持存草稿和定时发布，而这条线的
    # 文案本来就是按小红书写的（`specs/reels/*.xhs.txt`，1000 字正文闸就在
    # `push_reel.split_copy` 里）。
    "xiaohongshu": Platform(
        key="xiaohongshu",
        name="小红书",
        publish_url="https://creator.xiaohongshu.com/publish/publish?target=video",
        login_url="https://creator.xiaohongshu.com/login",
        logged_out_hint="text=扫码登录",
        file_input="input[type=file]",
        title_box="input[placeholder*='标题']",
        body_box="div[contenteditable='true']",
        publish_hint="button:has-text('发布')",
        # `push_reel._fits` 已经按这个数卡过整句了，所以这儿只是复核。
        title_max=20,
        notes=[
            "正文粘进去之后 `#话题` 不一定会自动变成话题——要变成蓝色的那种，"
            "得在编辑器里点一下候选。填完自己看一眼。",
            "存草稿和定时发布都在发布按钮旁边，按需要自己点。",
        ],
    ),
    # 抖音：creator.douyin.com 可以传视频存草稿。它的前端类名是随机的，
    # 所以下面一律用相对定位，别改成钉 class。
    "douyin": Platform(
        key="douyin",
        name="抖音",
        publish_url="https://creator.douyin.com/creator-micro/content/upload",
        login_url="https://creator.douyin.com/",
        logged_out_hint="text=扫码登录",
        file_input="input[type=file]",
        title_box="input[placeholder*='作品标题']",
        body_box="div[contenteditable='true']",
        publish_hint="button:has-text('发布')",
        notes=[
            "抖音把标题和正文合成一格的时候有过好几版——真填进去看一眼是不是"
            "两格都吃到了字。",
            "「存草稿」按钮在发布按钮左边。",
        ],
    ),
    # 视频号：登录态绑微信扫码，过期比另外两个勤。
    "channels": Platform(
        key="channels",
        name="视频号",
        publish_url="https://channels.weixin.qq.com/platform/post/create",
        login_url="https://channels.weixin.qq.com/login",
        logged_out_hint="text=扫码登录",
        file_input="input[type=file]",
        title_box="input[placeholder*='概括视频主要内容']",
        body_box="div[contenteditable='true']",
        publish_hint="button:has-text('发表')",
        notes=[
            "视频号的「标题」其实是短标题（6~16 字），描述另有一格——"
            "这条线的标题是 20 字位，可能要手动收一下。",
            "登录态绑微信扫码，过期比另外两个勤，掉了就 --login channels。",
        ],
    ),
}


def load_manifest(slug: str, root: Path) -> dict:
    """按 slug 找那份 `publish.json`，**只找最新的一份**。

    ⚠️ 同一条片子会重渲好几次（CLAUDE.md：eala-fernandez 渲过 3 轮），
    而重渲会落在**同一个日期目录**里；真正会出现多份的是跨日重发。取最新那份，
    并且**把取到的是哪一份打出来**——「取错了版本」和「取对了」在填进去之前
    长得一模一样，而填错的那一版会被发出去。
    """
    hits = sorted(root.glob(f"output/*/reel/{slug}/publish.json"))
    if not hits:
        # 空结果先自证是真空：分清「这个 slug 不存在」和「这一版还没跑
        # --stage manifest」，两者的下一步完全不同。
        dirs = sorted(root.glob(f"output/*/reel/{slug}"))
        if dirs:
            raise SystemExit(
                f"{slug} 的产物目录在（{dirs[-1]}），但没有 publish.json。\n"
                "那是渲染的时候没跑 `push_reel.py --stage manifest`——\n"
                "补一次：PYTHONPATH=src python3 tools/push_reel.py --stage manifest \\\n"
                f"          --outdir {dirs[-1]} --copy specs/reels/{slug}.xhs.txt")
        known = sorted(p.parent.name for p in root.glob("output/*/reel/*/publish.json"))
        raise SystemExit(
            f"找不到 {slug} 的发布包。现有的：{'、'.join(known) or '一个都没有'}")
    if len(hits) > 1:
        print(f"[清单] {slug} 有 {len(hits)} 份，取最新的 {hits[-1].parent.parent.parent.name}")
    doc = json.loads(hits[-1].read_text(encoding="utf-8"))
    doc["_manifest_path"] = str(hits[-1])
    return doc


def resolve_video(manifest: dict, root: Path) -> Path:
    """成片在本地哪儿。不在就说清楚怎么拿。

    ⚠️ **`path` 空着不是漏了**：超过 95 MiB 的成片走 GitHub Release 附件，
    渲完本地那份就删了（见 `push_reel.released_video_url`）。所以这儿分两种
    情况报——「仓库里没有，去 Release 下」和「仓库里该有却找不到」，
    处置完全不同。
    """
    video = manifest["video"]
    if video["path"]:
        local = root / video["path"]
        if local.is_file():
            mb = local.stat().st_size / 1024 / 1024
            print(f"[成片] {local}（{mb:.1f} MB）")
            return local
        raise SystemExit(
            f"清单说成片在 {local}，但那儿没有文件。\n"
            "多半是 git pull 之后这一格没拉下来（仓库用的是稀疏检出）：\n"
            f"  git sparse-checkout add {Path(video['path']).parent}")
    raise SystemExit(
        f"这一版成片走了 Release 附件（{video['url']}），本地没有。\n"
        "先下下来再跑：\n"
        f"  curl -L -o /tmp/{video['name']} '{video['url']}'\n"
        f"  然后 --video /tmp/{video['name']}")


def describe(manifest: dict, video: Path | None) -> None:
    """把「会填什么」原样打出来。`--dry-run` 就只做这一件事。

    改完文案先跑一次这个——比开浏览器快，也比填进去再发现写错便宜。
    """
    print(f"\n{'=' * 60}")
    print(f"slug   {manifest['slug']}（{manifest['date']} · {manifest['column']}）")
    print(f"标题   {manifest['title']}")
    print(f"话题   {'、'.join(manifest['hashtags']) or '（无）'}")
    print(f"成片   {video if video else manifest['video']['url']}")
    print(f"封面   {manifest['poster']['path'] or '（没有海报）'}")
    print(f"{'-' * 60}")
    print(manifest["body"])
    print(f"{'=' * 60}\n")
    for plat in PLATFORMS.values():
        if plat.title_max:
            width = _xhs_width(manifest["title"])
            flag = "" if width <= plat.title_max else f"  ⚠️ 超 {plat.title_max} 字位"
            print(f"  {plat.name}：标题 {width:g} 字位{flag}")


def _xhs_width(text: str) -> float:
    """小红书字位：全角 1、半角 0.5。和 `push_reel._fits` 是同一把尺。"""
    from tennislive.render.xiaohongshu import xhs_title_len  # noqa: PLC0415

    return xhs_title_len(text)


def _shot(page, plat: Platform, tag: str) -> Path:
    """出错时留一张图。平台改版的时候这是唯一的线索。"""
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SHOT_DIR / f"{plat.key}-{tag}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        print(f"  [截图] {path}")
    except Exception as exc:  # noqa: BLE001 - 截图失败不该盖过真正的错
        print(f"  [截图] 存不下来（{exc}）")
    return path


def _fill(page, plat: Platform, selector: str, value: str, what: str) -> None:
    """填一格，**填完出声**，失败时把两种可能分开说。"""
    try:
        box = page.locator(selector).first
        box.wait_for(state="visible", timeout=FIELD_TIMEOUT_MS)
        box.click()
        box.fill("") if box.get_attribute("contenteditable") is None else None
        box.type(value, delay=8)
        print(f"  [{what}] 填好了（{len(value)} 字）")
    except Exception as exc:  # noqa: BLE001
        _shot(page, plat, f"fill-{what}")
        raise SystemExit(
            f"{plat.name}：{what}那一格填不进去。\n"
            f"  选择器 {selector}\n"
            f"  {type(exc).__name__}: {str(exc).splitlines()[0][:160]}\n"
            "  两种可能，处置相反——**先看上面那张截图**：\n"
            f"    页面是登录页 → 登录态过期了，跑 --login {plat.key} 重扫一次码\n"
            f"    页面是发布页 → 平台改版了，改 PLATFORMS['{plat.key}'] 里的选择器"
        ) from exc


def publish_one(ctx, plat: Platform, manifest: dict, video: Path) -> bool:
    """填一个平台，**停在发布按钮前**。返回是不是走到了那一步。"""
    print(f"\n▶ {plat.name}")
    page = ctx.new_page()
    page.goto(plat.publish_url, wait_until="domcontentloaded")

    # 先判登录态。**判据是「登录页的特征出现了」**，不是「发布页的特征没
    # 出现」——后者在改版时也成立，会把改版误报成掉登录，然后人白扫一次码。
    try:
        page.locator(plat.logged_out_hint).first.wait_for(state="visible", timeout=4000)
        _shot(page, plat, "logged-out")
        print(f"  [登录] 掉了。跑一次：python tools/publish_local.py --login {plat.key}")
        return False
    except Exception:  # noqa: BLE001 - 等不到登录页特征，说明登录态还在
        print("  [登录] 还在")

    try:
        page.locator(plat.file_input).first.set_input_files(str(video))
        print(f"  [上传] {video.name} 已提交，等平台处理…")
    except Exception as exc:  # noqa: BLE001
        _shot(page, plat, "upload")
        raise SystemExit(
            f"{plat.name}：视频传不上去（{plat.file_input}）。\n"
            f"  {type(exc).__name__}: {str(exc).splitlines()[0][:160]}\n"
            "  看一眼截图：是发布页改版了，还是这个平台今天要求先选别的选项。"
        ) from exc

    _fill(page, plat, plat.title_box, manifest["title"], "标题")
    _fill(page, plat, plat.body_box, manifest["body"], "正文")

    # 走到发布按钮就停。**只确认它在，不点。**
    try:
        page.locator(plat.publish_hint).first.wait_for(
            state="visible", timeout=UPLOAD_TIMEOUT_MS)
        print(f"  [就绪] 已停在「{plat.name}」的发布按钮前——你自己看一眼再点。")
    except Exception:  # noqa: BLE001
        _shot(page, plat, "no-publish-button")
        print(f"  [就绪] 没等到发布按钮。多半是视频还在转码（大片子要几分钟），"
              f"页面开着，转完自己就出来了。")
    for note in plat.notes:
        print(f"  · {note}")
    return True


def do_login(plat: Platform) -> int:
    """开一个有头浏览器让人扫码，扫完把登录态存下来。"""
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = STATE_DIR / f"{plat.key}.json"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(plat.login_url, wait_until="domcontentloaded")
        print(f"\n浏览器已经开在「{plat.name}」的登录页。")
        print("扫码登录，进到后台首页之后回这儿按一下回车。")
        input("  登录好了就按回车 > ")
        ctx.storage_state(path=str(state))
        browser.close()
    print(f"登录态存好了：{state}")
    print("⚠️ 这个文件等于你的登录凭据，别提交进仓库、别发给别人。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slug", help="要发的那条片子，如 zhang-putintseva")
    ap.add_argument("--only", action="append", choices=sorted(PLATFORMS),
                    help="只发这个平台，可重复。默认三个都发")
    ap.add_argument("--login", choices=sorted(PLATFORMS),
                    help="扫码登录这个平台并把登录态存下来")
    ap.add_argument("--dry-run", action="store_true",
                    help="不开浏览器，只打印会填什么")
    ap.add_argument("--video", help="成片路径。默认按清单找；走了 Release 的要自己下")
    ap.add_argument("--root", default=".", help="仓库根目录")
    args = ap.parse_args()

    if args.login:
        return do_login(PLATFORMS[args.login])
    if not args.slug:
        ap.error("要么 --login <平台>，要么 --slug <片子>")

    root = Path(args.root).resolve()
    manifest = load_manifest(args.slug, root)

    video: Path | None = None
    if not args.dry_run:
        video = Path(args.video).expanduser() if args.video else resolve_video(manifest, root)
        if not video.is_file():
            raise SystemExit(f"成片不在：{video}")

    describe(manifest, video)
    if args.dry_run:
        print("（--dry-run：没开浏览器，一个字都没填）")
        return 0

    targets = [PLATFORMS[k] for k in (args.only or sorted(PLATFORMS))]
    missing = [p for p in targets if not (STATE_DIR / f"{p.key}.json").is_file()]
    if missing:
        raise SystemExit(
            "这几个平台还没登录过：" + "、".join(p.name for p in missing) + "\n"
            + "\n".join(f"  python tools/publish_local.py --login {p.key}" for p in missing))

    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    ready: list[str] = []
    with sync_playwright() as pw:
        # **有头浏览器，而且不许改成 headless。** 这个脚本的终点是「你看一眼
        # 再点发布」，看不见就没法看。
        browser = pw.chromium.launch(headless=False)
        for plat in targets:
            ctx = browser.new_context(
                storage_state=str(STATE_DIR / f"{plat.key}.json"))
            try:
                if publish_one(ctx, plat, manifest, video):
                    ready.append(plat.name)
            except SystemExit as exc:
                # 一个平台坏了不该把另外两个也停掉——填好的那些还等着人点。
                print(f"  ❌ {exc}")
        print(f"\n{'=' * 60}")
        print(f"填好了：{'、'.join(ready) or '一个都没有'}")
        print("三个页面都开着，**一个都没点发布**。你自己扫一眼再点。")
        input("全都发完了就按回车关掉浏览器 > ")
        browser.close()
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
