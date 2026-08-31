"""PushPlus 手机推送专用模板：窄屏友好 + 深色模式安全.

要点：
- 显式设置背景色和文字色（微信深色模式不会反转显式配色的卡片）
- 每条信息一行、行内容短，避免窄屏换行错乱
- 只放决策所需信息（焦点/中国军团/今晚看点），完整内容看仓库或公众号
"""

from __future__ import annotations

import html
import logging
import math
import os
import re

import requests

from ..digest import Digest
from ..timeutil import fmt_schedule_time, fmt_time_beijing
from .common import (
    curate_for_social,
    group_by_tournament,
    is_chinese_involved,
    match_round_display,
    side_display,
)
from .rating import (
    is_tour_focus_match,
    stay_up_stars,
    tonight_event_focus,
    top_results,
)
from .titles import pick_headline_auto
from ..cdn import jsdelivr_base

logger = logging.getLogger(__name__)

# 主题策略：内联浅色样式兜底 + <style> 媒体查询做深色覆盖。
# 微信内置浏览器支持 prefers-color-scheme；若个别环境剥离 <style>，
# 退回内联浅色版本，两种模式下都可读。
_CARD = (
    "background-color:#f4f7f5;color:#1c2b26;border-radius:12px;"
    "padding:14px 16px;font-size:15px;line-height:1.9;"
)
_TITLE = "font-size:17px;font-weight:bold;color:#0b3d2e;"
_HEAD = "color:#0a7d43;font-weight:bold;font-size:16px;"
_SEC = "font-weight:bold;color:#0b3d2e;margin-top:6px;"
_DIM = "color:#5f6f68;font-size:13px;"
_HR = '<div class="tl-hr" style="border-top:1px solid #d8e2dc;margin:10px 0;"></div>'
_COPY_BUTTON = (
    "display:block;background-color:#0a7d43;color:#ffffff;"
    "text-align:center;text-decoration:none;font-weight:bold;"
    "padding:12px 16px;border-radius:8px;margin:8px 0;"
)

# 深色模式：品牌深绿底 + 荧光黄强调
_DARK_CSS = """<style>
@media (prefers-color-scheme: dark) {
  .tl-card { background-color: #10201a !important; color: #e2e9e5 !important; }
  .tl-title { color: #ccff00 !important; }
  .tl-head { color: #b8e986 !important; }
  .tl-sec { color: #ccff00 !important; }
  .tl-dim { color: #93a39b !important; }
  .tl-hr { border-top-color: #2a3a33 !important; }
  .tl-copy { background-color: #0d1a15 !important; color: #dfe7e3 !important;
             border-color: #2a3a33 !important; }
}
</style>"""


def _short_side(players) -> str:
    return side_display(players, with_flag=True, with_seed=False, short_en=True)


def _score_of(m) -> str:
    return m.score_display(from_winner=True)


# 卡片图 CDN：jsDelivr 镜像 GitHub 内容，国内可访问
_REPO = os.environ.get("GITHUB_REPOSITORY", "robertyang87/tennislive")
_CDN = jsdelivr_base(_REPO)
_OWNER, _REPO_NAME = _REPO.split("/", 1)
_PAGES = os.environ.get(
    "TENNISLIVE_PAGES_URL", f"https://{_OWNER}.github.io/{_REPO_NAME}"
).rstrip("/")

_ASSET_REVISION_RE = re.compile(r"[0-9a-fA-F]{7,40}")
# 主机名不写死：换镜像之后，只认 cdn. 的正则会**悄悄不匹配**，于是推送里的
# 图片全部停在 @main 上，钉版本那一步等于没做（同一路径的新旧内容会被
# 微信的图片缓存混起来，正是当初钉 commit 要解决的问题）。
_JSDELIVR_MAIN_RE = re.compile(
    r"(https://[a-z0-9.\-]+\.jsdelivr\.net/gh/[^/@\s\"'<>]+/[^/@\s\"'<>]+)@main/"
)


def pin_asset_revision(html_content: str, revision: str) -> str:
    """Pin jsDelivr GitHub assets to an immutable commit revision."""
    if not _ASSET_REVISION_RE.fullmatch(revision):
        return html_content
    return _JSDELIVR_MAIN_RE.sub(rf"\g<1>@{revision}/", html_content)


