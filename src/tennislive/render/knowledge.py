"""「网球有故事」这一栏还留在生产线上的那几件事。

图文知识帖（静态四宫格卡）那条线 2026-09-15 停产，`generate_knowledge_package`
连同它的选题校验、正文拼装、配图预检一起删掉了——工作流 `knowledge-adhoc.yml`
和 CLI 入口已经先一步拿掉，删的时候生产调用方是 0。

剩下的两拨各有真实调用方，别再当成知识帖的零件一起清：

- 栏目名与标题：`render/webcards.py` 拿 `knowledge_column` 印在卡的台头上，
  `tests/test_platform_title_limits.py` 拿两个标题函数卡小红书 20 字位 /
  公众号 64 字。
- `knowledge_push_html_from_parts`：**字卡解说片（「网球有故事」字卡那条产线）的
  微信推送正文从这儿出**（`video/explainer.py`），和知识帖无关。⚠️ 原来这里写着
  「采访线也从这儿出」——不对：赛场之上、赛后开麦、网球有故事剪辑片走的是
  `tools/push_reel.py` 的 `build_html`。两个模板的样子现在都从 `render/push_style.py`
  出（2026-09-27 UI 评审 WP2），同一栏目的两条产线推出来长得一样。
"""

from __future__ import annotations

# design-tokens: enforced
import html

from ..digest import Digest
from . import push_style as ps
from .tournament_story import TournamentStory
from .copy_title import COPY_TITLE_MAX, compact_copy_title, copy_title

# 栏目名印在标题上——读者只看标题，承诺印不出来这个栏目对外就不存在。
# 见 docs/columns.md 与 docs/column-operations.md 的 R4。
# 2026-09-15 起只剩「网球有故事」一个知识栏目（「历史上的今天」停产，选题和
# 分支一起拿掉了），所以这里是一个常量，不是一张按 slug 分派的表。
_COLUMN_NAME = "网球有故事"
_COLUMN_EMOJI = "📖"


def knowledge_column(story: TournamentStory) -> str:
    """这条故事对外挂在哪个栏目下."""
    return _COLUMN_NAME


def knowledge_title(story: TournamentStory, digest: Digest) -> str:
    trivia_hooks = {
        "scoring-history": "网球为什么是15、30、40？",
        "yellow-ball": "网球为什么从白色变黄？",
        "longest-match": "最长一场网球，到底打了多久？",
        "hawkeye": "误判催生网球鹰眼",
        "golden-slam": "金满贯到底有多难？",
        "surfaces": "三种场地，真像三项运动？",
        "big-three": "三巨头统治了多少年？",
        "china-tennis": "中国网球，从哪一冠开始？",
        # 兜底的「X 的故事」在这条上尤其糟：「签表上那个 WC的故事」——
        # 既丢了空格，也把全篇最硬的那个数字留在了标题外面。
        "wildcard": "第125名靠外卡拿了温网",
    }
    if story.kind == "player":
        hook = f"{story.title}，不只是一场比分"
    elif story.kind == "trivia":
        hook = trivia_hooks.get(story.slug, f"{story.title}，你真懂吗？")
    else:
        hook = f"为什么要记住{story.title}？"
    if len(compact_copy_title(hook)) > COPY_TITLE_MAX:
        if story.kind == "player":
            short_name = story.title.rsplit("·", 1)[-1]
            hook = f"{short_name}的来路"
        else:
            hook = f"{story.title}的故事"
    if len(compact_copy_title(hook)) > COPY_TITLE_MAX:
        hook = story.title
    return copy_title(hook)


def knowledge_wechat_title(story: TournamentStory, digest: Digest) -> str:
    """Use a distinct, fully preserved title for WeChat image posts."""
    title = (
        f"{digest.today.month}.{digest.today.day}"
        f"{knowledge_column(story)}｜{story.title}"
    )
    if len(title) > 64:
        raise ValueError(f"公众号图片消息标题超长: {len(title)} > 64")
    return title


def knowledge_push_html_from_parts(
    *,
    image_urls: list[str],
    xhs_text: str,
    copy_url: str,
    video_url: str = "",
    column: str = _COLUMN_NAME,
) -> str:
    """The push body itself, given the pieces.

    Split out so the explainer video can send the same layout instead of
    growing its own — the badge, the per-image "didn't load?" fallback, the
    copy page button and the long-press hint are the parts that make a push
    usable on a phone, and they were worth having in one place.

    ⚠️ **知识帖和解说片两条线的微信正文都从这儿出**。AI 生成合成内容标识
    原来就是加在这一处的（别在两个调用方各加一遍），**2026-08-15 起不加了**，
    见 `ai_disclosure` 顶上那段。

    ⚠️ **「网球有故事」的两条产线推出来要长得一样**（2026-09-27 UI 评审 3.2）：
    原来这儿的药丸写「知识解说视频 · 9.26」、没有标题提示行、按钮「▶ 打开 9:16
    成片」，而同一栏目的剪辑片（`push_reel.build_html`）写的是栏目名、有提示行、
    按钮「▶ 打开竖版成片」。**药丸文字和按钮文字原来是调用方传进来的**——
    这正是它们分叉的原因。现在药丸只收栏目名（`column`，默认就是这一栏），
    视频按钮只收链接，文字和样式都从 `push_style` 出。

    每张图的回退链接是灰色「原图 ↗」，图的 `alt` 只写「第 N 页」——原来 alt 里
    带着整句标题、链接写「第N张未显示？点此打开原图」，**每张图各印一遍**，
    而推送有 2 万字的上限（`pushplus.check_content_length`），样式一加就挤掉
    能发的图数（`test_字卡推送图多也装得下_每张图不比改之前更贵`）。

    ⚠️⚠️ 卡底那颗红按钮是**字面写在这儿的**，逐字节不动（账号所有者 2026-08-31
    「微信推送的红色按钮不要改了」；它比 `push_reel` 那颗多一个分号，那也不动）。
    """
    lines = xhs_text.strip().splitlines()
    title = html.escape(lines[0] if lines else "")
    body_start = 2 if len(lines) > 1 and not lines[1].strip() else 1
    body = "\n".join(lines[body_start:]).strip()
    # One block, not paragraph divs: the body has to be readable *and* liftable
    # in a single long-press. Splitting it into elements made copying a drag-
    # across-the-whole-screen job, and pairing pretty paragraphs with a second
    # copyable copy of the same text just sent everything twice. pre-wrap keeps
    # the blank lines between beats, so it reads the same and selects as one.
    images = [
        ps.image(url, f"第{index}页", ps.SLIDE_RATIO, rounded=True, data_src=True)
        + ps.original_link(url)
        for index, url in enumerate(image_urls, 1)
    ]
    action = ps.video_button(video_url) if video_url else ""
    red = (f'<a href="{copy_url}" style="display:block;background-color:#ff2442;color:#ffffff;text-align:center;text-decoration:none;font-weight:bold;padding:13px 16px;border-radius:6px;margin:0 0 7px;">'  # token-exempt: 红按钮逐字节不动（2026-08-31）
           "分别复制标题 / 正文 / 置顶评论</a>")
    return f"""<div lang="zh-CN" class="tl-push" style="{ps.PAGE}">{ps.system_theme_style()}
<div style="{ps.card("18px 16px 22px")}">
  {ps.pill(column)}
  {ps.title_block(title)}
  {ps.title_hint()}
  {''.join(images)}
  {ps.body_block(body)}
  <div style="{ps.DIVIDER}"></div>
  {action}{red}
  {ps.foot()}
</div>
</div>"""
