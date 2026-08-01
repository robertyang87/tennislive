"""PushPlus 手机推送专用模板：窄屏友好 + 深色模式安全.

要点：
- 显式设置背景色和文字色（微信深色模式不会反转显式配色的卡片）
- 每条信息一行、行内容短，避免窄屏换行错乱
- 只放决策所需信息（焦点/中国军团/今晚看点），完整内容看仓库或公众号
"""

from __future__ import annotations

import html
import logging
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


def to_push_html(
    digest: Digest,
    cards: list[str] | None = None,
    xhs_text: str | None = None,
    videos: list[str] | None = None,
) -> str:
    """Render the PushPlus review message as the actual Xiaohongshu post."""
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
                f'<a href="{copy_url}" style="display:block;background-color:#ff2442;'
                'color:#ffffff;text-align:center;text-decoration:none;font-weight:bold;'
                'padding:13px 16px;border-radius:6px;margin:0 0 7px;">'
                '分别复制标题 / 正文 / 置顶评论</a>',
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


def copy_page_fingerprint(path) -> str:
    """从本地 copy.html 里取一句能认出「是不是这一版」的话。

    用 `<h1>` 那行——它是当天文案的标题（如「7.29 今日赛程 | 王欣瑜战萨姆索诺娃」），
    换一版内容它必然跟着变，而模板里的固定文字（样式、按钮说明）不会。
    取不到就返回空串，调用方退回只探可达。
    """
    from pathlib import Path

    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group(1))).strip()


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
_COPY_PAGE_ATTEMPTS = int(os.environ.get("TENNISLIVE_COPYPAGE_ATTEMPTS") or 12)
_COPY_PAGE_RETRY_SECONDS = float(
    os.environ.get("TENNISLIVE_COPYPAGE_RETRY_SECONDS") or 30.0
)


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


def _probe_page(
    url: str, *, attempts: int = 3, delay: float = 20.0, expect: str = ""
) -> bool:
    """200 且 Content-Type 是 text/html 才算数——soft-404 会返回 200。

    给了 `expect` 还要**正文里真的有这句话**：Pages 只服务 main，分支上的新
    copy.html 上不去，而线上那份旧的照样返回 200，光看状态码分不出来。
    """
    import time

    for attempt in range(max(1, attempts)):
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200 and "text/html" in (
                response.headers.get("Content-Type", "").lower()
            ):
                if not expect or expect in response.text:
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
