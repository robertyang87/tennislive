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
from ..timeutil import fmt_time_beijing
from .common import (
    curate_for_social,
    group_by_tournament,
    is_chinese_involved,
    match_round_display,
    side_display,
)
from .rating import stay_up_stars, top_results, top_schedule
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


def to_copy_page(xhs_text: str) -> str:
    """生成适合手机打开的一键复制页面。"""
    lines = xhs_text.splitlines()
    title = lines[0].strip() if lines else ""
    body_start = 2 if len(lines) > 1 and not lines[1].strip() else 1
    body = "\n".join(lines[body_start:]).strip()
    safe_title = html.escape(title)
    safe_body = html.escape(body)
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
    #body {{ min-height: 55vh; }}
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
    </section>
    <section>
      <div class="label"><span>正文</span><button type="button" data-copy="body">复制正文</button></div>
      <textarea id="body" readonly>{safe_body}</textarea>
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
      toast.textContent = id === 'title' ? '标题已复制' : '正文已复制';
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
) -> str:
    d = digest.today
    parts: list[str] = [_DARK_CSS, f'<div class="tl-card" style="{_CARD}">']
    parts.append(
        f'<div class="tl-title" style="{_TITLE}">🎾 网球晨报 · {d.month}月{d.day}日</div>'
    )
    parts.append(
        f'<div class="tl-head" style="{_HEAD}">{pick_headline_auto(digest)}</div>'
    )
    parts.append(_HR)

    cn_results = [m for m in digest.results if is_chinese_involved(m)][:4]
    cn_today = [
        m for m in digest.schedule + digest.live if is_chinese_involved(m)
    ][:3]
    if cn_results or cn_today:
        parts.append(f'<div class="tl-sec" style="{_SEC}">🇨🇳 中国军团</div>')
        for m in cn_results:
            w = m.winner_players() or []
            mark = "✅" if any(is_chinese_involved_side([p]) for p in w) else "❌"
            parts.append(
                f"{mark} {_short_side(m.home if m.winner == 0 else m.away)} "
                f"胜 {_short_side(m.away if m.winner == 0 else m.home)}<br/>"
                f'<span class="tl-dim" style="{_DIM}">{_score_of(m)} · {_label(m)}</span>'
            )
        for m in cn_today:
            parts.append(
                f"⏰ {fmt_time_beijing(m.start_utc)} {_short_side(m.home)} vs "
                f"{_short_side(m.away)}<br/>"
                f'<span class="tl-dim" style="{_DIM}">{_label(m)}</span>'
            )
        parts.append(_HR)

    focus = top_results([m for m in digest.results if m.is_singles], 3)
    focus = [m for m in focus if not is_chinese_involved(m)]
    if focus:
        parts.append(f'<div class="tl-sec" style="{_SEC}">🏆 昨夜焦点</div>')
        for m in focus:
            w, l = m.winner_players() or [], m.loser_players() or []
            if not w or not l:
                continue
            parts.append(
                f"{_short_side(w)} 胜 {_short_side(l)}<br/>"
                f'<span class="tl-dim" style="{_DIM}">{_score_of(m)} · {_label(m)}</span>'
            )
        parts.append(_HR)

    tonight = top_schedule([m for m in digest.schedule if m.is_singles], 3)
    if tonight:
        parts.append(f'<div class="tl-sec" style="{_SEC}">🌙 今晚看点</div>')
        for m in tonight:
            stars = "★" * stay_up_stars(m)
            parts.append(
                f"{fmt_time_beijing(m.start_utc)} {_short_side(m.home)} vs "
                f"{_short_side(m.away)}<br/>"
                f'<span class="tl-dim" style="{_DIM}">{_label(m)} · 熬夜指数 {stars}</span>'
            )
        parts.append(_HR)

    if xhs_text:
        parts.append(
            f'<div class="tl-sec" style="{_SEC}">📋 贴图发布文案</div>'
        )
        copy_url = f"{_PAGES}/output/{d.isoformat()}/copy.html"
        parts.append(
            f'<a href="{copy_url}" style="{_COPY_BUTTON}">打开并复制文案</a>'
        )
        parts.append(
            f'<div class="tl-dim" style="{_DIM}">标题、正文可分别一键复制。</div>'
        )
        parts.append(_HR)

    if cards:
        parts.append(
            f'<div class="tl-sec" style="{_SEC}">📸 今日卡片（长按保存 → 订阅号助手/小红书发图）</div>'
        )
        for name in cards:
            url = f"{_CDN}/output/{d.isoformat()}/cards/{name}"
            parts.append(
                f'<img src="{url}" style="width:100%;border-radius:8px;'
                f'margin:6px 0;display:block;" />'
            )
        parts.append(_HR)
    parts.append(
        f'<div class="tl-dim" style="{_DIM}">📦 原始文案：output/{d.isoformat()}/xiaohongshu.txt</div>'
    )
    parts.append("</div>")
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
