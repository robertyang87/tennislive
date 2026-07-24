"""Single-image tennis news flash card — a lightweight, timely post format.

Unlike the four-card knowledge deck (verified cover + story + explainer +
today), a flash card is one vertical image built to react to the day's tennis
news fast: a hook headline, one core fact or on-record quote, and a source
line — no external player photo, so it skips the heavy photo-verification
loop and can ship the same day.

The content architecture is deliberately flexible: pass whatever hook / quote
/ source fits the story. Sensitive topics must be gated upstream via
``render.sensitivity`` before an item is auto-published through this format.
Nothing here invents facts — callers supply verified text.
"""

from __future__ import annotations

import html
from pathlib import Path

from .webcards import _FOOTER, _masthead, _screenshot_pages

W, H = 1080, 1440


def flash_card_body(
    headline: str,
    *,
    quote: str,
    source_label: str,
    date_label: str,
    kicker: str = "网球快讯 · TENNIS FLASH",
) -> str:
    """Build one vertical flash-card HTML body (rendered inside the brand shell).

    ``headline`` is the news hook, ``quote`` the core fact or on-record quote to
    highlight, ``source_label`` a short attribution shown small at the bottom.
    All text is escaped; the layout is self-contained inline CSS so it renders
    without depending on deck-specific classes.
    """
    hook = html.escape(headline).replace("，", "，<br>", 1)
    quote_html = html.escape(quote)
    source_html = html.escape(source_label)
    bg = (
        "position:absolute;inset:0;z-index:0;"
        "background:radial-gradient(120% 80% at 50% 12%,#12503a 0%,#0b3a2a 45%,#072318 100%);"
    )
    # Center the content in the space between masthead and footer so a short
    # flash card fills the canvas instead of stranding an empty lower half.
    stage = (
        "position:relative;z-index:2;flex:1;display:flex;flex-direction:column;"
        "justify-content:center;gap:40px;"
    )
    kicker_style = (
        "color:#37e29a;font-size:27px;font-weight:700;letter-spacing:3px;"
    )
    h1_style = (
        "color:#f4fbf7;font-size:80px;line-height:1.24;font-weight:800;"
        "margin:18px 0 0;"
    )
    quote_style = (
        "padding:38px 40px;background:rgba(255,255,255,.06);"
        "border-left:8px solid #37e29a;border-radius:16px;color:#eaf5ef;"
        "font-size:44px;line-height:1.5;font-weight:600;"
    )
    source_style = "color:#9fb4aa;font-size:25px;margin-top:-16px;"
    return (
        '<div class="poster cover knowledge-page" data-visual="flash-card">'
        f'<div style="{bg}"></div>'
        + _masthead(date_label)
        + f'<div style="{stage}">'
        f'<div><div style="{kicker_style}">{kicker}</div>'
        f'<h1 style="{h1_style}">{hook}</h1></div>'
        f'<div style="{quote_style}">{quote_html}</div>'
        f'<div style="{source_style}">{source_html}</div>'
        "</div>"
        + _FOOTER
        + "</div>"
    )


def generate_flash_card(
    headline: str,
    *,
    quote: str,
    source_label: str,
    date_label: str,
    out_path: str | Path,
    theme: str = "dark",
    kicker: str = "网球快讯 · TENNIS FLASH",
) -> Path:
    """Render a flash-card body to a 1080x1440 social image and save it."""
    from .image_output import save_social_image

    body = flash_card_body(
        headline,
        quote=quote,
        source_label=source_label,
        date_label=date_label,
        kicker=kicker,
    )
    (_kind, image), = _screenshot_pages([("flash", body)], theme)
    return save_social_image(image, out_path)
