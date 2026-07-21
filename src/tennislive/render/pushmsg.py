"""PushPlus 手机推送专用模板：窄屏友好 + 深色模式安全.

要点：
- 显式设置背景色和文字色（微信深色模式不会反转显式配色的卡片）
- 每条信息一行、行内容短，避免窄屏换行错乱
- 只放决策所需信息（焦点/中国军团/今晚看点），完整内容看仓库或公众号
"""

from __future__ import annotations

import html
import os
import re

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
_CDN = f"https://cdn.jsdelivr.net/gh/{_REPO}@main"
_OWNER, _REPO_NAME = _REPO.split("/", 1)
_PAGES = os.environ.get(
    "TENNISLIVE_PAGES_URL", f"https://{_OWNER}.github.io/{_REPO_NAME}"
).rstrip("/")

_ASSET_REVISION_RE = re.compile(r"[0-9a-fA-F]{7,40}")
_JSDELIVR_MAIN_RE = re.compile(
    r"(https://cdn\.jsdelivr\.net/gh/[^/@\s\"'<>]+/[^/@\s\"'<>]+)@main/"
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
    <section>
      <div class="label"><span>置顶评论</span><button type="button" data-copy="comment">复制评论</button></div>
      <textarea id="comment" readonly>{safe_comment}</textarea>
    </section>
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
                f'<img src="{url}" style="width:100%;border-radius:6px;'
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