def to_copy_page(
    xhs_text: str,
    alt_titles: list[str] | None = None,
    pinned_comment: str | None = None,
) -> str:
    """生成适合手机打开的一键复制页面。

    alt_titles：V1 §3.1 的备选标题（候选 ②③），人工从 3 个候选里选 1 个。

    ⚠️ **复制页是四条线共用的那个出口**（解说片 / 知识帖 / 内容雷达 / 竖版
    短片都调它），也是文案真正被粘到小红书的地方。AI 生成合成内容标识原来就是
    加在这儿的，**2026-08-15 起不加了**（账号所有者：「以后不要出现这些东西」，
    见 `ai_disclosure` 顶上那段）。
    """
    lines = xhs_text.splitlines()
    title = lines[0].strip() if lines else ""
    body_start = 2 if len(lines) > 1 and not lines[1].strip() else 1
    body = "\n".join(lines[body_start:]).strip()
    safe_title = html.escape(title)
    safe_body = html.escape(body)
    safe_comment = html.escape((pinned_comment or "").strip())
    # 没有置顶评论就别留那一格：一个空框加一个复制不出东西的按钮，
    # 页面上看着像坏了（竖版赛报那条线没有置顶评论，一渲染就露馅）。
    comment_section = f"""<section>
      <div class="label"><span>置顶评论</span><button type="button" data-copy="comment">复制评论</button></div>
      <textarea id="comment" readonly>{safe_comment}</textarea>
    </section>""" if safe_comment else ""
    alt_sections = ""
    for i, alt in enumerate(t for t in (alt_titles or []) if t and t != title):
        safe_alt = html.escape(alt)
        alt_sections += f"""
    <section>
      <div class="label"><span>备选标题 {i + 2}</span><button type="button" data-copy="alt{i}">复制</button></div>
      <textarea id="alt{i}" class="alt" readonly>{safe_alt}</textarea>
    </section>"""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>复制贴图文案</title>
  <style>
    :root {{ color-scheme: light dark; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f4f7f5; color: #1c2b26;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ width: min(100%, 680px); margin: 0 auto; padding: 20px 16px 40px; }}
    h1 {{ margin: 0 0 6px; font-size: 24px; letter-spacing: 0; }}
    .sub {{ margin: 0 0 20px; color: #5f6f68; font-size: 14px; }}
    section {{ margin-top: 18px; }}
    .label {{ display: flex; align-items: center; justify-content: space-between;
      gap: 12px; margin-bottom: 8px; font-weight: 700; }}
    button {{ border: 0; border-radius: 8px; background: #0a7d43; color: #fff;
      min-height: 42px; padding: 0 16px; font-size: 15px; font-weight: 700; }}
    textarea {{ display: block; width: 100%; resize: vertical; border: 1px solid #d8e2dc;
      border-radius: 8px; background: #fff; color: #1c2b26; padding: 12px;
      font: 15px/1.7 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    #title {{ min-height: 76px; }}
    .alt {{ min-height: 52px; }}
    #body {{ min-height: 55vh; }}
    #comment {{ min-height: 118px; }}
    #toast {{ position: fixed; left: 50%; bottom: 22px; transform: translateX(-50%);
      background: #10201a; color: #fff; padding: 10px 16px; border-radius: 8px;
      opacity: 0; pointer-events: none; transition: opacity .18s ease; }}
    #toast.show {{ opacity: 1; }}
    @media (prefers-color-scheme: dark) {{
      body {{ background: #10201a; color: #e2e9e5; }}
      .sub {{ color: #93a39b; }}
      textarea {{ background: #0d1a15; color: #dfe7e3; border-color: #2a3a33; }}
      button {{ background: #b8e986; color: #10201a; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>贴图发布文案</h1>
    <p class="sub">标题和正文已分开，可直接粘贴到发布页。</p>
    <section>
      <div class="label"><span>标题</span><button type="button" data-copy="title">复制标题</button></div>
      <textarea id="title" readonly>{safe_title}</textarea>
    </section>{alt_sections}
    <section>
      <div class="label"><span>正文</span><button type="button" data-copy="body">复制正文</button></div>
      <textarea id="body" readonly>{safe_body}</textarea>
    </section>
    {comment_section}
  </main>
  <div id="toast" role="status">已复制</div>
  <script>
    const toast = document.getElementById('toast');
    async function copyText(id) {{
      const field = document.getElementById(id);
      try {{
        await navigator.clipboard.writeText(field.value);
      }} catch (_) {{
        field.focus(); field.select(); document.execCommand('copy');
      }}
      const labels = {{body: '正文已复制', comment: '评论已复制'}};
      toast.textContent = labels[id] || '标题已复制';
      toast.classList.add('show');
      setTimeout(() => toast.classList.remove('show'), 1400);
    }}
    document.querySelectorAll('[data-copy]').forEach((button) => {{
      button.addEventListener('click', () => copyText(button.dataset.copy));
    }});
  </script>
</body>
</html>
"""


#: 推送卡片底部那两颗按钮的配色和高度。**三条线共用这一份**
#: （`tools/push_reel.py` 的成片推送、`render/knowledge.py` 的知识帖、
#: 本文件这条已停产的日报模板），别再各自内联一遍——同一件事写三处必分叉，
#: 而分叉的样子是「同一个账号发出去的推送，按钮高矮不一」。
#:
#: ⭐ **红的那颗要比深绿那颗矮。** 账号所有者 2026-08-31：「红色区域高度可以
#: 更小一些」。来路是这两颗按钮原来**一模一样高**（各 47px），而红色的视觉分量
#: 天生比深绿重——于是「分别复制标题 / 正文」这个**次要动作**在卡片底部喊得比
#: 「▶ 打开竖版成片」这个**主要动作**还响，层级是反的。
#:
#: 四档真渲量过（Chromium，390px 视口，和微信里同一个字号）：
#:
#:     padding-y 13px → 47px   和主按钮一样重 ← 改之前
#:     padding-y 10px → 41px   轻下来了，层级读得出
#:     **padding-y  8px → 37px   现在这档：明确是次要动作，还是一颗正经按钮**
#:     padding-y  6px → 33px   字快贴着上下边，看着是「压扁了」不是「次要」
#:
#: ⚠️ **别再往下压**：6px 那档已经不像按钮；而且它仍然是个要用手指点的链接，
#: 37px 已经贴着舒适点击区的下沿了。
#: ⚠️ **矮的只有红那颗**。主按钮跟着一起矮，层级差就又没了——这条改动的全部
#: 内容就是那个高度差。
PUSH_BTN_BG_PRIMARY = "#102d23"
PUSH_BTN_BG_COPY = "#ff2442"
PUSH_BTN_PAD_Y = 13
PUSH_BTN_PAD_Y_COPY = 8


def push_button(url: str, label: str, *, primary: bool) -> str:
    """推送卡片底部的一颗按钮。`primary=False` 就是那颗红的「复制」按钮。

    ⚠️ **`href` 里的 `copy.html` 是 `_COPY_BUTTON_RE` 认领这颗按钮的钥匙**
    （复制页探不到时只摘这一个 `<a>`，正文照发）。那条正则认的是 href 不是
    样式，所以改高度不影响它——但**别把 href 包进别的标签里**。
    """
    bg = PUSH_BTN_BG_PRIMARY if primary else PUSH_BTN_BG_COPY
    pad_y = PUSH_BTN_PAD_Y if primary else PUSH_BTN_PAD_Y_COPY
    return (f'<a href="{url}" style="display:block;background-color:{bg};'
            f'color:#ffffff;text-align:center;text-decoration:none;'
            f'font-weight:bold;padding:{pad_y}px 16px;border-radius:6px;'
            f'margin:0 0 7px;">{html.escape(label)}</a>')


def to_push_html(
    digest: Digest,
    cards: list[str] | None = None,
    xhs_text: str | None = None,
    videos: list[str] | None = None,
) -> str:
    """Render the PushPlus review message as the actual Xiaohongshu post.

    ⚠️ 这里原来会补一行 AI 生成合成内容标识，**2026-08-15 起不补了**，
    见 `ai_disclosure` 顶上那段。
    """
    d = digest.today
    raw = (xhs_text or "").strip()
    lines = raw.splitlines()
    title = lines[0].strip() if lines else pick_headline_auto(digest)
    body_start = 2 if len(lines) > 1 and not lines[1].strip() else 1
    body = "\n".join(lines[body_start:]).strip()
    safe_title = html.escape(title)

    parts = [
        '<div style="background-color:#f6f7f4;color:#17251f;padding:12px 10px;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">',
        '<div style="max-width:680px;margin:0 auto;background-color:#ffffff;'
        'border-top:5px solid #ff2442;padding:18px 16px 22px;">',
        '<div style="display:inline-block;background-color:#e7f5ea;color:#087747;'
        'font-size:12px;font-weight:bold;padding:4px 8px;border-radius:4px;">'
        f'小红书待发稿 · {d.month}.{d.day}</div>',
        f'<div style="font-size:23px;line-height:1.38;font-weight:800;color:#102d23;'
        f'margin:10px 0 14px;">{safe_title}</div>',
    ]

    # Keep the image deck above the caption so the phone review mirrors a note.
    if cards:
        for name in cards:
            safe_name = html.escape(name, quote=True)
            url = f"{_CDN}/output/{d.isoformat()}/cards/{safe_name}"
            parts.append(
                f'<img src="{url}" data-src="{url}" width="100%" '
                'referrerpolicy="no-referrer" style="width:100%;border-radius:6px;'
                'margin:0 0 10px;display:block;" />'
            )
        parts.append(
            '<div style="color:#7a8580;font-size:12px;margin:0 0 18px;">'
            '长按保存图片 · 按当前顺序上传小红书</div>'
        )

    if body:
        parts.append(
            '<div style="border-left:3px solid #f1c84b;padding-left:12px;'
            'margin:4px 0 14px;font-size:13px;font-weight:bold;color:#087747;">'
            '可直接发布的正文</div>'
        )
        for paragraph in re.split(r"\n\s*\n", body):
            safe_paragraph = "<br/>".join(
                html.escape(line) for line in paragraph.splitlines()
            )
            if paragraph.lstrip().startswith("#"):
                style = "color:#087747;font-size:14px;line-height:1.8;margin:14px 0 0;"
            else:
                style = "color:#25342e;font-size:15px;line-height:1.85;margin:0 0 13px;"
            parts.append(f'<div style="{style}">{safe_paragraph}</div>')

    if xhs_text:
        copy_url = f"{_PAGES}/output/{d.isoformat()}/copy.html"
        parts.extend(
            [
                '<div style="border-top:1px solid #e6ebe8;margin:18px 0 12px;"></div>',
                push_button(copy_url, "分别复制标题 / 正文 / 置顶评论",
                            primary=False),
                '<div style="text-align:center;color:#7a8580;font-size:12px;">'
                '标题与正文已拆分，粘贴后即可发布</div>',
            ]
        )

    if videos:
        parts.append(
            '<div style="border-top:1px solid #e6ebe8;margin:18px 0 12px;"></div>'
            '<div style="font-size:15px;font-weight:bold;color:#102d23;margin-bottom:8px;">'
            '视频素材</div>'
        )
        for name in videos:
            safe_name = html.escape(name, quote=True)
            url = f"{_CDN}/output/{d.isoformat()}/video/{safe_name}"
            parts.append(
                f'<a href="{url}" style="display:block;background-color:#102d23;'
                'color:#ffffff;text-align:center;text-decoration:none;font-weight:bold;'
                'padding:12px 16px;border-radius:6px;margin:6px 0;">▶ 播放竖版视频</a>'
            )

    parts.extend(["</div>", "</div>"])
    return "\n".join(parts)


def copy_page_url(day, *, subdir: str = "schedule") -> str:
    return f"{_PAGES}/output/{day.isoformat()}/{subdir}/copy.html"


_COPY_BUTTON_RE = re.compile(
    r'<a\s+href="(?P<url>[^"]*?/copy\.html)"[^>]*>.*?</a>\s*', re.DOTALL
)


#: 复制页里**当期标题**所在的那一格。指纹必须取这里，不能取 `<h1>`。
_COPY_TITLE_RE = re.compile(
    r'<textarea id="title"[^>]*>(.*?)</textarea>', re.DOTALL
)


def copy_page_fingerprint(path) -> str:
    """从本地 copy.html 里取一句能认出「是不是这一版」的话。

    取 `<textarea id="title">` 里那句——它是**当期文案的标题**
    （如「7.29 今日赛程 | 王欣瑜战萨姆索诺娃」），换一版必然跟着变。

    ⚠️ **原来取的是 `<h1>`，而模板里 `<h1>` 写死是「贴图发布文案」**——
    一个常量。于是这个函数对任何一天的复制页都返回同一句话，
    `drop_dead_copy_button(expect=...)` 里那句 `expect in response.text`
    **恒真**：线上还是上一版的内容，闸照样放行。

    这正是 CLAUDE.md 里用翻车换来的那条规矩本身：「**「可达」不等于
    「是这一版」**……读者点开看到的是另一批场次——这比死链更糟，
    死链一眼能看出坏了，旧内容看着完全正常」。**规矩写对了，实现是空的。**

    判据落在 `test_复制页指纹必须能区分两版`：两份不同文案的指纹必须不同，
    而且必须真的出现在渲出来的页面里（否则探活永远匹配不上，闸从放行恒真
    变成拦截恒真——那是另一头的坏）。

    取不到就返回空串，调用方退回只探可达。
    """
    from pathlib import Path

    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""
    match = _COPY_TITLE_RE.search(text)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


#: 探复制页的重试预算。**这两个数是量出来的，不是拍的，别往下调。**
#:
#: 原来是 3 次 × 20 秒 = 40 秒，配的注释写着「Pages 重新发布要一两分钟」——
#: 那句话被 2026-08-02 那次证伪了：成片 16:11:08 提交到 main，16:11:48 探到
#: 404，一直到 16:2x 才返回 200，**超过 12 分钟**。于是「保护排名」那条推送
#: 的复制页按钮被摘掉了（run 30707429355），而闸门本身没判错——页面是真的
#: 还没发布。
#:
#: 40 秒对「合并很久之后再推」够用，对「合并完立刻重渲再推」永远不够：
#: 渲染→提交→探链接全在 50 秒内跑完，Pages 怎么都赶不上。所以真正的毛病是
#: 预算，不是闸门。12 × 30 秒 = 6 分钟，覆盖今天这次的大半，又留得住
#: 工作流 25 分钟的超时余量（出片本身只花 5 分钟）。
#:
#: 等不到仍然只摘按钮、不拦推送——正文整段渲染在消息里，长按可复制。
# **这个数是从实测的 Pages 构建时长倒推的，不是拍的。**
#
# 2026-08-03 那条解说片推送没有复制按钮，日志里连探 12 次全是 404，然后按兜底
# 摘掉了按钮（run 30800394939）。查下来不是「今天 Pages 慢」，是**窗口结构性地
# 短于发布时间**：这个仓库 `output/` 一 GB 多，Pages 每次重建整站，实测
#
#     0cfe168  5:50 success      89f34a1  7:14 success
#     7c90993  8:12 cancelled    42764e0  9:30 cancelled
#
# 而 12 × 30s 只有 **5.5 分钟**——比最快的那次还短。也就是说这条线上那颗按钮
# 几乎不可能等到，而它每次都「安静地」退回无按钮版，看起来和「Pages 恰好慢了」
# 一模一样。⚠️ 又一次「兜底出事的时候不吭声」。
#
# 26 次 × 30 秒 ＝ **12.5 分钟**，盖住实测最慢的那次（9:30）还留三分钟余量。
# 探到就立刻返回，所以典型代价仍是 6–8 分钟，不是 12.5。
#
# ⚠️ **同一趟 run 里提交两次会把前一次的 Pages 构建取消掉**（上表里两条
# cancelled 就是这么来的）。所以「把复制页挪到渲染前面单独提交」那条对
# match-reel 有效的办法，对解说片**无效**——它生成和推送在同一趟 run 里，
# 成片那次提交会把复制页那次的构建掐掉重来。真正的杠杆是把站点变小。
#
# ⚠️ **上面那张表是「整站发布」时代的数，#168 之后已经不成立了。**
# 那之后 `pages.yml` 只收 `output/**/*.html`（0.66 MB，站点的 0.03%），
# 2026-08-04 实测两趟成功构建：
#
#     run 30875246633  27 秒      run 30875537112  20 秒
#
# **少了一个数量级。** 窗口没跟着收——收窄是危险的那一头（探不到就永远没有
# 按钮，而且不报错），而探到就立刻返回，所以留着宽窗口的代价是 0。
# 记在这儿是因为「带数字的注释会过期，而它过期的时候不吭声」：下一个人读到
# 5:50~9:30 会以为这条线还是那么慢，然后去优化一个已经没了的问题。
_COPY_PAGE_ATTEMPTS = int(os.environ.get("TENNISLIVE_COPYPAGE_ATTEMPTS") or 26)
_COPY_PAGE_RETRY_SECONDS = float(
    os.environ.get("TENNISLIVE_COPYPAGE_RETRY_SECONDS") or 30.0
)
#: 整站发布时代实测最慢的一次成功构建（`42764e0`，9 分 30 秒）。等待窗口不许
#: 比它短——短了那颗按钮就永远出不来，而且不会报错。判据在 test_explainer 里。
#: 这个数**故意不按 #168 之后的 20~27 秒往下调**：它是安全下界，不是当前耗时。
MEASURED_PAGES_BUILD_SECONDS = 570.0

#: 端到端实测：`trigger_pages_build()` 点下去到 Pages 部署完成有多少秒。
#: 2026-08-04 06:41Z 量的（selftest run 30884872530 → pages run 30884890108，
#: dispatch 06:41:32 → deploy 完 06:41:51）。
#:
#: **它不是超时，是判据**：探活间隔 30 秒，19 < 30 意味着**第 1 次探活就该中**。
#: 探了两次以上说明这条链上还有别的没接上（点没点动、提交排在探活后面、
#: 指纹取错了那一格），**别当成「Pages 今天慢」放过去**——那正是它藏了一个月
#: 的方式。日志里那句 `复制页第 N 次探活命中` 就是给这个判据用的。
MEASURED_PAGES_DISPATCH_TO_LIVE_SECONDS = 19.0

#: Pages 部署那条工作流。**主线才有意义**——Pages 只服务 main。
_PAGES_WORKFLOW = "pages.yml"


def _gh_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def pages_runs(
    token: str, repo: str, *, per_page: int = 5, timeout: int = 15
) -> list[tuple[int, str, str]] | None:
    """最近几条 `pages.yml` 的运行记录：`(id, actor, event)`，新的在前。

    **读不到返回 `None`，一条都没有返回 `[]`**——两者必须分开。合成一档的话
    「查不了」会被读成「没跑起来」，而这两件事的处置正好相反。
    """
    url = (f"https://api.github.com/repos/{repo}/actions/"
           f"workflows/{_PAGES_WORKFLOW}/runs?per_page={per_page}")
    try:
        r = requests.get(url, timeout=timeout, headers=_gh_headers(token))
        if r.status_code != 200:
            logger.info("[Pages] 读运行列表失败：HTTP %s", r.status_code)
            return None
        runs = r.json().get("workflow_runs") or []
    except (requests.RequestException, ValueError) as exc:
        logger.info("[Pages] 读运行列表失败（%s: %s）", type(exc).__name__, exc)
        return None
    return [(int(run["id"]),
             str((run.get("actor") or {}).get("login") or "?"),
             str(run.get("event") or "?"))
            for run in runs if run.get("id") is not None]


def trigger_pages_build(
    *, ref: str = "main", timeout: int = 15, confirm_seconds: float = 25.0
) -> bool:
    """让 Pages 重新发布。**工作流自己提交的那次 push 不会触发它。**

    2026-08-04 挖出来的静默回归。判据是 `pages.yml` 从上线到出事的**全部**
    四趟运行记录：

        #1  workflow_dispatch  我手动跑的第一趟
        #2  push               **真人合并 PR #166**      ← 唯一自动触发的
        #3  workflow_dispatch  工作流提交的佩古拉复制页    ← 手动补的
        #4  workflow_dispatch  工作流提交的伊埃拉复制页    ← 手动补的

    两次由推送流程自己 commit + push 的复制页，**一次都没触发部署**。原因是
    GitHub 明文规定：用仓库自带的 `GITHUB_TOKEN` 推上去的 push **不会创建新的
    workflow run**（防递归），而复制页正是工作流自己推的。

    #168 之前 Pages 走的是「从分支部署」——那不是工作流，谁推都重建，所以这条
    路一直通（只是慢，整站一两 GB 要六到九分钟）。换成 Actions 部署之后，
    **触发器写对了，可它对这条唯一重要的路径是空的**。

    ⚠️ **症状是「慢」不是「错」，所以它能藏住**：探活一直 404，探满
    `_COPY_PAGE_ATTEMPTS` 次（26 × 30s ＝ 12.5 分钟）之后静静摘掉按钮、
    正文照发。伊埃拉那条连吃七次 404，我手动 dispatch 一次之后**第 8 次立刻
    中**——那就是判据。又一次「兜底出事的时候不吭声」。

    **`workflow_dispatch` 正是那条禁令明文列出的例外**（和 `repository_dispatch`
    一起），所以主动点一下就能绕过去，不用另配 PAT。
    ⚠️ **但「文档这么说」不等于「跑通了」，而 204 也不等于「跑起来了」。**
    `dispatches` 那个接口返回的 204 只保证 **GitHub 收下了这个请求**——
    工作流被停用、`pages.yml` 不在默认分支上、ref 指到没有这个文件的地方，
    都可能收下之后什么也不发生。**这正是「查产物，不查信号」**：信号是
    204，产物是**一条真的运行记录**。所以现在点完还要回头确认它出现了，
    并把 **run id 和 actor** 一起打进日志。

    判据是 `actor`：`github-actions[bot]` 才说明**是这段代码点的**；
    写着人名就说明那趟是有人手动补的（2026-08-04 那两条就是我补的，
    而它们看起来和自动触发一模一样）。

    ⚠️ **比「新东西出现」要比变化量，别比内容特征**——这里比的是 run id
    的集合差，不是时间戳也不是「最近有没有一条 workflow_dispatch」。
    后者当前就成立，循环一上来就为真。

    **点不动不算失败**（探活那道闸还在，最坏是摘掉按钮），**但必须出声**——
    否则「没点成」和「点成了」在日志上长得一模一样，而这正是这个 bug 藏了
    一整天的原因。
    """
    import time

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        logger.info("[Pages] 没有 GITHUB_TOKEN，不主动触发部署——"
                    "复制页要等别的 push 才会发布，探活可能一直 404")
        return False
    repo = os.environ.get("GITHUB_REPOSITORY", "robertyang87/tennislive")
    # 点之前先记下已经有哪些 run，等下拿集合差认出新的那条。
    before = pages_runs(token, repo, timeout=timeout)
    known = {rid for rid, _, _ in before} if before is not None else None

    url = (f"https://api.github.com/repos/{repo}/actions/"
           f"workflows/{_PAGES_WORKFLOW}/dispatches")
    try:
        r = requests.post(url, json={"ref": ref}, timeout=timeout,
                          headers=_gh_headers(token))
    except requests.RequestException as exc:
        logger.warning("[Pages] 触发部署失败（%s: %s）——复制页可能迟迟发不出来",
                       type(exc).__name__, exc)
        return False
    if r.status_code != 204:
        # 403 多半是工作流少了 `actions: write`；404 是文件名或 ref 不对。
        logger.warning("[Pages] 触发部署被拒：HTTP %s %s——"
                       "工作流要有 `permissions: actions: write` 并传 GITHUB_TOKEN",
                       r.status_code, (r.text or "")[:200])
        return False

    if known is None:
        # 读不到基线就没法比集合差。**说出来**，别让「没确认」混进「确认了」。
        logger.info("[Pages] 已请求重新发布（%s @ %s）——读不到运行列表，"
                    "这一趟确认不了它有没有真的跑起来", _PAGES_WORKFLOW, ref)
        return True

    deadline = time.monotonic() + confirm_seconds
    while True:
        for rid, actor, event in pages_runs(token, repo, timeout=timeout) or []:
            if rid in known:
                continue
            logger.info("[Pages] 已触发重新发布：run %s，actor=%s，event=%s",
                        rid, actor, event)
            return True
        if time.monotonic() >= deadline:
            break
        time.sleep(2.0)
    logger.warning(
        "[Pages] dispatch 收下了（204），但 %.0f 秒内没出现新的运行记录——"
        "204 只保证请求被接受，不保证它跑起来（工作流被停用？`%s` 不在 %s 上？）。"
        "复制页多半要探满全程才摘按钮",
        confirm_seconds, _PAGES_WORKFLOW, ref)
    return False


def drop_dead_copy_button(
    html_body: str, *, probe=None, attempts: int | None = None,
    delay: float | None = None, expect: str = "",
) -> tuple[str, str | None]:
    """发之前探一次复制页；取不到**或不是这一版**就把那个按钮摘掉。

    **这道闸必须装在「发」那一步，不是「渲」那一步。** 第一版我把
    `live_copy_page_url` 放进了生成流程，结果每次都把按钮拿掉——因为渲染
    排在提交之前，那一刻 copy.html 还没进仓库，Pages 当然取不到。安全是
    安全了，可它同时也让**能用的按钮永远出不来**：2026-07-29 蒂姆那条推送
    就是这么少了按钮的（run 30432435525）。

    `tennislive publish pushplus` 跑在提交之后，那才是链接真正该可达的时刻。
    放在这里还有一层好处：解说片、知识帖、赛程包共用同一个出口，一处装闸
    三条线都护住，不用各自记得调一次。

    **「可达」不等于「是这一版」。** 2026-07-29 那条赛程推送踩了这个：copy.html
    的新版本只在特性分支上，而 Pages 只服务 main，于是线上那份还是同一天早些
    时候生成的旧包。探到 200 就把按钮留下了，读者点开看到的是另一批场次——
    这比死链更糟，死链一眼能看出坏了，旧内容看着完全正常。

    所以给 `expect`（本地 copy.html 的标题，见 `copy_page_fingerprint`）：
    线上那份必须**包含这句话**才算数。Pages 重新发布要一两分钟，所以照旧
    重试几次再判——但**判据是内容对上，不是等够时间**。

    返回 (正文, 可达的 URL 或 None)，让调用方能如实打印判断依据——只在
    成功时出声的检查没法证明它真的看过。
    """
    match = _COPY_BUTTON_RE.search(html_body)
    if not match:
        return html_body, None
    url = match.group("url")
    ok = (
        _probe_page(
            url,
            attempts=_COPY_PAGE_ATTEMPTS if attempts is None else attempts,
            delay=_COPY_PAGE_RETRY_SECONDS if delay is None else delay,
            expect=expect,
        )
        if probe is None
        else probe(url)
    )
    if ok:
        return html_body, url
    # 只摘按钮，不动正文：复制页是文案的出口之一，另一个是消息里整段渲染的
    # 正文（可长按复制）。两个一起丢，这条文案就传不出去了。
    return _COPY_BUTTON_RE.sub("", html_body, count=1), None


def expected_first_hit(delay: float) -> int:
    """第几次探活**才可能**命中——从间隔算出来，不写死。

    第 1 次探活是紧跟在 `trigger_pages_build()` 之后发出的（中间只隔一次
    HTTP 往返），而点一下到部署完实测要
    `MEASURED_PAGES_DISPATCH_TO_LIVE_SECONDS` 秒。所以第 n 次探活距离那一下
    大约是 `(n-1) * delay` 秒，**第一次够得着的是**

        1 + ceil(MEASURED / delay)

    30 秒间隔 → 2；40 秒间隔 → 2；20 秒间隔 → 2；60 秒间隔 → 1。

    ⚠️ **这个函数是为了修一条搬错线的判据。** 原来那句告警写死「正常应该第 1
    次就中」——那句话只有在「第一次探活比那一下晚 19 秒以上」时才成立，而这条
    线上第一枪是**结构性打不中**的。2026-08-16 盘外招那条推送的日志里因此挂着
    一条 WARNING，说「这条链上多半还有别的没接上」，而链子好好的。

    CLAUDE.md 记过同一个形状：「判据要连它的时序前提一起搬」「一个搬错线的判据
    比没有判据坏——它会让下一个人去追一个不存在的问题，而且他找不到」。
    """
    if delay <= 0:
        return 1
    return 1 + math.ceil(MEASURED_PAGES_DISPATCH_TO_LIVE_SECONDS / delay)


def _say_probe_hit(nth: int, url: str, *, delay: float = _COPY_PAGE_RETRY_SECONDS) -> None:
    """探活命中时如实报第几次——两条探活路径共用，别各写一遍再对不上。

    ⚠️ **「正常是第几次」按间隔算，不写死 1**（见 `expected_first_hit`）：
    第一次探活紧跟在点 Pages 之后发出，而部署要 19 秒，所以 30 秒间隔下健康值
    本来就是 2。写死 1 的那一版会在**完全正常**的推送上挂一条
    「这条链上多半还有别的没接上」，把人引去追一个不存在的问题。
    """
    ok = expected_first_hit(delay)
    if nth <= ok:
        logger.info(
            # 措辞和下面那条 warning 保持一致（「最快能中的是第 N 次」），
            # 两行读起来才是同一件事的两面。
            "复制页第 %d 次探活命中（间隔 %.0fs，部署要 %.0fs，最快能中的是第 %d 次）"
            "：已是这一版的内容 %s",
            nth, delay, MEASURED_PAGES_DISPATCH_TO_LIVE_SECONDS, ok, url,
        )
        return
    logger.warning(
        "复制页第 %d 次探活才命中：%s——实测点一下到部署完只要 %.0f 秒，"
        "而探活间隔 %.0f 秒，最快能中的是第 %d 次。多出来的那几次说明这条链上"
        "还有别的没接上（点没点动、提交排在探活后面、指纹取错了那一格），"
        "别当成「Pages 今天慢」",
        nth, url, MEASURED_PAGES_DISPATCH_TO_LIVE_SECONDS,
        delay, ok,
    )


def _probe_page(
    url: str, *, attempts: int = 3, delay: float = 20.0, expect: str = ""
) -> bool:
    """200 且 Content-Type 是 text/html 才算数——soft-404 会返回 200。

    给了 `expect` 还要**正文里真的有这句话**：Pages 只服务 main，分支上的新
    copy.html 上不去，而线上那份旧的照样返回 200，光看状态码分不出来。

    ⚠️ **命中那一路也要出声，而且要报第几次。** 原来它只在失败时打日志，
    命中直接 `return True`——于是「第 1 次就中」在日志里是**零行**，
    和「这一步压根没跑」长得一模一样。而「探了七次才中」只是多六行 404，
    没有任何一行说「后来中了」。

    报第几次是有判据的：`MEASURED_PAGES_DISPATCH_TO_LIVE_SECONDS` 实测 19 秒、
    探活间隔 30 秒，所以**正常就该是第 1 次**。第 2 次以上要当成信号查，
    不是「Pages 今天慢」。
    """
    import time

    # **先点一下部署，再开始探。** 工作流自己提交的 push 不会触发 Pages，
    # 不点的话这个循环注定探满全程再摘按钮——见 `trigger_pages_build`。
    trigger_pages_build()

    for attempt in range(max(1, attempts)):
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200 and "text/html" in (
                response.headers.get("Content-Type", "").lower()
            ):
                if not expect or expect in response.text:
                    _say_probe_hit(attempt + 1, url, delay=delay)
                    return True
                # 这一条要出声：它和「取不到」是两种毛病，日志里混成一句就
                # 永远查不出到底是没发布还是发布了旧版
                logger.info("复制页是旧版（找不到「%s」）：%s", expect, url)
            else:
                logger.info("复制页暂不可达（HTTP %s）：%s", response.status_code, url)
        except requests.RequestException as e:  # noqa: PERF203
            logger.info("复制页探测失败：%s", e)
        if attempt + 1 < attempts:
            time.sleep(delay)
    return False


def live_copy_page_url(
    day, *, subdir: str = "schedule", attempts: int = 3, delay: float = 20.0
) -> str | None:
    """探复制页是否真的能打开；打不开就返回 None，让调用方别放那个按钮。

    Pages 重新发布要一两分钟，等得起，所以留几次重试；但**只在分支上存在的
    包永远等不到**（Pages 只服务 main），那时如实返回 None。
    """
    import time

    url = copy_page_url(day, subdir=subdir)
    for attempt in range(max(1, attempts)):
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200 and "text/html" in (
                response.headers.get("Content-Type", "").lower()
            ):
                # ⚠️ 这条路的间隔和 `_probe_page` 不一样（20s vs 30s），所以
                # 「正常是第几次」也不一样——`delay` 必须传进去，别让它按缺省
                # 那条线的间隔去算。这正是那句告警原来搬错线的同一个毛病。
                _say_probe_hit(attempt + 1, url, delay=delay)
                return url
            logger.info("复制页暂不可达（HTTP %s）：%s", response.status_code, url)
        except requests.RequestException as e:  # noqa: PERF203
            logger.info("复制页探测失败：%s", e)
        if attempt + 1 < attempts:
            time.sleep(delay)
    return None


def to_schedule_push_html(
    day,
    cards: list[str],
    *,
    events: list[str] | None = None,
    subdir: str = "schedule",
    xhs_text: str | None = None,
    copy_url: str | None = None,
) -> str:
    """今日赛程的推送消息：只有卡片图，没有小红书文案。

    和 ``to_push_html`` 分开写：那条是"待发稿"的审稿消息（标题 + 卡片 + 可复制
    正文 + 复制页链接），这条是直接给人看的赛程，多一个字都是噪声。

    图片地址仍写成 jsDelivr 的 output 路径：``publish.pushplus`` 会先按
    ``asset_dir`` 把它们换成本地文件上传到 PushPlus 图床，只有没配图床密钥时
    才真的走 CDN（那时需要图已经提交上去）。
    """
    raw = (xhs_text or "").strip()
    lines = raw.splitlines()
    title = lines[0].strip() if lines else ""
    body_start = 2 if len(lines) > 1 and not lines[1].strip() else 1
    body = "\n".join(lines[body_start:]).strip()

    parts = [
        '<div style="background-color:#f6f7f4;color:#17251f;padding:12px 10px;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">',
        '<div style="max-width:680px;margin:0 auto;background-color:#ffffff;'
        'border-top:5px solid #0b3d2e;padding:18px 16px 22px;">',
        '<div style="display:inline-block;background-color:#e7f5ea;color:#087747;'
        'font-size:12px;font-weight:bold;padding:4px 8px;border-radius:4px;">'
        f'今日赛程 · {day.month}.{day.day}</div>',
    ]
    # 标题单独成块：复制页有时不可用（GitHub Pages 只服务 main，分支上生成的
    # 包它取不到），那时这一块就是唯一能长按复制标题的地方。
    parts.append(
        '<div style="font-size:22px;line-height:1.38;font-weight:800;'
        'color:#102d23;margin:10px 0 4px;">'
        + html.escape(title or " / ".join(events or []))
        + "</div>"
    )
    if title:
        parts.append(
            '<div style="color:#7a8580;font-size:12px;margin:0 0 12px;">'
            "↑ 长按可复制标题</div>"
        )
    for name in cards:
        safe_name = html.escape(name, quote=True)
        url = f"{_CDN}/output/{day.isoformat()}/{subdir}/cards/{safe_name}"
        parts.append(
            f'<img src="{url}" data-src="{url}" width="100%" '
            'referrerpolicy="no-referrer" style="width:100%;border-radius:6px;'
            'margin:0 0 10px;display:block;" />'
        )
    if cards:
        parts.append(
            '<div style="color:#7a8580;font-size:12px;margin:0 0 18px;">'
            "长按保存图片 · 按当前顺序上传小红书</div>"
        )
    if body:
        parts.append(
            '<div style="border-left:3px solid #f1c84b;padding-left:12px;'
            'margin:4px 0 14px;font-size:13px;font-weight:bold;color:#087747;">'
            "可直接发布的正文</div>"
        )
        for paragraph in re.split(r"\n\s*\n", body):
            safe_paragraph = "<br/>".join(
                html.escape(line) for line in paragraph.splitlines()
            )
            style = (
                "color:#087747;font-size:14px;line-height:1.8;margin:14px 0 0;"
                if paragraph.lstrip().startswith("#")
                else "color:#25342e;font-size:15px;line-height:1.85;margin:0 0 13px;"
            )
            parts.append(f'<div style="{style}">{safe_paragraph}</div>')
    # 复制页的按钮只在链接**确认可达**时才放。
    #
    # 踩过：GitHub Pages 只服务 main，而赛程包是在特性分支上生成的，Pages 永远
    # 取不到——按钮点开就是 404。图片没事，是因为它们走 jsDelivr 并钉在 commit
    # SHA 上，任意 commit 都能取。pushplus.wait_for_images 也帮不上：它**故意**
    # 把 Pages 链接排除在外（Pages 发布延迟大，不该阻塞推送）。
    # 微信那条消息发出去就收不回来，所以宁可不放按钮，也不放一个死链。
    if raw and copy_url:
        parts.extend([
            '<div style="border-top:1px solid #e6ebe8;margin:18px 0 12px;"></div>',
            f'<a href="{html.escape(copy_url, quote=True)}" '
            'style="display:block;background-color:#0b3d2e;'
            'color:#ffffff;text-align:center;text-decoration:none;font-weight:bold;'
            'padding:13px 16px;border-radius:6px;margin:0 0 7px;">'
            "分别复制标题 / 正文</a>",
            '<div style="text-align:center;color:#7a8580;font-size:12px;">'
            "标题与正文已拆分，粘贴后即可发布</div>",
        ])
    parts.extend(["</div>", "</div>"])
    return "\n".join(parts)


def _label(m) -> str:
    g = group_by_tournament([m])[0]
    r = match_round_display(m)
    return f"{g.name_zh}{('·' + r) if r else ''}"


def is_chinese_involved_side(players) -> bool:
    from .common import CHINESE_PLAYER_NAMES
    from ..zh import player_zh

    for p in players:
        if (p.country or "").upper() in ("CHN", "CN"):
            return True
        if player_zh(p.name) in CHINESE_PLAYER_NAMES:
            return True
    return False
